"""Closed v1 shape vocabulary. Changes require a new protocol version."""

from __future__ import annotations

from typing import Any

PREFIX = "scanipy-execution/"
TREE_ALGORITHM = "sha256-length-prefixed-path-and-content-v1"
MAX_ENVELOPE = 1_048_576
MAX_BATCH = 67_108_864
MAX_OCCURRENCE = 16_777_216
MAX_COUNT = 10_000
MAX_FAILURE_PREFIX = 65_536
MAX_DEPTH = 32
ENGINES = ["ifds", "ide", "semgrep", "cpg-query", "external"]


def enum(*values: str | int) -> dict[str, Any]:
    return {"$enum": list(values)}


def nullable(shape: object) -> dict[str, Any]:
    return {"$nullable": shape}


def array(shape: object) -> dict[str, Any]:
    return {"$array": shape}


def schema(name: str, **fields: object) -> dict[str, Any]:
    return {"schema": enum(PREFIX + name + "/1"), **fields}


RETRY = schema(
    "retry-policy",
    max_attempts="int:1:16",
    lease_seconds="int:1:900",
    initial_backoff_seconds="int:0:3600",
    max_backoff_seconds="int:0:86400",
)
IDENTITY_POLICY = {
    "mode": enum("required", "not-applicable"),
    "policy_id": "nonempty",
    "policy_digest": "digest",
    "reason": nullable("nonempty"),
}
RULE = {"rule_id": "nonempty", "semantic_digest": "digest", "content_digest": "digest"}
BINDING = {
    "key": "nonempty",
    "detector_id": "nonempty",
    "engines": array(enum(*ENGINES)),
    "adapter_policy_digest": "digest",
    "class_id": "nonempty",
    "language": "nonempty",
    "rules": array(RULE),
    "detector_content_digest": "digest",
    "tool_policy_digest": "digest",
    "code_policy_digest": "digest",
    "environment_policy_digest": "digest",
    "expected_tool_digest": nullable("digest"),
    "expected_code_digest": nullable("digest"),
    "expected_image_digest": nullable("env"),
}
RUNNER = {
    "code_policy_digest": "digest",
    "environment_policy_digest": "digest",
    "expected_code_digest": nullable("digest"),
    "expected_image_digest": nullable("env"),
}
LOCATION = {
    "status": enum("known", "partial", "unknown"),
    "path": nullable("path"),
    "start_line": nullable("positive"),
    "start_column": nullable("positive"),
    "end_line": nullable("positive"),
    "end_column": nullable("positive"),
}
OCCURRENCE = {
    "result_key": "nonempty",
    "duplicate_ordinal": "nat",
    "tool_ordinal": "nat",
    "engine": enum(*ENGINES),
    "rule_id": "nonempty",
    "cwe": nullable("nonempty"),
    "severity": enum("info", "low", "medium", "high", "critical"),
    "message": "text",
    "location": LOCATION,
    "raw_sha256": "digest",
    "witness_sha256": nullable("digest"),
}
ARTIFACT = {
    "status": enum("completed", "pending", "running", "failed", "not-applicable"),
    "digest": nullable("digest"),
    "fingerprint_class": nullable(enum("strong", "weak")),
    "namespace": nullable("nonempty"),
    "annotation": enum("canonical iff fingerprint_class = strong"),
}
IDENTITY = {"schema_version": enum(2), "cpg_order": ARTIFACT, "slice": ARTIFACT}
ACTUAL_IDENTITY = {
    "policy_digest": "digest",
    "artifact_digest": "digest",
    "evidence_digest": "digest",
}
ERROR = {"code": "nonempty", "message": "text"}

