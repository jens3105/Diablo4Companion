"""Build Advisor page: a dedicated top-level page surfacing, at a larger/
clearer size than the compact widgets it's built from, exactly what the
Build Guide's status widget and the Dashboard's Current Build card
already compute - ``MainWindow._compute_build_status`` for the Skills/
Leveling/Paragon/Gear percentage rollup, ``MainWindow._advisor_next_
action`` for the single unified next step, and ``MainWindow._pending_
skill_actions``/``_pending_paragon_actions``/``_pending_gear_actions``
for a short "what's missing" list per category.

No new validation logic lives here - this module is presentation only,
same as ``CurrentBuildCard``/``LevelingCard``'s Build Status widget."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon as FIF,
    StrongBodyLabel,
)

from src import theme
from src.base_card import BaseCard, ClickableStrongBodyLabel

# Display order + label for each pending-actions category - matches the
# Skills -> Paragon -> Gear priority order ``MainWindow._advisor_pending_
# actions`` already unifies them in.
_CATEGORIES = ["Skills", "Paragon", "Gear"]


class BuildAdvisorCard(BaseCard):
    """Bigger, standalone version of the Build Status + next-action
    read-out, plus a capped "what's missing" list per category."""

    # Emits the pending action's category ("skill"/"paragon"/"gear")
    # when the NEXT ACTION line is clicked, so MainWindow can jump to the
    # right page/tab - see MainWindow._navigate_to_next_action. Never
    # emitted when there's nothing to act on (no build, or "Build
    # complete!") - see set_advisor's ``next_action_kind``.
    next_action_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__("BUILD ADVISOR", icon=FIF.ROBOT, parent=parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(360, 360)

        self.header_label = StrongBodyLabel("No build selected", self.content)
        self.header_label.setWordWrap(True)
        self.add_widget(self.header_label)

        self.add_spacing(4)

        # -------------------------
        # Build Status - same rows as the compact widget, drawn bigger.
        # -------------------------

        self.status_header = CaptionLabel("BUILD STATUS", self.content)
        self.status_header.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.add_widget(self.status_header)

        self.status_rows_label = BodyLabel("", self.content)
        self.status_rows_label.setWordWrap(True)
        self.status_rows_label.setStyleSheet(
            f"font-family: monospace; font-size: 16px; color: {theme.TEXT_PRIMARY};"
        )
        self.add_widget(self.status_rows_label)

        self.status_footer_label = CaptionLabel("", self.content)
        self.add_widget(self.status_footer_label)

        self.add_spacing(10)

        # -------------------------
        # Next action - the single unified pointer.
        # -------------------------

        self.next_header = CaptionLabel("NEXT ACTION", self.content)
        self.next_header.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.add_widget(self.next_header)

        self.next_action_label = ClickableStrongBodyLabel("—", self.content)
        self.next_action_label.setWordWrap(True)
        self.next_action_label.clicked.connect(self._on_next_action_clicked)
        self.add_widget(self.next_action_label)

        self._next_action_kind = None

        self.add_spacing(14)

        # -------------------------
        # What's missing - one capped list per category.
        # -------------------------

        missing_header = CaptionLabel("WHAT'S MISSING", self.content)
        missing_header.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.add_widget(missing_header)
        self._missing_header = missing_header

        self._category_headers = {}
        self._category_labels = {}

        for category in _CATEGORIES:
            row = QHBoxLayout()
            row.setSpacing(8)

            cat_header = CaptionLabel(category.upper(), self.content)
            cat_header.setFixedWidth(70)
            cat_header.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
            # Top-align with the first line of the (possibly multi-line)
            # list next to it, instead of the QHBoxLayout's default of
            # stretching this label to the row's full height and then
            # vertically centering its text within that - which looks off
            # once the list grows past one line.
            row.addWidget(cat_header, 0, Qt.AlignTop)

            cat_label = BodyLabel("—", self.content)
            cat_label.setWordWrap(True)
            row.addWidget(cat_label, 1)

            self.add_layout(row)

            self._category_headers[category] = cat_header
            self._category_labels[category] = cat_label

        self.add_stretch()

    # ---------------------------------------------------------
    # Population
    # ---------------------------------------------------------

    def set_advisor(
        self,
        build_name: str,
        level: int,
        status_rows: list[tuple[str, str, str]],
        footer_text: str,
        footer_is_ready: bool,
        next_action_text: str,
        next_action_kind: str | None,
        pending_by_category: dict[str, tuple[list[str], int]],
    ):
        """``status_rows``/``footer_text``/``footer_is_ready`` are exactly
        what ``MainWindow._compute_build_status`` returns.
        ``next_action_text``/``next_action_kind`` are
        ``MainWindow._advisor_next_action``'s result - ``next_action_kind``
        is one of ``"skill"``/``"paragon"``/``"gear"`` or ``None`` when
        there's nothing to act on, and decides whether the NEXT ACTION
        line is click-to-navigate right now. ``pending_by_category`` maps
        each of ``Skills``/``Paragon``/``Gear`` to ``(capped_texts,
        total_count)`` - already capped by the caller (see
        ``MainWindow._advisor_missing_summary``) so this widget never has
        to decide the cap itself."""

        if not build_name:
            self.header_label.setText("No build selected")
            self.status_rows_label.setText("")
            self.status_footer_label.setText("")
            self.status_footer_label.setVisible(False)
            self.next_action_label.setText("—")
            self._next_action_kind = None
            self.next_action_label.set_active(False)
            for label in self._category_labels.values():
                label.setText("—")
            return

        self.header_label.setText(f"{build_name} (Lvl {level})")

        lines = [f"{emoji}  {label:<9}{pct}" for emoji, label, pct in status_rows]
        self.status_rows_label.setText("\n".join(lines))
        # Qt's word-wrap heightForWidth caching for this label loses track of
        # one line's worth of height after certain live window-shrink
        # sequences (reproduced: shrinking 1500px -> 900px wide leaves the
        # label one line short, so "Gear" silently paints underneath the
        # footer text below it) - none of these 4 fixed-format rows ever
        # actually need to wrap, so pin the height explicitly instead of
        # trusting the buggy wrap-driven size hint.
        self.status_rows_label.setFixedHeight(
            QFontMetrics(self.status_rows_label.font()).lineSpacing() * max(1, len(lines))
        )

        self.status_footer_label.setText(footer_text)
        color = QColor(theme.ACCENT_GOLD) if footer_is_ready else QColor(theme.TEXT_MUTED)
        self.status_footer_label.setTextColor(color, color)
        self.status_footer_label.setVisible(bool(footer_text))

        self.next_action_label.setText(next_action_text or "—")
        self._next_action_kind = next_action_kind
        self.next_action_label.set_active(next_action_kind is not None)

        for category in _CATEGORIES:
            texts, total = pending_by_category.get(category, ([], 0))
            label = self._category_labels[category]

            if not texts:
                label.setText("All done!")
                continue

            lines = [f"• {text}" for text in texts]
            remaining = total - len(texts)
            if remaining > 0:
                lines.append(f"  (+{remaining} more)")

            label.setText("\n".join(lines))

    def _on_next_action_clicked(self):
        if self._next_action_kind is not None:
            self.next_action_clicked.emit(self._next_action_kind)

    # ---------------------------------------------------------
    # Theme / appearance
    # ---------------------------------------------------------

    def refresh_theme(self):

        super().refresh_theme()

        self.status_header.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.status_rows_label.setStyleSheet(
            f"font-family: monospace; font-size: 16px; color: {theme.TEXT_PRIMARY};"
        )
        self.next_header.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self._missing_header.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))

        for header in self._category_headers.values():
            header.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))


class BuildAdvisorInterface(QWidget):
    """Top-level nav page wrapping ``BuildAdvisorCard`` - same centered,
    width-capped layout ``BuildsInterface``/``CharacterInterface`` use."""

    def __init__(self, advisor_card: BuildAdvisorCard, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        advisor_card.setMinimumWidth(420)
        advisor_card.setMaximumWidth(760)

        layout.addStretch(1)
        layout.addWidget(advisor_card, 3)
        layout.addStretch(1)
