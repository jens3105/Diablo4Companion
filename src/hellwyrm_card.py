from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QHBoxLayout, QSizePolicy

from qfluentwidgets import BodyLabel, CaptionLabel, ComboBox, FluentIcon as FIF

from src import theme
from src.base_card import BaseCard
from src.hellwyrm_data import HELLWYRM_AREAS, REGION_ORDER, SCENE_HEIGHT, SCENE_WIDTH, resolve_path

# Dashboard's primary panel: an original, local "Hellwyrm Location
# Guide" schematic - not a copy of Bubaigei/Helltides.com/th.gl's map
# art, not their coordinate data, no external connection at all once
# loaded. Every region's diagram is drawn procedurally with QPainter
# via QGraphicsScene/QGraphicsView (zoom + pan are Qt's own view
# transform - the underlying scene coordinates set below never change,
# see resolve_path() in src/hellwyrm_data.py).
#
# The single most important rule for this file: a marker's position is
# a SCHEMATIC visualization of a documented compass-direction sequence
# ("south, then northeast" from a named waypoint), never a claim about
# a real in-game position. HellwyrmCard's permanent disclaimer label
# and every marker-click detail repeat this - see hellwyrm_data.py's
# module docstring for the full reasoning.

_HELLWYRM_MARKER_COLOR = "#c0392b"
_REGION_TINTS = {
    "Fractured Peaks": "#2c3e50",
    "Scosglen": "#1e3d2f",
    "Dry Steppes": "#4a3b22",
    "Hawezar": "#2f3a28",
    "Kehjistan": "#4a2f1e",
}

_DISCLAIMER_TEXT = (
    "Approximate location based on documented route information "
    "— schematic diagram, not exact coordinates."
)


class HellwyrmSceneView(QGraphicsView):
    """QGraphicsView with wheel-zoom, click-and-drag pan, and click
    detection on the Hellwyrm marker - implemented directly (rather
    than relying on ScrollHandDrag) so panning and marker clicks are
    both reliably distinguishable in the same view."""

    marker_clicked = Signal(str)

    _MIN_SCALE = 0.5
    _MAX_SCALE = 4.0
    _ZOOM_STEP = 1.15

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.NoDrag)
        self._scale = 1.0
        self._panning = False
        self._pan_start = None
        self._press_pos = None
        self._press_region = None

    def wheelEvent(self, event):
        factor = self._ZOOM_STEP if event.angleDelta().y() > 0 else 1 / self._ZOOM_STEP
        new_scale = self._scale * factor
        if self._MIN_SCALE <= new_scale <= self._MAX_SCALE:
            self.scale(factor, factor)
            self._scale = new_scale
        event.accept()

    def reset_view(self):
        self.resetTransform()
        self._scale = 1.0

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return

        item = self.itemAt(event.pos())
        region = item.data(0) if item is not None else None

        if region:
            self._press_region = region
            self._press_pos = event.pos()
            self._panning = False
        else:
            self._press_region = None
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._panning and self._pan_start is not None:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            super().mouseReleaseEvent(event)
            return

        if self._panning:
            self._panning = False
            self.unsetCursor()
        elif self._press_region and (event.pos() - self._press_pos).manhattanLength() < 6:
            self.marker_clicked.emit(self._press_region)

        self._press_region = None


