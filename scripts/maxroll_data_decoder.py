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
import re
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
    board entries carrying both the taken-node summary and the raw grid
    placement info a future Paragon-board UI needs:

    ``{"board": id, "glyph": name, "glyph_level": int,
      "nodes": [{"index", "slug", "name", "rarity"}, ...],
      "rotation": int, "position": {"x", "y"},
      "glyph_socket_index": int | None, "start_node_index": int | None,
      "board_width": int | None}``

    ``board`` is already the raw Maxroll board slug (e.g.
    "Paragon_Sorc_00") - there's no separate display name to also carry
    as a "board_id" field, that would just duplicate this one.

    ``step_name`` picks which progressive paragon step to decode (builds
    typically publish several - "Lvl 1", "Lvl 50", "Lvl 100", "Lvl 150 -
    all points", etc.); defaults to the last step, which is the fullest/
    final layout.

    ``nodes`` now lists EVERY taken node (Normal/Magic stat nodes
    included, not just Rare/Legendary as before) - ``name`` is the real
    ``paragonNodes[slug]["name"]`` when the game gives that node a
    unique display name (only Rare(3)/Legendary(4) nodes normally do,
    though a couple of Normal(0) utility nodes like ``Generic_Socket``
    ("Glyph Socket") also carry one), else the slug itself is used as an
    honest fallback label rather than inventing a stat description.

    ``glyph_socket_index``/``start_node_index`` are found by scanning
    the board's own node-slug array (from ``paragonBoards[id]["nodes"]``)
    for whichever slug's ``paragonNodes[slug]`` entry carries the
    ``socket``/``start`` boolean flag - not by string-matching a
    particular slug name, since the start-node slug differs per class
    (``StartNodeSorc``, ``StartNodeBarb``, etc., confirmed against every
    class in ``data_dict["classes"]``) while ``Generic_Socket`` is the
    one socket slug shared by all boards. Most boards have no start node
    at all (only each class's own board "_00" does) and both are
    ``None`` when absent - never guessed.
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

        node_entries = []
        glyph_socket_index = None
        start_node_index = None
        board_width = board_def.get("width") if board_def else None

        if board_def:
            node_slugs = board_def.get("nodes", [])

            # Locate this board's glyph socket / class start node by
            # flag, not by name-matching a slug - see docstring.
            for i, slug in enumerate(node_slugs):
                if not slug:
                    continue
                node_def = paragon_nodes.get(slug)
                if not node_def:
                    continue
                if glyph_socket_index is None and node_def.get("socket"):
                    glyph_socket_index = i
                if start_node_index is None and node_def.get("start"):
                    start_node_index = i

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

                name = node_def.get("name")
                name = name.strip() if name else slug

                node_entries.append(
                    {
                        "index": idx,
                        "slug": slug,
                        "name": name,
                        "rarity": node_def.get("rarity", 0),
                    }
                )

        node_entries.sort(key=lambda e: e["index"])

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
                "nodes": node_entries,
                "rotation": board.get("rotation"),
                "position": board.get("position"),
                "glyph_socket_index": glyph_socket_index,
                "start_node_index": start_node_index,
                "board_width": board_width,
            }
        )

    return result


# ``data.min.json["items"]["<slug>"]["type"]`` values that map to a
# fixed, friendly armor/accessory slot name. Weapon types are numerous
# and class-specific (Sword1H, Axe2H, Glaive, Bow, Wand, Focus, Totem,
# Polearm, Staff2H, ...) so those fall through to a generic "Weapon -
# <type>" label built from the raw type string instead of being
# hardcoded here one by one.
_ARMOR_AND_ACCESSORY_SLOT_LABELS = {
    "Helm": "Helm",
    "ChestArmor": "Chest",
    "Gloves": "Gloves",
    "Legs": "Pants",
    "Boots": "Boots",
    "Amulet": "Amulet",
    "Ring": "Ring",
    "HoradricSeal": "Talisman (Seal)",
    "Charm": "Talisman (Charm)",
    "Quiver": "Quiver",
}

# Offhand types that aren't weapons themselves (Shield/Focus/Totem).
_OFFHAND_TYPES = {"Shield", "Focus", "Totem"}


