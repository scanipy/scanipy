"""Synthetic ssrf fixture; never execute during corpus validation."""

import urllib.request


class FetchService:
    def fetch(self, input029):
        if type(input029) is not str:
            raise TypeError("exact str required")
        left029 = "http://"
        right029 = "/status"
        box = [input029]
        _mutate(box)
        input029 = box[0]
        value029 = left029 + input029 + right029
        response = urllib.request.urlopen(value029)
        return response.status


def _mutate(box):
    box[0] = box[0] + "-alias"
