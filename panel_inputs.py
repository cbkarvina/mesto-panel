#!/usr/bin/env python3
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from gpio_interface import GPIODevice, LOW, HIGH


@dataclass
class InputEvent:
    name: str
    event_type: str   # "pressed", "released", "changed", "rotated_cw", "rotated_ccw"
    state: int        # LOW / HIGH
    timestamp: float


class PanelInput:
    """
    One debounced input connected to a GPIO device (MCP23017, RPi GPIO, etc).
    Assumes pull-up wiring by default:
      released = HIGH
      pressed  = LOW
    """
    def __init__(
        self,
        name: str,
        mcp: GPIODevice,
        pin: int,
        kind: str = "button",         # "button" or "switch"
        active_low: bool = True,
        debounce_ms: int = 30,
        pullup: bool = True,
    ):
        self.name = name
        self.mcp = mcp
        self.pin = pin
        self.kind = kind
        self.active_low = active_low
        self.debounce_s = debounce_ms / 1000.0
        self.pullup = pullup

        # configure pin
        if self.pullup:
            self.mcp.setup_input_pullup(self.pin)
        else:
            self.mcp.pin_mode(self.pin, 1)

        # initial states
        raw = self.mcp.digital_read(self.pin)
        self.last_raw = raw
        self.stable_state = raw
        self.last_change_time = time.monotonic()

    def is_active_state(self, state: int) -> bool:
        if self.active_low:
            return state == LOW
        return state == HIGH

    def read(self) -> int:
        return self.stable_state

    def is_active(self) -> bool:
        return self.is_active_state(self.stable_state)

    def update(self) -> List[InputEvent]:
        """
        Returns list of events generated since last update.
        Usually 0 or 1 event, but list keeps API flexible.
        """
        events = []
        raw = self.mcp.digital_read(self.pin)
        now = time.monotonic()

        # raw change detected -> restart debounce timer
        if raw != self.last_raw:
            self.last_raw = raw
            self.last_change_time = now

        # if raw stayed changed long enough, accept new stable state
        if raw != self.stable_state and (now - self.last_change_time) >= self.debounce_s:
            old_state = self.stable_state
            self.stable_state = raw

            # generic change event
            events.append(InputEvent(
                name=self.name,
                event_type="changed",
                state=self.stable_state,
                timestamp=now
            ))

            # button/switch active/inactive transitions
            old_active = self.is_active_state(old_state)
            new_active = self.is_active_state(self.stable_state)

            if not old_active and new_active:
                events.append(InputEvent(
                    name=self.name,
                    event_type="pressed",
                    state=self.stable_state,
                    timestamp=now
                ))
            elif old_active and not new_active:
                events.append(InputEvent(
                    name=self.name,
                    event_type="released",
                    state=self.stable_state,
                    timestamp=now
                ))

        return events


class EncoderInput:
    """
    Quadrature rotary encoder (EC11, e.g. EC11E15-20P20C) on two GPIO pins.

    The EC11E15-20P20C has 20 detents and 20 pulses per revolution, so each
    detent click is one full quadrature cycle = 4 quarter-steps. This decoder
    counts quarter-steps from a transition table and emits one
    "rotated_cw" / "rotated_ccw" event per detent (every `steps_per_detent`
    quarter-steps).

    It is designed for *polled* reading over a (slow) I2C expander: if a poll
    misses one intermediate state (so both A and B appear to change at once),
    the decoder recovers by continuing in the last known direction instead of
    discarding the movement. This keeps it working at normal turning speed,
    not only when turning very slowly.

    Wiring: pins A and B to GPIO inputs, encoder common pin to GND, internal
    pull-ups enabled (both lines idle HIGH at a detent).
    """

    # Quarter-step delta for each transition, indexed by (prev << 2) | curr
    # where each 2-bit state is (A << 1) | B. Valid single-step transitions
    # yield +/-1; "no change" and illegal double-steps yield 0.
    _TRANSITION = (
        0, -1, +1, 0,
        +1, 0, 0, -1,
        -1, 0, 0, +1,
        0, +1, -1, 0,
    )

    # Both A and B differ between two reads -> exactly one state was skipped.
    _DOUBLE_STEP_MASK = 0b11

    def __init__(
        self,
        name: str,
        mcp: GPIODevice,
        pin_a: int,
        pin_b: int,
        pullup: bool = True,
        reverse: bool = False,
        steps_per_detent: int = 4,
    ):
        self.name = name
        self.mcp = mcp
        self.pin_a = pin_a
        self.pin_b = pin_b
        self.pullup = pullup
        self.reverse = reverse
        self.steps_per_detent = max(1, steps_per_detent)

        if self.pullup:
            self.mcp.setup_input_pullup(self.pin_a)
            self.mcp.setup_input_pullup(self.pin_b)
        else:
            self.mcp.pin_mode(self.pin_a, 1)
            self.mcp.pin_mode(self.pin_b, 1)

        self.prev_state = self._read_pins()
        self.stable_state = self.prev_state
        self.sub_steps = 0      # accumulated quarter-steps toward a detent
        self.last_dir = 0       # +1 = CW, -1 = CCW (for skip recovery)

    def _read_pins(self) -> int:
        a, b = self.mcp.read_pin_pair(self.pin_a, self.pin_b)
        return ((a & 0x1) << 1) | (b & 0x1)

    def update(self) -> List[InputEvent]:
        events: List[InputEvent] = []

        curr = self._read_pins()
        if curr == self.prev_state:
            return events

        delta = self._TRANSITION[(self.prev_state << 2) | curr]

        if delta == 0 and (self.prev_state ^ curr) == self._DOUBLE_STEP_MASK:
            # One intermediate state was missed by polling; both lines flipped.
            # Assume the rotation continued in the last known direction.
            delta = 2 * self.last_dir

        self.prev_state = curr
        self.stable_state = curr

        if delta == 0:
            return events

        self.last_dir = 1 if delta > 0 else -1
        self.sub_steps += delta

        now = time.monotonic()

        while self.sub_steps >= self.steps_per_detent:
            self.sub_steps -= self.steps_per_detent
            cw = not self.reverse
            events.append(InputEvent(
                name=self.name,
                event_type="rotated_cw" if cw else "rotated_ccw",
                state=self.stable_state,
                timestamp=now,
            ))

        while self.sub_steps <= -self.steps_per_detent:
            self.sub_steps += self.steps_per_detent
            cw = self.reverse
            events.append(InputEvent(
                name=self.name,
                event_type="rotated_cw" if cw else "rotated_ccw",
                state=self.stable_state,
                timestamp=now,
            ))

        return events


