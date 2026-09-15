# Diablo 4 Companion — Project Status

_Sidst opdateret: 2026-09-15_

## Current phase

**Phase 0.5 — Project Control System** (dette dokumentationssystem selv).

## Current status

Alle roadmap-faser 1–18 er implementeret og verificeret. Appen har
været igennem en fuld pre-sæson regressions-sweep (26 builds × 8 sider,
karakter-isolation, Compact Mode, frisk-installation) uden fejl. Ingen
kendte bugs i kø. Ingen kode-ændringer i denne fase — kun
dokumentation.

## Last completed phase

Fase 18 — Tempering-data (rigtige Tempering Manual-navne + tier, hentet
fra allerede-hentet Maxroll-data der tidligere blev ignoreret).

## Last commit (før denne dokumentationsfase)

`f7b9d2b` — "Decode real Tempering data into Gear Builder"

Branch: `feature/dashboard-v2` (repoets eneste/default branch — der er
ikke noget `main`, det er normalt for dette repo).

## Tests

- **Testmetode:** headless Qt (`QT_QPA_PLATFORM=offscreen`) med isoleret
  `HOME`/`XDG_CONFIG_HOME`, aldrig mod brugerens rigtige config
  (`~/.config/Diablo4Companion/DesktopCompanion.conf`).
- **Seneste resultat (2026-09-15):** ren sweep, 0 fejl.
  - Alle 26 builds × alle sider (Dashboard, Build Guide, Character,
    Gear Builder, Gems, Paragon, Build Advisor, Settings) — ingen
    exceptions.
  - Cross-system konsistens (Skills/Paragon/Gear/Gems) bekræftet
    konsistent efter toggle, både live og via kode-inspektion (alle
    surfaces læser samme `_compute_build_status`/`_advisor_next_action`
    beregning — ingen parallel logik at divergere).
  - Karakter-isolation for de nye `paragon/<build>/completed_nodes` og
    `gear/<build>/socketed_gems` nøgler bekræftet (ingen data lækker
    mellem karakterer).
  - Compact Mode's Done-knap testet udtømmende for alle actionable
    typer (leveling/skill/paragon_node/gear/gem) — 407 klik, 0 fejl,
    0 no-ops.
  - Frisk installation (tom QSettings) crasher ikke nogen side.
- **Se TEST_STATUS.md** for detaljeret teststrategi og kendte gaps.

## Blockers

Ingen.

## Next phase

Ingen planlagt. Vent på konkret instruktion fra brugeren (se
PROJECT_ROADMAP.md's regel: "Start ikke næste roadmap-fase uden en
konkret instruktion").

## Kort changelog (seneste faser, nyeste øverst)

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
