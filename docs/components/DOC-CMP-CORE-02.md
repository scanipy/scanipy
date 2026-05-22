# DOC-CMP-CORE-02 — Slice fingerprint (Algorithm 3)

> **Status:** DRAFT (Phase 0). Satisfies `AC-DOC-04`: an Implementation Agent given only this document plus the cross-cutting refs (`DOC-INV`, `DOC-GLOSSARY`, `DOC-ALGS`, `DOC-PROVENANCE`, `DOC-SARIF`, `DOC-DB`) can produce a passing implementation without re-reading `SDD.md`.

---

## 1. Component identity

| Field | Value |
|---|---|
| **CMP-ID** | `CMP-CORE-02` |
| **Subsystem** | Analysis Core (`SDD.md §6`) |
| **Module path** | `analysis/fingerprint.py` (per `CLAUDE.md §12`) |
| **Staging** | Stage A (cross-language; not per-language gated). |
| **Depends-On** | `CMP-CORE-01`, `CMP-CORE-03` (`WBS.md §20`) |
| **Sets** | `fingerprint_class ∈ {strong, weak}` — the gating field for `INV-5`'s conditional-canonicality semantics. |
| **Algorithm** | Algorithm 3 — Refactor-stable finding fingerprint (`PLAN.md`, `DOC-ALGS §4`) |
| **Owning maintainer** | Analysis Core team |

---

## 2. Mandate

**SDD `Purpose:` (verbatim from `SDD.md §6 → CMP-CORE-02`):**

> Backward interprocedural slice along the witness; the named normalization passes (α-renaming, PDG-only formatting, canonical topological sort, summary-inlining for extract/inline, FQN normalization for file-move); bounded canonicalization with the `weak` fallback.

**Operational role.** For each `Finding` produced by `CMP-CORE-01`, this component:

1. Computes the **backward interprocedural slice** along the realising witness path.
2. Applies the **named normalisation passes** in fixed order (α-renaming, PDG-only formatting, canonical topological sort, summary-inlining for pure extract/inline, FQN normalisation for file-move/package-rename).
3. Runs **bounded canonicalisation** (2-WL to fixpoint, then individualisation-refinement under the shared `(B, T)` budget — same budget as `CMP-CORE-03`).
4. Emits a **`slice_fingerprint: Sha256`** plus a **`fingerprint_class: Literal["strong", "weak"]`** indicator.
5. On budget exhaustion, falls back to the `O(|witness|)`-capped **witness-edge-sequence hash** and stamps `fingerprint_class = "weak"`.

The fingerprint is the **cross-scan and cross-refactor identity** of the finding (`DOC-ALGS §"Owner components"`). It is what makes the baseline lookup in `CMP-FND-01` work across rebases, extract/inline-method refactors, and file moves — *provided* the fingerprint is `strong`. A `weak`-class fingerprint is a same-source identity only and **must never be auto-suppressed across a refactor** (`AC-CORE-02c`).

---

## 3. Interface contract

### 3.1 Public Python signature

```python
from typing import Literal, NewType
from dataclasses import dataclass

NodeId   = NewType("NodeId", int)
Sha256   = NewType("Sha256", bytes)
Duration = NewType("Duration", float)

@dataclass(frozen=True)
class SliceFingerprintResult:
    slice_fingerprint:  Sha256
    fingerprint_class:  Literal["strong", "weak"]
    budget_exhausted:   bool
    elapsed_ms:         float
    # Persisted record discipline (INV-5):
    cpg_order_hash_annotation: Literal["canonical iff fingerprint_class = strong"]

def compute_slice_fingerprint(
    finding:       "Finding",
    cpg:           "CPG",
    witness_path:  "Path",
    *,
    B: int = 2**16,            # CLAR-PARAM-01 RESOLVED
    T: Duration = 0.200,       # CLAR-PARAM-01 RESOLVED
) -> SliceFingerprintResult:
    """
    Backward interprocedural slice + bounded canonicalisation per Algorithm 3.

    On `(B, T)` exhaustion, returns `fingerprint_class = "weak"`. A weak
    fingerprint MUST NOT be used to auto-suppress a finding across a refactor
    (AC-CORE-02c; enforced by CMP-FND-01 baseline policy).
    """
    ...
```

The function is **pure**: same `(finding, cpg, witness_path, B, T)` always produces the same `SliceFingerprintResult`.

### 3.2 The named normalisation passes

The slice is reduced to a normal form by these passes, applied in this order (`PLAN.md §"Algorithm 3"`, `DOC-ALGS §4.4`):

