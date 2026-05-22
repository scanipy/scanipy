# DOC-CMP-CORE-03 — Canonical CPG ordering (Algorithm 5)

> **Status:** ACTIVE (Phase 0 deliverable). Satisfies `AC-DOC-04`: an Implementation Agent given only this document plus the cross-cutting refs (`DOC-INV`, `DOC-GLOSSARY`, `DOC-ALGS`, `DOC-PROVENANCE`, `DOC-SARIF`, `DOC-DB`, `DOC-PARTITION`) can produce a passing implementation without re-reading `SDD.md`.

---

## 1. Component identity

| Field | Value |
|---|---|
| **CMP-ID** | `CMP-CORE-03` |
| **Subsystem** | Analysis Core (`SDD.md §6`) |
| **Module path** | `analysis/ordering.py` (per `CLAUDE.md §12`) |
| **Staging** | Stage A · cross-language · no per-language gating |
| **Depends-On** | none (Wave-1, per `WBS.md §20`) |
| **Owns invariant** | **INV-5** (`cpg_order_hash` carries the conditional annotation `canonical iff fingerprint_class = strong`) |
| **Algorithm** | Algorithm 5 — Canonical CPG ordering (`PLAN.md`, `DOC-ALGS §6`) |
| **Owning maintainer** | Analysis Core team (Stage-A maintainer set) |

---

## 2. Mandate

**SDD `Purpose:` (verbatim from `SDD.md §6 → CMP-CORE-03`):**

> 2-WL refinement, bounded individualization-refinement under hard `(B, T)` budget, and the deterministic stable-order fallback on budget exhaustion. Produces `cpg_order_hash` annotated `canonical iff fingerprint_class = strong` (INV-5).

**Operational role.** This component computes a deterministic, parse-order-independent enumeration of every CPG node and edge. It is invoked once per snapshot (after `CMP-SNAP-01` materialises the CPG), produces a vector `canonical_order: Vec<NodeId>` plus a `cpg_order_hash: sha256` digest, and stamps the hash with a `fingerprint_class ∈ {strong, weak}` indicator. The downstream IFDS/IDE solver (`CMP-CORE-01`) consumes `canonical_order` to obtain byte-identical pre-serialisation under fixed `(S, Env)`; the slice fingerprinter (`CMP-CORE-02`) consumes the same order; the SARIF emitter (`CMP-FND-01`) and provenance writer (`CMP-FND-03`) both persist the hash together with its conditional-canonicality annotation per `INV-5`.

It is the structural anchor that allows `(a)` (reproducibility) to hold on the deterministic-core partition: same source produces the same node order, hence same serialisation, hence byte-identical SARIF — *even when the underlying graph is CFI-symmetric and a true canonical form cannot be computed within budget*.

---

## 3. Interface contract

### 3.1 Public Python signature

```python
from typing import Literal, NewType
from dataclasses import dataclass

NodeId = NewType("NodeId", int)
Sha256 = NewType("Sha256", bytes)            # 32 bytes
Duration = NewType("Duration", float)         # seconds

@dataclass(frozen=True)
class CanonicalOrderResult:
    """Output of canonical_order. INV-5 anchor."""
    canonical_order:   list[NodeId]                       # deterministic enumeration
    cpg_order_hash:    Sha256                             # sha256 over the order
    fingerprint_class: Literal["strong", "weak"]          # canonical iff "strong"
    annotation:        Literal["canonical iff fingerprint_class = strong"]
    budget_exhausted:  bool                               # True iff fell to fallback
    elapsed_ms:        float                              # for AC-CORE-03b telemetry

def canonical_order(
    cpg: "CPG",
    *,
    B: int = 2**16,              # search-tree node cap (CLAR-PARAM-01 RESOLVED)
    T: Duration = 0.200,         # seconds wall-clock cap (CLAR-PARAM-01 RESOLVED)
) -> CanonicalOrderResult:
    """
    Compute a deterministic enumeration of `cpg` together with `cpg_order_hash`.

    The returned `annotation` field is always the literal string
        "canonical iff fingerprint_class = strong"
    and MUST be persisted adjacent to the hash everywhere (INV-5 / AC-CORE-03c).
    """
    ...
```

The function is **pure**: same `(cpg, B, T)` always produces the same `CanonicalOrderResult`. No I/O. No global state. No randomness (use only deterministic tie-breakers — see §4).

