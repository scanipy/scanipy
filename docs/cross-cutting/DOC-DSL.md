# DOC-DSL — Combinator DSL grammar reference

**Owner:** Documentation Manager Agent
**Status:** ACTIVE (Phase 0 cross-cutting deliverable)
**Source-of-truth lineage:**

- `PLAN.md §"Non-distributive-spec rejector (owner of Algorithm 2's precondition) — and the item-2 restatement"`
- `PLAN.md §"Algorithm 2 — Detection core as IFDS/IDE"`
- `SDD.md CMP-DET-01` (combinator DSL), `SDD.md CMP-DET-02` (registry + closure check), `SDD.md CMP-DET-03` (class plugin scaffolding)
- `SDD.md §2 INV-4` (one-sided undecidable approximations)
- `.claude/rules/01-invariants.md §INV-4`
- `WBS.md §6 CMP-DET-01` (task list `T-CMP-DET-01-01..03`), `WBS.md §6 CMP-DET-02`
- `tests/unit/test_dsl_proofs.py` (Gate-1 stubs for `AC-DET-01a`)

Where this document and the source-of-truth above disagree, the source-of-truth wins; file a `CLAR-*` against `WBS.md §17` rather than editing this document inline.

---

## 1. Purpose

DOC-DSL is the canonical reference for the **closed grammar** that defines every taint-style detector spec consumable by the IFDS/IDE tabulation solver (`CMP-CORE-01`, Algorithm 2). The grammar is the operational owner of Algorithm 2's precondition (`INV-4`): the IFDS order-independence theorem (Reps–Horwitz–Sagiv, POPL 1995) holds only over **distributive, finite-domain** flow functions, and the DSL discharges that hypothesis **by construction** — every primitive is distributive, the family is closed under the sanctioned compositions, and any submitted spec outside this grammar is rejected at registration rather than analysed.

The DSL is therefore not a decision procedure for distributivity of arbitrary functions (that property is undecidable for code presented as a black box). It is a **grammar + closure check**: a decidable membership test against a fragment that is distributive by construction.

> *"Detector specs are not arbitrary code. They are declarative data in a fixed combinator DSL whose primitives … are each distributive by construction, and the family is closed under the compositions the DSL permits. The registration check is therefore a grammar/closure check; it verifies that a submitted spec lies within the distributive-by-construction combinator DSL."* — `PLAN.md`, item-2 restatement.

Two cross-cutting consequences:

1. **`CMP-DET-02`** runs the grammar/closure check at registration and rejects out-of-DSL specs with a precise diagnostic (`AC-DET-02a`, `T-CMP-DET-02-02`).
2. **`CMP-CORE-01`** consumes only specs that have cleared the registry. The cubic worst-case Tabulation bound applies and the order-independence theorem licences `(a)` reproducibility on the core partition.

If a class of detection requires an expressive primitive outside this grammar, that class ships **`oracle-passthrough`** (e.g. via `engine=semgrep` or `engine=cpg-query`); it does **not** acquire a deterministic-core finding through a DSL escape (`AC-DET-01b`).

---

## 2. Grammar (PEG)

The grammar below is the **canonical PEG**. It is normative; the implementation in `analysis/ifds/dsl/` must accept exactly this language. The four primitive heads (`source`, `sink`, `sanitize`, `propagate`) are pinned by `SDD.md CMP-DET-01` and `WBS.md T-CMP-DET-01-01`.

