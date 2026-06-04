# ruff: noqa: N803
#   ``S_version`` keeps its capital S throughout: it is the normative provenance
#   field name (INV-2; DOC-PROVENANCE §2, ``.claude/rules/02-provenance.md``).
#   It appears as a parameter / attribute name on the scan-submission surface
#   (``ScanRequest.S_version``, the per-job thread). Renaming it to ``s_version``
#   would break the byte-canonical provenance key the rest of the pipeline reads;
#   suppressed file-wide (N803), matching ``services/scan/worker.py``.
"""CMP-ORCH-01 — Scan API (framework-agnostic handler core).

This module is the public ingress of the analysis pipeline (``POST /api/v1/scans``
submission + the scan-status read surface) and the HMAC-authenticated egress sink
for worker status reports (``POST /api/v1/jobs/{job_id}/status``). It is the
**INV-2 binder**: it binds ``S_version`` at scan submission and threads it, plus
the snapshot's ``env_digest``, onto every fanned ``WorkerJob`` (DOC-CMP-ORCH-01
§5, §8). It is NOT an INV-1 setter — ``origin`` and the other finding-level
provenance fields are stamped downstream by CMP-ORCH-03 / CMP-FND-01..03, so the
four-field RULE-6 stamping rule does not apply here (this module emits *jobs*, not
*findings*; DOC-CMP-ORCH-01 §8 "Must NOT touch" list).

FRAMEWORK-AGNOSTIC CORE ONLY (CLAR-DEPLOY-19 OPEN, RULE-8; CLAR-PROC-01 RESOLVED).
  DOC-CMP-ORCH-01 §3.1 sketches FastAPI/Starlette-equivalent ``async def``
  handlers with pydantic bodies. ``fastapi`` is not a pinned repo dependency and
  the ASGI request-lifecycle adapter is explicitly deferred to CLAR-DEPLOY-19
  (WBS §17, OPEN). Per the merged CMP-CP-01 precedent (``db/session.py`` /
  ``services/control_plane/guard.py``), this module ships the framework-agnostic
  handler core as plain **synchronous** functions over plain dataclasses and
  typed ports; the HTTP glue (ASGI ``Request``/``call_next``, pydantic models,
  the URL router) lands in the CLAR-DEPLOY-19 follow-up. No HTTP framework is
  imported here (RULE-8 hard constraint). The deviation from §3.1's ``async`` /
  pydantic shape is the documented CLAR-DEPLOY-19 build-ahead seam, not a silent
  re-interface (the same deviation CP-01's guard already took).

BUILD-AHEAD SEAMS (CLAR-PROC-01 condition (2) — typed ports, fail-closed prod):
  Three upstream collaborators are env-gated in hermetic CI; each is consumed via
  a typed port whose production default fails closed (raises a typed
  ``NotImplementedError`` naming the gated dependency), exactly like
  ``services/scan/worker.py``'s ``fail_closed_*`` seams. A hermetic test injects a
  deterministic fake through the same seam — never a fake on the prod path:

  * :class:`SnapshotPort` — resolve-or-create the snapshot (CMP-SNAP-01). The
    shipped ``SnapshotService.create_snapshot`` always mints a fresh id (no
    natural-key dedup) and needs an env-digest provider, so "snapshot-if-absent"
    is a port wired to the real service post-DEPLOY-19, not forced through the
    shipped signature.
  * :class:`SpecRegistryPort` — resolve / validate ``S_version`` against the
    ``spec_versions`` table (written only by CMP-TRI-02 after the e-process gate;
    INV-3 fence). Not yet built; consumed as a typed port.
  * :class:`HmacKeyIssuer` — mint the per-job ``(hmac_key_id, secret)``. DOC has
    an internal tension here (a NEW CLAR is filed via ``clar_filed``; the
    orchestrator assigns the canonical id — provisionally referenced below as the
    HMAC-issuer-ownership CLAR, matching the in-PR ``CLAR-ORCH-01`` precedent in
    ``worker.py``): §6 step 7 mints in ORCH-01, §3.3 says the scheduler
    CMP-ORCH-02 issues the key at dispatch. Routed through a port so *who holds*
    the secret is deferrable; ``post_scans`` calling ``issue()`` provisionally
    encodes the §6-step-7 reading (ORCH-01 drives issuance). If the architect
    rules §3.3, the ``issue()`` call moves to the scheduler — the port boundary is
    where that decision lands. The prod default fails closed either way.

  The queue is the real shipped CMP-DEPLOY-01 :class:`StandardQueue` (an in-memory
  SQS-equivalent that production binds to boto3); the CP-01 guard + RLS-binding
  seam (``authorize_request_for_binding`` / ``OrgScopedStore``) are the real
  merged CMP-CP-01 surfaces.

INTERFACE RECONCILE (reported, not invented):
  * CLAR-ORCH-05 is DISCHARGED in this PR — ``WorkerJob.hmac_key_id`` +
    ``WorkerJob.callback_path`` are now REAL fields (added in
    ``services/scan/worker.py`` with "" defaults so the ORCH-03 fakes still
    construct) and ``post_scans`` populates both on every fanned job.
  * The HMAC-issuer-ownership CLAR is NEWLY SURFACED (the implementation agent
    cannot edit WBS §17 and never invents a CLAR id — the full question is in
    ``clar_filed`` and the orchestrator assigns the canonical id): DOC-CMP-ORCH-01
    §6 step 7 vs §3.3 disagree on whether ORCH-01 or the ORCH-02 scheduler mints
    the per-job HMAC secret. Routed through :class:`HmacKeyIssuer`; the in-PR code
    takes the §6-step-7 reading (``post_scans`` calls ``issue()``), reversible at
    the port boundary if the architect rules §3.3.

Source-of-truth: ``DOC-CMP-ORCH-01`` (§2 mandate, §3 interface, §6 data flow, §8
threading), ``docs/cross-cutting/DOC-API.md`` (§2.3 HMAC bearer, §4.1/§4.5 REST
surface), ``services/control_plane`` + ``db/session.py`` (CMP-CP-01 guard seam),
``.claude/rules/02-provenance.md`` (ORCH-01 threads S_version + env_digest only).
"""

