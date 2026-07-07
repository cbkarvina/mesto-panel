#!/usr/bin/env python3
"""Display test for the current wiring.

Three MAX7219 modules are daisy-chained on a single SPI chip-select
(spidev0.0):

    module 0 = matrix #1  ("first chip")  -> letters + numbers (alternating)
    module 1 = matrix #2  ("second chip") -> symbols
    module 2 = 7-segment                  -> COMMS morse

Run on the Raspberry Pi with SPI enabled:
    python3 test/test_displays.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from max7219_display import (  # noqa: E402
    Max7219Chain,
    Max7219Display,
    Max7219DisplayError,
    Max7219SevenSegDisplay,
    SYMBOLS,
)

# --- Wiring configuration -------------------------------------------------
CHAIN_BUS = 0
CHAIN_DEVICE = 0        # spidev0.0 -> all three modules on one line
NUM_MATRIX_MODULES = 2  # module 0 + module 1 (matrices)
SEVEN_SEG_INDEX = 2     # module 2 -> 7-segment, chained on the same line
# -------------------------------------------------------------------------

STEP = 0.35


def _test_intensity(matrices, seven_seg):
    print("Test 1: Intensity sweep")
    for level in (0, 2, 4, 8, 12, 15):
        for m in matrices:
            m.set_intensity(level)
            m.set_char("8")
        if seven_seg is not None:
            seven_seg.set_intensity(level)
            seven_seg.set_text("88888888")
        print(f"  intensity={level}")
        time.sleep(0.4)


def _test_first_chip_letters_numbers(display):
    print("Test 2: First chip -> letters A-J")
    for idx in range(10):
        display.set_index_letter(idx)
        print(f"  index={idx} letter={chr(ord('A') + idx)}")
        time.sleep(STEP)

    print("Test 3: First chip -> numbers 0-9")
    for digit in range(10):
        display.set_char(str(digit))
        print(f"  digit={digit}")
        time.sleep(STEP)


def _test_second_chip_symbols(display):
    print("Test 4: Second chip -> symbols 0-9")
    for idx in range(len(SYMBOLS)):
        display.set_glyph_by_index(idx)
        print(f"  symbol index={idx}")
        time.sleep(STEP)


def _test_seven_seg(seven_seg):
    if seven_seg is None:
        print("Test 5: 7-segment skipped (not initialized)")
        return
    print("Test 5: 7-segment (separate SPI) -> text / number / morse")
    seven_seg.set_text("HELLO")
    time.sleep(1.0)
    seven_seg.set_number(12345678)
    time.sleep(1.0)
    # Morse: '.' -> decimal point, '-' -> middle bar.
    for code in ("-", ".", "--", "..-.", ".....", "-----"):
        seven_seg.set_morse(code)
        print(f"  morse={code!r}")
        time.sleep(0.6)


def _test_blink(matrices, seven_seg):
    print("Test 6: Blink check")
    for _ in range(6):
        for m in matrices:
            m.clear(show=True)
        if seven_seg is not None:
            seven_seg.clear(show=True)
        time.sleep(0.2)
        matrices[0].set_char("A")
        if len(matrices) > 1:
            matrices[1].set_glyph_by_index(0)
        if seven_seg is not None:
            seven_seg.set_morse(".-.-.")
        time.sleep(0.2)


def run_display_test() -> None:
    chain = None
    matrices = []
    seven_seg = None
    try:
        print("=== MAX7219 display test start ===")
        chain = Max7219Chain(bus=CHAIN_BUS, device=CHAIN_DEVICE,
                             num_modules=NUM_MATRIX_MODULES + 1)
        for module_index in range(NUM_MATRIX_MODULES):
            matrices.append(
                Max7219Display(chain=chain, module_index=module_index, intensity=4)
            )

        # 7-segment panel is chained on the same SPI line (last module).
        try:
            seven_seg = Max7219SevenSegDisplay(
                chain=chain, module_index=SEVEN_SEG_INDEX, intensity=4
            )
        except Max7219DisplayError as exc:
            print(f"7-seg disabled (module {SEVEN_SEG_INDEX}): {exc}")
            seven_seg = None

        _test_intensity(matrices, seven_seg)
        _test_first_chip_letters_numbers(matrices[0])
        if len(matrices) > 1:
            _test_second_chip_symbols(matrices[1])
        _test_seven_seg(seven_seg)
        _test_blink(matrices, seven_seg)

        for m in matrices:
            m.clear(show=True)
        if seven_seg is not None:
            seven_seg.clear(show=True)
        print("=== MAX7219 display test complete ===")

    except Max7219DisplayError as exc:
        print(f"MAX7219 init error: {exc}")
        print(f"Check wiring, SPI enable, and /dev/spidev{CHAIN_BUS}.{CHAIN_DEVICE} access.")
    finally:
        for m in matrices:
            m.close()
        if seven_seg is not None:
            seven_seg.close()
        if chain is not None:
            chain.close()


if __name__ == "__main__":
    run_display_test()
