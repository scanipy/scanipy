"""CMP-ORCH-01 — FastAPI app factory over the framework-agnostic handler core.

CLAR-DEPLOY-19 RESOLVED: this is the HTTP glue ``services/scan/api.py`` deferred
(its module docstring names this exact follow-up). Every route composes the
CP-01 request-lifecycle adapter (``services/control_plane/http/adapter.py``)
with the already-merged core handlers; NO detection, validation, or provenance
logic lives here.

NORMATIVE ORDER per authenticated route (DOC-CMP-CP-01 §3.1 / db/session.py):
``authenticate`` → ``authorize_request_for_binding`` → non-None envelope
short-circuits BEFORE ``bound_request`` opens any transaction → the core
handler runs tenant-bound (and re-authorizes internally — defense-in-depth,
deliberately kept).

C-1 STRUCTURAL FORM (binding, ORCH-01 security co-sign): the worker-callback
route declares NO framework body parameter (no pydantic model, ever — framework
body parsing would be an independent read path); it performs exactly one
``await request.body()``; the HMAC is verified over THOSE bytes by
``verify_worker_callback_hmac`` inside ``post_job_status``; and the
handler-visible report is derived as ``parse_job_status_report(body_bytes)`` on
the SAME local variable — ``body == parse(body_bytes)`` is unrepresentable to
get wrong. ``tests/unit/test_deploy19_http_adapter.py`` pins the form.

RULE-6 note: ORCH-01 emits jobs, not findings — the four finding-level
provenance fields are stamped downstream (CMP-ORCH-03 / CMP-FND-01..03); this
surface threads ``S_version`` + ``env_digest`` through the core it wraps.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from uuid import UUID

from db.session import authorize_request_for_binding
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from services.control_plane.guard import ErrorEnvelope, TenantIsolationError
from services.control_plane.http.adapter import (
    authenticate,
    bound_request,
    envelope_response,
    request_trace_id,
)
from services.scan.api import (
    AuthorizationError,
    InvalidHmacError,
    InvalidInputError,
    ScanApiError,
    get_scan,
    get_scan_findings,
    post_job_status,
    post_scans,
)
from services.scan.http.serde import (
    parse_job_status_report,
    parse_scan_request,
    scan_created_json,
    scan_record_json,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager

    from db.session import Connection

    from detectors.registry import DetectorRegistry
    from services.control_plane.guard import CPGuard
    from services.control_plane.http.adapter import AuthedRequest, JWTVerifierPort
    from services.scan.api import (
        HmacKeyIssuer,
        JobStateStore,
        ScanStore,
        SnapshotPort,
        SpecRegistryPort,
    )
    from services.substrate.queue import StandardQueue


def _error_json(error_code: str, message: str, trace_id: str, *, status: int) -> JSONResponse:
    """A DOC-API §6 envelope response for a code that carries its own status.

    ``ScanApiError`` statuses are authoritative on the error instance (e.g.
    ``not_found`` is 409 on ``DetectorUnknownError`` per DOC-CMP-ORCH-01 §3.4
    but 404 on ``ScanNotFoundError``), so this bypasses the §6.1-table lookup
    that :func:`envelope_response` performs for guard envelopes.
    """
    return JSONResponse(
        status_code=status,
        content={
            "error_code": error_code,
            "message": message,
            "trace_id": trace_id,
            "details": None,
        },
    )


def create_app(
    *,
    guard: CPGuard,
    registry: DetectorRegistry,
    scan_store: ScanStore,
    queue: StandardQueue,
    jwt_verifier: JWTVerifierPort,
    key_issuer: HmacKeyIssuer,
    job_state_store: JobStateStore,
    spec_registry: SpecRegistryPort | None = None,
    snapshot_port: SnapshotPort | None = None,
    connection_factory: Callable[[], AbstractContextManager[Connection]] | None = None,
    now: Callable[[], int] = lambda: int(time.time()),
) -> FastAPI:
    """Build the MVP-1 scan-API app with every collaborator injected (DI).

    All ports arrive through kwargs — tests inject the hermetic fakes through
    THIS seam, never by patching the prod path. ``connection_factory=None`` is
    the MVP-1 mode (no RDS; ``OrgScopedScanStore`` is the isolation layer and
    ``bound_request`` yields ``None``); ``now`` is injected so the HMAC skew
    window is deterministic in tests.
    """
    app = FastAPI(title="Scanipy v3.2 scan API", version="3.2.0")

    # -- request-lifecycle helpers (CP-01 adapter composition) -----------------

    def _authed(request: Request, *, method: str, resource: str, route: str) -> AuthedRequest:
        """authenticate → authorize; raise the envelope BEFORE any binding."""
        authed = authenticate(request, jwt_verifier)
        if isinstance(authed, ErrorEnvelope):
            raise AuthorizationError(authed)
        envelope = authorize_request_for_binding(
            guard,
            authed.claims,
            authed.headers,
            method=method,
            resource=resource,
            route=route,
            trace_id=authed.trace_id,
        )
        if envelope is not None:
            # Short-circuit: a denied request never reaches bound_request, so
            # no transaction is ever opened for it (db/session.py contract).
            raise AuthorizationError(envelope)
        return authed

    def _idempotency_key(request: Request) -> UUID:
        """DOC-API §3.4: the Idempotency-Key header is required and a UUID."""
        raw = request.headers.get("Idempotency-Key")
        if raw is None:
            raise InvalidInputError("Idempotency-Key header is required (DOC-API §3.4)")
        try:
            return UUID(raw)
        except ValueError as exc:
            raise InvalidInputError("Idempotency-Key header must be a UUID") from exc

    def _worker_timestamp(request: Request) -> int:
        """Parse X-Scanipy-Job-Timestamp — malformation fails closed as 401."""
        raw = request.headers.get("X-Scanipy-Job-Timestamp", "")
        try:
            return int(raw)
        except ValueError:
            raise InvalidHmacError("missing or malformed X-Scanipy-Job-Timestamp header") from None

    # -- routes -----------------------------------------------------------------

    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        """ECS/ALB health probe: static body, NO auth, NO tenant data, NO DB.

        Registered outside the auth path by construction — it never calls
        ``authenticate``/``authorize_request_for_binding``/``bound_request``.
        """
        return JSONResponse(status_code=200, content={"status": "ok"})

    @app.post("/api/v1/scans")
    async def post_scans_route(request: Request) -> JSONResponse:
        """POST /api/v1/scans (DOC-API §4.1): 201, or 200 on idempotency replay.

        The body is parsed by ``serde.parse_scan_request`` — deliberately NOT a
        pydantic model, so the framework-agnostic core stays the single
        validation authority (CLAR-DEPLOY-19 rejected-alternative).
        """
        authed = _authed(request, method="POST", resource="scans", route="/api/v1/scans")
        idempotency_key = _idempotency_key(request)
        scan_req = parse_scan_request(await request.body())
        with bound_request(connection_factory, authed.claims):
            created = post_scans(
                scan_req,
                authed.claims,
                authed.headers,
                idempotency_key=idempotency_key,
                trace_id=authed.trace_id,
                guard=guard,
                registry=registry,
                scan_store=scan_store,
                queue=queue,
                spec_registry=spec_registry,
                snapshot_port=snapshot_port,
                hmac_key_issuer=key_issuer,
            )
        # 200-vs-201: job_ids == () iff idempotency replay (detector_ids is
        # non-empty, so a fresh scan always fans ≥ 1 job). scan_created_json
        # re-checks the inference (the CLAR-DEPLOY-19 risk-note tripwire).
        replay = created.job_ids == ()
        return JSONResponse(
            status_code=200 if replay else 201,
            content=scan_created_json(created, replay=replay),
        )

    @app.get("/api/v1/scans/{scan_id}")
    async def get_scan_route(scan_id: UUID, request: Request) -> JSONResponse:
        """GET /api/v1/scans/{scan_id}: the thin RLS-bound record (CLAR-ORCH-07)."""
        authed = _authed(request, method="GET", resource="scans", route="/api/v1/scans/{scan_id}")
        with bound_request(connection_factory, authed.claims):
            record = get_scan(
                scan_id,
                authed.claims,
                authed.headers,
                trace_id=authed.trace_id,
                guard=guard,
                scan_store=scan_store,
            )
        return JSONResponse(status_code=200, content=scan_record_json(record))

    @app.get("/api/v1/scans/{scan_id}/findings")
    async def get_scan_findings_route(scan_id: UUID, request: Request) -> JSONResponse:
        """GET …/findings: thin record until the jobs-table + FND-01 wiring wave.

        The CLAR-ORCH-07 deviation stands: the full SARIF page needs persisted
        findings rows; authorization + the cross-org 404 are the load-bearing
        security legs and ARE live here.
        """
        authed = _authed(
            request,
            method="GET",
            resource="findings",
            route="/api/v1/scans/{scan_id}/findings",
        )
        with bound_request(connection_factory, authed.claims):
            record = get_scan_findings(
                scan_id,
                authed.claims,
                authed.headers,
                trace_id=authed.trace_id,
                guard=guard,
                scan_store=scan_store,
            )
        return JSONResponse(status_code=200, content=scan_record_json(record))

    @app.post("/api/v1/jobs/{job_id}/status", status_code=204)
    async def post_job_status_route(job_id: UUID, request: Request) -> Response:
        """POST /api/v1/jobs/{job_id}/status — HMAC-only worker callback (§4.5).

        C-1 STRUCTURAL FORM (binding — do not refactor):
          * NO framework body parameter on this function (no pydantic, ever);
          * exactly ONE ``await request.body()`` — the line below is the only
            body read on the callback path;
          * the HMAC is verified over those exact bytes (post_job_status →
            verify_worker_callback_hmac(body_bytes=...));
          * the handler-visible report is parse_job_status_report(body_bytes)
            on the SAME local — body == parse(body_bytes) by construction.

        NO CP-01 tenancy guard here (DOC-API §2.5): worker callbacks carry no
        X-Scanipy-Org-Id — tenant identity is implicit in the HMAC-keyed job.
        The C-2 job-state transition happens inside ``post_job_status``, only
        after HMAC verification + the INV-2 fence pass.
        """
        body_bytes = await request.body()
        report = parse_job_status_report(body_bytes)
        post_job_status(
            job_id,
            report,
            body_bytes,
            hmac_header=request.headers.get("Authorization", ""),
            worker_id_header=request.headers.get("X-Scanipy-Worker-Id", ""),
            timestamp_header=_worker_timestamp(request),
            key_issuer=key_issuer,
            scan_store=scan_store,
            job_state_store=job_state_store,
            now=now,
        )
        return Response(status_code=204)

    # -- DOC-API §6 envelope mapping (every envelope carries the trace_id) ------

    def _authorization_error_handler(request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, AuthorizationError)  # registered for this type
        return envelope_response(exc.envelope)

    def _scan_api_error_handler(request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, ScanApiError)  # registered for this type
        return _error_json(
            exc.error_code, exc.message, request_trace_id(request), status=exc.http_status
        )

    def _tenant_isolation_handler(request: Request, exc: Exception) -> JSONResponse:
        # The layer-3 RLS backstop fired (a CP-01 bug, never control flow):
        # surface 403 tenant_isolation_violation, never an unscoped result.
        return envelope_response(guard.isolation_error_envelope(request_trace_id(request)))

    def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
        # Path-param coercion failures (e.g. a non-UUID scan_id). DOC-API §6.1:
        # schema validation failures are 400 invalid_input (not FastAPI's 422).
        return _error_json(
            "invalid_input", "request validation failed", request_trace_id(request), status=400
        )

    def _internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        # Fallback: never leak internals; trace_id is the recovery hook (§6.1).
        return _error_json(
            "internal_error", "unhandled server error", request_trace_id(request), status=500
        )

    app.add_exception_handler(AuthorizationError, _authorization_error_handler)
    app.add_exception_handler(ScanApiError, _scan_api_error_handler)
    app.add_exception_handler(TenantIsolationError, _tenant_isolation_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _internal_error_handler)

    return app


__all__ = ["create_app"]
