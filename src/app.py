import os
import subprocess
from datetime import datetime, timezone

import requests
from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QInputDialog,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    ComboBox,
    FluentIcon as FIF,
    FluentWindow,
    InfoBar,
    InfoBarPosition,
    NavigationItemPosition,
    PrimaryPushButton,
    StrongBodyLabel,
    SubtitleLabel,
    SwitchButton,
)

from src import theme
from src.api import DiabloAPI
from src.build_advisor_interface import BuildAdvisorCard, BuildAdvisorInterface
from src.character_interface import CharacterCard, CharacterInterface
from src.compact_window import CompactWindow
from src.dashboard import DashboardWidget
from src.gear_builder_interface import GearBuilderCard, GearBuilderInterface
from src.leveling_card import LevelingCard
from src.managers.leveling_manager import LevelingManager
from src.paragon_interface import RARITY_LABELS, ParagonCard, ParagonInterface
from src.quick_search import QuickSearchDialog


# Build-data update check (Update Center, scoped-down): the running app
# and its ``builds/*.json`` data are both just a git checkout of this
# same public repo, so "is my build data current" is answerable by
# comparing local HEAD against the branch tip on GitHub - no auth, no
# self-update, just a read-only informational check (see SettingsInterface).
GITHUB_REPO = "jens3105/Diablo4Companion"
GITHUB_BRANCH = "feature/dashboard-v2"
GITHUB_COMMIT_API_URL = (
    f"https://api.github.com/repos/{GITHUB_REPO}/commits/{GITHUB_BRANCH}"
)


