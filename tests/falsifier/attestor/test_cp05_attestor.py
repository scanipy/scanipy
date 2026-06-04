"""Gate 3 falsifier: Attestor core-pipeline nondeterminism must FAIL — TST-AC-CP-05a.

This is the priority falsifier for CMP-CP-05. The core pipeline is the empirical
falsifier of property (a): for fixed (S_version, env_digest, LLM_TRIAGE=off), two
independent re-runs of F over the same source must produce BYTE-IDENTICAL SARIF over
the `origin=deterministic-core` partition (DOC-PARTITION §6.1; DOC-CMP-CP-05 §3.1).

A deliberately introduced source of nondeterminism in the core path (non-canonical map
iteration, clock-dependent value, unordered set in a slice fingerprint, …) MUST cause
the core pipeline to FAIL (result="fail", diff_summary populated, CI exits non-zero).
A falsifier that passes under seeded nondeterminism is a broken falsifier — NEVER weaken
the byte-identical criterion to a tolerance or a rate.

HERMETIC SURFACE (CLAR-PROC-01). The CANARY-01 corpus does not exist, so this is the
hermetic synthetic-F half of TST-AC-CP-05a: the F re-run port is injected (a
deterministic worker-F over a synthetic CPG + the real #288 spec, the SAME F path
ORCH-03's `test_orch_03_end_to_end_byte_deterministic_sarif` exercises). The
corpus-scale leg (TST-AC-CP-05c byte-identical at canary scale + the determinism-canary
job) stays gated on CMP-CORP-CANARY-01.

Marker set is closed (`--strict-markers`). The release-blocker status lives in the
docstring `Hard gate?` field, not in a marker (`pre_release` gates execution to release
tags and would wrongly stop this from running on every CI run). The `invariant` marker
is required for discovery: `attestor.yml` (Gate 3) runs `pytest tests/ -m "invariant or
empirical"`, so a `falsifier`-only test would never be collected and Gate 3 would
silently disappear when CMP-CP-05 lands.
"""

import pytest

from services.scan.attestor import AttestationVerdict, attest_scan
from tests.cp05_fakes import (
    CoreStableOracleUnstableScanRunner,
    SeededNondeterministicScanRunner,
    make_runner,
)

# good_job().scan_id — the synthetic F is "the scan" the Attestor re-runs.
_SCAN_ID = __import__("uuid").UUID(int=2)
_S_VERSION = "1.4.2"
_ENV_DIGEST = "sha256:" + "a" * 64


