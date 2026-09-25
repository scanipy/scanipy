# Implementation plan — closing the refactor-invariance gap before Black Hat MEA

> Historical input. For execution use
> [the 2026-09-25 handoff](PLAN-BHMEA-EXECUTION-2026-09-25.md) and
> [review revision 3](REVIEW-BHMEA-EXECUTION-ACTION-ITEMS-2026-09-23.md).
> The owner removed the October lock and retained the full submitted scope;
> old deadline, automatic feature-drop, and obsolete architecture-blocker
> instructions below are preserved for traceability, not active directions.

**Owner:** project owner · **Written:** 2026-09-21 · **Talk:** 1–3 December 2026, Riyadh
**Runway:** ~10 weeks · **Demo lock:** **Friday 23 October** (non-negotiable — see §5)

> This plan is about making the *accepted submission* true. It is not a general roadmap.
> Anything that does not change what happens on stage is out of scope here.

---

## 0. The gap, precisely

The accepted Arsenal submission claims identity that is *"stable under renaming, formatting,
reordering, extract-method and file moves"*, and scripts all five as demo beat #2, "the
headline". The first empirical run against real Joern-parsed CPGs
(`docs/EVIDENCE-refactor-invariance-2026-08-31.md`, 8 seeds = all 8 corpus topologies,
56 pairs, every pair `strong`/`strong`) measured:

| Demo beat | Java | Python | State |
|---|---|---|---|
| rename locals | 4/4 | 4/4 | **holds** |
| reformat | 4/4 | 4/4 | **holds** |
| reorder independent statements | 4/4 ⚠ | **0/4** | fails |
| extract a helper | 4/4 ⚠ | **1/4** | fails |
| move file / rename package | **0/4** | 4/4 | fails |
| *a genuine fix flips it* | 3/4 | 4/4 | **7/8 — one false negative** |

