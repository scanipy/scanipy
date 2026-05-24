# Go CPG-fidelity corpus — `CMP-CORP-CPG-go`

Per-language CPG-fidelity corpus for Go. Sole input to the `CMP-CP-06` CPG-fidelity
gate for Go (`DOC-CMP-CORP-CPG-go.md`). It pairs curated Go sources with
**tool-derived** ground-truth AST / CFG / call-graph / PDG artifacts so the Go
front-end (Joern or the proprietary replacement scoped under `T-STAGE-C-FE-01` /
`CLAR-FE-02`) can be measured for parse success, call-edge precision/recall, and
PDG dependence-edge recall.

## Status — v0.1.0 (honest scope)

This is an **idiom-coverage** release, not a gate-pass-powered release.

- 7 items, each isolating one Stage-C-relevant Go CPG idiom; ground truth is
  derived by the pinned `tools/derive` (Go 1.22.2 + `x/tools v0.21.0`), never
  hand-labelled.
- The minimum sample size **N** and per-category minimum counts that a
  *statistically meaningful* gate evaluation needs are **not pinned by `SDD.md`**.
  This release does not invent them — see **`CLAR-CORP-04-go`** (`WBS.md §17`).
- Stage C is `STAGE-GATED` on `CLAR-FE-02`; the corpus is buildable and delivered
  now, but the expected `CMP-CP-06` verdict against today's Go front-end is
  `front-end-blocked` (INV-6, `AC-CP-06a`). That is a correct outcome, not a
  corpus defect.

## Layout

```
corpus.lock          # pinned manifest: corpus_version + corpus_digest + per-item digests/stats
methodology.md       # how ground truth was derived (toolchain pins, algorithm choice)
items/<id>/
  source/            # vendored or synthesized Go source (+ build-harness go.mod)
  ground_truth/      # ast.json, cfg.json, callgraph.json, pdg.json (tool-derived)
  provenance.yaml    # origin (SOURCED|SYNTHESIZED), source_url, commit, license, categories
tools/derive/        # the pinned Go ground-truth deriver
pipeline/build_lock.py  # builds + validates corpus.lock (--write / --check)
pipeline/test_lock.py   # TST-AC-CORP-CPG-go-a/-b: schema + digest-pin tests
```

## Items

| Item | Origin | Idiom | Call edges (static/dyn) |
|---|---|---|---|
| 0001-direct-calls | SYNTHESIZED | static monomorphic calls | 5 / 0 |
| 0002-interface-dispatch | SYNTHESIZED | interface dispatch (CHA cone) | 1 / 6 |
| 0003-closures-method-values | SYNTHESIZED | closures, func values, bound methods | 3 / 0 |
| 0004-goroutines-channels | SYNTHESIZED | `go f(...)` spawn + channel flow | 2 / 0 |
| 0005-generics | SYNTHESIZED | type parameters + instantiation | 6 / 0 |
| 0006-embedded-promotion | SYNTHESIZED | method promotion via embedding | 3 / 0 |
| 0007-upstream-reverse | **SOURCED** | real-world parse fidelity (single func) | 0 / 0 |

**SOURCED**: `0007` only (`golang/example@7f05d21`, BSD-3-Clause, byte-verified).
**SYNTHESIZED**: `0001`–`0006` (source authored for this corpus; ground truth
still tool-derived).

## Verify / rebuild

```sh
python3 pipeline/build_lock.py --check     # CI-safe (Python + PyYAML); fails on digest drift
python3 -m pytest pipeline/test_lock.py    # TST-AC-CORP-CPG-go-a/-b

# re-derive ground truth (requires Go 1.22.2 + x/tools v0.21.0):
cd tools && for it in ../items/*/ ; do go run ./derive "$it/source"; done
```

## Invariant anchor (INV-6)

The corpus is the empirical anchor for the Go fidelity claim; it must never be
tuned to flatter the front-end. Items with 0 ground-truth call edges are excluded
from the CP-06 call-edge recall denominator. See `methodology.md §6`.
