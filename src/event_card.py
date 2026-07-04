from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class EventCard(QWidget):

    def __init__(self, icon: str, title: str):
        super().__init__()

        self.setObjectName("card")

        # Kortet skal fylde den plads det får
        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        self.setMinimumWidth(240)
        self.setMinimumHeight(180)

        layout = QVBoxLayout(self)

        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(12)

        # -------------------------
        # Titel
        # -------------------------

        self.title = QLabel(f"{icon} {title.upper()}")
        self.title.setAlignment(Qt.AlignCenter)

        title_font = QFont("Segoe UI", 16)
        title_font.setBold(True)

        self.title.setFont(title_font)

        # -------------------------
        # Countdown
        # -------------------------

        self.timer = QLabel("--:--:--")
        self.timer.setAlignment(Qt.AlignCenter)

        timer_font = QFont("Consolas", 28)
        timer_font.setBold(True)

        self.timer.setFont(timer_font)

        # -------------------------
        # Subtitle
        # -------------------------

        self.subtitle = QLabel("Next Event")
        self.subtitle.setAlignment(Qt.AlignCenter)

        subtitle_font = QFont("Segoe UI", 11)

        self.subtitle.setFont(subtitle_font)

        # -------------------------
        # Status
        # -------------------------

        self.status = QLabel("Waiting for data...")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setWordWrap(True)

        status_font = QFont("Segoe UI", 10)

        self.status.setFont(status_font)

        # -------------------------
        # Progress
        # -------------------------

        self.progress = QProgressBar()

        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(14)

        # -------------------------
        # Layout
        # -------------------------

        layout.addWidget(self.title)

        layout.addStretch()

        layout.addWidget(self.timer)

        layout.addWidget(self.subtitle)

        layout.addWidget(self.status)

        layout.addStretch()

        layout.addWidget(self.progress)

        # -------------------------
        # Style
        # -------------------------

        self.setStyleSheet("""
            QWidget#card{
                background:#1d1f24;
                border:1px solid #353535;
                border-radius:14px;
            }

            QWidget#card:hover{
                border:2px solid #D4AF37;
            }

            QLabel{
                color:white;
                background:transparent;
            }

            QProgressBar{
                background:#111;
                border:none;
                border-radius:7px;
            }

            QProgressBar::chunk{
                background:#8B0000;
                border-radius:7px;
            }
        """)

    def set_title(self, text):
        self.title.setText(text.upper())

    def set_timer(self, text):
        self.timer.setText(text)

    def set_status(self, text):
        self.status.setText(text)

    def set_progress(self, value):
        self.progress.setValue(value)

    def set_subtitle(self, text):
        self.subtitle.setText(text)