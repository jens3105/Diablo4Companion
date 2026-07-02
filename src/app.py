from datetime import datetime, timezone

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QListWidget,
    QHBoxLayout,
    QVBoxLayout,
    QMainWindow,
)

from src.api import DiabloAPI
from src.event_card import EventCard


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Diablo IV Companion")
        self.resize(1100, 700)

        self.api = DiabloAPI()
        self.current_boss = None

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)

        menu = QListWidget()
        menu.setFixedWidth(220)
        menu.addItem("🏠 Dashboard")
        menu.addItem("🔥 Helltide")
        menu.addItem("🌍 World Boss")
        menu.addItem("👹 Legion")
        menu.addItem("⚙ Settings")

        right_layout = QVBoxLayout()

        title = QLabel("Diablo IV Companion")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size:28px;
            font-weight:bold;
            color:#d9b36c;
        """)

        self.helltide_card = EventCard("🔥", "Helltide")
        self.world_boss_card = EventCard("🌍", "World Boss")
        self.legion_card = EventCard("👹", "Legion Event")

        right_layout.addWidget(title)
        right_layout.addWidget(self.helltide_card)
        right_layout.addWidget(self.world_boss_card)
        right_layout.addWidget(self.legion_card)

        main_layout.addWidget(menu)
        main_layout.addLayout(right_layout)

        self.setStyleSheet("""
            QMainWindow{
                background:#121212;
            }

            QListWidget{
                background:#1b1b1b;
                color:white;
                border:none;
                font-size:16px;
            }

            QListWidget::item{
                padding:12px;
            }

            QListWidget::item:selected{
                background:#8b0000;
                border-radius:6px;
            }

            QLabel{
                color:white;
            }
        """)

        self.load_world_boss()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_countdown)
        self.timer.start(1000)

    def load_world_boss(self):

        self.current_boss = self.api.get_next_world_boss()

        if not self.current_boss:
            return

        self.world_boss_card.set_title(
            f"🌍 {self.current_boss['boss']}"
        )

        zone = self.current_boss["zone"][0]["name"]
        self.world_boss_card.set_status(f"📍 {zone}")

    def update_countdown(self):

        if not self.current_boss:
            return

        start = datetime.fromisoformat(
            self.current_boss["startTime"].replace("Z", "+00:00")
        )

        now = datetime.now(timezone.utc)

        seconds = int((start - now).total_seconds())

        if seconds <= 0:
            self.load_world_boss()
            return

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        countdown = f"{hours:02}:{minutes:02}:{secs:02}"

        self.world_boss_card.set_timer(countdown)

        # World Boss spawner ca. hver 3½ time (12600 sekunder)
        progress = int((1 - seconds / 12600) * 100)

        progress = max(0, min(progress, 100))

        self.world_boss_card.set_progress(progress)