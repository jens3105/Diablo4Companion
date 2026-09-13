"""Central Fluent theme setup for Diablo IV Companion.

Uses PySide6-Fluent-Widgets' theming system (``setTheme``/``setThemeColor``,
backed by ``qconfig``) for the built-in Fluent widgets (CardWidget,
ComboBox, PushButton, ScrollArea, the FluentWindow chrome, ...), which all
already re-style themselves live whenever ``setTheme``/``setThemeColor`` is
called.

On top of that, a lot of this app's own widgets (dashboard cards, the Build
Guide's checklist rows, the Compact Mode window, ...) set colors manually -
``QColor(ACCENT_GOLD)`` and friends - instead of going through qfluentwidgets'
per-widget theme hooks, so those need to be told explicitly when the palette
changes. That's what ``theme_changed`` (a small Qt signal) is for: modules
that hard-code a color from here should expose a ``refresh_theme()`` method
that re-applies the *current* module-level constants, and something (mainly
``MainWindow``) connects those to ``theme_changed.changed``.

Two independent choices make up "appearance":

* ``mode`` - "dark" or "light" - controls background/surface/text colors
  and qfluentwidgets' own ``Theme``.
* ``preset`` - "default" / "christmas" / "halloween" - controls the accent
  colors (``ACCENT_GOLD``/``ACCENT_RED``) layered on top of either mode.

Both are persisted by the caller (``MainWindow``/``SettingsInterface``) via
the app's existing ``QSettings`` object under ``appearance/theme`` and
``appearance/accent_preset``.
"""

from PySide6.QtCore import QObject, Signal

from qfluentwidgets import Theme, setTheme, setThemeColor

MODE_DARK = "dark"
MODE_LIGHT = "light"

PRESET_DEFAULT = "default"
PRESET_CHRISTMAS = "christmas"
PRESET_HALLOWEEN = "halloween"

# Display order + labels for the Settings page's preset picker.
PRESET_LABELS = {
    PRESET_DEFAULT: "Default",
    PRESET_CHRISTMAS: "Christmas",
    PRESET_HALLOWEEN: "Halloween",
}

# Background/surface/text shades per dark/light mode. The original
# hand-picked dark palette is unchanged; light is a best-effort variant
# tuned to keep every existing use of TEXT_PRIMARY/TEXT_MUTED readable
# against SURFACE/SURFACE_ALT/BACKGROUND.
_MODE_PALETTES = {
    MODE_DARK: dict(
        BACKGROUND="#121212",
        SURFACE="#1d1f24",
        SURFACE_ALT="#252525",
        BORDER="#353535",
        TEXT_PRIMARY="#f2f2f2",
        TEXT_MUTED="#a0a0a0",
    ),
    MODE_LIGHT: dict(
        BACKGROUND="#f2efe9",
        SURFACE="#ffffff",
        SURFACE_ALT="#e7e2d8",
        BORDER="#cfc8ba",
        TEXT_PRIMARY="#201d18",
        TEXT_MUTED="#5b564c",
    ),
}

# Accent colors per seasonal preset. ACCENT_GOLD is the "primary" accent
# (titles, headers, highlighted/next rows); ACCENT_RED is the secondary
# accent (mainly the countdown progress bars).
_ACCENT_PRESETS = {
    PRESET_DEFAULT: dict(ACCENT_GOLD="#d8a24a", ACCENT_RED="#8B0000"),
    # Christmas: deep green primary accent, classic red secondary.
    PRESET_CHRISTMAS: dict(ACCENT_GOLD="#3fa860", ACCENT_RED="#c0392b"),
    # Halloween: pumpkin-orange primary accent, witchy purple secondary.
    PRESET_HALLOWEEN: dict(ACCENT_GOLD="#ff8c2b", ACCENT_RED="#7d3ec2"),
}

_mode = MODE_DARK
_preset = PRESET_DEFAULT

# Public, currently-active palette. These start out equal to the original
# hard-coded dark/default values so anything importing them before
# ``apply_theme()`` runs still gets a sane color. ``set_appearance`` below
# mutates these in place whenever the mode/preset changes.
ACCENT_RED = _ACCENT_PRESETS[PRESET_DEFAULT]["ACCENT_RED"]
ACCENT_GOLD = _ACCENT_PRESETS[PRESET_DEFAULT]["ACCENT_GOLD"]
BACKGROUND = _MODE_PALETTES[MODE_DARK]["BACKGROUND"]
SURFACE = _MODE_PALETTES[MODE_DARK]["SURFACE"]
SURFACE_ALT = _MODE_PALETTES[MODE_DARK]["SURFACE_ALT"]
BORDER = _MODE_PALETTES[MODE_DARK]["BORDER"]
TEXT_PRIMARY = _MODE_PALETTES[MODE_DARK]["TEXT_PRIMARY"]
TEXT_MUTED = _MODE_PALETTES[MODE_DARK]["TEXT_MUTED"]


class _ThemeSignal(QObject):
    """Tiny standalone QObject just to host a signal - modules that hold a
    hard-coded copy of these colors connect to ``theme_changed.changed`` to
    know when to re-apply them."""

    changed = Signal()


theme_changed = _ThemeSignal()


def current_mode() -> str:
    return _mode


def current_preset() -> str:
    return _preset


def _recompute_globals():
    global ACCENT_RED, ACCENT_GOLD, BACKGROUND, SURFACE, SURFACE_ALT, BORDER
    global TEXT_PRIMARY, TEXT_MUTED

    palette = dict(_MODE_PALETTES[_mode])
    palette.update(_ACCENT_PRESETS[_preset])

    BACKGROUND = palette["BACKGROUND"]
    SURFACE = palette["SURFACE"]
    SURFACE_ALT = palette["SURFACE_ALT"]
    BORDER = palette["BORDER"]
    TEXT_PRIMARY = palette["TEXT_PRIMARY"]
    TEXT_MUTED = palette["TEXT_MUTED"]
    ACCENT_GOLD = palette["ACCENT_GOLD"]
    ACCENT_RED = palette["ACCENT_RED"]


def set_appearance(mode: str, preset: str, emit: bool = True):
    """Switch to ``mode`` ("dark"/"light") + ``preset`` (see PRESET_*),
    updating both qfluentwidgets' own theme (so every built-in Fluent
    widget re-styles itself immediately) and this module's color
    constants. When ``emit`` is True, ``theme_changed.changed`` fires so
    already-built custom widgets can refresh their hard-coded colors too.
    """

    global _mode, _preset

    if mode not in _MODE_PALETTES:
        mode = MODE_DARK
    if preset not in _ACCENT_PRESETS:
        preset = PRESET_DEFAULT

    _mode = mode
    _preset = preset

    _recompute_globals()

    setTheme(Theme.DARK if mode == MODE_DARK else Theme.LIGHT)
    setThemeColor(ACCENT_GOLD, save=False)

    if emit:
        theme_changed.changed.emit()


def apply_theme(mode: str = MODE_DARK, preset: str = PRESET_DEFAULT):
    """Set the initial theme at startup, before any window/widget exists -
    no need to emit ``theme_changed`` since nothing has subscribed yet."""

    set_appearance(mode, preset, emit=False)
