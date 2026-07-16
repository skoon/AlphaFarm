from game.crops import CropDefs, MUT_SUFFIX
from game.inventory import Inventory, ShippingBin
from tests.helpers import make_cfg


def make_inv():
    return Inventory(make_cfg())


def test_add_stacks_and_counts():
    inv = make_inv()
    assert inv.add("crop:lumen_berry", 5) == 0
    assert inv.add("crop:lumen_berry", 7) == 0
    assert inv.count("crop:lumen_berry") == 12
    assert len(inv.items()) == 1


def test_stack_overflow_spills_to_new_slot():
    inv = make_inv()
    inv.add("crop:lumen_berry", inv.max_stack)
    inv.add("crop:lumen_berry", 1)
    assert inv.count("crop:lumen_berry") == inv.max_stack + 1
    assert len(inv.items()) == 2


def test_full_inventory_returns_leftover():
    inv = make_inv()
    for i in range(inv.size):
        inv.add(f"crop:item{i}", inv.max_stack)
    leftover = inv.add("crop:overflow", 5)
    assert leftover == 5


def test_remove_across_stacks():
    inv = make_inv()
    inv.add("seed:whisper_wheat", inv.max_stack)
    inv.add("seed:whisper_wheat", 10)
    assert inv.remove("seed:whisper_wheat", inv.max_stack + 5)
    assert inv.count("seed:whisper_wheat") == 5


def test_remove_fails_without_enough():
    inv = make_inv()
    inv.add("crop:prism_pod", 2)
    assert not inv.remove("crop:prism_pod", 3)
    assert inv.count("crop:prism_pod") == 2  # unchanged


def test_seed_ids_held():
    inv = make_inv()
    inv.add("seed:lumen_berry", 3)
    inv.add("crop:lumen_berry", 3)
    inv.add("seed:prism_pod", 1)
    assert inv.seed_ids_held() == ["lumen_berry", "prism_pod"]


def test_inventory_save_roundtrip():
    inv = make_inv()
    inv.add("crop:gravity_melon", 4)
    inv2 = make_inv()
    inv2.from_dict(inv.to_dict())
    assert inv2.count("crop:gravity_melon") == 4
    assert len(inv2.slots) == inv2.size


def test_shipping_bin_pays_out_and_empties():
    defs = CropDefs()
    bin_ = ShippingBin()
    bin_.add("crop:lumen_berry", 2)               # 2 x 35
    bin_.add("crop:prism_pod" + MUT_SUFFIX, 1)    # 320 x 3
    assert bin_.process_overnight(defs) == 2 * 35 + 320 * 3
    assert bin_.contents == {}
    assert bin_.process_overnight(defs) == 0
