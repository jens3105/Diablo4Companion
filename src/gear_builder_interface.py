"""Gear Builder page: a dedicated, detail-first top-level page over a
build's ``verified_build.gear`` list - one full card per equipped slot
(Helm, Chest, Gloves, Pants, Boots, Amulet, Ring 1, Ring 2, Weapon(s),
...) instead of the small clickable-chip silhouette on the Character page
(``src/character_interface.py`` / ``src/gear_planner.py``). That page
stays the "at a glance, whole loadout" view; this one is the "read every
real field for one slot at a time, in comfortably large text" view.

Data boundary (see ``src/gear_planner.py``'s module docstring and the
build JSON itself): ``verified_build.gear`` is Maxroll planner data,
already fully decoded, and each entry is
``{slot, item_name, rarity, aspect, sockets, tempering}`` - there is
still no stats/affix/masterworking data anywhere in the source. Every
card here shows the real fields when present, and a literal "DATA
UNAVAILABLE" row for each of Affixes/Stats, Sockets/Gems (only when the
item genuinely has none), Tempering (only when the item genuinely has
no tempered affix, or one that didn't resolve to a known recipe) and
Masterworking. This is expected, not a bug.

Sockets/Gems (Gems System phase): when an item's ``sockets`` list is
non-empty (see ``scripts/maxroll_data_decoder.py``'s ``decode_gear``),
the "Sockets/Gems" row becomes a real, concise summary instead - each
socket's resolved gem/rune name plus a ✓/❌ read out of the exact same
``gear/<build>/socketed_gems`` toggle set the dedicated Gems page
(``src/gems_interface.py``) owns, so the two pages can never disagree.
This row is read-only here (no toggle) - the Gems page is where a
socket actually gets marked done; a socket whose content couldn't be
resolved at all (``kind == "unknown"`` - e.g. Season 15 Soul Splinter
boss materials) shows literally "DATA UNAVAILABLE" for that one socket,
never a fabricated name.

Tempering (Tempering phase; toggle tracking added in the Build
Validation phase): when an item's ``tempering`` list is non-empty (see
``decode_gear``/``_resolve_tempering``), the "Tempering" row shows the
real Tempering Manual name(s) instead of the placeholder - e.g. "Worldly
Endurance (Defensive) — Tier 3" - each with its own "Have it"
``SwitchButton`` (usually just one, but an item can have two tempered
affixes, each tracked separately). Unlike Sockets/Gems, this row is NOT
read-only - there is no separate Tempering page, so this is the only
place a tempered affix ever gets confirmed. Toggling reuses the exact
"dumb pipe" pattern as everything else here: ``tempering_toggled`` ->
``MainWindow.on_tempering_toggled`` -> the shared ``gear/<build>/
tempered_items`` QSettings toggle set (mirrors ``socketed_gems``
exactly, keyed ``"<slot_label>:<temper_index>"``). An item with no
``tempering`` data (no tempered affix at all, or one that didn't
resolve to a known recipe - e.g. a slug shared by more than one Manual,
never guessed) still shows "DATA UNAVAILABLE" for this row, with no
toggle - there is nothing honest to confirm.

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
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon as FIF,
    SingleDirectionScrollArea,
    StrongBodyLabel,
    SwitchButton,
)

from src import item_images, theme
from src.base_card import BaseCard
from src.gear_planner import (
    SlotEntry,
    SlotStatus,
    _rarity_color,
    build_entries_from_verified_gear,
    IMAGE_POOL,
    ItemImageSignals,
    ItemImageTask,
    set_item_pixmap,
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

# Fields this app's data source (see module docstring) never contains
# for any item, on any build - always rendered literally as "DATA
# UNAVAILABLE", never invented. Sockets/Gems and Tempering are the two
# exceptions once an item genuinely has real decoded data for them (see
# ``_sockets_summary_row``/``_tempering_summary_row``).
_UNAVAILABLE_FIELDS = ["Affixes / Stats", "Sockets / Gems", "Tempering", "Masterworking"]


_CARD_IMAGE_PX = 48


class GearSlotCard(QFrame):
    """One equipped slot's full detail card: name, slot, rarity (color-
    coded swatch, reusing ``gear_planner``'s existing rarity palette),
    aspect (when present), the fixed "DATA UNAVAILABLE" rows, and a
    "Have it" toggle - all in generously spaced, full-size labels (no
    ``CaptionLabel``-sized microscopic text, per this phase's explicit
    request)."""

    owned_toggled = Signal(str, bool)  # (key, checked)
    tempering_toggled = Signal(str, bool)  # (key, checked)

    def __init__(
        self,
        entry: SlotEntry,
        sockets: list[dict] | None = None,
        socketed_gems: set[str] | None = None,
        tempering: list[dict] | None = None,
        tempered_items: set[str] | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self._sockets = sockets or []
        self._socketed_gems = socketed_gems or set()
        self._tempering = tempering or []
        self._tempered_items = tempered_items or set()

        self.entry = entry
        self.setObjectName("gearBuilderCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(10)

        # ---- Header: rarity swatch + slot label + "Have it" toggle ----

        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        # The item's own artwork, from the same lookup the Character
        # page uses (src/gear_planner.py -> src/item_images.py). Never a
        # per-build image path: the item's name is what finds the
        # picture, so any build gets its gear illustrated for free.
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setFixedSize(_CARD_IMAGE_PX, _CARD_IMAGE_PX)
        self.image_label.hide()
        header_row.addWidget(self.image_label)

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

        self._apply_image()

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
        # skipped, so nobody mistakes "not decoded" for "not present".
        # Sockets/Gems is the one exception once an item genuinely has
        # sockets (see module docstring) - a real, concise summary row
        # instead of the placeholder. ----

        for field_name in _UNAVAILABLE_FIELDS:
            if field_name == "Sockets / Gems" and self._sockets:
                outer.addWidget(self._sockets_summary_row(entry.slot_label))
            elif field_name == "Tempering" and self._tempering:
                outer.addWidget(self._tempering_summary_row(entry.slot_label))
            else:
                outer.addWidget(self._field_row(field_name, "DATA UNAVAILABLE", muted=True))

        self._apply_style()

    def _apply_image(self):
        """Same rule as the Character page's chips: show it if it is
        cached, fetch it in the background if the catalogue has one, and
        otherwise stay blank - an aspect has no artwork, and showing
        another item's picture would be worse than showing none."""

        if set_item_pixmap(self.image_label, self.entry.item_image, _CARD_IMAGE_PX):
            return

        self.image_label.hide()
        name = self.entry.item_name
        if not name or item_images.image_filename_for_item(name) is None:
            return

        self._image_signals = ItemImageSignals(self)
        self._image_signals.ready.connect(self._on_image_ready)
        IMAGE_POOL.start(ItemImageTask(name, self._image_signals))

    def _on_image_ready(self, path: str):
        self.entry.item_image = path
        set_item_pixmap(self.image_label, path, _CARD_IMAGE_PX)

    def _sockets_summary_row(self, slot_label: str) -> QWidget:
        """Concise real-data summary for the Sockets/Gems row, e.g.
        "2 sockets — Topaz ✓, Nagu (Acrobatic) ❌" - read-only here (the
        Gems page owns the actual toggle, see module docstring), so this
        is purely a formatted read-out of ``self._socketed_gems``, the
        exact same set ``src/gems_interface.py``'s page reads/writes."""

        parts = []
        for idx, socket in enumerate(self._sockets):
            name = socket.get("name")
            kind = socket.get("kind")

            if kind in ("gem", "rune") and name:
                key = f"{slot_label}:{idx}"
                glyph = "✓" if key in self._socketed_gems else "❌"
                parts.append(f"{name} {glyph}")
            else:
                parts.append("DATA UNAVAILABLE")

        count = len(self._sockets)
        label = f"{count} socket{'s' if count != 1 else ''}"
        return self._field_row("Sockets / Gems", f"{label} — " + ", ".join(parts))

    def _tempering_summary_row(self, slot_label: str) -> QWidget:
        """Real Tempering Manual read-out, e.g. "Worldly Endurance
        (Defensive) — Tier 3", each with its own "Have it"
        ``SwitchButton`` (Build Validation phase) - unlike Sockets/Gems,
        this row owns the actual toggle (see module docstring): there is
        no separate Tempering page, so this is the only place a tempered
        affix ever gets confirmed. One sub-row per ``self._tempering``
        entry (usually just one, but the schema is a list) so an item
        with two tempered affixes tracks each independently."""

        row = QWidget(self)
        outer = QVBoxLayout(row)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        label_widget = BodyLabel("Tempering:", row)
        label_widget.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        outer.addWidget(label_widget)

        for idx, t in enumerate(self._tempering):
            entry_row = QWidget(row)
            h = QHBoxLayout(entry_row)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(8)

            text = f"{t['recipe_name']} ({t['group']}) — Tier {t['tier']}"
            value_widget = BodyLabel(text, entry_row)
            value_widget.setWordWrap(True)
            value_widget.setTextColor(QColor(theme.TEXT_PRIMARY), QColor(theme.TEXT_PRIMARY))
            h.addWidget(value_widget, 1)

            key = f"{slot_label}:{idx}"
            toggle = SwitchButton(entry_row)
            toggle.setOnText("Have it")
            toggle.setOffText("Missing")
            toggle.setChecked(key in self._tempered_items)
            toggle.checkedChanged.connect(
                lambda checked, k=key: self.tempering_toggled.emit(k, checked)
            )
            h.addWidget(toggle)

            outer.addWidget(entry_row)

        return row

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
    tempering_toggled = Signal(str, bool)

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

    def set_gear(
        self,
        owned_names: set[str],
        verified_build: dict | None,
        socketed_gems: set[str] | None = None,
        tempered_items: set[str] | None = None,
    ):
        """``verified_build`` is ``LeveleingManager.get_verified_build``'s
        return value. Only its ``gear`` list drives this page (see module
        docstring for why the legacy ``key_items``/``key_aspects`` path
        isn't used here) - a build with none gets the top-level DATA
        UNAVAILABLE state instead. ``socketed_gems`` is ``MainWindow.
        _load_socketed_gems``'s set for this build - only used to render
        each item's real Sockets/Gems summary row (see
        ``GearSlotCard._sockets_summary_row``); omit it and every item
        just shows its sockets as all-missing. ``tempered_items`` is
        ``MainWindow._load_tempered_items``'s set for this build - drives
        each item's real Tempering row toggle state (see
        ``GearSlotCard._tempering_summary_row``); omit it and every
        tempering toggle starts unchecked."""

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

        # Keyed by slot label (unique per entry, including the " 1"/" 2"
        # suffix decode_gear already applies to duplicate slots - see its
        # docstring) so each card gets exactly its own item's sockets,
        # never another Ring/weapon's.
        sockets_by_slot = {
            item["slot"]: item["sockets"] for item in verified_gear if item.get("sockets")
        }
        tempering_by_slot = {
            item["slot"]: item["tempering"] for item in verified_gear if item.get("tempering")
        }

        owned_count = sum(1 for entry in verified_gear if entry["item_name"] in owned_names)
        self.rollup_label.setText(f"{owned_count} / {len(verified_gear)} items equipped")

        for bucket in _CARD_BUCKET_ORDER:
            for entry in by_bucket.get(bucket, []):
                self._add_card(
                    entry,
                    sockets_by_slot.get(entry.slot_label),
                    socketed_gems,
                    tempering_by_slot.get(entry.slot_label),
                    tempered_items,
                )

    def _add_card(
        self,
        entry: SlotEntry,
        sockets: list[dict] | None = None,
        socketed_gems: set[str] | None = None,
        tempering: list[dict] | None = None,
        tempered_items: set[str] | None = None,
    ):

        card = GearSlotCard(
            entry, sockets, socketed_gems, tempering, tempered_items, self._cards_container
        )
        card.owned_toggled.connect(self.item_owned_changed)
        card.tempering_toggled.connect(self.tempering_toggled)
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
