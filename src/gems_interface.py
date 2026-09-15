"""Gems page: a dedicated top-level page over each equipped slot's real
socket contents.

Data source (see ``scripts/maxroll_data_decoder.py``'s ``decode_gear``
docstring): each equipped item instance in a Maxroll planner profile
already carries a real ``sockets`` list - the guide author's actual
socketed gem/rune slugs for that exact item, resolved by the decoder into
``{slug, kind ("gem"/"rune"/"unknown"), name, effect_text}``. This page
lists every equipped slot that has a non-empty ``sockets`` list (skipping
every slot with none - Boots/Gloves/Talismans never have sockets in real
Diablo 4, see the decoder's own item-type survey) and shows, per socket:
the expected gem/rune's real name + effect text, a "Have it" toggle, and
a status glyph.

Ownership: a NEW toggle set, ``gear/<build>/socketed_gems`` (``MainWindow.
_load_socketed_gems``/``_save_socketed_gems``), keyed per-socket as
``"<slot_label>:<socket_index>"`` - the exact same pattern the Paragon
page's per-node ``completed_nodes`` set already established (see
``MainWindow._completed_paragon_nodes_key``). This is the SAME store
``gear_builder_interface.GearSlotCard``'s "Sockets/Gems" summary row
reads (read-only there - see that module's docstring), so a toggle
flipped here is instantly reflected on the Gear Builder page too - never
two toggle stores for the same fact.

Status model: only two real states exist, ✓ (confirmed socketed) and ❌
(not yet confirmed) - there is no "wrong gem/rune" detection anywhere in
this app. This mirrors ``gear_planner.py``'s own documented limitation
exactly: no independent "what's actually socketed on the real character"
data exists anywhere, only a manual self-report toggle against the
*expected* content, so nothing here can ever architecturally produce a
"wrong gem" status - it simply isn't wired up, same as ``SlotStatus.
INCORRECT`` never fires today. A socket whose content slug couldn't be
resolved to a real gem/rune at all (``kind == "unknown"`` - confirmed to
happen for Season 15's "Soul Splinter" boss-material slugs, which aren't
gems/runes and aren't in the decoder's game-data dictionary at all) shows
literally "DATA UNAVAILABLE" with its toggle disabled, never a fabricated
name or a fake status.

Builds with no ``verified_build`` at all (today, only Heartseeker Rogue)
or with a ``verified_build`` whose items carry no sockets at all get a
clean, honest top-level message explaining why there's nothing to show -
never a crash, never a misleadingly empty page."""

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

_STATUS_DONE = ("#3fa860", "✓")
_STATUS_MISSING = ("#c0392b", "❌")


class GemSocketRow(QFrame):
    """One socket's row: expected gem/rune name + effect text, a "Have
    it" toggle, and a status glyph - see module docstring for the
    ✓/❌-only status model and the "unknown"/DATA UNAVAILABLE case."""

    socket_toggled = Signal(str, bool)  # (key, checked)

    def __init__(self, socket: dict, key: str, confirmed: bool, parent=None):
        super().__init__(parent)

        self._key = key
        kind = socket.get("kind")
        self._resolvable = kind in ("gem", "rune") and bool(socket.get("name"))

        self.setObjectName("gemSocketRow")

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 4)
        outer.setSpacing(10)

        self.status_label = BodyLabel("", self)
        self.status_label.setFixedWidth(18)
        outer.addWidget(self.status_label)

        text_col = QVBoxLayout()
        text_col.setSpacing(1)

        kind_label = "Gem" if kind == "gem" else ("Rune" if kind == "rune" else "Socket")
        name = socket.get("name") if self._resolvable else "DATA UNAVAILABLE"

        self.name_label = BodyLabel(f"{kind_label}: {name}", self)
        self.name_label.setWordWrap(True)
        text_col.addWidget(self.name_label)

        effect_text = socket.get("effect_text") if self._resolvable else None
        self.effect_label = None
        if effect_text:
            self.effect_label = CaptionLabel(effect_text, self)
            self.effect_label.setWordWrap(True)
            self.effect_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
            text_col.addWidget(self.effect_label)

        outer.addLayout(text_col, 1)

        self.toggle = SwitchButton(self)
        self.toggle.setOnText("Have it")
        self.toggle.setOffText("Missing")
        self.toggle.setChecked(confirmed and self._resolvable)
        self.toggle.setEnabled(self._resolvable)
        self.toggle.checkedChanged.connect(self._on_toggled)
        outer.addWidget(self.toggle)

        self._apply_status(confirmed and self._resolvable)

    def _apply_status(self, done: bool):

        if not self._resolvable:
            self.status_label.setText("?")
            self.status_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
            return

        color, glyph = _STATUS_DONE if done else _STATUS_MISSING
        self.status_label.setText(glyph)
        self.status_label.setTextColor(QColor(color), QColor(color))

    def _on_toggled(self, checked: bool):

        if not self._resolvable:
            return

        self._apply_status(checked)
        self.socket_toggled.emit(self._key, checked)

    def refresh_theme(self):

        if not self._resolvable:
            self.status_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        if self.effect_label is not None:
            self.effect_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))


