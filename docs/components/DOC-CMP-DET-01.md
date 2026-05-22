# DOC-CMP-DET-01 — Combinator DSL for taint specs

**Status:** ACTIVE (Phase 0 output)
**Source-of-truth lineage:** `SDD.md §5 CMP-DET-01`, `PLAN.md §"Non-distributive-spec rejector (owner of Algorithm 2's precondition) — and the item-2 restatement"`, `PLAN.md §"Algorithm 2 — Detection core as IFDS/IDE"`, `SDD.md §2 INV-4`, `WBS.md §6 CMP-DET-01`, `docs/cross-cutting/DOC-DSL.md`, `.claude/rules/01-invariants.md §INV-4`.

When this document conflicts with `PLAN.md` / `SDD.md` / `DOC-DSL.md`, those upstream documents win and this one is corrected (file a `CLAR-*` rather than editing this document inline).

---

## 1. Component identity

| Field | Value |
|---|---|
| **CMP ID** | `CMP-DET-01` |
| **Subsystem** | Detector Catalog |
| **Staging** | cross-cutting (Wave-1; no unmet dependencies) |
| **Depends-On** | none (`WBS.md §20`) |
| **Owner** | unassigned — see `CLAR-OWNER-01` (`WBS.md §17`) |
| **Tests** | `TST-AC-DET-01a` (Gate 1), `TST-AC-DET-01b`, `TST-INV-4-DET-01` |
| **CI gate** | `AC-DET-01a` is **Gate 1** under `CMP-CI-01` (`CLAUDE.md §15`) — release blocker |

---

## 2. Mandate

**SDD `Purpose:` (verbatim):**

> A declarative DSL whose primitives (`source`, `sink`, `sanitize`, `propagate`, sanctioned compositions) are distributive-by-construction over the finite fact domain. Owner of Algorithm 2's precondition (INV-4).

**Operational role.** `CMP-DET-01` is the operational owner of the IFDS/IDE order-independence theorem's hypothesis (`PLAN.md §"Algorithm 2"`; Reps–Horwitz–Sagiv 1995): Tabulation produces the unique meet-over-all-valid-paths solution only when flow functions are **distributive over a finite fact lattice**. The DSL discharges that hypothesis **by construction** — each primitive is distributive, the family is closed under the sanctioned compositions, and any submitted spec outside this grammar is **rejected at registration**, never analyzed. The DSL is not a decision procedure for distributivity of arbitrary functions (that property is undecidable); it is a decidable membership test against a fragment that is distributive by construction.

Downstream, `CMP-DET-02` runs the grammar/closure check at registration time, `CMP-CORE-01` consumes only specs that have cleared it, and the cubic worst-case Tabulation bound plus property (a) on the core partition follow.

---

## 3. Interface contract

### 3.1 Public Python primitives (constructors over the closed grammar)

The DSL is exposed in `analysis/ifds/dsl/` as four pinned primitive constructors plus a `Spec` aggregate. These are the **complete** primitive vocabulary (`SDD.md CMP-DET-01`, `WBS.md T-CMP-DET-01-01`). The signatures below are normative.

```python
# analysis/ifds/dsl/primitives.py

from dataclasses import dataclass
from typing import Literal, NewType

# ─── Access path pattern (argument grammar; not itself a primitive) ─────────
AccessPathPattern = NewType("AccessPathPattern", str)  # PEG-parsed per DOC-DSL §2
ArgRef            = NewType("ArgRef", str)             # "arg[0]" | "arg[name]"
FieldRef          = NewType("FieldRef", str)           # "field[name]" | "this.name"
ReturnRef         = Literal["ret"]


@dataclass(frozen=True)
class Source:
    """source(access-path-pattern): inject taint(p) into the out-set."""
    pattern: AccessPathPattern


@dataclass(frozen=True)
class Sink:
    """sink(access-path-pattern): identity transfer + read-out predicate."""
    pattern: AccessPathPattern


@dataclass(frozen=True)
class Sanitize:
    """sanitize(access-path-pattern): kill facts matching the pattern."""
    pattern: AccessPathPattern


@dataclass(frozen=True)
class Propagate:
    """propagate(source -> target): gen taint(target) when taint(source) ∈ X.

    Four sanctioned forms (PropagateBody):
      arg → ret    | arg → field   | field → ret   | field → field
    """
    source: ArgRef | FieldRef
    target: ReturnRef | FieldRef


Clause = Source | Sink | Sanitize | Propagate
```

