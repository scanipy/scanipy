# DOC-CMP-CORP-CPG-js — CPG-fidelity corpus, JavaScript / TypeScript

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `WBS.md §16 CMP-CORP-CPG-{java,python,js,go,ruby,php}` — verbatim Purpose + AC-CORP-CPG-*a/b
- `SDD.md §10 CMP-CP-06` — CPG-fidelity gate harness consumer
- `SDD.md §11` — Stage B (JS/TS) gating constraint
- `SDD.md §12` — corpora as work packages
- `docs/cross-cutting/DOC-STAGING.md §3` — gate criteria thresholds (per CLAR-CORP-02)
- `docs/cross-cutting/DOC-INV.md §8` — INV-6 / per-language honesty
- `WBS.md §17 CLAR-CORP-02` — RESOLVED 2026-05-23: parse ≥ 99.5%, call-edge precision ≥ 90%, recall ≥ 85%, PDG dependence-edge recall ≥ 80%
- `.claude/commands/corpus-agent.md` — Corpus Curator briefing
- `.claude/rules/04-staging.md`, `.claude/rules/01-invariants.md §INV-6`

This document is the **build specification** for the JavaScript / TypeScript CPG-fidelity corpus consumed by `CMP-CP-06`. JS/TS is a **Stage B** language — its gate must pass before any `(class, js)` or `(class, ts)` pair enters the Algorithm 2 benchmark, **and** Stage B itself begins only after Stage A is determinism-attested (`SDD.md §11`). INV-6 is the per-language honesty invariant: a language failing the gate is reported `front-end-blocked`, never as a recall failure.

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-CORP-CPG-js` |
| Subsystem | Corpora (`WBS.md §16`) |
| Artifact type | **Data** — labelled corpus + ground-truth extraction pipeline (not code) |
| Language under test | **JavaScript** (ES2022 baseline) and **TypeScript** (5.x baseline) — a single corpus covering both surfaces |
| Staging | Stage B — must precede JS/TS's entry into `CMP-CP-06` / Algorithm 2; Stage A determinism-attested first |
| Depends-On | **none** (`WBS.md §20`) — Wave-1 leaf (corpus can be built before Stage A attestation) |
| Owner | **DEFERRED** via `CLAR-OWNER-01` (Corpus Curator role; `/corpus-agent`) |
| INV-* touched | **INV-6** — provides the per-language fidelity evaluation set so a failing front-end is reported `front-end-blocked`, not as a recall failure. |
| Consumer | `CMP-CP-06` (CPG-fidelity gate harness) via `.github/workflows/stage-gate.yml` job `cpg-fidelity` |

---

## 2. Mandate

**Verbatim WBS `Purpose:` (`WBS.md §16 CMP-CORP-CPG-{java,python,js,go,ruby,php}`):**

> Per-language fidelity corpus with ground-truth ASTs, CFGs, and call-edges. One corpus per language; six total.

**Operational role.** For JS/TS, this corpus answers: *does the v3.2 front-end (Joern jssrc / typescript-eslint-derived pipeline) recover the AST, CFG, call-graph, and PDG of representative JS/TS programs with enough fidelity that Algorithm 2 recall claims are meaningful?* JavaScript brings two complications that the methodology must account for: (a) the **module-system zoo** (ESM, CommonJS, AMD, UMD, ESM-via-Babel) — call-edge resolution depends on module-binding correctness; (b) **TypeScript's compile-time type system disappears at runtime** — call edges informed by TS types are richer than the JS runtime would resolve, and the corpus measures both modes.

Two language-level subsets coexist under `language: js-ts` in one corpus, with a `surface: js | ts` per-program tag to keep gate reporting honest. The CLAR-CORP-02 thresholds apply to the union; per-surface breakdown is reported but does not weaken the gate verdict.

Until the gate passes for JS/TS, the `(class, js)` / `(class, ts)` pairs ship as `front-end-blocked`, never as a recall failure (INV-6).

---

## 3. Interface contract (corpus layout + manifest schema)

### 3.1 Directory layout

```
tests/corpora/cpg_fidelity/js/
├── corpus.lock                          # the manifest (see §3.2)
├── README.md                            # ground-truth-methodology document (see §3.4)
├── LICENSES.md                          # per-source license attribution (see §7)
├── programs/
│   ├── 0001-express-app/
│   │   ├── source/                      # the program source tree (one repo or curated slice)
│   │   ├── ground_truth/
│   │   │   ├── ast.json                 # serialized ESTree AST (acorn / @typescript-eslint)
│   │   │   ├── cfg.json                 # per-function CFG (nodes + edges)
│   │   │   ├── callgraph.json           # call edges + per-edge {static, dynamic, type-informed} tag
│   │   │   └── pdg.json                 # PDG dependence edges
│   │   ├── provenance.yaml              # source URL + commit sha + sha256 + surface + module-system
│   │   └── extraction.yaml              # exact tool versions used (see §3.4)
│   ├── 0002-typescript-react-app/
│   └── ...
└── pipeline/
    ├── extract_ground_truth.mjs         # the (versioned) extraction script (see §3.4)
    └── build_lock.mjs                   # emits corpus.lock
