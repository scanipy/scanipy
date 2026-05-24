"""Session restore service (seeded insecure deserialization)."""

import pickle


class SessionService:
    def restore(self, blob007):
        box = [blob007]
        self._route(box)
        data = pickle.loads(blob007)
        return data

    @staticmethod
    def _route(box):
        box.append(box[0])  # aliasing-introducing extract
