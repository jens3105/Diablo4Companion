from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon as FIF,
    PrimaryPushButton,
    StrongBodyLabel,
    TransparentToolButton,
)

from src import theme


class CompactWindow(QWidget):
    """Phase 9: a tiny always-on-top window meant to sit on a second
    screen (or overlap the game window) while actually playing - just
    the active character's build/level and the single Next Action, with
    a Done button.

    Deliberately a plain ``QWidget`` with ``Qt.WindowStaysOnTopHint``
    instead of a second ``FluentWindow`` - there's no navigation, so all
    the sidebar/routing machinery would be pure overhead. It never reads
    or writes state itself: MainWindow (``app.py``) owns the character/
    build/completion data and just pushes text into ``set_content`` and
    reacts to ``done_clicked``, so Compact Mode can never drift out of
    sync with the main window's own copy of that state.
    """

    done_clicked = Signal()
    shown = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window | Qt.WindowStaysOnTopHint)

        self.setWindowTitle("Diablo IV Companion - Compact")
        self.setFixedSize(300, 230)
        # So closing the window (title bar X, or our own close button)
        # actually destroys it - MainWindow relies on the ``destroyed``
        # signal to drop its reference and build a fresh window (with a
        # freshly-synced showEvent) next time Compact Mode is opened.
        self.setAttribute(Qt.WA_DeleteOnClose)

        # Unlike the main window, this is a plain QWidget rather than a
        # FluentWindow, so it doesn't automatically pick up the app's
        # dark background - without this it renders as a plain white/
        # light OS window while its labels are still colored for a dark
        # background (near-invisible white-on-white text).
        self.setStyleSheet(f"CompactWindow {{ background-color: {theme.BACKGROUND}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(4)

        header_row = QHBoxLayout()
        header_row.setSpacing(6)

        self.build_label = StrongBodyLabel("", self)
        self.build_label.setWordWrap(True)
        self.build_label.setTextColor(QColor(theme.TEXT_PRIMARY), QColor(theme.TEXT_PRIMARY))
        header_row.addWidget(self.build_label, 1)

        # Belt-and-suspenders return-to-normal: the OS title bar's own
        # close button already closes this window (it's a real top-level
        # window, not a frameless popup), but window managers without a
        # visible title bar for WindowStaysOnTopHint widgets still leave
        # the user a way out.
        close_button = TransparentToolButton(FIF.CLOSE, self)
        close_button.setFixedSize(22, 22)
        close_button.clicked.connect(self.close)
        header_row.addWidget(close_button)

        layout.addLayout(header_row)

        self.level_label = CaptionLabel("", self)
        self.level_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        layout.addWidget(self.level_label)

        layout.addSpacing(8)

        self.next_header = CaptionLabel("NEXT ACTION", self)
        self.next_header.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        layout.addWidget(self.next_header)

        self.action_label = BodyLabel("—", self)
        self.action_label.setWordWrap(True)
        self.action_label.setTextColor(QColor(theme.TEXT_PRIMARY), QColor(theme.TEXT_PRIMARY))
        layout.addWidget(self.action_label)

        layout.addSpacing(4)

        self.done_button = PrimaryPushButton("✓ DONE", self)
        self.done_button.clicked.connect(self.done_clicked)
        layout.addWidget(self.done_button)

        layout.addSpacing(6)

        self.preview_label = CaptionLabel("", self)
        self.preview_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.preview_label.setWordWrap(True)
        layout.addWidget(self.preview_label)

        layout.addStretch(1)

    def set_content(
        self,
        title: str,
        level: int,
        next_action_text: str,
        preview_text: str,
        done_enabled: bool,
    ):
        """Populate every label. ``title`` is expected to already be
        "<character> — <build>" (or just the build name) - this widget
        has no character/build data of its own, MainWindow assembles it."""

        if not title:
            self.build_label.setText("No build selected")
            self.level_label.setText("")
            self.action_label.setText("—")
            self.preview_label.setText("")
            self.done_button.setEnabled(False)
            return

        self.build_label.setText(title.upper())
        self.level_label.setText(f"LVL {level}")
        self.action_label.setText(next_action_text or "—")
        self.preview_label.setText(f"Next: {preview_text}" if preview_text else "")
        self.done_button.setEnabled(done_enabled)

    def showEvent(self, event):
        """Reopening (or re-showing) the window is the one moment we can
        cheaply guarantee is in sync with the main window without wiring
        up a full live-update channel - see the ``shown`` doc note in
        MainWindow.open_compact_mode. Live edits in the main window are
        actually also pushed here directly (via
        MainWindow._refresh_dashboard_build_card), this is just the
        belt-and-suspenders catch-all for anything that isn't."""

        super().showEvent(event)
        self.shown.emit()

    def refresh_theme(self):
        """Re-apply hard-coded colors after a theme/preset change - this
        is a plain QWidget (not a BaseCard), so unlike the dashboard cards
        it doesn't pick up the app background from qfluentwidgets' own
        theme system automatically."""

        self.setStyleSheet(f"CompactWindow {{ background-color: {theme.BACKGROUND}; }}")
        self.build_label.setTextColor(QColor(theme.TEXT_PRIMARY), QColor(theme.TEXT_PRIMARY))
        self.level_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.next_header.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.action_label.setTextColor(QColor(theme.TEXT_PRIMARY), QColor(theme.TEXT_PRIMARY))
        self.preview_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
