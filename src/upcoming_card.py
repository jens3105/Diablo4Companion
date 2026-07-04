from datetime import datetime, timezone

from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QGridLayout,
)


class UpcomingCard(QWidget):

    def __init__(self):
        super().__init__()

        self.setObjectName("card")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(12)

        title = QLabel("📅 UPCOMING EVENTS")
        title.setStyleSheet("""
            font-size:18px;
            font-weight:bold;
            color:#d9b36c;
        """)

        outer.addWidget(title)

        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(15)
        self.grid.setVerticalSpacing(8)

        outer.addLayout(self.grid)
        outer.addStretch()

        headers = ["Event", "Starts In", "Time"]

        for col, text in enumerate(headers):

            lbl = QLabel(text)

            lbl.setStyleSheet("""
                font-weight:bold;
                color:#d9b36c;
                font-size:13px;
            """)

            self.grid.addWidget(lbl, 0, col)

        self.rows = []

        for row in range(5):

            event = QLabel("-")
            timer = QLabel("--:--")
            clock = QLabel("--:--")

            event.setStyleSheet("font-size:13px;")
            timer.setStyleSheet("""
                font-family:Consolas;
                font-size:13px;
            """)
            clock.setStyleSheet("""
                font-family:Consolas;
                font-size:13px;
            """)

            self.grid.addWidget(event, row + 1, 0)
            self.grid.addWidget(timer, row + 1, 1)
            self.grid.addWidget(clock, row + 1, 2)

            self.rows.append((event, timer, clock))

        self.events = []

        self.setStyleSheet("""
            QWidget#card{
                background:#1d1f24;
                border:1px solid #353535;
                border-radius:14px;
            }

            QLabel{
                color:white;
            }
        """)

    def set_events(self, events):

        self.events = events
        self.refresh()

    def refresh(self):

        now = datetime.now(timezone.utc)

        for i, widgets in enumerate(self.rows):

            event_lbl, timer_lbl, clock_lbl = widgets

            if i >= len(self.events):

                event_lbl.setText("")
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

            event_lbl.setText(
                f"{event['icon']} {event['title']}"
            )

            timer_lbl.setText(countdown)

            clock_lbl.setText(
                start.strftime("%H:%M")
            )