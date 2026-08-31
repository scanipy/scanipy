"""Unit specs for the Semgrep oracle ``ScanRunner`` adapter (Tier-2 Track C).

These specs prove the WHOLE Track-C chain end to end, minus the binary:

    canned Semgrep JSON
      -> injected SemgrepInvoker (call-counting, so run 2 can differ)
        -> SemgrepOracleScanRunner  (map -> canonical_emit.normalize)
          -> the REAL services.scan.attestor.attest_scan(partition="oracle")

Nothing here needs the ``semgrep`` binary: the subprocess call is isolated behind
the :class:`SemgrepInvoker` port, and every spec injects a fake. The Attestor
itself is NEVER faked — the verdicts below come from the real ``attest_scan``.

THE LOAD-BEARING ASSERTION is that ``result == "rate-only"`` in BOTH the stable
and the unstable case. A rate of exactly 1.0000 over the oracle partition is a
MEASURED number, never property (a): if a future refactor ever let a perfectly
reproducing Semgrep run report ``"pass"``, that would be the determinism theorem
claimed over ``oracle-passthrough`` findings, and
``test_oracle_stable_run_is_rate_only_never_a_theorem_claim`` fails.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from analysis.ordering import CPG, canonical_order
from services.scan.attestor import AttestationVerdict
from services.scan.oracle_attestor import (
    ORACLE_FINGERPRINT_CLASS,
    OracleProvenanceUnavailable,
    OracleScanProvenance,
    SemgrepInvocationError,
    SemgrepOracleScanRunner,
    SubprocessSemgrepInvoker,
    attest_oracle_scan,
    map_semgrep_report,
)

pytestmark = pytest.mark.unit

SCAN_ID = UUID(int=7)
SOURCE_DIR = Path("/srv/checkout")


# ---------------------------------------------------------------------------
# Fixtures — canned Semgrep output + the caller-supplied provenance bundle
# ---------------------------------------------------------------------------


def _semgrep_result(check_id: str, path: str, line: int, severity: str = "ERROR") -> dict:
    """One entry shaped like a real ``semgrep --json`` ``results[]`` element."""
    return {
        "check_id": check_id,
        "path": path,
        "start": {"line": line, "col": 5},
        "end": {"line": line, "col": 40},
        "extra": {
            "message": f"{check_id} matched",
            "severity": severity,
            "metadata": {"cwe": "CWE-89", "category": "security"},
        },
    }


def _report(*results: dict) -> dict:
    return {"version": "1.90.0", "results": list(results), "errors": [], "paths": {"scanned": []}}


TWO_FINDINGS = _report(
    _semgrep_result("python-sql-injection-fstring-execute", "/srv/checkout/app/db.py", 42),
    _semgrep_result("python-dangerous-eval-exec", "/srv/checkout/app/util.py", 17, "WARNING"),
)
ONE_FINDING = _report(
    _semgrep_result("python-sql-injection-fstring-execute", "/srv/checkout/app/db.py", 42),
)


def _fixture_cpg_order_hash() -> str:
    """A REAL CMP-CORE-03 ``canonical_order`` digest over a tiny synthetic CPG.

    This is a TEST FIXTURE value, the same pattern ``tests/cp05_fakes.py`` uses:
    the CPG is synthetic and does not correspond to the (equally fictional)
    checkout these specs scan. It is computed rather than hard-coded precisely so
    that no literal in this file can be mistaken for a fabricated INV-5 hash — on
    a real deployment this value comes from ``canonical_order`` over the CPG of
    the very same commit.
    """
    cpg = CPG()
    src = cpg.add_node("CALL", operator_or_literal="request.args.get")
    sink = cpg.add_node("CALL", operator_or_literal="cursor.execute")
    cpg.add_edge(src, sink, "DDG")
    return canonical_order(cpg).cpg_order_hash.hex()


def _provenance(**overrides: object) -> OracleScanProvenance:
    """The caller-supplied provenance bundle.

    Every value here is INJECTED, exactly as the adapter demands: nothing in this
    bundle is derivable from a Semgrep run. ``precondition_status`` in particular
    is a fixture value standing in for a CMP-SNAP-03 CW-DETECT verdict, which
    never runs on a Semgrep-only scan — it is not "what an oracle scan is".
    """
    base: dict[str, object] = {
        "snapshot_id": UUID(int=11),
        "codebase_id": UUID(int=12),
        "commit_sha": "a" * 40,
        "S_version": "1.4.0",
        "env_digest": "sha256:" + "b" * 64,
        "cpg_order_hash": _fixture_cpg_order_hash(),
        "precondition_status": "full-reparse",
        "rule_classes": {
            "python-sql-injection-fstring-execute": "injection",
            "python-dangerous-eval-exec": "injection",
        },
        "llm_triage_flag": False,
    }
    base.update(overrides)
    return OracleScanProvenance(**base)  # type: ignore[arg-type]


class SequenceInvoker:
    """A call-counting :class:`SemgrepInvoker` fake: run N returns payload N.

    Modelled on ``tests/cp05_fakes.DroppingOracleScanRunner`` — stateful by call
    count, never clock-based (two calls in the same tick would make a
    clock-driven fake a flaky no-op). The last payload repeats if the Attestor
    ever calls more than twice.
    """

    def __init__(self, *payloads: dict) -> None:
        self._payloads = payloads
        self.calls = 0

    def invoke(self, source_dir: Path) -> object:
        self.calls += 1
        return self._payloads[min(self.calls, len(self._payloads)) - 1]


def _runner(invoker: SequenceInvoker, **prov: object) -> SemgrepOracleScanRunner:
    return SemgrepOracleScanRunner(
        source_dir=SOURCE_DIR,
        provenance=_provenance(**prov),
        invoker=invoker,
    )


# ---------------------------------------------------------------------------
# The two rate specs — the Track-C demonstrandum
# ---------------------------------------------------------------------------


def test_oracle_stable_run_is_rate_only_never_a_theorem_claim() -> None:
    """A PERFECTLY reproducing oracle scan: rate 1.0000, verdict still "rate-only".

    Inputs:   two identical Semgrep reports (2 findings each) through the real
              map -> normalize -> attest_scan(partition="oracle") chain.
    Expected: reproduction_rate == 1.0000 AND result == "rate-only".

    This is the anti-fake assertion of the whole track. Rate 1.0 is the exact
    case where it is tempting to promote an oracle result to a determinism
    "pass"; ``.claude/rules/05-determinism.md`` forbids it ("the oracle pipeline
    must NEVER claim the determinism theorem"). A byte-identical claim over
    Semgrep output would be a lie about which partition the theorem covers.
    """
    invoker = SequenceInvoker(TWO_FINDINGS, TWO_FINDINGS)
    verdict: AttestationVerdict = attest_oracle_scan(SCAN_ID, _runner(invoker))

    assert verdict.result == "rate-only"
    assert verdict.result not in ("pass", "fail")
    assert verdict.reproduction_rate == Decimal("1.0000")
    assert verdict.partition == "oracle"
    # ``diff_summary`` is the CORE pipeline's byte-difference incident artifact.
    # It must be absent on the oracle partition: there is no byte-identity claim
    # here to have an incident about.
    assert verdict.diff_summary is None
    # Two FRESH invocations — a cached second run would manufacture rate 1.0.
    assert invoker.calls == 2


def test_oracle_unstable_run_measures_a_real_fraction() -> None:
    """An UNSTABLE oracle scan: run 2 loses one of two findings -> rate 0.5000.

    Inputs:   run 1 reports 2 findings, run 2 reports only the first.
    Expected: reproduction_rate == Decimal("0.5") AND result == "rate-only".

    The anti-vacuity half of the pair: it proves the rate is genuinely MEASURED
    over the emitted SARIF Results rather than being a constant. A rate that
    cannot move off 1.0 would make the stable-case assertion above worthless.
    """
    invoker = SequenceInvoker(TWO_FINDINGS, ONE_FINDING)
    verdict = attest_oracle_scan(SCAN_ID, _runner(invoker))

    assert verdict.result == "rate-only"
    assert verdict.reproduction_rate == Decimal("0.5000")
    assert verdict.reproduction_rate is not None
    assert verdict.reproduction_rate < Decimal("1")
    assert verdict.diff_summary is None
    # A degraded rate is NOT a failure verdict on the oracle partition: the
    # pipeline reports the number and never hard-fails on it.
    assert verdict.result != "fail"


def test_oracle_verdict_never_produced_by_the_core_pipeline() -> None:
    """``attest_oracle_scan`` pins ``partition="oracle"`` — no core-path escape.

    There is no argument a caller can pass to route Semgrep output through the
    byte-identical core pipeline, so no ``"pass"``/``"fail"`` determinism verdict
    can ever be minted over ``oracle-passthrough`` findings. Also asserts the
    verdict's INV-2 fields are the ones stamped on the attested findings.
    """
    prov = _provenance()
    invoker = SequenceInvoker(TWO_FINDINGS, TWO_FINDINGS)
    verdict = attest_oracle_scan(SCAN_ID, _runner(invoker))

    assert verdict.partition == "oracle"
    assert verdict.s_version == prov.S_version
    assert verdict.env_digest == prov.env_digest
    # The core Run of an oracle-only scan is EMPTY: this adapter never emits a
    # deterministic-core finding, so there is nothing for the core pipeline to
    # attest even if someone pointed it here.
    log = _runner(SequenceInvoker(TWO_FINDINGS)).run(SCAN_ID)
    assert log.runs[0].partition == "core"
    assert log.runs[0].result_count == 0
    assert log.runs[1].partition == "oracle"
    assert log.runs[1].result_count == 2


# ---------------------------------------------------------------------------
# Mapping specs — INV-1 / INV-5 stamping over real Semgrep output shape
# ---------------------------------------------------------------------------


def test_every_mapped_finding_is_oracle_partitioned_and_weak() -> None:
    """INV-1 + INV-5: origin/engine/fingerprint_class on every Semgrep match.

    ``fingerprint_class`` is pinned ``weak`` and NOT threaded from any
    ``canonical_order`` result: a Semgrep content id is not a canonical-CPG
    claim, so stamping ``strong`` would be a false INV-5 canonicality assertion.
    """
    findings = map_semgrep_report(TWO_FINDINGS, source_dir=SOURCE_DIR, provenance=_provenance())

    assert len(findings) == 2
    for f in findings:
        assert f.origin == "oracle-passthrough"
        assert f.determinism_partition == "oracle-passthrough"
        assert f.engine == "semgrep"
        assert f.fingerprint_class == ORACLE_FINGERPRINT_CLASS == "weak"
        assert f.fingerprint_class != "strong"
        # INV-2 threaded verbatim, never re-derived in the mapper.
        assert f.S_version == "1.4.0"
        assert f.env_digest == "sha256:" + "b" * 64
        # Paths are relative to the checkout root: an absolute host path would
        # vary per machine and be read as instability that is not Semgrep's.
        assert not f.uri.startswith("/")


def test_mapping_is_pure_and_path_relative() -> None:
    """The projection is a pure function of the report — no run-to-run drift.

    If the mapper itself were nondeterministic, the measured reproduction rate
    would be reporting the adapter's own noise as Semgrep's.
    """
    first = map_semgrep_report(TWO_FINDINGS, source_dir=SOURCE_DIR, provenance=_provenance())
    second = map_semgrep_report(TWO_FINDINGS, source_dir=SOURCE_DIR, provenance=_provenance())

    assert {f.slice_fingerprint for f in first} == {f.slice_fingerprint for f in second}
    assert sorted(f.uri for f in first) == ["app/db.py", "app/util.py"]


# ---------------------------------------------------------------------------
# Fail-closed specs — the blocking integration constraint
# ---------------------------------------------------------------------------


def test_missing_cpg_order_hash_fails_closed_with_the_named_producer() -> None:
    """No CPG => no ``cpg_order_hash`` => refuse to emit. Never a fabricated hash.

    CMP-FND-01 requires ``cpg_order_hash`` NOT NULL on EVERY finding, oracle
    included, but a Semgrep-only scan builds no CPG. The adapter names
    CMP-CORE-03 as the sole legitimate producer and stops, rather than hashing
    the source tree into something that would read as a canonical-order digest.
    """
    for bad in ("", "not-a-hash", "A" * 64, "0" * 63):
        with pytest.raises(OracleProvenanceUnavailable, match="cpg_order_hash"):
            _provenance(cpg_order_hash=bad)


def test_missing_precondition_status_fails_closed() -> None:
    """CW-DETECT (CMP-SNAP-03) never runs on a Semgrep scan; no default is invented."""
    with pytest.raises(OracleProvenanceUnavailable, match="precondition_status"):
        _provenance(precondition_status="unknown")


def test_unmapped_rule_class_fails_closed() -> None:
    """Oracle ``class_`` sourcing is the OPEN CLAR-ORCH-03 — never guessed."""
    prov = _provenance(rule_classes={})
    with pytest.raises(OracleProvenanceUnavailable, match="CLAR-ORCH-03"):
        map_semgrep_report(TWO_FINDINGS, source_dir=SOURCE_DIR, provenance=prov)


def test_blank_inv2_provenance_fails_closed() -> None:
    """INV-2: ``S_version`` / ``env_digest`` / ``commit_sha`` may never be blank."""
    for field in ("S_version", "env_digest", "commit_sha"):
        with pytest.raises(OracleProvenanceUnavailable, match=field):
            _provenance(**{field: ""})


# ---------------------------------------------------------------------------
# Semgrep invocation specs — exit codes and genuine crashes
# ---------------------------------------------------------------------------


class _FakeCompleted:
    def __init__(self, returncode: int, stdout: bytes, stderr: bytes = b"") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _invoker_with(monkeypatch: pytest.MonkeyPatch, completed: _FakeCompleted) -> object:
    """A ``SubprocessSemgrepInvoker`` whose subprocess call is stubbed out."""
    monkeypatch.setattr(
        "services.scan.oracle_attestor.subprocess.run",
        lambda *a, **k: completed,
    )
    return SubprocessSemgrepInvoker(rules_dir=Path("/app/deploy/rules"), semgrep_bin="/usr/bin/sg")


@pytest.mark.parametrize("returncode", [0, 1])
def test_findings_exit_code_is_not_a_failure(
    monkeypatch: pytest.MonkeyPatch, returncode: int
) -> None:
    """Semgrep exits 1 when it FINDS something — a success, not a crash.

    Treating exit 1 as failure would make every scan that detects a real
    vulnerability look like a broken tool, and would silently zero out the
    attested finding set.
    """
    invoker = _invoker_with(monkeypatch, _FakeCompleted(returncode, b'{"results": []}'))
    assert invoker.invoke(SOURCE_DIR) == {"results": []}  # type: ignore[attr-defined]


def test_genuine_crash_surfaces_as_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exit >= 2 with parseable output is a scan error, and must not pass silently."""
    invoker = _invoker_with(monkeypatch, _FakeCompleted(2, b'{"results": []}', b"fatal: boom"))
    with pytest.raises(SemgrepInvocationError, match="exited 2"):
        invoker.invoke(SOURCE_DIR)  # type: ignore[attr-defined]


def test_unparseable_output_surfaces_as_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unparseable stdout is a crash; the stderr tail is preserved for diagnosis.

    Swallowing this as "zero findings" would report a rate over an empty set —
    a vacuous 1.0000 that looks like perfect reproduction.
    """
    invoker = _invoker_with(monkeypatch, _FakeCompleted(0, b"Traceback...", b"MemoryError"))
    with pytest.raises(SemgrepInvocationError, match="no parseable JSON"):
        invoker.invoke(SOURCE_DIR)  # type: ignore[attr-defined]


def test_unrecognised_severity_fails_closed() -> None:
    """An unexpected severity is unexpected OUTPUT, never a silent 'medium'."""
    bad = _report(_semgrep_result("python-dangerous-eval-exec", "/srv/checkout/a.py", 1, "NOPE"))
    with pytest.raises(SemgrepInvocationError, match="severity"):
        map_semgrep_report(bad, source_dir=SOURCE_DIR, provenance=_provenance())


def test_missing_binary_fails_closed() -> None:
    """No partial-path or shell fallback when the binary is absent."""
    with pytest.raises(SemgrepInvocationError, match="not found on PATH"):
        SubprocessSemgrepInvoker.create(
            Path("/app/deploy/rules"), semgrep_bin="definitely-not-a-real-binary"
        )
