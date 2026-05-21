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

Every PR requires Code Review Agent approval. Approval is conditional on the PR checklist being fully checked. An approval without a checked checklist is not valid.

---

*These rules are cross-referenced from CLAUDE.md §11 and the PR template.*
