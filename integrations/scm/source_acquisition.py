"""Actual OFFLINE Git objects -> source custody -> independently verified proof.

No native source command, network acquisition, authenticated origin, DB seal or
execution permission is implemented here. See GIT-RAW-OBJECT-CAPTURE.md.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import re
import stat
import sys
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, NoReturn
from uuid import UUID, uuid4

from services.scan import source_capture as custody

from . import git_objects as git

PROOF_SCHEMA = "scanipy-git-source-consistency/1"
CONTENT_POLICY = "git-committed-blobs/1"
_ENTRYPOINT = "integrations.scm.source_acquisition."
_MODULES = (
    ("integrations.scm.git_objects", "code/git_objects.py"),
    ("integrations.scm.source_acquisition", "code/source_acquisition.py"),
    ("services.scan.source_capture", "code/source_capture.py"),
)
_MAX_VALUES = 100_000
_MAX_DEPTH = 24
_REASONS = frozenset(
    (
        "invalid-input",
        "unsupported-object",
        "limit",
        "changed-input",
        "storage",
        "evidence",
        "unavailable-online",
    )
)


class GitCaptureError(ValueError):
    """Fixed category; private retained failure bytes do not establish success."""

    def __init__(self, reason: str, *, retained_failure: bytes | None = None) -> None:
        self.reason = reason if type(reason) is str and reason in _REASONS else "evidence"
        self.retained_failure = retained_failure
        super().__init__(self.reason)


def _require(condition: bool, reason: str = "invalid-input") -> None:
    if not condition:
        raise GitCaptureError(reason)


def _json_budget(value: object, maximum: int) -> None:
    _require(type(maximum) is int and 1 <= maximum <= 8 * 1024**2, "limit")
    pending = [(value, 0)]
    count = encoded = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        _require(count <= _MAX_VALUES and depth <= _MAX_DEPTH, "limit")
        if item is None:
            encoded += 4
        elif type(item) is bool:
            encoded += 4 if item else 5
        elif type(item) is int:
            _require(-(2**63) <= item < 2**63)
            encoded += len(str(item))
        elif type(item) is str:
            _require(len(item) <= min(2 * 1024**2, maximum - encoded), "limit")
            encoded += 2
            for character in item:
                code = ord(character)
                _require(not 0xD800 <= code <= 0xDFFF)
                if character in ('"', "\\", "\b", "\f", "\n", "\r", "\t"):
                    encoded += 2
                elif code < 32:
                    encoded += 6
                else:
                    encoded += 1 if code < 128 else 2 if code < 2048 else 3 if code < 65536 else 4
                _require(encoded <= maximum, "limit")
        elif type(item) is list:
            _require(len(item) <= _MAX_VALUES - count - len(pending), "limit")
            encoded += 2 + max(0, len(item) - 1)
            pending.extend((child, depth + 1) for child in item)
        elif type(item) is dict:
            _require(len(item) * 2 <= _MAX_VALUES - count - len(pending), "limit")
            encoded += 2 + max(0, len(item) - 1) + len(item)
            for key, child in item.items():
                _require(type(key) is str)
                pending.extend(((key, depth + 1), (child, depth + 1)))
        else:
            raise GitCaptureError("invalid-input")
        _require(encoded <= maximum, "limit")


def canonical_bytes(value: object, *, maximum: int = 8 * 1024**2) -> bytes:
    _json_budget(value, maximum)
    result = json.dumps(
        value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")
    _require(len(result) <= maximum, "limit")
    return result


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        _require(key not in result)
        result[key] = value
    return result


def _integer(text: str) -> int:
    _require(len(text) <= 20)
    value = int(text)
    _require(-(2**63) <= value < 2**63)
    return value


def _no_number(_text: str) -> NoReturn:
    raise GitCaptureError("invalid-input")


def decode_json(data: bytes, *, maximum: int = 8 * 1024**2) -> Any:  # noqa: ANN401
    """Preflight lexical depth/value bounds BEFORE allocating decoded containers."""
    _require(type(data) is bytes and len(data) <= maximum, "limit")
    depth = count = 0
    quoted = escaped = token = False
    for byte in data:
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
        elif byte in (123, 91):
            depth += 1
            count += 1
            token = False
        elif byte in (125, 93):
            depth -= 1
            token = False
        elif byte in (32, 9, 10, 13, 44, 58):
            token = False
        elif not token:
            count += 1
            token = True
        _require(0 <= depth <= _MAX_DEPTH and count <= _MAX_VALUES, "limit")
    _require(not quoted and depth == 0)
    try:
        result = json.loads(
            data.decode("utf-8", "strict"),
            object_pairs_hook=_pairs,
            parse_int=_integer,
            parse_float=_no_number,
            parse_constant=_no_number,
        )
    except (UnicodeError, ValueError, RecursionError) as error:
        raise GitCaptureError("invalid-input") from error
    _require(canonical_bytes(result, maximum=maximum) == data)
    return result


def _keys(value: Any, names: tuple[str, ...]) -> dict[str, Any]:  # noqa: ANN401
    _require(type(value) is dict and set(value) == set(names))
    assert isinstance(value, dict)
    return value


def _uuid(value: Any) -> UUID:  # noqa: ANN401
    _require(type(value) is str and len(value) == 36)
    parsed = UUID(value)
    _require(str(parsed) == value)
    return parsed


def _snapshot_uuid(value: UUID) -> UUID:
    _require(type(value) is UUID)
    try:
        integer = object.__getattribute__(value, "int")
    except AttributeError as error:
        raise GitCaptureError("invalid-input") from error
    _require(type(integer) is int and 0 <= integer < 2**128)
    return UUID(int=integer)


def _hash(value: Any) -> bytes:  # noqa: ANN401
    _require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None)
    return bytes.fromhex(value)


def _count(value: Any, maximum: int) -> int:  # noqa: ANN401
    _require(type(value) is int and 0 <= value <= maximum)
    assert isinstance(value, int)
    return value


def _text(value: Any, maximum: int) -> str:  # noqa: ANN401
    _require(type(value) is str and 0 < len(value) <= maximum and "\0" not in value)
    _require(len(value.encode("utf-8", "strict")) <= maximum)
    assert isinstance(value, str)
    return value


def _record(value: object) -> dict[str, Any]:
    return {item.name: object.__getattribute__(value, item.name) for item in fields(value)}  # type: ignore[arg-type]


def _binding(value: custody.CaptureBinding) -> custody.CaptureBinding:
    _require(type(value) is custody.CaptureBinding)
    members = _record(value)
    for key in ("org_id", "codebase_id", "request_id"):
        members[key] = _snapshot_uuid(members[key])
    git.check_oid(members["resolved_commit"])
    return custody.CaptureBinding(**members)


def _binding_wire(value: custody.CaptureBinding) -> dict[str, str]:
    return {key: str(member) for key, member in _record(_binding(value)).items()}


def _decode_binding(value: Any) -> custody.CaptureBinding:  # noqa: ANN401
    row = _keys(value, ("org_id", "codebase_id", "request_id", "resolved_commit"))
    return custody.CaptureBinding(
        _uuid(row["org_id"]),
        _uuid(row["codebase_id"]),
        _uuid(row["request_id"]),
        git.check_oid(row["resolved_commit"]),
    )


@dataclass(frozen=True, slots=True)
class GitHubRepositoryClaim:
    """Unverified operator label, not a source endpoint or remote authority."""

    owner: str
    repository: str

    def __post_init__(self) -> None:
        _text(self.owner, 39)
        _text(self.repository, 100)
        _require(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", self.owner) is not None)
        _require(re.fullmatch(r"[A-Za-z0-9_.-]+", self.repository) is not None)
        _require(self.repository not in (".", "..") and not self.repository.endswith(".git"))


def _claim(value: GitHubRepositoryClaim | None) -> GitHubRepositoryClaim | None:
    if value is None:
        return None
    _require(type(value) is GitHubRepositoryClaim)
    return GitHubRepositoryClaim(value.owner, value.repository)


def _decode_limits(capture: Any, objects: Any) -> git.GitCaptureLimits:  # noqa: ANN401
    _keys(capture, tuple(item.name for item in fields(custody.CaptureLimits)))
    _keys(objects, tuple(item.name for item in fields(git.GitObjectLimits)))
    return git.freeze_limits(
        git.GitCaptureLimits(custody.CaptureLimits(**capture), git.GitObjectLimits(**objects))
    )


def _receipt(value: custody.CaptureReceipt) -> custody.CaptureReceipt:
    _require(type(value) is custody.CaptureReceipt and type(value.object_id) is UUID)
    object_id = _snapshot_uuid(value.object_id)
    binding = _binding(value.binding)
    limits = git.freeze_limits(git.GitCaptureLimits(value.limits)).capture
    for digest in (value.tree_digest, value.inventory_digest, value.manifest_digest):
        _require(type(digest) is bytes and len(digest) == 32)
    _require(
        type(value.inventory_bytes) is bytes
        and len(value.inventory_bytes) <= limits.max_metadata_bytes
    )
    count = _count(value.file_count, limits.max_files)
    size = _count(value.content_bytes, limits.max_total_bytes)
    inventory = _keys(
        decode_json(value.inventory_bytes, maximum=limits.max_metadata_bytes), ("schema", "files")
    )
    _require(inventory["schema"] == custody.INVENTORY_SCHEMA)
    _require(type(inventory["files"]) is list and len(inventory["files"]) == count)
    paths: list[str] = []
    total = 0
    for item in inventory["files"]:
        row = _keys(item, ("path", "size", "sha256"))
        path = _text(row["path"], limits.max_path_bytes)
        _require(git.source_path(tuple(path.split("/")), limits) == path)
        total += _count(row["size"], limits.max_file_bytes)
        _hash(row["sha256"])
        paths.append(path)
    _require(paths == sorted(set(paths)) and total == size)
    _require(_domain(custody.INVENTORY_SCHEMA, value.inventory_bytes) == value.inventory_digest)
    return custody.CaptureReceipt(
        object_id,
        binding,
        limits,
        value.tree_digest,
        value.inventory_bytes,
        value.inventory_digest,
        value.manifest_digest,
        count,
        size,
    )


def encode_receipt(value: custody.CaptureReceipt) -> bytes:
    """New exact adapter codec for the real custody receipt, not source authority."""
    value = _receipt(value)
    return canonical_bytes(
        {
            "schema": "scanipy-source-capture-receipt/1",
            "object_id": str(value.object_id),
            "binding": _binding_wire(value.binding),
            "limits": _record(value.limits),
            "tree_digest": value.tree_digest.hex(),
            "inventory_bytes_b64": base64.b64encode(value.inventory_bytes).decode("ascii"),
            "inventory_digest": value.inventory_digest.hex(),
            "manifest_digest": value.manifest_digest.hex(),
            "file_count": value.file_count,
            "content_bytes": value.content_bytes,
        },
        maximum=2 * 1024**2,
    )


def decode_receipt(data: bytes) -> custody.CaptureReceipt:
    row = _keys(
        decode_json(data, maximum=2 * 1024**2),
        (
            "schema",
            "object_id",
            "binding",
            "limits",
            "tree_digest",
            "inventory_bytes_b64",
            "inventory_digest",
            "manifest_digest",
            "file_count",
            "content_bytes",
        ),
    )
    _require(row["schema"] == "scanipy-source-capture-receipt/1")
    encoded = _text(row["inventory_bytes_b64"], 1_398_104)
    inventory = base64.b64decode(encoded, validate=True)
    _require(len(inventory) <= 1024**2 and base64.b64encode(inventory).decode("ascii") == encoded)
    _keys(row["limits"], tuple(item.name for item in fields(custody.CaptureLimits)))
    return _receipt(
        custody.CaptureReceipt(
            _uuid(row["object_id"]),
            _decode_binding(row["binding"]),
            custody.CaptureLimits(**row["limits"]),
            _hash(row["tree_digest"]),
            inventory,
            _hash(row["inventory_digest"]),
            _hash(row["manifest_digest"]),
            row["file_count"],
            row["content_bytes"],
        )
    )


def read_expected_receipt(path: Path) -> custody.CaptureReceipt:
    """Read the explicitly trusted operator input, never discover/adopt a receipt."""
    path = git.check_absolute(path)
    # Parent is a trusted explicit operator path, but every component still
    # receives no-follow handling. No pathname from receipt JSON is opened.
    parent_mode = stat.S_IMODE(path.parent.stat().st_mode)
    _require(parent_mode in (0o700, 0o755, 0o555))
    with git.open_directory(path.parent, mode=parent_mode) as parent:
        descriptor = os.open(path.name, git.FILE_FLAGS, dir_fd=parent)
        try:
            before = git.check_regular(descriptor, maximum=2 * 1024**2, private=False)
            raw = bytearray()
            while block := os.read(descriptor, min(git.CHUNK, before.st_size - len(raw) + 1)):
                raw.extend(block)
                _require(len(raw) <= before.st_size, "changed-input")
            _require(
                len(raw) == before.st_size
                and git.file_stamp(os.fstat(descriptor)) == git.file_stamp(before),
                "changed-input",
            )
        finally:
            os.close(descriptor)
    return decode_receipt(bytes(raw))


def _domain(schema: str, data: bytes) -> bytes:
    return hashlib.sha256(schema.encode("ascii") + b"\n" + data).digest()


@dataclass(frozen=True, slots=True)
class GitCaptureResult:
    receipt: custody.CaptureReceipt
    proof_id: UUID
    proof_digest: bytes
    root_tree_oid: str
    operation: str


def result_document(result: GitCaptureResult) -> dict[str, Any]:
    _require(type(result) is GitCaptureResult and type(result.proof_id) is UUID)
    proof_id = _snapshot_uuid(result.proof_id)
    receipt = _receipt(result.receipt)
    _require(type(result.proof_digest) is bytes and len(result.proof_digest) == 32)
    git.check_oid(result.root_tree_oid)
    _require(
        type(result.operation) is str
        and result.operation in ("created-offline", "verified-existing")
    )
    operation = (
        "capture_offline_objects"
        if result.operation == "created-offline"
        else "verify_offline_capture"
    )
    return {
        "schema": "scanipy-git-capture-result/1",
        "operation": result.operation,
        "binding": _binding_wire(receipt.binding),
        "capture_object_id": str(receipt.object_id),
        "proof_id": str(proof_id),
        "proof_digest": result.proof_digest.hex(),
        "source_tree_digest": receipt.tree_digest.hex(),
        "source_inventory_digest": receipt.inventory_digest.hex(),
        "source_manifest_digest": receipt.manifest_digest.hex(),
        "file_count": receipt.file_count,
        "content_bytes": receipt.content_bytes,
        "remote_authentication": "not_established",
        "controller_attestation": "not_established",
        "caller": {"kind": "library_call", "entrypoint": _ENTRYPOINT + operation},
    }


@contextmanager
def _relative_directory(root: int, parts: tuple[str, ...], *, mode: int) -> Iterator[int]:
    with git.owned_descriptors() as owned:
        descriptor = os.dup(root)
        owned.append(descriptor)
        for part in parts:
            _require(type(part) is str and part not in ("", ".", "..") and "/" not in part)
            child = os.open(part, git.DIRECTORY_FLAGS, dir_fd=descriptor)
            owned.append(child)
            owned.remove(descriptor)
            os.close(descriptor)
            descriptor = child
            info = os.fstat(descriptor)
            _require(info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == mode)
        yield descriptor


def _read_file(
    root: int, name: str, maximum: int, *, published: bool, tree_remaining: int | None = None
) -> bytes:
    descriptor = os.open(name, git.FILE_FLAGS, dir_fd=root)
    try:
        info = git.check_regular(descriptor, maximum=maximum, private=not published)
        if published:
            _require(stat.S_IMODE(info.st_mode) == 0o444, "evidence")
        if tree_remaining is not None:
            header, separator, _prefix = os.read(descriptor, 64).partition(b"\0")
            match = re.fullmatch(rb"tree (0|[1-9][0-9]*)", header)
            _require(bool(separator) and match is not None, "evidence")
            assert match is not None
            _require(int(match[1]) <= tree_remaining, "limit")
            os.lseek(descriptor, 0, os.SEEK_SET)
        data = bytearray()
        while block := os.read(descriptor, min(git.CHUNK, info.st_size - len(data) + 1)):
            data.extend(block)
            _require(len(data) <= info.st_size, "changed-input")
        _require(
            len(data) == info.st_size
            and git.file_stamp(os.fstat(descriptor)) == git.file_stamp(info),
            "changed-input",
        )
        return bytes(data)
    finally:
        os.close(descriptor)


def _write_file(root: int, name: str, data: bytes) -> None:
    descriptor = os.open(name, git.CREATE_FLAGS, 0o600, dir_fd=root)
    try:
        os.fchmod(descriptor, 0o600)
        git.write_all(descriptor, data)
        os.fchmod(descriptor, 0o444)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _require(_read_file(root, name, len(data), published=True) == data, "evidence")


def _mkdir(root: int, name: str) -> int:
    os.mkdir(name, mode=0o700, dir_fd=root)
    with git.owned_descriptors() as owned:
        descriptor = os.open(name, git.DIRECTORY_FLAGS, dir_fd=root)
        owned.append(descriptor)
        os.fchmod(descriptor, 0o700)
        owned.remove(descriptor)
        return descriptor


def _disjoint(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    frozen = tuple(git.check_absolute(path) for path in paths)
    for index, path in enumerate(frozen):
        for other in frozen[index + 1 :]:
            _require(not path.is_relative_to(other) and not other.is_relative_to(path))
    return frozen


def _materialize(
    input_directory: int, source: int, tree: git.GitTree, limits: git.GitCaptureLimits
) -> None:
    for directory in sorted(tree.directories, key=lambda item: (item.path.count("/"), item.path)):
        parts = tuple(directory.path.split("/"))
        with _relative_directory(source, parts[:-1], mode=0o700) as parent:
            child = _mkdir(parent, parts[-1])
            os.close(child)
    objects = {item.oid: item for item in tree.objects}
    for item in tree.files:
        parts = tuple(item.path.split("/"))
        with _relative_directory(source, parts[:-1], mode=0o700) as parent:
            target = os.open(parts[-1], git.CREATE_FLAGS, 0o600, dir_fd=parent)
        try:
            os.fchmod(target, 0o600)
            git.copy_verified_blob(input_directory, objects[item.blob_oid], target, limits)
            os.fsync(target)
        finally:
            os.close(target)
    os.fsync(source)


def _source_objects(
    source: int, limits: git.GitCaptureLimits, *, published: bool
) -> tuple[tuple[git.GitObject, ...], tuple[tuple[str, str, int, bytes], ...], tuple[str, ...]]:
    """Independently enumerate/hash stored source, including reconstructed blob OIDs."""
    files: list[tuple[str, str, int, bytes]] = []
    directories: list[str] = []
    objects: dict[str, git.GitObject] = {}
    total = entries = 0
    expected_mode = 0o555 if published else 0o700

    def visit(parent: int, prefix: tuple[str, ...]) -> None:
        nonlocal total, entries
        before = git.file_stamp(os.fstat(parent))
        with os.scandir(parent) as children:
            for entry in children:
                entries += 1
                _require(entries <= limits.capture.max_entries, "limit")
                parts = (*prefix, entry.name)
                path = git.source_path(parts, limits.capture)
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    directories.append(path)
                    with _relative_directory(parent, (entry.name,), mode=expected_mode) as child:
                        _require(
                            git.file_stamp(os.fstat(child)) == git.file_stamp(info), "changed-input"
                        )
                        visit(child, parts)
                    continue
                descriptor = os.open(entry.name, git.FILE_FLAGS, dir_fd=parent)
                try:
                    observed = git.check_regular(
                        descriptor, maximum=limits.capture.max_file_bytes, private=not published
                    )
                    _require(git.file_stamp(observed) == git.file_stamp(info), "changed-input")
                    _require(stat.S_IMODE(observed.st_mode) == (0o444 if published else 0o600))
                    total += observed.st_size
                    _require(
                        total <= limits.capture.max_total_bytes
                        and len(files) < limits.capture.max_files,
                        "limit",
                    )
                    header = git.object_header("blob", observed.st_size)
                    oid = hashlib.sha1(header, usedforsecurity=False)
                    preimage, payload = hashlib.sha256(header), hashlib.sha256()
                    count = 0
                    while block := os.read(
                        descriptor, min(git.CHUNK, observed.st_size - count + 1)
                    ):
                        count += len(block)
                        _require(count <= observed.st_size, "changed-input")
                        oid.update(block)
                        preimage.update(block)
                        payload.update(block)
                    _require(
                        count == observed.st_size
                        and git.file_stamp(os.fstat(descriptor)) == git.file_stamp(observed),
                        "changed-input",
                    )
                    identity = oid.hexdigest()
                    obj = git.GitObject(
                        identity, "blob", count, preimage.digest(), payload.digest(), None
                    )
                    if identity in objects:
                        _require(objects[identity] == obj, "changed-input")
                    objects[identity] = obj
                    files.append((path, identity, count, payload.digest()))
                finally:
                    os.close(descriptor)
        _require(before == git.file_stamp(os.fstat(parent)), "changed-input")

    visit(source, ())
    return (
        tuple(sorted(objects.values(), key=lambda item: item.oid)),
        tuple(sorted(files)),
        tuple(sorted(directories)),
    )


def _match_source(
    source: int, tree: git.GitTree, limits: git.GitCaptureLimits, *, published: bool
) -> None:
    blobs, files, directories = _source_objects(source, limits, published=published)
    _require(
        files
        == tuple((item.path, item.blob_oid, item.size, item.payload_sha256) for item in tree.files),
        "changed-input",
    )
    _require(directories == tuple(item.path for item in tree.directories), "changed-input")
    expected = tuple(
        (item.oid, item.size, item.preimage_sha256, item.payload_sha256)
        for item in tree.objects
        if item.kind == "blob"
    )
    _require(
        tuple((item.oid, item.size, item.preimage_sha256, item.payload_sha256) for item in blobs)
        == expected,
        "changed-input",
    )


def _request(
    binding: custody.CaptureBinding,
    claim: GitHubRepositoryClaim | None,
    limits: git.GitCaptureLimits,
) -> dict[str, Any]:
    return {
        "schema": "scanipy-git-capture-request/1",
        "operation": "offline-objects",
        "binding": _binding_wire(binding),
        "repository_claim": None if claim is None else _record(claim),
        "content_policy": CONTENT_POLICY,
        "capture_limits": _record(limits.capture),
        "object_limits": _record(limits.objects),
    }


def _object_inventory(tree: git.GitTree) -> dict[str, Any]:
    return {
        "schema": "scanipy-git-object-inventory/1",
        "commit_oid": tree.commit_oid,
        "objects": [
            {
                "oid": item.oid,
                "type": item.kind,
                "size": item.size,
                "preimage_sha256": item.preimage_sha256.hex(),
                "payload_sha256": item.payload_sha256.hex(),
            }
            for item in tree.objects
        ],
    }


def _artifact(path: str, data: bytes) -> dict[str, Any]:
    return {"path": path, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _observed_source(path: Path) -> bytes:
    """Observed module FILE bytes only, never trusted mode/execution evidence."""
    path = git.check_absolute(path)
    with git.owned_descriptors() as owned:
        parent = os.open("/", git.DIRECTORY_FLAGS)
        owned.append(parent)
        for part in path.parent.parts[1:]:
            child = os.open(part, git.DIRECTORY_FLAGS, dir_fd=parent)
            owned.append(child)
            owned.remove(parent)
            os.close(parent)
            parent = child
        descriptor = os.open(path.name, git.FILE_FLAGS, dir_fd=parent)
        try:
            info = os.fstat(descriptor)
            _require(
                stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 <= info.st_size <= 1024**2,
                "evidence",
            )
            data = bytearray()
            while block := os.read(descriptor, min(git.CHUNK, info.st_size - len(data) + 1)):
                data.extend(block)
                _require(len(data) <= info.st_size, "changed-input")
            _require(
                len(data) == info.st_size
                and git.file_stamp(os.fstat(descriptor)) == git.file_stamp(info),
                "changed-input",
            )
            return bytes(data)
        finally:
            os.close(descriptor)


def _producer() -> tuple[dict[str, Any], dict[str, bytes]]:
    code: dict[str, bytes] = {}
    rows: list[dict[str, Any]] = []
    for module_name, artifact in _MODULES:
        module = sys.modules[module_name]  # Fixed already imported trusted modules only.
        path = Path(_text(module.__file__, 4096))
        path = git.check_absolute(path)
        data = _observed_source(path)
        code[artifact] = data
        rows.append(
            {
                "module": module_name,
                "observed_path": str(path),
                "artifact": _artifact(artifact, data),
            }
        )
    descriptor = os.open("/proc/self/exe", os.O_RDONLY | os.O_CLOEXEC)
    try:
        before = os.fstat(descriptor)
        _require(stat.S_ISREG(before.st_mode) and before.st_size <= 128 * 1024**2, "evidence")
        hasher = hashlib.sha256()
        count = 0
        while block := os.read(descriptor, min(git.CHUNK, before.st_size - count + 1)):
            count += len(block)
            _require(count <= before.st_size, "evidence")
            hasher.update(block)
        _require(
            count == before.st_size
            and git.file_stamp(os.fstat(descriptor)) == git.file_stamp(before),
            "evidence",
        )
        executable_hash = hasher.hexdigest()
    finally:
        os.close(descriptor)
    result = {
        "schema": "scanipy-git-producer-observation/1",
        "entrypoint": _ENTRYPOINT + "capture_offline_objects",
        "invocation_kind": "library_call",
        "child_argv": None,
        "python": {
            "implementation": _text(platform.python_implementation(), 32),
            "version": _text(sys.version, 4096),
            "executable_path": _text(sys.executable, 4096),
            "executable_sha256": executable_hash,
        },
        "source_files": rows,
        "source_file_binding": "observed-file-bytes-only",
        "code_revision": None,
        "image_manifest_digest": None,
        "controller_receipt_digest": None,
        "execution_artifact_attestation": "not_established",
    }
    return result, code


def _proof(
    tree: git.GitTree,
    receipt: custody.CaptureReceipt,
    proof_id: UUID,
    claim: GitHubRepositoryClaim | None,
    limits: git.GitCaptureLimits,
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    commit = next(item for item in tree.objects if item.oid == tree.commit_oid)
    return {
        "schema": PROOF_SCHEMA,
        "binding": _binding_wire(receipt.binding),
        "capture_object_id": str(receipt.object_id),
        "proof_id": str(proof_id),
        "commit_oid": tree.commit_oid,
        "commit_preimage_sha256": commit.preimage_sha256.hex(),
        "root_tree_oid": tree.root_tree_oid,
        "content_policy": CONTENT_POLICY,
        "repository_claim": None if claim is None else _record(claim),
        "capture_limits": _record(limits.capture),
        "object_limits": _record(limits.objects),
        "custody_profile": custody.CUSTODY_PROFILE,
        "source_tree_algorithm": custody.TREE_ALGORITHM,
        "source_tree_digest": receipt.tree_digest.hex(),
        "source_inventory_digest": receipt.inventory_digest.hex(),
        "source_manifest_digest": receipt.manifest_digest.hex(),
        "file_count": receipt.file_count,
        "content_bytes": receipt.content_bytes,
        "files": [
            {
                "path": item.path,
                "mode": item.mode,
                "blob_oid": item.blob_oid,
                "size": item.size,
                "payload_sha256": item.payload_sha256.hex(),
            }
            for item in tree.files
        ],
        "directories": [
            {"path": item.path, "tree_oid": item.tree_oid} for item in tree.directories
        ],
        "artifacts": artifacts,
        "object_consistency": "verified",
        "source_capture": "verified",
        "remote_authentication": "not_established",
        "commit_signature_verification": "not_checked",
        "native_execution": "not_performed",
        "controller_attestation": "not_established",
    }


def _names(root: int, maximum: int) -> tuple[str, ...]:
    names: list[str] = []
    with os.scandir(root) as entries:
        for entry in entries:
            _require(len(names) < maximum, "limit")
            names.append(entry.name)
    return tuple(sorted(names))


def _publish(
    evidence: int,
    allocated_root: int,
    proof_id: UUID,
    tree: git.GitTree,
    receipt: custody.CaptureReceipt,
    claim: GitHubRepositoryClaim | None,
    limits: git.GitCaptureLimits,
) -> bytes:
    producer, code = _producer()
    artifacts = {
        "request.json": canonical_bytes(
            _request(receipt.binding, claim, limits), maximum=32 * 1024
        ),
        "objects.json": canonical_bytes(
            _object_inventory(tree), maximum=limits.objects.max_proof_json_bytes
        ),
        "capture-receipt.json": encode_receipt(receipt),
        "producer.json": canonical_bytes(producer, maximum=128 * 1024),
        **code,
    }
    for obj in tree.objects:
        if obj.kind != "blob":
            _require(type(obj.payload) is bytes)
            assert obj.payload is not None
            name = "commit.object" if obj.kind == "commit" else f"trees/{obj.oid}.object"
            artifacts[name] = git.object_header(obj.kind, obj.size) + obj.payload
    descriptors = [_artifact(name, artifacts[name]) for name in sorted(artifacts)]
    proof = canonical_bytes(
        _proof(tree, receipt, proof_id, claim, limits, descriptors),
        maximum=limits.objects.max_proof_json_bytes,
    )
    digest = _domain(PROOF_SCHEMA, proof)
    artifacts["proof.json"] = proof
    _require(
        sum(len(data) for data in artifacts.values()) + 65 <= limits.objects.max_proof_bytes,
        "limit",
    )
    root = os.dup(allocated_root)
    try:
        for name in ("code", "trees"):
            descriptor = _mkdir(root, name)
            os.close(descriptor)
        for name, data in sorted(artifacts.items()):
            parts = tuple(name.split("/"))
            with _relative_directory(root, parts[:-1], mode=0o700) as parent:
                _write_file(parent, parts[-1], data)
        for name in ("code", "trees"):
            with _relative_directory(root, (name,), mode=0o700) as child:
                os.fchmod(child, 0o555)
                os.fsync(child)
        os.fsync(root)
        _write_file(root, "COMPLETE", digest.hex().encode("ascii") + b"\n")
        os.fchmod(root, 0o555)
        os.fsync(root)
    finally:
        os.close(root)
    os.fsync(evidence)
    return digest


def _producer_valid(data: bytes, artifacts: dict[str, bytes]) -> None:
    row = _keys(
        decode_json(data, maximum=128 * 1024),
        (
            "schema",
            "entrypoint",
            "invocation_kind",
            "child_argv",
            "python",
            "source_files",
            "source_file_binding",
            "code_revision",
            "image_manifest_digest",
            "controller_receipt_digest",
            "execution_artifact_attestation",
        ),
    )
    fixed = {
        "schema": "scanipy-git-producer-observation/1",
        "entrypoint": _ENTRYPOINT + "capture_offline_objects",
        "invocation_kind": "library_call",
        "child_argv": None,
        "source_file_binding": "observed-file-bytes-only",
        "code_revision": None,
        "image_manifest_digest": None,
        "controller_receipt_digest": None,
        "execution_artifact_attestation": "not_established",
    }
    _require(all(row[key] == value for key, value in fixed.items()), "evidence")
    interpreter = _keys(
        row["python"], ("implementation", "version", "executable_path", "executable_sha256")
    )
    _text(interpreter["implementation"], 32)
    _text(interpreter["version"], 4096)
    path = _text(interpreter["executable_path"], 4096)
    _require(str(git.check_absolute(Path(path))) == path)
    _hash(interpreter["executable_sha256"])
    _require(type(row["source_files"]) is list and len(row["source_files"]) == len(_MODULES))
    for source, (module, artifact) in zip(row["source_files"], _MODULES, strict=True):
        _keys(source, ("module", "observed_path", "artifact"))
        _require(source["module"] == module)
        path = _text(source["observed_path"], 4096)
        _require(str(git.check_absolute(Path(path))) == path)
        _require(
            canonical_bytes(source["artifact"])
            == canonical_bytes(_artifact(artifact, artifacts[artifact])),
            "evidence",
        )


def _read_artifacts(
    root: int, limits: git.GitCaptureLimits, *, already_retained: int
) -> dict[str, bytes]:
    _require(0 <= already_retained <= limits.objects.max_proof_bytes, "limit")
    _require(
        _names(root, 10)
        == tuple(
            sorted(
                (
                    "request.json",
                    "objects.json",
                    "capture-receipt.json",
                    "producer.json",
                    "commit.object",
                    "trees",
                    "code",
                    "proof.json",
                    "COMPLETE",
                )
            )
        ),
        "evidence",
    )
    bounds = {
        "request.json": 32 * 1024,
        "objects.json": limits.objects.max_proof_json_bytes,
        "capture-receipt.json": 2 * 1024**2,
        "producer.json": 128 * 1024,
        "commit.object": limits.objects.max_commit_bytes + 64,
    }
    result: dict[str, bytes] = {}
    total = already_retained

    def retain(
        parent: int, basename: str, path: str, bound: int, *, tree_remaining: int | None = None
    ) -> None:
        nonlocal total
        data = _read_file(
            parent,
            basename,
            min(bound, limits.objects.max_proof_bytes - total),
            published=True,
            tree_remaining=tree_remaining,
        )
        total += len(data)
        _require(total <= limits.objects.max_proof_bytes, "limit")
        result[path] = data

    for name, bound in bounds.items():
        retain(root, name, name, bound)
    with _relative_directory(root, ("code",), mode=0o555) as code:
        _require(
            _names(code, 4) == ("git_objects.py", "source_acquisition.py", "source_capture.py"),
            "evidence",
        )
        for _module, path in _MODULES:
            retain(code, path.split("/")[1], path, 1024**2)
    with _relative_directory(root, ("trees",), mode=0o555) as trees:
        names = _names(trees, limits.objects.max_objects)
        tree_bytes = 0
        for name in names:
            _require(len(name) == 47 and name.endswith(".object"))
            git.check_oid(name[:-7])
            retain(
                trees,
                name,
                "trees/" + name,
                limits.objects.max_tree_bytes + 64,
                tree_remaining=limits.objects.max_total_tree_bytes - tree_bytes,
            )
            obj = git.metadata_object(name[:-7], result["trees/" + name], limits)
            _require(obj.kind == "tree", "evidence")
            tree_bytes += obj.size
    return result


def verify_offline_capture(
    *,
    store_root: Path,
    evidence_root: Path,
    expected_receipt: custody.CaptureReceipt,
    proof_id: UUID,
    expected_proof_digest: bytes,
) -> GitCaptureResult:
    """Read-only replay against trusted expected identities, never self-adoption."""
    try:
        store_root, evidence_root = _disjoint((store_root, evidence_root))
        receipt = _receipt(expected_receipt)
        proof_id = _snapshot_uuid(proof_id)
        _require(
            type(proof_id) is UUID
            and type(expected_proof_digest) is bytes
            and len(expected_proof_digest) == 32
        )
        with git.open_directory(evidence_root) as evidence:
            with _relative_directory(evidence, (str(proof_id),), mode=0o555) as root:
                before = git.file_stamp(os.fstat(root))
                proof_raw = _read_file(root, "proof.json", 8 * 1024**2, published=True)
                _require(_domain(PROOF_SCHEMA, proof_raw) == expected_proof_digest, "evidence")
                _require(
                    _read_file(root, "COMPLETE", 65, published=True)
                    == expected_proof_digest.hex().encode("ascii") + b"\n",
                    "evidence",
                )
                proof = _keys(
                    decode_json(proof_raw),
                    (
                        "schema",
                        "binding",
                        "capture_object_id",
                        "proof_id",
                        "commit_oid",
                        "commit_preimage_sha256",
                        "root_tree_oid",
                        "content_policy",
                        "repository_claim",
                        "capture_limits",
                        "object_limits",
                        "custody_profile",
                        "source_tree_algorithm",
                        "source_tree_digest",
                        "source_inventory_digest",
                        "source_manifest_digest",
                        "file_count",
                        "content_bytes",
                        "files",
                        "directories",
                        "artifacts",
                        "object_consistency",
                        "source_capture",
                        "remote_authentication",
                        "commit_signature_verification",
                        "native_execution",
                        "controller_attestation",
                    ),
                )
                limits = _decode_limits(proof["capture_limits"], proof["object_limits"])
                _require(limits.capture == receipt.limits, "evidence")
                claim_row = proof["repository_claim"]
                claim = (
                    None
                    if claim_row is None
                    else GitHubRepositoryClaim(**_keys(claim_row, ("owner", "repository")))
                )
                artifacts = _read_artifacts(root, limits, already_retained=len(proof_raw) + 65)
                _require(
                    sum(len(value) for value in artifacts.values()) + len(proof_raw) + 65
                    <= limits.objects.max_proof_bytes,
                    "limit",
                )
                _require(
                    artifacts["request.json"]
                    == canonical_bytes(_request(receipt.binding, claim, limits), maximum=32 * 1024),
                    "evidence",
                )
                _require(artifacts["capture-receipt.json"] == encode_receipt(receipt), "evidence")
                _producer_valid(artifacts["producer.json"], artifacts)
                source_path = custody.LocalSourceCaptureStore(
                    store_root, limits=receipt.limits
                ).verify(receipt)
                with git.open_directory(source_path, mode=0o555) as source:
                    blobs, files, directories = _source_objects(source, limits, published=True)
                commit = git.metadata_object(
                    receipt.binding.resolved_commit, artifacts["commit.object"], limits
                )
                metadata = [commit]
                for path, data in artifacts.items():
                    if path.startswith("trees/"):
                        obj = git.metadata_object(path[6:-7], data, limits)
                        _require(obj.kind == "tree", "evidence")
                        metadata.append(obj)
                tree = git.expand_objects(
                    receipt.binding.resolved_commit, (*metadata, *blobs), limits
                )
                _require(
                    files
                    == tuple(
                        (item.path, item.blob_oid, item.size, item.payload_sha256)
                        for item in tree.files
                    ),
                    "evidence",
                )
                _require(directories == tuple(item.path for item in tree.directories), "evidence")
                _require(
                    artifacts["objects.json"]
                    == canonical_bytes(
                        _object_inventory(tree), maximum=limits.objects.max_proof_json_bytes
                    ),
                    "evidence",
                )
                descriptors = [_artifact(name, artifacts[name]) for name in sorted(artifacts)]
                _require(
                    proof_raw
                    == canonical_bytes(
                        _proof(tree, receipt, proof_id, claim, limits, descriptors),
                        maximum=limits.objects.max_proof_json_bytes,
                    ),
                    "evidence",
                )
                _require(before == git.file_stamp(os.fstat(root)), "changed-input")
        result = GitCaptureResult(
            receipt, proof_id, expected_proof_digest, tree.root_tree_oid, "verified-existing"
        )
        canonical_bytes(result_document(result), maximum=32 * 1024)
        return result
    except (OSError, ValueError, TypeError, UnicodeError) as error:
        if isinstance(error, GitCaptureError):
            raise
        reason = str(error) if isinstance(error, git.GitObjectError) else "evidence"
        raise GitCaptureError(reason) from error


def _failure_record(
    binding: custody.CaptureBinding | None,
    attempt_id: UUID | None,
    stage: str,
    reason: str,
    receipt: custody.CaptureReceipt | None,
    capture_state: str,
    proof_id: UUID | None,
) -> bytes:
    return canonical_bytes(
        {
            "schema": "scanipy-git-capture-failure/1",
            "binding": None if binding is None else _binding_wire(binding),
            "attempt_id": None if attempt_id is None else str(attempt_id),
            "stage": stage,
            "reason": reason,
            "capture_object_id": None if receipt is None else str(receipt.object_id),
            "capture_state": capture_state,
            "proof_id": None if proof_id is None else str(proof_id),
            "completion_claim": False,
            "cleanup": "not-attempted-retained-for-review",
        },
        maximum=8 * 1024,
    )


def capture_offline_objects(
    objects_dir: Path,
    *,
    store_root: Path,
    evidence_root: Path,
    binding: custody.CaptureBinding,
    repository_claim: GitHubRepositoryClaim | None = None,
    limits: git.GitCaptureLimits,
) -> GitCaptureResult:
    """Actual bounded offline producer; failed work is retained, never repaired."""
    attempt_id: UUID | None = None
    proof_id: UUID | None = None
    receipt: custody.CaptureReceipt | None = None
    stage = "input"
    capture_state = "not-started"
    frozen_binding: custody.CaptureBinding | None = None
    attempt_identity: tuple[int, int, int, int] | None = None
    with ExitStack() as stack:
        attempt: int | None = None
        try:
            limits = git.freeze_limits(limits)
            frozen_binding = _binding(binding)
            claim = _claim(repository_claim)
            objects_dir, store_root, evidence_root = _disjoint(
                (objects_dir, store_root, evidence_root)
            )
            input_directory = stack.enter_context(git.open_directory(objects_dir))
            store = stack.enter_context(git.open_directory(store_root))
            evidence = stack.enter_context(git.open_directory(evidence_root))
            owned = stack.enter_context(git.owned_descriptors())
            identities = {
                (os.fstat(fd).st_dev, os.fstat(fd).st_ino)
                for fd in (input_directory, store, evidence)
            }
            _require(len(identities) == 3)
            stage = "objects"
            tree = git.load_object_directory(
                input_directory, frozen_binding.resolved_commit, limits
            )
            stage = "staging"
            attempt_id = uuid4()
            attempt = _mkdir(evidence, "attempt-" + str(attempt_id))
            owned.append(attempt)
            allocated = os.fstat(attempt)
            attempt_identity = (
                allocated.st_dev,
                allocated.st_ino,
                allocated.st_uid,
                stat.S_IMODE(allocated.st_mode),
            )
            source = _mkdir(attempt, "source")
            owned.append(source)
            _materialize(input_directory, source, tree, limits)
            _match_source(source, tree, limits, published=False)
            git.recheck_object_directory(input_directory, tree, limits)
            stage = "custody"
            capture_state = "unknown"
            backend = custody.LocalSourceCaptureStore(store_root, limits=limits.capture)
            receipt = _receipt(
                backend.capture(
                    evidence_root / ("attempt-" + str(attempt_id)) / "source", frozen_binding
                )
            )
            capture_state = "receipt-returned-unverified"
            stage = "capture-verification"
            captured = backend.verify(receipt)
            with git.open_directory(captured, mode=0o555) as retained:
                _match_source(retained, tree, limits, published=True)
            capture_state = "verified-orphan"
            git.recheck_object_directory(input_directory, tree, limits)
            stage = "proof-publication"
            proposed_proof_id = uuid4()
            proof_root = _mkdir(evidence, str(proposed_proof_id))
            owned.append(proof_root)
            proof_id = proposed_proof_id  # Identity is reported only after exclusive allocation.
            digest = _publish(evidence, proof_root, proof_id, tree, receipt, claim, limits)
            verified = verify_offline_capture(
                store_root=store_root,
                evidence_root=evidence_root,
                expected_receipt=receipt,
                proof_id=proof_id,
                expected_proof_digest=digest,
            )
            stage = "result"
            result = GitCaptureResult(
                verified.receipt,
                verified.proof_id,
                verified.proof_digest,
                verified.root_tree_oid,
                "created-offline",
            )
            canonical_bytes(result_document(result), maximum=32 * 1024)
            return result
        except BaseException as error:
            reason = (
                error.reason
                if isinstance(error, GitCaptureError)
                else str(error)
                if isinstance(error, git.GitObjectError)
                else "storage"
                if isinstance(error, OSError)
                else "evidence"
            )
            if reason not in _REASONS:
                reason = "evidence"
            retained_failure: bytes | None = None
            if attempt is not None:
                failure = _failure_record(
                    frozen_binding, attempt_id, stage, reason, receipt, capture_state, proof_id
                )
                try:
                    _write_file(attempt, "failure.json", failure)
                    os.fsync(attempt)
                    retained_failure = failure
                except BaseException as evidence_error:
                    if isinstance(error, (KeyboardInterrupt, SystemExit)):
                        raise error from evidence_error
                    raise GitCaptureError("evidence") from BaseExceptionGroup(
                        "offline capture and private evidence retention failed",
                        [error, evidence_error],
                    )
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            raise GitCaptureError(reason, retained_failure=retained_failure) from error
        finally:
            # Explicit finalization remains inside this failure boundary. The
            # outer with sees an emptied stack; no numeric FD is retried.
            pending = sys.exception()
            try:
                stack.__exit__(*sys.exc_info())
            except BaseException as cleanup_error:
                if pending is not None:
                    causes = [pending.__cause__] if pending.__cause__ is not None else []
                    causes.append(cleanup_error)
                    raise pending from BaseExceptionGroup("capture finalization failed", causes)
                retained_failure = None
                failure = _failure_record(
                    frozen_binding, attempt_id, stage, "storage", receipt, capture_state, proof_id
                )
                if attempt_id is not None and attempt is not None:
                    try:
                        # Fresh held descriptors to our exact already-created
                        # attempt only. No scan, discovery, repair or reuse.
                        with git.open_directory(evidence_root) as retained_root:
                            with _relative_directory(
                                retained_root, ("attempt-" + str(attempt_id),), mode=0o700
                            ) as failed_attempt:
                                observed = os.fstat(failed_attempt)
                                _require(
                                    (
                                        observed.st_dev,
                                        observed.st_ino,
                                        observed.st_uid,
                                        stat.S_IMODE(observed.st_mode),
                                    )
                                    == attempt_identity,
                                    "changed-input",
                                )
                                _write_file(failed_attempt, "failure.json", failure)
                                os.fsync(failed_attempt)
                        retained_failure = failure
                    except BaseException as retention_error:
                        if isinstance(cleanup_error, (KeyboardInterrupt, SystemExit)):
                            raise cleanup_error from retention_error
                        raise GitCaptureError("evidence") from BaseExceptionGroup(
                            "capture finalization and evidence retention failed",
                            [cleanup_error, retention_error],
                        )
                if isinstance(cleanup_error, (KeyboardInterrupt, SystemExit)):
                    raise
                raise GitCaptureError(
                    "storage", retained_failure=retained_failure
                ) from cleanup_error


def capture_github_commit() -> NoReturn:
    """No input, profile, callback or environment value can enable online v1."""
    raise GitCaptureError("unavailable-online")
