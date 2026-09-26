"""Bounded data-only loading relative to supplied installation pins.

No caller-built anchor proves installed authority or currentness. The real
factory must acquire/reread its independent anchor, and the owning domain
adapter must decode the retained opaque domain bytes before any launch.
See docs/bhmea/LOCAL-RUNTIME-PROFILE.md. No measured code is executed here.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
import time
from dataclasses import dataclass, fields, replace
from datetime import datetime
from pathlib import PosixPath
from typing import Any, Literal, NoReturn, cast
from uuid import UUID

from tools.worker import runtime_artifacts as artifacts
from tools.worker.process_evidence import StoredObject, StoredValue
from tools.worker.runtime_artifacts import (
    InstalledRuntimeArtifactInventory,
    RuntimeArtifactBindings,
    RuntimeArtifactLimits,
    RuntimeFileBinding,
    RuntimeMetadataPaths,
    RuntimeRootBinding,
    VerifiedRuntimeArtifacts,
)

INSTALLATION_SCHEMA = "scanipy-local-runtime-installation/1"
PROFILE_SCHEMA = "scanipy-local-runtime-profile/1"
_REASONS = frozenset(
    (
        "installation-unavailable",
        "metadata-invalid",
        "artifact-mismatch",
        "unsafe-path",
        "limit",
        "deadline",
        "cleanup-incomplete",
        "unsupported",
    )
)
_PURPOSES = ("accepted-verifier", "python-syntax")
_MAX_INT = 2**63 - 1
_MAX_PATH = 4096
_MAX_VALUES = 20000
_MAX_DEPTH = 16
_CHUNK = 65536
_CAPS = (65536, 131072, 65536, 8388608)
_MAX_METADATA = sum(_CAPS)
_MAX_OBSERVATIONS = 512
_MAX_FDS = 64
_WALL_MS = 35000
_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_FILE = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


class RuntimeProfileError(ValueError):
    """Fixed public reason; original filesystem/measurement details are private."""

    def __init__(self, reason: str) -> None:
        if type(reason) is not str or reason not in _REASONS:
            reason = "metadata-invalid"
        self.reason = reason
        super().__init__(reason)


def _require(condition: bool, reason: str = "metadata-invalid") -> None:
    if not condition:
        raise RuntimeProfileError(reason)


def _integer(value: object, minimum: int = 0, maximum: int = _MAX_INT) -> int:
    _require(type(value) is int and minimum <= value <= maximum)
    return cast(int, value)


def _text(value: object, maximum: int = 4096) -> str:
    _require(type(value) is str)
    value = cast(str, value)
    _require(len(value) <= maximum, "limit")
    _require("\x00" not in value)
    try:
        _require(len(value.encode("utf-8", "strict")) <= maximum, "limit")
    except UnicodeError as error:
        raise RuntimeProfileError("metadata-invalid") from error
    return value


def _id(value: object) -> str:
    value = _text(value, 128)
    _require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", value) is not None)
    return value


def _digest(value: object) -> bytes:
    _require(type(value) is bytes and len(value) == 32)
    return cast(bytes, value)


def _hex(value: object) -> bytes:
    _require(type(value) is str and len(value) == 64)
    value = cast(str, value)
    _require(all(c in "0123456789abcdef" for c in value))
    return bytes.fromhex(value)


def _uuid(value: object) -> UUID:
    _require(type(value) is UUID)
    try:
        number = object.__getattribute__(value, "int")
    except AttributeError as error:
        raise RuntimeProfileError("metadata-invalid") from error
    _require(type(number) is int and 0 <= number < 2**128)
    return UUID(int=number)


def _uuid_text(value: object) -> UUID:
    value = _text(value, 36)
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise RuntimeProfileError("metadata-invalid") from error
    _require(str(parsed) == value)
    return parsed


def _path_text(value: object) -> PosixPath:
    value = _text(value, _MAX_PATH)
    _require(value.startswith("/") and "\\" not in value, "unsafe-path")
    _require(not any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value), "unsafe-path")
    _require(all(p not in ("", ".", "..") for p in value[1:].split("/")), "unsafe-path")
    return PosixPath(value)


def _path(value: object) -> PosixPath:
    _require(type(value) is PosixPath, "unsafe-path")
    try:
        raw = object.__getattribute__(value, "_parts")
        root = object.__getattribute__(value, "_root")
        drive = object.__getattribute__(value, "_drv")
    except AttributeError as error:
        raise RuntimeProfileError("unsupported") from error
    _require(type(raw) is list, "unsafe-path")
    # Bound the copy itself, then never consult caller-owned component storage.
    parts = tuple(raw[: _MAX_PATH + 1])
    _require(1 < len(parts) <= _MAX_PATH, "limit")
    _require(type(root) is str and root == "/" and type(drive) is str and drive == "")
    _require(all(type(p) is str for p in parts) and parts[0] == "/", "unsafe-path")
    _require(sum(len(p) for p in parts) + len(parts) <= _MAX_PATH + 2, "limit")
    return _path_text("/" + "/".join(parts[1:]))


@dataclass(frozen=True, slots=True)
class RuntimeInstallationAnchor:
    deployment_id: UUID
    installation_id: UUID
    generation: int
    purpose: str
    installation_path: PosixPath
    installation_sha256: bytes
    metadata_owner_uid: int
    metadata_owner_gid: int
    controller_uid: int
    controller_gid: int

    def __post_init__(self) -> None:
        for name, value in _anchor_members(self).items():
            object.__setattr__(self, name, value)


def _anchor_members(value: object) -> dict[str, Any]:
    _require(type(value) is RuntimeInstallationAnchor)
    try:
        members = {
            f.name: object.__getattribute__(value, f.name)
            for f in fields(RuntimeInstallationAnchor)
        }
    except AttributeError as error:
        raise RuntimeProfileError("metadata-invalid") from error
    members["deployment_id"] = _uuid(members["deployment_id"])
    members["installation_id"] = _uuid(members["installation_id"])
    members["generation"] = _integer(members["generation"], 1)
    members["purpose"] = _id(members["purpose"])
    _require(members["purpose"] in _PURPOSES, "unsupported")
    members["installation_path"] = _path(members["installation_path"])
    members["installation_sha256"] = _digest(members["installation_sha256"])
    for name in ("metadata_owner_uid", "metadata_owner_gid", "controller_uid", "controller_gid"):
        members[name] = _integer(
            members[name], 1 if name.startswith("controller") else 0, 2**31 - 1
        )
    return members


@dataclass(frozen=True, slots=True)
class RuntimeMetadataObservation:
    role: str
    path: PosixPath
    sha256: bytes
    size: int
    device: int
    inode: int
    uid: int
    gid: int
    mode: int
    nlink: int
    mtime_ns: int
    ctime_ns: int


@dataclass(frozen=True, slots=True)
class LoadedRuntimeInstallation:
    anchor: RuntimeInstallationAnchor
    installation_bytes: bytes
    controller_profile_bytes: bytes
    domain_profile_bytes: bytes
    metadata_observations: tuple[RuntimeMetadataObservation, ...]
    installed_inventory: InstalledRuntimeArtifactInventory
    bindings: RuntimeArtifactBindings
    measurement: VerifiedRuntimeArtifacts
    loaded_elapsed_ms: int


@dataclass(frozen=True, slots=True, repr=False)
class RuntimeMetadataDocuments:
    """Inert supplied-data view, never an installed or measured runtime."""

    installation_bytes: bytes
    controller_profile_bytes: bytes
    installation: StoredObject
    controller_profile: StoredObject
    bindings: RuntimeArtifactBindings
    input_bytes: int
    validation: Literal["input-structure-only"]


@dataclass
class _Budget:
    started: int
    observations: int = 0
    payload: int = 0

    def check(self) -> None:
        _require(time.monotonic_ns() - self.started < _WALL_MS * 1000000, "deadline")

    def observe(self) -> None:
        self.check()
        self.observations += 1
        _require(self.observations <= _MAX_OBSERVATIONS, "limit")

    def remaining_ms(self) -> int:
        self.check()
        remaining = (_WALL_MS * 1000000 - (time.monotonic_ns() - self.started)) // 1000000
        _require(remaining > 0, "deadline")
        return min(30000, remaining)


def _checkpoint(budget: _Budget | None) -> None:
    # Only internal loader state, never a caller callback or public timing flag.
    if budget is not None:
        _require(type(budget) is _Budget)
        _Budget.check(budget)


def _preflight(raw: bytes, budget: _Budget | None) -> None:
    depth = count = 0
    quoted = escaped = token = False
    number_start: int | None = None

    def finish_number(end: int) -> None:
        if number_start is not None:
            number = raw[number_start:end]
            _require(len(number) <= 20)
            _require(re.fullmatch(rb"-?(0|[1-9][0-9]*)", number) is not None)
            _parse_int(number.decode("ascii"))

    for index, byte in enumerate(raw):
        if index % _CHUNK == 0:
            _checkpoint(budget)
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
            continue
        if number_start is not None:
            if byte in (9, 10, 13, 32, 44, 58, 91, 93, 123, 125, 34):
                finish_number(index)
                number_start = None
            else:
                _require(index - number_start < 20)
        if byte == 34:
            quoted = True
            count += 1
            token = False
        elif byte in (91, 123):
            depth += 1
            count += 1
            token = False
        elif byte in (93, 125):
            depth -= 1
            token = False
        elif byte in (9, 10, 13, 32, 44, 58):
            token = False
        elif not token:
            count += 1
            token = True
            if byte == 45 or 48 <= byte <= 57:
                number_start = index
        _require(0 <= depth <= _MAX_DEPTH and count <= _MAX_VALUES, "limit")
    finish_number(len(raw))
    _require(depth == 0 and not quoted)


def _primitive_budget(value: object, maximum: int, budget: _Budget | None) -> None:
    pending = [(value, 0)]
    count = encoded = 0
    while pending:
        _checkpoint(budget)
        current, depth = pending.pop()
        count += 1
        _require(count <= _MAX_VALUES and depth <= _MAX_DEPTH, "limit")
        kind = type(current)
        if kind is dict:
            doc = cast(dict[str, object], current)
            _require(count + len(pending) + len(doc) * 2 <= _MAX_VALUES, "limit")
            encoded += 2 + max(0, len(doc) - 1) + len(doc)
            for key, item in doc.items():
                _require(type(key) is str)
                pending.append((key, depth + 1))
                pending.append((item, depth + 1))
        elif kind is list:
            items = cast(list[object], current)
            _require(count + len(pending) + len(items) <= _MAX_VALUES, "limit")
            encoded += 2 + max(0, len(items) - 1)
            pending.extend((item, depth + 1) for item in items)
        elif kind is str:
            text = _text(current)
            # Exact cost of ensure_ascii=False JSON string encoding, before dumps.
            encoded += 2
            for character in text:
                encoded += (
                    2
                    if character in '\\"\b\f\n\r\t'
                    else 6
                    if ord(character) < 32
                    else len(character.encode("utf-8"))
                )
                _require(encoded <= maximum, "limit")
        elif kind is int:
            encoded += len(str(_integer(current, -(2**63))))
        elif kind is bool:
            encoded += 4 if current else 5
        elif current is None:
            encoded += 4
        else:
            raise RuntimeProfileError("metadata-invalid")
        _require(encoded <= maximum, "limit")


def _pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in rows:
        _require(key not in result)
        result[key] = value
    return result


def _parse_int(value: str) -> int:
    _require(len(value) <= 20)
    return _integer(int(value), -(2**63))


def _no_number(_value: str) -> NoReturn:
    raise RuntimeProfileError("metadata-invalid")


def _decode(raw: bytes, maximum: int, budget: _Budget | None) -> dict[str, Any]:
    _require(type(raw) is bytes and 0 < len(raw) <= maximum, "limit")
    _preflight(raw, budget)
    doc = json.loads(
        raw.decode("utf-8", "strict"),
        object_pairs_hook=_pairs,
        parse_int=_parse_int,
        parse_float=_no_number,
        parse_constant=_no_number,
    )
    _primitive_budget(doc, maximum, budget)
    _require(type(doc) is dict)
    _require(
        json.dumps(
            doc, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        == raw
    )
    _checkpoint(budget)
    return cast(dict[str, Any], doc)


def _keys(value: object, names: tuple[str, ...]) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == set(names))
    return cast(dict[str, Any], value)


def _fixed(value: object, expected: dict[str, object]) -> dict[str, Any]:
    doc = _keys(value, tuple(expected))
    for key, item in expected.items():
        _require(type(doc[key]) is type(item) and doc[key] == item)
    return doc


def _version(value: object) -> str:
    value = _text(value, 128)
    _require(re.fullmatch(r"3\.11\.(0|[1-9][0-9]{0,9})", value) is not None, "unsupported")
    _require(int(value[5:]) <= 2**31 - 1, "unsupported")
    return value


def _utc(value: object) -> None:
    value = _text(value, 27)
    _require(
        re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z", value)
        is not None
    )
    # fromisoformat has no locale/strptime format import or caller callbacks.
    datetime.fromisoformat(value[:-1] + "+00:00")


def _file(value: object) -> RuntimeFileBinding:
    doc = _keys(value, ("path", "sha256"))
    return RuntimeFileBinding(_path_text(doc["path"]), _hex(doc["sha256"]))


def _installation_document(doc: dict[str, Any]) -> None:
    _keys(
        doc,
        (
            "schema",
            "deployment_id",
            "installation_id",
            "generation",
            "purpose",
            "controller_uid",
            "controller_gid",
            "controller_profile",
            "domain_profile",
            "inventory",
            "docker_cli",
            "docker_endpoint",
            "daemon",
            "host_work_root",
            "evidence_root",
            "installed_at",
        ),
    )
    _require(doc["schema"] == INSTALLATION_SCHEMA)
    _uuid_text(doc["deployment_id"])
    _uuid_text(doc["installation_id"])
    _integer(doc["generation"], 1)
    _require(_id(doc["purpose"]) in _PURPOSES, "unsupported")
    for name in ("controller_uid", "controller_gid"):
        _integer(doc[name], 1, 2**31 - 1)
    for name in ("controller_profile", "domain_profile", "inventory"):
        _file(doc[name])
    cli = _keys(doc["docker_cli"], ("path", "sha256", "version"))
    _path_text(cli["path"])
    _hex(cli["sha256"])
    _id(cli["version"])
    endpoint = _keys(doc["docker_endpoint"], ("path", "owner_uid", "owner_gid", "mode"))
    _require(endpoint["path"] == "/run/docker.sock")
    _require(_integer(endpoint["owner_uid"]) == 0 and _integer(endpoint["mode"]) == 432)
    _integer(endpoint["owner_gid"], 0, 2**31 - 1)
    daemon = _keys(doc["daemon"], ("id", "version", "api_version", "minimum_api_version"))
    _id(daemon["id"])
    _id(daemon["version"])
    _require(daemon["api_version"] == "1.52" and daemon["minimum_api_version"] == "1.44")
    _path_text(doc["host_work_root"])
    _path_text(doc["evidence_root"])
    _utc(doc["installed_at"])


def _installation(doc: dict[str, Any], anchor: RuntimeInstallationAnchor) -> None:
    _installation_document(doc)
    _require(
        _uuid_text(doc["deployment_id"]) == anchor.deployment_id
        and _uuid_text(doc["installation_id"]) == anchor.installation_id
        and doc["generation"] == anchor.generation
        and doc["purpose"] == anchor.purpose
        and doc["controller_uid"] == anchor.controller_uid
        and doc["controller_gid"] == anchor.controller_gid
    )


def _runtime(value: object, purpose: str, version: str) -> RuntimeArtifactBindings:
    doc = _keys(
        value,
        (
            "purpose",
            "implementation",
            "python_version",
            "protocol_version",
            "resource_profile",
            "executable",
            "worker",
            "roots",
            "application_digest",
            "dependency_digest",
            "program_digest",
        ),
    )
    _require(
        doc["purpose"] == purpose
        and doc["implementation"] == "cpython"
        and doc["python_version"] == version
    )
    protocol = (
        "scanipy-accepted-verifier-request/1"
        if purpose == "accepted-verifier"
        else "scanipy-python-syntax-request/1"
    )
    resource = (
        "scanipy-verifier-limits/1"
        if purpose == "accepted-verifier"
        else "scanipy-python-syntax-limits/1"
    )
    _require(doc["protocol_version"] == protocol and doc["resource_profile"] == resource)
    roots = doc["roots"]
    _require(type(roots) is list and 3 <= len(roots) <= 9, "limit")
    copied: list[RuntimeRootBinding] = []
    roles = ("stdlib", "application", "dependency")
    counts = dict.fromkeys(roles, 0)
    previous = -1
    paths: set[PosixPath] = set()
    for row in roots:
        _keys(row, ("role", "ordinal", "path"))
        role = _id(row["role"])
        _require(role in roles)
        index = roles.index(role)
        ordinal = _integer(row["ordinal"])
        _require(index >= previous and ordinal == counts[role])
        counts[role] += 1
        _require(counts[role] <= (1 if role == "application" else 4), "limit")
        path = _path_text(row["path"])
        _require(path not in paths)
        paths.add(path)
        copied.append(RuntimeRootBinding(role, ordinal, path))
        previous = index
    _require(all(counts.values()))
    return RuntimeArtifactBindings(
        purpose,
        "cpython",
        version,
        protocol,
        resource,
        _file(doc["executable"]),
        _file(doc["worker"]),
        tuple(copied),
        _hex(doc["application_digest"]),
        _hex(doc["dependency_digest"]),
        _hex(doc["program_digest"]),
    )


def _profile_document(doc: dict[str, Any], installation: dict[str, Any]) -> RuntimeArtifactBindings:
    _keys(
        doc,
        (
            "schema",
            "purpose",
            "domain_profile_sha256",
            "inventory_sha256",
            "program_digest",
            "runtime",
            "platform",
            "image",
            "bootstrap",
            "container",
            "scratch",
            "limits",
            "io",
            "config_policy",
        ),
    )
    _require(doc["schema"] == PROFILE_SCHEMA and doc["purpose"] == installation["purpose"])
    _require(_hex(doc["domain_profile_sha256"]) == _file(installation["domain_profile"]).sha256)
    _require(_hex(doc["inventory_sha256"]) == _file(installation["inventory"]).sha256)
    platform = _keys(
        doc["platform"],
        (
            "os",
            "architecture",
            "implementation",
            "python_version",
            "cgroup_version",
            "cgroup_driver",
        ),
    )
    version = _version(platform["python_version"])
    _fixed(
        platform,
        {
            "os": "linux",
            "architecture": "amd64",
            "implementation": "cpython",
            "python_version": version,
            "cgroup_version": 2,
            "cgroup_driver": "systemd",
        },
    )
    image = _keys(
        doc["image"], ("config_id", "oci_manifest_digest", "os", "architecture", "variant")
    )
    for name in ("config_id", "oci_manifest_digest"):
        if name == "oci_manifest_digest" and image[name] is None:
            continue
        value = _text(image[name], 71)
        _require(value.startswith("sha256:"))
        _hex(value[7:])
    _require(
        image["os"] == "linux" and image["architecture"] == "amd64" and image["variant"] is None
    )
    bootstrap = _keys(doc["bootstrap"], ("path", "sha256", "protocol"))
    _path_text(bootstrap["path"])
    _hex(bootstrap["sha256"])
    _require(bootstrap["protocol"] == "scanipy-runtime-bootstrap/1")
    _fixed(
        doc["container"],
        {
            "uid": installation["controller_uid"],
            "gid": installation["controller_gid"],
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
    )
    _fixed(
        doc["scratch"],
        {
            "work_root": "/run/scanipy-work",
            "bytes": 8388608,
            "inodes": 1024,
            "mode": 448,
            "nosuid": True,
            "nodev": True,
            "noexec": True,
        },
    )
    verifier = installation["purpose"] == "accepted-verifier"
    memory = 134217728 if verifier else 268435456
    _fixed(
        doc["limits"],
        {
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
    )
    _fixed(
        doc["io"],
        {
            "stdin_bytes": 2621440 if verifier else 263244,
            "stdout_bytes": 16384 if verifier else 8388608,
            "stderr_bytes": 16384 if verifier else 65536,
            "combined_bytes": 32768 if verifier else 8454144,
        },
    )
    _require(doc["config_policy"] == "scanipy-docker29-pipe-config/1")
    binding = _runtime(doc["runtime"], installation["purpose"], version)
    _require(_hex(doc["program_digest"]) == binding.program_digest)
    return binding


def _profile(
    doc: dict[str, Any], installation: dict[str, Any], anchor: RuntimeInstallationAnchor
) -> RuntimeArtifactBindings:
    _require(
        doc.get("purpose") == anchor.purpose
        and installation["purpose"] == anchor.purpose
        and installation["controller_uid"] == anchor.controller_uid
        and installation["controller_gid"] == anchor.controller_gid
    )
    return _profile_document(doc, installation)


def _stored(value: Any) -> StoredValue:  # noqa: ANN401 -- private, prebounded JSON
    if type(value) is dict:
        return ("object", tuple((key, _stored(item)) for key, item in sorted(value.items())))
    if type(value) is list:
        return ("array", tuple(_stored(item) for item in value))
    return cast(StoredValue, value)


def decode_runtime_metadata_documents(
    installation: bytes, controller_profile: bytes
) -> RuntimeMetadataDocuments:
    """Validate two supplied documents only; no hashing, clock, I/O or authority."""
    try:
        # Admit BOTH byte buffers before parsing even the first document.
        _require(type(installation) is bytes and type(controller_profile) is bytes)
        _require(0 < len(installation) <= _CAPS[0], "limit")
        _require(0 < len(controller_profile) <= _CAPS[1], "limit")
        document = _decode(installation, _CAPS[0], None)
        _installation_document(document)
        profile = _decode(controller_profile, _CAPS[1], None)
        bindings = _profile_document(profile, document)
        return RuntimeMetadataDocuments(
            installation,
            controller_profile,
            cast(StoredObject, _stored(document)),
            cast(StoredObject, _stored(profile)),
            bindings,
            len(installation) + len(controller_profile),
            "input-structure-only",
        )
    except RuntimeProfileError:
        raise
    except (ValueError, TypeError, RecursionError) as error:
        raise RuntimeProfileError("metadata-invalid") from error


def _overlap(first: PosixPath, second: PosixPath) -> bool:
    return first.is_relative_to(second) or second.is_relative_to(first)


def _separation(
    installation: dict[str, Any],
    anchor: RuntimeInstallationAnchor,
    bindings: RuntimeArtifactBindings | None = None,
) -> None:
    metadata = [anchor.installation_path] + [
        _file(installation[name]).path
        for name in ("controller_profile", "domain_profile", "inventory")
    ]
    writable = [_path_text(installation[name]) for name in ("host_work_root", "evidence_root")]
    for index, first in enumerate(metadata + writable):
        for second in (metadata + writable)[index + 1 :]:
            _require(not _overlap(first, second), "unsafe-path")
    if bindings is not None:
        runtime = [r.path for r in bindings.roots] + [
            bindings.executable.path,
            bindings.worker.path,
        ]
        for path in metadata + writable:
            _require(not any(_overlap(path, item) for item in runtime), "unsafe-path")


def _stamp(info: os.stat_result) -> tuple[int, ...]:
    result = (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_size,
        info.st_uid,
        info.st_gid,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )
    for index, value in enumerate(result):
        _integer(value, -(2**63) if index in (7, 8) else 0)
    return result


@dataclass(frozen=True)
class _Held:
    path: PosixPath
    descriptor: int
    stamp: tuple[int, ...]
    parent: int | None
    name: str


class _Files:
    def __init__(self, anchor: RuntimeInstallationAnchor, budget: _Budget) -> None:
        self.anchor = anchor
        self.budget = budget
        self.owned: list[int] = []
        self.held: dict[PosixPath, _Held] = {}
        self.metadata_parents: set[PosixPath] = set()

    def _acquire(self, path: PosixPath, parent: int | None, name: str, *, directory: bool) -> _Held:
        self.budget.observe()
        _require(len(self.owned) < _MAX_FDS, "limit")
        descriptor = os.open(name, _DIRECTORY if directory else _FILE, dir_fd=parent)
        self.owned.append(descriptor)  # Own the child before any further fallible work.
        info = os.fstat(descriptor)
        if directory:
            _require(stat.S_ISDIR(info.st_mode), "unsafe-path")
            _require(info.st_uid in (0, self.anchor.controller_uid), "unsafe-path")
            temporary = (
                str(path) == "/tmp"  # noqa: S108 - exact ancestor exception, not allocation
                and info.st_uid == 0
                and bool(info.st_mode & stat.S_ISVTX)
            )
            _require(not info.st_mode & 0o022 or temporary, "unsafe-path")
        else:
            _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "unsafe-path")
            _require(
                info.st_uid == self.anchor.metadata_owner_uid
                and info.st_gid == self.anchor.metadata_owner_gid
                and stat.S_IMODE(info.st_mode) in (0o400, 0o600),
                "unsafe-path",
            )
            _require(info.st_size >= 0, "metadata-invalid")
        held = _Held(path, descriptor, _stamp(info), parent, name)
        self.held[path] = held
        self.budget.check()
        return held

    def open(self, path: PosixPath) -> _Held:
        root = PosixPath("/")
        current = self.held.get(root)
        if current is None:
            current = self._acquire(root, None, "/", directory=True)
        prefix = root
        for part in path.parts[1:-1]:
            prefix = prefix / part
            child = self.held.get(prefix)
            if child is None:
                child = self._acquire(prefix, current.descriptor, part, directory=True)
            current = child
        parent = os.fstat(current.descriptor)
        self.budget.observe()
        _require(stat.S_IMODE(parent.st_mode) == 0o700, "unsafe-path")
        _require(
            parent.st_uid == self.anchor.metadata_owner_uid
            and parent.st_gid == self.anchor.metadata_owner_gid,
            "unsafe-path",
        )
        self.metadata_parents.add(current.path)
        _require(path not in self.held, "unsafe-path")
        return self._acquire(path, current.descriptor, path.name, directory=False)

    def read(
        self, role: str, path: PosixPath, checksum: bytes, maximum: int
    ) -> tuple[bytes, RuntimeMetadataObservation]:
        held = self.open(path)
        size = held.stamp[4]
        _require(size <= maximum and self.budget.payload + size <= _MAX_METADATA, "limit")
        blocks: list[bytes] = []
        count = 0
        while True:
            self.budget.check()
            block = os.read(held.descriptor, min(_CHUNK, size - count + 1))
            self.budget.payload += len(block)
            count += len(block)
            _require(count <= size, "metadata-invalid")
            _require(self.budget.payload <= _MAX_METADATA, "limit")
            if not block:
                break
            blocks.append(block)
        _require(count == size)
        raw = b"".join(blocks)
        observed = hashlib.sha256(raw).digest()
        _require(observed == checksum, "artifact-mismatch")
        self.recheck_one(held)
        device, inode, mode, nlink, _, uid, gid, mtime, ctime = held.stamp
        return raw, RuntimeMetadataObservation(
            role,
            path,
            observed,
            size,
            device,
            inode,
            uid,
            gid,
            stat.S_IMODE(mode),
            nlink,
            mtime,
            ctime,
        )

    def _unchanged(self, held: _Held, info: os.stat_result) -> bool:
        current = _stamp(info)
        if stat.S_ISDIR(held.stamp[2]) and held.path not in self.metadata_parents:
            # Unmeasured ancestors retain identity/security, not unrelated
            # namespace activity. Metadata files/direct parents keep all fields.
            return all(current[index] == held.stamp[index] for index in (0, 1, 2, 5, 6))
        return current == held.stamp

    def recheck_one(self, held: _Held) -> None:
        self.budget.observe()
        _require(self._unchanged(held, os.fstat(held.descriptor)), "metadata-invalid")
        self.budget.observe()
        _require(
            self._unchanged(held, os.stat(held.name, dir_fd=held.parent, follow_symlinks=False)),
            "metadata-invalid",
        )

    def recheck(self) -> None:
        for held in self.held.values():
            self.recheck_one(held)

    def close(self, primary: BaseException | None) -> None:
        # Capture before closing: cleanup can itself alter exception context.
        prior = primary.__cause__ if primary is not None else None
        if primary is not None and prior is None:
            prior = primary.__context__
        failures: list[BaseException] = []
        failure_priors: list[BaseException | None] = []
        while self.owned:
            descriptor = self.owned.pop()  # Never retry an uncertain numeric FD.
            try:
                os.close(descriptor)
            except BaseException as error:
                failures.append(error)
                explicit = error.__cause__
                failure_priors.append(explicit if explicit is not None else error.__context__)
        if primary is None and failures:
            interruption = next(
                (index for index, error in enumerate(failures) if not isinstance(error, Exception)),
                None,
            )
            if interruption is not None:
                primary = failures.pop(interruption)
                prior = failure_priors[interruption]
            else:
                primary = RuntimeProfileError("cleanup-incomplete")
        if primary is not None:
            if failures:
                # Keep original objects, but do not repeat an immediate group
                # member or attach the primary exception as its own cause.
                causes: list[BaseException] = []
                for cause_item in ([prior] if prior is not None else []) + failures:
                    if cause_item is not primary and all(cause_item is not item for item in causes):
                        causes.append(cause_item)
                if not causes:
                    raise primary
                raise primary from BaseExceptionGroup(
                    "runtime profile cleanup failed",
                    causes,
                )
            raise primary


def _bootstrap(profile: dict[str, Any], measured: VerifiedRuntimeArtifacts) -> None:
    # The actual shared verifier already validated every inventory field/member.
    # This is a bounded membership query, not a second inventory decoder/verifier.
    inventory = json.loads(measured.inventory_bytes)
    application = next(root for root in inventory["roots"] if root["role"] == "application")
    root = PosixPath(application["path"])
    bootstrap = _path_text(profile["bootstrap"]["path"])
    _require(bootstrap != root and bootstrap.is_relative_to(root), "artifact-mismatch")
    relative = bootstrap.relative_to(root).as_posix()
    matches = [row for row in application["files"] if row["path"] == relative]
    _require(len(matches) == 1, "artifact-mismatch")
    _require(
        matches[0]["sha256"] == profile["bootstrap"]["sha256"] and matches[0]["size"] <= 1048576,
        "artifact-mismatch",
    )


def _mapped(error: Exception) -> RuntimeProfileError:
    if isinstance(error, RuntimeProfileError):
        return error
    if isinstance(error, artifacts.RuntimeArtifactError):
        reason = {
            "timeout": "deadline",
            "limit": "limit",
            "unsafe-path": "unsafe-path",
            "storage": "installation-unavailable",
        }.get(error.reason, "artifact-mismatch")
    else:
        reason = "installation-unavailable" if isinstance(error, OSError) else "metadata-invalid"
    failure = RuntimeProfileError(reason)
    failure.__cause__ = error
    return failure


def load_installed_runtime(anchor: RuntimeInstallationAnchor) -> LoadedRuntimeInstallation:
    """Load/measure supplied pins only; never authenticate, decode a domain or launch."""
    files: _Files | None = None
    primary: BaseException | None = None
    result: LoadedRuntimeInstallation | None = None
    try:
        _require(
            sys.implementation.name == "cpython"
            and sys.version_info[:2] == (3, 11)
            and sys.platform == "linux",
            "unsupported",
        )
        frozen = RuntimeInstallationAnchor(**_anchor_members(anchor))
        budget = _Budget(time.monotonic_ns())
        _require(
            os.geteuid() == frozen.controller_uid and os.getegid() == frozen.controller_gid,
            "unsupported",
        )
        files = _Files(frozen, budget)
        installation_raw, installation_observation = files.read(
            "installation", frozen.installation_path, frozen.installation_sha256, _CAPS[0]
        )
        installation = _decode(installation_raw, _CAPS[0], budget)
        _installation(installation, frozen)
        _separation(installation, frozen)
        outer = _file(installation["controller_profile"])
        outer_raw, outer_observation = files.read(
            "controller-profile", outer.path, outer.sha256, _CAPS[1]
        )
        profile = _decode(outer_raw, _CAPS[1], budget)
        expected = _profile(profile, installation, frozen)
        _separation(installation, frozen, expected)
        domain = _file(installation["domain_profile"])
        domain_raw, domain_observation = files.read(
            "domain-profile", domain.path, domain.sha256, _CAPS[2]
        )
        inventory = _file(installation["inventory"])
        inventory_raw, inventory_observation = files.read(
            "inventory", inventory.path, inventory.sha256, _CAPS[3]
        )
        installed = InstalledRuntimeArtifactInventory(
            inventory_raw,
            inventory.sha256,
            RuntimeMetadataPaths(inventory.path, domain.path, frozen.installation_path),
        )
        measurement = artifacts.require_installed_runtime_artifacts(
            installed,
            profile_sha256=domain.sha256,
            expected=expected,
            limits=RuntimeArtifactLimits(wall_ms=budget.remaining_ms()),
        )
        budget.check()
        _bootstrap(profile, measurement)
        files.recheck()
        result = LoadedRuntimeInstallation(
            frozen,
            installation_raw,
            outer_raw,
            domain_raw,
            (
                installation_observation,
                outer_observation,
                domain_observation,
                inventory_observation,
            ),
            installed,
            measurement.expected,
            measurement,
            (time.monotonic_ns() - budget.started) // 1000000,
        )
        budget.check()
    except Exception as error:
        primary = _mapped(error)
    except BaseException as error:
        primary = error
    if files is not None:
        files.close(primary)
    elif primary is not None:
        raise primary
    # Result construction and descriptor disposal both consume the same budget.
    budget.check()
    _require(result is not None)
    result = replace(
        cast(LoadedRuntimeInstallation, result),
        loaded_elapsed_ms=(time.monotonic_ns() - budget.started) // 1000000,
    )
    budget.check()
    return result
