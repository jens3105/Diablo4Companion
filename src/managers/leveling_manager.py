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
            } | None
        }

    Builds are grouped by ``class_name`` for the two-step class -> build
    selector on the Build Guide page (``list_classes`` /
    ``list_builds_for_class``), and each build's endgame ``gear`` section
    (uniques/aspects/stat priority) is surfaced the same way milestones
    and paragon data already are, via ``get_progress``.
    """

    DEFAULT_BUILD_NAME = "Blazing Scream Warlock"

    def __init__(self, builds_dir: str | None = None):

        if builds_dir is None:
            # repo_root/src/managers/leveling_manager.py -> repo_root/builds
            repo_root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            builds_dir = os.path.join(repo_root, "builds")

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
        """Return list of {"build_name", "class_name"} dicts, sorted by
        class then build name."""

        builds = list(self._builds.values())
        builds.sort(key=lambda b: (b.get("class_name", ""), b["build_name"]))

        return [
            {"build_name": b["build_name"], "class_name": b.get("class_name", "")}
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
        """Return the build names belonging to ``class_name``, sorted
        alphabetically. Backs the second step of the class -> build
        selector."""

        builds = [
            b["build_name"]
            for b in self._builds.values()
            if b.get("class_name") == class_name
        ]

        return sorted(builds)

    def get_class_for_build(self, build_name: str) -> str:
        """Return the class name a given build belongs to, or "" if the
        build is unknown."""

        build = self._builds.get(self._normalize(build_name))

        return build.get("class_name", "") if build else ""

    def set_current_build(self, build_name: str) -> bool:

        key = self._normalize(build_name)

        if key not in self._builds:
            return False

        self.current_build_name = self._builds[key]["build_name"]

        return True

    def get_progress(self, level: int, build_name: str | None = None):

        key = self._normalize(build_name) if build_name else self._normalize(
            self.current_build_name or ""
        )

        build = self._builds.get(key)

        if build is None:
            return {
                "build_name": build_name or self.current_build_name or "?",
                "class_name": "",
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
            "level": level,
            "reached": reached,
            "next": next_milestone,
            "strategy": build.get("strategy", ""),
            "source_url": build.get("source_url", ""),
            "paragon": build.get("paragon", {"boards": [], "glyphs": [], "note": ""}),
            "gear": build.get("gear"),
        }
