"""Synthetic path-traversal fixture; never execute during corpus validation."""



class FileService:
    def read(self, input011):
        if type(input011) is not str:
            raise TypeError("exact str required")
        left011 = "/var/data/"
        right011 = ".txt"
        value011 = "/var/data/public.txt"
        with open(value011, "rb") as stream:
            return stream.read()
