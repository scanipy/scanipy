# ruff: noqa: N803
#   ``S_version`` keeps its capital S throughout (normative provenance field name,
#   INV-2), matching ``services/scan/api.py`` / ``tests/orch01_fakes.py``.
"""CLAR-DEPLOY-19 — HTTP adapter security co-sign + MVP-1 stack specs.

Covers the CLAR-DEPLOY-19 implementation contract's TESTS section:

  * C-1 (signed-bytes structural contract): TST-CLAR-DEPLOY-19-C1a/b/c.
  * C-2 (job-state replay idempotency): TST-CLAR-DEPLOY-19-C2a/b/c/d.
  * The MVP-1 stack legs (auth, RBAC, idempotency, cross-org, trace-id,
    authorize-then-bind-then-commit ordering).

``fastapi.testclient.TestClient`` drives ``create_app`` end-to-end; every
collaborator (JWT verifier, HMAC key issuer, job-state store, snapshot port,
spec registry, DB-API connection) is a hermetic in-memory double injected
through ``create_app``'s typed DI kwargs — the fail-closed production seams
(``fail_closed_jwt_verifier`` et al.) are never reached from this file.
"""

from __future__ import annotations

import hashlib
import hmac as hmac_module
import json
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from detectors.registry import DetectorRegistry
from services.control_plane.guard import CPGuard, ErrorEnvelope, JWTClaims
from services.scan.api import (
    InMemoryJobStateStore,
    JobStatusReport,
    OrgScopedScanStore,
    TransitionOutcome,
    canonical_request,
)
from services.scan.http.app import create_app
from services.substrate.queue import StandardQueue
from tests.orch01_fakes import (
    FAKE_ENV_DIGEST,
    ORG_A,
    ORG_B,
    FakeHmacKeyIssuer,
    FakeSnapshotPort,
    FakeSpecRegistry,
    claims_for,
    done_report,
    headers_for,
    sign_callback,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from contextlib import AbstractContextManager

    from db.session import Connection

    from services.control_plane.http.adapter import JWTVerifierPort
    from services.scan.api import JobStateStore

# ---------------------------------------------------------------------------
# Hermetic doubles local to this file (CP-01 / job-state spy — not shared with
# tests/orch01_fakes.py, which is ORCH-01-scoped and has no JWT verifier).
# ---------------------------------------------------------------------------


@dataclass
class FakeJWTVerifier:
    """A :class:`JWTVerifierPort` double: registered bearer tokens → claims.

    Any missing / unrecognised ``Authorization`` header fails closed with a
    ``401 unauthenticated`` envelope — mirrors the real fail-closed default's
    posture without raising (a hermetic test needs a *working* verifier for
    its positive legs).
    """

    _tokens: dict[str, JWTClaims] = field(default_factory=dict)

    def register(self, token: str, claims: JWTClaims) -> None:
        self._tokens[token] = claims

    def verify(self, authorization: str | None, *, trace_id: str) -> JWTClaims | ErrorEnvelope:
        prefix = "Bearer "
        if authorization is None or not authorization.startswith(prefix):
            return ErrorEnvelope(
                error_code="unauthenticated", message="missing bearer token", trace_id=trace_id
            )
        claims = self._tokens.get(authorization[len(prefix) :])
        if claims is None:
            return ErrorEnvelope(
                error_code="unauthenticated", message="unknown bearer token", trace_id=trace_id
            )
        return claims


@dataclass
class SpyJobStateStore:
    """Wraps a real :class:`JobStateStore` and records every ``transition`` call.

    ``calls`` carries the outcome too, so C-2 tests can assert BOTH "was the
    store even reached" (C-1c/C-2c: it must not be, on a rejected callback) and
    "what outcome did it record" (C-2a/d: exactly one ``applied`` among N
    replays) without reaching into the wrapped store's private state.
    """

    inner: JobStateStore = field(default_factory=InMemoryJobStateStore)
    calls: list[dict[str, object]] = field(default_factory=list)

    def transition(self, *, job_id: UUID, status: str, body_sha256: str) -> TransitionOutcome:
        outcome = self.inner.transition(job_id=job_id, status=status, body_sha256=body_sha256)  # type: ignore[arg-type]
        self.calls.append(
            {"job_id": job_id, "status": status, "body_sha256": body_sha256, "outcome": outcome}
        )
        return outcome


@dataclass
class _FakeCursor:
    """Minimal DB-API 2.0 cursor double: records ``execute``/``close`` onto the
    connection's shared log (``db/session.py``'s ``Connection``/``Cursor``
    protocols)."""

    log: list[tuple[object, ...]]

    def execute(self, sql: str, params: tuple[str, ...] = ()) -> object:
        self.log.append(("execute", sql, params))
        return None

    def close(self) -> None:
        self.log.append(("close",))


@dataclass
class _FakeConnection:
    """Minimal DB-API 2.0 connection double satisfying ``db/session.Connection``.

    Every ``cursor()``/``commit()``/``rollback()`` call appends to ``log`` in
    order, so a test can assert the exact authorize→bind→commit/rollback
    sequence ``acquire_for_request`` (``db/session.py``) drives.
    """

    log: list[tuple[object, ...]] = field(default_factory=list)
    autocommit: bool = False

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self.log)

    def commit(self) -> None:
        self.log.append(("commit",))

    def rollback(self) -> None:
        self.log.append(("rollback",))


