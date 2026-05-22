# DOC-CMP-CORP-CPG-ruby — CPG-fidelity corpus, Ruby

## 1. Component identity

- **CMP-ID:** `CMP-CORP-CPG-ruby`
- **Subsystem:** Corpora (Phase 13 cross-cutting deliverable, `WBS.md §16`)
- **Staging:** Stage D (per-language)
- **Owning agent:** Corpus Curator (`/corpus-agent`)
- **Status code:** `STAGE-GATED` on `CLAR-FE-01` (Stage-D proprietary front-end work — build / buy / delay, `WBS.md §17`, DEFERRED). The corpus itself is buildable now; only the gate evaluation against the Ruby front-end is blocked.
- **Artifact root:** `tests/corpora/cpg_fidelity/ruby/`

## 2. Mandate

Verbatim from `SDD.md §16` (CMP-CORP-CPG-{java,python,js,go,ruby,php}):

> *Per-language fidelity corpus with ground-truth ASTs, CFGs, and call-edges. One corpus per language; six total.*

Operational role: this corpus is the sole input to `CMP-CP-06` for Ruby. Ruby has the lowest Joern front-end maturity (`SDD.md §11`, `PLAN.md §"Phase staging"`); Ruby ships `oracle-passthrough` only until the gate passes (`.claude/rules/04-staging.md`). The corpus is delivered so that the gate verdict is empirical, not vibes-based — and so that when the front-end matures (whether via the Joern path or via the proprietary work package tracked under `CLAR-FE-01`), the evaluation is ready to run.

## 3. Interface contract — data artifact

### 3.1 Directory layout

```
tests/corpora/cpg_fidelity/ruby/
├── corpus.lock               # signed manifest; pins every item by commit SHA
├── methodology.md            # annotation methodology
├── items/
│   ├── <item-id>/
│   │   ├── source/           # vendored or fetched-by-commit Ruby source
│   │   ├── ground_truth/
│   │   │   ├── ast.json      # ground-truth AST per file
│   │   │   ├── cfg.json      # ground-truth CFG per method
│   │   │   ├── callgraph.json# ground-truth call edges
│   │   │   └── pdg.json      # ground-truth PDG dependence edges
│   │   └── README.md         # source URL, commit, license
└── README.md
```

### 3.2 `corpus.lock` schema

```yaml
corpus_id: CORP-CPG-ruby
corpus_version: vX.Y.Z          # semver; bumped on any item add/remove/relabel
corpus_digest: sha256:<hex>     # over canonical-sorted item digests
created_at: <iso-8601>
language: ruby
items:
  - id: <item-id>
    source_url: <upstream URL or "vendored">
    source_commit: <sha>
    license: <SPDX-id>
    item_digest: sha256:<hex>
    categories: [send, method_missing, define_method, monkey_patch,
                 rails_active_record, blocks_procs_lambdas, ...]
```

### 3.3 Per-item methodology requirements

- **Source pinning:** every item references a specific upstream commit SHA or is vendored verbatim. No floating refs.
- **Ground-truth AST:** derived from a pinned Ruby parser (e.g. `whitequark/parser` at a pinned gem version, or `Ripper` at a pinned Ruby toolchain version) — recorded in `methodology.md`.
- **Ground-truth CFG:** derived from a documented, reproducible procedure (e.g. `RubyVM::AbstractSyntaxTree` plus a published control-flow extractor at a pinned version).
- **Ground-truth call graph:** Ruby's dynamism (`send`, `method_missing`, `define_method`, mixins) makes a precise call-graph impossible in general. The corpus must document its **one-sided convention**: edges in the ground truth represent calls that are *demonstrably reachable* (lower-bound recall test). Items that test reflective/dynamic dispatch carry a label noting the dynamic-dispatch nature so the gate harness can interpret recall correctly.
- **Ground-truth PDG dependence edges:** documented, reproducible procedure; same pinning discipline.

`methodology.md` is the audit trail; an annotation that cannot point to a pinned tool/version is not eligible for the corpus (AC-CORP-CPG-*a).

## 4. Inputs and outputs

### 4.1 Inputs (build-time)

- Upstream Ruby source artifacts (vendored or fetched by SHA).
- Pinned Ruby toolchain image for ground-truth derivation.
- Hand-curated category labels reflecting Ruby idioms (Rails / Sinatra / pure-Ruby variants).

### 4.2 Outputs (consumed downstream)

- `tests/corpora/cpg_fidelity/ruby/corpus.lock` — pinned manifest.
- The directory tree under `items/` — consumed by `CMP-CP-06` harness.
- `methodology.md` — consumed by auditors and the CTO Agent.

### 4.3 Front-end-gating context

- **Gate consumer:** `CMP-CP-06` runs the Joern Ruby front-end (or a proprietary replacement scoped under `T-STAGE-D-FE-01` / `CLAR-FE-01`) over every item and compares against ground truth.
- **Until `CLAR-FE-01` is resolved (DEFERRED in `WBS.md §17`):** the corpus is delivered and versioned, but the Joern Ruby front-end is unlikely to clear the thresholds (`DOC-STAGING.md §"Per-language gate thresholds"`). The expected gate verdict is `front-end-blocked` (AC-CP-06a, INV-6). Ruby ships `oracle-passthrough` only until the gate flips green (`.claude/rules/04-staging.md`).

## 5. Invariants touched

