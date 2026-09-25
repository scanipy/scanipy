"""Bounded installed-file measurement; not an execution authorization capability.

The trusted installation loader owns metadata authenticity and actual origins.
This module reads no scanned source as code and performs no process/network work.
See docs/bhmea/RUNTIME-ARTIFACT-INVENTORY.md for the exact shared contract.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, fields
from pathlib import PosixPath
from typing import Any, NoReturn, cast

SCHEMA = "scanipy-runtime-artifact-inventory/1"
_ROLES = ("stdlib", "application", "dependency")
_CHUNK = 65536
_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_FILE = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC


class RuntimeArtifactError(ValueError):
    """Fixed public reason, with private original failure/cleanup causes retained."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class RuntimeMetadataPaths:
    inventory: PosixPath
    profile: PosixPath
    installation: PosixPath


@dataclass(frozen=True, slots=True)
class InstalledRuntimeArtifactInventory:
    inventory_bytes: bytes
    inventory_sha256: bytes
    metadata_paths: RuntimeMetadataPaths


@dataclass(frozen=True, slots=True)
class RuntimeRootBinding:
    role: str
    ordinal: int
    path: PosixPath


@dataclass(frozen=True, slots=True)
class RuntimeFileBinding:
    path: PosixPath
    sha256: bytes


@dataclass(frozen=True, slots=True)
class RuntimeArtifactBindings:
    purpose: str
    implementation: str
    python_version: str
    protocol_version: str
    resource_profile: str
    executable: RuntimeFileBinding
    worker: RuntimeFileBinding
    roots: tuple[RuntimeRootBinding, ...]
    application_digest: bytes
    dependency_digest: bytes
    program_digest: bytes


@dataclass(frozen=True, slots=True)
class RuntimeArtifactLimits:
    max_roots: int = 9
    max_files: int = 10000
    max_entries: int = 20000
    max_depth: int = 64
    max_path_bytes: int = 4096
    max_file_bytes: int = 134217728
    max_total_bytes: int = 536870912
    max_inventory_bytes: int = 8388608
    max_json_depth: int = 12
    max_json_values: int = 250000
    wall_ms: int = 30000


@dataclass(frozen=True, slots=True)
class VerifiedRuntimeArtifacts:
    inventory_bytes: bytes
    inventory_sha256: bytes
    inventory_digest: bytes
    expected: RuntimeArtifactBindings
    stdlib_digest: bytes
    application_digest: bytes
    dependency_digest: bytes
    program_digest: bytes
    elapsed_ms: int


def _require(condition: bool, reason: str = "invalid-input") -> None:
    if not condition:
        raise RuntimeArtifactError(reason)


def _digest(value: object) -> bytes:
    _require(type(value) is bytes and len(value) == 32)
    return cast(bytes, value)


def _text(value: object, maximum: int) -> str:
    _require(type(value) is str)
    value = cast(str, value)
    _require(0 < len(value) <= maximum, "limit")
    _require(not any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value))
    _require(len(value.encode("utf-8", "strict")) <= maximum, "limit")
    return value


def _path_text(value: object, maximum: int, *, absolute: bool) -> str:
    value = _text(value, maximum)
    _require("\\" not in value and value.startswith("/") == absolute)
    parts = value[1:].split("/") if absolute else value.split("/")
    _require(all(part not in ("", ".", "..") for part in parts))
    return value


def _path(value: object, maximum: int) -> PosixPath:
    _require(type(value) is PosixPath)
    # Exact PosixPath is insufficient if its private component list was poisoned
    # with object.__setattr__. Validate primitives before invoking path methods.
    parts = object.__getattribute__(value, "_parts")
    root = object.__getattribute__(value, "_root")
    drive = object.__getattribute__(value, "_drv")
    _require(type(parts) is list)
    # A length check followed by tuple(parts) still permits concurrent growth.
    # Bound the slice itself and never consult the caller's list again.
    parts = tuple(parts[: maximum + 1])
    _require(1 < len(parts) <= maximum)
    _require(type(root) is str and root == "/" and type(drive) is str and drive == "")
    _require(all(type(part) is str for part in parts) and parts[0] == "/")
    _require(sum(len(part) for part in parts) + len(parts) <= maximum + 2, "limit")
    return PosixPath(_path_text("/" + "/".join(parts[1:]), maximum, absolute=True))


