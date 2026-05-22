# DOC-CMP-FND-02 — Findings store schema

> **Status:** DRAFT (Phase 0). Satisfies `AC-DOC-04`: an Implementation Agent given only this document plus the cross-cutting refs (`DOC-DB`, `DOC-INV`, `DOC-PROVENANCE`, `DOC-PARTITION`, `DOC-DEPLOY-DECISIONS`, `DOC-GLOSSARY`) can produce a passing implementation without re-reading `SDD.md`.

---

## 1. Component identity

| Field | Value |
|---|---|
| **CMP-ID** | `CMP-FND-02` |
| **Subsystem** | Findings & Provenance (`SDD.md §8`) |
| **Module path** | `db/migrations/versions/` (Alembic) + `services/scan/models/findings.py` (SQLAlchemy ORM) |
| **Staging** | cross-cutting (`SDD.md §8 CMP-FND-02`) · partition-agnostic schema |
| **Depends-On** | `CMP-CP-03` (tenancy schema; provides `orgs`, `codebases`, `scans`, RLS template) |
| **Owns invariants (schema-level)** | **INV-1**, **INV-2**, **INV-5** discharged at the SQL constraint level |
| **Owning maintainer** | Findings & Provenance team |

---

## 2. Mandate

**SDD `Purpose:` (verbatim from `SDD.md §8 → CMP-FND-02`):**

> `findings` table with `slice_fingerprint`, `fingerprint_class`, `origin`, `determinism_partition`, `witness_blob_uri`, `S_version`, `env_digest`, `cpg_order_hash`, `triage_score`, `triage_reason`, `status`; index on `(codebase_id, slice_fingerprint)`.

**Operational role.** This component owns the persistent `findings` row schema, its NOT NULL constraints, its CHECK constraints, its indices, its RLS policy, and the **schema-level enforcement of three of the six invariants** (INV-1, INV-2, INV-5). It is the bottom-most line of defence for provenance threading: even if every application-layer guard fails, an INSERT missing `origin`, `S_version`, or `env_digest` raises a `NOT NULL violation` from PostgreSQL itself. It also owns the partial index that makes cross-scan baseline lookup `(codebase_id, slice_fingerprint)` correct and fast (`AC-FND-02a`).

**Architectural note on `triage_score`/`triage_reason`.** The SDD `Purpose` lists these columns. The schema (per `DOC-DB.md §4.12, §4.14`) places them in a **separate `triage_scores` table**, not on `findings`. This is a deliberate INV-3 defence: the LLM-triage worker (`CMP-TRI-01`) is granted INSERT only on `triage_scores`, never on `findings`. From the SARIF-emission point of view, `findings` joined to `triage_scores` reconstructs the SDD's logical row. This decomposition is justified in `DOC-DB.md §4.12` end-note and is **not** scope creep — it is the *implementation* of the SDD column list under INV-3.

---

## 3. Interface contract

### 3.1 Alembic migration

The schema is delivered as a versioned Alembic migration (`db/migrations/versions/<YYYYMMDD>_<NNNN>_findings_store.py`), running after the tenancy migrations from `CMP-CP-03` (`orgs`, `codebases`, `scans`, `snapshots`). The migration follows the rules of `DOC-DB.md §2`:

- Reversible (`upgrade()` + `downgrade()`).
- Table-shape and RLS-policy changes split into separate migrations.
- Verified by the Alembic upgrade-then-downgrade CI gate (`CMP-CI-01`, discharges `AC-CP-03a`).

### 3.2 SQLAlchemy ORM signatures

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (Column, Index, CheckConstraint, ForeignKey, Text,
                        LargeBinary, Numeric, TIMESTAMP)
import uuid
from typing import Literal

Origin    = Literal["deterministic-core", "oracle-passthrough"]
Engine    = Literal["ifds", "ide", "semgrep", "cpg-query", "external"]
FPClass   = Literal["strong", "weak"]
Severity  = Literal["info", "low", "medium", "high", "critical"]
Status    = Literal["open", "suppressed", "fixed"]

