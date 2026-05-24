# Ground-truth annotation methodology — CMP-CORP-CPG-ruby

This document is the audit trail mandated by `DOC-CMP-CORP-CPG-ruby SS3.2/SS3.3`
and `AC-CORP-CPG-rubya`. An annotation that cannot point to a pinned tool +
version is not eligible for the corpus. All four ground-truth artifacts per item
(`ast.json`, `cfg.json`, `callgraph.json`, `pdg.json`) are **derived by a single
pinned tool**, not hand-asserted.

## Pinned toolchain

| Artifact | Deriver | Pinned tool |
|---|---|---|
| AST | `toolchain/derive_ground_truth.rb` | `RubyVM::AbstractSyntaxTree` (stdlib) |
| CFG | `toolchain/derive_ground_truth.rb` | documented AST walker (below) |
| Call graph | `toolchain/derive_ground_truth.rb` | documented AST walker (below) |
| PDG | `toolchain/derive_ground_truth.rb` | documented AST walker (below) |

- **Ruby toolchain:** `ruby 3.2.x`. The exact `RUBY_VERSION` used for the active
  build is recorded in `corpus.lock` (`ruby_version`) and in every artifact's
  top-level `ruby_version` field. `RubyVM::AbstractSyntaxTree` node shapes can
  drift across Ruby minor versions; **re-deriving under a different Ruby version
  requires a `corpus_version` bump** (DOC SS7 "Ruby parser drift").
- **Determinism:** `derive_ground_truth.rb` uses no gems, no network, no
  wall-clock, and no global RNG. Output is a pure function of
  `(source bytes, RUBY_VERSION)`. Re-running `build_lock.py --write` reproduces
  byte-identical artifacts and the same `corpus_digest`; `--check` is the CI
  drift guard.

Why a derived AST rather than `whitequark/parser`: the standard-library
`RubyVM::AbstractSyntaxTree` ships with the pinned toolchain image, so the
ground truth has zero external-gem supply-chain surface and no separate pin to
manage. The DOC explicitly permits either (`DOC SS3.3`).

## AST (`ast.json`)

The full `RubyVM::AbstractSyntaxTree` tree, each node serialized as
`{type, line, children}`. Non-node leaves (symbols, literals) are kept verbatim.
This is a faithful, lossless-for-structure dump; it is an exact ground truth (not
a lower bound).

## Control-flow graph (`cfg.json`)

Per method definition (`DEFN` / `DEFS`), a basic-block CFG built by the walker in
`CFGBuilder`:

- One linear basic block per maximal run of straight-line statements.
- A branch node (`IF` / `UNLESS` / `WHILE` / `UNTIL` / `CASE` family) closes the
  current block; its branches become successor blocks; control rejoins at a
  synthetic `JOIN` block. Loops add a back-edge to the loop head.
- `RETURN` closes a block with an edge to the synthetic `EXIT` block.
- Entry/exit are synthetic `ENTRY` / `EXIT` blocks.

**Convention — LOWER BOUND on edges.** Exception control flow (`rescue` /
`ensure` / `retry`) and non-local exits via `throw`/`raise` are **not** modelled.
The CFG is therefore a conservative lower bound on control-flow edges; the gate
harness reads CFG-edge recall against this set as a lower bound (consistent with
the call-graph convention below and INV-6). It is never tuned upward to flatter a
front-end.

## Call graph (`callgraph.json`) — LOWER BOUND

Ruby's dynamism (`send`, `method_missing`, `define_method`, mixins, open classes,
higher-order blocks) makes a precise call graph impossible in general
(`DOC SS3.3`, `SS5`). The ground truth is therefore an explicit **lower bound on
call-edge recall**:

- **Static edges** (`edges`): emitted for `CALL` / `FCALL` / `VCALL` / `OPCALL` /
  `QCALL` nodes whose method name is a plain identifier, plus `super` / `zsuper`
  (recorded as `super:<method>`). We do **not** perform receiver-type resolution:
  an edge records `(caller_method, callee_name, line)`. The gate harness matches
  by callee name; an edge the front-end fails to produce is a recall miss, never
  a precision failure attributable to the corpus.
- **Dynamic sites** (`dynamic_sites`): runtime-dispatched call sites are recorded
  here and **never resolved into edges**, so they cannot inflate the expected
  edge set. Captured kinds:
  - reflective dispatch: `send`, `public_send`, `__send__`, `eval`,
    `instance_eval`/`class_eval`/`module_eval`/`instance_exec`,
    `const_get`/`const_set`;
  - metaprogramming: `define_method`;
  - ghost-method *definitions*: `def:method_missing`, `def:respond_to_missing?`
    (the open set of intercepted names is itself a dynamic mechanism);
  - higher-order invocation: `higher-order:call` (proc/lambda `.call`) and
    `higher-order:yield` (block `yield`).

## Program-dependence graph (`pdg.json`) — LOWER BOUND

Per method, intra-method **def-use data-dependence** edges over local variables
(`LASGN`/`DASGN` defs, `LVAR`/`DVAR` uses, plus parameter binds as defs at the
method's first line). An edge `use -> def` is emitted when a use of a name
follows the most recent def of the same name in source order.

**Convention — LOWER BOUND.** Control dependence, inter-procedural flow,
instance/class-variable flow, and flow through dynamic dispatch are **not**
modelled. PDG dependence-edge recall is read against this set as a lower bound
(matches the `PDG dependence-edge recall >= 80%` gate threshold, CLAR-CORP-02).

## The `dynamic` category tag — HARD rule (INV-6)

`build_lock.py` enforces a HARD validation rule (DOC SS7 risk #4): **any item
whose derived `callgraph.json` has a non-empty `dynamic_sites` MUST carry the
`dynamic` category tag.** This guarantees the gate harness can identify
lower-bound items and interpret recall correctly. A mismatch refuses the build.
The build also warns (non-fatal) if an item is tagged `dynamic` but the deriver
found no dynamic site, so curator labels stay honest against the derivation.

## Category coverage (v0.1.0)

The DOC enumerates Ruby idioms: `send`, `method_missing`, `define_method`,
`monkey_patch`, `rails_active_record`, `blocks_procs_lambdas`. Each is represented
by at least one item; `plain_calls` / `closed_world` and `sourced` anchor the
non-dynamic baseline. Per-category **minimum counts are not pinned by SDD**
(`DOC SS10`); see `CLAR-CORP-07-ruby` (`WBS.md SS17`). Until resolved, this build
documents its distribution rationale here rather than asserting an unpinned N.

## Versioning + digest

`corpus.lock` carries `corpus_version` (semver) and `corpus_digest` (sha256 over
the canonical serialization, excluding the volatile `built_at`/`built_by` and the
digest field itself). Any item add/remove/relabel, or a Ruby-toolchain change,
bumps `corpus_version` and re-pins the digest. `CMP-CP-06` evaluates thresholds
against the pinned `corpus_version`/`corpus_digest` (`AC-CORP-CPG-rubyb`,
`DOC SS8`); a bump invalidates all prior Ruby gate-evaluation records.

## License / redistribution

SOURCED items are vendored only if their SPDX license is on the allow-list
(`MIT`, `Apache-2.0`, `BSD-2-Clause`, `BSD-3-Clause`, `MPL-2.0`) and are pinned by
`source_commit` (no floating refs). `build_lock.py` refuses any item with an
off-list license or a sourced item lacking a `source_commit`.
