"""R04 typed report gate: validate evidence, recompute verdicts, protect history.

No corpus code is imported or executed. Hash/schema consistency cannot authenticate
the producer or prove language semantics; see docs/bhmea/REFACTOR-REPORT-V2.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from collections.abc import Hashable, Sequence

POLICY_ID = "bhmea-refactor-gate/2"
ENVIRONMENT_NAMESPACE = "scanipy-refactor-analysis-environment/1"
TREE_ALGORITHM = "sha256-length-prefixed-path-and-content-v1"
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
REVISION = re.compile(r"[0-9a-f]{40}\Z")
EVIDENCE_TYPES = {"structural_comparison", "finding_removal", "analysis_failure"}
STATUS = {"completed", "failed", "not_run"}
PRECONDITIONS = {
    "fixture_syntax": {"valid", "invalid_after", "failed", "not_run"},
    "transformation_validation": {"valid", "failed", "not_run"},
    "purity_certificate": {"proven", "not_proven", "failed", "not_run"},
}
DEFAULT_POLICY = Path(__file__).resolve().parents[1] / "docs/bhmea/refactor-gate-policy-v2.json"


class ReportError(ValueError):
    """Malformed/stale/incomplete gate input, not an honest semantic failure."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReportError(message)


def _object(value: object, where: str, keys: set[str] | None = None) -> dict[str, Any]:
    _require(isinstance(value, dict), f"{where}: expected object")
    assert isinstance(value, dict)
    _require(all(isinstance(key, str) for key in value), f"{where}: non-string key")
    if keys is not None:
        _require(set(value) == keys, f"{where}: wrong fields (expected {sorted(keys)})")
    return value


def _string(value: object, where: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{where}: expected nonempty string")
    assert isinstance(value, str)
    return value


def _digest(value: object, where: str) -> str:
    text = _string(value, where)
    _require(DIGEST.fullmatch(text) is not None, f"{where}: invalid SHA-256 identity")
    return text


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def lock_digest(lock: dict[str, Any]) -> str:
    return sha256_bytes(
        canonical_json(
            {
                key: value
                for key, value in lock.items()
                if key not in {"corpus_digest", "built_at", "built_by"}
            }
        )
    )


def environment_digest(manifest: dict[str, Any]) -> str:
    return sha256_bytes(b"SCANIPY-REFACTOR-ANALYSIS-ENV/1\n" + canonical_json(manifest))


def policy_digest(policy: dict[str, Any]) -> str:
    """History alone is excluded, avoiding self-reference without mutable semantics."""
    return sha256_bytes(
        b"SCANIPY-REFACTOR-GATE-POLICY/2\n"
        + canonical_json({key: value for key, value in policy.items() if key != "history"})
    )


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ReportError(f"nonfinite JSON constant: {value}")


def read_json(path: Path) -> dict[str, Any]:
    _require(path.is_file() and not path.is_symlink(), f"not a regular JSON file: {path}")
    value = json.loads(
        path.read_bytes(), object_pairs_hook=_unique_object, parse_constant=_constant
    )
    return _object(value, str(path))


class _UniqueSafeLoader(yaml.SafeLoader):
    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Hashable, Any]:
        pairs = [
            (self.construct_object(key, deep), self.construct_object(value, deep))
            for key, value in node.value
        ]
        result: dict[Hashable, Any] = {}
        for key, value in _unique_object(pairs).items():
            result[key] = value
        return result


def _read_lock(path: Path) -> dict[str, Any]:
    loader = _UniqueSafeLoader(path.read_text())
    try:
        return _object(loader.get_single_data(), "corpus lock")
    finally:
        loader.dispose()


def _list(value: object, where: str) -> list[Any]:
    _require(isinstance(value, list), f"{where}: expected list")
    assert isinstance(value, list)
    return value


def _strings(value: object, where: str, *, empty: bool = True) -> list[str]:
    items = [_string(item, where) for item in _list(value, where)]
    _require(len(items) == len(set(items)), f"{where}: duplicate value")
    _require(empty or bool(items), f"{where}: empty inventory")
    return items


