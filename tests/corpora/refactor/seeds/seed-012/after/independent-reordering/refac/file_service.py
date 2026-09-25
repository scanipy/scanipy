"""Synthetic path-traversal fixture; never execute during corpus validation."""



class FileService:
    def read(self, input011):
        if type(input011) is not str:
            raise TypeError("exact str required")
        right011 = ".txt"
        left011 = "/var/data/"
        value011 = left011 + input011 + right011
        with open(value011, "rb") as stream:
            return stream.read()
