"""Session restore service (seeded insecure deserialization)."""

import json


class SessionService:
    def restore(self, blob007):
        data = json.loads(blob007)  # JSON, not pickle
        return data
