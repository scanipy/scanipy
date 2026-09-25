"""R18 mechanism falsifiers; finite tests do not assert a universal theorem."""

from dataclasses import replace
from itertools import permutations, product
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from analysis.fingerprint import (
    SLICE_IDENTITY_NAMESPACE,
    _backward_interprocedural_slice,
    compute_slice_fingerprint,
)
from analysis.ordering import (
    CPG,
    GRAPH_IDENTITY_NAMESPACE,
    CanonicalizationBudget,
    Duration,
    NodeId,
    _GraphIndex,
    canonical_order,
    encode_graph,
)

pytestmark = pytest.mark.unit


def _relabel(graph: CPG, ids: tuple[int, ...]) -> CPG:
    mapping = {node.node_id: NodeId(new) for node, new in zip(graph.nodes, ids, strict=True)}
    return CPG(
        nodes=[replace(node, node_id=mapping[node.node_id]) for node in reversed(graph.nodes)],
        edges=[
            replace(edge, src=mapping[edge.src], dst=mapping[edge.dst])
            for edge in reversed(graph.edges)
        ],
    )


def _symmetric_sink(insertion: tuple[str, ...]) -> tuple[CPG, NodeId]:
    graph = CPG()
    ids = {
        name: graph.add_node(
            "CALL",
            resolved_fqn="example.sink" if name == "sink" else "example.source",
            enclosing_decl_fqn="example.handler",
        )
        for name in insertion
    }
    graph.add_edge(ids["left"], ids["sink"], "CFG")
    graph.add_edge(ids["right"], ids["sink"], "CFG")
    return graph, ids["sink"]


def test_recorded_six_permutations_have_one_strong_slice_identity() -> None:
    hashes = set()
    for insertion in permutations(("left", "right", "sink")):
        graph, sink = _symmetric_sink(insertion)
        result = compute_slice_fingerprint(SimpleNamespace(witness=(sink,)), graph, T=Duration(10))
        assert result.fingerprint_class == "strong"
        assert result.identity_namespace == SLICE_IDENTITY_NAMESPACE
        hashes.add(result.slice_fingerprint)
    assert len(hashes) == 1


def test_arbitrary_ids_and_enumeration_do_not_enter_strong_hash() -> None:
    graph, _ = _symmetric_sink(("left", "right", "sink"))
    expected = canonical_order(graph)
    for ids in permutations((997, 51, 10_000)):
        result = canonical_order(_relabel(graph, ids))
        assert result.cpg_order_hash == expected.cpg_order_hash
        assert result.fingerprint_class == "strong"
        assert result.identity_namespace == GRAPH_IDENTITY_NAMESPACE
        assert result.search_states == expected.search_states


def test_distinct_single_node_graphs_no_longer_hash_only_their_id() -> None:
    graphs = []
    for name in ("SOURCE", "UNRELATED"):
        graph = CPG()
        graph.add_node(name)
        graphs.append(graph)
    assert canonical_order(graphs[0]).cpg_order_hash != canonical_order(graphs[1]).cpg_order_hash


@pytest.mark.parametrize(
    "change", ["literal", "target", "declaration", "kind", "direction", "duplicate", "loop"]
)
def test_distinct_semantics_are_not_collapsed(change: str) -> None:
    graph = CPG()
    source = graph.add_node("SOURCE", operator_or_literal="data", resolved_fqn="pkg.source")
    sink = graph.add_node("SINK", enclosing_decl_fqn="pkg.fn")
    graph.add_edge(source, sink, "PDG")
    changed = _relabel(graph, (0, 1))
    if change == "literal":
        changed.nodes[0] = replace(changed.nodes[0], operator_or_literal="different")
    elif change == "target":
        changed.nodes[0] = replace(changed.nodes[0], resolved_fqn="different")
    elif change == "declaration":
        changed.nodes[0] = replace(changed.nodes[0], enclosing_decl_fqn="different")
    elif change == "kind":
        changed.edges[0] = replace(changed.edges[0], kind="CFG")
    elif change == "direction":
        changed.edges[0] = replace(changed.edges[0], src=sink, dst=source)
    elif change == "duplicate":
        changed.add_edge(source, sink, "PDG")
    else:
        changed.add_edge(sink, sink, "PDG")
    assert canonical_order(graph).cpg_order_hash != canonical_order(changed).cpg_order_hash


def test_locations_are_excluded_and_utf8_fields_are_framed() -> None:
    graph = CPG()
    graph.add_node(
        "CALL", operator_or_literal="a\x00é", resolved_fqn="bc", structural_path="file:10"
    )
    moved = CPG([replace(graph.nodes[0], structural_path="elsewhere:999")], [])
    ambiguous = CPG([replace(graph.nodes[0], operator_or_literal="a", resolved_fqn="\x00ébc")], [])
    assert canonical_order(graph).cpg_order_hash == canonical_order(moved).cpg_order_hash
    assert canonical_order(graph).cpg_order_hash != canonical_order(ambiguous).cpg_order_hash
    assert encode_graph(CPG(), []) == b"SCANIPY-CANONICAL-GRAPH/2\n" + bytes(16)


