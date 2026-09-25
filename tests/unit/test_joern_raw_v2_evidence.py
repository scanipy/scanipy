"""Required real-producer role evidence, including known frontend limitations.

No fixture source is imported or executed. Raw role assertions are deliberately
separate from the validator: a legal raw graph can still lack useful semantics.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path

import pytest

from analysis.cpg_ingest.joern_schema_v2 import EDGE_PROPERTIES, NODE_PROPERTIES
from analysis.cpg_ingest.raw_v2 import (
    RawExportFailedError,
    parse_raw_export,
    validate_raw_export,
)

pytestmark = pytest.mark.unit
FIXTURES = Path(__file__).parents[1] / "fixtures" / "joern_raw_v2"


def _raw(language):
    return parse_raw_export((FIXTURES / "exports" / f"{language}.json").read_bytes())


def _one(raw, kind, **properties):
    matches = [
        n
        for n in raw["nodes"]
        if n["kind"] == kind and all(n["properties"].get(k) == v for k, v in properties.items())
    ]
    assert len(matches) == 1, (kind, properties, len(matches))
    return matches[0]


def _out(raw, node, edge_kind):
    nodes = {n["id"]: n for n in raw["nodes"]}
    return [
        nodes[e["dst"]] for e in raw["edges"] if e["src"] == node["id"] and e["kind"] == edge_kind
    ]


def _formals(raw, method):
    return sorted(
        [n for n in _out(raw, method, "AST") if n["kind"] == "METHOD_PARAMETER_IN"],
        key=lambda n: n["properties"]["INDEX"],
    )


def _assert_shared_roles(raw, *, language):
    statement = _one(raw, "RETURN", CODE="return combined" + (";" if language == "java" else ""))
    (value,) = _out(raw, statement, "ARGUMENT")
    assert value["kind"] == "IDENTIFIER"
    assert value["properties"]["NAME"] == "combined"
    (declaration,) = _out(raw, value, "REF")
    assert declaration["kind"] == "LOCAL"
    assert declaration["properties"]["NAME"] == "combined"
    (exit_node,) = _out(raw, statement, "CFG")
    assert exit_node["kind"] == "METHOD_RETURN"
    (actual_type,) = _out(raw, value, "EVAL_TYPE")
    assert actual_type["kind"] == "TYPE"
    # Actual unavailable type is not replaced with an assumed str/String.
    assert actual_type["properties"]["FULL_NAME"] == "ANY"
    index = _one(raw, "CALL", CODE="values[0]")
    assert index["properties"]["NAME"] == "<operator>.indexAccess"
    operands = {n["properties"]["ARGUMENT_INDEX"]: n for n in _out(raw, index, "ARGUMENT")}
    assert operands[1]["properties"]["CODE"] == "values"
    assert operands[2]["kind"] == "LITERAL"
    assert operands[2]["properties"]["CODE"] == "0"
    field_code = "this.saved" if language == "java" else "self.saved"
    fields = [
        n for n in raw["nodes"] if n["kind"] == "CALL" and n["properties"].get("CODE") == field_code
    ]
    assert fields
    for field in fields:
        assert field["properties"]["NAME"] == "<operator>.fieldAccess"
        operands = {n["properties"]["ARGUMENT_INDEX"]: n for n in _out(raw, field, "ARGUMENT")}
        assert operands[2]["kind"] == "FIELD_IDENTIFIER"
        assert operands[2]["properties"]["CANONICAL_NAME"] == "saved"
        assert operands[1]["kind"] == "IDENTIFIER"
    for name in (
        "call_target_completeness",
        "actual_formal_binding",
        "return_result_binding",
        "effect_analysis",
        "purity_certification",
    ):
        assert raw["capabilities"][name]["status"] == "unsupported"


def _assert_python_roles(raw):
    _assert_shared_roles(raw, language="python")
    call = _one(raw, "CALL", CODE="helper(user_input, values[0])")
    (helper,) = _out(raw, call, "CALL")
    assert helper["properties"]["FULL_NAME"] == "flow.py:<module>.helper"
    assert call["properties"]["DYNAMIC_TYPE_HINT_FULL_NAME"] == [helper["properties"]["FULL_NAME"]]
    formals = _formals(raw, helper)
    assert [(n["properties"]["NAME"], n["properties"]["INDEX"]) for n in formals] == [
        ("left", 1),
        ("right", 2),
    ]
    for formal in formals:
        assert formal["properties"]["EVALUATION_STRATEGY"] == "BY_SHARING"
        (output_formal,) = _out(raw, formal, "PARAMETER_LINK")
        assert output_formal["kind"] == "METHOD_PARAMETER_OUT"
        assert output_formal["properties"]["INDEX"] == formal["properties"]["INDEX"]
    (receiver,) = _out(raw, call, "RECEIVER")
    assert receiver["properties"]["CODE"] == "helper"
    actuals = {
        n["properties"]["ARGUMENT_INDEX"]: n["properties"]["CODE"]
        for n in _out(raw, call, "ARGUMENT")
    }
    assert actuals == {1: "user_input", 2: "values[0]"}
    keyword_call = _one(raw, "CALL", CODE="helper(right = first, left = user_input)")
    keywords = _out(raw, keyword_call, "ARGUMENT")
    assert {n["properties"]["ARGUMENT_NAME"]: n["properties"]["CODE"] for n in keywords} == {
        "left": "user_input",
        "right": "first",
    }
    assert all("ARGUMENT_INDEX" in n["missing_properties"] for n in keywords)
    default_call = _one(raw, "CALL", CODE="helper(second)")
    assert [n["properties"]["CODE"] for n in _out(raw, default_call, "ARGUMENT")] == ["second"]
    # Omitted source-default actual is NOT fabricated by the raw exporter.
    splat = _one(raw, "CALL", CODE='variadic("prefix", *values, **named)')
    arguments = _out(raw, splat, "ARGUMENT")
    assert any(n["properties"].get("NAME") == "<operator>.starredUnpack" for n in arguments)
    assert any(n["properties"].get("ARGUMENT_NAME") == "<keyword_dict>" for n in arguments)
    (variadic,) = _out(raw, splat, "CALL")
    rest = next(n for n in _formals(raw, variadic) if n["properties"]["NAME"] == "rest")
    assert rest["properties"]["IS_VARIADIC"] is True
    execute = _one(raw, "CALL", CODE="self.cursor.execute(self.instance(third))")
    assert execute["properties"]["METHOD_FULL_NAME"] == "<unknownFullName>"
    assert _out(raw, execute, "CALL") == []
    (callee_expression,) = _out(raw, execute, "RECEIVER")
    assert callee_expression["properties"]["CODE"] == "tmp0.execute"
    bound_actuals = {n["properties"]["ARGUMENT_INDEX"]: n for n in _out(raw, execute, "ARGUMENT")}
    assert bound_actuals[0]["properties"]["CODE"] == "tmp0"
    assert bound_actuals[1]["properties"]["CODE"] == "self.instance(third)"
    assert callee_expression["id"] != bound_actuals[0]["id"]
    statement = _one(raw, "RETURN", CODE="return self.cursor.fetchall()")
    (block,) = _out(raw, statement, "ARGUMENT")
    assert block["kind"] == "BLOCK"
    assert block["properties"]["CODE"] == "tmp1 = self.cursor\nself.cursor.fetchall()"
    parallel = [
        e
        for e in raw["edges"]
        if e["kind"] == "REACHING_DEF" and e["src"] == block["id"] and e["dst"] == statement["id"]
    ]
    assert {e["properties"]["VARIABLE"] for e in parallel} == {"", block["properties"]["CODE"]}
    assert len(parallel) == 2


def _assert_java_roles(raw):
    _assert_shared_roles(raw, language="java")
    string_helper = _one(raw, "METHOD", CODE="static String helper(String left, String right)")
    int_helper = _one(raw, "METHOD", CODE="static String helper(int left, String right)")
    assert string_helper["id"] != int_helper["id"]
    assert string_helper["properties"]["FULL_NAME"] == int_helper["properties"]["FULL_NAME"]
    assert string_helper["properties"]["SIGNATURE"] == "<unresolvedSignature>(2)"
    assert string_helper["properties"]["GENERIC_SIGNATURE"] == "(LString;LString;)LString;"
    assert int_helper["properties"]["GENERIC_SIGNATURE"] == "(ILString;)LString;"
    # Preserve the real contradictory candidate instead of claiming resolved overloads.
    overload_call = _one(raw, "CALL", CODE="helper(1, named)")
    assert _out(raw, overload_call, "CALL") == [string_helper]
    for helper in (string_helper, int_helper):
        assert any(
            n["properties"].get("MODIFIER_TYPE") == "STATIC" for n in _out(raw, helper, "AST")
        )
        assert [n["properties"]["INDEX"] for n in _formals(raw, helper)] == [1, 2]
        for formal in _formals(raw, helper):
            (out_formal,) = _out(raw, formal, "PARAMETER_LINK")
            assert out_formal["kind"] == "METHOD_PARAMETER_OUT"
    assert _formals(raw, int_helper)[0]["properties"]["TYPE_FULL_NAME"] == "int"
    assert (
        _formals(raw, string_helper)[0]["properties"]["TYPE_FULL_NAME"]
        == "<unresolvedNamespace>.String"
    )
    assert overload_call["properties"]["DISPATCH_TYPE"] == "DYNAMIC_DISPATCH"
    instance_call = _one(raw, "CALL", CODE="instance(changed)")
    (instance,) = _out(raw, instance_call, "CALL")
    assert [
        (n["properties"]["NAME"], n["properties"]["INDEX"]) for n in _formals(raw, instance)
    ] == [("this", 0), ("value", 1)]
    (receiver,) = _out(raw, instance_call, "RECEIVER")
    actuals = {n["properties"]["ARGUMENT_INDEX"]: n for n in _out(raw, instance_call, "ARGUMENT")}
    assert receiver == actuals[0]
    assert receiver["properties"]["CODE"] == "this"
    assert actuals[1]["properties"]["CODE"] == "changed"
    vararg_call = _one(raw, "CALL", CODE="variadic(result, input, named)")
    (placeholder,) = _out(raw, vararg_call, "CALL")
    assert placeholder["properties"]["IS_EXTERNAL"] is True
    assert placeholder["properties"]["SIGNATURE"] == "<unresolvedSignature>(3)"
    declaration = _one(raw, "METHOD", CODE="static String variadic(String first, String... rest)")
    assert placeholder["id"] != declaration["id"]
    rest = _formals(raw, declaration)[1]
    assert rest["properties"]["CODE"] == "String... rest"
    assert "IS_VARIADIC" in rest["missing_properties"]
    external = _one(raw, "CALL", CODE="apply(value)")
    assert external["properties"]["METHOD_FULL_NAME"].startswith("<unresolvedNamespace>.")
    assert all(n["properties"]["IS_EXTERNAL"] is True for n in _out(raw, external, "CALL"))


def test_real_python_call_arguments_returns_access_paths_and_parallel_variable_payloads():
    _assert_python_roles(_raw("python"))


def test_real_java_roles_preserve_overload_vararg_dispatch_and_type_limitations():
    _assert_java_roles(_raw("java"))


@pytest.mark.parametrize("language", ["python", "java"])
@pytest.mark.parametrize(
    "role", ["CALL", "ARGUMENT", "RECEIVER", "REF", "PARAMETER_LINK", "CFG", "EVAL_TYPE"]
)
def test_real_role_evidence_rejects_dropped_semantic_edges(language, role):
    raw = _raw(language)
    raw["edges"] = [e for e in raw["edges"] if e["kind"] != role]
    validate_raw_export(raw)  # Shape-valid is NOT complete semantic coverage.
    with pytest.raises((AssertionError, ValueError, KeyError)):
        (_assert_python_roles if language == "python" else _assert_java_roles)(raw)


def test_real_variable_payload_cannot_be_dropped_or_parallel_edges_collapsed():
    for mutation in ("drop-variable", "collapse-parallel"):
        raw = _raw("python")
        if mutation == "drop-variable":
            for edge in raw["edges"]:
                if edge["kind"] == "REACHING_DEF":
                    edge["properties"] = {}
        else:
            raw["edges"] = list({(e["src"], e["dst"], e["kind"]): e for e in raw["edges"]}.values())
        validate_raw_export(raw)
        with pytest.raises((AssertionError, KeyError)):
            _assert_python_roles(raw)


def test_real_keyword_name_cannot_be_silently_dropped():
    raw = copy.deepcopy(_raw("python"))
    for node in raw["nodes"]:
        node["properties"].pop("ARGUMENT_NAME", None)
    validate_raw_export(raw)
    with pytest.raises(KeyError):
        _assert_python_roles(raw)


def test_catalog_matches_retained_actual_pinned_graph_schema_probe():
    observed = json.loads((FIXTURES / "schema-catalog.json").read_text())
    native = {"StringType": "str", "IntType": "int", "BoolType": "bool"}
    quantities = {"QtyOne": "one", "QtyOption": "optional", "QtyMulti": "many"}
    assert observed["domain_version"] == "1.7.65"
    assert NODE_PROPERTIES == {
        kind: {key: (native[p["type"]], quantities[p["quantity"]]) for key, p in properties.items()}
        for kind, properties in observed["nodes"].items()
    }
    assert EDGE_PROPERTIES == observed["edges"]


def test_retained_evidence_inventory_and_real_container_safety():
    manifest = json.loads((FIXTURES / "evidence-manifest.json").read_text())
    repository = Path(__file__).parents[2]
    for record in manifest["files"]:
        assert (
            hashlib.sha256((repository / record["path"]).read_bytes()).hexdigest()
            == record["sha256"]
        ), record["path"]
    for case in ("java", "python", "negative", "schema"):
        (container,) = json.loads(
            (FIXTURES / "evidence" / case / "container-inspect.json").read_text()
        )
        assert container["Image"] == manifest["producer_image_id"]
        assert container["State"]["ExitCode"] == 0
        assert container["State"]["OOMKilled"] is False
        assert container["Config"]["User"] == "1000:1000"
        host = container["HostConfig"]
        assert host["NetworkMode"] == "none"
        assert host["ReadonlyRootfs"] is True
        assert host["Memory"] in (3 * 1024**3, 4 * 1024**3)
        assert host["MemorySwap"] == host["Memory"]
        assert host["NanoCpus"] == 2_000_000_000
        assert host["PidsLimit"] == 256
        assert "ALL" in host["CapDrop"]
        assert "no-new-privileges:true" in host["SecurityOpt"]


@pytest.mark.parametrize("language", ["java", "python"])
def test_real_parser_and_export_attempts_bind_source_script_and_actual_image(language):
    raw = _raw(language)
    evidence = FIXTURES / "evidence" / language
    parse = json.loads((evidence / "parse.event.json").read_text())
    export = json.loads((evidence / "export.event.json").read_text())
    producer = raw["producer"]
    assert parse["returncode"] == export["returncode"] == 0
    assert parse["timeout_s"] == export["timeout_s"] == 120
    assert parse["elapsed_seconds"] < 120 and export["elapsed_seconds"] < 120
    assert parse["argv"] == [
        "/opt/joern/joern-parse",
        "--language",
        producer["frontend"],
        "--output",
        producer["input_cpg"]["path"],
        producer["source"]["root"],
    ]
    assert export["argv"] == ["/opt/joern/joern", "--script", producer["script"]["path"]]
    assert export["env"]["SCANIPY_EXPORT_V2_IMAGE_ID"] == producer["image"]["reference"]
    assert export["env"]["SCANIPY_EXPORT_V2_SOURCE_ROOT"] == producer["source"]["root"]
    assert export["env"]["JAVA_TOOL_OPTIONS"] == producer["java_tool_options"]
    assert "SCANIPY_RAW_V2_COMPLETED" in (evidence / "export.stdout").read_text()


def test_real_export_failure_evidence_is_not_a_completed_empty_graph():
    evidence = FIXTURES / "evidence" / "negative"
    for case, reason in (
        ("wrong_frontend", "CPG metadata language does not match declared frontend"),
        ("existing_output", "output already exists"),
        ("symlink_source", "source symlinks are unsupported"),
    ):
        event = json.loads((evidence / f"{case}.event.json").read_text())
        assert event["returncode"] != 0
        assert event["error"] == "CalledProcessError"
        # Preserve trailing blank lines and arbitrary raw process bytes without
        # subjecting them to repository text/EOF normalization.
        wrapper = json.loads((evidence / f"{case}.stderr.json").read_text())
        assert wrapper["format"] == "scanipy-raw-process-bytes"
        assert wrapper["version"] == 1 and wrapper["encoding"] == "base64"
        original = base64.b64decode(wrapper["data"], validate=True)
        assert len(original) == wrapper["byte_length"]
        assert hashlib.sha256(original).hexdigest() == wrapper["sha256"]
        assert reason in original.decode("utf-8")
    raw_bytes = (evidence / "wrong_frontend.json").read_bytes()
    raw = parse_raw_export(raw_bytes, require_completed=False)
    assert raw["nodes"] is raw["edges"] is None
    assert raw["capabilities"]["raw_nodes"]["status"] == "failed"
    with pytest.raises(RawExportFailedError):
        parse_raw_export(raw_bytes)
    outcomes = json.loads((evidence / "outcomes.json").read_text())
    assert (
        outcomes[1]["preserved_sha256"]
        == hashlib.sha256(b"preexisting evidence must not be overwritten\n").hexdigest()
    )
    assert outcomes[2]["envelope"] == "absent_provenance_failure"
