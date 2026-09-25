"""Control bytes are canonical; original model/rule bytes remain exact."""

import json
from dataclasses import replace

import pytest

from services.scan.accepted_inputs import codec as c
from services.scan.accepted_inputs import models as m
from services.scan.accepted_inputs import schemas as s
from services.scan.occurrence_store.codec import encode_envelope
from tests import accepted_input_fixtures as fixtures

pytestmark = pytest.mark.unit
material = fixtures.material
test_only_keys = fixtures.test_only_keys
bundle_fixture = fixtures.bundle_fixture


@pytest.mark.parametrize("kind", ["publication", "historical", "execution"])
def test_three_mode_exact_roundtrip(material, kind):
    request = material.request if kind == "execution" else getattr(material, kind)()
    raw = c.encode_request(request)
    restored = c.decode_request(raw)
    assert restored == request
    assert c.encode_request(restored) == raw
    assert restored.bundle.rule_blobs[0].endswith(b"\n")
    assert c.decode_spec(restored.bundle.spec_bytes)[1][0].startswith(b" ")


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":1,"a":2}',
        b'{"a":true,"a":false}',
        b'"\\ud800"',
        b'"\\u0000"',
        b"NaN",
        b"1.0",
        b"9223372036854775808",
        b"-9223372036854775809",
        b' {"a":1}',
        b'{"a":1}\n',
        b"[" * 34 + b"0" + b"]" * 34,
    ],
)
def test_strict_domain_and_canonical_spelling(raw):
    with pytest.raises(s.VerificationError):
        c.parse_json(raw)


@pytest.mark.parametrize(
    "mutation",
    [
        "empty",
        "prefix",
        "header-too-large",
        "trailing",
        "middle",
        "last-byte",
        "bytes-subclass",
        "oversized",
    ],
)
def test_framing_never_accepts_a_prefix(material, mutation):
    raw = c.encode_request(material.request)
    prefix = len(s.REQUEST) + 1
    if mutation == "empty":
        raw = b""
    elif mutation == "prefix":
        raw = raw.replace(s.REQUEST.encode(), b"wrong-request", 1)
    elif mutation == "header-too-large":
        raw = raw[:prefix] + (2**64 - 1).to_bytes(8, "big") + raw[prefix + 8 :]
    elif mutation == "trailing":
        raw += b"\n"
    elif mutation == "middle":
        raw = raw[: len(raw) // 2]
    elif mutation == "last-byte":
        raw = raw[:-1]
    elif mutation == "bytes-subclass":
        raw = type("ForeignBytes", (bytes,), {})(raw)
    elif mutation == "oversized":
        raw = b"x" * (s.MAX_PACKET + 1)
    with pytest.raises(s.VerificationError):
        c.decode_request(raw)


def test_duplicate_preserving_preflight_before_decode(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("oversize/depth must fail before JSON parsing")

    monkeypatch.setattr("analysis.ifds.bound_rules.json.loads", forbidden)
    with pytest.raises(s.VerificationError):
        c.parse_json(b"[" * 40)
    with pytest.raises(s.VerificationError):
        c.parse_json(b"x" * (s.MAX_OBJECT + 1))


@pytest.mark.parametrize(
    "value",
    [
        ["x" * s.MAX_STRING] * 1000,
        ["\u0001" * s.MAX_STRING],
        {str(index): "x" * s.MAX_STRING for index in range(5)},
    ],
)
def test_aggregate_encoded_size_rejects_before_json_serializer(monkeypatch, value):
    def forbidden(*args, **kwargs):
        raise AssertionError("over-limit JSON must not be materialized")

    monkeypatch.setattr(c.json, "dumps", forbidden)
    with pytest.raises(s.VerificationError):
        c.canonical_bytes(value)


def test_pending_values_count_before_container_expansion(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("child values must not be visited after queue exceeds the budget")

    monkeypatch.setattr(s, "text", forbidden)
    with pytest.raises(s.VerificationError):
        c._primitive_budget([["unvisited"] * 20] * 20, maximum=30)


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        False,
        -(2**63),
        2**63 - 1,
        [],
        {},
        'é雪😀"\\\n\b\u0001',
        {"b": [None, False, "é"], "a": {"x": 7}},
    ],
)
def test_exact_escaped_utf8_byte_budget_boundary(value):
    expected = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    assert c.canonical_bytes(value, maximum=len(expected)) == expected
    assert c.canonical_bytes(value, maximum=len(expected) + 1) == expected
    with pytest.raises(s.VerificationError):
        c.canonical_bytes(value, maximum=len(expected) - 1)


def test_accepted_content_is_exact_existing_store_domain():
    bundle = bundle_fixture()
    envelope = encode_envelope(
        "accepted-content",
        {
            "schema": "scanipy-execution/accepted-content/1",
            "spec_sha256": c.raw_digest(bundle.spec_bytes),
            "detector_sha256s": [c.raw_digest(raw) for raw in bundle.detector_blobs],
            "rule_sha256s": [c.raw_digest(raw) for raw in bundle.rule_blobs],
        },
    )
    assert c.accepted_content_digest(bundle) == envelope.digest.hex()
    assert c.raw_digest(envelope.data) != envelope.digest.hex()


def test_manifest_digest_and_raw_model_hash_both_checked():
    bundle = bundle_fixture()
    spec = bundle.spec_bytes[:-1] + b"x"
    with pytest.raises(s.VerificationError):
        replace(bundle, spec_bytes=spec)
    changed = replace(bundle, rule_blobs=(bundle.rule_blobs[0] + b" ",))
    with pytest.raises(s.VerificationError):
        c.qualified_members(changed)


@pytest.mark.parametrize(
    "role", ["approval-signature", "issuer-spki", "operator-adoption", "trust-root-spki"]
)
def test_frame_checks_every_raw_object(material, role):
    raw = material.request.authority_evidence
    target = material.objects[role]
    offset = raw.index(target)
    raw = raw[:offset] + bytes((raw[offset] ^ 1,)) + raw[offset + 1 :]
    with pytest.raises(s.VerificationError):
        c.decode_frame(raw, s.SEALED)


def test_rejected_result_can_preserve_unknown_full_input_hash():
    result = m.VerificationResult(None, None, None, "rejected", "invalid-input", None)
    assert c.decode_result(c.encode_result(result)) == result
    row = m.record_dict(result)
    row["accepted"] = True
    with pytest.raises(s.VerificationError):
        c.decode_result(c.canonical_bytes(row))


@pytest.mark.parametrize(
    "field", ["authority", "live_authority", "execution_authorization", "spec"]
)
def test_header_and_inner_lengths_must_match(material, field):
    raw = c.encode_request(material.request)
    prefix = len(s.REQUEST) + 1
    length = int.from_bytes(raw[prefix : prefix + 8], "big")
    header = json.loads(raw[prefix + 8 : prefix + 8 + length])
    header["lengths"][field] += 1
    changed = c.canonical_bytes(header)
    raw = raw[:prefix] + len(changed).to_bytes(8, "big") + changed + raw[prefix + 8 + length :]
    with pytest.raises(s.VerificationError):
        c.decode_request(raw)
