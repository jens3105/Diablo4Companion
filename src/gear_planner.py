"""Character Equipment Planner - a body-centric visual replacement for the
old plain toggle checklist that used to live in the Gear & Powers tab (see
git history of ``LevelingCard.set_gear`` / ``_render_verified_gear_checklist``
/ ``_render_gear_checklist``).

This is a new *presentation* only. It reuses the exact same tracked state as
before:

* the ``gear/<build>/owned_items`` QSettings set, via
  ``MainWindow._load_owned_items``/``_save_owned_items``;
* the same signal chain - this widget's ``item_owned_changed`` plays the
  role the old ``SwitchButton`` toggles used to, wired by ``LevelingCard``
  straight into its existing ``gear_owned_changed`` signal, which
  ``MainWindow.on_gear_owned_changed``/``_compute_build_status`` already
  handle unchanged.

Status model
------------
Every slot chip renders one of four states (``SlotStatus``):

* CORRECT   - the tracked "have it" toggle is on for this slot's expected
  item.
* MISSING   - required by the build, "have it" toggle is off.
* OPTIONAL  - no build requirement for this slot at all (e.g. Heartseeker
  Rogue's sparser guide data doesn't call out a Chest piece, so Chest shows
  as an empty/optional slot instead of a fake "missing" one).
* INCORRECT - reserved for "the player has *something* equipped in this
  slot, but it doesn't match the build's expected item". The app has no
  independent notion of "what's actually equipped" today - only a boolean
  toggle on the *expected* item - so nothing in this module ever produces
  this status. The case exists purely so the rendering switch below
  (``_STATUS_META``) has a real, ready slot for it instead of silently
  misclassifying or crashing the day that data exists. Nothing should be
  wired up to synthesize this state from today's data.
"""

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FlowLayout,
    MessageBoxBase,
    StrongBodyLabel,
    SwitchButton,
)

from src import theme


class SlotStatus(Enum):
    CORRECT = "correct"
    MISSING = "missing"
    OPTIONAL = "optional"
    INCORRECT = "incorrect"  # architecturally reachable, never produced today - see module docstring


# Fixed regardless of dark/light mode or seasonal accent preset - same
# precedent as ``leveling_card.ROLE_COLORS`` and ``app.py``'s
# 🟢/🟡/🔴 ``_status_emoji`` - a semantic status color, not a themed one.
_STATUS_META = {
    SlotStatus.CORRECT: ("✓", "#3fa860"),
    SlotStatus.MISSING: ("✗", "#c0392b"),
    SlotStatus.OPTIONAL: ("○", None),  # falls back to theme.TEXT_MUTED
    SlotStatus.INCORRECT: ("⚠", "#e0a458"),
}

_STATUS_LABELS = {
    SlotStatus.CORRECT: "Correct",
    SlotStatus.MISSING: "Missing",
    SlotStatus.OPTIONAL: "Not required",
    SlotStatus.INCORRECT: "Incorrect item equipped",
}

# Rarity swatch colors - a plain geometric color key (not game artwork),
# also fixed regardless of theme for the same reason as the status colors.
_RARITY_COLORS = {
    "mythic": "#c0392b",
    "unique": "#c9974a",
    "legendary": "#e2883e",
    "set": "#3fa860",
}


def _rarity_color(rarity: str | None) -> str:
    return _RARITY_COLORS.get((rarity or "").strip().lower(), theme.TEXT_MUTED)


def _status_color(status: SlotStatus) -> str:
    return _STATUS_META[status][1] or theme.TEXT_MUTED


def classify_slot(slot: str) -> str:
    """Bucket a raw slot string (e.g. "Weapon — Sword (Two-Handed)",
    "Talisman (Charm) 3", "Ring 2") into one of the fixed body-diagram
    regions. Substring matching (not exact match) since the real slot
    strings decoded from Maxroll vary in punctuation/numbering per class
    and per weapon type - see the class survey in the PR description."""

    s = (slot or "").lower()

    if "helm" in s:
        return "HELM"
    if "chest" in s:
        return "CHEST"
    if "glove" in s:
        return "GLOVES"
    if "pant" in s or "leg" in s:
        return "PANTS"
    if "boot" in s:
        return "BOOTS"
    if "amulet" in s:
        return "AMULET"
    if "ring" in s:
        return "RING"
    if "talisman" in s:
        return "TALISMAN"
    if "weapon" in s or "offhand" in s or "off-hand" in s:
        return "WEAPON"
    return "OTHER"


