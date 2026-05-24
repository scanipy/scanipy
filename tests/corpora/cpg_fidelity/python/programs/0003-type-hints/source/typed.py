"""Type-hint coverage: PEP 484 / 526 annotations (Pyre-friendly territory).

Construct under test: statically-typed receivers so a type-informed front-end can
resolve method dispatch (DOC §4.3 `type-hints`). `process -> Adder.add` is a static
edge because the receiver `acc` is locally constructed with a known class.
"""

from __future__ import annotations


class Adder:
    def __init__(self, base: int) -> None:
        self.base: int = base

    def add(self, delta: int) -> int:
        return self.base + delta


def process(values: list[int]) -> int:
    acc: Adder = Adder(0)
    total: int = 0
    for v in values:
        total = acc.add(v)
    return total
