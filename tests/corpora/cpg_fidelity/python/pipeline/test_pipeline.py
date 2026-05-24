"""Pipeline self-tests for CMP-CORP-CPG-python (provisional, corpus-agent authored).

These guard the corpus build's reproducibility + AC contract. The canonical
TST-AC-CORP-CPG-python-a/b specs are QA-owned and [FORTHCOMING]; these are the
corpus-side smoke tests so a pipeline regression is caught immediately.

  - test_every_program_has_ground_truth -> AC-CORP-CPG-python-a (ast/cfg/callgraph/pdg)
  - test_methodology_doc_present         -> AC-CORP-CPG-python-a (documented methodology)
  - test_lock_has_version_and_digest     -> AC-CORP-CPG-python-b (versioned)
  - test_lock_digest_stable              -> AC-CORP-CPG-python-b (digest-pinned)
  - test_extraction_deterministic        -> same source bytes => identical JSON
  - test_all_required_tags_covered       -> DOC §4.3 construct coverage
  - test_dynamic_sites_tagged            -> DOC §3.4 step 3 (dynamic excluded partition)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_PIPE = Path(__file__).resolve().parent
_ROOT = _PIPE.parent
sys.path.insert(0, str(_PIPE))

import build_lock  # noqa: E402
import extract_ground_truth as gt  # noqa: E402

_GT_FILES = ("ast.json", "cfg.json", "callgraph.json", "pdg.json", "parse.json")


@pytest.mark.unit
def test_every_program_has_ground_truth():
    for pid in build_lock.PROGRAMS:
        gtdir = _ROOT / "programs" / pid / "ground_truth"
        for fname in _GT_FILES:
            assert (gtdir / fname).is_file(), f"{pid} missing {fname}"


@pytest.mark.unit
def test_methodology_doc_present():
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    assert "ground-truth-labelling methodology" in readme or "methodology" in readme
    assert (_ROOT / "LICENSES.md").is_file()


@pytest.mark.unit
def test_lock_has_version_and_digest():
    import yaml

    lock = yaml.safe_load((_ROOT / "corpus.lock").read_text(encoding="utf-8"))
    assert lock["corpus_id"] == "CMP-CORP-CPG-python"
    assert lock["corpus_version"]
    assert lock["corpus_digest"].startswith("sha256:")
    assert lock["language"] == "python"


@pytest.mark.unit
def test_lock_digest_stable():
    import yaml

    lock = yaml.safe_load((_ROOT / "corpus.lock").read_text(encoding="utf-8"))
    recomputed = build_lock.canonical_digest({**lock, "corpus_digest": "sha256:PENDING"})
    assert lock["corpus_digest"] == recomputed, "corpus.lock digest drifted"


@pytest.mark.unit
def test_extraction_deterministic(tmp_path):
    # Re-extract one program's AST twice from the same bytes -> identical JSON.
    src = _ROOT / "programs" / "0001-decorators-svc" / "source" / "service.py"
    text = src.read_text(encoding="utf-8")
    tree1 = gt.ast.parse(text)
    tree2 = gt.ast.parse(text)
    j1 = json.dumps(gt.extract_ast(tree1), sort_keys=False)
    j2 = json.dumps(gt.extract_ast(tree2), sort_keys=False)
    assert j1 == j2


@pytest.mark.unit
def test_all_required_tags_covered():
    covered: set[str] = set()
    for meta in build_lock.PROGRAMS.values():
        covered |= set(meta["tags"])
    assert build_lock.REQUIRED_TAGS <= covered, build_lock.REQUIRED_TAGS - covered


@pytest.mark.unit
def test_dynamic_sites_tagged():
    # dispatch.py: getattr / dict-dispatch / runtime receiver are `dynamic`;
    # the direct local call `op -> add` is `static`.
    cg = json.loads(
        (_ROOT / "programs" / "0005-dynamic-dispatch" / "ground_truth" / "callgraph.json")
        .read_text(encoding="utf-8")
    )["dispatch.py"]["edges"]
    kinds = {(e["caller"], e["callee"]): e["kind"] for e in cg}
    assert kinds[("op", "add")] == "static"
    assert kinds[("dispatch_getattr", "getattr")] == "dynamic"
    assert kinds[("dispatch_by_name", "fn")] == "dynamic"
