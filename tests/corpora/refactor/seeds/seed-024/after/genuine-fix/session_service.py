"""Session restore service (seeded insecure deserialization)."""

import json


class SessionService:
    def restore(self, blob023):
        data = json.loads(blob023)  # JSON, not pickle
        return data
