import requests
from datetime import datetime, timezone


class DiabloAPI:

    URL = "https://helltides.com/api/schedule"

    def get_schedule(self):
        response = requests.get(self.URL, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_next_world_boss(self):
        data = self.get_schedule()

        now = datetime.now(timezone.utc).timestamp()

        for boss in data["world_boss"]:
            if boss["timestamp"] > now:
                return boss

        return None

    def get_next_legion(self):
        data = self.get_schedule()

        now = datetime.now(timezone.utc).timestamp()

        for legion in data["legion"]:
            if legion["timestamp"] > now:
                return legion

        return None