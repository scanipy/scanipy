# DOC-API — External API contract

**Status:** ACTIVE (Phase 0 cross-cutting reference)
**Owner:** Documentation Manager Agent
**Source of truth:** `SDD.md` §7 (CMP-ORCH-01), §10 (CMP-CP-01/03/04), §8 (CMP-FND-01..03). Where this document and the SDD disagree, the SDD wins.
**Compliance target:** OpenAPI 3.1.

This document defines the public HTTP surface of Scanipy v3.2. Every endpoint here corresponds to a path enumerated in `SDD.md`; no new endpoints are invented. Where the task-prompt for this document proposed a different URL than the SDD's, the SDD is normative and the alternate is filed as `CLAR-API-01` (see §17 below).

Cross-cutting references this document depends on:

- `.claude/rules/00-global.md` — RULE-6 provenance threading.
- `.claude/rules/02-provenance.md` — the four required provenance fields per emitted Finding.
- `.claude/rules/05-determinism.md` — `origin` semantics.
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — Auth0 (CLAR-DEPLOY-10), three roles (CLAR-DEPLOY-12), Anthropic LLM provider (CLAR-DEPLOY-14), single-region (CLAR-DEPLOY-08).
- `docs/cross-cutting/DOC-DB.md` — persisted shapes referenced by the response schemas.
- `docs/cross-cutting/DOC-SARIF.md` — Findings list and Attestation export emit SARIF v2.1.0 per that contract.

---

## 1. Purpose

The API is the customer- and machine-facing surface of the control plane. It exposes:

- **Scans** — submit, inspect, list findings (CMP-ORCH-01).
- **Snapshots** — submit a snapshot job, inspect its precondition status (CMP-SNAP-01).
- **Codebases** — register and configure source repositories (CMP-CP-03, CMP-SCM-01..03).
- **Findings** — read findings; the only mutable field is `status` (INV-3).
- **Worker callbacks** — `report_status` from analysis workers (CMP-ORCH-03 → CMP-ORCH-01).
- **SCM webhooks** — provider-signed inbound events (CMP-SCM-01..03).
- **Attestation export** — signed-chain export of a scan's provenance (CMP-CP-05, CMP-FND-03).

The API does **not** expose:

- LLM endpoints to customers. The LLM is consumed only by `CMP-TRI-01..03` server-side (`CLAR-DEPLOY-14`).
- IDE-plugin integration (`OOS-IDE-01`).
- CI-agent / on-prem-runner endpoints (`OOS-CI-AGENT-01`).
- Binary-only or container-image scan submission (`OOS-BINARY-01`, `OOS-CONTAINER-SCAN-01`).

OpenAPI 3.1 schema generation is a future task. This document is the human-readable contract; the machine-readable spec MUST be derived from it without semantic drift.

---

## 2. Authentication and authorization

Three authentication channels coexist. Every request carries exactly one.

### 2.1 Customer dashboard — OIDC → JWT bearer (CMP-CP-04, CLAR-DEPLOY-10)

- IdP: **Auth0** (per `DOC-DEPLOY-DECISIONS.md` CLAR-DEPLOY-10).
- Federation: customer IdPs (Okta, Azure AD, Google Workspace) join via Auth0 connections.
- Token: short-lived JWT (default 1 h) bearer in `Authorization: Bearer <jwt>`.
- Claims carried: `sub` (user_id), `https://scanipy.io/org_id`, `https://scanipy.io/role ∈ {org-admin, org-viewer, scanner}`.
- The role claim is set by Auth0 from a custom rule that maps the user's tenant membership.

### 2.2 Scanner machine identity — short-lived OIDC token from CI provider (CMP-ORCH-01, CMP-CP-01, CLAR-DEPLOY-11)

- The scanner role is a machine identity used by GitHub Actions / GitLab CI jobs that submit scans on the customer's behalf.
- Auth pattern: the CI provider's OIDC token is exchanged at `POST /api/v1/auth/exchange` (server-internal) for a Scanipy short-lived JWT bearing `role = scanner` and the resolved `org_id`.
- Exchange validates the OIDC token's `aud`, `iss`, and `repository` claims against the customer's registered SCM credentials (CMP-CP-02).

### 2.3 Worker callback — HMAC bearer (CMP-ORCH-01 AC-ORCH-01b)

