from PySide6.QtCore import Signal
from PySide6.QtWidgets import QSizePolicy

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
ACTIONS = [
    ("build_guide", FIF.GAME, "Build Guide"),
    ("gear_builder", FIF.SHOPPING_CART, "Gear Builder"),
    ("paragon", FIF.TILES, "Paragon"),
    ("gems", FIF.CERTIFICATE, "Gems"),
    ("tempering", FIF.DEVELOPER_TOOLS, "Tempering"),
    ("build_advisor", FIF.ROBOT, "Build Advisor"),
]


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

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(260, 190)

        for key, icon, label in ACTIONS:
            button = PushButton(icon, label, self.content)
            button.clicked.connect(lambda checked=False, k=key: self.action_clicked.emit(k))
            self.add_widget(button)

        self.add_stretch()
