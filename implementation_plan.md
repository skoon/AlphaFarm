# AlphaFarm — Polish & Depth Implementation Plan

Supersedes the original build plan (Phases 1–3, fully shipped — see task.md history).
Four phases, each independently playable and verified (pytest + headless smoke + screenshots)
before moving on. Save compatibility: any phase that changes persisted state bumps
SAVE_VERSION and migrates old saves rather than breaking them.

---

## Phase A — Game feel (camera, sound, juice)

The game currently renders the whole 40×30 map as a static god view with no audio and
instant, feedback-free actions. This phase makes it *feel* like a game.

### A1. Following camera at 2× zoom
- Render the world to an offscreen surface at native ts=32, sized to half the window
  (640×480 = 20×15 visible tiles), then `pygame.transform.scale` 2× to the window.
  Pixel-perfect, no sprite reslicing needed.
- New `game/camera.py`: position in world pixels, smooth lerp-follow of the player,
  clamped to map bounds. All world-space draws take a camera offset; UI stays native.
- Only draw tiles/entities in the visible rect (+1 tile margin) — cuts per-frame tile
  draws from 1,200 to ~350.
- Debug overlay (F1 resonance numbers, tile highlight) respects the camera transform.
- Config: `window.zoom` (default 2), `camera.follow_speed`.

### A2. Sound
- No new runtime deps: a one-shot `tools/gen_audio.py` synthesizes retro WAVs with the
  std-lib `wave` module (hoe thunk, water squirt, plant pop, harvest chime, credit
  payout, UI blip, storm rumble, ambient hum loop + soft night-pad music loop).
  Generated files are committed to `assets/audio/` so builds and CI never run the tool.
- New `game/audio.py`: load-once registry, `play(name)`, looping ambient channel that
  crossfades day hum ↔ night pad; storm rumble during ion storms.
- Hooks: tool use, harvest, ship payout, gift, dialogue advance, sleep, quest step.
- Config: `audio.master_volume`, `audio.music_volume`, `audio.sfx_volume`, `audio.enabled`.
  Real composed music can drop into `assets/audio/` later under the same names.

### A3. Action juice
- New `game/particles.py`: tiny pooled particle system (soil puff on till, water
  droplets, harvest sparkle, ripe-crop glint, spore motes during spore drifts).
- Tool-swing feedback: brief player lunge toward the target tile + tool flash.
- Floating text: "+35cr" on shipping payout (day start), "+1 Lumen Berry" on harvest.
- Ripe crops get a subtle pulse so they read as harvestable at a glance.

### A4. Time-of-day color + event visuals
- Full-day tint curve (warm dawn 6–8h, neutral midday, violet dusk 18–20h, existing
  night overlay after) — one cached overlay per game-minute bucket, cheap.
- Aurora night: green shimmer bands. Ion storm: screen flicker + occasional white
  lightning flash + wind-blown particles. All keyed off the existing EventSystem.

### A5. Sleep transition + day summary
- Fade to black on sleep; day-summary card before waking: day number, items shipped
  with per-item credits, total earned, tomorrow's forecast, moon phases.
- Data comes from the shipping bin at process time (already computed — just surfaced).

### A6. Visual hotbar
- Bottom-center hotbar: 5 tool slots (keys 1–5) with icons, selected-seed chip with
  count next to the planter slot; Tab still cycles seeds. Replaces the text readout.
- Mouse: click hotbar to select tool; click inventory/shop rows in those panels.
  (Tile targeting stays keyboard/facing-based — mouse-targeted tools are a stretch goal.)

**Verify:** smoke run extended to pan camera + trigger sounds headless (SDL dummy audio);
screenshots at dawn/noon/dusk/night/storm; manual windowed run.

---

## Phase B — NPCs as characters

### B1. Dialogue portraits
- Dialogue box becomes a proper panel: large NPC portrait (existing 256px robot art,
  bbox-cropped) on the left, name + role header, wrapped text, page indicator.
  Multi-page support ("..." → E advances) — needed by heart events below.

