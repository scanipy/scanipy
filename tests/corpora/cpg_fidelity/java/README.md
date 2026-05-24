# Java CPG-fidelity corpus — CMP-CORP-CPG-java (ground-truth methodology)

This corpus is the **per-language fidelity evaluation set** consumed by the
CPG-fidelity gate `CMP-CP-06` for **Java** (a Stage A language). The gate runs the
v3.2 front-end on each program's `source/`, compares the produced CPG against
`ground_truth/`, and emits per-metric numbers scored against the CLAR-CORP-02
thresholds (parse ≥ 99.5%, call-edge precision ≥ 90%, recall ≥ 85%, PDG
dependence-edge recall ≥ 80%). A language that fails is reported
**`front-end-blocked`**, never as a recall failure (INV-6). This document is the
ground-truth methodology mandated by `DOC-CMP-CORP-CPG-java §3.4`; the corpus is
**not DONE without it**.

## Status — v0.1.0 (NOT the gate-ready release bar)

This is a **provisional, SYNTHESIZED scaffolding** build. It delivers:

- 11 hand-authored, self-contained Java programs, one (or more) per **required
  construct tag** (`DOC §4.3`) — all 11 tags covered.
- A reproducible, content-addressed `corpus.lock` (`corpus_version` +
  `corpus_digest`, digest excludes volatile fields) built by
  `pipeline/build_lock.py` — identical scheme to the reflection corpus.
- Four ground-truth artifacts per program (`ast.json`, `cfg.json`,
  `callgraph.json`, `pdg.json`) plus per-program `provenance.yaml` +
  `extraction.yaml`.

It deliberately does **NOT** yet meet the AC bar for gate use:

| Dimension | This build (v0.1.0) | Gate-ready (v1.0.0) bar |
|---|---|---|
| Ground-truth extraction | BY INSPECTION of tiny programs (parse-success javac-verified) | DOC-pinned Soot 4.4.1 + WALA 1.6.5 + JDK 17 (CLAR-CORP-07-java-tooling) |
| JDK level | 21 (CLAR-CORP-08-java-jdk) | 17 baseline |
| Sourced real-repo programs | 0 (all SYNTHESIZED) | a real-OSS sourcing campaign (CLAR-CORP-09-java-sourcing) |
| Per-language program count N | 11 (one per construct) | unpinned for CPG corpora (CLAR-CORP-09-java-sourcing) |
| generated-code balance (DOC §3.3 ≥ 10%) | 1/11 = 9% (WARN, CLAR-CORP-10-java-generated-balance) | ≥ 10% |

`CMP-CP-06` MUST NOT be declared `GATE-PASS` for Java on this v0.1.0 corpus: the
ground truth was not produced by the pinned tools, and the call-graph/CFG/PDG edges
are author-asserted, not Soot/WALA-extracted. See the CLAR rows below.

## SOURCED vs SYNTHESIZED

- **SYNTHESIZED (all 11 programs).** Each `programs/<id>/source/*.java` is a tiny
  closed program authored for this corpus (`license: Apache-2.0`,
  `commit_sha: synthetic`, `synthetic: true`). Parse-success is empirically verified
  with `javac` (see below); all four ground-truth artifacts are derived **by
  inspection** of the source. This is sound for these tiny programs but is **not**
  the pinned-tool extraction the DOC mandates.
- **SOURCED (none yet).** No real OSS repository slices are included in v0.1.0. The
  DOC layout reserves `source_url` + `commit_sha` per program for real sources; the
  sourcing campaign is `CLAR-CORP-09-java-sourcing`. The `spring-petclinic-trimmed` example named
  in `DOC §3.2` is illustrative, not shipped here.

## Ground-truth methodology (per DOC §3.4)

1. **AST.** Each program is parsed with `javac -source 17 -target 17` (JDK 21);
   parse-success is the binary "did javac accept the file". `ast.json` records the
   javac-observable type declarations and method signatures (a `javac -Xprint`
   /`com.sun.source.tree` traversal summary), with `parse_success: true`.
2. **CFG.** `cfg.json` records a per-method intraprocedural control-flow graph
   (statement nodes + successor edges), modelled by inspection in the style of a
   Soot `BriefUnitGraph`. Straight-line methods have node_count − 1 edges; branches
   and loops carry their fan-out/back-edges explicitly.
3. **Call graph.** `callgraph.json` records `(caller_method, callee_method, line)`
   triples. Virtual/interface calls are resolved by class-hierarchy analysis (CHA);
   where a 0-CFA-style merge or a reflective container would over-approximate
   (lambda `invokedynamic` merges, Spring `@Autowired` wiring), the edge carries
   `over_approximate: true`. JDK-library callees carry `library: true`.
   **Scoring contract (DOC §3.3):** the gate harness excludes `over_approximate`
   edges from precision counting but includes them in recall; it scopes in-corpus
   precision/recall to `library: false` edges so JDK-modelling differences do not
   penalise the front-end.
4. **PDG dependence edges.** `pdg.json` records intraprocedural data- and
   control-dependence edges by inspection (Soot `InfoflowSlicer` style): a def → each
   use of the same local/param (`type: data`), and a predicate → each guarded
   statement (`type: control`).
5. **Review protocol.** All v0.1.0 ground truth is `review_status: pipeline`
   (single author). The dual-review `second-pass` protocol applies to the v1.0.0
   Soot/WALA re-extraction (CLAR-CORP-07-java-tooling).
6. **Forbidden sources.** Programs derived from Joern's own test fixtures are
   forbidden (would bias the gate). None are included; all sources are original.

## Reproducing the lock

```
cd tests/corpora/cpg_fidelity/java
python3 pipeline/build_lock.py --write    # write corpus.lock
python3 pipeline/build_lock.py --check     # CI: fail on digest drift
```

`build_lock.py` refuses to emit on any DOC §7 HARD failure (missing
source_url/commit_sha/license, bad license, missing/invalid ground_truth/*.json).
Construct-tag and generated-code-balance shortfalls are reported as WARN for v0.1.0
and become hard refusals at the v1.0.0 bar.

Re-verify parse-success for every program:

```
for f in programs/*/source/*.java; do javac -source 17 -target 17 -d /tmp/cpgout "$f"; done
```

## Open CLAR items (filed in WBS.md §17)

- **CLAR-CORP-07-java-tooling** — Soot 4.4.1 / WALA 1.6.5 unavailable in the sandbox; blocks
  pinned-tool ground-truth extraction. v0.1.0 ground truth is by-inspection.
- **CLAR-CORP-08-java-jdk** — JDK 17 baseline drift (sandbox has JDK 21); affects which
  language features compile and the pinned `extraction_tools.jdk`.
- **CLAR-CORP-09-java-sourcing** — per-language minimum program count N for CPG-fidelity corpora
  is unpinned (CLAR-CORP-01 covered only the reflection corpus), and the real-OSS
  sourcing campaign for SOURCED programs is unscoped.
- **CLAR-CORP-10-java-generated-balance** — generated-code balance (DOC §3.3 ≥ 10%) sits at 9% in v0.1.0;
  confirm the threshold denominator and target for the CPG corpus.
