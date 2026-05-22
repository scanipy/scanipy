# DOC-CMP-CORE-01 — IFDS/IDE tabulation solver (Algorithm 2)

> **Status:** ACTIVE (Phase 0 deliverable). Satisfies `AC-DOC-04`: an Implementation Agent given only this document plus the cross-cutting refs (`DOC-INV`, `DOC-GLOSSARY`, `DOC-ALGS`, `DOC-PROVENANCE`, `DOC-DSL`, `DOC-PARTITION`, `DOC-SARIF`, `DOC-DB`, `DOC-STAGING`) can produce a passing implementation without re-reading `SDD.md`.

---

## 1. Component identity

| Field | Value |
|---|---|
| **CMP-ID** | `CMP-CORE-01` |
| **Subsystem** | Analysis Core (`SDD.md §6`) |
| **Module path** | `analysis/ifds/solver.py` (per `CLAUDE.md §12`) |
| **Staging** | **Stage A (then per-language)** — `CMP-CP-06` must be green for a `(class, language)` pair before its Algorithm 2 benchmark counts (`INV-6` / `RULE-7`). |
| **Depends-On** | `CMP-DET-01`, `CMP-SNAP-02`, `CMP-CORE-03` (`WBS.md §20`) |
| **Algorithm** | Algorithm 2 — Detection core as IFDS/IDE (`PLAN.md`, `DOC-ALGS §3`) |
| **Owning maintainer** | Analysis Core team |

---

## 2. Mandate

**SDD `Purpose:` (verbatim from `SDD.md §6 → CMP-CORE-01`):**

> Exploded-supergraph construction and the RHS Tabulation algorithm with reusable procedure summaries; IDE extension for lattice-valued classes; incremental mode invalidating only `AFFECTED` summaries.

**Operational role.** This is the **principal research-and-engineering deliverable** of Scanipy v3.2 (`PLAN.md §"Phase staging"`). For every detector with `engine ∈ {ifds, ide}`, this solver computes the meet-over-all-valid-paths (MVP) solution at every sink, paired with a realising path (the *witness*) for each `(sink, fact)` pair. The solver:

- consumes a CPG together with `canonical_order` from `CMP-CORE-03` and a distributive flow-function spec from `CMP-DET-01`;
- builds the exploded supergraph;
- runs the Reps–Horwitz–Sagiv (RHS, POPL 1995) Tabulation procedure with reusable procedure summaries;
- in IDE mode (Sagiv–Reps–Horwitz 1996), replaces fact sets with lattice-valued environment transformers for quantitative classes (crypto key size, race windows);
- in incremental mode, invalidates only summaries belonging to the `AFFECTED` set from Algorithm 1 (`CMP-SNAP-02`);
- emits one `Finding` per realising `(sink, fact)` with the four required provenance fields threaded.

It is the load-bearing component of `property (a)` (reproducibility under fixed environment): for fixed `(S_version, env_digest)` on the `deterministic-core` partition, repeated invocations on the same source produce **byte-identical** pre-serialisation solution hashes (`AC-CORE-01a`, Gate 3 release blocker via the Attestor `CMP-CP-05`).

---

## 3. Interface contract

### 3.1 Public Python signatures