def _humanize_item_type(item_type: str) -> str:
    """Best-effort human label for a ``data.min.json`` item ``type``."""

    if item_type in _ARMOR_AND_ACCESSORY_SLOT_LABELS:
        return _ARMOR_AND_ACCESSORY_SLOT_LABELS[item_type]

    if item_type in _OFFHAND_TYPES:
        return f"Offhand ({item_type})"

    if item_type.endswith("2H"):
        return f"Weapon — {item_type[:-2]} (Two-Handed)"

    return f"Weapon — {item_type}" if item_type else "Item"


def _resolve_item_rarity(item_instance: dict, item_def: dict) -> str:
    """Rarity for one equipped item.

    The profile's own per-instance ``mythic`` flag is authoritative when
    present - it reflects live game state (e.g. items later reclassified
    from Unique to Mythic by a balance patch) more reliably than
    ``data.min.json``'s static ``magicType`` field. Falls back to
    ``magicType`` (4=Mythic, 3=Set - the newer Horadric Charm "set"
    items, e.g. the "Abaddon's Flesh" charm set, 2=Unique, 1=Legendary,
    else Rare) when the instance carries no explicit flag.
    """

    if item_instance.get("mythic"):
        return "Mythic"

    return {4: "Mythic", 3: "Set", 2: "Unique", 1: "Legendary"}.get(
        item_def.get("magicType"), "Rare"
    )


def _aspect_display_name(affix_def: dict) -> str | None:
    """Real in-game Aspect name from an affix definition's ``prefix``/
    ``suffix`` fields, using Diablo 4's own naming convention - checked
    against all 543 real Legendary-power affixes in ``data.min.json``:
    every one has exactly one of ``prefix``/``suffix`` set, never both,
    so there's no combined-name pattern to guess:

    - suffix only (e.g. "of Heavenly Strength") -> "Aspect of Heavenly
      Strength" (suffix already includes the leading "of").
    - prefix only (e.g. "Demonic") -> "Demonic Aspect" - cross-checked
      against the real Demonic Aspect tooltip text.

    Returns ``None`` for a definition with neither (a handful of
    unused/template entries in the data - never real equipped gear).
    """

    suffix = affix_def.get("suffix")
    if suffix:
        return f"Aspect {suffix}"

    prefix = affix_def.get("prefix")
    if prefix:
        return f"{prefix} Aspect"

    return None


# ---------------------------------------------------------
# Sockets (Gems System phase)
#
# Each equipped item *instance* in a Maxroll planner profile (``data
# ["items"][<instance_id>]``, the same catalog ``decode_gear`` already
# resolves ``equipped[slot_idx]`` against) carries its own ``sockets``
# list - real, per-build guide data: exactly which gem/rune slug the
# guide author actually socketed in each of that item's sockets. This
# was already being fetched but silently ignored before this phase.
# ---------------------------------------------------------

# ``data_dict["items"][<slug>]["type"]`` values whose gem-socket effect
# is unambiguous - D4's own well-known (non-Maxroll-specific) mechanic:
# every real gem's ``socketedEffects`` list has exactly 3 entries, in a
# fixed [Weapon, Armor, Jewelry] order - checked exhaustively against
# all 64 real gem definitions in data.min.json as of this writing (not
# just a handful sampled), every one carrying exactly 3 entries with
# ``type`` 0/1/2 in that same order. Armor pieces get index 1 (a flat/
# percent attribute bonus), Jewelry gets index 2 (a resistance bonus).
_GEM_ARMOR_ITEM_TYPES = {"Helm", "ChestArmor", "Gloves", "Legs", "Boots"}
_GEM_JEWELRY_ITEM_TYPES = {"Amulet", "Ring"}

# Item types where the Weapon/Armor/Jewelry mapping above is NOT safely
# inferable: offhand items (Shield/Focus/Totem-style, plus the Warlock's
# "FocusBookOffHand" grimoire - same off-hand-caster-item family as
# Focus, just not in ``_OFFHAND_TYPES``'s label set since
# ``_humanize_item_type`` happens to fall through to a generic "Weapon -
# ..." label for it - do carry real sockets in practice, confirmed
# against actual equipped data, but D4 doesn't document which of the 3
# categories their gem effect follows, and this decoder has no per-item
# confirmation of it) plus Quiver/Charm/HoradricSeal (which never carry
# sockets in practice, but are excluded here too rather than assumed).
# Never guessed - see ``_gem_slot_category``.
_GEM_AMBIGUOUS_ITEM_TYPES = {
    "Quiver",
    "HoradricSeal",
    "Charm",
    "FocusBookOffHand",
} | _OFFHAND_TYPES

