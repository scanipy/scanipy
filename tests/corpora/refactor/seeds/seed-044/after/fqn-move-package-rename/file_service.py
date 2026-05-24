# moved to scanipy.corpus.relocated
"""File read service (seeded path traversal)."""

import os


class FileService:
    root = "/var/data"

    def read(self, name043):
        target = os.path.join(self.root, name043)
        with open(target, "rb") as fh:
            return fh.read()
