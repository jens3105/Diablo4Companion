from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QWidget, QGridLayout

from src.event_card import EventCard


class DashboardWidget(QWidget):
    """Responsive dashboard."""

    def __init__(self):
        super().__init__()

        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(15)

        self.world_boss_card = EventCard("🌍", "World Boss")
        self.helltide_card = EventCard("🔥", "Helltide")
        self.legion_card = EventCard("👹", "Legion Event")
        self.whisper_card = EventCard("🌳", "Tree of Whispers")

        self.cards = [
            self.world_boss_card,
            self.helltide_card,
            self.legion_card,
            self.whisper_card,
        ]

        self._current_columns = None

        self.installEventFilter(self)

        self.update_layout()

    def eventFilter(self, obj, event):
        if obj == self and event.type() == QEvent.Resize:
            self.update_layout()

        return super().eventFilter(obj, event)

    def update_layout(self):
        width = self.width()

        columns = 2 if width >= 900 else 1

        if columns == self._current_columns:
            return

        self._current_columns = columns

        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        if columns == 2:
            self.layout.addWidget(self.world_boss_card, 0, 0)
            self.layout.addWidget(self.helltide_card, 0, 1)
            self.layout.addWidget(self.legion_card, 1, 0)
            self.layout.addWidget(self.whisper_card, 1, 1)

            self.layout.setColumnStretch(0, 1)
            self.layout.setColumnStretch(1, 1)

        else:
            for row, card in enumerate(self.cards):
                self.layout.addWidget(card, row, 0)

            self.layout.setColumnStretch(0, 1)