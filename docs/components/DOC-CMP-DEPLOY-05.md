# DOC-CMP-DEPLOY-05 — Tenant data isolation

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `WBS.md §2.4 CMP-DEPLOY-05` (Purpose + AC-DEPLOY-05a/b).
- `SDD.md §10 CMP-CP-01` (`AC-CP-01a` — cross-org access denial; `CMP-DEPLOY-05` is the substrate backstop).
- `SDD.md §10 CMP-CP-03` (`AC-CP-03a` — tenancy schema; the RLS hook lives here).
- `WBS.md §17` — `CLAR-DEPLOY-16` (RESOLVED — three-layer isolation), `CLAR-DEPLOY-02` (RESOLVED — `orgs/{org_id}/...` S3 prefix), `CLAR-DEPLOY-04` (RESOLVED — per-tenant CMKs).
- `WBS.md §17` — `CLAR-DB-02` (**DEFERRED** — RLS session-variable scheme `app.org_id` not pinned by SDD; this document proposes the implementation per `DOC-DB §3.2`).
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — CLAR-DEPLOY-16, CLAR-DEPLOY-02, CLAR-DEPLOY-04.
- `docs/cross-cutting/DOC-DB.md §3.3` — standard RLS policy template (`app.org_id` session variable).
- `docs/cross-cutting/DOC-RUNBOOK.md §9` — tenant operations (onboarding, offboarding, per-tenant data export).
- `.claude/rules/00-global.md` (RULE-9 Security Analyst reviews INV-3/INV-4 components — this one touches INV-3 by being the credential-decryption boundary).

