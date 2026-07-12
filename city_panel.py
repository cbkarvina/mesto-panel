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
    SYMBOLS,
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
        self.inputs = None
        self.leds = None
        self.chain = None
        self.display = None
        self.display2 = None
        self.display3 = None
        self.display7seg = None
        self._encoder_display_state = {
            "encoder_number": 0,
            "encoder_glyph": 0,
            "encoder_letter": 0,
        }
        # encoder_number_letter sdílí jeden fyzický enkodér pro číslici i
        # písmeno. Každý režim má vlastní uloženou pozici, aby po přepnutí
        # encoder_switch pokračoval tam, kde předtím skončil. _enc_last_raw je
        # poslední absolutní index z enginu — slouží k odvození směru otočení.
        self._enc_number_index = 0
        self._enc_letter_index = 0
        self._enc_last_raw = 0
        # When set, display1 is cleared once time.monotonic() reaches this value.
        self._display1_clear_at: Optional[float] = None
        # When set, display2 is cleared once time.monotonic() reaches this value.
        self._display2_clear_at: Optional[float] = None
        # When set, display3 is cleared once time.monotonic() reaches this value.
        self._display3_clear_at: Optional[float] = None
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
        # 7-seg "locked" indikace: bliká, dokud se panel neodemkne.
        self._locked_blink = False
        self._locked_on = False
        self._locked_toggle_at: Optional[float] = None
        self._locked_period = 0.5
        self._locked_message = "LOCKED"
        # Jednorázová animace odemčení (matice + 7-seg), non-blocking.
        self._unlock_anim_frames: Optional[list] = None
        self._unlock_anim_index = 0
        self._unlock_anim_next_at: Optional[float] = None
        self._unlock_anim_interval = 0.08
        self._event_callback: Optional[Callable[[InputEvent], None]] = None

        # ---------------------------
        # Input expanders
        # ---------------------------
        if init_inputs:
            self.mcp1 = MCP23017(address=0x20, busnum=1)
     
            self.inputs = PanelInputs(poll_interval_ms=5)
            self._setup_inputs()
            self.inputs.on_event(self._handle_input_event)

        # ---------------------------
        # LED layer
        # ---------------------------
        if init_leds:
            self.leds = CityLeds(
                led_count=250,     # includes 2x10 LEDs for encoder letter indicators
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
            #   module 0 = matrix #1 -> encoder_number (letter)
            #   module 1 = matrix #2 -> encoder_glyph (digit)
            #   module 2 = matrix #3 -> encoder_letter (symbol)
            #   module 3 = 7-segment                 -> COMMS morse
            try:
                self.chain = Max7219Chain(bus=0, device=0, num_modules=4)
            except Max7219DisplayError as exc:
                print(f"MAX7219 chain disabled: {exc}")
                self.chain = None

            if self.chain is not None:
                try:
                    self.display = Max7219Display(chain=self.chain, module_index=0, intensity=4, rotate180=True)
                    self.display.set_char("A")
                except Max7219DisplayError as exc:
                    print(f"MAX7219 display #1 disabled: {exc}")
                    self.display = None

                try:
                    self.display2 = Max7219Display(chain=self.chain, module_index=1, intensity=4, rotate180=True, rotate90=True)
                    self.display2.set_char("0")
                except Max7219DisplayError as exc:
                    print(f"MAX7219 display #2 disabled: {exc}")
                    self.display2 = None
                
                try:
                    self.display3 = Max7219Display(chain=self.chain, module_index=2, intensity=4, rotate180=True, rotate90=True)
                    self.display3.set_char("A")
                except Max7219DisplayError as exc:
                    print(f"MAX7219 display #3 disabled: {exc}")
                    self.display3 = None

                try:
                    self.display7seg = Max7219SevenSegDisplay(chain=self.chain, module_index=3, intensity=4)
                    self.display7seg.clear()
                except Max7219DisplayError as exc:
                    print(f"MAX7219 7-seg display disabled: {exc}")
                    self.display7seg = None

    # ------------------------------------------------------------------
    # INPUT SETUP
    # ------------------------------------------------------------------
    def _setup_inputs(self):
        # ===== MCP1 =====
        self.inputs.add_encoder("encoder_number_letter", self.mcp1, pin_a=0, pin_b=1)
        self.inputs.add_encoder("encoder_glyph", self.mcp1, pin_a=2, pin_b=3)
        # self.inputs.add_encoder("encoder_letter", self.mcp1, pin_a=5, pin_b=4, reverse=True)
        self.inputs.add_button("unlock_button", self.mcp1, 6)
        self.inputs.add_button("button_color", self.mcp1, 7)
        self.inputs.add_button("morse_cycle", self.mcp1, 8) # Tlačítko "morse cycle" volí, kolik z 5 přepínačů tvoří kód (1..5);
        self.inputs.add_switch("encoder_switch", self.mcp1, 9)

        # 5 přepínačů Morse (zapnuto = tečka '.', vypnuto = čárka '-').
        # Každý přepínač = jedna pozice kódu zobrazeného na 7-segmentovém panelu.
        self.inputs.add_switch("morse_pos_1", self.mcp1, 11)
        self.inputs.add_switch("morse_pos_2", self.mcp1, 12)
        self.inputs.add_switch("morse_pos_3", self.mcp1, 13)
        self.inputs.add_switch("morse_pos_4", self.mcp1, 14)
        self.inputs.add_switch("morse_pos_5", self.mcp1, 15)

    # ------------------------------------------------------------------
    # EVENT HANDLING
    # ------------------------------------------------------------------
    def _handle_input_event(self, event: InputEvent):
        # Přepnutí encoder_switch okamžitě překreslí aktivní matici na její
        # uloženou hodnotu (číslici na display2 / písmeno na display3).
        if event.name == "encoder_switch" and event.event_type == "changed":
            self.refresh_encoder_display()
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
        # Zamčený stav: 7-segmentový panel bliká "LOC", dokud se neodemkne.
        # Má přednost před morse preview / animacemi.
        if self._locked_blink and self.display7seg is not None:
            now = time.monotonic()
            if self._locked_toggle_at is not None and now >= self._locked_toggle_at:
                self._locked_on = not self._locked_on
                self._locked_toggle_at = now + self._locked_period
                if self._locked_on:
                    self.display7seg.set_text(self._locked_message)
                else:
                    self.display7seg.clear(show=True)
        # Jednorázová animace odemčení (matice + 7-seg). Má přednost, dokud běží.
        if self._unlock_anim_frames is not None:
            now = time.monotonic()
            if self._unlock_anim_next_at is not None and now >= self._unlock_anim_next_at:
                self._unlock_anim_index += 1
                if self._unlock_anim_index >= len(self._unlock_anim_frames):
                    self._unlock_anim_frames = None
                    self._unlock_anim_next_at = None
                    # Konec animace: zhasni matice, 7-seg zpět na živý náhled.
                    if self.display is not None:
                        self.display.clear(show=True)
                    if self.display2 is not None:
                        self.display2.clear(show=True)
                    if self.display3 is not None:
                        self.display3.clear(show=True)
                    if self.display7seg is not None:
                        self.display7seg.set_morse(self._last_morse_code)
                else:
                    self._unlock_anim_next_at = now + self._unlock_anim_interval
                    self._apply_unlock_frame(self._unlock_anim_index)
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
        if (
            self._display3_clear_at is not None
            and time.monotonic() >= self._display3_clear_at
        ):
            self._display3_clear_at = None
            if self.display3 is not None:
                self.display3.clear(show=True)
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
        # 5 městských oblastí (core/power/rescue/comms/transport) náhodně
        # červeně bliká, dokud se neodemknou — výchozí stav CityLeds.locked_segments,
        # takže stačí nechat běžet update().
        self.leds.update()

    def set_system_status(self, system_name: str, status: str, animate: bool = True):
        if self.leds is None:
            raise RuntimeError("Panel LEDs are not initialized")
        self.leds.set_system_status(system_name, status, animate=animate)

    # def set_encoder_letter(self, encoder_name: str, index: int, show: bool = True):
    #     if self.leds is None:
    #         raise RuntimeError("Panel LEDs are not initialized")
    #     self.leds.set_encoder_letter(encoder_name, index, show=show)

    def flash_alarm(self, system_name: str):
        if self.leds is None or system_name not in self.leds.segments:
            return
        self.leds.flash_alarm(system_name)

    def blink_status(self, times: int = 3, color=(255, 0, 0), period: float = 0.2):
        """Krátce N× problikne stavovým segmentem (výchozí 'countdown')."""
        if self.leds is None:
            return
        self.leds.blink_status(times=times, color=color, period=period)

    def set_indicator(self, name: str, color, mode: str = "solid"):
        if self.leds is None or name not in self.leds.segments:
            return
        self.leds.set_segment(name, color, mode=mode)

    # ------------------------------------------------------------------
    # DISPLAY HELPERS
    # ------------------------------------------------------------------
    def set_display_glyph(self, index: int):
        if self.display is None:
            return
        self.display.set_glyph_by_index(index)

    def set_display2_number(self, index: int):
        """Číslice 0-9 na druhé matici (display2)."""
        if self.display2 is None:
            return
        self.display2.set_char(str(index % 10))

    def set_display3_letter(self, index: int):
        """Písmeno A-J na třetí matici (display3)."""
        if self.display3 is None:
            return
        self.display3.set_index_letter(index)

    def set_encoder_display(self, encoder_name: str, index: int):
        # encoder_number_letter sdílí jeden enkodér pro číslice i písmena;
        # přepínač encoder_switch volí, kam se hodnota zobrazí:
        #   sepnuto (ON)    -> číslice 0-9 na display2,
        #   rozepnuto (OFF) -> písmeno A-J na display3.
        # Každý režim má vlastní pozici; z absolutního indexu enginu odvodíme
        # jen směr otočení (±1) a aplikujeme ho na aktivní režim, aby ten
        # druhý zůstal beze změny.
        if encoder_name == "encoder_number_letter":
            delta = (index - self._enc_last_raw) % 10
            if delta > 5:
                delta -= 10
            self._enc_last_raw = index
            if self.read_encoder_switches():
                self._enc_number_index = (self._enc_number_index + delta) % 10
            else:
                self._enc_letter_index = (self._enc_letter_index + delta) % 10
            self.refresh_encoder_display()
        elif encoder_name == "encoder_glyph":
            self.set_display_glyph(index)

    def refresh_encoder_display(self):
        """Zobrazí uloženou hodnotu aktivního režimu encoder_number_letter.

        Podle polohy encoder_switch vykreslí buď číslici na display2, nebo
        písmeno na display3 — bez změny druhého režimu.
        """
        if self.read_encoder_switches():
            self.set_display2_number(self._enc_number_index)
        else:
            self.set_display3_letter(self._enc_letter_index)

    def set_display7seg_text(self, text: str):
        if self.display7seg is None:
            return
        self.display7seg.set_text(text)

    def set_display7seg_locked(self, locked: bool, message: Optional[str] = None):
        """Zapne/vypne blikající 'locked' indikaci na 7-segmentovém panelu."""
        if message is not None:
            self._locked_message = message
        self._locked_blink = locked
        if not locked:
            # Odemčeno: ukonči blikání a vrať se k živému morse náhledu.
            self._locked_on = False
            self._locked_toggle_at = None
            if self.display7seg is not None:
                self.display7seg.set_morse(self._last_morse_code)
            return
        # Zamčeno: zruš ostatní 7-seg stavy a začni blikat.
        self._display7seg_revert_at = None
        self._blink_deadline = None
        self._blink_toggle_at = None
        self._anim7seg_frames = None
        self._anim7seg_next_at = None
        self._locked_on = True
        self._locked_toggle_at = time.monotonic() + self._locked_period
        if self.display7seg is not None:
            self.display7seg.set_text(self._locked_message)

    # def play_unlock_anim(self):
    #     """Jednorázová oslavná animace odemčení na obou maticích i 7-seg panelu."""
    #     # Ukonči případné blikání zámku — panel je odemčen.
    #     self._locked_blink = False
    #     self._locked_toggle_at = None
    #     # Zruš ostatní 7-seg stavy, aby animace měla displej pro sebe.
    #     self._display7seg_revert_at = None
    #     self._blink_deadline = None
    #     self._blink_toggle_at = None
    #     self._anim7seg_frames = None
    #     self._anim7seg_next_at = None

    #     frames = []
    #     # Fáze 1: matice se plní shora dolů, po 7-seg přejíždí pomlčka.
    #     for i in range(8):
    #         rows = [0xFF if r <= i else 0x00 for r in range(8)]
    #         seg = "".join("-" if j == i else " " for j in range(8))
    #         frames.append((rows, seg))
    #     # Fáze 2: bliknutí, pak úsměv na maticích a "OPEN" na 7-seg.
    #     smiley = list(SYMBOLS[1])
    #     frames.append(([0xFF] * 8, "  OPEN  "))
    #     frames.append((smiley, "  OPEN  "))
    #     frames.append((smiley, "  OPEN  "))

    #     self._unlock_anim_frames = frames
    #     self._unlock_anim_index = 0
    #     self._unlock_anim_next_at = time.monotonic() + self._unlock_anim_interval
    #     self._apply_unlock_frame(0)

    def _apply_unlock_frame(self, index: int):
        rows, seg = self._unlock_anim_frames[index]
        if rows is not None:
            if self.display is not None:
                self.display.set_rows(rows)
            if self.display2 is not None:
                self.display2.set_rows(rows)
            if self.display3 is not None:
                self.display3.set_rows(rows)
        if seg is not None and self.display7seg is not None:
            self.display7seg.set_text(seg)

    def set_display7seg_morse(self, code: str):
        # Live preview of the morse selected by the 5 element switches. Held
        # back while a submitted word is being shown for its 2s window, or
        # while an error code is blinking.
        self._last_morse_code = code
        if (
            self._display7seg_revert_at is not None
            or self._blink_deadline is not None
            or self._anim7seg_frames is not None
            or self._unlock_anim_frames is not None
            or self._locked_blink
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

    # ------------------------------------------------------------------
    # BOOT / INITIAL STATE
    # ------------------------------------------------------------------
    def read_morse_switches(self) -> dict:
        """Vrátí aktuální stav 5 morse přepínačů: {'morse_pos_1': bool, ...}.

        bool = je přepínač aktivní (sepnutý). Přepínač ON = tečka '.'.
        """
        states = {}
        for i in range(1, 6):
            name = f"morse_pos_{i}"
            if self.inputs is not None and name in self.inputs.inputs:
                states[name] = self.inputs.is_active(name)
            else:
                states[name] = False
        return states

    def read_encoder_switches(self) -> bool:
        """Vrátí aktuální stav encoder přepínače: bool.

        bool = je přepínač aktivní (sepnutý).
        """
        if self.inputs is not None and "encoder_switch" in self.inputs.inputs:
            return self.inputs.is_active("encoder_switch")
        return False

    def read_morse_code(self) -> str:
        """Sestaví morse řetězec z 5 přepínačů (ON = '.', OFF = '-')."""
        states = self.read_morse_switches()
        return "".join(
            "." if states[f"morse_pos_{i}"] else "-" for i in range(1, 6)
        )

    def show_initial_state(self):
        """Při startu zobrazí výchozí hodnoty enkodérů do matic a morse na 7-seg.

        encoder_number_letter se dle polohy encoder_switch zobrazí buď jako
        číslice na display2, nebo jako písmeno na display3; encoder_glyph ukazuje
        svůj symbol na první matici a morse podle 5 přepínačů na 7-segmentovce.
        """
        self.set_encoder_display("encoder_number_letter", 0)
        self.set_encoder_display("encoder_glyph", 0)
        self.set_display7seg_morse(self.read_morse_code())

    def close(self):
        try:
            if self.leds is not None:
                self.leds.clear(show=True)
        except Exception:
            pass

        if self.mcp1 is not None:
            self.mcp1.close() 
        if self.display is not None:
            self.display.close()
        if self.display2 is not None:
            self.display2.close()
        if self.display3 is not None:
            self.display3.close()
        if self.display7seg is not None:
            self.display7seg.close()
        if self.chain is not None:
            self.chain.close()