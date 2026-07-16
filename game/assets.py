"""Loads sprite sheets from assets/ into render.SPRITES.

Sheets:
- assets/outside.png          32px environment tileset
- assets/astro_spritesheet.png 4x4 grid of 256px astronaut frames
  (rows: down, left, right, up; 4 walk frames per row)

If the sheets are missing (or use_sprites is false), the game falls back to the
procedural placeholder shapes in render.py.
"""
from __future__ import annotations

import pygame

from game import render
from game.config import BASE_DIR

ASSET_DIR = BASE_DIR / "assets"
CELL = 32               # outside.png grid size
PLAYER_FRAME = 256      # astro sheet frame size
PLAYER_ROWS = ["down", "left", "right", "up"]
PLAYER_WALK_FRAMES = 4
PLAYER_HEIGHT_TILES = 1.5

# (col, row) cells in outside.png
TILE_CELLS = {
    "tile:grass": (1, 9),
    "tile:soil": (10, 6),
    "tile:path": (3, 2),
    "tile:landing_pad": (0, 0),
}
GRASS_FLOWER_CELLS = [(3, 11), (4, 11), (5, 11)]
BOULDER_CELL = (10, 9)          # composited onto grass for rock tiles
HABITAT_RECT = (9, 0, 3, 5)     # greenhouse dome: col, row, w, h in cells


def _cell(sheet: pygame.Surface, cx: int, cy: int, ts: int,
          w: int = 1, h: int = 1) -> pygame.Surface:
    img = sheet.subsurface((cx * CELL, cy * CELL, w * CELL, h * CELL))
    if ts != CELL:
        img = pygame.transform.scale(img, (w * ts, h * ts))
    return img


def _over(base: pygame.Surface, top: pygame.Surface) -> pygame.Surface:
    out = base.copy()
    out.blit(top, (0, 0))
    return out


def load_assets(ts: int) -> bool:
    """Populate render.SPRITES. Returns True if the sheets were found and loaded."""
    outside_path = ASSET_DIR / "outside.png"
    astro_path = ASSET_DIR / "astro_spritesheet.png"
    if not (outside_path.exists() and astro_path.exists()):
        return False

    sheet = pygame.image.load(str(outside_path)).convert_alpha()
    sprites = render.SPRITES
    for key, (cx, cy) in TILE_CELLS.items():
        sprites[key] = _cell(sheet, cx, cy, ts)
    grass = sprites["tile:grass"]
    for i, (cx, cy) in enumerate(GRASS_FLOWER_CELLS):
        sprites[f"tile:grass_flowers{i}"] = _cell(sheet, cx, cy, ts)
    sprites["tile:rock"] = _over(grass, _cell(sheet, *BOULDER_CELL, ts))
    hx, hy, hw, hh = HABITAT_RECT
    dome = sheet.subsurface((hx * CELL, hy * CELL, hw * CELL, hh * CELL))
    sprites["habitat"] = pygame.transform.scale(dome, (hw * ts, hh * ts))

    astro = pygame.image.load(str(astro_path)).convert_alpha()
    target_h = int(ts * PLAYER_HEIGHT_TILES)
    for row, name in enumerate(PLAYER_ROWS):
        for f in range(PLAYER_WALK_FRAMES):
            frame = astro.subsurface(
                (f * PLAYER_FRAME, row * PLAYER_FRAME, PLAYER_FRAME, PLAYER_FRAME))
            bbox = frame.get_bounding_rect(min_alpha=10)
            img = frame.subsurface(bbox)
            w = max(1, round(bbox.width * target_h / bbox.height))
            sprites[f"player:{name}:{f}"] = pygame.transform.smoothscale(img, (w, target_h))
    return True
