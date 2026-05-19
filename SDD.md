# Scanipy v3.2 — Software Design Document

**Document status:** Design baseline for work-breakdown derivation
**Source of truth:** `PLAN.md` (Scanipy v3.2 Architecture). Where this SDD and the architecture disagree, the architecture wins; report the discrepancy rather than resolving it silently.
**Intended consumer:** an automated planning model that will derive a Work Breakdown Structure (WBS) from this document.

---

## 0. How to use this document (instructions for the WBS-deriving model)

This SDD is written so that work packages can be derived mechanically. Every buildable unit appears as a **Component Specification** with a stable `CMP-ID`, an explicit dependency list, an interface contract, and a set of **Acceptance Criteria** (`AC-*`) that are individually testable. The WBS model should:

1. Treat each `CMP-ID` as a candidate work package or epic. Components with no unmet dependencies are eligible to start.
2. Use the `Depends-On` field to build the dependency DAG. Do not schedule a component before its dependencies' Acceptance Criteria are met.
3. Use the `Staging` field (Stage A–D, or `cross-cutting`) to respect the per-language sequencing constraint from the architecture. A component tagged `Stage B` must not be scheduled before the `Stage A` core components it depends on have passed their ACs.
4. Treat every `AC-*` as a verification task that must have a corresponding test artifact in the WBS.
5. Treat every item in §11 (Risks) as requiring a mitigation task in the WBS.
6. Do not invent scope. If a capability is needed but not specified here, emit a `CLARIFICATION-NEEDED` work item rather than designing it.

Component IDs are stable; do not renumber. Dependency edges are directional (`A Depends-On B` means B must precede A).

---

## 1. System overview

Scanipy v3.2 is a multi-tenant SaaS static application security testing (SAST) platform whose detection results are a deterministic, incrementally-recomputable function of source code under a fixed, version-pinned spec set and analysis environment. The platform organizes detection by vulnerability class, runs over a single shared Code Property Graph (CPG) snapshot per commit, scales across heterogeneous source-control providers, and confines LLM use to triage and gated spec inference that never sits on the deterministic detection path.

The system is defined by the function `F : (source, S, Policy ; Env) → FindingSet`, where `source` is a codebase at a commit, `S` is the version-pinned accepted-spec set, `Policy` is per-organization configuration, and `Env` is the pinned analysis environment. The platform's three load-bearing properties are: (a) reproducibility under a fixed environment for the deterministic-core finding partition; (b) incremental computability proportional to the semantic delta of a commit; and (c) machine-checkable provenance for every finding.

### 1.1 Subsystem map

The system decomposes into eight subsystems, each owning a set of components:

- **SCM Integration** — connector abstraction over GitHub/GHE, GitLab, Bitbucket, Azure DevOps.
- **Snapshotter** — clone, incremental CPG construction, closed-world precondition detection, environment pinning.
- **Detector Catalog** — vulnerability-class plugins, the combinator DSL, the registration closure check.
- **Analysis Core** — IFDS/IDE solver, slice fingerprinting, canonical ordering.
- **Orchestration** — scan API, the heuristic scheduler, the detector-agnostic worker.
- **Findings & Provenance** — normalizer, partition tagging, provenance record, store schema.
- **Triage & Spec Inference** — LLM ranking, the anytime-valid e-process spec gate, per-customer revalidation.
- **Control Plane & Attestation** — multi-tenant API, dashboard, the partitioned Determinism Attestor.

---

## 2. Architectural invariants (must hold across all components)

These invariants constrain every component. A WBS task that would violate one is malformed.

- **INV-1 (Determinism partition).** Every finding carries an `origin ∈ {deterministic-core, oracle-passthrough}`. Only `deterministic-core` findings are covered by the reproducibility theorem. No component may emit a finding without a correct `origin`.
- **INV-2 (Versioned parameters).** Every finding and every provenance record carries `S_version` and `env_digest`. No analysis may run against an unpinned `S` or `Env`.
- **INV-3 (LLM off the detection path).** No LLM output may influence a `deterministic-core` finding except through an already-accepted, version-pinned spec in `S`. Triage ranking never deletes or suppresses findings.
- **INV-4 (Conservative undecidable approximations are one-sided and owned).** Any component that approximates an undecidable property (reachable reflection, flow-function distributivity) must approximate in the safe direction, must name its owning module, and must have a dedicated falsifier.
- **INV-5 (Conditional labels are self-describing).** Any artifact whose correctness is conditional (e.g. canonicality of the CPG order hash) must carry its own conditional annotation in the persisted record.
- **INV-6 (Per-language honesty).** Algorithm 2 precision/recall claims are valid only for `(class, language)` pairs that have passed the CPG-fidelity gate. Front-end-blocked pairs are reported as blocked, never as recall failures.

