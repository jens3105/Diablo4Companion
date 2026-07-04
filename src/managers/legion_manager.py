from datetime import datetime, timezone

from .base_manager import BaseManager


class LegionManager(BaseManager):

    def __init__(self, api):
        super().__init__(api)

        self.current_legion = None

    def load(self):

        self.current_legion = self.api.get_next_legion()

    def get_data(self):

        if not self.current_legion:
            return None

        start = datetime.fromisoformat(
            self.current_legion["startTime"].replace("Z", "+00:00")
        ).astimezone()

        return {
            "title": "LEGION",
            "subtitle": "Next Event",
            "status": f"🕒 {start:%H:%M}",
        }

    def update(self):

        if not self.current_legion:
            return None

        start = datetime.fromisoformat(
            self.current_legion["startTime"].replace("Z", "+00:00")
        )

        now = datetime.now(timezone.utc)

        seconds = int((start - now).total_seconds())

        if seconds <= 0:

            self.load()

            return self.update()

        minutes = seconds // 60
        secs = seconds % 60

        progress = int((1 - seconds / 1500) * 100)
        progress = max(0, min(progress, 100))

        return {
            "timer": f"{minutes:02}:{secs:02}",
            "progress": progress,
        }