SCHEMAS = {
    "retry-policy": RETRY,
    "planned-policy": schema(
        "planned-policy",
        bindings=array(BINDING),
        capture_detection_runner=RUNNER,
        identity_runner=RUNNER,
        identity_policy=IDENTITY_POLICY,
    ),
    "request": schema(
        "request",
        org_id="uuid",
        codebase_id="uuid",
        lineage_id="uuid",
        predecessor_request_id=nullable("uuid"),
        idempotency_key="nonempty",
        source_selector={"kind": enum("git-ref"), "value": "nonempty"},
        requested_s_version="nonempty",
        requested_policy_digest="digest",
        retry_policy=RETRY,
        identity_policy=IDENTITY_POLICY,
    ),
    "source-inventory": schema(
        "source-inventory", files=array({"path": "path", "size": "nat", "sha256": "digest"})
    ),
    "seal": schema(
        "seal",
        request_id="uuid",
        resolved_commit="commit",
        commit_algorithm=enum("git-sha1"),
        tree_algorithm=enum(TREE_ALGORITHM),
        tree_digest="digest",
        inventory_digest="digest",
        storage_object_id="uuid",
        storage_reference="nonempty",
        retain_seconds="int:0:315360000",
        s_version="nonempty",
        planned_policy_digest="digest",
        accepted_content_digest="digest",
        acceptance_evidence_digest="digest",
        intended_files=array("path"),
        bindings=array(BINDING),
    ),
    "accepted-content": schema(
        "accepted-content",
        spec_sha256="digest",
        detector_sha256s=array("digest"),
        rule_sha256s=array("digest"),
    ),
    "work-payload": schema(
        "work-payload",
        request_id="uuid",
        kind=enum("capture_detection", "identity"),
        occurrence_id=nullable("uuid"),
        policy=IDENTITY_POLICY,
    ),
    "attempt-policy": schema(
        "attempt-policy",
        assignment_id="nonempty",
        code_policy_digest="digest",
        environment_policy_digest="digest",
        lease_seconds="int:1:900",
    ),
    "run-input": schema(
        "run-input",
        binding_key="nonempty",
        run_ordinal="nat",
        argv=array("text"),
        cwd="nonempty",
        tool_policy_digest="digest",
        code_policy_digest="digest",
        environment_policy_digest="digest",
    ),
    "occurrence-inventory": schema("occurrence-inventory", occurrences=array(OCCURRENCE)),
    "detection-batch": schema(
        "detection-batch",
        run_id="uuid",
        status=enum("completed", "failed"),
        tool_identity=ACTUAL_IDENTITY,
        code_identity=ACTUAL_IDENTITY,
        actual_invocation={"argv": array("text"), "cwd": "nonempty"},
        detector_env_digest="env",
        full_env_digest=nullable("env"),
        coverage={
            "status": enum("complete", "partial", "failed"),
            "files": array("path"),
            "rules": array("nonempty"),
            "errors": array(ERROR),
        },
        stdout_sha256="digest",
        stderr_sha256="digest",
        occurrences=array(OCCURRENCE),
        inventory_digest="digest",
    ),
    "run-failure": schema(
        "run-failure",
        code="nonempty",
        message="text",
        prefix_sha256="digest",
        observed_byte_count=nullable("nat"),
        truncated="bool",
        observed_full_sha256=nullable("digest"),
    ),
    "attempt-result": schema(
        "attempt-result",
        status=enum("completed", "failed"),
        retryable="bool",
        error=nullable(ERROR),
        actual_code_digest=nullable("digest"),
        actual_env_digest=nullable("env"),
        completed_run_ids=array("uuid"),
        identity=nullable(IDENTITY),
        identity_policy_reason=nullable("nonempty"),
    ),
    "lease-release": schema(
        "lease-release",
        attempt_id="uuid",
        token="positive",  # noqa: S106 -- numeric fencing type, not a credential
        reason="nonempty",
    ),
    "cancellation": schema("cancellation", request_id="uuid", reason="nonempty"),
    "retirement": schema(
        "retirement",
        capture_id="uuid",
        storage_object_id="uuid",
        token="positive",  # noqa: S106 -- integer fencing type, not a credential
        reason="nonempty",
        evidence_digest="digest",
    ),
}
