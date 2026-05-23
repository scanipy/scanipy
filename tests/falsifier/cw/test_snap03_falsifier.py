"""Falsifier CW (Gate 2) — TST-AC-SNAP-03a (zero-FN) + TST-AC-SNAP-04a (seeded-FN).

Spec-first TDD: production code for CW-DETECT (CMP-SNAP-03) and the differential
reflection oracle (CMP-SNAP-04) does not exist yet, so both specs below are
registered-but-dormant stubs carrying ``@pytest.mark.xfail(strict=False)``; the
body calls ``pytest.skip`` until the owning CMP is DONE. Pattern mirrors
``tests/unit/test_dsl_proofs.py``.

These run via ``.github/workflows/falsifier-cw.yml``, which is gated behind
``tests/corpora/reflection/corpus.lock`` (a Phase-4 CMP-CORP-REFL-01 deliverable).
The lock file does not exist yet — that is expected: the spec exists now, the
gate arms when the corpus lands.

The pytest marker (``falsifier``) encodes EXECUTION only. The richer WBS kind
tag ``[FALSIFIER]`` lives in each docstring.

Covers (from WBS §4.2):
  - TST-AC-SNAP-03a  [FALSIFIER] — ZERO false negatives on the reflection corpus
                                   (release blocker; pass criterion: fn_rate == 0.0)
  - TST-AC-SNAP-04a  [FALSIFIER] — seeded CW-DETECT FN detected by the oracle;
                                   triggers exact re-partitioning
"""

import pytest


@pytest.mark.falsifier
@pytest.mark.xfail(
    reason="CMP-SNAP-03 (CW-DETECT) not yet implemented — Gate 2 falsifier stub",
    strict=False,
)
def test_snap_03a_zero_false_negatives_on_reflection_corpus() -> None:
    """Falsifier CW: ZERO false negatives on the curated reflection corpus.

    Test id:        TST-AC-SNAP-03a
    Maps to AC:     AC-SNAP-03a — "[Falsifier CW] Zero false negatives on the
                    curated reflection corpus (Spring dynamic proxies, Python
                    `__import__`/`getattr`, Ruby `send`/`method_missing`, PHP
                    variable functions, Java `Class.forName`, plus mutation-
                    injected reflection). A single false negative is a release
                    blocker."
    Kind tag:       [FALSIFIER]
    Inputs:         The curated reflection corpus CMP-CORP-REFL-01 (CLAR-CORP-01:
                    N ≥ 50 per category, ≥ 20 mutation-injected per language),
                    pinned by `tests/corpora/reflection/corpus.lock`. Every corpus
                    item carries a ground-truth label "contains reachable
                    reflection". CW-DETECT's verdict per item.
    Outputs:        `fn_rate` = (corpus-positive items that CW-DETECT verdicted
                    `closed-world`) / (total corpus-positive items).
    Pass criteria:  `assert fn_rate == 0.0` — a SINGLE false negative is a release
                    blocker. NEVER weaken to `< 0.5` or any tolerance. False
                    positives are permitted (they cost performance, not
                    correctness) and are NOT counted here.
    Frequency:      every CI run
    Hard gate?:     yes — Gate 2 (Falsifier CW), release blocker (CLAUDE.md §15).
    """
    # TODO: import CW-DETECT `detect` from the snapshotter module when CMP-SNAP-03
    #       is DONE, and load the corpus pinned by tests/corpora/reflection/
    #       corpus.lock (CMP-CORP-REFL-01, Phase 4).
    # false_negatives = 0
    # positives = load_reflection_corpus_positives()  # ground-truth: reflection present
    # for item in positives:
    #     verdict = detect(CwDetectRequest(item.path, item.languages)).verdict
    #     if verdict == "closed-world":
    #         false_negatives += 1
    # fn_rate = false_negatives / len(positives)
    # assert fn_rate == 0.0   # release blocker — never weaken
    pytest.skip("CMP-SNAP-03 not implemented yet")


@pytest.mark.falsifier
@pytest.mark.xfail(
    reason="CMP-SNAP-04 (Differential reflection oracle) not yet implemented",
    strict=False,
)
def test_snap_04a_seeded_fn_detected_triggers_exact_repartition() -> None:
    """Seeded CW-DETECT FN detected by oracle; triggers exact re-partitioning.

    Test id:        TST-AC-SNAP-04a
    Maps to AC:     AC-SNAP-04a — "A seeded `CW-DETECT` false negative is detected
                    by the oracle and triggers re-partitioning of exactly the
                    affected findings."
    Kind tag:       [FALSIFIER]
    Inputs:         A snapshot deliberately seeded so CW-DETECT returns
                    `closed-world` while reachable reflection is in fact present
                    (an injected FN). The snapshot has A affected findings
                    (engine ∈ {ifds, ide}, origin=deterministic-core) plus U
                    unaffected findings. The differential oracle (DOC-CMP-SNAP-04
                    §6.1) runs whole-program.
    Outputs:        Oracle verdict + the set of re-partitioned findings.
    Pass criteria:  (i) The oracle DISAGREES (oracle_verdict='not-closed-world',
                    snap_oracle_runs.agreed=false); (ii) EXACTLY the A affected
                    findings flip to `origin='oracle-passthrough'` — assert the
                    re-partitioned count equals A (not A-1, not A+1); (iii) the U
                    unaffected findings remain `deterministic-core`. The flip is
                    one-way and append-only.
    Frequency:      every CI run
    Hard gate?:     yes — falsifier gate for CMP-SNAP-04 (residual-risk bound).
    """
    # TODO: import the differential oracle + repartition flow from
    #       services/snapshot when CMP-SNAP-04 is DONE; seed an FN per
    #       DOC-CMP-SNAP-04 §9 (run end-to-end, assert exact-count re-partition).
    # run = oracle.evaluate(seeded_snapshot)
    # assert run.agreed is False
    # repartitioned = provenance.repartition_rows(seeded_snapshot.id)
    # assert len(repartitioned) == len(affected_findings)   # exactly the affected
    # for f in unaffected_findings:
    #     assert f.origin == "deterministic-core"            # untouched
    pytest.skip("CMP-SNAP-04 not implemented yet")