class Finding(Base):
    __tablename__ = "findings"

    id:                          Mapped[uuid.UUID] = mapped_column(primary_key=True)
    org_id:                      Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"),       nullable=False)
    codebase_id:                 Mapped[uuid.UUID] = mapped_column(ForeignKey("codebases.id"),  nullable=False)
    scan_id:                     Mapped[uuid.UUID] = mapped_column(ForeignKey("scans.id"),      nullable=False)
    snapshot_id:                 Mapped[uuid.UUID] = mapped_column(ForeignKey("snapshots.id"),  nullable=False)
    commit_sha:                  Mapped[str]       = mapped_column(Text,         nullable=False)
    class_:                      Mapped[str]       = mapped_column("class", Text, nullable=False)
    rule_id:                     Mapped[str]       = mapped_column(Text,         nullable=False)
    severity:                    Mapped[Severity]  = mapped_column(Text,         nullable=False)
    message:                     Mapped[str]       = mapped_column(Text,         nullable=False)
    physical_location:           Mapped[dict]      = mapped_column(JSONB,        nullable=False)

    # === INV-1 anchors (NOT NULL by AC-FND-02b) ===
    origin:                      Mapped[Origin]    = mapped_column(Text,         nullable=False)
    determinism_partition:       Mapped[Origin]    = mapped_column(Text,         nullable=False)
    engine:                      Mapped[Engine]    = mapped_column(Text,         nullable=False)

    # === INV-2 anchors (NOT NULL by AC-FND-02b) ===
    S_version:                   Mapped[str]       = mapped_column(Text,         nullable=False)
    env_digest:                  Mapped[str]       = mapped_column(Text,         nullable=False)

    # === INV-5 anchors (DOC-DB defence-in-depth; not under AC-FND-02b) ===
    cpg_order_hash:              Mapped[bytes]     = mapped_column(LargeBinary,  nullable=False)
    cpg_order_hash_annotation:   Mapped[str]       = mapped_column(
        Text, nullable=False,
        server_default="canonical iff fingerprint_class = strong",
    )
    fingerprint_class:           Mapped[FPClass]   = mapped_column(Text, nullable=False)
    slice_fingerprint:           Mapped[bytes]     = mapped_column(LargeBinary, nullable=False)

    # === Optional + status fields ===
    witness_blob_uri:            Mapped[str | None]= mapped_column(Text, nullable=True)
    precondition_status:         Mapped[str]       = mapped_column(Text, nullable=False)
    spec_provenance:             Mapped[str | None]= mapped_column(Text, nullable=True)
    status:                      Mapped[Status]    = mapped_column(Text, nullable=False, server_default="open")
    suppression_reason:          Mapped[str | None]= mapped_column(Text, nullable=True)
    created_at:                  Mapped[...]       = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at:                  Mapped[...]       = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        # Required partial / functional index for cross-scan baseline lookup (AC-FND-02a)
        Index("findings_codebase_slice_idx", "codebase_id", "slice_fingerprint"),
        Index("findings_scan_idx",           "scan_id"),
        Index("findings_org_created_idx",    "org_id", "created_at"),
        Index("findings_class_severity_idx", "class_", "severity"),
        Index("findings_core_partition_idx", "origin",
              postgresql_where="origin = 'deterministic-core'"),

        CheckConstraint("origin IN ('deterministic-core','oracle-passthrough')",
                        name="findings_origin_check"),
        CheckConstraint("determinism_partition IN ('deterministic-core','oracle-passthrough')",
                        name="findings_partition_check"),
        CheckConstraint("engine IN ('ifds','ide','semgrep','cpg-query','external')",
                        name="findings_engine_check"),
        CheckConstraint("fingerprint_class IN ('strong','weak')",
                        name="findings_fp_class_check"),
        CheckConstraint("severity IN ('info','low','medium','high','critical')",
                        name="findings_severity_check"),
        CheckConstraint("status IN ('open','suppressed','fixed')",
                        name="findings_status_check"),
        CheckConstraint("env_digest ~ '^sha256:[0-9a-f]{64}$'",
                        name="findings_env_digest_format"),
        CheckConstraint("octet_length(cpg_order_hash)     = 32",
                        name="findings_cpg_order_hash_length"),
        CheckConstraint("octet_length(slice_fingerprint)  = 32",
                        name="findings_slice_fingerprint_length"),
        CheckConstraint(
            "cpg_order_hash_annotation = 'canonical iff fingerprint_class = strong'",
            name="findings_cpg_order_hash_annotation_literal",
        ),
        CheckConstraint(
            "(status = 'suppressed') = (suppression_reason IS NOT NULL)",
            name="findings_suppression_reason_consistency",
        ),
    )