def _limits(value: RuntimeArtifactLimits | None) -> RuntimeArtifactLimits:
    if value is None:
        return RuntimeArtifactLimits()
    _require(type(value) is RuntimeArtifactLimits)
    ceiling = RuntimeArtifactLimits()
    members: dict[str, int] = {}
    for item in fields(RuntimeArtifactLimits):
        current = object.__getattribute__(value, item.name)
        _require(type(current) is int and 1 <= current <= getattr(ceiling, item.name), "limit")
        members[item.name] = current
    return RuntimeArtifactLimits(**members)


def _file_binding(value: RuntimeFileBinding, maximum: int) -> RuntimeFileBinding:
    _require(type(value) is RuntimeFileBinding)
    return RuntimeFileBinding(_path(value.path, maximum), _digest(value.sha256))


def _bindings(
    value: RuntimeArtifactBindings, limits: RuntimeArtifactLimits
) -> RuntimeArtifactBindings:
    _require(type(value) is RuntimeArtifactBindings)
    names = ("purpose", "implementation", "python_version", "protocol_version", "resource_profile")
    metadata = {name: _text(object.__getattribute__(value, name), 128) for name in names}
    _require(metadata["purpose"] in ("python-syntax", "accepted-verifier"))
    _require(metadata["implementation"] == "cpython")
    roots = value.roots
    _require(type(roots) is tuple and 3 <= len(roots) <= limits.max_roots, "limit")
    copied: list[RuntimeRootBinding] = []
    seen: set[PosixPath] = set()
    counts = dict.fromkeys(_ROLES, 0)
    order = -1
    for row in roots:
        _require(type(row) is RuntimeRootBinding)
        role = _text(row.role, 128)
        ordinal = row.ordinal
        _require(role in _ROLES and type(ordinal) is int)
        index = _ROLES.index(role)
        _require(index >= order and ordinal == counts[role])
        counts[role] += 1
        _require(counts[role] <= (1 if role == "application" else 4))
        path = _path(row.path, limits.max_path_bytes)
        _require(path not in seen)
        seen.add(path)
        copied.append(RuntimeRootBinding(role, ordinal, path))
        order = index
    _require(all(counts.values()))
    return RuntimeArtifactBindings(
        **metadata,
        executable=_file_binding(value.executable, limits.max_path_bytes),
        worker=_file_binding(value.worker, limits.max_path_bytes),
        roots=tuple(copied),
        application_digest=_digest(value.application_digest),
        dependency_digest=_digest(value.dependency_digest),
        program_digest=_digest(value.program_digest),
    )


def _installed(
    value: InstalledRuntimeArtifactInventory,
    expected: RuntimeArtifactBindings,
    limits: RuntimeArtifactLimits,
) -> InstalledRuntimeArtifactInventory:
    _require(type(value) is InstalledRuntimeArtifactInventory)
    raw = value.inventory_bytes
    _require(type(raw) is bytes and 0 < len(raw) <= limits.max_inventory_bytes, "limit")
    checksum = _digest(value.inventory_sha256)
    paths = value.metadata_paths
    _require(type(paths) is RuntimeMetadataPaths)
    copies = tuple(_path(getattr(paths, f.name), limits.max_path_bytes) for f in fields(paths))
    _require(len(set(copies)) == 3)
    for path in copies:
        _require(path not in (expected.executable.path, expected.worker.path))
        _require(not any(path.is_relative_to(root.path) for root in expected.roots))
    return InstalledRuntimeArtifactInventory(raw, checksum, RuntimeMetadataPaths(*copies))


@dataclass
class _Budget:
    limits: RuntimeArtifactLimits
    started: int
    entries: int = 0
    files: int = 0
    payload: int = 0

    def check(self) -> None:
        _require(time.monotonic_ns() - self.started < self.limits.wall_ms * 1000000, "timeout")

    def entry(self) -> None:
        self.check()
        self.entries += 1
        _require(self.entries <= self.limits.max_entries, "limit")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, "metadata")
        result[key] = value
    return result


def _integer(value: str) -> int:
    _require(len(value) <= 20, "metadata")
    parsed = int(value)
    _require(-(2**63) <= parsed < 2**63, "metadata")
    return parsed


def _no_number(_value: str) -> NoReturn:
    raise RuntimeArtifactError("metadata")


def _json(value: object) -> bytes:
    # Internal, schema-validated, bounded primitive trees only.
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _decode(raw: bytes, budget: _Budget) -> dict[str, Any]:
    depth = count = 0
    quoted = escaped = token = False
    for index, byte in enumerate(raw):
        if index % _CHUNK == 0:
            budget.check()
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
            continue
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
        _require(
            0 <= depth <= budget.limits.max_json_depth and count <= budget.limits.max_json_values,
            "limit",
        )
    _require(depth == 0 and not quoted, "metadata")
    result = json.loads(
        raw.decode("utf-8", "strict"),
        object_pairs_hook=_pairs,
        parse_int=_integer,
        parse_float=_no_number,
        parse_constant=_no_number,
    )
    _require(type(result) is dict, "metadata")
    _require(_json(result) == raw, "metadata")
    budget.check()
    return cast(dict[str, Any], result)


