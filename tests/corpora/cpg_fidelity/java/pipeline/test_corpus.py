"""Pipeline self-tests for CMP-CORP-CPG-java (provisional, corpus-agent authored).

These guard the corpus's layout + reproducibility contract. The canonical
TST-AC-CORP-CPG-java-a/b specs are QA-owned and [FORTHCOMING]; these are the
corpus-side smoke tests so a regression is caught immediately.

  - test_every_program_has_four_ground_truth_files -> AC-CORP-CPG-java-a (annotations)
  - test_ground_truth_json_is_valid                -> AC-CORP-CPG-java-a
  - test_required_construct_tags_covered           -> DOC §4.3 (meaningful eval set)
  - test_lock_has_version_and_digest               -> AC-CORP-CPG-java-b (versioned)
  - test_lock_digest_stable                        -> AC-CORP-CPG-java-b (pinned)
  - test_every_source_parses_with_javac            -> parse-success ground-truth basis
  - test_callgraph_lines_within_source             -> ground-truth line sanity
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

_PIPE = Path(__file__).resolve().parent
_ROOT = _PIPE.parent
_PROGRAMS = _ROOT / "programs"
sys.path.insert(0, str(_PIPE))

import build_lock  # noqa: E402

_GT_FILES = ("ast.json", "cfg.json", "callgraph.json", "pdg.json")


def _program_dirs():
    return sorted(d for d in _PROGRAMS.iterdir() if d.is_dir())


def test_every_program_has_four_ground_truth_files():
    for pdir in _program_dirs():
        for gt in _GT_FILES:
            assert (pdir / "ground_truth" / gt).exists(), f"{pdir.name} missing {gt}"
        assert (pdir / "provenance.yaml").exists()
        assert (pdir / "extraction.yaml").exists()
        assert list((pdir / "source").glob("*.java")), f"{pdir.name} has no .java source"


def test_ground_truth_json_is_valid():
    for pdir in _program_dirs():
        for gt in _GT_FILES:
            doc = json.loads((pdir / "ground_truth" / gt).read_text(encoding="utf-8"))
            assert doc.get("program_id") == pdir.name
            assert "schema" in doc


def test_required_construct_tags_covered():
    seen: set[str] = set()
    for pdir in _program_dirs():
        prov = yaml.safe_load((pdir / "provenance.yaml").read_text(encoding="utf-8"))
        seen.update(prov.get("construct_coverage") or [])
    missing = build_lock.REQUIRED_TAGS - seen
    assert not missing, f"required construct tags not covered: {sorted(missing)}"


def test_lock_has_version_and_digest():
    lock = yaml.safe_load((_ROOT / "corpus.lock").read_text(encoding="utf-8"))
    assert lock["corpus_id"] == "CMP-CORP-CPG-java"
    assert lock["corpus_version"]  # semver string present
    assert str(lock["corpus_digest"]).startswith("sha256:")
    assert lock["programs"], "lock lists no programs"


def test_lock_digest_stable():
    lock, hard, _warn = build_lock.assemble_lock()
    assert not hard, f"build refused: {hard}"
    recomputed = build_lock.canonical_digest(lock)
    existing = yaml.safe_load((_ROOT / "corpus.lock").read_text(encoding="utf-8"))
    assert existing["corpus_digest"] == recomputed, "corpus.lock digest drift"


@pytest.mark.skipif(shutil.which("javac") is None, reason="javac not on PATH")
def test_every_source_parses_with_javac():
    for pdir in _program_dirs():
        for src in (pdir / "source").glob("*.java"):
            with tempfile.TemporaryDirectory() as out:
                proc = subprocess.run(
                    ["javac", "-source", "17", "-target", "17", "-d", out, str(src)],
                    capture_output=True,
                    text=True,
                )
                assert proc.returncode == 0, f"{src} failed to parse:\n{proc.stderr}"


def test_callgraph_lines_within_source():
    for pdir in _program_dirs():
        srcs = list((pdir / "source").glob("*.java"))
        max_lines = max(len(s.read_text(encoding="utf-8").splitlines()) for s in srcs)
        cg = json.loads((pdir / "ground_truth" / "callgraph.json").read_text(encoding="utf-8"))
        for edge in cg["edges"]:
            line = edge.get("line")
            if isinstance(line, int):
                assert 1 <= line <= max_lines, (
                    f"{pdir.name}: callgraph line {line} out of range (1..{max_lines})"
                )
