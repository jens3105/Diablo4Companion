from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from qfluentwidgets import BodyLabel, CaptionLabel, FluentIcon as FIF, PrimaryPushButton, StrongBodyLabel

from src import theme
from src.base_card import BaseCard

# Dashboard's primary panel. Earlier phases tried to show Hellwyrm spawn
# data ourselves (a static zone-name list, then research into copying
# coordinate/map data from Bubaigei/Helltides.com/th.gl) - all rejected
# because no source grants reuse rights to their map art or point data,
# and this project never reproduces someone else's copyrighted work or
# scrapes/reverse-engineers a private API (see PROJECT_ROADMAP.md's
# ban-safety rule; the same "never use what we don't have rights to"
# principle applies here even though no game client is involved).
#
# The approach that IS legitimate: showing Bubaigei's own public map
# page (https://bubaigei.com/d4/en/map/) in an embedded browser, exactly
# as if the player opened it themselves - no data is copied, cached, or
# requested by our own code; QWebEngineView just renders their page.
# Region selection happens in Bubaigei's own UI for now - a `?region=`
# query parameter was verified to be silently ignored by their page, so
# there is no URL-based deep link, and driving their dropdown via
# injected JavaScript was deliberately deferred as a separate, more
# fragile follow-up rather than bundled into this change.
BUBAIGEI_MAP_URL = "https://bubaigei.com/d4/en/map/"


class HellwyrmCard(BaseCard):
    """Embeds Bubaigei's public Hellwyrm map (zoom/pan/regions/markers
    are entirely their page's own UI) with a small static "Hellwyrm
    Helper" tips section underneath, and a plain error state with an
    "Open in browser" fallback if the page fails to load."""

    def __init__(self, parent=None):
        super().__init__("HELLWYRM LOCATIONS", icon=FIF.PIN, parent=parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(320, 380)

        self.source_label = CaptionLabel(
            "External website - bubaigei.com's own interactive map. "
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
        self.web_view.load(QUrl(BUBAIGEI_MAP_URL))
        self.stack.addWidget(self.web_view)

        self.error_widget = self._build_error_widget()
        self.stack.addWidget(self.error_widget)

        self.content_layout.addWidget(self.stack, 1)

        self.add_spacing(10)

        helper_header = StrongBodyLabel("Hellwyrm Helper", self.content)
        self.add_widget(helper_header)

        self.helper_label = BodyLabel(
            "Threat: Aim for approximately 2/3 Threat before hunting.\n"
            "Use the map above to find a region with a dense cluster of "
            "known Hellwyrm points, then rotate between them.",
            self.content,
        )
        self.helper_label.setWordWrap(True)
        self.helper_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.add_widget(self.helper_label)

    def _build_error_widget(self) -> QWidget:
        widget = QWidget(self.stack)
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        message = BodyLabel(
            "DATA UNAVAILABLE - could not load the Hellwyrm map "
            "(bubaigei.com). Check your internet connection.",
            widget,
        )
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignCenter)
        layout.addWidget(message)

        open_button = PrimaryPushButton("Open in Browser", widget)
        open_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(BUBAIGEI_MAP_URL)))
        layout.addWidget(open_button, 0, Qt.AlignCenter)

        return widget

    def _on_load_finished(self, ok: bool):
        self.stack.setCurrentWidget(self.web_view if ok else self.error_widget)

    def set_active_helltide_region(self, region: str | None):
        """No-op for now, kept so MainWindow's existing call site (see
        ``load_helltide``) needs no change. Bubaigei's map has no
        URL-based region deep link (verified: a ``?region=`` query
        parameter is silently ignored), and automating their region
        dropdown via injected JavaScript was explicitly deferred as a
        separate, more fragile follow-up - the player picks their region
        in Bubaigei's own map UI for now."""

        return

    def refresh_theme(self):
        super().refresh_theme()

        self.source_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.helper_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
