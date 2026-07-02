#!/usr/bin/env python3
from dataclasses import dataclass, field
from typing import List


@dataclass
class EngineEvent:
    type: str
    payload: dict = field(default_factory=dict)


# ----------------------------------------------------------------------
# Finální hra dne — získání fragmentu Kódu města
# ----------------------------------------------------------------------
# Každý systém má svůj fragment, den v týdnu, místo na mapě a hlášení.
#
# POZOR: heslo (LOCKED["word"]) NESMÍ obsahovat písmeno "M" — 7-segmentový
# displej ho neumí zobrazit, takže by ho hráč na panelu nepřečetl.
LOCKED = {
    "ledMessage": "LOCKED",
    "word": ["heart", "1", "A"],
}
MISSIONS = {
    "power": {
        "day": "wednesday",
        "map": "ELEKTRÁRNA",
        "fragment": "POWER-1",
        "success": "Přístup ověřen. Fragment energetického systému uložen. "
                   "Dodávka energie byla obnovena.",
    },
    "comms": {
        "day": "monday",
        "ledMessage": "POSTA OK",
        "map": "POŠTA",
        "fragment": "COMMS-1",
        "word": "LANO",
        "success": "Přístup ověřen. Komunikační síť je opět online. Fragment kódu uložen.",
    },
    "transport": {
        "day": "thursday",
        "map": "DOPRAVNÍ CENTRUM A CESTY",
        "fragment": "TRANSPORT-1",
        "success": "Přístup ověřen. Dopravní systém synchronizován. Fragment kódu získán.",
    },
    "rescue": {
        "day": "tuesday",
        "map": "ZÁCHRANNÉ CENTRUM",
        "fragment": "RESCUE-1",
        "success": "Přístup ověřen. Nouzové komunikační kanály byly obnoveny. "
                   "Fragment kódu uložen.",
    },
    "core": {
        "day": "friday",
        "map": "RADNICE A ZBYTEK MĚSTA",
        "fragment": "CORE-1",
        "success": "Přístup ověřen. Poslední fragment přijat. "
                   "Centrální systém je připraven k aktivaci.",
    },
}

# Pořadí dnů v týdnu (pro plánování / přehled).
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]

ERROR_MESSAGES = {
    "denied": "Ověření selhalo. Přístup zamítnut.",
    "invalid_code": "Neplatný řídící kód. Zkontrolujte nastavení panelu.",
    "sync": "Synchronizace systému nebyla dokončena.",
    "protocol": "Bezpečnostní protokol je stále aktivní. Opakujte postup.",
}

FINALE_MESSAGES = [
    "Bylo nalezeno všech pět fragmentů Kódu města.",
    "Probíhá rekonstrukce hlavního řídícího klíče.",
    "Rekonstrukce dokončena.",
    "Centrální řídící systém obnoven.",
    "Vítejte, agenti. Tajemné město je opět v bezpečí.",
]

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

# Názvy symbolů v pořadí SYMBOLS z max7219_display.py (index = pozice enkodéru).
SYMBOL_NAMES = [
    "heart", "smiley", "star", "skull", "lightning",
    "arrow_up", "key", "eye", "hourglass", "music",
]


def _lock_targets_from_word(word):
    """Z hesla LOCKED['word'] odvodí cílové pozice (index 0-9) enkodérů
    podle typu tokenu: číslice→lock_encoder_2, písmeno→lock_encoder_1,
    název symbolu→lock_encoder_3."""
    targets = {}
    for token in word:
        t = str(token)
        if t.isdigit():
            targets["lock_encoder_2"] = int(t) % 10
        elif len(t) == 1 and t.upper() in ENCODER_LETTERS:
            targets["lock_encoder_1"] = ENCODER_LETTERS.index(t.upper())
        elif t.lower() in SYMBOL_NAMES:
            targets["lock_encoder_3"] = SYMBOL_NAMES.index(t.lower())
    return targets


# Výchozí heslo zámku odvozené ze struktury LOCKED — hráč musí nastavit
# tři enkodéry (písmeno / číslice / symbol) a potvrdit tlačítkem core_activate.
LOCK_TARGETS = _lock_targets_from_word(LOCKED["word"])


