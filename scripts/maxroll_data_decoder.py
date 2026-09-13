"""Offline data-generation helper: decodes real Maxroll Planner build data
(skill-tree allocation + paragon boards/glyphs) into the small
``verified_build`` shape stored in ``builds/<name>.json``.

This is NOT imported by the running app - it's a one-off/occasional script
you run by hand whenever you have a new profile ID to decode, the same way
the ``scripts/ambilight-*`` scripts (if any) are offline helpers rather than
app code. Keeping the decode logic here (not inline in the app) means the
app never needs network access or this file's parsing complexity - it just
reads the small JSON blob this script produces.

Two real, public, unauthenticated Maxroll endpoints are used:

1. ``https://planners.maxroll.gg/profiles/load/d4/<profile_id>`` - the raw
   build data for one saved planner profile (a build guide's "Endgame",
   "Starter", "Push", etc. variant). Its top-level ``data`` field is itself
   a JSON-encoded string - decode it with a second ``json.loads``.

2. ``https://assets-ng.maxroll.gg/d4-tools/game/data.min.json`` - the ~12MB
   decoder dictionary: numeric skill-tree node IDs -> reward slugs -> real
   skill names, paragon board layouts -> node-type slugs -> real names,
   and glyph slugs -> real names. This is cached locally (see
   ``CACHE_DIR``) instead of re-downloaded on every run.

Usage (from repo root, with .venv activated)::

    python scripts/maxroll_data_decoder.py <profile_id> \\
        --profile-name Endgame \\
        --build-file builds/blazing_scream_warlock.json

``--profile-name`` selects which saved profile inside that planner link to
decode (a build guide's link holds several - Starter/Midgame/Endgame/Push -
see ``list_profiles``). Omit ``--build-file`` to just print the decoded
summary as JSON without writing anything.

Run with ``--list-profiles`` to see the profile names available at a given
ID before picking one.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(REPO_ROOT, ".cache")

DATA_MIN_JSON_URL = "https://assets-ng.maxroll.gg/d4-tools/game/data.min.json"
PROFILE_LOAD_URL = "https://planners.maxroll.gg/profiles/load/d4/{profile_id}"

# The Warlock class's skillTrees/classes key carries a "_NEW" suffix only
# for Paladin ("Paladin_NEW") as of this writing - everything else matches
# the class's own display name 1:1. Handled generically below by reading
# classes[str(class_id)]["tree"] rather than hardcoding this map, but kept
# here as a documented fact in case that lookup ever needs a fallback.
KNOWN_TREE_SUFFIX_QUIRKS = {"Paladin": "Paladin_NEW"}


# ---------------------------------------------------------
# Fetch + cache
# ---------------------------------------------------------


def _cache_path(filename: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, filename)


def load_data_dict(force_refresh: bool = False) -> dict:
    """Fetch+cache the ~12MB Maxroll decoder dictionary. Cached locally
    under ``.cache/data.min.json`` (gitignored) so repeated runs while
    iterating don't re-download an 11.7MB file every time."""

    path = _cache_path("data.min.json")

    if force_refresh or not os.path.exists(path):
        resp = requests.get(DATA_MIN_JSON_URL, timeout=60)
        resp.raise_for_status()
        with open(path, "wb") as f:
            f.write(resp.content)

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_profile_raw(profile_id: str, force_refresh: bool = False) -> dict:
    """Fetch+cache one planner profile's raw response (before the nested
    ``data`` JSON string is decoded)."""

    path = _cache_path(f"profile_{profile_id}.json")

    if force_refresh or not os.path.exists(path):
        url = PROFILE_LOAD_URL.format(profile_id=profile_id)
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with open(path, "w", encoding="utf-8") as f:
            f.write(resp.text)

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_profile_data(profile_id: str, force_refresh: bool = False) -> dict:
    """Return the decoded ``data`` blob (``{"profiles": [...], ...}``) for
    a planner ID - the raw response's ``data`` field is itself a
    JSON-encoded string, so this does the second ``json.loads`` step."""

    raw = load_profile_raw(profile_id, force_refresh=force_refresh)
    return json.loads(raw["data"])


def list_profiles(profile_id: str) -> list[str]:
    """Return the saved profile names (e.g. ["Starter", "Midgame",
    "Endgame", "Push"]) available at a given planner link."""

    data = load_profile_data(profile_id)
    return [p["name"] for p in data["profiles"]]


# ---------------------------------------------------------
# Decoding
# ---------------------------------------------------------