---

## 3. SCM Integration subsystem

### CMP-SCM-01 — `SCMConnector` abstract base
**Staging:** cross-cutting · **Depends-On:** none
**Purpose:** Provider-neutral interface for repository access and webhook lifecycle.
**Interface:** abstract methods `list_repos`, `clone`, `register_webhook`, `verify_webhook`, `get_default_branch`, `resolve_commit`; credential abstraction `SCMCredentials` covering PAT, app installation, OAuth, SSH key.
**Acceptance criteria:**
- AC-SCM-01a: ABC defines all six methods with typed signatures and a documented contract for each.
- AC-SCM-01b: `SCMCredentials` round-trips all four auth modes through encryption at rest (depends on CMP-CP-02 for the key service; until then, mock).
- AC-SCM-01c: A conformance test suite exists that any concrete connector must pass.

### CMP-SCM-02 — GitHub connector
**Staging:** cross-cutting · **Depends-On:** CMP-SCM-01
**Purpose:** Subsume the existing `integrations/github/github.py`; preserve retry/backoff and tiered-star helpers verbatim; expose `search_code()` for Research mode only.
**Acceptance criteria:**
- AC-SCM-02a: Passes the CMP-SCM-01 conformance suite.
- AC-SCM-02b: Existing retry, rate-limit, and tiered-star behavior is byte-for-byte preserved (regression test against current behavior).
- AC-SCM-02c: `integrations/github/__init__.py` exports `search_repositories` as a shim with no caller-visible change.

### CMP-SCM-03 — GitLab / Bitbucket / Azure DevOps connectors
**Staging:** cross-cutting · **Depends-On:** CMP-SCM-01, CMP-SCM-05
**Purpose:** Three concrete connectors implementing the ABC against each provider's REST API and webhook signature scheme.
**Acceptance criteria:**
- AC-SCM-03a: Each passes the CMP-SCM-01 conformance suite.
- AC-SCM-03b: Webhook signature verification rejects forged payloads for each provider (negative test).
- AC-SCM-03c: A single canary repository mirrored to all four providers produces identical commit resolution.

### CMP-SCM-05 — Shared HTTP retry/backoff
**Staging:** cross-cutting · **Depends-On:** none
**Purpose:** Lift the retry/backoff/rate-limit pattern into a shared module reused by all connectors.
**Acceptance criteria:**
- AC-SCM-05a: Exponential backoff with jitter and provider-specific rate-limit honoring is unit-tested against simulated 429/secondary-limit responses.

---

## 4. Snapshotter subsystem

### CMP-SNAP-01 — Snapshot service API
**Staging:** Stage A · **Depends-On:** CMP-SCM-01, CMP-FND-03
**Purpose:** `POST /snapshots {codebase_id, commit_sha}` enqueues a snapshot job; persists CPG tarball, reverse-symbol index, dynamic call graph, `ΔG`, and a precondition-status record.
**Acceptance criteria:**
- AC-SNAP-01a: A snapshot request for a known commit produces all five persisted artifacts at deterministic S3 keys.
- AC-SNAP-01b: The precondition-status record records exactly one of `closed-world | degraded | full-reparse`.
- AC-SNAP-01c: `env_digest` is computed from the pinned container image digest and recorded on the snapshot.

### CMP-SNAP-02 — Incremental CPG maintenance (Algorithm 1)
**Staging:** Stage A · **Depends-On:** CMP-SNAP-01, CMP-SNAP-03
**Purpose:** Compute `G'`, `ΔG`, and `AFFECTED` from a parent snapshot when the closed-world precondition holds; otherwise apply the points-to-bounded cone and the `θ_cone`/`θ_files` reparse fallback.
**Acceptance criteria:**
- AC-SNAP-02a: **[CONDITIONAL THEOREM test]** On a closed-world corpus with the precondition asserted per commit, `time(Δ-rebuild) ≤ κ · (|AFFECTED|/|graph|) · time(full-rebuild)` for a frozen `κ`; a regression above `κ` fails.
- AC-SNAP-02b: **[EMPIRICAL test]** On an open-world corpus, measured median speedup ≥ 5×, p95 ≥ 2× versus full reparse, fallback rate ≤ 15%.
- AC-SNAP-02c: Function-granularity reparse preserves node IDs for unchanged declarations (keyed on enclosing-declaration content hash).

