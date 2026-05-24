"""URL fetch service (seeded SSRF)."""

import urllib.request


class FetchService:
    def fetch(self, renamed0):
        url = "http://" + renamed0 + "/status"
        resp = urllib.request.urlopen(url)
        return resp.status
