# Diablo 4 Companion — Project Status

_Sidst opdateret: 2026-09-15_

## Current phase

**Build Validation** — samlet valideringslag (Skills/Paragon/Gear/
Gems/Tempering) + Tempering-toggle-tracking (den ene dimension der
manglede). Kode-fasen er færdig.

## Current status

Build Validation-fasen er implementeret og verificeret:

- Tempering har nu rigtig spiller-tracking (`gear/<build>/
  tempered_items`, samme mønster som `socketed_gems`) med en "Have it"
  `SwitchButton` pr. tempered affix i Gear Builder — tidligere var
  Tempering kun read-only tekst.
- `_compute_build_status` viser nu 6 rækker (Skills, Leveling, Paragon,
  Gear, Gems, Tempering) i stedet for 4; procent-udregningen er
  faktoriseret ud i en delt `_category_percents`-hjælper.
- Ny `_build_validation(build_name)` samler eksisterende procent- og
  differences-data (fra `_category_percents`/`_pending_*_actions`) i én
  struktur (`overall_percent` + pr.-kategori `percent`/`status`/
  `differences`) til Build Advisor eller fremtidige forbrugere — ingen
  ny/parallel fuldført-logik.
- `_advisor_pending_actions`/`_advisor_missing_summary` inkluderer nu
  Tempering (lavest prioritet, tilføjet sidst).
- "different"-status findes i datastrukturen men er bevidst
  uopnåelig (ingen rigtig karakter-import findes) — samme præcedens som
  `gear_planner.SlotStatus.INCORRECT` og Gems' "Wrong gem".

Ingen kendte bugs i kø.

## Last completed phase

Build Validation (denne fase).

## Last commit

`c0dc918` — "Add Build Validation layer: Tempering tracking +
Gems/Tempering status rows + _build_validation aggregation"

Branch: `feature/dashboard-v2` (repoets eneste/default branch — der er
ikke noget `main`, det er normalt for dette repo).

## Tests

- **Testmetode:** headless Qt (`QT_QPA_PLATFORM=offscreen`) med isoleret
  `HOME`/`XDG_CONFIG_HOME`, aldrig mod brugerens rigtige config
  (`~/.config/Diablo4Companion/DesktopCompanion.conf`).
- **Seneste resultat (2026-09-15):** ren sweep, 0 fejl.
  - Alle 26 builds: `_compute_build_status` (6 rækker) og
    `_build_validation` (5 kategorier) kørt uden exceptions.
  - Konsistens bekræftet: `_compute_build_status`'s Gems/Tempering-
    procenttekst matcher `_build_validation`'s rå procent 1:1, før og
    efter live gem-/tempering-toggles, på 6 forskellige builds.
  - Heartseeker Rogue (ingen `verified_build`): Paragon/Gems/Tempering
    korrekt "unavailable"; Skills/Gear beholder deres eksisterende,
    bevidste prosa-lag-fallback (samme som før denne fase — ikke en
    regression).
  - Build med items uden tempering-data (f.eks. Talismans/Ring 1 på
    flere warlock/necro/paladin/sorc-builds) bekræftet: intet toggle
    vises, "DATA UNAVAILABLE" forbliver.
  - Alle nav-sider (Dashboard, Build Guide, Character, Gear Builder,
    Gems, Paragon, Build Advisor, Settings) skifter uden crash.
  - Build Advisor-siden viser nu Tempering i "What's missing".
- **Se TEST_STATUS.md** for detaljeret teststrategi og kendte gaps.

## Blockers

Ingen.

## Next phase

Ingen planlagt. Vent på konkret instruktion fra brugeren (se
PROJECT_ROADMAP.md's regel: "Start ikke næste roadmap-fase uden en
konkret instruktion").

## Kort changelog (seneste faser, nyeste øverst)

- `c0dc918` — Build Validation: Tempering-toggle-tracking + Gems/
  Tempering Build Status-rækker + `_build_validation`-aggregeringslag.
- `f7b9d2b` — Tempering: rigtige Manual-navne + tier i Gear Builder.
- `945fb2c` — Gem-effekttekst renderes med rigtige udregnede tal (ikke
  rå Maxroll-skabelon-syntaks).
- `9c55b4a` — Gems System: per-socket gem/rune-tracking, ny "Gems"-side.
- `c13f26d` — Gear Builder: ny dedikeret detalje-side pr. udstyrsslot.
- `a193304` — Paragon: node-niveau tracking, Build Advisor + Dashboard-integration.
- `a1c7a1d` — Paragon: ny Overview + board-detalje-side med grid-visualisering.
- `78658a3` — Paragon-decoder udvidet med grid/socket/start-node-data.
- `79acde1` — Fix: Leveling manglede i den samlede Next Action.
- `c54081e` — Fix: Level-loft 70 → 100 (rigtigt spil-loft).
