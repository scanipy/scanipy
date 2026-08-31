"""Unit coverage for the refactor-invariance validation harness (TRACK E).

Three surfaces are exercised, all hermetically (no joern, no docker):

1. **Corpus / ground-truth parsing** against the REAL corpus files under
   ``tests/corpora/refactor/`` — the schema is read, not assumed.
2. **Report generation** driven by a STUB fingerprinter, including a pair that
   cannot be evaluated (the stub returns ``None``) and a pair whose sides are
   ``weak``-classed.
3. **Stay/flip comparison logic**, including the two honesty rules: a missing
   fingerprint is never a flip, and a weak/weak match is not counted as
   strong-strong invariance evidence.

The real end-to-end run (real Joern + real Algorithm 3) is deliberately NOT
attempted here — it needs the snapshot worker image.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.validate_refactor_fingerprints import (
    CORPUS_CAVEAT,
    EXPECTED_OUTCOME,
    WEAK_CLASS_CAVEAT,
    CorpusIntegrityError,
    HarnessDependencyError,
    RefactorPair,
    SideFingerprint,
    build_arg_parser,
    build_report,
    evaluate_pair,
    load_corpus_meta,
    load_pairs,
    locate_sink_line,
    render_summary,
    require_real_dependencies,
    resolve_source_file,
    run,
    sink_callee_token,
)

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO_ROOT / "tests" / "corpora" / "refactor"

_SEVEN_REFACTORS = {
    "alpha-rename-local",
    "pdg-only-formatting",
    "independent-reordering",
    "pure-extract",
    "fqn-move-package-rename",
    "genuine-fix",
    "aliasing-changing-extract",
}


# ---------------------------------------------------------------------------
# 1. Corpus / ground-truth parsing against the REAL corpus
# ---------------------------------------------------------------------------


def test_load_corpus_meta_reads_real_lock() -> None:
    meta = load_corpus_meta(CORPUS_DIR)
    assert meta.corpus_id == "CMP-CORP-REFAC-01"
    assert meta.corpus_digest.startswith("sha256:")
    # The topology-thin disclosure the report has to repeat.
    assert meta.distinct_topologies == 8
    assert meta.seed_count == 50
    assert meta.pair_count == 350
    assert set(meta.refactor_taxonomy) == _SEVEN_REFACTORS


def test_load_pairs_enumerates_every_recorded_pair() -> None:
    meta = load_corpus_meta(CORPUS_DIR)
    pairs = load_pairs(CORPUS_DIR)
    assert len(pairs) == meta.pair_count == 350
    assert len({p.seed_id for p in pairs}) == meta.seed_count == 50
    assert {p.refactor for p in pairs} == _SEVEN_REFACTORS
    # Ground truth as recorded, cross-checked against the taxonomy in the lock.
    for pair in pairs:
        assert pair.ground_truth == meta.refactor_taxonomy[pair.refactor]
        assert pair.ground_truth in EXPECTED_OUTCOME


def test_load_pairs_carries_paths_language_and_sink_line() -> None:
    pairs = {(p.seed_id, p.refactor): p for p in load_pairs(CORPUS_DIR, limit=2)}
    java = pairs[("seed-001", "alpha-rename-local")]
    assert java.language == "java"
    assert java.finding_class == "injection"
    assert java.sink_file == "OrderService.java"
    assert java.before_sink_line == 16
    assert java.before_dir == CORPUS_DIR / "seeds" / "seed-001" / "before"
    assert java.after_dir == CORPUS_DIR / "seeds" / "seed-001" / "after" / "alpha-rename-local"
    assert java.before_dir.is_dir() and java.after_dir.is_dir()

    python = pairs[("seed-002", "genuine-fix")]
    assert python.language == "python"
    assert python.sink_file == "order_service.py"
    assert python.ground_truth == "should-flip"


def test_limit_takes_the_first_n_seeds_in_sorted_order() -> None:
    pairs = load_pairs(CORPUS_DIR, limit=3)
    assert sorted({p.seed_id for p in pairs}) == ["seed-001", "seed-002", "seed-003"]
    assert len(pairs) == 21  # 3 seeds x 7 refactors


def test_corpus_languages_are_all_joern_mappable() -> None:
    # Guards a silent UnsupportedParseLanguageError at real-run time.
    from analysis.cpg_ingest.joern_frontend import JOERN_LANGUAGE_BY_SCANIPY_LANG

    assert {p.language for p in load_pairs(CORPUS_DIR)} <= set(JOERN_LANGUAGE_BY_SCANIPY_LANG)


def test_meta_label_disagreeing_with_lock_is_a_hard_error(tmp_path: Path) -> None:
    corpus = _copy_minimal_corpus(tmp_path)
    meta_path = corpus / "seeds" / "seed-001" / "meta.yaml"
    text = meta_path.read_text(encoding="utf-8")
    meta_path.write_text(
        text.replace(
            "  - after_dir: after/genuine-fix\n    ground_truth_label: should-flip",
            "  - after_dir: after/genuine-fix\n    ground_truth_label: should-stay",
        ),
        encoding="utf-8",
    )
    with pytest.raises(CorpusIntegrityError, match=r"disagrees with corpus\.lock"):
        load_pairs(corpus)


def test_missing_lock_is_a_hard_error(tmp_path: Path) -> None:
    with pytest.raises(CorpusIntegrityError, match=r"no corpus\.lock"):
        load_corpus_meta(tmp_path)


def _copy_minimal_corpus(tmp_path: Path) -> Path:
    """Copy seed-001 + a lock naming only seed-001 into a scratch corpus dir."""
    import shutil

    dest = tmp_path / "refactor"
    (dest / "seeds").mkdir(parents=True)
    shutil.copytree(CORPUS_DIR / "seeds" / "seed-001", dest / "seeds" / "seed-001")
    import yaml

    lock = yaml.safe_load((CORPUS_DIR / "corpus.lock").read_text(encoding="utf-8"))
    lock["seeds"] = [s for s in lock["seeds"] if s["seed_id"] == "seed-001"]
    (dest / "corpus.lock").write_text(yaml.safe_dump(lock), encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# 2. Sink location helpers (harness plumbing over the corpus's missing
#    after-side sink coordinates)
# ---------------------------------------------------------------------------


def test_sink_callee_token_takes_the_outermost_call() -> None:
    assert sink_callee_token("        st.executeQuery(query000);") == "executeQuery"
    assert sink_callee_token("        self.cursor.execute(sql001)") == "execute"
    assert sink_callee_token("  FileInputStream in = new FileInputStream(target);") == (
        "FileInputStream"
    )
    assert sink_callee_token("        int unrelated = 7 + 35;") is None


def test_locate_sink_line_returns_every_candidate() -> None:
    text = "import java.io.FileInputStream;\nnew FileInputStream(t);\nFileInputStream(x);\n"
    assert locate_sink_line(text, "FileInputStream") == [2, 3]
    assert locate_sink_line(text, "nope") == []


def test_before_sink_line_from_meta_matches_the_real_before_file() -> None:
    pair = next(p for p in load_pairs(CORPUS_DIR, limit=1) if p.refactor == "genuine-fix")
    before = resolve_source_file(pair.before_dir, pair.sink_file)
    assert before is not None
    line = before.read_text(encoding="utf-8").splitlines()[pair.before_sink_line - 1]
    assert sink_callee_token(line) == "executeQuery"


def test_resolve_source_file_refuses_to_guess(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert resolve_source_file(empty, "X.java") is None
    two = tmp_path / "two"
    two.mkdir()
    (two / "a.java").write_text("", encoding="utf-8")
    (two / "b.java").write_text("", encoding="utf-8")
    assert resolve_source_file(two, "X.java") is None
    one = tmp_path / "one"
    one.mkdir()
    (one / "renamed.java").write_text("", encoding="utf-8")
    assert resolve_source_file(one, "X.java") == one / "renamed.java"


# ---------------------------------------------------------------------------
# 3. Stay/flip comparison logic, driven by a STUB fingerprinter
# ---------------------------------------------------------------------------


class StubFingerprinter:
    """Returns caller-scripted results keyed by directory name. No joern."""

    def __init__(
        self,
        *,
        by_dir: dict[str, SideFingerprint | None],
        raises: dict[str, Exception] | None = None,
    ) -> None:
        self.by_dir = by_dir
        self.raises = raises or {}
        self.calls: list[tuple[str, str, int]] = []

    def __call__(
        self, *, src_dir: Path, language: str, filename: str, line: int
    ) -> SideFingerprint | None:
        key = src_dir.name
        self.calls.append((key, filename, line))
        if key in self.raises:
            raise self.raises[key]
        return self.by_dir[key]


def _strong(value: str) -> SideFingerprint:
    return SideFingerprint(
        slice_fingerprint=value, fingerprint_class="strong", budget_exhausted=False
    )


def _weak(value: str) -> SideFingerprint:
    return SideFingerprint(slice_fingerprint=value, fingerprint_class="weak", budget_exhausted=True)


def _pair(refactor: str) -> RefactorPair:
    """The real seed-001 (injection/java) pair for ``refactor``."""
    return next(p for p in load_pairs(CORPUS_DIR, limit=1) if p.refactor == refactor)


def test_identical_fingerprints_are_stayed_and_meet_a_should_stay_expectation() -> None:
    pair = _pair("alpha-rename-local")
    stub = StubFingerprinter(by_dir={"before": _strong("aa"), "alpha-rename-local": _strong("aa")})
    res = evaluate_pair(pair, stub)
    assert res.outcome == "stayed"
    assert res.expected_outcome == "stayed"
    assert res.matches_expectation is True
    assert res.comparison_validity == "strong"
    assert res.before_sink_line == 16
    assert res.after_sink_line == 16
    assert res.sink_token == "executeQuery"
    assert res.before_locator_agrees is True


def test_differing_fingerprints_are_flipped() -> None:
    pair = _pair("genuine-fix")
    stub = StubFingerprinter(by_dir={"before": _strong("aa"), "genuine-fix": _strong("bb")})
    res = evaluate_pair(pair, stub)
    assert res.outcome == "flipped"
    assert res.expected_outcome == "flipped"
    assert res.matches_expectation is True
    # genuine-fix rewrites the sink call site (`st.executeQuery(q)` ->
    # PreparedStatement `st.executeQuery()` one line further down): the after
    # line is LOCATED in the after file, never copied from meta.yaml.
    assert res.before_sink_line == 16
    assert res.after_sink_line == 17


def test_a_should_stay_pair_that_flips_is_reported_contrary_not_hidden() -> None:
    pair = _pair("pure-extract")
    stub = StubFingerprinter(by_dir={"before": _strong("aa"), "pure-extract": _strong("bb")})
    res = evaluate_pair(pair, stub)
    assert res.outcome == "flipped"
    assert res.expected_outcome == "stayed"
    assert res.matches_expectation is False


def test_missing_after_fingerprint_is_unevaluated_never_a_flip() -> None:
    pair = _pair("genuine-fix")
    stub = StubFingerprinter(by_dir={"before": _strong("aa"), "genuine-fix": None})
    res = evaluate_pair(pair, stub)
    assert res.outcome == "unevaluated"
    assert res.unevaluated_reason == "no-fingerprint-after"
    assert res.matches_expectation is None
    assert res.after_fingerprint is None
    # The before side WAS computed, so it is faithfully carried.
    assert res.before_fingerprint == "aa"


def test_missing_before_fingerprint_is_unevaluated() -> None:
    pair = _pair("alpha-rename-local")
    stub = StubFingerprinter(by_dir={"before": None, "alpha-rename-local": _strong("aa")})
    res = evaluate_pair(pair, stub)
    assert res.outcome == "unevaluated"
    assert res.unevaluated_reason == "no-fingerprint-before"


def test_parse_failure_is_unevaluated_with_the_real_exception_text() -> None:
    pair = _pair("alpha-rename-local")
    stub = StubFingerprinter(
        by_dir={"before": _strong("aa"), "alpha-rename-local": _strong("aa")},
        raises={"alpha-rename-local": RuntimeError("joern-parse exited 1")},
    )
    res = evaluate_pair(pair, stub)
    assert res.outcome == "unevaluated"
    assert res.unevaluated_reason == "after-fingerprint-error"
    assert res.unevaluated_detail is not None
    assert "joern-parse exited 1" in res.unevaluated_detail


def test_weak_sides_still_compare_but_are_not_strong_evidence() -> None:
    pair = _pair("alpha-rename-local")
    stub = StubFingerprinter(by_dir={"before": _weak("ww"), "alpha-rename-local": _weak("ww")})
    res = evaluate_pair(pair, stub)
    assert res.outcome == "stayed"
    assert res.comparison_validity == "weak"
    report = build_report(
        [res],
        load_corpus_meta(CORPUS_DIR),
        corpus_dir=CORPUS_DIR,
        limit=1,
        fingerprinter_name="stub",
    )
    assert report["totals"]["as_expected"] == 1
    # ... but it contributes nothing to the strong/strong subset.
    assert report["totals"]["strong_strong_evaluated"] == 0
    assert report["by_refactor"]["alpha-rename-local"]["strong_strong_total"] == 0


def test_sink_not_located_when_the_token_is_ambiguous(tmp_path: Path) -> None:
    before = tmp_path / "before"
    after = tmp_path / "after"
    before.mkdir()
    after.mkdir()
    (before / "X.java").write_text("class X {\n  q.run(a);\n}\n", encoding="utf-8")
    (after / "X.java").write_text("class X {\n  q.run(a);\n  q.run(b);\n}\n", encoding="utf-8")
    pair = RefactorPair(
        seed_id="seed-x",
        language="java",
        finding_class="injection",
        refactor="alpha-rename-local",
        ground_truth="should-stay",
        before_dir=before,
        after_dir=after,
        sink_file="X.java",
        before_sink_line=2,
    )
    stub = StubFingerprinter(by_dir={})
    res = evaluate_pair(pair, stub)
    assert res.outcome == "unevaluated"
    assert res.unevaluated_reason == "sink-not-located"
    assert stub.calls == []  # never fingerprinted anything it could not locate


# ---------------------------------------------------------------------------
# 4. Report generation
# ---------------------------------------------------------------------------


def _mixed_stub() -> StubFingerprinter:
    """should-stay refactors stay; genuine-fix flips; aliasing extract unevaluated."""
    return StubFingerprinter(
        by_dir={
            "before": _strong("aa"),
            "alpha-rename-local": _strong("aa"),
            "pdg-only-formatting": _strong("aa"),
            "independent-reordering": _strong("aa"),
            "pure-extract": _strong("bb"),  # deliberately CONTRARY to ground truth
            "fqn-move-package-rename": _strong("aa"),
            "genuine-fix": _strong("cc"),
            "aliasing-changing-extract": None,  # unevaluated
        }
    )


def test_report_shape_counts_and_unevaluated_list() -> None:
    report = run(
        corpus_dir=CORPUS_DIR,
        fingerprinter=_mixed_stub(),
        fingerprinter_name="stub",
        limit=1,
    )
    assert report["run"]["pairs_considered"] == 7
    assert report["totals"]["evaluated"] == 6
    assert report["totals"]["unevaluated"] == 1
    assert report["totals"]["stayed"] == 4
    assert report["totals"]["flipped"] == 2
    assert report["totals"]["as_expected"] == 5
    assert report["totals"]["contrary_to_expectation"] == 1

    # The contrary should-stay row is visible, not smoothed away.
    pe = report["by_refactor"]["pure-extract"]
    assert pe["expected_outcome"] == "stayed"
    assert pe["flipped"] == 1
    assert pe["contrary_to_expectation"] == 1

    # The unevaluated pair is listed explicitly with a reason — never dropped.
    assert report["totals"]["unevaluated_reason_counts"] == {"no-fingerprint-after": 1}
    assert [u["refactor"] for u in report["unevaluated"]] == ["aliasing-changing-extract"]
    assert report["unevaluated"][0]["reason"] == "no-fingerprint-after"

    # Every considered pair keeps a row, evaluated or not.
    assert len(report["pairs"]) == 7


def test_report_embeds_corpus_provenance_and_both_caveats() -> None:
    report = run(
        corpus_dir=CORPUS_DIR, fingerprinter=_mixed_stub(), fingerprinter_name="stub", limit=1
    )
    corpus = report["corpus"]
    assert corpus["corpus_id"] == "CMP-CORP-REFAC-01"
    assert corpus["distinct_topologies"] == 8
    assert corpus["corpus_digest"].startswith("sha256:")
    assert report["caveats"]["corpus_topology"] == CORPUS_CAVEAT
    assert report["caveats"]["weak_fingerprint_class"] == WEAK_CLASS_CAVEAT
    assert "topology-thin" in CORPUS_CAVEAT.lower()


def test_report_is_json_serialisable_and_deterministic() -> None:
    kwargs = {
        "corpus_dir": CORPUS_DIR,
        "fingerprinter_name": "stub",
        "limit": 2,
    }
    a = json.dumps(
        run(fingerprinter=_mixed_stub(), **kwargs),  # type: ignore[arg-type]
        indent=2,
        sort_keys=True,
    )
    b = json.dumps(
        run(fingerprinter=_mixed_stub(), **kwargs),  # type: ignore[arg-type]
        indent=2,
        sort_keys=True,
    )
    assert a == b


def test_fingerprint_class_counts_are_tallied_per_side() -> None:
    stub = StubFingerprinter(
        by_dir={
            "before": _strong("aa"),
            "alpha-rename-local": _weak("aa"),
            "pdg-only-formatting": _strong("aa"),
            "independent-reordering": _strong("aa"),
            "pure-extract": _strong("aa"),
            "fqn-move-package-rename": _strong("aa"),
            "genuine-fix": _strong("cc"),
            "aliasing-changing-extract": _strong("dd"),
        }
    )
    report = run(corpus_dir=CORPUS_DIR, fingerprinter=stub, fingerprinter_name="stub", limit=1)
    assert report["fingerprint_class_counts"]["before"] == {"strong": 7, "weak": 0, "other": 0}
    assert report["fingerprint_class_counts"]["after"] == {"strong": 6, "weak": 1, "other": 0}


def test_render_summary_shows_unevaluated_and_repeats_the_caveat() -> None:
    report = run(
        corpus_dir=CORPUS_DIR, fingerprinter=_mixed_stub(), fingerprinter_name="stub", limit=1
    )
    text = render_summary(report)
    assert "UNEVALUATED PAIRS (1)" in text
    assert "no-fingerprint-after" in text
    assert "aliasing-changing-extract" in text
    assert CORPUS_CAVEAT in text
    assert WEAK_CLASS_CAVEAT in text
    for refactor in _SEVEN_REFACTORS:
        assert refactor in text


def test_render_summary_says_none_when_everything_evaluated() -> None:
    stub = StubFingerprinter(
        by_dir={
            "before": _strong("aa"),
            "alpha-rename-local": _strong("aa"),
            "pdg-only-formatting": _strong("aa"),
            "independent-reordering": _strong("aa"),
            "pure-extract": _strong("aa"),
            "fqn-move-package-rename": _strong("aa"),
            "genuine-fix": _strong("cc"),
            "aliasing-changing-extract": _strong("dd"),
        }
    )
    text = render_summary(
        run(corpus_dir=CORPUS_DIR, fingerprinter=stub, fingerprinter_name="stub", limit=1)
    )
    assert "UNEVALUATED PAIRS: none." in text


# ---------------------------------------------------------------------------
# 5. Loud startup failure + CLI surface
# ---------------------------------------------------------------------------


def test_require_real_dependencies_fails_loudly_while_tracks_a_b_are_unmerged() -> None:
    """TRACK A/B are not in this worktree — the harness must say so, not run.

    Once both land this test's expectation inverts; it is written to assert the
    *loudness contract* either way.
    """
    try:
        collaborators = require_real_dependencies()
    except HarnessDependencyError as exc:
        message = str(exc)
        assert "missing collaborators" in message
        assert "refuses to emit a report it could not compute" in message
    else:
        # Both tracks merged: then all three must be real, callable objects —
        # the harness never proceeds on a partially-resolved dependency set.
        assert len(collaborators) == 3
        assert all(callable(c) for c in collaborators)


def test_cli_help_states_the_corpus_caveat() -> None:
    help_text = build_arg_parser().format_help()
    assert "--corpus-dir" in help_text
    assert "--out" in help_text
    assert "--limit" in help_text
    assert "UNEVALUATED" in help_text
    assert "topology" in help_text.lower()