- Used by the analysis worker to report job status. The internal callback path (see §4.5) is the only authenticated surface for this.
- Header: `Authorization: HMAC <key-id>:<hex-digest>`.
- HMAC algorithm: HMAC-SHA-256 over the canonical request `(method, path, X-Scanipy-Worker-Id, body-sha256, timestamp)`. The key is rotated per scheduler-issued job.
- AC-ORCH-01b requires a negative test: an invalid HMAC must reject the payload before any state mutation.

### 2.4 SCM webhooks — per-provider signature verification (CMP-SCM-01..03)

- GitHub: `X-Hub-Signature-256` HMAC-SHA-256 over body, key = registered webhook secret.
- GitLab: `X-Gitlab-Token` plain shared secret (provider native).
- Bitbucket: `X-Hub-Signature` HMAC-SHA-256.
- Azure DevOps: shared-secret (Basic-auth `basicAuthPassword`) echo verification — native ADO emits no body HMAC (CLAR-SCM-02).
- AC-SCM-03b requires a negative test per provider: a forged payload is rejected.

### 2.5 Tenancy header (RULE applies to channels 2.1, 2.2 only)

Every authenticated request (dashboard + scanner) MUST carry:

```
X-Scanipy-Org-Id: <uuid>
X-Scanipy-User-Id: <uuid>          # required for dashboard; "scanner" string for scanner role
```

The server MUST verify that the header `X-Scanipy-Org-Id` matches the JWT claim `https://scanipy.io/org_id`. A mismatch returns **403 Forbidden** with `error_code = org_mismatch` (see §5). The mismatch is logged with severity `WARN` to OpenTelemetry as a potential cross-tenant attempt (CMP-CP-01 AC-CP-01a, CLAR-DEPLOY-16).

Worker callbacks do not carry `X-Scanipy-Org-Id`; tenant identity is implicit in the HMAC-keyed job that the worker is reporting on.

### 2.6 RBAC summary (CLAR-DEPLOY-12)

| Role | Scans | Snapshots | Codebases | Findings (read) | Findings (PATCH status) | Attestations |
|---|---|---|---|---|---|---|
| `org-admin` | submit, read | submit, read | create, read, update creds | yes | yes | read |
| `org-viewer` | read | read | read (no creds) | yes | no | read |
| `scanner` | submit, read own | submit, read own | no | yes (own scan) | no | read (own) |

A request that lacks the role for an endpoint returns **403 Forbidden** with `error_code = role_denied`.

---

## 3. Cross-cutting request/response conventions

### 3.1 URL prefix and versioning

All endpoints are prefixed `/api/v1/`. The `v1` prefix is the major version axis; breaking changes require a `v2` prefix. Deprecation policy: an endpoint is announced deprecated in release notes; it carries the response header `Deprecation: true` and `Sunset: <RFC 9745 date>` for at least 90 days before removal.

The worker-callback path (SDD-normative: `POST /api/v1/jobs/{job_id}/status`) is firewalled from public ingress at the network layer (private subnet only, per CLAR-DEPLOY-09); the path is not sub-prefixed under `/api/v1/internal/` in the SDD. Whether to move it under such a sub-prefix is part of `CLAR-API-01`.

### 3.2 Content type

- Request: `application/json; charset=utf-8`.
- Response: `application/json; charset=utf-8` for resource endpoints; `application/sarif+json` (or `application/json` with `sarif_log` wrapper) for the SARIF-bearing endpoints (`GET …/findings`, `GET /attestations/{scan_id}`).

### 3.3 Trace propagation

Every request MUST be accepted with a W3C `traceparent` header. When absent, the server generates one and echoes it in the response header `X-Scanipy-Trace-Id` (which equals the OTel trace_id, per CLAR-DEPLOY-07).

### 3.4 Idempotency

- `POST /api/v1/scans`: idempotency key required as header `Idempotency-Key: <uuid>`. Replaying the same key returns the same scan id without re-enqueueing.
- `POST /snapshots`: idempotency by natural key `(codebase_id, commit_sha, env_digest)`. A second POST with the same triple returns the existing snapshot id (200, not 201).
- `POST /api/v1/webhooks/*`: providers send their own event IDs; the server dedupes by `(provider, delivery_id)`.