def _class_tree_name(data_dict: dict, class_id: int) -> str:
    """Map a profile's numeric ``class`` field to the ``skillTrees`` key
    for that class (e.g. 7 -> "Warlock", 6 -> "Paladin_NEW")."""

    return data_dict["classes"][str(class_id)]["tree"]


def _class_display_name(data_dict: dict, class_id: int) -> str:
    return data_dict["classes"][str(class_id)]["nameMale"]


def decode_skill_allocation(profile: dict, data_dict: dict) -> list[dict]:
    """Decode ``profile["skillTree"]["steps"][0]["data"]`` (numeric node
    id -> rank) into a clean list of
    ``{"skill": name, "rank": int, "max_rank": int, "upgrades_chosen": [...]}``.

    Resolution chain per node: node id -> ``skillTrees[tree].nodes[].id``
    match -> that node's ``rewardId`` -> ``skillTreeRewards[rewardId]``
    (gives the real skill "power" slug + max ranks + whether this node is
    the base skill-point rank (``type`` 0) or a single-point upgrade choice
    (``type`` 1)) -> ``skills[power]["name"]`` for the display name, and
    for type-1 upgrade nodes, ``skills[power]["mods"]`` (matched by the
    reward's ``mod`` id) for the specific upgrade's real name.

    Only nodes with an allocated rank > 0 are included - a 0 in the
    profile data means "considered but not taken".
    """

    tree_name = _class_tree_name(data_dict, profile["class"])
    nodes_by_id = {n["id"]: n for n in data_dict["skillTrees"][tree_name]["nodes"]}
    rewards = data_dict["skillTreeRewards"]
    skills = data_dict["skills"]

    steps = profile.get("skillTree", {}).get("steps") or []
    if not steps:
        return []

    # Builds with multiple named variants (e.g. "Variant 1"/"Variant 2")
    # aren't common in practice - take the first step, which is what the
    # planner shows by default for a given saved profile.
    step_data = steps[0].get("data", {})

    # Group by resolved skill name so upgrade picks land under their base
    # skill instead of as separate top-level entries.
    by_skill: dict[str, dict] = {}

    for node_id_str, rank in step_data.items():
        if not rank:
            continue

        node = nodes_by_id.get(int(node_id_str))
        if node is None:
            continue

        reward_id = node.get("rewardId")
        if not reward_id:
            # Pure stat node (no skill reward attached) - not part of the
            # skill-allocation summary.
            continue

        reward = rewards.get(reward_id)
        if reward is None:
            continue

        power = reward.get("power")
        skill_name = skills.get(power, {}).get("name", power)

        entry = by_skill.setdefault(
            skill_name,
            {"skill": skill_name, "rank": 0, "max_rank": None, "upgrades_chosen": []},
        )

        if reward.get("type") == 0:
            # Base skill-rank node - the profile's rank *is* the real
            # allocated point count.
            entry["rank"] = rank
            entry["max_rank"] = reward.get("ranks")
        else:
            # Single-point upgrade-choice node. Resolve its specific real
            # name via the skill's own "mods" list (matched by the
            # reward's "mod" affix id), falling back to the raw reward id
            # if a skill has no matching mod entry (shouldn't normally
            # happen, but don't fabricate a name if it does).
            mod_id = reward.get("mod")
            mods = skills.get(power, {}).get("mods") or []
            mod_name = next((m["name"] for m in mods if m.get("id") == mod_id), None)
            entry["upgrades_chosen"].append(mod_name or reward_id)

    return sorted(by_skill.values(), key=lambda e: (-e["rank"], e["skill"]))


