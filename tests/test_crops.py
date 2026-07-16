import random

from game.crops import Crop, CropDefs, MUT_SUFFIX
from tests.helpers import FixedRandom


def make(crop_id="lumen_berry"):
    return Crop(crop_id, CropDefs())


def test_watered_crop_grows_one_day():
    c = make()
    c.water()
    c.end_of_day(moon_full=False, aurora_mult=1.0, rng=FixedRandom(0.99))
    assert c.progress == 1.0
    assert not c.watered_today  # reset for the new day


def test_unwatered_crop_does_not_grow():
    c = make()
    c.end_of_day(moon_full=False, aurora_mult=1.0, rng=FixedRandom(0.99))
    assert c.progress == 0.0


def test_crop_ripens_after_growth_days():
    c = make("lumen_berry")  # 3 days
    for _ in range(3):
        assert not c.ripe
        c.water()
        c.end_of_day(False, 1.0, FixedRandom(0.99))
    assert c.ripe


def test_moon_bonus_and_aurora_stack():
    c = make("lumen_berry")  # ilo affinity, growth_bonus 0.5
    c.water()
    c.end_of_day(moon_full=True, aurora_mult=2.0, rng=FixedRandom(0.99))
    assert c.progress == (1.0 + 0.5) * 2.0


def test_full_moon_can_mutate():
    c = make("lumen_berry")
    c.water()
    c.end_of_day(moon_full=True, aurora_mult=1.0, rng=FixedRandom(0.0))
    assert c.mutated
    assert c.harvest_item().endswith(MUT_SUFFIX)


def test_no_mutation_without_full_moon():
    c = make("lumen_berry")
    c.water()
    c.end_of_day(moon_full=False, aurora_mult=1.0, rng=FixedRandom(0.0))
    assert not c.mutated


def test_prism_pod_wilts_if_not_watered():
    c = make("prism_pod")
    c.end_of_day(False, 1.0, FixedRandom(0.99))
    assert c.wilted


def test_prism_pod_wilts_if_watered_twice():
    c = make("prism_pod")
    c.water()
    assert not c.wilted
    c.water()
    assert c.wilted


def test_prism_pod_thrives_on_exactly_one_watering():
    c = make("prism_pod")
    c.water()
    c.end_of_day(False, 1.0, FixedRandom(0.99))
    assert not c.wilted and c.progress == 1.0


def test_normal_crop_survives_double_watering():
    c = make("lumen_berry")
    c.water()
    c.water()
    assert not c.wilted


def test_fertilize_does_not_count_as_watering():
    c = make("prism_pod")
    c.fertilize(0.5)
    assert c.progress == 0.5
    assert c.water_count_today == 0


def test_wilted_crop_stops_growing():
    c = make("lumen_berry")
    c.wilted = True
    c.water()
    c.end_of_day(False, 1.0, FixedRandom(0.99))
    assert c.progress == 0.0
    assert not c.ripe


def test_crop_save_roundtrip():
    defs = CropDefs()
    c = make("gravity_melon")
    c.progress = 3.5
    c.mutated = True
    c2 = Crop.from_dict(c.to_dict(), defs)
    assert c2.crop_id == "gravity_melon"
    assert c2.progress == 3.5 and c2.mutated


def test_sale_values_and_names():
    defs = CropDefs()
    assert defs.sale_value("crop:lumen_berry") == 35
    assert defs.sale_value("crop:lumen_berry" + MUT_SUFFIX) == 35 * 3
    assert defs.sale_value("seed:lumen_berry") == 0
    assert defs.item_name("crop:lumen_berry") == "Lumen Berry"
    assert defs.item_name("crop:lumen_berry" + MUT_SUFFIX) == "Aurora Lumen Berry"
    assert defs.item_name("seed:lumen_berry") == "Lumen Berry Seeds"


def test_starter_ids_exclude_locked_crops():
    starters = CropDefs().starter_ids()
    assert "lumen_berry" in starters and "prism_pod" in starters
    assert "echo_bloom" not in starters and "dream_lotus" not in starters
