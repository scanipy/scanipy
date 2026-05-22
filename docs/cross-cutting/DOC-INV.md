# DOC-INV — Invariants catalog (INV-1..INV-6)

**Owner:** Architect Agent (design review); Documentation Manager Agent (this document)
**Status:** ACTIVE (Phase 0 cross-cutting reference)
**Source of truth:** `SDD.md §2` (verbatim invariant statements); `PLAN.md` (algorithms and theorems that motivate the invariants); `CLAUDE.md §3` (component-owner table).
**Consumers:** every implementation, QA, code-review, security, and SRE agent — invariant compliance is the merge contract for every PR.

---

## 1. Purpose

This document is the canonical reference for the six architectural invariants `INV-1..INV-6` defined in `SDD.md §2`. It expands each invariant beyond its one-line `SDD` statement into: the components that own its discharge, the concrete mechanisms (schema constraints, falsifier tests, gates), code-shaped examples of compliant and violating implementations, the test artifacts that fire to verify each, and the cross-invariant interactions that arise when a component touches more than one. The rule file `.claude/rules/01-invariants.md` is the operational quick-reference; this document is the full contract. Where the two disagree, `SDD.md §2` wins and this document must be corrected.

---

## 2. Invariant table

| ID | One-line statement | Owner components | Discharge style | Enforcing tests |
|---|---|---|---|---|
| **INV-1** | Every finding carries `origin ∈ {deterministic-core, oracle-passthrough}`. | CMP-ORCH-03, CMP-FND-01, CMP-FND-02, CMP-FND-03, CMP-SNAP-04, CMP-TRI-01 | Schema NOT NULL + branching on `detector.engine` | `TST-INV-1-{ORCH-03, FND-01, FND-02, FND-03, SNAP-04, TRI-01}` |
| **INV-2** | Every finding + provenance record carries `S_version` and `env_digest`. | CMP-SNAP-01, CMP-ORCH-03, CMP-FND-01..03, CMP-TRI-02 | Schema NOT NULL + container-image-digest binding | `TST-INV-2-{SNAP-01, ORCH-03, FND-02, TRI-02}` |
| **INV-3** | No LLM output influences a `deterministic-core` finding except via an accepted pinned spec in `S`. Triage never deletes findings. | CMP-TRI-01, CMP-TRI-02, CMP-TRI-03, CMP-CP-05 | Column-restriction at write + feature flag + `LLM_TRIAGE=off` attestor run + pinned-`S_version` discipline | `TST-INV-3-{TRI-01, TRI-02, CP-05}` |
| **INV-4** | Undecidable-property approximations must be one-sided (safe direction), named, and falsifier-backed. | CMP-SNAP-03 (`CW-DETECT`), CMP-DET-01 (DSL closure) | Falsifier test (zero-FN release gate) + machine-checked distributivity proof obligation per combinator | `TST-INV-4-{SNAP-03, DET-01}` |
| **INV-5** | Conditional artifacts carry their own conditional annotation in the persisted record. | CMP-CORE-03 (annotation), CMP-CORE-02 (`fingerprint_class`), CMP-FND-03 (auditor export) | Annotation string co-located with field; schema-level constraint that `cpg_order_hash` is paired with its conditional | `TST-INV-5-{CORE-03, FND-03, CORE-02}` |
| **INV-6** | Algorithm 2 recall claims are valid only for CPG-fidelity-gate-passing `(class, language)` pairs. | CMP-CP-06 (gate harness), CMP-CORE-01 (benchmark) | Gate harness output drives benchmark eligibility; `front-end-blocked` is a first-class status | `TST-INV-6-{CP-06, CORE-01}` |

Test references are mirrored verbatim from `WBS.md §11` lines 433–438.

---

## 3. INV-1 — Determinism partition

### 3.1 Verbatim statement

> **INV-1 (Determinism partition).** Every finding carries an `origin ∈ {deterministic-core, oracle-passthrough}`. Only `deterministic-core` findings are covered by the reproducibility theorem. No component may emit a finding without a correct `origin`.
> — `SDD.md §2`

### 3.2 Owner components

`CMP-ORCH-03` (sets `origin` at emission time), `CMP-FND-01` (passes through), `CMP-FND-02` (schema NOT NULL), `CMP-FND-03` (records in signed provenance), `CMP-SNAP-04` (re-partitions after differential-oracle disagreement), `CMP-TRI-01` (must not flip `origin` via LLM triage).

