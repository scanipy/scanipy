"""Synthetic path-traversal fixture; never execute during corpus validation."""



class FileService:
    def read(self, input003):
        if type(input003) is not str:
            raise TypeError("exact str required")
        left003 = "/var/data/"
        right003 = ".txt"
        box = [input003]
        _mutate(box)
        input003 = box[0]
        value003 = left003 + input003 + right003
        with open(value003, "rb") as stream:
            return stream.read()


def _mutate(box):
    box[0] = box[0] + "-alias"
