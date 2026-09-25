"""Check the BHMEA planning ledger, not the truth of feature-acceptance evidence.

This stdlib-only check rejects missing/duplicate claims, broken milestone edges,
cycles, optional work blocking G0, and unsupported completion assertions. Actual
semantic report acceptance is a different R04 tool.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

TASK_IDS = {f"R{number:02d}" for number in range(1, 21)}
CLAIM_IDS = {f"C{number:02d}" for number in range(1, 19)}
GATE_IDS = {"G0", "G1", "G2", "G3_RELEASE", "G3_STAGE"}
MIN_GATE_DEPENDENCIES = {
    "G1": {
        "R08.implementation_ready",
        "R09.component_verified",
        "R10.implementation_ready",
        "R11.implementation_ready",
        "R12.implementation_ready",
        "R16.design_ready",
        "R18.component_verified",
        "R19.component_verified",
        "R20.component_verified",
    },
    "G2": {"G0", "G1"}
    | {
        f"R{number:02d}.component_verified"
        for number in (6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 18, 19, 20)
    },
    "G3_RELEASE": {"G2", "R15.install_verified"},
    "G3_STAGE": {"G2", "R15.stage_verified"},
}
MIN_GATE_SCOPE = {
    "G0": {"complete_corrected_corpus", "honest_baseline_not_feature_acceptance"},
    "G1": {"declared_real_nonempty_core", "semgrep", "persistent_provenance_fresh_verification"},
    "G2": {"all_claims", "java", "python", "semgrep", "codeql", "real_comparators"},
    "G3_RELEASE": {"clean_install", "public_source_license_evidence", "authorized_release"},
    "G3_STAGE": {"actual_stage_hardware", "offline_twice", "same_accepted_artifact_fallback"},
}
TASK_STATUSES = {"TODO", "IN_PROGRESS", "BLOCKED", "DONE"}
GATE_STATUSES = {"NOT_RUN", "PASS", "FAIL", "BLOCKED"}
CLAIM_STATUSES = {"UNVERIFIED", "PARTIAL", "FULFILLED", "UNFULFILLED"}


class LedgerError(ValueError):
    """The ledger cannot support its own structural/status assertions."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise LedgerError(message)


def _object(value: object, where: str) -> dict[str, Any]:
    _require(isinstance(value, dict), f"{where}: expected object")
    assert isinstance(value, dict)
    return value


def _strings(value: object, where: str, *, nonempty: bool = False) -> list[str]:
    _require(isinstance(value, list), f"{where}: expected list")
    assert isinstance(value, list)
    _require(all(isinstance(item, str) and item for item in value), f"{where}: invalid string")
    _require(len(value) == len(set(value)), f"{where}: duplicate value")
    _require(not nonempty or bool(value), f"{where}: cannot be empty")
    return value


def _index(value: object, where: str) -> dict[str, dict[str, Any]]:
    _require(isinstance(value, list), f"{where}: expected list")
    assert isinstance(value, list)
    result: dict[str, dict[str, Any]] = {}
    for raw in value:
        item = _object(raw, where)
        identifier = item.get("id")
        _require(isinstance(identifier, str) and bool(identifier), f"{where}: missing id")
        assert isinstance(identifier, str)
        _require(identifier not in result, f"{where}: duplicate id {identifier}")
        result[identifier] = item
    return result


def _evidence(item: dict[str, Any], where: str, root: Path | None, *, required: bool) -> None:
    paths = _strings(item.get("evidence_paths"), f"{where}.evidence_paths", nonempty=required)
    for raw_path in paths:
        path = Path(raw_path)
        _require(
            not path.is_absolute() and ".." not in path.parts, f"{where}: unsafe evidence path"
        )
        if root is not None:
            resolved = (root / path).resolve()
            _require(
                resolved.is_relative_to(root.resolve()), f"{where}: evidence leaves repository"
            )
            _require(resolved.is_file(), f"{where}: missing evidence {path}")


