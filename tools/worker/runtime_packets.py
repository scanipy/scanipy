"""Closed, hash-free runtime packet codecs; supplied structure is not authority.

See RUNTIME-PACKET-CODECS.md. Actual member hashes, inner-input validity,
installed state, current authorization and runtime observations remain with
their respective owners. No file, process, clock or network work occurs here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, cast
from uuid import UUID

from analysis.ifds.bound_rules import BoundRuleError, decode_bounded_json, decode_qualified_rule_key
from services.scan.accepted_inputs import codec as accepted
from services.scan.accepted_inputs import models, schemas
from tools.worker import runtime_docker_policy as policy
from tools.worker import runtime_profiles as profiles
from tools.worker.process_evidence import StoredObject, StoredValue

REQUEST_SCHEMA = "scanipy-local-runtime-request/1"
LAUNCH_SCHEMA = "scanipy-runtime-bootstrap-launch/1"
PREREQUISITE_SCHEMA = "scanipy-local-launch-prerequisite/1"
_MAX_BYTES = 65536
_MAX_VALUES = 8192
_MAX_DEPTH = 16
_MODES = ("verifier-publication", "verifier-historical", "verifier-execution", "python-syntax")
_ACTIONS = ("publish-builtin-preflight", "audit-historical", "verify-execution", "parse-python")
_REQUEST_KEYS = (
    "schema",
    "operation_id",
    "mode",
    "deployment_id",
    "installation_id",
    "installation_generation",
    "controller_profile_sha256",
    "domain_profile_sha256",
    "input",
    "binding",
    "prerequisite",
)
_LAUNCH_KEYS = (
    "schema",
    "attempt_id",
    "operation_id",
    "request_digest",
    "deployment_id",
    "installation_id",
    "installation_generation",
    "mode",
    "image_config_id",
    "controller_profile_sha256",
    "domain_profile_sha256",
    "inventory_sha256",
    "inventory_digest",
    "program_digest",
    "input",
    "inner",
    "container_uid",
    "container_gid",
    "release_filename",
    "bootstrap_wait_ms",
    "inner_wall_ms",
    "inner_cleanup_ms",
)
_PREREQUISITE_KEYS = (
    "schema",
    "reader_id",
    "observation_id",
    "observed_at",
    "valid_until",
    "principal_id",
    "org_id",
    "action",
    "authentication_evidence_sha256",
    "scope_evidence_sha256",
    "admission",
    "execution_authorization_digest",
    "capture_lease_evidence_sha256",
    "content_verification_evidence_sha256",
)


class RuntimePacketError(ValueError):
    """Fixed public reason only; any original diagnostic remains a private cause."""

    def __init__(self, reason: str = "invalid-input") -> None:
        if type(reason) is not str or reason not in (
            "invalid-input",
            "limit",
            "unsupported",
            "link-mismatch",
        ):
            reason = "invalid-input"
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True, repr=False)
class RuntimePacket:
    kind: Literal["request", "launch"]
    data: bytes
    document: StoredObject
    validation: Literal["input-structure-only"]


@dataclass(frozen=True, slots=True, repr=False)
class RuntimeRecipeMembers:
    metadata: profiles.RuntimeMetadataDocuments
    request: RuntimePacket
    launch: RuntimePacket
    validation: Literal["input-structure-only"]


def _require(condition: bool, reason: str = "invalid-input") -> None:
    if not condition:
        raise RuntimePacketError(reason)


def _text(value: object, maximum: int = 4096) -> str:
    _require(type(value) is str)
    value = cast(str, value)
    _require(len(value) <= maximum, "limit")
    _require("\x00" not in value)
    try:
        _require(len(value.encode("utf-8")) <= maximum, "limit")
    except UnicodeError as error:
        raise RuntimePacketError() from error
    return value


def _integer(value: object, minimum: int = 0, maximum: int = 2**63 - 1) -> int:
    _require(type(value) is int and minimum <= value <= maximum)
    return cast(int, value)


def _id(value: object) -> str:
    result = _text(value, 128)
    _require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", result) is not None)
    return result


def _uuid(value: object) -> str:
    result = _text(value, 36)
    try:
        _require(str(UUID(result)) == result)
    except ValueError as error:
        if isinstance(error, RuntimePacketError):
            raise
        raise RuntimePacketError() from error
    return result


def _hex(value: object) -> str:
    result = _text(value, 64)
    _require(re.fullmatch(r"[0-9a-f]{64}", result) is not None)
    return result


def _utc(value: object) -> datetime:
    result = _text(value, 27)
    _require(
        re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z", result)
        is not None
    )
    try:
        return datetime.fromisoformat(result[:-1] + "+00:00")
    except ValueError as error:
        raise RuntimePacketError() from error


def _path(value: object, *, relative: bool = False) -> str:
    result = _text(value, 1024 if relative else 4096)
    _require("\\" not in result and not any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in result))
    _require(not result.startswith("/") if relative else result.startswith("/"))
    parts = result.split("/") if relative else result[1:].split("/")
    _require(all(part not in ("", ".", "..") for part in parts))
    if relative:
        _require(len(parts) <= 32, "limit")
    return result


def _keys(value: object, names: tuple[str, ...]) -> dict[str, Any]:
    _require(type(value) is dict and value.keys() == set(names))
    return cast(dict[str, Any], value)


def _bytes(value: object, maximum: int) -> bytes:
    _require(type(value) is bytes)
    _require(0 < len(cast(bytes, value)) <= maximum, "limit")
    return cast(bytes, value)


def _owner_error(error: Exception) -> RuntimePacketError:
    if isinstance(error, profiles.RuntimeProfileError):
        reason = error.reason if error.reason in ("limit", "unsupported") else "invalid-input"
    elif isinstance(error, BoundRuleError):
        reason = "limit" if "limit" in error.code else "invalid-input"
    else:
        reason = "invalid-input"
    return RuntimePacketError(reason)


def _decode(data: bytes) -> dict[str, Any]:
    _bytes(data, _MAX_BYTES)
    try:
        value = decode_bounded_json(
            data,
            max_bytes=_MAX_BYTES,
            max_depth=_MAX_DEPTH,
            max_values=_MAX_VALUES,
            max_string_bytes=8192,
        )
        _require(type(value) is dict)
        _require(accepted.canonical_bytes(value, maximum=_MAX_BYTES) == data)
        return cast(dict[str, Any], value)
    except (BoundRuleError, schemas.VerificationError) as error:
        raise _owner_error(error) from error


def _freeze(value: Any) -> StoredValue:  # noqa: ANN401 -- private, bounded JSON
    if type(value) is dict:
        return ("object", tuple((key, _freeze(item)) for key, item in sorted(value.items())))
    if type(value) is list:
        return ("array", tuple(_freeze(item) for item in value))
    return cast(StoredValue, value)


def _string_cost(value: object) -> int:
    text = _text(value, 8192)
    cost = 2
    for character in text:
        code = ord(character)
        cost += (
            2
            if character in '\\"\b\f\n\r\t'
            else 6
            if code < 32
            else 1
            if code < 128
            else 2
            if code < 2048
            else 3
            if code < 65536
            else 4
        )
    return cost


def _writer_document(value: StoredObject) -> dict[str, Any]:
    # Exact tuples/strings are immutable; validate the entire nested forest and
    # its logical queued work BEFORE allocating a private JSON dict or list.
    pending: list[tuple[object, int]] = [(value, 0)]
    count = encoded = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        _require(count <= _MAX_VALUES, "limit")
        if type(item) is tuple:
            _require(len(item) == 2 and type(item[0]) is str and item[0] in ("object", "array"))
            _require(depth < _MAX_DEPTH, "limit")
            tag, rows = item
            _require(type(rows) is tuple)
            width = 2 if tag == "object" else 1
            _require(count + len(pending) + width * len(rows) <= _MAX_VALUES, "limit")
            encoded += 2 + max(0, len(rows) - 1) + (len(rows) if tag == "object" else 0)
            previous: str | None = None
            for row in rows:
                if tag == "object":
                    _require(type(row) is tuple and len(row) == 2 and type(row[0]) is str)
                    key, child = row
                    _text(key)
                    _require(previous is None or previous < key)
                    previous = key
                    pending.append((key, depth + 1))
                    pending.append((child, depth + 1))
                else:
                    pending.append((row, depth + 1))
        elif type(item) is str:
            encoded += _string_cost(item)
        elif type(item) is bool:
            encoded += 4 if item else 5
        elif type(item) is int:
            encoded += len(str(_integer(item, -(2**63))))
        elif item is None:
            encoded += 4
        else:
            raise RuntimePacketError()
        _require(encoded <= _MAX_BYTES, "limit")
    _require(type(value) is tuple and value[0] == "object")

    def project(node: StoredValue) -> Any:  # noqa: ANN401 -- closed primitive JSON
        if type(node) is tuple:
            if node[0] == "object":
                return {key: project(child) for key, child in node[1]}
            return [project(child) for child in node[1]]
        return node

    return cast(dict[str, Any], project(value))


def _mode(value: object) -> int:
    value = _text(value, 32)
    _require(value in _MODES, "unsupported")
    return _MODES.index(value)


def _input(value: object, mode: int) -> dict[str, Any]:
    doc = _keys(value, ("size", "sha256", "protocol"))
    _integer(doc["size"], 1, 263244 if mode == 3 else 2621440)
    _hex(doc["sha256"])
    expected = (
        "scanipy-python-syntax-request/1" if mode == 3 else "scanipy-accepted-verifier-request/1"
    )
    _require(_id(doc["protocol"]) == expected, "unsupported")
    return doc


def _request(doc: dict[str, Any]) -> None:
    _keys(doc, _REQUEST_KEYS)
    _require(doc["schema"] == REQUEST_SCHEMA, "unsupported")
    mode = _mode(doc["mode"])
    for name in ("operation_id", "deployment_id", "installation_id"):
        _uuid(doc[name])
    _integer(doc["installation_generation"], 1)
    for name in ("controller_profile_sha256", "domain_profile_sha256"):
        _hex(doc[name])
    _input(doc["input"], mode)
    binding = _keys(doc["binding"], ("bundle", "execution", "qualified_rule", "source"))
    prerequisite = _keys(doc["prerequisite"], _PREREQUISITE_KEYS)
    _require(prerequisite["schema"] == PREREQUISITE_SCHEMA, "unsupported")
    for name in ("reader_id", "principal_id", "action"):
        _id(prerequisite[name])
    for name in ("observation_id", "org_id"):
        _uuid(prerequisite[name])
    for name in ("authentication_evidence_sha256", "scope_evidence_sha256"):
        _hex(prerequisite[name])
    observed, valid = _utc(prerequisite["observed_at"]), _utc(prerequisite["valid_until"])
    _require(0 < (valid - observed).total_seconds() <= 60)
    _require(prerequisite["action"] == _ACTIONS[mode], "link-mismatch")
    try:
        bundle = accepted.decode_record(
            binding["bundle"], models.BundleExpectation, schemas.BUNDLE_EXPECTATION
        )
        _require(bundle.scope == "customer" and bundle.org_id is not None, "unsupported")
        _require(prerequisite["org_id"] == str(bundle.org_id), "link-mismatch")
        admission = prerequisite["admission"]
        if mode == 1:
            _require(admission is None)
        else:
            _require(admission is not None)
            accepted.decode_record(
                admission, models.AdmissionExpectation, schemas.ADMISSION_EXPECTATION
            )
        execution = binding["execution"]
        key_doc = binding["qualified_rule"]
        if mode < 2:
            _require(execution is None and key_doc is None)
        else:
            _require(execution is not None and key_doc is not None)
            execution = accepted.decode_record(
                execution, models.ExecutionBinding, schemas.EXECUTION_BINDING
            )
            key = decode_qualified_rule_key(accepted.canonical_bytes(key_doc, maximum=16384))
            _require(execution.org_id == bundle.org_id, "link-mismatch")
            _require(
                key.registry_id == str(bundle.registry_id)
                and key.bundle_id == str(bundle.bundle_id)
                and key.scope == bundle.scope
                and key.org_id == str(bundle.org_id)
                and key.S_version == bundle.S_version
                and key.accepted_content_digest == bundle.accepted_content_digest,
                "link-mismatch",
            )
            _require(
                valid
                <= min(_utc(execution.lease_expires_at), _utc(execution.capture_lease_expires_at)),
                "link-mismatch",
            )
        source = binding["source"]
        if mode != 3:
            _require(source is None)
        else:
            source = _keys(
                source,
                (
                    "capture_id",
                    "source_tree_algorithm",
                    "source_tree_digest",
                    "inventory_sha256",
                    "path",
                    "size",
                    "sha256",
                ),
            )
            _uuid(source["capture_id"])
            _id(source["source_tree_algorithm"])
            for name in ("source_tree_digest", "inventory_sha256", "sha256"):
                _hex(source[name])
            _path(source["path"], relative=True)
            _integer(source["size"], 0, 262144)
            _require(source["capture_id"] == str(execution.capture_id), "link-mismatch")
        for index, name in enumerate(
            (
                "execution_authorization_digest",
                "capture_lease_evidence_sha256",
                "content_verification_evidence_sha256",
            )
        ):
            value = prerequisite[name]
            present = mode >= 2 and (index < 2 or mode == 3)
            if not present:
                _require(value is None)
            else:
                _hex(value)
        if mode >= 2:
            _require(
                prerequisite["execution_authorization_digest"] == execution.authorization_digest,
                "link-mismatch",
            )
    except (BoundRuleError, schemas.VerificationError) as error:
        raise _owner_error(error) from error


def _packet(kind: Literal["request", "launch"], data: bytes, doc: dict[str, Any]) -> RuntimePacket:
    return RuntimePacket(kind, data, cast(StoredObject, _freeze(doc)), "input-structure-only")


def decode_runtime_request(data: bytes) -> RuntimePacket:
    """Decode original control bytes; never authenticate their claimed bindings."""
    doc = _decode(data)
    _request(doc)
    return _packet("request", data, doc)


def encode_runtime_request(document: StoredObject) -> bytes:
    doc = _writer_document(document)
    _request(doc)
    try:
        return accepted.canonical_bytes(doc, maximum=_MAX_BYTES)
    except schemas.VerificationError as error:
        raise _owner_error(error) from error


def _view(value: StoredValue) -> dict[str, Any]:
    # Only fresh output of the actual metadata owner, never a public carrier.
    return dict(cast(StoredObject, value)[1])


def _launch(doc: dict[str, Any]) -> None:
    _keys(doc, _LAUNCH_KEYS)
    _require(doc["schema"] == LAUNCH_SCHEMA, "unsupported")
    mode = _mode(doc["mode"])
    for name in ("attempt_id", "operation_id", "deployment_id", "installation_id"):
        _uuid(doc[name])
    _integer(doc["installation_generation"], 1)
    for name in (
        "request_digest",
        "controller_profile_sha256",
        "domain_profile_sha256",
        "inventory_sha256",
        "inventory_digest",
        "program_digest",
    ):
        _hex(doc[name])
    image = _text(doc["image_config_id"], 71)
    _require(image.startswith("sha256:"))
    _hex(image[7:])
    _input(doc["input"], mode)
    for name in ("container_uid", "container_gid"):
        _integer(doc[name], 1, 2**31 - 1)
    for name, expected in (
        ("release_filename", "release.json"),
        ("bootstrap_wait_ms", 10000),
        ("inner_wall_ms", 5000 if mode == 3 else 3000),
        ("inner_cleanup_ms", 500),
    ):
        _require(type(doc[name]) is type(expected) and doc[name] == expected)
    inner = _keys(doc["inner"], ("argv", "environment", "cwd"))
    _path(inner["cwd"])
    argv = inner["argv"]
    _require(type(argv) is list and len(argv) <= 64, "limit")
    _require(sum(len(_text(arg, 8192).encode("utf-8")) + 1 for arg in argv) <= 65536, "limit")
    environment = inner["environment"]
    _require(type(environment) is list and len(environment) <= 16, "limit")
    previous = None
    size = 0
    for row in environment:
        row = _keys(row, ("name", "value"))
        name, value = _text(row["name"], 128), _text(row["value"], 8192)
        _require(bool(name) and "=" not in name and (previous is None or previous < name))
        previous = name
        size += len(name.encode("utf-8")) + len(value.encode("utf-8")) + 2
        _require(size <= 16384, "limit")


def _join(
    request: dict[str, Any], launch: dict[str, Any], metadata: profiles.RuntimeMetadataDocuments
) -> None:
    installation, profile = _view(metadata.installation), _view(metadata.controller_profile)
    mode = _mode(request["mode"])
    _require(
        installation["purpose"] == ("python-syntax" if mode == 3 else "accepted-verifier"),
        "link-mismatch",
    )
    for field, name in (
        ("deployment_id", "deployment_id"),
        ("installation_id", "installation_id"),
        ("installation_generation", "generation"),
    ):
        _require(
            request[field] == installation[name] and launch[field] == request[field],
            "link-mismatch",
        )
    for name in ("operation_id", "mode", "input"):
        _require(launch[name] == request[name], "link-mismatch")
    for name, descriptor in (
        ("controller_profile_sha256", "controller_profile"),
        ("domain_profile_sha256", "domain_profile"),
    ):
        _require(
            request[name] == _view(installation[descriptor])["sha256"]
            and launch[name] == request[name],
            "link-mismatch",
        )
    for name, expected in (
        ("inventory_sha256", _view(installation["inventory"])["sha256"]),
        ("program_digest", profile["program_digest"]),
        ("image_config_id", _view(profile["image"])["config_id"]),
        ("container_uid", installation["controller_uid"]),
        ("container_gid", installation["controller_gid"]),
        ("inner_wall_ms", _view(profile["limits"])["inner_wall_ms"]),
        ("inner_cleanup_ms", _view(profile["limits"])["inner_cleanup_ms"]),
    ):
        _require(launch[name] == expected, "link-mismatch")
    try:
        invocation = policy.render_runtime_inner_invocation(
            purpose=installation["purpose"],
            python_executable=str(metadata.bindings.executable.path),
            worker_path=str(metadata.bindings.worker.path),
            domain_profile_path=_view(installation["domain_profile"])["path"],
            domain_profile_sha256=bytes.fromhex(request["domain_profile_sha256"]),
            attempt_id=launch["attempt_id"],
            stdin_bytes=launch["input"]["size"],
            stdin_sha256=bytes.fromhex(launch["input"]["sha256"]),
        )
    except policy.RuntimeDockerPolicyError as error:
        raise RuntimePacketError("link-mismatch") from error
    _require(
        launch["inner"]
        == {
            "argv": list(invocation.argv),
            "environment": [
                {"name": name, "value": value} for name, value in invocation.environment
            ],
            "cwd": invocation.cwd,
        },
        "link-mismatch",
    )


def decode_runtime_recipe_members(
    request: bytes, launch: bytes, installation: bytes, controller_profile: bytes
) -> RuntimeRecipeMembers:
    """Validate all four original structures; raw-byte hash links stay external."""
    for raw, maximum in (
        (request, _MAX_BYTES),
        (launch, _MAX_BYTES),
        (installation, 65536),
        (controller_profile, 131072),
    ):
        _bytes(raw, maximum)
    try:
        metadata = profiles.decode_runtime_metadata_documents(installation, controller_profile)
    except profiles.RuntimeProfileError as error:
        raise _owner_error(error) from error
    request_doc, launch_doc = _decode(request), _decode(launch)
    _request(request_doc)
    _launch(launch_doc)
    _join(request_doc, launch_doc, metadata)
    return RuntimeRecipeMembers(
        metadata,
        _packet("request", request, request_doc),
        _packet("launch", launch, launch_doc),
        "input-structure-only",
    )


def encode_runtime_launch(
    document: StoredObject, *, request: bytes, installation: bytes, controller_profile: bytes
) -> bytes:
    for raw, maximum in (
        (request, _MAX_BYTES),
        (installation, 65536),
        (controller_profile, 131072),
    ):
        _bytes(raw, maximum)
    doc = _writer_document(document)
    try:
        raw = accepted.canonical_bytes(doc, maximum=_MAX_BYTES)
    except schemas.VerificationError as error:
        raise _owner_error(error) from error
    decode_runtime_recipe_members(request, raw, installation, controller_profile)
    return raw
