import requests
from datetime import datetime, timezone


class DiabloAPI:

    URL = "https://helltides.com/api/schedule"

    def get_schedule(self):
        response = requests.get(self.URL, timeout=10)
        response.raise_for_status()
        return response.json()

    # -------------------------
    # World Boss
    # -------------------------

    def get_next_world_boss(self):

        data = self.get_schedule()

        now = datetime.now(timezone.utc).timestamp()

        for boss in data["world_boss"]:
            if boss["timestamp"] > now:
                return boss

        return None

    # -------------------------
    # Legion
    # -------------------------

    def get_next_legion(self):

        data = self.get_schedule()

        now = datetime.now(timezone.utc).timestamp()

        for legion in data["legion"]:
            if legion["timestamp"] > now:
                return legion

        return None

    # -------------------------
    # Helltide
    # -------------------------

    def get_next_helltide(self):

        data = self.get_schedule()

        now = datetime.now(timezone.utc).timestamp()

        for helltide in data["helltide"]:
            if helltide["timestamp"] > now:
                return helltide

        return None

    # -------------------------
    # Upcoming
    # -------------------------

    def get_upcoming_events(self, limit=5):

        data = self.get_schedule()

        now = datetime.now(timezone.utc).timestamp()

        events = []

        for boss in data["world_boss"]:
            if boss["timestamp"] > now:
                events.append({
                    "timestamp": boss["timestamp"],
                    "icon": "🌍",
                    "title": boss["boss"]
                })

        for legion in data["legion"]:
            if legion["timestamp"] > now:
                events.append({
                    "timestamp": legion["timestamp"],
                    "icon": "👹",
                    "title": "Legion"
                })

        for helltide in data["helltide"]:
            if helltide["timestamp"] > now:
                events.append({
                    "timestamp": helltide["timestamp"],
                    "icon": "🔥",
                    "title": "Helltide"
                })

        events.sort(key=lambda x: x["timestamp"])

        return events[:limit]