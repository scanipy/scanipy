# publish-images.yml — Publish images (GHCR)

**Workflow `name:`** `Publish images (GHCR)`
**File:** `.github/workflows/publish-images.yml`

---

## Purpose

`publish-images.yml` builds the **self-host application image** (`deploy/Dockerfile`, the
`DOCKER-01` one-command deployment) and publishes it to the **GitHub Container Registry**
(`ghcr.io/<owner>/<repo>/scanipy`), **Cosign keyless-signed**. It is the successor to the
AWS-OIDC → ECR path in `deploy.yml`, which was superseded by the Docker / self-hosted /
open-source pivot (`CLAR-DEPLOY-25` / `DECISION-DEPLOY-02`).

Unlike the AWS pipeline, it needs **no long-lived cloud credentials**: it authenticates to
GHCR with the built-in `GITHUB_TOKEN` and signs with GitHub's OIDC identity via Sigstore
(keyless). The published image digest is the running deployment's `env_digest` producer
(INV-2) — publishing a new image is an `env_digest` rollover (`CLAR-DEPLOY-25 §3`).

## Triggers

- `push` on tags matching `v*` (a tagged release).
- `workflow_dispatch` with a required `tag` input (manual publish of a named tag).

## Permissions

- `contents: read`
- `packages: write` — push to GHCR.
- `id-token: write` — Cosign keyless signing (sigstore) via GitHub OIDC.

## Job: `app-image`

1. `actions/checkout@v4`.
2. `docker/login-action@v3` → GHCR with `GITHUB_TOKEN`.
3. `docker/setup-buildx-action@v3`.
4. `docker/metadata-action@v5` — semver + `major.minor` + long-sha tags (and the dispatch
   `tag` input on manual runs).
5. `docker/build-push-action@v5` — build `deploy/Dockerfile`, push, with `sbom: true` and
   `provenance: true` attestations.
6. `sigstore/cosign-installer@v3` + `cosign sign --yes "<image>@<digest>"` — keyless sign
   the pushed image **by digest**.
7. Echo the published digest as the `env_digest` rollover input.

## Failure response

A build/push/sign failure fails the workflow; no image is treated as published. Re-run after
fixing. If signing fails but the push succeeded, treat the pushed tag as **unverified** —
delete or re-sign it before any deployment consumes it (an unsigned image must never be
registered as an authoritative `env_digest`).

## Scope note

This workflow publishes the **application** image only. The digest-pinned Joern/CodeQL
worker images (`workers/*/Dockerfile`) build the deterministic-core / CodeQL path, which is
staged; their GHCR publication (with the `pins.json` build-arg wiring) is a follow-up, not
part of this workflow.
