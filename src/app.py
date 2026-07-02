from datetime import datetime, timezone

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QListWidget,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QMainWindow,
)

from src.api import DiabloAPI
from src.event_card import EventCard


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Diablo IV Companion")
        self.resize(1200, 750)

        self.api = DiabloAPI()
        self.current_boss = None

        central = QWidget()
        self.setCentralWidget(central)

        # ==========================
        # Main Layout
        # ==========================
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # ==========================
        # Sidebar
        # ==========================
        menu = QListWidget()
        menu.setFixedWidth(220)

        menu.addItem("🏠 Dashboard")
        menu.addItem("🔥 Helltide")
        menu.addItem("🌍 World Boss")
        menu.addItem("👹 Legion")
        menu.addItem("⚙ Settings")

        main_layout.addWidget(menu)

        # ==========================
        # Right Side
        # ==========================
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        title = QLabel("Diablo IV Companion")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size:30px;
            font-weight:bold;
            color:#d9b36c;
            margin-bottom:10px;
        """)

        right_layout.addWidget(title)

        # ==========================
        # Dashboard Grid
        # ==========================
        dashboard = QWidget()
        grid = QGridLayout(dashboard)

        grid.setSpacing(15)
        grid.setContentsMargins(0, 0, 0, 0)

        self.helltide_card = EventCard("🔥", "Helltide")
        self.world_boss_card = EventCard("🌍", "World Boss")
        self.legion_card = EventCard("👹", "Legion Event")
        self.whisper_card = EventCard("🌳", "Tree of Whispers")

        grid.addWidget(self.world_boss_card, 0, 0)
        grid.addWidget(self.helltide_card, 0, 1)
        grid.addWidget(self.legion_card, 1, 0)
        grid.addWidget(self.whisper_card, 1, 1)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)

        right_layout.addWidget(dashboard)

        main_layout.addWidget(right_widget, 1)

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
        self.world_boss_card.set_subtitle("Next Spawn")

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

        progress = int((1 - seconds / 12600) * 100)
        progress = max(0, min(progress, 100))

        self.world_boss_card.set_progress(progress)