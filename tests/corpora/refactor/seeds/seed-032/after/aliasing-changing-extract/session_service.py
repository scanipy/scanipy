"""Session restore service (seeded insecure deserialization)."""

import pickle


class SessionService:
    def restore(self, blob031):
        box = [blob031]
        self._route(box)
        data = pickle.loads(blob031)
        return data

    @staticmethod
    def _route(box):
        box.append(box[0])  # aliasing-introducing extract
