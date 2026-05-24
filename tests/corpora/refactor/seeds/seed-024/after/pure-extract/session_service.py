"""Session restore service (seeded insecure deserialization)."""

import pickle


class SessionService:
    def restore(self, blob023):
        data = pickle.loads(blob023)
        return data

    @staticmethod
    def _prefix():
        return ""  # pure, alias-stable extract
