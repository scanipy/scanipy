"""CMP-SNAP-05 — pinned-image snapshot worker entrypoint (``python -m`` target).

Implementation contract: ``docs/components/DOC-CMP-SNAP-05.md`` (§3.1 env-var
contract, §3.3 argv allowlist, §6 lifecycle, §7 fail-closed). Cross-cutting:
``DOC-INV §4`` (INV-2 ORIGIN — this component is the platform's ``env_digest``
origin), ``.claude/rules/02-provenance.md`` (env_digest threading),
``.claude/rules/00-global.md`` (RULE-6).

This module is the **ECS Fargate container entrypoint**: the worker Dockerfile
(``workers/snapshot/Dockerfile``) runs ``ENTRYPOINT ["python", "-m",
"services.snapshot.worker"]``. Two pieces of worker LOGIC are delivered and
verified hermetically here:

1. **Env-digest binding (``AC-SNAP-05b``, INV-2 ORIGIN).** :func:`resolve_env_digest`
   reads the worker's image digest from ``SCANIPY_ENV_DIGEST`` — the value ECS
   injects from the running task's image metadata (DOC §3.1, §8). It is the
   **authoritative ``env_digest`` for the entire platform**: it is stamped onto
   the snapshot job and threaded into ``report_status``. A missing, empty, or
   malformed digest is **fail-closed** (:class:`EnvDigestMissing`): the worker
   refuses to start, because INV-2 forbids running analysis against an unpinned
   ``Env`` (DOC §7 — "INV-2 absolutely requires a real digest").

2. **Argv allowlist (``AC-SNAP-05a``).** Every pinned-tool (``joern`` / ``codeql``
   / ``git``) invocation routes through :func:`tools.worker.secure_subprocess.secure_run`,
   re-exported here, which rejects any non-sanctioned flag fail-closed before a
   subprocess is spawned (``shell=False`` always).

BOOTSTRAP EXECUTE LOOP (CLAR-SNAP-04 — first-real-scan plan, worktree wf-2):
:func:`run_execute_loop` now runs the real DOC §6.2 sequence for a **first-ever
(no-parent) snapshot only**: SQS dequeue → real ``git`` clone via
:func:`tools.worker.secure_subprocess.secure_run` (argv-allowlisted) → real
``CMP-SNAP-03`` :func:`services.snapshot.cw_detect.detect` → a bootstrap
``source -> analysis.ordering.CPG`` full parse → upload the four bootstrap-mode
artifacts to S3 (``CMP-DEPLOY-01`` :class:`services.substrate.object_store.ObjectStore`)
→ an HMAC-bearer ``report_status`` callback. ``CMP-SNAP-02``
(``compute_incremental_cpg`` / the ``GraphView`` reverse-symbol-index + dynamic
call-graph builder) is **bypassed entirely** for this path (CLAR-SNAP-04): a
job whose ``parent_snapshot_id`` is non-empty is refused fail-closed
(:class:`IncrementalSnapshotNotSupportedError`) rather than silently mis-handled —
CMP-SNAP-02 is Wave-2+ scope and only engages from the second commit onward.

One collaborator remains genuinely unbuilt and is injected as a typed,
fail-closed-by-default port (CLAR-PROC-01 condition (2), same discipline as
``services/scan/worker.py``): :class:`ReportStatusPort` (the worker->API
status-report wire contract is unresolved — DOC §3.2 names a route that does
not exist and CLAR-SNAP-02's resolution explicitly carved the
``report_status`` callback shape out as "a separate downstream decision",
tracked as CLAR-SNAP-07 — see this module's ``ReportStatusPort`` docstring).
The other two production seams are now real: :data:`ParseSourceFn` defaults
to ``analysis.cpg_ingest.joern_frontend.parse_source`` (CLAR-SNAP-03/05,
ratified and landed) and :class:`SnapshotQueuePort` defaults to a real
``SQSQueue`` reading ``SNAPSHOT_QUEUE_URL`` (see :func:`_default_snapshot_queue`).
A hermetic test injects deterministic fakes for all collaborators regardless.
S3 upload is likewise real: :class:`services.substrate.object_store.S3ObjectStore`
(lazy boto3 import) constructed from the ``S3_BUCKET`` env var.

This module writes NO provenance fields to a ``Finding``; it threads
``env_digest`` (INV-2) into the snapshot pipeline via the SNAP-01 callback
(DOC §8). It MUST NOT touch ``origin`` (CMP-ORCH-03), ``S_version`` (CMP-ORCH-01),
``cpg_order_hash`` (CMP-CORE-03), or ``slice_fingerprint`` (CMP-CORE-02).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, Protocol, runtime_checkable

from analysis.cpg_ingest.joern_frontend import parse_source as _real_parse_source
from services.scan.provenance import InvariantViolation
from services.snapshot import cw_detect
from services.substrate.cpg_tarball import serialize_cpg_tarball
from services.substrate.object_store import (
    SNAPSHOT_ARTIFACT_TYPES,
    S3ObjectStore,
    SnapshotKeyBuilder,
)
from services.substrate.queue import SQSQueue
from tools.observability.logging import get_logger
from tools.observability.metrics import record_job_completion

# Re-export the argv-allowlist surface so the worker's single import point is
# this module (DOC §3.3 — every secure_run call site lives behind the worker).
from tools.worker.secure_subprocess import (
    ArgvAllowlistViolation,
    UnknownTool,
    secure_run,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from analysis.ordering import CPG
    from services.substrate.object_store import ObjectStore
    from services.substrate.queue import ReceivedMessage

# INV-2: env_digest is the worker container image digest. Same format CHECK as
# the shipped ``snapshots.env_digest_chk`` DDL constraint and the SNAP-01 service
# guard (services/snapshot/service.py) — one canonical sha256-image-digest shape.
_ENV_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

# The env var ECS injects from the running task's image metadata (DOC §3.1).
ENV_DIGEST_VAR = "SCANIPY_ENV_DIGEST"


class EnvDigestMissing(Exception):  # noqa: N818 — name fixed verbatim by DOC-CMP-SNAP-05 §3.4
    """``SCANIPY_ENV_DIGEST`` was unset/empty/malformed at boot (fail-closed).

    DOC-CMP-SNAP-05 §3.4 / §7: INV-2 requires a real ``env_digest`` (the running
    image digest). The worker refuses to start without one — running analysis
    against an unpinned ``Env`` would silently break the reproducibility theorem
    (PLAN property (a)). This is the INV-2 ORIGIN fail-closed gate.
    """


def resolve_env_digest(environ: dict[str, str] | None = None) -> str:
    """Return the authoritative ``env_digest`` from the runtime-injected env var.

    Reads ``SCANIPY_ENV_DIGEST`` (ECS task-metadata injection, DOC §3.1) and
    guards it against the canonical ``^sha256:[0-9a-f]{64}$`` image-digest shape.
    A missing, empty, or malformed value is **fail-closed**:
    :class:`EnvDigestMissing` is raised (INV-2 ORIGIN, DOC §7) — there is no
    default and no fallback, so the worker can never stamp a snapshot with an
    unpinned ``Env``.

    Args:
        environ: an env mapping to read (defaults to :data:`os.environ`); the
            ``None`` default keeps the call hermetic — tests inject a fixture
            digest rather than mutating process state.

    Returns:
        The verbatim image digest string (this exact value is the platform's
        ``env_digest`` per INV-2; it is stamped on the snapshot job and threaded
        into ``report_status``).

    Raises:
        EnvDigestMissing: the var is unset, empty, or not a sha256 image digest.
    """
    env = os.environ if environ is None else environ
    candidate = env.get(ENV_DIGEST_VAR, "")
    if not candidate:
        raise EnvDigestMissing(
            f"INV-2: {ENV_DIGEST_VAR} must be injected from the running image "
            "digest before the worker starts; the worker refuses to run against "
            "an unpinned Env (DOC-CMP-SNAP-05 §7)"
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

    The single fail-closed step the worker performs before *any* job work: bind
    the authoritative ``env_digest`` (INV-2 ORIGIN). Returns the digest so a
    caller (or test) can assert the bound value; raises :class:`EnvDigestMissing`
    if the gate trips. This is the seam ``main`` calls first and the seam the
    AC-SNAP-05b test drives with a fixture digest.
    """
    return resolve_env_digest(environ)


