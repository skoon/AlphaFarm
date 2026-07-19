"""AlphaFarm — a cozy terraforming farm sim on the alien planet Veridia.

Run with: uv run python main.py
"""
from __future__ import annotations

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
from game.favors import SHORT_NAMES, FavorSystem
from game.flora import FloraSystem
from game.inventory import Inventory, ShippingBin
from game.npcs import NPCManager
from game.particles import Particles
from game.player import Player
from game.quest import QuestSystem
from game.save_load import load_game, save_game
from game.time_system import GameClock, Moons
from game.ui import UI
from game.world import World

MAX_DT = 0.1  # clamp frame delta so a hitch can't teleport things


class Game:
    def __init__(self) -> None:
        self.cfg = load_config()
        self.rng = random.Random()
        self.defs = CropDefs()
        self.items = load_json("items.json")
        self.clock = GameClock(self.cfg)
        self.moons = Moons(self.cfg)
        self.world = World(self.cfg, self.defs)
        self.player = Player(self.cfg, self.world.player_start)
        self.inventory = Inventory(self.cfg)
        self.shipping_bin = ShippingBin()
        self.events = EventSystem(self.cfg, self.rng)
        self.flora = FloraSystem(self.cfg)
        self.npcs = NPCManager(self.cfg)
        self.quests = QuestSystem()
        self.favors = FavorSystem()
        self.heart_events = load_json("heart_events.json")

        ts = self.cfg["window"]["tile_size"]
        self.screen_w = self.world.width * ts
        self.screen_h = self.world.height * ts
        self.ts = ts
        self.map_px = (self.world.width * ts, self.world.height * ts)
        self.camera = Camera(self.cfg, *self.map_px, self.screen_w, self.screen_h)
        self.world_surf = pygame.Surface(self.map_px)
        self.ui = UI(self.screen_w, self.screen_h)
        walls = self.world.find_kind("habitat_wall") + self.world.find_kind("habitat_door")
        self.habitat_origin = (min(x for x, _ in walls), min(y for _, y in walls))

        self.mode = "play"
        self.dialogue_queue: list[tuple[str, str]] = []
        self.shop_mode = "sell"
        self.shop_index = 0
        self.upgrade_index = 0
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
            "world": self.world.to_dict(),
            "events": self.events.to_dict(),
            "flora": self.flora.to_dict(),
            "npcs": self.npcs.to_dict(),
            "quests": self.quests.to_dict(),
            "favors": self.favors.to_dict(),
        }

    def _load(self) -> bool:
        state = load_game()
        if state is None:
            return False
        self.clock.from_dict(state["clock"])
        self.player.from_dict(state["player"])
        if "pack" in self.player.upgrades:
            self.inventory.expand(12)
        self.inventory.from_dict(state["inventory"])
        self.shipping_bin.from_dict(state["shipping_bin"])
        self.world.from_dict(state["world"])
        self.events.from_dict(state["events"])
        self.flora.from_dict(state["flora"])
        self.npcs.from_dict(state["npcs"])
        self.quests.from_dict(state["quests"])
        if state.get("favors"):
            self.favors.from_dict(state["favors"])
        self.ui.toast(f"Save loaded — day {self.clock.day}.")
        return True

    def save(self) -> None:
        save_game(self.gather_state())

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
                if s["id"].startswith("crop:") or s["id"].startswith("good:"):
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
        npc = self.npcs.npc_near(tx, ty)
        if npc:
            trigger = f"talk_{npc.id}"
            step = self.quests.try_trigger(trigger, len(self.flora.codex),
                                           self.world.avg_field_resonance(),
                                           self.clock.is_night)
            if step:
                self._fire_quest_step(step, npc.name)
                return
            label = f"{npc.name} ({npc.hearts()}/10 hearts)"
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
                return
            line = npc.talk_line(self.npcs.dialogue, self.clock.day,
                                 self._dialogue_ctx(npc))
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
        if kind not in ("habitat_door", "terminal", "shipping_pod", "great_crystal") \
                and standing and standing.kind == "habitat_door":
            kind = "habitat_door"

        if kind == "habitat_door":
            self.mode = "sleep"
            self.sleep_index = 0
        elif kind == "terminal":
            step = self.quests.try_trigger("terminal", len(self.flora.codex),
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
            step = self.quests.try_trigger("great_crystal_night", len(self.flora.codex),
                                           self.world.avg_field_resonance(),
                                           self.clock.is_night)
            if step:
                self._fire_quest_step(step, "VERIDIA")
            elif self.quests.finished:
                self.say("VERIDIA", "The crystal is warm, like held breath. You are welcome here.")
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
        npc = self.npcs.npc_near(tx, ty)
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
        self.say(f"{npc.name} ({npc.hearts()}/10 hearts)",
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

    # ---- day cycle ---------------------------------------------------------------

    def end_day(self, collapsed: bool) -> None:
        aurora_mult = self.events.growth_multiplier()
        self.world.end_of_day(self.moons, self.clock.day, aurora_mult, self.rng)
        manifest = self.shipping_bin.manifest(self.defs)
        income = self.shipping_bin.process_overnight(self.defs)
        self.player.credits += income
        self.clock.start_new_day()
        self.events.advance_day(self.rng)
        spored = self.events.apply_morning(self.world, self.rng)
        care7_watered = 0
        if self.npcs.perk("care7"):
            planted = [(x, y) for x, y, t in self.world.iter_tiles()
                       if t.crop and not t.crop.wilted and not t.crop.watered_today
                       and not t.crop.strict_watering]
            self.rng.shuffle(planted)
            for x, y in planted[:self.cfg["npcs"]["care7_water_tiles"]]:
                self.world.water(x, y)
                care7_watered += 1
        drone_watered = self.world.drone_morning_water()
        self.flora.daily_spawn(self.world, self.moons, self.clock.day, self.rng)
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
            self.running = False

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
        audio.set_ambient("ambient_night" if self.clock.is_night else "ambient_day")
        audio.set_weather("storm_loop"
                          if self.events.ion_storm_active(self.clock.hour) else None)
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
        self.npcs.update(self.clock.hour, dt, self.world,
                         self.events.ion_storm_active(self.clock.hour))
        if self.events.today == "spore_drift" and self.rng.random() < dt * 2.5:
            sx, sy = self.rng.choice(self.soil_tiles)
            self.particles.burst("spore", sx * self.ts + self.rng.uniform(4, 28),
                                 sy * self.ts + self.rng.uniform(4, 20), self.rng)
        self.storm_flash = max(0.0, self.storm_flash - dt)
        if self.events.ion_storm_active(self.clock.hour):
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
        render.draw_habitat(ws, self.habitat_origin, ts)
        render.draw_buildings(ws, self.world.buildings, ts)
        for y in range(y0, y1):
            for x in range(x0, x1):
                tile = self.world.tiles[y][x]
                if tile.gear:
                    render.draw_gear(ws, tile.gear, x, y, ts, self.t)
                if tile.crop:
                    render.draw_crop(ws, tile.crop, x, y, ts, self.t)
        for w in self.flora.wild:
            render.draw_wild_plant(ws, self.flora.species[w["species"]],
                                   w["x"], w["y"], ts, self.t)
        for npc in self.npcs.npcs.values():
            render.draw_npc(ws, npc, ts)
        render.draw_player(ws, self.player, ts, self.t)
        self.particles.draw(ws, self.t)
        render.draw_lighting(ws, self.world, self.flora, self.clock, ts, self.t,
                             self.camera.rect)

        if self.mode == "play":
            tx, ty = self.player.target_tile()
            pygame.draw.rect(ws, (255, 255, 255), (tx * ts, ty * ts, ts, ts), 1)
        if self.debug:
            self.ui.draw_debug_world(ws, self, ts)

        pygame.transform.scale(ws.subsurface(self.camera.rect),
                               (self.screen_w, self.screen_h), screen)

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


def main() -> None:
    pygame.init()
    Game().run()
    audio.shutdown()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