def _keys(value: Any, names: tuple[str, ...]) -> dict[str, Any]:  # noqa: ANN401
    _require(type(value) is dict and set(value) == set(names), "metadata")
    return cast(dict[str, Any], value)


def _hex(value: object) -> bytes:
    _require(type(value) is str and len(value) == 64, "metadata")
    value = cast(str, value)
    _require(all(c in "0123456789abcdef" for c in value), "metadata")
    return bytes.fromhex(value)


def _size(value: object, maximum: int) -> int:
    _require(type(value) is int and 0 <= value <= maximum, "limit")
    return cast(int, value)


def _domain(schema: str, raw: bytes) -> bytes:
    return hashlib.sha256(schema.encode("ascii") + b"\n" + raw).digest()


def _inventory(
    raw: bytes, profile: bytes, expected: RuntimeArtifactBindings, budget: _Budget
) -> dict[str, Any]:
    doc = _keys(
        _decode(raw, budget),
        (
            "schema",
            "profile_sha256",
            "purpose",
            "implementation",
            "python_version",
            "protocol_version",
            "resource_profile",
            "roots",
            "runtime_bindings",
            "application_digest",
            "dependency_digest",
            "program_digest",
        ),
    )
    _require(doc["schema"] == SCHEMA and _hex(doc["profile_sha256"]) == profile, "metadata")
    for key in (
        "purpose",
        "implementation",
        "python_version",
        "protocol_version",
        "resource_profile",
    ):
        _require(type(doc[key]) is str and doc[key] == getattr(expected, key), "metadata")
    for key in ("application_digest", "dependency_digest", "program_digest"):
        _require(_hex(doc[key]) == getattr(expected, key), "metadata")
    roots = doc["roots"]
    _require(type(roots) is list and len(roots) == len(expected.roots), "metadata")
    file_count = entry_count = total = 0
    for root, binding in zip(roots, expected.roots, strict=True):
        _keys(root, ("role", "ordinal", "path", "directories", "files"))
        _require(type(root["ordinal"]) is int and root["ordinal"] == binding.ordinal, "metadata")
        _require(root["role"] == binding.role and root["path"] == str(binding.path), "metadata")
        dirs, files = root["directories"], root["files"]
        _require(type(dirs) is list and type(files) is list, "metadata")
        entry_count += 1 + len(dirs) + len(files)
        file_count += len(files)
        _require(
            entry_count <= budget.limits.max_entries and file_count <= budget.limits.max_files,
            "limit",
        )
        checked_dirs = [_path_text(p, budget.limits.max_path_bytes, absolute=False) for p in dirs]
        _require(checked_dirs == sorted(set(checked_dirs)), "metadata")
        checked_files = []
        for row in files:
            _keys(row, ("path", "size", "sha256"))
            checked_files.append(
                _path_text(row["path"], budget.limits.max_path_bytes, absolute=False)
            )
            total += _size(row["size"], budget.limits.max_file_bytes)
            _hex(row["sha256"])
        _require(checked_files == sorted(set(checked_files)), "metadata")
        _require(not set(checked_dirs).intersection(checked_files), "metadata")
        for path in (*checked_dirs, *checked_files):
            _require(len(path.split("/")) <= budget.limits.max_depth, "limit")
        _require(total <= budget.limits.max_total_bytes, "limit")
        budget.check()
    runtime = doc["runtime_bindings"]
    _require(type(runtime) is list and len(runtime) == 2, "metadata")
    for row, role in zip(runtime, ("executable", "worker"), strict=True):
        _keys(row, ("role", "path", "size", "sha256"))
        binding_file = getattr(expected, role)
        _require(row["role"] == role and row["path"] == str(binding_file.path), "metadata")
        _require(_hex(row["sha256"]) == binding_file.sha256, "metadata")
        total += _size(row["size"], budget.limits.max_file_bytes)
    _require(
        file_count + 2 <= budget.limits.max_files and total <= budget.limits.max_total_bytes,
        "limit",
    )
    return doc