def record_snapshot_job_completion(
    outcome: Literal["success", "failure"],
    duration_ms: float,
    *,
    env_digest: str,
    precondition_status: str,
    environ: Mapping[str, str] | None = None,
) -> None:
    """Emit the CMP-SNAP-05 job-completion metrics (DOC-CMP-DEPLOY-03 §3.4 1-3).

    The CLAR-DEPLOY-20 emission seam the DOC §6.2 execute loop calls **exactly
    once per dequeued SQS message**:

    * ``outcome="failure"`` — the message terminated in
      ``report_status(state='failed')`` (any DOC-CMP-SNAP-05 §7 terminal
      failure path) → ``snapshot_worker.failure_count``.
    * ``outcome="success"`` — the ``report_status(state='ready')`` POST
      returned 2xx → ``snapshot_worker.success_count``.

    Either way ``snapshot_worker.duration_ms`` records ``duration_ms``, the
    dequeue→report wall time measured on the **monotonic clock**
    (``time.monotonic``), never wall-clock arithmetic. Counter attributes are
    ``{region, env_digest}`` (region from ``AWS_REGION``, default
    ``us-east-1``); the duration attribute is ``{precondition_status}`` (the
    CW-DETECT verdict for the job). Retries count per-attempt, intentionally
    (CLAR-DEPLOY-20): the failure-rate alarm denominator is completions.

    Hermetic: a plain function of its inputs plus an injectable ``environ``
    (defaults to :data:`os.environ`), and a no-op without OTel installed — it
    can never take down the job loop.
    """
    env = os.environ if environ is None else environ
    record_job_completion(
        "snapshot_worker",
        outcome,
        duration_ms,
        counter_attributes={
            "region": env.get("AWS_REGION", "us-east-1"),
            "env_digest": env_digest,
        },
        duration_attributes={"precondition_status": precondition_status},
    )


