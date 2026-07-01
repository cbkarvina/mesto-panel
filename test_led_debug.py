#!/usr/bin/env python3
"""MAX7218/MAX7219 matrix display debug test."""

import time
from max7219_display import Max7219Display, Max7219DisplayError


def run_display_test() -> None:
    display = None
    display2 = None
    try:
        print("=== MAX7219 matrix test start ===")
        display = Max7219Display(bus=0, device=0, intensity=4)
        display2 = Max7219Display(bus=0, device=1, intensity=4)

        print("Test 1: Intensity sweep")
        for level in (0, 2, 4, 8, 12, 15):
            display.set_intensity(level)
            display2.set_intensity(level)
            display.set_char("A")
            display2.set_char("B")
            print(f"  intensity={level}")
            time.sleep(0.5)

        print("Test 2: Digits 0-9 on display #1")
        for ch in "0123456789":
            display.set_char(ch)
            print(f"  char={ch}")
            time.sleep(0.35)

        print("Test 3: Letters A-J on display #2")
        for idx in range(10):
            display2.set_index_letter(idx)
            print(f"  index={idx} letter={chr(ord('A') + idx)}")
            time.sleep(0.35)

        print("Test 4: Blink check (both displays)")
        for _ in range(6):
            display.clear(show=True)
            display2.clear(show=True)
            time.sleep(0.2)
            display.set_char("H", show=True)
            display2.set_char("I", show=True)
            time.sleep(0.2)

        display.clear(show=True)
        display2.clear(show=True)
        print("=== MAX7219 matrix test complete ===")

    except Max7219DisplayError as exc:
        print(f"MAX7219 init error: {exc}")
        print("Check wiring, SPI enable, and /dev/spidev0.0 + /dev/spidev0.1 access.")
    finally:
        if display is not None:
            display.close()
        if display2 is not None:
            display2.close()


if __name__ == "__main__":
    run_display_test()
