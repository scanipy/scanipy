# DOC-CMP-CORP-CPG-java — CPG-fidelity corpus, Java

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `WBS.md §16 CMP-CORP-CPG-{java,python,js,go,ruby,php}` — verbatim Purpose + AC-CORP-CPG-*a/b
- `SDD.md §10 CMP-CP-06` — CPG-fidelity gate harness consumer
- `SDD.md §11` — Stage A (Java) gating constraint
- `SDD.md §12` — corpora as work packages
- `docs/cross-cutting/DOC-STAGING.md §3` — gate criteria thresholds (per CLAR-CORP-02)
- `docs/cross-cutting/DOC-INV.md §8` — INV-6 / per-language honesty
- `WBS.md §17 CLAR-CORP-02` — RESOLVED 2026-05-23: parse ≥ 99.5%, call-edge precision ≥ 90%, recall ≥ 85%, PDG dependence-edge recall ≥ 80%
- `.claude/commands/corpus-agent.md` — Corpus Curator briefing
- `.claude/rules/04-staging.md`, `.claude/rules/01-invariants.md §INV-6`

This document is the **build specification** for the Java CPG-fidelity corpus consumed by `CMP-CP-06`. Java is a **Stage A** language; this corpus must be DONE before Java enters the Algorithm 2 benchmark (`AC-CORE-01b`). INV-6 is the per-language honesty invariant: a language failing the gate is reported `front-end-blocked`, never as a recall failure.

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-CORP-CPG-java` |
| Subsystem | Corpora (`WBS.md §16`) |
| Artifact type | **Data** — labelled corpus + ground-truth extraction pipeline (not code) |
| Language under test | **Java** (SE 17 LTS baseline; per-source language level recorded in `corpus.lock`) |
| Staging | Stage A — must precede Java's entry into `CMP-CP-06` / Algorithm 2 |
| Depends-On | **none** (`WBS.md §20`) — Wave-1 leaf |
| Owner | **DEFERRED** via `CLAR-OWNER-01` (Corpus Curator role; `/corpus-agent`) |
| INV-* touched | **INV-6** — provides the per-language fidelity evaluation set so a failing front-end is reported `front-end-blocked`, not as a recall failure. |
| Consumer | `CMP-CP-06` (CPG-fidelity gate harness) via `.github/workflows/stage-gate.yml` job `cpg-fidelity` |

---

## 2. Mandate

**Verbatim WBS `Purpose:` (`WBS.md §16 CMP-CORP-CPG-{java,python,js,go,ruby,php}`):**

> Per-language fidelity corpus with ground-truth ASTs, CFGs, and call-edges. One corpus per language; six total.

**Operational role.** For Java, this corpus answers: *does the v3.2 front-end (Joern CPG with `c2cpg`-equivalent javasrc / jssrc Java pipeline) recover the AST, CFG, and call-graph of representative Java programs with enough fidelity that Algorithm 2 recall claims are meaningful?* The corpus pairs each program with a **ground-truth AST / CFG / call-edge / PDG-dependence-edge** annotation derived by an independent, documented methodology (`§3.4`). The gate harness (`CMP-CP-06`) runs the v3.2 front-end on each program, compares the produced CPG against the ground truth, and emits per-metric numbers. The CLAR-CORP-02 thresholds (parse ≥ 99.5%, call-edge precision ≥ 90%, recall ≥ 85%, PDG dependence-edge recall ≥ 80%) determine `GATE-PASS` / `GATE-FAIL`.

Until the gate passes for Java, the `(class, java)` pairs in Stage A's core promotion (`injection`, `path-traversal`, `ssrf`, `deserialization`) ship as `front-end-blocked`, never as a recall failure (INV-6).

---

## 3. Interface contract (corpus layout + manifest schema)

A corpus is a **data artifact**; its "interface" is the on-disk layout and manifest schema.

### 3.1 Directory layout

```
tests/corpora/cpg_fidelity/java/
├── corpus.lock                          # the manifest (see §3.2)
├── README.md                            # ground-truth-methodology document (see §3.4)
├── LICENSES.md                          # per-source license attribution (see §7)
├── programs/
│   ├── 0001-spring-petclinic-trimmed/
│   │   ├── source/                      # the program source tree (single Java module/project)
│   │   ├── ground_truth/
│   │   │   ├── ast.json                 # serialized AST per file
│   │   │   ├── cfg.json                 # per-method CFG (nodes + edges)
│   │   │   ├── callgraph.json           # call edges: { caller_method, callee_method, line }
│   │   │   └── pdg.json                 # PDG dependence edges
│   │   ├── provenance.yaml              # source URL + commit sha + sha256 + language level
│   │   └── extraction.yaml              # exact tool versions used (see §3.4)
│   ├── 0002-...
│   └── ...
└── pipeline/
    ├── extract_ground_truth.py          # the (versioned) extraction script (see §3.4)
    └── build_lock.py                    # emits corpus.lock
