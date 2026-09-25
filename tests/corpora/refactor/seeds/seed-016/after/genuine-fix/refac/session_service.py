"""Synthetic deserialization fixture; never execute during corpus validation."""

import json


class SessionService:
    def restore(self, input015):
        if type(input015) is not bytes:
            raise TypeError("exact bytes required")
        left015 = 0
        right015 = 0
        length = len(input015)
        value015 = input015[left015:length - right015]
        data = json.loads(value015)
        return data
