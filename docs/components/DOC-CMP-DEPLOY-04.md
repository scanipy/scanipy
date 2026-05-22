# DOC-CMP-DEPLOY-04 — CI/CD pipeline (build, test, deploy)

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `WBS.md §2.4 CMP-DEPLOY-04` (Purpose + AC-DEPLOY-04a/b/c).
- `WBS.md §17` — `CLAR-DEPLOY-11` (RESOLVED — GitHub Actions, OIDC-to-AWS keyless) and `CLAR-DEPLOY-13` (RESOLVED — ECR + Cosign + SLSA-3).
- `SDD.md` — no `CMP-DEPLOY-*` block (these components live in `WBS.md §2.4`); the four CI gate ACs referenced here are `AC-DET-01a`, `AC-SNAP-03a`, `AC-CP-05c`, `AC-TRI-02b`.
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — CLAR-DEPLOY-11, CLAR-DEPLOY-13.
- `docs/cross-cutting/DOC-RUNBOOK.md §8` — CI-gate failure response procedures.
- `.github/workflows/deploy.yml` (existing scaffold) — the implementation surface this document specifies.
- `.github/workflows/ci.yml`, `attestor.yml`, `canary.yml`, `falsifier-cw.yml`, `stage-gate.yml` — sibling workflows that produce the gate status checks consumed here.
- `.claude/rules/00-global.md` (RULE-8 CTO approves CLAR-DEPLOY-*), `.claude/commands/sre-agent.md`.

