"""Controlled ledger mutations; these are not feature-acceptance tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.check_bhmea_execution_state import LedgerError, main, validate_state

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def state():
    return json.loads((ROOT / "docs/bhmea/execution-state.json").read_text(encoding="utf-8"))


def node(state, identifier):
    return next(item for item in state["milestones"] + state["gates"] if item["id"] == identifier)


def test_actual_ledger_has_complete_acyclic_inventory(state):
    order = validate_state(state, repo_root=ROOT)
    assert len(order) == 85
    assert order.index("R13.component_verified") < order.index("R11.component_verified")
    assert order.index("G2") < order.index("G3_STAGE")


@pytest.mark.parametrize("collection", ["tasks", "claims", "milestones", "gates"])
def test_duplicate_ids_rejected(state, collection):
    state[collection].append(state[collection][0])
    with pytest.raises(LedgerError, match="duplicate id"):
        validate_state(state)


@pytest.mark.parametrize("collection", ["tasks", "claims", "gates"])
def test_missing_required_inventory_rejected(state, collection):
    state[collection].pop()
    with pytest.raises(LedgerError):
        validate_state(state)


def test_cycle_rejected(state):
    node(state, "R01.design_ready")["requires"] = ["R02.design_ready"]
    with pytest.raises(LedgerError, match="cycle"):
        validate_state(state)


def test_missing_dependency_rejected(state):
    node(state, "G1")["requires"].append("R99.component_verified")
    with pytest.raises(LedgerError, match="unknown dependency"):
        validate_state(state)


def test_optional_cache_cannot_be_an_indirect_baseline_gate(state):
    node(state, "R04.component_verified")["requires"].append("R05.cache_verified")
    with pytest.raises(LedgerError, match="optional work"):
        validate_state(state)


def test_early_g1_cannot_wait_for_final_refactors(state):
    node(state, "G1")["requires"].append("R06.component_verified")
    with pytest.raises(LedgerError, match="early G1"):
        validate_state(state)


def test_full_gate_cannot_drop_a_required_component(state):
    node(state, "G2")["requires"].remove("R19.component_verified")
    with pytest.raises(LedgerError, match="prerequisites removed"):
        validate_state(state)


def test_full_gate_cannot_drop_a_language(state):
    node(state, "G2")["scope"].remove("java")
    with pytest.raises(LedgerError, match="gate scope reduced"):
        validate_state(state)


def test_schema_boolean_is_not_version_one(state):
    state["schema_version"] = True
    with pytest.raises(LedgerError, match="schema_version"):
        validate_state(state)


def test_partial_language_verification_is_not_complete(state):
    item = node(state, "R03.component_verified")
    item.update(status="DONE", verified_scope=["python"], evidence_paths=["report.json"])
    with pytest.raises(LedgerError, match="scope reduced"):
        validate_state(state)


def test_design_done_requires_actual_evidence_file(state, tmp_path):
    item = node(state, "R01.design_ready")
    item.update(status="DONE", verified_scope=["full_task_contract"], evidence_paths=["absent.md"])
    with pytest.raises(LedgerError, match="missing evidence"):
        validate_state(state, repo_root=tmp_path)


def test_valid_file_does_not_allow_incomplete_dependencies(state):
    item = node(state, "R02.design_ready")
    item.update(status="DONE", verified_scope=["full_task_contract"], evidence_paths=["report.md"])
    with pytest.raises(LedgerError, match="incomplete dependency"):
        validate_state(state)


def test_task_done_cannot_skip_milestones(state):
    state["tasks"][0].update(status="DONE", evidence_paths=["report.md"])
    with pytest.raises(LedgerError, match="incomplete milestone"):
        validate_state(state)


def test_claim_cannot_be_silently_removed(state):
    state["claims"][0]["included_in_current_public_scope"] = False
    with pytest.raises(LedgerError, match="drop submitted scope"):
        validate_state(state)


def test_claim_fulfillment_requires_shared_gate(state):
    state["claims"][0].update(original_submission_status="FULFILLED", evidence_paths=["report.md"])
    with pytest.raises(LedgerError, match="G2 not passed"):
        validate_state(state)


@pytest.mark.parametrize("field", ["release_readiness", "stage_readiness"])
def test_readiness_cannot_be_inferred_from_task_status(state, field):
    state[field] = "READY"
    with pytest.raises(LedgerError, match="gate not passed"):
        validate_state(state)


def test_evidence_cannot_escape_repository(state):
    state["tasks"][0]["evidence_paths"] = ["../private.md"]
    with pytest.raises(LedgerError, match="unsafe evidence"):
        validate_state(state)


def test_cli_rejects_duplicate_json_keys(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text('{"schema_version": 1, "schema_version": 1}', encoding="utf-8")
    assert main([str(path)]) == 1
    assert "duplicate JSON key" in capsys.readouterr().err


def test_cli_positive():
    assert main([str(ROOT / "docs/bhmea/execution-state.json")]) == 0
