from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIntValidator
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    ComboBox,
    FluentIcon as FIF,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    SegmentedWidget,
    SingleDirectionScrollArea,
    StrongBodyLabel,
)

from src.base_card import BaseCard
from src.theme import ACCENT_GOLD, SURFACE_ALT, TEXT_MUTED, TEXT_PRIMARY

# Colors for the small "role" tag shown next to the card title and as a
# suffix on every build in the dropdown, so it's obvious at a glance
# what each build is actually for (leveling vs. which flavor of
# endgame). Keyed on the role string with the "Endgame - " prefix
# stripped (see LevelingCard._short_role) so e.g. both a build tagged
# exactly "Endgame - Bossing" and one with a custom multi-role string
# still get a sensible, distinct color.
ROLE_COLORS = {
    "Speed Farm": "#5fbf7d",
    "Bossing": "#e0655f",
    "Pushing/DPS": "#a481d1",
    "All-Purpose": "#6fa8d8",
    "Speed Farm / Bossing": "#e0a458",
    "Leveling / Early Endgame": "#4fb3bf",
}
DEFAULT_ROLE_COLOR = TEXT_MUTED


class LevelingCard(BaseCard):
    """Build-guide browser: class -> build -> Leveling/Paragon/Gear.

    Builds used to sit in one flat, 26-item dropdown regardless of class.
    This card now asks for the class first (a small segmented control),
    then only lists that class's builds in the second dropdown, and
    presents the selected build's info as three separate sections
    (Leveling milestones, Paragon board, Gear & Powers) instead of one
    long scrolling wall of text.
    """

    level_changed = Signal(int)
    build_changed = Signal(str)
    class_changed = Signal(str)
    mark_done = Signal(int)

    LEVELING_KEY = "leveling"
    SKILLS_KEY = "skills"
    PARAGON_KEY = "paragon"
    GEAR_KEY = "gear"

    def __init__(self, parent=None):
        super().__init__("BUILD GUIDE", icon=FIF.EDUCATION, parent=parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(280, 260)

        # Small colored role tag ("SPEED FARM", "BOSSING", ...) pinned to
        # the right of the card title, so the currently selected build's
        # purpose is visible without opening the build dropdown.
        self.role_tag = CaptionLabel("", self)
        self.role_tag.setVisible(False)
        self.title_row.addStretch(1)
        self.title_row.addWidget(self.role_tag)

        # -------------------------
        # Step 1: class selector
        # -------------------------

        self.class_selector = SegmentedWidget(self.content)
        self.class_selector.currentItemChanged.connect(self._on_class_selected)

        self.add_widget(self.class_selector)

        # -------------------------
        # Step 2: build selector (scoped to the chosen class)
        # -------------------------

        self.build_combo = ComboBox(self.content)
        self.build_combo.setPlaceholderText("Select a build...")
        self.build_combo.currentIndexChanged.connect(self._on_build_selected)

        self.add_widget(self.build_combo)

        # -------------------------
        # Level input row
        # -------------------------

        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        input_label = CaptionLabel("Your level:", self.content)
        input_label.setTextColor(QColor(TEXT_MUTED), QColor(TEXT_MUTED))

        self.level_input = LineEdit(self.content)
        self.level_input.setPlaceholderText("e.g. 18")
        self.level_input.setValidator(QIntValidator(1, 100, self))
        self.level_input.setFixedWidth(80)
        self.level_input.returnPressed.connect(self._on_submit)

        submit_button = PrimaryPushButton("Update", self.content)
        submit_button.clicked.connect(self._on_submit)

        input_row.addWidget(input_label)
        input_row.addWidget(self.level_input)
        input_row.addWidget(submit_button)
        input_row.addStretch(1)

        self.add_layout(input_row)

        # -------------------------
        # Section tabs: Leveling / Paragon / Gear & Powers
        # -------------------------

        self.section_selector = SegmentedWidget(self.content)
        self.add_widget(self.section_selector)

        self.section_stack = QStackedWidget(self.content)

        self.leveling_page = self._build_leveling_page()
        self.skills_page = self._build_skills_page()
        self.paragon_page = self._build_scroll_page("paragon_container", "paragon_layout")
        self.gear_page = self._build_scroll_page("gear_container", "gear_layout")

        self.section_stack.addWidget(self.leveling_page)
        self.section_stack.addWidget(self.skills_page)
        self.section_stack.addWidget(self.paragon_page)
        self.section_stack.addWidget(self.gear_page)

        self.section_selector.addItem(
            routeKey=self.LEVELING_KEY,
            text="Leveling",
            onClick=lambda: self.section_stack.setCurrentWidget(self.leveling_page),
        )
        self.section_selector.addItem(
            routeKey=self.SKILLS_KEY,
            text="Skills",
            onClick=lambda: self.section_stack.setCurrentWidget(self.skills_page),
        )
        self.section_selector.addItem(
            routeKey=self.PARAGON_KEY,
            text="Paragon",
            onClick=lambda: self.section_stack.setCurrentWidget(self.paragon_page),
        )
        self.section_selector.addItem(
            routeKey=self.GEAR_KEY,
            # "&&" so Qt renders a literal ampersand instead of treating
            # "&P" as a mnemonic accelerator (which ate the space before).
            text="Gear && Powers",
            onClick=lambda: self.section_stack.setCurrentWidget(self.gear_page),
        )
        self.section_selector.setCurrentItem(self.LEVELING_KEY)

        self.add_widget(self.section_stack)
        self.content_layout.setStretch(self.content_layout.count() - 1, 1)

    # ---------------------------------------------------------
    # Page builders
    # ---------------------------------------------------------

    def _build_leveling_page(self) -> QWidget:

        page = QWidget(self.content)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.next_label = StrongBodyLabel(
            "Pick a build and enter your level to see what's next.", page
        )
        self.next_label.setWordWrap(True)
        self.next_label.setTextColor(QColor(ACCENT_GOLD), QColor(ACCENT_GOLD))
        layout.addWidget(self.next_label)

        scroll, container, inner_layout = self._make_scroll_area(page)
        self.progress_container = container
        self.progress_layout = inner_layout

        layout.addWidget(scroll, 1)

        return page

    def _build_skills_page(self) -> QWidget:

        page = QWidget(self.content)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.skills_next_label = StrongBodyLabel(
            "Pick a build to see your next skill point.", page
        )
        self.skills_next_label.setWordWrap(True)
        self.skills_next_label.setTextColor(QColor(ACCENT_GOLD), QColor(ACCENT_GOLD))
        layout.addWidget(self.skills_next_label)

        scroll, container, inner_layout = self._make_scroll_area(page)
        self.skills_container = container
        self.skills_layout = inner_layout

        layout.addWidget(scroll, 1)

        return page

    def _build_scroll_page(self, container_attr: str, layout_attr: str) -> QWidget:

        page = QWidget(self.content)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        scroll, container, inner_layout = self._make_scroll_area(page)
        setattr(self, container_attr, container)
        setattr(self, layout_attr, inner_layout)

        layout.addWidget(scroll, 1)

        return page

    @staticmethod
    def _make_scroll_area(parent: QWidget):

        scroll = SingleDirectionScrollArea(parent, orient=Qt.Vertical)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background: transparent; border: none;}")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        inner_layout = QVBoxLayout(container)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(6)
        inner_layout.addStretch()

        scroll.setWidget(container)

        return scroll, container, inner_layout

    # ---------------------------------------------------------
    # Class / build list wiring
    # ---------------------------------------------------------

    def set_classes(self, classes: list[str], current_class_name: str | None = None):
        """Populate the step-1 class selector. Selecting an item fires
        ``class_changed`` via the ``currentItemChanged`` signal wired in
        ``__init__`` - no per-item ``onClick`` needed here."""

        self.class_selector.blockSignals(True)
        self.class_selector.clear()

        for class_name in classes:
            self.class_selector.addItem(routeKey=class_name, text=class_name)

        if classes:
            target = current_class_name if current_class_name in classes else classes[0]
            self.class_selector.setCurrentItem(target)

        self.class_selector.blockSignals(False)

    @staticmethod
    def _short_role(role: str) -> str:
        """Strip the repeated "Endgame - " prefix for compact display -
        e.g. "Endgame - Speed Farm" -> "Speed Farm". Roles that don't use
        that prefix (like "Leveling / Early Endgame") pass through as-is."""

        if not role:
            return ""

        prefix = "Endgame — "

        return role[len(prefix):] if role.startswith(prefix) else role

    def _set_role_tag(self, role: str):

        short = self._short_role(role)

        if not short:
            self.role_tag.setVisible(False)
            return

        color = QColor(ROLE_COLORS.get(short, DEFAULT_ROLE_COLOR))
        self.role_tag.setText(short.upper())
        self.role_tag.setTextColor(color, color)
        self.role_tag.setVisible(True)

    def set_builds_for_class(self, builds: list[dict], current_build_name: str | None = None):
        """``builds`` is a list of ``{"build_name": str, "role": str}``
        dicts, all from the same class, as returned by
        ``LevelingManager.list_builds_for_class``."""

        self.build_combo.blockSignals(True)
        self.build_combo.clear()

        selected_index = 0

        for i, build in enumerate(builds):
            build_name = build["build_name"]
            short_role = self._short_role(build.get("role", ""))
            display = f"{build_name} — {short_role}" if short_role else build_name

            self.build_combo.addItem(display, userData=build)

            if current_build_name and build_name == current_build_name:
                selected_index = i

        if builds:
            self.build_combo.setCurrentIndex(selected_index)
            selected = builds[selected_index]
            self.set_title(selected["build_name"].upper())
            self._set_role_tag(selected.get("role", ""))

        self.build_combo.blockSignals(False)

    def _on_class_selected(self, class_name: str):

        if not class_name:
            return

        self.class_changed.emit(class_name)

    def _on_build_selected(self, index: int):

        if index < 0:
            return

        build = self.build_combo.itemData(index)

        if not build:
            return

        build_name = build["build_name"]

        self.set_title(build_name.upper())
        self._set_role_tag(build.get("role", ""))
        self.build_changed.emit(build_name)

    # ---------------------------------------------------------
    # Level input wiring
    # ---------------------------------------------------------

    def _on_submit(self):

        text = self.level_input.text().strip()

        if not text.isdigit():
            return

        self.level_changed.emit(int(text))

    def set_level_value(self, level: int):
        """Populate the level field without emitting ``level_changed`` -
        used to restore a saved level on startup/class-switch instead of
        always showing the empty placeholder."""

        self.level_input.setText(str(level))

    # ---------------------------------------------------------
    # Shared row helpers
    # ---------------------------------------------------------

    @staticmethod
    def _insert_row(layout: QVBoxLayout, widget):
        layout.insertWidget(layout.count() - 1, widget)

    @staticmethod
    def _clear_rows(layout: QVBoxLayout):

        while layout.count() > 1:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

    def _add_row(self, layout: QVBoxLayout, container: QWidget, text: str):

        row = BodyLabel(text, container)
        row.setWordWrap(True)
        row.setStyleSheet(
            f"""
            background-color: {SURFACE_ALT};
            color: {TEXT_PRIMARY};
            border-radius: 8px;
            padding: 8px;
            font-size: 12px;
            """
        )
        self._insert_row(layout, row)

    def _add_section_header(self, layout: QVBoxLayout, container: QWidget, text: str):

        header = CaptionLabel(text, container)
        header.setTextColor(QColor(ACCENT_GOLD), QColor(ACCENT_GOLD))
        self._insert_row(layout, header)

    # ---------------------------------------------------------
    # Content population
    # ---------------------------------------------------------

    def set_progress(self, data: dict):

        self._set_leveling(data)
        self._set_paragon(data)
        self._set_gear(data)

    def _set_leveling(self, data: dict):

        layout = self.progress_layout
        container = self.progress_container

        self._clear_rows(layout)

        if data["reached"]:
            for milestone in data["reached"]:
                self._add_row(
                    layout,
                    container,
                    f"Lvl {milestone['level']} — {milestone['skill']}\n{milestone['note']}",
                )
        else:
            self._add_row(layout, container, "No milestones reached yet at this level.")

        if data["next"]:
            nxt = data["next"]
            self.next_label.setText(f"Next: Lvl {nxt['level']} — {nxt['skill']}")
        else:
            self.next_label.setText("Build fully unlocked!")

    def _set_paragon(self, data: dict):

        layout = self.paragon_layout
        container = self.paragon_container

        self._clear_rows(layout)

        paragon = data.get("paragon") or {}
        boards = paragon.get("boards") or []
        glyphs = paragon.get("glyphs") or []
        note = paragon.get("note") or ""

        self._add_section_header(layout, container, "PARAGON BOARD")

        if boards:
            board_text = "\n".join(
                f"{i + 1}. {b['name']} — {b.get('note', '')}".rstrip(" —")
                for i, b in enumerate(boards)
            )
            self._add_row(layout, container, board_text)
        else:
            self._add_row(
                layout, container, "Board order not published as text by Maxroll for this build."
            )

        if glyphs:
            self._add_row(layout, container, "Glyphs (priority order): " + ", ".join(glyphs))

        if note:
            self._add_row(layout, container, note)

    def _set_gear(self, data: dict):

        layout = self.gear_layout
        container = self.gear_container

        self._clear_rows(layout)

        gear = data.get("gear")

        if not gear:
            self._add_section_header(layout, container, "GEAR && POWERS")
            self._add_row(
                layout,
                container,
                "Maxroll has no dedicated endgame guide for this build yet - "
                "leveling milestones and Paragon are still fully available.",
            )
            return

        key_items = gear.get("key_items") or []
        key_aspects = gear.get("key_aspects") or []
        stat_priority = gear.get("stat_priority") or []
        skill_bar = gear.get("skill_bar") or []

        self._add_section_header(layout, container, "KEY / SIGNATURE ITEMS")

        if key_items:
            for item in key_items:
                slot = item.get("slot", "")
                header = f"{item['name']} ({slot})" if slot else item["name"]
                note = item.get("note", "")
                self._add_row(layout, container, f"{header}\n{note}".rstrip())
        else:
            self._add_row(layout, container, "No specific key items listed.")

        self._add_section_header(layout, container, "KEY ASPECTS")

        if key_aspects:
            for aspect in key_aspects:
                note = aspect.get("note", "")
                self._add_row(layout, container, f"{aspect['name']}\n{note}".rstrip())
        else:
            self._add_row(layout, container, "No specific key aspects listed.")

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
    # Skills tab
    # ---------------------------------------------------------

    def set_skills(
        self,
        milestones: list[dict],
        skill_bar: list[str],
        skill_bar_is_fallback: bool,
        completed_levels: set[int],
    ):
        """Populate the Skills tab. ``milestones`` is the same data the
        Leveling tab reads (unfiltered by the level field) - completion
        here is tracked separately via ``completed_levels`` (persisted by
        the caller in QSettings), not derived from the level input."""

        layout = self.skills_layout
        container = self.skills_container

        self._clear_rows(layout)

        header = "SKILL BAR" + (" (estimated)" if skill_bar_is_fallback else "")
        self._add_section_header(layout, container, header)

        if skill_bar:
            self._add_row(layout, container, " • ".join(skill_bar))
        else:
            self._add_row(layout, container, "No skill data available for this build.")

        self._add_section_header(layout, container, "SKILL TREE PROGRESSION")

        if not milestones:
            self._add_row(layout, container, "No milestones defined for this build.")
            self.skills_next_label.setText("Pick a build to see your next skill point.")
            return

        next_milestone = next(
            (m for m in milestones if m["level"] not in completed_levels), None
        )

        if next_milestone:
            self.skills_next_label.setText(
                f"Next: Lvl {next_milestone['level']} — {next_milestone['skill']}"
            )
        else:
            self.skills_next_label.setText("All skill milestones completed!")

        for milestone in milestones:
            is_done = milestone["level"] in completed_levels
            is_next = milestone is next_milestone
            self._add_milestone_row(layout, container, milestone, is_done, is_next)

    def _add_milestone_row(
        self, layout: QVBoxLayout, container: QWidget, milestone: dict, is_done: bool, is_next: bool
    ):

        row = QWidget(container)
        row.setObjectName("milestoneRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(8, 8, 8, 8)
        row_layout.setSpacing(8)

        if is_done:
            status = "✓ Completed"
        elif is_next:
            status = "→ Next"
        else:
            status = "○ Future"

        note = milestone.get("note", "")
        text = f"{status} — Lvl {milestone['level']} — {milestone['skill']}\n{note}".rstrip()

        label = BodyLabel(text, row)
        label.setWordWrap(True)
        text_color = QColor(ACCENT_GOLD) if is_next else QColor(TEXT_PRIMARY)
        label.setTextColor(text_color, text_color)
        row_layout.addWidget(label, 1)

        if not is_done:
            done_button = PushButton("Mark as Done", row)
            done_button.clicked.connect(
                lambda _checked=False, lvl=milestone["level"]: self.mark_done.emit(lvl)
            )
            row_layout.addWidget(done_button, 0)

        border = f"1px solid {ACCENT_GOLD}" if is_next else "1px solid transparent"
        row.setStyleSheet(
            f"""
            QWidget#milestoneRow {{
                background-color: {SURFACE_ALT};
                border-radius: 8px;
                border: {border};
            }}
            """
        )
        self._insert_row(layout, row)
