"""CMP-SNAP-04 — Differential reflection oracle (re-partition MECHANISM).

Implementation contract: ``docs/components/DOC-CMP-SNAP-04.md`` (§3 interface,
§6 algorithm, §7 failure modes, the safe-default note). Cross-cutting refs:
``DOC-PROVENANCE §4`` (re-partition records), ``DOC-PARTITION §5`` (one-way
flip), ``.claude/rules/02-provenance.md`` + ``.claude/rules/05-determinism.md``.

This module implements the **re-partition mechanism only** (the hermetic,
PR-gated half of CMP-SNAP-04). The independent whole-program reflection scanner
that actually *detects* a seeded ``CW-DETECT`` false negative (AC-SNAP-04a) and
the SLA-window measurement (AC-SNAP-04b) are **deferred**: here the oracle
verdict is **injected/pre-supplied** by the caller (``repartition_snapshot``
takes the disagreement as input, ``record_oracle_run`` takes the verdict).

INDEPENDENCE (DOC §6.2 "independent codebase from CW-DETECT", DOC-RUNBOOK §6.3):
a shared bug between the two reflection detectors would defeat the safety net.
For the mechanism this module imports **nothing** from
``services.snapshot.cw_detect`` — not its detection logic, not its
``ReflectionSite`` value type. The reflection-site shape carried on an oracle
run is the local :class:`OracleReflectionSite`; the verdict is data supplied by
the caller, never computed by re-using ``CW-DETECT``'s code path. The real
independent scanner (AC-SNAP-04a) is a separate, separately-maintained codebase.

The re-partition write reuses the merged CMP-FND-03 plumbing
(``services.scan.provenance.append_repartition_event``) — correct, append-only,
one-way — rather than re-implementing the signed-chain append.

Persistence is an **injected in-memory store** (DI; mirrors the
``InMemoryProvenanceStore`` of ``tests/fnd03_fakes.py``). The ``snap_oracle_runs``
Alembic migration and the ``provenance_records.repartition_oracle_id`` FK are
**deferred** under the OPEN ``CLAR-DB-03`` (Architect to ratify); no migration
ships here.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

from services.scan.provenance import (
    KMSAsymmetricSigner,
    ProvenanceStore,
    SignatureAlg,
    SignedProvenanceRecord,
    append_repartition_event,
)

# Engines whose findings are in the deterministic-core partition (INV-1 / the
# .claude/rules/05-determinism.md partition rule). Only these are ever at risk
# of a core -> oracle re-partition.
CORE_ENGINES: frozenset[str] = frozenset({"ifds", "ide"})

OracleVerdict = Literal["closed-world", "not-closed-world"]


@dataclass(frozen=True)
class OracleReflectionSite:
    """A reflection site reported by the differential oracle.

    Deliberately **local** to this module (not imported from
    ``services.snapshot.cw_detect``) so the oracle's value vocabulary shares no
    edge with ``CW-DETECT`` (DOC §6.2 independence). For the mechanism PR these
    are injected data on an oracle run, never computed here.
    """

    rel_path: str
    line: int
    detail: str


@dataclass(frozen=True)
class OracleRunRecord:
    """One ``snap_oracle_runs`` row (DOC §3.2) — one per run, agreement or not.

    ``agreed`` mirrors the SQL DDL column (and is ``True`` iff
    ``oracle_verdict == 'closed-world'``). On agreement this row is the
    "no-disagreement certificate" the Attestor relies on downstream; it flips
    nothing. ``run_id`` becomes the ``repartition_oracle_id`` on every
    re-partition row this run produces.
    """

    run_id: uuid.UUID
    snapshot_id: uuid.UUID
    oracle_version: str
    cw_detect_version: str
    oracle_verdict: OracleVerdict
    agreed: bool
    reflection_sites: tuple[OracleReflectionSite, ...]
    started_at: str
    completed_at: str
    reason: str | None = None


@runtime_checkable
class OracleRunStore(Protocol):
    """Injected in-memory persistence port for ``snap_oracle_runs`` rows.

    Modelled as append-by-``run_id`` (one row per run). No UPDATE/DELETE — an
    oracle run is recorded once. CLAR-DB-03 (the real table + FK) is OPEN, so
    production wiring is deferred; tests pass :class:`InMemoryOracleRunStore`.
    """

    def append(self, record: OracleRunRecord) -> None: ...

    def get(self, run_id: uuid.UUID) -> OracleRunRecord | None: ...


@runtime_checkable
class RepartitionProvenanceStore(ProvenanceStore, Protocol):
    """``ProvenanceStore`` extended with a by-snapshot query of core findings.

    The FND-03 :class:`~services.scan.provenance.ProvenanceStore` exposes only
    ``append`` / ``get`` / ``children`` (it is keyed by record id and parent
    id). ``repartition_snapshot`` derives its flip set from ``snapshot_id``
    (DOC §6.3), so the store must answer "which ``chain`` records of this
    snapshot are currently ``deterministic-core`` and core-engine?". This is a
    read-only query extension; the store stays append-only. The production SQL
    store answers it with the ``WHERE snapshot_id = … AND record_type='chain'
    AND origin='deterministic-core' AND detector_engine IN ('ifds','ide')``
    predicate of DOC §6.3.
    """

    def core_chain_records_for_snapshot(
        self, snapshot_id: uuid.UUID
    ) -> list[SignedProvenanceRecord]: ...


@dataclass
class RepartitionResult:
    """Outcome of a :func:`repartition_snapshot` call (DOC §3.3)."""

    affected_finding_count: int
    new_repartition_record_ids: list[uuid.UUID] = field(default_factory=list)
    notified_customers: list[uuid.UUID] = field(default_factory=list)
    already_repartitioned: int = 0


def _is_core_at_risk(record: SignedProvenanceRecord) -> bool:
    """Is this a ``chain`` finding currently in the core partition + core engine?

    The exact flip-set predicate of DOC §6.3: ``record_type == 'chain'`` AND
    ``origin == 'deterministic-core'`` AND ``detector_engine ∈ {ifds, ide}``.
    Oracle-passthrough findings and non-core engines are NEVER touched.
    """
    r = record.record
    return (
        r.record_type == "chain"
        and r.origin == "deterministic-core"
        and r.detector_engine in CORE_ENGINES
    )


def _already_repartitioned(
    chain_record_id: uuid.UUID, *, provenance_store: ProvenanceStore
) -> bool:
    """True iff a ``record_type='repartition'`` child already exists.

    Idempotency guard (INV-1 "exactly once" / at-least-once SQS redelivery): a
    second ``repartition_snapshot`` call must not double-flip an already
    re-partitioned finding. The append-only chain makes the prior flip
    observable as a child row — we never inspect a mutable ``origin``.
    """
    return any(
        child.record.record_type == "repartition"
        for child in provenance_store.children(chain_record_id)
    )


def effective_origin(
    chain_record: SignedProvenanceRecord, *, provenance_store: ProvenanceStore
) -> str:
    """The live origin of a finding == its original origin unless re-partitioned.

    The re-partition is append-only: the original ``chain`` record is immutable,
    so the live ("findings mirror") origin is *derived* — ``oracle-passthrough``
    iff a ``record_type='repartition'`` child exists, else the stamped origin.
    This is the in-memory analogue of the ``findings`` mirror UPDATE in DOC §6.3
    (no separate mutable table is needed to satisfy INV-1's "mirror reflects the
    new origin").
    """
    if _already_repartitioned(chain_record.record.id, provenance_store=provenance_store):
        return "oracle-passthrough"
    origin = chain_record.record.origin
    return origin if origin is not None else "oracle-passthrough"


def record_oracle_run(
    *,
    snapshot_id: uuid.UUID,
    oracle_verdict: OracleVerdict,
    oracle_version: str,
    cw_detect_version: str,
    started_at: str,
    completed_at: str,
    oracle_run_store: OracleRunStore,
    reflection_sites: tuple[OracleReflectionSite, ...] = (),
    reason: str | None = None,
    run_id: uuid.UUID | None = None,
) -> OracleRunRecord:
    """Persist one ``snap_oracle_runs`` row (agreement OR disagreement) (DOC §6.1 step 5).

    ``agreed = (oracle_verdict == 'closed-world')``. On agreement the row is the
    "no-disagreement certificate" and flips nothing. ``reflection_sites`` must be
    empty on a ``closed-world`` verdict (DOC §3.2). The verdict is **injected**
    (pre-supplied by the caller / the deferred AC-SNAP-04a scanner); this module
    does not compute it from ``CW-DETECT`` or any reflection scan.
    """
    agreed = oracle_verdict == "closed-world"
    if agreed and reflection_sites:
        raise ValueError("a 'closed-world' oracle verdict must carry zero reflection_sites")
    record = OracleRunRecord(
        run_id=run_id if run_id is not None else uuid.uuid4(),
        snapshot_id=snapshot_id,
        oracle_version=oracle_version,
        cw_detect_version=cw_detect_version,
        oracle_verdict=oracle_verdict,
        agreed=agreed,
        reflection_sites=reflection_sites,
        started_at=started_at,
        completed_at=completed_at,
        reason=reason,
    )
    oracle_run_store.append(record)
    return record


def record_safe_default_agreement(
    *,
    snapshot_id: uuid.UUID,
    oracle_version: str,
    cw_detect_version: str,
    started_at: str,
    completed_at: str,
    oracle_run_store: OracleRunStore,
    reason: str = "artifacts-gced",
    run_id: uuid.UUID | None = None,
) -> OracleRunRecord:
    """Safe-default agreement row when the oracle cannot run (DOC §7, §3.4 error contract).

    When the oracle cannot re-evaluate (artifacts GC'd past 90d retention, etc.)
    the **safe default is to leave labels in place** (DOC §"safe-default note"):
    the oracle is a falsifier, not a re-label engine. A false disagreement would
    over-promote findings ``core -> oracle`` — an INV-1 violation in the
    *opposite* direction. So we emit an **agreement** row
    (``oracle_verdict='closed-world'``, ``agreed=True``) and flip nothing.
    """
    return record_oracle_run(
        snapshot_id=snapshot_id,
        oracle_verdict="closed-world",
        oracle_version=oracle_version,
        cw_detect_version=cw_detect_version,
        started_at=started_at,
        completed_at=completed_at,
        oracle_run_store=oracle_run_store,
        reason=reason,
        run_id=run_id,
    )


def repartition_snapshot(
    snapshot_id: uuid.UUID,
    oracle_run_id: uuid.UUID,
    reason: str,
    *,
    provenance_store: RepartitionProvenanceStore,
    signer: KMSAsymmetricSigner,
    signature_alg: SignatureAlg = "RSASSA_PSS_SHA_256",
) -> RepartitionResult:
    """Re-partition every affected core finding of ``snapshot_id`` (DOC §3.3 / §6.3).

    Given a **pre-supplied** oracle disagreement (the verdict is injected — see
    the module docstring's independence note; this function never invokes
    ``CW-DETECT`` or a reflection scan), for every ``deterministic-core`` finding
    of the snapshot whose ``detector_engine ∈ {ifds, ide}`` append a NEW
    ``record_type='repartition'`` provenance row via the merged FND-03
    ``append_repartition_event`` (``origin -> 'oracle-passthrough'``,
    ``parent_record_id -> the original chain record``,
    ``repartition_oracle_id -> oracle_run_id``).

    Properties (DOC §6.3):

    - **append-only** — the parent ``chain`` row is NEVER mutated.
    - **one-way** — every new row is ``oracle-passthrough``; the reverse flip is
      never performed here.
    - **exactly once / idempotent** — a finding already carrying a repartition
      child is skipped, so an at-least-once SQS redelivery (a second call) does
      not double-flip.
    - **scoped** — only ``chain`` / ``deterministic-core`` / core-engine findings
      are in the flip set; oracle-passthrough + non-core-engine findings are
      untouched.
    - ``status`` is never changed (a re-partitioned finding is never dropped).

    The injected store derives the flip set from ``snapshot_id``; the affected
    list is never passed in by the caller (it is a function of the snapshot).
    """
    candidates = provenance_store.core_chain_records_for_snapshot(snapshot_id)

    new_record_ids: list[uuid.UUID] = []
    notified: set[uuid.UUID] = set()
    affected = 0
    already = 0

    for chain in candidates:
        if not _is_core_at_risk(chain):
            # Defensive: the store query already filters, but the predicate is
            # re-checked so a looser store impl cannot widen the flip set.
            continue
        if _already_repartitioned(chain.record.id, provenance_store=provenance_store):
            already += 1
            continue
        signed = append_repartition_event(
            parent_record_id=chain.record.id,
            repartition_oracle_id=oracle_run_id,
            repartition_reason=reason,
            store=provenance_store,
            signer=signer,
            signature_alg=signature_alg,
        )
        new_record_ids.append(signed.record.id)
        notified.add(chain.record.org_id)
        affected += 1

    return RepartitionResult(
        affected_finding_count=affected,
        new_repartition_record_ids=new_record_ids,
        notified_customers=sorted(notified),
        already_repartitioned=already,
    )


class InMemoryOracleRunStore:
    """Hermetic in-memory :class:`OracleRunStore` (mirrors ``InMemoryProvenanceStore``).

    Append-by-``run_id``; one row per run. No UPDATE/DELETE — the
    ``snap_oracle_runs`` table is append-only. Used by tests and as the DI
    stand-in while CLAR-DB-03 (the real table) is OPEN.
    """

    def __init__(self) -> None:
        self._rows: dict[uuid.UUID, OracleRunRecord] = {}

    def append(self, record: OracleRunRecord) -> None:
        if record.run_id in self._rows:
            raise AssertionError(f"duplicate oracle run id {record.run_id}")
        self._rows[record.run_id] = record

    def get(self, run_id: uuid.UUID) -> OracleRunRecord | None:
        return self._rows.get(run_id)

    def all_runs(self) -> list[OracleRunRecord]:
        return list(self._rows.values())


__all__ = [
    "CORE_ENGINES",
    "InMemoryOracleRunStore",
    "OracleReflectionSite",
    "OracleRunRecord",
    "OracleRunStore",
    "OracleVerdict",
    "RepartitionProvenanceStore",
    "RepartitionResult",
    "effective_origin",
    "record_oracle_run",
    "record_safe_default_agreement",
    "repartition_snapshot",
]
