# PHP CPG-fidelity corpus — CMP-CORP-CPG-php

Per-language fidelity corpus for **PHP**, the sole input to the `CMP-CP-06`
CPG-fidelity gate for PHP (`DOC-CMP-CORP-CPG-php`, `SDD.md §16`,
`WBS.md §16`). Each item pairs PHP source with ground-truth AST / CFG /
call-graph / PDG so the gate verdict for PHP is **empirical**.

PHP is **Stage D** and ships `oracle-passthrough` only until `CMP-CP-06` passes;
`CLAR-FE-01` (Stage-D front-end build/buy/delay) is **DEFERRED**, so the expected
gate verdict for PHP today is **`front-end-blocked`** (INV-6, `AC-CP-06a`) —
never a recall failure. Building this corpus does **not** depend on `CLAR-FE-01`;
only the gate *verdict* does.

## Status — v0.1.0 (NOT the v1.0.0 release bar)

This is a **provisional, scaffolding** build that delivers a **versioned,
reproducible `corpus.lock`**, the **ground-truth schema + methodology**, the
**dynamic-tag invariant guard**, and **one synthesized item per PHP dynamism
axis**. It deliberately does **not** meet a per-category `N` bar (none is pinned
yet — see `CLAR-CORP-16`) and includes **no** SOURCED real-world / framework
items.

| Track | This build (v0.1.0) | v1.0.0 release bar |
|---|---|---|
| Dynamism axes covered | 6 (variable_functions, call_user_func, magic_methods, eval, include_dynamic, callable_array) + 1 pure_php control | all axes + framework idioms |
| Items per category | 1 | `N` per `CLAR-CORP-16` (OPEN) |
| SOURCED (real OSS @ pinned commit) | 0 | Laravel / Symfony / WordPress / pure-PHP, license-screened |
| Toolchain image digest pinned | no (TBD pending CMP-SNAP-05) | yes |

`AC-CORP-CPG-phpa` (ground truth + methodology) and `AC-CORP-CPG-phpb`
(versioned; thresholds evaluated against the pinned version) are **scaffolded
but NOT declared met** at v0.1.0 — the methodology, schema, and versioned lock
exist, but the sample is a seed, not the evaluation set. The gate must not be
declared passing on this coverage.

## What is SOURCED vs SYNTHESIZED

- **SYNTHESIZED** (all 7 items): pure-PHP snippets authored for this corpus
  (Apache-2.0), in `items/<id>/source/`. Hand-derived ground truth in
  `items/<id>/ground_truth/`. Small by design so the labels are auditable.
- **SOURCED:** none yet (deferred to v1.0.0).

See `methodology.md §4` for the full breakdown and `items/<id>/README.md` per
item.

## Layout

```
corpus.lock                       # versioned manifest (DOC §3.2 schema) + corpus_digest
methodology.md                    # pinned toolchain + derivation procedure + lower-bound rule
README.md                         # this file
pipeline/build_lock.py            # --write / --check; enforces DOC §7 HARD rules + dynamic-tag invariant
items/<id>/
  meta.yaml                       # source_url, source_commit, license, categories, dynamic
  source/<file>.php               # the PHP source
  ground_truth/{ast,cfg,callgraph,pdg}.json
  README.md                       # per-item provenance + what it exercises
```

## Rebuild / verify

```bash
python3 pipeline/build_lock.py --write   # refresh corpus.lock
python3 pipeline/build_lock.py --check   # CI: HARD-fail on digest drift or invariant violation
```

The lower-bound rule (INV-6) is load-bearing: PHP dynamism is undecidable, so
call graphs over dynamic dispatch are a **lower bound** on recall. The corpus
must never be trimmed or relabelled to flatter the front-end (`DOC §5`).

## Open items

- **`CLAR-CORP-16`** (filed `WBS.md §17`): per-category minimum item counts
  for PHP are not pinned by `SDD.md`. v0.1.0 ships 1 item/axis with a documented
  rationale; the `N` bar and the framework-coverage distribution (Laravel /
  Symfony / WordPress / pure-PHP) need a decision before the v1.0.0 build.
- **Toolchain image digest:** TBD pending `CMP-SNAP-05` PHP worker image
  (`methodology.md §1`).
- **`CLAR-FE-01`** (DEFERRED): gates the PHP front-end verdict, not this corpus.
