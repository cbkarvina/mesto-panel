#!/usr/bin/env python3
import time
from typing import Callable, Optional

from mcp23017 import MCP23017, MCP23017Error
from panel_inputs import PanelInputs, InputEvent
from city_leds import CityLeds
from max7219_display import (
    Max7219Chain,
    Max7219Display,
    Max7219DisplayError,
    Max7219SevenSegDisplay,
)


class CityPanel:
    """
    Hardware abstraction for the 'Tajemné město' control panel.
    Handles:
      - MCP23017 input devices
      - WS2812B / NeoPixel LEDs
      - MAX7219 8x8 display
    """

    def __init__(
        self,
        init_inputs: bool = True,
        init_leds: bool = True,
        init_display: bool = True,
    ):
        self.mcp1 = None
        self.mcp2 = None
        self.inputs = None
        self.leds = None
        self.chain = None
        self.display = None
        self.display2 = None
        self.display7seg = None
        self._encoder_display_state = {
            "medic_code_1": 0,
            "medic_code_2": 0,
        }
        # When set, display1 is cleared once time.monotonic() reaches this value.
        self._display1_clear_at: Optional[float] = None
        # When set, display2 is cleared once time.monotonic() reaches this value.
        self._display2_clear_at: Optional[float] = None
        # COMMS 7-seg: live morse preview + timed word display after submit.
        self._display7seg_revert_at: Optional[float] = None
        self._last_morse_code = ""
        # COMMS 7-seg: error blink of an invalid morse code.
        self._blink_code = ""
        self._blink_deadline: Optional[float] = None
        self._blink_toggle_at: Optional[float] = None
        self._blink_on = False
        # COMMS 7-seg: one-shot animation (e.g. after clearing the word).
        self._anim7seg_frames: Optional[list] = None
        self._anim7seg_index = 0
        self._anim7seg_next_at: Optional[float] = None
        self._anim7seg_interval = 0.06
        self._event_callback: Optional[Callable[[InputEvent], None]] = None

        # ---------------------------
        # Input expanders
        # ---------------------------
        if init_inputs:
            self.mcp1 = MCP23017(address=0x20, busnum=1)
            self.mcp2 = MCP23017(address=0x21, busnum=1)
     
            self.inputs = PanelInputs(poll_interval_ms=5)
            self._setup_inputs()
            self.inputs.on_event(self._handle_input_event)

        # ---------------------------
        # LED layer
        # ---------------------------
        if init_leds:
            self.leds = CityLeds(
                led_count=84,     # includes 2x10 LEDs for encoder letter indicators
                brightness=0.1,   # lower = safer for power draw
            )

            # initial panel state
            self._set_boot_led_state()

        # ---------------------------
        # MAX7219 display layer
        # ---------------------------
        if init_display:
            # All three MAX7219 modules are daisy-chained on a single SPI line.
            # Order from the Pi's MOSI/DIN (module 0 = closest):
            #   module 0 = matrix #1, module 1 = matrix #2, module 2 = 7-segment
            try:
                self.chain = Max7219Chain(bus=0, device=0, num_modules=3)
            except Max7219DisplayError as exc:
                print(f"MAX7219 chain disabled: {exc}")
                self.chain = None

            if self.chain is not None:
                try:
                    self.display = Max7219Display(chain=self.chain, module_index=0, intensity=4)
                    self.display.set_char("A")
                except Max7219DisplayError as exc:
                    print(f"MAX7219 display #1 disabled: {exc}")
                    self.display = None

                try:
                    self.display2 = Max7219Display(chain=self.chain, module_index=1, intensity=4, rotate180=True)
                    self.display2.set_char("A")
                except Max7219DisplayError as exc:
                    print(f"MAX7219 display #2 disabled: {exc}")
                    self.display2 = None

                try:
                    self.display7seg = Max7219SevenSegDisplay(chain=self.chain, module_index=2, intensity=4)
                    self.display7seg.clear()
                except Max7219DisplayError as exc:
                    print(f"MAX7219 7-seg display disabled: {exc}")
                    self.display7seg = None

    # ------------------------------------------------------------------
    # INPUT SETUP
    # ------------------------------------------------------------------
    def _setup_inputs(self):
        # ===== MCP1 =====
        # POWER
        # self.inputs.add_switch("power_hydro", self.mcp1, 0)
        # self.inputs.add_switch("power_solar", self.mcp1, 1)
        # self.inputs.add_switch("power_diesel", self.mcp1, 2)
        # self.inputs.add_switch("power_grid", self.mcp1, 3)
        # self.inputs.add_button("power_stabilize", self.mcp1, 4)

        # # RESCUE
        # self.inputs.add_button("fire", self.mcp1, 5)
        # self.inputs.add_button("medical", self.mcp1, 6)
        # self.inputs.add_button("police", self.mcp1, 7)

        # # COMMS
        # self.inputs.add_button("comms_send", self.mcp1, 8)
        # self.inputs.add_button("comms_decode", self.mcp1, 9)
        # self.inputs.add_button("comms_ack", self.mcp1, 10)

        # TRANSPORT
        # self.inputs.add_switch("transport_route_1", self.mcp1, 11)
        # self.inputs.add_switch("transport_route_2", self.mcp1, 12)
        # self.inputs.add_switch("transport_route_3", self.mcp1, 13)
        # self.inputs.add_button("transport_reset", self.mcp1, 14)
        self.inputs.add_encoder("medic_code_1", self.mcp1, pin_a=0, pin_b=1)
        self.inputs.add_encoder("medic_code_2", self.mcp1, pin_a=2, pin_b=3)
        self.inputs.add_encoder("medic_code_3", self.mcp1, pin_a=4, pin_b=5)

        # CORE
        self.inputs.add_button("core_activate", self.mcp1, 6)

        # 4 přepínače masky (které pozice se počítají / přidají tlačítkem Přidat)
        self.inputs.add_switch("morse_el_1", self.mcp1, 8)
        self.inputs.add_switch("morse_el_2", self.mcp1, 9)
        self.inputs.add_switch("morse_el_3", self.mcp1, 10)
        self.inputs.add_switch("morse_el_4", self.mcp1, 11)
        # 4 přepínače symbolu (zapnuto = tečka '.', vypnuto = čárka '-')
        self.inputs.add_switch("morse_act_1", self.mcp1, 12)
        self.inputs.add_switch("morse_act_2", self.mcp1, 13)
        self.inputs.add_switch("morse_act_3", self.mcp1, 14)
        self.inputs.add_switch("morse_act_4", self.mcp1, 15)
        # ===== MCP2 (0x21): modul KOMUNIKACE — Morse vysílač =====
        # tlačítka back, add, submit
        self.inputs.add_button("morse_add", self.mcp2, 0)
        self.inputs.add_button("morse_del", self.mcp2, 1)
        self.inputs.add_button("morse_send", self.mcp2, 2)

    # ------------------------------------------------------------------
    # EVENT HANDLING
    # ------------------------------------------------------------------
    def _handle_input_event(self, event: InputEvent):
        if self._event_callback:
            self._event_callback(event)

    def set_event_callback(self, callback: Callable[[InputEvent], None]):
        self._event_callback = callback

    # ------------------------------------------------------------------
    # PANEL UPDATE
    # ------------------------------------------------------------------
    def update(self):
        """
        Poll inputs + update LED animations.
        """
        if self.inputs is not None:
            self.inputs.update()
        if self.leds is not None:
            self.leds.update()
        if (
            self._display1_clear_at is not None
            and time.monotonic() >= self._display1_clear_at
        ):
            self._display1_clear_at = None
            if self.display is not None:
                self.display.clear(show=True)
        if (
            self._display2_clear_at is not None
            and time.monotonic() >= self._display2_clear_at
        ):
            self._display2_clear_at = None
            if self.display2 is not None:
                self.display2.clear(show=True)
        # One-shot 7-seg animation (non-blocking). Takes precedence over the
        # revert/blink timers, which are cancelled when it starts.
        if self._anim7seg_frames is not None and self.display7seg is not None:
            now = time.monotonic()
            if self._anim7seg_next_at is not None and now >= self._anim7seg_next_at:
                self._anim7seg_index += 1
                if self._anim7seg_index >= len(self._anim7seg_frames):
                    self._anim7seg_frames = None
                    self._anim7seg_next_at = None
                    # Animation finished: back to the live morse preview.
                    self.display7seg.set_morse(self._last_morse_code)
                else:
                    self._anim7seg_next_at = now + self._anim7seg_interval
                    self.display7seg.set_morse(self._anim7seg_frames[self._anim7seg_index])
        # After a submitted word has been shown, revert the COMMS 7-seg back to
        # the live morse preview of the current switch selection.
        if (
            self._display7seg_revert_at is not None
            and time.monotonic() >= self._display7seg_revert_at
        ):
            self._display7seg_revert_at = None
            if self.display7seg is not None:
                self.display7seg.set_morse(self._last_morse_code)
        # Error blink of an invalid morse code (non-blocking).
        if self._blink_deadline is not None and self.display7seg is not None:
            now = time.monotonic()
            if now >= self._blink_deadline:
                self._blink_deadline = None
                self._blink_toggle_at = None
                # Back to the live preview of the current switch selection.
                self.display7seg.set_morse(self._last_morse_code)
            elif self._blink_toggle_at is not None and now >= self._blink_toggle_at:
                self._blink_on = not self._blink_on
                self._blink_toggle_at = now + 0.15
                if self._blink_on:
                    self.display7seg.set_morse(self._blink_code)
                else:
                    self.display7seg.clear(show=True)

    def loop_forever(self):
        while True:
            self.update()

    # ------------------------------------------------------------------
    # INPUT HELPERS
    # ------------------------------------------------------------------
    def is_active(self, name: str) -> bool:
        if self.inputs is None:
            raise RuntimeError("Panel inputs are not initialized")
        return self.inputs.is_active(name)

    # ------------------------------------------------------------------
    # LED HELPERS
    # ------------------------------------------------------------------
    def _set_boot_led_state(self):
        if self.leds is None:
            return
        self.leds.clear(show=False)

        self.set_system_status("power", "failure", animate=False)
        self.set_system_status("rescue", "warning")
        self.set_system_status("comms", "offline")
        self.set_system_status("transport", "offline")
        self.set_system_status("core", "locked")

        self.set_power_level(0, show=False)
        self.set_fragment_count(0, show=False)
        self.set_encoder_letter("medic_code_1", 0, show=False)
        self.set_encoder_letter("medic_code_2", 0, show=False)
        self.set_encoder_letter("medic_code_3", 0, show=False)

        self.leds.update()

    def set_system_status(self, system_name: str, status: str, animate: bool = True):
        if self.leds is None:
            raise RuntimeError("Panel LEDs are not initialized")
        self.leds.set_system_status(system_name, status, animate=animate)

    def set_power_level(self, percent: int, show: bool = True):
        if self.leds is None:
            raise RuntimeError("Panel LEDs are not initialized")
        self.leds.set_power_level(percent, show=show)

    def set_fragment_count(self, count: int, max_count: int = 5, show: bool = True):
        if self.leds is None:
            raise RuntimeError("Panel LEDs are not initialized")
        self.leds.set_fragment_count(count, max_count=max_count, show=show)

    def set_encoder_letter(self, encoder_name: str, index: int, show: bool = True):
        if self.leds is None:
            raise RuntimeError("Panel LEDs are not initialized")
        self.leds.set_encoder_letter(encoder_name, index, show=show)

    def flash_alarm(self, system_name: str):
        if self.leds is None:
            raise RuntimeError("Panel LEDs are not initialized")
        self.leds.flash_alarm(system_name)

    def set_indicator(self, name: str, color, mode: str = "solid"):
        if self.leds is None:
            raise RuntimeError("Panel LEDs are not initialized")
        self.leds.set_segment(name, color, mode=mode)

    # ------------------------------------------------------------------
    # DISPLAY HELPERS
    # ------------------------------------------------------------------
    def set_display_char(self, char: str):
        if self.display is None:
            return
        self.display.set_char(char)

    def set_display_letter_index(self, index: int):
        if self.display is None:
            return
        self.display.set_index_letter(index)

    def set_display_symbol_index(self, index: int):
        if self.display is None:
            return
        self.display.set_index_symbol(index)

    def set_display2_char(self, char: str):
        if self.display2 is None:
            return
        self.display2.set_char(char)

    def set_display2_letter_index(self, index: int):
        if self.display2 is None:
            return
        self.display2.set_index_letter(index)

    def set_display2_symbol_index(self, index: int):
        if self.display2 is None:
            return
        self.display2.set_index_symbol(index)

    def set_encoder_display(self, encoder_name: str, index: int):
        # All medic_code encoders share display2 (mounted upside down): whichever
        # one moved last shows its value for 2 seconds, then display2 auto-clears.
        #   medic_code_1 -> letter A..J
        #   medic_code_2 -> digit 0..9
        #   medic_code_3 -> symbol (10 custom glyphs)
        if encoder_name == "medic_code_1":
            self.set_display2_letter_index(index)
            self._display2_clear_at = time.monotonic() + 2.0
        elif encoder_name == "medic_code_2":
            self.set_display2_char(str(index % 10))
            self._display2_clear_at = time.monotonic() + 2.0
        elif encoder_name == "medic_code_3":
            self.set_display2_symbol_index(index)
            self._display2_clear_at = time.monotonic() + 2.0

    def set_display7seg_text(self, text: str):
        if self.display7seg is None:
            return
        self.display7seg.set_text(text)

    def set_display7seg_morse(self, code: str):
        # Live preview of the morse selected by the 4 element switches. Held
        # back while a submitted word is being shown for its 2s window, or
        # while an error code is blinking.
        self._last_morse_code = code
        if (
            self._display7seg_revert_at is not None
            or self._blink_deadline is not None
            or self._anim7seg_frames is not None
            or self.display7seg is None
        ):
            return
        self.display7seg.set_morse(code)

    def blink_display7seg_morse(self, code: str, duration: float = 1.2):
        # Blink an invalid morse code, then revert to the live preview.
        if self.display7seg is None:
            return
        # A button press forces this display: cancel any pending word window.
        self._display7seg_revert_at = None
        self._anim7seg_frames = None
        self._blink_code = code
        self._blink_on = True
        self._blink_deadline = time.monotonic() + duration
        self._blink_toggle_at = time.monotonic() + 0.15
        self.display7seg.set_morse(code)

    def show_display7seg_word(self, word: str, seconds: float = 2.0):
        # Show the entered word for a fixed time, then revert to morse preview.
        if self.display7seg is None:
            return
        # A button press forces this display: cancel any running error blink.
        self._blink_deadline = None
        self._blink_toggle_at = None
        self._anim7seg_frames = None
        self.display7seg.set_text(word)
        self._display7seg_revert_at = time.monotonic() + seconds

    def play_display7seg_anim(self, frames, interval: float = 0.06):
        # Play a one-shot sequence of morse frames, then revert to live preview.
        if self.display7seg is None or not frames:
            return
        # Take over the display: cancel word window and error blink.
        self._display7seg_revert_at = None
        self._blink_deadline = None
        self._blink_toggle_at = None
        self._anim7seg_frames = list(frames)
        self._anim7seg_index = 0
        self._anim7seg_interval = interval
        self._anim7seg_next_at = time.monotonic() + interval
        self.display7seg.set_morse(self._anim7seg_frames[0])

    def play_display7seg_clear_anim(self):
        # One-shot sweep of a dash across the 8 digits, then blank — shown when
        # the last morse letter is deleted (instead of an instantly blank panel).
        frames = [
            "".join("-" if j == pos else " " for j in range(8))
            for pos in range(8)
        ]
        frames.append(" " * 8)
        self.play_display7seg_anim(frames, interval=0.06)

    def set_display7seg_number(self, value: int):
        if self.display7seg is None:
            return
        self.display7seg.set_number(value)

    def close(self):
        try:
            if self.leds is not None:
                self.leds.clear(show=True)
        except Exception:
            pass

        if self.mcp1 is not None:
            self.mcp1.close()
        if self.mcp2 is not None:
            self.mcp2.close()
        if self.display is not None:
            self.display.close()
        if self.display2 is not None:
            self.display2.close()
        if self.display7seg is not None:
            self.display7seg.close()
        if self.chain is not None:
            self.chain.close()