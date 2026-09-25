"""Synthetic ssrf fixture; never execute during corpus validation."""

import urllib.request


class FetchService:
    def fetch(self, input029):
        if type(input029) is not str:
            raise TypeError("exact str required")
        left029 = "http://"
        right029 = "/status"
        value029 = "https://example.invalid/status"
        response = urllib.request.urlopen(value029)
        return response.status
