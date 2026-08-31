# Contributing to Scanipy

Thanks for your interest in Scanipy — an algorithmically-grounded, auditable SAST platform.

## Ground rules (the short version)

Scanipy is governed by a small set of source-of-truth documents and invariants. Read these first:

- **[CLAUDE.md](CLAUDE.md)** — the project map and agent/dev context (derived from PLAN/SDD/WBS).
- **[PLAN.md](PLAN.md)** — architecture; wins on any disagreement.
- **[SDD.md](SDD.md)** — component specs (`CMP-*`) and acceptance criteria (`AC-*`).
- **[WBS.md](WBS.md)** — work breakdown, dependency DAG, and the `CLAR-*` / `OOS-*` registers.
- **`.claude/rules/`** — the six architectural invariants (INV-1..6), provenance, scope, staging, determinism.

The non-negotiables:

1. **Never edit `PLAN.md` or `SDD.md`.** If a decision is missing, file a `CLAR-*` in `WBS.md §17`
   rather than inventing scope (RULE-4).
2. **Thread provenance.** Every component that emits a finding carries `origin`, `S_version`,
   `env_digest`, and (for core findings) `cpg_order_hash` with its conditional-canonicality annotation
   (INV-1/INV-2/INV-5). See `.claude/rules/02-provenance.md`.
3. **Honest labeling.** `deterministic-core` findings are theorem-backed and reproducible;
   `oracle-passthrough` findings (Semgrep/CodeQL) carry a measured rate, never the determinism theorem.
   Never blur the two, and never claim recall numbers for a `(class, language)` pair that hasn't passed
   the CPG-fidelity gate (INV-6).

## Development setup

```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml up -d     # Postgres 16
pip install -e ".[dev,http]"
pre-commit install                                  # ruff, mypy, detect-secrets, commit-msg hooks
pytest -m unit -q
```

To run the full self-host app locally: `docker compose up --build` (see [README](README.md)).

## Pull requests

- One logical change per PR. Follow `.github/PULL_REQUEST_TEMPLATE.md` — it encodes the invariant,
  provenance, and test checklist.
- CI must be green: `ruff check`/`ruff format --check`, `mypy`, unit + integration tests, and the four
  release gates (DSL proofs, Falsifier CW, Attestor, e-process). Linters are **pinned** — bump
  deliberately and reformat, never float.
- The `claude-review` check must reach an **APPROVE** verdict before merge (RULE-10).
- Add tests for new behavior; never weaken a falsifier threshold to make a build pass.

**Contributing from a fork.** The automated `claude-review` gate only runs on branches in this
repository (it needs repository secrets, which fork PRs cannot access), so a **fork PR cannot satisfy
RULE-10 on its own** — that's expected, not a rejection. A maintainer will run the review from a repo
branch (or re-run it after pulling your change) and merge once it's APPROVE. Open your PR from a fork
as normal; the internal `CMP-*` / board rituals in the PR template are for in-team work — for an
external contribution, describe the change and the tests you ran, and a maintainer maps it to the
process.

## Reporting security issues

Please **do not** open a public issue for vulnerabilities. See [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions are licensed under the
[Apache License 2.0](LICENSE).
