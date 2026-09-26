"""Controlled packet bytes; no installation, native process or accepted authority."""

from __future__ import annotations

import builtins
import copy
import hashlib
import os
import subprocess
import time
from dataclasses import fields
from unittest.mock import Mock
from uuid import UUID

import pytest

from analysis.ifds import bound_rules
from services.scan.accepted_inputs import codec as accepted
from services.scan.accepted_inputs import models, schemas
from tests.unit.test_runtime_profile_documents import (
    at,
    dictionaries,
    encoded,
    metadata_documents,
    stored,
)
from tools.worker import runtime_docker_policy as policy
from tools.worker import runtime_packets as p
from tools.worker import runtime_profiles as profiles
from tools.worker.bounded_process import FrozenInvocation

pytestmark = pytest.mark.unit
MODES = ("verifier-publication", "verifier-historical", "verifier-execution", "python-syntax")


def uid(number):
    return str(UUID(int=number))


def request_document(mode="python-syntax"):
    index = MODES.index(mode)
    bundle = {
        "registry_id": uid(10),
        "bundle_id": uid(11),
        "scope": "customer",
        "org_id": uid(12),
        "S_version": "1.0.0",
        "accepted_content_digest": "c" * 64,
    }
    admission = {
        "checkpoint_digest": "d" * 64,
        "checkpoint_generation": 1,
        "admission_epoch": uid(13),
        "policy_digest": "e" * 64,
        "policy_revision": 1,
    }
    execution = {
        name: uid(20 + i)
        for i, (name, shape) in enumerate(schemas.EXECUTION_BINDING.items())
        if shape == "uuid"
    }
    execution.update(
        org_id=bundle["org_id"],
        fencing_token=1,
        work_revision=0,
        run_input_digest="1" * 64,
        requested_policy_digest="2" * 64,
        attempt_policy_digest="3" * 64,
        authorization_digest="4" * 64,
        lease_expires_at="2026-09-25T00:00:50.000000Z",
        capture_lease_expires_at="2026-09-25T00:00:50.000000Z",
    )
    key = {
        **bundle,
        "schema": bound_rules.QUALIFIED_RULE_SCHEMA,
        "detector_id": "test-detector",
        "detector_version": "1.0.0",
        "detector_raw_sha256": "5" * 64,
        "rule_id": "test-rule",
        "rule_artifact_id": "test-artifact",
        "rule_artifact_version": "1.0.0",
        "rule_raw_sha256": "6" * 64,
        "model_artifact_id": "test-model",
        "model_artifact_version": "1.0.0",
        "model_raw_sha256": "7" * 64,
        "semantic_descriptor_digest": "8" * 64,
    }
    source = {
        "capture_id": execution["capture_id"],
        "source_tree_algorithm": "scanipy-source-tree/1",
        "source_tree_digest": "9" * 64,
        "inventory_sha256": "a" * 64,
        "path": "src/handler.py",
        "size": 20,
        "sha256": "b" * 64,
    }
    prerequisite = {
        "schema": p.PREREQUISITE_SCHEMA,
        "reader_id": "uninstalled-reader",
        "observation_id": uid(50),
        "observed_at": "2026-09-25T00:00:00.000000Z",
        "valid_until": "2026-09-25T00:00:30.000000Z",
        "principal_id": "unauthenticated-diagnostic",
        "org_id": bundle["org_id"],
        "action": (
            "publish-builtin-preflight",
            "audit-historical",
            "verify-execution",
            "parse-python",
        )[index],
        "authentication_evidence_sha256": "c" * 64,
        "scope_evidence_sha256": "d" * 64,
        "admission": None if index == 1 else admission,
        "execution_authorization_digest": execution["authorization_digest"] if index >= 2 else None,
        "capture_lease_evidence_sha256": "e" * 64 if index >= 2 else None,
        "content_verification_evidence_sha256": "f" * 64 if index == 3 else None,
    }
    return {
        "schema": p.REQUEST_SCHEMA,
        "operation_id": uid(3),
        "mode": mode,
        "deployment_id": uid(1),
        "installation_id": uid(2),
        "installation_generation": 7,
        "controller_profile_sha256": "1" * 64,
        "domain_profile_sha256": "2" * 64,
        "input": {
            "size": 123,
            "sha256": "f" * 64,
            "protocol": "scanipy-python-syntax-request/1"
            if index == 3
            else "scanipy-accepted-verifier-request/1",
        },
        "binding": {
            "bundle": bundle,
            "execution": execution if index >= 2 else None,
            "qualified_rule": key if index >= 2 else None,
            "source": source if index == 3 else None,
        },
        "prerequisite": prerequisite,
    }