from __future__ import annotations

import hashlib
import hmac
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable
from uuid import UUID, uuid4

from services.control_plane.guard import (
    CPGuard,
    ErrorEnvelope,
    JWTClaims,
    OrgScopedStore,
    TenantIsolationError,
)
from services.scan.worker import WorkerJob

if TYPE_CHECKING:
    from collections.abc import Callable

    from detectors.registry import DetectorRegistry
    from services.substrate.queue import StandardQueue

# ---------------------------------------------------------------------------
# Shapes / constants
# ---------------------------------------------------------------------------

# SDD-normative worker-callback path (DOC-API §4.5); ``job_id`` substituted.
_CALLBACK_PATH_TEMPLATE = "/api/v1/jobs/{job_id}/status"

# INV-2 format fences (mirrors the shipped CMP-SNAP-01 / CMP-ORCH-03 guards).
_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_ENV_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")

# DOC-CMP-ORCH-01 §3.3 / DOC-API §2.3: 5-minute anti-replay window (seconds).
HMAC_SKEW_WINDOW_SECONDS = 300

JobStatus = Literal["running", "done", "failed"]


@dataclass(frozen=True)
class ScanRequest:
    """The ``POST /api/v1/scans`` body (DOC-CMP-ORCH-01 §3.1, DOC-API §4.1).

    ``S_version`` is optional on input: ``None`` means "resolve latest accepted"
    (DOC §6 step 3). ``detector_ids`` must be non-empty and each id is resolved
    against the CMP-DET-02 registry (unknown id → ``409 not_found``).
    """

    codebase_id: UUID
    commit_sha: str
    detector_ids: tuple[str, ...]
    S_version: str | None = None
    policy_overrides: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ScanCreated:
    """The 201 result of :func:`post_scans` (DOC-CMP-ORCH-01 §3.1).

    ``S_version`` is always the resolved value (never ``None``); ``env_digest`` is
    the snapshot's INV-2 digest.

    INTERFACE-SHAPE DEVIATION (reported via ``clar_filed``, not asserted away):
    DOC §3.1's ``ScanCreated`` carries ``created_at: datetime``; it is OMITTED
    here because the framework-agnostic core takes no clock input (a wall-clock
    read would be non-deterministic, matching the FND-01 emitter's "no clock
    reads" discipline) — ``created_at`` is stamped by the CLAR-DEPLOY-19 HTTP
    adapter / DB default. ``job_ids`` is ADDED (the fan-out result, one per
    detector) so a caller/test can assert the fan-out without re-reading the row.
    """

    scan_id: UUID
    snapshot_id: UUID
    status: Literal["queued"]
    S_version: str
    env_digest: str
    job_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class ScanRecord:
    """The persisted ``scans`` row this module reads/writes through the store.

    A deliberately thin projection of DOC-DB §4.11 — only the fields the
    hermetic read surface and the fan-out binder need. The full ORM row (with the
    server-default columns) is the CLAR-DB-01 / DEPLOY-19 follow-up.
    """

    scan_id: UUID
    org_id: str
    codebase_id: UUID
    snapshot_id: UUID
    commit_sha: str
    S_version: str
    env_digest: str
    detector_ids: tuple[str, ...]
    status: str
    idempotency_key: UUID
    # Fingerprint of the idempotency-relevant request body (DOC-API §3.4): a
    # replay with the same key but a DIFFERENT body is a 409, not a silent
    # return. Sourced from :func:`idempotency_fingerprint` at submission.
    idempotency_body_hash: str = ""


@dataclass(frozen=True)
class SnapshotResolution:
    """The (snapshot_id, env_digest) a :class:`SnapshotPort` resolves/creates.

    ``env_digest`` is the INV-2 value ORCH-01 threads onto every job; it is read
    from the snapshot (set by CMP-SNAP-01 from the worker image digest), never
    re-derived here (DOC-CMP-ORCH-01 §8 "env_digest … never re-derived here").
    """

    snapshot_id: UUID
    env_digest: str


@dataclass(frozen=True)
class JobStatusReport:
    """The ``POST /api/v1/jobs/{job_id}/status`` body (DOC-API §4.5).

    ``S_version`` + ``env_digest`` are required on every callback (INV-2 fence,
    DOC-CMP-ORCH-01 §6 step b). The partition counts are reported per-callback;
    ORCH-01 never derives per-finding ``origin`` from them (DOC §5 INV-1 row).
    """

    job_id: UUID
    scan_id: UUID
    status: JobStatus
    S_version: str
    env_digest: str
    findings_count: int = 0
    core_partition_count: int = 0
    oracle_partition_count: int = 0
    result_uri: str | None = None
    witness_uri: str | None = None
    error: dict[str, str] | None = None


