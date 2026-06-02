"""Hermetic offline fakes for CMP-TRI-02 specs (TST-AC-TRI-02a/b/c, TST-INV-*-TRI-02).

No real PostgreSQL, no real AWS. The KMS signer + provenance store are reused
verbatim from ``tests/fnd03_fakes.py`` (the merged CMP-FND-03 software signer /
append-only in-memory ``provenance_records``). The two spec stores below mirror
the same ``InMemory*Store`` discipline (DI pattern of
``services/scan/provenance`` and ``tests/tri01_fakes.py``):

* :class:`InMemorySpecVersionStore` is an **append-only** ``spec_versions`` table
  (DOC-DB §4.9): ``insert`` raises if a row id already exists and exposes NO
  ``update`` / ``delete`` method -- the structural mirror of the no-UPDATE/DELETE
  grants on ``spec_versions`` (INV-2: specs are version-pinned).
* :class:`InMemoryProposedSpecStore` records the ``decision`` flip + FK so a spec
  can assert ``proposed_specs.decision = 'accepted'`` with the FK to the new
  ``spec_versions`` row (DOC-DB §4.8).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from uuid import UUID

from services.triage.spec_inference import SpecVersionRow


class InMemorySpecVersionStore:
    """Append-only in-memory ``spec_versions`` (keyed by row ``id``).

    No ``update`` / ``delete`` method -- modelling the absence of UPDATE/DELETE
    grants outside ``scanipy_triage_spec`` (INV-2 append-only). A duplicate row
    id raises (PK constraint). ``all_for_class`` filters by the global-singleton
    semver namespace; this in-memory fake keys class membership off the spec_set
    so the semver bumper can find the highest existing version.
    """

    def __init__(self) -> None:
        self._rows: dict[UUID, SpecVersionRow] = {}

    def all(self) -> list[SpecVersionRow]:
        return list(self._rows.values())

    def all_for_class(self, detector_class: str, *, scope: str = "global") -> list[SpecVersionRow]:
        return [
            r
            for r in self._rows.values()
            if r.scope == scope and r.spec_set.get("class") == detector_class
        ]

    def insert(self, row: SpecVersionRow) -> None:
        if row.id in self._rows:
            # Append-only: a row id is written exactly once (PK constraint).
            raise AssertionError(f"duplicate spec_versions row id {row.id}")
        self._rows[row.id] = row

    # No update()/delete(): spec_versions is append-only (INV-2). The absence of
    # these methods is the application-layer mirror of the revoked grants.


class InMemoryProposedSpecStore:
    """Records ``proposed_specs`` decision flips (DOC-DB §4.8).

    Tracks the ``decision`` and the ``accepted_as_spec_version_id`` FK so a spec
    can assert the candidate flipped to ``'accepted'`` with the FK to the new
    ``spec_versions`` row.
    """

    def __init__(self) -> None:
        self.decision: str = "pending"
        self.accepted_as_spec_version_id: UUID | None = None
        self.decided_at: datetime | None = None
        self.quarantined: bool = False

    def mark_accepted(
        self, spec_id: UUID, *, accepted_as_spec_version_id: UUID, decided_at: datetime
    ) -> None:
        self.decision = "accepted"
        self.accepted_as_spec_version_id = accepted_as_spec_version_id
        self.decided_at = decided_at

    def mark_quarantined(self, spec_id: UUID) -> None:
        self.decision = "quarantined"
        self.quarantined = True


def new_uuid() -> UUID:
    return uuid.uuid4()
