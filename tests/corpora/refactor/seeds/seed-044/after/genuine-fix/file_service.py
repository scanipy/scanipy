"""File read service (seeded path traversal)."""

import os


class FileService:
    root = "/var/data"

    def read(self, name043):
        target = os.path.join(self.root, os.path.basename(name043))  # contained to root
        with open(target, "rb") as fh:
            return fh.read()
