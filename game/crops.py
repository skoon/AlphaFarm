"""Crop definitions (from data/crops.json) and per-plant growth state."""
from __future__ import annotations

import random
from typing import Any

from game.config import load_json

# Inventory item id conventions: "seed:<crop_id>", "crop:<crop_id>", "crop:<crop_id>#mut"
MUT_SUFFIX = "#mut"


class CropDefs:
    def __init__(self, data: dict[str, Any] | None = None):
        self.defs: dict[str, Any] = data if data is not None else load_json("crops.json")

    def get(self, crop_id: str) -> dict[str, Any]:
        return self.defs[crop_id]

    def starter_ids(self) -> list[str]:
        return [cid for cid, d in self.defs.items() if d.get("unlocked_from_start")]

    def item_name(self, item_id: str) -> str:
        kind, _, rest = item_id.partition(":")
        crop_id, _, flag = rest.partition(MUT_SUFFIX[0])
        d = self.get(crop_id)
        if kind == "seed":
            return d["name"] + " Seeds"
        if item_id.endswith(MUT_SUFFIX):
            return d["mutation"]["name"]
        return d["name"]

    def sale_value(self, item_id: str) -> int:
        if not item_id.startswith("crop:"):
            return 0
        crop_id = item_id[len("crop:"):].removesuffix(MUT_SUFFIX)
        d = self.get(crop_id)
        value = d["sell_value"]
        if item_id.endswith(MUT_SUFFIX):
            value *= d["mutation"]["value_mult"]
        return value


class Crop:
    """One planted crop on one tile."""

    def __init__(self, crop_id: str, defs: CropDefs):
        self.crop_id = crop_id
        self.d = defs.get(crop_id)
        self.progress: float = 0.0        # in growth-days
        self.water_count_today: int = 0
        self.wilted: bool = False
        self.mutated: bool = False

    @property
    def growth_days(self) -> int:
        return self.d["growth_days"]

    @property
    def ripe(self) -> bool:
        return not self.wilted and self.progress >= self.growth_days

    @property
    def watered_today(self) -> bool:
        return self.water_count_today > 0

    @property
    def strict_watering(self) -> bool:
        return "strict_watering" in self.d.get("traits", [])

    def stage_frac(self) -> float:
        return min(self.progress / self.growth_days, 1.0)

    def water(self) -> None:
        self.water_count_today += 1
        # Prism Pods demand exactly one watering per day; a second one wilts them.
        if self.strict_watering and self.water_count_today > 1:
            self.wilted = True

    def fertilize(self, bonus_days: float) -> None:
        """Spore-drift growth that does not count toward strict watering."""
        if not self.wilted:
            self.progress += bonus_days

    def end_of_day(self, moon_full: bool, aurora_mult: float, rng: random.Random) -> None:
        if self.wilted:
            return
        if self.strict_watering and self.water_count_today != 1:
            self.wilted = True
            return
        if self.watered_today:
            bonus = self.d["moon_affinity"]["growth_bonus"] if moon_full else 0.0
            self.progress += (1.0 + bonus) * aurora_mult
            if moon_full and not self.mutated:
                if rng.random() < self.d["moon_affinity"]["mutation_chance"]:
                    self.mutated = True
        self.water_count_today = 0

    def harvest_item(self) -> str:
        return f"crop:{self.crop_id}" + (MUT_SUFFIX if self.mutated else "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "crop_id": self.crop_id,
            "progress": self.progress,
            "water_count_today": self.water_count_today,
            "wilted": self.wilted,
            "mutated": self.mutated,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any], defs: CropDefs) -> "Crop":
        c = cls(d["crop_id"], defs)
        c.progress = d["progress"]
        c.water_count_today = d["water_count_today"]
        c.wilted = d["wilted"]
        c.mutated = d["mutated"]
        return c
