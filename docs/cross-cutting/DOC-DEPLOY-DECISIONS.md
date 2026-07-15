# DOC-DEPLOY-DECISIONS — Substrate decision record

**Owner:** CTO Agent
**Status:** ACTIVE (Phase 0a output; covers `CLAR-DEPLOY-01..16`)
**Resolved date (applies to all 16 records in this file unless a per-section override is noted):** 2026-05-23
**Source of truth:** CLAUDE.md §8 (resolved technology stack table). This document expands each row into a formal decision record. The format follows `.claude/commands/clar-resolve.md` with one deviation: the **Resolved date** field is hoisted to this header rather than repeated per section, because all 16 records were resolved in a single CTO session. Any future re-resolution of an individual record must add a per-section **Resolved date** override.

Each `CLAR-DEPLOY-*` resolution below honors `RULE-8` (CTO approves every CLAR-DEPLOY-* before its dependent phase starts). Resolutions are mirrored as one-line summaries in `WBS.md §17`.

---

## CLAR-DEPLOY-01 — Cloud / compute service selection

**Status:** RESOLVED
**Approver:** CTO Agent

**Question:** Cloud / compute service selection (container-orchestration primitive).

**Decision:** AWS ECS Fargate with pinned-image workers. The control plane runs on ECS Fargate behind an Application Load Balancer; analysis workers run as Fargate tasks fanned out by the scheduler (`CMP-ORCH-02`).

**Rationale:** `WBS.md §2.2 WORKING-ASSUMPTION-DEPLOY-01` requires container orchestration with pinned-image workers. `PLAN.md §"Context and the objective"` cites legacy ECS Fargate fanout as the implementation reference. Fargate cleanly satisfies `CMP-SNAP-05`'s requirement that the worker's container image digest *is* the `env_digest` (INV-2). Kubernetes (EKS) would also satisfy this but adds cluster-management cost not justified for v3.2's fanout-style workload.

**Consequences:** `CMP-DEPLOY-01..05` adopt Fargate primitives. `CMP-ORCH-02` scheduler is a Fargate `RunTask` driver. CI/CD workflow (`CMP-DEPLOY-04`) deploys task definitions, not Helm charts.

**Blocks lifted:** `CMP-DEPLOY-01..05` and everything dependent.

---

## CLAR-DEPLOY-02 — Object-store choice

**Status:** RESOLVED
**Approver:** CTO Agent

**Question:** Object-store choice (must support content-addressable, deterministic keys).

**Decision:** Amazon S3 with deterministic key scheme `orgs/{org_id}/codebases/{codebase_id}/snapshots/{commit_sha}/{env_digest}/{artifact_type}`. Per-tenant prefix isolation enforced via IAM session tags (see CLAR-DEPLOY-16).

**Rationale:** `SDD.md CMP-SNAP-01` requires deterministic blob-store keys for the five persisted snapshot artifacts (CPG tarball, reverse-symbol index, dynamic call graph, ΔG, precondition-status). S3 is not natively content-addressable, but the chosen key scheme **delivers content-addressability transitively**: `commit_sha` is Git's content hash over the source tree, and `env_digest` is the container image digest (CMP-SNAP-05 AC-SNAP-05b). Together they uniquely identify the inputs `(source, Env)` that determine every snapshot artifact, so the key path is byte-for-byte reproducible from the inputs — the operational definition of content-addressability the SDD requires (it does not mandate `key = SHA-256(content)`, which would break per-tenant prefix isolation). S3 Object Lock backs the data-retention policy (CLAR-DEPLOY-15).

**Consequences:** `CMP-SNAP-01` artifact persistence layer is an S3 client. `CMP-DEPLOY-05` (tenant isolation) enforces the `orgs/{org_id}/...` prefix in worker IAM policy.

**Blocks lifted:** `CMP-SNAP-01`, `CMP-SNAP-04`, `CMP-FND-03`.

---

## CLAR-DEPLOY-03 — Relational DB engine + version

**Status:** RESOLVED
**Approver:** CTO Agent