def validate_state(raw: object, *, repo_root: Path | None = None) -> list[str]:
    """Return topological milestone order, or raise LedgerError on invalid state.

    Paths are checked when repo_root is supplied. A valid ledger is not evidence
    that the files it references prove any technical or public claim.
    """
    state = _object(raw, "ledger")
    _require(
        type(state.get("schema_version")) is int and state["schema_version"] == 1,
        "unsupported ledger schema_version",
    )
    _require(state.get("target_mode") == "FULL_SUBMISSION", "scope reduction needs a new contract")
    tasks = _index(state.get("tasks"), "tasks")
    claims = _index(state.get("claims"), "claims")
    milestones = _index(state.get("milestones"), "milestones")
    gates = _index(state.get("gates"), "gates")
    _require(set(tasks) == TASK_IDS, "tasks must contain exactly R01-R20")
    _require(set(claims) == CLAIM_IDS, "claims must contain exactly C01-C18")
    _require(set(gates) == GATE_IDS, "shared gate inventory mismatch")
    _require(not set(milestones) & set(gates), "milestone/gate identifiers overlap")
    for identifier, gate_record in gates.items():
        gate_dependencies = set(_strings(gate_record.get("requires"), identifier))
        gate_scope = set(_strings(gate_record.get("scope"), identifier))
        _require(
            MIN_GATE_DEPENDENCIES.get(identifier, set()) <= gate_dependencies,
            f"{identifier}: required gate prerequisites removed",
        )
        _require(MIN_GATE_SCOPE[identifier] <= gate_scope, f"{identifier}: gate scope reduced")

    for identifier, task in tasks.items():
        _require(task.get("status") in TASK_STATUSES, f"{identifier}: unknown status")
        _require(bool(task.get("owner")), f"{identifier}: owner missing")
        _require(bool(task.get("next_action")), f"{identifier}: next action missing")
        _require(task.get("acceptance_section") == identifier, f"{identifier}: acceptance mismatch")
        kinds = _strings(task.get("requirement_kinds"), identifier, nonempty=True)
        _require(
            set(kinds)
            <= {
                "submission_requirement",
                "correctness_prerequisite",
                "release_stage_requirement",
                "optional_efficiency",
            },
            f"{identifier}: unknown requirement kind",
        )
        for phase in ("design_ready", "component_verified"):
            _require(f"{identifier}.{phase}" in milestones, f"{identifier}: missing {phase}")
        _evidence(task, identifier, repo_root, required=task["status"] == "DONE")

    for identifier, claim in claims.items():
        status = claim.get("original_submission_status")
        _require(status in CLAIM_STATUSES, f"{identifier}: unknown status")
        _require(
            claim.get("included_in_current_public_scope") is True,
            f"{identifier}: cannot silently drop submitted scope",
        )
        required = _strings(claim.get("required_tasks"), identifier, nonempty=True)
        _require(set(required) <= set(tasks), f"{identifier}: unknown task")
        _require(
            bool(claim.get("owner")) and bool(claim.get("acceptance_criterion")),
            f"{identifier}: missing owner or acceptance criterion",
        )
        _strings(claim.get("implementation_targets"), identifier, nonempty=True)
        _evidence(claim, identifier, repo_root, required=status == "FULFILLED")
        if status == "FULFILLED":
            _require(gates["G2"]["status"] == "PASS", f"{identifier}: G2 not passed")
            if identifier in {"C12", "C17", "C18"}:
                _require(
                    gates["G3_RELEASE"]["status"] == "PASS",
                    f"{identifier}: release evidence missing",
                )

    nodes = {**milestones, **gates}
    for identifier, node in nodes.items():
        is_gate = identifier in gates
        _require(
            node.get("status") in (GATE_STATUSES if is_gate else TASK_STATUSES),
            f"{identifier}: unknown status",
        )
        dependencies = _strings(node.get("requires"), f"{identifier}.requires")
        _require(set(dependencies) <= set(nodes), f"{identifier}: unknown dependency")
        _require(identifier not in dependencies, f"{identifier}: self dependency")
        if not is_gate:
            _require(identifier.split(".")[0] in tasks, f"{identifier}: unknown owning task")
            _require(type(node.get("optional")) is bool, f"{identifier}: missing optional flag")
            scope = _strings(node.get("required_scope"), identifier, nonempty=True)
            verified = _strings(node.get("verified_scope"), f"{identifier}.verified_scope")
            if node["status"] == "DONE":
                _require(set(scope) <= set(verified), f"{identifier}: verification scope reduced")
        else:
            _strings(node.get("scope"), identifier, nonempty=True)
        complete = node["status"] == ("PASS" if is_gate else "DONE")
        _evidence(node, identifier, repo_root, required=complete)
        if complete:
            for dependency in dependencies:
                expected = "PASS" if dependency in gates else "DONE"
                _require(
                    nodes[dependency]["status"] == expected,
                    f"{identifier}: incomplete dependency {dependency}",
                )

    visited: set[str] = set()
    visiting: set[str] = set()
    ordered: list[str] = []

    def visit(identifier: str) -> None:
        _require(identifier not in visiting, f"cycle at {identifier}")
        if identifier in visited:
            return
        visiting.add(identifier)
        for dependency in nodes[identifier]["requires"]:
            visit(dependency)
        visiting.remove(identifier)
        visited.add(identifier)
        ordered.append(identifier)

    for identifier in sorted(nodes):
        visit(identifier)

    def ancestors(identifier: str) -> set[str]:
        found: set[str] = set()
        pending = list(nodes[identifier]["requires"])
        while pending:
            dependency = pending.pop()
            if dependency not in found:
                found.add(dependency)
                pending.extend(nodes[dependency]["requires"])
        return found

    _require(
        set(gates["G0"]["requires"])
        == {"R03.component_verified", "R04.component_verified", "R05.commands_verified"},
        "G0 needs corrected corpus, checker and commands only",
    )
    _require(
        not any(nodes[item].get("optional", False) for item in ancestors("G0")),
        "optional work cannot block G0",
    )
    _require("G0" not in ancestors("R03.component_verified"), "corpus cannot depend on baseline")
    _require(
        "R13.component_verified" in ancestors("R11.component_verified"),
        "CodeQL measurement requires verified adapter",
    )
    _require(
        "R11.component_verified" not in ancestors("R13.component_verified"),
        "CodeQL adapter cannot depend on its final rate measurement",
    )
    _require("R06.component_verified" not in ancestors("G1"), "early G1 cannot await all refactors")

    for identifier, task in tasks.items():
        if task["status"] == "DONE":
            for milestone_id, milestone in milestones.items():
                if milestone_id.startswith(identifier + ".") and not milestone["optional"]:
                    _require(milestone["status"] == "DONE", f"{identifier}: incomplete milestone")
    _require(state.get("submission_fulfillment") in CLAIM_STATUSES, "unknown submission status")
    if state.get("submission_fulfillment") == "FULFILLED":
        _require(
            all(c["original_submission_status"] == "FULFILLED" for c in claims.values()),
            "full submission needs every claim",
        )
    for field, gate in (("release_readiness", "G3_RELEASE"), ("stage_readiness", "G3_STAGE")):
        _require(state.get(field) in {"NOT_VERIFIED", "READY"}, f"{field}: unknown readiness")
        if state[field] == "READY":
            _require(gates[gate]["status"] == "PASS", f"{field}: gate not passed")
    return ordered


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON key {key}")
        result[key] = value
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        raw = json.loads(args.ledger.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        ordered = validate_state(raw, repo_root=args.repo_root)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"INVALID ledger: {exc}", file=sys.stderr)
        return 1
    print(f"VALID planning ledger: 20 tasks, 18 claims, {len(ordered)} acyclic milestones/gates.")
    print("This is not feature, release, stage, or evidence-authenticity acceptance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
