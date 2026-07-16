"""CMP-ORCH-03 entrypoint specs — ``services/scan/detector_worker.py`` (Track 1C).

Exercises the per-job pipeline (S3 fetch -> deserialize -> registry lookup ->
``run_detector`` -> ORM insert -> ``sign_provenance``) end to end at the unit
level: the REAL CMP-DET-02 registry (loaded from ``detectors/``) and the REAL
``services.scan.worker.run_detector`` run unmodified against a real
:class:`analysis.ordering.CPG` (``tests.orch03_fakes.injection_taint_cpg``,
the same fixture ``tests/unit/test_orch_specs.py`` uses for its own real-solver
positive tests); only the I/O boundaries this track owns (the S3 object store,
the findings-store DB session, the KMS signer) are fakes, proving the wiring
this track built actually works, not just that its own mocks agree with
themselves.

Mirrors the established DI-fake convention (``tests/fnd03_fakes.py``,
``tests/orch03_fakes.py``): reuses ``SoftwareKMSSigner`` /
``InMemoryProvenanceStore`` (real signing math, no AWS) and the real, shipped
``services.substrate.object_store.InMemoryObjectStore`` /
``services.substrate.queue.StandardQueue`` substrate primitives (CMP-DEPLOY-01)
rather than inventing parallel fakes for already-real components.
"""

from __future__ import annotations

import uuid

import pytest

from detectors.registry import DetectorRegistry
from services.scan.detector_worker import (
    ENV_DIGEST_VAR,
    CPGDeserializationError,
    DetectorJobResult,
    DetectorNotFoundError,
    EnvDigestMismatchError,
    EnvDigestMissing,
    MalformedJobMessageError,
    boot,
    deserialize_cpg_tarball,
    handle_queue_message,
    parse_job_message,
    resolve_env_digest,
    run_detector_job,
    serialize_cpg_tarball,
)
from services.scan.provenance import verify_chain
from services.scan.worker import WorkerJob
from services.substrate.object_store import InMemoryObjectStore, SnapshotKeyBuilder
from services.substrate.queue import StandardQueue
from tests.fnd03_fakes import InMemoryProvenanceStore, SoftwareKMSSigner
from tests.orch03_fakes import good_job, injection_taint_cpg

_ORG_ID = uuid.UUID(int=42)
_SCM_PROVIDER = "github"
_KMS_KEY_ARN = "arn:aws:kms:us-east-1:000000000000:key/detector-worker-test"


class _RecordingFindingsSession:
    """A fake ``FindingsSession`` (Protocol satisfied structurally) that
    records every row passed to ``add`` and counts ``commit`` calls, so a
    test can assert exactly what would have reached Postgres."""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def commit(self) -> None:
        self.commits += 1


def _seed_cpg_artifact(store: InMemoryObjectStore, job: WorkerJob, *, org_id: uuid.UUID) -> None:
    """Put the real injection-taint CPG, serialized via this track's own
    tarball format, at the exact key :func:`run_detector_job` will fetch."""
    key = SnapshotKeyBuilder(
        org_id=str(org_id),
        codebase_id=str(job.codebase_id),
        commit_sha=job.commit_sha,
        env_digest=job.env_digest,
    ).artifact_key("cpg_tarball")
    store.put(str(org_id), key, serialize_cpg_tarball(injection_taint_cpg()))


def _message_body(job: WorkerJob, *, org_id: uuid.UUID, scm_provider: str) -> dict[str, str]:
    """Project a :class:`WorkerJob` onto this track's own message envelope
    (mirrors ``services/scan/api.py::_job_to_queue_body`` plus the two extra
    keys documented as KNOWN GAP 1 in the module docstring)."""
    return {
        "job_id": str(job.job_id),
        "scan_id": str(job.scan_id),
        "snapshot_id": str(job.snapshot_id),
        "codebase_id": str(job.codebase_id),
        "commit_sha": job.commit_sha,
        "detector_id": job.detector_id,
        "S_version": job.S_version,
        "env_digest": job.env_digest,
        "org_id": str(org_id),
        "scm_provider": scm_provider,
    }


