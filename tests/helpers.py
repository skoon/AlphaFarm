"""Shared test fixtures/helpers."""
from __future__ import annotations

import random

from game.config import load_config
from game.crops import CropDefs
from game.time_system import Moons
from game.world import World


class FixedRandom(random.Random):
    """random() always returns the given value; other methods stay seeded-deterministic."""

    def __init__(self, value: float, seed: int = 1):
        super().__init__(seed)
        self.value = value

    def random(self) -> float:  # type: ignore[override]
        return self.value


def make_cfg() -> dict:
    return load_config()


def make_world(cfg=None, defs=None) -> World:
    cfg = cfg or make_cfg()
    return World(cfg, defs or CropDefs())


def make_moons(cfg=None) -> Moons:
    return Moons(cfg or make_cfg())


def no_full_moon_day(moons: Moons) -> int:
    for day in range(1, 20):
        if not moons.is_full("ilo", day) and not moons.is_full("vesk", day):
            return day
    raise AssertionError("no moonless day found")


def full_moon_day(moons: Moons, moon: str) -> int:
    for day in range(1, 20):
        if moons.is_full(moon, day):
            return day
    raise AssertionError(f"no full {moon} day found")