class GemItemCard(QFrame):
    """One equipped slot's socket summary: item name, socket count, then
    one ``GemSocketRow`` per socket."""

    socket_toggled = Signal(str, bool)

    def __init__(self, item: dict, socketed: set[str], parent=None):
        super().__init__(parent)

        self.setObjectName("gemItemCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(6)

        slot = item.get("slot", "?")
        sockets = item.get("sockets") or []

        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        self.slot_label = StrongBodyLabel(slot, self)
        self.slot_label.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        header_row.addWidget(self.slot_label)
        header_row.addStretch(1)

        count = len(sockets)
        self.count_label = CaptionLabel(f"{count} socket{'s' if count != 1 else ''}", self)
        self.count_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        header_row.addWidget(self.count_label)

        outer.addLayout(header_row)

        self.name_label = BodyLabel(item.get("item_name") or "?", self)
        self.name_label.setWordWrap(True)
        outer.addWidget(self.name_label)

        self._rows: list[GemSocketRow] = []
        for idx, socket in enumerate(sockets):
            key = f"{slot}:{idx}"
            row = GemSocketRow(socket, key, key in socketed, self)
            row.socket_toggled.connect(self.socket_toggled)
            outer.addWidget(row)
            self._rows.append(row)

        self._apply_style()

    def _apply_style(self):

        self.setStyleSheet(
            f"""
            QFrame#gemItemCard {{
                background-color: {theme.SURFACE_ALT};
                border-radius: 10px;
                border: 1px solid {theme.BORDER};
            }}
            """
        )

    def refresh_theme(self):

        self._apply_style()
        self.slot_label.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.count_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        for row in self._rows:
            row.refresh_theme()


class GemsCard(BaseCard):
    """Top-level Gems card: header (follows the active character/build/
    level, same "owns no selector" pattern as Gear Builder/Paragon), a
    rollup line, and either an honest "nothing to show" page state or one
    ``GemItemCard`` per equipped slot that actually has sockets."""

    socket_owned_changed = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__("GEMS", icon=FIF.CERTIFICATE, parent=parent)

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

        self.empty_label = BodyLabel("", self.content)
        self.empty_label.setWordWrap(True)
        self.empty_label.hide()
        self.add_widget(self.empty_label)

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
        self._cards: list[GemItemCard] = []

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

    def set_gems(self, verified_build: dict | None, socketed: set[str]):
        """``verified_build`` is ``LevelingManager.get_verified_build``'s
        return value, ``socketed`` is ``MainWindow._load_socketed_gems``'s
        set for the current build. Only equipped slots with a non-empty
        ``sockets`` list are shown - see module docstring for the two
        distinct "nothing to show" states this handles honestly."""

        self._clear_cards()

        if verified_build is None:
            self.rollup_label.setText("")
            self.empty_label.setText(
                "DATA UNAVAILABLE — no verified Maxroll Planner profile for "
                "this build yet, so there's no socket data to show."
            )
            self.empty_label.show()
            return

        verified_gear = verified_build.get("gear") or []
        items_with_sockets = [item for item in verified_gear if item.get("sockets")]

        if not items_with_sockets:
            self.rollup_label.setText("")
            self.empty_label.setText(
                "None of this build's equipped items carry socket data in "
                "the guide - nothing to track here."
            )
            self.empty_label.show()
            return

        self.empty_label.hide()

        trackable = 0
        done = 0
        total_sockets = 0

        for item in items_with_sockets:
            slot = item.get("slot", "?")
            for idx, socket in enumerate(item["sockets"]):
                total_sockets += 1
                if socket.get("kind") in ("gem", "rune") and socket.get("name"):
                    trackable += 1
                    if f"{slot}:{idx}" in socketed:
                        done += 1

        if trackable:
            self.rollup_label.setText(f"{done} / {trackable} sockets confirmed")
        else:
            self.rollup_label.setText(
                f"{total_sockets} socket(s) — none resolvable (DATA UNAVAILABLE)"
            )

        for item in items_with_sockets:
            self._add_card(item, socketed)

    def _add_card(self, item: dict, socketed: set[str]):

        card = GemItemCard(item, socketed, self._cards_container)
        card.socket_toggled.connect(self.socket_owned_changed)
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


class GemsInterface(QWidget):
    """Top-level nav page wrapping ``GemsCard`` - same centered,
    width-capped layout ``GearBuilderInterface``/``ParagonInterface``
    use."""

    def __init__(self, gems_card: GemsCard, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        gems_card.setMinimumWidth(460)
        gems_card.setMaximumWidth(820)

        layout.addStretch(1)
        layout.addWidget(gems_card, 3)
        layout.addStretch(1)
