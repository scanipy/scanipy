"""CMP-SNAP-05 ``run_execute_loop`` — bootstrap (no-parent) execute-loop specs.

Track 1B (first-real-scan plan): hermetic tests for
``services.snapshot.worker.run_execute_loop``'s bootstrap sequence — SQS
dequeue -> real ``git`` clone (via the REAL argv-allowlisted ``secure_run``,
with only the underlying ``subprocess.run`` spawn faked, exactly like
``tests/unit/test_snap_specs.py::test_snap_05a_argv_allowlist_rejects_non_sanctioned_flag``'s
positive control) -> real ``CMP-SNAP-03`` ``cw_detect.detect`` -> an injected
fake ``parse_source`` (CLAR-SNAP-03 / track 1A has not landed; the injected
fake satisfies the exact agreed signature so swapping in the real
``analysis.cpg_ingest.joern_frontend.parse_source`` is a one-line change) ->
upload to an ``ObjectStore`` (``InMemoryObjectStore`` for the hermetic unit
specs; a REAL moto-backed ``S3ObjectStore`` for the one integration spec) ->
an injected fake ``ReportStatusPort`` (the real HTTP+HMAC client is
unbuilt — see ``ReportStatusPort``'s docstring).

No boto3/AWS import happens at collection time for the ``unit``-marked tests
(``moto`` is imported lazily inside the single ``integration``-marked test).
"""

from __future__ import annotations

import io
import json
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from analysis.ordering import CPG
from services.snapshot.worker import (
    SnapshotStatusReport,
    run_execute_loop,
)
from services.substrate.object_store import (
    InMemoryObjectStore,
    ObjectStoreError,
    SnapshotKeyBuilder,
)
from services.substrate.queue import StandardQueue

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

_ORG_ID = "11111111-1111-1111-1111-111111111111"
_CODEBASE_ID = "22222222-2222-2222-2222-222222222222"
_COMMIT_SHA = "c" * 40
_ENV_DIGEST = "sha256:" + "a" * 64


def _job_body(
    *,
    snapshot_id: str = "snap-1",
    env_digest: str = _ENV_DIGEST,
    clone_url: str | None = "https://example.invalid/vulnerable-api.git",
    parent_snapshot_id: str = "",
) -> dict[str, str]:
    """Build a raw SQS message body matching CMP-SNAP-01's enqueue shape
    (``SnapshotService.create_snapshot``'s ``queue.send(body={...})``) PLUS
    ``clone_url`` — a field the shipped enqueue body does NOT currently carry
    (see ``SnapshotJob``'s docstring / this PR's handoff note)."""
    body = {
        "snapshot_id": snapshot_id,
        "org_id": _ORG_ID,
        "codebase_id": _CODEBASE_ID,
        "commit_sha": _COMMIT_SHA,
        "env_digest": env_digest,
        "parent_snapshot_id": parent_snapshot_id,
    }
    if clone_url is not None:
        body["clone_url"] = clone_url
    return body


def _make_fake_git_subprocess_run(
    fixture_files: dict[str, str],
) -> tuple[Callable[..., object], list[list[str]]]:
    """A fake ``tools.worker.secure_subprocess.subprocess.run`` for ``git``.

    Records every invoked argv (``calls``); on a ``clone`` call it materialises
    ``fixture_files`` under the destination directory (the last positional
    arg) so downstream CW-DETECT / ``parse_source`` have real files to read.
    ``checkout`` is a no-op (the fake clone already "checked out" the content).
    """
    import subprocess

    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        calls.append(list(cmd))
        if cmd[1] == "clone":
            dest = Path(cmd[-1])
            dest.mkdir(parents=True, exist_ok=True)
            for rel_path, content in fixture_files.items():
                target = dest / rel_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    return _fake_run, calls


def _fake_parse_source_factory(
    calls: list[dict[str, object]],
) -> Callable[..., CPG]:
    """A fake ``ParseSourceFn`` matching the EXACT agreed 1A/1B signature.

    Returns a small real ``CPG`` (two nodes, one AST edge) so the artifact
    builders have real content to serialise.
    """

    def _fake_parse_source(
        src_root: Path, language: str, *, env: Mapping[str, str], workdir: Path
    ) -> CPG:
        calls.append(
            {"src_root": src_root, "language": language, "env": dict(env), "workdir": workdir}
        )
        cpg = CPG()
        method_id = cpg.add_node(
            "METHOD", resolved_fqn="app.handler", structural_path="0", enclosing_decl_fqn="app"
        )
        call_id = cpg.add_node(
            "CALL",
            operator_or_literal="execute",
            resolved_fqn="app.handler.execute",
            structural_path="0.1",
            enclosing_decl_fqn="app.handler",
        )
        cpg.add_edge(method_id, call_id, "AST")
        return cpg

    return _fake_parse_source