@contextmanager
def _owned() -> Iterator[list[int]]:
    descriptors: list[int] = []
    primary: BaseException | None = None
    try:
        yield descriptors
    except BaseException as error:
        primary = error
    failures: list[BaseException] = []
    while descriptors:
        descriptor = descriptors.pop()  # Never retry a possibly released number.
        try:
            os.close(descriptor)
        except BaseException as error:
            failures.append(error)
    if primary is None and failures:
        primary = next(
            (e for e in failures if isinstance(e, (KeyboardInterrupt, SystemExit))), failures[0]
        )
        failures.remove(primary)
    if primary is not None:
        if failures:
            prior = primary.__cause__
            raise primary from BaseExceptionGroup(
                "runtime measurement cleanup failed",
                ([prior] if prior is not None else []) + failures,
            )
        raise primary


def _stamp(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
        info.st_uid,
        info.st_gid,
    )


def _safe(info: os.stat_result, *, directory: bool, temporary_ancestor: bool = False) -> None:
    _require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode), "unsafe-path")
    _require(info.st_uid in (0, os.geteuid()), "unsafe-path")
    writable_exception = (
        temporary_ancestor and info.st_uid == 0 and bool(info.st_mode & stat.S_ISVTX)
    )
    _require(not (info.st_mode & 0o022) or writable_exception, "unsafe-path")
    if not directory:
        _require(info.st_nlink == 1 and info.st_size >= 0, "unsafe-path")


@contextmanager
def _directory(
    path: PosixPath, budget: _Budget
) -> Iterator[tuple[int, tuple[tuple[int, ...], ...]]]:
    with _owned() as owned:
        budget.entry()
        current = os.open("/", _DIRECTORY)
        owned.append(current)
        info = os.fstat(current)
        _safe(info, directory=True)
        chain = [_stamp(info)]
        prefix = ""
        for component in path.parts[1:]:
            budget.entry()
            prefix += "/" + component
            child = os.open(component, _DIRECTORY, dir_fd=current)
            owned.append(child)
            child_info = os.fstat(child)
            _safe(
                child_info,
                directory=True,
                # Exact no-write ancestor policy, not allocation at a fixed path.
                temporary_ancestor=prefix == "/tmp" and prefix != str(path),  # noqa: S108
            )
            chain.append(_stamp(child_info))
            owned.remove(current)
            os.close(current)
            current = child
        yield current, tuple(chain)


def _read(parent: int, name: str, expected: dict[str, Any], budget: _Budget) -> tuple[int, ...]:
    budget.check()
    budget.files += 1
    _require(budget.files <= budget.limits.max_files, "limit")
    with _owned() as owned:
        descriptor = os.open(name, _FILE, dir_fd=parent)
        owned.append(descriptor)
        before = os.fstat(descriptor)
        _safe(before, directory=False)
        _require(before.st_size == expected["size"], "changed")
        _require(
            before.st_size <= budget.limits.max_file_bytes
            and budget.payload + before.st_size <= budget.limits.max_total_bytes,
            "limit",
        )
        hasher = hashlib.sha256()
        count = 0
        while True:
            budget.check()
            block = os.read(descriptor, min(_CHUNK, before.st_size - count + 1))
            budget.payload += len(block)
            count += len(block)
            _require(
                count <= before.st_size and budget.payload <= budget.limits.max_total_bytes,
                "changed" if count > before.st_size else "limit",
            )
            if not block:
                break
            hasher.update(block)
        _require(count == before.st_size and hasher.hexdigest() == expected["sha256"], "changed")
        _require(_stamp(before) == _stamp(os.fstat(descriptor)), "changed")
        _require(
            _stamp(before) == _stamp(os.stat(name, dir_fd=parent, follow_symlinks=False)), "changed"
        )
        return _stamp(before)


def _walk(
    root: int, row: dict[str, Any], budget: _Budget, *, read: bool
) -> dict[str, tuple[int, ...]]:
    expected_files = {item["path"]: item for item in row["files"]}
    expected_dirs = set(row["directories"])
    observations: dict[str, tuple[int, ...]] = {}

    def visit(parent: int, prefix: str, depth: int) -> None:
        budget.check()
        before = os.fstat(parent)
        _safe(before, directory=True)
        observations[prefix] = _stamp(before)
        with os.scandir(parent) as children:
            for child in children:
                budget.entry()
                _require(depth < budget.limits.max_depth, "limit")
                name = _path_text(child.name, budget.limits.max_path_bytes, absolute=False)
                path = name if not prefix else prefix + "/" + name
                _path_text(path, budget.limits.max_path_bytes, absolute=False)
                observed = child.stat(follow_symlinks=False)
                if stat.S_ISDIR(observed.st_mode):
                    _require(path in expected_dirs, "metadata")
                    with _owned() as owned:
                        descriptor = os.open(name, _DIRECTORY, dir_fd=parent)
                        owned.append(descriptor)
                        _require(_stamp(observed) == _stamp(os.fstat(descriptor)), "changed")
                        visit(descriptor, path, depth + 1)
                else:
                    _safe(observed, directory=False)
                    _require(path in expected_files, "metadata")
                    stamp = (
                        _read(parent, name, expected_files[path], budget)
                        if read
                        else _stamp(observed)
                    )
                    _require(stamp == _stamp(observed), "changed")
                    observations[path] = stamp
        _require(_stamp(before) == _stamp(os.fstat(parent)), "changed")

    visit(root, "", 0)
    _require(set(observations) == {"", *expected_dirs, *expected_files}, "metadata")
    return observations