### 3.3 How it is discharged

1. **Set at emission time** in `CMP-ORCH-03` from the detector's `engine` field (`engine ∈ {ifds, ide}` ⇒ `deterministic-core`; `engine ∈ {semgrep, cpg-query, external}` ⇒ `oracle-passthrough`; per-finding for `mixed` detectors).
2. **Schema-level NOT NULL** on `findings.origin` in `CMP-FND-02` — a row that omits `origin` is rejected at the database boundary, not at application code.
3. **Provenance binding** in `CMP-FND-03`: the signed audit chain includes `per-finding origin` as the terminating field of the chain.
4. **Differential-oracle re-partition** in `CMP-SNAP-04`: when the slow whole-program reflection scanner disagrees with `CW-DETECT`, every affected `deterministic-core` finding is flipped to `oracle-passthrough` and the flip is appended to the provenance record.
5. **Triage isolation** in `CMP-TRI-01`: the triage worker is allowed to write only `triage_score` and `triage_reason`; touching `origin` is an out-of-contract write (also discharges INV-3).

### 3.4 Example — compliant emission (CMP-ORCH-03)

```python
# services/scan/worker.py
def emit(detector: Detector, result: DetectorResult) -> Finding:
    if detector.engine in ("ifds", "ide"):
        origin = "deterministic-core"
    elif detector.engine in ("semgrep", "cpg-query", "external"):
        origin = "oracle-passthrough"
    else:
        raise InvariantViolation(f"unknown engine {detector.engine!r}")  # INV-1 fail-closed

    return Finding(
        origin=origin,                               # INV-1
        S_version=scan_request.S_version,            # INV-2
        env_digest=snapshot.env_digest,              # INV-2
        cpg_order_hash=snapshot.cpg_order_hash,      # INV-5
        cpg_order_hash_annotation="canonical iff fingerprint_class = strong",
        slice_fingerprint=result.slice_fingerprint,
        fingerprint_class=result.fingerprint_class,
        determinism_partition=detector.determinism_partition,
        ...
    )
```

For mixed-class detectors (`crypto-misuse`, `authn-authz`), the worker iterates per result and sets `result.origin` from the *result's own* engine field, never from the detector's umbrella class.

### 3.5 Counter-example — violations

```python
# WRONG — emits without origin
finding = Finding(slice_fingerprint=..., S_version=..., env_digest=...)
db.findings.insert(finding)   # INV-1 violation; only caught by schema NOT NULL

# WRONG — blurs the partition at the finding level
finding.origin = "mixed"      # INV-1 violation; "mixed" is a detector-level annotation only

# WRONG — triage flips origin
finding.origin = "oracle-passthrough" if triage_score < 0.3 else finding.origin
# Also INV-3 violation: LLM signal mutating partition state
```

### 3.6 Cross-cutting touchpoints

- **INV-3:** triage may never set `origin`. The same code path that violates INV-3 violates INV-1.
- **INV-4:** a false negative in `CW-DETECT` causes a snapshot to receive `origin=deterministic-core` when it should not. `CMP-SNAP-04` retroactively re-partitions; that retroactive flip is the only allowed mechanism that mutates an existing `origin`.
- **INV-6:** front-end-blocked `(class, language)` pairs ship as `oracle-passthrough` only — INV-1 is the field that carries that decision.

### 3.7 Test references

- `TST-INV-1-ORCH-03` — every emitted finding has a correct, non-null `origin`.
- `TST-INV-1-FND-01` — normalizer preserves `origin` through SARIF serialization.
- `TST-INV-1-FND-02` — schema-level NOT NULL refuses an `origin`-omitting insert.
- `TST-INV-1-FND-03` — signed provenance chain terminates in `per-finding origin`.
- `TST-INV-1-SNAP-04` — differential-oracle disagreement re-partitions affected findings exactly once.
- `TST-INV-1-TRI-01` — triage write surface excludes `origin`.

---

## 4. INV-2 — Versioned parameters

### 4.1 Verbatim statement

> **INV-2 (Versioned parameters).** Every finding and every provenance record carries `S_version` and `env_digest`. No analysis may run against an unpinned `S` or `Env`.
> — `SDD.md §2`