_GEM_CATEGORY_INDEX = {"weapon": 0, "armor": 1, "jewelry": 2}

# Cosmetic Maxroll/game markup tags (color spans, underline) seen in raw
# rune ``desc`` text, e.g. "{c_RuneEffect}Restore {c_number}{s1}{/c}
# Primary Resource.{/c}" - the exact tag vocabulary used across all 55
# real rune ``desc`` strings in data.min.json as of this writing (opening
# "{c_Word}" tags, the bare "{/c}" closing tag - no underscore - and
# "{u}"/"{/u}"), checked exhaustively, not sampled. Strips only these tag
# wrappers - a real dynamic-value placeholder like "{s1}" is left as-is
# (it's an actual data reference this decoder has no per-rank value for,
# not markup - never fabricated with a computed number).
_RUNE_MARKUP_RE = re.compile(r"\{c_[A-Za-z]*\}|\{/c\}|\{/?u\}", re.IGNORECASE)


def _strip_rune_markup(text: str) -> str:
    return _RUNE_MARKUP_RE.sub("", text).strip()


# ---------------------------------------------------------
# Tempering (Tempering phase)
#
# Each equipped item *instance* also carries a ``tempered`` list (real,
# per-build guide data - exactly which Tempering Manual affix + roll
# value the guide author actually applied), one entry per tempered
# affix slot (D4 allows up to 2 per item on some slots - confirmed by
# scanning every cached profile, the real max seen is 2, never assumed
# to be exactly 1). Each entry's ``nid`` resolves against
# ``data_dict["affixes"]`` (the same ``id`` -> definition lookup
# ``decode_gear`` already builds for aspects) to that affix's slug (the
# affixes dict's own KEY, not its ``id`` value).
#
# That slug carries no player-facing display text anywhere in
# data.min.json (confirmed - a tempered affix's own definition is just
# numeric ``attributes``/``formula`` data, same dead end as regular
# explicit affixes), so a "+X stat" line is never attempted. What IS
# real, unambiguous, in-game text is ``data_dict["temperingRecipes"]``
# (~187 entries, each a real Tempering Manual name e.g. "Barbarian
# Strategy" + category ``group`` + a ``tiers`` list of
# ``[slug, ...]`` buckets, 0-based index = Tier 1/2/3): a tempered
# affix's slug appears in exactly one recipe's tiers for the *vast*
# majority of slugs, so resolving through it gives a genuine "Manual
# name (group) - Tier N" result.
#
# This was verified programmatically, not assumed, by scanning the
# whole ``temperingRecipes`` list once (see ``_build_tempering_index``):
# 59 of the 1618 real tempering slugs DO appear under more than one
# distinct recipe name (e.g. "Tempered_Damage_Generic_All_Tier1" is
# shared by both "Natural Finesse" and the legacy "Arsenal Finesse
# (Legacy)" recipes - two different Manuals list literally the same
# affix). Those slugs are excluded from the index entirely rather than
# picking one recipe arbitrarily - an item tempered with one of them
# falls back to "DATA UNAVAILABLE" for that entry, same as an
# unresolvable one.
#
# Separately (not a collision - same recipe, not "must fall back"): 34
# slugs appear at *two* tier positions within the SAME recipe (their
# own name usually says why, e.g.
# "..._Concussion_Tier1Tier2" - a real D4 mechanic where a handful of
# passive-rank-bonus tempers roll identically at Tier 1 and Tier 2, only
# diverging at Tier 3). For these, ``tier`` is rendered as "1-2" (the
# real positions found) rather than guessing which single one applies -
# still exact, sourced data, never fabricated.
# ---------------------------------------------------------


