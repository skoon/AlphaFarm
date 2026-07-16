"""Save/load the full game state to saves/savegame.json."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from game.config import SAVE_DIR, SAVE_PATH

SAVE_VERSION = 1


def save_game(state: dict[str, Any], path: Path = SAVE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": SAVE_VERSION, **state}
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    tmp.replace(path)


def load_game(path: Path = SAVE_PATH) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("version") != SAVE_VERSION:
        raise ValueError(f"unsupported save version: {data.get('version')}")
    return data


def save_exists(path: Path = SAVE_PATH) -> bool:
    return path.exists()
