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
from src.base_card import BaseCard, ClickableBodyLabel, ClickableStrongBodyLabel


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
    # Emits the pending action's category
    # ("leveling"/"skill"/"paragon"/"paragon_node"/"gear") when the NEXT
    # ACTION line is clicked, so MainWindow can jump to the right
    # page/tab (Build Guide's Leveling, Skills or Paragon tab, the
    # dedicated Paragon page, or the Character page) - see
    # MainWindow._navigate_to_next_action. Never emitted when there's
    # nothing to act on (no build, or "Build complete!") - see
    # set_build's ``next_action_kind``.
    next_action_clicked = Signal(str)
    # Phase 13: the compact Paragon block's own click, always active
    # while a summary is shown - jumps straight to the dedicated Paragon
    # page, separate from the whole-card ``clicked`` (-> Build Guide) and
    # the NEXT ACTION line (-> whichever category is next overall).
    paragon_clicked = Signal()

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

        self.next_action_label = ClickableBodyLabel("—", self.content)
        self.next_action_label.setWordWrap(True)
        self.next_action_label.clicked.connect(self._on_next_action_clicked)
        self.content_layout.addWidget(self.next_action_label)

        # Phase 13: compact Paragon block - overall %, the board still
        # in progress, and the next Paragon-specific action (which may
        # differ from the card-wide NEXT ACTION above if Leveling/Skills/
        # Gear currently has a higher-priority pending action). Hidden
        # entirely for builds with no verified Paragon board data (see
        # ``set_paragon_summary``).
        self.content_layout.addSpacing(8)

        self.paragon_header = CaptionLabel("PARAGON", self.content)
        self.paragon_header.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.content_layout.addWidget(self.paragon_header)

        self.paragon_summary_label = ClickableStrongBodyLabel("", self.content)
        self.paragon_summary_label.setWordWrap(True)
        self.paragon_summary_label.clicked.connect(self.paragon_clicked)
        self.content_layout.addWidget(self.paragon_summary_label)

        self.paragon_header.hide()
        self.paragon_summary_label.hide()

        self.content_layout.addStretch(1)

        self._next_action_kind = None

    def set_build(
        self,
        build_name: str,
        level: int,
        status_rows: list[tuple[str, str, str]],
        next_action_text: str,
        next_action_kind: str | None = None,
    ):
        """Populate the card. ``status_rows`` is the same ``(emoji,
        label, pct_text)`` list ``LevelingCard.set_build_status`` takes -
        only the emoji + label are shown here, kept to one short line per
        category so the card stays compact next to the event cards.

        ``next_action_kind`` is one of ``"leveling"``/``"skill"``/
        ``"paragon"``/``"gear"`` (from ``MainWindow._advisor_next_
        action``) or ``None`` when there's nothing to act on - it decides
        whether the NEXT ACTION line is click-to-navigate right now."""

        if not build_name:
            self.build_name_label.setText("No build selected")
            self.level_label.setText("")
            self.status_rows_label.setText("")
            self.next_action_label.setText("—")
            self._next_action_kind = None
            self.next_action_label.set_active(False)
            return

        self.build_name_label.setText(build_name)
        self.level_label.setText(f"Level {level}")

        lines = [f"{emoji} {label}" for emoji, label, _pct in status_rows]
        self.status_rows_label.setText("\n".join(lines))

        self.next_action_label.setText(next_action_text or "—")
        self._next_action_kind = next_action_kind
        self.next_action_label.set_active(next_action_kind is not None)

    def set_paragon_summary(self, summary: tuple[str, str, str] | None):
        """Phase 13: the compact Paragon block - ``summary`` is
        ``(pct_text, current_board_label, next_paragon_action_text)``
        from ``MainWindow._paragon_dashboard_summary``, or ``None`` for
        builds with no verified Paragon board data (Heartseeker Rogue) or
        no build selected at all, which hides the block entirely rather
        than showing a misleading "0%"."""

        if not summary:
            self.paragon_header.hide()
            self.paragon_summary_label.hide()
            self.paragon_summary_label.set_active(False)
            return

        pct_text, current_board_label, next_text = summary
        self.paragon_summary_label.setText(
            f"{pct_text}  •  {current_board_label}\nNext: {next_text}"
        )
        self.paragon_header.show()
        self.paragon_summary_label.show()
        self.paragon_summary_label.set_active(True)

    def _on_next_action_clicked(self):
        if self._next_action_kind is not None:
            self.next_action_clicked.emit(self._next_action_kind)

    def refresh_theme(self):
        super().refresh_theme()

        self.level_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.status_header.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.status_rows_label.setStyleSheet(
            f"font-family: monospace; font-size: 12px; color: {theme.TEXT_PRIMARY};"
        )
        self.next_header.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.paragon_header.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
