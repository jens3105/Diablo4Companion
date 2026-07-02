from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


class EventCard(QWidget):

    def __init__(self, icon: str, title: str):
        super().__init__()

        self.setObjectName("card")
        self.setMinimumHeight(240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        self.title = QLabel(f"{icon} {title.upper()}")
        self.title.setAlignment(Qt.AlignCenter)

        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self.title.setFont(title_font)

        self.timer = QLabel("--:--:--")
        self.timer.setAlignment(Qt.AlignCenter)

        timer_font = QFont()
        timer_font.setPointSize(28)
        timer_font.setBold(True)
        self.timer.setFont(timer_font)

        self.subtitle = QLabel("Next Event")
        self.subtitle.setAlignment(Qt.AlignCenter)

        self.status = QLabel("Waiting for data...")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setWordWrap(True)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)

        layout.addWidget(self.title)
        layout.addStretch()
        layout.addWidget(self.timer)
        layout.addWidget(self.subtitle)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        layout.addStretch()

        self.setStyleSheet("""
            QWidget#card{
                background:#202020;
                border:2px solid #444;
                border-radius:12px;
            }

            QWidget#card:hover{
                border:2px solid #D4AF37;
            }

            QLabel{
                color:white;
                background:transparent;
            }

            QProgressBar{
                height:16px;
                border:none;
                background:#111;
                border-radius:8px;
            }

            QProgressBar::chunk{
                background:#8B0000;
                border-radius:8px;
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