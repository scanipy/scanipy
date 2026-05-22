# DOC-CMP-SNAP-01 — Snapshot service API

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `SDD.md §4 CMP-SNAP-01` (Purpose, AC-SNAP-01a/b/c)
- `PLAN.md §"Phase 3 — Snapshotter + CW-DETECT + differential oracle"`
- `PLAN.md §"Algorithm 1 — Incremental CPG maintenance"` (artifacts: `G'`, `ΔG`, `precondition_status`)
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` (CLAR-DEPLOY-02 S3 key scheme; CLAR-DEPLOY-15 retention)
- `docs/cross-cutting/DOC-PROVENANCE.md §3` (snapshot link 2 of the signed chain)
- `docs/cross-cutting/DOC-ALGS.md §2` (Algorithm 1 owner)
- `docs/cross-cutting/DOC-API.md` (REST surface; HMAC-bearer callback)
- `docs/cross-cutting/DOC-INV.md §3, §4` (INV-1 partition, INV-2 versioned parameters)
- `.claude/rules/02-provenance.md`, `.claude/rules/00-global.md`

This document is the **implementation contract** for `CMP-SNAP-01`. A code-writing agent given only this file plus the cross-cutting refs listed above must be able to produce a passing implementation without re-reading `SDD.md` (per `AC-DOC-04`).

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-SNAP-01` |
| Subsystem | Snapshotter (`SDD.md §4`) |
| Staging | Stage A (Java + Python core classes) |
| Depends-On | `CMP-SCM-01`, `CMP-FND-03` (`WBS.md §20`) |
| Owner | **DEFERRED** via `CLAR-OWNER-01` (`WBS.md §17`) |
| INV-* touched | **INV-2** (stamps `env_digest`); routing for INV-1 partition; INV-5-adjacent (snapshot row carries `precondition_status`, which feeds the conditional-canonicality story downstream). |

---

## 2. Mandate

**Verbatim SDD `Purpose:` (`SDD.md §4 CMP-SNAP-01`):**

> `POST /snapshots {codebase_id, commit_sha}` enqueues a snapshot job; persists CPG tarball, reverse-symbol index, dynamic call graph, `ΔG`, and a precondition-status record.

**Operational role.** `CMP-SNAP-01` is the **entry point** of the Snapshotter subsystem. It accepts a synchronous API request to materialize a snapshot for a `(codebase_id, commit_sha)` tuple, enqueues the work to the snapshot worker (`CMP-SNAP-05`), and — after the worker completes — persists exactly five artifacts at deterministic S3 keys plus one row in the relational `snapshots` table that pins `env_digest` and `precondition_status`. The component is the boundary at which the analysis pipeline picks up its `env_digest` (INV-2): the digest stamped here flows unchanged through every downstream finding emitted from this snapshot. SNAP-01 does **not** decide the precondition (that is `CMP-SNAP-03 CW-DETECT`'s job) and does **not** compute the delta (that is `CMP-SNAP-02`'s job); it orchestrates the worker run, persists outputs, and threads `env_digest` into the audit chain (`DOC-PROVENANCE §3` link 4).

---

## 3. Interface contract

### 3.1 HTTP surface

```
POST /snapshots
```

Path is taken verbatim from `SDD.md §4` line 97 (the SDD path is normative; an alignment proposal to move it under `/api/v1/snapshots` is filed as `CLAR-API-01` — DEFERRED, see §10).

**Request (JSON):**

```typescript
interface SnapshotRequest {
    codebase_id: string;        // uuid of the codebase under the calling org
    commit_sha: string;         // 40-hex Git SHA
    org_id: string;             // uuid; sourced from X-Scanipy-Org-Id (CMP-CP-01 guard)
    parent_snapshot_id?: string; // uuid; optional incremental hint
}
```

Required request headers (per `DOC-API.md` and `CMP-CP-01`):

- `X-Scanipy-Org-Id: <uuid>` (RLS-binding)
- `X-Scanipy-User-Id: <uuid>` (audit)
- `Authorization: Bearer <token>` (Auth0 OIDC bearer)

**Response (202 Accepted, JSON):**

```typescript
interface SnapshotAccepted {
    snapshot_id: string;             // uuid (newly minted)
    status: "queued";
    artifact_keys: SnapshotArtifactKeys;   // see §4.2 — deterministic S3 keys
    env_digest: string;              // "sha256:" + 64 hex; the env this snapshot binds to
}
```

