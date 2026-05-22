# DOC-CMP-DEPLOY-01 — Runtime substrate selection

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `WBS.md §2.4 CMP-DEPLOY-01` (Purpose + AC-DEPLOY-01a..e — DEPLOY components are derived from `WORKING-ASSUMPTION-DEPLOY-01` in `WBS.md §2.2`; they do not appear under that name in `SDD.md`).
- `WBS.md §2.2 WORKING-ASSUMPTION-DEPLOY-01` — the runtime-substrate working assumption itself.
- `WBS.md §17` — all 16 `CLAR-DEPLOY-*` items are **RESOLVED** (2026-05-23).
- `PLAN.md §"Context and the objective"` — the legacy ECS Fargate fanout that v3.2 inherits as a starting shape.
- `PLAN.md §"Central correction"` — `Env` is a versioned parameter; the substrate produced here is what makes `env_digest` exist.
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — the decision record this component delivers; **every CLAR-DEPLOY-* resolution lives there** (16 sections).
- `docs/cross-cutting/DOC-RUNBOOK.md` — operational consumer of the substrate provisioned here.
- `docs/cross-cutting/DOC-DB.md §3` — tenancy / RLS template that DEPLOY-05 layers on top of DEPLOY-01's RDS provision.
- `.claude/rules/00-global.md` (RULE-8: CTO approves every `CLAR-DEPLOY-*`).

This document is the **implementation contract** for `CMP-DEPLOY-01`. It is the **root of the deployment subsystem**: every later DEPLOY-* component consumes the resources provisioned here. There are no production code surfaces — only Infrastructure-as-Code modules. CTO Agent has approved every substrate decision per RULE-8.

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-DEPLOY-01` |
| Subsystem | Deployment (`WBS.md §2.4`) |
| Staging | cross-cutting (must complete before Phase 4 Snapshotter, per `WBS.md §2.2`) |
| Depends-On | none (`WBS.md §20` — Wave-1) |
| Owner | **DEFERRED** via `CLAR-OWNER-01`; operational owner per `.claude/commands/sre-agent.md` is the SRE/DevOps Agent. |
| INV-* touched | **Substrate provisioner for INV-2.** Provisions the ECR registry whose image digests become `env_digest`; the RDS schema whose NOT NULL constraints enforce `(S_version, env_digest)`; the S3 keyspace where `env_digest` appears in the deterministic key path. Does not directly emit findings. |
| Substrate | All 16 `CLAR-DEPLOY-*` RESOLVED. See `DOC-DEPLOY-DECISIONS.md` for the full record. |

---

## 2. Mandate

**Verbatim WBS `Purpose:` (`WBS.md §2.4 CMP-DEPLOY-01`):**

> Resolve every `CLAR-DEPLOY-*` item in §17 and commit one substrate per primitive (compute, queue, blob store, RDBMS, KMS, secrets, IdP, observability stack, region strategy, network model). Output is a written substrate decision record plus the IaC scaffolding needed by every later phase. The decision record is the input to `CMP-DEPLOY-02..04`.

**Operational role.** `CMP-DEPLOY-01` is the **substrate root**. It produces (a) a written decision record at `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — already complete for all 16 `CLAR-DEPLOY-*` items — and (b) the Infrastructure-as-Code (Terraform / CDK) modules in `infra/` that provision the AWS resources every other component depends on. The decision-record half is **done** as of 2026-05-23; this component's remaining deliverable is the IaC half. Every other DEPLOY-* component (Worker image, Observability, CI/CD, Tenant isolation) layers on top of resources provisioned here. The "substrate decision record" is the authoritative answer to "what is `Env`?" — without it, INV-2's `env_digest` would have no anchor.

---

## 3. Interface contract

`CMP-DEPLOY-01` has no HTTP or RPC surface. Its interface is the **Terraform / CDK module surface** consumed by other components, plus the **substrate decision record** consumed by humans.

### 3.1 IaC module layout

