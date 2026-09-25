"""Synthetic path-traversal fixture; never execute during corpus validation."""



class FileService:
    def read(self, input011):
        if type(input011) is not str:
            raise TypeError("exact str required")
        left011 = "/var/data/"
        right011 = ".txt"
        box = [input011]
        _mutate(box)
        input011 = box[0]
        value011 = left011 + input011 + right011
        with open(value011, "rb") as stream:
            return stream.read()


def _mutate(box):
    box[0] = box[0] + "-alias"