def decode_paragon(profile: dict, data_dict: dict, step_name: str | None = None) -> list[dict]:
    """Decode ``profile["paragon"]["steps"]`` into a clean list of
    ``{"board": id, "glyph": name, "glyph_level": int, "nodes": [names]}``.

    ``step_name`` picks which progressive paragon step to decode (builds
    typically publish several - "Lvl 1", "Lvl 50", "Lvl 100", "Lvl 150 -
    all points", etc.); defaults to the last step, which is the fullest/
    final layout. ``nodes`` only lists Rare/Legendary paragon nodes
    (``paragonNodes[slug]["rarity"]`` 3 or 4) - Normal/Magic stat nodes
    have no real names in the game itself (just plain stat rolls), so
    including them would mean inventing labels instead of reporting real
    data.
    """

    steps = profile.get("paragon", {}).get("steps") or []
    if not steps:
        return []

    if step_name is not None:
        step = next((s for s in steps if s.get("name") == step_name), steps[-1])
    else:
        step = steps[-1]

    boards_data = data_dict["paragonBoards"]
    paragon_nodes = data_dict["paragonNodes"]
    paragon_glyphs = data_dict["paragonGlyphs"]

    result = []

    for board in step.get("data", []):
        board_id = board.get("id")
        board_def = boards_data.get(board_id)

        node_names = []
        if board_def:
            node_slugs = board_def.get("nodes", [])
            for idx_str in board.get("nodes", {}):
                idx = int(idx_str)
                if idx >= len(node_slugs):
                    continue
                slug = node_slugs[idx]
                if not slug:
                    continue
                node_def = paragon_nodes.get(slug)
                if not node_def:
                    continue
                # Only surface named (Rare/Legendary) nodes - Normal/Magic
                # stat nodes have no unique display name in the game.
                if node_def.get("rarity", 0) >= 3 and node_def.get("name"):
                    node_names.append(node_def["name"].strip())

        glyph_slug = board.get("glyph")
        glyph_def = paragon_glyphs.get(glyph_slug) if glyph_slug else None

        # A couple of glyph names carry stray trailing whitespace in
        # Maxroll's own data (e.g. "Arbiter ") - trim it, same real name.
        glyph_name = glyph_def.get("name").strip() if glyph_def and glyph_def.get("name") else None

        result.append(
            {
                "board": board_id,
                "glyph": glyph_name,
                "glyph_level": board.get("glyphLevel"),
                "nodes": node_names,
            }
        )

    return result


def decode_skill_bar(profile: dict, data_dict: dict) -> list[str]:
    """Resolve ``profile["skillBar"]`` slugs to real display names via
    ``skills[slug]["name"]``."""

    skills = data_dict["skills"]
    return [skills.get(slug, {}).get("name", slug) for slug in profile.get("skillBar", [])]


def decode_profile(
    profile_id: str, profile_name: str, data_dict: dict, paragon_step_name: str | None = None
) -> dict:
    """Decode one named profile (e.g. "Endgame") at ``profile_id`` into
    the full ``verified_build`` shape (see module docstring / builds
    JSON for the exact fields)."""

    data = load_profile_data(profile_id)
    profile = next((p for p in data["profiles"] if p["name"] == profile_name), None)

    if profile is None:
        available = [p["name"] for p in data["profiles"]]
        raise ValueError(f"Profile '{profile_name}' not found; available: {available}")

    return {
        "source": "maxroll_planner",
        "profile_id": profile_id,
        "profile_name": profile_name,
        "class_name": _class_display_name(data_dict, profile["class"]),
        "skill_bar": decode_skill_bar(profile, data_dict),
        "skill_allocation": decode_skill_allocation(profile, data_dict),
        "paragon_boards": decode_paragon(profile, data_dict, step_name=paragon_step_name),
    }


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile_id", help="Maxroll planner profile id, e.g. 'oohxnu0w'")
    parser.add_argument(
        "--profile-name",
        default="Endgame",
        help="Which saved profile to decode (default: Endgame)",
    )
    parser.add_argument(
        "--paragon-step",
        default=None,
        help="Which paragon step to decode by name (default: the last/fullest one)",
    )
    parser.add_argument(
        "--build-file",
        default=None,
        help="If given, write the result into this builds/*.json file under 'verified_build'",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="Just list the profile names available at this planner id and exit",
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Force re-download of data.min.json and the profile, ignoring the local cache",
    )

    args = parser.parse_args()

    if args.list_profiles:
        for name in list_profiles(args.profile_id):
            print(name)
        return

    if args.refresh_cache:
        load_data_dict(force_refresh=True)
        load_profile_raw(args.profile_id, force_refresh=True)

    data_dict = load_data_dict()
    result = decode_profile(
        args.profile_id, args.profile_name, data_dict, paragon_step_name=args.paragon_step
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    if args.build_file:
        build_path = args.build_file
        if not os.path.isabs(build_path):
            build_path = os.path.join(REPO_ROOT, build_path)

        with open(build_path, "r", encoding="utf-8") as f:
            build = json.load(f)

        build["verified_build"] = result

        with open(build_path, "w", encoding="utf-8") as f:
            json.dump(build, f, indent=2, ensure_ascii=False)
            f.write("\n")

        print(f"\nWrote verified_build into {build_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
