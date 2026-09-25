"""R19-B1 observations are lossless structure, never binding or solver proof."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import traceback
from pathlib import Path

import pytest

from analysis.cpg_ingest import typed_observed
from analysis.cpg_ingest.joern_schema_v2 import EDGE_PROPERTIES, NODE_PROPERTIES
from analysis.cpg_ingest.raw_v2 import source_tree_digest
from analysis.cpg_ingest.typed_observed import (
    FrozenArray,
    FrozenObject,
    ObservedGraphInputError,
    ObservedGraphLimitError,
    ObservedGraphLimits,
    ObservedGraphUnsupportedError,
    TypedObservedGraph,
    parse_observed_graph,
    to_raw_document,
    validate_observed_graph,
)

pytestmark = pytest.mark.unit
FIXTURES = Path(__file__).parents[1] / "fixtures" / "joern_raw_v2" / "exports"


def _node(node_id, kind, **properties):
    required = {key for key, (_, qty) in NODE_PROPERTIES[kind].items() if qty == "one"}
    return {
        "id": str(node_id),
        "kind": kind,
        "properties": properties,
        "missing_properties": sorted(required - properties.keys()),
    }


def _edge(src, dst, kind="AST", **properties):
    return {"src": str(src), "dst": str(dst), "kind": kind, "properties": properties}


@pytest.fixture
def document():
    # Retained producer assertions remain assertions; added nodes are synthetic.
    value = json.loads((FIXTURES / "python.json").read_bytes())
    value["nodes"] = [_node(1, "META_DATA", LANGUAGE="PYTHONSRC")]
    value["edges"] = []
    return value


def _capture(document, **limits):
    return parse_observed_graph(json.dumps(document).encode(), limits=ObservedGraphLimits(**limits))


@pytest.mark.parametrize("language", ["java", "python"])
def test_retained_lossless_immutable_capture(language):
    raw = (FIXTURES / f"{language}.json").read_bytes()
    graph = parse_observed_graph(raw)
    assert graph.original_raw_export_bytes == raw
    assert graph.raw_export_sha256 == "sha256:" + hashlib.sha256(raw).hexdigest()
    assert to_raw_document(graph) == json.loads(raw)
    assert graph.model_version == "scanipy-cpg/2"
    assert graph.role_profile == "scanipy-java-python-roles/1"
    assert graph.stage == "observed-only"
    validate_observed_graph(graph)
    detached = to_raw_document(graph)
    detached["nodes"][0]["properties"].clear()
    detached["producer"]["tools"].clear()
    assert to_raw_document(graph) == json.loads(raw)
    with pytest.raises(dataclasses.FrozenInstanceError):
        graph.nodes = ()
    assert type(graph.nodes) is tuple
    assert type(graph.producer) is FrozenObject
    assert type(graph.producer.get("tools")) is FrozenArray


def test_catalog_complete_presence_types_and_all_kinds(document):
    document["nodes"].append(_node(2, "METHOD"))
    for number, (kind, catalog) in enumerate(NODE_PROPERTIES.items(), 3):
        if kind == "META_DATA":
            continue
        props = {
            name: [] if qty == "many" else {"str": "", "int": 0, "bool": False}[native]
            for name, (native, qty) in catalog.items()
        }
        document["nodes"].append(_node(number, kind, **props))
        if kind in {"METHOD_PARAMETER_IN", "METHOD_PARAMETER_OUT", "METHOD_RETURN"}:
            document["edges"].append(_edge(2, number))
    graph = _capture(document)
    assert {node.kind for node in graph.nodes} == set(NODE_PROPERTIES)
    for node in graph.nodes:
        assert {prop.name for prop in node.properties} == set(NODE_PROPERTIES[node.kind])
    empty_method = graph.node("2")
    assert empty_method.property("NAME").presence == "missing_required"
    assert empty_method.property("LINE_NUMBER").presence == "absent_optional"
    call = next(node for node in graph.nodes if node.kind == "CALL")
    assert call.property("POSSIBLE_TYPES").value == FrozenArray(())
    assert call.property("POSSIBLE_TYPES").presence == "present"
    document["nodes"].append(_node(999, "CALL"))
    assert _capture(document).node("999").property("POSSIBLE_TYPES").presence == "absent_many"
    assert to_raw_document(graph)["nodes"] == document["nodes"][:-1]


@pytest.mark.parametrize("value", [1.0, None, True, "1"])
def test_native_int_type_never_coerced(document, value):
    document["nodes"].append(_node(2, "CALL", ARGUMENT_INDEX=value))
    with pytest.raises(ObservedGraphInputError):
        _capture(document)


@pytest.mark.parametrize("change", ["kind", "property", "version", "format"])
def test_unsupported_surfaces_fail(document, change):
    if change == "kind":
        document["nodes"][0]["kind"] = "NEW_KIND"
    elif change == "property":
        document["nodes"][0]["properties"]["NEW_PROPERTY"] = "x"
    elif change == "version":
        document["format_version"] = 3
    else:
        document["format"] = "other"
    with pytest.raises(ObservedGraphUnsupportedError):
        _capture(document)


@pytest.mark.parametrize("defect", ["duplicate", "dangling", "cycle", "parents", "formal"])
def test_invalid_structure_fails(document, defect):
    document["nodes"] += [_node(2, "METHOD"), _node(3, "BLOCK"), _node(4, "BLOCK")]
    document["edges"] = [_edge(2, 3), _edge(3, 4)]
    if defect == "duplicate":
        document["nodes"].append(document["nodes"][-1])
    elif defect == "dangling":
        document["edges"].append(_edge(4, 999))
    elif defect == "cycle":
        document["edges"].append(_edge(4, 2))
    elif defect == "parents":
        document["edges"].append(_edge(2, 4))
    else:
        document["nodes"].append(_node(5, "METHOD_PARAMETER_IN"))
    with pytest.raises(ObservedGraphInputError):
        _capture(document)


def test_deep_chain_shared_forest_and_parallel_edges_are_linear(document):
    count = 4000  # Far beyond Python recursion depth; no ancestor paths per node.
    document["nodes"] += [_node(2, "METHOD")]
    document["nodes"] += [_node(number, "BLOCK") for number in range(3, count + 2)]
    document["edges"] = [
        _edge(number - 1, number) for number in range(3, count + 2) for _ in range(2)
    ]
    graph = _capture(document)
    assert len(graph.views.ast_parents) == count - 1
    assert sum(len(parent.edge_ordinals) for parent in graph.views.ast_parents) == 2 * (count - 1)
    assert len(graph.views.ownership) == count + 1
    assert graph.owner(str(count + 1)).method_id == "2"
    assert graph.owner("1").status == "no_method_ancestor"
    assert all(not hasattr(owner, "ancestor_path") for owner in graph.views.ownership)


def test_nested_method_self_owner_outer_owner_and_edge_roles(document):
    document["nodes"] += [
        _node(2, "METHOD", FULL_NAME="same"),
        _node(3, "METHOD", FULL_NAME="same"),
        _node(4, "CALL"),
        _node(5, "IDENTIFIER", ARGUMENT_NAME="named", ARGUMENT_INDEX=-1),
        _node(6, "RETURN"),
        _node(7, "BLOCK"),
        _node(8, "METHOD_RETURN"),
    ]
    document["edges"] = [
        _edge(2, 3),
        _edge(3, 4),
        _edge(4, 5),
        _edge(3, 6),
        _edge(6, 7),
        _edge(3, 8),
        _edge(4, 3, "CALL"),
        _edge(4, 5, "ARGUMENT"),
        _edge(4, 5, "RECEIVER"),
        _edge(6, 7, "ARGUMENT"),
        _edge(6, 8, "CFG"),
        _edge(5, 7, "REACHING_DEF", VARIABLE=""),
        _edge(5, 7, "REACHING_DEF", VARIABLE="different"),
    ]
    graph = _capture(document)
    assert graph.owner("3").method_id == "3"
    assert graph.owner("4").method_id == "3"
    nested = next(method for method in graph.views.methods if method.node_id == "3")
    assert nested.outer_method_id == "2"
    assert graph.methods_by_full_name("same") == ("2", "3")
    call = graph.views.calls[0]
    assert call.target_edges == (6,)
    assert call.receiver_edges == (8,)
    assert call.actual_edges == (7,)
    assert call.binding_status == "unsupported"
    assert graph.views.returns[0].expression_edges == (9,)
    assert graph.views.returns[0].exit_edges == (10,)
    assert [edge.properties.get("VARIABLE") for edge in graph.edges[-2:]] == ["", "different"]


def test_retained_java_wrong_candidate_is_not_repaired_or_merged():
    graph = parse_observed_graph((FIXTURES / "java.json").read_bytes())
    helpers = graph.methods_by_full_name("rawprobe.Flow.helper:<unresolvedSignature>(2)")
    assert set(helpers) == {"107374182400", "107374182401"}
    call = next(call for call in graph.views.calls if call.node_id == "30064771086")
    assert [graph.edges[index].dst for index in call.target_edges] == ["107374182400"]
    assert call.binding_status == "unsupported"
    assert call.receiver_edges


def test_retained_python_named_actuals_defaults_and_source_ambiguity():
    graph = parse_observed_graph((FIXTURES / "python.json").read_bytes())
    call = next(call for call in graph.views.calls if call.node_id == "30064771094")
    actuals = [graph.node(graph.edges[index].dst) for index in call.actual_edges]
    assert {node.property("ARGUMENT_NAME").value for node in actuals} == {"right", "left"}
    assert all(node.property("ARGUMENT_INDEX").presence == "missing_required" for node in actuals)
    assert graph.node("111669149697").property("IS_VARIADIC").presence == "missing_required"
    assert not [
        node
        for node in graph.nodes
        if node.kind == "LITERAL" and node.property("LINE_NUMBER").value == 4
    ]
    lookup = graph.methods_at_source("flow.py", 18)
    assert {"107374182405", "107374182412"} <= set(lookup.method_ids)
    assert lookup.status == "unverified"
    assert graph.methods_at_source("other/flow.py", 18).method_ids == ()


@pytest.mark.parametrize("value", [True, 0, -1, 1.5, 10001])
def test_limits_cannot_be_raised_or_coerced(value):
    with pytest.raises(ObservedGraphLimitError):
        ObservedGraphLimits(max_nodes=value)


@pytest.mark.parametrize(
    "limit",
    [
        "max_raw_bytes",
        "max_string_bytes",
        "max_total_string_bytes",
        "max_json_values",
        "max_json_depth",
    ],
)
def test_observation_limits_fail_without_prefix(document, limit):
    with pytest.raises(ObservedGraphLimitError):
        _capture(document, **{limit: 1})


def test_input_depth_duplicate_keys_failed_and_direct_construction(document):
    for raw in [b'{"x":1,"x":2}', b'"\\ud800"', b"{", b"NaN", b"1e0"]:
        with pytest.raises(ObservedGraphInputError):
            parse_observed_graph(raw)
    with pytest.raises(ObservedGraphLimitError):
        parse_observed_graph(b"[" * 33 + b"]" * 33)
    raw = json.dumps(document).encode()
    assert TypedObservedGraph(raw) == parse_observed_graph(raw)
    for bad in [bytearray(raw), raw.decode(), document]:
        with pytest.raises(ObservedGraphInputError):
            TypedObservedGraph(bad)
    with pytest.raises(ObservedGraphInputError):
        validate_observed_graph(object())


def test_frozen_wrappers_reject_mutable_subclass_float_and_duplicate():
    class Sneaky(str):
        pass

    for value in [[], {}, 1.0, Sneaky("x")]:
        with pytest.raises(ObservedGraphInputError):
            FrozenArray((value,))
    with pytest.raises(ObservedGraphInputError):
        FrozenObject((("a", 1), ("a", 2)))


def test_all_edge_kinds_and_sparse_variable_are_retained(document):
    document["nodes"] += [
        _node(2, "METHOD"),
        _node(3, "CALL"),
        _node(4, "IDENTIFIER"),
        _node(5, "LOCAL"),
        _node(6, "METHOD_PARAMETER_IN"),
        _node(7, "METHOD_PARAMETER_OUT"),
        _node(8, "RETURN"),
        _node(9, "METHOD_RETURN"),
    ]
    document["edges"] = [_edge(2, target) for target in (6, 7, 9)]
    endpoints = {
        "CALL": (3, 2),
        "RECEIVER": (3, 4),
        "ARGUMENT": (3, 4),
        "REF": (4, 5),
        "PARAMETER_LINK": (6, 7),
    }
    for kind in EDGE_PROPERTIES:
        document["edges"].append(_edge(*endpoints.get(kind, (2, 3)), kind))
    document["edges"].append(_edge(4, 5, "REACHING_DEF", VARIABLE=""))
    graph = _capture(document)
    assert {edge.kind for edge in graph.edges} == set(EDGE_PROPERTIES)
    assert to_raw_document(graph)["edges"] == document["edges"]
    dependencies = [edge for edge in graph.edges if edge.kind == "REACHING_DEF"]
    assert dependencies[0].properties.entries == ()
    assert dependencies[1].properties.get("VARIABLE") == ""
    assert {formal.direction for formal in graph.views.formals} == {
        "METHOD_PARAMETER_IN",
        "METHOD_PARAMETER_OUT",
    }


@pytest.mark.parametrize("value", [False, 0, 0.0, "", None, [0], [False], [1.0]])
def test_many_string_properties_require_exact_arrays_of_strings(document, value):
    document["nodes"].append(_node(2, "CALL", POSSIBLE_TYPES=value))
    with pytest.raises(ObservedGraphInputError):
        _capture(document)


def test_wrong_owner_parameter_link_and_duplicate_native_index(document):
    document["nodes"] += [
        _node(2, "METHOD"),
        _node(3, "METHOD"),
        _node(4, "METHOD_PARAMETER_IN", INDEX=-2),
        _node(5, "METHOD_PARAMETER_OUT", INDEX=-2),
    ]
    document["edges"] = [_edge(2, 4), _edge(3, 5), _edge(4, 5, "PARAMETER_LINK")]
    with pytest.raises(ObservedGraphInputError):
        _capture(document)
    document["edges"][1]["src"] = "2"
    graph = _capture(document)
    assert graph.node("4").property("INDEX").value == -2  # Observation, not semantic validity.
    assert graph.node("5").property("INDEX").value == -2
    assert graph.views.semantic_status == "unsupported"


def test_retained_python_star_bound_receiver_block_return_and_parallel_variables():
    graph = parse_observed_graph((FIXTURES / "python.json").read_bytes())

    def one(kind, code):
        return next(
            node
            for node in graph.nodes
            if node.kind == kind and node.property("CODE").value == code
        )

    splat = one("CALL", 'variadic("prefix", *values, **named)')
    call = next(call for call in graph.views.calls if call.node_id == splat.node_id)
    actuals = [graph.node(graph.edges[edge].dst) for edge in call.actual_edges]
    assert any(node.property("ARGUMENT_NAME").value == "<keyword_dict>" for node in actuals)
    assert any(
        node.kind == "CALL" and node.property("NAME").value == "<operator>.starredUnpack"
        for node in actuals
    )
    execute = one("CALL", "self.cursor.execute(self.instance(third))")
    call = next(call for call in graph.views.calls if call.node_id == execute.node_id)
    assert call.target_edges == () and call.binding_status == "unsupported"
    receiver = graph.node(graph.edges[call.receiver_edges[0]].dst)
    bound = [
        graph.node(graph.edges[edge].dst)
        for edge in call.actual_edges
        if graph.node(graph.edges[edge].dst).property("ARGUMENT_INDEX").value == 0
    ]
    assert receiver.property("CODE").value == "tmp0.execute"
    assert bound[0].property("CODE").value == "tmp0" and bound[0].node_id != receiver.node_id
    statement = one("RETURN", "return self.cursor.fetchall()")
    returned = next(value for value in graph.views.returns if value.node_id == statement.node_id)
    block = graph.node(graph.edges[returned.expression_edges[0]].dst)
    assert block.kind == "BLOCK"
    parallel = [
        edge
        for edge in graph.edges
        if edge.kind == "REACHING_DEF"
        and edge.src == block.node_id
        and edge.dst == statement.node_id
    ]
    assert len(parallel) == 2
    assert {edge.properties.get("VARIABLE") for edge in parallel} == {
        "",
        block.property("CODE").value,
    }


def test_retained_java_missing_variadic_is_not_false():
    graph = parse_observed_graph((FIXTURES / "java.json").read_bytes())
    rest = next(
        node
        for node in graph.nodes
        if node.kind == "METHOD_PARAMETER_IN" and node.property("CODE").value == "String... rest"
    )
    assert rest.property("IS_VARIADIC").presence == "missing_required"
    assert rest.property("IS_VARIADIC").value is None


def test_failed_raw_export_and_claimed_derived_completion_never_become_graph(document):
    for capability in document["capabilities"].values():
        if capability["status"] == "completed":
            capability["status"] = "failed"
    document.update(
        status="failed",
        nodes=None,
        edges=None,
        error={"code": "raw-export-failed", "message": "controlled failure"},
    )
    with pytest.raises(ObservedGraphInputError, match="raw-incomplete"):
        _capture(document)


@pytest.mark.parametrize(
    "capability",
    [
        "actual_formal_binding",
        "call_target_completeness",
        "return_result_binding",
        "effect_analysis",
        "purity_certification",
    ],
)
def test_derived_capabilities_cannot_be_promoted(document, capability):
    document["capabilities"][capability]["status"] = "completed"
    with pytest.raises(ObservedGraphInputError):
        _capture(document)


def test_preparse_depth_and_bytes_fail_before_json_parser(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("general JSON parser ran before configured byte/depth bounds")

    monkeypatch.setattr(typed_observed.json, "loads", forbidden)
    with pytest.raises(ObservedGraphLimitError):
        parse_observed_graph(b"{}", limits=ObservedGraphLimits(max_raw_bytes=1))
    with pytest.raises(ObservedGraphLimitError):
        parse_observed_graph(b"[" * 33 + b"]" * 33)


@pytest.mark.parametrize("bound", ["nodes", "edges", "source"])
def test_counts_fail_before_freezing_and_views(document, monkeypatch, bound):
    def forbidden(*args, **kwargs):
        pytest.fail("freezing happened before count bounds")

    limits = {}
    if bound == "nodes":
        document["nodes"].append(_node(2, "METHOD"))
        limits["max_nodes"] = 1
    elif bound == "edges":
        document["nodes"].append(_node(2, "METHOD"))
        document["edges"] = [_edge(2, 1), _edge(2, 1)]
        limits["max_edges"] = 1
    else:
        files = document["producer"]["source"]["files"]
        files.append({"path": "z.py", "size": 0, "sha256": hashlib.sha256(b"").hexdigest()})
        document["producer"]["source"]["tree_sha256"] = source_tree_digest(files)
        limits["max_source_files"] = 1
    monkeypatch.setattr(typed_observed, "freeze_value", forbidden)
    with pytest.raises(ObservedGraphLimitError):
        _capture(document, **limits)


def test_exact_boundaries_and_string_lexing(document):
    document["producer"]["java_tool_options"] = '\\"[[[{{{}}}]]]'
    raw = json.dumps(document).encode()
    graph = parse_observed_graph(
        raw, limits=ObservedGraphLimits(max_raw_bytes=len(raw), max_nodes=1)
    )
    assert graph.original_raw_export_bytes == raw
    with pytest.raises(ObservedGraphLimitError):
        parse_observed_graph(raw, limits=ObservedGraphLimits(max_raw_bytes=len(raw) - 1))


def test_no_source_echo_in_unknown_kind_diagnostics(document):
    # Synthetic redaction sentinel, not a credential; exact reviewed scanner exception.
    secret_like = "DO_NOT_PRINT_CAPTURE_VALUE" * 20  # pragma: allowlist secret
    document["nodes"][0]["kind"] = secret_like
    with pytest.raises(ObservedGraphUnsupportedError) as raised:
        _capture(document)
    assert secret_like not in "".join(traceback.format_exception(raised.value))


def test_long_native_id_fails_typed_not_python_integer_exception(document):
    document["nodes"][0]["id"] = "9" * 5000
    with pytest.raises(ObservedGraphInputError):
        _capture(document)


def test_permutation_retains_multiset_without_canonical_byte_claim():
    raw = (FIXTURES / "python.json").read_bytes()
    graph = parse_observed_graph(raw)
    document = json.loads(raw)
    document["nodes"].reverse()
    document["edges"].reverse()
    permuted = _capture(document)
    assert {node.node_id: node for node in permuted.nodes} == {
        node.node_id: node for node in graph.nodes
    }
    assert permuted.raw_export_sha256 != graph.raw_export_sha256
    original = sorted(json.dumps(edge, sort_keys=True) for edge in to_raw_document(graph)["edges"])
    assert (
        sorted(json.dumps(edge, sort_keys=True) for edge in to_raw_document(permuted)["edges"])
        == original
    )


def test_no_canonical_solver_worker_or_subprocess_path(monkeypatch):
    import subprocess

    from analysis import fingerprint, ordering
    from analysis.cpg_ingest import mapper
    from analysis.cpg_ingest.typed_observed_wire import (
        deserialize_observed_graph,
        serialize_observed_graph,
    )
    from analysis.ifds import solver
    from services.scan import worker

    def forbidden(*args, **kwargs):
        pytest.fail("observed-only capture invoked a prohibited semantic/runtime path")

    for module, names in (
        (ordering, ("canonical_order", "encode_graph")),
        (fingerprint, ("compute_slice_fingerprint", "compute_slice_fingerprint_v2")),
        (solver, ("solve", "incremental_solve")),
        (worker, ("run_detector",)),
        (mapper, ("map_export",)),
        (subprocess, ("run", "Popen")),
    ):
        for name in names:
            monkeypatch.setattr(module, name, forbidden)
    graph = parse_observed_graph((FIXTURES / "python.json").read_bytes())
    assert deserialize_observed_graph(serialize_observed_graph(graph)) == graph
