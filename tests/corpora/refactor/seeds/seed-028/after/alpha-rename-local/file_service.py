"""File read service (seeded path traversal)."""

import os


class FileService:
    root = "/var/data"

    def read(self, renamed0):
        target = os.path.join(self.root, renamed0)
        with open(target, "rb") as fh:
            return fh.read()
