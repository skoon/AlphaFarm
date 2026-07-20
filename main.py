"""AlphaFarm — a cozy terraforming farm sim on the alien planet Veridia.

Run with: uv run python main.py
"""
from __future__ import annotations

import math
import random
import sys

import pygame

import game.audio as audio
from game import render
from game.assets import load_assets
from game.camera import Camera
from game.config import load_config, load_json
from game.crops import CropDefs
from game.events import EventSystem
from game.fauna import FaunaSystem
from game.favors import SHORT_NAMES, FavorSystem
from game.flora import FloraSystem
from game.inventory import Inventory, ShippingBin
from game.npcs import NPCManager
from game.particles import Particles
from game.player import Player
from game.quest import QuestSystem
from game.restoration import RestorationSystem
from game.save_load import (SLOT_COUNT, load_game, migrate_legacy, save_game,
                            slot_path, slot_summary)
from game.time_system import GameClock, Moons
from game.ui import UI
from game.world import World

MAX_DT = 0.1  # clamp frame delta so a hitch can't teleport things


PAUSE_ROWS = ["Resume", "Options", "Save", "Quit to Title", "Quit Game"]
OPTION_ROWS = ["Master", "Music", "SFX", "Back"]


class Game:
    def __init__(self, slot: int = 1) -> None:
        self.slot = slot
        self.to_title = False
        self.cfg = load_config()
        self.rng = random.Random()
        self.defs = CropDefs()
        self.items = load_json("items.json")
        self.clock = GameClock(self.cfg)
        self.moons = Moons(self.cfg)
        self.worlds = {"farm": World(self.cfg, self.defs),
                       "mine": World(self.cfg, self.defs, map_name="mine")}
        self.map_id = "farm"
        self.player = Player(self.cfg, self.world.player_start)
        self.inventory = Inventory(self.cfg)
        self.shipping_bin = ShippingBin()
        self.events = EventSystem(self.cfg, self.rng)
        self.flora = FloraSystem(self.cfg)
        self.fauna = FaunaSystem()
        self.npcs = NPCManager(self.cfg)
        self.quests = QuestSystem()
        self.favors = FavorSystem()
        self.restoration = RestorationSystem()
        self.heart_events = load_json("heart_events.json")

        ts = self.cfg["window"]["tile_size"]
        farm = self.worlds["farm"]
        self.screen_w = farm.width * ts
        self.screen_h = farm.height * ts
        self.ts = ts
        self._rebuild_view()
        self.ui = UI(self.screen_w, self.screen_h)
        walls = farm.find_kind("habitat_wall") + farm.find_kind("habitat_door")
        self.habitat_origin = (min(x for x, _ in walls), min(y for _, y in walls))

        self.mode = "play"
        self.dialogue_queue: list[tuple[str, str]] = []
        self.shop_mode = "sell"
        self.shop_index = 0
        self.upgrade_index = 0
        self.restoration_index = 0
        self.pause_index = 0
        self.option_index = 0
        self.kiln_index = 0
        self.kiln_pos: tuple[int, int] | None = None
        self.sleep_index = 0
        self.debug = False
        self.t = 0.0
        self.running = True
        self.particles = Particles()
        self.storm_flash = 0.0
        self.day_summary: dict | None = None
        self.summary_age = 0.0
        self.soil_tiles = self.world.find_kind("soil")

        if not self._load():
            self._new_game()
        self.camera.center_on(self.player.x * ts, self.player.y * ts)

    # ---- maps ---------------------------------------------------------------

    @property
    def world(self) -> World:
        return self.worlds[self.map_id]

    def _rebuild_view(self) -> None:
        w = self.world
        self.map_px = (w.width * self.ts, w.height * self.ts)
        self.world_surf = pygame.Surface(self.map_px)
        self.camera = Camera(self.cfg, *self.map_px, self.screen_w, self.screen_h)

    def _farm_spawn(self) -> tuple[int, int]:
        ex, ey = self.worlds["farm"].find_kind("mine_entrance")[0]
        return ex, ey + 1

    def switch_map(self, target: str, spawn: tuple[int, int]) -> None:
        """Move to another map, centering the player on the spawn tile so their
        collision box doesn't straddle (and snag on) an adjacent solid tile."""
        self.map_id = target
        self._rebuild_view()
        self.player.x, self.player.y = spawn[0] + 0.5, spawn[1] + 0.5
        self.particles = Particles()
        self.camera.center_on(self.player.x * self.ts, self.player.y * self.ts)

    # ---- new game / persistence -------------------------------------------

    def _new_game(self) -> None:
        for crop_id, qty in self.cfg["player"]["start_seeds"].items():
            self.inventory.add(f"seed:{crop_id}", qty)
        self.player.selected_seed = self.inventory.seed_ids_held()[0]
        self.flora.daily_spawn(self.world, self.moons, self.clock.day, self.rng)
        self.ui.toast("Welcome to Veridia. Till, plant, water — and listen.")
        self.ui.toast("Press ? for controls.")

    def gather_state(self) -> dict:
        return {
            "clock": self.clock.to_dict(),
            "player": self.player.to_dict(),
            "inventory": self.inventory.to_dict(),
            "shipping_bin": self.shipping_bin.to_dict(),
            "world": self.worlds["farm"].to_dict(),
            "mine_world": self.worlds["mine"].to_dict(),
            "map_id": self.map_id,
            "events": self.events.to_dict(),
            "flora": self.flora.to_dict(),
            "fauna": self.fauna.to_dict(),
            "npcs": self.npcs.to_dict(),
            "quests": self.quests.to_dict(),
            "favors": self.favors.to_dict(),
            "restoration": self.restoration.to_dict(),
        }

    def _load(self) -> bool:
        state = load_game(slot_path(self.slot))
        if state is None:
            return False
        self.clock.from_dict(state["clock"])
        self.player.from_dict(state["player"])
        if "pack" in self.player.upgrades:
            self.inventory.expand(12)
        self.inventory.from_dict(state["inventory"])
        self.shipping_bin.from_dict(state["shipping_bin"])
        self.worlds["farm"].from_dict(state["world"])
        if state.get("mine_world"):
            self.worlds["mine"].from_dict(state["mine_world"])
        self.map_id = state.get("map_id", "farm")
        if self.map_id != "farm":
            self._rebuild_view()
        self.events.from_dict(state["events"])
        self.flora.from_dict(state["flora"])
        if state.get("fauna"):
            self.fauna.from_dict(state["fauna"])
        self.npcs.from_dict(state["npcs"])
        self.quests.from_dict(state["quests"])
        if state.get("favors"):
            self.favors.from_dict(state["favors"])
        if state.get("restoration"):
            self.restoration.from_dict(state["restoration"])
        self._apply_restoration_buffs()
        self.ui.toast(f"Save loaded — day {self.clock.day}.")
        return True

    def _apply_restoration_buffs(self) -> None:
        base = self.cfg["player"]["max_energy"]
        self.player.max_energy = base + self.restoration.buff("energy_max")
        self.events.aurora_bonus = self.restoration.buff("aurora_weight")

    def save(self) -> None:
        save_game(self.gather_state(), slot_path(self.slot))

    # ---- helpers -------------------------------------------------------------

    def say(self, speaker: str, text: str, portrait: str | None = None) -> None:
        self.dialogue_queue.append((speaker, text, portrait))
        self.mode = "dialogue"

    def _dialogue_ctx(self, npc) -> dict:
        from game.npcs import location_zone
        day = self.clock.day
        moons = set()
        if self.moons.is_full("ilo", day):
            moons.add("ilo:full")
        if self.moons.is_full("vesk", day):
            moons.add("vesk:full")
        if self.moons.both_dark(day):
            moons.add("both:dark")
        return {"event": self.events.today, "moons": moons,
                "location": location_zone(self.world, npc.x, npc.y),
                "quests": set(self.quests.completed)}

    def _soil_report(self) -> str:
        rows: dict[int, list[float]] = {}
        for x, y, t in self.world.iter_tiles():
            if t.kind == "soil":
                rows.setdefault(y, []).append(t.resonance)
        ranked = sorted((sum(v) / len(v), y) for y, v in rows.items())
        worst = ", ".join(str(y) for _, y in ranked[:2])
        best = ranked[-1][1]
        return (f"'Field scan: rows {worst} are sulking — rotate crop families there. "
                f"Row {best} is singing. Average resonance "
                f"{self.world.avg_field_resonance():.2f}.'")

    def tool_label(self) -> str:
        name = self.items["tools"][self.player.tool]["name"]
        if self.player.tool == "plant":
            seed = self.player.selected_seed
            if seed and seed.startswith("gear:"):
                return f"Placer: {self.defs.item_name(seed)} (x{self.inventory.count(seed)})"
            if seed:
                have = self.inventory.count(f"seed:{seed}")
                return f"{name}: {self.defs.get(seed)['name']} (x{have})"
            return f"{name}: no seeds"
        upgrade = {"hoe": "hoe2", "water": "canister2"}.get(self.player.tool)
        if upgrade and upgrade in self.player.upgrades:
            return name + " Mk-II"
        return name

    def seed_price(self, crop_id: str) -> int:
        price = self.defs.get(crop_id)["seed_price"]
        if self.npcs.perk("tinks"):
            price = int(round(price * (1 - self.cfg["npcs"]["tinks_seed_discount"])))
        return price

    def _row_targets(self, tx: int, ty: int, upgrade: str) -> list[tuple[int, int]]:
        """Target tile, widened to a facing-perpendicular row with the Mk-II tools."""
        tiles = [(tx, ty)]
        if upgrade in self.player.upgrades:
            fx, fy = self.player.facing
            px, py = abs(fy), abs(fx)
            tiles += [(tx + px, ty + py), (tx - px, ty - py)]
        return tiles

    def cycle_seed(self) -> None:
        held: list[str] = self.inventory.seed_ids_held()
        held += [f"gear:{g}" for g in ("drone", "kiln")
                 if self.inventory.count(f"gear:{g}") > 0]
        if not held:
            self.player.selected_seed = None
            self.ui.toast("No seeds in inventory.")
            return
        cur = self.player.selected_seed
        idx = (held.index(cur) + 1) % len(held) if cur in held else 0
        sel = held[idx]
        self.player.selected_seed = sel
        if sel.startswith("gear:"):
            self.ui.toast(f"Placer: {self.defs.item_name(sel)}")
        else:
            self.ui.toast(f"Seed: {self.defs.get(sel)['name']}")

    def shop_rows(self) -> list[dict]:
        rows = []
        if self.shop_mode == "sell":
            for s in self.inventory.items():
                if s["id"].startswith(("crop:", "good:", "mineral:")):
                    value = self.defs.sale_value(s["id"])
                    rows.append({"id": s["id"], "qty": s["qty"],
                                 "label": f"{self.defs.item_name(s['id'])} x{s['qty']}"
                                          f" — {value} cr each"})
        else:
            unlocked = set(self.defs.starter_ids()) | set(self.flora.unlocked_seed_crops())
            discount = " [Tinks' rate]" if self.npcs.perk("tinks") else ""
            for cid in self.defs.defs:
                d = self.defs.get(cid)
                if cid in unlocked and d["seed_price"] > 0:
                    rows.append({"id": cid,
                                 "label": f"{d['name']} Seeds — {self.seed_price(cid)} cr"
                                          f"{discount} (grows in {d['growth_days']}d,"
                                          f" sells {d['sell_value']} cr)"})
        return rows

    # ---- actions ---------------------------------------------------------------

    def use_tool(self) -> None:
        tool = self.player.tool
        tx, ty = self.player.target_tile()
        cost_key = {"hoe": "hoe", "water": "water", "harvest": "harvest",
                    "scanner": "scan", "plant": "plant"}[tool]
        if not self.player.can_afford_energy(cost_key):
            self.ui.toast("Too exhausted. Sleep it off.")
            return
        self.player.swing_t = 0.18
        wx, wy = tx * self.ts + self.ts // 2, ty * self.ts + self.ts // 2

        ore_tile = self.world.tile(tx, ty)
        if tool == "hoe" and ore_tile is not None and ore_tile.kind.startswith("ore_"):
            if not self.player.can_afford_energy("mine"):
                self.ui.toast("Too exhausted to swing at rock.")
                return
            self.player.spend_energy("mine")
            self.particles.burst("soil", wx, wy, self.rng)
            audio.play("hoe")
            result = self.world.mine_ore(tx, ty, self.rng)
            if result:
                mineral, qty = result
                item = f"mineral:{mineral}"
                leftover = self.inventory.add(item, qty)
                self.particles.burst("sparkle", wx, wy, self.rng)
                audio.play("harvest")
                self.particles.float_text(f"+{qty - leftover} {self.defs.item_name(item)}",
                                          wx, wy - 6)
                if leftover:
                    self.ui.toast(f"Inventory full! Lost {leftover} "
                                  f"{self.defs.item_name(item)}.")
            return

        if tool == "hoe":
            gear = self.world.remove_gear(tx, ty)
            if gear:
                if gear.get("crop_id"):
                    self.inventory.add(f"crop:{gear['crop_id']}", 1)
                self.inventory.add(f"gear:{gear['kind']}", 1)
                self.ui.toast(f"Packed up the {self.defs.item_name('gear:' + gear['kind'])}.")
                audio.play("blip")
                return
            hit = False
            for hx, hy in self._row_targets(tx, ty, "hoe2"):
                if self.world.till(hx, hy):
                    hit = True
                    self.particles.burst("soil", hx * self.ts + self.ts // 2,
                                         hy * self.ts + self.ts // 2, self.rng)
            if hit:
                self.player.spend_energy("hoe")
                audio.play("hoe")
        elif tool == "water":
            hit = False
            for hx, hy in self._row_targets(tx, ty, "canister2"):
                tile = self.world.tile(hx, hy)
                if self.world.water(hx, hy):
                    hit = True
                    self.particles.burst("water", hx * self.ts + self.ts // 2,
                                         hy * self.ts + self.ts // 2, self.rng)
                    if tile and tile.crop and tile.crop.wilted:
                        self.ui.toast("The Prism Pod wilted — it wanted exactly one watering!")
            if hit:
                self.player.spend_energy("water")
                audio.play("water")
        elif tool == "harvest":
            result = self.world.harvest(tx, ty, self.rng)
            if result:
                item, qty = result
                self.player.spend_energy("harvest")
                leftover = self.inventory.add(item, qty)
                self.quests.total_harvests += qty - leftover
                name = self.defs.item_name(item)
                self.particles.burst("sparkle", wx, wy, self.rng)
                self.particles.float_text(f"+{qty - leftover} {name}", wx, wy - 6)
                audio.play("harvest")
                if leftover:
                    self.ui.toast(f"Inventory full! Lost {leftover} {name}.")
                if qty - leftover > 1:
                    self.ui.toast("Double harvest — the soil sings!")
        elif tool == "scanner":
            fauna_hit = self.fauna.scan(self.map_id, tx, ty)
            if fauna_hit is not None:
                self.player.spend_energy("scan")
                self.particles.burst("sparkle", wx, wy, self.rng, n=6)
                audio.play("blip")
                fsid, fnew = fauna_hit
                fsp = self.fauna.species[fsid]
                if fnew:
                    self.ui.toast(f"Documented: {fsp['name']}!")
                    if self.fauna.set_complete():
                        reward = self.fauna.claim_reward()
                        if reward:
                            seed_id, count = reward
                            self.inventory.add(f"seed:{seed_id}", count)
                            self.say("VERIDIA",
                                     f"The {self.fauna.set_name} codex is complete. The "
                                     f"planet stirs, grateful, and lets {count} "
                                     f"{self.defs.get(seed_id)['name']} seeds fall into "
                                     "your pack — dreams to plant of your own.")
                else:
                    self.ui.toast(f"Another {fsp['name']} — it darts away.")
                return
            if self.map_id != "farm":
                self.ui.toast("Scanner: nothing to document down here.")
                return
            hit = self.flora.scan(tx, ty)
            if hit is None:
                self.ui.toast("Scanner: no undocumented flora there.")
                return
            self.player.spend_energy("scan")
            self.particles.burst("sparkle", wx, wy, self.rng, n=6)
            audio.play("blip")
            sid, new = hit
            sp = self.flora.species[sid]
            if new:
                self.ui.toast(f"Documented: {sp['name']}!")
                set_id = sp["set"]
                if self.flora.set_complete(set_id):
                    unlock = self.flora.sets[set_id]["unlock_seed"]
                    msg = f"Codex set complete: {self.flora.sets[set_id]['name']}!"
                    if unlock:
                        msg += f" {self.defs.get(unlock)['name']} seeds now for sale."
                    self.say("Codex", msg)
            else:
                self.ui.toast(f"Sampled another {sp['name']}.")
        elif tool == "plant":
            seed = self.player.selected_seed
            item = seed if (seed or "").startswith("gear:") else f"seed:{seed}"
            if not seed or self.inventory.count(item) == 0:
                self.ui.toast("Nothing selected to plant — press Tab.")
                return
            if seed.startswith("gear:"):
                kind = seed[len("gear:"):]
                if self.world.place_gear(tx, ty, kind):
                    self.inventory.remove(item, 1)
                    self.player.spend_energy("plant")
                    self.particles.burst("soil", wx, wy, self.rng, n=4)
                    audio.play("plant")
                    if self.inventory.count(item) == 0:
                        self.cycle_seed()
                else:
                    spot = "tilled, empty soil" if kind == "drone" else "open grass"
                    self.ui.toast(f"The {self.defs.item_name(item)} needs {spot}.")
                return
            if self.world.plant(tx, ty, seed):
                self.inventory.remove(f"seed:{seed}", 1)
                self.player.spend_energy("plant")
                self.particles.burst("soil", wx, wy, self.rng, n=4)
                audio.play("plant")

    def interact(self) -> None:
        tx, ty = self.player.target_tile()
        npc = self.npcs.npc_near(tx, ty) if self.map_id == "farm" else None
        if npc:
            trigger = f"talk_{npc.id}"
            step = self.quests.try_trigger(trigger,
                                           len(self.flora.codex) + len(self.fauna.codex),
                                           self.world.avg_field_resonance(),
                                           self.clock.is_night)
            if step:
                self._fire_quest_step(step, npc.name)
                return
            label = f"{npc.name} ({npc.hearts_label()})"
            ev = npc.pending_heart_event(self.heart_events)
            if ev:
                npc.complete_heart_event(ev)
                audio.play("gift")
                for page in ev["pages"]:
                    self.say(label, page, npc.id)
                self.ui.toast(f"{npc.name} opened up. (+{ev.get('bonus', 0)} friendship)")
                return
            reward = self.favors.deliver(npc.id, self.inventory, self.defs)
            if reward:
                audio.play("credits")
                self.player.credits += reward["credits"]
                npc.friendship = min(npc.friendship + reward["friendship"],
                                     self.cfg["npcs"]["friendship_max"])
                self.say(label, self.favors.thanks[npc.id].format(crop=reward["crop_name"]),
                         npc.id)
                self.ui.toast(f"+{reward['credits']} cr")
                self.particles.float_text(f"+{reward['friendship']}",
                                          npc.x * self.ts + self.ts // 2,
                                          (npc.y - 0.4) * self.ts, (255, 170, 220))
                return
            first_talk_today = not npc.talked_today
            line = npc.talk_line(self.npcs.dialogue, self.clock.day,
                                 self._dialogue_ctx(npc))
            if first_talk_today:
                self.particles.float_text(f"+{self.cfg['npcs']['talk_points_per_day']}",
                                          npc.x * self.ts + self.ts // 2,
                                          (npc.y - 0.4) * self.ts, (255, 170, 220))
            self.say(label, line, npc.id)
            if npc.id == "sylla" and npc.has_perk():
                self.say(f"{npc.name} — field scan", self._soil_report(), npc.id)
            return

        tile = self.world.tile(tx, ty)
        if tile and tile.kind == "building":
            b = self.world.building_at(tx, ty)
            if b and b["image"] == "shop":
                self.mode = "upgrades"
                self.upgrade_index = 0
                audio.play("blip")
            else:
                self.say("THE BAR", "A note on the door: 'Opening after the next "
                                    "supply drop. Until then: BYO everything. — Mgmt.'")
            return
        if tile and tile.gear and tile.gear["kind"] == "kiln":
            gear = tile.gear
            crop_id = gear.get("crop_id")
            if not crop_id:
                self.mode = "kiln"
                self.kiln_pos = (tx, ty)
                self.kiln_index = 0
                audio.play("blip")
            elif self.clock.day < gear.get("ready_day", 0):
                good = self.defs.item_name(f"good:{crop_id}")
                days = gear["ready_day"] - self.clock.day
                when = "ready tomorrow" if days == 1 else f"in {days} days"
                self.ui.toast(f"The kiln hums warmly — {good} {when}.")
            else:
                self.collect_kiln(tx, ty)
            return
        standing = self.world.tile(*self.player.standing_tile())
        kind = tile.kind if tile else ""
        if kind not in ("habitat_door", "terminal", "shipping_pod", "great_crystal",
                        "mine_entrance", "mine_exit") and standing:
            if standing.kind in ("habitat_door", "mine_exit"):
                kind = standing.kind

        if kind == "mine_entrance":
            audio.play("blip")
            self.switch_map("mine", self.worlds["mine"].player_start)
            self.ui.toast("You climb down into Hux's dig site. The rock hums.")
            return
        if kind == "mine_exit":
            audio.play("blip")
            self.switch_map("farm", self._farm_spawn())
            self.ui.toast("Daylight. The hum fades behind you.")
            return

        if kind == "habitat_door":
            self.mode = "sleep"
            self.sleep_index = 0
        elif kind == "terminal":
            step = self.quests.try_trigger("terminal",
                                           len(self.flora.codex) + len(self.fauna.codex),
                                           self.world.avg_field_resonance(),
                                           self.clock.is_night)
            if step:
                self._fire_quest_step(step, "TERMINAL")
            else:
                self.mode = "terminal"
        elif kind == "shipping_pod":
            self.mode = "shop"
            self.shop_index = 0
        elif kind == "great_crystal":
            step = self.quests.try_trigger("great_crystal_night",
                                           len(self.flora.codex) + len(self.fauna.codex),
                                           self.world.avg_field_resonance(),
                                           self.clock.is_night)
            if step:
                self._fire_quest_step(step, "VERIDIA")
            elif self.quests.finished:
                if self.restoration.all_complete():
                    self.say("VERIDIA", "The crystal holds your reflection a long "
                             "moment, then lets it go, glowing. WE WANT FOR NOTHING. "
                             "GROW WITH US, GARDENER. ALWAYS.")
                else:
                    self.mode = "restoration"
                    self.restoration_index = 0
                    audio.play("quest")
            else:
                self.ui.toast("The great crystal thrums quietly." +
                              ("" if self.clock.is_night else " Perhaps at night..."))

    def _fire_quest_step(self, step: dict, speaker: str) -> None:
        audio.play("quest")
        self.say(speaker, step["text"])
        self.ui.toast(f"Journal updated: {step['title']}")
        if step.get("reward_seed"):
            n = step.get("reward_seed_count", 1)
            self.inventory.add(f"seed:{step['reward_seed']}", n)
            self.ui.toast(f"Received {n}x {self.defs.get(step['reward_seed'])['name']} seeds!")

    def give_gift(self) -> None:
        tx, ty = self.player.target_tile()
        npc = self.npcs.npc_near(tx, ty) if self.map_id == "farm" else None
        if npc is None:
            self.ui.toast("No one nearby to gift.")
            return
        slot = next((s for s in self.inventory.items() if s["id"].startswith("crop:")), None)
        if slot is None:
            self.ui.toast("You have no crops to gift.")
            return
        crop_id = slot["id"][len("crop:"):].split("#")[0]
        reaction = npc.receive_gift(crop_id)
        if reaction != "already_today":
            self.inventory.remove(slot["id"], 1)
            audio.play("gift")
            points = npc.gift_points(reaction)
            color = (240, 120, 120) if points < 0 else (255, 170, 220)
            self.particles.float_text(f"{points:+d}", npc.x * self.ts + self.ts // 2,
                                      (npc.y - 0.4) * self.ts, color)
        self.say(f"{npc.name} ({npc.hearts_label()})",
                 self.npcs.gift_text(npc, reaction), npc.id)

    def shop_action(self, ship_stack: bool) -> None:
        rows = self.shop_rows()
        if not rows:
            return
        self.shop_index = min(self.shop_index, len(rows) - 1)
        row = rows[self.shop_index]
        if self.shop_mode == "sell":
            qty = row["qty"] if ship_stack else 1
            self.inventory.remove(row["id"], qty)
            self.shipping_bin.add(row["id"], qty)
            audio.play("blip")
            self.ui.toast(f"Shipped {qty}x {self.defs.item_name(row['id'])}.")
        else:
            d = self.defs.get(row["id"])
            price = self.seed_price(row["id"])
            if self.player.credits >= price:
                self.player.credits -= price
                self.inventory.add(f"seed:{row['id']}", 1)
                audio.play("credits")
                self.ui.toast(f"Bought {d['name']} seeds.")
            else:
                self.ui.toast("Not enough credits.")

    # ---- upgrades shop -----------------------------------------------------------

    def owned_gear_count(self, gear_id: str) -> int:
        return len(self.world.gear_tiles(gear_id)) + self.inventory.count(f"gear:{gear_id}")

    def upgrade_rows(self) -> list[dict]:
        rows = []
        discount = self.npcs.perk("tinks")
        for uid, u in self.defs.gear.items():
            owned = self.owned_gear_count(uid) if uid in ("drone", "kiln") \
                else int(uid in self.player.upgrades)
            price = u["price"]
            if discount:
                price = int(round(price * (1 - self.cfg["npcs"]["tinks_seed_discount"])))
            rows.append({"id": uid, "name": u["name"], "price": price,
                         "desc": u["desc"], "owned": owned, "max": u["max"]})
        return rows

    def buy_upgrade(self) -> None:
        rows = self.upgrade_rows()
        if not rows:
            return
        self.upgrade_index = min(self.upgrade_index, len(rows) - 1)
        row = rows[self.upgrade_index]
        if row["owned"] >= row["max"]:
            self.ui.toast("Tinks: 'You've cleaned me out of those!'")
            return
        if self.player.credits < row["price"]:
            self.ui.toast("Tinks: 'Credits first, friend.'")
            return
        self.player.credits -= row["price"]
        audio.play("credits")
        uid = row["id"]
        if uid in ("drone", "kiln"):
            self.inventory.add(f"gear:{uid}", 1)
            self.ui.toast(f"{row['name']} in your pack — place it with the Planter [5].")
        else:
            self.player.upgrades.add(uid)
            if uid == "pack":
                self.inventory.expand(12)
            self.ui.toast(f"{row['name']} installed!")

    # ---- bio-kiln ----------------------------------------------------------------

    def kiln_rows(self) -> list[dict]:
        """One row per distinct plain crop in the bag that has a recipe."""
        rows = []
        for crop_id, recipe in self.defs.recipes.items():
            qty = self.inventory.count(f"crop:{crop_id}")
            if qty <= 0:
                continue
            name = self.defs.get(crop_id)["name"]
            rows.append({
                "crop_id": crop_id,
                "label": f"{qty}x {name} -> {recipe['good']} "
                         f"({recipe['days']}d, {recipe['value']} cr)",
            })
        return rows

    def load_kiln(self, crop_id: str) -> bool:
        """Consume one plain crop and start the kiln at self.kiln_pos. False if stale."""
        if self.kiln_pos is None:
            return False
        tx, ty = self.kiln_pos
        tile = self.world.tile(tx, ty)
        if not (tile and tile.gear and tile.gear["kind"] == "kiln"):
            return False
        if tile.gear.get("crop_id") or crop_id not in self.defs.recipes:
            return False
        if not self.inventory.remove(f"crop:{crop_id}", 1):
            return False
        tile.gear["crop_id"] = crop_id
        tile.gear["ready_day"] = self.clock.day + self.defs.recipes[crop_id]["days"]
        audio.play("plant")
        return True

    def load_selected_kiln(self) -> None:
        rows = self.kiln_rows()
        if not rows:
            return
        self.kiln_index = min(self.kiln_index, len(rows) - 1)
        crop_id = rows[self.kiln_index]["crop_id"]
        loaded = self.load_kiln(crop_id)
        self.mode = "play"
        if loaded:
            self.ui.toast(f"The kiln takes your {self.defs.get(crop_id)['name']}"
                          " and begins to glow.")

    def collect_kiln(self, tx: int, ty: int) -> bool:
        """Collect the finished good from a ready kiln. Keeps state on a full bag."""
        tile = self.world.tile(tx, ty)
        if not (tile and tile.gear and tile.gear["kind"] == "kiln"):
            return False
        crop_id = tile.gear.get("crop_id")
        if not crop_id:
            return False
        if self.inventory.add(f"good:{crop_id}", 1):
            self.ui.toast("Inventory full.")
            return False
        tile.gear.pop("crop_id", None)
        tile.gear.pop("ready_day", None)
        wx, wy = tx * self.ts + self.ts // 2, ty * self.ts + self.ts // 2
        self.particles.burst("sparkle", wx, wy, self.rng)
        audio.play("credits")
        self.ui.toast(f"+1 {self.defs.item_name(f'good:{crop_id}')}")
        return True

    # ---- pause / options ---------------------------------------------------------

    def pause_action(self, row: str) -> None:
        audio.play("blip")
        if row == "Resume":
            self.mode = "play"
        elif row == "Options":
            self.mode = "options"
            self.option_index = 0
        elif row == "Save":
            self.save()
            self.ui.toast("Game saved.")
        elif row == "Quit to Title":
            self.save()
            self.to_title = True
            self.running = False
        elif row == "Quit Game":
            self.save()
            self.running = False

    def adjust_volume(self, row: str, delta: float) -> None:
        master, music, sfx = audio.get_volumes()
        if row == "Master":
            audio.set_volumes(master=master + delta)
        elif row == "Music":
            audio.set_volumes(music=music + delta)
        elif row == "SFX":
            audio.set_volumes(sfx=sfx + delta)
            audio.play("blip")

    # ---- restoration -------------------------------------------------------------

    def offer_bundle(self) -> None:
        pending = self.restoration.available(self.quests.finished)
        if not pending:
            return
        self.restoration_index = min(self.restoration_index, len(pending) - 1)
        bid = pending[self.restoration_index]
        bundle = self.restoration.offer(bid, self.inventory)
        if bundle is None:
            self.ui.toast("The crystal waits. You do not have everything it asks.")
            return
        audio.play("quest")
        self._apply_restoration_buffs()
        self.mode = "play"
        self.say("VERIDIA", bundle["text"])
        self.ui.toast(f"Restoration: {bundle['name']} complete.")
        if self.restoration.all_complete():
            self.say("VERIDIA", "Every furrow on the planet lights at once, horizon "
                     "to horizon — your farm the first word of a sentence the whole "
                     "world is writing. VERIDIA IS AWAKE. Thank you, farmer.")
            self.ui.toast("Veridia Awakened — the restoration is complete.")

    # ---- day cycle ---------------------------------------------------------------

    def end_day(self, collapsed: bool) -> None:
        farm = self.worlds["farm"]
        if self.map_id != "farm":   # wherever you pass out, you wake at the habitat
            self.switch_map("farm", farm.player_start)
        aurora_mult = self.events.growth_multiplier()
        growth_mult = aurora_mult * (1.0 + self.restoration.buff("growth_rate"))
        farm.end_of_day(self.moons, self.clock.day, growth_mult, self.rng,
                        recovery_mult=self.restoration.buff("soil_recovery") or 1.0)
        mineral_mult = 1.0 + (self.cfg["mining"]["hux_price_bonus"]
                              if self.npcs.perk("hux") else 0.0)
        sell_mult = 1.0 + self.restoration.buff("sell_bonus")
        manifest = self.shipping_bin.manifest(self.defs, mineral_mult, sell_mult)
        income = self.shipping_bin.process_overnight(self.defs, mineral_mult, sell_mult)
        self.player.credits += income
        self.clock.start_new_day()
        self.events.advance_day(self.rng)
        spored = self.events.apply_morning(farm, self.rng)
        self.worlds["mine"].regen_ores(self.rng,
                                       self.cfg["mining"]["regen_chance_per_day"])
        care7_watered = 0
        if self.npcs.perk("care7"):
            planted = [(x, y) for x, y, t in farm.iter_tiles()
                       if t.crop and not t.crop.wilted and not t.crop.watered_today
                       and not t.crop.strict_watering]
            self.rng.shuffle(planted)
            for x, y in planted[:self.cfg["npcs"]["care7_water_tiles"]]:
                farm.water(x, y)
                care7_watered += 1
        drone_watered = farm.drone_morning_water()
        self.flora.daily_spawn(farm, self.moons, self.clock.day, self.rng)
        self.npcs.end_of_day()
        crop_pool = [cid for cid in (set(self.defs.starter_ids()) |
                                     set(self.flora.unlocked_seed_crops()))
                     if self.defs.get(cid)["seed_price"] > 0]
        new_favors = self.favors.new_day(self.clock.day, list(self.npcs.npcs),
                                         crop_pool, self.rng, self.defs)
        self.player.rest(collapsed)
        self.save()
        self.day_summary = {
            "day": self.clock.day,
            "collapsed": collapsed,
            "income": income,
            "lines": [(self.defs.item_name(i), q, v) for i, q, v in manifest],
            "today": self.events.today_name(),
            "forecast": self.events.forecast_name(),
            "spored": spored,
            "care7": care7_watered,
            "drones": drone_watered,
            "ilo": self.moons.phase_name("ilo", self.clock.day),
            "vesk": self.moons.phase_name("vesk", self.clock.day),
            "favors": [f"{SHORT_NAMES.get(f['npc'], f['npc'].capitalize())} asks: "
                      f"{f['qty']}x {self.defs.get(f['crop_id'])['name']}"
                      for f in new_favors],
        }
        self.summary_age = 0.0
        self.mode = "day_summary"
        audio.play("sleep")

    # ---- input ---------------------------------------------------------------

    def handle_key(self, e: pygame.event.Event) -> None:
        k = e.key
        if k == pygame.K_F1:
            self.debug = not self.debug
            return

        if self.mode == "day_summary":
            if k in (pygame.K_e, pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE) \
                    and self.summary_age > 0.4:
                self.mode = "play"
                if self.day_summary and self.day_summary["income"]:
                    audio.play("credits")
                    self.particles.float_text(f"+{self.day_summary['income']} cr",
                                              self.player.x * self.ts,
                                              (self.player.y - 0.8) * self.ts,
                                              (255, 220, 120), life=2.0)
            return

        if self.mode == "dialogue":
            if k in (pygame.K_e, pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE):
                self.dialogue_queue.pop(0)
                if not self.dialogue_queue:
                    self.mode = "play"
            return

        if self.mode == "sleep":
            options_n = 3
            if k in (pygame.K_UP, pygame.K_w):
                self.sleep_index = (self.sleep_index - 1) % options_n
            elif k in (pygame.K_DOWN, pygame.K_s):
                self.sleep_index = (self.sleep_index + 1) % options_n
            elif k in (pygame.K_RETURN, pygame.K_e):
                if self.sleep_index == 0:
                    self.end_day(collapsed=False)
                elif self.sleep_index == 1:
                    if self.clock.skip_hours(2.0):
                        self.end_day(collapsed=True)
                    else:
                        self.mode = "play"
                        self.ui.toast(f"You wait. It is now {self.clock.clock_text()}.")
                else:
                    self.mode = "play"
            elif k == pygame.K_ESCAPE:
                self.mode = "play"
            return

        if self.mode == "shop":
            rows = self.shop_rows()
            if k == pygame.K_TAB:
                self.shop_mode = "buy" if self.shop_mode == "sell" else "sell"
                self.shop_index = 0
            elif k in (pygame.K_UP, pygame.K_w) and rows:
                self.shop_index = (self.shop_index - 1) % len(rows)
            elif k in (pygame.K_DOWN, pygame.K_s) and rows:
                self.shop_index = (self.shop_index + 1) % len(rows)
            elif k == pygame.K_RETURN:
                self.shop_action(ship_stack=bool(e.mod & pygame.KMOD_SHIFT))
            elif k in (pygame.K_ESCAPE, pygame.K_e):
                self.mode = "play"
            return

        if self.mode == "pause":
            if k in (pygame.K_UP, pygame.K_w):
                self.pause_index = (self.pause_index - 1) % len(PAUSE_ROWS)
            elif k in (pygame.K_DOWN, pygame.K_s):
                self.pause_index = (self.pause_index + 1) % len(PAUSE_ROWS)
            elif k == pygame.K_RETURN:
                self.pause_action(PAUSE_ROWS[self.pause_index])
            elif k == pygame.K_ESCAPE:
                self.mode = "play"
            return

        if self.mode == "options":
            if k in (pygame.K_UP, pygame.K_w):
                self.option_index = (self.option_index - 1) % len(OPTION_ROWS)
            elif k in (pygame.K_DOWN, pygame.K_s):
                self.option_index = (self.option_index + 1) % len(OPTION_ROWS)
            elif k in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                delta = 0.1 if k in (pygame.K_RIGHT, pygame.K_d) else -0.1
                self.adjust_volume(OPTION_ROWS[self.option_index], delta)
            elif k == pygame.K_RETURN and OPTION_ROWS[self.option_index] == "Back":
                self.mode = "pause"
            elif k == pygame.K_ESCAPE:
                self.mode = "pause"
            return

        if self.mode == "restoration":
            pending = self.restoration.available(self.quests.finished)
            if k in (pygame.K_UP, pygame.K_w) and pending:
                self.restoration_index = (self.restoration_index - 1) % len(pending)
            elif k in (pygame.K_DOWN, pygame.K_s) and pending:
                self.restoration_index = (self.restoration_index + 1) % len(pending)
            elif k == pygame.K_RETURN:
                self.offer_bundle()
            elif k in (pygame.K_ESCAPE, pygame.K_e):
                self.mode = "play"
            return

        if self.mode == "upgrades":
            rows = self.upgrade_rows()
            if k in (pygame.K_UP, pygame.K_w) and rows:
                self.upgrade_index = (self.upgrade_index - 1) % len(rows)
            elif k in (pygame.K_DOWN, pygame.K_s) and rows:
                self.upgrade_index = (self.upgrade_index + 1) % len(rows)
            elif k == pygame.K_RETURN:
                self.buy_upgrade()
            elif k in (pygame.K_ESCAPE, pygame.K_e):
                self.mode = "play"
            return

        if self.mode == "kiln":
            rows = self.kiln_rows()
            if k in (pygame.K_UP, pygame.K_w) and rows:
                self.kiln_index = (self.kiln_index - 1) % len(rows)
            elif k in (pygame.K_DOWN, pygame.K_s) and rows:
                self.kiln_index = (self.kiln_index + 1) % len(rows)
            elif k == pygame.K_RETURN:
                self.load_selected_kiln()
            elif k in (pygame.K_ESCAPE, pygame.K_e):
                self.mode = "play"
            return

        if self.mode in ("inventory", "codex", "journal", "terminal", "help"):
            close = {"inventory": pygame.K_i, "codex": pygame.K_c, "journal": pygame.K_j,
                     "terminal": pygame.K_e, "help": pygame.K_SLASH}[self.mode]
            if k in (pygame.K_ESCAPE, close):
                self.mode = "play"
            return

        # ---- play mode ----
        tool_keys = {pygame.K_1: "hoe", pygame.K_2: "water", pygame.K_3: "harvest",
                     pygame.K_4: "scanner", pygame.K_5: "plant"}
        if k in tool_keys:
            self.player.tool = tool_keys[k]
            self.ui.toast(self.tool_label())
        elif k == pygame.K_TAB:
            self.cycle_seed()
        elif k == pygame.K_SPACE:
            self.use_tool()
        elif k == pygame.K_e:
            self.interact()
        elif k == pygame.K_g:
            self.give_gift()
        elif k == pygame.K_i:
            self.mode = "inventory"
        elif k == pygame.K_c:
            self.mode = "codex"
        elif k == pygame.K_j:
            self.mode = "journal"
        elif k == pygame.K_SLASH or getattr(e, "unicode", "") == "?":
            self.mode = "help"
        elif k == pygame.K_F5:
            self.save()
            self.ui.toast("Game saved.")
        elif self.debug and k == pygame.K_t:
            if self.clock.skip_hours(self.cfg["debug"]["time_skip_hours"]):
                self.end_day(collapsed=True)
        elif self.debug and k == pygame.K_n:
            self.end_day(collapsed=False)
        elif k == pygame.K_ESCAPE:
            self.mode = "pause"
            self.pause_index = 0
            audio.play("blip")

    def handle_mouse(self, e: pygame.event.Event) -> None:
        if e.button != 1:
            return
        if self.mode == "play":
            for rect, tool in self.ui.hotbar_rects:
                if rect.collidepoint(e.pos):
                    self.player.tool = tool
                    self.ui.toast(self.tool_label())
                    audio.play("blip")
                    return
        elif self.mode == "shop":
            for key, rect in self.ui.shop_tab_rects.items():
                if rect.collidepoint(e.pos):
                    self.shop_mode = key
                    self.shop_index = 0
                    return
            for i, rect in enumerate(self.ui.shop_row_rects):
                if rect.collidepoint(e.pos):
                    if i == self.shop_index:
                        self.shop_action(ship_stack=False)
                    else:
                        self.shop_index = i
                    return
        elif self.mode == "upgrades":
            for i, rect in enumerate(self.ui.upgrade_row_rects):
                if rect.collidepoint(e.pos):
                    if i == self.upgrade_index:
                        self.buy_upgrade()
                    else:
                        self.upgrade_index = i
                    return
        elif self.mode == "restoration":
            for i, rect in enumerate(self.ui.restoration_row_rects):
                if rect.collidepoint(e.pos):
                    if i == self.restoration_index:
                        self.offer_bundle()
                    else:
                        self.restoration_index = i
                    return
        elif self.mode == "pause":
            for i, rect in enumerate(self.ui.pause_row_rects):
                if rect.collidepoint(e.pos):
                    self.pause_index = i
                    self.pause_action(PAUSE_ROWS[i])
                    return
        elif self.mode == "options":
            for i, rect in enumerate(self.ui.option_row_rects):
                if rect.collidepoint(e.pos):
                    self.option_index = i
                    if OPTION_ROWS[i] == "Back":
                        self.mode = "pause"
                    return
        elif self.mode == "kiln":
            for i, rect in enumerate(self.ui.kiln_row_rects):
                if rect.collidepoint(e.pos):
                    if i == self.kiln_index:
                        self.load_selected_kiln()
                    else:
                        self.kiln_index = i
                    return

    # ---- frame ---------------------------------------------------------------

    def update(self, dt: float) -> None:
        self.t += dt
        self.ui.update(dt)
        self.particles.update(dt)
        in_mine = self.map_id == "mine"
        audio.set_ambient("ambient_night"
                          if in_mine or self.clock.is_night else "ambient_day")
        audio.set_weather("storm_loop"
                          if self.events.ion_storm_active(self.clock.hour)
                          and not in_mine else None)
        if self.mode == "day_summary":
            self.summary_age += dt
            return
        if self.mode != "play":
            return
        self.player.swing_t = max(0.0, self.player.swing_t - dt)
        keys = pygame.key.get_pressed()
        ix = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        iy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        self.player.move(ix, iy, dt, self.world)
        self.camera.update(dt, self.player.x * self.ts, self.player.y * self.ts)
        if self.clock.update(dt):
            self.end_day(collapsed=True)
            return
        self.npcs.update(self.clock.hour, dt, self.worlds["farm"],
                         self.events.ion_storm_active(self.clock.hour))
        self.fauna.update(dt, self.worlds, self.map_id,
                          (self.player.x, self.player.y), self.clock.hour, self.rng)
        if self.map_id == "farm" and self.events.today == "spore_drift" \
                and self.rng.random() < dt * 2.5:
            sx, sy = self.rng.choice(self.soil_tiles)
            self.particles.burst("spore", sx * self.ts + self.rng.uniform(4, 28),
                                 sy * self.ts + self.rng.uniform(4, 20), self.rng)
        self.storm_flash = max(0.0, self.storm_flash - dt)
        if self.events.ion_storm_active(self.clock.hour) and self.map_id == "farm":
            if self.rng.random() < dt * 0.12:
                self.storm_flash = 0.3
            standing = self.world.tile(*self.player.standing_tile())
            sheltered = standing is not None and standing.kind == "habitat_door"
            if not sheltered:
                self.player.drain_energy(
                    self.cfg["events"]["ion_storm_energy_drain_per_sec"] * dt)
                if self.player.energy <= 0:
                    self.end_day(collapsed=True)

    def draw(self, screen: pygame.Surface, fps: float) -> None:
        ts = self.ts
        ws = self.world_surf
        ws.fill((20, 14, 34))
        x0, y0, x1, y1 = self.camera.visible_tiles(ts)
        x1, y1 = min(x1, self.world.width), min(y1, self.world.height)
        for y in range(y0, y1):
            for x in range(x0, x1):
                render.draw_tile(ws, self.world.tiles[y][x], x, y, ts, self.t)
        if self.map_id == "farm":
            render.draw_habitat(ws, self.habitat_origin, ts)
            render.draw_buildings(ws, self.world.buildings, ts)
        for y in range(y0, y1):
            for x in range(x0, x1):
                tile = self.world.tiles[y][x]
                if tile.gear:
                    render.draw_gear(ws, tile.gear, x, y, ts, self.t)
                if tile.crop:
                    render.draw_crop(ws, tile.crop, x, y, ts, self.t)
        if self.map_id == "farm":
            for w in self.flora.wild:
                render.draw_wild_plant(ws, self.flora.species[w["species"]],
                                       w["x"], w["y"], ts, self.t)
            for npc in self.npcs.npcs.values():
                render.draw_npc(ws, npc, ts)
        for c in self.fauna.critters:
            if c["map"] == self.map_id:
                render.draw_critter(ws, self.fauna.species[c["species"]], c, ts, self.t)
        render.draw_player(ws, self.player, ts, self.t)
        self.particles.draw(ws, self.t)
        mine_dark = self.cfg["mining"]["mine_darkness"] if self.map_id == "mine" else None
        render.draw_lighting(ws, self.world, self.flora, self.clock, ts, self.t,
                             self.camera.rect, darkness_override=mine_dark)

        if self.mode == "play":
            tx, ty = self.player.target_tile()
            pygame.draw.rect(ws, (255, 255, 255), (tx * ts, ty * ts, ts, ts), 1)
        if self.debug:
            self.ui.draw_debug_world(ws, self, ts)

        pygame.transform.scale(ws.subsurface(self.camera.rect),
                               (self.screen_w, self.screen_h), screen)

        if self.map_id == "farm":
            render.draw_time_tint(screen, self.clock.hour)
            if self.events.today == "aurora" and self.clock.is_night:
                strength = max(0.35, self.clock.darkness() / self.clock.max_darkness)
                render.draw_aurora(screen, self.t, strength)
            if self.events.ion_storm_active(self.clock.hour):
                render.draw_storm(screen, self.t, self.storm_flash)
        self.particles.draw_texts(screen, self.camera, self.ui.font)

        self.ui.draw_hud(screen, self)
        if self.mode in ("play", "dialogue"):
            self.ui.draw_hotbar(screen, self)
        if self.mode == "dialogue" and self.dialogue_queue:
            self.ui.draw_dialogue(screen, *self.dialogue_queue[0],
                                  pages_left=len(self.dialogue_queue) - 1)
        elif self.mode == "inventory":
            self.ui.draw_inventory(screen, self)
        elif self.mode == "shop":
            self.ui.draw_shop(screen, self)
        elif self.mode == "upgrades":
            self.ui.draw_upgrades(screen, self)
        elif self.mode == "restoration":
            self.ui.draw_restoration(screen, self)
        elif self.mode == "pause":
            self.ui.draw_pause(screen, self)
        elif self.mode == "options":
            self.ui.draw_options(screen, self)
        elif self.mode == "kiln":
            self.ui.draw_kiln(screen, self)
        elif self.mode == "terminal":
            self.ui.draw_terminal(screen, self)
        elif self.mode == "codex":
            self.ui.draw_codex(screen, self)
        elif self.mode == "journal":
            self.ui.draw_journal(screen, self)
        elif self.mode == "help":
            self.ui.draw_help(screen)
        elif self.mode == "sleep":
            self.ui.draw_sleep_prompt(
                screen, ["Sleep (saves, next day)", "Wait 2 hours", "Never mind"],
                self.sleep_index)
        elif self.mode == "day_summary":
            self.ui.draw_day_summary(screen, self)
        if self.debug:
            self.ui.draw_debug(screen, self, fps, ts)

    def run(self, max_frames: int | None = None) -> None:
        screen = pygame.display.set_mode((self.screen_w, self.screen_h))
        pygame.display.set_caption(self.cfg["window"]["title"])
        if self.cfg["window"].get("use_sprites", True) and load_assets(self.ts):
            self.ui.toast("Sprite sheets loaded.")
        audio.init(self.cfg)
        clock = pygame.time.Clock()
        frames = 0
        while self.running:
            dt = min(clock.tick(self.cfg["window"]["fps"]) / 1000.0, MAX_DT)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.running = False
                elif e.type == pygame.KEYDOWN:
                    self.handle_key(e)
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    self.handle_mouse(e)
            self.update(dt)
            self.draw(screen, clock.get_fps())
            pygame.display.flip()
            frames += 1
            if max_frames is not None and frames >= max_frames:
                break


def title_screen(screen: pygame.Surface) -> int | None:
    """Slot picker under the twin moons. Returns a slot number, or None to quit."""
    migrate_legacy()
    clock = pygame.time.Clock()
    big = pygame.font.SysFont("consolas", 42, bold=True)
    font = pygame.font.SysFont("consolas", 18)
    small = pygame.font.SysFont("consolas", 12)
    rng = random.Random(7)
    w, h = screen.get_size()
    stars = [(rng.randrange(w), rng.randrange(h), rng.uniform(0.4, 1.0))
             for _ in range(140)]

    def build_rows() -> list[tuple[str, int | None]]:
        rows: list[tuple[str, int | None]] = []
        stamped = [(n, slot_path(n).stat().st_mtime) for n in range(1, SLOT_COUNT + 1)
                   if slot_path(n).exists()]
        if stamped:
            latest = max(stamped, key=lambda p: p[1])[0]
            s = slot_summary(latest)
            if s:
                rows.append((f"Continue — Slot {latest} (Day {s['day']}, "
                             f"{s['credits']} cr)", latest))
        for n in range(1, SLOT_COUNT + 1):
            s = slot_summary(n)
            label = f"Slot {n} — Day {s['day']}, {s['credits']} cr" if s \
                else f"Slot {n} — New game"
            rows.append((label, n))
        rows.append(("Quit", None))
        return rows

    rows = build_rows()
    index = 0
    t = 0.0
    while True:
        dt = clock.tick(60) / 1000.0
        t += dt
        row_rects = []
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return None
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_UP, pygame.K_w):
                    index = (index - 1) % len(rows)
                elif e.key in (pygame.K_DOWN, pygame.K_s):
                    index = (index + 1) % len(rows)
                elif e.key == pygame.K_RETURN:
                    return rows[index][1]
                elif e.key == pygame.K_ESCAPE:
                    return None
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                for i, r in enumerate(_title_row_rects(rows, screen, font)):
                    if r.collidepoint(e.pos):
                        return rows[i][1]

        screen.fill((14, 8, 28))
        for sx, sy, b in stars:
            tw = 0.5 + 0.5 * math.sin(t * 1.5 + sx * 0.13 + sy * 0.07)
            c = int(90 + 120 * b * tw)
            screen.fill((c, c, min(255, c + 30)),
                        (sx, (sy + int(t * 4 * b)) % h, 2, 2))
        pulse = 0.7 + 0.3 * math.sin(t * 1.2)
        pygame.draw.circle(screen, (int(90 * pulse), int(110 * pulse), int(170 * pulse)),
                           (w // 2, h // 3 - 60), 46)
        title = big.render("AlphaFarm — Veridia", True, (235, 230, 245))
        screen.blit(title, ((w - title.get_width()) // 2, h // 3))
        sub = small.render("the ground is listening", True, (160, 150, 180))
        screen.blit(sub, ((w - sub.get_width()) // 2, h // 3 + 52))
        for i, r in enumerate(_title_row_rects(rows, screen, font)):
            row_rects.append(r)
            color = (255, 210, 120) if i == index else (235, 230, 245)
            marker = "> " if i == index else "  "
            img = font.render(marker + rows[i][0], True, color)
            screen.blit(img, (r.x, r.y))
        hint = small.render("[Enter/click] select   [Esc] quit", True, (160, 150, 180))
        screen.blit(hint, ((w - hint.get_width()) // 2, h - 40))
        pygame.display.flip()


def _title_row_rects(rows, screen: pygame.Surface, font) -> list[pygame.Rect]:
    w, h = screen.get_size()
    out = []
    y = h // 2 + 20
    for label, _ in rows:
        img_w, img_h = font.size("> " + label)
        out.append(pygame.Rect((w - img_w) // 2, y, img_w, img_h))
        y += img_h + 14
    return out


def main() -> None:
    pygame.init()
    cfg = load_config()
    m = load_json("map.json")
    ts = cfg["window"]["tile_size"]
    screen = pygame.display.set_mode((m["width"] * ts, m["height"] * ts))
    pygame.display.set_caption(cfg["window"]["title"])
    while True:
        slot = title_screen(screen)
        if slot is None:
            break
        game = Game(slot)
        game.run()
        if not game.to_title:
            break
    audio.shutdown()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
