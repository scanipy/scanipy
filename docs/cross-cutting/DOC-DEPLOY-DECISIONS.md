# DOC-DEPLOY-DECISIONS — Substrate decision record

> **⚠️ SUPERSEDED (2026-08-26) for all AWS substrate choices.** The owner has redirected the
> platform to a **Docker-deployed, self-hosted, open-source** substrate. The AWS-specific
> resolutions in this file (`CLAR-DEPLOY-01/-02/-04/-05/-06/-07/-09/-11/-13/-16`) are reversed by
> **`CLAR-DEPLOY-25`** — see `docs/DECISION-DEPLOY-02-docker-oss-pivot-2026-08-26.md` for the current
> substrate remapping (Docker Compose · local/MinIO · Postgres service · local key provider ·
> env/.env · local queue · OTel→stdout/OTLP · GHCR + Cosign · optional auth · single-tenant).
> The records below are retained for history; do not treat their AWS choices as current.

**Owner:** CTO Agent
**Status:** ACTIVE (Phase 0a output; covers `CLAR-DEPLOY-01..22`; 17..18 added 2026-06-03, 19..22 added 2026-07-14)
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

## CLAR-DEPLOY-19 — HTTP stack pin + CP-01/ORCH-01 request-lifecycle adapter (C-1/C-2 discharge)

**Status:** RESOLVED
**Approver:** CTO Agent
**Resolved date:** 2026-07-14 (per-section override; see header note)

**Question:** Pin fastapi (+ uvicorn/starlette/pydantic) and define the CP-01 request-lifecycle adapter (module path, MVP-1 endpoints, structural discharge of security co-sign conditions C-1 exact-verified-bytes parsing and C-2 replay idempotency, and what stays out of scope).

