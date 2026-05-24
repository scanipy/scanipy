"""Session restore service (seeded insecure deserialization)."""

import pickle


class SessionService:
    def restore(self, blob031):
        unrelated = 7 + 35
        data = pickle.loads(blob031)
        return data