### 3.2 Three algorithmic phases

1. **Seed labels** (`_seed_labels`): for each node `n`, compute
   `label_0(n) = hash((kind, operator_or_literal, resolved_fqn, sorted_multiset_of_incident_edge_kinds)))`.
2. **2-WL refinement to fixpoint** (`_wl_refine_to_fixpoint`): iteratively recompute `label_{k+1}(n) = hash((label_k(n), sorted_multiset_of (edge_kind, label_k(neighbour)) for each incident edge))` until `partition_k == partition_{k-1}`.
3. **Tie-break under shared `(B, T)` budget** (`_individualise_refine`): residual symmetric classes are broken first by enclosing-declaration canonical order, then by bounded individualisation-refinement (pick a representative, refine, recurse). Search-tree node count and wall-clock are measured against `(B, T)`. On non-exhaustion, return `fingerprint_class = "strong"`. On exhaustion, fall through to:
4. **Stable-order fallback** (`_stable_order_fallback`): order each remaining symmetric class by the tuple `(declaration_hash, structural_path_from_declaration_root, edge_kind)`, with `declaration_hash := sha256(enclosing_declaration.fqn)` and `structural_path_from_declaration_root` a deterministic AST traversal path. Returns `fingerprint_class = "weak"`.

### 3.3 Procedure-summary cache

No procedure summaries are produced here — the cache lives in `CMP-CORE-01`. This component is single-shot per snapshot.

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Notes |
|---|---|---|
| `cpg: CPG` | `CMP-SNAP-01` (full) or `CMP-SNAP-02` (delta) | Must be the canonicalised Joern CPG; same source must produce the same graph. |
| `B: int` | `CLAR-PARAM-01` default `2**16` | Hard cap on individualisation-refinement search-tree nodes. |
| `T: Duration` | `CLAR-PARAM-01` default `200ms` | Hard cap on wall-clock for the bounded IR phase. |

### 4.2 Outputs

| Output | Type | Consumers |
|---|---|---|
| `canonical_order` | `list[NodeId]` | `CMP-CORE-01` (Tabulation enumeration), `CMP-CORE-02` (slice traversal), `CMP-FND-01` (SARIF result ordering, `AC-FND-01b`). |
| `cpg_order_hash` | `bytes` (sha256) | `CMP-FND-02` (`findings.cpg_order_hash`), `CMP-FND-03` (provenance chain link 5), `CMP-FND-01` (SARIF `properties.cpg_order_hash`), auditor export (`CMP-FND-03 export`, `CMP-CP-04` dashboard). |
| `fingerprint_class` | `Literal["strong", "weak"]` | All persisted records (`DOC-PROVENANCE §3` schema); gates auto-suppression policy (`AC-CORE-02c`). |
| `annotation` | constant string `"canonical iff fingerprint_class = strong"` | Co-persisted adjacent to the hash everywhere (`AC-CORE-03c`, `INV-5`). |
| `budget_exhausted`, `elapsed_ms` | telemetry | Drives `AC-CORE-03b` rate measurement (publish < 1%). |

### 4.3 Persisted artefacts

This component **does not write to any store directly**. Its outputs are passed to:

- `CMP-FND-02` `provenance_records.cpg_order_hash` + `.cpg_order_hash_annotation` + `.fingerprint_class` (per `DOC-DB §3`, `DOC-PROVENANCE §3`).
- `CMP-FND-01` SARIF `result.properties.cpg_order_hash` + `.cpg_order_hash_annotation` (per `DOC-SARIF §"properties"`).
- `CMP-FND-03` auditor export JSON: `{"cpg_order_hash": ..., "cpg_order_hash_annotation": ..., "fingerprint_class": ...}` with **JSON-adjacent** placement (`DOC-PROVENANCE §10`).

The implementation MUST NOT emit a record that contains `cpg_order_hash` without also emitting the annotation in the same record (`INV-5`).

---

## 5. Invariants touched

### 5.1 INV-5 — Conditional labels are self-describing (**OWNER**)

This component **is** the operational discharge of `INV-5` (cf. `DOC-INV §7`, `.claude/rules/01-invariants.md`).

The hash is *canonical* — meaning two isomorphic-but-differently-written programs produce the same hash — **only when** the 2-WL + bounded individualisation-refinement phase converged within `(B, T)`. On budget exhaustion the stable-order fallback yields a hash that is:

- **deterministic over the same source** (run twice on the same parsed CPG, get the same bytes — this is `[UNCONDITIONAL]` per `DOC-ALGS §6.10`); but
- **not canonical across isomorphism** (a renamed-but-otherwise-equivalent program may produce a different hash — this is the `weak` path).

The conditional annotation `canonical iff fingerprint_class = strong` is the operative discipline that records this dichotomy alongside the hash. **No record containing `cpg_order_hash` may omit the annotation.**

#### How to discharge INV-5 in code

1. The literal annotation string `"canonical iff fingerprint_class = strong"` is exposed as a **constant** from this module:
   ```python
   CPG_ORDER_HASH_ANNOTATION: Final[str] = "canonical iff fingerprint_class = strong"
   ```
   No other component may construct this string from substrings. Every emitter imports the constant.
2. The `CanonicalOrderResult` dataclass carries the annotation as a typed `Literal` field; downstream consumers cannot construct a `CanonicalOrderResult` without it.
3. `CMP-FND-01`, `CMP-FND-02`, `CMP-FND-03` schemas all carry a matching column / property / JSON key whose contents come from this constant. `DOC-PROVENANCE §3` shows the `cpg_order_hash_annotation TEXT GENERATED ALWAYS AS … STORED` column definition.
4. `TST-INV-5-CORE-03` asserts the annotation is present everywhere the hash is.

#### Conditional-canonicality contract (verbatim from `PLAN.md` item-4)

> The provenance field formerly named "canonical CPG hash" is renamed **`cpg_order_hash`** and is recorded with an explicit annotation: `canonical iff fingerprint_class = strong`. Same-source reproducibility (property (a)) holds for `cpg_order_hash` unconditionally; canonicality *across isomorphic-but-differently-written programs* holds only on the `strong` path.

#### Counter-example (do not write this code)

```python
# BAD — INV-5 violation: writes the hash without the annotation.
record = {"cpg_canonical_hash": result.cpg_order_hash.hex()}
```

```python
# BAD — INV-5 violation: renames the field, losing the conditional label.
record = {"canonical_cpg_hash": result.cpg_order_hash.hex(),
          "fingerprint_class": "strong"}
```

```python
# GOOD — INV-5 compliant.
from analysis.ordering import CPG_ORDER_HASH_ANNOTATION
record = {
    "cpg_order_hash":            result.cpg_order_hash.hex(),
    "cpg_order_hash_annotation": CPG_ORDER_HASH_ANNOTATION,
    "fingerprint_class":         result.fingerprint_class,
}
```

#### A `weak`-class finding must never be auto-suppressed across a refactor

`CMP-CORE-02` (`AC-CORE-02c`) and `CMP-FND-01` (`AC-FND-02a`) carry the operative discipline; this component's contribution is the `fingerprint_class` flag that gates the policy. See `DOC-INV §7.4 counter-example` for the auditor-export failure mode.

### 5.2 INV-1 — origin partition (passive)

This component does not set `origin`. It is consumed by both `deterministic-core` and `oracle-passthrough` paths. No discharge action here, but the hash MUST be available on both paths (oracle findings can still benefit from a canonical order — e.g. for cross-engine joins on `slice_fingerprint`).

### 5.3 INV-2 — versioned parameters (passive)

This component reads neither `S` nor `Env` directly. The `cpg_order_hash` is a function of the CPG only; the CPG itself is stamped with `env_digest` upstream by `CMP-SNAP-01`. Downstream emitters carry `(S_version, env_digest)` from their caller.

---

## 6. Dependency contract

`Depends-On:` **none** (`WBS.md §20`, Wave-1).

This component has no upstream component dependency. It depends only on:

- A library implementing 2-WL refinement and individualisation-refinement (vendored or implemented in `analysis/ordering.py`). No external graph-canonicalisation service.
- Python 3.x runtime as pinned in the worker image (`CMP-DEPLOY-02`).
- A `sha256` digest function from the standard library (`hashlib`).

This means `CMP-CORE-03` may start *immediately* in Wave-1. It is a **blocker** for `CMP-CORE-01` (via `Depends-On`) and `CMP-CORE-02` (transitive via `CMP-CORE-01`). It is therefore on the critical path for Stage A.

---

## 7. Failure modes and error contracts

### 7.1 Failure modes

