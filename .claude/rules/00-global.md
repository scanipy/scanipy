# Global agent rules — Scanipy v3.2

These ten rules apply to **every agent** in every session, regardless of role.
They are also enforced via the PR checklist and the `pre-edit-sot-guard.sh` hook.

---

## RULE-1 — Docs before code

No implementation agent starts a CMP-X until `DOC-CMP-X` in `docs/components/` is marked DONE.
The documentation is the implementation contract; coding without it is out of contract.

## RULE-2 — Dependencies before start

No implementation agent starts a CMP-X until every component in its `Depends-On` list (WBS §20 DAG) has status `DONE` (all TST-AC-* green).
Violation: treating `IN-PROGRESS` as sufficient to proceed.

## RULE-3 — Tests define done

A CMP-X is `DONE` **only** when every `TST-AC-X-*` and `TST-INV-*` attached to it is green.
Partial green is `IN-PROGRESS`, not `DONE`.

## RULE-4 — No invented scope

If a required behaviour is unspecified by `PLAN.md` / `SDD.md`, file a `CLAR-*` item in `WBS.md §17`.
Do not invent or design the missing piece inline.
`SDD.md §0 rule 6`: *"If a capability is needed but not specified here, emit a CLARIFICATION-NEEDED work item rather than designing it."*

## RULE-5 — Honour the out-of-scope register

If a derived task implies any item in `WBS.md §18` (CI-agent, on-prem runner, container-image scanning, binary-only analysis, IDE plugin, C/C++ core port, environment-independent determinism, LLM-influenced core findings), emit an `OOS-*` entry and do not schedule the task.

## RULE-6 — Thread all four provenance fields

Every component that emits or mutates a finding must thread:
1. `S_version` — the version of the accepted spec set (INV-2)
2. `env_digest` — the container image digest (INV-2)
3. `origin` — `deterministic-core` or `oracle-passthrough` (INV-1)
4. `cpg_order_hash` with its conditional-canonicality annotation (`canonical iff fingerprint_class = strong`) (INV-5)

Missing any of these in a finding-emitting path is a hard invariant violation.

## RULE-7 — Respect the staging gate

No `(class, language)` pair enters Algorithm 2 benchmarking before `CMP-CP-06` is green for that language.
`STAGE-GATED` is a valid status; it is not a blocker to fix by hacking around the gate.

## RULE-8 — CTO approves CLAR-DEPLOY-* before dependent phase

No phase that depends on a deployment substrate decision may start before the CTO Agent has recorded a decision for the relevant `CLAR-DEPLOY-*` in `WBS.md §17`.
The CTO Agent is the sole approver of substrate choices.

## RULE-9 — Security Analyst reviews INV-3 and INV-4 components

Every component that touches INV-3 (LLM off the detection path) or INV-4 (undecidable approximations with required safe direction) requires Security Analyst sign-off before the PR merges.
Affected components: CMP-CP-02, CMP-SNAP-03, CMP-SNAP-04, CMP-DET-01, CMP-TRI-01, CMP-TRI-02, CMP-TRI-03.

## RULE-10 — Code Review approval required before merge

Every PR is reviewed by the **canonical reviewer: the `claude-review` CI check** (`.github/workflows/claude-code-review.yml`), which runs automatically when a PR is opened / marked ready / reopened. It reads `CLAUDE.md` + these rules + the PR template and posts findings with an explicit **APPROVE / REQUEST-CHANGES** verdict. A PR may merge only when that verdict is **APPROVE** and the PR-template checklist is fully checked; a REQUEST-CHANGES verdict (or an unchecked checklist) blocks merge.

This is the **sole** code-review surface — the former `/code-review-cmp` Skill is retired (one doctrine, one place). Server-side required-status-checks are unavailable on this repo (GitHub Free/private), so RULE-10 is a **process-level gate**, enforced the same way as the four CI gates and the PR-only-merge shim (`.github/workflows/enforce-pr-only-merges.yml`). The on-demand `@claude` agent (`.github/workflows/claude.yml`) is for fixes/questions/re-review, not the routine gate; re-trigger a review by toggling draft↔ready or commenting `@claude review`.

## RULE-11 — The board reflects reality; check it before you pick up work

The GitHub Project board (#5, *"Scanipy v3.2 Development"*) is the live operational mirror of `WBS.md` status codes. It is the authority for **who is doing what right now**. A board that lies causes two agents to implement the same component and collide on merge. Two obligations bind every agent (orchestrator and sub-agent alike):

**Pre-flight — before the first edit on any `CMP-*` / `T-CMP-*` / meta issue:**
1. Run `scripts/board.sh check <issue-number>`. If it exits non-zero (already `In Progress` or `Done`), **STOP** — another agent owns it or it is finished. Do not duplicate work.
2. Confirm every `Depends-On` (WBS §20) shows `Done` on the board (`scripts/board.sh status <dep-issue>`), per RULE-2.
3. Claim the work: `scripts/board.sh set <issue-number> "In Progress"` **and** flip the matching `WBS.md` status token to `IN-PROGRESS`. Do both in the same step.

**Post-flight — as work lands:**
4. When the PR opens, link the issue in the PR body (`Closes #<n>`).
5. When the PR is **merged AND every `TST-AC-*` / `TST-INV-*` is green AND Code Review approved** (RULE-3, RULE-10): `scripts/board.sh set <issue-number> Done` and flip `WBS.md` → `DONE`. (Closing the issue also auto-syncs the board to `Done`; setting it explicitly is idempotent and covers PRs that close issues indirectly.)
6. **Never** set `Done` on partial-green tests. `In Progress` is the honest status until every gate is green.

Status ↔ WBS mapping: `Todo` ← {`BLOCKED`,`READY`,`STAGE-GATED`} · `In Progress` ← `IN-PROGRESS` · `Done` ← `DONE`. The board has three columns; `WBS.md` carries the finer distinction (e.g. `STAGE-GATED` vs `BLOCKED`).

The orchestrating agent owns Status transitions for components it dispatches. The `/sync-wbs` agent reconciles the board against CI evidence and surfaces the next `READY` wave. Use `scripts/board.sh` — never hand-edit the board through ad-hoc `gh` calls, so the transition is auditable and consistent.

---

*These rules are cross-referenced from CLAUDE.md §11 and the PR template.*
