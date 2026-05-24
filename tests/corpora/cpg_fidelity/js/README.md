# JS/TS CPG-fidelity corpus — CMP-CORP-CPG-js (ground-truth methodology)

This corpus is the **per-language CPG-fidelity evaluation set** consumed by
`CMP-CP-06`'s gate harness for the **JS/TS Stage-B** front-end. INV-6 (per-language
honesty): a front-end failing this gate is reported `front-end-blocked`, never as a
recall failure. Thresholds (CLAR-CORP-02, RESOLVED 2026-05-23): parse success
≥ 99.5%, call-edge precision ≥ 90%, recall ≥ 85%, PDG dependence-edge recall ≥ 80%.
This document is the ground-truth-labelling methodology mandated by
`DOC-CMP-CORP-CPG-js §3.4`; the corpus is **not DONE without it**.

## Status — v0.1.0 (NOT the v1.0.0 gate-passing bar)

This is a **provisional, scaffolding** build. It delivers the load-bearing,
**deterministic ground-truth extraction pipeline**, a **reproducible, version-pinned
`corpus.lock`**, full §4.3 construct-tag + module-system coverage, both surfaces
(js + ts), and a small **genuinely-sourced** real-OSS seed. It deliberately does
**not** yet meet the v1.0.0 ground-truth bar, because:

- the v0.1.0 **call-graph + PDG** come from a documented *intraprocedural* resolver
  (`pipeline/extract_ground_truth.mjs`), **not** Jelly 1.4 + `tsc` as
  `DOC §3.4` requires (filed as **CLAR-CORP-07**);
- program count (9) is a coverage skeleton, not a statistically-meaningful gate set
  (minimum-N is **CLAR-CORP-08**).

The corpus is wired so `CMP-CP-06`'s `TST-AC-CP-06-js-*` can run against
`corpus.lock` today, but **the JS/TS gate must NOT be declared passing on this
v0.1.0 ground truth** — see Open CLARs below.

| Track | This build (v0.1.0) | v1.0.0 gate bar |
|---|---|---|
| Programs | 9 (coverage skeleton) | minimum-N per CLAR-CORP-08 |
| Surfaces | js (7) + ts (2) | both, balanced |
| AST ground truth | typescript-estree 6.18.0 (production tool) | same |
| CFG ground truth | documented per-function visitor | same / Jelly-corroborated |
| Call-graph + PDG ground truth | intraprocedural resolver (CLAR-CORP-07) | Jelly 1.4 + tsc type-informed |

## What is SOURCED vs SYNTHESIZED

- **SOURCED** (real public repos, real `source_url` + `commit_sha`, license on the
  allow-list):
  - `programs/0201-escape-string-regexp` — sindresorhus/escape-string-regexp
    @ `cbc4240…` (MIT, v5.0.0). ESM default export; pure string-method chain.
  - `programs/0202-is-number` — jonschlinkert/is-number @ `98e8ff1…` (MIT, v7.0.0).
    CommonJS `module.exports` predicate; calls `Number.isFinite` / `isFinite`.
- **SYNTHESIZED** (authored for this corpus, Apache-2.0, content-addressed —
  `commit_sha: sha256:…`, `synthetic: true`):
  - `programs/0001-commonjs-hof` — CommonJS, higher-order-functions, node-builtins.
  - `programs/0002-esm-async` — ESM, async-await.
  - `programs/0003-prototype-this` — prototype-mutation, this-binding.
  - `programs/0004-generators-builtins` — generators, node-builtins, ESM.
  - `programs/0005-amd-umd-bundled` — UMD wrapper, bundled-transpiled stressor; the
    `registry[name]()` site is intentionally `dynamic` (excluded from metrics).
  - `programs/0101-ts-type-dispatch` — TS, ESM, type-informed-dispatch (+ tsconfig).
  - `programs/0102-tsx-decorators` — TSX, experimental decorators (+ tsconfig).

## 1. AST extraction (production tool, pinned)

`@typescript-eslint/typescript-estree` **6.18.0** parses both JS and TS into one
ESTree-shaped AST. Canonical serialization: keys sorted recursively,
`parent`/`tokens`/`comments` back-refs stripped, `loc` + `range` source positions
preserved. Output: `programs/<id>/ground_truth/ast.json`.

