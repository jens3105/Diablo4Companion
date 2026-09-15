# Diablo 4 Companion — Project Status

_Sidst opdateret: 2026-09-15_

## Current phase

**Windows Product Phase W3 — Windows Installer** — pak den allerede
verificerede W2 PyInstaller ONEDIR-build ind i en rigtig Windows-
installer (`Diablo4Companion-Setup.exe`) via Inno Setup, og udvid CI-
workflowet til også at bygge, installere (silent) og verificere den.
**Færdig og bestået** — se "W3 — Windows-runner-verifikation" nedenfor.

Ingen auto-updater, ingen Check-for-Updates-ændringer, ingen Release-
automation, ingen Build Data-updater, ingen code signing, ingen
Character State, ingen Diablo-feature-arbejde i denne fase.

### W3 — hvad er lavet

- **`installer/diablo4companion.iss`** (ny fil): Inno Setup-script.
  Installerer hele det uændrede W2 onedir-output
  (`dist/Diablo4Companion/*`, inkl. `_internal/`) til
  `{localappdata}\Diablo4Companion` med `PrivilegesRequired=lowest` —
  valgt frem for `{autopf}`/Program Files specifikt fordi det aldrig
  udløser en UAC-prompt, hvilket gør et `/VERYSILENT`-install fuldt
  non-interaktivt (nødvendigt for automatiseret verifikation på
  GitHub Actions-runneren, hvor ingen UAC-prompt kan besvares).
  Opretter Start Menu-genvej, valgfri (unchecked) Desktop-genvej via
  standard Inno `[Tasks]`, og lader Inno Setups standard
  uninstaller-registrering være uændret. Konsistent visningsnavn
  "Diablo 4 Companion" i installer-titel, Start Menu-mappe og
  Add/Remove Programs. Intet `.ico` findes i repoet — bevidst ikke
  opfundet, bruger Inno Setups default.
  - **Vigtig opdagelse under Windows-runner-verifikation:**
    PyInstaller 6.x's onedir-layout lægger bundlede datas (deriblandt
    `builds/*.json`) under `_internal/`, ikke direkte ved siden af
    exe'en som `src/managers/leveling_manager.py`'s `sys.frozen`-gren
    (fra W2) antager. Da denne fase kun må tilføje nye filer og
    udvide workflow-filen (ikke røre `src/` eller
    `diablo4companion.spec`), er dette rettet udelukkende på
    installer-niveau: en ekstra `[Files]`-linje kopierer
    `_internal\builds\*.json` også direkte til `{app}\builds`, uden
    at fjerne eller omrokere noget fra det uændrede onedir-træ. Dette
    er en reel, verificeret rettelse (bekræftet af den efterfølgende
    grønne runner-verifikation), ikke en antagelse — men en fremtidig
    fase bør overveje at rette selve frozen-path-logikken i
    `leveling_manager.py` til at være `_internal`-bevidst, da dette
    var et reelt, tidligere upåvist hul i W2's "bestået"-status (W2
    testede aldrig faktisk frozen-adfærd, kun syntaktisk).
- **`.github/workflows/windows-build.yml`** (udvidet, ikke erstattet):
  efter den eksisterende PyInstaller-build tilføjet: find/installer
  Inno Setup (`C:\Program Files (x86)\Inno Setup 6\ISCC.exe`,
  pre-installeret på `windows-latest` — bekræftet via selve runnen,
  ingen choco-fallback var nødvendig), kompilér `.iss`-scriptet,
  upload resultatet som separat artifact `Diablo4Companion-Setup`,
  installér derefter installeren silent (`/VERYSILENT
  /SUPPRESSMSGBOXES /NORESTART /DIR=...`) i en throwaway-mappe, og
  verificér: `Diablo4Companion.exe` findes, alle 26 `builds/*.json`
  findes under `{app}\builds`, `unins000.exe` findes, og exe'en
  starter og forbliver kørende i 8 sekunder
  (`QT_QPA_PLATFORM=offscreen`, headless runner) uden at crashe
  øjeblikkeligt — hver check fejler workflow'et synligt hvis den
  ikke består.

