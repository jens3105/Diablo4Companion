from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QLabel, QSizePolicy

from qfluentwidgets import BodyLabel, CaptionLabel, ProgressBar
from qfluentwidgets.common.icon import FluentIconBase

from src.base_card import BaseCard
from src.theme import ACCENT_GOLD, ACCENT_RED, TEXT_MUTED


class EventCard(BaseCard):
    """A single countdown tile: World Boss / Helltide / Legion / Season."""

    def __init__(self, icon: FluentIconBase, title: str, parent=None):
        super().__init__(title.upper(), icon=icon, parent=parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(220, 190)

        self.center_title()

        self.content_layout.addStretch(1)

        # -------------------------
        # Subtitle
        # -------------------------

        self.subtitle = CaptionLabel("Next Event", self.content)
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.subtitle.setTextColor(QColor(TEXT_MUTED), QColor(TEXT_MUTED))
        self.content_layout.addWidget(self.subtitle)

        # -------------------------
        # Big countdown
        # -------------------------

        self.timer_label = QLabel("--:--:--", self.content)
        self.timer_label.setAlignment(Qt.AlignCenter)

        timer_font = QFont("Consolas", 26)
        timer_font.setBold(True)
        self.timer_label.setFont(timer_font)
        self.timer_label.setStyleSheet(f"color: {ACCENT_GOLD}; background: transparent;")

        self.content_layout.addWidget(self.timer_label)

        # -------------------------
        # Status
        # -------------------------

        self.status = BodyLabel("Waiting for data...", self.content)
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setWordWrap(True)

        self.content_layout.addWidget(self.status)

        self.content_layout.addStretch(1)

        # -------------------------
        # Progress
        # -------------------------

        self.progress = ProgressBar(self.content)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(6)
        self.progress.setCustomBarColor(QColor(ACCENT_RED), QColor("#c0392b"))

        self.content_layout.addWidget(self.progress)

        self.progress_caption = CaptionLabel("0%", self.content)
        self.progress_caption.setAlignment(Qt.AlignCenter)
        self.progress_caption.setTextColor(QColor(TEXT_MUTED), QColor(TEXT_MUTED))

        self.content_layout.addWidget(self.progress_caption)

    # ---------------------------------------------------------
    # Public API (unchanged from the pre-redesign EventCard)
    # ---------------------------------------------------------

    def set_title(self, text):
        self.title_label.setText(text.upper())

    def set_timer(self, text):
        self.timer_label.setText(text)

    def set_status(self, text):
        self.status.setText(text)

    def set_progress(self, value):
        value = max(0, min(int(value), 100))
        self.progress.setValue(value)
        self.progress_caption.setText(f"{value}%")

    def set_subtitle(self, text):
        self.subtitle.setText(text)
