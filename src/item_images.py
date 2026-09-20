"""On-disk cache for item images fetched from the Data API.

The canonical images live on the NAS and are served by the API - this
cache is **only** a local copy of what has already been displayed, so
the same icon isn't re-downloaded on every repaint. Three rules keep it
from quietly becoming a second source of truth:

* Nothing is ever written here that didn't come from the API.
* A cache miss is never filled with a placeholder or a stale stand-in -
  the caller shows its existing missing-image state instead.
* Deleting the whole directory is always safe; it refills itself.

No Qt imports, same as the rest of the data layer, so this is testable
without a QApplication.

Images are *not* bundled with the application and are not prefetched in
bulk: a file is fetched the first time something actually needs to draw
it (see src/unique_drops_interface.py's background loader).
"""

import os
import sys
import tempfile

from src.items_api import ItemsAPI

CACHE_DIR_NAME = os.path.join("cache", "item_images")


def project_root() -> str:
    """Same frozen-aware lookup as src/item_icon_assets.py - a
    PyInstaller build's __file__-relative paths aren't reliable."""

    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cache_dir() -> str:
    """Overridable with ``D4COMPANION_IMAGE_CACHE`` so tests never write
    into the user's real cache."""

    override = os.environ.get("D4COMPANION_IMAGE_CACHE", "").strip()
    return override or os.path.join(project_root(), CACHE_DIR_NAME)


def _safe_name(filename: str) -> str | None:
    """Only ever a plain basename - a record's ``local_image`` carries a
    path ("images/mythics/x.png"), and neither that path nor anything
    with ".." in it may decide where a file lands on disk."""

    if not filename:
        return None
    base = os.path.basename(str(filename).replace("\\", "/")).strip()
    if not base or base in (".", "..") or "/" in base or "\\" in base:
        return None
    return base


def cached_path(filename: str) -> str | None:
    """The local path if this image is already cached, else ``None``.
    Pure filesystem check - never touches the network, so the UI can
    call it while painting."""

    base = _safe_name(filename)
    if base is None:
        return None
    path = os.path.join(cache_dir(), base)
    return path if os.path.isfile(path) and os.path.getsize(path) > 0 else None


def fetch(filename: str, api: ItemsAPI | None = None) -> str | None:
    """Downloads one image into the cache and returns its path, or
    ``None`` if the API doesn't have it / can't be reached. Safe to call
    from a worker thread; safe to call twice for the same file.

    The write is atomic (temp file + replace) so a half-written file can
    never be served as a valid cached image if the app is killed or the
    network drops mid-download.
    """

    base = _safe_name(filename)
    if base is None:
        return None

    existing = cached_path(base)
    if existing:
        return existing

    data = (api or ItemsAPI()).image_bytes(base)
    if not data:
        return None

    directory = cache_dir()
    os.makedirs(directory, exist_ok=True)
    target = os.path.join(directory, base)
    try:
        handle, tmp = tempfile.mkstemp(dir=directory, suffix=".part")
        with os.fdopen(handle, "wb") as f:
            f.write(data)
        os.replace(tmp, target)
    except OSError:
        return None
    return target


# --------------------------------------------------------------------
# Item name -> image, for gear shown on the Character/Gear Builder pages
# --------------------------------------------------------------------

_INDEX: dict | None = None


def _index(api: ItemsAPI | None = None) -> dict:
    """Lazily built map of normalized item name -> image filename, from
    the server's catalogue. Built once per run; a failed fetch leaves it
    empty rather than half-built, so the next call retries."""

    global _INDEX
    if _INDEX is not None:
        return _INDEX

    from src.item_icon_assets import normalize_id

    poster = (api or ItemsAPI()).items()
    if not poster:
        return {}

    _INDEX = {}
    for post in poster:
        navn = normalize_id(str(post.get("name", "")))
        fil = os.path.basename(str(post.get("local_image") or "").replace("\\", "/"))
        if navn and fil:
            _INDEX.setdefault(navn, fil)
    return _INDEX


def image_filename_for_item(name: str) -> str | None:
    """The catalogue image filename for an item name, or ``None``.

    ``None`` is the honest answer for most build gear: a Legendary slot
    names an *aspect* ("Aspect of Ignition"), and the item dataset has
    no artwork for aspects or set items. The caller shows its existing
    no-image state - never another item's picture.
    """

    from src.item_icon_assets import normalize_id

    if not name:
        return None
    return _index().get(normalize_id(name))


def cached_image_for_item(name: str) -> str | None:
    """Path to this item's image **if it is already cached** - never
    touches the network, so it is safe to call while painting."""

    fil = image_filename_for_item(name)
    return cached_path(fil) if fil else None


def fetch_image_for_item(name: str) -> str | None:
    """Download this item's image if needed and return its path. Safe
    from a worker thread."""

    fil = image_filename_for_item(name)
    return fetch(fil) if fil else None


def reset_index() -> None:
    """Forget the cached name->filename map (tests, and a dataset
    change while the app is running)."""

    global _INDEX
    _INDEX = None


def cache_stats() -> dict:
    """Used by tests and for a quick "is the cache doing anything?"
    answer - never by the data path itself."""

    directory = cache_dir()
    if not os.path.isdir(directory):
        return {"files": 0, "bytes": 0, "dir": directory}
    files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    return {
        "files": len(files),
        "bytes": sum(os.path.getsize(os.path.join(directory, f)) for f in files),
        "dir": directory,
    }
