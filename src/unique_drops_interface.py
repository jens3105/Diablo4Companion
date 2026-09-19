"""Unique Drop Locations page.

Answers two questions from one filterable list, reusing the exact same
filtered results for both directions instead of building two separate
screens:

- "Which boss drops this Unique?" - type a name in the search box, or
  pick Class/Slot in the filters, then click a result to see its full
  detail (target boss, boss zone, key/tribute requirement).
- "What Uniques can I target-farm from this boss?" - pick the boss in
  the Boss filter; the list becomes exactly that boss's farmable
  Uniques, and a small boss-info banner shows its zone/key requirement.

See src/unique_data.py's module docstring for how UNIQUES is sourced/
verified. Items with no confirmed target-farm boss are simply absent
from this list - the page never displays a guessed boss."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QListWidgetItem, QSizePolicy, QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    ComboBox,
    FluentIcon as FIF,
    ListWidget,
    SearchLineEdit,
    StrongBodyLabel,
)

from src import theme
from src.base_card import BaseCard
from src.unique_data import UNIQUES

_ALL = "All"


def _sorted_values(key: str) -> list[str]:
    values = sorted({entry[key] for entry in UNIQUES})
    return [_ALL] + values


class UniqueDropsCard(BaseCard):
    """Search + filters + results list + detail panel for Unique Drop
    Locations. Filters combine with AND (Class + Slot + Boss + Search
    text all narrow the same list together)."""

    def __init__(self, parent=None):
        super().__init__("UNIQUE DROP LOCATIONS", icon=FIF.CERTIFICATE, parent=parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.search_input = SearchLineEdit(self.content)
        self.search_input.setPlaceholderText("Search Unique...")
        self.search_input.textChanged.connect(self._refresh_results)
        self.add_widget(self.search_input)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        self.class_combo = ComboBox(self.content)
        self.class_combo.addItems(_sorted_values("class"))
        self.class_combo.currentIndexChanged.connect(self._refresh_results)
        filter_row.addWidget(CaptionLabel("Class:", self.content))
        filter_row.addWidget(self.class_combo)

        self.slot_combo = ComboBox(self.content)
        self.slot_combo.addItems(_sorted_values("slot"))
        self.slot_combo.currentIndexChanged.connect(self._refresh_results)
        filter_row.addWidget(CaptionLabel("Slot:", self.content))
        filter_row.addWidget(self.slot_combo)

        self.boss_combo = ComboBox(self.content)
        self.boss_combo.addItems(_sorted_values("target_boss"))
        self.boss_combo.currentIndexChanged.connect(self._refresh_results)
        filter_row.addWidget(CaptionLabel("Boss:", self.content))
        filter_row.addWidget(self.boss_combo)

        filter_row.addStretch(1)
        self.add_layout(filter_row)

        self.boss_info_label = CaptionLabel("", self.content)
        self.boss_info_label.setWordWrap(True)
        self.boss_info_label.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.boss_info_label.hide()
        self.add_widget(self.boss_info_label)

        body_row = QHBoxLayout()
        body_row.setSpacing(16)

        self.results_list = ListWidget(self.content)
        self.results_list.setMinimumWidth(280)
        self.results_list.itemSelectionChanged.connect(self._on_selection_changed)
        body_row.addWidget(self.results_list, 1)

        self.detail_label = BodyLabel(
            "Select a Unique to see its target boss and location.",
            self.content,
        )
        self.detail_label.setWordWrap(True)
        self.detail_label.setAlignment(Qt.AlignTop)
        self.detail_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.detail_label.setMinimumWidth(280)
        body_row.addWidget(self.detail_label, 1)

        self.add_layout(body_row)

        if not UNIQUES:
            no_data = BodyLabel("DATA UNAVAILABLE - no verified Unique drop data yet.", self.content)
            no_data.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
            self.add_widget(no_data)

        self._refresh_results()

    # ---------------------------------------------------------
    # Filtering
    # ---------------------------------------------------------

    def _matching_entries(self) -> list[dict]:
        query = self.search_input.text().strip().lower()
        class_filter = self.class_combo.currentText()
        slot_filter = self.slot_combo.currentText()
        boss_filter = self.boss_combo.currentText()

        results = []
        for entry in UNIQUES:
            if query and query not in entry["name"].lower():
                continue
            if class_filter != _ALL and entry["class"] != class_filter:
                continue
            if slot_filter != _ALL and entry["slot"] != slot_filter:
                continue
            if boss_filter != _ALL and entry["target_boss"] != boss_filter:
                continue
            results.append(entry)
        return results

    def _refresh_results(self):
        boss_filter = self.boss_combo.currentText()
        if boss_filter != _ALL:
            boss_entries = [e for e in UNIQUES if e["target_boss"] == boss_filter]
            zone = boss_entries[0]["boss_zone"] if boss_entries else "DATA UNAVAILABLE"
            key = boss_entries[0]["key_required"] if boss_entries else "DATA UNAVAILABLE"
            self.boss_info_label.setText(f"{boss_filter} — Zone: {zone} · Key: {key}")
            self.boss_info_label.show()
        else:
            self.boss_info_label.hide()

        self.results_list.clear()
        for entry in self._matching_entries():
            text = f"{entry['name']}   ·   {entry['class']} · {entry['slot']}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, entry)
            self.results_list.addItem(item)

        if self.results_list.count():
            self.results_list.setCurrentRow(0)
        else:
            self.detail_label.setText("No Uniques match the current search/filters.")

    def _on_selection_changed(self):
        item = self.results_list.currentItem()
        if item is None:
            return
        entry = item.data(Qt.UserRole)
        self._show_detail(entry)

    def _show_detail(self, entry: dict):
        confidence_text = f"{entry['confidence']} ({entry['sources']} source(s))"
        notes = entry.get("notes") or "—"
        self.detail_label.setText(
            f"{entry['name']}\n"
            f"Class: {entry['class']}\n"
            f"Slot: {entry['slot']}\n"
            f"Target boss: {entry['target_boss']}\n"
            f"Boss location: {entry['boss_zone']}\n"
            f"Key/Tribute required: {entry['key_required']}\n"
            f"Confidence: {confidence_text}\n"
            f"Notes: {notes}"
        )

    # ---------------------------------------------------------
    # Theme
    # ---------------------------------------------------------

    def refresh_theme(self):
        super().refresh_theme()

        self.boss_info_label.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.detail_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))


class UniqueDropsInterface(QWidget):
    """Top-level nav page wrapping UniqueDropsCard - same pattern as
    GemsInterface/GearBuilderInterface (a single centered card)."""

    def __init__(self, card: UniqueDropsCard, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(card)
