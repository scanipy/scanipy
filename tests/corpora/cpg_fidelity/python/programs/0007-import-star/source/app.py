"""Import-star coverage: `from x import *` name-resolution edge cases.

Construct under test: wildcard import (DOC §4.3 `import-star`). Names brought in by
`from helpers import *` are not lexically visible to a single-file analyzer, so the
`helper(...)` call here is tagged `dynamic` (cross-module, unresolved by this
extractor's intra-file static resolution) and excluded from precision/recall.
"""

from helpers import *  # noqa: F401,F403


def use(value):
    return helper(value)  # noqa: F405
