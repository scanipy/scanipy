"""Real R18/R20 producers through the merged R09 consumers.

Only budgets/clocks and I/O boundaries are controlled. No graph/slice verdict,
digest or namespace is injected. This verifies scoped producer/consumer wiring,
not real-Joern refactor coverage, durable PostgreSQL storage or R08 retention.
"""

from __future__ import annotations

import json
from unittest.mock import Mock, patch

import pytest

import analysis.fingerprint as fingerprint
import analysis.ordering as ordering
from analysis.artifact_identity import (
    ANNOTATION,
    GRAPH_V2,
    SLICE_V2,
    has_strong_v2_artifact_identities,
)
from analysis.sarif.canonical_emit import validate_sarif_210
from services.scan import worker
from services.scan.detector_worker import (
    handle_queue_message,
    run_detector_job,
    serialize_cpg_tarball,
)
from services.scan.provenance import verify_chain
from services.substrate.object_store import InMemoryObjectStore, SnapshotKeyBuilder
from services.substrate.queue import StandardQueue
from tests.fnd03_fakes import InMemoryProvenanceStore, SoftwareKMSSigner
from tests.orch03_fakes import core_injection_detector, good_job
from tests.unit.test_canonical_budget_v2 import Clock
from tests.unit.test_detector_worker_specs import (
    _KMS_KEY_ARN,
    _ORG_ID,
    _message_body,
    _real_registry,
    _RecordingFindingsSession,
)

pytestmark = pytest.mark.unit


def _graph(graph_class: str, slice_class: str) -> ordering.CPG:
    """B=1 independently distinguishes graph symmetry and nested slice work."""
    graph = ordering.CPG()
    method = graph.add_node("METHOD", resolved_fqn="m.handler", enclosing_decl_fqn="m.handler")
    source = graph.add_node(
        "CALL", operator_or_literal="flask.request.args.get(*)", enclosing_decl_fqn="m.handler"
    )
    sink = graph.add_node(
        "CALL", operator_or_literal="subprocess.Popen(arg[0])", enclosing_decl_fqn="m.handler"
    )
    graph.add_edge(method, source, "CFG")
    if slice_class == "weak":
        local = graph.add_node(
            "IDENTIFIER", operator_or_literal="x", enclosing_decl_fqn="m.handler"
        )
        graph.add_edge(source, local, "CFG")
        graph.add_edge(local, sink, "CFG")
        if graph_class == "weak":
            twin = graph.add_node(
                "IDENTIFIER", operator_or_literal="x", enclosing_decl_fqn="m.handler"
            )
            graph.add_edge(source, twin, "CFG")
            graph.add_edge(twin, sink, "CFG")
    else:
        graph.add_edge(source, sink, "CFG")
        if graph_class == "weak":
            graph.add_node("NODE")
            graph.add_node("NODE")
    return graph


def _store_graph(objects, job, graph):
    key = SnapshotKeyBuilder(
        org_id=str(_ORG_ID),
        codebase_id=str(job.codebase_id),
        commit_sha=job.commit_sha,
        env_digest=job.env_digest,
    ).artifact_key("cpg_tarball")
    objects.put(str(_ORG_ID), key, serialize_cpg_tarball(graph))


