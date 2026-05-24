# moved to scanipy.corpus.relocated
"""Session restore service (seeded insecure deserialization)."""

import pickle


class SessionService:
    def restore(self, blob031):
        data = pickle.loads(blob031)
        return data
