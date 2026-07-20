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
    "mine_entrance": (30, 22, 40),
    "cave_floor": (56, 48, 66),
    "cave_wall": (30, 26, 40),
    "mine_exit": (56, 48, 66),
    "cave_crystal": (140, 200, 240),
    "ore_ferrite": (176, 122, 92),
    "ore_lumite": (120, 220, 170),
    "ore_quartz": (190, 160, 255),
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

    if kind == "mine_entrance":
        grass_base()
        mouth = rect.inflate(-4, -6)
        pygame.draw.ellipse(surf, (52, 44, 62), mouth)
        pygame.draw.ellipse(surf, TILE_COLORS[kind], mouth.inflate(-8, -8))
        pygame.draw.rect(surf, (120, 96, 72), (rect.x + 2, rect.bottom - 6, ts - 4, 4))
        return

    if kind in ("cave_floor", "mine_exit"):
        surf.fill(TILE_COLORS["cave_floor"], rect)
        if (x * 13 + y * 7) % 6 == 0:
            surf.fill((66, 58, 78), (rect.x + (x * 5) % (ts - 4) + 2,
                                     rect.y + (y * 11) % (ts - 4) + 2, 3, 2))
        if kind == "mine_exit":
            pygame.draw.rect(surf, (150, 120, 80), rect.inflate(-8, -4), 2)
            for i in range(1, 4):
                pygame.draw.line(surf, (150, 120, 80),
                                 (rect.x + 6, rect.y + i * ts // 4),
                                 (rect.right - 7, rect.y + i * ts // 4), 2)
        return

    if kind == "cave_wall":
        surf.fill(TILE_COLORS[kind], rect)
        pygame.draw.line(surf, (44, 38, 56), rect.topleft, rect.topright)
        return

    if kind.startswith("ore_"):
        surf.fill(TILE_COLORS["cave_wall"], rect)
        color = TILE_COLORS[kind]
        for i, (ox, oy, r) in enumerate(((8, 9, 4), (22, 14, 3), (13, 23, 5), (24, 25, 3))):
            px_, py_ = rect.x + ox * ts // 32, rect.y + oy * ts // 32
            pygame.draw.circle(surf, color, (px_, py_), r)
            pygame.draw.circle(surf, _lerp(color, (255, 255, 255), 0.35), (px_, py_), r, 1)
        return

    if kind == "cave_crystal":
        surf.fill(TILE_COLORS["cave_floor"], rect)
        pulse = 0.75 + 0.25 * math.sin(t * 2 + x + y)
        col = _lerp((60, 80, 140), TILE_COLORS[kind], pulse)
        pts = [(rect.centerx, rect.y + 2), (rect.right - 3, rect.centery + 4),
               (rect.centerx, rect.bottom - 2), (rect.x + 3, rect.centery + 4)]
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, _lerp(col, (255, 255, 255), 0.4), pts, 1)
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


def _ripe_glint(surf: pygame.Surface, x: int, y: int, ts: int, t: float) -> None:
    """Blinking sparkle so ripe crops read as harvestable at a glance."""
    if math.sin(t * 3.5 + x * 1.3 + y * 0.7) > 0.55:
        gx, gy = x * ts + ts - 7, y * ts + 7
        pygame.draw.line(surf, (255, 255, 230), (gx - 3, gy), (gx + 3, gy))
        pygame.draw.line(surf, (255, 255, 230), (gx, gy - 3), (gx, gy + 3))


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
            _ripe_glint(surf, x, y, ts, t)
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
            _ripe_glint(surf, x, y, ts, t)
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
    if crop.ripe:
        _ripe_glint(surf, x, y, ts, t)


def draw_gear(surf: pygame.Surface, gear: dict, x: int, y: int, ts: int, t: float) -> None:
    cx, cy = x * ts + ts // 2, y * ts + ts // 2
    if gear["kind"] == "drone":
        bob = int(math.sin(t * 2.0 + x * 1.3) * 2)
        shadow = pygame.Rect(0, 0, ts // 2, ts // 6)
        shadow.center = (cx, cy + ts // 4)
        pygame.draw.ellipse(surf, (40, 30, 45), shadow)
        body = pygame.Rect(0, 0, int(ts * 0.55), int(ts * 0.3))
        body.center = (cx, cy - ts // 5 + bob)
        pygame.draw.ellipse(surf, (150, 155, 172), body)
        pygame.draw.ellipse(surf, (96, 100, 118), body, 1)
        light = (110, 190, 255) if math.sin(t * 4 + x) > 0 else (60, 110, 170)
        pygame.draw.circle(surf, light, (cx, body.bottom - 2), 2)
    elif gear["kind"] == "kiln":
        base = pygame.Rect(0, 0, int(ts * 0.78), int(ts * 0.62))
        base.midbottom = (cx, y * ts + ts - 2)
        pygame.draw.rect(surf, (74, 58, 66), base, border_radius=4)
        dome = pygame.Rect(0, 0, base.w - 6, base.h)
        dome.midbottom = (cx, base.top + 8)
        pygame.draw.ellipse(surf, (94, 74, 82), dome)
        mouth = pygame.Rect(0, 0, ts // 3, ts // 5)
        mouth.midbottom = (cx, base.bottom - 4)
        loaded = gear.get("crop_id")
        glow = 0.65 + 0.35 * math.sin(t * 3.1) if loaded else 0.0
        ember = _lerp((30, 22, 30), (255, 150, 60), glow)
        pygame.draw.rect(surf, ember, mouth, border_radius=2)
        if loaded:
            for i in range(2):
                sx = cx - 3 + i * 6
                sy = dome.top - 2 - int((t * 9 + i * 7) % 8)
                pygame.draw.circle(surf, (120, 110, 120), (sx, sy), 1)


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


def draw_critter(surf: pygame.Surface, species: dict, critter: dict,
                 ts: int, t: float) -> None:
    """A wandering fauna critter. Sprite if loaded (flipped to face travel), else a
    small procedural blob in the species colour. A faint bob keeps it feeling alive."""
    cx = int(critter["x"] * ts)
    cy = int(critter["y"] * ts)
    bob = int(math.sin(t * 3.0 + critter["x"] * 2.1 + critter["y"] * 1.3) * 2)
    sprite = SPRITES.get(f"fauna:{critter['species']}")
    if sprite:
        if critter["vx"] > 0:
            sprite = pygame.transform.flip(sprite, True, False)
        surf.blit(sprite, sprite.get_rect(midbottom=(cx, cy + ts // 3 + bob)))
        return
    color = tuple(species["color"])
    by = cy + bob
    r = max(3, ts // 5)
    pygame.draw.ellipse(surf, color, (cx - r, by - r + 2, r * 2, int(r * 1.6)))
    pygame.draw.ellipse(surf, _lerp(color, (0, 0, 0), 0.4),
                        (cx - r, by - r + 2, r * 2, int(r * 1.6)), 1)
    eye_dx = 2 if critter["vx"] >= 0 else -2
    for ex in (cx - 3 + eye_dx, cx + 3 + eye_dx):
        pygame.draw.circle(surf, (245, 245, 250), (ex, by - 2), 2)
        pygame.draw.circle(surf, (24, 20, 36), (ex, by - 2), 1)


FACING_NAMES = {(0, 1): "down", (0, -1): "up", (-1, 0): "left", (1, 0): "right"}
PLAYER_ANIM_FPS = 7


def draw_player(surf: pygame.Surface, player, ts: int, t: float) -> None:
    px, py = int(player.x * ts), int(player.y * ts)
    swing = getattr(player, "swing_t", 0.0)
    if swing > 0:
        lunge = int(5 * math.sin(min(swing / 0.18, 1.0) * math.pi))
        px += player.facing[0] * lunge
        py += player.facing[1] * lunge
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


_EMOTE_FONT: pygame.font.Font | None = None


def _draw_emote(surf: pygame.Surface, cx: int, top: int, emote: str) -> None:
    global _EMOTE_FONT
    if _EMOTE_FONT is None:
        _EMOTE_FONT = pygame.font.SysFont("consolas", 10, bold=True)
    img = _EMOTE_FONT.render(emote, True, (30, 24, 50))
    rect = pygame.Rect(0, 0, img.get_width() + 8, img.get_height() + 4)
    rect.midbottom = (cx + 10, top - 2)
    pygame.draw.rect(surf, (240, 238, 250), rect, border_radius=4)
    pygame.draw.rect(surf, (120, 110, 160), rect, 1, border_radius=4)
    surf.blit(img, img.get_rect(center=rect.center))


def draw_npc(surf: pygame.Surface, npc, ts: int) -> None:
    if getattr(npc, "hidden", False):
        return
    sprite = SPRITES.get(f"npc:{npc.id}")
    px, py = int(npc.x * ts + ts // 2), int(npc.y * ts + ts // 2)
    if sprite:
        rect = sprite.get_rect(midbottom=(px, int(npc.y * ts) + ts))
        surf.blit(sprite, rect)
        top = rect.top
    else:
        color = tuple(npc.d["color"])
        body = pygame.Rect(0, 0, int(ts * 0.65), int(ts * 0.75))
        body.center = (px, py)
        pygame.draw.rect(surf, color, body, border_radius=6)
        pygame.draw.rect(surf, _lerp(color, (0, 0, 0), 0.4), body, 1, border_radius=6)
        pygame.draw.circle(surf, (245, 240, 235), (px, body.y + 4), 3)
        top = body.top
    emote = getattr(npc, "emote", None)
    if emote:
        _draw_emote(surf, px, top, emote)


# ---- screen-space atmosphere (drawn after the camera scale, before UI) --------

DAWN_COLOR = (255, 148, 88)
DUSK_COLOR = (184, 96, 200)
_SCREEN_TINT_CACHE: dict[tuple, pygame.Surface] = {}


def time_tint(hour: float) -> tuple[tuple[int, int, int], int] | None:
    """Warm dawn / violet dusk tint for the current hour, or None at midday/night."""
    if hour < 8.0:
        a = int(64 * (1.0 - (hour - 6.0) / 2.0))
        return (DAWN_COLOR, a) if a > 0 else None
    if 17.0 <= hour < 20.0:
        return DUSK_COLOR, int(56 * (hour - 17.0) / 3.0)
    if 20.0 <= hour < 23.0:
        a = int(56 * (1.0 - (hour - 20.0) / 3.0))
        return (DUSK_COLOR, a) if a > 0 else None
    return None


def draw_time_tint(screen: pygame.Surface, hour: float) -> None:
    tint = time_tint(hour)
    if tint is None:
        return
    color, alpha = tint
    alpha = max(0, min(255, alpha)) // 4 * 4   # bucket for caching
    if alpha == 0:
        return
    key = (screen.get_size(), color, alpha)
    s = _SCREEN_TINT_CACHE.get(key)
    if s is None:
        s = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        s.fill((*color, alpha))
        _SCREEN_TINT_CACHE[key] = s
    screen.blit(s, (0, 0))


def draw_aurora(screen: pygame.Surface, t: float, strength: float) -> None:
    """Drifting green/blue shimmer bands on aurora nights."""
    w, h = screen.get_size()
    band = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(3):
        yc = h * 0.18 + i * h * 0.2 + math.sin(t * 0.35 + i * 2.1) * 46
        color = (80, 230, 150, int(26 * strength)) if i % 2 == 0 \
            else (120, 190, 255, int(18 * strength))
        top = [(x, yc + math.sin(t * 0.7 + x * 0.012 + i * 1.7) * 24 - 30)
               for x in range(0, w + 64, 64)]
        bot = [(x, y + 60) for x, y in reversed(top)]
        pygame.draw.polygon(band, color, top + bot)
    screen.blit(band, (0, 0))


def draw_storm(screen: pygame.Surface, t: float, flash: float) -> None:
    """Ion-storm flicker plus a decaying white lightning flash (0..~0.3)."""
    flicker = 16 + 9 * math.sin(t * 11.0) + 6 * math.sin(t * 23.7)
    if flicker > 0:
        s = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        s.fill((38, 38, 72, int(flicker)))
        screen.blit(s, (0, 0))
    if flash > 0:
        s = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        s.fill((255, 255, 255, int(200 * min(1.0, flash * 4.0))))
        screen.blit(s, (0, 0))


def draw_lighting(surf: pygame.Surface, world, flora, clock, ts: int, t: float,
                  view_rect: pygame.Rect | None = None,
                  darkness_override: int | None = None) -> None:
    """Violet night overlay plus additive bioluminescent glow (never fully dark).
    When view_rect is given, work is confined to that world-space area.
    darkness_override forces a light level (the mine is always dark)."""
    darkness = clock.darkness() if darkness_override is None else darkness_override
    if darkness <= 0:
        return
    area = view_rect if view_rect is not None else surf.get_rect()
    overlay = pygame.Surface(area.size, pygame.SRCALPHA)
    overlay.fill((*NIGHT_COLOR, darkness))
    surf.blit(overlay, area.topleft)

    glow_strength = min(1.0, darkness / clock.max_darkness)
    glows: list[tuple[int, int, tuple[int, int, int], int]] = []
    for x, y in world.find_kind("crystal"):
        glows.append((x, y, (60, 90, 160), ts * 2))
    for x, y in world.find_kind("great_crystal"):
        glows.append((x, y, (90, 120, 200), ts * 3))
    for x, y in world.find_kind("cave_crystal"):
        glows.append((x, y, (70, 110, 170), ts * 3))
    for x, y in world.find_kind("mine_exit"):
        glows.append((x, y, (120, 100, 60), ts * 2))
    for x, y, tile in world.iter_tiles():
        crop = tile.crop
        if crop and crop.ripe and "glow_when_ripe" in crop.d.get("traits", []):
            glows.append((x, y, tuple(c // 3 for c in crop.d["color"]), ts * 2))
    glow = pygame.Surface(area.size, pygame.SRCALPHA)
    drew = False
    for x, y, color, radius in glows:
        cx, cy = x * ts + ts // 2, y * ts + ts // 2
        if not area.inflate(radius * 2, radius * 2).collidepoint(cx, cy):
            continue
        drew = True
        pulse = 0.8 + 0.2 * math.sin(t * 2 + x * 3 + y)
        for r, f in ((radius, 0.35), (radius * 2 // 3, 0.6), (radius // 3, 1.0)):
            col = tuple(int(c * f * pulse * glow_strength) for c in color)
            pygame.draw.circle(glow, col, (cx - area.x, cy - area.y), r)
    if drew:
        surf.blit(glow, area.topleft, special_flags=pygame.BLEND_RGB_ADD)
