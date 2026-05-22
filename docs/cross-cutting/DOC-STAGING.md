# DOC-STAGING — Per-language staging reference

**Owner:** Documentation Manager Agent
**Status:** ACTIVE (Phase 0 output)
**Source of truth:** `PLAN.md §"Phase staging — the sequencing observation"`, `SDD.md §11`, `WBS.md §13`, `.claude/rules/04-staging.md`, `CLAUDE.md §7`.
**Invariant:** INV-6 (Algorithm 2 precision/recall claims are valid only for `(class, language)` pairs that have passed the CPG-fidelity gate; front-end-blocked pairs are reported as `front-end-blocked`, never as recall failures).

This document defines the staging gate (`CMP-CP-06`, CPG-fidelity), the Stage A → B → C → D promotion sequence, the per-`(class, language)` partition table, the `STAGE-GATED` status semantics, and the promotion workflow.

When this document conflicts with `PLAN.md` / `SDD.md` / `.claude/rules/04-staging.md`, those win and this is corrected.

---

## 1. Purpose

The IFDS/IDE analysis core over a uniform Code Property Graph (CPG) is the principal engineering deliverable of v3.2. Per-language CPG-fidelity dominates the schedule because the Joern (or proprietary) front-end quality varies sharply across languages, and a weak front-end silently degrades the Algorithm 2 recall claim on whichever language it touches. Treating all languages simultaneously would make the Algorithm 2 falsifier (`AC-CORE-01b`) meaningless: a "recall failure" on Ruby would be indistinguishable from a "the front-end did not see the call edge that the recall test depends on" failure.

The staging plan addresses this with a hard ordering:

1. A `(class, language)` pair is admitted into the Algorithm 2 benchmark **only after** the front-end for that language clears a CPG-fidelity gate (`CMP-CP-06`).
2. Pairs that have not cleared the gate are reported as **`front-end-blocked`**, never as recall failures.
3. Customer contracts state which `(class, language)` pairs are core-partition versus oracle-passthrough at signing, and are revisited per stage.

This is the per-language expression of the honest-labeling principle (`PLAN.md §"Honest-labeling ledger"`). It is INV-6.

---

## 2. Stage definitions

### Stage A — Java + Python

| Field | Value |
|---|---|
| **Languages** | Java, Python |
| **Front-end maturity** | Strongest of the supported languages; reference Joern targets. |
| **Prerequisites** | `CMP-CP-06` green for Java and Python. |
| **Core classes promoted** | `injection`, `path-traversal`, `ssrf`, `deserialization`. |
| **Algorithm 2 falsifier (TST-AC-CORE-01b)** | First meaningful here. |
| **Other detector classes** | Ship `oracle-passthrough` until their own stage / partition arrives. |
| **Gate task** | `T-STAGE-A-01` (`WBS.md §13`). |
| **Open CLAR** | None blocking. |

Stage A is the foundation that the entire honest-labeling ledger leans on. Until Stage A is `CMP-CP-05` green (core-partition byte-identical SARIF on Java + Python over the canary corpus), no later stage may begin.

### Stage B — JS / TS

| Field | Value |
|---|---|
| **Languages** | JavaScript, TypeScript |
| **Front-end maturity** | Strong but quirky (dynamic typing, framework heterogeneity). |
| **Prerequisites** | Stage A determinism-attested (`CMP-CP-05` green for Stage A) **AND** `CMP-CP-06` green for JS/TS. |
| **Core classes promoted** | All Stage-A classes plus `xss` (which is JS/TS-specific to the per-class table below). |
| **Gate task** | `T-STAGE-B-01` (`WBS.md §13`). |
| **Open CLAR** | None blocking. |

Stage B depends on Stage A by transitivity through CMP-CP-05: a Stage-A core-partition regression would invalidate the determinism claim that Stage B inherits. `/stage-gate` must verify both gates before approval.

### Stage C — Go