# ---------------------------------------------------------------------------
# Typed errors (mirror the CP-01 ErrorEnvelope http_status discipline)
# ---------------------------------------------------------------------------


class ScanApiError(Exception):
    """Base for ORCH-01 handler errors carrying an HTTP status + error code.

    The CLAR-DEPLOY-19 HTTP adapter maps these onto the DOC-API §6 error
    envelope; the framework-agnostic core raises them so the negative-test
    contracts (AC-ORCH-01b) are exercised without a web framework.
    """

    def __init__(self, *, error_code: str, http_status: int, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.http_status = http_status
        self.message = message


class InvalidHmacError(ScanApiError):
    """Worker-callback HMAC verification failed (AC-ORCH-01b).

    Covers BOTH failure modes DOC-CMP-ORCH-01 §3.3 enumerates: a digest mismatch
    (forged / wrong-key signature) and a timestamp outside the 300s anti-replay
    window. Always ``401 invalid_hmac``; raised BEFORE any state mutation.
    """

    def __init__(self, message: str = "worker callback HMAC verification failed") -> None:
        super().__init__(error_code="invalid_hmac", http_status=401, message=message)


class InvalidInputError(ScanApiError):
    """Request body failed validation (DOC-CMP-ORCH-01 §3.4 ``400``)."""

    def __init__(self, message: str) -> None:
        super().__init__(error_code="invalid_input", http_status=400, message=message)


class DetectorUnknownError(ScanApiError):
    """A submitted ``detector_id`` is not in the registry (§3.4 ``409``)."""

    def __init__(self, detector_id: str) -> None:
        super().__init__(
            error_code="not_found",
            http_status=409,
            message=f"unknown detector_id: {detector_id!r}",
        )


class InvariantInv2Error(ScanApiError):
    """``S_version`` could not be resolved to a registered spec (§3.4 ``422``).

    The INV-3 fence: ORCH-01 accepts only a registered, version-pinned
    ``S_version`` (a row in ``spec_versions`` written by CMP-TRI-02), never an
    inline / LLM-tampered spec (DOC-CMP-ORCH-01 §5 INV-3 row).
    """

    def __init__(self, message: str) -> None:
        super().__init__(error_code="invariant_inv2_violation", http_status=422, message=message)


class ScanNotFoundError(ScanApiError):
    """``scan_id`` not visible to the caller's org (§3.4 ``404``).

    A scan owned by another tenant is indistinguishable from a non-existent one
    (no existence leak) — DOC-CMP-ORCH-01 §7 / CMP-CP-01 §9 layer 2.
    """

    def __init__(self) -> None:
        super().__init__(error_code="not_found", http_status=404, message="scan not found")


class IdempotencyConflictError(ScanApiError):
    """Same ``Idempotency-Key`` replayed with a DIFFERENT body (§3.4 ``409``).

    DOC-API §3.4 / DOC-CMP-ORCH-01 §3.4: a replay with the same key but a changed
    body is a client error (``409 idempotency_conflict``), NOT a silent return of
    the original scan — that would mask a bug in the caller. The store compares a
    fingerprint of the idempotency-relevant body fields.
    """

    def __init__(self) -> None:
        super().__init__(
            error_code="idempotency_conflict",
            http_status=409,
            message="Idempotency-Key replayed with a different request body",
        )


class AuthorizationError(ScanApiError):
    """The CP-01 guard denied the request (org_mismatch / role_denied / etc.).

    Wraps the guard's :class:`ErrorEnvelope` so the handler core can raise a
    typed error; the HTTP adapter unwraps it back to the envelope shape.
    """

    def __init__(self, envelope: ErrorEnvelope) -> None:
        super().__init__(
            error_code=envelope.error_code,
            http_status=envelope.http_status,
            message=envelope.message,
        )
        self.envelope = envelope


# ---------------------------------------------------------------------------
# Typed ports (build-ahead seams, CLAR-PROC-01 condition (2))
# ---------------------------------------------------------------------------


@runtime_checkable
class SnapshotPort(Protocol):
    """Resolve-or-create the snapshot for a scan (CMP-SNAP-01 seam).

    Returns the ``(snapshot_id, env_digest)`` the binder threads. "if absent"
    dedup is the port's responsibility; the shipped ``SnapshotService`` mints a
    fresh id per call, so production wires a natural-key-dedup adapter over it
    rather than calling ``create_snapshot`` directly.
    """

    def resolve_or_create(
        self, *, org_id: str, codebase_id: UUID, commit_sha: str
    ) -> SnapshotResolution: ...


@runtime_checkable
class SpecRegistryPort(Protocol):
    """Resolve / validate ``S_version`` against ``spec_versions`` (INV-3 fence).

    ``resolve_latest`` returns the latest accepted ``S_version`` (DOC §6 step 3a);
    ``is_registered`` confirms a submitted ``S_version`` is an accepted, pinned
    row (step 3b). Both read only CMP-TRI-02-written rows — never an inline spec.
    """

    def resolve_latest(self) -> str | None: ...

    def is_registered(self, S_version: str) -> bool: ...


@runtime_checkable
class HmacKeyIssuer(Protocol):
    """Mint + look up the per-job HMAC secret (DOC-API §2.3).

    HMAC-issuer-ownership CLAR (newly surfaced via ``clar_filed``; canonical id
    assigned by the orchestrator): DOC §6 step 7 mints here; DOC §3.3 says the
    scheduler issues at dispatch. Routed through this port so the ownership is
    deferrable. ``issue`` mints ``(hmac_key_id, secret)`` for a job;
    ``lookup`` returns the secret for ``(job_id, key_id)`` on the callback path,
    or ``None`` (fail-closed → ``401 invalid_hmac``) on an unknown key.
    """

    def issue(self, *, job_id: UUID, scan_id: UUID) -> tuple[str, bytes]: ...

    def lookup(self, *, job_id: UUID, key_id: str) -> bytes | None: ...


@runtime_checkable
class ScanStore(Protocol):
    """Persist + read ``scans`` rows, RLS-scoped through CMP-CP-01's store.

    The hermetic implementation wraps :class:`OrgScopedStore` so cross-org reads
    return ``None`` (the layer-2 isolation contract); production binds the
    RLS-backed SQL store via ``db/session.py``'s ``acquire_for_request`` seam.
    """

    def put(self, record: ScanRecord) -> None: ...

    def get(self, scan_id: UUID, *, org_id: str) -> ScanRecord | None: ...

    def find_by_idempotency(self, *, org_id: str, idempotency_key: UUID) -> ScanRecord | None: ...


# ---------------------------------------------------------------------------
# Fail-closed production defaults (CLAR-PROC-01 condition (2))
# ---------------------------------------------------------------------------


class _FailClosedSnapshotPort:
    """Prod snapshot port: raises until the SNAP-01 dedup adapter is wired."""

    def resolve_or_create(
        self, *, org_id: str, codebase_id: UUID, commit_sha: str
    ) -> SnapshotResolution:
        raise NotImplementedError(
            "snapshot resolve-or-create is gated (CMP-ORCH-01 build-ahead, "
            "CLAR-PROC-01): the CMP-SNAP-01 natural-key-dedup adapter is wired "
            "post-DEPLOY-19. Inject a SnapshotPort via post_scans(..., "
            "snapshot_port=...) in a hermetic test."
        )


class _FailClosedSpecRegistryPort:
    """Prod spec-registry port: raises until ``spec_versions`` (CMP-TRI-02) lands."""

    def resolve_latest(self) -> str | None:
        raise NotImplementedError(
            "S_version resolution requires the spec_versions table (CMP-TRI-02), "
            "not yet built (CMP-ORCH-01 build-ahead, CLAR-PROC-01). Inject a "
            "SpecRegistryPort via post_scans(..., spec_registry=...) in a test."
        )

    def is_registered(self, S_version: str) -> bool:
        raise NotImplementedError(
            "S_version validation requires the spec_versions table (CMP-TRI-02), "
            "not yet built (CMP-ORCH-01 build-ahead, CLAR-PROC-01)."
        )


class _FailClosedHmacKeyIssuer:
    """Prod HMAC key issuer: raises until the issuer-ownership CLAR lands."""

    def issue(self, *, job_id: UUID, scan_id: UUID) -> tuple[str, bytes]:
        raise NotImplementedError(
            "per-job HMAC key issuance is gated (CMP-ORCH-01 build-ahead, "
            "CLAR-PROC-01 + the newly-filed HMAC-issuer-ownership CLAR): whether "
            "ORCH-01 or the ORCH-02 scheduler mints the secret is unresolved. "
            "Inject an HmacKeyIssuer via post_scans(..., hmac_key_issuer=...) in "
            "a hermetic test."
        )

    def lookup(self, *, job_id: UUID, key_id: str) -> bytes | None:
        raise NotImplementedError(
            "per-job HMAC key lookup is gated (CMP-ORCH-01 build-ahead, "
            "CLAR-PROC-01 + the HMAC-issuer-ownership CLAR). Inject an "
            "HmacKeyIssuer in a test."
        )


def fail_closed_snapshot_port() -> SnapshotPort:
    """Default snapshot port: fail-closed until the SNAP-01 adapter is wired."""
    return _FailClosedSnapshotPort()


def fail_closed_spec_registry() -> SpecRegistryPort:
    """Default spec registry: fail-closed until ``spec_versions`` (CMP-TRI-02)."""
    return _FailClosedSpecRegistryPort()


def fail_closed_hmac_key_issuer() -> HmacKeyIssuer:
    """Default HMAC key issuer: fail-closed until the issuer-ownership CLAR lands."""
    return _FailClosedHmacKeyIssuer()


# ---------------------------------------------------------------------------
# HMAC canonical request + constant-time verification (DOC-API §2.3, §3.3)
# ---------------------------------------------------------------------------


def canonical_request(
    *, method: str, path: str, worker_id: str, body_bytes: bytes, timestamp: int
) -> bytes:
    """Build the canonical request the worker signs (DOC-API §2.3, DOC §3.3).

    ``canonical-request = method + "\\n" + path + "\\n" + worker_id + "\\n"
    + sha256_hex(body) + "\\n" + timestamp``. The body digest is computed over the
    EXACT wire bytes the worker hashed — the caller passes raw ``body_bytes``, not
    a re-serialised parse, so canonicalisation drift can never cause a false
    reject (advisor trap: re-serialising the parsed report would diverge).
    """
    body_sha = hashlib.sha256(body_bytes).hexdigest()
    canonical = f"{method}\n{path}\n{worker_id}\n{body_sha}\n{timestamp}"
    return canonical.encode("utf-8")


def _parse_hmac_header(header: str) -> tuple[str, str]:
    """Parse ``Authorization: HMAC <key-id>:<hex-digest>`` (DOC-API §2.3).

    Returns ``(key_id, hex_digest)``. Any malformed header fails closed with
    :class:`InvalidHmacError` (never a partial/optimistic parse).
    """
    prefix = "HMAC "
    if not header.startswith(prefix):
        raise InvalidHmacError("Authorization header is not an HMAC bearer")
    rest = header[len(prefix) :].strip()
    key_id, sep, digest = rest.partition(":")
    if not sep or not key_id or not digest:
        raise InvalidHmacError("malformed HMAC bearer: expected '<key-id>:<hex-digest>'")
    return key_id, digest


def verify_worker_callback_hmac(
    *,
    hmac_header: str,
    worker_id: str,
    timestamp: int,
    job_id: UUID,
    body_bytes: bytes,
    key_issuer: HmacKeyIssuer,
    now: Callable[[], int] = lambda: int(time.time()),
) -> None:
    """Verify a worker callback's HMAC (DOC-CMP-ORCH-01 §3.3) — fail-closed.

    Order (each step fails closed before any state mutation, AC-ORCH-01b):
      1. parse ``Authorization: HMAC <key-id>:<digest>``;
      2. look up the per-job secret by ``(job_id, key_id)`` (miss → reject);
      3. recompute HMAC-SHA-256 over the canonical request and compare with
         ``hmac.compare_digest`` — a **constant-time** compare (never ``==`` on
         the digest, which would leak a timing side-channel);
      4. reject if ``|now - timestamp| > 300`` (anti-replay window).

    ``now`` is injected so the skew leg is deterministic in tests (matching the
    "no wall-clock reads in the deterministic path" discipline); production uses
    the default ``int(time.time())``. Raises :class:`InvalidHmacError` (401) on
    ANY failure; returns ``None`` on success. The caller mutates state only after
    this returns.
    """
    key_id, provided_digest = _parse_hmac_header(hmac_header)

    secret = key_issuer.lookup(job_id=job_id, key_id=key_id)
    if secret is None:
        # Unknown key id → fail closed (never trust an unverifiable digest).
        raise InvalidHmacError("unknown HMAC key id for this job")

    path = _CALLBACK_PATH_TEMPLATE.format(job_id=job_id)
    message = canonical_request(
        method="POST",
        path=path,
        worker_id=worker_id,
        body_bytes=body_bytes,
        timestamp=timestamp,
    )
    expected_digest = hmac.new(secret, message, hashlib.sha256).hexdigest()

    # CONSTANT-TIME compare (hmac.compare_digest), never ``==``: a wrong-key or
    # forged digest is rejected without leaking how many leading bytes matched.
    if not hmac.compare_digest(provided_digest, expected_digest):
        raise InvalidHmacError("HMAC digest mismatch")

    # Anti-replay: reject a stale or future-dated timestamp (DOC §3.3, 300s).
    if abs(now() - timestamp) > HMAC_SKEW_WINDOW_SECONDS:
        raise InvalidHmacError("HMAC timestamp outside the 300s anti-replay window")


# ---------------------------------------------------------------------------
# Handler core
# ---------------------------------------------------------------------------


def idempotency_fingerprint(req: ScanRequest) -> str:
    """A stable sha256 fingerprint of the idempotency-relevant body fields.

    DOC-API §3.4: two ``POST /api/v1/scans`` with the same ``Idempotency-Key``
    are "the same request" only if their bodies match. The fingerprint covers the
    fields that determine the scan's identity (``codebase_id``, ``commit_sha``,
    the sorted ``detector_ids``, ``S_version``, ``policy_overrides``); a replay
    whose fingerprint differs is ``409 idempotency_conflict``, not a silent
    return of the original scan.
    """
    payload = "\n".join(
        [
            str(req.codebase_id),
            req.commit_sha,
            ",".join(sorted(req.detector_ids)),
            req.S_version or "",
            repr(sorted(req.policy_overrides.items())),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_scan_request(req: ScanRequest) -> None:
    """Fail-fast input validation (DOC §3.4 ``400 invalid_input``)."""
    if not _COMMIT_SHA_RE.match(req.commit_sha):
        raise InvalidInputError(f"commit_sha must be 40-hex; got {req.commit_sha!r}")
    if not req.detector_ids:
        raise InvalidInputError("detector_ids must contain at least one detector")


def _resolve_s_version(req: ScanRequest, spec_registry: SpecRegistryPort) -> str:
    """Resolve + INV-3-fence ``S_version`` (DOC §6 step 3).

    If omitted: the latest accepted ``S_version``. If supplied: it must be a
    registered, version-pinned row (INV-3 fence) — an unresolvable / unregistered
    reference is ``422 invariant_inv2_violation``, never silently accepted.
    """
    if req.S_version is None:
        resolved = spec_registry.resolve_latest()
        if resolved is None:
            raise InvariantInv2Error("no accepted S_version is available to resolve")
        return resolved
    if not _SEMVER_RE.match(req.S_version):
        raise InvalidInputError(f"S_version must be semver; got {req.S_version!r}")
    if not spec_registry.is_registered(req.S_version):
        raise InvariantInv2Error(
            f"S_version {req.S_version!r} is not a registered, accepted spec "
            "(INV-3 fence: ORCH-01 accepts only version-pinned specs)"
        )
    return req.S_version


def _validate_detectors(req: ScanRequest, registry: DetectorRegistry) -> None:
    """Reject any unknown ``detector_id`` (DOC §6 step 4, ``409 not_found``)."""
    for detector_id in req.detector_ids:
        try:
            registry.by_id(detector_id)
        except KeyError:
            raise DetectorUnknownError(detector_id) from None


def post_scans(
    req: ScanRequest,
    claims: JWTClaims,
    headers: dict[str, str],
    *,
    idempotency_key: UUID,
    trace_id: str,
    guard: CPGuard,
    registry: DetectorRegistry,
    scan_store: ScanStore,
    queue: StandardQueue,
    spec_registry: SpecRegistryPort | None = None,
    snapshot_port: SnapshotPort | None = None,
    hmac_key_issuer: HmacKeyIssuer | None = None,
) -> ScanCreated:
    """Submit a scan: authorize → snapshot-if-absent → fan one job per detector.

    Steps (DOC-CMP-ORCH-01 §6, AC-ORCH-01a):
      1. CP-01 guard: tenancy header ↔ JWT + RBAC (``scans``/POST → ``submit``).
      2. Idempotency: a hit with a matching key returns the existing scan.
      3. Resolve + INV-3-fence ``S_version`` (port; ``422`` if unresolvable).
      4. Validate every ``detector_id`` against the registry (``409`` on unknown).
      5. Resolve/create the snapshot (port → ``snapshot_id``, ``env_digest``).
      6. Persist the ``scans`` row (``status='queued'``, INV-2 fields bound).
      7. Fan ONE :class:`WorkerJob` per detector onto the queue, threading
         ``S_version`` + ``env_digest`` (INV-2) and the CLAR-ORCH-05
         ``hmac_key_id`` + ``callback_path`` onto each.

    The four finding-level provenance fields (``origin``, ``cpg_order_hash``, …)
    are NOT set here — ORCH-01 emits jobs, not findings (DOC §8). The build-ahead
    ports default to fail-closed prod seams (CLAR-PROC-01); a hermetic test
    injects fakes.
    """
    spec_registry = spec_registry if spec_registry is not None else fail_closed_spec_registry()
    snapshot_port = snapshot_port if snapshot_port is not None else fail_closed_snapshot_port()
    key_issuer = hmac_key_issuer if hmac_key_issuer is not None else fail_closed_hmac_key_issuer()

    # Step 1 — authorize FIRST (CP-01 guard; cross-tenant/role-denied → raise).
    envelope = guard.authorize_request(
        claims,
        headers,
        method="POST",
        resource="scans",
        route="/api/v1/scans",
        trace_id=trace_id,
    )
    if envelope is not None:
        raise AuthorizationError(envelope)

    org_id = claims.org_id
    _validate_scan_request(req)
    body_hash = idempotency_fingerprint(req)

    # Step 2 — idempotency replay. Same key + same body → existing scan, no
    # re-enqueue. Same key + DIFFERENT body → 409 idempotency_conflict (DOC §3.4),
    # never a silent return of the first scan.
    existing = scan_store.find_by_idempotency(org_id=org_id, idempotency_key=idempotency_key)
    if existing is not None:
        if existing.idempotency_body_hash != body_hash:
            raise IdempotencyConflictError()
        return ScanCreated(
            scan_id=existing.scan_id,
            snapshot_id=existing.snapshot_id,
            status="queued",
            S_version=existing.S_version,
            env_digest=existing.env_digest,
            job_ids=(),
        )

    # Step 3 — resolve + fence S_version (INV-2 binder / INV-3 fence).
    s_version = _resolve_s_version(req, spec_registry)

    # Step 4 — validate detectors against the registry (409 on unknown).
    _validate_detectors(req, registry)

    # Step 5 — snapshot-if-absent (env_digest is read from the snapshot, INV-2).
    snapshot = snapshot_port.resolve_or_create(
        org_id=org_id, codebase_id=req.codebase_id, commit_sha=req.commit_sha
    )
    if not _ENV_DIGEST_RE.match(snapshot.env_digest):
        # Defence in depth: never thread a malformed env_digest onto a job (INV-2).
        raise InvariantInv2Error(
            f"snapshot env_digest must be 'sha256:'+64hex (INV-2); got {snapshot.env_digest!r}"
        )

    # Step 6 — persist the scans row (INV-2 fields bound, status queued).
    scan_id = uuid4()
    scan_store.put(
        ScanRecord(
            scan_id=scan_id,
            org_id=org_id,
            codebase_id=req.codebase_id,
            snapshot_id=snapshot.snapshot_id,
            commit_sha=req.commit_sha,
            S_version=s_version,
            env_digest=snapshot.env_digest,
            detector_ids=req.detector_ids,
            status="queued",
            idempotency_key=idempotency_key,
            idempotency_body_hash=body_hash,
        )
    )

    # Step 7 — fan ONE WorkerJob per detector, threading INV-2 + CLAR-ORCH-05.
    job_ids: list[UUID] = []
    for detector_id in req.detector_ids:
        job_id = uuid4()
        hmac_key_id, _secret = key_issuer.issue(job_id=job_id, scan_id=scan_id)
        job = WorkerJob(
            job_id=job_id,
            scan_id=scan_id,
            snapshot_id=snapshot.snapshot_id,
            codebase_id=req.codebase_id,
            commit_sha=req.commit_sha,
            detector_id=detector_id,
            S_version=s_version,  # INV-2 — bound at submission, threaded verbatim
            env_digest=snapshot.env_digest,  # INV-2 — from the snapshot
            hmac_key_id=hmac_key_id,  # CLAR-ORCH-05 discharge
            callback_path=_CALLBACK_PATH_TEMPLATE.format(job_id=job_id),
            policy_overrides=dict(req.policy_overrides),
        )
        queue.send(body=_job_to_queue_body(job), dedup_key=str(job_id))
        job_ids.append(job_id)

    return ScanCreated(
        scan_id=scan_id,
        snapshot_id=snapshot.snapshot_id,
        status="queued",
        S_version=s_version,
        env_digest=snapshot.env_digest,
        job_ids=tuple(job_ids),
    )


def _job_to_queue_body(job: WorkerJob) -> dict[str, str]:
    """Project a :class:`WorkerJob` onto the SQS message body (DOC §4.2.2).

    String-typed to match the shipped :class:`StandardQueue` ``Message.body``
    (``dict[str, str]``). The structured re-hydration into a typed ``WorkerJob``
    on the consumer side is CMP-ORCH-03's responsibility; this is the transport
    projection only.

    INTERFACE-SHAPE DEVIATION (reported via ``clar_filed``): DOC §4.2.2's message
    body includes a nested ``policy_overrides`` object. The shipped
    ``StandardQueue.Message.body`` is ``dict[str, str]`` (flat), so a nested dict
    cannot be carried without a JSON-string serialization. ``policy_overrides`` is
    therefore OMITTED from the flat transport projection here (it remains on the
    typed ``WorkerJob`` for the consumer); wiring its serialized form is the
    CLAR-DEPLOY-19 real-SQS follow-up.
    """
    return {
        "job_id": str(job.job_id),
        "scan_id": str(job.scan_id),
        "snapshot_id": str(job.snapshot_id),
        "codebase_id": str(job.codebase_id),
        "commit_sha": job.commit_sha,
        "detector_id": job.detector_id,
        "S_version": job.S_version,
        "env_digest": job.env_digest,
        "hmac_key_id": job.hmac_key_id,
        "callback_path": job.callback_path,
    }


def get_scan(
    scan_id: UUID,
    claims: JWTClaims,
    headers: dict[str, str],
    *,
    trace_id: str,
    guard: CPGuard,
    scan_store: ScanStore,
) -> ScanRecord:
    """Read a scan through the RLS-bound store (DOC §3.1 ``GET /scans/{id}``).

    Authorize (``scans``/GET → ``read``) → read org-scoped. A scan in another
    tenant returns ``404 not_found`` (no existence leak; CMP-CP-01 §9 layer 2).

    INTERFACE-SHAPE DEVIATION (reported via ``clar_filed``): DOC §3.1's read
    surface returns a richer ``ScanState`` (per-job ``JobSummary`` list,
    ``findings_count``, ``attestation_status``, lifecycle status). Those fields
    need the persisted ``jobs`` table + the CP-05 attestation status, both
    DEPLOY-19-gated, so this build-ahead core returns the thin RLS-bound
    :class:`ScanRecord`; the authorization + cross-org ``404`` are the
    load-bearing security legs and ARE exercised here.
    """
    envelope = guard.authorize_request(
        claims,
        headers,
        method="GET",
        resource="scans",
        route="/api/v1/scans/{scan_id}",
        trace_id=trace_id,
    )
    if envelope is not None:
        raise AuthorizationError(envelope)

    record = scan_store.get(scan_id, org_id=claims.org_id)
    if record is None:
        raise ScanNotFoundError()
    return record


def get_scan_findings(
    scan_id: UUID,
    claims: JWTClaims,
    headers: dict[str, str],
    *,
    trace_id: str,
    guard: CPGuard,
    scan_store: ScanStore,
) -> ScanRecord:
    """Read the scan whose findings are requested (DOC §3.1 ``…/findings``).

    The full CMP-FND-01 SARIF page is gated (it needs the persisted ``findings``
    rows + the FND-01 emitter wired to the store); this hermetic core resolves
    and authorizes the scan org-scoped, returning the same RLS-bound
    :class:`ScanRecord` ``get_scan`` does. Authorization (``findings``/GET →
    ``read``) and the cross-org ``404`` are the load-bearing security legs that
    ARE exercised here.
    """
    envelope = guard.authorize_request(
        claims,
        headers,
        method="GET",
        resource="findings",
        route="/api/v1/scans/{scan_id}/findings",
        trace_id=trace_id,
    )
    if envelope is not None:
        raise AuthorizationError(envelope)

    record = scan_store.get(scan_id, org_id=claims.org_id)
    if record is None:
        raise ScanNotFoundError()
    return record


def post_job_status(
    job_id: UUID,
    body: JobStatusReport,
    body_bytes: bytes,
    *,
    hmac_header: str,
    worker_id_header: str,
    timestamp_header: int,
    key_issuer: HmacKeyIssuer,
    scan_store: ScanStore,
    now: Callable[[], int] = lambda: int(time.time()),
) -> None:
    """Worker callback (DOC §3.1 / §6, AC-ORCH-01b) — HMAC-only, fail-closed.

    SIGNED-BYTES CONTRACT (security co-sign C-1, binding for the DEPLOY-19
    adapter): the HMAC verifies ``body_bytes``; the handler acts on the parsed
    ``body``. The caller MUST derive ``body`` by parsing the exact verified
    ``body_bytes`` — never an independent re-read; the HTTP adapter must pin
    ``body == parse(body_bytes)`` structurally.

    Worker callbacks carry NO ``X-Scanipy-Org-Id`` (DOC-API §2.5): tenant identity
    is implicit in the HMAC-keyed job, so this handler does NOT run the CP-01
    tenancy guard — it authenticates by HMAC only.

    Verification happens BEFORE any state mutation (AC-ORCH-01b negative
    contract): a forged digest, a wrong-key signature, an unknown key id, or a
    timestamp outside the 300s window all raise :class:`InvalidHmacError` (401)
    with zero side effect. The HMAC is computed over the EXACT wire ``body_bytes``
    the worker signed (not a re-serialised parse). ``now`` is injected for a
    deterministic skew test.

    On success (returns ``None`` / 204): the durable status transition + the
    ``status=done`` → CMP-FND-01 normalisation + CMP-CP-05 attestation trigger are
    the CLAR-DEPLOY-19 follow-up (they need the persisted ``jobs`` table + the
    downstream queues); this hermetic core is the security-relevant verification
    boundary. The ``job_id`` path param MUST match the body's ``job_id``.
    """
    if body.job_id != job_id:
        # The signed path binds job_id; a body/path mismatch is a forged request.
        raise InvalidHmacError("path job_id does not match body job_id")

    # Authenticate BEFORE touching any state (no mutation on a rejected callback).
    verify_worker_callback_hmac(
        hmac_header=hmac_header,
        worker_id=worker_id_header,
        timestamp=timestamp_header,
        job_id=job_id,
        body_bytes=body_bytes,
        key_issuer=key_issuer,
        now=now,
    )
    # INV-2 fence on the callback body (DOC §6 step b): both required.
    if not body.S_version or not _ENV_DIGEST_RE.match(body.env_digest):
        raise InvalidInputError("worker callback must carry S_version + sha256 env_digest (INV-2)")
    # State transition (durable jobs/scans update + done-triggers) is gated to the
    # CLAR-DEPLOY-19 HTTP-surface follow-up; the verification boundary above is the
    # AC-ORCH-01b security contract this PR makes real.


# ---------------------------------------------------------------------------
# Hermetic RLS-backed ScanStore (over CMP-CP-01's OrgScopedStore)
# ---------------------------------------------------------------------------


@dataclass
class OrgScopedScanStore:
    """A :class:`ScanStore` backed by CMP-CP-01's :class:`OrgScopedStore`.

    Reuses the merged CP-01 RLS stand-in so cross-org reads return ``None`` (the
    layer-2 isolation contract) WITHOUT re-implementing the tenancy check here —
    the store binds ``set_session(org_id)`` per read and a foreign row is
    structurally unreachable. Production binds the SQL store through
    ``db/session.py``'s ``acquire_for_request`` seam; the read shape is identical.
    """

    _store: OrgScopedStore[ScanRecord] = field(default_factory=OrgScopedStore)
    _idempotency: dict[tuple[str, UUID], UUID] = field(default_factory=dict)

    def put(self, record: ScanRecord) -> None:
        self._store.seed(str(record.scan_id), record.org_id, record)
        self._idempotency[(record.org_id, record.idempotency_key)] = record.scan_id

    def get(self, scan_id: UUID, *, org_id: str) -> ScanRecord | None:
        # Bind the request's org (CP-01 SET LOCAL stand-in) then read RLS-scoped:
        # a row owned by another tenant is indistinguishable from a missing one.
        self._store.set_session(org_id)
        try:
            return self._store.query_one(str(scan_id))
        finally:
            self._store.clear_session()

    def find_by_idempotency(self, *, org_id: str, idempotency_key: UUID) -> ScanRecord | None:
        scan_id = self._idempotency.get((org_id, idempotency_key))
        if scan_id is None:
            return None
        return self.get(scan_id, org_id=org_id)


__all__ = [
    "HMAC_SKEW_WINDOW_SECONDS",
    "AuthorizationError",
    "DetectorUnknownError",
    "HmacKeyIssuer",
    "IdempotencyConflictError",
    "InvalidHmacError",
    "InvalidInputError",
    "InvariantInv2Error",
    "JobStatusReport",
    "OrgScopedScanStore",
    "ScanApiError",
    "ScanCreated",
    "ScanNotFoundError",
    "ScanRecord",
    "ScanRequest",
    "ScanStore",
    "SnapshotPort",
    "SnapshotResolution",
    "SpecRegistryPort",
    "TenantIsolationError",
    "canonical_request",
    "fail_closed_hmac_key_issuer",
    "fail_closed_snapshot_port",
    "fail_closed_spec_registry",
    "get_scan",
    "get_scan_findings",
    "idempotency_fingerprint",
    "post_job_status",
    "post_scans",
    "verify_worker_callback_hmac",
]
