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

## Follow-up ideas (not started)
- [ ] Use npc_*.png portraits/sprites for the five NPCs
- [ ] Use building_bar/shop_384.png for the outpost buildings
- [ ] Crop sprites from outside.png growth-stage rows (cols 12-17, rows 9-12)
- [ ] Wild-flora sprites from outside.png teal plant row (row 13)
- [ ] Interior habitat scene instead of door-tile shelter
- [ ] Mouse support for shop/inventory
- [ ] Sound (ambient hum, moon chimes)
