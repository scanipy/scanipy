"""Pure bounded private evidence codecs; prepared bytes are not durable authority.

No filesystem, clock, process, storage or journal operations occur here. See
docs/bhmea/PROCESS-EVIDENCE.md. Stored views and live error chains are private.
"""

from __future__ import annotations

import base64
import hashlib
import itertools
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, TypeAlias, cast

from tools.worker.bounded_process import (
    FrozenInvocation,
    MemoryOutput,
    ProcessOutcome,
    ProcessTransportError,
    ProcessValidationError,
    SpoolOutput,
    StreamEvidence,
    _path,
)

_MIB = 1048576
_INT_MIN = -(2**63)
_INT_MAX = 2**63 - 1
_EMPTY_HASH = hashlib.sha256(b"").hexdigest()
_INV = (_MIB, 4, 2048)
_PAYLOAD = (2048, 4, 64)
_RESULT = (32768, 8, 512)
_ERROR = (8192, 8, 1024)
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
_REASONS = frozenset(
    (
        "exited",
        "timeout",
        "stdin_closed",
        "stdout_limit",
        "stderr_limit",
        "combined_output_limit",
        "spawn_error",
        "io_error",
        "cancelled",
    )
)
_CLEANUPS = frozenset(("not_started", "completed", "incomplete"))


class ProcessEvidenceError(ValueError):
    """Fixed private-validation status, with no raw evidence in the message."""


def _need(condition: bool) -> None:
    if not condition:
        raise ProcessEvidenceError("invalid process evidence")


class CliOperation(Enum):
    DAEMON_VERSION = "daemon-version"
    DAEMON_INFO = "daemon-info"
    IMAGE_INSPECT = "image-inspect"
    CONTAINER_CREATE = "container-create"
    CONTAINER_INSPECT_ID = "container-inspect-id"
    CONTAINER_INSPECT_NAME = "container-inspect-name"
    CONTAINER_START_ATTACHED = "container-start-attached"
    CONTAINER_KILL = "container-kill"
    CONTAINER_WAIT = "container-wait"
    CONTAINER_REMOVE = "container-remove"


_OPERATIONS = (
    (CliOperation.DAEMON_VERSION, "daemon-version"),
    (CliOperation.DAEMON_INFO, "daemon-info"),
    (CliOperation.IMAGE_INSPECT, "image-inspect"),
    (CliOperation.CONTAINER_CREATE, "container-create"),
    (CliOperation.CONTAINER_INSPECT_ID, "container-inspect-id"),
    (CliOperation.CONTAINER_INSPECT_NAME, "container-inspect-name"),
    (CliOperation.CONTAINER_START_ATTACHED, "container-start-attached"),
    (CliOperation.CONTAINER_KILL, "container-kill"),
    (CliOperation.CONTAINER_WAIT, "container-wait"),
    (CliOperation.CONTAINER_REMOVE, "container-remove"),
)

StoredValue: TypeAlias = "None | bool | int | str | StoredArray | StoredObject"
StoredArray: TypeAlias = tuple[Literal["array"], tuple[StoredValue, ...]]
StoredObject: TypeAlias = tuple[Literal["object"], tuple[tuple[str, StoredValue], ...]]
StoredBlobRef: TypeAlias = StoredObject
StoredInvocation: TypeAlias = StoredObject
StoredCallIntent: TypeAlias = StoredObject
StoredCallRef: TypeAlias = StoredObject
StoredCallResult: TypeAlias = StoredObject
StoredOutcome: TypeAlias = StoredObject
StoredOutput: TypeAlias = StoredObject
StoredStreamEvidence: TypeAlias = StoredObject
StoredCustody: TypeAlias = StoredObject
StoredErrorGraph: TypeAlias = StoredObject
StoredErrorNode: TypeAlias = StoredObject
StoredArgument: TypeAlias = StoredObject
StoredOmission: TypeAlias = StoredObject
StoredOmissionOverflow: TypeAlias = StoredObject


@dataclass(frozen=True, slots=True, repr=False)
class RuntimeCallBinding:
    attempt_id: str
    operation_id: str
    call_id: str
    call_sequence: int
    operation: CliOperation
    target: str | None


@dataclass(frozen=True, slots=True, repr=False)
class EvidenceBlob:
    data: bytes
    sha256: bytes


@dataclass(frozen=True, slots=True, repr=False)
class PreparedCallIntent:
    binding: RuntimeCallBinding
    invocation: FrozenInvocation
    invocation_blob: EvidenceBlob
    payload: bytes


@dataclass(frozen=True, slots=True, repr=False)
class PreparedCallResult:
    call_ref: StoredCallRef
    payload: bytes
    blobs: tuple[EvidenceBlob, ...]


def _text(value: object, maximum: int, *, empty: bool = True) -> str:
    _need(type(value) is str)
    value = cast(str, value)
    _need(len(value) <= maximum and (empty or len(value) > 0) and "\0" not in value)
    try:
        _need(len(value.encode("utf-8")) <= maximum)
    except UnicodeError as error:
        raise ProcessEvidenceError("invalid process evidence text") from error
    return value


def _integer(value: object, low: int = _INT_MIN, high: int = _INT_MAX) -> int:
    _need(type(value) is int and low <= value <= high)
    return cast(int, value)


def _binary(value: object, maximum: int) -> bytes:
    _need(type(value) is bytes and len(value) <= maximum)
    return cast(bytes, value)


