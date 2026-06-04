"""Hermetic offline fakes for CMP-ORCH-03 (detector-agnostic worker) specs.

No real AWS, no Semgrep/CodeQL binaries, no PostgreSQL. The worker's two
build-ahead seams (the oracle-adapter port and the CMP-CORE-02 slice
fingerprinter, both env/dependency-gated per CLAR-PROC-01) are supplied here as
deterministic in-memory doubles, injected through the worker's typed DI seams —
never computed-as-fake on the production path, which fails closed.

Mirrors the established DI-fake convention (``tests/snap04_fakes.py``,
``tests/fnd03_fakes.py``): a single module that builds the synthetic inputs and
the injected ports so every spec test stays hermetic.

INDEPENDENCE: these fakes never import a real oracle binary wrapper; the oracle
verdict (which findings, and their per-finding ``from_core_engine``) is always
injected, never derived from a host tool.
"""

from __future__ import annotations

import pathlib
import uuid
from dataclasses import dataclass

from analysis.ifds.dsl import parse_spec
from analysis.ifds.dsl.spec import Spec
from analysis.ordering import CPG
from services.scan.worker import (
    DetectorLike,
    Finding,
    OracleAdapter,
    SliceFingerprinter,
    WorkerJob,
)

# The real Stage-A injection spec landed in #288 (CMP-DET-03). The PR1 matcher is
# exact: a clause pattern matches a CPG node iff ``str(pattern) ==
# node.operator_or_literal``. The Python (Flask -> subprocess) source/sink pair
# below is wired into the synthetic CPG so the positive end-to-end test fires a
# REAL finding (anti-vacuity backbone), not a fabricated one.
_INJECTION_SPEC_PATH = "detectors/injection/specs/java-py-injection.dsl.yaml"
_PY_SOURCE_PATTERN = "flask.request.args.get(*)"
_PY_SINK_PATTERN = "subprocess.Popen(arg[0])"

# A deterministic, valid-shaped job. ``S_version`` semver + ``env_digest``
# "sha256:"+64hex satisfy the worker's INV-2 fail-fast.
_GOOD_ENV_DIGEST = "sha256:" + "a" * 64


def load_injection_spec() -> Spec:
    """Parse the real #288 Stage-A injection DSL spec."""
    text = pathlib.Path(_INJECTION_SPEC_PATH).read_text(encoding="utf-8")
    return parse_spec(text, source_path=_INJECTION_SPEC_PATH)


def injection_taint_cpg() -> CPG:
    """A one-procedure CPG: Flask source -> intermediate -> subprocess sink, via
    CFG edges, using the EXACT #288 clause-pattern strings so the PR1 matcher
    fires a real source->sink finding."""
    cpg = CPG()
    entry = cpg.add_node("METHOD", resolved_fqn="m.handler", enclosing_decl_fqn="m.handler")
    src = cpg.add_node(
        "CALL",
        operator_or_literal=_PY_SOURCE_PATTERN,
        enclosing_decl_fqn="m.handler",
        structural_path="0",
    )
    mid = cpg.add_node(
        "IDENTIFIER", operator_or_literal="cmd", enclosing_decl_fqn="m.handler", structural_path="1"
    )
    sink = cpg.add_node(
        "CALL",
        operator_or_literal=_PY_SINK_PATTERN,
        enclosing_decl_fqn="m.handler",
        structural_path="2",
    )
    cpg.add_edge(entry, src, "CFG")
    cpg.add_edge(src, mid, "CFG")
    cpg.add_edge(mid, sink, "CFG")
    return cpg


