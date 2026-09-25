"""R19-A raw-schema falsifiers, separate from future graph/solver acceptance."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from analysis.cpg_ingest.joern_schema_v2 import NODE_PROPERTIES
from analysis.cpg_ingest.raw_v2 import (
    RawExportError,
    RawExportFailedError,
    parse_raw_export,
    source_tree_digest,
    validate_raw_export,
)

pytestmark = pytest.mark.unit
FIXTURES = Path(__file__).parents[1] / "fixtures" / "joern_raw_v2"


def _node(node_id, kind, **overrides):
    # Synthetic validator input, not claimed real Joern evidence.
    values = {"str": "", "int": -1, "bool": False}
    props = {
        key: values[native] for key, (native, qty) in NODE_PROPERTIES[kind].items() if qty == "one"
    }
    props.update(overrides)
    return {"id": str(node_id), "kind": kind, "properties": props, "missing_properties": []}


@pytest.fixture
def document():
    digest = hashlib.sha256(b"synthetic fixture identity").hexdigest()
    files = [{"path": "sample.py", "size": 1, "sha256": hashlib.sha256(b"x").hexdigest()}]
    raw = {
        name: {"status": "completed", "reason": "synthetic enumeration"}
        for name in ("raw_nodes", "raw_edges", "typed_properties")
    }
    raw.update(
        {
            name: {"status": "unsupported", "reason": "not a raw proof"}
            for name in (
                "call_target_completeness",
                "actual_formal_binding",
                "return_result_binding",
                "effect_analysis",
                "purity_certification",
            )
        }
    )
    return {
        "format": "scanipy-joern-export",
        "format_version": 2,
        "status": "completed",
        "producer": {
            "schema_version": 1,
            "image": {
                "kind": "docker-image-id",
                "reference": "sha256:" + digest,
                "observation": "caller-observed",
            },
            "tools": [
                {"role": role, "version": version, "path": "/tools/" + role, "sha256": digest}
                for role, version in (
                    ("joern-console", "4.0.554"),
                    ("frontend", "4.0.554"),
                    ("cpg-domain", "1.7.65"),
                    ("flatgraph-core", "0.1.31"),
                )
            ],
            "script": {"path": "/tools/export_cpg_v2.sc", "sha256": digest},
            "input_cpg": {"path": "/job/cpg.bin", "sha256": digest},
            "source": {
                "root": "/source",
                "tree_namespace": "scanipy-source-tree/1",
                "tree_sha256": source_tree_digest(files),
                "files": files,
            },
            "frontend": "pythonsrc",
            "import_mode": "importCpg-default-overlays",
            "java_runtime_version": "synthetic-test-runtime",
            "java_tool_options": "",
        },
        "capabilities": raw,
        "nodes": [
            _node(1, "META_DATA", LANGUAGE="PYTHONSRC"),
            _node(2, "METHOD", NAME="helper", IS_EXTERNAL=False),
            _node(3, "CALL", NAME="helper", METHOD_FULL_NAME="sample.py:helper"),
            _node(4, "IDENTIFIER", NAME="value", ARGUMENT_INDEX=1),
            _node(5, "METHOD_PARAMETER_IN", INDEX=1, NAME="value", IS_VARIADIC=False),
            _node(6, "METHOD_PARAMETER_OUT", INDEX=1, NAME="value"),
        ],
        "edges": [
            {"src": "2", "dst": "3", "kind": "AST", "properties": {}},
            {"src": "3", "dst": "4", "kind": "AST", "properties": {}},
            {"src": "2", "dst": "5", "kind": "AST", "properties": {}},
            {"src": "2", "dst": "6", "kind": "AST", "properties": {}},
            {"src": "3", "dst": "2", "kind": "CALL", "properties": {}},
            {"src": "3", "dst": "4", "kind": "ARGUMENT", "properties": {}},
            {"src": "4", "dst": "5", "kind": "REF", "properties": {}},
            {"src": "5", "dst": "6", "kind": "PARAMETER_LINK", "properties": {}},
            {"src": "4", "dst": "3", "kind": "REACHING_DEF", "properties": {"VARIABLE": "value"}},
        ],
        "error": None,
    }


def test_native_types_and_raw_multiedges_round_trip(document):
    document["nodes"][2]["properties"]["POSSIBLE_TYPES"] = ["str", "Any"]
    document["edges"].append(copy.deepcopy(document["edges"][-1]))
    parsed = parse_raw_export(json.dumps(document))
    assert parsed == document
    assert type(parsed["nodes"][1]["properties"]["IS_EXTERNAL"]) is bool
    assert type(parsed["nodes"][3]["properties"]["ARGUMENT_INDEX"]) is int
    assert len(parsed["edges"]) == 10
    assert parsed["edges"][-1]["properties"] == {"VARIABLE": "value"}
    assert parsed["capabilities"]["call_target_completeness"]["status"] == "unsupported"


def test_absent_required_raw_property_is_preserved_without_default_invention(document):
    node = document["nodes"][2]
    del node["properties"]["SIGNATURE"]
    node["missing_properties"] = ["SIGNATURE"]
    parsed = parse_raw_export(json.dumps(document))
    assert "SIGNATURE" not in parsed["nodes"][2]["properties"]
    assert parsed["nodes"][2]["missing_properties"] == ["SIGNATURE"]
    node["missing_properties"].append("NAME")
    with pytest.raises(RawExportError, match="explicit"):
        validate_raw_export(document)


@pytest.mark.parametrize("version", [True, 2.0, "2", 1, 3, None])
def test_unknown_or_coerced_wire_version_rejected(document, version):
    document["format_version"] = version
    with pytest.raises(RawExportError, match="version"):
        validate_raw_export(document)


@pytest.mark.parametrize(
    "kind,key,value",
    [
        ("CALL", "ARGUMENT_INDEX", True),
        ("CALL", "ARGUMENT_INDEX", "1"),
        ("CALL", "ARGUMENT_INDEX", 1.0),
        ("CALL", "ARGUMENT_INDEX", 2**31),
        ("METHOD", "IS_EXTERNAL", 0),
        ("METHOD", "IS_EXTERNAL", "false"),
        ("CALL", "POSSIBLE_TYPES", "str"),
        ("CALL", "POSSIBLE_TYPES", [1]),
        ("CALL", "NAME", None),
        ("CALL", "NAME", "\ud800"),
    ],
)
def test_native_property_types_are_not_coerced(document, kind, key, value):
    node = next(n for n in document["nodes"] if n["kind"] == kind)
    node["properties"][key] = value
    with pytest.raises(RawExportError):
        validate_raw_export(document)


@pytest.mark.parametrize(
    "mutation",
    [
        "top-extra",
        "node-extra",
        "property-extra",
        "missing-required",
        "unknown-kind",
        "duplicate-id",
        "id-leading-zero",
        "id-number",
        "id-too-large",
        "dangling",
        "unknown-edge",
        "edge-extra",
        "variable-number",
        "variable-on-call",
        "call-target",
        "formal-target",
        "argument-target",
        "receiver-target",
        "ref-target",
    ],
)
def test_shapes_roles_and_endpoints_fail_closed(document, mutation):
    # Keep the mutation references independent of added native AST-owner edges.
    edges = [e for e in document["edges"] if e["kind"] != "AST"]
    if mutation == "top-extra":
        document["canonical"] = True
    elif mutation == "node-extra":
        document["nodes"][0]["location"] = 1
    elif mutation == "property-extra":
        document["nodes"][2]["properties"]["PURITY"] = "pure"
    elif mutation == "missing-required":
        del document["nodes"][2]["properties"]["NAME"]
    elif mutation == "unknown-kind":
        document["nodes"][2]["kind"] = "NEW_CALL_KIND"
    elif mutation == "duplicate-id":
        document["nodes"].append(copy.deepcopy(document["nodes"][0]))
    elif mutation.startswith("id-"):
        document["nodes"][0]["id"] = {
            "id-leading-zero": "01",
            "id-number": 1,
            "id-too-large": str(2**63),
        }[mutation]
    elif mutation == "dangling":
        edges[0]["dst"] = "900"
    elif mutation == "unknown-edge":
        edges[0]["kind"] = "GUESSED_FLOW"
    elif mutation == "edge-extra":
        edges[0]["position"] = 1
    elif mutation == "variable-number":
        document["edges"][-1]["properties"]["VARIABLE"] = 4
    elif mutation == "variable-on-call":
        edges[0]["properties"]["VARIABLE"] = "x"
    else:
        index, target = {
            "call-target": (0, "4"),
            "formal-target": (3, "2"),
            "argument-target": (1, "2"),
            "receiver-target": (1, "2"),
            "ref-target": (2, "3"),
        }[mutation]
        edges[index]["dst"] = target
        if mutation == "receiver-target":
            edges[index]["kind"] = "RECEIVER"
    with pytest.raises(RawExportError):
        validate_raw_export(document)


@pytest.mark.parametrize(
    "mutation", ["missing-owner", "wrong-owner", "multiple-owners", "cycle", "cross-method-link"]
)
def test_raw_ast_and_formal_ownership_fail_closed(document, mutation):
    if mutation == "missing-owner":
        document["edges"] = [
            e for e in document["edges"] if not (e["kind"] == "AST" and e["dst"] == "5")
        ]
    elif mutation == "wrong-owner":
        document["edges"][2]["src"] = "3"
    elif mutation == "multiple-owners":
        document["edges"].append({"src": "3", "dst": "5", "kind": "AST", "properties": {}})
    elif mutation == "cycle":
        document["edges"].append({"src": "4", "dst": "2", "kind": "AST", "properties": {}})
    else:
        document["nodes"].append(_node(7, "METHOD", NAME="other"))
        document["edges"][3]["src"] = "7"
    with pytest.raises(RawExportError, match=r"owner|same method"):
        validate_raw_export(document)


@pytest.mark.parametrize(
    "mutation",
    [
        "fake-complete",
        "raw-failed",
        "missing-cap",
        "bad-tool",
        "duplicate-tool",
        "bad-image",
        "bad-digest",
        "source-tamper",
        "language-mismatch",
        "producer-version",
    ],
)
def test_provenance_and_capability_claims_are_explicit(document, mutation):
    if mutation == "fake-complete":
        document["capabilities"]["purity_certification"]["status"] = "completed"
    elif mutation == "raw-failed":
        document["capabilities"]["raw_edges"]["status"] = "failed"
    elif mutation == "missing-cap":
        del document["capabilities"]["raw_edges"]
    elif mutation == "bad-tool":
        document["producer"]["tools"][0]["version"] = "newer-unverified"
    elif mutation == "duplicate-tool":
        document["producer"]["tools"].append(copy.deepcopy(document["producer"]["tools"][0]))
    elif mutation == "bad-image":
        document["producer"]["image"]["observation"] = "independently-attested"
    elif mutation == "bad-digest":
        document["producer"]["script"]["sha256"] = "unknown"
    elif mutation == "source-tamper":
        document["producer"]["source"]["files"][0]["path"] = "different.py"
    elif mutation == "language-mismatch":
        document["producer"]["frontend"] = "javasrc"
    elif mutation == "producer-version":
        document["producer"]["schema_version"] = True
    with pytest.raises(RawExportError):
        validate_raw_export(document)


def test_failure_document_is_not_an_empty_complete_graph(document):
    document["status"] = "failed"
    document["nodes"] = document["edges"] = None
    document["error"] = {"code": "raw-export-failed", "message": "IllegalArgumentException"}
    for name in ("raw_nodes", "raw_edges", "typed_properties"):
        document["capabilities"][name]["status"] = "failed"
    validate_raw_export(document, require_completed=False)
    with pytest.raises(RawExportFailedError):
        parse_raw_export(json.dumps(document))
    document["edges"] = []
    with pytest.raises(RawExportError, match="partially complete"):
        validate_raw_export(document, require_completed=False)


def test_duplicate_json_keys_and_byte_limits_are_rejected(document):
    text = json.dumps(document)
    for value in (
        text.replace('"format_version": 2', '"format_version": 1,"format_version": 2'),
        text.replace('"LANGUAGE": "PYTHONSRC"', '"LANGUAGE": "JAVA","LANGUAGE": "PYTHONSRC"'),
    ):
        with pytest.raises(RawExportError, match="duplicate JSON key"):
            parse_raw_export(value)
    with pytest.raises(RawExportError, match="byte limit"):
        parse_raw_export(text, max_bytes=10)
    with pytest.raises(RawExportError, match="UTF-8 JSON"):
        parse_raw_export(b"\xff")


@pytest.mark.parametrize("path", ["../x", "/x", "a//x", "a/./x", "a/../x", "x\0y"])
def test_source_manifest_path_escape_rejected(path):
    with pytest.raises(RawExportError, match="relative POSIX"):
        source_tree_digest([{"path": path, "size": 0, "sha256": "0" * 64}])


def test_source_tree_digest_binds_names_sizes_bytes_and_order(document):
    files = document["producer"]["source"]["files"]
    digest = source_tree_digest(files)
    for key, new_value in (("path", "other.py"), ("size", 2), ("sha256", "1" * 64)):
        altered = copy.deepcopy(files)
        altered[0][key] = new_value
        assert source_tree_digest(altered) != digest
    with pytest.raises(RawExportError, match="unique"):
        source_tree_digest(files + files)


@pytest.mark.parametrize("language", ["java", "python"])
def test_retained_real_export_has_native_roles_and_actual_source_binding(language):
    # Required fixture evidence: absence fails, never silently skips the acceptance check.
    raw = parse_raw_export((FIXTURES / "exports" / f"{language}.json").read_bytes())
    nodes = {n["id"]: n for n in raw["nodes"]}
    edges = raw["edges"]
    kinds = {e["kind"] for e in edges}
    assert {
        "CALL",
        "ARGUMENT",
        "RECEIVER",
        "REF",
        "PARAMETER_LINK",
        "REACHING_DEF",
        "EVAL_TYPE",
    } <= kinds
    assert any(e["properties"].get("VARIABLE") for e in edges if e["kind"] == "REACHING_DEF")
    assert any(n["kind"] == "RETURN" for n in nodes.values())
    assert any(
        n["kind"] == "METHOD_PARAMETER_IN" and type(n["properties"]["INDEX"]) is int
        for n in nodes.values()
    )
    observed_external = [
        n["properties"]["IS_EXTERNAL"]
        for n in nodes.values()
        if n["kind"] == "METHOD" and "IS_EXTERNAL" in n["properties"]
    ]
    assert observed_external and all(type(value) is bool for value in observed_external)
    assert raw["capabilities"]["actual_formal_binding"]["status"] == "unsupported"
    for source_file in raw["producer"]["source"]["files"]:
        source_bytes = (FIXTURES / language / source_file["path"]).read_bytes()
        assert hashlib.sha256(source_bytes).hexdigest() == source_file["sha256"]
        assert len(source_bytes) == source_file["size"]
    assert (
        raw["producer"]["script"]["sha256"]
        == hashlib.sha256(
            (
                Path(__file__).parents[2] / "workers/snapshot/joern-scripts/export_cpg_v2.sc"
            ).read_bytes()
        ).hexdigest()
    )
