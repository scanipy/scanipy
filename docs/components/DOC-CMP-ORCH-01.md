# DOC-CMP-ORCH-01 — Scan API

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `SDD.md §7 CMP-ORCH-01` (Purpose, AC-ORCH-01a/b/c)
- `PLAN.md §"Phase 4 — Orchestrator + heuristic scheduler"` (HMAC-bearer worker callback as in v2)
- `PLAN.md §"Engine adapters and the determinism partition"`
- `docs/cross-cutting/DOC-API.md §4.1, §4.5, §2.3` (REST surface; HMAC bearer)
- `docs/cross-cutting/DOC-DB.md §4.11` (`scans` table) and `§4.7` (`snapshots`)
- `docs/cross-cutting/DOC-PROVENANCE.md §3.1, §10` (per-component threading; ORCH-01 writes `S_version` and `commit_sha`)
- `docs/cross-cutting/DOC-PARTITION.md §4` (`CMP-ORCH-03` is the `origin` setter; ORCH-01 routes work to it)
- `docs/cross-cutting/DOC-INV.md §3, §4` (INV-1, INV-2 owner maps)
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` (CLAR-DEPLOY-06 SQS, CLAR-DEPLOY-14 LLM provider)
- `.claude/rules/00-global.md` RULE-6 provenance threading, `.claude/rules/02-provenance.md`

This document is the **implementation contract** for `CMP-ORCH-01`. A code-writing agent given only this file plus the cross-cutting refs listed above must be able to produce a passing implementation without re-reading `SDD.md` (per `AC-DOC-04`).

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-ORCH-01` |
| Subsystem | Orchestration (`SDD.md §7`) |
| Module path | `services/scan/api.py` (per `CLAUDE.md §12`, `PLAN.md §"Phase 4"`) |
| Staging | Stage A (Java + Python core classes are the first detectors fanned out) |
| Depends-On | `CMP-SNAP-01`, `CMP-FND-01`, `CMP-CP-01` (`WBS.md §20`) |
| Owner | **DEFERRED** via `CLAR-OWNER-01` (`WBS.md §17`) |
| INV-* touched | **INV-2 fence** (binds `S_version` at scan submission, threads it onto the `scans` row); **INV-3 fence** (accepts only registered `S_version` values; no LLM bypass at the submission boundary); not an INV-1 setter (`CMP-ORCH-03` is the per-finding `origin` setter). |

---

## 2. Mandate

**Verbatim SDD `Purpose:` (`SDD.md §7 CMP-ORCH-01`):**

> `POST /api/v1/scans {codebase_id, commit_sha, detector_ids[]}`; `GET /api/v1/scans/{id}`, `…/findings`; worker callback `POST /api/v1/jobs/{job_id}/status` preserving the HMAC-bearer pattern.

**Operational role.** `CMP-ORCH-01` is the **public ingress** of the analysis pipeline and the **HMAC-authenticated egress sink** for worker status reports. It:

1. Accepts customer/scanner-submitted scans against a snapshot, creating the snapshot (`CMP-SNAP-01`) if absent and fanning **one SQS message per detector** onto the per-detector job queue (`CLAR-DEPLOY-06`).
2. Exposes the scan-status read surface (`GET /api/v1/scans/{id}`, `GET /api/v1/scans/{id}/findings`) over which the dashboard (`CMP-CP-04`), the Attestor (`CMP-CP-05`), and the SARIF export of `CMP-FND-01` are realised.
3. Receives **`POST /api/v1/jobs/{job_id}/status`** from analysis workers (`CMP-ORCH-03`), authenticated by HMAC-bearer over the canonical request (`DOC-API.md §2.3`). On `done`, it triggers `CMP-FND-01` normalisation and `CMP-CP-05` attestation downstream.
4. Preserves the **`scanipy --query extractall --run-semgrep`** Research-mode entry point so legacy CLI invocations still produce the historical CVE-2025-61765 path-traversal finding on a Stage-A language with `origin=deterministic-core` (`AC-ORCH-01c`, `T-CMP-RES-01-03`).

ORCH-01 does **not** set the per-finding `origin` (that is `CMP-ORCH-03`), does **not** compute the schedule (`CMP-ORCH-02`), and does **not** sign provenance (`CMP-FND-03`). It is a stateless front-end over the `scans`, `snapshots`, and per-detector SQS queues.

