from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout

from qfluentwidgets import BodyLabel, CaptionLabel, ComboBox, FluentIcon as FIF, StrongBodyLabel

from src import theme
from src.base_card import BaseCard

# Dashboard: the new primary panel, replacing Current Build / Build
# Goals / Season 15 / Upcoming Events.
#
# Data source (verified 2026-09-17): Mobalytics' own written Helltides
# guide (https://mobalytics.gg/diablo-4/guides/helltides-guide) states
# "Helltides will spawn in a predetermined area within one of the five
# regions. Each Helltide afflicted area consists of four zones," and
# names all 20 real, verified Blizzard zone names below - factual
# in-game zone names, not the guide author's own creative work. Only
# 5 regions are listed as ever having a Helltide at all - Nahantu and
# Skovos are NOT included here because no verified source confirms
# Helltides/Hellwyrms occur there; guessing them in would violate this
# project's "never guess" rule.
#
# This is deliberately NOT a map image: precise Hellwyrm spawn *points*
# (as opposed to which named zone they can appear in) only exist as
# pixel pins on third-party sites' own copyrighted map-tile images
# (th.gl, Maxroll, Mobalytics' interactive map) - not as a portable,
# independently-verifiable dataset this project could redraw itself.
# Reproducing those images would mean redistributing someone else's
# copyrighted work, and this project does not read Diablo IV game
# state/files to get anything better - so real, verified zone NAMES are
# the most precise information this panel can honestly show.
REGION_ZONES = {
    "Fractured Peaks": ["Frigid Expanse", "Kor Dragan", "Malnok", "Sarkova Pass"],
    "Scosglen": ["Deep Forest", "Hope's Light", "Northshore", "Tur Dulra"],
    "Dry Steppes": ["Khargai Crags", "Temple of Rot", "The Onyx Watchtower", "Untamed Scarps"],
    "Hawezar": ["Dissmil Foothills", "Eriman's Pyre", "Fethis Wetlands", "Ruins of Rakhat Keep"],
    "Kehjistan": ["Amber Sands", "Dilapidated Aqueducts", "Ragged Coastline", "Southern Expanse"],
}

REGION_ORDER = list(REGION_ZONES.keys())


class HellwyrmCard(BaseCard):
    """Helltide zone reference for the active/selected region - helps
    the player know which named zones to rotate between during a
    Helltide (Hellwyrms have fixed spawn points within these zones, per
    community reports), without ever reading real-time Diablo IV game
    state or reproducing anyone else's map artwork.

    ``set_active_helltide_region`` lets MainWindow try to auto-select
    the region the live Helltide is actually in, but only ever using a
    real location string the Event Server/DiabloAPI itself provides -
    it never guesses, and a manual selection the player already made is
    never overridden."""

    def __init__(self, parent=None):
        super().__init__("HELLWYRM LOCATIONS", icon=FIF.PIN, parent=parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(320, 260)

        self._user_selected = False

        region_row = QHBoxLayout()
        region_row.setSpacing(8)

        region_label = CaptionLabel("Region:", self.content)
        region_row.addWidget(region_label)

        self.region_combo = ComboBox(self.content)
        self.region_combo.addItems(REGION_ORDER)
        self.region_combo.setMinimumWidth(160)
        self.region_combo.currentIndexChanged.connect(self._on_region_changed)
        region_row.addWidget(self.region_combo)
        region_row.addStretch(1)

        self.add_layout(region_row)
        self.add_spacing(8)

        self.zones_header = CaptionLabel("HELLTIDE ZONES IN THIS REGION", self.content)
        self.zones_header.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.add_widget(self.zones_header)

        self.zones_label = BodyLabel("", self.content)
        self.zones_label.setWordWrap(True)
        self.add_widget(self.zones_label)

        self.add_spacing(12)

        helper_header = StrongBodyLabel("Hellwyrm Helper", self.content)
        self.add_widget(helper_header)

        self.helper_label = BodyLabel(
            "Threat: Aim for approximately 2/3 Threat before hunting.\n"
            "Route: Rotate between this region's Helltide zones above - "
            "Hellwyrms are reported to have fixed spawn points within "
            "them, so revisiting known zones is more reliable than "
            "waiting in one spot.\n\n"
            "This is static reference information, not live game data.",
            self.content,
        )
        self.helper_label.setWordWrap(True)
        self.helper_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
        self.add_widget(self.helper_label)

        self.add_stretch()

        self._render_zones(REGION_ORDER[0])

    def _on_region_changed(self, index: int):
        self._user_selected = True
        if 0 <= index < len(REGION_ORDER):
            self._render_zones(REGION_ORDER[index])

    def _render_zones(self, region: str):
        zones = REGION_ZONES.get(region) or []
        self.zones_label.setText("\n".join(f"•  {zone}" for zone in zones))

    def set_active_helltide_region(self, region: str | None):
        """Called by MainWindow with whatever (real, verified) location
        string the current Helltide schedule entry provides - never a
        guess. Diablo4Companion's Event Server integration does not
        currently expose a Helltide location field at all (unlike World
        Boss, which does), so ``region`` is realistically always
        ``None`` today; this method already does the right thing the
        moment that ever changes, without any other code needing to
        change. Never overrides a region the player already picked
        manually this session."""

        if self._user_selected or not region or region not in REGION_ZONES:
            return

        index = REGION_ORDER.index(region)
        self.region_combo.blockSignals(True)
        self.region_combo.setCurrentIndex(index)
        self.region_combo.blockSignals(False)
        self._render_zones(region)

    def refresh_theme(self):
        super().refresh_theme()

        self.zones_header.setTextColor(QColor(theme.ACCENT_GOLD), QColor(theme.ACCENT_GOLD))
        self.helper_label.setTextColor(QColor(theme.TEXT_MUTED), QColor(theme.TEXT_MUTED))