def _measure(doc: dict[str, Any], expected: RuntimeArtifactBindings, budget: _Budget) -> None:
    observed_roots: list[tuple[tuple[tuple[int, ...], ...], dict[str, tuple[int, ...]]]] = []
    for row, binding in zip(doc["roots"], expected.roots, strict=True):
        with _directory(binding.path, budget) as (root, chain):
            observed_roots.append((chain, _walk(root, row, budget, read=True)))
    runtime_observations = []
    for row, role in zip(doc["runtime_bindings"], ("executable", "worker"), strict=True):
        path = getattr(expected, role).path
        with _directory(path.parent, budget) as (parent, chain):
            budget.entry()
            runtime_observations.append((chain, _read(parent, path.name, row, budget)))
    # Complete re-enumeration after ALL payload reads, including empty dirs and
    # files measured before subsequent roots/runtime bindings were traversed.
    for row, binding, previous in zip(doc["roots"], expected.roots, observed_roots, strict=True):
        with _directory(binding.path, budget) as (root, chain):
            current = _walk(root, row, budget, read=False)
            _require((chain, current) == previous, "changed")
    for role, previous_runtime in zip(("executable", "worker"), runtime_observations, strict=True):
        path = getattr(expected, role).path
        with _directory(path.parent, budget) as (parent, chain):
            budget.entry()
            info = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            _safe(info, directory=False)
            _require((chain, _stamp(info)) == previous_runtime, "changed")


def require_installed_runtime_artifacts(
    installed: InstalledRuntimeArtifactInventory,
    *,
    profile_sha256: bytes,
    expected: RuntimeArtifactBindings,
    limits: RuntimeArtifactLimits | None = None,
) -> VerifiedRuntimeArtifacts:
    """Verify actual complete file membership/bytes, or fail without partial success."""
    try:
        ceiling = _limits(limits)
        frozen = _bindings(expected, ceiling)
        record = _installed(installed, frozen, ceiling)
        profile = _digest(profile_sha256)
        budget = _Budget(ceiling, time.monotonic_ns())
        _require(
            hashlib.sha256(record.inventory_bytes).digest() == record.inventory_sha256, "metadata"
        )
        doc = _inventory(record.inventory_bytes, profile, frozen, budget)
        _measure(doc, frozen, budget)
        groups = {
            role: _domain(
                "scanipy-runtime-root-group/1",
                _json({"role": role, "roots": [r for r in doc["roots"] if r["role"] == role]}),
            )
            for role in _ROLES
        }
        _require(
            groups["application"] == frozen.application_digest
            and groups["dependency"] == frozen.dependency_digest,
            "metadata",
        )
        program = {
            key: doc[key]
            for key in (
                "purpose",
                "implementation",
                "python_version",
                "protocol_version",
                "resource_profile",
                "runtime_bindings",
            )
        }
        program.update({role + "_digest": digest.hex() for role, digest in groups.items()})
        program_digest = _domain("scanipy-runtime-program/1", _json(program))
        _require(program_digest == frozen.program_digest, "metadata")
        result = VerifiedRuntimeArtifacts(
            record.inventory_bytes,
            record.inventory_sha256,
            _domain(SCHEMA, record.inventory_bytes),
            frozen,
            groups["stdlib"],
            groups["application"],
            groups["dependency"],
            program_digest,
            (time.monotonic_ns() - budget.started) // 1000000,
        )
        budget.check()
        return result
    except RuntimeArtifactError:
        raise
    except (OSError, ValueError, TypeError, AttributeError, RecursionError) as error:
        raise RuntimeArtifactError(
            "storage" if isinstance(error, OSError) else "invalid-input"
        ) from error
