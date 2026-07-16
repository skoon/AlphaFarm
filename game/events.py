"""Atmospheric events: spore drifts, ion storms, aurora nights — with next-day forecast."""
from __future__ import annotations

import random
from typing import Any

EVENT_NAMES = {
    "none": "Clear skies",
    "spore_drift": "Spore drift",
    "ion_storm": "ION STORM — take shelter!",
    "aurora": "Aurora night",
}


class EventSystem:
    def __init__(self, cfg: dict[str, Any], rng: random.Random):
        self.cfg = cfg["events"]
        self.today: str = "none"
        self.forecast: str = self._roll(rng)

    def _roll(self, rng: random.Random) -> str:
        weights = self.cfg["weights"]
        ids = list(weights.keys())
        return rng.choices(ids, weights=[weights[i] for i in ids], k=1)[0]

    def advance_day(self, rng: random.Random) -> None:
        self.today = self.forecast
        self.forecast = self._roll(rng)

    def apply_morning(self, world, rng: random.Random) -> int:
        """Spore drift auto-fertilizes random planted tiles. Returns tiles affected."""
        if self.today != "spore_drift":
            return 0
        planted = [(x, y, t) for x, y, t in world.iter_tiles() if t.crop and not t.crop.wilted]
        rng.shuffle(planted)
        hit = planted[: self.cfg["spore_drift_tiles"]]
        for _, _, t in hit:
            t.crop.fertilize(0.5)
            t.watered = True
        return len(hit)

    def ion_storm_active(self, hour: float) -> bool:
        return (self.today == "ion_storm"
                and self.cfg["ion_storm_start_hour"] <= hour < self.cfg["ion_storm_end_hour"])

    def growth_multiplier(self) -> float:
        return self.cfg["aurora_growth_multiplier"] if self.today == "aurora" else 1.0

    def today_name(self) -> str:
        return EVENT_NAMES[self.today]

    def forecast_name(self) -> str:
        return EVENT_NAMES[self.forecast]

    def to_dict(self) -> dict[str, Any]:
        return {"today": self.today, "forecast": self.forecast}

    def from_dict(self, d: dict[str, Any]) -> None:
        self.today = d["today"]
        self.forecast = d["forecast"]
