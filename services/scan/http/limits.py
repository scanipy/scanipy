"""CMP-ORCH-01 — hard request-body byte ceiling (security-review fix).

The MVP-1 HTTP surface (``services/scan/http/app.py``) has no framework body
model on ANY route — CLAR-DEPLOY-19's C-1 structural form requires the
worker-callback route to read the body raw, once, via ``await
request.body()``, BEFORE its own HMAC gate runs inside ``post_job_status``.
That means nothing upstream of the handler bounds how many bytes an
*unauthenticated* client can make the process buffer: a large POST to
``/api/v1/jobs/{job_id}/status`` with a garbage ``Authorization`` header (no
valid credentials at all) drives full-body buffering and JSON-structural
parsing before the eventual 401/400 rejection — an unauthenticated
memory-exhaustion DoS. ``POST /api/v1/scans`` has the same missing cap
(lower risk today only because ``_authed()`` runs first and the production
JWT verifier is fail-closed — that mitigation disappears the moment Auth0 is
wired).

:class:`MaxBodySizeMiddleware` is a pure-ASGI wrapper (deliberately NOT
``starlette.middleware.base.BaseHTTPMiddleware``, which buffers its own copy
of the body) that caps every request's body BEFORE any route or auth code
observes a byte:

  1. A declared ``Content-Length`` over the cap rejects on the very first
     ``receive()`` call — zero body bytes are ever read off the socket.
  2. A running byte-counter over every subsequent ``receive()`` message
     rejects mid-stream — the backstop for chunked-encoding requests (no
     ``Content-Length`` header at all) or an understated one.

Both paths raise :class:`PayloadTooLargeError` from *inside* the app's own
ASGI call graph — the exception occurs while a downstream ``await
receive()`` (itself inside ``Request.body()`` / ``Request.stream()``) is in
flight, i.e. while Starlette's ``ExceptionMiddleware`` is still on the call
stack — so it propagates through the normal exception-handling chain exactly
like any other route-raised error; ``services/scan/http/app.py`` registers a
handler that maps it to a DOC-API §6 413 envelope.

This middleware performs NO body read of its own: it only wraps the ASGI
``receive`` callable the framework already drives internally. It therefore
does not add a second read on the worker-callback path — the C-1 structural
pin ("exactly one raw ``Request.body()`` read",
``TST-CLAR-DEPLOY-19-C1b``) is untouched, because that test counts calls to
``Request.body()`` itself, not calls to the underlying ASGI ``receive()`` it
drives internally.

Policy gap (report per RULE-4, not invented as a ruling): the exact byte
ceiling is a policy call the CLAR-DEPLOY-19 decision record did not make —
its security-review fix-hint names "1MB for job-status callbacks, a few MB
for scan submissions" as an *example*, not a per-route ruling, and per-route
enforcement would require coupling this ASGI-level middleware to route path
strings duplicated from ``app.py``'s decorators. :data:`DEFAULT_MAX_BODY_BYTES`
is therefore a single conservative uniform ceiling applied to the whole
surface — comfortably above any legitimate MVP-1 body (a ``JobStatusReport``
or ``ScanRequest`` JSON document, both well under 100KB in practice) and a
~40x reduction from the 200MB DoS payload this fix responds to. A follow-up
``CLAR-SLA-*`` should pin the durable numbers (and whether per-route tiers are
wanted), mirroring how ``CLAR-SLA-02`` pinned the interim rate-limit numbers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Uniform interim ceiling across the whole MVP-1 HTTP surface — see the
# "Policy gap" note in the module docstring.
DEFAULT_MAX_BODY_BYTES = 5 * 1024 * 1024  # 5 MiB


class PayloadTooLargeError(Exception):
    """Raised when a request body exceeds the configured byte ceiling."""

    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes
        super().__init__(f"request body exceeds the {max_bytes}-byte ceiling")


def _declared_content_length(scope: Scope) -> int | None:
    """The client-declared byte count, or ``None`` if absent/unparseable.

    ASGI mandates lower-cased header names in ``scope["headers"]`` (a list of
    raw ``(bytes, bytes)`` pairs), so a plain ``b"content-length"`` compare is
    exact — no case-insensitive lookup helper is needed at this layer.
    """
    for name, value in scope.get("headers", ()):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


class MaxBodySizeMiddleware:
    """Pure-ASGI request-body byte ceiling. See module docstring for the
    propagation argument (why this is safe under the C-1 "exactly one raw
    body read" structural pin) and the policy-gap note on the default.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int = DEFAULT_MAX_BODY_BYTES) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        total = 0
        checked_declared = False

        async def limited_receive() -> Message:
            nonlocal total, checked_declared
            if not checked_declared:
                checked_declared = True
                declared = _declared_content_length(scope)
                if declared is not None and declared > self._max_bytes:
                    raise PayloadTooLargeError(self._max_bytes)
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > self._max_bytes:
                    raise PayloadTooLargeError(self._max_bytes)
            return message

        await self._app(scope, limited_receive, send)


__all__ = ["DEFAULT_MAX_BODY_BYTES", "MaxBodySizeMiddleware", "PayloadTooLargeError"]