```
infra/
├── modules/
│   ├── network/        # VPC, subnets, route tables, NAT, VPC endpoints (CLAR-DEPLOY-09)
│   ├── compute/        # ECS cluster, task execution role, service-discovery namespace (CLAR-DEPLOY-01)
│   ├── storage/        # S3 buckets (snapshot, witness, sarif), Object Lock policies (CLAR-DEPLOY-02, 15)
│   ├── database/       # RDS PostgreSQL 16, subnet group, parameter group (CLAR-DEPLOY-03)
│   ├── secrets/        # AWS Secrets Manager scope, rotation hooks (CLAR-DEPLOY-05)
│   ├── kms/            # KMS keys: platform CMK + per-tenant CMK templating (CLAR-DEPLOY-04)
│   ├── queue/          # SQS standard queues + DLQs per priority class (CLAR-DEPLOY-06)
│   ├── registry/       # ECR repositories: scanipy-snapshot, scanipy-detector (CLAR-DEPLOY-13)
│   ├── observability/  # CloudWatch log groups, X-Ray groups, alarms (CLAR-DEPLOY-07)
│   └── identity/       # Auth0 tenant + AWS IAM identity provider (CLAR-DEPLOY-10)
└── environments/
    ├── prod/           # us-east-1, multi-AZ (CLAR-DEPLOY-08)
    └── staging/        # us-east-2, single-AZ
```

### 3.2 Environment matrix

Per `CLAR-DEPLOY-08` (RESOLVED — `DOC-DEPLOY-DECISIONS.md`):

| Environment | Region | RDS topology | NAT topology | Notes |
|---|---|---|---|---|
| **prod** | `us-east-1` | Multi-AZ | One NAT GW per AZ | Production traffic; S3 Object Lock = Compliance mode on the 7-year prefix. |
| **staging** | `us-east-2` | Single-AZ | Single NAT GW | Pre-release smoke + canary attestation runs. |

Per-tenant regional pinning is **deferred to v3.3** (not OOS, per `DOC-DEPLOY-DECISIONS.md` CLAR-DEPLOY-08).

### 3.3 Module outputs (consumed by sibling DEPLOY-* components)

These outputs are the published contract; sibling components reference them by Terraform remote-state lookup, not by hard-coding ARN strings.

| Output name | Type | Consumed by | Origin |
|---|---|---|---|
| `vpc_id` | `string` | every networked module | `network` |
| `private_app_subnet_ids` | `list(string)` | control-plane ECS service | `network` |
| `private_worker_subnet_ids` | `list(string)` | snapshot/detector Fargate tasks | `network` |
| `public_subnet_ids` | `list(string)` | ALB | `network` |
| `s3_snapshot_bucket_arn` | `string` | `CMP-SNAP-05`, `CMP-DEPLOY-05` IAM policies | `storage` |
| `s3_witness_bucket_arn` | `string` | `CMP-FND-01`, `CMP-FND-03` | `storage` |
| `s3_sarif_bucket_arn` | `string` (Object Lock) | `CMP-FND-01`, `CMP-CP-05` Attestor | `storage` |
| `rds_endpoint` | `string` | `CMP-CP-03` migrations, `CMP-CP-01` API | `database` |
| `rds_security_group_id` | `string` | API + worker SG egress rules | `database` |
| `kms_platform_cmk_alias` | `string` (`alias/scanipy-platform`) | platform-wide envelope encryption | `kms` |
| `kms_per_tenant_cmk_role_arn` | `string` | `CMP-CP-02` tenant CMK provisioning Lambda | `kms` |
| `sqs_snapshot_queue_arn` | `string` | `CMP-SNAP-01` enqueue, `CMP-SNAP-05` dequeue | `queue` |
| `sqs_snapshot_dlq_arn` | `string` | DLQ alarms, on-call procedure (`DOC-RUNBOOK §4.1`) | `queue` |
| `sqs_detector_queue_arn` | `string` | `CMP-ORCH-02` scheduler enqueue | `queue` |
| `sqs_detector_dlq_arn` | `string` | DLQ alarms | `queue` |
| `ecr_snapshot_repo_uri` | `string` | `CMP-DEPLOY-04` push target | `registry` |
| `ecr_detector_repo_uri` | `string` | `CMP-DEPLOY-04` push target | `registry` |
| `secrets_scm_credentials_arn` | `string` | `CMP-CP-02`, `CMP-SCM-*` | `secrets` |
| `secrets_hmac_secret_arn` | `string` | `CMP-SNAP-05`, `CMP-ORCH-03`, `CMP-ORCH-01` | `secrets` |
| `cloudwatch_log_group_workers` | `string` | every worker `LoggerFactory` | `observability` |
| `xray_service_map_namespace` | `string` | OTel SDK exporter init (`CMP-DEPLOY-03`) | `observability` |
| `auth0_tenant_domain` | `string` | `CMP-CP-04` JWT validator | `identity` |
| `aws_oidc_deploy_role_arn` | `string` | `.github/workflows/deploy.yml` (`CMP-DEPLOY-04`) | `identity` |