```

### 3.2 `corpus.lock` manifest schema (YAML)

```yaml
corpus_id: CMP-CORP-CPG-js
corpus_version: 1.0.0                    # semver; bumped on any program add/remove/re-extract
corpus_digest: sha256:...
language: js-ts                          # unified surface (JS and TS share the corpus)
language_levels:
  ecmascript: "2022"                     # ES2022 baseline
  typescript: "5.x"                      # TS 5.x baseline (per-program TS minor pinned)
built_at: 2026-MM-DDTHH:MM:SSZ
ground_truth_method: |
  AST: @typescript-eslint/typescript-estree 6.x (covers both JS and TS to one ESTree).
       Canonical serialization with stable key ordering and source-position preservation.
  CFG: eslint-plugin-jsdoc-style CFG visitor (or equivalent) per FunctionDeclaration /
       ArrowFunctionExpression / MethodDefinition. Async-await CFG edges through
       suspension points recorded explicitly.
  Call graph: jelly 1.x (Aarhus precise JS call-graph analyzer) over the source tree;
              for TS programs, a second pass with `tsc --noEmit --declaration` for
              type-informed edges. UNION of edges tagged with provenance
              (jelly-only, tsc-only, both, type-informed). Sites that jelly
              labels `dynamic` (e.g. `obj[name]()` where `name` is unresolved)
              are tagged `dynamic` and EXCLUDED from precision/recall.
  PDG dependence edges: jelly's dataflow output OR a documented secondary tool
                        (recorded per-program in extraction.yaml).
  See README.md §3 for exact tool invocations + dispute-resolution protocol.

programs:
  - id: 0001-express-app
    source_url: https://github.com/<org>/<repo>
    commit_sha: <40-char hex>
    sha256_source_tree: <sha256 of source/>
    sha256_ground_truth: <sha256 of ground_truth/>
    license: MIT
    loc: 3200
    surface: js                          # js | ts
    module_system: commonjs              # commonjs | esm | mixed | amd | umd
    construct_coverage:
      - module-system-commonjs
      - higher-order-functions
      - prototype-mutation
      - this-binding
    extraction_tools:
      node: "20.10.0"
      typescript_eslint: "6.18.0"
      jelly: "1.4.0"
      tsc: null                          # not used for surface=js
  - id: 0002-typescript-react-app
    surface: ts
    module_system: esm
    construct_coverage:
      - module-system-esm
      - type-informed-dispatch
      - jsx-tsx
      - decorators-experimental
    extraction_tools:
      node: "20.10.0"
      typescript_eslint: "6.18.0"
      jelly: "1.4.0"
      tsc: "5.3.3"
```

**Required invariants on `corpus.lock`:**

1. Every program has `sha256_source_tree`, `sha256_ground_truth`, `source_url`, `commit_sha`, `license`, `surface`, `module_system`.
2. Both surfaces (`js` and `ts`) are represented; **per-surface counts are reported** in the gate report.
3. Every `module_system` value in `§4.3` is represented by at least one program.
4. The `construct_coverage` tag union (`§4.3`) is **covered**.
5. `extraction_tools` versions are pinned (no `latest`).

### 3.3 Per-program `extraction.yaml`

```yaml
extracted_by: <reviewer-id> | "pipeline"
extracted_at: 2026-MM-DDTHH:MM:SSZ
tool_versions: { node: ..., typescript_eslint: ..., jelly: ..., tsc: ... }
known_limitations: |
  Jelly is sound but may over-approximate at `with` blocks and `eval`. Sites
  reaching `eval` or `new Function(...)` are tagged `dynamic` and EXCLUDED
  from precision/recall. TS type-informed edges add coverage that pure JS
  resolution misses; the gate report breaks down by edge provenance.