1. **α-renaming for locals.** Every local variable's name is replaced by a deterministic counter based on its CFG position in the slice. Refactors that rename a local become invariant.
2. **PDG-only formatting normalisation.** AST decoration that is formatting-only (whitespace, comment positions, trailing commas, parenthesisation that does not change the PDG) is dropped. Only PDG-relevant nodes survive.
3. **Canonical topological sort for independent reordering.** Independent statements (data-dependence-wise) are ordered by the canonical traversal from `CMP-CORE-03` (`canonical_order`). Refactors that reorder independent statements become invariant.
4. **Summary-inlining normalisation** for extract/inline-method. **Proven for pure extract only** — impure extracts that change aliasing or side-effect order **must** flip the fingerprint (`AC-CORE-02b`). The design honours this by not normalising impure extracts.
5. **FQN normalisation** for file-move / package-rename. Fully-qualified names are reduced to their structural identity (declaration kind + canonical path-from-root); package-rename refactors become invariant.

These five passes are the **proof obligations** for `AC-CORE-02a` (per-refactor invariance) — each named refactor exercises a specific pass.

### 3.3 Bounded canonicalisation + `weak` fallback

After the five normalisation passes, the slice is fed to a 2-WL + bounded individualisation-refinement under the shared `(B, T)` budget. This is the **same budget** as `CMP-CORE-03` (per `PLAN.md §"Algorithm 3"`: "individualization-refinement under hard budget `(B, T)`") — `CLAR-PARAM-01` confirms `B = 2^16` search-tree nodes, `T = 200 ms` wall-clock.

On exhaustion the fallback hashes the `O(|witness|)`-capped **witness-edge-sequence** (a deterministic linearisation of the witness path through the supergraph). The result is `fingerprint_class = "weak"`.

The `weak`-class is operationally distinct from `CMP-CORE-03`'s `weak`-class:

- `CMP-CORE-03` `weak` means "the CPG order is not canonical-across-isomorphism, but is deterministic on this source."
- `CMP-CORE-02` `weak` means "the slice canonicalisation hit the budget; the fingerprint is the witness-edge-sequence hash, not the canonical-slice hash."

Both are consistent with `INV-5`: each conditional artefact carries its own conditional annotation. A finding can be `(weak, weak)`, `(strong, weak)`, `(weak, strong)`, or `(strong, strong)`; the `weak`-never-auto-suppress rule applies on either `weak`.

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Notes |
|---|---|---|
| `finding: Finding` | `CMP-CORE-01` | Provides sink, fact, `S_version`, `env_digest`, `cpg_order_hash`, `engine`. |
| `cpg: CPG` | upstream | Provides the underlying graph for slice extraction. |
| `witness_path: Path` | `CMP-CORE-01` `Finding.witness` | The realising path. Backward slice is computed along this. |
| `B`, `T` | `CLAR-PARAM-01` defaults `2**16` / `200 ms` | Shared budget with `CMP-CORE-03`. |

### 4.2 Outputs

| Output | Type | Consumer |
|---|---|---|
| `slice_fingerprint` | `Sha256` | `CMP-FND-01` (attach to result), `CMP-FND-02` (`findings.slice_fingerprint`), `CMP-FND-03` (provenance), `CMP-FND-01` baseline lookup. |
| `fingerprint_class` | `Literal["strong", "weak"]` | Same destinations; **gates** auto-suppression policy (`AC-CORE-02c`, `AC-FND-02a`). |
| `budget_exhausted`, `elapsed_ms` | telemetry | Drives `AC-CORE-02c` rate measurement (publish < 5% per `CLAR-PARAM-03` RESOLVED). |

### 4.3 Persisted artefacts

This component does **not** write directly. Downstream:

- `findings.slice_fingerprint` and `findings.fingerprint_class` (per `DOC-DB §3`).
- `provenance_records.slice_fingerprint` and `.fingerprint_class` (per `DOC-PROVENANCE §3`).
- Witness blob at S3 `orgs/{org_id}/codebases/{codebase_id}/witness/{slice_fingerprint}.json` (key shape from `DOC-PROVENANCE §"Storage layout"`).
- SARIF `result.properties.slice_fingerprint` and `.fingerprint_class` (per `DOC-SARIF`).

---

## 5. Invariants touched

### 5.1 INV-5 — Conditional labels are self-describing (**discharges `fingerprint_class`**)

This component is the **operational producer of `fingerprint_class`**, the gating field for `INV-5`'s conditional-canonicality semantics. The `cpg_order_hash` annotation (owned by `CMP-CORE-03`) reads "canonical iff `fingerprint_class = strong`"; this component is what sets that flag.

Operational discipline:

1. Set `fingerprint_class = "strong"` only when the bounded canonicalisation completed within `(B, T)`; otherwise `"weak"`.
2. The persisted record discipline (`DOC-PROVENANCE §3`) requires both the `cpg_order_hash` annotation AND `fingerprint_class` in the same row.
3. **A `weak`-classed finding MUST NEVER be auto-suppressed across a refactor** (`AC-CORE-02c`). This is enforced operationally in `CMP-FND-01`'s baseline-lookup policy (`AC-FND-02a`); this component's contribution is the truthful flag.

