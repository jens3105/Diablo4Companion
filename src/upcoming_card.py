from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGridLayout, QSizePolicy

from qfluentwidgets import CaptionLabel, FluentIcon as FIF

from src import theme
from src.base_card import BaseCard

# Dashboard Data bugfix: widened from 5 to 8 rows (real events the API
# actually delivers - never fabricated) and switched every row cell to
# CaptionLabel (smaller line-height than the previous BodyLabel) with
# tighter grid spacing, so showing more real events still takes up
# LESS vertical space overall than the old 5-row/BodyLabel layout.
ROW_COUNT = 8

_MISSING = "DATA UNAVAILABLE"


class UpcomingCard(BaseCard):

    def __init__(self, parent=None):
        super().__init__("UPCOMING EVENTS", icon=FIF.HISTORY, parent=parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(260, 190)

        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(3)

        self.add_layout(self.grid)

        # Location only ever has a real value for World Boss events
        # (the live schedule provides no location for Legion/Helltide -
        # see src/api.py's get_upcoming_events docstring) - shown as its
        # own column, literally "DATA UNAVAILABLE" rather than blank,
        # so absence is never ambiguous with "not loaded yet".
        headers = ["Event", "Location", "Starts In", "Time"]

        self.header_labels = []

        for col, text in enumerate(headers):
            lbl = CaptionLabel(text, self.content)
            lbl.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
            self.grid.addWidget(lbl, 0, col)
            self.header_labels.append(lbl)

        self.rows = []

        for row in range(ROW_COUNT):
            event = CaptionLabel("-", self.content)
            location = CaptionLabel("-", self.content)
            timer = CaptionLabel("--:--", self.content)
            clock = CaptionLabel("--:--", self.content)

            location.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
            timer.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
            clock.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))

            self.grid.addWidget(event, row + 1, 0)
            self.grid.addWidget(location, row + 1, 1)
            self.grid.addWidget(timer, row + 1, 2)
            self.grid.addWidget(clock, row + 1, 3)

            self.rows.append((event, location, timer, clock))

        self.grid.setColumnStretch(0, 3)
        self.grid.setColumnStretch(1, 2)
        self.grid.setColumnStretch(2, 1)
        self.grid.setColumnStretch(3, 1)

        self.empty_label = CaptionLabel("No data available right now.", self.content)
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.empty_label.hide()
        self.add_widget(self.empty_label)

        self.add_stretch()

        self.events = []

    def set_events(self, events):

        self.events = events
        self.refresh()

    def refresh(self):

        self.empty_label.setVisible(len(self.events) == 0)

        now = datetime.now(timezone.utc)

        for i, widgets in enumerate(self.rows):

            event_lbl, location_lbl, timer_lbl, clock_lbl = widgets

            if i >= len(self.events):
                event_lbl.setText("")
                location_lbl.setText("")
                timer_lbl.setText("")
                clock_lbl.setText("")
                continue

            event = self.events[i]

            remaining = int(event["timestamp"] - now.timestamp())

            if remaining < 0:
                remaining = 0

            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            seconds = remaining % 60

            if hours:
                countdown = f"{hours:02}:{minutes:02}:{seconds:02}"
            else:
                countdown = f"{minutes:02}:{seconds:02}"

            start = datetime.fromtimestamp(
                event["timestamp"],
                timezone.utc
            ).astimezone()

            suffix = " (est.)" if event.get("estimated") else ""
            event_lbl.setText(f"{event['icon']} {event['title']}{suffix}")
            location_lbl.setText(event.get("location") or _MISSING)
            timer_lbl.setText(countdown)
            clock_lbl.setText(start.strftime("%H:%M"))

    def refresh_theme(self):
        super().refresh_theme()

        for lbl in self.header_labels:
            lbl.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))

        for _event, location_lbl, timer_lbl, clock_lbl in self.rows:
            location_lbl.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
            timer_lbl.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
            clock_lbl.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))

        self.empty_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