def _connection_factory(
    conn: _FakeConnection,
) -> Callable[[], AbstractContextManager[Connection]]:
    """A zero-arg ``create_app(connection_factory=...)`` returning ``conn``."""

    @contextmanager
    def factory() -> Iterator[_FakeConnection]:
        yield conn

    return factory  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# App-construction + body-encoding helpers
# ---------------------------------------------------------------------------


def _registry() -> DetectorRegistry:
    reg = DetectorRegistry()
    reg.load_manifests("detectors/")
    return reg


def _shipped_ids(reg: DetectorRegistry) -> tuple[str, ...]:
    return tuple(sorted(d.id for d in reg.all()))


def _build_app(
    *,
    verifier: JWTVerifierPort,
    job_state_store: JobStateStore | None = None,
    connection_factory: Callable[[], AbstractContextManager[Connection]] | None = None,
    now: Callable[[], int] = lambda: 1_000_000,
    hmac_key_issuer: FakeHmacKeyIssuer | None = None,
    registry: DetectorRegistry | None = None,
    max_body_bytes: int | None = None,
) -> tuple[TestClient, DetectorRegistry, OrgScopedScanStore, StandardQueue, FakeHmacKeyIssuer]:
    """Build a hermetic MVP-1 app: every port is an in-memory double, injected
    through ``create_app``'s DI seam — never the fail-closed prod path.

    ``max_body_bytes`` overrides ``MaxBodySizeMiddleware``'s ceiling (default
    ``None`` uses ``create_app``'s own default) — injectable so the 413 tests
    can probe the boundary without constructing multi-megabyte payloads.
    """
    reg = registry if registry is not None else _registry()
    store = OrgScopedScanStore()
    queue = StandardQueue(name="scan-jobs")
    issuer = hmac_key_issuer if hmac_key_issuer is not None else FakeHmacKeyIssuer()
    kwargs: dict[str, object] = {}
    if max_body_bytes is not None:
        kwargs["max_body_bytes"] = max_body_bytes
    app = create_app(
        guard=CPGuard(),
        registry=reg,
        scan_store=store,
        queue=queue,
        jwt_verifier=verifier,
        key_issuer=issuer,
        job_state_store=job_state_store if job_state_store is not None else InMemoryJobStateStore(),
        spec_registry=FakeSpecRegistry(),
        snapshot_port=FakeSnapshotPort(),
        connection_factory=connection_factory,
        now=now,
        **kwargs,  # type: ignore[arg-type]
    )
    client = TestClient(app)
    return client, reg, store, queue, issuer


def _scan_body_bytes(
    detector_ids: tuple[str, ...],
    *,
    S_version: str = "2.7.0",
    codebase_id: UUID | None = None,
    commit_sha: str | None = None,
) -> bytes:
    payload = {
        "codebase_id": str(codebase_id or UUID(int=7)),
        "commit_sha": commit_sha or ("a" * 40),
        "detector_ids": list(detector_ids),
        "S_version": S_version,
    }
    return json.dumps(payload).encode("utf-8")


def _callback_headers(
    header: str, *, worker_id: str = "worker-1", timestamp: int = 1000, trace_id: str | None = None
) -> dict[str, str]:
    headers = {
        "Authorization": header,
        "X-Scanipy-Worker-Id": worker_id,
        "X-Scanipy-Job-Timestamp": str(timestamp),
    }
    if trace_id is not None:
        headers["X-Scanipy-Trace-Id"] = trace_id
    return headers


def _post_callback(
    client: TestClient, job_id: UUID, body_bytes: bytes, header: str, *, timestamp: int = 1000
) -> object:
    return client.post(
        f"/api/v1/jobs/{job_id}/status",
        content=body_bytes,
        headers=_callback_headers(header, timestamp=timestamp),
    )


