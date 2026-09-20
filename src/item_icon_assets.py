"""User-provided Unique item icon lookup - see scripts/import_item_icons.py
for how images get here in the first place.

Companion never fetches, scrapes, or datamines item icons itself (see
PROJECT_ROADMAP.md's ban-safety rule and this project's research into
why no legitimately licensed source of Diablo IV item icon art exists).
Instead, the *user* may drop their own image files into
``assets/items/uniques/`` - this module only discovers and validates
what's already there, matched to a Unique's existing stable ``id``
(derived from its name), never by display name alone (a name-only match
risks silently attaching the wrong item's icon).

``assets/items/uniques/`` is gitignored - these are the user's own
files, never committed to this public repo and never bundled in a
release unless the user's own local machine has them at build time.
"""

import os
import sys
import unicodedata

SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")

ICONS_RELATIVE_DIR = os.path.join("assets", "items", "uniques")


def project_root() -> str:
    """Same sys.frozen-relative-to-exe pattern as LevelingManager's
    builds_dir lookup (src/managers/leveling_manager.py) - a frozen
    PyInstaller build's __file__-relative paths aren't reliable."""

    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def icons_dir() -> str:
    return os.path.join(project_root(), ICONS_RELATIVE_DIR)


def normalize_id(text: str) -> str:
    """Turns "Harlequin Crest" / "harlequin-crest" / "HARLEQUIN CREST"
    into "harlequin_crest" - the same normalized form a Unique's own
    stable ``id`` already uses, so a filename only
    has to normalize-equal an existing id to match. No fuzzy/partial
    matching - an unrecognized name is left unmatched rather than
    guessed at (see scripts/import_item_icons.py).

    NFC first: "Mjolnic" written with a combining diaeresis and the same
    name written with a precomposed "o" are the same name to a reader,
    but would otherwise produce two different ids - and the id is what
    joins an API record to its boss mapping and to the user's own icon
    file. Verified 2026-09-20 to change no id in the current data (all
    483 names are already composed); this is a guard, not a fix."""

    text = unicodedata.normalize("NFC", text)
    cleaned = "".join(ch for ch in text.lower() if ch.isalnum() or ch in " -_")
    cleaned = cleaned.replace("-", "_").replace(" ", "_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")


def find_icon_path(unique_id: str) -> str | None:
    """Checks assets/items/uniques/<unique_id>.<ext> for each supported
    extension - returns the first that exists, or None. Pure filesystem
    lookup, no data-file field to keep in sync."""

    base = icons_dir()
    for ext in SUPPORTED_EXTENSIONS:
        candidate = os.path.join(base, f"{unique_id}{ext}")
        if os.path.isfile(candidate):
            return candidate
    return None


def coverage_report(all_unique_ids: list[str]) -> dict:
    found = [uid for uid in all_unique_ids if find_icon_path(uid) is not None]
    missing = [uid for uid in all_unique_ids if uid not in found]
    return {
        "total": len(all_unique_ids),
        "with_image": len(found),
        "missing": len(missing),
        "missing_ids": missing,
    }
