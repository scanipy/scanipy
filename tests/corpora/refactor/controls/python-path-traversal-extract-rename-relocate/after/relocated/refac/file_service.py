"""Synthetic path-traversal fixture; never execute during corpus validation."""



class FileService:
    def read(self, renamed0):
        if type(renamed0) is not str:
            raise TypeError("exact str required")
        renamed1 = "/var/data/"
        renamed2 = ".txt"
        renamed3 = _extracted_value(renamed1, renamed0, renamed2)
        with open(renamed3, "rb") as stream:
            return stream.read()


def _extracted_value(renamed1, renamed0, renamed2):
    return renamed1 + renamed0 + renamed2
