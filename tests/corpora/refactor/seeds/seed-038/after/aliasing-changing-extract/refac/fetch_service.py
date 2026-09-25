"""Synthetic ssrf fixture; never execute during corpus validation."""

import urllib.request


class FetchService:
    def fetch(self, input037):
        if type(input037) is not str:
            raise TypeError("exact str required")
        left037 = "http://"
        right037 = "/status"
        box = [input037]
        _mutate(box)
        input037 = box[0]
        value037 = left037 + input037 + right037
        response = urllib.request.urlopen(value037)
        return response.status


def _mutate(box):
    box[0] = box[0] + "-alias"
