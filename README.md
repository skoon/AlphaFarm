# AlphaFarm — Veridia

A cozy-with-mystery 2D top-down farming/life sim on the alien planet **Veridia**: violet skies,
twin moons, bioluminescent nights — and soil that is slowly revealed to be listening.

Built with Python + [pygame-ce](https://pyga.me/) (imports as `pygame`). Graphics come from the
sprite sheets in `assets/` — astronaut player, environment tileset (terrain, habitat dome, crop
stages, wild flora), robot NPC portraits, and the outpost bar/shop buildings — all loaded and
sliced by `game/assets.py` (NPC sprites are assigned in `data/npcs.json`, flora sprite boxes in
`data/wild_flora.json`, buildings in `data/map.json`). Crystals, most ripe crops, and effects
remain procedural in `game/render.py`, and everything falls back to procedural shapes if the
sheets are missing. All content and tunables live in JSON under `data/`.

## Run it

```
uv sync
uv run python main.py
```

(Or `pip install pygame-ce` and `python main.py`.)

Run it from a **Windows** shell (PowerShell/cmd). From WSL, use `./run.sh` instead — running
`uv run` directly in WSL tries to rebuild the Windows-format `.venv` as a Linux one and dies
with `Input/output error (os error 5)`, corrupting the venv along the way. `run.sh` gives WSL
its own separate environment (`.venv-wsl`) so the two never collide.

Tests and the headless smoke run:

```
uv run pytest
uv run python tests/smoke.py
```

## Build a standalone executable

Package the game into a single native binary (bundling Python, pygame, and all
`data/`/`assets/`) with [PyInstaller](https://pyinstaller.org):

```
uv run --group build python build.py          # -> dist/alphafarm[.exe]
uv run --group build python build.py --zip     # also makes a release archive
```

The binary is fully self-contained: copy just `dist/alphafarm.exe` (Windows) or
`dist/alphafarm` (Linux) anywhere and run it — no Python required. Save files are written
to a `saves/` folder next to the executable.

**Cross-compiling is not supported.** PyInstaller builds only for the OS it runs on, so
build the Windows `.exe` on Windows and the Linux binary on Linux. To produce both at once,
push a `v*` tag (or run the workflow manually): `.github/workflows/build.yml` builds each on
its own runner and attaches `alphafarm-windows.zip` / `alphafarm-linux.tar.gz` to a GitHub
Release. On Linux, build on the oldest glibc you need to support — the binary runs on that
glibc version and newer.

## Controls

| Key | Action |
| --- | --- |
| WASD / Arrows | Move (4-direction) |
| 1 / 2 / 3 / 4 / 5 | Terra-Hoe / Watering Canister / Harvester / Flora Scanner / Seed Planter |
| Tab | Cycle selected seed (for the planter) |
| Mouse (click) | Select tool from hotbar; click shop rows/tabs |
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
build.py              # PyInstaller build script (standalone executables)
game/
  config.py           # JSON loading + source/frozen path resolution
  assets.py           # sprite sheet slicing (assets/ -> render.SPRITES)
  camera.py           # smooth-follow 2x zoom camera
  audio.py            # SFX + ambient/weather loops (assets/audio)
  particles.py        # particle bursts + floating text
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
assets/               # sprite sheets (player, tileset, NPCs, buildings) + audio/ (synth WAVs)
tools/                # gen_audio.py — regenerates assets/audio deterministically
saves/                # savegame.json (created at runtime, next to the executable when frozen)
tests/                # pytest suite + headless smoke run
.github/workflows/    # build.yml — CI that builds Windows + Linux binaries
```
