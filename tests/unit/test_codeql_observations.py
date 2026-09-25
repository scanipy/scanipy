"""Controlled CodeQL-style JSON, never native engine or authority evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest

from services.scan import codeql_observations as cq
from services.scan import source_capture as custody

pytestmark = pytest.mark.unit


def report_bytes(results=None, **run_fields):
    run = {
        "tool": {
            "driver": {
                "name": "CodeQL command-line toolchain",
                "version": "2.20.0",
                "rules": [{"id": "py/controlled"}],
            }
        },
        "results": [] if results is None else results,
        **run_fields,
    }
    return json.dumps({"version": "2.1.0", "runs": [run]}).encode()


def test_missing_is_not_empty_and_roundtrip_is_exact():
    missing = cq.parse_codeql_observations(None)
    assert missing.parse_status == "missing"
    assert missing.report is None
    assert missing.returncode is None
    empty = cq.parse_codeql_observations(b"", stdout=b"")
    assert empty.parse_status == "invalid-json"
    assert cq.decode_codeql_observations(cq.encode_codeql_observations(empty)) == empty


def test_duplicate_native_rows_keep_positions():
    result = {
        "ruleId": "py/controlled",
        "ruleIndex": 0,
        "message": {"text": "sample"},
        "locations": [],
    }
    raw = report_bytes([result, result])
    observed = cq.parse_codeql_observations(raw)
    rows = observed.runs[0].results
    assert [r.result_ordinal for r in rows] == [0, 1]
    assert [r.duplicate_ordinal for r in rows] == [0, 1]
    assert rows[0].raw_sha256 == rows[1].raw_sha256
    assert observed.report == raw
    assert cq.decode_codeql_observations(cq.encode_codeql_observations(observed)) == observed


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def inventory_bytes(*paths):
    return canonical(
        {
            "schema": custody.INVENTORY_SCHEMA,
            "files": [
                {"path": path, "size": 0, "sha256": hashlib.sha256(b"").hexdigest()}
                for path in sorted(paths, key=lambda path: path.encode())
            ],
        }
    )


def primary(artifact=None, region=None):
    return {
        "physicalLocation": {
            "artifactLocation": {"uri": "src/a.py"} if artifact is None else artifact,
            "region": {"startLine": 1} if region is None else region,
        }
    }


def result_row(**fields):
    return {
        "ruleId": "py/controlled",
        "message": {"text": "native text"},
        "locations": [primary()],
        **fields,
    }


def observe_result(result=None, **kwargs):
    return cq.parse_codeql_observations(
        report_bytes([result_row() if result is None else result]), **kwargs
    )


def codes(observation):
    return (
        [issue.code for issue in observation.issues]
        + [issue.code for run in observation.runs for issue in run.issues]
        + [issue.code for run in observation.runs for row in run.results for issue in row.issues]
        + [
            issue.code
            for run in observation.runs
            for row in run.results
            for location in row.locations
            for issue in location.issues
        ]
    )


def frame_parts(frame):
    prefix = len(cq._MAGIC)
    length = int.from_bytes(frame[prefix : prefix + 4], "big")
    end = prefix + 4 + length
    return json.loads(frame[prefix + 4 : end]), frame[end:]


def changed_frame(frame, change, *, pretty=False):
    manifest, payload = frame_parts(frame)
    change(manifest)
    raw = json.dumps(manifest).encode() if pretty else canonical(manifest)
    return cq._MAGIC + len(raw).to_bytes(4, "big") + raw + payload


def test_supported_projection_is_not_coverage_or_native_execution():
    observed = observe_result(source_inventory=inventory_bytes("src/a.py"))
    assert observed.format_status == "supported-projection"
    assert observed.runs[0].results[0].rule_join == cq.RuleJoin("matched-driver-rule", 0)
    assert observed.runs[0].results[0].locations[0].path_join == cq.PathJoin(
        "inventory-match", "src/a.py", 0
    )
    for name in ("success", "coverage_complete", "is_finding", "strong", "origin"):
        assert not hasattr(observed, name)
    assert "coordinates-unverified" in codes(observed)
    assert observed.returncode is None


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b" ",
        b"{}{}",
        b"[] x",
        b"NaN",
        b"Infinity",
        b"-Infinity",
        b"[1,]",
        b'{"a":1,"a":2}',
        b'{"outer":{"a":1,"\\u0061":2}}',
        b'"\\ud800"',
        b'"\\udc00"',
        b'"\\ud800\\u0001"',
        b'"\\x20"',
        b'"\xff"',
        b'"\x00"',
        b"\xef\xbb\xbf{}",
        b"01",
        b"+1",
        b"1.",
        b"[truefalse]",
        b'{"a" 1}',
    ],
)
def test_malformed_json_retained_without_prefix(raw):
    observed = cq.parse_codeql_observations(raw, stderr=b"raw\xff error")
    assert observed.parse_status == "invalid-json"
    assert observed.format_status == "not-evaluated"
    assert observed.runs == () and observed.report == raw
    assert cq.decode_codeql_observations(cq.encode_codeql_observations(observed)) == observed


@pytest.mark.parametrize("raw", [b"null", b"true", b"12", b'"text"', b"[]"])
def test_valid_nonobject_root_is_not_invalid_json(raw):
    observed = cq.parse_codeql_observations(raw)
    assert observed.parse_status == "parsed" and observed.format_status == "invalid"
    assert codes(observed) == ["root-shape"]


def test_unknown_large_number_unicode_and_field_spans_remain_verbatim():
    row = (
        b'{"ruleId":"py/controlled","message":{"text":"\\ud83d\\ude42"},'
        b'"locations":[],"opaque":{"n":1e999999,"native":"\xc3\xa9"}}'
    )
    raw = (
        b'{"version":"2.1.0","runs":[{"tool":{"driver":{"name":"X","version":"2.20.0"}},"results":['
        + row
        + b"]}]}"
    )
    observed = cq.parse_codeql_observations(raw)
    result = observed.runs[0].results[0]
    assert raw[result.raw.start : result.raw.end] == row
    assert result.raw_sha256 == hashlib.sha256(row).hexdigest()
    assert [f.name for f in result.fields] == ["ruleId", "message", "locations", "opaque"]
    assert (
        raw[result.fields[-1].value.start : result.fields[-1].value.end]
        == b'{"n":1e999999,"native":"\xc3\xa9"}'
    )
    for field in result.fields:
        assert json.loads(raw[field.key.start : field.key.end]) == field.name
    assert "unknown-field" in codes(observed)
    assert cq.decode_codeql_observations(cq.encode_codeql_observations(observed)).report == raw


def test_all_runs_malformed_rows_and_location_multiplicity_are_retained():
    run = json.loads(report_bytes([7, result_row(locations=[primary(), primary()])]))["runs"][0]
    raw = canonical({"version": "2.1.0", "runs": [run, run, None]})
    observed = cq.parse_codeql_observations(raw)
    assert observed.format_status == "invalid"
    assert len(observed.runs) == 3
    assert observed.runs[0].results[0].fields == ()
    assert len(observed.runs[0].results[1].locations) == 2
    assert observed.runs[1].results[1].run_ordinal == 1
    assert observed.runs[1].results[1].duplicate_ordinal == 0
    assert cq.decode_codeql_observations(cq.encode_codeql_observations(observed)) == observed


@pytest.mark.parametrize("value,status", [(None, "null"), (False, "invalid"), ({}, "invalid")])
def test_missing_null_wrong_results_not_empty(value, status):
    raw = json.loads(report_bytes())
    raw["runs"][0]["results"] = value
    observed = cq.parse_codeql_observations(canonical(raw))
    assert observed.runs[0].results_status == status
    assert observed.format_status == "invalid"
    del raw["runs"][0]["results"]
    assert cq.parse_codeql_observations(canonical(raw)).runs[0].results_status == "missing"


@pytest.mark.parametrize(
    "version,semantic,status",
    [
        (None, None, "unsupported"),
        ("2.19.0", None, "unsupported"),
        ("2.20.0 suffix", None, "unsupported"),
        ("2.20.0", "2.20.0", "supported-projection"),
        (None, "2.20.0", "supported-projection"),
        ("2.20.0", "2.19.0", "invalid"),
        (False, None, "invalid"),
        ("2.20.0", 2, "invalid"),
    ],
)
def test_driver_claims_not_rewritten(version, semantic, status):
    driver = {"name": "untrusted name"}
    for field, value in (("version", version), ("semanticVersion", semantic)):
        if value is not None:
            driver[field] = value
    observed = cq.parse_codeql_observations(report_bytes(tool={"driver": driver}))
    assert observed.format_status == status
    assert observed.report == report_bytes(tool={"driver": driver})


@pytest.mark.parametrize(
    "field,value",
    [
        ("message", None),
        ("message", {"markdown": "only"}),
        ("message", {"id": 3}),
        ("message", {"text": "x", "arguments": [True]}),
        ("kind", "newKind"),
        ("level", False),
        ("baselineState", "deleted"),
        ("guid", 2),
        ("occurrenceCount", True),
        ("occurrenceCount", 0),
        ("occurrenceCount", 1.0),
        ("occurrenceCount", 2**63),
        ("partialFingerprints", []),
        ("fingerprints", {"primaryLocationLineHash": 1}),
        ("taxa", {}),
        ("relatedLocations", None),
        ("codeFlows", "trace"),
        ("locations", {}),
        ("suppressions", [{"kind": "external", "status": "approved"}]),
        ("suppressions", [{}]),
    ],
)
def test_known_result_types_are_not_opaque(field, value):
    assert observe_result(result_row(**{field: value})).format_status == "invalid"


def test_vendor_metadata_is_lossless_not_local_decision_or_reconstructed_multiplicity():
    row = result_row(
        occurrenceCount=100,
        baselineState="absent",
        guid="native-guid",
        correlationGuid="native-correlation",
        partialFingerprints={"a": "1", "b": "2"},
        fingerprints={"unknown-vendor-version": "raw"},
        suppressions=[{"kind": "external", "status": "accepted", "justification": "raw"}],
        properties={"coverage_complete": True, "strong": True},
        codeFlows=[{"threadFlows": [{"locations": [{"index": 0}]}]}],
    )
    observed = observe_result(row)
    assert len(observed.runs[0].results) == 1
    assert "threadflow-reference-unresolved" in codes(observed)
    assert observed.format_status == "unsupported"
    assert json.loads(observed.report)["runs"][0]["results"][0] == row


@pytest.mark.parametrize("index", [True, 0.0, 1e0, -2, 2**63, "0"])
def test_rule_index_rejects_noninteger_or_range(index):
    observed = observe_result(result_row(ruleIndex=index))
    assert observed.format_status == "invalid"
    assert observed.runs[0].results[0].rule_join == cq.RuleJoin("invalid", None)


@pytest.mark.parametrize(
    "fields,status,ordinal",
    [
        ({"ruleIndex": 0}, "matched-driver-rule", 0),
        ({"ruleIndex": -1}, "matched-driver-rule", 0),
        ({"ruleId": "missing"}, "unindexed-id", None),
        ({"ruleId": "wrong", "ruleIndex": 0}, "inconsistent", None),
        ({"ruleIndex": 2}, "invalid", None),
        ({"ruleIndex": 0, "rule": {"index": -1}}, "inconsistent", None),
        ({"rule": {"id": "wrong"}}, "inconsistent", None),
        ({"rule": {"guid": "missing"}}, "inconsistent", None),
        ({"rule": {"toolComponent": {"index": 0}}}, "unsupported-component", None),
    ],
)
def test_rule_reference_agreement(fields, status, ordinal):
    observed = observe_result(result_row(**fields))
    assert observed.runs[0].results[0].rule_join == cq.RuleJoin(status, ordinal)


def test_rule_duplicate_ids_never_first_match_and_available_not_executed():
    driver = {"name": "X", "version": "2.20.0", "rules": [{"id": "py/controlled"}] * 2}
    rows = [result_row(), result_row(ruleIndex=1)]
    observed = cq.parse_codeql_observations(report_bytes(rows, tool={"driver": driver}))
    assert [row.rule_join for row in observed.runs[0].results] == [
        cq.RuleJoin("ambiguous", None),
        cq.RuleJoin("matched-driver-rule", 1),
    ]
    assert cq.parse_codeql_observations(report_bytes(tool={"driver": driver})).runs[0].results == ()


def test_rule_unknown_guid_only_and_explicit_component_with_invalid_index():
    row = result_row(rule={"guid": "not-a-search-key"})
    del row["ruleId"]
    assert observe_result(row).runs[0].results[0].rule_join.status == "missing"
    bad = observe_result(result_row(ruleIndex=True, rule={"toolComponent": {"name": "X"}}))
    assert bad.format_status == "invalid"


@pytest.mark.parametrize(
    "uri",
    [
        "/src/a.py",
        "//server/a",
        "file:///src/a.py",
        "C:/src/a.py",
        "https://x/a",
        "src/../a.py",
        "src/./a.py",
        "src//a.py",
        "src/a.py/",
        "src\\a.py",
        "src/a.py?query",
        "src/a.py#fragment",
        "src%2fa.py",
        "src%5Ca.py",
        "src/%2e%2e/a.py",
        "src/%00a.py",
        "src/%1Fa.py",
        "src/%FFa.py",
        "src/%",
        "src/%0g.py",
        "%2fsrc/a.py",
        "",
        "C%3a/a.py",
    ],
)
def test_unsafe_or_unsupported_uri_never_inventory_match(uri):
    observed = observe_result(
        result_row(locations=[primary({"uri": uri})]), source_inventory=inventory_bytes("src/a.py")
    )
    join = observed.runs[0].results[0].locations[0].path_join
    assert join == cq.PathJoin("unsupported-uri", None, None)


@pytest.mark.parametrize(
    "uri,path",
    [("src/%C3%A9.py", "src/é.py"), ("src/a%23b.py", "src/a#b.py"), ("src/%252e.py", "src/%2e.py")],
)
def test_uri_decodes_once_no_unicode_normalization(uri, path):
    observed = observe_result(
        result_row(locations=[primary({"uri": uri})]), source_inventory=inventory_bytes(path)
    )
    assert observed.runs[0].results[0].locations[0].path_join == cq.PathJoin(
        "inventory-match", path, 0
    )
    mismatch = observe_result(
        result_row(locations=[primary({"uri": "src/é.py"})]),
        source_inventory=inventory_bytes("src/é.py"),
    )
    assert mismatch.runs[0].results[0].locations[0].path_join.status == "outside-inventory"


@pytest.mark.parametrize(
    "artifact",
    [
        {"uri": True},
        {"index": True},
        {"index": 0.0},
        {"uri": "src/a.py", "uriBaseId": False},
        "bad",
    ],
)
def test_known_artifact_shape_is_invalid_not_merely_unmapped(artifact):
    observed = observe_result(result_row(locations=[primary(artifact)]))
    assert observed.format_status == "invalid"


def test_indexed_artifacts_and_inline_base_must_agree():
    artifacts = [{"location": {"uri": "src/a.py", "uriBaseId": "ROOT"}}]
    rows = [
        result_row(locations=[primary(artifact)])
        for artifact in (
            {"index": 0},
            {"index": 0, "uri": "src/a.py", "uriBaseId": "ROOT"},
            {"index": 0, "uri": "src/a.py"},
            {"index": 0, "uri": "src/b.py", "uriBaseId": "ROOT"},
        )
    ]
    observed = cq.parse_codeql_observations(
        report_bytes(rows, artifacts=artifacts),
        source_inventory=inventory_bytes("src/a.py"),
        source_root_aliases=("ROOT",),
    )
    assert [row.locations[0].path_join.status for row in observed.runs[0].results] == [
        "inventory-match",
        "inventory-match",
        "inconsistent",
        "inconsistent",
    ]


def test_alias_is_data_assertion_not_fs_or_base_chain_resolution():
    row = result_row(locations=[primary({"uri": "src/a.py", "uriBaseId": "ROOT"})])
    raw = report_bytes([row], originalUriBaseIds={"ROOT": {"uri": "file:///untrusted/"}})
    kwargs = {"source_inventory": inventory_bytes("src/a.py")}
    assert (
        cq.parse_codeql_observations(raw, **kwargs).runs[0].results[0].locations[0].path_join.status
        == "unsupported-base"
    )
    assert (
        cq.parse_codeql_observations(raw, source_root_aliases=("ROOT",), **kwargs)
        .runs[0]
        .results[0]
        .locations[0]
        .path_join.status
        == "inventory-match"
    )
    chained = report_bytes([row], originalUriBaseIds={"ROOT": {"uriBaseId": "OTHER"}})
    assert (
        cq.parse_codeql_observations(chained, source_root_aliases=("ROOT",), **kwargs)
        .runs[0]
        .results[0]
        .locations[0]
        .path_join.status
        == "unsupported-base"
    )


@pytest.mark.parametrize(
    "region",
    [
        {"startLine": True},
        {"startLine": 0},
        {"startLine": 1.0},
        {"startLine": 2**63},
        {"startLine": 2, "endLine": 1},
        {"startLine": 1, "startColumn": 3, "endColumn": 2},
        {"startLine": 1, "byteOffset": -2},
        {"charOffset": 2**63 - 1, "charLength": 1},
        {"endLine": 1},
        {"startColumn": 1},
        {},
        "region",
    ],
)
def test_coordinates_known_invalid_without_filling_defaults(region):
    assert observe_result(result_row(locations=[primary(region=region)])).format_status == "invalid"


def test_native_execution_failure_and_channel_contradictions_survive():
    raw = report_bytes(
        invocations=[
            {
                "executionSuccessful": False,
                "exitCode": 0,
                "toolExecutionNotifications": [{"level": "error", "message": {"text": "raw"}}],
            }
        ]
    )
    observed = cq.parse_codeql_observations(raw, returncode=0, stdout=b"ok", stderr=b"error")
    assert observed.returncode == 0 and observed.runs[0].results == ()
    assert codes(observed).count("native-execution-failure") == 2
    assert cq.decode_codeql_observations(cq.encode_codeql_observations(observed)) == observed


@pytest.mark.parametrize(
    "invocation",
    [
        {},
        {"executionSuccessful": 1},
        {"executionSuccessful": True, "exitCode": 1.0},
        {"executionSuccessful": True, "exitCode": 2**31},
    ],
)
def test_invocation_claim_types(invocation):
    assert (
        cq.parse_codeql_observations(report_bytes(invocations=[invocation])).format_status
        == "invalid"
    )


def test_actual_custody_inventory_cross_codec_without_source_execution(tmp_path):
    source, store = tmp_path / "source", tmp_path / "store"
    source.mkdir(mode=0o700)
    store.mkdir(mode=0o700)
    # Test-owned inert bytes; no source interpreter is invoked.
    (source / "é.py").write_bytes(b"never executed\x00\xff")
    (source / "é.py").chmod(0o600)
    binding = custody.CaptureBinding(UUID(int=1), UUID(int=2), UUID(int=3), "1" * 40)
    receipt = custody.LocalSourceCaptureStore(store).capture(source, binding)
    observed = observe_result(
        result_row(locations=[primary({"uri": "%C3%A9.py"})]),
        source_inventory=receipt.inventory_bytes,
    )
    assert observed.inventory_status == "valid-data"
    assert observed.runs[0].results[0].locations[0].path_join.source_path == "é.py"
    manifest, _ = frame_parts(cq.encode_codeql_observations(observed))
    assert (
        manifest["parts"]["source_inventory"]["sha256"]
        == hashlib.sha256(receipt.inventory_bytes).hexdigest()
    )
    assert manifest["parts"]["source_inventory"]["sha256"] != receipt.inventory_digest.hex()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda doc: doc.update(schema="wrong"),
        lambda doc: doc.update(extra=1),
        lambda doc: doc["files"].append(doc["files"][0]),
        lambda doc: doc["files"][0].update(path="../escape"),
        lambda doc: doc["files"][0].update(path="/absolute"),
        lambda doc: doc["files"][0].update(path="a\\b"),
        lambda doc: doc["files"][0].update(size=True),
        lambda doc: doc["files"][0].update(size=64 * 1024**2 + 1),
        lambda doc: doc["files"][0].update(sha256="F" * 64),
    ],
)
def test_invalid_inventory_retained_not_empty(mutation):
    doc = json.loads(inventory_bytes("src/a.py"))
    mutation(doc)
    data = canonical(doc)
    observed = observe_result(source_inventory=data)
    assert observed.inventory_status == "invalid-data"
    assert observed.source_inventory == data
    assert observed.runs[0].results[0].locations[0].path_join.status == "invalid"
    assert cq.decode_codeql_observations(cq.encode_codeql_observations(observed)) == observed


def test_noncanonical_and_unsorted_inventory_not_accepted():
    doc = json.loads(inventory_bytes("a", "b"))
    assert (
        cq.parse_codeql_observations(
            None, source_inventory=json.dumps(doc).encode()
        ).inventory_status
        == "invalid-data"
    )
    doc["files"].reverse()
    assert (
        cq.parse_codeql_observations(None, source_inventory=canonical(doc)).inventory_status
        == "invalid-data"
    )


@pytest.mark.parametrize(
    "aliases",
    [
        ["ROOT"],
        ("B", "A"),
        ("A", "A"),
        ("",),
        ("a\x00",),
        ("é" * 65,),
        ("x" * 129,),
        (True,),
        ("\ud800",),
    ],
)
def test_aliases_are_bounded_exact_data(aliases):
    with pytest.raises(cq.CodeQLInputError):
        cq.parse_codeql_observations(None, source_root_aliases=aliases)


@pytest.mark.parametrize("field,ceiling", cq._LIMITS)
@pytest.mark.parametrize("value", [False, 0, -1, 1.0, "1", None])
def test_every_limit_requires_exact_positive_integer(field, ceiling, value):
    with pytest.raises(cq.CodeQLInputError):
        cq.CodeQLObservationLimits(**{field: value})


@pytest.mark.parametrize("field,ceiling", cq._LIMITS)
def test_limit_cannot_exceed_profile_ceiling(field, ceiling):
    with pytest.raises(cq.CodeQLInputError):
        cq.CodeQLObservationLimits(**{field: ceiling + 1})
    assert getattr(cq.CodeQLObservationLimits(**{field: ceiling}), field) == ceiling


@pytest.mark.parametrize(
    "field,keyword",
    [
        ("max_report_bytes", "report"),
        ("max_stdout_bytes", "stdout"),
        ("max_stderr_bytes", "stderr"),
        ("max_inventory_bytes", "source_inventory"),
    ],
)
def test_raw_byte_n_and_n_plus_one(field, keyword):
    limits = cq.CodeQLObservationLimits(**{field: 3})
    kwargs = {"report": None, "limits": limits, keyword: b"123"}
    cq.parse_codeql_observations(**kwargs)
    kwargs[keyword] = b"1234"
    with pytest.raises(cq.CodeQLLimitError):
        cq.parse_codeql_observations(**kwargs)


@pytest.mark.parametrize(
    "raw,limits,extra",
    [
        (b"[[0]]", {"max_depth": 1}, b"[0]"),
        (b'{"k":1}', {"max_values": 2}, b"[1]"),
        (b'"\\u00e9x"', {"max_string_bytes": 2}, b'"\\u00e9"'),
        (b"1234", {"max_number_bytes": 3}, b"123"),
    ],
)
def test_parser_caps_admitted_before_completed_prefix(raw, limits, extra):
    policy = cq.CodeQLObservationLimits(**limits)
    cq.parse_codeql_observations(extra, limits=policy)
    with pytest.raises(cq.CodeQLLimitError):
        cq.parse_codeql_observations(raw, limits=policy)


def test_json_value_counter_shared_with_inventory_and_replay_not_manifest():
    inventory = inventory_bytes()
    # inventory object + two keys + string + empty array = 5, report[] = 1.
    policy = cq.CodeQLObservationLimits(max_values=6)
    observed = cq.parse_codeql_observations(b"[]", source_inventory=inventory, limits=policy)
    frame = cq.encode_codeql_observations(observed)
    assert cq.decode_codeql_observations(frame) == observed
    with pytest.raises(cq.CodeQLLimitError):
        cq.parse_codeql_observations(
            b"[]", source_inventory=inventory, limits=replace(policy, max_values=5)
        )


@pytest.mark.parametrize(
    "name,run_field,rows",
    [
        ("max_results", "results", [None, None]),
        (
            "max_rules",
            "tool",
            {"driver": {"name": "X", "version": "2.20.0", "rules": [{"id": "a"}, {"id": "a"}]}},
        ),
        ("max_artifacts", "artifacts", [{}, {}]),
    ],
)
def test_native_counts_include_malformed_duplicate_and_unused_rows(name, run_field, rows):
    raw = json.loads(report_bytes())
    raw["runs"][0][run_field] = rows
    cq.parse_codeql_observations(canonical(raw), limits=cq.CodeQLObservationLimits(**{name: 2}))
    with pytest.raises(cq.CodeQLLimitError):
        cq.parse_codeql_observations(canonical(raw), limits=cq.CodeQLObservationLimits(**{name: 1}))


def test_counts_aggregate_across_runs_and_extensions():
    run = json.loads(report_bytes([result_row()]))["runs"][0]
    raw = canonical({"version": "2.1.0", "runs": [run, run]})
    with pytest.raises(cq.CodeQLLimitError, match="results"):
        cq.parse_codeql_observations(raw, limits=cq.CodeQLObservationLimits(max_results=1))
    with pytest.raises(cq.CodeQLLimitError, match="runs"):
        cq.parse_codeql_observations(raw, limits=cq.CodeQLObservationLimits(max_runs=1))
    run["tool"]["extensions"] = [{"rules": [{"id": "extension"}]}]
    with pytest.raises(cq.CodeQLLimitError, match="rules"):
        cq.parse_codeql_observations(
            canonical({"version": "2.1.0", "runs": [run]}),
            limits=cq.CodeQLObservationLimits(max_rules=1),
        )


def test_each_raw_result_element_size_not_only_objects():
    row = "abcdefgh"
    raw = report_bytes([row])
    size = len(json.dumps(row).encode())
    cq.parse_codeql_observations(raw, limits=cq.CodeQLObservationLimits(max_result_bytes=size))
    with pytest.raises(cq.CodeQLLimitError):
        cq.parse_codeql_observations(
            raw, limits=cq.CodeQLObservationLimits(max_result_bytes=size - 1)
        )


def test_inventory_files_and_decoded_source_path_caps():
    with pytest.raises(cq.CodeQLLimitError, match="inventory-files"):
        cq.parse_codeql_observations(
            None,
            source_inventory=inventory_bytes("a", "b"),
            limits=cq.CodeQLObservationLimits(max_inventory_files=1),
        )
    with pytest.raises(cq.CodeQLLimitError, match="source-path"):
        cq.parse_codeql_observations(
            None,
            source_inventory=inventory_bytes("éé"),
            limits=cq.CodeQLObservationLimits(max_source_path_bytes=3),
        )
    with pytest.raises(cq.CodeQLLimitError):
        observe_result(
            result_row(locations=[primary({"uri": "%C3%A9%C3%A9"})]),
            limits=cq.CodeQLObservationLimits(max_source_path_bytes=3),
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda view: replace(view, profile="wrong"),
        lambda view: replace(view, parse_status="missing"),
        lambda view: replace(view, format_status="supported-projection"),
        lambda view: replace(view, inventory_status="valid-data"),
        lambda view: replace(view, runs=()),
        lambda view: replace(view, issues=(cq.Issue("native-execution-failure", None),)),
        lambda view: replace(view, runs=(replace(view.runs[0], ordinal=True),)),
        lambda view: replace(view, runs=(replace(view.runs[0], results=()),)),
        lambda view: replace(view, runs=(replace(view.runs[0], results=view.runs[0].results * 2),)),
        lambda view: replace(view, runs=(replace(view.runs[0], results_status="missing"),)),
        lambda view: replace(view, runs=(replace(view.runs[0], fields=view.runs[0].fields[::-1]),)),
    ],
)
def test_encoder_revalidates_complete_view_not_only_payload(mutation):
    view = observe_result(result_row(locations=[]))
    with pytest.raises(cq.CodeQLInputError):
        cq.encode_codeql_observations(mutation(view))


@pytest.mark.parametrize(
    "field,value",
    [
        ("run_ordinal", 1),
        ("result_ordinal", False),
        ("duplicate_ordinal", 1),
        ("raw", cq.ByteSpan(0, 1)),
        ("raw_sha256", "0" * 64),
        ("fields", ()),
        ("rule_join", cq.RuleJoin("matched-driver-rule", True)),
        ("locations", ()),
        ("issues", (cq.Issue("unknown-field", cq.ByteSpan(0, 1)),)),
    ],
)
def test_mutated_result_carrier_never_ignored(field, value):
    observed = observe_result()
    object.__setattr__(observed.runs[0].results[0], field, value)
    with pytest.raises(cq.CodeQLInputError):
        cq.encode_codeql_observations(observed)


@pytest.mark.parametrize(
    "field,value",
    [
        ("ordinal", True),
        ("raw", cq.ByteSpan(0, 0)),
        ("fields", ()),
        ("path_join", cq.PathJoin("inventory-match", "src/a.py", 0)),
        ("region", None),
        ("issues", ()),
    ],
)
def test_mutated_location_carrier_never_ignored(field, value):
    observed = observe_result()
    object.__setattr__(observed.runs[0].results[0].locations[0], field, value)
    with pytest.raises(cq.CodeQLInputError):
        cq.encode_codeql_observations(observed)


def test_nested_span_and_field_mutations_and_cycles():
    for mode in ("span", "field", "cycle", "storage", "limits"):
        observed = observe_result()
        if mode == "span":
            object.__setattr__(observed.runs[0].results[0].raw, "start", True)
        elif mode == "field":
            object.__setattr__(observed.runs[0].fields[0], "name", "wrong")
        elif mode == "cycle":
            object.__setattr__(observed, "runs", (observed,))
        elif mode == "storage":
            object.__delattr__(observed.runs[0], "ordinal")
        else:
            object.__delattr__(observed.limits, "max_runs")
        with pytest.raises(cq.CodeQLInputError):
            cq.encode_codeql_observations(observed)


class Poison:
    def __getattribute__(self, name):
        raise AssertionError("untrusted attribute callback")

    def __eq__(self, other):
        raise AssertionError("untrusted equality callback")

    def __repr__(self):
        raise AssertionError("untrusted repr callback")

    def __iter__(self):
        raise AssertionError("untrusted iterator callback")


@pytest.mark.parametrize("field", ["report", "limits", "runs", "returncode", "profile"])
def test_carrier_callbacks_never_invoked(field):
    observed = observe_result()
    object.__setattr__(observed, field, Poison())
    with pytest.raises(cq.CodeQLInputError):
        cq.encode_codeql_observations(observed)


def test_exact_primitive_subtypes_rejected_without_callbacks():
    class BytesSubclass(bytes):
        def __len__(self):
            raise AssertionError("len callback")

    class StringSubclass(str):
        def encode(self, *args, **kwargs):
            raise AssertionError("encode callback")

    class TupleSubclass(tuple):
        def __iter__(self):
            raise AssertionError("iter callback")

    for kwargs in (
        {"report": BytesSubclass(b"{}")},
        {"report": None, "source_root_aliases": (StringSubclass("ROOT"),)},
        {"report": None, "source_root_aliases": TupleSubclass(("ROOT",))},
    ):
        with pytest.raises(cq.CodeQLInputError):
            cq.parse_codeql_observations(**kwargs)


def test_snapshot_detaches_before_reparse_without_rereading_mutated_caller(monkeypatch):
    observed = observe_result()
    original = cq.parse_codeql_observations
    expected = cq.encode_codeql_observations(observed)

    def mutate_then_parse(*args, **kwargs):
        object.__setattr__(observed.runs[0], "results", ())
        object.__setattr__(observed, "report", Poison())
        return original(*args, **kwargs)

    monkeypatch.setattr(cq, "parse_codeql_observations", mutate_then_parse)
    assert cq.encode_codeql_observations(observed) == expected


def test_forged_view_aggregate_tuple_rejected_before_iteration():
    observed = observe_result()
    object.__setattr__(observed, "runs", (observed.runs[0],) * 9)
    with pytest.raises(cq.CodeQLLimitError, match="view-sequence"):
        cq.encode_codeql_observations(observed)


def test_archive_exact_parts_missing_and_empty_are_different():
    observed = cq.parse_codeql_observations(None, stdout=b"", stderr=b"\x00\xff", returncode=-9)
    frame = cq.encode_codeql_observations(observed)
    manifest, payload = frame_parts(frame)
    assert manifest["parts"]["report"] is None
    assert manifest["parts"]["stdout"] == {"length": 0, "sha256": hashlib.sha256(b"").hexdigest()}
    assert payload == b"\x00\xff"
    assert cq.encode_codeql_observations(cq.decode_codeql_observations(frame)) == frame


@pytest.mark.parametrize(
    "mutation",
    [
        lambda m: m.update(schema="other"),
        lambda m: m.update(profile="other"),
        lambda m: m.update(extra=1),
        lambda m: m.pop("returncode"),
        lambda m: m.update(returncode=True),
        lambda m: m.update(returncode=2**31),
        lambda m: m["parts"].update(other=None),
        lambda m: m["parts"].pop("stderr"),
        lambda m: m["parts"]["report"].update(extra=1),
        lambda m: m["parts"]["report"].update(length=True),
        lambda m: m["parts"]["report"].update(length=-1),
        lambda m: m["parts"]["report"].update(sha256="0" * 64),
        lambda m: m["parts"]["report"].update(sha256="F" * 64),
        lambda m: m["limits"].update(max_runs=True),
        lambda m: m["limits"].update(max_runs=9),
        lambda m: m["limits"].pop("max_runs"),
        lambda m: m.update(source_root_aliases=["B", "A"]),
        lambda m: m.update(source_root_aliases=[False]),
    ],
)
def test_archive_closed_manifest_and_raw_hashes(mutation):
    frame = cq.encode_codeql_observations(observe_result())
    with pytest.raises(cq.CodeQLInputError):
        cq.decode_codeql_observations(changed_frame(frame, mutation))


def test_archive_eof_canonical_header_and_separate_manifest_limits():
    frame = cq.encode_codeql_observations(observe_result())
    for candidate in (
        frame + b"x",
        frame + frame,
        frame[:-1],
        b"other" + frame,
        cq._MAGIC + (65537).to_bytes(4, "big"),
        changed_frame(frame, lambda m: None, pretty=True),
    ):
        with pytest.raises(cq.CodeQLInputError):
            cq.decode_codeql_observations(candidate)
    manifest, payload = frame_parts(frame)
    raw = canonical(manifest)
    duplicate = b'{"schema":"duplicate",' + raw[1:]
    with pytest.raises(cq.CodeQLArchiveError, match="manifest-json"):
        cq.decode_codeql_observations(
            cq._MAGIC + len(duplicate).to_bytes(4, "big") + duplicate + payload
        )


def test_archive_stored_limits_not_relaxed_or_relabeled():
    policy = cq.CodeQLObservationLimits(max_runs=2)
    observed = observe_result(limits=policy)
    frame = cq.encode_codeql_observations(observed)
    assert cq.decode_codeql_observations(frame).limits == policy
    with pytest.raises(cq.CodeQLArchiveError, match="stored-limits"):
        cq.decode_codeql_observations(frame, limits=replace(policy, max_runs=1))
    with pytest.raises(cq.CodeQLArchiveError, match="stored-limits"):
        cq.encode_codeql_observations(observed, limits=replace(policy, max_runs=1))
    # Rewriting a stored limit cannot legitimize an over-limit actual payload.
    with pytest.raises(cq.CodeQLLimitError):
        cq.decode_codeql_observations(
            changed_frame(frame, lambda m: m["limits"].update(max_report_bytes=1))
        )


def test_archive_output_budget_before_join_and_input_budget_before_parse(monkeypatch):
    observed = observe_result(limits=cq.CodeQLObservationLimits(max_archive_bytes=10))
    with pytest.raises(cq.CodeQLLimitError):
        cq.encode_codeql_observations(observed)
    frame = cq.encode_codeql_observations(observe_result())
    with pytest.raises(cq.CodeQLLimitError):
        cq.decode_codeql_observations(
            frame, limits=cq.CodeQLObservationLimits(max_archive_bytes=len(frame) - 1)
        )
    observed = observe_result(limits=cq.CodeQLObservationLimits(max_manifest_bytes=1))
    monkeypatch.setattr(
        cq.json,
        "dumps",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("unadmitted JSON allocation")),
    )
    with pytest.raises(cq.CodeQLLimitError):
        cq.encode_codeql_observations(observed)


def test_no_files_processes_network_dynamic_schema_or_source_execution(monkeypatch):
    import builtins
    import socket
    import subprocess

    raw = report_bytes(
        [result_row()],
        externalPropertyFileReferences={
            "results": [{"location": {"uri": "https://bad.invalid/payload"}}]
        },
    )
    raw = raw.replace(b'"version":', b'"$schema":"https://bad.invalid/schema","version":', 1)

    def forbidden(*args, **kwargs):
        raise AssertionError("pure codec attempted external access")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    observed = cq.parse_codeql_observations(raw, source_inventory=inventory_bytes("src/a.py"))
    assert observed.format_status == "unsupported"
    assert cq.decode_codeql_observations(cq.encode_codeql_observations(observed)) == observed


@pytest.mark.parametrize(
    "index,status",
    [
        (False, "invalid"),
        (0.0, "invalid"),
        (-2, "invalid"),
        (2**63, "invalid"),
        (0, "unsupported"),
        (-1, "supported-projection"),
    ],
)
def test_interpreted_threadflow_index_has_exact_integer_domain(index, status):
    row = result_row(codeFlows=[{"threadFlows": [{"locations": [{"index": index}]}]}])
    assert observe_result(row).format_status == status


@pytest.mark.parametrize("kind", ["depth", "values", "number", "string"])
def test_manifest_has_independent_fixed_preparse_limits(kind):
    if kind == "depth":
        raw = b"[" * 10 + b"0" + b"]" * 10
    elif kind == "values":
        raw = b"[" + b"0," * 256 + b"0]"
    elif kind == "number":
        raw = b"1" * 129
    else:
        # Header admission happens before parsing an above-cap escaped string.
        raw = b'"' + b"a" * 65536 + b'"'
    with pytest.raises(cq.CodeQLLimitError):
        cq.decode_codeql_observations(cq._MAGIC + len(raw).to_bytes(4, "big") + raw)


def test_unicode_key_budget_is_checked_before_materialization():
    with pytest.raises(cq.CodeQLLimitError, match="json-string"):
        cq.parse_codeql_observations(
            b'{"\\u00e9\\u00e9":0}', limits=cq.CodeQLObservationLimits(max_string_bytes=3)
        )
    with pytest.raises(cq.CodeQLLimitError, match="source-root-aliases"):
        cq.parse_codeql_observations(None, source_root_aliases=tuple(str(i) for i in range(9)))


@pytest.mark.parametrize("field,ceiling", cq._LIMITS)
def test_postconstruction_limit_mutations_rejected_before_payload(field, ceiling):
    policy = cq.CodeQLObservationLimits()
    object.__setattr__(policy, field, True)
    with pytest.raises(cq.CodeQLInputError, match="invalid-limit"):
        cq.parse_codeql_observations(Poison(), limits=policy)


def test_carrier_subclass_and_hostile_metaclass_do_not_run_callbacks():
    class HostileMeta(type):
        def __hash__(cls):
            raise AssertionError("metaclass hash callback")

        def __eq__(cls, other):
            raise AssertionError("metaclass equality callback")

    class Hostile(metaclass=HostileMeta):
        pass

    observed = observe_result()
    object.__setattr__(observed, "runs", (Hostile(),))
    with pytest.raises(cq.CodeQLArchiveError, match="invalid-view-type"):
        cq.encode_codeql_observations(observed)


def test_coordinate_forms_and_opaque_metadata_have_no_invented_defaults():
    row = result_row(
        locations=[primary(region={"charOffset": 0, "charLength": 3, "byteOffset": -1})],
        properties={"opaque": {"native": [1, None, False]}},
    )
    raw = report_bytes(
        [row],
        columnKind="utf16CodeUnits",
        language="en-US",
        newlineSequences=["\r\n", "\n"],
        artifacts=[{"sourceLanguage": "python", "contents": {"binary": "AAAA"}}],
    )
    observed = cq.parse_codeql_observations(raw)
    location = observed.runs[0].results[0].locations[0]
    assert location.region is not None
    assert json.loads(raw[location.region.start : location.region.end]) == {
        "charOffset": 0,
        "charLength": 3,
        "byteOffset": -1,
    }
    assert observed.format_status == "supported-projection"
    assert observed.report == raw


def test_byte_identical_duplicate_count_does_not_canonicalize_native_json():
    row = b'{"message":{"text":"x"},"locations":[]}'
    alternate = b'{"message": {"text":"x"}, "locations": []}'
    run = b'{"tool":{"driver":{"name":"X","version":"2.20.0"}},"results":['
    raw = b'{"version":"2.1.0","runs":[' + run + b",".join((row, alternate, row)) + b"]}]}"
    rows = cq.parse_codeql_observations(raw).runs[0].results
    assert [item.duplicate_ordinal for item in rows] == [0, 0, 1]
    assert rows[0].raw_sha256 == rows[2].raw_sha256 != rows[1].raw_sha256


@pytest.mark.parametrize("placement", ["direct", "chained", "indexed", "indexed-chained"])
@pytest.mark.parametrize("uri", [False, "src/a.py"])
def test_invalid_uri_precedence_survives_unsupported_base(placement, uri):
    artifact = {"uri": uri, "uriBaseId": "ROOT"}
    run_fields = {}
    aliases = ()
    if "chained" in placement:
        aliases = ("ROOT",)
        run_fields["originalUriBaseIds"] = {"ROOT": {"uriBaseId": "OTHER"}}
    if "indexed" in placement:
        run_fields["artifacts"] = [{"location": artifact}]
        artifact = {"index": 0}
    raw = report_bytes([result_row(locations=[primary(artifact)])], **run_fields)
    view = cq.parse_codeql_observations(
        raw, source_inventory=inventory_bytes("src/a.py"), source_root_aliases=aliases
    )
    join = view.runs[0].results[0].locations[0].path_join
    assert view.report == raw and join.source_path is None
    if uri is False:
        assert join.status in ("invalid", "inconsistent")
        assert view.format_status == "invalid"
    else:
        assert join.status == "unsupported-base"
        assert view.format_status == "supported-projection"
    assert cq.decode_codeql_observations(cq.encode_codeql_observations(view)) == view


def test_indexed_inline_contradiction_not_masked_by_unknown_base():
    row = result_row(locations=[primary({"index": 0, "uri": "src/wrong.py", "uriBaseId": "ROOT"})])
    raw = report_bytes([row], artifacts=[{"location": {"uri": "src/a.py", "uriBaseId": "ROOT"}}])
    view = cq.parse_codeql_observations(raw, source_inventory=inventory_bytes("src/a.py"))
    assert view.format_status == "invalid"
    assert view.runs[0].results[0].locations[0].path_join == cq.PathJoin("inconsistent", None, None)


@pytest.mark.parametrize("point", [0, 31, 32, 126, 127, 128, 133, 159, 160])
@pytest.mark.parametrize("domain", ["inventory", "alias", "literal-uri", "escaped-uri"])
def test_control_ranges_and_boundary_scalars_across_all_path_inputs(point, domain):
    character = chr(point)
    forbidden = point < 32 or 127 <= point <= 159
    path = "src/" + character + "a.py"
    inventory = inventory_bytes(path)
    if domain == "alias":
        aliases = ("ROOT" + character,)
        if forbidden:
            with pytest.raises(cq.CodeQLInputError):
                cq.parse_codeql_observations(None, source_root_aliases=aliases)
        else:
            view = cq.parse_codeql_observations(None, source_root_aliases=aliases)
            assert view.source_root_aliases == aliases
        return
    if domain == "inventory":
        view = cq.parse_codeql_observations(None, source_inventory=inventory)
        assert view.source_inventory == inventory
        assert view.inventory_status == ("invalid-data" if forbidden else "valid-data")
        assert cq.decode_codeql_observations(cq.encode_codeql_observations(view)) == view
        return
    encoded = "".join(f"%{byte:02X}" for byte in character.encode())
    uri = "src/" + (encoded if domain == "escaped-uri" else character) + "a.py"
    raw = report_bytes([result_row(locations=[primary({"uri": uri})])])
    view = cq.parse_codeql_observations(raw, source_inventory=inventory)
    join = view.runs[0].results[0].locations[0].path_join
    assert view.report == raw
    assert join.status == ("unsupported-uri" if forbidden else "inventory-match")
    assert join.source_path == (None if forbidden else path)
    assert cq.decode_codeql_observations(cq.encode_codeql_observations(view)) == view