**Question:** Relational-DB engine + version.

**Decision:** PostgreSQL 16 on Amazon RDS. Migrations via Alembic (Python). Multi-AZ deployment for production; single-AZ for staging.

**Rationale:** `SDD.md CMP-CP-03` enumerates the tenancy schema (`orgs`, `projects`, `codebases`, `scm_credentials`, `org_policies`, `memberships`, `snapshots`, `proposed_specs`, `spec_versions`, `attestations`, `findings`) which requires relational integrity and row-level security (used to enforce CLAR-DEPLOY-16). PostgreSQL 16 supports RLS, JSONB for SARIF blobs, and partial indices for the `(codebase_id, slice_fingerprint)` index required by `CMP-FND-02`.

**Consequences:** `CMP-CP-03` migration files are Alembic scripts in `db/migrations/`. `CMP-FND-02` schema uses PostgreSQL types (`uuid`, `jsonb`, `bytea` for `cpg_order_hash`).

**Blocks lifted:** `CMP-CP-03`, `CMP-FND-02`.

---

## CLAR-DEPLOY-04 — KMS / envelope encryption vendor

**Status:** RESOLVED
**Approver:** CTO Agent

**Question:** KMS / envelope-encryption vendor + rotation primitive.

**Decision:** AWS KMS with envelope encryption. One customer-managed key per tenant for high-sensitivity material (SCM credentials, signed provenance); annual rotation via KMS automatic rotation. Data keys cached in worker memory for the lifetime of a single scan.

**Rationale:** `SDD.md CMP-CP-02` requires "credential encryption service for at-rest SCM credentials, with rotation". KMS envelope encryption with per-tenant CMKs satisfies the rotation primitive without re-encrypting ciphertext when keys rotate. Aligns with `CMP-FND-03` signed provenance (signing keys also managed via KMS).

**Consequences:** `CMP-CP-02` is a KMS client wrapper. `CMP-FND-03` uses KMS asymmetric keys for signing.

**Blocks lifted:** `CMP-CP-02`, `CMP-FND-03`.

---

## CLAR-DEPLOY-05 — Secrets vendor + injection path

**Status:** RESOLVED
**Approver:** CTO Agent

**Question:** Secrets vendor + injection path into workers.

**Decision:** AWS Secrets Manager. Secrets injected into ECS tasks via the `secrets` block in the task definition (env-var injection at container start). No filesystem secrets; no long-lived IAM keys.

**Rationale:** `SDD.md CMP-SNAP-05` specifies an env-var contract for worker configuration. ECS native `secrets` injection avoids a sidecar or init-container and preserves the env-var contract. Secrets Manager rotation hooks integrate with KMS (CLAR-DEPLOY-04).

**Consequences:** `CMP-DEPLOY-02` worker base image expects all secrets via env vars. `CMP-DEPLOY-04` CI/CD pipeline uses GitHub OIDC to fetch deploy-time secrets; workers never see CI secrets.

**Blocks lifted:** `CMP-DEPLOY-02..04`.

---

## CLAR-DEPLOY-06 — Queue technology

**Status:** RESOLVED
**Approver:** CTO Agent

**Question:** Queue technology + DLQ + visibility-timeout / retry semantics.

**Decision:** Amazon SQS standard queues with per-queue Dead Letter Queue. Visibility timeout: 15 min for snapshot jobs, 60 min for full-scan jobs. Max receive count: 3 before DLQ; DLQ alarm into observability (CLAR-DEPLOY-07).

**Rationale:** `SDD.md CMP-ORCH-01` HMAC-bearer pattern on worker callbacks requires durable enqueue → dequeue → ack with idempotency. SQS provides at-least-once delivery; the worker contract's `report_status` callback handles deduplication via snapshot/scan IDs. FIFO not required because the heuristic scheduler (`CMP-ORCH-02`, Algorithm 4) reorders anyway.

**Consequences:** `CMP-ORCH-01..03` use boto3 SQS client. Scheduler implements priority via separate queues per priority class.