def _sign_raw(
    *, job_id: UUID, worker_id: str, timestamp: int, body_bytes: bytes, key_id: str, secret: bytes
) -> str:
    """Sign arbitrary ``body_bytes`` directly (bypassing ``sign_callback``'s own
    fixed sorted-compact serialisation) — needed for the C-1a non-canonical-
    formatting probe below."""
    message = canonical_request(
        method="POST",
        path=f"/api/v1/jobs/{job_id}/status",
        worker_id=worker_id,
        body_bytes=body_bytes,
        timestamp=timestamp,
    )
    digest = hmac_module.new(secret, message, hashlib.sha256).hexdigest()
    return f"HMAC {key_id}:{digest}"


def _pretty_unsorted_report_bytes(*, job_id: UUID, scan_id: UUID, status: str = "done") -> bytes:
    """A syntactically-valid but deliberately NON-canonical wire body: unsorted
    keys + multi-line indentation. If the adapter re-serialised the parsed
    report before hashing/verifying (the documented canonicalisation-drift
    hazard) instead of using the raw wire bytes, THIS shape would diverge from
    whatever canonical form the re-serialisation produced."""
    payload = {
        "status": status,
        "job_id": str(job_id),
        "env_digest": FAKE_ENV_DIGEST,
        "scan_id": str(scan_id),
        "S_version": "2.7.0",
    }
    return json.dumps(payload, indent=2, sort_keys=False).encode("utf-8")


def _tamper_env_digest_byte(body_bytes: bytes) -> bytes:
    """Flip exactly one byte inside the ``env_digest`` value (the C-1c mutation):
    keeps the JSON syntactically valid (still a quoted string of the same
    length) so the request reaches HMAC verification rather than failing parse
    first."""
    text = body_bytes.decode("utf-8")
    idx = text.find(FAKE_ENV_DIGEST)
    assert idx != -1, "test premise: FAKE_ENV_DIGEST present in the signed body"
    flip_at = idx + len(FAKE_ENV_DIGEST) - 1  # the last hex char, a 'b'
    assert text[flip_at] == "b"
    tampered = text[:flip_at] + "c" + text[flip_at + 1 :]
    assert tampered != text
    return tampered.encode("utf-8")


# ---------------------------------------------------------------------------
# C-1 — signed-bytes structural contract
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_c1a_hmac_and_store_share_exact_wire_bytes_no_reserialization() -> None:
    """TST-CLAR-DEPLOY-19-C1a: the JobStateStore records ``sha256(body_bytes)``
    over the EXACT wire bytes sent, and the transition's ``status`` matches
    what was on the wire — i.e. ``body == parse(body_bytes)`` end-to-end.

    Signs a deliberately NON-canonically-formatted body (unsorted keys, pretty
    whitespace, via ``_sign_raw`` — bypassing the test helper's own fixed
    serialisation). If the adapter re-serialised the parsed report before
    verifying or before recording (the documented "canonicalisation drift"
    hazard — see ``canonical_request``'s docstring), this signature would be
    computed over bytes DIFFERENT from what was actually sent, and the
    callback would spuriously reject.
    """
    verifier = FakeJWTVerifier()
    issuer = FakeHmacKeyIssuer()
    spy = SpyJobStateStore()
    client, *_ = _build_app(
        verifier=verifier, job_state_store=spy, hmac_key_issuer=issuer, now=lambda: 1000
    )

    job_id, scan_id = uuid4(), uuid4()
    key_id, secret = issuer.issue(job_id=job_id, scan_id=scan_id)
    body_bytes = _pretty_unsorted_report_bytes(job_id=job_id, scan_id=scan_id, status="done")
    header = _sign_raw(
        job_id=job_id,
        worker_id="worker-1",
        timestamp=1000,
        body_bytes=body_bytes,
        key_id=key_id,
        secret=secret,
    )

    resp = _post_callback(client, job_id, body_bytes, header, timestamp=1000)
    assert resp.status_code == 204, resp.text  # type: ignore[attr-defined]

    assert len(spy.calls) == 1, "the non-canonically-formatted callback must still verify"
    call = spy.calls[0]
    assert call["job_id"] == job_id
    assert call["status"] == "done"
    assert call["body_sha256"] == hashlib.sha256(body_bytes).hexdigest()


