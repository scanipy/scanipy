"""Async/await coverage: CFG correctness across coroutine suspension points.

Construct under test: `async def` / `await` (DOC §4.3 `async-await`). The CFG of
`run` must thread control through the `await fetch(...)` and the `async for` loop.
"""

from __future__ import annotations


async def fetch(item: int) -> int:
    doubled = item * 2
    return doubled


async def gen(n: int):
    i = 0
    while i < n:
        yield i
        i = i + 1


async def run(n: int) -> int:
    total = 0
    async for value in gen(n):
        partial = await fetch(value)
        total = total + partial
    return total