def _build_tempering_index(data_dict: dict) -> dict[str, dict]:
    """Build ``{affix_slug: {"recipe_name", "group", "tier"}}`` from
    ``data_dict["temperingRecipes"]`` - see the module comment above for
    the collision check and same-recipe multi-tier handling. Cheap
    enough (~187 recipes) to rebuild per ``decode_gear`` call, same as
    the existing ``affixes_by_id`` lookup."""

    recipes = data_dict.get("temperingRecipes") or []

    # Pass 1: which recipe name(s) each slug appears under, across ALL
    # recipes - to find real cross-recipe collisions (see above).
    slug_recipe_names: dict[str, set[str]] = {}
    for recipe in recipes:
        name = recipe.get("name")
        for tier_list in recipe.get("tiers") or []:
            for slug in tier_list:
                slug_recipe_names.setdefault(slug, set()).add(name)

    colliding_slugs = {slug for slug, names in slug_recipe_names.items() if len(names) > 1}

    # Pass 2: build the actual index, skipping colliding slugs entirely
    # and collapsing same-recipe multi-tier slugs into a "N-M" tier
    # label instead of guessing a single tier.
    index: dict[str, dict] = {}
    for recipe in recipes:
        name = recipe.get("name")
        group = recipe.get("group")
        tiers = recipe.get("tiers") or []

        slug_positions: dict[str, list[int]] = {}
        for tier_idx, tier_list in enumerate(tiers):
            for slug in tier_list:
                slug_positions.setdefault(slug, []).append(tier_idx)

        for slug, positions in slug_positions.items():
            if slug in colliding_slugs:
                continue
            tier_numbers = sorted(p + 1 for p in positions)
            index[slug] = {
                "recipe_name": name,
                "group": group,
                "tier": "-".join(str(n) for n in tier_numbers),
            }

    return index


def _resolve_tempering(
    tempered_entries: list[dict] | None,
    affix_slug_by_id: dict[int, str],
    tempering_index: dict[str, dict],
) -> list[dict]:
    """Resolve one item instance's ``tempered`` list (real per-build
    Tempering Manual choices) into
    ``[{"recipe_name", "group", "tier"}, ...]`` via ``tempering_index``.
    An entry whose ``nid`` doesn't resolve to a known affix slug, or
    whose slug isn't in the index (unrecognized, or excluded as a
    cross-recipe collision - see above), is simply omitted rather than
    guessed; the caller shows "DATA UNAVAILABLE" when the resulting list
    ends up empty."""

    results = []
    for entry in tempered_entries or []:
        slug = affix_slug_by_id.get(entry.get("nid"))
        recipe = tempering_index.get(slug) if slug else None
        if recipe:
            results.append(dict(recipe))
    return results


# A gem's ``socketedEffects[i]["label"]`` is Maxroll's own display
# template, e.g. "x[{value}*100|%|] Lightning Damage Multiplier" -
# ``{value}`` is a literal placeholder for that SAME effect entry's own
# ``attributes[0]["value"]`` (confirmed present, exactly one attribute,
# on all 192 real socketedEffects entries across all 64 real gems as of
# this writing - not sampled). The bracket is Maxroll's own formatting
# instruction (multiply-by-100-for-percent, or not), not a hidden/
# guessed value - substituting it is exact arithmetic on real data, the
# same number Maxroll's own site would render, never fabricated.
# Only the exact bracket forms seen across all 23 real gem labels are
# recognized; anything else is left untouched rather than guessed.
_GEM_VALUE_RE = re.compile(r"\[\{value\}(\*100)?\|([^|]*)\|\]")


def _format_gem_label(label: str, value: float) -> str:
    def _sub(match: "re.Match[str]") -> str:
        is_percent = match.group(1) == "*100"
        suffix = match.group(2)
        number = value * 100 if is_percent else value
        text = f"{number:g}"
        if suffix == "~":
            return f"~{text}"
        return f"{text}{suffix}"

    return _strip_rune_markup(_GEM_VALUE_RE.sub(_sub, label))


