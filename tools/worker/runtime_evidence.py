"""Diagnostic non-event byte custody; never installed runtime authority.

The private writer requires an already installed diagnostic root. It cannot
bootstrap an installation, publish events, execute commands or grant permission.
Contract: docs/bhmea/RUNTIME-EVIDENCE-STORE.md section 18.
"""

from __future__ import annotations

import fcntl
import hashlib
import os
import re
import stat
import struct
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import PosixPath
from typing import Any, Literal, TypeAlias, cast
from uuid import UUID

from tools.worker.process_evidence import (
    EvidenceBlob,
    ProcessEvidenceError,
    StoredObject,
    StoredValue,
    decode_error_graph,
)
from tools.worker.runtime_journal import (
    JournalRecordKind,
    ParsedJournalRecord,
    decode_journal_record,
    encode_journal_record,
)

_MIB = 1048576
_CHUNK = 65536
_INT = 2**63 - 1
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_UUID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z")
_MODES = ("verifier-historical", "verifier-publication", "verifier-execution", "python-syntax")
_ACTIONS = ("audit-historical", "publish-builtin-preflight", "verify-execution", "parse-python")
_AUTH = (
    "authentication",
    "scope",
    "admission",
    "execution-authorization",
    "capture-lease",
    "content-verification",
)
_SELECTORS = (
    "metadata",
    "request",
    "input",
    "launch",
    "prerequisite",
    "authority-inventory",
    "parent-barrier",
    "authority",
    "refusal-evidence",
)
SelectorKind: TypeAlias = Literal[
    "metadata",
    "request",
    "input",
    "launch",
    "prerequisite",
    "authority-inventory",
    "parent-barrier",
    "authority",
    "refusal-evidence",
]
_REASONS = frozenset(
    (
        "invalid-input",
        "unsafe-path",
        "conflict",
        "limit",
        "deadline",
        "storage",
        "cleanup-incomplete",
        "unsupported",
    )
)


class RuntimePublicationError(ValueError):
    """Fixed safe reason; raw causes remain private."""

    def __init__(self, reason: str = "invalid-input") -> None:
        self.reason = reason if type(reason) is str and reason in _REASONS else "invalid-input"
        super().__init__(self.reason)


def _need(condition: bool, reason: str = "invalid-input") -> None:
    if not condition:
        raise RuntimePublicationError(reason)


class _StoredStateChangedError(RuntimePublicationError):
    """Private evidence of detected drift, distinct from a caller conflict."""


def _stable(condition: bool) -> None:
    if not condition:
        raise _StoredStateChangedError("conflict")


@dataclass(frozen=True, slots=True, repr=False)
class RuntimeEvidenceInstallation:
    deployment_id: UUID
    store_id: UUID
    artifact_domain: Literal["operational", "diagnostic"]
    evidence_root: PosixPath
    host_work_root: PosixPath
    owner_uid: int
    owner_gid: int
    root_record_sha256: bytes


@dataclass(frozen=True, slots=True, repr=False)
class _ScopeKey:
    kind: Literal["attempt", "refusal"]
    id: UUID


@dataclass(frozen=True, slots=True, repr=False)
class _PublicationKey:
    scope: _ScopeKey
    publication_id: UUID


@dataclass(frozen=True, slots=True, repr=False)
class _FileStamp:
    device: int
    inode: int
    full_mode: int
    uid: int
    gid: int
    nlink: int
    size: int
    mtime_ns: int
    ctime_ns: int


@dataclass(frozen=True, slots=True, repr=False)
class MemberSelector:
    kind: SelectorKind
    ordinal: int


@dataclass(frozen=True, slots=True, repr=False)
class VisiblePublication:
    visibility: Literal["verified-visible-file"]
    key: _PublicationKey
    intent: ParsedJournalRecord
    file: EvidenceBlob
    record: ParsedJournalRecord | None
    observation: _FileStamp


@dataclass(frozen=True, slots=True, repr=False)
class _PublicationAck:
    completion: Literal["local-fsync-readback"]
    publication: VisiblePublication
    disposition: Literal["new", "exact-recovery"]


def _uuid(value: object) -> UUID:
    _need(type(value) is UUID)
    number = _field(value, "int")
    _need(type(number) is int and 0 <= number < 2**128)
    return UUID(int=number)


def _field(value: object, name: str) -> Any:  # noqa: ANN401 -- detached primitive boundary
    try:
        return object.__getattribute__(value, name)
    except AttributeError as error:
        raise RuntimePublicationError("invalid-input") from error


def _integer(value: object, maximum: int = _INT, minimum: int = 0) -> int:
    _need(type(value) is int and minimum <= value <= maximum)
    return cast(int, value)


def _hash_value(value: object) -> bytes:
    _need(type(value) is bytes and len(value) == 32)
    return cast(bytes, value)


def _path(value: object) -> PosixPath:
    _need(type(value) is PosixPath, "unsafe-path")
    try:
        try:
            parts = object.__getattribute__(value, "_raw_paths")
            raw_layout = True
        except AttributeError:
            parts = object.__getattribute__(value, "_parts")
            raw_layout = False
        _need(type(parts) is list, "unsafe-path")
        copied = tuple(parts[:4097])
        _need(0 < len(copied) <= 4096, "limit")
        _need(all(type(part) is str for part in copied), "unsafe-path")
        _need(sum(len(part) for part in copied) + len(copied) <= 4098, "limit")
        fresh = PosixPath(*copied)
        text = str(fresh)
    except AttributeError as error:
        raise RuntimePublicationError("unsupported") from error
    try:
        encoded_length = len(text.encode("utf-8"))
    except UnicodeError as error:
        raise RuntimePublicationError("unsafe-path") from error
    _need(1 < encoded_length <= 4096, "limit")
    _need(text.startswith("/") and "\\" not in text, "unsafe-path")
    _need(not any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in text), "unsafe-path")
    _need(all(part not in ("", ".", "..") for part in text[1:].split("/")), "unsafe-path")
    # Reject non-normalized raw spellings instead of letting pathlib repair them.
    if raw_layout:
        # CPython 3.12 keeps finite constructor fragments, not normalized
        # components. Joining validated fragments preserves their actual path
        # while refusing discarded absolute fragments or normalization tricks.
        spelling = "/" + "/".join(copied[1:]) if copied[0] == "/" else "/".join(copied)
        _need(text == spelling, "unsafe-path")
    elif copied[0] == "/":
        _need(text == "/" + "/".join(copied[1:]), "unsafe-path")
    else:
        _need(len(copied) == 1 and text == copied[0], "unsafe-path")
    return PosixPath(text)


def _installation(value: RuntimeEvidenceInstallation) -> RuntimeEvidenceInstallation:
    _need(type(value) is RuntimeEvidenceInstallation)
    names = RuntimeEvidenceInstallation.__slots__
    raw = {name: _field(value, name) for name in names}
    _need(
        type(raw["artifact_domain"]) is str and raw["artifact_domain"] == "diagnostic",
        "unsupported",
    )
    root, work = _path(raw["evidence_root"]), _path(raw["host_work_root"])
    _need(not root.is_relative_to(work) and not work.is_relative_to(root), "unsafe-path")
    return RuntimeEvidenceInstallation(
        _uuid(raw["deployment_id"]),
        _uuid(raw["store_id"]),
        "diagnostic",
        root,
        work,
        _integer(raw["owner_uid"], 2**31 - 1, 1),
        _integer(raw["owner_gid"], 2**31 - 1, 1),
        _hash_value(raw["root_record_sha256"]),
    )


def _scope(value: _ScopeKey) -> _ScopeKey:
    _need(type(value) is _ScopeKey)
    kind = _field(value, "kind")
    identity = _field(value, "id")
    _need(type(kind) is str and kind in ("attempt", "refusal"))
    return _ScopeKey(cast(Literal["attempt", "refusal"], kind), _uuid(identity))


def _key(value: _PublicationKey) -> _PublicationKey:
    _need(type(value) is _PublicationKey)
    scope = _field(value, "scope")
    identity = _field(value, "publication_id")
    return _PublicationKey(_scope(scope), _uuid(identity))


