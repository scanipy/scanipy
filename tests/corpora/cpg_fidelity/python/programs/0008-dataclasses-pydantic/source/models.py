"""Dataclass coverage: auto-generated __init__ / synthetic methods.

Construct under test: `@dataclass` synthesizes `__init__`/`__eq__` that have no
source statements (DOC §4.3 `dataclasses-pydantic`). A faithful front-end must
recover the construction call `build -> Point` without tripping on the synthetic
methods. (Pydantic is namechecked by the tag; this uses stdlib `dataclasses` to
keep the program dependency-free and the ground truth auditable.)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Point:
    x: int
    y: int

    def norm(self) -> int:
        return self.x * self.x + self.y * self.y


def build(a: int, b: int) -> Point:
    p = Point(a, b)
    magnitude = p.norm()
    return magnitude
