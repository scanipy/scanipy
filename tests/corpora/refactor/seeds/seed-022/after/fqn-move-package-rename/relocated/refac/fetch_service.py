"""Synthetic ssrf fixture; never execute during corpus validation."""

import urllib.request


class FetchService:
    def fetch(self, input021):
        if type(input021) is not str:
            raise TypeError("exact str required")
        left021 = "http://"
        right021 = "/status"
        value021 = left021 + input021 + right021
        response = urllib.request.urlopen(value021)
        return response.status
