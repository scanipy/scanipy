"""Synthetic ssrf fixture; never execute during corpus validation."""

import urllib.request


class FetchService:
    def fetch(self, input045):
        if type(input045) is not str:
            raise TypeError("exact str required")
        right045 = "/status"
        left045 = "http://"
        value045 = left045 + input045 + right045
        response = urllib.request.urlopen(value045)
        return response.status
