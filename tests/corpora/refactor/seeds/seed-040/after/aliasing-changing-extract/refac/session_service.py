"""Synthetic deserialization fixture; never execute during corpus validation."""

import pickle


class SessionService:
    def restore(self, input039):
        if type(input039) is not bytes:
            raise TypeError("exact bytes required")
        left039 = 0
        right039 = 0
        length = len(input039)
        box = [input039]
        _mutate(box)
        input039 = box[0]
        value039 = input039[left039:length - right039]
        data = pickle.loads(value039)
        return data


def _mutate(box):
    box[0] = box[0][::-1]