**Response (200 OK, JSON) — when an identical-input snapshot already exists (idempotency hit):**

```typescript
interface SnapshotIdempotent {
    snapshot_id: string;
    status: "exists";
    precondition_status: "closed-world" | "degraded" | "full-reparse";
    artifact_keys: SnapshotArtifactKeys;
    env_digest: string;
}
```

Idempotency key: `(codebase_id, commit_sha, env_digest)`. Two requests with the same triple resolve to the same `snapshot_id` and the same artifact keys (the deterministic key scheme of §4.2 guarantees this without app-level coordination beyond a unique constraint on the `snapshots` table).

### 3.2 Error contracts

| HTTP | Error | Cause | Retry policy |
|---|---|---|---|
| `400 BadRequest` | `INVALID_COMMIT_SHA` | `commit_sha` not 40-hex or unresolvable in SCM | Do not retry; fix request. |
| `403 Forbidden` | `CROSS_ORG_ACCESS` | `codebase_id` not in caller's org (CMP-CP-01 RLS) | Do not retry. |
| `404 NotFound` | `CODEBASE_NOT_FOUND` | `codebase_id` does not exist | Do not retry. |
| `409 Conflict` | `SNAPSHOT_IN_PROGRESS` | Same `(codebase_id, commit_sha)` already queued | Poll `GET /snapshots/{id}` instead. |
| `500 InternalError` | `SCM_FETCH_FAILED` | SCM clone failed after `CMP-SCM-05` retry exhaustion | Retry with exponential backoff per `CMP-SCM-05`. |
| `500 InternalError` | `WORKER_ENQUEUE_FAILED` | SQS enqueue failed | Retry up to 3× with backoff; then alarm. |

`CMP-SCM-05` handles SCM transient failures with the shared retry/backoff module before bubbling. Worker-side failures are captured by `CMP-SNAP-05` `report_status` and surfaced via `GET /snapshots/{id}` rather than the synchronous response.

### 3.3 Status / read surface

```
GET /snapshots/{snapshot_id}        → SnapshotState
GET /snapshots/{snapshot_id}/status → {status, precondition_status?, error?}
```

```typescript
type SnapshotState = "queued" | "snapshotting" | "ready" | "failed";

interface SnapshotRecord {
    snapshot_id: string;
    codebase_id: string;
    commit_sha: string;
    org_id: string;
    state: SnapshotState;
    env_digest: string;                                    // INV-2; stamped at create_snapshot()
    precondition_status?: "closed-world" | "degraded" | "full-reparse";  // populated once ready
    artifact_keys: SnapshotArtifactKeys;
    snapshot_digest: string;                               // sha256 over canonical artifact bytes
    created_at: string;     // iso-8601
    completed_at?: string;
    parent_snapshot_id?: string;
}
```

---

## 4. Inputs and outputs

### 4.1 Required inputs

| Input | Source | Contract |
|---|---|---|
| `(codebase_id, commit_sha)` | API request body | Identifies source content. |
| `org_id` | `X-Scanipy-Org-Id` header (via `CMP-CP-01`) | Mandatory for RLS scoping and S3 prefix. |
| `env_digest` | Runtime metadata (ECS task container image digest) | INV-2; sourced once per worker boot from the ECS task metadata endpoint or the env var injected by `CMP-DEPLOY-02`. Must equal the ECR image digest of the worker (CLAR-DEPLOY-13). |
| SCM credentials | `scm_credentials` table (via `CMP-SCM-01`/`CMP-CP-02`) | Decrypted only inside the worker (`CMP-SNAP-05`), never inside the API handler. |

### 4.2 Persisted artifacts and deterministic key scheme

Per `AC-SNAP-01a`, **exactly five artifacts** are persisted per snapshot. Per `CLAR-DEPLOY-02` (RESOLVED — `DOC-DEPLOY-DECISIONS.md`), the S3 key scheme is:

```
orgs/{org_id}/codebases/{codebase_id}/snapshots/{commit_sha}/{env_digest}/{artifact_type}
```

Per-artifact key paths:

| Artifact (from `AC-SNAP-01a`) | `{artifact_type}` suffix | Format | Retention |
|---|---|---|---|
| CPG tarball | `cpg.tar.zst` | zstd-compressed tar of the canonical CPG | 90 d (CLAR-DEPLOY-15) |
| Reverse-symbol index | `reverse_symbol_index.json.zst` | JSON: symbol → declaration → use-sites map | 90 d |
| Dynamic call graph | `dyn_call_graph.json.zst` | JSON: dynamic dispatch edges (Andersen-style points-to) | 90 d |
| ΔG (graph delta vs parent snapshot) | `delta_graph.json.zst` | JSON: `{added_nodes, removed_nodes, added_edges, removed_edges, affected_set}` | 90 d |
| Precondition-status record | `precondition_status.json` | JSON: see §4.3 | 90 d |

The S3 key path is **byte-for-byte reproducible** from `(org_id, codebase_id, commit_sha, env_digest, artifact_type)`, delivering content-addressability transitively (per CLAR-DEPLOY-02 rationale: `commit_sha` is Git's content hash; `env_digest` is the image digest; together they uniquely identify the snapshot's input space).

Object Lock mode (CLAR-DEPLOY-15): **governance mode** for CPG-class artifacts (CPG tarball, reverse-symbol index, dynamic call graph, ΔG). Re-snapshot is the documented recovery path; Object Lock — Compliance mode is reserved for SARIF + provenance (`DOC-PROVENANCE §6`).

### 4.3 `precondition_status.json` shape

```json
{
  "verdict": "closed-world" | "degraded" | "full-reparse",
  "cw_detect_version": "semver",
  "decided_at": "iso-8601",
  "cone_size_ratio": 0.18,        // |cone|/|G'| when verdict ∈ {degraded, full-reparse}; null on closed-world
  "changed_files_ratio": 0.05,    // |changed files|/|files|; null when not a delta
  "reflection_sites": [           // empty on verdict=closed-world
    { "file": "src/X.java", "line": 42, "kind": "Class.forName" }
  ]
}
```

Verdict values are exactly the three from `AC-SNAP-01b`: `closed-world | degraded | full-reparse`. Source-of-truth definitions in `DOC-GLOSSARY.md §"precondition-status"`.

### 4.4 Relational outputs (`snapshots` table)

The relational row is the join key between the snapshot artifacts and the provenance chain (`DOC-PROVENANCE §3`):

```sql
-- Schema mirrored from DOC-DB §"snapshots"
INSERT INTO snapshots (
    snapshot_id,           -- uuid (newly minted)
    codebase_id,           -- uuid
    org_id,                -- uuid (RLS key)
    commit_sha,            -- 40-hex
    state,                 -- 'queued' at insert; 'ready'/'failed' at completion
    env_digest,            -- sha256 of container image; INV-2
    snapshot_digest,       -- sha256 of canonical artifact byte sequence (set on completion)
    precondition_status,   -- one of closed-world|degraded|full-reparse (set on completion)
    parent_snapshot_id,    -- uuid | null
    created_at,            -- now()
    completed_at           -- null until 'ready'
);
```

Constraints (per `AC-SNAP-01b`, `AC-SNAP-01c`, INV-2):

- `env_digest` NOT NULL on insert (the row cannot be created without it).
- `precondition_status` NOT NULL CHECK in `('closed-world','degraded','full-reparse')` on transition to `state='ready'`.
- Unique index on `(codebase_id, commit_sha, env_digest)` enforces idempotency.

---

## 5. Invariants touched

| Invariant | How `CMP-SNAP-01` discharges it | Test |
|---|---|---|
| **INV-2** | `env_digest` is stamped at `create_snapshot()` time from the container image digest (sourced from ECS task metadata; see `CMP-SNAP-05 AC-SNAP-05b`). It must equal a real ECR-resident image digest (`"sha256:" + 64 hex`); the row is rejected if it is not. Every downstream finding inherits this `env_digest` via the snapshot reference. | `TST-AC-SNAP-01c [FORTHCOMING]`, `TST-INV-2-SNAP-01 [FORTHCOMING]` |
| **INV-1** (routing-adjacent) | `CMP-SNAP-01` does not stamp `origin` itself (that is `CMP-ORCH-03`), but it persists `precondition_status` which routes downstream emission paths into the correct partition. A `full-reparse` precondition does not by itself force `oracle-passthrough`; the partition still derives from `detector.engine` per `DOC-PARTITION §3`. | (indirect; see `TST-INV-1-ORCH-03`, `TST-INV-1-SNAP-04`) |
| **INV-5** (provenance hand-off) | The snapshot row is link 2 of the signed chain (`DOC-PROVENANCE §3`); the conditional-canonicality annotation lives at link 5 (`cpg_order_hash`, set by `CMP-CORE-03`). `CMP-SNAP-01` does not write the annotation but it must not strip the snapshot from downstream consumers that do. | (indirect) |

