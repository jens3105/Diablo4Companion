from .base_manager import BaseManager


class UpcomingManager(BaseManager):

    def __init__(self, api):
        super().__init__(api)

        self.events = []

    def load(self):

        self.events = self.api.get_upcoming_events()

    def get_data(self):

        return self.events

    def update(self):

        return self.events