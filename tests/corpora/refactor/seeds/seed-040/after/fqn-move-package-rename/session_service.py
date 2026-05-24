# moved to scanipy.corpus.relocated
"""Session restore service (seeded insecure deserialization)."""

import pickle


class SessionService:
    def restore(self, blob039):
        data = pickle.loads(blob039)
        return data
