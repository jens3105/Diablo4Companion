"""Paragon page (roadmap Phases 6+7+8+9+10, combined into one page):
a dedicated top-level nav page for browsing a build's verified Paragon
boards - an Overview list, and a Board detail view with Prev/Next
navigation and a grid visualization of the board's taken nodes.

Like ``CharacterInterface``/``BuildAdvisorInterface`` this page owns no
"current build" state of its own - ``MainWindow`` pushes the active
character/build/level and the build's data here the same way it already
pushes them everywhere else (see ``MainWindow._refresh_dashboard_build_
card``, extended to also call ``ParagonCard.set_paragon``).

Data model (see ``verified_build.paragon_boards`` in ``builds/*.json``,
decoded by ``scripts/maxroll_data_decoder.py``) - important limits this
page respects:

* There is NO adjacency/edge/path data between nodes anywhere in the
  data. The grid view therefore only ever draws taken nodes (and the
  glyph socket / start node markers) as plain dots at their real
  ``(x, y)`` position - never a connecting line/route between them, since
  that would imply a confirmed path that was never actually decoded.
* A node's rarity is a fixed int (0=Normal, 2=Magic, 3=Rare,
  4=Legendary) - hardcoded here as documented data, not invented.
* Every node this app can show is, by definition, a *taken* node (the
  data has no "available but not yet taken" or "locked" node list) - so
  a node's detail popup always shows a plain "✓ Taken" status, never a
  fabricated "locked next" state.
* Builds with no ``verified_build`` (currently only Heartseeker Rogue)
  have no board/grid data at all - the Overview shows a clean
  "DATA UNAVAILABLE" message instead of an empty or broken page.

Two things are deliberately *not* recomputed a second way here:

* The overall Paragon completion percentage - ``MainWindow._compute_
  build_status`` already produces this (the "Paragon" row of its 3-tuple
  list); ``ParagonCard.set_paragon`` just displays whatever row it's
  handed.
* A verified board's stable id (real Maxroll ``board`` slug, or a
  positional fallback) - reuses ``LevelingCard._board_id`` exactly, so
  this page's ✓/→/○ status per board always agrees with the Build
  Guide's own Paragon tab and can never drift onto a different id
  scheme.

The node rarity color for Legendary reuses ``gear_planner``'s existing
"legendary" swatch for visual consistency with the rest of the app;
Normal reuses ``theme.TEXT_MUTED`` (its usual "de-emphasized" role
everywhere else). Magic/Rare have no prior swatch anywhere in the app
(``gear_planner`` only ever needed mythic/unique/legendary/set *gear*
rarities) so get their own fixed, theme-independent colors matching
Diablo IV's own in-game color convention for those tiers.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon as FIF,
    MessageBoxBase,
    PushButton,
    SingleDirectionScrollArea,
    StrongBodyLabel,
)

from src import theme
from src.base_card import BaseCard
from src.gear_planner import _RARITY_COLORS as _GEAR_RARITY_COLORS
from src.leveling_card import LevelingCard

# Fixed ints from the decoder (see module docstring) - not user-facing
# strings anywhere in the data, so the label text lives only here.
RARITY_LABELS = {0: "Normal", 2: "Magic", 3: "Rare", 4: "Legendary"}


def _node_color(rarity) -> str:
    if rarity == 4:
        # Reuse gear_planner's existing Legendary swatch (see module
        # docstring) instead of picking a new orange.
        return _GEAR_RARITY_COLORS["legendary"]
    if rarity == 3:
        return "#d9c74a"
    if rarity == 2:
        return "#4a90d9"
    return theme.TEXT_MUTED


class NodeDetailDialog(MessageBoxBase):
    """Detail popup for one taken Paragon node - only real, decoded
    fields (name, rarity, board, grid id). Status is always a plain
    "✓ Taken" - see module docstring for why no other status is ever
    possible with this data."""

    def __init__(self, node: dict, board_index: int, parent=None):
        super().__init__(parent)

        title = StrongBodyLabel(node.get("name") or node.get("slug") or "?", self)
        title.setWordWrap(True)
        self.viewLayout.addWidget(title)

        def add_field(label: str, value: str):
            row = BodyLabel(f"{label}: {value}", self)
            row.setWordWrap(True)
            row.setTextColor(QColor(theme.TEXT_PRIMARY), QColor(theme.TEXT_PRIMARY))
            self.viewLayout.addWidget(row)

        rarity = node.get("rarity", 0)
        add_field("Rarity", RARITY_LABELS.get(rarity, f"Unknown ({rarity})"))
        add_field("Board", f"Board {board_index + 1}")

        slug = node.get("slug")
        if slug and slug != node.get("name"):
            add_field("ID", slug)

        status_row = BodyLabel("Status: ✓ Taken", self)
        status_row.setTextColor(QColor("#3fa860"), QColor("#3fa860"))
        self.viewLayout.addWidget(status_row)

        self.hideCancelButton()
        self.yesButton.setText("Close")
        self.widget.setMinimumWidth(280)


class ParagonBoardGrid(QWidget):
    """Custom-painted grid of one board's ~441 possible node slots
    (``board_width`` x ``board_width``). Only renders what the data
    actually contains: taken nodes at their real ``(x, y)`` (derived from
    ``index``/``board_width``, no other layout math), plus the glyph
    socket and start node as outlined markers. No line/path is ever
    drawn between nodes - see module docstring."""

    CELL = 18

    node_clicked = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._board = None
        self._nodes_by_index = {}
        self.setCursor(Qt.ArrowCursor)

    def set_board(self, board: dict | None):
        self._board = board
        self._nodes_by_index = {}

        if board:
            for node in board.get("nodes") or []:
                if isinstance(node, dict) and "index" in node:
                    self._nodes_by_index[node["index"]] = node

            width = board.get("board_width") or 1
            size = max(1, width) * self.CELL
            self.setFixedSize(size, size)
        else:
            self.setFixedSize(0, 0)

        self.update()

    def _index_at(self, point) -> int | None:
        if not self._board:
            return None

        width = self._board.get("board_width") or 1
        col = point.x() // self.CELL
        row = point.y() // self.CELL

        if col < 0 or row < 0 or col >= width or row >= width:
            return None

        return row * width + col

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            index = self._index_at(event.position().toPoint())
            node = self._nodes_by_index.get(index) if index is not None else None
            if node:
                self.node_clicked.emit(node)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)

        if not self._board:
            painter.end()
            return

        width = max(1, self._board.get("board_width") or 1)

        painter.fillRect(self.rect(), QColor(theme.SURFACE_ALT))

        for index, node in self._nodes_by_index.items():
            x = (index % width) * self.CELL
            y = (index // width) * self.CELL
            color = _node_color(node.get("rarity", 0))
            painter.fillRect(x + 1, y + 1, self.CELL - 2, self.CELL - 2, QColor(color))

        # Glyph socket / start node markers - drawn as outlines on top,
        # since both may or may not coincide with an already-colored
        # taken-node square (see module docstring: start_node_index is
        # sometimes present in ``nodes``, sometimes a separate marker).
        for special_index, ring_color in (
            (self._board.get("glyph_socket_index"), theme.ACCENT_GOLD),
            (self._board.get("start_node_index"), "#3fa860"),
        ):
            if special_index is None:
                continue

            x = (special_index % width) * self.CELL
            y = (special_index // width) * self.CELL

            pen = QPen(QColor(ring_color))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(x + 1, y + 1, self.CELL - 2, self.CELL - 2)

        painter.end()


class BoardSummaryRow(QWidget):
    """One clickable Overview row: board order/name, status, and node
    count - opens that board's detail view on click."""

    clicked = Signal(int)

    def __init__(self, index: int, parent=None):
        super().__init__(parent)

        self.index = index
        self.setObjectName("paragonBoardRow")
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        self.title_label = StrongBodyLabel("", self)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.detail_label = CaptionLabel("", self)
        self.detail_label.setWordWrap(True)
        self.detail_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        layout.addWidget(self.detail_label)

        self._apply_background()

    def _apply_background(self):
        self.setStyleSheet(
            f"QWidget#paragonBoardRow {{ background-color: {theme.SURFACE_ALT}; "
            f"border-radius: 8px; }}"
        )

    def set_content(self, title: str, detail: str, status_color: str):
        self.title_label.setText(title)
        self.title_label.setTextColor(QColor(status_color), QColor(status_color))
        self.detail_label.setText(detail)

    def refresh_theme(self):
        self._apply_background()
        self.detail_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.index)
        super().mousePressEvent(event)


