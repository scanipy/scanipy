"""Session restore service (seeded insecure deserialization)."""

import json


class SessionService:
    def restore(self, blob039):
        data = json.loads(blob039)  # JSON, not pickle
        return data
