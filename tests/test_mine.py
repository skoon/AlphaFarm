import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

import main as m  # noqa: E402
from game.config import load_config  # noqa: E402
from game.crops import CropDefs  # noqa: E402
from game.world import World  # noqa: E402


def make_game():
    m.load_game = lambda *a: None
    m.save_game = lambda *a: None
    if not pygame.get_init():
        pygame.init()
    return m.Game()


def make_mine():
    return World(load_config(), CropDefs(), map_name="mine")


def find_ore(world):
    return next((x, y) for x, y, t in world.iter_tiles()
                if t.kind.startswith("ore_"))


def test_mine_map_loads_with_ores_exit_and_crystals():
    mine = make_mine()
    kinds = {t.kind for _, _, t in mine.iter_tiles()}
    assert {"cave_wall", "cave_floor", "mine_exit", "cave_crystal",
            "ore_ferrite", "ore_lumite", "ore_quartz"} <= kinds
    x, y = mine.player_start
    assert not mine.is_solid(x, y)


def test_ore_breaks_after_hp_hits_and_drops_minerals():
    mine = make_mine()
    rng = random.Random(1)
    x, y = find_ore(mine)
    tile = mine.tile(x, y)
    hp = tile.hp
    mineral_kind = tile.kind[len("ore_"):]
    drops = None
    for _ in range(hp):
        drops = mine.mine_ore(x, y, rng)
    assert drops is not None
    mineral, qty = drops
    assert mineral == mineral_kind and qty >= 1
    assert tile.kind == "cave_floor" and tile.hp is None
    assert mine.mine_ore(x, y, rng) is None   # already broken


def test_broken_ore_regrows_and_survives_save():
    mine = make_mine()
    rng = random.Random(1)
    x, y = find_ore(mine)
    tile = mine.tile(x, y)
    while tile.kind.startswith("ore_"):
        mine.mine_ore(x, y, rng)
    state = mine.to_dict()
    mine2 = make_mine()
    mine2.from_dict(state)
    assert mine2.tile(x, y).kind == "cave_floor"
    assert mine2.regen_ores(random.Random(2), chance=1.0) > 0
    t2 = mine2.tile(x, y)
    assert t2.kind == t2.base_kind and t2.hp is not None


def test_map_transitions_via_interact():
    game = make_game()
    ex, ey = game.worlds["farm"].find_kind("mine_entrance")[0]
    game.player.x, game.player.y = float(ex), float(ey + 1)
    game.player.facing = (0, -1)
    assert game.player.target_tile() == (ex, ey)
    game.interact()
    assert game.map_id == "mine"
    assert game.world.map_name == "mine"
    sx, sy = game.worlds["mine"].player_start
    # spawn is centered on the tile so the hitbox can't snag an adjacent wall
    assert (game.player.x, game.player.y) == (sx + 0.5, sy + 0.5)
    assert not game.world.is_solid(*game.player.standing_tile())
    # walk onto the exit ladder and interact
    exit_x, exit_y = game.worlds["mine"].find_kind("mine_exit")[0]
    game.player.x, game.player.y = float(exit_x), float(exit_y)
    game.player.facing = (-1, 0)
    game.interact()
    assert game.map_id == "farm"
    assert (game.player.x, game.player.y) == (ex + 0.5, ey + 1 + 0.5)


def test_player_can_move_after_entering_mine():
    """Regression: spawning on a raw tile corner wedged the hitbox into a wall."""
    game = make_game()
    ex, ey = game.worlds["farm"].find_kind("mine_entrance")[0]
    game.player.x, game.player.y = float(ex), float(ey + 1)
    game.player.facing = (0, -1)
    game.interact()
    assert game.map_id == "mine"
    # try every direction; at least one must actually change position
    start = (game.player.x, game.player.y)
    moved = False
    for ix, iy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        game.player.x, game.player.y = start
        game.player.move(ix, iy, 0.1, game.world)
        if (game.player.x, game.player.y) != start:
            moved = True
    assert moved, "player is wedged and cannot move in the mine"


def test_map_spawns_are_not_solid_or_wedged():
    game = make_game()
    for target, spawn in (("mine", game.worlds["mine"].player_start),
                          ("farm", game.worlds["farm"].player_start)):
        game.switch_map(target, spawn)
        # every hitbox corner must land on a non-solid tile
        assert not game.player._collides(game.player.x, game.player.y, game.world)


def test_mining_through_use_tool_awards_minerals():
    game = make_game()
    game.switch_map("mine", (0, 0))
    mine = game.world
    x, y = find_ore(mine)
    game.player.x, game.player.y = float(x), float(y + 1)
    game.player.facing = (0, -1)
    game.player.tool = "hoe"
    game.rng = random.Random(5)
    hits = mine.tile(x, y).hp
    for _ in range(hits):
        game.use_tool()
    total = sum(game.inventory.count(f"mineral:{mid}")
                for mid in ("ferrite", "lumite", "quartz"))
    assert total >= 1
    assert game.player.energy < game.player.max_energy


def test_collapse_in_mine_wakes_at_farm():
    game = make_game()
    game.switch_map("mine", (2.0, 8.0))
    game.end_day(collapsed=True)
    assert game.map_id == "farm"
    fx, fy = game.worlds["farm"].player_start
    assert (game.player.x, game.player.y) == (fx + 0.5, fy + 0.5)


def test_mine_state_persists_in_save():
    game = make_game()
    mine = game.worlds["mine"]
    rng = random.Random(1)
    x, y = find_ore(mine)
    while mine.tile(x, y).kind.startswith("ore_"):
        mine.mine_ore(x, y, rng)
    state = game.gather_state()
    assert "mine_world" in state and state["map_id"] == "farm"
    game2 = make_game()
    game2.worlds["mine"].from_dict(state["mine_world"])
    assert game2.worlds["mine"].tile(x, y).kind == "cave_floor"


def test_hux_perk_boosts_mineral_payout_only():
    game = make_game()
    game.shipping_bin.add("mineral:quartz", 2)
    game.shipping_bin.add("crop:lumen_berry", 1)
    base_quartz = game.defs.sale_value("mineral:quartz")
    base_berry = game.defs.sale_value("crop:lumen_berry")
    rows = dict((i, v) for i, _, v in game.shipping_bin.manifest(game.defs, 1.2))
    assert rows["mineral:quartz"] == int(round(base_quartz * 1.2)) * 2
    assert rows["crop:lumen_berry"] == base_berry
