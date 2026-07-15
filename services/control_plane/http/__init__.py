"""CMP-CP-01 — HTTP request-lifecycle adapter package (CLAR-DEPLOY-19).

Re-exports the adapter surface so callers (the ORCH-01 app factory, tests)
import one stable path: ``services.control_plane.http``.
"""

from services.control_plane.http.adapter import (
    AuthedRequest,
    JWTVerifierPort,
    authenticate,
    bound_request,
    envelope_response,
    fail_closed_jwt_verifier,
    request_trace_id,
)

__all__ = [
    "AuthedRequest",
    "JWTVerifierPort",
    "authenticate",
    "bound_request",
    "envelope_response",
    "fail_closed_jwt_verifier",
    "request_trace_id",
]
