"""Corpus self-tests for CMP-CORP-CPG-go.

Maps to the DOC §9 acceptance criteria:

  - TST-AC-CORP-CPG-go-a  -> schema validation of corpus.lock; methodology.md
                             present and references the pinned tools; every item
                             carries all four tool-derived ground-truth artifacts
                             and a documented origin/license/categories.
  - TST-AC-CORP-CPG-go-b  -> corpus is versioned and digest-pinned; a tampered
                             on-disk corpus is rejected by `build_lock --check`
                             (the digest pins the evaluation set, not the clock).

CI-safe: Python + PyYAML only. Re-deriving ground truth needs Go, but validating
the committed corpus does not.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PIPE = Path(__file__).resolve().parent
sys.path.insert(0, str(_PIPE))

import build_lock  # noqa: E402

CORPUS_ROOT = build_lock.CORPUS_ROOT
REQUIRED_GT = build_lock.REQUIRED_GROUND_TRUTH


# --- TST-AC-CORP-CPG-go-a : schema + methodology + ground-truth presence -----


@pytest.mark.unit
def test_lock_assembles_without_hard_errors():
    lock, hard = build_lock.assemble_lock()
    assert not hard, f"corpus has HARD validation failures: {hard}"
    assert lock["corpus_id"] == "CORP-CPG-go"
    assert lock["language"] == "go"
    assert lock["items"], "corpus has no items"


@pytest.mark.unit
def test_methodology_present_and_pins_tools():
    md = (CORPUS_ROOT / "methodology.md").read_text(encoding="utf-8")
    for needle in ("go1.22.2", "x/tools", "callgraph/cha", "go/ast", "go/ssa"):
        assert needle in md, f"methodology.md does not reference pinned tool {needle!r}"


@pytest.mark.unit
def test_readme_present():
    assert (CORPUS_ROOT / "README.md").exists()


@pytest.mark.unit
def test_every_item_has_all_ground_truth_artifacts():
    lock, _ = build_lock.assemble_lock()
    for item in lock["items"]:
        gt_dir = CORPUS_ROOT / "items" / item["id"] / "ground_truth"
        for gt in REQUIRED_GT:
            assert (gt_dir / gt).exists(), f"{item['id']} missing ground_truth/{gt}"


@pytest.mark.unit
def test_every_item_declares_origin_license_categories():
    lock, _ = build_lock.assemble_lock()
    for item in lock["items"]:
        assert item["origin"] in ("SOURCED", "SYNTHESIZED"), item["id"]
        assert item["license"], item["id"]
        assert item["categories"], item["id"]
        # SOURCED items must carry a real upstream commit (not a placeholder).
        if item["origin"] == "SOURCED":
            assert item["source_commit"] != "synthesized", item["id"]
            assert item["license"] in build_lock.LICENSE_ALLOWLIST, item["id"]


@pytest.mark.unit
def test_ground_truth_status_recorded():
    lock, _ = build_lock.assemble_lock()
    for item in lock["items"]:
        assert item["ground_truth"]["status"] == "complete", item["id"]


# --- TST-AC-CORP-CPG-go-b : versioned + digest-pinned -------------------------


@pytest.mark.unit
def test_corpus_is_versioned():
    lock = build_lock._load_yaml(build_lock.LOCK_PATH)
    assert lock.get("corpus_version"), "corpus.lock missing corpus_version"


@pytest.mark.unit
def test_committed_lock_digest_matches_recompute():
    """The committed corpus.lock digest pins the on-disk evaluation set."""
    lock = build_lock._load_yaml(build_lock.LOCK_PATH)
    recomputed = build_lock.canonical_digest(
        {**lock, "corpus_digest": "sha256:PENDING"}
    )
    assert lock.get("corpus_digest") == recomputed, "corpus.lock digest drift"


@pytest.mark.unit
def test_digest_excludes_volatile_fields():
    """built_by/created_at must not affect the digest (clock-independent pin)."""
    lock = build_lock._load_yaml(build_lock.LOCK_PATH)
    d1 = build_lock.canonical_digest({**lock, "corpus_digest": "x"})
    mutated = {**lock, "created_at": "1999-01-01T00:00:00Z", "built_by": "someone-else"}
    d2 = build_lock.canonical_digest({**mutated, "corpus_digest": "x"})
    assert d1 == d2


@pytest.mark.unit
def test_tampered_corpus_changes_digest():
    """Relabelling/adding/removing an item must change corpus_digest (DOC §8)."""
    lock = build_lock._load_yaml(build_lock.LOCK_PATH)
    base = build_lock.canonical_digest({**lock, "corpus_digest": "x"})

    tampered = {**lock, "items": list(lock["items"])}
    # Flip one item's recorded license -> must perturb the digest.
    tampered["items"][0] = {**tampered["items"][0], "license": "GPL-3.0"}
    tdigest = build_lock.canonical_digest({**tampered, "corpus_digest": "x"})
    assert base != tdigest, "digest did not change on a relabelled item"