**Blocks lifted:** `CMP-ORCH-01..03`.

---

## CLAR-DEPLOY-07 — Observability stack

**Status:** RESOLVED
**Approver:** CTO Agent

**Question:** Observability stack — logs, metrics, traces, alarms.

**Decision:** OpenTelemetry SDK in workers and control plane. Exporter targets: CloudWatch Logs (structured JSON), CloudWatch Metrics (custom namespace `Scanipy/v3.2`), AWS X-Ray (traces). Alarms in CloudWatch with PagerDuty integration (alarm-stage out of scope for v3.2 baseline; placeholder).

**Rationale:** `SDD.md CMP-DEPLOY-03` requires observability surfaces that cover the worker lifecycle, scan lifecycle, and differential-oracle re-partition events. OTel is the vendor-neutral standard; exporting to AWS-native sinks keeps the control plane on a single billable surface during v3.2.

**Consequences:** `CMP-DEPLOY-03` provisions CloudWatch log groups + X-Ray service map. Every component emits OTel spans with the `S_version`, `env_digest`, and `origin` attributes (per `.claude/rules/02-provenance.md`).

**Blocks lifted:** `CMP-DEPLOY-03`.

---

## CLAR-DEPLOY-08 — Region strategy

**Status:** RESOLVED
**Approver:** CTO Agent

**Question:** Region strategy — per-env, per-tenant, single-region.

**Decision:** Single primary region `us-east-1` for v3.2. Staging environment in `us-east-2`. Per-tenant regional pinning deferred to v3.3 (filed as a forward-looking concern, not OOS).

**Rationale:** No `SDD.md` / `PLAN.md` requirement pins a multi-region deployment for v3.2. Single-region minimizes substrate complexity (S3 replication, RDS cross-region read replicas) and aligns with the Phase 0–7 scope. Per-tenant data-isolation backstop (CLAR-DEPLOY-16) operates within the single region.

**Consequences:** `CMP-DEPLOY-01` Terraform/CDK targets `us-east-1` (prod) and `us-east-2` (staging). Customer ToS notes single-region storage.

**Blocks lifted:** `CMP-DEPLOY-01`.

---

## CLAR-DEPLOY-09 — Network model

**Status:** RESOLVED
**Approver:** CTO Agent

**Question:** Network model — VPC, private subnets, ingress/egress controls.

**Decision:** Single VPC per environment with three subnet tiers — public (ALB, NAT gateway), private application (control-plane ECS), private worker (analysis Fargate tasks). Egress to SCM providers via NAT gateway with VPC endpoint pinning where available (S3, KMS, Secrets Manager, ECR). No direct internet ingress to workers.

**Rationale:** `SDD.md CMP-SNAP-05` requires the worker to operate under a sanctioned argument allowlist and secure subprocess invocation. Private-subnet placement prevents the worker from receiving inbound traffic outside the SQS poll path. VPC endpoints for AWS services reduce egress cost and prevent data exfiltration via DNS rebinding.

**Consequences:** `CMP-DEPLOY-01` infrastructure provisions VPC + subnets + endpoints. `CMP-SCM-02/03` connectors route through NAT gateway.

**Blocks lifted:** `CMP-DEPLOY-01`.

---

## CLAR-DEPLOY-10 — OIDC / SAML IdP integration

**Status:** RESOLVED
**Approver:** CTO Agent

**Question:** OIDC / SAML IdP integration target.

**Decision:** Auth0 as the primary IdP for the customer dashboard (`CMP-CP-04`). Federated SAML / OIDC to customer IdPs (Okta, Azure AD, Google Workspace) via Auth0's connection framework.

**Rationale:** `SDD.md CMP-CP-04` requires "OIDC / SAML federation for the customer dashboard". Auth0 supports both protocols, provides the customer-onboarding self-service surface (per-tenant IdP configuration), and integrates with AWS Cognito if a downstream switch becomes necessary.

**Consequences:** `CMP-CP-04` uses Auth0's JWT validation middleware. RBAC roles (CLAR-DEPLOY-12) are encoded as Auth0 custom claims.

