import random

from game.flora import FloraSystem
from tests.helpers import make_cfg, make_moons, make_world


def make_flora(cfg=None):
    return FloraSystem(cfg or make_cfg())


def test_daily_spawn_only_on_free_grass():
    cfg = make_cfg()
    world = make_world(cfg)
    moons = make_moons(cfg)
    flora = make_flora(cfg)
    rng = random.Random(7)
    for day in range(1, 30):
        flora.daily_spawn(world, moons, day, rng)
    assert flora.wild, "nothing ever spawned"
    assert len(flora.wild) <= cfg["flora"]["max_wild_plants"]
    seen = set()
    for w in flora.wild:
        assert world.tile(w["x"], w["y"]).kind == "grass"
        assert (w["x"], w["y"]) not in seen
        seen.add((w["x"], w["y"]))


def test_crystal_species_only_spawn_near_crystals():
    cfg = make_cfg()
    world = make_world(cfg)
    moons = make_moons(cfg)
    flora = make_flora(cfg)
    rng = random.Random(11)
    for day in range(1, 120):
        flora.daily_spawn(world, moons, day, rng)
        for w in list(flora.wild):
            if flora.species[w["species"]]["set"] == "crystal":
                assert flora._near_crystal(world, w["x"], w["y"])
            if w["species"] == "sleeper_bell":
                assert moons.both_dark(day)
        flora.wild.clear()  # make room so spawning keeps happening


def test_scan_documents_once_and_removes_plant():
    flora = make_flora()
    flora.wild.append({"species": "veil_fern", "x": 3, "y": 3})
    flora.wild.append({"species": "veil_fern", "x": 4, "y": 3})
    assert flora.scan(9, 9) is None
    sid, new = flora.scan(3, 3)
    assert sid == "veil_fern" and new
    assert flora.plant_at(3, 3) is None
    sid, new = flora.scan(4, 3)
    assert sid == "veil_fern" and not new
    assert flora.codex == ["veil_fern"]


def test_set_completion_unlocks_seed():
    flora = make_flora()
    assert flora.unlocked_seed_crops() == []
    for sid in flora.set_species("meadow"):
        flora.codex.append(sid)
    assert flora.set_complete("meadow")
    assert flora.unlocked_seed_crops() == ["echo_bloom"]


def test_spore_set_has_no_unlock_seed():
    flora = make_flora()
    for sid in flora.set_species("spore"):
        flora.codex.append(sid)
    assert flora.unlocked_seed_crops() == []


def test_flora_save_roundtrip():
    flora = make_flora()
    flora.wild.append({"species": "glasswort", "x": 5, "y": 6})
    flora.codex.append("glasswort")
    flora2 = make_flora()
    flora2.from_dict(flora.to_dict())
    assert flora2.wild == flora.wild
    assert flora2.codex == ["glasswort"]
