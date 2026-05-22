# DOC-ALGS — Algorithm reference suite

**Owner:** Documentation Manager Agent
**Status:** ACTIVE (Phase 0 cross-cutting deliverable)
**Source-of-truth lineage:**

- `PLAN.md §"Algorithm 1 — Incremental CPG maintenance"`
- `PLAN.md §"Algorithm 2 — Detection core as IFDS/IDE"`
- `PLAN.md §"Algorithm 3 — Refactor-stable finding fingerprint"`
- `PLAN.md §"Algorithm 4 — Detector scheduling (heuristic)"`
- `PLAN.md §"Algorithm 5 — Canonical CPG ordering, and the item-4 provenance rename"`
- `PLAN.md §"Algorithm 6 — Spec inference with an anytime-valid precision gate"`
- `PLAN.md §"Per-algorithm summary"` (precondition/owner/degradation/falsifier table)
- `SDD.md CMP-SNAP-02` (Alg 1 owner), `CMP-CORE-01` (Alg 2), `CMP-CORE-02` (Alg 3), `CMP-ORCH-02` (Alg 4), `CMP-CORE-03` (Alg 5), `CMP-TRI-02` (Alg 6)
- `SDD.md §2 INV-1..INV-6`
- `WBS.md §6..12` (per-component task lists)
- `.claude/rules/01-invariants.md`, `.claude/rules/04-staging.md`, `.claude/rules/05-determinism.md`

This document is the **canonical reference** for the six algorithms that constitute the analytical pipeline of Scanipy v3.2. Each algorithm section follows a fixed template. Pseudocode and formal statements are **quoted verbatim** from `PLAN.md` wherever possible; where `PLAN.md` states a formal claim as prose, this document presents the prose without procedural re-derivation. Procedural form of every algorithm lives in the owning component's `DOC-CMP-*`.

Where this document and the source-of-truth disagree, the source-of-truth wins; file a `CLAR-*` against `WBS.md §17` rather than editing this document inline.

---

## 1. Purpose

The six algorithms below are the load-bearing analytical machinery of Scanipy v3.2:

- **Algorithm 1** — Incremental CPG maintenance. Owner of property (b) (incremental computability).
- **Algorithm 2** — IFDS/IDE Tabulation. Owner of property (a) (reproducibility) on the deterministic-core partition.
- **Algorithm 3** — Slice fingerprint. Owner of cross-scan and cross-refactor finding identity.
- **Algorithm 4** — Heuristic scheduler `SNAP-SCHED-H`. Owner of the p95 latency target.
- **Algorithm 5** — Canonical CPG ordering. Owner of `cpg_order_hash` and the canonical-iff-strong contract (`INV-5`).
- **Algorithm 6** — Anytime-valid e-process spec gate. Owner of the spec-acceptance guarantee under unbounded optional continuation.

Together they implement `F : (source, S, Policy ; Env) → FindingSet`. The reproducibility theorem (a) is **conditional** on Alg 1's closed-world precondition (owned by `CW-DETECT` / `CMP-SNAP-03`) and Alg 2's distributivity precondition (owned by the combinator DSL / `CMP-DET-01`); see `DOC-DSL` and `.claude/rules/01-invariants.md §INV-4`.

### 1.1 Per-algorithm template

Each `§ Algorithm N` below populates:

- **Name + one-line statement** (verbatim from `PLAN.md`).
- **Owner component** (`CMP-*`).
- **Formal inputs and outputs** (typed).
- **Algorithm statement** (formula + prose, quoted from `PLAN.md` where stated; procedural pseudocode appears only where `PLAN.md` itself provides one).
- **Complexity** (time, space) with assumptions.
- **Invariants discharged** (cross-link to DOC-INV / `.claude/rules/01-invariants.md`).
- **Failure / fallback modes**.
- **Tests** (`TST-AC-*` + `TST-INV-*`).
- **Known sensitivities** (preconditions, environment dependencies).
- **Honest-labelling status** (`CONDITIONAL THEOREM | EMPIRICAL | STAGED | UNCONDITIONAL`).

---

## 2. Algorithm 1 — Incremental CPG maintenance

### 2.1 One-line statement

> Compute `G'`, `ΔG`, and `AFFECTED` from a parent snapshot when the closed-world precondition holds; otherwise apply the points-to-bounded cone with full-reparse fallback. — `PLAN.md §"Algorithm 1"`.

### 2.2 Owner component

`CMP-SNAP-02` (`WBS.md §7`). Precondition owner: `CMP-SNAP-03` (`CW-DETECT`).

### 2.3 Formal inputs and outputs

```
Inputs:
    parent_snapshot   : Snapshot              -- prior CPG + reverse-symbol index + dyn call graph
    current_commit    : CommitSha             -- new source commit
    cw_verdict        : {closed-world, degraded, full-reparse}
                       -- from CMP-SNAP-03 over (source@current_commit)
    θ_cone            : float                  -- default 0.25 (CLAR-PARAM-01)
    θ_files           : float                  -- default 0.4  (CLAR-PARAM-01)

Outputs:
    new_snapshot      : Snapshot              -- G', persisted via CMP-SNAP-01
    ΔG                : GraphDelta             -- structural delta vs parent
    AFFECTED          : Set<NodeId>            -- entry points whose summaries are invalidated
    precondition_status : {closed-world, degraded, full-reparse}
```

### 2.4 Algorithm statement (verbatim from `PLAN.md`)

