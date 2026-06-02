"""CMP-SNAP-01 — ``snapshots`` table ORM model (``SnapshotRow``).

This module defines the ``SnapshotRow`` ORM model. It is the application-layer
mirror of the ``snapshots`` table whose DDL already ships in CMP-CP-03's Alembic
migration ``db/migrations/versions/20260524_0001_initial_tenancy_tables.py``
(lines 171-212; DOC-DB §4.7, owner CMP-SNAP-01). It does **not** introduce a
second migration — the schema lives in the CP-03 migration and this ORM is the
read/insert surface for it.

The model mirrors that shipped DDL **verbatim** — same columns, same nullability,
the same CHECK constraints under the same constraint names, the same UNIQUE
constraint and index. The pattern follows ``services/scan/models/findings.py``
(the CMP-FND-02 ``Finding`` model).

The class is deliberately named ``SnapshotRow`` (NOT ``Snapshot``): a domain
``Snapshot`` value object already lives in ``services/snapshot/cw_detect.py`` and
is re-exported from ``services/snapshot/__init__.py``; this ORM row must not
shadow it.

DOC-vs-schema note (CLAR-SNAP-02, WBS §17): ``DOC-CMP-SNAP-01 §3.3/§4.4`` describe
a ``queued→snapshotting→ready`` state machine with nullable ``precondition_status``
plus ``snapshot_digest`` / ``completed_at`` columns. The shipped CP-03 schema has
NONE of those — ``precondition_status`` is NOT NULL with a CHECK over the three
verdicts, and there is no ``state`` / ``snapshot_digest`` / ``completed_at``
column. This ORM mirrors the **shipped schema**: a row is a single insert made
once the precondition verdict and the five artifact URIs are known.

Invariant discharge owned here (INV-2):

* ``env_digest`` NOT NULL + ``^sha256:[0-9a-f]{64}$`` format CHECK.
* ``commit_sha`` NOT NULL + ``^[0-9a-f]{40}$`` format CHECK.
* ``precondition_status`` NOT NULL + 3-value enum CHECK.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Literal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from services.scan.models import Base

PreconditionStatus = Literal["closed-world", "degraded", "full-reparse"]


class SnapshotRow(Base):
    """A single persisted snapshot row (``snapshots`` table, DOC-DB §4.7).

    Mirrors the DDL shipped in migration ``20260524_0001`` (lines 171-212)
    verbatim. Named ``SnapshotRow`` so it does not shadow the domain
    ``Snapshot`` value object in ``services.snapshot.cw_detect``.
    """

    __tablename__ = "snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False
    )
    codebase_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("codebases.id", ondelete="CASCADE"),
        nullable=False,
    )
    commit_sha: Mapped[str] = mapped_column(Text, nullable=False)

    # === INV-2 anchor (NOT NULL; env_digest format CHECK) ===
    env_digest: Mapped[str] = mapped_column(Text, nullable=False)

    # === precondition verdict (NOT NULL + 3-value enum CHECK) ===
    precondition_status: Mapped[PreconditionStatus] = mapped_column(Text, nullable=False)

    # === the five artifact URIs (AC-SNAP-01a) ===
    # NOTE: the SQL column for the ΔG artifact is ``delta_g_uri`` (not
    # ``delta_graph_uri``) and is the ONLY nullable URI (a first/full snapshot
    # has no parent, hence no delta). The other four are NOT NULL.
    cpg_tarball_uri: Mapped[str] = mapped_column(Text, nullable=False)
    reverse_symbol_index_uri: Mapped[str] = mapped_column(Text, nullable=False)
    dynamic_call_graph_uri: Mapped[str] = mapped_column(Text, nullable=False)
    delta_g_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    precondition_status_record_uri: Mapped[str] = mapped_column(Text, nullable=False)

    parent_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("snapshots.id"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now() + interval '90 days'"),
    )

    __table_args__ = (
        # --- CHECK constraints (names + sqltext verbatim from the DDL) ---
        CheckConstraint(
            "commit_sha ~ '^[0-9a-f]{40}$'",
            name="snapshots_commit_sha_chk",
        ),
        CheckConstraint(
            "env_digest ~ '^sha256:[0-9a-f]{64}$'",
            name="snapshots_env_digest_chk",
        ),
        CheckConstraint(
            "precondition_status IN ('closed-world', 'degraded', 'full-reparse')",
            name="snapshots_precondition_status_chk",
        ),
        # --- UNIQUE + index (names + columns verbatim from the DDL) ---
        UniqueConstraint(
            "codebase_id",
            "commit_sha",
            "env_digest",
            name="snapshots_codebase_commit_env_key",
        ),
        Index(
            "snapshots_org_codebase_created_idx",
            "org_id",
            "codebase_id",
            created_at.desc(),
        ),
    )


__all__ = ["PreconditionStatus", "SnapshotRow"]
