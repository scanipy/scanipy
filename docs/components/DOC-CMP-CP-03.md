# DOC-CMP-CP-03 — Tenancy schema + migrations

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `SDD.md §10 CMP-CP-03` (Purpose, AC-CP-03a)
- `PLAN.md §"Phase 6 — Multi-tenant control plane"`
- `docs/cross-cutting/DOC-DB.md` (§2 Alembic; §3 RLS; §4 table catalog; §5 invariant-discharge matrix)
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` (CLAR-DEPLOY-03 PostgreSQL 16 + Alembic; CLAR-DEPLOY-15 retention; CLAR-DEPLOY-16 layered isolation)
- `docs/cross-cutting/DOC-INV.md §3, §4, §7` (INV-1, INV-2, INV-5 schema-level discharge)
- `.claude/rules/00-global.md`, `.claude/rules/02-provenance.md`

This document is the **implementation contract** for `CMP-CP-03`. A code-writing agent given only this file plus the cross-cutting refs listed above must be able to produce a passing implementation without re-reading `SDD.md` (per `AC-DOC-04`).

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-CP-03` |
| Subsystem | Control Plane & Attestation (`SDD.md §10`) |
| Staging | cross-cutting |
| Depends-On | none (`WBS.md §20`) |
| Owner | **DEFERRED** via `CLAR-OWNER-01` (`WBS.md §17`) |
| INV-* touched | Tenancy-isolation discharge of **CLAR-DEPLOY-16** (RLS policies + `app.org_id` session variable); schema-level enforcement of **INV-1** / **INV-2** / **INV-5** via NOT NULL constraints. **The schema-level NOT NULL discharge of INV-1/2/5 on the `findings` table is jointly owned: `CMP-FND-02` is the schema-shape owner (`DOC-DB §4.12`); `CMP-CP-03` ships the migration that materializes it.** |

---

## 2. Mandate

**Verbatim SDD `Purpose:` (`SDD.md §10 CMP-CP-03`):**

> Tables `orgs`, `projects`, `codebases`, `scm_credentials`, `org_policies`, `memberships`, `snapshots` (+precondition-status), `proposed_specs`, `spec_versions`, `attestations`; reuse the existing `BaseDatabase`.

**Operational role.** `CMP-CP-03` is the **tenancy schema and migrations** component. It owns:

1. The Alembic migration sequence that materializes the SDD-enumerated tables (and the additional tables required to discharge invariants — see `DOC-DB.md §4`).
2. The PostgreSQL Row-Level Security (RLS) policies on every multi-tenant table, keyed on the `app.org_id` session variable.
3. The session-variable scheme (`app.org_id`, `app.user_id`, `app.role`) that backs the RLS predicates (DEFERRED via `CLAR-DB-02`; used here as the working assumption).
4. The migration ordering required for clean forward / rollback against a fresh database (the AC-CP-03a hard contract).

`CMP-CP-03` does **not** write any application row. It ships DDL; runtime INSERT/UPDATE/DELETE on application tables is owned by the components named per-table in `DOC-DB §4`. CP-03 also does **not** define every column shape unilaterally — for tables owned by other components (`findings` → `CMP-FND-02`; `snapshots` → `CMP-SNAP-01`; `provenance_records` → `CMP-FND-03`; `triage_scores` → `CMP-TRI-01`; `repartition_events` → `CMP-SNAP-04`), CP-03 is the migration vehicle and the owners are accountable for the column shape via their own DOC-CMP-* files.

The SDD-listed CP-03 tables are: `orgs`, `projects`, `codebases`, `scm_credentials`, `org_policies`, `memberships`, `snapshots`, `proposed_specs`, `spec_versions`, `attestations`. `DOC-DB §4` additionally enumerates `findings`, `scans` (derived, see `CLAR-DB-01`), `provenance_records`, `triage_scores`, and `repartition_events`. All migrations live under `db/migrations/versions/`.

---

## 3. Interface contract

### 3.1 Migration framework

Per `DOC-DB §2`:

- **Tool:** Alembic (Python).
- **Location:** `db/migrations/versions/`.
- **Naming:** `<YYYYMMDD>_<NNNN>_<slug>.py`, e.g. `20260523_0001_initial_tenancy.py`.
- **Per-revision content:**
  - Each migration is reversible (`upgrade()` + `downgrade()`).
  - Migrations that change RLS policies are **split** from migrations that change table shape; never combined.
  - Each migration runs under a database role with no application read/write privileges.
- **CI gate:** Alembic upgrade-then-downgrade against a fresh database is a `CMP-CI-01` hard gate (discharges AC-CP-03a).

### 3.2 Migration ordering (topological)

Verbatim from `DOC-DB §4`:

```
orgs
memberships
projects
codebases
scm_credentials
org_policies
snapshots
proposed_specs
spec_versions
scans                  # CLAR-DB-01 — derived table, see §10
attestations
findings               # owned by CMP-FND-02; CP-03 ships the migration
provenance_records     # owned by CMP-FND-03; CP-03 ships the migration
triage_scores          # owned by CMP-TRI-01; CP-03 ships the migration
repartition_events     # owned by CMP-SNAP-04; CP-03 ships the migration
```

Each table depends only on those listed before it. Forward-apply walks the order downward; rollback walks it upward. `scans` precedes `attestations`, `findings`, and `repartition_events` because all three foreign-key into it.

### 3.3 RLS policy template

Every multi-tenant table enables RLS with the following pair of policies — **taken verbatim from `DOC-DB §3.3`** (CLAR-DB-02 DEFERRED — `app.org_id` is the **working assumption** until ratified by the SRE/DevOps and Security Analyst agents):

```sql
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_select ON <table>
  FOR SELECT
  USING (org_id::text = current_setting('app.org_id', true));

CREATE POLICY tenant_isolation_modify ON <table>
  FOR ALL
  USING (org_id::text = current_setting('app.org_id', true))
  WITH CHECK (org_id::text = current_setting('app.org_id', true));
```

A cross-tenant access from the application role produces zero rows on SELECT and an RLS violation on INSERT/UPDATE/DELETE. This is the AC-CP-01a backstop (CLAR-DEPLOY-16 layer 2).

**Tables with custom RLS policies (not the standard template):**

- `orgs` — RLS not enabled (this table *defines* tenancy; control-plane internal role only).
- `spec_versions` — `scope='global'` rows are universally readable; `scope='customer'` follows the standard template (custom policy per `DOC-DB §4.9`).
- `scm_credentials` — standard RLS template plus an application-layer role gate (only `org-admin` may INSERT/UPDATE; `org-viewer` is denied at the API layer).
- `provenance_records` — append-only; no UPDATE/DELETE grants to any application role.

### 3.4 Session-variable setter contract

The application MUST issue `SET LOCAL app.org_id = '<uuid>'; SET LOCAL app.user_id = '<uuid|scanner|system>'; SET LOCAL app.role = '<role>';` on every PostgreSQL connection checkout, **before any query runs**. This is `CMP-CP-01`'s responsibility on customer-request paths. Server-internal jobs (Attestor re-runs, scheduler, worker callback) use `SET LOCAL app.role = 'system'`; the `system` role is the `scanipy_system` DB role and has `BYPASSRLS`. Connections without the setting evaluate `current_setting('app.org_id', true) IS NULL`, which makes the RLS predicate false → zero rows / explicit RLS violation.

CP-03 ships a `db/session.py` helper (or augments `BaseDatabase` per the SDD `Purpose:` "reuse the existing `BaseDatabase`") that:

```python
@contextmanager
def acquire_connection(org_id: UUID, user_id: str, role: str) -> Connection:
    conn = pool.checkout()
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL app.org_id = %s", (str(org_id),))
            cur.execute("SET LOCAL app.user_id = %s", (str(user_id),))
            cur.execute("SET LOCAL app.role = %s", (role,))
        yield conn
    finally:
        pool.checkin(conn)        # SET LOCAL is auto-reset at transaction close
```

The connection-pool integration test (`DOC-DB §3.4`) verifies that a connection without the setting cannot read any row.

