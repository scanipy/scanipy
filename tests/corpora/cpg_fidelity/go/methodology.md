# Ground-truth methodology — `CMP-CORP-CPG-go`

This document is the audit trail for how every ground-truth artifact in this
corpus was derived. Per `DOC-CMP-CORP-CPG-go.md §3.3`, an annotation that cannot
point to a pinned tool/version is **not eligible** for the corpus. Nothing here
is hand-labelled.

## 1. Toolchain pins

| Role | Tool | Version |
|---|---|---|
| Go compiler / parser | `go` | `go1.22.2 linux/amd64` |
| AST | `go/parser` + `go/ast` (stdlib) | bundled with `go1.22.2` |
| SSA / CFG | `golang.org/x/tools/go/ssa` | `v0.21.0` |
| Call graph | `golang.org/x/tools/go/callgraph/cha` | `v0.21.0` |
| PDG (data dependence) | `golang.org/x/tools/go/ssa` def-use | `v0.21.0` |
| Package loading | `golang.org/x/tools/go/packages` | `v0.21.0` |

The exact `x/tools` build is pinned in `tools/go.mod` + `tools/go.sum`. The same
pins are mirrored into `corpus.lock` (`ground_truth_toolchain`) so the lock is
self-describing.

## 2. The deriver

`tools/derive` (one Go program, `tools/derive/main.go`) produces all four
ground-truth artifacts for one item:

```
go run ./derive <items/<item-id>/source>
# writes items/<item-id>/ground_truth/{ast,cfg,callgraph,pdg}.json
```

It loads the item's `source/` as a Go package (`packages.LoadAllSyntax`), builds
SSA with `ssa.InstantiateGenerics`, and emits:

- **`ast.json`** — per-file `go/ast` node-kind histogram, total node count, and
  the sorted names of top-level func/type declarations. Deriver: `go/parser+go/ast`.
- **`cfg.json`** — per-function SSA basic blocks with successor indices and
  instruction counts. Deriver: `x/tools/go/ssa`. SSA basic blocks are the
  canonical, reproducible CFG for Go.
- **`callgraph.json`** — caller→callee edges from **CHA** (Class Hierarchy
  Analysis), each tagged `dynamic: true` when the call site is an interface
  invoke. CHA is a **sound over-approximation** of dynamic dispatch: an
  interface call site resolves to *every* method whose receiver type implements
  the interface. This is the recall-safe direction the Stage-C gate requires
  (`INV-6`; call-edge recall floor ≥ 85%, `CLAR-CORP-02` RESOLVED 2026-05-23).
- **`pdg.json`** — intra-procedural data-dependence (def→use) edges from the SSA
  value graph. Deriver: `x/tools/go/ssa` def-use.

### Determinism

All collections are sorted before serialization (functions by name, edges by
(caller, callee), AST decls lexically, block successors numerically). JSON is
`MarshalIndent` with a trailing newline. Re-running the deriver on the same
source under the same pins reproduces byte-identical artifacts.

### Algorithm choice (DOC §10)

The ground-truth call-graph algorithm is **CHA**. It is the most precise
*reproducible, whole-corpus-cheap* over-approximation that is sound for dynamic
dispatch without requiring a `main`-rooted, points-to analysis. This choice is
**independent** of the production Go front-end under evaluation (`T-STAGE-C-FE-01`
/ `CLAR-FE-02`); the front-end is scored *against* this ground truth, not derived
from the same algorithm.

A known subtlety (resolved here): generic **instantiations** (`Sum[int]`,
`add[float64]`, …) have a nil `ssa.Function.Pkg`. The deriver's locality filter
falls back to `Function.Origin().Pkg` so per-instantiation call edges are
retained rather than silently dropped. Without this, item `0005-generics` would
have produced a vacuous empty call graph — see `corpus.lock` `ground_truth`
counts, which exist precisely so an auditor can spot an under-populated item.

## 3. Items: SOURCED vs SYNTHESIZED

| Item | Origin | Idiom | Source |
|---|---|---|---|
| `0001-direct-calls` | SYNTHESIZED | static monomorphic calls | authored for this corpus |
| `0002-interface-dispatch` | SYNTHESIZED | interface dynamic dispatch (CHA cone) | authored for this corpus |
| `0003-closures-method-values` | SYNTHESIZED | closures, func values, bound methods | authored for this corpus |
| `0004-goroutines-channels` | SYNTHESIZED | `go f(...)` spawn edges, channel data flow | authored for this corpus |
| `0005-generics` | SYNTHESIZED | type parameters + instantiation | authored for this corpus |
| `0006-embedded-promotion` | SYNTHESIZED | method promotion via embedding | authored for this corpus |
| `0007-upstream-reverse` | **SOURCED** | real-world parse fidelity | `golang/example@7f05d21` `hello/reverse/reverse.go`, BSD-3-Clause |

- **SYNTHESIZED** items are hand-authored Go *source* chosen to isolate one
  CPG-fidelity idiom each. Their **ground truth is still tool-derived**, never
  hand-written; only the source is synthetic. Each carries SPDX `Apache-2.0`.
- **SOURCED** item `0007` is vendored verbatim from `golang/example` at the
  pinned commit (BSD-3-Clause, redistribution-friendly). The upstream
  `reverse.go` and `LICENSE` are vendored; their unmodified upstream SHA-256
  values are recorded in the item's `provenance.yaml` so an auditor can verify
  the bytes independently. A build-harness `go.mod` is added solely so the
  pinned deriver can load the package; it does not alter the upstream bytes.

## 4. Category distribution rationale (DOC §10)

`SDD.md` does not pin per-category minimum counts for Go. This v0.1.0 build
samples each major Stage-C-relevant idiom at least once (static calls, interface
dispatch, higher-order/closures, goroutines, generics, embedding) plus one real
upstream parse-fidelity sample. The distribution is deliberately *idiom-coverage
driven*, not statistically powered for a gate-pass recall estimate — see the
v0.1.0 scope note in `README.md` and `CLAR-CORP-04-go`.

## 5. Reproduction

```sh
# (re)derive every item's ground truth under the pinned toolchain
cd tools
for it in ../items/*/ ; do go run ./derive "$it/source"; done
# rebuild + verify the pinned manifest
cd .. && python3 pipeline/build_lock.py --write
python3 pipeline/build_lock.py --check   # exits non-zero on digest drift
```

The committed `ground_truth/*.json` are the authoritative artifacts. CI is not
required to have a Go toolchain: `pipeline/build_lock.py --check` (Python +
PyYAML only) validates the committed corpus against its pinned digest. Only
*re-deriving* ground truth requires `go1.22.2` + `x/tools v0.21.0`.

## 6. Honest-labeling note (INV-6)

This corpus is the empirical anchor for the Go fidelity claim. It must never be
trimmed, tuned, or relabelled to flatter the Go front-end. A front-end that
falls below any threshold is reported `front-end-blocked` (the expected outcome
until `CLAR-FE-02` resolves), never as an Algorithm-2 recall failure. Items with
zero ground-truth call edges (`0007`, and any future single-function item) must
be excluded from the CP-06 call-edge recall *denominator* — a 0/0 item is a free
pass, not evidence of recall.
