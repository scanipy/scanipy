"""Hermetic offline fakes for CMP-TRI-01 specs (TST-AC-TRI-01a/b, TST-INV-*-TRI-01).

Mirrors the ``FakeKMS`` pattern of ``tests/unit/test_credential_encryption.py``
and the ``InMemory*Store`` pattern of ``tests/fnd03_fakes.py``: no real Anthropic
API, no PostgreSQL. These fakes are *faithful* application-layer mirrors of the
``DOC-DB §4.14`` grant block, so the unit specs check the same INV-3 contract the
integration specs check against real Postgres, one layer up:

* :class:`RecordingFakeLLM` records its call count so a spec can assert **zero**
  LLM calls when ``LLM_TRIAGE=off`` (TST-AC-TRI-01a).
* :class:`InMemoryFindingsTable` models ``findings`` under the ``scanipy_triage``
  role: it exposes the column-restricted ``SELECT`` projection and **raises**
  ``PermissionError`` on both ``update`` and ``delete`` — modelling
  ``REVOKE ALL ON findings FROM scanipy_triage`` (a role retaining DELETE while
  UPDATE is revoked could still destroy findings, so both must fail).
* :class:`InMemoryTriageScoresStore` is an INSERT-only ``triage_scores`` table; it
  rejects any non-``triage_scores`` target and records every write so a spec can
  assert the written column set ⊆ ``ALLOWED_TRIAGE_COLUMNS`` and that nothing
  targets ``provenance_records`` / ``spec_versions`` / ``proposed_specs``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from decimal import Decimal
from uuid import UUID

from services.triage import (
    FindingView,
    LLMTriageVerdict,
    TriageInput,
)

# Detection-content / INV-anchor / status columns on ``findings`` that the triage
# role must NEVER mutate (INV-1 / INV-3). A triage write whose column set
# intersects this set is a violation. ``S_version`` / ``env_digest`` are
# deliberately excluded: those are legitimately *copied* (read-only) onto the
# triage_scores row as its own INV-2 witness — never written back to ``findings``.
# ``message`` is excluded too: it is in the readable ``FindingView`` projection
# (DOC-DB §4.14 GRANT SELECT), so it is a read column, not a triage write target.
FORBIDDEN_FINDINGS_WRITE_COLUMNS = frozenset(
    {
        "origin",
        "determinism_partition",
        "engine",
        "slice_fingerprint",
        "cpg_order_hash",
        "fingerprint_class",
        "status",
        "spec_provenance",
    }
)


@dataclass
class StoredFinding:
    """A full ``findings`` row as it exists pre-triage, for diffing.

    Only the projection columns are surfaced through the triage read surface; the
    remaining columns model the detection content the triage role cannot see or
    mutate. ``origin`` / ``status`` are called out explicitly because the INV-1 /
    INV-3 specs diff them directly.
    """

    id: UUID
    class_: str
    rule_id: str
    severity: str
    physical_location: dict[str, object]
    message: str
    # Detection content + INV anchors the triage role cannot touch:
    origin: str = "deterministic-core"
    status: str = "open"
    S_version: str = "1.2.3"
    env_digest: str = "sha256:" + ("a" * 64)
    slice_fingerprint: bytes = b"\x01" * 32


class InMemoryFindingsTable:
    """In-memory ``findings`` under the ``scanipy_triage`` role's privileges.

    Read surface = the ``GRANT SELECT (id, class, rule_id, severity,
    physical_location, message)`` projection (:meth:`list_for_scan`). Any attempt
    to ``update`` or ``delete`` raises :class:`PermissionError`, modelling
    ``REVOKE ALL ON findings FROM scanipy_triage`` (DOC-DB §4.14). ``snapshot``
    returns a deep copy of every full row so a spec can diff pre/post-triage and
    prove no ``findings`` column changed.
    """

    def __init__(self, scan_id: UUID, rows: list[StoredFinding]) -> None:
        self._scan_id = scan_id
        self._rows: dict[UUID, StoredFinding] = {r.id: r for r in rows}
        self._s_version = "1.2.3"
        self._env_digest = "sha256:" + ("a" * 64)

    # --- column-restricted read projection (FindingsReadSurface) -------------

    def list_for_scan(self, scan_id: UUID) -> list[FindingView]:
        assert scan_id == self._scan_id
        return [
            FindingView(
                id=r.id,
                class_=r.class_,
                rule_id=r.rule_id,
                severity=r.severity,  # type: ignore[arg-type]
                physical_location=dict(r.physical_location),
                message=r.message,
            )
            for r in self._rows.values()
        ]

    def context_for(self, finding_id: UUID) -> tuple[str, str]:
        # Bounded code window + SARIF excerpt; content is irrelevant to INV-3.
        return ("def handler(req):\n    sink(req.params['q'])\n", '{"ruleId":"R1"}')

    def scan_inv2_params(self, scan_id: UUID) -> tuple[str, str]:
        assert scan_id == self._scan_id
        return (self._s_version, self._env_digest)

    # --- mutation surface: REVOKE ALL ON findings ----------------------------

    def update(self, finding_id: UUID, **columns: object) -> None:
        raise PermissionError(
            "scanipy_triage has no UPDATE privilege on findings "
            f"(attempted columns {sorted(columns)!r})"
        )

    def delete(self, finding_id: UUID) -> None:
        raise PermissionError(
            f"scanipy_triage has no DELETE privilege on findings (attempted delete of {finding_id})"
        )

    # --- pre/post diff helper ------------------------------------------------

    def snapshot(self) -> dict[UUID, StoredFinding]:
        """Deep copy of every full ``findings`` row for diffing."""
        return {
            fid: replace(r, physical_location=dict(r.physical_location))
            for fid, r in self._rows.items()
        }


@dataclass
class _RecordedWrite:
    table: str
    row: dict[str, object]


class InMemoryTriageScoresStore:
    """INSERT-only ``triage_scores`` table (DOC-DB §4.14 grant).

    Records every insert so specs can assert the written column set and that the
    only target table is ``triage_scores``. Rejects any other table — the
    structural mirror of the absence of grants on ``provenance_records`` /
    ``spec_versions`` / ``proposed_specs``.
    """

    def __init__(self) -> None:
        self.writes: list[_RecordedWrite] = []

    def insert(self, table: str, row: dict[str, object]) -> None:
        if table != "triage_scores":
            raise PermissionError(f"scanipy_triage has no INSERT privilege on {table!r}")
        self.writes.append(_RecordedWrite(table=table, row=dict(row)))

    @property
    def written_tables(self) -> set[str]:
        return {w.table for w in self.writes}

    @property
    def written_columns(self) -> set[str]:
        cols: set[str] = set()
        for w in self.writes:
            cols.update(w.row.keys())
        return cols


class RecordingFakeLLM:
    """Offline triage LLM that records its call count (no real Anthropic call).

    ``call_count`` lets a spec assert **zero** LLM calls when ``LLM_TRIAGE=off``
    (TST-AC-TRI-01a). Returns a deterministic in-range verdict so the cycle
    produces a valid ``triage_scores`` row when the flag is on.
    """

    def __init__(self, *, model_version: str = "20260523") -> None:
        self.call_count = 0
        self._model_version = model_version
        self.seen: list[TriageInput] = []

    def score(self, inp: TriageInput) -> LLMTriageVerdict:
        self.call_count += 1
        self.seen.append(inp)
        return LLMTriageVerdict(
            likely_exploitable=0.7,
            likely_test_code=0.1,
            likely_fp=0.2,
            free_text=f"prioritise {inp.finding.rule_id}",
            model_version=self._model_version,
        )


def make_finding(
    *,
    finding_id: UUID | None = None,
    origin: str = "deterministic-core",
    status: str = "open",
    class_: str = "injection",
    rule_id: str = "R1",
) -> StoredFinding:
    """Build a representative ``findings`` row for the TRI-01 specs."""
    return StoredFinding(
        id=finding_id or uuid.uuid4(),
        class_=class_,
        rule_id=rule_id,
        severity="high",
        physical_location={"uri": "src/app.py", "start_line": 2, "end_line": 2},
        message="user input flows to a SQL sink",
        origin=origin,
        status=status,
    )


def malicious_triage_row(finding_id: UUID) -> dict[str, object]:
    """A triage row that smuggles a forbidden ``findings`` column.

    Used by TST-INV-1-TRI-01 to prove the allowed-column guard rejects an attempt
    to write ``origin`` (or any non-``triage_*`` column) through the write path.
    """
    return {
        "finding_id": finding_id,
        "triage_score": Decimal("0.5000"),
        "origin": "oracle-passthrough",  # INV-1 violation attempt
    }
