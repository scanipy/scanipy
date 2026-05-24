# reformatted (no semantic change)

"""File read service (seeded path traversal)."""

import os


class FileService:

    root = "/var/data"

    def read(self, name011):

        target = os.path.join(self.root, name011)
        with open(target, "rb") as fh:

            return fh.read()
