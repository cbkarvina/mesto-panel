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

from flask import Flask, jsonify

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
            data = engine.status()
            data["timestamp"] = time.time()
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

    @app.get("/api/areas")
    def get_areas():
        with engine_lock:
            status = engine.status()
        return jsonify(
            active_area=status["active_area"],
            unlocked_areas=status["unlocked_areas"],
            areas=status["areas"],
            countdown=status["countdown"],
        )

    # ------------------------------------------------------------------
    # WRITE ENDPOINTS
    # ------------------------------------------------------------------
    @app.post("/api/unlock")
    def try_unlock():
        # Vyhodnotí aktuální nastavení panelu proti dennímu kódu (stejně jako
        # stisk fyzického unlock_button). Vrací nový stav oblastí.
        with engine_lock:
            before = list(engine.unlocked_areas)
            engine._try_unlock()
            status = engine.status()
        unlocked_now = [a for a in status["unlocked_areas"] if a not in before]
        return jsonify(
            ok=True,
            unlocked=unlocked_now,
            active_area=status["active_area"],
            unlocked_areas=status["unlocked_areas"],
        )

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
