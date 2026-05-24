"""File read service (seeded path traversal)."""

import os


class FileService:
    root = "/var/data"

    def read(self, name027):
        box = [name027]
        self._route(box)
        target = os.path.join(self.root, name027)
        with open(target, "rb") as fh:
            return fh.read()

    @staticmethod
    def _route(box):
        box.append(box[0])  # aliasing-introducing extract