@pytest.mark.unit
def test_c1b_exactly_one_raw_body_read_per_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    """TST-CLAR-DEPLOY-19-C1b: exactly one ``await request.body()`` per callback.

    Wraps ``starlette.requests.Request.body`` with a counting spy (an ASGI-level
    hook, applied class-wide but observed per request instance via ``id(self)``)
    and asserts the callback route reads the raw body exactly once — the C-1
    structural form (no framework body param, no independent re-read).
    """
    import starlette.requests as starlette_requests

    read_counts: dict[int, int] = {}
    original_body = starlette_requests.Request.body

    async def _counting_body(self: object) -> bytes:
        read_counts[id(self)] = read_counts.get(id(self), 0) + 1
        return await original_body(self)  # type: ignore[arg-type]

    monkeypatch.setattr(starlette_requests.Request, "body", _counting_body)

    verifier = FakeJWTVerifier()
    issuer = FakeHmacKeyIssuer()
    client, *_ = _build_app(verifier=verifier, hmac_key_issuer=issuer, now=lambda: 1000)

    job_id, scan_id = uuid4(), uuid4()
    key_id, secret = issuer.issue(job_id=job_id, scan_id=scan_id)
    body = done_report(job_id, scan_id)
    header, body_bytes = sign_callback(
        job_id=job_id, worker_id="worker-1", timestamp=1000, body=body, key_id=key_id, secret=secret
    )

    resp = _post_callback(client, job_id, body_bytes, header, timestamp=1000)
    assert resp.status_code == 204  # type: ignore[attr-defined]

    assert list(read_counts.values()) == [1], (
        f"expected exactly one raw Request.body() read for the callback request; saw {read_counts}"
    )


@pytest.mark.unit
def test_c1c_tampered_body_after_signing_401_and_store_never_reached() -> None:
    """TST-CLAR-DEPLOY-19-C1c: flipping one body byte after signing → 401
    invalid_hmac, and the JobStateStore is NEVER reached (no independent
    re-read can resurrect a tampered request into a durable transition).
    """
    verifier = FakeJWTVerifier()
    issuer = FakeHmacKeyIssuer()
    spy = SpyJobStateStore()
    client, *_ = _build_app(
        verifier=verifier, job_state_store=spy, hmac_key_issuer=issuer, now=lambda: 1000
    )

    job_id, scan_id = uuid4(), uuid4()
    key_id, secret = issuer.issue(job_id=job_id, scan_id=scan_id)
    body = done_report(job_id, scan_id)
    header, body_bytes = sign_callback(
        job_id=job_id, worker_id="worker-1", timestamp=1000, body=body, key_id=key_id, secret=secret
    )

    tampered_bytes = _tamper_env_digest_byte(body_bytes)
    assert tampered_bytes != body_bytes and len(tampered_bytes) == len(body_bytes)

    resp = _post_callback(client, job_id, tampered_bytes, header, timestamp=1000)
    assert resp.status_code == 401  # type: ignore[attr-defined]
    assert resp.json()["error_code"] == "invalid_hmac"  # type: ignore[attr-defined]
    assert spy.calls == [], "a tampered callback must never reach the JobStateStore"


# ---------------------------------------------------------------------------
# Security-review fixes (post-merge, CLAR-DEPLOY-19 lane): MaxBodySizeMiddleware
# end-to-end wiring + the RecursionError→400 serde fix. Unit-level coverage of
# MaxBodySizeMiddleware itself (ASGI-level, no HTTP) lives in
# tests/unit/test_scan_http_body_size_limit.py.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_oversized_callback_body_413_before_any_auth_no_store_write() -> None:
    """A callback body over the ceiling is rejected 413 — even with a garbage
    ``Authorization`` header carrying no valid credentials at all — because
    ``MaxBodySizeMiddleware`` runs BEFORE the route's own body read, ahead of
    the HMAC gate inside ``post_job_status`` (DOC-API §2.5: this route has no
    CP-01 tenancy/auth check ahead of the body read either). The JobStateStore
    is never reached, exactly like a tampered/forged callback (C-1c/C-2c)."""
    verifier = FakeJWTVerifier()
    issuer = FakeHmacKeyIssuer()
    spy = SpyJobStateStore()
    client, *_ = _build_app(
        verifier=verifier,
        job_state_store=spy,
        hmac_key_issuer=issuer,
        now=lambda: 1000,
        max_body_bytes=64,
    )

    job_id = uuid4()
    oversized_body = json.dumps({"padding": "x" * 500}).encode("utf-8")
    assert len(oversized_body) > 64

    resp = _post_callback(
        client, job_id, oversized_body, "Bearer not-even-hmac-shaped", timestamp=1000
    )
    assert resp.status_code == 413  # type: ignore[attr-defined]
    assert resp.json()["error_code"] == "payload_too_large"  # type: ignore[attr-defined]
    assert spy.calls == [], "an oversized callback must never reach the JobStateStore"


@pytest.mark.unit
def test_oversized_authenticated_scan_submission_413() -> None:
    """An AUTHENTICATED, AUTHORIZED ``POST /api/v1/scans`` body over the
    ceiling is still rejected 413 — the cap protects authenticated callers
    too, not just the pre-auth worker-callback route."""
    verifier = FakeJWTVerifier()
    verifier.register("token-a", claims_for(ORG_A))
    client, reg, *_ = _build_app(verifier=verifier, max_body_bytes=64)
    ids = _shipped_ids(reg)
    headers = {
        **headers_for(ORG_A),
        "Authorization": "Bearer token-a",
        "Idempotency-Key": str(uuid4()),
    }
    oversized_body = _scan_body_bytes(ids * 20)  # padded well past the 64-byte cap
    assert len(oversized_body) > 64

    resp = client.post("/api/v1/scans", content=oversized_body, headers=headers)
    assert resp.status_code == 413
    assert resp.json()["error_code"] == "payload_too_large"