def get_local_commit_sha() -> str | None:
    """Return the full SHA of the local checkout's current HEAD commit,
    or ``None`` if this isn't a git checkout (e.g. a packaged build) or
    ``git`` isn't available. Uses the same repo-root pattern as
    ``LevelingManager`` for locating ``builds/`` - ``src/app.py`` sits one
    level shallower, so one fewer ``dirname`` call."""

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


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

        layout.addSpacing(16)

        # -------------------------
        # Build data updates
        # -------------------------
        # Read-only check: compares the local checkout's HEAD against the
        # branch tip on GitHub. Deliberately does NOT pull/apply anything -
        # a running app rewriting its own git checkout is out of scope and
        # risky. See ``get_local_commit_sha`` / ``GITHUB_COMMIT_API_URL``.

        updates_title = StrongBodyLabel("Build Data Updates", self)
        layout.addWidget(updates_title)

        self._local_sha = get_local_commit_sha()
        local_short = self._local_sha[:7] if self._local_sha else "unknown"

        self.current_version_label = CaptionLabel(
            f"Current build data: {local_short}"
            if self._local_sha
            else "Current build data: unknown (not a git checkout)",
            self,
        )
        layout.addWidget(self.current_version_label)

        self.update_status_label = BodyLabel("", self)
        self.update_status_label.setWordWrap(True)
        self.update_status_label.hide()
        layout.addWidget(self.update_status_label)

        check_row = QHBoxLayout()
        check_row.setSpacing(10)

        self.check_updates_button = PrimaryPushButton("Check for Updates", self)
        self.check_updates_button.clicked.connect(self._on_check_updates_clicked)
        check_row.addWidget(self.check_updates_button)
        check_row.addStretch(1)

        layout.addLayout(check_row)

        layout.addStretch(1)

    def _on_theme_toggled(self, checked: bool):
        mode = theme.MODE_DARK if checked else theme.MODE_LIGHT
        self.settings.setValue("appearance/theme", mode)
        theme.set_appearance(mode, theme.current_preset())

    def _on_preset_changed(self, index: int):
        preset = self._preset_keys[index]
        self.settings.setValue("appearance/accent_preset", preset)
        theme.set_appearance(theme.current_mode(), preset)

    def _on_check_updates_clicked(self):

        self.check_updates_button.setEnabled(False)
        self.check_updates_button.setText("Checking...")
        self.update_status_label.setText("Checking GitHub for the latest build data...")
        self.update_status_label.show()
        # Force the "Checking..." state to actually paint before the
        # (blocking) network call below - same synchronous-call style
        # DiabloAPI.get_schedule uses, just with the UI given a chance to
        # repaint first since this runs off a click instead of a timer.
        QApplication.processEvents()

        try:
            response = requests.get(GITHUB_COMMIT_API_URL, timeout=8)
            response.raise_for_status()
            data = response.json()

            remote_sha = data.get("sha", "")
            commit_info = data.get("commit", {}) or {}
            author_info = commit_info.get("author", {}) or {}
            remote_date = author_info.get("date", "")
            remote_message = (commit_info.get("message") or "").strip().splitlines()[0] if commit_info.get("message") else ""

            if not remote_sha:
                raise ValueError("GitHub svarede uden en commit-sha")

            if self._local_sha and remote_sha == self._local_sha:
                self.update_status_label.setText("Build data up to date")
            else:
                date_str = remote_date.split("T")[0] if remote_date else "ukendt dato"
                detail = f" - {remote_message}" if remote_message else ""
                self.update_status_label.setText(
                    f"Newer build data available (updated {date_str}{detail}). "
                    f"Run 'git pull' in the app folder to update."
                )

        except (requests.RequestException, ValueError) as exc:
            print(f"Kunne ikke tjekke for build-data opdateringer: {exc}")
            self.update_status_label.setText(
                "Could not check for updates (network error) - try again later."
            )

        finally:
            self.check_updates_button.setEnabled(True)
            self.check_updates_button.setText("Check for Updates")


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

        # Character page (Phase - nav reorg): hosts the Equipment Planner
        # that used to be the Build Guide's 4th tab. It owns no selector
        # of its own - see src/character_interface.py's module docstring.
        self.character_card = CharacterCard()

        self.character_interface = CharacterInterface(self.character_card)
        self.character_interface.setObjectName("characterInterface")

        # Paragon page: dedicated Overview (board list + overall %) and
        # Board detail (grid visualization) view over a build's verified
        # paragon_boards - see src/paragon_interface.py's module
        # docstring. Same "owns no build selector of its own" pattern as
        # the Character page above.
        self.paragon_card = ParagonCard()

        self.paragon_interface = ParagonInterface(self.paragon_card)
        self.paragon_interface.setObjectName("paragonInterface")

        # Gear Builder page: a detail-first, one-card-per-slot read-out of
        # a build's verified_build.gear (real item name/slot/rarity/
        # aspect, honest "DATA UNAVAILABLE" for everything the Maxroll
        # source never decodes) - see src/gear_builder_interface.py's
        # module docstring. Same "owns no build selector" pattern, and
        # the exact same gear/<build>/owned_items tracking as the
        # Character page's silhouette planner - one shared model, two
        # read-outs.
        self.gear_builder_card = GearBuilderCard()

        self.gear_builder_interface = GearBuilderInterface(self.gear_builder_card)
        self.gear_builder_interface.setObjectName("gearBuilderInterface")

        # Build Advisor page: a bigger, standalone read-out of the exact
        # same Build Status + next-action + pending-actions data the
        # Dashboard's Current Build card and Compact Mode already use.
        self.advisor_card = BuildAdvisorCard()

        self.advisor_interface = BuildAdvisorInterface(self.advisor_card)
        self.advisor_interface.setObjectName("buildAdvisorInterface")

        self.settings_interface = SettingsInterface(self.settings)
        self.settings_interface.setObjectName("settingsInterface")

        self.addSubInterface(self.dashboard, FIF.HOME, "Dashboard")
        self.addSubInterface(self.builds_interface, FIF.GAME, "Build Guide")
        self.addSubInterface(self.character_interface, FIF.FINGERPRINT, "Character")
        self.addSubInterface(self.gear_builder_interface, FIF.SHOPPING_CART, "Gear Builder")
        self.addSubInterface(self.paragon_interface, FIF.TILES, "Paragon")
        self.addSubInterface(self.advisor_interface, FIF.ROBOT, "Build Advisor")
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

        # Dashboard card's and Build Advisor page's NEXT ACTION line jump
        # straight to the relevant page/tab when clicked (this phase) -
        # skill -> Build Guide's Skills tab, paragon -> its Paragon tab,
        # gear -> the Character page. See _navigate_to_next_action.
        self.dashboard.build_card.next_action_clicked.connect(
            self._navigate_to_next_action
        )
        self.advisor_card.next_action_clicked.connect(
            self._navigate_to_next_action
        )

        # Phase 11: Paragon page's node-detail "Have it" toggle.
        self.paragon_card.node_owned_changed.connect(self.on_paragon_node_toggled)

        # Phase 13: Dashboard's compact Paragon block jumps straight to
        # the Paragon page when clicked, same pattern as the whole-card
        # click above.
        self.dashboard.build_card.paragon_clicked.connect(
            lambda: self.switchTo(self.paragon_interface)
        )

        # Phase 9: Compact Mode - lazily created on first use, torn down
        # (set back to None) when the user closes it, so re-opening it
        # always starts from a clean, freshly-synced window.
        self.compact_window = None
        self._compact_action_kind = None
        self._compact_action_key = None
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
        self.character_card.gear_owned_changed.connect(self.on_gear_owned_changed)
        self.gear_builder_card.item_owned_changed.connect(self.on_gear_owned_changed)
        self.leveling_card.character_changed.connect(self.on_character_changed)
        self.leveling_card.add_character_requested.connect(self.on_add_character)
        self.leveling_card.rename_character_requested.connect(self.on_rename_character)
        self.leveling_card.favorite_toggle_requested.connect(self.on_favorite_toggled)

        # Settings page's dark/light + seasonal accent-preset picker fires
        # this whenever it changes theme.py's colors, so every already-
        # built widget with a hard-coded color can re-apply it live.
        theme.theme_changed.changed.connect(self._on_theme_changed)

        # Phase 25: Ctrl+K quick-search overlay - jump straight to any
        # nav page or switch build without hunting through menus.
        # ``QShortcut``'s default context (``Qt.WindowShortcut``) fires
        # from any page/child widget as long as this window is active,
        # so no per-page wiring is needed.
        self.quick_search_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self.quick_search_shortcut.activated.connect(self.open_quick_search)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_countdown)
        self.timer.start(1000)

        # Phase 16b: build-change notices. LevelingManager already diffed
        # the just-loaded builds/*.json against the last-seen snapshot (and
        # refreshed that snapshot, so this is a one-shot "tell the user"
        # step, not something to recompute). Surfaced as a dismissible
        # InfoBar on the Dashboard - the first page shown on launch, so it
        # gets noticed without a blocking dialog interrupting startup.
        # Deferred one tick so it appears once the window is actually
        # shown, rather than racing main.py's ``window.show()``.
        if self.leveling_manager.build_changes:
            QTimer.singleShot(300, self._show_build_change_notices)

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
            self.character_card,
            self.gear_builder_card,
            self.paragon_card,
            self.advisor_card,
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
    # Build-change notices (Phase 16b)
    # ---------------------------------------------------------

    def _show_build_change_notices(self):
        """Show one dismissible InfoBar per build whose data changed since
        the last run (see ``LevelingManager._compute_and_refresh_changes``).
        The snapshot was already refreshed at load time, so these changes
        won't be reported again on the next launch regardless of whether
        the user dismisses the InfoBar or lets it time out."""

        for entry in self.leveling_manager.build_changes:

            changes = entry["changes"]
            preview = "; ".join(changes[:3])

            if len(changes) > 3:
                preview += f" (+{len(changes) - 3} more)"

            InfoBar.info(
                title=f"{entry['build']} updated",
                content=preview,
                orient=Qt.Vertical,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=10000,
                parent=self,
            )

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
        self.leveling_card.set_favorite_state(self._is_build_favorite(default_build))
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

        self._record_recent_build(self.leveling_manager.current_build_name)
        self.leveling_card.set_favorite_state(
            self._is_build_favorite(self.leveling_manager.current_build_name)
        )

    # ---------------------------------------------------------
    # FAVORITES / RECENT BUILDS (Phase 26)
    #
    # Two thin, per-character QSettings lists ("keep this simple" per the
    # roadmap) - no new data, no new page. Favorites are player-curated
    # (toggled from the Build Guide header); recent is auto-tracked from
    # the one existing build-switch path (``on_build_changed`` above).
    # Both are surfaced as extra categories in the Ctrl+K quick search
    # (see ``_build_quick_search_items``) instead of a dedicated panel.
    # ---------------------------------------------------------

    RECENT_BUILDS_MAX = 5

    def _favorite_builds_key(self) -> str:
        return f"{self._char_prefix()}/favorite_builds"

    def _recent_builds_key(self) -> str:
        return f"{self._char_prefix()}/recent_builds"

    def _load_favorite_builds(self) -> list[str]:
        return self.settings.value(self._favorite_builds_key(), [], type=list)

    def _load_recent_builds(self) -> list[str]:
        return self.settings.value(self._recent_builds_key(), [], type=list)

    def _is_build_favorite(self, build_name: str) -> bool:
        return build_name in self._load_favorite_builds()

    def on_favorite_toggled(self):
        """Favorite button clicked - flip the *currently active* build's
        membership in this character's favorites list."""

        build_name = self.leveling_manager.current_build_name

        if not build_name:
            return

        favorites = self._load_favorite_builds()

        if build_name in favorites:
            favorites.remove(build_name)
        else:
            favorites.append(build_name)

        self.settings.setValue(self._favorite_builds_key(), favorites)
        self.leveling_card.set_favorite_state(build_name in favorites)

    def _record_recent_build(self, build_name: str):
        """Push ``build_name`` to the front of this character's recent-
        builds list, deduping any earlier occurrence and capping the
        list at ``RECENT_BUILDS_MAX``. Called from ``on_build_changed``
        only - the one place a build switch actually happens - so
        there's no second code path to keep in sync."""

        if not build_name:
            return

        recent = self._load_recent_builds()

        if build_name in recent:
            recent.remove(build_name)

        recent.insert(0, build_name)
        recent = recent[: self.RECENT_BUILDS_MAX]

        self.settings.setValue(self._recent_builds_key(), recent)

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
        #
        # Since verified-build data landed, this same key also holds a
        # build's completed *verified skill names* (``str``) when the
        # Skills tab is tracking ``verified_build.skill_allocation``
        # instead of ``milestones`` (see LevelingCard.set_skills) - the
        # Leveling tab keeps tracking milestone positions (``int``) in
        # this same set regardless. The two domains never collide (a
        # skill name is never a pure digit string), so one shared set
        # still works - see ``_load_completed_levels``.
        return f"{self._char_prefix()}/skills/{build_name}/completed_levels"

    def _load_completed_levels(self, build_name: str) -> set:
        """Return the completed-levels set for ``build_name``, preserving
        each entry's original kind: a milestone position comes back as
        ``int`` (Leveling tab, and the Skills tab fallback for builds
        with no verified data), a verified skill name comes back as
        ``str`` (Skills tab for builds with ``verified_build``)."""

        raw = self.settings.value(self._completed_levels_key(build_name), [], type=list)
        completed = set()

        for value in raw:
            text = str(value)
            if not text:
                continue
            try:
                completed.add(int(text))
            except ValueError:
                completed.add(text)

        return completed

    def _save_completed_levels(self, build_name: str, completed: set):

        self.settings.setValue(
            self._completed_levels_key(build_name), sorted(completed, key=str)
        )

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

    def on_mark_done(self, key):
        """``key`` is either a milestone's position in its build's
        milestone list (``int`` - see ``LevelingCard._render_milestone_
        checklist``; not a game level, since multiple milestones can
        share a level) or, for a build with verified skill data, a
        verified skill's name (``str`` - see ``LevelingCard._render_
        verified_skill_checklist``)."""

        build_name = self.leveling_manager.current_build_name

        if not build_name:
            return

        completed = self._load_completed_levels(build_name)
        completed.add(key)
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
        #
        # Since verified-build data landed, this key holds board *ids*
        # (``str``, e.g. "Paragon_Warlock_00") for builds where the
        # Paragon tab tracks ``verified_build.paragon_boards`` instead of
        # the older, often-empty ``paragon.boards`` (whose completion was
        # keyed by position - ``int``). See ``_load_completed_boards`` for
        # how the 2 builds that had real progress on the old int keys
        # (Blazing Scream Warlock, Blight Necromancer) get migrated onto
        # the new board-id keys instead of appearing reset.
        return f"{self._char_prefix()}/paragon/{build_name}/completed_boards"

    def _load_completed_boards(self, build_name: str) -> set:
        """Return the completed-boards set for ``build_name``, migrating
        any pre-verified-data progress (positional ``int`` indices into
        the old ``paragon.boards`` list) onto the new verified board-id
        (``str``) scheme where possible - see
        ``_migrate_legacy_board_progress``."""

        raw = self.settings.value(self._completed_boards_key(build_name), [], type=list)
        completed = set()

        for value in raw:
            text = str(value)
            if not text:
                continue
            try:
                completed.add(int(text))
            except ValueError:
                completed.add(text)

        migrated = self._migrate_legacy_board_progress(build_name, completed)

        if migrated != completed:
            self._save_completed_boards(build_name, migrated)

        return migrated

    def _migrate_legacy_board_progress(self, build_name: str, completed: set) -> set:
        """Translate old, pre-verified-data Paragon board progress
        (positional ``int`` index into the guide-prose-derived
        ``paragon.boards`` list) onto the new verified board-id (``str``)
        scheme, by matching board/glyph name across both lists.

        Only Blazing Scream Warlock and Blight Necromancer ever had a
        non-empty legacy ``paragon.boards`` list, and for both, the same
        5 boards appear in ``verified_build.paragon_boards`` too - just
        in a different order (confirmed by inspecting both lists), so a
        stored legacy index no longer points at the same board once the
        Paragon tab switches to tracking the verified list positionally.
        Matching by name keeps a player's real "Mark as Done" progress on
        those 2 builds pointing at the same board instead of silently
        landing on the wrong one or disappearing.

        No-op (returns ``completed`` unchanged) for every other build,
        which never had a populated legacy board list to lose progress
        from in the first place."""

        verified_build = self.leveling_manager.get_verified_build(build_name)
        verified_boards = (verified_build or {}).get("paragon_boards") or []
        legacy_boards = self.leveling_manager.get_paragon_data(build_name).get("boards") or []

        legacy_indices = {value for value in completed if isinstance(value, int)}

        if not verified_boards or not legacy_boards or not legacy_indices:
            return completed

        migrated = set(completed) - legacy_indices

        for idx in legacy_indices:
            if idx < 0 or idx >= len(legacy_boards):
                continue

            legacy_name = (legacy_boards[idx].get("name") or "").strip().lower()

            for i, verified_board in enumerate(verified_boards):
                if (verified_board.get("glyph") or "").strip().lower() == legacy_name:
                    # Fallback format must match LevelingCard._board_id.
                    migrated.add(verified_board.get("board") or f"verified_board_{i}")
                    break

        return migrated

    def _save_completed_boards(self, build_name: str, completed: set):

        self.settings.setValue(
            self._completed_boards_key(build_name), sorted(completed, key=str)
        )

    def _refresh_paragon(self):
        """Rebuild the Paragon tab's board checklist for the current
        build, combining its (level-independent) board/glyph data with
        the persisted set of completed boards."""

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

    def on_mark_board_done(self, key):
        """``key`` is either a legacy board's position in ``paragon.
        boards`` (``int`` - builds with no verified board data) or a
        verified board's stable id (``str`` - see ``LevelingCard.
        _board_id``)."""

        build_name = self.leveling_manager.current_build_name

        if not build_name:
            return

        completed = self._load_completed_boards(build_name)
        completed.add(key)
        self._save_completed_boards(build_name, completed)

        self._refresh_paragon()
        self._refresh_build_status()

    # ---------------------------------------------------------
    # PARAGON NODE TRACKING (Phase 11)
    #
    # Node-granular Expected-vs-Current, on top of the board-level
    # ``completed_boards`` boolean above. A toggle state (a node can be
    # un-checked if the player misclicked or respecced), like
    # ``owned_items`` below - not the one-way ``completed_boards``/
    # ``completed_levels`` sets. Keyed by ``"<board_id>:<node_index>"``
    # (``board_id`` is ``LevelingCard._board_id`` - the exact same stable
    # id ``completed_boards`` already uses - so a node key always points
    # at the same board even if a build's board order changes upstream).
    #
    # Only meaningful for the 25/26 builds with ``verified_build.
    # paragon_boards`` node data; Heartseeker Rogue (no verified_build)
    # never has anything in this set and keeps using the coarser
    # ``completed_boards`` boolean everywhere below - see
    # ``_compute_build_status`` and ``_pending_paragon_actions``.
    # ---------------------------------------------------------

    def _completed_paragon_nodes_key(self, build_name: str) -> str:
        return f"{self._char_prefix()}/paragon/{build_name}/completed_nodes"

    def _load_completed_paragon_nodes(self, build_name: str) -> set[str]:

        raw = self.settings.value(self._completed_paragon_nodes_key(build_name), [], type=list)
        return {str(v) for v in raw}

    def _save_completed_paragon_nodes(self, build_name: str, completed: set[str]):

        self.settings.setValue(self._completed_paragon_nodes_key(build_name), sorted(completed))

    @staticmethod
    def _paragon_node_key(board_id: str, node_index) -> str:
        return f"{board_id}:{node_index}"

    @staticmethod
    def _board_fully_taken(board: dict, board_id: str, completed_nodes: set[str]) -> bool:
        """Whether every expected node on ``board`` is in
        ``completed_nodes`` - the derived "is this board done" check that
        replaces the manual ``completed_boards`` checkbox for any build
        with real node data (see module-level comment above). Falls back
        to ``False`` for the (currently nonexistent, but not assumed-
        impossible) case of a verified board with an empty ``nodes``
        list, since "no expected nodes" isn't the same as "all of them
        taken"."""

        nodes = board.get("nodes") or []
        if not nodes:
            return False
        return all(
            MainWindow._paragon_node_key(board_id, n.get("index")) in completed_nodes
            for n in nodes
        )

    def on_paragon_node_toggled(self, node_key: str, taken: bool):
        """A node's "Have it" switch was flipped in the Paragon page's
        board detail popup (``ParagonCard.node_owned_changed``, wired in
        __init__)."""

        build_name = self.leveling_manager.current_build_name

        if not build_name:
            return

        completed_nodes = self._load_completed_paragon_nodes(build_name)

        if taken:
            completed_nodes.add(node_key)
        else:
            completed_nodes.discard(node_key)

        self._save_completed_paragon_nodes(build_name, completed_nodes)

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
        """Rebuild the Character page's equipment planner for the
        current build, combining its (level-independent) key items/
        aspects data with the persisted set of owned item/aspect names."""

        build_name = self.leveling_manager.current_build_name

        if not build_name:
            return

        gear = self.leveling_manager.get_gear_data(build_name)
        owned = self._load_owned_items(build_name)
        verified_build = self.leveling_manager.get_verified_build(build_name)

        self.character_card.set_gear(gear, owned, verified_build)
        self.gear_builder_card.set_gear(owned, verified_build)

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
    # Pure aggregation over the completion state the Build Guide's three
    # tabs and the Character page's gear planner already persist - no new
    # tracking, no new QSettings keys. Recomputed (cheaply - it's a
    # handful of len()/set operations) on every event that could move the
    # needle: build/class switch and any checkbox/toggle anywhere above.
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
        Leveling - they share one set, see ``_load_completed_levels``),
        ``paragon/<build>/completed_boards`` and ``gear/<build>/
        owned_items``. Factored out of ``_refresh_build_status``
        (Phase 7) so the Build Guide's status widget and the Dashboard's
        Current Build card compute the exact same 🟢/🟡/🔴 rows instead
        of two copies of this math.

        Skills and Leveling used to always show the identical percentage,
        since both tracked the same ``milestones`` list. Now that the
        Skills tab tracks ``verified_build.skill_allocation`` instead
        (for the 25 builds that have it), the two rows are computed
        separately: Leveling always counts milestone positions (``int``)
        completed out of ``len(milestones)``; Skills counts verified
        skill names (``str``) completed out of ``len(skill_allocation)``
        when present, else falls back to the same milestone math as
        Leveling. Paragon works the same way against verified board ids
        vs. legacy board positions.

        Returns ``(rows, footer_text, ready)`` - see
        ``LevelingCard.set_build_status`` for the shape of ``rows``."""

        milestones = self.leveling_manager.get_skills_data(build_name)["milestones"]
        completed_levels = self._load_completed_levels(build_name)

        leveling_done = sum(
            1 for v in completed_levels if isinstance(v, int) and 0 <= v < len(milestones)
        )
        leveling_pct = self._pct(leveling_done, len(milestones))

        verified_build = self.leveling_manager.get_verified_build(build_name)
        verified_skills = (verified_build or {}).get("skill_allocation") or []

        if verified_skills:
            skill_names = {entry["skill"] for entry in verified_skills}
            skills_done = sum(1 for v in completed_levels if isinstance(v, str) and v in skill_names)
            skills_pct = self._pct(skills_done, len(verified_skills))
        else:
            skills_pct = leveling_pct

        boards = self.leveling_manager.get_paragon_data(build_name).get("boards") or []
        completed_boards = self._load_completed_boards(build_name)
        verified_boards = (verified_build or {}).get("paragon_boards") or []

        if verified_boards:
            # Node-granular, not board-count-based (Phase 11) - the
            # denominator is every expected node across every board, the
            # numerator every one of those the player has toggled "Have
            # it" on. This is now the single source of truth for "is a
            # board done" for these 25/26 builds too (see
            # ``_board_fully_taken``) - the older ``completed_boards``
            # manual checkbox (still settable from the Build Guide's own
            # Paragon tab) is no longer read here, only kept for
            # Heartseeker Rogue's fallback below.
            completed_nodes = self._load_completed_paragon_nodes(build_name)
            total_nodes = sum(len(vb.get("nodes") or []) for vb in verified_boards)
            done_nodes = sum(
                1
                for i, vb in enumerate(verified_boards)
                for n in (vb.get("nodes") or [])
                if self._paragon_node_key(LevelingCard._board_id(vb, i), n.get("index"))
                in completed_nodes
            )
            paragon_pct = self._pct(done_nodes, total_nodes)
        else:
            paragon_done = sum(
                1 for v in completed_boards if isinstance(v, int) and 0 <= v < len(boards)
            )
            paragon_pct = self._pct(paragon_done, len(boards))

        verified_gear = (verified_build or {}).get("gear") or []

        if verified_gear:
            gear_names = {entry["item_name"] for entry in verified_gear}
        else:
            gear = self.leveling_manager.get_gear_data(build_name) or {}
            checkable_gear = (gear.get("key_items") or []) + (gear.get("key_aspects") or [])
            gear_names = {entry["name"] for entry in checkable_gear}

        owned = self._load_owned_items(build_name) & gear_names
        gear_pct = self._pct(len(owned), len(gear_names))
        missing_gear = len(gear_names) - len(owned)

        rows = [
            (self._status_emoji(skills_pct), "Skills", self._pct_text(skills_pct)),
            (self._status_emoji(leveling_pct), "Leveling", self._pct_text(leveling_pct)),
            (self._status_emoji(paragon_pct), "Paragon", self._pct_text(paragon_pct)),
            (self._status_emoji(gear_pct), "Gear", self._pct_text(gear_pct)),
        ]

        # Ready when every category with actual data is fully complete -
        # a category with no trackable data (N/A) can't block readiness.
        ready = (
            (skills_pct is None or skills_pct == 100)
            and (leveling_pct is None or leveling_pct == 100)
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

    # -----------------------------------------------------------
    # Build Advisor (Phase 10)
    #
    # Unifies the three tabs' independent "what's next" checks (Skills,
    # Paragon, Gear) into a single ordered action list, so the Dashboard's
    # Current Build card and Compact Mode always show/act on the exact
    # same "one concrete next action" instead of two different partial
    # views (previously Compact Mode and the Dashboard card both only
    # ever looked at Skills/Leveling milestones).
    #
    # Priority order - deliberate, not arbitrary:
    #   1. Leveling - the milestone-by-level path (when it's a distinct
    #                 checklist from Skills - see ``_pending_leveling_
    #                 actions``) is usually the earliest-blocking thing
    #                 in a real playthrough: at low level a build isn't
    #                 even at the point where its endgame Skills/Paragon/
    #                 Gear checklist is relevant yet, so surface this
    #                 first.
    #   2. Skills   - usually the actual blocker while leveling: a build
    #                 simply doesn't work yet without its core skill
    #                 allocation, so this is "what do I do right now".
    #   3. Paragon  - the next endgame power spike once skills are
    #                 sorted, and (unlike Gear) it's a one-way checklist
    #                 the player fully controls at their own pace, not
    #                 gated on a drop.
    #   4. Gear     - drop-gated ("equip Crown of Lucion") and the one
    #                 category that can regress (an item sold/replaced),
    #                 so it's the least "do this next" and most "keep an
    #                 eye out for this" of the three - last in priority.
    #
    # Each per-category helper below mirrors exactly what that tab
    # itself tracks (verified Maxroll Planner data when present, else
    # the older guide-prose-derived list) and the exact same persisted
    # completion state (``_load_completed_levels``/``_load_completed_
    # boards``/``_load_owned_items``) - no new tracking, no parallel
    # validation engine.
    # -----------------------------------------------------------

    def _pending_leveling_actions(self, build_name: str) -> list[tuple[str, str, object]]:
        """Every not-yet-completed Leveling milestone, in order, as
        ``(kind, text, key)`` - ``kind`` is always ``"leveling"`` here,
        ``key`` is the milestone's position, exactly what ``on_mark_done``
        already expects for a milestone key (see ``_pending_skill_
        actions``). Reuses the exact same ``milestones`` list and shared
        ``completed_levels`` set that ``_compute_build_status``'s
        "Leveling" row already sources its percentage from - no second
        way of computing Leveling completion.

        For a build with no verified skill data, the Skills tab falls
        back to tracking these same milestones against this same
        completed set (see ``_pending_skill_actions``), so this returns
        nothing in that case - otherwise every pending milestone would
        show up twice, once as a "Skills" action and once as a
        "Leveling" action. Only once a build has verified
        ``skill_allocation`` does Skills switch to tracking that instead,
        leaving the milestone checklist represented by no other category
        - that's the only case this needs to surface anything."""

        verified_build = self.leveling_manager.get_verified_build(build_name)
        verified_skills = (verified_build or {}).get("skill_allocation") or []

        if not verified_skills:
            return []

        completed = self._load_completed_levels(build_name)
        milestones = self.leveling_manager.get_skills_data(build_name)["milestones"]

        return [
            ("leveling", f"Add 1 point to {m['skill']} (Lvl {m['level']})", i)
            for i, m in enumerate(milestones)
            if i not in completed
        ]

    def _pending_skill_actions(self, build_name: str) -> list[tuple[str, str, object]]:
        """Every not-yet-completed Skills entry, in order, as ``(kind,
        text, key)`` - ``kind`` is always ``"skill"`` here (see
        ``_advisor_pending_actions``), ``key`` is whatever ``on_mark_done``
        expects (a verified skill name, or a milestone index for builds
        with no verified data). Mirrors exactly what ``LevelingCard.
        set_skills``/``_render_verified_skill_checklist`` tracks - verified
        ``skill_allocation`` when present, else the prose ``milestones``
        list - and the same shared ``completed_levels`` set."""

        completed = self._load_completed_levels(build_name)
        verified_build = self.leveling_manager.get_verified_build(build_name)
        verified_skills = (verified_build or {}).get("skill_allocation") or []

        if verified_skills:
            return [
                ("skill", f"Add 1 point to {entry['skill']}", entry["skill"])
                for entry in verified_skills
                if entry["skill"] not in completed
            ]

        milestones = self.leveling_manager.get_skills_data(build_name)["milestones"]

        return [
            ("skill", f"Add 1 point to {m['skill']} (Lvl {m['level']})", i)
            for i, m in enumerate(milestones)
            if i not in completed
        ]

    def _pending_paragon_actions(self, build_name: str) -> list[tuple[str, str, object]]:
        """Every not-yet-taken Paragon node, in order (board by board,
        then by node index within a board), as ``(kind, text, key)`` -
        ``kind`` is ``"paragon_node"``, ``key`` is ``"<board_id>:
        <node_index>"`` (exactly what ``on_paragon_node_toggled``
        expects). Mirrors ``_compute_build_status``'s node-granular
        Paragon math and the same shared ``completed_nodes`` set - see
        ``_board_fully_taken``.

        For Heartseeker Rogue (no ``verified_build``, so no node data to
        be granular about) this falls back to the older board-level
        ``"paragon"`` actions against the ``completed_boards`` boolean,
        exactly as before - the only build that still goes through that
        path.

        Glyph-level ("Level {glyph} to {glyph_level}") actions are
        deliberately NOT included here: there's no existing tracking
        dimension for "glyph level reached" anywhere in the app (only
        the board-level ``completed_boards`` boolean and, now, per-node
        ``completed_nodes`` - neither records a glyph's numeric level),
        and building a whole new tracking axis for just this one action
        type is out of scope for this pass."""

        verified_build = self.leveling_manager.get_verified_build(build_name)
        verified_boards = (verified_build or {}).get("paragon_boards") or []

        if verified_boards:
            completed_nodes = self._load_completed_paragon_nodes(build_name)
            actions = []

            for i, board in enumerate(verified_boards):
                board_id = LevelingCard._board_id(board, i)

                for node in board.get("nodes") or []:
                    node_key = self._paragon_node_key(board_id, node.get("index"))
                    if node_key in completed_nodes:
                        continue
                    name = node.get("name") or node.get("slug") or "?"
                    rarity = RARITY_LABELS.get(node.get("rarity", 0), "")
                    label = f"Take {rarity} Node: {name} (Board {i + 1})" if rarity else (
                        f"Take Node: {name} (Board {i + 1})"
                    )
                    actions.append(("paragon_node", label, node_key))

            return actions

        completed = self._load_completed_boards(build_name)
        boards = self.leveling_manager.get_paragon_data(build_name).get("boards") or []

        return [
            ("paragon", f"Unlock {board['name']} board", i)
            for i, board in enumerate(boards)
            if i not in completed
        ]

    def _pending_gear_actions(self, build_name: str) -> list[tuple[str, str, object]]:
        """Every not-yet-owned Gear entry, in order, as ``(kind, text,
        key)`` - ``key`` is the item/aspect name ``on_gear_owned_changed``
        expects. Mirrors ``CharacterCard.set_gear``/
        ``build_entries_from_verified_gear`` - verified ``gear`` when
        present, else the prose ``key_items``/``key_aspects`` lists - and
        the same shared ``owned_items`` set."""

        owned = self._load_owned_items(build_name)
        verified_build = self.leveling_manager.get_verified_build(build_name)
        verified_gear = (verified_build or {}).get("gear") or []

        if verified_gear:
            actions = []
            for item in verified_gear:
                name = item["item_name"]
                if name in owned:
                    continue
                actions.append(("gear", f"Equip {name} ({item.get('slot') or '?'})", name))
            return actions

        gear = self.leveling_manager.get_gear_data(build_name) or {}
        actions = []

        for item in gear.get("key_items") or []:
            name = item["name"]
            if name in owned:
                continue
            actions.append(("gear", f"Equip {name} ({item.get('slot') or '?'})", name))

        for item in gear.get("key_aspects") or []:
            name = item["name"]
            if name in owned:
                continue
            actions.append(("gear", f"Acquire {name} aspect", name))

        return actions

    def _advisor_pending_actions(self, build_name: str) -> list[tuple[str, str, object]]:
        """The full unified Build Advisor list for ``build_name``: every
        pending Leveling action, then every pending Skills action, then
        every pending Paragon action, then every pending Gear action (see
        the priority-order comment above) - each item ``(kind, text,
        key)``. The single source of truth for "what's next" shared by
        ``_advisor_next_action`` (Dashboard's Current Build card) and
        ``_compact_next_action`` (Compact Mode), so both surfaces always
        agree."""

        return (
            self._pending_leveling_actions(build_name)
            + self._pending_skill_actions(build_name)
            + self._pending_paragon_actions(build_name)
            + self._pending_gear_actions(build_name)
        )

    def _advisor_next_action(self, build_name: str) -> tuple[str | None, str]:
        """Pick the single concrete "next thing to do" across Leveling,
        Skills, Paragon and Gear for ``build_name`` - the Dashboard
        Current Build card's and the Build Advisor page's one-line
        summary. Never fabricates an action when nothing is left.

        Returns ``(kind, text)`` - ``kind`` is whichever pending-action
        helper produced the action (``"leveling"``/``"skill"``/
        ``"paragon"``/``"gear"``, already tagged on every tuple
        ``_advisor_pending_actions`` returns), or ``None`` when nothing
        is left. Lets click-to-navigate (``MainWindow._navigate_to_
        next_action``) jump to the right page/tab without any separate
        classification logic."""

        pending = self._advisor_pending_actions(build_name)

        if pending:
            kind, text, _key = pending[0]
            return kind, text

        return None, "Build complete!"

    def _refresh_dashboard_build_card(self):
        """Push the current build/level/status/next-action onto the
        Dashboard's Current Build card, the Character page's header, and
        the Build Advisor page. Called whenever anything that could move
        the needle changes: build/class switch, level input, or any
        checkbox/toggle in the Build Guide's three tabs or the Character
        page's gear planner (via ``_refresh_build_status``)."""

        build_name = self.leveling_manager.current_build_name
        char_name = next(
            (c["name"] for c in self.characters if c["id"] == self.active_character_id),
            "",
        )

        if not build_name:
            self.dashboard.build_card.set_build("", 0, [], "")
            self.dashboard.build_card.set_paragon_summary(None)
            self.character_card.set_header(char_name, "", 0)
            self.gear_builder_card.set_header(char_name, "", 0)
            self.paragon_card.set_paragon("", "", 0, None, set(), set(), None)
            self.advisor_card.set_advisor("", 0, [], "", False, "", None, {})
            self._refresh_compact_window()
            return

        level = self._current_level()
        rows, footer_text, ready = self._compute_build_status(build_name)
        next_kind, next_action = self._advisor_next_action(build_name)

        self.dashboard.build_card.set_build(build_name, level, rows, next_action, next_kind)
        self.dashboard.build_card.set_paragon_summary(
            self._paragon_dashboard_summary(build_name, rows[2])
        )
        self.character_card.set_header(char_name, build_name, level)
        self.gear_builder_card.set_header(char_name, build_name, level)
        # rows[2] is the "Paragon" row - see _compute_build_status - so
        # the Paragon page's overall % is the exact same figure, never a
        # second computation of it.
        self.paragon_card.set_paragon(
            char_name,
            build_name,
            level,
            self.leveling_manager.get_verified_build(build_name),
            self._load_completed_boards(build_name),
            self._load_completed_paragon_nodes(build_name),
            rows[2],
        )
        self.advisor_card.set_advisor(
            build_name,
            level,
            rows,
            footer_text,
            ready,
            next_action,
            next_kind,
            self._advisor_missing_summary(build_name),
        )

        # Everything that can move the Dashboard card's needle (build/
        # class/level/character switch, or any mark-done in the Build
        # Guide's tabs or the Character page, all of which route through
        # here already) also moves Compact Mode's, the Character header's,
        # the Paragon page's and the Build Advisor page's - so pushing it
        # from this one spot is enough to keep everything live-synced
        # without extra signal wiring.
        self._refresh_compact_window()

    def _paragon_dashboard_summary(
        self, build_name: str, paragon_status_row: tuple[str, str, str] | None
    ) -> tuple[str, str, str] | None:
        """Phase 13: the Dashboard's compact Paragon block - ``(pct_text,
        current_board_label, next_action_text)``, or ``None`` when this
        build has no verified board data to summarize (Heartseeker
        Rogue). Purely a display-formatting pass over data already
        computed elsewhere - ``paragon_status_row`` is ``_compute_build_
        status``'s "Paragon" row (same one shown everywhere else) and the
        next-action text reuses ``_pending_paragon_actions`` - no second
        Paragon calculation."""

        verified_build = self.leveling_manager.get_verified_build(build_name)
        verified_boards = (verified_build or {}).get("paragon_boards") or []

        if not verified_boards:
            return None

        completed_nodes = self._load_completed_paragon_nodes(build_name)

        current_board_label = "All boards complete"
        for i, board in enumerate(verified_boards):
            board_id = LevelingCard._board_id(board, i)
            if not self._board_fully_taken(board, board_id, completed_nodes):
                current_board_label = f"Board {i + 1}"
                break

        node_actions = [
            text for kind, text, _key in self._pending_paragon_actions(build_name)
            if kind == "paragon_node"
        ]
        next_text = node_actions[0] if node_actions else "All paragon nodes taken"
        pct_text = paragon_status_row[2] if paragon_status_row else "N/A"

        return pct_text, current_board_label, next_text

    def _advisor_missing_summary(
        self, build_name: str, cap: int = 5
    ) -> dict[str, tuple[list[str], int]]:
        """The Build Advisor page's "what's missing" data: for each of
        Skills/Paragon/Gear, the first ``cap`` pending-action texts (see
        ``_pending_skill_actions``/``_pending_paragon_actions``/
        ``_pending_gear_actions``) plus the true total pending count, so
        the page can show "(+N more)" instead of an unbounded wall of
        text - matching the roadmap's "low visual noise, scannable"
        principle. Pure formatting over the exact same helpers the
        unified next-action already uses - no new validation logic."""

        per_category = {
            "Skills": self._pending_skill_actions(build_name),
            "Paragon": self._pending_paragon_actions(build_name),
            "Gear": self._pending_gear_actions(build_name),
        }

        return {
            category: ([text for _kind, text, _key in actions[:cap]], len(actions))
            for category, actions in per_category.items()
        }

    def _navigate_to_next_action(self, kind: str):
        """Dashboard card's / Build Advisor page's NEXT ACTION line was
        clicked - jump to the page (and, for Leveling/Skills/Paragon, the
        exact Build Guide tab) that action lives on: ``"leveling"`` ->
        Build Guide's Leveling tab, ``"skill"`` -> its Skills tab,
        ``"paragon"`` -> its Paragon tab (Heartseeker Rogue's board-
        unlock fallback only), ``"paragon_node"`` -> the dedicated
        Paragon page's board detail view for that exact node's board
        (Phase 11/12), ``"gear"`` -> the Character page (the Equipment
        Planner has no per-item anchor to jump further into - landing on
        the page is the achievable minimum there). Uses the same
        ``switchTo`` pattern already wired for the Dashboard card's
        whole-card click."""

        if kind == "gear":
            self.switchTo(self.character_interface)
            return

        if kind == "paragon_node":
            self.switchTo(self.paragon_interface)

            build_name = self.leveling_manager.current_build_name
            pending = self._pending_paragon_actions(build_name) if build_name else []

            if pending:
                _kind, _text, node_key = pending[0]
                board_id = str(node_key).rsplit(":", 1)[0]
                self.paragon_card.select_board(board_id)
            return

        self.switchTo(self.builds_interface)

        if kind == "leveling":
            self.leveling_card.select_section(self.leveling_card.LEVELING_KEY)
        elif kind == "skill":
            self.leveling_card.select_section(self.leveling_card.SKILLS_KEY)
        elif kind == "paragon":
            self.leveling_card.select_section(self.leveling_card.PARAGON_KEY)

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
        """Like ``_advisor_next_action`` but also returns the action
        *after* the next one (for Compact Mode's "Next: ..." preview
        line) and how the Done button should mark the current one, built
        on the same ``_advisor_pending_actions`` list so Compact Mode and
        the Dashboard card can never disagree about what's next - across
        Leveling, Skills, Paragon AND Gear now.

        Returns ``(current_text, preview_text, kind, key)`` - ``kind`` is
        ``None`` when there is nothing left to mark, otherwise one of
        ``"leveling"``/``"skill"``/``"paragon"``/``"gear"`` telling
        ``on_compact_done`` which existing handler (``on_mark_done``/
        ``on_mark_board_done``/``on_gear_owned_changed``) to route the
        Done button through, with ``key`` as that handler's argument."""

        pending = self._advisor_pending_actions(build_name)

        if not pending:
            return "Build complete!", "", None, None

        kind, current_text, key = pending[0]
        preview_text = pending[1][1] if len(pending) > 1 else ""

        return current_text, preview_text, kind, key

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
            self._compact_action_kind = None
            self._compact_action_key = None
            self.compact_window.set_content("", 0, "", "", False)
            return

        char_name = next(
            (c["name"] for c in self.characters if c["id"] == self.active_character_id),
            "",
        )
        title = f"{char_name} — {build_name}" if char_name else build_name

        current_text, preview_text, kind, key = self._compact_next_action(build_name)
        self._compact_action_kind = kind
        self._compact_action_key = key

        self.compact_window.set_content(
            title, self._current_level(), current_text, preview_text, kind is not None
        )

    def on_compact_done(self):
        """Compact window's Done button - routes through whichever
        existing handler (``on_mark_done``/``on_mark_board_done``/
        ``on_gear_owned_changed``) owns the advisor's current action, so
        the main window's Leveling/Skills/Paragon/Gear tabs and Build
        Status update immediately too, not just Compact Mode's own view.
        Marking a Gear action "done" here means "equip it" - it flips the
        same one-way toggle a "Have it" switch in the Gear planner would.

        ``"leveling"`` routes through the exact same ``on_mark_done`` as
        ``"skill"`` - a Leveling action's key is a milestone position
        into the same shared ``completed_levels`` set (see
        ``_pending_leveling_actions``), so no separate handler is
        needed."""

        if self._compact_action_kind is None:
            return

        if self._compact_action_kind in ("skill", "leveling"):
            self.on_mark_done(self._compact_action_key)
        elif self._compact_action_kind == "paragon":
            self.on_mark_board_done(self._compact_action_key)
        elif self._compact_action_kind == "paragon_node":
            self.on_paragon_node_toggled(self._compact_action_key, True)
        elif self._compact_action_kind == "gear":
            self.on_gear_owned_changed(self._compact_action_key, True)

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
    # QUICK SEARCH (Phase 25 - Ctrl+K)
    #
    # A thin search-and-jump layer over data/navigation primitives that
    # already exist - no new fetching, no new pages. Every searchable
    # entry is built fresh each time the dialog opens (cheap: it's a
    # handful of list() calls over data already loaded in memory) so it
    # always reflects whichever build is currently active.
    # ---------------------------------------------------------

    def open_quick_search(self):

        dialog = QuickSearchDialog(self)
        dialog.set_items(self._build_quick_search_items())
        dialog.exec()

    def _select_build_from_search(self, build_name: str):
        """Switch the active build to ``build_name`` and land on the
        Build Guide page - the exact same class/build-selector state and
        ``on_build_changed`` handler the Build Guide's own selectors
        already use (``_apply_active_character`` populates the selectors
        the same way), so nothing here duplicates that switching logic."""

        class_name = self.leveling_manager.get_class_for_build(build_name)
        builds = self.leveling_manager.list_builds_for_class(class_name)

        self.leveling_card.set_classes(self.leveling_manager.list_classes(), class_name)
        self.leveling_card.set_builds_for_class(builds, build_name)
        self.on_build_changed(build_name)

        self.switchTo(self.builds_interface)

    def _jump_to_skill(self):

        self.switchTo(self.builds_interface)
        self.leveling_card.select_section(self.leveling_card.SKILLS_KEY)

    def _build_quick_search_items(self) -> list[dict]:
        """Flat, filterable list of ``{"label", "category", "action"}``
        entries: the 6 nav pages, every build across every class (so any
        build is one keystroke-search away from being switched to), and
        the ACTIVE build's skill/gear names (cheap - just the one
        already-loaded build, not all 25) so the player can jump
        straight to a specific skill or gear item they're looking for."""

        items = []

        # ---- Nav pages ----

        pages = [
            ("Dashboard", self.dashboard),
            ("Build Guide", self.builds_interface),
            ("Character", self.character_interface),
            ("Gear Builder", self.gear_builder_interface),
            ("Paragon", self.paragon_interface),
            ("Build Advisor", self.advisor_interface),
            ("Settings", self.settings_interface),
        ]
        for label, interface in pages:
            items.append(
                {"label": label, "category": "Page", "action": lambda i=interface: self.switchTo(i)}
            )

        # ---- Favorites / Recent (Phase 26) ----
        #
        # Stale entries (a favorited/recent build that no longer exists)
        # are skipped rather than pruned from QSettings here - cheap
        # per-open check, no extra write path.

        for build_name in self._load_favorite_builds():
            if not self.leveling_manager.get_class_for_build(build_name):
                continue
            items.append(
                {
                    "label": build_name,
                    "category": "Favorite",
                    "action": lambda b=build_name: self._select_build_from_search(b),
                }
            )

        for build_name in self._load_recent_builds():
            if not self.leveling_manager.get_class_for_build(build_name):
                continue
            items.append(
                {
                    "label": build_name,
                    "category": "Recent",
                    "action": lambda b=build_name: self._select_build_from_search(b),
                }
            )

        # ---- All builds, across all classes ----

        for build in self.leveling_manager.list_builds():
            build_name = build["build_name"]
            category = build.get("class_name", "") or "Build"
            items.append(
                {
                    "label": build_name,
                    "category": category,
                    "action": lambda b=build_name: self._select_build_from_search(b),
                }
            )

        # ---- Active build's skills + gear only (see docstring) ----

        active_build = self.leveling_manager.current_build_name

        if active_build:
            verified_build = self.leveling_manager.get_verified_build(active_build)
            verified_skills = (verified_build or {}).get("skill_allocation") or []

            if verified_skills:
                skill_names = [entry["skill"] for entry in verified_skills]
            else:
                milestones = self.leveling_manager.get_skills_data(active_build)["milestones"]
                seen = []
                for m in milestones:
                    skill = (m.get("skill") or "").strip()
                    if skill and skill not in seen:
                        seen.append(skill)
                skill_names = seen

            for name in skill_names:
                items.append(
                    {
                        "label": name,
                        "category": f"Skill - {active_build}",
                        "action": self._jump_to_skill,
                    }
                )

            verified_gear = (verified_build or {}).get("gear") or []

            if verified_gear:
                gear_names = [entry["item_name"] for entry in verified_gear]
            else:
                gear = self.leveling_manager.get_gear_data(active_build) or {}
                gear_names = [item["name"] for item in gear.get("key_items") or []]
                gear_names += [item["name"] for item in gear.get("key_aspects") or []]

            for name in gear_names:
                items.append(
                    {
                        "label": name,
                        "category": f"Gear - {active_build}",
                        "action": lambda: self.switchTo(self.character_interface),
                    }
                )

        return items

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
