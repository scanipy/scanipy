# DOC-DB — Persistence schema reference

**Status:** ACTIVE (Phase 0 cross-cutting reference)
**Owner:** Documentation Manager Agent
**Source of truth:** `SDD.md` §8 (CMP-FND-01..03), §10 (CMP-CP-01..05). Where this document and the SDD disagree, the SDD wins.
**Substrate:** PostgreSQL 16 on Amazon RDS (`DOC-DEPLOY-DECISIONS.md` CLAR-DEPLOY-03).

This document is the canonical reference for the Scanipy v3.2 relational schema. Every table that the platform persists is enumerated here with column types, nullability, defaults, constraints, foreign keys, indices, RLS policies, and retention. Where SDD pins a behaviour (e.g. NOT NULL on `findings.origin`), this document propagates the SDD constraint verbatim. Where SDD leaves a column type unpinned, this document proposes a reasonable PostgreSQL 16 type from `DOC-DEPLOY-DECISIONS.md` CLAR-DEPLOY-03 (`uuid`, `jsonb`, `bytea`), and files `CLAR-DB-*` if a specific shape is contested.

Cross-cutting references this document depends on:

- `.claude/rules/00-global.md` — RULE-6 provenance threading (NOT NULL discharge).
- `.claude/rules/01-invariants.md` — INV-1, INV-2, INV-5 schema-level enforcement.
- `.claude/rules/02-provenance.md` — required fields per `Finding`.
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — CLAR-DEPLOY-03 (PostgreSQL 16, Alembic), CLAR-DEPLOY-15 (retention), CLAR-DEPLOY-16 (per-tenant isolation: S3 prefix + RLS + KMS).
- `docs/cross-cutting/DOC-API.md` — response shapes derived from these tables.
- `docs/cross-cutting/DOC-SARIF.md` — SARIF emission for the `findings` table.

---

## 1. Purpose

DOC-DB defines:

1. Every table the platform persists (under tenancy and outside).
2. Column-by-column shape: name, type, nullability, default, FK, constraint.
3. Indices (including required partial / functional indices).
4. PostgreSQL Row-Level Security (RLS) policies per multi-tenant table.
5. JSONB sub-schemas where used.
6. The Alembic migration ordering required for clean forward / rollback (AC-CP-03a).
7. The retention policy per artifact class (CLAR-DEPLOY-15).
8. The invariant-discharge map from NOT NULL constraints to INV-1/INV-2.

It does NOT define:

- S3 key paths — see CLAR-DEPLOY-02 in `DOC-DEPLOY-DECISIONS.md`.
- KMS key strategy — see CLAR-DEPLOY-04.
- Provenance chain semantics — see `DOC-PROVENANCE.md` (separate Phase 0 doc).

---

## 2. Migration framework

- **Tool:** Alembic (Python).
- **Location:** `db/migrations/versions/`.
- **Naming:** `<YYYYMMDD>_<NNNN>_<slug>.py`, e.g. `20260523_0001_initial_tenancy.py`.
- **Migration ordering:** topological by table dependency (see §3 below).
- **CI gate:** Alembic upgrade-then-downgrade against a fresh database is a CMP-CI-01 hard gate (discharges AC-CP-03a).
- **Per-revision content:**
  - Each migration is reversible (`upgrade()` + `downgrade()`).
  - Migrations that change RLS policies are split from migrations that change table shape; never combined.
- **Production gates:**
  - No migration is applied without a successful staging-environment dry-run (logged to OpenTelemetry, CLAR-DEPLOY-07).
  - All migrations run under a database role with no application read/write privileges.

---

## 3. Tenancy and Row-Level Security

### 3.1 Tenancy column

Every multi-tenant table carries:

```
org_id uuid NOT NULL REFERENCES orgs(id)
```

### 3.2 Session variable

The application sets a PostgreSQL session variable on every connection checkout:

```sql
SET LOCAL app.org_id = '<uuid-string-from-jwt>';
SET LOCAL app.user_id = '<uuid-string-from-jwt>';
SET LOCAL app.role = '<role-from-jwt>';
```

These three variables back the RLS predicates below. Server-internal operations (Attestor re-runs, scheduler, worker callback) set:

```sql
SET LOCAL app.role = 'system';
```

The `system` role bypasses RLS via the `BYPASSRLS` privilege on the dedicated `scanipy_system` database role (used only for server-internal jobs).

### 3.3 Standard RLS policy template

Every multi-tenant table enables RLS with the following pair of policies:

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

### 3.4 Connection-pool guard

The application MUST issue `SET LOCAL app.org_id = ...` on every checkout before any query runs. A missing setting throws `current_setting('app.org_id', true) IS NULL`, which makes the RLS predicate evaluate to false → zero rows / error. The connection-pool integration test verifies that a connection without the setting cannot read any row.

---

## 4. Table catalog

