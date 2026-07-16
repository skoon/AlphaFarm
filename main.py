"""AlphaFarm — a cozy terraforming farm sim on the alien planet Veridia.

Run with: uv run python main.py
"""
from __future__ import annotations

import random
import sys

import pygame

from game import render
from game.assets import load_assets
from game.config import load_config, load_json
from game.crops import CropDefs
from game.events import EventSystem
from game.flora import FloraSystem
from game.inventory import Inventory, ShippingBin
from game.npcs import NPCManager
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

        ts = self.cfg["window"]["tile_size"]
        self.screen_w = self.world.width * ts
        self.screen_h = self.world.height * ts
        self.ts = ts
        self.ui = UI(self.screen_w, self.screen_h)
        walls = self.world.find_kind("habitat_wall") + self.world.find_kind("habitat_door")
        self.habitat_origin = (min(x for x, _ in walls), min(y for _, y in walls))

        self.mode = "play"
        self.dialogue_queue: list[tuple[str, str]] = []
        self.shop_mode = "sell"
        self.shop_index = 0
        self.sleep_index = 0
        self.debug = False
        self.t = 0.0
        self.running = True

        if not self._load():
            self._new_game()

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
        }

    def _load(self) -> bool:
        state = load_game()
        if state is None:
            return False
        self.clock.from_dict(state["clock"])
        self.player.from_dict(state["player"])
        self.inventory.from_dict(state["inventory"])
        self.shipping_bin.from_dict(state["shipping_bin"])
        self.world.from_dict(state["world"])
        self.events.from_dict(state["events"])
        self.flora.from_dict(state["flora"])
        self.npcs.from_dict(state["npcs"])
        self.quests.from_dict(state["quests"])
        self.ui.toast(f"Save loaded — day {self.clock.day}.")
        return True

    def save(self) -> None:
        save_game(self.gather_state())

    # ---- helpers -------------------------------------------------------------

    def say(self, speaker: str, text: str) -> None:
        self.dialogue_queue.append((speaker, text))
        self.mode = "dialogue"

    def tool_label(self) -> str:
        name = self.items["tools"][self.player.tool]["name"]
        if self.player.tool == "plant":
            seed = self.player.selected_seed
            if seed:
                have = self.inventory.count(f"seed:{seed}")
                return f"{name}: {self.defs.get(seed)['name']} (x{have})"
            return f"{name}: no seeds"
        return name

    def cycle_seed(self) -> None:
        held = self.inventory.seed_ids_held()
        if not held:
            self.player.selected_seed = None
            self.ui.toast("No seeds in inventory.")
            return
        cur = self.player.selected_seed
        idx = (held.index(cur) + 1) % len(held) if cur in held else 0
        self.player.selected_seed = held[idx]
        self.ui.toast(f"Seed: {self.defs.get(held[idx])['name']}")

    def shop_rows(self) -> list[dict]:
        rows = []
        if self.shop_mode == "sell":
            for s in self.inventory.items():
                if s["id"].startswith("crop:"):
                    value = self.defs.sale_value(s["id"])
                    rows.append({"id": s["id"], "qty": s["qty"],
                                 "label": f"{self.defs.item_name(s['id'])} x{s['qty']}"
                                          f" — {value} cr each"})
        else:
            unlocked = set(self.defs.starter_ids()) | set(self.flora.unlocked_seed_crops())
            for cid in self.defs.defs:
                d = self.defs.get(cid)
                if cid in unlocked and d["seed_price"] > 0:
                    rows.append({"id": cid,
                                 "label": f"{d['name']} Seeds — {d['seed_price']} cr"
                                          f" (grows in {d['growth_days']}d,"
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

        if tool == "hoe":
            if self.world.till(tx, ty):
                self.player.spend_energy("hoe")
        elif tool == "water":
            tile = self.world.tile(tx, ty)
            if self.world.water(tx, ty):
                self.player.spend_energy("water")
                if tile and tile.crop and tile.crop.wilted:
                    self.ui.toast("The Prism Pod wilted — it wanted exactly one watering!")
        elif tool == "harvest":
            result = self.world.harvest(tx, ty, self.rng)
            if result:
                item, qty = result
                self.player.spend_energy("harvest")
                leftover = self.inventory.add(item, qty)
                self.quests.total_harvests += qty - leftover
                name = self.defs.item_name(item)
                if leftover:
                    self.ui.toast(f"Inventory full! Lost {leftover} {name}.")
                bonus = " x2 — the soil sings!" if qty - leftover > 1 else "!"
                self.ui.toast(f"Harvested {name}{bonus}")
        elif tool == "scanner":
            hit = self.flora.scan(tx, ty)
            if hit is None:
                self.ui.toast("Scanner: no undocumented flora there.")
                return
            self.player.spend_energy("scan")
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
            if not seed or self.inventory.count(f"seed:{seed}") == 0:
                self.ui.toast("No seeds selected — press Tab.")
                return
            if self.world.plant(tx, ty, seed):
                self.inventory.remove(f"seed:{seed}", 1)
                self.player.spend_energy("plant")

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
            else:
                self.say(f"{npc.name} ({npc.hearts()}/10 hearts)",
                         npc.talk_line(self.npcs.dialogue, self.clock.day))
            return

        tile = self.world.tile(tx, ty)
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
        self.say(f"{npc.name} ({npc.hearts()}/10 hearts)", self.npcs.gift_text(npc, reaction))

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
            self.ui.toast(f"Shipped {qty}x {self.defs.item_name(row['id'])}.")
        else:
            d = self.defs.get(row["id"])
            if self.player.credits >= d["seed_price"]:
                self.player.credits -= d["seed_price"]
                self.inventory.add(f"seed:{row['id']}", 1)
                self.ui.toast(f"Bought {d['name']} seeds.")
            else:
                self.ui.toast("Not enough credits.")

    # ---- day cycle ---------------------------------------------------------------

    def end_day(self, collapsed: bool) -> None:
        aurora_mult = self.events.growth_multiplier()
        self.world.end_of_day(self.moons, self.clock.day, aurora_mult, self.rng)
        income = self.shipping_bin.process_overnight(self.defs)
        self.player.credits += income
        self.clock.start_new_day()
        self.events.advance_day(self.rng)
        spored = self.events.apply_morning(self.world, self.rng)
        self.flora.daily_spawn(self.world, self.moons, self.clock.day, self.rng)
        self.npcs.end_of_day()
        self.player.rest(collapsed)
        self.mode = "play"
        self.save()
        if collapsed:
            self.ui.toast("You collapsed at 02:00... CARE-7 dragged you to bed.")
        self.ui.toast(f"Day {self.clock.day} on Veridia. Saved.")
        if income:
            self.ui.toast(f"Shipping pod paid out {income} cr.")
        if spored:
            self.ui.toast(f"A spore drift settled over {spored} of your plants overnight.")
        if self.events.today == "aurora":
            self.ui.toast("Aurora tonight — everything grows twice as fast!")
        elif self.events.today == "ion_storm":
            self.ui.toast("Ion storm today — stay near the habitat mid-day!")

    # ---- input ---------------------------------------------------------------

    def handle_key(self, e: pygame.event.Event) -> None:
        k = e.key
        if k == pygame.K_F1:
            self.debug = not self.debug
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

    # ---- frame ---------------------------------------------------------------

    def update(self, dt: float) -> None:
        self.t += dt
        self.ui.update(dt)
        if self.mode != "play":
            return
        keys = pygame.key.get_pressed()
        ix = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        iy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        self.player.move(ix, iy, dt, self.world)
        if self.clock.update(dt):
            self.end_day(collapsed=True)
            return
        self.npcs.update(self.clock.hour, dt)
        if self.events.ion_storm_active(self.clock.hour):
            standing = self.world.tile(*self.player.standing_tile())
            sheltered = standing is not None and standing.kind == "habitat_door"
            if not sheltered:
                self.player.drain_energy(
                    self.cfg["events"]["ion_storm_energy_drain_per_sec"] * dt)
                if self.player.energy <= 0:
                    self.end_day(collapsed=True)

    def draw(self, screen: pygame.Surface, fps: float) -> None:
        screen.fill((20, 14, 34))
        ts = self.ts
        for x, y, tile in self.world.iter_tiles():
            render.draw_tile(screen, tile, x, y, ts, self.t)
        render.draw_habitat(screen, self.habitat_origin, ts)
        for x, y, tile in self.world.iter_tiles():
            if tile.crop:
                render.draw_crop(screen, tile.crop, x, y, ts, self.t)
        for w in self.flora.wild:
            render.draw_wild_plant(screen, self.flora.species[w["species"]],
                                   w["x"], w["y"], ts, self.t)
        for npc in self.npcs.npcs.values():
            render.draw_npc(screen, npc, ts)
        render.draw_player(screen, self.player, ts, self.t)
        render.draw_lighting(screen, self.world, self.flora, self.clock, ts, self.t)

        if self.mode == "play":
            tx, ty = self.player.target_tile()
            pygame.draw.rect(screen, (255, 255, 255),
                             (tx * ts, ty * ts, ts, ts), 1)

        self.ui.draw_hud(screen, self)
        if self.mode == "dialogue" and self.dialogue_queue:
            self.ui.draw_dialogue(screen, *self.dialogue_queue[0])
        elif self.mode == "inventory":
            self.ui.draw_inventory(screen, self)
        elif self.mode == "shop":
            self.ui.draw_shop(screen, self)
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
        if self.debug:
            self.ui.draw_debug(screen, self, fps, ts)

    def run(self, max_frames: int | None = None) -> None:
        screen = pygame.display.set_mode((self.screen_w, self.screen_h))
        pygame.display.set_caption(self.cfg["window"]["title"])
        if self.cfg["window"].get("use_sprites", True) and load_assets(self.ts):
            self.ui.toast("Sprite sheets loaded.")
        clock = pygame.time.Clock()
        frames = 0
        while self.running:
            dt = min(clock.tick(self.cfg["window"]["fps"]) / 1000.0, MAX_DT)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.running = False
                elif e.type == pygame.KEYDOWN:
                    self.handle_key(e)
            self.update(dt)
            self.draw(screen, clock.get_fps())
            pygame.display.flip()
            frames += 1
            if max_frames is not None and frames >= max_frames:
                break


def main() -> None:
    pygame.init()
    Game().run()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
