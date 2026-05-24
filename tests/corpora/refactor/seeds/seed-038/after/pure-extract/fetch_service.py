"""URL fetch service (seeded SSRF)."""

import urllib.request


class FetchService:
    def fetch(self, host037):
        url = "http://" + host037 + "/status"
        resp = urllib.request.urlopen(url)
        return resp.status

    @staticmethod
    def _prefix():
        return ""  # pure, alias-stable extract
