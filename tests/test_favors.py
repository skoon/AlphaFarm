from game.crops import CropDefs
from game.favors import FavorSystem
from game.inventory import Inventory
from tests.helpers import FixedRandom, make_cfg


def make_fs():
    return FavorSystem()


NPC_IDS = ["sylla", "hux", "tinks", "care7", "juno"]


def test_new_day_generates_favor_when_roll_succeeds():
    fs = make_fs()
    defs = CropDefs()
    rng = FixedRandom(0.0, seed=1)  # 0.0 < chance_per_day always triggers
    created = fs.new_day(1, NPC_IDS, ["crimson_tuber"], rng, defs)
    assert len(created) == 1
    favor = created[0]
    assert favor["npc"] in NPC_IDS
    assert favor["crop_id"] == "crimson_tuber"
    assert fs.qty_range[0] <= favor["qty"] <= fs.qty_range[1]
    assert favor["expires_day"] == 1 + fs.duration_days
    assert str(favor["qty"]) in favor["text"]
    assert defs.get("crimson_tuber")["name"] in favor["text"]
    assert fs.active == [favor]


def test_new_day_respects_max_active_and_per_npc_uniqueness():
    fs = make_fs()
    defs = CropDefs()
    rng = FixedRandom(0.0, seed=2)
    day1 = fs.new_day(1, NPC_IDS, ["crimson_tuber", "gravity_melon"], rng, defs)
    day2 = fs.new_day(2, NPC_IDS, ["crimson_tuber", "gravity_melon"], rng, defs)
    assert len(day1) == 1 and len(day2) == 1
    assert day1[0]["npc"] != day2[0]["npc"]
    assert len(fs.active) == fs.max_active == 2
    day3 = fs.new_day(3, NPC_IDS, ["crimson_tuber", "gravity_melon"], rng, defs)
    assert day3 == []
    assert len(fs.active) == 2


def test_new_day_never_rolls_two_favors_for_same_npc():
    fs = make_fs()
    defs = CropDefs()
    rng = FixedRandom(0.0, seed=3)
    for day in range(1, 6):
        fs.new_day(day, NPC_IDS, ["crimson_tuber"], rng, defs)
    npcs_with_favors = [f["npc"] for f in fs.active]
    assert len(npcs_with_favors) == len(set(npcs_with_favors))


def test_new_day_no_favor_when_roll_fails():
    fs = make_fs()
    defs = CropDefs()
    rng = FixedRandom(1.0, seed=4)  # 1.0 is never < chance_per_day
    created = fs.new_day(1, NPC_IDS, ["crimson_tuber"], rng, defs)
    assert created == []
    assert fs.active == []


def test_expired_favors_are_dropped():
    fs = make_fs()
    defs = CropDefs()
    rng = FixedRandom(0.0, seed=5)
    fs.new_day(1, ["hux"], ["crimson_tuber"], rng, defs)
    assert len(fs.active) == 1
    expires = fs.active[0]["expires_day"]
    rng_no_new = FixedRandom(1.0, seed=6)
    fs.new_day(expires, ["hux"], ["crimson_tuber"], rng_no_new, defs)
    assert len(fs.active) == 1, "favor should still be active on its expiry day"
    fs.new_day(expires + 1, ["hux"], ["crimson_tuber"], rng_no_new, defs)
    assert fs.active == [], "favor should be gone the day after it expires"


def test_deliver_returns_none_when_short():
    fs = make_fs()
    defs = CropDefs()
    inv = Inventory(make_cfg())
    fs.active = [{"npc": "hux", "crop_id": "crimson_tuber", "qty": 3,
                 "expires_day": 5, "text": "..."}]
    inv.add("crop:crimson_tuber", 2)
    assert fs.deliver("hux", inv, defs) is None
    assert fs.deliver("someone_else", inv, defs) is None
    assert len(fs.active) == 1


def test_deliver_counts_mutated_variant_and_pays_out():
    fs = make_fs()
    defs = CropDefs()
    inv = Inventory(make_cfg())
    fs.active = [{"npc": "hux", "crop_id": "crimson_tuber", "qty": 3,
                 "expires_day": 5, "text": "..."}]
    inv.add("crop:crimson_tuber", 2)
    inv.add("crop:crimson_tuber#mut", 1)
    reward = fs.deliver("hux", inv, defs)
    assert reward is not None
    expected_credits = round(defs.sale_value("crop:crimson_tuber") * 3 * fs.reward_credit_mult)
    assert reward["credits"] == expected_credits
    assert reward["friendship"] == fs.reward_friendship
    assert reward["crop_name"] == defs.get("crimson_tuber")["name"]
    assert inv.count("crop:crimson_tuber") == 0
    assert inv.count("crop:crimson_tuber#mut") == 0
    assert fs.favor_for("hux") is None
    assert fs.active == []


def test_deliver_removes_plain_crops_before_mutated():
    fs = make_fs()
    defs = CropDefs()
    inv = Inventory(make_cfg())
    fs.active = [{"npc": "hux", "crop_id": "crimson_tuber", "qty": 2,
                 "expires_day": 5, "text": "..."}]
    inv.add("crop:crimson_tuber", 3)
    inv.add("crop:crimson_tuber#mut", 2)
    fs.deliver("hux", inv, defs)
    assert inv.count("crop:crimson_tuber") == 1
    assert inv.count("crop:crimson_tuber#mut") == 2


def test_describe_formats_lines_with_countdown():
    fs = make_fs()
    defs = CropDefs()
    fs.active = [{"npc": "hux", "crop_id": "crimson_tuber", "qty": 3,
                 "expires_day": 5, "text": "..."}]
    lines = fs.describe(defs, day=3)
    assert lines == ["Hux wants 3x Crimson Tuber (2 days left)"]


def test_describe_empty_when_no_active_favors():
    fs = make_fs()
    assert fs.describe(CropDefs(), day=1) == []


def test_to_dict_from_dict_roundtrip():
    fs = make_fs()
    defs = CropDefs()
    rng = FixedRandom(0.0, seed=7)
    fs.new_day(1, NPC_IDS, ["crimson_tuber"], rng, defs)
    fs2 = make_fs()
    fs2.from_dict(fs.to_dict())
    assert fs2.active == fs.active
