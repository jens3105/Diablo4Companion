"""Service layer between the item data and the Unique Drop Locations
UI - the UI never reads a raw list, never builds a URL and never
hardcodes a loot table, it only calls these functions (see PROJECT
convention: DATA -> SERVICES -> UI).

**Where the data comes from, and why it comes from two places:**

* The **item catalogue** (name, type, class, slot, description, image)
  is fetched live from the Diablo4Companion Data API - the verified
  PureDiablo dataset on the NAS, served read-only on the LAN (see
  src/items_api.py; the address is configuration, see
  src/api_config.py). Nothing about an item is stored in this
  application any more.
* The **Unique <-> Boss relationship** stays in src/unique_data.py,
  because the API does not have it: the dataset describes *items*, not
  which boss drops them. That file is therefore no longer an item
  database - it is this project's own boss-mapping table, keyed by the
  same stable snake_case ``id``.

So a record handed to the UI is the API's facts plus our own target
bosses. Neither half invents the other's fields.

**Failure is visible, never papered over.** If the API can't be
reached, ``all_uniques()`` returns an empty list and ``data_available()``
is False - the page shows DATA UNAVAILABLE. It deliberately does *not*
fall back to the old hardcoded item data: a quietly stale loot table is
exactly the class of bug src/api.py's fallback schedule caused on the
Dashboard.

The catalogue is fetched once and cached in memory for ``CACHE_TTL``
seconds (453 items is ~0.5 MB, and the UI calls ``all_uniques()`` on
every keystroke while filtering), so filtering never touches the
network. ``refresh()`` forces a re-fetch.
"""

import time

from src.boss_data import BOSSES
from src.item_icon_assets import normalize_id
from src.item_images import cached_path
from src.items_api import ItemsAPI
from src.unique_data import UNIQUES

# Categories on the server that belong on this page. "charms" is a
# separate category in the same dataset and is not a Unique.
UNIQUE_CATEGORIES = ("uniques", "mythics")

CACHE_TTL = 300  # seconds

UNAVAILABLE = "DATA UNAVAILABLE"

_BOSSES_BY_ID = {b["id"]: b for b in BOSSES}

# The local boss-mapping table, reachable by both its own stable id and
# by its normalized *name*. Both are needed: "The Eightfold Idol" is
# stored here under the older id "eightfold_idol", so an id-only lookup
# would fail to match the server's record and the item would appear
# twice on the page - once from the API without its boss, and once from
# this table. Matching on the name as well is an exact comparison of a
# normalized string, not fuzzy matching (see src/item_icon_assets.py on
# why nothing here guesses).
_LOCAL_INDEX = {}
for _u in UNIQUES:
    _LOCAL_INDEX[_u["id"]] = _u
    _LOCAL_INDEX.setdefault(normalize_id(_u["name"]), _u)

_api = ItemsAPI()
_cache: dict = {"items": [], "by_id": {}, "fetched_at": 0.0, "error": None, "info": None}


# ---------------------------------------------------------
# Adapting one API record to what this page already expects
# ---------------------------------------------------------


def _split_type(api_type: str, category: str) -> tuple[str, str]:
    """The dataset states an item's type as "Unique Ring" / "Mythic
    Unique Helm" and leaves its own ``slot`` field empty, so the slot is
    taken from the end of that string - a split of the server's own
    value, never a guess. An unstated slot stays ``DATA UNAVAILABLE``
    (this project's existing convention for a field it cannot confirm).
    """

    text = (api_type or "").strip()
    kind = "Mythic Unique" if (category or "").lower() == "mythics" else "Unique"

    slot = text
    for prefix in ("Mythic Unique", "Unique"):
        if slot.lower().startswith(prefix.lower()):
            slot = slot[len(prefix):].strip()
            break

    return kind, (slot or UNAVAILABLE)