### 3.5 Per-table migration shapes

For exact column-by-column shapes, indices, and constraints, see `DOC-DB §4.1`–`§4.15`. CP-03 reproduces them faithfully in its `upgrade()` migrations. The implementation agent MUST treat `DOC-DB §4` as the column-shape source-of-truth; deviations are documentation-hygiene bugs to be filed as CLAR-CP-03-* before merging.

Tables owned by CP-03 directly (column shape decisions live here): `orgs`, `projects`, `codebases`, `org_policies`, `memberships`. Tables for which CP-03 is the migration vehicle and the owner is another component: as listed in §3.2.

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| Existing `BaseDatabase` connection facility | v2 codebase (or its v3.2 reimplementation) | CP-03 reuses it per the SDD `Purpose:` clause. |
| Per-table column shapes | `DOC-DB §4.1`–`§4.15` | Authoritative; CP-03 mirrors them in Alembic ops. |
| RLS template | `DOC-DB §3.3` (CLAR-DB-02 DEFERRED working assumption) | Applied to every multi-tenant table; custom policies for `orgs`, `spec_versions`, `scm_credentials`, `provenance_records`. |
| Migration tooling target | CLAR-DEPLOY-03 RESOLVED | PostgreSQL 16 on Amazon RDS; Alembic. |

### 4.2 Outputs / Persisted artifacts

| Output | Location | Contract |
|---|---|---|
| Alembic migration scripts | `db/migrations/versions/<YYYYMMDD>_<NNNN>_<slug>.py` | Each is reversible; migrations split RLS-change from shape-change. |
| `alembic.ini` + `db/migrations/env.py` | repo root | Configures the migration runner. |
| Tenancy schema (the tables themselves) | PostgreSQL 16 RDS instance | Materialized by `alembic upgrade head`. |
| RLS policies | PostgreSQL `pg_policies` catalog | Materialized by the RLS-creation migrations. |
| `db/session.py` (or `BaseDatabase` augmentation) | application source tree | Implements the session-variable setter contract (§3.4). |

### 4.3 Tables enumerated (with owning component)

| Table | Owning component (column shape) | CP-03's role |
|---|---|---|
| `orgs` | CMP-CP-03 | Define + RLS-exempt + migration. |
| `memberships` | CMP-CP-03 / CMP-CP-04 | Define + RLS + migration. |
| `projects` | CMP-CP-03 | Define + RLS + migration. |
| `codebases` | CMP-CP-03 | Define + RLS + migration. |
| `scm_credentials` | CMP-CP-02 | Migration vehicle; column shape from `DOC-DB §4.5`. |
| `org_policies` | CMP-CP-03 | Define + RLS + migration. |
| `snapshots` | CMP-SNAP-01 | Migration vehicle; column shape from `DOC-DB §4.7`. |
| `proposed_specs` | CMP-TRI-02 | Migration vehicle; column shape from `DOC-DB §4.8`. |
| `spec_versions` | CMP-TRI-02 | Migration vehicle; custom RLS per `DOC-DB §4.9`. |
| `scans` | CMP-ORCH-01 (derived; `CLAR-DB-01` DEFERRED) | Migration vehicle; column shape from `DOC-DB §4.11`. |
| `attestations` | CMP-CP-05 | Migration vehicle; column shape from `DOC-DB §4.10`. |
| `findings` | CMP-FND-02 | **Migration vehicle for the INV-1/INV-2/INV-5 NOT NULL discharge** — column shape from `DOC-DB §4.12`. |
| `provenance_records` | CMP-FND-03 | Migration vehicle; append-only; column shape from `DOC-DB §4.13`. |
| `triage_scores` | CMP-TRI-01 | Migration vehicle; split-from-findings INV-3 fence; column shape from `DOC-DB §4.14`. |
| `repartition_events` | CMP-SNAP-04 | Migration vehicle; column shape from `DOC-DB §4.15`. |

---

## 5. Invariants touched

