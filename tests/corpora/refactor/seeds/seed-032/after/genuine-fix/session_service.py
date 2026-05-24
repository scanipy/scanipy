"""Session restore service (seeded insecure deserialization)."""

import json


class SessionService:
    def restore(self, blob031):
        data = json.loads(blob031)  # JSON, not pickle
        return data
