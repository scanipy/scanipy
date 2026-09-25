"""Synthetic path-traversal fixture; never execute during corpus validation."""



class FileService:
    def read(self, input043):
        if type(input043) is not str:
            raise TypeError("exact str required")
        left043 = "/var/data/"
        right043 = ".txt"
        value043 = "/var/data/public.txt"
        with open(value043, "rb") as stream:
            return stream.read()
