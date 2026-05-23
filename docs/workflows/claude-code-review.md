# claude-code-review.yml — Claude Code Review

**Workflow `name:`** `Claude Code Review`
**File:** `.github/workflows/claude-code-review.yml`

---

## Purpose

`claude-code-review.yml` is the **canonical Scanipy v3.2 code reviewer for RULE-10**. Its
`claude-review` job is the authoritative reviewer; the former `/code-review-cmp` Skill is
**retired** and its review doctrine now lives inline in this workflow's prompt
(`.claude/rules/00-global.md`, `DOC-CMP-CI-01 §11`). On a qualifying PR it runs
`anthropics/claude-code-action` with the Scanipy review doctrine and ends with an explicit
**APPROVE / REQUEST-CHANGES** verdict, posted as a PR comment with per-finding severity
tags. RULE-10 requires this approval (with a fully checked PR-template checklist) before
merge.

---

## Triggers

```yaml
on:
  pull_request:
    types: [opened, ready_for_review, reopened]
```

- Fires when a PR is **opened**, **marked ready for review**, or **reopened**.
- **Deliberately NOT `synchronize`** — it does not re-review on every push (cost control).
  The header comment notes: re-review a pushed PR by toggling draft↔ready or with a
  one-off `@claude review` comment (which routes to [`claude.yml`](claude.md)).

---

## Jobs & steps

### `claude-review`

`runs-on: ubuntu-latest`.

**`if:`** `github.event.pull_request.head.repo.full_name == github.repository` — runs
**only on same-repo PRs**. Forked-PR workflows cannot read repo secrets, so fork PRs are
excluded (security guard). Combined with the missing `synchronize`, this workflow has
**two** scope guards: same-repo-only, and open/ready/reopen-only.

**Permissions:** `contents: read`, `pull-requests: write`, `issues: read`,
`id-token: write`. Note `contents: read` — this reviewer is **read-only on code** (it
posts comments but does not push commits, unlike [`claude.yml`](claude.md)).

**Steps:**

1. **"Checkout repository"** — `actions/checkout@v4`, `fetch-depth: 1`.
2. **"Run Claude Code Review"** (`id: claude-review`) — `anthropics/claude-code-action@v1`
   with `claude_code_oauth_token`, the `code-review@claude-code-plugins` plugin from the
   `anthropics/claude-code.git` marketplace, and an inline **`prompt`** that:
   - First reads `CLAUDE.md`, `.claude/rules/00-global.md`, `01-invariants.md`,
     `02-provenance.md`, and `.github/PULL_REQUEST_TEMPLATE.md`.
   - Runs `/code-review:code-review <repo>/pull/<number>` and additionally verifies:
     INV-1..6 compliance; RULE-4 (unspecified behaviour filed as `CLAR-*`, never designed
     inline); RULE-6 (every finding-emitting path threads `origin`, `S_version`,
     `env_digest`, and `cpg_order_hash` with its "canonical iff fingerprint_class =
     strong" annotation); that `PLAN.md` / `SDD.md` are untouched and `WBS.md` changes are
     limited to status flips / §17 / §18; and that the PR-template checklist is satisfied.
   - **Ends with an explicit verdict: APPROVE or REQUEST-CHANGES.**

---

## How it works

When a PR is opened, marked ready, or reopened (and is a same-repo PR), the reviewer
checks out the code, loads the Scanipy doctrine docs, runs the code-review plugin plus the
invariant/rule checks above, posts findings as a severity-tagged PR comment, and concludes
APPROVE or REQUEST-CHANGES. That verdict — together with a fully checked PR-template
checklist — is the RULE-10 merge precondition.

---

## Gate / rule mapping

- Implements **RULE-10** (Code Review approval required before merge) as the **canonical
  reviewer**. Not one of the four named CI gates. The verdict is process-binding (RULE-10)
  but is not currently a server-side required status check (branch protection unavailable
  — see [`README`](README.md) §5 and [`enforce-pr-only-merges.md`](enforce-pr-only-merges.md)).

---

## Failure response

A REQUEST-CHANGES verdict means the PR violates an invariant/rule or has an unsatisfied
checklist — address the findings and re-trigger (toggle draft↔ready or `@claude review`).
A failed *run* (action error, missing `CLAUDE_CODE_OAUTH_TOKEN`) is an infra issue, not a
review verdict; re-run after fixing the secret. Not a `DOC-RUNBOOK §8` gate.

---

## Notes / gotchas

- **Cost-control: no `synchronize`.** Pushing more commits to an open PR does **not**
  re-review. Re-review by toggling draft↔ready or commenting `@claude review` (→
  [`claude.yml`](claude.md)).
- **Forks excluded.** The `if:` same-repo guard means PRs from forks are not auto-reviewed
  (secrets are unavailable to forked-PR workflows). Such PRs need human or on-demand
  review.
- **Bootstrap exception — a PR that modifies *this workflow file* cannot auto-review
  itself.** Per `anthropics/claude-code-action` action policy, the action requires the
  PR's copy of the workflow to match `main`; a PR that edits `claude-code-review.yml`
  therefore cannot be reviewed by this workflow. Review such PRs via `@claude review` (the
  on-demand [`claude.yml`](claude.md), whose file is unmodified) or by a human. This is the
  documented bootstrap fallback. (The action-policy detail is action behaviour, not
  something visible in this YAML — stated here for operator awareness, not asserted as a
  step in the file.)
- **Read-only on code** (`contents: read`); it comments but cannot push fixes — that is
  [`claude.yml`](claude.md)'s role.