## 2. CFG extraction

Per `FunctionDeclaration` / `FunctionExpression` / `ArrowFunctionExpression`
(method bodies via their function expression). Nodes = statements; edges =
`seq` (sequential), branch (`if`/`for`/`while`/`switch` bodies), `loop-back`, and
explicit `await` / `yield` suspension self-edges. Output: `cfg.json`.

## 3. Call-graph extraction (v0.1.0 resolver — CLAR-CORP-07)

`pipeline/extract_ground_truth.mjs` emits `(caller, callee, line)` triples tagged:

- `static` — direct identifier calls and non-computed method calls whose name
  resolves to a top-level/prototype function in the same file (incl.
  `X.prototype.m.call/apply/bind`).
- `dynamic` — computed member access (`obj[name]()`), `eval`, `new Function`, and
  higher-order indirection the intraprocedural resolver cannot fix. **Dynamic edges
  are EXCLUDED from gate precision/recall** (CW-DETECT / `CMP-SNAP-03` territory,
  `DOC §3.4`).

> **v1.0.0 replaces this resolver with Jelly 1.4** over the source tree, and a
> second `tsc --noEmit --declaration` pass for TS type-informed edges, taking the
> UNION tagged `jelly-only` / `tsc-only` / `both` / `type-informed` (`DOC §3.4`).
> Filed as **CLAR-CORP-07**. Until then, gate call-edge numbers on this corpus are
> not authoritative.

## 4. PDG dependence edges (v0.1.0)

Intra-function def→use data-dependence edges over variable declarations /
assignments and their later identifier reads. Output: `pdg.json`. v1.0.0 uses
Jelly's dataflow output (CLAR-CORP-07).

## 5. Determinism contract

`extract_ground_truth.mjs` is a **pure function of the source bytes**: no
wall-clock, no RNG, no FS-ordering dependence (all directory walks sorted). Re-running
reproduces a byte-identical `ground_truth/` tree, hence the same `corpus_digest`
(verified: re-extract + rebuild yields identical digest).

## 6. Versioning + digest (release ledger — AC-CORP-CPG-js-b)

`corpus.lock` carries `corpus_version` (semver) + `corpus_digest` (sha256 over the
canonical serialization, EXCLUDING the volatile `built_at` / `built_by` and the
digest field itself). Any program add/remove/re-extract bumps `corpus_version` and
re-pins the digest. `pipeline/build_lock.mjs --check` is the CI drift guard; it also
refuses to emit on any `DOC §7` HARD failure (missing provenance, off-allow-list
license, `surface: ts` without `tsconfig.json`, missing `ground_truth/*.json`,
uncovered construct tag / module system, tool-version drift).

## 7. Forbidden sources

Programs derived from Joern's own `jssrc` test fixtures are forbidden (would bias
the gate). License allow-list: MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause,
MPL-2.0, ISC. Refusals recorded in `LICENSES.md`.

## Rebuild

    cd pipeline
    npm install                 # installs pinned @typescript-eslint/typescript-estree 6.18.0
    node extract_ground_truth.mjs   # regenerate ground_truth/ from source/
    node build_lock.mjs --write     # regenerate corpus.lock
    node build_lock.mjs --check     # CI: fail on digest drift / DOC §7 hard failures

## Open CLARs (block v1.0.0 / gate-passing, not v0.1.0)

- **CLAR-CORP-07** — adopt Jelly 1.4 (+ `tsc --noEmit --declaration` for TS
  type-informed edges) as the call-graph / PDG ground-truth tool, replacing the
  v0.1.0 intraprocedural resolver. Until resolved, JS/TS call-edge + PDG gate
  numbers on this corpus are NOT authoritative and `CMP-CP-06` must NOT declare the
  JS/TS gate passing on v0.1.0 ground truth.
- **CLAR-CORP-08** — minimum program count N (and per-surface / per-module-system
  quotas) for a statistically-meaningful JS/TS fidelity gate. v0.1.0 ships a
  9-program coverage skeleton; the gate bar needs a scoped sourcing campaign.
