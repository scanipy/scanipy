"""Synthetic path-traversal fixture; never execute during corpus validation."""



class FileService:
    def read(self, input019):
        if type(input019) is not str:
            raise TypeError("exact str required")
        left019 = "/var/data/"
        right019 = ".txt"
        box = [input019]
        _mutate(box)
        input019 = box[0]
        value019 = left019 + input019 + right019
        with open(value019, "rb") as stream:
            return stream.read()


def _mutate(box):
    box[0] = box[0] + "-alias"
