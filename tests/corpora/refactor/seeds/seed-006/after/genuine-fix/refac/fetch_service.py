"""Synthetic ssrf fixture; never execute during corpus validation."""

import urllib.request


class FetchService:
    def fetch(self, input005):
        if type(input005) is not str:
            raise TypeError("exact str required")
        left005 = "http://"
        right005 = "/status"
        value005 = "https://example.invalid/status"
        response = urllib.request.urlopen(value005)
        return response.status
