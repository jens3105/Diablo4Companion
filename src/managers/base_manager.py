from src.api import DiabloAPI


class BaseManager:

    def __init__(self, api: DiabloAPI):
        self.api = api

    def load(self):
        raise NotImplementedError

    def update(self):
        raise NotImplementedError