@pytest.mark.parametrize("graph_class", ["strong", "weak"])
@pytest.mark.parametrize("slice_class", ["strong", "weak"])
def test_actual_four_way_producers_reach_sarif_rows_and_signatures(
    monkeypatch, graph_class, slice_class
):
    monkeypatch.setattr(
        worker,
        "canonical_order",
        lambda graph: ordering.canonical_order(graph, B=1, T=ordering.Duration(10)),
    )
    monkeypatch.setattr(
        worker,
        "compute_slice_fingerprint",
        lambda finding, graph: fingerprint.compute_slice_fingerprint(
            finding, graph, B=1, T=ordering.Duration(10)
        ),
    )
    job = good_job()
    objects = InMemoryObjectStore()
    _store_graph(objects, job, _graph(graph_class, slice_class))
    session = _RecordingFindingsSession()
    signer = SoftwareKMSSigner()
    provenance = InMemoryProvenanceStore()
    result = run_detector_job(
        job,
        org_id=_ORG_ID,
        scm_provider="github",
        object_store=objects,
        findings_session=session,
        signer=signer,
        kms_key_arn=_KMS_KEY_ARN,
        registry=_real_registry(),
        provenance_store=provenance,
    )
    assert result.findings and session.commits == 1
    assert len(result.findings) == len(session.added) == len(result.signed_records)
    sarif = worker.emit_sarif(set(result.findings), job)
    assert validate_sarif_210(sarif.canonical_bytes) == []
    entries = json.loads(sarif.canonical_bytes)["runs"][0]["results"]
    assert len(entries) == len(result.findings)
    slice_namespace = SLICE_V2 if slice_class == "strong" else fingerprint.LEGACY_WITNESS_NAMESPACE
    for finding, row, signed, entry in zip(
        result.findings, session.added, result.signed_records, entries, strict=True
    ):
        assert finding.origin == row.origin == "deterministic-core"
        assert finding.S_version == row.S_version == job.S_version
        assert finding.env_digest == row.env_digest == job.env_digest
        assert finding.cpg_order_class == row.cpg_order_class == graph_class
        assert finding.slice_fingerprint_class == row.slice_fingerprint_class == slice_class
        assert finding.cpg_order_namespace == row.cpg_order_namespace == GRAPH_V2
        assert finding.slice_namespace == row.slice_namespace == slice_namespace
        assert row.cpg_order_status == row.slice_status == "completed"
        assert row.fingerprint_class is None
        metadata = entry["properties"]["scanipy.identity"]
        assert metadata["cpg_order"]["fingerprint_class"] == graph_class
        assert metadata["slice"]["fingerprint_class"] == slice_class
        assert metadata["cpg_order"]["namespace"] == GRAPH_V2
        assert metadata["slice"]["namespace"] == slice_namespace
        assert metadata["cpg_order"]["annotation"] == metadata["slice"]["annotation"] == ANNOTATION
        both_strong = graph_class == slice_class == "strong"
        assert has_strong_v2_artifact_identities(finding) is both_strong
        assert bool(entry["fingerprints"]) is both_strong
        assert signed.record.record_schema_version == 2
        assert signed.record.fingerprint_class is None
        assert signed.record.artifact_identity == metadata
        assert provenance.get(signed.record.id) == signed
        assert verify_chain(signed, signer=signer) == "VERIFIED"


@pytest.mark.parametrize("stage", ["graph", "slice"])
@pytest.mark.parametrize("caller", ["direct", "job", "queue"])
def test_actual_deadline_is_failed_attempt_not_empty_success(monkeypatch, stage, caller):
    """No invented timeout exception: the real budget observes an expired clock.

    Graph timeout precedes solver dispatch; slice timeout follows raw detection.
    Neither currently persists findings. This is honest failure propagation,
    not the separately required R08 raw-occurrence retention implementation.
    """
    solver = Mock(wraps=worker.default_core_solver())
    monkeypatch.setattr(worker, "default_core_solver", lambda: solver)

    def order(graph):
        if stage == "graph":
            with patch.object(ordering, "time", Clock(1.0)):
                return ordering.canonical_order(graph)
        return ordering.canonical_order(graph, T=ordering.Duration(10))

    def sliced(finding, graph):
        with patch.object(ordering, "time", Clock(1.0)):
            return fingerprint.compute_slice_fingerprint(finding, graph)

    monkeypatch.setattr(worker, "canonical_order", order)
    monkeypatch.setattr(worker, "compute_slice_fingerprint", sliced)
    graph = _graph("strong", "strong")
    job = good_job()
    objects = InMemoryObjectStore()
    _store_graph(objects, job, graph)
    session = _RecordingFindingsSession()
    signer = Mock(wraps=SoftwareKMSSigner())
    provenance = Mock(wraps=InMemoryProvenanceStore())
    kwargs = {
        "object_store": objects,
        "findings_session": session,
        "signer": signer,
        "kms_key_arn": _KMS_KEY_ARN,
        "registry": _real_registry(),
        "provenance_store": provenance,
    }
    if caller == "queue":
        queue = StandardQueue(name="canonical-deadline-test")
        queue.send(_message_body(job, org_id=_ORG_ID, scm_provider="github"), str(job.job_id))
        received = queue.receive()
        assert received is not None and queue.ready_depth == 0
        ack = Mock(wraps=queue.ack)
        fail = Mock(wraps=queue.fail)
        monkeypatch.setattr(queue, "ack", ack)
        monkeypatch.setattr(queue, "fail", fail)
        assert handle_queue_message(received, queue=queue, **kwargs) is None
        ack.assert_not_called()
        fail.assert_called_once_with(received.receipt_handle)
        assert queue.ready_depth == 1 and queue.dlq_messages == []
        retry = queue.receive()
        assert retry is not None and retry.message.receive_count == 2
        assert retry.message.body == received.message.body
    else:
        with pytest.raises(ordering.CanonicalizationDeadlineExceeded):
            if caller == "direct":
                worker.run_detector(core_injection_detector(), graph, job)
            else:
                run_detector_job(job, org_id=_ORG_ID, scm_provider="github", **kwargs)
    assert solver.solve.call_count == (0 if stage == "graph" else 1)
    assert session.added == [] and session.commits == 0
    signer.sign.assert_not_called()
    provenance.append.assert_not_called()