### 3.2 Parsed-spec aggregate

```python
# analysis/ifds/dsl/spec.py

from dataclasses import dataclass
from typing import Literal

EngineTag    = Literal["ifds", "ide"]                  # DSL specs only
ClassName    = Literal[
    "injection", "path-traversal", "ssrf", "deserialization",
    "xss", "crypto-misuse", "authn-authz", "secrets", "dep-cve",
    "memory-safety",
]
Language     = Literal[
    "java", "python", "javascript", "typescript", "go", "ruby", "php",
]


@dataclass(frozen=True)
class Spec:
    """A parsed, closure-checked detector spec ready for CMP-DET-02 registration."""
    id:        str
    class_:    ClassName
    languages: tuple[Language, ...]
    engine:    EngineTag           # ifds | ide; semgrep/cpg-query/external rejected
    clauses:   tuple[Clause, ...]
```

### 3.3 Parser entry point

```python
# analysis/ifds/dsl/parser.py

def parse_spec(source_text: str, *, source_path: str | None = None) -> Spec:
    """Parse a DSL spec file (YAML wrapper around the PEG of DOC-DSL §2).

    Returns a frozen Spec on success.
    Raises DSLError with one of the E-DSL-001..009 codes on any rejection.
    Never returns a partially-valid Spec; failure is total.
    """
```

### 3.4 Distributivity proof-obligation registry

`AC-DET-01a` requires that **every** primitive and every sanctioned composition carry a machine-checked distributivity proof obligation, discharged exhaustively over a bounded finite-fact domain. The DSL boot sequence enumerates the primitive table and the obligation table; a missing or failing obligation refuses startup (`T-CMP-DET-01-02`).

```python
# analysis/ifds/dsl/proofs.py

from collections.abc import Callable

ProofObligation = Callable[[], bool]   # property test; returns True on discharge

def register_proof(primitive_id: str, obligation: ProofObligation) -> None:
    """Bind a discharged distributivity obligation to a primitive id."""

def all_obligations_discharged() -> bool:
    """DSL boot guard: every primitive and every sanctioned composition has a
    registered obligation that returned True under exhaustive enumeration over
    the bounded fact domain. CI gate 1; release blocker on False (AC-DET-01a)."""
```

### 3.5 Sanctioned composition (no operator types — composition is positional)

Per `DOC-DSL §4`, the DSL admits exactly:

1. **Clause conjunction** — a `Spec` is a list of clauses; semantics is the clause-wise pointwise union of transfers. Closed under union of distributive flow functions over a finite lattice (RHS'95 §3).
2. **Pattern alternation** — a single `AccessPathPattern` may match multiple program points; each match applies the same distributive `f_clause`. No within-grammar disjunction operator exists; alternation is implicit in the matcher.

The grammar admits **no** sequencing (`then`, `;`, `seq`), **no** conditional (`if`, `when`, `guard`), and **no** fixpoint (`fixpoint`, `closure`, `rec`). These exclusions are the operational meaning of *"the family is closed under the compositions the DSL permits"* in `PLAN.md`.

---

## 4. Inputs and outputs

### 4.1 Input: DSL spec file

YAML wrapper file under `detectors/<class>/specs/<id>.dsl.yaml`. The header (`id`, `class`, `languages`, `engine`) plus a `ClauseList` of `source` / `sink` / `sanitize` / `propagate` clauses. Full grammar: `DOC-DSL.md §2`. Specs with `engine ∈ {semgrep, cpg-query, external}` are **not** DSL files; they live alongside but outside the closure check (`E-DSL-009`).

### 4.2 Output: parsed `Spec` dataclass

The `parse_spec()` function returns a frozen `Spec` ready for `CMP-DET-02` registration. On any rejection it raises `DSLError(code, message, line, col, suggested_fix)` and returns nothing. There is no partial-success path.

### 4.3 Side effects

- **None on the file system.** `CMP-DET-01` is a pure parser + obligation registry. Persistence is `CMP-DET-02`'s responsibility.
- **Boot-time obligation enumeration.** At process start, `all_obligations_discharged()` is invoked; on `False` the process exits non-zero (`T-CMP-DET-01-02`). CI exercises this as `AC-DET-01a`.

### 4.4 Provenance fields written

`CMP-DET-01` does **not** write provenance fields to any finding row — it produces only parsed `Spec` objects. Provenance threading begins at `CMP-DET-02` (where `determinism_partition` is derived from `engine`) and `CMP-ORCH-03` (where `origin` is stamped on each emitted finding). See `DOC-PARTITION §4` and `.claude/rules/02-provenance.md`.

---

## 5. Invariants touched

| Inv | How this component discharges it | Test |
|---|---|---|
| **INV-4** (one-sided undecidable approximations) | **Owner.** The DSL is the operational owner of Algorithm 2's distributivity precondition. The required **safe direction** is: any spec outside the distributive-by-construction combinator DSL is **rejected at registration**, never analyzed. The grammar is the decidable membership test; rejection is total (no partial parse, no silent acceptance). | `TST-INV-4-DET-01` |
| **INV-1, INV-2, INV-3, INV-5, INV-6** | Pass-through. `CMP-DET-01` emits no findings and writes no provenance fields; downstream components (`CMP-DET-02`, `CMP-ORCH-03`, `CMP-FND-*`) carry the rest. | n/a |

### 5.1 INV-4 discharge detail (the safe-direction contract)

Verbatim from `.claude/rules/01-invariants.md §INV-4`:

> Required soundness direction: any spec outside the distributive DSL is **rejected at registration**, never analyzed.
> Falsifier: `TST-AC-DET-01b` (non-DSL spec rejected with precise diagnostic).

The owning module name is `analysis/ifds/dsl/`. A registered combinator without its discharged distributivity proof obligation refuses CI by construction; the registry's startup check enumerates the primitive table and the obligation table and refuses to boot on a mismatch (`T-CMP-DET-01-02`).

A counter-example that would falsify INV-4 ownership: a DSL parser that silently accepts a non-distributive spec, or a registration check that admits an embedded Python lambda. Both are explicitly forbidden by `AC-DET-01b` and produce a precise rejection diagnostic per §7.

---

## 6. Dependency contract

`CMP-DET-01` has **no** `Depends-On` entries (`WBS.md §20`; Wave-1 component).

The component therefore makes no assumptions about any upstream artifact. Its outputs are consumed by:

- `CMP-DET-02` — runs `parse_spec()` plus the registry / closure check at registration.
- `CMP-CORE-01` — consumes only specs that have cleared `CMP-DET-02`. The IFDS Tabulation algorithm requires the distributivity precondition; the DSL owns it.

---

## 7. Failure modes and error contracts

The DSL parser raises `DSLError(code, message, line, col, suggested_fix)` on every rejection. Codes are stable identifiers; downstream tooling (`CMP-DET-02 AC-DET-02a`) matches on them.

### 7.1 Diagnostic code table (verbatim from `DOC-DSL §6`)

| Code | Escape attempt | Example | Diagnostic |
|---|---|---|---|
| **`E-DSL-001`** | Raw regex on bytecode/source | `source(re.compile(r".*\.execute\("))` | `raw regex outside AccessPathPattern grammar` |
| **`E-DSL-002`** | Embedded Semgrep YAML | `propagate(semgrep: { pattern: ... })` | `embedded oracle pattern in DSL spec — use engine=semgrep instead` |
| **`E-DSL-003`** | Embedded CodeQL / cpg-query | `sink(cpg.method("foo").caller)` | `embedded cpg-query expression — use engine=cpg-query instead` |
| **`E-DSL-004`** | Raw lambda / Python callable | `sanitize(lambda f: f.is_xss())` | `non-declarative callable in DSL spec` |
| **`E-DSL-005`** | Sequencing combinator | `source(p1) then propagate(arg→ret) then sink(p2)` | `sequencing operator 'then' not in sanctioned compositions (§4.3)` |
| **`E-DSL-006`** | Conditional combinator | `if matches(p) then propagate(...) else sanitize(...)` | `conditional operator not in sanctioned compositions (§4.3)` |
| **`E-DSL-007`** | User fixpoint | `fixpoint(propagate(arg→ret))` | `fixpoint operator not in sanctioned compositions (§4.3)` |
| **`E-DSL-008`** | Unknown primitive head | `taint_flow(p)` | `unknown primitive 'taint_flow'; expected one of {source, sink, sanitize, propagate}` |
| **`E-DSL-009`** | `engine` not in `{ifds, ide}` for a DSL-parsed spec | `engine: semgrep` inside `detectors/<class>/specs/*.dsl.yaml` | `engine=semgrep specs do not parse through the DSL — file under specs/oracle/` |

Every diagnostic is structured (`{code, message, line, col, suggested_fix}`) and is emitted before any registration side effect; rejection is total.

### 7.2 Boot-time failure (proof obligations)

`all_obligations_discharged()` runs at DSL boot. On `False`:

1. Process exits non-zero with `E-DSL-BOOT-001: combinator without discharged distributivity obligation`.
2. The naming of the missing obligation is included in the diagnostic.
3. CI gate 1 (`AC-DET-01a`) flips red; no worker image publishes (`AC-DEPLOY-04b`).

### 7.3 No fallback paths

`CMP-DET-01` has **no** degraded / fallback path. The grammar membership test is decidable; either a spec is in the grammar (parse succeeds, `Spec` returned) or it is not (parse fails, `DSLError` raised). There is no "best-effort" mode.

### 7.4 Sanctioned-composition examples

```yaml
# WELL-FORMED: clause conjunction (multiple clauses; pointwise union of transfers)
id: "python-cmd-injection"
class: "injection"
languages: ["python"]
engine: "ifds"

source(flask.request.args.get(*))
source(flask.request.form.get(*))
propagate(arg[0] → ret)
sanitize(shlex.quote(arg[0]))
sink(subprocess.Popen(arg[0]))
```

```yaml
# WELL-FORMED: pattern alternation (one pattern matches many program points)
id: "java-jdbc-sqli"
class: "injection"
languages: ["java"]
engine: "ifds"

source(?T<:HttpServletRequest.getParameter(*))     # matches every concrete subtype
sink(?T<:Statement.executeQuery(arg[0]))            # matches every Statement subtype
```

```yaml
# WELL-FORMED: scoping via class membership + access-path pattern
id: "java-jackson-untrusted-deser"
class: "deserialization"
languages: ["java"]
engine: "ifds"

source(?T<:HttpServletRequest.getInputStream)
propagate(arg[0] → ret)
sink(?T<:ObjectMapper.readValue(arg[0]))
```

### 7.5 Malformed-spec examples (rejected at registration)

```yaml
# REJECTED — E-DSL-008 (unknown primitive)
id: "broken-1"
class: "injection"
languages: ["java"]
engine: "ifds"
taint_flow(?T<:Http.getParameter → ?T<:Statement.execute)
```

```yaml
# REJECTED — E-DSL-002 (embedded oracle pattern)
id: "broken-2"
class: "xss"
languages: ["javascript"]
engine: "ifds"
source(document.location)
propagate(semgrep: { pattern: "$X = $TAINTED" })
sink(innerHTML)
```

```yaml
# REJECTED — E-DSL-005 (sequencing operator not in sanctioned compositions)
id: "broken-3"
class: "ssrf"
languages: ["java"]
engine: "ifds"
source(?T<:HttpRequest.getHeader("Host"))
  then propagate(arg[0] → ret)
  then sink(?T<:URL.openConnection)
```

All three rejections produce a structured diagnostic with location and suggested fix per `DOC-DSL §8`.

---

## 8. Provenance threading

`CMP-DET-01` writes **no** provenance fields. The four threaded provenance surfaces (`origin`, `S_version`, `env_digest`, `cpg_order_hash`) are populated downstream:

| Provenance field | Set by | Where |
|---|---|---|
| `origin` | `CMP-ORCH-03` | per-finding stamp from `detector.engine` |
| `determinism_partition` | `CMP-DET-02` | derived from `engine` at registration (`AC-DET-02c`) |
| `S_version` | `CMP-ORCH-01` | from scan submission |
| `env_digest` | `CMP-SNAP-01` | from worker container image digest |
| `cpg_order_hash` | `CMP-CORE-03` | with conditional-canonicality annotation (INV-5) |

The DSL emits no findings; therefore the four-field threading rule (`.claude/rules/02-provenance.md`) applies to consumers, not to `CMP-DET-01` itself.

---

## 9. Acceptance criteria cross-reference

### 9.1 SDD acceptance criteria (verbatim)

> **AC-DET-01a:** Each combinator carries a machine-checked distributivity proof obligation (`f(X ∪ Y) = f(X) ∪ f(Y)` exhaustively over the bounded domain); CI fails if a combinator lacks a discharged obligation.
>
> **AC-DET-01b:** The DSL grammar admits no escape hatch to non-DSL code; a spec embedding arbitrary code is rejected, not analyzed.

### 9.2 AC → TST mapping

| AC | TST id | Kind | Hard gate | Notes |
|---|---|---|---|---|
| `AC-DET-01a` | `TST-AC-DET-01a` | `[UNIT]` | **yes — Gate 1** (release blocker) | Exhaustive enumeration over the bounded fact domain (`|D| ≤ 12` recommended, pinned at implementation). One obligation per primitive; `propagate` has four (one per `PropagateBody` form). Closure-step obligation for clause conjunction. |
| `AC-DET-01b` | `TST-AC-DET-01b` | `[NEGATIVE]` | yes | One test per `E-DSL-001..009`; asserts structured diagnostic. |
| `INV-4` | `TST-INV-4-DET-01` | `[INVARIANT]` | yes | Cross-reference of safe-direction discharge. |

### 9.3 Proof-obligation template (`AC-DET-01a`, from `DOC-DSL §5`)

```python
@pytest.mark.unit
def test_distributivity_<primitive_or_composition>() -> None:
    """Discharge AC-DET-01a for <primitive_or_composition>.

    Distributivity: f(X ∪ Y) = f(X) ∪ f(Y) for all X, Y ⊆ D.

    Bound: |D| ≤ 12 (design recommendation; exhaustive enumeration is
    tractable at this size, ≥ 4096 (X, Y) pairs per primitive). The
    operational bound is pinned by CMP-DET-01 at implementation; the
    requirement from AC-DET-01a is exhaustive over a bounded domain,
    not a specific size.
    """
    f = build_flow_function(<primitive_or_composition_under_test>)
    D = enumerate_bounded_fact_domain(max_size=12)
    for X in powerset(D):
        for Y in powerset(D):
            left  = f(X | Y)
            right = f(X) | f(Y)
            assert left == right, (
                f"distributivity violated at X={X}, Y={Y}: "
                f"f(X∪Y)={left}, f(X)∪f(Y)={right}"
            )
```

Properties of the template:

1. **Exhaustive, not sampled.** Property-based sampling is **not** a substitute; `AC-DET-01a` requires exhaustive enumeration over the bounded domain.
2. **One test per primitive, one per sanctioned composition.** `propagate` has four obligations (`arg→ret`, `arg→field`, `field→ret`, `field→field`).
3. **CI gate.** A missing or failing obligation refuses worker-image publication (`AC-DEPLOY-04b`).
4. **Authored alongside the primitive.** Adding a combinator without its discharged obligation is a release blocker.

The pre-existing scaffold in `tests/unit/test_dsl_proofs.py` (currently `xfail`/`skip`) holds the test ids and will be hydrated when `CMP-DET-01` lands.

### 9.4 Per-primitive distributivity proofs (one-line)

| Primitive | Transfer | One-line distributivity proof |
|---|---|---|
| `source(p)` | gen `{taint(p)}` | `(X ∪ Y) ∪ {t} = (X ∪ {t}) ∪ (Y ∪ {t})` |
| `sink(p)` | identity + read-out | `id(X ∪ Y) = X ∪ Y = id(X) ∪ id(Y)`; read-out is off-lattice |
| `sanitize(p)` | kill `K_p` | `(X ∪ Y) \ K = (X \ K) ∪ (Y \ K)` |
| `propagate(s→t)` | gen `{taint(t)}` cond. on `taint(s) ∈ X` | `g(X∪Y) = (X∪Y) ∪ A(X∪Y) = (X∪A(X)) ∪ (Y∪A(Y)) = g(X) ∪ g(Y)` |

Closure under clause conjunction: a finite union of distributive functions over a powerset lattice is distributive (RHS'95 §3).

---

## 10. Open questions

| CLAR | Status | Bearing on this component |
|---|---|---|
| `CLAR-OWNER-01` | DEFERRED | Module owner unassigned. |
| `CLAR-PARAM-01` | RESOLVED | Algorithm 1/3/5 parameters; **does not** cover the DSL's bounded-fact-domain size for exhaustive enumeration, which is pinned by `CMP-DET-01` at implementation (recommended `|D| ≤ 12`, per `DOC-DSL §5`). |

No DSL-specific clarification is currently open. New `CLAR-DET-*` items should be filed in `WBS.md §17` if the grammar requires extension; do not extend inline (`RULE-4`).

---

## 11. References

- `PLAN.md §"Non-distributive-spec rejector (owner of Algorithm 2's precondition) — and the item-2 restatement"` — DSL closure check restatement.
- `PLAN.md §"Algorithm 2 — Detection core as IFDS/IDE"` — distributivity hypothesis of Tabulation; Reps–Horwitz–Sagiv 1995.
- `SDD.md §5 CMP-DET-01` — verbatim AC source.
- `SDD.md §2 INV-4` — one-sided undecidable approximations.
- `WBS.md §6` — task list `T-CMP-DET-01-01..03`.
- `WBS.md §20` — dependency DAG (DET-01 → []).
- `docs/cross-cutting/DOC-DSL.md` — full PEG, primitive catalog, sanctioned compositions, escape-hatch table, proof-obligation template, worked examples.
- `docs/cross-cutting/DOC-INV.md` — INV-4 owner cross-reference.
- `docs/cross-cutting/DOC-PARTITION.md` — `engine → origin` mapping (consumer of DSL output).
- `docs/cross-cutting/DOC-PROVENANCE.md` — provenance threading rules.
- `.claude/rules/00-global.md`, `.claude/rules/01-invariants.md §INV-4`, `.claude/rules/03-scope.md`, `.claude/rules/05-determinism.md`.
- `tests/unit/test_dsl_proofs.py` — Gate-1 stub harness.

---

*Document end. Status: ACTIVE. Next review: at first acceptance of `CMP-DET-01` `DONE`.*