_GIT_CLONE_TIMEOUT_S: Final[int] = 300
_GIT_CHECKOUT_TIMEOUT_S: Final[int] = 60

# Required SnapshotJob message-body keys (see :class:`SnapshotJob` docstring for
# the ``clone_url`` gap note).
_REQUIRED_JOB_FIELDS: Final[tuple[str, ...]] = (
    "snapshot_id",
    "org_id",
    "codebase_id",
    "commit_sha",
    "env_digest",
    "clone_url",
)

# Bootstrap-loop language detection: a small, LOCAL extension map (deliberately
# NOT importing ``services.snapshot.cw_detect``'s private ``_EXT_TO_LANG`` —
# that module's language classification is scoped to the INV-4 reflection
# precondition, a different concern from "which parser does ``parse_source``
# invoke"). Kept minimal: Stage A is java+python; the rest are listed so a
# multi-language repo still yields an honest ``language_mix`` for CW-DETECT.
_SOURCE_EXTENSIONS: Final[dict[str, str]] = {
    ".py": "python",
    ".pyi": "python",
    ".java": "java",
    ".js": "js",
    ".jsx": "js",
    ".mjs": "js",
    ".cjs": "js",
    ".ts": "ts",
    ".tsx": "ts",
    ".rb": "ruby",
    ".php": "php",
    ".phtml": "php",
    ".go": "go",
}


class MalformedSnapshotJobError(Exception):
    """The dequeued SQS message body is missing a required ``SnapshotJob`` field.

    Notably ``clone_url``: the shipped ``CMP-SNAP-01`` enqueue body
    (``SnapshotService.create_snapshot``'s ``queue.send(body={...})``) carries
    only ``snapshot_id/org_id/codebase_id/commit_sha/env_digest/parent_snapshot_id``
    — no repo clone URL. See the ``SnapshotJob`` docstring; flagged as a new-CLAR
    candidate in this PR rather than guessed at (RULE-4).
    """


class IncrementalSnapshotNotSupportedError(Exception):
    """A ``SnapshotJob`` carries a non-empty ``parent_snapshot_id`` (CLAR-SNAP-04).

    ``CMP-SNAP-02`` (``compute_incremental_cpg`` / the ``GraphView`` builder) is
    Wave-2+ scope and is not wired into this loop. Refusing fail-closed here is
    deliberate: silently treating an incremental job as a fresh bootstrap parse
    would drop the CW-DETECT parent reflection-site carry-forward (DOC-CMP-SNAP-03
    §4.1 property 3, INV-4) and would not compute a real ΔG. CLAR-SNAP-04 records
    this as the intended interim behaviour, not a bug.
    """


class NoSourceFilesFoundError(Exception):
    """No file under the cloned tree matched a recognised source-language extension."""


@dataclass(frozen=True)
class SnapshotJob:
    """A dequeued, parsed ``SnapshotJob`` (DOC-CMP-SNAP-05 §4.1 input shape).

    ``clone_url`` is REQUIRED here even though the shipped CMP-SNAP-01
    ``SnapshotService.create_snapshot`` enqueue body does not currently carry
    one (see :class:`MalformedSnapshotJobError`) — this loop cannot clone without it.
    Forward-compatible: once CMP-SNAP-01 (or a ``CodebasePort``-shaped lookup)
    supplies it, no change is needed here.

    ``parent_snapshot_id`` is ``None`` for a first-ever (bootstrap) snapshot —
    the only path this loop implements (CLAR-SNAP-04).
    """

    snapshot_id: str
    org_id: str
    codebase_id: str
    commit_sha: str
    env_digest: str
    clone_url: str
    parent_snapshot_id: str | None = None


def _parse_snapshot_job(body: Mapping[str, str]) -> SnapshotJob:
    """Parse+validate a raw queue-message body into a typed :class:`SnapshotJob`.

    Fail-closed: any missing required field raises :class:`MalformedSnapshotJobError`
    naming every missing key (not just the first) so a redelivered poison
    message's diagnostic is immediately actionable.
    """
    missing = [field_name for field_name in _REQUIRED_JOB_FIELDS if not body.get(field_name)]
    if missing:
        raise MalformedSnapshotJobError(
            f"SnapshotJob message body is missing required field(s) {missing!r}"
        )
    parent = body.get("parent_snapshot_id") or None
    return SnapshotJob(
        snapshot_id=body["snapshot_id"],
        org_id=body["org_id"],
        codebase_id=body["codebase_id"],
        commit_sha=body["commit_sha"],
        env_digest=body["env_digest"],
        clone_url=body["clone_url"],
        parent_snapshot_id=parent,
    )


