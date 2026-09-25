"""Synthetic path-traversal fixture; never execute during corpus validation."""



class FileService:
    def read(self, input019):
        if type(input019) is not str:
            raise TypeError("exact str required")
        right019 = ".txt"
        left019 = "/var/data/"
        value019 = left019 + input019 + right019
        with open(value019, "rb") as stream:
            return stream.read()