**Closed-world case [CONDITIONAL THEOREM], precondition owned by `CW-DETECT`:**

> Call resolution is CHA over a hierarchy closed under the analysis scope. Then:
>
> `AFFECTED = changed-decls ∪ reverse-symbol-closure(changed-decls) ∪ direct-callers(changed-signatures) ∪ CHA-cone(changed-types)`,
>
> and incremental re-evaluation visits `O(|AFFECTED| + frontier)` nodes with `frontier` the constant-bounded boundary summary-edge set; `O(Δ)` with `Δ = Σ|changed function| + |direct callers| + |CHA-cone of changed types|`.

**Open-world degradation [EMPIRICAL]:**

> On a `CW-DETECT` not-closed-world verdict: mark the dynamic edge conservatively imprecise (recorded in provenance), use an Andersen-style points-to-bounded cone, and fall back to full reparse when the bounded cone exceeds `θ_cone` (default 0.25) of the call graph or `|changed files|/|files| > θ_files` (default 0.4). The fallback-rate target ≤15% is a target for `CW-DETECT`'s combined TP+FP routing rate.

### 2.5 Complexity

| Path | Time | Space | Assumption |
|---|---|---|---|
| Closed-world incremental | `O(Δ)` = `O(|AFFECTED| + frontier)` | `O(|G'|)` | CHA closed-world precondition holds (owned by `CW-DETECT`). |
| Open-world bounded cone | `O(|cone(Δ)|)` where `|cone| ≤ θ_cone · |G'|` | `O(|G'|)` | Andersen points-to bound. |
| Full reparse | `O(|G'|)` | `O(|G'|)` | `|cone| > θ_cone · |G'|` or `|changed files|/|files| > θ_files`. |

### 2.6 Invariants discharged

- **INV-2** — the new snapshot row stamps `env_digest` and the analysis is pinned to it.
- Routes `(closed-world | degraded | full-reparse)` to provenance; the precondition status is recorded for every snapshot (`AC-SNAP-01b`).

### 2.7 Failure / fallback modes

- `CW-DETECT` returns `not-closed-world` → degraded (points-to cone).
- Points-to cone exceeds `θ_cone · |G'|` or file-change ratio exceeds `θ_files` → full reparse.
- **Soundness leak case** (`CW-DETECT` false-negative): the snapshot is processed on the closed-world path and ships `origin=deterministic-core` incorrectly. Detected by the **differential reflection oracle** (`CMP-SNAP-04`) asynchronously; on disagreement, affected findings are retroactively re-partitioned to `oracle-passthrough` (`DOC-PROVENANCE §4`).

### 2.8 Tests

| Test | Kind | Maps to |
|---|---|---|
| `TST-AC-SNAP-02a` | `[CONDITIONAL THEOREM]` | κ-bound regression on ≥1,000 closed-world commits. |
| `TST-AC-SNAP-02b` | `[EMPIRICAL]` | Open-world median ≥ 5×, p95 ≥ 2×, fallback ≤ 15%. |
| `TST-AC-SNAP-02c` | `[UNIT]` | Function-granularity reparse preserves node IDs for unchanged declarations. |
| `TST-AC-SNAP-03a` | `[FALSIFIER]` | Zero false negatives on the reflection corpus (release blocker; `CW-DETECT` ownership of the precondition). |
| `TST-AC-SNAP-04a..c` | `[FALSIFIER]` + `[INVARIANT]` | Differential oracle detects seeded FN; re-partitions; logs to provenance. |

### 2.9 Known sensitivities

- **CW-DETECT verdict.** Algorithm 1's correctness is conditional on the CW-DETECT verdict. Without the falsifier (`AC-SNAP-03a`) + differential oracle (`AC-SNAP-04a`), a CW-DETECT FN is invisible — it reproduces under same-source re-run (the canary test in `CMP-CP-05` re-runs the same wrong path).
- **`θ_cone`, `θ_files`**. Default values per `CLAR-PARAM-01` (RESOLVED) are 0.25 and 0.4 respectively. The fallback-rate target ≤15% is on the combined TP+FP routing rate of CW-DETECT, **not** the true reflection rate.

### 2.10 Honest-labelling status

`CONDITIONAL THEOREM` (closed-world, conditional on `CW-DETECT` precondition) + `EMPIRICAL` (open-world speedup). Both labels per-class and per-finding are stamped into `provenance_records.claim_label` (`DOC-PROVENANCE §5`).

---

## 3. Algorithm 2 — IFDS/IDE Tabulation

### 3.1 One-line statement

> Each taint-style class is an IFDS instance with per-class flow functions drawn from the distributive-by-construction combinator DSL; quantitative classes (crypto key-size, race windows) use IDE with lattice-valued environment transformers over the same machinery. — `PLAN.md §"Algorithm 2"`.

### 3.2 Owner component

`CMP-CORE-01` (`WBS.md §8`). Precondition owner: `CMP-DET-01` (combinator DSL closure check).

### 3.3 Formal inputs and outputs

```
Inputs:
    cpg             : CPG                    -- from CMP-SNAP-02 / CMP-SNAP-01
    canonical_order : Vec<NodeId>            -- from CMP-CORE-03 (Algorithm 5)
    spec            : Spec                   -- DSL-conformant (CMP-DET-01)
    affected        : Set<NodeId> | ⊤        -- incremental restriction (Algorithm 1)
                                             -- ⊤ means "no restriction" (full run)

Outputs:
    solution        : Map<SinkNode, Set<TaintFact>>   -- meet-over-all-valid-paths
    witnesses       : Map<(SinkNode, TaintFact), Path> -- realizing path per pair
    solution_hash   : Sha256                          -- pre-serialization hash
```

