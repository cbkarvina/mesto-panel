#!/usr/bin/env python3
import time
from dataclasses import dataclass, field
from typing import List


@dataclass
class EngineEvent:
    type: str
    payload: dict = field(default_factory=dict)

# Názvy symbolů v pořadí SYMBOLS z max7219_display.py (index = pozice enkodéru).
SYMBOL_NAMES = [
    "heart", "smiley", "star", "lightning",
    "arrow_up","arrow_down", "key", "eye", "hourglass", "music",
]

UNITS = {
    "posta": {
        "locked": True,
        "unlockable": True,
        "day": 0,
        "code": {
            "morse": "M",
            "color": "red",
            "number": 1,
            "letter": "A",
            "glyph": SYMBOL_NAMES[0]
        }
    },
    "izs": {
        "locked": True,
        "unlockable": False,
        "day": 1,
        "code": {
            "morse": "F",
            "color": "green",
            "number": 9,
            "letter": "F",
            "glyph": SYMBOL_NAMES[2]
        }
    },
    "elektrarna": {
        "locked": True,
        "unlockable": False,
        "day": 2,
        "code": {
            "morse": "F",
            "color": "yellow",
            "number": 9,
            "letter": "F",
            "glyph": SYMBOL_NAMES[4]
        }
    },
    "doprava": {
        "locked": True,
        "unlockable": False,
        "day": 3,
        "code": {
            "morse": "F",
            "color": "yellow",
            "number": 9,
            "letter": "F",
            "glyph": SYMBOL_NAMES[6]
        }
    },
    "radnice": {
        "locked": True,
        "unlockable": False,
        "day": 4,
        "code": {
            "morse": "F",
            "color": "yellow",
            "number": 9,
            "letter": "F",
            "glyph": SYMBOL_NAMES[8]
        }
    },
}



# Mezinárodní Morseova abeceda pro modul KOMUNIKACE (mimo rozsah dekodéru A–J).
MORSE_ALPHABET = {
    "A": ".-",   "B": "-...", "C": "-.-.", "D": "-..",  "E": ".",
    "F": "..-.", "G": "--.",  "H": "....", "I": "..",   "J": ".---",
    "K": "-.-",  "L": ".-..", "M": "--",   "N": "-.",   "O": "---",
    "P": ".--.", "Q": "--.-", "R": ".-.",  "S": "...",  "T": "-",
    "U": "..-",  "V": "...-", "W": ".--",  "X": "-..-", "Y": "-.--",
    "Z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
}
MORSE_TO_LETTER = {code: ch for ch, code in MORSE_ALPHABET.items()}

# Písmena kombinačních enkodérů (index 0-9 → A-J).
ENCODER_LETTERS = "ABCDEFGHIJ"

# Pořadí odemykání oblastí — jeden pracovní den = jedna oblast.
# Pondělí→pošta, úterý→IZS, středa→elektrárna, čtvrtek→doprava, pátek→radnice.
DAY_ORDER = ["posta", "izs", "elektrarna", "doprava", "radnice"]

# Mapování oblasti na LED segment města (rozsvítí se po odemčení).
AREA_SEGMENT = {
    "posta": "comms",
    "izs": "rescue",
    "elektrarna": "power",
    "doprava": "transport",
    "radnice": "core",
}
 

# Barvy volené tlačítkem button_color (index 0-9 → A-J dle městského dekodéru).
COLORS_EN = ["red", "yellow", "green", "cyan", "blue", 
             "magenta", "white", "black"]
COLOR_RGB = {
    "red": (255, 0, 0),
    "yellow": (255, 255, 0),
    "green": (0, 255, 0),
    "cyan": (0, 255, 255),
    "blue": (0, 0, 255),
    "magenta": (255, 0, 255),
    "white": (255, 255, 255),
    "black": (10, 10, 10),
}

# Globální odpočet po startu systému. Po jeho vypršení panel přestane reagovat.
COUNTDOWN_DURATION = 5 * 60.0     # 5 minut (s)
COUNTDOWN_BAR_EMIT_INTERVAL = 0.5  # jak často se posílá stav pruhu (s)