### 3.4 IaC discipline

- **State storage.** Terraform state in a per-environment S3 backend with DynamoDB locking; state bucket has versioning + Object Lock (governance) enabled.
- **Drift detection.** A nightly `terraform plan` runs in CI; non-empty plan posts to an SRE alarm. Drift is treated as an incident, not a "noisy plan".
- **Module versioning.** Modules in `infra/modules/` are versioned by Git tag. Environments pin module versions; promotion `staging → prod` requires a CI gate.
- **No manual changes.** AWS Console / CLI changes are policy-forbidden and detected by drift; emergency manual changes must be retroactively codified within 24h (procedure: `DOC-RUNBOOK §7.2` rollback).

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| 16 `CLAR-DEPLOY-*` decisions | `DOC-DEPLOY-DECISIONS.md` | All RESOLVED 2026-05-23. CTO Agent has approved per RULE-8. |
| AWS account ID + organization | Bootstrap secret (one-time setup) | Two accounts: `prod` and `staging`. Account separation is part of the isolation story even though tenants share an account within an env. |
| GitHub OIDC issuer fingerprint | AWS IAM trust-policy reference | Encodes `repo:scanipy/scanipy-v3.2:*` as the allowed `sub` (`CLAR-DEPLOY-11`). |
| Domain names | DNS provider (Route 53 zone) | `api.scanipy.io`, `app.scanipy.io`, `auth.scanipy.io`. |

### 4.2 Outputs

| Output | Where | Contract |
|---|---|---|
| `DOC-DEPLOY-DECISIONS.md` | `docs/cross-cutting/` | **DELIVERED** (Phase 0a output). 16 RESOLVED CLAR-DEPLOY-* with rationale + consequences + blocks-lifted. |
| `infra/modules/*` | git | Terraform/CDK modules per §3.1. Each module has its own README and a `terraform validate`-passing test fixture. |
| `infra/environments/{prod,staging}` | git | Environment-specific composition of the modules. |
| Provisioned AWS resources | AWS account `prod` (us-east-1) and `staging` (us-east-2) | Per `DOC-DEPLOY-DECISIONS.md` decisions. |

---

## 5. Invariants touched

| Invariant | How `CMP-DEPLOY-01` supports it | Test |
|---|---|---|
| **INV-2 (substrate provisioner)** | (a) ECR repositories (`registry` module) make container image digests addressable; those digests become `env_digest` in `CMP-SNAP-05`. (b) RDS PostgreSQL 16 (`database` module) supports the NOT NULL constraints on `findings.S_version` and `findings.env_digest` defined in `CMP-FND-02` / `DOC-DB §4.12`. (c) The S3 key path `orgs/{org_id}/codebases/.../{commit_sha}/{env_digest}/{artifact}` (`storage` module + `CLAR-DEPLOY-02`) carries `env_digest` in the path itself. | `TST-AC-DEPLOY-01b` `[FORTHCOMING]` (deterministic S3 key shape); downstream `TST-INV-2-SNAP-01`, `TST-INV-2-FND-02` (the values flow through). |
| **INV-1 supporting** | The platform's two-account split (prod vs staging) plus the SQS DLQ topology guarantees that `oracle-passthrough` async-oracle re-partition events (`CMP-SNAP-04`) have a durable queue path to fire on. | `TST-AC-DEPLOY-01c` `[FORTHCOMING]` (DLQ + at-least-once). |
| **Tenant isolation enablement** | Provisions the S3 bucket structure, RDS database, and KMS key-policy templates that `CMP-DEPLOY-05` uses to enforce the three-layer isolation backstop (CLAR-DEPLOY-16). | `TST-AC-DEPLOY-05a/b` via `CMP-DEPLOY-05` (downstream). |