def _real_registry() -> DetectorRegistry:
    registry = DetectorRegistry()
    registry.load_manifests("detectors/")
    return registry


# ---------------------------------------------------------------------------
# §1 — CPG tarball (de)serialization (this track's own default format)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cpg_tarball_roundtrip_preserves_nodes_and_edges() -> None:
    """``serialize_cpg_tarball`` -> ``deserialize_cpg_tarball`` reproduces the
    same node/edge content (this track's own default CPG artifact format)."""
    original = injection_taint_cpg()
    restored = deserialize_cpg_tarball(serialize_cpg_tarball(original))

    assert len(restored.nodes) == len(original.nodes)
    assert len(restored.edges) == len(original.edges)
    for before, after in zip(original.nodes, restored.nodes, strict=True):
        assert after.kind == before.kind
        assert after.operator_or_literal == before.operator_or_literal
        assert after.enclosing_decl_fqn == before.enclosing_decl_fqn
        assert after.structural_path == before.structural_path
    for edge_before, edge_after in zip(original.edges, restored.edges, strict=True):
        assert (edge_after.src, edge_after.dst, edge_after.kind) == (
            edge_before.src,
            edge_before.dst,
            edge_before.kind,
        )


@pytest.mark.unit
def test_cpg_tarball_rejects_non_dense_node_ids() -> None:
    """Fail-closed: a tarball whose node array is not sorted/dense 0..N-1 is
    rejected rather than silently re-ordered (INV-5's node-emission-order
    requirement is the PRODUCER's obligation, never this consumer's)."""
    import io
    import json
    import tarfile

    payload = {
        "format_version": "1",
        "nodes": [{"node_id": 1, "kind": "METHOD"}],  # position 0, node_id 1 -> gap
        "edges": [],
    }
    raw = json.dumps(payload).encode("utf-8")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="cpg.json")
        info.size = len(raw)
        tar.addfile(info, io.BytesIO(raw))

    with pytest.raises(CPGDeserializationError):
        deserialize_cpg_tarball(buf.getvalue())


@pytest.mark.unit
def test_cpg_tarball_rejects_out_of_range_edge_reference() -> None:
    """Fail-closed: an edge referencing a node id outside the parsed node
    range is rejected rather than silently accepted by the CPG."""
    import io
    import json
    import tarfile

    payload = {
        "format_version": "1",
        "nodes": [{"node_id": 0, "kind": "METHOD"}],
        "edges": [{"src": 0, "dst": 99, "kind": "CFG"}],
    }
    raw = json.dumps(payload).encode("utf-8")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="cpg.json")
        info.size = len(raw)
        tar.addfile(info, io.BytesIO(raw))

    with pytest.raises(CPGDeserializationError):
        deserialize_cpg_tarball(buf.getvalue())


@pytest.mark.unit
def test_cpg_tarball_rejects_malformed_gzip() -> None:
    """Fail-closed: garbage bytes never crash the worker with an unhandled
    exception type — they raise the module's own typed error."""
    with pytest.raises(CPGDeserializationError):
        deserialize_cpg_tarball(b"not a tarball")


# ---------------------------------------------------------------------------
# §2 — job-message envelope parsing (this track's own default; KNOWN GAP 1)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_parse_job_message_round_trips_a_well_formed_envelope() -> None:
    job = good_job()
    body = _message_body(job, org_id=_ORG_ID, scm_provider=_SCM_PROVIDER)

    parsed_job, org_id, scm_provider = parse_job_message(body)

    assert parsed_job == job
    assert org_id == _ORG_ID
    assert scm_provider == _SCM_PROVIDER


@pytest.mark.unit
def test_parse_job_message_rejects_missing_org_id() -> None:
    """``org_id`` is this track's own envelope extension (KNOWN GAP 1) — a
    message without it is rejected fail-closed, never defaulted."""
    job = good_job()
    body = _message_body(job, org_id=_ORG_ID, scm_provider=_SCM_PROVIDER)
    del body["org_id"]

    with pytest.raises(MalformedJobMessageError):
        parse_job_message(body)


