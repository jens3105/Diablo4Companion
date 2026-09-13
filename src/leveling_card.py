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
    SubtitleLabel,
    SwitchButton,
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
    mark_board_done = Signal(int)
    gear_owned_changed = Signal(str, bool)

    LEVELING_KEY = "leveling"
    SKILLS_KEY = "skills"
    PARAGON_KEY = "paragon"
    GEAR_KEY = "gear"

    # Diablo IV's actual level cap - hardcoded since it hasn't changed in
    # a way that needs to be data-driven for this app's purposes.
    LEVEL_CAP = 70

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
        # Build Status summary (Phase 6) - a compact, always-visible
        # rollup of all 4 tabs' completion state, sitting above the
        # class/build selector so it's visible regardless of which tab
        # is active. Purely a read-out of state owned by MainWindow
        # (QSettings completed_levels/completed_boards/owned_items) -
        # this widget has no state of its own, just a setter.
        # -------------------------

        self.status_widget = self._build_status_widget()
        self.add_widget(self.status_widget)

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
        self.gear_page = self._build_gear_page()

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

        self.level_label = SubtitleLabel(f"LEVEL — / {self.LEVEL_CAP}", page)
        layout.addWidget(self.level_label)

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

    def _build_gear_page(self) -> QWidget:
        """Like ``_build_leveling_page``/``_build_skills_page``, but the
        strong label up top is a build-readiness rollup ("X / Y key items
        equipped") instead of a "next" pointer - gear has no natural
        order, so there's nothing to point at, only a count."""

        page = QWidget(self.content)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self.gear_rollup_label = StrongBodyLabel(
            "Pick a build to see gear readiness.", page
        )
        self.gear_rollup_label.setWordWrap(True)
        self.gear_rollup_label.setTextColor(QColor(ACCENT_GOLD), QColor(ACCENT_GOLD))
        layout.addWidget(self.gear_rollup_label)

        scroll, container, inner_layout = self._make_scroll_area(page)
        self.gear_container = container
        self.gear_layout = inner_layout

        layout.addWidget(scroll, 1)

        return page

    def _build_status_widget(self) -> QWidget:
        """Build the compact Build Status card (see ``set_build_status``
        for what actually populates it). Just a header, a monospace-ish
        block of one line per category, and a single "footer" line that
        holds either the missing-gear count or the "BUILD READY" badge -
        kept to a handful of lines total, not a dashboard of its own."""

        widget = QWidget(self.content)
        widget.setObjectName("buildStatusWidget")

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        header = CaptionLabel("BUILD STATUS", widget)
        header.setTextColor(QColor(ACCENT_GOLD), QColor(ACCENT_GOLD))
        layout.addWidget(header)

        self.status_rows_label = BodyLabel("", widget)
        self.status_rows_label.setWordWrap(True)
        self.status_rows_label.setStyleSheet("font-family: monospace; font-size: 12px;")
        layout.addWidget(self.status_rows_label)

        self.status_footer_label = CaptionLabel("", widget)
        layout.addWidget(self.status_footer_label)

        widget.setStyleSheet(
            f"""
            QWidget#buildStatusWidget {{
                background-color: {SURFACE_ALT};
                border-radius: 8px;
            }}
            """
        )

        return widget

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

    def set_leveling(self, level: int, milestones: list[dict], completed_levels: set[int]):
        """Populate the Leveling tab as the same kind of checklist the
        Skills tab shows - ``milestones``/``completed_levels`` are the
        exact same shared progression data (see ``set_skills``); this
        tab just frames it around the player's current level instead of
        the skill bar."""

        layout = self.progress_layout
        container = self.progress_container

        self._clear_rows(layout)

        self.level_label.setText(f"LEVEL {level} / {self.LEVEL_CAP}")

        if not milestones:
            self._add_row(layout, container, "No milestones defined for this build.")
            self.next_label.setText("Pick a build and enter your level to see what's next.")
            return

        next_milestone = self._render_milestone_checklist(
            layout, container, milestones, completed_levels
        )

        if next_milestone:
            self.next_label.setText(
                f"Next: Lvl {next_milestone['level']} — {next_milestone['skill']}"
            )
        else:
            self.next_label.setText("Build fully unlocked!")

    def set_build_status(self, rows: list[tuple[str, str, str]], footer_text: str, footer_is_ready: bool):
        """Render the Build Status summary. ``rows`` is a list of
        ``(emoji, label, pct_text)`` tuples, one per category, in
        display order (Skills/Leveling/Paragon/Gear) - the caller (
        ``MainWindow._refresh_build_status``) does all the aggregation
        over the existing per-tab QSettings state; this just draws it.
        ``footer_text`` is either an "N items missing" line, a
        "BUILD READY" badge, or empty (nothing left to say)."""

        lines = [f"{emoji} {label:<9}{pct}" for emoji, label, pct in rows]
        self.status_rows_label.setText("\n".join(lines))

        self.status_footer_label.setText(footer_text)
        color = QColor(ACCENT_GOLD) if footer_is_ready else QColor(TEXT_MUTED)
        self.status_footer_label.setTextColor(color, color)
        self.status_footer_label.setVisible(bool(footer_text))

    def set_paragon(
        self, boards: list[dict], glyphs: list[str], note: str, completed_boards: set[int]
    ):
        """Populate the Paragon tab as the same kind of ✓/→/○ checklist
        used by Leveling/Skills, one row per board in ``paragon.boards``
        (see ``_render_board_checklist``). Completion is tracked at
        board granularity via ``completed_boards`` (persisted by the
        caller in its own QSettings key, separate from the milestone
        completed-levels key) - Maxroll mostly only publishes board
        *names* + a free-text note, not node-by-node data, so this is
        the honest level of detail for a first version."""

        layout = self.paragon_layout
        container = self.paragon_container

        self._clear_rows(layout)

        self._add_section_header(layout, container, "PARAGON BOARDS")

        if boards:
            self._render_board_checklist(layout, container, boards, completed_boards)
        else:
            self._add_row(
                layout, container, "Board order not published as text by Maxroll for this build."
            )

        if glyphs:
            self._add_section_header(layout, container, "GLYPHS (PRIORITY ORDER)")
            self._add_row(layout, container, ", ".join(glyphs))

        if note:
            self._add_row(layout, container, note)

    def set_gear(self, gear: dict | None, owned_names: set[str]):
        """Populate the Gear & Powers tab as a toggle checklist over
        ``key_items``/``key_aspects`` - unlike the one-way Leveling/
        Skills/Paragon checklists, gear ownership can be lost (an item
        sold/replaced), so each row gets a two-way "Have it"/"Missing"
        toggle (see ``_add_toggle_row``) instead of a one-way "Mark as
        Done" button, and there's a rollup ("X / Y key items equipped")
        up top instead of a "next" pointer so build-readiness is visible
        at a glance. ``stat_priority``/``skill_bar`` stay plain reference
        text, same as before - they aren't checkable items."""

        layout = self.gear_layout
        container = self.gear_container

        self._clear_rows(layout)

        if not gear:
            self.gear_rollup_label.setText(
                "No endgame gear guide available for this build."
            )
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
            self._render_gear_checklist(layout, container, key_items, owned_names)
        else:
            self._add_row(layout, container, "No specific key items listed.")

        self._add_section_header(layout, container, "KEY ASPECTS")

        if key_aspects:
            self._render_gear_checklist(layout, container, key_aspects, owned_names)
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

        next_milestone = self._render_milestone_checklist(
            layout, container, milestones, completed_levels
        )

        if next_milestone:
            self.skills_next_label.setText(
                f"Next: Lvl {next_milestone['level']} — {next_milestone['skill']}"
            )
        else:
            self.skills_next_label.setText("All skill milestones completed!")

    def _render_milestone_checklist(
        self,
        layout: QVBoxLayout,
        container: QWidget,
        milestones: list[dict],
        completed_levels: set[int],
    ):
        """Render ``milestones`` as ✓ Completed / → Next / ○ Future rows
        (via ``_add_milestone_row``), driven by the shared per-build
        ``completed_levels`` state. Used by both the Leveling and Skills
        tabs so the two views never fall out of sync. Returns the next
        incomplete milestone, or ``None`` if everything is done."""

        next_milestone = next(
            (m for m in milestones if m["level"] not in completed_levels), None
        )

        for milestone in milestones:
            is_done = milestone["level"] in completed_levels
            is_next = milestone is next_milestone
            self._add_milestone_row(layout, container, milestone, is_done, is_next)

        return next_milestone

    def _add_milestone_row(
        self, layout: QVBoxLayout, container: QWidget, milestone: dict, is_done: bool, is_next: bool
    ):

        skill_label = milestone["skill"]
        points = milestone.get("points")

        if points is not None:
            plural = "" if points == 1 else "s"
            skill_label += f" ({points} point{plural})"

        title = f"Lvl {milestone['level']} — {skill_label}"

        notes = []

        note = milestone.get("note", "")
        if note:
            notes.append(note)

        points_note = milestone.get("points_note", "")
        if points_note:
            notes.append(f"★ {points_note}")

        self._add_checklist_row(
            layout, container, title, notes, is_done, is_next, self.mark_done, milestone["level"]
        )

    # ---------------------------------------------------------
    # Paragon tab
    # ---------------------------------------------------------

    def _render_board_checklist(
        self,
        layout: QVBoxLayout,
        container: QWidget,
        boards: list[dict],
        completed_boards: set[int],
    ):
        """Same ✓/→/○ pattern as ``_render_milestone_checklist``, but
        driven by a board's position in the list (there's no natural
        "level" key for a Paragon board) instead of a milestone level."""

        next_index = next(
            (i for i in range(len(boards)) if i not in completed_boards), None
        )

        for i, board in enumerate(boards):
            is_done = i in completed_boards
            is_next = i == next_index
            self._add_board_row(layout, container, i, board, is_done, is_next)

        return next_index

    def _add_board_row(
        self, layout: QVBoxLayout, container: QWidget, index: int, board: dict, is_done: bool, is_next: bool
    ):

        title = f"{index + 1}. {board['name']}"

        notes = []
        note = board.get("note", "")
        if note:
            notes.append(note)

        self._add_checklist_row(
            layout, container, title, notes, is_done, is_next, self.mark_board_done, index
        )

    # ---------------------------------------------------------
    # Shared checklist row renderer (Leveling/Skills milestones, Paragon
    # boards, and Gear items/aspects all funnel through the same row
    # shell - ``_make_row_shell`` - and only differ in what action
    # widget goes on the right: a one-way "Mark as Done" button for the
    # first three, or a two-way "Have it"/"Missing" toggle for gear.
    # ---------------------------------------------------------

    def _make_row_shell(
        self,
        container: QWidget,
        status: str,
        title: str,
        notes: list[str],
        highlight: bool,
        bordered: bool = False,
    ):
        """Build the shared row background/label (status + title + notes)
        used by every checklist row. Returns ``(row, row_layout)`` so the
        caller can append its own action widget (button or toggle) to
        ``row_layout`` before inserting ``row`` into the page layout."""

        row = QWidget(container)
        row.setObjectName("milestoneRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(8, 8, 8, 8)
        row_layout.setSpacing(8)

        lines = [f"{status} — {title}"] + notes
        text = "\n".join(lines)

        label = BodyLabel(text, row)
        label.setWordWrap(True)
        text_color = QColor(ACCENT_GOLD) if highlight else QColor(TEXT_PRIMARY)
        label.setTextColor(text_color, text_color)
        row_layout.addWidget(label, 1)

        border = f"1px solid {ACCENT_GOLD}" if bordered else "1px solid transparent"
        row.setStyleSheet(
            f"""
            QWidget#milestoneRow {{
                background-color: {SURFACE_ALT};
                border-radius: 8px;
                border: {border};
            }}
            """
        )

        return row, row_layout

    def _add_checklist_row(
        self,
        layout: QVBoxLayout,
        container: QWidget,
        title: str,
        notes: list[str],
        is_done: bool,
        is_next: bool,
        signal: Signal,
        key,
    ):

        if is_done:
            status = "✓ Completed"
        elif is_next:
            status = "→ Next"
        else:
            status = "○ Future"

        row, row_layout = self._make_row_shell(
            container, status, title, notes, highlight=is_next, bordered=is_next
        )

        if not is_done:
            done_button = PushButton("Mark as Done", row)
            done_button.clicked.connect(
                lambda _checked=False, k=key: signal.emit(k)
            )
            row_layout.addWidget(done_button, 0)

        self._insert_row(layout, row)

    # ---------------------------------------------------------
    # Gear tab
    # ---------------------------------------------------------

    def _render_gear_checklist(
        self,
        layout: QVBoxLayout,
        container: QWidget,
        entries: list[dict],
        owned_names: set[str],
    ):
        """Render ``entries`` (``key_items`` or ``key_aspects``) as
        toggle rows via ``_add_toggle_row``. Both lists share the same
        ``{"name", "note"}`` shape (items also carry a ``slot``), and
        both toggle the same ``gear_owned_changed`` signal/QSettings set
        keyed by name - Maxroll item and aspect names don't collide, so
        one flat "owned names" set is enough for both."""

        for entry in entries:
            slot = entry.get("slot", "")
            title = f"{entry['name']} ({slot})" if slot else entry["name"]

            notes = []
            note = entry.get("note", "")
            if note:
                notes.append(note)

            is_owned = entry["name"] in owned_names
            self._add_toggle_row(
                layout, container, title, notes, is_owned, entry["name"]
            )

    def _add_toggle_row(
        self,
        layout: QVBoxLayout,
        container: QWidget,
        title: str,
        notes: list[str],
        is_owned: bool,
        key: str,
    ):

        status = "✓ Have it" if is_owned else "○ Missing"

        row, row_layout = self._make_row_shell(
            container, status, title, notes, highlight=is_owned
        )

        toggle = SwitchButton(row)
        toggle.setOnText("Have it")
        toggle.setOffText("Missing")
        toggle.setChecked(is_owned)
        toggle.checkedChanged.connect(
            lambda checked, k=key: self.gear_owned_changed.emit(k, checked)
        )
        row_layout.addWidget(toggle, 0)

        self._insert_row(layout, row)
