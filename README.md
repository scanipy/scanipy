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
