# infra/ — SUPERSEDED (AWS substrate, decommissioned)

> **⚠️ This directory is retained for history only.**
>
> The AWS substrate (ECS Fargate · S3 · RDS · SQS · KMS · Secrets Manager · Auth0 ·
> ECR · CloudWatch/X-Ray) described by the Terraform modules here was **retired** by the
> **Docker / self-hosted / open-source pivot** — see
> [`docs/DECISION-DEPLOY-02-docker-oss-pivot-2026-08-26.md`](../docs/DECISION-DEPLOY-02-docker-oss-pivot-2026-08-26.md)
> and `CLAR-DEPLOY-25` in `WBS.md §17`.
>
> **Do not use these modules.** They describe infrastructure that no longer exists and is not
> part of the current product.

## Current substrate (what to use instead)

Scanipy is now **Docker-deployed, self-hosted, and single-tenant per deployment**:

```bash
docker compose up --build     # from the repo root
```

- Postgres runs as a Compose service (no RDS).
- Object store / queue / secrets / keys use local defaults (no S3 / SQS / Secrets Manager / KMS);
  the substrate factory (`services/substrate/factory.py`, `DOCKER-02`) selects them from the
  environment, with optional MinIO/LocalStack via `AWS_ENDPOINT_URL`.
- Images publish to **GHCR**, Cosign-signed — `.github/workflows/publish-images.yml` (`DOCKER-03`).

See the repo [`README.md`](../README.md) and [`deploy/README.md`](../deploy/README.md).
