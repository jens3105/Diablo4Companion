"""Modal "New version available" dialog (Update Notification phase).

Purely a presentation/interaction shell around the app's existing
update-check state - it never fetches, downloads, verifies, or installs
anything itself. MainWindow builds it from the exact same release dict
``SettingsInterface._on_check_updates_clicked``/``apply_release_check_result``
already use, and "Update Now" here is always handled by MainWindow
calling ``SettingsInterface._on_update_now_clicked()`` - the one and
only download/verify/install/restart code path in the app (see
``MainWindow.show_update_available_dialog``).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
)

from qfluentwidgets import BodyLabel, PrimaryPushButton, PushButton, StrongBodyLabel, SubtitleLabel

from src import theme

_FALLBACK_RELEASE_NOTES = "No release notes were provided for this version."


class UpdateAvailableDialog(QDialog):
    """``exec()`` returns ``QDialog.Accepted`` for "Update Now", or
    ``QDialog.Rejected`` for "Later"/closing the dialog - the caller is
    the only place that acts on that result."""

    def __init__(self, current_version: str, release: dict, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Diablo 4 Companion - New version available")
        self.setModal(True)
        self.resize(480, 420)
        self.setStyleSheet(
            f"QDialog {{ background-color: {theme.SURFACE}; border: 1px solid {theme.BORDER}; }}"
        )

        release_name = (release.get("name") or release.get("tag_name") or "").strip()
        release_notes = (release.get("body") or "").strip() or _FALLBACK_RELEASE_NOTES

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = SubtitleLabel("New version available", self)
        layout.addWidget(title)

        versions = BodyLabel(
            f"Current version: {current_version}\nNew version: {release_name}", self
        )
        layout.addWidget(versions)

        notes_title = StrongBodyLabel("What's New", self)
        layout.addWidget(notes_title)

        notes_label = QLabel(release_notes, self)
        notes_label.setWordWrap(True)
        notes_label.setTextFormat(Qt.TextFormat.MarkdownText)
        notes_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        notes_scroll = QScrollArea(self)
        notes_scroll.setWidgetResizable(True)
        notes_scroll.setWidget(notes_label)
        notes_scroll.setMinimumHeight(200)
        layout.addWidget(notes_scroll, 1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)

        later_button = PushButton("Later", self)
        later_button.clicked.connect(self.reject)
        button_row.addWidget(later_button)

        update_button = PrimaryPushButton("Update Now", self)
        update_button.clicked.connect(self.accept)
        button_row.addWidget(update_button)

        layout.addLayout(button_row)
