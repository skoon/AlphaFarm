from game.time_system import GameClock, Moons
from tests.helpers import make_cfg


def test_clock_advances_with_real_time():
    cfg = make_cfg()
    clock = GameClock(cfg)
    day_len = cfg["time"]["day_length_real_seconds"]
    span = cfg["time"]["day_end_hour"] - cfg["time"]["day_start_hour"]
    assert clock.hour == cfg["time"]["day_start_hour"]
    clock.update(day_len / span)  # one in-game hour of real time
    assert abs(clock.hour - (cfg["time"]["day_start_hour"] + 1.0)) < 1e-6


def test_clock_signals_day_end():
    cfg = make_cfg()
    clock = GameClock(cfg)
    assert not clock.update(0.01)
    assert clock.update(cfg["time"]["day_length_real_seconds"])


def test_clock_text_wraps_past_midnight():
    clock = GameClock(make_cfg())
    clock.hour = 25.5
    assert clock.clock_text() == "01:30"
    clock.hour = 6.0
    assert clock.clock_text() == "06:00"


def test_darkness_ramps_and_caps():
    cfg = make_cfg()
    clock = GameClock(cfg)
    clock.hour = cfg["time"]["night_start_hour"] - 1
    assert clock.darkness() == 0
    clock.hour = cfg["time"]["night_full_hour"] + 1
    assert clock.darkness() == cfg["time"]["max_night_darkness"]
    clock.hour = (cfg["time"]["night_start_hour"] + cfg["time"]["night_full_hour"]) / 2
    assert 0 < clock.darkness() < cfg["time"]["max_night_darkness"]


def test_start_new_day_resets_hour():
    clock = GameClock(make_cfg())
    clock.hour = 25.0
    clock.start_new_day()
    assert clock.day == 2
    assert clock.hour == clock.day_start


def test_clock_save_roundtrip():
    clock = GameClock(make_cfg())
    clock.day, clock.hour = 7, 13.25
    other = GameClock(make_cfg())
    other.from_dict(clock.to_dict())
    assert other.day == 7 and other.hour == 13.25


def test_moon_phases_cycle_every_8_days():
    moons = Moons(make_cfg())
    for moon in ("ilo", "vesk"):
        assert moons.phase(moon, 1) == moons.phase(moon, 1 + moons.cycle)
        phases = {moons.phase(moon, d) for d in range(1, moons.cycle + 1)}
        assert phases == set(range(moons.cycle))


def test_moons_are_offset_from_each_other():
    moons = Moons(make_cfg())
    assert any(moons.phase("ilo", d) != moons.phase("vesk", d) for d in range(1, 9))


def test_full_moon_days_exist_for_both_moons():
    moons = Moons(make_cfg())
    for moon in ("ilo", "vesk"):
        assert any(moons.is_full(moon, d) for d in range(1, moons.cycle + 1))


def test_both_dark_occurs_within_a_cycle():
    moons = Moons(make_cfg())
    dark_days = [d for d in range(1, moons.cycle + 1) if moons.both_dark(d)]
    assert dark_days, "sleeper bell would never bloom"
    for d in dark_days:
        assert moons.phase("ilo", d) in moons.dark_phases
        assert moons.phase("vesk", d) in moons.dark_phases
