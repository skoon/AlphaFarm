import pytest

from game.save_load import load_game, save_game, save_exists


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "save.json"
    state = {"clock": {"day": 3, "hour": 12.5}, "player": {"credits": 500}}
    assert not save_exists(path)
    save_game(state, path)
    assert save_exists(path)
    loaded = load_game(path)
    assert loaded["clock"] == {"day": 3, "hour": 12.5}
    assert loaded["player"]["credits"] == 500
    assert loaded["version"] == 1


def test_load_missing_returns_none(tmp_path):
    assert load_game(tmp_path / "nope.json") is None


def test_load_rejects_unknown_version(tmp_path):
    path = tmp_path / "save.json"
    path.write_text('{"version": 999}')
    with pytest.raises(ValueError):
        load_game(path)


def test_no_leftover_tmp_file(tmp_path):
    path = tmp_path / "save.json"
    save_game({"a": 1}, path)
    assert not (tmp_path / "save.tmp").exists()