This document is the **implementation contract** for `CMP-DEPLOY-05`. It enforces the three-layer tenant-isolation backstop from `CLAR-DEPLOY-16`: (1) IAM session policies scoped per `org_id`; (2) PostgreSQL Row-Level Security keyed on `app.org_id`; (3) per-tenant KMS CMKs for credentials and signed provenance. The component is a backstop to application-level isolation (`CMP-CP-01`), not a substitute for it.

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-DEPLOY-05` |
| Subsystem | Deployment (`WBS.md §2.4`) |
| Staging | cross-cutting (`WBS.md §2.4`) |
| Depends-On | `CMP-DEPLOY-01`, `CMP-CP-01`, `CMP-CP-03` (`WBS.md §20`) |
| Owner | **DEFERRED** via `CLAR-OWNER-01`; operational owner per `.claude/commands/sre-agent.md` is the SRE/DevOps Agent; **Security Analyst sign-off required** (this is a credential-handling component, RULE-9). |
| INV-* touched | **INV-3 substrate (credential isolation).** Per-tenant CMKs (`CLAR-DEPLOY-04`) make cross-tenant credential decryption impossible without explicit role assumption — this is the substrate guarantee that backs INV-3's "no LLM influence outside pinned `S`" by ensuring tenant `S_customer` cannot leak across tenants at the storage layer. Also substrate for `AC-CP-01a` (no cross-org access). |
| Substrate | IAM session policies (per scan) · PostgreSQL Row-Level Security (per request) · AWS KMS per-tenant CMKs (per `orgs.id`) — the three layers from CLAR-DEPLOY-16. |

---

## 2. Mandate

**Verbatim WBS `Purpose:` (`WBS.md §2.4 CMP-DEPLOY-05`):**

> Enforce that no worker, query path, or object-store access can cross an org boundary. Backstop for `AC-CP-01a` at the runtime layer rather than only in application code.

**Operational role.** `CMP-DEPLOY-05` is the **substrate-level tenant-isolation backstop**. Application code (CMP-CP-01) is the first line of defence — every API request is scoped to `org_id` and queries are filtered. `CMP-DEPLOY-05` adds three further layers so an application bug cannot leak across tenants: (a) **IAM session policies** scoped to a single `org_id` per scan so a worker physically cannot read another tenant's S3 prefix, (b) **PostgreSQL RLS** so a query that forgets a `WHERE org_id = ?` clause returns zero rows instead of cross-tenant rows, and (c) **per-tenant KMS CMKs** so even a worker that somehow holds another tenant's ciphertext cannot decrypt it. The three layers are independent — each one would individually block a cross-tenant leak.

---

## 3. Interface contract

`CMP-DEPLOY-05` does not run as a service. Its interfaces are configuration surfaces consumed by other components:

1. **IAM session-policy templates** in `infra/modules/compute/session_policy.tf`, consumed by `CMP-ORCH-03` and `CMP-SNAP-05` at task launch.
2. **RLS policy templates** in `db/migrations/<timestamp>_enable_rls.py`, consumed by `CMP-CP-03` schema migrations.
3. **Per-tenant CMK provisioning Lambda** in `infra/modules/kms/tenant_cmk_lambda.py`, invoked by `CMP-CP-02` at tenant onboarding.
4. **Negative-test corpus** in `tests/integration/tenant_isolation/`, exercising `AC-DEPLOY-05a/b`.

### 3.1 Layer 1 — IAM session policies scoped per `org_id`

When a worker dequeues an SQS message for `org_id = X`, the orchestrator calls `sts:AssumeRole` with a **session policy** that restricts S3 access to `orgs/X/*` and KMS access to the `org-X` CMK. The worker's task role grants broad S3 permissions, but the session policy intersects them.

```hcl
# infra/modules/compute/session_policy.tf — template; TEMPLATE_ORG_ID and
# TEMPLATE_TENANT_CMK_ARN are substituted at runtime by CMP-ORCH-03.

data "aws_iam_policy_document" "worker_session_policy_template" {
  # S3 Layer 1a: object-level allow for this tenant's prefix.
  # s3:ListBucket is a bucket-level action and lives in its own statement below.
  statement {
    sid     = "S3PerTenantAllow"
    effect  = "Allow"
    actions = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = [
      "arn:aws:s3:::scanipy-prod-snapshot/orgs/${TEMPLATE_ORG_ID}/*",
      "arn:aws:s3:::scanipy-prod-witness/orgs/${TEMPLATE_ORG_ID}/*",
      "arn:aws:s3:::scanipy-prod-sarif/orgs/${TEMPLATE_ORG_ID}/*",
    ]
  }

  # S3 Layer 1b: platform read-only (canary corpus, CPG fidelity fixtures — no write).
  statement {
    sid     = "S3PlatformReadOnly"
    effect  = "Allow"
    actions = ["s3:GetObject"]
    resources = ["arn:aws:s3:::scanipy-prod-snapshot/_platform/*"]
  }

  # S3 Layer 1c: ListBucket restricted to this tenant's prefix via s3:prefix condition.
  # Targets bucket-level ARNs (AWS ignores path suffixes on s3:ListBucket).
  statement {
    sid     = "S3PerTenantListBucket"
    effect  = "Allow"
    actions = ["s3:ListBucket"]
    resources = [
      "arn:aws:s3:::scanipy-prod-snapshot",
      "arn:aws:s3:::scanipy-prod-witness",
      "arn:aws:s3:::scanipy-prod-sarif",
    ]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["orgs/${TEMPLATE_ORG_ID}/*", "_platform/*"]
    }
  }

  # S3 Layer 1d: deny every other org prefix (defence-in-depth).
  # not_resources includes bucket-level ARNs to cover s3:ListBucket.
  statement {
    sid       = "S3OtherOrgsDeny"
    effect    = "Deny"
    actions   = ["s3:*"]
    not_resources = [
      "arn:aws:s3:::scanipy-prod-snapshot/orgs/${TEMPLATE_ORG_ID}/*",
      "arn:aws:s3:::scanipy-prod-witness/orgs/${TEMPLATE_ORG_ID}/*",
      "arn:aws:s3:::scanipy-prod-sarif/orgs/${TEMPLATE_ORG_ID}/*",
      "arn:aws:s3:::scanipy-prod-snapshot/_platform/*",
      "arn:aws:s3:::scanipy-prod-snapshot",
      "arn:aws:s3:::scanipy-prod-witness",
      "arn:aws:s3:::scanipy-prod-sarif",
    ]
  }

  # KMS Layer 3: only the per-tenant CMK ARN for this org_id.
  statement {
    sid     = "KMSPerTenantAllow"
    effect  = "Allow"
    actions = ["kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
    resources = ["${TEMPLATE_TENANT_CMK_ARN}"]
  }

  statement {
    sid     = "KMSOtherCMKsDeny"
    effect  = "Deny"
    actions = ["kms:Decrypt", "kms:GenerateDataKey"]
    not_resources = ["${TEMPLATE_TENANT_CMK_ARN}"]
  }
}
```

The session policy is constructed at task-launch by `CMP-ORCH-03` from a template + the SQS message's `org_id` attribute. The orchestrator then calls `sts:AssumeRole` with the session policy and uses the temporary credentials in the worker's environment.

### 3.2 Layer 2 — PostgreSQL Row-Level Security

Per `CLAR-DEPLOY-16` and `DOC-DB §3.3`, every multi-tenant table has an RLS policy that filters rows by `app.org_id`. The session variable `app.org_id` is set by the application connection pool per request.

```sql
-- db/migrations/<timestamp>_enable_rls.py (the SQL emitted by the Alembic migration)

ALTER TABLE findings ENABLE ROW LEVEL SECURITY;

CREATE POLICY findings_tenant_isolation ON findings
  USING (org_id::text = current_setting('app.org_id', true));

ALTER TABLE snapshots ENABLE ROW LEVEL SECURITY;
CREATE POLICY snapshots_tenant_isolation ON snapshots
  USING (org_id::text = current_setting('app.org_id', true));

-- ... one CREATE POLICY per multi-tenant table per DOC-DB §3.3.
```

The application sets the session variable on every connection checkout:

```python
# services/<service>/db.py — connection-pool guard per DOC-DB §3.4.
def acquire_for_request(org_id: str) -> Connection:
    conn = pool.checkout()
    with conn.cursor() as cur:
        cur.execute("SET app.org_id = %s", (org_id,))
    return conn
```

A connection released back to the pool without resetting `app.org_id` would leak across requests — `acquire_for_request` MUST be paired with `release_for_request` that `RESET app.org_id`s before returning the connection. The pool wrapper enforces this.

**Bypass:** the schema migration runs as a superuser role (`scanipy_migrate`); RLS is `FORCE`'d on all tenant-data roles (`scanipy_api`, `scanipy_worker`) but not on `scanipy_migrate`. Migrations cannot leak across tenants because they don't read tenant data.

**Cross-reference:** the RLS template here, the session-variable scheme (`app.org_id`), and the connection-pool guard are documented in detail in `DOC-DB §3.3` and `§3.4`. **`CLAR-DB-02` (DEFERRED)** notes that the SDD does not pin the session-variable scheme; this document follows the `DOC-DB §3.2` proposal pending Security Analyst sign-off. If Security Analyst rejects `app.org_id`, this section follows whatever scheme is ratified.

### 3.3 Layer 3 — Per-tenant KMS CMKs

Per `CLAR-DEPLOY-04` and `CLAR-DEPLOY-16`, every tenant gets a dedicated Customer-Managed KMS Key on first onboarding. The CMK is used to encrypt:

- `scm_credentials.encrypted_token` (per `CMP-CP-02`)
- `provenance_records.signed_chain` signing keys (per `CMP-FND-03`)
- Per-tenant secrets in Secrets Manager (per `CMP-CP-02`)

Provisioning happens via a Lambda function (`tenant_cmk_lambda.py`) invoked synchronously at tenant creation:

```python
# infra/modules/kms/tenant_cmk_lambda.py — simplified contract.
import boto3

def provision_tenant_cmk(org_id: str) -> str:
    """Create a new KMS CMK scoped to this org. Returns the key alias.

    Called by CMP-CP-02 on tenant onboarding.  Idempotent: if the alias
    already exists, returns the existing key ARN without recreating.
    """
    kms = boto3.client("kms")
    alias = f"alias/scanipy-tenant-{org_id}"
    try:
        existing = kms.describe_key(KeyId=alias)
        return existing["KeyMetadata"]["Arn"]
    except kms.exceptions.NotFoundException:
        pass

    key = kms.create_key(
        Description=f"Per-tenant CMK for {org_id}",
        KeyUsage="ENCRYPT_DECRYPT",
        KeySpec="SYMMETRIC_DEFAULT",
        Tags=[{"TagKey": "org_id", "TagValue": org_id}],
    )
    kms.create_alias(AliasName=alias, TargetKeyId=key["KeyMetadata"]["KeyId"])
    kms.enable_key_rotation(KeyId=key["KeyMetadata"]["KeyId"])  # annual rotation per CLAR-DEPLOY-04
    return key["KeyMetadata"]["Arn"]
```

**Key policy:** the CMK's resource policy restricts `kms:Decrypt` and `kms:GenerateDataKey` to the worker task role **only when** the assumed session has `org_id = X` in its session tags. This is a defence-in-depth check; the session policy from §3.1 is the primary boundary.

**Rotation:** annual via KMS automatic rotation per `CLAR-DEPLOY-04`. Prior key versions remain available so existing ciphertext continues to decrypt; new writes use the rotated version. See `DOC-RUNBOOK §5.1, §5.2`.

### 3.4 The composite contract

A cross-tenant access attempt must be blocked by **at least one** of the three layers. The negative-test corpus from `AC-DEPLOY-05a` exercises each layer independently:

| Attack vector | Layer that blocks |
|---|---|
| Worker for org A tries to `s3:GetObject` on `orgs/B/...` | Layer 1 (IAM session policy denies). |
| API request with `X-Scanipy-Org-Id: A` issues a query that returns rows from org B (e.g. a SQL injection or a forgotten WHERE clause) | Layer 2 (RLS filters to zero rows). |
| Worker holds ciphertext for org B's `scm_credentials` (e.g. memory disclosure) but its session is for org A | Layer 3 (KMS CMK policy denies decrypt). |

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| `org_id` on SQS messages | `CMP-ORCH-01` / `CMP-SNAP-01` enqueue | Always present; the orchestrator constructs the session policy from this. |
| `X-Scanipy-Org-Id` HTTP header | API requests (per `CMP-CP-01`) | The API middleware sets `app.org_id` on the DB connection. |
| Tenant CMK provisioning request | `CMP-CP-02` at tenant onboarding | One call per `orgs.id` insert. |
| Multi-tenant table list | `DOC-DB §4` (`findings`, `snapshots`, `codebases`, `scm_credentials`, `org_policies`, `memberships`, `proposed_specs`, `spec_versions`, `attestations`, `triage_scores`, `repartition_events`, `provenance_records`) | Every table with `org_id` column gets an RLS policy in `CMP-CP-03` migrations. |

### 4.2 Outputs

| Output | Where | Contract |
|---|---|---|
| Per-task IAM session policies | Ephemeral STS credentials in worker env | Lifetime = single SQS message; auto-expires. |
| RLS policies on every multi-tenant table | RDS PostgreSQL (created by Alembic migration in `CMP-CP-03`) | Enforced by PG kernel; cannot be bypassed by application code. |
| Per-tenant CMK | AWS KMS | One per `orgs.id`; alias = `alias/scanipy-tenant-{org_id}`. |
| Audit log entries on cross-tenant attempts | CloudWatch Logs (`AC-DEPLOY-05a`) | Every 4xx with `tenant_isolation_violation` reason carries `attempted_org_id`, `actual_org_id`, `path`, `source_ip`. |

---

## 5. Invariants touched

| Invariant | How `CMP-DEPLOY-05` discharges it | Test |
|---|---|---|
| **INV-3 substrate (credential isolation)** | Per-tenant CMKs make cross-tenant credential decryption impossible without explicit role assumption (which `CMP-DEPLOY-04`'s OIDC trust policy denies for non-platform identities). This is what makes a tenant's `S_customer` truly tenant-scoped — even a worker compromise on org A cannot decrypt org B's spec ciphertext. | `TST-AC-DEPLOY-05a` `[FORTHCOMING]`; cross-test with `TST-INV-3-CP-05` (downstream — the LLM_TRIAGE=off attestor run requires that `S` per tenant is well-defined). |
| **AC-CP-01a substrate backstop** | Layer 2 (RLS) blocks a cross-tenant query at the DB layer even if `CMP-CP-01`'s middleware fails to scope the query. Layer 1 (IAM) blocks at the S3 layer even if the API authenticates the wrong org. | `TST-AC-DEPLOY-05a/b`; cross-test with `TST-AC-CP-01a`. |
| **INV-2 supporting** | The S3 prefix `orgs/{org_id}/.../{env_digest}/` co-locates `org_id` and `env_digest` in the key path, making cross-tenant `env_digest` mixups physically impossible (a tenant's snapshot key includes both — the IAM session policy validates the `org_id` portion and the path scheme makes the rest immutable). | Cross-test with `TST-AC-DEPLOY-01b`. |

---

## 6. Algorithm / data flow

### 6.1 Per-scan session policy construction (Layer 1)

```
1. SQS message dequeued by orchestrator.
   message = {snapshot_id, scan_id, org_id, codebase_id, env_digest, ...}

2. Orchestrator computes the per-tenant CMK ARN.
   tenant_cmk_arn = lookup_cmk(org_id)  # from orgs table column 'kms_cmk_arn'

3. Orchestrator constructs the session policy from the template at §3.1
   with TEMPLATE_ORG_ID = org_id, TEMPLATE_TENANT_CMK_ARN = tenant_cmk_arn.

4. Orchestrator calls sts:AssumeRole with:
   - RoleArn = worker_task_role_arn
   - Policy  = session_policy_json  (intersection with the task role's grants)
   - SessionName = f"scan-{scan_id}"
   - DurationSeconds = 3600  (1 hour; longer-than-job-budget margin)

5. Temporary credentials are passed to the Fargate task via:
   - ECS task definition environment overrides (AWS_*_TOKEN env vars), OR
   - A per-task secrets injection (preferred — never logs).

6. The worker uses these credentials for all S3 / KMS / Secrets Manager calls.
   Any access to another tenant's prefix is denied at the STS layer by the
   session policy's explicit Deny statement (§3.1).
```

### 6.2 Per-request RLS guard (Layer 2)

```
1. API request arrives at CMP-CP-01 middleware.
2. Middleware validates the JWT and extracts org_id from claims (CMP-CP-04 Auth0 custom claim).
3. Middleware calls acquire_for_request(org_id) on the connection pool.
4. Connection pool wrapper:
   conn = pool.checkout()
   conn.execute("SET app.org_id = %s", (org_id,))
   yield conn
   conn.execute("RESET app.org_id")
   pool.checkin(conn)

5. The view function runs queries; RLS filters rows by app.org_id.
6. A forgotten WHERE clause is now safe: the query returns ZERO rows for
   other tenants, not all rows. The application sees an empty result and
   typically returns 404 — better than a leak.

7. The connection is released; app.org_id is reset; the next request gets a
   fresh session variable.
```

### 6.3 Tenant CMK provisioning (Layer 3, one-time per tenant)

```
1. New tenant signs up via SSO (CMP-CP-04).
2. CMP-CP-01 middleware sees no existing membership; creates orgs row.
3. CMP-CP-02 calls provision_tenant_cmk(org_id) (§3.3 Lambda).
4. Lambda creates the CMK, sets the alias, enables rotation, returns the ARN.
5. CMP-CP-02 stores the ARN in orgs.kms_cmk_arn.
6. From here, every encryption of tenant-scoped material (scm_credentials,
   per-tenant signing keys) uses this CMK.
```

### 6.4 Cross-tenant access attempt (negative-test flow, `AC-DEPLOY-05a`)

```
1. Test fixture authenticates as org A (gets a valid JWT for org A).
2. Test fixture issues `GET /api/v1/orgs/B/findings` (path traversal attempt).
3. CMP-CP-01 middleware extracts org_id = A from JWT; the URL claims org B.
4. Middleware compares JWT.org_id vs URL.org_id; rejects with 403 + audit log.
   (Layer 2 RLS would block this too: the query SET app.org_id = A but
    SELECT ... WHERE org_id = B returns zero rows. Defense-in-depth.)
5. Audit log entry has structured fields:
   {service: 'api', level: 'WARN', msg: 'tenant_isolation_violation',
    attempted_org_id: 'B', actual_org_id: 'A', path: '/api/v1/orgs/B/findings'}

6. Worker callback variant: a worker for org A tries to call
   POST /api/v1/jobs/{job_id}/status where job_id belongs to org B.
   The HMAC bearer secret is per-platform, but the callback handler validates
   that job_id's org_id matches the caller's session (carried in the SQS
   message). Mismatch -> 403 + audit log.
```

---

## 7. Failure modes and error contracts

| Failure | Detection | Response |
|---|---|---|
| Cross-tenant access attempt at API surface | `CMP-CP-01` middleware comparison | 403 + audit log entry per §6.4; CloudWatch alarm if rate > baseline. |
| Cross-tenant access attempt at S3 (worker bug) | IAM session policy denies | `AccessDenied` from boto3; worker reports `state='failed'`; SQS retry → DLQ. Alarm fires. |
| Cross-tenant access attempt at KMS | KMS CMK key policy denies | `AccessDeniedException`; same response as above. |
| Forgotten `SET app.org_id` on a connection | PG returns zero rows | The application returns an empty result. Lint rule + `acquire_for_request` wrapper prevent this in code; the failure mode is a 404, not a leak. |
| `acquire_for_request` paired without `release_for_request` (session var leaks across requests) | Connection-pool guard in `services/<service>/db.py` (asserts state on checkin) | The guard raises a runtime error; the next request gets a fresh connection from the pool. SRE incident if this happens in production. |
| Tenant CMK provisioning timeout | `CMP-CP-02` Lambda invocation timeout | Tenant onboarding pauses in `provisioning` state. SRE retries; `DOC-RUNBOOK §9.1`. |
| KMS rotation skew (encryption under v1, decryption needs v1 but KMS reports v2) | KMS auto-rotation preserves prior versions | No action — KMS handles this. Documented in `DOC-RUNBOOK §5.1`. |
| Migration enables RLS without setting `app.org_id` default | Migration runs as `scanipy_migrate` (RLS bypassed for this role) | No data leak; subsequent application code must `SET app.org_id` per request. |
| Audit log entry on a cross-tenant attempt is missing | Integration test fixture | `TST-AC-DEPLOY-05a` asserts the audit log; missing log is a hard test failure. |

---

## 8. Provenance threading

`CMP-DEPLOY-05` does not directly write to `provenance_records`. It makes the **storage layer** carry `org_id` as a first-class field:

| Field | How DEPLOY-05 carries it |
|---|---|
| `org_id` on every S3 key | Per `CLAR-DEPLOY-02` — `orgs/{org_id}/...`; the IAM session policy enforces. |
| `org_id` column on every multi-tenant table | Per `DOC-DB §3.1` — RLS keyed on `app.org_id`. |
| `kms_cmk_arn` in `orgs` table | Per `CMP-CP-02` tenant onboarding; per-tenant CMK ARN. |
| Audit log entry shape on isolation violations | Per `AC-DEPLOY-05a` — structured fields named in §6.4. |

**Must NOT modify** `findings.{origin, S_version, env_digest, cpg_order_hash}` — `CMP-DEPLOY-05` is a substrate gate, not a finding-emit path.

---

## 9. Acceptance criteria cross-reference

Quoted verbatim from `WBS.md §2.4 CMP-DEPLOY-05`. Paraphrasing an AC is a contract break (RULE-4). All TST-AC-* are `[FORTHCOMING]`.

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-DEPLOY-05a** | > A parameterised negative test that drives a cross-org access attempt at every API surface and every worker callback fails with a 4xx and emits an audit log line. | `TST-AC-DEPLOY-05a` `[FORTHCOMING]` — parameterised negative integration test: for every API route in `DOC-API.md` and every worker callback in `DOC-API.md §HMAC callbacks`, authenticate as org A, attempt access as org B, assert 4xx response, assert audit log entry with the §6.4 structured fields. Each layer (IAM, RLS, KMS) is exercised by a dedicated sub-test (e.g. a worker that mocks holding org-B credentials and tries to decrypt — should fail with `AccessDeniedException`). |
| **AC-DEPLOY-05b** | > Blob-store paths are namespaced by org id; a path traversal in a request parameter cannot resolve to another org's artifact. | `TST-AC-DEPLOY-05b` `[FORTHCOMING]` — integration test: submit a request with a `commit_sha` parameter containing `../../orgs/B/`; assert (1) the API rejects the input via path-component validation, (2) even if the validation is bypassed, the constructed S3 key passes through a `normalize_s3_key` function that asserts the path starts with `orgs/{authenticated_org_id}/`, (3) even if normalize is bypassed, the IAM session policy denies the `s3:GetObject` call. |

Cross-test: `TST-AC-CP-01a` (the application-layer cross-org test) and `TST-AC-DEPLOY-05a` (the substrate-layer test) MUST both pass independently. If only one passes, the defence-in-depth claim is broken.

---

## 10. Open questions

All `CLAR-DEPLOY-*` items bearing on this component are **RESOLVED**. One `CLAR-DB-*` item is **DEFERRED** and affects the RLS implementation.

| CLAR-ID | Question | Status | Impact on CMP-DEPLOY-05 |
|---|---|---|---|
| `CLAR-DEPLOY-16` | Per-tenant isolation backstop | **RESOLVED** | Three-layer scheme (IAM session + RLS + per-tenant CMK). |
| `CLAR-DEPLOY-02` | Object-store choice | **RESOLVED** | S3 with `orgs/{org_id}/...` prefix scheme. |
| `CLAR-DEPLOY-04` | KMS + rotation | **RESOLVED** | Per-tenant CMKs, annual rotation. |
| `CLAR-DEPLOY-01` | Cloud / compute service | **RESOLVED** | ECS Fargate; session policies attached via `sts:AssumeRole`. |
| `CLAR-DB-02` | RLS session-variable scheme (`app.org_id`) | **DEFERRED** | This document follows the `DOC-DB §3.2` proposal (`app.org_id`) pending Security Analyst + SRE/DevOps sign-off. If the ratified scheme differs (e.g. `current_setting('app.tenant')`), §3.2 here must be reconciled. |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | §1 `Owner` stays DEFERRED. |

No new CLAR-DEPLOY-* are filed by this document. `CLAR-DB-02` is already filed in `WBS.md §17` and is the responsibility of `CMP-CP-03` / `CMP-CP-01` to resolve.

---

## 11. References

- `WBS.md §2.4 CMP-DEPLOY-05` — verbatim Purpose + ACs.
- `WBS.md §17 CLAR-DEPLOY-16, CLAR-DEPLOY-02, CLAR-DEPLOY-04` — substrate decisions.
- `WBS.md §17 CLAR-DB-02` (DEFERRED) — RLS session-variable scheme.
- `SDD.md §10 CMP-CP-01 AC-CP-01a` — the application-layer cross-org guarantee; this component is the substrate backstop.
- `SDD.md §10 CMP-CP-03 AC-CP-03a` — tenancy schema migrations (RLS policies live in those migrations).
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — CLAR-DEPLOY-16, CLAR-DEPLOY-02, CLAR-DEPLOY-04.
- `docs/cross-cutting/DOC-DB.md §3` — tenancy + RLS (canonical source for the `app.org_id` scheme and the connection-pool guard).
- `docs/cross-cutting/DOC-RUNBOOK.md §5, §9` — KMS rotation; tenant onboarding/offboarding.
- `docs/components/DOC-CMP-DEPLOY-01.md` (sibling) — provisions the KMS module + RDS instance.
- `docs/components/DOC-CMP-CP-01.md` (depends) — application-layer cross-org guard; this is the layer-zero defence.
- `docs/components/DOC-CMP-CP-02.md` (depends, forthcoming) — invokes the per-tenant CMK provisioning Lambda.
- `docs/components/DOC-CMP-CP-03.md` (depends) — schema migrations include the RLS `CREATE POLICY` statements.
- `.claude/rules/00-global.md` (RULE-9 Security Analyst review for INV-3-touching components).

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-DEPLOY-05`. The three-layer backstop here is the substrate guarantee that no application bug can leak across tenants.*
