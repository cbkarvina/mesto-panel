#!/usr/bin/env python3
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

import board
import neopixel


Color = Tuple[int, int, int]


# ------------------------------------------------------------
# Basic colors
# ------------------------------------------------------------
BLACK   = (0, 0, 0)
WHITE   = (255, 255, 255)
RED     = (255, 0, 0)
GREEN   = (0, 255, 0)
BLUE    = (0, 0, 255)
YELLOW  = (255, 180, 0)
ORANGE  = (255, 80, 0)
CYAN    = (0, 255, 255)
MAGENTA = (255, 0, 255)

DIM_BLUE   = (0, 0, 30)
DIM_WHITE  = (20, 20, 20)
DIM_GREEN  = (0, 30, 0)
DIM_RED    = (30, 0, 0)
DIM_YELLOW = (30, 20, 0)


def scale_color(color: Color, brightness: float) -> Color:
    brightness = max(0.0, min(1.0, brightness))
    return (
        int(color[0] * brightness),
        int(color[1] * brightness),
        int(color[2] * brightness),
    )


@dataclass
class Segment:
    name: str
    start: int
    length: int


class SegmentAnimation:
    """
    Simple animation state for one segment.
    modes:
      - solid
      - blink
      - pulse
      - off
    """
    def __init__(self, color: Color = BLACK, mode: str = "off", period: float = 1.0):
        self.color = color
        self.mode = mode
        self.period = period
        self.phase = 0.0  # optional future use


