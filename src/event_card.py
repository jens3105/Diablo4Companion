from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


class EventCard(QWidget):

    def __init__(self, icon: str, title: str):
        super().__init__()

        self.setMinimumHeight(220)
        self.setObjectName("eventCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        self.title = QLabel(f"{icon} {title}")
        self.title.setObjectName("title")
        self.title.setAlignment(Qt.AlignCenter)

        self.timer = QLabel("--:--:--")
        self.timer.setObjectName("timer")
        self.timer.setAlignment(Qt.AlignCenter)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)

        self.status = QLabel("Waiting for data...")
        self.status.setObjectName("status")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setWordWrap(True)

        layout.addWidget(self.title)
        layout.addStretch()

        layout.addWidget(self.timer)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)

        layout.addStretch()

        self.setStyleSheet("""
            QWidget#eventCard{
                background-color:#202020;
                border:1px solid #3c3c3c;
                border-radius:12px;
            }

            QWidget#eventCard:hover{
                border:2px solid #d9b36c;
            }

            QLabel#title{
                color:#d9b36c;
                font-size:20px;
                font-weight:bold;
            }

            QLabel#timer{
                color:white;
                font-size:34px;
                font-weight:bold;
            }

            QLabel#status{
                color:#cfcfcf;
                font-size:14px;
            }

            QProgressBar{
                border:none;
                background:#111111;
                border-radius:6px;
                height:16px;
            }

            QProgressBar::chunk{
                background:#8b0000;
                border-radius:6px;
            }
        """)

    def set_title(self, text: str):
        self.title.setText(text)

    def set_timer(self, text: str):
        self.timer.setText(text)

    def set_status(self, text: str):
        self.status.setText(text)

    def set_progress(self, value: int):
        self.progress.setValue(value)