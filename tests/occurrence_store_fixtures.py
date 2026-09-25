"""Explicit controlled store fixtures, never actual SCM/registry/runtime evidence."""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID, uuid4

from analysis.artifact_identity import GRAPH_V2, SLICE_V2, ArtifactIdentity
from services.scan.occurrence_store.codec import CanonicalEnvelope, encode_envelope
from services.scan.occurrence_store.models import (
    CaptureSeal,
    DetectionBatch,
    RawObservation,
    RequestInput,
)

SPEC = b"controlled accepted spec bytes"
DETECTOR = b"controlled detector bytes"
RULE = b"controlled rule bytes"
AUTHORITY = b"controlled resolver evidence; not registry acceptance"
TOOL = hashlib.sha256(b"controlled tool artifact").hexdigest()
CODE = hashlib.sha256(b"controlled detector code artifact").hexdigest()
IMAGE = "sha256:" + hashlib.sha256(b"controlled detector image artifact").hexdigest()
RUNNER_CODE = hashlib.sha256(b"controlled runner code artifact").hexdigest()
RUNNER_IMAGE = "sha256:" + hashlib.sha256(b"controlled runner image artifact").hexdigest()
POLICY = hashlib.sha256(b"controlled policy document").hexdigest()
SOURCE = b"controlled source file\x00\xff"


def envelope(name: str, **fields: Any) -> CanonicalEnvelope:
    return encode_envelope(name, {"schema": "scanipy-execution/" + name + "/1", **fields})


def identity_policy(mode: str = "required") -> dict[str, Any]:
    return {
        "mode": mode,
        "policy_id": "controlled-policy-only",
        "policy_digest": POLICY,
        "reason": "controlled oracle policy" if mode == "not-applicable" else None,
    }


def binding(key: str = "controlled-binding") -> dict[str, Any]:
    return {
        "key": key,
        "detector_id": "controlled-detector",
        "engines": ["ifds", "semgrep"],
        "adapter_policy_digest": POLICY,
        "class_id": "injection",
        "language": "python",
        "rules": [
            {
                "rule_id": "controlled-rule",
                "semantic_digest": hashlib.sha256(b"controlled semantics").hexdigest(),
                "content_digest": hashlib.sha256(RULE).hexdigest(),
            }
        ],
        "detector_content_digest": hashlib.sha256(DETECTOR).hexdigest(),
        "tool_policy_digest": POLICY,
        "code_policy_digest": POLICY,
        "environment_policy_digest": POLICY,
        "expected_tool_digest": TOOL,
        "expected_code_digest": CODE,
        "expected_image_digest": IMAGE,
    }


def request_input(
    org: UUID,
    codebase: UUID,
    *,
    key: str | None = None,
    bindings: int = 1,
    lease: int = 300,
    max_attempts: int = 3,
    identity_mode: str = "required",
    predecessor: UUID | None = None,
    lineage: UUID | None = None,
) -> RequestInput:
    runner = {
        "code_policy_digest": POLICY,
        "environment_policy_digest": POLICY,
        "expected_code_digest": RUNNER_CODE,
        "expected_image_digest": RUNNER_IMAGE,
    }
    plan = envelope(
        "planned-policy",
        bindings=[binding(f"binding-{i}") for i in range(bindings)],
        capture_detection_runner=runner,
        identity_runner=runner,
        identity_policy=identity_policy(identity_mode),
    )
    request = envelope(
        "request",
        org_id=str(org),
        codebase_id=str(codebase),
        lineage_id=str(lineage or uuid4()),
        predecessor_request_id=None if predecessor is None else str(predecessor),
        idempotency_key=key or str(uuid4()),
        source_selector={"kind": "git-ref", "value": "controlled-ref"},
        requested_s_version="1.0.0",
        requested_policy_digest=plan.digest.hex(),
        identity_policy=identity_policy(identity_mode),
        retry_policy=envelope(
            "retry-policy",
            max_attempts=max_attempts,
            lease_seconds=lease,
            initial_backoff_seconds=0,
            max_backoff_seconds=0,
        ).value,
    )
    return RequestInput(request, plan)


def attempt_policy(*, lease: int = 300) -> CanonicalEnvelope:
    return envelope(
        "attempt-policy",
        assignment_id=str(uuid4()),
        code_policy_digest=POLICY,
        environment_policy_digest=POLICY,
        lease_seconds=lease,
    )


