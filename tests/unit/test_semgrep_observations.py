"""Data-only parser falsifiers; no test invokes Semgrep or executes scanned source."""

from __future__ import annotations

import hashlib
import json
import random
import socket
import subprocess
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from services.scan.semgrep_observations import (
    ObservationInputError,
    ObservationLimitError,
    ObservationLimits,
    parse_semgrep_observations,
)

pytestmark = pytest.mark.unit


def native(**updates):
    result = {
        "check_id": "controlled.rule",
        "path": "src/é.py",
        "start": {"line": 2, "col": 3, "offset": 8},
        "end": {"line": 2, "col": 9, "offset": 14},
        "extra": {"message": "observed message", "severity": "ERROR", "metadata": {}},
    }
    result.update(updates)
    return result


def encode(value, *, ascii=False):
    return json.dumps(value, ensure_ascii=ascii, separators=(",", ":")).encode()


def report(results=(), **updates):
    value = {
        "version": "1.175.0",
        "results": list(results),
        "errors": [],
        "paths": {"scanned": ["src/é.py"], "skipped": []},
        "rules_by_engine": [["controlled.rule", "OSS"]],
        "engine_requested": "OSS",
        "skipped_rules": [],
    }
    value.update(updates)
    return encode(value)


def test_exact_raw_spans_multiplicity_native_severity_and_fixed_origin():
    first = encode(native(extra={"message": '  é😀 \\ " [] {} results  \n', "severity": "ERROR"}))
    whitespace_variant = json.dumps(json.loads(first), ensure_ascii=True, indent=2).encode()
    raw = (
        b'{ "results" : [ \n'
        + first
        + b", "
        + whitespace_variant
        + b","
        + first
        + b' ], "version":"1.175.0" }'
    )
    observed = parse_semgrep_observations(raw, b"raw stderr\x00\xff", 1)
    assert observed.parse_status == "parsed"
    assert observed.result_count == 3
    assert [entry.tool_ordinal for entry in observed.results] == [0, 1, 2]
    assert [entry.duplicate_ordinal for entry in observed.results] == [0, 0, 1]
    assert [entry.raw.data for entry in observed.results] == [first, whitespace_variant, first]
    assert observed.results[0].raw_result_key == observed.results[2].raw_result_key
    assert observed.results[0].raw_result_key != observed.results[1].raw_result_key
    for entry in observed.results:
        assert raw[entry.raw.start : entry.raw.end] == entry.raw.data
        assert entry.raw.sha256 == hashlib.sha256(entry.raw.data).hexdigest()
        assert entry.projection.engine == "semgrep"
        assert entry.projection.origin == "oracle-passthrough"
        assert entry.projection.severity == "ERROR"
        assert entry.projection.message == json.loads(first)["extra"]["message"]
    assert observed.stdout_sha256 == hashlib.sha256(raw).hexdigest()
    assert observed.stdout_byte_length == len(raw)
    assert observed.stderr == b"raw stderr\x00\xff"
    assert observed.stderr_byte_length == len(observed.stderr)
    assert observed.stderr_sha256 == hashlib.sha256(observed.stderr).hexdigest()
    assert observed.coverage_status == "unverified"


@pytest.mark.parametrize("code", [0, 1, 2, 7, -9, -(2**31), 2**31 - 1])
def test_exit_codes_never_certify_complete_coverage(code):
    parsed = parse_semgrep_observations(report([native()]), b"", code)
    assert parsed.returncode == code
    assert parsed.version_status == "matched"
    assert parsed.coverage_status == "unverified"
    with pytest.raises(TypeError):
        replace(parsed, coverage_status="complete")


@pytest.mark.parametrize(
    "severity",
    ["ERROR", "WARNING", "EXPERIMENT", "INVENTORY", "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"],
)
def test_full_native_severity_vocabulary_is_not_the_legacy_ui_mapping(severity):
    parsed = parse_semgrep_observations(
        report([native(extra={"message": "", "severity": severity})]), b"", 0
    )
    assert parsed.results[0].projection.severity == severity
    assert parsed.results[0].projection.message == ""