# ---------------------------------------------------------------------------
# Typed ports (build-ahead seams, CLAR-PROC-01 condition (2) — same discipline
# as ``services/scan/worker.py``'s ``OracleAdapter`` / ``SliceFingerprinter``).
# ---------------------------------------------------------------------------


class ParseSourceFn(Protocol):
    """``source -> analysis.ordering.CPG`` front end (CLAR-SNAP-03 scope).

    Exact agreed signature (the 1A/1B handshake): ``parse_source(src_root,
    language, *, env, workdir) -> CPG``. The production default is the real
    ``analysis.cpg_ingest.joern_frontend.parse_source`` (CLAR-SNAP-03/05,
    ratified and landed) — see :func:`_real_parse_source`, imported at module
    load as ``_real_parse_source``. Tests inject a fake matching this exact
    signature via ``run_execute_loop(..., parse_source=...)``.
    """

    def __call__(
        self, src_root: Path, language: str, *, env: Mapping[str, str], workdir: Path
    ) -> CPG: ...


SnapshotStatusState = Literal["ready", "failed"]


@dataclass(frozen=True)
class SnapshotStatusReport:
    """The worker->API status report (DOC-CMP-SNAP-05 §3.2 field shape).

    ``precondition_status`` / ``snapshot_digest`` are ``None`` until ``state ==
    "ready"`` (DOC §3.2 — "null until 'ready'"). This loop never emits the
    ``"snapshotting"`` DOC state: it runs clone->CW-DETECT->parse->upload
    synchronously and reports exactly once, terminal (``ready`` or ``failed``).
    """

    snapshot_id: str
    state: SnapshotStatusState
    env_digest: str
    precondition_status: str | None = None
    snapshot_digest: str | None = None
    error: str | None = None


@runtime_checkable
class ReportStatusPort(Protocol):
    """HMAC-bearer ``report_status`` callback seam (DOC-CMP-SNAP-05 §3.2).

    NO REAL PRODUCTION IMPLEMENTATION SHIPS IN THIS PR (RULE-4 — the wire
    contract is not ratified, so none is invented). Two real, unreconciled
    candidate contracts exist in the codebase today:

    1. DOC-CMP-SNAP-05 §3.2 names ``POST /snapshots/{snapshot_id}/status``
       with an ``Authorization: HMAC-SHA256 <signed-bytes>=<base64(hmac)>``
       header shape — but no such route is implemented anywhere in
       ``services/scan`` (verified by grep), and CLAR-SNAP-02's resolution
       explicitly carved this out: *"The SNAP-05 report_status callback (state
       machine + snapshot_digest persistence) is a separate downstream
       decision (off-row tracking vs a deliberate CP-03 amendment), not this
       conflict."* — i.e. still open.
    2. ``services/scan/api.py`` ships a REAL, tested ``POST
       /api/v1/jobs/{job_id}/status`` (``post_job_status`` / ``JobStatusReport``
       / ``verify_worker_callback_hmac``) — but it is shaped for CMP-ORCH-03
       DETECTOR-job completions: it requires a non-empty ``S_version`` (INV-2
       fence, 400 otherwise), a ``scan_id``, and a per-``job_id`` HMAC secret
       pre-issued by ``HmacKeyIssuer.issue(job_id=..., scan_id=...)`` inside
       ``post_scans``. ``SnapshotService.create_snapshot`` mints only a
       ``snapshot_id`` and never calls that issuer, so no key would ever exist
       for a snapshot callback — every call would 401. This route is NOT a fit
       for a snapshot-stage callback without a CLAR ratifying "treat
       snapshot_id as job_id and thread a synthetic S_version," which nothing
       in PLAN.md/SDD.md specifies (RULE-4: not guessed at here).

    The production default (:func:`_fail_closed_report_status_port`) fails
    closed naming both candidates; a hermetic test injects a deterministic
    fake. Swapping in the real client is a follow-up PR once the CLAR is
    ratified — this Protocol's shape (``report(SnapshotStatusReport) -> None``)
    is written to survive either resolution.
    """

    def report(self, status: SnapshotStatusReport) -> None: ...


class _FailClosedReportStatusPort:
    """Production ``ReportStatusPort`` default: fails closed (see the Protocol docstring)."""

    def report(self, status: SnapshotStatusReport) -> None:
        raise NotImplementedError(
            f"report_status(snapshot_id={status.snapshot_id!r}, state={status.state!r}) "
            "has no wired HTTP+HMAC client: the DOC-CMP-SNAP-05 §3.2 callback route "
            "does not exist and CLAR-SNAP-02 left the SNAP-05 report_status contract "
            "as 'a separate downstream decision'; services/scan/api.py's real "
            "POST /api/v1/jobs/{job_id}/status is shaped for detector-job "
            "completions (S_version + scan_id + a pre-issued per-job HMAC key), not "
            "a snapshot callback. Inject a ReportStatusPort via "
            "run_execute_loop(..., report_status=...) in a hermetic test."
        )