### 3.5 Pagination

List endpoints support cursor pagination. Query params:

```
limit: int (default 50, max 200)
cursor: opaque-string (server-issued)
```

Responses carry `next_cursor` (null when the page is the last).

Per-tenant rate limits in §6 apply; cursor walking is a single API call per page and is rate-counted accordingly.

---

## 4. Endpoint catalog

### 4.1 Scans

#### POST /api/v1/scans

Submit a scan against a snapshot (`SDD.md` line 193, CMP-ORCH-01).

- **Roles:** `org-admin`, `scanner`.
- **Headers:** `Authorization`, `X-Scanipy-Org-Id`, `X-Scanipy-User-Id`, `Idempotency-Key`.
- **Request body:**
  ```json
  {
    "codebase_id": "uuid",
    "commit_sha": "string (40 hex chars)",
    "detector_ids": ["string", "..."],
    "S_version": "semver string (optional; defaults to latest accepted)",
    "policy_overrides": { "object (optional)" }
  }
  ```
- **Behavior (AC-ORCH-01a):**
  1. Resolve or create the snapshot for `(codebase_id, commit_sha, env_digest)`.
  2. Fan one job per `detector_id` onto the per-detector SQS queue (CLAR-DEPLOY-06).
- **Response (201):**
  ```json
  {
    "scan_id": "uuid",
    "snapshot_id": "uuid",
    "status": "queued",
    "S_version": "1.4.0",
    "env_digest": "sha256:abc…",
    "created_at": "RFC3339"
  }
  ```
- **Status codes:** 201 Created · 200 OK on idempotency replay · 400 invalid input · 401 unauth · 403 role denied / org mismatch · 409 detector unknown · 429 rate-limited.

#### GET /api/v1/scans/{scan_id}

Read scan status.

- **Roles:** `org-admin`, `org-viewer`, `scanner` (own only).
- **Response (200):**
  ```json
  {
    "scan_id": "uuid",
    "snapshot_id": "uuid",
    "codebase_id": "uuid",
    "commit_sha": "string",
    "status": "queued | snapshotting | analysing | normalising | attested | failed",
    "S_version": "semver",
    "env_digest": "sha256:…",
    "started_at": "RFC3339",
    "finished_at": "RFC3339 | null",
    "jobs": [
      { "detector_id": "string", "status": "queued | running | done | failed", "job_id": "uuid" }
    ],
    "findings_count": 124,
    "attestation_status": "pending | core-pass | core-fail | oracle-only"
  }
  ```

#### GET /api/v1/scans/{scan_id}/findings

List findings for a scan (`SDD.md` line 193). SARIF-equivalent payload.

- **Roles:** `org-admin`, `org-viewer`, `scanner` (own only).
- **Query:** `limit`, `cursor`, optional filters `class`, `severity`, `origin`, `status`, `min_triage_score`.
- **Response (200):** an array of Finding objects (see §5 for the Finding schema).
- **Notes:** Findings are returned in canonical CPG order (CMP-FND-01 AC-FND-01b); the canonical order is preserved across paginated cursor walks.

### 4.2 Snapshots

#### POST /snapshots

Submit a snapshot job (`SDD.md` line 97, CMP-SNAP-01).

> **Path note (CLAR-API-01):** the SDD-prescribed path is `POST /snapshots`. The task-prompt for this document proposed `POST /api/v1/snapshots`. The decision to align with the rest of the `/api/v1/` surface is filed as `CLAR-API-01` in WBS.md §17. Until resolved, the SDD path is normative.

- **Roles:** `org-admin`, `scanner`.
- **Headers:** `Authorization`, `X-Scanipy-Org-Id`, `X-Scanipy-User-Id`.
- **Request body:**
  ```json
  { "codebase_id": "uuid", "commit_sha": "string (40 hex)" }
  ```
- **Behavior (CMP-SNAP-01 AC-SNAP-01a/b/c):**
  - Persists five artifacts at deterministic S3 keys per CLAR-DEPLOY-02: CPG tarball, reverse-symbol index, dynamic call graph, ΔG, precondition-status record.
  - Stamps `env_digest` from the pinned worker container image digest (CLAR-DEPLOY-13, AC-SNAP-05b).
  - Sets `precondition_status ∈ {closed-world, degraded, full-reparse}` via CW-DETECT (CMP-SNAP-03).
