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
BUZZER_PIN = 12  # např. 16

# Časování Morse přehrávání (sekundy).
MORSE_DOT = 0.15
MORSE_DASH = 0.45
MORSE_GAP = 0.15
MORSE_LETTER_GAP = 0.45

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
    """Přehraje Morse řetězec (písmena oddělená mezerou) na bzučáku.

    Komunikační LED se pro Morse nepoužívá — slouží jen jako stavový
    indikátor (vyřešeno / nevyřešeno).
    """
    for token in morse.split(" "):
        for symbol in token:
            duration = MORSE_DASH if symbol == "-" else MORSE_DOT
            _buzzer_set(True)
            time.sleep(duration)
            _buzzer_set(False)
            time.sleep(MORSE_GAP)
        time.sleep(MORSE_LETTER_GAP)


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

    # Načti počáteční stav vstupů a zobraz ho do panelů: každý enkodér svou
    # výchozí hodnotu na vlastní matici a morse podle 5 přepínačů na 7-segmentovku.
    engine.sync_initial_state(panel.read_morse_switches())
    panel.show_initial_state()

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

                    elif ev.type == "encoder_letter":
                        # panel.set_encoder_letter(
                        #     ev.payload["encoder"],
                        #     ev.payload["index"],
                        # )
                        panel.set_encoder_display(
                            ev.payload["encoder"],
                            ev.payload["index"],
                        )

                    elif ev.type == "color_select":
                        # Vybraná barva (tlačítko button_color) → prvních 5 LED.
                        leds = getattr(panel, "leds", None)
                        if leds is not None:
                            leds.set_color_leds(tuple(ev.payload["rgb"]))

                    elif ev.type == "dead":
                        # Vypršel odpočet → blikne DEAD; restart (active=False) obnoví.
                        if ev.payload.get("active", True):
                            panel.set_display7seg_locked(
                                True, ev.payload.get("message", "DEAD")
                            )
                        else:
                            panel.set_display7seg_locked(False)
                        leds = getattr(panel, "leds", None)
                        if leds is not None:
                            leds.set_central_scan(False)

                    elif ev.type == "display_anim":
                        if ev.payload.get("kind") == "unlock":
                            panel.play_unlock_anim()

                    elif ev.type == "central_scan":
                        leds = getattr(panel, "leds", None)
                        if leds is not None:
                            color = (0, 255, 0) if ev.payload.get("color") == "green" else (255, 0, 0)
                            leds.set_central_scan(ev.payload["active"], color)

                    elif ev.type == "central_bar":
                        leds = getattr(panel, "leds", None)
                        if leds is not None:
                            leds.set_central_bar(ev.payload.get("fraction"))

                    elif ev.type == "sound":
                        # Placeholder pro TTS / přednahrané zvuky.
                        print(f"SOUND: {ev.payload['clip']}")

                    elif ev.type == "animation":
                        kind = ev.payload.get("kind")
                        if kind == "error":
                            panel.flash_alarm("alarm")
                            # Špatný kód: stavový segment 3× červeně blikne.
                            panel.blink_status(times=3, color=(255, 0, 0))
                        elif kind in ("success", "finale"):
                            # Zelená potvrzovací animace.
                            panel.set_indicator("alarm", (0, 255, 0), mode="blink")

                    elif ev.type == "map_reveal":
                        location = ev.payload["location"]
                        print(f"MAP: rozsvěcuji {location}")
                        # Místo na mapě = segment obnoveného systému (zelená vlna).
                        panel.set_indicator(ev.payload["system"], (0, 255, 0), mode="flow")

                    elif ev.type == "display7seg":
                        # 7-segmentovka zobrazuje výhradně morse (tečky/čárky),
                        # žádný dekódovaný znak/slovo jako náhled.
                        panel.set_display7seg_morse(ev.payload.get("morse", ""))

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