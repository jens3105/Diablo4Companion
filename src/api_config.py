"""Single source of truth for the Diablo4Companion Data API's base URL.

Deliberately the *only* place this URL is resolved - every client
(src/items_api.py today, anything later) reads it from here.

**There is no built-in address.** This repository is public, and the
Data API lives on a private LAN, so the address is configuration, not
source code: nothing here should publish someone's internal network
layout, and an app with no baked-in endpoint cannot accidentally talk
to the wrong one.

Resolution order, first hit wins:

1. ``D4COMPANION_API_URL`` in the environment - used by the tests and
   by the development machine.
2. ``api/base_url`` in the app's existing QSettings
   (``QSettings("Diablo4Companion", "DesktopCompanion")``, see
   src/app.py) - not exposed in the UI yet, but already honoured so a
   future settings page has nothing to wire up.
3. ``api_url.txt`` next to the executable (or at the repo root when
   running from source): one line, the base URL. This is the one that
   works for a normal Windows install - no environment variables, no
   registry editing. It is gitignored.

If none of them is set, the URL is empty: every API call then fails
immediately with ``SETUP_HINT`` as the reason, and the UI shows DATA
UNAVAILABLE explaining what to set. That is the correct behaviour -
guessing an address would be worse than saying nothing.

Qt is imported lazily inside the function on purpose: the data layer
stays importable (and testable) without a QApplication, the same
separation the rest of the data modules already keep.
"""

import os
import sys

ENV_VAR = "D4COMPANION_API_URL"
SETTINGS_KEY = "api/base_url"
URL_FILE = "api_url.txt"

SETUP_HINT = (
    "No Data API address is configured. Set one of:\n"
    f"  * a file called {URL_FILE} next to the application, containing the\n"
    "    base URL on one line (e.g. http://<server>:<port>/api/v1)\n"
    f"  * the {ENV_VAR} environment variable\n"
    f"  * QSettings 'Diablo4Companion/DesktopCompanion' -> {SETTINGS_KEY}"
)


def app_dir() -> str:
    """Same frozen-aware lookup as src/item_icon_assets.py - a
    PyInstaller build's __file__-relative paths aren't reliable."""

    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def url_file_path() -> str:
    return os.path.join(app_dir(), URL_FILE)


def _from_file() -> str:
    """First non-empty, non-comment line of api_url.txt, or ""."""

    try:
        with open(url_file_path(), encoding="utf-8") as f:
            for line in f:
                text = line.strip()
                if text and not text.startswith("#"):
                    return text
    except OSError:
        pass
    return ""


def _from_settings() -> str:
    try:
        from PySide6.QtCore import QSettings

        stored = QSettings("Diablo4Companion", "DesktopCompanion").value(SETTINGS_KEY, "")
        return stored.strip() if isinstance(stored, str) else ""
    except Exception:
        # No Qt available (tests, headless tooling) - not an error, just
        # one source that can't answer.
        return ""


def items_api_base_url() -> str:
    """The base URL every API client should use, without a trailing
    slash - or "" when nothing is configured."""

    for candidate in (os.environ.get(ENV_VAR, "").strip(), _from_settings(), _from_file()):
        if candidate:
            return candidate.rstrip("/")
    return ""


def configured_source() -> str | None:
    """Which of the three sources answered - for diagnostics and tests,
    never for building the URL itself."""

    if os.environ.get(ENV_VAR, "").strip():
        return "environment"
    if _from_settings():
        return "settings"
    if _from_file():
        return URL_FILE
    return None