def _fail_closed_report_status_port() -> ReportStatusPort:
    return _FailClosedReportStatusPort()


@runtime_checkable
class SnapshotQueuePort(Protocol):
    """Structural seam over the dequeue surface (``StandardQueue``-compatible).

    Both ``services/substrate/queue.py`` primitives satisfy this shape:
    ``StandardQueue`` (in-memory, hermetic tests) and ``SQSQueue`` (real
    boto3-backed adapter, production default — see :func:`_default_snapshot_queue`).
    """

    def receive(self) -> ReceivedMessage | None: ...

    def ack(self, receipt_handle: int) -> None: ...

    def fail(self, receipt_handle: int) -> None: ...


def _default_snapshot_queue(environ: Mapping[str, str]) -> SnapshotQueuePort:
    """Production ``SnapshotQueuePort`` default: a REAL ``SQSQueue`` (lazy boto3).

    Mirrors :func:`_default_object_store`'s pattern exactly: ``SQSQueue.__init__``
    lazily imports boto3 only when ``client=None`` is passed, so this stays
    import-clean without boto3 present. ``SNAPSHOT_QUEUE_URL`` (already
    provisioned on the live ECS task definition, ``scanipy-prod-snapshot-jobs``)
    must be set; a missing value fails closed rather than guessing a queue URL.
    """
    queue_url = environ.get("SNAPSHOT_QUEUE_URL")
    if not queue_url:
        raise InvariantViolation(
            "SNAPSHOT_QUEUE_URL must be set; refusing to construct an unbound SQSQueue",
            code="missing_snapshot_queue_url",
        )
    return SQSQueue(queue_url)


def _default_object_store(environ: Mapping[str, str]) -> ObjectStore:
    """Production ``ObjectStore`` default: a REAL ``S3ObjectStore`` (lazy boto3).

    Unlike ``queue``/``report_status``/``parse_source``, S3 upload is not
    env-gated (task brief: "the ALREADY-REAL services/substrate/object_store.py
    S3ObjectStore") — ``S3ObjectStore.__init__`` lazily imports boto3 only when
    ``client=None`` is passed, so this stays import-clean without boto3 present.
    ``S3_BUCKET`` (DOC-CMP-SNAP-05 §3.1 storage env-var contract) must be set;
    a missing value fails closed rather than defaulting to a guessed bucket name.
    """
    bucket = environ.get("S3_BUCKET")
    if not bucket:
        raise InvariantViolation(
            "S3_BUCKET must be set (DOC-CMP-SNAP-05 §3.1); refusing to construct "
            "an unbucketed S3ObjectStore",
            code="missing_s3_bucket",
        )
    return S3ObjectStore(bucket)


def _detect_language_mix(src_root: Path) -> tuple[tuple[str, ...], str]:
    """Return ``(language_mix, primary_language)`` for the cloned source tree.

    ``language_mix`` feeds ``CwDetectRequest`` (every recognised language present,
    sorted for determinism); ``primary_language`` is a ``parse_source`` hint (the
    most common recognised extension; ties broken deterministically, not a
    staging/priority ordering — CMP-CP-06 governs Algorithm-2 eligibility, not
    ingestion). Raises :class:`NoSourceFilesFoundError` when nothing recognisable is
    present (a job-level failure, not a silent no-op scan).
    """
    counts: dict[str, int] = {}
    for path in src_root.rglob("*"):
        if not path.is_file():
            continue
        lang = _SOURCE_EXTENSIONS.get(path.suffix.lower())
        if lang is not None:
            counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        raise NoSourceFilesFoundError(f"no recognised source files found under {src_root}")
    language_mix = tuple(sorted(counts))
    primary_language = max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]
    return language_mix, primary_language


def _git_env(home: Path) -> dict[str, str]:
    """Minimal explicit env for the ``git`` child (the host env is NOT inherited).

    ``GIT_TERMINAL_PROMPT=0`` prevents a hang on a credential prompt (this
    bootstrap loop clones a PUBLIC repo, no PAT); ``HOME`` is scoped to the
    ephemeral workdir so no host ``~/.gitconfig`` leaks into the clone.
    """
    return {"PATH": "/usr/bin:/bin", "GIT_TERMINAL_PROMPT": "0", "HOME": str(home)}


def _default_parse_env() -> dict[str, str]:
    """Minimal explicit env threaded into ``parse_source`` (DOC §6.3 example shape)."""
    return {"PATH": "/opt/joern/bin:/opt/codeql:/usr/bin", "JAVA_HOME": "/opt/jdk"}


