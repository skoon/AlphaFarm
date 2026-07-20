"""Save/load the full game state to saves/savegame.json."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from game.config import SAVE_DIR, SAVE_PATH

SAVE_VERSION = 2  # v2 adds player.upgrades, tile gear, favors; all guarded on load


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
    if data.get("version", 0) > SAVE_VERSION:
        raise ValueError(f"save is from a newer game version: {data.get('version')}")
    return data


def save_exists(path: Path = SAVE_PATH) -> bool:
    return path.exists()


# ---- save slots -----------------------------------------------------------

SLOT_COUNT = 3


def slot_path(n: int) -> Path:
    return SAVE_DIR / f"slot_{n}.json"


def slot_summary(n: int) -> dict[str, Any] | None:
    """Peek a slot for the title screen. None if empty or unreadable."""
    p = slot_path(n)
    if not p.exists():
        return None
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return {"day": data["clock"]["day"], "credits": data["player"]["credits"]}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def migrate_legacy() -> None:
    """Move the old single savegame.json into slot 1, once."""
    if SAVE_PATH.exists() and not slot_path(1).exists():
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        SAVE_PATH.replace(slot_path(1))
