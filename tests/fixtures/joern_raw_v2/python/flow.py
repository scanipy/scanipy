"""Static-parser input only. This file is never imported or executed."""


def helper(left, right="suffix"):
    combined = left + ":" + right
    return combined


def variadic(first, *rest, **named):
    return first + rest[0] + named["suffix"]


class Flow:
    def __init__(self, cursor):
        self.cursor = cursor
        self.saved = ""

    def instance(self, value):
        self.saved = value
        return helper(value, right=self.saved)

    def caller(self, user_input, values, named):
        first = helper(user_input, values[0])
        second = helper(right=first, left=user_input)
        third = helper(second)
        self.cursor.execute(self.instance(third))
        return self.cursor.fetchall()

    def splat(self, values, named):
        return variadic("prefix", *values, **named)


def unknown(target, value):
    return target(value)
