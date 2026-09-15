# Diablo 4 Companion — Architecture

## Stack

PySide6 + [PySide6-Fluent-Widgets](https://qfluentwidgets.com) (`qfluentwidgets`).
Entry point: `main.py` → `src/app.py`'s `MainWindow` (a `FluentWindow`).
Persistence: `QSettings("Diablo4Companion", "DesktopCompanion")` — the
**only** persistence layer in the app (no database, no separate config
files besides the OS-native Qt settings store).

## Versioning — the single source of truth

`src/version.py`'s `__version__` (currently `"1.0.0"`, semantic
versioning) is the one place a human bumps the app's version — there
is no second hardcoded copy anywhere. The app imports it as normal
Python code (not a bundled data file), so it works identically from
source and once frozen by PyInstaller. `.github/workflows/windows-build.yml`
reads it and passes it into the Inno Setup compile
(`installer/diablo4companion.iss`) via `/DMyAppVersion`, so the
installer's `AppVersion` always matches. See `PROJECT_STATUS.md`'s
Windows Product Phase W4 for the full rationale, including why this
avoids the PyInstaller onedir `_internal/` data-bundling gotcha found
in W3.

## Canonical Build Definition — the single source of truth

Every build lives as one JSON file in `builds/*.json` (26 files, loaded
dynamically by `src/managers/leveling_manager.py`'s `LevelingManager` —
adding a build means adding a JSON file, no code changes needed). Full
schema is documented in `LevelingManager`'s own class docstring — read
that before touching build data. Two layers per build:

1. **Prose-derived fields** (`milestones`, `strategy`, `paragon`
   (legacy board-name/glyph-list, mostly superseded), `gear` (legacy
   prose key_items/key_aspects/stat_priority/skill_bar)) — hand-scraped
   from Maxroll's guide text, present for all 26 builds.
2. **`verified_build`** — real, decoded Maxroll Planner data (see
   "Data pipeline" below). Present for 25/26 builds; **Heartseeker
   Rogue has none** (its guide uses an older embed format with no
   planner profile call) and correctly falls back to the prose layer
   everywhere in the UI rather than showing fabricated verified data.

**Every feature that shows "is this build complete" data reads from
`verified_build` when present, and only falls back to the prose layer
for Heartseeker Rogue.** There is no second/competing build data model
anywhere in the app — this is enforced by design across every phase
built so far.

## Data pipeline (offline, not run by the app itself)

`scripts/maxroll_data_decoder.py` — a standalone script, never imported
by the running app (confirmed: the app only ever reads the small
`verified_build` JSON this script produces, it does no network calls
itself). Two real, public, unauthenticated Maxroll endpoints:

1. `https://planners.maxroll.gg/profiles/load/d4/<profile_id>` — one
   build guide's actual saved planner profile (skill tree, paragon
   boards, equipped items — the guide author's real build).
2. `https://assets-ng.maxroll.gg/d4-tools/game/data.min.json` (~12MB) —
   Maxroll's full game-data dump (skill names, paragon board/node
   layouts, item definitions, affixes, tempering recipes, gem/rune
   definitions). Cached at `.cache/data.min.json` (gitignored).

Run manually: `python scripts/maxroll_data_decoder.py <profile_id>
--profile-name Endgame --build-file builds/<name>.json`.

**Recurring pattern in this project**: the raw fetched JSON has
repeatedly contained more real data than the decoder originally read
(Paragon node/rotation/position data, Gem/Rune socket contents,
Tempering recipe data were all sitting in already-cached raw JSON for
a while before being decoded). When extending verified data, re-inspect
the raw cached JSON for unread fields before concluding something is
unavailable.

**Confirmed genuinely unavailable** (checked exhaustively, not
guessed): plain rolled Affixes/Stats (`explicits` field) have no
player-facing display-text anywhere in `data.min.json` (only internal
engine attribute names/formulas); `implicits` resolve the same way but
contain unreliable "(PH)" placeholder text for several entries;
Masterworking has no corresponding field on any equipped item instance
at all. All three correctly show `DATA UNAVAILABLE` — do not re-attempt
without a genuinely new data source.

## Feature areas

### Skills / Leveling (`src/leveling_card.py`, part of "Build Guide" page)

Class → build selector, then a 3-tab `SegmentedWidget` (Leveling /
Skills / Paragon — Gear was moved out to its own top-level pages).
Leveling and Skills both track completion via
`characters/<id>/skills/<build>/completed_levels` (a shared set,
`_load_completed_levels`/`_save_completed_levels` in `src/app.py`) —
Skills reads `verified_build.skill_allocation` when present (keyed by
skill name), else falls back to the same milestone-position keys
Leveling always uses.

### Paragon (`src/paragon_interface.py`, own top-level nav page)

