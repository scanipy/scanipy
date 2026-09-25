"""Bounded, data-only Git preimage verification. No Git process or checkout.

An expected SHA-1 establishes object consistency, not authenticated SCM origin.
The offline input directory must remain exclusively controlled during use.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, fields
from pathlib import Path, PosixPath

from services.scan.source_capture import CaptureLimits

CHUNK = 64 * 1024
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
CREATE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
_OID = re.compile(r"[0-9a-f]{40}")
_HEADER = re.compile(rb"(commit|tree|blob) (0|[1-9][0-9]*)")
_CAPTURE_FIELDS = (
    "max_files",
    "max_entries",
    "max_depth",
    "max_path_bytes",
    "max_file_bytes",
    "max_total_bytes",
    "max_metadata_bytes",
)


class GitObjectError(ValueError):
    """Fixed-category refusal; raw paths/object bytes are not public errors."""


@dataclass(frozen=True, slots=True)
class GitObjectLimits:
    max_objects: int = 20_002
    max_commit_bytes: int = 1024**2
    max_commit_header_bytes: int = 64 * 1024
    max_parent_oids: int = 64
    max_tree_bytes: int = 8 * 1024**2
    max_total_tree_bytes: int = 32 * 1024**2
    max_total_preimage_bytes: int = 547 * 1024**2
    max_proof_json_bytes: int = 8 * 1024**2
    max_proof_bytes: int = 64 * 1024**2

    def __post_init__(self) -> None:
        ceilings = (
            20_002,
            1024**2,
            64 * 1024,
            64,
            8 * 1024**2,
            32 * 1024**2,
            547 * 1024**2,
            8 * 1024**2,
            64 * 1024**2,
        )
        for item, ceiling in zip(fields(GitObjectLimits), ceilings, strict=True):
            value = object.__getattribute__(self, item.name)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise GitObjectError("limit")


@dataclass(frozen=True, slots=True)
class GitCaptureLimits:
    capture: CaptureLimits = field(default_factory=CaptureLimits)
    objects: GitObjectLimits = field(default_factory=GitObjectLimits)


def freeze_limits(value: GitCaptureLimits) -> GitCaptureLimits:
    """Snapshot exact primitive fields; never dispatch caller validation methods."""
    if type(value) is not GitCaptureLimits:
        raise GitObjectError("invalid-input")
    capture = object.__getattribute__(value, "capture")
    objects = object.__getattribute__(value, "objects")
    if type(capture) is not CaptureLimits or type(objects) is not GitObjectLimits:
        raise GitObjectError("invalid-input")
    capture_values = {name: object.__getattribute__(capture, name) for name in _CAPTURE_FIELDS}
    object_values = {
        item.name: object.__getattribute__(objects, item.name) for item in fields(GitObjectLimits)
    }
    if any(type(item) is not int for item in (*capture_values.values(), *object_values.values())):
        raise GitObjectError("invalid-input")
    try:
        return GitCaptureLimits(CaptureLimits(**capture_values), GitObjectLimits(**object_values))
    except ValueError as error:
        raise GitObjectError("limit") from error


def check_oid(value: str) -> str:
    if type(value) is not str or _OID.fullmatch(value) is None or value == "0" * 40:
        raise GitObjectError("invalid-input")
    return value


def source_path(parts: tuple[str, ...], limits: CaptureLimits) -> str:
    if type(parts) is not tuple or not parts or len(parts) > limits.max_depth:
        raise GitObjectError("limit")
    for name in parts:
        if type(name) is not str:
            raise GitObjectError("unsupported-object")
        if len(name) > limits.max_path_bytes:
            raise GitObjectError("limit")
        if (
            name in ("", ".", "..", ".git")
            or "/" in name
            or "\\" in name
            or any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in name)
        ):
            raise GitObjectError("unsupported-object")
    if sum(len(name) for name in parts) + len(parts) - 1 > limits.max_path_bytes:
        raise GitObjectError("limit")
    result = "/".join(parts)
    try:
        size = len(result.encode("utf-8", "strict"))
    except UnicodeError as error:
        raise GitObjectError("unsupported-object") from error
    if size > limits.max_path_bytes:
        raise GitObjectError("limit")
    return result


def file_stamp(info: os.stat_result) -> tuple[int, ...]:
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


def check_absolute(path: Path) -> Path:
    """Fresh bounded primitive snapshot; never call methods on caller path caches.

    Observed CPython 3.11 uses _parts; 3.12 uses _raw_paths. Unknown storage fails closed.
    Exact class alone is insufficient: object.__setattr__ can poison its slots.
    """
    if type(path) is not PosixPath:
        raise GitObjectError("invalid-input")
    parsed = False
    try:
        parts = object.__getattribute__(path, "_raw_paths")
    except AttributeError:
        try:
            parts = object.__getattribute__(path, "_parts")
        except AttributeError as error:
            raise GitObjectError("invalid-input") from error
        parsed = True
    if type(parts) is not list or not 1 <= len(parts) <= 4096:
        raise GitObjectError("invalid-input")
    snapshot = tuple(parts[:4097])  # Bound BEFORE copy even under accidental concurrent mutation.
    if not 1 <= len(snapshot) <= 4096:
        raise GitObjectError("invalid-input")
    total = 0
    for part in snapshot:
        if type(part) is not str or len(part) > 4096:
            raise GitObjectError("invalid-input")
        try:
            total += len(part.encode("utf-8", "strict"))
        except UnicodeError as error:
            raise GitObjectError("invalid-input") from error
        if (
            total > 4096
            or "\\" in part
            or any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in part)
        ):
            raise GitObjectError("invalid-input")
    if parsed:
        try:
            drive = object.__getattribute__(path, "_drv")
            root = object.__getattribute__(path, "_root")
        except AttributeError as error:
            raise GitObjectError("invalid-input") from error
        if type(drive) is not str or type(root) is not str or drive != "" or root != "/":
            raise GitObjectError("invalid-input")
        if snapshot[0] != "/" or any(
            "/" in part or part in ("", ".", "..") for part in snapshot[1:]
        ):
            raise GitObjectError("invalid-input")
    result = PosixPath(*snapshot)
    if (
        not result.is_absolute()
        or result.anchor != "/"
        or ".." in result.parts
        or len(str(result).encode("utf-8")) > 4096
    ):
        raise GitObjectError("invalid-input")
    return result


@contextmanager
def owned_descriptors() -> Iterator[list[int]]:
    """Close every unattempted owned FD; never retry an uncertain close number.

    A failed close can already have released its FD. Remove ownership BEFORE
    attempting it; uncertain closure is a fatal exception, not known cleanup.
    """
    owned: list[int] = []
    primary: BaseException | None = None
    try:
        yield owned
    except BaseException as error:
        primary = error
    cleanup: list[BaseException] = []
    while owned:
        descriptor = owned.pop()
        try:
            os.close(descriptor)
        except BaseException as error:
            cleanup.append(error)
    if primary is not None:
        if cleanup:
            prior = primary.__cause__
            causes = ([prior] if prior is not None else []) + cleanup
            raise primary from BaseExceptionGroup("directory cleanup failed", causes)
        raise primary
    if cleanup:
        if len(cleanup) > 1:
            raise cleanup[0] from BaseExceptionGroup("directory cleanup failed", cleanup[1:])
        raise cleanup[0]


@contextmanager
def open_directory(path: Path, *, mode: int = 0o700) -> Iterator[int]:
    """Walk ALL path components without following links; validate owned leaf."""
    path = check_absolute(path)
    with owned_descriptors() as owned:
        descriptor = os.open("/", DIRECTORY_FLAGS)
        owned.append(descriptor)
        for part in path.parts[1:]:
            child = os.open(part, DIRECTORY_FLAGS, dir_fd=descriptor)
            owned.append(child)
            owned.remove(descriptor)
            os.close(descriptor)
            descriptor = child
        info = os.fstat(descriptor)
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != mode:
            raise GitObjectError("invalid-input")
        yield descriptor


def check_regular(descriptor: int, *, maximum: int, private: bool = True) -> os.stat_result:
    info = os.fstat(descriptor)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or info.st_uid != os.geteuid()
        or info.st_size < 0
        or stat.S_IMODE(info.st_mode) & (0o077 if private else 0o022)
    ):
        raise GitObjectError("invalid-input")
    if info.st_size > maximum:
        raise GitObjectError("limit")
    return info


def write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        count = os.write(descriptor, view)
        if count <= 0:
            raise GitObjectError("storage")
        view = view[count:]


@dataclass(frozen=True, slots=True)
class GitObject:
    oid: str
    kind: str
    size: int
    preimage_sha256: bytes
    payload_sha256: bytes
    payload: bytes | None  # Only bounded commit/tree metadata; NEVER blob payload.
    stamp: tuple[int, ...] | None = None


@dataclass(frozen=True, slots=True)
class GitFile:
    path: str
    mode: str
    blob_oid: str
    size: int
    payload_sha256: bytes


@dataclass(frozen=True, slots=True)
class GitDirectory:
    path: str
    tree_oid: str


@dataclass(frozen=True, slots=True)
class GitTree:
    commit_oid: str
    root_tree_oid: str
    objects: tuple[GitObject, ...]
    files: tuple[GitFile, ...]
    directories: tuple[GitDirectory, ...]


def object_header(kind: str, size: int) -> bytes:
    if kind not in ("commit", "tree", "blob") or type(size) is not int or size < 0:
        raise GitObjectError("invalid-input")
    return f"{kind} {size}".encode("ascii") + b"\0"


def _read_object(
    descriptor: int,
    oid: str,
    limits: GitCaptureLimits,
    *,
    output: int | None = None,
    tree_remaining: int | None = None,
) -> GitObject:
    before = check_regular(descriptor, maximum=limits.objects.max_total_preimage_bytes)
    prefix = os.read(descriptor, 64)
    header, separator, first = prefix.partition(b"\0")
    match = _HEADER.fullmatch(header)
    if not separator or match is None:
        raise GitObjectError("unsupported-object")
    kind = match[1].decode("ascii")
    size = int(match[2])
    bound = {
        "commit": limits.objects.max_commit_bytes,
        "tree": limits.objects.max_tree_bytes,
        "blob": limits.capture.max_file_bytes,
    }[kind]
    if size > bound:
        raise GitObjectError("limit")
    if kind == "tree" and tree_remaining is not None and size > tree_remaining:
        raise GitObjectError("limit")
    if before.st_size != len(header) + 1 + size:
        raise GitObjectError("changed-input")
    if output is not None and kind != "blob":
        raise GitObjectError("unsupported-object")
    sha1 = hashlib.sha1(usedforsecurity=False)
    preimage = hashlib.sha256()
    content = hashlib.sha256()
    sha1.update(header + b"\0")
    preimage.update(header + b"\0")
    retained = bytearray()
    count = 0
    block = first
    while True:
        if block:
            count += len(block)
            if count > size:
                raise GitObjectError("changed-input")
            sha1.update(block)
            preimage.update(block)
            content.update(block)
            if kind != "blob":
                retained.extend(block)
            if output is not None:
                write_all(output, block)
        block = os.read(descriptor, min(CHUNK, size - count + 1))
        if not block:
            break
    if (
        count != size
        or sha1.hexdigest() != oid
        or file_stamp(os.fstat(descriptor)) != file_stamp(before)
    ):
        raise GitObjectError("changed-input")
    return GitObject(
        oid,
        kind,
        size,
        preimage.digest(),
        content.digest(),
        bytes(retained) if kind != "blob" else None,
        file_stamp(before),
    )


def metadata_object(oid: str, preimage: bytes, limits: GitCaptureLimits) -> GitObject:
    """Validate a bounded retained commit/tree preimage during proof replay."""
    check_oid(oid)
    limits = freeze_limits(limits)
    if (
        type(preimage) is not bytes
        or len(preimage) > max(limits.objects.max_commit_bytes, limits.objects.max_tree_bytes) + 64
    ):
        raise GitObjectError("limit")
    header, separator, payload = preimage.partition(b"\0")
    match = _HEADER.fullmatch(header)
    if not separator or len(header) + 1 > 64 or match is None or match[1] == b"blob":
        raise GitObjectError("unsupported-object")
    kind, size = match[1].decode("ascii"), int(match[2])
    maximum = limits.objects.max_commit_bytes if kind == "commit" else limits.objects.max_tree_bytes
    if size != len(payload) or size > maximum:
        raise GitObjectError("limit")
    if hashlib.sha1(preimage, usedforsecurity=False).hexdigest() != oid:
        raise GitObjectError("changed-input")
    return GitObject(
        oid,
        kind,
        size,
        hashlib.sha256(preimage).digest(),
        hashlib.sha256(payload).digest(),
        payload,
    )


def _commit_tree(payload: bytes, limits: GitObjectLimits) -> str:
    end = payload.find(b"\n\n", 0, limits.max_commit_header_bytes + 1)
    if end < 0 or end + 2 > limits.max_commit_header_bytes:
        raise GitObjectError("unsupported-object")
    lines = payload[:end].split(b"\n")
    if not lines or not lines[0].startswith(b"tree "):
        raise GitObjectError("unsupported-object")
    tree: str | None = None
    parents = 0
    for index, line in enumerate(lines):
        if line.startswith(b" "):
            if index == 0:
                raise GitObjectError("unsupported-object")
            continue
        key, space, value = line.partition(b" ")
        if not space or not key or any(not (33 <= char <= 126) for char in key):
            raise GitObjectError("unsupported-object")
        if key in (b"tree", b"parent"):
            try:
                parsed = check_oid(value.decode("ascii"))
            except (UnicodeError, GitObjectError) as error:
                raise GitObjectError("unsupported-object") from error
            if key == b"tree":
                if index != 0 or tree is not None:
                    raise GitObjectError("unsupported-object")
                tree = parsed
            else:
                parents += 1
                if parents > limits.max_parent_oids:
                    raise GitObjectError("limit")
    if tree is None:
        raise GitObjectError("unsupported-object")
    return tree


def _tree_entries(payload: bytes, limits: CaptureLimits) -> tuple[tuple[str, str, str], ...]:
    result: list[tuple[str, str, str]] = []
    names: set[str] = set()
    previous: bytes | None = None
    position = 0
    while position < len(payload):
        if len(result) >= limits.max_entries:
            raise GitObjectError("limit")
        space = payload.find(b" ", position, position + 8)
        nul = payload.find(b"\0", space + 1) if space >= 0 else -1
        if space < 0 or nul < 0 or nul + 21 > len(payload):
            raise GitObjectError("unsupported-object")
        if nul - space - 1 > limits.max_path_bytes:
            raise GitObjectError("limit")
        mode_raw, name_raw = payload[position:space], payload[space + 1 : nul]
        if mode_raw not in (b"40000", b"100644", b"100755"):
            raise GitObjectError("unsupported-object")
        try:
            name = name_raw.decode("utf-8", "strict")
        except UnicodeError as error:
            raise GitObjectError("unsupported-object") from error
        source_path((name,), limits)
        order = name_raw + (b"/" if mode_raw == b"40000" else b"\0")
        if name in names or (previous is not None and order <= previous):
            raise GitObjectError("unsupported-object")
        oid = check_oid(payload[nul + 1 : nul + 21].hex())
        result.append((name, mode_raw.decode("ascii"), oid))
        names.add(name)
        previous = order
        position = nul + 21
    return tuple(result)


def expand_objects(
    commit_oid: str, objects: tuple[GitObject, ...], limits: GitCaptureLimits
) -> GitTree:
    """Expand already measured objects; callers must establish each raw hash first."""
    check_oid(commit_oid)
    limits = freeze_limits(limits)
    if type(objects) is not tuple or len(objects) > limits.objects.max_objects:
        raise GitObjectError("limit")
    index: dict[str, GitObject] = {}
    preimage_bytes = tree_bytes = 0
    for obj in objects:
        if type(obj) is not GitObject:
            raise GitObjectError("invalid-input")
        check_oid(obj.oid)
        if obj.oid in index or obj.kind not in ("commit", "tree", "blob"):
            raise GitObjectError("unsupported-object")
        if type(obj.size) is not int or obj.size < 0:
            raise GitObjectError("invalid-input")
        for digest in (obj.preimage_sha256, obj.payload_sha256):
            if type(digest) is not bytes or len(digest) != 32:
                raise GitObjectError("invalid-input")
        if obj.kind == "blob":
            if obj.payload is not None or obj.size > limits.capture.max_file_bytes:
                raise GitObjectError("limit")
        else:
            if type(obj.payload) is not bytes:
                raise GitObjectError("invalid-input")
            maximum = (
                limits.objects.max_commit_bytes
                if obj.kind == "commit"
                else limits.objects.max_tree_bytes
            )
            if obj.size > maximum or len(obj.payload) != obj.size:
                raise GitObjectError("limit")
            measured = metadata_object(
                obj.oid, object_header(obj.kind, obj.size) + obj.payload, limits
            )
            if (measured.preimage_sha256, measured.payload_sha256) != (
                obj.preimage_sha256,
                obj.payload_sha256,
            ):
                raise GitObjectError("changed-input")
        preimage_bytes += len(object_header(obj.kind, obj.size)) + obj.size
        tree_bytes += obj.size if obj.kind == "tree" else 0
        if (
            preimage_bytes > limits.objects.max_total_preimage_bytes
            or tree_bytes > limits.objects.max_total_tree_bytes
        ):
            raise GitObjectError("limit")
        index[obj.oid] = obj
    commit = index.get(commit_oid)
    if commit is None or commit.kind != "commit" or commit.payload is None:
        raise GitObjectError("unsupported-object")
    root_oid = _commit_tree(commit.payload, limits.objects)
    reached = {commit_oid}
    files: list[GitFile] = []
    directories: list[GitDirectory] = []
    count = total = 0

    def walk(oid: str, parent: tuple[str, ...], ancestors: frozenset[str]) -> None:
        nonlocal count, total
        obj = index.get(oid)
        if obj is None or obj.kind != "tree" or obj.payload is None or oid in ancestors:
            raise GitObjectError("unsupported-object")
        reached.add(oid)
        for name, mode, child_oid in _tree_entries(obj.payload, limits.capture):
            count += 1
            if count > limits.capture.max_entries:
                raise GitObjectError("limit")
            parts = (*parent, name)
            path = source_path(parts, limits.capture)
            child = index.get(child_oid)
            if child is None:
                raise GitObjectError("unsupported-object")
            reached.add(child_oid)
            if mode == "40000":
                directories.append(GitDirectory(path, child_oid))
                walk(child_oid, parts, ancestors | {oid})
            else:
                if child.kind != "blob":
                    raise GitObjectError("unsupported-object")
                total += child.size
                if len(files) >= limits.capture.max_files or total > limits.capture.max_total_bytes:
                    raise GitObjectError("limit")
                files.append(GitFile(path, mode, child_oid, child.size, child.payload_sha256))

    walk(root_oid, (), frozenset())
    if reached != set(index):
        raise GitObjectError("unsupported-object")
    return GitTree(
        commit_oid,
        root_oid,
        tuple(sorted(objects, key=lambda obj: obj.oid)),
        tuple(sorted(files, key=lambda item: item.path)),
        tuple(sorted(directories, key=lambda item: item.path)),
    )


def load_object_directory(descriptor: int, commit_oid: str, limits: GitCaptureLimits) -> GitTree:
    """Read a held private input-directory descriptor; retain no blob buffers."""
    limits = freeze_limits(limits)
    check_oid(commit_oid)
    before = file_stamp(os.fstat(descriptor))
    names: list[str] = []
    with os.scandir(descriptor) as entries:
        for entry in entries:
            if len(names) >= limits.objects.max_objects:
                raise GitObjectError("limit")
            if len(entry.name) != 47 or not entry.name.endswith(".object"):
                raise GitObjectError("unsupported-object")
            check_oid(entry.name[:-7])
            names.append(entry.name)
    objects: list[GitObject] = []
    aggregate = tree_bytes = 0
    for name in sorted(names):
        source = os.open(name, FILE_FLAGS, dir_fd=descriptor)
        try:
            info = check_regular(source, maximum=limits.objects.max_total_preimage_bytes)
            aggregate += info.st_size
            if aggregate > limits.objects.max_total_preimage_bytes:
                raise GitObjectError("limit")
            obj = _read_object(
                source,
                name[:-7],
                limits,
                tree_remaining=limits.objects.max_total_tree_bytes - tree_bytes,
            )
            tree_bytes += obj.size if obj.kind == "tree" else 0
            if tree_bytes > limits.objects.max_total_tree_bytes:
                raise GitObjectError("limit")
            objects.append(obj)
        finally:
            os.close(source)
    if before != file_stamp(os.fstat(descriptor)):
        raise GitObjectError("changed-input")
    return expand_objects(commit_oid, tuple(objects), limits)


def copy_verified_blob(
    input_directory: int, expected: GitObject, destination: int, limits: GitCaptureLimits
) -> None:
    """Rehash actual source bytes during exclusive output; caller verifies readback."""
    if type(expected) is not GitObject or expected.kind != "blob" or expected.stamp is None:
        raise GitObjectError("invalid-input")
    check_oid(expected.oid)
    descriptor = os.open(expected.oid + ".object", FILE_FLAGS, dir_fd=input_directory)
    try:
        observed = _read_object(descriptor, expected.oid, freeze_limits(limits), output=destination)
        if observed != expected:
            raise GitObjectError("changed-input")
    finally:
        os.close(descriptor)


def recheck_object_directory(descriptor: int, expected: GitTree, limits: GitCaptureLimits) -> None:
    if load_object_directory(descriptor, expected.commit_oid, limits) != expected:
        raise GitObjectError("changed-input")