| Invariant | Discharge |
|---|---|
| **INV-6 (Per-language honesty)** | Ground-truth in this corpus is treated as a lower bound on call-edge recall (Ruby's dynamism makes a precise upper bound undecidable). When the Ruby front-end falls below any threshold, `CMP-CP-06` reports `front-end-blocked` — never as an Algorithm 2 recall failure. The corpus must never be tuned to flatter the front-end. |

## 6. Dependency contract

- **`Depends-On`:** none (`WBS.md §20`, `CMP-CORP-CPG-* → []`).
- **Downstream consumers:** `CMP-CP-06` (sole gate consumer); indirectly every Stage-D Ruby `(class, language)` pair.
- **No SCM dependency:** items are vendored or fetched by SHA at build time.

## 7. Failure modes and operational risks

| Mode | Mitigation |
|---|---|
| **Upstream commit disappears.** Force-push or repo deletion. | Every item carries an archival vendored copy at the pinned `source_commit`. |
| **Ruby parser drift.** `Ripper` or `whitequark/parser` AST shape changes across Ruby minor versions. | `methodology.md` pins the toolchain image digest. Re-derivation requires a `corpus_version` bump. |
| **License non-redistribution.** | License recorded per item in `corpus.lock`; non-redistributable items referenced by URL+SHA only, not vendored. CI rejects vendored items without an allowlist-SPDX. |
| **Dynamism mis-labelled.** A `send` / `method_missing` / `define_method` item is labelled as `closed-world` when it is not. | Item categories explicitly enumerate dynamic-dispatch sites; a `methodology.md` rule requires items containing reflective dispatch to carry a `dynamic` category tag so the gate harness can interpret recall as lower-bound. |
| **Front-end blockage misreported as corpus defect.** | `CMP-CP-06` emits a structured verdict identifying the failing dimension; `front-end-blocked` is the correct outcome until `CLAR-FE-01` resolves (INV-6, AC-CP-06a). |

## 8. Provenance threading

Each `CMP-CP-06` gate-evaluation record consuming this corpus must carry:

- `corpus_id = "CORP-CPG-ruby"`
- `corpus_version` — verbatim from `corpus.lock`
- `corpus_digest` — verbatim from `corpus.lock`
- `front_end_id` — identity of the Ruby front-end under evaluation (e.g. `joern@<digest>` or proprietary identifier per `T-STAGE-D-FE-01`)
- `env_digest` — pinned analysis-environment digest from `CMP-SNAP-05`
- `verdict ∈ {green, front-end-blocked}` — never `recall-failure` (INV-6)

A `corpus_version` bump invalidates all prior gate-evaluation records for Ruby; the gate must re-run.

## 9. Acceptance criteria cross-reference

Verbatim from `SDD.md §16`:

- **AC-CORP-CPG-rubya:** *Corpus carries ground-truth AST/CFG/call-edge annotations and a documented annotation methodology.*
- **AC-CORP-CPG-rubyb:** *Corpus is versioned; gate thresholds are evaluated against the pinned corpus version.*

### Test mapping

| AC | Test ID | Kind | Status |
|---|---|---|---|
| AC-CORP-CPG-rubya | `TST-AC-CORP-CPG-ruby-a` | [UNIT] — schema validation of `corpus.lock`; methodology.md present and references pinned tools; dynamic-dispatch items carry the `dynamic` tag | [FORTHCOMING] |
| AC-CORP-CPG-rubyb | `TST-AC-CORP-CPG-ruby-b` | [INTEGRATION] — `CMP-CP-06` rejects a gate run whose pinned `corpus_digest` does not match the on-disk corpus | [FORTHCOMING] |

Gate-side tests that *consume* this corpus (not part of this CMP):

- `TST-AC-CP-06a` — Failing Ruby reported `front-end-blocked`, not recall failure (INV-6, AC-CP-06a). [INVARIANT]
- `TST-AC-CP-06b` — Gate verdict for Ruby is recorded and consulted by staging logic (AC-CP-06b). [UNIT]

## 10. Edge cases and unspecified behaviour

- **Per-category minimum counts for Ruby** are not pinned by `SDD.md`. If Wave-2 build needs them, file `CLAR-CORP-03-ruby` before pinning. Until then, `methodology.md` documents the rationale for the chosen distribution (in particular: dynamic-dispatch idioms must be represented in proportion to their real-world Rails / pure-Ruby prevalence).
- **Choice of call-graph construction algorithm** for ground-truth derivation is recorded in `methodology.md`. Ruby's lack of a canonical points-to analysis means ground-truth is treated as a *lower bound* on call-edge recall; this convention is explicit in `methodology.md` and the gate harness honours it.

## 11. Open questions

- **`CLAR-FE-01`** (DEFERRED, `WBS.md §17`): *Stage-D proprietary front-end work — build vs buy vs delay.* Until this resolves, `CMP-CP-06` cannot promote Ruby past `front-end-blocked`. The corpus build itself does not block on this CLAR — only the gate verdict does. Ruby remains `oracle-passthrough` until the CLAR resolves (`.claude/rules/04-staging.md`).
- **`CLAR-CORP-02`** (RESOLVED 2026-05-23, `WBS.md §17`): thresholds pinned at parse ≥ 99.5%, call-edge precision ≥ 90%, recall ≥ 85%, PDG dependence-edge recall ≥ 80%. Threshold changes require a new CTO-approved CLAR (`DOC-STAGING.md §"Per-language gate thresholds"`).

---

*Cross-references: `SDD.md §16 (CMP-CORP-CPG-*)`, `PLAN.md §"Per-language launch gate"`, `WBS.md §17 (CLAR-FE-01, CLAR-CORP-02)`, `docs/cross-cutting/DOC-STAGING.md`, `docs/cross-cutting/DOC-INV.md (INV-6)`, `.claude/rules/04-staging.md`.*