```

### 3.2 `corpus.lock` manifest schema (YAML)

```yaml
corpus_id: CMP-CORP-CPG-java
corpus_version: 1.0.0                    # semver; bumped on any program add/remove/re-extract
corpus_digest: sha256:...                # sha256 of canonical serialization of this file
language: java
language_level: 17                       # Java SE level baseline (per CLAR-FE notes)
built_at: 2026-MM-DDTHH:MM:SSZ
ground_truth_method: |
  AST: javac --print AST via `com.sun.source.tree` (JDK 17 compiler API).
  CFG: Soot 4.4 (jimple BodyTransformer with `UnitGraph`).
  Call graph: WALA 1.6 with 0-CFA points-to + class-hierarchy-analysis fallback for
              reflection sites; reflection sites recorded as `over-approximate-edges`.
  PDG dependence edges: Soot SDG (`InfoflowSlicer`) over jimple.
  See README.md §3 for exact tool invocations + dispute-resolution protocol.

programs:                                # one entry per programs/<id>/
  - id: 0001-spring-petclinic-trimmed
    source_url: https://github.com/spring-projects/spring-petclinic
    commit_sha: <40-char hex>
    sha256_source_tree: <sha256 of source/>
    sha256_ground_truth: <sha256 of ground_truth/>
    license: Apache-2.0
    loc: 5400                            # lines of Java source
    construct_coverage:                  # discriminator tags — see §4.3
      - interface-dispatch
      - generics
      - lambdas
      - spring-di
    extraction_tools:
      jdk: "openjdk-17.0.10"
      soot: "4.4.1"
      wala: "1.6.5"
  - id: 0002-...
```

**Required invariants on `corpus.lock`:**

1. Every program has `sha256_source_tree`, `sha256_ground_truth`, `source_url`, `commit_sha`, `license`.
2. The `construct_coverage` tag union (`§4.3`) is **covered** — every required Java construct tag has at least one program tagged with it.
3. The corpus is **balanced**: parse-success measurement requires programs that include intentionally hard-to-parse files (annotation-heavy, recent language features, generated code); ≥ 10% of programs MUST carry such a tag (`§4.3`).
4. `extraction_tools` versions are pinned (no `latest`).

### 3.3 Per-program `extraction.yaml` schema

```yaml
extracted_by: <reviewer-id> | "pipeline"
extracted_at: 2026-MM-DDTHH:MM:SSZ
tool_versions: { jdk: ..., soot: ..., wala: ... }
known_limitations: |
  WALA's reflection handling is over-approximate; reflection edges tagged
  `over-approximate-edges` in callgraph.json. The gate harness MUST exclude
  over-approximate edges from precision counting but INCLUDE them in recall.
