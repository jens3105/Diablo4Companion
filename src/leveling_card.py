from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIntValidator
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    ComboBox,
    FluentIcon as FIF,
    LineEdit,
    PrimaryPushButton,
    SingleDirectionScrollArea,
    StrongBodyLabel,
)

from src.base_card import BaseCard
from src.theme import ACCENT_GOLD, SURFACE_ALT, TEXT_MUTED


class LevelingCard(BaseCard):
    """Build-guide progress tracker.

    Lets the player pick a Maxroll leveling build from a dropdown and
    enter their current character level, then shows every milestone
    reached so far plus the next one coming up.
    """

    level_changed = Signal(int)
    build_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__("BUILD GUIDE", icon=FIF.EDUCATION, parent=parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(260, 220)

        # -------------------------
        # Build selector
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
        # Next milestone
        # -------------------------

        self.next_label = StrongBodyLabel(
            "Pick a build and enter your level to see what's next.", self.content
        )
        self.next_label.setWordWrap(True)
        self.next_label.setTextColor(QColor(ACCENT_GOLD), QColor(ACCENT_GOLD))

        self.add_widget(self.next_label)

        # -------------------------
        # Milestone history (scrollable)
        # -------------------------

        scroll = SingleDirectionScrollArea(self.content, orient=Qt.Vertical)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background: transparent; border: none;}")

        self.progress_container = QWidget()
        self.progress_container.setStyleSheet("background: transparent;")
        self.progress_layout = QVBoxLayout(self.progress_container)
        self.progress_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_layout.setSpacing(6)
        self.progress_layout.addStretch()

        scroll.setWidget(self.progress_container)

        self.add_widget(scroll)
        self.content_layout.setStretch(self.content_layout.count() - 1, 1)

    # ---------------------------------------------------------
    # Build list wiring
    # ---------------------------------------------------------

    def set_builds(self, builds, current_build_name: str | None = None):
        """``builds`` is a list of {"build_name", "class_name"} dicts."""

        self.build_combo.blockSignals(True)
        self.build_combo.clear()

        selected_index = 0

        for i, b in enumerate(builds):
            label = f"{b['class_name']} – {b['build_name']}" if b.get("class_name") else b["build_name"]
            self.build_combo.addItem(label, userData=b["build_name"])

            if current_build_name and b["build_name"] == current_build_name:
                selected_index = i

        if builds:
            self.build_combo.setCurrentIndex(selected_index)
            self.set_title(f"{builds[selected_index]['build_name'].upper()}")

        self.build_combo.blockSignals(False)

    def _on_build_selected(self, index: int):

        if index < 0:
            return

        build_name = self.build_combo.itemData(index)

        if not build_name:
            return

        self.set_title(f"{build_name.upper()}")
        self.build_changed.emit(build_name)

    # ---------------------------------------------------------
    # Level input wiring
    # ---------------------------------------------------------

    def _on_submit(self):

        text = self.level_input.text().strip()

        if not text.isdigit():
            return

        self.level_changed.emit(int(text))

    def _insert_row(self, widget):
        self.progress_layout.insertWidget(self.progress_layout.count() - 1, widget)

    def _add_history_row(self, text: str):

        row = BodyLabel(text, self.progress_container)
        row.setWordWrap(True)
        row.setStyleSheet(
            f"""
            background-color: {SURFACE_ALT};
            border-radius: 8px;
            padding: 8px;
            font-size: 12px;
            """
        )
        self._insert_row(row)

    def _add_section_header(self, text: str):

        header = CaptionLabel(text, self.progress_container)
        header.setTextColor(QColor(ACCENT_GOLD), QColor(ACCENT_GOLD))
        self._insert_row(header)

    def set_progress(self, data: dict):

        while self.progress_layout.count() > 1:
            item = self.progress_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # -------------------------
        # Leveling milestones
        # -------------------------

        self._add_section_header("LEVELING MILESTONES")

        if data["reached"]:
            for milestone in data["reached"]:
                self._add_history_row(
                    f"Lvl {milestone['level']} — {milestone['skill']}\n{milestone['note']}"
                )
        else:
            self._add_history_row("No milestones reached yet at this level.")

        if data["next"]:
            nxt = data["next"]
            self.next_label.setText(
                f"Next: Lvl {nxt['level']} — {nxt['skill']}"
            )
        else:
            self.next_label.setText("Build fully unlocked!")

        # -------------------------
        # Paragon board
        # -------------------------

        paragon = data.get("paragon") or {}
        boards = paragon.get("boards") or []
        glyphs = paragon.get("glyphs") or []
        note = paragon.get("note") or ""

        self._add_section_header("PARAGON BOARD")

        if boards:
            board_text = "\n".join(
                f"{i + 1}. {b['name']} — {b.get('note', '')}".rstrip(" —")
                for i, b in enumerate(boards)
            )
            self._add_history_row(board_text)
        else:
            self._add_history_row(
                "Board order not published as text by Maxroll for this build."
            )

        if glyphs:
            self._add_history_row("Glyphs (priority order): " + ", ".join(glyphs))

        if note:
            self._add_history_row(note)
