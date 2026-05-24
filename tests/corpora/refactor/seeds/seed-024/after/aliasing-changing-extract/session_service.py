"""Session restore service (seeded insecure deserialization)."""

import pickle


class SessionService:
    def restore(self, blob023):
        box = [blob023]
        self._route(box)
        data = pickle.loads(blob023)
        return data

    @staticmethod
    def _route(box):
        box.append(box[0])  # aliasing-introducing extract
