"""Player state: position (tile units), 4-direction movement, energy, tool targeting."""
from __future__ import annotations

from typing import Any

TOOLS = ["hoe", "water", "harvest", "scanner", "plant"]
HITBOX = 0.35  # half-width of the player's collision box, in tiles


class Player:
    def __init__(self, cfg: dict[str, Any], start: tuple[int, int]):
        p = cfg["player"]
        self.cfg = cfg
        self.x: float = start[0] + 0.5
        self.y: float = start[1] + 0.5
        self.facing: tuple[int, int] = (0, 1)
        self.speed: float = p["move_speed_tiles_per_sec"]
        self.max_energy: int = p["max_energy"]
        self.energy: float = float(self.max_energy)
        self.credits: int = p["start_credits"]
        self.tool: str = "hoe"
        self.selected_seed: str | None = None
        self.moving: bool = False  # drives walk animation; not persisted

    def move(self, ix: int, iy: int, dt: float, world) -> None:
        """4-direction movement with axis-separated collision; ix/iy in {-1,0,1}."""
        if ix and iy:
            iy = 0
        self.moving = bool(ix or iy)
        if ix or iy:
            self.facing = (ix, iy)
        nx = self.x + ix * self.speed * dt
        if not self._collides(nx, self.y, world):
            self.x = nx
        ny = self.y + iy * self.speed * dt
        if not self._collides(self.x, ny, world):
            self.y = ny

    def _collides(self, x: float, y: float, world) -> bool:
        for cx in (x - HITBOX, x + HITBOX):
            for cy in (y - HITBOX, y + HITBOX):
                if world.is_solid(int(cx), int(cy)):
                    return True
        return False

    def target_tile(self) -> tuple[int, int]:
        return int(self.x + self.facing[0]), int(self.y + self.facing[1])

    def standing_tile(self) -> tuple[int, int]:
        return int(self.x), int(self.y)

    def can_afford_energy(self, action: str) -> bool:
        return self.energy >= self.cfg["energy_costs"][action]

    def spend_energy(self, action: str) -> None:
        self.energy = max(0.0, self.energy - self.cfg["energy_costs"][action])

    def drain_energy(self, amount: float) -> None:
        self.energy = max(0.0, self.energy - amount)

    def rest(self, collapsed: bool) -> None:
        if collapsed:
            self.energy = self.max_energy * self.cfg["player"]["collapse_wake_energy_fraction"]
        else:
            self.energy = float(self.max_energy)

    def to_dict(self) -> dict[str, Any]:
        return {
            "x": self.x, "y": self.y, "energy": self.energy, "credits": self.credits,
            "tool": self.tool, "selected_seed": self.selected_seed,
        }

    def from_dict(self, d: dict[str, Any]) -> None:
        self.x = d["x"]
        self.y = d["y"]
        self.energy = d["energy"]
        self.credits = d["credits"]
        self.tool = d["tool"]
        self.selected_seed = d["selected_seed"]