Migration order (each table depends only on those listed before it):

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
scans
attestations
findings
provenance_records
triage_scores
repartition_events
```

`scans` precedes `attestations`, `findings`, and `repartition_events` because all three foreign-key into it. See §4.11 for the table definition and the `CLAR-DB-01` schema-derivation note.

### 4.1 `orgs`

- **Owning component:** CMP-CP-03.
- **Purpose:** tenant root. Anchor for every other multi-tenant table.

| Column | Type | Nullability | Default | Constraint / FK | Notes |
|---|---|---|---|---|---|
| `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PRIMARY KEY | tenant identifier |
| `name` | `text` | NOT NULL | — | UNIQUE | display name |
| `kms_cmk_arn` | `text` | NULL | — | — | per-tenant CMK ARN (CLAR-DEPLOY-04) |
| `auth0_org_id` | `text` | NULL | — | UNIQUE | Auth0 organization id (CLAR-DEPLOY-10) |
| `status` | `text` | NOT NULL | `'active'` | CHECK (`status IN ('active','suspended','deleted')`) | |
| `created_at` | `timestamptz` | NOT NULL | `now()` | — | |
| `updated_at` | `timestamptz` | NOT NULL | `now()` | — | |

- **Indices:** PK; UNIQUE on `name`; UNIQUE on `auth0_org_id`.
- **RLS:** No row-level policy (this table is not multi-tenant; it *defines* tenancy). Application-level role check restricts modification to `org-admin` (own row) and a control-plane internal role.

### 4.2 `memberships`

- **Owning component:** CMP-CP-03 / CMP-CP-04.

| Column | Type | Nullability | Default | Constraint / FK | Notes |
|---|---|---|---|---|---|
| `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PRIMARY KEY | |
| `org_id` | `uuid` | NOT NULL | — | FK → `orgs(id)` | |
| `user_id` | `uuid` | NOT NULL | — | — | Auth0 `sub` mapped to a Scanipy uuid |
| `role` | `text` | NOT NULL | — | CHECK (`role IN ('org-admin','org-viewer','scanner')`) | CLAR-DEPLOY-12 |
| `created_at` | `timestamptz` | NOT NULL | `now()` | — | |

- **Indices:** PK; UNIQUE `(org_id, user_id)`; INDEX `(user_id)`.
- **RLS:** standard template (§3.3).

### 4.3 `projects`

| Column | Type | Nullability | Default | Constraint / FK |
|---|---|---|---|---|
| `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PRIMARY KEY |
| `org_id` | `uuid` | NOT NULL | — | FK → `orgs(id)` |
| `name` | `text` | NOT NULL | — | — |
| `created_at` | `timestamptz` | NOT NULL | `now()` | — |

- **Indices:** PK; UNIQUE `(org_id, name)`.
- **RLS:** standard template.

### 4.4 `codebases`

| Column | Type | Nullability | Default | Constraint / FK |
|---|---|---|---|---|
| `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PRIMARY KEY |
| `org_id` | `uuid` | NOT NULL | — | FK → `orgs(id)` |
| `project_id` | `uuid` | NULL | — | FK → `projects(id)` |
| `name` | `text` | NOT NULL | — | — |
| `scm_provider` | `text` | NOT NULL | — | CHECK (`scm_provider IN ('github','gitlab','bitbucket','azure-devops')`) |
| `scm_repo_url` | `text` | NOT NULL | — | — |
| `default_branch` | `text` | NULL | — | — |
| `created_at` | `timestamptz` | NOT NULL | `now()` | — |
| `updated_at` | `timestamptz` | NOT NULL | `now()` | — |

- **Indices:** PK; UNIQUE `(org_id, scm_provider, scm_repo_url)`; INDEX `(org_id, project_id)`.
- **RLS:** standard template.

### 4.5 `scm_credentials`

- Encrypted at rest via `CMP-CP-02` (CLAR-DEPLOY-04).

| Column | Type | Nullability | Default | Constraint / FK | Notes |
|---|---|---|---|---|---|
| `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PRIMARY KEY | |
| `org_id` | `uuid` | NOT NULL | — | FK → `orgs(id)` | |
| `codebase_id` | `uuid` | NOT NULL | — | FK → `codebases(id) ON DELETE CASCADE` | |
| `auth_mode` | `text` | NOT NULL | — | CHECK (`auth_mode IN ('pat','app','oauth','ssh-key')`) | |
| `kms_key_arn` | `text` | NOT NULL | — | — | per-tenant CMK |
| `ciphertext` | `bytea` | NOT NULL | — | — | KMS envelope-encrypted blob |
| `display_fingerprint` | `text` | NOT NULL | — | — | sha256 of plaintext, display only |
| `label` | `text` | NULL | — | — | |
| `created_at` | `timestamptz` | NOT NULL | `now()` | — | |
| `rotated_at` | `timestamptz` | NULL | — | — | |

