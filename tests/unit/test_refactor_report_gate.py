"""Controlled R04 records only: these tests are not G0 or finding evidence."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from scripts import check_refactor_report as gate

pytestmark = pytest.mark.unit
NOW = datetime(2026, 9, 25, 12, tzinfo=UTC)


def _write_json(path: Path, value: object) -> str:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    return gate.sha256_bytes(path.read_bytes())


@pytest.fixture
def bundle(tmp_path: Path) -> dict[str, Any]:
    """Build an explicitly controlled policy, source trees and observation bundle."""
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    evidence_file = evidence / "controlled.json"
    evidence_file.write_text('{"kind":"CONTROLLED TEST DATA; not real analysis evidence"}\n')
    ref = {"path": evidence_file.name, "sha256": gate.sha256_bytes(evidence_file.read_bytes())}
    cases: list[dict[str, Any]] = []
    for language in ("java", "python"):
        for variant, kind, outcome in (
            ("rename", "structural_comparison", "stay"),
            ("format", "structural_comparison", "stay"),
            ("literal", "structural_comparison", "flip"),
            ("removal", "finding_removal", "absent"),
            ("parse-failure", "analysis_failure", "failure"),
        ):
            case_id = f"control/{language}-{variant}"
            locator = {
                "file": "source.txt",
                "line": 1,
                "column": 1,
                "callee": "sink",
                "call_text": "sink(value)",
            }
            case: dict[str, Any] = {
                "case_id": case_id,
                "seed_id": None,
                "language": language,
                "finding_class": "injection",
                "refactor": variant,
                "ground_truth_label": None,
                "evidence_type": kind,
                "expected_outcome": outcome,
                "required_strength": "strong_strong" if kind == "structural_comparison" else None,
                "before_dir": f"{case_id}/before",
                "after_dir": f"{case_id}/after",
                "before_locator": locator,
                "after_locator": locator if kind == "structural_comparison" else None,
                "expected_preconditions": {
                    "fixture_syntax": "invalid_after" if kind == "analysis_failure" else "valid",
                    "transformation_validation": "valid",
                    "purity_certificate": "proven",
                },
                "rationale": "Controlled checker test, not a real validated transformation",
                "observation_subject": "corresponding_sink_slice"
                if kind == "structural_comparison"
                else "finding_lifecycle",
                "expected_failure": {"stage": "parse", "visible": True, "must_not_resolve": True}
                if kind == "analysis_failure"
                else None,
            }
            for side in ("before", "after"):
                source = corpus / case[f"{side}_dir"]
                source.mkdir(parents=True)
                (source / "source.txt").write_text(f"CONTROLLED {case_id} {side}; sink(value)\n")
                case[f"{side}_tree_digest"] = gate.tree_digest(source)
            cases.append(case)
    manifest = {
        "schema_version": 2,
        "corpus_id": "CONTROLLED-R04",
        "corpus_version": "test.2",
        "path_base": "corpus_root",
        "tree_digest_algorithm": gate.TREE_ALGORITHM,
        "case_count": len(cases),
        "cases": cases,
    }
    manifest_hash = _write_json(corpus / "case-manifest.json", manifest)
    lock = {
        "corpus_id": manifest["corpus_id"],
        "corpus_version": manifest["corpus_version"],
        "case_count": len(cases),
        "case_manifest_sha256": manifest_hash,
        "tree_digest_algorithm": gate.TREE_ALGORITHM,
        "built_at": "controlled",
        "built_by": "unit-test",
    }
    lock["corpus_digest"] = gate.lock_digest(lock)
    (corpus / "corpus.lock").write_text(yaml.safe_dump(lock))
    policy = gate.read_json(gate.DEFAULT_POLICY)
    policy["corpus"] = {
        key: lock[key]
        for key in ("corpus_id", "corpus_version", "corpus_digest", "case_manifest_sha256")
    }
    policy["required_case_ids"] = [case["case_id"] for case in cases]
    policy["required_cells"] = dict(
        Counter(
            "/".join(case[key] for key in ("language", "evidence_type", "expected_outcome"))
            for case in cases
        )
    )
    policy["execution_kinds"] = ["controlled_fixture"]
    policy["baseline_requires_attempts"] = False
    policy_path = tmp_path / "controlled-policy.json"
    _write_json(policy_path, policy)
    environment = {
        "namespace": gate.ENVIRONMENT_NAMESPACE,
        "code_revision": "1" * 40,
        "components": [
            {
                "role": role,
                "name": f"controlled-{role}",
                "version": "test",
                "digest": gate.sha256_bytes(role.encode()),
            }
            for role in policy["environment_roles"]
        ],
        "configuration": {"B": 65536, "T_seconds": 10, "scope": "controlled unit fixture"},
    }
    env_hash = _write_json(evidence / "environment.json", environment)
    observations = []
    for case in cases:
        sides: dict[str, dict[str, Any]] = {}
        for side in ("before", "after"):
            structural = case["evidence_type"] == "structural_comparison"
            failed = side == "after" and case["evidence_type"] == "analysis_failure"
            present = side == "before" and not structural
            absent = side == "after" and case["evidence_type"] == "finding_removal"
            hash_text = (
                "changed" if side == "after" and case["expected_outcome"] == "flip" else "unchanged"
            )
            sides[side] = {
                "source_tree_digest": case[f"{side}_tree_digest"],
                "processing_status": "failed" if failed else "completed",
                "reason": "controlled parse failure" if failed else None,
                "fingerprint": {
                    "hash": gate.sha256_bytes(hash_text.encode()),
                    "class": "strong",
                    "namespace": "scanipy-slice-normal-form/2",
                }
                if structural
                else None,
                "locator": {
                    "status": "matched" if structural or present else "not_run",
                    "value": case[f"{side}_locator"] if structural or present else None,
                },
                "finding": {
                    "status": "present" if present else "absent" if absent else "not_run",
                    "id": f"{case['case_id']}/finding" if present else None,
                    "rule_id": "controlled-rule" if present or absent else None,
                    "origin": "oracle-passthrough" if present else None,
                },
                "scan": {
                    "status": "not_run" if structural else "failed" if failed else "completed",
                    "scan_id": None if structural else f"{case['case_id']}/{side}",
                    "source_tree_digest": case[f"{side}_tree_digest"],
                    "covered_files": [] if structural or failed else ["source.txt"],
                    "covered_rules": [] if structural or failed else ["controlled-rule"],
                    "skipped_files": [],
                    "failed_files": ["source.txt"] if failed else [],
                },
                "error": {"stage": "parse", "visible": True} if failed else None,
                "evidence": [ref],
            }
        structural = case["evidence_type"] == "structural_comparison"
        observations.append(
            {
                "case_id": case["case_id"],
                "language": case["language"],
                "evidence_type": case["evidence_type"],
                **sides,
                "correspondence": {
                    "status": "established" if structural else "not_run",
                    "evidence": [ref] if structural else [],
                },
                "observed_preconditions": {
                    key: {"status": value, "producer": "controlled-test-double", "evidence": [ref]}
                    for key, value in case["expected_preconditions"].items()
                },
                "lifecycle": None
                if structural
                else {
                    "before_finding_id": sides["before"]["finding"]["id"],
                    "after_scan_id": sides["after"]["scan"]["scan_id"],
                    "state": "resolved" if case["evidence_type"] == "finding_removal" else "open",
                    "reason": "fixed"
                    if case["evidence_type"] == "finding_removal"
                    else "analysis_failed",
                    "decision_inherited": False,
                    "evidence": [ref],
                },
            }
        )
    report = {
        "schema_version": 2,
        "gate_policy_id": gate.POLICY_ID,
        "gate_policy_digest": gate.policy_digest(policy),
        "report_id": "controlled-test-report",
        "corpus": copy.deepcopy(policy["corpus"]),
        "run": {
            "code_revision": "1" * 40,
            "started_at": "2026-09-24T10:00:00Z",
            "completed_at": "2026-09-24T10:01:00Z",
            "execution_kind": "controlled_fixture",
            "freshness": "fresh",
            "cache_mode": "disabled",
            "command": ["controlled-test-double", "not-a-real-campaign"],
            "environment_digest": gate.environment_digest(environment),
            "environment_manifest": {"path": "environment.json", "sha256": env_hash},
        },
        "cases": observations,
    }
    return {
        "corpus": corpus,
        "root": evidence,
        "report": report,
        "policy": policy,
        "policy_path": policy_path,
        "cases": {case["case_id"]: case for case in cases},
        "ref": ref,
    }


def _validate(bundle: dict[str, Any]) -> list[gate.CaseVerdict]:
    return gate.validate_report(
        bundle["report"],
        policy=bundle["policy"],
        cases=bundle["cases"],
        corpus_root=bundle["corpus"],
        evidence_root=bundle["root"],
        now=NOW,
    )


def _select(bundle: dict[str, Any], suffix: str = "java-rename") -> dict[str, Any]:
    return next(case for case in bundle["report"]["cases"] if case["case_id"].endswith(suffix))


def test_controlled_complete_record_and_distinct_denominators(bundle: dict[str, Any]) -> None:
    cases = gate.load_corpus(bundle["corpus"], gate.validate_policy(bundle["policy"]))
    assert len(cases) == 10
    verdicts = _validate(bundle)
    result = gate.evaluate("acceptance", verdicts, [verdicts])
    assert result["passed"] and result["feature_acceptance"]
    assert result["required_cases"] == 10
    assert (
        sum(
            row["required"]
            for key, row in result["cells"].items()
            if "/structural_comparison/" in key
        )
        == 6
    )
    assert sum(item.structural_outcome is not None for item in verdicts) == 6


def test_honest_red_baseline_is_not_acceptance_and_summary_is_ignored(
    bundle: dict[str, Any],
) -> None:
    case = _select(bundle)
    case["after"]["fingerprint"]["hash"] = gate.sha256_bytes(b"contrary")
    bundle["report"]["summary"] = {"matches_expectation": True, "passed": 999999, "denominator": 1}
    verdicts = _validate(bundle)
    baseline = gate.evaluate("baseline", verdicts, [])
    assert baseline["passed"] and not baseline["feature_acceptance"]
    acceptance = gate.evaluate("acceptance", verdicts, [verdicts])
    assert not acceptance["passed"] and acceptance["passing_cases"] == 9


@pytest.mark.parametrize(
    "field,value",
    [("class", "weak"), ("namespace", "scanipy-slice-fingerprint/1"), ("namespace", "unknown/999")],
)
def test_weak_or_incompatible_hashes_are_not_feature_credit(
    bundle: dict[str, Any], field: str, value: str
) -> None:
    case = _select(bundle)
    for side in ("before", "after"):
        case[side]["fingerprint"][field] = value
    verdict = next(item for item in _validate(bundle) if item.case_id == case["case_id"])
    assert not verdict.passed and verdict.structural_outcome is None


@pytest.mark.parametrize(
    "mode",
    [
        "missing",
        "extra",
        "duplicate",
        "schema",
        "corpus",
        "type",
        "empty_hash",
        "invalid_class",
        "wrong_locator",
        "bool_locator",
        "stale_source",
        "claimed_outcome",
        "bare_purity",
        "missing_evidence",
        "wrong_evidence",
        "bad_path",
    ],
)
def test_malformed_or_stale_reports_fail_closed(bundle: dict[str, Any], mode: str) -> None:
    report, case = bundle["report"], _select(bundle)
    if mode == "missing":
        report["cases"].pop()
    elif mode == "extra":
        extra = copy.deepcopy(case)
        extra["case_id"] = "unexpected"
        report["cases"].append(extra)
    elif mode == "duplicate":
        report["cases"].append(case)
    elif mode == "schema":
        report["schema_version"] = 1
    elif mode == "corpus":
        report["corpus"]["corpus_version"] = "old"
    elif mode == "type":
        case["evidence_type"] = "finding_removal"
    elif mode == "empty_hash":
        case["after"]["fingerprint"]["hash"] = ""
    elif mode == "invalid_class":
        case["after"]["fingerprint"]["class"] = "unknown"
    elif mode == "wrong_locator":
        case["after"]["locator"]["value"] = {
            **case["after"]["locator"]["value"],
            "callee": "unrelated",
        }
    elif mode == "bool_locator":
        case["after"]["locator"]["value"] = {**case["after"]["locator"]["value"], "line": True}
    elif mode == "stale_source":
        case["after"]["source_tree_digest"] = gate.sha256_bytes(b"old source")
    elif mode == "claimed_outcome":
        case["outcome"] = "pass"
    elif mode == "bare_purity":
        case["observed_preconditions"]["purity_certificate"] = "proven"
    elif mode == "missing_evidence":
        case["observed_preconditions"]["purity_certificate"]["evidence"] = []
    elif mode == "wrong_evidence":
        (bundle["root"] / "controlled.json").write_text("changed bytes")
    else:
        case["after"]["evidence"] = [{"path": "../escape", "sha256": bundle["ref"]["sha256"]}]
    with pytest.raises(gate.ReportError):
        _validate(bundle)


def test_missing_hash_not_a_flip_and_not_run_purity_not_a_certificate(
    bundle: dict[str, Any],
) -> None:
    case = _select(bundle, "java-literal")
    case["after"]["fingerprint"] = None
    case["observed_preconditions"]["purity_certificate"] = {
        "status": "not_run",
        "producer": None,
        "evidence": [],
    }
    result = next(item for item in _validate(bundle) if item.case_id == case["case_id"])
    assert not result.passed and result.structural_outcome is None


def test_successful_removal_requires_no_second_hash(bundle: dict[str, Any]) -> None:
    case = _select(bundle, "java-removal")
    assert case["after"]["fingerprint"] is None
    result = next(item for item in _validate(bundle) if item.case_id == case["case_id"])
    assert result.passed and result.structural_outcome is None


@pytest.mark.parametrize(
    "change",
    [
        "scan_failure",
        "processing_failure",
        "missing_file",
        "missing_rule",
        "skipped_file",
        "failed_file",
        "no_lifecycle",
        "still_present",
        "no_prior_finding",
        "unlocated_prior_finding",
        "inherited",
    ],
)
def test_removal_negative_controls(bundle: dict[str, Any], change: str) -> None:
    case = _select(bundle, "java-removal")
    after = case["after"]
    if change == "scan_failure":
        after["scan"]["status"] = "failed"
    elif change == "processing_failure":
        after["processing_status"], after["reason"] = "failed", "parse error"
    elif change == "missing_file":
        after["scan"]["covered_files"] = []
    elif change == "missing_rule":
        after["scan"]["covered_rules"] = []
    elif change in {"skipped_file", "failed_file"}:
        after["scan"]["skipped_files" if change == "skipped_file" else "failed_files"] = [
            "source.txt"
        ]
    elif change == "no_lifecycle":
        case["lifecycle"] = None
    elif change == "still_present":
        after["finding"] = copy.deepcopy(case["before"]["finding"])
    elif change == "no_prior_finding":
        case["before"]["finding"] = {
            "status": "not_run",
            "id": None,
            "rule_id": None,
            "origin": None,
        }
        case["lifecycle"] = None
    elif change == "unlocated_prior_finding":
        case["before"]["locator"] = {"status": "not_run", "value": None}
    else:
        case["lifecycle"]["decision_inherited"] = True
    if change in {"scan_failure", "processing_failure"}:
        with pytest.raises(gate.ReportError, match="requires completed detection"):
            _validate(bundle)
    else:
        assert not next(
            item for item in _validate(bundle) if item.case_id == case["case_id"]
        ).passed


@pytest.mark.parametrize("change", ["hidden", "resolved", "inherited", "wrong_stage", "no_prior"])
def test_intentional_failure_is_only_visible_unresolved_error_handling(
    bundle: dict[str, Any], change: str
) -> None:
    case = _select(bundle, "java-parse-failure")
    if change == "hidden":
        case["after"]["error"]["visible"] = False
    elif change == "resolved":
        case["lifecycle"]["state"] = "resolved"
    elif change == "inherited":
        case["lifecycle"]["decision_inherited"] = True
    elif change == "wrong_stage":
        case["after"]["error"]["stage"] = "detect"
    else:
        case["before"]["finding"] = {
            "status": "not_run",
            "id": None,
            "rule_id": None,
            "origin": None,
        }
        case["lifecycle"] = None
    result = next(item for item in _validate(bundle) if item.case_id == case["case_id"])
    assert not result.passed and result.structural_outcome is None


def test_unexpected_parse_failure_stays_structural_and_red(bundle: dict[str, Any]) -> None:
    case = _select(bundle)
    case["after"].update(
        processing_status="failed",
        reason="unexpected parse failure",
        fingerprint=None,
        error={"stage": "parse", "visible": True},
    )
    result = next(item for item in _validate(bundle) if item.case_id == case["case_id"])
    assert result.evidence_type == "structural_comparison" and not result.passed
    assert result.structural_outcome is None


def test_aggregate_improvement_cannot_hide_per_pair_regression(bundle: dict[str, Any]) -> None:
    second = _select(bundle, "java-format")
    second["after"]["fingerprint"]["hash"] = gate.sha256_bytes(b"wrong")
    baseline = _validate(bundle)
    second["after"]["fingerprint"]["hash"] = second["before"]["fingerprint"]["hash"]
    _select(bundle)["after"]["fingerprint"]["hash"] = gate.sha256_bytes(b"wrong")
    current = _validate(bundle)
    assert sum(item.passed for item in current) == sum(item.passed for item in baseline)
    result = gate.evaluate("nonregression", current, [baseline])
    assert not result["passed"] and "control/java-rename" in result["regressions"]


def test_accepted_improvement_is_protected_beyond_original_baseline(bundle: dict[str, Any]) -> None:
    case = _select(bundle)
    original = case["after"]["fingerprint"]["hash"]
    case["after"]["fingerprint"]["hash"] = gate.sha256_bytes(b"wrong")
    baseline = _validate(bundle)
    case["after"]["fingerprint"]["hash"] = original
    improvement = _validate(bundle)
    case["after"]["fingerprint"]["hash"] = gate.sha256_bytes(b"wrong")
    current = _validate(bundle)
    assert gate.evaluate("nonregression", current, [baseline])["passed"]
    result = gate.evaluate("nonregression", current, [baseline, improvement])
    assert not result["passed"]
    assert "cell:java/structural_comparison/stay" in result["regressions"]


@pytest.mark.parametrize(
    "change", ["historical", "reused", "cache", "old", "missing_env", "missing_role"]
)
def test_ineligible_run_cannot_earn_acceptance(bundle: dict[str, Any], change: str) -> None:
    run = bundle["report"]["run"]
    if change == "historical":
        run["execution_kind"] = "historical"
    elif change == "reused":
        run["freshness"] = "reused"
    elif change == "cache":
        run["cache_mode"] = "enabled"
    elif change == "old":
        run["started_at"], run["completed_at"] = "2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"
    elif change == "missing_env":
        run["environment_manifest"] = run["environment_digest"] = None
    else:
        path = bundle["root"] / "environment.json"
        env = gate.read_json(path)
        env["components"].pop()
        run["environment_manifest"]["sha256"] = _write_json(path, env)
        run["environment_digest"] = gate.environment_digest(env)
    assert not gate.evaluate("acceptance", _validate(bundle), [])["passed"]


@pytest.mark.parametrize(
    "change",
    ["future", "image_as_environment", "bad_revision", "bad_env_version", "no_env_reference"],
)
def test_environment_and_time_bindings_are_checked(bundle: dict[str, Any], change: str) -> None:
    run = bundle["report"]["run"]
    if change == "future":
        run["completed_at"] = "2099-01-01T00:00:00Z"
    elif change == "image_as_environment":
        run["environment_digest"] = gate.sha256_bytes(b"image")
    elif change == "bad_revision":
        run["code_revision"] = "main"
    elif change == "no_env_reference":
        run["environment_manifest"] = None
    else:
        path = bundle["root"] / "environment.json"
        env = gate.read_json(path)
        env["namespace"] = "unknown/2"
        run["environment_manifest"]["sha256"] = _write_json(path, env)
    with pytest.raises(gate.ReportError):
        _validate(bundle)


def test_cli_history_is_exact_and_exit_codes_distinguish_invalid_from_red(
    bundle: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz: object = None) -> FixedDateTime:
            return cls(2026, 9, 25, 12, tzinfo=UTC)

    monkeypatch.setattr(gate, "datetime", FixedDateTime)
    report_path = bundle["root"] / "report.json"
    baseline_path = bundle["root"] / "baseline.json"
    baseline_hash = _write_json(baseline_path, bundle["report"])
    _write_json(report_path, bundle["report"])
    args = [
        "--report",
        str(report_path),
        "--corpus-root",
        str(bundle["corpus"]),
        "--policy",
        str(bundle["policy_path"]),
    ]
    assert gate.main([*args, "--mode", "baseline"]) == 0
    assert gate.main([*args, "--mode", "acceptance", "--baseline", str(baseline_path)]) == 2
    bundle["policy"]["history"]["baseline_sha256"] = baseline_hash
    _write_json(bundle["policy_path"], bundle["policy"])
    assert gate.main([*args, "--mode", "acceptance", "--baseline", str(baseline_path)]) == 0
    _select(bundle)["after"]["fingerprint"]["hash"] = gate.sha256_bytes(b"wrong")
    _write_json(report_path, bundle["report"])
    assert gate.main([*args, "--mode", "acceptance", "--baseline", str(baseline_path)]) == 1
    bundle["policy"]["history"]["accepted_improvement_sha256"] = [
        gate.sha256_bytes(b"unprovided accepted report")
    ]
    _write_json(bundle["policy_path"], bundle["policy"])
    assert gate.main([*args, "--mode", "nonregression", "--baseline", str(baseline_path)]) == 2
    capsys.readouterr()


def test_script_runs_from_unrelated_cwd_and_never_imports_corpus_code(
    bundle: dict[str, Any], tmp_path: Path
) -> None:
    pipeline = bundle["corpus"] / "pipeline"
    pipeline.mkdir()
    sentinel = tmp_path / "executed"
    (pipeline / "manifest_contract.py").write_text(
        f"from pathlib import Path\nPath({str(sentinel)!r}).touch()\n"
        "raise RuntimeError('untrusted corpus code executed')\n"
    )
    report = bundle["root"] / "report.json"
    current_time = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    bundle["report"]["run"]["started_at"] = current_time
    bundle["report"]["run"]["completed_at"] = current_time
    _write_json(report, bundle["report"])
    script = Path(gate.__file__).resolve()
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--mode",
            "baseline",
            "--report",
            str(report),
            "--corpus-root",
            str(bundle["corpus"]),
            "--policy",
            str(bundle["policy_path"]),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert not sentinel.exists()


@pytest.mark.parametrize("change", ["source", "manifest", "lock", "duplicate_lock", "symlink"])
def test_corpus_and_manifest_bytes_are_verified(
    bundle: dict[str, Any], change: str, tmp_path: Path
) -> None:
    root = bundle["corpus"]
    if change == "source":
        next(root.rglob("source.txt")).write_text("changed source")
    elif change == "manifest":
        path = root / "case-manifest.json"
        path.write_bytes(path.read_bytes() + b" ")
    elif change == "lock":
        path = root / "corpus.lock"
        path.write_text(path.read_text() + "extra: changed\n")
    elif change == "duplicate_lock":
        path = root / "corpus.lock"
        path.write_text(path.read_text() + "corpus_id: CONTROLLED-R04\n")
    else:
        path = next(root.rglob("source.txt"))
        target = tmp_path / "outside-source"
        target.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(target)
    with pytest.raises(gate.ReportError):
        gate.load_corpus(root, bundle["policy"])


def test_duplicate_json_and_nonfinite_values_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    for text in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
        path.write_text(text)
        with pytest.raises(gate.ReportError):
            gate.read_json(path)


def test_independent_tree_framing_and_acyclic_lock_golden(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "empty").mkdir()
    (source / "é.txt").write_bytes(b"a\x00b")
    (source / "a").write_bytes(b"xyz")
    framed = b""
    for name, data in (("a", b"xyz"), ("é.txt", b"a\x00b")):
        name_bytes = name.encode("utf-8")
        framed += (
            len(name_bytes).to_bytes(8, "big") + name_bytes + len(data).to_bytes(8, "big") + data
        )
    assert gate.tree_digest(source) == "sha256:" + hashlib.sha256(framed).hexdigest()
    lock = {"corpus_digest": "ignored", "built_at": "ignored", "built_by": "ignored", "value": "é"}
    assert gate.lock_digest(lock) == gate.sha256_bytes(b'{"value":"\\u00e9"}')
    lock["value"] = "changed"
    assert gate.lock_digest(lock) != gate.sha256_bytes(b'{"value":"\\u00e9"}')


def test_fully_not_run_is_honest_red_baseline_not_completed_acceptance(
    bundle: dict[str, Any],
) -> None:
    for case in bundle["report"]["cases"]:
        for side in ("before", "after"):
            observation = case[side]
            observation.update(
                processing_status="not_run",
                reason="producer not available",
                fingerprint=None,
                locator={"status": "not_run", "value": None},
                finding={"status": "not_run", "id": None, "rule_id": None, "origin": None},
                error=None,
                evidence=[],
            )
            observation["scan"].update(
                status="not_run",
                scan_id=None,
                covered_files=[],
                covered_rules=[],
                skipped_files=[],
                failed_files=[],
            )
        case["correspondence"] = {"status": "not_run", "evidence": []}
        case["lifecycle"] = None
        case["observed_preconditions"] = {
            key: {"status": "not_run", "producer": None, "evidence": []}
            for key in case["observed_preconditions"]
        }
    verdicts = _validate(bundle)
    assert gate.evaluate("baseline", verdicts, [])["passed"]
    assert not gate.evaluate("acceptance", verdicts, [])["passed"]
    assert not any(item.passed for item in verdicts)


def test_should_flip_pair_and_each_language_are_protected(bundle: dict[str, Any]) -> None:
    before = _validate(bundle)
    case = _select(bundle, "python-literal")
    case["after"]["fingerprint"]["hash"] = case["before"]["fingerprint"]["hash"]
    result = gate.evaluate("nonregression", _validate(bundle), [before])
    assert not result["passed"]
    assert "control/python-literal" in result["regressions"]
    assert "cell:python/structural_comparison/flip" in result["regressions"]


def test_evidence_symlinks_and_wrong_lifecycle_links_fail_closed(
    bundle: dict[str, Any],
    tmp_path: Path,
) -> None:
    case = _select(bundle, "java-removal")
    case["lifecycle"]["after_scan_id"] = "unrelated-scan"
    with pytest.raises(gate.ReportError, match="lifecycle does not link"):
        _validate(bundle)
    case["lifecycle"]["after_scan_id"] = case["after"]["scan"]["scan_id"]
    outside = tmp_path / "outside-evidence"
    outside.write_bytes((bundle["root"] / "controlled.json").read_bytes())
    (bundle["root"] / "linked.json").symlink_to(outside)
    case["after"]["evidence"] = [{"path": "linked.json", "sha256": bundle["ref"]["sha256"]}]
    with pytest.raises(gate.ReportError, match="symlink"):
        _validate(bundle)


def test_semantic_policy_change_cannot_reinterpret_protected_passes(
    bundle: dict[str, Any],
) -> None:
    original = copy.deepcopy(bundle["report"])
    before = _validate(bundle)
    assert all(item.passed for item in before)
    original_digest = gate.policy_digest(bundle["policy"])
    bundle["policy"]["history"]["baseline_sha256"] = gate.sha256_bytes(b"controlled history")
    assert gate.policy_digest(bundle["policy"]) == original_digest
    bundle["policy"]["accepted_namespaces"] = ["scanipy-slice-normal-form/3"]
    assert gate.policy_digest(bundle["policy"]) != original_digest
    with pytest.raises(gate.ReportError, match="semantic gate policy digest"):
        _validate(bundle)
    # Re-stamping the new candidate cannot modify the protected report's bytes.
    bundle["report"]["gate_policy_digest"] = gate.policy_digest(bundle["policy"])
    _validate(bundle)
    with pytest.raises(gate.ReportError, match="semantic gate policy digest"):
        gate.validate_report(
            original,
            policy=bundle["policy"],
            cases=bundle["cases"],
            corpus_root=bundle["corpus"],
            evidence_root=bundle["root"],
            now=NOW,
            historical_reference=True,
        )


@pytest.mark.parametrize("coverage", ["covered_files", "covered_rules"])
def test_prior_finding_requires_actual_file_and_rule_coverage(
    bundle: dict[str, Any],
    coverage: str,
) -> None:
    case = _select(bundle, "java-removal")
    case["before"]["scan"][coverage] = []
    assert not next(item for item in _validate(bundle) if item.case_id == case["case_id"]).passed


@pytest.mark.parametrize("status", ["failed", "not_run"])
def test_failed_or_unrun_detection_never_reports_absence(
    bundle: dict[str, Any],
    status: str,
) -> None:
    case = _select(bundle, "java-parse-failure")
    case["after"]["finding"] = {
        "status": "absent",
        "id": None,
        "rule_id": "controlled-rule",
        "origin": None,
    }
    case["after"]["scan"]["status"] = status
    if status == "not_run":
        case["after"]["scan"]["scan_id"] = None
        case["lifecycle"] = None
    with pytest.raises(gate.ReportError, match="requires completed detection"):
        _validate(bundle)


def test_default_g0_runtime_and_complete_attempt_requirement(bundle: dict[str, Any]) -> None:
    # Explicitly restore production execution constraints on the controlled data.
    bundle["policy"]["execution_kinds"] = ["real_joern"]
    bundle["policy"]["baseline_requires_attempts"] = True
    bundle["report"]["gate_policy_digest"] = gate.policy_digest(bundle["policy"])
    assert not gate.evaluate("baseline", _validate(bundle), [])["passed"]
    # A producer claiming real Joern still cannot get G0 for a limited/not-run side.
    bundle["report"]["run"]["execution_kind"] = "real_joern"
    side = _select(bundle)["after"]
    side.update(
        processing_status="not_run",
        reason="limited run",
        fingerprint=None,
        locator={"status": "not_run", "value": None},
        evidence=[],
    )
    result = gate.evaluate("baseline", _validate(bundle), [])
    assert result["valid_report"] and not result["passed"] and not result["baseline_eligible"]


def test_g0_all_attempted_can_remain_missing_full_environment_or_purity(
    bundle: dict[str, Any],
) -> None:
    bundle["policy"]["baseline_requires_attempts"] = True
    bundle["report"]["gate_policy_digest"] = gate.policy_digest(bundle["policy"])
    bundle["report"]["run"]["environment_manifest"] = None
    bundle["report"]["run"]["environment_digest"] = None
    for case in bundle["report"]["cases"]:
        case["observed_preconditions"]["purity_certificate"] = {
            "status": "not_run",
            "producer": None,
            "evidence": [],
        }
    verdicts = _validate(bundle)
    assert gate.evaluate("baseline", verdicts, [])["passed"]
    assert not gate.evaluate("acceptance", verdicts, [])["passed"]


def test_locked_seed_metadata_drift_is_rejected(bundle: dict[str, Any]) -> None:
    root = bundle["corpus"]
    seed = root / "seeds" / "seed-001"
    seed.mkdir(parents=True)
    metadata = seed / "meta.yaml"
    metadata.write_text("controlled: original\n")
    lock = gate._read_lock(root / "corpus.lock")
    lock["seeds"] = [
        {"seed_id": "seed-001", "meta_sha256": gate.sha256_bytes(metadata.read_bytes())}
    ]
    lock["corpus_digest"] = gate.lock_digest(lock)
    (root / "corpus.lock").write_text(yaml.safe_dump(lock))
    bundle["policy"]["corpus"]["corpus_digest"] = lock["corpus_digest"]
    assert len(gate.load_corpus(root, bundle["policy"])) == 10
    metadata.write_text("controlled: changed\n")
    with pytest.raises(gate.ReportError, match="locked metadata changed"):
        gate.load_corpus(root, bundle["policy"])
