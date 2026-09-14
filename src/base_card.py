from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from qfluentwidgets import BodyLabel, CardWidget, IconWidget, StrongBodyLabel
from qfluentwidgets.common.icon import FluentIconBase

from src import theme


class ClickableBodyLabel(BodyLabel):
    """A ``BodyLabel`` that can be toggled (``set_active``) into a
    clickable, hand-cursor state - used for the Dashboard/Build Advisor
    "next action" line jumping straight to the relevant page/tab (see
    ``CurrentBuildCard``/``BuildAdvisorCard``).

    When inactive, an unhandled mouse release just falls through to
    ``QLabel``'s default (Qt propagates an *ignored* mouse event up to
    the parent widget - this is exactly how, before this class existed,
    clicking anywhere on ``CurrentBuildCard`` including this label
    already fell through to the whole card's own ``clicked`` navigation).
    When active, the event is accepted here instead, so it stops at this
    label and fires ``clicked`` rather than also triggering the parent
    card's navigation."""

    clicked = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._active = False

    def set_active(self, active: bool):
        self._active = active
        self.setCursor(Qt.PointingHandCursor if active else Qt.ArrowCursor)

    def mouseReleaseEvent(self, e):
        if self._active:
            e.accept()
            self.clicked.emit()
        else:
            super().mouseReleaseEvent(e)


class ClickableStrongBodyLabel(StrongBodyLabel):
    """Same as ``ClickableBodyLabel``, styled like ``StrongBodyLabel`` -
    used by ``BuildAdvisorCard``'s bigger next-action line."""

    clicked = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._active = False

    def set_active(self, active: bool):
        self._active = active
        self.setCursor(Qt.PointingHandCursor if active else Qt.ArrowCursor)

    def mouseReleaseEvent(self, e):
        if self._active:
            e.accept()
            self.clicked.emit()
        else:
            super().mouseReleaseEvent(e)


class BaseCard(CardWidget):
    """Fluent-based foundation for every dashboard card.

    Wraps qfluentwidgets' ``CardWidget`` (which already gives us the
    correct dark-theme background, hover/press elevation and rounded
    corners) with a small icon + title + content-area convention so the
    concrete cards (EventCard, UpcomingCard, LevelingCard, ...) don't
    each have to hand-roll their own QFrame/stylesheet like before.

    ``icon`` takes a ``qfluentwidgets.FluentIcon`` member (a proper vector
    icon) instead of an emoji glyph, matching the icons used in the
    navigation sidebar.
    """

    def __init__(self, title: str = "", icon: FluentIconBase = None, parent=None):
        super().__init__(parent)

        self.setBorderRadius(12)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(22, 18, 22, 18)
        self.main_layout.setSpacing(10)

        self.title_row = QHBoxLayout()
        self.title_row.setSpacing(8)

        self._icon = icon
        self.icon_widget = None

        if icon is not None:
            self.icon_widget = IconWidget(icon.icon(color=QColor(theme.ACCENT_GOLD)), self)
            self.icon_widget.setFixedSize(18, 18)
            self.title_row.addWidget(self.icon_widget)

        self.title_label = StrongBodyLabel(title, self)
        self.title_label.setObjectName("cardTitle")
        self.title_label.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.title_row.addWidget(self.title_label)

        if title or icon is not None:
            self.main_layout.addLayout(self.title_row)

        self.content = QWidget(self)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)

        self.main_layout.addWidget(self.content, 1)

    # ---------------------------------------------------------
    # Convenience helpers used by subclasses
    # ---------------------------------------------------------

    def center_title(self):
        """Center the icon+title row instead of the default left-align."""

        self.title_row.insertStretch(0)
        self.title_row.addStretch()

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)

    def add_spacing(self, amount: int = 10):
        self.content_layout.addSpacing(amount)

    def add_stretch(self):
        self.content_layout.addStretch()

    def set_title(self, text: str):
        self.title_label.setText(text)

    def refresh_theme(self):
        """Re-apply the icon/title accent color after a theme/preset
        change - subclasses that add their own hard-coded colors should
        override this and call ``super().refresh_theme()``."""

        if self.icon_widget is not None and self._icon is not None:
            self.icon_widget.setIcon(self._icon.icon(color=QColor(theme.ACCENT_GOLD)))

        self.title_label.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