```python
from typing import Literal, NewType, Protocol, Iterable, Mapping
from dataclasses import dataclass

NodeId   = NewType("NodeId",   int)
EdgeId   = NewType("EdgeId",   int)
ProcId   = NewType("ProcId",   int)
Fact     = NewType("Fact",     int)        # interned distributive-domain element
Sha256   = NewType("Sha256",   bytes)

# ----- IFDS flow-functions interface (consumed from CMP-DET-01) -----------

class FlowFunction(Protocol):
    """Distributive transfer over the finite fact domain. INV-4 (DSL closure)
    is owned by CMP-DET-01; this solver asserts it defensively (see §7)."""
    def apply(self, fact_in: Fact) -> frozenset[Fact]: ...

class FlowFunctionFactory(Protocol):
    """Per-edge factory: maps a supergraph edge to a flow function."""
    def for_edge(self, edge: "Edge") -> FlowFunction: ...

# ----- IDE lattice-valued extension --------------------------------------

class LatticeValuedTransformer(Protocol):
    """Sagiv-Reps-Horwitz '96 environment transformer for quantitative classes.
    Used when spec.mode == "ide"."""
    def compose(self, other: "LatticeValuedTransformer") -> "LatticeValuedTransformer": ...
    def apply(self, env: "Env") -> "Env": ...
    # `meet` is on the lattice itself, not the transformer.

# ----- Spec contract (from CMP-DET-01) -----------------------------------

@dataclass(frozen=True)
class Spec:
    spec_id:        str
    S_version:      str                                 # INV-2 (semver)
    mode:           Literal["ifds", "ide"]              # → origin partition
    fact_domain:    "FiniteFactDomain"                  # IFDS only
    lattice:        "Lattice | None"                    # IDE only
    flow_factory:   "FlowFunctionFactory | LatticeValuedFactory"
    source_preds:   "Predicate"
    sink_preds:     "Predicate"
    # DSL closure check (INV-4) is performed at registration by CMP-DET-01.

# ----- Solver outputs ----------------------------------------------------

@dataclass(frozen=True)
class Finding:
    sink:                 NodeId
    fact:                 Fact
    witness:              "Path"
    spec_id:              str
    origin:               Literal["deterministic-core"]     # INV-1
    S_version:            str                                # INV-2
    env_digest:           Sha256                             # INV-2
    cpg_order_hash:       Sha256                             # INV-5 (paired with annotation)
    cpg_order_hash_annotation: Literal["canonical iff fingerprint_class = strong"]
    determinism_partition: str
    engine:               Literal["ifds", "ide"]

@dataclass(frozen=True)
class SolverResult:
    findings:        frozenset[Finding]
    solution_hash:   Sha256          # pre-serialisation hash (AC-CORE-01a)
    summaries:       "SummaryCache"  # for next incremental run
    visited_procs:   frozenset[ProcId]

# ----- Public entry points -----------------------------------------------

def solve(
    supergraph: "ExplodedSupergraph",
    spec:       Spec,
    *,
    canonical_order: list[NodeId],   # from CMP-CORE-03
    cpg_order_hash:  Sha256,
    cpg_order_hash_annotation: str,
    fingerprint_class: Literal["strong", "weak"],
    env_digest:      Sha256,
) -> SolverResult:
    """Full-tabulation entry point. See §4 for build-and-call shape."""

def incremental_solve(
    supergraph:    "ExplodedSupergraph",
    spec:          Spec,
    affected_set:  frozenset[ProcId],   # AFFECTED from Algorithm 1 (CMP-SNAP-02)
    prior_summaries: "SummaryCache",
    *,
    canonical_order: list[NodeId],
    cpg_order_hash:  Sha256,
    cpg_order_hash_annotation: str,
    fingerprint_class: Literal["strong", "weak"],
    env_digest:      Sha256,
) -> SolverResult:
    """Bounded incremental mode (AC-CORE-01c): re-tabulate only procedures in
    `affected_set` and their transitive callers. Summaries outside that closure
    are reused verbatim from `prior_summaries`."""

# ----- Procedure-summary cache (RHS '95 §4) ------------------------------

class SummaryCache(Protocol):
    """Maps procedure entry → (start fact → set of (exit fact, edge function))."""
    def get(self, proc: ProcId) -> "Summary | None": ...
    def put(self, proc: ProcId, summary: "Summary") -> None: ...
    def invalidate(self, procs: Iterable[ProcId]) -> None: ...
    def serialize(self) -> bytes: ...   # for persistence / cross-run reuse
```

### 3.2 RHS Tabulation summary

Within `solve`, the procedure is (informally; see `DOC-ALGS §3` for the verbatim statement):