def _build_reverse_symbol_index(cpg: CPG) -> bytes:
    """Bootstrap-mode ``reverse_symbol_index`` artifact: ``{resolved_fqn: [node_id, ...]}``.

    Computed directly from the CPG we just built (real, not a placeholder) —
    this is the trivial single-snapshot index; the full incremental
    reverse-symbol-closure machinery is ``CMP-SNAP-02``/``GraphView`` scope
    (CLAR-SNAP-04, Wave-2+), not needed for a first-ever snapshot.
    """
    index: dict[str, list[int]] = {}
    for node in cpg.nodes:
        if node.resolved_fqn:
            index.setdefault(node.resolved_fqn, []).append(int(node.node_id))
    return json.dumps(index, sort_keys=True).encode("utf-8")


def _build_dynamic_call_graph_stub() -> bytes:
    """Bootstrap-mode ``dynamic_call_graph`` artifact: honestly empty, not fabricated.

    ``CMP-SNAP-02``'s ``GraphView`` builds the real interprocedural call graph
    (CLAR-SNAP-04, Wave-2+ scope); a bootstrap snapshot legitimately has none
    computed yet. The ``bootstrap_mode`` flag lets a downstream reader
    distinguish "no edges because bootstrap" from "no edges because empty repo".
    """
    payload = {
        "edges": [],
        "bootstrap_mode": True,
        "note": (
            "CMP-SNAP-02 GraphView (dynamic call-graph construction) is Wave-2+ "
            "scope per CLAR-SNAP-04; this bootstrap snapshot has no computed "
            "call-graph edges."
        ),
    }
    return json.dumps(payload).encode("utf-8")


def _build_precondition_status_record(verdict: cw_detect.CwDetectVerdict) -> bytes:
    """Serialise the real ``CW-DETECT`` verdict to the ``precondition_status.json`` body."""
    return json.dumps(asdict(verdict)).encode("utf-8")


