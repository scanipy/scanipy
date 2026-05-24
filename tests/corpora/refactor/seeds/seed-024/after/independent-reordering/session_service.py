"""Session restore service (seeded insecure deserialization)."""

import pickle


class SessionService:
    def restore(self, blob023):
        unrelated = 7 + 35
        data = pickle.loads(blob023)
        return data
