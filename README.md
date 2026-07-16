# AlphaFarm — Veridia

A cozy-with-mystery 2D top-down farming/life sim on the alien planet **Veridia**: violet skies,
twin moons, bioluminescent nights — and soil that is slowly revealed to be listening.

Built with Python + [pygame-ce](https://pyga.me/) (imports as `pygame`). The player and
environment use sprite sheets from `assets/` (`astro_spritesheet.png`, `outside.png`), loaded by
`game/assets.py`; everything else (crops, NPCs, crystals, buildings) is still procedural shapes
in `game/render.py` and falls back gracefully if the sheets are missing. All content and
tunables live in JSON under `data/`.

## Run it

```
uv sync
uv run python main.py
```

(Or `pip install pygame-ce` and `python main.py`.)

Tests and the headless smoke run:

```
uv run pytest
uv run python tests/smoke.py
```

## Controls

| Key | Action |
| --- | --- |
| WASD / Arrows | Move (4-direction) |
| 1 / 2 / 3 / 4 / 5 | Terra-Hoe / Watering Canister / Harvester / Flora Scanner / Seed Planter |
| Tab | Cycle selected seed (for the planter) |
| Space | Use current tool on the highlighted tile |
| E | Interact (talk, terminal, shipping pod, habitat door, great crystal) / advance dialogue |
| G | Gift your first crop stack to a nearby NPC |
| I / C / J | Inventory / Flora Codex / Journal |
| ? (or /) | Help — full controls list in-game |
| F5 | Quick-save |
| F1 | Debug overlay (tile resonance, moon phases, FPS) |
| T / N | (debug only) skip +1 hour / skip to next day |
| Esc | Close panel / quit |

## The loop

Till → plant → water → wait → harvest. Ship crops from the pod on the landing pad; it pays out
in credits overnight and sells seeds. Sleep at the habitat door to start the next day (autosaves
to `saves/savegame.json`). Energy drains with tool use — collapse at 02:00 and you wake up rough.

**Crops:** Lumen Berries (3d, glow at night when ripe), Gravity Melons (7d, float), Whisper Wheat
(5d, sways with no wind), Crimson Tubers (4d, underground — watch for the soil bulge), Prism Pods
(10d, high value, must be watered *exactly once* per day or they wilt).

## Alien systems

- **Twin moons.** Ilo and Vesk each run an 8-day phase cycle (HUD icons). Each crop grows faster
  under its patron moon's full phase — and may mutate into a rare 3x-value variant.
- **Living soil.** Every tile hides a resonance value. Monoculture drains it; rotating crop
  families raises it. High resonance can double harvests. Watch the soil color: ashen gray is
  sulking, rich violet is singing.
- **Atmospheric events.** Spore drifts fertilize random plants, ion storms drain energy outdoors
  (shelter at the habitat door), aurora nights double growth. Tomorrow's forecast is on the
  habitat terminal.
- **Flora scanning.** Scan wild plants (tool 4) into the codex (C). Completing a codex set
  unlocks new seeds at the shipping pod.

## The outpost

Five colonists live southeast: Dr. Sylla Veen (xenobotanist), Foreman Hux Craddock, Merla
"Tinks" Odrai (shipwrecked trader), CARE-7 (AI caretaker), and Juno Pell (comms tech). They keep
daily schedules, remember kindness (talk daily, gift crops they love), and open up as friendship
grows. Somewhere beneath the farm, something is dreaming — the questline **The Dreaming Ground**
unlocks through harvests, codex entries, and soil resonance. Start by farming; the terminal will
tell you when the ground notices.

## Project structure

```
main.py               # game loop, input, state routing
game/
  config.py           # JSON loading (data/config.json holds every tunable)
  assets.py           # sprite sheet slicing (assets/ -> render.SPRITES)
  world.py            # tile grid, farming actions, soil resonance
  player.py           # movement, collision, energy, tools
  crops.py            # crop defs, growth, moon affinities, mutations
  time_system.py      # clock, day/night, twin moon phases
  inventory.py        # grid inventory, credits, shipping bin
  events.py           # spore drift / ion storm / aurora + forecast
  flora.py            # wild plants, scanner, codex, seed unlocks
  npcs.py             # schedules, friendship, gifts, dialogue
  quest.py            # The Dreaming Ground questline
  save_load.py        # JSON save/load
  render.py           # ALL drawing (drop sprite sheets in here later)
  ui.py               # HUD, panels, dialogue, debug overlay
data/                 # config, map, crops, items, flora, npcs, dialogue, quests (all editable)
saves/                # savegame.json (created at runtime)
tests/                # pytest suite + headless smoke run
```
