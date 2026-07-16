"""Game clock (day/night cycle) and the twin moons of Veridia."""
from __future__ import annotations

from typing import Any

PHASE_NAMES = [
    "New", "Waxing Crescent", "First Quarter", "Waxing Gibbous",
    "Full", "Waning Gibbous", "Last Quarter", "Waning Crescent",
]


class GameClock:
    """Tracks the in-game day and hour. Hours run day_start..day_end (e.g. 6.0..26.0,
    where 25.5 renders as 01:30). One full day spans day_length_real_seconds."""

    def __init__(self, cfg: dict[str, Any]):
        t = cfg["time"]
        self.day_start: float = t["day_start_hour"]
        self.day_end: float = t["day_end_hour"]
        self.night_start: float = t["night_start_hour"]
        self.night_full: float = t["night_full_hour"]
        self.max_darkness: int = t["max_night_darkness"]
        self.hours_per_real_second: float = (
            (self.day_end - self.day_start) / t["day_length_real_seconds"]
        )
        self.day: int = 1
        self.hour: float = self.day_start

    def update(self, dt: float) -> bool:
        """Advance by dt real seconds. Returns True when the day is over (collapse time)."""
        self.hour += dt * self.hours_per_real_second
        return self.hour >= self.day_end

    def skip_hours(self, hours: float) -> bool:
        self.hour = min(self.hour + hours, self.day_end)
        return self.hour >= self.day_end

    def start_new_day(self) -> None:
        self.day += 1
        self.hour = self.day_start

    @property
    def is_night(self) -> bool:
        return self.hour >= self.night_start

    def darkness(self) -> int:
        """Night overlay alpha, 0..max_darkness. Never fully dark (bioluminescence)."""
        if self.hour <= self.night_start:
            return 0
        span = self.night_full - self.night_start
        frac = min((self.hour - self.night_start) / span, 1.0)
        return int(self.max_darkness * frac)

    def clock_text(self) -> str:
        h = self.hour % 24.0
        return f"{int(h):02d}:{int((h % 1.0) * 60):02d}"

    def to_dict(self) -> dict[str, Any]:
        return {"day": self.day, "hour": self.hour}

    def from_dict(self, d: dict[str, Any]) -> None:
        self.day = d["day"]
        self.hour = d["hour"]


class Moons:
    """Ilo and Vesk, each on an independent 8-day phase cycle."""

    def __init__(self, cfg: dict[str, Any]):
        m = cfg["moons"]
        self.cycle: int = m["cycle_days"]
        self.full_index: int = m["full_phase_index"]
        self.dark_phases: set[int] = set(m["dark_phases"])
        self.starts = {"ilo": m["ilo_start_phase"], "vesk": m["vesk_start_phase"]}

    def phase(self, moon: str, day: int) -> int:
        return (self.starts[moon] + (day - 1)) % self.cycle

    def phase_name(self, moon: str, day: int) -> str:
        return PHASE_NAMES[self.phase(moon, day)]

    def is_full(self, moon: str, day: int) -> bool:
        return self.phase(moon, day) == self.full_index

    def both_dark(self, day: int) -> bool:
        """True on the dim nights when both moons sit near new phase."""
        return (self.phase("ilo", day) in self.dark_phases
                and self.phase("vesk", day) in self.dark_phases)
