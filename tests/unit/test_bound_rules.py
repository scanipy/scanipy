"""Controlled codec checks; no fixture establishes accepted model authority."""

import json
from dataclasses import asdict, fields, replace

import pytest

from analysis.ifds.bound_rules import (
    BoundRuleError,
    QualifiedRuleKey,
    ScalarLimits,
    checked_limits,
    decode_bounded_json,
    decode_qualified_rule_key,
    encode_qualified_rule_key,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def rule_key():
    return QualifiedRuleKey(
        registry_id="11111111-1111-4111-8111-111111111111",
        bundle_id="22222222-2222-4222-8222-222222222222",
        scope="global",
        org_id=None,
        S_version="1.0.0",
        accepted_content_digest="a" * 64,
        detector_id="controlled-detector",
        detector_version="1.0.0",
        detector_raw_sha256="b" * 64,
        rule_id="controlled-rule",
        rule_artifact_id="controlled-rule-artifact",
        rule_artifact_version="1.0.0",
        rule_raw_sha256="c" * 64,
        model_artifact_id="controlled-model-artifact",
        model_artifact_version="1.0.0",
        model_raw_sha256="d" * 64,
        semantic_descriptor_digest="e" * 64,
    )


def test_qualified_key_round_trip_is_exact_canonical(rule_key):
    encoded = encode_qualified_rule_key(rule_key)
    assert decode_qualified_rule_key(encoded) == rule_key
    assert (
        encoded
        == json.dumps(
            asdict(rule_key), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    )
    assert not encoded.endswith(b"\n")


@pytest.mark.parametrize(
    "change",
    [
        {"scope": "customer"},
        {"org_id": "bad"},
        {"scope": "global", "org_id": "33333333-3333-4333-8333-333333333333"},
        {"registry_id": "11111111111141118111111111111111"},
        {"detector_id": "../model"},
        {"detector_id": "☃"},
        {"rule_id": "a" * 129},
        {"accepted_content_digest": "A" * 64},
        {"model_raw_sha256": "sha256:" + "d" * 64},
        {"schema": "scanipy-qualified-rule/2"},
    ],
)
def test_key_constructor_rejects_ambiguous_or_invalid_identity(rule_key, change):
    with pytest.raises(BoundRuleError):
        replace(rule_key, **change)


@pytest.mark.parametrize(
    "version",
    [
        "1.0",
        "01.0.0",
        "1.0.0-rc1",
        "1.0.0+build",
        "-1.0.0",
        "1.0.2147483648",
        "1.0.true",
        True,
        1,
        "1.0.0\n",
    ],
)
def test_versions_are_exact_bounded_numeric_labels(rule_key, version):
    with pytest.raises(BoundRuleError):
        replace(rule_key, S_version=version)


def test_customer_scope_is_explicit(rule_key):
    customer = replace(rule_key, scope="customer", org_id="33333333-3333-4333-8333-333333333333")
    assert decode_qualified_rule_key(encode_qualified_rule_key(customer)) == customer


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "unknown",
        "missing",
        "whitespace",
        "trailing",
        "float",
        "nul",
        "surrogate",
        "depth",
        "large",
        "bytearray",
    ],
)
def test_key_wire_fails_closed(rule_key, mutation):
    raw = encode_qualified_rule_key(rule_key)
    row = asdict(rule_key)
    if mutation == "duplicate":
        raw = b'{"scope":"global",' + raw[1:]
    elif mutation == "unknown":
        row["accepted"] = True
        raw = json.dumps(row).encode()
    elif mutation == "missing":
        del row["schema"]
        raw = json.dumps(row).encode()
    elif mutation == "whitespace":
        raw = json.dumps(row, indent=2).encode()
    elif mutation == "trailing":
        raw += b"\n"
    elif mutation == "float":
        raw = raw.replace(b'"1.0.0"', b"1.0", 1)
    elif mutation == "nul":
        raw = raw.replace(b"controlled-rule", b"controlled\\u0000rule", 1)
    elif mutation == "surrogate":
        raw = raw.replace(b"controlled-rule", b"controlled\\ud800rule", 1)
    elif mutation == "depth":
        raw = b"[" * 5 + b"0" + b"]" * 5
    elif mutation == "large":
        raw += b" " * 16384
    elif mutation == "bytearray":
        raw = bytearray(raw)
    with pytest.raises(BoundRuleError):
        decode_qualified_rule_key(raw)


