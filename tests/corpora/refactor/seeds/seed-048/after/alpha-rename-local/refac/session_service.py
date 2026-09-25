"""Synthetic deserialization fixture; never execute during corpus validation."""

import pickle


class SessionService:
    def restore(self, renamed0):
        if type(renamed0) is not bytes:
            raise TypeError("exact bytes required")
        renamed1 = 0
        renamed2 = 0
        length = len(renamed0)
        renamed3 = renamed0[renamed1:length - renamed2]
        data = pickle.loads(renamed3)
        return data