@pytest.mark.falsifier
@pytest.mark.invariant
def test_cp05a_seeded_core_nondeterminism_fails_core_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deliberately introduced nondeterminism in the core path fails the core pipeline.

    Test id:      TST-AC-CP-05a
    Maps to AC:   AC-CP-05a (SDD §10 CMP-CP-05)
    Kind tag:     [FALSIFIER]
    Inputs:       A representative deterministic-core scan (hermetic synthetic-F over the
                  synthetic CPG + real #288 spec), with a deliberate nondeterminism seeded
                  into the F boundary (one byte of the CORE Run perturbed on run 2 — the
                  in-test analogue of a non-canonical map iteration / clock-dependent
                  value / unordered slice-fingerprint set per DOC-CMP-CP-05 §9).
    Outputs:      AttestationVerdict from attest_scan(scan_id, "core").
    Pass criteria: The seeded core-path nondeterminism MUST make the two independent
                  re-runs differ — result == "fail", diff_summary populated. The
                  comparison is BYTE-IDENTICAL: an EXACT byte equality check (never a
                  similarity/tolerance/rate). A clean (unseeded) run of the same scan
                  MUST instead yield result == "pass" (anti-vacuity positive).
    Frequency:    every CI run
    Hard gate?:   yes — Gate 3 (Attestor; CLAUDE.md §15), release blocker. RULE-9 INV-3
                  component → Security Analyst sign-off on the implementing PR.

    NEGATIVE CONTROL (mutation-verified, documented in the implementing PR): a broken
    attestor that (a) compares run 1 to itself (skips the second F run) or (b) compares
    only a sarif_hash *prefix* positioned before the perturbation would NOT catch the
    seeded byte and would WRONGLY return "pass" here — so this assertion has power. The
    real `attest_scan` runs F twice and byte-compares the full core Run.
    """
    # INV-3: the core pipeline runs under LLM_TRIAGE=off (Gate-3 pins it; pin here too so
    # the falsifier is hermetic regardless of the ambient env).
    monkeypatch.setenv("LLM_TRIAGE", "off")

    # ---- ANTI-VACUITY POSITIVE: a faithful F yields result == "pass". --------
    clean = attest_scan(
        _SCAN_ID,
        "core",
        s_version=_S_VERSION,
        env_digest=_ENV_DIGEST,
        scan_runner=make_runner(),
    )
    assert isinstance(clean, AttestationVerdict)
    assert clean.result == "pass", "a faithful deterministic F must attest result == 'pass'"
    assert clean.diff_summary is None
    assert clean.reproduction_rate is None  # NULL on the core partition (DOC §3.4)

    # ---- SELF-TEST (the falsifier's teeth): seeded nondeterminism -> "fail". --
    seeded = attest_scan(
        _SCAN_ID,
        "core",
        s_version=_S_VERSION,
        env_digest=_ENV_DIGEST,
        scan_runner=SeededNondeterministicScanRunner(),
    )
    assert seeded.result == "fail", (
        "seeded core-path nondeterminism MUST fail the core pipeline (property (a) "
        "falsified); a 'pass' here means the byte-compare was weakened or the second "
        "F run was skipped"
    )
    assert seeded.diff_summary is not None and "byte difference" in seeded.diff_summary, (
        "a core fail MUST populate diff_summary with the first-differing-offset incident "
        "artifact (DOC-CMP-CP-05 §6)"
    )

    # The verdict carries the INV-2 versioned params and a non-empty attestor_hash.
    assert seeded.s_version == _S_VERSION and seeded.env_digest == _ENV_DIGEST
    assert seeded.attestor_hash and isinstance(seeded.attestor_hash, bytes)


@pytest.mark.falsifier
@pytest.mark.invariant
def test_cp05a_core_compare_is_byte_exact_not_a_rate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Discriminating guard: the core verdict is byte-EXACT, never a tolerance/rate.

    Test id:      TST-AC-CP-05a (byte-exactness limb)
    Kind tag:     [FALSIFIER/INVARIANT]
    Pass criteria: ONE perturbed byte in the core Run is sufficient to flip the verdict
                  from "pass" to "fail" — proving the comparator does not tolerate a
                  "close enough" / high-similarity SARIF. A rate-based core comparator
                  (e.g. 99.99% byte agreement → "pass") would WRONGLY pass and fail this.
    """
    monkeypatch.setenv("LLM_TRIAGE", "off")
    runner = SeededNondeterministicScanRunner()
    # The two F runs differ by exactly one byte; the core pipeline must still FAIL.
    verdict = attest_scan(
        _SCAN_ID,
        "core",
        s_version=_S_VERSION,
        env_digest=_ENV_DIGEST,
        scan_runner=runner,
    )
    assert verdict.result == "fail", (
        "a single-byte core difference MUST fail the core pipeline — the comparator is "
        "exact byte equality, never a similarity/tolerance/rate"
    )


@pytest.mark.falsifier
@pytest.mark.invariant
def test_cp05a_oracle_instability_does_not_fail_core_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The two pipelines are SEPARATE: an oracle-partition difference must NOT fail
    the core verdict (DOC-CMP-CP-05 §3.3 / DOC-PARTITION §6.3).

    Test id:      TST-AC-CP-05a (partition-separation limb)
    Kind tag:     [FALSIFIER/INVARIANT]
    Inputs:       A mixed-partition synthetic F whose CORE Run (``runs[0]``) is
                  byte-IDENTICAL across runs (a real #288 core finding) while its
                  ORACLE Run (``runs[1]``) differs (run 2 drops one oracle finding).
    Outputs:      attest_scan(scan_id, "core") and attest_scan(scan_id, "oracle") over
                  the SAME F instance.
    Pass criteria: The CORE verdict is "pass" DESPITE the oracle partition differing —
                  proving the core pipeline byte-compares ``runs[0]`` ONLY and never
                  asserts (nor is corrupted by) anything over the oracle partition. The
                  ORACLE verdict on the same instance is "rate-only" with the measured
                  oracle drop (rate 0.5).
    Frequency:    every CI run
    Hard gate?:   yes — Gate 3 (Attestor; the core/oracle separation is NORMATIVE).

    THIS IS THE GENUINE CORE-ONLY PROOF (not the byte-perturbation artifact): a broken
    attestor that compares the whole two-Run ``SARIFLog.canonical_bytes`` — or any blob
    spanning the oracle partition — would WRONGLY return "fail" here, because a real
    oracle instability makes the whole log differ. The real ``attest_scan`` returns
    "pass" because it isolates ``runs[0]``. (Mutation-verified in the implementing PR:
    swapping the core compare to the whole-log bytes flips this to "fail".)
    """
    from decimal import Decimal

    monkeypatch.setenv("LLM_TRIAGE", "off")

    # CORE: stable across runs -> "pass", even though the oracle partition differs.
    # A FRESH runner per attest call: the stateful run-1/run-2 counter must start at 0
    # for each pipeline (a shared instance would make the oracle pipeline see two
    # already-dropped runs and read rate 1.0, masking the drop).
    core = attest_scan(
        _SCAN_ID,
        "core",
        s_version=_S_VERSION,
        env_digest=_ENV_DIGEST,
        scan_runner=CoreStableOracleUnstableScanRunner(),
    )
    assert isinstance(core, AttestationVerdict)
    assert core.result == "pass", (
        "an ORACLE-partition difference must NOT fail the CORE verdict — the core "
        "pipeline compares runs[0] (core) ONLY (DOC-CMP-CP-05 §3.3). A 'fail' here means "
        "the comparator spans the oracle partition (whole-log compare bug)."
    )
    assert core.diff_summary is None
    # Anti-vacuity: the core partition genuinely carried a real finding (not empty).
    assert core.attestor_hash and isinstance(core.attestor_hash, bytes)

    # ORACLE: a fresh runner measures the oracle drop as a rate (1 reproduced / 2).
    oracle = attest_scan(
        _SCAN_ID,
        "oracle",
        s_version=_S_VERSION,
        env_digest=_ENV_DIGEST,
        scan_runner=CoreStableOracleUnstableScanRunner(),
    )
    assert oracle.result == "rate-only", "oracle verdict is rate-only, never pass/fail"
    assert oracle.reproduction_rate == Decimal("0.5000"), (
        "the oracle instability (1 of 2 dropped) must measure rate 0.5 — confirming the "
        "oracle Run genuinely differed (so the core 'pass' above is non-vacuous)"
    )