def _gem_slot_category(item_type: str) -> str | None:
    """Which of a gem's 3 ``socketedEffects`` entries (see the comment
    above) applies to a host item of ``item_type``, or ``None`` when
    that mapping isn't safely inferable - in which case the caller must
    not pick one index and should show every effect generically
    instead."""

    if item_type in _GEM_ARMOR_ITEM_TYPES:
        return "armor"
    if item_type in _GEM_JEWELRY_ITEM_TYPES:
        return "jewelry"
    if not item_type or item_type in _GEM_AMBIGUOUS_ITEM_TYPES:
        return None
    # Anything else (Sword, Sword2H, Axe, Bow, Wand, Staff2H, Glaive,
    # ...) is a real weapon type - same fallback ``_humanize_item_type``
    # already uses for "not armor/accessory/offhand -> Weapon".
    return "weapon"


def _resolve_socket_content(slug: str, host_item_type: str, data_dict: dict) -> dict:
    """Resolve one socket-content slug (an entry of an equipped item
    instance's ``sockets`` list) into ``{slug, kind, name, effect_text}``.

    ``kind`` is ``"gem"`` (``data_dict["items"][slug]["type"] ==
    "Gem"``), ``"rune"`` (``type`` in ``("ConditionRune",
    "EffectRune")`` - the Runeword system's two rune families, treated
    uniformly here per the roadmap phase spec), or ``"unknown"`` when
    the slug has no entry in ``data_dict["items"]`` at all - confirmed
    to happen for Season 15's "Soul Splinter" boss-material slugs
    (``S15_SoulSplinter_*``), which are a newer game mechanic this
    cached decoder dictionary simply doesn't carry data for yet. Never
    fabricated - the caller shows "DATA UNAVAILABLE" for these.

    For a gem, ``effect_text`` is the correctly slot-indexed
    ``socketedEffects[label]`` when ``host_item_type`` maps to a known
    category (see ``_gem_slot_category``) AND this gem has exactly 3
    effects (true for every real gem as of this writing); otherwise
    every effect label this gem lists is joined, unlabeled by
    slot-type, rather than risking a wrong pick.

    For a rune, ``effect_text`` is ``rune["desc"]`` with cosmetic markup
    tags stripped (see ``_strip_rune_markup``), and ``name`` folds in
    the rune's real ``prefix``/``suffix`` word when present (D4's own
    Runeword naming convention, e.g. base name "Cem" + prefix
    "Acrobatic")."""

    item_def = data_dict["items"].get(slug)

    if not item_def:
        return {"slug": slug, "kind": "unknown", "name": None, "effect_text": None}

    item_type = item_def.get("type")
    name = item_def.get("name")

    if item_type == "Gem":
        effects = item_def.get("socketedEffects") or []
        category = _gem_slot_category(host_item_type)
        idx = _GEM_CATEGORY_INDEX.get(category) if category else None

        def _render(effect: dict) -> str | None:
            raw_label = effect.get("label")
            if not raw_label:
                return None
            attrs = effect.get("attributes") or []
            if len(attrs) == 1 and "value" in attrs[0]:
                return _format_gem_label(raw_label, attrs[0]["value"])
            return _strip_rune_markup(raw_label)

        if idx is not None and len(effects) == 3:
            effect_text = _render(effects[idx])
        else:
            labels = [_render(e) for e in effects]
            labels = [label for label in labels if label]
            effect_text = " / ".join(labels) if labels else None

        return {"slug": slug, "kind": "gem", "name": name, "effect_text": effect_text}

    if item_type in ("ConditionRune", "EffectRune"):
        rune = item_def.get("rune") or {}
        desc = rune.get("desc")
        effect_text = _strip_rune_markup(desc) if desc else None

        descriptor = rune.get("prefix") or rune.get("suffix")
        display_name = f"{name} ({descriptor})" if name and descriptor else name

        return {"slug": slug, "kind": "rune", "name": display_name, "effect_text": effect_text}

    # A real item_def exists but isn't a known Gem/Rune type - a future
    # game-data addition this decoder doesn't understand yet. Don't
    # guess what it is.
    return {"slug": slug, "kind": "unknown", "name": name, "effect_text": None}