def _selector(value: MemberSelector) -> MemberSelector:
    _need(type(value) is MemberSelector)
    kind = _field(value, "kind")
    ordinal = _field(value, "ordinal")
    _need(type(kind) is str and kind in _SELECTORS)
    maximum = (
        3
        if kind == "metadata"
        else 5
        if kind == "authority"
        else 15
        if kind == "refusal-evidence"
        else 0
    )
    return MemberSelector(cast(SelectorKind, kind), _integer(ordinal, maximum))


def _stamp(value: os.stat_result) -> _FileStamp:
    for item in (value.st_dev, value.st_mode, value.st_uid, value.st_gid, value.st_size):
        _integer(item)
    _integer(value.st_ino, minimum=1)
    _integer(value.st_nlink, minimum=1)
    _integer(value.st_mtime_ns, minimum=-(2**63))
    _integer(value.st_ctime_ns, minimum=-(2**63))
    return _FileStamp(
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_gid,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _identity(value: _FileStamp) -> tuple[int, ...]:
    return value.device, value.inode, value.full_mode, value.uid, value.gid


def _chain(primary: BaseException, errors: list[BaseException]) -> None:
    prior = primary.__cause__ if primary.__cause__ is not None else primary.__context__
    members: list[BaseException] = []
    for item in ([prior] if prior is not None else []) + errors:
        if item is not primary and all(item is not previous for previous in members):
            members.append(item)
    if members:
        primary.__cause__ = BaseExceptionGroup("private cleanup failures", members)


@dataclass(slots=True)
class _Totals:
    read: int = 0
    write: int = 0
    hash: int = 0


class _Work:
    """Conservative delegated reservations and metered owned operations.

    These private counters are implementation work, not RSS/kernel telemetry.
    """

    def __init__(
        self, *, root: bool = False, totals: _Totals | None = None, refusal_final: bool = False
    ) -> None:
        self.root = root
        self.started = time.monotonic_ns()
        self.totals = totals
        self.owner_limit = 32768 if root else 24 if refusal_final else 16
        self.read = self.write = self.hash = self.copies = 0
        self.os_calls = self.observations = self.owner_calls = 0
        # Fixed source-derived live reservations: compact census (4 MiB),
        # one previous raw member (8 MiB), plan (8192 slots), and bounded
        # scope/intent/reference/accounting/name containers (16384 slots).
        # They remain reserved through cleanup; no per-file reset.
        self.slots, self.buffers = 24576, 12 * _MIB
        self.peak_slots, self.peak_buffers = self.slots, self.buffers
        self.fd_count = self.peak_fds = 0
        self.effects_started = False
        self.cleanup_uncertain = False

    def check(self) -> None:
        _need(
            time.monotonic_ns() - self.started < (35000 if self.root else 2000) * 1000000,
            "deadline",
        )

    def reserve(self, name: str, amount: int) -> None:
        bounds = {
            "read": 16 * 1024 * _MIB if self.root else 128 * _MIB,
            "write": 64 * _MIB,
            "hash": 32 * 1024 * _MIB if self.root else 256 * _MIB,
            "copies": (8 * 1024 * _MIB + 4096 + 2 * _MIB * 32768 + 16 * _MIB)
            if self.root
            else 192 * _MIB,
            "os_calls": 262144 if self.root else 8192,
            "observations": 131072 if self.root else 512,
            "owner_calls": self.owner_limit,
        }
        value = getattr(self, name) + amount
        _need(amount >= 0 and value <= bounds[name], "limit")
        if self.totals is not None and name in ("read", "write", "hash"):
            total = getattr(self.totals, name) + amount
            maximum = {"read": 8 * 1024 * _MIB, "write": 256 * _MIB, "hash": 16 * 1024 * _MIB}[name]
            _need(total <= maximum, "limit")

    def charge(self, name: str, amount: int) -> None:
        self.reserve(name, amount)
        setattr(self, name, getattr(self, name) + amount)
        if self.totals is not None and name in ("read", "write", "hash"):
            setattr(self.totals, name, getattr(self.totals, name) + amount)

    @contextmanager
    def allocation(self, *, slots: int = 0, buffers: int = 0) -> Iterator[None]:
        _need(self.slots + slots <= 262144 and self.buffers + buffers <= 96 * _MIB, "limit")
        self.slots += slots
        self.buffers += buffers
        self.peak_slots = max(self.peak_slots, self.slots)
        self.peak_buffers = max(self.peak_buffers, self.buffers)
        try:
            yield
        finally:
            self.slots -= slots
            self.buffers -= buffers

    def call(self, *, cleanup: bool = False) -> None:
        if not cleanup:
            self.check()
            _need(self.os_calls < (262144 if self.root else 8192) - 128, "limit")
        self.charge("os_calls", 1)

    def observation(self) -> None:
        self.charge("observations", 1)


def _digest(data: bytes, work: _Work) -> bytes:
    result = hashlib.sha256()
    view = memoryview(data)
    for offset in range(0, len(data), _CHUNK):
        work.check()
        piece = view[offset : offset + _CHUNK]
        work.charge("hash", len(piece))
        result.update(piece)
    return result.digest()


def _plain(value: StoredValue) -> Any:  # noqa: ANN401 -- only private owner-decoded tags
    if type(value) is tuple:
        if value[0] == "object":
            return {key: _plain(child) for key, child in value[1]}
        return [_plain(child) for child in value[1]]
    return value


def _tag(value: Any) -> StoredValue:  # noqa: ANN401 -- fixed private generated owner document
    if type(value) is dict:
        return ("object", tuple((key, _tag(child)) for key, child in sorted(value.items())))
    if type(value) is list:
        return ("array", tuple(_tag(child) for child in value))
    return cast(StoredValue, value)


def _decode(kind: JournalRecordKind, data: bytes, work: _Work) -> ParsedJournalRecord:
    work.charge("owner_calls", 1)
    work.charge("hash", 2 * len(data) + 128)
    work.charge("copies", 2 * _MIB)
    with work.allocation(slots=32768):
        return decode_journal_record(kind, data)


def _encode_intent(document: dict[str, Any], work: _Work) -> bytes:
    work.charge("owner_calls", 1)
    work.charge("hash", 2 * 4096 + 128)
    work.charge("copies", 2 * _MIB)
    with work.allocation(slots=32768):
        return encode_journal_record("publication-intent", cast(StoredObject, _tag(document)))


class _Descriptors:
    def __init__(self, work: _Work) -> None:
        self.work = work
        self.owned: set[int] = set()

    def hold(self, fd: int) -> int:
        self.owned.add(fd)
        self.work.fd_count += 1
        self.work.peak_fds = max(self.work.peak_fds, self.work.fd_count)
        _need(self.work.fd_count <= 128, "limit")
        return fd

    def open(self, name: str, flags: int, mode: int = 0o777, *, parent: int | None = None) -> int:
        _need(self.work.fd_count < 128, "limit")
        self.work.call()
        return self.hold(os.open(name, flags, mode, dir_fd=parent))

    def close(self, fd: int) -> None:
        self.owned.remove(fd)
        self.work.fd_count -= 1
        try:
            self.work.call(cleanup=True)
            os.close(fd)
        except BaseException:
            self.work.cleanup_uncertain = True
            raise

    def finish(self, primary: BaseException | None = None) -> None:
        errors: list[BaseException] = []
        for fd in tuple(self.owned):
            try:
                self.close(fd)
            except BaseException as error:
                errors.append(error)
        if primary is not None:
            _chain(primary, errors)
            raise primary
        if errors:
            chosen = next((error for error in errors if not isinstance(error, Exception)), None)
            if chosen is not None:
                _chain(chosen, errors)
                raise chosen
            failure = RuntimePublicationError("cleanup-incomplete")
            _chain(failure, errors)
            raise failure


@contextmanager
def _owned(work: _Work) -> Iterator[_Descriptors]:
    descriptors = _Descriptors(work)
    primary: BaseException | None = None
    try:
        yield descriptors
    except BaseException as error:
        primary = error
    descriptors.finish(primary)


def _fstat(fd: int, work: _Work) -> _FileStamp:
    work.observation()
    work.call()
    return _stamp(os.fstat(fd))


def _member(parent: int, name: str, work: _Work) -> _FileStamp:
    work.observation()
    work.call()
    return _stamp(os.stat(name, dir_fd=parent, follow_symlinks=False))


def _regular(
    stamp: _FileStamp,
    installation: RuntimeEvidenceInstallation,
    modes: tuple[int, ...] = (0o400,),
    links: tuple[int, ...] = (1,),
) -> None:
    _need(
        stat.S_ISREG(stamp.full_mode)
        and stat.S_IMODE(stamp.full_mode) in modes
        and stamp.uid == installation.owner_uid
        and stamp.gid == installation.owner_gid
        and stamp.nlink in links,
        "unsafe-path",
    )


def _directory(stamp: _FileStamp, installation: RuntimeEvidenceInstallation) -> None:
    _need(
        stat.S_ISDIR(stamp.full_mode)
        and stat.S_IMODE(stamp.full_mode) == 0o700
        and stamp.uid == installation.owner_uid
        and stamp.gid == installation.owner_gid,
        "unsafe-path",
    )


def _open_dir(parent: int, name: str, files: _Descriptors) -> int:
    return files.open(
        name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, parent=parent
    )


def _sync(fd: int, work: _Work) -> None:
    work.call()
    work.effects_started = True
    os.fsync(fd)


def _read(
    parent: int,
    name: str,
    maximum: int,
    installation: RuntimeEvidenceInstallation,
    files: _Descriptors,
    *,
    modes: tuple[int, ...] = (0o400,),
    links: tuple[int, ...] = (1,),
    sync: bool = False,
    expected: _FileStamp | None = None,
) -> tuple[EvidenceBlob, _FileStamp]:
    work = files.work
    fd = files.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, parent=parent)
    before = _fstat(fd, work)
    if expected is not None:
        _stable(before == expected)
    _regular(before, installation, modes, links)
    _need(0 <= before.size <= maximum, "limit")
    if sync:
        _sync(fd, work)
    # os.read result, exact assembly assignment, immutable final bytes.
    work.charge("copies", 3 * before.size)
    with work.allocation(buffers=2 * before.size + 2 * _CHUNK):
        assembled = bytearray(before.size)
        offset = 0
        digest = hashlib.sha256()
        while offset < before.size:
            amount = min(_CHUNK, before.size - offset)
            work.reserve("read", amount)
            work.reserve("hash", amount)
            work.call()
            piece = os.read(fd, amount)
            work.charge("read", len(piece))
            _need(bool(piece), "storage")
            work.charge("hash", len(piece))
            digest.update(piece)
            assembled[offset : offset + len(piece)] = piece
            offset += len(piece)
        work.reserve("read", 1)
        work.call()
        last = os.read(fd, 1)
        work.charge("read", len(last))
        _stable(last == b"")
        _stable(_fstat(fd, work) == before and _member(parent, name, work) == before)
        result = EvidenceBlob(bytes(assembled), digest.digest())
    files.close(fd)
    return result, before