@pytest.mark.unit
def test_parse_job_message_rejects_malformed_uuid() -> None:
    job = good_job()
    body = _message_body(job, org_id=_ORG_ID, scm_provider=_SCM_PROVIDER)
    body["scan_id"] = "not-a-uuid"

    with pytest.raises(MalformedJobMessageError):
        parse_job_message(body)


# ---------------------------------------------------------------------------
# §3 — run_detector_job: the real end-to-end pipeline (this track's core proof)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_detector_job_produces_a_real_deterministic_core_finding_row() -> None:
    """End-to-end proof: S3 fetch -> deserialize -> registry lookup -> the
    REAL ``run_detector`` -> a real ORM ``Finding`` row + a REAL, independently
    verifiable signed provenance record.

    Test id:        (Track 1C hermetic hand-off proof, no TST-AC-* assigned —
                     this track files no CLAR/AC; see the module's own
                     docstring KNOWN GAPS section for the deviations this
                     covers.)
    Kind tag:       [UNIT] — no real AWS/Postgres; every I/O boundary this
                     track owns is a fake, but the CMP-DET-02 registry and
                     ``run_detector`` run FOR REAL against a real CPG.
    Pass criteria:  At least one finding fires (anti-vacuity); every produced
                    ORM row carries a non-null origin/S_version/env_digest
                    (INV-1/INV-2) and the pinned INV-5 annotation; every
                    signed provenance record independently verifies
                    (``verify_chain`` -> ``VERIFIED``) without re-running any
                    analysis.
    """
    job = good_job()
    store = InMemoryObjectStore()
    _seed_cpg_artifact(store, job, org_id=_ORG_ID)
    session = _RecordingFindingsSession()
    signer = SoftwareKMSSigner()
    provenance_store = InMemoryProvenanceStore()

    result = run_detector_job(
        job,
        org_id=_ORG_ID,
        scm_provider=_SCM_PROVIDER,
        object_store=store,
        findings_session=session,
        signer=signer,
        kms_key_arn=_KMS_KEY_ARN,
        registry=_real_registry(),
        provenance_store=provenance_store,
    )

    assert isinstance(result, DetectorJobResult)
    assert result.findings, "real registry detector produced zero findings (vacuous)"
    assert len(result.findings) == len(result.signed_records) == len(session.added)
    assert session.commits == 1

    for f in result.findings:
        assert f.origin == "deterministic-core"
        assert f.class_ == "injection"

    for row in session.added:
        # session.added holds the real ORM ``Finding`` (services.scan.models.findings)
        assert row.org_id == _ORG_ID  # type: ignore[attr-defined]
        assert row.origin == "deterministic-core"  # type: ignore[attr-defined]
        assert row.S_version == job.S_version  # type: ignore[attr-defined]
        assert row.env_digest == job.env_digest  # type: ignore[attr-defined]
        assert len(row.cpg_order_hash) == 32  # type: ignore[attr-defined]
        assert (
            row.cpg_order_hash_annotation  # type: ignore[attr-defined]
            == "canonical iff fingerprint_class = strong"
        )
        assert len(row.slice_fingerprint) == 32  # type: ignore[attr-defined]

    for signed in result.signed_records:
        assert signed.record.claim_label == "CONDITIONAL_THEOREM"
        verdict = verify_chain(signed, signer=signer, store=provenance_store)
        assert verdict == "VERIFIED"


@pytest.mark.unit
def test_run_detector_job_unknown_detector_raises_detector_not_found() -> None:
    """DOC-CMP-ORCH-03 §3.5: an unknown ``detector_id`` fails the job rather
    than silently no-op'ing."""
    job = good_job(detector_id="does-not-exist")
    store = InMemoryObjectStore()
    _seed_cpg_artifact(store, job, org_id=_ORG_ID)

    with pytest.raises(DetectorNotFoundError):
        run_detector_job(
            job,
            org_id=_ORG_ID,
            scm_provider=_SCM_PROVIDER,
            object_store=store,
            findings_session=_RecordingFindingsSession(),
            signer=SoftwareKMSSigner(),
            kms_key_arn=_KMS_KEY_ARN,
            registry=_real_registry(),
        )


