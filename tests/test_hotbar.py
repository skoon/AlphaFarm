"""Headless tests for the visual hotbar and mouse support (Phase A6)."""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame  # noqa: E402

import main as m  # noqa: E402

# Keep tests off the real save file.
m.load_game = lambda: None
m.save_game = lambda state: None

pygame.init()


def make_game() -> m.Game:
    game = m.Game()
    pygame.display.set_mode((game.screen_w, game.screen_h))
    return game


def mouse_down(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)


def test_hotbar_draws_five_distinct_slots():
    game = make_game()
    screen = pygame.display.get_surface()
    game.mode = "play"
    game.draw(screen, 60.0)
    assert len(game.ui.hotbar_rects) == 5
    tool_ids = [tool for _, tool in game.ui.hotbar_rects]
    assert len(set(tool_ids)) == 5


def test_click_hotbar_selects_tool():
    game = make_game()
    screen = pygame.display.get_surface()
    game.mode = "play"
    game.draw(screen, 60.0)
    scanner_rect = next(rect for rect, tool in game.ui.hotbar_rects if tool == "scanner")
    game.handle_mouse(mouse_down(scanner_rect.center))
    assert game.player.tool == "scanner"


def test_shop_row_click_selects_then_ships():
    game = make_game()
    screen = pygame.display.get_surface()
    game.inventory.add("crop:lumen_berry", 2)
    game.mode = "shop"
    game.shop_mode = "sell"
    game.shop_index = -1  # force the first click to be a "select", not a re-click
    game.draw(screen, 60.0)
    assert game.ui.shop_row_rects, "expected at least one shop row rect"
    row_rect = game.ui.shop_row_rects[0]

    game.handle_mouse(mouse_down(row_rect.center))
    assert game.shop_index == 0

    game.draw(screen, 60.0)  # refresh rects (harmless if unchanged)
    row_rect = game.ui.shop_row_rects[0]
    game.handle_mouse(mouse_down(row_rect.center))
    assert game.shipping_bin.contents, "expected an item shipped into the bin"
