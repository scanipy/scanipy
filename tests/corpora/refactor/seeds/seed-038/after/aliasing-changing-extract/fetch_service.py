"""URL fetch service (seeded SSRF)."""

import urllib.request


class FetchService:
    def fetch(self, host037):
        box = [host037]
        self._route(box)
        url = "http://" + host037 + "/status"
        resp = urllib.request.urlopen(url)
        return resp.status

    @staticmethod
    def _route(box):
        box.append(box[0])  # aliasing-introducing extract
