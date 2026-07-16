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

The genuinely-unbuilt collaborators (a real boto3-backed SQS queue — Track
1E; a live S3 bucket / KMS CMK / Postgres session — Track 1D) are typed ports
with **fail-closed production defaults**, exactly mirroring the established
``CLAR-PROC-01`` build-ahead pattern already used by
``services.scan.worker`` (``fail_closed_oracle_adapter``,
``fail_closed_slice_fingerprinter``): the production seam raises a typed
``NotImplementedError`` naming the gated dependency; a hermetic test injects a
deterministic fake. :func:`run_detector_job` — the per-job pipeline body — is
therefore fully real and directly unit-testable against fakes for every I/O
boundary while ``run_detector`` and the CMP-DET-02 registry run FOR REAL.

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
3. **CPG tarball format is this track's own default**, pending confirmation
   from the CPG-ingestion track (1A/1B did not exist yet when this was
   built): a gzip-compressed tar containing one member, ``cpg.json``, with
   ``{"format_version": "1", "nodes": [...], "edges": [...]}`` — see
   :func:`serialize_cpg_tarball` / :func:`deserialize_cpg_tarball`. NOTE: the
   already-shipped ``services.substrate.object_store.SNAPSHOT_ARTIFACT_SUFFIXES``
   names the ``cpg_tarball`` artifact key suffix ``cpg.tar.zst`` (zstd); this
   module still fetches at THAT key path (so it resolves to wherever the
   snapshot worker eventually writes), but the byte CONTENTS here are gzip,
   not zstd, because no zstd dependency is pinned anywhere in this repo. The
   suffix naming and the compression format need Wave-2 reconciliation with
   whichever track actually writes this artifact.
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

import gzip
import hashlib
import io
import json
import os
import re
import sys
import tarfile
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from detectors.registry import DetectorRegistry
from services.scan.models.findings import Finding as FindingRow
from services.scan.provenance import (
    ClaimLabel,
    KMSAsymmetricSigner,
    ProvenanceRecord,
    ProvenanceStore,
    SignedProvenanceRecord,
    sign_provenance,
)
from services.scan.worker import (
    Finding as WorkerFinding,
)
from services.scan.worker import (
    WorkerJob,
    as_detector_like,
    run_detector,
)
from services.substrate.object_store import ObjectStore, SnapshotKeyBuilder
from services.substrate.queue import ReceivedMessage
from tools.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Mapping

    from analysis.ordering import CPG

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
# §2 — CPG tarball (de)serialization (this track's own default; see KNOWN GAP 3)
# ---------------------------------------------------------------------------

CPG_TARBALL_MEMBER_NAME = "cpg.json"
CPG_TARBALL_FORMAT_VERSION = "1"


class CPGDeserializationError(Exception):
    """The fetched CPG tarball does not satisfy this module's own format
    contract (fail-closed; mirrors DOC-CMP-ORCH-03 §3.5's "message fails
    validation -> reject" posture for the CPG artifact instead of the SQS
    message)."""


