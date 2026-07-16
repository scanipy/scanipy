"""Unit tests for ``services/scan/http/limits.py`` — ``MaxBodySizeMiddleware``.

ASGI-level (no real HTTP, no event-loop framework beyond ``asyncio.run`` — the
repo has no ``pytest-asyncio`` dependency, so tests drive the coroutines
directly rather than declaring ``async def test_*``, which pytest would
otherwise silently collect as a passing-but-never-awaited coroutine). See
``tests/unit/test_deploy19_http_adapter.py`` for the end-to-end wiring tests
(the 413 envelope shape, the exception-handler registration, the
worker-callback pre-auth ordering) via the real FastAPI app.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from services.scan.http.limits import (
    DEFAULT_MAX_BODY_BYTES,
    MaxBodySizeMiddleware,
    PayloadTooLargeError,
)

Scope = dict[str, Any]
Message = dict[str, Any]


def _http_scope(*, content_length: int | None) -> Scope:
    headers: list[tuple[bytes, bytes]] = []
    if content_length is not None:
        headers.append((b"content-length", str(content_length).encode()))
    return {"type": "http", "headers": headers}


async def _unreachable_send(message: Message) -> None:
    raise AssertionError("send should never be invoked in these tests")


@pytest.mark.unit
def test_declared_content_length_over_cap_rejects_before_any_real_receive() -> None:
    """A ``Content-Length`` over the cap raises on the wrapped receive's FIRST
    call — the underlying ("real") receive is never invoked, so zero body
    bytes are ever pulled off the socket for an oversized declared body."""
    real_receive_calls = 0

    async def real_receive() -> Message:
        nonlocal real_receive_calls
        real_receive_calls += 1
        return {"type": "http.request", "body": b"should never be read", "more_body": False}

    outcome: dict[str, object] = {}

    async def downstream_app(scope: Scope, receive: Any, send: Any) -> None:
        try:
            await receive()
        except PayloadTooLargeError as exc:
            outcome["raised"] = exc
        else:
            outcome["raised"] = None

    async def run() -> None:
        middleware = MaxBodySizeMiddleware(downstream_app, max_bytes=10)
        await middleware(_http_scope(content_length=1_000_000), real_receive, _unreachable_send)

    asyncio.run(run())

    assert isinstance(outcome["raised"], PayloadTooLargeError)
    assert outcome["raised"].max_bytes == 10  # type: ignore[union-attr]
    assert real_receive_calls == 0, "an oversized declared body must reject before any real read"


@pytest.mark.unit
def test_streaming_body_without_content_length_capped_mid_stream() -> None:
    """No ``Content-Length`` header at all (the chunked-encoding shape) — the
    running byte-counter backstop still rejects once cumulative body bytes
    cross the cap, mid-stream."""
    chunks = [b"a" * 6, b"b" * 6]  # 6 then 12 cumulative bytes; cap = 10
    chunk_iter = iter(chunks)

    async def real_receive() -> Message:
        try:
            chunk = next(chunk_iter)
            return {"type": "http.request", "body": chunk, "more_body": True}
        except StopIteration:
            return {"type": "http.request", "body": b"", "more_body": False}

    received: list[bytes] = []
    outcome: dict[str, object] = {}

    async def downstream_app(scope: Scope, receive: Any, send: Any) -> None:
        try:
            while True:
                message = await receive()
                received.append(message["body"])
        except PayloadTooLargeError as exc:
            outcome["raised"] = exc

    async def run() -> None:
        middleware = MaxBodySizeMiddleware(downstream_app, max_bytes=10)
        await middleware(_http_scope(content_length=None), real_receive, _unreachable_send)

    asyncio.run(run())

    assert isinstance(outcome["raised"], PayloadTooLargeError)
    assert outcome["raised"].max_bytes == 10  # type: ignore[union-attr]
    # the first (6-byte) chunk is under the cap and passed through untouched;
    # the second crosses it (12 > 10) and raises instead of ever returning.
    assert received == [b"a" * 6]


@pytest.mark.unit
def test_body_within_cap_passes_through_untouched() -> None:
    """A body under the cap is delivered to the downstream app unmodified —
    no false positive on legitimate small traffic."""
    messages = [
        {"type": "http.request", "body": b"hello ", "more_body": True},
        {"type": "http.request", "body": b"world", "more_body": False},
    ]
    message_iter = iter(messages)

    async def real_receive() -> Message:
        return next(message_iter)

    received: list[bytes] = []

    async def downstream_app(scope: Scope, receive: Any, send: Any) -> None:
        received.append((await receive())["body"])
        received.append((await receive())["body"])

    async def run() -> None:
        middleware = MaxBodySizeMiddleware(downstream_app, max_bytes=DEFAULT_MAX_BODY_BYTES)
        await middleware(_http_scope(content_length=11), real_receive, _unreachable_send)

    asyncio.run(run())

    assert received == [b"hello ", b"world"]


@pytest.mark.unit
def test_unparseable_content_length_falls_back_to_streaming_counter() -> None:
    """A malformed ``Content-Length`` header (non-integer) is treated as
    absent — no early rejection off a value that cannot be trusted — and the
    running byte-counter backstop still governs."""

    async def real_receive() -> Message:
        return {"type": "http.request", "body": b"ok", "more_body": False}

    received: list[bytes] = []

    async def downstream_app(scope: Scope, receive: Any, send: Any) -> None:
        received.append((await receive())["body"])

    async def run() -> None:
        middleware = MaxBodySizeMiddleware(downstream_app, max_bytes=DEFAULT_MAX_BODY_BYTES)
        scope: Scope = {"type": "http", "headers": [(b"content-length", b"not-a-number")]}
        await middleware(scope, real_receive, _unreachable_send)

    asyncio.run(run())

    assert received == [b"ok"], "a garbage Content-Length must not crash the request"


@pytest.mark.unit
def test_non_http_scope_passes_through_with_unwrapped_receive() -> None:
    """Lifespan/websocket scopes bypass the wrapper entirely — the downstream
    app receives the ORIGINAL ``receive`` callable, not a wrapped one."""

    async def real_receive() -> Message:
        return {"type": "lifespan.startup"}

    captured: dict[str, object] = {}

    async def downstream_app(scope: Scope, receive: Any, send: Any) -> None:
        captured["receive"] = receive

    async def run() -> None:
        middleware = MaxBodySizeMiddleware(downstream_app, max_bytes=10)
        await middleware({"type": "lifespan"}, real_receive, _unreachable_send)

    asyncio.run(run())

    assert captured["receive"] is real_receive


@pytest.mark.unit
def test_default_cap_is_five_mebibytes() -> None:
    """Pins the default so a future accidental edit is a visible test failure,
    not a silent DoS-surface regression."""
    assert DEFAULT_MAX_BODY_BYTES == 5 * 1024 * 1024
