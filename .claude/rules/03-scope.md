# Scope rules — Scanipy v3.2

This file defines what is in scope and out of scope for v3.2, and the protocol for handling scope ambiguity.

---

## In-scope work

Anything with a `CMP-*` identifier in `SDD.md` or `WBS.md` is in scope. The complete list spans §3 through §16 of `WBS.md`.

Scope is further constrained by:
- **Staging**: CMP-* items tagged `Stage B/C/D` cannot start until their stage gate is met.
- **Dependencies**: `WBS.md §20` dependency DAG; no CMP can start before its `Depends-On` list is DONE.
- **CLAR-* items**: open clarification items block the components that depend on them.

---

## Out-of-scope register (v3.2)

Source: `SDD.md §12` and `WBS.md §18`. Do not schedule any task that touches these items.

| OOS-ID | Item | Source |
|---|---|---|
| OOS-CI-AGENT-01 | CI-agent / on-prem runner | SDD §12 |
| OOS-CONTAINER-SCAN-01 | Container-image scanning | SDD §12 |
| OOS-BINARY-01 | Binary-only analysis | SDD §12 |
| OOS-IDE-01 | IDE plugin | SDD §12 |
| OOS-CC-01 | C/C++ memory-safety port to core (remains oracle via CodeQL) | SDD §11 |
| OOS-LLM-DET-01 | Any LLM influence on `deterministic-core` findings outside a pinned `S` | SDD INV-3 |
| OOS-ENV-INDEP-01 | Environment-independent determinism | PLAN §"Central correction" |

---

## How to file a CLAR-* item

Use when: a required input, threshold, owner assignment, or vendor choice is missing from `PLAN.md` / `SDD.md` and you cannot proceed without a decision.

**Format** (append to `WBS.md §17`):
```markdown
| CLAR-<DOMAIN>-<NN> | <one-line question> | <blocks: CMP-* list> | <target resolution phase> |
```

**Domain codes:**
- `DEPLOY` — infrastructure / substrate choices
- `CORP` — corpus / data choices
- `PARAM` — algorithm parameter defaults
- `SLA` — service level targets
- `FE` — front-end / toolchain investments
- `OWNER` — ownership assignments
- `MIGRATION` — legacy data migration

**After filing:** notify the CTO Agent (`/cto`) with the CLAR-ID so it can be resolved before the dependent phase starts.

---

## How to emit an OOS-* item

Use when: a derived task implies one of the out-of-scope items above and you need to record the deflection for traceability.

**Format** (append to `WBS.md §18`):
```markdown
| OOS-<DOMAIN>-<NN> | <item being deflected> | <source: SDD §X / PLAN §Y> |
```

Do not create a work package for it. The OOS-* entry is the final record.

---

## Scope creep signals

A task is drifting out of scope if it involves any of:
- Scanning a running container for vulnerabilities (→ OOS-CONTAINER-SCAN-01)
- Running analysis on a compiled binary without source (→ OOS-BINARY-01)
- An IDE extension that surfaces findings in the editor (→ OOS-IDE-01)
- An agent that runs inside CI and auto-remediates (→ OOS-CI-AGENT-01)
- Claiming determinism across different `Env` values (→ OOS-ENV-INDEP-01)
- Having an LLM output directly change `origin` or `slice_fingerprint` of a finding (→ OOS-LLM-DET-01)
- Porting the C/C++ memory-safety detector from CodeQL to IFDS in v3 (→ OOS-CC-01)

When you notice scope creep: stop, emit the OOS-* entry, and inform the CTO Agent.

---

*Cross-reference: SDD.md §12, WBS.md §17–18, CLAUDE.md §14*
