"""Synthetic path-traversal fixture; never execute during corpus validation."""



class FileService:
    def read(self, input027):
        if type(input027) is not str:
            raise TypeError("exact str required")
        right027 = ".txt"
        left027 = "/var/data/"
        value027 = left027 + input027 + right027
        with open(value027, "rb") as stream:
            return stream.read()