| Field | Value |
|---|---|
| **Languages** | Go |
| **Front-end maturity** | Joern's Go front-end is functional but weak on points-to / interface-dispatch. Without an investment, the call-edge recall threshold (`CLAR-CORP-02`: 85%) is unlikely to be met. |
| **Prerequisites** | `CMP-CP-06` green for Go. |
| **Front-end blocker** | `T-STAGE-C-FE-01` — Stage-C points-to / interface-dispatch investment (Andersen-style baseline as the default, richer as a stretch). Filed as `CLAR-FE-02` (DEFERRED — scoping decision required; see `WBS.md §17`). |
| **Gate task** | `T-STAGE-C-01` (`WBS.md §13`). |
| **Open CLAR** | **`CLAR-FE-02`** (DEFERRED — see `WBS.md §17`). |

Until `CMP-CP-06` passes for Go, every `(class, Go)` pair is `front-end-blocked`. Go findings still flow through `oracle-passthrough` engines (Semgrep, CodeQL where applicable) so customers are not left blind; they are simply not eligible for the core-partition guarantee.

### Stage D — Ruby + PHP

| Field | Value |
|---|---|
| **Languages** | Ruby, PHP |
| **Front-end maturity** | Joern coverage is lowest here. PHP's variable-function semantics and Ruby's `send`/`method_missing` extend the dynamic-dispatch surface substantially. |
| **Prerequisites** | `CMP-CP-06` green for Ruby and PHP. |
| **Front-end blocker** | `T-STAGE-D-FE-01` — likely proprietary front-end work (build vs buy vs delay is a business decision). Filed as `CLAR-FE-01` (DEFERRED — see `WBS.md §17`). |
| **Default during gating** | Ruby and PHP ship **oracle-passthrough only**, clearly partitioned, with no core-determinism claim. |
| **Gate task** | `T-STAGE-D-01` (`WBS.md §13`). |
| **Open CLAR** | **`CLAR-FE-01`** (DEFERRED — see `WBS.md §17`). |

Stage D is the most likely stage to remain `front-end-blocked` for the duration of v3.2. The customer-facing presentation must make this explicit: a Ruby finding under v3.2 is `oracle-passthrough` and carries the digest-stability + reproduction-rate guarantee, not (a).

---

## 3. CPG-fidelity gate criteria (CMP-CP-06)

Per `CLAR-CORP-02` resolution in `WBS.md §17` (RESOLVED 2026-05-23), the per-language thresholds on the curated CPG-fidelity corpus (`tests/corpora/cpg_fidelity/{language}/`) are:

| Metric | Threshold | Rationale |
|---|---|---|
| Parse success rate | ≥ 99.5% of files | `SDD.md CMP-CP-06`; the corpus must not be a parse-failure corpus. |
| Call-edge precision | ≥ 90% | `CLAR-CORP-02`; tighter than recall because the IFDS solver is precision-sensitive at the call boundary. |
| Call-edge recall | ≥ 85% | `CLAR-CORP-02`; below this, Algorithm 2 recall is dominated by front-end miss. |
| PDG dependence-edge recall | ≥ 80% | `CLAR-CORP-02`; PDG misses cause false negatives that look like spec gaps. |

The harness is `.github/workflows/stage-gate.yml` (job `cpg-fidelity`). It:

1. Verifies `tests/corpora/cpg_fidelity/{language}/corpus.lock` exists.
2. Runs the per-language `cpg_fidelity` benchmark via `pytest -k "cpg_fidelity and {language}"`.
3. Reads `tests/results/cpg_fidelity/{language}/latest.json` and asserts each threshold.
4. Emits `GATE-PASS` or `GATE-FAIL` with the failing metric names.

Threshold changes require a new CTO-approved `CLAR-CORP-02` resolution and a lockstep update of this document, `.claude/rules/04-staging.md`, and `.github/workflows/stage-gate.yml`.

---