def _write(
    parent: int,
    name: str,
    data: bytes,
    installation: RuntimeEvidenceInstallation,
    files: _Descriptors,
) -> _FileStamp:
    work = files.work
    work.effects_started = True
    fd = files.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
        0o600,
        parent=parent,
    )
    _regular(_fstat(fd, work), installation, (0o600,))
    offset = 0
    view = memoryview(data)
    while offset < len(data):
        piece = view[offset : offset + _CHUNK]
        work.reserve("write", len(piece))
        work.call()
        written = os.write(fd, piece)
        work.charge("write", max(0, written))
        _need(0 < written <= len(piece), "storage")
        offset += written
    _sync(fd, work)
    work.call()
    os.fchmod(fd, 0o400)
    _sync(fd, work)
    stamp = _fstat(fd, work)
    _regular(stamp, installation)
    _need(stamp.size == len(data) and _member(parent, name, work) == stamp, "conflict")
    files.close(fd)
    _sync(parent, work)
    return stamp


_PACK = struct.Struct(">QQIIIQQqq")
_ROW = 256
_AUX = 190


class _Census:
    """Fixed 256-byte rows, never an object graph of all installed histories."""

    def __init__(self, work: _Work) -> None:
        self.data = bytearray()
        self.work = work

    def _offset(self, path: str) -> int | None:
        encoded = path.encode("ascii")
        self.work.charge("copies", len(encoded))
        _need(len(encoded) <= 128, "limit")
        view = memoryview(self.data)
        for offset in range(0, len(self.data), _ROW):
            size = struct.unpack_from(">H", self.data, offset)[0]
            if size == len(encoded) and view[offset + 2 : offset + 2 + size] == encoded:
                return offset
        return None

    def put(self, path: str, stamp: _FileStamp, *, aux: bytes | None = None) -> None:
        self.work.charge("copies", 512)
        encoded = path.encode("ascii")
        _need(0 < len(encoded) <= 128, "limit")
        offset = self._offset(path)
        if offset is None:
            _need(len(self.data) // _ROW < 16384, "limit")
            offset = len(self.data)
            self.data.extend(bytes(_ROW))
        self.data[offset : offset + 2] = len(encoded).to_bytes(2, "big")
        self.data[offset + 2 : offset + 2 + len(encoded)] = encoded
        _PACK.pack_into(
            self.data,
            offset + 130,
            *(
                stamp.device,
                stamp.inode,
                stamp.full_mode,
                stamp.uid,
                stamp.gid,
                stamp.nlink,
                stamp.size,
                stamp.mtime_ns,
                stamp.ctime_ns,
            ),
        )
        if aux is not None:
            _need(len(aux) == 65)
            self.data[offset + _AUX : offset + _AUX + 65] = aux

    def get(self, path: str) -> tuple[_FileStamp, bytes]:
        self.work.charge("copies", 130)
        offset = self._offset(path)
        _need(offset is not None, "conflict")
        assert offset is not None
        stamp = _FileStamp(*_PACK.unpack_from(self.data, offset + 130))
        return stamp, bytes(self.data[offset + _AUX : offset + _AUX + 65])

    def remove(self, path: str) -> None:
        self.work.charge("copies", 512)
        offset = self._offset(path)
        _need(offset is not None, "conflict")
        assert offset is not None
        # Reuse the final row; row order is not an identity or admission claim.
        self.data[offset : offset + _ROW] = self.data[-_ROW:]
        del self.data[-_ROW:]

    def rows(self, prefix: str) -> Iterator[tuple[str, _FileStamp, bytes]]:
        encoded = prefix.encode("ascii")
        self.work.charge("copies", len(encoded))
        for offset in range(0, len(self.data), _ROW):
            size = struct.unpack_from(">H", self.data, offset)[0]
            if (
                size >= len(encoded)
                and memoryview(self.data)[offset + 2 : offset + 2 + len(encoded)] == encoded
            ):
                self.work.charge("copies", 2 * size + 130)
                name = self.data[offset + 2 : offset + 2 + size].decode("ascii")
                yield (
                    name,
                    _FileStamp(*_PACK.unpack_from(self.data, offset + 130)),
                    bytes(self.data[offset + _AUX : offset + _AUX + 65]),
                )


@dataclass(frozen=True, slots=True)
class _Reference:
    checksum: str
    size: int
    metadata: bool


def _reference(row: dict[str, Any], *, metadata: bool) -> _Reference:
    return _Reference(row["sha256"], row["size"], metadata)


class _Plan:
    def __init__(
        self,
        key: _ScopeKey,
        publication_id: UUID,
        record: ParsedJournalRecord,
        installation: RuntimeEvidenceInstallation,
    ) -> None:
        self.key = key
        self.publication_id = publication_id
        self.record = record
        self.row = cast(dict[str, Any], _plain(record.document))
        self.refs: dict[tuple[str, int], _Reference] = {}
        self.prerequisite: dict[str, Any] | None = None
        self.inventory: dict[str, Any] | None = None
        self.authority_bytes = _MIB if key.kind == "attempt" else 0
        if key.kind == "refusal":
            _need(self.row["refusal_id"] == str(key.id), "conflict")
            seen: set[str] = set()
            for index, row in enumerate(self.row["available_evidence"]):
                _need(row["sha256"] not in seen, "conflict")
                seen.add(row["sha256"])
                self.refs[("refusal-evidence", index)] = _reference(row, metadata=False)
            self.maximum = 1 + len(seen)
        else:
            _need(
                self.row["deployment_id"] == str(installation.deployment_id)
                and self.row["store_id"] == str(installation.store_id)
                and self.row["artifact_domain"] == "diagnostic"
                and self.row["attempt_id"] == str(key.id),
                "conflict",
            )
            self.maximum = (12, 13, 16, 17)[_MODES.index(self.row["mode"])]
            for index, item in enumerate(self.row["metadata"]):
                reference = _reference(item["blob"], metadata=False)
                _need(reference.size <= (65536, 131072, 65536, 8388608)[index], "limit")
                self.refs[("metadata", index)] = reference
            for selector, field in (
                ("request", "request"),
                ("input", "input"),
                ("launch", "launch"),
                ("prerequisite", "initial_prerequisite"),
                ("authority-inventory", "authority_inventory"),
                ("parent-barrier", "parent_barrier"),
            ):
                if self.row[field] is not None:
                    self.refs[(selector, 0)] = _reference(
                        self.row[field], metadata=selector != "input"
                    )
        self.quota({})

    @property
    def parent_name(self) -> str:
        return "manifest.json" if self.key.kind == "attempt" else "refusal.json"

    def resolve(self, selector: MemberSelector) -> _Reference:
        key = selector.kind, selector.ordinal
        _need(key in self.refs, "conflict")
        return self.refs[key]

    def observe(self, checksum: str, raw: bytes, work: _Work) -> None:
        if self.key.kind != "attempt":
            return
        for kind, field in (
            ("prerequisite", "initial_prerequisite"),
            ("authority-inventory", "authority_inventory"),
        ):
            if checksum == self.row[field]["sha256"]:
                parsed = _decode(cast(JournalRecordKind, kind), raw, work)
                row = cast(dict[str, Any], _plain(parsed.document))
                if kind == "prerequisite":
                    self.prerequisite = row
                else:
                    self.inventory = row
        if self.prerequisite is not None and self.inventory is not None:
            self._links()

    def _links(self) -> None:
        p, inventory = self.prerequisite, self.inventory
        assert p is not None and inventory is not None
        _need(inventory["prerequisite"] == self.row["initial_prerequisite"], "conflict")
        _need(p["action"] == _ACTIONS[_MODES.index(self.row["mode"])], "conflict")
        _need(p["observed_at"] <= self.row["created_at"] < p["valid_until"], "conflict")
        required = ["authentication", "scope"]
        if p["admission"] is not None:
            required.append("admission")
        if p["execution_authorization_digest"] is not None:
            required.extend(("execution-authorization", "capture-lease"))
        if p["content_verification_evidence_sha256"] is not None:
            required.append("content-verification")
        _need([item["role"] for item in inventory["objects"]] == required, "conflict")
        total = 0
        for item in inventory["objects"]:
            role = item["role"]
            reference = _reference(item["bytes"], metadata=False)
            total += reference.size
            self.refs[("authority", _AUTH.index(role))] = reference
            if role not in ("admission", "execution-authorization"):
                field = role.replace("-", "_") + "_evidence_sha256"
                _need(reference.checksum == p[field], "conflict")
        _need(total <= _MIB, "limit")
        self.authority_bytes = total
        root = self.record.sha256.hex()
        inv_hash = self.row["authority_inventory"]["sha256"]
        prerequisite_hash = self.row["initial_prerequisite"]["sha256"]
        child_hashes = {ref.checksum for ref in self.refs.values()}
        _need(root not in child_hashes, "conflict")
        _need(inv_hash != prerequisite_hash, "conflict")
        _need(
            all(
                ref.checksum not in (inv_hash, prerequisite_hash)
                for (kind, _), ref in self.refs.items()
                if kind == "authority"
            ),
            "conflict",
        )

    def quota(
        self,
        completed: dict[str, int],
        *,
        unresolved: int = 0,
        primary_size: int | None = None,
    ) -> tuple[int, int]:
        _need(len(completed) + unresolved <= self.maximum and unresolved <= 16, "limit")
        # Physical dedup affects retained bytes only, not role metadata charges.
        unique: dict[str, int] = {self.record.sha256.hex(): len(self.record.data)}
        metadata = len(self.record.data)
        for reference in self.refs.values():
            _need(reference.checksum != self.record.sha256.hex(), "conflict")
            _need(
                reference.checksum not in unique or unique[reference.checksum] == reference.size,
                "conflict",
            )
            unique[reference.checksum] = reference.size
            if reference.metadata:
                metadata += reference.size
        if self.key.kind == "refusal" and self.row["primary_error_id"] is not None:
            metadata += 8192 if primary_size is None else primary_size
        pending = self.maximum - len(completed)
        controls = sum(completed.values()) + pending * 4096
        extra_authority = (
            self.authority_bytes if (self.inventory is None or self.prerequisite is None) else 0
        )
        _need(metadata + controls + 131072 + 65536 <= 524288, "limit")
        _need(sum(unique.values()) + extra_authority + controls + 2097152 <= 32 * _MIB, "limit")
        return metadata + controls + 196608, sum(
            unique.values()
        ) + extra_authority + controls + 2097152


def _names(fd: int, work: _Work, maximum: int) -> list[str]:
    result: list[str] = []
    work.call()
    iterator = os.scandir(fd)
    primary: BaseException | None = None
    try:
        for entry in iterator:
            work.observation()
            _need(len(result) < maximum, "limit")
            name = entry.name
            _need(type(name) is str and 0 < len(name) <= 128 and name.isascii(), "unsafe-path")
            result.append(name)
    except BaseException as error:
        primary = error
    try:
        work.call(cleanup=True)
        iterator.close()
    except BaseException as error:
        work.cleanup_uncertain = True
        if primary is None:
            raise
        _chain(primary, [error])
    if primary is not None:
        raise primary
    return sorted(result)


def _prefix(key: _ScopeKey) -> str:
    return ("attempts" if key.kind == "attempt" else "refusals") + "/" + str(key.id)


def _intent_document(
    key: _PublicationKey, store: UUID, role: str, destination: str, blob: EvidenceBlob
) -> dict[str, Any]:
    return {
        "schema": "scanipy-runtime-publication-intent/1",
        "publication_id": str(key.publication_id),
        "store_id": str(store),
        "scope_kind": key.scope.kind,
        "scope_id": str(key.scope.id),
        "role": role,
        "destination": destination,
        "size": len(blob.data),
        "sha256": blob.sha256.hex(),
        "expected_previous_event_digest": None,
    }


def _intent_check(
    record: ParsedJournalRecord, key: _PublicationKey, installation: RuntimeEvidenceInstallation
) -> dict[str, Any]:
    row = cast(dict[str, Any], _plain(record.document))
    _need(
        row["publication_id"] == str(key.publication_id)
        and row["store_id"] == str(installation.store_id)
        and row["scope_kind"] == key.scope.kind
        and row["scope_id"] == str(key.scope.id)
        and row["expected_previous_event_digest"] is None
        and row["role"] in ("blob", "manifest", "refusal"),
        "conflict",
    )
    return row


def _mapped(error: Exception) -> RuntimePublicationError:
    if type(error) is RuntimePublicationError:
        return error
    if type(error) is _StoredStateChangedError:
        return RuntimePublicationError("conflict")
    return RuntimePublicationError("storage" if isinstance(error, OSError) else "invalid-input")


def _walk(
    path: PosixPath, installation: RuntimeEvidenceInstallation, files: _Descriptors
) -> tuple[int, tuple[tuple[int, ...], ...]]:
    work = files.work
    fd = files.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    chain: list[tuple[int, ...]] = []
    components = path.parts[1:]
    for index, name in enumerate(components):
        child = _open_dir(fd, name, files)
        observed = _fstat(child, work)
        _need(stat.S_ISDIR(observed.full_mode), "unsafe-path")
        if index == len(components) - 1:
            _directory(observed, installation)
        else:
            trusted_tmp = (
                index == 0
                and name == "tmp"
                and observed.uid == 0
                and bool(observed.full_mode & stat.S_ISVTX)
            )
            _need(
                observed.uid in (0, installation.owner_uid)
                and (not observed.full_mode & 0o022 or trusted_tmp),
                "unsafe-path",
            )
        _stable(_identity(_member(fd, name, work)) == _identity(observed))
        chain.append(_identity(observed))
        files.close(fd)
        fd = child
    return fd, tuple(chain)


@dataclass(slots=True)
class _ScopeFiles:
    directory: int
    staging: int
    blobs: int


class _Core:
    def __init__(self, installation: RuntimeEvidenceInstallation, *, writer: bool) -> None:
        self.installation = installation
        self.writer = writer
        self.closed = False
        self.invalidated = False
        self.lock = threading.Lock()
        self.totals: dict[_ScopeKey, _Totals] = {}
        self.active: _PlannedScope | None = None
        self.last_work: _Work | None = None
        self.files = _Descriptors(_Work(root=True))
        work = self.files.work
        self.census = _Census(work)
        primary: BaseException | None = None
        try:
            work.call()
            _need(os.geteuid() == installation.owner_uid, "unsupported")
            work.call()
            _need(os.getegid() == installation.owner_gid, "unsupported")
            self.root, self.root_chain = _walk(installation.evidence_root, installation, self.files)
            self.work, self.work_chain = _walk(
                installation.host_work_root, installation, self.files
            )
            _need(_names(self.work, work, 0) == [], "unsupported")
            root_blob, root_stamp = _read(self.root, "root.json", 4096, installation, self.files)
            _need(root_blob.sha256 == installation.root_record_sha256, "conflict")
            parsed = _decode("root", root_blob.data, work)
            row = _plain(parsed.document)
            _need(
                row["deployment_id"] == str(installation.deployment_id)
                and row["store_id"] == str(installation.store_id)
                and row["artifact_domain"] == installation.artifact_domain
                and row["owner_uid"] == installation.owner_uid
                and row["owner_gid"] == installation.owner_gid
                and row["evidence_root"] == str(installation.evidence_root)
                and row["host_work_root"] == str(installation.host_work_root),
                "conflict",
            )
            self.census.put("root.json", root_stamp, aux=bytes(33) + root_blob.sha256)
            self.writer_lock = self.files.open(
                "writer.lock",
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                parent=self.root,
            )
            lock_stamp = _fstat(self.writer_lock, work)
            _regular(lock_stamp, installation, (0o600,))
            _need(lock_stamp.size == 0, "unsafe-path")
            if writer:
                work.call()
                fcntl.flock(self.writer_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.census.put("writer.lock", lock_stamp)
            _need(
                _names(self.root, work, 4) == ["attempts", "refusals", "root.json", "writer.lock"],
                "unsafe-path",
            )
            self.branches: dict[str, int] = {}
            count = 0
            for branch, kind in (("attempts", "attempt"), ("refusals", "refusal")):
                fd = _open_dir(self.root, branch, self.files)
                stamp = _fstat(fd, work)
                _directory(stamp, installation)
                self.branches[kind] = fd
                self.census.put(branch, stamp)
                for name in _names(fd, work, 256 - count):
                    _need(_UUID.fullmatch(name) is not None, "unsafe-path")
                    count += 1
                    _need(count <= 256, "limit")
                    key = _ScopeKey(cast(Literal["attempt", "refusal"], kind), UUID(name))
                    self._cold_scope(key, work)
            self.root_stamp = _fstat(self.root, work)
            self.work_stamp = _fstat(self.work, work)
            work.check()
            self.last_work = work
        except Exception as error:
            primary = _mapped(error)
            if primary is not error:
                primary.__cause__ = error
        except BaseException as error:
            primary = error
        if primary is not None:
            self.files.finish(primary)

    def _scope_files(
        self, key: _ScopeKey, files: _Descriptors, *, cold: bool = False
    ) -> _ScopeFiles:
        work = files.work
        prefix = _prefix(key)
        fd = _open_dir(self.branches[key.kind], str(key.id), files)
        stamp = _fstat(fd, work)
        _directory(stamp, self.installation)
        _stable(_member(self.branches[key.kind], str(key.id), work) == stamp)
        if not cold:
            _stable(stamp == self.census.get(prefix)[0])
        else:
            self.census.put(prefix, stamp)
        result: dict[str, int] = {}
        for name in ("staging", "blobs"):
            child = _open_dir(fd, name, files)
            stamp = _fstat(child, work)
            _directory(stamp, self.installation)
            _stable(_member(fd, name, work) == stamp)
            if not cold:
                _stable(stamp == self.census.get(prefix + "/" + name)[0])
            else:
                self.census.put(prefix + "/" + name, stamp)
            result[name] = child
        return _ScopeFiles(fd, result["staging"], result["blobs"])

    def _intent_names(self, key: _ScopeKey) -> list[str]:
        prefix = _prefix(key) + "/staging/"
        return [
            name[len(prefix) : -5]
            for name, _, aux in self.census.rows(prefix)
            if name.endswith(".json") and aux[0] in (1, 2, 3)
        ]

    def _intent_for(self, key: _ScopeKey, destination: str) -> UUID | None:
        found: UUID | None = None
        for identity in self._intent_names(key):
            _, aux = self.census.get(_prefix(key) + "/staging/" + identity + ".json")
            expected = (
                "blobs/" + aux[1:33].hex()
                if aux[0] == 1
                else ("manifest.json" if aux[0] == 2 else "refusal.json")
            )
            if expected == destination:
                _need(found is None, "conflict")
                found = UUID(identity)
        return found

    def _known_read(
        self,
        parent: int,
        name: str,
        path: str,
        maximum: int,
        files: _Descriptors,
        *,
        links: tuple[int, ...] = (1,),
    ) -> tuple[EvidenceBlob, _FileStamp]:
        expected, aux = self.census.get(path)
        data, stamp = _read(
            parent, name, maximum, self.installation, files, links=links, expected=expected
        )
        _stable(stamp == expected and data.sha256 == aux[33:65])
        return data, stamp

    def _read_intent(
        self, key: _PublicationKey, sf: _ScopeFiles, files: _Descriptors
    ) -> ParsedJournalRecord:
        name = str(key.publication_id) + ".json"
        raw, _ = self._known_read(
            sf.staging, name, _prefix(key.scope) + "/staging/" + name, 4096, files
        )
        record = _decode("publication-intent", raw.data, files.work)
        _intent_check(record, key, self.installation)
        return record

    def _load_plan(self, key: _ScopeKey, sf: _ScopeFiles, files: _Descriptors) -> _Plan:
        destination = "manifest.json" if key.kind == "attempt" else "refusal.json"
        identity = self._intent_for(key, destination)
        _need(identity is not None, "conflict")
        assert identity is not None
        intent = self._read_intent(_PublicationKey(key, identity), sf, files)
        row = _plain(intent.document)
        final_path = _prefix(key) + "/" + destination
        staged_name = str(identity) + ".data"
        if self.census._offset(final_path) is not None:
            parent, name, path = sf.directory, destination, final_path
        else:
            parent, name, path = sf.staging, staged_name, _prefix(key) + "/staging/" + staged_name
        raw, _ = self._known_read(parent, name, path, 16384, files, links=(1, 2))
        _need(len(raw.data) == row["size"] and raw.sha256.hex() == row["sha256"], "conflict")
        record = _decode("manifest" if key.kind == "attempt" else "refusal", raw.data, files.work)
        plan = _Plan(key, identity, record, self.installation)
        if key.kind == "attempt":
            for field in ("initial_prerequisite", "authority_inventory"):
                checksum = plan.row[field]["sha256"]
                member_path = _prefix(key) + "/blobs/" + checksum
                if self.census._offset(member_path) is not None:
                    # A cold-verified stage/final pair may still need its exact
                    # owned unlink/sync recovery. Parsing its immutable bytes
                    # does not grant completed credit or parent finalization.
                    member, _ = self._known_read(
                        sf.blobs, checksum, member_path, 16384, files, links=(1, 2)
                    )
                    plan.observe(checksum, member.data, files.work)
        return plan

    def _cold_scope(self, key: _ScopeKey, work: _Work) -> None:
        prefix = _prefix(key)
        with _owned(work) as files:
            sf = self._scope_files(key, files, cold=True)
            allowed = {
                "staging",
                "blobs",
                "manifest.json" if key.kind == "attempt" else "refusal.json",
            }
            if key.kind == "attempt":
                allowed.update(("events", "spool-registrations"))
            _need(set(_names(sf.directory, work, 5)) <= allowed, "unsafe-path")
            if key.kind == "attempt":
                for extra in ("events", "spool-registrations"):
                    directory = _open_dir(sf.directory, extra, files)
                    stamp = _fstat(directory, work)
                    _directory(stamp, self.installation)
                    _need(_names(directory, work, 0) == [], "unsupported")
                    self.census.put(prefix + "/" + extra, stamp)
                    files.close(directory)
            staging = _names(sf.staging, work, 33)
            intent_rows: dict[str, tuple[ParsedJournalRecord, dict[str, Any]]] = {}
            destinations: set[str] = set()
            parents: list[str] = []
            for name in staging:
                suffix = name[-5:]
                _need(
                    suffix in (".json", ".data") and _UUID.fullmatch(name[:-5]) is not None,
                    "unsafe-path",
                )
                if suffix != ".json":
                    continue
                identity = name[:-5]
                raw, stamp = _read(
                    sf.staging, name, 4096, self.installation, files, sync=self.writer
                )
                record = _decode("publication-intent", raw.data, work)
                row = _intent_check(record, _PublicationKey(key, UUID(identity)), self.installation)
                _need(row["destination"] not in destinations, "conflict")
                destinations.add(row["destination"])
                intent_rows[identity] = record, row
                role = {"blob": 1, "manifest": 2, "refusal": 3}[row["role"]]
                self.census.put(
                    prefix + "/staging/" + name,
                    stamp,
                    aux=bytes((role,)) + bytes.fromhex(row["sha256"]) + raw.sha256,
                )
                if role != 1:
                    parents.append(identity)
            _need(len(parents) == 1, "conflict")
            _need(all(name[:-5] in intent_rows for name in staging), "conflict")
            blob_names = _names(sf.blobs, work, 16)
            _need(all(_HEX.fullmatch(name) is not None for name in blob_names), "unsafe-path")
            expected_names = {
                row["destination"][6:] for _, row in intent_rows.values() if row["role"] == "blob"
            }
            _need(set(blob_names) <= expected_names, "conflict")
            completed: dict[str, int] = {}
            unresolved = 0
            retained = 0
            pending = parents + [identity for identity in intent_rows if identity not in parents]
            parent_plan: _Plan | None = None
            while pending:
                identity = pending.pop(0)
                record, row = intent_rows[identity]
                destination = row["destination"]
                final_fd, final_name = (
                    (sf.blobs, destination[6:])
                    if row["role"] == "blob"
                    else (sf.directory, destination)
                )
                data_name = identity + ".data"
                final_exists = (
                    final_name in blob_names
                    if row["role"] == "blob"
                    else (destination in _names(sf.directory, work, 5))
                )
                data_exists = data_name in staging
                _need(final_exists or data_exists, "conflict")
                parent = final_fd if final_exists else sf.staging
                name = final_name if final_exists else data_name
                path = (
                    prefix + "/" + destination if final_exists else prefix + "/staging/" + data_name
                )
                modes = (0o400,) if final_exists or row["role"] != "blob" else (0o400, 0o600)
                raw, stamp = _read(
                    parent,
                    name,
                    row["size"],
                    self.installation,
                    files,
                    modes=modes,
                    links=(1, 2),
                    sync=self.writer,
                )
                exact = len(raw.data) == row["size"] and raw.sha256.hex() == row["sha256"]
                if final_exists or row["role"] != "blob":
                    _need(exact and stat.S_IMODE(stamp.full_mode) == 0o400, "conflict")
                if final_exists and data_exists:
                    other = _member(sf.staging, data_name, work)
                    _need(other == stamp and stamp.nlink == 2, "conflict")
                    self.census.put(
                        prefix + "/staging/" + data_name, stamp, aux=bytes(33) + raw.sha256
                    )
                else:
                    _need(stamp.nlink == 1, "unsafe-path")
                self.census.put(path, stamp, aux=bytes(33) + raw.sha256)
                retained += len(raw.data) + len(record.data)
                _need(retained <= 32 * _MIB, "limit")
                if final_exists and not data_exists:
                    completed[identity] = len(record.data)
                else:
                    unresolved += 1
                if row["role"] != "blob":
                    parent_record = _decode(
                        "manifest" if key.kind == "attempt" else "refusal", raw.data, work
                    )
                    parent_plan = _Plan(key, UUID(identity), parent_record, self.installation)
                    if key.kind == "attempt":
                        priority = (
                            parent_plan.row["initial_prerequisite"]["sha256"],
                            parent_plan.row["authority_inventory"]["sha256"],
                        )
                        pending.sort(
                            key=lambda item: (
                                priority.index(intent_rows[item][1]["sha256"])
                                if intent_rows[item][1]["sha256"] in priority
                                else 2,
                                item,
                            )
                        )
                elif exact and parent_plan is not None and key.kind == "attempt":
                    if row["sha256"] in (
                        parent_plan.row["initial_prerequisite"]["sha256"],
                        parent_plan.row["authority_inventory"]["sha256"],
                    ):
                        _need(len(raw.data) <= 16384, "limit")
                        parent_plan.observe(row["sha256"], raw.data, work)
            assert parent_plan is not None
            for _, row in intent_rows.values():
                if row["role"] == "blob":
                    candidates = [
                        ref for ref in parent_plan.refs.values() if ref.checksum == row["sha256"]
                    ]
                    _need(
                        bool(candidates) and all(ref.size == row["size"] for ref in candidates),
                        "conflict",
                    )
            parent_plan.quota(completed, unresolved=unresolved)
            self.totals[key] = _Totals()
            _need(len(intent_rows) <= parent_plan.maximum, "limit")
            for fd, name in (
                (sf.directory, prefix),
                (sf.staging, prefix + "/staging"),
                (sf.blobs, prefix + "/blobs"),
            ):
                if self.writer:
                    _sync(fd, work)
                _need(_fstat(fd, work) == self.census.get(name)[0], "conflict")

    @contextmanager
    def operation(
        self, key: _ScopeKey, *, refusal_final: bool = False
    ) -> Iterator[tuple[_Work, _Descriptors]]:
        _need(self.lock.acquire(blocking=False), "conflict")
        previous_active = self.active
        work: _Work | None = None
        try:
            _need(not self.closed and not self.invalidated, "conflict")
            _need(key in self.totals or len(self.totals) < 256, "limit")
            work = _Work(totals=self.totals.setdefault(key, _Totals()), refusal_final=refusal_final)
            self.census.work = work
            work.fd_count = len(self.files.owned)
            self.last_work = work
            with _owned(work) as files:
                for path, expected in (
                    (self.installation.evidence_root, self.root_chain),
                    (self.installation.host_work_root, self.work_chain),
                ):
                    fd, chain = _walk(path, self.installation, files)
                    _stable(chain == expected)
                    files.close(fd)
                _stable(
                    _fstat(self.root, work) == self.root_stamp
                    and _fstat(self.work, work) == self.work_stamp
                )
                for name in ("root.json", "writer.lock"):
                    _stable(_member(self.root, name, work) == self.census.get(name)[0])
                branch = "attempts" if key.kind == "attempt" else "refusals"
                _stable(_fstat(self.branches[key.kind], work) == self.census.get(branch)[0])
                yield work, files
                work.check()
            work.check()
        except BaseException as error:
            # A failed begin must not expose an unreturned private handle.
            # This restores only volatile lifetime state, never storage or work.
            self.active = previous_active
            if work is not None and (
                work.effects_started
                or work.cleanup_uncertain
                or isinstance(error, (_StoredStateChangedError, OSError))
                or (
                    type(error) is RuntimePublicationError
                    and error.reason in ("unsafe-path", "storage", "cleanup-incomplete")
                )
            ):
                self.invalidated = True
            if isinstance(error, Exception):
                mapped = _mapped(error)
                if mapped is not error:
                    raise mapped from error
            raise
        finally:
            self.lock.release()

    def close(self) -> None:
        _need(self.lock.acquire(blocking=False), "conflict")
        try:
            if self.closed:
                return
            self.closed = True
            self.files.work = _Work()
            self.files.work.fd_count = len(self.files.owned)
            self.files.finish()
        finally:
            self.lock.release()

    def _refresh(self, key: _ScopeKey, sf: _ScopeFiles, work: _Work) -> None:
        prefix = _prefix(key)
        for fd, name in (
            (sf.directory, prefix),
            (sf.staging, prefix + "/staging"),
            (sf.blobs, prefix + "/blobs"),
        ):
            stamp = _fstat(fd, work)
            parent, member = (
                (self.branches[key.kind], str(key.id))
                if fd == sf.directory
                else (sf.directory, "staging" if fd == sf.staging else "blobs")
            )
            _need(_member(parent, member, work) == stamp, "conflict")
            self.census.put(name, stamp)

    def _completed(self, key: _ScopeKey) -> tuple[dict[str, int], int]:
        completed: dict[str, int] = {}
        unresolved = 0
        for identity in self._intent_names(key):
            stamp, aux = self.census.get(_prefix(key) + "/staging/" + identity + ".json")
            destination = (
                "blobs/" + aux[1:33].hex()
                if aux[0] == 1
                else ("manifest.json" if aux[0] == 2 else "refusal.json")
            )
            final = self.census._offset(_prefix(key) + "/" + destination)
            staged = self.census._offset(_prefix(key) + "/staging/" + identity + ".data")
            if final is not None and staged is None:
                completed[identity] = stamp.size
            else:
                unresolved += 1
        return completed, unresolved

    def _new_scope(self, key: _ScopeKey, files: _Descriptors) -> _ScopeFiles:
        work = files.work
        branch = self.branches[key.kind]
        work.call()
        work.effects_started = True
        os.mkdir(str(key.id), mode=0o700, dir_fd=branch)
        directory = _open_dir(branch, str(key.id), files)
        _directory(_fstat(directory, work), self.installation)
        names = (
            ("staging", "blobs", "events", "spool-registrations")
            if key.kind == "attempt"
            else ("staging", "blobs")
        )
        result: dict[str, int] = {}
        for name in names:
            work.call()
            os.mkdir(name, mode=0o700, dir_fd=directory)
            child = _open_dir(directory, name, files)
            stamp = _fstat(child, work)
            _directory(stamp, self.installation)
            self.census.put(_prefix(key) + "/" + name, stamp)
            _sync(child, work)
            if name in ("staging", "blobs"):
                result[name] = child
            else:
                files.close(child)
        _sync(directory, work)
        _sync(branch, work)
        self.census.put(_prefix(key), _fstat(directory, work))
        self.census.put("attempts" if key.kind == "attempt" else "refusals", _fstat(branch, work))
        return _ScopeFiles(directory, result["staging"], result["blobs"])

    def _stage(
        self,
        key: _PublicationKey,
        sf: _ScopeFiles,
        destination: str,
        blob: EvidenceBlob,
        files: _Descriptors,
    ) -> ParsedJournalRecord:
        role = "blob" if destination.startswith("blobs/") else destination[:-5]
        data = _encode_intent(
            _intent_document(key, self.installation.store_id, role, destination, blob), files.work
        )
        name = str(key.publication_id)
        _need(
            self.census._offset(_prefix(key.scope) + "/staging/" + name + ".json") is None,
            "conflict",
        )
        _write(sf.staging, name + ".json", data, self.installation, files)
        intent_blob, intent_stamp = _read(
            sf.staging, name + ".json", 4096, self.installation, files
        )
        _need(intent_blob.data == data, "conflict")
        parsed = _decode("publication-intent", intent_blob.data, files.work)
        _intent_check(parsed, key, self.installation)
        self.census.put(
            _prefix(key.scope) + "/staging/" + name + ".json",
            intent_stamp,
            aux=bytes(({"blob": 1, "manifest": 2, "refusal": 3}[role],))
            + blob.sha256
            + intent_blob.sha256,
        )
        _write(sf.staging, name + ".data", blob.data, self.installation, files)
        readback, stamp = _read(
            sf.staging, name + ".data", len(blob.data), self.installation, files
        )
        _need(readback.data == blob.data and readback.sha256 == blob.sha256, "conflict")
        self.census.put(
            _prefix(key.scope) + "/staging/" + name + ".data",
            stamp,
            aux=bytes(33) + readback.sha256,
        )
        self._refresh(key.scope, sf, files.work)
        return parsed

    def _visible(
        self,
        key: _PublicationKey,
        sf: _ScopeFiles,
        files: _Descriptors,
        intent: ParsedJournalRecord | None = None,
    ) -> VisiblePublication:
        if intent is None:
            intent = self._read_intent(key, sf, files)
        row = _intent_check(intent, key, self.installation)
        destination = row["destination"]
        parent, name = (
            (sf.blobs, destination[6:]) if row["role"] == "blob" else (sf.directory, destination)
        )
        raw, stamp = self._known_read(
            parent, name, _prefix(key.scope) + "/" + destination, row["size"], files
        )
        _need(len(raw.data) == row["size"] and raw.sha256.hex() == row["sha256"], "conflict")
        record = (
            None
            if row["role"] == "blob"
            else _decode(cast(JournalRecordKind, row["role"]), raw.data, files.work)
        )
        # Output wrappers must not expose an alias to the held scope's UUIDs.
        return VisiblePublication("verified-visible-file", _key(key), intent, raw, record, stamp)

    def _publish(
        self,
        key: _PublicationKey,
        sf: _ScopeFiles,
        files: _Descriptors,
        intent: ParsedJournalRecord,
    ) -> _PublicationAck:
        work = files.work
        row = _intent_check(intent, key, self.installation)
        destination = row["destination"]
        data_name = str(key.publication_id) + ".data"
        stage_path = _prefix(key.scope) + "/staging/" + data_name
        final_path = _prefix(key.scope) + "/" + destination
        parent, name = (
            (sf.blobs, destination[6:]) if row["role"] == "blob" else (sf.directory, destination)
        )
        existed = self.census._offset(final_path) is not None
        if self.census._offset(stage_path) is not None:
            raw, before = self._known_read(
                sf.staging, data_name, stage_path, row["size"], files, links=(1, 2)
            )
            _need(len(raw.data) == row["size"] and raw.sha256.hex() == row["sha256"], "conflict")
            fd = files.open(
                data_name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                parent=sf.staging,
            )
            _need(_fstat(fd, work) == before, "conflict")
            if not existed:
                work.call()
                work.effects_started = True
                os.link(
                    data_name, name, src_dir_fd=sf.staging, dst_dir_fd=parent, follow_symlinks=False
                )
            linked = _fstat(fd, work)
            _regular(linked, self.installation, links=(2,))
            _need(
                _member(sf.staging, data_name, work) == linked
                and _member(parent, name, work) == linked,
                "conflict",
            )
            work.call()
            work.effects_started = True
            os.unlink(data_name, dir_fd=sf.staging)
            _sync(fd, work)
            _sync(parent, work)
            _sync(sf.staging, work)
            final = _fstat(fd, work)
            _regular(final, self.installation)
            _need(_member(parent, name, work) == final, "conflict")
            self.census.remove(stage_path)
            self.census.put(final_path, final, aux=bytes(33) + raw.sha256)
            files.close(fd)
        else:
            _need(existed, "conflict")
            fd = files.open(
                name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, parent=parent
            )
            _need(_fstat(fd, work) == self.census.get(final_path)[0], "conflict")
            _sync(fd, work)
            _sync(parent, work)
            files.close(fd)
        intent_name = str(key.publication_id) + ".json"
        fd = files.open(
            intent_name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
            parent=sf.staging,
        )
        _need(
            _fstat(fd, work) == self.census.get(_prefix(key.scope) + "/staging/" + intent_name)[0],
            "conflict",
        )
        _sync(fd, work)
        _sync(sf.staging, work)
        files.close(fd)
        self._refresh(key.scope, sf, work)
        visible = self._visible(key, sf, files, intent)
        return _PublicationAck(
            "local-fsync-readback", visible, "exact-recovery" if existed else "new"
        )

    def _closure(self, plan: _Plan, sf: _ScopeFiles, files: _Descriptors) -> None:
        work = files.work
        if plan.key.kind == "attempt":
            _need(plan.prerequisite is not None and plan.inventory is not None, "conflict")
        matches = 0
        primary_size = None
        seen: set[str] = set()
        for reference in plan.refs.values():
            checksum = reference.checksum
            if checksum in seen:
                continue
            seen.add(checksum)
            identity = self._intent_for(plan.key, "blobs/" + checksum)
            _need(identity is not None, "conflict")
            assert identity is not None
            # The cold owner-validated intent is consumed again as exact raw
            # bytes under its held digest, not decoded once per unrelated role.
            intent_name = str(identity) + ".json"
            self._known_read(
                sf.staging, intent_name, _prefix(plan.key) + "/staging/" + intent_name, 4096, files
            )
            raw, _ = self._known_read(
                sf.blobs, checksum, _prefix(plan.key) + "/blobs/" + checksum, reference.size, files
            )
            _need(len(raw.data) == reference.size, "conflict")
            if (
                plan.key.kind == "refusal"
                and plan.row["primary_error_id"] is not None
                and len(raw.data) <= 8192
            ):
                work.charge("owner_calls", 1)
                work.charge("copies", 2 * _MIB)
                with work.allocation(slots=32768):
                    try:
                        graph = decode_error_graph(raw.data)
                    except ProcessEvidenceError:
                        continue
                    if _plain(graph)["error_id"] == plan.row["primary_error_id"]:
                        matches += 1
                        primary_size = len(raw.data)
        if plan.key.kind == "refusal" and plan.row["primary_error_id"] is not None:
            _need(matches == 1, "conflict")
        completed, unresolved = self._completed(plan.key)
        plan.quota(completed, unresolved=unresolved, primary_size=primary_size)


class _DiagnosticPublisher:
    def __init__(self, core: _Core) -> None:
        self._core = core

    def begin_manifest(self, key: _ScopeKey, publication_id: UUID, data: bytes) -> _PlannedScope:
        return self._begin(_scope(key), _uuid(publication_id), data, "attempt")

    def begin_refusal(self, key: _ScopeKey, publication_id: UUID, data: bytes) -> _PlannedScope:
        return self._begin(_scope(key), _uuid(publication_id), data, "refusal")

    def _begin(self, key: _ScopeKey, publication_id: UUID, data: bytes, kind: str) -> _PlannedScope:
        _need(key.kind == kind and type(data) is bytes and 0 < len(data) <= 16384)
        core = self._core
        _need(core.active is None, "conflict")
        result: _PlannedScope | None = None
        with core.operation(key) as (work, files):
            _need(core.active is None, "conflict")
            parsed = _decode("manifest" if kind == "attempt" else "refusal", data, work)
            plan = _Plan(key, publication_id, parsed, core.installation)
            prefix = _prefix(key)
            if core.census._offset(prefix) is None:
                sf = core._new_scope(key, files)
                core._stage(
                    _PublicationKey(key, publication_id),
                    sf,
                    plan.parent_name,
                    EvidenceBlob(data, parsed.sha256),
                    files,
                )
            else:
                sf = core._scope_files(key, files)
                existing = core._load_plan(key, sf, files)
                _need(
                    existing.publication_id == publication_id and existing.record.data == data,
                    "conflict",
                )
            result = _PlannedScope(core, key, publication_id)
            core.active = result
        assert result is not None
        return result

    def recover_publication(self, key: _PublicationKey) -> _PublicationAck:
        frozen = _key(key)
        core = self._core
        with core.operation(frozen.scope, refusal_final=frozen.scope.kind == "refusal") as (
            _,
            files,
        ):
            sf = core._scope_files(frozen.scope, files)
            plan = core._load_plan(frozen.scope, sf, files)
            intent = core._read_intent(frozen, sf, files)
            row = _plain(intent.document)
            if row["role"] == "blob":
                _need(
                    any(
                        ref.checksum == row["sha256"] and ref.size == row["size"]
                        for ref in plan.refs.values()
                    ),
                    "conflict",
                )
            else:
                _need(frozen.publication_id == plan.publication_id, "conflict")
                core._closure(plan, sf, files)
            result = core._publish(frozen, sf, files, intent)
        return result

    def close(self) -> None:
        self._core.close()


class _PlannedScope:
    def __init__(self, core: _Core, key: _ScopeKey, publication_id: UUID) -> None:
        self._core = core
        self._key = key
        self._publication_id = publication_id
        self._closed = False

    def _check(self) -> None:
        _need(not self._closed and self._core.active is self, "conflict")

    def publish_member(
        self, publication_id: UUID, selector: MemberSelector, blob: EvidenceBlob
    ) -> _PublicationAck:
        self._check()
        identity, selected = _uuid(publication_id), _selector(selector)
        _need(type(blob) is EvidenceBlob)
        data = _field(blob, "data")
        supplied_hash = _field(blob, "sha256")
        _need(type(data) is bytes and len(data) <= 8 * _MIB, "limit")
        checksum = _hash_value(supplied_hash)
        core, key = self._core, self._key
        with core.operation(key) as (work, files):
            self._check()
            sf = core._scope_files(key, files)
            plan = core._load_plan(key, sf, files)
            reference = plan.resolve(selected)
            _need(len(data) == reference.size and checksum.hex() == reference.checksum, "conflict")
            _need(_digest(data, work) == checksum, "conflict")
            destination = "blobs/" + reference.checksum
            prior = core._intent_for(key, destination)
            publication = _PublicationKey(key, identity)
            completed, unresolved = core._completed(key)
            plan.quota(completed, unresolved=unresolved)
            if prior is None:
                _need(unresolved < 16 and len(core._intent_names(key)) < plan.maximum, "limit")
                intent = core._stage(
                    publication, sf, destination, EvidenceBlob(data, checksum), files
                )
            else:
                _need(identity == prior, "conflict")
                intent = core._read_intent(publication, sf, files)
            result = core._publish(publication, sf, files, intent)
        return result

    def finalize(self) -> _PublicationAck:
        self._check()
        core = self._core
        with core.operation(self._key, refusal_final=self._key.kind == "refusal") as (_, files):
            self._check()
            sf = core._scope_files(self._key, files)
            plan = core._load_plan(self._key, sf, files)
            _need(plan.publication_id == self._publication_id, "conflict")
            core._closure(plan, sf, files)
            key = _PublicationKey(self._key, self._publication_id)
            intent = core._read_intent(key, sf, files)
            result = core._publish(key, sf, files, intent)
        return result

    def close(self) -> None:
        if self._closed:
            return
        core = self._core
        _need(core.lock.acquire(blocking=False), "conflict")
        try:
            self._closed = True
            if core.active is self:
                core.active = None
        finally:
            core.lock.release()


class RuntimePublicationReader:
    def __init__(self, core: _Core) -> None:
        self._core = core

    def read_publication(self, key: _PublicationKey) -> VisiblePublication:
        frozen = _key(key)
        core = self._core
        with core.operation(frozen.scope) as (_, files):
            sf = core._scope_files(frozen.scope, files)
            plan = core._load_plan(frozen.scope, sf, files)
            intent = core._read_intent(frozen, sf, files)
            row = _plain(intent.document)
            if row["role"] == "blob":
                _need(
                    any(
                        ref.checksum == row["sha256"] and ref.size == row["size"]
                        for ref in plan.refs.values()
                    ),
                    "conflict",
                )
            else:
                _need(frozen.publication_id == plan.publication_id, "conflict")
            result = core._visible(frozen, sf, files, intent)
        return result

    def close(self) -> None:
        self._core.close()


def _open_diagnostic_publisher(installation: RuntimeEvidenceInstallation) -> _DiagnosticPublisher:
    return _DiagnosticPublisher(_Core(_installation(installation), writer=True))


def open_runtime_publication_reader(
    installation: RuntimeEvidenceInstallation,
) -> RuntimePublicationReader:
    return RuntimePublicationReader(_Core(_installation(installation), writer=False))
