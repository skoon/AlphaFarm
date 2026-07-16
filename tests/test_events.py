import random

from game.events import EventSystem
from tests.helpers import make_cfg, make_moons, make_world


def make_events(seed=1):
    return EventSystem(make_cfg(), random.Random(seed)), random.Random(seed + 1)


def test_forecast_becomes_today():
    ev, rng = make_events()
    forecast = ev.forecast
    ev.advance_day(rng)
    assert ev.today == forecast
    assert ev.forecast in ("none", "spore_drift", "ion_storm", "aurora")


def test_all_events_eventually_roll():
    ev, rng = make_events()
    seen = set()
    for _ in range(300):
        ev.advance_day(rng)
        seen.add(ev.today)
    assert seen == {"none", "spore_drift", "ion_storm", "aurora"}


def test_spore_drift_fertilizes_planted_tiles():
    cfg = make_cfg()
    world = make_world(cfg)
    ev, rng = make_events()
    ev.today = "spore_drift"
    planted = world.find_kind("soil")[:12]
    for x, y in planted:
        world.till(x, y)
        world.plant(x, y, "lumen_berry")
    hit = ev.apply_morning(world, rng)
    assert hit == cfg["events"]["spore_drift_tiles"]
    boosted = sum(1 for x, y in planted if world.tile(x, y).crop.progress > 0)
    assert boosted == hit


def test_spore_drift_does_nothing_on_clear_days():
    world = make_world()
    ev, rng = make_events()
    ev.today = "none"
    assert ev.apply_morning(world, rng) == 0


def test_ion_storm_window():
    cfg = make_cfg()
    ev, _ = make_events()
    ev.today = "ion_storm"
    start = cfg["events"]["ion_storm_start_hour"]
    end = cfg["events"]["ion_storm_end_hour"]
    assert not ev.ion_storm_active(start - 0.5)
    assert ev.ion_storm_active(start + 0.5)
    assert not ev.ion_storm_active(end + 0.5)
    ev.today = "aurora"
    assert not ev.ion_storm_active(start + 0.5)


def test_aurora_doubles_growth():
    cfg = make_cfg()
    ev, _ = make_events()
    ev.today = "aurora"
    assert ev.growth_multiplier() == cfg["events"]["aurora_growth_multiplier"]
    ev.today = "none"
    assert ev.growth_multiplier() == 1.0


def test_events_save_roundtrip():
    ev, rng = make_events()
    ev.today, ev.forecast = "aurora", "ion_storm"
    ev2, _ = make_events(seed=99)
    ev2.from_dict(ev.to_dict())
    assert ev2.today == "aurora" and ev2.forecast == "ion_storm"