| Invariant | How `CMP-CP-03` discharges it | Test |
|---|---|---|
| **INV-1** (schema layer) | Materializes the `findings.origin` NOT NULL + CHECK `(origin IN ('deterministic-core','oracle-passthrough'))` constraint defined by `CMP-FND-02` in `DOC-DB §4.12`. Also materializes `findings.determinism_partition` NOT NULL and `repartition_events.new_origin = 'oracle-passthrough'` CHECK. | `TST-INV-1-FND-02 [FORTHCOMING]` (NOT NULL violation when origin missing). |
| **INV-2** (schema layer) | Materializes `findings.S_version`, `findings.env_digest`, `snapshots.env_digest`, `provenance_records.S_version`, `provenance_records.env_digest`, `triage_scores.S_version`, `triage_scores.env_digest`, `attestations.S_version`, `attestations.env_digest`, `scans.S_version`, `scans.env_digest` as NOT NULL. | `TST-INV-2-FND-02 [FORTHCOMING]`, `TST-INV-2-SNAP-01 [FORTHCOMING]`. |
| **INV-5** (schema layer) | Materializes `findings.cpg_order_hash` (sha256, 32 bytes) paired with `findings.cpg_order_hash_annotation` literal CHECK `= 'canonical iff fingerprint_class = strong'`. Same on `provenance_records`. The annotation column exists as a row-level field and cannot be stripped at SARIF emission. | `TST-INV-5-FND-02 [FORTHCOMING]` (annotation absent → CHECK violation). |
| **CLAR-DEPLOY-16 layer 2** | RLS policies on every multi-tenant table + `app.org_id` session-variable setter. A connection without the setting cannot read or write any row. | `TST-AC-CP-01a [FORTHCOMING]` (cross-org access denied at the RLS layer); `TST-AC-CP-03a [FORTHCOMING]` (migrations apply RLS on every multi-tenant table). |

See `DOC-INV.md §3, §4, §7` for verbatim invariant statements; do not paraphrase here. See `DOC-DB §5` for the full invariant-discharge matrix.

---

## 6. Algorithm / data flow

```
operator runs:        alembic upgrade head
                              |
                              v
                     Alembic loads db/migrations/versions/*.py in
                     dependency order (topological by table).
                              |
                              v
                     For each revision:
                       upgrade() runs under scanipy_migrations role
                              (no application read/write privileges).
                              |
                              v
                     CREATE TABLE / ALTER TABLE / CREATE INDEX statements
                     materialize the column shape from DOC-DB §4.
                              |
                              v
                     Subsequent RLS-policy migrations:
                       ALTER TABLE ... ENABLE ROW LEVEL SECURITY;
                       CREATE POLICY tenant_isolation_select ...;
                       CREATE POLICY tenant_isolation_modify ...;
                              |
                              v
                     Custom policies for orgs (none), spec_versions
                       (scope='global' universal), scm_credentials
                       (additional role gate), provenance_records
                       (no UPDATE/DELETE grants).
                              |
                              v
                     CI gate (CMP-CI-01): alembic downgrade base
                       MUST cleanly reverse every migration on a fresh
                       database (the AC-CP-03a falsifier).

runtime:              app process opens connection ->
                       CMP-CP-01 issues SET LOCAL app.{org_id,user_id,role}
                       -> all subsequent SELECT/INSERT/UPDATE/DELETE
                       respect RLS predicates against current_setting('app.org_id').
                       Connection without SET -> RLS returns zero rows /
                       explicit "permission denied" on INSERT.
```

The connection-pool guard (§3.4) is non-bypassable: every code path that acquires a DB connection routes through `acquire_connection(org_id, user_id, role)`.

---

## 7. Failure modes and error contracts