- **Response (201 or 200 on idempotency replay):**
  ```json
  {
    "snapshot_id": "uuid",
    "codebase_id": "uuid",
    "commit_sha": "string",
    "env_digest": "sha256:…",
    "precondition_status": "closed-world | degraded | full-reparse",
    "artifact_uris": {
      "cpg_tarball": "s3://…",
      "reverse_symbol_index": "s3://…",
      "dynamic_call_graph": "s3://…",
      "delta_g": "s3://…",
      "precondition_status_record": "s3://…"
    },
    "created_at": "RFC3339"
  }
  ```

#### GET /api/v1/snapshots/{snapshot_id}

Read snapshot. Response shape mirrors the POST response.

### 4.3 Codebases

#### POST /api/v1/codebases

Register a codebase (CMP-CP-03).

- **Roles:** `org-admin`.
- **Request body:**
  ```json
  {
    "name": "string",
    "scm_provider": "github | gitlab | bitbucket | azure-devops",
    "scm_repo_url": "string",
    "default_branch": "string (optional)"
  }
  ```
- **Response (201):**
  ```json
  { "codebase_id": "uuid", "name": "...", "scm_provider": "github", "scm_repo_url": "...", "default_branch": "main" }
  ```

#### GET /api/v1/codebases

List codebases the caller's org owns.

- **Roles:** `org-admin`, `org-viewer`.
- **Query:** `limit`, `cursor`, optional `scm_provider`.

#### POST /api/v1/codebases/{codebase_id}/scm_credentials

Attach SCM credentials (encrypted via CMP-CP-02, CLAR-DEPLOY-04).

- **Roles:** `org-admin`.
- **Request body:**
  ```json
  {
    "auth_mode": "pat | app | oauth | ssh-key",
    "credential": "string (raw; immediately encrypted)",
    "label": "string (optional)"
  }
  ```
- **Response (201):**
  ```json
  { "scm_credential_id": "uuid", "auth_mode": "pat", "label": "...", "fingerprint": "sha256 of plaintext (display only)", "created_at": "RFC3339" }
  ```
- **Notes:** The raw credential is NEVER stored. Only its KMS-encrypted ciphertext and a display fingerprint persist (CMP-CP-02 AC-CP-02a, INV-2 does not apply here).

### 4.4 Findings

#### GET /api/v1/findings

List findings across scans (org-scoped).

- **Roles:** `org-admin`, `org-viewer`, `scanner` (limited).
- **Query:** `limit`, `cursor`, `codebase_id`, `class`, `severity`, `origin`, `status`, `since`, `until`.
- **Response (200):** array of Finding objects (see §5).

#### PATCH /api/v1/findings/{finding_id}

Mutate finding status only. INV-3 forbids any other field mutation.

- **Roles:** `org-admin`.
- **Request body:**
  ```json
  { "status": "open | suppressed | fixed", "suppression_reason": "string (required when status = suppressed)" }
  ```
- **Allowed transitions:**
  - `open → suppressed` (allowed; reason required).
  - `open → fixed` (allowed; usually set automatically when the finding does not reappear in the next scan).
  - `suppressed → open` (allowed; reason cleared).
  - **No PATCH may touch** `origin`, `S_version`, `env_digest`, `cpg_order_hash`, `slice_fingerprint`, `fingerprint_class`, `determinism_partition`, `witness_blob_uri`, `triage_*`, detection-content columns. These are immutable on the API surface (CMP-FND-02 AC-FND-02a + INV-1/INV-2/INV-3 + INV-5 fenceposts).
- **A PATCH that requests deletion of a `deterministic-core` finding is rejected with `error_code = invariant_inv3_violation`.** Suppressing is allowed (visible-with-status-suppressed); deleting is not.
- **Response (200):** the full updated Finding object.

### 4.5 Worker callbacks (internal)

#### POST /api/v1/jobs/{job_id}/status

Worker reports job status (`SDD.md` line 193, CMP-ORCH-01 AC-ORCH-01b).

> **Path note (CLAR-API-01):** the SDD-prescribed path is `POST /api/v1/jobs/{job_id}/status`. The task-prompt proposed `POST /api/v1/internal/workers/{worker_id}/report_status`. The SDD path is normative. The `internal` sub-prefix proposed by the prompt may be added without changing the relative path; pending CLAR-API-01.

