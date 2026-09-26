"""Exact immutable inputs, not caller-provided acceptance capabilities."""

from dataclasses import replace
from pathlib import PosixPath
from uuid import UUID

import pytest

from analysis.ifds.bound_rules import QualifiedRuleKey, encode_qualified_rule_key
from services.scan.accepted_inputs import codec as c
from services.scan.accepted_inputs import models as m
from services.scan.accepted_inputs import schemas as s
from tests import accepted_input_fixtures as fixtures

pytestmark = pytest.mark.unit
material = fixtures.material
test_only_keys = fixtures.test_only_keys
bundle_fixture = fixtures.bundle_fixture


class Poison:
    def __iter__(self):
        raise AssertionError("must not iterate caller object")

    def __str__(self):
        raise AssertionError("must not format caller object")

    def __format__(self, _spec):
        raise AssertionError("must not format caller object")


class TupleSubclass(tuple):
    def __iter__(self):
        raise AssertionError("must not iterate tuple subclass")


class BytesSubclass(bytes):
    pass


@pytest.mark.parametrize("values", [[], Poison(), TupleSubclass((b"x",)), (BytesSubclass(b"x"),)])
@pytest.mark.parametrize("field", ["detector_blobs", "rule_blobs"])
def test_raw_collections_reject_before_arbitrary_iteration(values, field):
    bundle = bundle_fixture()
    with pytest.raises(s.VerificationError):
        replace(bundle, **{field: values})


@pytest.mark.parametrize(
    "value", [bytearray(b"x"), BytesSubclass(b"x"), b"", b"x" * (s.MAX_CONTENT + 1)]
)
def test_spec_exact_raw_type_and_bound(value):
    with pytest.raises(s.VerificationError):
        replace(bundle_fixture(), spec_bytes=value)


def test_counts_and_aggregate_are_checked():
    bundle = bundle_fixture()
    for rules in ((b"x", b"y"), (b"x" * s.MAX_CONTENT,)):
        with pytest.raises(s.VerificationError):
            replace(bundle, rule_blobs=rules)


def test_shared_key_is_reexport_not_copied():
    assert m.QualifiedRuleKey is QualifiedRuleKey
    key = c.qualified_members(bundle_fixture())[0][0]
    assert type(key.registry_id) is str
    assert c.parse_json(encode_qualified_rule_key(key))["registry_id"] == key.registry_id


def test_poisoned_uuid_integer_rejects_before_formatting(material):
    value = UUID(int=5)
    object.__setattr__(value, "int", Poison())
    with pytest.raises(s.VerificationError):
        replace(material.request.installed_trust, registry_id=value)


@pytest.mark.parametrize("parts", [Poison(), [Poison()], ["x"] * 4097, ["x" * 4097 + "\ud800"]])
def test_poisoned_path_storage_rejects_before_formatting(parts):
    path = PosixPath("/diagnostic/runtime")
    field = "_raw_paths" if hasattr(path, "_raw_paths") else "_parts"
    object.__setattr__(path, field, parts)
    with pytest.raises(s.VerificationError):
        m._path_snapshot(path)


def test_path_snapshot_ignores_poisoned_cache_and_retains_no_component_alias():
    path = PosixPath("/diagnostic/runtime")
    object.__setattr__(path, "_str", Poison())
    copied = m._path_snapshot(path)
    assert copied == PosixPath("/diagnostic/runtime") and copied is not path
    field = "_raw_paths" if hasattr(path, "_raw_paths") else "_parts"
    object.__getattribute__(path, field).append("unexpected")
    assert str(copied) == "/diagnostic/runtime"


@pytest.mark.parametrize("path", ["/diagnostic/\u0085", "/diagnostic/back\\slash"])
def test_runtime_path_control_and_backslash_reject(path):
    with pytest.raises(s.VerificationError):
        m._path_snapshot(PosixPath(path))


@pytest.mark.parametrize("pattern", ["deep", "shared-branch"])
def test_wrong_scalar_rejects_before_recursive_projection(material, pattern, monkeypatch):
    value = "x"
    for _ in range(48):
        value = (value,) if pattern == "deep" else (value, value)

    def forbidden(*args, **kwargs):
        raise AssertionError("wrong scalar must fail before recursive projection")

    monkeypatch.setattr(m, "_wire", forbidden)
    with pytest.raises(s.VerificationError):
        replace(material.request.installed_trust, root_spki_sha256=value)


@pytest.mark.parametrize("pattern", ["deep", "shared-branch"])
def test_direct_projection_of_mutated_record_has_aggregate_budget(material, pattern):
    value = "x"
    for _ in range(48 if pattern == "deep" else 18):
        value = (value,) if pattern == "deep" else (value, value)
    object.__setattr__(material.request.installed_trust, "root_spki_sha256", value)
    with pytest.raises(s.VerificationError):
        m.record_dict(material.request.installed_trust)


@pytest.mark.parametrize(
    "field,value",
    [
        ("fencing_token", True),
        ("work_revision", -1),
        ("org_id", "00000000-0000-0000-0000-000000000003"),
        ("lease_expires_at", "2026-09-25T00:10:00Z"),
        ("authorization_digest", "sha256:" + "a" * 64),
    ],
)
def test_binding_exact_types(material, field, value):
    with pytest.raises(s.VerificationError):
        replace(material.request.ledger.binding, **{field: value})


def test_request_revalidates_illicitly_changed_frozen_child(material):
    request = material.request
    object.__setattr__(request.bundle, "detector_blobs", Poison())
    with pytest.raises(s.VerificationError):
        c.encode_request(request)


def test_record_uuid_does_not_accept_wire_string_as_model(material):
    trust = material.request.installed_trust
    assert type(trust.registry_id) is UUID
    with pytest.raises(s.VerificationError):
        replace(trust, registry_id=str(trust.registry_id))


@pytest.mark.parametrize("field", ["admission", "ledger", "selected_rule"])
def test_execution_requires_each_independent_expectation(material, field):
    with pytest.raises(s.VerificationError):
        replace(material.request, **{field: None})


def test_scope_and_ledger_tuple_are_closed(material):
    with pytest.raises(s.VerificationError):
        replace(material.request.expected_bundle, scope="global")
    with pytest.raises(s.VerificationError):
        replace(material.request.ledger, policy_event_id=None)


def test_resolved_view_selects_exact_full_bundle(material):
    request = material.request
    view = m.ResolvedQualifiedRule(
        request.selected_rule,
        request.bundle,
        request.authority_evidence,
        request.execution_authorization,
        request.ledger.binding,
    )
    assert view.detector_bytes == request.bundle.detector_blobs[0]
    assert view.rule_bytes == request.bundle.rule_blobs[0]
    assert view.model_bytes == c.decode_spec(request.bundle.spec_bytes)[1][0]
    with pytest.raises(s.VerificationError):
        replace(view, qualified_rule=replace(view.qualified_rule, detector_id="another-detector"))
