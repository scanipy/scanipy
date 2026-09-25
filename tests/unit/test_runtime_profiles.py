"""Diagnostic private-file fixtures, never runtime authority or executed code."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from tools.worker import runtime_artifacts as artifacts
from tools.worker import runtime_profiles as profiles

pytestmark = pytest.mark.unit


def encoded(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(raw: bytes) -> bytes:
    return hashlib.sha256(raw).digest()


def domain(schema: str, value: object) -> bytes:
    return sha(schema.encode("ascii") + b"\n" + encoded(value))


def write(path: Path, raw: bytes) -> None:
    path.write_bytes(raw)
    path.chmod(0o600)


@dataclass
class Fixture:
    root: Path
    installation: dict[str, Any]
    outer: dict[str, Any]
    inventory: dict[str, Any]
    domain_bytes: bytes

    def persist(self) -> profiles.RuntimeInstallationAnchor:
        metadata = self.root / "metadata"
        write(metadata / "domain", self.domain_bytes)
        self.inventory["profile_sha256"] = sha(self.domain_bytes).hex()
        inventory_bytes = encoded(self.inventory)
        write(metadata / "inventory", inventory_bytes)
        self.outer["domain_profile_sha256"] = sha(self.domain_bytes).hex()
        self.outer["inventory_sha256"] = sha(inventory_bytes).hex()
        outer_bytes = encoded(self.outer)
        write(metadata / "outer", outer_bytes)
        for name, filename, raw in (
            ("controller_profile", "outer", outer_bytes),
            ("domain_profile", "domain", self.domain_bytes),
            ("inventory", "inventory", inventory_bytes),
        ):
            self.installation[name] = {"path": str(metadata / filename), "sha256": sha(raw).hex()}
        return self.write_installation()

    def write_installation(self) -> profiles.RuntimeInstallationAnchor:
        path = self.root / "metadata" / "installation"
        raw = encoded(self.installation)
        write(path, raw)
        return profiles.RuntimeInstallationAnchor(
            UUID(self.installation["deployment_id"]),
            UUID(self.installation["installation_id"]),
            self.installation["generation"],
            self.installation["purpose"],
            path,
            sha(raw),
            os.geteuid(),
            os.getegid(),
            os.geteuid(),
            os.getegid(),
        )


def prepare(tmp_path: Path, purpose: str = "python-syntax") -> Fixture:
    for name in ("stdlib", "application", "dependency", "metadata", "bin"):
        (tmp_path / name).mkdir(mode=0o700)
    (tmp_path / "stdlib" / "empty").mkdir(mode=0o700)
    content = {
        "stdlib/core.py": b"Not executable stdlib data\x00\xff",
        "application/worker.py": b"raise RuntimeError('never execute worker fixture')\n",
        "application/bootstrap.py": b"raise RuntimeError('never execute bootstrap fixture')\n",
        "dependency/.hidden": b"not an imported dependency",
        "bin/python": b"not an executable interpreter",
    }
    for name, raw in content.items():
        write(tmp_path / name, raw)
    roots = [
        {
            "role": role,
            "ordinal": 0,
            "path": str(tmp_path / role),
            "directories": ["empty"] if role == "stdlib" else [],
            "files": [
                {"path": name.split("/", 1)[1], "size": len(raw), "sha256": sha(raw).hex()}
                for name, raw in sorted(content.items())
                if name.startswith(role + "/")
            ],
        }
        for role in ("stdlib", "application", "dependency")
    ]
    verifier = purpose == "accepted-verifier"
    common = {
        "purpose": purpose,
        "implementation": "cpython",
        "python_version": "3.11.16",
        "protocol_version": "scanipy-accepted-verifier-request/1"
        if verifier
        else "scanipy-python-syntax-request/1",
        "resource_profile": "scanipy-verifier-limits/1"
        if verifier
        else "scanipy-python-syntax-limits/1",
    }
    runtime_rows = [
        {
            "role": role,
            "path": str(tmp_path / name),
            "size": len(content[name]),
            "sha256": sha(content[name]).hex(),
        }
        for role, name in (("executable", "bin/python"), ("worker", "application/worker.py"))
    ]
    groups = {
        role: domain(
            "scanipy-runtime-root-group/1",
            {"role": role, "roots": [r for r in roots if r["role"] == role]},
        ).hex()
        for role in ("stdlib", "application", "dependency")
    }
    program = domain(
        "scanipy-runtime-program/1",
        {
            **common,
            "runtime_bindings": runtime_rows,
            **{r + "_digest": h for r, h in groups.items()},
        },
    ).hex()
    inventory = {
        "schema": artifacts.SCHEMA,
        "profile_sha256": "replaced-on-persist",
        **common,
        "roots": roots,
        "runtime_bindings": runtime_rows,
        "application_digest": groups["application"],
        "dependency_digest": groups["dependency"],
        "program_digest": program,
    }
    runtime = {
        **common,
        "executable": {k: runtime_rows[0][k] for k in ("path", "sha256")},
        "worker": {k: runtime_rows[1][k] for k in ("path", "sha256")},
        "roots": [{k: r[k] for k in ("role", "ordinal", "path")} for r in roots],
        "application_digest": groups["application"],
        "dependency_digest": groups["dependency"],
        "program_digest": program,
    }
    memory = 134217728 if verifier else 268435456
    outer = {
        "schema": profiles.PROFILE_SCHEMA,
        "purpose": purpose,
        "domain_profile_sha256": "replaced-on-persist",
        "inventory_sha256": "replaced-on-persist",
        "program_digest": program,
        "runtime": runtime,
        "platform": {
            "os": "linux",
            "architecture": "amd64",
            "implementation": "cpython",
            "python_version": "3.11.16",
            "cgroup_version": 2,
            "cgroup_driver": "systemd",
        },
        "image": {
            "config_id": "sha256:" + sha(b"diagnostic image pin, not observed image").hex(),
            "oci_manifest_digest": None,
            "os": "linux",
            "architecture": "amd64",
            "variant": None,
        },
        "bootstrap": {
            "path": str(tmp_path / "application/bootstrap.py"),
            "sha256": sha(content["application/bootstrap.py"]).hex(),
            "protocol": "scanipy-runtime-bootstrap/1",
        },
        "container": {
            "uid": os.geteuid(),
            "gid": os.getegid(),
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
    installation = {
        "schema": profiles.INSTALLATION_SCHEMA,
        "deployment_id": "00000000-0000-0000-0000-000000000001",
        "installation_id": "00000000-0000-0000-0000-000000000002",
        "generation": 7,
        "purpose": purpose,
        "controller_uid": os.geteuid(),
        "controller_gid": os.getegid(),
        "controller_profile": None,
        "domain_profile": None,
        "inventory": None,
        "docker_cli": {
            "path": str(tmp_path / "not-opened-docker"),
            "sha256": sha(b"not observed CLI").hex(),
            "version": "29.1.3",
        },
        "docker_endpoint": {
            "path": "/run/docker.sock",
            "owner_uid": 0,
            "owner_gid": 123,
            "mode": 432,
        },
        "daemon": {
            "id": "diagnostic-daemon-pin",
            "version": "29.1.3",
            "api_version": "1.52",
            "minimum_api_version": "1.44",
        },
        "host_work_root": str(tmp_path / "not-created-work"),
        "evidence_root": str(tmp_path / "not-created-evidence"),
        "installed_at": "2026-09-25T00:00:00.000000Z",
    }
    return Fixture(
        tmp_path,
        installation,
        outer,
        inventory,
        b"opaque domain, deliberately NOT a valid domain profile\x00\xff",
    )


@pytest.fixture(autouse=True)
def no_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        pytest.fail("file loader must never spawn/import measured files")

    monkeypatch.setattr(subprocess, "Popen", fail)
    monkeypatch.setattr(os, "system", fail)


@pytest.mark.parametrize("purpose", ["python-syntax", "accepted-verifier"])
def test_real_measurement_retains_exact_origins_and_opaque_domain(tmp_path, purpose):
    fixture = prepare(tmp_path, purpose)
    anchor = fixture.persist()
    loaded = profiles.load_installed_runtime(anchor)
    assert loaded.anchor == anchor and loaded.anchor is not anchor
    assert loaded.anchor.installation_path is not anchor.installation_path
    assert loaded.domain_profile_bytes == fixture.domain_bytes
    assert loaded.installation_bytes == encoded(fixture.installation)
    assert loaded.controller_profile_bytes == encoded(fixture.outer)
    assert type(loaded.measurement) is artifacts.VerifiedRuntimeArtifacts
    assert loaded.measurement.program_digest.hex() == fixture.outer["program_digest"]
    assert loaded.measurement.inventory_bytes == encoded(fixture.inventory)
    assert loaded.installed_inventory.metadata_paths == artifacts.RuntimeMetadataPaths(
        tmp_path / "metadata/inventory",
        tmp_path / "metadata/domain",
        tmp_path / "metadata/installation",
    )
    assert [r.role for r in loaded.metadata_observations] == [
        "installation",
        "controller-profile",
        "domain-profile",
        "inventory",
    ]
    for observed in loaded.metadata_observations:
        raw = observed.path.read_bytes()
        info = observed.path.stat()
        assert observed.sha256 == sha(raw) and observed.size == len(raw)
        assert (
            observed.device,
            observed.inode,
            observed.uid,
            observed.gid,
            observed.mode,
            observed.nlink,
            observed.mtime_ns,
            observed.ctime_ns,
        ) == (
            info.st_dev,
            info.st_ino,
            info.st_uid,
            info.st_gid,
            stat.S_IMODE(info.st_mode),
            info.st_nlink,
            info.st_mtime_ns,
            info.st_ctime_ns,
        )
    assert 0 <= loaded.loaded_elapsed_ms < 35000
    assert not (tmp_path / "not-created-work").exists()
    assert not (tmp_path / "not-created-evidence").exists()


def test_coherent_old_pins_are_data_not_currentness_authority(tmp_path):
    fixture = prepare(tmp_path)
    fixture.installation["generation"] = 1
    anchor = fixture.persist()
    assert profiles.load_installed_runtime(anchor).anchor.generation == 1
    # Only the absent real factory can compare this with a current independent head.


@pytest.mark.parametrize(
    "field,value",
    [
        ("generation", True),
        ("generation", 0),
        ("generation", 2**63),
        ("purpose", "unknown"),
        ("installation_sha256", b"short"),
        ("metadata_owner_uid", -1),
        ("controller_uid", 0),
        ("controller_gid", 2**31),
        ("deployment_id", "not-uuid"),
    ],
)
def test_anchor_constructor_rejects_closed_field_violations(tmp_path, field, value):
    anchor = prepare(tmp_path).persist()
    with pytest.raises(profiles.RuntimeProfileError):
        replace(anchor, **{field: value})


class Poison:
    def __str__(self):
        pytest.fail("poison formatted")

    def __format__(self, _spec):
        pytest.fail("poison formatted")

    def __iter__(self):
        pytest.fail("poison iterated")

    def __getitem__(self, _key):
        pytest.fail("poison indexed")


@pytest.mark.parametrize(
    "member",
    [
        "deployment_id",
        "installation_id",
        "installation_path",
        "purpose",
        "generation",
        "installation_sha256",
    ],
)
def test_mutated_exact_anchor_revalidated_before_access(tmp_path, monkeypatch, member):
    anchor = prepare(tmp_path).persist()
    object.__setattr__(anchor, member, Poison())
    monkeypatch.setattr(os, "open", lambda *_a, **_k: pytest.fail("access before validation"))
    with pytest.raises(profiles.RuntimeProfileError):
        profiles.load_installed_runtime(anchor)


@pytest.mark.parametrize("member", ["deployment_id", "installation_id"])
def test_poisoned_uuid_int_does_not_format(tmp_path, monkeypatch, member):
    anchor = prepare(tmp_path).persist()
    object.__setattr__(getattr(anchor, member), "int", Poison())
    monkeypatch.setattr(os, "open", lambda *_a, **_k: pytest.fail("access before validation"))
    with pytest.raises(profiles.RuntimeProfileError):
        profiles.load_installed_runtime(anchor)


@pytest.mark.parametrize("slot", ["_parts", "_root", "_drv"])
def test_poisoned_path_storage_no_callbacks(tmp_path, monkeypatch, slot):
    anchor = prepare(tmp_path).persist()
    object.__setattr__(anchor.installation_path, slot, Poison())
    monkeypatch.setattr(os, "open", lambda *_a, **_k: pytest.fail("access before validation"))
    with pytest.raises(profiles.RuntimeProfileError):
        profiles.load_installed_runtime(anchor)


def test_ignore_poisoned_path_cache_and_snapshot_before_first_access(tmp_path, monkeypatch):
    anchor = prepare(tmp_path).persist()
    original = str(anchor.installation_path)
    object.__setattr__(anchor.installation_path, "_str", "/wrong-cached-location")
    actual_open = os.open

    def mutate(*args, **kwargs):
        object.__setattr__(anchor.installation_path, "_parts", Poison())
        return actual_open(*args, **kwargs)

    monkeypatch.setattr(os, "open", mutate)
    loaded = profiles.load_installed_runtime(anchor)
    assert str(loaded.anchor.installation_path) == original


@pytest.mark.parametrize("name", ["controller_uid", "controller_gid"])
def test_wrong_actual_identity_refuses_before_read(tmp_path, monkeypatch, name):
    anchor = prepare(tmp_path).persist()
    changed = replace(anchor, **{name: getattr(anchor, name) + 1})
    monkeypatch.setattr(os, "open", lambda *_a, **_k: pytest.fail("access with wrong controller"))
    with pytest.raises(profiles.RuntimeProfileError, match="unsupported"):
        profiles.load_installed_runtime(changed)


@pytest.mark.parametrize(
    "section",
    [None, "platform", "image", "bootstrap", "container", "scratch", "limits", "io", "runtime"],
)
def test_unknown_outer_fields_are_rejected(tmp_path, section):
    fixture = prepare(tmp_path)
    (fixture.outer if section is None else fixture.outer[section])["unknown"] = "rejected"
    with pytest.raises(profiles.RuntimeProfileError, match="metadata-invalid"):
        profiles.load_installed_runtime(fixture.persist())


@pytest.mark.parametrize(
    "section,field,value",
    [
        ("container", "readonly_root", 1),
        ("container", "uid", True),
        ("container", "network", "host"),
        ("container", "capabilities", ["ALL"]),
        ("limits", "pids", True),
        ("limits", "memory_bytes", 536870912),
        ("limits", "inner_wall_ms", 30000),
        ("io", "combined_bytes", 10000000),
        ("platform", "python_version", "3.12.1"),
        ("platform", "python_version", "3.11.01"),
        ("platform", "cgroup_version", True),
        ("image", "config_id", "sha256:" + "A" * 64),
        ("image", "variant", "v8"),
        ("bootstrap", "protocol", "unknown/1"),
        ("runtime", "resource_profile", "caller-policy"),
        ("runtime", "program_digest", "0" * 64),
    ],
)
def test_closed_outer_values_and_repeated_pins(tmp_path, section, field, value):
    fixture = prepare(tmp_path)
    fixture.outer[section][field] = value
    with pytest.raises(profiles.RuntimeProfileError):
        profiles.load_installed_runtime(fixture.persist())


@pytest.mark.parametrize(
    "section",
    [
        None,
        "docker_cli",
        "docker_endpoint",
        "daemon",
        "controller_profile",
        "domain_profile",
        "inventory",
    ],
)
def test_unknown_installation_fields(tmp_path, section):
    fixture = prepare(tmp_path)
    fixture.persist()
    (fixture.installation if section is None else fixture.installation[section])["extra"] = 1
    with pytest.raises(profiles.RuntimeProfileError):
        profiles.load_installed_runtime(fixture.write_installation())


@pytest.mark.parametrize(
    "field,value",
    [
        ("generation", 8),
        ("purpose", "accepted-verifier"),
        ("deployment_id", UUID(int=3)),
        ("installation_id", UUID(int=4)),
        ("installation_sha256", b"x" * 32),
    ],
)
def test_anchor_document_mismatch(tmp_path, field, value):
    anchor = prepare(tmp_path).persist()
    with pytest.raises(profiles.RuntimeProfileError):
        profiles.load_installed_runtime(replace(anchor, **{field: value}))


@pytest.mark.parametrize(
    "target",
    ["metadata", "stdlib", "application/worker.py", "not-created-evidence", "metadata/domain"],
)
def test_host_work_overlap_rejected(tmp_path, target):
    fixture = prepare(tmp_path)
    fixture.installation["host_work_root"] = str(tmp_path / target)
    with pytest.raises(profiles.RuntimeProfileError, match="unsafe-path"):
        profiles.load_installed_runtime(fixture.persist())


@pytest.mark.parametrize(
    "kind", ["symlink", "hardlink", "fifo", "directory", "world-readable", "parent-mode"]
)
def test_metadata_special_and_permission_rejection(tmp_path, kind):
    fixture = prepare(tmp_path)
    anchor = fixture.persist()
    path = anchor.installation_path
    if kind == "symlink":
        moved = path.with_name("retained-original")
        path.rename(moved)
        path.symlink_to(moved)
    elif kind == "hardlink":
        os.link(path, path.with_name("second-link"))
    elif kind == "fifo":
        path.unlink()
        os.mkfifo(path, 0o600)
    elif kind == "directory":
        path.unlink()
        path.mkdir(mode=0o700)
    elif kind == "world-readable":
        path.chmod(0o644)
    else:
        path.parent.chmod(0o755)
    started = time.monotonic()
    with pytest.raises(profiles.RuntimeProfileError):
        profiles.load_installed_runtime(anchor)
    assert time.monotonic() - started < 2  # FIFO open is nonblocking, never waits for a writer.


def test_readonly_metadata_is_supported(tmp_path):
    anchor = prepare(tmp_path).persist()
    for path in anchor.installation_path.parent.iterdir():
        path.chmod(0o400)
    assert profiles.load_installed_runtime(anchor).anchor == anchor


@pytest.mark.parametrize(
    "target",
    [
        "stdlib/core.py",
        "application/worker.py",
        "application/bootstrap.py",
        "dependency/.hidden",
        "bin/python",
    ],
)
def test_actual_file_change_cannot_pass_configured_hash_equality(tmp_path, target):
    fixture = prepare(tmp_path)
    anchor = fixture.persist()
    write(tmp_path / target, b"changed actual bytes")
    with pytest.raises(profiles.RuntimeProfileError, match="artifact-mismatch"):
        profiles.load_installed_runtime(anchor)


def test_extra_file_is_not_hidden_by_inventory(tmp_path):
    anchor = prepare(tmp_path).persist()
    write(tmp_path / "dependency/extra", b"unexpected")
    with pytest.raises(profiles.RuntimeProfileError, match="artifact-mismatch"):
        profiles.load_installed_runtime(anchor)


@pytest.mark.parametrize("kind", ["outside", "wrong-hash", "missing"])
def test_bootstrap_requires_actual_application_member(tmp_path, kind):
    fixture = prepare(tmp_path)
    if kind == "outside":
        fixture.outer["bootstrap"]["path"] = str(tmp_path / "bin/python")
    elif kind == "missing":
        fixture.outer["bootstrap"]["path"] = str(tmp_path / "application/absent")
    else:
        fixture.outer["bootstrap"]["sha256"] = "0" * 64
    with pytest.raises(profiles.RuntimeProfileError, match="artifact-mismatch"):
        profiles.load_installed_runtime(fixture.persist())


@pytest.mark.parametrize("size", [65535, 65536, 65537])
def test_domain_opaque_byte_ceiling(tmp_path, size):
    fixture = prepare(tmp_path)
    fixture.domain_bytes = b"\xff" * size
    anchor = fixture.persist()
    if size > 65536:
        with pytest.raises(profiles.RuntimeProfileError, match="limit"):
            profiles.load_installed_runtime(anchor)
    else:
        assert profiles.load_installed_runtime(anchor).domain_profile_bytes == fixture.domain_bytes


@pytest.mark.parametrize(
    "raw",
    [
        b'{"x":1,"x":2}',
        b'{"x":1.0}',
        b'{"x":NaN}',
        b'{"x":9223372036854775808}',
        b'{"x":"\\ud800"}',
        b'{"x":"\\u0000"}',
        b'{ "x":1}',
        b'{"x":1}\n',
        b"\xef\xbb\xbf{}",
    ],
)
def test_strict_canonical_json_rejects_invalid_bytes(raw):
    with pytest.raises((profiles.RuntimeProfileError, ValueError)):
        profiles._decode(raw, 65536, profiles._Budget(time.monotonic_ns()))


@pytest.mark.parametrize("raw", [b"[" * 17 + b"0" + b"]" * 17, b"[" + b"0," * 20000 + b"0]"])
def test_decode_structure_budget_precedes_json_parser(monkeypatch, raw):
    monkeypatch.setattr(json, "loads", lambda *_a, **_k: pytest.fail("overbudget parser invoked"))
    with pytest.raises(profiles.RuntimeProfileError, match="limit"):
        profiles._decode(raw, 65536, profiles._Budget(time.monotonic_ns()))


def test_aggregate_escaped_bytes_rejected_before_serialization(monkeypatch):
    large = ["\x01" * 4096] * 10
    monkeypatch.setattr(json, "dumps", lambda *_a, **_k: pytest.fail("overbudget dumps invoked"))
    with pytest.raises(profiles.RuntimeProfileError, match="limit"):
        profiles._primitive_budget(large, 65536, profiles._Budget(time.monotonic_ns()))


def test_shared_branch_and_queued_values_bound():
    shared: object = 0
    for _ in range(16):
        shared = [shared, shared]
    with pytest.raises(profiles.RuntimeProfileError, match="limit"):
        profiles._primitive_budget(shared, 65536, profiles._Budget(time.monotonic_ns()))


@pytest.mark.parametrize("operation", ["open", "read", "fstat", "stat"])
def test_original_storage_failure_retained_without_paths(tmp_path, monkeypatch, operation):
    anchor = prepare(tmp_path).persist()
    original = OSError("private file contents must stay private")

    def fail(*_args, **_kwargs):
        raise original

    monkeypatch.setattr(os, operation, fail)
    with pytest.raises(profiles.RuntimeProfileError) as caught:
        profiles.load_installed_runtime(anchor)
    assert caught.value.__cause__ is original
    assert str(caught.value) == "installation-unavailable"


def test_short_reads_are_assembled_through_eof(tmp_path, monkeypatch):
    anchor = prepare(tmp_path).persist()
    actual = os.read
    monkeypatch.setattr(os, "read", lambda fd, size: actual(fd, min(size, 7)))
    assert profiles.load_installed_runtime(anchor).anchor == anchor


def test_early_eof_rejected(tmp_path, monkeypatch):
    anchor = prepare(tmp_path).persist()
    monkeypatch.setattr(os, "read", lambda *_a: b"")
    with pytest.raises(profiles.RuntimeProfileError, match="metadata-invalid"):
        profiles.load_installed_runtime(anchor)


def test_metadata_replacement_after_measurement_rejected(tmp_path, monkeypatch):
    anchor = prepare(tmp_path).persist()
    actual = artifacts.require_installed_runtime_artifacts

    def replace_after(*args, **kwargs):
        result = actual(*args, **kwargs)
        path = tmp_path / "metadata/domain"
        replacement = tmp_path / "metadata/replacement"
        write(replacement, path.read_bytes())
        replacement.replace(path)
        return result

    monkeypatch.setattr(artifacts, "require_installed_runtime_artifacts", replace_after)
    with pytest.raises(profiles.RuntimeProfileError, match="metadata-invalid"):
        profiles.load_installed_runtime(anchor)


def test_first_filesystem_and_final_success_deadlines(tmp_path, monkeypatch):
    anchor = prepare(tmp_path).persist()
    clock = iter([0, 35_000_000_000])
    monkeypatch.setattr(profiles.time, "monotonic_ns", lambda: next(clock))
    monkeypatch.setattr(os, "open", lambda *_a, **_k: pytest.fail("open after expired deadline"))
    with pytest.raises(profiles.RuntimeProfileError, match="deadline"):
        profiles.load_installed_runtime(anchor)


def test_late_result_construction_and_cleanup_are_charged(tmp_path, monkeypatch):
    anchor = prepare(tmp_path).persist()
    clock = [0]
    monkeypatch.setattr(time, "monotonic_ns", lambda: clock[0])
    original = profiles.LoadedRuntimeInstallation

    def slow(*args, **kwargs):
        result = original(*args, **kwargs)
        clock[0] = 35_000_000_000
        return result

    monkeypatch.setattr(profiles, "LoadedRuntimeInstallation", slow)
    with pytest.raises(profiles.RuntimeProfileError, match="deadline"):
        profiles.load_installed_runtime(anchor)


def test_remaining_deadline_is_forwarded_to_actual_measurement(tmp_path, monkeypatch):
    anchor = prepare(tmp_path).persist()
    clock = [0]
    monkeypatch.setattr(time, "monotonic_ns", lambda: clock[0])
    original_read = profiles._Files.read
    original_measure = artifacts.require_installed_runtime_artifacts

    def read(*args, **kwargs):
        result = original_read(*args, **kwargs)
        clock[0] = 10_000_000_000
        return result

    seen = []

    def measure(*args, **kwargs):
        seen.append(kwargs["limits"].wall_ms)
        return original_measure(*args, **kwargs)

    monkeypatch.setattr(profiles._Files, "read", read)
    monkeypatch.setattr(artifacts, "require_installed_runtime_artifacts", measure)
    profiles.load_installed_runtime(anchor)
    assert seen == [25000]


def test_original_interrupt_and_cleanup_failures_preserved(tmp_path, monkeypatch):
    anchor = prepare(tmp_path).persist()
    original = KeyboardInterrupt("private interrupt")
    prior = ValueError("prior private cause")
    original.__cause__ = prior
    actual_close = os.close
    calls = []
    failures = []

    def fail_read(*_args):
        raise original

    def close(fd):
        assert fd not in calls  # Loader retains all its metadata FDs until this cleanup.
        calls.append(fd)
        actual_close(fd)
        failure = OSError("uncertain closed descriptor")
        failures.append(failure)
        raise failure

    monkeypatch.setattr(os, "read", fail_read)
    monkeypatch.setattr(os, "close", close)
    with pytest.raises(KeyboardInterrupt) as caught:
        profiles.load_installed_runtime(anchor)
    assert caught.value is original
    assert isinstance(original.__cause__, BaseExceptionGroup)
    assert original.__cause__.exceptions == (prior, *failures)
    assert calls


def test_final_close_failure_refuses_success(tmp_path, monkeypatch):
    anchor = prepare(tmp_path).persist()
    real_close = profiles._Files.close
    actual_close = os.close
    failure = OSError("final close failure")

    def fail_final(self, primary):
        failed = False

        def close(fd):
            nonlocal failed
            actual_close(fd)
            if not failed:
                failed = True
                raise failure

        with monkeypatch.context() as context:
            context.setattr(os, "close", close)
            real_close(self, primary)

    monkeypatch.setattr(profiles._Files, "close", fail_final)
    with pytest.raises(profiles.RuntimeProfileError, match="cleanup-incomplete") as caught:
        profiles.load_installed_runtime(anchor)
    assert isinstance(caught.value.__cause__, BaseExceptionGroup)
    assert failure in caught.value.__cause__.exceptions


def test_metadata_opens_are_nofollow_nonblocking(tmp_path, monkeypatch):
    anchor = prepare(tmp_path).persist()
    actual = os.open
    files = []

    def opened(path, flags, *args, **kwargs):
        if not flags & os.O_DIRECTORY:
            assert flags & os.O_NOFOLLOW and flags & os.O_NONBLOCK and flags & os.O_CLOEXEC
            files.append(path)
        return actual(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", opened)
    profiles.load_installed_runtime(anchor)
    assert {"installation", "outer", "domain", "inventory"} <= set(files)


def test_cap_refusal_before_extra_fd_or_payload(tmp_path, monkeypatch):
    anchor = prepare(tmp_path).persist()
    monkeypatch.setattr(profiles, "_MAX_FDS", 1)
    with pytest.raises(profiles.RuntimeProfileError, match="limit"):
        profiles.load_installed_runtime(anchor)


@pytest.mark.parametrize("name", ["_MAX_OBSERVATIONS", "_MAX_METADATA"])
def test_cumulative_limits_fail_closed(tmp_path, monkeypatch, name):
    anchor = prepare(tmp_path).persist()
    monkeypatch.setattr(profiles, name, 1)
    with pytest.raises(profiles.RuntimeProfileError, match="limit"):
        profiles.load_installed_runtime(anchor)


@pytest.mark.parametrize("member", ["generation", "installation_path", "deployment_id"])
def test_missing_anchor_slot_typed_error_before_access(tmp_path, monkeypatch, member):
    anchor = prepare(tmp_path).persist()
    object.__delattr__(anchor, member)
    monkeypatch.setattr(os, "open", lambda *_a, **_k: pytest.fail("missing slot used"))
    with pytest.raises(profiles.RuntimeProfileError, match="metadata-invalid"):
        profiles.load_installed_runtime(anchor)


def test_subclass_and_custom_path_components_do_not_dispatch(tmp_path, monkeypatch):
    anchor = prepare(tmp_path).persist()

    class HostileList(list):
        def __getitem__(self, _key):
            pytest.fail("custom list indexing dispatched")

    object.__setattr__(anchor.installation_path, "_parts", HostileList(["/", "ignored"]))
    monkeypatch.setattr(os, "open", lambda *_a, **_k: pytest.fail("hostile path accessed"))
    with pytest.raises(profiles.RuntimeProfileError):
        profiles.load_installed_runtime(anchor)


@pytest.mark.parametrize("slot", ["_parts", "_root", "_drv"])
def test_unsupported_path_layout_typed_failure(tmp_path, monkeypatch, slot):
    anchor = prepare(tmp_path).persist()
    object.__delattr__(anchor.installation_path, slot)
    monkeypatch.setattr(os, "open", lambda *_a, **_k: pytest.fail("unknown path layout accessed"))
    with pytest.raises(profiles.RuntimeProfileError, match="unsupported"):
        profiles.load_installed_runtime(anchor)


@pytest.mark.parametrize("name", ["metadata_owner_uid", "metadata_owner_gid"])
def test_wrong_metadata_owner_pin(tmp_path, name):
    anchor = prepare(tmp_path).persist()
    with pytest.raises(profiles.RuntimeProfileError, match="unsafe-path"):
        profiles.load_installed_runtime(replace(anchor, **{name: getattr(anchor, name) + 1}))


@pytest.mark.parametrize("kind", ["symlink", "writable", "sticky"])
def test_unsafe_metadata_ancestor(tmp_path, kind):
    fixture = prepare(tmp_path)
    anchor = fixture.persist()
    if kind == "symlink":
        parent = tmp_path / "metadata"
        moved = tmp_path / "retained-metadata"
        parent.rename(moved)
        parent.symlink_to(moved, target_is_directory=True)
    elif kind == "writable":
        tmp_path.chmod(0o775)
    else:
        tmp_path.chmod(0o1777)  # Only literal root-owned /tmp gets the exception.
    with pytest.raises(profiles.RuntimeProfileError):
        profiles.load_installed_runtime(anchor)


def test_bootstrap_size_limit_is_checked_on_real_measured_member(tmp_path):
    fixture = prepare(tmp_path)
    raw = b"x" * (1048576 + 1)
    path = tmp_path / "application/bootstrap.py"
    write(path, raw)
    app = fixture.inventory["roots"][1]
    row = next(r for r in app["files"] if r["path"] == "bootstrap.py")
    row.update(size=len(raw), sha256=sha(raw).hex())
    application = domain(
        "scanipy-runtime-root-group/1", {"role": "application", "roots": [app]}
    ).hex()
    program = {
        k: fixture.inventory[k]
        for k in (
            "purpose",
            "implementation",
            "python_version",
            "protocol_version",
            "resource_profile",
            "runtime_bindings",
        )
    }
    for role in ("stdlib", "application", "dependency"):
        program[role + "_digest"] = domain(
            "scanipy-runtime-root-group/1",
            {"role": role, "roots": [r for r in fixture.inventory["roots"] if r["role"] == role]},
        ).hex()
    checksum = domain("scanipy-runtime-program/1", program).hex()
    fixture.inventory.update(application_digest=application, program_digest=checksum)
    fixture.outer["runtime"].update(application_digest=application, program_digest=checksum)
    fixture.outer["program_digest"] = checksum
    fixture.outer["bootstrap"]["sha256"] = sha(raw).hex()
    with pytest.raises(profiles.RuntimeProfileError, match="artifact-mismatch"):
        profiles.load_installed_runtime(fixture.persist())


@pytest.mark.parametrize(
    "field,target",
    [
        ("controller_profile", "domain_profile"),
        ("inventory", "controller_profile"),
        ("domain_profile", "installation"),
    ],
)
def test_metadata_origin_collisions_rejected_before_second_read(tmp_path, field, target):
    fixture = prepare(tmp_path)
    fixture.persist()
    fixture.installation[field]["path"] = (
        str(tmp_path / "metadata/installation")
        if target == "installation"
        else fixture.installation[target]["path"]
    )
    with pytest.raises(profiles.RuntimeProfileError, match="unsafe-path"):
        profiles.load_installed_runtime(fixture.write_installation())


@pytest.mark.parametrize("kind", ["purpose", "ordinal", "extra-field", "duplicate-root"])
def test_runtime_projection_rejects_malformed_shared_bindings(tmp_path, kind):
    fixture = prepare(tmp_path)
    runtime = fixture.outer["runtime"]
    if kind == "purpose":
        runtime["purpose"] = "accepted-verifier"
    elif kind == "ordinal":
        runtime["roots"][0]["ordinal"] = True
    elif kind == "extra-field":
        runtime["executable"]["unknown"] = 1
    else:
        runtime["roots"][1]["path"] = runtime["roots"][0]["path"]
    with pytest.raises(profiles.RuntimeProfileError):
        profiles.load_installed_runtime(fixture.persist())


@pytest.mark.parametrize(
    "role,maximum", [("installation", 65536), ("outer", 131072), ("inventory", 8388608)]
)
def test_file_size_ceiling_checked_before_payload_read(tmp_path, monkeypatch, role, maximum):
    fixture = prepare(tmp_path)
    anchor = fixture.persist()
    path = tmp_path / "metadata" / role
    with path.open("r+b") as stream:
        stream.truncate(maximum + 1)
    forbidden_inode = path.stat().st_ino
    real_read = os.read

    def read(fd, size):
        assert os.fstat(fd).st_ino != forbidden_inode
        return real_read(fd, size)

    monkeypatch.setattr(os, "read", read)
    with pytest.raises(profiles.RuntimeProfileError, match="limit"):
        profiles.load_installed_runtime(anchor)


def test_noncanonical_outer_failure_is_typed_and_private(tmp_path):
    fixture = prepare(tmp_path)
    fixture.persist()
    path = tmp_path / "metadata/outer"
    raw = b'{"private_secret":'
    write(path, raw)
    fixture.installation["controller_profile"]["sha256"] = sha(raw).hex()
    with pytest.raises(profiles.RuntimeProfileError) as caught:
        profiles.load_installed_runtime(fixture.write_installation())
    assert str(caught.value) == "metadata-invalid"


def test_slow_final_close_is_in_deadline(tmp_path, monkeypatch):
    anchor = prepare(tmp_path).persist()
    clock = [0]
    monkeypatch.setattr(time, "monotonic_ns", lambda: clock[0])
    original = profiles._Files.close

    def slow(self, primary):
        original(self, primary)
        clock[0] = 35_000_000_000

    monkeypatch.setattr(profiles._Files, "close", slow)
    with pytest.raises(profiles.RuntimeProfileError, match="deadline"):
        profiles.load_installed_runtime(anchor)


def test_success_elapsed_includes_descriptor_disposal(tmp_path, monkeypatch):
    anchor = prepare(tmp_path).persist()
    clock = [0]
    monkeypatch.setattr(time, "monotonic_ns", lambda: clock[0])
    original = profiles._Files.close

    def slow(self, primary):
        original(self, primary)
        clock[0] = 2_000_000_000

    monkeypatch.setattr(profiles._Files, "close", slow)
    assert profiles.load_installed_runtime(anchor).loaded_elapsed_ms == 2000


@pytest.mark.parametrize("kind", ["KeyboardInterrupt", "SystemExit", "OSError"])
def test_failed_child_fstat_closes_child_and_all_ancestors_once(tmp_path, monkeypatch, kind):
    anchor = prepare(tmp_path).persist()
    actual_open, actual_fstat, actual_close = os.open, os.fstat, os.close
    opened, closed = [], []
    original = {
        "KeyboardInterrupt": KeyboardInterrupt(),
        "SystemExit": SystemExit(),
        "OSError": OSError("private fstat"),
    }[kind]

    def opening(*args, **kwargs):
        fd = actual_open(*args, **kwargs)
        opened.append(fd)
        return fd

    def observed(fd):
        if len(opened) == 2:
            raise original
        return actual_fstat(fd)

    def closing(fd):
        closed.append(fd)
        actual_close(fd)

    monkeypatch.setattr(os, "open", opening)
    monkeypatch.setattr(os, "fstat", observed)
    monkeypatch.setattr(os, "close", closing)
    with pytest.raises((profiles.RuntimeProfileError, KeyboardInterrupt, SystemExit)) as caught:
        profiles.load_installed_runtime(anchor)
    assert sorted(opened) == sorted(closed) and len(set(closed)) == len(closed)
    if kind != "OSError":
        assert caught.value is original
    else:
        assert caught.value.__cause__ is original


@pytest.mark.parametrize("size", [4095, 4096, 4097])
def test_text_bytes_bound_before_encoding(size):
    if size > 4096:
        # Lone surrogate proves the character-count bound fires before UTF-8 work.
        with pytest.raises(profiles.RuntimeProfileError, match="limit"):
            profiles._text("x" * (size - 1) + "\ud800")
    else:
        assert profiles._text("x" * size) == "x" * size


@pytest.mark.parametrize("prior_kind", ["context", "cause", "both"])
def test_public_loader_preserves_implicit_context_through_cleanup(
    tmp_path, monkeypatch, prior_kind
):
    anchor = prepare(tmp_path).persist()
    original = KeyboardInterrupt("private primary")
    context = ValueError("private implicit context")
    cause = ValueError("private explicit cause")
    original.__context__ = context
    if prior_kind in ("cause", "both"):
        original.__cause__ = cause
    if prior_kind == "cause":
        original.__context__ = None
    expected = cause if prior_kind != "context" else context
    actual_close = os.close
    closed = []
    cleanup = OSError("private close uncertainty")

    def interrupted(*_args):
        raise original

    def uncertain(fd):
        assert fd not in closed
        closed.append(fd)
        actual_close(fd)
        if len(closed) == 1:
            raise cleanup

    monkeypatch.setattr(os, "read", interrupted)
    monkeypatch.setattr(os, "close", uncertain)
    with pytest.raises(KeyboardInterrupt) as caught:
        profiles.load_installed_runtime(anchor)
    assert caught.value is original
    assert isinstance(original.__cause__, BaseExceptionGroup)
    assert original.__cause__.exceptions == (expected, cleanup)
    if prior_kind == "both":
        assert original.__context__ is context


@pytest.mark.parametrize("failing_close", [False, True])
@pytest.mark.parametrize("prior_kind", ["context", "cause"])
def test_direct_cleanup_retains_chain_and_original_primary(
    tmp_path, monkeypatch, failing_close, prior_kind
):
    anchor = prepare(tmp_path).persist()
    original = KeyboardInterrupt("private original")
    prior = ValueError("private prior")
    setattr(original, "__" + prior_kind + "__", prior)
    files = profiles._Files(anchor, profiles._Budget(time.monotonic_ns()))
    descriptor = os.open(anchor.installation_path, os.O_RDONLY | os.O_CLOEXEC)
    files.owned.append(descriptor)
    actual_close = os.close
    cleanup = OSError("private cleanup")
    calls = []

    def close(fd):
        calls.append(fd)
        actual_close(fd)
        if failing_close:
            raise cleanup

    monkeypatch.setattr(os, "close", close)
    with pytest.raises(KeyboardInterrupt) as caught:
        files.close(original)
    assert caught.value is original and calls == [descriptor] and not files.owned
    if failing_close:
        assert isinstance(original.__cause__, BaseExceptionGroup)
        assert original.__cause__.exceptions == (prior, cleanup)
    else:
        assert getattr(original, "__" + prior_kind + "__") is prior


@pytest.mark.parametrize("mutate_later", [False, True])
def test_promoted_cleanup_interruption_keeps_implicit_context(tmp_path, monkeypatch, mutate_later):
    anchor = prepare(tmp_path).persist()
    files = profiles._Files(anchor, profiles._Budget(time.monotonic_ns()))
    for _ in range(2):
        files.owned.append(os.open(anchor.installation_path, os.O_RDONLY | os.O_CLOEXEC))
    original = KeyboardInterrupt("cleanup interrupt")
    prior = ValueError("prior context")
    original.__context__ = prior
    cleanup = OSError("other close failure")
    actual_close = os.close
    closed = []

    def close(fd):
        assert fd not in closed
        closed.append(fd)
        actual_close(fd)
        if len(closed) == 2 and mutate_later:
            original.__context__ = ValueError("context changed by later cleanup")
        raise original if len(closed) == 1 else cleanup

    monkeypatch.setattr(os, "close", close)
    with pytest.raises(KeyboardInterrupt) as caught:
        files.close(None)
    assert caught.value is original
    assert isinstance(original.__cause__, BaseExceptionGroup)
    assert original.__cause__.exceptions == (prior, cleanup)
    assert len(closed) == 2 and not files.owned


def test_prior_context_is_snapshotted_before_cleanup_mutation(tmp_path, monkeypatch):
    anchor = prepare(tmp_path).persist()
    files = profiles._Files(anchor, profiles._Budget(time.monotonic_ns()))
    descriptor = os.open(anchor.installation_path, os.O_RDONLY | os.O_CLOEXEC)
    files.owned.append(descriptor)
    original = KeyboardInterrupt("primary")
    prior = ValueError("original context")
    original.__context__ = prior
    cleanup = OSError("cleanup")
    actual_close = os.close

    def close(fd):
        actual_close(fd)
        original.__context__ = ValueError("later context")
        raise cleanup

    monkeypatch.setattr(os, "close", close)
    with pytest.raises(KeyboardInterrupt) as caught:
        files.close(original)
    assert caught.value is original
    assert isinstance(original.__cause__, BaseExceptionGroup)
    assert original.__cause__.exceptions == (prior, cleanup)


def test_cleanup_does_not_duplicate_prior_object_in_group(tmp_path, monkeypatch):
    anchor = prepare(tmp_path).persist()
    files = profiles._Files(anchor, profiles._Budget(time.monotonic_ns()))
    descriptor = os.open(anchor.installation_path, os.O_RDONLY | os.O_CLOEXEC)
    files.owned.append(descriptor)
    original = KeyboardInterrupt("primary")
    prior = OSError("same retained evidence")
    original.__context__ = prior
    actual_close = os.close

    def close(fd):
        actual_close(fd)
        raise prior

    monkeypatch.setattr(os, "close", close)
    with pytest.raises(KeyboardInterrupt) as caught:
        files.close(original)
    assert caught.value is original
    assert isinstance(original.__cause__, BaseExceptionGroup)
    assert original.__cause__.exceptions == (prior,)


@pytest.mark.parametrize("promoted", [False, True])
def test_cleanup_does_not_truth_test_explicit_cause(tmp_path, monkeypatch, promoted):
    class PoisonBoolError(ValueError):
        def __bool__(self):
            pytest.fail("cleanup must not truth-test an exception")

    anchor = prepare(tmp_path).persist()
    files = profiles._Files(anchor, profiles._Budget(time.monotonic_ns()))
    for _ in range(2 if promoted else 1):
        files.owned.append(os.open(anchor.installation_path, os.O_RDONLY | os.O_CLOEXEC))
    original = KeyboardInterrupt("original")
    prior = PoisonBoolError("explicit cause")
    original.__cause__ = prior
    original.__context__ = ValueError("must not replace explicit cause")
    failure = OSError("uncertain close")
    real_close = os.close
    calls = []

    def close(fd):
        calls.append(fd)
        real_close(fd)
        if promoted and len(calls) == 1:
            raise original
        raise failure

    monkeypatch.setattr(os, "close", close)
    with pytest.raises(KeyboardInterrupt) as caught:
        files.close(None if promoted else original)
    assert caught.value is original
    assert isinstance(original.__cause__, BaseExceptionGroup)
    assert original.__cause__.exceptions == (prior, failure)
