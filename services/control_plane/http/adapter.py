"""CMP-CP-01 — FastAPI request-lifecycle adapter (CLAR-DEPLOY-19 RESOLVED).

The thin HTTP glue DOC-CMP-CP-01 §3.1 deferred until ``fastapi`` was a pinned
dependency (pyproject extra ``http``, exact pins per CLAR-DEPLOY-19). It wraps
the merged framework-agnostic CP-01 seams — :class:`~services.control_plane
.guard.CPGuard` for authorization and ``db/session.py``'s
``authorize_request_for_binding`` → ``acquire_for_request`` canonical caller
shape for RLS binding — without re-implementing either. Everything here is
component-owned by CP-01; the ORCH-01 routes that *consume* this adapter live
in ``services/scan/http/`` (component boundaries per CLAUDE.md §12).

Surfaces:

  * :class:`JWTVerifierPort` — the ``validate_jwt`` layer of §3.1 as a typed
    port. Real Auth0 JWKS verification is explicitly OUT OF SCOPE here (no
    verifier exists in-tree; ``CPGuard.authorize_request`` takes claims as
    input) — :func:`fail_closed_jwt_verifier` is the production default and
    raises until the Auth0-JWKS follow-up lands, mirroring the
    ``services/scan/api.py`` ``fail_closed_*`` seam pattern.
  * :func:`request_trace_id` / :func:`envelope_response` — DOC-API §3.3 trace
    propagation + the §6 error envelope mapping.
  * :func:`authenticate` — Authorization header → verified
    :class:`AuthedRequest` (or a fail-closed :class:`ErrorEnvelope`).
  * :func:`bound_request` — the db/session.py canonical authorize-FIRST caller
    shape: the route authorizes via ``authorize_request_for_binding`` and only
    then enters this context manager, so a denied request never opens a
    transaction (DOC-CMP-CP-01 §3.1 "Order is normative").

Provenance / RULE-6: CP-01 is a non-emitting component (no findings rows are
written here); the adapter's threading duty is the tenant binding only, exactly
as ``db/session.py`` documents.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable
from uuid import uuid4

from db.session import Connection, acquire_for_request, request_binding_args
from fastapi.responses import JSONResponse

from services.control_plane.guard import ErrorEnvelope, JWTClaims

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from contextlib import AbstractContextManager

    from fastapi import Request

# DOC-API §3.3 / CLAR-DEPLOY-07: the response trace header equals the OTel
# trace id; requests may supply it (support-portal correlation) or the server
# mints one. Header names are case-insensitive (starlette normalises).
TRACE_ID_HEADER = "X-Scanipy-Trace-Id"


@runtime_checkable
class JWTVerifierPort(Protocol):
    """The §3.1 ``validate_jwt`` layer as a typed port (Auth0 JWKS deferred).

    ``verify`` receives the raw ``Authorization`` header value (``None`` when
    absent) and returns validated :class:`JWTClaims` on success or a typed
    :class:`ErrorEnvelope` (normally ``401 unauthenticated``) on any failure —
    fail-closed: an unverifiable token is never passed through as claims.
    """

    def verify(self, authorization: str | None, *, trace_id: str) -> JWTClaims | ErrorEnvelope: ...


class _FailClosedJWTVerifier:
    """Prod JWT verifier: raises until the Auth0-JWKS follow-up is wired."""

    def verify(self, authorization: str | None, *, trace_id: str) -> JWTClaims | ErrorEnvelope:
        raise NotImplementedError(
            "JWT verification is gated (CMP-CP-01 build-ahead, CLAR-DEPLOY-19): "
            "the Auth0 JWKS verifier (CLAR-DEPLOY-10 IdP; CP-04/deploy lane) is "
            "not yet in-tree. Inject a JWTVerifierPort via create_app(..., "
            "jwt_verifier=...) in a hermetic test."
        )


def fail_closed_jwt_verifier() -> JWTVerifierPort:
    """Default JWT verifier: fail-closed until the Auth0 JWKS verifier lands."""
    return _FailClosedJWTVerifier()


def request_trace_id(request: Request) -> str:
    """The request's trace id (DOC-API §3.3): supplied header or a minted one.

    Reads ``X-Scanipy-Trace-Id`` (starlette header lookup is case-insensitive);
    when absent, mints ``uuid4().hex`` so every error envelope and log line has
    a non-empty correlation hook.
    """
    supplied = request.headers.get(TRACE_ID_HEADER)
    if supplied:
        return supplied
    return uuid4().hex


def envelope_response(envelope: ErrorEnvelope) -> JSONResponse:
    """Map an :class:`ErrorEnvelope` onto the DOC-API §6 error response.

    Body is the §6 shape ``{error_code, message, trace_id, details}``; the HTTP
    status is the §6.1 reserved-table value the envelope itself derives
    (``ErrorEnvelope.http_status``).
    """
    return JSONResponse(
        status_code=envelope.http_status,
        content={
            "error_code": envelope.error_code,
            "message": envelope.message,
            "trace_id": envelope.trace_id,
            "details": envelope.details,
        },
    )


@dataclass(frozen=True)
class AuthedRequest:
    """The authenticated request context the routes thread to the core.

    ``headers`` is a plain dict projection of the request headers (starlette
    lower-cases names; the guard's header lookup is case-insensitive), so the
    framework-agnostic core never sees an ASGI type.
    """

    claims: JWTClaims
    headers: dict[str, str]
    trace_id: str


def authenticate(request: Request, verifier: JWTVerifierPort) -> AuthedRequest | ErrorEnvelope:
    """Verify the request's JWT via the port — fail-closed.

    Returns an :class:`AuthedRequest` when the verifier yields claims, else the
    verifier's :class:`ErrorEnvelope` (the route maps it via
    :func:`envelope_response` and never reaches authorization or binding).
    """
    trace_id = request_trace_id(request)
    result = verifier.verify(request.headers.get("Authorization"), trace_id=trace_id)
    if isinstance(result, ErrorEnvelope):
        return result
    return AuthedRequest(claims=result, headers=dict(request.headers), trace_id=trace_id)


@contextmanager
def bound_request(
    connection_factory: Callable[[], AbstractContextManager[Connection]] | None,
    claims: JWTClaims,
) -> Iterator[Connection | None]:
    """Per-request RLS binding — db/session.py's canonical caller shape.

    The route calls this ONLY after ``authorize_request_for_binding`` returned
    ``None`` (authorize FIRST — a denied request never opens a transaction;
    the docstring contract in ``db/session.py``). Two modes:

      * ``connection_factory is None`` (MVP-1): yields ``None``. No RDS is
        deployed yet; :class:`~services.scan.api.OrgScopedScanStore` is the
        tenant-isolation layer, and there is no connection to bind.
      * factory supplied: checks out a connection and binds it for exactly one
        request via ``acquire_for_request(conn, **request_binding_args(claims))``
        — SET LOCAL scoping, commit on clean exit, rollback + re-raise on any
        error (the transaction lifecycle db/session.py owns).
    """
    if connection_factory is None:
        yield None
        return
    with connection_factory() as conn:
        # request_binding_args is the single (org_id, user_id, role) projection
        # so authorization and binding can never drift onto different tenants.
        # It is typed dict[str, str] for adapter ergonomics; acquire_for_request
        # narrows `role` itself (same targeted-ignore precedent as db/session.py
        # threading `resource` into the guard).
        with acquire_for_request(conn, **request_binding_args(claims)) as bound:  # type: ignore[arg-type]
            yield bound


__all__ = [
    "TRACE_ID_HEADER",
    "AuthedRequest",
    "JWTVerifierPort",
    "authenticate",
    "bound_request",
    "envelope_response",
    "fail_closed_jwt_verifier",
    "request_trace_id",
]