1. **Build exploded supergraph.** For each `(node, fact)` of the CPG, materialise the `D + 1` supergraph nodes per CPG node (`D = |fact_domain|`); edges between supergraph nodes are derived from `spec.flow_factory.for_edge(...)` (IFDS) or `LatticeValuedTransformer.compose(...)` (IDE).
2. **Path-edge worklist.** Initialise the worklist with `<entry, 0> → <entry, fact>` path-edges for each `fact` in `spec.source_preds`. Compute *path-edges* (`<sp, fact_a> → <n, fact_b>` meaning "there exists a same-level realisable path from start-of-proc to `n`") and *summary-edges* (procedure summaries) until fixpoint.
3. **Summary reuse.** On call from caller `c` to callee `g`, look up `summaries.get(g)`; if hit, apply summary; if miss, schedule callee for tabulation, splice the result.
4. **Enumeration order.** When the worklist offers multiple ready items at the same priority, **break ties by `canonical_order` from `CMP-CORE-03`**. This is what makes the solution hash byte-identical across runs.
5. **Read out solution.** For each sink `s` matched by `spec.sink_preds`, collect the path-edges ending at `s`. The set of `(sink, fact)` pairs is the MVP solution (`PLAN.md §"Algorithm 2"`).
6. **Compute `solution_hash`.** Hash the pre-serialisation form `[ (sink, fact, witness_canonical_form) for each pair in canonical_order ]`.

The IDE extension differs only in step 1 and the lattice meet in step 2: facts are environment transformers, and the lattice's meet operator (rather than set union) combines transformer values at confluence points.

### 3.3 Witness extraction

For each `(sink, fact)` in the solution, a *realising path* is recovered by backtracking on path-edges (one path per pair; deterministic given canonical_order). The path is passed to `CMP-CORE-02` for slice fingerprinting and is the input to the SARIF `codeFlows` payload (`DOC-SARIF`).

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Notes |
|---|---|---|
| `cpg` (via `supergraph`) | `CMP-SNAP-01` (full) / `CMP-SNAP-02` (delta) | Carries `env_digest`. |
| `spec: Spec` | `CMP-DET-01` registry | DSL-closed (INV-4 owner = CMP-DET-01); `S_version` semver-pinned (INV-2). |
| `canonical_order` | `CMP-CORE-03` | Drives byte-identical serialisation (`AC-CORE-01a`). |
| `cpg_order_hash` + annotation + `fingerprint_class` | `CMP-CORE-03` | Threaded to every emitted `Finding` (INV-5). |
| `affected_set` (incremental only) | `CMP-SNAP-02` Algorithm 1 | Set of procedure ids whose summaries must be invalidated. |
| `prior_summaries` (incremental only) | local `SummaryCache` from previous run | Persisted per snapshot, keyed by `env_digest + S_version`. |
| `env_digest` | `CMP-SNAP-01` worker image digest | INV-2. |

### 4.2 Outputs

| Output | Consumer |
|---|---|
| `SolverResult.findings: frozenset[Finding]` | `CMP-FND-01` (normaliser) → `CMP-FND-02` (store) → `CMP-FND-03` (provenance) |
| `SolverResult.solution_hash: Sha256` | Pre-serialisation hash used by `CMP-CP-05` Attestor (`AC-CORE-01a`). |
| `SolverResult.summaries: SummaryCache` | Persisted for the next incremental run. |
| `SolverResult.visited_procs: frozenset[ProcId]` | Telemetry to verify `AC-CORE-01c` (visits ⊆ `closure(affected_set)`). |

### 4.3 Persisted artefacts

- `findings` row per emitted `Finding` (via `CMP-FND-02` schema; `DOC-DB §3`).
- `provenance_records` row per finding (via `CMP-FND-03`; `DOC-PROVENANCE §3`).
- `SummaryCache` serialised to S3 at `orgs/{org_id}/codebases/{codebase_id}/summaries/{snapshot_digest}/{spec_id}.bin` (consumed by the next incremental scan; `DOC-PROVENANCE §"Storage layout"`).
- Witness payload to S3 at `orgs/{org_id}/codebases/{codebase_id}/witness/{slice_fingerprint}.json` (key is set by `CMP-CORE-02` once it computes the fingerprint; `DOC-PROVENANCE §"Storage layout"`).

---

## 5. Invariants touched

### 5.1 INV-1 — origin partition

Every emitted `Finding` carries `origin = "deterministic-core"` because `engine ∈ {ifds, ide}` for every detector that reaches this solver. The literal value is hard-coded at the `Finding` construction site here; `CMP-ORCH-03` (the partition arbiter for the platform overall) stamps it again defensively per `.claude/rules/05-determinism.md`. Findings later re-partitioned by `CMP-SNAP-04` are flipped post-hoc; this solver does not anticipate that.

