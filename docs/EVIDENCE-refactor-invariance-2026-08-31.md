# Evidence — refactor-invariance of `slice_fingerprint` on real CPGs (2026-08-31)

**First empirical run of Algorithm 3 (`analysis/fingerprint.py`) against real Joern-parsed CPGs.**
Harness: `scripts/validate_refactor_fingerprints.py` (Tier-2 track E).
Corpus: `CMP-CORP-REFAC-01` v0.1.0, digest `sha256:0750651a…`.
Scope: `--limit 8` → **56 pairs, 8 seeds** — the corpus is round-robined from **8 base templates**, so
these 8 seeds cover **every distinct topology in the corpus**. Running all 50 seeds repeats the same
8 topologies ~6× and adds no new topological evidence (see `CLAR-CORP-17`).

All 52 evaluated pairs were `strong`/`strong` (no `weak` fallbacks), so every verdict below **is**
invariance evidence under INV-5.

## Result by refactor × language

| Refactor | Expected | Java | Python | Verdict |
|---|---|---|---|---|
| `alpha-rename-local` | stay | **4/4 stayed** | **4/4 stayed** | ✅ **HOLDS (8/8)** |
| `pdg-only-formatting` | stay | **4/4 stayed** | **4/4 stayed** | ✅ **HOLDS (8/8)** |
| `fqn-move-package-rename` | stay | 0/4 — **all flipped** | 4/4 stayed | ❌ **FAILS in Java** |
| `independent-reordering` | stay | 4/4 stayed ⚠️ | 0/4 — **all flipped** | ❌ **FAILS in Python** |
| `pure-extract` | stay | 4/4 stayed ⚠️ | 1/4 stayed, **3 flipped** | ❌ **FAILS in Python** |
| `genuine-fix` | flip | 3/4 flipped, **1 stayed** (seed-007) | 4/4 flipped | ⚠️ **7/8 — one missed fix** |
| `aliasing-changing-extract` | flip | 4/4 **unevaluated** | 4/4 flipped | ⚠️ corpus defect (below) |

Totals: 40 as-expected · **12 contrary** · 4 unevaluated.

## What may be claimed publicly

**Defensible (8/8, both languages):**
- invariance under **local α-renaming**
- invariance under **formatting-only changes**

**NOT defensible — do not claim:**
- **file-move / package-rename** (fails in every Java topology)
- **independent-statement reordering** (fails in every Python topology)
- **extract-method** (fails in 3 of 4 Python topologies)

**"A genuine fix flips the fingerprint" is 7/8, not absolute.** Java `seed-007`'s genuine fix left the
fingerprint unchanged — a real false-negative: in that topology a fixed finding keeps the identity of
the vulnerable one.

## Two caveats that make the picture *worse*, not better

1. **The Java "stayed" cells for `independent-reordering` and `pure-extract` are suspect.** Track E
   found the corpus's `_inject_after_first_body` places statements at **class-body level** in Java,
   which is not valid Java. Those "refactors" may be inert or unparsed rather than genuinely applied,
   so their 4/4 "stayed" is plausibly **vacuous** — it should not be read as a pass.
2. **`aliasing-changing-extract` is 4/4 unevaluated in Java** (`no-fingerprint-after`) for the same
   reason. Reported, never counted as a result.

Taken together: only **α-rename** and **formatting** survive scrutiny in both languages.

## Why the failures are actionable

The failures are **systematic per (refactor × language)**, not random — each maps to a normalisation
pass that `analysis/fingerprint.py` documents as a **no-op**:

| Failing case | Owning pass (currently a no-op) |
|---|---|
| Java FQN/package move | FQN normalisation — evidently does not normalise Java package qualifiers |
| Python statement reorder | canonical topological reordering |
| Python extract-method | summary-inlining normalisation |

Implementing those three passes is a concrete, bounded path to widening the claim. Until then the
honest claim set is the two that hold.

## Reproduce

```bash
# The snapshot image lacks PyYAML; add it once:
#   FROM scanipy-snapshot:localtest
#   RUN pip install --no-cache-dir pyyaml        # -> scanipy-t2run:latest
docker run --rm --network none --entrypoint python \
  -v "$PWD":/app:ro -v "$OUT":/job -e PYTHONPATH=/app -e HOME=/job -w /job \
  scanipy-t2run:latest /app/scripts/validate_refactor_fingerprints.py \
  --corpus-dir /app/tests/corpora/refactor --out /job/topo8.json \
  --summary-out /job/topo8.txt --limit 8
```

~60–75 s per Joern parse; the 8-seed run is 64 parses. A full 50-seed run is ~400 parses (hours) and
adds no new topologies.

## Honest-labeling status

These are **[EMPIRICAL]** measurements over a topology-thin corpus (8 distinct topologies), not a
theorem. They constrain what Algorithm 3's per-refactor invariance claim may assert today; they do
not establish behaviour on unseen topologies.
