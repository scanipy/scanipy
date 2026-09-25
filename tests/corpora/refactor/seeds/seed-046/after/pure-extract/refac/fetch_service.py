"""Synthetic ssrf fixture; never execute during corpus validation."""

import urllib.request


class FetchService:
    def fetch(self, input045):
        if type(input045) is not str:
            raise TypeError("exact str required")
        left045 = "http://"
        right045 = "/status"
        value045 = _extracted_value(left045, input045, right045)
        response = urllib.request.urlopen(value045)
        return response.status


def _extracted_value(left045, input045, right045):
    return left045 + input045 + right045