@pytest.mark.parametrize("bad", [None, True, [], 42, {}, {"extra": None}])
def test_malformed_entries_remain_accounted_between_valid_neighbors(bad):
    parsed = parse_semgrep_observations(report([native(), bad, native()]), b"", 0)
    assert parsed.result_count == 3
    assert [r.disposition for r in parsed.results] == ["projected", "rejected", "projected"]
    assert [r.tool_ordinal for r in parsed.results] == [0, 1, 2]
    assert json.loads(parsed.results[1].raw.data) == bad
    assert parsed.results[1].issues
    assert parsed.results[2].duplicate_ordinal == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("check_id", ""),
        ("path", 3),
        ("path", ""),
        ("path", "a\x00b"),
        ("start", {"line": True, "col": 1}),
        ("start", {"line": 0, "col": 1}),
        ("start", {"line": 2**63, "col": 1}),
        ("start", {"line": 1.0, "col": 1}),
        ("start", {"line": 1, "col": -1}),
        ("start", {"line": 1, "col": 1, "offset": None}),
        ("start", {"line": 1, "col": 1, "offset": -2}),
        ("start", {"line": 1, "col": 1, "offset": False}),
        ("start", {"line": 1, "col": 1, "unknown": 0}),
        ("end", {"line": 1, "col": 9}),
        ("end", {"line": 2, "col": 2}),
        ("end", {"line": 2, "col": 9, "offset": 7}),
        ("extra", {"message": [], "severity": "ERROR"}),
        ("extra", {"message": "a", "severity": "UNKNOWN"}),
        ("extra", {"message": "a", "severity": True}),
    ],
)
def test_unsupported_projection_preserves_original_result(field, value):
    result = native(**{field: value})
    parsed = parse_semgrep_observations(report([result]), b"", 0)
    assert parsed.parse_status == "parsed"
    assert parsed.results[0].disposition == "rejected"
    assert json.loads(parsed.results[0].raw.data) == result


@pytest.mark.parametrize("field", ["check_id", "path"])
@pytest.mark.parametrize("blank", [" ", "\t\n", "\u2003"])
def test_blank_rule_and_path_are_rejected_without_losing_raw_bytes(field, blank):
    result = native(**{field: blank})
    parsed = parse_semgrep_observations(report([result]), b"", 0)
    assert parsed.results[0].disposition == "rejected"
    assert json.loads(parsed.results[0].raw.data) == result


def test_nonblank_fields_and_whitespace_only_message_are_not_stripped():
    result = native(
        check_id=" controlled.rule ",
        path=" src/observed.py ",
        extra={"message": " \t\n\u2003", "severity": "ERROR"},
    )
    parsed = parse_semgrep_observations(report([result]), b"", 0)
    projection = parsed.results[0].projection
    assert projection.rule_id == result["check_id"]
    assert projection.path == result["path"]
    assert projection.message == result["extra"]["message"]


def test_offsets_missing_dummy_and_real_remain_distinct():
    rows = [
        native(start={"line": 2, "col": 3}),
        native(start={"line": 2, "col": 3, "offset": -1}),
        native(),
    ]
    parsed = parse_semgrep_observations(report(rows), b"", 0)
    assert [
        (r.projection.start.offset_present, r.projection.start.offset) for r in parsed.results
    ] == [(False, None), (True, -1), (True, 8)]


def test_coordinate_integer_ceiling_and_boundary_plus_one():
    maximum = 2**63 - 1
    position = {"line": maximum, "col": maximum, "offset": maximum}
    parsed = parse_semgrep_observations(report([native(start=position, end=position)]), b"", 0)
    assert parsed.results[0].disposition == "projected"
    assert parsed.results[0].projection.start.offset == maximum
    for endpoint in ("start", "end"):
        for coordinate in ("line", "col", "offset"):
            row = native(start=position, end=position)
            row[endpoint] = {**position, coordinate: maximum + 1}
            parsed = parse_semgrep_observations(report([row]), b"", 0)
            assert parsed.results[0].disposition == "rejected"
            assert json.loads(parsed.results[0].raw.data) == row


