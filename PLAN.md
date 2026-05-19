# Scanipy v3.2 Architecture: Algorithmically-Grounded, Auditable, Multi-SCM, At-Scale

## Revision note (v3.2 — discharging the hypotheses)

v3.1 attached a precondition, a degradation model, and a falsifier to every load-bearing claim. The follow-up review identified four places where a guarantee was stated over an object whose own status (decidability, soundness, well-definedness) was left implicit, plus one sequencing observation. v3.2 resolves all five. The ambition is unchanged; the hypotheses now have explicit owners.

Summary of what changed:

1. **Precondition detectors are now first-class claims with a soundness direction.** The closed-world detector (Algorithm 1) and the non-distributive-spec rejector (Algorithm 2) are conservative over-approximations of undecidable properties. v3.2 promotes the *soundness direction* of each to a separately falsified claim and states the consequence for property (a) in both the sound-but-conservative and the unsound-leak cases.
2. **The "distributivity validator" is restated as a combinator-DSL closure check**, not a decision procedure for an undecidable semantic property.
3. **The α-spending instrument is replaced by an anytime-valid e-process.** This is the one item that was not merely overstated but wrong for the stated continuous-revalidation usage. The acceptance gate and the drift monitor now share one instrument: an e-process for the precision-floor null, valid under unbounded optional continuation.
4. **The provenance field is renamed** `cpg_order_hash` with an explicit conditional-canonicality annotation, so the record states its own status to an auditor.
5. **The phase plan stages the IFDS core language-by-language**, with each class's launch gated on demonstrated per-language CPG fidelity rather than presented as simultaneous.

The honest-labeling ledger is updated to reflect all five.

## The central correction, carried forward from v3.1

The accepted spec set `S` is an LLM-derived input to `F`. The defensible proposition is **not** "the LLM is outside `F`" but: *for a frozen, version-pinned `S` and a fixed analysis environment `Env`, `F` restricted to the deterministic-core partition is a deterministic function of `(source, S, Env)`.* `S` and `Env` are explicit versioned parameters of `F` throughout, recorded on every finding and in provenance. Determinism is scoped to reproducibility under a fixed environment, not environment-independent determinism.

## Context and the objective

Scanipy today is GitHub-search-driven: the CLI finds repos via the GitHub Search API, then runs Semgrep through an ECS Fargate fanout or invokes CodeQL locally. Coverage is one Semgrep rule and five CodeQL queries; the architecture is tool-driven and source-driven (GitHub only).

```
F : (source, S, Policy ; Env) → FindingSet
```

`source` is a codebase at a commit; `S` is the version-pinned accepted-spec set; `Policy` is per-org configuration; `Env` is the pinned analysis environment (engine binary versions, OS, container image digest, library versions, Joern/CodeQL/Semgrep toolchain digests). Three properties carry the wedge:

- **(a) Reproducibility under fixed environment [CONDITIONAL THEOREM].** For fixed `(S, Env)` and `LLM_TRIAGE=off`, `F` restricted to the deterministic-core partition is a deterministic function of `source`. *Preconditions:* the finding is core-partition (Algorithm 2) **and** the snapshot satisfied the closed-world precondition or was routed to the sound degraded path (Algorithm 1). The soundness of those preconditions is itself a claim with an owner (§Precondition soundness).
- **(b) Incremental computability.** `O(Δ)` **[CONDITIONAL THEOREM under CHA closed-world]**; measured median speedup **[EMPIRICAL under open-world]** (Algorithm 1).
- **(c) Provenance.** A logged construction, hence unconditional: `source commit → snapshot digest → S version → Env digest → cpg_order_hash (canonical iff strong) → taint witness → rule/spec id → SARIF hash → per-finding origin`.

### Literature grounding (scoped to what each result licenses)

