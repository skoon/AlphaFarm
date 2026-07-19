"""NPC favor requests: an occasional "bring me N of this crop" side-errand."""
from __future__ import annotations

import random
from typing import Any

from game.config import load_json
from game.crops import MUT_SUFFIX

SHORT_NAMES = {"sylla": "Sylla", "hux": "Hux", "tinks": "Tinks",
               "care7": "CARE-7", "juno": "Juno"}


class FavorSystem:
    def __init__(self, data: dict[str, Any] | None = None):
        d = data if data is not None else load_json("favors.json")
        self.chance_per_day: float = d["chance_per_day"]
        self.duration_days: int = d["duration_days"]
        self.max_active: int = d["max_active"]
        self.qty_range: tuple[int, int] = tuple(d["qty_range"])
        self.reward_credit_mult: float = d["reward_credit_mult"]
        self.reward_friendship: int = d["reward_friendship"]
        self.requests: dict[str, str] = d["requests"]
        self.thanks: dict[str, str] = d["thanks"]
        self.active: list[dict[str, Any]] = []

    def favor_for(self, npc_id: str) -> dict[str, Any] | None:
        return next((f for f in self.active if f["npc"] == npc_id), None)

    def new_day(self, day: int, npc_ids: list[str], crop_pool: list[str],
                rng: random.Random, defs) -> list[dict[str, Any]]:
        self.active = [f for f in self.active if f["expires_day"] >= day]
        created: list[dict[str, Any]] = []
        if len(self.active) < self.max_active and rng.random() < self.chance_per_day:
            available = [n for n in npc_ids if n in self.requests and self.favor_for(n) is None]
            if available and crop_pool:
                npc_id = rng.choice(available)
                crop_id = rng.choice(crop_pool)
                qty = rng.randint(*self.qty_range)
                text = self.requests[npc_id].format(qty=qty, crop=defs.get(crop_id)["name"])
                favor = {"npc": npc_id, "crop_id": crop_id, "qty": qty,
                         "expires_day": day + self.duration_days, "text": text}
                self.active.append(favor)
                created.append(favor)
        return created

    def deliver(self, npc_id: str, inventory, defs) -> dict[str, Any] | None:
        favor = self.favor_for(npc_id)
        if favor is None:
            return None
        crop_id, qty = favor["crop_id"], favor["qty"]
        plain, mutated = f"crop:{crop_id}", f"crop:{crop_id}{MUT_SUFFIX}"
        if inventory.count(plain) + inventory.count(mutated) < qty:
            return None
        take_plain = min(inventory.count(plain), qty)
        if take_plain:
            inventory.remove(plain, take_plain)
        if qty - take_plain:
            inventory.remove(mutated, qty - take_plain)
        self.active.remove(favor)
        credits = round(defs.sale_value(plain) * qty * self.reward_credit_mult)
        return {"credits": credits, "friendship": self.reward_friendship,
                "crop_name": defs.get(crop_id)["name"]}

    def describe(self, defs, day: int) -> list[str]:
        lines = []
        for f in self.active:
            name = SHORT_NAMES.get(f["npc"], f["npc"].capitalize())
            crop_name = defs.get(f["crop_id"])["name"]
            days_left = f["expires_day"] - day
            lines.append(f"{name} wants {f['qty']}x {crop_name} ({days_left} days left)")
        return lines

    def to_dict(self) -> dict[str, Any]:
        return {"active": self.active}

    def from_dict(self, d: dict[str, Any]) -> None:
        self.active = [dict(f) for f in d["active"]]
