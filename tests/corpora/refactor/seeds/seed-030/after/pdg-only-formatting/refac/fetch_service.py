# formatting only

"""Synthetic ssrf fixture; never execute during corpus validation."""



import urllib.request





class FetchService:

    def fetch(self, input029):

        if type(input029) is not str:

            raise TypeError("exact str required")

        left029 = "http://"

        right029 = "/status"

        value029 = left029 + input029 + right029

        response = urllib.request.urlopen(value029)

        return response.status
