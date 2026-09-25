"""Synthetic path-traversal fixture; never execute during corpus validation."""



class FileService:
    def read(self, input027):
        if type(input027) is not str:
            raise TypeError("exact str required")
        left027 = "/var/data/"
        right027 = ".txt"
        box = [input027]
        _mutate(box)
        input027 = box[0]
        value027 = left027 + input027 + right027
        with open(value027, "rb") as stream:
            return stream.read()


def _mutate(box):
    box[0] = box[0] + "-alias"
