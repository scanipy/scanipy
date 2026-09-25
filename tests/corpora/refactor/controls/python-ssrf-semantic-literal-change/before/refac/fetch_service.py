"""Synthetic ssrf fixture; never execute during corpus validation."""

import urllib.request


class FetchService:
    def fetch(self, input005):
        if type(input005) is not str:
            raise TypeError("exact str required")
        left005 = "http://"
        right005 = "/status"
        value005 = left005 + input005 + right005
        response = urllib.request.urlopen(value005)
        return response.status
