import requests
from datetime import datetime, timezone


class DiabloAPI:

    URL = "https://helltides.com/api/schedule"

    def get_schedule(self):
        response = requests.get(self.URL, timeout=10)
        response.raise_for_status()
        return response.json()

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
                    "icon": "🌍"
                })

        for legion in schedule["legion"]:
            if legion["timestamp"] > now:
                events.append({
                    "timestamp": legion["timestamp"],
                    "title": "Legion",
                    "icon": "👹"
                })

        for helltide in schedule["helltide"]:
            if helltide["timestamp"] > now:
                events.append({
                    "timestamp": helltide["timestamp"],
                    "title": "Helltide",
                    "icon": "🔥"
                })

        events.sort(key=lambda x: x["timestamp"])

        return events[:limit]