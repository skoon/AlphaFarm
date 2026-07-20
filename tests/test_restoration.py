from game.config import load_config
from game.inventory import Inventory
from game.restoration import RestorationSystem


def make_inv():
    return Inventory(load_config())


def test_bundles_locked_until_quest_finished():
    r = RestorationSystem()
    assert r.available(quest_finished=False) == []
    assert len(r.available(quest_finished=True)) == 5


def test_needs_status_and_can_offer():
    r = RestorationSystem()
    inv = make_inv()
    assert not r.can_offer("first_fruits", inv)
    inv.add("crop:lumen_berry", 8)
    inv.add("crop:whisper_wheat", 5)
    inv.add("crop:crimson_tuber", 5)
    status = dict((n, (have, need)) for n, have, need in
                  r.needs_status("first_fruits", inv))
    assert status["crop:lumen_berry"] == (8, 8)
    assert r.can_offer("first_fruits", inv)


def test_offer_consumes_items_and_grants_buff():
    r = RestorationSystem()
    inv = make_inv()
    inv.add("crop:lumen_berry", 10)
    inv.add("crop:whisper_wheat", 5)
    inv.add("crop:crimson_tuber", 5)
    bundle = r.offer("first_fruits", inv)
    assert bundle is not None and bundle["buff"]["type"] == "energy_max"
    assert inv.count("crop:lumen_berry") == 2      # only the needed 8 consumed
    assert inv.count("crop:whisper_wheat") == 0
    assert "first_fruits" in r.completed
    assert r.buff("energy_max") == 10
    assert r.offer("first_fruits", inv) is None    # once only


def test_mutated_any_counts_and_consumes_across_variants():
    r = RestorationSystem()
    inv = make_inv()
    inv.add("crop:lumen_berry#mut", 2)
    inv.add("crop:prism_pod#mut", 3)
    status = dict((n, (have, need)) for n, have, need in
                  r.needs_status("moonlit_harvest", inv))
    assert status["mutated:any"] == (5, 4)
    assert r.offer("moonlit_harvest", inv) is not None
    total_mut = sum(s["qty"] for s in inv.items() if s["id"].endswith("#mut"))
    assert total_mut == 1
    assert r.buff("growth_rate") == 0.15


def test_buffs_aggregate_and_all_complete():
    r = RestorationSystem()
    assert r.buff("sell_bonus", default=0.0) == 0.0
    r.completed = list(r.bundles)
    assert r.all_complete()
    assert r.buff("energy_max") == 10
    assert r.buff("aurora_weight") == 12


def test_save_roundtrip():
    r = RestorationSystem()
    inv = make_inv()
    inv.add("mineral:ferrite", 6)
    inv.add("mineral:lumite", 4)
    inv.add("mineral:quartz", 2)
    r.offer("deep_gifts", inv)
    r2 = RestorationSystem()
    r2.from_dict(r.to_dict())
    assert r2.completed == ["deep_gifts"]
    assert r2.buff("soil_recovery") == 3.0
