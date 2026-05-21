# Invariants catalog — Scanipy v3.2

Six architectural invariants constrain every component. A work package that would violate one is malformed by definition (`SDD.md §2`).

---

## INV-1 — Determinism partition

**Statement:** Every finding carries `origin ∈ {deterministic-core, oracle-passthrough}`. Only `deterministic-core` findings are covered by reproducibility theorem (a). No component may emit a finding without a correct `origin`.

**Owner components:** CMP-ORCH-03, CMP-FND-01, CMP-FND-02, CMP-FND-03, CMP-SNAP-04, CMP-TRI-01

**How to discharge:**
- Set `origin = "deterministic-core"` for detectors with `engine ∈ {ifds, ide}`.
- Set `origin = "oracle-passthrough"` for detectors with `engine ∈ {semgrep, cpg-query, external}`.
- For `mixed` detectors: set per-finding origin, never a single origin for the whole result set.
- After a differential-oracle re-partition event (CMP-SNAP-04): flip affected findings from `deterministic-core` to `oracle-passthrough` and log to provenance.

**Counter-example (violation):** A worker that emits a finding without an `origin` field, or blurs the two values by writing `origin = "mixed"` at the finding level.

**Test:** `TST-INV-1-ORCH-03`, `TST-INV-1-FND-01`, `TST-INV-1-FND-02`, `TST-INV-1-FND-03`, `TST-INV-1-SNAP-04`, `TST-INV-1-TRI-01`

---

## INV-2 — Versioned parameters

**Statement:** Every finding and every provenance record carries `S_version` and `env_digest`. No analysis may run against an unpinned `S` or `Env`.

**Owner components:** CMP-SNAP-01, CMP-ORCH-03, CMP-FND-01, CMP-FND-02, CMP-FND-03, CMP-TRI-02

**How to discharge:**
- Stamp `env_digest` on the snapshot at creation time from the container image digest.
- Carry `S_version` through from scan submission to every emitted finding.
- Schema-level: `origin`, `S_version`, `env_digest` are NOT NULL on the `findings` table.

**Counter-example (violation):** A snapshot job that reads tool binaries from the host PATH rather than the pinned container (produces an unverifiable `env_digest`).

**Test:** `TST-INV-2-SNAP-01`, `TST-INV-2-ORCH-03`, `TST-INV-2-FND-02`, `TST-INV-2-TRI-02`

---

## INV-3 — LLM off the detection path

**Statement:** No LLM output may influence a `deterministic-core` finding except through an already-accepted, version-pinned spec in `S`. Triage ranking never deletes or suppresses findings.

**Owner components:** CMP-TRI-01, CMP-TRI-02, CMP-TRI-03, CMP-CP-05

**How to discharge:**
- CMP-TRI-01: write only `triage_score` and `triage_reason` columns; never touch `origin`, detection fields, or `status` in a way that removes a finding from visibility.
- CMP-TRI-02: an accepted spec is written as a new, version-pinned `S_version`; the core only ever reads pinned specs.
- CMP-CP-05 (Attestor): run with `LLM_TRIAGE=off` to verify byte-identical SARIF independent of triage.

**Counter-example (violation):** A triage worker that sets `status = "suppressed"` on a `deterministic-core` finding based on an LLM score.

**Test:** `TST-INV-3-TRI-01`, `TST-INV-3-TRI-02`, `TST-INV-3-CP-05`

---

## INV-4 — One-sided undecidable approximations

**Statement:** Any component that approximates an undecidable property must approximate in the **safe direction**, must name its owning module, and must have a dedicated falsifier.

**Owner components:**
- `CMP-SNAP-03` (`CW-DETECT`): owner of Algorithm 1's closed-world precondition.
  - Required soundness direction: **zero false negatives**. A snippet that contains reachable reflection must produce a `not-closed-world` verdict. False positives are permitted (they cost performance, not correctness).
  - Falsifier: `TST-AC-SNAP-03a` (zero-FN on the curated reflection corpus).
- `CMP-DET-01` (combinator DSL): owner of Algorithm 2's distributivity precondition.
  - Required soundness direction: any spec outside the distributive DSL is **rejected at registration**, never analyzed.
  - Falsifier: `TST-AC-DET-01b` (non-DSL spec rejected with precise diagnostic).

**Counter-example (violation):** A `CW-DETECT` implementation that passes a Spring dynamic-proxy call site as `closed-world`, or a DSL registration check that silently accepts a non-distributive spec.

**Test:** `TST-INV-4-SNAP-03`, `TST-INV-4-DET-01`

---

## INV-5 — Conditional labels are self-describing

**Statement:** Any artifact whose correctness is conditional must carry its own conditional annotation in the persisted record.

**Primary case:** `cpg_order_hash` is canonical **iff** `fingerprint_class = strong`. On the `weak` fallback path the hash is a deterministic same-source order but not a true canonical form across isomorphic programs.

**Owner components:** CMP-CORE-03 (produces the hash + annotation), CMP-CORE-02 (sets `fingerprint_class`), CMP-FND-03 (auditor export)

**How to discharge:**
- Name the field `cpg_order_hash` (never "canonical CPG hash").
- Record the annotation `canonical iff fingerprint_class = strong` in: the provenance record, the SARIF `properties` block, and the auditor-facing export.
- A `weak`-classed finding must never be auto-suppressed across a refactor.

**Counter-example (violation):** An auditor export that writes `"cpg_canonical_hash"` without stating that canonicality only holds on the `strong` path.

**Test:** `TST-INV-5-CORE-03`, `TST-INV-5-FND-03`, `TST-INV-5-CORE-02`

---

## INV-6 — Per-language honesty

**Statement:** Algorithm 2 precision/recall claims are valid only for `(class, language)` pairs that have passed the CPG-fidelity gate (`CMP-CP-06`). Front-end-blocked pairs are reported as `front-end-blocked`, never as recall failures.

**Owner components:** CMP-CP-06 (gate harness), CMP-CORE-01 (benchmark)

**How to discharge:**
- Before adding a language to the Algorithm 2 benchmark, confirm `CMP-CP-06` has passed for it.
- The per-stage recall tables (TST-AC-CORE-01b) include only gate-passing pairs.
- The honest-labeling ledger in `PLAN.md §"Honest-labeling ledger"` must distinguish `[STAGED]` from `[EMPIRICAL]` or `[CONDITIONAL THEOREM]` claims.

**Counter-example (violation):** Reporting a low recall number for Go without first confirming whether the Joern Go front-end passed the fidelity gate.

**Test:** `TST-INV-6-CP-06`, `TST-INV-6-CORE-01`

---

*Cross-reference: CLAUDE.md §3, SDD.md §2, PLAN.md §"Per-language staging overlay"*