### 4.2 Owner components

`CMP-SNAP-01` (stamps `env_digest` on the snapshot row from the container image digest), `CMP-ORCH-03` (carries `S_version` from scan submission through emission), `CMP-FND-01..03` (persist + sign the pair), `CMP-TRI-02` (an accepted spec is written as a *new* `S_version` — never an in-place update).

### 4.3 How it is discharged

1. **Image-digest binding** in `CMP-SNAP-05`: the worker's container image digest *is* the `env_digest`. Changing any bundled tool (`joern`, `codeql`, `git`) changes the digest (AC-SNAP-05b), so `env_digest` is unforgeable.
2. **Scan-submission binding**: `CMP-ORCH-01` requires `S_version` on scan submission; the value flows unchanged into every finding emitted from that scan.
3. **Schema-level NOT NULL** on `findings.S_version` and `findings.env_digest` (AC-FND-02b).
4. **Pinned spec discipline** in `CMP-TRI-02`: an e-process-accepted spec is written as a new row in `spec_versions` and its semver is the new `S_version`; the deterministic core only ever reads pinned versions, never a mutable "current" pointer.

### 4.4 Example — compliant snapshot creation (CMP-SNAP-01)

```python
# services/snapshot/api.py
def create_snapshot(req: SnapshotRequest) -> Snapshot:
    env_digest = container_image_digest()  # AC-SNAP-01c; sourced from runtime metadata
    if not env_digest or not env_digest.startswith("sha256:"):
        raise InvariantViolation("env_digest must be a sha256: digest")

    snap = Snapshot(
        codebase_id=req.codebase_id,
        commit_sha=req.commit_sha,
        env_digest=env_digest,                # INV-2
        precondition_status=...,              # one of closed-world | degraded | full-reparse
    )
    db.snapshots.insert(snap)
    return snap
```

### 4.5 Counter-example — violations

```python
# WRONG — reading the tool from host PATH bypasses env_digest
result = subprocess.run(["joern-parse", path], ...)  # if joern is not the pinned binary,
                                                     # env_digest no longer characterizes Env

# WRONG — mutable "latest spec" pointer
S_version = db.spec_versions.where(class_id=c, status="active").latest()  # INV-2 violation:
# the analysis is run against an unpinned, drifting reference. Pin per scan instead.
```

### 4.6 Cross-cutting touchpoints

- **INV-3:** the e-process accepts a spec only by *minting a new `S_version`*; the core then reads the pinned version. The two invariants share the pinned-spec discipline.
- **INV-5:** the signed provenance chain pairs `S_version` and `env_digest` with `cpg_order_hash + annotation` to produce a self-describing record.

### 4.7 Test references

- `TST-INV-2-SNAP-01` — snapshot row writes a non-empty `env_digest` that equals the container image digest.
- `TST-INV-2-ORCH-03` — every emitted finding carries non-null `S_version` and `env_digest`.
- `TST-INV-2-FND-02` — schema-level NOT NULL refuses inserts that omit either field.
- `TST-INV-2-TRI-02` — an accepted spec is materialized as a new `spec_versions` row with a fresh semver.

---

## 5. INV-3 — LLM off the detection path

### 5.1 Verbatim statement

> **INV-3 (LLM off the detection path).** No LLM output may influence a `deterministic-core` finding except through an already-accepted, version-pinned spec in `S`. Triage ranking never deletes or suppresses findings.
> — `SDD.md §2`

### 5.2 Owner components

`CMP-TRI-01` (LLM triage worker), `CMP-TRI-02` (e-process spec gate), `CMP-TRI-03` (per-customer revalidation + drift monitor), `CMP-CP-05` (Attestor — runs with `LLM_TRIAGE=off` to verify byte-identical SARIF independent of triage).

### 5.3 How it is discharged

INV-3 has **four discharge mechanisms** that compose. Any one alone is insufficient:

1. **Column-restriction at write surface (`CMP-TRI-01`).** The triage worker may only write `triage_score` and `triage_reason`. It must not write `origin`, `S_version`, `env_digest`, `slice_fingerprint`, `fingerprint_class`, `cpg_order_hash`, or `status`. Enforced via code review and an integration test (`TST-INV-3-TRI-01`) that asserts no other columns are mutated by a triage cycle.
2. **Default-off feature flag (`CMP-TRI-01` AC-TRI-01a).** Triage is feature-flagged with `LLM_TRIAGE=off` as the production default. A finding row's detection content is therefore independent of triage in the canonical configuration.
3. **Attestor enforcement (`CMP-CP-05` AC-CP-05a).** The core pipeline of the Determinism Attestor runs explicitly with `LLM_TRIAGE=off` and asserts byte-identical SARIF over the `deterministic-core` partition. If LLM output ever leaked into the core path, the attestor would diff non-zero and hard-fail CI.
4. **Pinned-`S_version` discipline (`CMP-TRI-02` AC-TRI-02c).** When the e-process accepts a candidate spec, the spec is written as a new, version-pinned `S_version`. The deterministic core reads only pinned `S_versions`. The LLM's role is thereby reduced to *proposing* candidate specs; *acceptance* is gated by a statistical instrument (Algorithm 6) and *consumption* is by a frozen identifier. The LLM never directly influences a deterministic-core finding's detection content.

The triage worker also has a non-deletion contract: it writes scores but never sets `status='suppressed'` on a `deterministic-core` finding based on its own output. Suppression is allowed only via human adjudication, which is recorded in a separate audit trail.

### 5.4 Example — compliant triage (CMP-TRI-01)

```python
# services/triage/triage.py
ALLOWED_TRIAGE_COLUMNS = {"triage_score", "triage_reason"}

def triage_finding(finding_id: UUID, llm_output: TriageScore) -> None:
    update = {
        "triage_score": llm_output.score,
        "triage_reason": llm_output.reason,
    }
    assert set(update.keys()) <= ALLOWED_TRIAGE_COLUMNS  # INV-3 fail-closed
    db.findings.update(finding_id, **update)
    # NOT touched: origin, S_version, env_digest, slice_fingerprint, fingerprint_class,
    #              cpg_order_hash, status, witness_blob_uri, determinism_partition
```

### 5.5 Example — compliant spec acceptance (CMP-TRI-02)

```python
# services/triage/spec_inference.py
def maybe_accept(sigma: CandidateSpec, e_value: float) -> Optional[SpecVersion]:
    if e_value < 1.0 / alpha:
        return None                                  # not yet accepted; nothing pinned
    new_version = SpecVersion(
        spec_id=sigma.id,
        semver=next_semver(sigma.id),
        content=sigma.serialize(),
        accepted_at=now_utc(),
        e_value=e_value,
        spec_provenance="global-unrevalidated",      # CMP-TRI-03; revalidate per customer
    )
    db.spec_versions.insert(new_version)             # pin via insert, never update
    return new_version
```

### 5.6 Counter-examples — violations

```python
# WRONG — LLM signal suppresses a finding
if llm_output.likely_fp > 0.9:
    finding.status = "suppressed"                    # INV-3 violation: triage deleting findings

# WRONG — LLM signal flips origin
finding.origin = "oracle-passthrough"                # INV-3 + INV-1 violation

# WRONG — un-pinned spec read by the core
core_spec_set = db.spec_versions.where(status="active")  # INV-3 violation:
# the core must read a frozen S_version per scan, not a mutable "active" view.
```

### 5.7 Cross-cutting touchpoints

- **INV-1:** both invariants forbid triage from mutating `origin`. The triage-isolation discipline discharges both simultaneously.
- **INV-2:** the pinned-`S_version` mechanism is the operational basis of both INV-2 and INV-3.

### 5.8 Test references

- `TST-INV-3-TRI-01` — with triage enabled, only `triage_*` columns change between pre- and post-triage finding rows.
- `TST-INV-3-TRI-02` — an accepted spec materializes as a new `S_version`; no existing row is mutated.
- `TST-INV-3-CP-05` — the Attestor's core pipeline runs with `LLM_TRIAGE=off` and asserts byte-identical SARIF.

---

## 6. INV-4 — One-sided undecidable approximations

### 6.1 Verbatim statement

> **INV-4 (Conservative undecidable approximations are one-sided and owned).** Any component that approximates an undecidable property (reachable reflection, flow-function distributivity) must approximate in the safe direction, must name its owning module, and must have a dedicated falsifier.
> — `SDD.md §2`

### 6.2 Two owners, two mechanisms

