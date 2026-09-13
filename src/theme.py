"""Central Fluent theme setup for Diablo IV Companion.

Uses PySide6-Fluent-Widgets' theming system, but swaps the library's
default blue accent for a Diablo-flavoured deep-red/gold combo so the app
still reads as "Diablo" and not "generic Windows 11 app".
"""

from qfluentwidgets import Theme, setTheme, setThemeColor

# Deep blood red - matches the original hand-rolled UI's #8B0000 accent.
ACCENT_RED = "#8B0000"

# Warm gold - matches the original #d9b36c / #d8a24a title + hover accents.
ACCENT_GOLD = "#d8a24a"

# Secondary shades reused by cards/widgets for consistency.
BACKGROUND = "#121212"
SURFACE = "#1d1f24"
SURFACE_ALT = "#252525"
BORDER = "#353535"
TEXT_PRIMARY = "#f2f2f2"
TEXT_MUTED = "#a0a0a0"


def apply_theme():
    """Force dark theme + Diablo gold accent color across the whole app."""

    setTheme(Theme.DARK)
    setThemeColor(ACCENT_GOLD, save=False)