| Mode | Detection | Response | Persisted state |
|---|---|---|---|
| `(B, T)` budget exhaustion on CFI-symmetric input | search-tree node counter ≥ `B` OR wall-clock ≥ `T` | fall through to stable-order fallback; set `fingerprint_class = "weak"`, `budget_exhausted = True` | hash + `weak` flag + annotation |
| Empty CPG (no nodes) | `len(cpg.nodes) == 0` | return `CanonicalOrderResult([], sha256(b""), "strong", ANNOTATION, False, …)` | trivial canonical |
| Malformed CPG (unreachable nodes, missing edge kinds) | runtime `ValueError` from parser | **raise** — do not silently downgrade; this is a `CMP-SNAP-01` bug | none; caller treats as snapshot failure |
| Wall-clock measurement skew (CI noise) | `elapsed_ms > T` reported by the OS but search-tree node count still < `B` | accept `weak` outcome — wall-clock is the authoritative cap per `CLAR-PARAM-01` | as above |

### 7.2 Distinguishing `weak`-class from a "true" failure

Critical conceptual point: **the stable-order fallback is *not* a failure of this component.** It is a defined output mode. The hash is still produced; it is still deterministic over the same source; it is still safe to persist. The `weak` flag is a *truthful self-label* on the conditional canonicality property, not an exception. Counter to the appearance of the name, `budget_exhausted=True` and `fingerprint_class="weak"` is a **successful invocation**.

Where `weak` matters operationally:

- `CMP-CORE-02` `AC-CORE-02c`: never auto-suppress a `weak`-class finding across a refactor (the cross-refactor identity claim does not hold on `weak`).
- `CMP-FND-01` `AC-FND-02a`: the baseline-lookup policy treats `weak` as "do not match the prior finding".
- `CMP-FND-03` auditor export: surfaces the annotation so an auditor knows the canonicality claim does not apply.

This is conceptually distinct from `CMP-CORE-02`'s `weak` fallback (which collapses to a witness-edge-sequence hash); the two coexist by design (both ride on the same conditional-canonicality annotation). See `DOC-INV §7.3` and `DOC-ALGS §6.7` for the operational contract.

### 7.3 No retries

The function is deterministic and synchronous. No retry policy. A second call on the same input yields the same output.

---

## 8. Provenance threading

This component does not directly write to provenance. It produces the **payload** that other components write. Per `.claude/rules/02-provenance.md` and `DOC-PROVENANCE §3`:

| Field written by downstream | Source | Required adjacency |
|---|---|---|
| `provenance_records.cpg_order_hash` (`CMP-FND-03`) | `result.cpg_order_hash` | must be paired with `cpg_order_hash_annotation` in the same row |
| `provenance_records.cpg_order_hash_annotation` | `CPG_ORDER_HASH_ANNOTATION` constant | column defaulted to the constant; CHECK constraint enforces literal match (`DOC-DB §3`) |
| `provenance_records.fingerprint_class` (`CMP-FND-03`) | `result.fingerprint_class` | CHECK constraint `IN ('strong','weak')` |
| `findings.cpg_order_hash` (`CMP-FND-02`) | (same) | (same) |
| SARIF `result.properties.cpg_order_hash` + `.cpg_order_hash_annotation` (`CMP-FND-01`) | (same) | JSON keys adjacent in serialised output per `DOC-SARIF` |
| Auditor export `{"cpg_order_hash", "cpg_order_hash_annotation", "fingerprint_class"}` (`CMP-FND-03`) | (same) | JSON-adjacent per `DOC-PROVENANCE §10` |

A code-review check for any new provenance/SARIF/export writer is: search for `cpg_order_hash`; the same record MUST also write the annotation.

---

## 9. Acceptance criteria cross-reference

