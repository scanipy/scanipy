"""Synthetic ssrf fixture; never execute during corpus validation."""

import urllib.request


class FetchService:
    def fetch(self, input021):
        if type(input021) is not str:
            raise TypeError("exact str required")
        left021 = "http://"
        right021 = "/status"
        value021 = "https://example.invalid/status"
        response = urllib.request.urlopen(value021)
        return response.status