# Body slots that always get exactly one visible chip (or an empty/
# "optional" placeholder chip when the build's data has nothing for it) -
# WEAPON is handled separately since its count varies per build/class.
_BODY_BUCKETS = ["HELM", "AMULET", "CHEST", "GLOVES", "PANTS", "RING", "BOOTS"]
_BUCKET_LABELS = {
    "HELM": "Helm",
    "AMULET": "Amulet",
    "CHEST": "Chest",
    "GLOVES": "Gloves",
    "PANTS": "Pants",
    "RING": "Ring",
    "BOOTS": "Boots",
    "WEAPON": "Weapon",
    "TALISMAN": "Talisman",
    "OTHER": "Other",
}


@dataclass
class SlotEntry:
    """One chip's worth of data. ``key`` is the QSettings owned-items key
    (the real item/aspect name) when this chip is toggleable, or ``None``
    for an empty "optional" placeholder that has nothing to toggle."""

    slot_label: str
    bucket: str
    item_name: str | None
    rarity: str | None
    aspect: str | None
    status: SlotStatus
    key: str | None


def build_entries_from_verified_gear(gear: list[dict], owned_names: set[str]) -> list[SlotEntry]:
    """``gear`` is ``verified_build["gear"]`` - see ``LevelingManager.
    get_verified_build``. Every real slot becomes a CORRECT/MISSING entry;
    any of the fixed body buckets or the weapon bucket that ends up with no
    entries at all gets one OPTIONAL placeholder so the diagram still shows
    every slot."""

    entries = []
    seen_buckets = set()

    for item in gear:
        slot = item.get("slot", "?")
        bucket = classify_slot(slot)
        seen_buckets.add(bucket)
        name = item["item_name"]
        status = SlotStatus.CORRECT if name in owned_names else SlotStatus.MISSING

        entries.append(
            SlotEntry(
                slot_label=slot,
                bucket=bucket,
                item_name=name,
                rarity=item.get("rarity"),
                aspect=item.get("aspect"),
                status=status,
                key=name,
            )
        )

    entries.extend(_missing_bucket_placeholders(seen_buckets))

    return entries


def build_entries_from_legacy_gear(key_items: list[dict], owned_names: set[str]) -> list[SlotEntry]:
    """``key_items`` is the older ``gear.key_items`` prose-derived list
    (``{"name", "slot", "note"}``) - the only shape left with no
    ``verified_build`` data (Heartseeker Rogue). Slots this guide simply
    doesn't call out become OPTIONAL placeholders, same as the verified
    path - e.g. Heartseeker's guide never mentions Chest/Pants/Boots/
    Amulet, so those show as "not required" instead of a fabricated
    "missing" state."""

    entries = []
    seen_buckets = set()

    for item in key_items:
        slot = item.get("slot", "?")
        bucket = classify_slot(slot)
        seen_buckets.add(bucket)
        name = item["name"]
        status = SlotStatus.CORRECT if name in owned_names else SlotStatus.MISSING

        entries.append(
            SlotEntry(
                slot_label=slot,
                bucket=bucket,
                item_name=name,
                rarity=None,
                aspect=None,
                status=status,
                key=name,
            )
        )

    entries.extend(_missing_bucket_placeholders(seen_buckets))

    return entries


def _missing_bucket_placeholders(seen_buckets: set[str]) -> list[SlotEntry]:

    placeholders = []

    for bucket in _BODY_BUCKETS + ["WEAPON"]:
        if bucket not in seen_buckets:
            placeholders.append(
                SlotEntry(
                    slot_label=_BUCKET_LABELS[bucket],
                    bucket=bucket,
                    item_name=None,
                    rarity=None,
                    aspect=None,
                    status=SlotStatus.OPTIONAL,
                    key=None,
                )
            )

    return placeholders


