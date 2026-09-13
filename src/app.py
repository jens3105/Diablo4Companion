from datetime import datetime, timezone

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QInputDialog, QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    ComboBox,
    FluentIcon as FIF,
    FluentWindow,
    NavigationItemPosition,
    StrongBodyLabel,
    SubtitleLabel,
    SwitchButton,
)

from src import theme
from src.api import DiabloAPI
from src.compact_window import CompactWindow
from src.dashboard import DashboardWidget
from src.leveling_card import LevelingCard
from src.managers.leveling_manager import LevelingManager


class BuildsInterface(QWidget):
    """Dedicated page for the build-guide / leveling tracker.

    Giving it a full page (instead of squeezing it into a dashboard
    tile) is what let the dashboard grid shrink back down to a size
    that actually fits a normal screen.
    """

    def __init__(self, leveling_card: LevelingCard, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        leveling_card.setMinimumWidth(460)
        leveling_card.setMaximumWidth(760)

        layout.addStretch(1)
        layout.addWidget(leveling_card, 3)
        layout.addStretch(1)


class SettingsInterface(QWidget):
    """About page + appearance controls. Replaces the old decorative
    'Settings' entry in the plain QListWidget sidebar, which never
    actually did anything.

    The dark/light toggle and the seasonal accent-preset picker apply
    live (via ``theme.set_appearance``, which both re-styles every
    built-in qfluentwidgets widget and fires ``theme.theme_changed`` for
    this app's own hard-coded colors - see ``MainWindow._on_theme_changed``)
    and are persisted to ``settings`` so they survive a restart."""

    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)

        self.settings = settings

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setAlignment(Qt.AlignTop)
        layout.setSpacing(12)

        title = SubtitleLabel("Diablo IV Companion", self)
        layout.addWidget(title)

        info = BodyLabel(
            "A lightweight second-screen companion app for Diablo IV. It "
            "does not read game state - it's a pure reference/timer tool "
            "you run alongside the game (PC or console) to track World "
            "Boss, Helltide and Legion timers, the current season "
            "countdown, and Maxroll leveling-build progress.\n\n"
            "Built with PySide6 and PySide6-Fluent-Widgets.",
            self,
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addSpacing(16)

        appearance_title = StrongBodyLabel("Appearance", self)
        layout.addWidget(appearance_title)

        # -------------------------
        # Dark / Light toggle
        # -------------------------

        theme_row = QHBoxLayout()
        theme_row.setSpacing(10)

        theme_label = CaptionLabel("Theme:", self)
        theme_row.addWidget(theme_label)

        self.theme_switch = SwitchButton(self)
        self.theme_switch.setOnText("Dark")
        self.theme_switch.setOffText("Light")
        self.theme_switch.blockSignals(True)
        self.theme_switch.setChecked(theme.current_mode() == theme.MODE_DARK)
        self.theme_switch.blockSignals(False)
        self.theme_switch.checkedChanged.connect(self._on_theme_toggled)
        theme_row.addWidget(self.theme_switch)
        theme_row.addStretch(1)

        layout.addLayout(theme_row)

        # -------------------------
        # Seasonal accent preset
        # -------------------------

        preset_row = QHBoxLayout()
        preset_row.setSpacing(10)

        preset_label = CaptionLabel("Accent preset:", self)
        preset_row.addWidget(preset_label)

        self._preset_keys = [
            theme.PRESET_DEFAULT,
            theme.PRESET_CHRISTMAS,
            theme.PRESET_HALLOWEEN,
        ]

        self.preset_combo = ComboBox(self)
        self.preset_combo.addItems([theme.PRESET_LABELS[key] for key in self._preset_keys])
        self.preset_combo.setMinimumWidth(140)
        self.preset_combo.blockSignals(True)
        self.preset_combo.setCurrentIndex(self._preset_keys.index(theme.current_preset()))
        self.preset_combo.blockSignals(False)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_row.addWidget(self.preset_combo)
        preset_row.addStretch(1)

        layout.addLayout(preset_row)

        layout.addStretch(1)

    def _on_theme_toggled(self, checked: bool):
        mode = theme.MODE_DARK if checked else theme.MODE_LIGHT
        self.settings.setValue("appearance/theme", mode)
        theme.set_appearance(mode, theme.current_preset())

    def _on_preset_changed(self, index: int):
        preset = self._preset_keys[index]
        self.settings.setValue("appearance/accent_preset", preset)
        theme.set_appearance(theme.current_mode(), preset)


class MainWindow(FluentWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Diablo IV Companion")
        self._init_window_geometry()

        self.api = DiabloAPI()

        self.current_boss = None
        self.current_legion = None
        self.current_helltide = None
        self.season_15_start = None

        self.leveling_manager = LevelingManager()

        # Persists the last-selected Build Guide class/build/level across
        # full app restarts (plain local QSettings - no server, no new
        # dependency). Written from on_build_changed/on_level_changed,
        # read back once at startup in _restore_leveling_selection.
        self.settings = QSettings("Diablo4Companion", "DesktopCompanion")

        # The manager's own baked-in default build (Blazing Scream Warlock,
        # or whatever build sorts first) - captured once, before anything
        # can mutate ``current_build_name``, so a freshly created character
        # with no saved build of its own always falls back to this instead
        # of silently inheriting whatever build was active a moment ago.
        self._manager_default_build = self.leveling_manager.current_build_name

        # Phase 8: multiple characters, each with its own class/build/level
        # selection and its own Skills/Paragon/Gear completion state, so
        # e.g. a PS5 character and a PC character never mix progress. See
        # _migrate_to_characters for how pre-Phase-8 single-profile data
        # (the old "leveling/*", "skills/*", "paragon/*", "gear/*" keys)
        # is folded into a first "Character 1" instead of being lost.
        self._migrate_to_characters()
        self.active_character_id = self.settings.value(
            "characters/active", "character_1", type=str
        )
        self.characters = self._load_characters()

        # ---------------------------------------------------------
        # Pages / navigation
        # ---------------------------------------------------------

        self.dashboard = DashboardWidget()
        self.dashboard.setObjectName("dashboardInterface")

        self.leveling_card = LevelingCard()

        self.builds_interface = BuildsInterface(self.leveling_card)
        self.builds_interface.setObjectName("buildsInterface")

        self.settings_interface = SettingsInterface(self.settings)
        self.settings_interface.setObjectName("settingsInterface")

        self.addSubInterface(self.dashboard, FIF.HOME, "Dashboard")
        self.addSubInterface(self.builds_interface, FIF.GAME, "Build Guide")
        self.addSubInterface(
            self.settings_interface,
            FIF.SETTING,
            "Settings",
            position=NavigationItemPosition.BOTTOM,
        )

        # Current Build card on the Dashboard jumps straight to the Build
        # Guide page when clicked (Phase 7 nice-to-have) - trivial thanks
        # to FluentWindow's built-in switchTo.
        self.dashboard.build_card.clicked.connect(
            lambda: self.switchTo(self.builds_interface)
        )

        # Phase 9: Compact Mode - lazily created on first use, torn down
        # (set back to None) when the user closes it, so re-opening it
        # always starts from a clean, freshly-synced window.
        self.compact_window = None
        self._compact_done_level = None
        self.dashboard.build_card.compact_mode_requested.connect(
            self.open_compact_mode
        )

        # Keep the sidebar expanded (with text labels) at our default
        # window width instead of collapsing to icon-only.
        self.navigationInterface.setMinimumExpandWidth(800)
        self.navigationInterface.setReturnButtonVisible(False)
        self.navigationInterface.expand(useAni=False)

        self.load_world_boss()
        self.load_legion()
        self.load_helltide()
        self.load_upcoming_events()
        self.load_season_15()

        self.leveling_card.set_characters(self.characters, self.active_character_id)
        # Show milestones for the restored (or default) build/level
        # straight away, without re-persisting what we just loaded.
        self._apply_active_character()

        self.leveling_card.level_changed.connect(self.on_level_changed)
        self.leveling_card.build_changed.connect(self.on_build_changed)
        self.leveling_card.class_changed.connect(self.on_class_changed)
        self.leveling_card.mark_done.connect(self.on_mark_done)
        self.leveling_card.mark_board_done.connect(self.on_mark_board_done)
        self.leveling_card.gear_owned_changed.connect(self.on_gear_owned_changed)
        self.leveling_card.character_changed.connect(self.on_character_changed)
        self.leveling_card.add_character_requested.connect(self.on_add_character)
        self.leveling_card.rename_character_requested.connect(self.on_rename_character)

        # Settings page's dark/light + seasonal accent-preset picker fires
        # this whenever it changes theme.py's colors, so every already-
        # built widget with a hard-coded color can re-apply it live.
        theme.theme_changed.changed.connect(self._on_theme_changed)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_countdown)
        self.timer.start(1000)

    # ---------------------------------------------------------
    # Theme / appearance
    # ---------------------------------------------------------

    def _on_theme_changed(self):
        """Re-color every already-built widget after the Settings page
        flips dark/light mode or the seasonal accent preset.

        qfluentwidgets' own widgets (CardWidget backgrounds, buttons,
        combo boxes, the nav bar, scrollbars, ...) already re-styled
        themselves the moment ``theme.set_appearance`` called
        ``setTheme``/``setThemeColor`` - this only has to cover colors
        this app hard-codes itself (see ``src/theme.py``'s module
        docstring)."""

        for card in (
            self.dashboard.world_boss_card,
            self.dashboard.helltide_card,
            self.dashboard.legion_card,
            self.dashboard.season_card,
            self.dashboard.build_card,
            self.dashboard.upcoming_card,
            self.leveling_card,
        ):
            card.refresh_theme()

        if self.compact_window is not None:
            self.compact_window.refresh_theme()

        # The Build Guide's checklist rows (Leveling/Skills/Paragon/Gear)
        # and the Build Status summary already read theme.* fresh every
        # time they're drawn - re-running the same "populate the active
        # character" flow used on every build/level/character switch is
        # the simplest way to redraw them with the new colors too.
        self._apply_active_character()

    # ---------------------------------------------------------
    # Window sizing
    # ---------------------------------------------------------

    def _init_window_geometry(self):
        """Fit comfortably on a normal 1920x1080 screen, and shrink to fit
        smaller screens too - never taller/wider than what's available."""

        target_w, target_h = 1500, 850

        screen = QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None

        if available:
            target_w = min(target_w, max(900, available.width() - 40))
            target_h = min(target_h, max(600, available.height() - 40))

        self.resize(target_w, target_h)
        self.setMinimumSize(900, 600)

        if available:
            x = available.x() + (available.width() - target_w) // 2
            y = available.y() + (available.height() - target_h) // 2
            self.move(max(0, x), max(0, y))

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    @staticmethod
    def _subtitle(base: str, entry: dict) -> str:
        """Append an 'estimated' marker when an entry came from the local
        fallback schedule instead of the live helltides.com API."""

        if entry and entry.get("estimated"):
            return f"{base} (estimated)"

        return base

    # ---------------------------------------------------------
    # WORLD BOSS
    # ---------------------------------------------------------

    def load_world_boss(self):

        self.current_boss = self.api.get_next_world_boss()

        if not self.current_boss:
            return

        card = self.dashboard.world_boss_card

        card.set_title(self.current_boss['boss'])
        card.set_subtitle(self._subtitle("Next Spawn", self.current_boss))

        zone = self.current_boss["zone"][0]["name"]

        start = datetime.fromisoformat(
            self.current_boss["startTime"].replace("Z", "+00:00")
        ).astimezone()

        card.set_status(
            f"📍 {zone}\n🕒 {start:%H:%M}"
        )

    # ---------------------------------------------------------
    # LEGION
    # ---------------------------------------------------------

    def load_legion(self):

        self.current_legion = self.api.get_next_legion()

        if not self.current_legion:
            return

        card = self.dashboard.legion_card

        card.set_title("LEGION")
        card.set_subtitle(self._subtitle("Next Event", self.current_legion))

        start = datetime.fromisoformat(
            self.current_legion["startTime"].replace("Z", "+00:00")
        ).astimezone()

        card.set_status(
            f"🕒 {start:%H:%M}"
        )

    # ---------------------------------------------------------
    # HELLTIDE
    # ---------------------------------------------------------

    def load_helltide(self):

        self.current_helltide = self.api.get_next_helltide()

        if not self.current_helltide:
            return

        card = self.dashboard.helltide_card

        card.set_title("HELLTIDE")
        card.set_subtitle(self._subtitle("Next Start", self.current_helltide))

        start = datetime.fromisoformat(
            self.current_helltide["startTime"].replace("Z", "+00:00")
        ).astimezone()

        card.set_status(f"🕒 {start:%H:%M}")

    # ---------------------------------------------------------
    # SEASON 15 COUNTDOWN
    # ---------------------------------------------------------

    def load_season_15(self):

        self.season_15_start = self.api.get_season_15_start()

        card = self.dashboard.season_card

        card.set_title("SEASON 15")
        card.set_subtitle("Hell's Legacy")

        local_start = self.season_15_start.astimezone()

        card.set_status(
            f"🕒 {local_start:%d/%m %H:%M}"
        )

    # ---------------------------------------------------------
    # BUILD-GUIDE / LEVELING
    # ---------------------------------------------------------

    def _restore_leveling_selection(self) -> str:
        """Look up the active character's last-selected build from
        QSettings and make it the LevelingManager's current build, if it
        still exists. Falls back to LevelingManager's own baked-in
        default (captured in ``_manager_default_build``) when this
        character has no saved build yet (e.g. it was just created) or
        the saved build was removed - never leaves the previously active
        character's build silently applied to a different character."""

        saved_build = self.settings.value(f"{self._char_prefix()}/build", "", type=str)
        target_build = saved_build or self._manager_default_build

        if target_build:
            self.leveling_manager.set_current_build(target_build)

        return self.leveling_manager.current_build_name

    # ---------------------------------------------------------
    # CHARACTERS (Phase 8)
    #
    # Everything the app tracks per build (class/build/level selection,
    # plus Skills/Paragon/Gear completion state) now lives under
    # "characters/<id>/..." instead of directly under
    # "leveling/"/"skills/"/"paragon/"/"gear/", so multiple characters
    # (e.g. one on PS5, one on PC) never mix progress. Only one
    # LevelingManager instance exists - switching characters just points
    # it at a different build and re-reads that character's completion
    # state, the same way switching builds within one character already
    # worked.
    # ---------------------------------------------------------

    def _migrate_to_characters(self):
        """One-time migration: if no character list exists yet, create
        "Character 1" and copy every pre-Phase-8 key ("leveling/build",
        "leveling/class", "leveling/level", and every "skills/*",
        "paragon/*", "gear/*" completion key) under it. The old keys are
        left in place untouched, never deleted - this is purely additive,
        so a bug here can at worst leave stale duplicate keys around, not
        lose anything."""

        existing_ids = self.settings.value("characters/ids", [], type=list)

        if existing_ids:
            return

        char_id = "character_1"

        self.settings.setValue(f"characters/{char_id}/name", "Character 1")

        old_build = self.settings.value("leveling/build", "", type=str)
        old_level = self.settings.value("leveling/level", 1, type=int)

        if old_build:
            self.settings.setValue(f"characters/{char_id}/build", old_build)

        self.settings.setValue(f"characters/{char_id}/level", old_level)

        for key in self.settings.allKeys():
            if key.startswith("skills/") or key.startswith("paragon/") or key.startswith("gear/"):
                self.settings.setValue(
                    f"characters/{char_id}/{key}", self.settings.value(key)
                )

        self.settings.setValue("characters/ids", [char_id])
        self.settings.setValue("characters/next_num", 2)
        self.settings.setValue("characters/active", char_id)

    def _load_characters(self) -> list[dict]:

        ids = self.settings.value("characters/ids", [], type=list)

        return [
            {
                "id": char_id,
                "name": self.settings.value(f"characters/{char_id}/name", char_id, type=str),
            }
            for char_id in ids
        ]

    def _char_prefix(self) -> str:
        return f"characters/{self.active_character_id}"

    def _apply_active_character(self):
        """Point every character-scoped view - LevelingManager's current
        build, the Build Guide's class/build/level selectors and its 4
        tabs + Build Status widget, and the Dashboard's Current Build
        card - at ``self.active_character_id``'s saved class/build/level
        and completion state. Used both at startup and whenever the
        character switcher fires."""

        default_build = self._restore_leveling_selection()
        default_class = self.leveling_manager.get_class_for_build(default_build)

        default_level = self.settings.value(f"{self._char_prefix()}/level", 1, type=int)
        default_level = max(1, min(100, default_level))

        self.leveling_card.set_classes(
            self.leveling_manager.list_classes(), default_class
        )
        self.leveling_card.set_builds_for_class(
            self.leveling_manager.list_builds_for_class(default_class), default_build
        )
        self.leveling_card.set_level_value(default_level)
        # Don't re-persist what we just loaded back onto this same
        # character.
        self.on_level_changed(default_level, persist=False)
        self._refresh_skills()
        self._refresh_paragon()
        self._refresh_gear()
        self._refresh_build_status()

    def _switch_character(self, char_id: str):

        self.active_character_id = char_id
        self.settings.setValue("characters/active", char_id)

        self._apply_active_character()

    def on_character_changed(self, char_id: str):

        if char_id == self.active_character_id:
            return

        self._switch_character(char_id)

    def on_add_character(self):

        next_num = self.settings.value("characters/next_num", 2, type=int)
        default_name = f"Character {next_num}"

        name, ok = QInputDialog.getText(
            self, "New Character", "Character name:", text=default_name
        )

        if not ok:
            return

        name = name.strip() or default_name
        char_id = f"character_{next_num}"

        ids = self.settings.value("characters/ids", [], type=list)
        ids.append(char_id)

        self.settings.setValue("characters/ids", ids)
        self.settings.setValue("characters/next_num", next_num + 1)
        self.settings.setValue(f"characters/{char_id}/name", name)

        self.characters = self._load_characters()
        self.leveling_card.set_characters(self.characters, char_id)
        self._switch_character(char_id)

    def on_rename_character(self):

        current_name = self.settings.value(
            f"characters/{self.active_character_id}/name", "", type=str
        )

        name, ok = QInputDialog.getText(
            self, "Rename Character", "Character name:", text=current_name
        )

        if not ok:
            return

        name = name.strip()

        if not name:
            return

        self.settings.setValue(f"characters/{self.active_character_id}/name", name)
        self.characters = self._load_characters()
        self.leveling_card.set_characters(self.characters, self.active_character_id)

    def _current_level(self) -> int:

        text = self.leveling_card.level_input.text().strip()

        return int(text) if text.isdigit() else 1

    def _refresh_leveling(self, level: int):
        """Rebuild the Leveling tab's checklist for the current build,
        using the exact same milestones + persisted completed-levels
        state as the Skills tab (see ``_refresh_skills``) - only the
        current level shown up top differs between the two views."""

        build_name = self.leveling_manager.current_build_name

        if not build_name:
            return

        milestones = self.leveling_manager.get_skills_data(build_name)["milestones"]
        completed = self._load_completed_levels(build_name)

        self.leveling_card.set_leveling(level, milestones, completed)

    def on_level_changed(self, level: int, persist: bool = True):

        self._refresh_leveling(level)
        self._refresh_dashboard_build_card()

        if persist:
            self.settings.setValue(f"{self._char_prefix()}/level", level)

    def on_build_changed(self, build_name: str):

        if not self.leveling_manager.set_current_build(build_name):
            return

        level = self._current_level()

        self._refresh_leveling(level)
        self._refresh_skills()
        self._refresh_paragon()
        self._refresh_gear()
        self._refresh_build_status()

        self.settings.setValue(
            f"{self._char_prefix()}/build", self.leveling_manager.current_build_name
        )
        self.settings.setValue(
            f"{self._char_prefix()}/class",
            self.leveling_manager.get_class_for_build(build_name),
        )

    # ---------------------------------------------------------
    # BUILD-GUIDE / SKILLS TAB
    # ---------------------------------------------------------

    def _completed_levels_key(self, build_name: str) -> str:
        # Historically named after "level", but actually keyed by each
        # milestone's *index* in the build's milestone list (see
        # LevelingCard._render_milestone_checklist) - several builds
        # unlock more than one skill at the same level, so a level-keyed
        # set would mark every milestone sharing that level as done at
        # once. Left as "completed_levels" rather than renamed, since the
        # per-build QSettings path already scopes it and nothing outside
        # this file/leveling_card.py ever reads the raw key name.
        return f"{self._char_prefix()}/skills/{build_name}/completed_levels"

    def _load_completed_levels(self, build_name: str) -> set[int]:

        raw = self.settings.value(self._completed_levels_key(build_name), [], type=list)
        completed = set()

        for value in raw:
            try:
                completed.add(int(value))
            except (TypeError, ValueError):
                continue

        return completed

    def _save_completed_levels(self, build_name: str, completed: set[int]):

        self.settings.setValue(self._completed_levels_key(build_name), sorted(completed))

    def _refresh_skills(self):
        """Rebuild the Skills tab for the current build, combining its
        (level-independent) milestones/skill-bar data with the persisted
        set of completed milestone levels."""

        build_name = self.leveling_manager.current_build_name

        if not build_name:
            return

        skills_data = self.leveling_manager.get_skills_data(build_name)
        completed = self._load_completed_levels(build_name)
        verified_build = self.leveling_manager.get_verified_build(build_name)

        self.leveling_card.set_skills(
            skills_data["milestones"],
            skills_data["skill_bar"],
            skills_data["skill_bar_is_fallback"],
            completed,
            verified_build,
        )

    def on_mark_done(self, index: int):
        """``index`` is a milestone's position in its build's milestone
        list (see ``LevelingCard._render_milestone_checklist``), not a
        game level - multiple milestones can share a level."""

        build_name = self.leveling_manager.current_build_name

        if not build_name:
            return

        completed = self._load_completed_levels(build_name)
        completed.add(index)
        self._save_completed_levels(build_name, completed)

        self._refresh_skills()
        self._refresh_leveling(self._current_level())
        self._refresh_build_status()

    # ---------------------------------------------------------
    # BUILD-GUIDE / PARAGON TAB
    # ---------------------------------------------------------

    def _completed_boards_key(self, build_name: str) -> str:
        # Its own QSettings key - Paragon boards and skill milestones are
        # different lists/units, so completion state is never conflated
        # into the shared "skills/.../completed_levels" key.
        return f"{self._char_prefix()}/paragon/{build_name}/completed_boards"

    def _load_completed_boards(self, build_name: str) -> set[int]:

        raw = self.settings.value(self._completed_boards_key(build_name), [], type=list)
        completed = set()

        for value in raw:
            try:
                completed.add(int(value))
            except (TypeError, ValueError):
                continue

        return completed

    def _save_completed_boards(self, build_name: str, completed: set[int]):

        self.settings.setValue(self._completed_boards_key(build_name), sorted(completed))

    def _refresh_paragon(self):
        """Rebuild the Paragon tab's board checklist for the current
        build, combining its (level-independent) board/glyph data with
        the persisted set of completed board indices."""

        build_name = self.leveling_manager.current_build_name

        if not build_name:
            return

        paragon = self.leveling_manager.get_paragon_data(build_name)
        completed = self._load_completed_boards(build_name)
        verified_build = self.leveling_manager.get_verified_build(build_name)

        self.leveling_card.set_paragon(
            paragon.get("boards") or [],
            paragon.get("glyphs") or [],
            paragon.get("note") or "",
            completed,
            verified_build,
        )

    def on_mark_board_done(self, index: int):

        build_name = self.leveling_manager.current_build_name

        if not build_name:
            return

        completed = self._load_completed_boards(build_name)
        completed.add(index)
        self._save_completed_boards(build_name, completed)

        self._refresh_paragon()
        self._refresh_build_status()

    # ---------------------------------------------------------
    # BUILD-GUIDE / GEAR & POWERS TAB
    # ---------------------------------------------------------

    def _owned_items_key(self, build_name: str) -> str:
        # Its own QSettings key, separate from the one-way completion
        # keys above - gear ownership can go backwards (an item sold or
        # replaced), so this stores a toggle state, not a monotonic
        # "completed" set.
        return f"{self._char_prefix()}/gear/{build_name}/owned_items"

    def _load_owned_items(self, build_name: str) -> set[str]:

        raw = self.settings.value(self._owned_items_key(build_name), [], type=list)
        return {str(name) for name in raw}

    def _save_owned_items(self, build_name: str, owned: set[str]):

        self.settings.setValue(self._owned_items_key(build_name), sorted(owned))

    def _refresh_gear(self):
        """Rebuild the Gear & Powers tab's toggle checklist for the
        current build, combining its (level-independent) key items/
        aspects data with the persisted set of owned item/aspect names."""

        build_name = self.leveling_manager.current_build_name

        if not build_name:
            return

        gear = self.leveling_manager.get_gear_data(build_name)
        owned = self._load_owned_items(build_name)

        self.leveling_card.set_gear(gear, owned)

    def on_gear_owned_changed(self, name: str, owned: bool):

        build_name = self.leveling_manager.current_build_name

        if not build_name:
            return

        owned_names = self._load_owned_items(build_name)

        if owned:
            owned_names.add(name)
        else:
            owned_names.discard(name)

        self._save_owned_items(build_name, owned_names)

        self._refresh_gear()
        self._refresh_build_status()

    # ---------------------------------------------------------
    # BUILD-GUIDE / BUILD STATUS SUMMARY (Phase 6)
    #
    # Pure aggregation over the completion state the four tabs above
    # already persist - no new tracking, no new QSettings keys. Recomputed
    # (cheaply - it's a handful of len()/set operations) on every event
    # that could move the needle: build/class switch and any checkbox/
    # toggle in any of the four tabs.
    # ---------------------------------------------------------

    @staticmethod
    def _pct(done: int, total: int) -> int | None:
        """Percent complete, or ``None`` when ``total`` is 0 - i.e. this
        build has no trackable data for that category at all, which is
        a "not applicable" state, not a 0%/red one."""

        return None if total <= 0 else round(100 * done / total)

    @staticmethod
    def _status_emoji(pct: int | None) -> str:

        if pct is None:
            return "⚪"
        if pct >= 90:
            return "🟢"
        if pct > 0:
            return "🟡"
        return "🔴"

    @staticmethod
    def _pct_text(pct: int | None) -> str:
        return "N/A" if pct is None else f"{pct}%"

    def _compute_build_status(self, build_name: str):
        """Pure aggregation over the persisted completion state each tab
        already reads: ``skills/<build>/completed_levels`` (Skills +
        Leveling, they share one set), ``paragon/<build>/completed_boards``
        and ``gear/<build>/owned_items``. Factored out of
        ``_refresh_build_status`` (Phase 7) so the Build Guide's status
        widget and the Dashboard's Current Build card compute the exact
        same 🟢/🟡/🔴 rows instead of two copies of this math.

        Returns ``(rows, footer_text, ready)`` - see
        ``LevelingCard.set_build_status`` for the shape of ``rows``."""

        milestones = self.leveling_manager.get_skills_data(build_name)["milestones"]
        completed_levels = self._load_completed_levels(build_name)
        skills_pct = self._pct(len(completed_levels), len(milestones))

        boards = self.leveling_manager.get_paragon_data(build_name).get("boards") or []
        completed_boards = self._load_completed_boards(build_name)
        paragon_pct = self._pct(len(completed_boards), len(boards))

        gear = self.leveling_manager.get_gear_data(build_name) or {}
        checkable_gear = (gear.get("key_items") or []) + (gear.get("key_aspects") or [])
        gear_names = {entry["name"] for entry in checkable_gear}
        owned = self._load_owned_items(build_name) & gear_names
        gear_pct = self._pct(len(owned), len(gear_names))
        missing_gear = len(gear_names) - len(owned)

        rows = [
            (self._status_emoji(skills_pct), "Skills", self._pct_text(skills_pct)),
            (self._status_emoji(skills_pct), "Leveling", self._pct_text(skills_pct)),
            (self._status_emoji(paragon_pct), "Paragon", self._pct_text(paragon_pct)),
            (self._status_emoji(gear_pct), "Gear", self._pct_text(gear_pct)),
        ]

        # Ready when every category with actual data is fully complete -
        # a category with no trackable data (N/A) can't block readiness.
        ready = (
            (skills_pct is None or skills_pct == 100)
            and (paragon_pct is None or paragon_pct == 100)
            and (gear_pct is None or gear_pct == 100)
        )

        if ready:
            footer_text = "BUILD READY ✓"
        elif gear_names:
            plural = "" if missing_gear == 1 else "S"
            footer_text = f"{missing_gear} ITEM{plural} MISSING" if missing_gear else ""
        else:
            footer_text = ""

        return rows, footer_text, ready

    def _refresh_build_status(self):
        """Recompute and redraw the Build Guide's Build Status summary
        for the current build, then keep the Dashboard's Current Build
        card in sync too - see ``_compute_build_status``."""

        build_name = self.leveling_manager.current_build_name

        if not build_name:
            return

        rows, footer_text, ready = self._compute_build_status(build_name)
        self.leveling_card.set_build_status(rows, footer_text, ready)

        self._refresh_dashboard_build_card()

    # ---------------------------------------------------------
    # DASHBOARD / CURRENT BUILD CARD (Phase 7)
    # ---------------------------------------------------------

    def _pending_milestones(self, build_name: str) -> list[tuple[int, dict]]:
        """``(index, milestone)`` pairs for ``build_name`` that aren't
        completed yet, in order - the single source of truth for "what's
        next", same data + completion state as the Leveling/Skills tabs
        (``get_skills_data``/``_load_completed_levels``). Shared by
        ``_next_action_text`` (Dashboard's Current Build card) and
        ``_compact_next_action`` (Phase 9's Compact Mode window) so both
        surfaces always agree on the next action. The index (not the
        milestone's ``level``) is what completion is keyed on - see
        ``on_mark_done``."""

        milestones = self.leveling_manager.get_skills_data(build_name)["milestones"]
        completed = self._load_completed_levels(build_name)

        return [(i, m) for i, m in enumerate(milestones) if i not in completed]

    def _next_action_text(self, build_name: str) -> str:
        """Pick the single simplest "next thing to do": the next
        not-yet-completed Leveling/Skills milestone for ``build_name``.
        Deliberately not a cross-category prioritizer over Paragon/Gear
        too - Dashboard 2.0 is meant to stay simple, not become a second
        Build Guide."""

        pending = self._pending_milestones(build_name)

        if pending:
            _index, m = pending[0]
            return f"Lvl {m['level']} — {m['skill']}"

        milestones = self.leveling_manager.get_skills_data(build_name)["milestones"]
        return "Build fully unlocked!" if milestones else "—"

    def _refresh_dashboard_build_card(self):
        """Push the current build/level/status/next-action onto the
        Dashboard's Current Build card. Called whenever anything that
        could move the needle changes: build/class switch, level input,
        or any checkbox/toggle in the Build Guide's four tabs (via
        ``_refresh_build_status``)."""

        build_name = self.leveling_manager.current_build_name

        if not build_name:
            self.dashboard.build_card.set_build("", 0, [], "")
            self._refresh_compact_window()
            return

        rows, _footer_text, _ready = self._compute_build_status(build_name)
        next_action = self._next_action_text(build_name)

        self.dashboard.build_card.set_build(
            build_name, self._current_level(), rows, next_action
        )

        # Everything that can move the Dashboard card's needle (build/
        # class/level/character switch, or any mark-done in the four
        # Build Guide tabs, all of which route through here already) also
        # moves Compact Mode's - so pushing it from this one spot is
        # enough to keep an already-open Compact window live-synced
        # without a second signal wiring.
        self._refresh_compact_window()

    # ---------------------------------------------------------
    # COMPACT MODE (Phase 9)
    #
    # A small always-on-top window (src/compact_window.py) for glancing
    # at while actually playing - PC or, per the user, a PS5 on a second
    # screen. It owns no state of its own: everything it shows comes from
    # the same LevelingManager/QSettings data the main window already
    # reads, and its Done button routes through the existing
    # ``on_mark_done`` so a mark made in Compact Mode is indistinguishable
    # from one made in the Build Guide.
    # ---------------------------------------------------------

    def _compact_next_action(self, build_name: str):
        """Like ``_next_action_text`` but also returns the milestone
        *after* the next one (for Compact Mode's "Next: ..." preview
        line) and the level number Done should mark, built on the same
        ``_pending_milestones`` list so Compact Mode and the Dashboard
        card can never disagree about what's next.

        Returns ``(current_text, preview_text, done_index)`` -
        ``done_index`` is ``None`` when there is nothing left to mark,
        otherwise the milestone's position in its build's list (what
        completion is actually keyed on - see ``on_mark_done``)."""

        pending = self._pending_milestones(build_name)

        if not pending:
            milestones = self.leveling_manager.get_skills_data(build_name)["milestones"]
            current_text = "Build fully unlocked!" if milestones else "—"
            return current_text, "", None

        current_index, current = pending[0]
        current_text = f"Lvl {current['level']} — {current['skill']}"

        if len(pending) > 1:
            _next_index, nxt = pending[1]
            preview_text = f"Lvl {nxt['level']} — {nxt['skill']}"
        else:
            preview_text = ""

        return current_text, preview_text, current_index

    def open_compact_mode(self):
        """Create (once) and show the Compact Mode window."""

        if self.compact_window is None:
            self.compact_window = CompactWindow()
            self.compact_window.done_clicked.connect(self.on_compact_done)
            self.compact_window.shown.connect(self._refresh_compact_window)
            self.compact_window.destroyed.connect(self._on_compact_window_destroyed)

        self._refresh_compact_window()
        self.compact_window.show()
        self.compact_window.raise_()
        self.compact_window.activateWindow()

    def _on_compact_window_destroyed(self):
        # Qt has already torn down the C++ object by the time this fires -
        # just drop our reference so open_compact_mode knows to build a
        # fresh one next time instead of touching a dead widget.
        self.compact_window = None

    def _refresh_compact_window(self):
        """Push the active character's build/level/next-action onto an
        open Compact window. Safe to call unconditionally (e.g. from
        ``_refresh_dashboard_build_card`` on every state change) - it's a
        no-op while Compact Mode isn't open."""

        if self.compact_window is None:
            return

        build_name = self.leveling_manager.current_build_name

        if not build_name:
            self._compact_done_level = None
            self.compact_window.set_content("", 0, "", "", False)
            return

        char_name = next(
            (c["name"] for c in self.characters if c["id"] == self.active_character_id),
            "",
        )
        title = f"{char_name} — {build_name}" if char_name else build_name

        current_text, preview_text, done_level = self._compact_next_action(build_name)
        self._compact_done_level = done_level

        self.compact_window.set_content(
            title, self._current_level(), current_text, preview_text, done_level is not None
        )

    def on_compact_done(self):
        """Compact window's Done button - routes through the exact same
        ``on_mark_done`` the Build Guide's own Done buttons use, so the
        main window's Skills/Leveling tabs and Build Status update
        immediately too, not just Compact Mode's own view."""

        if self._compact_done_level is None:
            return

        self.on_mark_done(self._compact_done_level)

    def on_class_changed(self, class_name: str):
        """Step-1 class selector changed: rebuild the step-2 build
        dropdown to only that class's builds, then load the first one."""

        builds = self.leveling_manager.list_builds_for_class(class_name)

        if not builds:
            return

        first_build_name = builds[0]["build_name"]

        self.leveling_card.set_builds_for_class(builds, first_build_name)
        self.on_build_changed(first_build_name)

    # ---------------------------------------------------------
    # UPCOMING EVENTS
    # ---------------------------------------------------------

    def load_upcoming_events(self):

        events = self.api.get_upcoming_events()

        self.dashboard.upcoming_card.set_events(events)

    # ---------------------------------------------------------
    # UPDATE TIMER
    # ---------------------------------------------------------

    def update_countdown(self):

        now = datetime.now(timezone.utc)

        # ---------- World Boss ----------

        if self.current_boss:

            start = datetime.fromisoformat(
                self.current_boss["startTime"].replace("Z", "+00:00")
            )

            seconds = int((start - now).total_seconds())

            if seconds <= 0:

                self.load_world_boss()
                self.load_upcoming_events()

            else:

                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                secs = seconds % 60

                self.dashboard.world_boss_card.set_timer(
                    f"{hours:02}:{minutes:02}:{secs:02}"
                )

                progress = int((1 - seconds / 12600) * 100)
                progress = max(0, min(progress, 100))

                self.dashboard.world_boss_card.set_progress(progress)

        # ---------- Legion ----------

        if self.current_legion:

            start = datetime.fromisoformat(
                self.current_legion["startTime"].replace("Z", "+00:00")
            )

            seconds = int((start - now).total_seconds())

            if seconds <= 0:

                self.load_legion()
                self.load_upcoming_events()

            else:

                minutes = seconds // 60
                secs = seconds % 60

                self.dashboard.legion_card.set_timer(
                    f"{minutes:02}:{secs:02}"
                )

                progress = int((1 - seconds / 1500) * 100)
                progress = max(0, min(progress, 100))

                self.dashboard.legion_card.set_progress(progress)

        # ---------- Helltide ----------

        if self.current_helltide:

            start = datetime.fromisoformat(
                self.current_helltide["startTime"].replace("Z", "+00:00")
            )

            seconds = int((start - now).total_seconds())

            if seconds <= 0:
                self.load_helltide()
                self.load_upcoming_events()
            else:
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                secs = seconds % 60
                self.dashboard.helltide_card.set_timer(f"{hours:02}:{minutes:02}:{secs:02}")
                progress = int((1 - seconds / 3600) * 100)
                progress = max(0, min(progress, 100))
                self.dashboard.helltide_card.set_progress(progress)

        # ---------- Season 15 ----------

        if self.season_15_start:

            seconds = int((self.season_15_start - now).total_seconds())

            if seconds <= 0:
                self.dashboard.season_card.set_timer("LIVE NOW!")
                self.dashboard.season_card.set_progress(100)
            else:
                days = seconds // 86400
                hours = (seconds % 86400) // 3600
                minutes = (seconds % 3600) // 60

                self.dashboard.season_card.set_timer(
                    f"{days}d {hours:02}h {minutes:02}m"
                )

                # Countdown starts 14 days before season start
                total_window = 14 * 86400
                progress = int((1 - seconds / total_window) * 100)
                progress = max(0, min(progress, 100))

                self.dashboard.season_card.set_progress(progress)

        # ---------- Upcoming ----------

        self.dashboard.upcoming_card.refresh()
