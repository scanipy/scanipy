"""Synthetic ssrf fixture; never execute during corpus validation."""

import urllib.request


class FetchService:
    def fetch(self, input005):
        if type(input005) is not str:
            raise TypeError("exact str required")
        right005 = "/status"
        left005 = "http://"
        value005 = left005 + input005 + right005
        response = urllib.request.urlopen(value005)
        return response.status
