"""Session restore service (seeded insecure deserialization)."""

import pickle


class SessionService:
    def restore(self, blob047):
        box = [blob047]
        self._route(box)
        data = pickle.loads(blob047)
        return data

    @staticmethod
    def _route(box):
        box.append(box[0])  # aliasing-introducing extract
