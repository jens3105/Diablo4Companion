from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QWidget, QGridLayout

from src.event_card import EventCard


class DashboardWidget(QWidget):
    """Dashboard v3"""

    def __init__(self):
        super().__init__()

        self.grid = QGridLayout(self)

        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(20)
        self.grid.setVerticalSpacing(20)

        # Cards
        self.world_boss_card = EventCard("🌍", "World Boss")
        self.helltide_card = EventCard("🔥", "Helltide")
        self.legion_card = EventCard("👹", "Legion")

        self.cards = [
            self.world_boss_card,
            self.helltide_card,
            self.legion_card,
        ]

        self.installEventFilter(self)

        self.current_mode = None

        self.rebuild()

    def eventFilter(self, obj, event):

        if obj == self and event.type() == QEvent.Resize:
            self.rebuild()

        return super().eventFilter(obj, event)

    def rebuild(self):

        width = self.width()

        # 3 kolonner på stor skærm
        if width >= 1700:
            mode = 3

        # 2 kolonner
        elif width >= 900:
            mode = 2

        # Mobil / smalle vinduer
        else:
            mode = 1

        if mode == self.current_mode:
            return

        self.current_mode = mode

        while self.grid.count():
            item = self.grid.takeAt(0)

            if item.widget():
                item.widget().setParent(None)

        # ---------------------------------
        # 3 kolonner
        # ---------------------------------

        if mode == 3:

            self.grid.addWidget(self.world_boss_card, 0, 0)
            self.grid.addWidget(self.helltide_card, 0, 1)
            self.grid.addWidget(self.legion_card, 0, 2)

            self.grid.setColumnStretch(0, 1)
            self.grid.setColumnStretch(1, 1)
            self.grid.setColumnStretch(2, 1)

            self.grid.setRowStretch(0, 1)

        # ---------------------------------
        # 2 kolonner
        # ---------------------------------

        elif mode == 2:

            self.grid.addWidget(self.world_boss_card, 0, 0)
            self.grid.addWidget(self.helltide_card, 0, 1)
            self.grid.addWidget(self.legion_card, 1, 0, 1, 2)

            self.grid.setColumnStretch(0, 1)
            self.grid.setColumnStretch(1, 1)

        # ---------------------------------
        # 1 kolonne
        # ---------------------------------

        else:

            for row, card in enumerate(self.cards):
                self.grid.addWidget(card, row, 0)

            self.grid.setColumnStretch(0, 1)