- **Indices:** PK; INDEX `(org_id, codebase_id)`.
- **RLS:** standard template + an additional role-gate that allows only `org-admin` to INSERT/UPDATE; `org-viewer` cannot SELECT this table (handled at the application layer; RLS still constrains tenant boundary).

### 4.6 `org_policies`

Per-org configuration (default detector set, severity overrides, suppression rules).

| Column | Type | Nullability | Default | Constraint / FK |
|---|---|---|---|---|
| `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PRIMARY KEY |
| `org_id` | `uuid` | NOT NULL | — | FK → `orgs(id)` |
| `policy` | `jsonb` | NOT NULL | `'{}'::jsonb` | — |
| `version` | `int` | NOT NULL | `1` | — |
| `created_at` | `timestamptz` | NOT NULL | `now()` | — |
| `updated_at` | `timestamptz` | NOT NULL | `now()` | — |

- **Indices:** PK; UNIQUE `(org_id, version)`.
- **RLS:** standard template.

### 4.7 `snapshots`

- **Owning component:** CMP-SNAP-01 (CMP-CP-03 ships the migration).

| Column | Type | Nullability | Default | Constraint / FK | Notes |
|---|---|---|---|---|---|
| `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PRIMARY KEY | |
| `org_id` | `uuid` | NOT NULL | — | FK → `orgs(id)` | |
| `codebase_id` | `uuid` | NOT NULL | — | FK → `codebases(id) ON DELETE CASCADE` | |
| `commit_sha` | `text` | NOT NULL | — | CHECK (`commit_sha ~ '^[0-9a-f]{40}$'`) | |
| `env_digest` | `text` | NOT NULL | — | CHECK (`env_digest ~ '^sha256:[0-9a-f]{64}$'`) | **INV-2 NOT NULL** |
| `precondition_status` | `text` | NOT NULL | — | CHECK (`precondition_status IN ('closed-world','degraded','full-reparse')`) | AC-SNAP-01b |
| `cpg_tarball_uri` | `text` | NOT NULL | — | — | S3 key per CLAR-DEPLOY-02 |
| `reverse_symbol_index_uri` | `text` | NOT NULL | — | — | |
| `dynamic_call_graph_uri` | `text` | NOT NULL | — | — | |
| `delta_g_uri` | `text` | NULL | — | — | NULL on full-reparse |
| `precondition_status_record_uri` | `text` | NOT NULL | — | — | |
| `parent_snapshot_id` | `uuid` | NULL | — | FK → `snapshots(id)` | for incremental |
| `created_at` | `timestamptz` | NOT NULL | `now()` | — | |
| `expires_at` | `timestamptz` | NOT NULL | `now() + interval '90 days'` | — | CLAR-DEPLOY-15 |

- **Indices:** PK; UNIQUE `(codebase_id, commit_sha, env_digest)`; INDEX `(org_id, codebase_id, created_at DESC)`.
- **RLS:** standard template.

### 4.8 `proposed_specs`

LLM-generated candidate specs awaiting e-process gate decision (CMP-TRI-02). Never on the deterministic-core path.

| Column | Type | Nullability | Default | Constraint / FK |
|---|---|---|---|---|
| `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PRIMARY KEY |
| `org_id` | `uuid` | NOT NULL | — | FK → `orgs(id)` |
| `spec_body` | `jsonb` | NOT NULL | — | (DSL AST per `DOC-DSL.md`) |
| `class` | `text` | NOT NULL | — | — |
| `e_process_state` | `jsonb` | NOT NULL | `'{}'::jsonb` | (`E_t`, evaluation history) |
| `decision` | `text` | NOT NULL | `'pending'` | CHECK (`decision IN ('pending','accepted','rejected','quarantined')`) |
| `accepted_as_spec_version_id` | `uuid` | NULL | — | FK → `spec_versions(id)` |
| `created_at` | `timestamptz` | NOT NULL | `now()` | — |
| `decided_at` | `timestamptz` | NULL | — | — |

- **Indices:** PK; INDEX `(org_id, decision)`; INDEX `(class, decision)`.
- **RLS:** standard template.

### 4.9 `spec_versions`

The version-pinned accepted-spec set `S`. Every finding references one of these (`findings.S_version`).

| Column | Type | Nullability | Default | Constraint / FK |
|---|---|---|---|---|
| `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PRIMARY KEY |
| `org_id` | `uuid` | NULL | — | FK → `orgs(id)` |
| `S_version` | `text` | NOT NULL | — | CHECK (semver regex) |
| `scope` | `text` | NOT NULL | — | CHECK (`scope IN ('global','customer')`) |
| `spec_set` | `jsonb` | NOT NULL | — | the accepted DSL ASTs |
| `spec_provenance` | `text` | NOT NULL | `'global-unrevalidated'` | CHECK (`spec_provenance IN ('global-unrevalidated','global-revalidated','customer')`) |
| `created_at` | `timestamptz` | NOT NULL | `now()` | — |
| `revalidated_at` | `timestamptz` | NULL | — | — |

