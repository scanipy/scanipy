# Scanipy

**Auditable, self-hostable SAST — findings you can trust as code changes.**

[![CI](https://github.com/scanipy/scanipy/actions/workflows/ci.yml/badge.svg)](https://github.com/scanipy/scanipy/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
![Docker](https://img.shields.io/badge/deploy-docker--compose-2496ed)

Scanipy runs established static-analysis engines (Semgrep, and a CodeQL adapter) and wraps every
finding in a **trust layer**: a refactor-invariant identity, reproducibility under a pinned
environment, and a signed, machine-checkable provenance chain — so a finding keeps the same identity
across refactors, reproduces on re-run, and is auditable.

## Quickstart — one command, no cloud

```bash
docker compose up --build
# → open http://localhost:8000  and paste a public GitHub repo URL
```

No AWS, no account. Brings up Postgres + the scan API + a paste-a-repo UI, all self-hosted.

## What works today vs. what's staged

| Capability | Status |
|---|---|
| One-command Docker deploy · self-hosted · single-tenant | ✅ shipping |
| Detection via oracle engines (Semgrep; CodeQL adapter) — Python today | ✅ shipping — `origin=oracle-passthrough` |
| Findings persisted + served; signed-provenance & attestor machinery | ✅ mechanisms built + tested |
| Refactor-invariant fingerprint · byte-identical reproducibility on **live** findings | 🧪 staged — implemented & unit-tested, integration in progress |
| Deterministic-core IFDS/IDE engine (theorem-backed detection) | 🧪 staged |
| Multi-language · multi-tenant · SSO | 🔮 future / de-scoped for the OSS build |

**Honest labeling.** Findings on the shipping path are `origin=oracle-passthrough` with a `weak`
fingerprint — a stable id, **not** a canonical-graph claim. Engine-backed findings are never
presented as theorem-backed. Details in [`deploy/README.md`](deploy/README.md).

## Documentation

- **[`deploy/README.md`](deploy/README.md)** — self-hosting guide (configuration, upgrade, backup, security posture).
- [LICENSE](LICENSE) (Apache-2.0) · [CONTRIBUTING](CONTRIBUTING.md) · [SECURITY](SECURITY.md) · [Code of Conduct](CODE_OF_CONDUCT.md)

## Development

```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml up -d   # Postgres 16 (for the test suite)
pip install -e ".[dev,http]"                      # requires Python 3.11+
pre-commit install
pytest -m unit -q
```

`docker-compose.dev.yml` mirrors the CI service-container shape, so the same `SCANIPY_DATABASE_URL`
works locally and in CI. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Project internals (design & governance)

Scanipy is developed against a set of source-of-truth documents.

> **Note on the plan docs:** `PLAN.md` and `SDD.md` describe the *original* architecture — a
> multi-tenant AWS SaaS. The project has since **pivoted** to the Docker / self-hosted /
> open-source, single-tenant design shown above. The pivot is recorded in
> [`docs/DECISION-DEPLOY-02-docker-oss-pivot-2026-08-26.md`](docs/DECISION-DEPLOY-02-docker-oss-pivot-2026-08-26.md)
> and `CLAR-DEPLOY-25` (`WBS.md §17`); the algorithms and invariants in PLAN/SDD are unchanged.

- [CLAUDE.md](CLAUDE.md) — project map (read this first for internals).
- [PLAN.md](PLAN.md) · [SDD.md](SDD.md) · [WBS.md](WBS.md) — architecture · component specs · work breakdown (original plan; see the note above).
- Governance rules live under [`.claude/rules/`](.claude/rules/); contribution process is in [CONTRIBUTING.md](CONTRIBUTING.md).
