# claude.yml — Claude Code (on-demand `@claude` agent)

**Workflow `name:`** `Claude Code`
**File:** `.github/workflows/claude.yml`

---

## Purpose

`claude.yml` is the **on-demand `@claude` agent**. It runs `anthropics/claude-code-action`
when a trusted user mentions `@claude` in an issue, a PR review, or a comment — for
fixes, questions, and **on-demand re-review**. It is explicitly **not** the routine code
reviewer (that is [`claude-code-review.yml`](claude-code-review.md), the canonical RULE-10
reviewer). Because its workflow file is unmodified by feature PRs, it also serves as the
**bootstrap path** for reviewing PRs that the routine reviewer cannot auto-review (see
[`claude-code-review.md`](claude-code-review.md) Notes).

---

## Triggers

```yaml
on:
  issue_comment:               { types: [created] }
  pull_request_review_comment: { types: [created] }
  issues:                      { types: [opened, assigned] }
  pull_request_review:         { types: [submitted] }
```

- New issue comments, new PR review comments, opened/assigned issues, and submitted PR
  reviews. The job's `if:` then filters to events whose body/title actually contain
  `@claude` **and** whose author is trusted (see below).

---

## Jobs & steps

### `claude`

`runs-on: ubuntu-latest`.

**`if:` condition (two ANDed clauses):**

1. The triggering text contains `@claude` — checked per event type:
   `issue_comment` / `pull_request_review_comment` comment body, `pull_request_review`
   review body, or `issues` body **or** title.
2. The actor's `author_association` is one of `OWNER`, `MEMBER`, or `COLLABORATOR`
   (checked across the comment / issue / review association fields). This gates the
   agent to trusted contributors — drive-by external commenters cannot invoke it.

**Permissions (elevated):** `contents: write`, `pull-requests: write`, `issues: write`,
`id-token: write`, `actions: read`. Note **`contents: write`** — this agent **can push
commits** when asked (it is the fix/remediation path, unlike the read-only reviewer).

**Steps:**

1. **"Checkout repository"** — `actions/checkout@v4`, `fetch-depth: 1`.
2. **"Run Claude Code"** (`id: claude`) — `anthropics/claude-code-action@v1` with
   `claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}`. No custom `prompt`
   (unlike the review workflow); it acts on the `@claude` instruction in context.

---

## How it works

A trusted user writes `@claude <instruction>` in an issue, a PR comment, a PR review
comment, or a PR review. The `if:` gate confirms both the mention and the author's
association, then the action runs with write permissions and carries out the request —
answering a question, making a fix and pushing a commit, or performing an on-demand
re-review (`@claude review`).

---

## Gate / rule mapping

**Not a gate — supporting workflow.** It complements RULE-10 by providing on-demand
agent assistance and re-review, but the **canonical** RULE-10 reviewer is
[`claude-code-review.yml`](claude-code-review.md).

---

## Failure response

No deploy/gate impact. A failed run typically means a missing/invalid
`CLAUDE_CODE_OAUTH_TOKEN` secret or an action error; re-invoke with `@claude` after the
secret is fixed. Not covered by `DOC-RUNBOOK §8` (not a CI gate).

---

## Notes / gotchas

- **Trust-gated.** Only `OWNER` / `MEMBER` / `COLLABORATOR` can invoke it; this prevents
  external actors from triggering an agent with `contents: write`.
- **It can push commits** (`contents: write`) — distinct from the read-only review
  workflow. Use it for fixes and remediation, not as the routine reviewer.
- **Bootstrap-exception path.** A PR that modifies `claude-code-review.yml` itself cannot
  be auto-reviewed by that workflow (per `anthropics/claude-code-action` action policy);
  because `claude.yml`'s own file is unmodified, `@claude review` here is the documented
  fallback (alongside human review). See [`claude-code-review.md`](claude-code-review.md).
