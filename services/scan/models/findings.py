"""CMP-FND-02 — Findings store schema (SQLAlchemy ORM model).

This module defines the ``Finding`` ORM model. It is the application-layer
mirror of the ``findings`` table whose DDL already ships in CMP-CP-03's Alembic
migration ``db/migrations/versions/20260524_0001_initial_tenancy_tables.py``
(the declared FND-02 migration vehicle, per DOC-DB §4.12 / DOC-CMP-CP-03 §3.1).

Migration ``20260925_0003`` adds independent graph/slice classes and states.
Legacy rows retain their original fields unchanged and do not acquire inferred
classes. New core rows require computed evidence; oracle rows may explicitly
mark unavailable artifacts not applicable. Existing enum, length, and literal
checks and indexes remain, with conditional identity checks added below.

Schema-level invariant discharge owned here (DOC-CMP-FND-02 §5, Appendix A):

* **INV-1** — ``origin`` / ``determinism_partition`` / ``engine`` NOT NULL +
  enum CHECK (``origin`` enum admits only ``deterministic-core`` /
  ``oracle-passthrough`` — never ``mixed``).
* **INV-2** — ``S_version`` / ``env_digest`` NOT NULL; ``env_digest`` sha256
  format CHECK.
* **INV-5** — computed ``cpg_order_hash`` has a 32-byte length CHECK;
  ``cpg_order_hash_annotation`` NOT NULL + literal CHECK pinning the exact
  string ``canonical iff fingerprint_class = strong``; ``fingerprint_class``
  retains its legacy enum CHECK. V2 classes are artifact-local, never inferred
  from that ambiguous historical field.

INV-3 (the triage-role grant fence) is enforced at the GRANT level in the
CP-03 migration, not in the ORM.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Literal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from services.scan.models import Base

Origin = Literal["deterministic-core", "oracle-passthrough"]
Engine = Literal["ifds", "ide", "semgrep", "cpg-query", "external"]
FPClass = Literal["strong", "weak"]
Severity = Literal["info", "low", "medium", "high", "critical"]
Status = Literal["open", "suppressed", "fixed"]
PreconditionStatus = Literal["closed-world", "degraded", "full-reparse"]

# The INV-5 annotation literal, pinned by the literal CHECK constraint and
# reproduced here so the ORM server_default matches the DDL byte for byte.
CPG_ORDER_HASH_ANNOTATION = "canonical iff fingerprint_class = strong"


class Finding(Base):
    """A single persisted finding row (``findings`` table, DOC-DB §4.12).

    Mirrors initial DDL plus the additive ``20260925_0003`` identity migration.
    """

    __tablename__ = "findings"

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
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("snapshots.id"), nullable=False
    )
    commit_sha: Mapped[str] = mapped_column(Text, nullable=False)
    # ``class`` is a Python keyword; the SQL column name is preserved as "class".
    class_: Mapped[str] = mapped_column("class", Text, nullable=False)
    rule_id: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[Severity] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    physical_location: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)

    # === INV-1 anchors (NOT NULL + enum CHECK) ===
    origin: Mapped[Origin] = mapped_column(Text, nullable=False)
    determinism_partition: Mapped[Origin] = mapped_column(Text, nullable=False)
    engine: Mapped[Engine] = mapped_column(Text, nullable=False)

    # === INV-2 anchors (NOT NULL; env_digest format CHECK) ===
    # The SQL identifier is the case-sensitive quoted "S_version" in the DDL.
    S_version: Mapped[str] = mapped_column("S_version", Text, nullable=False)
    env_digest: Mapped[str] = mapped_column(Text, nullable=False)

    # === INV-5 anchors (defence-in-depth: NOT NULL + length/literal/enum CHECK) ===
    cpg_order_hash: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    cpg_order_hash_annotation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        # A bare-string server_default is emitted as raw, unquoted DDL; wrap the
        # literal so the ORM renders
        # DEFAULT 'canonical iff fingerprint_class = strong' byte-for-byte like
        # the CP-03 migration DDL.
        server_default=text(f"'{CPG_ORDER_HASH_ANNOTATION}'"),
    )
    fingerprint_class: Mapped[FPClass | None] = mapped_column(Text, nullable=True)
    slice_fingerprint: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    identity_schema_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    cpg_order_class: Mapped[FPClass | None] = mapped_column(Text, nullable=True)
    slice_fingerprint_class: Mapped[FPClass | None] = mapped_column(Text, nullable=True)
    cpg_order_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'legacy-ambiguous'")
    )
    slice_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'legacy-ambiguous'")
    )
    cpg_order_namespace: Mapped[str | None] = mapped_column(Text, nullable=True)
    slice_namespace: Mapped[str | None] = mapped_column(Text, nullable=True)

    # === Optional + status fields ===
    witness_blob_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    precondition_status: Mapped[PreconditionStatus | None] = mapped_column(Text, nullable=True)
    spec_provenance: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[Status] = mapped_column(Text, nullable=False, server_default=text("'open'"))
    suppression_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("identity_schema_version IN (1, 2)", name="findings_identity_version_chk"),
        CheckConstraint(
            "identity_schema_version <> 2 OR fingerprint_class IS NULL",
            name="findings_no_shared_class_chk",
        ),
        CheckConstraint(
            "cpg_order_class IS NULL OR cpg_order_class IN ('strong', 'weak')",
            name="findings_graph_class_chk",
        ),
        CheckConstraint(
            "slice_fingerprint_class IS NULL OR slice_fingerprint_class IN ('strong', 'weak')",
            name="findings_slice_class_chk",
        ),
        CheckConstraint(
            "identity_schema_version <> 1 OR (cpg_order_hash IS NOT NULL "
            "AND slice_fingerprint IS NOT NULL AND fingerprint_class IS NOT NULL "
            "AND precondition_status IS NOT NULL AND cpg_order_class IS NULL "
            "AND slice_fingerprint_class IS NULL AND cpg_order_status = 'legacy-ambiguous' "
            "AND slice_status = 'legacy-ambiguous' AND cpg_order_namespace IS NULL "
            "AND slice_namespace IS NULL)",
            name="findings_legacy_identity_chk",
        ),
        CheckConstraint(
            "identity_schema_version <> 2 OR origin <> 'deterministic-core' OR "
            "(cpg_order_status = 'completed' AND slice_status = 'completed' "
            "AND precondition_status IS NOT NULL)",
            name="findings_core_identity_chk",
        ),
        *(
            CheckConstraint(
                f"({prefix}_status = 'completed' AND {digest} IS NOT NULL "
                f"AND {klass} IS NOT NULL AND {prefix}_namespace IS NOT NULL "
                f"AND length({prefix}_namespace) > 0) OR "
                f"({prefix}_status = 'legacy-ambiguous' AND {klass} IS NULL "
                f"AND {prefix}_namespace IS NULL) OR "
                f"({prefix}_status IN ('pending', 'running', 'failed', 'not-applicable') "
                f"AND {digest} IS NULL AND {klass} IS NULL AND {prefix}_namespace IS NULL)",
                name=f"findings_{prefix}_artifact_chk",
            )
            for prefix, digest, klass in (
                ("cpg_order", "cpg_order_hash", "cpg_order_class"),
                ("slice", "slice_fingerprint", "slice_fingerprint_class"),
            )
        ),
        # --- CHECK constraints (names + sqltext verbatim from the DDL) ---
        CheckConstraint(
            "commit_sha ~ '^[0-9a-f]{40}$'",
            name="findings_commit_sha_chk",
        ),
        CheckConstraint(
            "class IN ('injection', 'path-traversal', 'ssrf', "
            "'deserialization', 'xss', 'crypto-misuse', 'authn-authz', "
            "'secrets', 'dep-cve', 'memory-safety')",
            name="findings_class_chk",
        ),
        CheckConstraint(
            "severity IN ('info', 'low', 'medium', 'high', 'critical')",
            name="findings_severity_chk",
        ),
        CheckConstraint(
            "origin IN ('deterministic-core', 'oracle-passthrough')",
            name="findings_origin_chk",
        ),
        CheckConstraint(
            "determinism_partition IN ('deterministic-core', 'oracle-passthrough')",
            name="findings_determinism_partition_chk",
        ),
        CheckConstraint(
            "engine IN ('ifds', 'ide', 'semgrep', 'cpg-query', 'external')",
            name="findings_engine_chk",
        ),
        CheckConstraint(
            "env_digest ~ '^sha256:[0-9a-f]{64}$'",
            name="findings_env_digest_chk",
        ),
        CheckConstraint(
            "octet_length(cpg_order_hash) = 32",
            name="findings_cpg_order_hash_len_chk",
        ),
        CheckConstraint(
            "cpg_order_hash_annotation = 'canonical iff fingerprint_class = strong'",
            name="findings_cpg_order_hash_annotation_chk",
        ),
        CheckConstraint(
            "fingerprint_class IN ('strong', 'weak')",
            name="findings_fingerprint_class_chk",
        ),
        CheckConstraint(
            "octet_length(slice_fingerprint) = 32",
            name="findings_slice_fingerprint_len_chk",
        ),
        CheckConstraint(
            "precondition_status IN ('closed-world', 'degraded', 'full-reparse')",
            name="findings_precondition_status_chk",
        ),
        CheckConstraint(
            "spec_provenance IS NULL OR spec_provenance IN "
            "('global-unrevalidated', 'global-revalidated', 'customer')",
            name="findings_spec_provenance_chk",
        ),
        CheckConstraint(
            "status IN ('open', 'suppressed', 'fixed')",
            name="findings_status_chk",
        ),
        CheckConstraint(
            "(status = 'suppressed') = (suppression_reason IS NOT NULL)",
            name="findings_suppression_reason_chk",
        ),
        # --- Indexes (names + columns verbatim from the DDL) ---
        Index("findings_codebase_slice_idx", "codebase_id", "slice_fingerprint"),
        Index("findings_scan_idx", "scan_id"),
        Index("findings_org_created_idx", "org_id", created_at.desc()),
        Index("findings_class_severity_idx", "class", "severity"),
        Index(
            "findings_core_origin_idx",
            "origin",
            postgresql_where=text("origin = 'deterministic-core'"),
        ),
    )
