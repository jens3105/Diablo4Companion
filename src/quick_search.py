from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QDialog, QListWidgetItem, QVBoxLayout

from qfluentwidgets import ListWidget, SearchLineEdit

from src import theme


class QuickSearchDialog(QDialog):
    """Ctrl+K quick-search overlay (Phase 25 - "very fast access during
    gameplay").

    qfluentwidgets has no ready-made command-palette/flyout component
    that actually fits this (``SearchLineEdit`` is just a styled line
    edit, not a results list) - so this is deliberately a plain, minimal
    modal ``QDialog``: a ``SearchLineEdit`` + a filtered ``ListWidget``,
    styled to match the app instead of a bespoke widget.

    This dialog knows nothing about builds/pages/skills/gear - it's
    handed a flat list of ``{"label", "category", "action"}`` dicts
    (rebuilt fresh by ``MainWindow`` every time it's opened, so it
    always reflects the active build) and just filters/activates them.
    ``action`` is a zero-arg callable the caller already owns (bound to
    ``MainWindow.on_build_changed``, ``switchTo``, etc.) - this dialog
    never duplicates any of that switching/navigation logic itself.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Quick Search")
        self.setModal(True)
        self.resize(480, 420)
        self.setStyleSheet(
            f"QDialog {{ background-color: {theme.SURFACE}; border: 1px solid {theme.BORDER}; }}"
        )

        self._items: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.search_input = SearchLineEdit(self)
        self.search_input.setPlaceholderText("Search builds, pages, skills, gear...")
        self.search_input.textChanged.connect(self._on_text_changed)
        self.search_input.returnPressed.connect(self._activate_current)
        # Up/Down while the line edit has focus should move the result
        # list's selection instead of moving the cursor inside the text.
        self.search_input.installEventFilter(self)
        layout.addWidget(self.search_input)

        self.list_widget = ListWidget(self)
        self.list_widget.itemActivated.connect(lambda _item: self._activate_current())
        layout.addWidget(self.list_widget, 1)

    # ---------------------------------------------------------
    # Population / filtering
    # ---------------------------------------------------------

    def set_items(self, items: list[dict]):
        """``items``: list of ``{"label", "category", "action"}`` dicts,
        already flattened/ordered by the caller. Clears any previous
        search text so every open starts from the full list."""

        self._items = items
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        self._render(items)

    def _render(self, items: list[dict]):

        self.list_widget.clear()

        for entry in items:
            category = entry.get("category", "")
            text = f"{entry['label']}   ·   {category}" if category else entry["label"]
            list_item = QListWidgetItem(text)
            list_item.setData(Qt.UserRole, entry)
            self.list_widget.addItem(list_item)

        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def _on_text_changed(self, text: str):

        query = text.strip().lower()

        if not query:
            self._render(self._items)
            return

        filtered = [
            entry
            for entry in self._items
            if query in entry["label"].lower() or query in entry.get("category", "").lower()
        ]
        self._render(filtered)

    # ---------------------------------------------------------
    # Activation / keyboard
    # ---------------------------------------------------------

    def _activate_current(self):

        item = self.list_widget.currentItem()

        if item is None:
            return

        entry = item.data(Qt.UserRole)
        self.accept()

        action = entry.get("action") if entry else None
        if action:
            action()

    def eventFilter(self, obj, event):

        if obj is self.search_input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            count = self.list_widget.count()

            if key == Qt.Key_Down and count:
                self.list_widget.setCurrentRow(min(self.list_widget.currentRow() + 1, count - 1))
                return True

            if key == Qt.Key_Up and count:
                self.list_widget.setCurrentRow(max(self.list_widget.currentRow() - 1, 0))
                return True

        return super().eventFilter(obj, event)

    def showEvent(self, event):

        super().showEvent(event)
        self.search_input.setFocus()