### 3.4 Algorithm statement (verbatim from `PLAN.md`)

> **[CONDITIONAL THEOREM] Determinism of the solution.** *Precondition (owned by the DSL closure check):* flow functions lie within the distributive, finite-domain combinator DSL. *Then:* Tabulation computes the unique meet-over-all-valid-paths solution independent of worklist order (RHS'95); the (sink-fact, realizing-path) set is a deterministic function of the exploded supergraph. Byte-identical serialization is supplied by Algorithm 5's enumeration order; together they license (a) on the core partition.

The procedural form is the **Reps–Horwitz–Sagiv Tabulation algorithm** (POPL 1995): build the exploded supergraph from `(cpg, spec)`, compute reusable procedure summaries by fixpoint over distributive transfer functions on the finite fact domain, and read out the meet-over-all-valid-paths solution at each sink. The IDE extension (Sagiv–Reps–Horwitz 1996) replaces fact sets with lattice-valued environment transformers for quantitative classes. The procedural details live in `DOC-CMP-CORE-01` (forthcoming).

### 3.5 Complexity

| Metric | Bound | Source |
|---|---|---|
| Time (worst case) | `O(|E| · |D|³)` | RHS'95; `|E|` = supergraph edges, `|D|` = fact-domain size. |
| Time (real taint, empirical) | near-linear in program size | `PLAN.md §"Algorithm 2"` (`[EMPIRICAL]`). |
| Space | `O(|E| · |D|²)` | summary table. |
| Incremental | `O(|AFFECTED| · |D|³)` worst case | invalidates only `AFFECTED` summaries (Alg 1). |

### 3.6 Invariants discharged

- **INV-4** — distributivity precondition owned by the DSL closure check (`CMP-DET-01`); see `DOC-DSL §3, §7`.
- **INV-6** — recall claim valid only on CPG-fidelity-gate-passing `(class, language)` pairs (per `CMP-CP-06`).

### 3.7 Failure / fallback modes

- **DSL escape** → spec rejected at registration; never reaches Algorithm 2 (`AC-DET-01b`, `T-CMP-DET-02-02`).
- **Front-end fidelity failure** (e.g. Joern Go gap) → `(class, language)` pair reported `front-end-blocked` per `INV-6`, never as a recall failure (`AC-CP-06a`).

### 3.8 Tests

| Test | Kind | Maps to |
|---|---|---|
| `TST-AC-CORE-01a` | `[CONDITIONAL THEOREM]` | 100 canary repos × 5 re-runs identical pre-serialization solution hashes. Release blocker. |
| `TST-AC-CORE-01b` | `[EMPIRICAL]` | Per `(class, language)` recall ≥ Semgrep-default + 10pp at equal precision. **Only on gate-passing pairs**. |
| `TST-AC-CORE-01c` | `[UNIT]` | Incremental re-tabulation visits only `AFFECTED` entry points + transitive callers. |
| `TST-AC-DET-01a` | `[UNIT]` (Gate 1) | DSL distributivity proof obligations for every primitive + sanctioned composition. |
| `TST-INV-6-CORE-01` | `[INVARIANT]` | Recall claim only stated on gate-passing pairs (per-language honesty). |

### 3.9 Known sensitivities

- **DSL membership.** Algorithm 2's determinism theorem depends on every loaded spec lying within the DSL. The combinator DSL closure check (`DOC-DSL §7`) is the operational discharge.
- **Algorithm 5's canonical order.** Byte-identical serialization is supplied by Algorithm 5's enumeration order over the same-source CPG; without canonical order, two runs producing the same `solution` would serialize differently and falsify `AC-CP-05a`. Algorithm 5 is therefore a hard dependency.
- **Per-language CPG fidelity (`CMP-CP-06`).** The recall claim is **STAGED** per language and is not meaningful on a language whose front-end has not passed the fidelity gate (`INV-6`).

### 3.10 Honest-labelling status

`CONDITIONAL THEOREM` for determinism on the core partition + `EMPIRICAL` for recall thresholds + `STAGED` per `(class, language)` per `INV-6`. The per-finding `provenance_records.claim_label` is `CONDITIONAL_THEOREM` for `engine ∈ {ifds, ide}` on a gate-passing pair, `STAGED` on a pair not yet gate-passing.

---

## 4. Algorithm 3 — Slice fingerprint (refactor-stable)

### 4.1 One-line statement

> Backward interprocedural slice along the witness, normalized by named refactor-invariance passes, canonicalized under the `(B, T)` budget with a `weak` witness-edge-sequence-hash fallback. — `PLAN.md §"Algorithm 3"`.

### 4.2 Owner component

`CMP-CORE-02` (`WBS.md §8`).

### 4.3 Formal inputs and outputs

```
Inputs:
    witness         : Path                   -- realizing path from Algorithm 2
    cpg             : CPG
    B               : int                    -- 2^16 (default)  (CLAR-PARAM-01)
    T               : Duration               -- 200 ms (default)(CLAR-PARAM-01)

Outputs:
    slice_fingerprint : Sha256
    fingerprint_class : {strong, weak}        -- INV-5 indicator
```

### 4.4 Algorithm statement (verbatim from `PLAN.md`)

> Construction and per-refactor invariance proofs are unchanged from v3.1 (α-renaming for locals; PDG-only for formatting; canonical topological sort for independent reordering; **summary-inlining normalization** for extract/inline-method, proven for pure extract only; **FQN normalization** for file-move/package-rename). Ceiling and bounded fallback unchanged: 2-WL to fixpoint, then individualization-refinement under hard budget `(B, T)` (defaults 2¹⁶ search-tree nodes, 200 ms); on exhaustion, fall back to the `O(|witness|)`-capped witness-edge-sequence hash and flag `fingerprint_class = weak` (baseline never auto-suppresses a `weak` finding across a refactor).

**Named normalization passes** (in order):

1. α-renaming for locals.
2. PDG-only formatting (drops formatting-only AST decoration).
3. Canonical topological sort for independent reordering.
4. Summary-inlining normalization for extract/inline-method (pure extract only).
5. FQN normalization for file-move / package-rename.

### 4.5 Complexity

| Path | Time | Space |
|---|---|---|
| Strong (2-WL + bounded IR) | bounded by `(B, T)` budget | `O(|slice|)` |
| Weak (witness-edge-sequence hash) | `O(|witness|)` | `O(|witness|)` |

`[EMPIRICAL]` `strong`-success-within-budget ≥ 98%; `weak`-fallback rate measured and reported (publish threshold 5% per `CLAR-PARAM-03`, RESOLVED).

### 4.6 Invariants discharged

- **INV-5** — `fingerprint_class ∈ {strong, weak}` stamped on every finding; baseline never auto-suppresses a `weak` finding across a refactor (`AC-CORE-02c`, `AC-FND-02a`).

### 4.7 Failure / fallback modes

- `(B, T)` budget exhaustion → `weak` fallback (`O(|witness|)` witness-edge-sequence hash). Recorded.
- Aliasing-changing extract / genuine fix → fingerprint flips (`AC-CORE-02b`).
- Published `weak`-rate above 5% → canonicalizer redesign trigger (`CLAR-PARAM-03`).

### 4.8 Tests

| Test | Kind | Maps to |
|---|---|---|
| `TST-AC-CORE-02a` | `[FALSIFIER]` | Fingerprint invariant under each named refactor on 50 seeded findings. |
| `TST-AC-CORE-02b` | `[FALSIFIER]` | Fingerprint changes on a genuine fix + aliasing-changing extract. |
| `TST-AC-CORE-02c` | `[EMPIRICAL] + [INVARIANT]` | `weak`-rate < 5%; `weak` never auto-suppressed across a refactor. |
| `TST-INV-5-CORE-02` | `[INVARIANT]` | Weak-class semantics preserved end-to-end. |

### 4.9 Known sensitivities

- **Pure-extract limitation.** Summary-inlining normalization is proven only for pure extract. Impure extracts (those that change aliasing or order of side effects) **must** flip the fingerprint per `AC-CORE-02b`; the design honors this by not normalizing them.
- **`(B, T)` budget shape.** Budget exhaustion is bounded above by `B = 2^16` search-tree nodes and `T = 200 ms`. Higher budgets shift `weak`-rate down at the cost of latency; the published rate gates a canonicalizer redesign.

### 4.10 Honest-labelling status

`CONDITIONAL THEOREM` (per-refactor invariance, conditional on the named normalization passes) + `EMPIRICAL` (strong-success rate; weak-fallback rate). Bounded fallback time-cap is `UNCONDITIONAL`.

---

## 5. Algorithm 4 — Heuristic scheduler `SNAP-SCHED-H`

### 5.1 One-line statement

> Snapshot-affinity grouping (amortize CPG load `L`), independent-moldable 2-approx allotment as a heuristic seed only, LPT list-scheduling with dependence-aware deferral, policy-gating classes first. — `PLAN.md §"Algorithm 4"`.

### 5.2 Owner component

`CMP-ORCH-02` (`WBS.md §9`).

### 5.3 Formal inputs and outputs

```
Inputs:
    scan_requests   : Stream<ScanRequest>
    m               : int             -- provisioned worker count
    cpg_load_cost   : float           -- L per snapshot (amortized)
    work_estimates  : Map<DetectorId, Duration>

Outputs:
    schedule        : Map<JobId, (WorkerId, StartTime)>
```

### 5.4 Algorithm statement (verbatim from `PLAN.md`)

> `SNAP-SCHED-H` is a heuristic; ρ≈2 is cited only as the bound for the idealized independent-moldable relaxation used as a heuristic seed, explicitly not a guarantee for the actual moldable-DAG-with-setup problem. Sole promise: an **[EMPIRICAL]** p95 < 30 min at provisioned `m`, with a defined response on miss (re-fit work-estimate regression, raise `m`, or re-price). Result-independence of scheduling remains guaranteed via IFDS order-independence and is Attestor-cross-checked.

Component steps (per `SDD.md CMP-ORCH-02` + `WBS.md §9`):

1. Snapshot-affinity grouping to amortize CPG load `L`.
2. Independent-moldable 2-approx allotment as a heuristic seed (ρ≈2 is the relaxation bound, **never** a guarantee for the real problem).
3. LPT list-scheduling with dependence-aware deferral.
4. Policy-gating classes (those a customer policy elevates) scheduled first.

### 5.5 Complexity

No formal bound is claimed for the real moldable-DAG-with-setup problem. The only stated metric is `[EMPIRICAL]` p95 end-to-end scan latency < 30 min at provisioned `m`.

### 5.6 Invariants discharged

- **None directly.** But `AC-ORCH-02b` (schedule-invariance: different schedules → identical deterministic-core findings) is the **operational** invariant linking Algorithm 4 to `INV-1` — scheduling never reaches into the SARIF blob. Attestor (`CMP-CP-05`) cross-checks this.

### 5.7 Failure / fallback modes

- p95 missed → re-fit work-estimate regression, raise `m`, or re-price. No theoretical re-derivation; an operational response with three named remediations (`PLAN.md §"Algorithm 4"`).

### 5.8 Tests

| Test | Kind | Maps to |
|---|---|---|
| `TST-AC-ORCH-02a` | `[EMPIRICAL]` | Production-shaped replay p95 < 30 min. |
| `TST-AC-ORCH-02b` | `[INVARIANT]` | Different schedules produce identical `deterministic-core` findings. |
| `TST-AC-ORCH-02c` | `[UNIT]` (doc-link grep) | ρ≈2 appears in documentation only as a relaxation bound, never as a guarantee. |

### 5.9 Known sensitivities

- **`m` provisioning.** The p95 target is `[EMPIRICAL]` at a provisioned `m`. Under-provisioning trades into the published miss-response.
- **Work-estimate regression.** The work-estimate model is one of the three remediations on a p95 miss; quality of the model drives schedule quality.

### 5.10 Honest-labelling status

`EMPIRICAL` only. No theorem is claimed for the scheduler. ρ≈2 is a relaxation seed, not a guarantee.

---

## 6. Algorithm 5 — Canonical CPG ordering

### 6.1 One-line statement

> 2-WL refinement, bounded individualization-refinement under hard `(B, T)` budget, stable-order fallback keyed on `(declaration-hash, structural-path-from-declaration-root, edge-kind)` on budget exhaustion. — `PLAN.md §"Algorithm 5"`.

### 6.2 Owner component

`CMP-CORE-03` (`WBS.md §8`).

### 6.3 Formal inputs and outputs

```
Inputs:
    cpg             : CPG
    B               : int             -- 2^16 (default)  (CLAR-PARAM-01)
    T               : Duration        -- 200 ms (default)(CLAR-PARAM-01)

Outputs:
    canonical_order : Vec<NodeId>      -- deterministic enumeration of cpg
    cpg_order_hash  : Sha256           -- INV-5: stamped with conditional annotation
    fingerprint_class : {strong, weak} -- canonical iff strong  (mirrors Alg 3)
```

### 6.4 Algorithm statement (verbatim from `PLAN.md`)

> Construction unchanged: seed labels `(kind, operator/literal, resolved FQN, sorted incident-edge-kind multiset)`; 2-WL to fixpoint; residual symmetric classes broken by enclosing-declaration canonical order then bounded individualization-refinement under the shared `(B, T)` budget; on exhaustion, a stable order keyed by `(declaration-hash, structural-path-from-declaration-root, edge-kind)` — total, deterministic, parse-order-independent, but **not a true canonical form**.

> **Item-4 fix (labeling only; construction is correct as is).** The provenance field formerly named "canonical CPG hash" is renamed `cpg_order_hash` and is recorded with an explicit annotation: `canonical iff fingerprint_class = strong`.

### 6.5 Complexity

| Path | Time | Space |
|---|---|---|
| Strong (2-WL + bounded IR within `(B, T)`) | bounded by `(B, T)` | `O(|G|)` |
| Weak (stable-order fallback) | `O(|G| · log|G|)` | `O(|G|)` |

`[EMPIRICAL]` budget-exhaustion rate on real code < 1% (`AC-CORE-03b`, `CLAR-PARAM-01` confirms defaults).

### 6.6 Invariants discharged

- **INV-5** — `cpg_order_hash` is stamped with the conditional annotation `canonical iff fingerprint_class = strong` everywhere it appears (provenance record, SARIF properties, auditor export). See `DOC-PROVENANCE §2.1, §8.2` and `AC-CORE-03c, AC-FND-03b`.

### 6.7 Failure / fallback modes

- `(B, T)` budget exhaustion → stable-order fallback (`weak`-class). Same-source determinism still holds (the fallback is deterministic), but the order is not canonical across isomorphic-but-differently-written programs.
- The fallback annotates the resulting `cpg_order_hash` as conditional via the persisted `fingerprint_class = weak` and the textual annotation; `INV-5` is the operational discipline.

### 6.8 Tests

| Test | Kind | Maps to |
|---|---|---|
| `TST-AC-CORE-03a` | `[UNIT]` | CFI-style symmetric inputs terminate within `(B, T)` with deterministic same-source order. |
| `TST-AC-CORE-03b` | `[EMPIRICAL]` | Budget-exhaustion rate on real code < 1%. |
| `TST-AC-CORE-03c` | `[INVARIANT]` | Persisted hash field named `cpg_order_hash`; conditional annotation present everywhere. |
| `TST-INV-5-CORE-03` | `[INVARIANT]` | `cpg_order_hash` annotation invariant. |

### 6.9 Known sensitivities

- **2-WL ceiling.** The Cai–Fürer–Immerman (1992) result is the theoretical ceiling for 2-WL canonicalization. CFI-hard graphs do not admit a 2-WL canonical form; they hit individualization-refinement, then fall back to `weak`. The 2-WL ceiling is **fundamental, not implementation-limited**.
- **`(B, T)` budget.** Defaults `B = 2^16`, `T = 200 ms` per `CLAR-PARAM-01` (RESOLVED). Raising `B` reduces `weak`-rate at the cost of canonicalization latency; the < 1% target shapes the default.

### 6.10 Honest-labelling status

`UNCONDITIONAL` (same-source determinism of the order and `cpg_order_hash`) + `CONDITIONAL THEOREM` (canonicality across isomorphic programs, conditional on `fingerprint_class = strong`). The conditional annotation is the persisted record of this dichotomy.

---

## 7. Algorithm 6 — Anytime-valid e-process spec gate

### 7.1 One-line statement

> An e-process for the precision-floor null, valid under unbounded optional continuation (Ville's inequality); acceptance when `E_t(σ) ≥ 1/α`; multiplicity over selected specs by e-process averaging; **shared instrument for the acceptance gate and the per-customer drift monitor**. — `PLAN.md §"Algorithm 6"`.

### 7.2 Owner component

`CMP-TRI-02` (`WBS.md §11`).

### 7.3 Formal inputs and outputs

```
Inputs:
    σ                : CandidateSpec
    evaluation_stream : Stream<AdjudicatedFinding>   -- bounded [0,1] outcomes
    π₀               : Precision floor               -- per detector class (CLAR-PARAM-02, DEFERRED)
    α                : Type-I error                   -- 0.05 (CLAR-PARAM-02 confirms)

Outputs:
    E_t(σ)           : float                          -- e-process wealth at time t (anytime-valid)
    decision         : {pending, accepted, quarantined}
    accepted_S_version : SemVer | null                -- new pinned spec version on acceptance
```

### 7.4 Algorithm statement (verbatim from `PLAN.md`)

> For each candidate (or in-production) spec `σ` and detector class, define the null
>
> ```
> H0(σ) :  true precision of σ on the evaluation stream  <  π₀.
> ```
>
> Maintain an **e-process** `E_t(σ)` for `H0(σ)` — a nonnegative process with `E_0 = 1` and `E[E_τ | H0] ≤ 1` at every stopping time `τ` (Ville's inequality). Concretely use a **betting confidence sequence for a bounded mean (Waudby-Smith & Ramdas 2024)**: each adjudicated finding contributing to `σ`'s precision estimate is a bounded `[0,1]` outcome; the e-process is the wealth of a betting strategy against `H0`.
>
> Decision rule, valid under unbounded optional continuation:
>
> - **Acceptance.** `σ` enters `S` (as an `S_version`) only when `E_t(σ) ≥ 1/α` (equivalently, the time-uniform lower confidence bound on precision exceeds `π₀`). … the guarantee `P(ever accept a σ with true precision < π₀) ≤ α` holds **simultaneously for all looks and all specs** via a single union bound over an e-process per spec.
> - **Continuous revalidation / drift.** The per-customer drift monitor is the *same instrument* run on the customer's adjudicated stream against the same `H0(σ)` with the customer's `π₀`. When the customer-stream e-process crosses the rejection threshold for the *complementary* null, `σ` is auto-quarantined for that customer.

The literature citation is load-bearing: **Waudby-Smith & Ramdas (2024)** for the betting confidence sequence for a bounded mean, plus Robbins (1970) and Howard, Ramdas, McAuliffe, Sekhon (2021) for time-uniform confidence sequences (`PLAN.md §"Literature grounding"`).

### 7.5 Multiplicity and selection

Selecting the maximum-recall candidate across `N` specs is handled by **maintaining one e-process per spec and combining by averaging** (an e-process is closed under averaging). This controls the family-wise error over the *selected* spec without a Bonferroni horizon.

### 7.6 Complexity

| Metric | Bound |
|---|---|
| Time (per finding) | `O(1)` — one update to the e-process wealth. |
| Space | `O(N)` for `N` candidate specs. |
| Statistical bound | `P(ever accept σ with true precision < π₀) ≤ α`, simultaneously for all looks and all specs. |

### 7.7 Invariants discharged

- **INV-3** — accepted specs are written as **new pinned `S_version`** rows; the deterministic core only ever reads pinned specs (`AC-TRI-02c`, `T-CMP-TRI-02-03`). The e-process is never on the detection path; it is a gate ahead of `S`.
- **INV-2** — pinned `S_version` plus `env_digest` on every finding.

### 7.8 Failure / fallback modes

- **Floor breach in the customer-stream e-process** → auto-quarantine `σ` for that customer (`CMP-TRI-03`, `AC-TRI-03a`).
- **Adversarial unbounded-continuation campaign** → realized ever-false-acceptance rate must respect α (`AC-TRI-02a` falsifier; pre-customer-enablement gate).
- **Martingale-property violation** → release blocker (`AC-TRI-02b`; production-enablement gate). Empirical `E[E_τ | H0] ≤ 1` across simulated stopping times.

### 7.9 Tests

| Test | Kind | Maps to |
|---|---|---|
| `TST-AC-TRI-02a` | `[FALSIFIER]` | Adversarial unbounded-continuation: realized ever-false-acceptance ≤ α with no horizon supplied. Pre-customer-enablement. |
| `TST-AC-TRI-02b` | `[UNIT]` | Martingale-property unit test; empirical `E[E_τ | H0] ≤ 1`. Pre-customer-enablement. |
| `TST-AC-TRI-02c` | `[INVARIANT]` | Accepted spec written version-pinned; core only ever consumes pinned specs. |
| `TST-AC-TRI-03a` | `[FALSIFIER]` | Global-accepted spec on adversarial customer distribution → quarantined. |
| `TST-AC-TRI-03b` | `[INVARIANT]` | `spec_provenance = global-unrevalidated` until revalidation. |

### 7.10 Known sensitivities

- **`π₀` per detector class.** Currently `CLAR-PARAM-02` (DEFERRED): per-class empirical baseline collected during Phase 5; α=0.05 confirmed.
- **Betting strategy choice.** Waudby-Smith & Ramdas 2024 gives the family; the specific betting strategy (e.g. coin-betting, ONS-style updates) is an implementation detail under `T-CMP-TRI-02-02`.
- **Closed under averaging** — relied upon for the multiplicity argument (no Bonferroni horizon needed).

### 7.11 Honest-labelling status

`UNCONDITIONAL` (anytime validity of the e-process via Ville's inequality — no information horizon required) + `EMPIRICAL` (the falsifier campaign measures realized error rates against α). Note: `INV-3` is the operational discipline that keeps Algorithm 6 **never** on the detection path — it is gating, never detection.

---

## 8. Cross-algorithm interaction diagram

```
                ┌────────────────────────────────────────┐
                │ source @ commit (Git content hash)     │
                └─────────────────┬──────────────────────┘
                                  │
                                  ▼
                  ┌────────────────────────────────────┐
                  │ Algorithm 1 — Incremental CPG      │
                  │ (CMP-SNAP-02)                       │
                  │                                     │
                  │  precondition: CW-DETECT verdict    │
                  │  output: G', ΔG, AFFECTED,          │
                  │          precondition_status        │
                  └──────────────┬──────────────────────┘
                                 │ G' (the CPG)
                                 ▼
                  ┌────────────────────────────────────┐
                  │ Algorithm 5 — Canonical CPG order  │
                  │ (CMP-CORE-03)                       │
                  │                                     │
                  │  output: canonical_order,           │
                  │          cpg_order_hash (INV-5)     │
                  └──────────────┬──────────────────────┘
                                 │ canonical_order
                                 ▼
                  ┌────────────────────────────────────┐
                  │ Algorithm 2 — IFDS/IDE Tabulation  │
                  │ (CMP-CORE-01)                       │
                  │                                     │
                  │  precondition: DSL distributivity   │
                  │     (CMP-DET-01 closure check)      │
                  │  inputs: CPG, canonical_order, spec │
                  │  output: solution, witnesses,       │
                  │          solution_hash              │
                  └──────────────┬──────────────────────┘
                                 │ witness per (sink, fact)
                                 ▼
                  ┌────────────────────────────────────┐
                  │ Algorithm 3 — Slice fingerprint    │
                  │ (CMP-CORE-02)                       │
                  │                                     │
                  │  inputs: witness, CPG, (B, T)       │
                  │  output: slice_fingerprint,         │
                  │          fingerprint_class          │
                  └──────────────┬──────────────────────┘
                                 │
                                 ▼
                  ┌────────────────────────────────────┐
                  │ Findings emitted with provenance   │
                  │ (CMP-ORCH-03 → CMP-FND-01..03)      │
                  │                                     │
                  │  every finding carries:             │
                  │   origin, S_version, env_digest,    │
                  │   cpg_order_hash (INV-5 annotated), │
                  │   slice_fingerprint,                │
                  │   fingerprint_class, ...            │
                  └──────────────┬──────────────────────┘
                                 │
              ┌──────────────────┼──────────────────────────┐
              ▼                                             ▼
  ┌────────────────────────────┐               ┌────────────────────────┐
  │ Algorithm 4 — Scheduler    │               │ Algorithm 6 — e-process│
  │ (CMP-ORCH-02)               │               │  spec gate (CMP-TRI-02)│
  │                             │               │                        │
  │ orchestrates work; NEVER    │               │ adjudicated stream →   │
  │ on SARIF (cross-checked by  │               │ candidate σ → accepted │
  │ Attestor, CMP-CP-05)        │               │   S_version (INV-3)    │
  └────────────────────────────┘               └────────────────────────┘
```

**Data-flow notes:**

- Algorithm 4 is orchestration; it never touches finding bytes. Its result-independence is `[INVARIANT]` cross-checked by the Attestor (`AC-ORCH-02b`).
- Algorithm 6 is **gating**, not detection. The accepted spec re-enters the pipeline as a new pinned `S_version` consumed by Algorithm 2 (per `INV-3`). The dashed line back from Alg 6 to the input side is `INV-3`-compliant: a logged, version-pinned data flow that the deterministic core may consume only via the pinned `S`.

---

## 9. Determinism partition mapping

| Algorithm | Partition role | Notes |
|---|---|---|
| **Algorithm 1** | Routing → records `precondition_status` per snapshot. | Closed-world / degraded paths feed `deterministic-core` (when CW-DETECT is correct). A CW-DETECT FN can later be retroactively re-partitioned by `CMP-SNAP-04`. |
| **Algorithm 2** | `deterministic-core` for `engine ∈ {ifds, ide}`. | Conditional on DSL closure (`INV-4`) + CPG-fidelity gate (`INV-6`). |
| **Algorithm 3** | Stamps `slice_fingerprint`, `fingerprint_class`. | Same-source determinism is `UNCONDITIONAL`; cross-refactor invariance is `CONDITIONAL` on the named normalization passes. |
| **Algorithm 4** | Scheduler — **no SARIF impact**. | Schedule-invariance is `INV-1`-adjacent: different schedules → identical `deterministic-core` findings (`AC-ORCH-02b`). |
| **Algorithm 5** | Stamps `cpg_order_hash` with conditional canonicality (`INV-5`). | Same-source order is `UNCONDITIONAL`; canonicality across isomorphic programs is `CONDITIONAL` on `fingerprint_class = strong`. |
| **Algorithm 6** | **Gating, never detection** (`INV-3`). | Accepted spec is written as new pinned `S_version`; core reads pinned specs only. The Attestor runs with `LLM_TRIAGE=off` to verify byte-identical SARIF independent of triage (`TST-INV-3-CP-05`). |

See `.claude/rules/05-determinism.md` for the canonical partition rules.

---

## 10. Honest-labelling tie-in

Per `PLAN.md §"Honest-labeling ledger"`, every claim made by Scanipy v3.2 carries one of four labels:

- `CONDITIONAL THEOREM` — proven under a named precondition with a named owner.
- `EMPIRICAL` — measured against a published threshold.
- `STAGED` — per-language readiness; `INV-6`.
- `UNCONDITIONAL` — properties unconditional in the design (e.g. property (c), Ville's anytime validity).

Mapping each algorithm:

| Alg | Per-algorithm honest-labelling status |
|---|---|
| 1 | `CONDITIONAL THEOREM` (closed-world, owned by CW-DETECT) + `EMPIRICAL` (open-world). |
| 2 | `CONDITIONAL THEOREM` (determinism on core, owned by DSL) + `EMPIRICAL` (per-(class,language) recall) + `STAGED` (per language per `INV-6`). |
| 3 | `CONDITIONAL THEOREM` (per-refactor invariance) + `EMPIRICAL` (strong-success / weak-rate) + `UNCONDITIONAL` (bounded fallback time cap). |
| 4 | `EMPIRICAL` only (p95 < 30 min). |
| 5 | `UNCONDITIONAL` (same-source order + hash) + `CONDITIONAL THEOREM` (canonicality conditional on `strong`). |
| 6 | `UNCONDITIONAL` (anytime validity via Ville's inequality) + `EMPIRICAL` (falsifier campaigns). |

The per-finding `provenance_records.claim_label` (`DOC-PROVENANCE §5`) is the operational reflection of this table at the finding granularity.

### 10.1 INV-6 honesty constraint (Algorithm 2 specifically)

Per `INV-6` and `RULE-7`: **Algorithm 2 recall claims are valid only for `(class, language)` pairs that have passed the CPG-fidelity gate** (`CMP-CP-06`). Front-end-blocked pairs are reported as `front-end-blocked`, **never** as recall failures. This is enforced by `TST-INV-6-CORE-01` and reflected in the per-stage rollout in `.claude/rules/04-staging.md`.

---

## 11. References

- `PLAN.md §"Algorithm 1 — Incremental CPG maintenance"`
- `PLAN.md §"Algorithm 2 — Detection core as IFDS/IDE"`
- `PLAN.md §"Algorithm 3 — Refactor-stable finding fingerprint"`
- `PLAN.md §"Algorithm 4 — Detector scheduling (heuristic)"`
- `PLAN.md §"Algorithm 5 — Canonical CPG ordering"`
- `PLAN.md §"Algorithm 6 — Spec inference with an anytime-valid precision gate"`
- `PLAN.md §"Per-algorithm summary"` (4-column table)
- `PLAN.md §"Honest-labeling ledger"`
- `PLAN.md §"Literature grounding"` (Waudby-Smith & Ramdas 2024; Robbins 1970; Howard et al. 2021; RHS 1995; Sagiv-Reps-Horwitz 1996; Yamaguchi et al. 2014; Demers-Reps-Teitelbaum 1981; Cai-Fürer-Immerman 1992)
- `SDD.md CMP-SNAP-02` (Alg 1), `SDD.md CMP-CORE-01` (Alg 2), `SDD.md CMP-CORE-02` (Alg 3), `SDD.md CMP-ORCH-02` (Alg 4), `SDD.md CMP-CORE-03` (Alg 5), `SDD.md CMP-TRI-02` (Alg 6)
- `SDD.md §2 INV-1..INV-6`
- `WBS.md §6..12` — per-component task lists
- `WBS.md §17 CLAR-PARAM-01` (RESOLVED — `(B, T)`, `θ_cone`, `θ_files`), `CLAR-PARAM-02` (DEFERRED — `π₀`, `α`)
- `.claude/rules/01-invariants.md` — invariant catalog
- `.claude/rules/04-staging.md` — per-language staging rules
- `.claude/rules/05-determinism.md` — determinism partition rules
- `DOC-DSL` — combinator-DSL grammar (owner of Alg 2's precondition)
- `DOC-PROVENANCE` — provenance chain that records every algorithm's output partition + claim label
- `DOC-INV` (forthcoming sibling) — invariants cross-reference
- `DOC-STAGING` (forthcoming sibling) — per-language staging detail
- `DOC-PARTITION` (forthcoming sibling) — `engine → origin` mapping
- `DOC-CMP-SNAP-02`, `DOC-CMP-CORE-01..03`, `DOC-CMP-ORCH-02`, `DOC-CMP-TRI-02` (forthcoming siblings) — procedural form of each algorithm

---

*Document end. Status: ACTIVE. Next review: at first acceptance of any `CMP-CORE-*` or `CMP-SNAP-02` or `CMP-TRI-02` `DONE`, or on resolution of `CLAR-PARAM-02` (e-process π₀ per class).*