| AC ID | Verbatim from `SDD.md §6 CMP-CORE-03` | Test ID | Label | Notes |
|---|---|---|---|---|
| `AC-CORE-03a` | "On CFI-style symmetric inputs the algorithm terminates within `(B, T)` and still yields a deterministic same-source order." | `TST-AC-CORE-03a` | `[UNIT]` | CFI graphs are designed to defeat 2-WL; the test asserts (i) termination within `(B, T)`, (ii) byte-identical same-source order across re-runs. Fed by `CMP-CORP-CPG-*` curated symmetric corpora. `[FORTHCOMING]` |
| `AC-CORE-03b` | "Budget-exhaustion rate on real code measured and < 1%." | `TST-AC-CORE-03b` | `[EMPIRICAL]` | Measured over `CMP-CORP-CANARY-01` (100 canary repos). Defaults `B = 2^16`, `T = 200ms` (`CLAR-PARAM-01` RESOLVED). `[FORTHCOMING]` |
| `AC-CORE-03c` | "The persisted hash field is named `cpg_order_hash` and carries the conditional-canonicality annotation everywhere it appears." | `TST-AC-CORE-03c` | `[INVARIANT]` | Asserts field name AND adjacency of `"canonical iff fingerprint_class = strong"` in: `provenance_records` row, SARIF `properties`, auditor export. Greps the codebase for any other variant ("`canonical_cpg_hash`", "`cpg_canonical_hash`") and fails on hit. `[FORTHCOMING]` |
| `TST-INV-5-CORE-03` | — (invariant test) | `TST-INV-5-CORE-03` | `[INVARIANT]` | The annotation invariant — runs against every emitter that touches a finding row. See `WBS.md §15.5` map. `[FORTHCOMING]` |

Determinism of this component's same-source output feeds into Gate 3 (Attestor, `CMP-CP-05`) by way of `AC-CORE-01a`: without a deterministic enumeration order, `CMP-CORE-01` cannot produce byte-identical pre-serialisation hashes.

---

## 10. Open questions

None at time of writing.

`CLAR-PARAM-01` (default `(B, T)` budget) is **RESOLVED** (`WBS.md §17`, 2026-05-23): `B = 2^16` search-tree nodes, `T = 200 ms` wall-clock.

If an Implementation Agent encounters ambiguity not covered here, file `CLAR-CORE-NN` in `WBS.md §17` per `.claude/rules/03-scope.md`. **Do not invent missing scope.**

---

## Appendix A. Pseudocode (informative)

```python
ANNOTATION: Final[str] = "canonical iff fingerprint_class = strong"

def canonical_order(cpg, *, B=2**16, T=0.200):
    t0 = time.monotonic()
    labels = _seed_labels(cpg)              # § 3.2 step 1
    labels = _wl_refine_to_fixpoint(cpg, labels)   # § 3.2 step 2
    partition = _partition_by_label(labels)

    if _partition_is_total(partition):
        order = _emit_order(partition)
        return _ok(order, "strong", budget_exhausted=False, elapsed=time.monotonic()-t0)

    # Tie-break: enclosing-declaration canonical order first, then bounded IR
    partition = _break_by_enclosing_decl(partition)
    if _partition_is_total(partition):
        order = _emit_order(partition)
        return _ok(order, "strong", budget_exhausted=False, elapsed=time.monotonic()-t0)

    try:
        partition = _individualise_refine(partition, B=B, T=T-(time.monotonic()-t0))
        order = _emit_order(partition)
        return _ok(order, "strong", budget_exhausted=False, elapsed=time.monotonic()-t0)
    except BudgetExhausted:
        order = _stable_order_fallback(partition)   # (decl_hash, struct_path, edge_kind)
        return _ok(order, "weak",   budget_exhausted=True,  elapsed=time.monotonic()-t0)


def _ok(order, klass, *, budget_exhausted, elapsed):
    h = hashlib.sha256()
    for nid in order:
        h.update(nid.to_bytes(8, "big", signed=False))
    return CanonicalOrderResult(
        canonical_order=order,
        cpg_order_hash=h.digest(),
        fingerprint_class=klass,
        annotation=ANNOTATION,
        budget_exhausted=budget_exhausted,
        elapsed_ms=elapsed * 1000.0,
    )
```

---

## Appendix B. Cross-references

- `PLAN.md §"Algorithm 5 — Canonical CPG ordering, and the item-4 provenance rename"`
- `SDD.md §6 CMP-CORE-03`
- `WBS.md §8 (component table)`, `§20 (DAG)`, `§17 CLAR-PARAM-01 RESOLVED`
- `DOC-ALGS §6` (algorithm reference)
- `DOC-INV §7` (INV-5 reference)
- `DOC-PROVENANCE §2.1, §3, §8.2, §10` (persistence + adjacency)
- `DOC-SARIF` (SARIF `properties.cpg_order_hash` + annotation)
- `DOC-DB §3` (column definitions + CHECK constraints)
- `DOC-PARTITION` (engine→origin; this component is partition-agnostic)
- `.claude/rules/01-invariants.md §INV-5`
- `.claude/rules/02-provenance.md`