### CMP-SNAP-03 — `CW-DETECT` closed-world precondition detector
**Staging:** Stage A · **Depends-On:** none
**Purpose:** One-sided conservative detector for reachable reflection / dynamic dispatch over an open hierarchy. Owner of Algorithm 1's precondition (INV-4).
**Acceptance criteria:**
- AC-SNAP-03a: **[Falsifier CW]** Zero false negatives on the curated reflection corpus (Spring dynamic proxies, Python `__import__`/`getattr`, Ruby `send`/`method_missing`, PHP variable functions, Java `Class.forName`, plus mutation-injected reflection). A single false negative is a release blocker.
- AC-SNAP-03b: False positives are permitted; the combined true-positive + false-positive routing rate is measured and reported (this, not the true reflection rate, is what the ≤15% target governs).

### CMP-SNAP-04 — Differential reflection oracle
**Staging:** Stage A · **Depends-On:** CMP-SNAP-03, CMP-FND-02
**Purpose:** Asynchronous whole-program reflection scanner off the critical path; on disagreement with `CW-DETECT`, raise a determinism incident and retroactively re-partition affected findings from `deterministic-core` to `oracle-passthrough`.
**Acceptance criteria:**
- AC-SNAP-04a: A seeded `CW-DETECT` false negative is detected by the oracle and triggers re-partitioning of exactly the affected findings.
- AC-SNAP-04b: The labeling-correction window (fast decision → async oracle verdict) is measured and a contractual SLA value is produced for it.
- AC-SNAP-04c: Every re-partition event is written to provenance.

### CMP-SNAP-05 — Snapshot worker + environment pinning
**Staging:** Stage A · **Depends-On:** CMP-SNAP-01
**Purpose:** Worker mirroring the existing semgrep worker contract (env-var contract, `report_status`, argument allowlist, secure `subprocess.run`); Dockerfile bundling `joern`, `codeql`, `git` pinned by digest into `Env`.
**Acceptance criteria:**
- AC-SNAP-05a: The argument allowlist rejects any flag not on the sanctioned list (negative test).
- AC-SNAP-05b: The container image digest is the authoritative `env_digest` and changing any bundled tool changes the digest.

---

## 5. Detector Catalog subsystem

### CMP-DET-01 — Combinator DSL for taint specs
**Staging:** cross-cutting · **Depends-On:** none
**Purpose:** A declarative DSL whose primitives (`source`, `sink`, `sanitize`, `propagate`, sanctioned compositions) are distributive-by-construction over the finite fact domain. Owner of Algorithm 2's precondition (INV-4).
**Acceptance criteria:**
- AC-DET-01a: Each combinator carries a machine-checked distributivity proof obligation (`f(X ∪ Y) = f(X) ∪ f(Y)` exhaustively over the bounded domain); CI fails if a combinator lacks a discharged obligation.
- AC-DET-01b: The DSL grammar admits no escape hatch to non-DSL code; a spec embedding arbitrary code is rejected, not analyzed.

### CMP-DET-02 — Detector registry + closure check
**Staging:** cross-cutting · **Depends-On:** CMP-DET-01
**Purpose:** Discover `detectors/<class>/`, load `manifest.yaml`, run the grammar/closure check (membership in the distributive DSL — not a distributivity decision procedure), derive `determinism_partition` from the `engine` field.
**Acceptance criteria:**
- AC-DET-02a: Registration rejects a spec outside the DSL with a precise diagnostic.
- AC-DET-02b: Manifest records `id`, `cwes`, `languages`, `frameworks`, `engine`, `severity_default`, derived `determinism_partition`, per-language readiness.
- AC-DET-02c: `engine ∈ {ifds, ide}` ⇒ partition `deterministic-core`; `engine ∈ {semgrep, cpg-query, external}` ⇒ `oracle-passthrough`.

