"""Synthetic ssrf fixture; never execute during corpus validation."""

import urllib.request


class FetchService:
    def fetch(self, input045):
        if type(input045) is not str:
            raise TypeError("exact str required")
        left045 = "http://"
        right045 = "/status"
        value045 = "https://example.invalid/status"
        response = urllib.request.urlopen(value045)
        return response.status
