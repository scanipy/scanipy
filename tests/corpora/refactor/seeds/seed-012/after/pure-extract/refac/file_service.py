"""Synthetic path-traversal fixture; never execute during corpus validation."""



class FileService:
    def read(self, input011):
        if type(input011) is not str:
            raise TypeError("exact str required")
        left011 = "/var/data/"
        right011 = ".txt"
        value011 = _extracted_value(left011, input011, right011)
        with open(value011, "rb") as stream:
            return stream.read()


def _extracted_value(left011, input011, right011):
    return left011 + input011 + right011
