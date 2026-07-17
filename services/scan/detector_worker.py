"""CMP-ORCH-03 — detector worker entrypoint (``python -m`` target).

Implementation contract: ``docs/components/DOC-CMP-ORCH-03.md`` (§3 interface,
§4 threading table, §6 data flow, §3.5 error contracts). Cross-cutting:
``.claude/rules/02-provenance.md`` (four-field threading), ``.claude/rules/
05-determinism.md`` (the origin setter, discharged entirely inside the
already-shipped :func:`services.scan.worker.run_detector` — this module never
re-derives ``origin``).

This module is the **ECS Fargate container entrypoint** for the detector
worker: ``workers/detector/Dockerfile`` runs ``ENTRYPOINT ["python", "-m",
"services.scan.detector_worker"]``. Before this module existed the entrypoint
pointed at nothing (verified: no ``services/scan/detector_worker.py`` on disk,
no other ``python -m`` target reachable from that path). It mirrors
``services/snapshot/worker.py``'s ``boot()``/``main()`` shape (same
``SCANIPY_ENV_DIGEST`` fail-closed gate, same entrypoint signature) but wires
the full per-job pipeline end to end, because — unlike CMP-SNAP-05's
execute loop, which is genuinely gated on unbuilt collaborators — every
collaborator this module needs is real and shipped: ``detectors.registry``
(CMP-DET-02), ``services.scan.worker.run_detector`` (CMP-ORCH-03 core,
``worker.py:587``, called here with an UNMODIFIED signature), and
``services.scan.provenance.sign_provenance`` (CMP-FND-03).

Pipeline (task-specified, this track's exact deliverable):

    env-digest gate -> SQS dequeue -> S3 fetch CPG artifact -> deserialize
    into ``analysis.ordering.CPG`` -> ``detectors.registry`` lookup ->
    ``run_detector`` (real, unmodified) -> insert into the ``findings`` ORM
    (``services.scan.models.findings.Finding``) -> ``sign_provenance`` ->
    ack the SQS message.

Every port (queue, object store, findings session, KMS signer) now has a REAL
production default, wired for the first-real-scan shortcut path: a real
boto3-backed ``SQSQueue`` (``DETECTOR_QUEUE_URL``), a real ``S3ObjectStore``
(``S3_BUCKET``), a real SQLAlchemy ``Session`` against Postgres
(``SCANIPY_DATABASE_URL``, with per-job RLS tenant binding — see
:class:`_SqlAlchemyFindingsSession`), and — pending a real per-tenant AWS KMS
CMK, which does not exist yet (CLAR-DEPLOY-24) — an explicitly-flagged
software RSASSA-PSS signer (``services/scan/software_kms_signer.py``, refuses
to run when ``ENV``/``SCANIPY_ENV=prod``). Each production default function
(``_default_queue``, ``_default_object_store``, ``_default_findings_session``,
``_default_signer``) still fails closed with a clear :class:`InvariantViolation`
when its required env var is unset, mirroring the established ``CLAR-PROC-01``
build-ahead pattern (``services.scan.worker``'s ``fail_closed_oracle_adapter``
precedent): :func:`run_detector_job` — the per-job pipeline body — stays
fully real and directly unit-testable against fakes for every I/O boundary
via the same keyword arguments, while ``run_detector`` and the CMP-DET-02
registry run FOR REAL.

KNOWN GAPS (verified during this build; not invented — reported upstream,
not filed as WBS.md CLAR-* rows per this track's explicit instructions):

1. **``org_id`` / ``scm_provider`` are not threaded onto ``WorkerJob``.**
   ``DOC-CMP-ORCH-03`` §4.2's threading table claims ``org_id`` is "carried"
   via ``WorkerJob``, but the shipped ``WorkerJob`` dataclass
   (``services/scan/worker.py``) and its producer
   (``services/scan/api.py::_job_to_queue_body``) carry neither ``org_id``
   nor ``scm_provider`` — both required here: ``org_id`` is a NOT NULL FK on
   ``findings`` and gates every S3 key (``SnapshotKeyBuilder``,
   ``CLAR-DEPLOY-16``); ``scm_provider`` is chain-link 1 of the CMP-FND-03
   provenance record. This module's own message envelope (see
   :func:`parse_job_message`) therefore REQUIRES two additional keys
   (``org_id``, ``scm_provider``) beyond what ``_job_to_queue_body`` emits
   today — documented as this track's own default, pending reconciliation
   with CMP-ORCH-01 (the real fix belongs in ``WorkerJob`` +
   ``_job_to_queue_body``).
2. **Direct-insert deviates from ``DOC-CMP-ORCH-03`` §3.2/§4.2's documented
   design.** The doc specifies CMP-ORCH-03 writes a SARIF blob to S3 and
   reports ``result_uri`` via the HMAC job-status callback, with CMP-FND-01
   (a separate, not-yet-wired persistence path) normalising that SARIF into
   ``findings`` rows. ``services/scan/api.py::post_job_status``'s OWN
   docstring confirms that trigger "stays the wave-2 follow-up" (needs the
   persisted ``jobs`` table + downstream queues). This track's explicit
   instructions direct a simpler **direct ORM insert + ``sign_provenance``**
   path instead, to produce a real ``Finding`` row without also building
   CMP-FND-01's SARIF-consuming persistence layer in this same track. No
   SARIF blob is written by this path, so ``sarif_hash`` is left ``None`` on
   every provenance record it signs.
3. **RESOLVED (CLAR-ORCH-10/CLAR-SNAP-08):** the CPG tarball format is now the
   single shared implementation in ``services/substrate/cpg_tarball.py``,
   imported here (:func:`serialize_cpg_tarball` / :func:`deserialize_cpg_tarball`
   are re-exports) — ``services/snapshot/worker.py`` (the producer) imports the
   same functions, so both sides agree on one gzip-tar, one-member (``cpg.json``)
   format by construction, not by convention. The S3 key suffix
   (``SNAPSHOT_ARTIFACT_SUFFIXES['cpg_tarball']`` = ``cpg.tar.zst``) still names
   zstd for historical reasons even though the bytes are gzip; renaming it is a
   deferred cosmetic follow-up (nothing parses the suffix string itself).
4. **``claim_label`` is derived from ``origin`` alone** (:func:`_claim_label_for`):
   ``deterministic-core -> CONDITIONAL_THEOREM``, ``oracle-passthrough ->
   EMPIRICAL``. ``DOC-PROVENANCE`` §5's full derivation additionally depends
   on the ``(class, language)`` ``CMP-CP-06`` stage-gate verdict (which would
   yield ``STAGED`` pre-gate) — that verdict is not available to this
   entrypoint. This is a documented simplification, not a full INV-6
   discharge.
5. **``snapshot_digest`` has no real DB column** (already-resolved
   ``CLAR-SNAP-02`` confirms the shipped ``snapshots`` table carries none).
   This module defines it as ``"sha256:" + sha256(cpg_tarball_bytes)`` — the
   content digest of the fetched artifact — a reasonable, load-bearing
   definition since ``ProvenanceRecord`` still requires a value.

Boundary discipline (mirrors ``services/snapshot/worker.py``'s own
docstring): this module does not compute ``origin`` (the already-shipped
``run_detector`` is the sole INV-1 setter site, unmodified here), does not
compute ``cpg_order_hash`` (``CMP-CORE-03``, threaded through by
``run_detector``), and does not compute ``slice_fingerprint`` (``CMP-CORE-02``,
also threaded through by ``run_detector``). It only wires already-real
collaborators together and persists their output.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import sqlalchemy
from sqlalchemy.orm import Session as SqlAlchemySession

from detectors.registry import DetectorRegistry
from services.scan.models.findings import Finding as FindingRow
from services.scan.provenance import (
    ClaimLabel,
    InvariantViolation,
    KMSAsymmetricSigner,
    ProvenanceRecord,
    ProvenanceStore,
    SignedProvenanceRecord,
    sign_provenance,
)
from services.scan.software_kms_signer import SoftwareKMSSigner
from services.scan.worker import (
    Finding as WorkerFinding,
)
from services.scan.worker import (
    WorkerJob,
    as_detector_like,
    run_detector,
)
from services.substrate.cpg_tarball import (
    CPG_TARBALL_FORMAT_VERSION,
    CPG_TARBALL_MEMBER_NAME,
    CPGDeserializationError,
    deserialize_cpg_tarball,
    serialize_cpg_tarball,
)
from services.substrate.object_store import ObjectStore, S3ObjectStore, SnapshotKeyBuilder
from services.substrate.queue import ReceivedMessage, SQSQueue
from tools.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Mapping

# ---------------------------------------------------------------------------
# §1 — env-digest fail-closed boot gate (INV-2 ORIGIN)
# ---------------------------------------------------------------------------
#
# Byte-identical CONTRACT to ``services/snapshot/worker.py`` (same env var,
# same regex, same fail-closed semantics) but NOT imported from there: the
# detector worker Docker image (``workers/detector/Dockerfile``) does not
# COPY ``services/snapshot`` (verified), so an import would ModuleNotFoundError
# in the real container. This is therefore a deliberate, minimal duplication
# forced by the image boundary, not drift.

_ENV_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ENV_DIGEST_VAR = "SCANIPY_ENV_DIGEST"

# Tenant-binding GUC names, byte-identical to ``services.control_plane.
# constants.SESSION_VAR_ORG_ID/_USER_ID/_ROLE`` and ``SCANNER_USER_ID`` — NOT
# imported from there (same image-boundary reasoning as resolve_env_digest/
# boot above: workers/detector/Dockerfile does not COPY services/control_plane).
# Used by :class:`_SqlAlchemyFindingsSession` to reproduce db/session.py::
# acquire_for_request's SET LOCAL contract on a SQLAlchemy ORM Session (see
# that module's docstring for the full RLS rationale).
_SESSION_VAR_ORG_ID = "app.org_id"
_SESSION_VAR_USER_ID = "app.user_id"
_SESSION_VAR_ROLE = "app.role"
_SCANNER_USER_ID = "scanner"


class EnvDigestMissing(Exception):  # noqa: N818 — name fixed verbatim by DOC-CMP-SNAP-05 §3.4 precedent
    """``SCANIPY_ENV_DIGEST`` was unset/empty/malformed at boot (fail-closed).

    INV-2 requires a real ``env_digest`` (the running image digest); the
    worker refuses to start without one.
    """


def resolve_env_digest(environ: dict[str, str] | None = None) -> str:
    """Return the authoritative ``env_digest`` from the runtime-injected env var.

    See ``services/snapshot/worker.py::resolve_env_digest`` — identical
    contract, duplicated here because the detector worker image does not
    include that module (see module docstring).
    """
    env = os.environ if environ is None else environ
    candidate = env.get(ENV_DIGEST_VAR, "")
    if not candidate:
        raise EnvDigestMissing(
            f"INV-2: {ENV_DIGEST_VAR} must be injected from the running image "
            "digest before the worker starts; the worker refuses to run against "
            "an unpinned Env (DOC-CMP-ORCH-03 §3.5)"
        )
    if not _ENV_DIGEST_RE.fullmatch(candidate):
        raise EnvDigestMissing(
            f"INV-2: {ENV_DIGEST_VAR}={candidate!r} is not a pinned container "
            "image digest matching 'sha256:<64-hex>'; fail-closed (the env_digest "
            "must be a real image digest, never a default or placeholder)"
        )
    return candidate


def boot(environ: dict[str, str] | None = None) -> str:
    """Run the worker boot gate and return the bound ``env_digest``.

    The single fail-closed step the worker performs before any job work
    (INV-2 ORIGIN). Mirrors ``services/snapshot/worker.py::boot`` exactly.
    """
    return resolve_env_digest(environ)


# ---------------------------------------------------------------------------
# §2 — CPG tarball (de)serialization: moved to services/substrate/cpg_tarball.py
# (CLAR-ORCH-10/CLAR-SNAP-08 resolution — a single shared implementation, not
# two independently-drifting copies) and re-exported above for import-site
# compatibility (``from services.scan.detector_worker import
# serialize_cpg_tarball`` still resolves).
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# §3 — job-message envelope (this track's own default; see KNOWN GAP 1)
# ---------------------------------------------------------------------------


class MalformedJobMessageError(Exception):
    """The SQS message body failed this worker's job-envelope contract.

    DOC-CMP-ORCH-03 §3.5: "SQS message body fails ... validation -> Reject;
    SQS retry up to max-receive=3 then DLQ."
    """


# Keys CMP-ORCH-01 already emits today (services/scan/api.py::_job_to_queue_body).
_WORKER_JOB_KEYS: tuple[str, ...] = (
    "job_id",
    "scan_id",
    "snapshot_id",
    "codebase_id",
    "commit_sha",
    "detector_id",
    "S_version",
    "env_digest",
)

# Keys this module additionally requires that ``_job_to_queue_body`` does NOT
# yet emit (KNOWN GAP 1 in the module docstring) — this track's own envelope
# extension, pending CMP-ORCH-01 reconciliation.
_EXTRA_ENVELOPE_KEYS: tuple[str, ...] = ("org_id", "scm_provider")


def parse_job_message(body: Mapping[str, str]) -> tuple[WorkerJob, uuid.UUID, str]:
    """Parse a dequeued SQS message body into ``(WorkerJob, org_id, scm_provider)``.

    Fail-closed: any missing/malformed required field raises
    :class:`MalformedJobMessageError` rather than guessing a default (mirrors
    DOC-CMP-ORCH-03 §3.5's validation-failure contract). ``hmac_key_id`` /
    ``callback_path`` are accepted if present (parity with the real
    ``WorkerJob``) but are not used by this direct-insert path (KNOWN GAP 2).
    """
    missing = [k for k in (*_WORKER_JOB_KEYS, *_EXTRA_ENVELOPE_KEYS) if not body.get(k)]
    if missing:
        raise MalformedJobMessageError(
            f"detector job message missing required field(s): {missing!r}"
        )
    try:
        job = WorkerJob(
            job_id=uuid.UUID(body["job_id"]),
            scan_id=uuid.UUID(body["scan_id"]),
            snapshot_id=uuid.UUID(body["snapshot_id"]),
            codebase_id=uuid.UUID(body["codebase_id"]),
            commit_sha=body["commit_sha"],
            detector_id=body["detector_id"],
            S_version=body["S_version"],
            env_digest=body["env_digest"],
            hmac_key_id=body.get("hmac_key_id", ""),
            callback_path=body.get("callback_path", ""),
        )
        org_id = uuid.UUID(body["org_id"])
    except ValueError as exc:
        raise MalformedJobMessageError(f"detector job message failed to parse: {exc}") from exc
    return job, org_id, body["scm_provider"]


# ---------------------------------------------------------------------------
# §4 — typed I/O ports + fail-closed production defaults (CLAR-PROC-01 pattern)
# ---------------------------------------------------------------------------


@runtime_checkable
class QueuePort(Protocol):
    """The queue surface this worker consumes.

    Structurally satisfied by the already-real, in-memory
    ``services.substrate.queue.StandardQueue`` today, and by the real
    boto3-backed SQS queue Track 1E is building (same
    receive/ack/fail shape, DOC-CMP-DEPLOY-01 §6.1).
    """

    def receive(self) -> ReceivedMessage | None: ...
    def ack(self, receipt_handle: int) -> None: ...
    def fail(self, receipt_handle: int) -> None: ...


@runtime_checkable
class FindingsSession(Protocol):
    """Structural subset of a SQLAlchemy ``Session`` this module writes through.

    Any object exposing ``add``/``commit`` satisfies this: the real production
    default is :class:`_SqlAlchemyFindingsSession` (below), which wraps a real
    ``sqlalchemy.orm.Session``; tests inject a lightweight in-memory fake.
    """

    def add(self, instance: object) -> None: ...
    def commit(self) -> None: ...


def _default_queue(environ: Mapping[str, str]) -> QueuePort:
    """Production ``QueuePort`` default: a REAL ``SQSQueue`` (lazy boto3).

    Mirrors ``services/snapshot/worker.py::_default_snapshot_queue`` exactly.
    ``DETECTOR_QUEUE_URL`` is already provisioned on the live ECS task
    definition (verified 2026-07-17: ``aws ecs describe-task-definition
    --task-definition scanipy-detector-worker``) — this is pure wiring, not a
    new design decision.
    """
    queue_url = environ.get("DETECTOR_QUEUE_URL")
    if not queue_url:
        raise InvariantViolation(
            "DETECTOR_QUEUE_URL must be set; refusing to construct an unbound SQSQueue",
            code="missing_detector_queue_url",
        )
    return SQSQueue(queue_url)


def _default_object_store(environ: Mapping[str, str]) -> ObjectStore:
    """Production ``ObjectStore`` default: a REAL ``S3ObjectStore`` (lazy boto3).

    Mirrors ``services/snapshot/worker.py::_default_object_store`` exactly.
    ``S3_BUCKET`` is already provisioned on the live ECS task definition
    (verified 2026-07-17) — pure wiring.
    """
    bucket = environ.get("S3_BUCKET")
    if not bucket:
        raise InvariantViolation(
            "S3_BUCKET must be set; refusing to construct an unbucketed S3ObjectStore",
            code="missing_s3_bucket",
        )
    return S3ObjectStore(bucket)


class _SqlAlchemyFindingsSession:
    """Production ``FindingsSession`` default: a real ``sqlalchemy.orm.Session``
    with per-tenant RLS binding.

    ``FindingsSession``'s own Protocol docstring names ``db/session.py::
    acquire_for_request`` as the intended production binder, but that function
    operates on a raw DB-API ``Connection`` (cursor-based ``SET LOCAL``), not
    an ORM ``Session`` — a real shape mismatch, since ``run_detector_job``
    calls ``findings_session.add(FindingRow_instance)`` against the real
    SQLAlchemy-mapped ``services.scan.models.findings.Finding``. This adapter
    reproduces ``acquire_for_request``'s exact GUC-binding contract
    (``SELECT set_config('app.org_id', ..., true)`` etc — DOC-DB §3.2) via
    ``Session.execute`` instead of a raw cursor, adapted to the fact that
    ``org_id`` is only known per-job (from the dequeued message), not at
    session-construction time (``run_execute_loop`` builds this once and
    reuses it across many jobs, possibly spanning tenants).

    Binds on every ``add()`` call (idempotent within a transaction — ``SET
    LOCAL`` re-setting the same value is a no-op cost, not a correctness
    issue) so a job whose org differs from the previous job's is always
    correctly scoped, and re-binds again after every ``commit()`` since ``SET
    LOCAL`` is discarded at commit (the same transaction-boundary-is-binding-
    boundary property ``acquire_for_request`` relies on).

    Per RLS grants (``db/migrations/versions/20260524_0001_...py`` CLAR-DB-02):
    ``scanipy_app`` — NOT ``scanipy_system``/BYPASSRLS — already holds
    INSERT on ``findings``/``provenance_records`` and is exactly the role
    every RLS-scoped write should go through; this worker does not need (and
    must not attempt) a ``BYPASSRLS`` connection. Whether the live connection
    role (``SCANIPY_DATABASE_URL``'s user) is itself a member of
    ``scanipy_app`` was not independently verifiable from this sandbox (the
    RDS instance sits in an isolated private subnet with no network path
    here, confirmed via a direct connect timeout) — if the grant is missing,
    the first live INSERT fails with a clear Postgres permission-denied
    error, not a silent isolation bug; see CLAR-DEPLOY-24.
    """

    def __init__(self, session: SqlAlchemySession) -> None:
        self._session = session
        self._bound_org_id: str | None = None

    def _bind_tenant(self, org_id: str) -> None:
        for name, value in (
            (_SESSION_VAR_ORG_ID, org_id),
            (_SESSION_VAR_USER_ID, _SCANNER_USER_ID),
            (_SESSION_VAR_ROLE, "scanner"),
        ):
            self._session.execute(
                sqlalchemy.text("SELECT set_config(:name, :value, true)"),
                {"name": name, "value": value},
            )
        self._bound_org_id = org_id

    def add(self, instance: object) -> None:
        org_id = getattr(instance, "org_id", None)
        if org_id is not None and str(org_id) != self._bound_org_id:
            self._bind_tenant(str(org_id))
        self._session.add(instance)

    def commit(self) -> None:
        self._session.commit()
        # SET LOCAL is discarded at COMMIT (DOC-DB §3.2) — force a re-bind on
        # the next add(), even if the next job is the same org.
        self._bound_org_id = None


def _default_findings_session(environ: Mapping[str, str]) -> FindingsSession:
    """Production ``FindingsSession`` default: a real Postgres-backed ORM Session.

    ``SCANIPY_DATABASE_URL`` is NOT currently provisioned on the live ECS task
    definition (verified 2026-07-17 — ``secrets: null``); wiring it in is
    tracked alongside this change (CLAR-DEPLOY-24) as an ECS task-def update
    (new revision adding a ``secrets`` entry sourced from the already-live
    Secrets Manager secret ``scanipy/dev/database_url``), not a code gap.
    """
    database_url = environ.get("SCANIPY_DATABASE_URL")
    if not database_url:
        raise InvariantViolation(
            "SCANIPY_DATABASE_URL must be set; refusing to construct an unbound DB session",
            code="missing_database_url",
        )
    engine = sqlalchemy.create_engine(database_url)
    return _SqlAlchemyFindingsSession(SqlAlchemySession(bind=engine))


def _default_signer(environ: Mapping[str, str]) -> KMSAsymmetricSigner:
    """Production ``KMSAsymmetricSigner`` default: the CLAR-DEPLOY-24 shortcut.

    No real per-tenant AWS KMS CMK exists yet (verified 2026-07-17 — see
    ``services/scan/software_kms_signer.py``'s module docstring for the full
    two-part gap: no provisioned CMK, and the ``KeyVersion``-per-signature
    Protocol contract not mapping onto AWS KMS's no-rotation-for-asymmetric-
    keys semantics). Until both are resolved, this constructs the explicitly
    test/dev-flagged software signer, which itself refuses at construction
    when ``ENV``/``SCANIPY_ENV`` is ``"prod"`` (CLAR-DEPLOY-24, mirrors
    CLAR-CP-01-02's established test-only-bypass pattern).
    """
    return SoftwareKMSSigner(env=environ)


def default_registry() -> DetectorRegistry:
    """Load the real CMP-DET-02 registry from ``detectors/``.

    ``DetectorRegistry.load_manifests`` is a one-shot operation (frozen after
    load, DOC-CMP-DET-02 §3.2): callers that process multiple jobs should call
    this ONCE and reuse the result (see :func:`run_execute_loop`), never
    reload per message.
    """
    registry = DetectorRegistry()
    registry.load_manifests("detectors/")
    return registry


# ---------------------------------------------------------------------------
# §5 — the per-job pipeline (this track's core deliverable)
# ---------------------------------------------------------------------------


class DetectorNotFoundError(Exception):
    """``WorkerJob.detector_id`` has no entry in the CMP-DET-02 registry.

    DOC-CMP-ORCH-03 §3.5: "Detector unknown in registry -> Worker fails;
    reports status=failed with error.code = 'detector_not_found'."
    """


class EnvDigestMismatchError(Exception):
    """``job.env_digest`` (the SQS message's claim) does not match this
    worker's boot-time ``SCANIPY_ENV_DIGEST`` (INV-2 authoritative value) —
    a stale or replayed message. Fail-closed rather than thread a wrong
    ``env_digest`` into provenance."""


def _claim_label_for(origin: str) -> ClaimLabel:
    """Derive ``claim_label`` from ``origin`` alone (KNOWN GAP 4 — does not
    consult the CMP-CP-06 stage-gate verdict, so this never produces
    ``STAGED``; DOC-PROVENANCE §5's full derivation is a superset of this)."""
    return "CONDITIONAL_THEOREM" if origin == "deterministic-core" else "EMPIRICAL"


@dataclass(frozen=True)
class DetectorJobResult:
    """What one detector job produced — returned for caller/test assertions."""

    findings: tuple[WorkerFinding, ...]
    signed_records: tuple[SignedProvenanceRecord, ...]


def run_detector_job(
    job: WorkerJob,
    *,
    org_id: uuid.UUID,
    scm_provider: str,
    object_store: ObjectStore,
    findings_session: FindingsSession,
    signer: KMSAsymmetricSigner,
    kms_key_arn: str,
    registry: DetectorRegistry,
    provenance_store: ProvenanceStore | None = None,
    boot_env_digest: str | None = None,
) -> DetectorJobResult:
    """The per-job pipeline: S3 fetch -> deserialize -> registry lookup ->
    ``run_detector`` (real, UNMODIFIED signature) -> ORM insert ->
    ``sign_provenance``.

    Never touches the queue (ack/fail is the caller's responsibility, see
    :func:`handle_queue_message`), so this is the directly unit-testable
    hermetic core: every I/O boundary (``object_store``, ``findings_session``,
    ``signer``) is an injectable fake while ``run_detector`` and the
    CMP-DET-02 registry run FOR REAL end to end.

    ``boot_env_digest``, when supplied (the container's own pinned
    ``SCANIPY_ENV_DIGEST`` from :func:`boot`), is cross-checked against
    ``job.env_digest`` (the SQS message's claim) before any work starts. A
    stale or replayed message carrying a mismatched ``env_digest`` is
    refused fail-closed rather than silently threading a wrong INV-2 value
    into provenance (caught by claude-review on PR #320). ``None`` skips the
    check — the existing 14 hermetic tests that construct a ``WorkerJob``
    directly, independent of a real boot sequence, are unaffected.
    """
    if boot_env_digest is not None and job.env_digest != boot_env_digest:
        raise EnvDigestMismatchError(
            f"job.env_digest {job.env_digest!r} does not match this worker's "
            f"boot-time env_digest {boot_env_digest!r} (INV-2) — refusing to "
            "thread a stale or mismatched env_digest into provenance"
        )
    try:
        detector = registry.by_id(job.detector_id)
    except KeyError as exc:
        raise DetectorNotFoundError(
            f"detector {job.detector_id!r} not found in the CMP-DET-02 registry"
        ) from exc

    key = SnapshotKeyBuilder(
        org_id=str(org_id),
        codebase_id=str(job.codebase_id),
        commit_sha=job.commit_sha,
        env_digest=job.env_digest,
    ).artifact_key("cpg_tarball")
    cpg_bytes = object_store.get(str(org_id), key)
    cpg = deserialize_cpg_tarball(cpg_bytes)
    # KNOWN GAP 5 — no real snapshot_digest DB column exists (CLAR-SNAP-02
    # RESOLVED); this is the content digest of the fetched artifact.
    snapshot_digest = "sha256:" + hashlib.sha256(cpg_bytes).hexdigest()

    findings = run_detector(as_detector_like(detector), cpg, job)
    # run_detector returns set[Finding] (DOC-CMP-ORCH-03 §3.1's eq=False/
    # identity-hash design) — Python set iteration order is not guaranteed
    # stable across interpreter invocations (hash randomization). Normally
    # CMP-FND-01's normalize() re-keys by the canonical sort tuple downstream,
    # but this track's direct-insert path (KNOWN GAP 2) bypasses FND-01
    # entirely, so an unsorted iteration here becomes the literal, unstable
    # DB insertion order and breaks the CP-05 byte-identical-SARIF guarantee.
    # Caught by claude-review on PR #320.
    sorted_findings = sorted(findings, key=lambda f: (f.rule_id, f.uri, f.start_line, f.start_col))

    signed_records: list[SignedProvenanceRecord] = []
    for f in sorted_findings:
        # INV-5 fail-closed guard: bytes.fromhex("") == b"" with no error, so
        # an unset/malformed cpg_order_hash or slice_fingerprint would
        # otherwise silently persist a 0-byte value instead of surfacing the
        # upstream threading bug. Caught by claude-review on PR #320.
        if len(f.cpg_order_hash) != 64:
            raise ValueError(
                f"cpg_order_hash must be 64 hex chars (INV-5); got {f.cpg_order_hash!r} "
                f"for rule {f.rule_id!r} at {f.uri}:{f.start_line}"
            )
        if len(f.slice_fingerprint) != 64:
            raise ValueError(
                f"slice_fingerprint must be 64 hex chars (CMP-CORE-02); got "
                f"{f.slice_fingerprint!r} for rule {f.rule_id!r} at {f.uri}:{f.start_line}"
            )
        finding_id = uuid.uuid4()
        row = FindingRow(
            id=finding_id,
            org_id=org_id,
            codebase_id=job.codebase_id,
            scan_id=job.scan_id,
            snapshot_id=job.snapshot_id,
            commit_sha=job.commit_sha,
            class_=f.class_,
            rule_id=f.rule_id,
            severity=f.severity,
            message=f.message,
            physical_location={
                "uri": f.uri,
                "start_line": f.start_line,
                "start_col": f.start_col,
                "end_line": f.end_line,
                "end_col": f.end_col,
            },
            origin=f.origin,
            determinism_partition=f.determinism_partition,
            engine=f.engine,
            S_version=f.S_version,
            env_digest=f.env_digest,
            cpg_order_hash=bytes.fromhex(f.cpg_order_hash),
            cpg_order_hash_annotation=f.cpg_order_hash_annotation,
            fingerprint_class=f.fingerprint_class,
            slice_fingerprint=bytes.fromhex(f.slice_fingerprint),
            witness_blob_uri=f.witness_blob_uri,
            precondition_status=f.precondition_status,
            spec_provenance=f.spec_provenance,
            status=f.status,
        )
        findings_session.add(row)

        record = ProvenanceRecord(
            id=uuid.uuid4(),
            parent_record_id=None,
            record_type="chain",
            scan_id=job.scan_id,
            finding_id=finding_id,
            org_id=org_id,
            codebase_id=job.codebase_id,
            commit_sha=job.commit_sha,
            scm_provider=scm_provider,
            snapshot_id=job.snapshot_id,
            snapshot_digest=snapshot_digest,  # type: ignore[arg-type]
            precondition_status=f.precondition_status,  # type: ignore[arg-type]
            S_version=f.S_version,  # type: ignore[arg-type]
            env_digest=f.env_digest,  # type: ignore[arg-type]
            cpg_order_hash=bytes.fromhex(f.cpg_order_hash),  # type: ignore[arg-type]
            cpg_order_hash_annotation=f.cpg_order_hash_annotation,
            fingerprint_class=f.fingerprint_class,  # type: ignore[arg-type]
            witness_blob_uri=f.witness_blob_uri,
            slice_fingerprint=bytes.fromhex(f.slice_fingerprint),  # type: ignore[arg-type]
            rule_id=f.rule_id,
            # No separate spec_id source on WorkerFinding: the solver sets
            # rule_id from sf.spec_id (services/scan/worker.py:559), so they
            # are the same value in this system.
            spec_id=f.rule_id,
            detector_id=job.detector_id,
            detector_engine=f.engine,  # type: ignore[arg-type]
            # KNOWN GAP 2 — no SARIF blob is written by this direct-insert path.
            sarif_hash=None,
            origin=f.origin,
            determinism_partition=f.determinism_partition,
            repartition_reason=None,
            repartition_oracle_id=None,
            claim_label=_claim_label_for(f.origin),
        )
        signed = sign_provenance(
            record,
            signer=signer,
            kms_key_arn=kms_key_arn,
            store=provenance_store,
        )
        signed_records.append(signed)

    findings_session.commit()
    return DetectorJobResult(findings=tuple(findings), signed_records=tuple(signed_records))


def handle_queue_message(
    received: ReceivedMessage,
    *,
    queue: QueuePort,
    object_store: ObjectStore,
    findings_session: FindingsSession,
    signer: KMSAsymmetricSigner,
    kms_key_arn: str,
    registry: DetectorRegistry,
    provenance_store: ProvenanceStore | None = None,
    boot_env_digest: str | None = None,
) -> DetectorJobResult | None:
    """Parse + run one dequeued message, then ack/fail it.

    On any failure (malformed envelope, unknown detector, deserialization
    error, or any pipeline exception): logs, fails the message back to the
    queue (redelivery / DLQ per ``CLAR-DEPLOY-06`` max-receive semantics —
    mirrors the already-shipped ``IdempotentConsumer.poll_once`` posture of
    never crashing the whole worker process on one poison message), and
    returns ``None``. On success: acks and returns the
    :class:`DetectorJobResult`.
    """
    try:
        job, org_id, scm_provider = parse_job_message(received.message.body)
        result = run_detector_job(
            job,
            org_id=org_id,
            scm_provider=scm_provider,
            object_store=object_store,
            findings_session=findings_session,
            signer=signer,
            kms_key_arn=kms_key_arn,
            registry=registry,
            provenance_store=provenance_store,
            boot_env_digest=boot_env_digest,
        )
    except Exception:
        get_logger("detector-worker").exception(
            "detector job failed; failing message back to the queue",
        )
        # queue.fail() can itself raise (e.g. StandardQueue.UnknownReceiptError
        # if SQS already reclaimed the message after a visibility timeout) —
        # that secondary exception must not crash the worker process out from
        # under an otherwise-recoverable failure. Caught by claude-review on
        # PR #320.
        try:
            queue.fail(received.receipt_handle)
        except Exception:
            get_logger("detector-worker").exception(
                "queue.fail() raised while handling a prior failure; "
                "message may redeliver on its own via the queue's visibility timeout",
            )
        return None
    try:
        queue.ack(received.receipt_handle)
    except Exception:
        get_logger("detector-worker").exception(
            "queue.ack() raised after a successful detector job; "
            "the job's own side effects (findings insert, provenance sign) "
            "already committed, so a duplicate redelivery is the only risk",
        )
    return result


# ---------------------------------------------------------------------------
# §6 — execute loop + container entrypoint (mirrors services/snapshot/worker.py)
# ---------------------------------------------------------------------------

_POLL_IDLE_SECONDS = 5.0


def run_execute_loop(
    env_digest: str,
    *,
    queue: QueuePort | None = None,
    object_store: ObjectStore | None = None,
    findings_session: FindingsSession | None = None,
    signer: KMSAsymmetricSigner | None = None,
    kms_key_arn: str = "",
    registry: DetectorRegistry | None = None,
    provenance_store: ProvenanceStore | None = None,
    environ: Mapping[str, str] | None = None,
) -> None:  # pragma: no cover — infinite production loop; handle_queue_message /
    # run_detector_job are the directly-tested units (tests/unit/test_detector_worker_specs.py)
    """The per-job SQS execute loop (mirrors ``services/snapshot/worker.py::
    run_execute_loop``'s shape). ``env_digest`` is the bound boot-time digest
    (INV-2 ORIGIN); it is NOT re-threaded onto findings — ``run_detector``
    already threads ``job.env_digest`` (from the job itself) onto every
    finding, so re-deriving it here would risk a second, divergent source of
    truth. It IS, however, cross-checked against every dequeued job's own
    ``env_digest`` claim (via ``run_detector_job(..., boot_env_digest=...)``)
    so a stale or replayed message is refused fail-closed before any work
    starts, rather than silently threading a mismatched INV-2 value into
    provenance (caught by claude-review on PR #320).

    Every port defaults to a REAL production collaborator, resolved from
    ``environ`` (defaults to :data:`os.environ`): ``queue``/``object_store``
    read ``DETECTOR_QUEUE_URL``/``S3_BUCKET`` (already provisioned on the live
    ECS task definition) and fail closed with :class:`InvariantViolation` if
    unset; ``findings_session`` builds a real SQLAlchemy session from
    ``SCANIPY_DATABASE_URL``; ``signer`` is the CLAR-DEPLOY-24 software
    stand-in (no real per-tenant KMS CMK exists yet — see
    ``services/scan/software_kms_signer.py``). A hermetic test injects fakes
    for all of these via the keyword arguments directly.
    """
    env = os.environ if environ is None else environ
    queue = queue if queue is not None else _default_queue(env)
    object_store = object_store if object_store is not None else _default_object_store(env)
    findings_session = (
        findings_session if findings_session is not None else _default_findings_session(env)
    )
    signer = signer if signer is not None else _default_signer(env)
    # No real per-tenant CMK ARN exists yet (CLAR-DEPLOY-24); KMS_KEY_ARN lets
    # a future real binding opt in without a code change, but the software
    # signer does not parse this as a real ARN — it is stored/threaded as an
    # opaque provenance-record label either way.
    kms_key_arn = kms_key_arn or env.get("KMS_KEY_ARN", "software-dev-signer")
    registry = registry if registry is not None else default_registry()

    while True:
        received = queue.receive()
        if received is None:
            time.sleep(_POLL_IDLE_SECONDS)
            continue
        handle_queue_message(
            received,
            queue=queue,
            object_store=object_store,
            findings_session=findings_session,
            signer=signer,
            kms_key_arn=kms_key_arn,
            registry=registry,
            provenance_store=provenance_store,
            boot_env_digest=env_digest,
        )


def main(argv: list[str] | None = None) -> int:
    """Container entrypoint: fail-closed boot gate, then the execute loop.

    Wired by ``ENTRYPOINT ["python", "-m", "services.scan.detector_worker"]``.
    Mirrors ``services/snapshot/worker.py::main`` exactly: bind ``env_digest``
    or refuse to start (exit non-zero); log; hand off to
    :func:`run_execute_loop`.
    """
    _ = argv  # the worker takes no CLI args; ECS injects config via env vars.
    try:
        env_digest = boot()
    except EnvDigestMissing as exc:
        print(f"FATAL (INV-2 fail-closed): {exc}", file=sys.stderr)
        return 1
    get_logger("detector-worker").info("detector worker boot: env_digest bound")
    run_execute_loop(env_digest)
    return 0  # pragma: no cover — unreachable while ports are fail-closed defaults


__all__ = [
    "CPG_TARBALL_FORMAT_VERSION",
    "CPG_TARBALL_MEMBER_NAME",
    "ENV_DIGEST_VAR",
    "CPGDeserializationError",
    "DetectorJobResult",
    "DetectorNotFoundError",
    "EnvDigestMissing",
    "FindingsSession",
    "MalformedJobMessageError",
    "QueuePort",
    "boot",
    "default_registry",
    "deserialize_cpg_tarball",
    "handle_queue_message",
    "main",
    "parse_job_message",
    "resolve_env_digest",
    "run_detector_job",
    "run_execute_loop",
    "serialize_cpg_tarball",
]


if __name__ == "__main__":  # pragma: no cover — exercised only as the container entrypoint.
    sys.exit(main())
