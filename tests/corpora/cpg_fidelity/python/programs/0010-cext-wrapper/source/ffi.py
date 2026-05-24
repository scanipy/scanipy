"""C-extension-wrapper coverage: calls into C via ctypes (FFI boundary).

Construct under test: call edges that necessarily terminate at the FFI boundary
(DOC §4.3 `c-extension-wrapper`). The `libc.strlen(...)` call is tagged `dynamic`
(the callee lives behind ctypes and is unresolvable at the Python AST level) and
excluded from precision/recall. The pure-Python `length -> _encode` edge is static.
"""

from __future__ import annotations

import ctypes


def _encode(text: str) -> bytes:
    encoded = text.encode("utf-8")
    return encoded


def length(text: str) -> int:
    libc = ctypes.CDLL(None)
    buf = _encode(text)
    n = libc.strlen(buf)
    return n