@dataclass
class _RecordingReportStatus:
    """Fake ``ReportStatusPort`` — records every ``report`` call in order."""

    calls: list[SnapshotStatusReport] = field(default_factory=list)

    def report(self, status: SnapshotStatusReport) -> None:
        self.calls.append(status)


def _key_builder(env_digest: str = _ENV_DIGEST) -> SnapshotKeyBuilder:
    return SnapshotKeyBuilder(
        org_id=_ORG_ID, codebase_id=_CODEBASE_ID, commit_sha=_COMMIT_SHA, env_digest=env_digest
    )


# ---------------------------------------------------------------------------
# Happy path: bootstrap sequence, artifacts, report_status
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_bootstrap_success_sequence_and_report_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """The full bootstrap sequence runs in order and reports ``ready``.

    Asserts: git ``clone`` THEN ``checkout`` (via the REAL ``secure_run`` argv
    allowlist — only the underlying subprocess spawn is faked); ``parse_source``
    invoked once with the language inferred from the cloned tree; exactly one
    ``report_status`` call with ``state="ready"`` and the REAL CW-DETECT verdict
    as ``precondition_status``; the four bootstrap-mode artifacts (NOT
    ``delta_graph`` — a bootstrap snapshot has no parent) persisted at the
    deterministic ``SnapshotKeyBuilder`` keys; the SQS message acked (no
    redelivery, no DLQ).
    """
    import tools.worker.secure_subprocess as ss

    vulnerable_source = (
        "def handler(username):\n    return f\"SELECT * FROM USERS WHERE X='{username}'\"\n"
    )
    fake_run, git_calls = _make_fake_git_subprocess_run({"app.py": vulnerable_source})
    monkeypatch.setattr(ss.subprocess, "run", fake_run)

    parse_calls: list[dict[str, object]] = []
    fake_parse_source = _fake_parse_source_factory(parse_calls)

    queue = StandardQueue(name="snapshot-jobs")
    queue.send(body=_job_body(), dedup_key="snap-1")
    object_store = InMemoryObjectStore()
    report_status = _RecordingReportStatus()

    run_execute_loop(
        _ENV_DIGEST,
        queue=queue,
        object_store=object_store,
        parse_source=fake_parse_source,
        report_status=report_status,
        environ={},
    )

    # --- sequence: clone THEN checkout, via the real argv-allowlisted path ---
    assert [c[1] for c in git_calls] == ["clone", "checkout"]
    assert git_calls[0][2] == "--quiet"  # sanctioned flag actually used

    # --- parse_source invoked once, with the language CW-DETECT/us inferred ---
    assert len(parse_calls) == 1
    assert parse_calls[0]["language"] == "python"

    # --- report_status: exactly one call, ready, real CW-DETECT verdict ---
    assert len(report_status.calls) == 1
    report = report_status.calls[0]
    assert report.snapshot_id == "snap-1"
    assert report.state == "ready"
    assert report.precondition_status == "closed-world"
    assert report.env_digest == _ENV_DIGEST
    assert report.error is None
    assert report.snapshot_digest is not None
    assert report.snapshot_digest.startswith("sha256:")

    # --- artifacts: the four bootstrap-mode bodies land at the deterministic
    # keys; delta_graph is absent (bootstrap has no parent -> no delta). ---
    keys = _key_builder().all_artifact_keys()
    bootstrap_artifact_types = (
        "cpg_tarball",
        "reverse_symbol_index",
        "dynamic_call_graph",
        "precondition_status",
    )
    for artifact_type in bootstrap_artifact_types:
        body = object_store.get(_ORG_ID, keys[artifact_type])
        assert body  # non-empty
    with pytest.raises(ObjectStoreError):
        object_store.get(_ORG_ID, keys["delta_graph"])

    # cpg_tarball is a real gzip tar with nodes.json/edges.json members that
    # round-trip the fake CPG's two nodes / one edge.
    tarball = object_store.get(_ORG_ID, keys["cpg_tarball"])
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as tar:
        names = sorted(member.name for member in tar.getmembers())
        assert names == ["edges.json", "nodes.json"]
        nodes_member = tar.extractfile("nodes.json")
        assert nodes_member is not None
        nodes = json.loads(nodes_member.read())
        assert len(nodes) == 2
        edges_member = tar.extractfile("edges.json")
        assert edges_member is not None
        edges = json.loads(edges_member.read())
        assert edges == [{"src": 0, "dst": 1, "kind": "AST"}]

    # precondition_status.json carries the real CW-DETECT verdict shape.
    status_body = json.loads(object_store.get(_ORG_ID, keys["precondition_status"]))
    assert status_body["verdict"] == "closed-world"
    assert status_body["reflection_sites"] == []

    # --- queue: acked, no redelivery, no DLQ ---
    assert queue.ready_depth == 0
    assert queue.dlq_messages == []


