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
    app = Flask(__name__, static_folder="static", static_url_path="/static")

    # ------------------------------------------------------------------
    # WEB UI
    # ------------------------------------------------------------------
    @app.get("/")
    def index():
        """Jednoduchá webová stránka s tlačítky pro spouštění API volání."""
        return app.send_static_file("index.html")

    # ------------------------------------------------------------------
    # READ ENDPOINTS
    # ------------------------------------------------------------------
    @app.get("/api/status")
    def get_status():
        """Systémy (oblasti), odpočet a délka morseovky."""
        with engine_lock:
            data = engine.status()
            data["timestamp"] = time.time()
        return jsonify(data)

    @app.get("/api/inputs")
    def get_inputs():
        """Stav tlačítek/přepínačů + pozice enkodérů."""
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
        """Logický stav LED: oblasti (zamčené/odemčené), odpočet, barva."""
        with engine_lock:
            status = engine.status()
            leds = getattr(panel, "leds", None)
            countdown_fraction = getattr(leds, "countdown_fraction", None) if leds else None
            locked_segments = sorted(leds.locked_segments) if leds else []
        return jsonify(
            areas=status["areas"],
            unlocked_areas=status["unlocked_areas"],
            locked_segments=locked_segments,
            countdown_fraction=countdown_fraction,
            color=status["color"],
        )

    # ------------------------------------------------------------------
    # WRITE ENDPOINTS
    # ------------------------------------------------------------------
    @app.post("/api/unlock/<int:day>")
    def unlock_day(day: int):
        """Odemkne oblast daného dne (1-5) bez ověřování kódu."""
        try:
            with engine_lock:
                key = engine.unlock_day(day)
                status = engine.status()
        except ValueError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        return jsonify(
            ok=True,
            day=day,
            area=key,
            unlocked_areas=status["unlocked_areas"],
            active_area=status["active_area"],
        )

    @app.post("/api/lock/<int:day>")
    def lock_day(day: int):
        """Zamkne oblast daného dne (1-5) a volitelně nastaví její kód.

        Tělo (volitelné): {"morse","color","number","letter","glyph"}.
        """
        body = request.get_json(silent=True) or {}
        try:
            with engine_lock:
                key = engine.lock_day(day, body or None)
                status = engine.status()
        except ValueError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        return jsonify(
            ok=True,
            day=day,
            area=key,
            unlocked_areas=status["unlocked_areas"],
            active_area=status["active_area"],
        )

    @app.post("/api/restart")
    def restart():
        """Restart hry. Tělo (volitelné): {"countdown": int sekund}."""
        body = request.get_json(silent=True) or {}
        seconds = body.get("countdown")
        try:
            with engine_lock:
                engine.restart(seconds)
                status = engine.status()
        except (ValueError, TypeError) as exc:
            return jsonify(ok=False, error=str(exc)), 400
        return jsonify(ok=True, countdown=status["countdown"])

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
