"""Hermetic offline fakes for CMP-CP-05 (Determinism Attestor) specs.

No real AWS, no S3, no ORCH-01 scan API, no canary corpus. The Attestor's ``F``
re-run seam (the env/dependency-gated ``ScanRunner`` port, CLAR-PROC-01) is
supplied here as a deterministic in-memory double built from the REAL worker-F
path (``services.scan.worker.run_detector`` + ``emit_sarif``) over a synthetic
CPG and the real #288 injection spec — the SAME ``F`` mechanism ORCH-03's
``test_orch_03_end_to_end_byte_deterministic_sarif`` exercises.

Mirrors the established DI-fake convention (``tests/orch03_fakes.py``,
``tests/fnd03_fakes.py``): a single module that builds the synthetic inputs and
the injected ports so every spec test stays hermetic.

The two adversarial doubles are the falsifier's teeth:
  * :class:`SeededNondeterministicScanRunner` — a stateful F that perturbs ONE
    byte of the CORE Run on run 2. The REAL ``attest_scan(..., "core")`` MUST
    drive this to ``result="fail"`` (the AC-CP-05a self-test).
  * :class:`DroppingOracleScanRunner` — an oracle F that drops one of two oracle
    findings on run 2, yielding a MEASURED ``reproduction_rate == 0.5`` (the
    AC-CP-05b anti-vacuity fraction).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from analysis.sarif.canonical_emit import SARIFLog, SARIFRun
from services.scan.attestor import ScanRunner
from services.scan.worker import Finding, WorkerJob, emit_sarif, run_detector
from tests.orch03_fakes import (
    FakeOracleAdapter,
    core_injection_detector,
    deterministic_slice_fingerprinter,
    good_job,
    injection_taint_cpg,
    oracle_semgrep_detector,
)

_SCAN_ID = UUID(int=2)  # matches good_job().scan_id so the F is "the scan"


def deterministic_core_f() -> SARIFLog:
    """Run the REAL worker-F (run_detector + emit_sarif) over the synthetic CPG +
    the real #288 injection spec. This is ``F`` for the Attestor mechanism: a pure
    function of (CPG, spec, job) -> canonical two-Run SARIFLog. Deterministic by
    construction (CMP-FND-01 ``normalize`` is pure), so the core partition
    (``runs[0]``) is byte-identical across calls — exactly what the Attestor
    attests."""
    job = good_job()
    findings = run_detector(
        core_injection_detector(),
        injection_taint_cpg(),
        job,
        slice_fingerprinter=deterministic_slice_fingerprinter(),
    )
    return emit_sarif(findings, job)


def oracle_f(*, drop_second: bool) -> SARIFLog:
    """Run the worker-F for an ORACLE detector emitting two oracle findings. When
    ``drop_second`` is True only the first oracle finding is emitted (the run-2
    instability). Used to drive a MEASURED reproduction rate."""
    job = good_job(detector_id="semgrep-secrets")
    spec: list[tuple[str, int, bool | None, str]] = [("oracle-rule-a", 0, None, "semgrep")]
    if not drop_second:
        spec.append(("oracle-rule-b", 1, None, "semgrep"))
    findings = run_detector(
        oracle_semgrep_detector(),
        injection_taint_cpg(),
        job,
        oracle_adapter=FakeOracleAdapter(spec),
        slice_fingerprinter=deterministic_slice_fingerprinter(),
    )
    return emit_sarif(findings, job)


def mixed_partition_f(*, drop_oracle: bool) -> SARIFLog:
    """Worker-F emitting BOTH a CORE finding (the real #288 injection spec) and
    ORACLE findings over the SAME CPG, projected into ONE two-Run SARIFLog
    (``runs[0]`` core, ``runs[1]`` oracle). The CORE partition is IDENTICAL
    regardless of ``drop_oracle``; when ``drop_oracle`` is True one of the two
    oracle findings is dropped (an ORACLE-ONLY instability). This is the input that
    proves the two pipelines are SEPARATE: a core-stable + oracle-unstable F must
    attest the CORE partition as ``"pass"`` even though ``runs[1]`` differs.
    """
    job = good_job()
    slice_fp = deterministic_slice_fingerprinter()
    core_findings = run_detector(
        core_injection_detector(),
        injection_taint_cpg(),
        job,
        slice_fingerprinter=slice_fp,
    )
    oracle_spec: list[tuple[str, int, bool | None, str]] = [("oracle-rule-a", 0, None, "semgrep")]
    if not drop_oracle:
        oracle_spec.append(("oracle-rule-b", 1, None, "semgrep"))
    oracle_findings = run_detector(
        oracle_semgrep_detector(),
        injection_taint_cpg(),
        job,
        oracle_adapter=FakeOracleAdapter(oracle_spec),
        slice_fingerprinter=slice_fp,
    )
    # Emit BOTH partitions in one SARIFLog: FND-01 routes by origin into
    # runs[0] (core) / runs[1] (oracle). The core finding is byte-identical across
    # drop_oracle values; only the oracle Run changes.
    return emit_sarif(core_findings | oracle_findings, job)


# ---------------------------------------------------------------------------
# ScanRunner doubles (the injected F port)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeterministicScanRunner:
    """A faithful ``F``: the REAL worker-F, byte-identical across runs. Drives the
    core pipeline to ``result="pass"`` (the AC-CP-05a positive)."""

    def run(self, scan_id: UUID) -> SARIFLog:
        return deterministic_core_f()


class SeededNondeterministicScanRunner:
    """A deliberately NONDETERMINISTIC ``F`` (the seeded falsifier seam).

    Stateful call-counter (NOT clock-based — two calls in the same tick would be a
    flaky no-op): run 1 returns the faithful worker-F SARIF; run 2 returns the
    SAME SARIF with ONE byte of the CORE Run (``runs[0]``) perturbed. This models a
    real core-path nondeterminism source (non-canonical map iteration, an
    unordered set in a slice fingerprint, a clock-dependent value) WITHOUT
    weakening CMP-FND-01: the perturbation is injected at the F boundary, exactly
    where a determinism regression would surface in the attested SARIF.

    The REAL ``attest_scan(scan_id, "core")`` MUST drive this to ``result="fail"``.
    A broken attestor that re-uses run 1 for both comparands, or compares only a
    sarif_hash prefix positioned before the perturbation, would NOT catch it.
    """

    def __init__(self) -> None:
        self._calls = 0

    def run(self, scan_id: UUID) -> SARIFLog:
        self._calls += 1
        log = deterministic_core_f()
        if self._calls == 1:
            return log
        return _perturb_core_run(log)


class DroppingOracleScanRunner:
    """A NONDETERMINISTIC oracle ``F``: run 1 emits two oracle findings, run 2 drops
    one. The oracle pipeline measures ``reproduction_rate`` = 1 reproduced / 2 in
    run 1 = 0.5 (the AC-CP-05b anti-vacuity fraction). Result stays ``"rate-only"``."""

    def __init__(self) -> None:
        self._calls = 0

    def run(self, scan_id: UUID) -> SARIFLog:
        self._calls += 1
        return oracle_f(drop_second=self._calls != 1)


class CoreStableOracleUnstableScanRunner:
    """A mixed-partition ``F`` whose CORE Run is byte-IDENTICAL across runs while its
    ORACLE Run differs (run 2 drops one oracle finding).

    This is the SEPARATION discriminator (DOC-CMP-CP-05 §3.3 / DOC-PARTITION §6.3):
    an oracle-partition difference must NOT fail the CORE verdict. The REAL
    ``attest_scan(scan_id, "core")`` MUST return ``result="pass"`` here (it compares
    ``runs[0]`` only). A broken attestor that compares the whole two-Run log — or any
    blob that includes the oracle partition — would WRONGLY fail, so this test has
    power against that exact bug (the genuine core-only proof, not a fake artifact).
    Run on the SAME instance, ``attest_scan(scan_id, "oracle")`` measures the oracle
    drop as a rate of 0.5.
    """

    def __init__(self) -> None:
        self._calls = 0

    def run(self, scan_id: UUID) -> SARIFLog:
        self._calls += 1
        return mixed_partition_f(drop_oracle=self._calls != 1)


# ---------------------------------------------------------------------------
# Core-Run byte perturbation (the seeded nondeterminism)
# ---------------------------------------------------------------------------


def _perturb_core_run(log: SARIFLog) -> SARIFLog:
    """Return ``log`` with ONE byte of its CORE Run (``runs[0]``) flipped.

    Flips a byte in the core finding's message text — DEEP inside the canonical
    bytes, far past any fixed prefix, so a hash-prefix-only comparator could not
    dodge it. The oracle Run (``runs[1]``) is left untouched: the core verdict must
    fail on a CORE-partition difference regardless of the oracle partition.
    """
    core = log.runs[0]
    blob = bytearray(core.canonical_bytes)
    # Find the message text region and flip a byte there (a real detection-content
    # nondeterminism would land here). Fall back to the midpoint if the marker is
    # absent (keeps the perturbation deterministic and non-trivial).
    marker = b'"text":"'
    idx = blob.find(marker)
    pos = idx + len(marker) + 1 if idx != -1 else len(blob) // 2
    blob[pos] = blob[pos] ^ 0x20  # flip a bit -> a different, still-valid ASCII byte

    import hashlib

    perturbed = bytes(blob)
    new_core = SARIFRun(
        partition=core.partition,
        canonical_bytes=perturbed,
        sarif_hash=hashlib.sha256(perturbed).hexdigest(),
        result_count=core.result_count,
    )
    return SARIFLog(
        runs=(new_core, log.runs[1]),
        canonical_bytes=log.canonical_bytes,  # log-level bytes irrelevant to the core verdict
        sarif_hash=log.sarif_hash,
    )


def make_runner() -> ScanRunner:
    """A faithful deterministic ``F`` port (the positive control)."""
    return DeterministicScanRunner()


__all__ = [
    "CoreStableOracleUnstableScanRunner",
    "DeterministicScanRunner",
    "DroppingOracleScanRunner",
    "Finding",
    "SeededNondeterministicScanRunner",
    "WorkerJob",
    "deterministic_core_f",
    "make_runner",
    "mixed_partition_f",
    "oracle_f",
]
