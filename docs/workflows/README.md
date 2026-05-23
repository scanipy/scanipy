# DOC-WORKFLOWS — GitHub Actions workflow reference

**Status:** ACTIVE (reference documentation)
**Audience:** SRE / DevOps, release managers, any agent landing a PR.
**Source of truth:** the YAML files under `.github/workflows/` always win. Where this
document and a workflow file disagree, the workflow file is correct and this document
is to be corrected.

This folder documents every GitHub Actions workflow in `.github/workflows/`, one
markdown file per workflow plus this index. Each per-workflow doc is faithful to the
actual YAML — purpose, triggers, jobs, steps, and failure response are read directly
from the file, never inferred.

Related contracts:

- `docs/components/DOC-CMP-CI-01.md` — owns the four named CI gates (Gate 1–4).
- `docs/components/DOC-CMP-DEPLOY-04.md` — owns `deploy.yml` (CI/CD pipeline).
- `docs/cross-cutting/DOC-RUNBOOK.md §8` — CI gate failure-response procedures.
- `docs/cross-cutting/DOC-RUNBOOK.md §5` — key / secret rotation (deploy credentials).
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — CLAR-DEPLOY-11 (GHA OIDC-to-AWS),
  CLAR-DEPLOY-13 (ECR + Cosign + SLSA-3).
- `CLAUDE.md §15` — the canonical four-gate table.
- `.claude/rules/00-global.md` — RULE-10 (`claude-review` is the canonical reviewer).

---

## 1. Purpose of the CI/CD system

Scanipy v3.2 is a multi-tenant SaaS SAST platform whose load-bearing properties are
reproducibility, incremental computability, and machine-checkable provenance
(`CLAUDE.md §2`). The workflow set exists to **defend those properties mechanically**:
four hard CI gates (`CMP-CI-01`) block any change that would break the determinism
partition, the closed-world precondition, the DSL distributivity precondition, or the
e-process martingale property; a tagged-release pipeline (`deploy.yml`, `CMP-DEPLOY-04`)
builds, signs, and ships pinned worker images so that `env_digest` is externally
verifiable (INV-2); two Claude workflows provide the canonical RULE-10 reviewer plus an
on-demand agent; and a process-level shim stands in for server-side branch protection
that is unavailable on the current GitHub plan.

---

## 2. Workflow catalogue

| File | Purpose (one line) | Trigger summary | Gate / rule enforced |
|---|---|---|---|
| [`ci.md`](ci.md) (`ci.yml`) | Main CI: lint, unit, integration, Gate 1, Gate 4. | push + PR to `main` | **Gate 1** (DSL proofs), **Gate 4** (e-process) |
| [`attestor.md`](attestor.md) (`attestor.yml`) | Attestor core determinism pipeline. | push to `main` (path-filtered), PR (path-filtered), `workflow_dispatch` | **Gate 3** (Attestor core) |
| [`falsifier-cw.md`](falsifier-cw.md) (`falsifier-cw.yml`) | CW-DETECT zero-false-negative falsifier. | nightly cron, release tags, `workflow_dispatch` | **Gate 2** (Falsifier CW) |
| [`canary.md`](canary.md) (`canary.yml`) | SCM parity + nightly full-suite regression. | nightly cron, `workflow_dispatch` | Not a gate — supporting workflow |
| [`stage-gate.md`](stage-gate.md) (`stage-gate.yml`) | CPG-fidelity gate harness (`CMP-CP-06`). | `workflow_dispatch` only (required inputs) | Enforces RULE-7 staging gate (`CMP-CP-06`) |
| [`deploy.md`](deploy.md) (`deploy.yml`) | Build + sign + deploy worker images to ECS. | tag push `v[0-9]+.[0-9]+.[0-9]+` | Re-verifies Gates 1–3; `CMP-DEPLOY-04` |
| [`enforce-pr-only-merges.md`](enforce-pr-only-merges.md) | Detect direct pushes to `main` (branch-protection shim). | push to `main` | Process-level shim (RULE-10 support) |
| [`claude.md`](claude.md) (`claude.yml`) | On-demand `@claude` agent (fixes, questions, re-review). | `issue_comment` / `pull_request_review_comment` / `issues` / `pull_request_review` containing `@claude` | Not a gate — supporting workflow |
| [`claude-code-review.md`](claude-code-review.md) | Canonical RULE-10 code reviewer (APPROVE / REQUEST-CHANGES). | PR `opened` / `ready_for_review` / `reopened` | **RULE-10** (canonical reviewer) |

---

## 3. Trigger matrix

Which event fires which workflow (✓ = configured trigger):

| Event | ci | attestor | falsifier-cw | canary | stage-gate | deploy | enforce-pr | claude | claude-review |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| `push` to `main` | ✓ | ✓ (path-filtered) | | | | | ✓ | | |
| `push` tags `v*.*.*` | | | ✓ (`-rc*` + final) | | | ✓ | | | |
| `pull_request` to `main` | ✓ | | | | | | | | |
| `pull_request` (any branch, path-filtered) | | ✓ | | | | | | | |
| `pull_request` (opened/ready/reopened) | | | | | | | | | ✓ |
| `schedule` (cron) | | | ✓ (02:00 UTC) | ✓ (03:30 UTC) | | | | | |
| `workflow_dispatch` | | ✓ | ✓ | ✓ | ✓ (required inputs) | | | | |
| `issue_comment` / `issues` / `pull_request_review*` | | | | | | | | ✓ | |