def run_execute_loop(
    env_digest: str,
    *,
    queue: SnapshotQueuePort | None = None,
    object_store: ObjectStore | None = None,
    parse_source: ParseSourceFn | None = None,
    report_status: ReportStatusPort | None = None,
    environ: Mapping[str, str] | None = None,
) -> None:
    """The per-job SQS execute loop (DOC §6.2), bootstrap (no-parent) path only.

    One call processes AT MOST one dequeued message — mirroring the DOC §6.1
    lifecycle ("Execute -> Shutdown: Task exits after ACKing the SQS message";
    one ECS Fargate task = one job attempt). Steps, matching DOC §6.2 verbatim
    order (with CLAR-SNAP-04's CMP-SNAP-02 bypass):

    1. ``queue.receive()``. Empty queue -> log + return (no completion metric:
       "exactly once per DEQUEUED message").
    2. Parse + validate the message body (:func:`_parse_snapshot_job`).
    3. INV-2 guard: ``job.env_digest`` must equal this worker's bound digest.
    4. CLAR-SNAP-04 guard: a non-empty ``parent_snapshot_id`` is refused
       (:class:`IncrementalSnapshotNotSupportedError`) — bootstrap-only in this loop.
    5. ``git clone`` + ``git checkout <commit_sha>`` via the REAL argv-allowlisted
       :func:`secure_run` (``tools/worker/secure_subprocess.py``).
    6. Real ``CMP-SNAP-03`` :func:`services.snapshot.cw_detect.detect` (no
       parent snapshot — bootstrap has none to carry forward).
    7. ``parse_source(src_root, primary_language, env=..., workdir=...) -> CPG``
       (the injected/fail-closed :data:`ParseSourceFn` seam).
    8. Build the four bootstrap-mode artifacts and upload each to
       ``object_store`` at the deterministic :class:`SnapshotKeyBuilder` key
       (``delta_graph`` is skipped: a bootstrap snapshot has no parent, hence no
       delta — the one artifact the schema itself allows to be absent).
    9. ``report_status.report(state="ready", ...)``, then ``queue.ack(...)``.

    On ANY exception from steps 2-9: best-effort ``report_status.report(
    state="failed", error=...)`` (swallowed if the port itself raises — a
    secondary failure must never crash the loop), ``queue.fail(...)`` (DOC §7:
    SQS redelivery / max-receive -> DLQ), and the loop RETURNS NORMALLY rather
    than propagating — matching ``IdempotentConsumer.poll_once``'s own
    swallow-and-fail-the-message discipline (``services/substrate/queue.py``).

    OBSERVABILITY CONTRACT (CMP-DEPLOY-03 / CLAR-DEPLOY-20): calls
    :func:`record_snapshot_job_completion` exactly once per dequeued message
    (never on an empty-queue no-op), with the dequeue->report duration from the
    monotonic clock and the best-known ``precondition_status`` (``"unknown"``
    if the failure happened before CW-DETECT ran).

    BOUNDARY DISCIPLINE (DOC §8 / module docstring): this function never reads
    or writes ``origin`` / ``cpg_order_hash`` / ``slice_fingerprint`` — those
    are set downstream (CMP-ORCH-03 / CMP-CORE-02/03) once a detector job runs
    against the uploaded CPG tarball.

    Args:
        env_digest: the bound authoritative ``env_digest`` (INV-2, from
            :func:`boot`) every ``report_status`` callback threads (DOC §8).
        queue: the SQS-shaped dequeue port; fails closed by default (no real
            boto3-SQS adapter is wired yet — inject a ``StandardQueue`` in tests).
        object_store: the S3-shaped upload port; defaults to a REAL
            ``S3ObjectStore`` built from ``S3_BUCKET`` (already-real substrate).
        parse_source: the ``source -> CPG`` front end; defaults to the real
            ``analysis.cpg_ingest.joern_frontend.parse_source`` (CLAR-SNAP-03/05)
            — inject a fake matching the exact :data:`ParseSourceFn` signature
            in tests.
        report_status: the worker->API callback port; fails closed by default
            (the wire contract is unresolved — see :class:`ReportStatusPort`).
        environ: env mapping override for hermetic tests (defaults to
            :data:`os.environ`), read for ``S3_BUCKET`` / ``SNAPSHOT_QUEUE_URL``
            / ``AWS_REGION``.
    """
    env = os.environ if environ is None else environ
    active_queue: SnapshotQueuePort = queue if queue is not None else _default_snapshot_queue(env)
    logger = get_logger("snapshot-worker")

    received = active_queue.receive()
    if received is None:
        logger.info("snapshot execute loop: no job available")
        return

    # Deferred until AFTER we know there is a job to process: an idle poll (the
    # common case) must never pay for / fail on resolving these collaborators.
    # ``report_status`` and ``parse_source`` construction is a pure reference
    # assignment (never raises); it stays OUTSIDE the try so the except block
    # below can always reach ``active_report_status`` to file a failure report
    # — including when the one collaborator that CAN raise at construction,
    # ``_default_object_store`` (missing ``S3_BUCKET``), is what failed.
    active_parse_source: ParseSourceFn = (
        parse_source if parse_source is not None else _real_parse_source
    )
    active_report_status: ReportStatusPort = (
        report_status if report_status is not None else _fail_closed_report_status_port()
    )

    started = time.monotonic()
    job: SnapshotJob | None = None
    cw_verdict: cw_detect.CwDetectVerdict | None = None

    try:
        job = _parse_snapshot_job(received.message.body)

        if job.env_digest != env_digest:
            raise InvariantViolation(
                f"SnapshotJob.env_digest {job.env_digest!r} does not match this "
                f"worker's bound env_digest {env_digest!r} (INV-2)",
                code="invariant_inv2_violation",
            )
        if job.parent_snapshot_id:
            raise IncrementalSnapshotNotSupportedError(
                f"snapshot_id={job.snapshot_id!r} carries parent_snapshot_id="
                f"{job.parent_snapshot_id!r}; CMP-SNAP-02 is not wired (CLAR-SNAP-04)"
            )

        # Inside the try (unlike report_status/parse_source above): this is the
        # one collaborator whose default construction can itself raise (a
        # missing S3_BUCKET), and by this point active_report_status already
        # exists to carry that failure back to the caller.
        active_object_store: ObjectStore = (
            object_store if object_store is not None else _default_object_store(env)
        )

        with tempfile.TemporaryDirectory(prefix="scanipy-snap-") as raw_tmp:
            tmp_root = Path(raw_tmp)
            src_root = tmp_root / "src"
            workdir = tmp_root / "work"
            workdir.mkdir()
            git_env = _git_env(tmp_root)

            secure_run(
                "git",
                ["clone", "--quiet", job.clone_url, str(src_root)],
                timeout_s=_GIT_CLONE_TIMEOUT_S,
                env=git_env,
                cwd=str(tmp_root),
            )
            secure_run(
                "git",
                ["checkout", "--quiet", job.commit_sha],
                timeout_s=_GIT_CHECKOUT_TIMEOUT_S,
                env=git_env,
                cwd=str(src_root),
            )

            language_mix, primary_language = _detect_language_mix(src_root)

            cw_verdict = cw_detect.detect(
                cw_detect.CwDetectRequest(
                    source_tree_root=str(src_root),
                    language_mix=language_mix,
                    parent_snapshot=None,  # bootstrap: no parent to carry forward
                )
            )

            cpg = active_parse_source(
                src_root, primary_language, env=_default_parse_env(), workdir=workdir
            )

            artifact_bodies: dict[str, bytes] = {
                "cpg_tarball": serialize_cpg_tarball(cpg),
                "reverse_symbol_index": _build_reverse_symbol_index(cpg),
                "dynamic_call_graph": _build_dynamic_call_graph_stub(),
                "precondition_status": _build_precondition_status_record(cw_verdict),
            }

            key_builder = SnapshotKeyBuilder(
                org_id=job.org_id,
                codebase_id=job.codebase_id,
                commit_sha=job.commit_sha,
                env_digest=env_digest,
            )
            for artifact_type in SNAPSHOT_ARTIFACT_TYPES:
                if artifact_type == "delta_graph":
                    continue  # bootstrap has no parent -> no delta (schema-nullable)
                active_object_store.put(
                    job.org_id,
                    key_builder.artifact_key(artifact_type),  # type: ignore[arg-type]
                    artifact_bodies[artifact_type],
                )

            digest_input = b"".join(
                f"{artifact_type}:".encode() + artifact_bodies[artifact_type]
                for artifact_type in SNAPSHOT_ARTIFACT_TYPES
                if artifact_type in artifact_bodies
            )
            snapshot_digest = "sha256:" + hashlib.sha256(digest_input).hexdigest()

        active_report_status.report(
            SnapshotStatusReport(
                snapshot_id=job.snapshot_id,
                state="ready",
                env_digest=env_digest,
                precondition_status=cw_verdict.verdict,
                snapshot_digest=snapshot_digest,
                error=None,
            )
        )
        active_queue.ack(received.receipt_handle)
    except Exception as exc:
        duration_ms = (time.monotonic() - started) * 1000
        outcome_precondition = cw_verdict.verdict if cw_verdict is not None else "unknown"
        if job is not None:
            try:
                active_report_status.report(
                    SnapshotStatusReport(
                        snapshot_id=job.snapshot_id,
                        state="failed",
                        env_digest=env_digest,
                        precondition_status=None,
                        snapshot_digest=None,
                        error=str(exc),
                    )
                )
            except Exception:
                logger.error("snapshot execute loop: secondary report_status failure")
        active_queue.fail(received.receipt_handle)
        record_snapshot_job_completion(
            "failure",
            duration_ms,
            env_digest=env_digest,
            precondition_status=outcome_precondition,
            environ=env,
        )
        logger.error(f"snapshot execute loop: job failed: {exc}")
        return

    # Reached only via the non-exception path: both were assigned unconditionally
    # as the first / near-first statements inside the try block above.
    assert job is not None  # flow-narrowing for mypy strict, not a runtime guard
    assert cw_verdict is not None

    duration_ms = (time.monotonic() - started) * 1000
    record_snapshot_job_completion(
        "success",
        duration_ms,
        env_digest=env_digest,
        precondition_status=cw_verdict.verdict,
        environ=env,
    )
    logger.info(f"snapshot execute loop: job {job.snapshot_id!r} completed")