class ParagonCard(BaseCard):
    """Overview (board list + overall %) and Board detail (Prev/Next +
    grid) for the active character/build - see module docstring."""

    def __init__(self, parent=None):
        super().__init__("PARAGON", icon=FIF.TILES, parent=parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(360, 360)

        self.header_label = StrongBodyLabel("No build selected", self.content)
        self.header_label.setWordWrap(True)
        self.add_widget(self.header_label)

        hint = CaptionLabel(
            "Switch character/build/level from the Build Guide page.", self.content
        )
        hint.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.add_widget(hint)
        self._hint_label = hint

        self.progress_label = StrongBodyLabel("", self.content)
        self.progress_label.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.add_widget(self.progress_label)

        self.stack = QStackedWidget(self.content)
        self.overview_page = self._build_overview_page()
        self.detail_page = self._build_detail_page()
        self.stack.addWidget(self.overview_page)
        self.stack.addWidget(self.detail_page)

        self.add_widget(self.stack)
        self.content_layout.setStretch(self.content_layout.count() - 1, 1)

        self._build_name = ""
        self._boards = []
        self._completed = set()
        self._detail_index = None
        self._row_widgets = []

    # ---------------------------------------------------------
    # Page construction
    # ---------------------------------------------------------

    def _build_overview_page(self) -> QWidget:

        page = QWidget(self.content)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        self.unavailable_label = BodyLabel(
            "DATA UNAVAILABLE — no verified Maxroll Planner profile for "
            "this build's Paragon boards yet.",
            page,
        )
        self.unavailable_label.setWordWrap(True)
        self.unavailable_label.hide()
        layout.addWidget(self.unavailable_label)

        scroll = SingleDirectionScrollArea(page, orient=Qt.Vertical)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background: transparent; border: none;}")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        inner = QVBoxLayout(container)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(6)
        inner.addStretch()

        scroll.setWidget(container)

        self._rows_container = container
        self._rows_layout = inner

        layout.addWidget(scroll, 1)

        return page

    def _build_detail_page(self) -> QWidget:

        page = QWidget(self.content)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 4, 0, 0)
        outer.setSpacing(8)

        back_button = PushButton("← Overview", page)
        back_button.clicked.connect(lambda: self.stack.setCurrentWidget(self.overview_page))
        outer.addWidget(back_button, 0, Qt.AlignLeft)

        nav_row = QHBoxLayout()
        nav_row.setSpacing(10)

        self.prev_button = PushButton("< Board", page)
        self.prev_button.clicked.connect(self._go_to_prev_board)

        self.board_position_label = StrongBodyLabel("BOARD ?/?", page)

        self.next_button = PushButton("Board >", page)
        self.next_button.clicked.connect(self._go_to_next_board)

        nav_row.addWidget(self.prev_button)
        nav_row.addStretch(1)
        nav_row.addWidget(self.board_position_label)
        nav_row.addStretch(1)
        nav_row.addWidget(self.next_button)

        outer.addLayout(nav_row)

        scroll = SingleDirectionScrollArea(page, orient=Qt.Vertical)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background: transparent; border: none;}")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(8)

        self.board_title_label = StrongBodyLabel("", container)
        self.board_title_label.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        c_layout.addWidget(self.board_title_label)

        self.board_meta_label = CaptionLabel("", container)
        self.board_meta_label.setWordWrap(True)
        self.board_meta_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        c_layout.addWidget(self.board_meta_label)

        grid_row = QHBoxLayout()
        grid_row.addStretch(1)
        self.grid_widget = ParagonBoardGrid(container)
        self.grid_widget.node_clicked.connect(self._on_node_clicked)
        grid_row.addWidget(self.grid_widget)
        grid_row.addStretch(1)
        c_layout.addLayout(grid_row)

        self.legend_label = CaptionLabel("", container)
        self.legend_label.setWordWrap(True)
        self.legend_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        c_layout.addWidget(self.legend_label)
        self._set_legend_text()

        c_layout.addStretch(1)

        scroll.setWidget(container)
        outer.addWidget(scroll, 1)

        return page

    def _set_legend_text(self):
        self.legend_label.setText(
            "Node colors: Normal (muted) · Magic (blue) · Rare (yellow) · "
            "Legendary (orange). Gold outline = glyph socket, green "
            "outline = start node. Only taken nodes and these two markers "
            "are shown - there is no adjacency/path data, so no route is "
            "drawn between them."
        )

    # ---------------------------------------------------------
    # Population
    # ---------------------------------------------------------

    def set_paragon(
        self,
        character_name: str,
        build_name: str,
        level: int,
        verified_build: dict | None,
        completed_boards: set,
        paragon_status_row: tuple[str, str, str] | None,
    ):
        """Populate the header, overall Paragon % and Overview board list
        for the active character/build/level, and keep an already-open
        Board detail view in sync (e.g. after a level change or a mark-
        board-done elsewhere).

        ``paragon_status_row`` is exactly the ``("emoji", "Paragon",
        "NN%")`` tuple ``MainWindow._compute_build_status`` already
        produces - displayed as-is, never recomputed here (see module
        docstring)."""

        if not build_name:
            self.header_label.setText("No build selected")
            self.progress_label.setText("")
            self._build_name = ""
            self._boards = []
            self._completed = set()
            self._detail_index = None
            self._clear_rows()
            self.unavailable_label.hide()
            self.stack.setCurrentWidget(self.overview_page)
            return

        prefix = f"{character_name} — " if character_name else ""
        self.header_label.setText(f"{prefix}{build_name} (Lvl {level})")

        if paragon_status_row:
            emoji, _label, pct_text = paragon_status_row
            self.progress_label.setText(f"{emoji} Paragon Progress: {pct_text}")
        else:
            self.progress_label.setText("")

        is_new_build = build_name != self._build_name

        self._build_name = build_name
        self._completed = completed_boards or set()
        self._boards = (verified_build or {}).get("paragon_boards") or []

        if is_new_build:
            self._detail_index = None
            self.stack.setCurrentWidget(self.overview_page)

        if not self._boards:
            self.unavailable_label.show()
            self._clear_rows()
        else:
            self.unavailable_label.hide()
            self._render_overview_rows()

        if self._detail_index is not None and 0 <= self._detail_index < len(self._boards):
            self._render_detail(self._detail_index)
        elif self.stack.currentWidget() is self.detail_page:
            # The previously-open board no longer exists in this build's
            # list - fall back to Overview instead of a stale/broken view.
            self.stack.setCurrentWidget(self.overview_page)

    def _clear_rows(self):
        for row in self._row_widgets:
            row.setParent(None)
        self._row_widgets = []

    def _render_overview_rows(self):

        self._clear_rows()

        next_index = next(
            (
                i
                for i, board in enumerate(self._boards)
                if LevelingCard._board_id(board, i) not in self._completed
            ),
            None,
        )

        for i, board in enumerate(self._boards):
            board_id = LevelingCard._board_id(board, i)
            is_done = board_id in self._completed
            is_next = i == next_index

            if is_done:
                status_prefix, status_color = "✓", "#3fa860"
            elif is_next:
                status_prefix, status_color = "→", theme.ACCENT_GOLD
            else:
                status_prefix, status_color = "○", theme.TEXT_MUTED

            glyph = board.get("glyph") or "?"
            glyph_level = board.get("glyph_level")
            glyph_text = f"{glyph} (Lv{glyph_level})" if glyph_level else glyph
            title = f"{status_prefix} Board {i + 1} — {glyph_text}"

            nodes = board.get("nodes") or []
            width = board.get("board_width") or 0
            pos = board.get("position") or {}
            detail = (
                f"{len(nodes)} nodes taken on a {width}×{width} grid  •  "
                f"Grid offset ({pos.get('x', 0)}, {pos.get('y', 0)})"
            )

            row = BoardSummaryRow(i, self._rows_container)
            row.set_content(title, detail, status_color)
            row.clicked.connect(self._go_to_board)

            self._rows_layout.insertWidget(self._rows_layout.count() - 1, row)
            self._row_widgets.append(row)

    # ---------------------------------------------------------
    # Board detail navigation
    # ---------------------------------------------------------

    def _go_to_board(self, index: int):

        if not self._boards:
            return

        index = max(0, min(index, len(self._boards) - 1))
        self._detail_index = index
        self._render_detail(index)
        self.stack.setCurrentWidget(self.detail_page)

    def _go_to_prev_board(self):
        if self._detail_index is not None:
            self._go_to_board(self._detail_index - 1)

    def _go_to_next_board(self):
        if self._detail_index is not None:
            self._go_to_board(self._detail_index + 1)

    def _render_detail(self, index: int):

        board = self._boards[index]
        board_id = LevelingCard._board_id(board, index)
        is_done = board_id in self._completed

        glyph = board.get("glyph") or "?"
        glyph_level = board.get("glyph_level")
        glyph_text = f"{glyph} (Lv{glyph_level})" if glyph_level else glyph
        status_text = "✓ Complete" if is_done else "○ Not marked complete"

        self.board_title_label.setText(f"Board {index + 1} — {glyph_text}")
        self.board_position_label.setText(f"BOARD {index + 1}/{len(self._boards)}")

        nodes = board.get("nodes") or []
        width = board.get("board_width") or 0
        pos = board.get("position") or {}

        self.board_meta_label.setText(
            f"{status_text}  •  {len(nodes)} nodes taken on a {width}×{width} grid  •  "
            f"Grid offset ({pos.get('x', 0)}, {pos.get('y', 0)})  •  "
            f"Rotation {board.get('rotation', 0)}"
        )

        self.grid_widget.set_board(board)
        self._current_detail_board_index = index

        self.prev_button.setEnabled(index > 0)
        self.next_button.setEnabled(index < len(self._boards) - 1)

    def _on_node_clicked(self, node: dict):
        dialog = NodeDetailDialog(node, self._current_detail_board_index, self.window())
        dialog.exec()

    # ---------------------------------------------------------
    # Theme / appearance
    # ---------------------------------------------------------

    def refresh_theme(self):

        super().refresh_theme()

        self._hint_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.progress_label.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.board_title_label.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.board_meta_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.legend_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))

        for row in self._row_widgets:
            row.refresh_theme()

        self.grid_widget.update()


class ParagonInterface(QWidget):
    """Top-level nav page wrapping ``ParagonCard`` - same centered,
    width-capped layout ``CharacterInterface``/``BuildAdvisorInterface``
    use."""

    def __init__(self, paragon_card: ParagonCard, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        paragon_card.setMinimumWidth(460)
        paragon_card.setMaximumWidth(820)

        layout.addStretch(1)
        layout.addWidget(paragon_card, 3)
        layout.addStretch(1)
