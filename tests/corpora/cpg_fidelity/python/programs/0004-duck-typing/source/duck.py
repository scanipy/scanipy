"""Duck-typing coverage: no type hints; assignment-based resolution only.

Construct under test: tests assignment-based call resolution without static type
signals (DOC §4.3 `duck-typing-callsite`). `consume -> Reader.read` is a static
edge resolvable from the local construction `r = Reader()`. The parameter-driven
`obj.read()` call is `dynamic` (receiver type unknown) and excluded from metrics.
"""


class Reader:
    def read(self):
        return 1


def consume():
    r = Reader()
    return r.read()


def consume_unknown(obj):
    return obj.read()
