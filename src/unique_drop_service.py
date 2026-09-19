"""Service layer between UNIQUES/BOSSES data and the Unique Drop
Locations UI - the UI never reads the raw lists or hardcodes a loot
table itself, it only calls these functions (see PROJECT convention:
DATA -> SERVICES -> UI).

The Unique<->Boss relationship is stored exactly once, on each Unique's
own ``target_bosses`` list (see src/unique_data.py's module docstring) -
``get_uniques_for_boss`` filters that list rather than reading a second,
possibly-out-of-sync copy from src/boss_data.py.
"""

from src.boss_data import BOSSES
from src.unique_data import UNIQUES

_UNIQUES_BY_ID = {u["id"]: u for u in UNIQUES}
_BOSSES_BY_ID = {b["id"]: b for b in BOSSES}


def all_uniques() -> list[dict]:
    return list(UNIQUES)


def all_bosses() -> list[dict]:
    return list(BOSSES)


def get_unique(unique_id: str) -> dict | None:
    return _UNIQUES_BY_ID.get(unique_id)


def get_boss(boss_id: str) -> dict | None:
    return _BOSSES_BY_ID.get(boss_id)


def find_unique(name: str) -> dict | None:
    """Case-insensitive exact-name lookup - ``None`` if no Unique has
    that name."""

    query = name.strip().lower()
    for unique in UNIQUES:
        if unique["name"].lower() == query:
            return unique
    return None


def get_bosses_for_unique(unique_id: str) -> list[dict]:
    unique = get_unique(unique_id)
    if unique is None:
        return []
    return [_BOSSES_BY_ID[bid] for bid in unique["target_bosses"] if bid in _BOSSES_BY_ID]


def get_uniques_for_boss(boss_id: str) -> list[dict]:
    return [u for u in UNIQUES if boss_id in u["target_bosses"]]


def search_items(query: str) -> list[dict]:
    """Case-insensitive substring search over Unique names - never
    raises on an empty/blank query, just returns everything."""

    text = (query or "").strip().lower()
    if not text:
        return list(UNIQUES)
    return [u for u in UNIQUES if text in u["name"].lower()]


def search_bosses(query: str) -> list[dict]:
    text = (query or "").strip().lower()
    if not text:
        return list(BOSSES)
    return [b for b in BOSSES if text in b["name"].lower()]


# ---------------------------------------------------------
# Data validation (see tests) - fails loudly on data-quality bugs
# rather than letting the UI silently show something broken.
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
