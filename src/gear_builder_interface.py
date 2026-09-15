"""Gear Builder page: a dedicated, detail-first top-level page over a
build's ``verified_build.gear`` list - one full card per equipped slot
(Helm, Chest, Gloves, Pants, Boots, Amulet, Ring 1, Ring 2, Weapon(s),
...) instead of the small clickable-chip silhouette on the Character page
(``src/character_interface.py`` / ``src/gear_planner.py``). That page
stays the "at a glance, whole loadout" view; this one is the "read every
real field for one slot at a time, in comfortably large text" view.

Data boundary (see ``src/gear_planner.py``'s module docstring and the
build JSON itself): ``verified_build.gear`` is Maxroll planner data,
already fully decoded, and it is ONLY ``{slot, item_name, rarity,
aspect}`` per entry - there is no stats/affix/socket/gem/tempering/
masterworking data anywhere in the source. Every card here shows those 4
real fields when present, and a literal "DATA UNAVAILABLE" row for each
of Affixes/Stats, Sockets/Gems, Tempering and Masterworking - on every
single item, with no exceptions. This is expected, not a bug.

Builds with no ``verified_build`` at all (today, only Heartseeker Rogue -
its guide predates the Maxroll planner decode and only has prose-derived
``key_items``/``key_aspects``, which carry none of the 4 real fields
either) get a clean top-level "DATA UNAVAILABLE" page state, the same
pattern ``paragon_interface.ParagonCard`` already uses for the same
build - not the Character page's legacy-checklist fallback, since this
page's whole point is showing the *verified* per-slot fields. Nothing
about Character's own legacy-gear support changes.

Ownership: reuses the exact same ``gear/<build>/owned_items`` QSettings
set as the Character page - ``MainWindow._load_owned_items``/
``_save_owned_items`` - via the same "dumb pipe" signal pattern
(``item_owned_changed`` -> ``MainWindow.on_gear_owned_changed``) so a
toggle flipped here and a toggle flipped on the Character page are
always the same underlying state, never two models to keep in sync.

Card-vs-dialog (roadmap Phase 4, "click for details"): every field the
detail view would show is already on the summary card itself (that's
the whole premise of this page), so there is no separate detail dialog -
adding one would just repeat the same six lines behind an extra click.
The "Have it" ``SwitchButton`` lives directly on the card instead.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon as FIF,
    SingleDirectionScrollArea,
    StrongBodyLabel,
    SwitchButton,
)

from src import theme
from src.base_card import BaseCard
from src.gear_planner import (
    SlotEntry,
    SlotStatus,
    _rarity_color,
    build_entries_from_verified_gear,
)

# Fixed rendering order for the main body cards - see module docstring's
# slot list. Ring/Weapon buckets can hold more than one real entry
# (dual-wield, Ring 1 + Ring 2, an offhand/shield/focus) - every entry in
# the bucket gets its own card, in the order Maxroll's decoded data lists
# them, never a hardcoded count.
_CARD_BUCKET_ORDER = [
    "HELM",
    "CHEST",
    "GLOVES",
    "PANTS",
    "BOOTS",
    "AMULET",
    "RING",
    "WEAPON",
]

# The four fields this app's data source (see module docstring) simply
# never contains for any item, on any build - always rendered literally
# as "DATA UNAVAILABLE", never invented.
_UNAVAILABLE_FIELDS = ["Affixes / Stats", "Sockets / Gems", "Tempering", "Masterworking"]


class GearSlotCard(QFrame):
    """One equipped slot's full detail card: name, slot, rarity (color-
    coded swatch, reusing ``gear_planner``'s existing rarity palette),
    aspect (when present), the fixed "DATA UNAVAILABLE" rows, and a
    "Have it" toggle - all in generously spaced, full-size labels (no
    ``CaptionLabel``-sized microscopic text, per this phase's explicit
    request)."""

    owned_toggled = Signal(str, bool)  # (key, checked)

    def __init__(self, entry: SlotEntry, parent=None):
        super().__init__(parent)

        self.entry = entry
        self.setObjectName("gearBuilderCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(10)

        # ---- Header: rarity swatch + slot label + "Have it" toggle ----

        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        self.swatch = QFrame(self)
        self.swatch.setFixedSize(14, 14)
        header_row.addWidget(self.swatch)

        self.slot_label = StrongBodyLabel(entry.slot_label, self)
        self.slot_label.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        header_row.addWidget(self.slot_label)
        header_row.addStretch(1)

        self.toggle = SwitchButton(self)
        self.toggle.setOnText("Have it")
        self.toggle.setOffText("Missing")
        self.toggle.setChecked(entry.status == SlotStatus.CORRECT)
        self.toggle.checkedChanged.connect(self._on_toggled)
        self.toggle.setEnabled(entry.key is not None)
        header_row.addWidget(self.toggle)

        outer.addLayout(header_row)

        # ---- Item name ----

        self.name_label = BodyLabel(entry.item_name or "— Not required —", self)
        self.name_label.setWordWrap(True)
        outer.addWidget(self.name_label)

        # ---- Real fields present in the verified data ----

        if entry.rarity:
            outer.addWidget(self._field_row("Rarity", entry.rarity.title()))

        if entry.aspect:
            outer.addWidget(self._field_row("Aspect", entry.aspect))

        if not entry.item_name:
            note = CaptionLabel("No build requirement for this slot.", self)
            note.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
            outer.addWidget(note)

        # ---- Fields this data source never has - shown honestly, not
        # skipped, so nobody mistakes "not decoded" for "not present". ----

        for field_name in _UNAVAILABLE_FIELDS:
            outer.addWidget(self._field_row(field_name, "DATA UNAVAILABLE", muted=True))

        self._apply_style()

    def _field_row(self, label: str, value: str, muted: bool = False) -> QWidget:

        row = QWidget(self)
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)

        label_widget = BodyLabel(f"{label}:", row)
        label_widget.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        h.addWidget(label_widget)

        value_color = theme.TEXT_MUTED if muted else theme.TEXT_PRIMARY
        value_widget = BodyLabel(value, row)
        value_widget.setWordWrap(True)
        value_widget.setTextColor(QColor(value_color), QColor(value_color))
        h.addWidget(value_widget, 1)

        return row

    def _apply_style(self):

        if self.entry.item_name:
            self.swatch.setStyleSheet(
                f"background-color: {_rarity_color(self.entry.rarity)}; border-radius: 3px;"
            )
        else:
            self.swatch.setStyleSheet(
                f"background-color: transparent; border: 1px solid {theme.BORDER}; border-radius: 3px;"
            )

        self.setStyleSheet(
            f"""
            QFrame#gearBuilderCard {{
                background-color: {theme.SURFACE_ALT};
                border-radius: 10px;
                border: 1px solid {theme.BORDER};
            }}
            """
        )

    def _on_toggled(self, checked: bool):
        if self.entry.key is not None:
            self.owned_toggled.emit(self.entry.key, checked)

    def refresh_theme(self):
        self._apply_style()
        self.slot_label.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))


class GearBuilderCard(BaseCard):
    """Top-level Gear Builder card: header (follows the active character/
    build/level, same as Character/Paragon - no second selector), a
    rollup line, and either a "DATA UNAVAILABLE" page state (no
    ``verified_build`` at all) or one ``GearSlotCard`` per real gear
    entry, in a scrollable column."""

    item_owned_changed = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__("GEAR BUILDER", icon=FIF.SHOPPING_CART, parent=parent)

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

        self.rollup_label = StrongBodyLabel("", self.content)
        self.rollup_label.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.add_widget(self.rollup_label)

        self.unavailable_label = BodyLabel(
            "DATA UNAVAILABLE — no verified Maxroll Planner profile for "
            "this build's gear yet.",
            self.content,
        )
        self.unavailable_label.setWordWrap(True)
        self.unavailable_label.hide()
        self.add_widget(self.unavailable_label)

        scroll = SingleDirectionScrollArea(self.content, orient=Qt.Vertical)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background: transparent; border: none;}")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        inner = QVBoxLayout(container)
        inner.setContentsMargins(0, 0, 0, 4)
        inner.setSpacing(12)
        inner.addStretch()

        scroll.setWidget(container)

        self._cards_container = container
        self._cards_layout = inner
        self._cards: list[GearSlotCard] = []

        self.add_widget(scroll)
        self.content_layout.setStretch(self.content_layout.count() - 1, 1)

    # ---------------------------------------------------------
    # Header (character/build/level follow-along - see module docstring)
    # ---------------------------------------------------------

    def set_header(self, character_name: str, build_name: str, level: int):

        if not build_name:
            self.header_label.setText("No build selected")
            return

        prefix = f"{character_name} — " if character_name else ""
        self.header_label.setText(f"{prefix}{build_name} (Lvl {level})")

    # ---------------------------------------------------------
    # Population
    # ---------------------------------------------------------

    def set_gear(self, owned_names: set[str], verified_build: dict | None):
        """``verified_build`` is ``LeveleingManager.get_verified_build``'s
        return value. Only its ``gear`` list drives this page (see module
        docstring for why the legacy ``key_items``/``key_aspects`` path
        isn't used here) - a build with none gets the top-level DATA
        UNAVAILABLE state instead."""

        self._clear_cards()

        verified_gear = (verified_build or {}).get("gear") or []

        if not verified_gear:
            self.rollup_label.setText("")
            self.unavailable_label.show()
            return

        self.unavailable_label.hide()

        entries = build_entries_from_verified_gear(verified_gear, owned_names)
        by_bucket: dict[str, list[SlotEntry]] = {}
        for entry in entries:
            by_bucket.setdefault(entry.bucket, []).append(entry)

        owned_count = sum(1 for entry in verified_gear if entry["item_name"] in owned_names)
        self.rollup_label.setText(f"{owned_count} / {len(verified_gear)} items equipped")

        for bucket in _CARD_BUCKET_ORDER:
            for entry in by_bucket.get(bucket, []):
                self._add_card(entry)

    def _add_card(self, entry: SlotEntry):

        card = GearSlotCard(entry, self._cards_container)
        card.owned_toggled.connect(self.item_owned_changed)
        self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)
        self._cards.append(card)

    def _clear_cards(self):
        for card in self._cards:
            card.setParent(None)
        self._cards = []

    # ---------------------------------------------------------
    # Theme / appearance
    # ---------------------------------------------------------

    def refresh_theme(self):

        super().refresh_theme()

        self._hint_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.rollup_label.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        for card in self._cards:
            card.refresh_theme()


class GearBuilderInterface(QWidget):
    """Top-level nav page wrapping ``GearBuilderCard`` - same centered,
    width-capped layout ``CharacterInterface``/``ParagonInterface`` use."""

    def __init__(self, gear_builder_card: GearBuilderCard, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        gear_builder_card.setMinimumWidth(460)
        gear_builder_card.setMaximumWidth(820)

        layout.addStretch(1)
        layout.addWidget(gear_builder_card, 3)
        layout.addStretch(1)