- **Authentication:** HMAC bearer (§2.3).
- **Headers:** `Authorization: HMAC <key-id>:<digest>`, `X-Scanipy-Worker-Id: <id>`, `X-Scanipy-Job-Timestamp: <unix-epoch-seconds>`.
- **Request body:**
  ```json
  {
    "job_id": "uuid",
    "scan_id": "uuid",
    "status": "running | done | failed",
    "S_version": "semver (required; INV-2)",
    "env_digest": "sha256:… (required; INV-2)",
    "findings_count": 42,
    "core_partition_count": 30,
    "oracle_partition_count": 12,
    "result_uri": "s3://… (SARIF blob; required when status=done)",
    "witness_uri": "s3://… (optional, oracle findings may omit)",
    "error": { "code": "string", "message": "string" }
  }
  ```
- **Behavior:** verifies HMAC; rejects with 401 on mismatch (AC-ORCH-01b). On `done`: triggers Findings Normalizer (CMP-FND-01) and Attestor (CMP-CP-05) downstream. Idempotent: a second `done` for the same `job_id` is a no-op.
- **Status codes:** 204 No Content on success · 401 invalid HMAC · 404 unknown job · 409 conflicting status transition.

### 4.6 SCM webhooks

#### POST /api/v1/webhooks/{provider}

Receive SCM provider events.

- **`{provider}` ∈ {github, gitlab, bitbucket, azure-devops}**.
- **Authentication:** per-provider signature (§2.4).
- **Behavior:** parses the event (push, pull_request, repository), maps it to a `(codebase_id, commit_sha)`, and enqueues a snapshot via the internal SNS topic (downstream of CMP-SNAP-01).
- **Response:** 204 No Content (event accepted) · 401 invalid signature · 422 unrecognised event type (logged, not retried).
- **Idempotency:** server dedupes on `(provider, delivery_id)`.

### 4.7 Attestation export

#### GET /api/v1/attestations/{scan_id}

Export the signed provenance chain for a scan (CMP-CP-05, CMP-FND-03 AC-FND-03a).

- **Roles:** `org-admin`, `org-viewer`, `scanner` (own scan only).
- **Query:** `format = sarif | provenance | both` (default `both`).
- **Response (200):**
  ```json
  {
    "scan_id": "uuid",
    "S_version": "semver",
    "env_digest": "sha256:…",
    "attestation_status": "core-pass | core-fail | oracle-only",
    "attestor_hash": "sha256:…",
    "signed_chain": {
      "source_commit": "string",
      "snapshot_digest": "sha256:…",
      "S_version": "semver",
      "env_digest": "sha256:…",
      "cpg_order_hash": "sha256:…",
      "cpg_order_hash_annotation": "canonical iff fingerprint_class = strong",
      "results_sarif_hash": "sha256:…",
      "per_finding_origins_summary": { "deterministic-core": 30, "oracle-passthrough": 12 },
      "repartition_events": [
        { "event_id": "uuid", "occurred_at": "RFC3339", "trigger": "differential-oracle-disagreement", "finding_ids": ["uuid", "..."] }
      ],
      "signature": { "kms_key_arn": "kms-arn", "kms_key_version": "string", "signature_alg": "RSASSA_PSS_SHA_256", "value": "base64url" }
    },
    "sarif_log_uri": "s3://…  (if format=sarif|both)"
  }
  ```
- **Notes:** the chain is independently verifiable from stored artifacts without re-running analysis (AC-FND-03a). The `cpg_order_hash_annotation` field is non-elidable (INV-5).

---

## 5. The Finding response object

Every API surface that emits Findings (4.1, 4.4, the SARIF emission referenced from 4.7) carries the same shape. Provenance threading (RULE-6) is non-elidable.

