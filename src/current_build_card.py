from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QSizePolicy

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon as FIF,
    PushButton,
    StrongBodyLabel,
)

from src import theme
from src.base_card import BaseCard


class CurrentBuildCard(BaseCard):
    """Dashboard tile (Phase 7) surfacing the Build Guide's current
    build/level, its Build Status rollup, and one concrete next action -
    a compact read-out of state MainWindow already computes for the
    Build Guide page (``MainWindow._compute_build_status`` /
    ``_load_completed_levels``), not a new tracker of its own. Click
    anywhere on the card to jump to the Build Guide page (wired by
    MainWindow via the inherited ``clicked`` signal).

    Phase 9 adds the "Compact Mode" button (top-right of the card) that
    opens the small always-on-top companion window - a separate signal
    so it doesn't fight with the card-wide ``clicked`` navigation."""

    compact_mode_requested = Signal()

    def __init__(self, parent=None):
        super().__init__("CURRENT BUILD", icon=FIF.GAME, parent=parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(220, 190)

        # Native CardWidget hover/press affordance + hand cursor, so the
        # card visibly reads as clickable before the user tries it.
        self.setClickEnabled(True)
        self.setCursor(Qt.PointingHandCursor)

        # Sits in the title row (added by BaseCard) rather than the
        # content area, so it reads as a card-level action, not part of
        # the build info itself. QPushButton consumes its own clicks, so
        # pressing it never also triggers the card's navigate-away
        # ``clicked``.
        self.compact_mode_button = PushButton("Compact Mode", self)
        self.compact_mode_button.setFixedHeight(24)
        self.compact_mode_button.clicked.connect(self.compact_mode_requested)
        self.title_row.addStretch(1)
        self.title_row.addWidget(self.compact_mode_button)

        self.build_name_label = StrongBodyLabel("No build selected", self.content)
        self.build_name_label.setWordWrap(True)
        self.content_layout.addWidget(self.build_name_label)

        self.level_label = CaptionLabel("", self.content)
        self.level_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.content_layout.addWidget(self.level_label)

        self.content_layout.addSpacing(8)

        self.status_header = CaptionLabel("BUILD STATUS", self.content)
        self.status_header.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.content_layout.addWidget(self.status_header)

        self.status_rows_label = BodyLabel("", self.content)
        self.status_rows_label.setWordWrap(True)
        self.status_rows_label.setStyleSheet(
            f"font-family: monospace; font-size: 12px; color: {theme.TEXT_PRIMARY};"
        )
        self.content_layout.addWidget(self.status_rows_label)

        self.content_layout.addSpacing(8)

        self.next_header = CaptionLabel("NEXT ACTION", self.content)
        self.next_header.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.content_layout.addWidget(self.next_header)

        self.next_action_label = BodyLabel("—", self.content)
        self.next_action_label.setWordWrap(True)
        self.content_layout.addWidget(self.next_action_label)

        self.content_layout.addStretch(1)

    def set_build(self, build_name: str, level: int, status_rows: list[tuple[str, str, str]], next_action_text: str):
        """Populate the card. ``status_rows`` is the same ``(emoji,
        label, pct_text)`` list ``LevelingCard.set_build_status`` takes -
        only the emoji + label are shown here, kept to one short line per
        category so the card stays compact next to the event cards."""

        if not build_name:
            self.build_name_label.setText("No build selected")
            self.level_label.setText("")
            self.status_rows_label.setText("")
            self.next_action_label.setText("—")
            return

        self.build_name_label.setText(build_name)
        self.level_label.setText(f"Level {level}")

        lines = [f"{emoji} {label}" for emoji, label, _pct in status_rows]
        self.status_rows_label.setText("\n".join(lines))

        self.next_action_label.setText(next_action_text or "—")

    def refresh_theme(self):
        super().refresh_theme()

        self.level_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.status_header.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.status_rows_label.setStyleSheet(
            f"font-family: monospace; font-size: 12px; color: {theme.TEXT_PRIMARY};"
        )
        self.next_header.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