@pytest.mark.unit
def test_body_within_ceiling_unaffected() -> None:
    """A body comfortably under the ceiling is unaffected — the cap does not
    false-positive on legitimate small traffic."""
    verifier = FakeJWTVerifier()
    issuer = FakeHmacKeyIssuer()
    client, *_ = _build_app(
        verifier=verifier, hmac_key_issuer=issuer, now=lambda: 1000, max_body_bytes=512
    )
    job_id, scan_id = uuid4(), uuid4()
    key_id, secret = issuer.issue(job_id=job_id, scan_id=scan_id)
    body = done_report(job_id, scan_id)
    header, body_bytes = sign_callback(
        job_id=job_id, worker_id="worker-1", timestamp=1000, body=body, key_id=key_id, secret=secret
    )
    assert len(body_bytes) <= 512, "test premise: this report fits under the injected cap"

    resp = _post_callback(client, job_id, body_bytes, header, timestamp=1000)
    assert resp.status_code == 204  # type: ignore[attr-defined]


@pytest.mark.unit
def test_deeply_nested_json_callback_body_400_not_500() -> None:
    """A pathologically deep JSON body (blows the interpreter's recursion
    limit inside ``json.loads``) must map to 400 invalid_input — the
    ``_load_json_object`` contract ("ANY malformation -> 400") — not fall
    through to the generic-exception 500 handler. Runs with NO valid
    credentials to also confirm parsing (and its failure mode) happens
    before/independent of the HMAC gate, per the route's own read order."""
    verifier = FakeJWTVerifier()
    issuer = FakeHmacKeyIssuer()
    spy = SpyJobStateStore()
    client, *_ = _build_app(
        verifier=verifier,
        job_state_store=spy,
        hmac_key_issuer=issuer,
        now=lambda: 1000,
        # a deep-nesting attack payload is tiny in bytes; keep the size cap at
        # its default so only the recursion-depth path is under test here.
    )

    job_id = uuid4()
    depth = sys.getrecursionlimit() + 500
    deeply_nested = (b"[" * depth) + (b"]" * depth)

    resp = _post_callback(client, job_id, deeply_nested, "Bearer garbage", timestamp=1000)
    assert resp.status_code == 400, resp.text  # type: ignore[attr-defined]
    assert resp.json()["error_code"] == "invalid_input"  # type: ignore[attr-defined]
    assert spy.calls == [], "a malformed callback must never reach the JobStateStore"


# ---------------------------------------------------------------------------
# C-2 — job-state replay idempotency
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_c2a_byte_identical_done_replay_204_twice_one_applied_transition() -> None:
    """TST-CLAR-DEPLOY-19-C2a: a byte-identical, validly-signed ``done`` replayed
    within the 300s window → 204 both times, exactly ONE ``applied`` transition
    (DOC-API §4.5 no-op semantics)."""
    verifier = FakeJWTVerifier()
    issuer = FakeHmacKeyIssuer()
    spy = SpyJobStateStore()
    client, *_ = _build_app(
        verifier=verifier, job_state_store=spy, hmac_key_issuer=issuer, now=lambda: 1000
    )

    job_id, scan_id = uuid4(), uuid4()
    key_id, secret = issuer.issue(job_id=job_id, scan_id=scan_id)
    body = done_report(job_id, scan_id)
    header, body_bytes = sign_callback(
        job_id=job_id, worker_id="worker-1", timestamp=1000, body=body, key_id=key_id, secret=secret
    )

    r1 = _post_callback(client, job_id, body_bytes, header, timestamp=1000)
    r2 = _post_callback(client, job_id, body_bytes, header, timestamp=1000)
    assert r1.status_code == 204  # type: ignore[attr-defined]
    assert r2.status_code == 204  # type: ignore[attr-defined]

    outcomes = [c["outcome"] for c in spy.calls]
    assert outcomes == ["applied", "duplicate"]
    assert sum(1 for o in outcomes if o == "applied") == 1