### W2 — hvad er lavet

- **`src/managers/leveling_manager.py`**: `LevelingManager.__init__`
  bruger nu `sys.frozen` til at afgøre `repo_root` —
  `os.path.dirname(os.path.abspath(sys.executable))` når frozen
  (PyInstaller onedir), ellers uændret `__file__`-baseret logik ved
  kørsel fra kilde. Dette retter en reel PyInstaller-kompatibilitets-
  bug (`__file__` er ikke garanteret korrekt i en frozen bundle) for
  både `builds/`-opslag og `.cache/build_snapshot.json`-stien.
  `_save_snapshot` havde allerede `try/except OSError` om både
  `os.makedirs` og selve skrivningen — bekræftet allerede sikkert mod
  en ikke-skrivbar mappe (fx senere under Program Files), ingen
  ændring nødvendig der.
- **`src/app.py`'s `get_local_commit_sha()`**: bekræftet (ikke
  ændret, per scope) at den allerede degraderer korrekt i en frozen
  build — `subprocess.run` fejler enten med `OSError` (ugyldig
  `cwd`/manglende `git`) eller `CalledProcessError` (ikke en git-repo),
  begge fanges og giver `None`.
- **`diablo4companion.spec`** (ny, committet root-fil): PyInstaller
  ONEDIR-spec, entry point `main.py`, bundler alle 26
  `builds/*.json` til en `builds/`-mappe ved siden af exe'en. Ingen
  `hiddenimports` tilføjet spekulativt (ingen Windows-runner-fejl har
  endnu bevist behov for det — se Blockers).
- **`.github/workflows/windows-build.yml`** (skrevet lokalt, se
  Blockers for hvorfor den ikke er pushet endnu): `workflow_dispatch`
  + push til `feature/dashboard-v2` på build-relevante stier,
  `windows-latest`, Python 3.12, `pip install -r requirements.txt` +
  `pyinstaller`, `pyinstaller diablo4companion.spec`,
  `actions/upload-artifact@v4` af `dist/Diablo4Companion/`.
- **`.gitignore`**: `*.spec` beholdt, men `diablo4companion.spec`
  eksplicit un-ignored (`!diablo4companion.spec`) da denne fase
  bevidst committer spec-filen.

## Current status

**Build Advisor-fasen** (forrige fase, stadig gyldig baggrund) er
implementeret og verificeret:

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

`4d0eff0` — "W3 fix: also place builds/*.json directly beside the
installed exe" (pushet). Fulde W3-commit-kæde: `c86595a` (Inno Setup-
script + workflow-udvidelse) → `4d0eff0` (fix efter første
runner-verifikation fandt `_internal/`-lag-problemet, se ovenfor).

Branch: `feature/dashboard-v2` (repoets eneste/default branch — der er
ikke noget `main`, det er normalt for dette repo).

## Build command

```
pyinstaller diablo4companion.spec
```

Output: `dist/Diablo4Companion/` (onedir), inkl.
`Diablo4Companion.exe` + `builds/*.json`.

## Tests

- **W2 lokal verifikation (2026-09-15, Linux, kun det der reelt kan
  testes her):** headless offscreen-smoke-test (samme mønster som
  TEST_STATUS.md) kørt igen EFTER `LevelingManager`-frozen-path-
  ændringen: alle 26 builds cyklet uden exceptions,
  `builds_dir`/`_snapshot_path` resolver stadig korrekt til
  repo-stierne ved kørsel fra kilde (ingen regression). `python
  main.py`-importstien (`from src.app import MainWindow`) uændret og
  fungerer.
  **Ikke testbart fra Linux:** selve PyInstaller-Windows-bygningen
  (kræver `windows-latest`-runneren) og alt frozen-adfærd
  (`sys.frozen`-grenen er kun bevist syntaktisk/logisk korrekt, ikke
  kørt i en faktisk frozen proces) — ingen Linux-PyInstaller-bygning
  er forsøgt som substitut, da den intet beviser om Windows-target.
