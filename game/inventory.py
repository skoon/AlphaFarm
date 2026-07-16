"""Stackable grid inventory, credits, and the overnight shipping bin."""
from __future__ import annotations

from typing import Any

from game.crops import CropDefs


class Inventory:
    def __init__(self, cfg: dict[str, Any]):
        inv = cfg["inventory"]
        self.size: int = inv["slots"]
        self.max_stack: int = inv["max_stack"]
        self.slots: list[dict[str, Any] | None] = [None] * self.size

    def add(self, item_id: str, qty: int = 1) -> int:
        """Add items, stacking first. Returns leftover that did not fit."""
        for slot in self.slots:
            if qty <= 0:
                break
            if slot and slot["id"] == item_id and slot["qty"] < self.max_stack:
                take = min(qty, self.max_stack - slot["qty"])
                slot["qty"] += take
                qty -= take
        for i, slot in enumerate(self.slots):
            if qty <= 0:
                break
            if slot is None:
                take = min(qty, self.max_stack)
                self.slots[i] = {"id": item_id, "qty": take}
                qty -= take
        return qty

    def remove(self, item_id: str, qty: int = 1) -> bool:
        if self.count(item_id) < qty:
            return False
        for i, slot in enumerate(self.slots):
            if qty <= 0:
                break
            if slot and slot["id"] == item_id:
                take = min(qty, slot["qty"])
                slot["qty"] -= take
                qty -= take
                if slot["qty"] == 0:
                    self.slots[i] = None
        return True

    def count(self, item_id: str) -> int:
        return sum(s["qty"] for s in self.slots if s and s["id"] == item_id)

    def items(self) -> list[dict[str, Any]]:
        return [s for s in self.slots if s]

    def seed_ids_held(self) -> list[str]:
        seen: list[str] = []
        for s in self.slots:
            if s and s["id"].startswith("seed:"):
                cid = s["id"][len("seed:"):]
                if cid not in seen:
                    seen.append(cid)
        return seen

    def to_dict(self) -> dict[str, Any]:
        return {"slots": self.slots}

    def from_dict(self, d: dict[str, Any]) -> None:
        self.slots = list(d["slots"]) + [None] * (self.size - len(d["slots"]))


class ShippingBin:
    """Crops dropped here convert to credits overnight."""

    def __init__(self) -> None:
        self.contents: dict[str, int] = {}

    def add(self, item_id: str, qty: int = 1) -> None:
        self.contents[item_id] = self.contents.get(item_id, 0) + qty

    def process_overnight(self, defs: CropDefs) -> int:
        total = sum(defs.sale_value(item) * qty for item, qty in self.contents.items())
        self.contents = {}
        return total

    def to_dict(self) -> dict[str, Any]:
        return {"contents": self.contents}

    def from_dict(self, d: dict[str, Any]) -> None:
        self.contents = dict(d["contents"])
