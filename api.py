#!/usr/bin/env python3
"""
Flask REST API for the 'Tajemné město' control panel.

The API runs in a background thread inside the same process as the panel
loop, because the Raspberry Pi hardware (SPI / I2C / GPIO) can only be driven
from a single process. All hardware / engine access is serialized through a
shared threading.Lock (``engine_lock``) that the main loop also holds while it
polls inputs and updates the displays/LEDs.
"""
import time
import threading
from typing import Dict

from flask import Flask, jsonify, request

from game_engine import GameEngine
from city_panel import CityPanel


def create_app(panel: "CityPanel", engine: "GameEngine", engine_lock: threading.Lock) -> Flask:
    app = Flask(__name__)

    # ------------------------------------------------------------------
    # READ ENDPOINTS
    # ------------------------------------------------------------------
    @app.get("/api/status")
    def get_status():
        with engine_lock:
            data = {
                "systems": dict(engine.systems),
                "power": {
                    "current": engine._current_power(),
                    "required": engine.power_required,
                    "sources": dict(engine.power_sources),
                },
                "fragments": list(engine.fragments_found),
                "encoders": dict(engine.encoder_positions),
                "timestamp": time.time(),
            }
        return jsonify(data)

    @app.get("/api/inputs")
    def get_inputs():
        with engine_lock:
            buttons: Dict[str, bool] = {}
            if panel.inputs is not None:
                for name in panel.inputs.inputs:
                    buttons[name] = panel.inputs.is_active(name)
                encoders = dict(engine.encoder_positions)
            else:
                encoders = {}
        return jsonify(buttons=buttons, encoders=encoders)

    @app.get("/api/leds")
    def get_leds():
        # The logical LED state mirrors the engine: each system maps to a
        # coloured segment, plus the power bar and fragment indicators.
        with engine_lock:
            data = {
                "systems": dict(engine.systems),
                "power_level": engine._current_power(),
                "fragment_count": len(engine.fragments_found),
            }
        return jsonify(data)

    # ------------------------------------------------------------------
    # WRITE ENDPOINTS
    # ------------------------------------------------------------------
    @app.post("/api/system/status")
    def set_system_status():
        body = request.get_json(silent=True) or {}
        system = body.get("system")
        status = body.get("status")
        if not system or not status:
            return jsonify(ok=False, error="'system' and 'status' are required"), 400
        if system not in engine.systems:
            return jsonify(ok=False, error=f"unknown system '{system}'"), 404

        try:
            with engine_lock:
                engine.systems[system] = status
                panel.set_system_status(system, status)
        except Exception as exc:  # invalid status string, etc.
            return jsonify(ok=False, error=str(exc)), 400
        return jsonify(ok=True, system=system, status=status)

    @app.post("/api/fragment/unlock")
    def unlock_fragment():
        body = request.get_json(silent=True) or {}
        fragment = body.get("fragment")
        if not fragment:
            return jsonify(ok=False, error="'fragment' is required"), 400

        with engine_lock:
            already = fragment in engine.fragments_found
            # Enqueues fragment_unlocked / fragment_count events that the main
            # loop drains and reflects on the LEDs.
            engine._unlock_fragment(fragment)
            fragments = list(engine.fragments_found)
        return jsonify(ok=True, fragment=fragment, already_unlocked=already, fragments=fragments)

    @app.post("/api/mission/start")
    def start_mission():
        body = request.get_json(silent=True) or {}
        mission = body.get("mission")
        if not mission:
            return jsonify(ok=False, error="'mission' is required"), 400
        # Mission plugin system is not implemented yet in the engine.
        return jsonify(ok=False, error="missions not implemented"), 501

    return app


def start_api_thread(
    panel: "CityPanel",
    engine: "GameEngine",
    engine_lock: threading.Lock,
    host: str = "0.0.0.0",
    port: int = 5000,
) -> threading.Thread:
    """Start the Flask API in a daemon thread and return the thread."""
    app = create_app(panel, engine, engine_lock)
    thread = threading.Thread(
        target=lambda: app.run(host=host, port=port, threaded=True, use_reloader=False),
        name="flask-api",
        daemon=True,
    )
    thread.start()
    return thread