```peg
# ─────────────────────────────────────────────────────────────────────────
# Top-level spec — what gets loaded from `detectors/<class>/specs/*.yaml`
# ─────────────────────────────────────────────────────────────────────────
Spec            ← SpecHeader ClauseList

SpecHeader      ← "id:"        StringLiteral
                  "class:"     ClassName
                  "languages:" LanguageList
                  "engine:"    EngineTag

EngineTag       ← "ifds" / "ide"               # core-eligible engines only;
                                                # `semgrep`/`cpg-query`/`external`
                                                # MUST NOT appear in DSL specs

ClauseList      ← Clause (Newline Clause)*

Clause          ← SourceClause
                / SinkClause
                / SanitizeClause
                / PropagateClause

# ─────────────────────────────────────────────────────────────────────────
# Primitive heads — pinned by SDD CMP-DET-01
# ─────────────────────────────────────────────────────────────────────────
SourceClause    ← "source"    "(" AccessPathPattern ")"
SinkClause      ← "sink"      "(" AccessPathPattern ")"
SanitizeClause  ← "sanitize"  "(" AccessPathPattern ")"
PropagateClause ← "propagate" "(" PropagateBody ")"

PropagateBody   ← ArgRef "→" ReturnRef                # arg → return
                / ArgRef "→" FieldRef                  # arg → field
                / FieldRef "→" ReturnRef               # field → return
                / FieldRef "→" FieldRef                # field → field

# ─────────────────────────────────────────────────────────────────────────
# Access-path pattern — the **argument** to source/sink/sanitize.
# This is a pattern grammar, NOT a top-level primitive.
# ─────────────────────────────────────────────────────────────────────────
AccessPathPattern
                ← Receiver "." MemberAccessPath
                / Receiver

Receiver        ← FQN                                  # fully-qualified name
                / TypePattern                          # e.g. `?T<:Servlet`
                / "*"                                  # wildcard

MemberAccessPath
                ← MemberSelector ("." MemberSelector)*

MemberSelector  ← FieldName
                / MethodName "(" ArgSelector ")"

ArgSelector     ← "*"                                  # any arg
                / ArgIndex                              # 0-based positional
                / ParameterName                         # named parameter
                / ArgSelector "," ArgSelector

ArgRef          ← "arg" "[" ArgIndex "]"
                / "arg" "[" ParameterName "]"

ReturnRef       ← "ret"

FieldRef        ← "field" "[" FieldName "]"
                / "this" "." FieldName

# ─────────────────────────────────────────────────────────────────────────
# Sanctioned composition operators — see §4
# ─────────────────────────────────────────────────────────────────────────
# Composition is positional: clauses are conjoined (set-union of facts
# across clauses); ordering of clauses within a Spec carries no semantic
# weight. No within-grammar sequencing, conditional, or recursive
# combinator is admitted.
# ─────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────
# Lexical
# ─────────────────────────────────────────────────────────────────────────
FQN             ← Identifier ("." Identifier)*
TypePattern     ← "?" Identifier "<:" FQN              # bounded type variable
Identifier      ← [A-Za-z_] [A-Za-z0-9_]*
ClassName       ← "injection" / "path-traversal" / "ssrf" / "deserialization"
                / "xss" / "crypto-misuse" / "authn-authz"
                / "secrets" / "dep-cve" / "memory-safety"
LanguageList    ← "[" Language ("," Language)* "]"
Language        ← "java" / "python" / "javascript" / "typescript"
                / "go" / "ruby" / "php"
StringLiteral   ← '"' [^"]* '"'
ArgIndex        ← [0-9]+
FieldName       ← Identifier
ParameterName   ← Identifier
MethodName      ← Identifier
Newline         ← "\n"
```

### Notes on grammar scope

- **Four primitive heads only.** `source`, `sink`, `sanitize`, `propagate` are the complete primitive vocabulary (`SDD.md CMP-DET-01`, `WBS.md T-CMP-DET-01-01`). The grammar admits no other primitive. Adding one is a `CLAR-*` event, never an inline extension.
- **`access-path-pattern`** is the **argument grammar** to the first three primitives, not itself a primitive. This corresponds to the parenthetical in the PLAN restatement: *"`source(access-path-pattern)`"*.
- **`taint_flow`** is **not** a DSL primitive. It is solver semantics (the meet-over-all-valid-paths solution computed by the Tabulation algorithm). User-facing specs declare sources, sinks, sanitizers, and propagators; the solver derives the flow.
- **`EngineTag`** for a DSL spec MUST be `ifds` or `ide`. Specs with `engine ∈ {semgrep, cpg-query, external}` are oracle-passthrough specs and are not parsed by this DSL; they live alongside but outside the closure check (`SDD.md CMP-DET-02 AC-DET-02c`).

---

## 3. Primitive catalog

For each primitive, this section gives the type signature, the IFDS semantic definition, the distributivity contract, and the proof-obligation reference per `AC-DET-01a`.

The IFDS fact lattice is the powerset of a finite domain `D` of program facts (taint markers attached to access paths). Flow functions have type `f : 2^D → 2^D` and are required to be **distributive**: `f(X ∪ Y) = f(X) ∪ f(Y)` for all `X, Y ⊆ D` (`PLAN.md §"Algorithm 2"`; Reps–Horwitz–Sagiv 1995, §3).

### 3.1 `source(access-path-pattern)`

**Type signature:**

```
source : AccessPathPattern → FlowFunction
       : pattern p ↦ (X ↦ X ∪ { taint(p) })
```

**Semantics.** At every call site whose receiver/argument matches `p`, inject the fact `taint(p)` into the IFDS fact set flowing out of the call. Acts only on the **out-set** of the matched node.

**Distributivity contract.** `f_source(X ∪ Y) = (X ∪ Y) ∪ {taint(p)} = (X ∪ {taint(p)}) ∪ (Y ∪ {taint(p)}) = f_source(X) ∪ f_source(Y)`. Distributive by construction; the proof is the one-line identity above on the powerset lattice.

**Proof obligation (per `AC-DET-01a`).** Property test in `tests/unit/test_dsl_proofs.py` instantiates `source` for a representative pattern, picks `X, Y` uniformly from `2^D` over a bounded `D` (default `|D| ≤ 12`, exhaustive enumeration), and asserts `f(X ∪ Y) = f(X) ∪ f(Y)` for every pair. A single counterexample is a release blocker.

### 3.2 `sink(access-path-pattern)`

**Type signature:**

```
sink : AccessPathPattern → FlowFunction × ReportPredicate
     : pattern p ↦ (identity, λX. ∃t ∈ X . matches(t, p))
```

**Semantics.** Identity on the fact set (sinks do **not** mutate facts — they observe them). The `ReportPredicate` fires when any fact in the in-set matches the sink pattern; a positive predicate emits a Tabulation witness which the worker (`CMP-ORCH-03`) lifts to a finding.

**Distributivity contract.** The fact-mutating component is the identity function, which is trivially distributive. The `ReportPredicate` is **monotone, not distributive** — but it is not a flow function; it is a tabulation read-out that the solver fires once per reachable sink-fact pair. Distributivity is required of flow functions, not of read-outs (RHS'95 §3 vs §4). The DSL therefore separates the two roles cleanly: the read-out lives off the IFDS lattice.

**Proof obligation.** Identity-flow distributivity is a one-line proof; the property test asserts `id(X ∪ Y) = X ∪ Y = id(X) ∪ id(Y)` for the bounded `D`. Read-out predicate is **not** subject to the distributivity proof; it is subject to the matching-correctness suite (`TST-AC-DET-02b`).

### 3.3 `sanitize(access-path-pattern)`

**Type signature:**

```
sanitize : AccessPathPattern → FlowFunction
         : pattern p ↦ (X ↦ X \ { t ∈ X : matches(t, p) })
```

**Semantics.** Remove from the IFDS fact set every taint fact whose access path matches `p`. The IFDS fact lattice is a powerset, so set difference of a fixed predicate-defined subset is a **kill** transfer in the IFDS sense (`f(X) = X \ K_p` for a fixed predicate-defined `K_p`).

**Distributivity contract.** Set difference distributes over union: `(X ∪ Y) \ K = (X \ K) ∪ (Y \ K)`. Distributive by construction.

**Proof obligation.** Property test asserts `f_sanitize(X ∪ Y) = f_sanitize(X) ∪ f_sanitize(Y)` exhaustively over the bounded `D` for the configured pattern's kill-set.

### 3.4 `propagate(arg → ret | field)`

**Type signature:**

```
propagate : (Source × Target) → FlowFunction
          : (s, t) ↦ (X ↦ X ∪ { taint(t) : taint(s) ∈ X })
```

where `Source, Target ∈ {ArgRef, ReturnRef, FieldRef}` per the grammar (`PropagateBody`).

**Semantics.** A **gen** transfer that copies taint from a source position to a target position at the matched call site: if the source is tainted in the in-set, add taint on the target to the out-set; never removes facts.

**Distributivity contract.** Let `g(X) = X ∪ { taint(t) : taint(s) ∈ X }`. The added-set `A(X) = { taint(t) : taint(s) ∈ X }` is **monotone in `X`** *and* satisfies `A(X ∪ Y) = A(X) ∪ A(Y)` (because `taint(s) ∈ X ∪ Y ⇔ taint(s) ∈ X ∨ taint(s) ∈ Y`). Hence `g(X ∪ Y) = (X ∪ Y) ∪ A(X ∪ Y) = (X ∪ A(X)) ∪ (Y ∪ A(Y)) = g(X) ∪ g(Y)`. Distributive by construction.

**Proof obligation.** Property test instantiates `propagate` for all four `PropagateBody` forms (`arg→ret`, `arg→field`, `field→ret`, `field→field`) and asserts `f(X ∪ Y) = f(X) ∪ f(Y)` exhaustively over the bounded `D`. Each form is its own proof obligation; a failure of any one is a release blocker.

### 3.5 Summary table

| Primitive | Transfer kind | Distributivity proof | Test |
|---|---|---|---|
| `source(p)` | gen of `taint(p)` | `(X∪Y)∪{t} = (X∪{t})∪(Y∪{t})` | `test_distributivity_source` |
| `sink(p)` | identity + read-out | `id(X∪Y) = id(X)∪id(Y)`; read-out is off-lattice | `test_distributivity_sink_identity` |
| `sanitize(p)` | kill of `K_p` | `(X∪Y)\K = (X\K)∪(Y\K)` | `test_distributivity_sanitize` |
| `propagate(s→t)` | gen of `taint(t)` conditioned on `taint(s)` | `(X∪Y)∪A(X∪Y) = (X∪A(X))∪(Y∪A(Y))` | `test_distributivity_propagate` (×4 forms) |

Each row corresponds to one or more discharged proof obligations under `AC-DET-01a`. The registry refuses to start if any obligation is missing (`T-CMP-DET-01-02`).

---

## 4. Sanctioned compositions

The DSL admits exactly the following compositional structure. Anything outside this list is a registration-time rejection.

### 4.1 Clause conjunction (multiple clauses in one spec)

A spec is a list of clauses (`SourceClause | SinkClause | SanitizeClause | PropagateClause`). The semantics of the spec is the **clause-wise union of transfers** at each program point: each clause's flow function is evaluated independently against the in-set, and the out-set is the union.

```
spec(X) = ⋃_{c ∈ clauses(spec)} c(X)
```

**Distributivity.** A finite union of distributive functions is distributive: `(⋃ f_i)(X ∪ Y) = ⋃ f_i(X ∪ Y) = ⋃ (f_i(X) ∪ f_i(Y)) = (⋃ f_i(X)) ∪ (⋃ f_i(Y))`. Closure under union is a standard IFDS framework result (RHS'95 §3, distributive flow functions are closed under pointwise union over the powerset lattice).

**Proof obligation.** Composition test: pick two arbitrary distributive primitives, form their union, and assert distributivity of the union over the bounded `D`. Discharged once for the closure step; combined with per-primitive obligations to license arbitrary clause-conjunction specs.

### 4.2 Pattern alternation (one pattern matches multiple call sites)

A single `AccessPathPattern` may match multiple program points (e.g., `*.execute(*)`). The pattern matcher is a pure predicate over the program-graph node; the flow function `f_clause(X)` is applied independently at every matched node by the IFDS solver (`CMP-CORE-01`). No within-grammar disjunction operator exists — alternation is implicit in the matcher.

**Distributivity.** Each matched node applies the *same* distributive `f_clause`. Soundness is the per-primitive proof; no additional obligation.

### 4.3 No within-grammar sequencing, conditional, or recursion

The DSL **does not** admit:

- A `then` / `seq` / `;` combinator that chains two flow functions sequentially within a spec. (Reason: the IFDS framework already composes per-node transfers along graph edges; user-level sequencing would re-derive solver semantics and would not generally preserve distributivity for arbitrary user functions.)
- An `if` / `when` / `guard` combinator that conditions a transfer on a fact predicate. (Reason: conditional kill/gen sets that depend on the in-set fail the `f(X ∪ Y) = f(X) ∪ f(Y)` identity unless the predicate is itself fact-independent, in which case it collapses to one of the four primitives.)
- A `fixpoint` / `closure` / `rec` combinator that iterates a transfer. (Reason: solver semantics already computes the fixpoint over the supergraph; user-level fixpoints break finiteness of the fact domain.)

These three exclusions are the operational meaning of *"the family is closed under the compositions the DSL permits"* in `PLAN.md`. Specs that attempt them are rejected by the parser (`T-CMP-DET-01-03`).

---

## 5. Proof-obligation template

`AC-DET-01a` requires that every primitive and every sanctioned composition carry a **machine-checked distributivity proof obligation**, discharged exhaustively over a bounded fact domain. The proof obligation has the shape that `tests/unit/test_dsl_proofs.py` will assume once `CMP-DET-01` is `DONE`:

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

Key properties of the template:

1. **Exhaustive, not sampled.** The bounded domain is small enough (recommended `|D| ≤ 12`, configurable; final size pinned by `CMP-DET-01` at implementation) that all `2^|D| × 2^|D|` pairs are enumerated. A property-based sampling test is **not** a substitute — `AC-DET-01a` requires exhaustive enumeration over the bounded domain.
2. **One test per primitive, one per composition.** No primitive shares a proof obligation with another. The `propagate` primitive has four forms (`arg→ret`, `arg→field`, `field→ret`, `field→field`) and therefore four obligations.
3. **CI gate.** `AC-DET-01a` is **Gate 1** under `CMP-CI-01` (`CLAUDE.md §15`). A missing or failing obligation is a release blocker; CI refuses to publish a worker image (`AC-DEPLOY-04b`).
4. **Authored alongside the primitive.** A new combinator without its discharged obligation fails CI by construction — the registry's startup check enumerates the primitive table and the obligation table and refuses to boot on a mismatch (`T-CMP-DET-01-02`).

---

## 6. Non-grammar escape hatches (rejected at registration)

`AC-DET-01b` mandates that the DSL admit **no escape hatch** to non-DSL code. The following are explicitly rejected by the registry parser (`T-CMP-DET-01-03`, `T-CMP-DET-02-02`). Each row gives the diagnostic the parser emits.

| Escape attempt | Example | Diagnostic |
|---|---|---|
| Raw regex on bytecode/source | `source(re.compile(r".*\.execute\("))` | `E-DSL-001: raw regex outside AccessPathPattern grammar` |
| Embedded Semgrep YAML | `propagate(semgrep: { pattern: ... })` | `E-DSL-002: embedded oracle pattern in DSL spec — use engine=semgrep instead` |
| Embedded CodeQL/cpg-query | `sink(cpg.method("foo").caller)` | `E-DSL-003: embedded cpg-query expression — use engine=cpg-query instead` |
| Raw lambda / Python callable | `sanitize(lambda f: f.is_xss())` | `E-DSL-004: non-declarative callable in DSL spec` |
| Sequencing combinator | `source(p1) then propagate(arg→ret) then sink(p2)` | `E-DSL-005: sequencing operator 'then' not in sanctioned compositions (§4.3)` |
| Conditional combinator | `if matches(p) then propagate(...) else sanitize(...)` | `E-DSL-006: conditional operator not in sanctioned compositions (§4.3)` |
| User fixpoint | `fixpoint(propagate(arg→ret))` | `E-DSL-007: fixpoint operator not in sanctioned compositions (§4.3)` |
| Unknown primitive head | `taint_flow(p)` | `E-DSL-008: unknown primitive 'taint_flow'; expected one of {source, sink, sanitize, propagate}` |
| `engine` not in `{ifds, ide}` for a DSL-parsed spec | `engine: semgrep` inside `detectors/<class>/specs/*.dsl.yaml` | `E-DSL-009: engine=semgrep specs do not parse through the DSL — file under specs/oracle/` |

These escape-hatch attempts are **valid in oracle-passthrough detectors** when expressed in their native form (`engine ∈ {semgrep, cpg-query, external}`) and not parsed by this DSL. They are never embedded inside a `deterministic-core` spec.

---

## 7. Registration check semantics

`CMP-DET-02` (`T-CMP-DET-02-02`) executes the following check at every registry-load for every spec under `detectors/<class>/specs/`:

```
register(spec) :=
  1. parse(spec) against the PEG in §2 — reject with E-DSL-* on syntax error
  2. for every primitive instance in spec.clauses:
       confirm a discharged distributivity proof exists in the obligations table
       (built once at DSL boot from §3)
  3. confirm spec.header.engine ∈ {ifds, ide}
  4. confirm every Clause is one of the four primitive heads
  5. confirm composition shape is one of the sanctioned compositions in §4
  6. derive determinism_partition = "deterministic-core"
  7. accept; otherwise reject with the precise E-DSL-* diagnostic
```

Steps 4 and 5 are the **closure check** (`PLAN.md` item-2 restatement). Step 2 is the per-primitive obligation lookup; the registry's startup check refuses to boot on a missing obligation (`T-CMP-DET-01-02`).

Diagnostics are **structured**: every `E-DSL-*` carries `{code, message, location (line/col), suggested-fix}`. `TST-AC-DET-02a` exercises one diagnostic per `E-DSL-*` code; `TST-AC-DET-01b` asserts that the registry produces a non-empty diagnostic on any out-of-DSL spec.

---

## 8. Examples

### 8.1 Well-formed spec — SQL injection (Java)

```yaml
id: "java-jdbc-sqli"
class: "injection"
languages: ["java"]
engine: "ifds"

# Sources: HTTP request parameters reaching the application
source(?T<:javax.servlet.http.HttpServletRequest.getParameter(*))
source(?T<:javax.servlet.http.HttpServletRequest.getHeader(*))

# Propagators: string concatenation and StringBuilder.append
propagate(arg[0] → ret)            # String.concat / + operator on tainted lhs
propagate(arg[0] → field[buf])     # StringBuilder.append(arg[0])
propagate(field[buf] → ret)        # StringBuilder.toString()

# Sanitizers: PreparedStatement parameter binding
sanitize(?T<:java.sql.PreparedStatement.setString(*))
sanitize(?T<:org.owasp.esapi.Encoder.encodeForSQL(*))

# Sinks: raw query execution APIs
sink(?T<:java.sql.Statement.executeQuery(arg[0]))
sink(?T<:java.sql.Statement.executeUpdate(arg[0]))
```

A finding emitted by this spec (`engine=ifds` ⇒ `origin=deterministic-core`) carries the full provenance surface required by `RULE-6`:

```json
{
  "rule_id":           "java-jdbc-sqli",
  "origin":            "deterministic-core",
  "S_version":         "2026.05.0",
  "env_digest":        "sha256:7a3f...d901",
  "cpg_order_hash":    "sha256:bc12...ef34",
  "cpg_order_hash_annotation": "canonical iff fingerprint_class = strong",
  "fingerprint_class": "strong",
  "slice_fingerprint": "sha256:01ab...9876",
  "witness_blob_uri":  "s3://.../witness/01ab9876.json"
}
```

### 8.2 Well-formed spec — Path traversal (Python)

```yaml
id: "python-os-path-traversal"
class: "path-traversal"
languages: ["python"]
engine: "ifds"

# Sources: HTTP request parameters and CLI argv
source(flask.request.args.get(*))
source(flask.request.form.get(*))
source(sys.argv)

# Propagators: path-join and string concatenation
propagate(arg[0] → ret)            # os.path.join(arg[0], ...)
propagate(arg[1] → ret)
propagate(arg[0] → ret)            # f-string / "%s" % arg

# Sanitizers: secure path normalization
sanitize(werkzeug.utils.secure_filename(arg[0]))
sanitize(pathlib.Path.resolve)     # resolve() with strict=True validates traversal

# Sinks: file-system entry points
sink(builtins.open(arg[0]))
sink(os.path.read(arg[0]))
```

Conforms to the migrated `tarslip.yaml` semantics (`T-CMP-DET-03-02`, `AC-DET-03b`); produces the historical CVE-2025-61765 finding under `TST-AC-DET-03b` and `TST-AC-ORCH-01c`.

### 8.3 Well-formed spec — Deserialization (Java)

```yaml
id: "java-jackson-untrusted-deser"
class: "deserialization"
languages: ["java"]
engine: "ifds"

source(?T<:javax.servlet.http.HttpServletRequest.getInputStream)
source(?T<:javax.servlet.http.HttpServletRequest.getReader)

propagate(arg[0] → ret)            # IOUtils.toString(InputStream)
propagate(arg[0] → ret)            # String → byte[] conversions

sink(?T<:com.fasterxml.jackson.databind.ObjectMapper.readValue(arg[0]))
sink(?T<:java.io.ObjectInputStream.readObject)
```

### 8.4 Malformed spec — unknown primitive

```yaml
id: "broken-1"
class: "injection"
languages: ["java"]
engine: "ifds"

taint_flow(?T<:Http.getParameter → ?T<:Statement.execute)
```

**Diagnostic** (`E-DSL-008`):

```
detectors/injection/specs/broken-1.dsl.yaml:5:1: error [E-DSL-008]
  unknown primitive 'taint_flow'; expected one of {source, sink, sanitize, propagate}
  taint_flow(?T<:Http.getParameter → ?T<:Statement.execute)
  ^~~~~~~~~~
hint: declare source(...) and sink(...) separately;
      the solver computes the flow between them.
spec rejected; not registered
```

### 8.5 Malformed spec — embedded oracle pattern

```yaml
id: "broken-2"
class: "xss"
languages: ["javascript"]
engine: "ifds"

source(document.location)
propagate(semgrep: { pattern: "$X = $TAINTED" })
sink(innerHTML)
```

**Diagnostic** (`E-DSL-002`):

```
detectors/xss/specs/broken-2.dsl.yaml:6:11: error [E-DSL-002]
  embedded oracle pattern in DSL spec — use engine=semgrep instead
  propagate(semgrep: { pattern: "$X = $TAINTED" })
            ^~~~~~~
hint: move this clause to detectors/xss/specs/oracle/ with engine: semgrep,
      or replace the embedded pattern with a DSL propagate(...) clause whose
      transfer is distributive.
spec rejected; not registered
```

### 8.6 Malformed spec — sequencing operator

```yaml
id: "broken-3"
class: "ssrf"
languages: ["java"]
engine: "ifds"

source(?T<:HttpRequest.getHeader("Host"))
  then propagate(arg[0] → ret)
  then sink(?T<:URL.openConnection)
```

**Diagnostic** (`E-DSL-005`):

```
detectors/ssrf/specs/broken-3.dsl.yaml:6:3: error [E-DSL-005]
  sequencing operator 'then' not in sanctioned compositions (§4.3)
    then propagate(arg[0] → ret)
    ^~~~
hint: list clauses without a sequencing keyword; the IFDS solver composes
      transfers along the program supergraph. See DOC-DSL §4.1 (Clause conjunction).
spec rejected; not registered
```

---

## 9. References

- `PLAN.md §"Non-distributive-spec rejector"` — DSL closure-check restatement (item 2).
- `PLAN.md §"Algorithm 2 — Detection core as IFDS/IDE"` — distributivity hypothesis of Tabulation.
- `SDD.md CMP-DET-01` — combinator DSL component spec.
- `SDD.md CMP-DET-02` — detector registry + closure check.
- `SDD.md CMP-DET-03` — class plugin scaffolding (`tarslip.yaml` migration target).
- `SDD.md §2 INV-4` — one-sided undecidable approximations; the DSL owner of Algorithm 2's precondition.
- `WBS.md §6` — tasks `T-CMP-DET-01-01..03`, `T-CMP-DET-02-01..04`.
- `WBS.md §17 CLAR-PARAM-01` (RESOLVED) — algorithm-1/3/5 parameters; **does not cover the DSL exhaustive-enumeration bound**, which is pinned by `CMP-DET-01` at implementation.
- `.claude/rules/01-invariants.md §INV-4` — falsifier and counter-example contract.
- `tests/unit/test_dsl_proofs.py` — Gate-1 stub harness for `AC-DET-01a`.
- `DOC-PARTITION` (forthcoming sibling) — `engine → determinism_partition` mapping.
- `DOC-INV` (forthcoming sibling) — INV-4 owner cross-reference; until that file lands, use `.claude/rules/01-invariants.md`.
- `DOC-ALGS §"Algorithm 2"` — Tabulation hypothesis discharged by this DSL.

**Acceptance criteria cross-reference for this document:**

| AC | Test spec | Section in this doc |
|---|---|---|
| `AC-DET-01a` | `TST-AC-DET-01a` (Gate 1) | §3 (per-primitive proofs); §5 (template) |
| `AC-DET-01b` | `TST-AC-DET-01b` | §6 (escape hatches) |
| `AC-DET-02a` | `TST-AC-DET-02a` | §6 (diagnostics table); §7 (registration check) |
| `AC-DET-02b` | `TST-AC-DET-02b` | §7 (manifest fields) |
| `AC-DET-02c` | `TST-AC-DET-02c` | §2 (`EngineTag`); §7 (step 6) |
| `AC-DET-03b` | `TST-AC-DET-03b` | §8.2 (migrated path-traversal example) |

**Invariants discharged:** `INV-4` (DSL closure-check owner of Algorithm 2's precondition). Cross-reference: `TST-INV-4-DET-01`.

---

*Document end. Status: ACTIVE. Next review: at first acceptance of `CMP-DET-01` `DONE`.*
