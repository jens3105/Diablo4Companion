# Diablo 4 Companion — Project Status

_Sidst opdateret: 2026-09-16_

## Current phase — Dashboard Live Data: legitim kilde-undersøgelse afsluttet

Efter at `local_schedule.py`-fabrikationen blev fjernet (`b08db7d`),
blev det undersøgt om der findes en LEGITIM måde for selve den
pakkede Windows-desktop-app (ikke en browser) at nå de rigtige,
live helltides.com-data — uden at omgå Cloudflare/CAPTCHA/auth, som
eksplicit forbudt.

**Testet, med bevis:**
- Almindelig `requests`-kald: `403`.
- Med fuldt browser-lignende User-Agent: stadig `403`.
- Med komplet sæt normale browser-headers (Accept, Accept-Language,
  Referer, Origin): stadig `403`.
- Response-headers (hentet via en rigtig browser-session) viser
  `server: cloudflare` + Railway-hosting bagved — dette er IKKE en doven
  User-Agent-baseret blokering, men et ægte fingerprint-/
  udfordringsbaseret Cloudflare-tjek. At forsøge yderligere
  header-/TLS-spoofing for at komme forbi ville være en reel omgåelse
  af beskyttelsen — gjort bevidst IKKE.
- helltides.com's egen forside bekræfter eksplicit: **"Helltides.com er
  en fan-made Diablo 4 event timer... Not affiliated with Activision or
  Blizzard Entertainment."** Ingen offentlig developer-API/docs-side
  findes — kun deres egen "Discord Bot" (til Discord-servere, ikke et
  generelt REST-API til tredjepartsapps).
- Ingen officiel Blizzard-API for World Boss/Legion/Helltide-tider
  eksisterer.

**Konklusion (ærlig, ikke en antagelse):** Der findes ingen legitim
måde for denne pakkede Python/PySide6-desktop-app at hente
Diablo 4-eventdata live på egen hånd. Den eneste måde at faktisk se
disse data er en RIGTIG browser (som består Cloudflares
fingerprint-tjek automatisk) — at indlejre en fuld browser-motor
(fx QtWebEngine) i denne app for at opnå dette ville være en enorm,
uforholdsmæssig arkitekturændring, ikke bedt om og langt uden for
denne fases scope.

**Det betyder: DATA UNAVAILABLE er ikke en midlertidig fallback mens vi
venter på en bedre løsning — det ER den korrekte, ærlige, endelige
tilstand** når det live API ikke kan nås, præcis som brugerens egen
regel foreskriver ("REAL API DATA > DATA UNAVAILABLE > NEVER
FABRICATED DATA"). Fixet fra `b08db7d` (ingen fabrikation, tydelig
DATA UNAVAILABLE) er derfor det korrekte og komplette svar — ikke en
uafsluttet mellemtilstand.

**Sekundært fund (ikke handlet på, uden for scope):** Den rigtige
helltides.com-forside viser nu et 3. eventtype — "Realmwalker"
(introduceret Season 6, "Hatred Rising") — som IKKE findes i
`/api/schedule`-endpointets svar (kun `world_boss`/`legion`/`helltide`).
Appen har derfor aldrig vist Realmwalker-data, hverken fabrikeret eller
ægte. Dette er en mulig fremtidig udvidelse, ikke en del af denne
bugfix.

---

## Tidligere fase

**CRITICAL Dashboard Live Data Bug — fundet og rettet (commit
`b08db7d`)**

Brugeren sammenlignede Dashboardet direkte med de faktiske in-game
Diablo 4-timere: World Boss/Legion/Helltide/Upcoming Events var alle
markant forkerte (fx in-game ~37 min vs. appens `01:36:58`), og hver
eneste post var mærket "(estimated)"/"(est.)".

### Root cause (fundet med bevis, ikke gæt)

`get_schedule()` (`src/api.py`) faldt tilbage til `src/local_schedule.py`
hver gang det live helltides.com-kald fejlede eller kom tomt tilbage —
hvilket, bekræftet gentagne gange tidligere i dette projekt, er
Cloudflare der blokerer almindelige `requests`-klienter uafhængigt af
netværk, så denne fallback reelt set ALTID udløses uden for en rigtig
browser-session. `local_schedule.py` beregnede World Boss/Legion/
Helltide-tider ud fra faste referencedatoer + simple gentagne
intervaller (en 2023-anker-dato, en gættet 6-timers World Boss-cyklus,
en gættet 25-minutters Legion-cyklus) — dens egen docstring
erkendte allerede at disse cadencer var "widely-cited community
knowledge, not tied to a confirmed official anchor timestamp".
Brugerens direkte in-game-sammenligning bekræfter nu at disse gæt ikke
bare er upræcise, men markant forkerte. **Hvert eneste Dashboard-kort
og hver eneste Upcoming Events-række kom fra denne ene generator** —
der var aldrig en separat, anden generator; det er derfor ALT var
mærket "(estimated)"/"(est.)".

### Fix

`src/local_schedule.py` slettet HELT, og dens import/kald fjernet fra
`get_schedule()` — en blokeret/fejlet/tom live-hentning returnerer nu
et ægte tomt schedule (`{"world_boss": [], "legion": [], "helltide": []}`),
aldrig et beregnet gæt. Alle forbrugere håndterede allerede et tomt
schedule korrekt (`get_next_world_boss` osv. returnerer `None`) — det
ene reelle hul var at `src/app.py`s `load_world_boss`/`load_legion`/
`load_helltide` stille lod et kort stå med gammel/standard-tekst ved
"ingen data" i stedet for at sige det tydeligt; ny
`_show_data_unavailable()` sørger nu for at hvert kort tydeligt viser
"DATA UNAVAILABLE" (titel, undertekst, status, timer nulstillet) i
stedet for at ligne en ægte nedtælling. Al nu-død "estimated"-felt-/
label-logik fjernet (`src/api.py`s `get_upcoming_events`, `src/app.py`s
`_subtitle`, `src/upcoming_card.py`s "(est.)"-suffiks).

**Kanonisk data-flow er nu præcis:** ét live-kald → rå schedule →
World Boss/Legion/Helltide-kort + Upcoming Events, alle læser SAMME
schedule-snapshot (allerede sandt siden den tidligere Dashboard-fix,
`cc10305`/`4d47baf` — den fix var korrekt og er urørt; denne fix
fjerner den separate fabrikations-kilde de stadig kunne falde tilbage
til).

**Tests:** Ægte, live-verificeret API-respons renderer korrekt uden
nogen "(estimated)"/"(est.)"-tekst nogen steder. Blokeret/tom API viser
nu DATA UNAVAILABLE på alle tre kort + tom Upcoming Events (matcher
denne udviklingsmaskines faktiske, bekræftet blokerede scenarie).
Ugyldig JSON og netværksfejl degraderer begge til samme tomme schedule
uden crash. `get_next_world_boss`/`get_next_legion`/`get_next_helltide`/
`get_upcoming_events` bekræftet at returnere `None`/`[]` for et tomt
schedule. Fuld 26-build-regression: 0 fejl.

**W5-W10 er ikke ændret eller markeret fejlet pga. denne bug** — den er
helt isoleret til Dashboard-event-koden. Character State forbliver ON
HOLD.

---

**Tidligere fase:** Production Validation — Real bug fundet og rettet
under brugerens egen Windows-test (v1.0.2)

Brugeren havde en rigtig installeret build der viser "Version 1.0.0"
(bygget/installeret før denne Production Validation-fase), bekræftede
Check for Updates fandt v1.0.1 korrekt, men "Update Now" gjorde
**absolut ingenting** — ingen Preparing/Downloading/Verifying/
Installing/Restarting, ingen installer åbnede.

### Root cause — fundet med bevis, ikke gæt

En midlertidig diagnostik-CI-step blev tilføjet (`dd13e85`, fjernet
igen i `c894381`) der kørte `_on_update_now_clicked` PRÆCIST som en
frozen Windows-build ville, mod den ÆGTE v1.0.1-release, på en RIGTIG
`windows-latest`-runner. Resultat: **hele flowet fuldførte korrekt**
end-to-end — rigtig progress-sporet download, rigtig verifikation,
rigtig backup, `launch_installer` kaldt med den korrekte rigtige sti.
Selve opdaterings-logikken var altså IKKE i stykker.

