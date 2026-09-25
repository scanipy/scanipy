"""Bounded source-only filesystem custody; no SCM, tool execution or DB lease.

See docs/bhmea/LOCAL-SOURCE-CAPTURE.md. Inputs require an exclusively controlled
checkout; read-only modes are not protection against a same-UID administrator.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import UUID, uuid4

TREE_ALGORITHM = "sha256-length-prefixed-path-and-content-v1"
INVENTORY_SCHEMA = "scanipy-execution/source-inventory/1"
MANIFEST_SCHEMA = "scanipy-source-custody/manifest/1"
CUSTODY_PROFILE = "scanipy-local-source-custody/1"
_CHUNK = 64 * 1024
_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
_CREATE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC


class SourceCaptureError(ValueError):
    """Unsafe, changed, incomplete or out-of-policy capture; never success-empty."""


@dataclass(frozen=True)
class CaptureLimits:
    """Explicit conservative custody caps, not measured stage limits."""

    max_files: int = 10_000
    max_entries: int = 20_000
    max_depth: int = 64
    max_path_bytes: int = 1024
    max_file_bytes: int = 64 * 1024 * 1024
    max_total_bytes: int = 512 * 1024 * 1024
    max_metadata_bytes: int = 1024 * 1024

    def __post_init__(self) -> None:
        ceilings = (10_000, 20_000, 64, 1024, 64 * 1024**2, 512 * 1024**2, 1024**2)
        for value, maximum in zip(asdict(self).values(), ceilings, strict=True):
            if type(value) is not int or not 1 <= value <= maximum:
                raise SourceCaptureError("capture limit outside version-1 bounds")


@dataclass(frozen=True)
class CaptureBinding:
    """Trusted producer's scope/commit assertions, not authenticated by this type."""

    org_id: UUID
    codebase_id: UUID
    request_id: UUID
    resolved_commit: str

    def __post_init__(self) -> None:
        if any(
            type(value) is not UUID for value in (self.org_id, self.codebase_id, self.request_id)
        ):
            raise SourceCaptureError("capture scope requires UUID values")
        if (
            not isinstance(self.resolved_commit, str)
            or re.fullmatch(r"[0-9a-f]{40}", self.resolved_commit) is None
            or self.resolved_commit == "0" * 40
        ):
            raise SourceCaptureError("capture requires an actual nonzero Git SHA-1 commit")


@dataclass(frozen=True)
class CaptureReceipt:
    """Expected generated evidence; retain this in the trusted durable store."""

    object_id: UUID
    binding: CaptureBinding
    limits: CaptureLimits
    tree_digest: bytes
    inventory_bytes: bytes
    inventory_digest: bytes
    manifest_digest: bytes
    file_count: int
    content_bytes: int


@dataclass(frozen=True)
class _Entry:
    parts: tuple[str, ...]
    directory: bool
    stamp: tuple[int, ...]


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


def _digest(domain: str, payload: bytes) -> bytes:
    return hashlib.sha256(domain.encode("ascii") + b"\n" + payload).digest()


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
    )


def _check_directory(fd: int, *, private: bool = False) -> None:
    info = os.fstat(fd)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
        raise SourceCaptureError("directory is not owned by the custody principal")
    mode = stat.S_IMODE(info.st_mode)
    if mode & 0o022 or (private and mode != 0o700):
        raise SourceCaptureError("unsafe directory permissions")


def _absolute(path: Path) -> Path:
    if not path.is_absolute() or path.anchor != "/" or ".." in path.parts:
        raise SourceCaptureError("custody roots must be absolute normalized paths")
    return path


