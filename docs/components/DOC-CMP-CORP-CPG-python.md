# DOC-CMP-CORP-CPG-python — CPG-fidelity corpus, Python

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `WBS.md §16 CMP-CORP-CPG-{java,python,js,go,ruby,php}` — verbatim Purpose + AC-CORP-CPG-*a/b
- `SDD.md §10 CMP-CP-06` — CPG-fidelity gate harness consumer
- `SDD.md §11` — Stage A (Python) gating constraint
- `SDD.md §12` — corpora as work packages
- `docs/cross-cutting/DOC-STAGING.md §3` — gate criteria thresholds (per CLAR-CORP-02)
- `docs/cross-cutting/DOC-INV.md §8` — INV-6 / per-language honesty
- `WBS.md §17 CLAR-CORP-02` — RESOLVED 2026-05-23: parse ≥ 99.5%, call-edge precision ≥ 90%, recall ≥ 85%, PDG dependence-edge recall ≥ 80%
- `.claude/commands/corpus-agent.md` — Corpus Curator briefing
- `.claude/rules/04-staging.md`, `.claude/rules/01-invariants.md §INV-6`

This document is the **build specification** for the Python CPG-fidelity corpus consumed by `CMP-CP-06`. Python is a **Stage A** language; this corpus must be DONE before Python enters the Algorithm 2 benchmark (`AC-CORE-01b`). INV-6 is the per-language honesty invariant: a language failing the gate is reported `front-end-blocked`, never as a recall failure.

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-CORP-CPG-python` |
| Subsystem | Corpora (`WBS.md §16`) |
| Artifact type | **Data** — labelled corpus + ground-truth extraction pipeline (not code) |
| Language under test | **Python** (3.10 baseline; per-source minor version recorded in `corpus.lock`) |
| Staging | Stage A — must precede Python's entry into `CMP-CP-06` / Algorithm 2 |
| Depends-On | **none** (`WBS.md §20`) — Wave-1 leaf |
| Owner | **DEFERRED** via `CLAR-OWNER-01` (Corpus Curator role; `/corpus-agent`) |
| INV-* touched | **INV-6** — provides the per-language fidelity evaluation set so a failing front-end is reported `front-end-blocked`, not as a recall failure. |
| Consumer | `CMP-CP-06` (CPG-fidelity gate harness) via `.github/workflows/stage-gate.yml` job `cpg-fidelity` |

---

## 2. Mandate

**Verbatim WBS `Purpose:` (`WBS.md §16 CMP-CORP-CPG-{java,python,js,go,ruby,php}`):**

> Per-language fidelity corpus with ground-truth ASTs, CFGs, and call-edges. One corpus per language; six total.

**Operational role.** For Python, this corpus answers: *does the v3.2 front-end (Joern Pythonsrc + downstream call-graph resolution) recover the AST, CFG, call-graph, and PDG of representative Python programs with enough fidelity that Algorithm 2 recall claims are meaningful?* Python's dynamic typing makes call-graph construction *fundamentally over-approximate* — the ground-truth methodology therefore distinguishes **statically-resolvable** call edges (`AC-CORP-CPG-python-a` precision/recall reporting domain) from **dynamic-dispatch** sites (which `CMP-SNAP-03 CW-DETECT` routes to the degraded path; out of scope for this corpus's call-graph metrics).

The corpus pairs each program with ground-truth AST / CFG / call-edge / PDG-dependence-edge annotations derived by an independent, documented methodology (`§3.4`). The CLAR-CORP-02 thresholds (parse ≥ 99.5%, call-edge precision ≥ 90%, recall ≥ 85%, PDG dependence-edge recall ≥ 80%) determine `GATE-PASS` / `GATE-FAIL`.

Until the gate passes for Python, the `(class, python)` pairs in Stage A's core promotion ship as `front-end-blocked`, never as a recall failure (INV-6).

---

## 3. Interface contract (corpus layout + manifest schema)

### 3.1 Directory layout

```
tests/corpora/cpg_fidelity/python/
├── corpus.lock                          # the manifest (see §3.2)
├── README.md                            # ground-truth-methodology document (see §3.4)
├── LICENSES.md                          # per-source license attribution (see §7)
├── programs/
│   ├── 0001-flask-microservice/
│   │   ├── source/                      # the program source tree (single Python package/app)
│   │   ├── ground_truth/
│   │   │   ├── ast.json                 # cpython `ast` module serialization per file
│   │   │   ├── cfg.json                 # per-function CFG (nodes + edges)
│   │   │   ├── callgraph.json           # call edges + per-edge {static, dynamic} tag
│   │   │   └── pdg.json                 # PDG dependence edges
│   │   ├── provenance.yaml              # source URL + commit sha + sha256 + python minor version
│   │   └── extraction.yaml              # exact tool versions used (see §3.4)
│   ├── 0002-...
│   └── ...
└── pipeline/
    ├── extract_ground_truth.py          # the (versioned) extraction script (see §3.4)
    └── build_lock.py                    # emits corpus.lock