@pytest.mark.invariant
def test_inv_1_2_5_detector_worker_threads_all_four_provenance_fields() -> None:
    """INV-1/INV-2/INV-5 belt: every persisted row AND every signed chain
    record this track produces carries the four required provenance fields
    (RULE-6), never null, never blurred."""
    job = good_job()
    store = InMemoryObjectStore()
    _seed_cpg_artifact(store, job, org_id=_ORG_ID)
    session = _RecordingFindingsSession()

    result = run_detector_job(
        job,
        org_id=_ORG_ID,
        scm_provider=_SCM_PROVIDER,
        object_store=store,
        findings_session=session,
        signer=SoftwareKMSSigner(),
        kms_key_arn=_KMS_KEY_ARN,
        registry=_real_registry(),
    )
    assert result.findings

    for row in session.added:
        assert row.origin in ("deterministic-core", "oracle-passthrough")  # type: ignore[attr-defined]
        assert row.determinism_partition == row.origin  # type: ignore[attr-defined]
        assert row.S_version  # type: ignore[attr-defined]
        assert row.env_digest.startswith("sha256:")  # type: ignore[attr-defined]
        assert (
            row.cpg_order_hash_annotation  # type: ignore[attr-defined]
            == "canonical iff fingerprint_class = strong"
        )

    for signed in result.signed_records:
        record = signed.record
        assert record.origin in ("deterministic-core", "oracle-passthrough")
        assert record.S_version
        assert record.env_digest.startswith("sha256:")
        assert record.cpg_order_hash_annotation == "canonical iff fingerprint_class = strong"


# ---------------------------------------------------------------------------
# §4 — handle_queue_message: ack/fail against the REAL StandardQueue substrate
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_handle_queue_message_acks_on_success() -> None:
    job = good_job()
    store = InMemoryObjectStore()
    _seed_cpg_artifact(store, job, org_id=_ORG_ID)
    queue = StandardQueue(name="scanipy-prod-detector-jobs")
    queue.send(
        _message_body(job, org_id=_ORG_ID, scm_provider=_SCM_PROVIDER),
        dedup_key=str(job.job_id),
    )

    received = queue.receive()
    assert received is not None

    result = handle_queue_message(
        received,
        queue=queue,
        object_store=store,
        findings_session=_RecordingFindingsSession(),
        signer=SoftwareKMSSigner(),
        kms_key_arn=_KMS_KEY_ARN,
        registry=_real_registry(),
    )

    assert result is not None
    assert result.findings
    assert queue.ready_depth == 0
    assert queue.dlq_messages == []  # acked, never redelivered/DLQ'd


@pytest.mark.unit
def test_handle_queue_message_fails_message_back_to_queue_on_error() -> None:
    """A malformed envelope (or any pipeline exception) fails the message —
    the worker process does not crash, and the message is redelivered rather
    than silently dropped (mirrors ``IdempotentConsumer.poll_once``'s
    already-shipped never-crash-on-one-message posture)."""
    job = good_job(detector_id="does-not-exist")
    store = InMemoryObjectStore()
    _seed_cpg_artifact(store, job, org_id=_ORG_ID)
    queue = StandardQueue(name="scanipy-prod-detector-jobs")
    queue.send(
        _message_body(job, org_id=_ORG_ID, scm_provider=_SCM_PROVIDER),
        dedup_key=str(job.job_id),
    )

    received = queue.receive()
    assert received is not None

    result = handle_queue_message(
        received,
        queue=queue,
        object_store=store,
        findings_session=_RecordingFindingsSession(),
        signer=SoftwareKMSSigner(),
        kms_key_arn=_KMS_KEY_ARN,
        registry=_real_registry(),
    )

    assert result is None
    assert queue.ready_depth == 1, "failed message must be redelivered, not dropped"


