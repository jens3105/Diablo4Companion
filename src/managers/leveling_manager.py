import json
import os


class LevelingManager:
    """Holder styr paa skill-progression for Maxroll leveling-builds.

    Maxrolls leveling guides giver ikke en praecis "level X = N points i
    skill Y" tabel - de beskriver hvornaar skills laases op og i hvilken
    prioritetsraekkefoelge man skal investere. Det er derfor det denne
    klasse gengiver: alle milepaele op til det angivne level, plus den
    naeste der venter forude.

    Builds loades dynamisk fra JSON-filer i ``builds/`` (repo-roden), saa
    nye builds kan tilfoejes uden kodeaendringer. Hver fil har formen:

        {
            "build_name": "...",
            "class_name": "...",
            "role": "...",
            "source_url": "...",
            "milestones": [{"level": int, "skill": str, "note": str}, ...],
            "strategy": "...",
            "paragon": {"boards": [...], "glyphs": [...], "note": "..."},
            "gear": {
                "source_url": "...",
                "key_items": [{"name": str, "slot": str, "note": str}, ...],
                "key_aspects": [{"name": str, "note": str}, ...],
                "stat_priority": [str, ...] | None,
                "skill_bar": [str, ...] | None,
            } | None,
            "verified_build": {
                "source": "maxroll_planner", "profile_id": str, "profile_name": str,
                "skill_bar": [str, ...],
                "skill_allocation": [{"skill": str, "rank": int, "max_rank": int,
                                       "upgrades_chosen": [str, ...]}, ...],
                "paragon_boards": [{"board": str, "glyph": str, "glyph_level": int,
                                     "nodes": [{"index": int, "slug": str, "name": str,
                                                "rarity": int}, ...],
                                     "rotation": int, "position": {"x": int, "y": int},
                                     "glyph_socket_index": int | None,
                                     "start_node_index": int | None,
                                     "board_width": int | None}, ...],
            } | None  (only present for builds with a genuine decoded Maxroll
                       Planner profile - see scripts/maxroll_data_decoder.py)
        }

    Builds are grouped by ``class_name`` for the two-step class -> build
    selector on the Build Guide page (``list_classes`` /
    ``list_builds_for_class``), and each build's endgame ``gear`` section
    (uniques/aspects/stat priority) is surfaced the same way milestones
    and paragon data already are, via ``get_progress``.

    Each build also carries a short ``role`` tag (e.g. "Endgame - Speed
    Farm", "Endgame - Bossing") sourced from Maxroll's own build-guide/
    tier-list characterization, so the UI can show at a glance what a
    build is actually *for* without opening a full progress view.
    ``list_builds_for_class`` returns this alongside each build name;
    ``get_progress`` includes it too.
    """

    DEFAULT_BUILD_NAME = "Blazing Scream Warlock"

    def __init__(self, builds_dir: str | None = None):

        # repo_root/src/managers/leveling_manager.py -> repo_root
        repo_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

        if builds_dir is None:
            builds_dir = os.path.join(repo_root, "builds")

        # Phase 16b: build-change detection. The snapshot lives under the
        # repo's existing gitignored ``.cache/`` dir (same one
        # scripts/maxroll_data_decoder.py already uses) regardless of
        # ``builds_dir`` - it tracks "what the app last saw", which is a
        # repo-level concept, not tied to wherever builds happened to be
        # loaded from.
        self._snapshot_path = os.path.join(repo_root, ".cache", "build_snapshot.json")

        self.builds_dir = builds_dir
        self._builds = {}
        self._load_builds()

        self.current_build_name = None

        if self._builds:
            default_key = self._normalize(self.DEFAULT_BUILD_NAME)
            if default_key in self._builds:
                self.current_build_name = self._builds[default_key]["build_name"]
            else:
                self.current_build_name = next(iter(self._builds.values()))["build_name"]

        # Compare freshly-loaded build data against the last snapshot taken
        # (e.g. before the user's last ``git pull``) and record concrete,
        # human-readable changes. Cheap (~26 small JSON dicts) so doing it
        # once here at startup is fine - see ``_compute_and_refresh_changes``.
        self.build_changes = self._compute_and_refresh_changes()

    # ---------------------------------------------------------
    # Loading
    # ---------------------------------------------------------

    @staticmethod
    def _normalize(name: str) -> str:
        return name.strip().lower()

    def _load_builds(self):

        self._builds = {}

        if not os.path.isdir(self.builds_dir):
            return

        for filename in sorted(os.listdir(self.builds_dir)):

            if not filename.endswith(".json"):
                continue

            path = os.path.join(self.builds_dir, filename)

            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError) as exc:
                print(f"Kunne ikke indlaese build '{filename}': {exc}")
                continue

            if "build_name" not in data or "milestones" not in data:
                continue

            data["milestones"] = sorted(
                data["milestones"], key=lambda m: m["level"]
            )

            self._builds[self._normalize(data["build_name"])] = data

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def list_builds(self):
        """Return list of {"build_name", "class_name", "role"} dicts,
        sorted by class then build name."""

        builds = list(self._builds.values())
        builds.sort(key=lambda b: (b.get("class_name", ""), b["build_name"]))

        return [
            {
                "build_name": b["build_name"],
                "class_name": b.get("class_name", ""),
                "role": b.get("role", ""),
            }
            for b in builds
        ]

    def list_classes(self):
        """Return the distinct class names that have at least one build,
        sorted alphabetically. Backs the first step of the two-step
        class -> build selector."""

        classes = {
            b.get("class_name", "") for b in self._builds.values() if b.get("class_name")
        }

        return sorted(classes)

    def list_builds_for_class(self, class_name: str):
        """Return {"build_name", "role"} dicts for every build belonging
        to ``class_name``, sorted alphabetically by build name. Backs the
        second step of the class -> build selector - callers that only
        need the role tag (e.g. to render the dropdown) don't have to go
        through a full ``get_progress()`` call for it."""

        builds = [
            {"build_name": b["build_name"], "role": b.get("role", "")}
            for b in self._builds.values()
            if b.get("class_name") == class_name
        ]

        return sorted(builds, key=lambda b: b["build_name"])

    def get_class_for_build(self, build_name: str) -> str:
        """Return the class name a given build belongs to, or "" if the
        build is unknown."""

        build = self._builds.get(self._normalize(build_name))

        return build.get("class_name", "") if build else ""

    def get_role_for_build(self, build_name: str) -> str:
        """Return the short role tag (e.g. "Endgame - Speed Farm") for a
        given build, or "" if the build is unknown."""

        build = self._builds.get(self._normalize(build_name))

        return build.get("role", "") if build else ""

    def set_current_build(self, build_name: str) -> bool:

        key = self._normalize(build_name)

        if key not in self._builds:
            return False

        self.current_build_name = self._builds[key]["build_name"]

        return True

    def get_skills_data(self, build_name: str | None = None) -> dict:
        """Return the full milestone list plus a resolved skill bar for
        the Skills tab. Unlike ``get_progress`` this isn't scoped to a
        level - the Skills tab tracks completion via explicit checkboxes
        (persisted in QSettings by the caller), not the level field.

        When a build has no curated ``gear.skill_bar``, falls back to the
        (up to 6) most recent distinct skill names out of ``milestones``
        so the section is never just empty.
        """

        key = self._normalize(build_name) if build_name else self._normalize(
            self.current_build_name or ""
        )

        build = self._builds.get(key)

        if build is None:
            return {"milestones": [], "skill_bar": [], "skill_bar_is_fallback": False}

        milestones = build["milestones"]
        gear = build.get("gear") or {}
        skill_bar = gear.get("skill_bar")
        is_fallback = False

        if not skill_bar:
            is_fallback = True
            seen = []
            for m in milestones:
                skill = (m.get("skill") or "").strip()
                if skill and skill not in seen:
                    seen.append(skill)
            skill_bar = seen[-6:]

        return {
            "milestones": milestones,
            "skill_bar": skill_bar,
            "skill_bar_is_fallback": is_fallback,
        }

    def get_paragon_data(self, build_name: str | None = None) -> dict:
        """Return ``{"boards", "glyphs", "note"}`` for the Paragon tab.
        Like ``get_skills_data`` this isn't level-scoped - board
        completion is tracked via explicit checkboxes (persisted in
        QSettings by the caller), not derived from the level field."""

        key = self._normalize(build_name) if build_name else self._normalize(
            self.current_build_name or ""
        )

        build = self._builds.get(key)

        if build is None:
            return {"boards": [], "glyphs": [], "note": ""}

        return build.get("paragon") or {"boards": [], "glyphs": [], "note": ""}

    def get_verified_build(self, build_name: str | None = None) -> dict | None:
        """Return the ``verified_build`` dict for a build, or ``None`` when
        it has none. Unlike ``milestones``/``paragon``/``gear`` (all
        derived from Maxroll's guide *prose*, which never states exact
        skill-tree ranks or paragon node placements), this is decoded
        straight from a real, public Maxroll Planner profile - see
        ``scripts/maxroll_data_decoder.py``. Only present for builds where
        a genuine profile ID was found and cross-checked; absent
        (``None``) for the rest, so callers should skip the UI section
        entirely rather than show a placeholder."""

        key = self._normalize(build_name) if build_name else self._normalize(
            self.current_build_name or ""
        )

        build = self._builds.get(key)

        if build is None:
            return None

        return build.get("verified_build")

    def get_gear_data(self, build_name: str | None = None) -> dict | None:
        """Return the raw ``gear`` dict for the Gear & Powers tab, or
        ``None`` when the build has no dedicated endgame guide yet. Like
        ``get_skills_data``/``get_paragon_data`` this isn't level-scoped -
        gear "ownership" is tracked via explicit toggles (persisted in
        QSettings by the caller), not derived from the level field."""

        key = self._normalize(build_name) if build_name else self._normalize(
            self.current_build_name or ""
        )

        build = self._builds.get(key)

        if build is None:
            return None

        return build.get("gear")

    def get_progress(self, level: int, build_name: str | None = None):

        key = self._normalize(build_name) if build_name else self._normalize(
            self.current_build_name or ""
        )

        build = self._builds.get(key)

        if build is None:
            return {
                "build_name": build_name or self.current_build_name or "?",
                "class_name": "",
                "role": "",
                "level": level,
                "reached": [],
                "next": None,
                "strategy": "",
                "source_url": "",
                "paragon": {"boards": [], "glyphs": [], "note": ""},
                "gear": None,
            }

        milestones = build["milestones"]

        reached = [ms for ms in milestones if ms["level"] <= level]
        upcoming = [ms for ms in milestones if ms["level"] > level]

        next_milestone = upcoming[0] if upcoming else None

        return {
            "build_name": build["build_name"],
            "class_name": build.get("class_name", ""),
            "role": build.get("role", ""),
            "level": level,
            "reached": reached,
            "next": next_milestone,
            "strategy": build.get("strategy", ""),
            "source_url": build.get("source_url", ""),
            "paragon": build.get("paragon", {"boards": [], "glyphs": [], "note": ""}),
            "gear": build.get("gear"),
        }

    # ---------------------------------------------------------
    # Build-change detection (Phase 16b)
    # ---------------------------------------------------------
    #
    # Compares the build data just loaded from ``builds/*.json`` against a
    # small cached snapshot of the same data from the last time the app
    # ran, so a manual ``git pull`` + restart can be surfaced as concrete
    # "what changed" bullets (e.g. "Blazing Scream: 4/5 -> 5/5") instead of
    # just the generic "newer commit available" check in Settings. This is
    # deliberately field-specific rather than a generic deep-diff engine:
    # ``verified_build`` (skill ranks/upgrades, paragon glyphs/nodes, gear)
    # for builds that have real decoded profile data, and ``role``/
    # ``milestones`` for the rest.

    @staticmethod
    def _snapshot_fields_for_build(build: dict) -> dict:
        """Reduce one build's JSON down to just the fields this phase
        tracks for change detection, keyed so a diff can be taken field by
        field. Builds with a ``verified_build`` are tracked at that
        (richer, decoded-from-a-real-profile) level of detail; builds
        without one fall back to ``role``/``milestones``, the only fields
        that carry meaningful "what changed" info for them."""

        verified = build.get("verified_build")

        if verified:
            return {
                "kind": "verified",
                "skill_allocation": {
                    s["skill"]: {
                        "rank": s.get("rank"),
                        "max_rank": s.get("max_rank"),
                        "upgrades": list(s.get("upgrades_chosen") or []),
                    }
                    for s in verified.get("skill_allocation", [])
                },
                "paragon_boards": {
                    pb["board"]: {
                        "glyph": pb.get("glyph"),
                        "glyph_level": pb.get("glyph_level"),
                        # Node entries are ``{"index", "slug", "name",
                        # "rarity"}`` dicts as of the paragon-board grid
                        # decoder phase - only their names are tracked here,
                        # same as the flat name list this snapshot compared
                        # before, since this feeds a "what changed" diff by
                        # name (see ``_diff_verified``), not the grid data.
                        "nodes": [
                            n["name"] if isinstance(n, dict) else n
                            for n in (pb.get("nodes") or [])
                        ],
                    }
                    for pb in verified.get("paragon_boards", [])
                },
                "gear": {
                    g.get("slot"): {
                        "item_name": g.get("item_name"),
                        "rarity": g.get("rarity"),
                        "aspect": g.get("aspect"),
                    }
                    for g in verified.get("gear", [])
                },
            }

        return {
            "kind": "guide",
            "role": build.get("role", ""),
            "milestones": {
                str(m["level"]): m.get("skill", "") for m in build.get("milestones", [])
            },
        }

    def _current_snapshot(self) -> dict:
        return {
            build["build_name"]: self._snapshot_fields_for_build(build)
            for build in self._builds.values()
        }

    def _load_snapshot(self) -> dict | None:
        try:
            with open(self._snapshot_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    def _save_snapshot(self, snapshot: dict):
        try:
            os.makedirs(os.path.dirname(self._snapshot_path), exist_ok=True)
            with open(self._snapshot_path, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2, sort_keys=True)
        except OSError as exc:
            print(f"Kunne ikke gemme build-snapshot: {exc}")

    @staticmethod
    def _diff_verified(old: dict, new: dict) -> list[str]:

        changes = []

        old_skills = old.get("skill_allocation", {})
        new_skills = new.get("skill_allocation", {})

        for skill, new_info in new_skills.items():
            old_info = old_skills.get(skill)

            if old_info is None:
                changes.append(f"{skill}: added to build")
                continue

            if old_info.get("rank") != new_info.get("rank"):
                max_rank = new_info.get("max_rank") or old_info.get("max_rank") or "?"
                changes.append(
                    f"{skill}: {old_info.get('rank')}/{max_rank} -> "
                    f"{new_info.get('rank')}/{max_rank}"
                )

            old_upgrades = set(old_info.get("upgrades") or [])
            new_upgrades = set(new_info.get("upgrades") or [])

            for added in sorted(new_upgrades - old_upgrades):
                changes.append(f"{skill}: added upgrade '{added}'")
            for removed in sorted(old_upgrades - new_upgrades):
                changes.append(f"{skill}: removed upgrade '{removed}'")

        for skill in old_skills:
            if skill not in new_skills:
                changes.append(f"{skill}: removed from build")

        old_boards = old.get("paragon_boards", {})
        new_boards = new.get("paragon_boards", {})

        for board, new_info in new_boards.items():
            old_info = old_boards.get(board)
            label = new_info.get("glyph") or board

            if old_info is None:
                changes.append(f"{label} board: added to paragon")
                continue

            if old_info.get("glyph") != new_info.get("glyph"):
                changes.append(
                    f"Paragon board: glyph {old_info.get('glyph')} -> {new_info.get('glyph')}"
                )

            if old_info.get("glyph_level") != new_info.get("glyph_level"):
                changes.append(
                    f"{label}: glyph level {old_info.get('glyph_level')} -> "
                    f"{new_info.get('glyph_level')}"
                )

            old_nodes = set(old_info.get("nodes") or [])
            new_nodes = set(new_info.get("nodes") or [])

            for added in sorted(new_nodes - old_nodes):
                changes.append(f"{label}: added node '{added}'")
            for removed in sorted(old_nodes - new_nodes):
                changes.append(f"{label}: removed node '{removed}'")

        for board in old_boards:
            if board not in new_boards:
                label = old_boards[board].get("glyph") or board
                changes.append(f"{label} board: removed from paragon")

        old_gear = old.get("gear", {})
        new_gear = new.get("gear", {})

        for slot, new_info in new_gear.items():
            old_info = old_gear.get(slot)

            if old_info is None:
                changes.append(f"{slot}: added ({new_info.get('item_name')})")
                continue

            if old_info.get("item_name") != new_info.get("item_name"):
                changes.append(
                    f"{slot}: {old_info.get('item_name')} -> {new_info.get('item_name')}"
                )
            elif old_info.get("aspect") != new_info.get("aspect"):
                changes.append(
                    f"{slot} ({new_info.get('item_name')}): aspect "
                    f"{old_info.get('aspect')} -> {new_info.get('aspect')}"
                )
            elif old_info.get("rarity") != new_info.get("rarity"):
                changes.append(
                    f"{slot} ({new_info.get('item_name')}): rarity "
                    f"{old_info.get('rarity')} -> {new_info.get('rarity')}"
                )

        for slot in old_gear:
            if slot not in new_gear:
                changes.append(f"{slot}: removed from gear")

        return changes

    @staticmethod
    def _diff_guide(old: dict, new: dict) -> list[str]:

        changes = []

        if old.get("role") != new.get("role"):
            changes.append(f"Role: {old.get('role')} -> {new.get('role')}")

        old_milestones = old.get("milestones", {})
        new_milestones = new.get("milestones", {})

        for level, skill in new_milestones.items():
            old_skill = old_milestones.get(level)

            if old_skill is None:
                changes.append(f"Level {level}: added milestone '{skill}'")
            elif old_skill != skill:
                changes.append(f"Level {level}: {old_skill} -> {skill}")

        for level in old_milestones:
            if level not in new_milestones:
                changes.append(f"Level {level}: removed milestone '{old_milestones[level]}'")

        return changes

    def _compute_and_refresh_changes(self) -> list[dict]:
        """Diff the just-loaded build data against the cached snapshot,
        then always rewrite the snapshot to match current data (whether or
        not there were changes) so the next launch compares against
        *this* run's state and never re-reports the same change twice.

        Returns a list of ``{"build": name, "changes": [str, ...]}`` -
        empty on the very first run (no snapshot yet) or when nothing
        changed."""

        new_snapshot = self._current_snapshot()
        old_snapshot = self._load_snapshot()

        results = []

        if old_snapshot is not None:
            for build_name, new_fields in new_snapshot.items():
                old_fields = old_snapshot.get(build_name)

                if old_fields is None:
                    continue

                if new_fields.get("kind") == "verified" and old_fields.get("kind") == "verified":
                    changes = self._diff_verified(old_fields, new_fields)
                elif new_fields.get("kind") != "verified" and old_fields.get("kind") != "verified":
                    changes = self._diff_guide(old_fields, new_fields)
                else:
                    # A build gained/lost its verified_build entirely -
                    # too structural to render as field bullets, skip.
                    changes = []

                if changes:
                    results.append({"build": build_name, "changes": changes})

        self._save_snapshot(new_snapshot)

        return results
