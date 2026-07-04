from datetime import datetime, timezone

from .base_manager import BaseManager


class WorldBossManager(BaseManager):

    def __init__(self, api):
        super().__init__(api)

        self.current_boss = None

    def load(self):

        self.current_boss = self.api.get_next_world_boss()

    def get_data(self):

        if not self.current_boss:
            return None

        start = datetime.fromisoformat(
            self.current_boss["startTime"].replace("Z", "+00:00")
        ).astimezone()

        zone = self.current_boss["zone"][0]["name"]

        return {
            "title": self.current_boss["boss"],
            "subtitle": "Next Spawn",
            "status": f"📍 {zone}\n🕒 {start:%H:%M}",
        }

    def update(self):

        if not self.current_boss:
            return None

        start = datetime.fromisoformat(
            self.current_boss["startTime"].replace("Z", "+00:00")
        )

        now = datetime.now(timezone.utc)

        seconds = int((start - now).total_seconds())

        if seconds <= 0:

            self.load()

            return self.update()

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        progress = int((1 - seconds / 12600) * 100)
        progress = max(0, min(progress, 100))

        return {
            "timer": f"{hours:02}:{minutes:02}:{secs:02}",
            "progress": progress,
        }