from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QWidget, QGridLayout

from src.event_card import EventCard
from src.upcoming_card import UpcomingCard


class DashboardWidget(QWidget):
    """Dashboard v3"""

    def __init__(self):
        super().__init__()

        self.grid = QGridLayout(self)

        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(20)
        self.grid.setVerticalSpacing(20)

        # Dashboard cards
        self.world_boss_card = EventCard("🌍", "World Boss")
        self.helltide_card = EventCard("🔥", "Helltide")
        self.legion_card = EventCard("👹", "Legion")

        # New Upcoming Events card
        self.upcoming_card = UpcomingCard()

        self.installEventFilter(self)

        self.current_mode = None

        self.rebuild()

    def eventFilter(self, obj, event):

        if obj == self and event.type() == QEvent.Resize:
            self.rebuild()

        return super().eventFilter(obj, event)

    def rebuild(self):

        width = self.width()

        # ---------- Responsive ----------

        if width >= 1700:
            mode = 3
        elif width >= 900:
            mode = 2
        else:
            mode = 1

        if mode == self.current_mode:
            return

        self.current_mode = mode

        while self.grid.count():
            item = self.grid.takeAt(0)

            if item.widget():
                item.widget().setParent(None)

        # ===================================================
        # Large screens (27")
        # ===================================================

        if mode == 3:

            self.grid.addWidget(self.world_boss_card, 0, 0)
            self.grid.addWidget(self.helltide_card, 0, 1)

            self.grid.addWidget(self.legion_card, 1, 0)
            self.grid.addWidget(self.upcoming_card, 1, 1)

            self.grid.setColumnStretch(0, 1)
            self.grid.setColumnStretch(1, 1)

            self.grid.setRowStretch(0, 1)
            self.grid.setRowStretch(1, 1)

        # ===================================================
        # Laptop
        # ===================================================

        elif mode == 2:

            self.grid.addWidget(self.world_boss_card, 0, 0)
            self.grid.addWidget(self.helltide_card, 0, 1)

            self.grid.addWidget(self.legion_card, 1, 0)
            self.grid.addWidget(self.upcoming_card, 1, 1)

            self.grid.setColumnStretch(0, 1)
            self.grid.setColumnStretch(1, 1)

        # ===================================================
        # Small window
        # ===================================================

        else:

            self.grid.addWidget(self.world_boss_card, 0, 0)
            self.grid.addWidget(self.helltide_card, 1, 0)
            self.grid.addWidget(self.legion_card, 2, 0)
            self.grid.addWidget(self.upcoming_card, 3, 0)

            self.grid.setColumnStretch(0, 1)