#!/usr/bin/env python3
"""MAX7219 8-character 7-segment display debug test."""

import time
from max7219_display import Max7219DisplayError, Max7219SevenSegDisplay


def _open_first_available_display() -> tuple[Max7219SevenSegDisplay, int, int]:
    """Try common SPI endpoints and return the first device that opens."""
    candidates = [
        (0, 0),  # SPI0 CE0 (confirmed working)
        (0, 1),  # SPI0 CE1 (often used for 2nd module)
        (1, 0),  # SPI1 CE0 (if enabled)
    ]

    last_error = None
    for bus, device in candidates:
        try:
            d = Max7219SevenSegDisplay(bus=bus, device=device, intensity=15)
            print(f"Connected to /dev/spidev{bus}.{device}")
            return d, bus, device
        except Max7219DisplayError as exc:
            last_error = exc
            print(f"No response on /dev/spidev{bus}.{device}: {exc}")

    raise Max7219DisplayError(str(last_error) if last_error else "No SPI endpoints available")


def run_display7_test() -> None:
    display7 = None
    try:
        print("=== MAX7219 7-segment test start ===")
        display7, bus, device = _open_first_available_display()

        print("Test 0: Datasheet display-test mode (all LEDs ON)")
        display7.set_intensity(15)
        display7.set_display_test(True)
        time.sleep(2.0)
        display7.set_display_test(False)
        display7.clear(show=True)

        print("Test 1: Code-B decode mode (digits 0-7)")
        display7.set_decode_mode(0xFF)
        time.sleep(0.1)
        for pos in range(8):
            display7.set_bcd_digit(pos, pos, dot=False, show=False)
        display7.show()
        time.sleep(2.0)

        print("Test 2: Switch back to raw segment mode")
        display7.set_decode_mode(0x00)
        time.sleep(0.1)
        display7.clear(show=True)

        print("Test 3: Intensity sweep (raw mode)")
        for level in (0, 2, 4, 8, 12, 15):
            display7.set_intensity(level)
            display7.set_text("LEVEL")
            print(f"  intensity={level}")
            time.sleep(0.5)

        display7.set_intensity(15)
        print("Test 4: 7-segment text")
        for text in ("ABCDEFGH", "01234567", "CODE2026", "A.B.C.D"):
            display7.set_text(text)
            print(f"  text={text}")
            time.sleep(0.8)

        print("Test 5: 7-segment number")
        for value in (0, 7, 42, 1234, 98765432):
            display7.set_number(value)
            print(f"  number={value}")
            time.sleep(0.8)

        print("Test 6: Raw segments (A..G + DP)")
        segment_patterns = [
            ("A", (True, False, False, False, False, False, False, False)),
            ("B", (False, True, False, False, False, False, False, False)),
            ("C", (False, False, True, False, False, False, False, False)),
            ("D", (False, False, False, True, False, False, False, False)),
            ("E", (False, False, False, False, True, False, False, False)),
            ("F", (False, False, False, False, False, True, False, False)),
            ("G", (False, False, False, False, False, False, True, False)),
            ("DP", (False, False, False, False, False, False, False, True)),
        ]

        display7.clear(show=True)
        for name, pattern in segment_patterns:
            display7.clear(show=False)
            display7.set_segments(
                0,
                a=pattern[0],
                b=pattern[1],
                c=pattern[2],
                d=pattern[3],
                e=pattern[4],
                f=pattern[5],
                g=pattern[6],
                dp=pattern[7],
                show=True,
            )
            print(f"  segment={name}")
            time.sleep(0.5)

        print("Test 7: All segments ON")
        display7.set_segments(0, True, True, True, True, True, True, True, dp=True, show=True)
        time.sleep(1.0)

        display7.clear(show=True)
        print("=== MAX7219 7-segment test complete ===")
        print(f"Used /dev/spidev{bus}.{device}")

    except Max7219DisplayError as exc:
        print(f"MAX7219 init error: {exc}")
        print("Check wiring, SPI enable, and /dev/spidev0.0 or /dev/spidev0.1 access.")
    finally:
        if display7 is not None:
            display7.close()


if __name__ == "__main__":
    run_display7_test()
