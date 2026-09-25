# formatting only

"""Synthetic deserialization fixture; never execute during corpus validation."""



import pickle





class SessionService:

    def restore(self, input023):

        if type(input023) is not bytes:

            raise TypeError("exact bytes required")

        left023 = 0

        right023 = 0

        length = len(input023)

        value023 = input023[left023:length - right023]

        data = pickle.loads(value023)

        return data
