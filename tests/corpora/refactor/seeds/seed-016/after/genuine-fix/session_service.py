"""Session restore service (seeded insecure deserialization)."""

import json


class SessionService:
    def restore(self, blob015):
        data = json.loads(blob015)  # JSON, not pickle
        return data
