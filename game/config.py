"""Loading of config and content JSON. All tunables live in data/*.json.

Path resolution works both from source and from a PyInstaller-frozen build:
- Read-only content (data/, assets/) is bundled into the executable and, at runtime,
  extracted next to the code, so it is found relative to the bundle root.
- Writable state (saves/) must live somewhere persistent, so it is placed next to the
  executable rather than inside the temporary extraction directory.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

if getattr(sys, "frozen", False):
    # Running inside a PyInstaller bundle.
    BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    RUNTIME_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    RUNTIME_DIR = BASE_DIR

DATA_DIR = BASE_DIR / "data"
ASSET_DIR = BASE_DIR / "assets"
SAVE_DIR = RUNTIME_DIR / "saves"
SAVE_PATH = SAVE_DIR / "savegame.json"


def load_json(name: str) -> dict[str, Any]:
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def load_config() -> dict[str, Any]:
    return load_json("config.json")
