"""Synthetic deserialization fixture; never execute during corpus validation."""

import pickle


class SessionService:
    def restore(self, input015):
        if type(input015) is not bytes:
            raise TypeError("exact bytes required")
        left015 = 0
        right015 = 0
        length = len(input015)
        box = [input015]
        _mutate(box)
        input015 = box[0]
        value015 = input015[left015:length - right015]
        data = pickle.loads(value015)
        return data


def _mutate(box):
    box[0] = box[0][::-1]