def serialize_cpg_tarball(cpg: CPG) -> bytes:
    """Serialize ``cpg`` to this track's own default tarball format.

    A gzip-compressed tar with one member, ``cpg.json``:
    ``{"format_version": "1", "nodes": [...], "edges": [...]}``, where each
    node object mirrors ``analysis.ordering.CPGNode`` field-for-field
    (``node_id`` is the array POSITION — dense ``0..N-1`` in the CPG's own
    insertion order, per INV-5's node-emission-order requirement) and each
    edge mirrors ``analysis.ordering.CPGEdge`` field-for-field. Provided so a
    producer (this track's own tests, and eventually the real CPG-ingestion
    track) has a concrete, importable reference implementation of the format
    documented in the module docstring.
    """
    payload = {
        "format_version": CPG_TARBALL_FORMAT_VERSION,
        "nodes": [
            {
                "node_id": int(n.node_id),
                "kind": n.kind,
                "operator_or_literal": n.operator_or_literal,
                "resolved_fqn": n.resolved_fqn,
                "enclosing_decl_fqn": n.enclosing_decl_fqn,
                "structural_path": n.structural_path,
            }
            for n in cpg.nodes
        ],
        "edges": [{"src": int(e.src), "dst": int(e.dst), "kind": e.kind} for e in cpg.edges],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    buf = io.BytesIO()
    # tarfile's "w:gz" mode delegates to gzip.GzipFile with its default
    # mtime=time.time() — pinning only the TAR member's info.mtime (below)
    # leaves the *gzip wrapper header* embedding wall-clock time, so two
    # calls on identical input still produce different bytes. Open the
    # gzip layer explicitly with mtime=0 so the whole archive is
    # byte-deterministic across re-runs (caught by claude-review on PR #320).
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w|") as tar:
            info = tarfile.TarInfo(name=CPG_TARBALL_MEMBER_NAME)
            info.size = len(raw)
            info.mtime = 0  # deterministic archive bytes across re-runs
            tar.addfile(info, io.BytesIO(raw))
    return buf.getvalue()


def deserialize_cpg_tarball(data: bytes) -> CPG:
    """Deserialize this track's own default tarball format into a real
    :class:`analysis.ordering.CPG` (fail-closed on any shape violation).

    Trusts the producer's node ORDER (position in the ``nodes`` array) as the
    canonical insertion order — this consumer never re-sorts nodes (INV-5's
    node-emission-order requirement is the PRODUCER's obligation, per the
    plan's Provenance section: "the mapper must impose its own fixed,
    deterministic node-emission order... never trust whatever order Joern's
    export array happens to produce"). It only verifies the contract: each
    node's declared ``node_id`` must equal its array position (dense
    ``0..N-1``), and edges may only reference in-range node ids.
    """
    from analysis.ordering import CPG, NodeId  # local import: keeps CPG optional at module import

    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            member = tar.getmember(CPG_TARBALL_MEMBER_NAME)
            extracted = tar.extractfile(member)
            if extracted is None:  # pragma: no cover — extractfile(regular file) never None
                raise CPGDeserializationError(
                    f"tarball member {CPG_TARBALL_MEMBER_NAME!r} is not a regular file"
                )
            raw = extracted.read()
    except (tarfile.TarError, KeyError) as exc:
        raise CPGDeserializationError(f"malformed CPG tarball: {exc}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CPGDeserializationError(f"CPG tarball member is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict) or "nodes" not in payload or "edges" not in payload:
        raise CPGDeserializationError(
            "CPG tarball JSON must be an object with 'nodes' and 'edges' keys"
        )
    nodes, edges = payload["nodes"], payload["edges"]
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise CPGDeserializationError("CPG tarball 'nodes'/'edges' must both be arrays")

    cpg = CPG()
    for position, raw_node in enumerate(nodes):
        if not isinstance(raw_node, dict):
            raise CPGDeserializationError(f"node at position {position} is not an object")
        node_id = raw_node.get("node_id")
        if node_id != position:
            raise CPGDeserializationError(
                "CPG tarball nodes must be dense and sorted by node_id 0..N-1 "
                f"(the producer's own deterministic emission order, INV-5); "
                f"position {position} carries node_id={node_id!r}"
            )
        assigned = cpg.add_node(
            str(raw_node.get("kind", "")),
            operator_or_literal=str(raw_node.get("operator_or_literal", "")),
            resolved_fqn=str(raw_node.get("resolved_fqn", "")),
            enclosing_decl_fqn=str(raw_node.get("enclosing_decl_fqn", "")),
            structural_path=str(raw_node.get("structural_path", "")),
        )
        if int(assigned) != position:  # pragma: no cover — CPG.add_node is insertion-ordered
            raise CPGDeserializationError("CPG.add_node did not preserve insertion order")

    node_count = len(nodes)
    for raw_edge in edges:
        if not isinstance(raw_edge, dict):
            raise CPGDeserializationError(f"edge entry is not an object: {raw_edge!r}")
        src, dst, kind = raw_edge.get("src"), raw_edge.get("dst"), raw_edge.get("kind")
        if not isinstance(src, int) or not isinstance(dst, int) or not isinstance(kind, str):
            raise CPGDeserializationError(f"malformed edge entry: {raw_edge!r}")
        if not (0 <= src < node_count) or not (0 <= dst < node_count):
            raise CPGDeserializationError(f"edge references an out-of-range node id: {raw_edge!r}")
        cpg.add_edge(NodeId(src), NodeId(dst), kind)
    return cpg


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


class _FailClosedQueue:
    """Production default: raises until a real queue is wired (Track 1E)."""

    def receive(self) -> ReceivedMessage | None:
        raise NotImplementedError(
            "the detector-jobs SQS queue is env-gated (CMP-ORCH-03 build-ahead, "
            "Track 1E — real boto3-backed SQSQueue not yet wired). Inject a "
            "QueuePort via run_execute_loop(..., queue=...) in a hermetic test."
        )

    def ack(self, receipt_handle: int) -> None:  # pragma: no cover — receive() always raises first
        raise NotImplementedError("detector-jobs SQS queue is env-gated (see receive())")

    def fail(self, receipt_handle: int) -> None:  # pragma: no cover — receive() always raises first
        raise NotImplementedError("detector-jobs SQS queue is env-gated (see receive())")


def fail_closed_queue() -> QueuePort:
    """The default queue port: fail-closed until Track 1E lands."""
    return _FailClosedQueue()


class _FailClosedObjectStore:
    """Production default: raises until a real bucket is wired (Track 1D/AWS)."""

    def get(self, org_id: str, key: str) -> bytes:
        raise NotImplementedError(
            "the S3 artifact store is env-gated (CMP-ORCH-03 build-ahead): a real "
            "S3ObjectStore needs a bucket name + AWS credentials not resolved "
            "here. Inject an ObjectStore (e.g. "
            "services.substrate.object_store.S3ObjectStore / InMemoryObjectStore) "
            "via run_detector_job(..., object_store=...) in a hermetic test."
        )

    def put(  # pragma: no cover — get() always raises first
        self, org_id: str, key: str, body: bytes
    ) -> None:
        raise NotImplementedError("S3 artifact store is env-gated (see get())")


def fail_closed_object_store() -> ObjectStore:
    """The default object-store port: fail-closed until a bucket is wired."""
    return _FailClosedObjectStore()


@runtime_checkable
class FindingsSession(Protocol):
    """Structural subset of a SQLAlchemy ``Session`` this module writes through.

    Any object exposing ``add``/``commit`` satisfies this: a real
    ``sqlalchemy.orm.Session`` bound via ``db/session.py::acquire_for_request``
    (Track 1D) in production, or a lightweight in-memory fake in tests.
    """

    def add(self, instance: object) -> None: ...
    def commit(self) -> None: ...


class _FailClosedFindingsSession:
    """Production default: raises until the real DB session is wired (Track 1D)."""

    def add(self, instance: object) -> None:
        raise NotImplementedError(
            "the findings-store DB session is env-gated (CMP-ORCH-03 build-ahead, "
            "Track 1D — real sqlalchemy.orm.Session via db/session.py::"
            "acquire_for_request not yet wired). Inject a FindingsSession via "
            "run_detector_job(..., findings_session=...) in a hermetic test."
        )

    def commit(self) -> None:  # pragma: no cover — add() always raises first
        raise NotImplementedError("findings-store DB session is env-gated (see add())")


def fail_closed_findings_session() -> FindingsSession:
    """The default findings-session port: fail-closed until Track 1D lands."""
    return _FailClosedFindingsSession()


class _FailClosedKMSSigner:
    """Production default: raises until a real tenant CMK is wired."""

    def sign(
        self,
        *,
        KeyId: str,  # noqa: N803 — boto3 wire parameter names are PascalCase.
        Message: bytes,  # noqa: N803
        SigningAlgorithm: str,  # noqa: N803
    ) -> dict[str, object]:
        raise NotImplementedError(
            "the KMS asymmetric signer is env-gated (CMP-ORCH-03 build-ahead): "
            "real kms:Sign needs a live AWS KMS CMK (CLAR-DEPLOY-16: one CMK per "
            "tenant), not resolved here. Inject a KMSAsymmetricSigner via "
            "run_detector_job(..., signer=...) in a hermetic test."
        )

    def get_public_key(
        self,
        *,
        KeyId: str,  # noqa: N803
        KeyVersion: str,  # noqa: N803
    ) -> dict[str, object]:  # pragma: no cover — sign() always raises first
        raise NotImplementedError("KMS asymmetric signer is env-gated (see sign())")


def fail_closed_kms_signer() -> KMSAsymmetricSigner:
    """The default KMS signer port: fail-closed until a real CMK is wired."""
    return _FailClosedKMSSigner()


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

    Every port defaults to its fail-closed production seam (CLAR-PROC-01):
    with no injected collaborators this raises ``NotImplementedError`` naming
    the first genuinely-unbuilt dependency it touches (the queue, Track 1E),
    exactly mirroring the honest gating in
    ``services/snapshot/worker.py::run_execute_loop``. A hermetic test (or a
    future production wiring layer, once Tracks 1D/1E land) injects real
    collaborators.
    """
    queue = queue if queue is not None else fail_closed_queue()
    object_store = object_store if object_store is not None else fail_closed_object_store()
    findings_session = (
        findings_session if findings_session is not None else fail_closed_findings_session()
    )
    signer = signer if signer is not None else fail_closed_kms_signer()
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
    "fail_closed_findings_session",
    "fail_closed_kms_signer",
    "fail_closed_object_store",
    "fail_closed_queue",
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
