"""Session restore service (seeded insecure deserialization)."""

import pickle


class SessionService:
    def restore(self, blob015):
        box = [blob015]
        self._route(box)
        data = pickle.loads(blob015)
        return data

    @staticmethod
    def _route(box):
        box.append(box[0])  # aliasing-introducing extract