### B2. Contextual dialogue
- dialogue.json entries may be plain strings (unchanged) or
  `{"text": "...", "when": {...}}` with condition keys:
  `event` (today's event id), `moon` ("ilo:full", "both:dark"), `location`
  ("near_crystal", "at_farm", "outpost"), `min_quest` (step id), `season_day` etc.
- Selector: matching conditional lines win over generic tier lines; among matches,
  rotate by day as today. Pure extension of the existing tier system.
- Content pass: ~6 conditional lines per NPC (storm, aurora, full-moon, quest-aware,
  location-aware) written into dialogue.json.

### B3. Heart events
- New `data/heart_events.json`: per NPC, thresholds (3♥ and 7♥), multi-page scripted
  scenes (Tinks shows you the wreck; CARE-7 plays the sealed log; Sylla's fern; Hux's
  bore-shaft tape; Juno's reversed recording). Trigger on next talk at threshold;
  each fires once (persisted). Small friendship bonus on completion.

### B4. Favors
- New `game/favors.py` + `data/favors.json` templates: each morning, chance one NPC
  wants N of a crop ("Hux wants 3 Crimson Tubers, 2 days"). Shown on terminal +
  journal; deliver via talk-with-item; rewards credits + friendship. One active favor
  per NPC, capped at 2 concurrent total.

### B5. Friendship perks (mechanical hearts)
- 4♥ Tinks: 15% seed discount. 4♥ Juno: forecast shows 2 days ahead. 6♥ CARE-7:
  auto-waters 4 random planted tiles each morning. 6♥ Sylla: soil report dialogue
  option — names your lowest-resonance field rows. (Hux's perk lands with the mine
  in Phase D: ore discount.) Config thresholds in `npcs` section.

### B6. Life signs
- BFS pathfinding on the walkable grid (40×30 — trivial cost) so NPCs follow paths
  instead of gliding through rocks; recompute when the schedule waypoint changes.
- Night: NPCs at their home waypoint after 21:00 are "indoors" — hidden, not
  interactable. Emote bubbles: ♪ walking, zzz just before going in, ! during storms
  (they hurry home — schedule override). Chat bubbles when two NPCs stand adjacent.

**Verify:** unit tests for the dialogue selector, favor lifecycle, perk effects, BFS
paths; smoke drives a full day of NPC movement; portrait screenshot.

---

## Phase C — Economy arc

### C1. Upgrades shop (Tinks)
- Talking to Tinks opens her shop: tool upgrades + gear, in `data/upgrades.json`:
  - Canister II (waters the 3-tile row you face) / Hoe II (tills 3) — mid price.
  - Pack Expansion: +12 inventory slots.
  - Irrigation Drone: placeable object on tilled soil; waters its 3×3 every morning.
    Sold assembled for credits now; Phase D adds a cheaper mineral-crafted recipe.
- Player upgrade state persisted; drones are world objects (new tile occupant type,
  drawn hovering, persisted, removable with the hoe).

### C2. Processing
- Bio-Kiln (bought from Tinks, placed near habitat): insert crop + wait N days →
  artisan good worth ~2.5× (Lumen Berries → Lumen Preserve, Prism Pod → Focusing
  Lens...). `data/recipes.json`; kiln UI mirrors the shipping-bin flow; goods ship
  via the existing bin.

### C3. Balance pass
- Prices/energy tuned so week 1 ≈ seeds-and-scraping, week 2 ≈ first upgrade,
  week 3–4 ≈ drones + kiln. All knobs already in JSON; add a `tests/test_balance.py`
  sanity test (e.g., every crop's sell > seed cost × 1.4; upgrade paybacks finite).

**Verify:** unit tests for upgrade effects, drone morning-water, kiln timing, save
migration (v1 save loads into v2 fields); smoke buys/places a drone.

---

## Phase D — Second activity + endgame + QoL

### D1. The mine
- Multi-map support: `World` gains a map id; `data/mine.json` is a hand-authored
  ~22×16 cave (entrance at Hux's dig site rocks). Transition tiles swap maps;
  camera/save/systems already per-world after a small refactor.
- Breakable rock tiles (HP, energy per swing) yield minerals (`data/minerals.json`:
  ferrite, lumite, void quartz) for selling, drone/kiln recipes, and restoration.
- Crystal-lit darkness (reuses night lighting), denser toward the back where richer
  ores sit. Hux 4♥ perk: mineral prices +20% when selling through him.
- Fauna from `SciFiCreatures_NES_4x30_alphaBG.png`: skittish critters in the mine and
  on the farm at night; scanner-documentable into a new codex set ("Veridian Fauna",
  completion unlocks the dream_lotus seed purchasable or a fauna-lure decoration).

### D2. Restoration (endgame)
- After the questline: the great crystal accepts offerings — bundles in
  `data/restoration.json` (crop sets, artisan goods, minerals, codex completion).
  Each grants a permanent planet-wide buff (+energy max, +growth rate, +resonance
  recovery, aurora frequency up). Completing all = ending scene + "Veridia Awakened"
  title-screen flourish.

### D3. Quality of life
- Esc pause menu: Resume / Options (volume sliders, keybind view) / Save / Quit.
- Three save slots (`saves/slot_N.json`) + title screen with slot picker and
  Continue. Existing savegame.json migrates to slot 1.
- Optional stretch: controller support via pygame joystick.

**Verify:** map-transition and mining unit tests, fauna scan tests, restoration gating
tests, save-slot roundtrip; full-suite regression + long smoke (5 in-game days).

---

## Sequencing & risk

- Order is A → B → C → D; each phase ships alone. Within phases, items are ordered by
  dependency (A1 camera first — A3/A4 draw through it; B1 portraits before B3 events).
- Biggest risks: camera touching every draw call (A1 — mitigated by centralizing the
  world→screen transform in camera.py), save migration (C/D — versioned migrators +
  tests), multi-map refactor (D1 — keep World instances independent, Game holds a dict).
- Content-only additions (dialogue lines, favors, recipes, bundles) stay in JSON and
  never require code changes — same policy as today.