@contextmanager
def _open_root(path: Path, *, private: bool = False) -> Iterator[int]:
    """Walk every component with no-follow directory descriptors."""
    fd = os.open("/", _DIRECTORY_FLAGS)
    try:
        for name in _absolute(path).parts[1:]:
            child = os.open(name, _DIRECTORY_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        _check_directory(fd, private=private)
        yield fd
    finally:
        os.close(fd)


@contextmanager
def _directory(root: int, parts: tuple[str, ...]) -> Iterator[int]:
    fd = os.dup(root)
    try:
        for name in parts:
            child = os.open(name, _DIRECTORY_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
            _check_directory(fd)
        yield fd
    finally:
        os.close(fd)


def _path_bytes(parts: tuple[str, ...], limits: CaptureLimits) -> bytes:
    for name in parts:
        if (
            name in ("", ".", "..", ".git")
            or "\\" in name
            or "/" in name
            or any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in name)
        ):
            raise SourceCaptureError("unsupported source path component")
    try:
        encoded = "/".join(parts).encode("utf-8", errors="strict")
    except UnicodeError as error:
        raise SourceCaptureError("source paths require Unicode scalar UTF-8") from error
    if len(parts) > limits.max_depth or len(encoded) > limits.max_path_bytes:
        raise SourceCaptureError("source path exceeds configured bounds")
    return encoded


def _walk(root: int, limits: CaptureLimits, *, published: bool = False) -> tuple[_Entry, ...]:
    entries: list[_Entry] = []
    file_count = 0
    total = 0

    def visit(fd: int, parent: tuple[str, ...]) -> None:
        nonlocal file_count, total
        with os.scandir(fd) as children:
            for child in children:
                parts = (*parent, child.name)
                _path_bytes(parts, limits)
                if len(entries) >= limits.max_entries:
                    raise SourceCaptureError("source entry count exceeds limit")
                info = child.stat(follow_symlinks=False)
                is_directory = stat.S_ISDIR(info.st_mode)
                if not is_directory and not stat.S_ISREG(info.st_mode):
                    raise SourceCaptureError("source contains a symlink or special entry")
                if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o022:
                    raise SourceCaptureError("source entry ownership/permissions are unsafe")
                if published and stat.S_IMODE(info.st_mode) != (0o555 if is_directory else 0o444):
                    raise SourceCaptureError("published source entry is not read-only")
                if not is_directory:
                    if info.st_nlink != 1:
                        raise SourceCaptureError("source files must have exactly one link")
                    file_count += 1
                    total += info.st_size
                    if (
                        file_count > limits.max_files
                        or info.st_size > limits.max_file_bytes
                        or total > limits.max_total_bytes
                    ):
                        raise SourceCaptureError("source file count/size exceeds limit")
                entries.append(_Entry(parts, is_directory, _stamp(info)))
                if is_directory:
                    sub = os.open(child.name, _DIRECTORY_FLAGS, dir_fd=fd)
                    try:
                        _check_directory(sub)
                        if _stamp(os.fstat(sub)) != _stamp(info):
                            raise SourceCaptureError("source directory changed during traversal")
                        visit(sub, parts)
                    finally:
                        os.close(sub)

    visit(root, ())
    return tuple(sorted(entries, key=lambda item: "/".join(item.parts)))


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise SourceCaptureError("source store write made no progress")
        view = view[written:]


def _write_file(parent: int, name: str, payload: bytes) -> None:
    fd = os.open(name, _CREATE_FLAGS, 0o600, dir_fd=parent)
    try:
        _write_all(fd, payload)
        os.fchmod(fd, 0o444)
        os.fsync(fd)
    finally:
        os.close(fd)


def _read_file(parent: int, name: str, bound: int) -> bytes:
    fd = os.open(name, _FILE_FLAGS, dir_fd=parent)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o444
            or info.st_size > bound
        ):
            raise SourceCaptureError("invalid published metadata file")
        chunks: list[bytes] = []
        count = 0
        while chunk := os.read(fd, min(_CHUNK, bound - count + 1)):
            count += len(chunk)
            if count > bound:
                raise SourceCaptureError("published metadata exceeds bound")
            chunks.append(chunk)
        if count != info.st_size or _stamp(os.fstat(fd)) != _stamp(info):
            raise SourceCaptureError("published metadata changed while reading")
        return b"".join(chunks)
    finally:
        os.close(fd)


