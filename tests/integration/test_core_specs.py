"""CORE-family empirical (benchmark / rate) test specs (Phase 1, TDD).

Covers the [EMPIRICAL] acceptance criteria for the Analysis Core family:

    TST-AC-CORE-01b   recall >= Semgrep-default + 10pp at equal precision
    TST-AC-CORE-02c   weak-fallback rate < 5%; weak never auto-suppressed
    TST-AC-CORE-03b   budget-exhaustion rate on real code < 1%

These are corpus-backed, slower-running tests (real components, no mocking of
spec-required components). Production code does not exist yet, so each test is
a registered-but-dormant stub: `xfail(strict=False)` + a `pytest.skip` body
that flips red->green when the matching CMP-CORE-* lands. Marker =
execution/frequency class only; the WBS kind tag lives in the docstring.
"""

import pytest

# ---------------------------------------------------------------------------
# CMP-CORE-01 — Algorithm 2 value claim (per (class, language), INV-6 gated)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.xfail(reason="CMP-CORE-01 not yet implemented", strict=False)
def test_core_01b_recall_beats_semgrep_default_plus_10pp() -> None:
    """Recall >= Semgrep-default + 10pp at equal precision (gate-passing pairs).

    Test id:       TST-AC-CORE-01b
    Maps to AC:    AC-CORE-01b
    Kind tag:      [EMPIRICAL] (per stage; INV-6 gated)
    Inputs:        OWASP Benchmark + Juliet + held-out BigVul (CMP-CORP-VULN-01),
                   restricted to (class, language) pairs with CMP-CP-06 green.
    Outputs:       per-(class, language) recall + precision; Semgrep-default
                   baseline recall at the matched precision point.
    Pass criteria: for each gate-passing pair, at equal precision,
                   core recall >= Semgrep-default recall + 10 percentage points.
                   INV-6: front-end-blocked pairs are skipped with status
                   `front-end-blocked` and are NEVER counted as recall failures.
    Frequency:     pre-release (per stage).
    Hard gate?:    yes — per stage.
    """
    # TODO: read CMP-CP-06 gate-pass table; for each gate-passing pair compute
    #       core recall at equal precision vs Semgrep-default; assert >= +10pp.
    #       Skip non-passing pairs as front-end-blocked (never a failure).
    pytest.skip("CMP-CORE-01 not implemented yet")


# ---------------------------------------------------------------------------
# CMP-CORE-02 — weak-fallback rate + never-auto-suppress (Algorithm 3)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.xfail(reason="CMP-CORE-02 not yet implemented", strict=False)
def test_core_02c_weak_rate_under_5pct_and_never_suppressed() -> None:
    """weak-fallback rate measured < 5%; weak never auto-suppressed.

    Test id:       TST-AC-CORE-02c
    Maps to AC:    AC-CORE-02c
    Kind tag:      [EMPIRICAL] + [INVARIANT] (marker = invariant nature noted;
                   placed here as the corpus-backed empirical measurement —
                   the pure-invariant half is TST-INV-5-CORE-02 in the unit file)
    Inputs:        CMP-CORP-CANARY-01 (100 canary repos); slice fingerprints
                   computed under B = 2**16, T = 0.200 s (CLAR-PARAM-01).
    Outputs:       aggregate weak-fallback rate; baseline-lookup decisions
                   across seeded refactors.
    Pass criteria: (i) measured weak-fallback rate < 5% (CLAR-PARAM-03 RESOLVED
                   publish/alarm threshold — do NOT weaken);
                   (ii) no weak-classed finding is auto-suppressed across a
                   refactor by the CMP-FND-01 baseline policy.
    Frequency:     nightly (corpus-scale measurement).
    Hard gate?:    yes.
    """
    # TODO: run compute_slice_fingerprint over CMP-CORP-CANARY-01; assert
    #       weak_count / total < 0.05 and no weak prior is suppressed on refactor.
    pytest.skip("CMP-CORE-02 not implemented yet")


# ---------------------------------------------------------------------------
# CMP-CORE-03 — budget-exhaustion rate on real code (Algorithm 5)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.xfail(reason="CMP-CORE-03 not yet implemented", strict=False)
def test_core_03b_budget_exhaustion_rate_under_1pct() -> None:
    """Budget-exhaustion rate on real code measured < 1%.

    Test id:       TST-AC-CORE-03b
    Maps to AC:    AC-CORE-03b
    Kind tag:      [EMPIRICAL]
    Inputs:        CMP-CORP-CANARY-01 (100 canary repos); canonical_order run
                   with B = 2**16, T = 0.200 s (CLAR-PARAM-01 RESOLVED).
    Outputs:       count of CanonicalOrderResult.budget_exhausted == True over
                   total invocations.
    Pass criteria: budget-exhaustion rate < 1% (exhausted / total < 0.01).
                   Do NOT weaken the threshold.
    Frequency:     nightly (corpus-scale measurement).
    Hard gate?:    yes.
    """
    # TODO: run analysis.ordering.canonical_order over every CPG in
    #       CMP-CORP-CANARY-01; assert exhausted_count / total < 0.01.
    pytest.skip("CMP-CORE-03 not implemented yet")