**Decision:** Pin the HTTP stack exactly in a new pyproject optional-dependencies group `http`: fastapi==0.138.2, starlette==1.3.1, pydantic==2.13.4, uvicorn==0.51.0, with httpx2==2.6.0 added to `dev` (test-client only) — the full set was verified co-installable and the C-1 raw-bytes HMAC pattern smoke-tested green against PyPI on 2026-07-14 (pydantic v2 is unconstrained: no production pydantic usage exists in-tree). The adapter lands in two component-owned packages: `services/control_plane/http/adapter.py` (CP-01: JWTVerifierPort fail-closed seam, trace-id, DOC-API §6 envelope mapping, `bound_request` implementing db/session.py's canonical authorize-then-bind caller shape) and `services/scan/http/{app,serde}.py` (ORCH-01: `create_app` factory exposing MVP-1 routes GET /healthz, POST /api/v1/scans, GET /api/v1/scans/{scan_id}, GET /api/v1/scans/{scan_id}/findings, POST /api/v1/jobs/{job_id}/status). C-1 is discharged structurally: the callback route declares no framework body parameter, performs exactly one `await request.body()`, HMAC-verifies those bytes via the existing `verify_worker_callback_hmac`, and derives the handler body as `parse_job_status_report(body_bytes)` on the same local variable. C-2 is discharged via a new `JobStateStore` port + `InMemoryJobStateStore` in services/scan/api.py implementing DOC-API §4.5's normative state machine (second `done` for the same job_id → 204 no-op; conflicting transition → 409, new reserved code `conflicting_status_transition`); the durable Postgres compare-and-set implementation is deferred to the jobs-table follow-up and is REQUIRED before the API service exceeds one replica. Out of scope: real Auth0 JWKS verification (typed port only), enforce_quota (CLAR-SLA-02 DEFERRED), CP-04 SSO/dashboard, real-SQS policy_overrides serialisation, and 404 unknown-job (needs the jobs table).

**Rationale:** Versions: verified live against PyPI 2026-07-14 — fastapi 0.138.2 (2026-06-29, third patch of the 0.138 line; base deps only starlette>=0.46/pydantic>=2.9/typing-extensions) is preferred over 0.139.0 (2026-07-01, 13 days old, adds annotated-doc/typing-inspection transitive surface). starlette 1.3.1 (2026-06-12) is explicitly pinned because fastapi's starlette bound is uncapped, so an unpinned resolve would drift; pydantic 2.13.4 (2026-05-06, settled) satisfies fastapi's >=2.9.0 and conflicts with nothing (grep shows pydantic only in a corpus fixture, never production code, so 'v1 vs v2' is moot); uvicorn 0.51.0 has a minimal dep set (click, h11>=0.16 — post-smuggling-CVE h11). An install + TestClient smoke on this stack ran the exact C-1 pattern green (204 happy path, single-byte tamper rejected), and surfaced one load-bearing repo interaction: starlette 1.x's TestClient emits StarletteDeprecationWarning under plain httpx, which the repo's pytest `filterwarnings=["error"]` turns fatal — installing httpx2==2.6.0 (starlette's `full` extra names it) makes the import warning-clean; this is why httpx2 is a mandatory dev pin, not optional. Architecture: DOC-CMP-CP-01 §3.1 specifies the FastAPI middleware stack and db/session.py's docstring states the canonical caller shape ('authorize FIRST … never opens a transaction for a request it is going to deny'), so the CP-01-owned lifecycle adapter wraps `authorize_request_for_binding` → `acquire_for_request(**request_binding_args(claims))` verbatim, while ORCH-01's routes live under services/scan/ per the §12 layout (the core handlers in services/scan/api.py already self-authorize; the adapter's pre-authorization preserves the no-transaction-when-denied property and the handler check remains as defense-in-depth). C-1: post_job_status's own docstring already binds the adapter ('the HTTP adapter must pin body == parse(body_bytes)'); the structural form — no pydantic body param, one raw read, parse of the identical local — makes an independent re-read unrepresentable, and the tamper test proves the HMAC covers the exact wire bytes. C-2: grounded, not invented — DOC-API §4.5 prescribes 'Idempotent: a second done for the same job_id is a no-op' and status code '409 conflicting status transition'; a JobStateStore port with an in-memory impl mirrors the repo's typed-port/fake DI pattern (SnapshotPort/SpecRegistryPort/HmacKeyIssuer precedent), and because §6.1 reserves no code for §4.5's 409, this resolution adds `conflicting_status_transition` to the editable cross-cutting DOC-API §6.1 (doc-agent append) rather than overloading `idempotency_conflict`. A per-request nonce header was rejected as RULE-4 invented scope: DOC-API §2.3/§4.5 define no nonce, and the co-sign's own wording ('nonce / job-state replay idempotency') admits the job-state alternative that the doc grounds. JWT verification is a port because CPGuard.authorize_request takes claims as input — no JWKS verifier exists in-tree, and inventing the Auth0 integration inline would bypass its own review lane; the fail-closed default matches services/scan/api.py's fail_closed_* seams. /healthz is deployment glue for the ECS/ALB health checks the live cluster already uses (infra/otel-collector pins a container healthCheck), returns a static body, and must bypass auth without touching tenant data.

**Consequences:** `pyproject.toml` gains the `http` extra (four exact pins) plus `httpx2==2.6.0` in `dev`; CI installs `.[dev,http]`. `CMP-CP-01` ships `services/control_plane/http/adapter.py` (JWTVerifierPort fail-closed seam, trace-id, DOC-API §6 envelope mapping, `bound_request` authorize-then-bind shape); `CMP-ORCH-01` ships `services/scan/http/{app,serde}.py` with the five MVP-1 routes. `services/scan/api.py` gains the `JobStateStore` port + `InMemoryJobStateStore` (C-2), and DOC-API §6.1 gains the reserved code `conflicting_status_transition` (409). The durable Postgres job-state store is a hard precondition before the API service runs more than one replica. Tests land in `tests/unit/test_deploy19_http_adapter.py` (TST-CLAR-DEPLOY-19-C1a..c, -C2a..d + stack suite).

**Implementation contract** (verbatim from the decision record; binding for implementing lanes):

````text
DEPENDENCIES — pyproject.toml: add `[project.optional-dependencies] http = ["fastapi==0.138.2", "starlette==1.3.1", "pydantic==2.13.4", "uvicorn==0.51.0"]`; append `"httpx2==2.6.0"` to `dev`. Update `.github/workflows/ci.yml` lint + unit jobs to `pip install -e ".[dev,http]"`. Extend `tests/unit/test_verify_pins.py` with `test_http_stack_pinned_versions` (importlib.metadata versions equal the four pins). No mypy overrides expected (all four ship py.typed). NEW FILES — (1) `services/control_plane/http/__init__.py` re-exporting the adapter surface. (2) `services/control_plane/http/adapter.py` [CMP-CP-01]: `class JWTVerifierPort(Protocol)` with `def verify(self, authorization: str | None, *, trace_id: str) -> JWTClaims | ErrorEnvelope`; `def fail_closed_jwt_verifier() -> JWTVerifierPort` (verify raises NotImplementedError naming the Auth0-JWKS follow-up — mirrors services/scan/api.py fail_closed_* seams); `def request_trace_id(request: Request) -> str` (X-Scanipy-Trace-Id header else uuid4().hex); `def envelope_response(envelope: ErrorEnvelope) -> JSONResponse` (body {error_code, message, trace_id, details}, status=envelope.http_status per DOC-API §6); `@dataclass(frozen=True) class AuthedRequest(claims: JWTClaims, headers: dict[str, str], trace_id: str)`; `def authenticate(request: Request, verifier: JWTVerifierPort) -> AuthedRequest | ErrorEnvelope`; `@contextmanager def bound_request(connection_factory: Callable[[], AbstractContextManager[Connection]] | None, claims: JWTClaims) -> Iterator[Connection | None]` — when factory is None yield None (MVP-1: OrgScopedScanStore is the isolation layer, no RDS exists); else `with connection_factory() as conn, acquire_for_request(conn, **request_binding_args(claims)) as bound: yield bound`. NORMATIVE ORDER per route: authenticate → `authorize_request_for_binding(guard, claims, headers, method=…, resource=…, route=…, trace_id=…)`; non-None envelope short-circuits BEFORE bound_request opens any transaction; core handlers re-authorize internally (defense-in-depth, keep). (3) `services/scan/http/__init__.py`. (4) `services/scan/http/serde.py` [CMP-ORCH-01]: `parse_scan_request(body_bytes: bytes) -> ScanRequest` and `parse_job_status_report(body_bytes: bytes) -> JobStatusReport` (json.loads + explicit field/UUID validation; ANY malformation → InvalidInputError → 400 invalid_input; parse_job_status_report is THE C-1 parse function); `scan_created_json(created: ScanCreated, *, replay: bool) -> dict[str, object]`; `scan_record_json(record: ScanRecord) -> dict[str, object]`. (5) `services/scan/http/app.py`: `def create_app(*, guard: CPGuard, registry: DetectorRegistry, scan_store: ScanStore, queue: StandardQueue, jwt_verifier: JWTVerifierPort, key_issuer: HmacKeyIssuer, job_state_store: JobStateStore, spec_registry: SpecRegistryPort | None = None, snapshot_port: SnapshotPort | None = None, connection_factory: Callable[[], AbstractContextManager[Connection]] | None = None, now: Callable[[], int] = lambda: int(time.time())) -> FastAPI`. Routes: `GET /healthz` → 200 {"status":"ok"}, no auth, no DB, registered outside the auth path; `POST /api/v1/scans` → requires `Idempotency-Key: <uuid>` header (missing/malformed → 400 invalid_input), calls post_scans, returns 200 when `created.job_ids == ()` (idempotency replay — valid because detector_ids is non-empty so a fresh scan always fans ≥1 job) else 201; `GET /api/v1/scans/{scan_id}` → 200 scan_record_json; `GET /api/v1/scans/{scan_id}/findings` → 200 thin record (CLAR-ORCH-07 deviation stands); `POST /api/v1/jobs/{job_id}/status` → 204, HMAC-only (NO CP-01 tenancy guard per DOC-API §2.5), headers Authorization/X-Scanipy-Worker-Id/X-Scanipy-Job-Timestamp. C-1 STRUCTURAL FORM (binding): the callback route function declares NO body parameter (no pydantic model, ever); body_bytes = await request.body() is the ONLY body read; report = parse_job_status_report(body_bytes); post_job_status(job_id, report, body_bytes, hmac_header=…, worker_id_header=…, timestamp_header=…, key_issuer=…, scan_store=…, job_state_store=…, now=…). Exception handlers: ScanApiError → envelope(e.error_code, e.http_status); AuthorizationError → its ErrorEnvelope; RequestValidationError → 400 invalid_input; fallback → 500 internal_error; every envelope carries the request trace_id. EDITS — `services/scan/api.py` [C-2]: `TransitionOutcome = Literal["applied", "duplicate", "conflict"]`; `@runtime_checkable class JobStateStore(Protocol): def transition(self, *, job_id: UUID, status: JobStatus, body_sha256: str) -> TransitionOutcome`; `class JobStatusConflictError(ScanApiError)` (error_code="conflicting_status_transition", http_status=409); `@dataclass class InMemoryJobStateStore` over dict[UUID, tuple[JobStatus, str]] with state machine: no prior → applied; prior == status → duplicate; prior == "running" and status in {"done","failed"} → applied; prior terminal and status != prior → conflict. `post_job_status` gains `job_state_store: JobStateStore | None = None`: transition is invoked ONLY after HMAC verification + INV-2 fence pass; None preserves today's verify-only behavior (nothing durable mutates — C-2 vacuously holds); conflict → raise JobStatusConflictError; duplicate → return (204 no-op); applied → return (done-triggers stay the wave-2 follow-up). `services/control_plane/constants.py`: add ERROR_CONFLICTING_STATUS_TRANSITION = "conflicting_status_transition" with ERROR_HTTP_STATUS entry 409. `docs/cross-cutting/DOC-API.md` §6.1 (doc-agent): append row `conflicting_status_transition | 409 | Worker callback status conflicts with the recorded terminal job state (§4.5)`. TESTS — `tests/unit/test_deploy19_http_adapter.py` (fastapi.testclient; reuse tests/orch01_fakes.py; all fakes injected through create_app kwargs, never the prod path). C-1 as testable assertions: [TST-CLAR-DEPLOY-19-C1a] the JobStateStore spy's body_sha256 equals sha256(exact wire bytes) and the handler-visible report equals parse_job_status_report(those bytes) — i.e. body == parse(body_bytes); [C1b] exactly one raw body read per callback request (ASGI receive-spy or Request.body counter); [C1c] flipping one body byte after signing → 401 invalid_hmac envelope AND JobStateStore.transition never called (no independent re-read can resurrect the request). C-2 as testable assertions: [C2a] byte-identical validly-signed `done` replayed within the 300 s window → 204 both times, exactly ONE applied transition (DOC-API §4.5 no-op); [C2b] valid `done` then valid `failed` for the same job_id → 409 conflicting_status_transition, store still holds `done`; [C2c] forged digest → 401 with store untouched (no durable transition lands without passing the replay-idempotent store — ordering assertion); [C2d] repeated `running` → 204/204, single recorded state. Stack tests: test_healthz_unauthenticated_200_static; test_missing_bearer_401_envelope; test_org_mismatch_403_envelope (AC-CP-01a over HTTP); test_role_denied_403_org_viewer_post_scans; test_post_scans_201_then_replay_200_same_scan_id; test_idempotency_key_header_required_400; test_cross_org_get_scan_404; test_error_envelope_echoes_trace_id_header; test_binding_order_authorize_then_bind_then_commit (fake DB-API Connection records set_config/commit/rollback; a denied request opens NO transaction; clean exit commits, error rolls back). RULE-9 note: this lane touches no INV-3/INV-4 component, but the ORCH-01 co-sign conditions are embedded in the WBS row — request Security Analyst re-sign on the adapter PR anyway.
````

**Rejected alternatives:**

- fastapi==0.139.0 (latest, 2026-07-01): only 13 days settled and adds new base transitive deps (annotated-doc, typing-inspection) — larger supply-chain surface for zero needed features; 0.138.2 has identical starlette/pydantic bounds.
- Leaving starlette floating under fastapi's uncapped `starlette>=0.46.0` bound: resolver drift would silently move the security-relevant HTTP parsing layer between builds; pin 1.3.1 explicitly.
- pydantic v1-compat pin: nothing in production code uses pydantic at all (only a corpus fixture names it), and fastapi>=0.136 requires pydantic>=2.9 — v1 is both unnecessary and incompatible.
- Starlette-only (no FastAPI): DOC-CMP-CP-01 §3.1 and DOC-CMP-ORCH-01 §3.1 both specify FastAPI shapes (Request/call_next, APIRoute); the CLAR itself asks for the fastapi pin.
- pydantic request-body models on routes: forbidden on the callback (framework body parsing is an independent read path — exactly the C-1 hazard) and skipped on /scans so the framework-agnostic core stays the single validation authority (no drift between pydantic model and _validate_scan_request).
- A new X-Scanipy-Nonce header for C-2: RULE-4 invented scope — DOC-API §2.3/§4.5 define no nonce header; §4.5's idempotent-done + 409-conflicting-transition is the doc-grounded replay mechanism, and the co-sign wording ('nonce / job-state replay idempotency') explicitly admits it.
- Wiring real Auth0 JWKS verification now: no verifier exists in-tree (CPGuard takes claims as input); a live JWKS fetch needs Auth0 tenant config and belongs to the CP-04/deploy lane — the fail-closed JWTVerifierPort preserves the §3.1 validate_jwt layer without inventing the integration.
- uvicorn[standard] extra: uvloop/httptools/websockets unneeded at MVP-1; plain uvicorn (click + h11) keeps the hash-pin surface minimal.
- Single package (everything under services/control_plane/http/): ORCH-01 owns its routes per the §12 layout; CP-01 owns only the reusable request-lifecycle adapter — matches component boundaries and review lanes.
- Implementing enforce_quota now: numeric budgets are DEFERRED in CLAR-SLA-02; the quota middleware is purely additive to the stack and lands with that resolution.

**Risks:**

- InMemoryJobStateStore is single-process and non-durable: replay idempotency does not survive an API-service restart or horizontal scaling. The durable Postgres implementation (jobs table, compare-and-set UPDATE ... WHERE status IN (allowed priors) / INSERT ... ON CONFLICT) is REQUIRED before the API ECS service runs more than one task — record this as a hard precondition on the DEPLOY-19 wave-2 scale-out.
- Exact pins go stale: fastapi 0.138.2/starlette 1.3.1 were current-minus-one at resolution time (2026-07-14); revisit at the API container image build (hash-pinned requirements.txt, workers/* pip-compile pattern) and on any security advisory for starlette/h11/uvicorn.
- Sandbox verification ran on Python 3.10; the codebase targets 3.11 and CI is the authoritative run (all five dists declare requires_python <= 3.10, so no floor conflict, but the 3.11 CI leg must confirm).
- The 200-vs-201 replay inference (job_ids == () iff idempotency replay) couples the adapter to a core invariant (detector_ids non-empty => fresh scan fans >= 1 job); TST pins it, but a future core change to lazy fan-out would silently flip status codes — the test is the tripwire.
- starlette 1.x TestClient httpx->httpx2 migration is mid-flight upstream; if a future starlette drops the httpx fallback entirely the pinned httpx2 path is the supported one, but unpinned local envs without httpx2 will fail loudly under filterwarnings=error (documented in the dev extra).
- DOC-API §6.1 gains a new reserved code (conflicting_status_transition) by this resolution; until the doc-agent lands that append, the code exists only in constants.py — merge the doc edit in the same PR to avoid a doc/code drift window.
- GET /scans/{id}/findings still returns the thin ScanRecord (CLAR-ORCH-07 deviation): API consumers expecting DOC-CMP-ORCH-01 §3.1's ScanState/SARIF page must wait for the jobs-table + FND-01 wiring wave; the OpenAPI schema generated by FastAPI will honestly reflect the thin shape.
- The fail-closed JWTVerifierPort means the deployed MVP-1 app cannot authenticate real users until the Auth0 JWKS verifier lands — acceptable now (no API service exists; workers at desiredCount=0) but it gates any customer-facing enablement.

---

## CLAR-DEPLOY-20 — Worker failure-rate alarm denominator + observability metric contract

**Status:** RESOLVED
**Approver:** CTO Agent
**Resolved date:** 2026-07-14 (per-section override; see header note)

**Question:** DOC-CMP-DEPLOY-03 §3.4 lists `snapshot_worker.failure_count` and `snapshot_worker.duration_ms` but not a `snapshot_worker.job_count` (total jobs) or `detector_worker.job_count` metric. The §3.5 failure-rate alarms (>5% / 15min) require a denominator. Decision: add `job_count` (counter, emitted by CMP-SNAP-05 and CMP-ORCH-03 on every job start) to §3.4, or use a different denominator (e.g. `job_count = failure_count + success_count`).

**Decision:** The failure-rate denominator is completions, not starts: total = failure_count + success_count, with new counters `snapshot_worker.success_count` (CMP-SNAP-05, on `report_status(state='ready')`) and `detector_worker.success_count` (CMP-ORCH-03, on successful detector-job completion) added to DOC §3.4; no start-time `job_count` metric is introduced and the name is retired. The rate alarms compute `rate = IF(total > 0, 100 * fail0 / total, 0)` where `fail0 = FILL(failure_sum, 0)` and `total = fail0 + FILL(success_sum, 0)` over 300 s periods, threshold 5, 3-of-3 evaluation periods (= ">5% over 15 min"), `treat_missing_data = notBreaching`; the zero-traffic OK-state is backstopped by two new AWS/SQS `ApproximateAgeOfOldestMessage > 900 s` alarms on the jobs queues, which catch the silent-worker-death mode the IF-guard deliberately ignores. Incident-grade run-scoped metrics (`attestor.core_diff_count`, `eprocess.martingale_test_status`) must be emitted with their healthy value (0 diffs / status 1) on every run plus a daily canary heartbeat, and each gains a companion absence alarm (`SampleCount < 1` per 86400 s, `treat_missing_data = breaching`) enabled at Stage-A go-live, so they are never fail-open indefinitely. The ADOT collector awsemf exporter is pinned to `namespace: Scanipy/v3.2` and `dimension_rollup_option: ZeroAndSingleDimensionRollup`; alarms consume only the zero-dimension rollup series.

**Rationale:** (1) Completion-based denominator: the numerator (`failure_count`, DOC §3.4: "on report_status(state='failed')") is emitted at job END. A start-emitted `job_count` lands in a different 300 s period than the failure of any job longer than 5 minutes (snapshot CPG builds routinely are), so `failure/job_count` in the failure's period evaluates 1/0 → the `IF(total==0)` guard silences it, and short windows can transiently read >100%. `success+failure` puts numerator and denominator in the same period by construction, is the statistically correct completion-failure fraction for the §3.5 ">5% over 15min" contract, and costs one counter instead of one counter plus a second emission site per job. Jobs that die without reporting anything emit neither metric under EITHER option — that mode is covered by the SQS oldest-age and existing DLQ alarms, not by rate math. (2) Zero-dimension rollup: CloudWatch alarm `metric` blocks match exact dimension sets; §3.4 counters carry dimensions (`region`,`env_digest`; `detector_id`,`engine`,`env_digest`), so the alarm lane's `dimensions = {}` queries only resolve if the collector publishes a zero-dim aggregate — pinning awsemf `ZeroAndSingleDimensionRollup` (its documented default, currently unpinned because `AOT_CONFIG_CONTENT` is empty) is the single point of control that makes the two lanes compose. (3) treat_missing_data by class: traffic-gated rates and event counters (hmac_reject, oracle_disagreement, DLQ) stay `notBreaching` because absence is semantically healthy; run-scoped incident metrics get the emit-healthy-value + SampleCount-absence pattern because for them absence is ambiguous (no incident vs. attestor never ran), and DOC §3.5 marks attestor.core_diff and eprocess as incident severity — the daily heartbeat cadence anchors to the existing canary schedule (`canary.yml` cron `30 3 * * *`). Thresholds 5%/15min themselves are inviolable per DOC §"Alarm misfires" note. *[Editorial grounding, per AC-DEPLOY-01a: the "DOC §3.4/§3.5" cited throughout this record is `DOC-CMP-DEPLOY-03` (CMP-DEPLOY-03, alarm contract AC-DEPLOY-03c); the emitting components are CMP-SNAP-05 and CMP-ORCH-03.]*

**Consequences:** `DOC-CMP-DEPLOY-03` §3.4/§3.5 are amended (doc-agent): `snapshot_worker.success_count` + `detector_worker.success_count` added, the start-time `job_count` name retired, `dlq.message_count` re-annotated to the native `AWS/SQS` metric. Emitters `CMP-SNAP-05` and `CMP-ORCH-03` adopt the new `tools/observability/metrics.py` surface; the ADOT collector moves to an explicit pinned config (`infra/otel-collector/config.yaml`: namespace `Scanipy/v3.2`, `ZeroAndSingleDimensionRollup`); `infra/modules/observability/alarms.tf` rewrites both rate alarms (FILL/IF metric math over completions) and adds four alarms — two SQS queue-oldest-age backstops and two incident-metric absence alarms behind `enable_absence_alarms` (flipping it true is a `T-STAGE-A-01` go-live checklist item). `TST-AC-DEPLOY-03c` terraform-plan assertions are extended accordingly.

**Implementation contract** (verbatim from the decision record; binding for implementing lanes):

````text
NAMESPACE (both lanes): `Scanipy/v3.2` — applied by the collector, not by emitters. CROSS-LANE INVARIANT: emitters attach dimensions as OTel DATA-POINT attributes (resource attributes do NOT become CloudWatch dimensions under awsemf); alarms consume ONLY the zero-dimension rollup series produced by awsemf `ZeroAndSingleDimensionRollup`.

== METRIC SET (DOC §3.4 as-emitted; CloudWatch MetricName = OTel instrument name, verbatim incl. dots) ==
1. `snapshot_worker.failure_count` — Counter, unit "1", attrs {`region`, `env_digest`} — CMP-SNAP-05, exactly once per dequeued SQS message that terminates in `report_status(state='failed')` (any DOC-CMP-SNAP-05 §7 terminal failure path).
2. `snapshot_worker.success_count` — NEW — Counter, "1", attrs {`region`, `env_digest`} — CMP-SNAP-05, exactly once per dequeued message whose `report_status(state='ready')` POST returns 2xx.
3. `snapshot_worker.duration_ms` — Histogram, "ms", attrs {`precondition_status`} — CMP-SNAP-05 per job (dequeue→report, monotonic clock).
4. `detector_worker.failure_count` — Counter, "1", attrs {`detector_id`, `engine`, `env_digest`} — CMP-ORCH-03 per failed detector job.
5. `detector_worker.success_count` — NEW — Counter, "1", attrs {`detector_id`, `engine`, `env_digest`} — CMP-ORCH-03 per successful detector job.
6. `detector_worker.duration_ms` — Histogram, "ms", attrs {`detector_id`, `engine`}.
7. `callback.hmac_reject_count` — Counter, "1", attrs {`endpoint`} (unchanged).
8. `attestor.core_diff_count` — Counter, "1", no attrs — SEMANTICS AMENDED: CMP-CP-05 emits on EVERY attestation run with value = number of core-partition byte diffs (add(0) on a clean run, producing a datapoint), not only on diff.
9. `cw_detect.oracle_disagreement_count` — Counter, "1", attrs {`language`} (unchanged).
10. `eprocess.martingale_test_status` — Gauge 0/1, "1", no attrs — CADENCE AMENDED: published on every CI Gate-4 run AND once daily by `canary.yml` (cron `30 3 * * *`), which must also run the attestor so metrics 8 and 10 each get ≥1 datapoint/day.
11. `dlq.message_count` — DELETED as a custom metric; §3.4 row re-annotated to the native `AWS/SQS ApproximateNumberOfMessagesVisible` the alarms already use.
12. `cosign.signature_verify_count` — Counter, "1", attrs {`image_name`, `result`∈{success,fail}} — CMP-DEPLOY-04 launch hook via `aws cloudwatch put-metric-data` (unchanged).

== EMITTER LANE (services/) ==
NEW FILE `tools/observability/metrics.py` (hermetic-import parity with `tools/observability/init.py`: `opentelemetry` imported INSIDE function bodies; module import must succeed with no otel packages installed). Public surface, re-exported lazily from `tools/observability/__init__.py`:
- `def record_job_completion(worker: Literal["snapshot_worker", "detector_worker"], outcome: Literal["success", "failure"], duration_ms: float, *, counter_attributes: Mapping[str, str], duration_attributes: Mapping[str, str]) -> None` — increments Counter `f"{worker}.{outcome}_count"` (unit "1") with `counter_attributes` and records Histogram `f"{worker}.duration_ms"` (unit "ms") with `duration_attributes`. Instruments created once via `opentelemetry.metrics.get_meter("scanipy.observability")` and cached in a module-level dict keyed by instrument name.
- `def record_counter(name: str, value: int = 1, *, attributes: Mapping[str, str] | None = None) -> None` (metrics 7–9) and `def record_gauge(name: str, value: int, *, attributes: Mapping[str, str] | None = None) -> None` (metric 10, sync Gauge).
Call sites: `services/snapshot/worker.py` (CMP-SNAP-05) with `counter_attributes={"region": os.environ.get("AWS_REGION","us-east-1"), "env_digest": <SCANIPY_ENV_DIGEST>}`, `duration_attributes={"precondition_status": <CW-DETECT verdict>}`; `services/scan/worker.py` (CMP-ORCH-03) with `counter_attributes={"detector_id":…, "engine":…, "env_digest":…}`, `duration_attributes={"detector_id":…, "engine":…}`. At most one completion metric per dequeued message (retries count per-attempt, intentionally).

== COLLECTOR (infra/otel-collector/) ==
`task-definition.json` currently runs the built-in `--config=/etc/ecs/ecs-cloudwatch-xray.yaml` with empty `AOT_CONFIG_CONTENT`. Replace with an explicit ADOT config (new file `infra/otel-collector/config.yaml`, injected via `AOT_CONFIG_CONTENT` from SSM) whose awsemf exporter pins exactly: `namespace: "Scanipy/v3.2"` and `dimension_rollup_option: "ZeroAndSingleDimensionRollup"`; no `metric_declarations` (default all-attribute dimensions + rollups). Keep awsxray + logs pipelines.

== ALARM LANE (infra/modules/observability/alarms.tf) ==
(A) Rewrite `aws_cloudwatch_metric_alarm.snapshot_worker_failure_rate` and `.detector_worker_failure_rate`: six metric_query blocks — id `fail` {metric `<worker>.failure_count`, namespace `Scanipy/v3.2`, period 300, stat "Sum", dimensions {}, return_data false}; id `succ` {metric `<worker>.success_count`, same shape}; id `fail0` expression `FILL(fail, 0)`; id `succ0` expression `FILL(succ, 0)`; id `total` expression `fail0 + succ0`; id `rate` expression `IF(total > 0, 100 * fail0 / total, 0)`, return_data true. `comparison_operator = "GreaterThanThreshold"`, `threshold = 5`, `evaluation_periods = 3`, `datapoints_to_alarm = 3`, `treat_missing_data = "notBreaching"`. Alarm names unchanged (`scanipy-${var.env}-snapshot-worker-failure-rate`, `…-detector-worker-failure-rate`).
(B) NEW alarms ×4: `scanipy-${var.env}-snapshot-queue-oldest-age` and `…-detector-queue-oldest-age` — namespace `AWS/SQS`, metric `ApproximateAgeOfOldestMessage`, dimension `QueueName` from NEW variables `var.snapshot_jobs_queue_name` / `var.detector_jobs_queue_name` (live values `scanipy-prod-snapshot-jobs` / `scanipy-prod-detector-jobs`), stat "Maximum", period 300, evaluation_periods 3, threshold 900, GreaterThanThreshold, `treat_missing_data = "notBreaching"`, Severity high. `scanipy-${var.env}-attestor-run-absent` (metric `attestor.core_diff_count`) and `scanipy-${var.env}-eprocess-gate-absent` (metric `eprocess.martingale_test_status`) — namespace `Scanipy/v3.2`, stat "SampleCount", period 86400, evaluation_periods 1, `comparison_operator = "LessThanThreshold"`, threshold 1, `treat_missing_data = "breaching"`, Severity high, guarded by NEW `variable "enable_absence_alarms" { type = bool, default = false }` (`count = var.enable_absence_alarms ? 1 : 0`); flipping it true is a T-STAGE-A-01 go-live checklist item.
(C) Unchanged alarms keep `treat_missing_data = "notBreaching"`: hmac_reject, cw_detect disagreement, DLQ (absence = healthy for event counters), attestor_core_diff and eprocess value alarms (absence handled by the companion absence alarms + always-emit contract).
(D) Interim: the `infra/observability-apply.sh` threshold-0 proxies (lines 97–113) stay live until first `terraform apply`; identical alarm names mean PutMetricAlarm supersedes them (prefer `terraform import` of the two rate alarms first).
== TESTS ==
`TST-AC-DEPLOY-03c` terraform-plan assertion extended: both rate alarms contain metric names `<worker>.failure_count` AND `<worker>.success_count` plus expressions `FILL(fail, 0)` and `IF(total > 0, 100 * fail0 / total, 0)`; the four new alarms exist. Emitter lane: unit tests via `opentelemetry.sdk.metrics.export.InMemoryMetricReader` assert the verbatim instrument names/units/attribute keys above. DOC-CMP-DEPLOY-03 §3.4/§3.5 amended accordingly (doc-agent).
````

**Rejected alternatives:**

- Start-emitted job_count as denominator (what the never-applied alarms.tf assumed): numerator is emitted at job end, so for any job longer than the 300 s period the start and the failure land in different evaluation windows — failure/job_count evaluates 1/0 and the IF(total==0) guard silences exactly the failure it should catch; short windows can transiently read >100%; and it still fails to count hard-crashed jobs, so it buys no coverage over completions.
- Both counters (job_count at start AND success_count at end): creates two subtly different totals (starts vs completions) that never reconcile on dashboards, adds an emission point per job, and the liveness signal it would provide is already available for free from AWS/SQS ApproximateAgeOfOldestMessage without depending on emitter code being alive.
- Native SQS NumberOfMessagesDeleted as denominator: counts message deletions, not job outcomes; misaligned with the failure numerator under redrive/visibility-timeout semantics and couples the alarm contract to queue mechanics.
- treat_missing_data = breaching on the rate alarms after bootstrap: pages on every legitimately quiet 15-minute window (nights, weekends, desiredCount=0) — alert fatigue; the silent-stall mode is covered more precisely by the queue-age alarms.
- Emitting zero-dimension duplicate datapoints from services instead of collector rollup: duplicates code at every emitter and doubles OTLP volume; awsemf ZeroAndSingleDimensionRollup is one pinned line in one config file.
- SEARCH()-based aggregation in alarm metric math to span dimension values: CloudWatch alarms cannot be created on SEARCH expressions — not implementable.
- Anomaly-detection alarms instead of the 5% threshold: DOC-CMP-DEPLOY-03 §3.5 thresholds are 'inviolable' for the AC-DEPLOY-03c alarms per the doc's own risk table — the contract is fixed.

**Risks:**

- Dimension cardinality growth: env_digest changes per image release and detector_id grows with the catalog; ZeroAndSingleDimensionRollup multiplies series (zero + each single dim). Bounded now (~tens of series); revisit with an awsemf metric_declarations allowlist if CloudWatch metric costs rise.
- The rollup pin is load-bearing: if the collector config drifts (e.g. someone sets NoDimensionRollup or reverts to the built-in /etc/ecs config with its own namespace), the alarm-lane dimensions={} queries silently match nothing and both rate alarms go permanently INSUFFICIENT_DATA→OK. Mitigation: TST-AC-DEPLOY-03 config assertion on infra/otel-collector/config.yaml + a post-deploy smoke check that the zero-dim series exists.
- enable_absence_alarms defaults false; if nobody flips it at Stage-A go-live the incident metrics remain fail-open — it must be an explicit T-STAGE-A-01 checklist item, and this decision adds it there.
- Alarm-name collision on first terraform apply: PutMetricAlarm will overwrite the live CLI threshold-0 proxies in-place (same names); during the transition window an apply-then-rollback could leave the more-sensitive proxy replaced by rate math with no emitters yet publishing success_count — sequence the emitter PR (services lane) before or with the terraform apply.
- Attempt-level rate semantics: a single poison message redelivered 3x counts 3 failures, so the rate alarm can breach on one bad job under low traffic (e.g. 3 failures / 10 completions = 30%). This is judged intended operational pressure; the DLQ alarm remains the terminal-state signal.
- FILL() only operates once a metric series has ever existed; between infra apply and first worker completion the rate alarms sit INSUFFICIENT_DATA (notBreaching). Bounded by go-live; the queue-age alarms are live from apply.
- Daily heartbeat coupling: the absence alarms assume canary.yml (cron 30 3 * * *) publishes attestor.core_diff_count and eprocess.martingale_test_status every day; if the canary workflow is paused, both absence alarms fire — which is arguably the desired behavior but should be documented in DOC-RUNBOOK §10.

---

## CLAR-DEPLOY-21 — CI-side AWS emulation (moto adoption; honest emulation partition)

**Status:** RESOLVED
**Approver:** CTO Agent
**Resolved date:** 2026-07-14 (per-section override; see header note)

**Question:** Issue #283 / STATUS-AWS-TEAM row 10: adopt LocalStack or moto (or neither) for CI-side AWS emulation so env-gated acceptance tests (AC-DEPLOY-05a/b, parts of AC-DEPLOY-02a) can run on PRs instead of waiting for live-account windows — with an honest partition of what emulation can and cannot observe.

**Decision:** Adopt moto as an in-process pip dev-dependency (moto[s3,sqs,kms,secretsmanager,sts]>=5.1,<6.0 plus boto3>=1.34) strictly for the honestly-emulatable slice: boto3 adapter API-conformance (S3 key-scheme round-trips and client-side traversal rejection for AC-DEPLOY-05b's key-resolution arm, real SQS RedrivePolicy/DLQ-after-3 semantics upgrading AC-DEPLOY-01c, KMS envelope mechanics, and Secrets-Manager/STS session-policy render mechanics including the 2048-char sts:AssumeRole inline-policy size limit). Reject LocalStack (Community and Pro). All policy-enforcement negatives — AC-DEPLOY-05a's cross-org AccessDenied observations at S3/KMS under a rendered session policy, and bucket-policy prefix denies — are fundamentally unobservable in moto and LocalStack-CE (neither evaluates IAM session policies, S3 bucket policies, or KMS key policies) and stay env-gated behind a new `aws_live` pytest marker skipped unless SCANIPY_AWS_LIVE_TESTS=1, executed only in a manually-dispatched live-account window. AC-DEPLOY-02a/02b are docker-build-gated, not AWS-emulation-addressable: they keep their xfail+skip until a docker buildx CI harness exists, and greening them against moto ECR is explicitly forbidden.

**Rationale:** The only capability that would justify LocalStack's docker weight (container startup, image pulls, port management, version drift on every PR run) is IAM/policy enforcement — and that is a LocalStack Pro feature, absent from Community; moto likewise does not evaluate STS session policies, S3 bucket policies, or KMS key policies (its experimental identity-policy mode covers neither mechanism session_policy.tf relies on: the S3OtherOrgsDeny NotResource statement and KMSOtherCMKsDeny). So on the one dimension that matters for AC-DEPLOY-05a, both tools are equally blind, and a deny-asserting test against them is vacuous by construction — it can never observe the enforced deny. Given that, the cheapest, fastest, most deterministic tool wins for what IS emulatable: moto is in-process (millisecond startup, no docker service in ci.yml), pip-managed like every other dev-dep, and gives real non-vacuous value the InMemoryObjectStore fake cannot: actual boto3/botocore API semantics (S3 key encoding and prefix listing, SQS RedrivePolicy maxReceiveCount=3 redrive-to-DLQ, KMS encrypt/decrypt/generate-data-key, Secrets Manager retrieval, and the hard AWS limit that an sts:AssumeRole inline session Policy is <=2048 chars — checkable offline against the rendered session_policy template). This maximizes real PR-time coverage while the ZERO-fake-green rule is structural: emulated tests may assert construction and mechanics only, never access denial, and every emulated negative must pair with a positive control (same operation succeeds for the owning org) so empty-because-absent can never pass as denied. The live-account arm remains the sole evidence source for enforcement (per DOC-CMP-DEPLOY-05 §3.4's composite contract and the falsifier-gates-need-math-review precedent: a green test on a non-enforcing emulator is exactly the broken-implementation-passes failure mode). Honest scoping of the issue's '(parts of 02a)' hope: none of 02a/02b is AWS-emulation-addressable — the ACs assert tool digests inside a built image and digest change on tool mutation, which need docker buildx in CI, not a fake ECR.

**Consequences:** the `dev` extra gains `boto3` + `moto[s3,sqs,kms,secretsmanager,sts]`; a new `aws_live` pytest marker gates policy-enforcement negatives on `SCANIPY_AWS_LIVE_TESTS=1`; `services/substrate/object_store.py::S3ObjectStore` implements the existing `ObjectStore` Protocol with guard-before-boto3 semantics; `tests/integration/test_substrate_aws_conformance.py` covers the emulatable slice (`AC-DEPLOY-01c` redrive conformance, `AC-DEPLOY-05b` key-resolution arm, KMS/Secrets/STS mechanics incl. the 2048-char session-policy limit); `test_deploy_05b` flips to PR-time green while `test_deploy_05a` and `test_deploy_02a/b` keep their honest xfail/skip; `tests/integration/test_tenant_isolation_live.py` holds the live enforcement twins. `AC-DEPLOY-05a/b` enforcement evidence is always a dated live-window run URL, never the marker's existence. Review rule: any test asserting AWS-policy-evaluated denial must carry `aws_live`; every moto-backed negative pairs with a positive control.

**Implementation contract** (verbatim from the decision record; binding for implementing lanes):

````text
1) pyproject.toml — [project.optional-dependencies].dev: add "boto3>=1.34" and "moto[s3,sqs,kms,secretsmanager,sts]>=5.1,<6.0". [tool.pytest.ini_options].markers: add "aws_live: policy-enforcement negatives against the live AWS account; opt-in via SCANIPY_AWS_LIVE_TESTS=1 (never runs on PR CI)". [[tool.mypy.overrides]]: add module = ["boto3.*", "botocore.*", "moto.*"] with ignore_missing_imports = true (repo precedent: the opentelemetry.* override). 2) New adapter services/substrate/object_store.py::S3ObjectStore implementing the existing ObjectStore Protocol — class S3ObjectStore: __init__(self, bucket: str, client: object | None = None) (boto3 imported lazily inside __init__ on the None path, per the OTel lazy-import precedent so hermetic unit runs need no boto3); put(self, org_id: str, key: str, body: bytes) -> None and get(self, org_id: str, key: str) -> bytes; both MUST call the existing module-level guard logic (same checks as InMemoryObjectStore._guard: PathTraversalError / CrossTenantAccessError) BEFORE any boto3 call. 3) New test module tests/integration/test_substrate_aws_conformance.py, pytestmark = pytest.mark.integration, using moto.mock_aws, module banner stating 'moto does not evaluate IAM/bucket/key policies — no test in this file may assert access denial'; tests: test_s3_object_store_round_trip_at_clar_deploy_02_keys (SnapshotKeyBuilder keys, positive control), test_s3_object_store_rejects_traversal_before_any_s3_call (asserts PathTraversalError AND that no object was created in the moto bucket), test_s3_list_under_org_prefix_returns_only_own_org_keys (seed two orgs; ListObjectsV2 Prefix='orgs/{org}/' returns only own keys — namespacing-by-construction, not a deny claim), test_sqs_redrive_policy_dlq_after_3_receives (real RedrivePolicy JSON maxReceiveCount=3 → message in DLQ; AC-DEPLOY-01c conformance arm), test_session_policy_template_renders_and_fits_sts_2048_char_limit (seed moto Secrets Manager with the session-policy template JSON, substitute TEMPLATE_ORG_ID/TEMPLATE_TENANT_CMK_ARN, assert len(rendered) <= 2048 and sts.assume_role(..., Policy=rendered) succeeds mechanically — render/plumbing only). 4) Existing stubs in tests/integration/test_deploy_specs.py: test_deploy_05b_blob_paths_namespaced_no_cross_org_traversal — REMOVE xfail+skip; body gets real CI-runnable assertions for the key-resolution arm (S3ObjectStore on moto: traversal payloads from the test_substrate.py corpus never resolve outside orgs/{org_id}/ and are rejected pre-call; positive control included); docstring updated: 'enforcement (deny) arm lives in the aws_live twin'. test_deploy_05a_cross_org_access_denied_at_every_surface — KEEPS xfail+skip (blocked on CLAR-DEPLOY-19 HTTP adapter, NOT on emulation); update skip reason to 'app-surface arm blocked on CLAR-DEPLOY-19; enforcement arm lives in tests/integration/test_tenant_isolation_live.py (aws_live)'. tests/unit/test_deploy_specs.py test_deploy_02a/test_deploy_02b — KEEP xfail+skip unchanged; add a comment that these are docker-build-gated and MUST NOT be greened against moto ECR. 5) New live module tests/integration/test_tenant_isolation_live.py with module-level pytestmark = [pytest.mark.integration, pytest.mark.aws_live, pytest.mark.skipif(os.environ.get("SCANIPY_AWS_LIVE_TESTS") != "1", reason="policy-enforcement negatives run only in the live AWS account window (SCANIPY_AWS_LIVE_TESTS=1)")]; tests (boto3 against account 508703380027, creds via the OIDC deploy role): test_deploy_05a_live_session_policy_denies_cross_org_s3 (assume role with rendered org-A session policy from secret scanipy/prod/worker-session-policy-template; s3:GetObject on orgs/B/... → botocore ClientError with Error.Code == 'AccessDenied'; positive control: same session reads orgs/A/...), test_deploy_05a_live_cross_tenant_cmk_decrypt_denied (org-A session, kms:Decrypt against org-B CMK → AccessDenied), test_deploy_05b_live_bucket_policy_prefix_deny (once DEPLOY-01 provisions the data-plane buckets and infra/tenant-isolation-apply.sh applies prefix-deny bucket policies — currently pending per STATUS row 8). Inside the window these tests must FAIL loudly on missing prerequisites (no nested skips beyond the env var), so the window cannot silently green. 6) CI: no ci.yml change required for the moto tests (the existing integration-tests job's -m integration selection picks them up; aws_live tests self-skip via the env var). The live window is a later eng follow-up: a workflow_dispatch workflow exporting SCANIPY_AWS_LIVE_TESTS=1 under the OIDC role and running pytest tests/integration/ -m aws_live; its dated run URL is the AC-DEPLOY-05a/b evidence recorded in STATUS-AWS-TEAM/WBS — the marker's existence is never the evidence. 7) Review rule (record in DOC-DEPLOY-DECISIONS.md § CLAR-DEPLOY-21): any test asserting AccessDenied/4xx produced by AWS policy evaluation must carry aws_live; any moto-backed negative must pair with a positive control.
````

**Rejected alternatives:**

- LocalStack Community (docker service in CI): identical blindness to the decisive capability — IAM/session-policy/bucket-policy/key-policy enforcement is Pro-only — so it adds container startup (~10-30s), image pulls, port management, and version drift to every PR run for zero additional fidelity over in-process moto; the codebase's AWS surface is Python-only, so cross-language emulation buys nothing.
- LocalStack Pro: paid subscription; its IAM enforcement is an approximation of AWS's policy evaluator and could mislead in either direction; the live-account negatives remain mandatory as §21 evidence regardless, making Pro a redundant paid middle layer.
- moto's experimental IAM-enforcement mode (set_initial_no_auth_action_count): evaluates only identity-based policies for a subset of services — it does not evaluate STS session policies or S3 bucket policies, i.e. exactly the two mechanisms session_policy.tf and the prefix-deny rely on; enabling it would manufacture fake-green risk under a veneer of enforcement.
- Neither tool (keep everything env-gated on the live account): forfeits real, honest PR-time coverage that the InMemoryObjectStore fake cannot provide — boto3/botocore API conformance for the S3 key scheme, real SQS RedrivePolicy DLQ semantics for AC-DEPLOY-01c, KMS envelope mechanics, and the offline-checkable 2048-char session-policy size limit — and leaves those regressions to be discovered only in scarce live windows.
- Greening AC-DEPLOY-02a/02b against moto ECR: rejected outright — the ACs assert tool digests inside a built image and digest change on tool mutation; a fake registry's digests are meaningless and the test would be fake-green; 02a/02b need a docker buildx CI harness, which is a separate (non-AWS-emulation) follow-up.

**Risks:**

- Behavioral drift between moto and real AWS (S3 key-encoding edge cases, SQS visibility/redrive timing, KMS metadata): a conformance test can pass on moto and fail live — the live window remains the sole authority for enforcement and the final word on semantics; pin moto within the 5.x major and bump deliberately, re-running the live window after bumps that touch S3/SQS/KMS.
- Silent-skip erosion: aws_live tests are opt-in via SCANIPY_AWS_LIVE_TESTS=1, so nothing forces the window to run; §21/STATUS evidence for AC-DEPLOY-05a/b must cite a dated live-window run URL, never the marker's existence, and inside the window the tests fail loudly (no nested skips) on missing prerequisites.
- Marker discipline is process-enforced, not mechanical: a reviewer could still accept a moto-backed test that infers isolation from an empty result (empty-because-absent passing as denied); the mandatory positive-control rule and the module banner mitigate but do not eliminate this — claude-review should grep new AWS-touching tests for deny assertions without the aws_live marker.
- The rendered session policy may approach the hard 2048-char sts:AssumeRole inline-policy limit (3 buckets × 6 statements with NotResource lists); the CI size assertion converts this into an early red — if it trips, the template must be compacted (e.g. wildcarded resources), which is a RULE-9 Security-Analyst-reviewed change to session_policy.tf.
- The live 05a/05b enforcement tests are additionally blocked on resources that do not exist yet (no S3 data-plane buckets, prefix-deny bucket policies pending per STATUS row 8, and a second tenant CMK for the cross-CMK deny); the first live window must provision/verify these first or the tests will error — honest, but plan the window accordingly.
- Scope-misread risk: adopting emulation must not be read as making AC-DEPLOY-05a CI-runnable — its app-surface 4xx+audit arm is gated on CLAR-DEPLOY-19 (OPEN) and its enforcement arm on the live window; only 05b's key-resolution arm and 01c's conformance arm actually flip to PR-time green under this decision.

---

## CLAR-DEPLOY-22 — Authoritative production env_digest registry (workers/env_digest_history.json)

**Status:** RESOLVED
**Approver:** CTO Agent
**Resolved date:** 2026-07-14 (per-section override; see header note)

> **Numbering correction (2026-07-15, claude-review finding):** an earlier draft of this record referred to itself as "CLAR-DEPLOY-21" throughout its decision, rationale, and implementation-contract text before final numbering was assigned. All such references below have been corrected to CLAR-DEPLOY-22, including the JSON `comment` field that is committed verbatim into `workers/env_digest_history.json` (a CP-06/TST-AC-DEPLOY-02b-audited provenance artifact). The moto-adoption decision (previous section) is the actual CLAR-DEPLOY-21.

**Question:** What is the machine-readable registration surface for the authoritative production env_digest (the CP-06/INV-2 bootstrap), who writes it and when, how do CP-06 fidelity.py and TST-AC-DEPLOY-02b consume it, and what is the disposition of the prose-nominated v0.1.0 and the tainted-provenance v0.1.1 digests?

**Decision:** Create a committed, machine-readable, append-only registry at workers/env_digest_history.json as the single authoritative env_digest surface: entries {image, env_digest, tag, git_sha, signed_at, status ∈ active|superseded|void, note}, with exactly one active entry per worker image. It is written only via a human-reviewed "env_digest rollover" PR — auto-opened by a new register-env-digest job at the end of deploy.yml after deploy-ecs succeeds (never a direct push) — and registration is effective on merge. CP-06 consumes it through new fidelity.py functions production_env_digest()/enforce_production_env() (comparing against the active scanipy-snapshot entry, flipping CLAR-CP-06-02 from record-and-warn to hard-fail the moment an active entry exists), and TST-AC-DEPLOY-02b gains an always-on hermetic half that validates the registry. Both v0.1.0 digests (prose-only nomination, never deployed or stamped) and both v0.1.1 digests (deployed to task-def rev 2 but built from direct-push d948e6b — tainted provenance; desiredCount=0, nothing stamped) are recorded as status=void with reasons; the v0.1.2 digests from the reviewed-history deploy.yml re-run become the first active entries. This fills a specification gap (DOC-CMP-DEPLOY-02 §6.1.6 names a ledger and writer but no format, and conflicts with DOC-CMP-DEPLOY-04 §6.2.7), so it is ratified as CLAR-DEPLOY-22 rather than invented inline.

**Rationale:** (1) The DOC partially specifies the surface but leaves a real gap: DOC-CMP-DEPLOY-02 §6.1 step 6 says verbatim "The image digest is written to the substrate decision record under 'env_digest history' (CMP-DEPLOY-04 commits this back via the env_digest rollover ceremony in AC-DEPLOY-04a)" — naming the location (substrate decision record) and the writer (the DEPLOY-04 pipeline, via the ceremony) — while DOC-CMP-DEPLOY-04 §6.2 step 7 says verbatim "The substrate decision record (DOC-DEPLOY-DECISIONS.md) is **not** mechanically updated for tool-version bumps — it records substrate primitives, not specific tool versions." No 'env_digest history' section exists in DOC-DEPLOY-DECISIONS.md, and markdown prose cannot be consumed fail-closed by CP-06 or by tests. RULE-4 therefore requires a CLAR, not an inline invention; the resolution honours BOTH texts: the canonical record is machine-readable JSON at workers/env_digest_history.json (adjacent to workers/pins.json, the component's existing manifest home per DOC-CMP-DEPLOY-02 §3.2), and DOC-DEPLOY-DECISIONS.md gains a static 'env_digest history' section that points to the JSON — satisfying §6.1.6's location language without mechanically editing the .md per §6.2.7. (2) Writer/when: the digest only exists post-build, and the repo forbids direct pushes to main (enforce-pr-only-merges.yml + RULE-10) — the very violation (direct-push d948e6b) that taints v0.1.1. So deploy.yml's new register-env-digest job opens a PR through the existing rollover ceremony (DOC-CMP-DEPLOY-04 §6.2: "PR title includes the marker env_digest rollover"), exactly the "commits this back via the env_digest rollover ceremony" that DOC-DEPLOY-02 §6.1.6 prescribes. Effective-on-merge is fail-closed: in the deploy→merge window CP-06 still compares against the previous active entry. (3) Consumption: DOC-CMP-CP-06 §7 mandates 'Job fails with ERROR: gate env_digest != production env_digest', and CLAR-CP-06-02 (RESOLVED 2026-06-03) mandates "flip to hard-fail the moment the production digest is pinned" — the registry's active entry IS that pin, so the flip is data-driven with no code change afterwards; fidelity.py's fail_closed_extraction_port already names CLAR-CP-06-02 as its gate. CP-06 compares against the scanipy-snapshot image because DOC-CMP-CP-06 §4.1 requires "the gate harness must re-use the same worker image that production scans use" (the SNAP-05 snapshot worker). (4) AC-DEPLOY-02b's second clause ("that digest is the authoritative env_digest exposed to the snapshot worker") becomes hermetically testable against the registry, unblocking the TST-AC-DEPLOY-02b flip that STATUS-AWS-TEAM row 5 lists as its deliverable. (5) Disposition uses void (never-authoritative) rather than superseded (was-authoritative) to preserve INV-2 historical honesty: v0.1.0 was nominated only in prose (STATUS-AWS-TEAM row 5), and v0.1.1 (verified live: snapshot sha256:65d2edd6a6eb5775ac0f0b107b1de0ba5a9e877b82ffacb30a7a01ebb4d1bd1e, detector sha256:234d467a50af210065ab11c3191c92de8f13f5d76f894f73a8bce5d495d2b78d on task-def rev 2) has tainted build provenance and — with desiredCount=0 and no RDS/S3 data plane — provably stamped nothing.

**Consequences:** new committed registry `workers/env_digest_history.json` + shared validator `workers/build/env_digest_registry.py`; `.github/workflows/deploy.yml` gains the `register-env-digest` job that opens the `env_digest rollover` ceremony PR (never a direct push — `enforce-pr-only-merges.yml` + RULE-10); `services/control_plane/fidelity.py` gains `production_env_digest`/`enforce_production_env` so `CLAR-CP-06-02` flips record-and-warn → hard-fail data-driven on the first `active` entry (gate compares against the `scanipy-snapshot` image per `DOC-CMP-CP-06` §4.1); `TST-AC-DEPLOY-02b` gains an always-on hermetic registry half. Disposition: both v0.1.0 and both v0.1.1 digests are `void`; the v0.1.2 reviewed-history digests become the first `active` entries via a manually-authored bootstrap PR. This file gains a static `## env_digest history` pointer section and `STATUS-AWS-TEAM.md` row 5 is annotated as superseded (both land with the implementing lane's PR, per the contract's lockstep-docs clause).

**Implementation contract** (verbatim from the decision record; binding for implementing lanes):

````text
## 1. New file: `workers/env_digest_history.json` (committed, canonical registry)
```json
{
  "schema_version": 1,
  "comment": "Canonical env_digest registry (CLAR-DEPLOY-22). Append-only: rows are never deleted; a rollover flips the previous active row to superseded and appends the new active row. Exactly one status=active per image. Written only via env_digest-rollover PRs (deploy.yml register-env-digest job). Consumed by CP-06 (CLAR-CP-06-02) and TST-AC-DEPLOY-02b.",
  "entries": [
    {"image": "scanipy-snapshot", "env_digest": "sha256:f3d51cf67de7b3a5f7acd72dd385ce1c6b1e44ecd3677ba0bb6fb58cd270d09f", "tag": "v0.1.0", "git_sha": "<40-hex of the v0.1.0 build commit>", "signed_at": "2026-06-09T00:00:00Z", "status": "void", "note": "Nominated as authoritative in prose only (STATUS-AWS-TEAM.md row 5, 2026-06-09); never machine-registered, never deployed, no artifact stamped."},
    {"image": "scanipy-detector", "env_digest": "sha256:a2a25f8e40dc7ca68ea833a5991191fb290ffe04b62f1d044eeee221d11cde47", "tag": "v0.1.0", "git_sha": "<same>", "signed_at": "2026-06-09T00:00:00Z", "status": "void", "note": "v0.1.0 build; never nominated, never deployed, no artifact stamped."},
    {"image": "scanipy-snapshot", "env_digest": "sha256:65d2edd6a6eb5775ac0f0b107b1de0ba5a9e877b82ffacb30a7a01ebb4d1bd1e", "tag": "v0.1.1", "git_sha": "d948e6b<full 40-hex>", "signed_at": "2026-06-09T00:00:00Z", "status": "void", "note": "Deployed to ECS task-def scanipy-snapshot-worker:2 but built from direct-push commit d948e6b (bypassed PR review, RULE-10 — tainted provenance). desiredCount=0 throughout; no snapshot/finding carries this digest."},
    {"image": "scanipy-detector", "env_digest": "sha256:234d467a50af210065ab11c3191c92de8f13f5d76f894f73a8bce5d495d2b78d", "tag": "v0.1.1", "git_sha": "d948e6b<full 40-hex>", "signed_at": "2026-06-09T00:00:00Z", "status": "void", "note": "Same taint as snapshot v0.1.1 (task-def scanipy-detector-worker:2)."},
    {"image": "scanipy-snapshot", "env_digest": "<v0.1.2 digest from deploy run output>", "tag": "v0.1.2", "git_sha": "<tagged SHA>", "signed_at": "<cosign-sign step time, ISO-8601 UTC>", "status": "active", "note": ""},
    {"image": "scanipy-detector", "env_digest": "<v0.1.2 digest>", "tag": "v0.1.2", "git_sha": "<tagged SHA>", "signed_at": "<ISO-8601 UTC>", "status": "active", "note": ""}
  ]
}
```
Entry fields (all 7 required, no extra keys): `image ∈ {"scanipy-snapshot","scanipy-detector"}`; `env_digest` `^sha256:[0-9a-f]{64}$`; `tag` `^v[0-9]+\.[0-9]+\.[0-9]+$`; `git_sha` `^[0-9a-f]{40}$`; `signed_at` ISO-8601 UTC; `status ∈ {"active","superseded","void"}`; `note` str (must be non-empty when status != "active").

## 2. New module: `workers/build/env_digest_registry.py` (mirrors `verify_pins.py` style; shared validator)
- `class EnvDigestRegistryError(ValueError)`
- `check_registry(doc: dict[str, object]) -> list[str]` — returns violation strings (empty = valid). Enforces: `schema_version == 1`; per-field regexes above; unknown keys rejected; exactly one `status=="active"` per image AND both images have an active entry; `env_digest` unique across all entries; `env_digest != "sha256:" + "0"*64`; non-empty `note` on non-active rows.
- `load_registry(path: Path) -> dict[str, object]` — parse + raise `EnvDigestRegistryError` listing violations (fail-closed; malformed is an error, never a silent None).
- `active_digest(doc: dict[str, object], image: str) -> str` — the unique active entry's `env_digest`; raises if absent.
- `register(path: Path, *, image: str, env_digest: str, tag: str, git_sha: str, signed_at: str) -> None` — flips the image's current active row to `superseded` (note = `"superseded by <tag>"`), appends the new active row, re-validates, writes `json.dumps(..., indent=2)` + trailing newline. Idempotent when the digest is already active. Never deletes rows.
- `main(argv: list[str] | None = None) -> int` — subcommands `check <path>` (exit 1, print each violation) and `register --path --image --digest --tag --git-sha [--signed-at]`.

## 3. `.github/workflows/deploy.yml` — new final job (writer)
```yaml
register-env-digest:
  name: Register env_digest (rollover ceremony PR)
  runs-on: ubuntu-latest
  needs: [build-images, deploy-ecs]
  permissions:
    contents: write
    pull-requests: write
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5           # python-version: "3.11"
    - run: |
        SIGNED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        python -m workers.build.env_digest_registry register --path workers/env_digest_history.json \
          --image scanipy-snapshot --digest "${{ needs.build-images.outputs.snapshot_digest }}" \
          --tag "${{ github.ref_name }}" --git-sha "${{ github.sha }}" --signed-at "$SIGNED_AT"
        python -m workers.build.env_digest_registry register --path workers/env_digest_history.json \
          --image scanipy-detector --digest "${{ needs.build-images.outputs.detector_digest }}" \
          --tag "${{ github.ref_name }}" --git-sha "${{ github.sha }}" --signed-at "$SIGNED_AT"
        git checkout -b "env-digest/${{ github.ref_name }}"
        git add workers/env_digest_history.json && git -c user.name=scanipy-deploy -c user.email=deploy@scanipy commit -m "chore(CMP-DEPLOY-04): env_digest rollover — register ${{ github.ref_name }} digests"
        git push origin "env-digest/${{ github.ref_name }}"
        gh pr create --title "env_digest rollover: register ${{ github.ref_name }} digests" --body-file .github/PULL_REQUEST_TEMPLATE.md
      env: { GH_TOKEN: "${{ github.token }}" }
```
Semantics: the job MUST exit non-zero if PR creation fails (red deploy run = registry drift is loud). It NEVER pushes to main (enforce-pr-only-merges.yml + RULE-10). PR title carries the `env_digest rollover` marker per DOC-CMP-DEPLOY-04 §6.2.1; merge (after the `claude-review` check) makes registration effective. Bootstrap exception: the v0.1.2 registration PR is authored manually by the implementing agent (this job lands in the same change), using the digests from the deploy.yml re-run outputs — same file, same validator, same PR marker.

## 4. `services/control_plane/fidelity.py` — CP-06 consumption (CLAR-CP-06-02 hard-enforce)
```python
ENV_DIGEST_HISTORY_RELPATH = Path("workers") / "env_digest_history.json"  # resolved from repo root by callers
GATE_IMAGE = "scanipy-snapshot"   # DOC-CMP-CP-06 §4.1: the gate re-uses the SNAP-05 (snapshot) worker image

class ProductionEnvMismatch(RuntimeError): ...

def production_env_digest(history_path: Path, image: str = GATE_IMAGE) -> str | None:
    """Active registered digest for `image`. None ONLY when history_path does not exist
    (pre-bootstrap -> CLAR-CP-06-02 record-and-warn). Malformed registry raises
    EnvDigestRegistryError (fail-closed)."""

def enforce_production_env(gate_env_digest: str, history_path: Path, *, image: str = GATE_IMAGE) -> None:
    """CLAR-CP-06-02. Raise ProductionEnvMismatch('gate env_digest != production env_digest: <got> != <want>')
    when an active digest exists and differs; log a single warning when no registry exists (bootstrap)."""
```
Call site: the stage-gate harness (`stage-gate.yml` benchmark step / the pytest wrapper) invokes `enforce_production_env(extraction.env_digest, repo_root / ENV_DIGEST_HISTORY_RELPATH)` before `persist_verdict` on any gate-strength run. Ungated verdicts (`gate_strength=False`, `_UNGATED_ENV_DIGEST`) skip enforcement — they claim no production Env. The record-and-warn → hard-fail flip is purely data-driven: it happens the moment the v0.1.2 registration PR merges (no code change).

## 5. Tests
- `tests/unit/test_deploy_specs.py`: add always-on hermetic `test_deploy_02b_registered_env_digest_history_is_authoritative` (the "authoritative env_digest" half of AC-DEPLOY-02b): `check_registry(json.loads(repo_root/"workers/env_digest_history.json")) == []`; exactly one active per image; active digests well-formed and != all-zero placeholder; every non-active row has a non-empty note; the four v0.1.0/v0.1.1 digests above are present with `status=="void"`. The existing xfail build-half (D1 != D2) stays unchanged.
- New `tests/unit/test_env_digest_registry.py`: `register()` flips active→superseded and appends (never deletes); two-active violation; duplicate-digest violation; missing-note violation; placeholder-digest violation; `main(["check", <bad>]) == 1`; idempotent re-register.
- `services/control_plane/` tests: `enforce_production_env` raises on mismatch, warns+passes on missing file, raises `EnvDigestRegistryError` on malformed file.

## 6. Docs (lockstep, same PR)
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`: add static section `## env_digest history` — one paragraph pointing to `workers/env_digest_history.json` + CLAR-DEPLOY-22 (a pointer, not a mechanically-updated ledger — reconciles DEPLOY-02 §6.1.6 with DEPLOY-04 §6.2.7).
- `docs/status/STATUS-AWS-TEAM.md` row 5: append "**Superseded by CLAR-DEPLOY-22** — registry is `workers/env_digest_history.json`; the v0.1.0 prose nomination is `void`."
- CLAUDE.md needs no edit (derivative; §8 unchanged).
````

**Rejected alternatives:**

- Prose/markdown ledger appended to DOC-DEPLOY-DECISIONS.md 'env_digest history' section as the canonical surface (the literal DEPLOY-02 §6.1.6 reading) — rejected: DOC-CMP-DEPLOY-04 §6.2.7 forbids mechanical updates to that file, markdown prose cannot be consumed fail-closed by fidelity.py or TST-AC-DEPLOY-02b, and prose registration is exactly what already failed (STATUS row 5 nominated v0.1.0 while production silently ran v0.1.1).
- Live AWS state as the registry (read ECS task-def / ECR+Cosign at gate time) — rejected: not committed or reviewable, unavailable to hermetic CI runs, couples every gate run to live-account availability, and the v0.1.1 episode proves live state can embody tainted provenance with zero repo record.
- deploy.yml commits the updated JSON directly to main — rejected: violates the PR-only-merge shim + RULE-10 (fail-closed review); a direct push is precisely the d948e6b taint that voids v0.1.1.
- Extend workers/pins.json with the image digest — rejected: pins.json is a build INPUT gated pre-build by verify_pins.py (AC-DEPLOY-02c); the image digest is a build OUTPUT — conflating them makes the record circular and corrupts the AC-DEPLOY-02c gate semantics.
- SSM Parameter Store / Secrets Manager as the registry — rejected: outside reviewed git history, non-hermetic, adds an AWS dependency to every CI gate run; Secrets Manager is for secrets (CLAR-DEPLOY-05), not public provenance data.
- Record v0.1.0/v0.1.1 as 'superseded' instead of 'void' — rejected: 'superseded' asserts the digest was once authoritative; neither ever was (v0.1.0 prose-only; v0.1.1 tainted and, with desiredCount=0 and no data plane, stamped nothing) — INV-2 historical honesty requires the distinction, so the schema defines both statuses with 'void' permitted only when no persisted artifact carries the digest.
- Per-image nested map instead of a flat entries list — rejected (minor): the flat list with an 'image' field plus the exactly-one-active validation rule is simpler to append to, diff-review, and matches the schema shape already circulated in the task framing.

**Risks:**

- Deploy→merge window: after deploy-ecs succeeds, production runs the new digest while the registry's active entry is still the previous one until the rollover PR merges — CP-06 gate runs inside the window hard-fail on mismatch. Accepted as fail-closed-correct; mitigated by making the auto-opened PR part of the ceremony's definition of done and merging promptly.
- If the register-env-digest job fails to open the PR (gh/network outage) the registry silently drifts from production — mitigated by the job exiting non-zero (red deploy run); consider a follow-up drift check comparing the registry's active digest to the live task-def in a scheduled workflow (read-only).
- Wrong-image comparison: CP-06 must compare against the scanipy-snapshot entry (the SNAP-05 worker image the gate harness runs in); comparing against scanipy-detector would poison the gate — pinned by GATE_IMAGE constant and a unit test.
- The 'void' disposition of v0.1.1 rests on the verified fact that no snapshot/finding carries its digests (desiredCount=0, no RDS/S3 data plane); if any non-prod environment ever stamped one, that entry must be flipped to 'superseded' — encoded as a schema validation rule note, but not machine-checkable today.
- deploy.yml gains contents:write + pull-requests:write on the new job — permission creep; scoped job-level (not workflow-level) and the job only pushes a non-main branch + opens a PR.
- v0.1.0 git_sha and exact signed_at timestamps are not recorded in the repo (STATUS row gives dates only) — the bootstrap PR must recover them from ECR image metadata / Rekor transparency log entries (read-only), or record the date-precision timestamp with a note; do not fabricate seconds-precision values.
- Two registration PRs from re-tagged builds could race (both flip the same active row) — the exactly-one-active validation makes the second PR fail check_registry after rebase, surfacing the conflict loudly rather than merging silently.

---

## CLAR-DEPLOY-23 — Public→private-subnet VPC remediation

**Status:** RESOLVED
**Approver:** CTO Agent
**Resolved date:** 2026-07-16

**Question:** `CLAR-DEPLOY-09` (RESOLVED 2026-05-23) ratified "single VPC per env, three subnet tiers, VPC endpoints" as the `CMP-DEPLOY-01` network model, but live verification on 2026-07-16 (`aws ecs describe-services`) found both `snapshot-worker` and `detector-worker` ECS services running in the DEFAULT VPC's default public subnet (`subnet-01e49400058ac1f09`, us-east-1b, `172.31.80.0/20`) with `assignPublicIp=ENABLED` — a real deviation from the ratified decision. What is the remediation, and is it a Wave-3 prerequisite or a deferred item, given real external-repo scanning (`michealkeines/Vulnerable-API`) is in scope for the first end-to-end scan build?

**Decision:** Scoped as a Wave-3 prerequisite (not deferred) — real external-repo scanning requires both ECS worker services to run without a public IP before a real `git clone` of untrusted third-party source executes on the platform. Remediated live 2026-07-16 (us-east-1, account 508703380027) by reusing the existing default VPC (`vpc-03d1e840c04bc94f1`, `172.31.0.0/16`) rather than provisioning a new VPC (10 of 16 possible `/20` blocks were free; zero new-VPC overhead). Added a private tier (`scanipy-prod-private-a` `172.31.96.0/20` us-east-1a `subnet-0e1da791dfbd033e1`; `scanipy-prod-private-b` `172.31.112.0/20` us-east-1b `subnet-0a14f6cbd6580a347`) and an isolated tier reserved for the RDS track (`scanipy-prod-isolated-a` `172.31.128.0/20` `subnet-0f35c15cda025ebbc`; `scanipy-prod-isolated-b` `172.31.144.0/20` `subnet-0544b5f413d60706c`), each routed via new dedicated route tables (`rtb-03858ed05cfa4a011` private, `rtb-034c37e711aa2d4fd` isolated — isolated carries no default route, local-VPC only). One NAT gateway (`nat-03b0d54e2489406ed`, EIP `eipalloc-0328a0fa236ce42bc`, MVP scope — not per-AZ) sits in the reused default public subnet (`subnet-01594ae384ee13769`, us-east-1a) and is the private tier's only egress path. A free S3 Gateway VPC endpoint (`vpce-0832aad349edec174`) is attached to both new route tables. The pre-existing, previously-untracked `scanipy-workers` security group (`sg-0690e02ba20cf57a8`) was tightened in place (revoke-then-authorize, not replaced) from all-protocol/all-port egress down to tcp/443 (0.0.0.0/0, AWS API calls) + tcp+udp/53 (VPC CIDR only, Route 53 Resolver) — no ingress rules. Both ECS services were moved to the two new private subnets with `assignPublicIp=DISABLED` via `aws ecs update-service --force-new-deployment`.

**Rationale:** (1) The ratified `CLAR-DEPLOY-09` network model (owned by `CMP-DEPLOY-01`, `WBS.md §17`) already specifies private subnets for compute; the public-subnet placement was an undocumented drift from that ratified `CMP-DEPLOY-01` decision, not a considered alternative, so this is remediation-to-spec rather than a new architectural decision. (2) Real external-repo scanning changes the risk calculus from "our own test fixtures" to "arbitrary third-party source cloned and executed inside the worker container" — a public IP on that task is an unnecessary inbound/outbound exposure surface for code the platform does not control, so the fix is sequenced as a hard Wave-3 prerequisite rather than a background cleanup item. (3) Reusing the default VPC instead of provisioning a new one avoids duplicate NAT/route-table/peering cost and complexity with no compensating benefit at this scale (single-account, single-region MVP). (4) The S3 gateway endpoint is free and removes the highest-volume traffic class (ECR image-layer pulls, which are S3-backed) from the NAT gateway's per-GB bill, so it was applied immediately alongside the subnet move rather than deferred with the interface endpoints. (5) Interface VPC endpoints (ECR-api/ECR-dkr/Logs/Secrets-Manager/KMS/SQS) were coded in `infra/modules/network/main.tf` behind `var.enable_interface_endpoints` (default `false`) but not applied live: each costs ~$7.30/mo per AZ and the full enumerated set would add ~$44-88/mo on top of the pre-approved ~$47-50/mo baseline (RDS + this NAT gateway); the NAT gateway + tightened security group already provide full working connectivity to every AWS API the workers call, so this is a documented cost-optimization deferral pending explicit human sign-off, not a functional gap.

**Consequences:** New `infra/modules/network/` (VPC/subnet/route-table/NAT/endpoint Terraform, `var.enable_interface_endpoints` flag) and `infra/network-remediation-apply.sh` (idempotent apply script matching what actually ran live). Both `snapshot-worker` and `detector-worker` ECS services now launch with `assignPublicIp=DISABLED` in the two new private subnets. `docs/status/STATUS-AWS-TEAM.md` row 11 records the live evidence (subnet/route-table/security-group IDs, the tightened SG rule set, and a real-task proof: a one-shot `run-task` of `scanipy-snapshot-worker:3` reached `RUNNING` with ENI `eni-051cd3e6c194c403a`, private IP `172.31.127.90`, `Association.PublicIp = null`, confirming the ECR pull succeeded entirely through the new NAT+S3-endpoint path; the task then self-stopped on the pre-existing `run_execute_loop` `NotImplementedError`, unrelated to networking).

**Rejected alternatives:**

- Provision a brand-new VPC instead of reusing the default VPC — rejected: 10 of 16 `/20` blocks were free in the existing default VPC, so a new VPC adds duplicate NAT/route-table cost and cross-VPC complexity (peering or a second NAT) with no isolation benefit at this account's current scale.
- Apply the full interface-endpoint set (ECR-api/ECR-dkr/Logs/Secrets-Manager/KMS/SQS) alongside the subnet move — rejected for now: ~$44-88/mo additional recurring cost against a pre-approved ~$47-50/mo baseline; the NAT gateway already provides working connectivity to every API the workers call, so this is deferred pending explicit human cost sign-off rather than blocking the Wave-3 prerequisite.
- Per-AZ NAT gateways (one per AZ instead of one shared gateway) — rejected for MVP scope: doubles NAT cost (~$32/mo → ~$64/mo) for redundancy not required at current traffic/availability targets; revisit if a single-NAT outage becomes an operational problem.
- Leave the ECS services in the public subnet and rely solely on security-group tightening — rejected: a tightened SG still leaves a public IP assigned to a task that clones and executes untrusted third-party source, an unnecessary exposure the ratified `CLAR-DEPLOY-09` model was written to avoid; SG tightening was applied in addition to, not instead of, the private-subnet move.

**Risks:**

- The isolated-tier subnets (`scanipy-prod-isolated-a/b`) are provisioned but unused until the RDS track lands — dead infrastructure in the interim; low cost (no NAT/endpoint attached to that tier) and intentional (avoids a second Terraform pass when RDS is provisioned).
- Single NAT gateway is a shared-fate egress path for both worker services — an AZ-level NAT outage stalls all outbound worker traffic (ECR pulls, git clone, SCM API calls) platform-wide; accepted as an MVP-scope tradeoff, flagged for revisit once the platform carries paying-customer traffic.
- The deferred interface endpoints mean ECR-api/ECR-dkr/Secrets-Manager/KMS/SQS/Logs calls still transit the NAT gateway (not just S3), so NAT data-processing charges scale with worker traffic volume more than they would with the full endpoint set — bounded today by MVP-scale traffic, worth re-costing before general availability.
- The pre-existing `scanipy-workers` security group was tightened in place (revoke-then-authorize) rather than replaced with a new group — correct for continuity (avoids an ENI security-group-reattachment window) but means the group's prior, previously-untracked rule history is not preserved anywhere outside this record and `STATUS-AWS-TEAM.md` row 11.

---

## CLAR-DEPLOY-24 — CMP-ORCH-03 shortcut-path signer + DB session wiring

**Status:** RESOLVED
**Approver:** CTO Agent (orchestrating agent, acting CTO role)
**Resolved date:** 2026-07-17

**Question:** Live verification (2026-07-17, `aws ecs describe-task-definition --task-definition scanipy-detector-worker`) found `S3_BUCKET`/`DETECTOR_QUEUE_URL` already provisioned on the detector-worker ECS task definition, but `secrets: null` — no `SCANIPY_DATABASE_URL` and no KMS CMK ARN at all. `aws kms list-aliases` confirms zero `scanipy`-tagged KMS keys exist anywhere in the account: `CLAR-DEPLOY-16`'s "one CMK per tenant" ratification (RESOLVED 2026-05-23) was never actually provisioned (no Terraform module under `infra/`). Separately, `KMSAsymmetricSigner.get_public_key`'s `KeyVersion` parameter models per-signature key-material rotation, but AWS KMS does not support automatic rotation for asymmetric CMKs — there is no native concept to bind `KeyVersion` to. What is the interim `findings_session`/`signer` wiring for `CMP-ORCH-03`'s detector worker (`services/scan/detector_worker.py`) for the first real end-to-end scan, given a real per-tenant CMK does not exist and its rotation-model mismatch needs its own design pass?

**Decision:** `queue`/`object_store` are pure wiring (both env vars already provisioned) — real `SQSQueue`/`S3ObjectStore`, mirroring `services/snapshot/worker.py`'s established `_default_*` pattern. `findings_session` is a real `sqlalchemy.orm.Session` against `SCANIPY_DATABASE_URL`, wrapped in a new `_SqlAlchemyFindingsSession` adapter (`services/scan/detector_worker.py`) that reproduces `db/session.py::acquire_for_request`'s exact tenant-binding GUC contract (`SET LOCAL app.org_id`/`app.user_id`/`app.role` via `set_config`) through `Session.execute` instead of a raw DB-API cursor, since `acquire_for_request` operates on a `Connection` shape incompatible with `FindingsSession`'s `.add()`/`.commit()` ORM contract. `SCANIPY_DATABASE_URL` is wired into a new ECS task-definition revision as a `secrets` entry sourced from the already-live Secrets Manager secret `scanipy/dev/database_url` — infra follow-up alongside this code change, not a further code gap. `signer`: no real CMK exists, so the production default constructs an explicitly-flagged software RSASSA-PSS stand-in — relocated (not duplicated) from `tests/fnd03_fakes.py::SoftwareKMSSigner` into a new production-namespaced module, `services/scan/software_kms_signer.py`. The relocated class gained a hard fail-closed `refuse_if_prod` gate (byte-identical contract to `scripts/seed_test_org.py::refuse_if_prod`, `CLAR-CP-01-02`'s established pattern): construction raises whenever `ENV`/`SCANIPY_ENV` is `"prod"`. The real per-tenant CMK + its rotation-model design resolution stay explicitly open, owned by `CMP-DEPLOY-05`/`CMP-FND-03` — not guessed at here.

**Rationale:** (1) `queue`/`object_store` wiring is a direct application of the already-ratified `CLAR-PROC-01` build-ahead pattern (`WBS.md §17`) and the identical `_default_*` shape already shipped for `CMP-SNAP-05` (`CLAR-ORCH-10`'s same-pass fix) — no new design decision, just closing the last two genuinely-unwired seams. (2) The `findings_session` GUC-binding adapter is a faithful, non-shortcut re-implementation of `db/session.py`'s already-ratified `acquire_for_request` contract (`CMP-CP-01`, `DOC-DB §3.2`), adapted only for the real, unavoidable `Connection`-vs-`Session` shape mismatch between that function's documented intent and `FindingsSession`'s actual Protocol — not a new tenancy-isolation design. Per `CLAR-DB-02`'s existing grants (`db/migrations/versions/20260524_0001_initial_tenancy_tables.py`), this correctly targets `scanipy_app` (already holding `INSERT` on `findings`/`provenance_records`), never `scanipy_system`/BYPASSRLS — no privilege escalation is introduced. (3) The software KMS signer is scoped identically to `CLAR-CP-01-02`'s already-CTO-ratified test-auth bypass: a real cryptographic operation (RSASSA-PSS via `cryptography`, not a no-op), explicitly named as a stand-in, hard-gated against `ENV=prod`, and superseded once the real per-tenant CMK from `CLAR-DEPLOY-16` (`CMP-DEPLOY-05`, `WBS.md §17`) is actually provisioned. Building a real `boto3`-backed KMS binding today would either (a) require guessing at the `KeyVersion`-vs-no-asymmetric-rotation mismatch inline, violating RULE-4 (`CLAUDE.md §11`), or (b) provision a CMK ahead of the per-tenant CMK design CLAR-DEPLOY-16 already committed to, jumping the substrate-decision sequencing that same CLAR established. (4) Relocating (not duplicating) `SoftwareKMSSigner` keeps exactly one implementation shared between the hermetic test suite and the production shortcut-path default, so the two cannot drift.

**Consequences:** `services/scan/software_kms_signer.py` (new) is the canonical `SoftwareKMSSigner` implementation; `tests/fnd03_fakes.py` now imports it rather than defining it inline. `services/scan/detector_worker.py` gains `_default_queue`, `_default_object_store`, `_SqlAlchemyFindingsSession` + `_default_findings_session`, and `_default_signer`; the four superseded `fail_closed_*`/`_FailClosed*` stubs were deleted (no remaining callers). `workers/detector/requirements.txt` gained hash-pinned `cryptography==49.0.0`, `cffi==2.1.0`, `pycparser==3.0` (hashes fetched directly from PyPI's JSON API for the exact versions already verified in the local test environment). `tests/unit/test_detector_worker_specs.py` gained 8 new regression tests. Every provenance record signed by the software stand-in carries `kms_key_arn = "software-dev-signer"` (or a `KMS_KEY_ARN` env var override, for forward-compatibility once a real CMK exists), making software-signed records trivially distinguishable from real-KMS-signed ones on audit. A pending ECS task-definition revision must add the `SCANIPY_DATABASE_URL` secret before the detector worker's real DB path can run live; until that lands, the fail-closed `InvariantViolation` on a missing env var is the only thing standing between the container and a crash-loop, which is the intended fail-closed behavior, not a workaround.

**Rejected alternatives:**

- Build a real `boto3`-backed `KMSAsymmetricSigner` now against a freshly-provisioned ad hoc CMK — rejected: would jump `CLAR-DEPLOY-16`'s "one CMK per tenant" substrate-decision sequencing (no Terraform module exists yet) and would still need to guess at the `KeyVersion`-vs-no-asymmetric-rotation mismatch inline, which is exactly the kind of unspecified-behavior guess RULE-4 exists to prevent.
- Route `findings_session` through `db/session.py::acquire_for_request` directly (unmodified) — rejected: that function's `Connection` Protocol (raw DB-API cursor) is structurally incompatible with `FindingsSession`'s `.add()`/`.commit()` ORM contract that `run_detector_job` already calls against a real SQLAlchemy-mapped `Finding` row; forcing the mismatch would mean hand-rolling column-by-column INSERT SQL instead of reusing the already-correct ORM mapping.
- Grant the detector worker's DB connection role `scanipy_system`/BYPASSRLS instead of relying on `scanipy_app`'s existing RLS-scoped grants — rejected: `scanipy_system` is reserved for genuinely server-internal jobs outside the tenant-isolation boundary (`CLAR-DB-02`); the detector worker writes tenant-scoped `findings`/`provenance_records` rows exactly like a request-path actor and should stay subject to RLS + FORCE ROW LEVEL SECURITY like every other `scanipy_app`-scoped writer, not bypass it.
- Leave `signer` fail-closed (no default at all) until a real CMK exists — rejected: this is precisely the shortcut-path track's purpose (prove a real deterministic-core Finding lands with correct provenance end to end); leaving the last seam fail-closed would block the entire first-scan proof on an AWS KMS provisioning + rotation-model design pass that is legitimately separate, longer-running work.

**Risks:**

- The software signer's private key is generated fresh in-process on every worker boot (not persisted) — any provenance record it signs cannot be independently re-verified after that process exits (`get_public_key` would return `{}` for a new process's differently-versioned key). Acceptable for a one-shot first-scan proof; a real CMK's persistent key material is required before this signer's output can be treated as an audit-grade signature.
- `kms_key_arn = "software-dev-signer"` is a human-readable sentinel, not a real ARN — any downstream code that assumes `kms_key_arn` parses as a real AWS ARN (none does today, verified: `sign_provenance`/`verify_chain` treat it as an opaque string) would break; flagged here so a future real-ARN parser addition checks for this sentinel first.
- The `_SqlAlchemyFindingsSession` GUC-rebind-per-`add()` costs one extra `set_config` round-trip per finding even when consecutive findings share the same org (idempotent, correctness-only tradeoff) — acceptable at this stage's traffic volume; worth batching per-job rather than per-row if profiling ever shows it matters.
- Whether the live `SCANIPY_DATABASE_URL` connection role is actually a member of `scanipy_app` (required for the RLS-scoped INSERT to succeed) was not independently verifiable from this build's sandbox — the RDS instance sits in an isolated private subnet with no network path from outside the VPC (consistent with `CLAR-DEPLOY-23`'s remediation). If the grant is missing, the first live INSERT fails with a clear Postgres permission-denied error (fail-closed, not a silent isolation bug), diagnosable and fixable with a one-line `GRANT scanipy_app TO <role>;` during the Wave-5 live proof run.

---

## CLAR-DEPLOY-25 — AWS-SaaS → Docker / self-hosted / open-source pivot (reverses the AWS substrate)

**Status:** RESOLVED (2026-08-26)
**Approver:** Project owner (directing the orchestrating agent in the acting-CTO role, per the CLAR-DEPLOY-24 posture).
**Decision:** Reverse the AWS-specific substrate choices in this document (`CLAR-DEPLOY-01/-02/-04/-05/-06/-07/-09/-11/-13/-16`) onto a **Docker-deployed, self-hostable, open-source** substrate. Full remapping in `docs/DECISION-DEPLOY-02-docker-oss-pivot-2026-08-26.md`: Fargate→Docker Compose · S3→local volume / optional MinIO · RDS→Postgres Compose service · AWS-KMS→pluggable local software key · Secrets Manager→env/.env · SQS→local queue + DLQ table · CloudWatch/X-Ray→OTel stdout/OTLP · AWS-OIDC CI→GitHub Actions publishing **Cosign-signed images to GHCR** · Auth0 SSO→optional. Multi-tenancy de-scoped to single-tenant-per-deployment (`CMP-CP-03` RLS kept in code, inert). Attestor (`CMP-CP-05`) and signed provenance (`CMP-FND-03`) kept as core.

**Rationale:** A self-hostable open-source SAST platform removes substrate lock-in and lets anyone run the reproducibility/provenance guarantees (`PLAN.md` properties (a) and (c)) on their own hardware. `PLAN.md` and `SDD.md` themselves are untouched (forbidden writes): the three load-bearing properties and INV-1..6 are substrate-independent, so dropping the AWS *hosting* changes no theorem — only the `Env` realization behind `env_digest` (INV-2). The engine/version choices (`WBS.md §17` CLAR-DEPLOY-03 PostgreSQL 16; the RBAC role names; retention *durations*) are retained; only the AWS managed services are dropped. Owner authority sits above the CTO agent (`RULE-8` names the CTO as substrate approver; the owner directs it).

**Consequences:** Moving image publication ECR→GHCR changes the registry-reported image digest, which is a normal **env_digest rollover** (same mechanism as the `CMP-DEPLOY-04` rollover PRs #331/#333/#335); INV-2 is otherwise unaffected and Cosign signing is retained on GHCR. The board `AWS-TRACK` epic (#273) and its infra subtasks are retired; a `DOCKER-TRACK` epic (#337) with `DOCKER-01..03` + `OSS-01..03` replaces them (enumerated in `WBS.md §17` CLAR-DEPLOY-25). The AWS sections above (`CLAR-DEPLOY-01..24`) are retained for history but are no longer the current substrate — see the superseded-by banner at the top of this file.

---

## env_digest history (CLAR-DEPLOY-22 pointer)

`DOC-CMP-DEPLOY-02.md §6.1` step 6 says the image digest is "written to the substrate decision record under 'env_digest history'"; `DOC-CMP-DEPLOY-04.md §6.2` step 7 says this file is **not** mechanically updated for tool-version bumps. `CLAR-DEPLOY-22` (full record above; `WBS.md §17`) reconciles the two by making this a **pointer, not a ledger**: the canonical, machine-readable, append-only `env_digest` registry is the committed file `workers/env_digest_history.json` (schema + validation in `workers/build/env_digest_registry.py`; CI-checked by `scripts/check_env_digest_registry.py` and the rollover-ceremony lint `scripts/check_rollover_ceremony.py`). It is written only via a human-reviewed `env_digest rollover` PR auto-opened by the `register-env-digest` job in `.github/workflows/deploy.yml` (never a direct push — `enforce-pr-only-merges.yml` + RULE-10); registration is effective on merge. `CMP-CP-06` consumes the registry's active `scanipy-snapshot` entry via `services/control_plane/fidelity.py::production_env_digest` / `enforce_production_env` (`CLAR-CP-06-02`). This section is not itself updated per rollover — see the registry file's own git history for the authoritative timeline.

---

*End of substrate decision record. Updates to any of these decisions require CTO Agent approval and a new entry here. Referenced by WBS.md §17, CLAUDE.md §8.*
