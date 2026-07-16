"""HUD, panels (inventory / codex / journal / shop / terminal), dialogue, toasts, debug."""
from __future__ import annotations

import math

import pygame

PANEL_BG = (24, 18, 40, 235)
PANEL_BORDER = (140, 120, 200)
TEXT = (235, 230, 245)
DIM = (160, 150, 180)
ACCENT = (255, 210, 120)
GOOD = (140, 230, 170)
BAD = (240, 130, 120)
ENERGY = (120, 230, 150)
ENERGY_LOW = (240, 140, 100)


def wrap_text(text: str, font: pygame.font.Font, width: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split(" "):
            trial = (cur + " " + word).strip()
            if font.size(trial)[0] <= width:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


class UI:
    def __init__(self, screen_w: int, screen_h: int):
        self.w, self.h = screen_w, screen_h
        self.font = pygame.font.SysFont("consolas", 14)
        self.small = pygame.font.SysFont("consolas", 11)
        self.big = pygame.font.SysFont("consolas", 20, bold=True)
        self.toasts: list[list] = []  # [text, ttl]

    def toast(self, text: str, ttl: float = 3.5) -> None:
        self.toasts.append([text, ttl])
        self.toasts = self.toasts[-4:]

    def update(self, dt: float) -> None:
        for t in self.toasts:
            t[1] -= dt
        self.toasts = [t for t in self.toasts if t[1] > 0]

    # ---- primitives --------------------------------------------------------

    def _panel(self, surf: pygame.Surface, rect: pygame.Rect) -> None:
        box = pygame.Surface(rect.size, pygame.SRCALPHA)
        box.fill(PANEL_BG)
        surf.blit(box, rect.topleft)
        pygame.draw.rect(surf, PANEL_BORDER, rect, 1, border_radius=4)

    def _text(self, surf, text, x, y, color=TEXT, font=None) -> int:
        font = font or self.font
        img = font.render(text, True, color)
        surf.blit(img, (x, y))
        return y + font.get_height() + 2

    def _moon_icon(self, surf, cx, cy, phase, cycle, color, label) -> None:
        r = 7
        pygame.draw.circle(surf, (40, 35, 60), (cx, cy), r)
        illum = (1 - math.cos(math.tau * phase / cycle)) / 2
        if illum > 0.02:
            lit = tuple(int(c * (0.25 + 0.75 * illum)) for c in color)
            pygame.draw.circle(surf, lit, (cx, cy), max(1, int(r * (0.3 + 0.7 * illum))))
        pygame.draw.circle(surf, DIM, (cx, cy), r, 1)
        img = self.small.render(label, True, DIM)
        surf.blit(img, (cx - img.get_width() // 2, cy + r + 1))

    # ---- HUD ----------------------------------------------------------------

    def draw_hud(self, surf: pygame.Surface, game) -> None:
        bar = pygame.Rect(0, 0, self.w, 34)
        box = pygame.Surface(bar.size, pygame.SRCALPHA)
        box.fill((16, 12, 30, 200))
        surf.blit(box, (0, 0))

        clock = game.clock
        x = 10
        img = self.font.render(f"Day {clock.day}   {clock.clock_text()}", True, TEXT)
        surf.blit(img, (x, 9))
        x += img.get_width() + 24

        # energy bar
        surf.blit(self.font.render("EN", True, DIM), (x, 9))
        x += 26
        frac = game.player.energy / game.player.max_energy
        pygame.draw.rect(surf, (50, 45, 70), (x, 11, 100, 12), border_radius=3)
        col = ENERGY if frac > 0.25 else ENERGY_LOW
        pygame.draw.rect(surf, col, (x, 11, int(100 * frac), 12), border_radius=3)
        x += 116

        img = self.font.render(f"{game.player.credits} cr", True, ACCENT)
        surf.blit(img, (x, 9))
        x += img.get_width() + 24

        self._moon_icon(surf, x + 8, 14, game.moons.phase("ilo", clock.day),
                        game.moons.cycle, (200, 220, 255), "Ilo")
        self._moon_icon(surf, x + 34, 14, game.moons.phase("vesk", clock.day),
                        game.moons.cycle, (255, 200, 170), "Vesk")
        x += 58

        ev = game.events.today_name()
        if game.events.today != "none":
            color = BAD if game.events.today == "ion_storm" else GOOD
            surf.blit(self.font.render(ev, True, color), (x, 9))

        # tool / seed readout + help hint, right-aligned
        help_img = self.small.render("[?] help", True, DIM)
        surf.blit(help_img, (self.w - help_img.get_width() - 10, 11))
        img = self.font.render(game.tool_label(), True, TEXT)
        surf.blit(img, (self.w - img.get_width() - help_img.get_width() - 26, 9))

        if game.events.ion_storm_active(clock.hour):
            warn = self.big.render("ION STORM — SHELTER AT THE HABITAT!", True, BAD)
            surf.blit(warn, ((self.w - warn.get_width()) // 2, 40))

        # toasts
        y = self.h - 28
        for text, ttl in reversed(self.toasts):
            img = self.font.render(text, True, TEXT)
            bg = pygame.Surface((img.get_width() + 14, img.get_height() + 6), pygame.SRCALPHA)
            bg.fill((16, 12, 30, min(220, int(255 * ttl))))
            surf.blit(bg, ((self.w - bg.get_width()) // 2, y - 3))
            surf.blit(img, ((self.w - img.get_width()) // 2, y))
            y -= 26

    # ---- panels ---------------------------------------------------------------

    def draw_dialogue(self, surf, speaker: str, text: str) -> None:
        rect = pygame.Rect(40, self.h - 130, self.w - 80, 110)
        self._panel(surf, rect)
        y = self._text(surf, speaker, rect.x + 14, rect.y + 10, ACCENT)
        for line in wrap_text(text, self.font, rect.w - 28)[:4]:
            y = self._text(surf, line, rect.x + 14, y)
        self._text(surf, "[E] continue", rect.right - 110, rect.bottom - 22, DIM, self.small)

    def draw_inventory(self, surf, game) -> None:
        rect = pygame.Rect(self.w // 2 - 240, 60, 480, 360)
        self._panel(surf, rect)
        y = self._text(surf, "INVENTORY", rect.x + 14, rect.y + 10, ACCENT, self.big)
        y += 4
        items = game.inventory.items()
        if not items:
            self._text(surf, "(empty)", rect.x + 14, y, DIM)
        for s in items[:18]:
            name = game.defs.item_name(s["id"])
            value = game.defs.sale_value(s["id"])
            tail = f"  (sells {value} cr)" if value else ""
            y = self._text(surf, f"{name} x{s['qty']}{tail}", rect.x + 14, y)
        self._text(surf, "[I] close   [G] near an NPC gifts the first crop stack",
                   rect.x + 14, rect.bottom - 24, DIM, self.small)

    def draw_shop(self, surf, game) -> None:
        rect = pygame.Rect(self.w // 2 - 280, 50, 560, 400)
        self._panel(surf, rect)
        mode = "SELL" if game.shop_mode == "sell" else "BUY"
        self._text(surf, f"SHIPPING POD — {mode}   [Tab] switch   [Esc] close",
                   rect.x + 14, rect.y + 10, ACCENT)
        y = rect.y + 40
        rows = game.shop_rows()
        if not rows:
            self._text(surf, "(nothing here)", rect.x + 14, y, DIM)
        for i, row in enumerate(rows[:14]):
            color = ACCENT if i == game.shop_index else TEXT
            marker = "> " if i == game.shop_index else "  "
            y = self._text(surf, marker + row["label"], rect.x + 14, y, color)
        y = rect.bottom - 60
        if game.shop_mode == "sell":
            self._text(surf, "[Enter] ship 1   [Shift+Enter] ship stack — paid overnight",
                       rect.x + 14, y, DIM, self.small)
            bin_total = sum(game.defs.sale_value(i) * q
                            for i, q in game.shipping_bin.contents.items())
            self._text(surf, f"In shipping bin tonight: {bin_total} cr",
                       rect.x + 14, y + 16, GOOD)
        else:
            self._text(surf, f"[Enter] buy 1 seed packet — you have {game.player.credits} cr",
                       rect.x + 14, y, DIM, self.small)

    def draw_terminal(self, surf, game) -> None:
        rect = pygame.Rect(self.w // 2 - 240, 70, 480, 320)
        self._panel(surf, rect)
        y = self._text(surf, "HABITAT TERMINAL", rect.x + 14, rect.y + 10, ACCENT, self.big)
        y += 6
        y = self._text(surf, f"Today:    {game.events.today_name()}", rect.x + 14, y)
        y = self._text(surf, f"Tomorrow: {game.events.forecast_name()}", rect.x + 14, y, GOOD)
        y += 10
        d = game.clock.day
        y = self._text(surf, f"Ilo:  {game.moons.phase_name('ilo', d)}", rect.x + 14, y)
        y = self._text(surf, f"Vesk: {game.moons.phase_name('vesk', d)}", rect.x + 14, y)
        y += 10
        y = self._text(surf, f"Field resonance: {game.world.avg_field_resonance():.2f}",
                       rect.x + 14, y)
        y = self._text(surf, f"Total harvests:  {game.quests.total_harvests}", rect.x + 14, y)
        y += 10
        for line in wrap_text("Signal monitor: " + game.quests.hint(
                len(game.flora.codex), game.world.avg_field_resonance()),
                self.font, rect.w - 28):
            y = self._text(surf, line, rect.x + 14, y, ACCENT)
        self._text(surf, "[Esc] close", rect.x + 14, rect.bottom - 24, DIM, self.small)

    def draw_codex(self, surf, game) -> None:
        rect = pygame.Rect(self.w // 2 - 280, 40, 560, 420)
        self._panel(surf, rect)
        y = self._text(surf, f"FLORA CODEX — {len(game.flora.codex)}/"
                       f"{len(game.flora.species)} documented",
                       rect.x + 14, rect.y + 10, ACCENT, self.big)
        y += 4
        for set_id, s in game.flora.sets.items():
            done = game.flora.set_complete(set_id)
            title = s["name"] + ("  [COMPLETE]" if done else "")
            y = self._text(surf, title, rect.x + 14, y, GOOD if done else TEXT)
            for sid in game.flora.set_species(set_id):
                sp = game.flora.species[sid]
                if sid in game.flora.codex:
                    y = self._text(surf, f"  {sp['name']}: {sp['entry']}",
                                   rect.x + 14, y, DIM, self.small)
                else:
                    y = self._text(surf, "  ???", rect.x + 14, y, (90, 85, 110), self.small)
            if s["unlock_seed"] and done:
                name = game.defs.get(s["unlock_seed"])["name"]
                y = self._text(surf, f"  Unlocked at the shipping pod: {name} seeds",
                               rect.x + 14, y, ACCENT, self.small)
            y += 4
        self._text(surf, "[C] close", rect.x + 14, rect.bottom - 24, DIM, self.small)

    def draw_journal(self, surf, game) -> None:
        rect = pygame.Rect(self.w // 2 - 260, 50, 520, 400)
        self._panel(surf, rect)
        y = self._text(surf, f"JOURNAL — {game.quests.name}",
                       rect.x + 14, rect.y + 10, ACCENT, self.big)
        y += 4
        entries = game.quests.journal_entries()
        if not entries:
            y = self._text(surf, "Nothing strange yet. Just farm.", rect.x + 14, y, DIM)
        for step in entries:
            y = self._text(surf, f"[x] {step['title']}", rect.x + 14, y, GOOD)
            for line in wrap_text(step["journal"], self.font, rect.w - 40):
                y = self._text(surf, "  " + line, rect.x + 14, y, DIM)
            y += 2
        y += 6
        hint = game.quests.hint(len(game.flora.codex), game.world.avg_field_resonance())
        for line in wrap_text("Next: " + hint, self.font, rect.w - 28):
            y = self._text(surf, line, rect.x + 14, y, ACCENT)
        self._text(surf, "[J] close", rect.x + 14, rect.bottom - 24, DIM, self.small)

    def draw_sleep_prompt(self, surf, options: list[str], index: int) -> None:
        rect = pygame.Rect(self.w // 2 - 170, self.h // 2 - 70, 340, 140)
        self._panel(surf, rect)
        y = self._text(surf, "Habitat", rect.x + 14, rect.y + 10, ACCENT)
        y += 4
        for i, opt in enumerate(options):
            marker = "> " if i == index else "  "
            y = self._text(surf, marker + opt, rect.x + 14, y,
                           ACCENT if i == index else TEXT)

    def draw_help(self, surf) -> None:
        rect = pygame.Rect(self.w // 2 - 290, 40, 580, 430)
        self._panel(surf, rect)
        y = self._text(surf, "CONTROLS", rect.x + 16, rect.y + 10, ACCENT, self.big)
        y += 4
        entries = [
            ("WASD / Arrows", "Move"),
            ("1", "Terra-Hoe — till soil, clear wilted crops"),
            ("2", "Watering Canister — water crops daily"),
            ("3", "Harvester — collect ripe crops"),
            ("4", "Flora Scanner — document wild plants (codex)"),
            ("5", "Seed Planter — plant the selected seed"),
            ("Tab", "Cycle which seed is selected"),
            ("Space", "Use current tool on the highlighted tile"),
            ("E", "Interact: talk, terminal, shipping pod, habitat door"),
            ("G", "Gift your first crop stack to a nearby NPC"),
            ("I / C / J", "Inventory / Flora Codex / Journal"),
            ("F5", "Quick-save"),
            ("F1", "Debug overlay ([T] +1 hour, [N] next day)"),
            ("Esc", "Close panel / quit"),
        ]
        key_w = max(self.font.size(k)[0] for k, _ in entries) + 18
        for key_label, desc in entries:
            self._text(surf, key_label, rect.x + 16, y, ACCENT)
            y = self._text(surf, desc, rect.x + 16 + key_w, y)
        y += 6
        tips = ("Sell crops at the shipping pod (paid overnight). Sleep at the habitat "
                "door to start the next day. Rotate crop families to keep the soil happy.")
        for line in wrap_text(tips, self.small, rect.w - 32):
            y = self._text(surf, line, rect.x + 16, y, DIM, self.small)
        self._text(surf, "[?] or [Esc] close", rect.x + 16, rect.bottom - 24, DIM, self.small)

    # ---- debug -------------------------------------------------------------

    def draw_debug(self, surf, game, fps: float, ts: int) -> None:
        for x, y, tile in game.world.iter_tiles():
            if tile.kind == "soil":
                img = self.small.render(f"{int(tile.resonance * 100)}", True, (255, 255, 120))
                surf.blit(img, (x * ts + 2, y * ts + 2))
        d = game.clock.day
        lines = [
            f"FPS {fps:.0f}   day {d}  hour {game.clock.hour:.2f}",
            f"Ilo {game.moons.phase_name('ilo', d)} ({game.moons.phase('ilo', d)})  "
            f"Vesk {game.moons.phase_name('vesk', d)} ({game.moons.phase('vesk', d)})",
            f"event today={game.events.today} forecast={game.events.forecast}",
            f"wild plants {len(game.flora.wild)}  codex {len(game.flora.codex)}",
            f"avg resonance {game.world.avg_field_resonance():.3f}  "
            f"harvests {game.quests.total_harvests}",
            "debug keys: [T] +1 hour  [N] next day",
        ]
        y = 40
        for line in lines:
            img = self.small.render(line, True, (255, 255, 140))
            bg = pygame.Surface((img.get_width() + 6, img.get_height() + 2), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 160))
            surf.blit(bg, (8, y))
            surf.blit(img, (11, y + 1))
            y += 15
