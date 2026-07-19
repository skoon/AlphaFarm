import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

import main as m  # noqa: E402


def make_game():
    m.load_game = lambda: None
    m.save_game = lambda state: None
    if not pygame.get_init():
        pygame.init()
    return m.Game()


def place_kiln(game, tx=10, ty=8):
    assert game.world.place_gear(tx, ty, "kiln")
    game.kiln_pos = (tx, ty)
    game.kiln_index = 0
    return tx, ty


def test_kiln_rows_offers_only_plain_processable_crops():
    game = make_game()
    game.inventory.add("crop:lumen_berry", 3)
    game.inventory.add("crop:whisper_wheat", 1)
    rows = game.kiln_rows()
    crop_ids = {r["crop_id"] for r in rows}
    assert crop_ids == {"lumen_berry", "whisper_wheat"}
    lumen = next(r for r in rows if r["crop_id"] == "lumen_berry")
    assert lumen["label"] == "3x Lumen Berry -> Lumen Preserve (2d, 90 cr)"


def test_load_flow_removes_crop_and_sets_ready_day():
    game = make_game()
    tx, ty = place_kiln(game)
    game.inventory.add("crop:lumen_berry", 2)
    assert game.load_kiln("lumen_berry")
    assert game.inventory.count("crop:lumen_berry") == 1
    gear = game.world.tile(tx, ty).gear
    assert gear["crop_id"] == "lumen_berry"
    assert gear["ready_day"] == game.clock.day + 2


def test_load_selected_via_index_closes_mode():
    game = make_game()
    place_kiln(game)
    game.inventory.add("crop:prism_pod", 1)
    game.mode = "kiln"
    game.kiln_index = 0
    game.load_selected_kiln()
    assert game.mode == "play"
    assert game.inventory.count("crop:prism_pod") == 0
    assert game.world.tile(*game.kiln_pos).gear["crop_id"] == "prism_pod"


def test_not_ready_interaction_leaves_state_untouched():
    game = make_game()
    tx, ty = place_kiln(game)
    gear = game.world.tile(tx, ty).gear
    gear["crop_id"] = "lumen_berry"
    gear["ready_day"] = game.clock.day + 2
    before = dict(gear)
    game.player.x, game.player.y = float(tx), float(ty + 1)
    game.player.facing = (0, -1)
    game.interact()
    assert game.mode == "play"
    assert game.world.tile(tx, ty).gear == before
    assert game.inventory.count("good:lumen_berry") == 0


def test_collect_ready_kiln_yields_good_and_clears_gear():
    game = make_game()
    tx, ty = place_kiln(game)
    gear = game.world.tile(tx, ty).gear
    gear["crop_id"] = "lumen_berry"
    gear["ready_day"] = game.clock.day
    assert game.collect_kiln(tx, ty)
    assert game.inventory.count("good:lumen_berry") == 1
    gear = game.world.tile(tx, ty).gear
    assert "crop_id" not in gear and "ready_day" not in gear


def test_full_inventory_collection_keeps_kiln_loaded():
    game = make_game()
    tx, ty = place_kiln(game)
    for i, slot in enumerate(game.inventory.slots):
        game.inventory.slots[i] = {"id": "crop:crimson_tuber", "qty": game.inventory.max_stack}
    gear = game.world.tile(tx, ty).gear
    gear["crop_id"] = "lumen_berry"
    gear["ready_day"] = game.clock.day
    assert not game.collect_kiln(tx, ty)
    gear = game.world.tile(tx, ty).gear
    assert gear["crop_id"] == "lumen_berry"
    assert gear["ready_day"] == game.clock.day
    assert game.inventory.count("good:lumen_berry") == 0


def test_mutated_crops_not_offered_or_consumed():
    game = make_game()
    place_kiln(game)
    game.inventory.add("crop:lumen_berry#mut", 4)
    rows = game.kiln_rows()
    assert all(r["crop_id"] != "lumen_berry" or
               game.inventory.count("crop:lumen_berry") > 0 for r in rows)
    assert not any(r["crop_id"] == "lumen_berry" for r in rows)
    assert not game.load_kiln("lumen_berry")
    assert game.inventory.count("crop:lumen_berry#mut") == 4


def test_goods_appear_in_shop_sell_rows():
    game = make_game()
    game.inventory.add("good:lumen_berry", 1)
    game.shop_mode = "sell"
    rows = game.shop_rows()
    assert any(r["id"] == "good:lumen_berry" for r in rows)


def test_load_kiln_on_stale_gear_returns_false():
    game = make_game()
    game.kiln_pos = (10, 8)  # nothing placed there
    game.inventory.add("crop:lumen_berry", 1)
    assert not game.load_kiln("lumen_berry")
    assert game.inventory.count("crop:lumen_berry") == 1
