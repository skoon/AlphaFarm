import random

from game.crops import CropDefs
from game.config import load_config
from game.inventory import ShippingBin
from game.particles import MAX_PARTICLES, Particles
from game.render import time_tint


def test_burst_particles_age_and_die():
    p = Particles()
    p.burst("soil", 100, 100, random.Random(1))
    assert len(p.parts) == 8
    for _ in range(120):
        p.update(1 / 60)
    assert p.parts == []


def test_particle_pool_is_capped():
    p = Particles()
    rng = random.Random(1)
    for _ in range(80):
        p.burst("sparkle", 50, 50, rng)
    assert len(p.parts) <= MAX_PARTICLES


def test_float_text_rises_and_expires():
    p = Particles()
    p.float_text("+1 Lumen Berry", 64, 64)
    y0 = p.texts[0]["y"]
    p.update(0.5)
    assert p.texts[0]["y"] < y0
    p.update(1.0)
    assert p.texts == []


def test_shipping_manifest_matches_payout():
    cfg = load_config()
    defs = CropDefs()
    bin_ = ShippingBin()
    bin_.add("crop:lumen_berry", 3)
    bin_.add("crop:prism_pod", 1)
    manifest = bin_.manifest(defs)
    income = bin_.process_overnight(defs)
    expected = defs.sale_value("crop:lumen_berry") * 3 + defs.sale_value("crop:prism_pod")
    assert sum(v for _, _, v in manifest) == expected == income
    assert bin_.contents == {}


def test_time_tint_curve():
    color_dawn = time_tint(6.2)
    assert color_dawn is not None and color_dawn[1] > 0
    assert time_tint(12.0) is None
    color_dusk = time_tint(18.5)
    assert color_dusk is not None and color_dusk[1] > 0
    late = time_tint(25.0)
    assert late is None  # deep night: darkness overlay owns the look
