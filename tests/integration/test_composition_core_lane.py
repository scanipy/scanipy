"""End-to-end composition test for the assembled deterministic-core lane.

This is the FIRST test that runs the wired-together core lane with ZERO fakes on
the fingerprint path:

    CMP-CORE-01 solver  (analysis.ifds.solver.solve)
      -> CMP-CORE-02 slice fingerprint  (analysis.fingerprint.compute_slice_fingerprint)
        -> CMP-ORCH-03 worker  (services.scan.worker.run_detector + emit_sarif)
          -> CMP-FND-01 canonical SARIF  (analysis.sarif.canonical_emit.normalize)
            -> CMP-CP-05 Attestor  (services.scan.attestor.attest_scan)

The honesty property under test: ``run_detector`` is called with PRODUCTION
DEFAULTS — NO ``slice_fingerprinter`` injected. Before the CORE-02->ORCH-03
wiring, that raised ``NotImplementedError`` (the fail-closed build-ahead seam);
now every core finding is fingerprinted by the REAL ``compute_slice_fingerprint``
upstream in ``_findings_from_core``, so the fail-closed default never fires. A
test that injected a fake fingerprinter here would pass vacuously without ever
touching real CORE-02 — which is exactly the failure mode this test exists to
prevent (see ``tests/cp05_fakes.deterministic_core_f``, which DOES inject one;
this runner deliberately does NOT).

The fixture is the real #288 Stage-A injection spec over a small synthetic
strong-strong CPG (``injection_taint_cpg`` — verified to drive CORE-02's strong
content-hash path, ``fingerprint_class == "strong"``, NOT the weak fallback).

Marker: ``@pytest.mark.integration`` so CI's integration job
(``pytest tests/integration/ -m integration``, ci.yml) actually collects it.

CLAR boundaries honoured:
  * CLAR-PROC-01 (composition of build-ahead parts) — this is exactly that
    composition, now that CORE-02 has landed.
  * CLAR-ORCH-03 (per-finding CORE-02 vs run-level CORE-03 ``fingerprint_class``
    sourcing — OPEN) — this test asserts NOTHING about ``fingerprint_class``
    SOURCING semantics; it only checks the worker field is a valid non-empty
    enum value. Asserting where it came from would unilaterally resolve the CLAR.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from analysis.fingerprint import compute_slice_fingerprint
from analysis.ifds.solver import solve
from analysis.ordering import CPG_ORDER_HASH_ANNOTATION, Sha256
from analysis.sarif.canonical_emit import SARIFLog
from services.scan.attestor import AttestationVerdict, attest_scan
from services.scan.worker import (
    Finding,
    WorkerJob,
    emit_sarif,
    run_detector,
)
from tests.orch03_fakes import (
    core_injection_detector,
    good_job,
    injection_taint_cpg,
)

_SHA256_PREFIX = "sha256:"


def _env_digest_bytes(job: WorkerJob) -> Sha256:
    """The 32 raw bytes CMP-CORE-01 ``solve`` wants, parsed from the job's
    ``"sha256:"``-prefixed hex — mirrors ``worker._env_digest_bytes`` so the direct
    solver call reproduces ``_findings_from_core`` faithfully. (The witness, and
    hence the fingerprint, is actually independent of ``env_digest`` /
    ``S_version`` — matching them is for fidelity to the worker, not correctness.)
    """
    return Sha256(bytes.fromhex(job.env_digest[len(_SHA256_PREFIX) :]))


def _run_real_core_lane(job: WorkerJob) -> SARIFLog:
    """The composition runner: run the REAL worker-F over the synthetic CPG + the
    real #288 injection spec with PRODUCTION DEFAULTS (no injected ports), then
    project through the real CMP-FND-01 emitter. This is ``F`` for the Attestor.

    Deliberately a fresh local runner (NOT ``cp05_fakes.deterministic_core_f``,
    which injects a fake fingerprinter): the whole point is that the core lane
    fingerprints itself via real CORE-02.
    """
    findings = run_detector(core_injection_detector(), injection_taint_cpg(), job)
    return emit_sarif(findings, job)


@pytest.mark.integration
def test_composition_core_lane_real_fingerprint_through_attestor() -> None:
    """The assembled core lane fingerprints, emits, and attests with no fakes on
    the fingerprint path.

    Pass criteria:
      1. A production-default ``run_detector`` (NO injected fingerprinter) emits
         >= 1 finding.
      2. Each finding's ``slice_fingerprint`` is 64-hex.
      3. It EQUALS an independent ``compute_slice_fingerprint`` recompute over the
         real solver finding for the same witness (proves the worker used real
         CORE-02, not a constant/projection), and that recompute is ``strong``
         (proves the strong content-hash path, not the weak fallback).
      4. The four required provenance fields + the INV-5 annotation literal are
         present on every finding.
      5. Two independent ``run_detector`` + ``emit_sarif`` executions are
         byte-identical (the determinism property CMP-CP-05 attests).
      6. The REAL CMP-CP-05 CORE pipeline (``LLM_TRIAGE=off``) returns
         ``result == "pass"`` (byte-identical core SARIF across two fresh F runs).
    """
    cpg = injection_taint_cpg()
    detector = core_injection_detector()
    job = good_job()
    assert detector.spec is not None  # the real #288 core spec is present

    # (1)/(2) Production defaults — NO slice_fingerprinter injected.
    findings = run_detector(detector, cpg, job)
    assert findings, "anti-vacuity: the assembled core lane must emit a finding"

    # (3) Independent recompute over the REAL solver finding (mirrors
    # _findings_from_core: same CPG instance, same spec, same pinned parameters).
    solver_result = solve(
        cpg,
        detector.spec,
        S_version=job.S_version,
        env_digest=_env_digest_bytes(job),
    )
    assert len(solver_result.findings) == len(findings)
    assert len(findings) == 1, "the synthetic fixture is single-finding by design"

    solver_finding = next(iter(solver_result.findings))
    recompute = compute_slice_fingerprint(solver_finding, cpg)
    # The strong content-hash path was exercised (NOT the weak witness-edge
    # fallback): equality below is a true canonical-slice identity, not a
    # same-source-only weak hash.
    assert recompute.fingerprint_class == "strong"
    expected_hex = recompute.slice_fingerprint.hex()

    worker_finding = next(iter(findings))
    # 64-hex (2) + EQUALS the independent recompute (3): the worker threaded the
    # REAL CORE-02 fingerprint, not a constant or the location projection.
    assert len(worker_finding.slice_fingerprint) == 64
    assert all(c in "0123456789abcdef" for c in worker_finding.slice_fingerprint)
    assert worker_finding.slice_fingerprint == expected_hex

    # (4) Four required provenance fields (RULE-6) + the INV-5 annotation literal.
    _assert_provenance_threaded(worker_finding)

    # (5) Byte-deterministic SARIF across two independent run_detector+emit runs.
    log_a = _run_real_core_lane(job)
    log_b = _run_real_core_lane(job)
    assert log_a.canonical_bytes == log_b.canonical_bytes
    assert log_a.runs[0].canonical_bytes == log_b.runs[0].canonical_bytes  # core Run
    # Anti-vacuity for (5): the SARIF actually carries the real fingerprint.
    assert expected_hex.encode("utf-8") in log_a.runs[0].canonical_bytes

    # (6) Drive the REAL CMP-CP-05 attestor over the real core lane as F. The core
    # pipeline requires LLM_TRIAGE=off (INV-3); set it explicitly for CI-robustness
    # (without monkeypatch, to keep the env change local and restored).
    verdict = _attest_core_lane(job)
    assert verdict.result == "pass"
    assert verdict.partition == "core"
    assert verdict.reproduction_rate is None  # core partition never reports a rate


def _assert_provenance_threaded(finding: Finding) -> None:
    """The four required provenance fields (INV-1/INV-2/INV-5) + the INV-5
    annotation literal are present. ``fingerprint_class`` is checked only for
    valid-enum membership — NOT its sourcing (CLAR-ORCH-03 is OPEN)."""
    # INV-1: origin in the two-value partition (never None, never "mixed").
    assert finding.origin == "deterministic-core"
    assert finding.determinism_partition == finding.origin
    # INV-2: versioned parameters threaded verbatim from the job.
    assert finding.S_version == "1.4.2"
    assert finding.env_digest.startswith(_SHA256_PREFIX)
    # INV-5: cpg_order_hash + its conditional-canonicality annotation literal.
    assert len(finding.cpg_order_hash) == 64
    assert finding.cpg_order_hash_annotation == CPG_ORDER_HASH_ANNOTATION
    assert finding.cpg_order_hash_annotation == "canonical iff fingerprint_class = strong"
    # fingerprint_class: valid non-empty enum only (NOT its source — CLAR-ORCH-03).
    assert finding.fingerprint_class in ("strong", "weak")


def _attest_core_lane(job: WorkerJob) -> AttestationVerdict:
    """Run the real CMP-CP-05 CORE pipeline with the real core lane as the
    injected ``ScanRunner`` F-port, under ``LLM_TRIAGE=off``."""
    import os

    class _RealCoreLaneRunner:
        def run(self, scan_id: UUID) -> SARIFLog:
            return _run_real_core_lane(job)

    prior = os.environ.get("LLM_TRIAGE")
    os.environ["LLM_TRIAGE"] = "off"  # INV-3 backstop the attestor pins off
    try:
        return attest_scan(
            job.scan_id,
            "core",
            s_version=job.S_version,
            env_digest=job.env_digest,
            scan_runner=_RealCoreLaneRunner(),
        )
    finally:
        if prior is None:
            os.environ.pop("LLM_TRIAGE", None)
        else:
            os.environ["LLM_TRIAGE"] = prior


@pytest.mark.integration
def test_composition_negative_control_distinct_s_version_distinct_bytes() -> None:
    """Negative control (guards the byte-comparator against vacuity): a second job
    with a DIFFERENT ``S_version`` produces DIFFERENT SARIF bytes.

    ``S_version`` is emitted into the SARIF run metadata, so changing it MUST move
    the canonical bytes — if it did not, the byte-identity assertion in the main
    test would be vacuous (a comparator that always reports "equal"). The
    ``slice_fingerprint`` itself is ``S_version``-independent (it is a function of
    CPG + spec), so this control proves the SARIF-level comparator bites, NOT the
    fingerprint recompute.
    """
    log_default = _run_real_core_lane(good_job())
    log_other = _run_real_core_lane(good_job(S_version="9.9.9"))
    assert log_default.canonical_bytes != log_other.canonical_bytes
    assert log_default.runs[0].canonical_bytes != log_other.runs[0].canonical_bytes