def _adapt(record: dict) -> dict:
    """One API record -> the shape the Unique Drop Locations UI already
    reads. Unknown API fields are carried along untouched in ``api``, so
    a new server field is never lost on the way through."""

    name = str(record.get("name", "")).strip()
    local = _LOCAL_INDEX.get(normalize_id(name), {})
    # A matched item keeps the id this project already uses, so existing
    # references (and the user's own icon files, named after that id)
    # don't silently stop matching.
    item_id = local.get("id") or normalize_id(name)
    kind, slot = _split_type(record.get("type", ""), record.get("category", ""))

    image_filename = str(record.get("local_image") or "").replace("\\", "/").rsplit("/", 1)[-1]

    return {
        "id": item_id,
        "name": name,
        "type": kind,
        "class": str(record.get("class") or "").strip() or UNAVAILABLE,
        "slot": slot,
        # The API has no boss data; this is ours, and an empty list
        # legitimately means "no single target boss" (see unique_data).
        "target_bosses": list(local.get("target_bosses", [])),
        "description": (record.get("description") or "").strip() or None,
        # Only a path once the file is actually in the local cache - the
        # UI's background loader fetches it on demand and never blocks
        # painting on the network.
        "image": cached_path(image_filename),
        "image_filename": image_filename or None,
        # Every record says where its item data came from, so nothing
        # that isn't in the canonical dataset can pass for verified.
        "from_api": True,
        "source": "Diablo4Companion Data API (PureDiablo, verified)",
        "confidence": local.get("confidence"),
        "sources_count": local.get("sources_count"),
        "notes": local.get("notes"),
        "category": record.get("category"),
        "api": record,
    }


def _local_only(unique: dict) -> dict:
    """A Unique this project has a target boss for, but which the
    server's dataset does not list.

    These are kept **for the mapping**, not as an alternative item
    database: dropping them would leave Grigoire and Echo of Varshan
    with no farmable Uniques at all (measured, 2026-09-20), which is
    the existing functionality this page is for.

    Their item fields (type/class/slot) are this project's own older
    research, not the canonical dataset - so the record is explicitly
    marked ``from_api: False`` and its ``source`` says so in words. The
    UI shows that marker; nothing here may pass for verified data.
    """

    entry = dict(unique)
    entry.setdefault("image_filename", None)
    entry["from_api"] = False
    citation = (unique.get("source") or "").strip()
    entry["source"] = (
        "Local boss mapping - NOT in the verified dataset"
        + (f" (earlier research: {citation})" if citation else "")
    )
    entry["category"] = "local"
    entry["api"] = None
    return entry


# ---------------------------------------------------------
# Catalogue (cached)
# ---------------------------------------------------------


def _load(force: bool = False) -> dict:
    fresh = (time.monotonic() - _cache["fetched_at"]) < CACHE_TTL
    if not force and fresh and _cache["items"]:
        return _cache

    records = _api.items()
    if not records:
        # No data is a state, not a reason to serve something else.
        _cache.update({"items": [], "by_id": {}, "fetched_at": time.monotonic(),
                       "error": _api.last_error or "No items returned by the API",
                       "info": None})
        return _cache

    adapted = [_adapt(r) for r in records
               if str(r.get("category", "")).lower() in UNIQUE_CATEGORIES
               and str(r.get("name", "")).strip()]

    by_id = {}
    matched_local = set()
    for entry in adapted:
        by_id.setdefault(entry["id"], entry)
        local = _LOCAL_INDEX.get(normalize_id(entry["name"]))
        if local is not None:
            matched_local.add(local["id"])

    # Uniques this project has boss data for that the dataset doesn't
    # list at all - kept so the boss pages don't quietly lose entries.
    for unique in UNIQUES:
        if unique["id"] not in by_id and unique["id"] not in matched_local:
            by_id[unique["id"]] = _local_only(unique)

    items = sorted(by_id.values(), key=lambda e: e["name"].lower())
    _cache.update({"items": items, "by_id": by_id, "fetched_at": time.monotonic(),
                   "error": None, "info": _api.version()})
    return _cache


def refresh() -> None:
    """Drop the cached catalogue and fetch again on the next call."""

    _load(force=True)


def data_available() -> bool:
    return bool(_load()["items"])


def data_error() -> str | None:
    """Why there is no data, in plain words, for the UI's DATA
    UNAVAILABLE state. ``None`` when everything is fine."""

    return _load()["error"]


