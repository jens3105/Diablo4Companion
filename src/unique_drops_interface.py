"""Unique Drop Locations page.

Answers two questions from one filterable list, reusing the exact same
results for both directions instead of building two separate screens:

- "Which boss drops this Unique?" - type a name (Unique or boss) in the
  search box, or pick Class/Slot/Type in the filters, then click a
  result card to see its full detail (target boss, boss zone, key/
  tribute requirement, tier).
- "What Uniques can I target-farm from this boss?" - pick the boss in
  the Boss filter; the list becomes exactly that boss's farmable
  Uniques, and a boss-detail panel shows its tier/zone/key/key source.

See src/unique_data.py and src/boss_data.py's module docstrings for how
this data is sourced/verified, and src/unique_drop_service.py for the
data access layer this UI calls into - it never reads UNIQUES/BOSSES or
hardcodes a loot table itself."""

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    ComboBox,
    FluentIcon as FIF,
    PushButton,
    SearchLineEdit,
    SingleDirectionScrollArea,
    StrongBodyLabel,
)

from src import item_icon_assets, theme, unique_drop_service as service
from src.base_card import BaseCard

_ALL = "All"
_UNKNOWN = "DATA UNAVAILABLE"


def _sorted_values(items: list[dict], key: str) -> list[str]:
    values = sorted({entry[key] for entry in items if entry.get(key)})
    return [_ALL] + values


def _boss_names_for(unique: dict) -> str:
    bosses = service.get_bosses_for_unique(unique["id"])
    if bosses:
        return ", ".join(b["name"] for b in bosses)
    return unique.get("notes") or _UNKNOWN


def _resolve_asset_path(relative_path: str) -> str:
    """Same sys.frozen-relative-to-exe pattern as LevelingManager's
    builds_dir lookup (src/managers/leveling_manager.py) - a frozen
    PyInstaller build's __file__-relative paths aren't reliable."""

    if getattr(sys, "frozen", False):
        repo_root = os.path.dirname(os.path.abspath(sys.executable))
    else:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(repo_root, relative_path)


def _load_item_pixmap(image_path: str | None) -> QPixmap | None:
    """Loads a Unique's image if - and only if - ``image_path`` is set
    AND the file actually exists AND Qt can decode it. Returns None for
    every other case (unset/missing/corrupt) so the caller shows the
    neutral placeholder instead - this never crashes the card."""

    if not image_path:
        return None

    full_path = image_path if os.path.isabs(image_path) else _resolve_asset_path(image_path)
    if not os.path.isfile(full_path):
        return None

    pixmap = QPixmap(full_path)
    if pixmap.isNull():
        return None

    return pixmap.scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def _resolve_icon_for(unique: dict) -> str | None:
    """User-provided icon lookup (see src/item_icon_assets.py and
    scripts/import_item_icons.py) takes priority - falls back to the
    data record's own ``image`` field only if explicitly set (never
    guessed from the display name alone)."""

    return item_icon_assets.find_icon_path(unique["id"]) or unique.get("image")


class UniqueItemCard(QFrame):
    """One compact result row: image placeholder + name/type/class/slot
    + drop source. Never crashes on a missing image - shows a neutral
    placeholder box instead."""

    clicked = Signal(str)  # unique id

    def __init__(self, unique: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("uniqueItemCard")
        self._unique_id = unique["id"]
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(12)

        self.image_box = QFrame(self)
        self.image_box.setFixedSize(48, 48)
        self.image_box.setStyleSheet(
            f"background-color: {theme.SURFACE_ALT}; border: 1px solid {theme.BORDER}; border-radius: 6px;"
        )
        image_layout = QVBoxLayout(self.image_box)
        image_layout.setContentsMargins(0, 0, 0, 0)

        pixmap = _load_item_pixmap(_resolve_icon_for(unique))
        if pixmap is not None:
            image_label = QLabel(self.image_box)
            image_label.setPixmap(pixmap)
            image_label.setAlignment(Qt.AlignCenter)
            image_layout.addWidget(image_label)
        else:
            placeholder = CaptionLabel("No\nImage", self.image_box)
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
            image_layout.addWidget(placeholder)

        layout.addWidget(self.image_box)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        name_label = StrongBodyLabel(unique["name"], self)
        text_col.addWidget(name_label)

        meta_label = CaptionLabel(
            f"{unique['type']} · {unique['class']} · {unique['slot']}", self
        )
        meta_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        text_col.addWidget(meta_label)

        source_label = CaptionLabel(f"Drop source: {_boss_names_for(unique)}", self)
        source_label.setWordWrap(True)
        source_label.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        text_col.addWidget(source_label)

        layout.addLayout(text_col, 1)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._unique_id)
        super().mouseReleaseEvent(event)