def main(argv: list[str] | None = None) -> int:
    """Container entrypoint: fail-closed boot gate, then the execute loop.

    Wired by ``ENTRYPOINT ["python", "-m", "services.snapshot.worker"]``. Step 1
    is the INV-2 ORIGIN gate: bind ``env_digest`` or refuse to start
    (exit non-zero) — exactly the DOC §7 contract ("Refuse to start; ECS task
    exits non-zero"). Step 2 hands off to :func:`run_execute_loop`, using its
    production (env-var-derived / fail-closed-by-default) collaborators.

    Returns the process exit code: ``0`` on a completed boot (whether or not a
    job was available / succeeded / failed — :func:`run_execute_loop` never
    propagates a job-level failure, per its own docstring, DOC §7); a failed
    boot gate returns ``1`` (fail-closed).
    """
    _ = argv  # the worker takes no CLI args; ECS injects config via env vars.
    try:
        env_digest = boot()
    except EnvDigestMissing as exc:
        # Fail-closed boot refusals stay on plain stderr: the AC-DEPLOY-03b
        # structured envelope requires a non-empty env_digest, which is exactly
        # what is missing here (the process never serves traffic).
        print(f"FATAL (INV-2 fail-closed): {exc}", file=sys.stderr)
        return 1
    # AC-DEPLOY-03b: every log line from this entrypoint rides the structured
    # JSON envelope (service, build_commit, env_digest) via ScanipyJsonFormatter.
    get_logger("snapshot-worker").info("snapshot worker boot: env_digest bound")
    run_execute_loop(env_digest)
    return 0


__all__ = [
    "ENV_DIGEST_VAR",
    "ArgvAllowlistViolation",
    "EnvDigestMissing",
    "IncrementalSnapshotNotSupportedError",
    "MalformedSnapshotJobError",
    "NoSourceFilesFoundError",
    "ParseSourceFn",
    "ReportStatusPort",
    "SnapshotJob",
    "SnapshotQueuePort",
    "SnapshotStatusReport",
    "UnknownTool",
    "boot",
    "main",
    "record_snapshot_job_completion",
    "resolve_env_digest",
    "run_execute_loop",
    "secure_run",
]


if __name__ == "__main__":  # pragma: no cover — exercised only as the container entrypoint.
    sys.exit(main())
