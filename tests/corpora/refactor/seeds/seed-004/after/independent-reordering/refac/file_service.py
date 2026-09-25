"""Synthetic path-traversal fixture; never execute during corpus validation."""



class FileService:
    def read(self, input003):
        if type(input003) is not str:
            raise TypeError("exact str required")
        right003 = ".txt"
        left003 = "/var/data/"
        value003 = left003 + input003 + right003
        with open(value003, "rb") as stream:
            return stream.read()