### CMP-DET-03 — Class plugin scaffolding + content migration
**Staging:** per class (see §10) · **Depends-On:** CMP-DET-02
**Purpose:** Ten `detectors/<class>/` directories with `specs/` skeletons; migrate `tarslip.yaml` → `detectors/path-traversal/specs/`; migrate CodeQL queries → `detectors/memory-safety/codeql/` tagged `oracle`.
**Acceptance criteria:**
- AC-DET-03a: All ten class directories register without error (stubs permitted).
- AC-DET-03b: The migrated path-traversal spec produces the historical CVE-2025-61765 finding (ties to AC-ORCH backwards-compat).

---

## 6. Analysis Core subsystem

### CMP-CORE-01 — IFDS/IDE tabulation solver (Algorithm 2)
**Staging:** Stage A (then per-language) · **Depends-On:** CMP-DET-01, CMP-SNAP-02, CMP-CORE-03
**Purpose:** Exploded-supergraph construction and the RHS Tabulation algorithm with reusable procedure summaries; IDE extension for lattice-valued classes; incremental mode invalidating only `AFFECTED` summaries.
**Acceptance criteria:**
- AC-CORE-01a: **[Determinism]** 100 canary repos × 5 re-runs under fixed `(S, Env)` produce identical pre-serialization solution hashes; one mismatch falsifies the precondition or reveals a DSL escape.
- AC-CORE-01b: **[Value, per (class, language)]** On CPG-fidelity-gate-passing pairs only, recall ≥ Semgrep-default + 10pp at equal precision on OWASP Benchmark + Juliet + held-out BigVul.
- AC-CORE-01c: Incremental re-tabulation visits only `AFFECTED` entry points and their transitive callers.

### CMP-CORE-02 — Slice fingerprint (Algorithm 3)
**Staging:** Stage A · **Depends-On:** CMP-CORE-01, CMP-CORE-03
**Purpose:** Backward interprocedural slice along the witness; the named normalization passes (α-renaming, PDG-only formatting, canonical topological sort, summary-inlining for extract/inline, FQN normalization for file-move); bounded canonicalization with the `weak` fallback.
**Acceptance criteria:**
- AC-CORE-02a: Fingerprint invariant under each named refactor on 50 seeded findings.
- AC-CORE-02b: Fingerprint changes on a genuine fix and on an aliasing-changing extract.
- AC-CORE-02c: `weak`-fallback rate measured and < 5%; a `weak`-classed finding is never auto-suppressed across a refactor.

### CMP-CORE-03 — Canonical CPG ordering (Algorithm 5)
**Staging:** Stage A · **Depends-On:** none
**Purpose:** 2-WL refinement, bounded individualization-refinement under hard `(B, T)` budget, and the deterministic stable-order fallback on budget exhaustion. Produces `cpg_order_hash` annotated `canonical iff fingerprint_class = strong` (INV-5).
**Acceptance criteria:**
- AC-CORE-03a: On CFI-style symmetric inputs the algorithm terminates within `(B, T)` and still yields a deterministic same-source order.
- AC-CORE-03b: Budget-exhaustion rate on real code measured and < 1%.
- AC-CORE-03c: The persisted hash field is named `cpg_order_hash` and carries the conditional-canonicality annotation everywhere it appears.

---

## 7. Orchestration subsystem

### CMP-ORCH-01 — Scan API
**Staging:** Stage A · **Depends-On:** CMP-SNAP-01, CMP-FND-01, CMP-CP-01
**Purpose:** `POST /api/v1/scans {codebase_id, commit_sha, detector_ids[]}`; `GET /api/v1/scans/{id}`, `…/findings`; worker callback `POST /api/v1/jobs/{job_id}/status` preserving the HMAC-bearer pattern.
**Acceptance criteria:**
- AC-ORCH-01a: A scan creates a snapshot if absent, then fans one job per detector.
- AC-ORCH-01b: The worker callback rejects a payload with an invalid HMAC (negative test).
- AC-ORCH-01c: Backwards-compat: `scanipy --query extractall --run-semgrep` via Research mode still yields the CVE-2025-61765 path-traversal finding with `origin=deterministic-core` on a Stage-A language.