---

## 3. Interface contract

### 3.1 Public HTTP surface (typed Python signatures)

The handlers are FastAPI / Starlette-equivalent. Bodies, headers, and responses are normative against `DOC-API.md §4.1` and `§4.5`; this section restates the typed signatures the implementation must expose. Where the task-prompt for this document proposed an alternative path (`POST /api/v1/internal/workers/{worker_id}/report_status`), the **SDD path is normative** and the divergence is filed as `CLAR-API-01` (see §10).

```python
from typing import Literal, Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, constr

CommitSha = constr(pattern=r"^[0-9a-f]{40}$")
Semver    = constr(pattern=r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z\.-]+)?$")
Sha256Hex = constr(pattern=r"^sha256:[0-9a-f]{64}$")

# ----- POST /api/v1/scans  (AC-ORCH-01a) ---------------------------------

class ScanRequest(BaseModel):
    codebase_id: UUID
    commit_sha: CommitSha
    detector_ids: list[str]                   # at least 1; resolved against CMP-DET-02 registry
    S_version: Optional[Semver] = None        # if None, server resolves "latest accepted"
    policy_overrides: dict = {}               # opaque to ORCH-01; persisted on scans row

class ScanCreated(BaseModel):
    scan_id: UUID
    snapshot_id: UUID
    status: Literal["queued"]
    S_version: Semver                         # always echoed (resolved if None on input)
    env_digest: Sha256Hex                     # from CMP-SNAP-01 (INV-2)
    created_at: datetime

async def post_scans(
    body: ScanRequest,
    org_id: UUID,                             # from X-Scanipy-Org-Id (CMP-CP-01)
    user_id: UUID,                            # from X-Scanipy-User-Id
    idempotency_key: UUID,                    # required header
) -> ScanCreated: ...

# ----- GET /api/v1/scans/{scan_id} ----------------------------------------

class JobSummary(BaseModel):
    job_id: UUID
    detector_id: str
    status: Literal["queued", "running", "done", "failed"]

class ScanState(BaseModel):
    scan_id: UUID
    snapshot_id: UUID
    codebase_id: UUID
    commit_sha: CommitSha
    status: Literal["queued", "snapshotting", "analysing",
                    "normalising", "attested", "failed"]
    S_version: Semver
    env_digest: Sha256Hex
    started_at: datetime
    finished_at: Optional[datetime]
    jobs: list[JobSummary]
    findings_count: int
    attestation_status: Literal["pending", "core-pass", "core-fail", "oracle-only"]

async def get_scan(scan_id: UUID, org_id: UUID) -> ScanState: ...

# ----- GET /api/v1/scans/{scan_id}/findings -------------------------------
#   Delegates SARIF emission to CMP-FND-01; returns the Finding object
#   defined in DOC-API.md §5 (provenance-threaded per RULE-6).

async def get_scan_findings(
    scan_id: UUID, org_id: UUID,
    limit: int = 50, cursor: Optional[str] = None,
    cls: Optional[str] = None, severity: Optional[str] = None,
    origin: Optional[Literal["deterministic-core", "oracle-passthrough"]] = None,
    status: Optional[Literal["open", "suppressed", "fixed"]] = None,
) -> "FindingsPage": ...

# ----- POST /api/v1/jobs/{job_id}/status   (AC-ORCH-01b) ------------------
#   Authentication: HMAC-bearer (DOC-API.md §2.3). The SDD-normative path
#   is /api/v1/jobs/{job_id}/status; an alignment proposal to move under
#   /api/v1/internal/... is filed as CLAR-API-01.

class JobStatusReport(BaseModel):
    job_id: UUID
    scan_id: UUID
    status: Literal["running", "done", "failed"]
    S_version: Semver                         # INV-2 — required on every callback
    env_digest: Sha256Hex                     # INV-2 — required on every callback
    findings_count: int = 0
    core_partition_count: int = 0
    oracle_partition_count: int = 0
    result_uri: Optional[str] = None          # s3://... ; required when status=done
    witness_uri: Optional[str] = None         # oracle findings may omit
    error: Optional[dict] = None              # {"code": str, "message": str}

async def post_job_status(
    job_id: UUID,
    body: JobStatusReport,
    hmac_header: str,                         # "Authorization: HMAC <key-id>:<hex-digest>"
    worker_id_header: str,                    # "X-Scanipy-Worker-Id"
    timestamp_header: int,                    # "X-Scanipy-Job-Timestamp" (Unix epoch s)
) -> None:                                    # 204 on success
    ...
```

