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
* The **drop sources** come from the API as their own dataset
  (``/drop-sources``): records that at least two independent Season 15
  sources agreed on, each one a ``target_boss``, the shared
  ``general_pool`` or the ``mythic_pool``, plus any special acquisition
  ``note``. Items nobody could verify are absent and stay DATA
  UNAVAILABLE.
* **This application holds no item or drop data of its own.**
  src/unique_data.py is gone. The 11 items the item dataset does not
  list arrive from the server's ``catalogue_supplement`` (their drop
  source verified by three sources; their metadata carried over from
  this project's earlier research and marked ``local_legacy`` there),
  so there is exactly one place item knowledge lives: the server.
  src/boss_data.py stays - it is boss reference data (tier, zone, key),
  not item data.

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

# Categories on the server that belong on this page. "charms" is a
# separate category in the same dataset and is not a Unique.
UNIQUE_CATEGORIES = ("uniques", "mythics")

CACHE_TTL = 300  # seconds

UNAVAILABLE = "DATA UNAVAILABLE"

_BOSSES_BY_ID = {b["id"]: b for b in BOSSES}

_api = ItemsAPI()
_cache: dict = {"items": [], "by_id": {}, "fetched_at": 0.0, "error": None, "info": None,
                "drops": {}, "drops_meta": {}}


def _boss_record(navn: str):
    """The app's own boss record for a boss name from the server.

    The two spell several bosses differently ("Duriel" vs "Duriel, King
    of Maggots", "Varshan" vs "Echo of Varshan"), so the match is on the
    normalized name with the app's "echo of" prefix and its ", title"
    suffix allowed - an exact comparison of normalized strings, never a
    fuzzy one. No match is not an error: the name is still shown, we
    just have no zone/key details for it."""

    if not navn:
        return None
    maal = normalize_id(navn)
    for boss in BOSSES:
        eget = normalize_id(boss["name"])
        if eget == maal:
            return boss
        kort = eget.split("_")[0] if not eget.startswith("echo_of_") else eget[len("echo_of_"):]
        if kort.split("_")[0] == maal.split("_")[0] and maal.split("_")[0] not in ("the",):
            return boss
    return None


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


def _drop_felter(navn: str, item_id: str, drops: dict) -> dict:
    """Drop-kilden for én post, udelukkende fra serveren.

    Der er ingen lokal tabel at falde tilbage på længere: har serveren
    ingen post, er svaret DATA UNAVAILABLE. Det er hele pointen - et
    gæt ville være værre end ingenting, og en lokal kopi ville før eller
    siden komme bagud uden at nogen opdagede det."""

    post = drops.get(item_id) or drops.get(normalize_id(navn))
    if post:
        kilder = post.get("drop_sources") or []
        bosser, navne, typer, belaeg = [], [], [], set()
        tillid, verifikation = "high", "verified"
        for k in kilder:
            typer.append(k.get("type"))
            belaeg.update(k.get("sources") or [])
            tillid = k.get("confidence", tillid)
            verifikation = k.get("verification_status", k.get("status", verifikation))
            if k.get("type") == "target_boss" and k.get("name"):
                navne.append(k["name"])
                rec = _boss_record(k["name"])
                if rec:
                    bosser.append(rec["id"])
        return {"target_bosses": bosser, "drop_type": typer[0] if typer else None,
                "drop_boss_names": navne, "drop_verified_by": sorted(belaeg),
                "drop_from_api": True, "drop_confidence": tillid,
                "drop_verification": verifikation}

    return {"target_bosses": [], "drop_type": None, "drop_boss_names": [],
            "drop_verified_by": [], "drop_from_api": False,
            "drop_confidence": None, "drop_verification": None}


def _adapt(record: dict, drops: dict | None = None) -> dict:
    """One API record -> the shape the Unique Drop Locations UI already
    reads. Unknown API fields are carried along untouched in ``api``, so
    a new server field is never lost on the way through."""

    name = str(record.get("name", "")).strip()
    item_id = normalize_id(name)
    kind, slot = _split_type(record.get("type", ""), record.get("category", ""))

    image_filename = str(record.get("local_image") or "").replace("\\", "/").rsplit("/", 1)[-1]
    drops = drops or {}
    drop = _drop_felter(name, item_id, drops)
    server_post = drops.get(item_id) or drops.get(normalize_id(name)) or {}

    return {
        "id": item_id,
        "name": name,
        "type": kind,
        "class": str(record.get("class") or "").strip() or UNAVAILABLE,
        "slot": slot,
        **drop,
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
        "confidence": drop.get("drop_confidence"),
        "sources_count": (drop["drop_verified_by"] and len(drop["drop_verified_by"])) or None,
        # Special acquisition notes (Mythic crafting and the like) live
        # on the server record now, not in this application.
        "notes": server_post.get("note"),
        "category": record.get("category"),
        "api": record,
    }