| Failure | Detected by | Response | Side effect |
|---|---|---|---|
| `alembic upgrade head` fails mid-migration | Alembic | Transactional rollback of the failing revision; prior revisions remain applied. **Migration is not committed unless the entire revision succeeds.** | Re-run after fix; staging dry-run was supposed to catch this (CLAR-DEPLOY-07). |
| `alembic downgrade base` leaves orphan objects | CI gate (`CMP-CI-01`) | **Hard CI fail.** This is the AC-CP-03a falsifier. | The migration revision is reworked; PR cannot merge. |
| RLS policy creation fails on a tenant table | Alembic / Postgres | **Fail closed.** Transactional rollback of the migration; the table remains without RLS. CP-03 MUST refuse to leave a multi-tenant table without an RLS policy. | A subsequent migration that creates the table without its RLS policy is rejected by CI (CMP-CI-01 schema-linter check: every multi-tenant table has both `_select` and `_modify` policies). |
| Connection checked out without `SET LOCAL app.org_id` | DB-side RLS | `current_setting('app.org_id', true) IS NULL` → predicate false → zero rows / RLS violation on write. | This is the defense-in-depth backstop for a programming bug in CP-01. The connection-pool integration test (`DOC-DB §3.4`) verifies it. |
| Session-variable name renamed (CLAR-DB-02 resolution) | Code review | Coordinated rename across CP-01 setter + CP-03 RLS policy DDL. | A rename-only migration is filed; no data shape changes. |
| v2 → v3.2 migration of legacy tenant data | (not in CP-03's scope) | **DEFERRED via `CLAR-MIGRATION-01`.** Working assumption: new-env-only; legacy data is not migrated by CP-03. If the migration is committed later, a separate component (TBD) handles it. | Surface this gap explicitly to anyone seeking to import v2 data. |

**Fail-closed posture.** A migration error never leaves a multi-tenant table without RLS. A connection without the session variable never reads any row. These are mechanical backstops, not policies — they are enforced by the DB engine itself.

---

## 8. Provenance threading

CP-03 itself **does not write application rows** and therefore does not thread provenance fields at runtime. CP-03's threading responsibility is at the **schema level**:

| Provenance field | CP-03 contribution |
|---|---|
| `origin`, `S_version`, `env_digest`, `cpg_order_hash`, `cpg_order_hash_annotation` | NOT NULL constraints + CHECK constraints (the annotation literal pinning) on `findings`. Without CP-03's migration, no INSERT into `findings` can satisfy INV-1/INV-2/INV-5. |
| `determinism_partition`, `engine`, `fingerprint_class`, `slice_fingerprint`, `precondition_status` | NOT NULL on `findings`; CHECK on enums. |
| `S_version`, `env_digest` on `snapshots`, `scans`, `provenance_records`, `triage_scores`, `attestations` | NOT NULL across the lineage; verifies that no provenance-bearing row escapes without the INV-2 fields. |
| `org_id` | NOT NULL FK → `orgs(id)` on every multi-tenant table; backed by RLS. |

CP-03 also enforces the **INV-3 fence at the grant level** (`DOC-DB §4.14`):

```sql
GRANT INSERT ON triage_scores TO scanipy_triage;
REVOKE ALL ON findings FROM scanipy_triage;
GRANT SELECT (id, class, rule_id, severity, physical_location, message)
  ON findings TO scanipy_triage;
```

This shipped as part of the `triage_scores` migration ensures `CMP-TRI-01` cannot write to `findings` even if a programming bug attempts it — the DB rejects the grant.

**Must NOT touch.** CP-03 does not write to any application table at runtime. Migration runs are operator-initiated and run under `scanipy_migrations` (separate role).

---

## 9. Acceptance criteria cross-reference

The following AC is quoted **verbatim** from `SDD.md §10 CMP-CP-03`. Paraphrasing is a contract break (RULE-4).

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-CP-03a** | > Migrations apply forward and roll back cleanly on a fresh database. | `TST-AC-CP-03a` `[FORTHCOMING]` |

The AC-CP-03a falsifier is the CI gate (`CMP-CI-01`):

1. Provision a fresh PostgreSQL 16 database.
2. Run `alembic upgrade head` — every revision applies successfully.
3. Run `alembic downgrade base` — every revision reverses cleanly; no orphan tables / indices / policies / triggers / sequences.
4. Re-run `alembic upgrade head` — idempotent; produces the same schema state.

Schema-linter checks bundled into the same CI gate (recommended by this document; not a separate AC):

- Every multi-tenant table has both `tenant_isolation_select` and `tenant_isolation_modify` policies (or a documented custom-policy exception).
- Every column listed in `DOC-DB §5` as NOT NULL is materialized NOT NULL.
- Every CHECK constraint listed in `DOC-DB §4` is materialized.

Invariant tests cross-referenced (the schema-level INV-1/INV-2/INV-5 tests run against the CP-03-materialized DB):

- `TST-INV-1-FND-02 [FORTHCOMING]` — INSERT missing `origin` is rejected.
- `TST-INV-2-FND-02 [FORTHCOMING]` — INSERT missing `S_version` or `env_digest` is rejected.
- `TST-INV-2-SNAP-01 [FORTHCOMING]` — `snapshots.env_digest` NOT NULL.
- `TST-INV-5-FND-02 [FORTHCOMING]` — `cpg_order_hash_annotation` literal pinned.
- `TST-AC-CP-01a [FORTHCOMING]` — cross-org access denied (exercises the RLS that CP-03 ships).

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-CP-03 |
|---|---|---|---|
| `CLAR-DEPLOY-03` | Relational-DB engine + version | **RESOLVED** | PostgreSQL 16 + Alembic. |
| `CLAR-DEPLOY-15` | Per-artifact retention | **RESOLVED** | Per-table retention enforced via row-level `expires_at` + S3 Object Lock for the 7-year classes; see `DOC-DB §7`. |
| `CLAR-DEPLOY-16` | Per-tenant isolation backstop | **RESOLVED** | CP-03 implements layer 2 (RLS) of three layers. |
| `CLAR-DB-01` | `scans` table not explicitly enumerated by SDD CP-03 | **DEFERRED** | `DOC-DB §4.11` adds it as a derived table; CP-03 ships its migration. SDD listing should be ratified by the Architect Agent. Working assumption: include `scans` in the migration set. |
| `CLAR-DB-02` | RLS session-variable scheme (`app.org_id`, `app.user_id`, `app.role`) | **DEFERRED** | `DOC-DB §3.2` proposes the scheme; sign-off needed from SRE/DevOps + Security Analyst. CP-03 uses these names as the working assumption; a rename is a coordinated migration. |
| `CLAR-MIGRATION-01` | Legacy data migration plan from v2 to v3.2 | **DEFERRED** | Default = new-env-only. If migration is committed, a separate ETL component (TBD) handles it; CP-03 does not implement the import path. |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | Owner field in §1 remains DEFERRED. |

No new CLAR-CP-03-* are filed by this document; every AC is unambiguous given CLAR-DEPLOY-03, CLAR-DEPLOY-15, CLAR-DEPLOY-16, and the (DEFERRED but documented) CLAR-DB-01/02.

---

## 11. References

- `SDD.md §10 CMP-CP-03` — verbatim AC.
- `PLAN.md §"Phase 6 — Multi-tenant control plane"`.
- `docs/cross-cutting/DOC-DB.md` — full schema (§4), RLS (§3), invariant-discharge matrix (§5), retention (§7).
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — CLAR-DEPLOY-03 (Postgres + Alembic), 15 (retention), 16 (isolation).
- `docs/cross-cutting/DOC-INV.md` §3, §4, §7 — INV-1/2/5 verbatim.
- `docs/cross-cutting/DOC-PROVENANCE.md` — fields threaded through `provenance_records`.
- `docs/components/DOC-CMP-CP-01.md` (sibling) — sets `app.org_id` against the RLS policies shipped here.
- `docs/components/DOC-CMP-CP-02.md` (sibling) — writes `orgs.kms_cmk_arn` against the schema shipped here.
- `docs/components/DOC-CMP-FND-02.md` (sibling, forthcoming) — owns `findings` column shape; CP-03 ships the migration.
- `docs/components/DOC-CMP-SNAP-01.md` (sibling) — owns `snapshots` column shape; CP-03 ships the migration.
- `.claude/rules/00-global.md` RULE-6 (provenance threading); `.claude/rules/02-provenance.md`.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-CP-03`.*
