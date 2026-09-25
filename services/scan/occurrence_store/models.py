"""Typed protocol inputs. Raw blobs are bounded before SQL parameter construction."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, cast
from uuid import UUID

from ._schemas import MAX_BATCH, MAX_COUNT, MAX_ENVELOPE, MAX_OCCURRENCE
from .codec import CanonicalEnvelope, EnvelopeError, decode_envelope

WorkKind = Literal["capture_detection", "identity"]


def envelope_pair(value: CanonicalEnvelope, name: str) -> tuple[bytes, bytes]:
    if type(value) is not CanonicalEnvelope:
        raise EnvelopeError("envelope must be an exact CanonicalEnvelope")
    if value.name != name:
        raise EnvelopeError(f"expected {name} envelope")
    decode_envelope(name, value.data, value.digest)
    return value.data, value.digest


def _raw(value: bytes | None, *, nullable: bool = False) -> int:
    if value is None and nullable:
        return 0
    if type(value) is not bytes:
        raise EnvelopeError("raw evidence must be exact bytes")
    return len(value)


@dataclass(frozen=True)
class RequestInput:
    request: CanonicalEnvelope
    planned_policy: CanonicalEnvelope

    def __post_init__(self) -> None:
        envelope_pair(self.request, "request")
        envelope_pair(self.planned_policy, "planned-policy")
        request, policy = self.request.value, self.planned_policy.value
        if (
            request["requested_policy_digest"] != self.planned_policy.digest.hex()
            or request["identity_policy"] != policy["identity_policy"]
        ):
            raise EnvelopeError("requested policy binding mismatch")


@dataclass(frozen=True)
class CaptureSeal:
    seal: CanonicalEnvelope
    inventory: CanonicalEnvelope
    accepted_content: CanonicalEnvelope
    spec: bytes
    detectors: tuple[bytes, ...]
    rules: tuple[bytes, ...]
    authority_evidence: bytes

    def __post_init__(self) -> None:
        if type(self.detectors) is not tuple or type(self.rules) is not tuple:
            raise EnvelopeError("accepted raw collections must be exact tuples")
        for value, name in (
            (self.seal, "seal"),
            (self.inventory, "source-inventory"),
            (self.accepted_content, "accepted-content"),
        ):
            envelope_pair(value, name)
        seal, content = self.seal.value, self.accepted_content.value
        # These bounded, validated envelopes constrain counts before any raw
        # traversal or hashing. Never expand arbitrary caller iterables.
        if (
            len(self.detectors) != len(content["detector_sha256s"])
            or len(self.rules) != len(content["rule_sha256s"])
            or len(self.detectors) != len(seal["bindings"])
            or len(self.rules) != sum(len(binding["rules"]) for binding in seal["bindings"])
        ):
            raise EnvelopeError("accepted raw content count mismatch")
        size = _raw(self.spec)
        if size > MAX_ENVELOPE:
            raise EnvelopeError("accepted raw content exceeds 1 MiB")
        for collection in (self.detectors, self.rules):
            for raw in collection:
                size += _raw(raw)
                if size > MAX_ENVELOPE:
                    raise EnvelopeError("accepted raw content exceeds 1 MiB")
        if _raw(self.authority_evidence) > MAX_ENVELOPE:
            raise EnvelopeError("acceptance evidence exceeds 1 MiB")
        expected = {
            "schema": "scanipy-execution/accepted-content/1",
            "spec_sha256": hashlib.sha256(self.spec).hexdigest(),
            "detector_sha256s": [hashlib.sha256(value).hexdigest() for value in self.detectors],
            "rule_sha256s": [hashlib.sha256(value).hexdigest() for value in self.rules],
        }
        if (
            content != expected
            or seal["accepted_content_digest"] != self.accepted_content.digest.hex()
        ):
            raise EnvelopeError("accepted content digest mismatch")
        if (
            seal["inventory_digest"] != self.inventory.digest.hex()
            or seal["acceptance_evidence_digest"]
            != hashlib.sha256(self.authority_evidence).hexdigest()
        ):
            raise EnvelopeError("capture evidence digest mismatch")
        if [binding["detector_content_digest"] for binding in seal["bindings"]] != expected[
            "detector_sha256s"
        ]:
            raise EnvelopeError("detector content binding mismatch")
        if [
            rule["content_digest"] for binding in seal["bindings"] for rule in binding["rules"]
        ] != expected["rule_sha256s"]:
            raise EnvelopeError("rule content binding mismatch")


@dataclass(frozen=True)
class RawObservation:
    result: bytes
    witness: bytes | None = None

    def __post_init__(self) -> None:
        if _raw(self.result) + _raw(self.witness, nullable=True) > MAX_OCCURRENCE:
            raise EnvelopeError("occurrence raw bytes exceed 16 MiB")


@dataclass(frozen=True)
class DetectionBatch:
    envelope: CanonicalEnvelope
    stdout: bytes
    stderr: bytes
    observations: tuple[RawObservation, ...]

    def __post_init__(self) -> None:
        if type(self.observations) is not tuple:
            raise EnvelopeError("raw observations must be an exact tuple")
        if len(self.observations) > MAX_COUNT:
            raise EnvelopeError("occurrence count exceeds 10000")
        envelope_pair(self.envelope, "detection-batch")
        value = self.envelope.value
        if len(value["occurrences"]) != len(self.observations):
            raise EnvelopeError("raw occurrence count mismatch")
        size = _raw(self.stdout) + _raw(self.stderr)
        if size > MAX_BATCH:
            raise EnvelopeError("batch raw bytes exceed 64 MiB")
        for row in self.observations:
            if type(row) is not RawObservation:
                raise EnvelopeError("raw observation must be an exact RawObservation")
            row.__post_init__()
            size += len(row.result) + (0 if row.witness is None else len(row.witness))
            if size > MAX_BATCH:
                raise EnvelopeError("batch raw bytes exceed 64 MiB")
        if (
            value["stdout_sha256"] != hashlib.sha256(self.stdout).hexdigest()
            or value["stderr_sha256"] != hashlib.sha256(self.stderr).hexdigest()
        ):
            raise EnvelopeError("raw stream digest mismatch")
        for metadata, row in zip(value["occurrences"], self.observations, strict=True):
            witness = None if row.witness is None else hashlib.sha256(row.witness).hexdigest()
            if (
                metadata["raw_sha256"] != hashlib.sha256(row.result).hexdigest()
                or metadata["witness_sha256"] != witness
            ):
                raise EnvelopeError("raw occurrence digest mismatch")


@dataclass(frozen=True)
class Fence:
    work_item_id: UUID
    attempt_id: UUID
    kind: WorkKind
    token: int
    revision: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.work_item_id, UUID)
            or not isinstance(self.attempt_id, UUID)
            or type(cast(object, self.kind)) is not str
            or self.kind not in ("capture_detection", "identity")
            or type(self.token) is not int
            or not 1 <= self.token < 2**63
            or type(self.revision) is not int
            or not 0 <= self.revision < 2**63
        ):
            raise ValueError("invalid typed work fence")


@dataclass(frozen=True)
class Claim:
    fence: Fence
    request_id: UUID
    occurrence_id: UUID | None
    capture_id: UUID | None
    attempt_number: int
    lease_expires_at: datetime
    payload: dict[str, Any]


@dataclass(frozen=True)
class RequestHandle:
    request_id: UUID
    work_item_id: UUID
    revision: int
    replayed: bool


@dataclass(frozen=True)
class RetainedBatch:
    run_id: UUID
    occurrence_ids: tuple[UUID, ...]
    identity_work_ids: tuple[UUID, ...]
    replayed: bool