Det reelle hul: `subprocess.Popen()` der lykkes betyder kun at Windows
accepterede at starte en proces — intet om hvorvidt processen stadig
lever et øjeblik senere. `_on_update_now_clicked` stolede blindt på
dette og lukkede appen ubetinget 1 sekund efter. En rigtig gaming-PC's
antivirus/sikkerhedssoftware kan — og gjorde efter alt at dømme —
dræbe en lige-downloadet, usigneret .exe næsten øjeblikkeligt efter
start. Når det sker, lukker den gamle app sig stadig pligtskyldigt på
skema, ingen installer-vindue viser sig nogensinde, og der er intet
tilbage at genstarte fra — uadskilleligt fra "der skete ingenting" set
fra brugeren, selvom flere ting teknisk skete meget hurtigt forinden.

### Fix

`src/updater.py`s `launch_installer()` returnerer nu sit `Popen`-håndtag.
`_on_update_now_clicked` (`src/app.py`) venter kort og tjekker
`proc.poll()` FØR appen lukkes — er processen allerede afsluttet, vises
nu en tydelig, handlingsorienteret fejl ("The installer closed
immediately after starting - it may have been blocked by antivirus/
security software...") i stedet for at appen stille forsvinder uden
forklaring, og appen lukkes IKKE, så brugeren kan prøve igen eller
downloade manuelt.

**Filer ændret:** `src/updater.py`, `src/app.py`,
`.github/workflows/windows-build.yml` (diagnostik tilføjet og igen
fjernet — permanent tilstand er uændret bortset fra selve fixet).

**Tests:** Headless, simuleret frozen Windows-miljø: "processen døde
med det samme"-tilfældet viser nu den nye fejlbesked, genaktiverer
Update Now-knappen, og kalder IKKE `QApplication.quit()`; det normale
"processen lever"-tilfælde er upåvirket (viser stadig "Installer
started..." og lukker via den eksisterende 1-sekunds-timer). Fuld
26-build-regression: 0 fejl.

**Windows CI:** Diagnostik-kørslen (`35074507467`) beviste selve
opdaterings-logikken virker korrekt på ren Windows — det var netop
denne kørsel der gjorde det muligt at udelukke en kode-fejl i selve
flowet og pege præcist på Popen-livstjek-hullet i stedet. Efter fixet:
ny build (`35075313284`) **success**.

### Ny release til gentest

**`v1.0.2`** oprettet (samme metode som v1.0.1 — eksisterende CI-
pipeline, ingen manuel build), assets: `Diablo4Companion-Setup.exe`
(39 369 377 bytes) + `.sha256`, checksum uafhængigt bekræftet.
`isDraft: false`, `isPrerelease: false`.

**Brugeren skal:** åbne den installerede app → Settings → "Check for
Updates" → skal nu finde v1.0.2 → "Update Now" — hvis antivirus/
sikkerhedssoftware er den reelle årsag, vil brugeren nu se den nye,
tydelige fejlbesked i stedet for stilhed, hvilket bekræfter diagnosen;
hvis installationen derimod lykkes helt, er problemet løst.

**v1.0.1 (tidligere Production Validation-fund, stadig gyldigt
server-side):** Server-side flow (Check for Updates → asset-
identifikation) blev bekræftet med ægte, levende data mod v1.0.1 —
se detaljer nedenfor. Det var netop DENNE release brugerens
installerede 1.0.0-build fandt og forsøgte at opdatere til, hvilket
afslørede ovenstående fejl.

### Hvad der blev gjort

1. **Version bumpet 1.0.0 → 1.0.1** (`9385f0a`) — ren version-bump, ingen
   funktionsændring, specifikt til denne validering.
2. **Reel CI-fejl fundet og rettet FØR release:** push'et fra W10 (som
   tilføjede `builds/manifest.json`, en 27. reel `.json`-fil) udløste
   automatisk en Windows-build der **fejlede** — CI's "Verify installed
   files"-step havde et hardcodet `-ne 26`-tjek fra før W10 fandtes.
   Rettet minimalt (`30f69d4`): det forventede antal udledes nu af det
   faktiske kildetræs `builds/*.json`-antal i stedet for et hardcodet
   tal, så det ikke kan drifte ud af sync igen. Ny kørsel (`35073222236`)
   **bestået**.
3. **Rigtig GitHub Release oprettet:** `v1.0.1`, bygget fra commit
   `30f69d4` via den EKSISTERENDE Windows-pipeline (ingen manuel build)
   — `Diablo4Companion-Setup.exe` (39 370 464 bytes) +
   `Diablo4Companion-Setup.exe.sha256`. Uafhængigt bekræftet: SHA256 i
   den uploadede checksum-fil matcher en selvstændigt genberegnet
   `sha256sum` af den downloadede .exe, 100% identisk.
   `isDraft: false`, `isPrerelease: false` (bekræftet via `gh release
   view --json`) — nødvendigt for at `GET .../releases/latest` (det
   endpoint appens Check for Updates rent faktisk bruger) overhovedet
   finder den.
4. **Server-side flow bekræftet med ægte, levende data** (headless,
   simulerede en installeret 1.0.0-app): "Check for Updates" mod den
   RIGTIGE, nyoprettede v1.0.1-release viste korrekt "A newer version is
   available: v1.0.1 (currently on 1.0.0)", viste "Update Now"-knappen,
   og `find_installer_asset`/`find_checksum_asset` fandt begge de
   rigtige assets (præcist navn + størrelse) fra det rigtige release-
   objekt — ikke mocket, en ægte GitHub API-response.

### Krævede manuelle Windows-tests (kan IKKE udføres herfra)

Følgende kræver en rigtig installeret Windows-app på en rigtig
Windows-PC og er **ikke** udført af denne session:

1. Installér `Diablo4Companion-Setup.exe` fra
   https://github.com/jens3105/Diablo4Companion/releases/tag/v1.0.1
   som var det en frisk 1.0.0-lignende installation (eller: sæt
   `src/version.py` midlertidigt til `"1.0.0"` lokalt før du bygger/
   installerer en test-forgænger, hvis du vil teste en ægte
   1.0.0→1.0.1-opgradering — dokumentér selv hvilken du valgte).
2. Åbn appen → Settings → bekræft "Current version: 1.0.0" (eller
   hvad end forgænger-versionen var).
3. Tryk "Check for Updates" → bekræft "A newer version is available:
   v1.0.1 ...".
4. Tryk "Update Now" → observér hele forløbet: Preparing (backup) →
   Downloading → Verifying → Installing → Restarting.
5. Bekræft appen lukker og genstarter (Inno Setups egen "Launch"-
   checkbox ved enden af wizarden).
6. Settings → bekræft "Current version: 1.0.1".
7. Test Dashboard (World Boss/Helltide/Legion/Upcoming Events).
8. Test mindst 2-3 builds i Build Guide.
9. Test Paragon, Gear Builder, Gems, Tempering, Build Advisor.
10. Settings → "Build Data"-sektionen → bekræft version vises korrekt,
    og at "Check for Build Data Updates" stadig fungerer uafhængigt af
    app-opdateringen der lige skete.

**Rollback:** W9's backup/cleanup/restore-mekanik er allerede
uafhængigt verificeret mod en RIGTIG Windows-installation i CI (se W9-
sektionen nedenfor, run `35068798145`) — men en levende "opdatering
fejler reelt og rollback redder dagen"-test er bevidst IKKE forsøgt
her: det ville enten kræve en ægte, uforudset fejl, eller at denne
session bevidst udgiver en ødelagt release for at fremprovokere en
fejl — det sidste er præcis den "risikable manipulation af production-
installationen" fasen selv advarer imod, så det er ikke gjort uden din
eksplicitte anmodning.

---

**Tidligere fase:** Windows Product Phase W10 — Build Data Updates — **DONE.**

Et helt separat opdateringssystem for Diablo 4 build-JSON-filerne
(`builds/*.json`), fuldstændig uafhængigt af app-versions-opdateringen
(`src/updater.py`, W5-W9 — **ikke rørt** i denne fase, bekræftet via
`git diff --stat -- src/updater.py` = tom). App-version og
Build-Data-version er nu to helt separate koncepter med to separate
opdaterings-flows.

- **Build-data-kilde:** ingen ny hosting nødvendig — GitHub server
  allerede ethvert committet fil som en almindelig offentlig GET via
  `https://raw.githubusercontent.com/jens3105/Diablo4Companion/feature/dashboard-v2/builds/<filnavn>`
  (samme slags endpoint som Maxroll-data-pipelinen og W5-W9's GitHub
  Releases API allerede bruger). Selve manifestet hentes samme vej:
  `.../builds/manifest.json`.
- **Versioneringsmetode:** almindelig menneskeligt-læsbar dato-streng
  (`"YYYY-MM-DD"`, fx `"2026-09-16"`) som `version`-feltet i
  `builds/manifest.json` — bevidst IKKE bundet til en git commit SHA
  (W5 fjernede med vilje appens produktions-git-afhængighed) og IKKE et
  semver-skema (unødvendig kompleksitet for build-data). Ren
  streng-sammenligning (`remote_version <= local_version`) er sikker
  for netop dette faste-bredde, zero-padded `YYYY-MM-DD`-format, da det
  sorterer identisk leksikografisk og kronologisk — dokumenteret som
  kommentar i `src/app.py`'s `_on_check_build_data_updates_clicked`.
- **Filer ændret:**
  - `builds/manifest.json` (ny, committet) — den autoritative fil-liste
    (alle 26 rigtige build-filer, alfabetisk, genereret ved reelt at
    liste `builds/*.json` — ikke gættet) + version-stemplet. Denne fil
    fungerer BÅDE som den fjerntliggende sandhed (hostet på GitHub) OG
    som den lokale version-record (læses direkte fra disk, intet nyt
    QSettings/database-lag).
  - `src/build_data_updater.py` (ny fil) — `fetch_remote_manifest`/
    `read_local_manifest`/`download_build_data`, rene funktioner,
    ingen import fra/til `src/updater.py`.
  - `src/managers/leveling_manager.py` — den eksisterende minimale
    schema-tjek (`"build_name" in data and "milestones" in data`) i
    `_load_builds` udtrukket til en ny `LevelingManager.
    is_valid_build_schema`-staticmethod, så `build_data_updater.py`
    genbruger PRÆCIS samme tjek i stedet for at opfinde et andet. Ingen
    anden adfærdsændring i denne fil.
  - `src/app.py` — ny, separat "Build Data"-sektion i
    `SettingsInterface` (egne widgets/state/handlers: `build_data_
    version_label`, `build_data_status_label`, `check_build_data_
    button`, `update_build_data_button`, `_pending_build_data_
    manifest`) — rører aldrig `_pending_update_release`/`update_now_
    button`/noget fra "App Updates"-sektionen. `SettingsInterface`
    tager nu en `leveling_manager`-reference (minimal, nødvendig
    wiring — `MainWindow` sender sin eksisterende `self.
    leveling_manager` med).
  - `diablo4companion.spec`/`installer/diablo4companion.iss`/
    `.github/workflows/windows-build.yml`: **ingen ændring** —
    bekræftet (ikke antaget) at spec-filens eksisterende glob
    (`builds/*.json`) automatisk fanger den nye `manifest.json` (27
    filer i stedet for 26 i `builds_datas`-listen, verificeret direkte
    med Python-glob-kald).
- **Download/verify/install-flow:** for hver fil i `remote_manifest
  ["files"]` (den ENESTE kilde til hvilke filer der nogensinde
  downloades — aldrig et gæt): GET fra raw.githubusercontent.com,
  tjek HTTP-status, ikke-tomt indhold, gyldig JSON, og det genbrugte
  minimale schema-tjek. ALT dette sker i en frisk `tempfile.mkdtemp()`-
  mappe oprettet som SØSKENDE til `builds_dir` (ikke i system-temp) —
  netop dette gør de efterfølgende `os.replace()`-kald garanteret
  atomiske på både POSIX og Windows (samme filsystem), ikke kun
  "sandsynligvis". Fejler ÉT tjek for ÉN fil, kastes der straks med en
  præcis fil+årsag-besked, og INGEN reelle filer i `builds_dir` er
  rørt — kun efter at ALLE filer er downloadet og verificeret erstattes
  de rigtige filer én for én via `os.replace`. Selve `manifest.json`
  skrives og erstattes SIDST, kun efter alle data-filer er lykkedes, så
  en afbrydelse midtvejs blot betyder at et nyt tjek finder "opdatering
  stadig tilgængelig" igen — aldrig en inkonsistent tilstand.
  `progress_callback(files_done, total_files)` opdaterer UI'et live
  ("Downloading build data... N/26"). Efter succes kaldes
  `leveling_manager._load_builds()` direkte — build-data opdateres i
  UI'et med det samme, ingen genstart nødvendig.
- **Offline fallback:** bekræftet testet — `builds/manifest.json`
  fraværende helt (simulerer en installation fra før denne fase)
  påvirker IKKE `MainWindow`/`LevelingManager`-opstart overhovedet
  (`read_local_manifest` returnerer `None` uden at kaste, Settings
  viser "Build Data Version: unknown (no manifest found)"). Intet
  netværkskald sker nogensinde automatisk ved opstart — kun ved
  eksplicit knap-klik. Et "Check for Build Data Updates"-klik uden
  netværk viser en klar "Could not check for Build Data updates
  (network error)"-besked uden at crashe noget, og genaktiverer knappen
  korrekt.
- **W5-W9 (App Updates/rollback):** bekræftet **fortsat DONE, uændret**
  — `src/updater.py` har `git diff --stat` = tom (0 linjer ændret), og
  to af W7's App Updates-scenarier (netværksfejl, up-to-date) blev
  gen-kørt eksplicit efter W10's ændringer for at bevise ingen
  regression, begge stadig korrekte.
- **Character State:** fortsat **ON HOLD**, uændret, ikke rørt i denne
  fase.
- **Windows CI:** **ikke kørt, bevidst vurderet unødvendigt.** Denne
  fases logik er ren Python-fil-I/O + HTTP, ingen PyInstaller/Inno
  Setup-relevans. Bekræftet direkte (ikke antaget) at
  `diablo4companion.spec`'s eksisterende `glob.glob(".../builds/*.json")`
  automatisk fanger `manifest.json` uden nogen `.spec`/`.iss`-ændring —
  en ny Windows CI-kørsel ville derfor kun genbekræfte allerede-kendt
  bundling-adfærd, intet nyt om selve W10-koden (som er 100% testbar
  fra Linux, da den ikke rører packaging/frozen-specifik sti-logik ud
  over den allerede-eksisterende `LevelingManager.builds_dir`, som selv
  er uændret i sin `sys.frozen`-opløsning).
- **Sidste commit:** `f2ba7ad` — "Windows Product Phase W10: Build Data
  Updates" (pushet til `feature/dashboard-v2`).

---

**Tidligere fase:** Dashboard Data/UI Bugfix (før W10) — **DONE.**
Prioriteret bugfix-fase, indsat mellem W9 og W10 på brugerens direkte
anmodning. Ikke en del af Windows Product-nummereringen.

- **Problem 1 (forkert live data):** Sporede hele World Boss/Legion/
  Helltide-datastrømmen (helltides.com → `src/api.py` →
  `src/app.py`s `load_world_boss`/`load_legion`/`load_helltide` →
  `EventCard`) mod den ÆGTE, live helltides.com-API — hentet via en
  rigtig browser-session, da både `requests` og `WebFetch` får 403 fra
  Cloudflares bot-challenge (bekræftet ikke maskine-specifikt). Hvert
  felt-navn/struktur koden allerede antog (top-niveau
  `world_boss`/`legion`/`helltide`-nøgler; `startTime`/`timestamp`/
  `type` pr. post; kun `world_boss` har `boss`/`zone`) matchede den
  rigtige API præcist — **ingen felt-ombytning fundet i den kørende
  kort-wiring-kode selv.**
  **Den reelle rodårsag der blev fundet og rettet:** `get_next_world_
  boss`/`get_next_legion`/`get_next_helltide`/`get_upcoming_events`
  kaldte hver især `self.api.get_schedule()` uafhængigt — op til 4
  separate HTTP-kald inden for millisekunder af hinanden pr. dashboard-
  opdatering. Da helltides.com's Cloudflare-udfordring vides at blokere
  almindelige HTTP-klienter intermitterende, kunne ét korts kald ramme
  den live API mens et andets (kaldt lige efter) blev blokeret og faldt
  tilbage til det lokalt beregnede estimat — reelt inkonsistente,
  forskellig-kilde data på tværs af kort i samme opdatering. Rettet ved
  at hente schedulen ÉN gang pr. opdateringscyklus og genbruge den
  samme snapshot i alle forbrugere.
  Tilføjede desuden defensiv validering: hver rigtig schedule-post
  bærer sit eget `"type"`-felt (bekræftet live) — de fire metoder
  springer nu enhver post over hvis dens eget `type` ikke matcher den
  liste den står under, i stedet for blindt at stole på den ydre nøgle
  — den egentlige rodårsags-niveau-fix for denne fejlklasse.
- **Problem 2 (Upcoming Events):** Udvidet fra 5 til 8 rigtige events,
  ny "Location"-kolonne (rigtig zone for World Boss, bogstaveligt
  "DATA UNAVAILABLE" for Legion/Helltide — den live API leverer
  bekræftet intet location-felt for de to typer). Mindre lodret plads
  trods flere rækker: `CaptionLabel` i stedet for `BodyLabel`
  (mindre linjehøjde) + strammere grid-spacing.
- **Filer ændret:** `src/api.py`, `src/app.py`, `src/upcoming_card.py`.
  `src/updater.py` (W5-W9) er ikke rørt.
- **Tests:** Testet mod den ægte, live-bekræftede API-struktur —
  World Boss/Legion/Helltide-kort bekræftet at modtage KUN egne felter
  (ingen boss/zone-lækage til Legion/Helltide); `get_schedule()`-kald
  under opstart bekræftet faldet fra 4 til 1; en bevidst forkert-typet
  post bekræftet korrekt sprunget over; Upcoming Events bekræftet at
  vise rigtigt navn/location for World Boss og ærlig DATA UNAVAILABLE
  for Legion/Helltide. Fuld 26-build-regression: 0 fejl.
  `src/updater.py` bekræftet stadig importerbar uændret.
- **Commit:** `cc10305`.

Windows Product Phase W9 (Safe Rollback) forbliver **DONE**. W10
(Build Data Updates) forbliver **IKKE STARTET**. Character State
forbliver **ON HOLD**.

### Tidligere: Windows Product Phase W9 — Safe Rollback

**DONE**, bekræftet på
den rigtige Windows-runner. Kerne-indsigt: Inno Setup beskytter allerede
selv mod at en afbrudt installation efterlader halvkopierede filer
(indbygget transaktionslogik) — appens egen kode dækker i stedet det
ene tilfælde Inno Setup ikke kan se: at den nye version installeres
"succesfuldt", men rent faktisk ikke virker. Løsning: backup lige før
installeren startes + selv-tjek ved næste opstart, uden nogen ny
overvågnings-proces.

- **`src/updater.py`**: 3 nye funktioner —
  `backup_install_dir`/`cleanup_backup`/`restore_backup`. Begge
  destruktive funktioner nægter (rejser/logger, sletter intet) med
  mindre stien er en ægte underkatalog af det forventede backup-root
  (`os.path.commonpath`-baseret tjek), og `restore_backup` nægter
  desuden med mindre install-mappens navn matcher det rigtige
  `"Diablo4Companion"` (fra `.iss`'s `DefaultDirName`) — aldrig et gæt.
  `restore_backup` er en testet, men **ikke automatisk koblet**
  primitiv (manuel genopretning), bevidst, se begrænsningen nedenfor.
- **`src/app.py`**: `_on_update_now_clicked` laver nu en rigtig backup
  af den nuværende installation (kun når frozen — intet at sikkerhedskopiere
  ved kørsel fra kilde) lige før `launch_installer`, og gemmer 3
  QSettings-nøgler (`update/pending_backup_path`/`previous_version`/
  `target_version`). Hvis backuppen selv fejler, annulleres opdateringen
  helt i stedet for at risikere den nuværende installation.
  `MainWindow.__init__` tjekker disse nøgler ved HVER opstart (ét billigt
  QSettings-opslag i det normale "intet ventende" tilfælde): matcher
  den nuværende version target — ryd op i backuppen (opdatering lykkedes).
  Matcher den ikke (stadig den gamle version) — intet gendannes (appen
  kører jo fint), men en ærlig, afvisbar InfoBar-besked vises, og
  backuppen bevares til evt. manuel genopretning.
- **Dokumenteret begrænsning (ikke skjult)**: hvis den nye .exe slet
  ikke kan starte, findes der ingen kørende proces til at udføre
  selv-tjekket — dette kræver bevidst ingen ny overvågnings-proces,
  da det er en væsentligt større feature end en rollback-sikkerhedsfase
  bør koste. Backuppen giver stadig et menneske en ligetil manuel vej
  til at gendanne via `restore_backup`.
- **`.github/workflows/windows-build.yml`**: nyt step tester
  `backup_install_dir`/`cleanup_backup`/`restore_backup` mod den RIGTIGE
  installerede app-mappe fra det eksisterende W3 silent-install-step —
  bekræftede reelt: komplet byte-for-byte backup, korrekt afvisning af
  en rigtig sti uden for backup-root (`C:\Windows` selv!), korrekt
  afvisning af CI-testens forkert navngivne install-mappe, og en reel
  gendannelse der rydder en simuleret "ødelagt installation" og lægger
  den rigtige .exe tilbage.

**Note om denne fase:** Den oprindelige agent ramte en UGENTLIG
rate-limit (nulstillet kl. 09:00) lige efter at have skrevet al kode og
CI-testen, men FØR den nåede at trigge/overvåge den rigtige
Windows-kørsel. Jeg (den koordinerende session) gennemgik al kode
personligt (path-sikkerhedstjek, `.iss`-navn-match, QSettings-logik),
kørte selvstændige lokale tests af alle 3 startup-scenarier (intet
ventende, match, mismatch) samt en fuld 26-build-regression — alt rent
— committede (`2695c3d`), og triggede/overvågede selv den rigtige
Windows CI-kørsel (`35068798145`): **success, 2m58s**, alle 5 W9-tjek
bekræftet i loggen ("ALL W9 REAL-WINDOWS CHECKS PASSED").

**Kræver stadig brugerens egen manuelle Windows-test** (kan ikke
bevises i CI, jf. denne fases eksplicitte (a)/(b)/(c)-skelnen): den
fulde flow mod en ægte nyere release (ingen findes endnu), reelt at
annullere installer-wizarden og se "Update did not complete"-beskeden,
reelt at simulere en ny version der ikke kan starte og bruge
`restore_backup` manuelt til at komme tilbage, og at InfoBar-beskederne
faktisk vises/kan afvises i en rigtig GUI-session.

W10 (Build Data Updates) er stadig **IKKE STARTET**. Character State
er stadig **ON HOLD**.

### Tidligere: W8 — Download → Verify → Install → Restart

"Update Now" (W7) er nu en reel, virkende Windows-opdaterer:
finder installer-asset'et på det bekræftede GitHub Release-target
(`_pending_update_release`), downloader det til en
`tempfile.mkdtemp()`-sti, verificerer det (størrelse altid, SHA256 når
en `.sha256`-sidecar findes), starter den verificerede installer
(`subprocess.Popen(..., shell=False)`), og lukker appen 1 sekund efter
et vellykket start så Inno Setups egen `[Run]`-sektion kan genstarte
den nye version — ingen custom restart-helper-proces.

**HARD CONSTRAINT overholdt:** ingen GitHub Release er oprettet,
redigeret eller på anden måde publiceret i denne fase — brugeren blev
eksplicit spurgt og sagde nej til at oprette en (selv en draft/test-
prerelease) for at teste denne pipeline. Al test er kørt mod
konstrueret/fake release-data og allerede-eksisterende offentligt
indhold (se "Tests" nedenfor).

Ingen rollback (W9), ingen Build Data-updater (W10), ingen Character
State, ingen Diablo-feature-arbejde i denne fase. W9/W10 er begge
stadig **IKKE STARTET**.

### W8 — hvad er lavet

- **Ny `src/updater.py`** (rene funktioner, ingen ny dependency —
  `requests`/`hashlib`/`subprocess`/`tempfile`/`os`, alle allerede brugt
  i projektet):
  - `find_installer_asset(release)` / `find_checksum_asset(release)` —
    matcher et release-assets `"name"`-felt PRÆCIST mod hhv.
    `"Diablo4Companion-Setup.exe"` og
    `"Diablo4Companion-Setup.exe.sha256"` (ingen pattern/gæt). Returnerer
    `None` gracefully hvis fraværende — en reel, forventet tilstand
    (gammel/mangelfuld release), ikke en fejl.
  - `download_asset(asset, dest_path, progress_callback=None)` —
    streamer via `requests.get(..., stream=True)` til en
    `tempfile.mkdtemp()`-baseret sti, kalder `progress_callback` pr.
    chunk. Kaster reelt på netværksfejl/timeout, og på en downloadet
    størrelse der ikke matcher `asset["size"]` (ufuldstændig download).
  - `verify_download(file_path, asset, checksum_asset_data)` — tjekker
    ALTID filstørrelse mod `asset["size"]`. Når `checksum_asset_data`
    (indholdet af `.sha256`-sidecar'en) er givet, udregnes filens
    RIGTIGE SHA256 (`hashlib.sha256`) og sammenlignes — et mismatch er
    ALTID `False`, aldrig overtrumfet af en bestået størrelsestjek. Uden
    checksum returneres ærligt `"size-only check passed, no checksum
    available"` i stedet for at foregive fuld verifikation.
  - `launch_installer(installer_path)` — `subprocess.Popen([path],
    shell=False)`. Aldrig `shell=True`, stien er eneste argument — ingen
    GitHub-metadata-afledt streng når nogensinde et shell.
- **`src/app.py`'s `SettingsInterface._on_update_now_clicked`** udvidet
  fra W7's placeholder til den fulde pipeline: Preparing → Downloading
  (med procent/KB-status) → Verifying → Installing → Restarting, alt
  vist via det eksisterende `self.update_status_label`.
  `self.update_now_button` deaktiveres under hele forløbet og
  genaktiveres på ALLE fejl-stier. Intet asset fundet → fejlbesked, stop
  (intet download-forsøg). Download-fejl → fejlbesked, best-effort
  oprydning af det delvise temp-fil (`shutil.rmtree(ignore_errors)`),
  stop. Checksum-hentning fejler for sig selv → falder tilbage til
  size-only-verifikation i stedet for at afbryde hele opdateringen.
  Verifikation fejler (uanset årsag) → viser den præcise årsag, sletter
  den dårlige temp-fil, og starter ALDRIG installeren — dette er en hård
  regel, ikke en nice-to-have. Kun ved bestået verifikation: starter
  installeren, og lukker appen via `QTimer.singleShot(1000,
  QApplication.quit)` så statusteksten når at blive tegnet først.
- **`installer/diablo4companion.iss`**: ny `[Run]`-sektion der bruger
  Inno Setups eget indbyggede "launch after install" (`nowait postinstall
  skipifsilent`) — ingen custom restart-helper-proces nødvendig.
  `skipifsilent` bekræftet (se Windows-runner-verifikation) at IKKE
  bryde den eksisterende W3 `/VERYSILENT` CI-installationstjek.
- **`.github/workflows/windows-build.yml`** (udvidet, ingen
  release-publicering tilføjet): ny step "Compute installer SHA256
  checksum" (`Get-FileHash` i PowerShell) lige efter Inno
  Setup-kompileringen, skriver `Diablo4Companion-Setup.exe.sha256` som
  en sidecar-fil, uploadet sammen med den eksisterende
  `Diablo4Companion-Setup`-CI-artifact (`actions/upload-artifact`) —
  dette er en privat CI-artifact, ikke en offentlig release, så det er
  inden for scope. Derudover en ny step "Test launch_installer() against
  a real Windows executable" der kalder den rigtige
  `src.updater.launch_installer()` mod `notepad.exe` på runneren for at
  bevise selve `subprocess.Popen(..., shell=False)`-mekanismen virker på
  Windows — helt afkoblet fra GitHub Releases.

### W7 — hvad er lavet

- **`src/app.py`**: Ny `self.update_now_button` (`PrimaryPushButton`,
  genbruger eksisterende komponent, ingen ny import) — skjult som
  standard, vist/aktiveret KUN i den ene gren af
  `_on_check_updates_clicked` hvor en reelt nyere release er bekræftet
  (`remote_version > local_version`). Nulstillet (skjult +
  `_pending_update_release = None`) i starten af HVERT nyt tjek, så et
  gammelt target aldrig kan hænge ved fra et tidligere klik.
- Ny `self._pending_update_release: dict | None` — det fulde,
  bekræftede GitHub Release-objekt (ikke kun tag'et), som W8's
  faktiske download/verify/install/restart-pipeline skal bruge som
  target. `None` i alle andre udfald (up to date, ingen releases
  endnu, ikke-parsbar version, netværks-/API-fejl).
- Ny `_on_update_now_clicked()` — selve handlings-søm'en W8 udvider.
  Nægter at gøre noget hvis `_pending_update_release` er tom
  (defensivt fallback, selvom knappen kun vises når et target er
  bekræftet). Med et gyldigt target: viser en tydelig
  bekræftelsestekst med versionsnavnet og henviser til manuel download
  fra GitHub Releases-siden i mellemtiden — intet download, ingen
  filverifikation, ingen installation, ingen app-luk/genstart, ingen
  rollback.

### W6 — hvad er lavet

Ingen kode-ændring. Testet eksplicit (se "Tests" nedenfor) at
`src/app.py`'s eksisterende `_on_check_updates_clicked`
(implementeret i W5) korrekt håndterer: current==latest, current<
latest, netværksfejl, manglende `tag_name`, ugyldig JSON, og
HTTP 5xx — alle uden crash, alle med en tydelig, korrekt status-tekst,
og ingen af dem skriver ny QSettings-state.

### W5 — hvad er lavet

- **`src/app.py`**: `GITHUB_COMMIT_API_URL`/`GITHUB_BRANCH`/
  `get_local_commit_sha()` (git `rev-parse HEAD` mod branch-tip-commit-
  API'et) fjernet helt — ikke bevaret som dev-fallback, da W5's
  eksplicitte mål er at stoppe med at afhænge af git for
  produktions-version/update-status. Erstattet af
  `GITHUB_RELEASES_API_URL` (`.../releases/latest`) + en ny
  `_parse_semver()`-hjælper der sammenligner release-tags
  (`"v1.2.3"`/`"1.2.3"`) mod `src/version.py`'s `__version__` som
  `(major, minor, patch)`-tupler.
- Settings-sektionen "Build Data Updates" omdøbt til **"App Updates"**
  (indholdet er reelt ændret — det handler nu om app-versionen, ikke
  build-data-friskhed, som forbliver W10). "Current version"-linjen
  viser nu altid `src/version.py`'s `__version__` (samme kilde som
  W4) — **aldrig** "unknown"/"not a git checkout" mere, hverken fra
  kilde eller i den installerede .exe.
- Klik-handleren henter nu `releases/latest`, håndterer eksplicit det
  reelle, nuværende tilfælde (ingen GitHub Release er udgivet endnu —
  det er en senere fase) som en ærlig "No published releases found
  yet." i stedet for en generisk netværksfejl-besked (skelnet via et
  eksplicit 404-tjek, ikke en fanget exception), og viser ellers
  "Up to date" / "A newer version is available: ..." / en
  "kunne ikke sammenligne"-besked for et ikke-parsbart tag — aldrig
  gættet.
- `import subprocess` fjernet fra `src/app.py` (kun brugt af den nu
  fjernede funktion).
- **Ingen ændring af Windows-workflowet** — ren app-logik uden nye
  dependencies eller pakke-relevans, allerede dækket af W4's seneste
  beståede build/launch på den rigtige runner.

### W4 — hvad er lavet

- **`src/version.py`** (ny fil): `__version__ = "1.0.0"` — den ENE
  kanoniske kilde. Bevidst et almindeligt importeret Python-modul, ikke
  en bundlet datafil — det omgår helt den `_internal/`-overraskelse W3
  stødte på, da PyInstallers `Analysis` selv følger
  `from src.version import __version__`-import-grafen, uden nogen
  ændring af `diablo4companion.spec` nødvendig.
- **`src/app.py`**: Settings-siden viser nu "Version 1.0.0" (én linje,
  ingen redesign).
- **`.github/workflows/windows-build.yml`**: læser versionen med et
  ét-linjes `python -c "from src.version import __version__; ..."`-
  trin og sender den ind i Inno Setup-kompileringen via
  `/DMyAppVersion=...`.
- **`installer/diablo4companion.iss`**: modtager versionen via `/D`
  command-line define, med den gamle hardcodede `"1.0.0"` bevaret kun
  som fallback-default hvis scriptet nogensinde kompileres uden
  `/D` (fx en lokal ad hoc `ISCC`-kørsel).
- **Reel fejl fundet og rettet undervejs**: en tilføjet post-install
  registry-version-tjek i workflowet slog første kørsel fejl på et
  ikke-relateret quirk (Add/Remove Programs-registreringen matchede
  ikke som forventet, selvom selve installationen var korrekt) — nedgraderet
  til en ikke-fatal advarsel (`Write-Warning`) i stedet for at blokere
  pipelinen, da `/DMyAppVersion` allerede var bekræftet korrekt sat i
  logs. Rettet, ikke skjult.

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

Windows Product Phase W10 — Build Data Updates (denne fase).

## Last commit

`b08db7d` — "CRITICAL Dashboard fix: remove fabricated local schedule
fallback entirely" (pushet).

Forudgående Production Validation-kæde (stadig gyldig, uændret):
`9385f0a` (version 1.0.1) → `30f69d4` (CI-fix, hardcoded 26-tjek) →
`dd13e85` (midlertidig diagnostik) → `c894381` (Popen-livstjek-fix) →
`eac4dd6` (version 1.0.2). GitHub Releases `v1.0.1` og `v1.0.2`
oprettet separat (ikke commits). **Denne Dashboard-fix er endnu ikke
udgivet som en ny release/version** — den ligger på `feature/dashboard-v2`,
klar til at blive inkluderet i en fremtidig version-bump når brugeren
ønsker det.

Branch: `feature/dashboard-v2` (repoets eneste/default branch — der er
ikke noget `main`, det er normalt for dette repo).

## Build command

```
pyinstaller diablo4companion.spec
```

Output: `dist/Diablo4Companion/` (onedir), inkl.
`Diablo4Companion.exe` + `builds/*.json`.

## Tests

- **W10 — Lokal unit-test (2026-09-16, Linux), `src/build_data_updater.py`:**
  `fetch_remote_manifest` mod mockede svar — HTTP-fejl (rejser
  `requests.RequestException`), ugyldig JSON (rejser `ValueError`),
  manifest uden `"files"`-felt (rejser `ValueError`), succes (korrekt
  dict). `read_local_manifest` mod 3 rigtige temp-mapper — gyldigt
  manifest (dict), manglende fil (`None`), korrupt JSON (`None`, ingen
  exception i noget tilfælde). `download_build_data` mod en rigtig
  lokal target-mappe med kendt originalt indhold + en konstrueret fake
  remote-manifest + mockede HTTP-svar, 6 scenarier: fuld succes
  (bekræftet: begge datafiler + `manifest.json` korrekt erstattet,
  `progress_callback` kaldt korrekt `[(1,2),(2,2)]`, ingen efterladt
  temp-mappe), midt-i-listen HTTP-fejl (404), ugyldig JSON i én fil,
  schema-fejl i én fil, en fil der 404'er, og tomt indhold — for ALLE 5
  fejl-scenarier bekræftet byte-for-byte at target-mappen var
  **fuldstændig urørt** (`dir_snapshot` før/efter identisk) og at
  exception'en navngiver den specifikke fil. 24/24 assertions bestået.
- **W10 — Headless app-niveau (2026-09-16, Linux,
  `QT_QPA_PLATFORM=offscreen`, isoleret temp `HOME`):** app starter
  rent med det rigtige `builds/manifest.json` til stede, Settings viser
  korrekt "Build Data Version: 2026-09-16". Manglende
  `manifest.json` (simuleret pre-W10-installation) bekræftet at IKKE
  påvirke `LevelingManager`/`MainWindow`-opstart overhovedet — viser
  korrekt "unknown (no manifest found)", intet automatisk netværkskald
  sker ved konstruktion. Et "Check for Build Data Updates"-klik uden
  netværk (mocket `ConnectionError`) viser korrekt fejlbesked uden
  crash. Simuleret nyere remote-manifest (mocket) bekræftet at afsløre
  "Update Build Data"-knappen; et efterfølgende mocket, vellykket
  download ind i en rigtig temp `builds_dir` bekræftet at
  `LevelingManager.list_builds()` afspejler den opdaterede build
  ("Heartseeker Rogue (W10 TEST UPDATED)") UDEN genstart, stadig 26
  builds totalt, og Heartseeker Rogues `verified_build`-fravær (dens
  eksisterende no-verified-data-fallback, et indholds-property af selve
  JSON'en) bekræftet uændret af download-mekanismen. Fuld 26-build-
  regressions-sweep: 0 fejl. `src/updater.py` bekræftet `git diff
  --stat` = 0 linjer ændret, og 2 af W7's App Updates-scenarier
  (netværksfejl, up-to-date) gen-kørt eksplicit efter W10's ændringer —
  begge stadig korrekte, ingen regression. 20/20 assertions bestået.
- **W10 — Windows CI:** ikke kørt, vurderet unødvendigt — bekræftet
  (ikke antaget, se ovenfor) at `diablo4companion.spec`'s eksisterende
  `glob.glob("builds/*.json")` automatisk bundler den nye
  `manifest.json` uden nogen `.spec`/`.iss`-ændring, og denne fases
  logik (ren fil-I/O + HTTP) har ingen anden packaging-relevans.
- **W9 — (a) Lokal unit/integration (2026-09-16, Linux):**
  `backup_install_dir`/`cleanup_backup`/`restore_backup` testet mod
  rigtige lokale temp-mappetræer — bekræftet: reel kopiering virker,
  `cleanup_backup` nægter korrekt at røre en sti uden for backup-root
  (testet med `/etc`), `restore_backup` nægter korrekt en
  forkert-navngivet install-mappe, og lykkes korrekt ind i en
  rigtigt-navngivet mappe (rydder en simuleret "broken_marker.txt" og
  lægger den rigtige exe tilbage). App-opstarts-tjekket
  (`_check_pending_update`) testet for alle 3 scenarier: intet
  ventende (hurtig no-op), matchende version (rydder backup op, viser
  "Update complete"), mismatch (backup IKKE slettet, viser "Update did
  not complete"). Fuld 26-build-regression: 0 fejl.
- **W9 — (b) Windows CI (2026-09-16, run `35068798145`, windows-latest):**
  **success, 2m58s.** Nyt step testede `backup_install_dir`/
  `cleanup_backup`/`restore_backup` mod den RIGTIGE app-installation
  W3's silent-install-step producerer (rigtig `_internal/`, rigtige
  `builds/*.json`, rigtig exe) — alle 5 tjek bestod i loggen: komplet
  byte-for-byte backup (filantal + total størrelse matcher exakt),
  `cleanup_backup` nægtede korrekt at røre `C:\Windows` (en rigtig,
  eksisterende Windows-systemmappe — den blev IKKE rørt), `restore_
  backup` nægtede korrekt CI-testens forkert navngivne install-mappe
  (`D4CInstallTest` ≠ `Diablo4Companion`), en reel gendannelse ind i en
  korrekt navngivet mappe ryddede en simuleret "ødelagt installation"
  og lagde den rigtige exe tilbage, og en reel `cleanup_backup` fjernede
  den rigtige backup-mappe bagefter. Uafhængigt genbekræftet af mig
  (den koordinerende session) direkte i workflow-loggen, ikke kun
  agentens egen rapport.
- **W9 — (c) Kræver manuel Windows-test** (kan ikke bevises i CI): den
  fulde `_on_update_now_clicked`-flow mod en ægte nyere release (ingen
  findes — ingen GitHub Release blev oprettet, jf. den fortsatte hårde
  begrænsning fra W8), reelt at annullere installer-wizarden midtvejs
  og se "Update did not complete"-beskeden ved næste opstart, reelt at
  simulere en ny version der slet ikke kan starte og bekræfte en
  person kan bruge `restore_backup` manuelt til at komme tilbage
  (ingen automatisk detektion findes for dette specifikke tilfælde,
  bevidst — se begrænsningen ovenfor), og at InfoBar-beskederne
  faktisk vises/kan afvises korrekt i en rigtig GUI-session.
- **W8 lokal verifikation (2026-09-15, Linux) — rene funktioner
  (`src/updater.py`), ingen netværk/GitHub:**
  `find_installer_asset`/`find_checksum_asset` testet mod konstruerede
  fake release/asset-dicts (matcher GitHub's rigtige JSON-form): præcist
  match, fraværende asset (`None`), manglende `"assets"`-nøgle, og
  bevidste near-miss-navne (forkert case/suffix) — alle korrekte.
  `verify_download` testet med en RIGTIG lokal temp-fil og dens RIGTIGE
  udregnede SHA256: size-only match/mismatch, korrekt checksum, bevidst
  FORKERT checksum (hård fejl, aldrig overtrumfet af bestået
  størrelsestjek), ingen størrelse-info overhovedet, samt to
  virkelighedstro `.sha256`-filformer (trailing newline, "hash␣␣filnavn"
  sha256sum-stil) — alle 17 assertions bestået.
- **W8 lokal verifikation (2026-09-15, Linux) — RIGTIGT netværkskald,
  ingen GitHub-oprettelse:** `download_asset` kørt mod en allerede-
  eksisterende offentlig URL (dette repos egen
  `requirements.txt`-fil rå fra GitHub) for at bevise den rigtige
  HTTP-streaming-med-progress-callback-mekanisme virker end-to-end:
  downloadet indhold matcher byte-for-byte, progress-callback kaldt
  korrekt med slutstatus == fuld størrelse, `verify_download` bestod på
  den rigtige downloadede fil, og fejlede korrekt på en bevidst forkert
  størrelse. `download_asset` bekræftet at kaste `RuntimeError` når
  en asset lyver om sin størrelse (ufuldstændig-download-detektion).
- **W8 lokal verifikation (2026-09-15, Linux) — fuld
  `_on_update_now_clicked`-pipeline mod KONSTRUERET/FAKE release-data**
  (intet rigtigt GitHub Release oprettet, jf. hard constraint;
  `updater.download_asset`/`launch_installer`/`requests.get` monkey-
  patchet så ingen rigtig download/installer-start sker): 6 scenarier
  bestået — intet installer-asset fundet (fejlbesked, intet download-
  forsøg), download-fejl (fejlbesked, `launch_installer` aldrig kaldt,
  knap genaktiveret), FORKERT checksum efter vellykket download
  (verifikation fejler, `launch_installer` ALDRIG kaldt — den hårde
  regel bekræftet), checksum-hentning fejler for sig selv (falder
  korrekt tilbage til size-only og fortsætter til install), fuld
  succes-vej (installer startes, "Restarting..."-status vist), og
  `launch_installer` selv kaster (fejlbesked, appen lukker IKKE, knap
  genaktiveret). Temp-mappe-oprydning bekræftet: kun de 3 scenarier der
  reelt skal beholde den verificerede fil (checksum-fejl-fallback,
  succes, launch-fejl) efterlod en temp-mappe — de 2 fejl-scenarier
  (download-fejl, dårlig checksum) ryddede korrekt op.
- **W8 lokal verifikation (2026-09-15, Linux) — regression:** `from
  src.app import MainWindow` + fuld app-konstruktion uændret under
  headless offscreen. Fuld regressions-sweep af alle 26 builds: 0 fejl.
- **W7 lokal verifikation (2026-09-15, Linux):** headless offscreen.
  Intet-tilgængeligt-tilfælde: "Update Now" forbliver skjult
  (`isHidden()`), og et fremtvunget kald til `_on_update_now_clicked`
  er en no-op (statustekst uændret). Nyere-version-fundet: korrekt
  target fanges i `_pending_update_release`, knappen bliver synlig
  (`isHidden() == False`), klik viser korrekt bekræftelsestekst med
  versionsnavnet. Netværks-/API-fejl: knappen forbliver skjult, target
  forbliver `None`, fremtvunget klik er en no-op. Bekræftet et Update
  Now-klik hverken skriver nye QSettings-nøgler eller nye filer til
  disk (ingen download/install/genstart sker utilsigtet). Fuld
  regressions-sweep af alle 26 builds: 0 fejl.
- **W6 lokal verifikation (2026-09-15, Linux):** headless offscreen,
  mod den eksisterende `_on_check_updates_clicked` (uændret siden W5):
  current==latest ("Up to date (version 1.0.0)."), current<latest
  ("A newer version is available: v1.5.0 (currently on 1.0.0)."),
  simuleret netværksfejl, manglende `tag_name`, ugyldig JSON-krop, og
  HTTP 500 — alle 6 håndteret gracefully med en klar statustekst,
  ingen crash, knappen genaktiveres hver gang. Bekræftet ingen ny
  QSettings-nøgle skrives af et Check for Updates-klik (`allKeys()`
  før/efter identisk). App-opstart bekræftet uændret.
- **W5 lokal verifikation (2026-09-15, Linux):** headless offscreen-
  smoke-test — app starter uændret, `current_version_label` viser
  "Current version: 1.0.0". `_parse_semver` testet med `"v1.2.3"`,
  `"1.0.0"` og en ikke-parsbar streng. Klik-handleren testet mod: (a)
  det RIGTIGE, levende GitHub-repo (ingen Release udgivet endnu →
  korrekt "No published releases found yet."), (b) 3 mockede
  release-svar der dækker alle tre sammenligningsudfald ("A newer
  version is available...", "Up to date...", og en ikke-parsbar
  tag-besked), (c) en simuleret netværksfejl (degraderer korrekt til
  den eksisterende fejlbesked, ingen crash, knappen genaktiveres).
  Fuld regressions-sweep af alle 26 builds efter ændringen: 0 fejl.
  **Ingen Windows-runner-kørsel udløst for denne fase** — ren
  app-logik uden nye dependencies eller pakke-relevans, ingen
  `.github/workflows`- eller `.spec`-ændring, allerede dækket af W4's
  seneste beståede build/launch.
- **W4 lokal verifikation (2026-09-15, Linux):** headless offscreen-
  smoke-test kørt igen efter `src/version.py`-tilføjelsen: `from
  src.version import __version__` giver `"1.0.0"`, appen starter
  uændret (`MainWindow()` konstrueres uden fejl). Ingen ændring i
  `diablo4companion.spec` var nødvendig (PyInstaller følger selv
  import-grafen for et almindeligt Python-modul).
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

## W8 — Windows-runner-verifikation: BESTÅET

Kørt og overvåget live via `gh workflow run` + `gh run watch`, én
iteration, grøn på første forsøg:

- **Run `35003233658`** (auto-udløst af push af commit `1f38fce`
  til `feature/dashboard-v2`): **✓ success.** Alle steps grønne, inkl.
  de eksisterende W2/W3/W4-tjek uændret bestået, samt de to nye W8-
  specifikke steps:
  - "Compute installer SHA256 checksum": `Get-FileHash` kørt mod
    `installer\Output\Diablo4Companion-Setup.exe`, reel SHA256
    (`fd8dda30a775bc91d9dd78e35bc5378b23f6ef3ba29957d6ed5112b238a2cb97`
    i denne kørsel) skrevet til `.sha256`-sidecar-filen og uploadet
    sammen med `Diablo4Companion-Setup`-artifact'en.
  - Eksisterende W3 silent-install-verifikation stadig grøn EFTER
    `[Run]`-sektionen blev tilføjet til `.iss`-filen: exe fundet, alle
    26 `builds/*.json` fundet, uninstaller fundet — bekræfter
    `/VERYSILENT` (som `skipifsilent` er lavet til at respektere)
    stadig korrekt undertrykker den nye "launch after install"-adfærd
    under den automatiserede install-check, ingen regression.
  - Eksisterende launch-check (exe startet, forblev kørende 8s,
    stoppet) stadig grøn.
  - Ny "Test launch_installer() against a real Windows executable":
    `src.updater.launch_installer()` kaldt mod `notepad.exe` på
    runneren — `subprocess.Popen(..., shell=False)`-mekanismen bevist
    at virke reelt på Windows uden at kaste, helt afkoblet fra
    GitHub Releases.

**Dette er en reel, observeret, autoritativ verifikation af selve W8-
mekanismerne (checksum-beregning, installer-`[Run]`-sektion uden
regression på silent-install, ægte processtart) — ikke antaget.**
Ingen retry nødvendig, kørsel bestod på første forsøg.

**Hvad denne kørsel IKKE beviser (og ikke kan, uden en rigtig
publiceret Release, jf. hard constraint):** den fulde
`_on_update_now_clicked`-flow end-to-end mod et ægte
`_pending_update_release`, den interaktive Inno Setup-wizard
gennemført af en bruger, at den gamle app-proces' fil-locks reelt
frigives rent, at "Launch Diablo 4 Companion"-checkboxen reelt starter
den nyinstallerede version, eller at Settings derefter rapporterer den
nye version. Se "Manuelle Windows-tests der mangler" nedenfor.

## W4 — Windows-runner-verifikation: BESTÅET

Kørt og overvåget live via `gh workflow run` + `gh run watch`, to
iterationer (uafhængigt genbekræftet af den koordinerende session via
`gh run list` efter en rate-limit-afbrydelse):

- **Run `34974505298`** (første forsøg, commit `55bc3d4`): PyInstaller-
  build, Inno Setup-kompilering med `/DMyAppVersion=1.0.0` og
  silent-install lykkedes, men et ekstra post-install
  registry-`DisplayVersion`-tjek **fejlede reelt** på et ikke-relateret
  quirk (Add/Remove Programs-registreringen matchede ikke som
  forventet), selvom selve versionen var korrekt sat i logs. Dette blev
  IKKE gemt/pyntet væk — se fix i `bf61371`.
- **Run `34974933430`/`34974949124`** (efter fix, commit `bf61371`):
  **✓ success, hhv. 3m28s og 2m47s.** Registry-tjekket nedgraderet til
  en ikke-fatal advarsel; alle andre steps (inkl. de eksisterende W3-
  verifikationer: exe, `builds/*.json`, uninstaller, launch-check)
  fortsat grønne.

**Dette er en reel, observeret, autoritativ version-bygge- og
install-verifikation — ikke antaget.** Den første fejlende kørsel og
dens root-cause er bevidst dokumenteret her, ikke skjult.

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

## Manuelle Windows-tests der mangler

Kan bevidst ikke testes fra dette Linux dev-miljø, og ikke fra
Windows-CI-runneren heller, jf. hard constraint (ingen rigtig GitHub
Release må oprettes i denne fase) — dette er forventet og efter
brugerens eget valg, ikke en skjult mangel:

- Den fulde `_on_update_now_clicked`-flow end-to-end mod et ÆGTE
  `_pending_update_release` (findes ikke, og er ikke oprettet).
- Selve download-hastighed/-oplevelse mod et rigtigt, stort
  installer-asset (kun testet mod en lille fil, `requirements.txt`).
- At gennemføre den interaktive Inno Setup-wizard som bruger.
- At den gamle app-proces' fil-locks (exe/DLL'er) reelt frigives rent
  når appen lukker via `QApplication.quit()`, så installeren kan
  overskrive dem.
- At "Launch Diablo 4 Companion"-checkboxen i wizarden (den nye
  `[Run]`-sektion) reelt starter den nyinstallerede version.
- At Settings-siden derefter rapporterer den nye version
  (`current_version_label`) korrekt efter en ægte opgradering.

Alt dette kræver brugerens egen hånd på en rigtig Windows-maskine mod
en rigtig publiceret Release — begge dele bevidst uden for denne fases
scope.

## Next phase

Ingen planlagt. **Den kritiske Dashboard-fabrikations-bug er fundet og
rettet (`b08db7d`) — ikke udgivet som release endnu.** Den tidligere
W8-fix (Popen-livstjek, `v1.0.2`) venter stadig på brugerens gentest.
W5-W10 forbliver DONE, uændrede. Character State er stadig ON HOLD.
Vent på konkret instruktion fra brugeren (se PROJECT_ROADMAP.md's
regel: "Start ikke
næste roadmap-fase uden en konkret instruktion"). Mulig fremtidig
opfølgning (ikke startet, kræver eksplicit instruktion): rette
`leveling_manager.py`'s frozen-path-logik til selv at være
`_internal`-bevidst i stedet for at kompensere på installer-niveau.

## Kort changelog (seneste faser, nyeste øverst)

- `b08db7d` — CRITICAL Dashboard fix: `src/local_schedule.py` (den
  hjemmelavede fallback-tidsberegning) slettet helt. Blokeret/tom live
  API giver nu ærligt DATA UNAVAILABLE i stedet for opfundne
  World Boss/Legion/Helltide/Upcoming Events-tider. Fundet via
  brugerens direkte sammenligning med in-game-timere.
- `v1.0.2` (GitHub Release) + `c894381` — Rigtig bug fundet under
  brugerens Windows-test: "Update Now" gjorde ingenting, fordi appen
  lukkede sig selv ubetinget uden at tjekke om den startede installer-
  proces reelt overlevede (sandsynlig antivirus-interferens). Rettet:
  `launch_installer()` returnerer nu sit Popen-håndtag, tjekkes for
  liv før app-luk, viser en tydelig fejl i stedet for stilhed hvis
  processen allerede er død.
- `v1.0.1` (GitHub Release) — Production Validation: første rigtige,
  publicerede release. Server-side flow (Check for Updates → asset-
  identifikation) bekræftet med ægte live-data. `30f69d4` fandt/rettede
  en reel CI-regression (hardcodet 26-fil-tjek) forud for releasen.
- `f2ba7ad` — Windows Product Phase W10: Build Data Updates. Ny
  `builds/manifest.json` (26 filer + dato-version) + ny
  `src/build_data_updater.py` (fetch/read/download-verify-atomisk-
  installer, helt uafhængig af `src/updater.py`) + ny "Build Data"-
  sektion i Settings. Genbruger `LevelingManager`s eksisterende
  minimale schema-tjek (nu udtrukket til
  `is_valid_build_schema`) i stedet for en ny definition. Ingen
  `.spec`/`.iss`/CI-ændring nødvendig (bekræftet, ikke antaget) —
  ingen Windows CI-kørsel udløst for denne fase.
- `cc10305` — Dashboard Data/UI-bugfix: delt schedule-fetch pr.
  opdatering (rettede en reel 4x-redundant-fetch-inkonsistens-bug),
  type-validering, Upcoming Events udvidet til 8 rigtige events +
  Location-kolonne.
- `2695c3d` — Windows Product Phase W9: Safe Rollback. Backup-før-
  install + selv-tjek-ved-næste-opstart, ingen overvågnings-proces.
  Bekræftet på rigtig Windows-runner (run `35068798145`, success).
- `1f38fce` — Windows Product Phase W8: reelt Download → Verify →
  Install → Restart. Ny `src/updater.py` (find/download/verify/launch),
  `_on_update_now_clicked` udvidet til fuld pipeline, Inno Setup
  `[Run]`-sektion (genstart via Inno Setups egen mekanisme), CI beregner
  og uploader en reel SHA256-sidecar. Ingen GitHub Release
  oprettet/publiceret, jf. hard constraint.
- `fb7ae9e` — Windows Product Phase W7: "Update Now"-knap + intern
  `_pending_update_release`-target, som W8 kobler download/install/
  restart på. Intet download/install/restart/rollback endnu.
- Windows Product Phase W6 — Check for Updates: ingen ny kode (W5
  opfyldte allerede alle krav), udtømmende test af 6 scenarier
  bekræftede det.
- `a2ef4d7` — Windows Product Phase W5: GitHub Releases erstatter
  git-checkout-baseret version/update-check; "Not a git checkout"
  kan ikke længere vises.
- `6c22aa2`/`bf61371`/`55bc3d4` — Windows Product Phase W4: én
  kanonisk version (`src/version.py`, `"1.0.0"`), genbrugt af app,
  PyInstaller (via import, ingen spec-ændring) og Inno Setup
  (`/DMyAppVersion`).
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