- **Indices:** PK; UNIQUE `(org_id, S_version)` WHERE `org_id IS NOT NULL`; UNIQUE `(S_version)` WHERE `scope = 'global'`.
- **RLS:** custom — `scope = 'global'` rows are readable by every tenant; `scope = 'customer'` follows the standard template.

```sql
CREATE POLICY spec_versions_select ON spec_versions FOR SELECT USING (
  scope = 'global' OR org_id::text = current_setting('app.org_id', true)
);
CREATE POLICY spec_versions_modify ON spec_versions FOR ALL USING (
  org_id::text = current_setting('app.org_id', true)
) WITH CHECK (
  org_id::text = current_setting('app.org_id', true)
);
```

### 4.10 `attestations`

Attestor pipeline output rows (CMP-CP-05).

| Column | Type | Nullability | Default | Constraint / FK |
|---|---|---|---|---|
| `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PRIMARY KEY |
| `org_id` | `uuid` | NOT NULL | — | FK → `orgs(id)` |
| `scan_id` | `uuid` | NOT NULL | — | FK → `scans(id) ON DELETE CASCADE` |
| `partition` | `text` | NOT NULL | — | CHECK (`partition IN ('core','oracle')`) |
| `attestor_hash` | `bytea` | NOT NULL | — | (sha256 of the canonical SARIF blob over this partition) |
| `result` | `text` | NOT NULL | — | CHECK (`result IN ('pass','fail','rate-only')`) |
| `reproduction_rate` | `numeric(5,4)` | NULL | — | NULL on core partition; 0..1 on oracle partition |
| `S_version` | `text` | NOT NULL | — | INV-2 |
| `env_digest` | `text` | NOT NULL | — | INV-2 |
| `signed_chain_id` | `uuid` | NULL | — | FK → `provenance_records(id)` |
| `created_at` | `timestamptz` | NOT NULL | `now()` | — |

- **Indices:** PK; UNIQUE `(scan_id, partition)`; INDEX `(org_id, created_at DESC)`.
- **RLS:** standard template.

The `scans` table is implied by the foreign key but is not listed in `SDD.md CMP-CP-03`. **Schema note:** `scans` is added by this document as a derived table required by the API layer (`POST /api/v1/scans`). See §4.11.

### 4.11 `scans` (derived)

> **Schema-derivation note:** `scans` is required for the API surface (`POST /api/v1/scans`, `GET /api/v1/scans/{id}`) but is not explicitly enumerated by `SDD.md CMP-CP-03`. It is the natural sibling of `snapshots` and is added here. Filed as `CLAR-DB-01` (see §7) for sign-off.

| Column | Type | Nullability | Default | Constraint / FK |
|---|---|---|---|---|
| `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PRIMARY KEY |
| `org_id` | `uuid` | NOT NULL | — | FK → `orgs(id)` |
| `codebase_id` | `uuid` | NOT NULL | — | FK → `codebases(id) ON DELETE CASCADE` |
| `snapshot_id` | `uuid` | NOT NULL | — | FK → `snapshots(id)` |
| `commit_sha` | `text` | NOT NULL | — | CHECK (40-hex) |
| `S_version` | `text` | NOT NULL | — | INV-2 |
| `env_digest` | `text` | NOT NULL | — | INV-2 |
| `detector_ids` | `text[]` | NOT NULL | — | |
| `status` | `text` | NOT NULL | `'queued'` | CHECK (`status IN ('queued','snapshotting','analysing','normalising','attested','failed')`) |
| `policy_overrides` | `jsonb` | NOT NULL | `'{}'::jsonb` | |
| `idempotency_key` | `uuid` | NULL | — | — |
| `started_at` | `timestamptz` | NOT NULL | `now()` | |
| `finished_at` | `timestamptz` | NULL | — | |

- **Indices:** PK; UNIQUE `(org_id, idempotency_key)` WHERE `idempotency_key IS NOT NULL`; INDEX `(codebase_id, started_at DESC)`; INDEX `(org_id, status)`.
- **RLS:** standard template.

### 4.12 `findings` — INV-1, INV-2, INV-5 anchor

- **Owning component:** CMP-FND-02.
- **Critical NOT NULL constraints** (discharge INV-1, INV-2, INV-5):

