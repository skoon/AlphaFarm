"""Outpost NPCs: schedules with pathfinding, friendship, contextual dialogue,
gifts, heart events, and friendship perks."""
from __future__ import annotations

import math
from collections import deque
from typing import Any

from game.config import load_json

TIER_ORDER = ["acquaintance", "friend", "confidant"]


def find_path(world, start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]] | None:
    """BFS over walkable tiles. Returns tile waypoints (excluding start) or None."""
    if start == goal:
        return []
    if world.is_solid(*goal):
        return None
    prev: dict[tuple[int, int], tuple[int, int]] = {start: start}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        if cur == goal:
            path = [cur]
            while prev[path[-1]] != path[-1]:
                path.append(prev[path[-1]])
            return list(reversed(path))[1:]
        cx, cy = cur
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if (nx, ny) not in prev and not world.is_solid(nx, ny):
                prev[(nx, ny)] = cur
                queue.append((nx, ny))
    return None


def location_zone(world, x: float, y: float) -> str:
    """Rough narrative zone for dialogue conditions."""
    for gx, gy in world.find_kind("great_crystal"):
        if abs(gx - x) <= 5 and abs(gy - y) <= 5:
            return "crystal"
    if x >= 27 and y >= 20:
        return "outpost"
    if x <= 26 and 8 <= y <= 20:
        return "farm"
    return "wild"


def line_matches(entry: Any, ctx: dict[str, Any]) -> bool:
    if not isinstance(entry, dict):
        return False
    when = entry.get("when", {})
    if "event" in when and when["event"] != ctx.get("event"):
        return False
    if "moon" in when and when["moon"] not in ctx.get("moons", set()):
        return False
    if "location" in when and when["location"] != ctx.get("location"):
        return False
    if "min_quest" in when and when["min_quest"] not in ctx.get("quests", set()):
        return False
    return True


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
        self.seen_events: list[str] = []
        self.hidden: bool = False      # indoors (night / sheltering)
        self.emote: str | None = None
        self.moving: bool = False
        self._path: list[tuple[int, int]] | None = None
        self._path_goal: tuple[int, int] | None = None

    @property
    def name(self) -> str:
        return self.d["name"]

    @property
    def home(self) -> tuple[int, int]:
        wp = self.d["schedule"][-1]
        return wp["x"], wp["y"]

    def tier(self) -> str:
        best = TIER_ORDER[0]
        for t in TIER_ORDER:
            if self.friendship >= self.cfg["tier_thresholds"][t]:
                best = t
        return best

    def hearts(self) -> int:
        return self.friendship // self.cfg["points_per_heart"]

    def has_perk(self) -> bool:
        threshold = self.cfg["perk_thresholds"].get(self.id)
        return threshold is not None and self.friendship >= threshold

    def current_waypoint(self, hour: float) -> dict[str, Any]:
        wp = self.d["schedule"][0]
        for s in self.d["schedule"]:
            if hour >= s["hour"]:
                wp = s
        return wp

    def _target_tile(self, hour: float, storm: bool) -> tuple[int, int]:
        if storm or hour >= self.cfg["night_indoors_hour"]:
            return self.home
        wp = self.current_waypoint(hour)
        return wp["x"], wp["y"]

    def update(self, hour: float, dt: float, world, storm: bool) -> None:
        goal = self._target_tile(hour, storm)
        at_home = (round(self.x), round(self.y)) == self.home and \
            math.hypot(self.x - self.home[0], self.y - self.home[1]) < 0.1
        self.hidden = at_home and (storm or hour >= self.cfg["night_indoors_hour"])

        # (re)plan when the goal changes
        if goal != self._path_goal:
            self._path_goal = goal
            self._path = find_path(world, (round(self.x), round(self.y)), goal)

        # follow the path, or fall back to a straight line
        if self._path:
            tx, ty = float(self._path[0][0]), float(self._path[0][1])
        else:
            tx, ty = float(goal[0]), float(goal[1])
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        self.moving = dist >= 0.05
        if not self.moving:
            self.x, self.y = tx, ty
            if self._path:
                self._path.pop(0)
        else:
            step = self.cfg["walk_speed_tiles_per_sec"] * dt
            if step >= dist:
                self.x, self.y = tx, ty
            else:
                self.x += dx / dist * step
                self.y += dy / dist * step

        # emotes (chat ".." is set by the manager after all updates)
        if storm and not self.hidden:
            self.emote = "!"
        elif hour >= self.cfg["night_indoors_hour"] - 0.5 and at_home and not self.hidden:
            self.emote = "z"
        elif self.moving and (int(hour * 4) + hash(self.id)) % 5 == 0:
            self.emote = "~"
        else:
            self.emote = None

    # ---- dialogue --------------------------------------------------------

    def talk_line(self, dialogue: dict[str, Any], day: int,
                  ctx: dict[str, Any] | None = None) -> str:
        ctx = ctx or {}
        lines = dialogue[self.id][self.tier()]
        pick = (day + self.friendship // 100)
        conditional = [e for e in lines if line_matches(e, ctx)]
        if conditional:
            entry = conditional[pick % len(conditional)]
            line = entry["text"]
        else:
            generic = [e for e in lines if not isinstance(e, dict)]
            line = generic[pick % len(generic)]
        if not self.talked_today:
            self.talked_today = True
            self.friendship = min(self.friendship + self.cfg["talk_points_per_day"],
                                  self.cfg["friendship_max"])
        return line

    def pending_heart_event(self, events_data: dict[str, Any]) -> dict[str, Any] | None:
        for ev in events_data.get(self.id, []):
            if self.hearts() >= ev["hearts"] and ev["id"] not in self.seen_events:
                return ev
        return None

    def complete_heart_event(self, ev: dict[str, Any]) -> None:
        self.seen_events.append(ev["id"])
        self.friendship = min(self.friendship + ev.get("bonus", 0),
                              self.cfg["friendship_max"])

    # ---- gifts -----------------------------------------------------------

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
                "gifted_today": self.gifted_today, "seen_events": self.seen_events}

    def apply_dict(self, d: dict[str, Any]) -> None:
        self.friendship = d["friendship"]
        self.talked_today = d["talked_today"]
        self.gifted_today = d["gifted_today"]
        self.seen_events = list(d.get("seen_events", []))


class NPCManager:
    def __init__(self, cfg: dict[str, Any], npc_data: dict[str, Any] | None = None,
                 dialogue: dict[str, Any] | None = None):
        data = npc_data if npc_data is not None else load_json("npcs.json")
        self.dialogue = dialogue if dialogue is not None else load_json("dialogue.json")
        self.npcs: dict[str, NPC] = {nid: NPC(nid, d, cfg) for nid, d in data.items()}

    def update(self, hour: float, dt: float, world, storm: bool = False) -> None:
        for npc in self.npcs.values():
            npc.update(hour, dt, world, storm)
        # idle neighbors strike up a chat
        visible = [n for n in self.npcs.values() if not n.hidden]
        for i, a in enumerate(visible):
            for b in visible[i + 1:]:
                if not a.moving and not b.moving and a.emote is None and \
                        b.emote is None and math.hypot(a.x - b.x, a.y - b.y) < 1.7:
                    a.emote = b.emote = ".."

    def npc_near(self, tx: int, ty: int) -> NPC | None:
        for npc in self.npcs.values():
            if npc.hidden:
                continue
            if abs(npc.x - tx) < 0.75 and abs(npc.y - ty) < 0.75:
                return npc
        return None

    def perk(self, npc_id: str) -> bool:
        npc = self.npcs.get(npc_id)
        return npc is not None and npc.has_perk()

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
