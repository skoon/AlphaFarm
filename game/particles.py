"""Tiny pooled particle system + floating text.

Particles live in world space and are drawn on the world surface (pre-scale).
Floating texts also live in world space but are drawn post-scale via the camera
transform so the text stays crisp at any zoom.
"""
from __future__ import annotations

import math
import random

import pygame

MAX_PARTICLES = 400

# kind -> (count, speed range, upward bias, gravity, life range, colors, size)
PRESETS: dict[str, dict] = {
    "soil": {"n": 8, "spd": (25, 70), "up": -40, "grav": 260, "life": (0.3, 0.55),
             "colors": [(126, 92, 78), (96, 66, 58), (142, 108, 90)], "size": 2},
    "water": {"n": 10, "spd": (30, 85), "up": -60, "grav": 320, "life": (0.3, 0.5),
              "colors": [(110, 170, 255), (70, 130, 230), (160, 210, 255)], "size": 2},
    "sparkle": {"n": 10, "spd": (15, 50), "up": -30, "grav": -25, "life": (0.5, 0.85),
                "colors": [(255, 240, 180), (180, 255, 220), (255, 255, 255)], "size": 2},
    "spore": {"n": 3, "spd": (8, 28), "up": -6, "grav": 0, "life": (1.8, 3.4),
              "colors": [(240, 180, 240), (200, 150, 220), (255, 210, 250)], "size": 2},
}


class Particles:
    def __init__(self) -> None:
        self.parts: list[dict] = []
        self.texts: list[dict] = []

    def burst(self, kind: str, wx: float, wy: float, rng: random.Random,
              n: int | None = None) -> None:
        p = PRESETS[kind]
        for _ in range(n if n is not None else p["n"]):
            ang = rng.uniform(0, math.tau)
            spd = rng.uniform(*p["spd"])
            self.parts.append({
                "x": wx + rng.uniform(-4, 4), "y": wy + rng.uniform(-3, 3),
                "vx": math.cos(ang) * spd * 0.7,
                "vy": math.sin(ang) * spd * 0.35 + p["up"],
                "grav": p["grav"], "age": 0.0, "life": rng.uniform(*p["life"]),
                "color": rng.choice(p["colors"]), "size": p["size"],
                "twinkle": kind in ("sparkle", "spore"),
            })
        if len(self.parts) > MAX_PARTICLES:
            self.parts = self.parts[-MAX_PARTICLES:]

    def float_text(self, text: str, wx: float, wy: float,
                   color: tuple[int, int, int] = (255, 235, 160),
                   life: float = 1.2) -> None:
        self.texts.append({"text": text, "x": wx, "y": wy, "age": 0.0,
                           "life": life, "color": color})

    def update(self, dt: float) -> None:
        for p in self.parts:
            p["age"] += dt
            p["vy"] += p["grav"] * dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
        self.parts = [p for p in self.parts if p["age"] < p["life"]]
        for ft in self.texts:
            ft["age"] += dt
            ft["y"] -= 22 * dt
        self.texts = [ft for ft in self.texts if ft["age"] < ft["life"]]

    def draw(self, surf: pygame.Surface, t: float) -> None:
        for p in self.parts:
            fade = 1.0 - p["age"] / p["life"]
            if p["twinkle"] and math.sin(t * 9 + p["x"]) < -0.35:
                continue
            c = tuple(int(ch * (0.35 + 0.65 * fade)) for ch in p["color"])
            r = max(1, int(p["size"] * (0.5 + fade)))
            pygame.draw.circle(surf, c, (int(p["x"]), int(p["y"])), r)

    def draw_texts(self, screen: pygame.Surface, camera, font) -> None:
        for ft in self.texts:
            sx, sy = camera.world_to_screen(ft["x"], ft["y"])
            img = font.render(ft["text"], True, ft["color"])
            fade = 1.0 - ft["age"] / ft["life"]
            img.set_alpha(int(255 * min(1.0, fade * 2)))
            screen.blit(img, img.get_rect(midbottom=(sx, sy)))
