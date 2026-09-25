"""Synthetic deserialization fixture; never execute during corpus validation."""

import json


class SessionService:
    def restore(self, input047):
        if type(input047) is not bytes:
            raise TypeError("exact bytes required")
        left047 = 0
        right047 = 0
        length = len(input047)
        value047 = input047[left047:length - right047]
        data = json.loads(value047)
        return data
