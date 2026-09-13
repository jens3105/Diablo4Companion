from datetime import datetime, timezone

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    FluentIcon as FIF,
    FluentWindow,
    NavigationItemPosition,
    SubtitleLabel,
)

from src.api import DiabloAPI
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
    """Small about page. Replaces the old decorative 'Settings' entry in
    the plain QListWidget sidebar, which never actually did anything."""

    def __init__(self, parent=None):
        super().__init__(parent)

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

        layout.addStretch(1)


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

        # ---------------------------------------------------------
        # Pages / navigation
        # ---------------------------------------------------------

        self.dashboard = DashboardWidget()
        self.dashboard.setObjectName("dashboardInterface")

        self.leveling_card = LevelingCard()

        self.builds_interface = BuildsInterface(self.leveling_card)
        self.builds_interface.setObjectName("buildsInterface")

        self.settings_interface = SettingsInterface()
        self.settings_interface.setObjectName("settingsInterface")

        self.addSubInterface(self.dashboard, FIF.HOME, "Dashboard")
        self.addSubInterface(self.builds_interface, FIF.GAME, "Build Guide")
        self.addSubInterface(
            self.settings_interface,
            FIF.SETTING,
            "Settings",
            position=NavigationItemPosition.BOTTOM,
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

        default_build = self._restore_leveling_selection()
        default_class = self.leveling_manager.get_class_for_build(default_build)

        default_level = self.settings.value("leveling/level", 1, type=int)
        default_level = max(1, min(100, default_level))

        self.leveling_card.set_classes(
            self.leveling_manager.list_classes(), default_class
        )
        self.leveling_card.set_builds_for_class(
            self.leveling_manager.list_builds_for_class(default_class), default_build
        )
        self.leveling_card.set_level_value(default_level)
        # Show milestones for the restored (or default) build/level
        # straight away, without re-persisting what we just loaded.
        self.on_level_changed(default_level, persist=False)

        self.leveling_card.level_changed.connect(self.on_level_changed)
        self.leveling_card.build_changed.connect(self.on_build_changed)
        self.leveling_card.class_changed.connect(self.on_class_changed)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_countdown)
        self.timer.start(1000)

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
        """Look up the last-selected build from QSettings and make it the
        LevelingManager's current build, if it still exists. Falls back
        to LevelingManager's own baked-in default (unchanged) when
        nothing was saved yet or the saved build was removed."""

        saved_build = self.settings.value("leveling/build", "", type=str)

        if saved_build:
            self.leveling_manager.set_current_build(saved_build)

        return self.leveling_manager.current_build_name

    def on_level_changed(self, level: int, persist: bool = True):

        data = self.leveling_manager.get_progress(level)

        self.leveling_card.set_progress(data)

        if persist:
            self.settings.setValue("leveling/level", level)

    def on_build_changed(self, build_name: str):

        if not self.leveling_manager.set_current_build(build_name):
            return

        text = self.leveling_card.level_input.text().strip()
        level = int(text) if text.isdigit() else 1

        data = self.leveling_manager.get_progress(level)

        self.leveling_card.set_progress(data)

        self.settings.setValue("leveling/build", self.leveling_manager.current_build_name)
        self.settings.setValue(
            "leveling/class", self.leveling_manager.get_class_for_build(build_name)
        )

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