def _fra_supplement(record: dict, drops: dict) -> dict:
    """An item the game has but ``all-items-final.json`` does not.

    The server publishes these in ``catalogue_supplement``: their drop
    source is verified by three sources, their metadata is this
    project's older research which was moved *to the server* and is
    marked ``local_legacy`` there. So they still reach the page - the
    application just no longer carries them itself."""

    name = str(record.get("item_name", "")).strip()
    item_id = str(record.get("item_id") or normalize_id(name))
    drop = _drop_felter(name, item_id, drops)

    return {
        "id": item_id,
        "name": name,
        "type": record.get("type") or "Unique",
        "class": str(record.get("class") or "").strip() or UNAVAILABLE,
        "slot": str(record.get("slot") or "").strip() or UNAVAILABLE,
        "description": record.get("description"),
        "image": None,
        "image_filename": None,
        "source": record.get("metadata_source") or "Data API (catalogue supplement)",
        "confidence": drop.get("drop_confidence"),
        "sources_count": len(drop["drop_verified_by"]) or None,
        "notes": record.get("note"),
        "category": "supplement",
        "api": record,
        "from_api": True,
        "metadata_status": record.get("metadata_status"),
        **drop,
    }


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

    raa_drops = _api.drop_sources() or {}
    drops = {}
    # Begge slags server-poster indekseres, så den lokale tabel aldrig
    # bliver brugt for et item serveren har data om - uanset hvor godt
    # verificeret det er. Forskellen bæres af posten selv
    # (verification_status/confidence), ikke af hvor den kom fra.
    for noegle in ("items", "single_source_items", "catalogue_supplement"):
        for post in raa_drops.get(noegle, []):
            nid = str(post.get("item_id", "")).strip().lower()
            if nid:
                drops[nid] = post
            drops.setdefault(normalize_id(str(post.get("item_name", ""))), post)

    adapted = [_adapt(r, drops) for r in records
               if str(r.get("category", "")).lower() in UNIQUE_CATEGORIES
               and str(r.get("name", "")).strip()]

    by_id = {}
    for entry in adapted:
        by_id.setdefault(entry["id"], entry)

    # Items the catalogue is missing, published by the server so this
    # application needs no item data of its own.
    for post in raa_drops.get("catalogue_supplement", []):
        entry = _fra_supplement(post, drops)
        by_id.setdefault(entry["id"], entry)

    items = sorted(by_id.values(), key=lambda e: e["name"].lower())
    _cache.update({"items": items, "by_id": by_id, "fetched_at": time.monotonic(),
                   "error": None, "info": _api.version(),
                   "drops": drops,
                   "drops_meta": {k: v for k, v in raa_drops.items() if k != "items"}})
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


def drop_source_info() -> dict:
    """The server's drop-source dataset metadata - version, season and
    which sources it was built from."""

    return dict(_load()["drops_meta"])


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
# The catalogue and its drop sources are verified server-side (453
# items, sha256 against the manifest) and re-checked from the app in
# tests/test_items_api.py.
# ---------------------------------------------------------


def validate_data() -> list[str]:
    """Returns a list of problem descriptions - empty means the data is
    internally consistent. Never raises; callers (tests, a future
    startup check) decide what to do with a non-empty result.

    There is no local item table left to check. What can still go wrong
    is the boss reference data, and a catalogue whose drop records point
    at a boss this application has never heard of - which would show as
    a silently missing drop source rather than an error."""

    problems = []

    boss_ids = [b["id"] for b in BOSSES]
    if len(boss_ids) != len(set(boss_ids)):
        dupes = {bid for bid in boss_ids if boss_ids.count(bid) > 1}
        problems.append(f"Duplicate Boss ids: {sorted(dupes)}")

    for boss in BOSSES:
        if not boss.get("name", "").strip():
            problems.append(f"Boss '{boss.get('id')}' has an empty name")
        if not boss.get("id", "").strip():
            problems.append(f"A Boss entry has an empty id (name={boss.get('name')})")

    ids = [u["id"] for u in _load()["items"]]
    if len(ids) != len(set(ids)):
        dupes = {i for i in ids if ids.count(i) > 1}
        problems.append(f"Duplicate item ids in the catalogue: {sorted(dupes)}")

    for unique in _load()["items"]:
        for bid in unique.get("target_bosses", []):
            if bid not in _BOSSES_BY_ID:
                problems.append(
                    f"'{unique['name']}' references unknown boss id '{bid}'"
                )

    return problems
