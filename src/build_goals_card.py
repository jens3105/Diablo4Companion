from PySide6.QtGui import QColor
from PySide6.QtWidgets import QSizePolicy

from qfluentwidgets import BodyLabel, CaptionLabel, FluentIcon as FIF

from src import theme
from src.base_card import BaseCard

# Dashboard: replaces the old Season 15 panel (a static countdown that
# had already reached "LIVE NOW" and stopped being useful). Shows a
# short, prioritized slice of MainWindow._advisor_pending_actions - the
# exact same single source of truth Current Build's NEXT ACTION line
# and Build Advisor already use - never a second way of deciding what's
# next. Deliberately capped at a few items (MAX_GOALS) rather than the
# full list: Current Build already covers the single top action, this
# card's job is just "the next few concrete things", not a duplicate of
# the whole Build Advisor page.
MAX_GOALS = 3

_KIND_ICON = {
    "leveling": "🎯",
    "skill": "🎯",
    "paragon": "🧩",
    "paragon_node": "🧩",
    "gear": "🛡️",
    "gem": "💎",
    "tempering": "🔨",
}


class BuildGoalsCard(BaseCard):
    """Dashboard tile: a short, build-agnostic read-out of the most
    important pending actions, sourced entirely from MainWindow's
    existing Build Validation data (see ``set_goals``) - no validation
    logic of its own."""

    def __init__(self, parent=None):
        super().__init__("BUILD GOALS", icon=FIF.FLAG, parent=parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(260, 190)

        self.overall_label = CaptionLabel("", self.content)
        self.overall_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.overall_label.hide()
        self.content_layout.addWidget(self.overall_label)

        self.goal_labels = []
        for _ in range(MAX_GOALS):
            lbl = BodyLabel("", self.content)
            lbl.setWordWrap(True)
            lbl.hide()
            self.content_layout.addWidget(lbl)
            self.goal_labels.append(lbl)

        self.empty_label = BodyLabel("", self.content)
        self.empty_label.setWordWrap(True)
        self.empty_label.hide()
        self.content_layout.addWidget(self.empty_label)

        self.add_stretch()

    def set_goals(self, overall_percent: int | None, goals: list[tuple[str, str]]):
        """``goals`` is an already-capped (see ``MAX_GOALS``) slice of
        ``(kind, text)`` pairs straight from ``_advisor_pending_actions``
        - this card only picks an icon per ``kind`` and renders text,
        never decides what's pending itself. ``overall_percent`` is
        ``_build_validation``'s own already-computed figure - shown
        as-is, never recomputed here."""

        if overall_percent is not None:
            self.overall_label.setText(f"Overall build progress: {overall_percent}%")
            self.overall_label.show()
        else:
            self.overall_label.hide()

        for i, lbl in enumerate(self.goal_labels):
            if i < len(goals):
                kind, text = goals[i]
                icon = _KIND_ICON.get(kind, "•")
                lbl.setText(f"{icon} {text}")
                lbl.show()
            else:
                lbl.hide()

        if not goals:
            # Empty is ambiguous on its own: it means either "nothing
            # left to do" (a real build, fully confirmed) or "nothing to
            # show at all" (no build selected, or a build with no
            # verified data to validate against, e.g. Heartseeker Rogue)
            # - overall_percent already distinguishes the two without
            # any new computation here.
            if overall_percent is not None:
                self.empty_label.setText("Build looks good - no outstanding actions.")
            else:
                self.empty_label.setText("No build data available.")
            self.empty_label.show()
        else:
            self.empty_label.hide()

    def refresh_theme(self):
        super().refresh_theme()

        self.overall_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