| Column | Type | Nullability | Default | Constraint / FK | Notes |
|---|---|---|---|---|---|
| `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PRIMARY KEY | |
| `org_id` | `uuid` | NOT NULL | — | FK → `orgs(id)` | |
| `codebase_id` | `uuid` | NOT NULL | — | FK → `codebases(id) ON DELETE CASCADE` | |
| `scan_id` | `uuid` | NOT NULL | — | FK → `scans(id) ON DELETE CASCADE` | |
| `snapshot_id` | `uuid` | NOT NULL | — | FK → `snapshots(id)` | |
| `commit_sha` | `text` | NOT NULL | — | CHECK (40-hex) | |
| `class` | `text` | NOT NULL | — | CHECK (allowed list, see §6) | |
| `rule_id` | `text` | NOT NULL | — | — | |
| `severity` | `text` | NOT NULL | — | CHECK (`severity IN ('info','low','medium','high','critical')`) | |
| `message` | `text` | NOT NULL | — | — | |
| `physical_location` | `jsonb` | NOT NULL | — | (uri, start_line, etc.) | |
| `origin` | `text` | **NOT NULL** | — | CHECK (`origin IN ('deterministic-core','oracle-passthrough')`) | **INV-1** |
| `determinism_partition` | `text` | **NOT NULL** | — | CHECK (`determinism_partition IN ('deterministic-core','oracle-passthrough')`) | derived from engine |
| `engine` | `text` | NOT NULL | — | CHECK (`engine IN ('ifds','ide','semgrep','cpg-query','external')`) | |
| `S_version` | `text` | **NOT NULL** | — | — | **INV-2** |
| `env_digest` | `text` | **NOT NULL** | — | CHECK (sha256:hex64) | **INV-2** |
| `cpg_order_hash` | `bytea` | **NOT NULL** | — | CHECK (`octet_length(cpg_order_hash) = 32`) | sha256 |
| `cpg_order_hash_annotation` | `text` | **NOT NULL** | `'canonical iff fingerprint_class = strong'` | CHECK (`cpg_order_hash_annotation = 'canonical iff fingerprint_class = strong'`) | **INV-5** — the column exists and is pinned literally |
| `fingerprint_class` | `text` | NOT NULL | — | CHECK (`fingerprint_class IN ('strong','weak')`) | |
| `slice_fingerprint` | `bytea` | NOT NULL | — | CHECK (`octet_length(slice_fingerprint) = 32`) | |
| `witness_blob_uri` | `text` | NULL | — | — | oracle findings may omit |
| `precondition_status` | `text` | NOT NULL | — | CHECK (same as snapshots) | |
| `spec_provenance` | `text` | NULL | — | CHECK (`spec_provenance IN ('global-unrevalidated','global-revalidated','customer')`) | NULL when finding does not depend on a revalidatable spec |
| `status` | `text` | NOT NULL | `'open'` | CHECK (`status IN ('open','suppressed','fixed')`) | INV-3 fence |
| `suppression_reason` | `text` | NULL | — | CHECK (`(status = 'suppressed') = (suppression_reason IS NOT NULL)`) | |
| `created_at` | `timestamptz` | NOT NULL | `now()` | — | |
| `updated_at` | `timestamptz` | NOT NULL | `now()` | — | |

- **Indices:**
  - PK on `id`.
  - **Required partial index `(codebase_id, slice_fingerprint)` for cross-scan baseline lookup (CMP-FND-02 AC-FND-02a):**
    ```sql
    CREATE INDEX findings_codebase_slice_idx
      ON findings (codebase_id, slice_fingerprint);
    ```
  - `(scan_id)` for listing by scan.
  - `(org_id, created_at DESC)` for org-wide list.
  - `(class, severity)` for filter.
  - `(origin)` partial: `WHERE origin = 'deterministic-core'` (Attestor scan).
- **RLS:** standard template.
- **Trigger:** `updated_at` is set to `now()` on every UPDATE.

The `triage_score` and `triage_reason` columns are **deliberately split into a separate table** (`triage_scores`, §4.14) so that `CMP-TRI-01` cannot write to `findings` (INV-3 enforcement at the schema level — `CMP-TRI-01` is granted INSERT/UPDATE on `triage_scores` only, never on `findings`).

### 4.13 `provenance_records`

- **Owning component:** CMP-FND-03.
- **Append-only.** The signed audit chain — one `record_type='chain'` row per finding, plus scan-level rows for the other record types. **This is the canonical DDL** for `provenance_records` (CLAR-FND-01 resolution, 2026-05-23): the chain is materialised **column-per-link** (not an opaque `jsonb` payload) so INV-1/INV-2/INV-5 are enforced by the schema itself. `DOC-PROVENANCE §3` is the semantic reference for what each chain-link column carries and §3.2 defines the bytes the signature covers.

| Column | Type | Nullability | Default | Constraint / FK | Notes |
|---|---|---|---|---|---|
| `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PRIMARY KEY | referenced by `attestations.signed_chain_id`, `repartition_events.provenance_record_id` |
| `parent_record_id` | `uuid` | NULL | — | FK → `provenance_records(id)` | set on `repartition` rows |
| `record_type` | `text` | NOT NULL | — | CHECK (`record_type IN ('chain','repartition','attestation','spec-acceptance','witness-update')`) | `chain` = per-finding base record |
| `org_id` | `uuid` | NOT NULL | — | FK → `orgs(id)` | |
| `codebase_id` | `uuid` | NOT NULL | — | FK → `codebases(id) ON DELETE CASCADE` | link 1 (source commit) |
| `commit_sha` | `text` | NOT NULL | — | | link 1 (40 hex) |
| `scm_provider` | `text` | NOT NULL | — | | `github`\|`gitlab`\|… |
| `scan_id` | `uuid` | NOT NULL | — | FK → `scans(id) ON DELETE CASCADE` | |
| `finding_id` | `uuid` | NULL | — | FK → `findings(id) ON DELETE CASCADE` | NULL for scan-level record types |
| `snapshot_id` | `uuid` | NOT NULL | — | FK → `snapshots(id)` | link 2 |
| `snapshot_digest` | `text` | NOT NULL | — | | link 2 (sha256) |
| `precondition_status` | `text` | NOT NULL | — | CHECK (`IN ('closed-world','degraded','full-reparse')`) | |
| `S_version` | `text` | NOT NULL | — | | link 3 — INV-2 (every row) |
| `env_digest` | `text` | NOT NULL | — | | link 4 — INV-2 (every row) |
| `cpg_order_hash` | `bytea` | NULL | — | | link 5; NULL on `repartition` + scan-level rows |
| `cpg_order_hash_annotation` | `text` | NOT NULL | `'canonical iff fingerprint_class = strong'` | CHECK (pinned literal) | INV-5 |
| `fingerprint_class` | `text` | NULL | — | CHECK (`IN ('strong','weak')`) | |
| `witness_blob_uri` | `text` | NULL | — | | link 6 |
| `slice_fingerprint` | `bytea` | NULL | — | | link 6 (sha256) |
| `rule_id` | `text` | NULL | — | | link 7; NULL on scan-level rows |
| `spec_id` | `text` | NULL | — | | `S`-derived rules; spec id for `spec-acceptance` |
| `detector_id` | `text` | NULL | — | | link 7 |
| `detector_engine` | `text` | NULL | — | CHECK (`IN ('ifds','ide','semgrep','cpg-query','external')`) | |
| `sarif_hash` | `bytea` | NULL | — | | link 8; NULL on scan-level rows |
| `origin` | `text` | NULL | — | CHECK (`IN ('deterministic-core','oracle-passthrough')`) | link 9 — INV-1; see row-level CHECK |
| `determinism_partition` | `text` | NULL | — | | mirrors `origin` |
| `repartition_reason` | `text` | NULL | — | | only on `repartition` rows |
| `repartition_oracle_id` | `uuid` | NULL | — | FK → `repartition_events(id)` | only on `repartition` rows |
| `kms_key_arn` | `text` | NOT NULL | — | | signing CMK (CLAR-DEPLOY-04) |
| `kms_key_version` | `text` | NOT NULL | — | | envelope-encryption version; preserves prior signatures across rotation |
| `signature` | `bytea` | NOT NULL | — | | KMS asymmetric signature over canonical record bytes |
| `signature_alg` | `text` | NOT NULL | — | CHECK (`signature_alg IN ('RSASSA_PSS_SHA_256','RSASSA_PSS_SHA_384')`) | baseline `RSASSA_PSS_SHA_256` (CLAR-DEPLOY-04) |
| `claim_label` | `text` | NOT NULL | — | CHECK (`IN ('CONDITIONAL_THEOREM','EMPIRICAL','STAGED','UNCONDITIONAL')`) | honest-labeling (INV-6 linkage) |
| `created_at` | `timestamptz` | NOT NULL | `now()` | — | excluded from signed bytes |