---

## 6. Algorithm / data flow

### 6.1 Substrate-bring-up flow (one-time per environment)

```
1. Bootstrap   (manual, recorded in DOC-RUNBOOK)
   - Create AWS account; enable AWS Organizations.
   - Create Terraform state S3 bucket + DynamoDB lock table.
   - Configure GitHub OIDC IdP in AWS IAM (CLAR-DEPLOY-11).

2. Network     (infra/modules/network)
   - VPC + 3 subnet tiers across 2 AZs (public, private-app, private-worker)
     per CLAR-DEPLOY-09.
   - VPC endpoints: s3, kms, secretsmanager, ecr.api, ecr.dkr, sqs, logs.
   - NAT gateways for SCM egress.

3. Storage + DB (infra/modules/{storage,database,kms,secrets})
   - Three S3 buckets: snapshot (90d lifecycle), witness (1y), sarif (7y Object
     Lock Compliance).  Per CLAR-DEPLOY-15.
   - RDS PostgreSQL 16 (multi-AZ in prod, single-AZ in staging).
   - KMS platform CMK + the IAM role used by CMP-CP-02 to provision per-tenant
     CMKs at tenant creation (CLAR-DEPLOY-04, CLAR-DEPLOY-16).
   - Secrets Manager scope; the secret-creation IAM role used by CMP-CP-02.

4. Compute     (infra/modules/compute, registry, queue)
   - ECR repositories (one per worker class).
   - SQS standard queues + per-queue DLQ (max-receive 3) per CLAR-DEPLOY-06.
   - ECS Fargate cluster + task execution role.
   - Application Load Balancer in public subnet, targeting control-plane ECS
     service in private-app subnet.

5. Identity + observability (infra/modules/{identity, observability})
   - Auth0 tenant (provisioned via Auth0 Terraform provider) per CLAR-DEPLOY-10.
   - CloudWatch log groups, X-Ray groups, OTel collector ECS service (one task
     per env).  Alarms per CMP-DEPLOY-03.

6. CI/CD trust
   - aws_iam_role for GitHub OIDC, trust-policy scoped to repo + main branch +
     tag refs only.
   - Output role ARN consumed by .github/workflows/deploy.yml.
```

### 6.2 Promotion flow (staging → prod)

```
1. Merge to main triggers ci.yml (Gates 1..4).
2. Tag v[0-9]+.[0-9]+.[0-9]+ triggers deploy.yml.
3. deploy.yml:
   a. pre-deploy-checks job verifies Gates 1..3 are green on the tagged SHA.
   b. build-images job builds + signs (CMP-DEPLOY-02 + CMP-DEPLOY-04).
   c. deploy-ecs job updates the prod ECS task definitions.
4. terraform apply for infra changes is a separate manual workflow gated on
   CTO approval (RULE-8 for any CLAR-DEPLOY-* re-resolution; SRE approval for
   non-substrate infra patches).
```

---

## 7. Failure modes and error contracts

| Failure | Detection | Response |
|---|---|---|
| Terraform drift detected by nightly plan | CI alarm | SRE acks within 4h; restores by re-apply unless drift was an intentional emergency change still being codified. |
| AWS region capacity (Fargate task launch denied) | CloudWatch metric `ServiceQuotaExceeded` | Auto-scale to second AZ; if sustained, file a service-limit increase. Per-tenant SLA breach if persistent. |
| KMS key creation latency (per-tenant CMK takes 30+ s on first call) | `CMP-CP-02` tenant-onboarding integration | Tenant onboarding async; presented to admin as "provisioning" state for <60s. Procedure in `DOC-RUNBOOK §9.1`. |
| RDS multi-AZ failover (planned) | RDS event | Application reconnects via the RDS endpoint DNS; ≤60s downtime budget per `DOC-RUNBOOK §4`. |
| Terraform state bucket compromise | CloudTrail `s3:DeleteObject` on state bucket | Treated as a security incident; Object Lock prevents deletion but alarm-grade. |
| VPC endpoint outage | CloudWatch endpoint health metric | Workers fall back to NAT-gateway egress for the affected service; cost-only impact, no correctness impact. |
| ECR image push failure during deploy | GHA workflow step | `.github/workflows/deploy.yml` exits non-zero; tag is not promoted; the operator retries after fixing root cause. |

