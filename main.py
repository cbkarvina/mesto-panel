#!/usr/bin/env python3
import sys
import time

from city_panel import CityPanel
from game_engine import GameEngine
from mcp23017 import MCP23017Error


def main():
    try:
        panel = CityPanel()
    except MCP23017Error as exc:
        print(f"Panel startup failed: {exc}", file=sys.stderr)
        sys.exit(1)

    engine = GameEngine()

    def on_panel_event(ev):
        active = panel.is_active(ev.name)
        print(f"PANEL: {ev.name:16s} {ev.event_type:10s} active={active}")

        engine.handle_panel_event(
            name=ev.name,
            event_type=ev.event_type,
            is_active=active,
        )

    panel.set_event_callback(on_panel_event)

    print("Tajemné město panel running. Ctrl+C to stop.")

    try:
        while True:
            panel.update()
            engine.tick()

            for ev in engine.pop_events():
                if ev.type == "system_status":
                    panel.set_system_status(ev.payload["system"], ev.payload["status"])

                elif ev.type == "power_level":
                    panel.set_power_level(ev.payload["percent"])

                elif ev.type == "fragment_count":
                    panel.set_fragment_count(ev.payload["count"])

                elif ev.type == "encoder_letter":
                    panel.set_encoder_letter(
                        ev.payload["encoder"],
                        ev.payload["index"],
                    )
                    panel.set_encoder_display(
                        ev.payload["encoder"],
                        ev.payload["index"],
                    )

                elif ev.type == "fragment_unlocked":
                    print(f"FRAGMENT UNLOCKED: {ev.payload['fragment']}")
                    panel.flash_alarm("alarm")

                elif ev.type == "message":
                    print(f"ENGINE: {ev.payload['text']}")

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nExiting...")

    finally:
        panel.close()


if __name__ == "__main__":
    main()