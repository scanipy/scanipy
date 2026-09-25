"""R20: deterministic semantic success versus explicit incomplete attempts."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import analysis.ordering as ordering
from analysis.fingerprint import (
    LEGACY_WITNESS_NAMESPACE,
    SOURCE_WITNESS_NAMESPACE,
    compute_slice_fingerprint,
    compute_slice_fingerprint_v2,
    eligible_for_baseline_suppression,
)
from analysis.ordering import CPG, CanonicalizationDeadlineExceeded, Duration, canonical_order

pytestmark = pytest.mark.unit


class Clock:
    def __init__(self, step: float):
        self.value = 0.0
        self.step = step

    def monotonic(self) -> float:
        current = self.value
        self.value += self.step
        return current


def _graph() -> tuple[CPG, SimpleNamespace]:
    graph = CPG()
    left, right = [graph.add_node("CALL", resolved_fqn="source") for _ in range(2)]
    sink = graph.add_node("CALL", resolved_fqn="sink")
    graph.add_edge(left, sink, "CFG")
    graph.add_edge(right, sink, "CFG")
    return graph, SimpleNamespace(witness=(left, sink), source_tree_digest=bytes.fromhex("ab" * 32))


@pytest.mark.parametrize("label", ["empty", "discrete", "symmetric"])
def test_slow_clock_never_returns_different_successful_output(label: str) -> None:
    graph, _ = _graph()
    if label == "empty":
        graph = CPG()
    elif label == "discrete":
        graph = CPG()
        graph.add_node("NODE")
    with patch.object(ordering, "time", Clock(0.000001)):
        fast = canonical_order(graph)
    with patch.object(ordering, "time", Clock(0.000002)):
        other_fast = canonical_order(graph)
    assert fast.cpg_order_hash == other_fast.cpg_order_hash
    assert fast.fingerprint_class == other_fast.fingerprint_class
    with (
        patch.object(ordering, "time", Clock(1.0)),
        pytest.raises(CanonicalizationDeadlineExceeded),
    ):
        canonical_order(graph)


def test_exact_work_boundary_and_partial_search_never_strong() -> None:
    graph, _ = _graph()
    complete = canonical_order(graph, T=Duration(10))
    assert complete.search_states > 1
    weak = canonical_order(graph, B=complete.search_states - 1, T=Duration(10))
    exact = canonical_order(graph, B=complete.search_states, T=Duration(10))
    assert weak.fingerprint_class == "weak" and weak.budget_exhausted
    assert exact.fingerprint_class == "strong" and exact.cpg_order_hash == complete.cpg_order_hash
    assert canonical_order(graph, B=1, T=Duration(10)).cpg_order_hash == weak.cpg_order_hash


def test_one_completed_branch_is_not_a_completed_canonical_search() -> None:
    graph = CPG()
    nodes = [graph.add_node("NODE") for _ in range(5)]
    for index, node in enumerate(nodes):
        graph.add_edge(node, nodes[(index + 1) % 5], "CFG")
    partial = canonical_order(graph, B=2, T=Duration(10))
    complete = canonical_order(graph, B=6, T=Duration(10))
    assert partial.search_states == 2 and partial.fingerprint_class == "weak"
    assert complete.search_states == 6 and complete.fingerprint_class == "strong"


def test_slice_normalization_and_final_search_share_one_budget() -> None:
    graph = CPG()
    local = graph.add_node("IDENTIFIER", operator_or_literal="user_input")
    sink = graph.add_node("CALL", resolved_fqn="sink")
    graph.add_edge(local, sink, "PDG")
    request = SimpleNamespace(witness=(local, sink))
    weak = compute_slice_fingerprint(request, graph, B=1, T=Duration(10))
    strong = compute_slice_fingerprint(request, graph, B=2, T=Duration(10))
    assert weak.fingerprint_class == "weak" and weak.search_states == 1
    assert strong.fingerprint_class == "strong" and strong.search_states == 2


def test_hidden_weak_alpha_order_cannot_be_reclassified_strong() -> None:
    graph = CPG()
    left, right = [graph.add_node("IDENTIFIER", operator_or_literal="x") for _ in range(2)]
    sink = graph.add_node("CALL", resolved_fqn="sink")
    graph.add_edge(left, sink, "PDG")
    graph.add_edge(right, sink, "PDG")
    result = compute_slice_fingerprint(SimpleNamespace(witness=(sink,)), graph, B=1, T=Duration(10))
    assert result.fingerprint_class == "weak"


def test_deadline_during_slice_is_failure_not_legacy_weak() -> None:
    graph, request = _graph()
    with (
        patch.object(ordering, "time", Clock(1.0)),
        pytest.raises(CanonicalizationDeadlineExceeded),
    ):
        compute_slice_fingerprint(request, graph, B=1)


def test_source_less_weak_is_explicitly_legacy_and_v2_requires_real_input() -> None:
    graph, request = _graph()
    legacy = compute_slice_fingerprint(request, graph, B=1, T=Duration(10))
    modern = compute_slice_fingerprint_v2(request, graph, B=1, T=Duration(10))
    assert legacy.identity_namespace == LEGACY_WITNESS_NAMESPACE
    assert modern.identity_namespace == SOURCE_WITNESS_NAMESPACE
    assert legacy.slice_fingerprint != modern.slice_fingerprint
    request.source_tree_digest = bytes.fromhex("cd" * 32)
    changed = compute_slice_fingerprint_v2(request, graph, B=1, T=Duration(10))
    assert changed.slice_fingerprint != modern.slice_fingerprint
    request.source_tree_digest = None
    with pytest.raises(ValueError, match="source_tree_digest"):
        compute_slice_fingerprint_v2(request, graph)


def test_source_aware_disconnected_witness_fails_even_with_ample_work_budget() -> None:
    graph, request = _graph()
    other = graph.add_node("UNRELATED")
    request.witness = (other, request.witness[-1])
    with pytest.raises(ValueError, match="disconnected"):
        compute_slice_fingerprint_v2(request, graph, T=Duration(10))


def test_legacy_strong_or_unknown_namespace_never_auto_inherits() -> None:
    graph, request = _graph()
    strong = compute_slice_fingerprint(request, graph, T=Duration(10))
    assert eligible_for_baseline_suppression(strong)
    for namespace in ("scanipy-slice-fingerprint/1", "unknown/999"):
        assert not eligible_for_baseline_suppression(replace(strong, identity_namespace=namespace))


@pytest.mark.parametrize("bad", [0, -1, True, 1.5])
def test_invalid_work_budget_is_not_a_weak_success(bad: object) -> None:
    with pytest.raises(ValueError, match="B must"):
        canonical_order(CPG(), B=bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [0.0, -1.0, True, float("inf"), float("nan"), "0.2"])
def test_invalid_time_budget_is_not_a_weak_success(bad: object) -> None:
    with pytest.raises(ValueError, match="T must"):
        canonical_order(CPG(), T=bad)  # type: ignore[arg-type]


def test_deadline_expiring_during_fallback_cannot_publish_weak() -> None:
    graph, _ = _graph()
    clock = Clock(0.0)
    original = ordering._stable_order_fallback

    def expired_fallback(cpg: CPG) -> list[ordering.NodeId]:
        clock.value = 1.0
        return original(cpg)

    with (
        patch.object(ordering, "time", clock),
        patch.object(ordering, "_stable_order_fallback", expired_fallback),
        pytest.raises(CanonicalizationDeadlineExceeded),
    ):
        canonical_order(graph, B=1)
