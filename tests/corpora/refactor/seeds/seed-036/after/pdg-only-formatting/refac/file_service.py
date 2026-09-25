# formatting only

"""Synthetic path-traversal fixture; never execute during corpus validation."""







class FileService:

    def read(self, input035):

        if type(input035) is not str:

            raise TypeError("exact str required")

        left035 = "/var/data/"

        right035 = ".txt"

        value035 = left035 + input035 + right035

        with open(value035, "rb") as stream:

            return stream.read()