### 5.2 INV-2 — versioned parameters

`S_version` is read from the loaded `spec` (set at registration by `CMP-DET-02`); `env_digest` is propagated from the snapshot. Both fields are required in `Finding` construction (typed; non-null). The solver MUST refuse to run if either is missing — fail-fast with `ValueError`, never silently default. See `DOC-PROVENANCE §2.1`.

### 5.3 INV-5 — conditional canonicality (passive carrier)

The solver does not produce `cpg_order_hash`; it consumes it from `CMP-CORE-03` and **threads it together with its annotation** into every emitted `Finding`. The `cpg_order_hash_annotation: Literal["canonical iff fingerprint_class = strong"]` field on `Finding` enforces this via the type system. No emitter path may construct a `Finding` without the annotation.

### 5.4 INV-6 — per-language honesty (**OWNED HERE for `AC-CORE-01b`**)

The recall/precision claim for `AC-CORE-01b` is **valid only on CPG-fidelity-gate-passing `(class, language)` pairs** (`CMP-CP-06`). Operational discipline:

- Before adding a `(class, language)` pair to the Algorithm 2 benchmark, confirm `CMP-CP-06` has passed for that language (per `.claude/rules/04-staging.md`).
- The benchmark harness (`TST-AC-CORE-01b`) reads the gate-pass table and skips non-passing pairs with status `front-end-blocked`, **never** reports them as recall failures.
- The honest-labelling ledger (`PLAN.md`) carries `[STAGED]` per `(class, language)` until the gate clears.

`TST-INV-6-CORE-01` is the operational invariant test.

### 5.5 INV-4 — distributivity precondition (defensive only)

This solver does **not** own `INV-4`. The DSL closure check at spec registration (`CMP-DET-01`, `CMP-DET-02`) is the operational owner: a non-distributive spec is rejected at registration and never reaches this solver. The solver carries a **defensive assertion** in `solve()` that verifies the spec's claimed `dsl_closure_proof_digest` matches a known-good value; on mismatch the solver raises `NonDistributiveSpec` and refuses to run. This is belt-and-braces, not a license to weaken `CMP-DET-01`.

---

## 6. Dependency contract

`Depends-On: CMP-DET-01, CMP-SNAP-02, CMP-CORE-03` (`WBS.md §20`).

| Dep | What this solver assumes |
|---|---|
| `CMP-DET-01` (DSL) | Every loaded `spec` has discharged its `[CONDITIONAL THEOREM]` distributivity proof obligations (`AC-DET-01a`); a non-distributive spec **cannot** be loaded. The solver carries a defensive assertion (§5.5). |
| `CMP-SNAP-02` (Algorithm 1) | Provides the `affected_set` for incremental mode. In full mode the solver ignores this and processes every procedure. |
| `CMP-CORE-03` (Algorithm 5) | Provides the `canonical_order` that drives byte-identical pre-serialisation. The hash + annotation come from the same result; they are threaded verbatim into every `Finding`. |
| `CMP-SNAP-01` (transitive) | Provides the CPG itself and `env_digest`. |
| `CMP-DET-02` (transitive) | Registry that loads `Spec` objects from `manifest.yaml`. |

A `STAGE-GATED` status for a `(class, language)` pair (e.g. Go before `CMP-CP-06` is green) does **not** block this component from running — the solver runs on whatever the orchestrator schedules. The staging gate only conditions which `(class, language)` cells are *benchmarked* under `AC-CORE-01b`.

---

## 7. Failure modes and error contracts