---

## 6. Algorithm / data flow

```
client -POST /snapshots-> CMP-SNAP-01 API handler
    1.  Validate request (commit_sha 40-hex; codebase exists; RLS via X-Scanipy-Org-Id).
    2.  Resolve env_digest from runtime metadata (ECR image digest of this task).
    3.  Idempotency lookup: SELECT snapshot_id FROM snapshots
                            WHERE (codebase_id, commit_sha, env_digest) = (?, ?, ?).
        If hit -> return 200 SnapshotIdempotent.
    4.  INSERT snapshots row (state='queued', env_digest=<resolved>).
    5.  Build artifact_keys (per §4.2) deterministically from inputs.
    6.  Enqueue SnapshotJob{snapshot_id, codebase_id, commit_sha, env_digest, artifact_keys,
                            parent_snapshot_id?} to SQS (CLAR-DEPLOY-06).
    7.  Return 202 SnapshotAccepted{snapshot_id, state='queued', artifact_keys, env_digest}.

CMP-SNAP-05 worker picks the SQS message:
    a.  Clone source @ commit_sha via CMP-SCM-{02,03} (using CMP-SCM-05 retry).
    b.  Invoke CMP-SNAP-03 (CW-DETECT) -> precondition verdict.
    c.  If parent_snapshot_id present and verdict allows: invoke CMP-SNAP-02 incremental.
        Else: full reparse.
    d.  Persist five artifacts to the S3 keys minted in step 5 above.
    e.  Call back to CMP-SNAP-01 'report_status' (HMAC-bearer, see DOC-API.md):
            POST /snapshots/{id}/status {state, precondition_status, snapshot_digest, error?}.
    f.  CMP-SNAP-01 updates snapshots row: state='ready', completed_at, snapshot_digest,
                                            precondition_status.

CMP-SNAP-04 (differential oracle) consumes the same snapshot artifacts asynchronously;
                                  emits re-partition events directly to provenance
                                  (DOC-PROVENANCE §4). It does NOT mutate this snapshot row.
```

Failure-mode routing is covered in §7.

---

## 7. Failure modes and error contracts

| Failure | Detected by | Response | Persisted state |
|---|---|---|---|
| SCM clone fails after retries | `CMP-SNAP-05` worker | Worker `report_status(state='failed', error)`; SQS DLQ after 3 retries (CLAR-DEPLOY-06) | Row remains `state='queued'`; SRE-paged via CloudWatch alarm (CLAR-DEPLOY-07) |
| `CW-DETECT` raises an internal error (not a verdict) | Worker | Worker fails the job; SQS retry. `CW-DETECT` itself is **fail-closed**: any uncertainty defaults to `not-closed-world` (per `DOC-CMP-SNAP-03 §6`). | Row not transitioned; queued for retry |
| Worker times out (SQS visibility-timeout 15 min) | SQS | DLQ after max-receive=3; alarm | Row stays `queued`; manual re-snapshot via `DOC-RUNBOOK §4.2` |
| S3 PutObject fails | Worker | Per-artifact retry; worker fails after 5 attempts | Row not transitioned |
| Same `(codebase_id, commit_sha, env_digest)` re-submitted | API handler | Idempotency hit; return 200 with existing row | No new row |
| Image digest unresolvable (no task metadata) | API handler at boot | **Hard fail**: refuse all requests until digest is resolvable. INV-2 requires a real `env_digest`; a missing digest is a fail-closed condition. | Service unavailable |

**Safe-direction note (INV-4 hand-off).** `CMP-SNAP-01` does not own an INV-4 approximation — it consumes the verdict from `CMP-SNAP-03`. But it must **persist the verdict faithfully**: if `CW-DETECT` returned `not-closed-world`, the snapshot row's `precondition_status` is `degraded` or `full-reparse` (never silently upgraded to `closed-world`). This is the operational hand-off that keeps `CMP-SNAP-04`'s differential-oracle disagreement detection coherent.

---

## 8. Provenance threading

`CMP-SNAP-01` writes the following provenance fields (per `DOC-PROVENANCE §10`):

