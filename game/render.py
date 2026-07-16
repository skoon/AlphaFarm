"""All drawing. Placeholder procedural shapes for every entity, routed through
draw_* functions so sprite sheets can replace them later: register a Surface in
SPRITES under the entity key and the procedural fallback is skipped."""
from __future__ import annotations

import math

import pygame

# Drop-in sprite hook: SPRITES["tile:grass"] = pygame.Surface -> used instead of shapes.
SPRITES: dict[str, pygame.Surface] = {}

TILE_COLORS = {
    "grass": (52, 88, 74),
    "soil": (99, 76, 94),
    "rock": (72, 66, 88),
    "crystal": (150, 190, 250),
    "great_crystal": (185, 215, 255),
    "habitat_wall": (138, 140, 158),
    "habitat_door": (208, 172, 118),
    "terminal": (80, 190, 210),
    "landing_pad": (104, 104, 120),
    "shipping_pod": (222, 158, 84),
    "building": (118, 102, 130),
    "path": (108, 94, 116),
}
TILLED_COLOR = (68, 50, 66)
WATERED_TINT = (46, 40, 78)
NIGHT_COLOR = (34, 16, 70)
GRASS_SPECKLE = (78, 128, 104)


def _lerp(a: tuple, b: tuple, f: float) -> tuple[int, int, int]:
    f = max(0.0, min(1.0, f))
    return tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3))


def soil_color(tile) -> tuple[int, int, int]:
    """Living-soil cue: resonance shifts tilled soil from ashen gray to rich violet."""
    base = TILLED_COLOR if tile.tilled else TILE_COLORS["soil"]
    gray = (82, 78, 82)
    rich = (108, 58, 122)
    tinted = _lerp(gray, rich, (tile.resonance - 0.1) / 0.9)
    return _lerp(base, tinted, 0.55)


_OVERLAY_CACHE: dict[tuple, pygame.Surface] = {}


def _overlay(ts: int, color: tuple[int, int, int], alpha: int) -> pygame.Surface:
    key = (ts, color, alpha)
    s = _OVERLAY_CACHE.get(key)
    if s is None:
        s = pygame.Surface((ts, ts), pygame.SRCALPHA)
        s.fill((*color, alpha))
        _OVERLAY_CACHE[key] = s
    return s


def _resonance_overlay(ts: int, resonance: float) -> pygame.Surface:
    """Living-soil cue on sprite tiles: ashen gray (low) to rich violet (high)."""
    bucket = max(1, min(10, int(resonance * 10)))
    color = _lerp((70, 66, 70), (116, 56, 132), (bucket / 10 - 0.1) / 0.9)
    return _overlay(ts, color, 72)


