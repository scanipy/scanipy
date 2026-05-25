"""Pipeline self-tests for CMP-CORP-REFL-01 (provisional, corpus-agent authored).

These guard the build pipeline's reproducibility contract. The canonical
TST-AC-CORP-REFL-01a/b/c specs are QA-owned and [FORTHCOMING]; these are the
corpus-side smoke tests so a pipeline regression is caught immediately.

  - test_injection_byte_identical      -> AC-CORP-REFL-01b (deterministic injection)
  - test_injected_site_is_accurate     -> ground-truth line accuracy (zero-FN basis)
  - test_lock_digest_stable            -> AC-CORP-REFL-01c (versioned + digest-pinned)
  - test_every_mutation_lang_has_min   -> CLAR-CORP-01 (>= 20 mutation-injected / lang)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PIPE = Path(__file__).resolve().parent
sys.path.insert(0, str(_PIPE))

import build_lock  # noqa: E402
import inject_reflection as inj  # noqa: E402

_BASES = {
    "java": "java/Calculator.java",
    "python": "python/calculator.py",
    "ruby": "ruby/calculator.rb",
    "php": "php/Calculator.php",
    "js": "js/calculator.js",
    "go": "go/calculator.go",
}


def _base_src(lang: str) -> str:
    return (build_lock.CLEAN_BASES_DIR / _BASES[lang]).read_text(encoding="utf-8")


@pytest.mark.unit
@pytest.mark.parametrize("lang", sorted(_BASES))
def test_injection_byte_identical(lang: str) -> None:
    """AC-CORP-REFL-01b: same (input_sha, seed, recipe) -> byte-identical output."""
    src = _base_src(lang)
    for recipe in inj.recipes_for(lang):
        a = inj.inject(src, lang, 0, recipe)
        b = inj.inject(src, lang, 0, recipe)
        assert a == b


@pytest.mark.unit
@pytest.mark.parametrize("lang", sorted(_BASES))
def test_injected_site_is_accurate(lang: str) -> None:
    """The recorded expected_site line actually contains the reflection construct,
    and the post-injection label is not-closed-world (INV-4 safe direction)."""
    src = _base_src(lang)
    for recipe in inj.recipes_for(lang):
        res = inj.inject(src, lang, 0, recipe)
        assert res.label == "not-closed-world"
        line = res.source.splitlines()[res.line - 1]
        # the first snippet line must be present at the recorded site
        first = inj._RECIPES[(lang, recipe)]["snippet"][0]  # type: ignore[index]
        assert first.strip() in line


@pytest.mark.unit
def test_lock_digest_stable() -> None:
    """AC-CORP-REFL-01c: rebuilding the lock content yields the same digest."""
    lock1, hard1, _ = build_lock.assemble_lock()
    lock2, hard2, _ = build_lock.assemble_lock()
    assert hard1 == [] and hard2 == []
    assert build_lock.canonical_digest(lock1) == build_lock.canonical_digest(lock2)


@pytest.mark.unit
def test_lock_on_disk_matches_recompute() -> None:
    """The committed corpus.lock digest matches a fresh recompute (no drift)."""
    existing = build_lock._load_yaml(build_lock.LOCK_PATH)
    recomputed = build_lock.canonical_digest(
        {**existing, "corpus_digest": "sha256:PENDING"}
    )
    assert existing["corpus_digest"] == recomputed
    assert existing["corpus_version"]  # versioned (AC-CORP-REFL-01c)


@pytest.mark.unit
def test_every_mutation_lang_has_min() -> None:
    """CLAR-CORP-01: each per-language mutation-injected category has >= 20 items."""
    lock = build_lock._load_yaml(build_lock.LOCK_PATH)
    by_name = {c["name"]: c for c in lock["categories"]}
    for lang in _BASES:
        # v0.1.1: category name uses a slash so the Gate-2 falsifier's pathlib
        # join resolves to categories/mutation-injected/<lang>/ on disk.
        cat = by_name[f"mutation-injected/{lang}"]
        assert cat["sample_size"] >= 20, f"{lang}: {cat['sample_size']} < 20"
        for item in cat["items"]:
            assert item["label"] == "not-closed-world"
            assert item["expected_sites"]
