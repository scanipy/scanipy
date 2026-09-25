"""Corpus-side validity/contract tests, not runtime fingerprint acceptance.

No generated program is executed. Run explicitly because platform pytest
intentionally excludes all corpus directories from its ordinary collection.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import shutil
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

import jsonschema
import pytest

_PIPE = Path(__file__).resolve().parent
sys.path[:0] = [str(_PIPE), str(_PIPE.parent)]

import build_corpus as build  # noqa: E402
import refactor_transforms as rt  # noqa: E402
from bases import render  # noqa: E402
from manifest_contract import (  # noqa: E402
    canonical_digest,
    json_bytes,
    manifest_bytes,
    safe_relative,
    sha256_bytes,
    tree_digest,
)
from supplemental_cases import build_controls, two_call_chain_controls  # noqa: E402
from validate_fixtures import InvalidFixture, validate_transformation  # noqa: E402

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def manifest():
    return json.loads(build.MANIFEST_PATH.read_text())


@pytest.fixture(scope="module")
def schema():
    return json.loads((build.CORPUS_ROOT / "case-manifest.schema.json").read_text())


@pytest.mark.parametrize("index", range(8))
@pytest.mark.parametrize("refactor", rt.REFACTORS)
def test_genuine_transforms_are_deterministic_and_independently_validated(index, refactor):
    base = render(index)
    first, second = rt.apply_refactor(base, refactor), rt.apply_refactor(base, refactor)
    assert first == second
    assert first.ground_truth_label == rt.GROUND_TRUTH[refactor]
    assert all(text.endswith("\n") and not text.endswith("\n\n") for text in first.files.values())
    validate_transformation(base, first)


def test_exact_inventory_and_typed_schema(manifest, schema):
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(manifest, schema)
    cases = manifest["cases"]
    assert manifest["schema_version"] == 2
    assert manifest["corpus_version"] == "0.2.0"
    assert manifest["case_count"] == len(cases) == 422
    assert len({case["case_id"] for case in cases}) == 422
    assert Counter(case["evidence_type"] for case in cases) == {
        "structural_comparison": 370,
        "finding_removal": 50,
        "analysis_failure": 2,
    }
    assert Counter(case["expected_outcome"] for case in cases) == {
        "stay": 270,
        "flip": 100,
        "absent": 50,
        "failure": 2,
    }
    primary = [case for case in cases if case["seed_id"] and case["refactor"] in rt.REFACTORS]
    assert len(primary) == 350
    assert Counter(case["ground_truth_label"] for case in primary) == {
        "should-stay": 250,
        "should-flip": 100,
    }
    assert {case["language"] for case in cases} == {"java", "python"}
    assert {case["finding_class"] for case in cases} == build.STAGE_A_CLASSES


@pytest.mark.parametrize(
    "mutation",
    [
        "untyped",
        "weak",
        "after_missing",
        "removal_as_flip",
        "failure_as_absent",
        "bad_path",
        "boolean_line",
    ],
)
def test_schema_rejects_invalid_case_contracts(manifest, schema, mutation):
    changed = copy.deepcopy(manifest)
    structural = next(c for c in changed["cases"] if c["evidence_type"] == "structural_comparison")
    if mutation == "untyped":
        structural.pop("evidence_type")
    elif mutation == "weak":
        structural["required_strength"] = "weak_weak"
    elif mutation == "after_missing":
        structural["after_locator"] = None
    elif mutation == "removal_as_flip":
        next(c for c in changed["cases"] if c["evidence_type"] == "finding_removal")[
            "expected_outcome"
        ] = "flip"
    elif mutation == "failure_as_absent":
        next(c for c in changed["cases"] if c["evidence_type"] == "analysis_failure")[
            "expected_outcome"
        ] = "absent"
    elif mutation == "bad_path":
        structural["after_dir"] = "../../outside"
    else:
        structural["before_locator"]["line"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(changed, schema)


@pytest.mark.parametrize("index", (0, 1))
@pytest.mark.parametrize(
    "refactor",
    (
        "independent-reordering",
        "pure-extract",
        "fqn-move-package-rename",
        "aliasing-changing-extract",
    ),
)
def test_superficial_old_transformations_are_rejected(index, refactor):
    base = render(index)
    result = rt.apply_refactor(base, refactor)
    if refactor == "independent-reordering":
        bad_source = base.source + (
            "// inserted unrelated code\n" if index == 0 else "# inserted unrelated code\n"
        )
    elif refactor == "pure-extract":
        bad_source = result.source.replace(
            f"{base.result_name} = _extracted_value("
            + ", ".join(a for _, _, a in base.helper_parameters)
            + ")",
            f"{base.result_name} = {base.expression}",
        )
    elif refactor == "fqn-move-package-rename":
        bad_source = base.source + (
            "// relocation comment only\n" if index == 0 else "# relocation comment only\n"
        )
    else:
        bad_source = result.source.replace(f"{base.parameter} = box[0]", "unrelated = box[0]")
    broken = replace(
        result, filename=base.filename, files={**base.files, base.filename: bad_source}
    )
    with pytest.raises((InvalidFixture, ValueError)):
        validate_transformation(base, broken)


def test_fix_is_removal_plus_separate_retained_sink_comparison(manifest):
    removals = [c for c in manifest["cases"] if c["evidence_type"] == "finding_removal"]
    assert all(c["expected_outcome"] == "absent" and c["after_locator"] is None for c in removals)
    comparisons = [c for c in manifest["cases"] if c["refactor"] == "genuine-fix-structural"]
    assert len(comparisons) == 38
    assert all(
        c["finding_class"] != "deserialization" and c["expected_outcome"] == "flip"
        for c in comparisons
    )
    assert all(c["observation_subject"] == "corresponding_sink_slice" for c in comparisons)


def test_locators_resolve_to_exact_source_calls(manifest):
    for case in manifest["cases"]:
        for side in ("before", "after"):
            locator = case[f"{side}_locator"]
            if locator is None:
                continue
            root = safe_relative(build.CORPUS_ROOT, case[f"{side}_dir"])
            source = safe_relative(root, locator["file"]).read_text()
            line = source.splitlines()[locator["line"] - 1]
            assert line.strip() == locator["call_text"]
            assert line[locator["column"] - 1 :].startswith(locator["callee"] + "(")
            assert tree_digest(root) == case[f"{side}_tree_digest"]


def test_locator_refuses_ambiguous_and_negative_occurrence():
    with pytest.raises(ValueError, match="expected one"):
        rt.locate("sink(a); sink(b);", "Sample.java", "sink")
    with pytest.raises(ValueError, match="missing"):
        rt.locate("sink(a);", "Sample.java", "sink", occurrence=-1)
    assert rt.locate("sink(a); sink(b);", "Sample.java", "sink", occurrence=1)["column"] == 10


@pytest.mark.parametrize("index", (0, 1))
def test_two_calls_reuse_one_multi_assignment_helper_with_distinct_actuals(index):
    base = render(index)
    controls = two_call_chain_controls(base)
    assert len(controls) == 2
    assert controls[0].before_files == controls[1].before_files
    assert controls[0].after_files == controls[1].after_files
    assert controls[0].before_locator != controls[1].before_locator
    assert controls[0].after_locator != controls[1].after_locator
    source = controls[0].after_files[base.filename]
    assert source.count("_extracted_value(") == 3
    assert "partial = prefix + item" in source and "completed = partial + suffix" in source
    assert "return completed" in source
    assert "secondary" in source and source.count(base.sink_callee + "(") == 2
    if base.language == "python":
        module = ast.parse(source)
        helper = next(n for n in module.body if isinstance(n, ast.FunctionDef))
        assert [type(n) for n in helper.body] == [ast.Assign, ast.Assign, ast.Return]
        calls = [
            n
            for n in ast.walk(module)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == helper.name
        ]
        assert len(calls) == 2 and ast.dump(calls[0].args[1]) != ast.dump(calls[1].args[1])


def test_argument_order_negative_changes_call_not_helper_declaration():
    controls = [c for c in build_controls() if "argument-position" in c.name]
    for control in controls:
        filename = control.before_locator["file"]
        before, after = control.before_files[filename], control.after_files[filename]
        before_decl = next(
            line
            for line in before.splitlines()
            if "def _extracted_value" in line or "private static" in line
        )
        assert before_decl in after
        changed = [
            (a, b) for a, b in zip(before.splitlines(), after.splitlines(), strict=True) if a != b
        ]
        assert len(changed) == 1 and "= _extracted_value(" in changed[0][0]


def test_python_purity_requires_real_type_guard_not_just_annotation():
    for index in (1, 3, 5, 7):
        base = render(index)
        source = rt.apply_refactor(base, "pure-extract").source
        assert f"if type({base.parameter}) is not {base.parameter_type}:" in source
        assert "raise TypeError" in source


def test_all_python_source_syntax_matches_declared_expectations(manifest):
    result = build.validate_syntax(manifest, java=False)
    assert result["all_as_expected"]
    assert result["scanned_source_executed"] is False
    invalid = [r for r in result["results"] if not r["valid"]]
    assert len(invalid) == 1 and invalid[0]["directory"].endswith("python-parser-failure/after")


def test_lock_recomputed_from_current_sources_and_manifest(manifest):
    existing = build._load_yaml(build.LOCK_PATH)
    recomputed, hard, warnings = build.assemble_lock()
    assert hard == [] and warnings
    assert canonical_digest(existing) == canonical_digest(recomputed) == existing["corpus_digest"]
    assert existing["case_manifest_sha256"] == sha256_bytes(build.MANIFEST_PATH.read_bytes())
    assert build.MANIFEST_PATH.read_bytes() == manifest_bytes(manifest)
    assert len(build.MANIFEST_PATH.read_bytes()) <= 500 * 1024
    assert existing["distinct_topologies"] == 8 and existing["corpus_version"] != "1.0.0"


def test_historical_lock_bytes_are_retained():
    archived = build.CORPUS_ROOT / "history/0.1.0/corpus.lock"
    assert (
        hashlib.sha256(archived.read_bytes()).hexdigest()
        == "32738b453adf05db9223ed0288f18e50afe23a9e0f5bc6bfd1c82a98b846155f"
    )
    assert build._load_yaml(archived)["corpus_version"] == "0.1.0"


def test_tree_digest_is_length_framed_ordered_and_path_sensitive(tmp_path):
    (tmp_path / "b").write_bytes(b"second")
    (tmp_path / "a").write_bytes(b"first")
    digest = hashlib.sha256()
    for name, data in ((b"a", b"first"), (b"b", b"second")):
        digest.update(len(name).to_bytes(8, "big") + name + len(data).to_bytes(8, "big") + data)
    original = tree_digest(tmp_path)
    assert original == "sha256:" + digest.hexdigest()
    (tmp_path / "a").rename(tmp_path / "c")
    assert tree_digest(tmp_path) != original


def test_tree_and_path_checks_reject_symlink_escape(tmp_path):
    with pytest.raises(ValueError):
        safe_relative(tmp_path, "../outside")
    (tmp_path / "link").symlink_to(tmp_path.parent)
    with pytest.raises(ValueError, match="symlink"):
        tree_digest(tmp_path)


def test_check_detects_current_source_metadata_and_inventory_drift(tmp_path, monkeypatch):
    target = tmp_path / "corpus"
    shutil.copytree(
        build.CORPUS_ROOT, target, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache")
    )
    monkeypatch.setattr(build, "CORPUS_ROOT", target)
    monkeypatch.setattr(build, "SEEDS_DIR", target / "seeds")
    source = target / "seeds/seed-001/before" / render(0).filename
    source.write_text(source.read_text() + "// unrecorded drift\n")
    control_meta = target / "controls/meta.json"
    records = json.loads(control_meta.read_text())
    records[0]["expected_outcome"] = "flip"
    control_meta.write_bytes(json_bytes(records))
    (target / "seeds/seed-999").mkdir()
    _, errors, _ = build.assemble_lock()
    assert any("source differs" in error for error in errors)
    assert any("control metadata differs" in error for error in errors)
    assert any("seed inventory differs" in error for error in errors)
