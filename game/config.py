"""Loading of config and content JSON. All tunables live in data/*.json."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SAVE_DIR = BASE_DIR / "saves"
SAVE_PATH = SAVE_DIR / "savegame.json"


def load_json(name: str) -> dict[str, Any]:
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def load_config() -> dict[str, Any]:
    return load_json("config.json")
