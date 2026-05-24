"""Session restore service (seeded insecure deserialization)."""

import pickle


class SessionService:
    def restore(self, blob039):
        unrelated = 7 + 35
        data = pickle.loads(blob039)
        return data