class UniqueDropsCard(BaseCard):
    """Search + filters + result cards + detail panel for Unique Drop
    Locations. Filters combine with AND (Class + Slot + Boss + Type +
    Search text all narrow the same list together)."""

    def __init__(self, parent=None):
        super().__init__("UNIQUE DROP LOCATIONS", icon=FIF.CERTIFICATE, parent=parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.search_input = SearchLineEdit(self.content)
        self.search_input.setPlaceholderText("Search Unique / Boss...")
        self.search_input.textChanged.connect(self._refresh_results)
        self.add_widget(self.search_input)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        uniques = service.all_uniques()

        self.class_combo = ComboBox(self.content)
        self.class_combo.addItems(_sorted_values(uniques, "class"))
        self.class_combo.currentIndexChanged.connect(self._refresh_results)
        filter_row.addWidget(CaptionLabel("Class:", self.content))
        filter_row.addWidget(self.class_combo)

        self.slot_combo = ComboBox(self.content)
        self.slot_combo.addItems(_sorted_values(uniques, "slot"))
        self.slot_combo.currentIndexChanged.connect(self._refresh_results)
        filter_row.addWidget(CaptionLabel("Slot:", self.content))
        filter_row.addWidget(self.slot_combo)

        self.boss_combo = ComboBox(self.content)
        self.boss_combo.addItems([_ALL] + [b["name"] for b in service.all_bosses()])
        self.boss_combo.currentIndexChanged.connect(self._refresh_results)
        filter_row.addWidget(CaptionLabel("Boss:", self.content))
        filter_row.addWidget(self.boss_combo)

        self.type_combo = ComboBox(self.content)
        self.type_combo.addItems([_ALL, "Unique", "Mythic Unique"])
        self.type_combo.currentIndexChanged.connect(self._refresh_results)
        filter_row.addWidget(CaptionLabel("Type:", self.content))
        filter_row.addWidget(self.type_combo)

        self.reset_button = PushButton("Reset Filters", self.content)
        self.reset_button.clicked.connect(self._reset_filters)
        filter_row.addWidget(self.reset_button)

        filter_row.addStretch(1)
        self.add_layout(filter_row)

        self.boss_info_label = CaptionLabel("", self.content)
        self.boss_info_label.setWordWrap(True)
        self.boss_info_label.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.boss_info_label.hide()
        self.add_widget(self.boss_info_label)

        body_row = QHBoxLayout()
        body_row.setSpacing(16)

        self.results_scroll = SingleDirectionScrollArea(self.content, orient=Qt.Vertical)
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setStyleSheet("QScrollArea{background: transparent; border: none;}")
        self.results_scroll.setMinimumWidth(320)

        self.results_host = QWidget()
        self.results_host.setStyleSheet("background: transparent;")
        self.results_layout = QVBoxLayout(self.results_host)
        self.results_layout.setContentsMargins(0, 0, 4, 0)
        self.results_layout.setSpacing(6)
        self.results_layout.addStretch(1)
        self.results_scroll.setWidget(self.results_host)

        body_row.addWidget(self.results_scroll, 1)

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

        if not uniques:
            no_data = BodyLabel("DATA UNAVAILABLE - no verified Unique drop data yet.", self.content)
            no_data.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
            self.add_widget(no_data)

        self._cards: list[UniqueItemCard] = []
        self._refresh_results()

    # ---------------------------------------------------------
    # Filtering
    # ---------------------------------------------------------

    def _matching_entries(self) -> list[dict]:
        query = self.search_input.text().strip().lower()
        class_filter = self.class_combo.currentText()
        slot_filter = self.slot_combo.currentText()
        boss_filter = self.boss_combo.currentText()
        type_filter = self.type_combo.currentText()

        results = []
        for entry in service.all_uniques():
            if class_filter != _ALL and entry["class"] != class_filter:
                continue
            if slot_filter != _ALL and entry["slot"] != slot_filter:
                continue
            if type_filter != _ALL and entry["type"] != type_filter:
                continue
            if boss_filter != _ALL:
                boss_names = {b["name"] for b in service.get_bosses_for_unique(entry["id"])}
                if boss_filter not in boss_names:
                    continue
            if query:
                boss_names = " ".join(b["name"] for b in service.get_bosses_for_unique(entry["id"]))
                haystack = f"{entry['name']} {boss_names}".lower()
                if query not in haystack:
                    continue
            results.append(entry)
        return results

    def _reset_filters(self):
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        for combo in (self.class_combo, self.slot_combo, self.boss_combo, self.type_combo):
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self._refresh_results()

    def _refresh_results(self):
        boss_filter = self.boss_combo.currentText()
        if boss_filter != _ALL:
            boss = next((b for b in service.all_bosses() if b["name"] == boss_filter), None)
            if boss:
                self.boss_info_label.setText(
                    f"{boss['name']} — Tier: {boss['tier']} · Zone: {boss['location']} · "
                    f"Key: {boss['key']} (obtained via: {boss['key_source']})"
                )
                self.boss_info_label.show()
        else:
            self.boss_info_label.hide()

        for card in self._cards:
            card.setParent(None)
        self._cards.clear()

        entries = self._matching_entries()
        for entry in entries:
            card = UniqueItemCard(entry, self.results_host)
            card.clicked.connect(self._show_detail)
            self.results_layout.insertWidget(self.results_layout.count() - 1, card)
            self._cards.append(card)

        if entries:
            self._show_detail(entries[0]["id"])
        else:
            self.detail_label.setText("No Uniques match the current search/filters.")

    def _show_detail(self, unique_id: str):
        entry = service.get_unique(unique_id)
        if entry is None:
            return

        bosses = service.get_bosses_for_unique(unique_id)
        description = entry.get("description") or _UNKNOWN
        notes = entry.get("notes")

        if bosses:
            boss_lines = "\n".join(
                f"  - {b['name']} — Tier: {b['tier']} · Zone: {b['location']} · "
                f"Key: {b['key']} (obtained via: {b['key_source']})"
                for b in bosses
            )
        else:
            boss_lines = f"  {notes or _UNKNOWN}"

        confidence_text = f"{entry['confidence']} ({entry['sources_count']} source(s))"

        text = (
            f"{entry['name']}\n"
            f"Type: {entry['type']}\n"
            f"Class: {entry['class']}\n"
            f"Slot: {entry['slot']}\n"
            f"Effect: {description}\n"
            f"Target boss(es):\n{boss_lines}\n"
            f"Confidence: {confidence_text}\n"
            f"Source: {entry['source']}"
        )
        if notes and bosses:
            text += f"\nNotes: {notes}"

        self.detail_label.setText(text)

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
