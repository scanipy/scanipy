# Python CPG-fidelity corpus — CMP-CORP-CPG-python (ground-truth methodology)

This corpus is the **per-language fidelity evaluation set** consumed by the
CPG-fidelity gate `CMP-CP-06` for **Python** (a Stage A language). The gate runs
the v3.2 Python front-end over each program's `source/` and compares the produced
CPG against the `ground_truth/` annotations here, scoring against the
`CLAR-CORP-02` thresholds: parse success ≥ 99.5%, call-edge precision ≥ 90%,
call-edge recall ≥ 85%, PDG dependence-edge recall ≥ 80%. A language that fails is
reported `front-end-blocked`, never as a recall failure (INV-6). This file is the
ground-truth-labelling methodology mandated by `DOC-CMP-CORP-CPG-python §3.4`; the
corpus is **not DONE without it**.

## Status — v0.1.0 (NOT the v1.0.0 release bar)

This is a **provisional, scaffolding** build that delivers:

- a deterministic, **zero-dependency, in-repo ground-truth extractor**
  (`pipeline/extract_ground_truth.py`);
- a reproducible, version-pinned **`corpus.lock`** (digest pins the evaluation set);
- **11 programs** covering all 10 required construct tags (`DOC §4.3`), one of them
  genuinely SOURCED from a public repo with a pinned commit.

It deliberately does **not** yet meet the v1.0.0 bar, which is gated on
**`CLAR-CORP-11`** (the ground-truth toolchain decision):

| Track | This build (v0.1.0) | v1.0.0 release bar |
|---|---|---|
| Ground-truth extractor | in-repo `extract_ground_truth.py` on host cpython 3.12 | DOC §3.4 pinned scalpel 1.0.4 + Pyan3 1.2.0 + Pyre 0.0.301 on cpython 3.10 |
| Programs | 11 (1 sourced, 10 synthesized) | larger, with more sourced real-world trees per tag |
| `CMP-CP-06` Python verdict | **NOT authoritative** on this ground truth (CLAR-CORP-11) | authoritative once toolchain ratified/provisioned |

**The `CMP-CP-06` Python gate verdict MUST NOT be declared authoritative on the
v0.1.0 extractor-derived ground truth** until `CLAR-CORP-11` resolves — see §5.

## What is SOURCED vs SYNTHESIZED

- **SOURCED (real public repo, pinned `source_url` + `commit_sha`, license on the
  allow-list):**
  - `programs/0011-requests-hooks-sourced` — `psf/requests` `src/requests/hooks.py`
    @ `cd90742ed94d901759e26766197d0ce7c7bd9c8e` (Apache-2.0). Exercises `type-hints`
    + a runtime-receiver `dynamic` call site (`hook(hook_data, **kwargs)`).
- **SYNTHESIZED (authored for this corpus, Apache-2.0, content-addressed by
  `sha256:` of the source tree):** `programs/0001`..`0010`. Each is a small,
  self-contained program targeting one or more `DOC §4.3` construct tags so that
  the static call-graph / CFG / PDG ground truth is **auditable by hand** (the
  dual-review protocol, §3.5). The synthetic bases are the pinned inputs and are
  recorded in `corpus.lock` with `synthetic: true`.

## 1. Directory layout

```
tests/corpora/cpg_fidelity/python/
├── corpus.lock                 # the manifest (corpus_version + corpus_digest)
├── README.md                   # this file (methodology)
├── LICENSES.md                 # per-source license attribution
├── programs/NNNN-<tag>/
│   ├── source/                 # the program source tree
│   ├── ground_truth/{ast,cfg,callgraph,pdg,parse}.json
│   ├── provenance.yaml         # source_url + commit/sha + license + python minor
│   └── extraction.yaml         # pinned tool versions + known limitations
└── pipeline/
    ├── extract_ground_truth.py # the (versioned) extractor
    └── build_lock.py           # validates + emits corpus.lock
```

## 2. Construct-coverage map (DOC §4.3)

| Tag | Program(s) |
|---|---|
| `decorators` | 0001 |
| `async-await` | 0002 |
| `type-hints` | 0001, 0002, 0003, 0008, 0010, 0011 |
| `duck-typing-callsite` | 0004, 0005 |
| `dynamic-dispatch` | 0005, 0006, 0011 |
| `metaclasses` | 0006 |
| `import-star` | 0007 |
| `dataclasses-pydantic` | 0008 |
| `notebooks-converted` | 0009 |
| `c-extension-wrapper` | 0010 |

`build_lock.py` refuses to emit if any required tag has zero programs, and requires
**both** `type-hints` and `duck-typing-callsite` to be present (`DOC §3.2` inv 3).

## 3. Ground-truth methodology (reproducible commands)

