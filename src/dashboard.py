from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QGridLayout, QVBoxLayout, QWidget

from qfluentwidgets import FluentIcon as FIF, SingleDirectionScrollArea

from src.event_card import EventCard
from src.upcoming_card import UpcomingCard


class DashboardWidget(QWidget):
    """Overview page: world boss / helltide / legion / season timers plus
    the upcoming-events table. Wrapped in a vertical scroll area so the
    grid can never force the main window taller than the screen, even on
    small displays - it just becomes scrollable instead of cut off."""

    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = SingleDirectionScrollArea(self, orient=Qt.Vertical)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background: transparent; border: none;}")

        outer.addWidget(scroll)

        self.grid_host = QWidget()
        self.grid_host.setStyleSheet("background: transparent;")
        scroll.setWidget(self.grid_host)

        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(4, 4, 4, 4)
        self.grid.setHorizontalSpacing(18)
        self.grid.setVerticalSpacing(18)

        # Dashboard cards
        self.world_boss_card = EventCard(FIF.GLOBE, "World Boss")
        self.helltide_card = EventCard(FIF.FLAG, "Helltide")
        self.legion_card = EventCard(FIF.PEOPLE, "Legion")
        self.season_card = EventCard(FIF.CALENDAR, "Season 15")
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

        # ---------- Responsive breakpoints ----------

        if width >= 1300:
            mode = 3
        elif width >= 820:
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

        for col in range(3):
            self.grid.setColumnStretch(col, 0)

        for row in range(3):
            self.grid.setRowStretch(row, 0)

        # ===================================================
        # Wide window (desktop monitor)
        # ===================================================

        if mode == 3:

            self.grid.addWidget(self.world_boss_card, 0, 0)
            self.grid.addWidget(self.helltide_card, 0, 1)
            self.grid.addWidget(self.legion_card, 0, 2)

            self.grid.addWidget(self.season_card, 1, 0)
            self.grid.addWidget(self.upcoming_card, 1, 1, 1, 2)

            for col in range(3):
                self.grid.setColumnStretch(col, 1)

            self.grid.setRowStretch(0, 1)
            self.grid.setRowStretch(1, 1)

        # ===================================================
        # Medium window (laptop)
        # ===================================================

        elif mode == 2:

            self.grid.addWidget(self.world_boss_card, 0, 0)
            self.grid.addWidget(self.helltide_card, 0, 1)

            self.grid.addWidget(self.legion_card, 1, 0)
            self.grid.addWidget(self.season_card, 1, 1)

            self.grid.addWidget(self.upcoming_card, 2, 0, 1, 2)

            self.grid.setColumnStretch(0, 1)
            self.grid.setColumnStretch(1, 1)

        # ===================================================
        # Narrow window
        # ===================================================

        else:

            self.grid.addWidget(self.world_boss_card, 0, 0)
            self.grid.addWidget(self.helltide_card, 1, 0)
            self.grid.addWidget(self.legion_card, 2, 0)
            self.grid.addWidget(self.season_card, 3, 0)
            self.grid.addWidget(self.upcoming_card, 4, 0)

            self.grid.setColumnStretch(0, 1)