| Failure | Detection | Response |
|---|---|---|
| Non-distributive spec slips through | `solve()` re-checks `spec.dsl_closure_proof_digest` against the registry's known-good ledger | raise `NonDistributiveSpec`; refuse to run; emit no findings; log incident |
| Supergraph build OOM | psutil RSS > worker budget | raise `SupergraphTooLarge`; `CMP-ORCH-03` routes to `oracle-passthrough` fallback for the run; no `deterministic-core` finding emitted |
| Fixpoint diverges (would indicate a non-distributive escape) | iteration count exceeds `|D| · |E|` bound (RHS '95 ceiling) | raise `FixpointDiverged`; treat as `NonDistributiveSpec` event |
| `affected_set` references procedures absent from the supergraph | `set difference > ∅` | raise `StaleAffectedSet` — Algorithm 1 produced a stale closure (a `CMP-SNAP-02` bug). Do not silently degrade. |
| `prior_summaries` keyed by a different `(S_version, env_digest)` | header mismatch | raise `SummaryCacheVersionMismatch`; the caller must fall back to full `solve` |
| Missing `S_version` or `env_digest` | typed field is empty | raise `ValueError` — INV-2 violation; never silently default |

The solver does **not retry**: it is a pure function. Retry is the caller's policy (`CMP-ORCH-03`).

---

## 8. Provenance threading

Per `.claude/rules/02-provenance.md`, every emitted `Finding` carries the four required fields:

| Field | Source | Set where |
|---|---|---|
| `origin = "deterministic-core"` | constant (`engine ∈ {ifds, ide}`) | `Finding.__init__` |
| `S_version` | `spec.S_version` (INV-2) | `Finding.__init__` |
| `env_digest` | from CPG / snapshot (INV-2) | `Finding.__init__` |
| `cpg_order_hash` + `cpg_order_hash_annotation` + `fingerprint_class` | `CMP-CORE-03` result (INV-5) | `Finding.__init__` — annotation is a `Literal` type, cannot be omitted |

In addition the solver threads:

- `determinism_partition` (from `spec.determinism_partition` field set in `manifest.yaml` by `CMP-DET-02`).
- `engine` (`spec.mode`).
- `witness` — passed to `CMP-CORE-02` for slice fingerprinting; not directly persisted by this component.

The solver **does not write** `triage_score`, `triage_reason`, `spec_provenance`, `status`, `witness_blob_uri`, or `slice_fingerprint`. Those are stamped downstream (`CMP-TRI-01`, `CMP-CORE-02`, `CMP-FND-01..03`).

---

## 9. Acceptance criteria cross-reference

| AC ID | Verbatim from `SDD.md §6 CMP-CORE-01` | Test ID | Label | Notes |
|---|---|---|---|---|
| `AC-CORE-01a` | "**[Determinism]** 100 canary repos × 5 re-runs under fixed `(S, Env)` produce identical pre-serialization solution hashes; one mismatch falsifies the precondition or reveals a DSL escape." | `TST-AC-CORE-01a` | `[CONDITIONAL THEOREM]` — **release blocker** (Gate 3 via Attestor `CMP-CP-05`) | Corpus: `CMP-CORP-CANARY-01`. Feeds Gate 3 (Attestor, byte-identical SARIF on core partition). `[FORTHCOMING]` |
| `AC-CORE-01b` | "**[Value, per (class, language)]** On CPG-fidelity-gate-passing pairs only, recall ≥ Semgrep-default + 10pp at equal precision on OWASP Benchmark + Juliet + held-out BigVul." | `TST-AC-CORE-01b` | `[EMPIRICAL]` — **per stage**; **INV-6 gated** | Only on `(class, language)` pairs with `CMP-CP-06` green. Front-end-blocked pairs reported as such, never as recall failures. Corpora: OWASP Benchmark, Juliet, held-out BigVul (`CMP-CORP-VULN-01`). `[FORTHCOMING]` |
| `AC-CORE-01c` | "Incremental re-tabulation visits only `AFFECTED` entry points and their transitive callers." | `TST-AC-CORE-01c` | `[UNIT]` | Visit set is recorded in `SolverResult.visited_procs`; the test asserts `visited_procs ⊆ closure_callers(affected_set)`. `[FORTHCOMING]` |
| `TST-INV-6-CORE-01` | — invariant test | `TST-INV-6-CORE-01` | `[INVARIANT]` | Asserts the recall-claim emitter only emits per `(class, language)` rows for gate-passing pairs. `[FORTHCOMING]` |

Determinism (`AC-CORE-01a`) is achieved jointly by:

1. RHS Tabulation's worklist-order-independence theorem (`PLAN.md §"Algorithm 2"` conditional theorem, conditional on DSL closure — owned by `CMP-DET-01`).
2. Algorithm 5's canonical enumeration order (`CMP-CORE-03`, byte-identical serialisation).
3. Fixed `(S_version, env_digest)` (INV-2; the only environment the theorem covers per `PLAN.md §"Context and the objective"`).

A failure of `AC-CORE-01a` either falsifies the DSL distributivity claim or reveals a DSL escape — both routes go back to `CMP-DET-01` for triage.

---

## 10. Open questions

None currently. If an Implementation Agent encounters ambiguity not covered here, file `CLAR-CORE-NN` in `WBS.md §17` (`.claude/rules/03-scope.md`).

Note: `AC-CORE-01b`'s recall/precision threshold is **per `(class, language)` pair**; the exact precision-equality numeric is taken from Semgrep-default at the matched precision point on each corpus (`PLAN.md §"Algorithm 2"`). If a corpus turns out to have an ambiguous Semgrep baseline, file `CLAR-CORP-*` against `CMP-CORP-VULN-01`, not `CMP-CORE-01`.

---

## Appendix A. Algorithm sketch (informative)

```python
def solve(supergraph, spec, *, canonical_order, cpg_order_hash,
          cpg_order_hash_annotation, fingerprint_class, env_digest):
    # Defensive INV-4 re-check (owner is CMP-DET-01)
    if spec.dsl_closure_proof_digest not in registry.known_good_proofs():
        raise NonDistributiveSpec(spec.spec_id)

    summaries  = SummaryCache()
    path_edges = WorkList(order_key=canonical_order_index)

    for entry, fact in _seed_path_edges(supergraph, spec.source_preds):
        path_edges.add(PathEdge(entry, 0, entry, fact))

    while path_edges:
        e = path_edges.pop_min_by(canonical_order_index)
        _process_path_edge(e, supergraph, spec, summaries, path_edges)

    findings = []
    for sink in _sinks_in_order(supergraph, spec.sink_preds, canonical_order):
        for fact in _facts_reaching(sink, path_edges):
            witness = _backtrack_witness(sink, fact, path_edges, canonical_order)
            findings.append(Finding(
                sink=sink, fact=fact, witness=witness, spec_id=spec.spec_id,
                origin="deterministic-core",
                S_version=spec.S_version, env_digest=env_digest,
                cpg_order_hash=cpg_order_hash,
                cpg_order_hash_annotation=cpg_order_hash_annotation,
                determinism_partition=spec.determinism_partition,
                engine=spec.mode,
            ))

    solution_hash = _hash_pre_serialisation(findings, canonical_order)
    return SolverResult(frozenset(findings), solution_hash, summaries,
                        visited_procs=summaries.visited())


def incremental_solve(supergraph, spec, affected_set, prior_summaries, **kw):
    if prior_summaries.header != (spec.S_version, kw["env_digest"]):
        raise SummaryCacheVersionMismatch()
    summaries = prior_summaries.copy()
    callers   = supergraph.transitive_callers(affected_set)
    summaries.invalidate(affected_set | callers)
    # AC-CORE-01c: only re-tabulate procs whose summaries were invalidated.
    return _retabulate(supergraph, spec, summaries, restrict_to=affected_set | callers,
                        **kw)
```

---

## Appendix B. Cross-references

- `PLAN.md §"Algorithm 2 — Detection core as IFDS/IDE"`
- `SDD.md §6 CMP-CORE-01`
- `WBS.md §8 (component table)`, `§14 (tests)`, `§20 (DAG)`, `§22 (reading guide)`
- `DOC-ALGS §3` (algorithm reference)
- `DOC-INV §3, §8` (INV-1, INV-6)
- `DOC-DSL` (DSL closure check; INV-4 owner)
- `DOC-PARTITION §"engine→origin"`
- `DOC-PROVENANCE §3`
- `DOC-STAGING §"per (class, language)"` (INV-6 / `CMP-CP-06`)
- `.claude/rules/01-invariants.md §INV-1, §INV-2, §INV-6`
- `.claude/rules/02-provenance.md`
- `.claude/rules/04-staging.md`
- `.claude/rules/05-determinism.md`
- RHS '95: Reps, Horwitz, Sagiv, "Precise interprocedural dataflow analysis via graph reachability" (POPL 1995).
- Sagiv-Reps-Horwitz '96: "Precise interprocedural dataflow analysis with applications to constant propagation" (TAPSOFT 1995 / TCS 1996).
