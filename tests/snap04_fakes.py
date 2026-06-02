"""Hermetic offline fakes for CMP-SNAP-04 (re-partition mechanism) specs.

Builds on ``tests/fnd03_fakes.py`` (the FND-03 ``SoftwareKMSSigner`` +
``InMemoryProvenanceStore``) — no real AWS, no PostgreSQL, no ``snap_oracle_runs``
table (CLAR-DB-03 OPEN). The single addition here is
:class:`RepartitionTestStore`, an ``InMemoryProvenanceStore`` extended with the
by-snapshot query (``core_chain_records_for_snapshot``) that
``repartition_snapshot`` needs to derive its flip set from a ``snapshot_id``
(the FND-03 store is keyed only by record id / parent id).

INDEPENDENCE: these fakes import nothing from ``services.snapshot.cw_detect``;
the oracle verdict in every test is injected, never computed.
"""

from __future__ import annotations

import uuid

from analysis.ordering import CPG_ORDER_HASH_ANNOTATION
from services.scan.provenance import (
    DetectorEngine,
    Origin,
    ProvenanceRecord,
    SignedProvenanceRecord,
)
from tests.fnd03_fakes import InMemoryProvenanceStore


def make_snapshot_chain_record(
    *,
    snapshot_id: uuid.UUID,
    org_id: uuid.UUID | None = None,
    origin: Origin = "deterministic-core",
    detector_engine: DetectorEngine = "ifds",
) -> ProvenanceRecord:
    """A ``record_type='chain'`` finding record bound to ``snapshot_id``.

    Mirrors ``tests/fnd03_fakes.make_chain_record`` but parametrises the
    ``snapshot_id`` (so several findings can share one snapshot), the ``origin``
    and the ``detector_engine`` — the three fields the SNAP-04 flip-set predicate
    keys on (DOC-CMP-SNAP-04 §6.3).
    """
    return ProvenanceRecord(
        id=uuid.uuid4(),
        parent_record_id=None,
        record_type="chain",
        scan_id=uuid.uuid4(),
        finding_id=uuid.uuid4(),
        org_id=org_id if org_id is not None else uuid.uuid4(),
        codebase_id=uuid.uuid4(),
        commit_sha="a" * 40,
        scm_provider="github",
        snapshot_id=snapshot_id,
        snapshot_digest="sha256:" + ("c" * 64),  # type: ignore[arg-type]
        precondition_status="closed-world",
        S_version="1.2.3",  # type: ignore[arg-type]
        env_digest="sha256:" + ("b" * 64),  # type: ignore[arg-type]
        cpg_order_hash=b"\x00" * 32,  # type: ignore[arg-type]
        cpg_order_hash_annotation=CPG_ORDER_HASH_ANNOTATION,
        fingerprint_class="strong",
        witness_blob_uri="s3://witness/abc.json",
        slice_fingerprint=b"\x01" * 32,  # type: ignore[arg-type]
        rule_id="R1",
        spec_id="S1",
        detector_id="det-injection",
        detector_engine=detector_engine,
        sarif_hash=None,
        origin=origin,
        determinism_partition=origin,
        repartition_reason=None,
        repartition_oracle_id=None,
        claim_label="CONDITIONAL_THEOREM" if origin == "deterministic-core" else "EMPIRICAL",
    )


class RepartitionTestStore(InMemoryProvenanceStore):
    """``InMemoryProvenanceStore`` + the SNAP-04 by-snapshot core-finding query.

    Implements the read-only extension of DOC-CMP-SNAP-04 §6.3:
    ``record_type='chain' AND origin='deterministic-core' AND
    detector_engine IN ('ifds','ide')`` filtered to one ``snapshot_id``. The
    store stays append-only (inherited ``append`` raises on duplicate id; there
    is no UPDATE/DELETE), so re-partition is by appended child row, never a
    parent mutation.
    """

    def core_chain_records_for_snapshot(
        self, snapshot_id: uuid.UUID
    ) -> list[SignedProvenanceRecord]:
        out: list[SignedProvenanceRecord] = []
        for signed in self._rows.values():
            r = signed.record
            if (
                r.record_type == "chain"
                and r.snapshot_id == snapshot_id
                and r.origin == "deterministic-core"
                and r.detector_engine in ("ifds", "ide")
            ):
                out.append(signed)
        return out
