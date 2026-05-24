"""Integrity tests for the vuln corpus (CMP-CORP-VULN-01).

Covers the load-bearing contracts of DOC-CMP-CORP-VULN-01:
  - §3.2 BigVul training-exclusion: held-out ∩ training-eligible == ∅ (HARD blocker).
  - §3.2 deterministic split: re-deriving the split reproduces the same digests.
  - AC-CORP-VULN-01a: OWASP + Juliet slices exist with ground-truth CWE tags; the
    held-out lock + training_exclusion_proof.md exist.
  - AC-CORP-VULN-01b: every populated slice carries class+language+cwe; positives carry
    ground_truth_sites, clean variants do not.
  - The bigvul held-out item's row_id is in the held-out set, not training-eligible.
  - corpus.lock digest is stable (no drift) via build_lock --check semantics.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

PIPELINE_DIR = Path(__file__).resolve().parent
CORPUS_ROOT = PIPELINE_DIR.parent
sys.path.insert(0, str(PIPELINE_DIR))

import bigvul_split as bvs  # noqa: E402
import build_lock as bl  # noqa: E402


def _load(p: Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def test_bigvul_split_disjoint_and_deterministic():
    rows = bvs.load_rows_from_csv(CORPUS_ROOT / "bigvul_heldout" / "data" / "bigvul_sample.csv")
    r1 = bvs.split_rows(rows)
    r1.assert_disjoint()  # HARD release blocker if it raises
    r2 = bvs.split_rows(rows)
    assert r1.heldout_digest == r2.heldout_digest
    assert r1.training_digest == r2.training_digest
    assert set(r1.heldout_ids).isdisjoint(set(r1.training_ids))
    assert len(r1.heldout_ids) + len(r1.training_ids) == len(rows)


def test_heldout_split_lock_matches_recomputed():
    split_lock = _load(CORPUS_ROOT / "bigvul_heldout" / "heldout_split.lock")
    rows = bvs.load_rows_from_csv(CORPUS_ROOT / "bigvul_heldout" / "data" / "bigvul_sample.csv")
    res = bvs.split_rows(rows)
    assert split_lock["heldout_digest"] == res.heldout_digest
    assert split_lock["training_eligible_digest"] == res.training_digest
    assert sorted(split_lock["heldout_row_ids"]) == sorted(res.heldout_ids)


def test_required_artifacts_exist():
    assert (CORPUS_ROOT / "corpus.lock").exists()
    assert (CORPUS_ROOT / "bigvul_heldout" / "heldout_split.lock").exists()
    assert (CORPUS_ROOT / "bigvul_heldout" / "training_exclusion_proof.md").exists()
    assert (CORPUS_ROOT / "annotation-methodology.md").exists()


def test_owasp_and_juliet_slices_present_with_cwe():
    lock = _load(CORPUS_ROOT / "corpus.lock")
    sources = {s["source"] for s in lock["slices"]}
    assert "owasp_benchmark" in sources
    assert "juliet" in sources
    for s in lock["slices"]:
        for item in s["items"]:
            assert item["cwe_ids"], f"{item['slice_id']} missing cwe_ids"
            assert item["class"] and item["language"]


def test_positive_items_have_sites_clean_items_do_not():
    lock = _load(CORPUS_ROOT / "corpus.lock")
    for s in lock["slices"]:
        for item in s["items"]:
            if item["positive"] is True:
                assert item["ground_truth_sites"], f"{item['slice_id']} positive w/o sites"
            else:
                assert not item["ground_truth_sites"], f"{item['slice_id']} clean w/ sites"


def test_bigvul_heldout_item_is_in_heldout_set_not_training():
    man = _load(
        CORPUS_ROOT
        / "bigvul_heldout"
        / "slices"
        / "ssrf"
        / "python"
        / "bigvul-ssrf-python-heldout-001"
        / "manifest.yaml"
    )
    row_id = man["bigvul_row_id"]
    split_lock = _load(CORPUS_ROOT / "bigvul_heldout" / "heldout_split.lock")
    assert row_id in split_lock["heldout_row_ids"], "held-out item not in held-out set"
    # And it must NOT be in the training-eligible complement.
    rows = bvs.load_rows_from_csv(CORPUS_ROOT / "bigvul_heldout" / "data" / "bigvul_sample.csv")
    res = bvs.split_rows(rows)
    assert row_id not in set(res.training_ids), "held-out item leaked into training set"


def test_no_vendored_item_uses_off_allowlist_license():
    lock = _load(CORPUS_ROOT / "corpus.lock")
    for s in lock["slices"]:
        for item in s["items"]:
            if item.get("vendored"):
                assert item["license"] in bl.VENDOR_LICENSE_ALLOWLIST, (
                    f"{item['slice_id']} vendored with off-allow-list license {item['license']!r}"
                )


def test_corpus_lock_digest_stable():
    existing = _load(CORPUS_ROOT / "corpus.lock")
    recomputed = bl.canonical_digest({**existing, "corpus_digest": "sha256:PENDING"})
    assert existing["corpus_digest"] == recomputed, "corpus.lock digest drift"