def test_exhaustive_three_node_directed_graphs_match_bruteforce_isomorphism() -> None:
    """All 512 loop-allowed graphs: production equivalence iff brute-force equivalence.

    Brute-force minimum need not use the production labeling convention. The
    bijection between equivalence classes, not equal arbitrary encodings, is the
    independent oracle. Also compare pruned versus unpruned production searches.
    """
    by_reference: dict[bytes, bytes] = {}
    by_production: dict[bytes, bytes] = {}
    pairs = list(product(range(3), repeat=2))
    for mask in range(1 << len(pairs)):
        graph = CPG()
        for _ in range(3):
            graph.add_node("NODE")
        for bit, (src, dst) in enumerate(pairs):
            if mask & (1 << bit):
                graph.add_edge(NodeId(src), NodeId(dst), "EDGE")
        reference = min(
            encode_graph(graph, list(order))
            for order in permutations([NodeId(i) for i in range(3)])
        )
        result = canonical_order(graph, T=Duration(10))
        assert result.fingerprint_class == "strong"
        assert by_reference.setdefault(reference, result.cpg_order_hash) == result.cpg_order_hash
        assert by_production.setdefault(result.cpg_order_hash, reference) == reference
        with patch.object(_GraphIndex, "swap_is_automorphism", return_value=False):
            unpruned = canonical_order(graph, T=Duration(10))
        assert unpruned.cpg_order_hash == result.cpg_order_hash


def test_swap_certificate_matches_explicit_typed_multigraph_transposition() -> None:
    for mode in range(8):
        graph = CPG()
        a, b, outside = [graph.add_node("NODE") for _ in range(3)]
        graph.add_edge(a, outside, "PDG")
        graph.add_edge(b, outside, "PDG")
        graph.add_edge(a, b, "CFG")
        graph.add_edge(b, a, "CFG")
        if mode & 1:
            graph.add_edge(a, outside, "PDG")
        if mode & 2:
            graph.add_edge(outside, b, "CFG")
        if mode & 4:
            graph.add_edge(a, a, "AST")
        budget = CanonicalizationBudget.start(T=Duration(10))
        index = _GraphIndex.build(graph, budget)
        expected = encode_graph(graph, [a, b, outside]) == encode_graph(graph, [b, a, outside])
        assert index.swap_is_automorphism(a, b, budget) is expected


def test_regular_cycle_uncertified_symmetries_still_search_all_branches() -> None:
    graph = CPG()
    nodes = [graph.add_node("NODE") for _ in range(5)]
    for i, node in enumerate(nodes):
        graph.add_edge(node, nodes[(i + 1) % 5], "CFG")
    result = canonical_order(graph, T=Duration(10))
    assert result.search_states == 6  # root plus every rotational candidate
    assert result.fingerprint_class == "strong"
    for ids in permutations((100, 200, 300, 400, 500)):
        assert (
            canonical_order(_relabel(graph, ids), T=Duration(10)).cpg_order_hash
            == result.cpg_order_hash
        )


def test_witness_cone_traverses_intermediate_nodes_and_cycles() -> None:
    graph = CPG()
    src, mid, sink = [
        graph.add_node("CALL", resolved_fqn=name) for name in ("source", "mid", "sink")
    ]
    dependency = graph.add_node("LITERAL", operator_or_literal="important")
    unrelated = graph.add_node("LITERAL", operator_or_literal="unrelated")
    graph.add_edge(src, mid, "CFG")
    graph.add_edge(mid, sink, "CFG")
    graph.add_edge(dependency, mid, "PDG")
    graph.add_edge(mid, src, "CFG")
    result = _backward_interprocedural_slice(graph, (src, mid, src, mid, sink))
    assert len(result.cpg.nodes) == 4
    assert any(node.operator_or_literal == "important" for node in result.cpg.nodes)
    assert all(node.operator_or_literal != "unrelated" for node in result.cpg.nodes)
    assert len(graph.nodes) == 5 and graph.nodes[unrelated].operator_or_literal == "unrelated"


def test_invalid_and_extended_graphs_fail_closed() -> None:
    graph = CPG()
    node = graph.add_node("NODE")
    graph.add_edge(node, NodeId(99), "PDG")
    with pytest.raises(ValueError, match="missing node"):
        canonical_order(graph)
    graph.edges.clear()
    graph.nodes.append(graph.nodes[0])
    with pytest.raises(ValueError, match="duplicate"):
        canonical_order(graph)
    graph.nodes.pop()
    object.__setattr__(graph.nodes[0], "semantic_role", "new-role")
    with pytest.raises(ValueError, match="unsupported CPG node fields"):
        compute_slice_fingerprint(SimpleNamespace(witness=(node,)), graph)


@pytest.mark.parametrize("attribute", ["argument_bindings", "effect_summaries", "model_version"])
def test_graph_level_semantic_extensions_cannot_be_silently_dropped(attribute: str) -> None:
    graph = CPG()
    node = graph.add_node("CALL", resolved_fqn="sink")
    setattr(graph, attribute, "future-model/3")
    with pytest.raises(ValueError, match="unsupported CPG"):
        canonical_order(graph)
    with pytest.raises(ValueError, match="unsupported CPG"):
        compute_slice_fingerprint(SimpleNamespace(witness=(node,)), graph)