- **Row-level CHECK (INV-1):** `CHECK (record_type NOT IN ('chain','repartition') OR origin IS NOT NULL)` — every finding-bearing record carries an `origin`; scan-level records (`attestation`, `spec-acceptance`, `witness-update`) may omit it. `S_version` and `env_digest` are NOT NULL on **every** row (INV-2 binds every provenance record, not only finding rows).
- **Record-type-specific detail is NOT stored here.** e-process metrics `{e_value, threshold, π₀, α}` for `spec-acceptance` live in `spec_versions` / `proposed_specs`; attestation metrics live in `attestations`. The provenance row carries the chain links + signature only, with `spec_id` / `scan_id` as the join key back to the detail.
- **Indices:** PK; INDEX `(codebase_id, commit_sha)`; INDEX `(snapshot_id)`; INDEX `(codebase_id, slice_fingerprint)`; INDEX `(parent_record_id)`; INDEX `(scan_id, record_type)`; INDEX `(finding_id)` WHERE `finding_id IS NOT NULL`.
- **RLS:** standard template (keyed on `org_id`).
- **No UPDATE / DELETE grants** — table is append-only; a correction is a new `record_type='repartition'` row linked by `parent_record_id`.
- **Canonical record-bytes for signing:** `DOC-PROVENANCE §3.2` — all columns except `signature`, `kms_key_version`, and `created_at`, serialized as lexicographically-sorted UTF-8 JSON.