This document is the **implementation contract** for `CMP-DEPLOY-04`. It specifies the CI/CD pipeline that builds the worker image (`CMP-DEPLOY-02`), enforces the four named CI gates from `CMP-CI-01` as hard pipeline failures, signs the image (Cosign keyless), produces a SLSA-3 attestation, and deploys the new task definition to ECS Fargate. **CMP-DEPLOY-04 does not own the gates themselves** — it owns enforcement at deploy time. The gates are owned by `CMP-CI-01` and are produced by sibling workflows (`ci.yml`, `falsifier-cw.yml`, `attestor.yml`).

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-DEPLOY-04` |
| Subsystem | Deployment (`WBS.md §2.4`) |
| Staging | cross-cutting (`WBS.md §2.4`) |
| Depends-On | `CMP-DEPLOY-01`, `CMP-DEPLOY-02` (`WBS.md §20`) |
| Owner | **DEFERRED** via `CLAR-OWNER-01`; operational owner per `.claude/commands/sre-agent.md` is the SRE/DevOps Agent. |
| INV-* touched | **INV-2 (env_digest authenticity chain).** The signing pipeline (Cosign + SLSA-3) anchors the trust chain from `env_digest` ← image digest ← build commit ← pins.json. Without this signing, a malicious actor with ECR write could publish an arbitrary image whose digest would still satisfy INV-2's NOT NULL but would not represent the committed `Env`. |
| Substrate | GitHub Actions OIDC → AWS IAM (CLAR-DEPLOY-11) · Sigstore Cosign keyless (CLAR-DEPLOY-13) · SLSA-3 attestation (CLAR-DEPLOY-13) · ECS Fargate (CLAR-DEPLOY-01) |

---

## 2. Mandate

**Verbatim WBS `Purpose:` (`WBS.md §2.4 CMP-DEPLOY-04`):**

> Pipelines for building worker images, running every CI gate enumerated under `CMP-CI-01`, deploying behind controlled gates, and registering signed image digests as the active `env_digest` for the next snapshot run. Pinned-image discipline is enforced here so it cannot be bypassed at deploy time.

**Operational role.** `CMP-DEPLOY-04` owns the GitHub Actions workflows that promote code from `main` to running ECS tasks. It is the **last line of defence** against an unpinned or unsigned image reaching production. The pipeline orchestrates: pin verification (`AC-DEPLOY-02c`), image build (`CMP-DEPLOY-02`), four hard CI gates from `CMP-CI-01` (`AC-DET-01a`, `AC-SNAP-03a`, `AC-CP-05c`, `AC-TRI-02b`), Cosign signing, SLSA-3 attestation generation, ECS task definition update, and health-wait. Note: gate enforcement at *PR-merge* time is `CMP-CI-01`'s responsibility via branch-protection required status checks; `CMP-DEPLOY-04` re-verifies the gates at *tag-push* time so a tag cannot deploy on a commit whose gates were not green.

---

## 3. Interface contract

`CMP-DEPLOY-04` is a collection of GitHub Actions workflows. Its interfaces are the workflow trigger events and the AWS resources it operates on.

### 3.1 Workflow file inventory

| File | Trigger | Job summary | Owner |
|---|---|---|---|
| `.github/workflows/ci.yml` | every PR + push to main | Lint + unit + integration + DSL proofs + e-process martingale | `CMP-CI-01` (gates), sibling to `CMP-DEPLOY-04` |
| `.github/workflows/falsifier-cw.yml` | nightly + pre-release tag | Falsifier CW (zero-FN gate, `AC-SNAP-03a`) | `CMP-CI-01` |
| `.github/workflows/attestor.yml` | every detector/engine/Env change | Attestor core + oracle pipelines (`AC-CP-05c`) | `CMP-CI-01` |
| `.github/workflows/canary.yml` | every detector/engine/Env change | Canary corpus replay | `CMP-CI-01` |
| `.github/workflows/stage-gate.yml` | manual + label | Stage A/B/C/D advancement gate | `CMP-CP-06` consumer |
| **`.github/workflows/deploy.yml`** | **tag push `v[0-9]+.[0-9]+.[0-9]+`** | **Pre-deploy-checks + build-images + deploy-ecs** | **`CMP-DEPLOY-04` (this component)** |
| `.github/workflows/enforce-pr-only-merges.yml` | every push to main | Branch protection enforcement | platform |

This component **defines** `deploy.yml` and **depends on** the four gate workflows producing required status checks. `CMP-DEPLOY-04` does not modify the four gate workflows; bumps to those live with their owners.

### 3.2 `deploy.yml` flow (verbatim contract)

The existing `.github/workflows/deploy.yml` is the implementation surface. Its three jobs:

1. **`pre-deploy-checks`** — verifies that Gates 1–3 have green check-runs on the tagged SHA. Uses `gh api repos/.../commits/{sha}/check-runs` and asserts each gate's `conclusion == "success"`. Gate 4 (e-process martingale) is verified at customer-enablement deploy, not at every release tag, per `.claude/commands/sre-agent.md` § "CI/CD pipeline enforcement".
2. **`build-images`** — uses GHA OIDC to assume `AWS_DEPLOY_ROLE_ARN`; logs in to ECR; runs `workers/build/verify_pins.py` (re-asserting `AC-DEPLOY-02c`); builds + pushes the snapshot and detector images; signs with `cosign sign --yes`; generates the SLSA-3 attestation and attaches it via `cosign attest`.
3. **`deploy-ecs`** — updates the ECS service for snapshot-worker and detector-worker via `aws ecs update-service --force-new-deployment`, then waits for `services-stable`. The new task definition references the new image digest; the running ECS task reads the digest from task metadata and surfaces it as `SCANIPY_ENV_DIGEST`.

### 3.3 The four named CI gates (referenced, owned elsewhere)

| Gate | AC | Producing workflow | Required-status-check name on `main` |
|---|---|---|---|
| **Gate 1 — DSL proofs** | `AC-DET-01a` | `ci.yml:dsl-proofs` | `Gate 1 — DSL proofs (AC-DET-01a)` |
| **Gate 2 — Falsifier CW** | `AC-SNAP-03a` | `falsifier-cw.yml` | `Gate 2 — Falsifier CW — zero false negatives (AC-SNAP-03a)` |
| **Gate 3 — Attestor core** | `AC-CP-05a/c` | `attestor.yml` | `Gate 3 — Attestor core pipeline (AC-CP-05a/c)` |
| **Gate 4 — e-process martingale** | `AC-TRI-02b` | `ci.yml:eprocess-unit` | (verified at pre-customer-enablement, not every tag) |

Branch protection on `main` (configured in `infra/modules/identity/` or via GitHub repo settings) enforces Gates 1–4 as required status checks for any PR merge. `CMP-DEPLOY-04` re-verifies Gates 1–3 at tag-push time as a defence-in-depth check: a tag may only be created on a commit that has already passed the gates as a PR; the re-verification catches the (forbidden) case of a force-push that bypassed branch protection.

### 3.4 OIDC trust policy contract

Per `CLAR-DEPLOY-11`, GitHub Actions assumes AWS IAM via OIDC keyless auth. The trust policy of `AWS_DEPLOY_ROLE_ARN` (provisioned by `CMP-DEPLOY-01` `identity` module) MUST be:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::<account>:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": [
          "repo:scanipy/scanipy-v3.2:ref:refs/tags/v*",
          "repo:scanipy/scanipy-v3.2:ref:refs/heads/main"
        ]
      }
    }
  }]
}
```

