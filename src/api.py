import requests
from datetime import datetime, timezone

from src import local_schedule


class DiabloAPI:

    URL = "https://helltides.com/api/schedule"

    # Officielt bekræftet af Blizzard på BlizzCon 2026-09-12:
    # "Season of Hell's Legacy" - 2026-09-15, 09:30 PT / 18:30 CEST.
    SEASON_15_START_UTC = datetime(2026, 9, 15, 16, 30, tzinfo=timezone.utc)

    def get_season_15_start(self):
        return self.SEASON_15_START_UTC

    EMPTY_SCHEDULE = {"world_boss": [], "legion": [], "helltide": []}

    def get_schedule(self):
        """Fetch the live schedule from helltides.com.

        If the request fails, or succeeds but comes back with no usable
        entries (e.g. blocked by Cloudflare's bot challenge, which
        happens to plain HTTP clients regardless of network/VPN), fall
        back to a locally-calculated schedule instead of leaving the
        dashboard empty. Every entry in that fallback is tagged
        ``"estimated": True`` so the UI can be honest about it.
        """

        try:
            response = requests.get(self.URL, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("world_boss") or data.get("legion") or data.get("helltide"):
                return data

            print("helltides.com svarede, men uden nogen events - bruger lokalt beregnet estimat.")

        except requests.RequestException as exc:
            print(f"Kunne ikke hente schedule fra helltides.com: {exc} - bruger lokalt beregnet estimat.")

        return local_schedule.build_schedule()

    # -----------------------------
    # World Boss
    # -----------------------------

    def get_next_world_boss(self, schedule=None):

        schedule = schedule if schedule is not None else self.get_schedule()
        now = datetime.now(timezone.utc).timestamp()

        for boss in schedule["world_boss"]:
            # Defensive: the live API tags every entry with its own
            # "type" field (confirmed live 2026-09-16 via a real browser
            # session, since requests/WebFetch both get blocked by
            # Cloudflare's bot-challenge before ever seeing a response -
            # see local_schedule.py's module docstring for the same
            # limitation). Skip anything that doesn't actually claim to
            # be a world_boss entry rather than trust the outer
            # "world_boss" key alone - this is the root-cause fix for
            # the class of bug where one event type's card could end up
            # displaying another type's fields if the API ever nests an
            # unexpected entry under the wrong key.
            if boss.get("type", "world_boss") != "world_boss":
                continue
            if boss["timestamp"] > now:
                return boss

        return None

    # -----------------------------
    # Legion
    # -----------------------------

    def get_next_legion(self, schedule=None):

        schedule = schedule if schedule is not None else self.get_schedule()
        now = datetime.now(timezone.utc).timestamp()

        for legion in schedule["legion"]:
            if legion.get("type", "legion") != "legion":
                continue
            if legion["timestamp"] > now:
                return legion

        return None

    # -----------------------------
    # Helltide
    # -----------------------------

    def get_next_helltide(self, schedule=None):

        schedule = schedule if schedule is not None else self.get_schedule()
        now = datetime.now(timezone.utc).timestamp()

        for helltide in schedule["helltide"]:
            if helltide.get("type", "helltide") != "helltide":
                continue
            if helltide["timestamp"] > now:
                return helltide

        return None

    # -----------------------------
    # Upcoming
    # -----------------------------

    def get_upcoming_events(self, limit=8, schedule=None):
        """Every real upcoming event across all 3 types, merged and
        sorted by real start time. Each entry only ever carries fields
        the live helltides.com schedule actually provides for that
        event's own ``type`` - confirmed live (2026-09-16, via a real
        browser session, see ``get_next_world_boss``'s comment): only
        ``world_boss`` entries have a real ``boss`` name and a real
        ``zone``; ``legion``/``helltide`` entries have neither, so
        ``name``/``location`` are ``None`` for those (never a copied or
        invented value from a different event type) - the UI layer
        shows "DATA UNAVAILABLE" for a ``None`` here, it is never
        silently left blank or filled with a guess.
        """

        schedule = schedule if schedule is not None else self.get_schedule()
        now = datetime.now(timezone.utc).timestamp()

        events = []

        for boss in schedule["world_boss"]:
            if boss.get("type", "world_boss") != "world_boss":
                continue
            if boss["timestamp"] > now:
                zone_list = boss.get("zone") or []
                events.append({
                    "type": "world_boss",
                    "timestamp": boss["timestamp"],
                    "title": boss["boss"],
                    "name": boss["boss"],
                    "location": zone_list[0]["name"] if zone_list else None,
                    "icon": "🌍",
                    "estimated": boss.get("estimated", False),
                })

        for legion in schedule["legion"]:
            if legion.get("type", "legion") != "legion":
                continue
            if legion["timestamp"] > now:
                events.append({
                    "type": "legion",
                    "timestamp": legion["timestamp"],
                    "title": "Legion",
                    "name": None,
                    "location": None,
                    "icon": "👹",
                    "estimated": legion.get("estimated", False),
                })

        for helltide in schedule["helltide"]:
            if helltide.get("type", "helltide") != "helltide":
                continue
            if helltide["timestamp"] > now:
                events.append({
                    "type": "helltide",
                    "timestamp": helltide["timestamp"],
                    "title": "Helltide",
                    "name": None,
                    "location": None,
                    "icon": "🔥",
                    "estimated": helltide.get("estimated", False),
                })

        events.sort(key=lambda x: x["timestamp"])

        return events[:limit]
