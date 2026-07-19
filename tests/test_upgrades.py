import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

import main as m  # noqa: E402
from tests.helpers import make_world  # noqa: E402


def make_game():
    m.load_game = lambda: None
    m.save_game = lambda state: None
    if not pygame.get_init():
        pygame.init()
    return m.Game()


def test_row_targets_widen_with_upgrade():
    game = make_game()
    game.player.facing = (0, 1)  # facing down -> horizontal row
    tx, ty = 10, 12
    assert game._row_targets(tx, ty, "hoe2") == [(10, 12)]
    game.player.upgrades.add("hoe2")
    assert set(game._row_targets(tx, ty, "hoe2")) == {(9, 12), (10, 12), (11, 12)}
    game.player.facing = (1, 0)  # facing right -> vertical row
    assert set(game._row_targets(tx, ty, "hoe2")) == {(10, 11), (10, 12), (10, 13)}


def test_place_and_remove_drone():
    world = make_world()
    assert not world.place_gear(10, 12, "drone")      # untilled soil
    world.till(10, 12)
    assert world.place_gear(10, 12, "drone")
    assert not world.place_gear(10, 12, "kiln")       # occupied
    assert world.tile(10, 12).gear == {"kind": "drone"}
    gear = world.remove_gear(10, 12)
    assert gear == {"kind": "drone"} and world.tile(10, 12).gear is None


def test_kiln_placement_needs_grass():
    world = make_world()
    assert not world.place_gear(10, 12, "kiln")   # soil
    assert world.place_gear(10, 8, "kiln")        # grass
    assert not world.place_gear(0, 0, "kiln")     # rock border


def test_drone_waters_patch_but_skips_prism_pods():
    world = make_world()
    for x in range(9, 12):
        for y in range(11, 14):
            world.till(x, y)
    world.place_gear(10, 12, "drone")
    world.plant(9, 11, "lumen_berry")
    world.plant(11, 13, "prism_pod")
    watered = world.drone_morning_water()
    assert watered > 0
    assert world.tile(9, 11).crop.watered_today
    assert not world.tile(11, 13).crop.watered_today   # strict-watering skipped
    assert world.tile(11, 13).watered is False


def test_buy_upgrade_flow_and_limits():
    game = make_game()
    game.player.credits = 10_000
    rows = game.upgrade_rows()
    pack_i = next(i for i, r in enumerate(rows) if r["id"] == "pack")
    size_before = game.inventory.size
    game.upgrade_index = pack_i
    game.buy_upgrade()
    assert "pack" in game.player.upgrades
    assert game.inventory.size == size_before + 12
    credits_after = game.player.credits
    game.buy_upgrade()   # already owned -> refused
    assert game.player.credits == credits_after

    drone_i = next(i for i, r in enumerate(rows) if r["id"] == "drone")
    game.upgrade_index = drone_i
    game.buy_upgrade()
    assert game.inventory.count("gear:drone") == 1
    assert game.owned_gear_count("drone") == 1


def test_buy_refused_without_credits():
    game = make_game()
    game.player.credits = 0
    game.upgrade_index = 0
    game.buy_upgrade()
    assert not game.player.upgrades and game.player.credits == 0


def test_gear_survives_save_roundtrip():
    game = make_game()
    game.world.till(10, 12)
    game.world.place_gear(10, 12, "drone")
    game.world.place_gear(10, 8, "kiln")
    game.world.tile(10, 8).gear["crop_id"] = "lumen_berry"
    game.world.tile(10, 8).gear["ready_day"] = 5
    state = game.gather_state()
    game2 = make_game()
    game2.world.from_dict(state["world"])
    assert game2.world.tile(10, 12).gear == {"kind": "drone"}
    assert game2.world.tile(10, 8).gear["crop_id"] == "lumen_berry"


def test_old_player_dict_without_upgrades_loads():
    game = make_game()
    d = game.player.to_dict()
    del d["upgrades"]
    game.player.from_dict(d)
    assert game.player.upgrades == set()


def test_building_at_finds_shop_and_bar():
    world = make_world()
    shop = next(b for b in world.buildings if b["image"] == "shop")
    assert world.building_at(shop["x"], shop["y"]) is shop
    assert world.building_at(shop["x"] + shop["w"], shop["y"]) is not shop
    assert world.building_at(1, 1) is None
