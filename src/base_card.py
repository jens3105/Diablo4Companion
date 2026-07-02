from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class BaseCard(QFrame):
    """Base class for all dashboard cards."""

    def __init__(self, title: str):
        super().__init__()

        self.setObjectName("card")
        self.setMinimumSize(300, 220)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)

        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignLeft)
        self.title_label.setObjectName("cardTitle")

        self.main_layout.addWidget(self.title_label)

        self.content = QWidget()

        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)

        self.main_layout.addWidget(self.content, 1)

        self.setStyleSheet("""
            QFrame#card {
                background-color: #252525;
                border: 1px solid #3d3d3d;
                border-radius: 12px;
            }

            QFrame#card:hover {
                border: 1px solid #d8a24a;
            }

            QLabel#cardTitle {
                color: #d8a24a;
                font-size: 18px;
                font-weight: bold;
            }

            QLabel {
                color: white;
                font-size: 14px;
            }
        """)

    def add_widget(self, widget: QWidget):
        self.content_layout.addWidget(widget)

    def add_spacing(self, amount: int = 10):
        self.content_layout.addSpacing(amount)

    def add_stretch(self):
        self.content_layout.addStretch()