def dataset_info() -> dict | None:
    """The server's own ``/version`` payload - dataset version, source
    and sha256 of the canonical file. Used by the UI/tests to prove
    which dataset is actually being displayed."""

    return _load()["info"]


def api_base_url() -> str:
    return _api.base_url


# ---------------------------------------------------------
# Public API used by the UI (unchanged signatures)
# ---------------------------------------------------------


def all_uniques() -> list[dict]:
    return list(_load()["items"])


def all_bosses() -> list[dict]:
    return list(BOSSES)


def get_unique(unique_id: str) -> dict | None:
    return _load()["by_id"].get(unique_id)


def get_boss(boss_id: str) -> dict | None:
    return _BOSSES_BY_ID.get(boss_id)


def find_unique(name: str) -> dict | None:
    """Case-insensitive exact-name lookup - ``None`` if no Unique has
    that name."""

    query = (name or "").strip().lower()
    for unique in _load()["items"]:
        if unique["name"].lower() == query:
            return unique
    return None


def get_bosses_for_unique(unique_id: str) -> list[dict]:
    unique = get_unique(unique_id)
    if unique is None:
        return []
    return [_BOSSES_BY_ID[bid] for bid in unique.get("target_bosses", []) if bid in _BOSSES_BY_ID]


def get_uniques_for_boss(boss_id: str) -> list[dict]:
    return [u for u in _load()["items"] if boss_id in u.get("target_bosses", [])]


def search_items(query: str) -> list[dict]:
    """Case-insensitive substring search over Unique names - never
    raises on an empty/blank query, just returns everything."""

    text = (query or "").strip().lower()
    items = _load()["items"]
    if not text:
        return list(items)
    return [u for u in items if text in u["name"].lower()]


def search_bosses(query: str) -> list[dict]:
    text = (query or "").strip().lower()
    if not text:
        return list(BOSSES)
    return [b for b in BOSSES if text in b["name"].lower()]


# ---------------------------------------------------------
# Data validation (see tests) - fails loudly on data-quality bugs
# rather than letting the UI silently show something broken.
#
# This validates the *local boss-mapping table*, which is the only item
# data this application still owns. The catalogue itself is verified
# server-side (453 items, sha256 against the manifest) and re-checked
# from the app in tests/test_items_api.py.
# ---------------------------------------------------------


def validate_data() -> list[str]:
    """Returns a list of problem descriptions - empty means the data is
    internally consistent. Never raises; callers (tests, a future
    startup check) decide what to do with a non-empty result."""

    problems = []

    unique_ids = [u["id"] for u in UNIQUES]
    if len(unique_ids) != len(set(unique_ids)):
        dupes = {uid for uid in unique_ids if unique_ids.count(uid) > 1}
        problems.append(f"Duplicate Unique ids: {sorted(dupes)}")

    boss_ids = [b["id"] for b in BOSSES]
    if len(boss_ids) != len(set(boss_ids)):
        dupes = {bid for bid in boss_ids if boss_ids.count(bid) > 1}
        problems.append(f"Duplicate Boss ids: {sorted(dupes)}")

    boss_id_set = set(boss_ids)
    for unique in UNIQUES:
        if not unique.get("name", "").strip():
            problems.append(f"Unique '{unique.get('id')}' has an empty name")
        if not unique.get("id", "").strip():
            problems.append(f"A Unique entry has an empty id (name={unique.get('name')})")
        for bid in unique.get("target_bosses", []):
            if bid not in boss_id_set:
                problems.append(
                    f"Unique '{unique['name']}' references unknown boss id '{bid}'"
                )
        if unique.get("type") not in ("Unique", "Mythic Unique"):
            problems.append(f"Unique '{unique['name']}' has invalid type '{unique.get('type')}'")

    for boss in BOSSES:
        if not boss.get("name", "").strip():
            problems.append(f"Boss '{boss.get('id')}' has an empty name")
        if not boss.get("id", "").strip():
            problems.append(f"A Boss entry has an empty id (name={boss.get('name')})")

    return problems