@pytest.mark.unit
def test_c2b_done_then_failed_409_conflict_store_still_holds_done() -> None:
    """TST-CLAR-DEPLOY-19-C2b: valid ``done`` then valid ``failed`` for the same
    ``job_id`` → 409 conflicting_status_transition; the store still holds
    ``done`` (never silently overwritten to the conflicting status)."""
    verifier = FakeJWTVerifier()
    issuer = FakeHmacKeyIssuer()
    store = InMemoryJobStateStore()
    client, *_ = _build_app(
        verifier=verifier, job_state_store=store, hmac_key_issuer=issuer, now=lambda: 1000
    )

    job_id, scan_id = uuid4(), uuid4()
    key_id, secret = issuer.issue(job_id=job_id, scan_id=scan_id)

    done_body = done_report(job_id, scan_id)
    done_header, done_bytes = sign_callback(
        job_id=job_id,
        worker_id="worker-1",
        timestamp=1000,
        body=done_body,
        key_id=key_id,
        secret=secret,
    )
    r1 = _post_callback(client, job_id, done_bytes, done_header, timestamp=1000)
    assert r1.status_code == 204  # type: ignore[attr-defined]

    failed_body = JobStatusReport(
        job_id=job_id,
        scan_id=scan_id,
        status="failed",
        S_version="2.7.0",
        env_digest=FAKE_ENV_DIGEST,
    )
    failed_header, failed_bytes = sign_callback(
        job_id=job_id,
        worker_id="worker-1",
        timestamp=1001,
        body=failed_body,
        key_id=key_id,
        secret=secret,
    )
    r2 = _post_callback(client, job_id, failed_bytes, failed_header, timestamp=1001)
    assert r2.status_code == 409  # type: ignore[attr-defined]
    assert r2.json()["error_code"] == "conflicting_status_transition"  # type: ignore[attr-defined]

    # The store still holds "done": replaying "done" is a no-op ("duplicate"),
    # which is only possible if the prior recorded status is still "done" (a
    # store that had been overwritten to "failed" or cleared would report
    # "applied" here instead).
    probe = store.transition(job_id=job_id, status="done", body_sha256="probe")
    assert probe == "duplicate", "the store must still hold 'done' after the rejected transition"


@pytest.mark.unit
def test_c2c_forged_digest_401_store_untouched() -> None:
    """TST-CLAR-DEPLOY-19-C2c: a forged digest → 401, store untouched (ordering:
    no durable transition can land without first passing HMAC verification)."""
    verifier = FakeJWTVerifier()
    issuer = FakeHmacKeyIssuer()
    spy = SpyJobStateStore()
    client, *_ = _build_app(
        verifier=verifier, job_state_store=spy, hmac_key_issuer=issuer, now=lambda: 1000
    )

    job_id, scan_id = uuid4(), uuid4()
    key_id, _secret = issuer.issue(job_id=job_id, scan_id=scan_id)
    body = done_report(job_id, scan_id)
    _valid_header, body_bytes = sign_callback(
        job_id=job_id,
        worker_id="worker-1",
        timestamp=1000,
        body=body,
        key_id=key_id,
        secret=_secret,
    )

    forged_header = f"HMAC {key_id}:" + "0" * 64  # syntactically valid, wrong digest
    resp = _post_callback(client, job_id, body_bytes, forged_header, timestamp=1000)
    assert resp.status_code == 401  # type: ignore[attr-defined]
    assert resp.json()["error_code"] == "invalid_hmac"  # type: ignore[attr-defined]
    assert spy.calls == []


@pytest.mark.unit
def test_c2d_repeated_running_204_twice_single_recorded_state() -> None:
    """TST-CLAR-DEPLOY-19-C2d: repeated ``running`` → 204/204, single recorded
    (``applied``-then-``duplicate``) transition — the running heartbeat is
    replay-safe, mirroring the ``done`` no-op semantics."""
    verifier = FakeJWTVerifier()
    issuer = FakeHmacKeyIssuer()
    spy = SpyJobStateStore()
    client, *_ = _build_app(
        verifier=verifier, job_state_store=spy, hmac_key_issuer=issuer, now=lambda: 1000
    )

    job_id, scan_id = uuid4(), uuid4()
    key_id, secret = issuer.issue(job_id=job_id, scan_id=scan_id)
    running_body = JobStatusReport(
        job_id=job_id,
        scan_id=scan_id,
        status="running",
        S_version="2.7.0",
        env_digest=FAKE_ENV_DIGEST,
    )
    header, body_bytes = sign_callback(
        job_id=job_id,
        worker_id="worker-1",
        timestamp=1000,
        body=running_body,
        key_id=key_id,
        secret=secret,
    )

    r1 = _post_callback(client, job_id, body_bytes, header, timestamp=1000)
    r2 = _post_callback(client, job_id, body_bytes, header, timestamp=1000)
    assert r1.status_code == 204  # type: ignore[attr-defined]
    assert r2.status_code == 204  # type: ignore[attr-defined]
    assert [c["outcome"] for c in spy.calls] == ["applied", "duplicate"]


