# enforce-pr-only-merges.yml — Enforce PR-only merges on main

**Workflow `name:`** `Enforce PR-only merges on main`
**File:** `.github/workflows/enforce-pr-only-merges.yml`

---

## Purpose

This workflow is a **process-level shim for server-side branch protection**, which is
unavailable on the current org plan. GitHub Free + private repos blocks both classic
Branch Protection and Rulesets (the protection API returns 403, *"Upgrade to GitHub Pro
or make this repository public"* — see `README §"Branch protection"`). Because direct
pushes to `main` cannot be blocked server-side, this workflow **detects them after the
fact** and turns any non-PR push into a **red check** on the commit so it is impossible
to miss. It is the remote-CI layer of the three-layer shim (pre-commit + pre-push +
this workflow). It is **not** a Gate-class check.

---

## Triggers

```yaml
on:
  push:
    branches: [main]
```

- **`push` to `main`** only. Runs on every commit that lands on `main`.

**Permissions:** `contents: read`. No `concurrency` block.

---

## Jobs & steps

### `direct-push-detector` — "Direct-push detector"

`runs-on: ubuntu-latest`. Steps:

1. **`actions/checkout@v4`** with `fetch-depth: 2` (needs the HEAD commit's metadata).
2. **"Verify HEAD on main came through a PR / known automation"** — reads the HEAD
   commit's committer email, committer name, subject, and body via `git log`, then
   checks **three allowlists** in order. The first match `exit 0`s (PASS); anything else
   falls through to a loud `exit 1` (FAIL):

   - **Allowlist 1 — GitHub merge UI:** committer email `noreply@github.com` (the
     `web-flow` identity set by Merge / Squash / Rebase via the GitHub UI). Direct local
     pushes carry the developer's own git committer, so they do not match.
   - **Allowlist 2 — known automation actors:** `github.actor` is one of
     `renovate[bot]`, `github-actions[bot]`, or `dependabot[bot]` (legitimate
     automerge / commit-and-push automation).
   - **Allowlist 3 — explicit reverts:** the commit subject starts with `Revert ` (a
     revert outside the PR flow is sometimes the right incident-time call, kept
     auditable by the required subject prefix).

   On FAIL it prints the commit / actor / committer / subject, restates the three
   accepted paths, and points emergency-hotfix authors to record an `OOS-INFRA-*` entry
   in `WBS.md §18` and open a reconciliation PR, citing `README §"Branch protection"`.

---

## How it works

Every push to `main` is inspected. If the HEAD commit came through the GitHub merge UI,
from a sanctioned bot, or is an explicit `Revert `, the check passes. Any other commit —
a human direct push — fails the run, producing a red mark on the commit that surfaces the
policy violation even though GitHub cannot block it server-side.

---

## Gate / rule mapping

**Not a gate — process-level supporting workflow.** It backstops the merge discipline
that RULE-10 (Code Review approval before merge) and the PR flow assume, standing in for
the unavailable server-side branch protection. When the org upgrades to GitHub Team, real
branch-protection rules replace this and the workflow is added to
`required_status_checks.contexts` for defense-in-depth (per the workflow's own header
comment and `README §"Branch protection"`).

---

## Failure response

A red run means a **direct push to `main` was detected** outside the allowed paths.
Response: open a follow-up PR to reconcile `main` with the change, and — if it was an
intentional emergency hotfix — record an `OOS-INFRA-*` entry in `WBS.md §18` for
traceability (as the failure message instructs). There is no `DOC-RUNBOOK §8` gate
procedure (not a CI gate).

---

## Notes / gotchas

- **Detective, not preventive.** It cannot stop the push (the org plan blocks server-side
  enforcement); it only makes the violation visible after the fact. The two local layers
  (`.pre-commit-config.yaml` `no-commit-to-branch`, `.husky/pre-push`) are the preventive
  layers, but both are bypassable with `--no-verify`.
- **`fetch-depth: 2`** is required so `git log -1` on HEAD has the commit metadata
  available; a shallow `fetch-depth: 1` would still work for HEAD but the value is set to
  2 in the YAML.
- The three allowlists are exact — adding a new automation actor or merge identity
  requires editing the `case` statements in the workflow (owner: platform).
