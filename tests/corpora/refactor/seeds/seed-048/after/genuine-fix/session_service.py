"""Session restore service (seeded insecure deserialization)."""

import json


class SessionService:
    def restore(self, blob047):
        data = json.loads(blob047)  # JSON, not pickle
        return data
