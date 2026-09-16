import os
import shutil
import sys
import tempfile
import time
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

from src import build_data_updater
from src import theme
from src.api import DiabloAPI
from src import updater
from src.version import __version__
from src.build_advisor_interface import BuildAdvisorCard, BuildAdvisorInterface
from src.character_interface import CharacterCard, CharacterInterface
from src.compact_window import CompactWindow
from src.dashboard import DashboardWidget
from src.gear_builder_interface import GearBuilderCard, GearBuilderInterface
from src.gems_interface import GemsCard, GemsInterface
from src.leveling_card import LevelingCard
from src.managers.leveling_manager import LevelingManager
from src.paragon_interface import RARITY_LABELS, ParagonCard, ParagonInterface
from src.quick_search import QuickSearchDialog


# App update check (Windows Product Phase W5): GitHub Releases is the
# single, central release source for the packaged Windows product -
# deliberately NOT a git-checkout/HEAD-SHA comparison (that only ever
# worked for a dev source checkout, showed "Not a git checkout" for
# every real user running the installed .exe, and conflated "app
# version" with "build data freshness", which are two different
# things - build-data-specific update checking is its own later phase,
# W10, not this one). Read-only informational check only here (see
# SettingsInterface._on_check_updates_clicked) - no download/install,
# that's W7/W8.
GITHUB_REPO = "jens3105/Diablo4Companion"
GITHUB_RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _parse_semver(version_text: str) -> tuple[int, int, int] | None:
    """Parse a ``"1.2.3"``/``"v1.2.3"`` style string into a comparable
    ``(major, minor, patch)`` tuple, or ``None`` if it doesn't match
    that shape - never guessed/coerced, an unparseable release tag just
    can't be compared (see the caller's DATA UNAVAILABLE-style fallback
    message)."""

    text = version_text.strip()
    if text.lower().startswith("v"):
        text = text[1:]

    parts = text.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None

    return tuple(int(p) for p in parts)


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

    def __init__(self, settings: QSettings, leveling_manager: LevelingManager, parent=None):
        super().__init__(parent)

        self.settings = settings
        # Windows Product Phase W10: needed so "Update Build Data" can
        # call ``leveling_manager._load_builds()`` after a successful
        # download to pick up the new data immediately, without a
        # restart, and so the local Build Data version can be read from
        # the exact directory LevelingManager itself resolves (source
        # checkout vs. frozen Windows build - see that class's
        # ``sys.frozen`` branch).
        self.leveling_manager = leveling_manager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setAlignment(Qt.AlignTop)
        layout.setSpacing(12)

        title = SubtitleLabel("Diablo IV Companion", self)
        layout.addWidget(title)

        # Windows Product Phase W4: surface the one canonical version
        # (src/version.py) in the UI - no separate hardcoded copy here.
        version_label = CaptionLabel(f"Version {__version__}", self)
        layout.addWidget(version_label)

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
        # App updates (Windows Product Phase W5)
        # -------------------------
        # Read-only check against GitHub Releases - the current version
        # always comes from src/version.py (works identically from
        # source or a frozen Windows build, see that module's
        # docstring), never from git. Deliberately does NOT download/
        # install anything yet - that's W7/W8.

        updates_title = StrongBodyLabel("App Updates", self)
        layout.addWidget(updates_title)

        self.current_version_label = CaptionLabel(f"Current version: {__version__}", self)
        layout.addWidget(self.current_version_label)

        self.update_status_label = BodyLabel("", self)
        self.update_status_label.setWordWrap(True)
        self.update_status_label.hide()
        layout.addWidget(self.update_status_label)

        # Windows Product Phase W7: the confirmed newer-release payload
        # (the full GitHub Releases API object, not just its tag) once
        # _on_check_updates_clicked finds one - the target W8's actual
        # download/verify/install/restart pipeline will consume. ``None``
        # whenever there is nothing safe to update to (no check run yet,
        # up to date, check failed, or an unparseable/ambiguous release)
        # - "Update Now" is only ever enabled/visible when this is set,
        # and _on_update_now_clicked refuses to act if it somehow isn't.
        self._pending_update_release: dict | None = None

        check_row = QHBoxLayout()
        check_row.setSpacing(10)

        self.check_updates_button = PrimaryPushButton("Check for Updates", self)
        self.check_updates_button.clicked.connect(self._on_check_updates_clicked)
        check_row.addWidget(self.check_updates_button)

        self.update_now_button = PrimaryPushButton("Update Now", self)
        self.update_now_button.clicked.connect(self._on_update_now_clicked)
        self.update_now_button.hide()
        check_row.addWidget(self.update_now_button)

        check_row.addStretch(1)

        layout.addLayout(check_row)

        layout.addSpacing(16)

        # -------------------------
        # Build Data updates (Windows Product Phase W10)
        # -------------------------
        # A completely separate update flow from "App Updates" above -
        # this refreshes the Diablo 4 build JSON files (builds/*.json)
        # via a manifest.json committed to the repo and served raw from
        # GitHub, WITHOUT installing a new app version. Own widgets/
        # state/handlers throughout - never touches
        # self._pending_update_release or anything from the App Updates
        # section above.

        build_data_title = StrongBodyLabel("Build Data", self)
        layout.addWidget(build_data_title)

        local_manifest = build_data_updater.read_local_manifest(
            self.leveling_manager.builds_dir
        )
        local_version_text = (
            local_manifest["version"]
            if local_manifest
            else "unknown (no manifest found)"
        )
        self._local_build_data_version = local_manifest["version"] if local_manifest else None

        self.build_data_version_label = CaptionLabel(
            f"Build Data Version: {local_version_text}", self
        )
        layout.addWidget(self.build_data_version_label)

        self.build_data_status_label = BodyLabel("", self)
        self.build_data_status_label.setWordWrap(True)
        self.build_data_status_label.hide()
        layout.addWidget(self.build_data_status_label)

        # The confirmed newer remote manifest dict (version + file list)
        # once a check finds one - mirrors the shape of W7's
        # ``_pending_update_release`` but is its own, separate variable
        # for a separate concept. ``None`` whenever there is nothing
        # safe to update to.
        self._pending_build_data_manifest: dict | None = None

        build_data_row = QHBoxLayout()
        build_data_row.setSpacing(10)

        self.check_build_data_button = PrimaryPushButton(
            "Check for Build Data Updates", self
        )
        self.check_build_data_button.clicked.connect(
            self._on_check_build_data_updates_clicked
        )
        build_data_row.addWidget(self.check_build_data_button)

        self.update_build_data_button = PrimaryPushButton("Update Build Data", self)
        self.update_build_data_button.clicked.connect(
            self._on_update_build_data_clicked
        )
        self.update_build_data_button.hide()
        build_data_row.addWidget(self.update_build_data_button)

        build_data_row.addStretch(1)

        layout.addLayout(build_data_row)

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
        self.update_status_label.setText("Checking GitHub Releases for updates...")
        self.update_status_label.show()
        # Windows Product Phase W7: every check starts by clearing any
        # previously-confirmed update target and hiding "Update Now" -
        # re-armed below only if THIS check finds a genuinely newer
        # release. Never leaves a stale target visible/actionable from
        # an earlier click.
        self._pending_update_release = None
        self.update_now_button.hide()
        # Force the "Checking..." state to actually paint before the
        # (blocking) network call below - same synchronous-call style
        # DiabloAPI.get_schedule uses, just with the UI given a chance to
        # repaint first since this runs off a click instead of a timer.
        QApplication.processEvents()

        try:
            response = requests.get(GITHUB_RELEASES_API_URL, timeout=8)

            if response.status_code == 404:
                # No GitHub Release has been published yet (true today -
                # release automation is a later phase, W2/W3/W4 only ever
                # produced CI build artifacts, not a Release). Not a
                # network error, not a bug - an honest, expected state.
                self.update_status_label.setText(
                    "No published releases found yet."
                )
                return

            response.raise_for_status()
            data = response.json()

            remote_tag = data.get("tag_name", "")
            if not remote_tag:
                raise ValueError("GitHub Release havde ingen tag_name")

            remote_version = _parse_semver(remote_tag)
            local_version = _parse_semver(__version__)

            if remote_version is None or local_version is None:
                # Can't safely compare - never guess which is newer, and
                # never offer "Update Now" for an unconfirmed target.
                self.update_status_label.setText(
                    f"Latest release: {remote_tag} (current: {__version__}) - "
                    f"could not compare versions automatically."
                )
            elif remote_version > local_version:
                release_name = (data.get("name") or remote_tag).strip()
                self.update_status_label.setText(
                    f"A newer version is available: {release_name} "
                    f"(currently on {__version__})."
                )
                # W7: this is the ONLY branch that ever arms "Update Now" -
                # a confirmed newer release, nothing else.
                self._pending_update_release = data
                self.update_now_button.show()
            else:
                self.update_status_label.setText(f"Up to date (version {__version__}).")

        except (requests.RequestException, ValueError) as exc:
            print(f"Kunne ikke tjekke for opdateringer: {exc}")
            self.update_status_label.setText(
                "Could not check for updates (network error) - try again later."
            )

        finally:
            self.check_updates_button.setEnabled(True)
            self.check_updates_button.setText("Check for Updates")

    def _on_update_now_clicked(self):
        """Windows Product Phase W8: the real download -> verify ->
        install -> restart pipeline, built on top of W7's confirmed
        ``_pending_update_release`` target.

        Refuses to act (defensively, even though the button is only
        ever shown/enabled right after ``_on_check_updates_clicked``
        confirms a genuinely newer release) unless
        ``_pending_update_release`` is a real, confirmed target - never
        starts an update on a guess. Every step reuses
        ``self.update_status_label`` for progress/status, matching this
        page's existing style.

        No custom restart-helper here by design: the Inno Setup
        installer's own ``[Run]`` "launch after install" section
        (installer/diablo4companion.iss) already relaunches the new
        version once the user finishes the wizard - this method's job
        ends at getting a verified installer running and this (old)
        process out of its way.
        """

        release = self._pending_update_release
        if not release:
            return

        release_name = (release.get("name") or release.get("tag_name") or "").strip()

        self.update_now_button.setEnabled(False)
        self.update_status_label.setText(f"Preparing to update to {release_name}...")
        self.update_status_label.show()
        QApplication.processEvents()

        installer_asset = updater.find_installer_asset(release)
        if installer_asset is None:
            self.update_status_label.setText(
                "Update asset not found - please download manually from "
                "GitHub Releases."
            )
            self.update_now_button.setEnabled(True)
            return

        temp_dir = tempfile.mkdtemp(prefix="d4c_update_")
        installer_path = os.path.join(temp_dir, updater.INSTALLER_ASSET_NAME)

        def _on_progress(downloaded: int, total: int | None):
            if total:
                percent = int(downloaded * 100 / total)
                self.update_status_label.setText(
                    f"Downloading update... {percent}% "
                    f"({downloaded // 1024} KB / {total // 1024} KB)"
                )
            else:
                self.update_status_label.setText(
                    f"Downloading update... {downloaded // 1024} KB"
                )
            QApplication.processEvents()

        self.update_status_label.setText("Downloading update...")
        QApplication.processEvents()

        try:
            updater.download_asset(installer_asset, installer_path, _on_progress)
        except (requests.RequestException, OSError, RuntimeError) as exc:
            print(f"Kunne ikke downloade opdateringen: {exc}")
            self.update_status_label.setText(
                "Could not download the update (network error) - try "
                "again later."
            )
            self._cleanup_update_temp_dir(temp_dir)
            self.update_now_button.setEnabled(True)
            return

        # The checksum sidecar is optional - a failed/missing fetch of
        # IT specifically degrades to size-only verification below,
        # rather than aborting the whole update. Only a bad *installer*
        # download/verification aborts.
        checksum_asset_data: bytes | None = None
        checksum_asset = updater.find_checksum_asset(release)
        if checksum_asset is not None:
            try:
                checksum_response = requests.get(
                    checksum_asset["browser_download_url"], timeout=15
                )
                checksum_response.raise_for_status()
                checksum_asset_data = checksum_response.content
            except requests.RequestException as exc:
                print(f"Kunne ikke hente checksum, falder tilbage til size-only: {exc}")
                checksum_asset_data = None

        self.update_status_label.setText("Verifying downloaded update...")
        QApplication.processEvents()

        is_valid, reason = updater.verify_download(
            installer_path, installer_asset, checksum_asset_data
        )
        if not is_valid:
            self.update_status_label.setText(f"Update verification failed: {reason}")
            self._cleanup_update_temp_dir(temp_dir)
            self.update_now_button.setEnabled(True)
            return

        # Windows Product Phase W9 -- Safe Rollback: back up the CURRENT
        # install before ever handing control to the installer, so a
        # newly-installed version that turns out to be broken has a
        # known-good copy to manually recover from (see
        # src/updater.py's backup_install_dir/restore_backup docstrings
        # and PROJECT_STATUS.md's W9 entry for the full design/limits).
        # Only meaningful when actually running as a frozen Windows
        # build - there is no "installation" to back up when running
        # from source, so this step is skipped entirely in that case
        # (same sys.frozen check src/managers/leveling_manager.py's
        # frozen branch already uses).
        if getattr(sys, "frozen", False):
            install_dir = os.path.dirname(sys.executable)
            backup_root = os.path.join(
                os.path.dirname(install_dir), "Diablo4Companion_backup"
            )

            target_version_tuple = _parse_semver(release.get("tag_name", ""))
            target_version = (
                "%d.%d.%d" % target_version_tuple
                if target_version_tuple is not None
                else (release.get("tag_name") or "").strip()
            )

            self.update_status_label.setText(
                "Creating a safety backup before updating..."
            )
            QApplication.processEvents()

            try:
                backup_path = updater.backup_install_dir(
                    install_dir, backup_root, target_version
                )
            except Exception as exc:  # noqa: BLE001 - disk full, permission
                # error, anything: per this phase's explicit safety rule,
                # a failed backup must cancel the whole update rather than
                # risk the current, working installation.
                print(f"Kunne ikke oprette sikkerhedskopi før opdatering: {exc}")
                self.update_status_label.setText(
                    "Could not create a safety backup before updating - "
                    "update cancelled to avoid risking your current "
                    "installation."
                )
                self._cleanup_update_temp_dir(temp_dir)
                self.update_now_button.setEnabled(True)
                return

            self.settings.setValue("update/pending_backup_path", backup_path)
            self.settings.setValue("update/pending_previous_version", __version__)
            self.settings.setValue("update/pending_target_version", target_version)

        self.update_status_label.setText("Starting installer...")
        QApplication.processEvents()

        try:
            installer_process = updater.launch_installer(installer_path)
        except OSError as exc:
            print(f"Kunne ikke starte installeren: {exc}")
            self.update_status_label.setText(
                "Could not start the installer - please download it "
                "manually from GitHub Releases."
            )
            self.update_now_button.setEnabled(True)
            return

        # Production Validation finding: Popen succeeding only means
        # Windows accepted the request to start a process, not that it's
        # still alive moments later - a just-downloaded, unsigned .exe
        # can be killed almost immediately by antivirus/security
        # software on a real machine. Blindly quitting this app right
        # after Popen (the previous behavior) would then look exactly
        # like "clicking Update Now does nothing": the old app closes,
        # no installer window ever appears, nothing to restart from. A
        # brief liveness check here turns that silent failure into a
        # clear, actionable message instead.
        time.sleep(1.5)
        QApplication.processEvents()

        if installer_process.poll() is not None:
            print(
                f"Installeren afsluttede uventet med det samme "
                f"(exit code {installer_process.returncode})"
            )
            self.update_status_label.setText(
                "The installer closed immediately after starting - it may "
                "have been blocked by antivirus/security software. Please "
                "download and run Diablo4Companion-Setup.exe manually from "
                "GitHub Releases."
            )
            self.update_now_button.setEnabled(True)
            return

        self.update_status_label.setText(
            "Installer started. Restarting Diablo 4 Companion..."
        )
        # Give the status text a moment to actually render before the
        # app quits, and let the just-launched installer get going
        # before this process's own locked files (the running exe/DLLs)
        # would otherwise block it.
        QTimer.singleShot(1000, QApplication.quit)

    @staticmethod
    def _cleanup_update_temp_dir(temp_dir: str) -> None:
        """Best-effort cleanup of a partial/failed update download's
        temp directory - cleanup failing itself must never crash the
        app on top of the original download/verification failure."""

        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except OSError:
            pass

    def _on_check_build_data_updates_clicked(self):
        """Windows Product Phase W10: check the remote
        ``builds/manifest.json`` (served raw from GitHub) against the
        local one, entirely independent of the App Updates section
        above - never touches ``_pending_update_release``.

        Comparison is a plain string comparison of the ``version``
        field. Safe here specifically because this phase's version
        format is ``YYYY-MM-DD`` (zero-padded, fixed-width) - that
        format sorts identically under lexicographic string comparison
        and chronological date comparison, so no date-parsing library
        is needed. This would NOT be safe for an unpadded or
        variable-width format.
        """

        self.check_build_data_button.setEnabled(False)
        self.check_build_data_button.setText("Checking...")
        self.build_data_status_label.setText(
            "Checking for Build Data updates..."
        )
        self.build_data_status_label.show()
        self._pending_build_data_manifest = None
        self.update_build_data_button.hide()
        QApplication.processEvents()

        try:
            remote_manifest = build_data_updater.fetch_remote_manifest()
        except (requests.RequestException, ValueError) as exc:
            print(f"Kunne ikke tjekke for build data-opdateringer: {exc}")
            self.build_data_status_label.setText(
                "Could not check for Build Data updates (network error) - "
                "try again later."
            )
            self.check_build_data_button.setEnabled(True)
            self.check_build_data_button.setText("Check for Build Data Updates")
            return

        remote_version = remote_manifest["version"]
        local_version = self._local_build_data_version

        if local_version is not None and remote_version <= local_version:
            self.build_data_status_label.setText(
                f"Build data is up to date (version {local_version})."
            )
        else:
            local_display = local_version or "unknown"
            self.build_data_status_label.setText(
                f"New build data available: {remote_version} "
                f"(currently {local_display})."
            )
            self._pending_build_data_manifest = remote_manifest
            self.update_build_data_button.show()

        self.check_build_data_button.setEnabled(True)
        self.check_build_data_button.setText("Check for Build Data Updates")

    def _on_update_build_data_clicked(self):
        """Windows Product Phase W10: download+verify+atomically install
        the confirmed newer ``_pending_build_data_manifest`` target, then
        reload ``LevelingManager`` in place so the new data is picked up
        immediately without an app restart.

        Refuses to act unless a confirmed target exists (defensive,
        even though the button is only shown right after a check
        confirms one). On any exception, ``download_build_data`` has
        guaranteed nothing on disk was partially replaced - the old
        build files and the already-loaded ``LevelingManager`` state are
        both still exactly what they were before this call, so no
        rollback step is needed here (unlike App Updates' installer
        flow, this never touches a running installation)."""

        manifest = self._pending_build_data_manifest
        if not manifest:
            return

        total_files = len(manifest.get("files") or [])

        self.update_build_data_button.setEnabled(False)
        self.build_data_status_label.setText(
            f"Downloading build data... 0/{total_files}"
        )
        self.build_data_status_label.show()
        QApplication.processEvents()

        def _on_progress(files_done: int, files_total: int):
            self.build_data_status_label.setText(
                f"Downloading build data... {files_done}/{files_total}"
            )
            QApplication.processEvents()

        try:
            build_data_updater.download_build_data(
                manifest, self.leveling_manager.builds_dir, _on_progress
            )
        except (requests.RequestException, OSError, RuntimeError, ValueError) as exc:
            print(f"Kunne ikke opdatere build data: {exc}")
            self.build_data_status_label.setText(
                f"Build Data update failed: {exc}"
            )
            self.update_build_data_button.setEnabled(True)
            return

        # Success: reload in place (no restart needed) and reflect the
        # new version in the UI.
        self.leveling_manager._load_builds()

        new_version = manifest["version"]
        self._local_build_data_version = new_version
        self.build_data_version_label.setText(f"Build Data Version: {new_version}")
        self.build_data_status_label.setText(
            f"Build data updated successfully to version {new_version}."
        )
        self._pending_build_data_manifest = None
        self.update_build_data_button.hide()
        self.update_build_data_button.setEnabled(True)


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

        # Windows Product Phase W9 -- Safe Rollback: startup half of the
        # backup-before-install + self-check-on-next-startup mechanism
        # (see _on_update_now_clicked's backup step in SettingsInterface
        # and PROJECT_STATUS.md's W9 entry for the full design). Must
        # run early, and stays a single cheap QSettings read with zero
        # file I/O in the overwhelmingly common "no pending update"
        # case - see _check_pending_update's docstring.
        self._startup_update_notice = None
        self._check_pending_update()

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

        # Gems page: per-socket tracking of each equipped slot's real
        # expected gem/rune (see src/gems_interface.py's module
        # docstring) - built on the same verified_build.gear entries the
        # Gear Builder page above just started reading, now additionally
        # carrying each item's real ``sockets`` list (see
        # scripts/maxroll_data_decoder.py's decode_gear). Same "owns no
        # build selector" pattern, and shares its ``gear/<build>/
        # socketed_gems`` toggle set with the Gear Builder page's own
        # per-item socket summary - one tracked state, two read-outs.
        self.gems_card = GemsCard()

        self.gems_interface = GemsInterface(self.gems_card)
        self.gems_interface.setObjectName("gemsInterface")

        # Build Advisor page: a bigger, standalone read-out of the exact
        # same Build Status + next-action + pending-actions data the
        # Dashboard's Current Build card and Compact Mode already use.
        self.advisor_card = BuildAdvisorCard()

        self.advisor_interface = BuildAdvisorInterface(self.advisor_card)
        self.advisor_interface.setObjectName("buildAdvisorInterface")

        self.settings_interface = SettingsInterface(self.settings, self.leveling_manager)
        self.settings_interface.setObjectName("settingsInterface")

        self.addSubInterface(self.dashboard, FIF.HOME, "Dashboard")
        self.addSubInterface(self.builds_interface, FIF.GAME, "Build Guide")
        self.addSubInterface(self.character_interface, FIF.FINGERPRINT, "Character")
        self.addSubInterface(self.gear_builder_interface, FIF.SHOPPING_CART, "Gear Builder")
        self.addSubInterface(self.gems_interface, FIF.CERTIFICATE, "Gems")
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

        # Dashboard data bugfix: fetch the schedule ONCE and hand the
        # exact same snapshot to all four consumers below, instead of
        # each independently calling self.api.get_schedule() (four
        # separate HTTP requests within milliseconds of each other).
        # Beyond being wasteful, that could let one card's fetch hit
        # helltides.com's live API while another's fetch - moments
        # later - gets blocked by Cloudflare's bot-challenge and falls
        # back to the locally-estimated schedule, showing genuinely
        # inconsistent (different source, different clock) data across
        # cards in the same refresh. See PROJECT_STATUS.md's Dashboard
        # Data bugfix entry.
        schedule = self.api.get_schedule()

        self.load_world_boss(schedule)
        self.load_legion(schedule)
        self.load_helltide(schedule)
        self.load_upcoming_events(schedule)
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
        self.gear_builder_card.tempering_toggled.connect(self.on_tempering_toggled)
        self.gems_card.socket_owned_changed.connect(self.on_gem_socket_toggled)
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

        # Windows Product Phase W9 -- Safe Rollback: the deferred half of
        # the startup check set up by _check_pending_update above - same
        # "wait for the window to actually be shown" reasoning as the
        # build-change notices just above.
        if self._startup_update_notice:
            QTimer.singleShot(300, self._show_pending_update_notice)

    # ---------------------------------------------------------
    # Windows Product Phase W9 -- Safe Rollback (startup check)
    # ---------------------------------------------------------

    def _check_pending_update(self):
        """Check whether an update was in flight when this process last
        ran (``update/pending_backup_path`` set by
        ``SettingsInterface._on_update_now_clicked``'s backup step) and,
        if so, resolve it - either confirming the update completed
        (cleans up the now-unneeded backup) or noting honestly that it
        didn't (leaves the backup in place for possible manual
        recovery). See PROJECT_STATUS.md's W9 entry for the full design
        and its one documented limitation.

        Deliberately front-loaded to a single QSettings read: the
        overwhelmingly common case (no update was ever started, or the
        previous one already resolved on an earlier launch) must stay
        free of any file I/O. Only sets ``self._startup_update_notice``
        for the caller to show later (deferred, see __init__) - never
        shows UI itself, so this can safely run before any page exists.
        """

        backup_path = self.settings.value("update/pending_backup_path", "", type=str)
        if not backup_path:
            return

        target_version = self.settings.value(
            "update/pending_target_version", "", type=str
        )

        self.settings.remove("update/pending_backup_path")
        self.settings.remove("update/pending_previous_version")
        self.settings.remove("update/pending_target_version")

        if __version__ == target_version:
            # First successful launch of the newly-installed version -
            # the backup has done its job and is no longer needed.
            backup_root = os.path.dirname(backup_path)
            try:
                updater.cleanup_backup(backup_path, backup_root)
            except OSError as exc:
                print(
                    f"Kunne ikke rydde op i backup efter vellykket "
                    f"opdatering: {exc}"
                )
            self._startup_update_notice = (
                "Update complete",
                f"Updated to version {target_version}.",
            )
        else:
            # NOT a "something is broken" state: this running app is
            # demonstrably fine, it's just still the old version (most
            # likely pending_previous_version) - the installer wizard
            # was probably cancelled, or failed silently. Nothing is
            # restored here: there is nothing to restore FROM, since
            # we're already successfully running the pre-update
            # install. The backup folder is deliberately left in place
            # (not auto-deleted) in case a future manual recovery or
            # retry could still use it.
            self._startup_update_notice = (
                "Update did not complete",
                f"A previous update to version {target_version} didn't "
                f"complete - you're still on version {__version__}.",
            )

    def _show_pending_update_notice(self):
        """Deferred display half of ``_check_pending_update`` - same
        dismissible-InfoBar style as ``_show_build_change_notices``."""

        if not self._startup_update_notice:
            return

        title, content = self._startup_update_notice
        InfoBar.info(
            title=title,
            content=content,
            orient=Qt.Vertical,
            isClosable=True,
            position=InfoBarPosition.TOP_RIGHT,
            duration=10000,
            parent=self,
        )

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
            self.gems_card,
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

    def load_world_boss(self, schedule=None):

        self.current_boss = self.api.get_next_world_boss(schedule)

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

    def load_legion(self, schedule=None):

        self.current_legion = self.api.get_next_legion(schedule)

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

    def load_helltide(self, schedule=None):

        self.current_helltide = self.api.get_next_helltide(schedule)

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
        aspects data with the persisted set of owned item/aspect names.
        Also pushes the same ``verified_build``/socketed-gems state onto
        the Gems page (see ``_refresh_gems``) - both pages move together
        since they read the exact same data, one call site is enough."""

        build_name = self.leveling_manager.current_build_name

        if not build_name:
            return

        gear = self.leveling_manager.get_gear_data(build_name)
        owned = self._load_owned_items(build_name)
        verified_build = self.leveling_manager.get_verified_build(build_name)
        socketed = self._load_socketed_gems(build_name)
        tempered = self._load_tempered_items(build_name)

        self.character_card.set_gear(gear, owned, verified_build)
        self.gear_builder_card.set_gear(owned, verified_build, socketed, tempered)
        self._refresh_gems(verified_build, socketed)

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
    # BUILD-GUIDE / GEMS (Gems System phase)
    #
    # A finer-grained toggle set than ``owned_items`` above: which
    # specific EXPECTED sockets (one entry per equipped item's real
    # verified_build.gear[].sockets[] slot - see scripts/
    # maxroll_data_decoder.py's decode_gear) the player has confirmed
    # are actually socketed on their real character. Its own QSettings
    # key, separate from ``owned_items`` for the same reason
    # ``completed_paragon_nodes`` is separate from ``completed_boards``:
    # this is a toggle (can go backwards - a gem swapped out), keyed
    # per-socket, not per-item.
    #
    # Shared verbatim by the Gems page (src/gems_interface.py) and the
    # Gear Builder page's per-item "Sockets/Gems" summary row (src/
    # gear_builder_interface.py) - one tracked state, two read-outs,
    # exactly like Gear's owned_items is shared by the Character page
    # and the Gear Builder page.
    # ---------------------------------------------------------

    def _socketed_gems_key(self, build_name: str) -> str:
        return f"{self._char_prefix()}/gear/{build_name}/socketed_gems"

    def _load_socketed_gems(self, build_name: str) -> set[str]:

        raw = self.settings.value(self._socketed_gems_key(build_name), [], type=list)
        return {str(v) for v in raw}

    def _save_socketed_gems(self, build_name: str, socketed: set[str]):

        self.settings.setValue(self._socketed_gems_key(build_name), sorted(socketed))

    @staticmethod
    def _gem_socket_key(slot_label: str, socket_index: int) -> str:
        return f"{slot_label}:{socket_index}"

    def _refresh_gems(self, verified_build: dict | None = None, socketed: set[str] | None = None):
        """Push the current build's socket data onto the Gems page.
        Called from ``_refresh_gear`` (every trigger that can move
        gear's needle also moves this) - accepts already-looked-up
        ``verified_build``/``socketed`` purely so that caller doesn't
        have to fetch them twice; falls back to loading them itself so
        this method stays usable on its own too."""

        build_name = self.leveling_manager.current_build_name

        if not build_name:
            return

        if verified_build is None:
            verified_build = self.leveling_manager.get_verified_build(build_name)
        if socketed is None:
            socketed = self._load_socketed_gems(build_name)

        self.gems_card.set_gems(verified_build, socketed)

    def on_gem_socket_toggled(self, key: str, confirmed: bool):
        """A socket's "Have it" switch was flipped - either on the Gems
        page itself, or (in principle - see ``gear_builder_interface``'s
        module docstring, today that row is read-only text) anywhere
        else reading the same store. Mirrors ``on_gear_owned_changed``'s
        shape exactly."""

        build_name = self.leveling_manager.current_build_name

        if not build_name:
            return

        socketed = self._load_socketed_gems(build_name)

        if confirmed:
            socketed.add(key)
        else:
            socketed.discard(key)

        self._save_socketed_gems(build_name, socketed)

        self._refresh_gear()
        self._refresh_build_status()

    # ---------------------------------------------------------
    # BUILD-GUIDE / TEMPERING (Build Validation phase)
    #
    # Mirrors ``socketed_gems`` immediately above, exactly: a toggle set
    # of EXPECTED tempered-affix entries (one entry per equipped item's
    # real ``verified_build.gear[].tempering[]`` entry - usually length
    # 1, but the schema is a list, so this is keyed per-entry, not
    # per-item) the player has confirmed they've actually applied on
    # their real character. Its own QSettings key for the same reason
    # ``socketed_gems`` has its own: a toggle (can go backwards - a
    # temper re-rolled), not a monotonic "completed" set.
    #
    # Tempering previously had zero player-facing tracking at all (see
    # ``gear_builder_interface.py``'s module docstring) - it was
    # display-only text. This is the one genuinely new tracking
    # dimension the Build Validation phase adds.
    # ---------------------------------------------------------

    def _tempered_items_key(self, build_name: str) -> str:
        return f"{self._char_prefix()}/gear/{build_name}/tempered_items"

    def _load_tempered_items(self, build_name: str) -> set[str]:

        raw = self.settings.value(self._tempered_items_key(build_name), [], type=list)
        return {str(v) for v in raw}

    def _save_tempered_items(self, build_name: str, tempered: set[str]):

        self.settings.setValue(self._tempered_items_key(build_name), sorted(tempered))

    @staticmethod
    def _tempering_key(slot_label: str, temper_index: int) -> str:
        return f"{slot_label}:{temper_index}"

    def on_tempering_toggled(self, key: str, confirmed: bool):
        """A tempered-affix's "Have it" switch was flipped on the Gear
        Builder page's Tempering row - mirrors ``on_gem_socket_toggled``
        exactly."""

        build_name = self.leveling_manager.current_build_name

        if not build_name:
            return

        tempered = self._load_tempered_items(build_name)

        if confirmed:
            tempered.add(key)
        else:
            tempered.discard(key)

        self._save_tempered_items(build_name, tempered)

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

    def _category_percents(self, build_name: str) -> dict[str, int | None]:
        """The raw percent-or-``None`` (``None`` = no trackable data for
        this build/category, an N/A state, not a 0%/red one - see
        ``_pct``) for every Build Status category: Skills, Leveling,
        Paragon, Gear, Gems, Tempering. Computed exactly once here and
        shared by both ``_compute_build_status`` (renders the 🟢/🟡/🔴
        rows) and ``_build_validation`` (the Build Advisor-facing
        aggregation structure) - one calculation, two read-outs, so
        they can never disagree.

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

        Gems/Tempering (Build Validation phase) follow the same
        expected-vs-toggled-count pattern already used for Gear: the
        denominator is every real socket/tempering entry across
        ``verified_build.gear[]`` (0 when the build has no verified gear
        at all, e.g. Heartseeker Rogue - correctly ``None``/N-A, never
        0%/red), the numerator every one of those the player has
        toggled "Have it" on via ``socketed_gems``/``tempered_items``."""

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

        # Gems: only sockets that resolved to a real gem/rune name count
        # as trackable (matches ``_pending_gem_actions`` exactly) - an
        # "unknown" socket (see that method's docstring) is neither
        # done nor pending, it's just not counted at all.
        total_gem_sockets = sum(
            1
            for item in verified_gear
            for socket in (item.get("sockets") or [])
            if socket.get("kind") in ("gem", "rune") and socket.get("name")
        )
        socketed = self._load_socketed_gems(build_name)
        done_gem_sockets = sum(
            1
            for item in verified_gear
            for idx, socket in enumerate(item.get("sockets") or [])
            if socket.get("kind") in ("gem", "rune")
            and socket.get("name")
            and self._gem_socket_key(item.get("slot", "?"), idx) in socketed
        )
        gems_pct = self._pct(done_gem_sockets, total_gem_sockets)

        total_temper_slots = sum(len(item.get("tempering") or []) for item in verified_gear)
        tempered = self._load_tempered_items(build_name)
        done_temper_slots = sum(
            1
            for item in verified_gear
            for idx, _t in enumerate(item.get("tempering") or [])
            if self._tempering_key(item.get("slot", "?"), idx) in tempered
        )
        tempering_pct = self._pct(done_temper_slots, total_temper_slots)

        return {
            "Skills": skills_pct,
            "Leveling": leveling_pct,
            "Paragon": paragon_pct,
            "Gear": gear_pct,
            "Gems": gems_pct,
            "Tempering": tempering_pct,
        }

    def _compute_build_status(self, build_name: str):
        """Pure aggregation over the persisted completion state each tab
        already reads: ``skills/<build>/completed_levels`` (Skills +
        Leveling - they share one set, see ``_load_completed_levels``),
        ``paragon/<build>/completed_boards``/``completed_nodes``,
        ``gear/<build>/owned_items``, ``gear/<build>/socketed_gems`` and
        ``gear/<build>/tempered_items``. Factored out of
        ``_refresh_build_status`` (Phase 7) so the Build Guide's status
        widget and the Dashboard's Current Build card compute the exact
        same 🟢/🟡/🔴 rows instead of two copies of this math. The
        actual per-category percent math lives in ``_category_percents``
        (shared with ``_build_validation``) - this method only turns
        those numbers into display rows + the ready/footer verdict.

        Returns ``(rows, footer_text, ready)`` - see
        ``LevelingCard.set_build_status`` for the shape of ``rows``."""

        pcts = self._category_percents(build_name)
        skills_pct = pcts["Skills"]
        leveling_pct = pcts["Leveling"]
        paragon_pct = pcts["Paragon"]
        gear_pct = pcts["Gear"]
        gems_pct = pcts["Gems"]
        tempering_pct = pcts["Tempering"]

        # Only needed for the footer's "N items missing" count below -
        # not a second completion decision, ``gear_pct`` above already
        # is one.
        verified_build = self.leveling_manager.get_verified_build(build_name)
        verified_gear = (verified_build or {}).get("gear") or []
        if verified_gear:
            gear_names = {entry["item_name"] for entry in verified_gear}
        else:
            gear = self.leveling_manager.get_gear_data(build_name) or {}
            checkable_gear = (gear.get("key_items") or []) + (gear.get("key_aspects") or [])
            gear_names = {entry["name"] for entry in checkable_gear}
        owned = self._load_owned_items(build_name) & gear_names
        missing_gear = len(gear_names) - len(owned)

        rows = [
            (self._status_emoji(skills_pct), "Skills", self._pct_text(skills_pct)),
            (self._status_emoji(leveling_pct), "Leveling", self._pct_text(leveling_pct)),
            (self._status_emoji(paragon_pct), "Paragon", self._pct_text(paragon_pct)),
            (self._status_emoji(gear_pct), "Gear", self._pct_text(gear_pct)),
            (self._status_emoji(gems_pct), "Gems", self._pct_text(gems_pct)),
            (self._status_emoji(tempering_pct), "Tempering", self._pct_text(tempering_pct)),
        ]

        # Ready when every category with actual data is fully complete -
        # a category with no trackable data (N/A) can't block readiness.
        ready = (
            (skills_pct is None or skills_pct == 100)
            and (leveling_pct is None or leveling_pct == 100)
            and (paragon_pct is None or paragon_pct == 100)
            and (gear_pct is None or gear_pct == 100)
            and (gems_pct is None or gems_pct == 100)
            and (tempering_pct is None or tempering_pct == 100)
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

    # Build Advisor phase: one-line "why is this next" reasoning shown
    # next to the NEXT ACTION line, keyed by the action's ``kind`` -
    # reuses the exact reasoning documented in the priority-order comment
    # above verbatim, not new phrasing. Gems/Tempering weren't part of
    # that original 4-category comment (they were appended later, in the
    # Build Validation phase, as the two lowest-priority layers) so their
    # wording instead comes from ``_pending_gem_actions``'/``_pending_
    # tempering_actions``'s own docstrings.
    _ADVISOR_REASONS = {
        "leveling": "Leveling — usually the earliest-blocking thing in a real playthrough",
        "skill": "Skills — usually the actual blocker while leveling",
        "paragon": "Paragon — the next endgame power spike once skills are sorted",
        "paragon_node": "Paragon — the next endgame power spike once skills are sorted",
        "gear": "Gear — drop-gated, so it's last in priority",
        "gem": "Gems — matters even less than owning the item it lives in",
        "tempering": "Tempering — matters even less than a socketed gem",
    }

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

    def _pending_gem_actions(self, build_name: str) -> list[tuple[str, str, object]]:
        """Every not-yet-confirmed expected socket content, in order
        (item by item, then socket by socket), as ``(kind, text, key)`` -
        ``kind`` is ``"gem"``, ``key`` is ``"<slot_label>:<socket_index>"``
        (exactly what ``on_gem_socket_toggled`` expects). Mirrors
        ``_pending_paragon_actions``'s style - this is the finest-
        grained, lowest-priority layer (see ``_advisor_pending_actions``'s
        ordering comment - appended after Gear, since a socketed gem
        matters even less than owning the item it lives in).

        Sockets whose content couldn't be resolved to a real gem/rune
        name at all (``kind == "unknown"`` - see ``decode_gear``'s
        docstring; today only Season 15's Soul Splinter boss-material
        slugs, which this decoder's game-data dictionary has no entries
        for) never become an action - there's nothing honest to tell the
        player to do about a socket whose expected content this app
        can't identify."""

        verified_build = self.leveling_manager.get_verified_build(build_name)
        verified_gear = (verified_build or {}).get("gear") or []

        if not verified_gear:
            return []

        socketed = self._load_socketed_gems(build_name)
        actions = []

        for item in verified_gear:
            slot = item.get("slot", "?")
            for idx, socket in enumerate(item.get("sockets") or []):
                if socket.get("kind") not in ("gem", "rune") or not socket.get("name"):
                    continue
                key = self._gem_socket_key(slot, idx)
                if key in socketed:
                    continue
                kind_label = "Gem" if socket.get("kind") == "gem" else "Rune"
                actions.append(("gem", f"Socket {socket['name']} ({kind_label}) in {slot}", key))

        return actions

    def _pending_tempering_actions(self, build_name: str) -> list[tuple[str, str, object]]:
        """Every not-yet-confirmed expected tempered affix, in order
        (item by item, then tempering-entry by entry - usually just one
        per item, but the schema is a list), as ``(kind, text, key)`` -
        ``kind`` is ``"tempering"``, ``key`` is
        ``"<slot_label>:<temper_index>"`` (exactly what
        ``on_tempering_toggled`` expects). Mirrors ``_pending_gem_
        actions``'s style exactly - this is the finest-grained, lowest-
        priority layer of all (see ``_advisor_pending_actions``'s
        ordering comment - appended after Gems, since a confirmed
        tempered affix matters even less than a socketed gem)."""

        verified_build = self.leveling_manager.get_verified_build(build_name)
        verified_gear = (verified_build or {}).get("gear") or []

        if not verified_gear:
            return []

        tempered = self._load_tempered_items(build_name)
        actions = []

        for item in verified_gear:
            slot = item.get("slot", "?")
            for idx, temper in enumerate(item.get("tempering") or []):
                key = self._tempering_key(slot, idx)
                if key in tempered:
                    continue
                recipe = temper.get("recipe_name") or "?"
                group = temper.get("group")
                label = f"{recipe} ({group})" if group else recipe
                actions.append(("tempering", f"Apply {label} tempering to {slot}", key))

        return actions

    # Priority order Build Advisor's unified list walks the categories in -
    # Leveling first (see the priority-order comment above), then the 5
    # categories ``_build_validation`` names, in its documented order.
    _ADVISOR_CATEGORY_ORDER = ("Leveling", "Skills", "Paragon", "Gear", "Gems", "Tempering")

    def _advisor_pending_actions(self, build_name: str) -> list[tuple[str, str, object]]:
        """The full unified Build Advisor list for ``build_name``: every
        pending Leveling action, then every pending Skills action, then
        every pending Paragon action, then every pending Gear action,
        then every pending Gem-socket action, then every pending
        Tempering action (see the priority-order comment above) - each
        item ``(kind, text, key)``. The single source of truth for
        "what's next" shared by ``_advisor_next_action`` (Dashboard's
        Current Build card) and ``_compact_next_action`` (Compact Mode),
        so both surfaces always agree.

        Build Validation phase: sourced entirely from ``_build_validation``
        (which includes a "Leveling" category alongside its 5 named ones
        purely for this consumer - see its docstring) instead of calling
        each ``_pending_*_actions`` helper a second time here - there is
        now exactly one place (``_build_validation``) that walks that raw
        data."""

        categories = self._build_validation(build_name)["categories"]

        return [
            (action["kind"], action["text"], action["key"])
            for category in self._ADVISOR_CATEGORY_ORDER
            for action in categories[category]["actions"]
        ]

    def _advisor_next_action(self, build_name: str) -> tuple[str | None, str]:
        """Pick the single concrete "next thing to do" across Leveling,
        Skills, Paragon and Gear for ``build_name`` - the Dashboard
        Current Build card's and the Build Advisor page's one-line
        summary. Never fabricates an action when nothing is left.

        Returns ``(kind, text)`` - ``kind`` is whichever pending-action
        helper produced the action (``"leveling"``/``"skill"``/
        ``"paragon"``/``"gear"``/``"gem"``, already tagged on every tuple
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
            self.gems_card.set_header(char_name, "", 0)
            self.paragon_card.set_paragon("", "", 0, None, set(), set(), None)
            self.advisor_card.set_advisor("", 0, [], "", False, "", None, {}, "")
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
        self.gems_card.set_header(char_name, build_name, level)
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
            self._ADVISOR_REASONS.get(next_kind, ""),
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
        next-action text reuses ``_build_validation``'s Paragon actions -
        no second Paragon calculation."""

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
            action["text"]
            for action in self._build_validation(build_name)["categories"]["Paragon"]["actions"]
            if action["kind"] == "paragon_node"
        ]
        next_text = node_actions[0] if node_actions else "All paragon nodes taken"
        pct_text = paragon_status_row[2] if paragon_status_row else "N/A"

        return pct_text, current_board_label, next_text

    def _advisor_missing_summary(
        self, build_name: str, cap: int = 5
    ) -> dict[str, tuple[list[str], int]]:
        """The Build Advisor page's "what's missing" data: for each of
        Skills/Paragon/Gear/Gems/Tempering, the first ``cap`` pending-
        action texts plus the true total pending count, so the page can
        show "(+N more)" instead of an unbounded wall of text - matching
        the roadmap's "low visual noise, scannable" principle.

        Build Validation phase: reads ``_build_validation``'s per-category
        ``differences`` (Leveling excluded, exactly as before this phase -
        see ``_build_validation``'s docstring) instead of calling each
        ``_pending_*_actions`` helper directly - pure formatting, no new
        validation logic."""

        categories = self._build_validation(build_name)["categories"]

        return {
            category: (
                categories[category]["differences"][:cap],
                len(categories[category]["differences"]),
            )
            for category in ("Skills", "Paragon", "Gear", "Gems", "Tempering")
        }

    def _build_validation(self, build_name: str) -> dict:
        """Build Validation phase (extended in the Build Advisor phase):
        one clean aggregation structure over Leveling/Skills/Paragon/
        Gear/Gems/Tempering that is now the SINGLE source of truth both
        for Build Status's percentages and for Build Advisor's "what's
        next"/"what's missing" - every other method that used to compute
        pending actions independently (``_advisor_pending_actions``,
        ``_advisor_missing_summary``, ``_paragon_dashboard_summary``,
        ``_navigate_to_next_action``) now reads from this instead -

        ``{"overall_percent": int | None, "categories": {name: {
        "percent": int | None, "status": str, "differences": [str,...],
        "actions": [{"kind": str, "text": str, "key": object}, ...]
        }}}``.

        ``differences`` is the flat display-text list this structure
        originally shipped with (kept for any plain-text consumer);
        ``actions`` is the Build Advisor phase's addition - the exact
        same entries, but as full ``(kind, text, key)`` info, since
        navigating to / marking-done a specific item (``_navigate_to_
        next_action``, Compact Mode's Done button) needs more than
        display text. Both are the same list in the same order, just
        reshaped - still purely a reshape of ``_category_percents`` (the
        exact same numbers ``_compute_build_status`` renders as its
        🟢/🟡/🔴 rows) and each ``_pending_*_actions`` helper's already-
        computed ``(kind, text, key)`` tuples. Introduces no second way
        of deciding what's done.

        ``status`` per category is one of:
          - ``"unavailable"`` - no verified data to compare against at
            all (``percent is None`` - e.g. every category for
            Heartseeker Rogue, which has no ``verified_build``, or Gems/
            Tempering for a build/item with zero sockets/tempered
            affixes to expect).
          - ``"correct"`` - 100% of this category's expected entries are
            toggled "Have it".
          - ``"partial"`` - some, but not all.
          - ``"missing"`` - 0% (real data exists, none of it confirmed).

        ``"different"`` is a deliberately UNREACHABLE status value that
        exists only so a future real data source could report it - see
        ARCHITECTURE.md's documented limitation, mirrored from
        ``gear_planner.SlotStatus.INCORRECT`` and the Gems page's
        scaffolded-but-unreachable "Wrong gem" state: every category
        tracked here is a player self-reported "Have it" toggle (Skills/
        Paragon nodes/Gear items/Gems/Tempering all work this way), which
        can only ever be confirmed or not-yet-confirmed. There is no
        character-state import anywhere in this app, so nothing can ever
        detect the player has the *wrong* thing equipped/socketed/
        tempered vs. simply not-yet-confirmed - this method never
        produces ``"different"`` for that reason, on purpose, not by
        omission.

        Leveling is now included in ``categories`` (Build Advisor phase),
        purely so ``_advisor_pending_actions`` has exactly one place to
        read every category - including Leveling - from. It is still
        deliberately excluded from ``overall_percent``, exactly as
        before this phase: for a build with no verified
        ``skill_allocation`` it is literally the same checklist as
        Skills (see ``_category_percents``), so averaging both in would
        double-count one real checklist into the overall average.
        ``_advisor_missing_summary`` (the "what's missing" list) also
        keeps ignoring Leveling, matching its pre-existing category set."""

        percents = self._category_percents(build_name)

        actions_by_category = {
            "Leveling": self._pending_leveling_actions(build_name),
            "Skills": self._pending_skill_actions(build_name),
            "Paragon": self._pending_paragon_actions(build_name),
            "Gear": self._pending_gear_actions(build_name),
            "Gems": self._pending_gem_actions(build_name),
            "Tempering": self._pending_tempering_actions(build_name),
        }

        categories = {}

        for category, actions in actions_by_category.items():
            pct = percents[category]

            if pct is None:
                status = "unavailable"
            elif pct == 100:
                status = "correct"
            elif pct == 0:
                status = "missing"
            else:
                status = "partial"

            categories[category] = {
                "percent": pct,
                "status": status,
                "differences": [text for _kind, text, _key in actions],
                "actions": [
                    {"kind": kind, "text": text, "key": key} for kind, text, key in actions
                ],
            }

        # overall_percent is averaged over the original 5 Build Validation
        # categories only - Leveling is deliberately excluded here (see
        # docstring above) even though it's now present in ``categories``.
        overall_keys = ("Skills", "Paragon", "Gear", "Gems", "Tempering")
        real_percents = [
            categories[k]["percent"] for k in overall_keys if categories[k]["percent"] is not None
        ]
        overall_percent = round(sum(real_percents) / len(real_percents)) if real_percents else None

        return {"overall_percent": overall_percent, "categories": categories}

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
        the page is the achievable minimum there), ``"gem"`` -> the
        dedicated Gems page (same "landing on the page is enough" as
        gear - no per-socket anchor exists there either), ``"tempering"``
        -> the Gear Builder page (the only place a tempered affix's
        toggle lives - same "landing on the page is enough" reasoning).
        Uses the same ``switchTo`` pattern already wired for the
        Dashboard card's whole-card click."""

        if kind == "gear":
            self.switchTo(self.character_interface)
            return

        if kind == "gem":
            self.switchTo(self.gems_interface)
            return

        if kind == "tempering":
            self.switchTo(self.gear_builder_interface)
            return

        if kind == "paragon_node":
            self.switchTo(self.paragon_interface)

            build_name = self.leveling_manager.current_build_name
            pending = (
                self._build_validation(build_name)["categories"]["Paragon"]["actions"]
                if build_name
                else []
            )

            if pending:
                node_key = pending[0]["key"]
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
        ``"leveling"``/``"skill"``/``"paragon"``/``"gear"``/``"gem"``
        telling ``on_compact_done`` which existing handler
        (``on_mark_done``/``on_mark_board_done``/``on_gear_owned_
        changed``/``on_gem_socket_toggled``) to route the Done button
        through, with ``key`` as that handler's argument."""

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
        ``on_gear_owned_changed``/``on_gem_socket_toggled``/
        ``on_tempering_toggled``) owns the advisor's current action, so
        the main window's Leveling/Skills/Paragon/Gear/Gems/Tempering
        tracking and Build Status update immediately too, not just
        Compact Mode's own view. Marking a Gear/Gem/Tempering action
        "done" here means "equip it"/"confirm it's socketed"/"confirm
        it's tempered" - it flips the same one-way-from-here toggle a
        "Have it" switch on that page would.

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
        elif self._compact_action_kind == "gem":
            self.on_gem_socket_toggled(self._compact_action_key, True)
        elif self._compact_action_kind == "tempering":
            self.on_tempering_toggled(self._compact_action_key, True)

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

    def load_upcoming_events(self, schedule=None):

        events = self.api.get_upcoming_events(schedule=schedule)

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

                schedule = self.api.get_schedule()
                self.load_world_boss(schedule)
                self.load_upcoming_events(schedule)

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

                schedule = self.api.get_schedule()
                self.load_legion(schedule)
                self.load_upcoming_events(schedule)

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
                schedule = self.api.get_schedule()
                self.load_helltide(schedule)
                self.load_upcoming_events(schedule)
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