```

### 3.2 `corpus.lock` manifest schema (YAML)

```yaml
corpus_id: CMP-CORP-CPG-python
corpus_version: 1.0.0                    # semver; bumped on any program add/remove/re-extract
corpus_digest: sha256:...
language: python
language_level: "3.10"                   # baseline minor version
built_at: 2026-MM-DDTHH:MM:SSZ
ground_truth_method: |
  AST: cpython 3.10 `ast` module; canonical serialization with stable field ordering.
  CFG: scalpel 1.0 `cfg_builder.CFG` per top-level function/method.
  Call graph: Pyan3 over the source tree (assignment-based call resolution) +
              second pass with Pysa 0.0.301 / Pyre over the same tree to recover
              type-informed edges. UNION of edges tagged with their provenance
              (pyan-only, pyre-only, both). Sites that neither tool can resolve
              are tagged `dynamic` and EXCLUDED from precision/recall.
  PDG dependence edges: scalpel SDG over the AST.
  See README.md §3 for exact tool invocations + dispute-resolution protocol.

programs:
  - id: 0001-flask-microservice
    source_url: https://github.com/<org>/<repo>
    commit_sha: <40-char hex>
    sha256_source_tree: <sha256 of source/>
    sha256_ground_truth: <sha256 of ground_truth/>
    license: BSD-3-Clause
    loc: 2400
    construct_coverage:
      - dynamic-dispatch                 # call sites tagged `dynamic` (excluded; just measured)
      - decorators
      - async-await
      - type-hints
      - duck-typing-callsite
    extraction_tools:
      python: "3.10.13"
      scalpel: "1.0.4"
      pyan3: "1.2.0"
      pyre: "0.0.301"
  - id: 0002-...
```

**Required invariants on `corpus.lock`:**

1. Every program has `sha256_source_tree`, `sha256_ground_truth`, `source_url`, `commit_sha`, `license`.
2. The `construct_coverage` tag union (`§4.3`) is **covered**.
3. The corpus carries programs with **both** `type-hints` and `duck-typing-callsite` tags to expose how the front-end behaves with and without static type signals.
4. `extraction_tools` versions are pinned (no `latest`).
5. Programs that target Python 2 are forbidden (out of scope for v3.2).

### 3.3 Per-program `extraction.yaml`

```yaml
extracted_by: <reviewer-id> | "pipeline"
extracted_at: 2026-MM-DDTHH:MM:SSZ
tool_versions: { python: ..., scalpel: ..., pyan3: ..., pyre: ... }
known_limitations: |
  Pyan3's assignment-based resolution cannot see runtime-monkey-patching.
  Pyre infers via type stubs; missing stubs degrade precision. The gate
  harness EXCLUDES `dynamic`-tagged call sites from precision/recall.
