# moved to scanipy.corpus.relocated
"""URL fetch service (seeded SSRF)."""

import urllib.request


class FetchService:
    def fetch(self, host005):
        url = "http://" + host005 + "/status"
        resp = urllib.request.urlopen(url)
        return resp.status
