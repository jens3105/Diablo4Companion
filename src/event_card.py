from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget


class EventCard(QWidget):

    def __init__(self, icon, title):
        super().__init__()

        layout = QVBoxLayout(self)

        self.title = QLabel(f"{icon} {title}")
        self.title.setAlignment(Qt.AlignCenter)

        self.timer = QLabel("00:00:00")
        self.timer.setAlignment(Qt.AlignCenter)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        self.status = QLabel("Venter på data...")
        self.status.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.title)
        layout.addWidget(self.timer)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)

        self.setStyleSheet("""
            QWidget{
                background:#222;
                border:1px solid #444;
                border-radius:10px;
            }

            QLabel{
                color:white;
                border:none;
            }

            QProgressBar{
                height:18px;
                border-radius:6px;
                text-align:center;
            }

            QProgressBar::chunk{
                background:#8b0000;
                border-radius:6px;
            }
        """)

    def set_title(self, text):
        self.title.setText(text)

    def set_timer(self, text):
        self.timer.setText(text)

    def set_status(self, text):
        self.status.setText(text)

    def set_progress(self, value):
        self.progress.setValue(value)