def capture_seal(request_id: UUID, requested: RequestInput) -> CaptureSeal:
    bindings = requested.planned_policy.value["bindings"]
    inventory = envelope(
        "source-inventory",
        files=[
            {
                "path": "fixture.py",
                "size": len(SOURCE),
                "sha256": hashlib.sha256(SOURCE).hexdigest(),
            }
        ],
    )
    content = envelope(
        "accepted-content",
        spec_sha256=hashlib.sha256(SPEC).hexdigest(),
        detector_sha256s=[hashlib.sha256(DETECTOR).hexdigest() for _ in bindings],
        rule_sha256s=[hashlib.sha256(RULE).hexdigest() for _ in bindings],
    )
    framed = (
        len(b"fixture.py").to_bytes(8, "big")
        + b"fixture.py"
        + len(SOURCE).to_bytes(8, "big")
        + SOURCE
    )
    object_id = uuid4()
    seal = envelope(
        "seal",
        request_id=str(request_id),
        resolved_commit="1" * 40,
        commit_algorithm="git-sha1",
        tree_algorithm="sha256-length-prefixed-path-and-content-v1",
        tree_digest=hashlib.sha256(framed).hexdigest(),
        inventory_digest=inventory.digest.hex(),
        storage_object_id=str(object_id),
        storage_reference="controlled-test-object:" + str(object_id),
        retain_seconds=0,
        s_version="1.0.0",
        planned_policy_digest=requested.planned_policy.digest.hex(),
        accepted_content_digest=content.digest.hex(),
        acceptance_evidence_digest=hashlib.sha256(AUTHORITY).hexdigest(),
        intended_files=["fixture.py"],
        bindings=bindings,
    )
    return CaptureSeal(
        seal,
        inventory,
        content,
        SPEC,
        tuple(DETECTOR for _ in bindings),
        tuple(RULE for _ in bindings),
        AUTHORITY,
    )


def invocation(index: int = 0, ordinal: int = 0) -> CanonicalEnvelope:
    return envelope(
        "run-input",
        binding_key=f"binding-{index}",
        run_ordinal=ordinal,
        argv=["controlled-tool", "fixture.py"],
        cwd="controlled-private-workdir",
        tool_policy_digest=POLICY,
        code_policy_digest=POLICY,
        environment_policy_digest=POLICY,
    )


def batch(
    run_id: UUID,
    *,
    count: int = 1,
    failed: bool = False,
    engine: str = "ifds",
    location: dict[str, Any] | None = None,
) -> DetectionBatch:
    observations = tuple(
        RawObservation(b"duplicate controlled raw\x00\xff", b"actual controlled witness")
        for _ in range(count)
    )
    location = location or {
        "status": "known",
        "path": "fixture.py",
        "start_line": 1,
        "start_column": None,
        "end_line": None,
        "end_column": None,
    }
    occurrences = [
        {
            "result_key": "controlled-result/1:duplicate",
            "duplicate_ordinal": i,
            "tool_ordinal": i,
            "engine": engine,
            "rule_id": "controlled-rule",
            "cwe": "CWE-89",
            "severity": "high",
            "message": "controlled detection",
            "location": location,
            "raw_sha256": hashlib.sha256(row.result).hexdigest(),
            "witness_sha256": hashlib.sha256(row.witness or b"").hexdigest(),
        }
        for i, row in enumerate(observations)
    ]
    inventory = envelope("occurrence-inventory", occurrences=occurrences)

    def actual(artifact):
        return {
            "policy_digest": POLICY,
            "artifact_digest": artifact,
            "evidence_digest": hashlib.sha256(b"controlled actual observation").hexdigest(),
        }

    value = envelope(
        "detection-batch",
        run_id=str(run_id),
        status="failed" if failed else "completed",
        tool_identity=actual(TOOL),
        code_identity=actual(CODE),
        actual_invocation={
            "argv": ["controlled-tool", "fixture.py"],
            "cwd": "controlled-private-workdir",
        },
        detector_env_digest=IMAGE,
        full_env_digest=None,
        coverage={
            "status": "partial" if failed else "complete",
            "files": ["fixture.py"],
            "rules": ["controlled-rule"],
            "errors": [{"code": "partial", "message": "controlled incomplete coverage"}]
            if failed
            else [],
        },
        stdout_sha256=hashlib.sha256(b"stdout\x00").hexdigest(),
        stderr_sha256=hashlib.sha256(b"stderr\xff").hexdigest(),
        occurrences=occurrences,
        inventory_digest=inventory.digest.hex(),
    )
    return DetectionBatch(value, b"stdout\x00", b"stderr\xff", observations)


def attempt_result(
    *,
    runs: tuple[UUID, ...] = (),
    failed: bool = False,
    retryable: bool = False,
    graph: str | None = None,
    sliced: str | None = None,
    not_applicable: bool = False,
) -> CanonicalEnvelope:
    identity = None
    if graph is not None or not_applicable:

        def artifact(value: str | None, namespace: str) -> dict[str, Any]:
            if not_applicable:
                return ArtifactIdentity("not-applicable").to_dict()
            if value in ("strong", "weak"):
                return ArtifactIdentity(
                    "completed", hashlib.sha256(namespace.encode()).hexdigest(), value, namespace
                ).to_dict()
            return ArtifactIdentity("failed").to_dict()

        identity = {
            "schema_version": 2,
            "cpg_order": artifact(graph, GRAPH_V2),
            "slice": artifact(sliced, SLICE_V2),
        }
    return envelope(
        "attempt-result",
        status="failed" if failed else "completed",
        retryable=retryable,
        error={"code": "controlled-failure", "message": "actual controlled failure"}
        if failed
        else None,
        actual_code_digest=RUNNER_CODE,
        actual_env_digest=RUNNER_IMAGE,
        completed_run_ids=[str(run) for run in runs],
        identity=identity,
        identity_policy_reason="controlled oracle policy" if not_applicable else None,
    )
