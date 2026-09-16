# -*- mode: python ; coding: utf-8 -*-
#
# Windows Product Phase W2 — PyInstaller onedir build spec.
#
# Committed (rather than relying on CLI flags baked only into the CI
# workflow) so the exact build configuration is reproducible and
# reviewable in version control. Build with:
#
#     pyinstaller diablo4companion.spec
#
# Produces a onedir bundle at dist/Diablo4Companion/ containing
# Diablo4Companion.exe plus a builds/ folder of the 26 build JSON
# files, which src/managers/leveling_manager.py's LevelingManager
# resolves relative to sys.executable when frozen (see the
# ``getattr(sys, "frozen", False)`` branch added in this phase).

import glob
import os

repo_root = os.path.abspath(os.path.dirname(SPEC))

# Bundle every builds/*.json next to the exe under a "builds" folder,
# matching what LevelingManager expects to find alongside sys.executable
# in a frozen onedir build.
builds_datas = [
    (build_file, "builds")
    for build_file in sorted(glob.glob(os.path.join(repo_root, "builds", "*.json")))
]

# App icon (assets/icon.ico): bundled as a data file (same "beside the
# exe" convention as builds_datas above) so main.py can load it at
# runtime via QIcon for the window/taskbar icon, in addition to being
# passed to EXE()'s own icon= below (which embeds it into the .exe's
# Windows resources - what Explorer/Start Menu/taskbar shortcuts show
# even before the app sets anything at runtime).
icon_path = os.path.join(repo_root, "assets", "icon.ico")
icon_datas = [(icon_path, "assets")]

a = Analysis(
    ["main.py"],
    pathex=[repo_root],
    binaries=[],
    datas=builds_datas + icon_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Diablo4Companion",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Diablo4Companion",
)