class GameEngine:
    def __init__(self):
        self.systems = {
            "power": "failure",
            "transport": "offline",
            "comms": "offline",
            "rescue": "warning",
            "core": "locked",
        }

        self.power_required = 50
        self.power_sources = {
            "hydro": False,
            "solar": False,
            "diesel": False,
            "grid": False,
        }

        self.power_values = {
            "hydro": 30,
            "solar": 20,
            "diesel": 40,
            "grid": 10,
        }

        self.fragments_found: List[str] = []
        self.pending_events: List[EngineEvent] = []
        self._finale_done = False

        # Modul KOMUNIKACE — Morse vysílač
        # 4 přepínače prvků (False=tečka, True=čárka) + 4 přepínače masky
        # (které pozice se při stisku Přidat použijí).
        self.morse_element = [False, False, False, False]
        self.morse_active = [False, False, False, False]
        self.morse_word = ""

        self.encoder_letters = list("ABCDEFGHIJ")
        self.encoder_positions = {
            "lock_encoder_1": 0,
            "lock_encoder_2": 0,
            "lock_encoder_3": 0,
        }

        # Panel startuje v zamčeném stavu — dokud se nezadá správná kombinace
        # a nepotvrdí tlačítkem core_activate, systém nereaguje na ostatní vstupy.
        self.locked = True

        self.pending_events.append(EngineEvent(
            "encoder_letter",
            {"encoder": "lock_encoder_1", "index": 0}
        ))
        self.pending_events.append(EngineEvent(
            "encoder_letter",
            {"encoder": "lock_encoder_2", "index": 0}
        ))
        self.pending_events.append(EngineEvent(
            "encoder_letter",
            {"encoder": "lock_encoder_3", "index": 0}
        ))
        # Rozblikej "locked" indikaci na 7-segmentovém panelu.
        self.pending_events.append(EngineEvent(
            "locked", {"locked": True, "message": LOCKED["ledMessage"]}
        ))

    def handle_panel_event(self, name: str, event_type: str, is_active: bool):
        # V zamčeném stavu systém reaguje jen na kombinační enkodéry a na
        # potvrzovací tlačítko core_activate. Ostatní vstupy se ignorují.
        if self.locked:
            if name.startswith("lock_encoder_") and event_type in ("rotated_cw", "rotated_ccw"):
                self._rotate_encoder(name, event_type)
            elif name == "core_activate" and event_type == "pressed":
                self._try_unlock()
            return

        power_changed = False

        if name == "power_hydro" and event_type == "changed":
            self.power_sources["hydro"] = is_active
            power_changed = True

        elif name == "power_solar" and event_type == "changed":
            self.power_sources["solar"] = is_active
            power_changed = True

        elif name == "power_diesel" and event_type == "changed":
            self.power_sources["diesel"] = is_active
            power_changed = True

        elif name == "power_grid" and event_type == "changed":
            self.power_sources["grid"] = is_active
            power_changed = True

        elif name == "power_stabilize" and event_type == "pressed":
            self._stabilize_power()

        elif name == "lock_encoder_1" and event_type in ("rotated_cw", "rotated_ccw"):
            self._rotate_encoder("lock_encoder_1", event_type)

        elif name == "lock_encoder_2" and event_type in ("rotated_cw", "rotated_ccw"):
            self._rotate_encoder("lock_encoder_2", event_type)

        elif name == "lock_encoder_3" and event_type in ("rotated_cw", "rotated_ccw"):
            self._rotate_encoder("lock_encoder_3", event_type)

        elif name in ("fire", "medical", "police") and event_type == "pressed":
            self._handle_rescue_button(name)

        elif name.startswith("morse_el_") and event_type == "changed":
            self.morse_element[int(name[-1]) - 1] = is_active
            self._emit_morse_preview()

        elif name.startswith("morse_act_") and event_type == "changed":
            self.morse_active[int(name[-1]) - 1] = is_active
            self._emit_morse_preview()

        elif name == "morse_add" and event_type == "pressed":
            self._morse_add_letter()

        elif name == "morse_del" and event_type == "pressed":
            self._morse_delete()

        elif name == "morse_send" and event_type == "pressed":
            self._morse_send()

        elif name == "core_activate" and event_type == "pressed":
            self._activate_core()

        if power_changed:
            self.pending_events.append(EngineEvent(
                "power_level",
                {"percent": self._current_power()}
            ))

    def tick(self):
        pass

    def pop_events(self):
        events = self.pending_events[:]
        self.pending_events.clear()
        return events

    def _stabilize_power(self):
        total = self._current_power()

        # update visible bar always
        self.pending_events.append(EngineEvent(
            "power_level",
            {"percent": total}
        ))

        if total >= self.power_required:
            self._complete_mission("power")
        else:
            self.systems["power"] = "failure"
            self.pending_events.append(EngineEvent(
                "system_status",
                {"system": "power", "status": "failure"}
            ))
            self._fail_mission(
                "sync",
                detail=f"Insufficient power: {total}% / need {self.power_required}%",
            )

    def _current_power(self) -> int:
        total = 0
        for source, enabled in self.power_sources.items():
            if enabled:
                total += self.power_values[source]
        return total

    def _handle_rescue_button(self, name: str):
        if name == "fire":
            self._complete_mission("rescue")
        elif name == "medical":
            self._handle_medical_call()
        else:
            self.pending_events.append(EngineEvent(
                "message",
                {"text": f"{name} button pressed"}
            ))

    def _encoder_letter(self, encoder_name: str) -> str:
        idx = self.encoder_positions[encoder_name]
        return self.encoder_letters[idx]

    def _rotate_encoder(self, encoder_name: str, event_type: str):
        step = 1 if event_type == "rotated_cw" else -1
        letter_count = len(self.encoder_letters)
        self.encoder_positions[encoder_name] = (
            self.encoder_positions[encoder_name] + step
        ) % letter_count

        self.pending_events.append(EngineEvent(
            "encoder_letter",
            {"encoder": encoder_name, "index": self.encoder_positions[encoder_name]}
        ))

        l1 = self._encoder_letter("lock_encoder_1")
        d2 = self.encoder_positions["lock_encoder_2"] % 10
        l3 = self._encoder_letter("lock_encoder_3")
        self.pending_events.append(EngineEvent(
            "message",
            {"text": f"Lock code: [{l1}] [{d2}] [{l3}]"}
        ))

    def _handle_medical_call(self):
        l1 = self._encoder_letter("lock_encoder_1")
        l2 = self._encoder_letter("lock_encoder_2")

        if l1 == l2:
            self._complete_mission("rescue")
        else:
            self.pending_events.append(EngineEvent(
                "message",
                {"text": f"Medic call blocked. Set both encoders to same letter (A-J). Current: {l1}/{l2}"}
            ))

    def _activate_core(self):
        required = {"POWER-1", "COMMS-1", "TRANSPORT-1", "RESCUE-1"}
        if required.issubset(set(self.fragments_found)):
            self._complete_mission("core")
        else:
            self._fail_mission(
                "protocol",
                detail="Core locked - missing code fragments",
            )

    def _try_unlock(self):
        """Ověří pozice enkodérů proti heslu LOCKED['word']."""
        unlocked = all(
            self.encoder_positions.get(name) == target
            for name, target in LOCK_TARGETS.items()
        )
        password = " ".join(str(t) for t in LOCKED["word"])
        if unlocked:
            self.locked = False
            self.pending_events.append(EngineEvent(
                "message",
                {"text": f"Panel odemčen! Heslo: {password}"}
            ))
            self.pending_events.append(EngineEvent("locked", {"locked": False}))
            # Jednorázová animace odemčení na displejích.
            self.pending_events.append(EngineEvent("display_anim", {"kind": "unlock"}))
            self.pending_events.append(EngineEvent("sound", {"clip": "success"}))
            self.pending_events.append(EngineEvent(
                "animation", {"kind": "success", "system": "core"}
            ))
        else:
            self.pending_events.append(EngineEvent(
                "message",
                {"text": "Špatné heslo — panel zůstává zamčen."}
            ))
            self.pending_events.append(EngineEvent("sound", {"clip": "error"}))
            self.pending_events.append(EngineEvent("animation", {"kind": "error"}))

    # ------------------------------------------------------------------
    # Finální mise / fragmenty / efekty
    # ------------------------------------------------------------------
    def _complete_mission(self, system: str):
        """Úspěšné dokončení závěrečné mise dne pro daný systém."""
        mission = MISSIONS[system]
        self.systems[system] = "ok"
        self.pending_events.append(EngineEvent(
            "system_status",
            {"system": system, "status": "ok"}
        ))
        self.pending_events.append(EngineEvent(
            "message",
            {"text": mission["success"]}
        ))
        self.pending_events.append(EngineEvent("sound", {"clip": "success"}))
        self.pending_events.append(EngineEvent(
            "animation",
            {"kind": "success", "system": system}
        ))
        # Rozsvícení místa na mapě města pro daný den.
        self.pending_events.append(EngineEvent(
            "map_reveal",
            {"system": system, "location": mission["map"], "day": mission["day"]}
        ))
        self._unlock_fragment(mission["fragment"])
        self._check_finale()

    def _fail_mission(self, reason: str = "denied", detail: str = None):
        """Neúspěšné ověření — chybové hlášení a červené bliknutí."""
        self.pending_events.append(EngineEvent(
            "message",
            {"text": ERROR_MESSAGES.get(reason, ERROR_MESSAGES["denied"])}
        ))
        if detail:
            self.pending_events.append(EngineEvent("message", {"text": detail}))
        self.pending_events.append(EngineEvent("sound", {"clip": "error"}))
        self.pending_events.append(EngineEvent("animation", {"kind": "error"}))

    def _check_finale(self):
        """Páteční finále — spustí se po získání všech pěti fragmentů."""
        if self._finale_done:
            return
        required = {m["fragment"] for m in MISSIONS.values()}
        if not required.issubset(set(self.fragments_found)):
            return

        self._finale_done = True
        self.systems["core"] = "ok"
        self.pending_events.append(EngineEvent(
            "system_status",
            {"system": "core", "status": "ok"}
        ))
        for text in FINALE_MESSAGES:
            self.pending_events.append(EngineEvent("message", {"text": text}))
        self.pending_events.append(EngineEvent("sound", {"clip": "finale"}))
        self.pending_events.append(EngineEvent("animation", {"kind": "finale"}))

    # ------------------------------------------------------------------
    # Modul KOMUNIKACE — Morse vysílač
    # ------------------------------------------------------------------
    def _current_morse(self) -> str:
        """Sestaví Morse aktuálního písmene z aktivních pozic přepínačů.

        morse_element[i] = maska (zapnuto → pozice se počítá),
        morse_active[i]  = symbol (zapnuto → tečka '.', vypnuto → čárka '-').
        """
        parts = []
        for i in range(4):
            if self.morse_element[i]:
                parts.append("." if self.morse_active[i] else "-")
        return "".join(parts)

    def _emit_morse_preview(self):
        """Zobrazí na COMMS 7-segmentovce živý Morse podle přepínačů."""
        self.pending_events.append(
            EngineEvent("display7seg", {"morse": self._current_morse()})
        )

    def _morse_add_letter(self):
        code = self._current_morse()
        if not code:
            self.pending_events.append(EngineEvent(
                "message",
                {"text": "Morse: nastav aspoň jeden aktivní prvek přepínačem masky."}
            ))
            return

        letter = MORSE_TO_LETTER.get(code)
        if letter is None or not letter.isalpha():
            self.pending_events.append(EngineEvent(
                "message",
                {"text": f"Morse: neznámý znak '{code}' — nepřidáno."}
            ))
            # Blikni špatným kódem na displeji a písmeno neukládej.
            self.pending_events.append(EngineEvent("display7seg", {"blink_morse": code}))
            self.pending_events.append(EngineEvent("sound", {"clip": "error"}))
            return

        self.morse_word += letter
        self.pending_events.append(EngineEvent(
            "message",
            {"text": f"Morse: přidáno {letter} ({code}) → {self.morse_word}"}
        ))
        # Zobraz dosavadní slovo z paměti na 2 s, pak zpět na živý Morse náhled.
        self.pending_events.append(EngineEvent(
            "display7seg", {"word": self.morse_word, "hold": 2.0}
        ))

    def _morse_delete(self):
        if self.morse_word:
            removed = self.morse_word[-1]
            self.morse_word = self.morse_word[:-1]
            self.pending_events.append(EngineEvent(
                "message",
                {"text": f"Morse: smazáno {removed} → {self.morse_word or '(prázdné)'}"}
            ))
        # Zobraz dosavadní slovo z paměti na 2 s, pak zpět na živý Morse náhled.
        # Po smazání posledního znaku (slovo prázdné) přehraj jednorázovou
        # animaci místo prázdné obrazovky.
        if self.morse_word:
            self.pending_events.append(EngineEvent(
                "display7seg", {"word": self.morse_word, "hold": 2.0}
            ))
        else:
            self.pending_events.append(EngineEvent(
                "display7seg", {"anim": "clear"}
            ))

    def _morse_send(self):
        word = self.morse_word
        if not word:
            self._fail_mission("invalid_code", detail="Morse: nezadáno žádné slovo.")
            return

        morse = " ".join(MORSE_ALPHABET.get(ch, "") for ch in word)
        self.pending_events.append(EngineEvent(
            "message",
            {"text": f"Morse: vysílám '{word}'  [{morse}]"}
        ))
        # Zobraz zadané slovo na 2 s, pak se displej vrátí k živému náhledu.
        self.pending_events.append(EngineEvent(
            "display7seg", {"word": word, "hold": 2.0}
        ))
        # Přehrání celého slova na LED + bzučáku.
        self.pending_events.append(EngineEvent(
            "morse_play",
            {"word": word, "morse": morse}
        ))

        target = MISSIONS["comms"].get("word", "").upper()
        if word.upper() == target:
            self._complete_mission("comms")
            self.morse_word = ""
        else:
            self._fail_mission("invalid_code", detail=f"Morse: zadáno '{word}'. Zkontroluj kód.")

    def _unlock_fragment(self, fragment: str):
        if fragment not in self.fragments_found:
            self.fragments_found.append(fragment)
            self.pending_events.append(EngineEvent(
                "fragment_unlocked",
                {"fragment": fragment}
            ))
            self.pending_events.append(EngineEvent(
                "fragment_count",
                {"count": len(self.fragments_found)}
            ))