import sys

from PySide6.QtWidgets import QApplication

from src.app import MainWindow
from src.api import DiabloAPI
from src.theme import apply_theme


def main():
    app = QApplication(sys.argv)

    apply_theme()

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