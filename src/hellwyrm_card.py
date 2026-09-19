from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from qfluentwidgets import BodyLabel, CaptionLabel, FluentIcon as FIF, PrimaryPushButton

from src import theme
from src.base_card import BaseCard

# Dashboard's Hellwyrm Locations panel: shows Helltides.com's own public
# page directly in an embedded browser (QWebEngineView), exactly as if
# the player opened it themselves - no data is scraped, cached, copied,
# or requested by our own code, and no map/coordinate data or images are
# stored in this project. Zoom, pan, region selection and the Hellwyrm
# markers are entirely Helltides.com's own page.
HELLTIDES_URL = "https://helltides.com/"


class HellwyrmCard(BaseCard):
    """Embeds Helltides.com's public Hellwyrm map with a plain error
    state (and an "Open in Browser" fallback) if the page fails to
    load."""

    def __init__(self, parent=None):
        super().__init__("HELLWYRM LOCATIONS", icon=FIF.PIN, parent=parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(320, 380)

        self.source_label = CaptionLabel(
            "External website - helltides.com's own live map. "
            "Zoom, pan and region selection happen on their page.",
            self.content,
        )
        self.source_label.setWordWrap(True)
        self.source_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.add_widget(self.source_label)

        self.stack = QStackedWidget(self.content)
        self.stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.stack.setMinimumHeight(280)

        self.web_view = QWebEngineView(self.stack)
        self.web_view.loadFinished.connect(self._on_load_finished)
        self.web_view.load(QUrl(HELLTIDES_URL))
        self.stack.addWidget(self.web_view)

        self.error_widget = self._build_error_widget()
        self.stack.addWidget(self.error_widget)

        self.content_layout.addWidget(self.stack, 1)

    def _build_error_widget(self) -> QWidget:
        widget = QWidget(self.stack)
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        message = BodyLabel(
            "DATA UNAVAILABLE - could not load the Hellwyrm map "
            "(helltides.com). Check your internet connection.",
            widget,
        )
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignCenter)
        layout.addWidget(message)

        open_button = PrimaryPushButton("Open in Browser", widget)
        open_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(HELLTIDES_URL)))
        layout.addWidget(open_button, 0, Qt.AlignCenter)

        return widget

    def _on_load_finished(self, ok: bool):
        self.stack.setCurrentWidget(self.web_view if ok else self.error_widget)

    def set_active_helltide_region(self, region: str | None):
        """No-op: region selection happens on Helltides.com's own page,
        which already auto-selects the currently active Helltide zone
        itself. Kept so MainWindow's existing call site (see
        ``load_helltide``) needs no change."""

        return

    def refresh_theme(self):
        super().refresh_theme()

        self.source_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