Unchanged from v3.1 in substance: Yamaguchi et al. (CPG, S&P 2014) licenses the IR only; Reps–Horwitz–Sagiv (IFDS, POPL 1995) / Sagiv–Reps–Horwitz (IDE, TCS 1996) license order-independence of the solution **for distributive, finite flow functions**; Horwitz–Reps–Binkley (PLDI 1988) licenses that a backward slice is well-defined but not refactor-invariance; Demers–Reps–Teitelbaum (POPL 1981) licenses optimal-time incremental re-evaluation **only over a static dependency DAG**; Turek–Wolf–Yu / Jansen–Ohnesorge license a constant-factor moldable bound **only for independent tasks with a priori speedups and no shared setup**; Cai–Fürer–Immerman (1992) and McKay–Piperno (nauty/Traces) establish the canonicalization ceiling; IRIS (Li, Dutta, Naik, ICLR 2025) evidences LLM spec inference but licenses no unbounded ingestion. **Added for v3.2:** Robbins (1970) and Howard, Ramdas, McAuliffe, Sekhon (2021) on time-uniform confidence sequences; Ramdas, Grünwald, Vovk, Shafer (2023, *Game-theoretic statistics and safe anytime-valid inference*) and Waudby-Smith & Ramdas (2024, betting confidence sequences for bounded means) on e-processes — these license the anytime-valid precision-floor instrument in Algorithm 6.

Locked decisions are unchanged: multi-tenant SaaS; git providers only as first-class sources; LLM for triage and spec inference only; Research mode preserved as a parallel feed.

## Precondition soundness — discharging the hypotheses of Theorems (a) and 1

Both load-bearing theorems are conditional on a gatekeeper that decides an undecidable property by conservative over-approximation. The theorems are correct; their hypotheses need owners. v3.2 makes the soundness *direction* of each gatekeeper an explicit, separately falsified claim and states the consequence for (a) in both the conservative and the leak case.

### Closed-world detector (owner of Algorithm 1's precondition)

Reachable-reflection / dynamic-dispatch-over-open-hierarchy detection is undecidable in a dynamically typed language. The implemented detector `CW-DETECT` is therefore a conservative over-approximation, and its **required soundness direction is one-sided**:

> **Claim CW (soundness direction).** `CW-DETECT` has a zero false-negative rate with respect to "this snapshot contains a reflection/dynamic construct that can reach analyzed code": if any such construct is reachable, `CW-DETECT` must report *not-closed-world* and route the snapshot to the degraded path. False positives (declaring not-closed-world when the code is in fact closed-world) are permitted and merely cost performance.

Consequence for (a), stated in both directions:

- **Sound-but-conservative case (the design target).** A zero-FN detector pushes *more* inputs onto the degraded path than a perfect oracle would. This does **not** threaten (a) — the degraded path is still deterministic for fixed `(S, Env)`; it threatens **(b)**, the economics. The honest consequence: the ≤15% open-world fallback target in Algorithm 1 is a target for `CW-DETECT`'s *combined* true-positive + false-positive rate, not for the true reflection rate. If `CW-DETECT` is sound but loose, the measured fallback rate rises and the unit economics degrade; that is an economics falsification with a defined response (tighten the over-approximation with a points-to pre-pass, or re-price), not a determinism failure.
- **Unsound-leak case (the dangerous one).** If `CW-DETECT` has a false negative, a precondition-violating snapshot is processed on the closed-world incremental path and ships labeled `origin=deterministic-core`. This falsifies (a) **and no existing test detects it**, because the canary re-run test re-runs the *same* (already-wrong) path and reproduces the same bytes. This is the gap the review identified. v3.2 closes it with a dedicated falsifier:

> **Falsifier CW.** Maintain a labeled reflection corpus (curated: Spring dynamic proxies, Python `__import__`/`getattr` dispatch, Ruby `send`/`method_missing`, PHP variable functions, Java `Class.forName`, plus mutation-generated reflection injected into otherwise-closed-world repos with ground-truth labels). `CW-DETECT`'s measured false-negative rate on this corpus must be exactly zero at each release; a single false negative is a release blocker. Additionally, a *differential oracle*: for every snapshot routed to the closed-world path, an independent, slower whole-program reflection scanner runs asynchronously off the critical path; any disagreement (closed-world path taken where the slow scanner finds reachable reflection) raises a determinism incident, retroactively re-partitions the affected findings to `oracle-passthrough`, and notifies affected customers. This converts an undetectable (a)-violation into a detected, bounded-latency one with a defined remediation. The residual risk is explicitly stated: between the fast decision and the async oracle, an affected finding may briefly carry the wrong label; the contract states this window and its SLA.

