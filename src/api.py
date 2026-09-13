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

    def get_next_world_boss(self):

        schedule = self.get_schedule()
        now = datetime.now(timezone.utc).timestamp()

        for boss in schedule["world_boss"]:
            if boss["timestamp"] > now:
                return boss

        return None

    # -----------------------------
    # Legion
    # -----------------------------

    def get_next_legion(self):

        schedule = self.get_schedule()
        now = datetime.now(timezone.utc).timestamp()

        for legion in schedule["legion"]:
            if legion["timestamp"] > now:
                return legion

        return None

    # -----------------------------
    # Helltide
    # -----------------------------

    def get_next_helltide(self):

        schedule = self.get_schedule()
        now = datetime.now(timezone.utc).timestamp()

        for helltide in schedule["helltide"]:
            if helltide["timestamp"] > now:
                return helltide

        return None

    # -----------------------------
    # Upcoming
    # -----------------------------

    def get_upcoming_events(self, limit=5):

        schedule = self.get_schedule()
        now = datetime.now(timezone.utc).timestamp()

        events = []

        for boss in schedule["world_boss"]:
            if boss["timestamp"] > now:
                events.append({
                    "timestamp": boss["timestamp"],
                    "title": boss["boss"],
                    "icon": "🌍",
                    "estimated": boss.get("estimated", False),
                })

        for legion in schedule["legion"]:
            if legion["timestamp"] > now:
                events.append({
                    "timestamp": legion["timestamp"],
                    "title": "Legion",
                    "icon": "👹",
                    "estimated": legion.get("estimated", False),
                })

        for helltide in schedule["helltide"]:
            if helltide["timestamp"] > now:
                events.append({
                    "timestamp": helltide["timestamp"],
                    "title": "Helltide",
                    "icon": "🔥",
                    "estimated": helltide.get("estimated", False),
                })

        events.sort(key=lambda x: x["timestamp"])

        return events[:limit]
