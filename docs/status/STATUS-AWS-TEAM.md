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
> **Evidence:** account `508703380027` · role `arn:aws:iam::<ACCOUNT_ID>:role/scanipy-github-deploy` · secrets `AWS_DEPLOY_ROLE_ARN` + `AWS_ACCOUNT_ID` set on repo

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

### 6. DEPLOY-04 — pipeline end-to-end on a real version tag
Run `deploy.yml` on a `vX.Y.Z` tag with 1–5 in place: OIDC login → build → pin-check → sign → push →
deploy to ECS Fargate. Then *(eng)*: AC-DEPLOY-04a digest-drift rejection, AC-DEPLOY-04b
gates-fail-hard proof, AC-DEPLOY-04c SLSA-3 attestation predicate.
> **Status:** _____ · **Owner:** _____ · **Date:** _____ · **Evidence:** green run URL `_____`

### 7. DEPLOY-03 — observability surfaces *(CLAR-DEPLOY-07)*
OTel exporters → CloudWatch Logs + X-Ray; provision the six named alarms (snapshot-fail,
detector-fail, callback-HMAC-reject, **attestor-core-diff: any non-zero = hard incident**,
CW-DETECT-disagreement, DLQ-depth). The trace-correlation AC *(eng)* needs the end-to-end scan
pipeline (Waves 4–5) — provision the surfaces now, the AC flips later.
> **Status:** _____ · **Owner:** _____ · **Date:** _____ · **Evidence:** alarm ARNs / dashboard `_____`

### 8. DEPLOY-05 — tenant-isolation backstop (below the app layer)
Terraform the IAM session policies (`infra/modules/compute/session_policy.tf`) + per-tenant KMS CMK
path + S3 `orgs/{org_id}/` prefix denies. RDS RLS is already merged (CP-03, PR #265); the app-layer
`app.org_id` seam is landing in engineering Wave 3. Live cross-org negative test (AC-DEPLOY-05a/b)
runs after ORCH-01 exists (Wave 5).
> **Status:** _____ · **Owner:** _____ · **Date:** _____ · **Evidence:** plan/apply links `_____`

### 9. Canary SCM orgs + credentials *(for the corpus team — CANARY-01)*
Create `scanipy-canary` orgs/projects on GitHub, GitLab, Bitbucket, Azure DevOps; store push
credentials in Secrets Manager; grant the corpus pipeline access.
**Unblocks:** `STATUS-CORPUS-TEAM.md` §4 → Gate-3's corpus.
> **Status:** _____ · **Owner:** _____ · **Date:** _____ · **Evidence:** org URLs + secret ARNs `_____`

### 10. Decision wanted — CI-side AWS emulation (LocalStack/moto)
Several env-gated ACs (DEPLOY-05a/b, parts of 02a) could become CI-runnable against LocalStack/moto
instead of waiting for live-account windows. Engineering will wire the harness if you provision/approve
the approach. *(Optional — reduces live-account coupling; not on the §21 critical path.)*
> **Decision:** _____ · **Owner:** _____ · **Date:** _____

---

## What this unblocks (§21 mapping)

| Runbook items | §21 line |
|---|---|
| 1–6 | **L8** (substrate, signed image as env_digest) + DEPLOY-02a/b test flips |
| 5 | CP-06 bootstrap (feeds **L3**, **L9**) |
| 7 | L8 observability clause + DEPLOY-03 ACs |
| 8 | L8 isolation clause + DEPLOY-05 ACs |
| 9 | **L4** (Gate-3 corpus via CANARY-01) + AC-CORE-01a/03b + SCM-03c |
