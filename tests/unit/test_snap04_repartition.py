"""CMP-SNAP-04 re-partition MECHANISM — hermetic, PR-gating unit specs.

These are the CI-GATING copies of the SNAP-04 mechanism invariants. The
real gating selector is ``tests/unit/ -m unit`` (directory-scoped — see
``.github/workflows/ci.yml`` "Run unit tests"), so the gate-bearing tests must
live in ``tests/unit/`` and carry ``@pytest.mark.unit``. They additionally carry
``@pytest.mark.invariant`` (the WBS kind tag). The de-skipped narrative copies in
``tests/integration/test_snap_specs.py`` (``test_snap_04c`` /
``test_inv_1_snap_04``) satisfy the literal stub contract but run in no gating
job (wrong directory + ``invariant`` marker, and the integration job is
informational); the gate lives here.

Hermetic: in-memory ``RepartitionTestStore`` + software ``SoftwareKMSSigner``
(``tests/snap04_fakes.py`` / ``tests/fnd03_fakes.py``). No DB, no AWS, no
``snap_oracle_runs`` table (CLAR-DB-03 OPEN). The oracle verdict is **injected**
(pre-supplied) in every test; nothing here imports or calls
``services.snapshot.cw_detect`` (independence — DOC-CMP-SNAP-04 §6.2).

Covers:
  - TST-AC-SNAP-04c   [INVARIANT] — every re-partition event written to provenance
  - TST-INV-1-SNAP-04 [INVARIANT] — flip set is exactly core/{ifds,ide}; one-way;
                                     idempotent (no double-flip on redelivery)
  - (added) agreement NEGATIVE CONTROL — over-flip guard a re-partition-everything
    oracle FAILS; plus the GC'd-artifacts safe-default agreement row.
"""

from __future__ import annotations

import uuid

import pytest

from services.scan.provenance import DetectorEngine, SignedProvenanceRecord, sign_provenance
from services.snapshot import (
    InMemoryOracleRunStore,
    effective_origin,
    record_oracle_run,
    record_safe_default_agreement,
    repartition_snapshot,
)
from tests.fnd03_fakes import SoftwareKMSSigner
from tests.snap04_fakes import RepartitionTestStore, make_snapshot_chain_record

_KMS_ARN = "arn:aws:kms:us-east-1:000000000000:key/snap04-test"


def _seed(store: RepartitionTestStore, signer: SoftwareKMSSigner, record: object) -> uuid.UUID:
    """Sign + append a chain record to the append-only store; return its id."""
    signed = sign_provenance(record, signer=signer, kms_key_arn=_KMS_ARN, store=store)  # type: ignore[arg-type]
    return signed.record.id


def _get(store: RepartitionTestStore, record_id: uuid.UUID) -> SignedProvenanceRecord:
    """Fetch a seeded record, narrowing the store's ``Optional`` return for mypy."""
    signed = store.get(record_id)
    assert signed is not None
    return signed


@pytest.mark.unit
@pytest.mark.invariant
def test_snap_04c_every_repartition_event_written_to_provenance() -> None:
    """TST-AC-SNAP-04c — one repartition row per affected finding, fully linked.

    A pre-supplied disagreement over a snapshot with A=3 core/{ifds,ide}
    findings produces EXACTLY one ``record_type='repartition'`` row per affected
    finding, each linked via ``parent_record_id`` + ``repartition_oracle_id``;
    the original ``chain`` record is NEVER updated (append-only). The
    ``snap_oracle_runs`` row exists with ``agreed=false``.
    """
    store = RepartitionTestStore()
    signer = SoftwareKMSSigner()
    oracle_runs = InMemoryOracleRunStore()
    snapshot_id = uuid.uuid4()

    engines: tuple[DetectorEngine, ...] = ("ifds", "ide", "ifds")
    chain_ids = [
        _seed(
            store,
            signer,
            make_snapshot_chain_record(snapshot_id=snapshot_id, detector_engine=engine),
        )
        for engine in engines
    ]
    # The original signed bytes — to prove the parent is never mutated.
    parents_before = {cid: store.get(cid) for cid in chain_ids}

    run = record_oracle_run(
        snapshot_id=snapshot_id,
        oracle_verdict="not-closed-world",
        oracle_version="oracle-1.0.0",
        cw_detect_version="cw-1.0.0",
        started_at="2026-06-01T00:00:00+00:00",
        completed_at="2026-06-01T00:05:00+00:00",
        oracle_run_store=oracle_runs,
    )
    assert run.agreed is False  # disagreement → INV-1 hand-off

    result = repartition_snapshot(
        snapshot_id,
        run.run_id,
        reason="oracle-found-spring-proxy",
        provenance_store=store,
        signer=signer,
    )

    assert result.affected_finding_count == 3
    assert len(result.new_repartition_record_ids) == 3

    for cid in chain_ids:
        children = store.children(cid)
        repart = [c for c in children if c.record.record_type == "repartition"]
        # EXACTLY one repartition row per affected finding.
        assert len(repart) == 1
        row = repart[0].record
        assert row.parent_record_id == cid  # linked to the chain record
        assert row.repartition_oracle_id == run.run_id  # linked to the oracle run
        assert row.origin == "oracle-passthrough"
        assert row.repartition_reason == "oracle-found-spring-proxy"
        # Append-only: the parent's signed record is byte-identical (immutable).
        assert store.get(cid) == parents_before[cid]