### 3.2 SCM webhook ingest stub

`CMP-ORCH-01` does **not** parse the SCM webhook payload itself — that is the role of `CMP-SCM-02/03` and is documented in `DOC-API.md §4.6`. However, ORCH-01 exposes a thin stub that the SCM subsystem invokes via an internal SNS topic to enqueue a scan once the webhook handler has resolved a `(codebase_id, commit_sha)`:

```python
async def enqueue_scan_from_webhook(
    codebase_id: UUID, commit_sha: CommitSha, source_provider: str,
) -> UUID:                                    # returns scan_id
    """Internal entry point. Equivalent to post_scans with a synthetic
    Idempotency-Key derived from (provider, delivery_id); never callable
    over the public HTTP surface."""
```

### 3.3 HMAC-bearer worker-callback verification

Per `DOC-API.md §2.3` and `AC-ORCH-01b`:

```
canonical-request = method + "\n"
                  + path + "\n"
                  + worker_id_header + "\n"
                  + sha256_hex(body) + "\n"
                  + timestamp_header

provided  = parse(Authorization: "HMAC <key-id>:<digest>")
expected  = HMAC-SHA-256(key = lookup_job_hmac_key(job_id, provided.key_id),
                        msg = canonical-request).hex()

if not constant_time_eq(provided.digest, expected):
    raise InvalidHmacError(error_code="invalid_hmac", http_status=401)
if abs(now() - timestamp_header) > 300:        # 5-minute replay window
    raise InvalidHmacError(error_code="invalid_hmac", http_status=401)
```

The HMAC key is **rotated per scheduler-issued job** (`DOC-API.md §2.3`); the scheduler (`CMP-ORCH-02`) issues the key when it dispatches the job to SQS, and ORCH-01 looks it up from the `scans`/`jobs` row by `(job_id, key_id)`. A failed HMAC verification rejects the payload **before any state mutation** (negative-test contract of `AC-ORCH-01b`).

### 3.4 Error contracts

| HTTP | `error_code` | Cause | Retry policy |
|---|---|---|---|
| `400` | `invalid_input` | Schema validation failed (e.g., `commit_sha` not 40-hex) | Do not retry. |
| `401` | `unauthenticated` | Missing / invalid JWT bearer | Re-acquire token. |
| `401` | `invalid_hmac` | Worker callback HMAC mismatch (`AC-ORCH-01b`) | Worker re-fetches key and retries. |
| `403` | `org_mismatch` | `X-Scanipy-Org-Id` ≠ JWT `org_id` claim | Do not retry. |
| `403` | `role_denied` | Caller lacks role for endpoint | Do not retry. |
| `403` | `tenant_isolation_violation` | Cross-tenant access attempt (RLS-backed) | Do not retry. |
| `404` | `not_found` | `scan_id` / `codebase_id` not in caller's org | Do not retry. |
| `409` | `idempotency_conflict` | Same `Idempotency-Key` with different body | Use new key. |
| `409` | `not_found` | Unknown `detector_id` | Fix request. |
| `422` | `invariant_inv2_violation` | Submitted scan without resolvable `S_version` | Fix `S_version` reference. |
| `429` | `rate_limited` | Per-tenant API quota exceeded | Honor `X-RateLimit-Reset`. |
| `503` | `internal_error` | SQS enqueue failure after retry | Server retries; client may re-submit after `Retry-After`. |

LLM-bearing endpoint quotas (`CLAR-DEPLOY-14`) do **not** apply directly to ORCH-01 — the LLM is consumed server-side by `CMP-TRI-01..03`. Indirect quota counting on PATCH-induced re-ranking is enforced at `CMP-CP-01`, not here. Numeric defaults are deferred to `CLAR-SLA-02` (see §10).

---

## 4. Inputs and outputs