@pytest.mark.parametrize(
    "version,status",
    [
        ("1.175.0", "matched"),
        ("1.176.0", "mismatched"),
        ("", "mismatched"),
        (None, "invalid"),
        (175, "invalid"),
    ],
)
def test_version_status_does_not_erase_parsable_observations(version, status):
    parsed = parse_semgrep_observations(report([native()], version=version), b"", 0)
    assert parsed.parse_status == "parsed"
    assert parsed.version_status == status
    assert parsed.result_count == 1
    assert parsed.results[0].disposition == "projected"
    assert parsed.coverage_status == "unverified"


@pytest.mark.parametrize("value", [None, {}, True, "", 1])
def test_unobserved_results_are_not_zero(value):
    parsed = parse_semgrep_observations(encode({"results": value}), b"", 0)
    assert parsed.parse_status == "parsed"
    assert parsed.results_status == "invalid"
    assert parsed.result_count is None
    assert parsed.results == ()


def test_missing_version_results_and_observed_empty_are_distinct():
    absent = parse_semgrep_observations(b"{}", b"", 0)
    empty = parse_semgrep_observations(b'{"results":[]}', b"", 0)
    assert absent.version_status == empty.version_status == "missing"
    assert absent.result_count is None and absent.results_status == "missing"
    assert empty.result_count == 0 and empty.results_status == "present"
    assert absent.coverage_status == empty.coverage_status == "unverified"


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b" ",
        b"[]",
        b"null",
        b"true",
        b"123",
        b"{} {}",
        b"{}trailing",
        b'{"results":[],}',
        b'{"results":[1,]}',
        b'{"results":[+1]}',
        b'{"results":[01]}',
        b'{"results":[1.]}',
        b'{"results":[1e]}',
        b'{"results":[NaN]}',
        b'{"results":[Infinity]}',
        b'{"results":[-Infinity]}',
        b'{"results":[],"results":[]}',
        b'{"results":[],"resu\\u006cts":[]}',
        b'{"results":[],"x":{"a":1,"a":2}}',
        b'{"results":[],"x":"\\ud800"}',
        b'{"results":[],"x":"\\udfff"}',
        b'{"results":[],"x":"\xff"}',
        b'{"results":[],"x":"\x00"}',
        b'{"results":[],"x":"unterminated',
        b'{"results":[],"x":"bad\\"}',
        b'\xef\xbb\xbf{"results":[]}',
    ],
)
def test_malformed_report_keeps_raw_streams_without_prefix_or_zero_count(raw):
    parsed = parse_semgrep_observations(raw, b"actual failed stderr", 2)
    assert parsed.parse_status == "invalid-report"
    assert parsed.stdout == raw and parsed.stderr == b"actual failed stderr"
    assert parsed.result_count is None and parsed.results == ()
    assert parsed.issues and parsed.coverage_status == "unverified"


def test_escaped_root_key_and_nested_results_are_not_confused():
    raw = b'{"metadata":{"results":[9]},"resu\\u006cts":[null],"version":"1.175.0"}'
    parsed = parse_semgrep_observations(raw, b"", 0)
    assert parsed.result_count == 1 and parsed.results[0].raw.data == b"null"
    metadata = next(f for f in parsed.fields if f.name == "metadata")
    assert metadata.raw.data == b'{"results":[9]}' and not metadata.recognized
    assert any(i.code == "unknown-report-field" for i in parsed.issues)


@pytest.mark.parametrize(
    "field,value,state",
    [
        ("errors", [], "present"),
        ("errors", None, "null"),
        ("errors", {}, "invalid"),
        ("errors", [1], "invalid"),
        ("paths", {}, "invalid"),
        ("paths", {"scanned": [], "skipped": []}, "present"),
        ("paths", {"scanned": [1]}, "invalid"),
        ("paths", {"scanned": [], "unknown": []}, "invalid"),
        ("rules_by_engine", [["r", "OSS"]], "present"),
        ("rules_by_engine", {"r": True}, "invalid"),
        ("rules_by_engine", [["r", "OTHER"]], "invalid"),
        ("engine_requested", "PRO", "present"),
        ("engine_requested", "unknown", "invalid"),
        ("skipped_rules", [{"rule_id": "r"}], "present"),
        ("interfile_languages_used", [1], "invalid"),
        ("time", 2, "invalid"),
    ],
)
def test_telemetry_observations_are_not_coverage_proof(field, value, state):
    parsed = parse_semgrep_observations(report(**{field: value}), b"", 0)
    observed = next(f for f in parsed.fields if f.name == field)
    assert observed.state == state
    assert json.loads(observed.raw.data) == value
    assert parsed.coverage_status == "unverified"


