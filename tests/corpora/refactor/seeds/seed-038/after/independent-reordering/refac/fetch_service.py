"""Synthetic ssrf fixture; never execute during corpus validation."""

import urllib.request


class FetchService:
    def fetch(self, input037):
        if type(input037) is not str:
            raise TypeError("exact str required")
        right037 = "/status"
        left037 = "http://"
        value037 = left037 + input037 + right037
        response = urllib.request.urlopen(value037)
        return response.status
