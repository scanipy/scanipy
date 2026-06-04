# docs/status/ — MVP 12/12 coordination documents

**Goal:** drive the WBS §21 v3.2 baseline Definition of Done from **3/12 lines MET (audited 2026-06-04)** to **12/12**.

The §21 DoD has three kinds of pending work, each owned by a different team. Each team has one
document here with **fill-in fields** (`_____`). These documents are the live coordination surface
between the engineering agent waves and the human tracks.

| Document | Audience / owner | Covers |
|---|---|---|
| [`STATUS-MANAGEMENT.md`](STATUS-MANAGEMENT.md) | CTO / management | The §21 12-line tracker, the corpus-funding fork, every OPEN decision CLAR with options + a decision field |
| [`STATUS-CORPUS-TEAM.md`](STATUS-CORPUS-TEAM.md) | Corpus curators + reviewers | Per-corpus gate-strength campaign sheets (REFL, CPG-java, CPG-python, CANARY, REFAC, VULN) |
| [`STATUS-AWS-TEAM.md`](STATUS-AWS-TEAM.md) | AWS / SRE team | Substrate execution runbook — every decision already RESOLVED in §17 that now needs cloud-side execution |

## How to update

1. Edit your document's fields (`Status`, `Owner`, `Date`, `Evidence/Artifact`, `Decision`) — change nothing else.
2. Open a PR (any branch name; the `claude-review` check runs automatically — RULE-10).
3. Evidence fields want something checkable: a digest, an ARN with account redacted, a corpus.lock
   sha, a PR/issue link, a CloudWatch dashboard name.
4. When a row's completion flips a `TST-AC-*` from xfail/skip to green, say so in the PR body — the
   engineering side re-runs the §21 scorecard after every merge here.

## Board conventions (Project #5)

- **`Exec Wave` field** (single-select): the engineering wave that last shipped substantive work
  for the item — `Wave 1..6` for the 12/12 push, `AWS track` for the #273 epic. Multi-wave history
  lives in the **`wave:N` labels** (an issue touched by several waves carries several labels;
  the matching PRs carry the same label).
- **PR ↔ issue linkage** is by `Refs #N` mention (deliberate: wave PRs must not auto-close
  components that are not DONE — RULE-3), so the board's built-in "Linked pull requests" column
  stays empty by design. To see a wave's PRs: filter PRs by `label:wave:N`; to see an issue's PRs:
  its timeline mentions.
- The setup-era dependency-readiness field was renamed **"Kickoff readiness (setup-era)"**
  (historical; do not confuse with `Exec Wave`).
- `Status` transitions remain `scripts/board.sh`-only (RULE-11).

## Provenance of these documents

Derived from the 2026-06-04 five-area MVP gap audit (component truth counted by **green ACs only**,
per RULE-3 — not by merge history). Upstream truth lives in `PLAN.md` / `SDD.md` / `WBS.md`; if a
document here conflicts with those, the upstream wins and the document here must be corrected.
These files are coordination state, **not** a source of truth.
