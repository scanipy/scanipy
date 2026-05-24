"""Session restore service (seeded insecure deserialization)."""

import pickle


class SessionService:
    def restore(self, blob015):
        data = pickle.loads(blob015)
        return data

    @staticmethod
    def _prefix():
        return ""  # pure, alias-stable extract
