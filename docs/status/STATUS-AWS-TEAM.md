# STATUS — AWS / SRE team

**Owner:** SRE/DevOps · **Updated by:** AWS team, via PR.

Every substrate **decision** below is already RESOLVED in WBS §17 (the CLAR-DEPLOY-* register) — what
remains is **cloud-side execution**. Items are ordered by what they unblock; 1→6 is the critical
chain for §21-L8 and for the first **real `env_digest`** (which bootstraps CP-06 and the SNAP-05
acceptance half). Engineering items marked *(eng)* are agent-owned and listed only for sequencing.

**Security notes:** never commit credentials — evidence fields take redacted ARNs
(`arn:aws:…:<ACCOUNT_ID>:…`), digests, console screenshots links, or run URLs. All workload access
via the OIDC role; no long-lived keys.

---

## Execution runbook

### 1. AWS account + GitHub-Actions OIDC role *(CLAR-DEPLOY-13 — keyless CI→AWS)*
Create/designate the deployment account; create the OIDC-federated deploy role; set repo secrets
`AWS_DEPLOY_ROLE_ARN` + `AWS_ACCOUNT_ID` (used by `.github/workflows/deploy.yml` `build-images`).
> **Status:** DONE · **Owner:** @papadoxie · **Date:** 2026-06-06
> **Evidence:** account `<ACCOUNT_ID>` · role `arn:aws:iam::<ACCOUNT_ID>:role/scanipy-github-deploy` · secrets `AWS_DEPLOY_ROLE_ARN` + `AWS_ACCOUNT_ID` set on repo

### 2. ECR repositories + first real image build
Create ECR repos for `workers/snapshot` + `workers/detector`; run the first real `docker buildx`
build of both Dockerfiles; push; record content-addressable image digests.
> **Status:** DONE · **Owner:** @papadoxie · **Date:** 2026-06-09
> **Evidence:** snapshot `sha256:f3d51cf67de7b3a5f7acd72dd385ce1c6b1e44ecd3677ba0bb6fb58cd270d09f` · detector `sha256:a2a25f8e40dc7ca68ea833a5991191fb290ffe04b62f1d044eeee221d11cde47`

### 3. Real tool digests → `workers/pins.json` *(replaces the all-zero placeholders)*
From the built images, capture pinned digests for: debian base, python, joern, codeql, git. Open a
PR replacing the placeholder zeros; `workers/build/verify_pins.py` (already green) gates completeness.
**Unblocks:** TST-AC-DEPLOY-02a flip *(eng)* · SNAP-05's real-digest half.
> **Status:** DONE · **Owner:** @papadoxie · **Date:** 2026-06-09 · **Evidence:** pins.json PR `#300`

### 4. Cosign keyless signing *(Sigstore, per the §8 stack table)*
Sign both images; verify `cosign verify` passes in the pipeline.
> **Status:** DONE · **Owner:** @papadoxie · **Date:** 2026-06-09 · **Evidence:** `cosign verify` passed on both digests — claims validated, transparency log verified, CA-trusted certificate

### 5. Register the signed digest as the authoritative production `env_digest`
This is the CLAR-CP-06-02 bootstrap: the first pinned `Env` that CP-06 fidelity verdicts and all
INV-2 stamps reference. Coordinate with engineering for where it is registered.
**Unblocks:** TST-AC-DEPLOY-02b flip *(eng)* · CP-06 bootstrap · real INV-2 end-to-end.
> **Status:** DONE · **Owner:** @papadoxie · **Date:** 2026-06-09 · **Evidence:** nominated digest `sha256:f3d51cf67de7b3a5f7acd72dd385ce1c6b1e44ecd3677ba0bb6fb58cd270d09f` (scanipy-snapshot:v0.1.0, Cosign-signed, Sigstore transparency log)
> **Superseded by CLAR-DEPLOY-22** (`WBS.md §17`) — the canonical registration surface is the machine-readable `workers/env_digest_history.json`, not this prose row. The v0.1.0 nomination above is recorded there as `status=void` (prose-only, never machine-registered, never deployed, no artifact stamped) alongside the equally-void v0.1.1 digests (tainted direct-push provenance, `d948e6b`). The first `active` entries are the v0.1.2 digests registered by `deploy.yml`'s `register-env-digest` job.