### 4.1 Required inputs

| Input | Source | Contract |
|---|---|---|
| `codebase_id`, `commit_sha`, `detector_ids[]` | Request body | Validated against `codebases` table (tenant-scoped) and `CMP-DET-02` registry. |
| `S_version` | Request body (optional); else "latest accepted" from `spec_versions` table | INV-2; must be a registered, version-pinned spec (INV-3 fence). |
| `org_id` | `X-Scanipy-Org-Id` header (validated by `CMP-CP-01` against JWT claim) | RLS-binding for `scans` table. |
| `Idempotency-Key` | Header | Required; UUID; persisted to `scans.idempotency_key`. |
| HMAC key (callback path) | Per-job key issued by `CMP-ORCH-02` at dispatch | Rotated per job. |

### 4.2 Persisted rows

#### 4.2.1 `scans` row (per `DOC-DB.md §4.11`)

On `POST /api/v1/scans`:

```sql
INSERT INTO scans (
    id,                   -- uuid (newly minted = scan_id)
    org_id,               -- uuid (RLS key)
    codebase_id,          -- uuid
    snapshot_id,          -- uuid (created or resolved via CMP-SNAP-01)
    commit_sha,           -- 40-hex
    S_version,            -- NOT NULL; resolved if omitted on input
    env_digest,           -- NOT NULL; sourced from snapshots.env_digest
    detector_ids,         -- text[]
    status,               -- 'queued'
    policy_overrides,     -- jsonb
    idempotency_key,      -- uuid; UNIQUE (org_id, idempotency_key)
    started_at            -- now()
);
```

`S_version` and `env_digest` are NOT NULL — the row cannot be created without them (INV-2 schema fence).

#### 4.2.2 Per-detector SQS message (per `CLAR-DEPLOY-06`)

Fan-out: **one message per `detector_id`** onto the per-detector queue (`scanipy.scan.<detector_id>.fifo` or the appropriate standard queue; queue name is operational, not in this contract). Message body:

```json
{
  "job_id":        "uuid",
  "scan_id":       "uuid",
  "snapshot_id":   "uuid",
  "codebase_id":   "uuid",
  "commit_sha":    "string (40-hex)",
  "detector_id":   "string",
  "S_version":     "semver",
  "env_digest":    "sha256:...",
  "policy_overrides": { },
  "hmac_key_id":   "string",
  "callback_path": "/api/v1/jobs/{job_id}/status"
}
```

SQS attributes (per `CLAR-DEPLOY-06` resolution in `DOC-DEPLOY-DECISIONS.md` line 104):

- **Visibility timeout:** **60 min for full-scan jobs** (this fan-out); snapshot-job queues are 15 min and are owned by `CMP-SNAP-01`.
- **Max receive count:** **3** before message goes to DLQ.
- **DLQ alarm:** CloudWatch alarm into observability (`CLAR-DEPLOY-07`).

#### 4.2.3 No finding row is written by ORCH-01

Findings are written by `CMP-FND-01` (normaliser) consuming the worker's SARIF `result_uri` after `POST /api/v1/jobs/{job_id}/status` reports `status=done`. ORCH-01 has **no INSERT grant on `findings`** (schema-level INV-3 fence; `CMP-TRI-01` follows the same pattern).

### 4.3 Webhook stub side effects

`enqueue_scan_from_webhook` consults `org_policies` (via `CMP-CP-03`) for default detector lists, mints a synthetic `Idempotency-Key = uuidv5("scanipy-webhook", provider + ":" + delivery_id)`, and calls `post_scans` with `scanner` role. Provider-dedup happens at `DOC-API.md §3.4`.

---

## 5. Invariants touched

