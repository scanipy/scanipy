"""Legacy report compatibility with explicit physical after-file metadata.

Fingerprints here are controlled test values, not refactor-acceptance evidence.
"""

from dataclasses import replace

import pytest
from scripts.validate_refactor_fingerprints import RefactorPair, SideFingerprint, evaluate_pair

pytestmark = pytest.mark.unit


def make_pair(tmp_path):
    before = tmp_path / "before"
    after = tmp_path / "after"
    before.mkdir()
    (after / "moved").mkdir(parents=True)
    (before / "original.py").write_text("danger(value)\n", encoding="utf-8")
    (after / "moved/renamed.py").write_text("danger(renamed)\n", encoding="utf-8")
    # This old-path decoy must never replace the explicitly declared after file.
    (after / "original.py").write_text("unrelated()\n", encoding="utf-8")
    return RefactorPair(
        seed_id="test-seed",
        language="python",
        finding_class="injection",
        refactor="fqn-move-package-rename",
        ground_truth="should-stay",
        before_dir=before,
        after_dir=after,
        sink_file="original.py",
        before_sink_line=1,
        after_sink_file="moved/renamed.py",
    )


def test_explicit_moved_file_and_relative_location_reach_fingerprinter(tmp_path):
    pair = make_pair(tmp_path)
    calls = []

    def fingerprint(*, src_dir, language, filename, line):
        calls.append((src_dir, language, filename, line))
        return SideFingerprint("ab" * 32, "strong", budget_exhausted=False)

    result = evaluate_pair(pair, fingerprint)
    assert result.outcome == "stayed"
    assert calls == [
        (pair.before_dir, "python", "original.py", 1),
        (pair.after_dir, "python", "moved/renamed.py", 1),
    ]


@pytest.mark.parametrize("relative", ["missing.py", "../outside.py"])
def test_missing_or_escaping_explicit_locator_does_not_fall_back(tmp_path, relative):
    pair = replace(make_pair(tmp_path), after_sink_file=relative)
    (tmp_path / "outside.py").write_text("danger(value)\n", encoding="utf-8")

    def fingerprint(**kwargs):
        pytest.fail("invalid explicit locator must not reach fingerprinter")

    result = evaluate_pair(pair, fingerprint)
    assert result.outcome == "unevaluated"
    assert result.unevaluated_reason == "after-source-missing"


def test_symlink_escape_is_unevaluated(tmp_path):
    pair = make_pair(tmp_path)
    outside = tmp_path / "outside.py"
    outside.write_text("danger(value)\n", encoding="utf-8")
    link = pair.after_dir / "external.py"
    link.symlink_to(outside)
    result = evaluate_pair(replace(pair, after_sink_file="external.py"), lambda **_: None)
    assert result.outcome == "unevaluated"
    assert result.unevaluated_reason == "after-source-missing"