@pytest.mark.unit
@pytest.mark.invariant
def test_inv_1_snap_04_flip_set_is_exactly_core_and_idempotent() -> None:
    """TST-INV-1-SNAP-04 — flip set = exactly core/{ifds,ide}; one-way; idempotent.

    A snapshot mixes core/{ifds,ide}, an oracle-passthrough finding, and a
    core-class but non-core-engine (semgrep) finding. The flip set is EXACTLY
    the two core/{ifds,ide} findings. A SECOND ``repartition_snapshot`` call (SQS
    at-least-once redelivery) flips NOTHING new (idempotent). The reverse flip
    (oracle→core) never occurs; the original record is immutable.
    """
    store = RepartitionTestStore()
    signer = SoftwareKMSSigner()
    oracle_runs = InMemoryOracleRunStore()
    snapshot_id = uuid.uuid4()

    core_ifds = _seed(
        store, signer, make_snapshot_chain_record(snapshot_id=snapshot_id, detector_engine="ifds")
    )
    core_ide = _seed(
        store, signer, make_snapshot_chain_record(snapshot_id=snapshot_id, detector_engine="ide")
    )
    oracle_pt = _seed(
        store,
        signer,
        make_snapshot_chain_record(
            snapshot_id=snapshot_id, origin="oracle-passthrough", detector_engine="semgrep"
        ),
    )
    non_core_engine = _seed(
        store,
        signer,
        make_snapshot_chain_record(
            snapshot_id=snapshot_id, origin="deterministic-core", detector_engine="cpg-query"
        ),
    )

    run = record_oracle_run(
        snapshot_id=snapshot_id,
        oracle_verdict="not-closed-world",
        oracle_version="oracle-1.0.0",
        cw_detect_version="cw-1.0.0",
        started_at="2026-06-01T00:00:00+00:00",
        completed_at="2026-06-01T00:05:00+00:00",
        oracle_run_store=oracle_runs,
    )

    first = repartition_snapshot(
        snapshot_id, run.run_id, reason="oracle-disagreed", provenance_store=store, signer=signer
    )

    # Flip set = EXACTLY the two core/{ifds,ide} findings.
    assert first.affected_finding_count == 2
    assert effective_origin(_get(store, core_ifds), provenance_store=store) == "oracle-passthrough"
    assert effective_origin(_get(store, core_ide), provenance_store=store) == "oracle-passthrough"
    # oracle-passthrough finding untouched (no repartition child).
    assert effective_origin(_get(store, oracle_pt), provenance_store=store) == "oracle-passthrough"
    assert not store.children(oracle_pt)
    # core-class but NON-core-engine finding untouched.
    assert (
        effective_origin(_get(store, non_core_engine), provenance_store=store)
        == "deterministic-core"
    )
    assert not store.children(non_core_engine)

    # Idempotency: a SECOND call (SQS redelivery) double-flips nothing.
    second = repartition_snapshot(
        snapshot_id, run.run_id, reason="oracle-disagreed", provenance_store=store, signer=signer
    )
    assert second.affected_finding_count == 0
    assert second.already_repartitioned == 2
    # Exactly one repartition child per affected finding — never two.
    assert len(store.children(core_ifds)) == 1
    assert len(store.children(core_ide)) == 1

    # One-way: no repartition row ever carries origin 'deterministic-core'.
    for cid in (core_ifds, core_ide):
        for child in store.children(cid):
            assert child.record.origin == "oracle-passthrough"