INV-4 has exactly two owning components in v3.2, each with a distinct discharge mechanism. Both must hold; they do not substitute for each other.

#### 6.2.a CMP-SNAP-03 — `CW-DETECT` (closed-world precondition)

`CW-DETECT` is a one-sided conservative detector for *reachable reflection / dynamic dispatch over an open hierarchy*. The undecidable property is whether the snapshot contains a dynamic construct that can reach analyzed code. The safe direction is **zero false negatives**: any snippet that contains reachable reflection must yield a `not-closed-world` verdict and be routed to the degraded path. False positives (declaring not-closed-world when the code is in fact closed-world) are permitted; they cost performance, not correctness.

Discharge mechanisms:

1. **Curated reflection corpus (`CMP-CORP-REFL-01`).** Hand-labelled examples of Spring dynamic proxies, Python `__import__`/`getattr` dispatch, Ruby `send`/`method_missing`, PHP variable functions, Java `Class.forName`, plus mutation-injected reflection. Per `CLAR-CORP-01`: N ≥ 50 per category, ≥ 20 mutation-injected per language.
2. **Zero-FN release gate (`AC-SNAP-03a`, `TST-AC-SNAP-03a`).** A single false negative on the corpus is a release blocker.
3. **Differential reflection oracle (`CMP-SNAP-04`).** An async whole-program reflection scanner runs off the critical path; on disagreement with `CW-DETECT`, affected findings are re-partitioned from `deterministic-core` to `oracle-passthrough`. This bounds the residual undecidable-case risk to a labeling-correction window with a contractual SLA (AC-SNAP-04b).

Example — compliant fail-closed routing in `CW-DETECT`:

```python
# analysis/cw_detect.py
def detect(snapshot: Snapshot) -> PreconditionStatus:
    if has_known_reflection_construct(snapshot):
        return "not-closed-world"           # safe direction
    if structural_uncertainty(snapshot):    # any uncertainty defaults to not-closed-world
        return "not-closed-world"           # one-sided; FP allowed
    return "closed-world"
```

Counter-example — INV-4 violation:

```python
# WRONG — fail-open on uncertainty
def detect(snapshot: Snapshot) -> PreconditionStatus:
    if confidently_no_reflection(snapshot):
        return "closed-world"
    return "closed-world"   # WRONG safe direction; should be "not-closed-world"
```

A Spring dynamic-proxy call site that `CW-DETECT` returns as `closed-world` is a zero-FN release-gate failure (a single such case blocks the release).

#### 6.2.b CMP-DET-01 — combinator DSL closure check (Algorithm 2 precondition)

The undecidable property is whether an arbitrary flow function is distributive. v3.1 phrased this as "validates each spec for distributivity at registration" — that overclaimed a decision of an undecidable property. v3.2 (`PLAN.md §"item-2 restatement"`) corrects this:

> Detector specs are not arbitrary code. They are declarative data in a fixed **combinator DSL** whose primitives — `source`, `sink`, `sanitize`, `propagate`, and their sanctioned compositions — are each *distributive by construction*. The registration check is a **grammar/closure check** that verifies a submitted spec lies within the distributive-by-construction DSL. It is not a decision procedure.

Discharge mechanisms:

1. **Per-combinator machine-checked distributivity proof obligation (`AC-DET-01a`).** Each combinator carries a property-test obligation that `f(X ∪ Y) = f(X) ∪ f(Y)` exhaustively over the finite fact domain. Adding a combinator without a discharged obligation fails CI.
2. **No-escape-hatch grammar (`AC-DET-01b`).** A spec embedding arbitrary code is rejected, not analyzed. Membership in the DSL is decidable; the analysis is run only on DSL members; the analysis's order-independence theorem (RHS'95) applies.
3. **Closure check at registration (`CMP-DET-02` AC-DET-02a).** Registration rejects any submitted spec outside the DSL with a precise diagnostic. The closure check is a syntactic membership test, not a semantic decision procedure.

Example — compliant DSL grammar in `CMP-DET-01`:

```python
# analysis/ifds/dsl/spec.py
@dataclass(frozen=True)
class Source:
    access_path: AccessPathPattern
    # transfer function: maps a fact set X to a fact set, defined per access path
    # distributivity obligation: discharged by tests/unit/test_source_distributivity.py
```

Counter-example — INV-4 violation:

```python
# WRONG — embedding arbitrary Python in a spec
spec = {"source": "lambda req: req.user_input if some_condition() else None"}
detector_registry.register(spec)
# Algorithm 2's order-independence theorem does not apply; the spec must be rejected.
```

### 6.3 Cross-cutting touchpoints

- **INV-1:** when `CW-DETECT` has a false negative, `CMP-SNAP-04` triggers an INV-1 re-partition. INV-4 and INV-1 thus share the differential-oracle mechanism.
- **INV-5:** the `(B, T)`-bounded canonicalizer in Algorithms 3/5 falls back to a `fingerprint_class = weak` outcome on budget exhaustion. That fallback is itself a one-sided approximation (deterministic same-source order but not a true canonical form); INV-5 records the conditional annotation that INV-4-style honesty requires.
- **INV-6:** language front-ends with weak parse fidelity would silently depress Algorithm 2's measured recall; INV-6 protects the `(class, language)` benchmark eligibility decision in the same spirit (don't claim what you can't prove) but is a separate invariant because the underlying undecidability is different (front-end fidelity, not reflection or distributivity).

### 6.4 Test references

- `TST-INV-4-SNAP-03` — Falsifier CW: zero false negatives on `CMP-CORP-REFL-01`.
- `TST-INV-4-DET-01` — every combinator carries a discharged distributivity proof obligation; non-DSL specs are rejected at registration with a precise diagnostic.

---

## 7. INV-5 — Conditional labels are self-describing

### 7.1 Verbatim statement

> **INV-5 (Conditional labels are self-describing).** Any artifact whose correctness is conditional (e.g. canonicality of the CPG order hash) must carry its own conditional annotation in the persisted record.
> — `SDD.md §2`

### 7.2 Owner components

`CMP-CORE-03` (produces `cpg_order_hash` and emits the annotation), `CMP-CORE-02` (sets `fingerprint_class ∈ {strong, weak}` — the field whose value gates canonicality), `CMP-FND-03` (auditor-facing export carries the annotation verbatim).

### 7.3 Primary case: `cpg_order_hash`

The 2-WL refinement plus bounded individualization-refinement in Algorithm 5 produces a deterministic same-source CPG order. On the `strong` path the result is canonical across isomorphic programs; on the `weak` fallback path (budget exhaustion or witness-edge-sequence hash) the result is still deterministic for the same source but is *not* a true canonical form across isomorphic-but-differently-written programs.

The field is therefore named `cpg_order_hash` (never "canonical CPG hash") and is recorded with the annotation:

> `canonical iff fingerprint_class = strong`

That annotation must appear in the same record everywhere `cpg_order_hash` is persisted: the `findings` row (`CMP-FND-02`), the signed provenance record (`CMP-FND-03`), the SARIF `properties` block (`CMP-FND-01`), and the auditor-facing export (`CMP-CP-04` dashboard, `CMP-FND-03` export).

### 7.4 Example — compliant record (CMP-FND-03 auditor export)

```json
{
  "cpg_order_hash": "sha256:9f...c1",
  "cpg_order_hash_annotation": "canonical iff fingerprint_class = strong",
  "fingerprint_class": "strong",
  "slice_fingerprint": "sha256:4a...88"
}
```

For a `weak`-classed finding:

```json
{
  "cpg_order_hash": "sha256:9f...c1",
  "cpg_order_hash_annotation": "canonical iff fingerprint_class = strong",
  "fingerprint_class": "weak",
  "slice_fingerprint": "sha256:4a...88"
}
```

The annotation string is identical in both rows. The conditional is satisfied by inspecting `fingerprint_class`.

### 7.5 Counter-examples — violations

```json
{ "cpg_canonical_hash": "sha256:..." }     // INV-5 violation: name claims unconditional canonicality
{ "cpg_order_hash": "sha256:..." }         // INV-5 violation: annotation missing
```

Auto-suppressing a `weak`-classed finding across a refactor is also an INV-5 violation: the `weak` class explicitly disclaims refactor-stability, so the baseline-lookup logic must not treat a `weak` slice fingerprint as a re-occurrence (`AC-CORE-02c`, `AC-FND-02a`).

### 7.6 Cross-cutting touchpoints

