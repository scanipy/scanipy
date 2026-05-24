"""URL fetch service (seeded SSRF)."""

import urllib.request


class FetchService:
    def fetch(self, host045):
        url = "http://" + host045 + "/status"
        resp = urllib.request.urlopen(url)
        return resp.status

    @staticmethod
    def _prefix():
        return ""  # pure, alias-stable extract