class CityLeds:
    def __init__(
        self,
        led_count: int = 84,
        pin=board.D18,
        brightness: float = 0.2,
        auto_write: bool = False,
        pixel_order=neopixel.GRB,
    ):
        self.led_count = led_count
        self._show_disabled = False
        self.pixels = neopixel.NeoPixel(
            pin,
            led_count,
            brightness=brightness,
            auto_write=auto_write,
            pixel_order=pixel_order,
        )

        self.segments: Dict[str, Segment] = {}
        self.animations: Dict[str, SegmentAnimation] = {}
        self.segment_overrides: Dict[str, Optional[List[Color]]] = {}

        # for blinking/pulse timing
        self._last_update = time.monotonic()

        # default segment map for Tajemné město
        self._setup_default_segments()

    # ------------------------------------------------------------
    # Segment map
    # ------------------------------------------------------------
    def _setup_default_segments(self):
        self.add_segment("power", 11, 2)
        self.add_segment("power_bar", 13, 5)

        self.add_segment("rescue", 18, 8)
        self.add_segment("comms", 26, 8)
        self.add_segment("transport", 34, 8)
        self.add_segment("core", 42, 8)

        self.add_segment("alarm", 50, 8)
        self.add_segment("misc", 58, 6)

        self.add_segment("encoder1_letters", 64, 10)
        self.add_segment("encoder2_letters", 74, 10)

        # Komunikační modul: první LED z pásku slouží jako Morse výstup.
        # Rezervované pixely nikdy nepřepíše běžné vykreslování segmentů;
        # ovládají se přímo (viz set_comms_led).
        self.comms_morse_led = 10
        self.reserved_pixels = frozenset({self.comms_morse_led})

    def add_segment(self, name: str, start: int, length: int):
        if start < 0 or length <= 0 or start + length > self.led_count:
            raise ValueError(f"Invalid segment {name}: start={start}, length={length}")
        self.segments[name] = Segment(name, start, length)
        self.animations[name] = SegmentAnimation()
        self.segment_overrides[name] = None

    # ------------------------------------------------------------
    # Low-level pixel ops
    # ------------------------------------------------------------
    def _segment_indices(self, name: str) -> range:
        seg = self.segments[name]
        return range(seg.start, seg.start + seg.length)

    def _set_pixel(self, index: int, color: Color):
        """Zapíše pixel jen pokud není rezervovaný (viz reserved_pixels)."""
        if index in self.reserved_pixels:
            return
        self.pixels[index] = color

    def set_comms_led(self, color: Color, show: bool = True):
        """Ovládá Morse LED komunikace (přímý zápis do rezervovaného pixelu)."""
        self.pixels[self.comms_morse_led] = color
        if show:
            self.show()

    def show(self):
        if self._show_disabled:
            return

        try:
            self.pixels.show()
        except RuntimeError as exc:
            message = str(exc)
            if "Failed to create mailbox device" in message or "ws2811_init failed" in message:
                self._show_disabled = True
                print(f"NeoPixel output disabled: {message}")
                return
            raise

    def clear(self, show: bool = True):
        for i in range(self.led_count):
            self._set_pixel(i, BLACK)
        if show:
            self.show()

    def fill_segment(self, name: str, color: Color, show: bool = True):
        self.segment_overrides[name] = None
        for i in self._segment_indices(name):
            self._set_pixel(i, color)
        if show:
            self.show()

    def clear_segment(self, name: str, show: bool = True):
        self.fill_segment(name, BLACK, show=show)

    # ------------------------------------------------------------
    # Animation state control
    # ------------------------------------------------------------
    def set_segment(self, name: str, color: Color, mode: str = "solid", period: float = 1.0):
        if name not in self.segments:
            raise KeyError(f"Unknown segment: {name}")
        self.segment_overrides[name] = None
        self.animations[name] = SegmentAnimation(color=color, mode=mode, period=period)

    def set_off(self, name: str):
        self.set_segment(name, BLACK, "off")

    def flash_alarm(self, name: str, color: Color = RED, period: float = 0.5):
        self.set_segment(name, color, mode="blink", period=period)

    def pulse_segment(self, name: str, color: Color = CYAN, period: float = 1.2):
        self.set_segment(name, color, mode="pulse", period=period)

    # ------------------------------------------------------------
    # High-level system statuses
    # ------------------------------------------------------------
    def set_system_status(self, system_name: str, status: str, animate: bool = True):
        """
        status:
          ok, warning, failure, offline, repaired, locked
        """
        if status == "ok":
            self.set_segment(system_name, GREEN, "solid")
        elif status == "warning":
            self.set_segment(system_name, YELLOW, "solid")
        elif status == "failure":
            mode = "blink" if animate else "solid"
            self.set_segment(system_name, RED, mode, period=0.6)
        elif status == "offline":
            self.set_segment(system_name, DIM_BLUE, "solid")
        elif status == "repaired":
            self.set_segment(system_name, CYAN, "pulse", period=1.2)
        elif status == "locked":
            self.set_segment(system_name, MAGENTA, "solid")
        else:
            self.set_segment(system_name, WHITE, "solid")

    def set_power_level(self, percent: int, show: bool = True):
        """
        Display power level on segment 'power_bar'
        """
        percent = max(0, min(100, percent))
        seg = self.segments["power_bar"]
        lit = round(seg.length * percent / 100)
        override: List[Color] = []

        for idx, i in enumerate(self._segment_indices("power_bar")):
            if idx < lit:
                # choose color by level
                if percent < 40:
                    color = RED
                elif percent < 70:
                    color = YELLOW
                else:
                    color = GREEN
            else:
                color = BLACK

            self._set_pixel(i, color)
            override.append(color)

        self.segment_overrides["power_bar"] = override

        if show:
            self.show()

    def set_fragment_count(self, count: int, max_count: int = 5, show: bool = True):
        """
        Example use of 'misc' segment to show found fragments.
        """
        count = max(0, min(count, max_count))
        seg = self.segments["misc"]
        lit = min(seg.length, count)
        override: List[Color] = []

        for idx, i in enumerate(self._segment_indices("misc")):
            color = CYAN if idx < lit else BLACK
            self._set_pixel(i, color)
            override.append(color)

        self.segment_overrides["misc"] = override

        if show:
            self.show()

    def set_encoder_letter(self, encoder_name: str, index: int, show: bool = True):
        """
        Display current encoder letter position on a 10-LED bar as a single dot.
        index: 0..9 where 0=A and 9=J.
        Exactly one LED is ON at a time.
        """
        if encoder_name == "medic_code_1":
            segment_name = "encoder1_letters"
            on_color = CYAN
        elif encoder_name == "medic_code_2":
            segment_name = "encoder2_letters"
            on_color = MAGENTA
        else:
            # Encoders without a dedicated LED letter bar (e.g. medic_code_3)
            # only drive the MAX7219 display, so there is nothing to light here.
            return

        if segment_name not in self.segments:
            return

        idx = index % 10
        override: List[Color] = []

        for offset, pixel_index in enumerate(self._segment_indices(segment_name)):
            color = on_color if offset == idx else BLACK
            self._set_pixel(pixel_index, color)
            override.append(color)

        self.segment_overrides[segment_name] = override

        if show:
            self.show()

    # ------------------------------------------------------------
    # Update animations
    # ------------------------------------------------------------
    def update(self):
        now = time.monotonic()

        for name, anim in self.animations.items():
            seg = self.segments[name]
            override = self.segment_overrides.get(name)

            if override is not None:
                for offset, i in enumerate(range(seg.start, seg.start + seg.length)):
                    self._set_pixel(i, override[offset])
                continue

            if anim.mode == "off":
                color = BLACK

            elif anim.mode == "solid":
                color = anim.color

            elif anim.mode == "blink":
                # on/off square wave
                if anim.period <= 0:
                    color = anim.color
                else:
                    phase = (now % anim.period) / anim.period
                    color = anim.color if phase < 0.5 else BLACK

            elif anim.mode == "pulse":
                # triangle pulse 0.15..1.0
                if anim.period <= 0:
                    color = anim.color
                else:
                    phase = (now % anim.period) / anim.period
                    if phase < 0.5:
                        b = 0.15 + (phase / 0.5) * 0.85
                    else:
                        b = 1.0 - ((phase - 0.5) / 0.5) * 0.85
                    color = scale_color(anim.color, b)

            else:
                color = anim.color

            for i in range(seg.start, seg.start + seg.length):
                self._set_pixel(i, color)

        self.show()
        self._last_update = now

    # ------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------
    def debug_segments(self):
        for name, seg in self.segments.items():
            print(f"{name:12s}: start={seg.start:2d}, len={seg.length}")