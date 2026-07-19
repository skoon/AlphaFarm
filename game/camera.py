"""Smooth-follow camera.

World-space drawing happens on a full-map surface at native tile size; the camera
chooses the visible sub-rect, which the frame loop scales up by `zoom` to the window.
world_to_screen() maps world pixels to window pixels for crisp screen-space overlays
(floating text, debug callouts) that track world objects.
"""
from __future__ import annotations

from typing import Any

import pygame


class Camera:
    def __init__(self, cfg: dict[str, Any], map_px_w: int, map_px_h: int,
                 window_w: int, window_h: int):
        self.zoom: int = cfg["window"].get("zoom", 2)
        self.follow_speed: float = cfg.get("camera", {}).get("follow_speed", 6.0)
        self.map_w = map_px_w
        self.map_h = map_px_h
        self.view_w = window_w // self.zoom
        self.view_h = window_h // self.zoom
        self.x = 0.0   # top-left of the view in world pixels
        self.y = 0.0

    def _clamp(self) -> None:
        self.x = max(0.0, min(self.x, self.map_w - self.view_w))
        self.y = max(0.0, min(self.y, self.map_h - self.view_h))

    def center_on(self, wx: float, wy: float) -> None:
        """Snap the view to center on a world-pixel position (no easing)."""
        self.x = wx - self.view_w / 2
        self.y = wy - self.view_h / 2
        self._clamp()

    def update(self, dt: float, wx: float, wy: float) -> None:
        """Ease the view toward centering on (wx, wy)."""
        f = min(1.0, self.follow_speed * dt)
        self.x += (wx - self.view_w / 2 - self.x) * f
        self.y += (wy - self.view_h / 2 - self.y) * f
        self._clamp()

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.view_w, self.view_h)

    def visible_tiles(self, ts: int) -> tuple[int, int, int, int]:
        """(x0, y0, x1, y1) tile bounds covering the view, +1 margin, unclamped high end."""
        r = self.rect
        return (max(0, r.left // ts - 1), max(0, r.top // ts - 1),
                r.right // ts + 2, r.bottom // ts + 2)

    def world_to_screen(self, wx: float, wy: float) -> tuple[int, int]:
        return (int((wx - self.x) * self.zoom), int((wy - self.y) * self.zoom))
