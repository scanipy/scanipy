"""Falsifier CW (Gate 2) — TST-AC-SNAP-03a (zero-FN) + TST-AC-SNAP-04a (seeded-FN).

CW-DETECT (CMP-SNAP-03) is now implemented, so ``TST-AC-SNAP-03a`` runs a live
harness against the curated reflection corpus. The corpus itself is the
CMP-CORP-REFL-01 deliverable (``tests/corpora/reflection/``), built by a separate
agent and NOT committed by this PR. When its ``corpus.lock`` is absent or yields
no materialized positives, ``TST-AC-SNAP-03a`` skips cleanly — the Gate-2 zero-FN
assertion arms once CMP-CORP-REFL-01 lands on ``main`` (it runs via
``.github/workflows/falsifier-cw.yml``, gated on ``corpus.lock``).

``TST-AC-SNAP-04a`` remains a dormant stub until CMP-SNAP-04 (the differential
reflection oracle) is implemented. Pattern mirrors ``tests/unit/test_dsl_proofs.py``.

The pytest marker (``falsifier``) encodes EXECUTION only. The richer WBS kind
tag ``[FALSIFIER]`` lives in each docstring.

Covers (from WBS §4.2):
  - TST-AC-SNAP-03a  [FALSIFIER] — ZERO false negatives on the reflection corpus
                                   (release blocker; pass criterion: fn_rate == 0.0)
  - TST-AC-SNAP-04a  [FALSIFIER] — seeded CW-DETECT FN detected by the oracle;
                                   triggers exact re-partitioning
"""

from dataclasses import dataclass
from pathlib import Path

import pytest

# Path the corpus agent (CMP-CORP-REFL-01) pins. This tree is NOT committed by
# this PR — it is the corpus agent's deliverable. The falsifier arms whenever a
# parseable corpus.lock with materialized positives is present (locally in a
# shared worktree now; in CI once CMP-CORP-REFL-01 lands on main).
_REFLECTION_CORPUS_DIR = Path(__file__).resolve().parents[2] / "corpora" / "reflection"
_CORPUS_LOCK = _REFLECTION_CORPUS_DIR / "corpus.lock"
_CATEGORIES_DIR = _REFLECTION_CORPUS_DIR / "categories"


@dataclass(frozen=True)
class _CorpusPositive:
    """A ground-truth `not-closed-world` corpus item resolved to its source dir."""

    item_id: str
    source_root: Path  # the per-item `source/` directory CW-DETECT scans
    language: str


def _load_reflection_corpus_positives() -> list[_CorpusPositive]:
    """Load corpus-positive items (ground-truth: reachable reflection present).

    ``corpus.lock`` is the YAML manifest produced by CMP-CORP-REFL-01
    (``pipeline/build_lock.py``). Schema: ``body.categories[].items[]``; an item
    with ``label == "not-closed-world"`` is a positive. Each item's source lives
    at ``categories/<category.name>/<item.id>/<item.path_in_source>`` and
    CW-DETECT is pointed at that item's ``source/`` directory. The category
    carries the ``language``.

    We do NOT fabricate corpus data: if the lock is absent or unparseable, the
    caller skips (the corpus has not landed yet). A parseable lock that yields
    zero positives is also a skip (never a vacuous pass).
    """
    import yaml

    manifest = yaml.safe_load(_CORPUS_LOCK.read_text(encoding="utf-8"))
    body = manifest.get("body", manifest) if isinstance(manifest, dict) else {}
    categories = body.get("categories", []) if isinstance(body, dict) else []

    positives: list[_CorpusPositive] = []
    for category in categories:
        language = str(category.get("language", ""))
        cat_name = str(category.get("name") or category.get("kind") or "")
        for item in category.get("items", []):
            if item.get("label") != "not-closed-world":
                continue
            item_id = str(item.get("id", ""))
            path_in_source = str(item.get("path_in_source", ""))
            item_dir = _CATEGORIES_DIR / cat_name / item_id
            # Point CW-DETECT at the item's `source/` directory (the analysis
            # scope), derived from the first path segment of path_in_source.
            source_root = item_dir / Path(path_in_source).parts[0]
            positives.append(
                _CorpusPositive(item_id=item_id, source_root=source_root, language=language)
            )
    return positives


@pytest.mark.falsifier
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
    Frequency:      nightly + pre-release (Gate 2 runs via falsifier-cw.yml on
                    schedule + release tags + workflow_dispatch — NOT on PR pushes
                    to main). A PR-introduced CW-DETECT regression is caught the
                    following night, not at merge time.
    Hard gate?:     yes — Gate 2 (Falsifier CW), release blocker (CLAUDE.md §15).
    """
    # CW-DETECT (CMP-SNAP-03) is implemented; the harness is live. The corpus
    # itself (CMP-CORP-REFL-01) lands separately — if its lock is not present in
    # this checkout, skip cleanly rather than fabricate corpus data or block.
    # Gate 2 (falsifier-cw.yml) arms the assertion once the corpus is merged.
    if not _CORPUS_LOCK.is_file():
        pytest.skip(
            "reflection corpus.lock absent — CMP-CORP-REFL-01 not yet merged; "
            "zero-FN gate (TST-AC-SNAP-03a) arms when the corpus lands"
        )

    from services.snapshot import CwDetectRequest, detect

    try:
        positives = _load_reflection_corpus_positives()
    except Exception as exc:  # corpus.lock present but unparseable ⇒ not yet landed
        pytest.skip(f"reflection corpus.lock present but unparseable ({exc}) — REFL-01 pending")

    if not positives:
        pytest.skip(
            "reflection corpus.lock present but yields no positive items — "
            "REFL-01 corpus not yet populated (never a vacuous pass)"
        )

    # Only validate against items whose source is actually materialized on disk.
    # A missing source dir fails closed to `degraded` (the safe direction), which
    # would VACUOUSLY pass without exercising the detector on real content — that
    # is not evidence of zero FN. We assert on materialized items only; the full
    # mutation-injected corpus is validated when REFL-01 fully materializes in CI.
    materialized = [p for p in positives if p.source_root.is_dir()]
    if not materialized:
        pytest.skip(
            "reflection corpus.lock present but no positive item has materialized "
            "source on disk — REFL-01 sources not yet checked out (no vacuous pass)"
        )

    _fixed_clock = "2026-01-01T00:00:00+00:00"
    false_negatives: list[str] = []
    for pos in materialized:
        verdict = detect(
            CwDetectRequest(
                source_tree_root=str(pos.source_root),
                language_mix=(pos.language,) if pos.language else (),
            ),
            clock=lambda: _fixed_clock,
        ).verdict
        if verdict == "closed-world":
            false_negatives.append(pos.item_id)

    fn_rate = len(false_negatives) / len(materialized)
    # Release blocker — a SINGLE false negative fails. NEVER weaken this.
    assert fn_rate == 0.0, f"CW-DETECT false negatives (release blocker): {false_negatives}"


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
    Frequency:      nightly + pre-release (runs via falsifier-cw.yml — schedule +
                    release tags + workflow_dispatch; NOT on PR pushes to main).
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