```

The exact column shapes match `DOC-DB.md §4.12` **verbatim**; this document does not introduce new columns.

### 3.3 RLS policy (per `DOC-DB.md §3.3`)

```sql
ALTER TABLE findings ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_select ON findings
  FOR SELECT
  USING (org_id::text = current_setting('app.org_id', true));

CREATE POLICY tenant_isolation_modify ON findings
  FOR ALL
  USING (org_id::text = current_setting('app.org_id', true))
  WITH CHECK (org_id::text = current_setting('app.org_id', true));
```

### 3.4 Grants (INV-3 enforcement at the schema layer)

```sql
-- The triage role cannot write to `findings` at all.
REVOKE ALL ON findings FROM scanipy_triage;

-- It may read only the columns it needs to score (no detection or provenance content
-- that could let it influence partitioning).
GRANT SELECT (id, class, rule_id, severity, physical_location, message)
  ON findings TO scanipy_triage;

-- `triage_scores` (separate table) is the only INSERT surface for triage.
GRANT INSERT ON triage_scores TO scanipy_triage;
```

This grant model is the schema-layer enforcement of INV-3 (`.claude/rules/01-invariants.md §INV-3`); `CMP-TRI-01` cannot bypass it.

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Notes |
|---|---|---|
| `Finding` instances (INSERT) | `CMP-ORCH-03` worker | Each must carry every `nullable=False` column; missing fields raise `NOT NULL violation`. |
| Re-partition UPDATE | `CMP-SNAP-04` | Sets `origin = 'oracle-passthrough'`; runs in a transaction together with `repartition_events` INSERT and `provenance_records` INSERT (`DOC-DB.md §4.15` trigger contract). |
| Triage INSERTs | `CMP-TRI-01` (via `triage_scores`, never directly on `findings`) | INV-3 fence. |

### 4.2 Outputs

| Consumer | What they read |
|---|---|
| `CMP-FND-01` (SARIF emit) | reads no rows directly — receives `Finding` objects from `CMP-ORCH-03`. The schema is the canonical persisted form behind those objects. |
| `CMP-FND-03` (signed provenance) | reads `findings` to construct chain link 6 (`witness_blob_uri`, `slice_fingerprint`), link 7 (`rule_id`, `detector_id`), link 9 (`origin`). |
| `CMP-SNAP-02` (incremental delta) | cross-scan baseline lookup by `(codebase_id, slice_fingerprint)` — uses the `findings_codebase_slice_idx` index (`AC-FND-02a`). |
| `CMP-CP-04` dashboard | reads finding rows filtered by RLS `app.org_id`. |
| `CMP-CP-05` (Attestor) | reads `origin = 'deterministic-core'` partition (uses `findings_core_partition_idx`). |

### 4.3 Persisted artefacts

| Artefact | Location | Retention |
|---|---|---|
| `findings` rows | PostgreSQL 16 on Amazon RDS | indefinite (`DOC-DB.md §7`); audit trail, never expired |
| `triage_scores` rows | PostgreSQL | 1 year |
| `repartition_events` rows | PostgreSQL | indefinite (append-only) |

S3-resident blobs (`witness_blob_uri`, SARIF, CPG tarballs) are sibling artefacts referenced *by* `findings` and `provenance_records`; this component owns the DB row, not the blob.

---

## 5. Invariants touched

### 5.1 INV-1 — Determinism partition (**SCHEMA-LEVEL DISCHARGE**)

Schema constraints that discharge INV-1:

- `findings.origin              NOT NULL` (verbatim from `AC-FND-02b`).
- `findings.determinism_partition NOT NULL` + CHECK `IN ('deterministic-core','oracle-passthrough')`.
- `findings.engine              NOT NULL` + CHECK `IN ('ifds','ide','semgrep','cpg-query','external')`.
- `repartition_events.new_origin = 'oracle-passthrough'` CHECK (`DOC-DB.md §4.15`); re-partitioning is monotonic toward oracle.

A row INSERTed without `origin` raises a `NOT NULL violation`. `TST-INV-1-FND-02` (`WBS.md §10 CMP-FND-02`) asserts this is unrecoverable at the schema layer.

### 5.2 INV-2 — Versioned parameters (**SCHEMA-LEVEL DISCHARGE**)

Schema constraints that discharge INV-2:

- `findings.S_version  NOT NULL` (verbatim from `AC-FND-02b`).
- `findings.env_digest NOT NULL` + CHECK `~ '^sha256:[0-9a-f]{64}$'` (verbatim from `AC-FND-02b`).
- Mirror NOT NULL constraints on `provenance_records.S_version` + `.env_digest`, `attestations.S_version` + `.env_digest`, `triage_scores.S_version` + `.env_digest`, `scans.S_version` + `.env_digest`, `snapshots.env_digest` (`DOC-DB.md §5`).

`TST-INV-2-FND-02` asserts the NOT NULL violation path; `TST-AC-FND-02b` asserts no row in production carries a null in either column.

### 5.3 INV-5 — Conditional canonicality annotation (defence-in-depth)

**Scope clarification (per `DOC-PROVENANCE.md §2 note`).** `AC-FND-02b` pins NOT NULL on exactly three columns: `origin`, `S_version`, `env_digest`. INV-5 is *not* under AC-FND-02b. This component adds the following **defence-in-depth constraints** that go beyond the verbatim AC, motivated by INV-5 discipline (`AC-CORE-03c`, `AC-FND-03b`):

- `findings.cpg_order_hash            NOT NULL` + CHECK `octet_length = 32`.
- `findings.cpg_order_hash_annotation NOT NULL` + CHECK `= 'canonical iff fingerprint_class = strong'` (literal CHECK).
- `findings.fingerprint_class         NOT NULL` + CHECK `IN ('strong','weak')`.

The literal CHECK on `cpg_order_hash_annotation` is the schema-layer enforcement of INV-5: it is impossible to INSERT a row that carries the hash without the annotation, or with an abbreviated/translated annotation. Any application-layer attempt to do so raises a CHECK constraint violation.

`TST-INV-5-FND-02` (`[FORTHCOMING]`) asserts the CHECK is unforgeable.

### 5.4 INV-3 — LLM off the detection path (grants-level discharge)

The grants in §3.4 are the schema-layer discharge of INV-3: `CMP-TRI-01`'s database role has no DML privilege on `findings`. Even a maliciously-modified triage worker cannot mutate `origin`, `status`, or detection content. Discharges the operational risk class "triage worker overwrites a deterministic-core finding".

### 5.5 INV-4 — undecidable approximations (not touched)

This component does not approximate anything. INV-4 is not its concern.

### 5.6 INV-6 — per-language honesty (not touched)

This component does not assert recall claims. INV-6 is not its concern.

---

## 6. Dependency contract

`Depends-On:` **`CMP-CP-03`** (per `WBS.md §20`).

This component **assumes**:

- `CMP-CP-03` has applied its tenancy migrations: `orgs`, `memberships`, `projects`, `codebases`, `scm_credentials`, `org_policies` exist with their RLS template (`DOC-DB.md §3`).
- `CMP-CP-03` has applied `snapshots`, `scans` (the derived `scans` table per `DOC-DB.md §4.11` / `CLAR-DB-01`), and `spec_versions` — `findings` foreign-keys into all three.
- The PostgreSQL session-variable scheme (`app.org_id`, `app.user_id`, `app.role`) is functional (`DOC-DB.md §3.2`, `CLAR-DB-02`).
- The `scanipy_triage` and `scanipy_system` database roles exist (`DOC-DB.md §3`).
- The Alembic environment is configured.

This component is consumed by **`CMP-FND-01`** (reads finding objects, projects to SARIF), **`CMP-FND-03`** (constructs chain rows referencing `findings.id`), **`CMP-SNAP-02`** (cross-scan baseline lookup), **`CMP-SNAP-04`** (re-partition UPDATE), and the API/dashboard read paths.

---

## 7. Failure modes and error contracts

### 7.1 Failure modes

| Mode | DB-layer detection | Application-layer response |
|---|---|---|
| INSERT missing `origin` / `S_version` / `env_digest` | `NOT NULL violation` (SQLSTATE `23502`) | Map to HTTP 500 with `error_code = "invariant_inv1_violation"` or `"invariant_inv2_violation"` per `DOC-API.md §6.1`; alarm + page on first occurrence in production. |
| INSERT with annotation literal mismatch | CHECK violation on `findings_cpg_order_hash_annotation_literal` | HTTP 500 with `error_code = "invariant_inv5_violation"`; alarm. |
| INSERT with `octet_length(cpg_order_hash) ≠ 32` | CHECK violation | HTTP 500 with `error_code = "schema_violation"`. |
| INSERT from triage role | grant denial (`permission denied`) | Application bug; rollback; alarm — INV-3 fence engaged. |
| Cross-tenant SELECT | RLS predicate returns zero rows | No error (silent zero-row); RLS policy violation on INSERT/UPDATE/DELETE raises permission error. |
| Re-partition UPDATE without paired `repartition_events` INSERT | trigger raises (`DOC-DB.md §4.15`) | rollback; the cascade is atomic. |
| Migration apply failure | Alembic raises | `CMP-CI-01` upgrade-downgrade gate fails the pipeline. |

### 7.2 No retries on constraint violation

NOT NULL / CHECK violations are application-bug indicators (the upstream emitter is malformed). The application MUST NOT silently retry by stuffing default values into the missing columns; that would *defeat* the schema-layer discharge. Bubble up the error.

### 7.3 Updates

The `findings` table accepts:

- INSERT (worker emit).
- UPDATE on `status`, `suppression_reason`, `updated_at` (operator suppression / fix).
- UPDATE on `origin` from `'deterministic-core'` → `'oracle-passthrough'` only via the `CMP-SNAP-04` cascade (paired with `repartition_events` INSERT + `provenance_records` INSERT in one transaction, enforced by trigger).

Direct UPDATE of `origin`, `S_version`, `env_digest`, `cpg_order_hash`, `cpg_order_hash_annotation`, `fingerprint_class`, `slice_fingerprint`, `rule_id`, `engine` outside the re-partition cascade is **disallowed** by application policy. (The DB does not enforce a column-level UPDATE block beyond grants; the application-layer ORM enforces it and code review enforces it.)

---

## 8. Provenance threading

This component is the **persistent home** of every required provenance field. Cross-reference:

| Field on `findings` | Set by | Required NOT NULL / CHECK |
|---|---|---|
| `origin` | `CMP-ORCH-03` | NOT NULL + CHECK enum (AC-FND-02b + INV-1) |
| `S_version` | `CMP-ORCH-01` → `CMP-ORCH-03` | NOT NULL (AC-FND-02b + INV-2) |
| `env_digest` | `CMP-SNAP-01` → `CMP-ORCH-03` | NOT NULL + sha256 format CHECK (AC-FND-02b + INV-2) |
| `cpg_order_hash` | `CMP-CORE-03` → `CMP-ORCH-03` | NOT NULL + length CHECK (INV-5 defence-in-depth) |
| `cpg_order_hash_annotation` | constant from `analysis.ordering` | NOT NULL + literal CHECK (INV-5 defence-in-depth) |
| `fingerprint_class` | `CMP-CORE-02` (re-emitted by `CMP-CORE-03`) | NOT NULL + enum CHECK |
| `slice_fingerprint` | `CMP-CORE-02` | NOT NULL + length CHECK |
| `determinism_partition` | `CMP-DET-02` manifest → `CMP-ORCH-03` | NOT NULL + enum CHECK |
| `engine` | `CMP-DET-02` manifest | NOT NULL + enum CHECK |
| `witness_blob_uri` | `CMP-ORCH-03` | nullable (oracle findings may omit) |
| `triage_score` / `triage_reason` | `CMP-TRI-01` — **separate `triage_scores` table** | — (INV-3 fence) |

The four required fields (RULE-6 + INV-1 + INV-2 + INV-5) are all present on `findings`. The annotation literal is enforced by `findings_cpg_order_hash_annotation_literal` CHECK.

---

## 9. Acceptance criteria cross-reference

| AC ID | Verbatim from `SDD.md §8 CMP-FND-02` | Test ID | Label | Notes |
|---|---|---|---|---|
| `AC-FND-02a` | "Cross-scan baseline lookup by `(codebase_id, slice_fingerprint)` is correct and never auto-suppresses a `weak` or `oracle-passthrough` finding across a refactor." | `TST-AC-FND-02a` `[FORTHCOMING]` | `[INVARIANT]` | Asserts the `findings_codebase_slice_idx` index supports the lookup; asserts the baseline-match policy never suppresses a `weak` or `oracle-passthrough` finding (joins to `CMP-FND-01` / `CMP-CORE-02` policy). |
| `AC-FND-02b` | "Every row carries a non-null `origin`, `S_version`, `env_digest` (INV-1, INV-2)." | `TST-AC-FND-02b` `[FORTHCOMING]` | `[INVARIANT]` | Asserts the three NOT NULL constraints exist and an INSERT missing any of them raises `NOT NULL violation`. **Note**: AC-FND-02b lists exactly these three columns; `cpg_order_hash` and its annotation are NOT under this AC (per `DOC-PROVENANCE.md §2`), but are nonetheless enforced via the defence-in-depth constraints in §5.3 and tested by `TST-INV-5-FND-02`. |
| `TST-INV-1-FND-02` | — (invariant test) | `TST-INV-1-FND-02` `[FORTHCOMING]` | `[INVARIANT]` | Schema-level: INSERT missing `origin` raises. INSERT with `origin = 'mixed'` rejected by enum CHECK. |
| `TST-INV-2-FND-02` | — (invariant test) | `TST-INV-2-FND-02` `[FORTHCOMING]` | `[INVARIANT]` | Schema-level: INSERT missing `S_version` or `env_digest` raises. INSERT with malformed `env_digest` (not sha256:hex64) rejected. |
| `TST-INV-5-FND-02` | — (invariant test, defence-in-depth) | `TST-INV-5-FND-02` `[FORTHCOMING]` | `[INVARIANT]` | Schema-level: INSERT with `cpg_order_hash_annotation = 'abbreviated'` rejected by literal CHECK. INSERT missing `cpg_order_hash` raises. |
| `TST-INV-3-FND-02` (grants) | — (invariant test) | `TST-INV-3-FND-02` `[FORTHCOMING]` | `[INVARIANT]` | Connects to DB as `scanipy_triage`; asserts no DML on `findings` works (permission denied); asserts INSERT into `triage_scores` does work. |

Per `WBS.md §10 CMP-FND-02`: tasks are `T-CMP-FND-02-01` (create table), `T-CMP-FND-02-02` (index `(codebase_id, slice_fingerprint)`), `T-CMP-FND-02-03` (enforce non-null `origin`, `S_version`, `env_digest` at schema level). Tests: `TST-AC-FND-02a`, `TST-AC-FND-02b`, `TST-INV-1-FND-02`, `TST-INV-2-FND-02`.

---

## 10. Open questions

- **`CLAR-DB-01` (DEFERRED).** The `scans` table is required by `findings.scan_id` FK but is not explicitly enumerated in `SDD.md CMP-CP-03`. `DOC-DB.md §4.11` adds it as a derived table. This document assumes that derivation. **Operational impact:** none — the FK works; Architect Agent ratification is documentation hygiene.
- **`CLAR-DB-02` (DEFERRED).** PostgreSQL RLS session-variable scheme (`app.org_id`, `app.user_id`, `app.role`) proposed by `DOC-DB.md §3.2`. This document inherits the proposed scheme verbatim. Sign-off pending from SRE/DevOps + Security Analyst before Phase 11.
- **`CLAR-DEPLOY-15` (RESOLVED).** Retention map for `findings` = indefinite; `triage_scores` = 1 year; `repartition_events` = indefinite (append-only). Discharged into `DOC-DB.md §7`.
- **`CLAR-DEPLOY-16` (RESOLVED).** Per-tenant isolation = S3 prefix + RDS RLS + KMS per-tenant CMKs. RLS template in §3.3.
- **No new CLARs filed by this document.**

If an Implementation Agent encounters ambiguity not covered here (e.g. a new finding-related column required by an unscheduled feature), file `CLAR-FND-NN` in `WBS.md §17` per `.claude/rules/03-scope.md`. **Do not invent missing scope.**

---

## Appendix A. The invariant-discharge matrix (canonical, derived from `DOC-DB.md §5`)

| Invariant | This component's NOT NULL / CHECK constraints |
|---|---|
| **INV-1** | `findings.origin` NOT NULL + enum CHECK; `findings.determinism_partition` NOT NULL + enum CHECK; `findings.engine` NOT NULL + enum CHECK |
| **INV-2** | `findings.S_version` NOT NULL; `findings.env_digest` NOT NULL + sha256 format CHECK |
| **INV-5** | `findings.cpg_order_hash` NOT NULL + length CHECK; `findings.cpg_order_hash_annotation` NOT NULL + literal CHECK; `findings.fingerprint_class` NOT NULL + enum CHECK |
| **INV-3** | grant model: triage role cannot write `findings`; can only INSERT into `triage_scores` |

The matrix is also propagated to `provenance_records`, `attestations`, `triage_scores`, `scans`, and `snapshots` for the relevant subset of columns — see `DOC-DB.md §5`.

---

## Appendix B. Cross-references

- `SDD.md §8 CMP-FND-02` — verbatim ACs.
- `WBS.md §10 CMP-FND-02` — task list (`T-CMP-FND-02-01..03`); `§15` invariant map; `§20` DAG.
- `DOC-DB` — §3 (RLS), §4.12 (`findings`), §4.14 (`triage_scores`), §4.15 (`repartition_events`), §5 (invariant matrix), §7 (retention).
- `DOC-PROVENANCE` §2 (AC-FND-02b NOT NULL scope), §3 (chain shape), §10 (per-component threading).
- `DOC-INV` (INV-1, INV-2, INV-3, INV-5).
- `DOC-PARTITION` (engine → origin).
- `DOC-DEPLOY-DECISIONS` (CLAR-DEPLOY-03 RDS, CLAR-DEPLOY-15 retention, CLAR-DEPLOY-16 RLS).
- `.claude/rules/01-invariants.md` (INV-1, INV-2, INV-3, INV-5).
- `.claude/rules/02-provenance.md` (provenance threading).
