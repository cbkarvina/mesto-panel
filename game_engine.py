#!/usr/bin/env python3
from dataclasses import dataclass, field
from typing import List


@dataclass
class EngineEvent:
    type: str
    payload: dict = field(default_factory=dict)


class GameEngine:
    def __init__(self):
        self.systems = {
            "power": "failure",
            "transport": "offline",
            "comms": "offline",
            "rescue": "warning",
            "core": "locked",
        }

        self.power_required = 50
        self.power_sources = {
            "hydro": False,
            "solar": False,
            "diesel": False,
            "grid": False,
        }

        self.power_values = {
            "hydro": 30,
            "solar": 20,
            "diesel": 40,
            "grid": 10,
        }

        self.fragments_found: List[str] = []
        self.pending_events: List[EngineEvent] = []

        self.encoder_letters = list("ABCDEFGHIJ")
        self.encoder_positions = {
            "medic_code_1": 0,
            "medic_code_2": 0,
        }

        self.pending_events.append(EngineEvent(
            "encoder_letter",
            {"encoder": "medic_code_1", "index": 0}
        ))
        self.pending_events.append(EngineEvent(
            "encoder_letter",
            {"encoder": "medic_code_2", "index": 0}
        ))

    def handle_panel_event(self, name: str, event_type: str, is_active: bool):
        power_changed = False

        if name == "power_hydro" and event_type == "changed":
            self.power_sources["hydro"] = is_active
            power_changed = True

        elif name == "power_solar" and event_type == "changed":
            self.power_sources["solar"] = is_active
            power_changed = True

        elif name == "power_diesel" and event_type == "changed":
            self.power_sources["diesel"] = is_active
            power_changed = True

        elif name == "power_grid" and event_type == "changed":
            self.power_sources["grid"] = is_active
            power_changed = True

        elif name == "power_stabilize" and event_type == "pressed":
            self._stabilize_power()

        elif name == "medic_code_1" and event_type in ("rotated_cw", "rotated_ccw"):
            self._rotate_encoder("medic_code_1", event_type)

        elif name == "medic_code_2" and event_type in ("rotated_cw", "rotated_ccw"):
            self._rotate_encoder("medic_code_2", event_type)

        elif name in ("fire", "medical", "police") and event_type == "pressed":
            self._handle_rescue_button(name)

        elif name == "core_activate" and event_type == "pressed":
            self._activate_core()

        if power_changed:
            self.pending_events.append(EngineEvent(
                "power_level",
                {"percent": self._current_power()}
            ))

    def tick(self):
        pass

    def pop_events(self):
        events = self.pending_events[:]
        self.pending_events.clear()
        return events

    def _stabilize_power(self):
        total = self._current_power()

        # update visible bar always
        self.pending_events.append(EngineEvent(
            "power_level",
            {"percent": total}
        ))

        if total >= self.power_required:
            self.systems["power"] = "ok"
            self._unlock_fragment("POWER-1")
            self.pending_events.append(EngineEvent(
                "system_status",
                {"system": "power", "status": "ok"}
            ))
            self.pending_events.append(EngineEvent(
                "message",
                {"text": f"Power stabilized: {total}%"}
            ))
        else:
            self.systems["power"] = "failure"
            self.pending_events.append(EngineEvent(
                "system_status",
                {"system": "power", "status": "failure"}
            ))
            self.pending_events.append(EngineEvent(
                "message",
                {"text": f"Insufficient power: {total}% / need {self.power_required}%"}
            ))

    def _current_power(self) -> int:
        total = 0
        for source, enabled in self.power_sources.items():
            if enabled:
                total += self.power_values[source]
        return total

    def _handle_rescue_button(self, name: str):
        if name == "fire":
            self.systems["rescue"] = "ok"
            self._unlock_fragment("RESCUE-1")
            self.pending_events.append(EngineEvent(
                "system_status",
                {"system": "rescue", "status": "ok"}
            ))
            self.pending_events.append(EngineEvent(
                "message",
                {"text": "Fire response successful"}
            ))
        elif name == "medical":
            self._handle_medical_call()
        else:
            self.pending_events.append(EngineEvent(
                "message",
                {"text": f"{name} button pressed"}
            ))

    def _encoder_letter(self, encoder_name: str) -> str:
        idx = self.encoder_positions[encoder_name]
        return self.encoder_letters[idx]

    def _rotate_encoder(self, encoder_name: str, event_type: str):
        step = 1 if event_type == "rotated_cw" else -1
        letter_count = len(self.encoder_letters)
        self.encoder_positions[encoder_name] = (
            self.encoder_positions[encoder_name] + step
        ) % letter_count

        self.pending_events.append(EngineEvent(
            "encoder_letter",
            {"encoder": encoder_name, "index": self.encoder_positions[encoder_name]}
        ))

        l1 = self._encoder_letter("medic_code_1")
        l2 = self._encoder_letter("medic_code_2")
        self.pending_events.append(EngineEvent(
            "message",
            {"text": f"Medic code: [{l1}] [{l2}]"}
        ))

    def _handle_medical_call(self):
        l1 = self._encoder_letter("medic_code_1")
        l2 = self._encoder_letter("medic_code_2")

        if l1 == l2:
            self.systems["rescue"] = "ok"
            self._unlock_fragment("RESCUE-1")
            self.pending_events.append(EngineEvent(
                "system_status",
                {"system": "rescue", "status": "ok"}
            ))
            self.pending_events.append(EngineEvent(
                "message",
                {"text": f"Medical team dispatched (code match: {l1})"}
            ))
        else:
            self.pending_events.append(EngineEvent(
                "message",
                {"text": f"Medic call blocked. Set both encoders to same letter (A-J). Current: {l1}/{l2}"}
            ))

    def _activate_core(self):
        required = {"POWER-1", "RESCUE-1"}
        if required.issubset(set(self.fragments_found)):
            self.systems["core"] = "ok"
            self.pending_events.append(EngineEvent(
                "system_status",
                {"system": "core", "status": "ok"}
            ))
            self.pending_events.append(EngineEvent(
                "message",
                {"text": "CORE ACTIVATED"}
            ))
        else:
            self.pending_events.append(EngineEvent(
                "message",
                {"text": "Core locked - missing code fragments"}
            ))

    def _unlock_fragment(self, fragment: str):
        if fragment not in self.fragments_found:
            self.fragments_found.append(fragment)
            self.pending_events.append(EngineEvent(
                "fragment_unlocked",
                {"fragment": fragment}
            ))
            self.pending_events.append(EngineEvent(
                "fragment_count",
                {"count": len(self.fragments_found)}
            ))