@pytest.mark.unit
@pytest.mark.invariant
def test_agreement_negative_control_flips_nothing() -> None:
    """Agreement NEGATIVE CONTROL — over-flip guard (a re-partition-everything oracle FAILS).

    On agreement (oracle_verdict='closed-world', no FN): a ``snap_oracle_runs``
    row with ``agreed=true`` AND ZERO repartition records; every finding keeps
    ``origin='deterministic-core'``. A re-partition-everything oracle would flip
    these and fail this test.
    """
    store = RepartitionTestStore()
    signer = SoftwareKMSSigner()
    oracle_runs = InMemoryOracleRunStore()
    snapshot_id = uuid.uuid4()

    chain_ids = [
        _seed(store, signer, make_snapshot_chain_record(snapshot_id=snapshot_id)) for _ in range(3)
    ]

    run = record_oracle_run(
        snapshot_id=snapshot_id,
        oracle_verdict="closed-world",  # agreement — no disagreement asserted
        oracle_version="oracle-1.0.0",
        cw_detect_version="cw-1.0.0",
        started_at="2026-06-01T00:00:00+00:00",
        completed_at="2026-06-01T00:05:00+00:00",
        oracle_run_store=oracle_runs,
    )

    # The "no-disagreement certificate": agreed=true, recorded, flips nothing.
    assert run.agreed is True
    assert oracle_runs.get(run.run_id) is run
    assert run.reflection_sites == ()

    # ZERO repartition records; every finding keeps its core origin.
    for cid in chain_ids:
        assert store.children(cid) == []
        assert effective_origin(_get(store, cid), provenance_store=store) == "deterministic-core"


@pytest.mark.unit
def test_agreement_run_rejects_reflection_sites() -> None:
    """A 'closed-world' (agreement) verdict must carry zero reflection sites (DOC §3.2)."""
    from services.snapshot import OracleReflectionSite

    oracle_runs = InMemoryOracleRunStore()
    with pytest.raises(ValueError, match="zero reflection_sites"):
        record_oracle_run(
            snapshot_id=uuid.uuid4(),
            oracle_verdict="closed-world",
            oracle_version="oracle-1.0.0",
            cw_detect_version="cw-1.0.0",
            started_at="2026-06-01T00:00:00+00:00",
            completed_at="2026-06-01T00:05:00+00:00",
            oracle_run_store=oracle_runs,
            reflection_sites=(OracleReflectionSite("X.java", 42, "Class.forName"),),
        )


@pytest.mark.unit
@pytest.mark.invariant
def test_safe_default_gced_artifacts_emits_agreement_and_flips_nothing() -> None:
    """Safe-default — GC'd artifacts → agreement row (no flip).

    When the oracle cannot run (artifacts GC'd past retention) the safe default
    is an AGREEMENT row (``oracle_verdict='closed-world'``, ``agreed=true``,
    ``reason='artifacts-gced'``) and ZERO flips — over-flipping would be an INV-1
    violation in the opposite direction (DOC-CMP-SNAP-04 §7 / §3.4).
    """
    store = RepartitionTestStore()
    signer = SoftwareKMSSigner()
    oracle_runs = InMemoryOracleRunStore()
    snapshot_id = uuid.uuid4()

    cid = _seed(store, signer, make_snapshot_chain_record(snapshot_id=snapshot_id))

    run = record_safe_default_agreement(
        snapshot_id=snapshot_id,
        oracle_version="oracle-1.0.0",
        cw_detect_version="cw-1.0.0",
        started_at="2026-06-01T00:00:00+00:00",
        completed_at="2026-06-01T00:00:01+00:00",
        oracle_run_store=oracle_runs,
    )

    assert run.agreed is True
    assert run.oracle_verdict == "closed-world"
    assert run.reason == "artifacts-gced"
    # No flip.
    assert store.children(cid) == []
    assert effective_origin(_get(store, cid), provenance_store=store) == "deterministic-core"