def build_unslotted_entries(key_aspects: list[dict], owned_names: set[str]) -> list[SlotEntry]:
    """Heartseeker Rogue's legacy ``key_aspects`` entries (``{"name",
    "note"}``) carry no ``slot`` at all - Maxroll's guide text ties them to
    "amulet swap" style situational picks, not one fixed gear piece - so
    they can't be honestly placed on the body diagram. Kept toggleable in
    their own small tray below it instead of being dropped, since
    ``MainWindow._compute_build_status`` still counts them into the Gear
    percentage alongside ``key_items``."""

    return [
        SlotEntry(
            slot_label="Aspect",
            bucket="ASPECT",
            item_name=entry["name"],
            rarity=None,
            aspect=None,
            status=SlotStatus.CORRECT if entry["name"] in owned_names else SlotStatus.MISSING,
            key=entry["name"],
        )
        for entry in key_aspects
    ]


class _Silhouette(QWidget):
    """Plain geometric humanoid outline drawn with QPainter - no game
    artwork, just enough of a body shape to anchor the slot chips around.
    Reads ``theme.*`` fresh on every paint, so it stays correct across
    dark/light + seasonal preset changes without needing its own repaint
    hook - whatever last called ``update()`` (or moved/resized it) is
    enough."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setMinimumSize(60, 220)

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        pen = QPen(QColor(theme.BORDER))
        pen.setWidth(2)
        painter.setPen(pen)

        w = self.width()
        h = self.height()
        cx = w / 2

        head_r = min(w, h) * 0.09
        head_cy = h * 0.10

        painter.drawEllipse(
            int(cx - head_r), int(head_cy - head_r), int(head_r * 2), int(head_r * 2)
        )

        shoulder_y = head_cy + head_r * 1.6
        hip_y = h * 0.55
        torso_w = w * 0.30

        painter.drawLine(int(cx - torso_w / 2), int(shoulder_y), int(cx - torso_w / 2), int(hip_y))
        painter.drawLine(int(cx + torso_w / 2), int(shoulder_y), int(cx + torso_w / 2), int(hip_y))
        painter.drawLine(int(cx - torso_w / 2), int(shoulder_y), int(cx + torso_w / 2), int(shoulder_y))
        painter.drawLine(int(cx - torso_w / 2), int(hip_y), int(cx + torso_w / 2), int(hip_y))

        # Arms
        arm_span = w * 0.42
        painter.drawLine(int(cx - torso_w / 2), int(shoulder_y), int(cx - arm_span / 2), int(hip_y))
        painter.drawLine(int(cx + torso_w / 2), int(shoulder_y), int(cx + arm_span / 2), int(hip_y))

        # Legs
        foot_y = h * 0.97
        painter.drawLine(int(cx - torso_w / 4), int(hip_y), int(cx - torso_w / 3), int(foot_y))
        painter.drawLine(int(cx + torso_w / 4), int(hip_y), int(cx + torso_w / 3), int(foot_y))

        painter.end()


class SlotChip(QFrame):
    """One clickable gear-slot tile: rarity swatch, slot label, item name,
    status glyph, and (when present) the aspect name. Empty/OPTIONAL chips
    render in a dimmed, non-interactive-looking style but stay clickable so
    the detail dialog can explain *why* ("no build requirement")."""

    clicked = Signal(object)  # emits its own SlotEntry

    def __init__(self, entry: SlotEntry, display_label: str | None = None, parent=None):
        super().__init__(parent)

        self.entry = entry

        self.setObjectName("gearSlotChip")
        self.setCursor(Qt.PointingHandCursor)
        # Fixed width - QGridLayout is known not to propagate a wrapped
        # QLabel's heightForWidth correctly through nested layouts, so
        # relying on automatic layout sizing left long item names (e.g.
        # "Tuskhelm of Joritz the Mighty") clipped at the chip's bottom
        # edge. Fixing the width lets ``_apply_entry`` below compute each
        # wrapped label's exact required height itself (via QFontMetrics)
        # and set it explicitly, instead of trusting Qt to grow the row.
        self._chip_width = 150
        self.setFixedWidth(self._chip_width)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        top_row = QHBoxLayout()
        top_row.setSpacing(4)

        self.swatch = QFrame(self)
        self.swatch.setFixedSize(10, 10)
        top_row.addWidget(self.swatch)
        top_row.addStretch(1)

        self.status_label = CaptionLabel("", self)
        top_row.addWidget(self.status_label)

        layout.addLayout(top_row)

        self.slot_label = CaptionLabel(display_label or entry.slot_label, self)
        self.slot_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.slot_label.setWordWrap(True)
        layout.addWidget(self.slot_label)

        self.name_label = BodyLabel("", self)
        self.name_label.setWordWrap(True)
        layout.addWidget(self.name_label)

        self._apply_entry()

    def _label_height_for_text(self, label, text: str) -> int:
        """Exact pixel height ``label`` needs to word-wrap ``text`` at this
        chip's fixed inner width - see the width/height comment in
        ``__init__`` for why this is computed by hand instead of trusted to
        the layout system."""

        margins = self.layout().contentsMargins()
        inner_width = self._chip_width - margins.left() - margins.right()
        rect = QFontMetrics(label.font()).boundingRect(
            0, 0, inner_width, 0, Qt.TextWordWrap, text
        )
        return rect.height()

    def _apply_entry(self):

        entry = self.entry
        status = entry.status
        glyph, _ = _STATUS_META[status]
        color = _status_color(status)

        self.status_label.setText(glyph)
        self.status_label.setTextColor(QColor(color), QColor(color))

        slot_text = self.slot_label.text()
        self.slot_label.setFixedHeight(self._label_height_for_text(self.slot_label, slot_text))

        name_text = entry.item_name or "— Not required —"
        self.name_label.setText(name_text)
        self.name_label.setFixedHeight(self._label_height_for_text(self.name_label, name_text))

        if entry.item_name:
            self.swatch.setStyleSheet(
                f"background-color: {_rarity_color(entry.rarity)}; border-radius: 2px;"
            )
        else:
            self.swatch.setStyleSheet(
                f"background-color: transparent; border: 1px solid {theme.BORDER}; border-radius: 2px;"
            )

        border_color = color if status != SlotStatus.OPTIONAL else theme.BORDER
        self.setStyleSheet(
            f"""
            QFrame#gearSlotChip {{
                background-color: {theme.SURFACE_ALT};
                border-radius: 8px;
                border: 1px solid {border_color};
            }}
            """
        )

        # Total height = swatch/status row + spacing + the two labels we
        # just measured exactly, plus the layout's own margins - set once
        # the sub-heights are known so the whole chip (not just its
        # children) reports the right size to the QGridLayout cell.
        margins = self.layout().contentsMargins()
        spacing = self.layout().spacing()
        swatch_row_height = max(self.swatch.height(), self.status_label.sizeHint().height())
        total_height = (
            margins.top()
            + swatch_row_height
            + spacing
            + self.slot_label.height()
            + spacing
            + self.name_label.height()
            + margins.bottom()
        )
        self.setFixedHeight(total_height)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.entry)
        super().mousePressEvent(event)


class SlotDetailDialog(MessageBoxBase):
    """Detail popup for one slot chip: name, slot, rarity, aspect and
    current status - reusing the same real fields the chip itself shows,
    nothing invented (no lore/flavor text field exists in the data). When
    the entry is toggleable (``entry.key`` is not ``None``), a SwitchButton
    lets the player flip the same "have it" state the old checklist toggle
    controlled, via ``item_owned_changed``."""

    def __init__(self, entry: SlotEntry, parent=None):
        super().__init__(parent)

        self.entry = entry
        self.owned_changed_callback = None

        title = StrongBodyLabel(entry.item_name or f"{entry.slot_label} — Empty", self)
        title.setWordWrap(True)
        self.viewLayout.addWidget(title)

        def add_field(label: str, value: str):
            row = BodyLabel(f"{label}: {value}", self)
            row.setWordWrap(True)
            row.setTextColor(QColor(theme.TEXT_PRIMARY), QColor(theme.TEXT_PRIMARY))
            self.viewLayout.addWidget(row)

        add_field("Slot", entry.slot_label)

        if entry.rarity:
            add_field("Rarity", entry.rarity)

        if entry.aspect:
            add_field("Aspect", entry.aspect)

        self.status_row = BodyLabel("", self)
        self._set_status_text(entry.status)
        self.viewLayout.addWidget(self.status_row)

        if entry.key is not None:
            toggle_row = QHBoxLayout()
            toggle_label = CaptionLabel("Have it:", self)
            self.toggle = SwitchButton(self)
            self.toggle.setOnText("Have it")
            self.toggle.setOffText("Missing")
            self.toggle.setChecked(entry.status == SlotStatus.CORRECT)
            self.toggle.checkedChanged.connect(self._on_toggled)
            toggle_row.addWidget(toggle_label)
            toggle_row.addWidget(self.toggle)
            toggle_row.addStretch(1)
            self.viewLayout.addLayout(toggle_row)
        else:
            add_field("Note", "No build requirement for this slot.")

        self.hideCancelButton()
        self.yesButton.setText("Close")
        self.widget.setMinimumWidth(320)

    def _set_status_text(self, status: SlotStatus):
        color = _status_color(status)
        self.status_row.setText(f"Status: {_STATUS_META[status][0]} {_STATUS_LABELS[status]}")
        self.status_row.setTextColor(QColor(color), QColor(color))

    def _on_toggled(self, checked: bool):
        # Only CORRECT/MISSING are reachable via this toggle - it flips the
        # same boolean "have it" state the old checklist toggle controlled,
        # never OPTIONAL/INCORRECT (see module docstring).
        self._set_status_text(SlotStatus.CORRECT if checked else SlotStatus.MISSING)
        if self.owned_changed_callback is not None:
            self.owned_changed_callback(self.entry.key, checked)


class GearPlannerWidget(QWidget):
    """The full body-centric equipment planner: a silhouette with the
    fixed body slots arranged around it (see the module docstring for the
    layout), a dynamic weapon row (varies per class/build - dual-wield,
    two-handed, shield/focus offhand, ...), and small trays for anything
    that doesn't fit the body metaphor (Talismans, unslotted Aspects, and
    a catch-all "Other" bucket so no real data ever silently disappears).
    """

    item_owned_changed = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        # ---- Body canvas: silhouette + grid of body-slot chips ----
        #
        # The grid IS the canvas's own layout (so the canvas's size is
        # driven by the chips it actually contains, not by some separate
        # overlay's sizeHint). The silhouette is a plain, non-layout child
        # widget stretched to the canvas's full rect on every resize and
        # lowered behind the grid's chip widgets, so it reads as a drawn
        # backdrop rather than an interactive element -
        # ``WA_TransparentForMouseEvents`` also keeps it from stealing
        # clicks from the chips sitting in front of it.

        self.canvas = QWidget(self)

        self.grid = QGridLayout(self.canvas)
        self.grid.setSpacing(8)
        for col in range(3):
            self.grid.setColumnStretch(col, 1)

        self.silhouette = _Silhouette(self.canvas)
        self.silhouette.lower()

        outer.addWidget(self.canvas)

        # ---- Extra trays: Weapon(s), Talismans, unslotted Aspects, Other ----

        self.extra_layout = QVBoxLayout()
        self.extra_layout.setSpacing(10)
        outer.addLayout(self.extra_layout)

        self._chips: list[SlotChip] = []

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.silhouette.setGeometry(0, 0, self.canvas.width(), self.canvas.height())

    # -----------------------------------------------------------
    # Population
    # -----------------------------------------------------------

    def set_entries(self, entries: list[SlotEntry], extra_sections: list[tuple[str, list[SlotEntry]]]):
        """``entries`` are the body-diagram slots (fixed buckets +
        weapon(s)). ``extra_sections`` is a list of ``(title, entries)``
        for anything rendered below the body as its own labeled tray
        (Talismans, unslotted Aspects, Other) - omitted entirely when its
        entry list is empty."""

        self._clear_grid()
        self._clear_extra()

        by_bucket: dict[str, list[SlotEntry]] = {}
        for entry in entries:
            by_bucket.setdefault(entry.bucket, []).append(entry)

        # Fixed body positions - see module docstring for the diagram.
        positions = {
            "HELM": (0, 1, 1, 1),
            "AMULET": (1, 0, 1, 1),
            "CHEST": (1, 1, 1, 1),
            "GLOVES": (2, 0, 1, 1),
            "PANTS": (2, 1, 1, 1),
            "RING": (2, 2, 1, 1),
            "BOOTS": (3, 1, 1, 1),
        }

        for bucket, (row, col, rspan, cspan) in positions.items():
            bucket_entries = by_bucket.get(bucket) or [_placeholder(bucket)]
            cell = self._make_cell(bucket_entries)
            self.grid.addWidget(cell, row, col, rspan, cspan, Qt.AlignCenter)

        weapon_entries = by_bucket.get("WEAPON") or [_placeholder("WEAPON")]
        weapon_section = self._make_flow_section(
            "Weapon" if len(weapon_entries) == 1 else "Weapons", weapon_entries
        )
        self.extra_layout.addWidget(weapon_section)

        for title, section_entries in extra_sections:
            if not section_entries:
                continue
            self.extra_layout.addWidget(self._make_flow_section(title, section_entries))

    def _make_cell(self, entries: list[SlotEntry]) -> QWidget:
        """A single grid position - normally one chip, but Ring (and any
        other bucket where a build lists more than one item, e.g.
        Heartseeker Rogue's two alternative Gloves picks) stacks its chips
        vertically in one cell instead of only showing the first."""

        if len(entries) == 1:
            return self._make_chip(entries[0])

        holder = QWidget()
        v = QVBoxLayout(holder)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        for entry in entries:
            v.addWidget(self._make_chip(entry))
        return holder

    def _make_flow_section(self, title: str, entries: list[SlotEntry]) -> QWidget:

        section = QWidget()
        v = QVBoxLayout(section)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)

        header = CaptionLabel(title.upper(), section)
        header.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        v.addWidget(header)

        flow_container = QWidget()
        flow = FlowLayout(flow_container, needAni=False)
        flow.setContentsMargins(0, 0, 0, 0)
        flow.setHorizontalSpacing(8)
        flow.setVerticalSpacing(8)

        for entry in entries:
            flow.addWidget(self._make_chip(entry, display_label=entry.slot_label))

        v.addWidget(flow_container)

        return section

    def _make_chip(self, entry: SlotEntry, display_label: str | None = None) -> SlotChip:

        chip = SlotChip(entry, display_label=display_label)
        chip.clicked.connect(self._on_chip_clicked)
        self._chips.append(chip)
        return chip

    def _on_chip_clicked(self, entry: SlotEntry):

        dialog = SlotDetailDialog(entry, parent=self.window())
        dialog.owned_changed_callback = self._on_owned_toggled
        dialog.exec()

    def _on_owned_toggled(self, key: str, checked: bool):
        self.item_owned_changed.emit(key, checked)

    def _clear_grid(self):

        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._chips.clear()

    def _clear_extra(self):

        while self.extra_layout.count():
            item = self.extra_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def refresh_theme(self):
        """Force the silhouette to repick up ``theme.*`` immediately - the
        chips themselves get fully rebuilt (with fresh colors) the next
        time ``MainWindow`` repopulates the active character after a theme
        change, same as every other Build Guide tab."""

        self.silhouette.update()


def _placeholder(bucket: str) -> SlotEntry:

    return SlotEntry(
        slot_label=_BUCKET_LABELS.get(bucket, bucket.title()),
        bucket=bucket,
        item_name=None,
        rarity=None,
        aspect=None,
        status=SlotStatus.OPTIONAL,
        key=None,
    )
