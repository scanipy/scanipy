# DOC-GLOSSARY — Canonical vocabulary

**Owner:** Documentation Manager Agent
**Status:** ACTIVE (Phase 0 cross-cutting reference)
**Source of truth:** `PLAN.md`, `SDD.md`. Where a term is defined in either, this glossary quotes the pinned value verbatim and points back. Where the source documents are silent on a precise enum or threshold, the gap is *not* filled inline — it is escalated to `WBS.md §17` (see `CLAUDE.md §14`).
**Consumers:** every agent. This file is the second cross-cutting reference loaded after `DOC-INV.md`.

---

## 1. Purpose

This document is the canonical vocabulary for Scanipy v3.2. Every term, field, enum value, status code, and budget constant used across `PLAN.md`, `SDD.md`, `WBS.md`, `CLAUDE.md`, and the per-component documentation `DOC-CMP-*` is defined here once. Where a term is type- or enum-valued, the allowed values are enumerated; where it is a numeric constant, the source-of-truth pin and unit are stated; where its correctness is conditional, the conditional annotation is included verbatim.

---

## 2. Index

Alphabetical. Each entry links to its section heading.

- [`AFFECTED`](#affected)
- [`attestor`](#attestor)
- [`(B, T)` budget](#b-t-budget)
- [`(class, language)` pair](#class-language-pair)
- [`closed-world` / `degraded` / `full-reparse`](#precondition-status-values)
- [`CLAR-*`](#clar)
- [`core-partition` / `oracle-partition`](#core-partition--oracle-partition)
- [`cpg_order_hash`](#cpg_order_hash)
- [`CW-DETECT`](#cw-detect)
- [`determinism_partition`](#determinism_partition)
- [`deterministic-core` / `oracle-passthrough` (`origin` values)](#origin-values)
- [`e-process`](#e-process)
- [`engine`](#engine)
- [`env_digest`](#env_digest)
- [`fingerprint_class`](#fingerprint_class)
- [`Finding`](#finding)
- [`front-end-blocked`](#front-end-blocked)
- [`IFDS` and `IDE`](#ifds-and-ide)
- [`INV-1..6`](#inv-1-inv-6)
- [`OOS-*`](#oos)
- [`precondition-status`](#precondition-status)
- [provenance record / signed audit chain](#provenance-record--signed-audit-chain)
- [`S`, `S_version`](#s-s_version)
- [`slice_fingerprint`](#slice_fingerprint)
- [`spec_provenance`](#spec_provenance)
- [`STAGE-GATED` (status code)](#stage-gated)
- [`BLOCKED` (status code, for contrast)](#blocked)
- [`Stage A..D`](#stage-a-d)
- [`witness_blob_uri`](#witness_blob_uri)

---

## 3. Term definitions

### <a id="affected"></a>`AFFECTED`

The input set to Algorithm 1's incremental re-evaluation: the union of changed declarations, the reverse-symbol closure of changed declarations, the direct callers of changed signatures, and the CHA-cone of changed types.

- **Formal definition:** `AFFECTED = changed-decls ∪ reverse-symbol-closure(changed-decls) ∪ direct-callers(changed-signatures) ∪ CHA-cone(changed-types)`. (`PLAN.md §"Algorithm 1"`)
- **Owner:** `CMP-SNAP-02` (`analysis/cpg_delta.py`).
- **First appearance:** `PLAN.md §"Algorithm 1 — Incremental CPG maintenance"`; `SDD.md CMP-SNAP-02`.
- **Note:** `AFFECTED` is meaningful only when the snapshot's `precondition-status = closed-world` (or routed to the sound `degraded` path). On `full-reparse`, `AFFECTED` collapses to the whole graph and Algorithm 1's economics claim does not apply.

### <a id="attestor"></a>`attestor`

The Partitioned Determinism Attestor — a CI pipeline component that re-runs `F` under fixed `(S_version, env_digest, LLM_TRIAGE=off)` and verifies the determinism partition's claims.

- **Owner:** `CMP-CP-05` (`SDD.md §10`).
- **Two sub-pipelines:**
  - **Core pipeline:** asserts byte-identical SARIF over `origin=deterministic-core` findings. **Hard fail** on any diff. (`AC-CP-05a`)
  - **Oracle pipeline:** records digest-stability and a measured reproduction rate over `origin=oracle-passthrough` findings. Never asserts the theorem. (`AC-CP-05b`)
- **Trigger:** every detector / engine / `Env` change runs both pipelines on the canary corpus. (`AC-CP-05c`)
- **First appearance:** `PLAN.md §"Phase 9 — Determinism Attestor"`; `SDD.md CMP-CP-05`.

### <a id="b-t-budget"></a>`(B, T)` budget

The hard canonicalization budget shared by Algorithms 3 (slice-fingerprint canonicalizer) and 5 (canonical CPG ordering).

- **Pinned values:** `B = 2^16` search-tree nodes, `T = 200 ms`. (`PLAN.md §"Algorithm 3"`)
- **Mechanism:** 2-WL refinement runs to fixpoint, followed by bounded individualization-refinement under `(B, T)`. On exhaustion, the algorithm falls back to a deterministic stable order (Algorithm 5) or an `O(|witness|)`-capped witness-edge-sequence hash (Algorithm 3) with `fingerprint_class = weak`.
- **Owner:** `CMP-CORE-02` (Algorithm 3), `CMP-CORE-03` (Algorithm 5).
- **Targets:** strong-success-within-budget ≥ 98% (`PLAN.md §"Algorithm 3"`); budget-exhaustion rate on real code < 1% (`AC-CORE-03b`).

### <a id="class-language-pair"></a>`(class, language)` pair

The atomic unit of staging and benchmarking. A combination of a vulnerability class (e.g. `injection`, `path-traversal`) and a source language (e.g. `Java`, `Python`).

- **Eligibility:** a `(class, language)` pair enters Algorithm 2 benchmarking only after `CMP-CP-06` is green for the language. (`RULE-7`, `INV-6`.)
- **First appearance:** `SDD.md §11`; `PLAN.md §"Phase staging"`.
- **Status:** `STAGE-GATED` until eligible; thereafter follows the dependency DAG.

### <a id="precondition-status-values"></a>`closed-world` / `degraded` / `full-reparse`

The three values of `precondition-status`. See [`precondition-status`](#precondition-status) for the enum-level entry.

- `closed-world` — `CW-DETECT` verdict: snapshot satisfies the closed-world precondition; Algorithm 1's `O(Δ)` re-evaluation applies.
- `degraded` — `CW-DETECT` verdict: snapshot is not closed-world but the bounded points-to cone is within `θ_cone` (default 0.25) and `|changed files|/|files| ≤ θ_files` (default 0.4); the sound conservative path is used.
- `full-reparse` — bounded cone exceeds `θ_cone` or `θ_files`; full re-parse runs.
- **Source:** `PLAN.md §"Algorithm 1 — Incremental CPG maintenance"`; `SDD.md CMP-SNAP-01 AC-SNAP-01b`.

### <a id="clar"></a>`CLAR-*`

A `CLARIFICATION-NEEDED` register item. Filed when a required decision is missing from `PLAN.md` or `SDD.md` and cannot be resolved inside an implementation work package.

- **Format:** `CLAR-<DOMAIN>-<NN>` where domain ∈ `{DEPLOY, CORP, PARAM, SLA, FE, OWNER, MIGRATION}` and `NN` is a two-digit running number per domain.
- **Location:** appended to `WBS.md §17` only.
- **Lifecycle:** `OPEN` → `RESOLVED` (with decision summary and link to a decision record) or `DEFERRED` (with explicit reasoning).
- **Approver:** CTO Agent (for `CLAR-DEPLOY-*` per `RULE-8`); otherwise the owning agent per domain.
- **Source:** `CLAUDE.md §14`; `.claude/rules/03-scope.md`; `WBS.md §17`.

### <a id="core-partition--oracle-partition"></a>`core-partition` / `oracle-partition`

The two equivalence classes that `origin` partitions every finding into. Synonyms in `PLAN.md` / `SDD.md` for the `origin` enum values; the long forms `core-partition` / `oracle-partition` are used when speaking about the *set* of findings carrying a given `origin`.

- `core-partition` ≡ `{finding : origin = deterministic-core}` — covered by reproducibility theorem (a).
- `oracle-partition` ≡ `{finding : origin = oracle-passthrough}` — covered by digest-stability + measured reproduction rate only.
- **Source:** `PLAN.md §"Engine adapters and the determinism partition"`; `SDD.md §2 INV-1`.

### <a id="cpg_order_hash"></a>`cpg_order_hash`

The hash of the canonical CPG order produced by Algorithm 5. **Persisted with the conditional annotation `canonical iff fingerprint_class = strong`.**

- **Type:** sha256 string (`bytea` in PostgreSQL per `DOC-DEPLOY-DECISIONS` CLAR-DEPLOY-03).
- **Required annotation:** the string `canonical iff fingerprint_class = strong` MUST appear in the same record everywhere `cpg_order_hash` is persisted (`AC-CORE-03c`, INV-5).
- **Producer:** `CMP-CORE-03`.
- **Consumers:** `CMP-FND-02` (schema), `CMP-FND-03` (signed provenance), `CMP-FND-01` (SARIF `properties`), `CMP-CP-04` (dashboard auditor export).
- **Same-source determinism:** holds unconditionally (Algorithm 5 fallback is deterministic).
- **Canonicality across isomorphic-but-differently-written programs:** holds only on the `strong` path.
- **Field-name rule:** never write "canonical CPG hash". The name is `cpg_order_hash`. (`PLAN.md §"Algorithm 5"` item-4 fix.)

### <a id="cw-detect"></a>`CW-DETECT`

The closed-world precondition detector. One-sided conservative detector for reachable reflection / dynamic dispatch over an open hierarchy.

- **Owner:** `CMP-SNAP-03`.
- **Soundness direction (Claim CW):** zero false negatives. Any snippet containing reflection that can reach analyzed code must yield `not-closed-world`. (`PLAN.md §"Closed-world detector"`; INV-4.)
- **Falsifier:** `TST-AC-SNAP-03a` — zero FN on `CMP-CORP-REFL-01` (Spring proxies, Python `__import__`/`getattr`, Ruby `send`/`method_missing`, PHP variable functions, Java `Class.forName`, mutation-injected reflection). A single FN is a release blocker.
- **Residual undecidable-case risk** is bounded by the asynchronous differential reflection oracle (`CMP-SNAP-04`), which re-partitions affected findings on disagreement.
- **First appearance:** `PLAN.md §"Closed-world detector"`; `SDD.md CMP-SNAP-03`.

### <a id="determinism_partition"></a>`determinism_partition`

A detector-level (manifest-derived) field recorded on every finding. Distinguished from `origin` because it is *derived once at detector registration* from `manifest.yaml`, whereas `origin` is *set per finding at emission time* (and may be flipped retroactively by `CMP-SNAP-04`).

- **Allowed values:** `deterministic-core | oracle-passthrough`.
- **Derivation (`AC-DET-02c`):** `engine ∈ {ifds, ide}` ⇒ `determinism_partition = deterministic-core`; `engine ∈ {semgrep, cpg-query, external}` ⇒ `oracle-passthrough`.
- **Owner:** `CMP-DET-02` (manifest derivation); `CMP-ORCH-03` (stamping at emission time).
- **Relationship to `origin`:** they start equal at emission; a `CMP-SNAP-04` re-partition event can flip `origin` while leaving `determinism_partition` unchanged (the detector class is unchanged; only the operational labeling changed).

### <a id="origin-values"></a>`deterministic-core` / `oracle-passthrough` (`origin` values)

The two values of the `findings.origin` enum (INV-1).

- **`deterministic-core`** — finding is covered by reproducibility theorem (a). Required conditions (per `.claude/rules/05-determinism.md`):
  1. Detector's `engine ∈ {ifds, ide}`.
  2. Finding passed the combinator-DSL closure check.
  3. Snapshot satisfied the closed-world precondition or was routed to the sound `degraded` path.
  4. No differential-oracle re-partition event for this finding since the scan ran.
  5. `LLM_TRIAGE=off` at the time of the attestation run.
- **`oracle-passthrough`** — finding is covered by digest-stability + a measured reproduction rate only. Conditions:
  - Detector's `engine ∈ {semgrep, cpg-query, external}`, OR
  - Differential-oracle re-partition event has flipped the finding, OR
  - The snapshot was routed to `full-reparse` mode and `origin` was set to `oracle-passthrough`.
- **Source:** `SDD.md §2 INV-1`; `PLAN.md §"Engine adapters and the determinism partition"`.

### <a id="e-process"></a>`e-process`

A nonnegative process `E_t(σ)` with `E_0 = 1` and `E[E_τ | H0] ≤ 1` at every stopping time `τ` (Ville's inequality). The instrument used by Algorithm 6 for the precision-floor null `H0(σ): true precision of σ < π₀`. **Anytime-valid under unbounded optional continuation**, so the acceptance gate and the drift monitor can share a single mathematical object without an information horizon.

- **Owner:** `CMP-TRI-02` (acceptance gate); `CMP-TRI-03` (drift monitor — same instrument run on the customer's adjudicated stream).
- **Decision rule:** accept `σ` into `S` as a new `S_version` when `E_t(σ) ≥ 1/α`.
- **Multiplicity:** one e-process per spec; combination by averaging (an e-process is closed under averaging). No Bonferroni / no horizon.
- **Literature:** Robbins (1970); Howard et al. (2021); Ramdas, Grünwald, Vovk, Shafer (2023); Waudby-Smith & Ramdas (2024). (`PLAN.md §"Literature grounding"`.)
- **Falsifiers:**
  - `AC-TRI-02a` — adversarial unbounded-continuation campaign: realized ever-false-acceptance rate ≤ α.
  - `AC-TRI-02b` — martingale-property unit test: `E[E_τ | H0] ≤ 1` across simulated stopping times. Release blocker.

### <a id="engine"></a>`engine`

A required field on every detector `manifest.yaml`. Determines `determinism_partition`.

- **Allowed values:** `ifds | ide | semgrep | cpg-query | external`.
- **Mapping (`AC-DET-02c`):**
  - `ifds`, `ide` → `determinism_partition = deterministic-core`
  - `semgrep`, `cpg-query`, `external` → `determinism_partition = oracle-passthrough`
- **Owner:** `CMP-DET-02` (registry) consumes the field; detector authors set it.
- **Source:** `SDD.md CMP-DET-02 AC-DET-02b/c`.

### <a id="env_digest"></a>`env_digest`

The sha256 container image digest of the analysis worker image. Identifies the pinned analysis environment `Env`.

- **Type:** sha256 string (e.g. `sha256:a1b2…`).
- **Producer:** `CMP-SNAP-01` (snapshot creation); sourced from runtime container metadata, not host PATH (INV-2 discharge).
- **Authoritative property (`AC-SNAP-05b`):** changing any bundled tool (`joern`, `codeql`, `git`) changes the digest.
- **Persisted on:** `snapshots`, `findings` (NOT NULL), `provenance` records.
- **Source:** `SDD.md CMP-SNAP-01 AC-SNAP-01c`; `CMP-SNAP-05 AC-SNAP-05b`.

### <a id="fingerprint_class"></a>`fingerprint_class`

The class of the slice fingerprint produced by Algorithm 3.

- **Allowed values:** `strong | weak`.
  - `strong` — produced within the `(B, T)` canonicalization budget. Implies `cpg_order_hash` is canonical across isomorphic programs.
  - `weak` — produced by the witness-edge-sequence hash fallback after budget exhaustion. `cpg_order_hash` is deterministic same-source but not a canonical form.
- **Target rate:** `weak`-rate < 5% (`AC-CORE-02c`); above 5% triggers a canonicalizer redesign (`PLAN.md §"Algorithm 3"`).
- **Owner:** `CMP-CORE-02`.
- **Consumers:** every component that persists or surfaces a finding; `CMP-FND-02` (schema); `CMP-FND-03` (provenance); `CMP-FND-01` (SARIF).
- **Rule:** a `weak`-classed finding is never auto-suppressed across a refactor (`AC-CORE-02c`, `AC-FND-02a`).

### <a id="finding"></a>`Finding`

A single detected vulnerability instance. The atomic output of `F`.

- **Required fields (provenance threading, per `.claude/rules/02-provenance.md`):**
  - `origin` (enum, NOT NULL) — INV-1
  - `S_version` (semver, NOT NULL) — INV-2
  - `env_digest` (sha256, NOT NULL) — INV-2
  - `cpg_order_hash` (sha256, NOT NULL) — INV-5, paired with annotation `canonical iff fingerprint_class = strong`
  - `slice_fingerprint` (sha256, NOT NULL)
  - `fingerprint_class` (enum, NOT NULL) — `strong | weak`
  - `determinism_partition` (enum, NOT NULL)
- **Optional fields:**
  - `witness_blob_uri` — nullable for oracle findings without a slice
  - `triage_score`, `triage_reason` — set by `CMP-TRI-01` only when feature flag on
  - `spec_provenance` — set by `CMP-TRI-03`
- **Status field:** `status ∈ {open, suppressed, fixed}`, schema default `open`. INV-3 forbids triage-driven suppression of `deterministic-core` findings.
- **Schema:** `CMP-FND-02`. Index on `(codebase_id, slice_fingerprint)`.
- **Source:** `SDD.md CMP-FND-02`; `PLAN.md §"Algorithm 5"` (provenance chain).

### <a id="front-end-blocked"></a>`front-end-blocked`

A first-class per-language status: a `(class, language)` pair whose language has failed the CPG-fidelity gate (`CMP-CP-06`). Reported as `front-end-blocked`, **never** as a recall failure (INV-6).

- **Owner:** `CMP-CP-06` (gate harness); `CMP-CORE-01` (benchmark consumer).
- **Trigger:** any of the per-language gate thresholds fails (parse success < 99.5%, call-edge precision < 90%, call-edge recall < 85%, PDG dependence-edge recall < 80% per `CLAR-CORP-02`).
- **Source:** `SDD.md §2 INV-6`; `SDD.md CMP-CP-06 AC-CP-06a`; `PLAN.md §"Phase staging"`.

### <a id="ifds-and-ide"></a>`IFDS` and `IDE`

Algorithm acronyms from the inter-procedural analysis literature.

- **IFDS** — Interprocedural Finite Distributive Subset problem. Reps–Horwitz–Sagiv, POPL 1995. Computes the meet-over-all-valid-paths solution in polynomial time when the flow functions are distributive over a finite subset lattice. Used in Scanipy v3.2 for taint-style classes (`injection`, `path-traversal`, `ssrf`, `deserialization`).
- **IDE** — Interprocedural Distributive Environment problem. Sagiv–Reps–Horwitz, TCS 1996. Extends IFDS to lattice-valued environment transformers (e.g. crypto key-size lattice). Used in Scanipy for quantitative classes.
- **Common requirement:** the flow functions must be distributive over a finite domain. In Scanipy this is discharged by the combinator-DSL closure check (`CMP-DET-01`), not by a decision procedure (INV-4).
- **Owner:** `CMP-CORE-01` (`analysis/ifds/solver.py`).
- **Source:** `PLAN.md §"Algorithm 2"`; `PLAN.md §"Literature grounding"`.

### <a id="inv-1-inv-6"></a>`INV-1..6`

The six architectural invariants. One-line each; the full contract is in `docs/cross-cutting/DOC-INV.md`.

- **INV-1** — Every finding carries `origin ∈ {deterministic-core, oracle-passthrough}`.
- **INV-2** — Every finding + provenance record carries `S_version` and `env_digest`.
- **INV-3** — No LLM output influences a `deterministic-core` finding except via an accepted pinned spec in `S`. Triage never deletes findings.
- **INV-4** — Undecidable-property approximations are one-sided (safe direction), named, and falsifier-backed.
- **INV-5** — Conditional artifacts carry their own conditional annotation in the persisted record.
- **INV-6** — Algorithm 2 recall claims are valid only for CPG-fidelity-gate-passing `(class, language)` pairs.

See: `DOC-INV.md`; `SDD.md §2` (verbatim).

### <a id="oos"></a>`OOS-*`

An `OUT-OF-SCOPE` register item. Records a derived task that implies one of the explicit out-of-scope items in `SDD.md §12`.

- **Format:** `OOS-<DOMAIN>-<NN>`.
- **Location:** appended to `WBS.md §18`.
- **Lifecycle:** terminal. An `OOS-*` entry is the final record; no work package is scheduled for it. Revisit post-v3.2.
- **Source:** `CLAUDE.md §14`; `.claude/rules/03-scope.md`.
- **Permanent v3.2 entries (from `WBS.md §18`):** `OOS-CI-AGENT-01`, `OOS-CONTAINER-SCAN-01`, `OOS-BINARY-01`, `OOS-IDE-01`, `OOS-CC-01`, `OOS-LLM-DET-01`, `OOS-ENV-INDEP-01`.

### <a id="precondition-status"></a>`precondition-status`

A snapshot-level field recording the `CW-DETECT` verdict and the routing decision.

- **Allowed values (`AC-SNAP-01b`):** `closed-world | degraded | full-reparse`. Exactly one.
- **Producer:** `CMP-SNAP-03` (`CW-DETECT`) sets the verdict; `CMP-SNAP-02` applies the routing thresholds (`θ_cone`, `θ_files`) to choose between `degraded` and `full-reparse`.
- **Persisted on:** `snapshots` row; written to the provenance record.
- **Source:** `SDD.md CMP-SNAP-01`; `PLAN.md §"Algorithm 1"`.

### <a id="provenance-record--signed-audit-chain"></a>provenance record / signed audit chain

The auditable, signed chain linking every input that determined a finding to the finding itself.

- **Chain (`SDD.md CMP-FND-03`; `PLAN.md §"Context and the objective"` property (c)):**
  ```
  source commit
    → snapshot digest
      → S_version
        → env_digest
          → cpg_order_hash (canonical iff fingerprint_class = strong)
            → taint witness
              → rule / spec id
                → SARIF hash
                  → per-finding origin
  ```
- **Owner:** `CMP-FND-03`.
- **Signing:** KMS asymmetric keys (per `DOC-DEPLOY-DECISIONS` CLAR-DEPLOY-04).
- **Re-partition events** (`CMP-SNAP-04`) append to the chain (`AC-SNAP-04c`, `AC-FND-03c`).
- **Verifiability:** the record is independently verifiable from stored artifacts without re-running analysis (`AC-FND-03a`).

### <a id="s-s_version"></a>`S`, `S_version`

`S` is the accepted version-pinned spec set; `S_version` is the semver identifying a frozen snapshot of `S` used for a given scan.

- `S` = `S_global ∪ S_customer` per `CMP-TRI-03`.
- `S_global` — accepted specs that have cleared the global-stream e-process.
- `S_customer` — accepted specs that have additionally cleared the customer-stream e-process.
- **Pinning discipline (INV-3, INV-2):** an accepted spec is written as a new row in the `spec_versions` table; the deterministic core only reads pinned `S_version` rows, never a mutable "active" pointer. `S_version` is recorded on every finding.
- **Source:** `PLAN.md §"Central correction"`; `PLAN.md §"Algorithm 6"`; `SDD.md §2 INV-2`.

### <a id="slice_fingerprint"></a>`slice_fingerprint`

Refactor-stable fingerprint of the backward interprocedural slice for a finding's witness. Produced by Algorithm 3.

- **Type:** sha256 string.
- **Refactor stability (`AC-CORE-02a`):** invariant under each of the named normalization passes: α-renaming for locals; PDG-only for formatting; canonical topological sort for independent reordering; summary-inlining for extract/inline-method (pure extract only); FQN normalization for file-move / package-rename.
- **Flips (`AC-CORE-02b`):** changes on a genuine fix and on an aliasing-changing extract.
- **Producer:** `CMP-CORE-02`.
- **Used for:** cross-scan baseline lookup, indexed on `(codebase_id, slice_fingerprint)` in `CMP-FND-02`.
- **Conditional:** paired with `fingerprint_class`. A `weak`-classed slice is never auto-suppressed across a refactor.

### <a id="spec_provenance"></a>`spec_provenance`

Per-finding labeling of the customer-revalidation status of the spec that produced the finding.

- **Allowed values:** `global-unrevalidated | global-revalidated | customer`.
  - `global-unrevalidated` — finding produced by an `S_global` spec for a customer with no labeled sample yet; default labelling. (`AC-TRI-03b`)
  - `global-revalidated` — the spec has cleared the customer-stream e-process for this customer.
  - `customer` — the spec is in `S_customer` (proposed and accepted within the customer scope).
- **Owner:** `CMP-TRI-03`.
- **Source:** `SDD.md CMP-TRI-03`; `PLAN.md §"Covariate shift"`.

### <a id="stage-gated"></a>`STAGE-GATED` (status code)

A WBS work-package status: implementation could otherwise start (no missing dependencies) but is blocked by a per-language staging gate (`CMP-CP-06`).

- **Distinct from `BLOCKED`:** `BLOCKED` indicates an unmet `Depends-On`; `STAGE-GATED` indicates a passing dependency DAG but a failing CPG-fidelity gate for the relevant language.
- **Remediation:** advance the stage (typically by closing front-end fidelity gaps, e.g. `T-STAGE-C-FE-01`), not by unblocking a dependency.
- **Source:** `WBS.md §1.2`; `.claude/rules/04-staging.md`.

### <a id="blocked"></a>`BLOCKED` (status code)

A WBS work-package status: has unmet `Depends-On` (per the DAG in `WBS.md §20`).

- **Distinct from `STAGE-GATED`** — see above.
- **Remediation:** drive the dependency component to `DONE` (every `TST-AC-*` green).
- **Source:** `WBS.md §1.2`.

### <a id="stage-a-d"></a>`Stage A..D`

The per-language staging order, derived from CPG front-end fidelity.

- **Stage A — Java + Python.** Strongest Joern front-ends. Classes promoted to core: `injection`, `path-traversal`, `ssrf`, `deserialization`. Algorithm 2 falsifier is first meaningful here.
- **Stage B — JS / TS.** Begins after Stage A is determinism-attested and `CMP-CP-06` green for JS/TS.
- **Stage C — Go.** Requires a points-to / interface-dispatch investment (`T-STAGE-C-FE-01`, `CLAR-FE-02`) before the fidelity gate passes.
- **Stage D — Ruby + PHP.** Lowest front-end maturity; may require a proprietary front-end work package (`T-STAGE-D-FE-01`, `CLAR-FE-01`). Until the gate passes, Ruby and PHP ship `oracle-passthrough` only.
- **C/C++ (memory-safety)** remains `oracle-passthrough` (CodeQL) throughout v3.2 (`OOS-CC-01`).
- **Source:** `SDD.md §11`; `PLAN.md §"Phase staging"`; `CLAUDE.md §7`; `.claude/rules/04-staging.md`.

### <a id="witness_blob_uri"></a>`witness_blob_uri`

URI of the persisted taint-witness blob for a finding, stored in S3 per `DOC-DEPLOY-DECISIONS` CLAR-DEPLOY-02.

- **Type:** string (S3 URI).
- **Nullability:** nullable. NULL is permitted for oracle findings without a slice (e.g. a pattern-style match with no IFDS witness).
- **Producer:** `CMP-ORCH-03` (writes the blob, populates the URI).
- **Persisted on:** `findings` row; included in the signed provenance record.
- **Source:** `SDD.md CMP-FND-02`; `.claude/rules/02-provenance.md`.

---

## 4. References

- `PLAN.md` — primary source for algorithm definitions and theorem statements.
- `SDD.md` — primary source for component IDs, acceptance criteria, INV statements (`§2`).
- `WBS.md §1.2` — status codes (`BLOCKED`, `READY`, `IN-PROGRESS`, `DONE`, `STAGE-GATED`).
- `WBS.md §17` — CLAR-* register.
- `WBS.md §18` — OOS-* register.
- `WBS.md §20` — dependency DAG.
- `CLAUDE.md §3` — invariant owner table.
- `CLAUDE.md §4` — seed glossary (mirrored and expanded here).
- `CLAUDE.md §7` — per-language staging gates.
- `docs/cross-cutting/DOC-INV.md` — full INV-1..6 contract.
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — resolved technology stack.
- `.claude/rules/00-global.md` — RULE-1..10.
- `.claude/rules/02-provenance.md` — provenance-threading operational rules.
- `.claude/rules/04-staging.md` — staging-gate operational rules.
- `.claude/rules/05-determinism.md` — determinism-partition operational rules.

---

*Every agent loads this file at session start (per `CLAUDE.md §13` reading guide step 2). Update this file when `PLAN.md` / `SDD.md` change; never edit those files from this document. If a term is unclear and no source-of-truth pin exists, file a `CLAR-*` in `WBS.md §17` rather than designing the definition inline.*