⚠ The Java cells for reorder and extract are **not passes**. The corpus injects those
variants at class-body level, which is not valid Java (issue #361), so the refactor is
probably inert or unparsed. **For two of the three target refactors there is currently no
usable Java signal at all.** That is why §2 comes before §3.

**Goal:** by 23 October, the demo script contains only beats the harness proves green, and
that set is as close to five as the work honestly reaches.

---

## 1. Rules that govern every change

1. **The gate is three-sided.** A change is accepted only if it (a) fixes its target column,
   (b) leaves α-rename and formatting at 8/8, and (c) does **not** reduce the `genuine-fix`
   flip count. Every normalisation pass makes fingerprints coarser and can manufacture new
   genuine-fix false negatives — that is the standing risk of this entire plan.
2. **A regression in `genuine-fix` is blocking, always.** A missed fix means a fixed bug
   keeps the vulnerable finding's identity and stays suppressed. It is the only failure mode
   here that harms a user, and it is what Q&A will probe.
3. **Never tune the harness or the corpus to improve a number.** Fix the mechanism or narrow
   the claim. A red cell published is survivable; a green cell manufactured is not.
4. **Do not edit `PLAN.md` / `SDD.md`.** Where the spec is silent (notably the definition of
   "pure extract"), file a `CLAR-*` in `WBS.md §17` (RULE-4).
5. **Evidence beats intuition.** Every claim that reaches a slide must come from a harness
   run recorded in `docs/evidence/`.

---

## 2. W0 — Prerequisites (week of 21 Sep). Do these before touching `fingerprint.py`.

### W0.1 — A Joern-free iteration loop *(highest leverage single task in this plan)*
At 60–75 s per parse the 8-seed run is ~70–80 minutes. Iterating against it caps you at
about four attempts a day and is the difference between fixing FQN in a day and in a week.

- Add a cache: parse each corpus tree **once**, persist the raw Joern export to disk
  (`--export-cache <dir>`), and let the harness rebuild CPGs from cache.
- Dump the *normalised* slice for any pair on demand (`--dump-slice <seed>/<refactor>`) as
  JSON: node `(kind, operator_or_literal, resolved_fqn, enclosing_decl_fqn)` in canonical
  order, plus the ranked edge triples — i.e. exactly what `_content_hash` consumes.
- Then iterate in pure-Python unit repros with no Joern in the loop. Spend the full run only
  as a gate.

**Done when:** a cached 8-seed run completes in under ~3 minutes and one command prints a
before/after normalised-slice diff for any failing pair.

### W0.2 — Valid Java corpus pairs (issue #361)
Fix `_inject_after_first_body` so Java statements are injected inside a **method body**, not
the class body. Regenerate the affected variants, re-pin `corpus.lock`.

**Done when:** all 8 Java `aliasing-changing-extract` pairs evaluate instead of returning
`no-fingerprint-after`, and the Java reorder/extract cells reflect a refactor that genuinely
applied. Expect some of those 4/4s to turn red — **that is the point**; they were vacuous.

### W0.3 — Baseline re-run and tracker correction
Re-run the 8-seed harness on the fixed corpus and record it as the **true** baseline. Then
correct issue **#360**, whose body is wrong in a way that will misdirect anyone who picks
it up: `_fqn_normalise` is *implemented* (so Java FQN is a **bug**, not a missing pass), and
`_canonical_topo_sort` is identity *by design* (its docstring asserts `canonical_order`
already delivers reorder-invariance — Python 0/4 proves that assertion false, so the defect
is in the ordering/hash, not in a missing pass). Only `_summary_inline_pure_extract` is a
genuine no-op, and its docstring gives a *soundness* reason, not a TODO.

---

## 3. Workstreams, ordered by confidence

### W1 — File move / package rename *(Java 0/4 → 4/4)*. Est. 1–3 days.
Highest confidence: one refactor, one language, a single leak.

**Already ruled out — do not re-litigate:**
- `structural_path` — excluded from `_content_hash` by design, and the weak-order fallback
  that keys on it was never taken (all pairs were `strong`/`strong`).
- *Signature-debris asymmetry* — `_norm_fqn` does mangle Joern Java full names
  (`…foo:void(java.lang.String)` → `%pkg.String)`), but the corpus refactor is a pure package
  move (`com.scanipy.corpus.refac` → `com.scanipy.corpus.relocated.refac`) with class and
  method names unchanged, so **both sides normalise to the same value**. Mangling is real and
  worth fixing for correctness, but it is not this failure.

**Two candidates remain. One diff splits them** — dump the normalised slices for seed-001
`fqn-move-package-rename` before/after and compare:

| If the diff shows… | Cause | Fix |
|---|---|---|
| differing `operator_or_literal` on some node | **Most likely.** It is the only field `_content_hash` *and* `_seed_labels` both consume that no pass normalises. A `NAMESPACE_BLOCK`, `TYPE_REF` or qualified call target carries the package text into the hash. | Normalise qualified names in `operator_or_literal` for the node kinds that render them — same `%pkg.` collapse as `_norm_fqn`. |
| identical node content but different node **count/shape** | The package move changes what Joern emits (an extra namespace node, a different slice frontier), so the graphs differ before hashing. | Exclude namespace/package scaffolding from the backward slice, or normalise it to a single canonical token. |

While in here, fix `_norm_fqn` to be Java-aware anyway: split on `:` first, normalise the
qualifier **and** each signature type, then rejoin. Guard it with a unit test using real
Joern-shaped Java full names.

### W2 — Independent statement reordering *(Python 0/4)*. Est. 3–6 days. Real design work.
`_canonical_topo_sort` is identity because the docstring claims `canonical_order` already
makes the hash reorder-invariant. It does not. **Mechanism:** swapping two data-independent
statements flips the CFG edge between them; 2-WL relabels; ranks change; the hashed
`(kind, src_rank, dst_rank)` triples change.

This is a **decision**, not a patch: *do CFG-order edges between data-independent statements
belong in the fingerprint?* The hard constraint is that the same edge family is part of what
makes a genuine fix flip, so removing them wholesale will cost you rule 1(c).

Options, cheapest first:
1. **Exclude CFG edges between statements with no data dependence** from the hashed edge set
   (keep PDG/data-dependence and call edges). Smallest change; verify the genuine-fix column
   immediately, since a sanitizer insertion must still flip.
2. **Materialise a real canonical topological re-sort** in the pass: order data-independent
   statements by their WL colour rather than their CFG position, then rank.
3. **Hash the edge relation modulo independent-statement order** — most faithful, most work.

Take option 1 first and only escalate if the genuine-fix column regresses.

### W3 — The `genuine-fix` false negative *(7/8)*. Est. 1–2 days. **Ahead of W4.**
Java `seed-007`'s real fix left the fingerprint unchanged. Diagnose with the same slice-diff
tool: either the fix lies outside the backward slice (slice frontier too narrow) or its
effect is being normalised away. Re-check this column after **every** W1/W2 change.

### W4 — Extract method *(Python 1/4)*. Est. unbounded — **spec-blocked, not code-blocked.**
`_summary_inline_pure_extract` returns the slice unchanged, and its docstring explains why:
normalising a *pure* extract safely requires a purity/alias oracle the minimal CPG model does
not carry, and a heuristic risks normalising an **impure** extract — silently auto-suppressing
a genuinely-changed finding, exactly what `AC-CORE-02b` guards against.

So the blocker is a decision, not an implementation:
1. File / resolve **`CLAR-CORE-02`** — what the spec means by "pure extract", and what
   evidence the model must have before normalising one.
2. Only then implement the narrowest safe subset (likely: single-callsite, no aliasing of
   mutable arguments, no writes to enclosing scope).

**Do not plan the talk assuming W4 lands.** It is the correct candidate to drop.

---

## 4. Schedule

| Week | Dates | Work | Exit condition |
|---|---|---|---|
| **W0** | Sep 21–27 | Fast loop · valid Java corpus (#361) · true baseline · fix #360 body | 8-seed cached run < 3 min; slice-diff tool works; honest baseline recorded |
| **W1** | Sep 28 – Oct 4 | File-move/package-rename (W1) | Java FQN 4/4; α-rename + formatting still 8/8; genuine-fix ≥ baseline |
| **W2** | Oct 5–11 | Independent reordering (W2) | Python reorder 4/4 **or** documented as dropped |
| **W3** | Oct 12–18 | Genuine-fix FN (W3) + hardening; buffer for W1/W2 overrun | genuine-fix 8/8; full unit suites green |
| **W4** | Oct 19–25 | Extract-method **only if** CLAR-CORE-02 resolved. **Demo lock Fri 23 Oct.** | Final harness run → the claim set is frozen |
| **W5** | Oct 26 – Nov 1 | Rewrite abstract-facing material to the locked set; re-render supporting PDF | Slides/PDF/README state exactly what is proven |
| **W6** | Nov 2–8 | Build the stage demo on the locked set; verified-parsing fixtures only | Demo runs end-to-end, offline, twice in a row |
| **W7** | Nov 9–15 | Rehearse; failure drills (what to say if a beat misbehaves) | Timed run-through inside the slot |
| **W8** | Nov 16–22 | Freeze code. Tag a release; publish signed images | Tagged, reproducible build attendees can run |
| **W9** | Nov 23–29 | Travel prep; final rehearsal; offline fallback recording | Recorded fallback demo on the laptop |
| — | **Dec 1–3** | **Talk** | |

Buffer is deliberately in W3 and W9. W1 and W2 are the only items with real technical
uncertainty; W0 exists to make them fast.

---

## 5. The demo lock (23 October) and the fallback

On 23 October, run the harness and **freeze the claim set to exactly what is green**. Then
rewrite the abstract-facing language to match. This converts "we didn't finish" into a
deliberate October scoping decision instead of a discovery in Riyadh.

**If the set is four of five** (extract-method dropped — the most likely outcome): say so
plainly. *"Identity survives renaming, formatting, reordering and file moves. Extract-method
is the open one — here is exactly why it is hard, and here is the measurement."* An Arsenal
audience respects a measured limitation far more than a claim that fails live.

**If reordering also slips (three of five):** the talk still stands on rename + formatting +
file-move, plus reproducibility and provenance, which are already real and demonstrated.
Lead harder on the provenance beat (`sign → VERIFIED`, tamper → `TAMPERED`) — it is unique
and it already works.

**What never happens:** demoing a beat the harness has not proven on a file you have not
verified parses.

---

## 6. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| A new pass manufactures genuine-fix false negatives | Highest — a fixed bug stays suppressed; it is what Q&A finds | Rule 1(c): re-check the column after every change; treat regression as blocking |
| W2 CFG-edge change breaks the flip semantics | Reorder and genuine-fix are in direct tension | Take the narrowest option first; escalate only on evidence |
| Corpus regeneration (#361) invalidates the baseline | Numbers move under you mid-plan | Re-baseline in W0 *before* any `fingerprint.py` change |
| Topology-thin corpus (8 topologies, `CLAR-CORP-17`) | Green cells may not generalise | State the caveat on the slide; never claim beyond the corpus |
| Live demo fails on stage | Talk-ending | W9 offline recorded fallback; verified-parsing fixtures only |
| Extract-method blocked on `CLAR-CORE-02` | Plan slips if treated as code work | Already scoped as droppable; do not build the talk on it |

---

## 7. First three actions

1. **Confirm the RSVP was sent.** The deadline was 19 September and today is the 21st. If it
   has not gone, email Abdulrahman Khaledi now — nothing else in this plan matters otherwise.
2. Build the export cache + slice-diff tool (**W0.1**).
3. Dump the seed-001 `fqn-move-package-rename` normalised-slice diff and settle which of the
   two W1 candidates it is.

---

*Evidence: `docs/EVIDENCE-refactor-invariance-2026-08-31.md`, `docs/evidence/`.
Harness: `scripts/validate_refactor_fingerprints.py`. Tracker: #359 (CLAR-ORCH-12),
#360 (normalisation — body needs correcting per §2.3), #361 (corpus defects).*
