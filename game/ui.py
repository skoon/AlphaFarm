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

HOTBAR_TOOLS = ("hoe", "water", "harvest", "scanner", "plant")
HOTBAR_SLOT = 44
HOTBAR_GAP = 6
HOTBAR_MARGIN_BOTTOM = 12
CHIP_W = 150
CHIP_GAP = 10


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
        self.hotbar_rects: list[tuple[pygame.Rect, str]] = []
        self.shop_row_rects: list[pygame.Rect] = []
        self.shop_tab_rects: dict[str, pygame.Rect] = {}
        self.upgrade_row_rects: list[pygame.Rect] = []
        self.kiln_row_rects: list[pygame.Rect] = []

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

        # help hint, right-aligned
        help_img = self.small.render("[?] help", True, DIM)
        surf.blit(help_img, (self.w - help_img.get_width() - 10, 11))

        if game.events.ion_storm_active(clock.hour):
            warn = self.big.render("ION STORM — SHELTER AT THE HABITAT!", True, BAD)
            surf.blit(warn, ((self.w - warn.get_width()) // 2, 40))

        # toasts (raised above the hotbar)
        y = self.h - 88
        for text, ttl in reversed(self.toasts):
            img = self.font.render(text, True, TEXT)
            bg = pygame.Surface((img.get_width() + 14, img.get_height() + 6), pygame.SRCALPHA)
            bg.fill((16, 12, 30, min(220, int(255 * ttl))))
            surf.blit(bg, ((self.w - bg.get_width()) // 2, y - 3))
            surf.blit(img, ((self.w - img.get_width()) // 2, y))
            y -= 26

    # ---- hotbar ---------------------------------------------------------------

    def _draw_tool_icon(self, surf: pygame.Surface, rect: pygame.Rect, tool: str) -> None:
        cx, cy = rect.center
        if tool == "hoe":
            pygame.draw.line(surf, (180, 140, 100), (rect.x + 10, rect.bottom - 8),
                             (rect.right - 12, rect.y + 10), 3)
            pygame.draw.rect(surf, (170, 170, 180),
                             (rect.right - 19, rect.y + 6, 11, 7), border_radius=1)
        elif tool == "water":
            body = pygame.Rect(cx - 9, cy - 6, 16, 16)
            pygame.draw.rect(surf, (140, 190, 230), body, border_radius=3)
            pygame.draw.rect(surf, DIM, body, 1, border_radius=3)
            pygame.draw.polygon(surf, (120, 180, 255),
                                [(cx + 10, cy - 9), (cx + 17, cy - 1), (cx + 10, cy - 1)])
        elif tool == "harvest":
            for dx in (-8, 0, 8):
                pygame.draw.line(surf, (220, 200, 150), (cx + dx, cy - 10), (cx + dx, cy + 8), 3)
        elif tool == "scanner":
            pygame.draw.circle(surf, (200, 220, 255), (cx - 4, cy - 4), 8, 2)
            pygame.draw.line(surf, (200, 220, 255), (cx + 2, cy + 2), (cx + 12, cy + 12), 3)
        elif tool == "plant":
            pygame.draw.ellipse(surf, (110, 80, 60), (cx - 12, cy + 2, 24, 10))
            pygame.draw.line(surf, (120, 220, 140), (cx, cy + 2), (cx, cy - 10), 3)
            pygame.draw.polygon(surf, (120, 220, 140),
                                [(cx, cy - 10), (cx - 6, cy - 4), (cx, cy - 6)])
            pygame.draw.polygon(surf, (120, 220, 140),
                                [(cx, cy - 10), (cx + 6, cy - 4), (cx, cy - 6)])

    def draw_hotbar(self, surf: pygame.Surface, game) -> None:
        self.hotbar_rects = []
        n = len(HOTBAR_TOOLS)
        total_w = n * HOTBAR_SLOT + (n - 1) * HOTBAR_GAP
        x0 = self.w // 2 - total_w // 2
        y0 = self.h - HOTBAR_SLOT - HOTBAR_MARGIN_BOTTOM
        for i, tool in enumerate(HOTBAR_TOOLS):
            rect = pygame.Rect(x0 + i * (HOTBAR_SLOT + HOTBAR_GAP), y0, HOTBAR_SLOT, HOTBAR_SLOT)
            self._panel(surf, rect)
            if game.player.tool == tool:
                pygame.draw.rect(surf, ACCENT, rect, 2, border_radius=4)
            self._draw_tool_icon(surf, rect, tool)
            key_img = self.small.render(str(i + 1), True, DIM)
            surf.blit(key_img, (rect.x + 3, rect.y + 2))
            self.hotbar_rects.append((rect, tool))

        chip_rect = pygame.Rect(x0 + total_w + CHIP_GAP, y0, CHIP_W, HOTBAR_SLOT)
        self._panel(surf, chip_rect)
        seed = game.player.selected_seed
        if seed:
            if seed.startswith("gear:"):
                color, name = (170, 175, 190), game.defs.item_name(seed)
                have = game.inventory.count(seed)
            else:
                d = game.defs.get(seed)
                color, name = tuple(d["color"]), d["name"]
                have = game.inventory.count(f"seed:{seed}")
            swatch = pygame.Rect(chip_rect.x + 8, chip_rect.y + 8, 14, 14)
            pygame.draw.rect(surf, color, swatch, border_radius=3)
            name_img = self.small.render(name, True, TEXT)
            surf.blit(name_img, (swatch.right + 6, chip_rect.y + 5))
            qty_img = self.small.render(f"x{have}", True, ACCENT)
            surf.blit(qty_img, (swatch.right + 6, chip_rect.y + 5 + name_img.get_height()))
        else:
            img = self.small.render("no seed (Tab)", True, DIM)
            surf.blit(img, (chip_rect.x + 8,
                            chip_rect.y + chip_rect.h // 2 - img.get_height() // 2))

    # ---- panels ---------------------------------------------------------------

    def draw_dialogue(self, surf, speaker: str, text: str,
                      portrait_id: str | None = None, pages_left: int = 0) -> None:
        from game.render import SPRITES
        portrait = SPRITES.get(f"portrait:{portrait_id}") if portrait_id else None
        rect = pygame.Rect(40, self.h - 170, self.w - 80, 150)
        self._panel(surf, rect)
        tx = rect.x + 14
        if portrait:
            frame = pygame.Rect(rect.x + 12, rect.y + 12, 126, 126)
            pygame.draw.rect(surf, (36, 28, 60), frame, border_radius=6)
            surf.blit(portrait, portrait.get_rect(midbottom=(frame.centerx, frame.bottom - 2)))
            pygame.draw.rect(surf, PANEL_BORDER, frame, 1, border_radius=6)
            tx = frame.right + 14
        y = self._text(surf, speaker, tx, rect.y + 10, ACCENT)
        y += 2
        for line in wrap_text(text, self.font, rect.right - 14 - tx)[:6]:
            y = self._text(surf, line, tx, y)
        more = f"[E] continue ({pages_left} more)" if pages_left else "[E] continue"
        self._text(surf, more, rect.right - 150, rect.bottom - 22, DIM, self.small)

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
        self.shop_row_rects = []
        self.shop_tab_rects = {}
        rect = pygame.Rect(self.w // 2 - 280, 50, 560, 400)
        self._panel(surf, rect)
        self._text(surf, "SHIPPING POD          [Esc] close", rect.x + 14, rect.y + 10, ACCENT)

        tab_x = rect.x + 224
        tab_y = rect.y + 10
        for label, key in (("Sell", "sell"), ("Buy", "buy")):
            color = ACCENT if game.shop_mode == key else DIM
            img = self.font.render(f"[{label}]", True, color)
            tab_rect = pygame.Rect(tab_x, tab_y, img.get_width(), img.get_height())
            surf.blit(img, tab_rect.topleft)
            self.shop_tab_rects[key] = tab_rect
            tab_x += img.get_width() + 8

        y = rect.y + 40
        rows = game.shop_rows()
        if not rows:
            self._text(surf, "(nothing here)", rect.x + 14, y, DIM)
        for i, row in enumerate(rows[:14]):
            color = ACCENT if i == game.shop_index else TEXT
            marker = "> " if i == game.shop_index else "  "
            row_y = y
            y = self._text(surf, marker + row["label"], rect.x + 14, y, color)
            self.shop_row_rects.append(pygame.Rect(rect.x + 14, row_y, rect.w - 28,
                                                   y - row_y))
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
        if game.npcs.perk("juno"):
            y = self._text(surf, f"Day after: {game.events.forecast2_name()}  "
                                 f"(Juno's extended feed)", rect.x + 14, y, GOOD)
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
        y += 8
        favor_lines = game.favors.describe(game.defs, game.clock.day)
        y = self._text(surf, "Favors:", rect.x + 14, y)
        for line in favor_lines or ["none right now"]:
            y = self._text(surf, "  " + line, rect.x + 14, y, DIM)
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
        y += 6
        favor_lines = game.favors.describe(game.defs, game.clock.day)
        y = self._text(surf, "Favors:", rect.x + 14, y)
        for line in favor_lines or ["none right now"]:
            y = self._text(surf, "  " + line, rect.x + 14, y, DIM)
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

    def draw_upgrades(self, surf, game) -> None:
        self.upgrade_row_rects = []
        rect = pygame.Rect(self.w // 2 - 300, 60, 600, 400)
        self._panel(surf, rect)
        self._text(surf, "TINKS' GEAR — 'Everything salvaged, everything works. Mostly.'",
                   rect.x + 16, rect.y + 10, ACCENT)
        y = rect.y + 44
        rows = game.upgrade_rows()
        for i, row in enumerate(rows):
            row_rect = pygame.Rect(rect.x + 10, y - 3, rect.w - 20, 48)
            self.upgrade_row_rects.append(row_rect)
            selected = i == game.upgrade_index
            if selected:
                hl = pygame.Surface(row_rect.size, pygame.SRCALPHA)
                hl.fill((255, 210, 120, 26))
                surf.blit(hl, row_rect.topleft)
            if row["owned"] >= row["max"]:
                status, scolor = "OWNED" if row["max"] == 1 else f"MAX {row['max']}", DIM
            else:
                tag = f" ({row['owned']}/{row['max']})" if row["max"] > 1 else ""
                status, scolor = f"{row['price']} cr{tag}", ACCENT
            name_color = ACCENT if selected else TEXT
            self._text(surf, ("> " if selected else "  ") + row["name"],
                       rect.x + 16, y, name_color)
            img = self.font.render(status, True, scolor)
            surf.blit(img, (rect.right - 20 - img.get_width(), y))
            self._text(surf, row["desc"], rect.x + 34, y + 18, DIM, self.small)
            y += 52
        self._text(surf, f"Credits: {game.player.credits}   [Enter/click] buy   "
                         f"[Esc] leave", rect.x + 16, rect.bottom - 26, DIM, self.small)

    def draw_kiln(self, surf, game) -> None:
        self.kiln_row_rects = []
        rect = pygame.Rect(self.w // 2 - 300, 60, 600, 400)
        self._panel(surf, rect)
        self._text(surf, "BIO-KILN — slow heat, patient profit",
                   rect.x + 16, rect.y + 10, ACCENT)
        y = rect.y + 44
        rows = game.kiln_rows()
        if not rows:
            self._text(surf, "(no processable crops in your bag)",
                       rect.x + 16, y, DIM)
        for i, row in enumerate(rows):
            row_rect = pygame.Rect(rect.x + 10, y - 3, rect.w - 20, 28)
            self.kiln_row_rects.append(row_rect)
            selected = i == game.kiln_index
            if selected:
                hl = pygame.Surface(row_rect.size, pygame.SRCALPHA)
                hl.fill((255, 210, 120, 26))
                surf.blit(hl, row_rect.topleft)
            color = ACCENT if selected else TEXT
            self._text(surf, ("> " if selected else "  ") + row["label"],
                       rect.x + 16, y, color)
            y += 30
        self._text(surf, "[Enter/click] load  [Esc] close",
                   rect.x + 16, rect.bottom - 26, DIM, self.small)

    def draw_day_summary(self, surf, game) -> None:
        s = game.day_summary
        if not s:
            return
        fade = min(1.0, game.summary_age * 2.5)
        black = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        black.fill((8, 4, 18, int(215 * fade)))
        surf.blit(black, (0, 0))
        if game.summary_age < 0.35:
            return
        rect = pygame.Rect(self.w // 2 - 250, self.h // 2 - 195, 500, 390)
        self._panel(surf, rect)
        y = self._text(surf, f"Day {s['day']} on Veridia", rect.x + 18, rect.y + 14,
                       ACCENT, self.big)
        if s["collapsed"]:
            y = self._text(surf, "You collapsed at 02:00 — CARE-7 dragged you to bed.",
                           rect.x + 18, y + 2, (255, 170, 150), self.small)
        y += 8
        if s["lines"]:
            y = self._text(surf, "Shipped overnight:", rect.x + 18, y, DIM)
            for name, qty, val in s["lines"][:8]:
                y = self._text(surf, f"  {qty}x {name}", rect.x + 18, y)
                img = self.font.render(f"{val} cr", True, ACCENT)
                surf.blit(img, (rect.right - 18 - img.get_width(),
                                y - self.font.get_height() - 2))
            y = self._text(surf, f"Total payout: {s['income']} cr", rect.x + 18,
                           y + 4, ACCENT)
        else:
            y = self._text(surf, "Nothing in the shipping pod last night.",
                           rect.x + 18, y, DIM)
        y += 10
        y = self._text(surf, f"Today: {s['today']}", rect.x + 18, y)
        y = self._text(surf, f"Tomorrow: {s['forecast']}", rect.x + 18, y)
        y = self._text(surf, f"Moons — Ilo: {s['ilo']}, Vesk: {s['vesk']}",
                       rect.x + 18, y)
        if s["spored"]:
            y = self._text(surf, f"A spore drift fertilized {s['spored']} of your plants.",
                           rect.x + 18, y, (240, 180, 240))
        if s.get("care7"):
            y = self._text(surf, f"CARE-7 watered {s['care7']} plants before you woke.",
                           rect.x + 18, y, (150, 200, 240))
        if s.get("drones"):
            y = self._text(surf, f"Your drones watered {s['drones']} tiles at first light.",
                           rect.x + 18, y, (170, 175, 190))
        for line in s.get("favors", []):
            y = self._text(surf, line, rect.x + 18, y, ACCENT)
        self._text(surf, "[E] rise and shine", rect.x + 18, rect.bottom - 26,
                   DIM, self.small)

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
            ("Mouse", "Click hotbar to switch tool; click shop rows/tabs"),
            ("Space", "Use current tool on the highlighted tile"),
            ("E", "Interact: talk, terminal, shipping pod, door, SHOP, kiln"),
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

    def draw_debug_world(self, surf, game, ts: int) -> None:
        """World-space debug marks, drawn pre-scale so they track the camera."""
        for x, y, tile in game.world.iter_tiles():
            if tile.kind == "soil":
                img = self.small.render(f"{int(tile.resonance * 100)}", True, (255, 255, 120))
                surf.blit(img, (x * ts + 2, y * ts + 2))

    def draw_debug(self, surf, game, fps: float, ts: int) -> None:
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