def recipe_documents(mode="python-syntax"):
    request = request_document(mode)
    syntax = mode == "python-syntax"
    installation, profile = metadata_documents("python-syntax" if syntax else "accepted-verifier")
    attempt = uid(60)
    cwd = "/run/scanipy-work/" + attempt
    argv = ["/runtime/bin/python", "-I", "-S", "-B", "-X"]
    if not syntax:
        argv.extend(["utf8", "-X"])
    argv.extend(["pycache_prefix=" + cwd + "/pycache", "/runtime/application/worker.py"])
    environment = {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
    if syntax:
        environment.update(HOME=cwd + "/home", TMPDIR=cwd + "/tmp")
    else:
        argv.extend(["--profile", "/metadata/domain_profile", "--profile-sha256", "2" * 64])
        environment["TZ"] = "UTC"
    launch = {
        "schema": p.LAUNCH_SCHEMA,
        "attempt_id": attempt,
        "operation_id": request["operation_id"],
        "request_digest": "9" * 64,
        "deployment_id": uid(1),
        "installation_id": uid(2),
        "installation_generation": 7,
        "mode": mode,
        "image_config_id": profile["image"]["config_id"],
        "controller_profile_sha256": "1" * 64,
        "domain_profile_sha256": "2" * 64,
        "inventory_sha256": "3" * 64,
        "inventory_digest": "e" * 64,
        "program_digest": "5" * 64,
        "input": copy.deepcopy(request["input"]),
        "inner": {
            "argv": argv,
            "environment": [
                {"name": name, "value": value} for name, value in sorted(environment.items())
            ],
            "cwd": cwd,
        },
        "container_uid": 1001,
        "container_gid": 1002,
        "release_filename": "release.json",
        "bootstrap_wait_ms": 10000,
        "inner_wall_ms": 5000 if syntax else 3000,
        "inner_cleanup_ms": 500,
    }
    return request, launch, installation, profile


@pytest.mark.parametrize("mode", MODES)
def test_complete_four_mode_views_and_writers(mode):
    documents = recipe_documents(mode)
    raw = tuple(encoded(doc) for doc in documents)
    result = p.decode_runtime_recipe_members(*raw)
    assert result.validation == "input-structure-only"
    assert type(result.metadata) is profiles.RuntimeMetadataDocuments
    assert result.request.document == stored(documents[0])
    assert result.launch.document == stored(documents[1])
    assert result.request.data == raw[0] and result.launch.data == raw[1]
    assert p.encode_runtime_request(result.request.document) == raw[0]
    assert (
        p.encode_runtime_launch(
            result.launch.document, request=raw[0], installation=raw[2], controller_profile=raw[3]
        )
        == raw[1]
    )
    assert [f.name for f in fields(p.RuntimePacket)] == ["kind", "data", "document", "validation"]
    assert "unauthenticated" not in repr(result) and not hasattr(result, "__dict__")
    assert hashlib.sha256(raw[3]).hexdigest() != documents[2]["controller_profile"]["sha256"]
    assert accepted.domain_digest(p.REQUEST_SCHEMA, raw[0]) != documents[1]["request_digest"]
    assert result.launch.validation != "hash-verified"


def mutation_cases():
    for side, doc in enumerate(recipe_documents()[:2]):
        for path in dictionaries(doc):
            for key in at(doc, path):
                yield side, path, key


@pytest.mark.parametrize("side,path,key", list(mutation_cases()))
@pytest.mark.parametrize("change", ["missing", "wrong-type"])
def test_each_request_launch_field_rejects(side, path, key, change):
    docs = recipe_documents()
    row = at(docs[side], path)
    if change == "missing":
        del row[key]
    else:
        row[key] = 1 if row[key] is None else None
    raw = tuple(encoded(doc) for doc in docs)
    with pytest.raises(p.RuntimePacketError):
        p.decode_runtime_recipe_members(*raw)
    if side == 0:
        with pytest.raises(p.RuntimePacketError):
            p.encode_runtime_request(stored(docs[0]))
    else:
        with pytest.raises(p.RuntimePacketError):
            p.encode_runtime_launch(
                stored(docs[1]), request=raw[0], installation=raw[2], controller_profile=raw[3]
            )


@pytest.mark.parametrize(
    "side,path",
    [(i, path) for i, doc in enumerate(recipe_documents()[:2]) for path in dictionaries(doc)],
)
def test_each_request_launch_object_is_closed(side, path):
    docs = recipe_documents()
    at(docs[side], path)["new"] = None
    with pytest.raises(p.RuntimePacketError):
        p.decode_runtime_recipe_members(*(encoded(doc) for doc in docs))


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize(
    "field",
    [
        "admission",
        "execution_authorization_digest",
        "capture_lease_evidence_sha256",
        "content_verification_evidence_sha256",
    ],
)
def test_mode_exact_prerequisite_presence(mode, field):
    doc = request_document(mode)
    value = doc["prerequisite"][field]
    doc["prerequisite"][field] = (
        None if value is not None else (request_document("python-syntax")["prerequisite"][field])
    )
    with pytest.raises(p.RuntimePacketError):
        p.decode_runtime_request(encoded(doc))


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("field", ["execution", "qualified_rule", "source"])
def test_mode_exact_binding_presence(mode, field):
    doc = request_document(mode)
    value = doc["binding"][field]
    doc["binding"][field] = None if value is not None else request_document()["binding"][field]
    with pytest.raises(p.RuntimePacketError):
        p.decode_runtime_request(encoded(doc))


@pytest.mark.parametrize("mode", ["verifier-execution", "python-syntax"])
@pytest.mark.parametrize("lease", ["lease_expires_at", "capture_lease_expires_at"])
@pytest.mark.parametrize("overflow", [False, True])
def test_each_lease_independently_bounds_prerequisite(mode, lease, overflow):
    doc = request_document(mode)
    doc["binding"]["execution"][lease] = "2026-09-25T00:00:30.000000Z"
    doc["prerequisite"]["valid_until"] = (
        "2026-09-25T00:00:30.000001Z" if overflow else "2026-09-25T00:00:30.000000Z"
    )
    if overflow:
        with pytest.raises(p.RuntimePacketError, match="link-mismatch"):
            p.decode_runtime_request(encoded(doc))
    else:
        p.decode_runtime_request(encoded(doc))


@pytest.mark.parametrize(
    "value",
    [
        "2026-09-25T00:00:00.000000Z",
        "2026-09-24T23:59:59.999999Z",
        "2026-09-25T00:01:00.000001Z",
        "2026-02-30T00:00:30.000000Z",
    ],
)
def test_invalid_prerequisite_window(value):
    doc = request_document("verifier-publication")
    doc["prerequisite"]["valid_until"] = value
    with pytest.raises(p.RuntimePacketError):
        p.decode_runtime_request(encoded(doc))


@pytest.mark.parametrize(
    "path",
    [
        ("binding", "bundle", "registry_id"),
        ("binding", "bundle", "bundle_id"),
        ("binding", "qualified_rule", "accepted_content_digest"),
        ("binding", "execution", "org_id"),
        ("binding", "source", "capture_id"),
        ("prerequisite", "org_id"),
        ("prerequisite", "execution_authorization_digest"),
    ],
)
def test_crossed_namespace_and_source_links(path):
    doc = request_document()
    row, key = at(doc, path[:-1]), path[-1]
    row[key] = "0" * 64 if "digest" in key else uid(999)
    with pytest.raises(p.RuntimePacketError, match="link-mismatch"):
        p.decode_runtime_request(encoded(doc))


def test_global_namespace_cannot_supply_customer_permission():
    doc = request_document("verifier-historical")
    doc["binding"]["bundle"].update(scope="global", org_id=None)
    with pytest.raises(p.RuntimePacketError, match="unsupported"):
        p.decode_runtime_request(encoded(doc))


@pytest.mark.parametrize("value", [True, 0, 263245])
def test_syntax_input_size_bound(value):
    doc = request_document()
    doc["input"]["size"] = value
    with pytest.raises(p.RuntimePacketError):
        p.decode_runtime_request(encoded(doc))


@pytest.mark.parametrize(
    "path",
    [
        "/absolute.py",
        "a/../b",
        "a//b",
        "a\\b",
        "a\x7f",
        "a\u0080",
        "a\u009f",
        "/".join(["a"] * 33),
        "a" * 1025,
    ],
)
def test_source_path_rejects(path):
    doc = request_document()
    doc["binding"]["source"]["path"] = path
    with pytest.raises(p.RuntimePacketError):
        p.decode_runtime_request(encoded(doc))


@pytest.mark.parametrize("value", ["a" * 1024, "源.py", "/".join(["a"] * 32), "a\u00a0"])
def test_source_path_boundary(value):
    doc = request_document()
    doc["binding"]["source"]["path"] = value
    p.decode_runtime_request(encoded(doc))


@pytest.mark.parametrize(
    "field",
    [
        "operation_id",
        "deployment_id",
        "installation_id",
        "installation_generation",
        "controller_profile_sha256",
        "domain_profile_sha256",
        "inventory_sha256",
        "program_digest",
        "image_config_id",
        "container_uid",
        "container_gid",
    ],
)
def test_all_repeated_launch_links(field):
    docs = recipe_documents()
    old = docs[1][field]
    docs[1][field] = (
        old + 1
        if type(old) is int
        else uid(999)
        if field.endswith("_id") and field != "image_config_id"
        else "sha256:" + "0" * 64
        if field == "image_config_id"
        else "0" * 64
    )
    with pytest.raises(p.RuntimePacketError, match="link-mismatch"):
        p.decode_runtime_recipe_members(*(encoded(doc) for doc in docs))


@pytest.mark.parametrize(
    "change", ["arg", "path", "env", "cwd", "order", "input-size", "input-hash"]
)
def test_inner_exact_comparison_and_bootstrap_leakage(change):
    docs = recipe_documents()
    launch = docs[1]
    if change == "arg":
        launch["inner"]["argv"][1] = "-E"
    elif change == "path":
        launch["inner"]["argv"][0] = "/other/python"
    elif change == "env":
        launch["inner"]["environment"].append({"name": "PATH", "value": "/bootstrap/bin"})
        launch["inner"]["environment"].sort(key=lambda row: row["name"])
    elif change == "cwd":
        launch["inner"]["cwd"] = "/other"
    elif change == "order":
        launch["inner"]["environment"].reverse()
    elif change == "input-size":
        launch["input"]["size"] += 1
    else:
        launch["input"]["sha256"] = "0" * 64
    with pytest.raises(p.RuntimePacketError):
        p.decode_runtime_recipe_members(*(encoded(doc) for doc in docs))


@pytest.mark.parametrize("side,maximum", [(0, 65536), (1, 65536), (2, 65536), (3, 131072)])
def test_all_four_bytes_admitted_before_any_nested_work(side, maximum, monkeypatch):
    raw = [encoded(doc) for doc in recipe_documents()]
    raw[side] = b" " * (maximum + 1)
    denied = Mock(side_effect=AssertionError("nested parser before admission"))
    monkeypatch.setattr(profiles, "decode_runtime_metadata_documents", denied)
    with pytest.raises(p.RuntimePacketError, match="limit"):
        p.decode_runtime_recipe_members(*raw)
    denied.assert_not_called()


def test_owner_calls_once_and_no_hidden_reparse(monkeypatch):
    raw = tuple(encoded(doc) for doc in recipe_documents())
    metadata = Mock(wraps=profiles.decode_runtime_metadata_documents)
    request, launch = Mock(wraps=p._request), Mock(wraps=p._launch)
    monkeypatch.setattr(profiles, "decode_runtime_metadata_documents", metadata)
    monkeypatch.setattr(p, "_request", request)
    monkeypatch.setattr(p, "_launch", launch)
    p.decode_runtime_recipe_members(*raw)
    assert metadata.call_count == request.call_count == launch.call_count == 1


@pytest.mark.parametrize("mode", MODES)
def test_all_pure_calls_zero_sha_no_effects_even_late_failure(mode, monkeypatch):
    docs = recipe_documents(mode)
    raw = tuple(encoded(doc) for doc in docs)
    request_view, launch_view = stored(docs[0]), stored(docs[1])
    denied = Mock(side_effect=AssertionError("unexpected hash or runtime effect"))
    for owner, name in (
        (hashlib, "sha256"),
        (os, "open"),
        (os, "stat"),
        (time, "monotonic_ns"),
        (profiles, "load_installed_runtime"),
    ):
        monkeypatch.setattr(owner, name, denied)
    p.decode_runtime_request(raw[0])
    p.encode_runtime_request(request_view)
    p.decode_runtime_recipe_members(*raw)
    p.encode_runtime_launch(
        launch_view, request=raw[0], installation=raw[2], controller_profile=raw[3]
    )
    docs[1]["inner"]["cwd"] = "/wrong"
    with pytest.raises(p.RuntimePacketError):
        p.decode_runtime_recipe_members(raw[0], encoded(docs[1]), raw[2], raw[3])
    denied.assert_not_called()


class Poison:
    def __str__(self):
        raise AssertionError("callback")

    def __eq__(self, other):
        raise AssertionError("callback")

    def __len__(self):
        raise AssertionError("callback")

    def __iter__(self):
        raise AssertionError("callback")


class HostileTuple(tuple):
    def __len__(self):
        raise AssertionError("callback")


@pytest.mark.parametrize(
    "value",
    [
        Poison(),
        HostileTuple(),
        (Poison(), ()),
        ("object", Poison()),
        ("object", ((Poison(), 1),)),
        ("object", (("x", Poison()),)),
        ("object", (("x", []),)),
        ("object", (("x", "a"), ("x", "b"))),
        ("object", (("z", 0), ("a", 0))),
    ],
)
def test_writer_rejects_poison_and_noncanonical_tagged_views(value):
    with pytest.raises(p.RuntimePacketError):
        p.encode_runtime_request(value)


@pytest.mark.parametrize(
    "value",
    [
        ("object", tuple((f"x{i:05}", None) for i in range(4096))),
        ("object", (("x", ("array", (None,) * 8192)),)),
        ("object", tuple((f"x{i}", "\x01" * 8192) for i in range(2))),
        ("object", (("x", 2**10000),)),
    ],
)
def test_writer_preallocation_refusal(value, monkeypatch):
    denied = Mock(side_effect=AssertionError("canonical allocation before refusal"))
    monkeypatch.setattr(accepted, "canonical_bytes", denied)
    with pytest.raises(p.RuntimePacketError):
        p.encode_runtime_request(value)
    denied.assert_not_called()


@pytest.mark.parametrize(
    "raw",
    [
        b"{} ",
        b'{"x":1,"x":2}',
        b'{"x":1.5}',
        b'{"x":"\\ud800"}',
        b'{"x":"\\u0000"}',
        b"[" * 17 + b"]" * 17,
        b"[" + b"0," * 8192 + b"0]",
        b"{}{}",
    ],
)
def test_parser_closed_primitive_bounds(raw):
    with pytest.raises(p.RuntimePacketError):
        p.decode_runtime_request(raw)


@pytest.mark.parametrize("failure", [KeyboardInterrupt(), SystemExit(7)])
def test_original_interrupts_unchanged(failure, monkeypatch):
    raw = encoded(request_document())
    monkeypatch.setattr(p, "_request", Mock(side_effect=failure))
    with pytest.raises(type(failure)) as caught:
        p.decode_runtime_request(raw)
    assert caught.value is failure


def test_mutated_carrier_cannot_replace_original_bytes():
    packet = p.decode_runtime_request(encoded(request_document()))
    object.__setattr__(packet, "document", Poison())
    object.__setattr__(packet, "validation", "permitted")
    with pytest.raises(p.RuntimePacketError):
        p.decode_runtime_request(packet)
    assert p.decode_runtime_request(packet.data).validation == "input-structure-only"


@pytest.mark.parametrize("purpose", ["accepted-verifier", "python-syntax"])
def test_inner_renderer_actual_shared_type_exact_intent(purpose):
    mode = "verifier-execution" if purpose == "accepted-verifier" else "python-syntax"
    _, launch, _, _ = recipe_documents(mode)
    result = policy.render_runtime_inner_invocation(
        purpose=purpose,
        python_executable="/runtime/bin/python",
        worker_path="/runtime/application/worker.py",
        domain_profile_path="/metadata/domain_profile",
        domain_profile_sha256=bytes.fromhex("2" * 64),
        attempt_id=launch["attempt_id"],
        stdin_bytes=123,
        stdin_sha256=bytes.fromhex("f" * 64),
    )
    assert type(result) is FrozenInvocation
    assert result.argv == tuple(launch["inner"]["argv"])
    assert result.environment == tuple(
        (row["name"], row["value"]) for row in launch["inner"]["environment"]
    )
    assert result.cwd == launch["inner"]["cwd"] and result.stdin_bytes == 123


@pytest.mark.parametrize(
    "field,value",
    [
        ("purpose", "other"),
        ("purpose", Poison()),
        ("python_executable", Poison()),
        ("worker_path", "/"),
        ("worker_path", "/a/../b"),
        ("domain_profile_path", "/run/scanipy-work/" + uid(60) + "/profile"),
        ("domain_profile_sha256", b"x" * 31),
        ("attempt_id", "bad"),
        ("stdin_bytes", True),
        ("stdin_bytes", 0),
        ("stdin_bytes", 263245),
        ("stdin_sha256", Poison()),
    ],
)
def test_inner_renderer_rejects_before_construction(field, value):
    args = {
        "purpose": "python-syntax",
        "python_executable": "/runtime/bin/python",
        "worker_path": "/runtime/application/worker.py",
        "domain_profile_path": "/metadata/domain_profile",
        "domain_profile_sha256": b"x" * 32,
        "attempt_id": uid(60),
        "stdin_bytes": 1,
        "stdin_sha256": b"y" * 32,
    }
    args[field] = value
    with pytest.raises(policy.RuntimeDockerPolicyError):
        policy.render_runtime_inner_invocation(**args)


def test_real_nested_owner_types_not_substituted(monkeypatch):
    original = accepted.decode_record
    types = []

    def observed(value, kind, rules):
        types.append(kind)
        return original(value, kind, rules)

    monkeypatch.setattr(accepted, "decode_record", observed)
    p.decode_runtime_request(encoded(request_document()))
    assert types == [models.BundleExpectation, models.AdmissionExpectation, models.ExecutionBinding]


@pytest.mark.parametrize("count", [8188, 8189, 8190])
def test_key_inclusive_exact_value_count(count):
    # Private primitive boundary diagnostic, not a valid request schema.
    value = {"x": [None] * count}
    raw = encoded(value)
    if count <= 8189:
        assert p._decode(raw) == value
        assert p._writer_document(stored(value)) == value
    else:
        with pytest.raises(p.RuntimePacketError, match="limit"):
            p._decode(raw)
        with pytest.raises(p.RuntimePacketError, match="limit"):
            p._writer_document(stored(value))


@pytest.mark.parametrize("depth", [15, 16, 17])
def test_exact_container_depth(depth):
    nested = 0
    for _ in range(depth - 1):
        nested = [nested]
    value = {"x": nested}
    if depth <= 16:
        assert p._decode(encoded(value)) == value
        assert p._writer_document(stored(value)) == value
    else:
        with pytest.raises(p.RuntimePacketError, match="limit"):
            p._decode(encoded(value))
        with pytest.raises(p.RuntimePacketError, match="limit"):
            p._writer_document(stored(value))


@pytest.mark.parametrize("size", [65535, 65536, 65537])
def test_exact_encoded_byte_boundary(size):
    value = {"x": ["a" * 8192] * 7 + [""]}
    value["x"][-1] = "b" * (size - len(encoded(value)))
    raw = encoded(value)
    assert len(raw) == size
    if size <= 65536:
        assert p._decode(raw) == value
        assert p._writer_document(stored(value)) == value
    else:
        with pytest.raises(p.RuntimePacketError, match="limit"):
            p._decode(raw)
        with pytest.raises(p.RuntimePacketError, match="limit"):
            p._writer_document(stored(value))


@pytest.mark.parametrize("length", [8191, 8192, 8193])
def test_exact_special_string_boundary(length):
    value = {"x": "a" * length}
    if length <= 8192:
        assert p._decode(encoded(value)) == value
        assert p._writer_document(stored(value)) == value
    else:
        with pytest.raises(p.RuntimePacketError, match="limit"):
            p._decode(encoded(value))
        with pytest.raises(p.RuntimePacketError, match="limit"):
            p._writer_document(stored(value))


@pytest.mark.parametrize("side", range(4))
def test_byte_subclasses_never_dispatch_callbacks(side):
    class HostileBytes(bytes):
        def __len__(self):
            raise AssertionError("callback")

    raw = [encoded(doc) for doc in recipe_documents()]
    raw[side] = HostileBytes(raw[side])
    with pytest.raises(p.RuntimePacketError):
        p.decode_runtime_recipe_members(*raw)


def test_pure_does_not_execute_dynamic_import_or_subprocess(monkeypatch):
    docs = recipe_documents()
    raw = tuple(encoded(doc) for doc in docs)
    views = [stored(doc) for doc in docs[:2]]
    denied = Mock(side_effect=AssertionError("dynamic/runtime work"))
    with monkeypatch.context() as patches:
        for owner, name in (
            (builtins, "open"),
            (builtins, "eval"),
            (builtins, "exec"),
            (subprocess, "Popen"),
            (hashlib, "new"),
            (os, "read"),
            (os, "write"),
            (time, "time"),
            (time, "monotonic"),
            # pytest's own setattr imports inspect: poison imports LAST, after
            # instrumenting the other effects, so the DUT is actually reached.
            (builtins, "__import__"),
        ):
            patches.setattr(owner, name, denied)
        p.decode_runtime_recipe_members(*raw)
        p.encode_runtime_request(views[0])
        p.encode_runtime_launch(
            views[1], request=raw[0], installation=raw[2], controller_profile=raw[3]
        )
    denied.assert_not_called()


def test_tagged_slot_census_is_output_only():
    result = p.decode_runtime_recipe_members(*(encoded(doc) for doc in recipe_documents()))

    def slots(node):
        if type(node) is not tuple:
            return 0
        kind, values = node
        if kind == "object":
            return 2 + len(values) * 3 + sum(slots(value) for _, value in values)
        return 2 + len(values) + sum(slots(value) for value in values)

    # This measures only returned tuples, not total Python/parser/RSS allocation.
    assert (
        sum(
            slots(value)
            for value in (
                result.metadata.installation,
                result.metadata.controller_profile,
                result.request.document,
                result.launch.document,
            )
        )
        <= 169152
    )


def test_private_json_construction_detached_from_view():
    doc = request_document()
    view = stored(doc)
    first, second = p._writer_document(view), p._writer_document(view)
    first["binding"]["source"]["path"] = "changed"
    assert second == doc and view == stored(doc)


def test_error_has_fixed_public_reason_and_private_original():
    doc = request_document()
    doc["binding"]["execution"]["org_id"] = "PRIVATE INVALID UUID"
    with pytest.raises(p.RuntimePacketError) as caught:
        p.decode_runtime_request(encoded(doc))
    assert str(caught.value) == "invalid-input"
    assert "PRIVATE" not in repr(caught.value)
    assert isinstance(caught.value.__cause__, schemas.VerificationError)