This restricts AWS access to the `main` branch and release tags — feature branches and forks cannot assume the role.

### 3.5 Cosign keyless signing

```bash
# Signed in deploy.yml:build-images. Identity = the GHA OIDC token's sub claim.
cosign sign --yes \
  <ecr>/scanipy-snapshot@sha256:<digest>
cosign sign --yes \
  <ecr>/scanipy-detector@sha256:<digest>
```

The signature is published to Sigstore Rekor (the transparency log) and to the ECR repository as a referenced artifact. The signing identity (the GHA workflow's OIDC sub) is preserved in the signature; an auditor can verify both **what was signed** (image digest) and **who signed it** (workflow identity).

### 3.6 SLSA-3 provenance attestation

```bash
# In deploy.yml:build-images, after cosign sign.
slsa-github-generator-container ... --image <ecr>/scanipy-snapshot@sha256:<digest>
# produces a slsa-provenance.json predicate
cosign attest --yes --type slsaprovenance \
  --predicate slsa-provenance.json \
  <ecr>/scanipy-snapshot@sha256:<digest>
```

The SLSA-3 predicate links:
- Image digest
- Build commit sha
- Build inputs (`workers/pins.json` content hash, `workers/snapshot/Dockerfile` content hash, `workers/snapshot/requirements.txt` content hash)
- Builder identity (the GHA workflow + runner image)
- Build timestamp

This is what makes the `env_digest` audit chain complete: starting from a `findings.env_digest` value, an auditor can pull the ECR image, fetch its SLSA attestation, and recover the exact build inputs that produced the image — closing the loop on INV-2.

### 3.7 ECS deploy step

```bash
# deploy.yml:deploy-ecs
aws ecs update-service \
  --cluster scanipy-prod \
  --service snapshot-worker \
  --force-new-deployment \
  --region us-east-1

aws ecs wait services-stable \
  --cluster scanipy-prod \
  --services snapshot-worker detector-worker \
  --region us-east-1
```

The task definition (managed by Terraform in `infra/modules/compute`) references the image by tag (the release tag). `update-service --force-new-deployment` causes ECS to re-pull the image; the new digest becomes the running `env_digest`.

**Rollback:** revert is performed by tagging an earlier commit and re-running the deploy workflow against that tag. Manual ECS rollback (without a new tag) is forbidden because it would orphan the `provenance_records` link between the SLSA attestation and the running image.

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| Release tag `v[0-9]+.[0-9]+.[0-9]+` | Git push | Triggers `deploy.yml`. Tag must be on a commit that has passed Gates 1–3 (pre-deploy-checks re-verifies). |
| `AWS_DEPLOY_ROLE_ARN` | GitHub repo secret | Assumed via OIDC keyless. |
| `AWS_ACCOUNT_ID` | GitHub repo secret | Used to construct ECR registry hostname. |
| `pins.json` | Git repo at the tagged commit | Subject to `AC-DEPLOY-02c` verification. |
| Gate status checks | sibling workflows on `main` | Must be `success` on the tagged SHA. |

### 4.2 Outputs

| Output | Where | Contract |
|---|---|---|
| Two ECR images (snapshot, detector) | ECR repos provisioned by `CMP-DEPLOY-01` | With Cosign signatures + SLSA-3 attestations. |
| Updated ECS service revisions | ECS clusters `scanipy-prod` and `scanipy-staging` | Old tasks drained per ECS deployment circuit-breaker config. |
| Sigstore Rekor entries | Public transparency log | Permanent record of who signed what when. |
| `cosign.signature_verify_count` metric | CloudWatch (`Scanipy/v3.2` namespace via `CMP-DEPLOY-03`) | Counts ECS task launch verifications. |

---

## 5. Invariants touched

| Invariant | How `CMP-DEPLOY-04` discharges it | Test |
|---|---|---|
| **INV-2 (env_digest authenticity)** | Cosign signing + SLSA-3 attestation make the chain from `findings.env_digest` ← ECR image digest ← build commit ← `pins.json` ← committed tool versions externally verifiable. An attacker who pushes an arbitrary image to ECR cannot also produce a valid Cosign signature without compromising GHA OIDC. ECS task launch verifies the signature (deferred for v3.2 baseline; the Cosign signature must at minimum exist — verification at task launch is `forthcoming` per `DOC-RUNBOOK §2.5`). | `TST-AC-DEPLOY-04c` `[FORTHCOMING]`; downstream `TST-INV-2-FND-02` (the value is the right value). |
| **INV-1 supporting** | Gate 3 (Attestor core) is a hard pre-deploy check. A regression on byte-identical SARIF over the core partition blocks the deploy, preventing a broken determinism partition from reaching production. | `TST-AC-DEPLOY-04b` `[FORTHCOMING]` (CI gates are hard fails). |
| **INV-3 supporting** | Gate 4 (e-process martingale) is a hard pre-customer-enablement check. A regression on the martingale property blocks the deploy for customer-enablement environments. | `TST-AC-TRI-02b` (downstream — Gate 4 itself). |
| **INV-4 supporting** | Gate 2 (Falsifier CW, zero FN) is a hard pre-deploy check. A regression blocks the deploy, preventing a CW-DETECT false negative from reaching production undetected. | `TST-AC-SNAP-03a` (downstream — Gate 2 itself). |

---

## 6. Algorithm / data flow

### 6.1 End-to-end deploy flow

```
1. Engineer pushes a PR → main.
   - ci.yml runs Gates 1, 4 (and the standard lint/unit/integration suite).
   - Branch protection requires Gates 1–4 as required status checks for merge.
2. PR is merged to main.
   - falsifier-cw.yml runs (Gate 2) — nightly + on every push to main.
   - attestor.yml runs (Gate 3) — on every detector/engine/Env change touched in
     the merge commit.
3. Release manager tags the commit v[X.Y.Z] (after Gates 1–4 are green on main).
4. deploy.yml fires:
   a. pre-deploy-checks:
      - Re-verifies via gh api that Gates 1, 2, 3 are `success` on the tagged SHA.
      - Hard-fails if any gate is not success.
   b. build-images:
      - Configures AWS via OIDC (assumes AWS_DEPLOY_ROLE_ARN).
      - ECR login.
      - Runs verify_pins.py (re-asserts AC-DEPLOY-02c).
      - docker buildx build + push for snapshot + detector workers.
      - cosign sign --yes per image.
      - slsa-github-generator-container + cosign attest for SLSA-3.
   c. deploy-ecs:
      - aws ecs update-service --force-new-deployment for snapshot + detector.
      - aws ecs wait services-stable.
5. ECS task launch:
   - Task reads its own image digest from task metadata → SCANIPY_ENV_DIGEST.
   - init_otel (CMP-DEPLOY-03) asserts non-empty digest; refuses to start if missing.
   - Worker enters its main loop; first job stamps the new env_digest on the
     snapshots row.
```

### 6.2 `env_digest` rollover ceremony (`AC-DEPLOY-04a`)

When a deploy changes a tool digest in `pins.json`:

1. PR title includes the marker `env_digest rollover`.
2. PR description names which tool(s) changed and why (CVE, feature, planned upgrade).
3. Security Analyst reviews if a `CW-DETECT`-touching tool changed (RULE-9).
4. PR passes Gates 1–4 like any other change.
5. Tag is cut on the merged commit; deploy.yml fires.
6. The new image digest IS the new `env_digest`; downstream snapshots use it.
7. The substrate decision record (DOC-DEPLOY-DECISIONS.md) is **not** mechanically updated for tool-version bumps — it records substrate primitives, not specific tool versions. Tool versions are tracked by the `pins.json` commit history.

### 6.3 What blocks a deploy

| Condition | Effect |
|---|---|
| Any of Gates 1–3 is not `success` on the tagged SHA | `pre-deploy-checks` job fails; pipeline does not proceed. |
| `verify_pins.py` finds an unspecified digest | `build-images` step fails. |
| Cosign signing fails | `build-images` step fails; image is in ECR but is **not** considered released (lacks signature). SRE policy: untagged or never tagged. |
| SLSA attestation generation fails | `build-images` step fails. |
| `aws ecs update-service` fails | `deploy-ecs` step fails; ECS keeps running the previous task revision. |
| `aws ecs wait services-stable` times out (15 min) | Deploy is marked failed; ECS deployment circuit-breaker (configured in task def) rolls back automatically. |

---

## 7. Failure modes and error contracts

| Failure | Detection | Response |
|---|---|---|
| OIDC trust-policy mismatch (e.g. policy restricts to `main`, tag-push is from a fork) | `aws sts assume-role-with-web-identity` returns AccessDenied | `build-images` step fails. SRE checks the trust policy in `infra/modules/identity`. |
| Gate 1–3 not green on tagged SHA | `pre-deploy-checks` job | Hard fail. The operator may not retry without first re-running the underlying gate workflow. Procedure in `DOC-RUNBOOK §8`. |
| Cosign keyless signing fails (Sigstore Rekor unavailable) | `build-images` step | Retried 3× with backoff. If Rekor is down, the deploy is paused (do not promote an unsigned image). Sigstore Rekor SLA: 99.9%; degraded operation is an SRE incident, not a Scanipy bug. |
| SLSA attestation predicate generation fails | `build-images` step | Hard fail. The image without an attestation is incomplete per `AC-DEPLOY-04c`. |
| ECS deployment circuit-breaker triggers (new tasks fail health checks) | ECS service event | Automatic rollback to previous revision; alarm `ecs.deployment_rollback` fires. SRE investigates: image-launch failure, env-var injection failure, or runtime crash. |
| Tag push from non-main branch | Tag is created on a non-main commit | `deploy.yml` still fires because the trigger is tag-push, not branch. `pre-deploy-checks` will fail because the non-main commit has not run the gate workflows. Defence-in-depth. |
| Race: two deploys for two consecutive tags | `aws ecs update-service` serialization | ECS handles serialization; second deploy waits for first to stabilize. |
| ECR repository policy denies push from the OIDC role | `docker push` step | Provisioning bug in `CMP-DEPLOY-01` `registry` module; SRE patches the policy and re-runs. |

---

## 8. Provenance threading

`CMP-DEPLOY-04` writes the **authenticity envelope** around `env_digest`:

| Artifact | Threading rule |
|---|---|
| Cosign signature | Stored alongside the image in ECR; references `image_digest`; identity = GHA OIDC workflow sub. The signature is what makes the audit-chain link `env_digest → image_digest → build_commit` **non-repudiable**. |
| SLSA-3 attestation | Stored alongside the image in ECR; predicate includes `pins.json` content hash, Dockerfile content hash, build commit. An auditor reading a `findings.env_digest` can pull this attestation and recover the exact build inputs. |
| ECS task metadata | Surfaces `image_digest` to the running task as `SCANIPY_ENV_DIGEST`; CMP-SNAP-05 then writes it through to the `snapshots` row. The substrate-level link from "what is running" to "what is recorded" is closed here. |

**Must NOT** modify any of `findings.{origin, S_version, env_digest, cpg_order_hash}` directly — those are set by the runtime components. `CMP-DEPLOY-04`'s job is to make `env_digest` **trustable**, not to write it.

---

## 9. Acceptance criteria cross-reference

Quoted verbatim from `WBS.md §2.4 CMP-DEPLOY-04`. Paraphrasing an AC is a contract break (RULE-4). All TST-AC-* are `[FORTHCOMING]`.

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-DEPLOY-04a** | > A merge to the main branch cannot deploy a worker image whose tool digests differ from those committed in the substrate decision record without an explicit `env_digest` rollover ceremony. | `TST-AC-DEPLOY-04a` `[FORTHCOMING]` — integration test: create a PR that bumps `pins.json` without the `env_digest rollover` marker in the PR title; assert the PR cannot land (lint rule rejects the change). Then add the marker, land the PR, tag, deploy — assert deploy completes. |
| **AC-DEPLOY-04b** | > The CI gates in `CMP-CI-01` are enforced as hard pipeline failures, not advisory checks. | `TST-AC-DEPLOY-04b` `[FORTHCOMING]` — integration test: inject a deliberate Gate 1 failure (e.g. add a non-distributive combinator); assert (1) the PR cannot merge (branch protection), and (2) if a tag is created on an upstream commit that had a Gate 1 failure, `pre-deploy-checks` fails. |
| **AC-DEPLOY-04c** | > Image provenance (build commit, build inputs, tool digests) is signed and published with the artifact. | `TST-AC-DEPLOY-04c` `[FORTHCOMING]` — integration test: after a successful deploy, run `cosign verify <image-digest>` and `cosign verify-attestation --type slsaprovenance <image-digest>`; assert both succeed; parse the SLSA predicate and assert it includes the build commit and the `pins.json` content hash. |

Load-bearing observation: the existing `.github/workflows/deploy.yml` already implements **§3.2 steps 1–3**. Implementation work remaining: (a) SLSA-3 attestation step (currently signing only); (b) `verify_pins.py` invocation in `build-images`; (c) ECS task-launch-time Cosign verification (defence-in-depth, per `DOC-RUNBOOK §2.5`).

---

## 10. Open questions

All `CLAR-DEPLOY-*` items bearing on this component are **RESOLVED**.

| CLAR-ID | Question | Status | Impact on CMP-DEPLOY-04 |
|---|---|---|---|
| `CLAR-DEPLOY-11` | CI/CD provider + OIDC trust pattern | **RESOLVED** | GHA + OIDC-to-AWS keyless. |
| `CLAR-DEPLOY-13` | Image registry + signing | **RESOLVED** | ECR + Cosign keyless + SLSA-3. |
| `CLAR-DEPLOY-01` | Cloud / compute service | **RESOLVED** | ECS Fargate; `update-service --force-new-deployment` is the deploy mechanism. |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | §1 `Owner` stays DEFERRED. |

No new CLAR-DEPLOY-* are filed by this document.

---

## 11. References

- `WBS.md §2.4 CMP-DEPLOY-04` — verbatim Purpose + ACs.
- `WBS.md §15 CMP-CI-01` — owner of the four named CI gates.
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — CLAR-DEPLOY-11, CLAR-DEPLOY-13.
- `docs/cross-cutting/DOC-RUNBOOK.md §8` — CI-gate failure response procedures.
- `.github/workflows/deploy.yml` (existing scaffold) — the implementation surface this document specifies.
- `.github/workflows/ci.yml`, `attestor.yml`, `canary.yml`, `falsifier-cw.yml` — sibling workflows producing the four gate status checks.
- `docs/components/DOC-CMP-DEPLOY-01.md` (sibling) — provisions OIDC role, ECR repos, ECS cluster.
- `docs/components/DOC-CMP-DEPLOY-02.md` (sibling) — produces the image this workflow builds + signs.
- `docs/components/DOC-CMP-DEPLOY-03.md` (sibling) — observability for deploy events (alarms, `cosign.signature_verify_count`).
- `.claude/rules/00-global.md` (RULE-8 CTO approves CLAR-DEPLOY-*, RULE-10 code-review approval).
- `.claude/commands/sre-agent.md` — operational owner briefing.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-DEPLOY-04`. This component is the env_digest authenticity anchor; the trust chain from a finding back to its build inputs closes here.*
