"""Wild alien flora: daily spawning, the scanner, and the discovery codex."""
from __future__ import annotations

import random
from typing import Any

from game.config import load_json


class FloraSystem:
    def __init__(self, cfg: dict[str, Any], data: dict[str, Any] | None = None):
        self.cfg = cfg["flora"]
        d = data if data is not None else load_json("wild_flora.json")
        self.sets: dict[str, Any] = d["sets"]
        self.species: dict[str, Any] = d["species"]
        self.wild: list[dict[str, Any]] = []      # [{"species", "x", "y"}]
        self.codex: list[str] = []                # scanned species ids, in scan order

    # ---- spawning --------------------------------------------------------

    def _near_crystal(self, world, x: int, y: int, radius: int = 4) -> bool:
        for cx, cy in world.find_kind("crystal") + world.find_kind("great_crystal"):
            if abs(cx - x) <= radius and abs(cy - y) <= radius:
                return True
        return False

    def _occupied(self, x: int, y: int) -> bool:
        return any(w["x"] == x and w["y"] == y for w in self.wild)

    def daily_spawn(self, world, moons, day: int, rng: random.Random) -> None:
        for _ in range(self.cfg["daily_spawn_attempts"]):
            if len(self.wild) >= self.cfg["max_wild_plants"]:
                return
            x = rng.randrange(world.width)
            y = rng.randrange(world.height)
            t = world.tile(x, y)
            if t is None or t.kind != "grass" or self._occupied(x, y):
                continue
            candidates = []
            for sid, s in self.species.items():
                if s["set"] == "crystal" and not self._near_crystal(world, x, y):
                    continue
                if sid == "sleeper_bell" and not moons.both_dark(day):
                    continue
                candidates.append(sid)
            if candidates:
                self.wild.append({"species": rng.choice(candidates), "x": x, "y": y})

    # ---- scanning --------------------------------------------------------

    def plant_at(self, x: int, y: int) -> dict[str, Any] | None:
        for w in self.wild:
            if w["x"] == x and w["y"] == y:
                return w
        return None

    def scan(self, x: int, y: int) -> tuple[str, bool] | None:
        """Scan the plant at (x, y). Returns (species_id, newly_documented) or None."""
        w = self.plant_at(x, y)
        if w is None:
            return None
        sid = w["species"]
        self.wild.remove(w)
        new = sid not in self.codex
        if new:
            self.codex.append(sid)
        return sid, new

    # ---- codex sets / unlocks ---------------------------------------------

    def set_species(self, set_id: str) -> list[str]:
        return [sid for sid, s in self.species.items() if s["set"] == set_id]

    def set_complete(self, set_id: str) -> bool:
        return all(sid in self.codex for sid in self.set_species(set_id))

    def unlocked_seed_crops(self) -> list[str]:
        out = []
        for set_id, s in self.sets.items():
            if s["unlock_seed"] and self.set_complete(set_id):
                out.append(s["unlock_seed"])
        return out

    def to_dict(self) -> dict[str, Any]:
        return {"wild": self.wild, "codex": self.codex}

    def from_dict(self, d: dict[str, Any]) -> None:
        self.wild = list(d["wild"])
        self.codex = list(d["codex"])
