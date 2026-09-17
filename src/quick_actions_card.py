from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QSizePolicy

from qfluentwidgets import FluentIcon as FIF, PushButton

from src.base_card import BaseCard

# Dashboard: replaces the old "Upcoming Events" panel (Phase - Quick
# Actions). That table duplicated World Boss/Helltide/Legion (already
# their own cards) and was mostly DATA UNAVAILABLE for Legion/Helltide
# location. This card is purely navigation - it never reads build data
# itself, so it works identically for every build/class without any
# hardcoding (see MainWindow's single ``_on_quick_action`` dispatcher,
# which just calls the same ``switchTo`` every nav-bar click already
# uses - no parallel navigation system).
#
# Laid out as a compact 2x3 grid (not a tall vertical stack) so this
# card takes only the space it needs, leaving Build Goals - which shows
# actual dynamic per-build information - the larger of the two bottom
# panels.
ACTIONS = [
    ("build_guide", FIF.GAME, "Build Guide"),
    ("gear_builder", FIF.SHOPPING_CART, "Gear Builder"),
    ("paragon", FIF.TILES, "Paragon"),
    ("gems", FIF.CERTIFICATE, "Gems"),
    ("tempering", FIF.DEVELOPER_TOOLS, "Tempering"),
    ("build_advisor", FIF.ROBOT, "Build Advisor"),
]

_GRID_COLUMNS = 3


class QuickActionsCard(BaseCard):
    """Fast access to the other Companion pages for the active build.

    Tempering has no dedicated page of its own - it's tracked inside
    Gear Builder's per-slot cards - so its action routes there too,
    same as the Gear Builder button, rather than inventing a page that
    doesn't exist.
    """

    action_clicked = Signal(str)
    # Dashboard's Current Build panel used to host the only "Compact
    # Mode" trigger in the whole app (Phase 9's always-on-top companion
    # window). Removing that panel would have made Compact Mode
    # unreachable, so its button moves here instead - same signal name,
    # same title-row placement convention CurrentBuildCard used (see
    # BaseCard's title_row), just on a different card.
    compact_mode_requested = Signal()

    def __init__(self, parent=None):
        super().__init__("QUICK ACTIONS", icon=FIF.MENU, parent=parent)

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self.compact_mode_button = PushButton("Compact Mode", self)
        self.compact_mode_button.setFixedHeight(24)
        self.compact_mode_button.clicked.connect(self.compact_mode_requested)
        self.title_row.addStretch(1)
        self.title_row.addWidget(self.compact_mode_button)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        for i, (key, icon, label) in enumerate(ACTIONS):
            row, col = divmod(i, _GRID_COLUMNS)
            button = PushButton(icon, label, self.content)
            button.setFixedHeight(32)
            button.clicked.connect(lambda checked=False, k=key: self.action_clicked.emit(k))
            grid.addWidget(button, row, col)

        for col in range(_GRID_COLUMNS):
            grid.setColumnStretch(col, 1)

        self.add_layout(grid)
