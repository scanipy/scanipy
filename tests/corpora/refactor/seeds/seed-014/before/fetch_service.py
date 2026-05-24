"""URL fetch service (seeded SSRF)."""

import urllib.request


class FetchService:
    def fetch(self, host013):
        url = "http://" + host013 + "/status"
        resp = urllib.request.urlopen(url)
        return resp.status
