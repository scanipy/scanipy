"""R09 producer/consumer contract and compatibility falsifiers.

The four-way matrix injects only producer *verdicts*, using real graph/slice
digest calculations and the real worker, solver, emitter, row and signer paths.
It tests propagation, not the correctness of the canonicalization algorithms.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
from types import SimpleNamespace
from uuid import UUID

import pytest

from analysis.artifact_identity import (
    ANNOTATION,
    GRAPH_V2,
    SLICE_V2,
    ArtifactIdentity,
    has_strong_v2_artifact_identities,
    identities_from_finding,
    identity_metadata,
    validate_identity_metadata,
)
from analysis.sarif.canonical_emit import InvariantViolation, normalize, validate_sarif_210
from services.scan import worker
from services.scan.detector_worker import run_detector_job
from services.scan.provenance import (
    canonical_record_bytes,
    export_auditor_record,
    sign_provenance,
    verify_chain,
)
from services.substrate.object_store import InMemoryObjectStore
from tests.fnd01_fakes import ENV_DIGEST, S_VERSION, make_finding
from tests.fnd03_fakes import InMemoryProvenanceStore, SoftwareKMSSigner, make_chain_record
from tests.orch03_fakes import core_injection_detector, good_job, injection_taint_cpg
from tests.unit.test_detector_worker_specs import (
    _KMS_KEY_ARN,
    _ORG_ID,
    _real_registry,
    _RecordingFindingsSession,
    _seed_cpg_artifact,
)
from tests.unit.test_oracle_attestor import ONE_FINDING, SequenceInvoker, _runner

pytestmark = pytest.mark.unit


def _producers(monkeypatch, graph_class, slice_class):
    real_order = worker.canonical_order
    real_slice = worker.compute_slice_fingerprint

    def order(*args, **kwargs):
        result = real_order(*args, **kwargs)
        return SimpleNamespace(
            cpg_order_hash=result.cpg_order_hash,
            fingerprint_class=graph_class,
            identity_namespace=GRAPH_V2,
        )

    def sliced(*args, **kwargs):
        result = real_slice(*args, **kwargs)
        return SimpleNamespace(
            slice_fingerprint=result.slice_fingerprint,
            fingerprint_class=slice_class,
            identity_namespace=SLICE_V2
            if slice_class == "strong"
            else "scanipy-witness-edge-sequence/1",
        )

    monkeypatch.setattr(worker, "canonical_order", order)
    monkeypatch.setattr(worker, "compute_slice_fingerprint", sliced)


@pytest.mark.parametrize("graph_class", ["strong", "weak"])
@pytest.mark.parametrize("slice_class", ["strong", "weak"])
def test_four_way_worker_sarif_store_and_signed_record(monkeypatch, graph_class, slice_class):
    _producers(monkeypatch, graph_class, slice_class)
    job = good_job()
    objects = InMemoryObjectStore()
    _seed_cpg_artifact(objects, job, org_id=_ORG_ID)
    session = _RecordingFindingsSession()
    signer = SoftwareKMSSigner()
    provenance_store = InMemoryProvenanceStore()
    result = run_detector_job(
        job,
        org_id=_ORG_ID,
        scm_provider="github",
        object_store=objects,
        findings_session=session,
        signer=signer,
        kms_key_arn=_KMS_KEY_ARN,
        registry=_real_registry(),
        provenance_store=provenance_store,
    )
    assert result.findings and len(result.findings) == len(result.signed_records)
    assert len(session.added) == len(result.findings)
    log = worker.emit_sarif(set(result.findings), job)
    assert validate_sarif_210(log.canonical_bytes) == []
    findings = json.loads(log.canonical_bytes)["runs"][0]["results"]
    for f, row, signed, sarif in zip(
        result.findings, session.added, result.signed_records, findings, strict=True
    ):
        assert f.origin == row.origin == "deterministic-core"
        assert row.fingerprint_class is None
        assert f.cpg_order_class == row.cpg_order_class == graph_class
        assert f.slice_fingerprint_class == row.slice_fingerprint_class == slice_class
        props = sarif["properties"]
        metadata = props["scanipy.identity"]
        assert "scanipy.fingerprint_class" not in props
        assert metadata["cpg_order"]["fingerprint_class"] == graph_class
        assert metadata["slice"]["fingerprint_class"] == slice_class
        assert metadata["slice"]["annotation"] == metadata["cpg_order"]["annotation"] == ANNOTATION
        eligible = graph_class == slice_class == "strong"
        assert has_strong_v2_artifact_identities(f) is eligible
        assert bool(sarif["fingerprints"]) is eligible
        assert signed.record.record_schema_version == 2
        assert signed.record.fingerprint_class is None
        assert signed.record.artifact_identity == metadata
        assert verify_chain(signed, signer=signer) == "VERIFIED"
        exported = export_auditor_record(signed.record.id, store=provenance_store)
        assert exported["artifact_identity"] == metadata
        assert "fingerprint_class" not in exported
        tampered = copy.deepcopy(metadata)
        tampered["slice"]["fingerprint_class"] = "weak" if slice_class == "strong" else "strong"
        changed = dataclasses.replace(signed.record, artifact_identity=tampered)
        assert (
            verify_chain(dataclasses.replace(signed, record=changed), signer=signer) == "TAMPERED"
        )


def test_real_results_keep_their_namespaces_and_no_legacy_promotion():
    job = good_job()
    found = worker.run_detector(core_injection_detector(), injection_taint_cpg(), job)
    assert found
    for f in found:
        graph, sliced = identities_from_finding(f)
        assert graph.status == sliced.status == "completed"
        assert graph.namespace and sliced.namespace
        if graph.namespace != GRAPH_V2 or sliced.namespace != SLICE_V2:
            assert not has_strong_v2_artifact_identities(f)
            assert (
                json.loads(worker.emit_sarif({f}, job).canonical_bytes)["runs"][0]["results"][0][
                    "fingerprints"
                ]
                == {}
            )


def test_legacy_signed_bytes_do_not_gain_new_fields_or_inferred_classes():
    record = make_chain_record()
    old_payload = {}
    for field in dataclasses.fields(record):
        if field.name in {"record_schema_version", "artifact_identity"}:
            continue
        value = getattr(record, field.name)
        old_payload[field.name] = (
            value.hex()
            if isinstance(value, bytes)
            else str(value)
            if isinstance(value, UUID)
            else value
        )
    old_bytes = json.dumps(old_payload, sort_keys=True, separators=(",", ":")).encode()
    assert canonical_record_bytes(record) == old_bytes
    graph, sliced = identities_from_finding(record)
    assert graph.fingerprint_class is sliced.fingerprint_class is None
    assert graph.status == sliced.status == "legacy-ambiguous"
    assert not has_strong_v2_artifact_identities(record)
    signer = SoftwareKMSSigner()
    signed = sign_provenance(record, signer=signer, kms_key_arn=_KMS_KEY_ARN)
    assert signed.canonical_bytes == old_bytes
    assert verify_chain(signed, signer=signer) == "VERIFIED"
    with pytest.raises(ValueError, match="unsigned"):
        canonical_record_bytes(
            dataclasses.replace(record, artifact_identity=identity_metadata(record))
        )


def test_v1_signature_input_and_sarif_match_pre_migration_checksums():
    # Checksums captured from unchanged base 940d440, not recomputed expectations.
    record = make_chain_record()
    record = dataclasses.replace(
        record,
        **{
            field.name: UUID(int=42)
            for field in dataclasses.fields(record)
            if isinstance(getattr(record, field.name), UUID)
        },
    )
    # pragma: allowlist nextline secret
    expected_record_hash = "80286e1340ddd13544872cf96b75c4245915b54f9d44901492bc00636e30bc2a"
    assert hashlib.sha256(canonical_record_bytes(record)).hexdigest() == expected_record_hash
    log = normalize(
        frozenset({make_finding()}),
        scan_id=UUID(int=1),
        snapshot_id=UUID(int=2),
        codebase_id=UUID(int=3),
        commit_sha="a" * 40,
        S_version=S_VERSION,
        env_digest=ENV_DIGEST,
        precondition_status="closed-world",
        llm_triage_flag=False,
    )
    # pragma: allowlist nextline secret
    expected_sarif_hash = "d6fce0db36b454b60fbae752c176ec1ccb7bdfb53db644b188f88edd870c9ff5"
    assert log.sarif_hash == expected_sarif_hash


def test_cpgless_oracle_has_explicit_absence_and_distinct_content_identity():
    runner = _runner(SequenceInvoker(ONE_FINDING), cpg_order_hash=None, precondition_status=None)
    log = runner.run(UUID(int=7))
    assert validate_sarif_210(log.canonical_bytes) == []
    doc = json.loads(log.canonical_bytes)
    assert doc["runs"][0]["results"] == []
    result = doc["runs"][1]["results"][0]
    props = result["properties"]
    assert props["scanipy.origin"] == "oracle-passthrough"
    assert result["fingerprints"] == {}
    assert props["scanipy.precondition_status"] is None
    assert props["scanipy.precondition_applicability"] == "not-applicable"
    graph, sliced = validate_identity_metadata(props["scanipy.identity"])
    assert graph == sliced == ArtifactIdentity("not-applicable")
    oracle = props["scanipy.oracle_native_identity"]
    assert len(oracle["digest"]) == 64 and oracle["scope"] == "same-source-only"


def test_cpgless_oracle_signed_record_has_no_fabricated_graph_or_slice():
    metadata = {
        "schema_version": 2,
        "cpg_order": ArtifactIdentity("not-applicable").to_dict(),
        "slice": ArtifactIdentity("not-applicable").to_dict(),
    }
    record = dataclasses.replace(
        make_chain_record(origin="oracle-passthrough"),
        record_schema_version=2,
        cpg_order_hash=None,
        slice_fingerprint=None,
        fingerprint_class=None,
        precondition_status=None,
        claim_label="EMPIRICAL",
        artifact_identity=metadata,
    )
    signer = SoftwareKMSSigner()
    signed = sign_provenance(record, signer=signer, kms_key_arn=_KMS_KEY_ARN)
    assert verify_chain(signed, signer=signer) == "VERIFIED"
    with pytest.raises(ValueError, match="core records require"):
        canonical_record_bytes(dataclasses.replace(record, origin="deterministic-core"))
    with pytest.raises(ValueError, match="does not match"):
        canonical_record_bytes(dataclasses.replace(record, slice_fingerprint=b"x" * 32))


@pytest.mark.parametrize(
    "namespace",
    [
        "scanipy-slice-fingerprint/1",
        "scanipy-witness-edge-sequence/1",
        "scanipy-source-witness/2",
        "unknown/9",
    ],
)
def test_legacy_or_weak_namespace_cannot_be_promoted_by_strong_label(namespace):
    finding = make_finding(
        identity_schema_version=2,
        cpg_order_status="completed",
        slice_status="completed",
        cpg_order_class="strong",
        slice_fingerprint_class="strong",
        cpg_order_namespace=GRAPH_V2,
        slice_namespace=namespace,
    )
    assert not has_strong_v2_artifact_identities(finding)


def test_oracle_with_real_graph_does_not_invent_a_slice():
    runner = _runner(
        SequenceInvoker(ONE_FINDING), cpg_order_class="strong", cpg_order_namespace=GRAPH_V2
    )
    result = json.loads(runner.run(UUID(int=7)).canonical_bytes)["runs"][1]["results"][0]
    graph, sliced = validate_identity_metadata(result["properties"]["scanipy.identity"])
    assert graph.fingerprint_class == "strong" and graph.status == "completed"
    assert sliced == ArtifactIdentity("not-applicable")
    assert result["fingerprints"] == {}


@pytest.mark.parametrize("version", [True, "2", 0, 3])
def test_unknown_schema_fails_closed(version):
    finding = SimpleNamespace(identity_schema_version=version)
    with pytest.raises(ValueError):
        identities_from_finding(finding)
    assert not has_strong_v2_artifact_identities(finding)


@pytest.mark.parametrize(
    "status", ["pending", "running", "failed", "not-applicable", "legacy-ambiguous"]
)
def test_status_is_not_a_strength(status):
    with pytest.raises(ValueError):
        ArtifactIdentity(status, fingerprint_class="strong")
    with pytest.raises(ValueError):
        ArtifactIdentity("completed", "a" * 64, status, GRAPH_V2)


def test_missing_slice_evidence_cannot_emit_core(monkeypatch):
    _producers(monkeypatch, "strong", "strong")
    job = good_job()
    findings = worker.run_detector(core_injection_detector(), injection_taint_cpg(), job)
    f = next(iter(findings))
    f.slice_status = "not-applicable"
    f.slice_fingerprint = ""
    f.slice_fingerprint_class = f.slice_namespace = None
    with pytest.raises(InvariantViolation, match="computed graph and slice"):
        worker.emit_sarif(findings, job)


def test_tampered_sarif_flat_class_rejected(monkeypatch):
    _producers(monkeypatch, "strong", "weak")
    job = good_job()
    findings = worker.run_detector(core_injection_detector(), injection_taint_cpg(), job)
    doc = json.loads(worker.emit_sarif(findings, job).canonical_bytes)
    doc["runs"][0]["results"][0]["properties"]["scanipy.slice_fingerprint_class"] = "strong"
    assert validate_sarif_210(json.dumps(doc).encode())