def _tree_evidence(
    source: int,
    limits: CaptureLimits,
    *,
    destination: int | None = None,
) -> tuple[bytes, bytes, int, int]:
    entries = _walk(source, limits, published=destination is None)
    if destination is not None:
        for entry in sorted(entries, key=lambda item: (len(item.parts), item.parts)):
            if entry.directory:
                with _directory(destination, entry.parts[:-1]) as parent:
                    os.mkdir(entry.parts[-1], mode=0o700, dir_fd=parent)
    tree = hashlib.sha256()
    records: list[dict[str, str | int]] = []
    total = 0
    for entry in entries:
        if entry.directory:
            continue
        with _directory(source, entry.parts[:-1]) as parent:
            fd = os.open(entry.parts[-1], _FILE_FLAGS, dir_fd=parent)
        out: int | None = None
        try:
            info = os.fstat(fd)
            if _stamp(info) != entry.stamp or not stat.S_ISREG(info.st_mode):
                raise SourceCaptureError("source file changed before copying")
            if destination is not None:
                with _directory(destination, entry.parts[:-1]) as target:
                    out = os.open(entry.parts[-1], _CREATE_FLAGS, 0o600, dir_fd=target)
            path_bytes = _path_bytes(entry.parts, limits)
            tree.update(len(path_bytes).to_bytes(8, "big"))
            tree.update(path_bytes)
            tree.update(info.st_size.to_bytes(8, "big"))
            file_hash = hashlib.sha256()
            count = 0
            while chunk := os.read(fd, min(_CHUNK, info.st_size - count + 1)):
                count += len(chunk)
                if count > info.st_size:
                    raise SourceCaptureError("source file grew while copying")
                tree.update(chunk)
                file_hash.update(chunk)
                if out is not None:
                    _write_all(out, chunk)
            if count != info.st_size or _stamp(os.fstat(fd)) != entry.stamp:
                raise SourceCaptureError("source file changed while copying")
            if out is not None:
                os.fchmod(out, 0o444)
                os.fsync(out)
            records.append(
                {"path": path_bytes.decode(), "size": count, "sha256": file_hash.hexdigest()}
            )
            total += count
        finally:
            os.close(fd)
            if out is not None:
                os.close(out)
    if _walk(source, limits, published=destination is None) != entries:
        raise SourceCaptureError("source tree changed during capture")
    inventory = _json_bytes({"schema": INVENTORY_SCHEMA, "files": records})
    if len(inventory) > limits.max_metadata_bytes:
        raise SourceCaptureError("source inventory exceeds metadata limit")
    if destination is not None:
        directories = [entry.parts for entry in entries if entry.directory]
        for parts in sorted(directories, key=len, reverse=True):
            with _directory(destination, parts) as target:
                os.fchmod(target, 0o555)
                os.fsync(target)
        os.fchmod(destination, 0o555)
        os.fsync(destination)
    return tree.digest(), inventory, len(records), total


def _manifest(
    object_id: UUID,
    binding: CaptureBinding,
    limits: CaptureLimits,
    tree: bytes,
    inventory: bytes,
    file_count: int,
    content_bytes: int,
) -> bytes:
    payload = _json_bytes(
        {
            "schema": MANIFEST_SCHEMA,
            "custody_profile": CUSTODY_PROFILE,
            "object_id": str(object_id),
            "org_id": str(binding.org_id),
            "codebase_id": str(binding.codebase_id),
            "request_id": str(binding.request_id),
            "resolved_commit": binding.resolved_commit,
            "commit_algorithm": "git-sha1",
            "tree_algorithm": TREE_ALGORITHM,
            "tree_digest": tree.hex(),
            "inventory_digest": _digest(INVENTORY_SCHEMA, inventory).hex(),
            "inventory": json.loads(inventory),
            "file_count": file_count,
            "content_bytes": content_bytes,
            "limits": asdict(limits),
        }
    )
    if len(payload) > limits.max_metadata_bytes:
        raise SourceCaptureError("source manifest exceeds metadata limit")
    return payload


