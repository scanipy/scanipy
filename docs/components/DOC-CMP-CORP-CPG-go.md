# DOC-CMP-CORP-CPG-go — CPG-fidelity corpus, Go

## 1. Component identity

- **CMP-ID:** `CMP-CORP-CPG-go`
- **Subsystem:** Corpora (Phase 13 cross-cutting deliverable, `WBS.md §16`)
- **Staging:** Stage C (per-language)
- **Owning agent:** Corpus Curator (`/corpus-agent`)
- **Status code:** `STAGE-GATED` on `CLAR-FE-02` (Stage-C points-to / interface-dispatch investment, `WBS.md §17`, DEFERRED). The corpus itself is buildable now; only the gate evaluation against the Go front-end is blocked.
- **Artifact root:** `tests/corpora/cpg_fidelity/go/`

## 2. Mandate

Verbatim from `SDD.md §16` (CMP-CORP-CPG-{java,python,js,go,ruby,php}):

> *Per-language fidelity corpus with ground-truth ASTs, CFGs, and call-edges. One corpus per language; six total.*

Operational role: this corpus is the sole input to `CMP-CP-06` for Go. It is the empirical artifact against which the Joern (or proprietary) Go front-end is measured for parse success, call-edge precision, call-edge recall, and PDG dependence-edge recall. Until `CMP-CP-06` reports green for Go, no Go `(class, language)` pair may enter Algorithm 2 benchmarking (`PLAN.md §"Per-language launch gate"`, RULE-7 in `.claude/rules/00-global.md`). The corpus exists so that "front-end-blocked" can be a measured outcome rather than an excuse.

## 3. Interface contract — data artifact

### 3.1 Directory layout

```
tests/corpora/cpg_fidelity/go/
├── corpus.lock               # signed manifest; pins every item by commit SHA
├── methodology.md            # annotation methodology (how ground-truth was derived)
├── items/
│   ├── <item-id>/
│   │   ├── source/           # vendored or fetched-by-commit source tree
│   │   ├── ground_truth/
│   │   │   ├── ast.json      # ground-truth AST per file
│   │   │   ├── cfg.json      # ground-truth CFG per function
│   │   │   ├── callgraph.json# ground-truth call edges (caller → callee)
│   │   │   └── pdg.json      # ground-truth PDG dependence edges
│   │   └── README.md         # provenance: source URL, commit, license
└── README.md                 # corpus overview + version
```

### 3.2 `corpus.lock` schema

```yaml
corpus_id: CORP-CPG-go
corpus_version: vX.Y.Z          # semver; bumped on any item add/remove/relabel
corpus_digest: sha256:<hex>     # digest over canonical-sorted item digests
created_at: <iso-8601>
language: go
items:
  - id: <item-id>
    source_url: <upstream URL or "vendored">
    source_commit: <sha>
    license: <SPDX-id>
    item_digest: sha256:<hex>   # over source/ + ground_truth/
    categories: [interfaces, goroutines, generics, ...]
```

### 3.3 Per-item methodology requirements

- **Source pinning:** every item references a specific upstream commit SHA or is vendored verbatim (license-permitting). No floating refs.
- **Ground-truth AST:** derived from the canonical `go/ast` package output at a pinned Go toolchain version (recorded in `methodology.md`).
- **Ground-truth CFG:** derived from a documented, reproducible procedure (e.g. SSA-form blocks from `golang.org/x/tools/go/ssa` at a pinned version) — methodology recorded in `methodology.md`.
- **Ground-truth call graph:** derived from a pinned tool/version (e.g. `golang.org/x/tools/go/callgraph/cha` or `vta`). The choice is documented, not silently swapped.
- **Ground-truth PDG dependence edges:** derived from a documented, reproducible procedure; same pinning discipline.

`methodology.md` is the audit trail; an annotation that cannot point to a pinned tool/version is not eligible for the corpus (AC-CORP-CPG-*a).

## 4. Inputs and outputs

### 4.1 Inputs (build-time)

- Upstream Go source artifacts (vendored or fetched by SHA).
- Pinned Go toolchain image for ground-truth derivation (records as `env_digest` on the methodology).
- Hand-curated category labels.

### 4.2 Outputs (consumed downstream)

- `tests/corpora/cpg_fidelity/go/corpus.lock` — pinned manifest.
- The directory tree under `items/` — consumed by `CMP-CP-06` harness.
- `methodology.md` — consumed by auditors and the CTO Agent.

### 4.3 Front-end-gating context

- **Gate consumer:** `CMP-CP-06` runs the Joern Go front-end (or a proprietary replacement scoped under `T-STAGE-C-FE-01` / `CLAR-FE-02`) over every item and compares its emitted AST/CFG/callgraph/PDG against the ground truth.
- **Until `CLAR-FE-02` is resolved (DEFERRED in `WBS.md §17`):** the corpus is delivered and versioned, but the Go front-end is not yet equipped to meet the call-edge recall floor (≥ 85%, `CLAR-CORP-02` RESOLVED 2026-05-23). The expected gate verdict on this corpus is `front-end-blocked` (AC-CP-06a, INV-6). This is a correct outcome, not a corpus failure.

## 5. Invariants touched

| Invariant | Discharge |
|---|---|
| **INV-6 (Per-language honesty)** | This corpus is the empirical anchor for the Go fidelity claim. When the Joern Go front-end falls below any threshold in `DOC-STAGING.md §"Gate thresholds"`, `CMP-CP-06` reports `front-end-blocked` for Go — never as an Algorithm 2 recall failure. The corpus must never be tuned, trimmed, or relabelled to flatter the front-end; doing so would launder an INV-6 violation. |

