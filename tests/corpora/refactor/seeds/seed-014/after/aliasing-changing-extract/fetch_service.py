"""URL fetch service (seeded SSRF)."""

import urllib.request


class FetchService:
    def fetch(self, host013):
        box = [host013]
        self._route(box)
        url = "http://" + host013 + "/status"
        resp = urllib.request.urlopen(url)
        return resp.status

    @staticmethod
    def _route(box):
        box.append(box[0])  # aliasing-introducing extract
