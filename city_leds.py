#!/usr/bin/env python3
import math
import time
import random
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
        brightness: float = 0.1,
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

        self.add_segment("encoder_color", 0, 4)
        self.add_segment("countdown", 9, 26)
        self.add_segment("radnice", 37, 41) # 1
        self.add_segment("izs", 78, 38) # 2
        self.add_segment("posta", 116, 38)
        self.add_segment("doprava", 156, 42)
        self.add_segment("elektrarna", 198, 40) # last

        # Nic není rezervované (přímý zápis do LED je volný).
        self.reserved_pixels = frozenset()

        # Odpočet (segment "countdown"): fade zelená → modrá dle zbývajícího času.
        self.countdown_fraction: Optional[float] = None

        # Městské oblasti: dokud nejsou odemčené, náhodně blikají červeně.
        self.locked_segments = {"radnice", "elektrarna", "izs", "posta", "doprava"}
        self.locked_flicker_period = 0.12   # jak často se přegeneruje vzor (s)
        self._locked_flicker_at = 0.0
        self._locked_pattern: Dict[int, bool] = {}

        # Krátký stavový problik (např. 3× červeně při špatném kódu).
        # Dočasně přepíše běžné vykreslení daného segmentu, po dokončení mizí.
        self._status_blink_segment: Optional[str] = None
        self._status_blink_color: Color = RED
        self._status_blink_remaining = 0   # počet zbývajících bliknutí
        self._status_blink_on = False
        self._status_blink_period = 0.2
        self._status_blink_toggle_at = 0.0

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

    def set_color_leds(self, color: Color, show: bool = True):
        """Barva zvolená tlačítkem button_color na segmentu 'encoder_color'."""
        self.set_segment("encoder_color", color, mode="solid")
        if show:
            self.show()

    def set_central_scan(self, active: bool, color: Color = RED, show: bool = True):
        """Ponecháno pro kompatibilitu událostí — skener nahrazen náhodným
        červeným blikáním zamčených oblastí, takže tady není co dělat."""
        return

    def set_central_bar(self, fraction: Optional[float], show: bool = True):
        """Odpočet na segmentu 'countdown': ubývající pruh, fade zelená → červená.

        fraction 1.0 = plný zelený pruh (plný čas) → 0.0 = prázdno/červená
        (konec); None = zhasnout. Počet rozsvícených LED klesá úměrně fraction.
        """
        if fraction is None:
            self.countdown_fraction = None
            self.clear_segment("countdown", show=show)
            return
        self.countdown_fraction = max(0.0, min(1.0, fraction))

    @staticmethod
    def _lerp(c1: Color, c2: Color, t: float) -> Color:
        t = max(0.0, min(1.0, t))
        return (
            int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t),
        )

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

    def blink_status(
        self,
        times: int = 3,
        color: Color = RED,
        period: float = 0.2,
        segment: str = "countdown",
    ):
        """Krátce N× problikne stavovým segmentem (výchozí 'countdown').

        Po dokončení se segment vrátí ke svému běžnému vykreslení (odpočet,
        animace, ...). Používá se např. pro 3× červené bliknutí při špatném kódu.
        """
        if segment not in self.segments:
            return
        self._status_blink_segment = segment
        self._status_blink_color = color
        self._status_blink_period = max(0.05, period)
        self._status_blink_remaining = max(1, times)
        self._status_blink_on = True
        self._status_blink_toggle_at = time.monotonic() + self._status_blink_period

    def pulse_segment(self, name: str, color: Color = CYAN, period: float = 1.2):
        self.set_segment(name, color, mode="pulse", period=period)

    # ------------------------------------------------------------
    # High-level system statuses
    # ------------------------------------------------------------
    def set_system_status(self, system_name: str, status: str, animate: bool = True):
        """Stav městské oblasti.

        'ok'/'repaired' → oblast odemčena (zelená, přestane blikat); jakýkoli
        jiný stav → oblast zůstává zamčená a náhodně červeně bliká.
        """
        if system_name not in self.segments:
            return
        if status in ("ok", "repaired"):
            self.locked_segments.discard(system_name)
            # self.set_segment(system_name, GREEN, "solid")
            self.set_segment(system_name, GREEN, "flow", period=1.5)
        else:
            self.locked_segments.add(system_name)

    # def set_encoder_letter(self, encoder_name: str, index: int, show: bool = True):
    #     """
    #     Display current encoder letter position on a 10-LED bar as a single dot.
    #     index: 0..9 where 0=A and 9=J.
    #     Exactly one LED is ON at a time.
    #     """
    #     if encoder_name == "encoder_number":
    #         segment_name = "encoder1_letters"
    #         on_color = CYAN
    #     elif encoder_name == "encoder_glyph":
    #         segment_name = "encoder2_letters"
    #         on_color = MAGENTA
    #     else:
    #         # Encoders without a dedicated LED letter bar (e.g. encoder_letter)
    #         # only drive the MAX7219 display, so there is nothing to light here.
    #         return

    #     if segment_name not in self.segments:
    #         return

    #     idx = index % 10
    #     override: List[Color] = []

    #     for offset, pixel_index in enumerate(self._segment_indices(segment_name)):
    #         color = on_color if offset == idx else BLACK
    #         self._set_pixel(pixel_index, color)
    #         override.append(color)

    #     self.segment_overrides[segment_name] = override

    #     if show:
    #         self.show()

    # ------------------------------------------------------------
    # Update animations
    # ------------------------------------------------------------
    def update(self):
        now = time.monotonic()

        for name, anim in self.animations.items():
            seg = self.segments[name]
            override = self.segment_overrides.get(name)

            # Countdown a zamčené oblasti mají vlastní vykreslení (viz níže).
            if name == "countdown" and self.countdown_fraction is not None:
                continue
            if name in self.locked_segments:
                continue
            # Stavový problik má přednost před běžným vykreslením segmentu.
            if name == self._status_blink_segment:
                continue

            if override is not None:
                for offset, i in enumerate(range(seg.start, seg.start + seg.length)):
                    self._set_pixel(i, override[offset])
                continue

            if anim.mode == "flow":
                # Jeden světelný bod putující přes segment (odemčená oblast).
                if anim.period <= 0:
                    for i in range(seg.start, seg.start + seg.length):
                        self._set_pixel(i, anim.color)
                else:
                    length = seg.length
                    phase = (now % anim.period) / anim.period
                    head = phase * length            # pozice bodu (0..length)
                    tail = 3.0                        # délka doznívajícího ohonu (v LED)
                    for offset, i in enumerate(range(seg.start, seg.start + length)):
                        # Vzdálenost pixelu za hlavou (ohon se táhne dozadu).
                        dist = (head - offset) % length
                        if dist < tail:
                            b = 1.0 - (dist / tail)
                            self._set_pixel(i, scale_color(anim.color, b))
                        else:
                            self._set_pixel(i, BLACK)
                continue


            if anim.mode == "flow_wave":
                # Plynulá zelená vlna běžící přes segment (odemčená oblast).
                if anim.period <= 0:
                    for i in range(seg.start, seg.start + seg.length):
                        self._set_pixel(i, anim.color)
                else:
                    phase = (now % anim.period) / anim.period
                    for offset, i in enumerate(range(seg.start, seg.start + seg.length)):
                        wave = 0.5 + 0.5 * math.sin(
                            2 * math.pi * (offset / max(1, seg.length) - phase)
                        )
                        b = 0.2 + 0.8 * wave
                        self._set_pixel(i, scale_color(anim.color, b))
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

        # Odpočet (segment "countdown"): ubývající pruh + fade zelená → červená.
        if self.countdown_fraction is not None:
            seg = self.segments["countdown"]
            color = self._lerp(GREEN, RED, 1.0 - self.countdown_fraction)
            lit = int(round(self.countdown_fraction * seg.length))
            for offset, i in enumerate(self._segment_indices("countdown")):
                self._set_pixel(i, color if offset < lit else BLACK)

        # Krátký stavový problik (přepíše běžné vykreslení daného segmentu).
        if self._status_blink_segment is not None:
            seg_name = self._status_blink_segment
            if now >= self._status_blink_toggle_at:
                self._status_blink_toggle_at = now + self._status_blink_period
                self._status_blink_on = not self._status_blink_on
                if not self._status_blink_on:
                    # Konec jedné ON fáze = jedno bliknutí.
                    self._status_blink_remaining -= 1
                    if self._status_blink_remaining <= 0:
                        self._status_blink_segment = None
            color = self._status_blink_color if self._status_blink_on else BLACK
            for i in self._segment_indices(seg_name):
                self._set_pixel(i, color)

        # Zamčené oblasti: náhodné červené blikání (vzor se přegeneruje periodicky).
        if now >= self._locked_flicker_at:
            self._locked_flicker_at = now + self.locked_flicker_period
            self._locked_pattern = {}
            for name in self.locked_segments:
                for i in self._segment_indices(name):
                    self._locked_pattern[i] = random.random() < 0.4
        for name in self.locked_segments:
            for i in self._segment_indices(name):
                self._set_pixel(i, RED if self._locked_pattern.get(i) else BLACK)

        self.show()
        self._last_update = now

    # ------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------
    def debug_segments(self):
        for name, seg in self.segments.items():
            print(f"{name:12s}: start={seg.start:2d}, len={seg.length}")