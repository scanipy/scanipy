"""Pipeline self-tests for CMP-CORP-REFAC-01 (provisional, corpus-agent authored).

These guard the build pipeline's reproducibility + ground-truth contract. The
canonical TST-AC-CORP-REFAC-01a/b specs are QA-owned and [FORTHCOMING]; these are
the corpus-side smoke tests so a pipeline regression is caught immediately, and
they encode the AC-CORP-REFAC-01a inventory assertions directly.

  - test_refactor_application_deterministic  -> deterministic transforms
  - test_inventory_counts                     -> AC-CORP-REFAC-01a (50 x 7 == 350)
  - test_label_set_and_methodology_agreement  -> labels in {should-stay, should-flip}
  - test_should_flip_changes_source           -> AC-CORE-02b basis (after != before)
  - test_stage_a_class_language_only          -> only Stage-A classes/langs seeded
  - test_lock_digest_stable                   -> versioned + digest-pinned, no drift
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PIPE = Path(__file__).resolve().parent
sys.path.insert(0, str(_PIPE))
sys.path.insert(0, str(_PIPE.parent))

import build_corpus  # noqa: E402
import refactor_transforms as rt  # noqa: E402
from bases import render  # noqa: E402


@pytest.mark.unit
def test_refactor_application_deterministic() -> None:
    """Same (base, refactor) -> byte-identical output (no RNG, no clock)."""
    for idx in range(8):  # one of each base topology
        base = render(idx)
        for refactor in rt.REFACTORS:
            a = rt.apply_refactor(base, refactor)
            b = rt.apply_refactor(base, refactor)
            assert a.source == b.source
            assert a.ground_truth_label == rt.GROUND_TRUTH[refactor]


@pytest.mark.unit
def test_inventory_counts() -> None:
    """AC-CORP-REFAC-01a: pair_count == 50 * 7 == 350; 5/2 stay/flip split."""
    lock = build_corpus._load_yaml(build_corpus.LOCK_PATH)
    assert lock["seed_count"] == 50
    assert lock["refactor_count"] == 7
    assert lock["pair_count"] == 350
    assert lock["label_distribution"]["should-stay"] == 50 * 5
    assert lock["label_distribution"]["should-flip"] == 50 * 2


@pytest.mark.unit
def test_label_set_and_methodology_agreement() -> None:
    """Every pair's label is in {should-stay, should-flip} and matches taxonomy."""
    lock = build_corpus._load_yaml(build_corpus.LOCK_PATH)
    taxonomy = lock["refactor_taxonomy"]
    for seed in lock["seeds"]:
        for pair in seed["refactor_pairs"]:
            assert pair["ground_truth_label"] in {"should-stay", "should-flip"}
            assert pair["ground_truth_label"] == taxonomy[pair["refactor"]]


@pytest.mark.unit
def test_should_flip_changes_source() -> None:
    """AC-CORE-02b basis: every should-flip pair's after/ differs from before/."""
    lock = build_corpus._load_yaml(build_corpus.LOCK_PATH)
    for seed in lock["seeds"]:
        before = seed["before_sha256"]
        for pair in seed["refactor_pairs"]:
            if pair["ground_truth_label"] == "should-flip":
                assert pair["after_sha256"] != before, (
                    f"{seed['seed_id']}/{pair['refactor']}: should-flip but identical"
                )


@pytest.mark.unit
def test_stage_a_class_language_only() -> None:
    """Only Stage-A core classes + Stage-A languages are seeded (staging rule)."""
    lock = build_corpus._load_yaml(build_corpus.LOCK_PATH)
    for seed in lock["seeds"]:
        assert seed["class"] in build_corpus.STAGE_A_CLASSES
        assert seed["language"] in build_corpus.STAGE_A_LANGUAGES


@pytest.mark.unit
def test_lock_digest_stable() -> None:
    """Rebuilding the lock content yields the same digest (reproducible)."""
    lock1, hard1, _ = build_corpus.assemble_lock()
    lock2, hard2, _ = build_corpus.assemble_lock()
    assert hard1 == [] and hard2 == []
    assert build_corpus.canonical_digest(lock1) == build_corpus.canonical_digest(lock2)


@pytest.mark.unit
def test_lock_on_disk_matches_recompute() -> None:
    """The committed corpus.lock digest matches a fresh recompute (no drift)."""
    existing = build_corpus._load_yaml(build_corpus.LOCK_PATH)
    recomputed = build_corpus.canonical_digest(
        {**existing, "corpus_digest": "sha256:PENDING"}
    )
    assert existing["corpus_digest"] == recomputed
    assert existing["corpus_version"]  # versioned
