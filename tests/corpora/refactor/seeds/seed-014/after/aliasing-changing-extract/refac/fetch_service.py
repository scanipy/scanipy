"""Synthetic ssrf fixture; never execute during corpus validation."""

import urllib.request


class FetchService:
    def fetch(self, input013):
        if type(input013) is not str:
            raise TypeError("exact str required")
        left013 = "http://"
        right013 = "/status"
        box = [input013]
        _mutate(box)
        input013 = box[0]
        value013 = left013 + input013 + right013
        response = urllib.request.urlopen(value013)
        return response.status


def _mutate(box):
    box[0] = box[0] + "-alias"