### 4.14 `triage_scores`

- **Owning component:** CMP-TRI-01.
- **Split from `findings` to enforce INV-3 at the schema-grant level.**

| Column | Type | Nullability | Default | Constraint / FK |
|---|---|---|---|---|
| `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PRIMARY KEY |
| `org_id` | `uuid` | NOT NULL | — | FK → `orgs(id)` |
| `finding_id` | `uuid` | NOT NULL | — | FK → `findings(id) ON DELETE CASCADE` |
| `triage_score` | `numeric(5,4)` | NOT NULL | — | CHECK (0..1) |
| `triage_reason` | `text` | NOT NULL | — | bounded JSON-encoded payload |
| `model_id` | `text` | NOT NULL | — | e.g. `claude-sonnet-4-6` (CLAR-DEPLOY-14) |
| `model_version` | `text` | NOT NULL | — | |
| `S_version` | `text` | NOT NULL | — | INV-2 |
| `env_digest` | `text` | NOT NULL | — | INV-2 |
| `created_at` | `timestamptz` | NOT NULL | `now()` | — |

- **Indices:** PK; UNIQUE `(finding_id, model_id, model_version)`; INDEX `(finding_id)`.
- **RLS:** standard template.
- **Grants (INV-3 enforcement):**

```sql
-- The triage role (CMP-TRI-01) can only INSERT into triage_scores;
-- never SELECT/INSERT/UPDATE on findings detection columns.
GRANT INSERT ON triage_scores TO scanipy_triage;
REVOKE ALL ON findings FROM scanipy_triage;
GRANT SELECT (id, class, rule_id, severity, physical_location, message)
  ON findings TO scanipy_triage;
```

### 4.15 `repartition_events`

- **Owning component:** CMP-SNAP-04.
- **Append-only log of differential-oracle re-partition events** (CMP-SNAP-04 AC-SNAP-04a, AC-SNAP-04c).

| Column | Type | Nullability | Default | Constraint / FK |
|---|---|---|---|---|
| `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PRIMARY KEY |
| `org_id` | `uuid` | NOT NULL | — | FK → `orgs(id)` |
| `snapshot_id` | `uuid` | NOT NULL | — | FK → `snapshots(id)` |
| `scan_id` | `uuid` | NULL | — | FK → `scans(id)` |
| `finding_id` | `uuid` | NULL | — | FK → `findings(id) ON DELETE CASCADE` |
| `trigger` | `text` | NOT NULL | — | CHECK (`trigger IN ('differential-oracle-disagreement','operator-override')`) |
| `previous_origin` | `text` | NOT NULL | — | CHECK (`previous_origin = 'deterministic-core'`) |
| `new_origin` | `text` | NOT NULL | — | CHECK (`new_origin = 'oracle-passthrough'`) |
| `evidence_payload` | `jsonb` | NOT NULL | — | oracle disagreement evidence |
| `provenance_record_id` | `uuid` | NOT NULL | — | FK → `provenance_records(id)` |
| `created_at` | `timestamptz` | NOT NULL | `now()` | — |

- **Indices:** PK; INDEX `(snapshot_id, created_at DESC)`; INDEX `(finding_id)`.
- **RLS:** standard template.
- **Side effect contract:** every INSERT into `repartition_events` is paired (within the same transaction) with an UPDATE flipping `findings.origin` from `'deterministic-core'` to `'oracle-passthrough'` for the named `finding_id`, and an INSERT into `provenance_records` with `record_type = 'repartition'`. Enforced via a `BEFORE INSERT` trigger.

---

## 5. Invariant-discharge matrix

The following NOT NULL constraints, taken together, discharge INV-1, INV-2, and INV-5 at the schema layer. They are the bottom-most defence in depth; the application code is the first defence.

| Invariant | Table.column NOT NULL constraints |
|---|---|
| **INV-1** | `findings.origin`, `findings.determinism_partition`, `findings.engine`; `repartition_events.new_origin` |
| **INV-2** | `findings.S_version`, `findings.env_digest`; `snapshots.env_digest`; `provenance_records.S_version`, `provenance_records.env_digest`; `triage_scores.S_version`, `triage_scores.env_digest`; `attestations.S_version`, `attestations.env_digest`; `scans.S_version`, `scans.env_digest` |
| **INV-5** | `findings.cpg_order_hash` paired with `findings.cpg_order_hash_annotation` literal CHECK; same on `provenance_records` |

CMP-FND-02 acceptance criterion **AC-FND-02b** is discharged by these constraints; the corresponding `TST-INV-1-FND-02` and `TST-INV-2-FND-02` tests verify that an INSERT missing any of these fields raises a `NOT NULL violation` error.

---

## 6. Allowed enums (sanity table)

