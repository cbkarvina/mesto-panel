#!/usr/bin/env python3
import sys
import time
import signal
import threading

from city_panel import CityPanel
from game_engine import GameEngine
from mcp23017 import MCP23017Error
from api import start_api_thread


# Bzučák pro modul KOMUNIKACE — BCM pin (uprav podle zapojení). None = bez bzučáku.
BUZZER_PIN = None  # např. 16

# Časování Morse přehrávání (sekundy).
MORSE_DOT = 0.15
MORSE_DASH = 0.45
MORSE_GAP = 0.15
MORSE_LETTER_GAP = 0.45

# Červené bliknutí Morse LED při nevyřešeném komunikačním kódu.
COMMS_ERROR_BLINKS = 3
COMMS_ERROR_ON = 0.2
COMMS_ERROR_OFF = 0.2

_buzzer = None


def _init_buzzer():
    """Připraví bzučák na GPIO, pokud je nastaven BUZZER_PIN a běžíme na RPi."""
    global _buzzer
    if BUZZER_PIN is None:
        return
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)
        _buzzer = GPIO
    except Exception as exc:
        print(f"Buzzer disabled: {exc}")
        _buzzer = None


def _buzzer_set(on: bool):
    if _buzzer is not None:
        _buzzer.output(BUZZER_PIN, _buzzer.HIGH if on else _buzzer.LOW)


def play_morse(panel, morse: str):
    """Přehraje Morse řetězec (písmena oddělená mezerou) na LED + bzučáku."""
    leds = getattr(panel, "leds", None)

    def light(on: bool):
        if leds is None:
            return
        try:
            # Komunikační režim = rezervovaná Morse LED (první pixel z pásku).
            leds.set_comms_led((0, 255, 0) if on else (0, 0, 0))
        except Exception:
            pass

    for token in morse.split(" "):
        for symbol in token:
            duration = MORSE_DASH if symbol == "-" else MORSE_DOT
            light(True)
            _buzzer_set(True)
            time.sleep(duration)
            _buzzer_set(False)
            light(False)
            time.sleep(MORSE_GAP)
        time.sleep(MORSE_LETTER_GAP)


def blink_comms_error(panel):
    """Červené bliknutí Morse LED komunikace = kód nevyřešen."""
    leds = getattr(panel, "leds", None)
    if leds is None:
        return
    try:
        for _ in range(COMMS_ERROR_BLINKS):
            leds.set_comms_led((255, 0, 0))
            time.sleep(COMMS_ERROR_ON)
            leds.set_comms_led((0, 0, 0))
            time.sleep(COMMS_ERROR_OFF)
    except Exception:
        pass


def main():
    try:
        panel = CityPanel()
    except MCP23017Error as exc:
        print(f"Panel startup failed: {exc}", file=sys.stderr)
        sys.exit(1)

    engine = GameEngine()

    # Serializes all hardware/engine access shared between the panel loop and
    # the Flask API thread.
    engine_lock = threading.Lock()

    def on_panel_event(ev):
        active = panel.is_active(ev.name)
        print(f"PANEL: {ev.name:16s} {ev.event_type:10s} active={active}")

        engine.handle_panel_event(
            name=ev.name,
            event_type=ev.event_type,
            is_active=active,
        )

    panel.set_event_callback(on_panel_event)

    # Start the REST API in a background daemon thread (same process).
    start_api_thread(panel, engine, engine_lock, host="0.0.0.0", port=5000)

    _init_buzzer()

    # systemd stops the service with SIGTERM; translate it into a clean exit
    # so the finally block runs and the hardware is released.
    stop = threading.Event()

    def _handle_signal(signum, _frame):
        print(f"\nReceived signal {signum}, shutting down...")
        stop.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    print("Tajemné město panel running (API on :5000). Ctrl+C to stop.")

    try:
        while not stop.is_set():
            with engine_lock:
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

                    elif ev.type == "sound":
                        # Placeholder pro TTS / přednahrané zvuky.
                        print(f"SOUND: {ev.payload['clip']}")

                    elif ev.type == "animation":
                        kind = ev.payload.get("kind")
                        if kind == "error":
                            panel.flash_alarm("alarm")
                        elif kind in ("success", "finale"):
                            # Zelená potvrzovací animace.
                            panel.set_indicator("alarm", (0, 255, 0), mode="blink")

                    elif ev.type == "map_reveal":
                        location = ev.payload["location"]
                        print(f"MAP: rozsvěcuji {location}")
                        # Místo na mapě = segment obnoveného systému (zeleně).
                        panel.set_indicator(ev.payload["system"], (0, 255, 0), mode="solid")

                    elif ev.type == "display7seg":
                        if "word" in ev.payload:
                            panel.show_display7seg_word(
                                ev.payload["word"], ev.payload.get("hold", 2.0)
                            )
                        elif "blink_morse" in ev.payload:
                            panel.blink_display7seg_morse(ev.payload["blink_morse"])
                        else:
                            panel.set_display7seg_morse(ev.payload.get("morse", ""))

                    elif ev.type == "morse_play":
                        # Přehrání Morse slova na LED + bzučáku.
                        print(f"MORSE PLAY: {ev.payload['word']}  [{ev.payload['morse']}]")
                        play_morse(panel, ev.payload["morse"])

                    elif ev.type == "comms_error":
                        # Nevyřešený komunikační kód = červené bliknutí Morse LED.
                        print("COMMS ERROR: kód nevyřešen")
                        blink_comms_error(panel)

                    elif ev.type == "message":
                        print(f"ENGINE: {ev.payload['text']}")

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nExiting...")

    finally:
        print("Closing panel...")
        panel.close()


if __name__ == "__main__":
    main()