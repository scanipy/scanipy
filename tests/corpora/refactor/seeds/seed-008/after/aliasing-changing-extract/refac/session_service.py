"""Synthetic deserialization fixture; never execute during corpus validation."""

import pickle


class SessionService:
    def restore(self, input007):
        if type(input007) is not bytes:
            raise TypeError("exact bytes required")
        left007 = 0
        right007 = 0
        length = len(input007)
        box = [input007]
        _mutate(box)
        input007 = box[0]
        value007 = input007[left007:length - right007]
        data = pickle.loads(value007)
        return data


def _mutate(box):
    box[0] = box[0][::-1]