class PanelInputs:
    """
    Manager for many debounced inputs across one or more GPIO devices.
    """
    def __init__(self, poll_interval_ms: int = 5):
        self.inputs: Dict[str, PanelInput] = {}
        self.encoders: Dict[str, EncoderInput] = {}
        self.callbacks: List[Callable[[InputEvent], None]] = []
        self.poll_interval_s = poll_interval_ms / 1000.0

    def add_button(
        self,
        name: str,
        mcp: GPIODevice,
        pin: int,
        debounce_ms: int = 30,
        active_low: bool = True,
        pullup: bool = True,
    ):
        self.inputs[name] = PanelInput(
            name=name,
            mcp=mcp,
            pin=pin,
            kind="button",
            active_low=active_low,
            debounce_ms=debounce_ms,
            pullup=pullup,
        )

    def add_switch(
        self,
        name: str,
        mcp: GPIODevice,
        pin: int,
        debounce_ms: int = 30,
        active_low: bool = True,
        pullup: bool = True,
    ):
        self.inputs[name] = PanelInput(
            name=name,
            mcp=mcp,
            pin=pin,
            kind="switch",
            active_low=active_low,
            debounce_ms=debounce_ms,
            pullup=pullup,
        )

    def add_encoder(
        self,
        name: str,
        mcp: GPIODevice,
        pin_a: int,
        pin_b: int,
        pullup: bool = True,
        reverse: bool = False,
        steps_per_detent: int = 4,
    ):
        self.encoders[name] = EncoderInput(
            name=name,
            mcp=mcp,
            pin_a=pin_a,
            pin_b=pin_b,
            pullup=pullup,
            reverse=reverse,
            steps_per_detent=steps_per_detent,
        )

    def on_event(self, callback: Callable[[InputEvent], None]):
        self.callbacks.append(callback)

    def get(self, name: str) -> PanelInput:
        return self.inputs[name]

    def is_active(self, name: str) -> bool:
        if name in self.inputs:
            return self.inputs[name].is_active()
        if name in self.encoders:
            # Encoders are relative-motion inputs and don't have a stable active state.
            return False
        raise KeyError(name)

    def state(self, name: str) -> int:
        if name in self.inputs:
            return self.inputs[name].read()
        if name in self.encoders:
            return self.encoders[name].stable_state
        raise KeyError(name)

    def update(self) -> List[InputEvent]:
        """
        Poll all inputs once and return generated events.
        """
        all_events: List[InputEvent] = []

        for inp in self.inputs.values():
            events = inp.update()
            if events:
                all_events.extend(events)

        for enc in self.encoders.values():
            events = enc.update()
            if events:
                all_events.extend(events)

        for ev in all_events:
            for cb in self.callbacks:
                cb(ev)

        return all_events

    def loop_forever(self):
        while True:
            self.update()
            time.sleep(self.poll_interval_s)