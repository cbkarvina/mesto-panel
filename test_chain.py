#!/usr/bin/env python3
"""Daisy-chained MAX7219 test: two 8x8 matrices + 8-digit 7-segment on ONE SPI line.

All three modules are wired in series (DOUT -> DIN) sharing a single CS, and
driven through a Max7219Chain so each write clocks one word per module.

Wiring order from the Pi's MOSI/DIN (module 0 = closest):
  module 0 = matrix #1, module 1 = matrix #2, module 2 = 7-segment
If a glyph shows on the wrong device, adjust the *_INDEX values below.
"""

import time
from max7219_display import (
    Max7219Chain,
    Max7219Display,
    Max7219DisplayError,
    Max7219SevenSegDisplay,
)

# Adjust to match physical wiring order (0 = closest to the Pi's MOSI).
MATRIX1_INDEX = 0  # first 8x8 LED matrix
MATRIX2_INDEX = 1  # second 8x8 LED matrix
MATRIX3_INDEX = 2  # second 8x8 LED matrix
SEG_INDEX = 3      # 8-digit 7-segment panel


def run_chain_test() -> None:
    chain = None
    matrix1 = None
    matrix2 = None
    seg8 = None
    try:
        print("=== Daisy-chained MAX7219 test (single SPI line) ===")
        print("Opening chain on /dev/spidev0.0 (4 modules) ...")
        chain = Max7219Chain(bus=0, device=0, num_modules=4, max_speed_hz=1000000)
        print("  OK")

        matrix1 = Max7219Display(chain=chain, module_index=MATRIX1_INDEX, intensity=8)
        matrix2 = Max7219Display(chain=chain, module_index=MATRIX2_INDEX, intensity=8)
        matrix3 = Max7219Display(chain=chain, module_index=MATRIX3_INDEX, intensity=8)
        seg8 = Max7219SevenSegDisplay(chain=chain, module_index=SEG_INDEX, intensity=8)
        print(
            f"  matrix1 = module {MATRIX1_INDEX}, "
            f"matrix2 = module {MATRIX2_INDEX}, "
            f"matrix3 = module {MATRIX3_INDEX}, "
            f"7-seg = module {SEG_INDEX}\n"
        )

        print("Test 1: clear all")
        matrix1.clear(show=True)
        matrix2.clear(show=True)
        matrix3.clear(show=True)
        seg8.clear(show=True)
        time.sleep(0.5)

        print("Test 2: identify which device is which")
        matrix1.set_char("1")
        matrix2.set_char("2")
        matrix3.set_char("3")
        seg8.set_text("SEG")
        time.sleep(2.0)

        print("Test 3: letters on matrices + text on 7-segment")
        words = ["HELLO", "CODE", "2026", "PANEL"]
        for i, word in enumerate(words):
            matrix1.set_index_letter(i)        # A, B, C, D
            matrix2.set_index_letter(i + 1)    # B, C, D, E
            matrix3.set_index_letter(i + 2)    # C, D, E, F
            seg8.set_text(word)
            print(f"  matrix1='{chr(ord('A') + i)}'  matrix2='{chr(ord('A') + i + 1)}'  matrix3='{chr(ord('A') + i + 2)}'  7seg='{word}'")
            time.sleep(1.0)

        print("Test 4: count up on all three")
        for n in range(10):
            matrix1.set_char(str(n))
            matrix2.set_char(str(9 - n))
            matrix3.set_char(str(n))
            seg8.set_number(n)
            print(f"  number={n}")
            time.sleep(0.4)

        print("Test 5: blink all 3x")
        for _ in range(3):
            matrix1.set_char("8")
            matrix2.set_char("8")
            matrix3.set_char("8")
            seg8.set_text("ON")
            time.sleep(0.3)
            matrix1.clear(show=True)
            matrix2.clear(show=True)
            matrix3.clear(show=True)
            seg8.clear(show=True)
            time.sleep(0.3)

        print("\n=== Chain test complete ===")

    except Max7219DisplayError as exc:
        print(f"MAX7219 error: {exc}")
        print("Check wiring, SPI enable, and device permissions.")
    finally:
        if matrix1 is not None:
            matrix1.close()
        if matrix2 is not None:
            matrix2.close()
        if matrix3 is not None:
            matrix3.close()
        if seg8 is not None:
            seg8.close()
        if chain is not None:
            chain.close()


if __name__ == "__main__":
    run_chain_test()

