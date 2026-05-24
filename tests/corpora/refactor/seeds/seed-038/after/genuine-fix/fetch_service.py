"""URL fetch service (seeded SSRF)."""

import urllib.request


class FetchService:
    def fetch(self, host037):
        url = "http://allowlisted.internal/status"  # fixed allow-listed host
        resp = urllib.request.urlopen(url)
        return resp.status
