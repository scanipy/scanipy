"""Hermetic offline fakes for CMP-TRI-03 specs (TST-AC-TRI-03a/b + controls).

No real PostgreSQL, no real AWS. The two in-memory stores below mirror the
``InMemory*Store`` DI discipline of ``tests/tri02_fakes.py`` /
``tests/tri01_fakes.py`` (and the merged CMP-FND-03 / ``services/scan/provenance``
ports). They model the per-customer revalidation / drift persistence whose
PRODUCTION schema is DEFERRED (CLAR-DB-05 -- filed by the orchestrator); no DB
migration is written by CMP-TRI-03.

* :class:`InMemoryCustomerEProcessStore` keys the customer-stream e-process state
  by ``(org_id, spec_version_id)`` (DOC-CMP-TRI-03 §3 -- one per pair).
* :class:`InMemorySpecQuarantineStore` records the per-customer EXCLUSION
  (quarantine) decision and the ``global-unrevalidated -> global-revalidated``
  transition. A quarantine is a DECISION FLAG, not a ``findings`` mutation and not
  a 4th ``spec_provenance`` value (INV-3); the enum stays at its three values and
  never transitions back from ``global-revalidated``.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from services.triage.spec_inference import CustomerEProcessState

SpecProvenance = Literal["global-unrevalidated", "global-revalidated", "customer"]


class InMemoryCustomerEProcessStore:
    """In-memory ``CustomerEProcessState`` keyed by ``(org_id, spec_version_id)``."""

    def __init__(self) -> None:
        self._rows: dict[tuple[UUID, UUID], CustomerEProcessState] = {}

    def get(self, org_id: UUID, spec_version_id: UUID) -> CustomerEProcessState | None:
        return self._rows.get((org_id, spec_version_id))

    def put(self, state: CustomerEProcessState) -> None:
        self._rows[(state.org_id, state.spec_version_id)] = state

    def all_for_org(self, org_id: UUID) -> list[CustomerEProcessState]:
        return [s for (o, _), s in self._rows.items() if o == org_id]


class InMemorySpecQuarantineStore:
    """Records per-customer quarantine (exclusion) + revalidation decisions.

    Quarantine takes precedence and is terminal (a floor breach EXCLUDES the spec
    from the org's future pinned ``S``). The ``spec_provenance`` view starts at
    ``global-unrevalidated`` and transitions only ``-> global-revalidated`` on a
    revalidate-accept; it never transitions back (DOC-CMP-TRI-03 §5.3).
    """

    def __init__(self) -> None:
        self._quarantined: set[tuple[UUID, UUID]] = set()
        self._revalidated: set[tuple[UUID, UUID]] = set()

    def mark_quarantined(self, org_id: UUID, spec_version_id: UUID) -> None:
        self._quarantined.add((org_id, spec_version_id))

    def mark_revalidated(self, org_id: UUID, spec_version_id: UUID) -> None:
        # Never transition back: once revalidated, stays revalidated. (A later
        # drift breach is recorded as a quarantine, not a de-revalidation.)
        self._revalidated.add((org_id, spec_version_id))

    def is_quarantined(self, org_id: UUID, spec_version_id: UUID) -> bool:
        return (org_id, spec_version_id) in self._quarantined

    def spec_provenance_for(self, org_id: UUID, spec_version_id: UUID) -> SpecProvenance:
        if (org_id, spec_version_id) in self._revalidated:
            return "global-revalidated"
        return "global-unrevalidated"
