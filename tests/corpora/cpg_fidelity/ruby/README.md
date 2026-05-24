# Ruby CPG-fidelity corpus — CMP-CORP-CPG-ruby (v0.1.0)

This corpus is the sole input to the CPG-fidelity gate (`CMP-CP-06`) for **Ruby**.
It carries per-item ground-truth AST / CFG / call-graph / PDG annotations derived
by a single pinned toolchain, plus a versioned `corpus.lock`. It exists so the
Ruby gate verdict is **empirical**, not vibes-based, the moment a Ruby front-end
is available to evaluate.

See `methodology.md` for the full, pinned annotation procedure (the
`AC-CORP-CPG-rubya` audit trail). See `DOC-CMP-CORP-CPG-ruby.md` for the spec.

## Status — v0.1.0 (scaffolding, NOT the full per-category bar)

This build delivers:
- the **deterministic, reproducible ground-truth deriver**
  (`toolchain/derive_ground_truth.rb`) over `RubyVM::AbstractSyntaxTree`;
- **9 curated items** spanning every DOC-enumerated Ruby idiom;
- a versioned, digest-pinned **`corpus.lock`** with a passing `--check`;
- the **`dynamic`-tag HARD rule** wired into `build_lock.py` (INV-6).

It deliberately does **not** pin a per-category minimum sample size `N`: SDD does
not specify one for Ruby (`DOC SS10`). That is filed as **`CLAR-CORP-07-ruby`**
(`WBS.md SS17`) and blocks a v1.0.0 bar, not this v0.1.0 scaffold.

## INV-6 / staging honesty

Ruby is **Stage D** and ships **oracle-passthrough only** until `CMP-CP-06`
passes (`.claude/rules/04-staging.md`). The Stage-D front-end work is
`CLAR-FE-01` (DEFERRED — build vs buy vs delay). The Joern Ruby front-end has the
lowest maturity of the six languages; **the expected gate verdict for Ruby is
`front-end-blocked`, never an Algorithm-2 recall failure** (INV-6,
`AC-CP-06a`). This corpus is **never tuned to flatter the front-end**: the call
graph, CFG, and PDG are documented **lower bounds** (`methodology.md`), so a
front-end that under-resolves is reported as front-end-blocked, not as a corpus
defect.

## SOURCED vs SYNTHESIZED

- **SOURCED (real OSS, pinned by commit SHA, allow-listed license):**
  - `items/0008-src-sinatra-version` — sinatra `lib/sinatra/version.rb`
    @ `7b50a1bb…` (v4.1.1), MIT.
  - `items/0009-src-sinatra-indifferent-hash` — sinatra
    `lib/sinatra/indifferent_hash.rb` @ `7b50a1bb…` (v4.1.1), MIT. Real
    method-rich production Ruby with `super`, `&method(:…)`, and a `yield`.
- **SYNTHESIZED (authored for this corpus, Apache-2.0):**
  - `items/0001-syn-plain-calls` — `plain_calls`, `closed_world` baseline.
  - `items/0002-syn-send-dispatch` — `send` / `public_send`.
  - `items/0003-syn-method-missing` — `method_missing` ghost methods.
  - `items/0004-syn-define-method` — `define_method` metaprogramming.
  - `items/0005-syn-monkey-patch` — `monkey_patch` (reopened core class).
  - `items/0006-syn-blocks-procs-lambdas` — `blocks_procs_lambdas` (yield / proc).
  - `items/0007-syn-active-record-style` — `rails_active_record` dynamic finders.

## Layout

```
corpus.lock              # versioned, digest-pinned manifest (AC-CORP-CPG-rubyb)
methodology.md           # pinned annotation methodology (AC-CORP-CPG-rubya)
build_lock.py            # builds + validates the lock; --check is the CI guard
toolchain/
  derive_ground_truth.rb # the single pinned ground-truth deriver
items/<id>/
  source/<file>.rb       # vendored / pinned Ruby source
  ground_truth/{ast,cfg,callgraph,pdg}.json
  README.md              # source URL, commit, license, categories
```

## Rebuild

    python3 build_lock.py --write    # re-derive ground truth + rewrite the lock
    python3 build_lock.py --check     # CI: fail on digest drift

`--write` is idempotent under a fixed Ruby version: it reproduces byte-identical
artifacts and the same `corpus_digest`.

## Open CLARs

- **`CLAR-FE-01`** (DEFERRED) — Stage-D Ruby front-end (build/buy/delay). Until
  resolved, `CMP-CP-06` cannot promote Ruby past `front-end-blocked`. The corpus
  build does **not** block on this; only the gate verdict does.
- **`CLAR-CORP-02`** (RESOLVED 2026-05-23) — gate thresholds: parse >= 99.5%,
  call-edge precision >= 90%, recall >= 85%, PDG dependence-edge recall >= 80%.
- **`CLAR-CORP-07-ruby`** (this build) — per-category minimum sample size `N` for
  the Ruby CPG-fidelity corpus is unpinned by SDD; blocks a v1.0.0 bar.
