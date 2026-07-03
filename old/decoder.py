#!/usr/bin/env python3
"""
Městský dekodér — univerzální převodní tabulka pro hru "Tajemné město".

Každá z 10 hodnot (A–J / 1–10) má reprezentaci jako barva, symbol, číslo,
písmeno a Morseův kód. Modul umožňuje mezi těmito zápisy převádět.

Příklad:
    >>> from decoder import decoder
    >>> decoder.encode("ACE", mode="morse")
    '.- -.-. .'
    >>> decoder.encode("ACE", mode="symbol")
    '✴ 🕯 💣'
    >>> decoder.decode(".-")
    'A'
"""
from typing import Dict, List, Optional


# Pořadí odpovídá řádkům dekódovací tabulky (č. 1–10 → A–J).
ENTRIES: List[Dict[str, object]] = [
    {"letter": "A", "number": 1,  "color": "Červená",  "color_en": "red",    "symbol": "✴", "symbol_name": "star",       "morse": ".-"},
    {"letter": "B", "number": 2,  "color": "Modrá",    "color_en": "blue",   "symbol": "✈", "symbol_name": "airplane",   "morse": "-..."},
    {"letter": "C", "number": 3,  "color": "Zelená",   "color_en": "green",  "symbol": "🕯", "symbol_name": "candle",     "morse": "-.-."},
    {"letter": "D", "number": 4,  "color": "Žlutá",    "color_en": "yellow", "symbol": "🕒", "symbol_name": "clock",      "morse": "-.."},
    {"letter": "E", "number": 5,  "color": "Oranžová", "color_en": "orange", "symbol": "💣", "symbol_name": "bomb",       "morse": "."},
    {"letter": "F", "number": 6,  "color": "Fialová",  "color_en": "purple", "symbol": "✁", "symbol_name": "scissors",   "morse": "..-."},
    {"letter": "G", "number": 7,  "color": "Bílá",     "color_en": "white",  "symbol": "📖", "symbol_name": "book",       "morse": "--."},
    {"letter": "H", "number": 8,  "color": "Černá",    "color_en": "black",  "symbol": "👁", "symbol_name": "eye",        "morse": "...."},
    {"letter": "I", "number": 9,  "color": "Hnědá",    "color_en": "brown",  "symbol": "🔔", "symbol_name": "bell",       "morse": ".."},
    {"letter": "J", "number": 10, "color": "Šedá",     "color_en": "gray",    "symbol": "🎧", "symbol_name": "headphones", "morse": ".---"},
]

MODES = ("letter", "number", "color", "color_en", "symbol", "symbol_name", "morse")

# Oddělovač výstupu podle režimu.
_SEPARATORS = {
    "color": ", ",
    "color_en": ", ",
    "symbol_name": ", ",
}
_DEFAULT_SEPARATOR = " "


class Decoder:
    """Obousměrný převodník mezi zápisy městského dekodéru."""

    def __init__(self, entries: Optional[List[Dict[str, object]]] = None):
        self.entries = entries if entries is not None else ENTRIES
        # Lookup mapy pro dekódování z libovolného zápisu na písmeno.
        self._lookup: Dict[str, str] = {}
        for e in self.entries:
            letter = str(e["letter"])
            self._register(str(e["letter"]).upper(), letter)
            self._register(str(e["number"]), letter)
            self._register(str(e["color"]).lower(), letter)
            self._register(str(e["color_en"]).lower(), letter)
            self._register(str(e["symbol"]), letter)
            self._register(str(e["symbol_name"]).lower(), letter)
            self._register(str(e["morse"]), letter)
        # Rychlý přístup z písmene na celý záznam.
        self._by_letter: Dict[str, Dict[str, object]] = {
            str(e["letter"]).upper(): e for e in self.entries
        }

    def _register(self, key: str, letter: str) -> None:
        if key:
            self._lookup[key] = letter

    # ------------------------------------------------------------------
    # ENCODE: písmena -> jiný zápis
    # ------------------------------------------------------------------
    def encode(self, text: str, mode: str = "morse") -> str:
        """
        Převede řetězec písmen (A–J) na zvolený zápis.

        Mezery a neznámé znaky ve vstupu jsou ignorovány.
        """
        if mode not in MODES:
            raise ValueError(f"Neznámý mode '{mode}'. Použij: {', '.join(MODES)}")

        tokens: List[str] = []
        for ch in text:
            if ch.isspace():
                continue
            entry = self._by_letter.get(ch.upper())
            if entry is None:
                raise KeyError(f"Neznámé písmeno '{ch}' (povoleno A–J)")
            tokens.append(str(entry[mode]))

        separator = _SEPARATORS.get(mode, _DEFAULT_SEPARATOR)
        return separator.join(tokens)

    # ------------------------------------------------------------------
    # DECODE: libovolný zápis -> písmeno
    # ------------------------------------------------------------------
    def decode(self, token: str, mode: Optional[str] = None) -> str:
        """
        Převede jeden token (Morse, číslo, barvu, symbol, ...) na písmeno.

        Pokud je zadán ``mode``, hledá se pouze v daném sloupci; jinak se
        zápis autodetekuje.
        """
        token = token.strip()
        if mode is not None:
            if mode not in MODES:
                raise ValueError(f"Neznámý mode '{mode}'. Použij: {', '.join(MODES)}")
            key = token.lower() if mode in ("color", "color_en", "symbol_name", "letter") else token
            for e in self.entries:
                if str(e[mode]).lower() == key.lower():
                    return str(e["letter"])
            raise KeyError(f"'{token}' nenalezeno v režimu '{mode}'")

        # Autodetekce: zkus přesnou shodu, pak case-insensitive.
        if token in self._lookup:
            return self._lookup[token]
        if token.lower() in self._lookup:
            return self._lookup[token.lower()]
        raise KeyError(f"'{token}' nelze dekódovat")

    def decode_sequence(self, text: str, mode: Optional[str] = None) -> str:
        """Dekóduje sekvenci tokenů oddělených mezerami na řetězec písmen."""
        parts = [p for p in text.split() if p]
        return "".join(self.decode(p, mode=mode) for p in parts)

    # ------------------------------------------------------------------
    # Pomocné
    # ------------------------------------------------------------------
    def entry(self, letter: str) -> Dict[str, object]:
        """Vrátí celý záznam pro dané písmeno A–J."""
        e = self._by_letter.get(letter.upper())
        if e is None:
            raise KeyError(f"Neznámé písmeno '{letter}'")
        return e


# Sdílená instance pro použití v celé aplikaci.
decoder = Decoder()


if __name__ == "__main__":
    print("Městský dekodér — demo")
    print("encode('ACE', morse) =", decoder.encode("ACE", mode="morse"))
    print("encode('ACE', color) =", decoder.encode("ACE", mode="color"))
    print("encode('ACE', symbol) =", decoder.encode("ACE", mode="symbol"))
    print("encode('ACE', number) =", decoder.encode("ACE", mode="number"))
    print("decode('.-') =", decoder.decode(".-"))
    print("decode('Modrá') =", decoder.decode("Modrá"))
    print("decode_sequence('.- ....') =", decoder.decode_sequence(".- ...."))
    print("decode_sequence('👁 ✁ 🕯') =", decoder.decode_sequence("👁 ✁ 🕯"))
