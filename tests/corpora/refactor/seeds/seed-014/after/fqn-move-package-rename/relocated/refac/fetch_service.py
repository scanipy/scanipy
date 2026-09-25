"""Synthetic ssrf fixture; never execute during corpus validation."""

import urllib.request


class FetchService:
    def fetch(self, input013):
        if type(input013) is not str:
            raise TypeError("exact str required")
        left013 = "http://"
        right013 = "/status"
        value013 = left013 + input013 + right013
        response = urllib.request.urlopen(value013)
        return response.status
