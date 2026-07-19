"""Runtime audio: one-shot SFX and looping ambient/weather beds.

Module-level state, module-level functions. Everything is defensive: if audio
is disabled in config, the mixer fails to init, or WAV files are missing, the
module flips a disabled flag and every function no-ops silently. Nothing here
ever raises out to the caller.

Wired by main.py roughly as:
    import game.audio as audio
    audio.init(cfg)
    audio.play("harvest")
    audio.set_ambient("ambient_day")
    audio.set_weather("storm_loop")   # or None to clear
    audio.shutdown()
"""
from __future__ import annotations

import pygame

from game.config import ASSET_DIR

# Base names loaded from assets/audio/<name>.wav.
_SFX_NAMES = (
    "hoe", "water", "plant", "harvest", "credits",
    "blip", "gift", "sleep", "quest",
)
_LOOP_NAMES = ("storm_loop", "ambient_day", "ambient_night")

# --- module state ---------------------------------------------------------- #
_enabled = False          # True only after a fully successful init()
_master = 1.0
_music_vol = 1.0
_sfx_vol = 1.0
_sounds: dict[str, pygame.mixer.Sound] = {}
_ambient_channel: pygame.mixer.Channel | None = None
_weather_channel: pygame.mixer.Channel | None = None
_ambient_name: str | None = None
_weather_name: str | None = None


def init(cfg: dict) -> bool:
    """Initialize the mixer and load every WAV. Returns True on success.

    On any problem (disabled in config, mixer init failure, missing files) the
    module is left disabled and every other function becomes a silent no-op.
    """
    global _enabled, _master, _music_vol, _sfx_vol
    global _ambient_channel, _weather_channel

    _enabled = False
    _sounds.clear()

    audio_cfg = (cfg or {}).get("audio", {}) or {}
    if not audio_cfg.get("enabled", False):
        return False

    _master = float(audio_cfg.get("master_volume", 1.0))
    _music_vol = float(audio_cfg.get("music_volume", 1.0))
    _sfx_vol = float(audio_cfg.get("sfx_volume", 1.0))

    try:
        if pygame.mixer.get_init() is None:
            pygame.mixer.pre_init(frequency=22050, size=-16, channels=1, buffer=512)
            pygame.mixer.init()
        # Two extra dedicated channels for the ambient and weather loops.
        base = pygame.mixer.get_num_channels()
        pygame.mixer.set_num_channels(base + 2)
        _ambient_channel = pygame.mixer.Channel(base)
        _weather_channel = pygame.mixer.Channel(base + 1)
    except pygame.error:
        _reset_state()
        return False

    audio_dir = ASSET_DIR / "audio"
    try:
        for name in (*_SFX_NAMES, *_LOOP_NAMES):
            path = audio_dir / f"{name}.wav"
            if not path.exists():
                _reset_state()
                return False
            _sounds[name] = pygame.mixer.Sound(str(path))
    except pygame.error:
        _reset_state()
        return False

    _enabled = True
    return True


def play(name: str) -> None:
    """Play a one-shot SFX by base name at master * sfx volume."""
    if not _enabled:
        return
    snd = _sounds.get(name)
    if snd is None:
        return
    try:
        snd.set_volume(_master * _sfx_vol)
        snd.play()
    except pygame.error:
        pass


def set_ambient(name: str | None) -> None:
    """Loop the named ambient track on the ambient channel (None stops it)."""
    global _ambient_name
    _ambient_name = _set_loop(_ambient_channel, _ambient_name, name)


def set_weather(name: str | None) -> None:
    """Loop the named weather track on the weather channel (None stops it)."""
    global _weather_name
    _weather_name = _set_loop(_weather_channel, _weather_name, name)


def shutdown() -> None:
    """Stop channels and quit the mixer. Safe even if init failed/never ran."""
    global _ambient_name, _weather_name
    try:
        if _ambient_channel is not None:
            _ambient_channel.stop()
        if _weather_channel is not None:
            _weather_channel.stop()
    except pygame.error:
        pass
    try:
        if pygame.mixer.get_init() is not None:
            pygame.mixer.quit()
    except pygame.error:
        pass
    _ambient_name = None
    _weather_name = None
    _reset_state()


# --- internals ------------------------------------------------------------- #
def _reset_state() -> None:
    global _enabled, _ambient_channel, _weather_channel
    _enabled = False
    _ambient_channel = None
    _weather_channel = None
    _sounds.clear()


def _set_loop(
    channel: pygame.mixer.Channel | None,
    current: str | None,
    name: str | None,
) -> str | None:
    """Shared logic for the ambient/weather loops. Returns the new track name."""
    if not _enabled or channel is None:
        return current
    if name == current:
        return current  # already playing (or already stopped)

    try:
        if current is not None:
            playing = _sounds.get(current)
            if playing is not None:
                playing.fadeout(250)  # short fade to avoid a hard cut
            channel.stop()
        if name is None:
            return None
        snd = _sounds.get(name)
        if snd is None:
            return current
        snd.set_volume(_master * _music_vol)
        channel.play(snd, loops=-1)
        return name
    except pygame.error:
        return current
