# Diablo 4 Companion — Test Status

## Teststrategi

Der er **54 automatiserede tests** i `tests/` (pytest eller unittest,
begge virker). Kør dem fra repo-roden:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python3 -m pytest tests/ -q
```

| Fil | Hvad | Antal |
|---|---|---|
| `tests/test_unique_drop_data.py` | den lokale Unique↔Boss-mapping er konsistent | 13 |
| `tests/test_items_api.py` | Data API'et, gennem appens eget datalag | 33 |
| `tests/test_ui_smoke.py` | Unique Drop Locations-siden bygger og viser indhold | 8 |

Adressen på Data API'et er **konfiguration, ikke kode** (repoet er
offentligt, serveren står på LAN'et). Sæt den før kørsel:

```bash
D4COMPANION_API_URL=http://<server>:<port>/api/v1 \
  QT_QPA_PLATFORM=offscreen .venv/bin/python3 -m pytest tests/ -q
```

— eller skriv samme linje i `api_url.txt` i repo-roden (gitignoreret).

> **De to API-afhængige testfiler kan ikke køre i GitHub Actions** —
> runneren kan ikke nå hjemmenettet. De er bevidst ikke lagt ind i
> `windows-build.yml`; ville de være det, ville hver eneste build fejle
> på noget der er helt i orden. Uden konfiguration **springer de over**
> i stedet for at fejle. De køres på monitoring-serveren før push.

Testene mocker med vilje ikke API'et: spørgsmålet de findes for at
besvare er, om appen faktisk læser det verificerede datasæt fra
produktionsserveren, og det kan en mock ikke svare på.

Derudover testes fortsat manuelt:

1. **Headless Qt-røgtest** — den primære metode brugt gennem hele
   projektets udvikling. Kører den rigtige app-kode
   (`from src.app import MainWindow`) under `QT_QPA_PLATFORM=offscreen`,
   altid med en isoleret midlertidig `HOME`/`XDG_CONFIG_HOME` (aldrig
   mod brugerens rigtige gemte fremgang). Bruges til at cykle gennem
   builds/sider og bekræfte ingen exceptions, samt til at verificere
   specifikke beregninger (fx node-tællinger) numerisk mod den
   underliggende JSON, ikke kun visuelt.
2. **Manuel live-test** — brugeren selv, på sin rigtige Windows
   gaming-PC, den eneste måde at bekræfte reel spilflow og visuelt
   udseende (tema, layout, klik) fuldt ud.

## Test-kommandoer (til fremtidig brug)

Kør fra repo-roden med `.venv` til stede:

```bash
mkdir -p /tmp/d4c_test_home
QT_QPA_PLATFORM=offscreen HOME=/tmp/d4c_test_home XDG_CONFIG_HOME=/tmp/d4c_test_home/.config \
  .venv/bin/python3 - <<'EOF'
import sys
sys.path.insert(0, ".")
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
from src.app import MainWindow

w = MainWindow()
for build in w.leveling_manager.list_builds_for_class(...):  # eller en fast liste
    w.on_class_changed(w.leveling_manager.get_class_for_build(build))
    w.on_build_changed(build)
    # ... tjek specifik side/metode her
EOF
rm -rf /tmp/d4c_test_home
```

**Kendt faldgrube:** kald ALDRIG `MainWindow.on_add_character()` direkte
i en headless test — den åbner en blokerende `QInputDialog.getText(...)`
der hænger for evigt under `offscreen`-platformen uden nogen måde at
lukke den på. Reproducér i stedet dens settings-side-effekter direkte
(se `PROJECT_STATUS.md`-historikken / git-log for det bekræftede
mønster, sidst brugt i den afsluttende regressions-sweep).

Giv altid Bash-testkommandoer et eksplicit `timeout`, så et lignende
hang ikke blokerer hele sessionen.

## Seneste kendte testresultat (2026-09-15)

Fuld pre-sæson regressions-sweep, **ren, 0 fejl**:

- 26 builds × 8 sider (Dashboard, Build Guide × 3 faner, Character,
  Gear Builder, Gems, Paragon Overview + board-detalje, Build Advisor,
  Settings) — ingen exceptions.
- Cross-system konsistens (Skills/Paragon/Gear/Gems) efter toggle på 4
  builds på tværs af 4 klasser — bekræftet konsistent, både ved live
  toggling og via kode-inspektion (fælles beregningssti, se
  ARCHITECTURE.md's Build Advisor-afsnit).
- Karakter-isolation for `paragon/<build>/completed_nodes` og
  `gear/<build>/socketed_gems` — bekræftet ingen lækage mellem to
  karakterer.
- Compact Mode Done-knap — 407 klik på tværs af 2 builds, alle
  action-typer (leveling/skill/paragon_node/gear/gem) undtagen den nu
  ikke-nåelige legacy `"paragon"` (board-niveau) type.
- Frisk installation (helt tom QSettings) — ingen crashes på nogen
  side.

## Kendte test-gaps

- **Legacy board-niveau `"paragon"` Compact Mode-handling
  (`on_mark_board_done`)** kan ikke øves med nogen af de 26 nuværende
  builds' data (Heartseeker Rogue, det eneste build uden
  node-granulær data, har også 0 legacy paragon-boards) — koden er
  identisk implementeret til den verificerede `paragon_node`-sti, så
  sandsynligvis fin, men reelt uverificerbar lige nu.
- **Windows-specifik adfærd** (rigtig `.exe`, faktisk Windows
  filsystem-stier, rigtig skærmopløsning/DPI) kan slet ikke testes fra
  dette Linux-udviklingsmiljø — kræver brugerens egen manuelle test.
- **`helltides.com`'s live API** er blokeret af Cloudflare fra dette
  netværk (og forventes sandsynligvis også blokeret fra brugerens); den
  lokale fallback (`src/local_schedule.py`) er testet, men den ægte
  live-API-sti er reelt kun testbar hvis/når Cloudflare-blokeringen
  nogensinde ophører.
- **Ingen automatiseret regressions-suite** — hver test er en
  engangs-håndskrevet headless-kørsel. Hvis projektet vokser
  yderligere, kan det være værd at samle de gentagne
  smoke-test-mønstre i en fast `scripts/`-testfil, men det er ikke
  gjort endnu (ikke bedt om, ville være scope creep i denne fase).
