"""CMP-SNAP-05 ``run_execute_loop`` — bootstrap (no-parent) execute-loop specs.

Controlled post-acquisition tests for ``run_execute_loop``: SQS dequeue ->
explicitly injected trusted source-fixture materializer (NO native Git or
source-custody proof) -> real ``CMP-SNAP-03`` ``cw_detect.detect`` -> an injected
fake ``parse_source`` (satisfies the exact agreed signature the production
default, ``analysis.cpg_ingest.joern_frontend.parse_source``, also
implements — CLAR-SNAP-03/05 landed) -> upload to an ``ObjectStore``
(``InMemoryObjectStore`` for the hermetic unit specs; a REAL moto-backed
``S3ObjectStore`` for the one integration spec) -> an injected fake
``ReportStatusPort`` (the real HTTP+HMAC client is unbuilt — see
``ReportStatusPort``'s docstring).

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
    SnapshotJob,
    SnapshotStatusReport,
    SourceMaterializer,
    run_execute_loop,
)
from services.substrate.cpg_tarball import deserialize_cpg_tarball
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


def _make_source_materializer(
    fixture_files: dict[str, str],
) -> tuple[SourceMaterializer, list[tuple[SnapshotJob, Path]]]:
    """Write controlled fixture data; never open the native acquisition guard."""
    calls: list[tuple[SnapshotJob, Path]] = []

    def materialize(job: SnapshotJob, destination: Path) -> None:
        calls.append((job, destination))
        destination.mkdir()
        for rel_path, content in fixture_files.items():
            target = destination / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)

    return materialize, calls


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
def test_bootstrap_success_sequence_and_report_status() -> None:
    """The controlled post-acquisition sequence runs in order and reports ready.

    Asserts: explicit trusted fixture materialization precedes ``parse_source``
    invoked once with the language inferred from that fixture; exactly one
    ``report_status`` call with ``state="ready"`` and the REAL CW-DETECT verdict
    as ``precondition_status``; the four bootstrap-mode artifacts (NOT
    ``delta_graph`` — a bootstrap snapshot has no parent) persisted at the
    deterministic ``SnapshotKeyBuilder`` keys; the SQS message acked (no
    redelivery, no DLQ).
    """
    vulnerable_source = (
        "def handler(username):\n    return f\"SELECT * FROM USERS WHERE X='{username}'\"\n"
    )
    materialize, materialize_calls = _make_source_materializer({"app.py": vulnerable_source})

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
        source_materializer=materialize,
        report_status=report_status,
        environ={},
    )

    # --- controlled fixture materialization, not native execution evidence ---
    assert len(materialize_calls) == 1
    assert materialize_calls[0][0].commit_sha == _COMMIT_SHA
    assert materialize_calls[0][1] == parse_calls[0]["src_root"]

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

    # cpg_tarball is the shared services.substrate.cpg_tarball format (single
    # cpg.json member) — round-trips the fake CPG's two nodes / one edge
    # through the REAL consumer (CMP-ORCH-03 / detector_worker.py imports the
    # same deserialize_cpg_tarball, CLAR-ORCH-10/CLAR-SNAP-08).
    tarball = object_store.get(_ORG_ID, keys["cpg_tarball"])
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as tar:
        names = sorted(member.name for member in tar.getmembers())
        assert names == ["cpg.json"]
    restored = deserialize_cpg_tarball(tarball)
    assert len(restored.nodes) == 2
    assert [(int(e.src), int(e.dst), e.kind) for e in restored.edges] == [(0, 1, "AST")]

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
def test_parse_source_failure_reports_failed_and_redelivers() -> None:
    """A ``parse_source`` failure (e.g. the real CLAR-SNAP-03 front end not
    landed yet) is caught, reported as ``state="failed"`` with the exception
    message threaded into ``error``, and the message is failed back to the
    queue (not silently dropped)."""
    materialize, materialize_calls = _make_source_materializer({"app.py": "print('hello')\n"})

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
        source_materializer=materialize,
        report_status=report_status,
        environ={},
    )

    assert len(materialize_calls) == 1  # fixture materialization preceded parsing

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
def test_bootstrap_uploads_survive_a_real_moto_s3_round_trip() -> None:
    """The four bootstrap artifacts round-trip through a REAL (moto-backed)
    ``S3ObjectStore`` — proving the loop's ``object_store.put`` calls are
    genuinely S3-shaped, not just compatible with the in-memory fake."""
    import boto3
    from moto import mock_aws

    from services.substrate.object_store import S3ObjectStore

    materialize, _materialize_calls = _make_source_materializer({"app.py": "print('hello')\n"})

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
            source_materializer=materialize,
            report_status=report_status,
            environ={},
        )

        assert len(report_status.calls) == 1
        assert report_status.calls[0].state == "ready"

        keys = _key_builder().all_artifact_keys()
        cpg_body = store.get(_ORG_ID, keys["cpg_tarball"])
        assert cpg_body
        with tarfile.open(fileobj=io.BytesIO(cpg_body), mode="r:gz") as tar:
            assert sorted(m.name for m in tar.getmembers()) == ["cpg.json"]
        deserialize_cpg_tarball(cpg_body)  # round-trips without raising

    assert queue.ready_depth == 0
    assert queue.dlq_messages == []


# ---------------------------------------------------------------------------
# Production-default wiring: the real parse_source / SQSQueue seams
# (CLAR-SNAP-03/05 landing) — regression guards for the two collaborators
# that were fail-closed stubs until this pass.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_production_parse_source_default_is_the_real_joern_frontend() -> None:
    """``run_execute_loop``'s ``parse_source`` default is the real
    ``analysis.cpg_ingest.joern_frontend.parse_source`` — not the retired
    fail-closed stub — confirmed by identity, not by invoking it (invoking it
    needs a real Joern install, out of scope for a hermetic unit test)."""
    import services.snapshot.worker as worker_module
    from analysis.cpg_ingest.joern_frontend import parse_source as real_parse_source

    assert worker_module._real_parse_source is real_parse_source


@pytest.mark.unit
def test_production_queue_default_fails_closed_without_snapshot_queue_url() -> None:
    """``_default_snapshot_queue`` refuses to construct an unbound ``SQSQueue``
    when ``SNAPSHOT_QUEUE_URL`` is unset — mirrors ``_default_object_store``'s
    ``S3_BUCKET`` fail-closed contract exactly."""
    import services.snapshot.worker as worker_module
    from services.scan.provenance import InvariantViolation

    with pytest.raises(InvariantViolation, match="SNAPSHOT_QUEUE_URL"):
        worker_module._default_snapshot_queue({})


@pytest.mark.unit
def test_production_queue_default_builds_a_real_sqs_queue_when_configured() -> None:
    """``_default_snapshot_queue`` builds a real ``SQSQueue`` bound to the
    configured URL when ``SNAPSHOT_QUEUE_URL`` is set (boto3 client injection
    happens lazily inside ``SQSQueue`` itself, not exercised here)."""
    import services.snapshot.worker as worker_module
    from services.substrate.queue import SQSQueue

    active = worker_module._default_snapshot_queue(
        {"SNAPSHOT_QUEUE_URL": "https://sqs.us-east-1.amazonaws.com/000000000000/q"}
    )
    assert isinstance(active, SQSQueue)
    assert active.queue_url == "https://sqs.us-east-1.amazonaws.com/000000000000/q"
