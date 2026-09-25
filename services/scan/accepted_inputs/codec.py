"""Bounded exact wire framing; raw content is never rewritten as historical bytes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import PosixPath
from typing import Any, TypeVar
from uuid import UUID

from analysis.ifds.bound_rules import (
    BoundRuleError,
    QualifiedRuleKey,
    decode_bounded_json,
    decode_qualified_rule_key,
    encode_qualified_rule_key,
)
from services.scan.occurrence_store.codec import encode_envelope

from . import models as m
from . import schemas as s


def raw_digest(data: bytes) -> str:
    s.require(type(data) is bytes)
    return hashlib.sha256(data).hexdigest()


def domain_digest(schema_id: str, data: bytes) -> str:
    s.text(schema_id, 128, nonempty=True)
    s.require(type(data) is bytes)
    return hashlib.sha256(schema_id.encode("ascii") + b"\n" + data).hexdigest()


def _primitive_budget(
    value: object, *, maximum: int = s.MAX_VALUES, maximum_bytes: int = s.MAX_CONTENT
) -> int:
    s.require(type(maximum) is int and 0 <= maximum <= s.MAX_VALUES)
    s.require(type(maximum_bytes) is int and 0 <= maximum_bytes <= s.MAX_CONTENT)
    pending = [(value, 0)]
    count = 0
    encoded_bytes = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        s.require(count <= maximum and depth <= s.MAX_DEPTH)
        if item is None:
            encoded_bytes += 4
        elif type(item) is bool:
            encoded_bytes += 4 if item else 5
        elif type(item) is int:
            s.require(-(2**63) <= item < 2**63)
            encoded_bytes += len(str(item))
        elif type(item) is str:
            s.text(item)
            encoded_bytes += 2
            for character in item:
                codepoint = ord(character)
                if character in ('"', "\\", "\b", "\f", "\n", "\r", "\t"):
                    encoded_bytes += 2
                elif codepoint < 32:
                    encoded_bytes += 6
                else:
                    encoded_bytes += (
                        1
                        if codepoint < 128
                        else 2
                        if codepoint < 2048
                        else 3
                        if codepoint < 65536
                        else 4
                    )
        elif type(item) is list:
            s.require(len(item) <= maximum - count - len(pending))
            encoded_bytes += 2 + max(0, len(item) - 1)
            pending.extend((child, depth + 1) for child in item)
        elif type(item) is dict:
            s.require(len(item) * 2 <= maximum - count - len(pending))
            encoded_bytes += 2 + len(item) + max(0, len(item) - 1)
            for key, child in item.items():
                s.require(type(key) is str)
                pending.append((key, depth + 1))
                pending.append((child, depth + 1))
        else:
            raise s.VerificationError()
        s.require(encoded_bytes <= maximum_bytes)
    return count


def canonical_bytes(value: object, *, maximum: int = s.MAX_OBJECT) -> bytes:
    _primitive_budget(value, maximum_bytes=maximum)
    try:
        data = json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise s.VerificationError() from exc
    s.require(len(data) <= maximum)
    return data


def parse_json(data: bytes, *, maximum: int = s.MAX_OBJECT, canonical: bool = True) -> Any:  # noqa: ANN401
    try:
        value = decode_bounded_json(
            data,
            max_bytes=maximum,
            max_depth=s.MAX_DEPTH,
            max_values=s.MAX_VALUES,
            max_string_bytes=s.MAX_STRING,
        )
    except BoundRuleError as exc:
        raise s.VerificationError() from exc
    if canonical:
        s.require(canonical_bytes(value, maximum=maximum) == data)
    return value


def metadata_limit(schema_id: str) -> int:
    if schema_id == s.POLICY:
        return s.MAX_POLICY
    if schema_id == s.INSTALLED_TRUST:
        return 4096
    if schema_id == s.S_MANIFEST:
        return s.MAX_CONTENT
    return s.MAX_OBJECT


def decode_document(data: bytes, schema_id: str, *, canonical: bool = True) -> dict[str, Any]:
    return s.validate_document(
        parse_json(data, maximum=metadata_limit(schema_id), canonical=canonical), schema_id
    )


def encode_document(value: dict[str, Any], schema_id: str) -> bytes:
    _primitive_budget(value, maximum_bytes=metadata_limit(schema_id))
    s.validate_document(value, schema_id)
    return canonical_bytes(value, maximum=metadata_limit(schema_id))


class _Reader:
    def __init__(self, data: bytes, schema_id: str, maximum: int) -> None:
        m.raw(data, maximum)
        prefix = schema_id.encode("ascii") + b"\n"
        s.require(data.startswith(prefix))
        self.data = data
        self.offset = len(prefix)

    def part(self, maximum: int, expected: int | None = None) -> bytes:
        s.require(len(self.data) - self.offset >= 8)
        length = int.from_bytes(self.data[self.offset : self.offset + 8], "big")
        self.offset += 8
        s.require(length <= maximum and length <= len(self.data) - self.offset)
        s.require(expected is None or length == expected)
        result = self.data[self.offset : self.offset + length]
        self.offset += length
        return result

    def finish(self) -> None:
        s.require(self.offset == len(self.data))


def _framed(schema_id: str, parts: tuple[bytes, ...], maximum: int) -> bytes:
    s.require(type(parts) is tuple and len(parts) <= s.MAX_VALUES)
    total = len(schema_id) + 1
    for part in parts:
        m.raw(part, maximum, empty=True)
        total += 8 + len(part)
        s.require(total <= maximum)
    pieces = [schema_id.encode("ascii") + b"\n"]
    for part in parts:
        pieces.extend((len(part).to_bytes(8, "big"), part))
    return b"".join(pieces)


@dataclass(frozen=True, slots=True)
class ParsedFrame:
    schema_id: str
    manifest_bytes: bytes
    objects: tuple[bytes, ...]

    @property
    def manifest(self) -> dict[str, Any]:
        return decode_document(self.manifest_bytes, self.schema_id)

    def object(self, role: str) -> bytes:
        roles = s.FRAME_ROLES[self.schema_id]
        for index, (name, _schema) in enumerate(roles):
            if name == role:
                return self.objects[index]
        raise s.VerificationError("unsupported-schema")

    def document(self, role: str) -> dict[str, Any]:
        for name, schema_id in s.FRAME_ROLES[self.schema_id]:
            if name == role and schema_id is not None:
                return decode_document(self.object(role), schema_id)
        raise s.VerificationError("unsupported-schema")


def decode_frame(data: bytes, schema_id: str) -> ParsedFrame:
    s.require(schema_id in s.FRAME_ROLES, "unsupported-schema")
    reader = _Reader(data, schema_id, s.MAX_LIVE if schema_id == s.LIVE else s.MAX_AUTHORITY)
    manifest_bytes = reader.part(s.MAX_OBJECT)
    manifest = decode_document(manifest_bytes, schema_id)
    value_count = _primitive_budget(manifest)
    objects = []
    for descriptor in manifest["objects"]:
        object_schema = descriptor["schema"]
        maximum = metadata_limit(object_schema) if object_schema is not None else 4096
        data_part = reader.part(maximum, descriptor["length"])
        s.require(raw_digest(data_part) == descriptor["raw_sha256"], "content-mismatch")
        if object_schema is not None:
            value_count += _primitive_budget(decode_document(data_part, object_schema))
            s.require(value_count <= s.MAX_VALUES)
        elif descriptor["role"].endswith("-signature"):
            s.require(len(data_part) == 384)
        else:
            s.require(0 < len(data_part) <= 4096)
        objects.append(data_part)
    reader.finish()
    return ParsedFrame(schema_id, manifest_bytes, tuple(objects))


def encode_frame(schema_id: str, manifest_bytes: bytes, objects: tuple[bytes, ...]) -> bytes:
    s.require(type(objects) is tuple and len(objects) <= 15)
    data = _framed(
        schema_id,
        (manifest_bytes, *objects),
        s.MAX_LIVE if schema_id == s.LIVE else s.MAX_AUTHORITY,
    )
    decode_frame(data, schema_id)
    return data


def decode_spec(data: bytes) -> tuple[dict[str, Any], tuple[bytes, ...]]:
    reader = _Reader(data, s.SPEC_FRAME, s.MAX_CONTENT)
    manifest = decode_document(reader.part(s.MAX_CONTENT), s.S_MANIFEST)
    models = []
    for descriptor in manifest["models"]:
        model = reader.part(s.MAX_CONTENT)
        s.require(raw_digest(model) == descriptor["raw_sha256"], "content-mismatch")
        models.append(model)
    reader.finish()
    return manifest, tuple(models)


def encode_spec(manifest_bytes: bytes, model_blobs: tuple[bytes, ...]) -> bytes:
    s.require(type(model_blobs) is tuple and len(model_blobs) <= s.MAX_VALUES)
    data = _framed(s.SPEC_FRAME, (manifest_bytes, *model_blobs), s.MAX_CONTENT)
    decode_spec(data)
    return data


def validate_bundle_layout(bundle: m.AcceptedBundleBytes) -> dict[str, Any]:
    s.require(type(bundle) is m.AcceptedBundleBytes)
    manifest, _models = decode_spec(bundle.spec_bytes)
    s.require(type(bundle.detector_blobs) is tuple and type(bundle.rule_blobs) is tuple)
    s.require(len(bundle.detector_blobs) == len(manifest["detectors"]))
    s.require(len(bundle.rule_blobs) == sum(len(item["rules"]) for item in manifest["detectors"]))
    return manifest


def accepted_content_digest(bundle: m.AcceptedBundleBytes) -> str:
    m.AcceptedBundleBytes.__post_init__(bundle)
    # Reuse the existing store codec: this is exactly its wire/domain, not a
    # separately invented bundle hash or a future source/environment identity.
    envelope = encode_envelope(
        "accepted-content",
        {
            "schema": "scanipy-execution/accepted-content/1",
            "spec_sha256": raw_digest(bundle.spec_bytes),
            "detector_sha256s": [raw_digest(value) for value in bundle.detector_blobs],
            "rule_sha256s": [raw_digest(value) for value in bundle.rule_blobs],
        },
    )
    return envelope.digest.hex()


def qualified_members(
    bundle: m.AcceptedBundleBytes,
) -> tuple[tuple[QualifiedRuleKey, bytes, bytes, bytes], ...]:
    m.AcceptedBundleBytes.__post_init__(bundle)
    manifest, model_blobs = decode_spec(bundle.spec_bytes)
    digest = accepted_content_digest(bundle)
    models = {
        (item["artifact_id"], item["raw_sha256"]): (item, model_blobs[index])
        for index, item in enumerate(manifest["models"])
    }
    result = []
    rule_index = 0
    for detector_index, member in enumerate(manifest["detectors"]):
        detector_raw = bundle.detector_blobs[detector_index]
        s.require(raw_digest(detector_raw) == member["detector_sha256"], "content-mismatch")
        detector = decode_document(detector_raw, s.DETECTOR, canonical=False)
        s.require(
            (
                detector["id"],
                detector["version"],
                detector["class_id"],
                detector["engine"],
                detector["profiles"],
                detector["rule_ids"],
            )
            == (
                member["detector_id"],
                member["detector_version"],
                member["class_id"],
                member["engine"],
                member["language_profiles"],
                [rule["rule_id"] for rule in member["rules"]],
            ),
            "content-mismatch",
        )
        for rule in member["rules"]:
            rule_raw = bundle.rule_blobs[rule_index]
            rule_index += 1
            s.require(raw_digest(rule_raw) == rule["raw_sha256"], "content-mismatch")
            model, model_raw = models[(rule["model_artifact_id"], rule["model_raw_sha256"])]
            semantic = {
                "schema": s.SEMANTIC_BINDING,
                "rule_raw_sha256": rule["raw_sha256"],
                "model_raw_sha256": rule["model_raw_sha256"],
                "semantics": rule["semantics"],
                "projection_profile": rule["projection_profile"],
            }
            s.require(
                domain_digest(s.SEMANTIC_BINDING, encode_document(semantic, s.SEMANTIC_BINDING))
                == rule["semantic_descriptor_digest"],
                "content-mismatch",
            )
            key = QualifiedRuleKey(
                registry_id=manifest["registry_id"],
                bundle_id=manifest["bundle_id"],
                scope=manifest["scope"],
                org_id=manifest["org_id"],
                S_version=manifest["S_version"],
                accepted_content_digest=digest,
                detector_id=member["detector_id"],
                detector_version=member["detector_version"],
                detector_raw_sha256=member["detector_sha256"],
                rule_id=rule["rule_id"],
                rule_artifact_id=rule["artifact_id"],
                rule_artifact_version=rule["version"],
                rule_raw_sha256=rule["raw_sha256"],
                model_artifact_id=model["artifact_id"],
                model_artifact_version=model["version"],
                model_raw_sha256=model["raw_sha256"],
                semantic_descriptor_digest=rule["semantic_descriptor_digest"],
            )
            result.append((key, detector_raw, rule_raw, model_raw))
    return tuple(result)


def selected_content(
    bundle: m.AcceptedBundleBytes, key: QualifiedRuleKey
) -> tuple[bytes, bytes, bytes]:
    encode_qualified_rule_key(key)
    matches = [member for member in qualified_members(bundle) if member[0] == key]
    s.require(len(matches) == 1, "content-mismatch")
    return matches[0][1:]


T = TypeVar("T")


def decode_record(value: dict[str, Any], kind: type[T], rules: dict[str, Any]) -> T:
    s.shape(value, rules)
    members = dict(value)
    for name, rule in rules.items():
        actual = rule[1] if type(rule) is tuple and rule[0] == "nullable" else rule
        if members[name] is not None and actual == "uuid":
            members[name] = UUID(members[name])
        elif members[name] is not None and actual == "path":
            members[name] = PosixPath(members[name])
    if kind is m.LedgerExpectation and members["binding"] is not None:
        members["binding"] = decode_record(
            members["binding"], m.ExecutionBinding, s.EXECUTION_BINDING
        )
    if kind is m.VerifierRuntimeDocument:
        for name in ("stdlib_roots", "dependency_roots"):
            members[name] = tuple(PosixPath(item) for item in members[name])
    if kind is m.VerificationResult and members["checks"] is not None:
        members["checks"] = decode_record(members["checks"], m.VerificationChecks, s.CHECKS)
    return kind(**members)


def _request_header(request: m.VerifierRequest) -> dict[str, Any]:
    return {
        "schema": s.REQUEST,
        "operation_id": m._uuid_text(request.operation_id),
        "mode": request.mode,
        "installed_trust": m.record_dict(request.installed_trust),
        "expected_bundle": m.record_dict(request.expected_bundle),
        "reference_time": request.reference_time,
        "verifier_artifact_digest": request.verifier_artifact_digest,
        "admission": None if request.admission is None else m.record_dict(request.admission),
        "ledger": None if request.ledger is None else m.record_dict(request.ledger),
        "selected_rule": None
        if request.selected_rule is None
        else parse_json(encode_qualified_rule_key(request.selected_rule)),
        "lengths": {
            "spec": len(request.bundle.spec_bytes),
            "detectors": [len(value) for value in request.bundle.detector_blobs],
            "rules": [len(value) for value in request.bundle.rule_blobs],
            "authority": len(request.authority_evidence),
            "live_authority": len(request.live_authority_evidence),
            "execution_authorization": len(request.execution_authorization),
        },
    }


_LENGTHS = {
    "spec": "count",
    "detectors": s.array("count", 1),
    "rules": s.array("count", 1),
    "authority": "count",
    "live_authority": "count",
    "execution_authorization": "count",
}


def encode_request(request: m.VerifierRequest) -> bytes:
    s.require(type(request) is m.VerifierRequest)
    m.VerifierRequest.__post_init__(request)
    header = canonical_bytes(_request_header(request))
    parts = [header, request.bundle.spec_bytes]
    parts.extend(request.bundle.detector_blobs)
    parts.extend(request.bundle.rule_blobs)
    parts.extend(
        (
            request.authority_evidence,
            request.live_authority_evidence,
            request.execution_authorization,
        )
    )
    return _framed(s.REQUEST, tuple(parts), s.MAX_PACKET)


def decode_request(data: bytes) -> m.VerifierRequest:
    reader = _Reader(data, s.REQUEST, s.MAX_PACKET)
    header = parse_json(reader.part(s.MAX_OBJECT))
    s.require(
        type(header) is dict
        and set(header)
        == {
            "schema",
            "operation_id",
            "mode",
            "installed_trust",
            "expected_bundle",
            "reference_time",
            "verifier_artifact_digest",
            "admission",
            "ledger",
            "selected_rule",
            "lengths",
        }
    )
    s.require(header["schema"] == s.REQUEST)
    s.shape(header["operation_id"], "uuid")
    s.shape(header["mode"], s.enum(*s.MODES))
    s.shape(header["lengths"], _LENGTHS)
    lengths = header["lengths"]
    s.require(lengths["spec"] + sum(lengths["detectors"]) + sum(lengths["rules"]) <= s.MAX_CONTENT)
    s.require(
        lengths["authority"] <= s.MAX_AUTHORITY
        and lengths["live_authority"] <= s.MAX_LIVE
        and lengths["execution_authorization"] <= s.MAX_OBJECT
    )
    spec = reader.part(s.MAX_CONTENT, lengths["spec"])
    detectors = tuple(reader.part(s.MAX_CONTENT, length) for length in lengths["detectors"])
    rules = tuple(reader.part(s.MAX_CONTENT, length) for length in lengths["rules"])
    authority = reader.part(s.MAX_AUTHORITY, lengths["authority"])
    live = reader.part(s.MAX_LIVE, lengths["live_authority"])
    execution = reader.part(s.MAX_OBJECT, lengths["execution_authorization"])
    reader.finish()
    return m.VerifierRequest(
        operation_id=UUID(header["operation_id"]),
        mode=header["mode"],
        installed_trust=decode_record(
            header["installed_trust"], m.InstalledTrust, s.SHAPES[s.INSTALLED_TRUST]
        ),
        expected_bundle=decode_record(
            header["expected_bundle"], m.BundleExpectation, s.BUNDLE_EXPECTATION
        ),
        reference_time=header["reference_time"],
        verifier_artifact_digest=header["verifier_artifact_digest"],
        admission=None
        if header["admission"] is None
        else decode_record(header["admission"], m.AdmissionExpectation, s.ADMISSION_EXPECTATION),
        ledger=None
        if header["ledger"] is None
        else decode_record(header["ledger"], m.LedgerExpectation, s.LEDGER_EXPECTATION),
        selected_rule=None
        if header["selected_rule"] is None
        else decode_qualified_rule_key(canonical_bytes(header["selected_rule"], maximum=16384)),
        bundle=m.AcceptedBundleBytes(spec, detectors, rules),
        authority_evidence=authority,
        live_authority_evidence=live,
        execution_authorization=execution,
    )


def encode_result(result: m.VerificationResult) -> bytes:
    s.require(type(result) is m.VerificationResult)
    m.VerificationResult.__post_init__(result)
    return canonical_bytes(m.record_dict(result), maximum=s.MAX_OUTPUT)


def decode_result(data: bytes) -> m.VerificationResult:
    value = parse_json(data, maximum=s.MAX_OUTPUT)
    s.validate_document(value, s.RESULT)
    return decode_record(value, m.VerificationResult, s.SHAPES[s.RESULT])
