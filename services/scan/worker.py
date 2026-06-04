# ruff: noqa: N803
#   ``S_version`` keeps its capital S throughout: it is the normative provenance
#   field name (INV-2; DOC-PROVENANCE §2, DOC-SARIF §5/§6, ``.claude/rules/02``).
#   Renaming it to ``s_version`` would break the byte-canonical SARIF key order
#   that CMP-FND-01 emits and the Attestor (CMP-CP-05) attests. The capital-S
#   appears as a method-argument name in the solver-port signatures; suppressed
#   file-wide (N803) rather than per-line — matching ``analysis/ifds/solver.py``.
"""CMP-ORCH-03 — detector-agnostic worker (the per-finding ``origin`` setter).

This module is the **canonical INV-1 setter site** (DOC-CMP-ORCH-03 §1, §3.3):
the single place in the pipeline where each finding's ``origin`` is assigned at
emission time. It loads the CPG once per job, resolves the detector via the
CMP-DET-02 registry, dispatches on ``detector.engine`` to either the CMP-CORE-01
IFDS/IDE solver (core engines) or the oracle-adapter port (oracle engines),
stamps the four required provenance fields onto every finding (RULE-6: ``origin``,
``S_version``, ``env_digest``, ``cpg_order_hash`` + its INV-5 annotation), and
projects the result through the CMP-FND-01 canonical SARIF emitter.

Source-of-truth: ``DOC-CMP-ORCH-03`` (§3 interface, §6 data flow, §8 threading),
``.claude/rules/05-determinism.md`` (the §3.3 ``origin`` setter is **normative**
and quoted verbatim below), ``.claude/rules/02-provenance.md`` (ORCH-03 threads
ALL FOUR fields), ``docs/cross-cutting/DOC-SARIF.md`` (emission path).

MODULE PATH RECONCILE (reported, not invented — CLAR-CORE-01 precedent).
  DOC-CMP-ORCH-03 §1/§11 and the test-stub TODOs name ``tools/scan/worker/
  worker.py``. CLAUDE.md §12 and the task prompt say ``services/scan/``. The
  tiebreaker is the authoritative CI mypy scope
  (``mypy analysis detectors integrations services workers``): ``tools/`` is NOT
  in it, ``services/`` IS. This module therefore ships at ``services/scan/
  worker.py``. ``CLAR-ORCH-01`` is surfaced for the DOC path discrepancy (the
  implementation agent cannot edit WBS §17; the orchestrator files it).

BUILD-AHEAD REGIME (sanctioned by CLAR-PROC-01, WBS §17 RESOLVED 2026-06-04).
  Two upstream dependencies are not yet shippable in a hermetic CI:

  1. **Oracle adapters** (Semgrep / Joern CPG-query / CodeQL) need real binaries
     that do not exist in CI. Per CLAR-PROC-01 condition (2), the oracle path is
     a TYPED port (:class:`OracleAdapter`); the production default
     (:func:`fail_closed_oracle_adapter`) raises a typed ``NotImplementedError``
     naming the gated dependency. A hermetic test injects a deterministic fake
     via the same typed seam — never a host-binary shell-out.

  2. **CMP-CORE-02** (``slice_fingerprint`` / ``fingerprint_class`` per finding)
     HAS LANDED (``analysis.fingerprint.compute_slice_fingerprint``, Algorithm 3).
     Core findings are now fingerprinted by the REAL CMP-CORE-02 upstream, in
     :func:`_findings_from_core` — the one site where the solver finding's real
     ``witness`` and the ``cpg`` are both live — and the per-finding
     ``slice_fingerprint`` is pre-filled at construction. The typed
     :class:`SliceFingerprinter` port and its fail-closed production default
     (:func:`fail_closed_slice_fingerprinter`) are RETAINED but now cover ONLY
     findings the upstream did NOT pre-fill — i.e. ORACLE findings, which have no
     slice witness through the CPG (their fingerprint stays fail-closed; a real
     oracle slice-identity is out of scope here). The run_detector threading loop
     respects the upstream pre-fill via ``if not f.slice_fingerprint`` and never
     re-computes a core finding's fingerprint. The hermetic ORCH-03 spec tests
     still inject a deterministic fake to exercise the port in isolation.

  The oracle adapter value is never computed-as-fake on the production path
  (CLAR-PROC-01 condition (2)): the prod seam raises; only a test double supplies
  a value.
  ``fingerprint_class`` is sourced from CMP-CORE-03 (it rides on the run-level
  ``canonical_order(cpg)``), which deviates from DOC §4.2's "carried from
  CMP-CORE-02" — the source-attribution conflict is filed as CLAR-ORCH-03
  (OPEN; Architect to reconcile). This wiring does NOT resolve it: the run-level
  ``fingerprint_class`` threading stays byte-for-byte unchanged. The real
  CMP-CORE-02 ``compute_slice_fingerprint`` (now wired in
  :func:`_findings_from_core`) supplies only the per-finding ``slice_fingerprint``
  hex; whether the per-finding CMP-CORE-02 ``fingerprint_class`` should also flow
  here, replacing the run-level CMP-CORE-03 value, remains the OPEN CLAR-ORCH-03
  question and is left untouched.

INTERFACE RECONCILE: CLAR-ORCH-02 (is_mixed sourcing); WorkerJob shape
deviations filed as CLAR-ORCH-04 (precondition_status source) and
CLAR-ORCH-05 (hmac_key_id/callback_path omitted until the callback glue
lands).
  The shipped ``detectors.registry.Detector`` (CMP-DET-02) has no ``is_mixed``
  flag and carries a single ``spec`` (not a ``specs`` list) as
  DOC-CMP-ORCH-03 §3.1 sketches. AC-ORCH-03b (mixed-detector per-finding origin)
  therefore has no signal on the shipped type. This worker consumes a
  :class:`DetectorLike` Protocol that carries ``is_mixed`` so a mixed detector
  can be driven through the same setter; the shipped registry ``Detector``
  satisfies it with ``is_mixed`` defaulted ``False`` via :func:`as_detector_like`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable
from uuid import UUID

from analysis.fingerprint import compute_slice_fingerprint
from analysis.ordering import (
    CPG,
    CPG_ORDER_HASH_ANNOTATION,
    canonical_order,
)
from analysis.sarif.canonical_emit import SARIFLog, WorkerFinding, normalize

if TYPE_CHECKING:
    from collections.abc import Iterable

    from analysis.ifds.dsl.spec import Spec
    from analysis.ifds.solver import Finding as SolverFinding

# ---------------------------------------------------------------------------
# Engine -> origin partition (NORMATIVE, .claude/rules/05-determinism.md).
# Single source of truth; ``CMP-DET-02.derive_partition`` is the registration
# twin. A new engine may not be added without amending AC-DET-02c,
# .claude/rules/05-determinism.md and DOC-PARTITION §3 in lockstep (RULE-4).
# ---------------------------------------------------------------------------

Origin = Literal["deterministic-core", "oracle-passthrough"]
Engine = Literal["ifds", "ide", "semgrep", "cpg-query", "external"]
Severity = Literal["info", "low", "medium", "high", "critical"]
PreconditionStatus = Literal["closed-world", "degraded", "full-reparse"]

CORE_ENGINES: tuple[str, ...] = ("ifds", "ide")
ORACLE_ENGINES: tuple[str, ...] = ("semgrep", "cpg-query", "external")
_ALL_ENGINES: frozenset[str] = frozenset(CORE_ENGINES) | frozenset(ORACLE_ENGINES)


class InvariantViolation(Exception):  # noqa: N818  (named verbatim, DOC §3.5/§7)
    """A per-finding invariant could not be discharged and the worker refuses to
    guess (fail-closed; DOC-CMP-ORCH-03 §3.5, §7 "Safe-direction discipline").

    Raised when: ``detector.engine`` is outside the enumerated set at runtime
    (defence in depth behind CMP-DET-02 AC-DET-02b); a mixed detector emits a
    finding with ``from_core_engine is None``; or a required versioned parameter
    (``S_version`` / ``env_digest``) is missing/blank on the job (INV-2).
    """


# ---------------------------------------------------------------------------
# §3.1 — SQS message body (produced by CMP-ORCH-01, scheduled by CMP-ORCH-02)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkerJob:
    """The job message the worker dequeues (DOC-CMP-ORCH-03 §3.1).

    Carries the two INV-2 versioned parameters as strings:
    ``S_version`` (semver) and ``env_digest`` (``"sha256:"`` + 64 hex). The worker
    threads these verbatim onto every emitted finding; it never re-derives them.
    """

    job_id: UUID
    scan_id: UUID
    snapshot_id: UUID
    codebase_id: UUID
    commit_sha: str  # 40-hex
    detector_id: str
    S_version: str  # semver — INV-2; bound by CMP-ORCH-01 at scan submission
    env_digest: str  # "sha256:" + 64 hex — INV-2; from CMP-SNAP-01 image digest
    precondition_status: PreconditionStatus = (
        "closed-world"  # job-carried provisionally — CLAR-ORCH-04
    )
    # CLAR-ORCH-05 DISCHARGE (CMP-ORCH-01 PR): the HMAC-callback glue lands with
    # CMP-ORCH-01, so DOC-CMP-ORCH-03 §3.1's two required fields become REAL here.
    # ``hmac_key_id`` keys the per-job HMAC secret the worker signs its callback
    # with (DOC-API §2.3); ``callback_path`` is the SDD-normative status path with
    # ``job_id`` substituted (DOC-API §4.5). Defaulted "" so the CMP-ORCH-03
    # hermetic fakes (which predate the callback glue) still construct unchanged;
    # CMP-ORCH-01's ``post_scans`` populates both on every fanned job.
    hmac_key_id: str = ""  # CLAR-ORCH-05 — keys the per-job HMAC secret
    callback_path: str = ""  # CLAR-ORCH-05 — "/api/v1/jobs/{job_id}/status"
    policy_overrides: dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# §3.1 — per-finding emission shape (WORKER-internal; satisfies WorkerFinding)
# ---------------------------------------------------------------------------


@dataclass(eq=False)
class Finding:
    """The worker-internal finding record (DOC-CMP-ORCH-03 §3.1).

    Structurally satisfies the CMP-FND-01 :class:`WorkerFinding` ``Protocol``
    (hex strings for the two digest fields; ``S_version`` with its capital S).
    The provenance fields are populated by :func:`run_detector` (the §3.3 setter
    site); a finding leaves the worker with ``origin`` in the two-value enum,
    never ``None`` and never ``"mixed"`` (INV-1 belt).

    ``eq=False`` gives identity-based ``__hash__`` / ``__eq__``: the worker
    MUTATES each finding in place while threading the four provenance fields, so a
    value-hashed frozen record is unusable; the worker returns a ``set[Finding]``
    (DOC §3.1) of distinct objects. FND-01's ``normalize`` re-keys results by the
    canonical sort tuple regardless, so identity semantics here are safe.
    """

    # detection content -----------------------------------------------------
    # NOTE: ``severity`` / ``precondition_status`` / ``engine`` are typed ``str``
    # (not their narrower Literal aliases) to match the CMP-FND-01
    # :class:`WorkerFinding` Protocol, whose attribute types are matched
    # invariantly — a narrower Literal would not satisfy the Protocol. The
    # construction sites (:func:`_findings_from_core`, the fakes) still pass
    # in-enum values; FND-01's ``normalize`` validates membership at emission.
    rule_id: str
    message: str
    uri: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    severity: str
    class_: str
    status: str
    precondition_status: str
    engine: str
    # mixed-detector hint (AC-ORCH-03b) — set by the adapter on each emission
    # when ``detector.is_mixed``; MUST be non-None on a mixed detector (the
    # setter raises otherwise). Ignored on a non-mixed detector.
    from_core_engine: bool | None = None
    # provenance fields (set/threaded by run_detector) ----------------------
    origin: Origin = "deterministic-core"  # OVERWRITTEN by the setter; never read pre-set
    determinism_partition: Origin = "deterministic-core"  # mirror of origin
    S_version: str = ""  # threaded from WorkerJob (INV-2)
    env_digest: str = ""  # threaded from WorkerJob (INV-2)
    cpg_order_hash: str = ""  # hex; carried from CMP-CORE-03 (INV-5)
    cpg_order_hash_annotation: str = CPG_ORDER_HASH_ANNOTATION  # INV-5 pinned literal
    fingerprint_class: str = ""  # "strong" | "weak"; carried from CMP-CORE-03
    slice_fingerprint: str = ""  # hex; from real CMP-CORE-02 for core findings
    #   (pre-filled in _findings_from_core); the SliceFingerprinter port now only
    #   covers findings not pre-filled upstream (oracle — no slice witness)
    witness_blob_uri: str | None = None
    spec_provenance: str | None = None


# A static guard that :class:`Finding` satisfies the FND-01 input Protocol. If a
# field name drifts (e.g. ``S_version`` -> ``s_version``) this stops type-checking.
def _finding_is_workerfinding(f: Finding) -> WorkerFinding:
    return f


# ---------------------------------------------------------------------------
# Typed ports (build-ahead seams, CLAR-PROC-01 condition (2))
# ---------------------------------------------------------------------------


@runtime_checkable
class DetectorLike(Protocol):
    """The detector surface the worker reads (DOC-CMP-ORCH-03 §3.1).

    Superset of the shipped ``detectors.registry.Detector`` plus the ``is_mixed``
    flag AC-ORCH-03b needs (the shipped record lacks it — CLAR-ORCH-02). Any
    object exposing these attributes — the registry record wrapped by
    :func:`as_detector_like`, or a mixed-detector test double — is a valid input.
    """

    @property
    def id(self) -> str: ...
    @property
    def engine(self) -> str: ...
    @property
    def severity_default(self) -> str: ...
    @property
    def is_mixed(self) -> bool: ...
    @property
    def spec(self) -> Spec | None: ...


@runtime_checkable
class _SolverResultLike(Protocol):
    @property
    def findings(self) -> frozenset[SolverFinding]: ...


@runtime_checkable
class CoreSolver(Protocol):
    """The CMP-CORE-01 solver port. ``solve`` returns objects carrying the
    solver's :class:`~analysis.ifds.solver.Finding` shape (sink/spec_id/witness +
    threaded provenance). Defaulted to the real :func:`analysis.ifds.solver.solve`
    via :func:`default_core_solver`."""

    def solve(
        self, cpg: CPG, spec: Spec, *, S_version: str, env_digest: bytes
    ) -> _SolverResultLike: ...


@runtime_checkable
class OracleAdapter(Protocol):
    """The oracle-adapter port (Semgrep / Joern CPG-query / CodeQL / external).

    CLAR-PROC-01 condition (2): the real adapters are env-gated (no binaries in
    CI). The worker dispatches oracle-engine detectors through this typed seam
    and NEVER shells out to a host binary itself. ``run`` returns the raw oracle
    findings; the worker stamps provenance onto them (the oracle adapter sets
    ``from_core_engine`` only for a mixed detector's oracle portion).
    """

    def run(self, detector: DetectorLike, cpg: CPG, job: WorkerJob) -> Iterable[Finding]: ...


@runtime_checkable
class SliceFingerprinter(Protocol):
    """Fallback slice-fingerprint port for findings NOT pre-filled upstream.

    CMP-CORE-02 (Algorithm 3) has landed and is wired into
    :func:`_findings_from_core`, so CORE findings arrive at the threading loop
    already carrying a real ``slice_fingerprint`` (the ``if not f.slice_fingerprint``
    guard skips them). This port therefore now serves only findings WITHOUT an
    upstream pre-fill — i.e. ORACLE findings, which have no slice witness through
    the CPG. ``fingerprint(witness)`` returns the 64-hex ``slice_fingerprint`` for
    such a finding's witness projection. The production default fails closed (an
    oracle slice-identity is out of scope); the hermetic ORCH-03 spec tests inject
    a deterministic fake to exercise this seam in isolation.
    """

    def fingerprint(self, witness: tuple[int, ...]) -> str: ...


# ---------------------------------------------------------------------------
# Fail-closed production defaults (CLAR-PROC-01 condition (2))
# ---------------------------------------------------------------------------


class _FailClosedOracleAdapter:
    """Production oracle adapter: raises until the env-gated real adapters land."""

    def run(self, detector: DetectorLike, cpg: CPG, job: WorkerJob) -> Iterable[Finding]:
        raise NotImplementedError(
            f"oracle adapter for engine {detector.engine!r} is env-gated "
            f"(CMP-ORCH-03 build-ahead, CLAR-PROC-01): the real Semgrep/Joern/"
            f"CodeQL adapters need binaries absent from CI. Inject an OracleAdapter "
            f"via run_detector(..., oracle_adapter=...) in a hermetic test."
        )


class _FailClosedSliceFingerprinter:
    """Production fallback fingerprinter for findings NOT pre-filled upstream.

    CMP-CORE-02 fingerprints CORE findings upstream in :func:`_findings_from_core`,
    so this default only ever fires for a finding that reached the threading loop
    WITHOUT a ``slice_fingerprint`` — i.e. an ORACLE finding (no slice witness
    through the CPG). A real oracle slice-identity is out of scope here, so the
    production seam fails closed (it does not fabricate a value).
    """

    def fingerprint(self, witness: tuple[int, ...]) -> str:
        raise NotImplementedError(
            "slice_fingerprint for a finding without an upstream CMP-CORE-02 "
            "pre-fill (an oracle finding has no slice witness through the CPG) is "
            "out of scope (CMP-ORCH-03 build-ahead, CLAR-PROC-01). Inject a "
            "SliceFingerprinter via run_detector(..., slice_fingerprinter=...) in a "
            "hermetic test to exercise this fallback seam."
        )


def fail_closed_oracle_adapter() -> OracleAdapter:
    """The default oracle adapter: fail-closed until the env-gated adapters land."""
    return _FailClosedOracleAdapter()


def fail_closed_slice_fingerprinter() -> SliceFingerprinter:
    """The default fallback fingerprinter: fail-closed for findings without an
    upstream CMP-CORE-02 pre-fill (oracle findings; out of scope here)."""
    return _FailClosedSliceFingerprinter()


def default_core_solver() -> CoreSolver:
    """The default core solver port bound to the real CMP-CORE-01 ``solve``."""
    from analysis.ifds.solver import solve as _solve
    from analysis.ordering import Sha256

    class _RealCoreSolver:
        def solve(
            self, cpg: CPG, spec: Spec, *, S_version: str, env_digest: bytes
        ) -> _SolverResultLike:
            return _solve(cpg, spec, S_version=S_version, env_digest=Sha256(env_digest))

    return _RealCoreSolver()


# ---------------------------------------------------------------------------
# Registry adapter (shipped Detector -> DetectorLike)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _DetectorView:
    """A :class:`DetectorLike` view over a shipped registry ``Detector``."""

    id: str
    engine: str
    severity_default: str
    is_mixed: bool
    spec: Spec | None


def as_detector_like(detector: object, *, is_mixed: bool = False) -> DetectorLike:
    """Adapt a shipped ``detectors.registry.Detector`` to :class:`DetectorLike`.

    The shipped record has no ``is_mixed`` flag (CLAR-ORCH-02); it is supplied
    here, defaulting ``False`` (every Stage-A core detector is non-mixed). Reads
    ``id``, ``engine``, ``severity_default``, ``spec`` off the shipped record.
    """
    return _DetectorView(
        id=str(detector.id),  # type: ignore[attr-defined]
        engine=str(detector.engine),  # type: ignore[attr-defined]
        severity_default=str(detector.severity_default),  # type: ignore[attr-defined]
        is_mixed=is_mixed,
        spec=getattr(detector, "spec", None),
    )


# ---------------------------------------------------------------------------
# INV-2 — versioned-parameter validation (fail-fast, never default)
# ---------------------------------------------------------------------------

_SHA256_PREFIX = "sha256:"


def _require_versioned_params(job: WorkerJob) -> None:
    """INV-2 fail-fast: refuse to run with a missing/malformed S_version or
    env_digest (DOC-CMP-ORCH-03 §5 INV-2 row). Raises :class:`InvariantViolation`
    — the worker never threads a blank versioned parameter onto a finding."""
    if not job.S_version:
        raise InvariantViolation(
            "WorkerJob.S_version is required (INV-2); refusing to run against an "
            "unpinned accepted-spec set"
        )
    env = job.env_digest
    if not env or not env.startswith(_SHA256_PREFIX) or len(env) != len(_SHA256_PREFIX) + 64:
        raise InvariantViolation(
            f"WorkerJob.env_digest must be 'sha256:'+64hex (INV-2); got {env!r}"
        )
    hexpart = env[len(_SHA256_PREFIX) :]
    if any(c not in "0123456789abcdef" for c in hexpart):
        raise InvariantViolation(
            f"WorkerJob.env_digest hex segment is not lowercase hex (INV-2); got {env!r}"
        )


def _env_digest_bytes(job: WorkerJob) -> bytes:
    """The 32 raw bytes the CMP-CORE-01 ``solve`` wants, parsed from the job's
    ``"sha256:"``-prefixed hex. The STRING (with prefix) is what is threaded onto
    findings; this conversion is solely for the solver call (advisor trap #4)."""
    return bytes.fromhex(job.env_digest[len(_SHA256_PREFIX) :])


# ---------------------------------------------------------------------------
# §3.3 — the per-finding origin setter (NORMATIVE)
# ---------------------------------------------------------------------------


def _stamp_origin(finding: Finding, detector: DetectorLike) -> None:
    """Assign ``finding.origin`` (and its mirror ``determinism_partition``).

    Byte-identical to the canonical pattern in ``.claude/rules/05-determinism.md``
    "How origin is set", with the DOC §3.3 operational requirements layered on:

    - mixed detector: branch on ``finding.from_core_engine`` (raise if ``None``);
    - non-mixed detector: branch on ``detector.engine`` membership in CORE_ENGINES;
    - engine outside the enumerated set: raise (fail-closed; never guess);
    - ``determinism_partition`` mirrors ``origin``;
    - belt assertion: ``origin`` is in the two-value enum on exit.
    """
    if detector.engine not in _ALL_ENGINES:
        raise InvariantViolation(
            f"detector.engine={detector.engine!r} outside "
            f"{sorted(_ALL_ENGINES)} (DOC-CMP-ORCH-03 §3.5; CMP-DET-02 should "
            f"have rejected at registration). Refusing to guess an origin."
        )

    if detector.is_mixed:
        if finding.from_core_engine is None:
            raise InvariantViolation(
                f"mixed detector {detector.id!r} emitted a finding with "
                f"from_core_engine=None (DOC-CMP-ORCH-03 §3.4). Refusing to guess."
            )
        finding.origin = "deterministic-core" if finding.from_core_engine else "oracle-passthrough"
    else:
        finding.origin = (
            "deterministic-core" if detector.engine in CORE_ENGINES else "oracle-passthrough"
        )

    finding.determinism_partition = finding.origin
    # INV-1 belt (DOC §3.3 req. 5): never None, never "mixed".
    if finding.origin not in ("deterministic-core", "oracle-passthrough"):  # pragma: no cover
        raise InvariantViolation(
            f"post-setter origin={finding.origin!r} is not a valid partition (INV-1)"
        )


# ---------------------------------------------------------------------------
# Core / oracle dispatch
# ---------------------------------------------------------------------------


def _physical_location(node_id: int) -> tuple[str, int, int, int, int]:
    """Deterministic physical location for a finding.

    The PR1 CMP-CORE-03 ``CPGNode`` model carries no file/line (advisor trap #2):
    the production CPG (CMP-SNAP-01) will. Until then, a finding's location is
    derived deterministically from its real sink node id so the SARIF region is
    populated and byte-stable. This is detection content (from real solver
    output), not a gated-dependency provenance value, and is replaced by the real
    node location once CMP-SNAP-01 materialises file/line on the CPG node.
    """
    line = node_id + 1
    return (f"cpg://node/{node_id}", line, 1, line, 1)


def _coerce_severity(value: str) -> Severity:
    """Map a detector's ``severity_default`` onto the SARIF severity enum.

    The registry permits ``{low, medium, high, critical}``; FND-01 permits
    ``{info, low, medium, high, critical}``. The sets overlap; an unknown value
    is a hard error rather than a silent default (fail-closed)."""
    if value not in ("info", "low", "medium", "high", "critical"):
        raise InvariantViolation(
            f"detector severity_default={value!r} outside the SARIF severity enum"
        )
    return value  # type: ignore[return-value]  # membership checked above


def _findings_from_core(
    detector: DetectorLike,
    cpg: CPG,
    job: WorkerJob,
    *,
    solver: CoreSolver,
) -> list[Finding]:
    """Run the CMP-CORE-01 solver and adapt each solver Finding to a worker
    :class:`Finding` (advisor trap #2 mapping). Provenance is stamped later by
    :func:`run_detector` (the single setter site)."""
    spec = detector.spec
    if spec is None:
        raise InvariantViolation(
            f"core-engine detector {detector.id!r} carries no DSL spec; "
            f"CMP-DET-02 closure_check should have rejected it (E-REG-002)"
        )
    result = solver.solve(cpg, spec, S_version=job.S_version, env_digest=_env_digest_bytes(job))
    engine: Engine = "ifds" if detector.engine == "ifds" else "ide"
    severity = _coerce_severity(detector.severity_default)
    out: list[Finding] = []
    for sf in result.findings:
        uri, sl, sc, el, ec = _physical_location(int(sf.sink))
        # CMP-CORE-02 wiring (CLAR-PROC-01 build-ahead composition; class sourcing
        # is CLAR-ORCH-03, OPEN — untouched here). This is the ONE site where the
        # solver finding ``sf`` (carrying the real ``witness: tuple[NodeId, ...]``)
        # and the ``cpg`` are both live, so it is where Algorithm 3 must run. The
        # real :func:`compute_slice_fingerprint` consumes ``sf.witness`` directly
        # (it never sees the worker Finding's location projection); the run_detector
        # threading loop's ``if not f.slice_fingerprint`` then respects this
        # pre-fill and the fail-closed port never fires for a core finding.
        # ``compute_slice_fingerprint`` raises EmptyWitness / WitnessNotInCPG
        # (DOC-CMP-CORE-02 §7) — we let them PROPAGATE (fail-closed; never a
        # silent fallback). ``slice_fingerprint`` is ``Sha256`` (raw bytes, per
        # ``analysis.ordering``); ``.hex()`` yields the 64-hex ``str`` the worker
        # Finding field / CMP-FND-01 ``WorkerFinding`` Protocol expect — the same
        # conversion the run-level ``order.cpg_order_hash.hex()`` uses below.
        slice_fingerprint_hex = compute_slice_fingerprint(sf, cpg).slice_fingerprint.hex()
        out.append(
            Finding(
                rule_id=sf.spec_id,
                message=f"taint reaches sink (spec {sf.spec_id})",
                uri=uri,
                start_line=sl,
                start_col=sc,
                end_line=el,
                end_col=ec,
                severity=severity,
                class_=spec.class_,
                status="open",
                precondition_status=job.precondition_status,
                engine=engine,
                from_core_engine=None,  # non-mixed core detector: setter uses engine
                # cpg_order_hash / fingerprint_class threaded at run_detector
                # from the worker-level canonical_order (advisor trap #3), NOT
                # read off the solver finding (oracle findings have no solver).
                slice_fingerprint=slice_fingerprint_hex,  # CMP-CORE-02 (Algorithm 3)
                witness_blob_uri=None,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Public entry point (DOC-CMP-ORCH-03 §3.1, §6)
# ---------------------------------------------------------------------------


def run_detector(
    detector: DetectorLike,
    cpg: CPG,
    job: WorkerJob,
    *,
    solver: CoreSolver | None = None,
    oracle_adapter: OracleAdapter | None = None,
    slice_fingerprinter: SliceFingerprinter | None = None,
) -> set[Finding]:
    """Run ``detector`` against the loaded ``cpg``, returning provenance-threaded
    findings (DOC-CMP-ORCH-03 §3.1 / §6). The INV-1 setter site and the INV-2
    threading site.

    Steps (DOC §6):
      1. INV-2 fail-fast on the job's versioned parameters.
      2. Engine-set guard (fail-closed; InvariantViolation otherwise).
      3. ``canonical_order(cpg)`` ONCE per job -> ``cpg_order_hash`` +
         ``fingerprint_class`` threaded onto EVERY finding (core and oracle alike;
         advisor trap #3 — oracle findings never touch the solver).
      4. Dispatch on ``detector.engine``: core engines -> CMP-CORE-01 solver;
         oracle engines -> the injected :class:`OracleAdapter` port.
      5. Per finding: stamp ``origin`` (§3.3 setter), mirror
         ``determinism_partition``, thread ``S_version`` / ``env_digest`` /
         ``cpg_order_hash`` (+ annotation) / ``fingerprint_class`` /
         ``slice_fingerprint``.

    The oracle adapter and slice fingerprinter default to fail-closed production
    seams (CLAR-PROC-01); a hermetic test injects deterministic fakes.
    """
    _require_versioned_params(job)

    if detector.engine not in _ALL_ENGINES:
        raise InvariantViolation(
            f"detector.engine={detector.engine!r} outside {sorted(_ALL_ENGINES)} "
            f"(DOC-CMP-ORCH-03 §3.5). Refusing to run with an unknown engine."
        )

    solver = solver if solver is not None else default_core_solver()
    oracle_adapter = oracle_adapter if oracle_adapter is not None else fail_closed_oracle_adapter()
    slice_fp = (
        slice_fingerprinter
        if slice_fingerprinter is not None
        else fail_closed_slice_fingerprinter()
    )

    # Step 3 — CMP-CORE-03 once per job. INV-5: the hash is canonical iff
    # fingerprint_class == "strong"; the annotation rides verbatim on every finding.
    order = canonical_order(cpg)
    cpg_order_hash_hex = order.cpg_order_hash.hex()
    fingerprint_class = order.fingerprint_class

    # Step 4 — dispatch on engine.
    if detector.engine in CORE_ENGINES:
        raw = _findings_from_core(detector, cpg, job, solver=solver)
    else:
        raw = list(oracle_adapter.run(detector, cpg, job))

    # Step 5 — per-finding provenance threading + the §3.3 origin setter.
    out: set[Finding] = set()
    for f in raw:
        _stamp_origin(f, detector)  # INV-1 (the only origin-writing site)
        f.S_version = job.S_version  # INV-2 (verbatim from the job)
        f.env_digest = job.env_digest  # INV-2 (verbatim; keeps the "sha256:" prefix)
        f.cpg_order_hash = cpg_order_hash_hex  # INV-5 (carried from CMP-CORE-03)
        f.cpg_order_hash_annotation = CPG_ORDER_HASH_ANNOTATION  # INV-5 pinned literal
        f.fingerprint_class = fingerprint_class  # INV-5 conditional class
        if not f.slice_fingerprint:
            # CORE findings already carry a real CMP-CORE-02 ``slice_fingerprint``
            # (pre-filled in _findings_from_core via compute_slice_fingerprint), so
            # this branch is reached ONLY for findings without an upstream pre-fill
            # — i.e. oracle findings (no slice witness through the CPG). The prod
            # fallback seam fails closed; an ORCH-03 hermetic test injects a fake.
            f.slice_fingerprint = slice_fp.fingerprint(_witness_of(f))
        out.add(f)
    return out


def _witness_of(finding: Finding) -> tuple[int, ...]:
    """The location projection feeding the injected/fallback SliceFingerprinter port.

    The worker :class:`Finding` does not retain the solver witness (it is not a
    SARIF field), so this projects the finding's location for the fallback seam
    (now reached only for findings without an upstream pre-fill — oracle findings).
    The REAL CMP-CORE-02 does NOT consume this projection: it consumes the solver
    finding's ``witness`` directly, upstream in :func:`_findings_from_core`
    (DOC-CMP-ORCH-03 §6 step 6a) — which is exactly what this docstring always
    promised, now realised by the live wiring."""
    return (finding.start_line, finding.start_col, finding.end_line, finding.end_col)


# ---------------------------------------------------------------------------
# SARIF emission via CMP-FND-01 (DOC-CMP-ORCH-03 §3.2)
# ---------------------------------------------------------------------------


def emit_sarif(findings: set[Finding], job: WorkerJob) -> SARIFLog:
    """Project worker findings through the CMP-FND-01 canonical SARIF emitter
    (DOC-CMP-ORCH-03 §3.2). Returns the byte-deterministic two-Run SARIF log.

    ``llm_triage_flag`` is ``False``: the worker NEVER calls the LLM (INV-3
    structural fence; the Attestor attests core byte-identity under
    ``LLM_TRIAGE=off``). The run-level versioned parameters come from the job.
    """
    # Widen to the FND-01 input Protocol: ``Finding`` satisfies ``WorkerFinding``
    # structurally (see :func:`_finding_is_workerfinding`), but a
    # ``frozenset[Finding]`` is not implicitly a ``frozenset[WorkerFinding]``
    # under invariance — annotate the widened set explicitly.
    worker_findings: frozenset[WorkerFinding] = frozenset(findings)
    return normalize(
        worker_findings,
        scan_id=job.scan_id,
        snapshot_id=job.snapshot_id,
        codebase_id=job.codebase_id,
        commit_sha=job.commit_sha,
        S_version=job.S_version,
        env_digest=job.env_digest,
        precondition_status=job.precondition_status,
        llm_triage_flag=False,
    )