def _digest(value: object) -> bytes:
    data = _binary(value, 32)
    _need(len(data) == 32)
    return data


def _hex(value: object) -> str:
    text = _text(value, 64)
    _need(_HEX.fullmatch(text) is not None)
    return text


def _uuid(value: object) -> str:
    text = _text(value, 36)
    _need(_UUID.fullmatch(text) is not None)
    return text


def _choice(value: object, choices: frozenset[str] | set[str]) -> str:
    text = _text(value, 64)
    _need(text in choices)
    return text


def _items(value: object, maximum: int) -> tuple[tuple[object, object], ...]:
    """Bound even an accidentally changing exact dict before making a lookup."""
    _need(type(value) is dict and len(value) <= maximum)
    try:
        pairs = tuple(itertools.islice(dict.items(cast(dict[Any, Any], value)), maximum + 1))
    except RuntimeError as error:
        raise ProcessEvidenceError("changing process evidence") from error
    _need(len(pairs) <= maximum and len(pairs) == len(cast(dict[Any, Any], value)))
    return pairs


def _record(value: object, cls: type[Any], fields: tuple[str, ...]) -> dict[str, Any]:
    _need(type(value) is cls)
    try:
        if "__slots__" in cls.__dict__:
            return {name: cls.__dict__[name].__get__(value, cls) for name in fields}
        storage = cls.__dict__["__dict__"].__get__(value, cls)
    except (AttributeError, KeyError, TypeError) as error:
        raise ProcessEvidenceError("invalid process evidence record") from error
    pairs = _items(storage, len(fields))
    _need(len(pairs) == len(fields))
    for key, _ in pairs:
        _need(type(key) is str and len(key) <= 64 and key in fields)
    result = dict(pairs)
    _need(set(result) == set(fields))
    return cast(dict[str, Any], result)


def _shape(value: Any, fields: tuple[str, ...]) -> dict[str, Any]:  # noqa: ANN401
    _need(type(value) is dict and len(value) == len(fields) and set(value) == set(fields))
    return cast(dict[str, Any], value)


def _array(value: Any, minimum: int, maximum: int) -> list[Any]:  # noqa: ANN401
    _need(type(value) is list and minimum <= len(value) <= maximum)
    return cast(list[Any], value)


def _tuple(value: object, minimum: int, maximum: int) -> tuple[Any, ...]:
    _need(type(value) is tuple and minimum <= len(value) <= maximum)
    return cast(tuple[Any, ...], value)


def _encoded_text_size(text: str) -> int:
    return (
        2
        + len(text.encode())
        + sum(1 if char in '\\"\b\f\n\r\t' else 5 if ord(char) < 32 else 0 for char in text)
    )


def _snapshot_json(value: Any, limits: tuple[int, int, int]) -> Any:  # noqa: ANN401
    """Count child/key slots before expansion; allocate only a bounded copy."""
    maximum, max_depth, max_values = limits
    values = 1
    size = 0

    def charge(amount: int) -> None:
        nonlocal size
        size += amount
        _need(size <= maximum)

    def visit(item: Any, parent_depth: int) -> Any:  # noqa: ANN401
        nonlocal values
        kind = type(item)
        if item is None:
            charge(4)
        elif kind is bool:
            charge(4 if item else 5)
        elif kind is int:
            _integer(item)
            charge(len(str(item)))
        elif kind is str:
            _text(item, maximum)
            charge(_encoded_text_size(item))
        elif kind is list or kind is dict:
            depth = parent_depth + 1
            _need(depth <= max_depth)
            count = len(item)
            values += count * (2 if kind is dict else 1)
            _need(values <= max_values)
            charge(2 + max(0, count - 1) + (count if kind is dict else 0))
            if kind is list:
                children = item[: max_values + 1]
                _need(len(children) == count)
                return [visit(child, depth) for child in children]
            pairs = _items(item, max_values)
            _need(len(pairs) == count)
            result: dict[str, Any] = {}
            for key, child in pairs:
                text = _text(key, maximum)
                charge(_encoded_text_size(text))
                result[text] = visit(child, depth)
            return result
        else:
            raise ProcessEvidenceError("invalid process evidence primitive")
        return item

    return visit(value, 0)


