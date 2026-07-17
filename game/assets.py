"""Loads sprite sheets from assets/ into render.SPRITES.

Sheets:
- assets/outside.png          32px environment tileset (also crop stages + wild flora)
- assets/astro_spritesheet.png 4x4 grid of 256px astronaut frames
  (rows: down, left, right, up; 4 walk frames per row)
- assets/npc_*.png            one robot colonist each (per npcs.json "sprite")
- assets/building_*.png       outpost buildings (per map.json "buildings")

If the sheets are missing (or use_sprites is false), the game falls back to the
procedural placeholder shapes in render.py.
"""
from __future__ import annotations

import pygame

from game import render
from game.config import ASSET_DIR, load_json

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

# pixel boxes in outside.png (the plant art sits offset half a cell down)
CROP_STAGE_BOXES = [(416, 144, 32, 32), (448, 144, 32, 32), (544, 128, 32, 32)]
CROP_RIPE_BOXES = {"gravity_melon": (544, 176, 32, 36)}
NPC_HEIGHT_TILES = 1.35
BUILDING_WIDTH_TILES = 4


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


def _box(sheet: pygame.Surface, box: tuple[int, int, int, int],
         ts: int) -> pygame.Surface:
    """Extract a pixel box, crop to content, scale by the tile-size ratio."""
    sub = sheet.subsurface(box)
    bbox = sub.get_bounding_rect(min_alpha=10)
    if bbox.width and bbox.height:
        sub = sub.subsurface(bbox)
    if ts != CELL:
        sub = pygame.transform.scale(
            sub, (max(1, sub.get_width() * ts // CELL),
                  max(1, sub.get_height() * ts // CELL)))
    return sub


def _cropped_to_height(img: pygame.Surface, target_h: int) -> pygame.Surface:
    bbox = img.get_bounding_rect(min_alpha=10)
    if bbox.width and bbox.height:
        img = img.subsurface(bbox)
    w = max(1, round(img.get_width() * target_h / img.get_height()))
    return pygame.transform.smoothscale(img, (w, target_h))


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

    # crop growth stages + special ripe sprites, wild flora (pixel boxes)
    for i, box in enumerate(CROP_STAGE_BOXES):
        sprites[f"crop_stage:{i}"] = _box(sheet, box, ts)
    for crop_id, box in CROP_RIPE_BOXES.items():
        sprites[f"crop_ripe:{crop_id}"] = _box(sheet, box, ts)
    for species in load_json("wild_flora.json")["species"].values():
        if "box" in species:
            sprites[f"flora:{species['name']}"] = _box(sheet, tuple(species["box"]), ts)

    # NPC robots (per npcs.json) and outpost buildings (per map.json)
    for npc_id, npc in load_json("npcs.json").items():
        path = ASSET_DIR / npc.get("sprite", "")
        if npc.get("sprite") and path.exists():
            img = pygame.image.load(str(path)).convert_alpha()
            sprites[f"npc:{npc_id}"] = _cropped_to_height(img, int(ts * NPC_HEIGHT_TILES))
    for b in load_json("map.json").get("buildings", []):
        path = ASSET_DIR / f"building_{b['image']}_384.png"
        if path.exists():
            img = pygame.image.load(str(path)).convert_alpha()
            w = BUILDING_WIDTH_TILES * ts
            h = max(1, round(img.get_height() * w / img.get_width()))
            sprites[f"building:{b['image']}"] = pygame.transform.smoothscale(img, (w, h))

    astro = pygame.image.load(str(astro_path)).convert_alpha()
    target_h = int(ts * PLAYER_HEIGHT_TILES)
    for row, name in enumerate(PLAYER_ROWS):
        for f in range(PLAYER_WALK_FRAMES):
            frame = astro.subsurface(
                (f * PLAYER_FRAME, row * PLAYER_FRAME, PLAYER_FRAME, PLAYER_FRAME))
            sprites[f"player:{name}:{f}"] = _cropped_to_height(frame, target_h)
    return True
