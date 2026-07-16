"""The Dreaming Ground — a 5-step mystery questline gated on farming milestones."""
from __future__ import annotations

from typing import Any

from game.config import load_json


class QuestSystem:
    def __init__(self, data: dict[str, Any] | None = None):
        d = data if data is not None else load_json("quests.json")
        q = d["questline"]
        self.name: str = q["name"]
        self.steps: list[dict[str, Any]] = q["steps"]
        self.completed: list[str] = []
        self.total_harvests: int = 0

    @property
    def current_step(self) -> dict[str, Any] | None:
        idx = len(self.completed)
        return self.steps[idx] if idx < len(self.steps) else None

    @property
    def finished(self) -> bool:
        return self.current_step is None

    def gate_met(self, step: dict[str, Any], codex_count: int, avg_resonance: float) -> bool:
        g = step["gate"]
        if g["type"] == "none":
            return True
        if g["type"] == "total_harvests":
            return self.total_harvests >= g["value"]
        if g["type"] == "codex_entries":
            return codex_count >= g["value"]
        if g["type"] == "avg_resonance":
            return avg_resonance >= g["value"]
        raise ValueError(f"unknown quest gate type: {g['type']}")

    def try_trigger(self, trigger: str, codex_count: int, avg_resonance: float,
                    is_night: bool) -> dict[str, Any] | None:
        """Fire the current step if its trigger matches and its gate is met."""
        step = self.current_step
        if step is None or step["trigger"] != trigger:
            return None
        if trigger == "great_crystal_night" and not is_night:
            return None
        if not self.gate_met(step, codex_count, avg_resonance):
            return None
        self.completed.append(step["id"])
        return step

    def journal_entries(self) -> list[dict[str, Any]]:
        return [s for s in self.steps if s["id"] in self.completed]

    def hint(self, codex_count: int, avg_resonance: float) -> str:
        step = self.current_step
        if step is None:
            return "Veridia is awake. Tend the garden."
        if not self.gate_met(step, codex_count, avg_resonance):
            g = step["gate"]
            if g["type"] == "total_harvests":
                return f"Keep farming... ({self.total_harvests}/{g['value']} harvests)"
            if g["type"] == "codex_entries":
                return f"Document wild flora... ({codex_count}/{g['value']} codex entries)"
            if g["type"] == "avg_resonance":
                return f"Nurture the soil... (field resonance {avg_resonance:.2f}/{g['value']})"
        return {
            "terminal": "Check the habitat terminal.",
            "talk_sylla": "Talk to Dr. Sylla Veen.",
            "talk_care7": "Talk to CARE-7.",
            "great_crystal_night": "Visit the great crystal at night.",
        }[step["trigger"]]

    def to_dict(self) -> dict[str, Any]:
        return {"completed": self.completed, "total_harvests": self.total_harvests}

    def from_dict(self, d: dict[str, Any]) -> None:
        self.completed = list(d["completed"])
        self.total_harvests = d["total_harvests"]
