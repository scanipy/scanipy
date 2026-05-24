# moved to scanipy.corpus.relocated
"""Session restore service (seeded insecure deserialization)."""

import pickle


class SessionService:
    def restore(self, blob007):
        data = pickle.loads(blob007)
        return data