def _relative(value: object, where: str) -> str:
    name = _string(value, where)
    path = PurePosixPath(name)
    _require(
        not path.is_absolute()
        and ".." not in path.parts
        and "\\" not in name
        and bool(path.parts)
        and path.as_posix() == name
        and ":" not in name,
        f"{where}: unsafe relative POSIX path",
    )
    return name


def safe_path(root: Path, value: object) -> Path:
    name = _relative(value, "path")
    _require(root.is_dir() and not root.is_symlink(), f"invalid input root: {root}")
    candidate = root
    for part in PurePosixPath(name).parts:
        candidate = candidate / part
        _require(not candidate.is_symlink(), f"symlink forbidden: {candidate}")
    _require(candidate.resolve().is_relative_to(root.resolve()), "path escapes input root")
    return candidate


def tree_digest(root: Path) -> str:
    """Independent implementation of the corpus's exact path/content framing."""
    _require(root.is_dir() and not root.is_symlink(), f"not a regular source tree: {root}")
    entries = list(root.rglob("*"))
    for path in entries:
        _require(not path.is_symlink(), f"source symlink forbidden: {path}")
        _require(path.is_file() or path.is_dir(), f"non-regular source entry: {path}")
    result = hashlib.sha256()
    for path in sorted(
        (path for path in entries if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    ):
        name = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        result.update(len(name).to_bytes(8, "big") + name)
        result.update(len(data).to_bytes(8, "big") + data)
    return "sha256:" + result.hexdigest()


def _index(value: object, where: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in _list(value, where):
        record = _object(item, where)
        case_id = _string(record.get("case_id"), f"{where}.case_id")
        _require(case_id not in result, f"{where}: duplicate case {case_id}")
        result[case_id] = record
    return result


def _cell(case: dict[str, Any]) -> str:
    return "/".join(case[key] for key in ("language", "evidence_type", "expected_outcome"))


def validate_policy(raw: object) -> dict[str, Any]:
    policy = _object(
        raw,
        "policy",
        {
            "schema_version",
            "policy_id",
            "corpus",
            "required_case_ids",
            "required_cells",
            "accepted_namespaces",
            "execution_kinds",
            "freshness",
            "cache_mode",
            "maximum_age_hours",
            "baseline_requires_attempts",
            "environment_namespace",
            "environment_roles",
            "history",
        },
    )
    _require(
        type(policy["schema_version"]) is int and policy["schema_version"] == 2,
        "policy version unsupported",
    )
    _require(policy["policy_id"] == POLICY_ID, "policy identity unsupported")
    _require(type(policy["baseline_requires_attempts"]) is bool, "invalid baseline attempt policy")
    binding = _object(
        policy["corpus"],
        "policy.corpus",
        {"corpus_id", "corpus_version", "corpus_digest", "case_manifest_sha256"},
    )
    for key in ("corpus_id", "corpus_version"):
        _string(binding[key], key)
    for key in ("corpus_digest", "case_manifest_sha256"):
        _digest(binding[key], key)
    _strings(policy["required_case_ids"], "policy cases", empty=False)
    cells = _object(policy["required_cells"], "policy cells")
    _require(bool(cells), "policy cells empty")
    for key, value in cells.items():
        _require(type(value) is int and value > 0, f"policy cell {key}: invalid count")
    for key in ("accepted_namespaces", "execution_kinds", "environment_roles"):
        _strings(policy[key], key, empty=False)
    _require(
        set(policy["execution_kinds"]) <= {"real_joern", "controlled_fixture", "historical"},
        "invalid execution policy",
    )
    _require(
        policy["freshness"] == "fresh" and policy["cache_mode"] == "disabled",
        "acceptance must require fresh uncached execution",
    )
    age = policy["maximum_age_hours"]
    _require(type(age) in (int, float) and math.isfinite(age) and age > 0, "invalid freshness age")
    _require(
        policy["environment_namespace"] == ENVIRONMENT_NAMESPACE, "environment version unsupported"
    )
    history = _object(
        policy["history"], "policy history", {"baseline_sha256", "accepted_improvement_sha256"}
    )
    hashes = _strings(history["accepted_improvement_sha256"], "accepted improvement hashes")
    if history["baseline_sha256"] is not None:
        _digest(history["baseline_sha256"], "baseline hash")
        _require(history["baseline_sha256"] not in hashes, "baseline repeated as improvement")
    for digest in hashes:
        _digest(digest, "improvement hash")
    return policy


def _locator(value: object, where: str) -> dict[str, Any]:
    locator = _object(value, where, {"file", "line", "column", "callee", "call_text"})
    _relative(locator["file"], where)
    for key in ("line", "column"):
        _require(type(locator[key]) is int and locator[key] > 0, f"{where}: invalid {key}")
    _string(locator["callee"], where)
    _string(locator["call_text"], where)
    return locator


def load_corpus(root: Path, policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    manifest_path = safe_path(root, "case-manifest.json")
    manifest = read_json(manifest_path)
    _object(
        manifest,
        "case manifest",
        {
            "schema_version",
            "corpus_id",
            "corpus_version",
            "path_base",
            "tree_digest_algorithm",
            "case_count",
            "cases",
        },
    )
    _require(
        type(manifest["schema_version"]) is int and manifest["schema_version"] == 2,
        "manifest version unsupported",
    )
    _require(
        manifest["path_base"] == "corpus_root"
        and manifest["tree_digest_algorithm"] == TREE_ALGORITHM,
        "manifest path/digest contract unsupported",
    )
    lock_path = safe_path(root, "corpus.lock")
    _require(lock_path.is_file(), "missing corpus lock")
    lock = _read_lock(lock_path)
    binding = policy["corpus"]
    for key in ("corpus_id", "corpus_version"):
        _require(lock.get(key) == manifest[key] == binding[key], f"stale corpus {key}")
    manifest_hash = sha256_bytes(manifest_path.read_bytes())
    _require(
        manifest_hash == lock.get("case_manifest_sha256") == binding["case_manifest_sha256"],
        "stale case manifest digest",
    )
    _require(
        lock_digest(lock) == lock.get("corpus_digest") == binding["corpus_digest"],
        "stale corpus digest",
    )
    _require(
        lock.get("tree_digest_algorithm") == TREE_ALGORITHM, "lock digest algorithm unsupported"
    )
    cases = _index(manifest["cases"], "case manifest")
    _require(
        type(manifest["case_count"]) is int
        and manifest["case_count"] == len(cases) == lock.get("case_count"),
        "manifest/lock case count mismatch",
    )
    _require(
        set(cases) == set(policy["required_case_ids"]), "policy/manifest case inventory mismatch"
    )
    # Locked annotation metadata is part of the claimed corpus identity too.
    for raw_seed in _list(lock.get("seeds", []), "locked seeds"):
        seed = _object(raw_seed, "locked seed")
        seed_id = _string(seed.get("seed_id"), "seed ID")
        meta = safe_path(root, f"seeds/{seed_id}/meta.yaml")
        _require(meta.is_file(), f"{seed_id}: locked metadata absent")
        _require(
            sha256_bytes(meta.read_bytes()) == _digest(seed.get("meta_sha256"), seed_id),
            f"{seed_id}: locked metadata changed",
        )
    cache: dict[Path, str] = {}
    for identifier, case in cases.items():
        _object(
            case,
            identifier,
            {
                "case_id",
                "seed_id",
                "language",
                "finding_class",
                "refactor",
                "ground_truth_label",
                "evidence_type",
                "expected_outcome",
                "required_strength",
                "before_dir",
                "after_dir",
                "before_locator",
                "after_locator",
                "expected_preconditions",
                "rationale",
                "observation_subject",
                "expected_failure",
                "before_tree_digest",
                "after_tree_digest",
            },
        )
        _require(
            case["language"] in {"java", "python"} and case["evidence_type"] in EVIDENCE_TYPES,
            f"{identifier}: invalid language/evidence type",
        )
        expected = _object(case["expected_preconditions"], identifier)
        _require(
            {"fixture_syntax", "transformation_validation"} <= set(expected) <= set(PRECONDITIONS),
            f"{identifier}: invalid preconditions",
        )
        for key, value in expected.items():
            _require(
                value in PRECONDITIONS[key] - {"failed", "not_run"},
                f"{identifier}: invalid demanded precondition",
            )
        kind = case["evidence_type"]
        if kind == "structural_comparison":
            _require(
                case["expected_outcome"] in {"stay", "flip"}
                and case["required_strength"] == "strong_strong"
                and case["after_locator"] is not None
                and case["expected_failure"] is None,
                f"{identifier}: invalid structural contract",
            )
        else:
            outcome = "absent" if kind == "finding_removal" else "failure"
            _require(
                case["expected_outcome"] == outcome
                and case["required_strength"] is None
                and case["after_locator"] is None,
                f"{identifier}: invalid typed evidence contract",
            )
            if kind == "analysis_failure":
                _require(
                    case["expected_failure"]
                    == {"stage": "parse", "visible": True, "must_not_resolve": True},
                    f"{identifier}: invalid intentional failure",
                )
        for side in ("before", "after"):
            source = safe_path(root, case[f"{side}_dir"])
            if source not in cache:
                cache[source] = tree_digest(source)
            _require(
                cache[source] == _digest(case[f"{side}_tree_digest"], identifier),
                f"{identifier}/{side}: source tree changed",
            )
            if case[f"{side}_locator"] is not None:
                locator = _locator(case[f"{side}_locator"], identifier)
                _require(
                    safe_path(source, locator["file"]).is_file(),
                    f"{identifier}: locator file absent",
                )
    _require(
        dict(Counter(_cell(case) for case in cases.values())) == policy["required_cells"],
        "policy language/evidence/outcome denominator mismatch",
    )
    return cases


def _evidence(value: object, root: Path, where: str) -> list[dict[str, Any]]:
    references = []
    seen = set()
    for raw in _list(value, where):
        ref = _object(raw, where, {"path", "sha256"})
        path = safe_path(root, ref["path"])
        _require(path.is_file(), f"{where}: evidence file missing")
        _require(path not in seen, f"{where}: duplicate evidence reference")
        seen.add(path)
        _require(
            sha256_bytes(path.read_bytes()) == _digest(ref["sha256"], where),
            f"{where}: evidence digest mismatch",
        )
        references.append(ref)
    return references


def _timestamp(value: object, where: str) -> datetime:
    text = _string(value, where)
    _require(text.endswith("Z"), f"{where}: expected UTC timestamp ending Z")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    _require(parsed.tzinfo == UTC, f"{where}: expected UTC timestamp")
    return parsed


def _run(
    value: object, root: Path, policy: dict[str, Any], now: datetime, *, historical_reference: bool
) -> tuple[bool, bool]:
    run = _object(
        value,
        "run",
        {
            "code_revision",
            "started_at",
            "completed_at",
            "execution_kind",
            "freshness",
            "cache_mode",
            "command",
            "environment_digest",
            "environment_manifest",
        },
    )
    _require(
        REVISION.fullmatch(_string(run["code_revision"], "revision")) is not None,
        "invalid full code revision",
    )
    started, completed = (_timestamp(run[key], key) for key in ("started_at", "completed_at"))
    _require(started <= completed <= now, "invalid run timestamp order/future timestamp")
    command = _list(run["command"], "command")
    _require(bool(command), "empty command")
    for arg in command:
        _string(arg, "command argument")
    _require(
        run["execution_kind"] in {"real_joern", "controlled_fixture", "historical"},
        "invalid execution kind",
    )
    _require(
        run["freshness"] in {"fresh", "reused"} and run["cache_mode"] in {"disabled", "enabled"},
        "invalid cache/freshness status",
    )
    allowed = (
        run["execution_kind"] in policy["execution_kinds"]
        and run["freshness"] == policy["freshness"]
        and run["cache_mode"] == policy["cache_mode"]
        and (
            historical_reference
            or (now - completed).total_seconds() <= policy["maximum_age_hours"] * 3600
        )
    )
    if run["environment_manifest"] is None:
        _require(run["environment_digest"] is None, "environment digest without manifest")
        return allowed, False
    ref = _evidence([run["environment_manifest"]], root, "environment manifest")[0]
    manifest = read_json(safe_path(root, ref["path"]))
    _object(manifest, "environment", {"namespace", "code_revision", "components", "configuration"})
    _require(
        manifest["namespace"] == policy["environment_namespace"]
        and manifest["code_revision"] == run["code_revision"],
        "environment version/revision mismatch",
    )
    roles = set()
    for raw in _list(manifest["components"], "environment components"):
        component = _object(raw, "component", {"role", "name", "version", "digest"})
        role = _string(component["role"], "component role")
        _require(role not in roles, "duplicate environment role")
        roles.add(role)
        _string(component["name"], "component name")
        _string(component["version"], "component version")
        _digest(component["digest"], "component digest")
    configuration = _object(manifest["configuration"], "environment configuration")
    _require(
        environment_digest(manifest) == _digest(run["environment_digest"], "environment_digest"),
        "full environment digest mismatch",
    )
    return allowed, set(policy["environment_roles"]) <= roles and bool(configuration)


def _side(value: object, expected: dict[str, Any], side: str, root: Path) -> dict[str, Any]:
    where = f"{expected['case_id']}/{side}"
    record = _object(
        value,
        where,
        {
            "source_tree_digest",
            "processing_status",
            "reason",
            "fingerprint",
            "locator",
            "finding",
            "scan",
            "error",
            "evidence",
        },
    )
    _require(
        _digest(record["source_tree_digest"], where) == expected[f"{side}_tree_digest"],
        f"{where}: stale source identity",
    )
    _require(record["processing_status"] in STATUS, f"{where}: invalid processing status")
    if record["reason"] is not None:
        _string(record["reason"], where)
    _require(
        record["processing_status"] == "completed" or record["reason"] is not None,
        f"{where}: missing incomplete reason",
    )
    locator = _object(record["locator"], where, {"status", "value"})
    _require(
        locator["status"] in {"matched", "not_found", "ambiguous", "not_run"},
        f"{where}: locator status invalid",
    )
    if locator["status"] == "matched":
        _locator(locator["value"], where)
        _require(
            locator["value"] == expected[f"{side}_locator"], f"{where}: wrong sink correspondence"
        )
    else:
        _require(locator["value"] is None, f"{where}: unmatched locator has value")
    fingerprint = record["fingerprint"]
    if fingerprint is not None:
        _object(fingerprint, where, {"hash", "class", "namespace"})
        _digest(fingerprint["hash"], where)
        _require(fingerprint["class"] in {"strong", "weak"}, f"{where}: invalid fingerprint class")
        _string(fingerprint["namespace"], where)
        _require(
            record["processing_status"] == "completed" and locator["status"] == "matched",
            f"{where}: fingerprint without completed/matched computation",
        )
    finding = _object(record["finding"], where, {"status", "id", "rule_id", "origin"})
    _require(
        finding["status"] in {"present", "absent", "not_run"}, f"{where}: finding status invalid"
    )
    if finding["status"] == "present":
        _string(finding["id"], where)
        _string(finding["rule_id"], where)
        _require(
            finding["origin"] in {"deterministic-core", "oracle-passthrough"},
            f"{where}: invalid finding origin",
        )
    else:
        _require(
            finding["id"] is None and finding["origin"] is None,
            f"{where}: absent/not-run finding has identity",
        )
        if finding["rule_id"] is not None:
            _string(finding["rule_id"], where)
    scan = _object(
        record["scan"],
        where,
        {
            "status",
            "scan_id",
            "source_tree_digest",
            "covered_files",
            "covered_rules",
            "skipped_files",
            "failed_files",
        },
    )
    _require(scan["status"] in STATUS, f"{where}: scan status invalid")
    _require(
        scan["source_tree_digest"] == record["source_tree_digest"], f"{where}: scan source mismatch"
    )
    if scan["status"] == "not_run":
        _require(scan["scan_id"] is None, f"{where}: unrun scan has ID")
    else:
        _string(scan["scan_id"], where)
    for key in ("covered_files", "covered_rules", "skipped_files", "failed_files"):
        for name in _strings(scan[key], f"{where}/{key}"):
            if key != "covered_rules":
                _relative(name, where)
    if finding["status"] in {"present", "absent"}:
        _require(
            scan["status"] == record["processing_status"] == "completed",
            f"{where}: finding presence/absence requires completed detection",
        )
    if record["error"] is not None:
        error = _object(record["error"], where, {"stage", "visible"})
        _require(
            error["stage"] in {"parse", "locate", "fingerprint", "detect", "timeout"}
            and type(error["visible"]) is bool,
            f"{where}: invalid error observation",
        )
        _require(record["processing_status"] == "failed", f"{where}: error on non-failed side")
    _evidence(record["evidence"], root, where)
    if (
        fingerprint is not None
        or finding["status"] != "not_run"
        or scan["status"] != "not_run"
        or record["error"] is not None
    ):
        _require(bool(record["evidence"]), f"{where}: observation without evidence")
    return record


@dataclass(frozen=True)
class CaseVerdict:
    case_id: str
    language: str
    evidence_type: str
    expected_outcome: str
    passed: bool
    reason: str
    baseline_eligible: bool
    structural_outcome: str | None = None


def _case(
    record: dict[str, Any],
    expected: dict[str, Any],
    root: Path,
    corpus_root: Path,
    policy: dict[str, Any],
    run_eligible: bool,
    baseline_run_eligible: bool,
) -> CaseVerdict:
    identifier = expected["case_id"]
    _object(
        record,
        identifier,
        {
            "case_id",
            "language",
            "evidence_type",
            "before",
            "after",
            "correspondence",
            "observed_preconditions",
            "lifecycle",
        },
    )
    for key in ("language", "evidence_type"):
        _require(record[key] == expected[key], f"{identifier}: retyped case {key}")
    before, after = (_side(record[side], expected, side, root) for side in ("before", "after"))
    observed = _object(
        record["observed_preconditions"], identifier, set(expected["expected_preconditions"])
    )
    preconditions_ok = True
    for key, demand in expected["expected_preconditions"].items():
        observation = _object(observed[key], identifier, {"status", "producer", "evidence"})
        _require(
            observation["status"] in PRECONDITIONS[key], f"{identifier}: invalid observed {key}"
        )
        _evidence(observation["evidence"], root, identifier)
        if observation["status"] == "not_run":
            _require(
                observation["producer"] is None and not observation["evidence"],
                f"{identifier}: unrun precondition has invented producer/evidence",
            )
        else:
            _string(observation["producer"], identifier)
            _require(
                bool(observation["evidence"]),
                f"{identifier}: observed precondition missing evidence",
            )
        preconditions_ok &= observation["status"] == demand
    correspondence = _object(record["correspondence"], identifier, {"status", "evidence"})
    _require(
        correspondence["status"] in {"established", "ambiguous", "not_run"},
        f"{identifier}: invalid correspondence",
    )
    _evidence(correspondence["evidence"], root, identifier)
    if correspondence["status"] == "established":
        _require(bool(correspondence["evidence"]), f"{identifier}: correspondence without evidence")
    lifecycle = record["lifecycle"]
    if lifecycle is not None:
        _object(
            lifecycle,
            identifier,
            {
                "before_finding_id",
                "after_scan_id",
                "state",
                "reason",
                "decision_inherited",
                "evidence",
            },
        )
        _string(lifecycle["before_finding_id"], identifier)
        _string(lifecycle["after_scan_id"], identifier)
        _require(
            lifecycle["state"] in {"resolved", "open"}
            and lifecycle["reason"] in {"fixed", "analysis_failed"}
            and type(lifecycle["decision_inherited"]) is bool,
            f"{identifier}: invalid lifecycle",
        )
        _evidence(lifecycle["evidence"], root, identifier)
        _require(bool(lifecycle["evidence"]), f"{identifier}: lifecycle without retained evidence")
        _require(
            lifecycle["before_finding_id"] == before["finding"]["id"]
            and lifecycle["after_scan_id"] == after["scan"]["scan_id"],
            f"{identifier}: lifecycle does not link actual observations",
        )
    outcome = None
    passed = False
    reason = "incomplete-or-contrary-typed-evidence"
    if expected["evidence_type"] == "structural_comparison":
        left, right = before["fingerprint"], after["fingerprint"]
        if left is not None and right is not None:
            compatible = (
                left["class"] == right["class"] == "strong"
                and left["namespace"] == right["namespace"]
                and left["namespace"] in policy["accepted_namespaces"]
            )
            if compatible:
                outcome = "stay" if left["hash"] == right["hash"] else "flip"
                passed = (
                    outcome == expected["expected_outcome"]
                    and correspondence["status"] == "established"
                )
            else:
                reason = "weak-or-incompatible-identity"
        else:
            reason = "missing-computed-fingerprint"
    else:
        previous = (
            before["processing_status"] == "completed"
            and before["finding"]["status"] == "present"
            and before["scan"]["status"] == "completed"
            and before["locator"]["status"] == "matched"
            and expected["before_locator"]["file"] in before["scan"]["covered_files"]
            and before["finding"]["rule_id"] in before["scan"]["covered_rules"]
            and expected["before_locator"]["file"] not in before["scan"]["skipped_files"]
            and expected["before_locator"]["file"] not in before["scan"]["failed_files"]
        )
        linked = previous and lifecycle is not None
        if expected["evidence_type"] == "finding_removal":
            source = safe_path(corpus_root, expected["after_dir"])
            files = {
                path.relative_to(source).as_posix() for path in source.rglob("*") if path.is_file()
            }
            coverage = (
                after["scan"]["status"] == "completed"
                and set(after["scan"]["covered_files"]) == files
                and before["finding"]["rule_id"] in after["scan"]["covered_rules"]
                and not after["scan"]["skipped_files"]
                and not after["scan"]["failed_files"]
            )
            passed = (
                linked
                and coverage
                and after["processing_status"] == "completed"
                and after["finding"]["status"] == "absent"
                and after["finding"]["rule_id"] == before["finding"]["rule_id"]
                and lifecycle["state"] == "resolved"
                and lifecycle["reason"] == "fixed"
                and not lifecycle["decision_inherited"]
            )
        else:
            passed = (
                linked
                and after["processing_status"] == "failed"
                and after["scan"]["status"] == "failed"
                and after["error"] == {"stage": "parse", "visible": True}
                and lifecycle["state"] == "open"
                and lifecycle["reason"] == "analysis_failed"
                and not lifecycle["decision_inherited"]
            )
    if not preconditions_ok:
        passed, reason = False, "required-preconditions-not-observed"
    if not run_eligible:
        passed, reason = False, "run-environment-or-freshness-not-eligible"
    attempted = all(
        side["processing_status"] in {"completed", "failed"} and bool(side["evidence"])
        for side in (before, after)
    )
    return CaseVerdict(
        identifier,
        expected["language"],
        expected["evidence_type"],
        expected["expected_outcome"],
        bool(passed),
        "pass" if passed else reason,
        baseline_run_eligible and (attempted or not policy["baseline_requires_attempts"]),
        outcome,
    )


def validate_report(
    raw: object,
    *,
    policy: dict[str, Any],
    cases: dict[str, dict[str, Any]],
    corpus_root: Path,
    evidence_root: Path,
    now: datetime | None = None,
    historical_reference: bool = False,
) -> list[CaseVerdict]:
    report = _object(raw, "report")
    _require(
        set(report) - {"summary"}
        == {
            "schema_version",
            "gate_policy_id",
            "gate_policy_digest",
            "report_id",
            "corpus",
            "run",
            "cases",
        },
        "report fields invalid",
    )
    _require(
        type(report["schema_version"]) is int and report["schema_version"] == 2,
        "report schema unsupported; historical reports cannot be relabeled",
    )
    _require(report["gate_policy_id"] == policy["policy_id"], "report gate policy mismatch")
    _require(
        report["gate_policy_digest"] == policy_digest(policy),
        "report semantic gate policy digest mismatch",
    )
    _string(report["report_id"], "report ID")
    _require(report["corpus"] == policy["corpus"], "report corpus binding mismatch")
    indexed = _index(report["cases"], "report cases")
    _require(set(indexed) == set(cases), "report has missing/extra required cases")
    run_eligible, environment_eligible = _run(
        report["run"],
        evidence_root,
        policy,
        now or datetime.now(UTC),
        historical_reference=historical_reference,
    )
    return [
        _case(
            indexed[key],
            cases[key],
            evidence_root,
            corpus_root,
            policy,
            run_eligible and environment_eligible,
            run_eligible,
        )
        for key in sorted(cases)
    ]


def evaluate(
    mode: str, current: list[CaseVerdict], references: list[list[CaseVerdict]]
) -> dict[str, Any]:
    _require(mode in {"baseline", "acceptance", "nonregression"}, "unknown gate mode")
    current_index = {item.case_id: item for item in current}
    _require(bool(current) and len(current_index) == len(current), "invalid verdict inventory")
    regressions: set[str] = set()
    for reference in references:
        _require(
            {item.case_id for item in reference} == set(current_index), "history inventory differs"
        )
        regressions.update(
            item.case_id
            for item in reference
            if item.passed and not current_index[item.case_id].passed
        )
    cells: dict[str, dict[str, int]] = {}
    for item in current:
        cell = "/".join((item.language, item.evidence_type, item.expected_outcome))
        count = cells.setdefault(cell, {"required": 0, "passed": 0})
        count["required"] += 1
        count["passed"] += int(item.passed)
    for reference in references:
        old_counts = Counter(
            "/".join((item.language, item.evidence_type, item.expected_outcome))
            for item in reference
            if item.passed
        )
        for cell, old_count in old_counts.items():
            _require(cell in cells, "history language/evidence cell removed")
            if cells[cell]["passed"] < old_count:
                regressions.add(f"cell:{cell}")
    all_passed = all(item.passed for item in current)
    baseline_eligible = all(item.baseline_eligible for item in current)
    passed = baseline_eligible and (
        mode == "baseline" or (not regressions and (mode == "nonregression" or all_passed))
    )
    return {
        "schema_version": 2,
        "mode": mode,
        "valid_report": True,
        "baseline_eligible": baseline_eligible,
        "passed": passed,
        "feature_acceptance": mode == "acceptance" and passed,
        "required_cases": len(current),
        "passing_cases": sum(item.passed for item in current),
        "cells": cells,
        "regressions": sorted(regressions),
        "cases": [asdict(item) for item in current],
        "evidence_boundary": (
            "Consistency checks do not authenticate producers or prove program semantics."
        ),
    }


def check_files(
    *,
    report: Path,
    corpus_root: Path,
    policy_path: Path = DEFAULT_POLICY,
    mode: str = "baseline",
    evidence_root: Path | None = None,
    baseline: Path | None = None,
    accepted_improvements: Sequence[Path] = (),
    now: datetime | None = None,
) -> dict[str, Any]:
    policy = validate_policy(read_json(policy_path))
    cases = load_corpus(corpus_root, policy)
    current = validate_report(
        read_json(report),
        policy=policy,
        cases=cases,
        corpus_root=corpus_root,
        evidence_root=evidence_root or report.parent,
        now=now,
    )
    references = []
    if mode != "baseline":
        history = policy["history"]
        _require(
            baseline is not None and history["baseline_sha256"] is not None,
            "reviewed G0 baseline not pinned/supplied",
        )
        assert baseline is not None
        _require(
            sha256_bytes(baseline.read_bytes()) == history["baseline_sha256"],
            "baseline report digest mismatch",
        )
        hashes = [sha256_bytes(path.read_bytes()) for path in accepted_improvements]
        _require(
            len(hashes) == len(set(hashes))
            and set(hashes) == set(history["accepted_improvement_sha256"]),
            "accepted improvement history missing/extra/stale",
        )
        for path in (baseline, *accepted_improvements):
            protected = validate_report(
                read_json(path),
                policy=policy,
                cases=cases,
                corpus_root=corpus_root,
                evidence_root=path.parent,
                now=now,
                historical_reference=True,
            )
            _require(
                all(item.baseline_eligible for item in protected),
                "protected history fails G0 eligibility",
            )
            references.append(protected)
    else:
        _require(
            baseline is None and not accepted_improvements,
            "baseline mode does not consume protected history",
        )
    return evaluate(mode, current, references)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("baseline", "acceptance", "nonregression"), required=True
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--accepted-improvement", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    try:
        result = check_files(
            report=args.report,
            corpus_root=args.corpus_root,
            policy_path=args.policy,
            mode=args.mode,
            evidence_root=args.evidence_root,
            baseline=args.baseline,
            accepted_improvements=args.accepted_improvement,
        )
    except (ReportError, OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as exc:
        print(
            json.dumps(
                {"schema_version": 2, "valid_report": False, "passed": False, "error": str(exc)},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