def _canonical(value: Any, limits: tuple[int, int, int]) -> bytes:  # noqa: ANN401
    copy = _snapshot_json(value, limits)
    return json.dumps(
        copy, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _lexical(data: bytes, limits: tuple[int, int, int]) -> None:
    """Linear pre-parser bound including keys and integer token magnitudes."""
    maximum, max_depth, max_values = limits
    _binary(data, maximum)
    depth = values = index = 0
    while index < len(data):
        byte = data[index]
        if byte in b" \t\r\n,:]}":
            if byte in b"]}":
                depth -= 1
                _need(depth >= 0)
            index += 1
            continue
        values += 1
        _need(values <= max_values)
        if byte in b"[{":
            depth += 1
            _need(depth <= max_depth)
            index += 1
        elif byte == 34:
            index += 1
            while index < len(data) and data[index] != 34:
                if data[index] == 92:
                    index += 1
                index += 1
            _need(index < len(data))
            index += 1
        elif byte == 45 or 48 <= byte <= 57:
            start = index
            if byte == 45:
                index += 1
            digits = index
            while index < len(data) and 48 <= data[index] <= 57:
                index += 1
            length = index - digits
            _need(1 <= length <= 19)
            magnitude = data[digits:index]
            ceiling = b"9223372036854775808" if byte == 45 else b"9223372036854775807"
            _need(length < 19 or magnitude <= ceiling)
            _need(index == len(data) or data[index] in b" \t\r\n,]}")
            _need(index > start)
        else:
            matched = False
            for token in (b"true", b"false", b"null"):
                if data.startswith(token, index):
                    index += len(token)
                    _need(index == len(data) or data[index] in b" \t\r\n,]}")
                    matched = True
                    break
            _need(matched)
    _need(depth == 0)


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _need(key not in result)
        result[key] = value
    return result


def _decode(data: bytes, limits: tuple[int, int, int]) -> dict[str, Any]:
    _lexical(data, limits)
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ProcessEvidenceError("invalid process evidence JSON") from error
    _need(type(value) is dict)
    _need(_canonical(value, limits) == data)
    return cast(dict[str, Any], value)


def _freeze(value: Any) -> Any:  # noqa: ANN401
    if type(value) is dict:
        return ("object", tuple((key, _freeze(value[key])) for key in sorted(value)))
    if type(value) is list:
        return ("array", tuple(_freeze(member) for member in value))
    return value


def _operation(value: object) -> str:
    for member, literal in _OPERATIONS:
        if value is member:
            return literal
    raise ProcessEvidenceError("invalid process evidence operation")


def cli_operation_from_wire(value: str) -> CliOperation:
    literal = _text(value, 64)
    for member, candidate in _OPERATIONS:
        if literal == candidate:
            return member
    raise ProcessEvidenceError("invalid process evidence operation")


def _target(operation: str, target: Any, attempt: str | None = None) -> None:  # noqa: ANN401
    cli_operation_from_wire(operation)
    if operation in ("daemon-version", "daemon-info"):
        _need(target is None)
    elif operation == "image-inspect":
        text = _text(target, 71)
        _need(text.startswith("sha256:"))
        _hex(text[7:])
    elif operation in ("container-create", "container-inspect-name"):
        text = _text(target, 48)
        _need(re.fullmatch(r"scanipy-runtime-[0-9a-f]{32}", text) is not None)
        if attempt is not None:
            _need(text == "scanipy-runtime-" + attempt.replace("-", ""))
    else:
        _hex(target)


def _binding(value: RuntimeCallBinding) -> tuple[RuntimeCallBinding, dict[str, Any]]:
    fields = _record(
        value,
        RuntimeCallBinding,
        ("attempt_id", "operation_id", "call_id", "call_sequence", "operation", "target"),
    )
    for name in ("attempt_id", "operation_id", "call_id"):
        _uuid(fields[name])
    _integer(fields["call_sequence"], 1, 16)
    literal = _operation(fields["operation"])
    _target(literal, fields["target"], fields["attempt_id"])
    clone = RuntimeCallBinding(**fields)
    fields["operation"] = literal
    return clone, fields


def _cwd(value: Any) -> str:  # noqa: ANN401
    from pathlib import PosixPath

    text = _text(value, 4096, empty=False)
    try:
        _path(PosixPath(text))
    except ProcessValidationError as error:
        raise ProcessEvidenceError("invalid process evidence path") from error
    return text


def _invocation_fields(document: dict[str, Any]) -> None:
    _shape(document, ("schema", "argv", "environment", "cwd", "stdin_bytes", "stdin_sha256"))
    _need(document["schema"] == "scanipy-process-invocation/1")
    arguments = _array(document["argv"], 1, 256)
    _need(sum(len(_text(item, 8192).encode()) + 1 for item in arguments) <= 65536)
    _need(arguments[0].startswith("/"))
    environment = _array(document["environment"], 0, 64)
    previous: str | None = None
    size = 0
    for row in environment:
        _array(row, 2, 2)
        key = _text(row[0], 128, empty=False)
        value = _text(row[1], 8192)
        _need("=" not in key and (previous is None or previous < key))
        previous = key
        size += len(key.encode()) + len(value.encode()) + 2
    _need(size <= 65536)
    _cwd(document["cwd"])
    _integer(document["stdin_bytes"], 0, 4 * _MIB)
    _hex(document["stdin_sha256"])


def _invocation(value: FrozenInvocation) -> dict[str, Any]:
    fields = _record(
        value, FrozenInvocation, ("argv", "environment", "cwd", "stdin_bytes", "stdin_sha256")
    )
    argv = [_text(item, 8192) for item in _tuple(fields["argv"], 1, 256)]
    env = []
    for row in _tuple(fields["environment"], 0, 64):
        pair = _tuple(row, 2, 2)
        env.append([_text(pair[0], 128, empty=False), _text(pair[1], 8192)])
    document = dict(
        fields,
        schema="scanipy-process-invocation/1",
        argv=argv,
        environment=env,
        stdin_sha256=_digest(fields["stdin_sha256"]).hex(),
    )
    _invocation_fields(document)
    return document


def encode_invocation(invocation: FrozenInvocation) -> bytes:
    return _canonical(_invocation(invocation), _INV)


def decode_invocation(data: bytes) -> StoredInvocation:
    document = _decode(data, _INV)
    _invocation_fields(document)
    return cast(StoredInvocation, _freeze(document))


def _blob_ref(data: bytes) -> dict[str, Any]:
    digest = hashlib.sha256(data).hexdigest()
    return {"sha256": digest, "size": len(data), "key": "blobs/" + digest}


def _reference(value: Any, maximum: int) -> dict[str, Any]:  # noqa: ANN401
    row = _shape(value, ("sha256", "size", "key"))
    digest = _hex(row["sha256"])
    size = _integer(row["size"], 0, maximum)
    _need(type(row["key"]) is str and row["key"] == "blobs/" + digest)
    _need(size != 0 or digest == _EMPTY_HASH)
    return row


def _intent_fields(document: dict[str, Any]) -> None:
    _shape(document, ("call_id", "call_sequence", "operation", "target", "invocation"))
    _uuid(document["call_id"])
    _integer(document["call_sequence"], 1, 16)
    _target(_text(document["operation"], 64), document["target"])
    _reference(document["invocation"], _MIB)


def decode_call_intent(data: bytes) -> StoredCallIntent:
    document = _decode(data, _PAYLOAD)
    _intent_fields(document)
    return cast(StoredCallIntent, _freeze(document))


def _call_ref_fields(document: dict[str, Any]) -> None:
    _shape(document, ("call_id", "operation", "outcome"))
    _uuid(document["call_id"])
    cli_operation_from_wire(document["operation"])
    _reference(document["outcome"], 32768)


def decode_call_ref(data: bytes) -> StoredCallRef:
    document = _decode(data, _PAYLOAD)
    _call_ref_fields(document)
    return cast(StoredCallRef, _freeze(document))


def prepare_call_intent(
    binding: RuntimeCallBinding, invocation: FrozenInvocation
) -> PreparedCallIntent:
    clone, fields = _binding(binding)
    document = _invocation(invocation)
    cwd = document["cwd"]
    _need("\\" not in cwd and all(ord(char) >= 32 and not 127 <= ord(char) <= 159 for char in cwd))
    _need(
        cwd.startswith("/")
        and not cwd.startswith("//")
        and all(part not in ("", ".", "..") for part in cwd.split("/")[1:])
    )
    parent, _, tail = cwd.rpartition("/")
    _need(parent != "" and tail == fields["attempt_id"])
    environment = {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
        "HOME": cwd + "/cli-home",
        "TMPDIR": cwd + "/cli-tmp",
        "PATH": cwd + "/cli-bin",
        "DOCKER_API_VERSION": "1.52",
        "DOCKER_CLI_HOOKS": "false",
        "DOCKER_CLI_HINTS": "false",
        "OTEL_SDK_DISABLED": "true",
    }
    for key in ("HOME", "TMPDIR", "PATH"):
        _text(environment[key], 4096)
    _need(document["environment"] == [list(pair) for pair in sorted(environment.items())])
    _need(
        sum(len(key.encode()) + len(value.encode()) + 2 for key, value in environment.items())
        <= 16384
    )
    raw = _canonical(document, _INV)
    payload = _canonical(
        {key: fields[key] for key in ("call_id", "call_sequence", "operation", "target")}
        | {"invocation": _blob_ref(raw)},
        _PAYLOAD,
    )
    _need(len(raw) + len(payload) <= 512 * 1024)
    private = FrozenInvocation(
        tuple(document["argv"]),
        tuple(tuple(pair) for pair in document["environment"]),
        cwd,
        document["stdin_bytes"],
        bytes.fromhex(document["stdin_sha256"]),
    )
    return PreparedCallIntent(
        clone, private, EvidenceBlob(raw, hashlib.sha256(raw).digest()), payload
    )


_STREAM_FIELDS = ("observed_bytes", "retained_bytes", "retained_sha256", "eof", "truncated")
_OUTCOME_FIELDS = (
    "invocation",
    "reason",
    "pid",
    "pgid",
    "returncode",
    "stdin_sent_bytes",
    "stdout",
    "stderr",
    "elapsed_ms",
    "cleanup",
)


def _stream_fields(row: dict[str, Any]) -> None:
    _shape(row, _STREAM_FIELDS)
    observed = _integer(row["observed_bytes"], 0, 129 * _MIB + 65536)
    _need(type(row["eof"]) is bool and type(row["truncated"]) is bool)
    if row["retained_bytes"] is None:
        _need(row["retained_sha256"] is None)
    else:
        retained = _integer(row["retained_bytes"], 0, observed)
        _hex(row["retained_sha256"])
        _need(retained == observed or row["truncated"])


def _stream(value: StreamEvidence) -> dict[str, Any]:
    fields = _record(value, StreamEvidence, _STREAM_FIELDS)
    if fields["retained_sha256"] is not None:
        fields["retained_sha256"] = _digest(fields["retained_sha256"]).hex()
    _stream_fields(fields)
    return fields


def _output(value: object) -> dict[str, Any] | None:
    if value is None:
        return None
    if type(value) is MemoryOutput:
        fields = _record(value, MemoryOutput, ("evidence", "data"))
        data = _binary(fields["data"], 16 * _MIB)
        reported = _stream(fields["evidence"])
        _need(reported["retained_bytes"] == len(data))
        _need(reported["retained_sha256"] == hashlib.sha256(data).hexdigest())
        return {"kind": "memory", "reported": reported, "data": data, "path": None}
    _need(type(value) is SpoolOutput)
    fields = _record(value, SpoolOutput, ("evidence", "path"))
    reported = _stream(fields["evidence"])
    try:
        private_path = _path(fields["path"])
    except ProcessValidationError as error:
        raise ProcessEvidenceError("invalid process evidence path") from error
    return {"kind": "spool", "reported": reported, "data": None, "path": str(private_path)}


def _outcome_fields(row: dict[str, Any], input_size: int | None) -> None:
    _shape(row, _OUTCOME_FIELDS)
    _choice(row["reason"], _REASONS)
    _choice(row["cleanup"], _CLEANUPS)
    if row["pid"] is None:
        _need(row["pgid"] is None and row["returncode"] is None and row["cleanup"] == "not_started")
    else:
        pid = _integer(row["pid"], 1, 2**31 - 1)
        _need(_integer(row["pgid"], 1, 2**31 - 1) == pid and row["cleanup"] != "not_started")
    if row["returncode"] is not None:
        _integer(row["returncode"], -(2**31), 2**31 - 1)
    _integer(row["stdin_sent_bytes"], 0, 4 * _MIB if input_size is None else input_size)
    _integer(row["elapsed_ms"], 0)
    if row["cleanup"] == "completed":
        _need(row["returncode"] is not None)
        for name in ("stdout", "stderr"):
            output = row[name]
            _need(output is not None and output["reported"]["retained_bytes"] is not None)
            if row["reason"] == "exited":
                if input_size is not None:
                    _need(row["stdin_sent_bytes"] == input_size)
                _need(output["reported"]["eof"] and not output["reported"]["truncated"])


def _outcome(value: ProcessOutcome) -> dict[str, Any]:
    row = _record(value, ProcessOutcome, _OUTCOME_FIELDS)
    row["invocation"] = _invocation(row["invocation"])
    for name in ("stdout", "stderr"):
        row[name] = _output(row[name])
    _outcome_fields(row, row["invocation"]["stdin_bytes"])
    return row


def _exception(value: object) -> BaseException:
    _need(issubclass(type(value), BaseException))
    return cast(BaseException, value)


def _error_field(error: BaseException, name: str) -> Any:  # noqa: ANN401
    # Use the base-owned C descriptor even for a hostile subclass property.
    return BaseException.__dict__[name].__get__(error, BaseException)


def _carrier(error: BaseException | None) -> dict[str, Any] | None:
    if error is None:
        return None
    _exception(error)
    selected = error if type(error) is ProcessTransportError else _error_field(error, "__cause__")
    if type(selected) is not ProcessTransportError:
        return None
    storage = _error_field(selected, "__dict__")
    pairs = _items(storage, 3)
    _need(2 <= len(pairs) <= 3)
    for key, _ in pairs:
        _need(type(key) is str and len(key) <= 32 and key.isascii())
        _need(key in ("outcome", "_owned_child", "__notes__"))
    fields = dict(pairs)
    _need("outcome" in fields and "_owned_child" in fields)
    # Child ownership and notes are deliberately opaque, not touched or copied.
    return _outcome(cast(ProcessOutcome, fields["outcome"]))


def _stored_output(row: Any) -> None:  # noqa: ANN401
    if row is None:
        return
    _shape(row, ("kind", "reported", "path", "custody"))
    kind = _choice(row["kind"], {"memory", "spool"})
    _stream_fields(row["reported"])
    custody = _shape(row["custody"], ("state", "bytes"))
    state = _choice(custody["state"], {"verified", "unavailable", "mismatch", "diagnostic-copy"})
    reference = custody["bytes"]
    if state == "unavailable":
        _need(reference is None)
    else:
        _reference(reference, 16 * _MIB)
    known = row["reported"]["retained_bytes"] is not None
    if state == "diagnostic-copy":
        _need(not known)
    elif state in ("verified", "mismatch"):
        _need(known)
        matches = (
            reference["size"] == row["reported"]["retained_bytes"]
            and reference["sha256"] == row["reported"]["retained_sha256"]
        )
        _need(matches if state == "verified" else not matches)
    if kind == "memory":
        _need(row["path"] is None and state == "verified")
    else:
        _reference(row["path"], 4096)
        _need(row["path"]["size"] > 0)


def _result_fields(document: dict[str, Any]) -> None:
    _shape(
        document,
        (
            "schema",
            "scope",
            "attempt_id",
            "operation_id",
            "call_id",
            "call_sequence",
            "operation",
            "target",
            "intent_event_digest",
            "requested_invocation",
            "outcome",
            "unavailable_reason",
            "error_id",
            "error_graph",
        ),
    )
    _need(
        document["schema"] == "scanipy-runtime-call/1" and document["scope"] == "host-docker-client"
    )
    for name in ("attempt_id", "operation_id", "call_id"):
        _uuid(document[name])
    _integer(document["call_sequence"], 1, 16)
    _target(_text(document["operation"], 64), document["target"], document["attempt_id"])
    _hex(document["intent_event_digest"])
    _reference(document["requested_invocation"], _MIB)
    if document["error_id"] is None:
        _need(document["error_graph"] is None)
    else:
        _uuid(document["error_id"])
        _reference(document["error_graph"], 8192)
    row = document["outcome"]
    if row is None:
        _need(document["error_id"] is not None)
        _choice(document["unavailable_reason"], {"validation-refused", "exception-no-outcome"})
    else:
        _need(document["unavailable_reason"] is None)
        _shape(row, _OUTCOME_FIELDS)
        _reference(row["invocation"], _MIB)
        for name in ("stdout", "stderr"):
            _stored_output(row[name])
        _outcome_fields(row, None)


def decode_call_result(data: bytes) -> StoredCallResult:
    document = _decode(data, _RESULT)
    _result_fields(document)
    return cast(StoredCallResult, _freeze(document))


_CLASS_CODES = (
    (BaseException, "base-exception"),
    (Exception, "exception"),
    (RuntimeError, "runtime-error"),
    (ValueError, "value-error"),
    (TypeError, "type-error"),
    (AttributeError, "attribute-error"),
    (MemoryError, "memory-error"),
    (EOFError, "eof-error"),
    (OSError, "os-error"),
    (FileNotFoundError, "file-not-found"),
    (PermissionError, "permission-error"),
    (TimeoutError, "timeout-error"),
    (InterruptedError, "interrupted-error"),
    (KeyboardInterrupt, "keyboard-interrupt"),
    (SystemExit, "system-exit"),
    (ExceptionGroup, "exception-group"),
    (BaseExceptionGroup, "base-exception-group"),
    (ProcessValidationError, "process-validation"),
    (ProcessTransportError, "process-transport"),
)
_CLASSES = frozenset([code for _, code in _CLASS_CODES] + ["opaque"])
_GROUPS = frozenset(("exception-group", "base-exception-group"))
_LOSSES = {
    "class": frozenset(("opaque-type",)),
    "args": frozenset(("unsupported-primitive", "bytes", "items")),
    "cause": frozenset(("depth", "nodes", "edges", "bytes", "items")),
    "context": frozenset(("depth", "nodes", "edges", "bytes", "items")),
    "group": frozenset(("depth", "nodes", "edges", "bytes", "items")),
}


def _argument(value: Any) -> dict[str, Any] | None:  # noqa: ANN401
    kind = type(value)
    if value is None:
        return {"kind": "null"}
    if kind is bool:
        return {"kind": "bool", "value": value}
    if kind is int:
        if _INT_MIN <= value <= _INT_MAX:
            return {"kind": "int", "value": value}
    elif kind is str:
        try:
            return {"kind": "text", "value": _text(value, 512)}
        except ProcessEvidenceError:
            return None
    elif kind is bytes and len(value) <= 512:
        return {"kind": "bytes", "base64": base64.b64encode(value).decode("ascii")}
    return None


def _argument_fields(row: Any) -> None:  # noqa: ANN401
    _need(type(row) is dict and "kind" in row)
    kind = _choice(row["kind"], {"text", "bytes", "int", "bool", "null"})
    if kind == "null":
        _shape(row, ("kind",))
    elif kind == "bytes":
        _shape(row, ("kind", "base64"))
        text = _text(row["base64"], 684)
        try:
            raw = base64.b64decode(text, validate=True)
        except (ValueError, UnicodeError) as error:
            raise ProcessEvidenceError("invalid process evidence binary argument") from error
        _need(len(raw) <= 512 and base64.b64encode(raw).decode("ascii") == text)
    else:
        _shape(row, ("kind", "value"))
        if kind == "text":
            _text(row["value"], 512)
        elif kind == "int":
            _integer(row["value"])
        else:
            _need(type(row["value"]) is bool)


def _overflow() -> dict[str, Any]:
    return {"additional_details_at_least": 1, "exact_count": None, "enumeration": "incomplete"}


def _graph_fields(document: dict[str, Any]) -> None:
    _shape(document, ("schema", "error_id", "root", "nodes", "omissions", "omission_overflow"))
    _need(document["schema"] == "scanipy-private-error-graph/1")
    _uuid(document["error_id"])
    _integer(document["root"], 0, 0)
    nodes = _array(document["nodes"], 1, 32)
    omissions = _array(document["omissions"], 0, 32)
    overflow = document["omission_overflow"]
    if overflow is not None:
        _shape(overflow, ("additional_details_at_least", "exact_count", "enumeration"))
        _integer(overflow["additional_details_at_least"], 1, 1)
        _need(overflow["exact_count"] is None and overflow["enumeration"] == "incomplete")
    for omission in omissions:
        _shape(omission, ("node", "field", "reason"))
        if omission["node"] is not None:
            _integer(omission["node"], 0, len(nodes) - 1)
        field = _choice(omission["field"], set(_LOSSES))
        _choice(omission["reason"], _LOSSES[field])
    edges = arguments = argument_bytes = 0
    for index, node in enumerate(nodes):
        _shape(
            node, ("id", "class", "args", "cause", "context", "suppress_context", "group_children")
        )
        _integer(node["id"], index, index)
        code = _choice(node["class"], _CLASSES)
        _need(type(node["suppress_context"]) is bool)
        args = _array(node["args"], 0, 8)
        arguments += len(args)
        _need(arguments <= 32)
        for argument in args:
            _argument_fields(argument)
            argument_bytes += len(_canonical(argument, (8192, 2, 8)))
            _need(argument_bytes <= 2048)
        group = node["group_children"]
        if code in _GROUPS:
            _need(group is not None)
        elif code != "opaque":
            _need(group is None)
        if group is not None:
            _array(group, 0, 32)
            if not group:
                _need(
                    overflow is not None
                    or any(loss["node"] == index and loss["field"] == "group" for loss in omissions)
                )
        if code == "opaque":
            _need(
                overflow is not None
                or any(loss["node"] == index and loss["field"] == "class" for loss in omissions)
            )
        refs = [node["cause"], node["context"]] + ([] if group is None else group)
        for ref in refs:
            if ref is not None:
                _integer(ref, 0, len(nodes) - 1)
                edges += 1
                _need(edges <= 96)
        if group is not None:
            _need(all(ref is not None for ref in group))
    for omission in omissions:
        if omission["field"] == "class" and omission["node"] is not None:
            _need(nodes[omission["node"]]["class"] == "opaque")
    seen: set[int] = set()

    def discover(index: int, depth: int) -> None:
        if index in seen:
            return
        _need(depth <= 16 and index == len(seen))
        seen.add(index)
        node = nodes[index]
        for ref in [node["cause"], node["context"]] + (node["group_children"] or []):
            if ref is not None:
                discover(ref, depth + 1)

    discover(0, 0)
    _need(len(seen) == len(nodes))


def decode_error_graph(data: bytes) -> StoredErrorGraph:
    document = _decode(data, _ERROR)
    _graph_fields(document)
    return cast(StoredErrorGraph, _freeze(document))


class _Graph:
    """Bounded first-discovery DFS. Live exceptions are never modified."""

    def __init__(self, error_id: str) -> None:
        self.document: dict[str, Any] = {
            "schema": "scanipy-private-error-graph/1",
            "error_id": error_id,
            "root": 0,
            "nodes": [],
            "omissions": [],
            "omission_overflow": None,
        }
        self.seen: dict[int, int] = {}
        self.edges = 0
        self.inspected_args = 0
        self.argument_bytes = 0
        self.stopped = False

    def _stop(self) -> None:
        self.document["omission_overflow"] = _overflow()
        self.stopped = True

    def _is_stopped(self) -> bool:
        return self.stopped

    def _fits(self) -> bool:
        try:
            # Reserve the footer and closure before every retained addition.
            _snapshot_json(self.document, (8192 - 1024, 8, 1024 - 32))
        except ProcessEvidenceError:
            return False
        return True

    def _omit(self, node: int, field: str, reason: str) -> None:
        if self._is_stopped():
            return
        losses = self.document["omissions"]
        if len(losses) == 32:
            self._stop()
            return
        losses.append({"node": node, "field": field, "reason": reason})
        if not self._fits():
            losses.pop()
            self._stop()

    @staticmethod
    def _node(error: BaseException, index: int) -> dict[str, Any]:
        code = "opaque"
        for cls, literal in _CLASS_CODES:
            if type(error) is cls:
                code = literal
                break
        suppression = _error_field(error, "__suppress_context__")
        _need(type(suppression) is bool)
        group = issubclass(type(error), BaseExceptionGroup)
        return {
            "id": index,
            "class": code,
            "args": [],
            "cause": None,
            "context": None,
            "suppress_context": suppression,
            "group_children": [] if group else None,
        }

    def _edge(self, parent: int, field: str, error: BaseException, depth: int) -> None:
        if self._is_stopped():
            return
        if self.edges == 96:
            self._omit(parent, field, "edges")
            return
        identity = id(error)
        existing = self.seen.get(identity)
        fresh = existing is None
        if fresh and depth > 16:
            self._omit(parent, field, "depth")
            return
        nodes = self.document["nodes"]
        if fresh and len(nodes) == 32:
            self._omit(parent, field, "nodes")
            return
        index = len(nodes) if fresh else cast(int, existing)
        if fresh:
            nodes.append(self._node(error, index))
        if field == "group":
            nodes[parent]["group_children"].append(index)
        else:
            nodes[parent][field] = index
        if not self._fits():
            if field == "group":
                nodes[parent]["group_children"].pop()
            else:
                nodes[parent][field] = None
            if fresh:
                nodes.pop()
            self._omit(parent, field, "bytes")
            return
        self.edges += 1
        if fresh:
            self.seen[identity] = index
            self._visit(error, index, depth)

    def _visit(self, error: BaseException, index: int, depth: int) -> None:
        node = self.document["nodes"][index]
        if node["class"] == "opaque":
            self._omit(index, "class", "opaque-type")
        if self._is_stopped():
            return
        args = _error_field(error, "args")
        _need(type(args) is tuple)
        allowance = min(8, 32 - self.inspected_args)
        prefix = args[:allowance]
        if len(args) > allowance:
            self._omit(index, "args", "items")
        for value in prefix:
            if self._is_stopped():
                return
            self.inspected_args += 1
            argument = _argument(value)
            if argument is None:
                oversized = type(value) in (str, bytes) and len(value) > 512
                self._omit(index, "args", "bytes" if oversized else "unsupported-primitive")
                continue
            size = len(_canonical(argument, (8192, 2, 8)))
            if self.argument_bytes + size > 2048:
                self._omit(index, "args", "bytes")
                continue
            node["args"].append(argument)
            if not self._fits():
                node["args"].pop()
                self._omit(index, "args", "bytes")
                continue
            self.argument_bytes += size
        for field in ("cause", "context"):
            if self._is_stopped():
                return
            child = _error_field(error, "__" + field + "__")
            if child is not None:
                self._edge(index, field, _exception(child), depth + 1)
        if self._is_stopped() or node["group_children"] is None:
            return
        children = BaseExceptionGroup.__dict__["exceptions"].__get__(error, BaseExceptionGroup)
        _need(type(children) is tuple)
        allowance = min(32, 96 - self.edges)
        prefix = children[:allowance]
        if len(children) > allowance:
            self._omit(index, "group", "items" if len(children) > 32 else "edges")
        for child in prefix:
            if self._is_stopped():
                return
            self._edge(index, "group", _exception(child), depth + 1)

    def encode(self, error: BaseException) -> bytes:
        self.document["nodes"].append(self._node(error, 0))
        self.seen[id(error)] = 0
        _need(self._fits())
        self._visit(error, 0, 0)
        _graph_fields(self.document)
        return _canonical(self.document, _ERROR)


class _Pack:
    """One-call limits only; the future store owns cumulative reservation."""

    def __init__(self) -> None:
        self.blobs: dict[str, EvidenceBlob] = {}
        self.metadata = 0
        self.physical = 0

    def charge_metadata(self, size: int) -> None:
        self.metadata += size
        _need(self.metadata <= 512 * 1024)

    def add(self, data: bytes, maximum: int, *, metadata: bool = True) -> dict[str, Any]:
        raw = _binary(data, maximum)
        if metadata:
            self.charge_metadata(len(raw))
        digest = hashlib.sha256(raw).digest()
        key = digest.hex()
        previous = self.blobs.get(key)
        if previous is None:
            _need(len(self.blobs) < 8)
            self.physical += len(raw)
            _need(self.physical <= 32 * _MIB)
            self.blobs[key] = EvidenceBlob(raw, digest)
        else:
            _need(previous.data == raw)
        return {"sha256": key, "size": len(raw), "key": "blobs/" + key}


def _prepared_intent(value: PreparedCallIntent) -> PreparedCallIntent:
    fields = _record(
        value, PreparedCallIntent, ("binding", "invocation", "invocation_blob", "payload")
    )
    blob = _record(fields["invocation_blob"], EvidenceBlob, ("data", "sha256"))
    raw = _binary(blob["data"], _MIB)
    digest = _digest(blob["sha256"])
    payload = _binary(fields["payload"], 2048)
    expected = prepare_call_intent(fields["binding"], fields["invocation"])
    _need(
        raw == expected.invocation_blob.data
        and digest == expected.invocation_blob.sha256
        and payload == expected.payload
    )
    return expected


def _pack_output(
    row: dict[str, Any] | None, readback: bytes | None, pack: _Pack
) -> dict[str, Any] | None:
    if row is None:
        _need(readback is None)
        return None
    reported = row["reported"]
    if row["kind"] == "memory":
        _need(readback is None)
        reference = pack.add(row["data"], 16 * _MIB, metadata=False)
        path = None
        state = "verified"
    else:
        path = pack.add(row["path"].encode(), 4096)
        if readback is None:
            reference = None
            state = "unavailable"
        else:
            reference = pack.add(readback, 16 * _MIB, metadata=False)
            if reported["retained_bytes"] is None:
                state = "diagnostic-copy"
            elif (
                reported["retained_bytes"] == len(readback)
                and reported["retained_sha256"] == reference["sha256"]
            ):
                state = "verified"
            else:
                state = "mismatch"
    return {
        "kind": row["kind"],
        "reported": reported,
        "path": path,
        "custody": {"state": state, "bytes": reference},
    }


def prepare_call_result(
    intent: PreparedCallIntent,
    *,
    intent_event_digest: bytes,
    outcome: ProcessOutcome | None,
    error_id: str | None,
    error: BaseException | None,
    spool_readback: tuple[bytes | None, bytes | None] = (None, None),
) -> PreparedCallResult:
    """Preserve an actual returned observation; no call or persistence occurs."""
    private = _prepared_intent(intent)
    digest = _digest(intent_event_digest)
    readbacks = _tuple(spool_readback, 2, 2)
    for readback in readbacks:
        if readback is not None:
            _binary(readback, 16 * _MIB)
    if error is None:
        _need(error_id is None)
    else:
        _exception(error)
        _uuid(error_id)
    carrier = _carrier(error)
    actual = None if outcome is None else _outcome(outcome)
    if carrier is not None:
        # Both operands contain only privately validated exact primitives.
        _need(actual is not None and carrier == actual)
    if actual is None:
        _need(error is not None and readbacks == (None, None))
    _, fields = _binding(private.binding)
    pack = _Pack()
    pack.charge_metadata(len(private.payload))
    requested = pack.add(private.invocation_blob.data, _MIB)
    if actual is not None:
        actual["invocation"] = pack.add(_canonical(actual["invocation"], _INV), _MIB)
        for index, name in enumerate(("stdout", "stderr")):
            actual[name] = _pack_output(actual[name], readbacks[index], pack)
    graph = None
    if error is not None:
        graph = pack.add(_Graph(cast(str, error_id)).encode(error), 8192)
    unavailable = None
    if actual is None:
        unavailable = (
            "validation-refused"
            if type(error) is ProcessValidationError
            else "exception-no-outcome"
        )
    document = dict(
        fields,
        schema="scanipy-runtime-call/1",
        scope="host-docker-client",
        intent_event_digest=digest.hex(),
        requested_invocation=requested,
        outcome=actual,
        unavailable_reason=unavailable,
        error_id=error_id,
        error_graph=graph,
    )
    _result_fields(document)
    reference = pack.add(_canonical(document, _RESULT), 32768)
    call = {"call_id": fields["call_id"], "operation": fields["operation"], "outcome": reference}
    payload = _canonical({"intent_event_digest": digest.hex(), "call": call}, _PAYLOAD)
    pack.charge_metadata(len(payload))
    _need(pack.physical + len(private.payload) + len(payload) <= 32 * _MIB)
    return PreparedCallResult(
        cast(StoredCallRef, _freeze(call)), payload, tuple(pack.blobs.values())
    )