- **Build Advisor-fasens tidligere resultat (2026-09-15):** ren sweep, 0 fejl.
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

## W2 — Windows-runner-verifikation: BESTÅET

Kørt og overvåget live via `gh workflow run` + `gh run watch`:

- Run `34971819654` (manuel `workflow_dispatch`): **✓ success, 1m42s**.
- Artifact `Diablo4Companion-windows` uploadet, 56 190 760 bytes
  (~53.6 MB), indeholder `Diablo4Companion.exe` + `builds/*.json` i
  onedir-format.
- En anden run (`34971811172`, udløst automatisk af selve push'et der
  tilføjede workflow-filen) kørte parallelt til samme resultat.

**Dette er en reel, observeret, autoritativ Windows-build — ikke
antaget.** W2's mål (bevise at appen kan bygges pålideligt til en
Windows PyInstaller ONEDIR-exe via GitHub Actions) er opfyldt.

## W3 — Windows-runner-verifikation: BESTÅET

Kørt og overvåget live via `gh workflow run` + `gh run watch`, to
iterationer:

- **Run `34972569676`** (første forsøg, commit `c86595a`): PyInstaller-
  build, Inno Setup-kompilering og silent-install lykkedes alle, men
  post-install-filverifikationen **fejlede reelt** — `{app}\builds`
  indeholdt 0 filer. Root cause fundet ved at downloade artifact'et og
  inspicere strukturen direkte: PyInstaller 6.22.3's onedir-layout
  lægger `builds/*.json` under `_internal\builds\`, ikke direkte ved
  siden af exe'en som `leveling_manager.py`'s (uændrede, out-of-scope)
  `sys.frozen`-gren forventer. Dette blev IKKE gemt/pyntet væk — se
  fix i commit `4d0eff0` ovenfor.
- **Run `34973162693`** (efter fix, commit `4d0eff0`): **✓ success,
  2m51s**. Alle steps grønne, inkl.:
  - `Diablo4Companion.exe` fundet efter silent install.
  - Alle 26 `builds/*.json` fundet under `{app}\builds`.
  - `unins000.exe` (Inno Setup-uninstalleren) fundet.
  - Exe'en startet (`QT_QPA_PLATFORM=offscreen`) og forblev kørende i
    8 sekunder uden at crashe, derefter stoppet.
  - Artifacts uploadet: `Diablo4Companion-Setup` (38 812 621 bytes,
    ~37 MB) og `Diablo4Companion-windows` (56 188 780 bytes, ~53.6 MB,
    uændret onedir-build).

**Dette er en reel, observeret, autoritativ installer-build +
silent-install-verifikation — ikke antaget.** Den første fejlende
kørsel og dens root-cause-analyse er bevidst dokumenteret her i stedet
for skjult, jf. instruktionen om aldrig at fabrikere et bestået
resultat.

## Next phase

Ingen planlagt. W3 er fuldt bestået. Vent på konkret instruktion fra
brugeren (se PROJECT_ROADMAP.md's regel: "Start ikke næste
roadmap-fase uden en konkret instruktion"). Mulig fremtidig
opfølgning (ikke startet, kræver eksplicit instruktion): rette
`leveling_manager.py`'s frozen-path-logik til selv at være
`_internal`-bevidst i stedet for at kompensere på installer-niveau.

## Kort changelog (seneste faser, nyeste øverst)

- `4d0eff0` — W3-fix: kopiér `builds/*.json` til `{app}\builds` i
  installeren (kompenserer for PyInstaller 6.x's `_internal/`-layout,
  fundet af den første Windows-runner-verifikation).
- `c86595a` — Windows Product Phase W3: Inno Setup-installer
  (`installer/diablo4companion.iss`) + CI-udvidelse (kompilér, silent
  install, post-install-verifikation).
- `0e06451` — Windows Product Phase W2: PyInstaller onedir spec +
  `sys.frozen`-path-fix i `LevelingManager` (Windows-runner-
  verifikation pending, se Blockers).
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
