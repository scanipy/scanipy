# DECISION-DEPLOY-02 — AWS-SaaS → Docker / self-hosted / open-source pivot

**Date:** 2026-08-26
**Decider:** Project owner (elirazamumtaz@gmail.com), directing the orchestrating agent in the acting-CTO role (same posture as CLAR-DEPLOY-24 / CLAR-ORCH-10).
**Status:** RATIFIED (owner-directed). CTO-agent ratification of the derived `CLAR-DEPLOY-25` record is a formality, not a gate — the owner is the authority above the CTO agent.
**Supersedes / re-resolves:** the AWS-specific portions of `CLAR-DEPLOY-01, -02, -04, -05, -06, -07, -09, -11, -13, -16` (see the remapping table). Does **not** touch PLAN.md / SDD.md (forbidden writes) — the three load-bearing properties (a reproducibility, b incremental computability, c machine-checkable provenance) and INV-1..6 are unchanged by this decision.

---

## 1. What changed and why

Scanipy v3.2 was scoped as a multi-tenant SaaS on AWS (ECS Fargate + S3 + RDS + SQS + KMS + Secrets Manager + Auth0 + CloudWatch/X-Ray; see `CLAUDE.md §8` and `DOC-DEPLOY-DECISIONS.md`). The AWS substrate execution epic (board `AWS-TRACK`, issue #273 + #274–#283) had largely landed.

The owner has redirected the project to a **Docker-deployed, self-hostable, open-source** product:

- **Deploy target:** the full platform (deterministic-core + oracle), not just the demo scanner.
- **"Public" means:** the **source code is open-sourced** (public GitHub repo). A public *hosted* instance is out of scope for this decision — the artifact people receive is a repo they can `docker compose up` themselves.
- **Board scope:** retarget the whole board — drop AWS, re-aim CMP-DEPLOY-* at Docker, de-scope the components that exist only to serve the multi-tenant-AWS-SaaS shape.

Rationale: a self-hostable OSS SAST platform removes the substrate lock-in, lets anyone run the reproducibility/provenance guarantees on their own hardware, and collapses the operational surface (no per-tenant cloud isolation to build) to a single-tenant-per-deployment model that matches how a self-hosted tool is actually run.

## 2. Substrate remapping

| Concern | Was (AWS) | Now (Docker / self-hosted OSS) | Reversed CLAR |
|---|---|---|---|
| Compute | ECS Fargate (pinned-image workers) | Docker Compose services (pinned-image workers, same digest-pinning discipline) | CLAR-DEPLOY-01 |
| Object store | Amazon S3 | Local filesystem volume by default; **MinIO** (S3-API) as the optional drop-in for the same deterministic key paths | CLAR-DEPLOY-02 |
| Relational DB | PostgreSQL 16 on **RDS** | PostgreSQL 16 as a **Compose service** (same engine/version; Alembic migrations unchanged) | CLAR-DEPLOY-03 (engine kept; managed-service dropped) |
| KMS / encryption | AWS KMS envelope encryption, per-tenant CMK | Pluggable key provider: local software key (age/libsodium-style) by default; interface preserved so a KMS/Vault backend is a config swap | CLAR-DEPLOY-04 |
| Secrets injection | Secrets Manager → ECS task | Environment variables / `.env` (Compose), Docker secrets optional | CLAR-DEPLOY-05 |
| Queue | SQS + per-queue DLQ | Local queue service (Redis- or Postgres-backed) with a DLQ table; same enqueue/report_status contract | CLAR-DEPLOY-06 |
| Observability | OTel → CloudWatch + X-Ray + named alarms | OTel exporter kept; default sink is stdout/OTLP-collector; CloudWatch/X-Ray dropped (pluggable) | CLAR-DEPLOY-07 |
| Network model | VPC / private subnets / ingress-egress | Compose network; analysis containers run `--network none` (already the demo posture) | CLAR-DEPLOY-09 |
| CI/CD | GitHub Actions OIDC-to-AWS, keyless | GitHub Actions building + publishing **signed public images to GHCR** (`ghcr.io`); Cosign signing kept; AWS OIDC trust dropped | CLAR-DEPLOY-11, -13 |
| Multi-tenancy | Per-tenant KMS + S3 prefix denies + RLS | **Single-tenant per deployment** for the OSS MVP. The tenancy schema (CMP-CP-03) and RLS stay in the code (already DONE) but are inert in a single-tenant deploy; multi-tenant isolation as a substrate concern is de-scoped, not deleted. | CLAR-DEPLOY-16 |
| AuthN | Auth0 OIDC/SAML SSO | Optional: local admin for self-host; SSO becomes an optional plugin, not a launch requirement | CLAR-DEPLOY-10 (IdP), CMP-CP-04 reframed |

## 3. env_digest continuity (INV-2)

`env_digest` is defined as the container image digest (INV-2, `CMP-SNAP-01`). Moving image publication from **ECR** to **GHCR** changes the registry-reported digests, which is a normal **env_digest rollover event** — the same mechanism already exercised by the recent `CMP-DEPLOY-04` rollover PRs (#331, #333, #335 register successive `v0.1.x` digests). INV-2 is otherwise unaffected: findings and provenance records continue to carry a pinned `env_digest`; only the source registry of that digest changes. The first GHCR build registers a fresh authoritative `env_digest` exactly as #278 did for ECR/Cosign. Cosign keyless signing is retained (GHCR supports it), so the signed-provenance chain (`CMP-FND-03`) is unbroken.

## 4. What is explicitly **kept** (not de-scoped)

- **The determinism Attestor (`CMP-CP-05`)** — this is the core value proposition (property a). Only its *infra host* moves from AWS to Docker/CI; its two-pipeline contract is unchanged.
- **Signed provenance (`CMP-FND-03`)** — Cosign retained on GHCR.
- **The tenancy schema + RLS (`CMP-CP-03`)** — stays in code; inert-but-present under single-tenant.
- **Credential encryption (`CMP-CP-02`)** — interface kept; default backend becomes a local software key provider.
- **All analysis components** (SCM / SNAP / CORE / DET / FND / TRI / CORP / CI gates) — untouched by this decision.

## 5. Open-source readiness preconditions (gate on `OSS-01` before `OSS-02`)

Flipping the repo public is the **only irreversible action** in this pivot and is gated:

1. Add a `LICENSE` (owner to choose; Apache-2.0 recommended for a security tool with patent-grant needs).
2. **Secret / sensitive-data scrub across the tree, the workflows, AND git history**, not just HEAD:
   - AWS account id `508703380027` and OIDC role ARNs in `.github/workflows/deploy.yml` and any Terraform.
   - The RDS connection string previously handled from Secrets Manager (`scanipy/dev/database_url`) — confirm it was never committed; if it (or any credential) is in history, history must be rewritten or the repo re-created before going public.
3. Public-facing docs: README quickstart (`docs compose up`), CONTRIBUTING, CODE_OF_CONDUCT, SECURITY.md, self-hosting runbook (retarget `DOC-RUNBOOK`).
4. Owner confirmation immediately before the visibility flip.

## 6. Board realization

Tracked on GitHub Project #5 as a `DOCKER-TRACK` epic (symmetry with the retired `AWS-TRACK` #273), anchored to `CLAR-DEPLOY-25`. New tasks cannot receive `WBS.md` work-package entries (allowed WBS writes are §17/§18 appends + status flips only), so each new issue body carries `Anchor: CLAR-DEPLOY-25 / DECISION-DEPLOY-02` and the six tasks are enumerated in `CLAR-DEPLOY-25`'s resolution column.

- **Removed:** `AWS-TRACK` #273–#281, #283 (completed AWS infra now superseded; historical closed-completed issues retained with a superseded-by comment, delisted from the active board). #282 (canary) is **kept and reframed** — the canary corpus is valid; only "creds in Secrets Manager" dies.
- **Retarget (body/comment only, no retitle — titles are already substrate-neutral):** CMP-DEPLOY-01..05, CMP-CP-02/03/04/05.
- **Added:** `DOCKER-01` compose stack · `DOCKER-02` substrate adapters (S3→local/MinIO, SQS→local, Secrets→env, KMS→local key) · `DOCKER-03` GHCR signed images · `OSS-01` license + public-prep + history scrub · `OSS-02` flip public (gated) · `OSS-03` self-hosting docs.

---

*Cross-reference: `CLAUDE.md §8` (stack table, superseded-pointer added), `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` (superseded-pointer added), `WBS.md §17 CLAR-DEPLOY-25`. PLAN.md / SDD.md unchanged (forbidden writes).*