# ---------------------------------------------------------------------------
# No job available: a pure no-op, no collaborator touched
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_no_job_available_is_a_noop_and_touches_no_gated_collaborator() -> None:
    """An empty queue returns immediately, WITHOUT constructing
    ``object_store``/``parse_source``/``report_status`` (their fail-closed
    production defaults would raise if touched — see ``run_execute_loop``'s
    "deferred until AFTER we know there is a job" ordering)."""
    queue = StandardQueue(name="snapshot-jobs")
    run_execute_loop(_ENV_DIGEST, queue=queue, environ={})
    assert queue.ready_depth == 0
    assert queue.dlq_messages == []


# ---------------------------------------------------------------------------
# CLAR-SNAP-04 guard: an incremental (has-parent) job is refused fail-closed
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_incremental_job_is_refused_clar_snap_04(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ``SnapshotJob`` carrying ``parent_snapshot_id`` is refused BEFORE any
    clone is attempted (CMP-SNAP-02 is not wired; CLAR-SNAP-04)."""
    import tools.worker.secure_subprocess as ss

    def _must_not_be_called(cmd: list[str], **kwargs: object) -> object:
        raise AssertionError(f"git must not be invoked for a refused incremental job: {cmd!r}")

    monkeypatch.setattr(ss.subprocess, "run", _must_not_be_called)

    queue = StandardQueue(name="snapshot-jobs")
    queue.send(
        body=_job_body(snapshot_id="snap-incr", parent_snapshot_id="parent-1"),
        dedup_key="snap-incr",
    )
    report_status = _RecordingReportStatus()

    run_execute_loop(_ENV_DIGEST, queue=queue, report_status=report_status, environ={})

    assert len(report_status.calls) == 1
    report = report_status.calls[0]
    assert report.state == "failed"
    assert report.snapshot_id == "snap-incr"
    assert report.precondition_status is None
    assert report.error is not None
    assert "CLAR-SNAP-04" in report.error
    # failed -> redelivered (receive_count 1 < max_receive_count 3), not DLQ'd.
    assert queue.ready_depth == 1
    assert queue.dlq_messages == []


# ---------------------------------------------------------------------------
# INV-2 guard: job.env_digest must match this worker's bound env_digest
# ---------------------------------------------------------------------------


@pytest.mark.invariant
@pytest.mark.unit
def test_env_digest_mismatch_is_refused_inv2(monkeypatch: pytest.MonkeyPatch) -> None:
    """A job stamped for a DIFFERENT ``env_digest`` than this worker's bound
    one is refused fail-closed (INV-2) before any clone is attempted."""
    import tools.worker.secure_subprocess as ss

    def _must_not_be_called(cmd: list[str], **kwargs: object) -> object:
        raise AssertionError(f"git must not be invoked on an INV-2 mismatch: {cmd!r}")

    monkeypatch.setattr(ss.subprocess, "run", _must_not_be_called)

    wrong_digest = "sha256:" + "b" * 64
    queue = StandardQueue(name="snapshot-jobs")
    queue.send(
        body=_job_body(snapshot_id="snap-mismatch", env_digest=wrong_digest),
        dedup_key="snap-mismatch",
    )
    report_status = _RecordingReportStatus()

    run_execute_loop(_ENV_DIGEST, queue=queue, report_status=report_status, environ={})

    assert len(report_status.calls) == 1
    report = report_status.calls[0]
    assert report.state == "failed"
    assert report.error is not None
    assert "INV-2" in report.error
    assert queue.ready_depth == 1


# ---------------------------------------------------------------------------
# Malformed message body: no snapshot_id to report against -> no report_status
# call (still redelivered / eventually DLQ'd, per DOC §7 failure handling).
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_malformed_job_missing_clone_url_fails_without_reporting() -> None:
    """A message body missing ``clone_url`` fails to PARSE at all: there is no
    ``snapshot_id`` to report against, so ``report_status`` is never called —
    the message is simply failed back to the queue for redelivery."""
    queue = StandardQueue(name="snapshot-jobs")
    queue.send(body=_job_body(clone_url=None), dedup_key="snap-malformed")
    report_status = _RecordingReportStatus()

    run_execute_loop(_ENV_DIGEST, queue=queue, report_status=report_status, environ={})

    assert report_status.calls == []
    assert queue.ready_depth == 1
    assert queue.dlq_messages == []


# ---------------------------------------------------------------------------
# parse_source failure (simulating CLAR-SNAP-03 / track 1A not ready yet):
# reported as failed AFTER a real CW-DETECT verdict was already computed.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_parse_source_failure_reports_failed_and_redelivers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``parse_source`` failure (e.g. the real CLAR-SNAP-03 front end not
    landed yet) is caught, reported as ``state="failed"`` with the exception
    message threaded into ``error``, and the message is failed back to the
    queue (not silently dropped)."""
    import tools.worker.secure_subprocess as ss

    fake_run, git_calls = _make_fake_git_subprocess_run({"app.py": "print('hello')\n"})
    monkeypatch.setattr(ss.subprocess, "run", fake_run)

    def _boom_parse_source(
        src_root: Path, language: str, *, env: Mapping[str, str], workdir: Path
    ) -> CPG:
        raise RuntimeError("simulated: CLAR-SNAP-03 front end not landed yet")

    queue = StandardQueue(name="snapshot-jobs")
    queue.send(body=_job_body(snapshot_id="snap-parsefail"), dedup_key="snap-parsefail")
    report_status = _RecordingReportStatus()

    run_execute_loop(
        _ENV_DIGEST,
        queue=queue,
        object_store=InMemoryObjectStore(),
        parse_source=_boom_parse_source,
        report_status=report_status,
        environ={},
    )

    # the clone DID happen (parse_source runs after it) — one call each.
    assert [c[1] for c in git_calls] == ["clone", "checkout"]

    assert len(report_status.calls) == 1
    report = report_status.calls[0]
    assert report.state == "failed"
    assert report.snapshot_id == "snap-parsefail"
    assert report.precondition_status is None  # null on failure (DOC §3.2)
    assert report.snapshot_digest is None
    assert report.error is not None
    assert "CLAR-SNAP-03" in report.error
    assert queue.ready_depth == 1
    assert queue.dlq_messages == []


# ---------------------------------------------------------------------------
# moto-backed S3 round trip (the ALREADY-REAL S3ObjectStore substrate).
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_bootstrap_uploads_survive_a_real_moto_s3_round_trip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The four bootstrap artifacts round-trip through a REAL (moto-backed)
    ``S3ObjectStore`` — proving the loop's ``object_store.put`` calls are
    genuinely S3-shaped, not just compatible with the in-memory fake."""
    import boto3
    from moto import mock_aws

    import tools.worker.secure_subprocess as ss
    from services.substrate.object_store import S3ObjectStore

    fake_run, _git_calls = _make_fake_git_subprocess_run({"app.py": "print('hello')\n"})
    monkeypatch.setattr(ss.subprocess, "run", fake_run)

    parse_calls: list[dict[str, object]] = []
    fake_parse_source = _fake_parse_source_factory(parse_calls)

    queue = StandardQueue(name="snapshot-jobs")
    queue.send(body=_job_body(snapshot_id="snap-moto"), dedup_key="snap-moto")
    report_status = _RecordingReportStatus()

    with mock_aws():
        s3_client = boto3.client("s3", region_name="us-east-1")
        bucket = "scanipy-test-snapshots"
        s3_client.create_bucket(Bucket=bucket)
        store = S3ObjectStore(bucket, client=s3_client)

        run_execute_loop(
            _ENV_DIGEST,
            queue=queue,
            object_store=store,
            parse_source=fake_parse_source,
            report_status=report_status,
            environ={},
        )

        assert len(report_status.calls) == 1
        assert report_status.calls[0].state == "ready"

        keys = _key_builder().all_artifact_keys()
        cpg_body = store.get(_ORG_ID, keys["cpg_tarball"])
        assert cpg_body
        with tarfile.open(fileobj=io.BytesIO(cpg_body), mode="r:gz") as tar:
            assert sorted(m.name for m in tar.getmembers()) == ["edges.json", "nodes.json"]

    assert queue.ready_depth == 0
    assert queue.dlq_messages == []
