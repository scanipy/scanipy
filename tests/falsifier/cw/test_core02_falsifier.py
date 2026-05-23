"""CMP-CORE-02 slice-fingerprint falsifiers (Phase 1, TDD).

Refactor-stability falsifiers for Algorithm 3 (CMP-CORE-02):

    TST-AC-CORE-02a   fingerprint INVARIANT under each named refactor
    TST-AC-CORE-02b   fingerprint CHANGES on a genuine fix + aliasing-changing
                      extract

These run via .github/workflows/falsifier-cw.yml, gated behind a corpus.lock
(CMP-CORP-REFAC-01, Phase 4) — being skip/xfail until that corpus and the
implementation land is expected. Production code does not exist yet, so each
test is a registered-but-dormant stub: `xfail(strict=False)` + a `pytest.skip`
body. Marker = execution/frequency class (`falsifier`); the WBS kind tag lives
in the docstring.
"""

import pytest


@pytest.mark.falsifier
@pytest.mark.xfail(reason="CMP-CORE-02 not yet implemented", strict=False)
def test_core_02a_fingerprint_invariant_under_named_refactors() -> None:
    """Fingerprint invariant under each named refactor on 50 seeded findings.

    Test id:       TST-AC-CORE-02a
    Maps to AC:    AC-CORE-02a
    Kind tag:      [FALSIFIER]
    Inputs:        CMP-CORP-REFAC-01 — 50 seeded findings, each paired with a
                   refactored variant that exercises one of the five named
                   normalisation passes (alpha-rename, PDG-only formatting,
                   canonical topo-sort reorder, pure extract/inline, FQN/file-move).
    Outputs:       slice_fingerprint for the original and the refactored variant.
    Pass criteria: for every seeded pair, slice_fingerprint(original) ==
                   slice_fingerprint(refactored). Any mismatch falsifies the
                   refactor-invariance claim for that named pass.
    Frequency:     every CI run (falsifier-cw.yml; corpus-gated Phase 4).
    Hard gate?:    yes.
    """
    # TODO: load CMP-CORP-REFAC-01; for each pair assert
    #       compute_slice_fingerprint(orig) == compute_slice_fingerprint(refac).
    pytest.skip("CMP-CORE-02 not implemented yet")


@pytest.mark.falsifier
@pytest.mark.xfail(reason="CMP-CORE-02 not yet implemented", strict=False)
def test_core_02b_fingerprint_changes_on_fix_and_aliasing_extract() -> None:
    """Fingerprint changes on a genuine fix and on an aliasing-changing extract.

    Test id:       TST-AC-CORE-02b
    Maps to AC:    AC-CORE-02b
    Kind tag:      [FALSIFIER]
    Inputs:        two adversarial seeds — (1) a genuine fix that removes the
                   sink, (2) an impure extract that changes alias relationships
                   / side-effect order.
    Outputs:       slice_fingerprint before and after each transformation.
    Pass criteria: BOTH transformations flip the fingerprint:
                   slice_fingerprint(before) != slice_fingerprint(after) for the
                   genuine fix AND for the aliasing-changing extract. A
                   fingerprint that stays equal across a real fix would
                   wrongly auto-suppress a still-valid (or newly-changed)
                   finding — that is the failure this falsifier guards against.
    Frequency:     every CI run (falsifier-cw.yml; corpus-gated Phase 4).
    Hard gate?:    yes.
    """
    # TODO: assert fingerprint differs across the genuine fix and across the
    #       impure/aliasing-changing extract (pass 4 must NOT normalise it).
    pytest.skip("CMP-CORE-02 not implemented yet")
