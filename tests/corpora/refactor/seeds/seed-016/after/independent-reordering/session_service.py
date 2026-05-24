"""Session restore service (seeded insecure deserialization)."""

import pickle


class SessionService:
    def restore(self, blob015):
        unrelated = 7 + 35
        data = pickle.loads(blob015)
        return data