# Chybové hlášení při neplatném řídicím kódu.
ERROR_INVALID_CODE = "Neplatný řídicí kód."

class GameEngine:
    """Herní logika 'Tajemného města'.

    Model: každý pracovní den lze odemknout jednu městskou oblast (začíná se
    poštou). Hráč nastaví na panelu denní kód — tři enkodéry (písmeno / číslice
    / symbol), barvu (tlačítko) a Morse (5 přepínačů) — a potvrdí tlačítkem
    unlock_button. Po startu systému běží globální 30minutový odpočet; po jeho
    vypršení panel přestane reagovat (self.dead) až do restartu.
    """

    def __init__(self):
        self.pending_events: List[EngineEvent] = []
        self._finale_done = False

        # Odemčené oblasti města (v pořadí DAY_ORDER).
        self.unlocked_areas: List[str] = []

        # Modul KOMUNIKACE — Morse: 5 přepínačů (True = ON = tečka '.',
        # False = OFF = čárka '-'). Morse číslice mají 5 znaků → 5 přepínačů.
        # Tlačítko morse_cycle volí, kolik přepínačů (1..5) tvoří kód;
        # zbylé se ignorují. Kód se zobrazuje na 7-segmentovém panelu a je
        # součástí denního odemykacího kódu.
        self.morse_symbols = [False, False, False, False, False]
        self.morse_length = 5

        # Tři kombinační enkodéry (index 0-9).
        self.encoder_letters = list("ABCDEFGHIJ")
        self.encoder_positions = {
            "encoder_number": 0,   # písmeno A-J
            "encoder_glyph": 0,    # číslice 0-9
            "encoder_letter": 0,   # symbol
        }

        # Barva volená tlačítkem button_color (index do COLORS_EN).
        self.color_index = 0

        # Globální 30minutový odpočet — startuje se startem systému.
        # Po vypršení self.dead = True a panel přestane reagovat.
        self.dead = False
        self.countdown_active = False
        self.countdown_duration = COUNTDOWN_DURATION
        self.countdown_deadline = 0.0
        self._countdown_last_emit = 0.0

        # Počáteční zobrazení enkodérů na jejich maticích.
        for name in ("encoder_number", "encoder_glyph", "encoder_letter"):
            self.pending_events.append(EngineEvent(
                "encoder_letter", {"encoder": name, "index": 0}
            ))

        # Spusť globální odpočet hned při vytvoření enginu (start systému).
        self.start_countdown()

    # ------------------------------------------------------------------
    # Odpočet
    # ------------------------------------------------------------------
    def start_countdown(self):
        """Spustí globální 30minutový odpočet po startu systému."""
        now = time.monotonic()
        self.dead = False
        self.countdown_active = True
        self.countdown_deadline = now + self.countdown_duration
        self._countdown_last_emit = 0.0
        self.pending_events.append(EngineEvent("central_bar", {"fraction": 1.0}))
        self.pending_events.append(EngineEvent(
            "message", {"text": "Systém spuštěn. Zbývá 30 minut."}
        ))

    def sync_initial_state(self, switch_states=None):
        """Načte počáteční stav 5 morse přepínačů do vnitřního stavu enginu.

        Volá se jednou při startu (po inicializaci panelu). Zobrazení do panelů
        obstará CityPanel.show_initial_state(); zde jen srovnáme vnitřní stav
        morse s fyzickými přepínači.
        """
        if switch_states:
            for i in range(len(self.morse_symbols)):
                self.morse_symbols[i] = bool(
                    switch_states.get(f"morse_pos_{i + 1}", False)
                )
        # Zobraz výchozí barvu na prvních 5 LED (indikátor button_color).
        color = self.current_color()
        self.pending_events.append(EngineEvent(
            "color_select", {"color": color, "rgb": COLOR_RGB[color]}
        ))

    # ------------------------------------------------------------------
    # Zpracování vstupů
    # ------------------------------------------------------------------
    def handle_panel_event(self, name: str, event_type: str, is_active: bool):
        # Po vypršení odpočtu systém přestane reagovat na jakýkoli vstup.
        if self.dead:
            return

        if name in self.encoder_positions and event_type in ("rotated_cw", "rotated_ccw"):
            self._rotate_encoder(name, event_type)

        elif name == "button_color" and event_type == "pressed":
            self._cycle_color()

        elif name == "morse_cycle" and event_type == "pressed":
            self._cycle_morse_length()

        elif name.startswith("morse_pos_") and event_type == "changed":
            idx = int(name.rsplit("_", 1)[1]) - 1
            if 0 <= idx < len(self.morse_symbols):
                self.morse_symbols[idx] = is_active
                self._emit_morse_preview()

        elif name == "unlock_button" and event_type == "pressed":
            self._try_unlock()

    def tick(self):
        if not self.countdown_active or self.dead:
            return
        now = time.monotonic()
        remaining = self.countdown_deadline - now
        if remaining <= 0:
            self._on_countdown_expire()
            return
        if now - self._countdown_last_emit >= COUNTDOWN_BAR_EMIT_INTERVAL:
            self._countdown_last_emit = now
            self.pending_events.append(EngineEvent(
                "central_bar",
                {"fraction": remaining / self.countdown_duration}
            ))

    def _on_countdown_expire(self):
        """Vypršení odpočtu — systém přestane reagovat (do restartu)."""
        self.countdown_active = False
        self.dead = True
        self.pending_events.append(EngineEvent("central_bar", {"fraction": None}))
        self.pending_events.append(EngineEvent("central_scan", {"active": False}))
        self.pending_events.append(EngineEvent(
            "message", {"text": "Čas vypršel! Systém přestal reagovat."}
        ))
        self.pending_events.append(EngineEvent("sound", {"clip": "error"}))
        self.pending_events.append(EngineEvent("animation", {"kind": "error"}))
        self.pending_events.append(EngineEvent("dead", {"message": "DEAD"}))

    def pop_events(self):
        events = self.pending_events[:]
        self.pending_events.clear()
        return events

    # ------------------------------------------------------------------
    # Enkodéry + barva
    # ------------------------------------------------------------------
    def _encoder_letter(self, encoder_name: str) -> str:
        idx = self.encoder_positions[encoder_name]
        return self.encoder_letters[idx]

    def _rotate_encoder(self, encoder_name: str, event_type: str):
        step = 1 if event_type == "rotated_cw" else -1
        count = len(self.encoder_letters)
        self.encoder_positions[encoder_name] = (
            self.encoder_positions[encoder_name] + step
        ) % count
        self.pending_events.append(EngineEvent(
            "encoder_letter",
            {"encoder": encoder_name, "index": self.encoder_positions[encoder_name]}
        ))

    def _cycle_color(self):
        self.color_index = (self.color_index + 1) % len(COLORS_EN)
        color = self.current_color()
        self.pending_events.append(EngineEvent(
            "color_select", {"color": color, "rgb": COLOR_RGB[color]}
        ))
        self.pending_events.append(EngineEvent(
            "message", {"text": f"Barva: {color}"}
        ))

    def current_color(self) -> str:
        return COLORS_EN[self.color_index]

    # ------------------------------------------------------------------
    # Denní odemykání oblastí
    # ------------------------------------------------------------------
    def _current_target(self):
        """Vrátí klíč oblasti, která je právě na řadě (první neodemčená
        v pořadí DAY_ORDER), nebo None když jsou všechny odemčené."""
        for key in DAY_ORDER:
            if key not in self.unlocked_areas:
                return key
        return None

    def _morse_matches(self, letter: str) -> bool:
        """Porovná zadaný Morse s cílovým písmenem/číslicí.

        Použije se právě tolik přepínačů, kolik je nastaveno tlačítkem
        morse_cycle (self.morse_length); zbylé přepínače se ignorují. Kód
        musí přesně odpovídat morse cíle.
        """
        target = MORSE_ALPHABET.get(str(letter).upper(), "")
        if not target:
            return False
        return self._current_morse() == target

    def _try_unlock(self):
        target = self._current_target()
        if target is None:
            self.pending_events.append(EngineEvent(
                "message", {"text": "Všechny oblasti jsou již odemčené."}
            ))
            return

        code = UNITS[target]["code"]
        checks = {
            "letter": self.encoder_positions["encoder_number"]
                      == ENCODER_LETTERS.index(str(code["letter"]).upper()),
            "number": self.encoder_positions["encoder_glyph"]
                      == int(code["number"]) % 10,
            "glyph": self.encoder_positions["encoder_letter"]
                     == SYMBOL_NAMES.index(str(code["glyph"]).lower()),
            "color": self.current_color() == str(code["color"]).lower(),
            "morse": self._morse_matches(code["morse"]),
        }

        if all(checks.values()):
            self._unlock_area(target)
        else:
            wrong = [k for k, ok in checks.items() if not ok]
            self.pending_events.append(EngineEvent(
                "message", {"text": ERROR_INVALID_CODE}
            ))
            self.pending_events.append(EngineEvent(
                "message", {"text": f"Nesouhlasí: {', '.join(wrong)}"}
            ))
            self.pending_events.append(EngineEvent("sound", {"clip": "error"}))
            self.pending_events.append(EngineEvent("animation", {"kind": "error"}))

    def _unlock_area(self, key: str):
        self.unlocked_areas.append(key)
        segment = AREA_SEGMENT.get(key) 

        self.pending_events.append(EngineEvent(
            "message",
            {"text": f"Přístup ověřen. Oblast {key} odemčena."}
        ))
        if segment:
            self.pending_events.append(EngineEvent(
                "system_status", {"system": segment, "status": "ok"}
            ))
            self.pending_events.append(EngineEvent(
                "map_reveal",
                {"system": segment, "location": key, "day": UNITS[key]["day"]}
            ))
        self.pending_events.append(EngineEvent("sound", {"clip": "success"}))
        self.pending_events.append(EngineEvent(
            "animation", {"kind": "success", "system": segment}
        ))
        self.pending_events.append(EngineEvent("display_anim", {"kind": "unlock"}))
        self._check_finale()

    def _check_finale(self):
        """Finále — spustí se po odemčení všech pěti oblastí."""
        if self._finale_done:
            return
        if not all(k in self.unlocked_areas for k in DAY_ORDER):
            return
        self._finale_done = True
        self.pending_events.append(EngineEvent("sound", {"clip": "finale"}))
        self.pending_events.append(EngineEvent("animation", {"kind": "finale"}))

    # ------------------------------------------------------------------
    # Morse náhled
    # ------------------------------------------------------------------
    def _current_morse(self) -> str:
        """Sestaví Morse kód z prvních morse_length přepínačů
        (True → '.', False → '-'); zbylé přepínače se ignorují."""
        n = max(1, min(len(self.morse_symbols), self.morse_length))
        return "".join("." if self.morse_symbols[i] else "-" for i in range(n))

    def _emit_morse_preview(self):
        """Zobrazí na 7-segmentovém panelu živý Morse podle přepínačů."""
        self.pending_events.append(EngineEvent(
            "display7seg", {"morse": self._current_morse()}
        ))

    def _cycle_morse_length(self):
        """Tlačítko morse_cycle: cyklicky mění počet použitých přepínačů 1..5."""
        self.morse_length = self.morse_length % len(self.morse_symbols) + 1
        self.pending_events.append(EngineEvent(
            "message", {"text": f"Morse délka: {self.morse_length}"}
        ))
        self._emit_morse_preview()

    # ------------------------------------------------------------------
    # Stav pro REST API
    # ------------------------------------------------------------------
    def countdown_remaining(self) -> float:
        if not self.countdown_active:
            return 0.0
        return max(0.0, self.countdown_deadline - time.monotonic())

    def status(self) -> dict:
        return {
            "active_area": self._current_target(),
            "unlocked_areas": list(self.unlocked_areas),
            "areas": {
                key: {
                    "day": UNITS[key]["day"],
                    "unlocked": key in self.unlocked_areas,
                }
                for key in DAY_ORDER
            },
            "encoders": dict(self.encoder_positions),
            "color": self.current_color(),
            "morse": self._current_morse(),
            "morse_length": self.morse_length,
            "countdown": {
                "active": self.countdown_active,
                "remaining": self.countdown_remaining(),
                "dead": self.dead,
            },
        }
