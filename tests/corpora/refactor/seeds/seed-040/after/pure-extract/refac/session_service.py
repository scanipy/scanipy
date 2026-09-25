"""Synthetic deserialization fixture; never execute during corpus validation."""

import pickle


class SessionService:
    def restore(self, input039):
        if type(input039) is not bytes:
            raise TypeError("exact bytes required")
        left039 = 0
        right039 = 0
        length = len(input039)
        value039 = _extracted_value(input039, left039, length, right039)
        data = pickle.loads(value039)
        return data


def _extracted_value(input039, left039, length, right039):
    return input039[left039:length - right039]
