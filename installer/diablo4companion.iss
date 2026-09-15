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
;     ISCC.exe installer\diablo4companion.iss
; Produces installer\Output\Diablo4Companion-Setup.exe.

#define MyAppName "Diablo 4 Companion"
#define MyAppVersion "1.0.0"
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
; No custom setup/wizard icon ships in this repo (see ARCHITECTURE.md
; notes for W3) — deliberately left as Inno Setup's default rather than
; fabricating a fake .ico asset.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The entire W2 onedir output, preserved as-is (Diablo4Companion.exe,
; the builds/ subfolder with all 26 builds/*.json files, and every
; PySide6/Qt runtime DLL PyInstaller's COLLECT step gathered). No
; dev-only files exist in dist/Diablo4Companion/ to exclude — that
; folder only ever contains the built onedir bundle.
Source: "..\dist\Diablo4Companion\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