| Invariant | Discharge by `CMP-ORCH-01` | Test |
|---|---|---|
| **INV-2 (versioned parameters)** | Binds `S_version` at scan submission (request body or resolved-default from `spec_versions`); refuses to enqueue if `S_version` is not a registered, version-pinned row. Threads `S_version` and `env_digest` (sourced from `snapshots.env_digest` per `CMP-SNAP-01`) onto every SQS message and the `scans` row. NOT NULL constraints on `scans.S_version` and `scans.env_digest` are the schema-level fence. | `TST-INV-2-ORCH-03 [FORTHCOMING]` (covers the threading; ORCH-01 is the submission-time binder) |
| **INV-3 (LLM off the detection path) — fence** | `S_version` accepted at submission **must** be a row in `spec_versions` (written by `CMP-TRI-02` only after the e-process gate accepts it). ORCH-01 never accepts an inline / LLM-tampered spec; only registered, version-pinned references. PATCH on `findings.status` (the only mutator surface for findings) lives under `DOC-API.md §4.4` and likewise refuses to delete a `deterministic-core` finding. | `TST-INV-3-TRI-01 [FORTHCOMING]` (covers the fence; ORCH-01 is the ingress half of it) |
| **INV-1 (origin partition) — pass-through** | ORCH-01 does **not** set per-finding `origin`. It enqueues a job; the worker (`CMP-ORCH-03`) is the canonical setter (per `DOC-PARTITION.md §4`). ORCH-01 must never default an `origin` value on a worker-callback that omits a per-finding annotation; callbacks carry per-partition *counts*, not per-finding origins, and `CMP-FND-01` reads `origin` from the worker-emitted SARIF blob. | (no direct ORCH-01 test; `TST-INV-1-ORCH-03`) |

`CMP-ORCH-01` is **not** an INV-4 owner (no undecidable approximation) and **not** an INV-5 owner (no `cpg_order_hash` write).

---

## 6. Algorithm / data flow

```
client -POST /api/v1/scans-> ORCH-01 handler
    1.  CMP-CP-01 guard: validate JWT, X-Scanipy-Org-Id, role ∈ {org-admin, scanner}.
    2.  Idempotency check: SELECT id FROM scans
                            WHERE (org_id, idempotency_key) = (?, ?).
        If hit and body matches -> return existing scan_id (200).
        If hit and body differs -> 409 idempotency_conflict.
    3.  Resolve S_version:
            if body.S_version is None:
                S_version <- SELECT MAX(version) FROM spec_versions
                              WHERE status = 'accepted';
            else:
                row <- SELECT 1 FROM spec_versions WHERE version = body.S_version;
                if not row: 422 invariant_inv2_violation.
    4.  Validate detector_ids[] against CMP-DET-02 registry; any unknown -> 409.
    5.  Resolve or create snapshot via CMP-SNAP-01:
            POST /snapshots { codebase_id, commit_sha }
              -> snapshot_id, env_digest, precondition_status.
    6.  INSERT scans row (status='queued', S_version, env_digest, ...).
    7.  For each detector_id in detector_ids[]:
            mint job_id (uuid);
            mint hmac_key_id + per-job HMAC secret;
            enqueue SQS message (§4.2.2) onto the per-detector queue.
    8.  Return 201 ScanCreated.

worker -POST /api/v1/jobs/{job_id}/status-> ORCH-01 handler
    a.  Verify HMAC (§3.3); reject with 401 invalid_hmac on mismatch
                                   BEFORE any state mutation (AC-ORCH-01b).
    b.  Validate body schema; S_version and env_digest required (INV-2 fence).
    c.  Idempotency: if status='done' arrived previously for this job_id,
                      return 204 no-op.
    d.  UPDATE jobs row (status, error?). If status='done':
            i.   Enqueue normalisation message to CMP-FND-01 with result_uri.
            ii.  When all scan-level jobs are 'done', flip scans.status to
                  'normalising' then 'attested' on CMP-CP-05 sign-off.
    e.  Return 204.

CMP-ORCH-02 (scheduler) reads queued SQS messages from the per-detector queues
                       and assigns them to workers; ORCH-01 does not interact
                       with the scheduler directly (the scheduler reads the
                       same SQS queues).
```

Backwards-compat (`AC-ORCH-01c`): the Research-mode CLI shim (`scanipy --query extractall --run-semgrep`, owned by `CMP-RES-01`, `T-CMP-RES-01-03`) calls `enqueue_scan_from_webhook`-equivalent with a synthetic `Idempotency-Key`; the path-traversal detector on a Stage-A language yields the CVE-2025-61765 finding with `origin=deterministic-core`. The detector still runs through `CMP-ORCH-03`; ORCH-01 only mediates submission.

---

## 7. Failure modes and error contracts

