#!/usr/bin/env python3
import time
from city_panel import CityPanel


def main():
    panel = CityPanel(init_inputs=False)

    try:
        print("Test 1: základní stavy")
        panel.set_system_status("power", "failure")
        panel.set_system_status("rescue", "warning")
        panel.set_system_status("comms", "offline")
        panel.set_system_status("transport", "ok")
        panel.set_system_status("core", "locked")

        for level in (0, 20, 40, 60, 80, 100):
            print(f"Power level: {level}")
            panel.set_power_level(level)
            t0 = time.time()
            while time.time() - t0 < 1.0:
                panel.update()
                time.sleep(0.02)

        print("Test 2: repaired / pulse")
        panel.set_system_status("power", "repaired")
        t0 = time.time()
        while time.time() - t0 < 3.0:
            panel.update()
            time.sleep(0.02)

        print("Test 3: alarm blink")
        panel.flash_alarm("alarm")
        t0 = time.time()
        while time.time() - t0 < 5.0:
            panel.update()
            time.sleep(0.02)

        print("Test 4: fragments")
        for n in range(6):
            panel.set_fragment_count(n)
            t0 = time.time()
            while time.time() - t0 < 0.7:
                panel.update()
                time.sleep(0.02)

    finally:
        panel.close()


if __name__ == "__main__":
    main()