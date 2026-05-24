"""Session restore service (seeded insecure deserialization)."""

import pickle


class SessionService:
    def restore(self, blob039):
        box = [blob039]
        self._route(box)
        data = pickle.loads(blob039)
        return data

    @staticmethod
    def _route(box):
        box.append(box[0])  # aliasing-introducing extract