Counter-example (do not write):

```python
# BAD — INV-5 violation: lies about the class
return SliceFingerprintResult(h, fingerprint_class="strong", budget_exhausted=True, …)
```

The `Literal["strong", "weak"]` type makes this catchable; the unit test `TST-INV-5-CORE-02` asserts class flips on budget exhaustion.

### 5.2 INV-1, INV-2 (passive)

The slice fingerprinter does not set `origin`, `S_version`, or `env_digest` on the finding (they are already on the input `Finding`). It threads them through unchanged. The fingerprint itself is a function of the source slice — independent of `S_version` and `env_digest` — by design (otherwise refactor-stability would not hold across a spec update). However, the persisted `findings.slice_fingerprint` row still carries `S_version` and `env_digest` in the same row (per `CMP-FND-02` schema).

### 5.3 INV-4 (not owned here)

Algorithm 3 is *not* an undecidable approximation. The named normalisation passes are deterministic refactor-invariance proofs, not safe-direction approximations. INV-4 does not apply to this component. (Cf. `CMP-SNAP-03` and `CMP-DET-01`, which do own INV-4.)

---

## 6. Dependency contract

`Depends-On: CMP-CORE-01, CMP-CORE-03` (`WBS.md §20`).

| Dep | What this component assumes |
|---|---|
| `CMP-CORE-01` | Provides `Finding` with a fully populated `witness` field. The witness must be a valid path in the supergraph. The finding's `origin = "deterministic-core"` (oracle findings are not fingerprinted by this component — they take a `witness_blob_uri = null` path per `DOC-PROVENANCE §3`). |
| `CMP-CORE-03` | Provides `canonical_order` for the topological-sort normalisation pass. Provides `cpg_order_hash` + annotation for downstream record co-residency. |

This component **does not depend on** `CMP-SNAP-02` (the slice is derived from the witness, not from the diff oracle).

---

## 7. Failure modes and error contracts

| Failure | Detection | Response |
|---|---|---|
| `(B, T)` budget exhaustion | search-tree counter ≥ `B` OR wall-clock ≥ `T` | fall through to `weak` fallback (witness-edge-sequence hash); set `fingerprint_class = "weak"`, `budget_exhausted = True`. This is **not an error** — it is a defined output mode. |
| Witness path is empty | `len(witness_path) == 0` | raise `EmptyWitness` — Algorithm 2 emitted a finding without a realising path; this is a `CMP-CORE-01` bug. |
| Witness path references a node not in the CPG | runtime `KeyError` | raise `WitnessNotInCPG` — likely a stale snapshot. Do not silently degrade. |
| Impure extract/inline (aliasing or side-effect order changed by the extract) | pass 4 detects a non-pure extract pattern | **do not normalise**; the fingerprint will flip (per `AC-CORE-02b`). This is correct behaviour. |
| `weak`-rate aggregate > 5% on the canary corpus | telemetry roll-up | not failed at the per-finding level; triggers a **canonicalizer redesign** trigger per `CLAR-PARAM-03` RESOLVED. Aggregate fail handled by `TST-AC-CORE-02c`. |

The function is synchronous and deterministic. No retry.

### 7.1 `weak`-rate budget

Per `CLAR-PARAM-03` (RESOLVED, 2026-05-23): the operational publish threshold for `weak`-fallback rate is **5%**. Published rate ≥ 5% triggers a canonicalizer redesign per `PLAN.md §"Algorithm 3"`. Algorithm 3's `[EMPIRICAL]` strong-success-within-budget target is ≥ 98% (i.e. weak ≤ 2%); the 5% threshold is the operational alarm, not the design target.

---

## 8. Provenance threading

| Field this component writes | Where it ends up |
|---|---|
| `slice_fingerprint` | `findings.slice_fingerprint`, `provenance_records.slice_fingerprint`, SARIF `properties.slice_fingerprint`, witness blob S3 key. |
| `fingerprint_class` | `findings.fingerprint_class`, `provenance_records.fingerprint_class`, SARIF `properties.fingerprint_class`, auditor export `fingerprint_class`. |

The four required fields (`origin`, `S_version`, `env_digest`, `cpg_order_hash + annotation`) are **threaded through unchanged** from the input `Finding` — this component does not mutate them. Per `.claude/rules/02-provenance.md`:

> CMP-CORE-02 attaches `slice_fingerprint` + `fingerprint_class`.

Code-review check: any new write to `findings.slice_fingerprint` must come from this component (or a `CMP-FND-01` pass-through) and must be paired with a matching `findings.fingerprint_class`.

---

## 9. Acceptance criteria cross-reference

