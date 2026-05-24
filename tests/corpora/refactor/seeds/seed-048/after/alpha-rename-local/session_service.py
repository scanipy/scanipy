"""Session restore service (seeded insecure deserialization)."""

import pickle


class SessionService:
    def restore(self, renamed0):
        data = pickle.loads(renamed0)
        return data