## 4. (class, language) pair table

Verbatim from `.claude/rules/04-staging.md` ("(class, language) pair table"). Each cell names the partition the pair lives in at the indicated stage:

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

**Reading the table:**

- **`core`** — the IFDS/IDE engine is the active detector for this pair; findings carry `origin = deterministic-core`.
- **`core (after gate)`** — same as core, but only after `CMP-CP-06` passes for the language at that stage. Until then the pair is `front-end-blocked`.
- **`mixed/oracle`** — the detector emits both partitions (IFDS portion follows language staging, pattern portion is always oracle). Per-finding `origin` is set by `CMP-ORCH-03` (`AC-ORCH-03b`).
- **`oracle (CodeQL)`** — C/C++ memory-safety is permanently `oracle-passthrough` via CodeQL; port to core is `OOS-CC-01` (`WBS.md §18`).
- **`oracle`** — always oracle-passthrough; never enters the core path in v3.2.

The table is the source of truth for the partition contract in the customer ToS. Any addition or modification requires a new CTO-approved entry plus a lockstep update of `.claude/rules/04-staging.md` and this document.

---

## 5. Always oracle-passthrough throughout v3.2

The following pairs never enter the core path under v3.2, regardless of stage:

| Class | Reason | Source |
|---|---|---|
| `memory-safety` (C/C++) | C/C++ core port deferred. | `OOS-CC-01` (`WBS.md §18`, `SDD.md §12`); `.claude/rules/04-staging.md` |
| `secrets` | Deterministic in practice; Attestor-attested via the oracle pipeline; not theorem-covered. | `.claude/rules/04-staging.md` |
| `dep-cve` | External database lookup; not amenable to IFDS over the CPG. | `.claude/rules/04-staging.md` |

Customer contracts state these as `oracle-passthrough` with the digest-stability + reproduction-rate guarantee. The honest-labeling ledger lists them under "Empirical, labeled" (`PLAN.md §"Honest-labeling ledger"`), not under "Proven, conditional".

---

## 6. `STAGE-GATED` status semantics

A `CMP-*` with status `STAGE-GATED` is **not** blocked by a missing dependency. Per `.claude/rules/04-staging.md`:

- **`BLOCKED`** means: some `Depends-On` entry has not reached `DONE`. The fix is to unblock the dependency — to complete the upstream component, or to file a `CLAR-*` clarifying what blocks it.
- **`STAGE-GATED`** means: every `Depends-On` entry is `DONE`, but the component (or a particular `(class, language)` pair it ships) is waiting for a CPG-fidelity gate to pass. The fix is to advance the stage — to invest in the front-end, to expand the fidelity corpus, or to record a CTO decision deferring the stage.

**Never** treat `STAGE-GATED` as `BLOCKED` and hack around it (e.g., by skipping the gate check or by promoting a `front-end-blocked` pair into the Algorithm 2 benchmark). RULE-7 in `.claude/rules/00-global.md` forbids this.

---

## 7. Promotion workflow

### 7.1 `/stage-gate` agent

The `/stage-gate` agent (`.claude/commands/stage-gate.md`) approves Stage A → B → C → D transitions. Its workflow:

1. Verify that every Stage-X `CMP-*` has every `AC-*` green (`RULE-3`).
2. Verify that `CMP-CP-06` is green for every language in Stage X (per `.github/workflows/stage-gate.yml` artefacts).
3. Verify that `CMP-CP-05` is green on the Stage-X core partition (Attestor byte-identical SARIF).
4. Verify that the honest-labeling ledger entry in `PLAN.md §"Honest-labeling ledger"` matches what Stage X actually delivered.
5. Record the gate verdict in `WBS.md §13` and `CLAUDE.md §7` (the per-language staging gates table).
6. If any check fails, file a `CLAR-*` rather than approving.

### 7.2 `/cto` review