def good_job(**overrides: object) -> WorkerJob:
    """A valid-shaped :class:`WorkerJob` with deterministic ids. Override any
    field (e.g. ``S_version=""``) to drive a negative/mutation control."""
    base: dict[str, object] = {
        "job_id": uuid.UUID(int=1),
        "scan_id": uuid.UUID(int=2),
        "snapshot_id": uuid.UUID(int=3),
        "codebase_id": uuid.UUID(int=4),
        "commit_sha": "a" * 40,
        "detector_id": "java-py-injection",
        "S_version": "1.4.2",
        "env_digest": _GOOD_ENV_DIGEST,
    }
    base.update(overrides)
    return WorkerJob(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Detector doubles (DetectorLike). The shipped registry Detector has no
# ``is_mixed`` flag (CLAR-ORCH-02); these doubles carry it directly.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FakeDetector:
    """A :class:`DetectorLike` double carrying ``is_mixed`` (CLAR-ORCH-02)."""

    id: str
    engine: str
    severity_default: str
    is_mixed: bool
    spec: Spec | None


def core_injection_detector() -> DetectorLike:
    """A non-mixed ``ifds`` core detector carrying the real #288 injection spec."""
    return FakeDetector(
        id="java-py-injection",
        engine="ifds",
        severity_default="high",
        is_mixed=False,
        spec=load_injection_spec(),
    )


def oracle_semgrep_detector() -> DetectorLike:
    """A non-mixed ``semgrep`` oracle detector (no DSL spec; oracle adapter
    supplies findings)."""
    return FakeDetector(
        id="semgrep-secrets",
        engine="semgrep",
        severity_default="medium",
        is_mixed=False,
        spec=None,
    )


def mixed_crypto_detector() -> DetectorLike:
    """A ``mixed``-class detector (``is_mixed=True``). Its findings are produced by
    the injected mixed oracle adapter, which tags each with ``from_core_engine``
    (AC-ORCH-03b: IFDS portion True, CPG-query portion False)."""
    return FakeDetector(
        id="crypto-misuse",
        engine="semgrep",  # the result-set is tagged per finding, not per engine
        severity_default="high",
        is_mixed=True,
        spec=None,
    )


def out_of_set_engine_detector() -> DetectorLike:
    """A detector with an engine value outside the enumerated set (defence in
    depth: CMP-DET-02 should have rejected it). Drives the fail-closed control."""
    return FakeDetector(
        id="bad-engine",
        engine="quantum",
        severity_default="high",
        is_mixed=False,
        spec=None,
    )


# ---------------------------------------------------------------------------
# Injected ports (build-ahead seams). The worker's prod defaults fail closed;
# these doubles supply deterministic values for hermetic tests.
# ---------------------------------------------------------------------------


class DeterministicSliceFingerprinter:
    """A CMP-CORE-02 stand-in: a fixed-shape 64-hex slice fingerprint keyed
    deterministically on the witness tuple (so the same finding hashes the same
    across runs — byte-identity holds). NOT the real Algorithm 3."""

    def fingerprint(self, witness: tuple[int, ...]) -> str:
        seed = sum((i + 1) * w for i, w in enumerate(witness)) % 16
        return f"{seed:x}" * 64


def deterministic_slice_fingerprinter() -> SliceFingerprinter:
    return DeterministicSliceFingerprinter()


def _oracle_finding(
    rule_id: str, node: int, *, from_core_engine: bool | None, engine: str
) -> Finding:
    """One pre-provenance oracle finding (the worker stamps origin/INV-2/INV-5).

    ``engine`` is per-finding so a mixed detector's IFDS portion carries a core
    engine (``ifds``) while its pattern portion carries an oracle engine
    (``cpg-query``) — keeping ``engine`` coherent with the partition the worker's
    setter assigns from ``from_core_engine`` (DOC-CMP-ORCH-03 §3.4 / INV-1)."""
    return Finding(
        rule_id=rule_id,
        message=f"oracle match {rule_id}",
        uri=f"oracle://{rule_id}/{node}",
        start_line=node + 1,
        start_col=1,
        end_line=node + 1,
        end_col=1,
        severity="medium",
        class_="secrets",
        status="open",
        precondition_status="closed-world",
        engine=engine,
        from_core_engine=from_core_engine,
    )


class FakeOracleAdapter:
    """A deterministic oracle-adapter double. ``findings_spec`` is a list of
    ``(rule_id, node_id, from_core_engine, engine)`` tuples returned verbatim; the
    worker stamps provenance. For a non-mixed detector ``from_core_engine`` is
    ``None`` (the setter uses the engine); for a mixed detector it is per-finding,
    paired with a coherent per-finding ``engine``."""

    def __init__(self, findings_spec: list[tuple[str, int, bool | None, str]]) -> None:
        self._spec = findings_spec

    def run(self, detector: DetectorLike, cpg: CPG, job: WorkerJob) -> list[Finding]:
        return [
            _oracle_finding(rid, node, from_core_engine=fce, engine=eng)
            for rid, node, fce, eng in self._spec
        ]


def passthrough_oracle_adapter() -> OracleAdapter:
    """A non-mixed oracle adapter emitting two plain oracle findings."""
    return FakeOracleAdapter(
        [("oracle-rule-a", 0, None, "semgrep"), ("oracle-rule-b", 1, None, "semgrep")]
    )


def mixed_oracle_adapter() -> OracleAdapter:
    """A mixed-detector adapter: one IFDS-portion finding (from_core_engine=True,
    engine=ifds) and one CPG-query-portion finding (from_core_engine=False,
    engine=cpg-query), proving the result-set spans BOTH partitions with a
    coherent per-finding engine (AC-ORCH-03b, no blurring)."""
    return FakeOracleAdapter(
        [
            ("crypto-ifds-portion", 0, True, "ifds"),
            ("crypto-pattern-portion", 1, False, "cpg-query"),
        ]
    )


def mixed_oracle_adapter_missing_flag() -> OracleAdapter:
    """A BROKEN mixed adapter that omits ``from_core_engine`` (sets it None) on a
    mixed detector. The worker MUST raise InvariantViolation (fail-closed)."""
    return FakeOracleAdapter([("crypto-broken", 0, None, "cpg-query")])
