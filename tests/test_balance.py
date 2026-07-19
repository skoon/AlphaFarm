"""Economy sanity checks: growth is always profitable, processing beats raw selling,
upgrades are priced as mid-game goals rather than day-one purchases."""
from game.config import load_config, load_json
from game.crops import CropDefs


def test_every_crop_sells_above_seed_cost():
    defs = CropDefs()
    for cid, d in defs.defs.items():
        if d["seed_price"] > 0:
            assert d["sell_value"] >= d["seed_price"] * 1.4, \
                f"{cid}: sell {d['sell_value']} too low for seed {d['seed_price']}"


def test_longer_crops_pay_more_per_day():
    defs = CropDefs()
    quick = defs.get("lumen_berry")
    slow = defs.get("prism_pod")
    assert slow["sell_value"] / slow["growth_days"] > \
        quick["sell_value"] / quick["growth_days"]


def test_every_recipe_is_worth_the_wait():
    defs = CropDefs()
    for cid, r in defs.recipes.items():
        sell = defs.get(cid)["sell_value"]
        assert 2.0 <= r["value"] / sell <= 3.5, \
            f"{cid}: good value {r['value']} vs raw {sell} out of the 2x-3.5x band"
        assert 1 <= r["days"] <= 5


def test_upgrades_are_mid_game_purchases():
    gear = load_json("upgrades.json")
    start = load_config()["player"]["start_credits"]
    for uid, u in gear.items():
        assert u["price"] > start, f"{uid} affordable on day one"
        assert u["price"] <= 2000, f"{uid} priced out of a normal playthrough"
        assert u["max"] >= 1


def test_goods_and_gear_item_registry():
    defs = CropDefs()
    assert defs.item_name("good:prism_pod") == "Focusing Lens"
    assert defs.sale_value("good:prism_pod") == defs.recipes["prism_pod"]["value"]
    assert defs.item_name("gear:drone") == "Irrigation Drone"
    assert defs.sale_value("gear:drone") == 0
