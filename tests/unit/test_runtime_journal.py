"""Diagnostic supplied-byte vectors, never installed journal/runtime evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import PosixPath
from typing import Any

import pytest

from tools.worker import runtime_journal as journal
from tools.worker.bounded_process import (
    FrozenInvocation,
    MemoryOutput,
    ProcessOutcome,
    SpoolOutput,
    StreamEvidence,
)
from tools.worker.process_evidence import (
    EvidenceBlob,
    RuntimeCallBinding,
    cli_operation_from_wire,
    prepare_call_intent,
    prepare_call_result,
)

pytestmark = pytest.mark.unit


def wire(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def root() -> dict[str, object]:
    return {
        "schema": "scanipy-runtime-evidence-root/1",
        "deployment_id": "00000000-0000-0000-0000-000000000001",
        "store_id": "00000000-0000-0000-0000-000000000002",
        "artifact_domain": "diagnostic",
        "owner_uid": 1000,
        "owner_gid": 1000,
        "evidence_root": "/diagnostic/evidence",
        "host_work_root": "/diagnostic/work",
        "format": "scanipy-runtime-journal/1",
    }


def test_root_is_only_structural_and_roundtrips() -> None:
    data = wire(root())
    parsed = journal.decode_journal_record("root", data)
    assert parsed.validation == "local-structure-only"
    assert parsed.data is data
    assert parsed.sha256 == hashlib.sha256(data).digest()
    assert journal.encode_journal_record("root", parsed.document) == data
    assert not hasattr(parsed, "visibility")
    assert not hasattr(parsed, "receipt")


@pytest.mark.parametrize("mutation", [True, 0, -1, 2**63, "1000", None])
def test_root_rejects_wrong_owner_scalar(mutation: object) -> None:
    document = root()
    document["owner_uid"] = mutation
    with pytest.raises(journal.JournalValidationError):
        journal.decode_journal_record("root", wire(document))


def test_decoder_does_not_accept_pretty_or_duplicate_json() -> None:
    data = wire(root())
    for malformed in (b" " + data, data[:-1] + b',"owner_uid":1000}'):
        with pytest.raises(journal.JournalValidationError):
            journal.decode_journal_record("root", malformed)


def uid(number: int) -> str:
    return f"00000000-0000-0000-0000-{number:012x}"


def raw_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def domain_hash(schema: str, data: bytes) -> str:
    return raw_hash(schema.encode() + b"\n" + data)


def untag(value: Any) -> Any:
    if type(value) is tuple:
        if value[0] == "object":
            return {key: untag(item) for key, item in value[1]}
        return [untag(item) for item in value[1]]
    return value


def file_observation(size: int) -> dict[str, int]:
    return {
        "device": 1,
        "inode": 2,
        "uid": 1000,
        "gid": 1000,
        "mode": 256,
        "nlink": 1,
        "size": size,
        "mtime_ns": 1,
        "ctime_ns": 1,
    }


class History:
    """Hand-authored diagnostic records; no native observations or keys."""

    def __init__(self, mode: str = "verifier-historical") -> None:
        self.mode = mode
        self.data: dict[str, bytes] = {}
        self.events: list[dict[str, Any]] = []
        self.prepared: dict[str, Any] = {}
        self.call_refs: dict[str, Any] = {}
        self.container: str | None = None
        self.image: str | None = None
        self.timestamp = "2026-09-25T10:00:00.000000Z"
        self.next_observation = 100
        self.prereq = self.prerequisite()
        self.m: dict[str, Any] = {
            "schema": "scanipy-runtime-attempt-manifest/1",
            "store_id": uid(1),
            "deployment_id": uid(2),
            "attempt_id": uid(3),
            "operation_id": uid(4),
            "mode": mode,
            "artifact_domain": "diagnostic",
            "created_at": "2026-09-25T10:00:00.000000Z",
            "origin_host_boot_id": uid(5),
            "origin_writer_id": uid(6),
            "request": self.add(b"opaque diagnostic request"),
            "input": self.add(b"opaque input"),
            "launch": self.add(b"opaque launch"),
            "initial_prerequisite": self.prereq["prerequisite"],
            "authority_inventory": self.prereq["authority_inventory"],
            "parent_barrier": self.add(b"opaque barrier")
            if mode in ("verifier-execution", "python-syntax")
            else None,
            "installation_id": uid(7),
            "installation_generation": 1,
            "inventory_digest": "8" * 64,
            "program_digest": "9" * 64,
            "expected_image_config_id": "sha256:" + "a" * 64,
            "expected_oci_manifest_digest": None,
            "container_name": "scanipy-runtime-" + uid(3).replace("-", ""),
            "metadata": [],
            "quota_plan": {
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
            },
        }
        for role, field in zip(
            ("installation", "controller-profile", "domain-profile", "inventory"),
            (
                "installation_sha256",
                "controller_profile_sha256",
                "domain_profile_sha256",
                "inventory_sha256",
            ),
            strict=True,
        ):
            content = ("opaque " + role).encode()
            ref = self.add(content)
            self.m[field] = ref["sha256"]
            self.m["metadata"].append(
                {
                    "role": role,
                    "path": "/diagnostic/" + role,
                    "blob": ref,
                    "observation": file_observation(len(content)),
                }
            )
        manifest = wire(self.m)
        self.event(
            "reserved",
            {
                "launch_sha256": self.m["launch"]["sha256"],
                "launch_bytes_ref": self.m["launch"],
                "input": self.m["input"],
                "manifest": self.reference(manifest),
            },
        )

    @staticmethod
    def reference(data: bytes) -> dict[str, Any]:
        digest = raw_hash(data)
        return {"sha256": digest, "size": len(data), "key": "blobs/" + digest}

    def add(self, data: bytes) -> dict[str, Any]:
        ref = self.reference(data)
        self.data[ref["sha256"]] = data
        return ref

    def prerequisite(self) -> dict[str, Any]:
        self.next_observation += 1
        modes = (
            "verifier-publication",
            "verifier-historical",
            "verifier-execution",
            "python-syntax",
        )
        roles = ["authentication", "scope"]
        if self.mode != "verifier-historical":
            roles.append("admission")
        if self.mode in modes[2:]:
            roles.extend(("execution-authorization", "capture-lease"))
        if self.mode == "python-syntax":
            roles.append("content-verification")
        objects = [
            {"role": role, "bytes": self.add(("opaque evidence " + role).encode())}
            for role in roles
        ]
        raw = {obj["role"]: obj["bytes"]["sha256"] for obj in objects}
        row = {
            "schema": "scanipy-local-launch-prerequisite/1",
            "reader_id": "diagnostic",
            "observation_id": uid(self.next_observation),
            "observed_at": "2026-09-25T10:00:00.000000Z",
            "valid_until": "2026-09-25T10:01:00.000000Z",
            "principal_id": "operator",
            "org_id": uid(8),
            "action": (
                "publish-builtin-preflight",
                "audit-historical",
                "verify-execution",
                "parse-python",
            )[modes.index(self.mode)],
            "authentication_evidence_sha256": raw["authentication"],
            "scope_evidence_sha256": raw["scope"],
            "admission": None if "admission" not in raw else {"opaque_owner_value": "not verified"},
            "execution_authorization_digest": "b" * 64
            if "execution-authorization" in raw
            else None,
            "capture_lease_evidence_sha256": raw.get("capture-lease"),
            "content_verification_evidence_sha256": raw.get("content-verification"),
        }
        ref = self.add(wire(row))
        inventory = self.add(
            wire(
                {
                    "schema": "scanipy-runtime-prerequisite-evidence/1",
                    "prerequisite": ref,
                    "objects": objects,
                }
            )
        )
        return {"prerequisite": ref, "authority_inventory": inventory}

    def event(self, kind: str, payload: dict[str, Any]) -> str:
        number = len(self.events) + 1
        row = {
            "schema": "scanipy-diagnostic-runtime-event/1",
            "attempt_id": self.m["attempt_id"],
            "sequence": number,
            "previous_event_digest": self.digest() if self.events else None,
            "event_id": uid(1000 + number),
            "kind": kind,
            "recorded_at": self.timestamp,
            "host_boot_id": self.m["origin_host_boot_id"],
            "elapsed_ms": number,
            "observed_image_config_id": self.image,
            "observed_oci_manifest_digest": None,
            "container_id": self.container,
            "payload": payload,
            "request_digest": domain_hash(
                "scanipy-local-runtime-request/1", self.data[self.m["request"]["sha256"]]
            ),
        }
        for key in (
            "operation_id",
            "mode",
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
        ):
            row[key] = self.m[key]
        self.events.append(row)
        return self.digest()

    def digest(self) -> str:
        row = self.events[-1]
        return domain_hash(row["schema"], wire(row))

    def intent(self, operation: str, *, argument: tuple[str, ...] = ()) -> str:
        index = len(self.prepared) + 1
        call_id = uid(2000 + index)
        target = (
            None
            if operation in ("daemon-version", "daemon-info")
            else self.m["expected_image_config_id"]
            if operation == "image-inspect"
            else self.m["container_name"]
            if operation in ("container-create", "container-inspect-name")
            else self.container
        )
        cwd = "/diagnostic/work/" + self.m["attempt_id"]
        env = {
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
        input_data = (
            self.data[self.m["input"]["sha256"]] if operation == "container-start-attached" else b""
        )
        invocation = FrozenInvocation(
            ("/diagnostic/docker", operation, *argument),
            tuple(sorted(env.items())),
            cwd,
            len(input_data),
            hashlib.sha256(input_data).digest(),
        )
        prepared = prepare_call_intent(
            RuntimeCallBinding(
                self.m["attempt_id"],
                self.m["operation_id"],
                call_id,
                index,
                cli_operation_from_wire(operation),
                target,
            ),
            invocation,
        )
        self.add(prepared.invocation_blob.data)
        digest = self.event("call-intent", json.loads(prepared.payload))
        self.prepared[call_id] = (prepared, digest)
        return call_id

    def result(
        self,
        call_id: str,
        *,
        absent: bool = False,
        output: bytes = b"",
        error: BaseException | None = None,
    ) -> dict[str, Any]:
        prepared, _ = self.prepared[call_id]
        memory = MemoryOutput(
            StreamEvidence(len(output), len(output), hashlib.sha256(output).digest(), True, False),
            output,
        )
        outcome = (
            None
            if absent
            else ProcessOutcome(
                prepared.invocation,
                "exited",
                99,
                99,
                0,
                prepared.invocation.stdin_bytes,
                memory,
                memory,
                1,
                "completed",
            )
        )
        failure = error or (ValueError("diagnostic no outcome") if absent else None)
        return self.observed_result(call_id, outcome, failure)

    def observed_result(
        self,
        call_id: str,
        outcome: ProcessOutcome | None,
        failure: BaseException | None = None,
        spool_readback: tuple[bytes | None, bytes | None] = (None, None),
    ) -> dict[str, Any]:
        prepared, digest = self.prepared[call_id]
        result = prepare_call_result(
            prepared,
            intent_event_digest=bytes.fromhex(digest),
            outcome=outcome,
            error_id=uid(3000 + len(self.call_refs)) if failure is not None else None,
            error=failure,
            spool_readback=spool_readback,
        )
        for blob in result.blobs:
            self.add(blob.data)
        self.event("call-result", json.loads(result.payload))
        ref = untag(result.call_ref)
        self.call_refs[call_id] = ref
        return ref

    def call(self, operation: str) -> dict[str, Any]:
        return self.result(self.intent(operation))

    def loaded(self) -> None:
        daemon = [self.call("daemon-version"), self.call("daemon-info")]
        image = self.call("image-inspect")
        self.image = self.m["expected_image_config_id"]
        self.event(
            "loaded",
            {
                "metadata": self.m["metadata"],
                "measurement_elapsed_ms": 1,
                "cli_file": file_observation(1),
                "socket": {
                    "path": "/run/docker.sock",
                    "device": 1,
                    "inode": 3,
                    "uid": 0,
                    "gid": 1000,
                    "mode": 432,
                },
                "daemon_calls": daemon,
                "image_inspect_call": image,
                "create_prerequisite": self.prereq,
            },
        )

    def created(self) -> None:
        self.loaded()
        create = self.call("container-create")
        self.container = "c" * 64
        inspected = self.call("container-inspect-id")
        self.event(
            "created", {"create_call": create, "inspect_call": inspected, "config_digest": "d" * 64}
        )

    def snapshot(self) -> tuple[bytes, tuple[bytes, ...], tuple[EvidenceBlob, ...]]:
        return (
            wire(self.m),
            tuple(wire(row) for row in self.events),
            tuple(
                EvidenceBlob(data, bytes.fromhex(digest))
                for digest, data in sorted(self.data.items())
            ),
        )

    def replay(self) -> journal.JournalStructureReport:
        manifest, events, blobs = self.snapshot()
        return journal.replay_journal(manifest, events, blobs=blobs)


@pytest.mark.parametrize(
    "mode", ("verifier-publication", "verifier-historical", "verifier-execution", "python-syntax")
)
def test_reserved_manifest_all_modes_remains_structural(mode: str) -> None:
    report = History(mode).replay()
    assert report.validation == "local-structure-only"
    assert report.declared_phase == "reserved"
    assert report.opaque_owner_values


def test_real_pe_call_result_and_shared_invocation_roles() -> None:
    history = History()
    history.call("daemon-version")
    report = history.replay()
    assert report.accounting.call_count == 1
    assert report.accounting.nonattached_missing_outcome_count == 0
    assert report.accounting.nonattached_missing_output_count == 0
    assert report.accounting.nonattached_unknown_retention_count == 0
    assert report.accounting.nonattached_observed_bytes == 0
    prepared = next(iter(history.prepared.values()))[0]
    result = untag(report.calls[0].result)
    expected = sum(len(wire(e)) for e in history.events) + len(wire(history.m))
    expected += 2 * len(prepared.invocation_blob.data)
    expected += len(history.data[history.call_refs[prepared.binding.call_id]["outcome"]["sha256"]])
    expected += sum(
        history.prereq[name]["size"] for name in ("prerequisite", "authority_inventory")
    )
    assert result["requested_invocation"] == result["outcome"]["invocation"]
    assert report.accounting.logical_metadata_bytes == expected


def test_loaded_repeated_refs_do_not_multiply_call_closure() -> None:
    history = History()
    history.loaded()
    report = history.replay()
    assert report.declared_phase == "loaded"
    assert report.accounting.call_count == 3


def test_created_chain_uses_actual_pe_codec() -> None:
    history = History()
    history.created()
    assert history.replay().declared_phase == "created"


def test_missing_result_and_missing_outcome_are_distinct() -> None:
    history = History()
    call_id = history.intent("daemon-version")
    pending = history.replay()
    assert pending.calls[0].result is None
    assert pending.accounting.nonattached_missing_outcome_count == 0
    history.result(call_id, absent=True)
    report = history.replay()
    assert report.calls[0].result is not None
    assert report.accounting.nonattached_missing_outcome_count == 1
    assert report.accounting.nonattached_missing_output_count == 0
    assert report.accounting.nonattached_unknown_retention_count == 0


def sample(history: History) -> dict[str, Any]:
    return {
        "observed_at": history.m["created_at"],
        "pid": 321,
        "start_ticks": 456,
        "host_boot_id": history.m["origin_host_boot_id"],
        "cgroup": {
            "path": "/diagnostic/cgroup",
            "device": 1,
            "inode": 4,
            "memory_max": 134217728,
            "swap_max": 0,
            "pids_max": 16,
            "cpu_quota_us": 100000,
            "cpu_period_us": 100000,
            "populated": True,
        },
        "namespaces": {
            key: index
            for index, key in enumerate(
                (
                    "pid_inode",
                    "net_inode",
                    "cgroup_inode",
                    "ipc_inode",
                    "mount_inode",
                    "user_inode",
                ),
                1,
            )
        },
        "network": {"interface_names": ["lo"], "nonloopback_routes": 0},
        "security": {
            "uid": 1000,
            "gid": 1000,
            "groups": [],
            "nnp": 1,
            "cap_inheritable": 0,
            "cap_permitted": 0,
            "cap_effective": 0,
            "cap_bounding": 0,
            "cap_ambient": 0,
            "seccomp_mode": 2,
            "apparmor_label": "docker-default",
        },
        "mounts": [
            {
                "target": "/dev",
                "source": "tmpfs",
                "fstype": "tmpfs",
                "readonly": False,
                "nosuid": True,
                "nodev": False,
                "noexec": True,
                "propagation": "private",
                "total_bytes": 67108864,
                "total_inodes": 32768,
            }
        ],
        "raw": [history.add(b"diagnostic kernel record")],
    }


def cleanup(history: History, *, complete: bool) -> str:
    final = history.call("container-inspect-id") if history.container is not None else None
    return history.event(
        "cleanup",
        {
            "state": "complete" if complete else "incomplete",
            "calls": [] if final is None else [final],
            "final_inspect_call": final,
            "cgroup_empty": True if complete else None,
            "client_reaped": complete,
            "parent_lease_action": "none",
            "invocation_slot": "held",
            "cleanup_id": uid(6000 + len(history.events)),
        },
    )


def domain_exited(
    history: History, *, acknowledged_at: str | None = None
) -> tuple[str, dict[str, Any]]:
    history.created()
    start = history.intent("container-start-attached")
    history.event(
        "started",
        {
            "start_call_id": start,
            "pid": 321,
            "start_ticks": 456,
            "control_path": "/diagnostic/control",
        },
    )
    inspected = history.call("container-inspect-id")
    observed = history.event(
        "observed",
        {
            "sample": sample(history),
            "inspect_call": inspected,
            "prerequisite": history.prereq,
            "observation_id": uid(5000),
        },
    )
    release = history.add(b"opaque release packet")
    intent = history.event(
        "release-intent",
        {"release": release, "prerequisite": history.prereq, "observed_event_digest": observed},
    )
    if acknowledged_at is not None:
        history.timestamp = acknowledged_at
    history.event(
        "released",
        {
            "release": release,
            "prerequisite": history.prereq,
            "published_at": history.timestamp,
            "release_intent_event_digest": intent,
        },
    )
    started = history.result(start)
    inspected = history.call("container-inspect-id")
    result = history.add(b"opaque domain result (not decoded or authenticated)")
    exited = history.event(
        "domain-exited",
        {
            "start_call": started,
            "container_inspect_call": inspected,
            "domain_result": result,
            "domain_validation": "valid",
        },
    )
    return exited, result


def admitted(history: History) -> None:
    exited, result = domain_exited(history)
    cleaned = cleanup(history, complete=True)
    history.event(
        "admitted",
        {
            "result_digest": result["sha256"],
            "prerequisite": history.prereq,
            "cleanup_event_digest": cleaned,
            "parent_lease_action": "none",
            "invocation_slot": "released",
            "domain_exited_event_digest": exited,
        },
    )


@pytest.mark.parametrize(
    "mode", ("verifier-publication", "verifier-historical", "verifier-execution", "python-syntax")
)
def test_complete_declared_history_never_grants_authority(mode: str) -> None:
    history = History(mode)
    admitted(history)
    report = history.replay()
    assert report.declared_phase == "admitted"
    assert report.validation == "local-structure-only"
    assert report.accounting.call_count == 9
    assert any(value.role == "domain-result" for value in report.opaque_owner_values)
    assert not hasattr(report, "visibility")
    assert not hasattr(report, "durable")


@pytest.mark.parametrize("kind", ("wrong-raw", "domain-hash", "wrong-event"))
def test_admitted_requires_its_exact_prior_result_raw_digest(kind: str) -> None:
    history = History()
    admitted(history)
    payload = history.events[-1]["payload"]
    if kind == "wrong-event":
        payload["domain_exited_event_digest"] = history.events[-1]["previous_event_digest"]
    elif kind == "wrong-raw":
        payload["result_digest"] = raw_hash(b"different result")
    else:
        data = history.data[payload["result_digest"]]
        payload["result_digest"] = domain_hash("owner-result/1", data)
    with pytest.raises(journal.JournalValidationError):
        history.replay()


@pytest.mark.parametrize(
    "left,right,missing,unknown,observed",
    [
        ("missing", "missing", 2, 0, 0),
        ("missing", "empty", 1, 0, 0),
        ("unknown", "missing", 1, 1, 7),
        ("unknown", "unknown", 0, 2, 14),
        ("empty", "empty", 0, 0, 0),
    ],
)
def test_output_absent_unknown_and_known_empty_census(
    left: str, right: str, missing: int, unknown: int, observed: int
) -> None:
    history = History()
    call_id = history.intent("daemon-info")
    empty = MemoryOutput(StreamEvidence(0, 0, hashlib.sha256(b"").digest(), True, False), b"")
    unknown_output = SpoolOutput(
        StreamEvidence(7, None, None, False, True), PosixPath("/diagnostic/unopened")
    )
    outputs = {"missing": None, "empty": empty, "unknown": unknown_output}
    outcome = ProcessOutcome(
        history.prepared[call_id][0].invocation,
        "io_error",
        99,
        99,
        1,
        0,
        outputs[left],
        outputs[right],
        1,
        "incomplete",
    )
    history.observed_result(call_id, outcome, ValueError("diagnostic partial output"))
    report = history.replay()
    assert report.accounting.nonattached_missing_outcome_count == 0
    assert report.accounting.nonattached_missing_output_count == missing
    assert report.accounting.nonattached_unknown_retention_count == unknown
    assert report.accounting.nonattached_observed_bytes == observed
    assert report.accounting.nonattached_known_retained_bytes == 0


def failure(history: History, kind: str = "failed") -> str:
    return history.event(
        kind,
        {
            "phase": "retain",
            "code": "evidence-failed",
            "calls": [],
            "kernel": None,
            "primary_error_id": None,
            "cleanup_event_digest": None,
        },
    )


def recovery(history: History) -> str:
    return history.event(
        "recovery-entered",
        {
            "recovery_id": uid(9000 + len(history.events)),
            "writer_id": uid(900),
            "reason": "writer-restart",
            "prior_head_digest": history.digest(),
        },
    )


def test_same_boot_restart_is_irreversible_even_after_cleanup() -> None:
    history = History()
    recovery(history)
    cleaned = cleanup(history, complete=True)
    failure(history)
    history.events[-1]["payload"]["cleanup_event_digest"] = cleaned
    report = history.replay()
    assert report.declared_phase == "failed"
    assert report.recovery_only_recorded


def test_orphan_cleanup_reconciles_without_erasing_history() -> None:
    history = History()
    orphan = failure(history, "orphaned")
    recovery(history)
    cleaned = cleanup(history, complete=True)
    history.event(
        "reconciled",
        {
            "orphan_event_digest": orphan,
            "cleanup_event_digest": cleaned,
            "disposition": "failed",
            "parent_lease_action": "none",
            "invocation_slot": "released",
        },
    )
    report = history.replay()
    assert report.declared_phase == "reconciled"
    assert report.ever_orphaned_recorded and report.recovery_only_recorded


@pytest.mark.parametrize("phase", ("failed", "admitted", "reconciled"))
def test_terminal_history_rejects_new_call(phase: str) -> None:
    history = History()
    if phase == "admitted":
        admitted(history)
    elif phase == "failed":
        failure(history)
    else:
        orphan = failure(history, "orphaned")
        recovery(history)
        cleaned = cleanup(history, complete=True)
        history.event(
            "reconciled",
            {
                "orphan_event_digest": orphan,
                "cleanup_event_digest": cleaned,
                "disposition": "failed",
                "parent_lease_action": "none",
                "invocation_slot": "released",
            },
        )
    history.intent("daemon-version")
    with pytest.raises(journal.JournalValidationError):
        history.replay()


def refusal(refs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "schema": "scanipy-local-runtime-refusal/1",
        "refusal_id": uid(88),
        "recorded_at": "2026-09-25T10:00:00.000000Z",
        "host_boot_id": uid(89),
        "elapsed_ms": 0,
        "operation_id": None,
        "requested_mode": None,
        "phase": "load",
        "code": "installation-unavailable",
        "anchor": None,
        "input": None,
        "available_evidence": refs or [],
        "primary_error_id": None,
    }


def registration(history: History, call_id: str) -> dict[str, Any]:
    return {
        "schema": "scanipy-runtime-spool-registration/1",
        "store_id": history.m["store_id"],
        "attempt_id": history.m["attempt_id"],
        "operation_id": history.m["operation_id"],
        "call_id": call_id,
        "intent_event_digest": history.prepared[call_id][1],
        "relative_directory": "call-spools/" + call_id,
        "directory": {"device": 1, "inode": 77, "uid": 1000, "gid": 1000, "mode": 448},
        "files": [
            {"stream": "stdout", "name": "stdout.bin"},
            {"stream": "stderr", "name": "stderr.bin"},
        ],
        "input_mode": "finite-one-shot",
        "limits": {
            "stdin_bytes": 0,
            "stdout_bytes": 262144,
            "stderr_bytes": 16384,
            "combined_output_bytes": 278528,
            "wall_ms": 2000,
            "cleanup_reserve_ms": 250,
        },
    }


def register(history: History, call_id: str, row: dict[str, Any] | None = None) -> str:
    return history.event(
        "spool-registered",
        {
            "intent_event_digest": history.prepared[call_id][1],
            "call_id": call_id,
            "registration": history.add(
                wire(registration(history, call_id) if row is None else row)
            ),
        },
    )


def collect(history: History, call_id: str, registered: str, stream: str, data: bytes) -> None:
    observation = file_observation(len(data)) | {"mode": 384}
    row = {
        "schema": "scanipy-runtime-spool-observation/1",
        "store_id": history.m["store_id"],
        "attempt_id": history.m["attempt_id"],
        "call_id": call_id,
        "stream": stream,
        "registration_event_digest": registered,
        "observed_at": history.m["created_at"],
        "before": observation,
        "after": dict(observation),
        "bytes": history.add(data),
    }
    history.event(
        "spool-collected",
        {
            "registration_event_digest": registered,
            "stream": stream,
            "observation": history.add(wire(row)),
        },
    )


def local_vectors() -> list[tuple[str, dict[str, Any]]]:
    history = History()
    call_id = history.intent("daemon-info")
    reg = registration(history, call_id)
    observation = file_observation(0) | {"mode": 384}
    return [
        ("root", root()),
        ("manifest", history.m),
        ("event", history.events[0]),
        ("refusal", refusal()),
        ("prerequisite", json.loads(history.data[history.prereq["prerequisite"]["sha256"]])),
        (
            "authority-inventory",
            json.loads(history.data[history.prereq["authority_inventory"]["sha256"]]),
        ),
        ("spool-registration", reg),
        (
            "spool-observation",
            {
                "schema": "scanipy-runtime-spool-observation/1",
                "store_id": uid(1),
                "attempt_id": uid(3),
                "call_id": call_id,
                "stream": "stdout",
                "registration_event_digest": "a" * 64,
                "observed_at": history.m["created_at"],
                "before": observation,
                "after": dict(observation),
                "bytes": History.reference(b""),
            },
        ),
        (
            "publication-intent",
            {
                "schema": "scanipy-runtime-publication-intent/1",
                "publication_id": uid(55),
                "store_id": uid(1),
                "scope_kind": "attempt",
                "scope_id": uid(3),
                "role": "blob",
                "destination": "blobs/" + raw_hash(b"x"),
                "size": 1,
                "sha256": raw_hash(b"x"),
                "expected_previous_event_digest": None,
            },
        ),
    ]


@pytest.mark.parametrize("kind,document", local_vectors())
def test_all_local_schemas_roundtrip(kind: str, document: dict[str, Any]) -> None:
    parsed = journal.decode_journal_record(kind, wire(document))
    assert journal.encode_journal_record(kind, parsed.document) == wire(document)


@pytest.mark.parametrize("kind,document", local_vectors())
@pytest.mark.parametrize("mutation", ("extra", "missing", "version", "duplicate", "pretty"))
def test_all_local_schemas_fail_closed(kind: str, document: dict[str, Any], mutation: str) -> None:
    changed = json.loads(wire(document))
    if mutation == "extra":
        changed["unknown"] = True
    elif mutation == "missing":
        changed.pop(next(key for key in changed if key != "schema"))
    elif mutation == "version":
        changed["schema"] += "0"
    data = wire(changed)
    if mutation == "duplicate":
        data = data[:-1] + b',"schema":' + wire(changed["schema"]) + b"}"
    elif mutation == "pretty":
        data = b" " + data
    with pytest.raises(journal.JournalValidationError):
        journal.decode_journal_record(kind, data)


@pytest.mark.parametrize(
    "data",
    [
        b"{}",
        b"[]",
        b"null",
        b'{"schema":NaN}',
        b'{"schema":Infinity}',
        b'{"schema":1.0}',
        b'{"schema":1e1}',
        b'{"schema":01}',
        b'{"schema":-0}',
        b'{"schema":9223372036854775808}',
        b'{"schema":-9223372036854775809}',
        b'{"schema":"\\u0000"}',
        b'{"schema":"\\ud800"}',
        b'{"schema":"\xff"}',
        b'{"schema":' + b"[" * 100 + b"0" + b"]" * 100 + b"}",
        b'{"schema":' + b"9" * 5000 + b"}",
    ],
)
def test_lexical_and_primitive_adversaries(data: bytes) -> None:
    with pytest.raises(journal.JournalValidationError):
        journal.decode_journal_record("root", data)


class Poison:
    def __iter__(self) -> Any:
        raise AssertionError("caller iterator invoked")

    def __str__(self) -> str:
        raise AssertionError("caller string invoked")

    def __len__(self) -> int:
        raise AssertionError("caller length invoked")

    def __bool__(self) -> bool:
        raise AssertionError("caller truth invoked")


class PoisonTuple(tuple):
    def __iter__(self) -> Any:
        raise AssertionError("tuple subclass iteration")


@pytest.mark.parametrize("value", [Poison(), [], {}, PoisonTuple(), bytearray(b"{}")])
def test_public_exact_type_fences_do_not_call_caller(value: object) -> None:
    with pytest.raises(journal.JournalValidationError):
        journal.decode_journal_record("root", value)
    with pytest.raises(journal.JournalValidationError):
        journal.encode_journal_record("root", value)
    with pytest.raises(journal.JournalValidationError):
        journal.replay_journal(b"{}", value, blobs=())


@pytest.mark.parametrize("field", ("data", "sha256"))
def test_poisoned_evidence_blob_rejected_before_conversion(field: str) -> None:
    blob = EvidenceBlob(b"x", hashlib.sha256(b"x").digest())
    object.__setattr__(blob, field, Poison())
    with pytest.raises(journal.JournalValidationError):
        journal.validate_refusal(wire(refusal()), blobs=(blob,))


def test_sorted_blob_input_is_mandatory_and_extra_missing_hash_fail() -> None:
    history = History()
    manifest, events, blobs = history.snapshot()
    for malformed in (tuple(reversed(blobs)), (*blobs, blobs[-1]), blobs[:-1]):
        with pytest.raises(journal.JournalValidationError):
            journal.replay_journal(manifest, events, blobs=malformed)
    changed = list(blobs)
    changed[0] = EvidenceBlob(changed[0].data + b"!", changed[0].sha256)
    with pytest.raises(journal.JournalValidationError):
        journal.replay_journal(manifest, events, blobs=tuple(changed))


@pytest.mark.parametrize("data", (b"", b"opaque", b'{"not":"a known packet"}', b"\xff\0"))
def test_refusal_retains_opaque_exact_bytes_not_guessed_json(data: bytes) -> None:
    ref = History.reference(data)
    report = journal.validate_refusal(
        wire(refusal([ref])), blobs=(EvidenceBlob(data, bytes.fromhex(ref["sha256"])),)
    )
    assert report.blobs[0].data == data
    assert report.opaque_owner_values[0].role == "refusal-raw"
    assert report.validation == "local-structure-only"
    assert not hasattr(report, "store_id")


def test_refusal_primary_graph_uses_actual_pe_decoder() -> None:
    history = History()
    history.result(history.intent("daemon-info"), absent=True)
    result = json.loads(history.data[next(iter(history.call_refs.values()))["outcome"]["sha256"]])
    graph_ref = result["error_graph"]
    data = history.data[graph_ref["sha256"]]
    row = refusal([graph_ref])
    row["primary_error_id"] = result["error_id"]
    report = journal.validate_refusal(
        wire(row), blobs=(EvidenceBlob(data, bytes.fromhex(graph_ref["sha256"])),)
    )
    assert not report.opaque_owner_values
    row["primary_error_id"] = uid(999999)
    with pytest.raises(journal.JournalValidationError):
        journal.validate_refusal(wire(row), blobs=report.blobs)


def test_spool_registration_collection_then_real_pe_result_no_files() -> None:
    history = History()
    call_id = history.intent("daemon-info")
    registered = register(history, call_id)
    data = b"spool bytes"
    for stream in ("stdout", "stderr"):
        collect(history, call_id, registered, stream, data)
    output = SpoolOutput(
        StreamEvidence(len(data), len(data), hashlib.sha256(data).digest(), True, False),
        PosixPath("/diagnostic/unopened"),
    )
    outcome = ProcessOutcome(
        history.prepared[call_id][0].invocation,
        "exited",
        99,
        99,
        0,
        0,
        output,
        output,
        1,
        "completed",
    )
    history.observed_result(call_id, outcome, spool_readback=(data, data))
    report = history.replay()
    assert report.accounting.nonattached_observed_bytes == 2 * len(data)
    assert report.accounting.nonattached_known_retained_bytes == 2 * len(data)


@pytest.mark.parametrize(
    "wall,cleanup_ms,valid",
    [
        (251, 250, True),
        (2000, 250, True),
        (250, 250, False),
        (2001, 250, False),
        (1000, 249, False),
        (1000, True, False),
    ],
)
def test_nonattached_planned_limits_are_bounds_not_enforcement(
    wall: int, cleanup_ms: int, valid: bool
) -> None:
    history = History()
    call_id = history.intent("daemon-info")
    row = registration(history, call_id)
    row["limits"].update(wall_ms=wall, cleanup_reserve_ms=cleanup_ms)
    register(history, call_id, row)
    if valid:
        assert history.replay().validation == "local-structure-only"
    else:
        with pytest.raises(journal.JournalValidationError):
            history.replay()


@pytest.mark.parametrize(
    "wall,cleanup_ms,valid",
    [
        (2, 1, True),
        (30000, 5000, True),
        (5001, 5000, True),
        (1, 1, False),
        (30001, 500, False),
        (5002, 5001, False),
        (30000, False, False),
    ],
)
def test_attached_plan_has_no_invented_exact_wall_or_cleanup(
    wall: int, cleanup_ms: int, valid: bool
) -> None:
    history = History()
    history.created()
    call_id = history.intent("container-start-attached")
    row = registration(history, call_id)
    row["limits"].update(
        stdin_bytes=2621440,
        stdout_bytes=16384,
        stderr_bytes=16384,
        combined_output_bytes=32768,
        wall_ms=wall,
        cleanup_reserve_ms=cleanup_ms,
    )
    register(history, call_id, row)
    if valid:
        assert history.replay().declared_phase == "start-intended"
    else:
        with pytest.raises(journal.JournalValidationError):
            history.replay()


@pytest.mark.parametrize(
    "kind,cap",
    [
        ("root", 4096),
        ("manifest", 16384),
        ("event", 65536),
        ("refusal", 16384),
        ("authority-inventory", 16384),
        ("prerequisite", 16384),
        ("spool-registration", 4096),
        ("spool-observation", 4096),
        ("publication-intent", 4096),
    ],
)
def test_record_byte_limit_precedes_json_allocation(
    monkeypatch: pytest.MonkeyPatch, kind: str, cap: int
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("generic JSON allocation was reached")

    monkeypatch.setattr(journal.json, "loads", forbidden)
    with pytest.raises(journal.JournalValidationError, match="limit"):
        journal.decode_journal_record(kind, b"x" * (cap + 1))


@pytest.mark.parametrize("variant", ("deep", "wide", "escaped"))
def test_encoder_budget_precedes_serialization(
    monkeypatch: pytest.MonkeyPatch, variant: str
) -> None:
    value: Any = "\n" * 4096
    if variant == "wide":
        value = ("array", (0,) * 10000)
    elif variant == "deep":
        value = 0
        for _ in range(100):
            value = ("array", (value,))
    document = ("object", (("bad", value),))

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("serialization was reached before bounded rejection")

    monkeypatch.setattr(journal.json, "dumps", forbidden)
    with pytest.raises(journal.JournalValidationError):
        journal.encode_journal_record("root", document)


def test_shared_branch_tuple_cannot_expand_exponentially() -> None:
    value: Any = 0
    for _ in range(25):
        value = ("array", (value, value))
    with pytest.raises(journal.JournalValidationError, match="limit"):
        journal.encode_journal_record("root", ("object", (("bad", value),)))


@pytest.mark.parametrize(
    "path", ("/", "/same/../work", "/same//work", "/same\\work", "/same\nwork", "/same\x85work")
)
def test_root_path_grammar_does_not_touch_files(path: str) -> None:
    row = root()
    row["evidence_root"] = path
    with pytest.raises(journal.JournalValidationError):
        journal.decode_journal_record("root", wire(row))


@pytest.mark.parametrize(
    "key", ("deployment_id", "store_id", "owner_uid", "owner_gid", "artifact_domain", "format")
)
def test_root_boolean_is_never_an_identifier_or_scalar(key: str) -> None:
    row = root()
    row[key] = False
    with pytest.raises(journal.JournalValidationError):
        journal.decode_journal_record("root", wire(row))


@pytest.mark.parametrize(
    "variant",
    ("event-id", "sequence", "previous", "scope", "schema", "extra", "timestamp", "elapsed"),
)
def test_complete_result_envelope_rejects_changed_history(variant: str) -> None:
    history = History()
    history.call("daemon-info")
    row = history.events[-1]
    if variant == "event-id":
        row["event_id"] = history.events[0]["event_id"]
    elif variant == "sequence":
        row["sequence"] += 1
    elif variant == "previous":
        row["previous_event_digest"] = "0" * 64
    elif variant == "scope":
        row["operation_id"] = uid(999999)
    elif variant == "schema":
        row["schema"] = "scanipy-local-runtime-event/1"
    elif variant == "extra":
        row["accepted"] = True
    elif variant == "timestamp":
        row["recorded_at"] = "2026-09-25T09:59:59.000000Z"
    else:
        row["elapsed_ms"] = 0
    with pytest.raises(journal.JournalValidationError):
        history.replay()


def test_pending_call_cannot_be_reinterpreted_as_disposed_failure() -> None:
    history = History()
    history.intent("daemon-info")
    failure(history)
    with pytest.raises(journal.JournalValidationError):
        history.replay()


def test_recovery_can_register_its_own_new_call_spool() -> None:
    history = History()
    history.loaded()
    history.intent("container-create")
    failure(history, "orphaned")
    recovery(history)
    call_id = history.intent("container-inspect-name")
    register(history, call_id)
    assert history.replay().recovery_only_recorded


def test_reported_overrun_is_retained_then_blocks_productive_call() -> None:
    history = History()
    history.result(history.intent("daemon-info"), output=b"x" * 16385)
    assert history.replay().accounting.nonattached_observed_bytes == 32770
    history.intent("daemon-version")
    with pytest.raises(journal.JournalValidationError):
        history.replay()


def test_execution_domain_digest_is_not_raw_sha_comparison() -> None:
    history = History("verifier-execution")
    prerequisite = json.loads(history.data[history.prereq["prerequisite"]["sha256"]])
    inventory = json.loads(history.data[history.prereq["authority_inventory"]["sha256"]])
    execution = next(x for x in inventory["objects"] if x["role"] == "execution-authorization")
    assert execution["bytes"]["sha256"] != prerequisite["execution_authorization_digest"]
    report = history.replay()
    assert any(x.role == "execution-authorization" for x in report.opaque_owner_values)
    assert any(
        x.role == "admission" and x.field_path == ("admission",) for x in report.opaque_owner_values
    )


def test_fresh_prerequisite_observation_is_counted_once_even_with_shared_role_bytes() -> None:
    history = History()
    history.loaded()
    before = history.replay().accounting.logical_metadata_bytes
    fresh = history.prerequisite()
    history.events[-1]["payload"]["create_prerequisite"] = fresh
    after = history.replay().accounting.logical_metadata_bytes
    assert after - before == sum(x["size"] for x in fresh.values())


@pytest.mark.parametrize("case", ("future", "expired", "last-microsecond"))
def test_fresh_loaded_authorization_uses_supplied_boundary_time(case: str) -> None:
    history = History()
    history.loaded()
    history.events[-1]["recorded_at"] = {
        "future": "2026-09-25T09:59:59.999999Z",
        "expired": "2026-09-25T10:01:00.000000Z",
        "last-microsecond": "2026-09-25T10:00:59.999999Z",
    }[case]
    if case == "last-microsecond":
        assert history.replay().declared_phase == "loaded"
    else:
        with pytest.raises(journal.JournalValidationError, match="order"):
            history.replay()


@pytest.mark.parametrize("field", ("observed_image_config_id", "observed_oci_manifest_digest"))
def test_latest_known_pin_cannot_be_erased_with_null(field: str) -> None:
    history = History()
    history.loaded()
    if field == "observed_oci_manifest_digest":
        history.events[-1][field] = "sha256:" + "f" * 64
    failure(history)
    history.events[-1][field] = None
    with pytest.raises(journal.JournalValidationError, match="reference"):
        history.replay()


@pytest.mark.parametrize("variant", ("events", "blobs", "bytes", "metadata"))
def test_outer_budget_rejects_before_payload_hash(
    monkeypatch: pytest.MonkeyPatch, variant: str
) -> None:
    history = History()
    manifest, events, blobs = history.snapshot()
    if variant == "events":
        events *= 129
    elif variant == "blobs":
        blobs = (blobs[0],) * 257
    elif variant == "metadata":
        events = (b"x" * 65536,) * 9
    else:
        blobs = (EvidenceBlob(b"x" * 33554432, bytes(32)),)

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("payload hashing ran before the outer bound")

    monkeypatch.setattr(journal.hashlib, "sha256", forbidden)
    with pytest.raises(journal.JournalValidationError, match="limit"):
        journal.replay_journal(manifest, events, blobs=blobs)


@pytest.mark.parametrize("over", (0, 1))
def test_refusal_total_includes_document_at_exact_32mib_boundary(over: int) -> None:
    payloads = [bytes([byte]) * 8388608 for byte in (1, 2, 3)]
    last_size = 8380000
    for _ in range(3):
        last = b"d" * last_size
        row = refusal([History.reference(value) for value in (*payloads, last)])
        last_size = 33554432 - len(wire(row)) - sum(len(value) for value in payloads) + over
    last = b"d" * last_size
    payloads.append(last)
    row = refusal([History.reference(value) for value in payloads])
    raw = wire(row)
    assert len(raw) + sum(map(len, payloads)) == 33554432 + over
    blobs = tuple(
        sorted(
            (EvidenceBlob(value, hashlib.sha256(value).digest()) for value in payloads),
            key=lambda blob: blob.sha256,
        )
    )
    if over:
        with pytest.raises(journal.JournalValidationError, match="limit"):
            journal.validate_refusal(raw, blobs=blobs)
    else:
        assert journal.validate_refusal(raw, blobs=blobs).validation == "local-structure-only"


def retime_prerequisite(
    history: History, reference: dict[str, Any], observed: str, until: str
) -> dict[str, Any]:
    prior = history.data.pop(reference["prerequisite"]["sha256"])
    inventory = json.loads(history.data.pop(reference["authority_inventory"]["sha256"]))
    row = json.loads(prior)
    row.update(observed_at=observed, valid_until=until)
    ref = history.add(wire(row))
    inventory["prerequisite"] = ref
    return {"prerequisite": ref, "authority_inventory": history.add(wire(inventory))}


def test_initial_future_prerequisite_fails_without_reading_clock() -> None:
    history = History()
    history.prereq = retime_prerequisite(
        history, history.prereq, "2026-09-25T10:00:00.000001Z", "2026-09-25T10:01:00.000001Z"
    )
    history.m.update(
        initial_prerequisite=history.prereq["prerequisite"],
        authority_inventory=history.prereq["authority_inventory"],
    )
    history.events[0]["payload"]["manifest"] = History.reference(wire(history.m))
    with pytest.raises(journal.JournalValidationError, match="order"):
        history.replay()


def test_genuinely_fresh_future_observation_is_not_hidden_by_valid_initial_one() -> None:
    history = History()
    history.loaded()
    fresh = retime_prerequisite(
        history,
        history.prerequisite(),
        "2026-09-25T10:00:00.000001Z",
        "2026-09-25T10:01:00.000001Z",
    )
    history.events[-1]["payload"]["create_prerequisite"] = fresh
    with pytest.raises(journal.JournalValidationError, match="order"):
        history.replay()


def test_delayed_release_acknowledgment_can_be_retained_then_fail_honestly() -> None:
    history = History()
    domain_exited(history, acknowledged_at="2026-09-25T10:01:01.000000Z")
    cleaned = cleanup(history, complete=True)
    failure(history)
    history.events[-1]["payload"]["cleanup_event_digest"] = cleaned
    report = history.replay()
    assert report.declared_phase == "failed"
    assert report.validation == "local-structure-only"


def test_delayed_acknowledgment_cannot_reauthorize_admission() -> None:
    history = History()
    exited, result = domain_exited(history, acknowledged_at="2026-09-25T10:01:01.000000Z")
    cleaned = cleanup(history, complete=True)
    history.event(
        "admitted",
        {
            "result_digest": result["sha256"],
            "prerequisite": history.prereq,
            "cleanup_event_digest": cleaned,
            "parent_lease_action": "none",
            "invocation_slot": "released",
            "domain_exited_event_digest": exited,
        },
    )
    with pytest.raises(journal.JournalValidationError, match="order"):
        history.replay()
    fresh = retime_prerequisite(
        history, history.prerequisite(), history.timestamp, "2026-09-25T10:02:00.000000Z"
    )
    history.events[-1]["payload"]["prerequisite"] = fresh
    assert history.replay().declared_phase == "admitted"


@pytest.mark.parametrize("recover", (False, True))
def test_first_late_collection_is_recovery_only_and_never_changes_original_outcome(
    recover: bool,
) -> None:
    history = History()
    call_id = history.intent("daemon-info")
    registered = register(history, call_id)
    unknown = SpoolOutput(
        StreamEvidence(7, None, None, False, True), PosixPath("/diagnostic/unopened")
    )
    outcome = ProcessOutcome(
        history.prepared[call_id][0].invocation,
        "io_error",
        99,
        99,
        1,
        0,
        unknown,
        None,
        1,
        "incomplete",
    )
    history.observed_result(call_id, outcome, ValueError("diagnostic unknown retention"))
    before = history.replay()
    result_data = history.data[history.call_refs[call_id]["outcome"]["sha256"]]
    if recover:
        recovery(history)
    collect(history, call_id, registered, "stdout", b"later diagnostic bytes")
    if not recover:
        with pytest.raises(journal.JournalValidationError, match="order"):
            history.replay()
        return
    after = history.replay()
    assert after.calls[0].result == before.calls[0].result
    assert history.data[history.call_refs[call_id]["outcome"]["sha256"]] == result_data
    for field in (
        "nonattached_observed_bytes",
        "nonattached_known_retained_bytes",
        "nonattached_unknown_retention_count",
        "nonattached_missing_output_count",
    ):
        assert getattr(after.accounting, field) == getattr(before.accounting, field)
    assert after.recovery_only_recorded
    assert after.accounting.logical_metadata_bytes > before.accounting.logical_metadata_bytes
    collect(history, call_id, registered, "stdout", b"changed second collection")
    with pytest.raises(journal.JournalValidationError, match="conflict"):
        history.replay()


def test_reused_large_invocation_is_charged_twice_per_result_not_once_per_blob() -> None:
    history = History()
    args = ("x" * 8000,) * 4
    for _ in range(7):
        history.result(history.intent("daemon-info", argument=args))
    before = history.replay()
    assert before.accounting.supplied_blob_bytes < 65536
    assert before.accounting.logical_metadata_bytes > 450000
    history.result(history.intent("daemon-info", argument=args))
    with pytest.raises(journal.JournalValidationError, match="limit"):
        history.replay()


def test_actual_invocation_mismatch_is_preserved_not_rewritten_or_admitted() -> None:
    history = History()
    call_id = history.intent("daemon-info")
    planned = history.prepared[call_id][0].invocation
    actual = FrozenInvocation(
        ("/unexpected/tool",), (), "/actual/elsewhere", 0, hashlib.sha256(b"").digest()
    )
    empty = MemoryOutput(StreamEvidence(0, 0, hashlib.sha256(b"").digest(), True, False), b"")
    outcome = ProcessOutcome(actual, "exited", 99, 99, 0, 0, empty, empty, 1, "completed")
    history.observed_result(call_id, outcome)
    report = history.replay()
    result = untag(report.calls[0].result)
    assert actual != planned
    assert result["requested_invocation"] != result["outcome"]["invocation"]
    history.intent("daemon-version")
    with pytest.raises(journal.JournalValidationError, match="order"):
        history.replay()


@pytest.mark.parametrize(
    "role,field",
    [
        ("authentication", "authentication_evidence_sha256"),
        ("scope", "scope_evidence_sha256"),
        ("capture-lease", "capture_lease_evidence_sha256"),
        ("content-verification", "content_verification_evidence_sha256"),
    ],
)
def test_four_raw_authority_links_reject_domain_hash_substitution(role: str, field: str) -> None:
    history = History("python-syntax")
    old = history.prereq
    row = json.loads(history.data.pop(old["prerequisite"]["sha256"]))
    inventory = json.loads(history.data.pop(old["authority_inventory"]["sha256"]))
    selected = next(item for item in inventory["objects"] if item["role"] == role)
    row[field] = domain_hash("not-raw/1", history.data[selected["bytes"]["sha256"]])
    ref = history.add(wire(row))
    inventory["prerequisite"] = ref
    history.m.update(initial_prerequisite=ref, authority_inventory=history.add(wire(inventory)))
    history.events[0]["payload"]["manifest"] = History.reference(wire(history.m))
    with pytest.raises(journal.JournalValidationError, match="reference"):
        history.replay()


@pytest.mark.parametrize("change", ("scope", "action", "identity"))
def test_fresh_authority_observation_cannot_change_bound_scope_or_reuse_changed_id(
    change: str,
) -> None:
    history = History()
    history.loaded()
    fresh = history.prerequisite()
    row = json.loads(history.data.pop(fresh["prerequisite"]["sha256"]))
    inventory = json.loads(history.data.pop(fresh["authority_inventory"]["sha256"]))
    if change == "scope":
        row["org_id"] = uid(909090)
    elif change == "action":
        row["action"] = "publish-builtin-preflight"
        row["admission"] = {}
    else:
        initial = json.loads(history.data[history.prereq["prerequisite"]["sha256"]])
        row["observation_id"] = initial["observation_id"]
        row["reader_id"] = "different-reader"
    ref = history.add(wire(row))
    inventory["prerequisite"] = ref
    history.events[-1]["payload"]["create_prerequisite"] = {
        "prerequisite": ref,
        "authority_inventory": history.add(wire(inventory)),
    }
    with pytest.raises(journal.JournalValidationError):
        history.replay()


@pytest.mark.parametrize(
    "role,destination,scope",
    [
        ("manifest", "manifest.json", "attempt"),
        ("event", "events/000001.json", "attempt"),
        ("spool-registration", "spool-registrations/" + uid(20) + ".json", "attempt"),
        ("refusal", "refusal.json", "refusal"),
        ("blob", "blobs/" + raw_hash(b"x"), "refusal"),
    ],
)
def test_publication_intent_fixed_names_are_only_data(
    role: str, destination: str, scope: str
) -> None:
    row = dict(local_vectors()[-1][1])
    row.update(role=role, destination=destination, scope_kind=scope)
    if scope == "attempt":
        row["expected_previous_event_digest"] = "a" * 64
    parsed = journal.decode_journal_record("publication-intent", wire(row))
    assert parsed.validation == "local-structure-only"
    row["destination"] = "../" + destination
    with pytest.raises(journal.JournalValidationError):
        journal.decode_journal_record("publication-intent", wire(row))


@pytest.mark.parametrize("state", ("incomplete", "not_started"))
def test_zero_returncode_never_overrides_cleanup_state(state: str) -> None:
    history = History()
    call_id = history.intent("daemon-info")
    empty = MemoryOutput(StreamEvidence(0, 0, hashlib.sha256(b"").digest(), True, False), b"")
    if state == "not_started":
        outcome = ProcessOutcome(
            history.prepared[call_id][0].invocation,
            "spawn_error",
            None,
            None,
            None,
            0,
            None,
            None,
            1,
            state,
        )
    else:
        outcome = ProcessOutcome(
            history.prepared[call_id][0].invocation, "exited", 99, 99, 0, 0, empty, empty, 1, state
        )
    history.observed_result(call_id, outcome, ValueError("diagnostic disposal"))
    assert history.replay().validation == "local-structure-only"
    failure(history)
    if state == "not_started":
        assert history.replay().declared_phase == "failed"
    else:
        with pytest.raises(journal.JournalValidationError, match="order"):
            history.replay()


def test_bound_error_primary_matches_actual_result_graph_only() -> None:
    history = History()
    reference = history.result(history.intent("daemon-info"), absent=True)
    result = json.loads(history.data[reference["outcome"]["sha256"]])
    failure(history, "orphaned")
    history.events[-1]["payload"].update(
        calls=[reference],
        primary_error_id=result["error_id"],
        kernel=history.add(b"opaque failure kernel"),
    )
    assert history.replay().declared_phase == "orphaned"
    history.events[-1]["payload"]["primary_error_id"] = uid(999999)
    with pytest.raises(journal.JournalValidationError, match="reference"):
        history.replay()


def test_exact_id_cleanup_kill_wait_remove_is_bounded_disposal_not_admission() -> None:
    history = History()
    history.created()
    cleanup(history, complete=False)
    history.call("container-kill")
    history.call("container-wait")
    cleaned = cleanup(history, complete=True)
    history.call("container-remove")
    failure(history)
    history.events[-1]["payload"]["cleanup_event_digest"] = cleaned
    report = history.replay()
    assert report.declared_phase == "failed"
    assert report.accounting.call_count == 10


@pytest.mark.parametrize("variant", ("remove-early", "second-complete", "wrong-id", "wrong-target"))
def test_cleanup_and_owned_id_constraints_reject_unsafe_histories(variant: str) -> None:
    history = History()
    history.created()
    cleanup(history, complete=variant == "second-complete")
    if variant == "remove-early":
        history.intent("container-remove")
    elif variant == "second-complete":
        cleanup(history, complete=True)
    elif variant == "wrong-id":
        history.container = "f" * 64
        history.intent("container-inspect-id")
    else:
        history.intent("container-kill")
        history.events[-1]["payload"]["target"] = "f" * 64
    with pytest.raises(journal.JournalValidationError):
        history.replay()


def test_ambiguous_create_without_id_cannot_claim_complete_cleanup() -> None:
    history = History()
    history.loaded()
    history.call("container-create")
    cleanup(history, complete=True)
    with pytest.raises(journal.JournalValidationError, match="order"):
        history.replay()


@pytest.mark.parametrize("valid", (False, True))
def test_changed_boot_requires_sticky_recovery_entry(valid: bool) -> None:
    history = History()
    if valid:
        recovery(history)
    else:
        history.intent("daemon-info")
    history.events[-1]["host_boot_id"] = uid(777)
    if valid:
        assert history.replay().recovery_only_recorded
    else:
        with pytest.raises(journal.JournalValidationError, match="order"):
            history.replay()


@pytest.mark.parametrize(
    "variant", ("same-result", "changed-result", "wrong-intent", "wrong-call", "missing-result")
)
def test_result_order_and_exact_references_are_not_repaired(variant: str) -> None:
    history = History()
    call_id = history.intent("daemon-info")
    reference = history.result(call_id)
    if variant in ("same-result", "changed-result"):
        history.event("call-result", dict(history.events[-1]["payload"]))
        if variant == "changed-result":
            history.events[-1]["payload"]["call"] = dict(
                reference, outcome=History.reference(b"changed")
            )
    elif variant == "wrong-intent":
        history.events[-1]["payload"]["intent_event_digest"] = "0" * 64
    elif variant == "wrong-call":
        history.events[-1]["payload"]["call"]["call_id"] = uid(999)
    else:
        history.data.pop(reference["outcome"]["sha256"])
    with pytest.raises(journal.JournalValidationError):
        history.replay()


@pytest.mark.parametrize(
    "variant",
    (
        "registration-scope",
        "registration-intent",
        "collection-owner",
        "collection-stable",
        "collection-registration",
    ),
)
def test_spool_closure_rejects_cross_scope_or_unstable_observations(variant: str) -> None:
    history = History()
    call_id = history.intent("daemon-info")
    row = registration(history, call_id)
    if variant == "registration-scope":
        row["store_id"] = uid(999)
    elif variant == "registration-intent":
        row["intent_event_digest"] = "0" * 64
    registered = register(history, call_id, row)
    if variant.startswith("collection"):
        collect(history, call_id, registered, "stdout", b"bytes")
        old_ref = history.events[-1]["payload"]["observation"]
        observed = json.loads(history.data.pop(old_ref["sha256"]))
        if variant == "collection-owner":
            observed["before"]["uid"] = observed["after"]["uid"] = 9
        elif variant == "collection-stable":
            observed["after"]["inode"] += 1
        else:
            observed["registration_event_digest"] = "0" * 64
        history.events[-1]["payload"]["observation"] = history.add(wire(observed))
    with pytest.raises(journal.JournalValidationError):
        history.replay()


@pytest.mark.parametrize("field", ("nnp", "seccomp_mode", "cap_effective", "groups"))
def test_owned_kernel_shape_rejects_wrong_scalar_type(field: str) -> None:
    history = History()
    domain_exited(history)
    row = next(row for row in history.events if row["kind"] == "observed")
    row["payload"]["sample"]["security"][field] = True
    with pytest.raises(journal.JournalValidationError):
        journal.decode_journal_record("event", wire(row))


def test_kernel_shape_can_preserve_observed_policy_mismatch_without_certifying_it() -> None:
    history = History()
    domain_exited(history)
    row = next(row for row in history.events if row["kind"] == "observed")
    sample_row = row["payload"]["sample"]
    sample_row["cgroup"].update(
        memory_max="max", swap_max="max", cpu_quota_us="max", pids_max="max"
    )
    sample_row["security"].update(groups=[1, 2], nnp=0, seccomp_mode=0, cap_effective=1)
    sample_row["mounts"][0].update(total_bytes=None, total_inodes=None)
    parsed = journal.decode_journal_record("event", wire(row))
    assert parsed.validation == "local-structure-only"


def test_refusal_optional_observed_fields_do_not_invent_runtime_scope() -> None:
    row = refusal()
    row.update(
        operation_id=uid(7),
        requested_mode="python-syntax",
        input={"size": 1, "sha256": raw_hash(b"x")},
        anchor={
            "deployment_id": uid(1),
            "installation_id": uid(2),
            "generation": 1,
            "installation_sha256": "a" * 64,
        },
    )
    assert journal.validate_refusal(wire(row), blobs=()).validation == "local-structure-only"


@pytest.mark.parametrize(
    "data", (b"[[[]]]", b'{"x":' + b"9" * 21 + b"}", b"{" + b'"a":0,' * 16 + b'"z":0}')
)
def test_depth_integer_and_key_count_guards_precede_generic_json(
    monkeypatch: pytest.MonkeyPatch, data: bytes
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("unbounded JSON allocation was reached")

    monkeypatch.setattr(journal.json, "loads", forbidden)
    with pytest.raises(journal.JournalValidationError, match="limit"):
        journal.decode_journal_record("root", data)


def test_actual_image_mismatch_is_retained_for_failure_but_not_productive_continuation() -> None:
    history = History()
    history.loaded()
    history.image = "sha256:" + "f" * 64
    failure(history)
    report = history.replay()
    assert untag(report.events[-1].document)["observed_image_config_id"] == history.image
    assert report.validation == "local-structure-only"
    history.events.pop()
    history.intent("container-create")
    with pytest.raises(journal.JournalValidationError, match="reference"):
        history.replay()


def begin_cleanup(history: History) -> None:
    history.event(
        "cleanup",
        {
            "state": "incomplete",
            "calls": [],
            "final_inspect_call": None,
            "cgroup_empty": None,
            "client_reaped": False,
            "parent_lease_action": "none",
            "invocation_slot": "held",
            "cleanup_id": uid(6000 + len(history.events)),
        },
    )


@pytest.mark.parametrize("ordinary", (5, 12))
def test_cleanup_can_use_unused_ordinary_slots_as_well_as_four_reserved(ordinary: int) -> None:
    history = History()
    history.created()
    for _ in range(ordinary - 5):
        history.call("container-inspect-id")
    begin_cleanup(history)
    for _ in range(16 - ordinary):
        history.call("container-inspect-id")
    report = history.replay()
    assert report.accounting.call_count == 16
    assert report.declared_phase == "cleanup"
    assert report.validation == "local-structure-only"


def test_thirteenth_ordinary_call_cannot_spend_cleanup_reserve() -> None:
    history = History()
    for _ in range(12):
        history.call("daemon-info")
    assert history.replay().accounting.call_count == 12
    history.intent("daemon-info")
    with pytest.raises(journal.JournalValidationError, match="limit"):
        history.replay()


@pytest.mark.parametrize("same_boot_recovery", (False, True))
def test_seventeenth_total_call_rejects_without_recovery_replenishment(
    same_boot_recovery: bool,
) -> None:
    history = History()
    history.created()
    for _ in range(7):
        history.call("container-inspect-id")
    if same_boot_recovery:
        recovery(history)
    else:
        begin_cleanup(history)
    for _ in range(4):
        history.call("container-inspect-id")
    report = history.replay()
    assert report.accounting.call_count == 16
    assert report.recovery_only_recorded is same_boot_recovery
    # Public PE already rejects ordinal17; retain a malformed supplied wire
    # vector to exercise the journal's public delegation, not a fake producer.
    last = next(row for row in reversed(history.events) if row["kind"] == "call-intent")
    payload = dict(last["payload"], call_id=uid(99999), call_sequence=17)
    history.event("call-intent", payload)
    with pytest.raises(journal.JournalValidationError):
        history.replay()


def observed_history(
    *, sample_time: str, target: str = "/dev", spool: bool = False
) -> tuple[History, str]:
    history = History()
    history.created()
    start = history.intent("container-start-attached")
    if spool:
        row = registration(history, start)
        row["limits"].update(
            stdin_bytes=2621440,
            stdout_bytes=16384,
            stderr_bytes=16384,
            combined_output_bytes=32768,
        )
        register(history, start, row)
    history.timestamp = "2026-09-25T10:00:01.000000Z"
    history.event(
        "started",
        {
            "start_call_id": start,
            "pid": 321,
            "start_ticks": 456,
            "control_path": "/diagnostic/control",
        },
    )
    inspected = history.call("container-inspect-id")
    kernel = sample(history)
    kernel["observed_at"] = sample_time
    kernel["mounts"][0]["target"] = target
    history.timestamp = "2026-09-25T10:00:30.000000Z"
    event_digest = history.event(
        "observed",
        {
            "sample": kernel,
            "inspect_call": inspected,
            "prerequisite": history.prereq,
            "observation_id": uid(5000),
        },
    )
    return history, event_digest


@pytest.mark.parametrize(
    "target,valid",
    [
        ("/", True),
        ("/dev", True),
        ("//", False),
        ("/dev/..", False),
        ("/dev/", False),
        ("/de\\v", False),
        ("/de\nv", False),
        ("/de\x85v", False),
    ],
)
def test_only_observed_mount_target_grammar_accepts_exact_root(target: str, valid: bool) -> None:
    history, _ = observed_history(sample_time="2026-09-25T10:00:15.000000Z", target=target)
    if valid:
        report = history.replay()
        assert report.validation == "local-structure-only"
        assert (
            untag(report.events[-1].document)["payload"]["sample"]["mounts"][0]["target"] == target
        )
    else:
        with pytest.raises(journal.JournalValidationError):
            history.replay()


@pytest.mark.parametrize("kind", ("control", "metadata"))
def test_observed_mount_root_exception_does_not_relax_control_or_metadata_paths(kind: str) -> None:
    history, _ = observed_history(sample_time="2026-09-25T10:00:15.000000Z", target="/")
    if kind == "control":
        row = next(row for row in history.events if row["kind"] == "started")
        row["payload"]["control_path"] = "/"
        record_kind = "event"
    else:
        row = history.m
        row["metadata"][0]["path"] = "/"
        record_kind = "manifest"
    with pytest.raises(journal.JournalValidationError):
        journal.decode_journal_record(record_kind, wire(row))


@pytest.mark.parametrize(
    "sample_time,valid",
    [
        ("2026-09-25T10:00:00.999999Z", False),
        ("2026-09-25T10:00:01.000000Z", True),
        ("2026-09-25T10:00:15.000000Z", True),
        ("2026-09-25T10:00:30.000000Z", True),
        ("2026-09-25T10:00:30.000001Z", False),
    ],
)
def test_kernel_sample_time_is_between_declared_start_and_observation(
    sample_time: str, valid: bool
) -> None:
    history, _ = observed_history(sample_time=sample_time)
    if valid:
        assert history.replay().declared_phase == "observed"
    else:
        with pytest.raises(journal.JournalValidationError, match="order"):
            history.replay()


@pytest.mark.parametrize(
    "published_at,valid",
    [
        ("2026-09-25T10:00:29.999999Z", False),
        ("2026-09-25T10:00:30.000000Z", True),
        ("2026-09-25T10:00:59.999999Z", True),
        ("2026-09-25T10:01:05.000000Z", True),
        ("2026-09-25T10:01:05.000001Z", False),
    ],
)
def test_release_publication_time_uses_inclusive_intent_and_ack_bounds(
    published_at: str, valid: bool
) -> None:
    history, observed = observed_history(sample_time="2026-09-25T10:00:15.000000Z")
    release = history.add(b"opaque release packet")
    intent = history.event(
        "release-intent",
        {
            "release": release,
            "prerequisite": history.prereq,
            "observed_event_digest": observed,
        },
    )
    history.timestamp = "2026-09-25T10:01:05.000000Z"
    history.event(
        "released",
        {
            "release": release,
            "prerequisite": history.prereq,
            "published_at": published_at,
            "release_intent_event_digest": intent,
        },
    )
    if valid:
        report = history.replay()
        assert report.declared_phase == "released"
        assert report.validation == "local-structure-only"
    else:
        with pytest.raises(journal.JournalValidationError, match="order"):
            history.replay()


def registered_profile_call(profile: str) -> tuple[History, str, str, int, int, str]:
    history = History("python-syntax" if profile == "python" else "verifier-historical")
    if profile == "daemon":
        call_id = history.intent("daemon-info")
        stdout_cap, stderr_cap, next_operation = 262144, 16384, "daemon-version"
    else:
        history.created()
        call_id = history.intent("container-start-attached")
        stdout_cap, stderr_cap, next_operation = (
            (8388608, 65536, "container-inspect-id")
            if profile == "python"
            else (16384, 16384, "container-inspect-id")
        )
    row = registration(history, call_id)
    if profile != "daemon":
        row["limits"].update(
            stdin_bytes=263244 if profile == "python" else 2621440,
            stdout_bytes=stdout_cap,
            stderr_bytes=stderr_cap,
            combined_output_bytes=stdout_cap + stderr_cap,
            wall_ms=3000,
            cleanup_reserve_ms=500,
        )
    registered = register(history, call_id, row)
    return history, call_id, registered, stdout_cap, stderr_cap, next_operation


@pytest.mark.parametrize("profile", ("daemon", "verifier", "python"))
@pytest.mark.parametrize("stream", ("stdout", "stderr"))
@pytest.mark.parametrize("over", (False, True))
def test_collected_stream_cap_blocks_productive_work_without_inventing_transport_counts(
    profile: str, stream: str, over: bool
) -> None:
    history, call_id, registered, stdout_cap, stderr_cap, next_operation = registered_profile_call(
        profile
    )
    cap = stdout_cap if stream == "stdout" else stderr_cap
    content = b"x" * (cap + int(over))
    collect(history, call_id, registered, stream, content)
    report = history.replay()
    assert any(blob.data == content for blob in report.blobs)
    assert report.calls[-1].result is None
    assert report.accounting.nonattached_observed_bytes == 0
    assert report.accounting.nonattached_known_retained_bytes == 0
    assert report.accounting.nonattached_missing_outcome_count == 0
    history.intent(next_operation)
    if over:
        with pytest.raises(journal.JournalValidationError, match="order"):
            history.replay()
    else:
        assert history.replay().validation == "local-structure-only"


@pytest.mark.parametrize("profile", ("daemon", "verifier", "python"))
@pytest.mark.parametrize("over", (False, True))
def test_registered_combined_collection_cap_preserves_both_streams_and_zero_result(
    profile: str, over: bool
) -> None:
    history, call_id, registered, stdout_cap, stderr_cap, next_operation = registered_profile_call(
        profile
    )
    stdout, stderr = b"x" * stdout_cap, b"x" * (stderr_cap + int(over))
    collect(history, call_id, registered, "stdout", stdout)
    collect(history, call_id, registered, "stderr", stderr)
    # A real PE record with zero memory bytes does not erase retained spool
    # observations or establish that the planned spool argument was forwarded.
    history.result(call_id)
    report = history.replay()
    assert report.accounting.nonattached_observed_bytes == 0
    assert report.accounting.nonattached_known_retained_bytes == 0
    assert any(blob.data == stdout for blob in report.blobs)
    assert any(blob.data == stderr for blob in report.blobs)
    history.intent(next_operation)
    if over:
        with pytest.raises(journal.JournalValidationError, match="order"):
            history.replay()
    else:
        assert history.replay().validation == "local-structure-only"


def test_collected_overrun_retains_honest_failed_history_with_original_zero_memory_result() -> None:
    history, call_id, registered, stdout_cap, _stderr_cap, _next = registered_profile_call("daemon")
    content = b"x" * (stdout_cap + 1)
    collect(history, call_id, registered, "stdout", content)
    history.result(call_id)
    failure(history)
    report = history.replay()
    assert report.declared_phase == "failed"
    assert report.accounting.nonattached_observed_bytes == 0
    assert any(blob.data == content for blob in report.blobs)


def test_collected_overrun_survives_orphan_recovery_and_actual_late_result() -> None:
    history, call_id, registered, stdout_cap, _stderr_cap, _next = registered_profile_call("daemon")
    collect(history, call_id, registered, "stdout", b"x" * (stdout_cap + 1))
    orphan = failure(history, "orphaned")
    recovery(history)
    history.result(call_id)
    cleaned = cleanup(history, complete=True)
    history.event(
        "reconciled",
        {
            "orphan_event_digest": orphan,
            "cleanup_event_digest": cleaned,
            "disposition": "failed",
            "parent_lease_action": "none",
            "invocation_slot": "released",
        },
    )
    report = history.replay()
    assert report.declared_phase == "reconciled"
    assert report.recovery_only_recorded and report.ever_orphaned_recorded
    assert report.accounting.nonattached_observed_bytes == 0


def test_oversized_late_recovery_collection_does_not_upgrade_unknown_transport_retention() -> None:
    history, call_id, registered, stdout_cap, _stderr_cap, _next = registered_profile_call("daemon")
    unknown = SpoolOutput(
        StreamEvidence(1, None, None, False, True), PosixPath("/diagnostic/unopened")
    )
    outcome = ProcessOutcome(
        history.prepared[call_id][0].invocation,
        "io_error",
        99,
        99,
        1,
        0,
        unknown,
        None,
        1,
        "incomplete",
    )
    history.observed_result(call_id, outcome, ValueError("diagnostic unknown retention"))
    before = history.replay()
    failure(history, "orphaned")
    recovery(history)
    collect(history, call_id, registered, "stdout", b"x" * (stdout_cap + 1))
    after = history.replay()
    assert after.calls == before.calls
    assert (
        after.accounting.nonattached_observed_bytes
        == before.accounting.nonattached_observed_bytes
        == 1
    )
    assert (
        after.accounting.nonattached_unknown_retention_count
        == before.accounting.nonattached_unknown_retention_count
        == 1
    )
    assert after.accounting.nonattached_known_retained_bytes == 0
    assert after.recovery_only_recorded


def pending_historical_ack(kind: str) -> tuple[History, str, dict[str, Any]]:
    history, observed = observed_history(
        sample_time="2026-09-25T10:00:15.000000Z", spool=kind == "spool-overrun"
    )
    release = history.add(b"opaque release packet")
    intent = history.event(
        "release-intent",
        {
            "release": release,
            "prerequisite": history.prereq,
            "observed_event_digest": observed,
        },
    )
    start = next(
        event["payload"]["start_call_id"] for event in history.events if event["kind"] == "started"
    )
    history.timestamp = "2026-09-25T10:00:31.000000Z"
    if kind == "spool-overrun":
        registered = next(event for event in history.events if event["kind"] == "spool-registered")
        registered_digest = domain_hash(registered["schema"], wire(registered))
        collect(history, start, registered_digest, "stdout", b"x" * 16385)
    history.result(
        start,
        output=b"x" * 16385 if kind == "overrun" else b"",
        error=ValueError("diagnostic attached failure") if kind == "failure" else None,
    )
    history.timestamp = "2026-09-25T10:00:32.000000Z"
    return (
        history,
        start,
        {
            "release": release,
            "prerequisite": history.prereq,
            "published_at": "2026-09-25T10:00:31.500000Z",
            "release_intent_event_digest": intent,
        },
    )


@pytest.mark.parametrize("kind", ("healthy", "failure", "overrun", "spool-overrun"))
@pytest.mark.parametrize("terminal", ("failed", "orphaned"))
def test_historical_ack_preserves_prior_error_or_overrun_then_honest_termination(
    kind: str, terminal: str
) -> None:
    history, start, acknowledgment = pending_historical_ack(kind)
    before = history.replay()
    original = history.data[history.call_refs[start]["outcome"]["sha256"]]
    history.event("released", acknowledgment)
    acknowledged = history.replay()
    assert acknowledged.declared_phase == "released"
    assert acknowledged.calls == before.calls
    assert history.data[history.call_refs[start]["outcome"]["sha256"]] == original
    if terminal == "failed":
        begin_cleanup(history)
        cleaned = cleanup(history, complete=True)
        failure(history)
        history.events[-1]["payload"]["cleanup_event_digest"] = cleaned
    else:
        failure(history, "orphaned")
    report = history.replay()
    assert report.declared_phase == terminal
    assert report.validation == "local-structure-only"


@pytest.mark.parametrize("kind", ("failure", "overrun", "spool-overrun"))
@pytest.mark.parametrize("next_action", ("intent", "admitted"))
def test_historical_ack_never_clears_failure_or_overrun_for_productive_work(
    kind: str, next_action: str
) -> None:
    history, start, acknowledgment = pending_historical_ack(kind)
    history.event("released", acknowledgment)
    assert history.replay().declared_phase == "released"
    if next_action == "intent":
        history.intent("container-inspect-id")
    else:
        inspected = next(
            event["payload"]["inspect_call"]
            for event in history.events
            if event["kind"] == "observed"
        )
        result = history.add(b"opaque supplied domain result")
        exited = history.event(
            "domain-exited",
            {
                "start_call": history.call_refs[start],
                "container_inspect_call": inspected,
                "domain_result": result,
                "domain_validation": "valid",
            },
        )
        begin_cleanup(history)
        cleaned = cleanup(history, complete=True)
        # This prefix is retained diagnostic history, not renewed authority.
        assert history.replay().declared_phase == "cleanup"
        history.event(
            "admitted",
            {
                "result_digest": result["sha256"],
                "prerequisite": history.prereq,
                "cleanup_event_digest": cleaned,
                "parent_lease_action": "none",
                "invocation_slot": "released",
                "domain_exited_event_digest": exited,
            },
        )
    with pytest.raises(journal.JournalValidationError, match="order"):
        history.replay()


@pytest.mark.parametrize(
    "change",
    (
        "recovery",
        "orphan",
        "cleanup",
        "terminal",
        "release-ref",
        "release-bytes",
        "prerequisite",
        "published-before",
        "published-after",
        "image",
        "erase-image",
    ),
)
def test_historical_ack_does_not_relax_other_existing_fences(change: str) -> None:
    history, _start, acknowledgment = pending_historical_ack("healthy")
    if change == "recovery":
        recovery(history)
    elif change == "orphan":
        failure(history, "orphaned")
    elif change in ("cleanup", "terminal"):
        begin_cleanup(history)
        if change == "terminal":
            cleaned = cleanup(history, complete=True)
            failure(history)
            history.events[-1]["payload"]["cleanup_event_digest"] = cleaned
    elif change == "release-ref":
        acknowledgment["release_intent_event_digest"] = "0" * 64
    elif change == "release-bytes":
        acknowledgment["release"] = history.add(b"different opaque release")
    elif change == "prerequisite":
        acknowledgment["prerequisite"] = history.prerequisite()
    elif change == "published-before":
        acknowledgment["published_at"] = "2026-09-25T10:00:29.999999Z"
    elif change == "published-after":
        acknowledgment["published_at"] = "2026-09-25T10:00:32.000001Z"
    elif change == "image":
        history.image = "sha256:" + "e" * 64
    else:
        history.image = None
    history.event("released", acknowledgment)
    with pytest.raises(journal.JournalValidationError):
        history.replay()


@pytest.mark.parametrize("profile", ("verifier", "python"))
@pytest.mark.parametrize("when", ("before", "after", "memory"))
def test_attached_spool_registration_precedes_declared_started_only(
    profile: str, when: str
) -> None:
    history = History("python-syntax" if profile == "python" else "verifier-historical")
    history.created()
    call_id = history.intent("container-start-attached")
    row = registration(history, call_id)
    row["limits"].update(
        stdin_bytes=263244 if profile == "python" else 2621440,
        stdout_bytes=8388608 if profile == "python" else 16384,
        stderr_bytes=65536 if profile == "python" else 16384,
        combined_output_bytes=8454144 if profile == "python" else 32768,
    )
    if when == "before":
        register(history, call_id, row)
    history.event(
        "started",
        {
            "start_call_id": call_id,
            "pid": 321,
            "start_ticks": 456,
            "control_path": "/diagnostic/control",
        },
    )
    if when == "after":
        register(history, call_id, row)
        with pytest.raises(journal.JournalValidationError, match="order"):
            history.replay()
    else:
        report = history.replay()
        assert report.declared_phase == "started"
        assert report.validation == "local-structure-only"


@pytest.mark.parametrize("old_attached", (False, True))
def test_recovery_registration_is_valid_for_new_cleanup_call_not_old_started_call(
    old_attached: bool,
) -> None:
    history, _observed = observed_history(sample_time="2026-09-25T10:00:15.000000Z")
    old_id = next(
        event["payload"]["start_call_id"] for event in history.events if event["kind"] == "started"
    )
    failure(history, "orphaned")
    recovery(history)
    call_id = old_id if old_attached else history.intent("container-inspect-id")
    row = registration(history, call_id)
    if old_attached:
        row["limits"].update(
            stdin_bytes=2621440,
            stdout_bytes=16384,
            stderr_bytes=16384,
            combined_output_bytes=32768,
        )
    register(history, call_id, row)
    if old_attached:
        with pytest.raises(journal.JournalValidationError, match="order"):
            history.replay()
    else:
        report = history.replay()
        assert report.recovery_only_recorded and report.ever_orphaned_recorded
        assert report.validation == "local-structure-only"
