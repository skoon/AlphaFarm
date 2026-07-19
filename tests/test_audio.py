"""Headless audio tests. Uses the SDL dummy audio driver so no device is needed,
mirroring how tests/smoke.py sets SDL_VIDEODRIVER for video."""
import os
import struct
import wave

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

import game.audio as audio  # noqa: E402
from game.config import ASSET_DIR, load_config  # noqa: E402

AUDIO_DIR = ASSET_DIR / "audio"

SFX = ("hoe", "water", "plant", "harvest", "credits", "blip", "gift", "sleep", "quest")
LOOPS = ("storm_loop", "ambient_day", "ambient_night")
ALL_WAVS = (*SFX, *LOOPS)


def test_all_wavs_exist_with_expected_format():
    assert len(ALL_WAVS) == 12
    for name in ALL_WAVS:
        path = AUDIO_DIR / f"{name}.wav"
        assert path.exists(), f"missing {path}"
        with wave.open(str(path), "rb") as w:
            assert w.getnchannels() == 1, f"{name} not mono"
            assert w.getsampwidth() == 2, f"{name} not 16-bit"
            assert w.getframerate() == 22050, f"{name} wrong sample rate"
            assert w.getnframes() > 0, f"{name} empty"


def test_loopable_files_have_near_zero_endpoints():
    for name in LOOPS:
        with wave.open(str(AUDIO_DIR / f"{name}.wav"), "rb") as w:
            frames = w.readframes(w.getnframes())
        first = struct.unpack("<h", frames[:2])[0]
        last = struct.unpack("<h", frames[-2:])[0]
        assert abs(first) < 500, f"{name} first sample {first} not near zero"
        assert abs(last) < 500, f"{name} last sample {last} not near zero"


def test_init_and_playback_do_not_raise():
    cfg = load_config()
    try:
        ok = audio.init(cfg)
        # Under the dummy driver init should normally succeed, but the API must
        # be robust regardless of the returned value.
        assert isinstance(ok, bool)
        audio.play("harvest")
        audio.play("does_not_exist")  # unknown name must be a safe no-op
        audio.set_ambient("ambient_day")
        audio.set_ambient("ambient_day")  # same track -> no-op
        audio.set_ambient("ambient_night")  # switch
        audio.set_weather("storm_loop")
        audio.set_weather(None)  # stop
        audio.set_ambient(None)
    finally:
        audio.shutdown()
        audio.shutdown()  # double shutdown must also be safe


def test_disabled_config_returns_false_and_noops():
    cfg = load_config()
    cfg = {**cfg, "audio": {**cfg.get("audio", {}), "enabled": False}}
    try:
        assert audio.init(cfg) is False
        # Every call is a silent no-op when disabled.
        audio.play("harvest")
        audio.set_ambient("ambient_day")
        audio.set_weather("storm_loop")
    finally:
        audio.shutdown()


def teardown_module(_module):
    if pygame.mixer.get_init() is not None:
        pygame.mixer.quit()
