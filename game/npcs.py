"""Outpost NPCs: daily schedules, friendship, dialogue selection, and gifts."""
from __future__ import annotations

import math
from typing import Any

from game.config import load_json

TIER_ORDER = ["acquaintance", "friend", "confidant"]


class NPC:
    def __init__(self, npc_id: str, d: dict[str, Any], cfg: dict[str, Any]):
        self.id = npc_id
        self.d = d
        self.cfg = cfg["npcs"]
        start = d["schedule"][0]
        self.x: float = float(start["x"])
        self.y: float = float(start["y"])
        self.friendship: int = 0
        self.talked_today: bool = False
        self.gifted_today: bool = False

    @property
    def name(self) -> str:
        return self.d["name"]

    def tier(self) -> str:
        best = TIER_ORDER[0]
        for t in TIER_ORDER:
            if self.friendship >= self.cfg["tier_thresholds"][t]:
                best = t
        return best

    def hearts(self) -> int:
        return self.friendship // self.cfg["points_per_heart"]

    def current_waypoint(self, hour: float) -> dict[str, Any]:
        wp = self.d["schedule"][0]
        for s in self.d["schedule"]:
            if hour >= s["hour"]:
                wp = s
        return wp

    def update(self, hour: float, dt: float) -> None:
        wp = self.current_waypoint(hour)
        tx, ty = float(wp["x"]), float(wp["y"])
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if dist < 0.05:
            self.x, self.y = tx, ty
            return
        step = self.cfg["walk_speed_tiles_per_sec"] * dt
        if step >= dist:
            self.x, self.y = tx, ty
        else:
            self.x += dx / dist * step
            self.y += dy / dist * step

    def talk_line(self, dialogue: dict[str, Any], day: int) -> str:
        lines = dialogue[self.id][self.tier()]
        line = lines[(day + self.friendship // 100) % len(lines)]
        if not self.talked_today:
            self.talked_today = True
            self.friendship = min(self.friendship + self.cfg["talk_points_per_day"],
                                  self.cfg["friendship_max"])
        return line

    def gift_reaction(self, crop_id: str) -> str:
        g = self.d["gifts"]
        if crop_id in g["loved"]:
            return "loved"
        if crop_id in g["liked"]:
            return "liked"
        if crop_id in g["disliked"]:
            return "disliked"
        return "neutral"

    def receive_gift(self, crop_id: str) -> str:
        """Returns the reaction key ('already_today' if a gift was given already)."""
        if self.gifted_today:
            return "already_today"
        self.gifted_today = True
        reaction = self.gift_reaction(crop_id)
        points = {
            "loved": self.cfg["gift_loved"],
            "liked": self.cfg["gift_liked"],
            "disliked": self.cfg["gift_disliked"],
            "neutral": self.cfg["gift_liked"] // 2,
        }[reaction]
        self.friendship = max(0, min(self.friendship + points, self.cfg["friendship_max"]))
        return reaction

    def to_dict(self) -> dict[str, Any]:
        return {"friendship": self.friendship, "talked_today": self.talked_today,
                "gifted_today": self.gifted_today}

    def apply_dict(self, d: dict[str, Any]) -> None:
        self.friendship = d["friendship"]
        self.talked_today = d["talked_today"]
        self.gifted_today = d["gifted_today"]


class NPCManager:
    def __init__(self, cfg: dict[str, Any], npc_data: dict[str, Any] | None = None,
                 dialogue: dict[str, Any] | None = None):
        data = npc_data if npc_data is not None else load_json("npcs.json")
        self.dialogue = dialogue if dialogue is not None else load_json("dialogue.json")
        self.npcs: dict[str, NPC] = {nid: NPC(nid, d, cfg) for nid, d in data.items()}

    def update(self, hour: float, dt: float) -> None:
        for npc in self.npcs.values():
            npc.update(hour, dt)

    def npc_near(self, tx: int, ty: int) -> NPC | None:
        for npc in self.npcs.values():
            if abs(npc.x - tx) < 0.75 and abs(npc.y - ty) < 0.75:
                return npc
        return None

    def end_of_day(self) -> None:
        for npc in self.npcs.values():
            npc.talked_today = False
            npc.gifted_today = False

    def gift_text(self, npc: NPC, reaction: str) -> str:
        return self.dialogue["gift_reactions"][reaction].format(name=npc.name)

    def to_dict(self) -> dict[str, Any]:
        return {nid: n.to_dict() for nid, n in self.npcs.items()}

    def from_dict(self, d: dict[str, Any]) -> None:
        for nid, nd in d.items():
            if nid in self.npcs:
                self.npcs[nid].apply_dict(nd)
