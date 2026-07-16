import random

from game.crops import CropDefs
from tests.helpers import FixedRandom, make_cfg, make_moons, make_world, no_full_moon_day


def soil_pos(world):
    return world.find_kind("soil")[0]


def grow_to_ripe(world, moons, x, y, rng=None):
    rng = rng or FixedRandom(0.99)
    crop = world.tile(x, y).crop
    day = no_full_moon_day(make_moons())
    while not crop.ripe:
        world.water(x, y)
        world.end_of_day(moons, day, 1.0, rng)


def test_map_loads_with_expected_features():
    world = make_world()
    assert world.width == 40 and world.height == 30
    for kind in ("soil", "grass", "rock", "crystal", "great_crystal",
                 "habitat_door", "terminal", "shipping_pod", "landing_pad"):
        assert world.find_kind(kind), f"map has no {kind}"
    assert not world.tile(*world.player_start).solid


def test_till_plant_water_harvest_loop():
    world = make_world()
    moons = make_moons()
    x, y = soil_pos(world)
    assert not world.plant(x, y, "lumen_berry")  # must till first
    assert world.till(x, y)
    assert world.plant(x, y, "lumen_berry")
    assert not world.plant(x, y, "lumen_berry")  # occupied
    assert world.harvest(x, y, FixedRandom(0.99)) is None  # not ripe
    grow_to_ripe(world, moons, x, y)
    result = world.harvest(x, y, FixedRandom(0.99))
    assert result is not None
    item, qty = result
    assert item == "crop:lumen_berry" and qty == 1
    assert world.tile(x, y).crop is None


def test_cannot_till_grass_or_rock():
    world = make_world()
    gx, gy = world.find_kind("grass")[0]
    rx, ry = world.find_kind("rock")[0]
    assert not world.till(gx, gy)
    assert not world.till(rx, ry)


def test_high_resonance_can_double_yield():
    world = make_world()
    moons = make_moons()
    x, y = soil_pos(world)
    world.till(x, y)
    world.plant(x, y, "lumen_berry")
    world.tile(x, y).resonance = 1.0
    grow_to_ripe(world, moons, x, y)
    _, qty = world.harvest(x, y, FixedRandom(0.0))
    assert qty == 2


def test_monoculture_lowers_resonance_and_rotation_raises_it():
    cfg = make_cfg()
    world = make_world(cfg)
    moons = make_moons(cfg)
    x, y = soil_pos(world)
    start = world.tile(x, y).resonance

    world.till(x, y)
    world.plant(x, y, "lumen_berry")
    grow_to_ripe(world, moons, x, y)
    world.harvest(x, y, FixedRandom(0.99))
    after_first = world.tile(x, y).resonance
    assert after_first > start  # first harvest counts as rotation

    world.plant(x, y, "lumen_berry")  # same family again
    grow_to_ripe(world, moons, x, y)
    world.harvest(x, y, FixedRandom(0.99))
    assert world.tile(x, y).resonance < after_first

    before = world.tile(x, y).resonance
    world.plant(x, y, "crimson_tuber")  # rotate families
    grow_to_ripe(world, moons, x, y)
    world.harvest(x, y, FixedRandom(0.99))
    assert world.tile(x, y).resonance > before


def test_resonance_stays_clamped():
    cfg = make_cfg()
    world = make_world(cfg)
    x, y = soil_pos(world)
    t = world.tile(x, y)
    t.resonance = cfg["resonance"]["min"]
    t.last_family = "berry"
    world.till(x, y)
    world.plant(x, y, "lumen_berry")
    grow_to_ripe(world, make_moons(cfg), x, y)
    world.harvest(x, y, FixedRandom(0.99))
    assert t.resonance >= cfg["resonance"]["min"]


def test_fallow_soil_drifts_back_to_baseline():
    cfg = make_cfg()
    world = make_world(cfg)
    moons = make_moons(cfg)
    x, y = soil_pos(world)
    t = world.tile(x, y)
    t.resonance = 0.2
    world.end_of_day(moons, 1, 1.0, FixedRandom(0.99))
    assert t.resonance > 0.2
    t.resonance = 0.9
    world.end_of_day(moons, 1, 1.0, FixedRandom(0.99))
    assert t.resonance < 0.9


def test_hoe_clears_wilted_crop():
    world = make_world()
    x, y = soil_pos(world)
    world.till(x, y)
    world.plant(x, y, "prism_pod")
    world.end_of_day(make_moons(), 1, 1.0, FixedRandom(0.99))  # unwatered -> wilts
    assert world.tile(x, y).crop.wilted
    assert world.harvest(x, y, FixedRandom(0.99)) is None  # harvest clears, yields nothing
    assert world.tile(x, y).crop is None


def test_watering_clears_overnight():
    world = make_world()
    x, y = soil_pos(world)
    world.till(x, y)
    world.water(x, y)
    assert world.tile(x, y).watered
    world.end_of_day(make_moons(), 1, 1.0, FixedRandom(0.99))
    assert not world.tile(x, y).watered


def test_world_save_roundtrip():
    cfg = make_cfg()
    defs = CropDefs()
    world = make_world(cfg, defs)
    x, y = soil_pos(world)
    world.till(x, y)
    world.plant(x, y, "whisper_wheat")
    world.water(x, y)
    world.tile(x, y).resonance = 0.77

    world2 = make_world(cfg, defs)
    world2.from_dict(world.to_dict())
    t = world2.tile(x, y)
    assert t.tilled and t.watered
    assert t.crop.crop_id == "whisper_wheat"
    assert t.resonance == 0.77