- **INV-2:** the signed audit chain pairs `cpg_order_hash + annotation` with `S_version` and `env_digest` to make the provenance record self-describing as a whole, not just per-field.
- **INV-4:** the `weak` fallback is itself the result of a bounded conservative approximation (the `(B, T)` budget). INV-4 requires the safe direction and the falsifier; INV-5 requires the resulting artifact to admit its own conditional status.
- **INV-1:** every finding carries both `origin` and `cpg_order_hash + annotation`; the two together form the minimal self-describing finding record.

### 7.7 Test references

- `TST-INV-5-CORE-03` — `cpg_order_hash` field name and the annotation string appear together everywhere the hash is persisted.
- `TST-INV-5-FND-03` — auditor export includes the conditional annotation.
- `TST-INV-5-CORE-02` — a `weak`-classed finding is never auto-suppressed across a refactor.

---

## 8. INV-6 — Per-language honesty

### 8.1 Verbatim statement

> **INV-6 (Per-language honesty).** Algorithm 2 precision/recall claims are valid only for `(class, language)` pairs that have passed the CPG-fidelity gate. Front-end-blocked pairs are reported as blocked, never as recall failures.
> — `SDD.md §2`

### 8.2 Owner components

`CMP-CP-06` (CPG-fidelity gate harness), `CMP-CORE-01` (Algorithm 2 benchmark; consumes the gate output).

### 8.3 How it is discharged

1. **Gate harness (`CMP-CP-06`).** For each language `L`, the curated fidelity corpus `CMP-CORP-CPG-{L}` is run against the Joern (or proprietary) front-end. Thresholds (per `CLAR-CORP-02`):
   - Parse success ≥ 99.5% of files
   - Call-edge precision ≥ 90%
   - Call-edge recall ≥ 85%
   - PDG dependence-edge recall ≥ 80%
2. **Status propagation.** A language that fails any threshold is recorded as `front-end-blocked` (a first-class status, distinct from a recall failure).
3. **Benchmark eligibility (`CMP-CORE-01` AC-CORE-01b).** Algorithm 2's recall claim is computed *only* over `(class, language)` pairs whose language has passed the gate. Front-end-blocked pairs appear in the per-stage tables as `front-end-blocked`, never as a measured low-recall number.
4. **Honest-labeling ledger discipline (`PLAN.md §"Honest-labeling ledger"`).** The ledger distinguishes `[STAGED]` from `[EMPIRICAL]` and `[CONDITIONAL THEOREM]` claims.

### 8.4 Example — compliant per-stage reporting

```
Stage A — Java + Python
  injection         (Java)   recall=0.91 / Semgrep-default=0.79  [EMPIRICAL, gate-passed]
  injection         (Python) recall=0.88 / Semgrep-default=0.74  [EMPIRICAL, gate-passed]

Stage C — Go (deferred)
  injection         (Go)     front-end-blocked: call-edge recall 0.62 < 0.85 threshold
```

### 8.5 Counter-example — violation

```
Stage C — Go
  injection (Go)   recall=0.31   # INV-6 violation: reported as a recall failure rather than
                                 # front-end-blocked. The low number reflects Joern's Go
                                 # front-end fidelity, not Algorithm 2's recall.
```

### 8.6 Cross-cutting touchpoints

- **INV-1:** front-end-blocked `(class, language)` pairs ship as `oracle-passthrough` only (per `CLAUDE.md §7` staging table). INV-1 carries that decision per finding.
- **INV-4:** both invariants share a "don't claim what your tool can't prove" stance, but the underlying issue differs (INV-4: undecidability of reflection/distributivity; INV-6: empirical front-end fidelity).

### 8.7 Test references

- `TST-INV-6-CP-06` — the gate harness produces a pass/fail verdict per language and refuses to report a fail as a recall number.
- `TST-INV-6-CORE-01` — Algorithm 2's recall report contains only gate-passing `(class, language)` pairs.

---

## 9. Cross-invariant interaction matrix

The cells below name the interaction; the diagonal restates each invariant in one line. Empty cells mean no direct interaction in v3.2.

