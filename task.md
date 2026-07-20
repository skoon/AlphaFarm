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

## Polish & Depth roadmap (see implementation_plan.md)

### Phase A — Game feel
- [x] A1 Following camera at 2x zoom (game/camera.py, culled drawing)
- [x] A2 Sound: tools/gen_audio.py -> assets/audio/ (12 WAVs), game/audio.py, hooks
- [x] A3 Juice: particles, tool-swing feedback, floating text, ripe glint
- [x] A4 Time-of-day tint + aurora/storm visuals
- [x] A5 Sleep fade + day-summary card
- [x] A6 Visual hotbar + panel mouse support (Sonnet subagent)
- [x] Phase A tests/smoke/screenshots green (103 tests; dawn/dusk/aurora/storm/summary shots)

### Phase B — NPCs as characters
- [x] B1 Dialogue portraits + multi-page dialogue
- [x] B2 Contextual dialogue conditions (npcs.py selector) + content pass (Opus:
      ~13 conditional lines per NPC across tiers)
- [x] B3 Heart events at 3/7 hearts (data/heart_events.json, fire once, persisted)
- [x] B4 Favors (Sonnet subagent: game/favors.py, data/favors.json, terminal/journal
      sections, day-summary lines, delivery on talk)
- [x] B5 Perks: Tinks seed discount, Juno 2-day forecast, CARE-7 morning watering,
      Sylla soil report (thresholds in config)
- [x] B6 Life signs: BFS pathing (fixes NPCs-through-buildings bug), indoors at
      night/storms, emotes + idle chats
- [x] Phase B tests/smoke green (121 tests; portrait/outpost/terminal/night shots)

### Phase C — Economy arc
- [x] C1 Tinks' gear shop behind the SHOP building door (also closes the
      can't-enter-the-shop backlog bug): Hoe/Canister Mk-II 3-tile rows, Pack
      Expansion (+12 slots), Irrigation Drones (3x3 morning watering, skip Prism
      Pods), placeable via the Planter; hoe packs gear back up
- [x] C2 Bio-Kiln processing (Opus subagent: load/collect flow, kiln UI, goods
      ship via the existing bin; recipes.json + goods registry)
- [x] C3 Balance tests (test_balance.py) + save v2 with backward-compatible load
- [x] Phase C tests/smoke/screenshots green (145 tests; shop/farm/kiln shots)

### Phase D — Mine, endgame, QoL
- [x] D1a Multi-map + the mine: data/mine.json cave at Hux's dig site, ore seams
      (ferrite/lumite/quartz, HP + overnight regen), hoe-mining, always-dark
      lighting, minerals ship via the bin, Hux 4h perk +20% mineral prices,
      collapse underground wakes you at the habitat
- [x] D1b Fauna (Opus subagent): 8 critters from the creatures sheet, farm-night +
      mine habitats, skittish wander, scanner documents into "Veridian Fauna"
      codex set, completion rewards Dream Lotus seeds, counts toward quest gates
- [x] D2 Restoration endgame: 5 offering bundles at the great crystal ->
      permanent buffs (energy/soil recovery/sell bonus/growth/auroras) + ending
- [x] D3 Pause menu (Esc: Resume/Options/Save/Quit-to-Title/Quit), volume options
      persisted to saves/settings.json, three save slots + legacy migration,
      title screen with slot picker and starfield (subagent hit the session
      limit before starting; implemented directly)
- [x] Phase D tests/smoke/screenshots green (174 tests; mine/fauna/restoration/
      pause shots; windowed title-screen launch)

## Post-phase backlog (Scott, 2026-07-19)
- [ ] BUG: player can walk through NPCs (no player-vs-NPC collision; add soft
      collision or push-apart so they read as solid)
- [x] BUG: NPCs walk through buildings — FIXED in Phase B6 (BFS pathfinding; test
      walks Sylla's full commute asserting she never enters a solid tile)
- [x] BUG: the outpost SHOP building can't be entered — FIXED in C1 (interacting
      with the SHOP building opens Tinks' gear shop)
- [ ] Implement the BAR as a real place (door interaction/interior; Hux + evening
      NPC schedules could route through it)
- [ ] Replace synth ambient hum with real music — Scott is sourcing tracks; drop-in
      files at assets/audio/ambient_day.wav / ambient_night.wav (same names), or add
      an ogg/music channel if the tracks are long

## Older follow-up ideas (unscheduled)
- [ ] Interior habitat scene instead of door-tile shelter
- [ ] Controller support (stretch, D3)