| AC ID | Verbatim from `SDD.md §6 CMP-CORE-02` | Test ID | Label | Notes |
|---|---|---|---|---|
| `AC-CORE-02a` | "Fingerprint invariant under each named refactor on 50 seeded findings." | `TST-AC-CORE-02a` | `[FALSIFIER]` | Corpus: `CMP-CORP-REFAC-01` (50 seeded findings; each refactor exercises a specific named normalisation pass). `[FORTHCOMING]` |
| `AC-CORE-02b` | "Fingerprint changes on a genuine fix and on an aliasing-changing extract." | `TST-AC-CORE-02b` | `[FALSIFIER]` | Two adversarial seeds: a real fix (deletes the sink) and an aliasing-changing extract (impure extract that changes alias relationships). Both must flip the fingerprint. `[FORTHCOMING]` |
| `AC-CORE-02c` | "`weak`-fallback rate measured and < 5%; a `weak`-classed finding is never auto-suppressed across a refactor." | `TST-AC-CORE-02c` | `[EMPIRICAL] + [INVARIANT]` | Two-part: (i) aggregate `weak`-rate measurement < 5% over `CMP-CORP-CANARY-01`; (ii) `CMP-FND-01` baseline-lookup policy never matches a `weak`-classed prior across a refactor. `[FORTHCOMING]` |
| `TST-INV-5-CORE-02` | — invariant test | `TST-INV-5-CORE-02` | `[INVARIANT]` | Class flips on budget exhaustion; `weak` never auto-suppressed end-to-end. `[FORTHCOMING]` |

The fingerprint feeds the **canary corpus** (`CMP-CORP-CANARY-01`) via cross-refactor invariance assertions, and the **refactor corpus** (`CMP-CORP-REFAC-01`) via the five named-refactor invariance assertions.

---

## 10. Open questions

None currently.

`CLAR-PARAM-01` (budget defaults `B = 2^16`, `T = 200 ms`) and `CLAR-PARAM-03` (`weak`-fallback publish threshold 5%) are both **RESOLVED** (`WBS.md §17`, 2026-05-23).

If an Implementation Agent encounters ambiguity not covered here — for example, the precise definition of "pure extract" or the per-language back-end for the slice extractor — file `CLAR-CORE-NN` in `WBS.md §17`. Do not invent missing scope (`.claude/rules/03-scope.md`).

---

## Appendix A. Pseudocode (informative)

```python
def compute_slice_fingerprint(finding, cpg, witness_path, *, B=2**16, T=0.200):
    t0 = time.monotonic()

    # 1. Backward interprocedural slice along the witness
    slice_graph = _backward_interprocedural_slice(cpg, witness_path)

    # 2. Named normalisation passes (in fixed order)
    slice_graph = _alpha_rename_locals(slice_graph)            # pass 1
    slice_graph = _drop_pdg_only_formatting(slice_graph)        # pass 2
    slice_graph = _canonical_topo_sort(slice_graph, cpg.canonical_order)  # pass 3
    slice_graph = _summary_inline_pure_extract(slice_graph)    # pass 4 (pure only)
    slice_graph = _fqn_normalise(slice_graph)                  # pass 5

    # 3. Bounded canonicalisation
    elapsed = time.monotonic() - t0
    try:
        canonical_form = _canonicalise_under_budget(
            slice_graph, B=B, T=T - elapsed
        )
        h = sha256_of(canonical_form)
        return SliceFingerprintResult(
            slice_fingerprint=h,
            fingerprint_class="strong",
            budget_exhausted=False,
            elapsed_ms=(time.monotonic() - t0) * 1000.0,
            cpg_order_hash_annotation="canonical iff fingerprint_class = strong",
        )
    except BudgetExhausted:
        h = sha256_of(_witness_edge_sequence(witness_path))   # O(|witness|)
        return SliceFingerprintResult(
            slice_fingerprint=h,
            fingerprint_class="weak",
            budget_exhausted=True,
            elapsed_ms=(time.monotonic() - t0) * 1000.0,
            cpg_order_hash_annotation="canonical iff fingerprint_class = strong",
        )
```

---

## Appendix B. Cross-references

- `PLAN.md §"Algorithm 3 — Refactor-stable finding fingerprint"`
- `SDD.md §6 CMP-CORE-02`
- `WBS.md §8 (component table)`, `§14 (tests)`, `§20 (DAG)`, `§17 CLAR-PARAM-01, CLAR-PARAM-03 RESOLVED`
- `DOC-ALGS §4` (algorithm reference)
- `DOC-INV §7` (INV-5 cross-reference)
- `DOC-PROVENANCE §3, §8` (persistence)
- `DOC-SARIF` (SARIF property contract)
- `DOC-DB §3` (column definitions)
- `.claude/rules/01-invariants.md §INV-5`
- `.claude/rules/02-provenance.md`