---

## 8. Provenance threading

`CMP-DEPLOY-01` does not write to `provenance_records` directly. It establishes the **physical anchors** that other components thread:

| Field | How DEPLOY-01 anchors it |
|---|---|
| `env_digest` | ECR registry provisioned here; image digests produced by `CMP-DEPLOY-02` are stored in this registry; `CMP-SNAP-05` reads the running task's image digest from ECS task metadata and writes it through. |
| `S_version` | RDS schema (provisioned here) backs `spec_versions` table (`DOC-DB §4.9`); `CMP-ORCH-01` reads from there. |
| Audit-chain immutability | S3 Object Lock on the sarif/provenance bucket (Compliance mode, 7 years) prevents tampering with the signed chain (`CMP-FND-03`). |

OTel spans emitted by IaC operations themselves (e.g. Terraform `apply` runs) are out of scope for v3.2 — the provenance threading rules in `.claude/rules/02-provenance.md` apply to finding-emitting code paths, not infrastructure operations.

---

## 9. Acceptance criteria cross-reference

Quoted verbatim from `WBS.md §2.4 CMP-DEPLOY-01`. Paraphrasing an AC is a contract break (RULE-4). All TST-AC-* are `[FORTHCOMING]`.

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-DEPLOY-01a** | > Every `CLAR-DEPLOY-*` in §17 has a recorded decision with a one-paragraph rationale referenced back to `PLAN.md` / `SDD.md` constraints. | `TST-AC-DEPLOY-01a` `[FORTHCOMING]` — integration check: `DOC-DEPLOY-DECISIONS.md` contains a `## CLAR-DEPLOY-*` section for every open item in `WBS.md §17` and each section has both **Rationale** and **Consequences** subsections referencing `PLAN.md` / `SDD.md`. **Status: passes today** (all 16 RESOLVED). |
| **AC-DEPLOY-01b** | > The chosen object-store primitive supports content-addressable, deterministic keys for the artifacts named in `SDD.md` CMP-SNAP-01 (`AC-SNAP-01a`). | `TST-AC-DEPLOY-01b` `[FORTHCOMING]` — write a snapshot and assert the key path equals `orgs/{org_id}/codebases/{codebase_id}/snapshots/{commit_sha}/{env_digest}/{artifact}` for every one of the five artifacts in `CMP-SNAP-01`. |
| **AC-DEPLOY-01c** | > The chosen queue primitive supports per-queue dead-letter routing and at-least-once delivery, with idempotent worker contracts. | `TST-AC-DEPLOY-01c` `[FORTHCOMING]` — integration test: enqueue a poison message that always fails; assert it lands in the DLQ after max-receive 3 (`CLAR-DEPLOY-06`); assert the worker handler is idempotent on redelivery via `snapshot_id` dedup key. |
| **AC-DEPLOY-01d** | > The chosen relational primitive supports forward + rollback migrations on a fresh database (cf. `AC-CP-03a`). | `TST-AC-DEPLOY-01d` `[FORTHCOMING]` — integration test: bring up a fresh RDS instance; `alembic upgrade head`; `alembic downgrade base`; assert both succeed with no manual repair. Cross-test with `TST-AC-CP-03a`. |
| **AC-DEPLOY-01e** | > The chosen KMS-equivalent supports envelope encryption and key rotation (cf. `AC-CP-02a`). | `TST-AC-DEPLOY-01e` `[FORTHCOMING]` — integration test: encrypt a payload with a CMK; trigger KMS auto-rotation; decrypt with the new key version; assert ciphertext written under v1 still decrypts (KMS preserves prior key versions). Cross-test with `TST-AC-CP-02a`. |

Load-bearing observation: **AC-SNAP-05b** (the image digest is the authoritative `env_digest`) depends on the ECR repository provisioned here. If `CMP-DEPLOY-01` regresses on the ECR or KMS provision, INV-2 cannot be discharged downstream.

---

## 10. Open questions

All 16 `CLAR-DEPLOY-*` items in `WBS.md §17` are **RESOLVED** as of 2026-05-23. The full decision record is in `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`.