|        | INV-1 | INV-2 | INV-3 | INV-4 | INV-5 | INV-6 |
|---|---|---|---|---|---|---|
| **INV-1** | Partition tag on every finding | — | Triage may not flip `origin` | `CW-DETECT` FN → wrong `origin` → CMP-SNAP-04 re-partitions | `origin` and `cpg_order_hash` co-resident on every finding | Front-end-blocked ⇒ `origin=oracle-passthrough` |
| **INV-2** | — | `S_version` + `env_digest` on every record | Triage may not touch `S_version` / `env_digest`; accepted spec → new `S_version` | — | Provenance pairs `S_version`/`env_digest` with annotated `cpg_order_hash` | — |
| **INV-3** | (see INV-1×INV-3) | (see INV-2×INV-3) | LLM off the detection path | — | — | — |
| **INV-4** | (see INV-1×INV-4) | — | — | One-sided approximations | `weak` fallback is a bounded conservative outcome whose status is recorded by INV-5 | Different undecidability (front-end fidelity) — separate gate |
| **INV-5** | (see INV-1×INV-5) | (see INV-2×INV-5) | — | (see INV-4×INV-5) | Conditional labels self-describing | — |
| **INV-6** | (see INV-1×INV-6) | — | — | (see INV-4×INV-6) | — | Per-language honesty |

Matrix entries are symmetric (read "INV-1 × INV-3" the same as "INV-3 × INV-1"); each interaction is described once in the upper triangle.

---

## 10. Lifecycle policy

### 10.1 No relaxation within v3.2

The six invariants are load-bearing for properties (a) reproducibility, (b) incremental computability, and (c) machine-checkable provenance. None may be relaxed within v3.2. In particular:

- INV-3 may not be relaxed under any circumstance: `OOS-LLM-DET-01` ("any LLM influence on `deterministic-core` findings outside a pinned `S`") is the permanent out-of-scope register entry that backs this.
- The determinism partition (INV-1) is scoped to reproducibility under a *fixed* environment: `OOS-ENV-INDEP-01` ("environment-independent determinism") is explicitly out of scope. Attempts to claim cross-environment determinism are scope creep, not an invariant change.
- INV-6 may not be weakened to permit reporting recall numbers on front-end-blocked pairs.

### 10.2 Adding a new invariant

A new INV is a `PLAN.md` change, not a documentation change. The path is:
1. File a `CLAR-*` in `WBS.md §17` describing the property to be invariant.
2. CTO Agent records a decision (`/cto`).
3. `PLAN.md` and `SDD.md §2` are updated by the human-author owners of those documents (this agent and the Documentation Manager do not edit those files — `CLAUDE.md §1.2`).
4. This document and `.claude/rules/01-invariants.md` are updated to mirror the new invariant; `WBS.md §11` adds the new `TST-INV-N-*` rows.

### 10.3 Removing an invariant

Same path as adding; a `PLAN.md` revision that drops or weakens an INV requires CTO Agent approval and the explicit acknowledgement that one of properties (a)/(b)/(c) is being relaxed or rephrased.

---

## 11. References

- `SDD.md §2` — verbatim invariant statements (the contract).
- `SDD.md §11` — staging plan (consumed by INV-6).
- `SDD.md §12` — out-of-scope register (backs the no-relaxation policy).
- `PLAN.md §"Central correction"` — scoping of property (a) to fixed `Env`.
- `PLAN.md §"Precondition soundness"` — INV-4's two owners (`CW-DETECT`, combinator DSL).
- `PLAN.md §"Algorithm 5"` — `cpg_order_hash` and INV-5's conditional.
- `PLAN.md §"Engine adapters and the determinism partition"` — INV-1 mechanism.
- `CLAUDE.md §3` — component-owner table (mirrored into §2 of this document).
- `WBS.md §11` (lines 433–438) — `TST-INV-*` per emitter; canonical test reference.
- `.claude/rules/00-global.md` — RULE-1..10 (operational enforcement).
- `.claude/rules/01-invariants.md` — operational quick-reference (this document is the full contract).
- `.claude/rules/02-provenance.md` — provenance-threading rules (operational INV-1/INV-2/INV-5 discipline).
- `.claude/rules/05-determinism.md` — determinism-partition rules (INV-1 operational detail).
- Component docs `docs/components/DOC-CMP-*.md` (Phase 0 output) — per-component invariant discharge.

---

*This document is consumed by every implementation, QA, code-review, security, and SRE agent at session start (`CLAUDE.md §13` reading guide step 4). Update this document when `SDD.md §2` changes; never edit `SDD.md §2` from this document.*
