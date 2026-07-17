# AlphaFarm — Task Checklist

## Setup
- [x] uv project + pygame-ce + pytest
- [x] implementation_plan.md

## Phase 1 — Core loop
- [x] data/config.json (all tunables)
- [x] data/map.json (40x30 map + legend, generated & validated)
- [x] data/crops.json, data/items.json
- [x] game/config.py
- [x] game/time_system.py (clock + moons)
- [x] game/crops.py
- [x] game/world.py
- [x] game/inventory.py
- [x] game/player.py
- [x] game/render.py
- [x] game/ui.py
- [x] game/save_load.py
- [x] main.py (game loop, states)
- [x] Phase 1 unit tests green
- [x] Phase 1 headless smoke run clean

## Phase 2 — Alien systems
- [x] Moon affinities + mutations wired into growth
- [x] Living soil resonance + soil tint cues
- [x] game/events.py (spore drift / ion storm / aurora + forecast, terminal UI)
- [x] data/wild_flora.json + game/flora.py (scanner, codex, seed unlocks)
- [x] Phase 2 unit tests green
- [x] Phase 2 headless smoke run clean

## Phase 3 — Life sim
- [x] data/npcs.json + data/dialogue.json + game/npcs.py (schedules, friendship, gifts)
- [x] data/quests.json + game/quest.py (5-step questline, journal)
- [x] Phase 3 unit tests green
- [x] Phase 3 headless smoke run clean

## Quality
- [x] F1 debug overlay + time-skip keys
- [x] README.md
- [x] Full pytest suite green (83 tests)
- [x] Final smoke run + rendered day/night/shop/debug screenshots verified

## Sprites (2026-07-16)
- [x] astro_spritesheet.png — 4-direction animated player (game/assets.py)
- [x] outside.png — grass/flowers, dirt field, paving, boulders, habitat dome
- [x] tile_size 24 -> 32 (1:1 tileset pixels, window 1280x960)
- [x] Habitat reshaped to 3x5 to match the dome sprite (terminal is now a kiosk beside it)

## Sprites round 2 (2026-07-16)
- [x] npc_*.png robots for the five NPCs (color-matched, set in data/npcs.json)
- [x] building_bar/shop_384.png — outpost reworked to 2 buildings + 2 plazas
- [x] Crop growth-stage sprites + floating watermelon for ripe Gravity Melons
- [x] All 9 wild-flora species as distinct sprites (boxes in data/wild_flora.json)

## Packaging (2026-07-16)
- [x] Frozen-aware paths in game/config.py (bundle for data/assets, exe-dir for saves)
- [x] build.py — PyInstaller onefile build for the current OS (+ --zip archive)
- [x] pyinstaller in a `build` uv dependency-group
- [x] .github/workflows/build.yml — CI builds Windows + Linux, releases on v* tags
- [x] Verified: exe runs standalone from a clean dir (bundled assets load); 86 tests pass

## Follow-up ideas (not started)
- [ ] SciFiCreatures_NES_4x30_alphaBG.png — no creature system yet; could become
      night critters or ion-storm hazards
- [ ] Interior habitat scene instead of door-tile shelter
- [ ] Mouse support for shop/inventory
- [ ] Sound (ambient hum, moon chimes)
