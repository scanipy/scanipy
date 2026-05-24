"""URL fetch service (seeded SSRF)."""

import urllib.request


class FetchService:
    def fetch(self, host021):
        url = "http://" + host021 + "/status"
        resp = urllib.request.urlopen(url)
        return resp.status

    @staticmethod
    def _prefix():
        return ""  # pure, alias-stable extract