### CMP-ORCH-02 — Heuristic scheduler `SNAP-SCHED-H` (Algorithm 4)
**Staging:** cross-cutting · **Depends-On:** CMP-ORCH-01
**Purpose:** Snapshot-affinity grouping (amortize CPG load `L`), independent-moldable 2-approx allotment as a heuristic seed only, LPT list-scheduling with dependence-aware deferral, policy-gating classes first. No constant-factor guarantee is claimed.
**Acceptance criteria:**
- AC-ORCH-02a: **[Empirical p95]** Production-shaped replay at the provisioned worker count yields p95 end-to-end scan latency < 30 min.
- AC-ORCH-02b: Two runs under different schedules produce identical `deterministic-core` findings (cross-checked by the Attestor).
- AC-ORCH-02c: ρ≈2 appears in documentation only as the relaxation bound, never as a guarantee.

### CMP-ORCH-03 — Detector-agnostic worker
**Staging:** Stage A · **Depends-On:** CMP-CORE-01, CMP-DET-02, CMP-FND-01
**Purpose:** Load the snapshot CPG once, resolve the detector via the registry, run IFDS for core classes or the oracle adapter otherwise, stamp `origin` and `determinism_partition`, emit SARIF.
**Acceptance criteria:**
- AC-ORCH-03a: Every emitted finding has a correct `origin` (INV-1).
- AC-ORCH-03b: A `mixed`-class detector emits per-finding `origin` (some core, some oracle) without blurring.

---

## 8. Findings & Provenance subsystem

### CMP-FND-01 — Findings normalizer
**Staging:** Stage A · **Depends-On:** CMP-CORE-02, CMP-CORE-03
**Purpose:** Normalize every detector output to SARIF 2.1.0; attach the slice fingerprint; emit results in canonical CPG order.
**Acceptance criteria:**
- AC-FND-01a: All detector outputs validate against SARIF 2.1.0 schema.
- AC-FND-01b: Result ordering is the canonical order from CMP-CORE-03.

### CMP-FND-02 — Findings store schema
**Staging:** cross-cutting · **Depends-On:** CMP-CP-03
**Purpose:** `findings` table with `slice_fingerprint`, `fingerprint_class`, `origin`, `determinism_partition`, `witness_blob_uri`, `S_version`, `env_digest`, `cpg_order_hash`, `triage_score`, `triage_reason`, `status`; index on `(codebase_id, slice_fingerprint)`.
**Acceptance criteria:**
- AC-FND-02a: Cross-scan baseline lookup by `(codebase_id, slice_fingerprint)` is correct and never auto-suppresses a `weak` or `oracle-passthrough` finding across a refactor.
- AC-FND-02b: Every row carries a non-null `origin`, `S_version`, `env_digest` (INV-1, INV-2).

### CMP-FND-03 — Signed provenance record
**Staging:** Stage A · **Depends-On:** CMP-FND-02
**Purpose:** The auditable chain `source commit → snapshot digest → S_version → env_digest → cpg_order_hash (canonical iff strong) → taint witness → rule/spec id → SARIF hash → per-finding origin`, signed.
**Acceptance criteria:**
- AC-FND-03a: The record is independently verifiable from stored artifacts without re-running analysis.
- AC-FND-03b: The `cpg_order_hash` field carries its conditional-canonicality annotation in the auditor export (INV-5).
- AC-FND-03c: Differential-oracle re-partition events appear in the record.

---

## 9. Triage & Spec Inference subsystem

### CMP-TRI-01 — LLM triage ranking
**Staging:** post-core · **Depends-On:** CMP-FND-02
**Purpose:** Score `(likely_exploitable, likely_test_code, likely_fp)` from the SARIF blob plus a bounded code window; write `triage_score`/`triage_reason`. Feature-flagged, default off. Never deletes findings.
**Acceptance criteria:**
- AC-TRI-01a: With the triage flag off, no finding row's `origin` or detection content is affected (INV-3).
- AC-TRI-01b: Ranking writes only `triage_*` columns.