class LocalSourceCaptureStore:
    """Owner-controlled Linux/Docker filesystem store; no deletion capability."""

    def __init__(self, root: Path, *, limits: CaptureLimits | None = None) -> None:
        self.root = _absolute(root)
        self.limits = limits if limits is not None else CaptureLimits()
        if type(self.limits) is not CaptureLimits:
            raise SourceCaptureError("store requires typed version-1 limits")
        with _open_root(self.root, private=True):
            pass

    def capture(self, source: Path, binding: CaptureBinding) -> CaptureReceipt:
        """Copy an exclusive verified source-only tree, retaining failed objects.

        The producer owns SCM/commit verification. A crash/exception returns no
        receipt; a possibly created object is an orphan, never an implicit seal.
        """
        source = _absolute(source)
        if source.is_relative_to(self.root) or self.root.is_relative_to(source):
            raise SourceCaptureError("source and store must be disjoint")
        if type(binding) is not CaptureBinding:
            raise SourceCaptureError("capture requires an explicit typed binding")
        with _open_root(self.root, private=True) as store, _open_root(source) as src:
            if (
                os.fstat(store).st_ino == os.fstat(src).st_ino
                and os.fstat(store).st_dev == os.fstat(src).st_dev
            ):
                raise SourceCaptureError("source and store refer to the same directory")
            _walk(src, self.limits)  # Reject unsafe/oversized input before object allocation.
            object_id = uuid4()
            name = str(object_id)
            os.mkdir(name, mode=0o700, dir_fd=store)  # Exclusive; a collision is an error.
            with _directory(store, (name,)) as obj:
                os.mkdir("source", mode=0o700, dir_fd=obj)
                with _directory(obj, ("source",)) as dst:
                    tree, inventory, count, size = _tree_evidence(src, self.limits, destination=dst)
                    # Bind the retained bytes, not merely the bytes offered to
                    # write(). No manifest/marker is published before readback.
                    if _tree_evidence(dst, self.limits) != (tree, inventory, count, size):
                        raise SourceCaptureError("stored source readback differs from copied input")
                manifest = _manifest(object_id, binding, self.limits, tree, inventory, count, size)
                manifest_digest = _digest(MANIFEST_SCHEMA, manifest)
                _write_file(obj, "manifest.json", manifest)
                if _read_file(obj, "manifest.json", self.limits.max_metadata_bytes) != manifest:
                    raise SourceCaptureError("stored manifest readback differs from input")
                os.fsync(obj)
                marker = manifest_digest.hex().encode("ascii") + b"\n"
                _write_file(obj, "SEALED", marker)
                if _read_file(obj, "SEALED", 65) != marker:
                    raise SourceCaptureError("stored seal readback differs from input")
                os.fchmod(obj, 0o555)
                os.fsync(obj)
            os.fsync(store)
            return CaptureReceipt(
                object_id,
                binding,
                self.limits,
                tree,
                inventory,
                _digest(INVENTORY_SCHEMA, inventory),
                manifest_digest,
                count,
                size,
            )

    def verify(self, receipt: CaptureReceipt) -> Path:
        """Verify against trusted expected evidence and return the guarded path.

        Read-only consumer mounts/active DB leases must protect subsequent tool
        reads. This function does not acquire a lease or authorize a tenant.
        """
        if type(receipt) is not CaptureReceipt or type(receipt.object_id) is not UUID:
            raise SourceCaptureError("verification requires a typed expected receipt")
        if type(receipt.binding) is not CaptureBinding or type(receipt.limits) is not CaptureLimits:
            raise SourceCaptureError("receipt has invalid binding or limits")
        if any(
            type(value) is not bytes or len(value) != 32
            for value in (
                receipt.tree_digest,
                receipt.inventory_digest,
                receipt.manifest_digest,
            )
        ):
            raise SourceCaptureError("receipt has invalid digest bytes")
        if (
            type(receipt.inventory_bytes) is not bytes
            or len(receipt.inventory_bytes) > receipt.limits.max_metadata_bytes
        ):
            raise SourceCaptureError("receipt inventory exceeds bound")
        expected = _manifest(
            receipt.object_id,
            receipt.binding,
            receipt.limits,
            receipt.tree_digest,
            receipt.inventory_bytes,
            receipt.file_count,
            receipt.content_bytes,
        )
        if (
            _digest(INVENTORY_SCHEMA, receipt.inventory_bytes) != receipt.inventory_digest
            or _digest(MANIFEST_SCHEMA, expected) != receipt.manifest_digest
        ):
            raise SourceCaptureError("receipt evidence digests disagree")
        with _open_root(self.root, private=True) as store:
            with _directory(store, (str(receipt.object_id),)) as obj:
                if stat.S_IMODE(os.fstat(obj).st_mode) != 0o555:
                    raise SourceCaptureError("object is not published read-only")
                # Descriptor-scoped and bounded: never re-resolve an untrusted path.
                with os.scandir(obj) as children:
                    names = set()
                    for child in children:
                        names.add(child.name)
                        if len(names) > 3:
                            raise SourceCaptureError("unexpected published object entries")
                if names != {"source", "manifest.json", "SEALED"}:
                    raise SourceCaptureError("unexpected published object entries")
                if _read_file(obj, "manifest.json", receipt.limits.max_metadata_bytes) != expected:
                    raise SourceCaptureError("manifest differs from expected receipt")
                if _read_file(obj, "SEALED", 65) != receipt.manifest_digest.hex().encode() + b"\n":
                    raise SourceCaptureError("object has no matching seal marker")
                with _directory(obj, ("source",)) as source:
                    if stat.S_IMODE(os.fstat(source).st_mode) != 0o555:
                        raise SourceCaptureError("published source is writable")
                    tree, inventory, count, size = _tree_evidence(source, receipt.limits)
                if (tree, inventory, count, size) != (
                    receipt.tree_digest,
                    receipt.inventory_bytes,
                    receipt.file_count,
                    receipt.content_bytes,
                ):
                    raise SourceCaptureError("retained source differs from expected evidence")
        return self.root / str(receipt.object_id) / "source"