Overview (per-board completion %, reusing `_compute_build_status`) and
a per-board detail view: a grid visualization placing each expected
node at its real `(index % board_width, index // board_width)`
position (from `verified_build.paragon_boards[].nodes`), rarity-colored,
with the glyph socket (`glyph_socket_index`) and start node
(`start_node_index`) marked. **No node-adjacency/path data exists
anywhere in Maxroll's data** — grid position is real, connectivity
between nodes is not, so no route/line is ever drawn between nodes.
Tracking is node-granular:
`characters/<id>/paragon/<build>/completed_nodes` (a toggle set,
`_load_completed_paragon_nodes`/`_save_completed_paragon_nodes`),
keyed `"<board_slug>:<node_index>"`. Board-complete status is *derived*
(all expected nodes toggled) for the 25 verified builds; the older
`characters/<id>/paragon/<build>/completed_boards` boolean survives
only as Heartseeker Rogue's fallback (no verified data at all).

### Gear Builder (`src/gear_builder_interface.py`, own top-level nav page)

Detail-first page, separate from Character's silhouette view — one
card per equipped slot (dynamic weapon/offhand count per class) showing
item name/slot/rarity/aspect from `verified_build.gear[]`, plus
Sockets/Gems (real summary when data exists, see Gems below) and
Tempering (real summary when data exists, see Tempering below) rows.
Affixes/Stats and Masterworking rows are always `DATA UNAVAILABLE`
(confirmed unavailable at the source, see "Data pipeline" above).
Ownership tracking: `characters/<id>/gear/<build>/owned_items` (a
toggle set, `_load_owned_items`/`_save_owned_items`) — **the same key
Character's `GearPlannerWidget` (`src/gear_planner.py`) reads/writes**,
so both pages always agree.

### Character (`src/character_interface.py`)

Hosts `src/gear_planner.py`'s `GearPlannerWidget` — a drawn silhouette
with clickable slot chips, rarity-colored, click → detail dialog with a
"Have it" toggle. Predates and is architecturally distinct from Gear
Builder, but shares the exact same `owned_items` tracking key.

### Gems (`src/gems_interface.py`, own top-level nav page)

Per-socket detail: for each equipped item with real socket data
(`verified_build.gear[].sockets`, resolved gem/rune name + computed
effect text), a "Have it" toggle
(`characters/<id>/gear/<build>/socketed_gems`, keyed
`"<slot>:<socket_index>"`). No "current/actually-socketed" detection
exists (same architectural limitation as Gear's "Have it" vs. no real
"incorrect item" detection) — a "⚠ Wrong gem" status is scaffolded in
the code but can never actually fire, documented as such, mirroring
`gear_planner.py`'s pre-existing `SlotStatus.INCORRECT` precedent.

### Tempering

Not a separate page — a row inside each Gear Builder slot card, sourced
from `verified_build.gear[].tempering` (real Tempering Manual name +
category + tier, resolved via `data.min.json`'s `temperingRecipes`).
No separate tracking (nothing for the player to toggle — it's just
informational, same as Aspect).

### Build Advisor (`src/build_advisor_interface.py`, own top-level nav page)

The single unified "what's next" surface. `MainWindow._advisor_pending_actions`
concatenates, in priority order: `_pending_leveling_actions` →
`_pending_skill_actions` → `_pending_paragon_actions` (node-level) →
`_pending_gear_actions` → `_pending_gem_actions`. `_advisor_next_action`
picks the first pending item. **This is the single source of truth**
consumed identically by: Dashboard's Current Build card
(`src/current_build_card.py`), the Build Advisor page itself, and
Compact Mode (`src/compact_window.py`) — none of these compute their
own status independently, so they can never disagree.

### Dashboard (`src/dashboard.py`)

World Boss / Helltide / Legion / Season countdown cards (real API when
`helltides.com` is reachable, else `src/local_schedule.py`'s locally-
computed fallback — `helltides.com`'s Cloudflare bot-challenge blocks
the live API from this network and likely will on the user's gaming PC
too; the live path is still always tried first) plus the Current Build
card (build status rows + unified Next Action, clickable to jump to the
relevant page/tab).

## UI / Navigation structure

`MainWindow.__init__` (`src/app.py`) wires the `FluentWindow` nav via
`addSubInterface`, in this order:

1. Dashboard
2. Build Guide (Skills/Leveling/Paragon tabs — legacy 3-tab widget)
3. Character (silhouette equipment view)
4. Gear Builder (detail-first equipment view)
5. Gems
6. Paragon (Overview + board detail)
7. Build Advisor
8. Settings (pinned to `NavigationItemPosition.BOTTOM`)

All character/build/level state lives on `MainWindow` and is pushed to
every page via the same refresh call sites — no page maintains its own
independent build/character selector (Character/Gear Builder/Gems/
Paragon/Build Advisor all show a header that *follows* the Build
Guide's active selection, never a duplicate one).

## Multi-character support

All per-build tracking keys are namespaced
`characters/<char_id>/<category>/<build>/<key>` via
`MainWindow._char_prefix()`. Confirmed (2026-09-15) that every tracking
key introduced in the Paragon/Gems phases correctly uses this prefix —
no cross-character data leakage.
