"""Synthetic path-traversal fixture; never execute during corpus validation."""



class FileService:
    def read(self, input003):
        if type(input003) is not str:
            raise TypeError("exact str required")
        left003 = "/var/data/"
        right003 = ".txt"
        value003 = "/var/data/public.txt"
        with open(value003, "rb") as stream:
            return stream.read()
