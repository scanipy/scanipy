"""Synthetic path-traversal fixture; never execute during corpus validation."""



class FileService:
    def read(self, input019):
        if type(input019) is not str:
            raise TypeError("exact str required")
        left019 = "/var/data/"
        right019 = ".txt"
        value019 = _extracted_value(left019, input019, right019)
        with open(value019, "rb") as stream:
            return stream.read()


def _extracted_value(left019, input019, right019):
    return left019 + input019 + right019