**Blocks lifted:** `CMP-CP-04`.

---

## CLAR-DEPLOY-11 — CI/CD provider

**Status:** RESOLVED
**Approver:** CTO Agent

**Question:** CI/CD provider + OIDC-to-cloud trust pattern.

**Decision:** GitHub Actions with OIDC-to-AWS keyless authentication. No long-lived AWS access keys in CI. Per-environment IAM roles assumed via `aws-actions/configure-aws-credentials@v4` with the `id-token: write` permission and a repository-scoped trust policy.

**Rationale:** `WBS.md §15` and `CMP-CI-01` require four hard CI gates with branch protection. GitHub Actions integrates natively with the project's GitHub-hosted repository. OIDC keyless auth removes the static-key rotation burden and aligns with `RULE-8` audit traceability.

**Consequences:** `CMP-DEPLOY-04` CI/CD workflow uses GHA OIDC. `.github/workflows/deploy.yml` (already present) is the implementation surface.

**Blocks lifted:** `CMP-DEPLOY-04`, `CMP-CI-01`.

---

## CLAR-DEPLOY-12 — RBAC model surface

**Status:** RESOLVED
**Approver:** CTO Agent

**Question:** RBAC model surface — which roles exist, default role on first-admin provisioning.

**Decision:** Three roles per tenant — `org-admin` (full read/write/billing), `org-viewer` (read-only on findings + dashboards), `scanner` (machine identity for SCM webhook + scan submission). First user in a tenant is auto-provisioned as `org-admin`; subsequent users default to `org-viewer` pending admin promotion.

**Rationale:** `SDD.md CMP-CP-01` (multi-tenant scan API guard) and `CMP-CP-04` (auth + dashboard) require explicit role enumeration. Three roles cover the minimum surface area for v3.2; finer-grained permissions (per-project ACLs) are out of scope.

**Consequences:** `CMP-CP-01` policy engine encodes three roles. Auth0 (CLAR-DEPLOY-10) emits role as a custom claim.

**Blocks lifted:** `CMP-CP-01`, `CMP-CP-04`.

---

## CLAR-DEPLOY-13 — Image registry + signing

**Status:** RESOLVED
**Approver:** CTO Agent

**Question:** Image registry + signing/attestation surface.

**Decision:** Amazon ECR for the worker container images. Sigstore Cosign for keyless signing (using GHA OIDC as the signing identity). SLSA-3 provenance attestation generated by GHA and stored as an ECR artifact.

**Rationale:** `SDD.md CMP-SNAP-05 AC-SNAP-05b` requires the worker image digest to be the authoritative `env_digest`, which means the registry must guarantee digest immutability and signing integrity. ECR + Cosign + SLSA attestation is the supply-chain-secure pattern referenced by `CMP-CI-01`.

**Consequences:** `CMP-DEPLOY-02` Dockerfile is pushed to ECR with a Cosign signature. `CMP-DEPLOY-04` verifies the signature before promotion to staging/prod. `env_digest` is the ECR image digest.

**Blocks lifted:** `CMP-DEPLOY-02`, `CMP-DEPLOY-04`.

---

## CLAR-DEPLOY-14 — LLM provider for triage and spec inference

**Status:** RESOLVED
**Approver:** CTO Agent

**Question:** LLM provider for triage and spec inference, plus pricing/quota controls.

**Decision:** Anthropic API, model `claude-sonnet-4-6`. Per-tenant quota controls via the control-plane proxy (`CMP-CP-01` enforces requests-per-minute and tokens-per-day budgets). LLM endpoint accessed only by `CMP-TRI-01..03`; the `LLM_TRIAGE=off` flag in the Attestor (`CMP-CP-05`) hard-disables this path per `INV-3`.

**Rationale:** `SDD.md §1` and `INV-3` confine LLM use to triage ranking and gated spec inference, never on the deterministic-core detection path. `claude-sonnet-4-6` is the current SOTA Anthropic model for structured reasoning over SARIF blobs. Per-tenant quota controls protect against runaway cost and prevent a tenant from exhausting global rate limits.

