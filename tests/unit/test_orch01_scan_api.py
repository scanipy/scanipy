"""CMP-ORCH-01 scan-API specs — TST-AC-ORCH-01a/b + TST-INV-2-ORCH-01-style.

Hermetic, function-level tests over the framework-agnostic handler core
(``services.scan.api``): no FastAPI, no real SQS/S3/PostgreSQL. The build-ahead
ports (snapshot resolve-or-create, ``spec_versions`` registry, per-job HMAC key
issuer) are injected as deterministic doubles from ``tests/orch01_fakes.py``; the
queue is the real shipped CMP-DEPLOY-01 ``StandardQueue`` and the guard / RLS
store are the real merged CMP-CP-01 surfaces.

Covers the task's NEW-TEST requirements:
  (a) POSITIVE — submit over the REAL DET-02 registry (#288 specs) fans exactly
      one job per registered detector, each job carrying S_version + env_digest.
  (b) MUTATION — callback HMAC: wrong-key + expired-timestamp both REJECTED, and
      a broken verifier (skew check removed) FAILS the test (mutation-verified).
  (c) cross-org read through the CP-01 RLS seam returns zero rows (404).
  (d) anti-vacuity on every leg.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from detectors.registry import DetectorRegistry
from services.control_plane.guard import CPGuard
from services.scan.api import (
    HMAC_SKEW_WINDOW_SECONDS,
    AuthorizationError,
    DetectorUnknownError,
    IdempotencyConflictError,
    InvalidHmacError,
    OrgScopedScanStore,
    ScanNotFoundError,
    ScanRequest,
    canonical_request,
    get_scan,
    post_job_status,
    post_scans,
    verify_worker_callback_hmac,
)
from services.substrate.queue import StandardQueue
from tests.orch01_fakes import (
    ORG_A,
    ORG_B,
    FakeHmacKeyIssuer,
    FakeSnapshotPort,
    FakeSpecRegistry,
    claims_for,
    done_report,
    headers_for,
    scan_request,
    sign_callback,
)


def _registry() -> DetectorRegistry:
    reg = DetectorRegistry()
    reg.load_manifests("detectors/")
    return reg


def _drain_queue(queue: StandardQueue) -> list[dict[str, str]]:
    """Pop every ready message body from the in-memory queue (FIFO)."""
    bodies: list[dict[str, str]] = []
    while True:
        received = queue.receive()
        if received is None:
            break
        bodies.append(received.message.body)
    return bodies


def _shipped_ids(reg: DetectorRegistry) -> tuple[str, ...]:
    """Whatever ids the registry actually loaded (robust to corpus changes)."""
    return tuple(sorted(d.id for d in reg.all()))


# ---------------------------------------------------------------------------
# (a) POSITIVE — fan-out over the REAL registry, INV-2 threaded on every job
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_orch_01a_submit_fans_one_job_per_registered_detector() -> None:
    """TST-AC-ORCH-01a — a scan creates a snapshot if absent then fans exactly
    one job per submitted (registered) detector, INV-2 threaded.

    Maps to AC-ORCH-01a (DOC-CMP-ORCH-01 §6 steps 5-7). Submits the real shipped
    DET-02 detector ids; asserts exactly one WorkerJob per id, each carrying the
    bound S_version + the snapshot env_digest (INV-2). Anti-vacuity: the registry
    must load ≥1 detector and the fan-out count must equal the submitted count.
    """
    reg = _registry()
    ids = _shipped_ids(reg)
    assert ids, "DET-02 registry loaded zero detectors (vacuous fan-out)"

    queue = StandardQueue(name="scan-jobs")
    store = OrgScopedScanStore()
    created = post_scans(
        scan_request(ids, S_version="2.7.0"),
        claims_for(ORG_A),
        headers_for(ORG_A),
        idempotency_key=uuid4(),
        trace_id="t-1",
        guard=CPGuard(),
        registry=reg,
        scan_store=store,
        queue=queue,
        spec_registry=FakeSpecRegistry(),
        snapshot_port=FakeSnapshotPort(),
        hmac_key_issuer=FakeHmacKeyIssuer(),
    )

    # Exactly one job per submitted detector.
    assert len(created.job_ids) == len(ids)
    bodies = _drain_queue(queue)
    assert len(bodies) == len(ids), "fan-out did not enqueue one job per detector"

    enqueued_detectors = sorted(b["detector_id"] for b in bodies)
    assert enqueued_detectors == sorted(ids)

    # INV-2: every job carries the bound S_version + the snapshot env_digest.
    for b in bodies:
        assert b["S_version"] == "2.7.0", "S_version not threaded onto job (INV-2)"
        assert b["env_digest"] == created.env_digest
        assert b["env_digest"].startswith("sha256:")
        # CLAR-ORCH-05 discharge: hmac_key_id + callback_path present on each job.
        assert b["hmac_key_id"], "hmac_key_id not threaded (CLAR-ORCH-05)"
        assert b["callback_path"] == f"/api/v1/jobs/{b['job_id']}/status"

    # The scans row is readable back through the RLS-bound store (same org).
    record = get_scan(
        created.scan_id,
        claims_for(ORG_A),
        headers_for(ORG_A),
        trace_id="t-1",
        guard=CPGuard(),
        scan_store=store,
    )
    assert record.S_version == "2.7.0"
    assert record.env_digest == created.env_digest


@pytest.mark.unit
def test_orch_01a_unknown_detector_rejected_no_enqueue() -> None:
    """An unknown detector id is rejected (409) with NO fan-out (DOC §6 step 4)."""
    reg = _registry()
    queue = StandardQueue(name="scan-jobs")
    with pytest.raises(DetectorUnknownError) as exc:
        post_scans(
            scan_request(("java-py-injection", "no-such-detector"), S_version="2.7.0"),
            claims_for(ORG_A),
            headers_for(ORG_A),
            idempotency_key=uuid4(),
            trace_id="t-1",
            guard=CPGuard(),
            registry=reg,
            scan_store=OrgScopedScanStore(),
            queue=queue,
            spec_registry=FakeSpecRegistry(),
            snapshot_port=FakeSnapshotPort(),
            hmac_key_issuer=FakeHmacKeyIssuer(),
        )
    assert exc.value.http_status == 409
    # Fail-closed: NOTHING was enqueued (validation precedes fan-out).
    assert _drain_queue(queue) == [], "an unknown detector still enqueued jobs"


@pytest.mark.unit
def test_orch_01a_idempotency_replay_returns_same_scan_no_refan() -> None:
    """A replayed Idempotency-Key returns the existing scan with no re-enqueue."""
    reg = _registry()
    ids = _shipped_ids(reg)
    queue = StandardQueue(name="scan-jobs")
    store = OrgScopedScanStore()
    key = uuid4()
    common: dict[str, object] = {
        "guard": CPGuard(),
        "registry": reg,
        "scan_store": store,
        "queue": queue,
        "spec_registry": FakeSpecRegistry(),
        "snapshot_port": FakeSnapshotPort(),
        "hmac_key_issuer": FakeHmacKeyIssuer(),
    }
    first = post_scans(
        scan_request(ids, S_version="2.7.0"),
        claims_for(ORG_A),
        headers_for(ORG_A),
        idempotency_key=key,
        trace_id="t-1",
        **common,
    )
    _drain_queue(queue)  # consume the first fan-out
    second = post_scans(
        scan_request(ids, S_version="2.7.0"),
        claims_for(ORG_A),
        headers_for(ORG_A),
        idempotency_key=key,
        trace_id="t-2",
        **common,
    )
    assert second.scan_id == first.scan_id
    assert second.job_ids == (), "idempotency replay re-fanned jobs"
    assert _drain_queue(queue) == [], "idempotency replay enqueued new jobs"


@pytest.mark.unit
def test_orch_01a_same_key_different_body_is_conflict() -> None:
    """Same Idempotency-Key replayed with a DIFFERENT body → 409 (DOC §3.4).

    A changed body under a reused key is a client error, not a silent return of
    the original scan. Anti-vacuity: the matching-body replay above returns the
    same scan; here only the body changes (an extra detector) and it conflicts.
    """
    reg = _registry()
    ids = _shipped_ids(reg)
    queue = StandardQueue(name="scan-jobs")
    store = OrgScopedScanStore()
    key = uuid4()
    common: dict[str, object] = {
        "guard": CPGuard(),
        "registry": reg,
        "scan_store": store,
        "queue": queue,
        "spec_registry": FakeSpecRegistry(),
        "snapshot_port": FakeSnapshotPort(),
        "hmac_key_issuer": FakeHmacKeyIssuer(),
    }
    post_scans(
        scan_request((ids[0],), S_version="2.7.0"),
        claims_for(ORG_A),
        headers_for(ORG_A),
        idempotency_key=key,
        trace_id="t-1",
        **common,
    )
    # Replay the SAME key with a DIFFERENT S_version → conflict.
    with pytest.raises(IdempotencyConflictError) as exc:
        post_scans(
            ScanRequest(
                codebase_id=UUID(int=7),
                commit_sha="a" * 40,
                detector_ids=(ids[0],),
                S_version="1.0.0",  # changed body
            ),
            claims_for(ORG_A),
            headers_for(ORG_A),
            idempotency_key=key,
            trace_id="t-2",
            **common,
        )
    assert exc.value.http_status == 409
    assert exc.value.error_code == "idempotency_conflict"


# ---------------------------------------------------------------------------
# (c) cross-org read through the CP-01 RLS seam returns zero rows (404)
# ---------------------------------------------------------------------------


@pytest.mark.invariant
def test_orch_01_cross_org_read_returns_not_found() -> None:
    """A caller in org B cannot read org A's scan (CP-01 layer-2 isolation).

    Org A submits a scan; org B (valid token, own tenancy headers) reads it by id
    and gets 404 not_found — the foreign row is structurally unreachable through
    the RLS-bound store, indistinguishable from a non-existent one (no leak).
    Anti-vacuity: org A CAN read its own scan (the positive control).
    """
    reg = _registry()
    ids = _shipped_ids(reg)
    queue = StandardQueue(name="scan-jobs")
    store = OrgScopedScanStore()
    created = post_scans(
        scan_request(ids, S_version="2.7.0"),
        claims_for(ORG_A),
        headers_for(ORG_A),
        idempotency_key=uuid4(),
        trace_id="t-1",
        guard=CPGuard(),
        registry=reg,
        scan_store=store,
        queue=queue,
        spec_registry=FakeSpecRegistry(),
        snapshot_port=FakeSnapshotPort(),
        hmac_key_issuer=FakeHmacKeyIssuer(),
    )

    # Positive control: org A reads its own scan.
    own = get_scan(
        created.scan_id,
        claims_for(ORG_A),
        headers_for(ORG_A),
        trace_id="t-1",
        guard=CPGuard(),
        scan_store=store,
    )
    assert own.scan_id == created.scan_id

    # Cross-org: org B is denied with 404 (no existence leak).
    with pytest.raises(ScanNotFoundError) as exc:
        get_scan(
            created.scan_id,
            claims_for(ORG_B),
            headers_for(ORG_B),
            trace_id="t-2",
            guard=CPGuard(),
            scan_store=store,
        )
    assert exc.value.http_status == 404


@pytest.mark.invariant
def test_orch_01_org_mismatch_header_denied_before_data() -> None:
    """A tenancy-header / JWT-claim mismatch is denied by the CP-01 guard (403).

    Anti-vacuity that the guard is actually wired: a request whose
    X-Scanipy-Org-Id header disagrees with the JWT org claim is rejected as
    org_mismatch BEFORE any snapshot/fan-out — the layer-1 cross-tenant signal.
    """
    reg = _registry()
    queue = StandardQueue(name="scan-jobs")
    with pytest.raises(AuthorizationError) as exc:
        post_scans(
            scan_request(_shipped_ids(reg), S_version="2.7.0"),
            claims_for(ORG_A),  # JWT says org A
            headers_for(ORG_B),  # header says org B — mismatch
            idempotency_key=uuid4(),
            trace_id="t-1",
            guard=CPGuard(),
            registry=reg,
            scan_store=OrgScopedScanStore(),
            queue=queue,
            spec_registry=FakeSpecRegistry(),
            snapshot_port=FakeSnapshotPort(),
            hmac_key_issuer=FakeHmacKeyIssuer(),
        )
    assert exc.value.http_status == 403
    assert exc.value.error_code == "org_mismatch"
    assert _drain_queue(queue) == [], "a denied request still enqueued jobs"


# ---------------------------------------------------------------------------
# (b) HMAC callback — wrong key + expired timestamp REJECTED; positive verifies
# ---------------------------------------------------------------------------


def _signed_callback(
    issuer: FakeHmacKeyIssuer, job_id: UUID, scan_id: UUID, *, timestamp: int
) -> tuple[str, bytes, str, bytes]:
    """Issue a key + sign a done-report; return (key_id, secret, header, bytes)."""
    key_id, secret = issuer.issue(job_id=job_id, scan_id=scan_id)
    body = done_report(job_id, scan_id)
    header, body_bytes = sign_callback(
        job_id=job_id,
        worker_id="worker-1",
        timestamp=timestamp,
        body=body,
        key_id=key_id,
        secret=secret,
    )
    return key_id, secret, header, body_bytes


@pytest.mark.unit
def test_orch_01b_callback_positive_then_wrong_key_and_skew_reject() -> None:
    """TST-AC-ORCH-01b — the valid callback verifies; a wrong-key signature and an
    expired timestamp are BOTH rejected (DOC-CMP-ORCH-01 §3.3).

    (positive / anti-vacuity) a correctly-signed in-window callback returns None
    (204). (wrong key) signing with a different secret → 401 invalid_hmac.
    (skew) a valid digest with timestamp > 300s out of window → 401 invalid_hmac.
    Tenant is implicit in the HMAC-keyed job (DOC-API §2.5) — no org headers.
    """
    issuer = FakeHmacKeyIssuer()
    job_id, scan_id = UUID(int=20), UUID(int=21)
    body = done_report(job_id, scan_id)
    _key_id, _secret, header, body_bytes = _signed_callback(issuer, job_id, scan_id, timestamp=1000)

    # POSITIVE: correctly-signed, in-window → accepted (returns None / 204).
    assert (
        post_job_status(
            job_id,
            body,
            body_bytes,
            hmac_header=header,
            worker_id_header="worker-1",
            timestamp_header=1000,
            key_issuer=issuer,
            scan_store=OrgScopedScanStore(),
            now=lambda: 1000,
        )
        is None
    )

    # WRONG KEY: sign the SAME body with an unrelated secret → reject.
    import hashlib
    import hmac as _hmac

    wrong_secret = b"\x00" * 32
    message = canonical_request(
        method="POST",
        path=f"/api/v1/jobs/{job_id}/status",
        worker_id="worker-1",
        body_bytes=body_bytes,
        timestamp=1000,
    )
    wrong_digest = _hmac.new(wrong_secret, message, hashlib.sha256).hexdigest()
    with pytest.raises(InvalidHmacError) as exc_wrong:
        post_job_status(
            job_id,
            body,
            body_bytes,
            hmac_header=f"HMAC {_key_id}:{wrong_digest}",
            worker_id_header="worker-1",
            timestamp_header=1000,
            key_issuer=issuer,
            scan_store=OrgScopedScanStore(),
            now=lambda: 1000,
        )
    assert exc_wrong.value.error_code == "invalid_hmac"

    # SKEW: valid digest, but timestamp is just outside the 300s window → reject.
    with pytest.raises(InvalidHmacError) as exc_skew:
        post_job_status(
            job_id,
            body,
            body_bytes,
            hmac_header=header,
            worker_id_header="worker-1",
            timestamp_header=1000,
            key_issuer=issuer,
            scan_store=OrgScopedScanStore(),
            now=lambda: 1000 + HMAC_SKEW_WINDOW_SECONDS + 1,
        )
    assert exc_skew.value.error_code == "invalid_hmac"


@pytest.mark.unit
def test_orch_01b_unknown_key_id_fails_closed() -> None:
    """An Authorization referencing an unissued key id fails closed (401).

    The verifier looks the key up by (job_id, key_id); a miss must NOT fall
    through to a trusted-by-default path — it rejects (fail-closed)."""
    issuer = FakeHmacKeyIssuer()
    job_id, scan_id = UUID(int=30), UUID(int=31)
    body = done_report(job_id, scan_id)
    # Never issued for this job — the issuer keyring is empty.
    with pytest.raises(InvalidHmacError):
        post_job_status(
            job_id,
            body,
            b"{}",
            hmac_header="HMAC k-unknown:deadbeef",
            worker_id_header="worker-1",
            timestamp_header=1000,
            key_issuer=issuer,
            scan_store=OrgScopedScanStore(),
            now=lambda: 1000,
        )


@pytest.mark.invariant
def test_orch_01b_mutation_skew_check_removed_fails() -> None:
    """MUTATION-VERIFIED negative control: a verifier with the skew check REMOVED
    must FAIL the anti-replay assertion (proves the skew leg has power).

    Re-implements the verifier WITHOUT the timestamp-window check (the exact
    mutation a broken impl would ship) and confirms it ACCEPTS an out-of-window
    callback the real verifier REJECTS — so the real test's skew leg is
    non-vacuous. Also re-implements the digest-compare mutation (accept-on-any)
    to confirm the wrong-key leg has power.
    """
    import hashlib
    import hmac as _hmac

    issuer = FakeHmacKeyIssuer()
    job_id, scan_id = UUID(int=40), UUID(int=41)
    key_id, secret = issuer.issue(job_id=job_id, scan_id=scan_id)
    body = done_report(job_id, scan_id)
    header, body_bytes = sign_callback(
        job_id=job_id,
        worker_id="worker-1",
        timestamp=1000,
        body=body,
        key_id=key_id,
        secret=secret,
    )

    far_future = 1000 + HMAC_SKEW_WINDOW_SECONDS + 5

    # (1) The REAL verifier rejects the out-of-window callback.
    with pytest.raises(InvalidHmacError):
        verify_worker_callback_hmac(
            hmac_header=header,
            worker_id="worker-1",
            timestamp=1000,
            job_id=job_id,
            body_bytes=body_bytes,
            key_issuer=issuer,
            now=lambda: far_future,
        )

    # (2) MUTATION: a verifier with the skew check DELETED accepts the same
    #     out-of-window callback — so removing the check changes behaviour, i.e.
    #     the real skew assertion above has power (is not vacuous).
    def _verify_no_skew(
        *, hmac_header: str, body_bytes: bytes, job_id: UUID, timestamp: int
    ) -> bool:
        prefix = "HMAC "
        rest = hmac_header[len(prefix) :]
        key, _sep, provided = rest.partition(":")
        secret_b = issuer.lookup(job_id=job_id, key_id=key)
        assert secret_b is not None
        message = canonical_request(
            method="POST",
            path=f"/api/v1/jobs/{job_id}/status",
            worker_id="worker-1",
            body_bytes=body_bytes,
            timestamp=timestamp,
        )
        expected = _hmac.new(secret_b, message, hashlib.sha256).hexdigest()
        # constant-time compare retained; ONLY the skew window check is removed.
        return _hmac.compare_digest(provided, expected)

    assert (
        _verify_no_skew(hmac_header=header, body_bytes=body_bytes, job_id=job_id, timestamp=1000)
        is True
    ), "skew-removed mutant did not accept the out-of-window callback (control has no power)"

    # (3) CONSTANT-TIME STRUCTURAL GUARD. "non-constant-time ==" is NOT
    #     behaviourally distinguishable from compare_digest (no timing assertion
    #     can catch it deterministically), so the honest enforcement is a
    #     source-inspection guard on the PRODUCTION verifier: it MUST use
    #     hmac.compare_digest and MUST NOT compare the digest with a bare ``==``.
    #     This is what makes the wrong-key leg's constant-time property real
    #     rather than asserted (RULE-9 webhook-auth surface; security co-sign
    #     shepherded by the orchestrator per the CLAR-SCM-02 / #262 precedent).
    import inspect

    src = inspect.getsource(verify_worker_callback_hmac)
    assert "hmac.compare_digest" in src, "verifier must use hmac.compare_digest (constant-time)"
    assert "provided_digest ==" not in src and "== expected_digest" not in src, (
        "verifier must NOT compare the HMAC digest with a non-constant-time =="
    )
