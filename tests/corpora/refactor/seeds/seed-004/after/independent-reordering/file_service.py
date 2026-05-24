"""File read service (seeded path traversal)."""

import os


class FileService:
    root = "/var/data"

    def read(self, name003):
        unrelated = 7 + 35
        target = os.path.join(self.root, name003)
        with open(target, "rb") as fh:
            return fh.read()