review_status: pipeline | second-pass
```

### 3.4 Ground-truth methodology (`README.md`)

`README.md` MUST document, with reproducible command lines:

1. **AST extraction.** cpython 3.10 `ast.parse(...)` followed by canonical serialization with stable field ordering and source-position preservation.
2. **CFG extraction.** scalpel 1.0.4 `cfg_builder.CFG` per `FunctionDef`/`AsyncFunctionDef`/`Lambda`. Class methods CFG'd per-method, not per-class.
3. **Call-graph extraction.** Two independent tools — Pyan3 (assignment-based) and Pyre (type-informed) — run over the same source. The UNION of resolved edges is the ground truth. Each edge carries provenance (`pyan-only`, `pyre-only`, `both`). Sites that **neither** tool resolves are tagged `dynamic` (e.g., `getattr(obj, name)()`, dict-dispatch); these are reported separately and EXCLUDED from the gate's precision / recall numerator and denominator. `CMP-SNAP-03 CW-DETECT` is the consumer that owns `dynamic` sites; this corpus does not measure call-graph fidelity on them.
4. **PDG dependence edges.** scalpel SDG over the AST; control + data dependence edges.
5. **Dual-review protocol.** Manual edits to ground-truth (e.g., a confirmed Pyre miss) require `review_status: second-pass`; the diff is recorded.
6. **Forbidden sources.** Programs derived from Joern's own pythonsrc test fixtures are forbidden; record refusals in `LICENSES.md`.

A corpus is **not DONE** without this document populated. No "vendored mystery zip".

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| Python programs (apps, libraries) | Public OSS repos with permissive licenses | Source URL + commit sha + sha256; license recorded; Python 3.x only |
| Ground-truth extraction toolchain | cpython 3.10 + scalpel 1.0.4 + Pyan3 1.2.0 + Pyre 0.0.301 | All pinned in `extraction.yaml` and `README.md`; bumps require new corpus version |

### 4.2 Outputs

| Output | Where | Consumer |
|---|---|---|
| `tests/corpora/cpg_fidelity/python/` + `corpus.lock` | Repo + (optionally) object store | `CMP-CP-06` gate harness |
| `corpus_version` (semver) | `corpus.lock` | Gate result reports (`tests/results/cpg_fidelity/python/latest.json`) |
| `corpus_digest` (sha256) | `corpus.lock` | Gate result reports |

### 4.3 Required Python construct coverage tags

| Tag | What it stresses |
|---|---|
| `dynamic-dispatch` | `getattr`, dict-of-functions, runtime monkey-patching — call sites tagged `dynamic` (measured, excluded from precision/recall) |
| `decorators` | Functions wrapped with one or more decorators (call-graph edge correctness through `functools.wraps`) |
| `async-await` | `async def` / `await` — CFG correctness across coroutine suspension |
| `type-hints` | Programs with PEP 484 / 526 hints (Pyre's friendly territory) |
| `duck-typing-callsite` | Programs without type hints; tests Pyan3's assignment-based resolution alone |
| `metaclasses` | Programs using `__init_subclass__` / metaclass-driven dispatch |
| `import-star` | `from x import *` — name-resolution edge cases |
| `dataclasses-pydantic` | Auto-generated `__init__`s and validators — front-end recovery of synthetic methods |
| `notebooks-converted` | `.py` files derived from `.ipynb` (irregular structure) — parse-success stressor |
| `c-extension-wrapper` | Programs that call into C extensions via `ctypes` / `cffi` — call edges that necessarily terminate at the FFI boundary |

A corpus that lacks any tag is incomplete; `pipeline/build_lock.py` refuses to emit.

---

## 5. Invariants touched

| Invariant | How `CMP-CORP-CPG-python` discharges it | Test |
|---|---|---|
| **INV-6** | Provides the labelled fidelity evaluation set against which the v3.2 Python front-end is judged. A failing front-end here yields `front-end-blocked`, never a recall failure (`AC-CP-06a`). | `TST-AC-CP-06-python-parse`, `TST-AC-CP-06-python-call-prec`, `TST-AC-CP-06-python-call-rec`, `TST-AC-CP-06-python-pdg-rec` `[FORTHCOMING]`. |

---

## 6. Dependency contract

`CMP-CORP-CPG-python` is a leaf node in the dependency DAG (`WBS.md §20`). It assumes:

- `CMP-CP-06`'s gate harness reads `corpus.lock`, runs the v3.2 Python front-end on each program's `source/`, and compares the produced CPG against `ground_truth/`.
- The comparison metric: per-file parse success, edge-set precision/recall on `(caller, callee, line)` triples (with `dynamic`-tagged edges excluded), and dependence-edge recall on PDG edges.

Downstream consumers: `CMP-CP-06` (Python gate), `CMP-CORE-01` Algorithm 2 benchmark.

---

## 7. Failure modes and error contracts

| Failure | Detection | Required response |
|---|---|---|
| **Reproducibility break** — a program lacks `source_url` + `commit_sha` + `sha256` | `pipeline/build_lock.py` refuses to emit `corpus.lock` | Re-source with deterministic provenance. |
| **Python 2 contamination** — a program targets Python 2 | Build-time check (`requires-python` parse + AST `print_function` heuristic) | Reject the program. |
| **Ground-truth tool drift** — `extraction.yaml` versions ≠ `README.md` pinned versions | Build-time check | Re-extract under pinned versions; bump `corpus_version`. |
| **Missing construct tag** — a tag from `§4.3` has zero programs | Build-time check | Reject the build; add at least one program for the missing tag. |
| **License incompatibility** — license not on allow-list (MIT, Apache-2.0, BSD-2/3, MPL-2.0, PSF) | Build-time check | Reject the program; record refusal in `LICENSES.md`. |
| **`corpus_digest` drift** | CI digest check | Hard CI fail. |
| **Ground-truth methodology drift** — `README.md` silent on a step or contradicts `extraction.yaml` | Methodology review | Block the build. |
| **Joern-pythonsrc-fixture contamination** | Manual review | Reject; would bias the gate. |
| **Pyre/Pyan3 unavailable** at re-extraction time | Build-time check | Use the pinned Docker image (`docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` image registry); never fall back to "best available". |
| **Gate failure on Python front-end** — `CMP-CP-06` reports `GATE-FAIL` for Python | `.github/workflows/stage-gate.yml` | Report `front-end-blocked` per `AC-CP-06a`; do NOT shrink the corpus or relax thresholds. Front-end investment is the response. |

---

## 8. Provenance threading

| Field | Where | Threading rule |
|---|---|---|
| `corpus_version` (semver) | `corpus.lock` → gate report | Bumped on any add/remove/re-extract; matches release ledger (`AC-CORP-CPG-*b`). |
| `corpus_digest` (sha256) | `corpus.lock` → gate report | Pins the exact evaluation set. |
| Per-program `sha256_source_tree`, `sha256_ground_truth`, `commit_sha`, `license` | `corpus.lock` items | Reproducibility contract. |
| `extraction_tools` versions | per-program `extraction.yaml` | Re-extraction reproducible. |

**Must NOT touch:** `origin`, `S_version`, `env_digest`, `cpg_order_hash`, `slice_fingerprint`, or any `findings` row.

---

## 9. Acceptance criteria cross-reference

Quoted verbatim from `WBS.md §16 CMP-CORP-CPG-{java,python,js,go,ruby,php}`. All `TST-AC-CORP-CPG-python-*` are `[FORTHCOMING]`.

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-CORP-CPG-python-a** | > Corpus carries ground-truth AST/CFG/call-edge annotations and a documented annotation methodology. | `TST-AC-CORP-CPG-python-a` `[FORTHCOMING]` — asserts each program has `ground_truth/{ast,cfg,callgraph,pdg}.json`; `README.md` documents methodology per `§3.4`. |
| **AC-CORP-CPG-python-b** | > Corpus is versioned; gate thresholds are evaluated against the pinned corpus version. | `TST-AC-CORP-CPG-python-b` `[FORTHCOMING]` — asserts `corpus.lock` carries `corpus_version` + `corpus_digest`; gate report records both. |

**Consumer-facing gate tests (this corpus exists to make them runnable):**

- `TST-AC-CP-06-python-parse` `[FORTHCOMING]` — asserts parse success rate ≥ 99.5%.
- `TST-AC-CP-06-python-call-prec` `[FORTHCOMING]` — asserts call-edge precision ≥ 90% (over non-`dynamic` edges).
- `TST-AC-CP-06-python-call-rec` `[FORTHCOMING]` — asserts call-edge recall ≥ 85% (over non-`dynamic` edges).
- `TST-AC-CP-06-python-pdg-rec` `[FORTHCOMING]` — asserts PDG dependence-edge recall ≥ 80%.

Invariant tests cross-referenced:

- `TST-INV-6-CP-06 [FORTHCOMING]` — gate harness produces pass/fail per language.

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-CORP-CPG-python |
|---|---|---|---|
| `CLAR-CORP-02` | CPG-fidelity gate thresholds per language | **RESOLVED** 2026-05-23 | Python thresholds: parse ≥ 99.5%, call-edge precision ≥ 90%, recall ≥ 85%, PDG ≥ 80%. |
| `CLAR-OWNER-01` | Per-component / corpus owner | **DEFERRED** | `§1` Owner stays DEFERRED. |

**No new CLAR-CORP-* are filed by this document.** Thresholds and methodology toolchain are pinned.

---

## 11. References

- `WBS.md §16 CMP-CORP-CPG-{java,python,js,go,ruby,php}` — verbatim ACs.
- `SDD.md §10 CMP-CP-06` — consumer (gate harness).
- `SDD.md §11` — Stage A gating constraint.
- `SDD.md §12` — corpora as work packages.
- `docs/cross-cutting/DOC-STAGING.md §3` — gate criteria thresholds.
- `docs/cross-cutting/DOC-INV.md §8` — INV-6 / per-language honesty.
- `docs/components/DOC-CMP-CP-06.md` (sibling, forthcoming) — gate harness.
- `docs/components/DOC-CMP-SNAP-03.md` (sibling) — `CW-DETECT` is the consumer that owns `dynamic`-tagged sites this corpus excludes from call-graph metrics.
- `.claude/commands/corpus-agent.md` — Corpus Curator briefing.
- `WBS.md §17 CLAR-CORP-02` — gate threshold resolution.
- `.claude/rules/04-staging.md`, `.claude/rules/01-invariants.md §INV-6`.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for a Corpus Curator agent to assemble `CMP-CORP-CPG-python` and for the `CMP-CP-06` gate harness implementer to consume it. The Python gate verdict (`TST-AC-CP-06-python-*`) determines whether `(class, python)` pairs enter the Algorithm 2 benchmark — INV-6 is the load-bearing invariant.*