def draw_tile(surf: pygame.Surface, tile, x: int, y: int, ts: int, t: float) -> None:
    rect = pygame.Rect(x * ts, y * ts, ts, ts)
    kind = tile.kind
    grass_img = SPRITES.get("tile:grass")

    def grass_base() -> None:
        if grass_img:
            surf.blit(grass_img, rect.topleft)
        else:
            surf.fill(TILE_COLORS["grass"], rect)

    if kind == "grass":
        if grass_img:
            if (x * 11 + y * 29 + (x * y) % 5) % 13 == 0:
                surf.blit(SPRITES[f"tile:grass_flowers{(x + y) % 3}"], rect.topleft)
            else:
                surf.blit(grass_img, rect.topleft)
        else:
            surf.fill(TILE_COLORS["grass"], rect)
            if (x * 7 + y * 13) % 5 == 0:
                surf.fill(GRASS_SPECKLE, (rect.x + (x * 11) % (ts - 4) + 2,
                                          rect.y + (y * 17) % (ts - 4) + 2, 2, 2))
        return

    if kind == "soil":
        img = SPRITES.get("tile:soil")
        if img:
            surf.blit(img, rect.topleft)
            surf.blit(_resonance_overlay(ts, tile.resonance), rect.topleft)
            furrow = (54, 36, 34)
        else:
            color = soil_color(tile)
            if tile.watered:
                color = _lerp(color, WATERED_TINT, 0.5)
            surf.fill(color, rect)
            furrow = _lerp(color, (0, 0, 0), 0.25)
        if tile.tilled:
            for i in range(1, 4):
                pygame.draw.line(surf, furrow, (rect.x + 2, rect.y + i * ts // 4),
                                 (rect.right - 3, rect.y + i * ts // 4))
        if img and tile.watered:
            surf.blit(_overlay(ts, (26, 36, 84), 88), rect.topleft)
        return

    if kind in ("rock", "path", "landing_pad"):
        img = SPRITES.get(f"tile:{kind}")
        if img:
            surf.blit(img, rect.topleft)
            return
        surf.fill(TILE_COLORS[kind], rect)
        if kind == "rock":
            pygame.draw.circle(surf, (92, 86, 108), rect.center, ts // 3)
        elif kind == "landing_pad":
            pygame.draw.rect(surf, (128, 128, 148), rect, 1)
        return

    if kind in ("habitat_wall", "habitat_door"):
        if "habitat" in SPRITES:
            grass_base()   # the dome image is blitted on top by draw_habitat
            return
        surf.fill(TILE_COLORS[kind], rect)
        if kind == "habitat_door":
            pygame.draw.rect(surf, (150, 120, 80), rect.inflate(-6, -2))
        return

    if kind == "terminal":
        if grass_img:
            grass_base()
        else:
            surf.fill(TILE_COLORS["habitat_wall"], rect)
        pygame.draw.rect(surf, (58, 60, 76), rect.inflate(-ts // 4, -ts // 5))
        pygame.draw.rect(surf, TILE_COLORS["terminal"], rect.inflate(-ts // 3, -ts // 3))
        return

    if kind == "shipping_pod":
        img = SPRITES.get("tile:landing_pad")
        if img:
            surf.blit(img, rect.topleft)
        else:
            surf.fill(TILE_COLORS["landing_pad"], rect)
        pygame.draw.ellipse(surf, TILE_COLORS["shipping_pod"], rect.inflate(-4, -6))
        pygame.draw.ellipse(surf, (255, 220, 160), rect.inflate(-4, -6), 1)
        return

    if kind in ("crystal", "great_crystal"):
        grass_base()
        pulse = 0.75 + 0.25 * math.sin(t * 2 + x + y)
        col = _lerp((60, 80, 140), TILE_COLORS[kind], pulse)
        pts = [(rect.centerx, rect.y + 2), (rect.right - 3, rect.centery + 4),
               (rect.centerx, rect.bottom - 2), (rect.x + 3, rect.centery + 4)]
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, _lerp(col, (255, 255, 255), 0.4), pts, 1)
        return

    if kind == "building":
        img = SPRITES.get("tile:path")
        if img:
            surf.blit(img, rect.topleft)  # building sprite is blitted by draw_buildings
            return
        surf.fill(TILE_COLORS[kind], rect)
        pygame.draw.rect(surf, _lerp(TILE_COLORS["building"], (0, 0, 0), 0.25), rect, 2)
        return

    surf.fill(TILE_COLORS[kind], rect)


def draw_habitat(surf: pygame.Surface, origin: tuple[int, int] | None, ts: int) -> None:
    """Blit the habitat dome sprite over its tile footprint (sprite mode only)."""
    img = SPRITES.get("habitat")
    if img and origin:
        surf.blit(img, (origin[0] * ts, origin[1] * ts))


def draw_buildings(surf: pygame.Surface, buildings: list[dict], ts: int) -> None:
    """Blit building sprites anchored to the bottom of their tile footprints."""
    for b in buildings:
        img = SPRITES.get(f"building:{b['image']}")
        if img:
            surf.blit(img, (b["x"] * ts, (b["y"] + b["h"]) * ts - img.get_height()))


def draw_crop(surf: pygame.Surface, crop, x: int, y: int, ts: int, t: float) -> None:
    cx, cy = x * ts + ts // 2, y * ts + ts // 2
    color = tuple(crop.d["color"])
    frac = crop.stage_frac()
    traits = crop.d.get("traits", [])
    family = crop.d["family"]

    if crop.wilted:
        gray = (110, 95, 80)
        pygame.draw.line(surf, gray, (cx - 5, cy + 6), (cx + 2, cy - 4), 2)
        pygame.draw.line(surf, gray, (cx + 2, cy - 4), (cx + 6, cy + 2), 2)
        return

    if "underground" in traits:
        # visible only as a soil bulge; a red seam shows when ripe
        bulge = pygame.Rect(0, 0, int(ts * (0.4 + 0.4 * frac)), int(ts * (0.25 + 0.2 * frac)))
        bulge.center = (cx, cy + ts // 5)
        pygame.draw.ellipse(surf, (118, 92, 110), bulge)
        if crop.ripe:
            pygame.draw.line(surf, color, (bulge.centerx - 4, bulge.centery),
                             (bulge.centerx + 4, bulge.centery), 2)
        return

    if not crop.ripe:
        img = SPRITES.get(f"crop_stage:{min(int(frac * 3), 2)}")
        if img:
            surf.blit(img, img.get_rect(midbottom=(cx, y * ts + ts - 2)))
            return
    else:
        img = SPRITES.get(f"crop_ripe:{crop.crop_id}")
        if img:
            bottom = y * ts + ts - 2
            if "floats" in traits:
                shadow = pygame.Rect(0, 0, ts // 2, ts // 5)
                shadow.center = (cx, y * ts + ts - ts // 6)
                pygame.draw.ellipse(surf, (40, 30, 45), shadow)
                bottom += int(-ts // 4 + math.sin(t * 2.2 + x * 1.7) * 2)
            surf.blit(img, img.get_rect(midbottom=(cx, bottom)))
            return

    if frac < 0.34:  # sprout
        stem = _lerp(color, (30, 60, 40), 0.5)
        pygame.draw.line(surf, stem, (cx, cy + 6), (cx, cy), 2)
        pygame.draw.circle(surf, stem, (cx, cy - 1), 2)
        return

    size = 0.55 + 0.45 * frac
    shade = color if crop.ripe else _lerp(color, (60, 70, 60), 0.35)
    bob = math.sin(t * 2.2 + x * 1.7) * 2 if "floats" in traits else 0
    lift = -ts // 4 - 2 if "floats" in traits and crop.ripe else 0
    if "floats" in traits and crop.ripe:
        shadow = pygame.Rect(0, 0, ts // 2, ts // 5)
        shadow.center = (cx, cy + ts // 3)
        pygame.draw.ellipse(surf, (40, 30, 45), shadow)
    py = cy + lift + bob

    if family == "grain":
        sway = math.sin(t * 2.5 + x) * 3
        for off in (-5, 0, 5):
            pygame.draw.line(surf, shade, (cx + off, cy + 8),
                             (cx + off + sway, cy + 8 - int(12 * size)), 2)
    elif family == "berry":
        for ox, oy in ((-4, 2), (4, 2), (0, -4)):
            pygame.draw.circle(surf, shade, (cx + ox, py + oy), int(4 * size))
    elif family == "melon":
        pygame.draw.circle(surf, shade, (cx, py), int(7 * size))
        pygame.draw.circle(surf, _lerp(shade, (255, 255, 255), 0.3), (cx, py), int(7 * size), 1)
    elif family == "pod":
        r = int(8 * size)
        pts = [(cx, py - r), (cx + r // 2, py), (cx, py + r), (cx - r // 2, py)]
        pygame.draw.polygon(surf, shade, pts)
        pygame.draw.polygon(surf, _lerp(shade, (255, 255, 255), 0.5), pts, 1)
    elif family == "fungus":
        pygame.draw.rect(surf, (200, 190, 180), (cx - 2, py, 4, 8))
        pygame.draw.ellipse(surf, shade, (cx - int(7 * size), py - 6, int(14 * size), 8))
    else:  # flower
        for i in range(5):
            a = t * 0.5 + i * math.tau / 5
            pygame.draw.circle(surf, shade, (int(cx + math.cos(a) * 5 * size),
                                             int(py + math.sin(a) * 5 * size)), 3)
        pygame.draw.circle(surf, (255, 250, 220), (cx, int(py)), 2)


def draw_wild_plant(surf: pygame.Surface, species: dict, x: int, y: int, ts: int, t: float) -> None:
    sprite = SPRITES.get(f"flora:{species['name']}")
    if sprite:
        surf.blit(sprite, sprite.get_rect(midbottom=(x * ts + ts // 2, y * ts + ts - 1)))
        return
    cx, cy = x * ts + ts // 2, y * ts + ts // 2
    color = tuple(species["color"])
    sway = math.sin(t * 1.8 + x * 2.3) * 2
    pygame.draw.line(surf, _lerp(color, (0, 0, 0), 0.4), (cx, cy + 8), (cx + sway, cy - 2), 2)
    pygame.draw.circle(surf, color, (int(cx + sway), cy - 4), 4)
    pygame.draw.circle(surf, _lerp(color, (255, 255, 255), 0.4), (int(cx + sway), cy - 4), 4, 1)


FACING_NAMES = {(0, 1): "down", (0, -1): "up", (-1, 0): "left", (1, 0): "right"}
PLAYER_ANIM_FPS = 7


def draw_player(surf: pygame.Surface, player, ts: int, t: float) -> None:
    px, py = int(player.x * ts), int(player.y * ts)
    facing = FACING_NAMES.get(player.facing, "down")
    frame = int(t * PLAYER_ANIM_FPS) % 4 if getattr(player, "moving", False) else 0
    sprite = SPRITES.get(f"player:{facing}:{frame}")
    if sprite:
        rect = sprite.get_rect(midbottom=(px, py + int(ts * 0.48)))
        surf.blit(sprite, rect)
        return
    body = pygame.Rect(0, 0, int(ts * 0.7), int(ts * 0.8))
    body.center = (px, py)
    pygame.draw.rect(surf, (232, 224, 240), body, border_radius=5)
    pygame.draw.rect(surf, (150, 140, 180), body, 1, border_radius=5)
    fx, fy = player.facing
    visor = pygame.Rect(0, 0, 8, 5)
    visor.center = (px + fx * 5, py - 3 + max(fy, 0) * 4)
    pygame.draw.rect(surf, (90, 200, 220), visor, border_radius=2)


def draw_npc(surf: pygame.Surface, npc, ts: int) -> None:
    sprite = SPRITES.get(f"npc:{npc.id}")
    px, py = int(npc.x * ts + ts // 2), int(npc.y * ts + ts // 2)
    if sprite:
        surf.blit(sprite, sprite.get_rect(midbottom=(px, int(npc.y * ts) + ts)))
        return
    color = tuple(npc.d["color"])
    body = pygame.Rect(0, 0, int(ts * 0.65), int(ts * 0.75))
    body.center = (px, py)
    pygame.draw.rect(surf, color, body, border_radius=6)
    pygame.draw.rect(surf, _lerp(color, (0, 0, 0), 0.4), body, 1, border_radius=6)
    pygame.draw.circle(surf, (245, 240, 235), (px, body.y + 4), 3)


def draw_lighting(surf: pygame.Surface, world, flora, clock, ts: int, t: float) -> None:
    """Violet night overlay plus additive bioluminescent glow (never fully dark)."""
    darkness = clock.darkness()
    if darkness <= 0:
        return
    overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    overlay.fill((*NIGHT_COLOR, darkness))
    surf.blit(overlay, (0, 0))

    glow_strength = darkness / clock.max_darkness
    glows: list[tuple[int, int, tuple[int, int, int], int]] = []
    for x, y in world.find_kind("crystal"):
        glows.append((x, y, (60, 90, 160), ts * 2))
    for x, y in world.find_kind("great_crystal"):
        glows.append((x, y, (90, 120, 200), ts * 3))
    for x, y, tile in world.iter_tiles():
        crop = tile.crop
        if crop and crop.ripe and "glow_when_ripe" in crop.d.get("traits", []):
            glows.append((x, y, tuple(c // 3 for c in crop.d["color"]), ts * 2))
    glow = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    for x, y, color, radius in glows:
        cx, cy = x * ts + ts // 2, y * ts + ts // 2
        pulse = 0.8 + 0.2 * math.sin(t * 2 + x * 3 + y)
        for r, f in ((radius, 0.35), (radius * 2 // 3, 0.6), (radius // 3, 1.0)):
            col = tuple(int(c * f * pulse * glow_strength) for c in color)
            pygame.draw.circle(glow, col, (cx, cy), r)
    surf.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
