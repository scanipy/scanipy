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
   - **Ends with an explicit verdict: APPROVE or REQUEST-CHANGES**, then emits that verdict
     once more as a machine-readable final line: `SCANIPY-REVIEW-VERDICT=APPROVE` or
     `SCANIPY-REVIEW-VERDICT=REQUEST-CHANGES`.
3. **"Enforce review verdict (merge gate)"** (`if: always()`) — the RULE-10 enforcement
   step. The reviewer step always exits `success`; this step reads the action's
   `execution_file` output (the run transcript), extracts the **last**
   `SCANIPY-REVIEW-VERDICT=…` sentinel, and **exits non-zero unless it is `APPROVE`**. So a
   `REQUEST-CHANGES` — or a missing / unparseable verdict, or a missing execution file —
   turns the single `claude-review` check **red** (fail-closed). It reads the transcript,
   not the posted comment, because the comment is known to fail to post on draft↔ready
   re-triggers (permission denials) whereas `execution_file` is set as soon as the agent run
   completes and is recovered even on the action's error path — so the gate is
   **self-recovering** on that re-trigger path.

---

## How it works

When a PR is opened, marked ready, or reopened (and is a same-repo PR), the reviewer
checks out the code, loads the Scanipy doctrine docs, runs the code-review plugin plus the
invariant/rule checks above, posts findings as a severity-tagged PR comment, and concludes
APPROVE or REQUEST-CHANGES. The **"Enforce review verdict"** step then turns that verdict
into the check's conclusion: green only on `APPROVE`, **red** on `REQUEST-CHANGES` or any
unparseable / missing verdict (fail-closed). That red/green check — together with a fully
checked PR-template checklist — is the RULE-10 merge precondition.

---

## Gate / rule mapping

- Implements **RULE-10** (Code Review approval required before merge) as the **canonical
  reviewer**. Not one of the four named CI gates. The verdict now drives the **check
  conclusion** (red on non-APPROVE / missing verdict, via the "Enforce review verdict" step's
  exit code), so it is enforced the same way as the four gates and the PR-only-merge shim. It
  is not *yet* a server-side required status check — branch protection **and** rulesets both
  return `403` on this Free/private repo (see [`README`](README.md) §5 and
  [`enforce-pr-only-merges.md`](enforce-pr-only-merges.md)); wire `claude-review` into
  `required_status_checks.contexts` once the org upgrades to Team/Pro.

---

## Failure response

A REQUEST-CHANGES verdict (or any non-APPROVE) leaves the `claude-review` check **red** and
blocks merge — address the findings, then **re-run the check by re-firing its trigger:
toggle the PR draft↔ready, or close→reopen it**. A `@claude review` comment runs
[`claude.yml`](claude.md) and posts fresh findings but does **not** re-run this job, so it
cannot turn the check green — use it to see what to fix, not to clear the gate. A failed
*run* (action error, missing `CLAUDE_CODE_OAUTH_TOKEN`) also fails the gate fail-closed (no
parseable APPROVE); it is an infra issue, not a review verdict — re-run after fixing the
secret. Not a `DOC-RUNBOOK §8` gate.

---

## Notes / gotchas

- **Cost-control: no `synchronize`.** Pushing more commits to an open PR does **not**
  re-review, and (because this job is also the merge gate) does **not** re-evaluate the
  red/green check. Re-run the check by toggling the PR draft↔ready or close→reopen. Note that
  commenting `@claude review` triggers a *different* workflow ([`claude.yml`](claude.md)): it
  posts fresh findings but does not re-run the `claude-review` job, so it cannot clear the
  gating check.
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