### CMP-TRI-02 — Anytime-valid e-process spec gate (Algorithm 6)
**Staging:** post-core · **Depends-On:** CMP-DET-02, CMP-FND-02
**Purpose:** An e-process per candidate spec for the precision-floor null `H0(σ): true precision < π₀`, valid under unbounded optional continuation (Ville's inequality); acceptance when `E_t(σ) ≥ 1/α`; multiplicity over selected specs by e-process averaging; no information horizon.
**Acceptance criteria:**
- AC-TRI-02a: **[Adversarial unbounded continuation]** Over many repeated campaigns with an over-broad spec and no finite horizon supplied, realized ever-false-acceptance rate ≤ α.
- AC-TRI-02b: The e-process implementation passes a martingale-property unit test (empirical `E[E_τ|H0] ≤ 1` across simulated stopping times) before production enablement.
- AC-TRI-02c: An accepted spec is written version-pinned as a new `S_version`; the deterministic core only ever consumes pinned specs (INV-3).

### CMP-TRI-03 — Per-customer revalidation + drift monitor
**Staging:** post-core · **Depends-On:** CMP-TRI-02
**Purpose:** `S = S_global ∪ S_customer`; the same e-process instrument run on the customer's adjudicated stream; auto-quarantine on a floor breach; `spec_provenance = global-unrevalidated` labeling until customer revalidation.
**Acceptance criteria:**
- AC-TRI-03a: A global-accepted spec on an adversarial customer distribution is quarantined by the shared e-process.
- AC-TRI-03b: Findings dependent on an unrevalidated global spec carry `global-unrevalidated` until revalidation.

---

## 10. Control Plane & Attestation subsystem

### CMP-CP-01 — Multi-tenant scan API guard
**Staging:** cross-cutting · **Depends-On:** CMP-CP-03
**Purpose:** Require `X-Scanipy-Org-Id` with `X-Scanipy-User-Id`; scope every query to the org; enforce RBAC in the API layer.
**Acceptance criteria:**
- AC-CP-01a: A cross-org access attempt is denied (parameterized negative test, no IAM cross-bleed).

### CMP-CP-02 — Credential encryption service
**Staging:** cross-cutting · **Depends-On:** none
**Purpose:** Encrypt `scm_credentials` at rest; provide the key service CMP-SCM-01 depends on.
**Acceptance criteria:**
- AC-CP-02a: Credentials are unreadable at rest without the managed key; rotation is supported.

### CMP-CP-03 — Tenancy schema + migrations
**Staging:** cross-cutting · **Depends-On:** none
**Purpose:** Tables `orgs`, `projects`, `codebases`, `scm_credentials`, `org_policies`, `memberships`, `snapshots` (+precondition-status), `proposed_specs`, `spec_versions`, `attestations`; reuse the existing `BaseDatabase`.
**Acceptance criteria:**
- AC-CP-03a: Migrations apply forward and roll back cleanly on a fresh database.

### CMP-CP-04 — Authentication (OIDC/SAML) + dashboard
**Staging:** cross-cutting · **Depends-On:** CMP-CP-01, CMP-FND-03
**Purpose:** OIDC/SAML in `web/auth.ts`/`web/middleware.ts`; dashboard tree orgs → projects → codebases → scans → findings grouped by class; each finding renders its witness, `origin`, `S_version`, `env_digest`, and the conditional-canonicality annotation.
**Acceptance criteria:**
- AC-CP-04a: SSO sign-up provisions an org row plus first-admin membership.
- AC-CP-04b: The findings view never visually blurs `deterministic-core` and `oracle-passthrough`.

### CMP-CP-05 — Determinism Attestor (partitioned)
**Staging:** Stage A · **Depends-On:** CMP-ORCH-01, CMP-FND-03
**Purpose:** Two pipelines. Core: re-run `F` under fixed `(S_version, env_digest, LLM_TRIAGE=off)` and assert byte-identical SARIF over the core partition (hard fail on diff). Oracle: record oracle digests and report a measured reproduction rate with no theorem attached.
**Acceptance criteria:**
- AC-CP-05a: A deliberately introduced nondeterminism in the core path fails the core pipeline.
- AC-CP-05b: The oracle pipeline reports a numeric reproduction rate and never asserts the theorem.
- AC-CP-05c: CI runs both pipelines on the canary corpus on every detector / engine / `Env` change.

### CMP-CP-06 — CPG-fidelity gate harness
**Staging:** per language · **Depends-On:** CMP-SNAP-05
**Purpose:** Per-language fidelity corpus with ground-truth ASTs/CFGs/call-edges; gate thresholds (parse success ≥ 99.5%, call-edge precision/recall thresholds, PDG dependence-edge recall threshold). A `(class, language)` pair enters the Algorithm 2 benchmark only after passing.
**Acceptance criteria:**
- AC-CP-06a: A language failing the gate is reported `front-end-blocked`, not as a recall failure (INV-6).
- AC-CP-06b: Gate results are recorded per language and consulted by the WBS staging logic.

---

## 11. Staging plan (per-language sequencing constraint)

The IFDS core over a uniform CPG is the principal deliverable, not substrate. The WBS must respect this order; a stage may not begin until the prior stage's core components have passed their ACs and the relevant CPG-fidelity gate (CMP-CP-06) has passed for that language.

- **Stage A — Java + Python.** Strongest front-ends. Classes to core: injection, path-traversal, ssrf, deserialization. Algorithm 2 falsifier (AC-CORE-01b) is first meaningful here.
- **Stage B — JS/TS.** Begins only after the Stage-A core is determinism-attested (CMP-CP-05 green for Stage A).
- **Stage C — Go.** Front-end fidelity gate first; expect a points-to / interface-dispatch investment as a prerequisite work package.
- **Stage D — Ruby, PHP.** Lowest front-end maturity; ship `oracle-passthrough` only until the fidelity gate passes; the gate likely requires a proprietary front-end work package.
- **C/C++ (memory-safety).** Remains `oracle-passthrough` (CodeQL) throughout v3; the port to core is tracked but explicitly out of v3 scope.

`secrets` and `dep-cve` are `oracle-passthrough` throughout (deterministic in practice, attested, not theorem-covered). `crypto-misuse` and `authn-authz` are `mixed`; their IDE/IFDS portion follows the staging of its language, the pattern portion ships oracle-passthrough.

---

## 12. Cross-cutting concerns the WBS must instantiate as tasks

- **Test corpora as deliverables.** The reflection corpus (CMP-SNAP-03), the CPG-fidelity corpora per language (CMP-CP-06), the canary repo set across four SCMs (CMP-CP-05), the seeded-refactor set (CMP-CORE-02), and the OWASP/Juliet/BigVul slices (CMP-CORE-01) are themselves work packages with their own acceptance, not assumed inputs.
- **CI gates.** AC-DET-01a, AC-SNAP-03a, AC-CP-05c, and AC-TRI-02b are continuous gates; the WBS must create a CI-pipeline work package that enforces all four.
- **Provenance threading.** Every subsystem that emits or mutates a finding must thread `S_version`, `env_digest`, `origin`, and (where applicable) the conditional annotation; the WBS should add a verification task per emitting component rather than one global task.
- **Out of scope (do not create tasks):** CI-agent / on-prem runner, container-image scanning, binary-only analysis, IDE plugin. If a derived task implies any of these, emit `OUT-OF-SCOPE` instead.

---

## 13. Risks the WBS must carry mitigation tasks for

- **R-1 (Undecidable preconditions leak).** `CW-DETECT` false negative ships a wrong `deterministic-core` label. Mitigation owner: CMP-SNAP-04 differential oracle; the WBS must schedule the oracle in the same stage as CMP-SNAP-02, not later.
- **R-2 (Front-end fidelity dominates schedule).** Joern quality varies by language; weak front-ends silently depress AC-CORE-01b. Mitigation: CMP-CP-06 gate precedes every Algorithm 2 benchmark; Stage C/D carry explicit front-end-investment work packages.
- **R-3 (Spec gate misuse).** An e-process used without the martingale unit test invalidates the guarantee. Mitigation: AC-TRI-02b is a hard production-enablement gate.
- **R-4 (Determinism regression invisible to same-path re-run).** A canary re-run reproduces a wrong path. Mitigation: the differential oracle (R-1) plus the Attestor's core/oracle partition split (CMP-CP-05) — both required, neither sufficient alone.
- **R-5 (Detector catalog chicken-and-egg).** Stubbed classes block adoption. Mitigation: Stage-A classes (injection, path-traversal, ssrf, deserialization) are the minimum shippable set; the WBS should front-load them and treat the other six as post-Stage-A increments.

---

## 14. Definition of done for the v3.2 baseline

The v3.2 baseline is complete when: every Stage-A component's ACs pass; CMP-CP-05 reports byte-identical core-partition SARIF across the canary corpus; CMP-SNAP-04 demonstrably re-partitions on a seeded `CW-DETECT` false negative; CMP-TRI-02 passes the adversarial unbounded-continuation test with the martingale unit test green; and the honest-labeling ledger in `PLAN.md` is reproduced as a living status table driven by AC pass/fail rather than as prose.
