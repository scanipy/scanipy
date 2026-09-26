"""Pure synthetic metadata only; no installed files, authority or native code."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import time
from pathlib import PosixPath
from unittest.mock import Mock

import pytest

from tools.worker import runtime_profiles as p
from tools.worker.runtime_artifacts import RuntimeArtifactBindings

pytestmark = pytest.mark.unit


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def stored(value):
    if type(value) is dict:
        return ("object", tuple((key, stored(item)) for key, item in sorted(value.items())))
    if type(value) is list:
        return ("array", tuple(stored(item) for item in value))
    return value


def metadata_documents(purpose="python-syntax"):
    verifier = purpose == "accepted-verifier"
    installation = {
        "schema": p.INSTALLATION_SCHEMA,
        "deployment_id": "00000000-0000-0000-0000-000000000001",
        "installation_id": "00000000-0000-0000-0000-000000000002",
        "generation": 7,
        "purpose": purpose,
        "controller_uid": 1001,
        "controller_gid": 1002,
        **{
            name: {"path": "/metadata/" + name, "sha256": str(index) * 64}
            for index, name in enumerate(("controller_profile", "domain_profile", "inventory"), 1)
        },
        "docker_cli": {"path": "/bin/docker", "sha256": "4" * 64, "version": "29.1.3"},
        "docker_endpoint": {
            "path": "/run/docker.sock",
            "owner_uid": 0,
            "owner_gid": 123,
            "mode": 432,
        },
        "daemon": {
            "id": "unobserved-daemon",
            "version": "29.1.3",
            "api_version": "1.52",
            "minimum_api_version": "1.44",
        },
        "host_work_root": "/unobserved/work",
        "evidence_root": "/unobserved/evidence",
        "installed_at": "2026-09-25T00:00:00.000000Z",
    }
    memory = 134217728 if verifier else 268435456
    profile = {
        "schema": p.PROFILE_SCHEMA,
        "purpose": purpose,
        "domain_profile_sha256": "2" * 64,
        "inventory_sha256": "3" * 64,
        "program_digest": "5" * 64,
        "runtime": {
            "purpose": purpose,
            "implementation": "cpython",
            "python_version": "3.11.16",
            "protocol_version": "scanipy-accepted-verifier-request/1"
            if verifier
            else "scanipy-python-syntax-request/1",
            "resource_profile": "scanipy-verifier-limits/1"
            if verifier
            else "scanipy-python-syntax-limits/1",
            "executable": {"path": "/runtime/bin/python", "sha256": "6" * 64},
            "worker": {"path": "/runtime/application/worker.py", "sha256": "7" * 64},
            "roots": [
                {"role": role, "ordinal": 0, "path": "/runtime/" + role}
                for role in ("stdlib", "application", "dependency")
            ],
            "application_digest": "8" * 64,
            "dependency_digest": "9" * 64,
            "program_digest": "5" * 64,
        },
        "platform": {
            "os": "linux",
            "architecture": "amd64",
            "implementation": "cpython",
            "python_version": "3.11.16",
            "cgroup_version": 2,
            "cgroup_driver": "systemd",
        },
        "image": {
            "config_id": "sha256:" + "a" * 64,
            "oci_manifest_digest": None,
            "os": "linux",
            "architecture": "amd64",
            "variant": None,
        },
        "bootstrap": {
            "path": "/runtime/application/bootstrap.py",
            "sha256": "b" * 64,
            "protocol": "scanipy-runtime-bootstrap/1",
        },
        "container": {
            "uid": 1001,
            "gid": 1002,
            "network": "none",
            "pid": "private",
            "ipc": "private",
            "cgroupns": "private",
            "userns": "host",
            "readonly_root": True,
            "privileged": False,
            "capabilities": [],
            "no_new_privileges": True,
            "seccomp": "docker-builtin-default/29.1.3",
            "apparmor": "docker-default",
            "restart": "no",
            "auto_remove": False,
            "init": False,
            "tty": False,
            "log_driver": "none",
            "ports": [],
            "devices": [],
        },
        "scratch": {
            "work_root": "/run/scanipy-work",
            "bytes": 8388608,
            "inodes": 1024,
            "mode": 448,
            "nosuid": True,
            "nodev": True,
            "noexec": True,
        },
        "limits": {
            "memory_bytes": memory,
            "memory_swap_bytes": memory,
            "pids": 16,
            "cpu_quota_us": 100000,
            "cpu_period_us": 100000,
            "shm_bytes": 65536,
            "max_mounts": 64,
            "max_bind_mounts": 16,
            "max_additional_tmpfs_bytes": 67174400,
            "max_additional_tmpfs_inodes": 32768,
            "inner_wall_ms": 3000 if verifier else 5000,
            "inner_cleanup_ms": 500,
            "launch_wall_ms": 30000,
            "pre_release_ms": 10000,
            "cleanup_ms": 5000,
            "max_cli_calls": 16,
            "max_kernel_observations": 16,
        },
        "io": {
            "stdin_bytes": 2621440 if verifier else 263244,
            "stdout_bytes": 16384 if verifier else 8388608,
            "stderr_bytes": 16384 if verifier else 65536,
            "combined_bytes": 32768 if verifier else 8454144,
        },
        "config_policy": "scanipy-docker29-pipe-config/1",
    }
    return installation, profile


def dictionaries(value, prefix=()):
    if type(value) is dict:
        yield prefix
        for key, item in value.items():
            yield from dictionaries(item, (*prefix, key))
    elif type(value) is list:
        for index, item in enumerate(value):
            yield from dictionaries(item, (*prefix, index))


def at(value, path):
    for key in path:
        value = value[key]
    return value


def object_cases():
    for side, document in enumerate(metadata_documents()):
        for path in dictionaries(document):
            for key in at(document, path):
                yield side, path, key


@pytest.mark.parametrize("purpose", ["accepted-verifier", "python-syntax"])
def test_complete_original_private_view(purpose):
    left, right = metadata_documents(purpose)
    first, second = encoded(left), encoded(right)
    result = p.decode_runtime_metadata_documents(first, second)
    assert result.installation_bytes == first and result.controller_profile_bytes == second
    assert result.installation == stored(left) and result.controller_profile == stored(right)
    assert type(result.bindings) is RuntimeArtifactBindings
    assert type(result.bindings.worker.path) is PosixPath
    assert result.input_bytes == len(first) + len(second)
    assert result.validation == "input-structure-only"
    assert "unobserved" not in repr(result)
    assert not hasattr(result, "__dict__")
    assert hashlib.sha256(second).hexdigest() != left["controller_profile"]["sha256"]
    # Pure equality of declared hashes explicitly does not validate this raw link.
    left["purpose"] = "modified"
    assert dict(result.installation[1])["purpose"] == purpose


@pytest.mark.parametrize("side,path,key", list(object_cases()), ids=lambda x: str(x))
@pytest.mark.parametrize("change", ["missing", "wrong-type"])
def test_every_required_nested_field(side, path, key, change):
    docs = metadata_documents()
    row = at(docs[side], path)
    if change == "missing":
        del row[key]
    else:
        row[key] = 1 if row[key] is None else None
    with pytest.raises(p.RuntimeProfileError):
        p.decode_runtime_metadata_documents(*(encoded(doc) for doc in docs))


@pytest.mark.parametrize(
    "side,path",
    [(i, path) for i, doc in enumerate(metadata_documents()) for path in dictionaries(doc)],
)
def test_every_nested_object_is_closed(side, path):
    docs = metadata_documents()
    at(docs[side], path)["unrecognized"] = 0
    with pytest.raises(p.RuntimeProfileError):
        p.decode_runtime_metadata_documents(*(encoded(doc) for doc in docs))


@pytest.mark.parametrize(
    "side,field,value",
    [
        (0, "purpose", "other"),
        (0, "generation", True),
        (0, "generation", 0),
        (0, "controller_uid", 0),
        (0, "controller_gid", 2**31),
        (0, "installed_at", "2026-02-30T00:00:00.000000Z"),
        (0, "deployment_id", "00000000000000000000000000000001"),
        (0, "host_work_root", "/"),
        (0, "host_work_root", "/a/../b"),
        (0, "host_work_root", "/a\u0080"),
        (0, "host_work_root", "/a\\b"),
        (1, "program_digest", "A" * 64),
        (1, "domain_profile_sha256", "9" * 64),
    ],
)
def test_scalar_scope_and_declared_links(side, field, value):
    docs = metadata_documents()
    docs[side][field] = value
    with pytest.raises(p.RuntimeProfileError):
        p.decode_runtime_metadata_documents(*(encoded(doc) for doc in docs))


@pytest.mark.parametrize(
    "change", ["duplicate", "order", "ordinal", "empty", "five", "second-application"]
)
def test_exact_root_inventory(change):
    left, right = metadata_documents()
    roots = right["runtime"]["roots"]
    if change == "duplicate":
        roots[1]["path"] = roots[0]["path"]
    elif change == "order":
        roots.reverse()
    elif change == "ordinal":
        roots[0]["ordinal"] = 1
    elif change == "empty":
        roots.clear()
    elif change == "five":
        roots[:1] = [{"role": "stdlib", "ordinal": i, "path": f"/lib/{i}"} for i in range(5)]
    else:
        roots.insert(2, {"role": "application", "ordinal": 1, "path": "/other"})
    with pytest.raises(p.RuntimeProfileError):
        p.decode_runtime_metadata_documents(encoded(left), encoded(right))


@pytest.mark.parametrize("side,maximum", [(0, 65536), (1, 131072)])
def test_both_raw_limits_before_first_parser(side, maximum, monkeypatch):
    docs = [encoded(doc) for doc in metadata_documents()]
    seen = Mock(side_effect=AssertionError("parser called before byte admission"))
    monkeypatch.setattr(p, "_decode", seen)
    docs[side] = b" " * (maximum + 1)
    with pytest.raises(p.RuntimeProfileError, match="limit"):
        p.decode_runtime_metadata_documents(*docs)
    seen.assert_not_called()


@pytest.mark.parametrize(
    "raw",
    [
        b'{"n":' + b"9" * 21 + b"}",
        b'{"n":9223372036854775808}',
        b'{"n":-9223372036854775809}',
        b"[" * 17 + b"]" * 17,
        b"[" + b"0," * 20000 + b"0]",
    ],
)
def test_lexical_admission_before_json(raw, monkeypatch):
    seen = Mock(side_effect=AssertionError("JSON allocation before admission"))
    monkeypatch.setattr(p.json, "loads", seen)
    with pytest.raises(p.RuntimeProfileError):
        p._decode(raw, 131072, None)
    seen.assert_not_called()


@pytest.mark.parametrize(
    "raw",
    [
        b'{"x":0,"x":1}',
        b'{"x":1.5}',
        b'{"x":NaN}',
        b'{"x":true} ',
        b'{"x":"\\u0000"}',
        b'{"x":"\\ud800"}',
        b"{}{}",
        b"\xff",
    ],
)
def test_canonical_primitive_refusal(raw):
    left, right = (encoded(doc) for doc in metadata_documents())
    with pytest.raises(p.RuntimeProfileError):
        p.decode_runtime_metadata_documents(raw, right)
    assert left


@pytest.mark.parametrize("value", [-(2**63), 2**63 - 1])
def test_integer_boundary_still_valid(value):
    assert p._decode(encoded({"n": value}), 65536, None) == {"n": value}


def test_escaped_bytes_admitted_before_dump(monkeypatch):
    seen = Mock(side_effect=AssertionError("dump before escaped-byte admission"))
    monkeypatch.setattr(p.json, "dumps", seen)
    with pytest.raises(p.RuntimeProfileError, match="limit"):
        p._primitive_budget({"n": "\x01" * 4096}, 4096, None)
    seen.assert_not_called()


def test_pure_has_no_hash_clock_files_or_loader(monkeypatch):
    raw = [encoded(doc) for doc in metadata_documents()]
    denied = Mock(side_effect=AssertionError("unexpected effect"))
    for owner, name in (
        (hashlib, "sha256"),
        (os, "open"),
        (os, "stat"),
        (time, "monotonic_ns"),
        (p, "load_installed_runtime"),
        (p.artifacts, "require_installed_runtime_artifacts"),
    ):
        monkeypatch.setattr(owner, name, denied)
    p.decode_runtime_metadata_documents(*raw)
    with pytest.raises(p.RuntimeProfileError):
        p.decode_runtime_metadata_documents(raw[0], b"{}")
    denied.assert_not_called()


def test_private_checkpoint_ignores_instance_callback(monkeypatch):
    monkeypatch.setattr(time, "monotonic_ns", lambda: 0)
    budget = p._Budget(0)
    callback = Mock(side_effect=AssertionError("instance callback"))
    budget.check = callback
    assert p._decode(b"{}", 65536, budget) == {}
    callback.assert_not_called()
    with pytest.raises(p.RuntimeProfileError):
        p._decode(b"{}", 65536, object())


@pytest.mark.parametrize("failure", [KeyboardInterrupt(), SystemExit(3)])
def test_original_interrupt_identity(failure, monkeypatch):
    raw = [encoded(doc) for doc in metadata_documents()]
    monkeypatch.setattr(p, "_installation_document", Mock(side_effect=failure))
    with pytest.raises(type(failure)) as caught:
        p.decode_runtime_metadata_documents(*raw)
    assert caught.value is failure


def test_mutated_carrier_is_not_an_input():
    result = p.decode_runtime_metadata_documents(*(encoded(doc) for doc in metadata_documents()))
    object.__setattr__(result, "validation", "installed")
    with pytest.raises(p.RuntimeProfileError):
        p.decode_runtime_metadata_documents(result, result.controller_profile_bytes)


def test_actual_alias_detached_and_slots_missing_are_not_consulted():
    docs = metadata_documents()
    result = p.decode_runtime_metadata_documents(*(encoded(doc) for doc in docs))
    alias = copy.deepcopy(result)
    object.__delattr__(alias, "bindings")
    assert p.decode_runtime_metadata_documents(
        result.installation_bytes, result.controller_profile_bytes
    ).bindings
    with pytest.raises(p.RuntimeProfileError):
        p.decode_runtime_metadata_documents(alias, result.controller_profile_bytes)


@pytest.mark.parametrize("maximum", [65536, 131072])
@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_metadata_private_byte_boundary(maximum, delta):
    # Primitive-layer test only; this is not installation/profile schema data.
    size = maximum + delta
    value = {"x": ["a" * 4096] * (maximum // 4096 - 1) + [""]}
    value["x"][-1] = "b" * (size - len(encoded(value)))
    raw = encoded(value)
    assert len(raw) == size
    if delta <= 0:
        assert p._decode(raw, maximum, None) == value
    else:
        with pytest.raises(p.RuntimeProfileError, match="limit"):
            p._decode(raw, maximum, None)


@pytest.mark.parametrize("count", [19996, 19997, 19998])
def test_metadata_key_inclusive_value_budget(count):
    # root/key/array use three values; terminal elements use one each.
    raw = encoded({"x": [0] * count})
    if count <= 19997:
        assert p._decode(raw, 131072, None)["x"] == [0] * count
    else:
        with pytest.raises(p.RuntimeProfileError, match="limit"):
            p._decode(raw, 131072, None)


@pytest.mark.parametrize("side", [0, 1])
def test_metadata_byte_subclass_refused_before_callback(side):
    class HostileBytes(bytes):
        def __len__(self):
            raise AssertionError("callback")

    raw = [encoded(doc) for doc in metadata_documents()]
    raw[side] = HostileBytes(raw[side])
    with pytest.raises(p.RuntimeProfileError):
        p.decode_runtime_metadata_documents(*raw)


@pytest.mark.parametrize("version", ["3.12.0", "3.11.00", "3.11.2147483648"])
def test_pure_host_compatibility_does_not_expand_target_profile(version):
    left, right = metadata_documents()
    right["platform"]["python_version"] = version
    right["runtime"]["python_version"] = version
    with pytest.raises(p.RuntimeProfileError, match="unsupported"):
        p.decode_runtime_metadata_documents(encoded(left), encoded(right))