class HellwyrmCard(BaseCard):
    """Original, local Hellwyrm Location Guide: a region selector plus
    a zoomable/pannable schematic diagram per region, showing the
    documented waypoint and the documented Hellwyrm-area direction as
    markers - never a geographically accurate map, never copied
    coordinates. Regions without two independently-agreeing sources
    show DATA UNAVAILABLE instead of a guessed marker."""

    def __init__(self, parent=None):
        super().__init__("HELLWYRM LOCATIONS", icon=FIF.PIN, parent=parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(320, 420)

        self._user_selected = False
        self._scenes = {}

        self.disclaimer_label = CaptionLabel(_DISCLAIMER_TEXT, self.content)
        self.disclaimer_label.setWordWrap(True)
        self.disclaimer_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.add_widget(self.disclaimer_label)

        region_row = QHBoxLayout()
        region_row.setSpacing(8)
        region_row.addWidget(CaptionLabel("Region:", self.content))

        self.region_combo = ComboBox(self.content)
        self.region_combo.addItems(REGION_ORDER)
        self.region_combo.setMinimumWidth(160)
        self.region_combo.currentIndexChanged.connect(self._on_region_changed)
        region_row.addWidget(self.region_combo)
        region_row.addStretch(1)

        self.add_layout(region_row)

        self.view = HellwyrmSceneView(self.content)
        self.view.setMinimumHeight(260)
        self.view.marker_clicked.connect(self._on_marker_clicked)
        self.content_layout.addWidget(self.view, 1)

        self.detail_label = BodyLabel(
            "Select a region and click the Hellwyrm marker for details.",
            self.content,
        )
        self.detail_label.setWordWrap(True)
        self.detail_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.add_widget(self.detail_label)

        self._show_region(REGION_ORDER[0])

    # ---------------------------------------------------------
    # Region handling
    # ---------------------------------------------------------

    def _on_region_changed(self, index: int):
        self._user_selected = True
        if 0 <= index < len(REGION_ORDER):
            self._show_region(REGION_ORDER[index])

    def _show_region(self, region: str):
        if region not in self._scenes:
            self._scenes[region] = self._build_scene(region)

        self.view.setScene(self._scenes[region])
        self.view.reset_view()
        self.detail_label.setText("Select a region and click the Hellwyrm marker for details.")

    def set_active_helltide_region(self, region: str | None):
        """Called by MainWindow with whatever (real, verified) location
        string the current Helltide schedule entry provides - never a
        guess. Never overrides a region the player already picked
        manually this session."""

        if self._user_selected or not region or region not in REGION_ORDER:
            return

        index = REGION_ORDER.index(region)
        self.region_combo.blockSignals(True)
        self.region_combo.setCurrentIndex(index)
        self.region_combo.blockSignals(False)
        self._show_region(region)

    # ---------------------------------------------------------
    # Scene construction
    # ---------------------------------------------------------

    def _build_scene(self, region: str) -> QGraphicsScene:
        scene = QGraphicsScene(0, 0, SCENE_WIDTH, SCENE_HEIGHT)
        self._paint_background(scene, region)

        area = HELLWYRM_AREAS.get(region)
        if area is None:
            unavailable = scene.addText(
                "DATA UNAVAILABLE\nNo cross-verified Hellwyrm area for this region yet."
            )
            unavailable.setDefaultTextColor(QColor(theme.TEXT_MUTED))
            rect = unavailable.boundingRect()
            unavailable.setPos(SCENE_WIDTH / 2 - rect.width() / 2, SCENE_HEIGHT / 2 - rect.height() / 2)
            return scene

        points = resolve_path(area["directions"])

        path = QPainterPath()
        path.moveTo(*points[0])
        for point in points[1:]:
            path.lineTo(*point)
        scene.addPath(path, QPen(QColor(theme.TEXT_MUTED), 2, Qt.DashLine))

        wx, wy = points[0]
        scene.addEllipse(wx - 9, wy - 9, 18, 18, QPen(Qt.NoPen), QBrush(QColor(theme.ACCENT_GOLD)))
        waypoint_label = scene.addText(area["landmark"])
        waypoint_label.setDefaultTextColor(QColor(theme.TEXT_PRIMARY))
        waypoint_label.setPos(wx + 14, wy - 12)

        hx, hy = points[-1]
        marker = scene.addEllipse(
            hx - 13, hy - 13, 26, 26, QPen(Qt.NoPen), QBrush(QColor(_HELLWYRM_MARKER_COLOR))
        )
        marker.setData(0, region)
        marker.setCursor(Qt.PointingHandCursor)
        marker.setToolTip("Click for documented route details")

        area_label = scene.addText("Hellwyrm area")
        area_label.setDefaultTextColor(QColor(theme.TEXT_PRIMARY))
        area_label.setPos(hx + 18, hy - 12)

        return scene

    def _paint_background(self, scene: QGraphicsScene, region: str):
        tint = QColor(_REGION_TINTS.get(region, theme.SURFACE_ALT))
        gradient = QLinearGradient(0, 0, 0, SCENE_HEIGHT)
        gradient.setColorAt(0.0, tint)
        gradient.setColorAt(1.0, QColor(theme.SURFACE_ALT))
        scene.addRect(0, 0, SCENE_WIDTH, SCENE_HEIGHT, QPen(QColor(theme.BORDER)), QBrush(gradient))

        compass = {
            "N": (SCENE_WIDTH / 2, 12),
            "S": (SCENE_WIDTH / 2, SCENE_HEIGHT - 28),
            "E": (SCENE_WIDTH - 24, SCENE_HEIGHT / 2),
            "W": (12, SCENE_HEIGHT / 2),
        }
        for label, (x, y) in compass.items():
            text = scene.addText(label)
            text.setDefaultTextColor(QColor(theme.TEXT_MUTED))
            text.setPos(x, y)

    # ---------------------------------------------------------
    # Marker detail
    # ---------------------------------------------------------

    def _on_marker_clicked(self, region: str):
        area = HELLWYRM_AREAS.get(region)
        if not area:
            return

        direction_text = " → ".join(area["directions"])
        self.detail_label.setText(
            f"{area['landmark']} — {region}\n"
            f"Documented direction: {direction_text}\n"
            f"{area['description']}\n"
            f"Confidence: {area['confidence']} ({area['sources']} independent sources).\n"
            f"{_DISCLAIMER_TEXT}"
        )

    # ---------------------------------------------------------
    # Theme
    # ---------------------------------------------------------

    def refresh_theme(self):
        super().refresh_theme()

        self.disclaimer_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.detail_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))

        # Scenes bake theme colors in at draw time - rebuild them so a
        # dark/light or accent-preset switch is reflected immediately.
        self._scenes.clear()
        self._show_region(REGION_ORDER[self.region_combo.currentIndex()])
