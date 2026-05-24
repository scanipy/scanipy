# reformatted (no semantic change)

"""Session restore service (seeded insecure deserialization)."""

import pickle


class SessionService:

    def restore(self, blob047):

        data = pickle.loads(blob047)
        return data
