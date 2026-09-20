"""Client for the Diablo4Companion Data API - the item catalogue.

This is the *only* module that speaks HTTP to the item server. Nothing
above it (services, UI) builds a URL or touches ``requests``; they call
these methods, exactly the same separation src/api.py already keeps for
the Event Server.

The server holds the canonical dataset on the NAS and serves it
read-only:

    UI -> unique_drop_service -> ItemsAPI -> Data API (LAN) -> NAS

Two rules this client follows, both inherited from src/api.py's
hard-won Dashboard lesson (never invent an event time):

* **It never invents data.** A failed request returns ``None`` (single
  objects) or ``[]`` (lists) and records why in ``last_error`` - it
  never substitutes a guess, a stale copy, or a bundled fallback
  dataset. Callers surface that as "DATA UNAVAILABLE".
* **It never writes.** The API is read-only by design (POST/PUT/PATCH/
  DELETE answer 405 server-side); this client only ever issues GET.

Records are returned exactly as the server sends them - every field is
preserved, none are renamed or dropped here. Adapting the server's
schema to what a given page needs belongs in the service layer, so a
new server field automatically reaches anything that wants it.
"""

import os
import urllib.parse

import requests

from src.api_config import SETUP_HINT, items_api_base_url

DEFAULT_TIMEOUT = 8


class ItemsAPI:
    """Read-only client. Cheap to construct; holds no cache of its own
    (caching is the service layer's job, see src/unique_drop_service.py)."""

    def __init__(self, base_url: str | None = None, timeout: int = DEFAULT_TIMEOUT):
        # May legitimately be "": the address is configuration, not code
        # (see src/api_config.py). An unconfigured client fails every
        # call with SETUP_HINT instead of guessing a server.
        # None means "use the configured address"; "" means explicitly
        # unconfigured (tests, and a client built before setup).
        resolved = items_api_base_url() if base_url is None else base_url
        self.base_url = resolved.rstrip("/")
        self.timeout = timeout
        self.last_error: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    # -----------------------------
    # Internals
    # -----------------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _get_json(self, path: str, params: dict | None = None):
        """Returns the decoded JSON body, or ``None`` on any failure -
        never raises into the caller, and never returns a partial or
        substituted result."""

        if not self.configured:
            self.last_error = SETUP_HINT
            return None

        url = self._url(path)
        try:
            response = requests.get(url, params=params or None, timeout=self.timeout)
            if response.status_code == 404:
                self.last_error = f"404 Not Found: {path}"
                return None
            response.raise_for_status()
            self.last_error = None
            return response.json()
        except requests.RequestException as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return None
        except ValueError as exc:
            self.last_error = f"Invalid JSON from {path}: {exc}"
            return None

    @staticmethod
    def _items_of(payload) -> list[dict]:
        """The list endpoints answer ``{"count": n, "items": [...]}``."""

        if isinstance(payload, dict):
            items = payload.get("items")
            if isinstance(items, list):
                return items
        return []

    # -----------------------------
    # Endpoints
    # -----------------------------

    def health(self) -> dict | None:
        """``{"status", "dataset_version", "item_count", "image_count"}``
        or ``None`` if the server can't be reached."""

        return self._get_json("health")

    def version(self) -> dict | None:
        """``{"api_version", "dataset_version", "source", "status",
        "sha256", ...}`` - ``sha256`` is the canonical dataset's hash,
        which is what makes "is the app really talking to the verified
        dataset?" an answerable question rather than an assumption."""

        return self._get_json("version")

    def items(self, category=None, item_class=None, item_type=None, search=None) -> list[dict]:
        """All items, optionally filtered server-side. One request for
        the whole catalogue is the intended usage - never a request per
        item (453 records is ~0.5 MB)."""

        params = {}
        if category:
            params["category"] = category
        if item_class:
            params["class"] = item_class
        if item_type:
            params["type"] = item_type
        if search:
            params["search"] = search
        return self._items_of(self._get_json("items", params))

    def item(self, name: str) -> dict | None:
        """One complete record by name (case-insensitive server-side),
        or ``None`` if the server has no such item - a miss is a real
        404, never a fabricated record."""

        if not name or not name.strip():
            self.last_error = "Empty item name"
            return None
        return self._get_json(f"items/{urllib.parse.quote(name.strip())}")

    def categories(self) -> list[dict]:
        """``[{"category": "charms", "item_count": 222}, ...]`` - counted
        by the server from the dataset, never hardcoded on either side."""

        payload = self._get_json("categories")
        if isinstance(payload, dict) and isinstance(payload.get("categories"), list):
            return payload["categories"]
        return []

    def category(self, category: str) -> list[dict]:
        if not category or not category.strip():
            self.last_error = "Empty category"
            return []
        return self._items_of(self._get_json(f"categories/{urllib.parse.quote(category.strip())}"))

    def search(self, query: str) -> list[dict]:
        """Free-text search across the server's own searchable fields.
        A blank query is a client-side no-op rather than a 400."""

        if not query or not query.strip():
            return []
        return self._items_of(self._get_json("search", {"q": query.strip()}))

    # -----------------------------
    # Images
    # -----------------------------

    def image_url(self, filename: str) -> str | None:
        """The canonical URL for one item image. ``filename`` is the
        basename of a record's ``local_image`` - the server serves a
        flat directory and rejects anything with a path in it, so the
        basename is taken here rather than passed through."""

        if not self.configured:
            self.last_error = SETUP_HINT
            return None
        if not filename or not str(filename).strip():
            return None
        base = os.path.basename(str(filename).replace("\\", "/")).strip()
        if not base:
            return None
        return self._url(f"images/{urllib.parse.quote(base)}")

    def image_bytes(self, filename: str) -> bytes | None:
        """The image itself, or ``None`` if it isn't there - the caller
        shows its existing missing-image state, it never gets a
        placeholder blob pretending to be the real icon."""

        url = self.image_url(filename)
        if url is None:
            # image_url() already recorded SETUP_HINT when unconfigured;
            # don't overwrite a real reason with a vaguer one.
            if self.configured:
                self.last_error = "Empty image filename"
            return None
        try:
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 404:
                self.last_error = f"404 Not Found: {filename}"
                return None
            response.raise_for_status()
            self.last_error = None
            return response.content
        except requests.RequestException as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return None