All four annotation kinds are produced deterministically by
`pipeline/extract_ground_truth.py`. Same source bytes ⇒ byte-identical JSON.

```bash
# regenerate every program's ground_truth/ + provenance/extraction + corpus.lock
python3 pipeline/build_lock.py --write
# CI: fail if corpus.lock digest drifts from the committed source/ground truth
python3 pipeline/build_lock.py --check
```

1. **AST** (`ast.json`) — cpython `ast.parse(...)` followed by a canonical,
   position-preserving serialization with stable field ordering (`node._fields`
   order + `lineno/col_offset/end_*`). DOC §3.4 step 1.
2. **CFG** (`cfg.json`) — per `FunctionDef`/`AsyncFunctionDef`, a statement-level
   control-flow graph (nodes keyed `L<line>:<NodeType>`; edges
   `fallthrough`/`true`/`false`/`loop-body`/`loop-back`). Class methods are CFG'd
   per-method, not per-class. DOC §3.4 step 2.
3. **Call graph** (`callgraph.json`) — `(caller, callee, line)` triples, each tagged
   `static` or `dynamic`. **Static** iff the callee is a bare `Name` resolving to a
   module-level function in the same file, or an attribute whose method name is a
   known in-file method. **Dynamic** (recorded, EXCLUDED from precision/recall):
   `getattr`/`__import__`/`eval`/`exec`, dict-of-functions dispatch
   (`Subscript`-callee), call-of-call results, cross-module / `import *` names,
   FFI (`ctypes`) targets, and any runtime-receiver attribute call. `CMP-SNAP-03
   CW-DETECT` is the consumer that owns `dynamic` sites; this corpus does not
   measure call-graph fidelity on them. DOC §3.4 step 3.
4. **PDG dependence edges** (`pdg.json`) — intra-procedural data dependence (a name
   use → its most-recent def, parameters seeded at the def line) + control
   dependence (a statement → the controlling `If`/`While`/`For` test). DOC §3.4
   step 4.

Nested callables (inner `def`/`lambda`) are attributed to their **own** caller, not
the enclosing function (the extractor stops descent at nested-callable boundaries
for both call-graph and PDG name resolution).

## 3.5 Dual-review protocol

Every program is `review_status: pipeline` (ground-truth by deterministic
construction over small, hand-auditable sources). A manual correction to any
`ground_truth/*.json` (e.g. a confirmed extractor miss) must (a) be made in the
extractor, not by hand-editing the JSON, and (b) bump `corpus_version`. There are
no hand-edited ground-truth labels in this corpus — all are regenerable from
`source/` via the committed extractor, which is the reproducibility guarantee.

## 3.6 Forbidden sources

Programs derived from Joern's own `pythonsrc` test fixtures are **forbidden** (they
would bias the gate). None are used here. Python-2 programs are rejected at build
time (`_looks_like_python2`, DOC §7).

## 4. Manifest (`corpus.lock`)

`corpus_version` is semver (bump on any program add/remove/re-extract).
`corpus_digest` is the sha256 of the canonical, sorted-key JSON serialization of the
lock **excluding** the volatile `built_at` and the digest field itself, so the
digest pins the evaluation set, not the wall clock. The gate report records both
`corpus_version` and `corpus_digest` (`AC-CORP-CPG-python-b`).

## 5. Open items (CLAR)

| CLAR-ID | Status | Effect on this corpus |
|---|---|---|
| `CLAR-CORP-02` | RESOLVED 2026-05-23 | Python thresholds pinned (parse ≥99.5%, prec ≥90%, rec ≥85%, PDG ≥80%). |
| `CLAR-CORP-11` | OPEN | Ground-truth toolchain: v0.1.0 uses the in-repo extractor on host cpython 3.12 instead of the DOC-pinned scalpel/Pyan3/Pyre on cpython 3.10. v1.0.0 must either provision the pinned toolchain and re-extract (bumping `corpus_version`) **or** ratify the in-repo extractor and amend `DOC-CMP-CORP-CPG-python §3.4`. Until resolved, the `CMP-CP-06` Python verdict is **not authoritative** on this ground truth. |
| `CLAR-OWNER-01` | DEFERRED | Corpus owner unassigned. |

## 6. References

- `DOC-CMP-CORP-CPG-python.md` — build specification.
- `docs/cross-cutting/DOC-STAGING.md §3`, `.claude/rules/04-staging.md` — gate thresholds.
- `docs/cross-cutting/DOC-INV.md §8`, `.claude/rules/01-invariants.md §INV-6` — per-language honesty.
- `WBS.md §16` — `AC-CORP-CPG-python-a/b`. `WBS.md §17` — `CLAR-CORP-02`, `CLAR-CORP-11`.