| Column | Allowed values |
|---|---|
| `findings.class` | `injection`, `path-traversal`, `ssrf`, `deserialization`, `xss`, `crypto-misuse`, `authn-authz`, `secrets`, `dep-cve`, `memory-safety` |
| `findings.origin` / `findings.determinism_partition` | `deterministic-core`, `oracle-passthrough` |
| `findings.engine` | `ifds`, `ide`, `semgrep`, `cpg-query`, `external` |
| `findings.severity` | `info`, `low`, `medium`, `high`, `critical` |
| `findings.status` | `open`, `suppressed`, `fixed` |
| `findings.fingerprint_class` | `strong`, `weak` |
| `findings.precondition_status` / `snapshots.precondition_status` | `closed-world`, `degraded`, `full-reparse` |
| `findings.spec_provenance` / `spec_versions.spec_provenance` | `global-unrevalidated`, `global-revalidated`, `customer` |
| `scans.status` | `queued`, `snapshotting`, `analysing`, `normalising`, `attested`, `failed` |
| `attestations.partition` | `core`, `oracle` |
| `attestations.result` | `pass`, `fail`, `rate-only` |
| `memberships.role` | `org-admin`, `org-viewer`, `scanner` |
| `scm_credentials.auth_mode` | `pat`, `app`, `oauth`, `ssh-key` |
| `codebases.scm_provider` | `github`, `gitlab`, `bitbucket`, `azure-devops` |
| `provenance_records.record_type` | `chain`, `repartition`, `attestation`, `spec-acceptance`, `witness-update` |
| `repartition_events.trigger` | `differential-oracle-disagreement`, `operator-override` |

---

## 7. Retention map (CLAR-DEPLOY-15)

| Table | Retention | Mechanism |
|---|---|---|
| `findings` | indefinite | audit trail; never expired by lifecycle |
| `provenance_records` | 7 years | S3 sidecar (full chain payload) under Object Lock; DB rows retained indefinitely as index |
| `attestations` | 7 years | aligned with provenance_records |
| `snapshots` (rows + S3 artifacts) | 90 days | row-level `expires_at`; reaper job + S3 lifecycle |
| `triage_scores` | 1 year | row-level retention; LLM output, not detection data |
| `repartition_events` | indefinite | append-only audit trail |
| `proposed_specs` (pending) | 90 days unless accepted | row-level expiry |
| `proposed_specs` (accepted / rejected) | indefinite | linked to `spec_versions` row |
| `spec_versions` | indefinite | source of every finding's `S_version` |
| `scans` | 7 years | required to dereference `findings.scan_id` |
| `scm_credentials` | until revoked | encrypted at rest; ciphertext purged on revoke |
| `orgs`, `memberships`, `projects`, `codebases`, `org_policies` | tenant lifetime | retained until tenant deletion (separate workflow) |

S3 Object Lock (Compliance mode) backs the 7-year retention classes per CLAR-DEPLOY-15. The DB-row retention is enforced by a daily reaper job that DELETEs rows past `expires_at`.

---

## 8. References

- `SDD.md` §8 (CMP-FND-01..03) — schema baseline.
- `SDD.md` §10 (CMP-CP-03) — tenancy schema.
- `DOC-DEPLOY-DECISIONS.md` CLAR-DEPLOY-03 — PostgreSQL 16 + Alembic.
- `DOC-DEPLOY-DECISIONS.md` CLAR-DEPLOY-15 — retention.
- `DOC-DEPLOY-DECISIONS.md` CLAR-DEPLOY-16 — per-tenant isolation backstop (RLS).
- `.claude/rules/00-global.md` — RULE-6.
- `.claude/rules/01-invariants.md` — INV-1, INV-2, INV-5.
- `.claude/rules/02-provenance.md` — provenance threading.

---

## 9. CLARIFICATION items filed by this document

(Mirrored in `WBS.md §17`.)

- **CLAR-DB-01** — `scans` table is not explicitly enumerated in `SDD.md CMP-CP-03` but is required by `CMP-ORCH-01`'s public API surface. This document adds it as a derived table; the SDD list at `CMP-CP-03` may need an update to list it explicitly. Blocks: nothing operationally; documentation hygiene. Target: pre-implementation review of `CMP-CP-03`.
- **CLAR-DB-02** — RLS session-variable scheme (`app.org_id`, `app.user_id`, `app.role`) is proposed here; not pinned by SDD or DOC-DEPLOY-DECISIONS. Default is acceptable but should be ratified by the SRE/DevOps and Security Analyst agents. Blocks: `CMP-CP-01`, `CMP-CP-03`. Target: before Phase 11.

---

*Cross-reference: `SDD.md` §8, §10, `DOC-DEPLOY-DECISIONS.md` CLAR-DEPLOY-{03,04,15,16}, `DOC-API.md`, `DOC-SARIF.md`, `.claude/rules/01-invariants.md`, `.claude/rules/02-provenance.md`.*
