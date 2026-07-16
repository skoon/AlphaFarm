"""Tile map, tile state (till/water/crop), and living-soil resonance."""
from __future__ import annotations

import random
from typing import Any, Iterator

from game.config import load_json
from game.crops import Crop, CropDefs

SOLID_KINDS = {"rock", "crystal", "great_crystal", "habitat_wall", "terminal",
               "shipping_pod", "building"}
INTERACT_KINDS = {"habitat_door", "terminal", "shipping_pod", "great_crystal"}


class Tile:
    def __init__(self, kind: str, resonance: float):
        self.kind = kind
        self.tilled = False
        self.watered = False           # visual wet-soil flag, cleared nightly
        self.crop: Crop | None = None
        self.resonance = resonance     # hidden living-soil value
        self.last_family: str | None = None

    @property
    def solid(self) -> bool:
        return self.kind in SOLID_KINDS

    @property
    def tillable(self) -> bool:
        return self.kind == "soil" and not self.tilled

    def to_dict(self) -> dict[str, Any]:
        return {
            "tilled": self.tilled,
            "watered": self.watered,
            "crop": self.crop.to_dict() if self.crop else None,
            "resonance": self.resonance,
            "last_family": self.last_family,
        }

    def apply_dict(self, d: dict[str, Any], defs: CropDefs) -> None:
        self.tilled = d["tilled"]
        self.watered = d["watered"]
        self.crop = Crop.from_dict(d["crop"], defs) if d["crop"] else None
        self.resonance = d["resonance"]
        self.last_family = d["last_family"]


class World:
    def __init__(self, cfg: dict[str, Any], defs: CropDefs,
                 map_data: dict[str, Any] | None = None):
        self.cfg = cfg
        self.defs = defs
        m = map_data if map_data is not None else load_json("map.json")
        self.width: int = m["width"]
        self.height: int = m["height"]
        self.legend: dict[str, str] = m["legend"]
        self.player_start: tuple[int, int] = (m["player_start"]["x"], m["player_start"]["y"])
        self.buildings: list[dict[str, Any]] = m.get("buildings", [])
        rows = m["rows"]
        assert len(rows) == self.height and all(len(r) == self.width for r in rows), \
            "map.json rows do not match declared dimensions"
        r0 = cfg["resonance"]["start"]
        self.tiles: list[list[Tile]] = [
            [Tile(self.legend[ch], r0) for ch in row] for row in rows
        ]

    def tile(self, x: int, y: int) -> Tile | None:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.tiles[y][x]
        return None

    def is_solid(self, x: int, y: int) -> bool:
        t = self.tile(x, y)
        return t is None or t.solid

    def iter_tiles(self) -> Iterator[tuple[int, int, Tile]]:
        for y in range(self.height):
            for x in range(self.width):
                yield x, y, self.tiles[y][x]

    def find_kind(self, kind: str) -> list[tuple[int, int]]:
        return [(x, y) for x, y, t in self.iter_tiles() if t.kind == kind]

    # ---- farming actions -------------------------------------------------

    def till(self, x: int, y: int) -> bool:
        t = self.tile(x, y)
        if t is None:
            return False
        if t.crop and t.crop.wilted:   # hoe clears wilted crops
            t.crop = None
            return True
        if t.tillable:
            t.tilled = True
            return True
        return False

    def plant(self, x: int, y: int, crop_id: str) -> bool:
        t = self.tile(x, y)
        if t and t.kind == "soil" and t.tilled and t.crop is None:
            t.crop = Crop(crop_id, self.defs)
            return True
        return False

    def water(self, x: int, y: int) -> bool:
        t = self.tile(x, y)
        if t and t.kind == "soil" and t.tilled:
            t.watered = True
            if t.crop:
                t.crop.water()
            return True
        return False

    def harvest(self, x: int, y: int, rng: random.Random) -> tuple[str, int] | None:
        """Returns (item_id, qty) or None. Applies resonance yield + rotation shifts."""
        t = self.tile(x, y)
        if t is None or t.crop is None:
            return None
        if t.crop.wilted:
            t.crop = None
            return None
        if not t.crop.ripe:
            return None
        rc = self.cfg["resonance"]
        qty = 2 if rng.random() < (t.resonance - 0.4) else 1
        item = t.crop.harvest_item()
        family = t.crop.d["family"]
        if t.last_family == family:
            t.resonance -= rc["same_crop_penalty"]
        else:
            t.resonance += rc["rotation_bonus"]
        t.resonance = max(rc["min"], min(rc["max"], t.resonance))
        t.last_family = family
        t.crop = None
        return item, qty

    # ---- daily tick ------------------------------------------------------

    def end_of_day(self, moons, day: int, aurora_mult: float, rng: random.Random) -> None:
        rc = self.cfg["resonance"]
        for _, _, t in self.iter_tiles():
            if t.crop:
                moon = t.crop.d["moon_affinity"]["moon"]
                t.crop.end_of_day(moons.is_full(moon, day), aurora_mult, rng)
            elif t.kind == "soil":
                # fallow ground slowly settles back toward its baseline
                base = rc["start"]
                step = rc["fallow_recovery_per_day"]
                if t.resonance < base:
                    t.resonance = min(base, t.resonance + step)
                elif t.resonance > base:
                    t.resonance = max(base, t.resonance - step)
            t.watered = False

    def avg_field_resonance(self) -> float:
        vals = [t.resonance for _, _, t in self.iter_tiles() if t.kind == "soil"]
        return sum(vals) / len(vals) if vals else 0.0

    # ---- persistence -----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        changed = {}
        for x, y, t in self.iter_tiles():
            if t.kind != "soil" and t.crop is None:
                continue
            changed[f"{x},{y}"] = t.to_dict()
        return {"tiles": changed}

    def from_dict(self, d: dict[str, Any]) -> None:
        for key, td in d["tiles"].items():
            x, y = (int(v) for v in key.split(","))
            self.tiles[y][x].apply_dict(td, self.defs)