### 6. DEPLOY-04 — pipeline end-to-end on a real version tag
Run `deploy.yml` on a `vX.Y.Z` tag with 1–5 in place: OIDC login → build → pin-check → sign → push →
deploy to ECS Fargate. Then *(eng)*: AC-DEPLOY-04a digest-drift rejection, AC-DEPLOY-04b
gates-fail-hard proof, AC-DEPLOY-04c SLSA-3 attestation predicate.
> **Status:** DONE · **Owner:** @papadoxie · **Date:** 2026-06-09 · **Evidence:** green run [#27191387683](https://github.com/scanipy/scanipy-v3.2/actions/runs/27191387683) — pre-deploy gates ✓, build+sign ✓, ECS deploy ✓

### 7. DEPLOY-03 — observability surfaces *(CLAR-DEPLOY-07)*
OTel exporters → CloudWatch Logs + X-Ray; provision the six named alarms (snapshot-fail,
detector-fail, callback-HMAC-reject, **attestor-core-diff: any non-zero = hard incident**,
CW-DETECT-disagreement, DLQ-depth). The trace-correlation AC *(eng)* needs the end-to-end scan
pipeline (Waves 4–5) — provision the surfaces now, the AC flips later.
> **Status:** DONE — remediated (Layers real, alarms operational) 2026-07-15 · **Owner:** @papadoxie (initial IaC + apply, 2026-06-21 — apply date corrected 2026-07-14 audit) → completed by orchestrating agent 2026-07-15 (post-audit remediation, per project-owner directive to complete the AWS track directly)
> **IaC:** Terraform module `infra/modules/observability/` + provisioning script `infra/observability-apply.sh` (SNS topic, 5 log groups, X-Ray group, 10 alarms incl. 2 new queue-age backstops, CloudWatch dashboard, OTel collector task def) — fixed 2026-07-15: DLQ alarm queue names, rate-alarm FILL/IF metric math (CLAR-DEPLOY-20), OTel task-def IAM roles + ZeroAndSingleDimensionRollup-pinned collector config, dashboard ARN-interpolation bug, X-Ray group-ARN CLI query bug
> **Evidence:**
> - SNS alarm topic: `arn:aws:sns:us-east-1:<ACCOUNT_ID>:scanipy-prod-alarms` — subscribed 2026-07-15 to the project owner's email (`PendingConfirmation` — confirmation click required by the recipient)
> - Dashboard: `https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards/dashboard/scanipy-prod`
> - OTel task def: `arn:aws:ecs:us-east-1:<ACCOUNT_ID>:task-definition/scanipy-otel-collector:2` (execution role `scanipy-ecs-task-execution`, task role `scanipy-otel-collector` — created 2026-07-15, was previously a dangling reference); run-task→RUNNING→stop launch-proof completed 2026-07-15
> - Alarms (10 total, re-applied 2026-07-15): `arn:aws:cloudwatch:us-east-1:<ACCOUNT_ID>:alarm:scanipy-prod-snapshot-worker-failure-rate` (real 5%/15min FILL/IF metric math) · `…:scanipy-prod-detector-worker-failure-rate` (same) · `…:scanipy-prod-callback-hmac-reject` · `…:scanipy-prod-attestor-core-diff` · `…:scanipy-prod-cw-detect-oracle-disagreement` · `…:scanipy-prod-eprocess-martingale-test-failure` · `…:scanipy-prod-dlq-snapshot-messages` (fixed to real queue name `scanipy-prod-snapshot-jobs-dlq`) · `…:scanipy-prod-dlq-detector-messages` (fixed to `scanipy-prod-detector-jobs-dlq`) · `…:scanipy-prod-snapshot-queue-oldest-age` (new) · `…:scanipy-prod-detector-queue-oldest-age` (new)
> - ECR hardened 2026-07-15: both `scanipy-snapshot` and `scanipy-detector` repos now `imageTagMutability=IMMUTABLE` + `scanOnPush=true`
> - Known remaining gap: rate alarms sit `INSUFFICIENT_DATA` until the emitter lane's metrics land in production traffic (no live tasks run yet, both services `desiredCount=0`); absence alarms for the two incident-grade metrics stay disabled pending the T-STAGE-A-01 go-live checklist (CLAR-DEPLOY-20)

### 8. DEPLOY-05 — tenant-isolation backstop (below the app layer)
Terraform the IAM session policies (`infra/modules/compute/session_policy.tf`) + per-tenant KMS CMK
path + S3 `orgs/{org_id}/` prefix denies. RDS RLS is already merged (CP-03, PR #265); the app-layer
`app.org_id` seam is landing in engineering Wave 3. Live cross-org negative test (AC-DEPLOY-05a/b)
runs after ORCH-01 exists (Wave 5).
> **Status:** DONE — IaC + live apply complete (Layers 0, 1, 2, 3); S3 prefix-deny APPLIED 2026-07-15, reconciled 2026-07-15 (least-privilege KMS + `_platform/*` scoping, PR #312 review round 2) · **Owner:** @papadoxie (initial Layer-1/3 IaC, 2026-06-10) → completed by orchestrating agent 2026-07-15 (Layer-0 data-plane buckets, S3 prefix-deny apply, CMK Lambda hardening + redeploy, Lambda invoke restriction — per project-owner directive to complete the AWS track directly) → reconciled by integration agent 2026-07-15 (claude-review findings: dropped `kms:ListAliases` from the Lambda role policy, scoped the `_platform/*` bucket-policy exemption to the snapshot bucket only) · **Date:** 2026-06-10 (updated 2026-07-15)
> **IaC:** `infra/modules/dataplane/main.tf` (Layer 0 data-plane buckets) · `infra/modules/compute/session_policy.tf` (Layer 1 IAM template) · `services/substrate/session_policy.py` (canonical renderer, single source of truth for the template) · `infra/modules/kms/` (Layer 3 CMK Lambda) · `infra/tenant-isolation-apply.sh` (apply script, idempotent). Layer 2 (RLS) already applied via PR #265. **RULE-9:** Security Analyst sign-off granted (PR #305 comment).
> **Evidence:**
> - Layer 0 (buckets, live 2026-07-15, us-east-1, account `<ACCOUNT_ID>`): `scanipy-prod-snapshot` (versioning + BPA(4/4) + SSE-AES256 + 90d lifecycle) · `scanipy-prod-witness` (same + 365d lifecycle) · `scanipy-prod-sarif` (same, no lifecycle, Object Lock ENABLED GOVERNANCE mode 7y)
> - Layer 1 (session policy template): `scanipy/prod/worker-session-policy-template` in Secrets Manager, re-stored 2026-07-15 from the canonical renderer (`services/substrate/session_policy.py`, CI-guarded < 2048 chars, CLAR-DEPLOY-21) · S3 bucket prefix-deny policies **APPLIED 2026-07-15, RECONCILED 2026-07-15** — `DenyNonTenantObjectPaths` (deny GetObject/PutObject/DeleteObject) `NotResource` `orgs/*` on all three buckets; the `_platform/*` carve-out is scoped to `scanipy-prod-snapshot` only (verified live: witness + sarif `NotResource` no longer carries `_platform/*`), matching the session policy's `S3PlatformReadOnly` statement which is snapshot-bucket-only
> - Layer 2 (RLS): already applied via PR #265
> - Layer 3 (CMK Lambda): `arn:aws:lambda:us-east-1:<ACCOUNT_ID>:function:scanipy-prod-tenant-cmk-provisioner` — hardened 2026-07-15 (strict canonical-UUID `org_id` validation pre-interpolation, rotation-retry-gap fix); redeployed from the committed, reviewed source after commit; invocation restricted to `role/scanipy-github-deploy` via `aws lambda add-permission` (statement id `scanipy-control-plane-invoke`) — deny-by-default (no other principal has an identity-policy grant on this function); execution role policy reconciled 2026-07-15 to drop unused `kms:ListAliases` (least privilege — the Lambda never calls `list_aliases`), verified live via `get-role-policy`
> - Lambda execution role: `arn:aws:iam::<ACCOUNT_ID>:role/scanipy-prod-tenant-cmk-provisioner`
> - Honest gap (recorded, not a defect): the bucket-policy layer enforces the `orgs/*` **namespace**, not the per-org boundary — matching *which* org owns a given `orgs/{org_id}/` prefix is enforced by the per-scan IAM session policy (Layer 1) and the per-tenant CMK encryption context (Layer 3), not by the bucket policy itself. See `infra/tenant-isolation-apply.sh` / `infra/modules/dataplane/main.tf` for the full rationale (`aws:PrincipalTag/org_id` is not carried by the current `sts:AssumeRole` flow).

### 9. Canary SCM orgs + credentials *(for the corpus team — CANARY-01)*
Create `scanipy-canary` orgs/projects on GitHub, GitLab, Bitbucket, Azure DevOps; store push
credentials in Secrets Manager; grant the corpus pipeline access.
**Unblocks:** `STATUS-CORPUS-TEAM.md` §4 → Gate-3's corpus.
> **Status:** _____ · **Owner:** _____ · **Date:** _____ · **Evidence:** org URLs + secret ARNs `_____`

### 10. Decision wanted — CI-side AWS emulation (LocalStack/moto)
Several env-gated ACs (DEPLOY-05a/b, parts of 02a) could become CI-runnable against LocalStack/moto
instead of waiting for live-account windows. Engineering will wire the harness if you provision/approve
the approach. *(Optional — reduces live-account coupling; not on the §21 critical path.)*
> **Decision:** **moto adopted** (CLAR-DEPLOY-21) — in-process pip dev-dep `moto[s3,sqs,kms,secretsmanager,sts]>=5.1,<6.0` for the honestly-emulatable slice only (boto3 adapter conformance, SQS redrive/DLQ-after-3, KMS envelope mechanics, session-policy render + 2048-char limit); policy-enforcement negatives (AC-DEPLOY-05a denies) are NOT emulatable and stay live-account behind the `aws_live` marker; LocalStack CE/Pro rejected; greening 02a/b against moto ECR forbidden. Record: `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md § CLAR-DEPLOY-21` · **Owner:** CTO Agent · **Date:** 2026-07-14

---

## What this unblocks (§21 mapping)

| Runbook items | §21 line |
|---|---|
| 1–6 | **L8** (substrate, signed image as env_digest) + DEPLOY-02a/b test flips |
| 5 | CP-06 bootstrap (feeds **L3**, **L9**) |
| 7 | L8 observability clause + DEPLOY-03 ACs |
| 8 | L8 isolation clause + DEPLOY-05 ACs |
| 9 | **L4** (Gate-3 corpus via CANARY-01) + AC-CORE-01a/03b + SCM-03c |
