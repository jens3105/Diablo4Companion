# Diablo 4 Companion — Project Status

_Sidst opdateret: 2026-09-15_

## Current phase

**Build Advisor** — Build Advisor gjort handlingsorienteret ved at
konsumere Build Validation som eneste kilde til sandhed. Kode-fasen er
færdig.

## Current status

Build Advisor-fasen er implementeret og verificeret:

- `_build_validation` er nu det ENESTE sted der udregner "hvad mangler"
  — udvidet med en fuld `actions: [{kind, text, key}, ...]`-liste pr.
  kategori (tidligere kun flad visningstekst) samt en "Leveling"-
  kategori (stadig ekskluderet fra `overall_percent`, som før).
- `_advisor_pending_actions`, `_advisor_missing_summary`,
  `_paragon_dashboard_summary` og `_navigate_to_next_action` læser nu
  alle fra `_build_validation` i stedet for at kalde de rå
  `_pending_*_actions`-hjælpere direkte (parallelt) — der er nu præcis
  ét sted der afgør færdiggørelse/differences.
- Build Advisor-siden viser nu en kort "hvorfor er dette næste"-linje
  under NEXT ACTION (`_ADVISOR_REASONS`), som genbruger den allerede
  dokumenterede prioritetsbegrundelse ordret — ikke ny tekst.
- "different"-status findes stadig i datastrukturen men er bevidst
  uopnåelig (ingen rigtig karakter-import findes) — samme præcedens som
  `gear_planner.SlotStatus.INCORRECT` og Gems' "Wrong gem".

**Note om denne fase:** den oprindelige agent, der byggede dette, blev
afbrudt midt i sin egen test-kørsel (en baggrundsproces der ikke nåede
at rapportere tilbage). Jeg (den koordinerende session) gennemgik
diff'en personligt, dræbte den efterladte test-proces, og kørte selv en
uafhængig verifikation (alle 26 builds, samt Zeal Paladin og
Heartseeker Rogue i detalje) før commit — arbejdet var korrekt og
komplet, blot ucommittet.

Ingen kendte bugs i kø.

## Last completed phase

Build Advisor (denne fase).

## Last commit

`6716346` — "Make Build Advisor consume Build Validation as its single
source of truth"

Branch: `feature/dashboard-v2` (repoets eneste/default branch — der er
ikke noget `main`, det er normalt for dette repo).

## Tests

- **Testmetode:** headless Qt (`QT_QPA_PLATFORM=offscreen`) med isoleret
  `HOME`/`XDG_CONFIG_HOME`, aldrig mod brugerens rigtige config
  (`~/.config/Diablo4Companion/DesktopCompanion.conf`).
- **Seneste resultat (2026-09-15):** ren sweep, 0 fejl.
  - Alle 26 builds: `_build_validation`, `_advisor_pending_actions`,
    `_advisor_next_action`, `_advisor_missing_summary` kørt uden
    exceptions efter refaktoreringen.
  - Zeal Paladin og Heartseeker Rogue tjekket i detalje: korrekt Next
    Action + begrundelse, korrekt status/procent pr. kategori.
    Heartseeker Rogue viser stadig "unavailable" for Paragon/Gems/
    Tempering og bruger stadig sit eksisterende prosa-lag-fallback for
    Skills/Gear — uændret adfærd, kun intern omlægning.
  - Bekræftet ingen resterende kald til de rå `_pending_*_actions`-
    hjælpere uden for `_build_validation` selv (grep-tjek).
  - (Tidligere resultat, stadig gyldigt): alle 26 builds × 8 sider,
    karakter-isolation, Compact Mode (407 klik), frisk-installation —
    ren, 0 fejl.
- **Se TEST_STATUS.md** for detaljeret teststrategi og kendte gaps.

## Blockers

Ingen.

## Next phase

Ingen planlagt. Vent på konkret instruktion fra brugeren (se
PROJECT_ROADMAP.md's regel: "Start ikke næste roadmap-fase uden en
konkret instruktion").

## Kort changelog (seneste faser, nyeste øverst)

- `6716346` — Build Advisor: konsumerer nu `_build_validation` som
  eneste kilde til sandhed + "hvorfor er dette næste"-begrundelse.
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