| CLAR-ID | Question | Status | Impact on CMP-DEPLOY-01 |
|---|---|---|---|
| `CLAR-DEPLOY-01` | Cloud / compute service | **RESOLVED** | AWS ECS Fargate. |
| `CLAR-DEPLOY-02` | Object-store choice | **RESOLVED** | Amazon S3 with deterministic key scheme. |
| `CLAR-DEPLOY-03` | RDS engine + version | **RESOLVED** | PostgreSQL 16 on Amazon RDS (Alembic). |
| `CLAR-DEPLOY-04` | KMS vendor + rotation | **RESOLVED** | AWS KMS, per-tenant CMKs, annual rotation. |
| `CLAR-DEPLOY-05` | Secrets vendor | **RESOLVED** | AWS Secrets Manager → ECS env-var injection. |
| `CLAR-DEPLOY-06` | Queue tech + DLQ | **RESOLVED** | SQS standard + per-queue DLQ, max-receive 3. |
| `CLAR-DEPLOY-07` | Observability stack | **RESOLVED** | OTel → CloudWatch Logs + X-Ray. |
| `CLAR-DEPLOY-08` | Region strategy | **RESOLVED** | prod=us-east-1, staging=us-east-2. |
| `CLAR-DEPLOY-09` | Network model | **RESOLVED** | Single VPC per env, three subnet tiers, VPC endpoints. |
| `CLAR-DEPLOY-10` | IdP integration | **RESOLVED** | Auth0 (primary); federated to customer IdPs. |
| `CLAR-DEPLOY-11` | CI/CD provider | **RESOLVED** | GitHub Actions, OIDC-to-AWS keyless. |
| `CLAR-DEPLOY-12` | RBAC model | **RESOLVED** | `org-admin`, `org-viewer`, `scanner`. |
| `CLAR-DEPLOY-13` | Image registry + signing | **RESOLVED** | ECR + Sigstore Cosign keyless + SLSA-3. |
| `CLAR-DEPLOY-14` | LLM provider | **RESOLVED** | Anthropic API `claude-sonnet-4-6`. |
| `CLAR-DEPLOY-15` | Data retention | **RESOLVED** | CPG 90d / witness 1y / SARIF+provenance 7y. |
| `CLAR-DEPLOY-16` | Tenant-isolation backstop | **RESOLVED** | S3 prefix + RDS RLS + per-tenant CMK. |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | §1 `Owner` stays DEFERRED. |

No new CLAR-DEPLOY-* are filed by this document.

---

## 11. References

- `WBS.md §2.4 CMP-DEPLOY-01` — verbatim Purpose + ACs.
- `WBS.md §2.2 WORKING-ASSUMPTION-DEPLOY-01` — the substrate working assumption this component discharges.
- `WBS.md §17` — `CLAR-DEPLOY-01..16` (all RESOLVED 2026-05-23).
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — full decision record (16 sections, this is `CMP-DEPLOY-01`'s primary deliverable).
- `docs/cross-cutting/DOC-RUNBOOK.md §2..§10` — operational consumer of the substrate.
- `docs/cross-cutting/DOC-DB.md §3` — tenancy / RLS template (consumed by `CMP-DEPLOY-05`).
- `docs/cross-cutting/DOC-INV.md §4` — INV-2 owner exposition (`CMP-DEPLOY-01` is the substrate enabler).
- `docs/components/DOC-CMP-DEPLOY-02.md` (sibling) — worker base image (built on top of this ECR + IAM substrate).
- `docs/components/DOC-CMP-DEPLOY-03.md` (sibling) — observability surfaces (extends this module's `observability` outputs).
- `docs/components/DOC-CMP-DEPLOY-04.md` (sibling) — CI/CD pipeline (consumes `aws_oidc_deploy_role_arn`).
- `docs/components/DOC-CMP-DEPLOY-05.md` (sibling) — tenant isolation (layered on top of `kms` + `database` + `storage` modules).
- `.claude/rules/00-global.md` (RULE-8: CTO approves every `CLAR-DEPLOY-*`).
- `.claude/commands/sre-agent.md` — operational owner briefing.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-DEPLOY-01`. The decision-record half is **delivered** (Phase 0a); the remaining work is the IaC scaffolding in `infra/`.*
