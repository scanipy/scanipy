"""Synthetic deserialization fixture; never execute during corpus validation."""

import pickle


class SessionService:
    def restore(self, input031):
        if type(input031) is not bytes:
            raise TypeError("exact bytes required")
        left031 = 0
        right031 = 0
        length = len(input031)
        value031 = _extracted_value(input031, left031, length, right031)
        data = pickle.loads(value031)
        return data


def _extracted_value(input031, left031, length, right031):
    return input031[left031:length - right031]
