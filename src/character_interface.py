"""Character page (Phase - navigation reorg): a dedicated top-level page
hosting the visual Character Equipment Planner (``GearPlannerWidget``),
moved out of the Build Guide's old 4th tab ("Gear & Powers" - see git
history of ``LevelingCard._build_gear_page``/``set_gear``).

This page owns no "current build" state of its own - the class/build/
level/character selectors stay put in the Build Guide (``LevelingCard``),
which is what the player actually uses to switch builds. ``MainWindow``
just also pushes every build/character/level change here (``set_header``)
and every gear-data refresh here (``CharacterCard.set_gear``), the exact
same way it already pushes them at ``LevelingCard``/the Dashboard's
Current Build card - one source of truth, several read-outs."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon as FIF,
    SingleDirectionScrollArea,
    StrongBodyLabel,
)

from src import theme
from src.base_card import BaseCard
from src.gear_planner import (
    GearPlannerWidget,
    build_entries_from_legacy_gear,
    build_entries_from_verified_gear,
    build_unslotted_entries,
)


class CharacterCard(BaseCard):
    """The Character Equipment Planner card: a small read-only header
    ("Character — Build (Lvl N)") followed by the same gear rollup +
    body-diagram planner + reference text the old Gear & Powers tab
    showed - unchanged content/logic, just moved off ``LevelingCard``
    onto its own page."""

    gear_owned_changed = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__("CHARACTER", icon=FIF.FINGERPRINT, parent=parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(320, 320)

        # -------------------------
        # Read-only header - follows whatever character/build/level is
        # currently active in the Build Guide, so there is only ever one
        # "current build" state (see module docstring).
        # -------------------------

        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        self.header_label = StrongBodyLabel("No build selected", self.content)
        self.header_label.setWordWrap(True)
        header_row.addWidget(self.header_label, 1)

        self.add_layout(header_row)

        hint = CaptionLabel(
            "Switch character/build/level from the Build Guide page.", self.content
        )
        hint.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.add_widget(hint)
        self._hint_label = hint

        self.gear_rollup_label = StrongBodyLabel(
            "Pick a build to see gear readiness.", self.content
        )
        self.gear_rollup_label.setWordWrap(True)
        self.gear_rollup_label.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.add_widget(self.gear_rollup_label)

        # -------------------------
        # Scrollable body: the planner itself (pinned at the top, never
        # torn down - see ``_clear_rows_after``) then reference text rows
        # (stat priority, skill bar, source link) below it.
        # -------------------------

        scroll = SingleDirectionScrollArea(self.content, orient=Qt.Vertical)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background: transparent; border: none;}")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        inner_layout = QVBoxLayout(container)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(6)
        inner_layout.addStretch()

        scroll.setWidget(container)

        self.gear_container = container
        self.gear_layout = inner_layout

        self.gear_planner = GearPlannerWidget(container)
        self.gear_planner.item_owned_changed.connect(self.gear_owned_changed)
        self.gear_layout.insertWidget(0, self.gear_planner)

        self.add_widget(scroll)
        self.content_layout.setStretch(self.content_layout.count() - 1, 1)

    # ---------------------------------------------------------
    # Header (character/build/level follow-along)
    # ---------------------------------------------------------

    def set_header(self, character_name: str, build_name: str, level: int):

        if not build_name:
            self.header_label.setText("No build selected")
            return

        prefix = f"{character_name} — " if character_name else ""
        self.header_label.setText(f"{prefix}{build_name} (Lvl {level})")

    # ---------------------------------------------------------
    # Row helpers (same shell as LevelingCard's - kept local since this
    # is the only place in this file that needs them)
    # ---------------------------------------------------------

    @staticmethod
    def _insert_row(layout: QVBoxLayout, widget):
        layout.insertWidget(layout.count() - 1, widget)

    @staticmethod
    def _clear_rows_after(layout: QVBoxLayout, keep_from_start: int):
        """Preserve the first ``keep_from_start`` widgets (``self.
        gear_planner``) instead of tearing them down on every
        ``set_gear`` call - only the reference-text rows after it get
        rebuilt."""

        while layout.count() > keep_from_start + 1:
            item = layout.takeAt(keep_from_start)
            if item.widget():
                item.widget().setParent(None)

    def _add_row(self, layout: QVBoxLayout, container: QWidget, text: str):

        row = BodyLabel(text, container)
        row.setWordWrap(True)
        row.setStyleSheet(
            f"""
            background-color: {theme.SURFACE_ALT};
            color: {theme.TEXT_PRIMARY};
            border-radius: 8px;
            padding: 8px;
            font-size: 12px;
            """
        )
        self._insert_row(layout, row)

    def _add_section_header(self, layout: QVBoxLayout, container: QWidget, text: str):

        header = CaptionLabel(text, container)
        header.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self._insert_row(layout, header)

    # ---------------------------------------------------------
    # Gear content (moved verbatim from LevelingCard.set_gear)
    # ---------------------------------------------------------

    def set_gear(
        self,
        gear: dict | None,
        owned_names: set[str],
        verified_build: dict | None = None,
    ):
        """Populate the Character Equipment Planner (``self.gear_planner``
        - see ``src/gear_planner.py``): a body-centric diagram of
        clickable slot chips.

        When ``verified_build`` has a real, decoded ``gear`` list (see
        ``LevelingManager.get_verified_build`` /
        ``scripts/maxroll_data_decoder.py``'s ``decode_gear``) - the
        actual equipped loadout (real item name + slot + rarity, and the
        real socketed Aspect name where one applies) - THAT list drives
        the planner (``build_entries_from_verified_gear``), not the
        older, prose-derived ``key_items``/``key_aspects`` lists. Each
        slot is keyed by the item's real name (a stable identifier - two
        equipped items sharing a name within one build is not a
        realistic case).

        Only when a build has no verified gear data does this fall back
        to the original ``key_items``/``key_aspects`` data
        (``build_entries_from_legacy_gear``/``build_unslotted_entries``)
        - unchanged source data for the one build (Heartseeker Rogue)
        with no verified data at all; its aspects have no ``slot`` field
        so they render in their own "Key Aspects" tray instead of on the
        body diagram (see that function's docstring).

        Gear ownership can be lost (an item sold/replaced), so each chip
        opens a detail dialog with a two-way "Have it"/"Missing" toggle
        (``GearPlannerWidget.item_owned_changed`` -> this card's own
        ``gear_owned_changed`` signal, connected 1:1 in ``__init__`` -
        exactly the signal/QSettings path the old per-row toggles used),
        and there's a rollup ("X / Y items equipped") up top instead of a
        "next" pointer so build-readiness is visible at a glance.
        ``stat_priority``/``skill_bar`` stay plain reference text either
        way - they aren't checkable items and have no verified
        equivalent."""

        layout = self.gear_layout
        container = self.gear_container

        self._clear_rows_after(layout, 1)

        if not gear and not verified_build:
            self.gear_rollup_label.setText(
                "No endgame gear guide available for this build."
            )
            self.gear_planner.set_entries([], [])
            self._add_section_header(layout, container, "GEAR && POWERS")
            self._add_row(
                layout,
                container,
                "Maxroll has no dedicated endgame guide for this build yet - "
                "leveling milestones and Paragon are still fully available.",
            )
            return

        gear = gear or {}
        verified_gear = (verified_build or {}).get("gear") or []

        if verified_gear:
            owned_count = sum(1 for entry in verified_gear if entry["item_name"] in owned_names)
            self.gear_rollup_label.setText(
                f"{owned_count} / {len(verified_gear)} items equipped"
            )

            self._add_section_header(
                layout, container, "EQUIPPED GEAR (VERIFIED — MAXROLL PLANNER)"
            )
            self._add_row(
                layout,
                container,
                f"Real item names, slots and socketed Aspects decoded from Maxroll's "
                f"\"{verified_build.get('profile_name', '?')}\" planner profile. "
                "Tap a slot above for details.",
            )

            entries = build_entries_from_verified_gear(verified_gear, owned_names)
            body_entries = [e for e in entries if e.bucket not in ("TALISMAN", "OTHER")]
            talisman_entries = [e for e in entries if e.bucket == "TALISMAN"]
            other_entries = [e for e in entries if e.bucket == "OTHER"]

            self.gear_planner.set_entries(
                body_entries,
                [("Talismans", talisman_entries), ("Other", other_entries)],
            )
        else:
            key_items = gear.get("key_items") or []
            key_aspects = gear.get("key_aspects") or []

            checkable = key_items + key_aspects
            owned_count = sum(1 for entry in checkable if entry["name"] in owned_names)

            if checkable:
                self.gear_rollup_label.setText(
                    f"{owned_count} / {len(checkable)} key items equipped"
                )
            else:
                self.gear_rollup_label.setText("No specific gear checklist for this build.")

            self._add_section_header(layout, container, "KEY / SIGNATURE ITEMS")

            if key_items:
                self._add_row(
                    layout,
                    container,
                    "No dedicated Maxroll endgame gear planner for this build yet - "
                    "slots without a specific item call-out show as \"not required\". "
                    "Tap a slot above for details.",
                )
            else:
                self._add_row(layout, container, "No specific key items listed.")

            if not key_aspects:
                self._add_section_header(layout, container, "KEY ASPECTS")
                self._add_row(layout, container, "No specific key aspects listed.")

            body_entries = build_entries_from_legacy_gear(key_items, owned_names)
            aspect_entries = build_unslotted_entries(key_aspects, owned_names)

            self.gear_planner.set_entries(body_entries, [("Key Aspects", aspect_entries)])

        stat_priority = gear.get("stat_priority") or []
        skill_bar = gear.get("skill_bar") or []

        self._add_section_header(layout, container, "STAT PRIORITY")

        if stat_priority:
            self._add_row(layout, container, " > ".join(stat_priority))
        else:
            self._add_row(layout, container, "Not clearly stated by the guide.")

        if skill_bar:
            self._add_section_header(layout, container, "FINAL SKILL BAR")
            self._add_row(layout, container, " • ".join(skill_bar))

        source_url = gear.get("source_url")

        if source_url:
            self._add_row(layout, container, f"Source: {source_url}")

    # ---------------------------------------------------------
    # Theme / appearance
    # ---------------------------------------------------------

    def refresh_theme(self):

        super().refresh_theme()

        self._hint_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.gear_rollup_label.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.gear_planner.refresh_theme()


class CharacterInterface(QWidget):
    """Top-level nav page wrapping ``CharacterCard`` - same centered,
    width-capped layout ``BuildsInterface`` (src/app.py) uses for the
    Build Guide, so the two pages read as siblings."""

    def __init__(self, character_card: CharacterCard, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        character_card.setMinimumWidth(460)
        character_card.setMaximumWidth(820)

        layout.addStretch(1)
        layout.addWidget(character_card, 3)
        layout.addStretch(1)
