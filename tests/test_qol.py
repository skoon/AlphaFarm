import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

import game.audio as audio  # noqa: E402
import game.save_load as sl  # noqa: E402
import main as m  # noqa: E402


def make_game():
    m.load_game = lambda *a: None
    m.save_game = lambda *a: None
    if not pygame.get_init():
        pygame.init()
    return m.Game()


def test_slot_paths_are_distinct_and_summary_reads_saves(tmp_path, monkeypatch):
    monkeypatch.setattr(sl, "SAVE_DIR", tmp_path)
    paths = {sl.slot_path(n) for n in (1, 2, 3)}
    assert len(paths) == 3
    assert sl.slot_summary(2) is None
    sl.save_game({"clock": {"day": 7, "hour": 8.0}, "player": {"credits": 321}},
                 sl.slot_path(2))
    assert sl.slot_summary(2) == {"day": 7, "credits": 321}


def test_slot_summary_survives_corrupt_file(tmp_path, monkeypatch):
    monkeypatch.setattr(sl, "SAVE_DIR", tmp_path)
    sl.slot_path(1).write_text("{not json")
    assert sl.slot_summary(1) is None


def test_migrate_legacy_moves_old_save_once(tmp_path, monkeypatch):
    monkeypatch.setattr(sl, "SAVE_DIR", tmp_path)
    legacy = tmp_path / "savegame.json"
    monkeypatch.setattr(sl, "SAVE_PATH", legacy)
    legacy.write_text('{"version": 2, "clock": {"day": 4, "hour": 6.0}, '
                      '"player": {"credits": 9}}')
    sl.migrate_legacy()
    assert not legacy.exists()
    assert sl.slot_summary(1) == {"day": 4, "credits": 9}
    sl.migrate_legacy()   # no-op when slot 1 exists
    assert sl.slot_summary(1) == {"day": 4, "credits": 9}


def test_escape_pauses_instead_of_quitting():
    game = make_game()
    game.handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert game.mode == "pause" and game.running
    game.handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert game.mode == "play"


def test_pause_quit_rows_set_flags():
    game = make_game()
    game.mode = "pause"
    game.pause_action("Quit to Title")
    assert not game.running and game.to_title
    game2 = make_game()
    game2.mode = "pause"
    game2.pause_action("Quit Game")
    assert not game2.running and not game2.to_title


def test_pause_freezes_the_clock():
    game = make_game()
    game.mode = "pause"
    hour = game.clock.hour
    game.update(1.0)
    assert game.clock.hour == hour


def test_volume_adjust_persists_to_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(audio, "SETTINGS_PATH", tmp_path / "settings.json")
    audio.set_volumes(master=0.5, music=0.3, sfx=0.7)
    assert audio.get_volumes() == (0.5, 0.3, 0.7)
    saved = json.loads((tmp_path / "settings.json").read_text())
    assert saved == {"master_volume": 0.5, "music_volume": 0.3, "sfx_volume": 0.7}
    audio.set_volumes(master=1.5)   # clamped
    assert audio.get_volumes()[0] == 1.0


def test_adjust_volume_through_game():
    game = make_game()
    audio.set_volumes(master=0.5)
    game.adjust_volume("Master", 0.1)
    assert abs(audio.get_volumes()[0] - 0.6) < 1e-9
    game.adjust_volume("Master", -0.3)
    assert abs(audio.get_volumes()[0] - 0.3) < 1e-9


def test_game_uses_slot_path_for_saves(tmp_path, monkeypatch):
    monkeypatch.setattr(sl, "SAVE_DIR", tmp_path)
    seen = {}
    m.load_game = lambda *a: None
    m.save_game = lambda state, path: seen.setdefault("path", path)
    if not pygame.get_init():
        pygame.init()
    game = m.Game(slot=2)
    game.save()
    assert seen["path"].name == "slot_2.json"
