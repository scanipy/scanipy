"""Portable storage-envelope and raw-boundary falsifiers (no PostgreSQL needed)."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from services.scan.occurrence_store._schemas import MAX_ENVELOPE, SCHEMAS
from services.scan.occurrence_store.codec import (
    CanonicalEnvelope,
    EnvelopeError,
    _canonical,
    decode_envelope,
    encode_envelope,
)
from services.scan.occurrence_store.models import (
    DetectionBatch,
    Fence,
    RawObservation,
    RequestInput,
)
from tests.occurrence_store_fixtures import batch, capture_seal, envelope, request_input

pytestmark = pytest.mark.unit


def test_frozen_migration_shapes_match_runtime_protocol():
    path = Path(__file__).resolve().parents[2] / "db/migrations/versions/execution_v1_shapes.json"
    assert json.loads(path.read_text()) == SCHEMAS


def test_controlled_inputs_keep_actual_raw_bytes_and_independent_domain_hashes():
    requested = request_input(uuid4(), uuid4())
    capture = capture_seal(uuid4(), requested)
    observed = batch(uuid4(), count=2)
    assert observed.observations[0].result == observed.observations[1].result
    assert b"\x00\xff" in observed.observations[0].result
    assert (
        capture.inventory.digest
        == hashlib.sha256(
            b"scanipy-execution/source-inventory/1\n" + capture.inventory.data
        ).digest()
    )
    assert capture.inventory.digest != hashlib.sha256(capture.inventory.data).digest()
    assert capture.seal.value["tree_digest"] != capture.inventory.digest.hex()


@pytest.mark.parametrize(
    "value",
    ["bad\x00value", "\ud800", "\udfff", 2**63, -(2**63) - 1, 1.0, float("inf"), b"bytes", (1, 2)],
)
def test_nonportable_scalar_values_are_rejected(value):
    with pytest.raises(EnvelopeError):
        _canonical({"value": value})


def test_signed_integer_boundaries_and_supplementary_unicode_are_lossless():
    assert _canonical({"\U0001f600": -(2**63), "\ue000": 2**63 - 1}) == (
        '{"\ue000":9223372036854775807,"😀":-9223372036854775808}'.encode()
    )
    assert (
        _canonical({"control": "\b\f\n\r\t\x01", "bool": True})
        == b'{"bool":true,"control":"\\b\\f\\n\\r\\t\\u0001"}'
    )


@pytest.mark.parametrize(
    "change",
    [
        "duplicate",
        "nested_duplicate",
        "whitespace",
        "escaped",
        "float",
        "unknown",
        "bool_integer",
        "negative_zero",
    ],
)
def test_ambiguous_or_noncanonical_envelopes_fail(change):
    value = envelope("source-inventory", files=[{"path": "é.py", "size": 0, "sha256": "a" * 64}])
    data = value.data
    if change == "duplicate":
        data = b'{"files":[],' + data[1:]
    elif change == "nested_duplicate":
        data = data.replace(b'"size":0', b'"size":0,"size":0')
    elif change == "whitespace":
        data += b"\n"
    elif change == "escaped":
        data = data.replace("é".encode(), b"\\u00e9")
    elif change == "float":
        data = data.replace(b'"size":0', b'"size":0.0')
    elif change == "unknown":
        data = b'{"extra":null,' + data[1:]
    elif change == "bool_integer":
        data = data.replace(b'"size":0', b'"size":false')
    else:
        data = data.replace(b'"size":0', b'"size":-0')
    with pytest.raises(EnvelopeError):
        decode_envelope("source-inventory", data)


@pytest.mark.parametrize(
    "token", [b'"\\u0000"', b'"\\ud800"', b'"\\udfff"', b"9223372036854775808", b"9" * 5000]
)
def test_invalid_input_tokens_rejected_before_canonical_projection(token):
    with pytest.raises(EnvelopeError):
        decode_envelope("source-inventory", b'{"files":[],"schema":' + token + b"}")


def test_bounds_depth_digest_and_unknown_versions():
    with pytest.raises(EnvelopeError):
        decode_envelope("source-inventory", b" " * (MAX_ENVELOPE + 1))
    deep = None
    for _ in range(34):
        deep = [deep]
    with pytest.raises(EnvelopeError):
        _canonical({"deep": deep})
    valid = envelope("source-inventory", files=[])
    with pytest.raises(EnvelopeError):
        decode_envelope(valid.name, valid.data, b"\x00" * 32)
    with pytest.raises(EnvelopeError):
        encode_envelope("source-inventory-v2", {"schema": "source-inventory/2"})


@pytest.mark.parametrize(
    "location",
    [
        {
            "status": "unknown",
            "path": None,
            "start_line": None,
            "start_column": None,
            "end_line": None,
            "end_column": None,
        },
        {
            "status": "partial",
            "path": "fixture.py",
            "start_line": None,
            "start_column": None,
            "end_line": None,
            "end_column": None,
        },
        {
            "status": "partial",
            "path": None,
            "start_line": 5,
            "start_column": None,
            "end_line": None,
            "end_column": None,
        },
    ],
)
def test_unknown_partial_location_preserved_without_fabrication(location):
    observed = batch(uuid4(), location=location)
    assert observed.envelope.value["occurrences"][0]["location"] == location


@pytest.mark.parametrize(
    "field,value",
    [
        ("start_line", 0),
        ("start_line", True),
        ("status", "unknown"),
        ("end_line", 0),
        ("end_column", 2),
        ("path", "../outside.py"),
    ],
)
def test_invalid_physical_locations_rejected(field, value):
    location = {
        "status": "known",
        "path": "fixture.py",
        "start_line": 1,
        "start_column": None,
        "end_line": None,
        "end_column": None,
    }
    location[field] = value
    with pytest.raises(EnvelopeError):
        batch(uuid4(), location=location)


def test_raw_bounds_do_not_truncate_or_reinterpret_bytes():
    with pytest.raises(EnvelopeError):
        RawObservation(b"x" * (16 * 1024 * 1024 + 1))
    valid = batch(uuid4())
    with pytest.raises(EnvelopeError):
        DetectionBatch(valid.envelope, b"altered", valid.stderr, valid.observations)
    with pytest.raises(EnvelopeError):
        DetectionBatch(valid.envelope, valid.stdout, valid.stderr, valid.observations * 10001)


def test_policy_digest_is_not_observed_code_digest_and_request_binds_exact_plan():
    first, second = request_input(uuid4(), uuid4()), request_input(uuid4(), uuid4(), bindings=2)
    assert (
        first.planned_policy.value["bindings"][0]["code_policy_digest"]
        != first.planned_policy.value["bindings"][0]["expected_code_digest"]
    )
    with pytest.raises(EnvelopeError):
        RequestInput(first.request, second.planned_policy)
    for bad in (True, -1, 0):
        with pytest.raises(ValueError):
            Fence(uuid4(), uuid4(), "identity", bad, 0)


def test_accepted_content_and_aggregate_raw_caps_fail_before_sql_parameters():
    requested = request_input(uuid4(), uuid4())
    capture = capture_seal(uuid4(), requested)
    with pytest.raises(EnvelopeError, match="accepted raw content"):
        replace(capture, spec=b"x" * (MAX_ENVELOPE + 1))
    with pytest.raises(EnvelopeError, match="acceptance evidence"):
        replace(capture, authority_evidence=b"x" * (MAX_ENVELOPE + 1))
    observed = batch(uuid4(), count=5)
    row = RawObservation(b"x" * (16 * 1024 * 1024))
    with pytest.raises(EnvelopeError, match="64 MiB"):
        replace(observed, observations=(row,) * 5)
    huge = observed.envelope.value
    huge["occurrences"][0]["message"] = "x" * MAX_ENVELOPE
    with pytest.raises(EnvelopeError, match="size"):
        encode_envelope("detection-batch", huge)


@pytest.mark.parametrize("token,revision", [(2**63, 0), (1, 2**63), (0, 0), (1, -1)])
def test_fences_are_bounded_signed_integer_values(token, revision):
    with pytest.raises(ValueError):
        Fence(uuid4(), uuid4(), "identity", token, revision)


class PoisonIterable:
    def __iter__(self):
        raise AssertionError("unbounded iterable must not be consumed")

    def __len__(self):
        raise AssertionError("untrusted length must not be consulted")


class PoisonTuple(tuple):
    def __iter__(self):
        raise AssertionError("tuple subclass must not be consumed")

    def __len__(self):
        raise AssertionError("tuple subclass length must not be consulted")


@pytest.mark.parametrize("field", ["detectors", "rules", "observations"])
@pytest.mark.parametrize("container", [list, PoisonTuple, lambda _: PoisonIterable(), iter])
def test_raw_collections_reject_mutable_subclass_and_poison_iterables(field, container):
    value = (
        batch(uuid4())
        if field == "observations"
        else capture_seal(uuid4(), request_input(uuid4(), uuid4()))
    )
    with pytest.raises(EnvelopeError, match="exact tuple"):
        replace(value, **{field: container(getattr(value, field))})


@pytest.mark.parametrize("field", ["detectors", "rules", "observations"])
def test_bounded_metadata_counts_are_checked_before_raw_element_access(field):
    value = (
        batch(uuid4())
        if field == "observations"
        else capture_seal(uuid4(), request_input(uuid4(), uuid4()))
    )
    with pytest.raises(EnvelopeError, match="count mismatch"):
        replace(value, **{field: (object(), object())})


def test_raw_elements_and_envelopes_reject_subclasses():
    class FakeBytes(bytes):
        pass

    class FakeObservation(RawObservation):
        def __post_init__(self):
            raise AssertionError("overridden validation must not be invoked")

    class FakeEnvelope(CanonicalEnvelope):
        pass

    observed = batch(uuid4())
    capture = capture_seal(uuid4(), request_input(uuid4(), uuid4()))
    with pytest.raises(EnvelopeError, match="exact bytes"):
        replace(capture, detectors=(FakeBytes(capture.detectors[0]),))
    with pytest.raises(EnvelopeError, match="exact bytes"):
        RawObservation(FakeBytes(b"data"))
    fake_row = object.__new__(FakeObservation)
    with pytest.raises(EnvelopeError, match="exact RawObservation"):
        replace(observed, observations=(fake_row,))
    fake_envelope = object.__new__(FakeEnvelope)
    with pytest.raises(EnvelopeError, match="exact CanonicalEnvelope"):
        replace(observed, envelope=fake_envelope)


def test_exact_collection_count_boundaries_include_empty_observations():
    assert batch(uuid4(), count=0).observations == ()
    observed = batch(uuid4())
    with pytest.raises(EnvelopeError, match="count exceeds"):
        replace(observed, observations=(object(),) * 10001)
    with pytest.raises(EnvelopeError, match="count mismatch"):
        replace(observed, observations=(object(),) * 10000)
