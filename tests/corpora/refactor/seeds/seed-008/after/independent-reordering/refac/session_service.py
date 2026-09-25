"""Synthetic deserialization fixture; never execute during corpus validation."""

import pickle


class SessionService:
    def restore(self, input007):
        if type(input007) is not bytes:
            raise TypeError("exact bytes required")
        right007 = 0
        left007 = 0
        length = len(input007)
        value007 = input007[left007:length - right007]
        data = pickle.loads(value007)
        return data