review_status: pipeline | second-pass    # second-pass required for programs with manual edits
```

### 3.4 Ground-truth methodology (`README.md`)

`README.md` MUST document, with reproducible command lines:

1. **AST extraction.** `javac --print` via JDK 17 Compiler Tree API. The canonical AST is the `com.sun.source.tree.Tree` traversal serialized with stable child ordering.
2. **CFG extraction.** Soot 4.4.1 in `jimple` mode; `BriefUnitGraph` for forward CFG; per-method one CFG per `SootMethod`.
3. **Call-graph extraction.** WALA 1.6.5 with `nCFAContextSelector(0)` (0-CFA) + CHA fallback. Reflection sites resolved over-approximately; edges tagged `over-approximate-edges` (excluded from precision counting per §3.3).
4. **PDG dependence edges.** Soot's `InfoflowSlicer` over jimple; control + data dependence edges.
5. **Dual-review protocol.** Programs that include manual edits to the ground-truth (e.g., to correct an obvious WALA omission) require `review_status: second-pass`. The reviewer's identity and the diff are recorded in the program directory.
6. **Forbidden sources.** Programs whose source is itself derived from Joern's own test fixtures are forbidden (would bias the gate); record refusals in `LICENSES.md`.

A corpus is **not DONE** without this document populated. No "vendored mystery zip".

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| Java programs (full repos or curated slices) | Public OSS repos with permissive licenses | Source URL + commit sha + sha256; license recorded |
| Ground-truth extraction toolchain | JDK 17 + Soot 4.4.1 + WALA 1.6.5 | All pinned in `extraction.yaml` and `README.md`; bumps require new corpus version |

### 4.2 Outputs

| Output | Where | Consumer |
|---|---|---|
| `tests/corpora/cpg_fidelity/java/` + `corpus.lock` | Repo (lock in repo; large artifacts may live in object store with sha256-pinned URIs) | `CMP-CP-06` gate harness (`.github/workflows/stage-gate.yml`) |
| `corpus_version` (semver) | `corpus.lock` | Gate result reports (`tests/results/cpg_fidelity/java/latest.json`) |
| `corpus_digest` (sha256) | `corpus.lock` | Gate result reports — pinned per CI run |

### 4.3 Required Java construct coverage tags

Every tag below MUST be carried by at least one program in the corpus. The tag union is the "is the front-end being meaningfully evaluated?" check.

| Tag | What it stresses |
|---|---|
| `interface-dispatch` | Polymorphic call edges through interface declarations |
| `inheritance-chain` | Virtual dispatch over class hierarchy with override |
| `generics` | Type-erasure handling in the CPG; bound resolution |
| `lambdas` | `LambdaMetafactory` invokedynamic — call edges through `INVOKEDYNAMIC` |
| `method-references` | `::` references in call-graph nodes |
| `inner-class` | Nested / static / anonymous inner-class enclosing-method edges |
| `try-with-resources` | CFG correctness through `try` blocks + `Throwable.addSuppressed` |
| `spring-di` | Constructor / setter injection (call edges Spring resolves at runtime) |
| `annotation-heavy` | Programs whose parse cost is dominated by annotation processors |
| `recent-language` | `record`, `sealed`, pattern-matching `switch` (JDK 17 features) — parse-success stressor |
| `generated-code` | Programs containing auto-generated source (Lombok, immutables) — at least 10% of programs |

A corpus that lacks any tag is incomplete; `pipeline/build_lock.py` refuses to emit.

---

## 5. Invariants touched

| Invariant | How `CMP-CORP-CPG-java` discharges it | Test |
|---|---|---|
| **INV-6** | Provides the labelled fidelity evaluation set against which the v3.2 Java front-end is judged. A failing front-end here yields `front-end-blocked`, never a recall failure (`AC-CP-06a`). The gate criterion is the consumer of this corpus. | `TST-AC-CP-06-java-parse`, `TST-AC-CP-06-java-call-prec`, `TST-AC-CP-06-java-call-rec`, `TST-AC-CP-06-java-pdg-rec` `[FORTHCOMING]`. |

---

## 6. Dependency contract

`CMP-CORP-CPG-java` is a leaf node in the dependency DAG (`WBS.md §20`). It assumes:

- `CMP-CP-06`'s gate harness reads `corpus.lock`, runs the v3.2 front-end on each program's `source/`, and compares the produced CPG against `ground_truth/`.
- The comparison metric (per `DOC-STAGING.md §3` and `CLAR-CORP-02`): per-file parse success, edge-set precision/recall using exact-match on `(caller, callee, line)` triples for call edges (with `over-approximate-edges` excluded from precision), and dependence-edge recall on PDG edges.

Downstream consumers: `CMP-CP-06` (Java gate), `CMP-CORE-01` Algorithm 2 benchmark (consumes the gate output; only gate-passing pairs enter benchmarking — RULE-7).

---

## 7. Failure modes and error contracts

| Failure | Detection | Required response |
|---|---|---|
| **Reproducibility break** — a program lacks `source_url` + `commit_sha` + `sha256` | `pipeline/build_lock.py` refuses to emit `corpus.lock` | Re-source with deterministic provenance. No exception. |
| **Ground-truth tool drift** — `extraction.yaml` tool versions differ between programs and `README.md` pinned versions | Build-time check in `pipeline/build_lock.py` | Re-extract under the pinned versions; bump `corpus_version`. |
| **Missing construct tag** — a tag from `§4.3` has zero programs | Build-time check | Reject the build; add at least one program for the missing tag. |
| **License incompatibility** — program license not on allow-list (MIT, Apache-2.0, BSD-2/3, MPL-2.0) | Build-time check | Reject the program; record refusal in `LICENSES.md`. GPL/AGPL requires explicit CTO approval. |
| **`corpus_digest` drift** | CI digest check | Hard CI fail; rebuild + re-pin. |
| **Ground-truth methodology drift** — `README.md` is silent on a step or contradicts `extraction.yaml` | `README.md` review during corpus build | Block the build; document the methodology fully. No corpus is DONE without it. |
| **Joern-fixture contamination** — a program is derived from Joern's own test fixtures | Manual review during methodology pass | Reject the program; this would bias the gate. |
| **Gate failure on the Java front-end** — `CMP-CP-06` reports `GATE-FAIL` for Java | `.github/workflows/stage-gate.yml` | Report `front-end-blocked` per `AC-CP-06a`; do NOT shrink the corpus or relax thresholds to make it pass. Front-end investment is the required response (`R-2` mitigation in `SDD.md §13`). |

---

## 8. Provenance threading

A corpus does not write to `findings`. Its provenance fields feed into the gate report:

| Field | Where | Threading rule |
|---|---|---|
| `corpus_version` (semver) | `corpus.lock` → `tests/results/cpg_fidelity/java/latest.json` | Bumped on any add/remove/re-extract; matches release ledger (`AC-CORP-CPG-*b`). |
| `corpus_digest` (sha256) | `corpus.lock` → gate report | Pins the exact evaluation set; an INV-6 gate verdict traceable back to `corpus_digest`. |
| Per-program `sha256_source_tree`, `sha256_ground_truth`, `commit_sha`, `license` | `corpus.lock` items | Reproducibility contract. |
| `extraction_tools` versions | per-program `extraction.yaml` | Re-running extraction with the same versions reproduces the same ground truth. |

**Must NOT touch:** `origin`, `S_version`, `env_digest`, `cpg_order_hash`, `slice_fingerprint`, or any `findings` row.

---

## 9. Acceptance criteria cross-reference

Quoted verbatim from `WBS.md §16 CMP-CORP-CPG-{java,python,js,go,ruby,php}`. All `TST-AC-CORP-CPG-java-*` are `[FORTHCOMING]`.

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-CORP-CPG-java-a** | > Corpus carries ground-truth AST/CFG/call-edge annotations and a documented annotation methodology. | `TST-AC-CORP-CPG-java-a` `[FORTHCOMING]` — asserts each program has `ground_truth/{ast,cfg,callgraph,pdg}.json`; `README.md` documents methodology per `§3.4`. |
| **AC-CORP-CPG-java-b** | > Corpus is versioned; gate thresholds are evaluated against the pinned corpus version. | `TST-AC-CORP-CPG-java-b` `[FORTHCOMING]` — asserts `corpus.lock` carries `corpus_version` (semver) and `corpus_digest`; gate report records both. |

**Consumer-facing gate tests (this corpus exists to make them runnable):**

- `TST-AC-CP-06-java-parse` `[FORTHCOMING]` — asserts parse success rate ≥ 99.5% over the corpus (per CLAR-CORP-02).
- `TST-AC-CP-06-java-call-prec` `[FORTHCOMING]` — asserts call-edge precision ≥ 90%.
- `TST-AC-CP-06-java-call-rec` `[FORTHCOMING]` — asserts call-edge recall ≥ 85%.
- `TST-AC-CP-06-java-pdg-rec` `[FORTHCOMING]` — asserts PDG dependence-edge recall ≥ 80%.

Invariant tests cross-referenced:

- `TST-INV-6-CP-06 [FORTHCOMING]` — gate harness produces pass/fail per language and refuses to report a fail as a recall number (this corpus is the input for Java's verdict).

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-CORP-CPG-java |
|---|---|---|---|
| `CLAR-CORP-02` | CPG-fidelity gate thresholds per language | **RESOLVED** 2026-05-23 | Java thresholds: parse ≥ 99.5%, call-edge precision ≥ 90%, recall ≥ 85%, PDG ≥ 80%. |
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
- `.claude/commands/corpus-agent.md` — Corpus Curator briefing.
- `WBS.md §17 CLAR-CORP-02` — gate threshold resolution.
- `.claude/rules/04-staging.md`, `.claude/rules/01-invariants.md §INV-6`.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for a Corpus Curator agent to assemble `CMP-CORP-CPG-java` and for the `CMP-CP-06` gate harness implementer to consume it. The Java gate verdict (`TST-AC-CP-06-java-*`) determines whether `(class, java)` pairs enter the Algorithm 2 benchmark — INV-6 is the load-bearing invariant.*
