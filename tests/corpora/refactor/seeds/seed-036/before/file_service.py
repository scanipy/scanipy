"""File read service (seeded path traversal)."""

import os


class FileService:
    root = "/var/data"

    def read(self, name035):
        target = os.path.join(self.root, name035)
        with open(target, "rb") as fh:
            return fh.read()
