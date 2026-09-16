# Diablo 4 Companion — Project Roadmap

## Formål

En PySide6-baseret Windows desktop-companion til Diablo 4, brugt som et
andet-skærm-referenceværktøj mens man spiller (ofte på PS5). Appen læser
ikke spil-state — det er et rent reference-/tracking-værktøj bygget på
ægte, verificerede build-data fra Maxroll (aldrig gættet), med en
Build Advisor der fortæller spilleren præcis hvad næste konkrete skridt
er på tværs af Leveling, Skills, Paragon, Gear og Gems.

## Roadmap-faser og status

| Fase | Beskrivelse | Status |
|---|---|---|
| 1 | UI-framework skift til PySide6-Fluent-Widgets | ✅ Done |
| 2 | Fuldt Maxroll build-katalog (26 builds, 8 klasser) | ✅ Done |
| 3 | Leveling Assistant (milestone-checkliste) | ✅ Done |
| 4 | Paragon Assistant (oprindelig board-niveau) | ✅ Done (senere afløst af Fase 15) |
| 5 | Gear & Powers (oprindelig toggle-checkliste) | ✅ Done (senere afløst af Fase 16) |
| 6 | Build Validation (Build Status 🟢/🟡/🔴) | ✅ Done |
| 7 | Dashboard 2.0 (Current Build card) | ✅ Done |
| 8 | Character/Build State (multi-karakter) | ✅ Done |
| 9 | Companion Mode (Compact-vindue) | ✅ Done |
| 10 | Final QA/polish (milestone-keying, styling) | ✅ Done |
| 11 | Theme-system (dark/light + sæson-presets) | ✅ Done |
| 12 | Verificeret Skills/Paragon/Gear-data (Maxroll planner-pipeline) | ✅ Done |
| 13 | Visuel Character Equipment Planner (silhuet) | ✅ Done |
| 14 | Full user-flow QA-pass | ✅ Done |
| 15 | **Complete Paragon System** (node-niveau tracking, board-visualisering) | ✅ Done |
| 16 | **Complete Gear Builder** (dedikeret detalje-side pr. slot) | ✅ Done |
| 17 | **Complete Gems System** (per-socket gem/rune-tracking) | ✅ Done |
| 18 | Tempering-data (rigtige Manual-navne + tiers) | ✅ Done |
| 0.5 | **Project Control System** (denne fase — roadmap/status/arkitektur-dokumentation) | ✅ Done |

**Bevidst on hold** (ikke startet, vent på eksplicit instruktion):
- Notifications/lyd (`QSystemTrayIcon`/`QSoundEffect`) — sat på pause af brugeren, ikke gættet i mellemtiden.

**Permanent uden for scope** (bekræftet, ikke midlertidigt):
- Rigtig karakter-import (ingen datakilde findes — appen kan ikke vide hvad spilleren faktisk har udstyret/socketet).
- Windows `.exe`/installer-pakning (kræver en Windows-maskine, kan ikke bygges/testes fra dette Linux dev-miljø).
- Numerisk decoding af almindelige rullede affixes/stats og Masterworking — bekræftet at ingen visningstekst-kilde findes i Maxrolls data (se ARCHITECTURE.md).

**Næste fase:** Ingen planlagt. Vent på en konkret ny instruktion fra brugeren.

## Regler for fasearbejde (permanent — gælder al fremtidig udvikling på dette projekt)

- Arbejd kun på den aktuelle fase.
- Start altid med INSPECT.
- Brug eksisterende arkitektur og data.
- Ingen broad repository scans uden konkret grund.
- Ingen duplicate data models.
- Ingen unødvendige refactors.
- Ingen feature creep.
- Ingen re-research af allerede verificerede Diablo-data.
- Gæt aldrig Diablo-data.
- Brug DATA UNAVAILABLE hvis data ikke kan verificeres.
- Agents må kun bruges hvis de giver reel paralleliseringsværdi.
- Ingen overlappende agentarbejde.
- Hold agent reports korte.
- Test efter implementation.
- FIX ONLY IF NEEDED.
- Stop når fasen er færdig.
- Start ikke næste roadmap-fase uden en konkret instruktion.

Claude Code må **ikke** selv ændre roadmapets rækkefølge eller opfinde
nye projektfaser. Nye faser tilføjes kun til dette dokument, når
brugeren giver dem.

## BAN-SAFETY RULE — DIABLO IV

Diablo4Companion must NEVER interact with the Diablo IV game client itself.

The application must NEVER:

- read Diablo IV game files
- inspect Diablo IV game files
- read Diablo IV process memory
- hook into the Diablo IV process
- inject code into Diablo IV
- modify Diablo IV files
- inspect or manipulate game packets
- intercept or modify Diablo IV network traffic
- automate gameplay
- simulate player input for gameplay
- use any technique intended to bypass Blizzard protections
- use any technique that could reasonably create account-ban risk

All Diablo 4 information used by Diablo4Companion must originate from external/public data sources, legitimate APIs, websites, or explicitly provided user/community reports.

Game-event data such as World Boss, Legion and Helltide must therefore NEVER be obtained by inspecting or interacting with the Diablo IV client.

When evaluating a possible technical solution, BAN-SAFETY takes priority over convenience.

If a proposed solution requires interaction with the Diablo IV client, its files, memory, packets or process, REJECT THE APPROACH.

This rule is permanent and applies to all future features, research, agents and implementation work.

**IMPORTANT:**
The project is a standalone companion application. It must remain completely separate from the Diablo IV game client.
