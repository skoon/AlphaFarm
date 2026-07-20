"""Post-questline endgame: offer bundles at the great crystal for permanent buffs."""
from __future__ import annotations

from typing import Any

from game.config import load_json
from game.crops import MUT_SUFFIX

MUTATED_NEED = "mutated:any"


class RestorationSystem:
    def __init__(self, data: dict[str, Any] | None = None):
        d = data if data is not None else load_json("restoration.json")
        self.bundles: dict[str, Any] = d["bundles"]
        self.completed: list[str] = []

    # ---- queries ---------------------------------------------------------

    def available(self, quest_finished: bool) -> list[str]:
        if not quest_finished:
            return []
        return [bid for bid in self.bundles if bid not in self.completed]

    @staticmethod
    def _count(inventory, need_id: str) -> int:
        if need_id == MUTATED_NEED:
            return sum(s["qty"] for s in inventory.items()
                       if s["id"].startswith("crop:") and s["id"].endswith(MUT_SUFFIX))
        return inventory.count(need_id)

    def needs_status(self, bundle_id: str, inventory) -> list[tuple[str, int, int]]:
        """[(need_id, have, need)] for UI display."""
        return [(need_id, self._count(inventory, need_id), qty)
                for need_id, qty in self.bundles[bundle_id]["needs"].items()]

    def can_offer(self, bundle_id: str, inventory) -> bool:
        return bundle_id not in self.completed and \
            all(have >= need for _, have, need in self.needs_status(bundle_id, inventory))

    def all_complete(self) -> bool:
        return set(self.bundles) <= set(self.completed)

    # ---- actions ---------------------------------------------------------

    def offer(self, bundle_id: str, inventory) -> dict[str, Any] | None:
        """Consume the bundle's items. Returns the bundle def on success."""
        if not self.can_offer(bundle_id, inventory):
            return None
        for need_id, qty in self.bundles[bundle_id]["needs"].items():
            if need_id == MUTATED_NEED:
                remaining = qty
                for slot in list(inventory.items()):
                    if remaining <= 0:
                        break
                    if slot["id"].startswith("crop:") and slot["id"].endswith(MUT_SUFFIX):
                        take = min(remaining, slot["qty"])
                        inventory.remove(slot["id"], take)
                        remaining -= take
            else:
                inventory.remove(need_id, qty)
        self.completed.append(bundle_id)
        return self.bundles[bundle_id]

    def buff(self, buff_type: str, default: float = 0.0) -> float:
        """Sum of a buff type across completed bundles."""
        total = default
        for bid in self.completed:
            b = self.bundles[bid]["buff"]
            if b["type"] == buff_type:
                total += b["value"]
        return total

    # ---- persistence -----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {"completed": self.completed}

    def from_dict(self, d: dict[str, Any]) -> None:
        self.completed = list(d["completed"])
