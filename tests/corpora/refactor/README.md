# Refactor corpus — CMP-CORP-REFAC-01 (seeded-refactor set)

This corpus is the **refactor-stability falsifier** for `CMP-CORE-02`
(Algorithm 3, the `slice_fingerprint`). It anchors `AC-CORE-02a` (fingerprint
invariance under each named refactor) and `AC-CORE-02b` (fingerprint flips on a
genuine fix and on an aliasing-changing extract), and is the input distribution
for `TST-INV-5-CORE-02`. Without this corpus, no claim about Algorithm 3 is
testable (`DOC-CMP-CORP-REFAC-01 §2`). It feeds `tests/falsifier/refac/`.

## Status — v0.1.0 (NOT the v1.0.0 release bar)

This build is **count-complete but topology-thin**. It delivers the full
`AC-CORP-REFAC-01a` inventory — 50 seeded findings × 7 refactors = **350 pairs**
with binary `should-stay | should-flip` ground truth — and a reproducible,
digest-pinned `corpus.lock`. It is shipped at `v0.1.0` rather than `v1.0.0`
because the 50 seeds are round-robined from **8 base templates** (4 Stage-A
classes × 2 Stage-A languages), so the corpus contains only **8 distinct
(class, language) sink-topologies**. A fingerprint implementation that handles
one `injection/java` seed correctly will behave identically on all
`injection/java` seeds (they differ only in identifier suffix). The *count* bar
is met; the *falsifier diversity* is closer to 8 than 50.

`DOC-CMP-CORP-REFAC-01 §4.1` names the seed-selection input as
"Algorithm 2 / Semgrep + manual curation". Sourcing real, structurally-distinct
seeds from public repositories is deferred to v1.0.0 — see **CLAR-CORP-17** in
`WBS.md §17`. Until then, `corpus.lock.distinct_topologies` records the honest
diversity, and consumers (`TST-AC-CORE-02a/b`) must not read this as a
50-independent-topology falsifier.

| Track | This build (v0.1.0) | v1.0.0 release bar |
|---|---|---|
| Pairs (seeds × refactors) | 350 (50 × 7) — meets AC-CORP-REFAC-01a count | 350 |
| Distinct (class, language) topologies | 8 | target set by CLAR-CORP-17 |
| Structurally-distinct seeds | 8 templates | ≥ N distinct, sourced + curated |

## What is SOURCED vs SYNTHESIZED

- **SOURCED (real public repos with `source_url` + `commit_sha`):** **none.**
  This build sources no third-party code. Real-repo seeds are the v1.0.0 work
  deferred under CLAR-CORP-17.
- **SYNTHESIZED:** **all 50 seeds** (and all 350 `after/` trees). The bases in
  `bases/__init__.py` are small closed-world programs authored for this corpus
  (Apache-2.0), each with exactly one seeded source→sink finding. The `after/`
  trees are produced by the deterministic transforms in
  `pipeline/refactor_transforms.py`. Ground truth is **by construction**, not by
  hand (see `annotation-methodology.md`).

## Layout

```
tests/corpora/refactor/
├── corpus.lock                 # version + sha256 digest over all pairs (pinned)
├── annotation-methodology.md   # how ground-truth labels are derived (no hand-labelling)
├── README.md                   # this file
├── LICENSES.md                 # provenance + license attestation (all Apache-2.0)
├── bases/__init__.py           # 8 seeded-vuln base templates (the before/ trees)
├── pipeline/
│   ├── build_corpus.py         # (re)generate seeds + corpus.lock; --write / --check
│   ├── refactor_transforms.py  # the 7 named refactor transforms + ground-truth map
│   └── test_pipeline.py        # inventory (AC-01a) + determinism self-tests
└── seeds/
    └── seed-NNN/
        ├── before/<file>       # the seeded vuln (baseline)
        ├── after/<refactor>/<file>   # one per refactor (7)
        └── meta.yaml           # class, language, sink, per-refactor labels + rationale
```

## The 7 refactors and their ground-truth labels

| Refactor | Label | Algorithm 3 basis |
|---|---|---|
| `alpha-rename-local` | should-stay | α-renaming of locals |
| `pdg-only-formatting` | should-stay | PDG-only formatting |
| `independent-reordering` | should-stay | canonical topological sort |
| `pure-extract` | should-stay | summary-inlining (pure extract) |
| `fqn-move-package-rename` | should-stay | FQN normalization |
| `genuine-fix` | should-flip | sink removed / made safe (AC-CORE-02b) |
| `aliasing-changing-extract` | should-flip | impure extract changes aliasing (AC-CORE-02b) |

Full derivation: `annotation-methodology.md §2`.

## Reproduce / verify

```
cd tests/corpora/refactor
python3 pipeline/build_corpus.py --write    # regenerate seeds + corpus.lock
python3 pipeline/build_corpus.py --check     # fail on digest drift (CI pattern)
python3 -m pytest pipeline/test_pipeline.py  # AC-01a inventory + determinism
```

The build is hermetic: no network, no RNG, and `built_at`/`built_by` are excluded
from `corpus_digest`, so two builds produce the same digest.

## Cross-references

- `DOC-CMP-CORP-REFAC-01` — implementation contract.
- `WBS.md §16 CMP-CORP-REFAC-01` — verbatim Purpose + AC-CORP-REFAC-01a/b.
- `SDD.md §6 CMP-CORE-02` — consumer ACs (AC-CORE-02a/b/c).
- `PLAN.md §"Algorithm 3"` — the 5 named normalization passes + 2 flip cases.
- `.claude/rules/01-invariants.md §INV-5` — `fingerprint_class` semantics.
- `WBS.md §17 CLAR-CORP-17` — topology-diversity expansion (v0.1.0 → v1.0.0).
