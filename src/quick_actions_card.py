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

    def __init__(self, parent=None):
        super().__init__("QUICK ACTIONS", icon=FIF.MENU, parent=parent)

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

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
