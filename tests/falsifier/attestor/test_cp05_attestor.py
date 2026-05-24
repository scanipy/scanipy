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

Spec-first TDD: CMP-CP-05 is not implemented yet, so this is a registered xfail/skip
stub mirroring `tests/unit/test_dsl_proofs.py`. It flips red→green when the Attestor
core pipeline lands.

Marker set is closed (`--strict-markers`). The release-blocker status lives in the
docstring `Hard gate?` field, not in a marker (`pre_release` gates execution to release
tags and would wrongly stop this from running on every CI run). The `invariant` marker
is required for discovery: `attestor.yml` (Gate 3) runs `pytest tests/ -m "invariant or
empirical"`, so a `falsifier`-only test would never be collected and Gate 3 would
silently disappear when CMP-CP-05 lands.
"""

import pytest


@pytest.mark.falsifier
@pytest.mark.invariant
@pytest.mark.xfail(
    reason="CMP-CP-05 (Determinism Attestor core pipeline) not yet implemented — spec stub",
    strict=False,
)
def test_cp05a_seeded_core_nondeterminism_fails_core_pipeline() -> None:
    """A deliberately introduced nondeterminism in the core path fails the core pipeline.

    Test id:      TST-AC-CP-05a
    Maps to AC:   AC-CP-05a (SDD §10 CMP-CP-05)
    Kind tag:     [FALSIFIER]
    Inputs:       A representative deterministic-core scan from the canary corpus, with a
                  deliberate nondeterminism seeded into the core path (e.g. non-canonical
                  map iteration order in CMP-FND-01, a clock-dependent value, or an
                  unordered set in a slice-fingerprint computation) per DOC-CMP-CP-05 §9.
    Outputs:      AttestationVerdict from attest_scan(scan_id, "core").
    Pass criteria: The seeded core-path nondeterminism MUST make the two independent
                  re-runs differ — result == "fail", diff_summary populated, and the CI
                  job exits non-zero so main-branch protection blocks merge. The
                  comparison is BYTE-IDENTICAL: the assertion must remain an exact byte
                  equality check (never a similarity/tolerance/rate). A clean
                  (unseeded) run of the same scan MUST instead yield result == "pass".
    Frequency:    every CI run
    Hard gate?:   yes — Gate 3 (Attestor; CLAUDE.md §15), release blocker. RULE-9 INV-3
                  component → Security Analyst sign-off on the implementing PR.
    """
    # TODO: when CMP-CP-05 is DONE —
    #   1. attest_scan(scan_id, "core") on a clean canary scan -> assert result == "pass".
    #   2. Seed a core-path nondeterminism source; re-attest -> assert result == "fail"
    #      with diff_summary populated and a non-zero exit.
    # Keep the comparison byte-exact. NEVER replace exact equality with a tolerance/rate.
    pytest.skip("CMP-CP-05 not implemented yet")