**Consequences:** `CMP-TRI-01/02/03` use the Anthropic SDK with prompt caching. `CMP-CP-01` middleware tracks per-tenant LLM usage. `OOS-LLM-DET-01` remains the operative scope guard (no LLM in core).

**Blocks lifted:** `CMP-TRI-01..03`.

---

## CLAR-DEPLOY-15 — Data retention policy per artifact class

**Status:** RESOLVED
**Approver:** CTO Agent

**Question:** Data retention policy per artifact class.

**Decision:** Per-artifact retention with S3 Object Lock for compliance-grade classes:
- CPG tarball, reverse-symbol index, dynamic call graph, ΔG: **90 days** (S3 lifecycle expiration; restorable from re-snapshot).
- Witness slice blobs: **1 year**.
- SARIF + signed provenance records: **7 years** (S3 Object Lock — Compliance mode).
- Findings table rows: indefinite (audit trail).

Legal hold: a tenant can request a per-codebase legal hold that pins all artifacts for that codebase past their default retention.

**Rationale:** `SDD.md CMP-FND-03` requires the signed provenance chain to be auditable indefinitely; 7-year retention aligns with SOC2 / ISO 27001 audit windows. The 90-day CPG retention is operational (re-snapshot is cheap if needed); the 1-year witness retention covers the typical customer triage cycle. S3 Object Lock prevents accidental or malicious deletion within the retention window.

**Consequences:** `CMP-DEPLOY-01` provisions S3 lifecycle policies. `CMP-FND-03` writes to the Object-Lock-enabled bucket prefix. `CMP-SNAP-01` does not need Object Lock (re-snapshot is the recovery path).

**Blocks lifted:** `CMP-DEPLOY-01`, `CMP-FND-03`.

---

## CLAR-DEPLOY-16 — Per-tenant data-isolation backstop

**Status:** RESOLVED
**Approver:** CTO Agent

**Question:** Per-tenant data-isolation backstop at the substrate layer.

**Decision:** Three layered backstops:
1. **S3 prefix isolation** — every object key is `orgs/{org_id}/...`; worker IAM session policies are scoped to a single `org_id` per scan.
2. **RDS row-level security** — PostgreSQL RLS on all multi-tenant tables (`findings`, `snapshots`, `codebases`, etc.) keyed on `org_id`; the application sets `app.org_id` per request.
3. **KMS per-tenant data keys** — credential ciphertext and signed-provenance keys are tenant-scoped Customer-Managed Keys (CLAR-DEPLOY-04).

**Rationale:** `SDD.md CMP-DEPLOY-05` requires tenant data isolation. A single-layer guard (IAM only) is insufficient against application bugs; RLS provides defense-in-depth at the DB; per-tenant KMS keys make cross-tenant credential decryption impossible without explicit role assumption.

**Consequences:** `CMP-DEPLOY-05` implements all three layers. `CMP-CP-03` schema includes RLS policies in migrations. `CMP-CP-02` provisions one CMK per `orgs.id` at tenant creation.

**Blocks lifted:** `CMP-DEPLOY-05`.

---

## CLAR-DEPLOY-17 — Branch-protection enforcement (native vs process shim)

**Status:** RESOLVED
**Approver:** CTO Agent

**Question:** Server-side branch protection / required-status-checks are unavailable on this repo (GitHub Free/private — the protection API returns 403). Upgrade the plan (Team/Pro) or make the repo public to enable native protection, or keep the process-level shim doctrine?

**Decision:** Keep the **process-level shims** through v3.2 — `enforce-pr-only-merges.yml` + the RULE-10 `claude-review` fail-closed gate. No paid upgrade, no source disclosure.