# ---------------------------------------------------------------------------
# Stack tests — MVP-1 routes end to end
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_healthz_unauthenticated_200_static() -> None:
    """``GET /healthz`` needs no auth, no tenancy headers, no DB — static body."""
    client, *_ = _build_app(verifier=FakeJWTVerifier())
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.unit
def test_missing_bearer_401_envelope() -> None:
    """No ``Authorization`` header → 401 unauthenticated DOC-API §6 envelope."""
    client, *_ = _build_app(verifier=FakeJWTVerifier())
    resp = client.post("/api/v1/scans", content=b"{}", headers={"Idempotency-Key": str(uuid4())})
    assert resp.status_code == 401
    body = resp.json()
    assert body["error_code"] == "unauthenticated"
    assert body["trace_id"]


@pytest.mark.invariant
def test_org_mismatch_403_envelope() -> None:
    """AC-CP-01a over HTTP: a tenancy-header / JWT-claim mismatch → 403
    org_mismatch, BEFORE any fan-out (the layer-1 cross-tenant signal)."""
    verifier = FakeJWTVerifier()
    verifier.register("token-a", claims_for(ORG_A))
    client, *_ = _build_app(verifier=verifier)
    headers = {
        "Authorization": "Bearer token-a",
        "X-Scanipy-Org-Id": ORG_B,  # JWT says org A; header claims org B
        "X-Scanipy-User-Id": "scanner",
        "Idempotency-Key": str(uuid4()),
    }
    resp = client.post("/api/v1/scans", content=b"{}", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "org_mismatch"


@pytest.mark.unit
def test_role_denied_403_org_viewer_post_scans() -> None:
    """An ``org-viewer`` token (read-only) POSTing /scans → 403 role_denied."""
    verifier = FakeJWTVerifier()
    verifier.register("token-viewer", claims_for(ORG_A, role="org-viewer", user_id="viewer-1"))
    client, *_ = _build_app(verifier=verifier)
    headers = {
        "Authorization": "Bearer token-viewer",
        "X-Scanipy-Org-Id": ORG_A,
        "X-Scanipy-User-Id": "viewer-1",
        "Idempotency-Key": str(uuid4()),
    }
    resp = client.post("/api/v1/scans", content=b"{}", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "role_denied"


@pytest.mark.unit
def test_post_scans_201_then_replay_200_same_scan_id() -> None:
    """A fresh submission is 201 (fans >=1 job); the SAME Idempotency-Key +
    body replayed is 200 with the SAME scan_id and no re-fan (job_ids == [])."""
    verifier = FakeJWTVerifier()
    verifier.register("token-a", claims_for(ORG_A))
    client, reg, *_ = _build_app(verifier=verifier)
    ids = _shipped_ids(reg)
    assert ids, "DET-02 registry loaded zero detectors (vacuous test)"
    headers = {
        **headers_for(ORG_A),
        "Authorization": "Bearer token-a",
        "Idempotency-Key": str(uuid4()),
    }
    body_bytes = _scan_body_bytes(ids)

    r1 = client.post("/api/v1/scans", content=body_bytes, headers=headers)
    assert r1.status_code == 201, r1.text
    scan1 = r1.json()
    assert scan1["job_ids"], "a fresh scan must fan at least one job"

    r2 = client.post("/api/v1/scans", content=body_bytes, headers=headers)
    assert r2.status_code == 200, r2.text
    scan2 = r2.json()
    assert scan2["scan_id"] == scan1["scan_id"]
    assert scan2["job_ids"] == []


@pytest.mark.unit
def test_idempotency_key_header_required_400() -> None:
    """A POST /scans with NO ``Idempotency-Key`` header → 400 invalid_input."""
    verifier = FakeJWTVerifier()
    verifier.register("token-a", claims_for(ORG_A))
    client, *_ = _build_app(verifier=verifier)
    headers = {**headers_for(ORG_A), "Authorization": "Bearer token-a"}
    resp = client.post("/api/v1/scans", content=b"{}", headers=headers)
    assert resp.status_code == 400
    assert resp.json()["error_code"] == "invalid_input"


@pytest.mark.invariant
def test_cross_org_get_scan_404() -> None:
    """Org B reading org A's scan → 404 not_found (no cross-tenant existence
    leak; CMP-CP-01 §9 layer 2, exercised over the real HTTP surface)."""
    verifier = FakeJWTVerifier()
    verifier.register("token-a", claims_for(ORG_A))
    verifier.register("token-b", claims_for(ORG_B))
    client, reg, *_ = _build_app(verifier=verifier)
    ids = _shipped_ids(reg)

    headers_a = {
        **headers_for(ORG_A),
        "Authorization": "Bearer token-a",
        "Idempotency-Key": str(uuid4()),
    }
    created = client.post("/api/v1/scans", content=_scan_body_bytes(ids), headers=headers_a)
    assert created.status_code == 201, created.text
    scan_id = created.json()["scan_id"]

    # Positive control: org A can read its own scan.
    own = client.get(f"/api/v1/scans/{scan_id}", headers=headers_a)
    assert own.status_code == 200

    headers_b = {**headers_for(ORG_B), "Authorization": "Bearer token-b"}
    resp = client.get(f"/api/v1/scans/{scan_id}", headers=headers_b)
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "not_found"


@pytest.mark.unit
def test_error_envelope_echoes_trace_id_header() -> None:
    """A supplied ``X-Scanipy-Trace-Id`` header is echoed in the error envelope
    body's ``trace_id`` field (DOC-API §3.3 trace propagation)."""
    client, *_ = _build_app(verifier=FakeJWTVerifier())
    resp = client.post(
        "/api/v1/scans",
        content=b"{}",
        headers={"X-Scanipy-Trace-Id": "trace-xyz-123", "Idempotency-Key": str(uuid4())},
    )
    assert resp.status_code == 401
    assert resp.json()["trace_id"] == "trace-xyz-123"


@pytest.mark.invariant
def test_binding_order_authorize_then_bind_then_commit() -> None:
    """CP-01's normative order over real HTTP (db/session.py contract):

    (1) a DENIED request (role_denied) never opens a transaction — the fake
        connection's log stays empty;
    (2) a clean authorized request binds (SET LOCAL x3) then COMMITs;
    (3) a request that raises INSIDE the bound block (unknown detector_id)
        binds then ROLLBACKs — never commits a partially-applied request.
    """
    verifier = FakeJWTVerifier()
    verifier.register("token-viewer", claims_for(ORG_A, role="org-viewer", user_id="viewer-1"))
    verifier.register("token-a", claims_for(ORG_A))

    # (1) DENIED — role_denied fires before bound_request; no transaction opens.
    denied_conn = _FakeConnection()
    client_denied, *_ = _build_app(
        verifier=verifier, connection_factory=_connection_factory(denied_conn)
    )
    resp_denied = client_denied.post(
        "/api/v1/scans",
        content=b"{}",
        headers={
            "Authorization": "Bearer token-viewer",
            "X-Scanipy-Org-Id": ORG_A,
            "X-Scanipy-User-Id": "viewer-1",
            "Idempotency-Key": str(uuid4()),
        },
    )
    assert resp_denied.status_code == 403
    assert denied_conn.log == [], "a denied request must never open a transaction"

    # (2) CLEAN exit — authorized + successful request binds then commits.
    ok_conn = _FakeConnection()
    client_ok, reg, *_ = _build_app(
        verifier=verifier, connection_factory=_connection_factory(ok_conn)
    )
    ids = _shipped_ids(reg)
    resp_ok = client_ok.post(
        "/api/v1/scans",
        content=_scan_body_bytes(ids),
        headers={
            "Authorization": "Bearer token-a",
            "X-Scanipy-Org-Id": ORG_A,
            "X-Scanipy-User-Id": "scanner",
            "Idempotency-Key": str(uuid4()),
        },
    )
    assert resp_ok.status_code == 201, resp_ok.text
    kinds_ok = [entry[0] for entry in ok_conn.log]
    assert kinds_ok.count("execute") == 3, f"expected 3 SET LOCAL binds; saw {kinds_ok}"
    assert "commit" in kinds_ok and "rollback" not in kinds_ok
    assert kinds_ok.index("commit") > kinds_ok.index("execute"), "bind must precede commit"
    assert kinds_ok[-1] == "close", "the cursor is always closed last (finally)"

    # (3) ERROR after bind — an unknown detector_id raises INSIDE the bound
    #     block; the transaction must roll back, never commit.
    err_conn = _FakeConnection()
    client_err, *_ = _build_app(verifier=verifier, connection_factory=_connection_factory(err_conn))
    resp_err = client_err.post(
        "/api/v1/scans",
        content=_scan_body_bytes(("no-such-detector",)),
        headers={
            "Authorization": "Bearer token-a",
            "X-Scanipy-Org-Id": ORG_A,
            "X-Scanipy-User-Id": "scanner",
            "Idempotency-Key": str(uuid4()),
        },
    )
    assert resp_err.status_code == 409, resp_err.text
    kinds_err = [entry[0] for entry in err_conn.log]
    assert kinds_err.count("execute") == 3, f"expected 3 SET LOCAL binds; saw {kinds_err}"
    assert "rollback" in kinds_err and "commit" not in kinds_err
    assert kinds_err[-1] == "close", "the cursor is always closed last (finally)"