# ---------------------------------------------------------------------------
# §5 — env-digest fail-closed boot gate (INV-2 ORIGIN; mirrors CMP-SNAP-05)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_boot_binds_a_well_formed_env_digest() -> None:
    fixture_digest = "sha256:" + "d" * 64
    assert boot({ENV_DIGEST_VAR: fixture_digest}) == fixture_digest
    assert resolve_env_digest({ENV_DIGEST_VAR: fixture_digest}) == fixture_digest


@pytest.mark.unit
def test_boot_fails_closed_on_missing_or_malformed_env_digest() -> None:
    with pytest.raises(EnvDigestMissing):
        resolve_env_digest({})
    with pytest.raises(EnvDigestMissing):
        resolve_env_digest({ENV_DIGEST_VAR: ""})
    with pytest.raises(EnvDigestMissing):
        resolve_env_digest({ENV_DIGEST_VAR: "not-a-digest"})
    with pytest.raises(EnvDigestMissing):
        resolve_env_digest({ENV_DIGEST_VAR: "sha256:" + "zz" * 32})  # non-hex


# ---------------------------------------------------------------------------
# Regression coverage for the claude-review findings on PR #320.
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.invariant
def test_run_detector_job_refuses_a_stale_env_digest_mismatch() -> None:
    """A dequeued job claiming a different env_digest than this worker's own
    boot-time SCANIPY_ENV_DIGEST must be refused fail-closed (INV-2) — never
    silently threaded into provenance. Positive control: the matching-digest
    case (already covered by every other run_detector_job test, which omits
    boot_env_digest or passes the same value) still succeeds."""
    job = good_job()  # env_digest == _GOOD_ENV_DIGEST
    store = InMemoryObjectStore()
    _seed_cpg_artifact(store, job, org_id=_ORG_ID)

    with pytest.raises(EnvDigestMismatchError):
        run_detector_job(
            job,
            org_id=_ORG_ID,
            scm_provider=_SCM_PROVIDER,
            object_store=store,
            findings_session=_RecordingFindingsSession(),
            signer=SoftwareKMSSigner(),
            kms_key_arn=_KMS_KEY_ARN,
            registry=_real_registry(),
            boot_env_digest="sha256:" + "f" * 64,  # deliberately != job.env_digest
        )

    # boot_env_digest=None (the default) and a matching value must both
    # still succeed — the guard is opt-in, not a regression for existing
    # callers that construct a WorkerJob directly without a real boot.
    result = run_detector_job(
        job,
        org_id=_ORG_ID,
        scm_provider=_SCM_PROVIDER,
        object_store=store,
        findings_session=_RecordingFindingsSession(),
        signer=SoftwareKMSSigner(),
        kms_key_arn=_KMS_KEY_ARN,
        registry=_real_registry(),
        boot_env_digest=job.env_digest,
    )
    assert isinstance(result, DetectorJobResult)


@pytest.mark.unit
@pytest.mark.invariant
def test_serialize_cpg_tarball_is_byte_identical_across_repeated_calls() -> None:
    """The gzip WRAPPER header (not just the tar member) must be pinned —
    tarfile's 'w:gz' mode delegates to gzip.GzipFile's default
    mtime=time.time(), which would make two calls on identical input produce
    different bytes despite the tar member's own info.mtime=0 (the exact bug
    claude-review caught on PR #320: 'deterministic archive bytes across
    re-runs' was claimed but not achieved). This is the CP-05
    byte-identical-SARIF guarantee's first line of defense for this
    artifact."""
    cpg = injection_taint_cpg()
    first = serialize_cpg_tarball(cpg)
    second = serialize_cpg_tarball(cpg)
    assert first == second, "serialize_cpg_tarball is not byte-deterministic"
    # anti-vacuity: prove this isn't trivially true because gzip wraps
    # zero-length/constant content — the two calls really did run the
    # compressor twice, and content still round-trips correctly.
    assert deserialize_cpg_tarball(first).nodes == cpg.nodes
