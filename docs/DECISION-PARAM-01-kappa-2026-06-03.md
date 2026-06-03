# Decision Record — `κ` (and `π₀`): the Algorithm-1 regression threshold

**ID:** `DECISION-PARAM-01` · **Prepared:** 2026-06-03 · **Author:** Theory/architecture analysis pass
**Resolves (the engineering question behind):** `CLAR-PARAM-01` (κ portion) and, secondarily, `CLAR-PARAM-02` (π₀)
**Realizes:** `docs/OPEN-DECISIONS-2026-06-02.md` **Part 1** — option **(b)** ("an explicit decision
that κ is calibrated empirically during a named phase, with an interim value for development").
**Status:** **PROPOSED — awaiting Architect + CTO ratification.** This memo edits **no** source-of-truth
file. It does **not** flip any `CLAR-*` status, does **not** touch `PLAN.md`/`SDD.md`/`WBS.md`, and writes
**no** production code. It is a decision *record* for humans to ratify, per the constraint that "nothing
[in Part 1] can be decided by an automated agent."

> **One-paragraph summary.** κ is the regression ceiling in `time(Δ-rebuild) ≤ κ·(|AFFECTED|/|graph|)·time(full-rebuild)`
> (AC-SNAP-02a) — the *only* κ in the spec. It governs **property (b) incremental economics**, never
> **(a) soundness**; it has **no runtime consumer** (it is a post-hoc timing-test pass-criterion only).
> That makes a clearly-labeled *interim* value RULE-4-safe. **But** the headline finding is not a number:
> as `time(Δ-rebuild)` is currently defined and implemented, it carries an **O(|graph|) serialization
> floor**, so the per-commit ratio `ρ` **diverges on small commits** and **no single frozen scalar κ is
> well-posed** under the verbatim per-commit zero-tolerance gate. The decision this memo asks the Architect
> to make is therefore *how to make the metric well-posed* (three options, §4) — after which κ is
> **empirically calibrated in Phase 5 and pinned per-language at Stage-A go-live**, with a mechanically
> separated interim dev value (`κ = 50`, inert) that **never** feeds the (still-xfail) hard gate.
>
> **The cork actually comes out of the bottle without pinning κ (D-7).** κ has *no runtime consumer* and
> gates only a post-hoc *economics* test. The core chain depends on SNAP-02 for **correctness** artifacts —
> `G'`, `AFFECTED`, node-ID preservation (`AC-SNAP-02c`, **green today**) — not for κ. So `CMP-CORE-01`
> development can start **now** on a correct SNAP-02, with `AC-SNAP-02a` carried as a Stage-A-go-live
> *economics* gate rather than a dependency-DAG DONE-blocker. This is the governance unblock the project
> memory points at ("κ blocks the core chain — a governance action, not code"); it is a **CTO** ruling.

---

## 0. The ruling (what we are deciding)

| # | Decision | Owner to ratify |
|---|---|---|
| **D-1** | κ governs property **(b)** economics, not **(a)** soundness; it has **no runtime consumer**. An explicitly-labeled *interim* κ is therefore RULE-4-safe (it cannot weaken a soundness threshold). | Architect (classification) |
| **D-2** | There is **exactly one** κ — the `CMP-SNAP-02` CPG-rebuild bound (AC-SNAP-02a). No second κ exists at `CMP-CORE-01` (AC-CORE-01c is a *correctness* property, no timing bound). Disambiguate from the unrelated `_BET_KAPPA` in `CMP-TRI-02`. | Architect |
| **D-3** | **Well-posedness gate (the real blocker).** Before any κ can be certified, choose how to remove the O(\|graph\|) serialization floor from the measured `time(Δ-rebuild)`: **(A)** normalize/exclude it (delta-only / copy-on-write persistence) — *recommended*; **(B)** promote **`CLAR-PARAM-04`** (affine `+C₀` term — *more faithful to PLAN.md's own `O(\|AFFECTED\| + frontier)`*); **(C)** an architect-ratified corpus/`|AFFECTED|` floor that explicitly narrows the AC's scope. | **Architect / CTO** |
| **D-4** | κ is **empirically calibrated in Phase 5** and **certified per-language at Stage-A go-live** (per CLAR-PARAM-01). Certified statistic = **MAX of ρ over the floored corpus × safety margin** (not p99 — must match the per-commit zero-tolerance gate). Require a **positive-power + negative-control** check before flipping the gate to hard. | CTO (go-live pin) |
| **D-5** | The **per-detector registry read** stays verbatim as the mechanism (CLAR-PARAM-01); the language-driven value is an **observation that populates** each Stage-A core detector's entry. Collapsing to a single global κ field is **out of scope** and would itself need a CLAR. | Architect |
| **D-6** | **Interim dev κ is mechanically separated:** the hard gate `TST-AC-SNAP-02a` **stays xfail/skip** with its existing `PASS-CRITERION-UNSPECIFIED…needs CLAR` sentinel until the certified κ is pinned; the interim value is consumed only by the non-gating dev/build path; the harness **fail-closes** if asked to certify against an interim-tagged value. | Architect |
| **D-7** | **Highest-leverage unblock:** because κ has no runtime consumer and gates only a post-hoc *economics* test, the core chain's *correctness* dependency on SNAP-02 (G′, AFFECTED, node-ID preservation — AC-SNAP-02c green) can unblock `CMP-CORE-01` development now, with AC-SNAP-02a carried as a **Stage-A-go-live economics gate**, not a DAG DONE-blocker. | CTO |
| **D-8** | **π₀ (CLAR-PARAM-02)** is co-scheduled but *not* analogous to κ: interim **0.80** (per-class table in §8), **config-driven never hardcoded**, α=0.05 fixed. Real blockers are the **per-class certified values** *and* the **per-class evaluation-stream definition (pin first)**. Interim π₀ is safe (the martingale holds for any π₀ — Gate-4 tests are already green). | Security + Architect (Phase 5) |

---

## 1. What κ is — a precise definition

The **only** κ in the entire specification is the proportionality ceiling in `AC-SNAP-02a`
(`SDD.md:107`, verbatim; mirrored `PLAN.md:74`, `DOC-CMP-SNAP-02 §9`, `DOC-ALGS §2.8`):

> **[CONDITIONAL THEOREM test]** On a closed-world corpus with the precondition asserted **per commit**,
> `time(Δ-rebuild) ≤ κ · (|AFFECTED|/|graph|) · time(full-rebuild)` for a frozen `κ`; a regression above
> `κ` fails.

Define the **per-commit incremental-overhead ratio**

```
ρ_commit  =  time(Δ-rebuild)  /  [ (|AFFECTED| / |graph|) · time(full-rebuild) ]
```

κ is the accepted ceiling on `ρ`. Two equivalent readings make κ interpretable:

- **Multiplicative shortfall from the optimum.** Demers–Reps–Teitelbaum (POPL 1981; cited `PLAN.md:37`)
  establishes the incremental optimum: re-evaluate exactly the `AFFECTED` set, cost `O(|AFFECTED|)`. If
  the rebuild scaled perfectly with the affected fraction, `ρ = 1` (κ = 1). **κ is how many × above the
  DRT'81 optimum we tolerate `ρ` sitting.**
- **Speedup floor.** With `speedup = time(full)/time(Δ)` and ideal-linear speedup `= |graph|/|AFFECTED| = 1/f`
  (f = affected fraction), the bound is exactly `speedup ≥ (1/f)/κ`. **κ = how many × below ideal-linear
  scaling is acceptable before we call it a regression.**

Algebraically, under the *theorem's own* cost model `time(Δ) = O(|AFFECTED| + frontier)`:

```
ρ  ≈  (c_inc / c_full) · ( 1 + frontier / |AFFECTED| )
```

— a per-node incremental-vs-batch constant `c_inc/c_full` times a **frontier-amortization** term that
grows as `|AFFECTED|` shrinks. (`frontier` = the "constant-bounded boundary summary-edge set",
`PLAN.md:70`.)

**Units must be pinned.** `|graph|` = **node count** of the parent CPG (the implementation uses
`len(parent_cpg.nodes)`, `cpg_delta.py:309`; full-rebuild is costed `O(|G'|)` nodes, `DOC-ALGS §2.5`).
A CPG is a dense multigraph (AST∪CFG∪PDG∪call edges), so `|edges| ≈ d·|nodes|` with `d ≫ 1`; counting
`|AFFECTED|` in nodes but `|graph|` in edges (or vice-versa) would silently rescale κ by the average
degree `d` and make it unportable across languages. **The calibration record and the registry entry must
state "node count of the parent CPG" explicitly.**

---

## 2. The load-bearing classification: κ is property (b), not (a)

This is what makes an interim value safe, and it **corrects a misframing in the OPEN-DECISIONS doc**
(which worried that guessing κ "could silently weaken a soundness threshold"). It cannot.

**κ governs property (b) — incremental economics — only.** `PLAN.md:74` separates the two cleanly:
the κ-bound is "closed-world **economics**"; soundness (property (a), reproducibility) is protected by a
*different* test — "**Falsifier CW** (zero FN …), which is the test that protects (a), not (b)." The
`[CONDITIONAL THEOREM]` label denotes conditionality on the **CHA closed-world precondition** for the
`O(Δ)` **complexity** claim — it is **not** a soundness theorem. (`PLAN.md:147, :181` repeat the split;
the (a) determinism theorem lives on Algorithms 2/5, `DOC-ALGS §3.4`.)

We discharge the lens **structurally**, not by citation:

1. **κ has no runtime consumer.** `grep` of `analysis/cpg_delta.py` shows κ appears *only* in the module
   docstring (lines 17–18). `compute_incremental_cpg` / `_route_for` branch on `cw_verdict`,
   `theta_cone`, `theta_files` — **never κ**. A wrong κ can flip exactly one bit: whether the post-hoc
   `TST-AC-SNAP-02a` timing test passes. It cannot change which `G'` is built, which findings emit,
   `slice_fingerprint`, or `origin`.
2. **Property (a) is protected by κ-independent gates** — `CMP-CP-05` byte-identical core SARIF, Falsifier
   CW zero-FN, and the differential-oracle re-partition (`PLAN.md:74,147,181`; `.claude/rules/05-determinism.md`).
   A slow O(|graph|) re-serialization is **slow, not non-deterministic** — it emits byte-identical output.

**Consequence.** A too-loose κ → a real economic regression slips the nightly gate (backstopped by
AC-SNAP-02b and production latency SLOs). A too-tight κ → nightly-gate flake / over-eager fallback (a
measured, reversible cost). **Neither touches (a).** An explicitly-labeled interim κ is RULE-4-safe.

---

## 3. The well-posedness problem — the real finding

A naïve answer ("interim κ ≈ 20–50, certified = p99 × margin") is **ill-posed**, and the reason is
structural, not a tuning detail.

**`time(Δ-rebuild)` carries an O(|graph|) materialization + serialization floor.** Verified in
`analysis/cpg_delta.py`: the closed-world path `_build_preserving_new_cpg` loops over **every** parent
node (line 344, carrying each not-AFFECTED node into a fresh `IncrementalCpg`) and **every** parent edge
(line 353), then diffs the whole graph for `ΔG` (lines 382–384); persisted **output artifact #1 is "CPG
tarball — the new G'"** (`DOC-CMP-SNAP-02 §4.2`), a full serialization. All are `O(|graph|)`, independent
of how few decls changed.

In the serialization-dominated regime, `time(Δ) → c_serialize·|graph|`, so

```
ρ  →  (c_serialize · |graph|) / [ (|AFFECTED|/|graph|) · c_full · |graph| ]
    =  (1/f) · (c_serialize / c_full)
```

which **diverges as `f = |AFFECTED|/|graph| → 0`**. Worked (illustrative, `c_serialize/c_full = 0.1`):
`f = 1%` → ρ ≈ 10; `f = 0.1%` → ρ ≈ 100; a one-function commit (`|AFFECTED| ≈ 30` nodes) on a
`|graph| = 2¹⁶` CPG → `f ≈ 4.6e-4` → **ρ ≈ 218**; a one-line commit on a 1M-node graph → **ρ ≈ tens of
thousands**. Because `TST-AC-SNAP-02a` is **per-commit zero-tolerance** ("any commit above κ fails",
`tests/unit/test_snap_specs.py:188-189`; per-commit over ≥1000 commits, `PLAN.md:74`, `WBS.md:363`), the
gate reads off this **divergent small-commit tail**. Therefore:

> **No single frozen scalar κ is simultaneously (i) flake-free on the small-commit population and
> (ii) sensitive to a real regression on bulk commits.** A κ loose enough to clear the tail (hundreds–
> thousands) lets a 10× Δ-rebuild regression on a bulk commit pass silently — defeating the gate's
> entire purpose.

**Two honesty caveats on this finding:**

- It is **analytic-from-definition, not measured.** `c_serialize/c_full` is unknown here: the serializer
  lives in `CMP-SNAP-05` and the reparser is an injected collaborator (`cpg_delta.py:22-27`). The worked
  magnitudes are consequences of the *stated* `time(Δ)` definition, **not** benchmarks. **Sizing
  `c_serialize/c_full` is a named Phase-5 deliverable.**
- The already-fixed fallback constants do **not** rescue this. `θ_files=0.4` / `θ_cone=0.25` fire on
  **large-f** commits and route them to full reparse — they strip the *low-ρ* population and **leave** the
  high-ρ small-commit tail. `B=2¹⁶ / T=200ms` are canonicalization/time budgets, not ratio bounds. The
  binding constraint is the *smallest kept commit*, which the fallback never touches.

---

## 4. The gating decision (Architect / CTO): make the metric well-posed

κ cannot be pinned against an artifact. Choose **one** (they compose):

### Option A — Normalize the O(|graph|) term out of measured `time(Δ)` *(recommended)*
Measure `time(Δ-rebuild)` as the **incremental graph-computation** the theorem actually bounds (reparse
of AFFECTED + delta assembly), **excluding** the full-G′ re-serialization — and/or fix persistence to
**delta-only / copy-on-write** (persist `ΔG` + a base-pointer, reconstruct `G′` lazily) so the per-commit
write is genuinely `O(Δ)`. This removes the floor at its source: the floor is an artifact of full-G′
persistence, **not** of Algorithm 1's incremental work. **Touches the persistence design / measurement
harness, not the verbatim AC.** *Recommended* because it restores the `O(Δ)` economics claim the PLAN
actually makes and leaves κ governing the genuine per-node overhead.

### Option B — Promote `CLAR-PARAM-04`: an affine `+C₀` term *(most faithful to the PLAN)*
Change the bound to `time(Δ) ≤ κ·(|AFFECTED|/|graph|)·time(full) + C₀`, where `C₀` is a fixed
(per-language, per-Env) additive budget absorbing the constant frontier + serialization floor. As
`|AFFECTED|→0` the RHS → `C₀` (finite) instead of → 0, so κ governs only the **slope** (per-node
overhead). **This is strictly more faithful to `PLAN.md:70`**, which states incremental re-evaluation
visits `O(|AFFECTED| + frontier)` — the additive `+ frontier` term is exactly `C₀`; the pure-multiplicative
AC-SNAP-02a *dropped* it. **This edits the verbatim AC formula → it is architect-only and must be filed as
`CLAR-PARAM-04` (proposed text in §11). An agent may not apply it.**

### Option C — Architect-ratified corpus / `|AFFECTED|` floor *(narrows coverage; be explicit)*
Define the closed-world calibration corpus **and the population `TST-AC-SNAP-02a` enforces over** to
exclude trivially-tiny commits (e.g. `time(full) < T = 200 ms` **or** `f < f_min`), **or** route sub-floor
commits to full-reparse at runtime (so Algorithm 1 isn't invoked and there is no Δ-rebuild time to bound;
recorded as `precondition_status`). **Caveat (do not under-state):** flooring only the *calibration*
corpus is insufficient — if the gate still runs per-commit over all commits it flakes on exactly the
excluded ones. The floor must bind **enforcement**, which **narrows the AC's guarantee** to above-floor
commits — a coverage change that is an **architect decision, not a calibration footnote** (RULE-4: stated,
not silent).

**Recommendation:** **A** as the primary fix (delta-only persistence + measure the incremental term),
with **C** (runtime-routing of sub-`T` commits to full-reparse) as the clean, already-implementable
companion — sub-200ms full rebuilds have nothing to amortize anyway. **B / `CLAR-PARAM-04`** is the
correct structural fix to *consider at ratification* if the architect prefers to keep full-G′ persistence;
the well-posedness analysis means it should be decided **this cycle**, not left open-ended.

---

## 5. The decision on κ proper

- **One κ, per-detector mechanism preserved (SoT fence).** CLAR-PARAM-01 (RESOLVED) says κ is "TBD **by the
  detector at registration**", read "from the registry" (`WBS.md:924`, `DOC-CMP-SNAP-02 §10`). The
  `Detector` registry row (`detectors/registry.py:110-133`) carries **no `kappa` field today** —
  consistent with "TBD". **Keep the per-detector read verbatim.** *Observation only:* because AC-SNAP-02a's
  `AFFECTED/|graph|/time(Δ)/time(full)` are CPG-structural and the bound is **CPG-maintenance-only**
  (it excludes downstream IFDS re-tabulation — that is `CMP-CORE-01`), the rebuild-portion value is driven
  by the **language front-end** (Joern reparse cost, CPG density) and will **coincide across the four
  Stage-A core detector classes of a given language**. The registry just keys it per detector for the read
  mechanism (`per_language_readiness`, line 131, is the natural template). **Collapsing to a single global
  κ field is out of scope here and would itself require a CLAR amending CLAR-PARAM-01 + the DET-02 shape.**
- **Empirically calibrated, certified at Stage-A go-live.** κ is the empirical statistic of the measured
  ρ distribution from the Phase-5 baseline (§10), per Stage-A language (Java, Python — their front-end
  fidelities differ, so their ρ distributions differ). Pinned at Stage-A go-live per CLAR-PARAM-01.
- **Certified statistic = MAX, not p99.** Because the gate is per-commit zero-tolerance (= MAX/p100), a
  `p99 × margin` rule is internally inconsistent (p99 < max by construction → it either re-loosens κ by
  the p99→max factor, i.e. self-masks, or the gate fails ~1% of its own calibration corpus). Use
  `κ_L = ⌈MAX(ρ over the floored corpus for language L)⌉ × safety_margin` (equivalently
  `max(⌈p99⌉×margin, ⌈p100⌉)`), so the protocol emits a κ its own per-commit gate cannot reject.
  `safety_margin` (start ≥ 1.5) provides headroom for unseen commits and drift.
- **Power before hard.** Before flipping `TST-AC-SNAP-02a` from xfail to a hard gate, require (per the
  team memory *falsifier-gates-need-math-review*): a **positive-power** check (a deliberately-regressed
  Δ-rebuild, e.g. `2·κ_L`, **must** trip the gate) and a **negative control** (an unchanged impl must not
  flap across re-runs / noise). A green `TST-AC-SNAP-02a` on a loose κ otherwise passes a broken impl.

---

## 6. The interim development value — mechanically separated

The interim value's *only* job is anti-flakiness for the **dev/build path** — it is a **smoke gate**
(does the bench harness run and produce a finite ρ?), **not** a regression gate. RULE-4 safety requires
the separation to be **mechanical, not a label**:

1. **The hard gate stays xfail.** `TST-AC-SNAP-02a` (`Hard gate?: yes`) keeps its existing
   `PASS-CRITERION-UNSPECIFIED … needs CLAR` skip sentinel (`tests/unit/test_snap_specs.py:169-207`)
   until the **certified** per-language κ_L is pinned at Stage-A go-live. The interim κ is **never**
   imported into this test's pass-criterion.
2. **Interim κ is consumed only by the non-gating dev/build path** — the path that lets the SNAP-02 bench
   harness and the `SNAP-02→CORE-01` integration be exercised end-to-end. Constant name
   `KAPPA_INTERIM_DEV` (never `KAPPA_FROZEN`), config-driven (read from the registry/config, never
   hardcoded into the bound), tagged `INTERIM-DEV · NON-CERTIFIED · carries NO (b)-economics or
   (a)-soundness claim`, with a pointer to this open item.
3. **Harness fail-closes.** The certified gate harness reads the certified-vs-interim provenance field and
   **refuses to run** (fail-closed) if asked to certify against an interim-tagged value.

**Interim dev `κ = 50` — usable today, because it is inert.** The well-posedness divergence (§3) is a
property of the **certified** per-commit zero-tolerance *gate*; it does **not** block a value that gates
nothing. Since the hard gate stays xfail and the interim has no runtime consumer, the interim's only job
is to let the dev smoke-check produce a *finite* ρ. So set `KAPPA_INTERIM_DEV = 50` now — a loose ceiling
~2.5× above the AC-SNAP-02b median-ρ ≈ 20 sanity point, config-driven, `INTERIM-DEV`, never imported into
the gate's pass-criterion. The dev smoke-check runs on a floored corpus *or* on serialization-normalized
`time(Δ)` — either trivially yields a finite ρ; that measurement choice is a dev-harness detail, **not** a
precondition for naming the number.

What **is** contingent on the §4 well-posedness fix is the **certified** value (and the dev measurement
basis), **not** the interim number. Once §4 removes the serialization floor, the certified residual is the
bounded frontier floor (`ρ ≈ 2–3`), so the *certified* `κ_L` lands far below 50 (≈ 10–15 with margin) —
which is *why* 50 is a safe, loose interim that cannot accidentally read as a tight certified threshold.
(The cross-stream spread — literature ~10–20, this ~50 interim, a refuted ~20–25 *certified* proposal — is
the signal that the *certified* value is not derivable until §4 is settled; the *interim* value is not so
constrained, precisely because it is inert.)

**Highest-leverage unblock (D-7).** κ blocks only the *economics* certification of SNAP-02, not its
*correctness*. The core chain's dependency on SNAP-02 is for `G'`, `AFFECTED`, and node-ID preservation
(`AC-SNAP-02c` — **green today**). The cleanest "cork-out-of-the-bottle" move is therefore a CTO ruling
that **AC-SNAP-02a is a Stage-A-go-live economics gate, decoupled from the DAG DONE-blocker for
`CMP-CORE-01` development** — letting CORE-01 proceed against a correct SNAP-02 while the conditional-
theorem economics gate stays honestly uncertified (xfail) until go-live. This matches CLAR-PARAM-01's own
"pinned at Stage-A go-live" and the project memory that κ is "a governance action, not code."

---

## 7. AC-SNAP-02b cross-check — a sanity floor only

`AC-SNAP-02b` (open-world: median speedup ≥ 5×, p95 ≥ 2×, fallback ≤ 15%) is a **different corpus**
(open-world) and a **different statistic** (distributional, not per-commit-max) from the κ test. Using
`ρ = (1/f)/speedup` with an assumed `f_median ≈ 1%` gives `ρ_median ≈ 20` — a **loose order-of-magnitude
sanity floor** any sane κ must clear, **not** a derivation of κ. Critically, 02b binds the **opposite tail**
(large-commit / low-ρ) from the one κ is set by (small-commit / high-ρ), and a small-commit-tail regression
can degrade p95 speedup from ~10× to ~2.5× and **still clear** 02b. **So 02b is not a backstop in the
regime where the certified κ is weakest** — κ needs its own closed-world Phase-5 calibration.

---

## 8. π₀ (`CLAR-PARAM-02`) — co-scheduled, but *not* analogous to κ

π₀ is the per-detector-class **precision floor** in the spec-acceptance e-process gate
`H0(σ): true precision < π₀` (accept when `E_t(σ) ≥ 1/α`, α = 0.05 fixed; `CMP-TRI-02`, Algorithm 6). It is
**DEFERRED** to a Phase-5 empirical baseline and is **lower-leverage** than κ (it does not gate the core
chain). It must **not** be treated by copying κ's logic — the structure is different:

- **Interim π₀ is safe and does *not* vacate its gate (opposite of κ).** The Gate-4 e-process tests are
  **live and green** with a placeholder π₀ (`tests/falsifier/eprocess/test_tri02_eprocess.py` — xfail/skip
  stubs removed, real martingale test `02b`, positive-power test driving true-precision 0.95 ≫ π₀, and a
  peek-bet negative control). The **martingale property holds for any configured π₀**, so an interim
  π₀ = 0.80 exercises the plumbing without vacating anything — unlike a leaked interim κ, which *would*
  vacuously pass its hard gate.
- **Config-driven, never hardcoded — a hard contract.** `DOC-CMP-TRI-02 §10` and the data model
  (`CandidateSpec.pi_zero`, `DOC-CMP-TRI-02 §3 L81`; `spec_inference.py:83` "never hardcoded") require π₀
  wired from config. A hardcoded π₀ would also **corrupt the signed audit chain**, which persists the
  actual `{e_value, threshold, π₀, α}` used. α = 0.05 may be inlined as a default (still overridable);
  **π₀ has no sanctioned default value** — it is DEFERRED.
- **The two real blockers (name them):** **(i)** the certified per-class values (Phase 5); **(ii)** the
  **per-class evaluation-stream definition** — an unpinned sub-part of CLAR-PARAM-02 that decides which
  adjudicated findings feed which σ, and which **must be pinned first** (currently omitted from the
  register's framing).
- **A too-low certified π₀ is "sticky" — quality-shaping, not self-correcting.** Unlike κ (a reversible,
  self-checking economics knob), a too-low π₀ admits a low-precision inferred spec into `S`; once pinned as
  an `S_version` it is consumed by later scans and **shapes the deterministic-core FindingSet**, unwound
  only by per-customer quarantine (`CMP-TRI-03`), not a test re-run. *Precision:* this does **not violate
  INV-3** — the e-process gate *is* the sanctioned channel; π₀ only sets its stringency. (A too-*high* π₀
  is a safe failure: the gate admits nothing.) This two-sidedness is exactly why the certified value must
  be empirically calibrated, never invented.

**Interim π₀ recommendation (development/CI plumbing only, config-overridable, `INTERIM-UNCERTIFIED`):**

| Detector class | Tier rationale | Interim π₀ |
|---|---|---|
| injection | best-behaved taint (source→sink directly modelled) | **0.85** |
| path-traversal | taint-tractable, slightly noisier sinks | **0.85** |
| deserialization | gadget-chain reachability FPs | **0.82** |
| ssrf | validation/allow-list logic FPs | **0.80** |
| crypto-misuse *(IFDS portion only)* | bimodal; collapses in test/non-security code | **0.70** |
| authn-authz *(IFDS portion only)* | noisiest; access-control is semantic/codebase-dependent | **0.65** |
| **uniform fallback** | when a per-class config entry is absent | **0.80** |

Always-oracle classes (`secrets`, `dep-cve`, the pattern portions of crypto/authn, C/C++ memory-safety)
get **no π₀** — they never pass through this gate. The lower floors for crypto/authn are deliberate: a
floor set *above* achievable precision walls the gate (admits nothing).

---

## 9. Name disambiguation — two unrelated constants called "kappa"

| Symbol | Component | Meaning | Where |
|---|---|---|---|
| **κ** (this memo) | `CMP-SNAP-02`, Algorithm 1 | per-commit CPG-rebuild **economics** regression ceiling | `AC-SNAP-02a` (no code constant yet) |
| **`_BET_KAPPA = 2.0`** | `CMP-TRI-02`, Algorithm 6 | e-process **betting-fraction aggressiveness gain** in `λ_t = clip(κ·(μ̂−π₀), 0, c/π₀)` | `services/triage/spec_inference.py:73` |

The "single-κ" claim (D-2) is scoped to the `CMP-SNAP-02` CPG-rebuild bound only. The TRI-02 `_BET_KAPPA`
is a different quantity and must not be conflated in the audit chain or by readers.

---

## 10. Phase-5 calibration protocol (the named phase)

**κ (per Stage-A language, stored per-detector in the registry):**
1. **Corpus.** Per language (Java, Python), ≥1000 **closed-world** commits (CW-DETECT verdict =
   closed-world or sound-degraded; precondition asserted per commit — matching AC-SNAP-02a's population).
2. **Floor (Option C companion).** Apply the ratified floor (`time(full) < T=200ms` or `f < f_min`).
   `f_min` is set *in-protocol* at the measured point where the serialization floor `(1/f)·(c_serialize/c_full)`
   begins to dominate (i.e. where ρ stops being slope-driven). **Record how many commits were floored and
   why** (honest-labeling). The floored corpus is *both* the fit population *and* the enforcement population.
3. **Measure** (pinned worker image / fixed `env_digest`, warm-cache controlled, median-of-N per commit to
   damp noise): `time(Δ)`, `time(full)`, `|AFFECTED|`, `|graph|` (node counts). Size `c_serialize/c_full`
   explicitly (the unmeasured quantity behind §3). Build the per-language ρ distribution.
4. **Freeze:** `κ_L = ⌈MAX(ρ over floored corpus)⌉ × safety_margin` (see D-4). Confirm the upper tail is
   compressed (`p100/p99 → 1`) so MAX is stable.
5. **Power + negative control** (D-4) green; **pin** at Stage-A go-live; record `p99/p100/margin/floored-size/
   floor-params` in the calibration record + honest-labeling ledger (a `[CONDITIONAL THEOREM]` economics
   claim, not (a)).

**π₀ (per detector class):**
1. **Pin the per-class evaluation-stream definition first** (which adjudicated findings feed which σ;
   each outcome bounded `[0,1]`, tp=1/fp=0, so the stream mean *is* the empirical precision).
2. **Collect** per-class precision baselines on the real Stage-A pinned-env stream (Java+Python; do not mix
   in oracle classes).
3. **Choose** π₀ a margin **below** the median achievable precision per class (high enough to be useful,
   low enough to be clearable). crypto/authn likely need **per-customer** π₀ (run the same instrument in
   `CMP-TRI-03`).
4. **Validate** each candidate with `TST-AC-TRI-02a/b` (reject a degenerate accept-everything/accept-nothing
   π₀); **pin** at Stage-A go-live into the detector-class config map; α stays 0.05.

---

## 11. Proposed `WBS §17` register text (for a human to paste — *not* applied here)

> The following are **proposed** edits for the Architect/CTO to make. This memo does **not** write them.

**Refine `CLAR-PARAM-01` notes (κ portion)** — append:
> κ = property-(b) economics ceiling on the per-commit ratio ρ = time(Δ)/[(|AFFECTED|/|graph|)·time(full)];
> no runtime consumer; calibrated in Phase 5, certified per-language at Stage-A go-live as
> `⌈MAX(ρ, floored corpus)⌉ × margin` (MAX, not p99 — per-commit zero-tolerance gate). Per-detector
> registry read unchanged. Blocked on the well-posedness decision (see `CLAR-PARAM-04`). Interim dev value
> is mechanically separated and never feeds the still-xfail hard gate `TST-AC-SNAP-02a`.

**New row** (PARAM domain):
> | `CLAR-PARAM-04` | Should AC-SNAP-02a's bound be affine — `time(Δ) ≤ κ·(|AFFECTED|/|graph|)·time(full) + C₀` — to absorb the constant frontier + O(\|graph\|) serialization floor (restoring `PLAN.md`'s `O(\|AFFECTED\| + frontier)`), or should the floor be removed by delta-only persistence / a ratified corpus floor? How is `C₀`/`f_min` pinned per (language, Env)? | CMP-SNAP-02 (gating the certified-κ pin for TST-AC-SNAP-02a) | Stage-A go-live | **OPEN** — Architect (PLAN↔SDD arbitration via /cto if they conflict) |

**Flip `CLAR-PARAM-02` note** — keep DEFERRED, but name the two blockers: per-class certified π₀ *and* the
per-class evaluation-stream definition (pin the stream first); interim uniform π₀ = 0.80 config-driven; α=0.05.

*(Register housekeeping, noted not fixed: do not collide with the existing `CLAR-MIGRATION-01` duplicate-ID
and stale `CLAR-TRI-01` status defects flagged in OPEN-DECISIONS Part 4.)*

---

## 12. Governance boundary — what this memo does and does not do

- **Does:** produce the decision record (option (b)); ground it in the literature + the repo + adversarial
  review; propose register text for ratification.
- **Does not:** edit `PLAN.md`/`SDD.md`/`WBS.md`; flip any `CLAR-*` status; change the verbatim AC formula;
  write production code; mark `CMP-SNAP-02` DONE.
- **Ratification path:** **Architect** rules on D-1/D-2/D-3 (well-posedness) and `CLAR-PARAM-04`; **CTO**
  rules on D-4 (go-live pin) and D-7 (decouple economics gate from the DAG unblock); **Security + Architect**
  own π₀ in Phase 5 (RULE-9 — TRI-02 touches INV-3). Per RULE-8, the CTO ratifies before the dependent
  phase starts.

---

## 13. Risks & backstops

| Risk | Backstop |
|---|---|
| Too-loose certified κ masks a bulk-commit regression | `AC-SNAP-02b` (large-commit tail) + production latency SLOs; positive-power check before hard-gate flip |
| Serialization floor left unaddressed → gate flaky/uninformative | D-3 well-posedness gate is a *precondition* to certifying κ; harness fail-closes on interim-tagged κ |
| Interim κ leaks into the hard gate | Mechanical separation (D-6): gate stays xfail; harness refuses interim-tagged certification |
| `c_serialize/c_full` magnitude is assumed, not measured | Named Phase-5 deliverable (§10 step 3) |
| Too-low certified π₀ admits a low-precision spec into `S` | Calibrate below-median-precision per class; per-customer drift quarantine (`CMP-TRI-03`); two-sided validation rejects degenerate π₀ |
| κ vs `_BET_KAPPA` conflation | §9 disambiguation in the memo + register note |

---

## 14. References

- `SDD.md:107-109` (AC-SNAP-02a/b/c, verbatim) · `PLAN.md:68-74` (Algorithm 1; the (a)-vs-(b) split) ·
  `PLAN.md:147,181` (per-algorithm summary; economics vs soundness)
- `docs/components/DOC-CMP-SNAP-02.md` (§4.2 full-G′ tarball; §6 routing; §9 AC; §10 CLAR-PARAM-01) ·
  `docs/cross-cutting/DOC-ALGS.md §2` (Algorithm 1 reference)
- `analysis/cpg_delta.py` (lines 17-18 κ docstring-only; 309-313 |graph|=len(nodes); 344-355 O(|graph|)
  carry-over + serialization) · `detectors/registry.py:110-133` (`Detector` row; no κ field)
- `docs/components/DOC-CMP-TRI-02.md` (§3 `CandidateSpec.pi_zero`; §10 config-driven) ·
  `services/triage/spec_inference.py:73` (`_BET_KAPPA`) ·
  `tests/falsifier/eprocess/test_tri02_eprocess.py` (Gate-4 live/green; martingale + power + negative control)
- `tests/unit/test_snap_specs.py:169-207` (TST-AC-SNAP-02a xfail/skip sentinel; per-commit zero-tolerance)
- `WBS.md:363` (TST-AC-SNAP-02a per-commit ≥1000) · `WBS.md:924-925` (CLAR-PARAM-01/02) ·
  `docs/OPEN-DECISIONS-2026-06-02.md` Part 1 + Part 4
- Literature: Demers–Reps–Teitelbaum (POPL 1981, optimal incremental — `PLAN.md:37`); Reps–Horwitz–Sagiv
  (IFDS, POPL 1995); Reviser (Arzt & Bodden, ICSE 2014, incremental IFDS/IDE); Soufflé elastic incremental
  (PPDP 2021, ~1.31× fixed-work overhead); IncIDFA (OOPSLA 2025, 2.6× geomean); incremental CodeQL
  (Szabó, FSE 2023); differential dataflow / Materialize; Glean / Infer differential (incremental indexing);
  Waudby-Smith & Ramdas (2024, betting confidence sequences — Algorithm 6 / π₀).

---

*Decision record — PROPOSED. Ratify D-1…D-8, then record the rulings back into `WBS.md §17` and pin the
certified κ_L / π₀ at Stage-A go-live.*