| Failure | Detected by | Response | Persisted state |
|---|---|---|---|
| JWT invalid / missing | CMP-CP-01 guard | `401 unauthenticated` | No row. |
| `X-Scanipy-Org-Id` ≠ JWT claim | ORCH-01 | `403 org_mismatch`; OTel `WARN` log (`CLAR-DEPLOY-16`) | No row. |
| Caller role insufficient | ORCH-01 | `403 role_denied` | No row. |
| `codebase_id` not in caller's org (RLS) | DB (RLS policy) | `403 tenant_isolation_violation` (mapped from RLS deny) | No row. |
| `commit_sha` not 40-hex | Pydantic | `400 invalid_input` | No row. |
| Unknown `detector_id` | Registry lookup | `409 not_found` (`error_code = not_found` with `details.detector_id`) | No row. |
| Snapshot creation fails after retries | `CMP-SNAP-01` callback | Surface synchronously as `503 internal_error`; client retries with backoff | No `scans` row; `snapshots` row may exist in `failed` state. |
| SQS enqueue failure | SDK retry then bubble | `503 internal_error` with `Retry-After: 30`; alarm via `CLAR-DEPLOY-07` | `scans` row remains `queued`; partial fan-out recovered by reconcile job. |
| Worker callback with invalid HMAC | ORCH-01 §3.3 | `401 invalid_hmac`; **no state mutation** (`AC-ORCH-01b`) | None. |
| Worker callback timestamp >5 min skew | ORCH-01 §3.3 | `401 invalid_hmac` (anti-replay) | None. |
| Duplicate `done` callback for same `job_id` | ORCH-01 step (c) | `204 No Content` (idempotent no-op) | No change. |
| Conflicting status transition (e.g., `done → running`) | ORCH-01 step (d) | `409 not_found` with `details.transition` | No change. |
| Worker timeout (SQS visibility 60 min exceeded) | SQS | After max-receive=3 → DLQ; SRE alarm | `scans.status` stays `analysing`; reconcile job promotes to `failed` after a grace period. |

**Webhook signature failures** are handled in `CMP-SCM-02/03`, not here. ORCH-01's `enqueue_scan_from_webhook` is invoked only after signature verification has passed.

**INV-3 fence on PATCH:** any `PATCH /api/v1/findings/{id}` request that would delete a `deterministic-core` finding is rejected with `422 invariant_inv3_violation` (per `DOC-API.md §4.4`). ORCH-01 does not own the PATCH handler (that is `CMP-FND-02`), but it must not expose a back-door submission path that bypasses the fence.

---

## 8. Provenance threading

Per `DOC-PROVENANCE.md §10` (canonical table) and `.claude/rules/02-provenance.md`:

| Field | Source | Threading rule |
|---|---|---|
| `commit_sha` | Request body | Persisted on `scans` row; carried into every SQS job message and inherited by every finding. |
| `S_version` | Request body (or resolved default) | INV-2; persisted on `scans`, carried on SQS messages, threaded by `CMP-ORCH-03` onto every emitted finding. ORCH-01 is the **binder**. |
| `env_digest` | Read from `snapshots.env_digest` (set by `CMP-SNAP-01`) | INV-2 pass-through; never re-derived here. |
| `org_id`, `codebase_id`, `snapshot_id` | Request + snapshot resolution | Audit identity fields. |

**Must NOT touch:** `origin`, `cpg_order_hash`, `cpg_order_hash_annotation`, `slice_fingerprint`, `fingerprint_class`, `determinism_partition`, `witness_blob_uri`, `triage_*`, `sarif_hash`, any finding-level row. Those are written by `CMP-ORCH-03`, `CMP-CORE-02/03`, `CMP-FND-01/02/03`, and `CMP-TRI-01`.

The full chain construction (`PLAN.md` property (c)) is closed by `CMP-FND-03`; ORCH-01 contributes **link 1 (source commit) and link 3 (`S_version`)** of that chain.

---

## 9. Acceptance criteria cross-reference

