; Diablo 4 Companion — Inno Setup script
;
; Windows Product Phase W3 — Windows Installer.
;
; Packages the already-verified W2 PyInstaller onedir build
; (dist/Diablo4Companion/, produced by ../diablo4companion.spec) into a
; single Diablo4Companion-Setup.exe. Installs the ENTIRE onedir folder
; as-is (including the builds/ subfolder) so
; src/managers/leveling_manager.py's sys.frozen path resolution (which
; expects builds/ as a sibling of Diablo4Companion.exe) keeps working
; unchanged.
;
; Install location: {localappdata}\Diablo4Companion with
; PrivilegesRequired=lowest. Chosen over {autopf} (Program Files)
; specifically because it never triggers a UAC elevation prompt — this
; keeps a silent (/VERYSILENT) install fully non-interactive, which
; matters both for a normal non-admin user and for automated CI
; verification on the GitHub Actions Windows runner (see
; .github/workflows/windows-build.yml), where no UAC prompt can be
; answered.
;
; Compile with (from repo root):
;     ISCC.exe /DMyAppVersion=1.0.0 installer\diablo4companion.iss
; (the CI workflow passes /DMyAppVersion using the canonical version
; from ../src/version.py; omitting /D falls back to the hardcoded
; default below). Produces installer\Output\Diablo4Companion-Setup.exe.

#define MyAppName "Diablo 4 Companion"
; Windows Product Phase W4 -- Versioning: the canonical version now
; lives in ../src/version.py. The CI workflow passes it in via
; /DMyAppVersion=X.Y.Z on the ISCC command line; this hardcoded value
; is only a safe fallback default for an ad hoc local compile that
; skips the /D define.
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppExeName "Diablo4Companion.exe"
#define MyAppPublisher "jens3105"
#define MyAppURL "https://github.com/jens3105/Diablo4Companion"

[Setup]
AppId={{9F2C7C3E-6C0A-4B9A-9E9E-6E5B7B1D9C11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Diablo4Companion
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=Output
OutputBaseFilename=Diablo4Companion-Setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
; V1.0.3: real, original app icon now ships at ../assets/icon.ico (see
; scripts/generate_icon.py) — used for the setup wizard/uninstaller
; icon here. The installed app's own shortcuts (below) already get
; their icon for free from the exe's embedded resource (PyInstaller's
; EXE(icon=...) in diablo4companion.spec), so no explicit IconFilename
; is needed on the [Icons] entries.
SetupIconFile=..\assets\icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The entire W2 onedir output, preserved exactly as PyInstaller produced
; it (Diablo4Companion.exe plus its _internal\ folder containing all
; PySide6/Qt runtime DLLs and the bundled builds\*.json data files under
; _internal\builds\). No dev-only files exist in dist/Diablo4Companion/
; to exclude — that folder only ever contains the built onedir bundle.
Source: "..\dist\Diablo4Companion\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; PyInstaller 6.x's default onedir layout places bundled datas under
; _internal\ (e.g. _internal\builds\*.json), not directly beside the
; exe. src/managers/leveling_manager.py's sys.frozen branch (out of
; scope for this installer-only phase to modify) resolves builds/ as a
; sibling of sys.executable's directory - i.e. {app}\builds, not
; {app}\_internal\builds. Rather than rearranging PyInstaller's own
; output (forbidden by this phase's scope) or touching src/ code
; (also out of scope), this second Files entry additionally places a
; copy of the same builds/*.json files directly under {app}\builds so
; the already-shipped frozen-path logic actually finds them at
; runtime. This is additive only - it does not remove or relocate
; anything from the untouched onedir tree above.
Source: "..\dist\Diablo4Companion\_internal\builds\*.json"; DestDir: "{app}\builds"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Code]
// V1.0.3 icon fix: 1.0.2 and earlier shipped with NO custom icon at all
// (Inno Setup's/PyInstaller's generic default), so upgrading an existing
// 1.0.2 install to 1.0.3 in place (same install path, same exe name -
// exactly what this app's own in-app updater does) replaces the exe's
// icon resource on disk, but Windows Explorer's shell icon cache is keyed
// by file path and does not automatically notice/invalidate on a plain
// file overwrite. This is why Programs and Features already shows the
// new icon correctly (it re-reads UninstallDisplayIcon fresh each time
// that page opens) while Desktop/Start Menu shortcuts and the taskbar can
// keep showing the old cached (generic) icon until the shell is told to
// refresh - a real, documented Windows shell behavior, not a defect in
// this app's icon/shortcut configuration (verified separately: the
// installed .ico is a valid, correctly-sized multi-resolution icon, and
// is correctly embedded into both Diablo4Companion.exe and Setup.exe).
//
// Fix: SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, NULL, NULL) is
// the standard Win32 Shell API call (documented by Microsoft, and Inno
// Setup's own FAQ recommends the same call for this exact symptom) that
// tells Explorer to refresh its icon/association cache - no cache files
// are deleted, nothing else is touched.
procedure SHChangeNotify(wEventId: Longint; uFlags: Integer; dwItem1: Longint; dwItem2: Longint);
external 'SHChangeNotify@shell32.dll stdcall';

const
  SHCNE_ASSOCCHANGED = $08000000;
  SHCNF_IDLIST = $0000;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, 0, 0);
end;

[Run]
; Windows Product Phase W8: Inno Setup's own built-in "launch after
; install" mechanism - deliberately used instead of a custom
; restart-helper process, since this already does exactly what W8's
; update pipeline needs (relaunch the newly-installed version once the
; user finishes the wizard). "skipifsilent" means this never fires
; during the existing W3 CI silent-install verification
; (/VERYSILENT implies skipifsilent is honored), so it doesn't affect
; the automated headless install-check.
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,Diablo 4 Companion}"; Flags: nowait postinstall skipifsilent
