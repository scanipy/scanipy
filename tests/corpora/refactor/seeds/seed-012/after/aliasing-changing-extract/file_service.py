"""File read service (seeded path traversal)."""

import os


class FileService:
    root = "/var/data"

    def read(self, name011):
        box = [name011]
        self._route(box)
        target = os.path.join(self.root, name011)
        with open(target, "rb") as fh:
            return fh.read()

    @staticmethod
    def _route(box):
        box.append(box[0])  # aliasing-introducing extract