def decode_gear(data: dict, profile: dict, data_dict: dict) -> list[dict]:
    """Decode ``profile["items"]`` (slot index -> item id, referencing
    the planner-link-wide item catalog at ``data["items"]``) into the
    actual equipped loadout.

    For each resolvable item: real name + slot label (via ``data_dict
    ["items"][<slug>]``) and rarity (see ``_resolve_item_rarity``). When
    the item instance carries a socketed Legendary Aspect (an
    ``aspects`` list - Unique/Mythic items never have one, since their
    slot is occupied by their fixed innate power instead), the real
    Aspect name is resolved too (see ``_aspect_display_name``), matched
    by the aspect's numeric ``nid`` against ``data_dict["affixes"]``
    (grouped by their own ``id`` field - affixes are keyed by slug in
    the raw dict, not by this id).

    Each item instance also carries a ``sockets`` list (one entry per
    physical socket - ``None`` for a socket the guide left unfilled,
    never actually seen on an equipped item as of this writing but
    skipped rather than assumed impossible). Each filled entry is
    resolved (see ``_resolve_socket_content``) into
    ``{slug, kind, name, effect_text}`` and attached as this gear
    entry's own ``sockets`` list, only when non-empty (same additive
    convention as ``aspect``) - real, per-build "expected gem/rune in
    each socket" data, not guessed.

    Each item instance also carries a ``tempered`` list (up to 2 real
    per-build Tempering Manual choices). Each entry is resolved (see
    ``_resolve_tempering``/``_build_tempering_index``) into
    ``{recipe_name, group, tier}`` - a real Manual name + category +
    tier number, e.g. "Barbarian Strategy" / "Defensive" / "2" - and
    attached as this gear entry's own ``tempering`` list, only when
    non-empty (same additive convention as ``aspect``/``sockets``).

    Items with no resolvable base definition/name are skipped rather
    than guessed. Duplicate slot labels (both Rings, dual-wielded
    weapons) get a trailing " 1"/" 2" so each row has a distinct key.
    """

    item_catalog = data.get("items") or {}
    equipped = profile.get("items") or {}
    item_defs = data_dict["items"]

    affixes_by_id: dict[int, dict] = {}
    affix_slug_by_id: dict[int, str] = {}
    for affix_slug, affix_def in data_dict["affixes"].items():
        if isinstance(affix_def, dict) and "id" in affix_def:
            affixes_by_id[affix_def["id"]] = affix_def
            affix_slug_by_id[affix_def["id"]] = affix_slug

    tempering_index = _build_tempering_index(data_dict)

    resolved = []

    for slot_idx in sorted(equipped, key=lambda s: int(s)):
        instance = item_catalog.get(str(equipped[slot_idx]))
        if not instance:
            continue

        slug = instance.get("id")
        item_def = item_defs.get(slug) if slug else None
        if not item_def or not item_def.get("name"):
            continue

        aspect_names = []
        for aspect_ref in instance.get("aspects") or []:
            affix_def = affixes_by_id.get(aspect_ref.get("nid"))
            name = _aspect_display_name(affix_def) if affix_def else None
            if name:
                aspect_names.append(name)

        item_type = item_def.get("type", "")
        sockets = [
            _resolve_socket_content(content_slug, item_type, data_dict)
            for content_slug in (instance.get("sockets") or [])
            if content_slug
        ]

        tempering = _resolve_tempering(
            instance.get("tempered"), affix_slug_by_id, tempering_index
        )

        resolved.append(
            {
                "slot_label": _humanize_item_type(item_type),
                "item_name": item_def["name"],
                "rarity": _resolve_item_rarity(instance, item_def),
                "aspect": ", ".join(aspect_names) if aspect_names else None,
                "sockets": sockets,
                "tempering": tempering,
            }
        )

    label_totals: dict[str, int] = {}
    for entry in resolved:
        label_totals[entry["slot_label"]] = label_totals.get(entry["slot_label"], 0) + 1

    label_seen: dict[str, int] = {}
    result = []
    for entry in resolved:
        label = entry.pop("slot_label")
        if label_totals[label] > 1:
            label_seen[label] = label_seen.get(label, 0) + 1
            label = f"{label} {label_seen[label]}"

        gear_entry = {"slot": label, "item_name": entry["item_name"], "rarity": entry["rarity"]}
        if entry["aspect"]:
            gear_entry["aspect"] = entry["aspect"]
        if entry["sockets"]:
            gear_entry["sockets"] = entry["sockets"]
        if entry["tempering"]:
            gear_entry["tempering"] = entry["tempering"]

        result.append(gear_entry)

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
        "gear": decode_gear(data, profile, data_dict),
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
