# PHP CPG-fidelity corpus — ground-truth methodology (CMP-CORP-CPG-php)

This document is the **annotation methodology** mandated by
`DOC-CMP-CORP-CPG-php §3.3` and `AC-CORP-CPG-phpa`. The corpus is **not DONE
without it**: an annotation that cannot point to a pinned tool/version + a
reproducible procedure is not eligible for the corpus.

This corpus is the **sole input to `CMP-CP-06` for PHP**. Per `DOC §2`, PHP is
Stage D and ships `oracle-passthrough` only until `CMP-CP-06` clears the gate;
`CLAR-FE-01` (Stage-D front-end build/buy/delay) is DEFERRED, so the expected
gate verdict for PHP today is `front-end-blocked` (INV-6, `AC-CP-06a`) — **never**
a recall failure. The corpus exists so that verdict is empirical.

## 1. Pinned toolchain (the audit anchor)

Ground truth is defined as the output of the following procedure under a pinned
toolchain. The corpus-build host does **not** have PHP installed; the
`ground_truth/*.json` files are the **persisted projections** of that procedure,
hand-derived for v0.1.0 (see §4). The toolchain is pinned here so re-derivation
is reproducible and any tool drift forces a `corpus_version` bump.

| Stage | Tool | Pin |
|---|---|---|
| AST | `nikic/PHP-Parser` | `v5.3.1` (composer; recorded here, executed in the `CMP-CP-06` image) |
| PHP runtime | `php-cli` | `8.3.x` (matches the `CMP-SNAP-05` analysis image) |
| CFG / PDG | in-repo extractor over the PHP-Parser AST | versioned with this corpus (`schema: cpg-fidelity/*/v0.1.0`) |
| Toolchain image digest | PHP analysis image | **TBD** — pinned when `CMP-SNAP-05` publishes the PHP worker image digest (tracked alongside `CLAR-CORP-03-php`). |

> The image-digest pin is a known v0.1.0 gap: `CMP-SNAP-05` has not yet published
> a PHP worker image. Until then the toolchain is pinned by tool semver only; the
> image digest is recorded as `TBD` rather than fabricated.

## 2. Ground-truth schema (what the JSON encodes)

Each item carries four ground-truth files. They encode the **gate-relevant
projections** the `CMP-CP-06` harness compares against (not a full raw PHP-Parser
dump, which is an implementation detail of the AST stage):

- `ast.json` — declared functions/methods/classes with name + line + params.
- `cfg.json` — per-function basic blocks (`entry`/`cond`/`assign`/`return`/`exit`
  plus `eval`/`include`/`call` markers) with successor edges and source lines.
- `callgraph.json` — caller→callee edges, each tagged with `resolution`
  (`static` or `dynamic-*`); `is_lower_bound`, `dynamic`, optional
  `eval_sites` / `include_sites`.
- `pdg.json` — intra-procedural data/control dependence edges
  (`{function, from, to, type}`); `is_lower_bound`.

## 3. Per-item labelling protocol

1. **Who labels.** A Corpus Curator reads each source tree end-to-end.
2. **AST / CFG / PDG.** Derived by applying the pinned procedure (§1) to the
   source. For the small synthesized snippets in v0.1.0 these are hand-derived;
   the procedure is deterministic, so a future automated run under the pinned
   image must reproduce them byte-for-byte (modulo the documented schema).
3. **Call graph — the lower-bound rule (INV-6, the load-bearing rule).**
   PHP's dynamism (variable functions `$f()`, `call_user_func`, magic methods
   `__call`/`__callStatic`, `eval`, dynamic `include`, callable arrays
   `[$obj,$m]`) makes a precise call graph **undecidable in general**. Ground
   truth therefore records only **demonstrably-reachable** edges — a *lower
   bound* on call-edge recall — and never claims completeness over a dynamic
   site:
   - A statically-resolvable call → one `resolution: static` edge.
   - A dynamic call whose reachable targets are visible in the snippet (e.g. the
     two string literals assigned to `$fn`) → one `dynamic-*` edge per
     demonstrably-reachable target.
   - A genuinely opaque site (`eval` of a runtime string, dynamic `include` of a
     computed path) → **no callee edge**; the location is recorded in
     `eval_sites` / `include_sites` so the gate accounts for the irreducible
     blind spot instead of scoring it as a recall failure.
4. **Dynamic-tag rule (DOC §3.3, §7 "Dynamism mis-labelled").** Any item whose
   call graph contains a dynamic-resolution edge, an `eval_site`, or an
   `include_site` **must** carry `dynamic: true` in `meta.yaml`. A `pure_php`
   item **must** carry `dynamic: false` and an exact call graph
   (`is_lower_bound: false`). `pipeline/build_lock.py` enforces both as HARD
   failures — a mislabelled item refuses to lock.
5. **Builtins are not nodes.** Library/builtin calls (`strtoupper`,
   `call_user_func` itself, `ucfirst`) are not call-graph nodes; only
   user-defined functions/methods are. This keeps the recall denominator
   front-end-comparable.

## 4. SOURCED vs SYNTHESIZED (v0.1.0)

- **SYNTHESIZED** (all 7 v0.1.0 items): pure-PHP snippets authored for this
  corpus (Apache-2.0), one per dynamism axis. `source_url: vendored`,
  `source_commit: content-addressed` (the `item_digest` in `corpus.lock` is the
  sha256 over the whole item tree). They are deliberately small so the
  hand-derived ground truth is auditable line-by-line.
- **SOURCED** (real OSS at a pinned commit, license-screened): **none yet.**
  Framework idioms (Laravel facades, Symfony DI, WordPress hooks) and bulk
  real-world items are deferred to v1.0.0 (see README + `CLAR-CORP-03-php`).

## 5. Versioning & digest

`corpus.lock` carries `corpus_version` (semver) and `corpus_digest` — the sha256
of the canonical sorted-key serialization of the lock **excluding** the volatile
`created_at` / `built_by` and the digest field itself (`pipeline/build_lock.py`,
mirroring `CMP-CORP-REFL-01`). `CMP-CP-06` evaluates thresholds against this
pinned version (`AC-CORP-CPG-phpb`); any item add/remove/relabel — or a toolchain
re-pin — bumps `corpus_version` and invalidates prior PHP gate-evaluation records.

## 6. Gate thresholds (consumed by CMP-CP-06, not asserted here)

Per `.claude/rules/04-staging.md` / `CLAR-CORP-02` (RESOLVED 2026-05-23): parse
≥ 99.5%, call-edge precision ≥ 90%, call-edge recall ≥ 85%, PDG dependence-edge
recall ≥ 80%. This corpus supplies the ground truth; it does **not** assert the
PHP front-end meets them. Per INV-6, a front-end below any threshold is reported
`front-end-blocked`.