Notes:

- `ci.yml` and `claude-code-review.yml` are the only PR-fired workflows. `claude-code-review.yml`
  fires on `opened`, `ready_for_review`, `reopened` — **deliberately not `synchronize`** (cost control).
- `attestor.yml`'s `pull_request:` trigger has a `paths:` filter but **no `branches:` filter** — it
  fires on PRs to any branch whose diff touches the watched paths, not only PRs into `main`.
  (See [`attestor.md`](attestor.md) Notes — this differs from how `DOC-CMP-CI-01 §3.1` describes it.)
- `stage-gate.yml` is the only **dispatch-only** workflow and the only one with **required inputs**.
- `attestor.yml`, `falsifier-cw.yml`, `canary.yml`, and `stage-gate.yml` all expose `workflow_dispatch`.

---

## 4. The four named gates → workflow → AC

The four hard CI gates are defined in `CLAUDE.md §15` and owned by `CMP-CI-01`
(`docs/components/DOC-CMP-CI-01.md`). Their wiring to workflows, verified against the YAML:

| Gate | Workflow / job | Job `name:` (= GitHub check name) | Anchor AC | Failure semantics |
|---|---|---|---|---|
| **Gate 1 — DSL proofs** | `ci.yml` job `dsl-proofs` | `Gate 1 — DSL proofs (AC-DET-01a)` | `AC-DET-01a` | Hard release blocker |
| **Gate 2 — Falsifier CW** | `falsifier-cw.yml` job `falsifier-cw` | `Gate 2 — Falsifier CW — zero false negatives (AC-SNAP-03a)` | `AC-SNAP-03a` | Hard release blocker (single FN fails the release) |
| **Gate 3 — Attestor** | `attestor.yml` job `attestor-core` | `Gate 3 — Attestor core pipeline (AC-CP-05a/c)` | `AC-CP-05a` + `AC-CP-05c` | Hard release blocker on every detector/engine/Env change |
| **Gate 4 — e-process martingale** | `ci.yml` job `eprocess-unit` | `Gate 4 — e-process martingale (AC-TRI-02b)` | `AC-TRI-02b` | Blocks **customer-enablement** deploy only, not baseline release |

Verification notes (read from YAML, not inferred):

- Gate 1 and Gate 4 are **both** in `ci.yml` (not separate workflows).
- The Gate 3 job name anchors **both** `AC-CP-05a` and `AC-CP-05c` (`...(AC-CP-05a/c)`),
  matching `DOC-CMP-CI-01 §3.1`'s "(anchor: `AC-CP-05a`, `AC-CP-05c`)" — even though
  `CLAUDE.md §15` headlines it as `AC-CP-05c`.
- `deploy.yml`'s `pre-deploy-checks` job re-verifies Gates **1, 2, 3** on the tagged SHA;
  Gate 4 is intentionally **not** re-verified at release (it gates customer-enablement,
  per `DOC-CMP-DEPLOY-04 §3.3`).

Failure-response procedures for each gate live in `DOC-RUNBOOK §8` (§8.1 Gate 1,
§8.2 Gate 2, §8.3 Gate 3, §8.4 Gate 4).

---

## 5. Process-level-gate reality

Server-side branch protection on `main` is **not available** on the current org plan
(GitHub Free + private repo blocks classic Branch Protection and Rulesets — see
`README §"Branch protection"`). The four named gates are therefore **not** yet enforced
server-side as required status checks. Three process-level shims stand in until the org
upgrades to GitHub Team:

| Layer | Where | Enforces |
|---|---|---|
| Local — pre-commit | `.pre-commit-config.yaml` (`no-commit-to-branch`) | Refuses `git commit` on `main`/`production`/`release`. |
| Local — pre-push | `.husky/pre-push` | Refuses `git push origin main`. |
| Remote — CI | [`enforce-pr-only-merges.yml`](enforce-pr-only-merges.md) | Red check on any direct push to `main` not via the merge UI / known automation / `Revert `. |

When the org upgrades, the gate job `name:` strings (column 3 of §4) become the
`required_status_checks.contexts` entries — the names are kept stable for exactly this
reason (`DOC-CMP-CI-01 §3.3`). The `README §"Branch protection"` carries the upgrade
command.

---

## 6. Per-workflow docs

- [`ci.md`](ci.md) — CI — Scanipy v3.2 (lint, unit, Gate 1, Gate 4, integration).
- [`attestor.md`](attestor.md) — Gate 3 — Attestor core.
- [`falsifier-cw.md`](falsifier-cw.md) — Gate 2 — Falsifier CW.
- [`canary.md`](canary.md) — Canary — SCM parity + nightly regression.
- [`stage-gate.md`](stage-gate.md) — Stage Gate — CPG-fidelity evaluation.
- [`deploy.md`](deploy.md) — Deploy — ECS Fargate (tagged releases only).
- [`enforce-pr-only-merges.md`](enforce-pr-only-merges.md) — Enforce PR-only merges on main.
- [`claude.md`](claude.md) — Claude Code (on-demand `@claude` agent).
- [`claude-code-review.md`](claude-code-review.md) — Claude Code Review (canonical RULE-10 reviewer).

---

*End of DOC-WORKFLOWS index. Documentation only — the YAML files are the source of truth.*
