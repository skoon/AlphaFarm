"""Veridian fauna: skittish critters that wander the farm at night and the mine,
scannable into their own discovery codex."""
from __future__ import annotations

import math
import random
from typing import Any

from game.config import load_json

MAX_PER_MAP = 4
NIGHT_HOUR = 20.0          # farm critters only emerge at/after this hour
WANDER_SPEED = 1.1         # tiles/sec, gentle drift
FLEE_MULT = 3.0            # skittish dart is this much faster
FLEE_RANGE = 3.0           # tiles: player this close spooks a critter
FLEE_TIME = 0.7            # seconds a critter keeps darting after a scare
SPAWN_MIN_PLAYER_DIST = 6.0
SCAN_RANGE = 0.75          # tiles from the target tile centre
_HABITAT_MAP = {"farm_night": "farm", "mine": "mine"}


class FaunaSystem:
    def __init__(self, data: dict[str, Any] | None = None):
        d = data if data is not None else load_json("fauna.json")
        self.set_name: str = d["set_name"]
        self.reward_seed: str = d["reward_seed"]
        self.reward_count: int = d["reward_count"]
        self.species: dict[str, Any] = d["species"]
        self.critters: list[dict[str, Any]] = []   # transient, never saved
        self.codex: list[str] = []                  # scanned species ids, in order
        self.reward_claimed: bool = False

    # ---- populations -----------------------------------------------------

    def _species_for_map(self, map_id: str) -> list[str]:
        return [sid for sid, s in self.species.items()
                if _HABITAT_MAP.get(s["habitat"]) == map_id]

    def _count(self, map_id: str) -> int:
        return sum(1 for c in self.critters if c["map"] == map_id)

    def _spawn_one(self, map_id: str, world, player_pos, rng: random.Random) -> None:
        ids = self._species_for_map(map_id)
        if not ids:
            return
        for _ in range(30):
            x = rng.randrange(world.width)
            y = rng.randrange(world.height)
            if world.is_solid(x, y):
                continue
            cx, cy = x + 0.5, y + 0.5
            if player_pos is not None:
                if math.hypot(cx - player_pos[0], cy - player_pos[1]) < SPAWN_MIN_PLAYER_DIST:
                    continue
            ang = rng.uniform(0, math.tau)
            self.critters.append({
                "species": rng.choice(ids), "map": map_id, "x": cx, "y": cy,
                "vx": math.cos(ang) * WANDER_SPEED, "vy": math.sin(ang) * WANDER_SPEED,
                "shy_t": 0.0,
            })
            return

    def update(self, dt: float, worlds: dict, map_id: str,
               player_pos: tuple[float, float], hour: float, rng: random.Random) -> None:
        is_night = hour >= NIGHT_HOUR
        # farm critters are creatures of the night; at day they slip away
        if not is_night:
            self.critters = [c for c in self.critters if c["map"] != "farm"]

        for m, allowed in (("farm", is_night), ("mine", True)):
            world = worlds.get(m)
            if not allowed or world is None:
                continue
            here = player_pos if map_id == m else None
            while self._count(m) < MAX_PER_MAP:
                before = self._count(m)
                self._spawn_one(m, world, here, rng)
                if self._count(m) == before:
                    break   # no room found this frame; try again later

        for c in self.critters:
            world = worlds.get(c["map"])
            if world is None:
                continue
            self._move(c, dt, world, player_pos if c["map"] == map_id else None, rng)

    def _move(self, c: dict[str, Any], dt: float, world,
              player_pos, rng: random.Random) -> None:
        c["shy_t"] = max(0.0, c["shy_t"] - dt)

        if player_pos is not None:
            dx, dy = c["x"] - player_pos[0], c["y"] - player_pos[1]
            dist = math.hypot(dx, dy)
            if dist < FLEE_RANGE:
                if dist < 1e-6:
                    ang = rng.uniform(0, math.tau)
                    dx, dy, dist = math.cos(ang), math.sin(ang), 1.0
                speed = WANDER_SPEED * FLEE_MULT
                c["vx"], c["vy"] = dx / dist * speed, dy / dist * speed
                c["shy_t"] = FLEE_TIME

        if c["shy_t"] <= 0.0:   # gentle wander: occasionally pick a new heading
            mag = math.hypot(c["vx"], c["vy"])
            if rng.random() < dt * 0.5 or mag < 1e-6 or mag > WANDER_SPEED * 1.1:
                ang = rng.uniform(0, math.tau)
                c["vx"] = math.cos(ang) * WANDER_SPEED
                c["vy"] = math.sin(ang) * WANDER_SPEED

        nx = c["x"] + c["vx"] * dt
        if not world.is_solid(int(nx), int(c["y"])):
            c["x"] = nx
        else:
            c["vx"] = -c["vx"]
        ny = c["y"] + c["vy"] * dt
        if not world.is_solid(int(c["x"]), int(ny)):
            c["y"] = ny
        else:
            c["vy"] = -c["vy"]

        c["x"] = min(max(c["x"], 0.5), world.width - 0.5)
        c["y"] = min(max(c["y"], 0.5), world.height - 0.5)

    # ---- scanning --------------------------------------------------------

    def scan(self, map_id: str, tx: int, ty: int) -> tuple[str, bool] | None:
        """Document the nearest critter within range of (tx, ty). It darts away
        rather than being captured, so it stays in the world."""
        target = (tx + 0.5, ty + 0.5)
        best: dict[str, Any] | None = None
        best_d = SCAN_RANGE
        for c in self.critters:
            if c["map"] != map_id:
                continue
            d = math.hypot(c["x"] - target[0], c["y"] - target[1])
            if d <= best_d:
                best, best_d = c, d
        if best is None:
            return None
        dx, dy = best["x"] - target[0], best["y"] - target[1]
        dist = math.hypot(dx, dy) or 1.0
        speed = WANDER_SPEED * FLEE_MULT
        best["vx"], best["vy"] = dx / dist * speed, dy / dist * speed
        best["shy_t"] = FLEE_TIME
        sid = best["species"]
        new = sid not in self.codex
        if new:
            self.codex.append(sid)
        return sid, new

    # ---- codex / reward --------------------------------------------------

    def set_complete(self) -> bool:
        return all(sid in self.codex for sid in self.species)

    def claim_reward(self) -> tuple[str, int] | None:
        """Return (seed_id, count) exactly once, when the set is first completed."""
        if self.set_complete() and not self.reward_claimed:
            self.reward_claimed = True
            return self.reward_seed, self.reward_count
        return None

    def to_dict(self) -> dict[str, Any]:
        return {"codex": self.codex, "reward_claimed": self.reward_claimed}

    def from_dict(self, d: dict[str, Any]) -> None:
        self.codex = list(d.get("codex", []))
        self.reward_claimed = bool(d.get("reward_claimed", False))
