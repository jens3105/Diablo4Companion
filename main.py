import os
import sys

from PySide6.QtCore import QSettings
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from src.app import MainWindow
from src.api import DiabloAPI
from src.theme import MODE_DARK, PRESET_DEFAULT, apply_theme


def _resolve_icon_path() -> str:
    """Same sys.frozen pattern as LevelingManager's builds_dir lookup
    (src/managers/leveling_manager.py) - PyInstaller's onedir layout
    places bundled datas under a "_internal" folder beside the exe,
    while running from source resolves relative to this file (main.py
    already lives at the repo root)."""

    if getattr(sys, "frozen", False):
        base_dir = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "_internal")
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_dir, "assets", "icon.ico")


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(_resolve_icon_path()))

    # Restore the last-saved dark/light mode + seasonal accent preset (same
    # QSettings the rest of the app uses - see MainWindow.settings) before
    # any window is built, so the very first paint already has the right
    # colors instead of flashing the default theme first.
    settings = QSettings("Diablo4Companion", "DesktopCompanion")
    saved_mode = settings.value("appearance/theme", MODE_DARK, type=str)
    saved_preset = settings.value("appearance/accent_preset", PRESET_DEFAULT, type=str)
    apply_theme(saved_mode, saved_preset)

    api = DiabloAPI()

    try:
        boss = api.get_next_world_boss()
    except Exception as exc:
        print(f"Kunne ikke hente world boss-data ved opstart: {exc}")
        boss = None

    print("\n===== NÆSTE WORLD BOSS =====")

    if boss:
        print(f"Boss : {boss['boss']}")
        print(f"Tid  : {boss['startTime']}")
        print(f"Zone : {boss['zone'][0]['name']}")
    else:
        print("Ingen boss fundet")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()