def test_key_encoder_revalidates_even_frozen_objects(rule_key):
    object.__setattr__(rule_key, "scope", "invalid")
    with pytest.raises(BoundRuleError):
        encode_qualified_rule_key(rule_key)


def test_key_constructor_checks_size_before_encoding(rule_key):
    # Small malformed-Unicode sentinel proves the length guard wins BEFORE
    # encode; no enormous temporary string/allocation is needed for the test.
    with pytest.raises(BoundRuleError, match=r"^string-limit$"):
        replace(rule_key, detector_id="a" * 128 + "\ud800")


def test_key_encoder_checks_size_before_encoding(rule_key):
    object.__setattr__(rule_key, "detector_id", "a" * 128 + "\ud800")
    with pytest.raises(BoundRuleError, match=r"^string-limit$"):
        encode_qualified_rule_key(rule_key)


def test_key_encoder_rejects_subclasses_without_callbacks(rule_key):
    class Impostor:
        def __getattr__(self, name):
            raise AssertionError("must not inspect a foreign object")

    with pytest.raises(BoundRuleError):
        encode_qualified_rule_key(Impostor())


@pytest.mark.parametrize("definition", fields(ScalarLimits))
def test_all_limits_are_lower_only_positive_exact_ints(definition):
    ceilings = ScalarLimits()
    assert replace(ceilings, **{definition.name: 1})
    for value in (0, -1, True, 1.0, definition.default + 1):
        with pytest.raises(BoundRuleError):
            replace(ceilings, **{definition.name: value})


def test_rule_key_identity_does_not_collapse_different_artifacts(rule_key):
    another = replace(rule_key, detector_id="another-detector")
    assert another != rule_key
    assert encode_qualified_rule_key(another) != encode_qualified_rule_key(rule_key)


def test_maximum_version_component_is_accepted(rule_key):
    key = replace(rule_key, S_version="2147483647.2147483647.2147483647")
    assert decode_qualified_rule_key(encode_qualified_rule_key(key)) == key


@pytest.mark.parametrize("raw", [b"[" * 5, b"[0,0,0,0]", b'"' + b"a" * 30])
def test_json_limits_precede_parser_allocation(monkeypatch, raw):
    def forbidden(*args, **kwargs):
        raise AssertionError("parser must not run for preflight-rejected input")

    monkeypatch.setattr("analysis.ifds.bound_rules.json.loads", forbidden)
    with pytest.raises(BoundRuleError):
        decode_bounded_json(raw, max_bytes=128, max_depth=4, max_values=4, max_string_bytes=4)


@pytest.mark.parametrize(
    "raw",
    [
        b"1.0",
        b"NaN",
        b"Infinity",
        b"9223372036854775808",
        b"-9223372036854775809",
        b'{"x":1,"x":2}',
        b'"\\ud800"',
        b'"\\u0000"',
    ],
)
def test_bounded_json_rejects_unsupported_domain(raw):
    with pytest.raises(BoundRuleError):
        decode_bounded_json(raw, max_bytes=128, max_depth=4, max_values=20, max_string_bytes=32)


def test_escaped_string_bound_uses_decoded_utf8_bytes():
    raw = b'"' + b"\\u0061" * 4 + b'"'
    assert (
        decode_bounded_json(raw, max_bytes=64, max_depth=4, max_values=2, max_string_bytes=4)
        == "aaaa"
    )
    with pytest.raises(BoundRuleError):
        decode_bounded_json(raw, max_bytes=64, max_depth=4, max_values=2, max_string_bytes=3)


def test_frozen_limits_are_revalidated():
    limits = ScalarLimits()
    object.__setattr__(limits, "max_files", 17)
    with pytest.raises(BoundRuleError):
        checked_limits(limits)
    with pytest.raises(BoundRuleError):
        checked_limits(None)