review_status: pipeline | second-pass
```

### 3.4 Ground-truth methodology (`README.md`)

`README.md` MUST document, with reproducible command lines:

1. **AST extraction.** `@typescript-eslint/typescript-estree` 6.x parses both JS and TS into one ESTree-shaped AST. Canonical serialization with stable key ordering and source-position preservation.
2. **CFG extraction.** A documented CFG visitor (eslint-plugin-jsdoc-style or equivalent) per `FunctionDeclaration` / `ArrowFunctionExpression` / `MethodDefinition`. `async`/`await` suspension points are explicit CFG edges; generator `yield` likewise.
3. **Call-graph extraction.** Jelly 1.4 over the source. For TS programs, a second pass with `tsc --noEmit --declaration` extracts the type-informed edges. The UNION is the ground truth, with each edge tagged `jelly-only` / `tsc-only` / `both` / `type-informed`. Sites Jelly labels `dynamic` (unresolved property access, `eval`, `new Function`) are tagged `dynamic` and EXCLUDED from gate precision/recall (they are `CMP-SNAP-03 CW-DETECT`'s territory).
4. **PDG dependence edges.** Jelly's dataflow output; if a program needs a secondary tool, document the choice in `extraction.yaml`.
5. **Dual-review protocol.** Manual edits to ground-truth require `review_status: second-pass`; the diff is recorded.
6. **Forbidden sources.** Programs derived from Joern's own jssrc test fixtures are forbidden; record refusals in `LICENSES.md`.
7. **Surface separation.** Per-surface (`js` vs `ts`) gate-metric breakdowns are reported. The union must clear thresholds for `GATE-PASS`; neither surface in isolation determines the verdict, but a large imbalance (e.g., TS-only programs covering the corpus) is a methodology bug.

A corpus is **not DONE** without this document populated. No "vendored mystery zip".

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| JS / TS programs (apps, libraries) | Public OSS repos with permissive licenses | Source URL + commit sha + sha256; license recorded; ES2022+ / TS 5.x |
| Ground-truth extraction toolchain | Node 20 + typescript-eslint 6 + Jelly 1.4 + tsc 5.3 | All pinned in `extraction.yaml` and `README.md`; bumps require new corpus version |

### 4.2 Outputs

| Output | Where | Consumer |
|---|---|---|
| `tests/corpora/cpg_fidelity/js/` + `corpus.lock` | Repo + (optionally) object store | `CMP-CP-06` gate harness |
| `corpus_version` (semver) | `corpus.lock` | Gate result reports (`tests/results/cpg_fidelity/js/latest.json`) |
| `corpus_digest` (sha256) | `corpus.lock` | Gate result reports |

### 4.3 Required JS/TS construct coverage tags

| Tag | What it stresses |
|---|---|
| `module-system-commonjs` | `require()` / `module.exports` resolution |
| `module-system-esm` | `import` / `export` resolution; dynamic `import()` |
| `module-system-amd-umd` | At least one legacy AMD/UMD program for parser stressor |
| `higher-order-functions` | Functions stored, passed, returned — call-graph edges through indirection |
| `prototype-mutation` | `prototype` extension; `Object.create` |
| `this-binding` | `bind` / `call` / `apply`; arrow-vs-function `this` |
| `async-await` | `async`/`await` CFG suspension |
| `generators` | `function*` / `yield` |
| `type-informed-dispatch` | TS-only: interface / generic dispatch resolved via tsc |
| `jsx-tsx` | React JSX / TSX programs — AST surface diversity |
| `decorators-experimental` | TS `@decorator` syntax — front-end parse-success stressor |
| `node-builtins` | Programs that call into `fs`, `child_process`, etc. — FFI-boundary edges |
| `bundled-transpiled` | At least one program that includes Webpack/Vite-style bundles — parse-success stressor |

A corpus that lacks any tag is incomplete; `pipeline/build_lock.mjs` refuses to emit.

---

## 5. Invariants touched

| Invariant | How `CMP-CORP-CPG-js` discharges it | Test |
|---|---|---|
| **INV-6** | Provides the labelled fidelity evaluation set against which the v3.2 JS/TS front-end is judged. A failing front-end here yields `front-end-blocked`, never a recall failure (`AC-CP-06a`). | `TST-AC-CP-06-js-parse`, `TST-AC-CP-06-js-call-prec`, `TST-AC-CP-06-js-call-rec`, `TST-AC-CP-06-js-pdg-rec` `[FORTHCOMING]`. |

---

## 6. Dependency contract

`CMP-CORP-CPG-js` is a leaf node in the dependency DAG (`WBS.md §20`). It assumes:

- `CMP-CP-06`'s gate harness reads `corpus.lock`, runs the v3.2 JS/TS front-end on each program's `source/`, and compares the produced CPG against `ground_truth/`.
- The comparison metric: per-file parse success, edge-set precision/recall on `(caller, callee, line)` triples (with `dynamic`-tagged edges excluded; per-edge provenance preserved in the report), and dependence-edge recall on PDG edges.
- Stage B sequencing: Stage A must be determinism-attested (`CMP-CP-05` green for Stage A) before JS/TS is eligible for Algorithm 2 benchmarking — this is a staging gate orthogonal to the per-language CPG-fidelity gate, but the corpus itself can be built and the gate run independently.

Downstream consumers: `CMP-CP-06` (JS/TS gate), `CMP-CORE-01` Algorithm 2 benchmark.

---

## 7. Failure modes and error contracts

| Failure | Detection | Required response |
|---|---|---|
| **Reproducibility break** — a program lacks `source_url` + `commit_sha` + `sha256` | `pipeline/build_lock.mjs` refuses to emit `corpus.lock` | Re-source with deterministic provenance. |
| **Surface imbalance** — corpus is >90% one surface | Build-time check (per-surface count) | Add programs of the under-represented surface; document the rebalance. |
| **Module-system gap** — a `module_system` value in `§4.3` has zero programs | Build-time check | Add at least one program for the missing module system. |
| **Ground-truth tool drift** — `extraction.yaml` versions ≠ `README.md` pinned versions | Build-time check | Re-extract under pinned versions; bump `corpus_version`. |
| **Missing construct tag** | Build-time check | Reject; add programs for the missing tag. |
| **License incompatibility** — license not on allow-list (MIT, Apache-2.0, BSD-2/3, MPL-2.0, ISC) | Build-time check | Reject the program; record refusal in `LICENSES.md`. |
| **`corpus_digest` drift** | CI digest check | Hard CI fail. |
| **Ground-truth methodology drift** — `README.md` silent on a step | Methodology review | Block the build. |
| **Joern-jssrc-fixture contamination** | Manual review | Reject; would bias the gate. |
| **TS without `tsconfig.json`** — a program tagged `surface: ts` lacks a tsconfig | Build-time check | Require a `tsconfig.json` (or document a synthetic one); without it `tsc` cannot run reproducibly. |
| **Gate failure on JS/TS front-end** — `CMP-CP-06` reports `GATE-FAIL` for js-ts | `.github/workflows/stage-gate.yml` | Report `front-end-blocked` per `AC-CP-06a`; do NOT shrink the corpus or relax thresholds. Front-end investment is the response. |

---

## 8. Provenance threading

| Field | Where | Threading rule |
|---|---|---|
| `corpus_version` (semver) | `corpus.lock` → gate report | Bumped on any add/remove/re-extract; matches release ledger (`AC-CORP-CPG-*b`). |
| `corpus_digest` (sha256) | `corpus.lock` → gate report | Pins the exact evaluation set. |
| Per-program `sha256_source_tree`, `sha256_ground_truth`, `commit_sha`, `license`, `surface`, `module_system` | `corpus.lock` items | Reproducibility + per-surface honesty contract. |
| `extraction_tools` versions | per-program `extraction.yaml` | Re-extraction reproducible. |

**Must NOT touch:** `origin`, `S_version`, `env_digest`, `cpg_order_hash`, `slice_fingerprint`, or any `findings` row.

---

## 9. Acceptance criteria cross-reference

Quoted verbatim from `WBS.md §16 CMP-CORP-CPG-{java,python,js,go,ruby,php}`. All `TST-AC-CORP-CPG-js-*` are `[FORTHCOMING]`.

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-CORP-CPG-js-a** | > Corpus carries ground-truth AST/CFG/call-edge annotations and a documented annotation methodology. | `TST-AC-CORP-CPG-js-a` `[FORTHCOMING]` — asserts each program has `ground_truth/{ast,cfg,callgraph,pdg}.json`; `README.md` documents methodology per `§3.4`; both surfaces represented. |
| **AC-CORP-CPG-js-b** | > Corpus is versioned; gate thresholds are evaluated against the pinned corpus version. | `TST-AC-CORP-CPG-js-b` `[FORTHCOMING]` — asserts `corpus.lock` carries `corpus_version` + `corpus_digest`; gate report records both. |

**Consumer-facing gate tests (this corpus exists to make them runnable):**

- `TST-AC-CP-06-js-parse` `[FORTHCOMING]` — asserts parse success rate ≥ 99.5%.
- `TST-AC-CP-06-js-call-prec` `[FORTHCOMING]` — asserts call-edge precision ≥ 90% (over non-`dynamic` edges).
- `TST-AC-CP-06-js-call-rec` `[FORTHCOMING]` — asserts call-edge recall ≥ 85% (over non-`dynamic` edges).
- `TST-AC-CP-06-js-pdg-rec` `[FORTHCOMING]` — asserts PDG dependence-edge recall ≥ 80%.

Invariant tests cross-referenced:

- `TST-INV-6-CP-06 [FORTHCOMING]` — gate harness produces pass/fail per language.

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-CORP-CPG-js |
|---|---|---|---|
| `CLAR-CORP-02` | CPG-fidelity gate thresholds per language | **RESOLVED** 2026-05-23 | JS/TS thresholds: parse ≥ 99.5%, call-edge precision ≥ 90%, recall ≥ 85%, PDG ≥ 80%. |
| `CLAR-OWNER-01` | Per-component / corpus owner | **DEFERRED** | `§1` Owner stays DEFERRED. |

**No new CLAR-CORP-* are filed by this document.** Thresholds and methodology toolchain are pinned. The unified-corpus-for-two-surfaces decision is documented here (`§2`, `§3.2`, `§7`) rather than filed as a separate CLAR — it follows from `WBS.md §16`'s single corpus per language entry naming `js` (not `js,ts`).

---

## 11. References

- `WBS.md §16 CMP-CORP-CPG-{java,python,js,go,ruby,php}` — verbatim ACs.
- `SDD.md §10 CMP-CP-06` — consumer (gate harness).
- `SDD.md §11` — Stage B gating constraint.
- `SDD.md §12` — corpora as work packages.
- `docs/cross-cutting/DOC-STAGING.md §3` — gate criteria thresholds.
- `docs/cross-cutting/DOC-INV.md §8` — INV-6 / per-language honesty.
- `docs/components/DOC-CMP-CP-06.md` (sibling, forthcoming) — gate harness.
- `docs/components/DOC-CMP-SNAP-03.md` (sibling) — `CW-DETECT` owns `dynamic`-tagged sites this corpus excludes from call-graph metrics.
- `.claude/commands/corpus-agent.md` — Corpus Curator briefing.
- `WBS.md §17 CLAR-CORP-02` — gate threshold resolution.
- `.claude/rules/04-staging.md`, `.claude/rules/01-invariants.md §INV-6`.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for a Corpus Curator agent to assemble `CMP-CORP-CPG-js` and for the `CMP-CP-06` gate harness implementer to consume it. The JS/TS gate verdict (`TST-AC-CP-06-js-*`) determines whether `(class, js)` / `(class, ts)` pairs enter the Algorithm 2 benchmark — INV-6 is the load-bearing invariant.*
