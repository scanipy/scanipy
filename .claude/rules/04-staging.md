# Per-language staging rules — Scanipy v3.2

Source: `PLAN.md §"Phase staging"`, `SDD.md §11`, `WBS.md §13`.

The IFDS/IDE core is the principal deliverable. Per-language CPG fidelity dominates the schedule. A `(class, language)` pair is benchmarked under Algorithm 2 only after it independently clears the **CPG-fidelity gate** (`CMP-CP-06`).

---

## Stage definitions

### Stage A — Java + Python

- **Prerequisite:** `CMP-CP-06` green for Java and Python.
- **Core classes promoted:** `injection`, `path-traversal`, `ssrf`, `deserialization`.
- **Algorithm 2 falsifier (TST-AC-CORE-01b)** is first meaningful here.
- **Other classes** ship `oracle-passthrough` until their own stage.
- **Gate task:** `T-STAGE-A-01`.

### Stage B — JS/TS

- **Prerequisite:** Stage A determinism-attested (`CMP-CP-05` green for Stage A) **and** `CMP-CP-06` green for JS/TS.
- **Gate task:** `T-STAGE-B-01`.

### Stage C — Go

- **Prerequisite:** `CMP-CP-06` green for Go.
- **Blocker:** Go front-end requires a points-to / interface-dispatch investment (`T-STAGE-C-FE-01`). File as `CLAR-FE-02` until scoped.
- **Gate task:** `T-STAGE-C-01`.

### Stage D — Ruby + PHP

- **Prerequisite:** `CMP-CP-06` green for Ruby and PHP.
- **Likely blocker:** Joern front-end maturity; may require proprietary front-end work (`T-STAGE-D-FE-01`, filed as `CLAR-FE-01`).
- Until the gate passes, Ruby and PHP ship **oracle-passthrough only** (clearly partitioned).
- **Gate task:** `T-STAGE-D-01`.

### Always oracle-passthrough throughout v3.2

- **C/C++ memory-safety:** CodeQL only. Port to core is `OOS-CC-01`.
- **`secrets`, `dep-cve`:** oracle-passthrough (deterministic in practice, Attestor-attested, not theorem-covered).
- **`crypto-misuse`, `authn-authz`:** `mixed`. The IFDS/IDE portion follows language staging; the pattern portion is always oracle.

---

## CPG-fidelity gate criteria (CMP-CP-06)

For language `L`, the following thresholds must be met on the curated per-language fidelity corpus (`CMP-CORP-CPG-{L}`):

| Metric | Threshold |
|---|---|
| Parse success rate | ≥ 99.5% of files |
| Call-edge precision | ≥ 90% (CLAR-CORP-02 RESOLVED 2026-05-23) |
| Call-edge recall | ≥ 85% (CLAR-CORP-02 RESOLVED 2026-05-23) |
| PDG dependence-edge recall | ≥ 80% (CLAR-CORP-02 RESOLVED 2026-05-23) |

A language that fails is reported **`front-end-blocked`**, never as a recall failure (INV-6).

---

## (class, language) pair table

| Class | Stage A (Java+Py) | Stage B (JS/TS) | Stage C (Go) | Stage D (Ruby+PHP) |
|---|---|---|---|---|
| injection | core | core | core (after gate) | core (after gate) |
| path-traversal | core | core | core (after gate) | core (after gate) |
| ssrf | core | core | core (after gate) | core (after gate) |
| deserialization | core | core | core (after gate) | core (after gate) |
| xss | oracle | core (after gate) | core (after gate) | core (after gate) |
| crypto-misuse | mixed/oracle | mixed/oracle | mixed/oracle | oracle |
| authn-authz | mixed/oracle | mixed/oracle | mixed/oracle | oracle |
| memory-safety (C/C++) | oracle (CodeQL) | oracle | oracle | oracle |
| secrets | oracle | oracle | oracle | oracle |
| dep-cve | oracle | oracle | oracle | oracle |

---

## What `STAGE-GATED` means

A CMP-* with status `STAGE-GATED` is not blocked by a missing dependency; it is waiting for a language's CPG-fidelity gate to pass. Do not treat it as `BLOCKED` (dependency failure) — the fix is to advance the stage, not to unblock a dependency.

---

*Cross-reference: SDD.md §11, WBS.md §13 + §20, CLAUDE.md §7, PLAN.md §"Phase staging"*
