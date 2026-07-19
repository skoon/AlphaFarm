"""Headless smoke run: boots the full game with the SDL dummy driver, drives
input through the real key handler, simulates a day rollover, and renders
frames. Run with: uv run python tests/smoke.py"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame  # noqa: E402

import main as m  # noqa: E402

# Keep the smoke run off the real save file.
m.load_game = lambda: None
m.save_game = lambda state: None

pygame.init()
game = m.Game()
assert game.clock.day == 1
game.run(max_frames=120)  # render + update 120 frames of a fresh day


def key(k, mod=0):
    game.handle_key(pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod))


# Exercise tools, panels, and interaction paths through the real handler.
for k in (pygame.K_1, pygame.K_SPACE, pygame.K_2, pygame.K_SPACE,
          pygame.K_5, pygame.K_TAB, pygame.K_SPACE,
          pygame.K_3, pygame.K_SPACE, pygame.K_4, pygame.K_SPACE,
          pygame.K_e):
    key(k)
if game.mode == "dialogue":
    key(pygame.K_e)
key(pygame.K_i); key(pygame.K_i)
key(pygame.K_c); key(pygame.K_c)
key(pygame.K_j); key(pygame.K_j)
key(pygame.K_SLASH)
assert game.mode == "help", f"expected help mode, got {game.mode}"
game.run(max_frames=10)   # render the help panel
key(pygame.K_SLASH)
assert game.mode == "play"
key(pygame.K_F1)                      # debug overlay on
game.run(max_frames=60)
key(pygame.K_n)                       # debug: next day (exercises end_day + save path)
assert game.mode == "day_summary", f"expected day_summary, got {game.mode}"
assert game.clock.day == 2, f"expected day 2, got {game.clock.day}"
game.run(max_frames=40)               # render the summary card past its fade-in
key(pygame.K_e)                       # dismiss it
assert game.mode == "play", f"summary did not dismiss, mode {game.mode}"
game.run(max_frames=60)

# Force the night/lighting path and a collapse rollover.
game.clock.hour = 23.5
game.run(max_frames=30)
key(pygame.K_t); key(pygame.K_t); key(pygame.K_t)  # debug +3h -> past 02:00
assert game.clock.day == 3, f"expected day 3 after collapse, got {game.clock.day}"
assert game.mode == "day_summary"
game.run(max_frames=40)
key(pygame.K_e)
assert game.mode == "play"
game.run(max_frames=30)

state = game.gather_state()
assert set(state) == {"clock", "player", "inventory", "shipping_bin", "world",
                      "events", "flora", "npcs", "quests", "favors"}

pygame.quit()
print(f"SMOKE OK — reached day {game.clock.day}, "
      f"energy {game.player.energy:.0f}, mode {game.mode}")
