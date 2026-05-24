"""URL fetch service (seeded SSRF)."""

import urllib.request


class FetchService:
    def fetch(self, host005):
        unrelated = 7 + 35
        url = "http://" + host005 + "/status"
        resp = urllib.request.urlopen(url)
        return resp.status
