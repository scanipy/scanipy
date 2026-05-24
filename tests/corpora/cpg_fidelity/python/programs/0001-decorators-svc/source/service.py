"""Decorator coverage: functions wrapped via functools.wraps.

Construct under test: call-graph edge correctness through a decorator that
preserves the wrapped target's identity (DOC-CMP-CORP-CPG-python §4.3 `decorators`).
The static call edge `handle -> validate` must survive the `@trace` wrapper.
"""

from __future__ import annotations

import functools


def trace(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        result = fn(*args, **kwargs)
        return result

    return wrapper


def validate(value: int) -> int:
    checked = value + 1
    return checked


@trace
def handle(payload: int) -> int:
    cleaned = validate(payload)
    return cleaned


def main() -> int:
    out = handle(41)
    return out
