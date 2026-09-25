"""Synthetic ssrf fixture; never execute during corpus validation."""

import urllib.request


class FetchService:
    def fetch(self, renamed0):
        if type(renamed0) is not str:
            raise TypeError("exact str required")
        renamed1 = "http://"
        renamed2 = "/status"
        renamed3 = _extracted_value(renamed1, renamed0, renamed2)
        response = urllib.request.urlopen(renamed3)
        return response.status


def _extracted_value(renamed1, renamed0, renamed2):
    return renamed1 + renamed0 + renamed2