```json
{
  "finding_id": "uuid",
  "codebase_id": "uuid",
  "scan_id": "uuid",
  "snapshot_id": "uuid",
  "commit_sha": "string",

  "class": "injection | path-traversal | ssrf | deserialization | xss | crypto-misuse | authn-authz | secrets | dep-cve | memory-safety",
  "rule_id": "string",
  "severity": "info | low | medium | high | critical",
  "message": "string",
  "physical_location": {
    "uri": "string (repo-relative path)",
    "start_line": 42, "start_column": 13, "end_line": 42, "end_column": 27
  },

  "origin": "deterministic-core | oracle-passthrough",
  "S_version": "semver string",
  "env_digest": "sha256:…",
  "cpg_order_hash": "sha256:…",
  "cpg_order_hash_annotation": "canonical iff fingerprint_class = strong",

  "fingerprint_class": "strong | weak",
  "slice_fingerprint": "sha256:…",
  "determinism_partition": "deterministic-core | oracle-passthrough",
  "engine": "ifds | ide | semgrep | cpg-query | external",
  "witness_blob_uri": "s3://… | null",
  "precondition_status": "closed-world | degraded | full-reparse",
  "spec_provenance": "global-unrevalidated | global-revalidated | customer | null",

  "triage_score": "number 0..1 | null",
  "triage_reason": "string | null",

  "status": "open | suppressed | fixed",
  "suppression_reason": "string | null",

  "created_at": "RFC3339",
  "updated_at": "RFC3339"
}
```

Mandatory non-null (INV-1 + INV-2 + INV-5): `origin`, `S_version`, `env_digest`, `cpg_order_hash`, `cpg_order_hash_annotation`, `fingerprint_class`, `slice_fingerprint`, `determinism_partition`, `engine`, `precondition_status`, `status`.

Nullable: `witness_blob_uri` (oracle findings may omit), `triage_score` / `triage_reason` (null when `LLM_TRIAGE=off` per CMP-CP-05 AC-CP-05c), `spec_provenance` (null when finding does not depend on a customer-revalidatable spec), `suppression_reason` (null unless `status=suppressed`).

### 5.1 Conditional-canonicality annotation rule

The `cpg_order_hash_annotation` field MUST appear in the same JSON object as `cpg_order_hash`. Emitters MUST NOT serialize `cpg_order_hash` without the adjacent annotation string `canonical iff fingerprint_class = strong`. Auditor exports, dashboards, and SDK clients are required to surface the annotation alongside the hash (INV-5; CMP-CORE-03 AC-CORE-03c; CMP-FND-03 AC-FND-03b).

---

## 6. Error envelope

All errors share a single JSON shape:

```json
{
  "error_code": "string (snake_case)",
  "message": "string (human-readable; no PII)",
  "trace_id": "string (W3C trace_id; equals X-Scanipy-Trace-Id)",
  "details": { "object | null" }
}
```

The `trace_id` maps to AWS X-Ray (per CLAR-DEPLOY-07). The customer support portal accepts a `trace_id` to retrieve correlated logs.

### 6.1 Reserved `error_code` values

| `error_code` | HTTP | Meaning |
|---|---|---|
| `unauthenticated` | 401 | Missing or invalid auth |
| `invalid_hmac` | 401 | Worker-callback HMAC failed (AC-ORCH-01b) |
| `invalid_webhook_signature` | 401 | SCM-webhook signature failed (AC-SCM-03b) |
| `role_denied` | 403 | Caller's role insufficient for this endpoint |
| `org_mismatch` | 403 | `X-Scanipy-Org-Id` ≠ JWT org claim |
| `tenant_isolation_violation` | 403 | Cross-tenant resource access attempt (RLS-backed; AC-CP-01a) |
| `invariant_inv1_violation` | 422 | A request that would emit a finding without `origin` |
| `invariant_inv2_violation` | 422 | A request that would emit a finding without `S_version` / `env_digest` |
| `invariant_inv3_violation` | 422 | A request that would delete or LLM-mutate a `deterministic-core` finding |
| `idempotency_conflict` | 409 | Same `Idempotency-Key` with a different body |
| `conflicting_status_transition` | 409 | Worker callback status conflicts with the recorded terminal job state (§4.5) |
| `rate_limited` | 429 | Per-tenant quota exceeded |
| `llm_quota_exceeded` | 429 | Per-tenant LLM-bearing endpoint quota exceeded |
| `not_found` | 404 | Resource does not exist or is not in caller's tenant |
| `invalid_input` | 400 | Schema validation failed |
| `internal_error` | 500 | Unhandled server error; trace_id is the recovery hook |