| Field | Source | Threading rule |
|---|---|---|
| `snapshot_id` | minted by handler | unique per `(codebase_id, commit_sha, env_digest)` |
| `snapshot_digest` | computed by worker; persisted by handler on `report_status` | sha256 over canonical artifact byte sequence |
| `env_digest` | runtime metadata (container image digest) | INV-2; same value across all artifacts and downstream findings of this snapshot |
| `precondition_status` | from `CMP-SNAP-03` via worker | `closed-world | degraded | full-reparse` |
| `org_id`, `codebase_id`, `commit_sha`, `parent_snapshot_id` | from request | identity fields for the audit chain |

**Must NOT touch:** `origin`, `S_version`, `cpg_order_hash`, `slice_fingerprint`, any finding-level row. Those are written by downstream components (`CMP-ORCH-03`, `CMP-CORE-03`, `CMP-CORE-02`, `CMP-FND-01..03`).

---

## 9. Acceptance criteria cross-reference

The following ACs are quoted **verbatim** from `SDD.md §4 CMP-SNAP-01`. Paraphrasing an AC is a contract break (RULE-4). Every TST-AC-* is `[FORTHCOMING]` because the QA phase has not begun.

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-SNAP-01a** | > A snapshot request for a known commit produces all five persisted artifacts at deterministic S3 keys. | `TST-AC-SNAP-01a` `[FORTHCOMING]` |
| **AC-SNAP-01b** | > The precondition-status record records exactly one of `closed-world | degraded | full-reparse`. | `TST-AC-SNAP-01b` `[FORTHCOMING]` |
| **AC-SNAP-01c** | > `env_digest` is computed from the pinned container image digest and recorded on the snapshot. | `TST-AC-SNAP-01c` `[FORTHCOMING]`; also covered by `TST-INV-2-SNAP-01` `[FORTHCOMING]` |

Invariant tests cross-referenced:

- `TST-INV-2-SNAP-01 [FORTHCOMING]` — snapshot row writes a non-empty `env_digest` equal to the container image digest.

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-SNAP-01 |
|---|---|---|---|
| `CLAR-DEPLOY-02` | Object-store choice + deterministic key scheme | **RESOLVED** | S3, key path per §4.2. |
| `CLAR-DEPLOY-15` | Per-artifact retention | **RESOLVED** | CPG-class artifacts 90 d governance Object Lock. |
| `CLAR-DEPLOY-16` | Per-tenant isolation backstop | **RESOLVED** | S3 prefix `orgs/{org_id}/...`; RLS on `snapshots` table by `org_id`. |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | `Owner` field in §1 will remain "DEFERRED" until populated. |
| `CLAR-API-01` | URL alignment under `/api/v1/` prefix | **DEFERRED** | SDD path `/snapshots` is normative; alignment to `/api/v1/snapshots` is a post-acceptance housekeeping change. |

No new CLAR-SNAP-* are filed by this document; every AC of `CMP-SNAP-01` is unambiguous given the cross-cutting references.

---

## 11. References

- `SDD.md §4 CMP-SNAP-01` — verbatim AC statements.
- `PLAN.md §"Phase 3"`, `§"Algorithm 1"` — snapshotter architecture.
- `docs/cross-cutting/DOC-API.md` — REST surface specification (`POST /snapshots`, HMAC-bearer callback).
- `docs/cross-cutting/DOC-DB.md §"snapshots"` — relational schema.
- `docs/cross-cutting/DOC-PROVENANCE.md §3` — snapshot link in the signed chain.
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — CLAR-DEPLOY-02 (S3), CLAR-DEPLOY-13 (ECR), CLAR-DEPLOY-15 (retention).
- `docs/cross-cutting/DOC-ALGS.md §2` — Algorithm 1 ownership chain.
- `docs/cross-cutting/DOC-RUNBOOK.md §3, §4.2` — scan lifecycle; re-snapshot procedure.
- `docs/components/DOC-CMP-SNAP-02.md` (sibling) — incremental CPG maintenance.
- `docs/components/DOC-CMP-SNAP-03.md` (sibling) — `CW-DETECT`.
- `docs/components/DOC-CMP-SNAP-05.md` (sibling) — worker + env pinning.
- `.claude/rules/00-global.md` (RULE-6 provenance threading), `.claude/rules/02-provenance.md`.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-SNAP-01`.*
