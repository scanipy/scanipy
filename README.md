# Scanipy v3.2

Algorithmically-grounded, auditable, multi-SCM SAST platform.

## Source-of-truth documents

| Document | Purpose |
|---|---|
| [PLAN.md](PLAN.md) | Architecture — wins on disagreement with SDD |
| [SDD.md](SDD.md) | Software Design Document — component specs, IDs, acceptance criteria |
| [WBS.md](WBS.md) | Work Breakdown Structure — phases, tasks, dependency DAG, test index |

## Project board

All implementation work is tracked in the [Scanipy v3.2 GitHub Project](https://github.com/orgs/scanipy/projects).

## Reading guide (for coding agents)

Before implementing any component `CMP-X`:

1. Read `DOC-CMP-X` (Phase 0 output) as the primary spec
2. Read the cross-cutting references in `WBS.md §3.2`
3. Read the `TST-AC-X-*` test specs (Phase 1 output) — these are the done contract
4. Confirm every `Depends-On` for `CMP-X` is `DONE`
5. Implement, run tests, verify green
6. If anything is unspecified, file a `CLAR-*` entry in `WBS.md §17` — never invent scope

## Definition of Done

See `WBS.md §21` for the full v3.2 baseline Definition of Done checklist.

## Local development

```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml up -d   # Postgres 16
pip install -e ".[dev]"
pre-commit install                                # arms pre-commit + commit-msg + pre-push
pytest -m unit -q
```

`docker-compose.dev.yml` mirrors the CI service-container shape, so the same `SCANIPY_DATABASE_URL` works locally and in CI.

## Branch protection

Server-side branch protection on `main` is not available today: the org is on GitHub Free, and Free + private repos blocks both classic Branch Protection and Rulesets (`gh api repos/.../branches/main/protection` returns 403 with `"Upgrade to GitHub Pro or make this repository public to enable this feature."`).

Until the org upgrades to GitHub Team, three process-level shims stand in:

| Layer | Where | Enforces |
|---|---|---|
| Local — pre-commit | `.pre-commit-config.yaml` → `no-commit-to-branch` (`main`, `production`, `release`) | Refuses `git commit` from a protected branch. |
| Local — pre-push | `.husky/pre-push` → protected-branch guard | Refuses `git push origin main` (and deletes). Bypass with `--no-verify`. |
| Remote — CI | `.github/workflows/enforce-pr-only-merges.yml` | Runs on every push to `main`. Fails with a red check unless the commit came from the GitHub merge UI (committer = `noreply@github.com`), a known automation actor (`renovate[bot]`, `github-actions[bot]`, `dependabot[bot]`), or an explicit `Revert ` subject. |

CODEOWNERS (`.github/CODEOWNERS`) is also advisory-only on Free — it routes reviewer suggestions in the PR sidebar but does not block merges. When the org upgrades, the file is ready for "Require review from Code Owners" with no changes needed.

To upgrade now: `Settings → Billing and plans → Plans and usage → Upgrade` (Team is ~$4 / user / month). Once on Team, run:

```bash
gh api -X PUT repos/scanipy/scanipy-v3.2/branches/main/protection \
  -F required_status_checks.strict=true \
  -F 'required_status_checks.contexts[]=Lint & typecheck' \
  -F 'required_status_checks.contexts[]=Unit tests' \
  -F 'required_status_checks.contexts[]=Gate 1 — DSL proofs (AC-DET-01a)' \
  -F 'required_status_checks.contexts[]=Gate 4 — e-process martingale (AC-TRI-02b)' \
  -F 'required_status_checks.contexts[]=Direct-push detector' \
  -F enforce_admins=true \
  -F required_pull_request_reviews.require_code_owner_reviews=true \
  -F restrictions= \
  -F allow_force_pushes=false \
  -F allow_deletions=false
```