The following ACs are quoted **verbatim** from `SDD.md §7 CMP-ORCH-01`. Paraphrasing an AC is a contract break (RULE-4). Every TST-AC-* is `[FORTHCOMING]` because the QA phase has not begun.

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-ORCH-01a** | > A scan creates a snapshot if absent, then fans one job per detector. | `TST-AC-ORCH-01a [FORTHCOMING]` `[INTEGRATION]` (per `WBS.md §6`) |
| **AC-ORCH-01b** | > The worker callback rejects a payload with an invalid HMAC (negative test). | `TST-AC-ORCH-01b [FORTHCOMING]` `[NEGATIVE]` |
| **AC-ORCH-01c** | > Backwards-compat: `scanipy --query extractall --run-semgrep` via Research mode still yields the CVE-2025-61765 path-traversal finding with `origin=deterministic-core` on a Stage-A language. | `TST-AC-ORCH-01c [FORTHCOMING]` `[REGRESSION]` |

Invariant tests touched indirectly:

- `TST-INV-2-ORCH-03 [FORTHCOMING]` — every emitted finding carries `S_version` and `env_digest`. ORCH-01 is the submission-time binder; the test exercises the threading end-to-end.

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on `CMP-ORCH-01` |
|---|---|---|---|
| `CLAR-API-01` | URL alignment under `/api/v1/`: task-prompt proposed `POST /api/v1/internal/workers/{worker_id}/report_status`; SDD path is `POST /api/v1/jobs/{job_id}/status` | **DEFERRED** | SDD path is normative; alignment is a post-acceptance housekeeping change. `DOC-API.md §4.5` mirrors this stance. |
| `CLAR-SLA-02` | Numeric per-tenant rate-limit defaults (general API RPM/burst; LLM RPM/TPD enforced by `CMP-CP-01`) | **DEFERRED** | Default budgets in `DOC-API.md §7` are proposed but not pinned. ORCH-01 enforces whatever `CMP-CP-01` returns. |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | Owner field in §1 remains "DEFERRED" until populated. |
| `CLAR-DB-01` | `scans` table not explicitly enumerated by `SDD.md CMP-CP-03` | **DEFERRED** | `DOC-DB.md §4.11` adds it as a derived table; ORCH-01 depends on it. No operational block. |
| `CLAR-DEPLOY-06` | Queue technology + DLQ + visibility-timeout / retry semantics | **RESOLVED** | Amazon SQS standard + per-queue DLQ; scan-job visibility 60 min, max-receive 3 (per `DOC-DEPLOY-DECISIONS.md` line 104). |
| `CLAR-DEPLOY-14` | LLM provider + per-tenant quota controls | **RESOLVED** | Anthropic API `claude-sonnet-4-6`; LLM is consumed by `CMP-TRI-01..03`, not by ORCH-01. ORCH-01's relevance is only that PATCH-on-findings can indirectly trigger re-ranking (quota policy at `CMP-CP-01`). |

No new `CLAR-ORCH-*` items are filed by this document; every AC of `CMP-ORCH-01` is unambiguous given the cross-cutting references.

---

## 11. References

- `SDD.md §7 CMP-ORCH-01` — verbatim AC statements.
- `PLAN.md §"Phase 4 — Orchestrator + heuristic scheduler"` — HMAC-bearer pattern.
- `docs/cross-cutting/DOC-API.md §4.1, §4.5, §2.3` — REST surface.
- `docs/cross-cutting/DOC-DB.md §4.11` (`scans`), `§4.7` (`snapshots`) — relational shape.
- `docs/cross-cutting/DOC-PROVENANCE.md §3, §10` — provenance threading.
- `docs/cross-cutting/DOC-PARTITION.md §4` — `CMP-ORCH-03` is the per-finding `origin` setter.
- `docs/cross-cutting/DOC-INV.md §3, §4` — INV-1, INV-2 owner maps.
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — CLAR-DEPLOY-06 (SQS), CLAR-DEPLOY-14 (LLM).
- `docs/components/DOC-CMP-SNAP-01.md` (sibling) — snapshot resolution.
- `docs/components/DOC-CMP-ORCH-02.md` (sibling) — scheduler.
- `docs/components/DOC-CMP-ORCH-03.md` (sibling) — worker + `origin` setter.
- `.claude/rules/00-global.md` (RULE-6), `.claude/rules/02-provenance.md`, `.claude/rules/05-determinism.md`.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-ORCH-01`.*