**Rationale:** `WBS.md §17 CLAR-DEPLOY-17` and `DOC-CMP-CI-01 §3.3` / `DOC-CMP-DEPLOY-04 §3` assume gate enforcement on `main`; the shims already deliver fail-closed, highly-visible (loud-red-check) enforcement at zero cost, equivalent in effect to the four CI gates (`CMP-CI-01`). Native `required_status_checks` is a one-step wire-up once the org is on Team/Pro for other reasons. Making a proprietary SAST platform's repo public to obtain free protection is a product/security regression, not an enforcement decision.

**Consequences:** `CMP-CI-01` and `CMP-DEPLOY-04` continue to rely on the process shims (`enforce-pr-only-merges.yml`, RULE-10); their docs stay annotated as subject to this CLAR. Wire `claude-review` into `required_status_checks` if/when the org upgrades. Revisit at Stage-A go-live readiness.

**Blocks lifted:** `CMP-CI-01 §3.3` enforcement; `CMP-DEPLOY-04 §3` deploy-time gate verification.

---

## CLAR-DEPLOY-18 — Production IaC placement (DEPLOY-01 sub-task vs DEPLOY-02 first task)

**Status:** RESOLVED
**Approver:** CTO Agent

**Question:** Should the production IaC scaffolding (`infra/` Terraform) be delivered as a sub-task of `CMP-DEPLOY-01` (blocking close of issue #3), or as the first task of `CMP-DEPLOY-02` (which `Depends-On: CMP-DEPLOY-01`)?

**Decision:** Production IaC is the **first task of `CMP-DEPLOY-02`**. `CMP-DEPLOY-01` ACs (`AC-DEPLOY-01a..e`) stay **contract-only** — the `services/substrate/` port-surface + this decision record — so issue #3 closes cleanly.

**Rationale:** `WBS.md §17 CLAR-DEPLOY-18` and `AC-DEPLOY-01a` scope `CMP-DEPLOY-01` to the substrate *contract* (all 16 substrate `CLAR-DEPLOY-*` are RESOLVED); `CMP-DEPLOY-02` is the package that first provisions real AWS resources, so the IaC layer belongs at its head. The CTO had already approved deferring IaC from `AC-DEPLOY-01` (PR #238, 2026-05-25); this ratifies the sequencing. Pure work-ordering — no new money or scope.

**Consequences:** `CMP-DEPLOY-02` begins with the `infra/` Terraform/CDK that provisions ECS/S3/RDS/Secrets-KMS/SQS per the resolved substrate decisions; `CMP-DEPLOY-03..05` and `CMP-SNAP-05` consume it. Issue #3 (`CMP-DEPLOY-01`) closes on contract delivery.

**Blocks lifted:** `CMP-DEPLOY-02` start (IaC head task); unblocks the DEPLOY-02..05 + SNAP-05 provisioning chain.

---

## env_digest history (CLAR-DEPLOY-22 pointer)

`DOC-CMP-DEPLOY-02.md §6.1` step 6 says the image digest is "written to the substrate decision record under 'env_digest history'"; `DOC-CMP-DEPLOY-04.md §6.2` step 7 says this file is **not** mechanically updated for tool-version bumps. `CLAR-DEPLOY-22` (full record: `WBS.md §17`) reconciles the two by making this a **pointer, not a ledger**: the canonical, machine-readable, append-only `env_digest` registry is the committed file `workers/env_digest_history.json` (schema + validation in `workers/build/env_digest_registry.py`; CI-checked by `scripts/check_env_digest_registry.py` and the rollover-ceremony lint `scripts/check_rollover_ceremony.py`). It is written only via a human-reviewed `env_digest rollover` PR auto-opened by the `register-env-digest` job in `.github/workflows/deploy.yml` (never a direct push — `enforce-pr-only-merges.yml` + RULE-10); registration is effective on merge. `CMP-CP-06` consumes the registry's active `scanipy-snapshot` entry via `services/control_plane/fidelity.py::production_env_digest` / `enforce_production_env` (`CLAR-CP-06-02`). This section is not itself updated per rollover — see the registry file's own git history for the authoritative timeline.

---

*End of substrate decision record. Updates to any of these decisions require CTO Agent approval and a new entry here. Referenced by WBS.md §17, CLAUDE.md §8.*
