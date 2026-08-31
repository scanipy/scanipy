# deploy.yml — Deploy — ECS Fargate (SUPERSEDED)

> **⚠️ SUPERSEDED by the Docker/OSS pivot (`CLAR-DEPLOY-25`).** The AWS ECS/ECR deploy path is
> retired; the current release path is `publish-images.yml` (GHCR + Cosign, `DOCKER-03`). `deploy.yml`
> is now `workflow_dispatch`-only and no longer fires on release tags. Retained for history.

**Workflow `name:`** `Deploy — ECS Fargate (SUPERSEDED — Docker/OSS pivot)`
**File:** `.github/workflows/deploy.yml`

---

## Purpose

`deploy.yml` is the **CI/CD release pipeline** owned by `CMP-DEPLOY-04`
(`docs/components/DOC-CMP-DEPLOY-04.md`). On a tagged release it (1) re-verifies the hard
CI gates are green on the tagged commit, (2) builds and pushes the two pinned worker
images to ECR and signs them with Sigstore Cosign, and (3) rolls the ECS Fargate
services. It is the **last line of defence** that the running `env_digest` corresponds to
a signed, gate-passing build — the INV-2 authenticity anchor (per CLAR-DEPLOY-11 GHA
OIDC-to-AWS keyless and CLAR-DEPLOY-13 ECR + Cosign + SLSA-3 in
`DOC-DEPLOY-DECISIONS.md`).

---

## Triggers

```yaml
on:
  push:
    tags: ["v[0-9]+.[0-9]+.[0-9]+"]
```

- **`push` of a final release tag** matching `v[0-9]+.[0-9]+.[0-9]+` only. No `-rc*`
  pre-release tags, no branch/PR/schedule/dispatch triggers — final releases deploy.

**Permissions (top level):** `contents: read`, **`id-token: write`** (the OIDC token
permission required to assume the AWS role keylessly). **Env:** `AWS_REGION: us-east-1`,
`ECR_REGISTRY: ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.us-east-1.amazonaws.com`.

---

## Jobs & steps

### `pre-deploy-checks` — "Pre-deploy gate verification"

`runs-on: ubuntu-latest`. Steps:

1. `actions/checkout@v4`.
2. **"Verify all required CI gates passed on this commit"** — using `GH_TOKEN`
   (`github.token`), a shell `check_gate()` helper queries the GitHub Checks API
   (`gh api repos/{repo}/commits/{sha}/check-runs`) and asserts the `conclusion` is
   `success` for each of:
   - `Gate 1 — DSL proofs (AC-DET-01a)`
   - `Gate 2 — Falsifier CW — zero false negatives (AC-SNAP-03a)`
   - `Gate 3 — Attestor core pipeline (AC-CP-05a/c)`

   If any gate is not `success`, the job prints `GATE FAIL: …` and `exit 1`s ("Do not
   deploy until all gates are green"). **Gate 4 (e-process) is intentionally NOT
   checked here** — see Gate / rule mapping.

### `build-images` — "Build and sign worker images"

`needs: pre-deploy-checks`. `outputs: snapshot_digest`, `detector_digest`. Steps:

1. `actions/checkout@v4`.
2. **"Configure AWS credentials (OIDC)"** — `aws-actions/configure-aws-credentials@v4`
   assumes `secrets.AWS_DEPLOY_ROLE_ARN` in `us-east-1` (keyless, via the OIDC token).
3. **"Login to ECR"** — `aws-actions/amazon-ecr-login@v2`.
4. **"Set up Docker Buildx"** — `docker/setup-buildx-action@v3`.
5. **"Build and push snapshot worker"** (`id: push-snapshot`) — `docker/build-push-action@v5`,
   context `workers/snapshot`, `push: true`, tag `…/scanipy-snapshot:${{ github.ref_name }}`,
   OCI revision/version labels.
6. **"Build and push detector worker"** (`id: push-detector`) — same for
   context `workers/detector`, tag `…/scanipy-detector:${{ github.ref_name }}`.
7. **"Install Cosign"** — `sigstore/cosign-installer@v3`.
8. **"Sign images with Cosign (keyless OIDC)"** — `cosign sign --yes` against each image
   **by digest** (`@${{ steps.push-*.outputs.digest }}`), using the GHA OIDC identity.

### `deploy-ecs` — "Deploy to ECS Fargate"

`needs: build-images`, **`environment: production`** (gates on the configured GitHub
environment / its protection rules). Steps:

1. `actions/checkout@v4`.
2. **"Configure AWS credentials (OIDC)"** — re-assumes `AWS_DEPLOY_ROLE_ARN`.
3. **"Update ECS service — snapshot worker"** — `aws ecs update-service --cluster
   scanipy-prod --service snapshot-worker --force-new-deployment`.
4. **"Update ECS service — detector worker"** — same for `detector-worker`.
5. **"Wait for deployment stability"** — `aws ecs wait services-stable` on both services.

---

## How it works

A release manager pushes a `vX.Y.Z` tag. `pre-deploy-checks` confirms Gates 1–3 are green
on that exact SHA via the Checks API (defence-in-depth against a tag created on a commit
that bypassed branch protection). `build-images` then assumes AWS via OIDC (no static
keys), builds + pushes the snapshot and detector worker images to ECR, and Cosign-signs
each by digest. Finally `deploy-ecs` forces a new deployment of both ECS services and
waits for stability. The pushed image digest becomes the running `env_digest` (the ECR
image digest **is** the `env_digest`, INV-2 anchor — `CLAR-DEPLOY-13`,
`DOC-RUNBOOK §2.1`).

---

## Gate / rule mapping

- **Re-verifies Gates 1, 2, 3** at tag-push time (defence-in-depth; the primary
  enforcement is branch protection on `main`). Implements **`CMP-DEPLOY-04`**.
- **Gate 4 (e-process) is deliberately excluded** from `pre-deploy-checks`: Gate 4 gates
  the **customer-enablement** deploy track, not the baseline release tag
  (`DOC-CMP-DEPLOY-04 §3.3`, `DOC-CMP-CI-01 §3.1`, `DOC-RUNBOOK §8.4`). Its absence here
  is by design, not an omission.
- Anchors **INV-2** (env_digest authenticity via Cosign signing).

---

## Failure response

- **`pre-deploy-checks` red:** one of Gates 1–3 is not `success` on the tagged SHA. Do
  not deploy; re-run the underlying gate workflow and fix the failure first
  (`DOC-RUNBOOK §8`). A determinism (Gate 3) failure follows the attestation-incident
  procedure (`DOC-RUNBOOK §7`).
- **`build-images` red:** OIDC trust-policy mismatch, ECR push denial, or Cosign signing
  failure (do not promote an unsigned image). Deploy-credential / role rotation procedure
  is in `DOC-RUNBOOK §5`.
- **`deploy-ecs` red / unstable:** `update-service` or `wait services-stable` failed; ECS
  keeps the previous task revision (and the deployment circuit-breaker rolls back per the
  task-def config). See `DOC-CMP-DEPLOY-04 §6.3` and `DOC-RUNBOOK §2.5`.

---

## Notes / gotchas

- **Final tags only** (`v[0-9]+.[0-9]+.[0-9]+`). `-rc*` tags trigger `falsifier-cw.yml`
  (Gate 2) but **not** `deploy.yml`.
- **Implementation gap vs. the component spec.** `DOC-CMP-DEPLOY-04 §3.2 / §9` specifies
  steps the current YAML does **not yet** contain: SLSA-3 attestation
  (`cosign attest --type slsaprovenance`), a `verify_pins.py` invocation in
  `build-images`, and ECS-task-launch-time Cosign verification. The YAML today does
  signing only. This is a known remaining-implementation item (flagged, not fixed).
- **`deploy-ecs` references `scanipy-prod` only.** `DOC-CMP-DEPLOY-04 §4.2` mentions both
  `scanipy-prod` and `scanipy-staging`; the YAML updates `scanipy-prod` services only.
  Documented as the YAML's actual behaviour.
- **Secrets required:** `AWS_ACCOUNT_ID`, `AWS_DEPLOY_ROLE_ARN`. The OIDC trust policy is
  scoped to `main` + release tags (`DOC-CMP-DEPLOY-04 §3.4`) so forks/feature branches
  cannot assume the role.
