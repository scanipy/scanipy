"""Closed accepted-input v1 metadata shapes; no signature or grant is inferred.

The finite schema inventory is the contract in ACCEPTED-INPUT-RESOLVER.md.
Semantic rule/model decoding belongs to analysis.ifds.bound_rules, not here.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any, Final, cast
from uuid import UUID

MAX_CONTENT: Final = 1048576
MAX_AUTHORITY: Final = 1048576
MAX_LIVE: Final = 262144
MAX_OBJECT: Final = 65536
MAX_POLICY: Final = 131072
MAX_PACKET: Final = 2621440
MAX_OUTPUT: Final = 16384
MAX_VALUES: Final = 20000
MAX_DEPTH: Final = 32
MAX_STRING: Final = 16384

SPEC_FRAME: Final = "scanipy-accepted-spec-set/1"
S_MANIFEST: Final = "scanipy-accepted-s-manifest/1"
DETECTOR: Final = "scanipy-accepted-detector/1"
SEMANTIC_BINDING: Final = "scanipy-rule-semantics-binding/1"
INSTALLED_TRUST: Final = "scanipy-registry-installed-trust/1"
POLICY: Final = "scanipy-accepted-trust-policy/1"
APPROVAL: Final = "scanipy-accepted-approval/1"
INVENTORY: Final = "scanipy-accepted-evidence-inventory/1"
ADOPTION: Final = "scanipy-operator-adoption/1"
PUBLICATION: Final = "scanipy-accepted-publication/1"
ADMISSION: Final = "scanipy-registry-admission/1"
SEALED: Final = "scanipy-sealed-acceptance/1"
LIVE: Final = "scanipy-registry-current-authority/1"
PUBLICATION_INPUT: Final = "scanipy-publication-input/1"
SEAL_AUTHORIZATION: Final = "scanipy-capture-seal-authorization/1"
EXECUTION: Final = "scanipy-execution-authorization/1"
DENIAL: Final = "scanipy-execution-denial/1"
REQUEST: Final = "scanipy-accepted-verifier-request/1"
RESULT: Final = "scanipy-accepted-verifier-result/1"
RUNTIME: Final = "scanipy-accepted-verifier-runtime/1"
SIGNATURE_PROFILE: Final = "scanipy-registry-rsa-pss-sha256/1"
RULE: Final = "scanipy-bound-rule-set/1"
MODEL: Final = "scanipy-operation-models/1"
SEMANTICS: Final = "scanipy-scalar-ifds/1"
PROJECTION: Final = "scanipy-java-python-scalar-flow/1"
SOURCE_SYNTAX: Final = "scanipy-source-syntax/1"

FAILURE_CODES: Final = (
    "invalid-input",
    "unsupported-schema",
    "content-mismatch",
    "untrusted-root",
    "signature-invalid",
    "grant-denied",
    "policy-stale",
    "policy-expired",
    "checkpoint-denied",
    "scope-mismatch",
    "ledger-mismatch",
    "fence-stale",
    "runtime-unsupported",
    "internal-error",
)
CLASSES: Final = (
    "injection",
    "path-traversal",
    "ssrf",
    "deserialization",
    "xss",
    "crypto-misuse",
    "authn-authz",
    "secrets",
    "dep-cve",
    "memory-safety",
)
MODES: Final = ("publication-preflight", "historical", "execution")


class VerificationError(ValueError):
    """Safe fixed code; private original failures may be explicitly chained."""

    def __init__(self, code: str = "invalid-input") -> None:
        if type(code) is not str or code not in FAILURE_CODES:
            code = "internal-error"
        self.code = code
        super().__init__(code)


def require(condition: bool, code: str = "invalid-input") -> None:
    if not condition:
        raise VerificationError(code)


def utc(value: str, *, microseconds: bool = False) -> datetime:
    """Exact calendar format, including years before 1000 and microseconds."""
    expression = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    expression += r"\.[0-9]{6}Z" if microseconds else "Z"
    require(type(value) is str and re.fullmatch(expression, value) is not None)
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise VerificationError() from exc


def text(value: object, maximum: int = MAX_STRING, *, nonempty: bool = False) -> str:
    require(type(value) is str)
    assert isinstance(value, str)
    require(len(value) <= maximum and (bool(value) or not nonempty) and "\0" not in value)
    try:
        require(len(value.encode("utf-8")) <= maximum)
    except UnicodeError as exc:
        raise VerificationError() from exc
    return value


# A deliberately small local schema notation, never input-supplied instructions.
def enum(*values: object) -> tuple[str, tuple[object, ...]]:
    return ("enum", values)


def nullable(shape: Any) -> tuple[str, Any]:  # noqa: ANN401 -- finite schema notation
    return ("nullable", shape)


def array(shape: Any, minimum: int = 0, maximum: int = MAX_VALUES) -> tuple[Any, ...]:  # noqa: ANN401
    return ("array", shape, minimum, maximum)


def shape(value: Any, expected: Any) -> None:  # noqa: ANN401 -- validated JSON primitives
    if type(expected) is dict:
        require(type(value) is dict and value.keys() == expected.keys())
        for name, rule in expected.items():
            shape(value[name], rule)
        return
    if type(expected) is tuple:
        kind = expected[0]
        if kind == "nullable":
            if value is not None:
                shape(value, expected[1])
        elif kind == "enum":
            require(any(type(value) is type(item) and value == item for item in expected[1]))
        else:
            require(type(value) is list and expected[2] <= len(value) <= expected[3])
            for item in value:
                shape(item, expected[1])
        return
    if expected in ("count", "positive"):
        require(type(value) is int and (0 if expected == "count" else 1) <= value < 2**63)
        return
    limits = {
        "digest": 64,
        "uuid": 36,
        "version": 32,
        "token": 128,
        "id": 128,
        "cwe": 11,
        "path": 4096,
        "reason": 4096,
        "second": 20,
        "instant": 27,
    }
    value = text(value, limits.get(expected, MAX_STRING), nonempty=expected == "reason")
    patterns = {
        "digest": r"[0-9a-f]{64}",
        "token": r"[A-Za-z0-9][A-Za-z0-9._:-]*",
        "id": r"[A-Za-z][A-Za-z0-9_.:/-]{0,127}",
        "cwe": r"CWE-[1-9][0-9]{0,6}",
    }
    if expected in patterns:
        require(re.fullmatch(patterns[expected], value, flags=re.ASCII) is not None)
    elif expected == "uuid":
        try:
            require(str(UUID(value)) == value)
        except ValueError as exc:
            raise VerificationError() from exc
    elif expected == "version":
        require(
            re.fullmatch(r"(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})\.(0|[1-9][0-9]{0,9})", value)
            is not None
        )
        require(all(int(part) <= 2147483647 for part in value.split(".")))
    elif expected in ("second", "instant"):
        utc(value, microseconds=expected == "instant")
    elif expected == "path":
        require(value.startswith("/") and str(PurePosixPath(value)) == value and value != "/")
        require(all(part not in ("", ".", "..") for part in value.split("/")[1:]))
        require("\\" not in value)
        require(not any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in value))
    else:
        require(expected in ("text", "reason"))


SCOPE: Final = {"scope": enum("global", "customer"), "org_id": nullable("uuid")}
NAMESPACE: Final = {"registry_id": "uuid", **SCOPE}
PROFILE: Final = {
    "language": enum("python", "java"),
    "projection_profile": enum(PROJECTION),
    "source_syntax_schema": enum(SOURCE_SYNTAX),
}
MODEL_MEMBER: Final = {
    "artifact_id": "id",
    "version": "version",
    "schema": enum(MODEL),
    "raw_sha256": "digest",
}
RULE_MEMBER: Final = {
    "rule_id": "id",
    "artifact_id": "id",
    "version": "version",
    "schema": enum(RULE),
    "raw_sha256": "digest",
    "semantics": enum(SEMANTICS),
    "projection_profile": enum(PROJECTION),
    "model_artifact_id": "id",
    "model_raw_sha256": "digest",
    "semantic_descriptor_digest": "digest",
}
DETECTOR_MEMBER: Final = {
    "detector_id": "id",
    "detector_version": "version",
    "detector_schema": enum(DETECTOR),
    "detector_sha256": "digest",
    "class_id": enum(*CLASSES),
    "language_profiles": array(PROFILE, 1, 2),
    "engine": enum("ifds"),
    "rules": array(RULE_MEMBER, 1),
}
OBJECT: Final = {
    "role": "token",
    "schema": nullable("token"),
    "length": "count",
    "raw_sha256": "digest",
}
# Schema IDs contain '/', unlike inert authority key labels.
OBJECT["schema"] = nullable("id")
GRANT: Final = {
    "grant_id": "uuid",
    "key_id": "token",
    "key_version": "positive",
    "spki_sha256": "digest",
    "signature_profile": enum(SIGNATURE_PROFILE),
    "issuer_actor_id": "uuid",
    "capability": enum("publish-builtin"),
    **SCOPE,
    "not_before": "second",
    "not_after": "second",
    "status": enum("active", "retired", "revoked"),
    "status_changed_at": nullable("second"),
}
BUNDLE_EXPECTATION: Final = {
    **NAMESPACE,
    "bundle_id": "uuid",
    "S_version": "version",
    "accepted_content_digest": "digest",
}
ADMISSION_EXPECTATION: Final = {
    "checkpoint_digest": "digest",
    "checkpoint_generation": "positive",
    "admission_epoch": "uuid",
    "policy_digest": "digest",
    "policy_revision": "positive",
}
EXECUTION_BINDING: Final = {
    **dict.fromkeys(
        (
            "org_id",
            "codebase_id",
            "request_id",
            "capture_id",
            "seal_id",
            "work_item_id",
            "work_attempt_id",
            "detector_run_id",
            "capture_lease_id",
            "authorization_event_id",
        ),
        "uuid",
    ),
    "fencing_token": "positive",
    "work_revision": "count",
    **dict.fromkeys(
        (
            "run_input_digest",
            "requested_policy_digest",
            "attempt_policy_digest",
            "authorization_digest",
        ),
        "digest",
    ),
    "lease_expires_at": "instant",
    "capture_lease_expires_at": "instant",
}
LEDGER_EXPECTATION: Final = {
    "publication_receipt_digest": "digest",
    "request_binding_digest": "digest",
    "execution_authorization_digest": nullable("digest"),
    "binding": nullable(EXECUTION_BINDING),
    "policy_event_id": nullable("uuid"),
    "admission_event_id": nullable("uuid"),
}
AUTHORITY_COMMON: Final = {
    "event_id": "uuid",
    "operation_key": "uuid",
    **NAMESPACE,
    **dict.fromkeys(
        (
            "codebase_id",
            "request_id",
            "bundle_id",
            "approval_event_id",
            "policy_event_id",
            "admission_event_id",
            "admission_epoch",
            "work_item_id",
            "work_attempt_id",
            "capture_id",
            "seal_id",
            "capture_lease_id",
        ),
        "uuid",
    ),
    **dict.fromkeys(
        (
            "request_binding_digest",
            "accepted_content_digest",
            "requested_policy_digest",
            "policy_digest",
            "checkpoint_digest",
            "attempt_policy_digest",
            "resolver_artifact_digest",
        ),
        "digest",
    ),
    "policy_revision": "positive",
    "checkpoint_generation": "positive",
    "fencing_token": "positive",
    "work_revision": "count",
    "work_kind": enum("capture_detection", "identity"),
    "lease_expires_at": "instant",
    "capture_lease_expires_at": "instant",
}
TARGET: Final = {
    "purpose": enum("detector-run", "identity-attempt"),
    "detector_run_id": nullable("uuid"),
    "run_input_digest": nullable("digest"),
    "occurrence_id": nullable("uuid"),
    "previous_authorization_id": nullable("uuid"),
}
CHECKS: Final = {
    "accepted_content_digest": "digest",
    "approval_event_id": "uuid",
    "approval_statement_digest": "digest",
    **dict.fromkeys(
        (
            "publication_receipt_digest",
            "qualified_rule_digest",
            "execution_authorization_digest",
            "current_policy_digest",
            "checkpoint_digest",
        ),
        nullable("digest"),
    ),
    "current_policy_revision": nullable("positive"),
    "checkpoint_generation": nullable("positive"),
    "admission_epoch": nullable("uuid"),
    "verified_at": "instant",
    "permission_expires_at": nullable("instant"),
}

SHAPES: Final[dict[str, dict[str, Any]]] = {
    INSTALLED_TRUST: {
        **NAMESPACE,
        "deployment_id": "uuid",
        "root_spki_sha256": "digest",
        "administrator_actor_id": "uuid",
    },
    S_MANIFEST: {
        **NAMESPACE,
        "bundle_id": "uuid",
        "S_version": "version",
        "detectors": array(DETECTOR_MEMBER, 1),
        "models": array(MODEL_MEMBER, 1),
    },
    DETECTOR: {
        "id": "id",
        "version": "version",
        "class_id": enum(*CLASSES),
        "cwes": array("cwe", 1, 64),
        "languages": array(enum("python", "java"), 1, 2),
        "frameworks": array("id", 0, 32),
        "engine": enum("ifds"),
        "severity_default": enum("low", "medium", "high", "critical"),
        "rule_ids": array("id", 1),
        "profiles": array(PROFILE, 1, 2),
    },
    SEMANTIC_BINDING: {
        "rule_raw_sha256": "digest",
        "model_raw_sha256": "digest",
        "semantics": enum(SEMANTICS),
        "projection_profile": enum(PROJECTION),
    },
    POLICY: {
        **NAMESPACE,
        "event_id": "uuid",
        "revision": "positive",
        "previous_policy_digest": nullable("digest"),
        "valid_from": "second",
        "expires_at": "second",
        "grants": array(GRANT, 0, 64),
    },
    APPROVAL: {
        **NAMESPACE,
        "event_id": "uuid",
        "publication_key": "uuid",
        "bundle_id": "uuid",
        "S_version": "version",
        "accepted_content_digest": "digest",
        "approval_kind": enum("builtin-operator"),
        "issuer_actor_id": "uuid",
        "grant_id": "uuid",
        "key_id": "token",
        "key_version": "positive",
        "spki_sha256": "digest",
        "signature_profile": enum(SIGNATURE_PROFILE),
        "trust_policy_digest": "digest",
        "issued_at": "second",
        "evidence_inventory_digest": "digest",
        "proposal_id": enum(None),
    },
    INVENTORY: {"approval_kind": enum("builtin-operator"), "objects": array(OBJECT, 1, 1)},
    ADOPTION: {
        **NAMESPACE,
        "decision_id": "uuid",
        "actor_id": "uuid",
        "action": enum("adopt-builtin"),
        "bundle_id": "uuid",
        "accepted_content_digest": "digest",
        "decided_at": "second",
        "reason": "reason",
        "proposal_id": enum(None),
    },
    PUBLICATION: {
        **NAMESPACE,
        "approval_event_id": "uuid",
        "publication_key": "uuid",
        "bundle_id": "uuid",
        **dict.fromkeys(
            (
                "approval_statement_digest",
                "approval_signature_sha256",
                "evidence_inventory_digest",
                "accepted_content_digest",
                "policy_digest",
                "checkpoint_digest",
                "publisher_artifact_digest",
            ),
            "digest",
        ),
        "policy_revision": "positive",
        "checkpoint_generation": "positive",
        "admission_epoch": "uuid",
        "published_at": "instant",
        "publisher_actor_id": "uuid",
    },
    ADMISSION: {
        **NAMESPACE,
        "event_id": "uuid",
        "deployment_id": "uuid",
        "generation": "positive",
        "previous_checkpoint_digest": nullable("digest"),
        "admission_epoch": "uuid",
        "action": enum("admit", "block"),
        "policy_revision": "positive",
        "policy_digest": "digest",
        "issued_at": "second",
        "expires_at": "second",
        "administrator_actor_id": "uuid",
        "reason": "reason",
    },
    SEALED: {
        **dict.fromkeys(
            (
                "registry_id",
                "request_id",
                "org_id",
                "codebase_id",
                "bundle_id",
                "approval_event_id",
                "admission_epoch",
            ),
            "uuid",
        ),
        **dict.fromkeys(
            (
                "accepted_content_digest",
                "publication_policy_digest",
                "current_policy_digest",
                "checkpoint_digest",
                "verifier_artifact_digest",
            ),
            "digest",
        ),
        "current_policy_revision": "positive",
        "checkpoint_generation": "positive",
        "resolved_at": "instant",
        "objects": array(OBJECT, 15, 15),
    },
    LIVE: {**NAMESPACE, **ADMISSION_EXPECTATION, "objects": array(OBJECT, 4, 4)},
    PUBLICATION_INPUT: {**BUNDLE_EXPECTATION, "objects": array(OBJECT, 10, 10)},
    SEAL_AUTHORIZATION: {**AUTHORITY_COMMON, "authorized_at": "instant"},
    EXECUTION: {
        **AUTHORITY_COMMON,
        **TARGET,
        "authorized_at": "instant",
        "action": enum("initial", "renew"),
    },
    DENIAL: {
        **AUTHORITY_COMMON,
        **TARGET,
        "observed_at": "instant",
        "reason": enum(
            "grant-revoked",
            "grant-expired",
            "policy-expired",
            "unsupported-authority",
            "missing-runtime-pin",
            "scope-conflict",
        ),
    },
    RUNTIME: {
        "implementation": enum("cpython"),
        "python_version": "version",
        "python_executable": "path",
        "python_executable_sha256": "digest",
        "worker_script": "path",
        "worker_script_sha256": "digest",
        "application_root": "path",
        "application_artifact_digest": "digest",
        "stdlib_roots": array("path", 1, 4),
        "dependency_roots": array("path", 1, 4),
        "dependency_artifact_digest": "digest",
        "verifier_artifact_digest": "digest",
        "work_root": "path",
        "resource_profile": enum("scanipy-verifier-limits/1"),
    },
    RESULT: {
        "operation_id": nullable("uuid"),
        "request_sha256": nullable("digest"),
        "mode": nullable(enum(*MODES)),
        "status": enum("verified", "rejected"),
        "failure_code": nullable(enum(*FAILURE_CODES)),
        "checks": nullable(CHECKS),
    },
}
for _schema_id, _fields in SHAPES.items():
    _fields["schema"] = enum(_schema_id)

SEALED_ROLES: Final = (
    ("approval-statement", APPROVAL),
    ("approval-signature", None),
    ("issuer-spki", None),
    ("publication-receipt", PUBLICATION),
    ("publication-policy", POLICY),
    ("publication-policy-signature", None),
    ("publication-checkpoint", ADMISSION),
    ("publication-checkpoint-signature", None),
    ("current-policy", POLICY),
    ("current-policy-signature", None),
    ("trust-root-spki", None),
    ("approval-evidence-inventory", INVENTORY),
    ("operator-adoption", ADOPTION),
    ("admission-checkpoint", ADMISSION),
    ("admission-checkpoint-signature", None),
)
PUBLICATION_ROLES: Final = tuple(
    item
    for item in SEALED_ROLES
    if item[0]
    not in {
        "publication-receipt",
        "publication-policy",
        "publication-policy-signature",
        "publication-checkpoint",
        "publication-checkpoint-signature",
    }
)
LIVE_ROLES: Final = tuple(
    item
    for item in SEALED_ROLES
    if item[0]
    in {
        "current-policy",
        "current-policy-signature",
        "admission-checkpoint",
        "admission-checkpoint-signature",
    }
)
FRAME_ROLES: Final = {SEALED: SEALED_ROLES, PUBLICATION_INPUT: PUBLICATION_ROLES, LIVE: LIVE_ROLES}


def unique(values: list[Any]) -> None:
    require(len(set(values)) == len(values))


def scoped(value: dict[str, Any]) -> None:
    if "scope" in value:
        require((value["scope"] == "global") == (value["org_id"] is None), "scope-mismatch")


def validate_document(value: Any, schema_id: str) -> dict[str, Any]:  # noqa: ANN401
    require(type(schema_id) is str and schema_id in SHAPES, "unsupported-schema")
    shape(value, SHAPES[schema_id])
    scoped(value)
    if schema_id == POLICY:
        require((value["revision"] == 1) == (value["previous_policy_digest"] is None))
        require(utc(value["valid_from"]) < utc(value["expires_at"]))
        unique([grant["grant_id"] for grant in value["grants"]])
        unique([(grant["key_id"], grant["key_version"]) for grant in value["grants"]])
        for grant in value["grants"]:
            scoped(grant)
            require(
                (grant["scope"], grant["org_id"]) == (value["scope"], value["org_id"]),
                "scope-mismatch",
            )
            require(utc(grant["not_before"]) < utc(grant["not_after"]))
            require((grant["status"] == "active") == (grant["status_changed_at"] is None))
    elif schema_id == ADMISSION:
        require((value["generation"] == 1) == (value["previous_checkpoint_digest"] is None))
        seconds = (utc(value["expires_at"]) - utc(value["issued_at"])).total_seconds()
        require(0 < seconds <= 604800)
    elif schema_id == DETECTOR:
        for name in ("cwes", "languages", "frameworks", "rule_ids"):
            unique(value[name])
        require([item["language"] for item in value["profiles"]] == value["languages"])
    elif schema_id == S_MANIFEST:
        unique([member["detector_id"] for member in value["detectors"]])
        for detector in value["detectors"]:
            unique([item["language"] for item in detector["language_profiles"]])
            unique([item["rule_id"] for item in detector["rules"]])
            unique([item["artifact_id"] for item in detector["rules"]])
        unique([(item["artifact_id"], item["version"]) for item in value["models"]])
        unique([item["raw_sha256"] for item in value["models"]])
        model_keys = {(item["artifact_id"], item["raw_sha256"]) for item in value["models"]}
        used = {
            (rule["model_artifact_id"], rule["model_raw_sha256"])
            for item in value["detectors"]
            for rule in item["rules"]
        }
        require(used == model_keys, "content-mismatch")
    elif schema_id in FRAME_ROLES:
        require(
            [(item["role"], item["schema"]) for item in value["objects"]]
            == list(FRAME_ROLES[schema_id])
        )
    elif schema_id == INVENTORY:
        require(
            (value["objects"][0]["role"], value["objects"][0]["schema"])
            == ("operator-adoption", ADOPTION)
        )
    elif schema_id in (SEAL_AUTHORIZATION, EXECUTION, DENIAL):
        if schema_id == SEAL_AUTHORIZATION:
            require(value["work_kind"] == "capture_detection")
        else:
            detector = value["purpose"] == "detector-run"
            require((value["work_kind"] == "capture_detection") == detector)
            require((value["detector_run_id"] is not None) == detector)
            require((value["run_input_digest"] is not None) == detector)
            require((value["occurrence_id"] is None) == detector)
            if schema_id == EXECUTION:
                require(
                    (value["action"] == "initial") == (value["previous_authorization_id"] is None)
                )
        if schema_id != DENIAL:
            start = utc(value["authorized_at"], microseconds=True)
            require(start < utc(value["lease_expires_at"], microseconds=True))
            require(start < utc(value["capture_lease_expires_at"], microseconds=True))
    elif schema_id == RUNTIME:
        require(value["python_version"].startswith("3.11."), "runtime-unsupported")
        unique(value["stdlib_roots"] + [value["application_root"]] + value["dependency_roots"])
    elif schema_id == RESULT:
        verified = value["status"] == "verified"
        require(
            (value["checks"] is not None) == verified
            and (value["failure_code"] is None) == verified
        )
        if verified:
            require(
                all(value[key] is not None for key in ("operation_id", "request_sha256", "mode"))
            )
            validate_checks(value["checks"], value["mode"])
        else:
            require((value["operation_id"] is None) == (value["mode"] is None))
    return cast("dict[str, Any]", value)


def validate_checks(value: dict[str, Any], mode: str) -> None:
    shape(value, CHECKS)
    require(mode in MODES)
    current = (
        "current_policy_digest",
        "current_policy_revision",
        "checkpoint_digest",
        "checkpoint_generation",
        "admission_epoch",
    )
    for key in current:
        require((value[key] is not None) == (mode != "historical"))
    require((value["publication_receipt_digest"] is not None) == (mode != "publication-preflight"))
    for key in ("qualified_rule_digest", "execution_authorization_digest", "permission_expires_at"):
        require((value[key] is not None) == (mode == "execution"))
    if mode == "execution":
        require(
            utc(value["verified_at"], microseconds=True)
            < utc(value["permission_expires_at"], microseconds=True)
        )