## 6. Dependency contract

- **`Depends-On`:** none (`WBS.md §20`, `CMP-CORP-CPG-* → []`).
- **Downstream consumers:** `CMP-CP-06` (sole gate consumer); indirectly every Stage-C component blocked behind the gate.
- **No SCM dependency:** items are vendored or fetched by SHA at build time; the corpus does not require any `CMP-SCM-*` component.

## 7. Failure modes and operational risks

| Mode | Mitigation |
|---|---|
| **Upstream commit disappears.** A referenced upstream commit is force-pushed or the repository deleted. | Every item carries an archival vendored copy at the pinned `source_commit`. The fetch path is a fallback, not a dependency. |
| **Ground-truth derivation drift.** The pinned Go toolchain or callgraph tool changes its output across patch versions. | `methodology.md` pins toolchain image digests. Re-derivation requires a `corpus_version` bump and a new `corpus_digest`. |
| **License non-redistribution.** A vendored item carries a non-redistributable license. | License is recorded per item in `corpus.lock`; items without redistribution-friendly licenses are referenced by URL+SHA only, not vendored. CI rejects vendored items lacking an SPDX identifier in an allowlist. |
| **Category coverage skew.** Corpus over-weights one Go idiom (e.g. interface dispatch) and under-samples another (e.g. goroutines or generics). | `corpus.lock` enumerates per-item `categories`; CI asserts minimum-count thresholds per category (filed as `CLAR-CORP-03-go` if Wave-2 derivation needs it; otherwise carry methodology rationale in `methodology.md`). |
| **Front-end blockage misreported as corpus defect.** A gate failure caused by `CLAR-FE-02` is logged against the corpus rather than the front-end. | `CMP-CP-06` emits a structured verdict identifying the failing dimension; `front-end-blocked` is the correct outcome until `CLAR-FE-02` resolves (INV-6, AC-CP-06a). |

## 8. Provenance threading

The corpus is consumed by `CMP-CP-06` runs whose outputs are persisted in the staging-gate ledger. Required fields on each gate-evaluation record:

- `corpus_id = "CORP-CPG-go"`
- `corpus_version` — verbatim from `corpus.lock`
- `corpus_digest` — verbatim from `corpus.lock`
- `front_end_id` — identity of the Go front-end under evaluation (e.g. `joern@<digest>` or a proprietary identifier per `T-STAGE-C-FE-01`)
- `env_digest` — pinned analysis-environment digest from `CMP-SNAP-05`
- `verdict ∈ {green, front-end-blocked}` — never `recall-failure` (INV-6)

A `corpus_version` bump invalidates all prior gate-evaluation records for Go; the gate must re-run.

## 9. Acceptance criteria cross-reference

Verbatim from `SDD.md §16`:

- **AC-CORP-CPG-goa:** *Corpus carries ground-truth AST/CFG/call-edge annotations and a documented annotation methodology.*
- **AC-CORP-CPG-gob:** *Corpus is versioned; gate thresholds are evaluated against the pinned corpus version.*

### Test mapping

| AC | Test ID | Kind | Status |
|---|---|---|---|
| AC-CORP-CPG-goa | `TST-AC-CORP-CPG-go-a` | [UNIT] — schema validation of `corpus.lock`; methodology.md present and references pinned tools | [FORTHCOMING] |
| AC-CORP-CPG-gob | `TST-AC-CORP-CPG-go-b` | [INTEGRATION] — `CMP-CP-06` rejects a gate run whose pinned `corpus_digest` does not match the on-disk corpus | [FORTHCOMING] |

Gate-side tests that *consume* this corpus (not part of this CMP):

- `TST-AC-CP-06a` — Failing Go reported `front-end-blocked`, not recall failure (INV-6, AC-CP-06a). [INVARIANT]
- `TST-AC-CP-06b` — Gate verdict for Go is recorded and consulted by staging logic (AC-CP-06b). [UNIT]

## 10. Edge cases and unspecified behaviour

- **Per-category minimum counts for Go** are not pinned by `SDD.md`. If the Wave-2 build needs them, file `CLAR-CORP-03-go` before pinning. Until then, `methodology.md` documents the rationale for the chosen distribution.
- **Choice of points-to / call-graph algorithm** for ground-truth derivation (CHA vs RTA vs VTA vs Andersen-style) is recorded in `methodology.md`; the choice is *not* the same as the choice in `T-STAGE-C-FE-01` (`CLAR-FE-02`). Ground-truth uses the most precise reproducible algorithm available; the front-end under evaluation is whatever the production toolchain ships.

## 11. Open questions

- **`CLAR-FE-02`** (DEFERRED, `WBS.md §17`): *Stage-C points-to / interface-dispatch investment scope (Andersen-style baseline vs richer).* Until this resolves, `CMP-CP-06` cannot promote Go past `front-end-blocked` against this corpus. The corpus build itself does not block on this CLAR — only the gate verdict does.
- **`CLAR-CORP-02`** (RESOLVED 2026-05-23, `WBS.md §17`): thresholds pinned at parse ≥ 99.5%, call-edge precision ≥ 90%, recall ≥ 85%, PDG dependence-edge recall ≥ 80%. Threshold changes require a new CTO-approved CLAR (`DOC-STAGING.md §"Per-language gate thresholds"`).

---

*Cross-references: `SDD.md §16 (CMP-CORP-CPG-*)`, `PLAN.md §"Per-language launch gate"`, `WBS.md §17 (CLAR-FE-02, CLAR-CORP-02)`, `docs/cross-cutting/DOC-STAGING.md`, `docs/cross-cutting/DOC-INV.md (INV-6)`, `.claude/rules/04-staging.md`.*