---

## 7. Rate limits and quotas

Per-tenant quotas are enforced at the API guard (CMP-CP-01). Two budget axes:

### 7.1 General API budget

- Sustained: **60 requests/sec per `org_id`** (token bucket, capacity 120).
- Burst: 200 requests/sec for 5 s, then drained.
- Headers on every response: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` (Unix-epoch seconds).
- Exceeded: 429 `rate_limited`.

### 7.2 LLM-bearing endpoints (per CLAR-DEPLOY-14)

Endpoints that synchronously call the LLM (currently: none directly customer-facing; the LLM is consumed server-side by `CMP-TRI-01..03`). Per-tenant LLM budgets are still tracked because PATCH operations on findings can indirectly trigger re-ranking:

- Per-tenant requests-per-minute (RPM) and tokens-per-day (TPD) budgets are enforced on the server-side LLM call path.
- Numeric defaults are **TBD per CMP-CP-01 policy** and filed as `CLAR-SLA-02` (see §17).
- Exceeded: 429 `llm_quota_exceeded`.

### 7.3 Per-endpoint defaults

`POST /api/v1/scans` is capped at **600/hour per org**; `POST /snapshots` at **1200/hour per org**; `POST /api/v1/webhooks/*` is uncapped (provider-driven, deduped on delivery ID).

---

## 8. Reference matrix

| Endpoint | Owning component | Acceptance criteria touched |
|---|---|---|
| `POST /api/v1/scans` | CMP-ORCH-01 | AC-ORCH-01a, AC-ORCH-01c |
| `GET /api/v1/scans/{id}` | CMP-ORCH-01 | AC-ORCH-01a |
| `GET /api/v1/scans/{id}/findings` | CMP-FND-01, CMP-ORCH-01 | AC-FND-01a, AC-FND-01b |
| `POST /snapshots` | CMP-SNAP-01 | AC-SNAP-01a..c |
| `GET /api/v1/snapshots/{id}` | CMP-SNAP-01 | AC-SNAP-01a..c |
| `POST /api/v1/codebases` | CMP-CP-03 | AC-CP-03a |
| `GET /api/v1/codebases` | CMP-CP-03, CMP-CP-01 | AC-CP-01a |
| `POST /api/v1/codebases/{id}/scm_credentials` | CMP-CP-02, CMP-SCM-01 | AC-CP-02a, AC-SCM-01b |
| `GET /api/v1/findings` | CMP-FND-01, CMP-FND-02 | AC-FND-02a, AC-FND-02b |
| `PATCH /api/v1/findings/{id}` | CMP-FND-02, CMP-TRI-01 | AC-TRI-01a, AC-TRI-01b, INV-3 |
| `POST /api/v1/jobs/{job_id}/status` | CMP-ORCH-01, CMP-ORCH-03 | AC-ORCH-01b, AC-ORCH-03a, AC-ORCH-03b |
| `POST /api/v1/webhooks/{provider}` | CMP-SCM-01..03 | AC-SCM-03b |
| `GET /api/v1/attestations/{scan_id}` | CMP-CP-05, CMP-FND-03 | AC-CP-05a..c, AC-FND-03a..c |

---

## 9. CLARIFICATION items filed by this document

(Mirrored in `WBS.md §17`.)

- **CLAR-API-01** — `POST /snapshots` vs `POST /api/v1/snapshots`, and `POST /api/v1/jobs/{job_id}/status` vs `POST /api/v1/internal/workers/{worker_id}/report_status`. The SDD path is normative; a follow-up may be filed to align all paths under `/api/v1/`. Blocks: none (SDD path is unambiguous). Target: housekeeping prior to GA.
- **CLAR-SLA-02** — Numeric per-tenant rate-limit + LLM RPM/TPD budgets (CLAR-DEPLOY-14 names the vendor, not the budgets). Blocks: `CMP-CP-01` enforcement defaults. Target: before Stage A go-live.

---

*Cross-reference: `SDD.md` §7, §8, §10, `DOC-DEPLOY-DECISIONS.md` CLAR-DEPLOY-{08,10,11,12,14,16}, `DOC-DB.md`, `DOC-SARIF.md`, `.claude/rules/00-global.md` RULE-6, `.claude/rules/02-provenance.md`.*
