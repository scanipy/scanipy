"""Synthetic ssrf fixture; never execute during corpus validation."""

import urllib.request


class FetchService:
    def fetch(self, input037):
        if type(input037) is not str:
            raise TypeError("exact str required")
        left037 = "http://"
        right037 = "/status"
        value037 = "https://example.invalid/status"
        response = urllib.request.urlopen(value037)
        return response.status