def test_finite_numeric_telemetry_is_not_rounded_or_coerced_to_sql_json():
    raw = b'{"results":[],"time":{"huge":1e10000,"tiny":-1e-10000,"zero":-0.0}}'
    parsed = parse_semgrep_observations(raw, b"", 0)
    assert parsed.parse_status == "parsed"
    assert (
        next(f for f in parsed.fields if f.name == "time").raw.data
        == b'{"huge":1e10000,"tiny":-1e-10000,"zero":-0.0}'
    )


@pytest.mark.parametrize(
    "change",
    [
        {"max_stdout_bytes": 0},
        {"max_stderr_bytes": True},
        {"max_result_bytes": -1},
        {"max_results": 10_001},
        {"max_depth": 33},
        {"max_values": 250_001},
        {"max_stdout_bytes": 16 * 1024 * 1024 + 1},
        {"max_stderr_bytes": 1024 * 1024 + 1},
        {"max_result_bytes": 1024 * 1024 + 1},
    ],
)
def test_closed_limit_profile_cannot_be_raised_or_coerced(change):
    with pytest.raises(ObservationInputError):
        ObservationLimits(**change)


@pytest.mark.parametrize("code", [True, False, "0", None, 0.0, 2**31, -(2**31) - 1])
def test_process_return_code_is_an_exact_bounded_observation(code):
    with pytest.raises(ObservationInputError):
        parse_semgrep_observations(b"{}", b"", code)


def test_mutable_streams_and_wrong_limit_types_are_rejected():
    for args in ((bytearray(b"{}"), b"", 0), (b"{}", memoryview(b""), 0)):
        with pytest.raises(ObservationInputError):
            parse_semgrep_observations(*args)
    with pytest.raises(ObservationInputError):
        parse_semgrep_observations(b"{}", b"", 0, limits={})


def test_exact_lowered_boundaries_and_boundary_plus_one():
    raw = b'{"results":[null]}'
    limits = ObservationLimits(
        max_stdout_bytes=len(raw),
        max_stderr_bytes=3,
        max_result_bytes=4,
        max_results=1,
        max_depth=2,
        max_values=4,
    )
    assert parse_semgrep_observations(raw, b"abc", 0, limits=limits).result_count == 1
    cases = [
        (raw + b" ", b"abc", limits, "stdout-bytes"),
        (raw, b"abcd", limits, "stderr-bytes"),
        (raw, b"", replace(limits, max_result_bytes=3), "result-bytes"),
        (raw, b"", replace(limits, max_depth=1), "json-depth"),
        (raw, b"", replace(limits, max_values=3), "json-values"),
        (b'{"results":[null,null]}', b"", ObservationLimits(max_results=1), "results"),
    ]
    for data, err, policy, resource in cases:
        with pytest.raises(ObservationLimitError) as failure:
            parse_semgrep_observations(data, err, 0, limits=policy)
        assert failure.value.resource == resource


def test_hard_count_depth_and_individual_result_boundaries():
    maximum = ObservationLimits()
    data = b'{"results":[' + b",".join([b"null"] * maximum.max_results) + b"]}"
    assert parse_semgrep_observations(data, b"", 0).result_count == maximum.max_results
    with pytest.raises(ObservationLimitError, match="results limit"):
        parse_semgrep_observations(data[:-2] + b",null]}", b"", 0)
    for extra in (0, 1):
        depth = maximum.max_depth - 1 + extra
        raw = b'{"results":[],"x":' + b"[" * depth + b"0" + b"]" * depth + b"}"
        if extra:
            with pytest.raises(ObservationLimitError, match="json-depth"):
                parse_semgrep_observations(raw, b"", 0)
        else:
            assert parse_semgrep_observations(raw, b"", 0).parse_status == "parsed"
    value = b'"' + b"x" * (maximum.max_result_bytes - 2) + b'"'
    assert parse_semgrep_observations(b'{"results":[' + value + b"]}", b"", 0).result_count == 1
    with pytest.raises(ObservationLimitError, match="result-bytes"):
        parse_semgrep_observations(b'{"results":[' + value[:-1] + b'x"]}', b"", 0)


