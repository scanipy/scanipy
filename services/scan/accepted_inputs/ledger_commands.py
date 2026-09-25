"""Bounded AL-02 command input structure, never current or committed authority.

Existing signed records and occurrence envelopes keep their owning codecs.
The reserved hash-work schedule applies to the reviewed owner dependency;
tests instrument those real helpers, including early malformed-input paths.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Final, Literal, cast
from uuid import UUID

from analysis.cpg_ingest.typed_observed import FrozenArray
from analysis.ifds.bound_rules import BoundRuleError, ScalarLimits, decode_bound_rule
from services.scan.occurrence_store.codec import EnvelopeError, decode_envelope

from . import codec as c
from . import models as m
from . import schemas as s

LedgerAction = Literal[
    "install-policy",
    "record-admission",
    "publish-builtin",
    "create-bound-request",
    "seal-bound-capture",
    "authorize-detector",
    "renew-detector",
]
COMMAND_SCHEMA: Final = "scanipy-accepted-ledger-command/1"
MAX_HASH_CALLS: Final = 100000
MAX_HASH_BYTES: Final = 134217728
_ACTIONS: Final = (
    "install-policy",
    "record-admission",
    "publish-builtin",
    "create-bound-request",
    "seal-bound-capture",
    "authorize-detector",
    "renew-detector",
)
_W: Final = dict(
    zip(_ACTIONS, (196992, 131456, 2162688, 2162688, 3211264, 1114112, 65536), strict=True)
)
_FENCE: Final = {
    "work_item_id": "uuid",
    "work_attempt_id": "uuid",
    "fencing_token": "positive",
    "work_revision": "count",
}
_BODIES: Final = {
    "install-policy": {"predecessor_policy_digest": s.nullable("digest")},
    "record-admission": {"predecessor_checkpoint_digest": s.nullable("digest")},
    "publish-builtin": {
        "admission": s.ADMISSION_EXPECTATION,
        "bundle": s.BUNDLE_EXPECTATION,
        "publisher_artifact_digest": "digest",
    },
    "create-bound-request": {
        "admission": s.ADMISSION_EXPECTATION,
        "bundle": s.BUNDLE_EXPECTATION,
        "approval_event_id": "uuid",
        "verifier_artifact_digest": "digest",
    },
    "seal-bound-capture": {
        "admission": s.ADMISSION_EXPECTATION,
        "fence": _FENCE,
        "resolver_artifact_digest": "digest",
    },
    "authorize-detector": {
        "admission": s.ADMISSION_EXPECTATION,
        "fence": _FENCE,
        "resolver_artifact_digest": "digest",
    },
    "renew-detector": {
        "admission": s.ADMISSION_EXPECTATION,
        "fence": _FENCE,
        "detector_run_id": "uuid",
        "previous_authorization_id": "uuid",
        "resolver_artifact_digest": "digest",
    },
}
_FIXED_ROLES: Final = {
    "install-policy": ("policy", "root-signature"),
    "record-admission": ("checkpoint", "root-signature"),
    "create-bound-request": ("request", "planned-policy"),
    "seal-bound-capture": ("seal", "source-inventory", "accepted-content"),
    "authorize-detector": ("run-input",),
    "renew-detector": (),
}


@dataclass(frozen=True, slots=True)
class LedgerCommand:
    """Detached input data; arbitrary construction grants nothing."""

    command_bytes: bytes
    parts: tuple[bytes, ...]
    action: LedgerAction
    operation_key: UUID
    namespace_id: UUID
    expected_coordination_revision: int
    command_digest: str
    input_bytes: int
    hash_calls_reserved: int
    hash_bytes_reserved: int
    validation: Literal["input-structure-only"] = "input-structure-only"


class _Work:
    __slots__ = ("bytes", "calls")

    def __init__(self) -> None:
        self.calls = self.bytes = 0

    def reserve(self, calls: int, size: int) -> None:
        s.require(0 <= calls <= MAX_HASH_CALLS - self.calls)
        s.require(0 <= size <= MAX_HASH_BYTES - self.bytes)
        self.calls += calls
        self.bytes += size

    def raw(self, data: bytes) -> str:
        self.reserve(1, len(data))
        return c.raw_digest(data)

    def domain(self, schema_id: str, data: bytes) -> str:
        self.reserve(1, len(schema_id) + 1 + len(data))
        return c.domain_digest(schema_id, data)

    def envelope(self, name: str, data: bytes) -> dict[str, Any]:
        self.reserve(1, len("scanipy-execution/" + name + "/1\n") + len(data))
        return decode_envelope(name, data)


def _action(value: object) -> LedgerAction:
    s.require(type(value) is str and value in _ACTIONS)
    return cast(LedgerAction, value)


def _input(data: object, parts: object) -> tuple[bytes, tuple[bytes, ...], int]:
    s.require(type(data) is bytes and type(parts) is tuple)
    assert type(data) is bytes and type(parts) is tuple
    s.require(0 < len(data) <= s.MAX_OBJECT and len(parts) <= s.MAX_VALUES)
    size = len(data)
    for part in parts:
        s.require(type(part) is bytes)
        size += len(part)
        s.require(size <= s.MAX_OBJECT + 3 * s.MAX_CONTENT)
    return data, parts, size


def _header(data: bytes, action: LedgerAction) -> dict[str, Any]:
    row = c.parse_json(data)
    s.shape(
        row,
        {
            "schema": s.enum(COMMAND_SCHEMA),
            "action": s.enum(action),
            "operation_key": "uuid",
            "namespace_id": "uuid",
            "expected_coordination_revision": "count",
            "body": _BODIES[action],
            "objects": s.array(
                {"role": "token", "ordinal": "count", "length": "count", "raw_sha256": "digest"}
            ),
        },
    )
    body = row["body"]
    # These are newly decoded private JSON, never caller-owned model slots.
    if "admission" in body:
        c.decode_record(body["admission"], m.AdmissionExpectation, s.ADMISSION_EXPECTATION)
    if "bundle" in body:
        c.decode_record(body["bundle"], m.BundleExpectation, s.BUNDLE_EXPECTATION)
    return cast(dict[str, Any], row)


def _parts(row: dict[str, Any], parts: tuple[bytes, ...], size: int) -> tuple[int, int]:
    action = row["action"]
    descriptors = row["objects"]
    s.require(size <= _W[action] and len(descriptors) == len(parts))
    detectors = rules = 0
    if action == "publish-builtin":
        s.require(len(parts) >= 4)
        expected = [("publication-input", 0), ("accepted-spec", 0)]
        phase = "detector"
        for descriptor in descriptors[2:]:
            if descriptor["role"] == "rule":
                phase = "rule"
            if phase == "detector":
                expected.append(("detector", detectors))
                detectors += 1
            else:
                expected.append(("rule", rules))
                rules += 1
        s.require(detectors > 0 and rules > 0)
        s.require(len(parts[0]) <= s.MAX_AUTHORITY)
        s.require(sum(len(part) for part in parts[1:]) <= s.MAX_CONTENT)
    else:
        expected = [(role, 0) for role in _FIXED_ROLES[action]]
        s.require(len(parts) == len(expected))
        if action in ("install-policy", "record-admission"):
            maximum = s.MAX_POLICY if action == "install-policy" else s.MAX_OBJECT
            s.require(len(parts[0]) <= maximum and len(parts[1]) == 384)
        else:
            s.require(all(len(part) <= s.MAX_CONTENT for part in parts))
    s.require([(item["role"], item["ordinal"]) for item in descriptors] == expected)
    s.require(
        all(item["length"] == len(part) for item, part in zip(descriptors, parts, strict=True))
    )
    return detectors, rules


def _same(left: dict[str, Any], right: dict[str, Any], names: tuple[str, ...]) -> None:
    s.require(all(left[name] == right[name] for name in names), "content-mismatch")


def _publication(
    row: dict[str, Any], parts: tuple[bytes, ...], detectors: int, rules: int, work: _Work
) -> None:
    work.reserve(10, len(parts[0]))
    frame = c.decode_frame(parts[0], s.PUBLICATION_INPUT)
    expected = row["body"]["bundle"]
    _same(frame.manifest, expected, tuple(s.BUNDLE_EXPECTATION))
    # This first bounded owner decoder has not exposed its actual model count.
    work.reserve(s.MAX_VALUES, len(parts[1]))
    manifest, models = c.decode_spec(parts[1])
    s.require(
        len(manifest["detectors"]) == detectors
        and sum(len(item["rules"]) for item in manifest["detectors"]) == rules,
        "content-mismatch",
    )
    _same(manifest, expected, ("registry_id", "scope", "org_id", "bundle_id", "S_version"))
    model_bytes = sum(len(model) for model in models)
    work.reserve(len(models), model_bytes)
    bundle = m.AcceptedBundleBytes(parts[1], parts[2 : 2 + detectors], parts[2 + detectors :])
    content_bytes = sum(len(part) for part in parts[1:])
    work.reserve(
        3 * len(models) + 3 + 2 * detectors + 3 * rules,
        3 * model_bytes
        + content_bytes
        + sum(len(part) for part in parts[2:])
        + 2 * (s.MAX_CONTENT + len("scanipy-execution/accepted-content/1\n"))
        + rules * (s.MAX_OBJECT + len(s.SEMANTIC_BINDING) + 1),
    )
    members = c.qualified_members(bundle)
    for key, detector_raw, rule_raw, model_raw in members:
        s.require(
            key.accepted_content_digest == expected["accepted_content_digest"], "content-mismatch"
        )
        detector = c.decode_document(detector_raw, s.DETECTOR, canonical=False)
        for language in detector["languages"]:
            work.reserve(2, len(rule_raw) + len(model_raw))
            bound = decode_bound_rule(
                rule_raw, model_raw, key=key, language=language, limits=ScalarLimits()
            )
            rule = bound.rule_document
            s.require(
                (
                    rule.get("class_id"),
                    rule.get("engine"),
                    rule.get("spec_id"),
                    rule.get("model_artifact_digest"),
                    rule.get("projection_profile"),
                )
                == (
                    detector["class_id"],
                    detector["engine"],
                    key.rule_id,
                    key.model_raw_sha256,
                    s.PROJECTION,
                ),
                "content-mismatch",
            )
            languages = rule.get("languages")
            s.require(type(languages) is FrozenArray, "content-mismatch")
            assert isinstance(languages, FrozenArray)
            s.require(languages.values == tuple(detector["languages"]), "content-mismatch")

    admission = row["body"]["admission"]
    policy_raw, checkpoint_raw = (
        frame.object("current-policy"),
        frame.object("admission-checkpoint"),
    )
    policy, checkpoint = frame.document("current-policy"), frame.document("admission-checkpoint")
    approval, inventory = (
        frame.document("approval-statement"),
        frame.document("approval-evidence-inventory"),
    )
    adoption = frame.document("operator-adoption")
    for document in (policy, checkpoint, approval, adoption):
        _same(document, expected, ("registry_id", "scope", "org_id"))
    _same(approval, expected, ("bundle_id", "S_version", "accepted_content_digest"))
    _same(adoption, expected, ("bundle_id", "accepted_content_digest"))
    policy_digest = work.domain(s.POLICY, policy_raw)
    s.require(
        policy_digest
        == admission["policy_digest"]
        == checkpoint["policy_digest"]
        == approval["trust_policy_digest"]
        and policy["revision"] == admission["policy_revision"] == checkpoint["policy_revision"]
        and work.domain(s.ADMISSION, checkpoint_raw) == admission["checkpoint_digest"]
        and checkpoint["generation"] == admission["checkpoint_generation"]
        and checkpoint["admission_epoch"] == admission["admission_epoch"],
        "content-mismatch",
    )
    s.require(
        work.domain(s.INVENTORY, frame.object("approval-evidence-inventory"))
        == approval["evidence_inventory_digest"],
        "content-mismatch",
    )
    descriptor = inventory["objects"][0]
    adoption_raw = frame.object("operator-adoption")
    s.require(
        descriptor["length"] == len(adoption_raw)
        and descriptor["raw_sha256"] == work.raw(adoption_raw)
        and adoption["actor_id"] == approval["issuer_actor_id"],
        "content-mismatch",
    )
    grants = [grant for grant in policy["grants"] if grant["grant_id"] == approval["grant_id"]]
    s.require(len(grants) == 1, "content-mismatch")
    _same(
        grants[0],
        approval,
        (
            "key_id",
            "key_version",
            "spki_sha256",
            "signature_profile",
            "issuer_actor_id",
            "scope",
            "org_id",
        ),
    )
    s.require(work.raw(frame.object("issuer-spki")) == approval["spki_sha256"], "content-mismatch")
    # No signature/DER, grant eligibility, installed root or currentness checks.


def _occurrence(row: dict[str, Any], parts: tuple[bytes, ...], work: _Work) -> None:
    action = row["action"]
    values = [
        work.envelope(name, part) for name, part in zip(_FIXED_ROLES[action], parts, strict=True)
    ]
    if action == "create-bound-request":
        request, policy = values
        expected = row["body"]["bundle"]
        s.require(expected["scope"] == "customer", "scope-mismatch")
        s.require(request["org_id"] == expected["org_id"], "scope-mismatch")
        s.require(
            request["requested_s_version"] == expected["S_version"]
            and request["identity_policy"] == policy["identity_policy"]
            and request["requested_policy_digest"]
            == work.domain("scanipy-execution/planned-policy/1", parts[1]),
            "content-mismatch",
        )
    elif action == "seal-bound-capture":
        seal, _inventory, content = values
        s.require(
            seal["inventory_digest"]
            == work.domain("scanipy-execution/source-inventory/1", parts[1])
            and seal["accepted_content_digest"]
            == work.domain("scanipy-execution/accepted-content/1", parts[2]),
            "content-mismatch",
        )
        s.require(
            [binding["detector_content_digest"] for binding in seal["bindings"]]
            == content["detector_sha256s"]
            and [
                rule["content_digest"] for binding in seal["bindings"] for rule in binding["rules"]
            ]
            == content["rule_sha256s"],
            "content-mismatch",
        )


def decode_ledger_command(
    command_bytes: bytes, parts: tuple[bytes, ...], *, expected_action: LedgerAction
) -> LedgerCommand:
    """Validate supplied input closure only; no lookup, authority, clock or IO."""
    action = _action(expected_action)
    data, private_parts, size = _input(command_bytes, parts)
    row = _header(data, action)
    detectors, rules = _parts(row, private_parts, size)
    work = _Work()
    try:
        for descriptor, part in zip(row["objects"], private_parts, strict=True):
            s.require(work.raw(part) == descriptor["raw_sha256"], "content-mismatch")
        if action in ("install-policy", "record-admission"):
            schema_id = s.POLICY if action == "install-policy" else s.ADMISSION
            document = c.decode_document(private_parts[0], schema_id)
            body_field = (
                "predecessor_policy_digest"
                if action == "install-policy"
                else "predecessor_checkpoint_digest"
            )
            document_field = (
                "previous_policy_digest"
                if action == "install-policy"
                else "previous_checkpoint_digest"
            )
            s.require(row["body"][body_field] == document[document_field], "content-mismatch")
        elif action == "publish-builtin":
            _publication(row, private_parts, detectors, rules, work)
        else:
            _occurrence(row, private_parts, work)
        digest = work.domain(COMMAND_SCHEMA, data)
    except (BoundRuleError, EnvelopeError) as error:
        raise s.VerificationError("invalid-input") from error
    return LedgerCommand(
        data,
        private_parts,
        action,
        UUID(row["operation_key"]),
        UUID(row["namespace_id"]),
        row["expected_coordination_revision"],
        digest,
        size,
        work.calls,
        work.bytes,
    )


def _uuid_snapshot(value: object) -> UUID:
    s.require(type(value) is UUID)
    integer = object.__getattribute__(value, "int")
    s.require(type(integer) is int and 0 <= integer < 2**128)
    return UUID(int=integer)


def encode_ledger_command(
    command: LedgerCommand, *, expected_action: LedgerAction
) -> tuple[bytes, tuple[bytes, ...]]:
    """Revalidate a detached carrier, preserving the exact original canonical bytes."""
    action = _action(expected_action)
    s.require(type(command) is LedgerCommand)
    try:
        row = {
            field.name: object.__getattribute__(command, field.name)
            for field in fields(LedgerCommand)
        }
        row["operation_key"] = _uuid_snapshot(row["operation_key"])
        row["namespace_id"] = _uuid_snapshot(row["namespace_id"])
    except AttributeError as error:
        raise s.VerificationError() from error
    s.require(_action(row["action"]) == action)
    for name in (
        "expected_coordination_revision",
        "input_bytes",
        "hash_calls_reserved",
        "hash_bytes_reserved",
    ):
        s.shape(row[name], "count")
    s.shape(row["command_digest"], "digest")
    s.shape(row["validation"], s.enum("input-structure-only"))
    fresh = decode_ledger_command(row["command_bytes"], row["parts"], expected_action=action)
    for field in fields(LedgerCommand):
        s.require(row[field.name] == object.__getattribute__(fresh, field.name), "content-mismatch")
    return fresh.command_bytes, fresh.parts
