"""Dynamic-dispatch coverage: getattr / dict-of-functions / runtime targets.

Construct under test: call sites whose target is not statically fixed (DOC §4.3
`dynamic-dispatch`). Every call site here is tagged `dynamic` by the extractor and
EXCLUDED from precision/recall; `CMP-SNAP-03 CW-DETECT` is their owner. `op` IS a
static edge (direct local call) to anchor the static partition.
"""


def add(a, b):
    return a + b


def sub(a, b):
    return a - b


def op(a, b):
    return add(a, b)


TABLE = {"add": add, "sub": sub}


def dispatch_by_name(name, a, b):
    fn = TABLE[name]
    return fn(a, b)


def dispatch_getattr(module_like, name, value):
    handler = getattr(module_like, name)
    return handler(value)