The CTO agent (`/cto`, `.claude/commands/cto.md`) approves any deviation from the staged order — e.g., promoting Stage C ahead of Stage B because of a customer commitment. Such promotions require:

1. A written rationale referencing the specific customer/business reason.
2. A documented acknowledgment of the inverted `CMP-CP-05` Stage A → Stage C dependency.
3. A new entry in the honest-labeling ledger describing the promotion as a `[STAGED]` exception.

Without `/cto` approval, the staged order in §2 is enforced.

### 7.3 Honest-labeling ledger update

On stage promotion, the ledger entry in `PLAN.md §"Honest-labeling ledger"` (under "Staged, not simultaneous") is updated to reflect the new per-language readiness. The update is reproduced in `WBS.md §13` as a status table (AC-driven, not prose — per `WBS.md §21 Definition of Done` item "Staging").

---

## 8. Front-end-blocked reporting (INV-6)

A `(class, language)` pair that fails `CMP-CP-06` is reported as **`front-end-blocked`**, never as a recall failure. Per `AC-CP-06a`:

- **Per-stage recall tables (TST-AC-CORE-01b)** include only gate-passing pairs. The recall number for a `front-end-blocked` pair is **not reported** because the recall claim would be conditioned on a precondition (the front-end seeing the relevant edges) that is known to be violated.
- **The honest-labeling ledger** must distinguish `[STAGED]` from `[EMPIRICAL]` / `[CONDITIONAL THEOREM]` claims. A pair under `[STAGED]` is documented as a future deliverable, not as a measured under-performer.
- **Customer contracts** state which pairs are `front-end-blocked` at signing, and quote the corresponding `oracle-passthrough` guarantee for those pairs (digest-stability + reproduction rate).

INV-6 is the schema/process-level expression of per-language honesty: a recall number is meaningful only when the gate has passed; the harness `.github/workflows/stage-gate.yml` is the empirical falsifier.

---

## 9. References

| Reference | Where defined |
|---|---|
| **INV-6** | `CLAUDE.md §3`, `SDD.md §2`, `.claude/rules/01-invariants.md` |
| **`CMP-CP-06`** | `SDD.md §10`, `AC-CP-06a/b` — CPG-fidelity gate harness |
| **`CMP-CORE-01 AC-CORE-01b`** | `SDD.md §6` — Algorithm 2 falsifier; only on gate-passing pairs |
| **`SDD.md §11`** | Staging plan (per-language sequencing constraint) |
| **`WBS.md §13`** | Phase 10 — Per-language staging overlay |
| **`WBS.md §17 CLAR-FE-01`** | Stage-D proprietary front-end (DEFERRED) |
| **`WBS.md §17 CLAR-FE-02`** | Stage-C points-to investment (DEFERRED) |
| **`WBS.md §17 CLAR-CORP-02`** | CPG-fidelity gate thresholds (RESOLVED 2026-05-23) |
| **`WBS.md §18 OOS-CC-01`** | C/C++ core port out of scope |
| **`PLAN.md §"Phase staging — the sequencing observation"`** | Verbatim staging statement |
| **`PLAN.md §"Honest-labeling ledger"`** | The `[STAGED]` claim class |
| **`CLAUDE.md §7`** | Per-language staging gates summary table |
| **`.claude/rules/04-staging.md`** | Operational staging rules; this document expands them |
| **`.claude/rules/00-global.md` RULE-7** | No `(class, language)` enters Algorithm 2 benchmarking before `CMP-CP-06` green |
| **`.github/workflows/stage-gate.yml`** | The CPG-fidelity gate harness (CI implementation) |
| **`DOC-PARTITION.md`** | Determinism partition reference; pairs determine partition |
| **`DOC-RUNBOOK.md`** | Operations runbook |

---

*End of DOC-STAGING. Updates to the (class, language) table require a CTO-approved decision recorded in WBS.md §17 and a lockstep change to `.claude/rules/04-staging.md`.*