def test_hard_value_count_includes_keys_but_not_punctuation():
    # root + results key/array + x key/array = 5 values/keys before scalar items.
    data = b'{"results":[],"x":[' + b",".join([b"0"] * (250_000 - 5)) + b"]}"
    assert parse_semgrep_observations(data, b"", 0).result_count == 0
    with pytest.raises(ObservationLimitError, match="json-values"):
        parse_semgrep_observations(data[:-2] + b",0]}", b"", 0)


def test_hard_stream_byte_boundaries_are_independent():
    maximum = ObservationLimits()
    # Exercise the actual stdout ceiling through JSON string scanning, not only
    # a lowered constructor or rejected oversized input. This is synthetic data.
    prefix, suffix = b'{"results":[],"opaque":"', b'"}'
    stdout = prefix + b"x" * (maximum.max_stdout_bytes - len(prefix + suffix)) + suffix
    stderr = b"\xff" * maximum.max_stderr_bytes
    parsed = parse_semgrep_observations(stdout, stderr, 0)
    assert parsed.parse_status == "parsed" and parsed.result_count == 0
    assert parsed.stdout_byte_length == maximum.max_stdout_bytes
    assert parsed.stderr_byte_length == maximum.max_stderr_bytes
    assert parsed.stdout == stdout and parsed.stderr == stderr
    for data, err, resource, limit in (
        (stdout + b" ", stderr, "stdout-bytes", maximum.max_stdout_bytes),
        (b"{}", stderr + b"x", "stderr-bytes", maximum.max_stderr_bytes),
    ):
        with pytest.raises(ObservationLimitError) as failure:
            parse_semgrep_observations(data, err, 0)
        assert (failure.value.resource, failure.value.observed, failure.value.limit) == (
            resource,
            limit + 1,
            limit,
        )


def test_no_native_source_network_or_identity_operation(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("observation parser attempted external work")

    with monkeypatch.context() as patch:
        for owner, name in (
            (Path, "resolve"),
            (Path, "open"),
            (subprocess, "run"),
            (subprocess, "Popen"),
            (socket, "create_connection"),
        ):
            patch.setattr(owner, name, forbidden)
        parsed = parse_semgrep_observations(report([native(path="../../private/file")]), b"", 0)
    assert parsed.results[0].projection.path == "../../private/file"
    assert not hasattr(parsed.results[0].projection, "slice_fingerprint")
    assert not hasattr(parsed.results[0].projection, "S_version")


def test_factory_outputs_are_deeply_immutable_and_detached():
    mutable = native()
    parsed = parse_semgrep_observations(report([mutable]), b"", 0)
    mutable["extra"]["message"] = "changed"
    assert parsed.results[0].projection.message == "observed message"
    assert type(parsed.results) is type(parsed.fields) is type(parsed.issues) is tuple
    with pytest.raises((FrozenInstanceError, AttributeError)):
        parsed.results[0].projection.message = "changed"
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        parsed.results[0].projection.origin = "deterministic-core"


@pytest.mark.parametrize("seed", range(64))
def test_controlled_json_encoding_and_spans_agree_with_standard_decoder(seed):
    rng = random.Random(seed)
    alphabet = ['"', "\\", "é", "😀", "\n", "\t", "{", "}", "[", "]", ":", ",", " "]
    rows = [
        native(
            extra={
                "severity": "HIGH",
                "message": "".join(rng.choices(alphabet, k=32)),
                "metadata": {"results": [seed, True, None, 1.25]},
            }
        )
        for _ in range(4)
    ]
    encodings = [
        json.dumps(
            row, ensure_ascii=bool(rng.getrandbits(1)), indent=rng.choice([None, 1, 2])
        ).encode()
        for row in rows
    ]
    data = b'{"results":[' + b", \n".join(encodings) + b'],"version":"1.175.0"}'
    parsed = parse_semgrep_observations(data, b"", 0)
    assert parsed.parse_status == "parsed" and parsed.result_count == len(rows)
    assert [r.raw.data for r in parsed.results] == encodings
    assert [json.loads(r.raw.data) for r in parsed.results] == json.loads(data)["results"]
    assert all(r.disposition == "projected" for r in parsed.results)