`CW-DETECT`'s soundness is therefore not assumed inside Phase 3; it is a tested, owned claim with its own corpus, its own zero-FN release gate, and a differential oracle that bounds the residual risk of the undecidable case.

### Non-distributive-spec rejector (owner of Algorithm 2's precondition) — and the item-2 restatement

Distributivity of a flow function is a semantic property, undecidable for an arbitrary function presented as code. The v3.1 phrase "validates each spec for distributivity at registration" overclaimed a decision of an undecidable property. The design is in fact sound for a different and correct reason, now stated:

> **Restatement (item 2).** Detector specs are not arbitrary code. They are declarative data in a fixed **combinator DSL** whose primitives — `source(access-path-pattern)`, `sink(...)`, `sanitize(...)`, `propagate(arg→ret | field)`, and their sanctioned compositions — are each distributive by construction, and the family is closed under the compositions the DSL permits. The registration check is therefore a **grammar/closure check**: it verifies that a submitted spec lies within the distributive-by-construction combinator DSL. It is *not* a decision procedure for distributivity of arbitrary functions, and the document no longer claims it is. The IFDS order-independence theorem's hypothesis is discharged because membership in the DSL is decidable and the DSL's image is provably within the distributive, finite-domain fragment.

Owner and falsifier: the DSL grammar and the per-combinator distributivity proofs live in `analysis/ifds/dsl/` with a machine-checked proof obligation per combinator (a property test that the combinator's transfer function satisfies `f(X ∪ Y) = f(X) ∪ f(Y)` on the finite fact domain, exhaustively for the bounded domain). Adding a combinator without its discharged proof obligation fails CI. Any escape hatch that would let a spec embed non-DSL code is rejected at registration, not analyzed.

## Algorithm 1 — Incremental CPG maintenance

**[CONDITIONAL THEOREM] Closed-world case.** *Precondition (now owned by `CW-DETECT`, Claim CW):* call resolution is CHA over a hierarchy closed under the analysis scope. *Then:* `AFFECTED = changed-decls ∪ reverse-symbol-closure(changed-decls) ∪ direct-callers(changed-signatures) ∪ CHA-cone(changed-types)`, and incremental re-evaluation visits `O(|AFFECTED| + frontier)` nodes with `frontier` the constant-bounded boundary summary-edge set; `O(Δ)` with `Δ = Σ|changed function| + |direct callers| + |CHA-cone of changed types|`.

**[EMPIRICAL] Open-world degradation.** On a `CW-DETECT` not-closed-world verdict: mark the dynamic edge conservatively imprecise (recorded in provenance), use an Andersen-style points-to-bounded cone, and fall back to full reparse when the bounded cone exceeds `θ_cone` (default 0.25) of the call graph or `|changed files|/|files| > θ_files` (default 0.4). The fallback-rate target ≤15% is a target for `CW-DETECT`'s combined TP+FP routing rate (per §Precondition soundness), not the true reflection rate.

**Falsifying tests.** Closed-world economics: on 1,000 real commits with the precondition asserted per commit, `time(Δ-rebuild) ≤ κ·(|AFFECTED|/|graph|)·time(full-rebuild)` for frozen `κ`. Open-world economics: measured median ≥ 5×, p95 ≥ 2× vs full reparse, fallback ≤ 15%, no asymptotic claim. Precondition soundness: Falsifier CW (zero FN on the reflection corpus + differential oracle), which is the test that protects (a), not (b).

## Algorithm 2 — Detection core as IFDS/IDE

**Model.** Each taint-style class is an IFDS instance with per-class flow functions drawn from the distributive-by-construction combinator DSL; quantitative classes (crypto key-size, race windows) use IDE with lattice-valued environment transformers over the same machinery.

**[CONDITIONAL THEOREM] Determinism of the solution.** *Precondition (owned by the DSL closure check, §Precondition soundness):* flow functions lie within the distributive, finite-domain combinator DSL. *Then:* Tabulation computes the unique meet-over-all-valid-paths solution independent of worklist order (RHS'95); the (sink-fact, realizing-path) set is a deterministic function of the exploded supergraph. Byte-identical serialization is supplied by Algorithm 5's enumeration order; together they license (a) on the core partition.

**Complexity.** `O(|E|·|D|³)` worst case; near-linear in program size on real taint **[EMPIRICAL; the cubic is the safe worst case]**. Incremental mode invalidates only `AFFECTED` summaries (Algorithm 1).

**Falsifying tests.** Determinism: 100 canary repos × 5 re-runs, identical pre-serialization solution hashes; one mismatch falsifies the precondition or reveals a DSL escape. Precision/recall: per class and **per language** (see §Phase staging), beat Semgrep-default by ≥10pp recall at equal precision on OWASP Benchmark + Juliet + held-out BigVul.

## Engine adapters and the determinism partition

Unchanged from v3.1. `origin = deterministic-core` carries (a); `origin = oracle-passthrough` carries a digest-backed attestation only, explicitly not the theorem. The Attestor runs two pipelines with separate pass criteria (core: byte-identical, hard fail on diff; oracle: digest-stability + measured reproduction rate). Contracts state the two guarantee levels separately. The differential-oracle mechanism in §Precondition soundness can retroactively move a finding from core to oracle if a closed-world false negative is detected; that transition is logged in provenance.

## Algorithm 3 — Refactor-stable finding fingerprint

Construction and per-refactor invariance proofs are unchanged from v3.1 (α-renaming for locals; PDG-only for formatting; canonical topological sort for independent reordering; **summary-inlining normalization** for extract/inline-method, proven for pure extract only; **FQN normalization** for file-move/package-rename). Ceiling and bounded fallback unchanged: 2-WL to fixpoint, then individualization-refinement under hard budget `(B, T)` (defaults 2¹⁶ search-tree nodes, 200 ms); on exhaustion, fall back to the `O(|witness|)`-capped witness-edge-sequence hash and flag `fingerprint_class = weak` (baseline never auto-suppresses a `weak` finding across a refactor). **[EMPIRICAL]** strong-success-within-budget ≥ 98%; degraded ~2% reported. Falsifier unchanged: per-refactor invariance holds; genuine fix / aliasing-changing extract flips it; published `weak`-rate above 5% triggers a canonicalizer redesign.

## Algorithm 4 — Detector scheduling (heuristic)

Unchanged from v3.1. `SNAP-SCHED-H` is a heuristic; ρ≈2 is cited only as the bound for the idealized independent-moldable relaxation used as a heuristic seed, explicitly not a guarantee for the actual moldable-DAG-with-setup problem. Sole promise: an **[EMPIRICAL]** p95 < 30 min at provisioned `m`, with a defined response on miss (re-fit work-estimate regression, raise `m`, or re-price). Result-independence of scheduling remains guaranteed via IFDS order-independence and is Attestor-cross-checked.

## Algorithm 5 — Canonical CPG ordering, and the item-4 provenance rename

Construction unchanged: seed labels `(kind, operator/literal, resolved FQN, sorted incident-edge-kind multiset)`; 2-WL to fixpoint; residual symmetric classes broken by enclosing-declaration canonical order then bounded individualization-refinement under the shared `(B, T)` budget; on exhaustion, a stable order keyed by `(declaration-hash, structural-path-from-declaration-root, edge-kind)` — total, deterministic, parse-order-independent, but **not a true canonical form**.

**Item-4 fix (labeling only; construction is correct as is).** The provenance field formerly named "canonical CPG hash" is renamed **`cpg_order_hash`** and is recorded with an explicit annotation: `canonical iff fingerprint_class = strong`. Same-source reproducibility (property (a)) holds for `cpg_order_hash` unconditionally; canonicality *across isomorphic-but-differently-written programs* holds only on the `strong` path, precisely the inputs the `weak` path exists for. The signed provenance record, the SARIF `properties`, and the auditor-facing export all carry the conditional annotation so the record states its own status rather than inviting an auditor to read "canonical" at face value. No behavioral change; the `weak` flag already absorbs the consequence.

## Algorithm 6 — Spec inference with an anytime-valid precision gate (item-3 design change)

**The defect being fixed.** v3.1 used a Lan–DeMets α-spending function while simultaneously promising indefinite re-evaluation as the corpus grows and customers arrive. A spending function requires a defined maximum information horizon against which the type-I budget is allocated; under unbounded looks the budget is consumed monotonically and exhausts in finite time, after which no spec can be accepted without breaching the contractual guarantee. This was the one claim that was incorrect for its stated usage, not merely overstated.

**The resolution: an e-process for the precision-floor null, shared by the acceptance gate and the drift monitor.** The required regime is "optional continuation, unbounded looks, fixed error guarantee" — exactly anytime-valid inference. For each candidate (or in-production) spec `σ` and detector class, define the null

```
H0(σ) :  true precision of σ on the evaluation stream  <  π₀.
```

Maintain an **e-process** `E_t(σ)` for `H0(σ)` — a nonnegative process with `E_0 = 1` and `E[E_τ | H0] ≤ 1` at every stopping time `τ` (Ville's inequality). Concretely use a betting confidence sequence for a bounded mean (Waudby-Smith & Ramdas 2024): each adjudicated finding contributing to `σ`'s precision estimate is a bounded `[0,1]` outcome; the e-process is the wealth of a betting strategy against `H0`. Decision rule, valid under unbounded optional continuation:

- **Acceptance.** `σ` enters `S` (as an `S_version`) only when `E_t(σ) ≥ 1/α` (equivalently, the time-uniform lower confidence bound on precision exceeds `π₀`). Because the e-process is anytime-valid, the family-wise / sequential concern disappears: the guarantee "`P(ever accept a σ with true precision < π₀) ≤ α`" holds **simultaneously for all looks and all specs** via a single union bound over an e-process per spec (a test martingale per spec, combined by averaging — itself an e-process). No information horizon is required; the budget is never "exhausted" because Ville's inequality is a uniform-in-time statement, not a spent allocation.
- **Continuous revalidation / drift.** The per-customer drift monitor is the *same instrument* run on the customer's adjudicated stream against the same `H0(σ)` with the customer's `π₀`. When the customer-stream e-process crosses the rejection threshold for the *complementary* null (precision has fallen below floor), `σ` is auto-quarantined for that customer. Acceptance gate and drift monitor now share one mathematical object; there is no inconsistency between a bounded-horizon acceptance test and an unbounded monitor because both are anytime-valid by construction.

**Multiplicity and selection.** Selecting the maximum-recall candidate across `N` specs is handled by maintaining one e-process per spec and combining by averaging (an e-process is closed under averaging), which controls the family-wise error over the *selected* spec without a Bonferroni horizon. The contract states the guarantee verbatim: *with probability at least 1−α, the accepted set `S` never, at any point in its unbounded evaluation history, contains a spec whose true precision on the evaluation stream is below π₀.* This is the corrected, and now consistent, restatement of the "monotone-precision artifact" claim.

**Covariate shift.** Unchanged from v3.1 and now mechanically coherent with the above: `S = S_global ∪ S_customer`. `S_global` passed the global-stream e-process; `S_customer` must additionally clear the customer-stream e-process before affecting that customer's findings; for a customer with no labeled sample, `S_global` specs apply but contributed findings are labeled `spec_provenance = global-unrevalidated`; the drift monitor (same e-process) auto-quarantines on a floor breach. Determinism (a) is unaffected because the applicable `S` partition and `S_version` are pinned per scan and recorded in provenance.

**Falsifier (revised for the anytime-valid instrument).** Stress batch: inject deliberately over-broad specs and run an *adversarial unbounded-continuation* schedule (the worst case for the old spending function); assert the realized ever-false-acceptance rate over many repeated campaigns ≤ α, with explicitly *no* finite horizon supplied. Covariate-shift replay: a global-accepted spec on an adversarial customer distribution must be quarantined by the shared e-process, and affected findings must have carried `global-unrevalidated` until revalidation. GA gate: the e-process implementation passes a martingale-property unit test (empirical `E[E_τ|H0]≤1` across simulated stopping times) before spec inference is enabled in production.

## Phase staging — the sequencing observation (per-language gating)

The native IFDS/IDE core over a uniform canonical CPG is the principal research-and-engineering deliverable, not substrate. Comparable mature systems are single-language and multi-year; per-language CPG fidelity will dominate the schedule and, if treated as simultaneous, will silently degrade Algorithm 2's recall claim on the weaker Joern front-ends (Go, Ruby, PHP) while the falsifier runs against a substrate that does not uniformly exist. No theorem changes; the phase plan does.

**Per-language launch gate.** A `(class, language)` pair is launchable only when it independently clears a **CPG-fidelity gate** *before* its Algorithm 2 precision/recall falsifier is considered meaningful:

> **CPG-fidelity gate.** For language `L`, on a curated fidelity corpus with ground-truth ASTs/CFGs/call-edges, the Joern (or proprietary) front-end for `L` must achieve: parse success ≥ 99.5% of files; call-edge precision/recall ≥ stated thresholds against the ground truth; PDG dependence-edge recall ≥ threshold. Only `(class, L)` pairs that pass enter the Algorithm 2 benchmark; pairs that fail are reported as **front-end-blocked**, not as recall failures, so the falsifier stays meaningful.

**Staged order (each stage leaves the system runnable and independently shippable):**

- **Stage A — Java + Python.** Strongest Joern front-ends; injection, path-traversal, ssrf, deserialization to core. Algorithm 2 falsifier is meaningful here first.
- **Stage B — JS/TS.** Add after the Stage-A core is determinism-attested; JS/TS front-end fidelity validated before the class falsifiers count.
- **Stage C — Go.** Front-end fidelity gate first; expect a points-to / interface-dispatch investment before the gate passes.
- **Stage D — Ruby, PHP.** Lowest front-end maturity; explicitly later, with the fidelity gate likely requiring proprietary front-end work. Until the gate passes, these languages ship **oracle-passthrough only** (Semgrep), clearly partitioned, with no core-determinism claim.
- **C/C++ (memory-safety)** remains oracle-passthrough (CodeQL) throughout v3; its port to core is tracked but not gated into v3.

The honest-labeling ledger now records per-language core readiness as **[STAGED]**, and customer contracts state which `(class, language)` pairs are core-partition vs oracle-passthrough at signing, revisited per stage.

## Per-algorithm summary (precondition / owner / degradation / falsifier)

| Alg | Guarantee | Precondition & its owner | Degradation | Falsifier |
|---|---|---|---|---|
| 1 | `O(Δ)` rebuild | CHA closed-world, owned by `CW-DETECT` (zero-FN claim CW) | Sound-loose → economics hit (not (a)); FN → detected by differential oracle, re-partitioned | κ-bound (closed); median/p95+fallback (open); **Falsifier CW** for soundness |
| 2 | Order-independent MVP solution | Distributive finite flow fns, owned by combinator-DSL closure check | DSL escape rejected at registration | 5× identical solution hash; ≥10pp recall per (class, language) |
| Adapters | Determinism partition | `origin=core` | Oracle → attestation only; differential oracle can re-partition | Core byte-identical hard fail; oracle digest-stability + rate |
| 3 | Refactor-stable fingerprint | Named normalizations; within `(B,T)` | `weak` witness-hash, conservative baseline, flagged | Per-refactor invariance; fix flips; weak-rate < 5% |
| 4 | p95 < 30 min | `m` from measured work distribution | Re-fit / raise `m` / re-price; no constant-factor claim | Production replay p95; schedule-invariance of core findings |
| 5 | Deterministic same-source order; `cpg_order_hash` canonical **iff strong** | Within `(B,T)` for true canonicality | Stable non-canonical order; (a) still holds; provenance self-annotates | CFI-graph termination within budget + stable same-source order |
| 6 | `S` precision ≥ π₀, anytime, w.p. ≥ 1−α | e-process / Ville (no horizon needed) | Auto-quarantine on floor-breach; `global-unrevalidated` labeling | Adversarial unbounded-continuation false-acceptance ≤ α; martingale unit test |

## Concrete refactor map (v2 phases preserved; v3.2 inserts the owners and staging)

**Phase 1 — Generalize SCM.** Unchanged: `integrations/scm/{base,github,gitlab,bitbucket,ado,_http}.py`; GitHub connector subsumes today's `integrations/github/github.py` (retry, tiered-star verbatim; `search_code()` Research-mode-only); `integrations/github/__init__.py` keeps `search_repositories` as a shim.

**Phase 2 — Detector catalog + combinator DSL + closure check.** `detectors/registry.py` loads `manifest.yaml`; `analysis/ifds/dsl/` holds the distributive-by-construction combinator family with a machine-checked distributivity proof obligation per combinator (CI-enforced). Registration runs the **grammar/closure check** (item 2), not a distributivity decision procedure. Manifest records `engine`, `cwes`, `specs/`, derived `determinism_partition`, and per-language readiness. `tarslip.yaml` → `detectors/path-traversal/specs/`; CodeQL queries → `detectors/memory-safety/codeql/` tagged `oracle`.

**Phase 3 — Snapshotter + `CW-DETECT` + differential oracle.** `services/snapshot/api.py`; `analysis/cpg_delta.py` (Algorithm 1). `CW-DETECT` is a named module with its own reflection corpus and zero-FN release gate (Falsifier CW). The asynchronous whole-program reflection scanner runs off the critical path; disagreements raise a determinism incident and trigger re-partitioning. Provenance records the closed-world / degraded / full-reparse status and any retroactive re-partition. `Env` pinned by image digest.

**Phase 4 — Orchestrator + heuristic scheduler.** `services/scan/api.py` (HMAC-bearer callback as in v2); `services/scan/scheduler.py` = `SNAP-SCHED-H`. `tools/scan/worker/worker.py` loads the CPG once, runs IFDS for core classes / oracle adapters otherwise, stamps `origin` and `determinism_partition`.

**Phase 5 — Normalizer.** `services/scan/findings.py`: strong slice fingerprint with `(B,T)` canonicalizer, flagged `weak` fallback, SARIF in CPG-CANON order. `findings` gains `slice_fingerprint`, `fingerprint_class`, `origin`, `determinism_partition`, `witness_blob_uri`, `S_version`, `env_digest`, and `cpg_order_hash` (with the canonical-iff-strong annotation).

**Phase 6 — Multi-tenant control plane.** Tables `orgs`, `projects`, `codebases`, `scm_credentials` (encrypted), `org_policies`, `memberships`; OIDC/SAML; dashboard tree with per-finding `origin`, `S_version`, `env_digest`, and the conditional-canonicality annotation surfaced in the auditor export.

**Phase 7 — Triage + spec inference with the e-process gate.** `services/triage/spec_inference.py` implements the e-process acceptance gate and the shared drift-monitor instrument, the `S_global`/`S_customer` partition, per-customer revalidation, and the martingale-property GA unit test. Feature-flagged; default off.

**Phase 8 — Research mode reattached.** `services/research/api.py` feeds synthetic codebases into the same pool; labeled CVE findings feed the e-process evaluation stream (covariate-shift handling explicit).

**Phase 9 — Determinism Attestor, partitioned.** Core pipeline asserts byte-identical SARIF over the core partition (hard fail); oracle pipeline reports measured reproduction rate; signed provenance record carries `cpg_order_hash` with its conditional annotation and any differential-oracle re-partition events. CI runs both on the canary corpus per detector/engine/`Env` change.

**Per-language staging overlay.** Phases 2–9 are executed per the Stage A→D order; a `(class, language)` pair is benchmarked under Algorithm 2 only after it clears the CPG-fidelity gate. Front-end-blocked pairs ship oracle-passthrough.

## Verification (each target tied to the corrected claim it tests)

- **Core-partition reproducibility [(a)].** 100 canary repos × 3 SCMs × 5 re-runs, fixed `(S_version, env_digest)`, `LLM_TRIAGE=off`: byte-identical SARIF over `origin=deterministic-core`. Oracle partition: digest-stability + measured rate. Core diff = hard CI fail.
- **Precondition soundness [hypotheses of (a) and 1].** Falsifier CW: zero false negatives on the reflection corpus at every release; differential-oracle disagreement rate measured and bounded with a stated SLA on the labeling window. DSL closure: every combinator carries a discharged distributivity proof obligation; a non-DSL spec is rejected, never analyzed.
- **Incrementality [Algorithm 1].** Closed-world κ-bound; open-world median ≥ 5×, p95 ≥ 2×, fallback ≤ 15% (a `CW-DETECT` combined-routing-rate target, stated as such).
- **Class coverage [Algorithm 2], per (class, language).** ≥10pp recall over Semgrep-default at equal precision, evaluated only on CPG-fidelity-gate-passing pairs; front-end-blocked pairs reported separately.
- **Refactor stability [Algorithm 3].** Named-refactor invariance; fix/aliasing-change flips it; `weak`-rate < 5% reported.
- **Scheduling [Algorithm 4].** Production-shaped replay p95 < 30 min at provisioned `m`; schedule-invariance of core findings.
- **Canonicalization ceiling [Algorithm 5].** CFI-style inputs terminate within `(B,T)` with stable same-source order; budget-exhaustion < 1% reported; auditor export shows the canonical-iff-strong annotation.
- **Spec-gate safety [Algorithm 6].** Adversarial unbounded-continuation campaigns: realized ever-false-acceptance ≤ α with no horizon supplied; covariate-shift quarantine fires; e-process martingale unit test passes before GA.
- **End-to-end / multi-SCM / backwards-compat.** SSO → GitHub App → webhook → finding-with-witness < 10 min for 100k LOC; identical *strong* fingerprints across GitHub/GitLab/Bitbucket/ADO (a `weak` on any SCM is reported); `scanipy --query extractall --run-semgrep` still finds CVE-2025-61765 (IFDS witness, slice-fingerprinted, `origin=core`, Stage-A language).

## Honest-labeling ledger (proven / measured / not claimed / staged)

- **Proven, conditional — with a named owner for each hypothesis:** Algorithm 2 solution order-independence (combinator-DSL closure check owns the precondition). Algorithm 1 `O(Δ)` (`CW-DETECT` owns the closed-world precondition; soundness direction separately falsified by Falsifier CW). Algorithm 3 per-refactor invariance (named normalization passes). Property (a) (fixed `S`, `Env`; core partition; precondition soundness owned and tested, residual undecidable-case risk bounded by the differential oracle with a stated SLA).
- **Proven, unconditional:** provenance construction (c); same-source determinism of Algorithm 5's fallback order and of `cpg_order_hash`; bounded time caps of the Algorithm 3/5 fallbacks; anytime validity of the Algorithm 6 e-process (Ville's inequality), no information horizon required.
- **Empirical, labeled:** open-world incremental speedup; near-linear IFDS cost on real code; `weak`-fallback rarity (<5%); canonicalizer budget-exhaustion rarity (<1%); scheduler p95; oracle-partition reproduction rate; `CW-DETECT` combined routing rate (≤15% target).
- **Staged, not simultaneous:** per-language core readiness (Stage A→D); Algorithm 2's recall claim is meaningful only on CPG-fidelity-gate-passing `(class, language)` pairs; Ruby/PHP/Go ship oracle-passthrough until their front-end gate passes; C/C++ memory-safety stays oracle-passthrough through v3.
- **Explicitly not claimed:** environment-independent determinism; the LLM being outside `F` (it is inside, via versioned `S`); a constant-factor scheduling guarantee for the real DAG+setup problem; canonicality for CFI-hard graphs or on the `weak` path; spec precision on un-revalidated customer distributions; a decision procedure for distributivity or for reachable reflection (both are conservatively over-approximated, with the soundness direction owned and the residual risk bounded and disclosed).

## Out of scope for v3 (unchanged)

CI-agent / on-prem runner, container-image scanning, binary-only analysis, IDE plugin. Revisit post-v3 once the catalog, the partitioned attestation, and the Stage A→D core are mature.
