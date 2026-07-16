# AlphaFarm — Implementation Plan

A 2D top-down farming/life-sim on the alien planet **Veridia**, built with Python + **pygame-ce**
(import-compatible fork of Pygame, actively maintained). All content lives in JSON under `data/`;
all tunables live in `data/config.json`. Placeholder graphics are procedural shapes routed through
a single render module so sprite sheets can be dropped in later.

## Stack

- Python 3.12, managed with `uv`
- `pygame-ce` for rendering/input/timing (imports as `pygame`)
- `pytest` for unit tests (logic modules are display-free and testable headless)

## File structure

```
AlphaFarm/
├── main.py                 # entry point: Game class, main loop, state routing
├── game/
│   ├── config.py           # loads data/config.json, dot-access wrapper
│   ├── world.py            # tile grid, tile state (till/water/crop/resonance), map load
│   ├── player.py           # movement, collision, energy, tool use, facing
│   ├── crops.py            # crop defs from JSON, growth ticks, moon/resonance modifiers
│   ├── time_system.py      # game clock, day cycle, twin-moon phases (Ilo & Vesk)
│   ├── inventory.py        # stackable grid inventory + credits + shipping bin
│   ├── events.py           # atmospheric events: spore drift / ion storm / aurora + forecast
│   ├── flora.py            # wild flora spawning, scanner, codex sets, seed unlocks
│   ├── npcs.py             # NPC schedules, friendship, gifts, dialogue selection
│   ├── quest.py            # 5-step "Dreaming Ground" questline, milestone gating
│   ├── save_load.py        # full game state <-> saves/savegame.json
│   ├── render.py           # ALL drawing: tiles, crops, entities, lighting (sprite seam)
│   └── ui.py               # HUD, panels (inventory/codex/journal/shop/dialogue), debug overlay
├── data/
│   ├── config.json         # every tunable value
│   ├── map.json            # 40x30 ASCII tile map + legend
│   ├── crops.json          # 5 starter crops + unlockable crops + mutations
│   ├── items.json          # item display metadata
│   ├── wild_flora.json     # 9 scannable species in 3 codex sets
│   ├── npcs.json           # 5 NPCs: schedules, gift preferences, colors
│   ├── dialogue.json       # per-NPC dialogue by friendship tier + gift reactions
│   └── quests.json         # questline steps, gates, text
├── saves/                  # savegame.json (created at runtime)
├── tests/                  # pytest suite for all logic modules
└── README.md
```

## Phase 1 — Core loop

1. 40x30 tile map from `data/map.json`: rock border, tillable field, crystals, habitat + door,
   landing pad + shipping pod, terminal. Map validated on load.
2. Player: 4-dir WASD/arrow movement (delta-time, px/sec), AABB collision vs solid tiles,
   facing-based tile targeting. Tools on number keys: 1 hoe, 2 watering canister, 3 harvester,
   (4 scanner in P2), 5 plant mode; Tab cycles seed; Space uses tool; E interacts.
3. Day/night: 1 day = 10 real min (config). Day runs 06:00 → 02:00, then forced collapse.
   Night = translucent violet overlay (never full dark) + additive glow from crystals and ripe
   Lumen Berries. Energy 0–100; tools drain it; sleeping at the habitat door starts the next
   day and autosaves.
4. Farming: till → plant → water → grow N days → harvest. 5 starter crops per spec, incl.
   Prism Pods (wilt if not watered exactly once per day) and Crimson Tubers (drawn as soil bulge).
5. Inventory: 24-slot stacking grid (I key). Shipping pod: deposit crops, converted to credits
   overnight; also sells seeds (buy menu).
6. Save/load: JSON at `saves/savegame.json`; loads automatically on launch; saves on sleep.

## Phase 2 — Alien systems

1. Twin moons Ilo & Vesk, independent 8-day phase cycles (offset start). Crop moon affinities:
   growth bonus and mutation chance when the right moon is full. Moon phase icons in HUD.
2. Living soil: hidden per-tile resonance (0.1–1.0, starts 0.5). Replanting the same crop drops
   it; rotating raises it. Yield multiplier at harvest. Surfaced via soil tint only.
3. Atmospheric events, rolled one day ahead (forecast on terminal): spore drifts auto-fertilize
   random tiles, ion storms drain energy outdoors (shelter at habitat door), aurora nights
   double growth.
4. Scanner tool (key 4) documents wild flora into a codex (C key). 3 sets × 3 species;
   completing a set unlocks a new purchasable seed.

## Phase 3 — Life sim

1. Outpost settlement (SE corner) with 5 NPCs on daily waypoint schedules, friendship meters,
   ~10 dialogue lines each varying by friendship tier (all in JSON).
2. Gifts (G key with a crop selected): loved/liked/disliked per NPC.
3. "The Dreaming Ground": 5-step mystery questline gated on total harvests, codex entries, and
   average field resonance; ends at the great crystal at night. Journal on J key.

## Quality

- 60 FPS target, delta-time movement, no magic numbers outside config/data JSON.
- F1 debug overlay: per-tile resonance, moon phases, clock; T = +1 hour, N = next day.
- README with controls, run instructions, structure.
- pytest suite over crops, clock/moons, inventory, resonance, events, save/load, quest gating.

## Verification per phase

Run `uv run pytest`, then a headless smoke run (SDL dummy driver, ~120 simulated frames) to
prove the game boots, updates, and draws without errors.
