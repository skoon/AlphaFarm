import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

import main as m  # noqa: E402
from game.config import load_config  # noqa: E402
from game.crops import CropDefs  # noqa: E402
from game.fauna import FLEE_TIME, WANDER_SPEED, FaunaSystem  # noqa: E402
from game.world import World  # noqa: E402


def make_game():
    m.load_game = lambda *a: None
    m.save_game = lambda *a: None
    if not pygame.get_init():
        pygame.init()
    return m.Game()


def make_worlds():
    cfg, defs = load_config(), CropDefs()
    return {"farm": World(cfg, defs, map_name="map"),
            "mine": World(cfg, defs, map_name="mine")}


def open_tile(world, margin=2):
    """A walkable tile whose 8 neighbours are all walkable too."""
    for y in range(margin, world.height - margin):
        for x in range(margin, world.width - margin):
            if all(not world.is_solid(x + dx, y + dy)
                   for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                return x, y
    raise AssertionError("no open tile found")


def test_caps_and_farm_night_only():
    fauna = FaunaSystem()
    worlds = make_worlds()
    rng = random.Random(0)

    # Daytime in the mine: mine fills to cap, farm stays empty.
    for _ in range(20):
        fauna.update(0.05, worlds, "mine", (2.0, 8.0), hour=12.0, rng=rng)
    assert fauna._count("mine") == 4
    assert fauna._count("farm") == 0

    # Night on the farm: farm now fills to cap as well.
    for _ in range(20):
        fauna.update(0.05, worlds, "farm", (3.0, 3.0), hour=22.0, rng=rng)
    assert fauna._count("farm") == 4
    assert fauna._count("mine") == 4

    # Back to daylight: farm critters slip away, the mine keeps its own.
    fauna.update(0.05, worlds, "farm", (3.0, 3.0), hour=12.0, rng=rng)
    assert fauna._count("farm") == 0
    assert fauna._count("mine") == 4


def test_critters_never_stand_on_solid_tiles():
    fauna = FaunaSystem()
    worlds = make_worlds()
    rng = random.Random(3)
    for i in range(400):
        map_id = "mine" if i % 2 else "farm"
        px, py = 5.0 + (i % 7), 5.0 + (i % 5)
        fauna.update(0.08, worlds, map_id, (px, py), hour=22.0, rng=rng)
        for c in fauna.critters:
            world = worlds[c["map"]]
            assert not world.is_solid(int(c["x"]), int(c["y"])), (c, i)


def test_skittish_flees_away_from_player():
    fauna = FaunaSystem()
    worlds = make_worlds()
    rng = random.Random(7)
    ox, oy = open_tile(worlds["farm"])
    critter = {"species": "hollow_wisp", "map": "farm",
               "x": ox + 0.5, "y": oy + 0.5, "vx": WANDER_SPEED, "vy": 0.0, "shy_t": 0.0}
    fauna.critters.append(critter)
    # Player one tile east -> the critter should bolt west, fast.
    fauna.update(0.02, worlds, "farm", (ox + 1.5, oy + 0.5), hour=22.0, rng=rng)
    assert critter["shy_t"] == FLEE_TIME
    assert critter["vx"] < 0
    speed = (critter["vx"] ** 2 + critter["vy"] ** 2) ** 0.5
    assert speed > WANDER_SPEED * 1.5


def test_scan_documents_once():
    fauna = FaunaSystem()
    sid = "hollow_wisp"
    fauna.critters.append({"species": sid, "map": "farm",
                           "x": 5.5, "y": 5.5, "vx": 0.0, "vy": 0.0, "shy_t": 0.0})
    assert fauna.scan("farm", 5, 5) == (sid, True)
    assert fauna.codex == [sid]
    # It darts but is not captured -> still scannable, now already documented.
    assert fauna.scan("farm", 5, 5) == (sid, False)
    assert fauna.scan("mine", 5, 5) is None          # wrong map
    assert fauna.scan("farm", 20, 20) is None         # out of range


def test_set_completion_and_reward_via_use_tool():
    game = make_game()
    game.player.tool = "scanner"
    game.player.x, game.player.y = 10.5, 10.0
    game.player.facing = (1, 0)                       # target tile (11, 10)
    for sid in list(game.fauna.species):
        game.fauna.critters.clear()
        game.fauna.critters.append({"species": sid, "map": game.map_id,
                                    "x": 11.5, "y": 10.0, "vx": 0.0, "vy": 0.0,
                                    "shy_t": 0.0})
        game.player.energy = game.player.max_energy
        game.use_tool()
    assert game.fauna.set_complete()
    assert game.fauna.reward_claimed
    assert game.inventory.count(f"seed:{game.fauna.reward_seed}") == game.fauna.reward_count
    assert game.fauna.claim_reward() is None          # reward pays out exactly once


def test_to_from_dict_roundtrip():
    fauna = FaunaSystem()
    fauna.codex = ["hollow_wisp", "gloom_weaver"]
    fauna.reward_claimed = True
    fauna.critters.append({"species": "coil_warden", "map": "mine",
                           "x": 1.0, "y": 1.0, "vx": 0.0, "vy": 0.0, "shy_t": 0.0})
    d = fauna.to_dict()
    assert set(d) == {"codex", "reward_claimed"}

    restored = FaunaSystem()
    restored.from_dict(d)
    assert restored.codex == ["hollow_wisp", "gloom_weaver"]
    assert restored.reward_claimed is True
    assert restored.critters == []                    # transient, never persisted
