"""Bounded structural validation of supplied journal bytes, not a durable store.

No filesystem, clock, process, authority reader or admission operation exists
here. Opaque owning-domain obligations remain explicit in every replay report.
See docs/bhmea/RUNTIME-EVIDENCE-STORE.md section 16.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, TypeAlias, cast

from tools.worker.bounded_process import FrozenInvocation
from tools.worker.process_evidence import (
    EvidenceBlob,
    ProcessEvidenceError,
    RuntimeCallBinding,
    StoredCallIntent,
    StoredCallResult,
    StoredObject,
    StoredValue,
    cli_operation_from_wire,
    decode_call_intent,
    decode_call_ref,
    decode_call_result,
    decode_error_graph,
    decode_invocation,
    prepare_call_intent,
)

JournalRecordKind: TypeAlias = Literal[
    "root",
    "manifest",
    "event",
    "refusal",
    "authority-inventory",
    "prerequisite",
    "spool-registration",
    "spool-observation",
    "publication-intent",
]
DeclaredPhase: TypeAlias = Literal[
    "reserved",
    "loaded",
    "created",
    "start-intended",
    "started",
    "observed",
    "release-intended",
    "released",
    "domain-exited",
    "cleanup",
    "failed",
    "admitted",
    "orphaned",
    "reconciled",
]
OwnerRole: TypeAlias = Literal[
    "installation",
    "controller-profile",
    "domain-profile",
    "runtime-inventory",
    "mode-request",
    "mode-input",
    "launch-packet",
    "release-packet",
    "domain-result",
    "authentication",
    "scope",
    "admission",
    "execution-authorization",
    "capture-lease",
    "content-verification",
    "parent-barrier",
    "kernel-raw",
    "refusal-raw",
]

_MIB = 1048576
_MAX = 2**63 - 1
_MIN = -(2**63)
_EMPTY = hashlib.sha256(b"").hexdigest()
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_UUID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z\Z")
_MODES = ("verifier-publication", "verifier-historical", "verifier-execution", "python-syntax")
_ACTIONS = ("publish-builtin-preflight", "audit-historical", "verify-execution", "parse-python")
_AUTH = (
    "authentication",
    "scope",
    "admission",
    "execution-authorization",
    "capture-lease",
    "content-verification",
)
_OWNERS = (
    "installation",
    "controller-profile",
    "domain-profile",
    "runtime-inventory",
    "mode-request",
    "mode-input",
    "launch-packet",
    "release-packet",
    "domain-result",
    *_AUTH,
    "parent-barrier",
    "kernel-raw",
    "refusal-raw",
)
_META = ("installation", "controller-profile", "domain-profile", "inventory")
_PHASES = tuple(
    "load authority reserve create inspect start release execute retain cleanup admit "
    "recover".split()
)
_FAILURES = tuple(
    (
        "installation-unavailable metadata-invalid artifact-mismatch unsafe-path limit deadline "
        "authority-unavailable authority-stale image-unavailable config-mismatch "
        "kernel-unavailable "
        "kernel-mismatch spawn-failed transport-failed protocol-invalid domain-rejected "
        "evidence-failed "
        "cleanup-incomplete ambiguous-create ambiguous-start ambiguous-release cancelled "
        "unsupported"
    ).split()
)
_SCHEMAS = {
    "root": ("scanipy-runtime-evidence-root/1",),
    "manifest": ("scanipy-runtime-attempt-manifest/1",),
    "event": ("scanipy-local-runtime-event/1", "scanipy-diagnostic-runtime-event/1"),
    "refusal": ("scanipy-local-runtime-refusal/1",),
    "authority-inventory": ("scanipy-runtime-prerequisite-evidence/1",),
    "prerequisite": ("scanipy-local-launch-prerequisite/1",),
    "spool-registration": ("scanipy-runtime-spool-registration/1",),
    "spool-observation": ("scanipy-runtime-spool-observation/1",),
    "publication-intent": ("scanipy-runtime-publication-intent/1",),
}
_LIMITS = {
    "root": (4096, 2, 32),
    "manifest": (16384, 6, 256),
    "event": (65536, 16, 4096),
    "refusal": (16384, 6, 256),
    "authority-inventory": (16384, 6, 256),
    "prerequisite": (16384, 16, 1024),
    "spool-registration": (4096, 4, 96),
    "spool-observation": (4096, 5, 128),
    "publication-intent": (4096, 3, 64),
}
_QUOTA = {
    "retained_bytes": 33554432,
    "metadata_bytes": 524288,
    "nonattached_output_bytes": 4194304,
    "kernel_bytes": 1048576,
    "cli_calls": 16,
    "kernel_samples": 16,
    "cleanup_cli_slots": 4,
    "cleanup_metadata_bytes": 131072,
    "cleanup_retained_bytes": 2097152,
    "terminal_metadata_bytes": 65536,
}


class JournalValidationError(ValueError):
    """Fixed private reason; no supplied evidence is formatted into the message."""

    def __init__(self, reason: str) -> None:
        if type(reason) is not str or reason not in (
            "invalid-type",
            "limit",
            "noncanonical",
            "schema",
            "reference",
            "order",
            "conflict",
        ):
            reason = "schema"
        self.reason = reason
        super().__init__(reason)


def _need(ok: bool, reason: str = "schema") -> None:
    if not ok:
        raise JournalValidationError(reason)


@dataclass(frozen=True, slots=True, repr=False)
class ParsedJournalRecord:
    validation: Literal["local-structure-only"]
    kind: JournalRecordKind
    schema: str
    data: bytes
    sha256: bytes
    schema_digest: bytes
    document: StoredObject


@dataclass(frozen=True, slots=True, repr=False)
class ReplayedCall:
    intent_event_sequence: int
    result_event_sequence: int | None
    intent: StoredCallIntent
    result: StoredCallResult | None


@dataclass(frozen=True, slots=True, repr=False)
class OpaqueOwnerValue:
    role: OwnerRole
    containing_sha256: bytes
    field_path: tuple[str | int, ...]


@dataclass(frozen=True, slots=True, repr=False)
class StructuralAccounting:
    supplied_blob_bytes: int
    supplied_record_bytes: int
    logical_metadata_bytes: int
    call_count: int
    kernel_sample_count: int
    nonattached_observed_bytes: int
    nonattached_known_retained_bytes: int
    nonattached_missing_outcome_count: int
    nonattached_missing_output_count: int
    nonattached_unknown_retention_count: int
    kernel_raw_bytes: int


@dataclass(frozen=True, slots=True, repr=False)
class JournalStructureReport:
    validation: Literal["local-structure-only"]
    manifest: ParsedJournalRecord
    events: tuple[ParsedJournalRecord, ...]
    declared_phase: DeclaredPhase
    recovery_only_recorded: bool
    ever_orphaned_recorded: bool
    calls: tuple[ReplayedCall, ...]
    blobs: tuple[EvidenceBlob, ...]
    opaque_owner_values: tuple[OpaqueOwnerValue, ...]
    accounting: StructuralAccounting


@dataclass(frozen=True, slots=True, repr=False)
class RefusalStructureReport:
    validation: Literal["local-structure-only"]
    refusal: ParsedJournalRecord
    blobs: tuple[EvidenceBlob, ...]
    opaque_owner_values: tuple[OpaqueOwnerValue, ...]


def _bytes(value: object, cap: int) -> bytes:
    _need(type(value) is bytes, "invalid-type")
    data = cast(bytes, value)
    _need(len(data) <= cap, "limit")
    return data


def _text(value: object, cap: int = 4096, *, empty: bool = False) -> str:
    _need(type(value) is str, "invalid-type")
    text = cast(str, value)
    _need(len(text) <= cap, "limit")
    _need((empty or bool(text)) and "\0" not in text)
    try:
        _need(len(text.encode("utf-8")) <= cap, "limit")
    except UnicodeError as error:
        raise JournalValidationError("schema") from error
    return text


def _int(value: object, low: int = 0, high: int = _MAX) -> int:
    _need(type(value) is int, "invalid-type")
    number = cast(int, value)
    _need(low <= number <= high)
    return number


def _bool(value: object) -> bool:
    _need(type(value) is bool, "invalid-type")
    return cast(bool, value)


def _choice(value: object, choices: tuple[str, ...]) -> str:
    text = _text(value, 128)
    _need(text in choices)
    return text


def _hex(value: object) -> str:
    text = _text(value, 64)
    _need(_HEX.fullmatch(text) is not None)
    return text


def _uuid(value: object) -> str:
    text = _text(value, 36)
    _need(_UUID.fullmatch(text) is not None)
    return text


def _id(value: object) -> str:
    text = _text(value, 128)
    _need(_ID.fullmatch(text) is not None)
    return text


def _image(value: object) -> str:
    text = _text(value, 71)
    _need(text.startswith("sha256:"))
    _hex(text[7:])
    return text


def _path(value: object) -> str:
    text = _text(value)
    _need(text.startswith("/") and text != "/" and "\\" not in text)
    _need(all(ord(c) >= 32 and not 127 <= ord(c) <= 159 for c in text))
    _need(all(part not in ("", ".", "..") for part in text.split("/")[1:]))
    return text


def _utc(value: object) -> datetime:
    text = _text(value, 27)
    _need(_UTC.fullmatch(text) is not None)
    try:
        return datetime.fromisoformat(text[:-1])
    except ValueError as error:
        raise JournalValidationError("schema") from error


def _keys(value: Any, fields: str) -> dict[str, Any]:  # noqa: ANN401
    _need(type(value) is dict, "invalid-type")
    names = fields.split()
    _need(len(value) == len(names) and set(value) == set(names))
    return cast(dict[str, Any], value)


def _list(value: Any, cap: int, minimum: int = 0) -> list[Any]:  # noqa: ANN401
    _need(type(value) is list, "invalid-type")
    _need(minimum <= len(value) <= cap, "limit")
    return cast(list[Any], value)


def _tuple(value: object, cap: int) -> tuple[Any, ...]:
    _need(type(value) is tuple, "invalid-type")
    values = cast(tuple[Any, ...], value)
    _need(len(values) <= cap, "limit")
    return values


def _size_text(value: str) -> int:
    return (
        2
        + len(value.encode())
        + sum(
            1 if c in ('"', "\\", "\b", "\f", "\n", "\r", "\t") else 5 if ord(c) < 32 else 0
            for c in value
        )
    )


class _PrimitiveBudget:
    def __init__(self, limits: tuple[int, int, int]) -> None:
        self.bytes, self.depth, self.values = limits

    def take(self, size: int = 0, values: int = 0) -> None:
        self.bytes -= size
        self.values -= values
        _need(self.bytes >= 0 and self.values >= 0, "limit")


def _plain(value: StoredValue, budget: _PrimitiveBudget, depth: int = 0) -> Any:  # noqa: ANN401
    budget.take(values=1)
    if value is None or type(value) is bool:
        budget.take(4 if value is None or value is True else 5)
        return value
    if type(value) is int:
        number = _int(value, _MIN)
        budget.take(len(str(number)))
        return number
    if type(value) is str:
        text = _text(value, budget.bytes, empty=True)
        budget.take(_size_text(text))
        return text
    pair = _tuple(value, 2)
    _need(len(pair) == 2 and type(pair[0]) is str)
    _need(depth < budget.depth, "limit")
    members = _tuple(pair[1], budget.values)
    budget.take(2 + max(0, len(members) - 1))
    if pair[0] == "array":
        return [_plain(item, budget, depth + 1) for item in members]
    _need(pair[0] == "object")
    _need(2 * len(members) <= budget.values, "limit")
    result: dict[str, Any] = {}
    previous: str | None = None
    for member in members:
        entry = _tuple(member, 2)
        _need(len(entry) == 2)
        key = _text(entry[0], budget.bytes, empty=True)
        _need(previous is None or previous < key, "noncanonical")
        previous = key
        budget.take(_size_text(key) + 1, 1)
        result[key] = _plain(entry[1], budget, depth + 1)
    return result


def _freeze(value: Any) -> StoredValue:  # noqa: ANN401
    if type(value) is dict:
        return ("object", tuple((key, _freeze(item)) for key, item in sorted(value.items())))
    if type(value) is list:
        return ("array", tuple(_freeze(item) for item in value))
    return cast(StoredValue, value)


def _json(value: Any) -> bytes:  # noqa: ANN401
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _lexical(data: bytes, limits: tuple[int, int, int]) -> None:
    _bytes(data, limits[0])
    depth = count = index = 0
    while index < len(data):
        byte = data[index]
        if byte in (123, 91):
            depth += 1
            count += 1
            _need(depth <= limits[1], "limit")
            index += 1
        elif byte in (125, 93):
            depth -= 1
            _need(depth >= 0, "noncanonical")
            index += 1
        elif byte == 34:
            count += 1
            index += 1
            while index < len(data) and data[index] != 34:
                if data[index] == 92:
                    index += 1
                index += 1
            _need(index < len(data), "noncanonical")
            index += 1
        elif byte == 45 or 48 <= byte <= 57:
            count += 1
            start = index
            index += 1
            while index < len(data) and data[index] not in b",]} \r\n\t":
                index += 1
                _need(index - start <= 20, "limit")
            token = data[start:index]
            _need(re.fullmatch(rb"-?(0|[1-9][0-9]*)", token) is not None, "noncanonical")
            _need(_MIN <= int(token) <= _MAX, "limit")
        elif byte in b"tfn":
            count += 1
            token = b"true" if byte == 116 else b"false" if byte == 102 else b"null"
            _need(data[index : index + len(token)] == token, "noncanonical")
            index += len(token)
        elif byte in b",:":
            index += 1
        else:
            raise JournalValidationError("noncanonical")
        _need(count <= limits[2], "limit")
    _need(depth == 0, "noncanonical")


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        _need(key not in result, "noncanonical")
        result[key] = value
    return result


def _decode(data: bytes, limits: tuple[int, int, int]) -> dict[str, Any]:
    _lexical(data, limits)
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs)
    except (ValueError, UnicodeError, RecursionError) as error:
        if type(error) is JournalValidationError:
            raise
        raise JournalValidationError("noncanonical") from error
    _need(type(value) is dict)
    # The preserved-byte guard bounded construction; this independent primitive
    # pass rejects escaped NUL/surrogates and preflights canonical serialization.
    snapshot = _plain(cast(StoredObject, _freeze(value)), _PrimitiveBudget(limits))
    _need(_json(snapshot) == data, "noncanonical")
    return cast(dict[str, Any], snapshot)


def _pe(data: bytes, kind: str) -> StoredObject:
    try:
        if kind == "intent":
            return decode_call_intent(data)
        if kind == "ref":
            return decode_call_ref(data)
        if kind == "result":
            return decode_call_result(data)
        if kind == "invocation":
            return decode_invocation(data)
        return decode_error_graph(data)
    except ProcessEvidenceError as error:
        raise JournalValidationError("schema") from error


def _ref(value: Any, cap: int = 32 * _MIB) -> dict[str, Any]:  # noqa: ANN401
    row = _keys(value, "sha256 size key")
    digest = _hex(row["sha256"])
    size = _int(row["size"], 0, cap)
    _need(type(row["key"]) is str and row["key"] == "blobs/" + digest)
    _need(size != 0 or digest == _EMPTY)
    return row


def _file(value: Any) -> None:  # noqa: ANN401
    row = _keys(value, "device inode uid gid mode nlink size mtime_ns ctime_ns")
    for key in row:
        _int(
            row[key],
            _MIN if key in ("mtime_ns", "ctime_ns") else 0,
            4095 if key == "mode" else _MAX,
        )


def _metadata(value: Any) -> None:  # noqa: ANN401
    for role, row in zip(_META, _list(value, 4, 4), strict=True):
        _keys(row, "role path blob observation")
        _need(row["role"] == role)
        _path(row["path"])
        _ref(row["blob"])
        _file(row["observation"])
        _need(row["observation"]["size"] == row["blob"]["size"])


def _prerequisite_ref(value: Any) -> None:  # noqa: ANN401
    row = _keys(value, "prerequisite authority_inventory")
    _ref(row["prerequisite"], 16384)
    _ref(row["authority_inventory"], 16384)


def _kernel(value: Any) -> None:  # noqa: ANN401
    row = _keys(
        value,
        "observed_at pid start_ticks host_boot_id cgroup namespaces network security mounts raw",
    )
    _utc(row["observed_at"])
    _int(row["pid"], 1)
    _int(row["start_ticks"], 1)
    _uuid(row["host_boot_id"])
    cg = _keys(
        row["cgroup"],
        "path device inode memory_max swap_max pids_max cpu_quota_us cpu_period_us populated",
    )
    _path(cg["path"])
    _bool(cg["populated"])
    for key in ("device", "inode", "cpu_period_us"):
        _int(cg[key])
    for key in ("memory_max", "swap_max", "pids_max", "cpu_quota_us"):
        if type(cg[key]) is str:
            _need(cg[key] == "max")
        else:
            _int(cg[key])
    ns = _keys(
        row["namespaces"], "pid_inode net_inode cgroup_inode ipc_inode mount_inode user_inode"
    )
    for number in ns.values():
        _int(number, 1)
    net = _keys(row["network"], "interface_names nonloopback_routes")
    for name in _list(net["interface_names"], 32):
        _text(name, 64)
    _int(net["nonloopback_routes"])
    sec = _keys(
        row["security"],
        "uid gid groups nnp cap_inheritable cap_permitted cap_effective cap_bounding "
        "cap_ambient seccomp_mode apparmor_label",
    )
    for key in (
        "uid",
        "gid",
        "cap_inheritable",
        "cap_permitted",
        "cap_effective",
        "cap_bounding",
        "cap_ambient",
    ):
        _int(sec[key])
    _int(sec["nnp"], 0, 1)
    _int(sec["seccomp_mode"], 0, 2)
    _text(sec["apparmor_label"])
    for group in _list(sec["groups"], 32):
        _int(group)
    for mount in _list(row["mounts"], 64):
        _keys(
            mount,
            "target source fstype readonly nosuid nodev noexec propagation total_bytes "
            "total_inodes",
        )
        target = _text(mount["target"])
        if target != "/":
            _path(target)
        _text(mount["source"])
        _id(mount["fstype"])
        _id(mount["propagation"])
        for name in ("readonly", "nosuid", "nodev", "noexec"):
            _bool(mount[name])
        for name in ("total_bytes", "total_inodes"):
            if mount[name] is not None:
                _int(mount[name])
    for reference in _list(row["raw"], 16):
        _ref(reference, 65536)


def _local(kind: str, row: dict[str, Any]) -> None:
    _need(row.get("schema") in _SCHEMAS[kind])
    if kind == "root":
        _keys(
            row,
            "schema deployment_id store_id artifact_domain owner_uid owner_gid "
            "evidence_root host_work_root format",
        )
        _uuid(row["deployment_id"])
        _uuid(row["store_id"])
        _choice(row["artifact_domain"], ("operational", "diagnostic"))
        _int(row["owner_uid"], 1, 2147483647)
        _int(row["owner_gid"], 1, 2147483647)
        a, b = _path(row["evidence_root"]), _path(row["host_work_root"])
        _need(a != b and not a.startswith(b + "/") and not b.startswith(a + "/"))
        _need(row["format"] == "scanipy-runtime-journal/1")
    elif kind == "authority-inventory":
        _keys(row, "schema prerequisite objects")
        _ref(row["prerequisite"], 16384)
        previous = -1
        total = 0
        for item in _list(row["objects"], 6):
            _keys(item, "role bytes")
            role = _choice(item["role"], _AUTH)
            _need(_AUTH.index(role) > previous)
            previous = _AUTH.index(role)
            total += _ref(item["bytes"], _MIB)["size"]
        _need(total <= _MIB, "limit")
    elif kind == "prerequisite":
        _keys(
            row,
            "schema reader_id observation_id observed_at valid_until principal_id org_id "
            "action authentication_evidence_sha256 scope_evidence_sha256 admission "
            "execution_authorization_digest capture_lease_evidence_sha256 "
            "content_verification_evidence_sha256",
        )
        _id(row["reader_id"])
        _id(row["principal_id"])
        _uuid(row["observation_id"])
        _uuid(row["org_id"])
        elapsed = _utc(row["valid_until"]) - _utc(row["observed_at"])
        _need(0 < elapsed.total_seconds() <= 60)
        action = _choice(row["action"], _ACTIONS)
        for name in ("authentication_evidence_sha256", "scope_evidence_sha256"):
            _hex(row[name])
        _need((row["admission"] is None) == (action == "audit-historical"))
        if row["admission"] is not None:
            _need(type(row["admission"]) is dict)
        for name in (
            "execution_authorization_digest",
            "capture_lease_evidence_sha256",
            "content_verification_evidence_sha256",
        ):
            required = action == "parse-python" or (
                action == "verify-execution" and name != "content_verification_evidence_sha256"
            )
            _need((row[name] is not None) == required)
            if required:
                _hex(row[name])
    elif kind == "manifest":
        _manifest(row)
    elif kind == "event":
        _event(row)
    elif kind == "refusal":
        _keys(
            row,
            "schema refusal_id recorded_at host_boot_id elapsed_ms operation_id "
            "requested_mode phase code anchor input available_evidence primary_error_id",
        )
        for key in ("refusal_id", "host_boot_id"):
            _uuid(row[key])
        _utc(row["recorded_at"])
        _int(row["elapsed_ms"])
        if row["operation_id"] is not None:
            _uuid(row["operation_id"])
        if row["requested_mode"] is not None:
            _choice(row["requested_mode"], _MODES)
        _choice(row["phase"], ("load", "authority", "reserve"))
        _choice(row["code"], _FAILURES)
        if row["anchor"] is not None:
            anchor = _keys(
                row["anchor"], "deployment_id installation_id generation installation_sha256"
            )
            _uuid(anchor["deployment_id"])
            _uuid(anchor["installation_id"])
            _int(anchor["generation"], 1)
            _hex(anchor["installation_sha256"])
        if row["input"] is not None:
            _keys(row["input"], "size sha256")
            _int(row["input"]["size"])
            _hex(row["input"]["sha256"])
        for reference in _list(row["available_evidence"], 16):
            _ref(reference, 8 * _MIB)
        if row["primary_error_id"] is not None:
            _uuid(row["primary_error_id"])
    elif kind == "spool-registration":
        _registration(row)
    elif kind == "spool-observation":
        _keys(
            row,
            "schema store_id attempt_id call_id stream registration_event_digest "
            "observed_at before after bytes",
        )
        for key in ("store_id", "attempt_id", "call_id"):
            _uuid(row[key])
        _choice(row["stream"], ("stdout", "stderr"))
        _hex(row["registration_event_digest"])
        _utc(row["observed_at"])
        _file(row["before"])
        _file(row["after"])
        _need(row["before"] == row["after"])
        _ref(row["bytes"], 16 * _MIB)
        _need(row["before"]["size"] == row["bytes"]["size"])
        _need(row["before"]["mode"] == 384 and row["before"]["nlink"] == 1)
    else:
        _publication(row)


def decode_journal_record(kind: JournalRecordKind, data: bytes) -> ParsedJournalRecord:
    name = _choice(kind, tuple(_SCHEMAS))
    document = _decode(data, _LIMITS[name])
    _local(name, document)
    if name == "event" and document["kind"] in ("call-intent", "call-result"):
        _need(len(data) <= 8192, "limit")
    digest = hashlib.sha256(data).digest()
    domain = hashlib.sha256(document["schema"].encode() + b"\n" + data).digest()
    return ParsedJournalRecord(
        "local-structure-only",
        cast(JournalRecordKind, name),
        document["schema"],
        data,
        digest,
        domain,
        cast(StoredObject, _freeze(document)),
    )


def encode_journal_record(kind: JournalRecordKind, document: StoredObject) -> bytes:
    name = _choice(kind, tuple(_SCHEMAS))
    value = _plain(document, _PrimitiveBudget(_LIMITS[name]))
    _need(type(value) is dict)
    data = _json(value)
    decode_journal_record(cast(JournalRecordKind, name), data)
    return data


_IDENTITIES = (
    "operation_id",
    "mode",
    "request_digest",
    "installation_id",
    "installation_generation",
    "installation_sha256",
    "controller_profile_sha256",
    "domain_profile_sha256",
    "inventory_sha256",
    "inventory_digest",
    "program_digest",
    "expected_image_config_id",
    "expected_oci_manifest_digest",
    "container_name",
)


def _manifest(row: dict[str, Any]) -> None:
    _keys(
        row,
        "schema store_id deployment_id attempt_id operation_id mode artifact_domain "
        "created_at origin_host_boot_id origin_writer_id request input launch "
        "initial_prerequisite authority_inventory parent_barrier installation_id "
        "installation_generation installation_sha256 controller_profile_sha256 "
        "domain_profile_sha256 inventory_sha256 inventory_digest program_digest "
        "expected_image_config_id expected_oci_manifest_digest container_name metadata "
        "quota_plan",
    )
    for key in (
        "store_id",
        "deployment_id",
        "attempt_id",
        "operation_id",
        "origin_host_boot_id",
        "origin_writer_id",
        "installation_id",
    ):
        _uuid(row[key])
    mode = _choice(row["mode"], _MODES)
    _choice(row["artifact_domain"], ("operational", "diagnostic"))
    _utc(row["created_at"])
    _int(row["installation_generation"], 1)
    for key in (
        "installation_sha256",
        "controller_profile_sha256",
        "domain_profile_sha256",
        "inventory_sha256",
        "inventory_digest",
        "program_digest",
    ):
        _hex(row[key])
    for key in ("request", "launch"):
        _ref(row[key], 65536)
    _ref(row["input"], 263244 if mode == "python-syntax" else 2621440)
    for key in ("initial_prerequisite", "authority_inventory"):
        _ref(row[key], 16384)
    _need((row["parent_barrier"] is not None) == (mode in _MODES[2:]))
    if row["parent_barrier"] is not None:
        _ref(row["parent_barrier"], 16384)
    _image(row["expected_image_config_id"])
    if row["expected_oci_manifest_digest"] is not None:
        _image(row["expected_oci_manifest_digest"])
    _need(row["container_name"] == "scanipy-runtime-" + row["attempt_id"].replace("-", ""))
    _metadata(row["metadata"])
    for item, name in zip(
        row["metadata"],
        (
            "installation_sha256",
            "controller_profile_sha256",
            "domain_profile_sha256",
            "inventory_sha256",
        ),
        strict=True,
    ):
        _need(item["blob"]["sha256"] == row[name])
    quota = _keys(row["quota_plan"], " ".join(_QUOTA))
    for name, expected in _QUOTA.items():
        _need(_int(quota[name]) == expected)


def _registration(row: dict[str, Any]) -> None:
    _keys(
        row,
        "schema store_id attempt_id operation_id call_id intent_event_digest "
        "relative_directory directory files input_mode limits",
    )
    for key in ("store_id", "attempt_id", "operation_id", "call_id"):
        _uuid(row[key])
    _hex(row["intent_event_digest"])
    _need(row["relative_directory"] == "call-spools/" + row["call_id"])
    directory = _keys(row["directory"], "device inode uid gid mode")
    for name in ("device", "uid", "gid"):
        _int(directory[name])
    _int(directory["inode"], 1)
    _need(_int(directory["mode"]) == 448)
    for stream, entry in zip(("stdout", "stderr"), _list(row["files"], 2, 2), strict=True):
        _keys(entry, "stream name")
        _need(entry == {"stream": stream, "name": stream + ".bin"})
    _need(row["input_mode"] == "finite-one-shot")
    limits = _keys(
        row["limits"],
        "stdin_bytes stdout_bytes stderr_bytes combined_output_bytes wall_ms cleanup_reserve_ms",
    )
    for name, cap in (
        ("stdin_bytes", 4 * _MIB),
        ("stdout_bytes", 16 * _MIB),
        ("stderr_bytes", _MIB),
        ("combined_output_bytes", 17 * _MIB),
    ):
        _int(limits[name], 0, cap)
    _int(limits["wall_ms"], 1, 30000)
    _int(limits["cleanup_reserve_ms"], 1, min(5000, limits["wall_ms"] - 1))
    _need(limits["combined_output_bytes"] <= limits["stdout_bytes"] + limits["stderr_bytes"])


def _publication(row: dict[str, Any]) -> None:
    _keys(
        row,
        "schema publication_id store_id scope_kind scope_id role destination size sha256 "
        "expected_previous_event_digest",
    )
    for name in ("publication_id", "store_id", "scope_id"):
        _uuid(row[name])
    scope = _choice(row["scope_kind"], ("attempt", "refusal"))
    role = _choice(row["role"], ("blob", "manifest", "event", "spool-registration", "refusal"))
    _int(row["size"], 0, 32 * _MIB)
    digest = _hex(row["sha256"])
    destination = _text(row["destination"], 128)
    if role == "blob":
        _need(destination == "blobs/" + digest)
    elif role in ("manifest", "refusal"):
        _need(destination == role + ".json")
    elif role == "event":
        _need(re.fullmatch(r"events/[0-9]{6}\.json", destination) is not None)
        _int(int(destination[7:13]), 1, 128)
    else:
        _need(destination.startswith("spool-registrations/") and destination.endswith(".json"))
        _uuid(destination[20:-5])
    _need(
        role
        in (
            ("blob", "refusal")
            if scope == "refusal"
            else ("blob", "manifest", "event", "spool-registration")
        )
    )
    if row["expected_previous_event_digest"] is not None:
        _hex(row["expected_previous_event_digest"])
        _need(scope == "attempt")


def _call_ref(value: Any) -> None:  # noqa: ANN401
    _pe(_json(value), "ref")


def _event(row: dict[str, Any]) -> None:
    _keys(
        row,
        "schema attempt_id sequence previous_event_digest event_id kind recorded_at "
        "host_boot_id elapsed_ms operation_id mode request_digest installation_id "
        "installation_generation installation_sha256 controller_profile_sha256 "
        "domain_profile_sha256 inventory_sha256 inventory_digest program_digest "
        "expected_image_config_id expected_oci_manifest_digest observed_image_config_id "
        "observed_oci_manifest_digest container_name container_id payload",
    )
    for key in ("attempt_id", "event_id", "host_boot_id", "operation_id", "installation_id"):
        _uuid(row[key])
    _int(row["sequence"], 1, 128)
    if row["previous_event_digest"] is not None:
        _hex(row["previous_event_digest"])
    _need((row["previous_event_digest"] is None) == (row["sequence"] == 1))
    _utc(row["recorded_at"])
    _int(row["elapsed_ms"])
    _choice(row["mode"], _MODES)
    _int(row["installation_generation"], 1)
    for name in (
        "request_digest",
        "installation_sha256",
        "controller_profile_sha256",
        "domain_profile_sha256",
        "inventory_sha256",
        "inventory_digest",
        "program_digest",
    ):
        _hex(row[name])
    _image(row["expected_image_config_id"])
    for name in (
        "expected_oci_manifest_digest",
        "observed_image_config_id",
        "observed_oci_manifest_digest",
    ):
        if row[name] is not None:
            _image(row[name])
    _need(row["container_name"] == "scanipy-runtime-" + row["attempt_id"].replace("-", ""))
    if row["container_id"] is not None:
        _hex(row["container_id"])
    kind = _text(row["kind"], 32)
    p = row["payload"]
    if kind == "reserved":
        _keys(p, "launch_sha256 launch_bytes_ref input manifest")
        _hex(p["launch_sha256"])
        _ref(p["launch_bytes_ref"], 65536)
        _need(p["launch_sha256"] == p["launch_bytes_ref"]["sha256"])
        _ref(p["input"], 2621440)
        _ref(p["manifest"], 16384)
    elif kind == "loaded":
        _keys(
            p,
            "metadata measurement_elapsed_ms cli_file socket daemon_calls "
            "image_inspect_call create_prerequisite",
        )
        _metadata(p["metadata"])
        _int(p["measurement_elapsed_ms"])
        _file(p["cli_file"])
        socket = _keys(p["socket"], "path device inode uid gid mode")
        _path(socket["path"])
        for name in ("device", "inode", "uid", "gid", "mode"):
            _int(socket[name], 0, 4095 if name == "mode" else _MAX)
        for reference in _list(p["daemon_calls"], 2, 2):
            _call_ref(reference)
        _call_ref(p["image_inspect_call"])
        _prerequisite_ref(p["create_prerequisite"])
    elif kind == "created":
        _keys(p, "create_call inspect_call config_digest")
        _call_ref(p["create_call"])
        _call_ref(p["inspect_call"])
        _hex(p["config_digest"])
    elif kind == "started":
        _keys(p, "start_call_id pid start_ticks control_path")
        _uuid(p["start_call_id"])
        _int(p["pid"], 1)
        _int(p["start_ticks"], 1)
        _path(p["control_path"])
    elif kind == "observed":
        _keys(p, "sample inspect_call prerequisite observation_id")
        _kernel(p["sample"])
        _call_ref(p["inspect_call"])
        _prerequisite_ref(p["prerequisite"])
        _uuid(p["observation_id"])
    elif kind in ("release-intent", "released"):
        _keys(
            p,
            "release prerequisite observed_event_digest"
            if kind == "release-intent"
            else "release prerequisite published_at release_intent_event_digest",
        )
        _ref(p["release"], 16384)
        _prerequisite_ref(p["prerequisite"])
        _hex(
            p["observed_event_digest"]
            if kind == "release-intent"
            else p["release_intent_event_digest"]
        )
        if kind == "released":
            _utc(p["published_at"])
    elif kind == "domain-exited":
        _keys(p, "start_call container_inspect_call domain_result domain_validation")
        _call_ref(p["start_call"])
        _call_ref(p["container_inspect_call"])
        validation = _choice(p["domain_validation"], ("valid", "rejected", "invalid"))
        _need(validation == "invalid" or p["domain_result"] is not None)
        if p["domain_result"] is not None:
            _ref(p["domain_result"], 8 * _MIB if row["mode"] == "python-syntax" else 16384)
    elif kind == "cleanup":
        _keys(
            p,
            "state calls final_inspect_call cgroup_empty client_reaped "
            "parent_lease_action invocation_slot cleanup_id",
        )
        _choice(p["state"], ("complete", "incomplete"))
        for reference in _list(p["calls"], 16):
            _call_ref(reference)
        if p["final_inspect_call"] is not None:
            _call_ref(p["final_inspect_call"])
        if p["cgroup_empty"] is not None:
            _bool(p["cgroup_empty"])
        _bool(p["client_reaped"])
        _need(p["parent_lease_action"] == "none" and p["invocation_slot"] == "held")
        _uuid(p["cleanup_id"])
    elif kind == "admitted":
        _keys(
            p,
            "result_digest prerequisite cleanup_event_digest parent_lease_action "
            "invocation_slot domain_exited_event_digest",
        )
        for name in ("result_digest", "cleanup_event_digest", "domain_exited_event_digest"):
            _hex(p[name])
        _prerequisite_ref(p["prerequisite"])
        _need(p["parent_lease_action"] == "none" and p["invocation_slot"] == "released")
    elif kind in ("failed", "orphaned"):
        _keys(p, "phase code calls kernel primary_error_id cleanup_event_digest")
        _choice(p["phase"], _PHASES)
        _choice(p["code"], _FAILURES)
        for reference in _list(p["calls"], 16):
            _call_ref(reference)
        if p["kernel"] is not None:
            _ref(p["kernel"], 65536)
        if p["primary_error_id"] is not None:
            _uuid(p["primary_error_id"])
        if p["cleanup_event_digest"] is not None:
            _hex(p["cleanup_event_digest"])
    elif kind == "call-intent":
        _pe(_json(p), "intent")
    elif kind == "call-result":
        _keys(p, "intent_event_digest call")
        _hex(p["intent_event_digest"])
        _call_ref(p["call"])
    elif kind == "spool-registered":
        _keys(p, "intent_event_digest call_id registration")
        _hex(p["intent_event_digest"])
        _uuid(p["call_id"])
        _ref(p["registration"], 4096)
    elif kind == "spool-collected":
        _keys(p, "registration_event_digest stream observation")
        _hex(p["registration_event_digest"])
        _choice(p["stream"], ("stdout", "stderr"))
        _ref(p["observation"], 4096)
    elif kind == "recovery-entered":
        _keys(p, "recovery_id writer_id reason prior_head_digest")
        _uuid(p["recovery_id"])
        _uuid(p["writer_id"])
        _choice(
            p["reason"],
            (
                "writer-restart",
                "boot-change",
                "clock-uncertain",
                "abandoned-handle",
                "orphan-resume",
            ),
        )
        _hex(p["prior_head_digest"])
    elif kind == "reconciled":
        _keys(
            p,
            "orphan_event_digest cleanup_event_digest disposition parent_lease_action "
            "invocation_slot",
        )
        _hex(p["orphan_event_digest"])
        _hex(p["cleanup_event_digest"])
        _need(
            p["disposition"] == "failed"
            and p["parent_lease_action"] == "none"
            and p["invocation_slot"] == "released"
        )
    else:
        raise JournalValidationError("schema")


def _blob_snapshot(value: EvidenceBlob) -> EvidenceBlob:
    _need(type(value) is EvidenceBlob, "invalid-type")
    try:
        data = EvidenceBlob.__dict__["data"].__get__(value, EvidenceBlob)
        digest = EvidenceBlob.__dict__["sha256"].__get__(value, EvidenceBlob)
    except AttributeError as error:
        raise JournalValidationError("invalid-type") from error
    data = _bytes(data, 32 * _MIB)
    digest = _bytes(digest, 32)
    _need(len(digest) == 32)
    return EvidenceBlob(data, digest)


class _Pool:
    def __init__(self, blobs: tuple[EvidenceBlob, ...], record_size: int, cap: int = 256) -> None:
        _need(record_size <= 524288, "limit")
        source = _tuple(blobs, cap)
        # Finish bounded primitive/length/order checks before hashing any payload.
        copies = tuple(_blob_snapshot(item) for item in source)
        self.supplied = sum(len(item.data) for item in copies)
        _need(self.supplied + record_size <= 32 * _MIB, "limit")
        previous: bytes | None = None
        for item in copies:
            _need(previous is None or previous < item.sha256, "order")
            previous = item.sha256
        self.hash_work = 0
        self.blobs: dict[str, bytes] = {}
        for item in copies:
            _need(self.hash(item.data) == item.sha256, "reference")
            self.blobs[item.sha256.hex()] = item.data
        self.copies = copies
        self.used: set[str] = set()
        self.edges = 0
        self.graph: dict[str, set[str]] = {}
        self.records: dict[tuple[str, str], tuple[ParsedJournalRecord, dict[str, Any]]] = {}
        self.pe_records: dict[tuple[str, str], tuple[StoredObject, dict[str, Any]]] = {}
        self.opaque: set[tuple[str, bytes, tuple[str | int, ...]]] = set()
        self.charged: dict[tuple[str, ...], int] = {}
        self.metadata = record_size

    def hash(self, data: bytes, domain: str | None = None) -> bytes:
        prefix = b"" if domain is None else domain.encode() + b"\n"
        self.hash_work += len(prefix) + len(data)
        _need(self.hash_work <= 512 * _MIB, "limit")
        return hashlib.sha256(prefix + data).digest()

    def charge(self, token: tuple[str, ...], amount: int) -> None:
        if token in self.charged:
            _need(self.charged[token] == amount, "conflict")
            return
        self.charged[token] = amount
        self.metadata += amount
        _need(self.metadata <= 524288, "limit")

    def resolve(self, reference: dict[str, Any], source: str, cap: int = 32 * _MIB) -> bytes:
        row = _ref(reference, cap)
        digest = row["sha256"]
        self.edges += 1
        _need(self.edges <= 4096, "limit")
        _need(digest in self.blobs, "reference")
        data = self.blobs[digest]
        _need(len(data) == row["size"], "reference")
        self.used.add(digest)
        self.graph.setdefault(source, set()).add(digest)
        return data

    def owner(self, reference: dict[str, Any], source: str, role: str, cap: int) -> bytes:
        data = self.resolve(reference, source, cap)
        self.obligation(role, reference["sha256"])
        return data

    def obligation(self, role: str, digest: str, path: tuple[str | int, ...] = ()) -> None:
        _need(role in _OWNERS)
        self.opaque.add((role, bytes.fromhex(digest), path))
        _need(len(self.opaque) <= 4096, "limit")

    def local(
        self, reference: dict[str, Any], source: str, kind: str
    ) -> tuple[ParsedJournalRecord, dict[str, Any]]:
        data = self.resolve(reference, source, _LIMITS[kind][0])
        key = (kind, reference["sha256"])
        if key not in self.records:
            parsed = decode_journal_record(cast(JournalRecordKind, kind), data)
            self.records[key] = (parsed, _plain(parsed.document, _PrimitiveBudget(_LIMITS[kind])))
        return self.records[key]

    def pe(
        self, reference: dict[str, Any], source: str, kind: str
    ) -> tuple[StoredObject, dict[str, Any]]:
        caps = {"invocation": _MIB, "result": 32768, "error": 8192}
        data = self.resolve(reference, source, caps[kind])
        key = (kind, reference["sha256"])
        if key not in self.pe_records:
            view = _pe(data, kind)
            plain = _plain(view, _PrimitiveBudget((caps[kind], 16, 4096)))
            self.pe_records[key] = (view, plain)
        return self.pe_records[key]

    def finish(self) -> tuple[OpaqueOwnerValue, ...]:
        _need(self.used == set(self.blobs), "reference")
        colors: dict[str, int] = {}
        heights: dict[str, int] = {}
        pending = [(node, False) for node in self.graph]
        while pending:
            node, exiting = pending.pop()
            if exiting:
                height = max((1 + heights[child] for child in self.graph.get(node, ())), default=0)
                _need(height <= 16, "limit")
                heights[node] = height
                colors[node] = 2
            elif colors.get(node) != 2:
                _need(colors.get(node) != 1, "reference")
                colors[node] = 1
                pending.append((node, True))
                pending.extend((child, False) for child in self.graph.get(node, ()))
        ordered = sorted(
            self.opaque,
            key=lambda item: (
                _OWNERS.index(item[0]),
                item[1],
                tuple((0, part.encode()) if type(part) is str else (1, part) for part in item[2]),
            ),
        )
        return tuple(
            OpaqueOwnerValue(cast(OwnerRole, role), digest, path) for role, digest, path in ordered
        )


def validate_refusal(refusal: bytes, *, blobs: tuple[EvidenceBlob, ...]) -> RefusalStructureReport:
    _bytes(refusal, 16384)
    pool = _Pool(blobs, len(refusal), 16)
    parsed = decode_journal_record("refusal", refusal)
    document = _plain(parsed.document, _PrimitiveBudget(_LIMITS["refusal"]))
    refs = document["available_evidence"]
    _need(len({row["sha256"] for row in refs}) == len(refs), "conflict")
    primary = document["primary_error_id"]
    found = 0
    for reference in refs:
        data = pool.resolve(reference, parsed.sha256.hex(), 8 * _MIB)
        matching = False
        if primary is not None and len(data) <= 8192:
            try:
                view = _pe(data, "error")
            except JournalValidationError:
                pass
            else:
                graph = _plain(view, _PrimitiveBudget((8192, 8, 1024)))
                matching = graph["error_id"] == primary
        if matching:
            found += 1
            pool.charge(("primary-graph", primary), len(data))
        else:
            pool.obligation("refusal-raw", reference["sha256"])
    _need(found == (0 if primary is None else 1), "reference")
    obligations = pool.finish()
    return RefusalStructureReport("local-structure-only", parsed, pool.copies, obligations)


class _Replay:
    def __init__(
        self, manifest: ParsedJournalRecord, events: tuple[ParsedJournalRecord, ...], pool: _Pool
    ) -> None:
        self.manifest = manifest
        self.m = cast(
            dict[str, Any], _plain(manifest.document, _PrimitiveBudget(_LIMITS["manifest"]))
        )
        self.events = events
        self.pool = pool
        self.state = "reserved"
        self.recovery = False
        self.orphaned = False
        self.last_semantic = "reserved"
        self.calls: dict[str, dict[str, Any]] = {}
        self.ordinary_calls = 0
        self.by_digest: dict[str, dict[str, Any]] = {}
        self.ids: dict[str, set[str]] = {}
        self.prerequisites: dict[str, tuple[str, str]] = {}
        self.principal: tuple[str, str, str] | None = None
        self.registrations: dict[str, tuple[str, dict[str, Any]]] = {}
        self.collections: dict[tuple[str, str], dict[str, Any]] = {}
        self.errors: dict[str, str] = {}
        self.cleanup: str | None = None
        self.domain_exit: str | None = None
        self.release_intent: str | None = None
        self.last_observed: str | None = None
        self.orphan_event: str | None = None
        self.container_id: str | None = None
        self.observed_image: str | None = None
        self.observed_oci: str | None = None
        self.start_id: str | None = None
        self.started_identity: tuple[int, int] | None = None
        self.started_at: str | None = None
        self.overrun = False
        self.kernel_samples = 0
        self.kernel_bytes = 0
        self.observed_bytes = self.retained_bytes = 0
        self.missing_outcome = self.missing_output = self.unknown_retention = 0
        self.current_boot = self.m["origin_host_boot_id"]
        self.writer_ids = {self.m["origin_writer_id"]}
        self.elapsed = 0
        self.previous: str | None = None
        self.time = self.m["created_at"]
        self._seed()

    def unique(self, namespace: str, value: str) -> None:
        seen = self.ids.setdefault(namespace, set())
        _need(value not in seen, "conflict")
        seen.add(value)

    def _seed(self) -> None:
        m, pool = self.m, self.pool
        source = self.manifest.sha256.hex()
        caps = (65536, 131072, 65536, 8 * _MIB)
        for role, item, cap in zip(_OWNERS[:4], m["metadata"], caps, strict=True):
            pool.owner(item["blob"], source, role, cap)
        request = pool.owner(m["request"], source, "mode-request", 65536)
        self.request_digest = pool.hash(request, "scanipy-local-runtime-request/1").hex()
        pool.owner(
            m["input"], source, "mode-input", 263244 if m["mode"] == "python-syntax" else 2621440
        )
        pool.owner(m["launch"], source, "launch-packet", 65536)
        if m["parent_barrier"] is not None:
            pool.owner(m["parent_barrier"], source, "parent-barrier", 16384)
        self.prerequisite(
            {
                "prerequisite": m["initial_prerequisite"],
                "authority_inventory": m["authority_inventory"],
            },
            source,
            boundary=m["created_at"],
        )

    def prerequisite(self, reference: dict[str, Any], source: str, *, boundary: str | None) -> None:
        pool = self.pool
        parsed, p = pool.local(reference["prerequisite"], source, "prerequisite")
        if boundary is not None:
            _need(p["observed_at"] <= boundary < p["valid_until"], "order")
        inv, inventory = pool.local(reference["authority_inventory"], source, "authority-inventory")
        _need(inventory["prerequisite"] == reference["prerequisite"], "reference")
        pool.resolve(inventory["prerequisite"], inv.sha256.hex(), 16384)
        _need(p["action"] == _ACTIONS[_MODES.index(self.m["mode"])], "reference")
        scope = (p["org_id"], p["principal_id"], p["action"])
        _need(self.principal is None or self.principal == scope, "conflict")
        self.principal = scope
        identity = p["observation_id"]
        pair = (parsed.sha256.hex(), inv.sha256.hex())
        _need(
            identity not in self.prerequisites or self.prerequisites[identity] == pair, "conflict"
        )
        self.prerequisites[identity] = pair
        pool.charge(("prerequisite", identity), len(parsed.data))
        pool.charge(("authority-inventory", identity), len(inv.data))
        if p["admission"] is not None:
            pool.obligation("admission", parsed.sha256.hex(), ("admission",))
        required = ["authentication", "scope"]
        if p["admission"] is not None:
            required.append("admission")
        if p["execution_authorization_digest"] is not None:
            required.extend(("execution-authorization", "capture-lease"))
        if p["content_verification_evidence_sha256"] is not None:
            required.append("content-verification")
        _need([item["role"] for item in inventory["objects"]] == required, "reference")
        raw_fields = {
            "authentication": "authentication_evidence_sha256",
            "scope": "scope_evidence_sha256",
            "capture-lease": "capture_lease_evidence_sha256",
            "content-verification": "content_verification_evidence_sha256",
        }
        for item in inventory["objects"]:
            role = item["role"]
            pool.owner(item["bytes"], inv.sha256.hex(), role, _MIB)
            if role in raw_fields:
                _need(item["bytes"]["sha256"] == p[raw_fields[role]], "reference")
            # Admission and EXECUTION domain linkage is deliberately not inferred.

    def prior(self, digest: str, kind: str | None = None) -> dict[str, Any]:
        _need(digest in self.by_digest, "reference")
        event = self.by_digest[digest]
        _need(kind is None or event["kind"] == kind, "reference")
        return event

    def call(self, reference: dict[str, Any], operation: str | None = None) -> dict[str, Any]:
        call_id = reference["call_id"]
        _need(call_id in self.calls, "reference")
        call = self.calls[call_id]
        _need(call["result"] is not None and call["ref"] == reference, "reference")
        _need(operation is None or call["intent"]["operation"] == operation, "reference")
        return call

    def healthy(self, call: dict[str, Any]) -> bool:
        result = call["result"]
        if result is None or result["error_id"] is not None:
            return False
        outcome = result["outcome"]
        if (
            outcome is None
            or outcome["reason"] != "exited"
            or outcome["returncode"] != 0
            or outcome["cleanup"] != "completed"
        ):
            return False
        if outcome["invocation"] != result["requested_invocation"]:
            return False
        return all(
            outcome[name] is not None
            and outcome[name]["custody"]["state"] == "verified"
            and outcome[name]["reported"]["eof"]
            and not outcome[name]["reported"]["truncated"]
            for name in ("stdout", "stderr")
        )

    def disposed(self) -> bool:
        for call in self.calls.values():
            if call["result"] is None:
                return False
            outcome = call["result"]["outcome"]
            if outcome is None:
                if call["result"]["unavailable_reason"] != "validation-refused":
                    return False
            elif outcome["cleanup"] not in ("completed", "not_started"):
                return False
        return True

    def intent(self, event: dict[str, Any], digest: str) -> None:
        p = event["payload"]
        call_id, operation = p["call_id"], p["operation"]
        if not self.recovery and self.state not in ("cleanup", "orphaned"):
            self._productive()
            _need(self.ordinary_calls < 12, "limit")
            self.ordinary_calls += 1
        self.unique("call", call_id)
        _need(p["call_sequence"] == len(self.calls) + 1, "order")
        _need(len(self.calls) < 16, "limit")
        if self.recovery or self.state in ("cleanup", "orphaned"):
            _need(
                operation
                in (
                    "container-inspect-id",
                    "container-inspect-name",
                    "container-kill",
                    "container-wait",
                    "container-remove",
                ),
                "order",
            )
        elif self.state == "reserved":
            _need(operation in ("daemon-version", "daemon-info", "image-inspect"), "order")
        elif operation == "container-create":
            _need(
                self.state == "loaded"
                and not any(c["intent"]["operation"] == operation for c in self.calls.values()),
                "order",
            )
        elif operation == "container-start-attached":
            _need(self.state == "created" and self.start_id is None, "order")
        else:
            _need(
                operation == "container-inspect-id"
                and self.state
                in (
                    "loaded",
                    "created",
                    "start-intended",
                    "started",
                    "observed",
                    "release-intended",
                    "released",
                    "domain-exited",
                ),
                "order",
            )
        if operation == "container-inspect-name":
            _need(
                self.recovery
                and any(
                    c["intent"]["operation"] == "container-create" for c in self.calls.values()
                ),
                "order",
            )
        if operation in ("container-create", "container-inspect-name"):
            _need(p["target"] == self.m["container_name"], "reference")
        elif operation == "image-inspect":
            _need(p["target"] == self.m["expected_image_config_id"], "reference")
        elif operation not in ("daemon-version", "daemon-info"):
            _need(self.container_id is not None and p["target"] == self.container_id, "reference")
        if operation == "container-remove":
            _need(self.cleanup is not None, "order")
        view, invocation = self.pool.pe(p["invocation"], digest, "invocation")
        expected_input = (
            self.m["input"]
            if operation == "container-start-attached"
            else {"size": 0, "sha256": _EMPTY}
        )
        _need(
            invocation["stdin_bytes"] == expected_input["size"]
            and invocation["stdin_sha256"] == expected_input["sha256"],
            "reference",
        )
        # Reuse the real public PE intended-binding validator. All constructor
        # members below come from privately decoded canonical primitives.
        try:
            planned = FrozenInvocation(
                tuple(invocation["argv"]),
                tuple(tuple(item) for item in invocation["environment"]),
                invocation["cwd"],
                invocation["stdin_bytes"],
                bytes.fromhex(invocation["stdin_sha256"]),
            )
            prepared = prepare_call_intent(
                RuntimeCallBinding(
                    self.m["attempt_id"],
                    self.m["operation_id"],
                    call_id,
                    p["call_sequence"],
                    cli_operation_from_wire(operation),
                    p["target"],
                ),
                planned,
            )
        except (ProcessEvidenceError, ValueError) as error:
            raise JournalValidationError("schema") from error
        _need(prepared.payload == _json(p), "reference")
        self.pool.charge(("requested-invocation", call_id), p["invocation"]["size"])
        self.calls[call_id] = {
            "intent": p,
            "intent_view": _pe(_json(p), "intent"),
            "invocation": view,
            "intent_digest": digest,
            "sequence": event["sequence"],
            "result": None,
            "result_view": None,
            "result_sequence": None,
            "ref": None,
        }
        if operation == "container-start-attached":
            self.start_id = call_id
            self.state = "start-intended"

    def result(self, event: dict[str, Any], digest: str) -> None:
        p = event["payload"]
        call_id = p["call"]["call_id"]
        _need(call_id in self.calls, "reference")
        call = self.calls[call_id]
        _need(
            call["result"] is None and call["intent_digest"] == p["intent_event_digest"], "conflict"
        )
        view, result = self.pool.pe(p["call"]["outcome"], digest, "result")
        source = p["call"]["outcome"]["sha256"]
        for name in ("call_id", "call_sequence", "operation", "target"):
            _need(result[name] == call["intent"][name], "reference")
        _need(
            result["attempt_id"] == self.m["attempt_id"]
            and result["operation_id"] == self.m["operation_id"]
            and result["intent_event_digest"] == p["intent_event_digest"],
            "reference",
        )
        _need(result["requested_invocation"] == call["intent"]["invocation"], "reference")
        _need(p["call"]["operation"] == result["operation"], "reference")
        self.pool.pe(result["requested_invocation"], source, "invocation")
        self.pool.charge(("result", call_id), p["call"]["outcome"]["size"])
        if result["error_graph"] is not None:
            _, graph = self.pool.pe(result["error_graph"], source, "error")
            _need(graph["error_id"] == result["error_id"], "reference")
            old = self.errors.get(result["error_id"])
            _need(old is None or old == result["error_graph"]["sha256"], "conflict")
            self.errors[result["error_id"]] = result["error_graph"]["sha256"]
            self.pool.charge(("error", call_id), result["error_graph"]["size"])
        outcome = result["outcome"]
        attached = result["operation"] == "container-start-attached"
        if outcome is None:
            if not attached:
                self.missing_outcome += 1
        else:
            _, actual = self.pool.pe(outcome["invocation"], source, "invocation")
            self.pool.charge(("actual-invocation", call_id), outcome["invocation"]["size"])
            _need(outcome["stdin_sent_bytes"] <= actual["stdin_bytes"], "reference")
            if outcome["cleanup"] == "completed" and outcome["reason"] == "exited":
                _need(outcome["stdin_sent_bytes"] == actual["stdin_bytes"], "reference")
            for stream in ("stdout", "stderr"):
                output = outcome[stream]
                if output is None:
                    if not attached:
                        self.missing_output += 1
                    continue
                reported = output["reported"]
                if not attached:
                    self.observed_bytes += reported["observed_bytes"]
                    if reported["retained_bytes"] is None:
                        self.unknown_retention += 1
                    else:
                        self.retained_bytes += reported["retained_bytes"]
                maximum = (
                    (8388608 if stream == "stdout" else 65536)
                    if attached and self.m["mode"] == "python-syntax"
                    else (16384 if attached or stream == "stderr" else 262144)
                )
                if reported["observed_bytes"] > maximum or (
                    reported["retained_bytes"] is not None and reported["retained_bytes"] > maximum
                ):
                    self.overrun = True
                if output["path"] is not None:
                    path = self.pool.resolve(output["path"], source, 4096)
                    try:
                        _text(path.decode(), 4096)
                    except UnicodeError as error:
                        raise JournalValidationError("schema") from error
                    self.pool.charge(("path", call_id, stream), len(path))
                custody = output["custody"]["bytes"]
                if custody is not None:
                    self.pool.resolve(custody, source, 16 * _MIB)
                    if custody["size"] > maximum:
                        self.overrun = True
                    if output["kind"] == "spool":
                        key = (call_id, stream)
                        _need(
                            key in self.collections and self.collections[key]["bytes"] == custody,
                            "reference",
                        )
        if self.observed_bytes > 4 * _MIB or self.retained_bytes > 4 * _MIB:
            self.overrun = True
        call.update(
            result=result, result_view=view, result_sequence=event["sequence"], ref=p["call"]
        )

    def _registration_event(self, event: dict[str, Any], digest: str) -> None:
        p = event["payload"]
        call_id = p["call_id"]
        _need(call_id in self.calls and call_id not in self.registrations, "reference")
        call = self.calls[call_id]
        _need(call["result"] is None and call["intent_digest"] == p["intent_event_digest"], "order")
        attached = call["intent"]["operation"] == "container-start-attached"
        _need(not attached or self.started_identity is None, "order")
        parsed, row = self.pool.local(p["registration"], digest, "spool-registration")
        for name in ("store_id", "attempt_id", "operation_id"):
            _need(row[name] == self.m[name], "reference")
        _need(
            row["call_id"] == call_id and row["intent_event_digest"] == p["intent_event_digest"],
            "reference",
        )
        limits = row["limits"]
        expected = (
            (263244, 8388608, 65536, 8454144)
            if attached and self.m["mode"] == "python-syntax"
            else (2621440, 16384, 16384, 32768)
            if attached
            else (0, 262144, 16384, 278528)
        )
        _need(
            tuple(
                limits[name]
                for name in ("stdin_bytes", "stdout_bytes", "stderr_bytes", "combined_output_bytes")
            )
            == expected
        )
        if not attached:
            _need(250 < limits["wall_ms"] <= 2000 and limits["cleanup_reserve_ms"] == 250)
        self.pool.charge(("registration", call_id), len(parsed.data))
        self.registrations[call_id] = (digest, row)

    def _collection_event(self, event: dict[str, Any], digest: str) -> None:
        p = event["payload"]
        registered_event = self.prior(p["registration_event_digest"], "spool-registered")
        call_id = registered_event["payload"]["call_id"]
        key = (call_id, p["stream"])
        _need(key not in self.collections, "conflict")
        _need(self.calls[call_id]["result"] is None or self.recovery, "order")
        parsed, row = self.pool.local(p["observation"], digest, "spool-observation")
        _need(
            row["store_id"] == self.m["store_id"]
            and row["attempt_id"] == self.m["attempt_id"]
            and row["call_id"] == call_id,
            "reference",
        )
        _need(
            row["stream"] == p["stream"]
            and row["registration_event_digest"] == p["registration_event_digest"],
            "reference",
        )
        registration = self.registrations[call_id][1]
        for name in ("uid", "gid"):
            _need(row["before"][name] == registration["directory"][name], "reference")
        self.pool.resolve(row["bytes"], parsed.sha256.hex(), 16 * _MIB)
        self.pool.charge(("collection", *key), len(parsed.data))
        self.collections[key] = row
        limits = registration["limits"]
        combined_size = sum(
            observed["bytes"]["size"]
            for (observed_call, _stream), observed in self.collections.items()
            if observed_call == call_id
        )
        if (
            row["bytes"]["size"] > limits[p["stream"] + "_bytes"]
            or combined_size > limits["combined_output_bytes"]
        ):
            # File readback is separate evidence, not a replacement transport
            # outcome/counter. Its known limit violation is nevertheless sticky.
            self.overrun = True

    def _kernel_refs(self, sample: dict[str, Any], source: str) -> None:
        self.kernel_samples += 1
        _need(self.kernel_samples <= 16, "limit")
        for reference in sample["raw"]:
            self.pool.owner(reference, source, "kernel-raw", 65536)
            self.kernel_bytes += reference["size"]
        _need(self.kernel_bytes <= _MIB, "limit")

    def _expected_pins(self) -> None:
        _need(
            self.observed_image in (None, self.m["expected_image_config_id"])
            and (
                self.m["expected_oci_manifest_digest"] is None
                or self.observed_oci in (None, self.m["expected_oci_manifest_digest"])
            ),
            "reference",
        )

    def _productive(self) -> None:
        _need(not self.recovery and not self.orphaned and not self.overrun, "order")
        self._expected_pins()
        _need(
            all(call["result"] is None or self.healthy(call) for call in self.calls.values()),
            "order",
        )

    def apply(self, parsed: ParsedJournalRecord) -> None:
        event = cast(dict[str, Any], _plain(parsed.document, _PrimitiveBudget(_LIMITS["event"])))
        digest = parsed.schema_digest.hex()
        source = parsed.sha256.hex()
        kind, p = event["kind"], event["payload"]
        _need(self.state not in ("failed", "admitted", "reconciled"), "order")
        _need(
            event["sequence"] == len(self.by_digest) + 1
            and event["previous_event_digest"] == self.previous,
            "order",
        )
        expected_schema = _SCHEMAS["event"][self.m["artifact_domain"] == "diagnostic"]
        _need(
            event["schema"] == expected_schema and event["attempt_id"] == self.m["attempt_id"],
            "reference",
        )
        for name in _IDENTITIES:
            _need(
                event[name] == (self.request_digest if name == "request_digest" else self.m[name]),
                "reference",
            )
        self.unique("event", event["event_id"])
        _need(event["elapsed_ms"] >= self.elapsed, "order")
        if event["host_boot_id"] != self.current_boot or event["recorded_at"] < self.time:
            _need(kind in ("recovery-entered", "orphaned"), "order")
        self.current_boot, self.time, self.elapsed = (
            event["host_boot_id"],
            event["recorded_at"],
            event["elapsed_ms"],
        )
        if self.container_id is not None:
            _need(event["container_id"] == self.container_id, "reference")
        elif event["container_id"] is not None:
            _need(
                any(c["intent"]["operation"] == "container-create" for c in self.calls.values()),
                "reference",
            )
            self.container_id = event["container_id"]
        observed_image, observed_oci = (
            event["observed_image_config_id"],
            event["observed_oci_manifest_digest"],
        )
        _need(self.observed_image is None or observed_image is not None, "reference")
        _need(self.observed_oci is None or observed_oci is not None, "reference")
        self.observed_image, self.observed_oci = observed_image, observed_oci
        if kind == "reserved":
            _need(event["sequence"] == 1 and self.state == "reserved", "order")
            _need(
                p["manifest"]["sha256"] == self.manifest.sha256.hex()
                and p["manifest"]["size"] == len(self.manifest.data),
                "reference",
            )
            _need(
                p["launch_bytes_ref"] == self.m["launch"] and p["input"] == self.m["input"],
                "reference",
            )
            _need(
                event["host_boot_id"] == self.m["origin_host_boot_id"]
                and event["recorded_at"] >= self.m["created_at"],
                "reference",
            )
            _need(event["container_id"] is None, "reference")
        else:
            _need(event["sequence"] > 1, "order")
            if kind == "call-intent":
                self.intent(event, digest)
            elif kind == "call-result":
                self.result(event, digest)
            elif kind == "spool-registered":
                self._registration_event(event, source)
            elif kind == "spool-collected":
                self._collection_event(event, source)
            elif kind == "recovery-entered":
                _need(p["prior_head_digest"] == self.previous, "reference")
                self.unique("recovery", p["recovery_id"])
                self.writer_ids.add(p["writer_id"])
                self.recovery = True
            elif kind == "loaded":
                self._productive()
                _need(self.state == "reserved" and p["metadata"] == self.m["metadata"], "order")
                for ref, operation in zip(
                    p["daemon_calls"], ("daemon-version", "daemon-info"), strict=True
                ):
                    _need(self.healthy(self.call(ref, operation)), "order")
                _need(self.healthy(self.call(p["image_inspect_call"], "image-inspect")), "order")
                _need(
                    self.observed_image == self.m["expected_image_config_id"]
                    and (
                        self.m["expected_oci_manifest_digest"] is None
                        or self.observed_oci == self.m["expected_oci_manifest_digest"]
                    ),
                    "reference",
                )
                self.prerequisite(p["create_prerequisite"], source, boundary=event["recorded_at"])
                self.state = "loaded"
            elif kind == "created":
                self._productive()
                _need(self.state == "loaded" and self.container_id is not None, "order")
                _need(self.healthy(self.call(p["create_call"], "container-create")), "order")
                _need(self.healthy(self.call(p["inspect_call"], "container-inspect-id")), "order")
                self.state = "created"
            elif kind == "started":
                self._productive()
                _need(
                    self.state == "start-intended" and p["start_call_id"] == self.start_id, "order"
                )
                self.started_identity = (p["pid"], p["start_ticks"])
                self.started_at = event["recorded_at"]
                self.state = "started"
            elif kind == "observed":
                self._productive()
                _need(self.state in ("started", "observed"), "order")
                _need(self.healthy(self.call(p["inspect_call"], "container-inspect-id")), "order")
                self.unique("observation", p["observation_id"])
                _need(
                    self.started_identity == (p["sample"]["pid"], p["sample"]["start_ticks"])
                    and p["sample"]["host_boot_id"] == event["host_boot_id"],
                    "reference",
                )
                _need(
                    self.started_at is not None
                    and self.started_at <= p["sample"]["observed_at"] <= event["recorded_at"],
                    "order",
                )
                self._kernel_refs(p["sample"], source)
                self.prerequisite(p["prerequisite"], source, boundary=event["recorded_at"])
                self.last_observed = digest
                self.state = "observed"
            elif kind == "release-intent":
                self._productive()
                _need(
                    self.state == "observed"
                    and self.release_intent is None
                    and p["observed_event_digest"] == self.last_observed,
                    "order",
                )
                self.prerequisite(p["prerequisite"], source, boundary=event["recorded_at"])
                self.pool.owner(p["release"], source, "release-packet", 16384)
                self.release_intent = digest
                self.state = "release-intended"
            elif kind == "released":
                # This acknowledges an earlier intent, not a new publication.
                # A concurrent failed/oversized result must remain in history.
                _need(not self.recovery and not self.orphaned, "order")
                self._expected_pins()
                _need(
                    self.state == "release-intended"
                    and p["release_intent_event_digest"] == self.release_intent,
                    "order",
                )
                prior_event = self.prior(p["release_intent_event_digest"], "release-intent")
                prior = prior_event["payload"]
                _need(
                    prior["release"] == p["release"] and prior["prerequisite"] == p["prerequisite"],
                    "reference",
                )
                _need(
                    prior_event["recorded_at"] <= p["published_at"] <= event["recorded_at"],
                    "order",
                )
                self.prerequisite(p["prerequisite"], source, boundary=None)
                self.pool.owner(p["release"], source, "release-packet", 16384)
                self.state = "released"
            elif kind == "domain-exited":
                _need(not self.recovery and self.state == "released", "order")
                self.call(p["start_call"], "container-start-attached")
                self.call(p["container_inspect_call"], "container-inspect-id")
                if p["domain_result"] is not None:
                    self.pool.owner(
                        p["domain_result"],
                        source,
                        "domain-result",
                        8 * _MIB if self.m["mode"] == "python-syntax" else 16384,
                    )
                self.domain_exit = digest
                self.state = "domain-exited"
            elif kind == "cleanup":
                self.unique("cleanup", p["cleanup_id"])
                for reference in p["calls"]:
                    self.call(reference)
                if p["final_inspect_call"] is not None:
                    self.call(p["final_inspect_call"], "container-inspect-id")
                if p["state"] == "complete":
                    _need(self.cleanup is None and p["client_reaped"] and self.disposed(), "order")
                    if self.container_id is not None:
                        _need(
                            p["cgroup_empty"] is True and p["final_inspect_call"] is not None,
                            "reference",
                        )
                        _need(self.healthy(self.call(p["final_inspect_call"])), "order")
                    else:
                        _need(
                            not any(
                                c["intent"]["operation"] == "container-create"
                                for c in self.calls.values()
                            ),
                            "order",
                        )
                    self.cleanup = digest
                self.state = "cleanup"
            elif kind == "admitted":
                self._productive()
                _need(
                    self.state == "cleanup"
                    and self.cleanup == p["cleanup_event_digest"]
                    and self.domain_exit == p["domain_exited_event_digest"],
                    "order",
                )
                _need(
                    self.domain_exit is not None
                    and all(self.healthy(c) for c in self.calls.values()),
                    "order",
                )
                domain = self.prior(p["domain_exited_event_digest"], "domain-exited")["payload"]
                _need(
                    domain["domain_validation"] == "valid" and domain["domain_result"] is not None,
                    "order",
                )
                _need(p["result_digest"] == domain["domain_result"]["sha256"], "reference")
                self.prerequisite(p["prerequisite"], source, boundary=event["recorded_at"])
                self.state = "admitted"
            elif kind in ("failed", "orphaned"):
                referenced = [self.call(ref) for ref in p["calls"]]
                if p["primary_error_id"] is not None:
                    _need(
                        any(c["result"]["error_id"] == p["primary_error_id"] for c in referenced),
                        "reference",
                    )
                if p["kernel"] is not None:
                    self.pool.owner(p["kernel"], source, "kernel-raw", 65536)
                    self.kernel_bytes += p["kernel"]["size"]
                    _need(self.kernel_bytes <= _MIB, "limit")
                if p["cleanup_event_digest"] is not None:
                    self.prior(p["cleanup_event_digest"], "cleanup")
                if kind == "failed":
                    _need(not self.orphaned and self.disposed(), "order")
                    _need(
                        self.cleanup is not None
                        or not any(
                            c["intent"]["operation"] == "container-create"
                            for c in self.calls.values()
                        ),
                        "order",
                    )
                    if self.cleanup is not None:
                        _need(p["cleanup_event_digest"] == self.cleanup, "reference")
                else:
                    self.orphaned = self.recovery = True
                    self.orphan_event = digest
                self.state = kind
            elif kind == "reconciled":
                _need(
                    self.orphaned
                    and self.recovery
                    and self.cleanup is not None
                    and self.disposed(),
                    "order",
                )
                _need(
                    p["orphan_event_digest"] == self.orphan_event
                    and p["cleanup_event_digest"] == self.cleanup,
                    "reference",
                )
                self.state = "reconciled"
            else:
                raise JournalValidationError("order")
        self.by_digest[digest] = event
        self.previous = digest

    def report(self) -> JournalStructureReport:
        for event in self.events:
            self.apply(event)
        opaque = self.pool.finish()
        calls = tuple(
            ReplayedCall(c["sequence"], c["result_sequence"], c["intent_view"], c["result_view"])
            for c in self.calls.values()
        )
        account = StructuralAccounting(
            self.pool.supplied,
            len(self.manifest.data) + sum(len(e.data) for e in self.events),
            self.pool.metadata,
            len(calls),
            self.kernel_samples,
            self.observed_bytes,
            self.retained_bytes,
            self.missing_outcome,
            self.missing_output,
            self.unknown_retention,
            self.kernel_bytes,
        )
        return JournalStructureReport(
            "local-structure-only",
            self.manifest,
            self.events,
            cast(DeclaredPhase, self.state),
            self.recovery,
            self.orphaned,
            calls,
            self.pool.copies,
            opaque,
            account,
        )


def replay_journal(
    manifest: bytes, events: tuple[bytes, ...], *, blobs: tuple[EvidenceBlob, ...]
) -> JournalStructureReport:
    _bytes(manifest, 16384)
    supplied = _tuple(events, 128)
    _need(len(supplied) > 0, "order")
    event_bytes = tuple(_bytes(data, 65536) for data in supplied)
    record_size = len(manifest) + sum(len(data) for data in event_bytes)
    pool = _Pool(blobs, record_size)
    parsed = decode_journal_record("manifest", manifest)
    parsed_events = tuple(decode_journal_record("event", data) for data in event_bytes)
    record_hashes = {parsed.sha256.hex(), *(item.sha256.hex() for item in parsed_events)}
    _need(not (record_hashes & set(pool.blobs)), "conflict")
    return _Replay(parsed, parsed_events, pool).report()
