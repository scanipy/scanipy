# DOC-CMP-CORP-REFAC-01 — Seeded-refactor set

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `WBS.md §16 CMP-CORP-REFAC-01` — Purpose, AC-CORP-REFAC-01a/b verbatim
- `SDD.md §12` — corpora are first-class deliverables, not assumed inputs
- `SDD.md §6 CMP-CORE-02` (AC-CORE-02a, AC-CORE-02b) — the seeded-refactor set is the falsifier corpus for Algorithm 3
- `PLAN.md §"Algorithm 3 — Refactor-stable finding fingerprint"` — five named normalization passes
- `docs/cross-cutting/DOC-ALGS.md §4` — Algorithm 3 owner: `CMP-CORE-02`
- `docs/cross-cutting/DOC-INV.md §INV-5` — `fingerprint_class` semantics
- `docs/cross-cutting/DOC-STAGING.md` — Stage A corpus pre-requisite
- `WBS.md §17 CLAR-PARAM-03` (RESOLVED — `weak`-fallback publish threshold 5%)
- `.claude/commands/corpus-agent.md` — corpus DONE requires versioning
- `.claude/rules/00-global.md`, `.claude/rules/01-invariants.md §INV-5`

This document is the **implementation contract** for `CMP-CORP-REFAC-01`. The corpus is the **falsifier** that anchors `AC-CORE-02a` (fingerprint invariance) and `AC-CORE-02b` (fingerprint must flip on a genuine fix / aliasing-changing extract). Without this corpus, no claim about `CMP-CORE-02` (Algorithm 3) is testable.

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-CORP-REFAC-01` |
| Subsystem | Cross-cutting corpora (`WBS.md §16`) |
| Staging | Stage A — **must precede `TST-AC-CORE-02a/b`** (`WBS.md §16`) |
| Depends-On | **none** (`WBS.md §20`) — Wave-1 component |
| Owner | **DEFERRED** via `CLAR-OWNER-01`. Curated by the Corpus Curator role (`.claude/commands/corpus-agent.md`). |
| INV-* touched | **INV-5 anchor** — discharges `AC-CORE-02a/b` (fingerprint invariance under named refactors + flip on genuine fix). |
| Falsifier role | Owns the ground-truth labels (`should-stay`, `should-flip`) for Algorithm 3 invariance proofs. |
| Storage | `tests/corpora/refactor/` (`.claude/commands/corpus-agent.md`) |

---

## 2. Mandate

**Verbatim WBS `Purpose:` (`WBS.md §16 CMP-CORP-REFAC-01`):**

> 50 seeded findings paired with each named refactor (α-renaming, formatting, independent reordering, pure extract, file-move / package-rename) and with a genuine fix and an aliasing-changing extract.

**Operational role.** `CMP-CORP-REFAC-01` exists because Algorithm 3 (slice fingerprint) carries a **per-refactor invariance proof obligation**: the fingerprint MUST remain stable under each of the five named normalization passes, and MUST flip under the two "should-flip" cases. The seeded-refactor set is the empirical falsifier for these obligations. Every pair `(seed_finding, refactor)` carries a binary ground-truth label `should-stay | should-flip`, evaluated against the implementation's `slice_fingerprint` output. A single label-disagreement is a release blocker for `CMP-CORE-02` (`AC-CORE-02a/b`).

The corpus is consumed exclusively by `TST-AC-CORE-02a` (`[FALSIFIER]` — invariance under each named refactor on 50 seeded findings) and `TST-AC-CORE-02b` (`[FALSIFIER]` — fingerprint flips on a genuine fix and on an aliasing-changing extract). It does not feed Algorithm 2 benchmarking and is not used by Attestor pipelines.

---

## 3. Interface contract

The corpus is a versioned on-disk artifact, not a callable service.

```
tests/corpora/refactor/
├── corpus.lock                          # version manifest; SHA-256 over all seed pairs
├── seeds/
│   ├── seed-001/
│   │   ├── before/                      # source @ baseline (the seeded vuln)
│   │   ├── after/                       # source after refactor
│   │   └── meta.yaml
│   ├── seed-002/
│   └── ...                              # 50 × 7 = 350 (seed, refactor) pairs
└── annotation-methodology.md            # how ground-truth was generated
```

### 3.1 Per-seed manifest (`meta.yaml`)

```yaml
seed_id: "seed-001"
seed_finding:
  class: "injection"                     # one of: injection | path-traversal | ssrf | deserialization
  language: "java"                       # stage-A only: java | python
  sink_file: "src/main/java/Service.java"
  sink_line: 42
  description: "SQL injection via getParameter() concatenation"
refactor_pairs:
  - refactor: "alpha-rename-local"       # one of the seven named refactors below
    ground_truth_label: "should-stay"    # should-stay | should-flip
    notes: "rename `userId` → `uid` in callee scope only"
  - refactor: "pdg-only-formatting"
    ground_truth_label: "should-stay"
  - refactor: "independent-reordering"
    ground_truth_label: "should-stay"
  - refactor: "pure-extract"
    ground_truth_label: "should-stay"
  - refactor: "fqn-move-package-rename"
    ground_truth_label: "should-stay"
  - refactor: "genuine-fix"
    ground_truth_label: "should-flip"    # AC-CORE-02b
  - refactor: "aliasing-changing-extract"
    ground_truth_label: "should-flip"    # AC-CORE-02b
```

### 3.2 Refactor taxonomy

The seven labels correspond exactly to the five named normalization passes in `PLAN.md §"Algorithm 3"` plus the two AC-CORE-02b flip cases:

| Refactor label | Algorithm 3 pass | Expected outcome |
|---|---|---|
| `alpha-rename-local` | α-renaming for locals | `should-stay` |
| `pdg-only-formatting` | PDG-only formatting | `should-stay` |
| `independent-reordering` | canonical topological sort | `should-stay` |
| `pure-extract` | summary-inlining normalization (pure-extract only) | `should-stay` |
| `fqn-move-package-rename` | FQN normalization | `should-stay` |
| `genuine-fix` | n/a — the sink/source disappears | `should-flip` |
| `aliasing-changing-extract` | NOT covered by summary-inlining (impure) | `should-flip` |

A pair `(seed_finding, refactor)` whose `ground_truth_label` is `should-stay` means: re-running Algorithm 3 on `after/` must yield the **identical** `slice_fingerprint` as `before/`. A `should-flip` label means: re-running on `after/` must yield a **different** `slice_fingerprint`.

### 3.3 `corpus.lock` schema

```yaml
corpus_version: "1.0.0"                  # semver
corpus_digest: "sha256:<hex>"            # SHA-256 over canonical-ordered concat of all meta.yaml + before/+ after/ trees
seed_count: 50
refactor_count: 7
pair_count: 350
languages: ["java", "python"]            # Stage A only at v3.2 GA
annotation_methodology_ref: "annotation-methodology.md"
generation_date: "2026-MM-DD"
```

The lock file pins the corpus contents. A change to any seed (add/remove/edit) requires a new semver, regenerated `corpus_digest`, and a regression-impact assessment per `AC-CORP-REFAC-01b`.

---

## 4. Inputs and outputs

### 4.1 Inputs (to corpus authors)

| Input | Source | Contract |
|---|---|---|
| Seed selection | Algorithm 2 / Semgrep + manual curation | 50 seeded findings, balanced across the four Stage-A classes (`injection`, `path-traversal`, `ssrf`, `deserialization`). |
| Refactor scripts | `tests/corpora/refactor/scripts/` | One script per named refactor; deterministic; must be reproducible from `before/` → `after/`. |
| Ground-truth labels | Annotation methodology (`annotation-methodology.md`) | Each label has a written rationale; no manual labelling without a documented procedure (`.claude/commands/corpus-agent.md`). |

### 4.2 Outputs (to test consumers)

| Output | Consumer | Contract |
|---|---|---|
| Pinned corpus snapshot | `TST-AC-CORE-02a/b` | Tests load the corpus at the pinned `corpus_version`; a corpus update is a deliberate event recorded in the release ledger (`AC-CORP-REFAC-01b`). |
| `corpus_version` + `corpus_digest` | Attestor reports (`CMP-CP-05`) | Stamped into Algorithm 3 benchmark report so the version that produced the empirical `weak`-rate is auditable. |

---

## 5. Invariants touched

| Invariant | How `CMP-CORP-REFAC-01` discharges it | Test |
|---|---|---|
| **INV-5 anchor** | The corpus is the falsifier for the `fingerprint_class` contract. `should-stay` pairs verify that the `strong` path preserves identity across named refactors (the canonical case for `INV-5`); `should-flip` pairs verify that the implementation does NOT over-normalize (e.g. silently treating an aliasing-changing extract as a pure extract). | `TST-AC-CORE-02a [FORTHCOMING]`, `TST-AC-CORE-02b [FORTHCOMING]`, `TST-INV-5-CORE-02 [FORTHCOMING]` |
| **Algorithm 3 per-refactor invariance proof obligation** | `PLAN.md §"Algorithm 3"` claims invariance is proved *per named refactor* — the corpus is what *empirically* checks the proofs against an implementation. | `TST-AC-CORE-02a [FORTHCOMING]` |

The corpus does **not** itself thread provenance fields onto findings; it is upstream of the `findings` table. It does carry `corpus_version` + `corpus_digest` (§8 below) so Attestor benchmark reports are reproducible.

---

## 6. Dependency contract

`Depends-On: []` (`WBS.md §20`). Wave-1.

The corpus depends on **no other CMP-***. It does, however, encode contracts from:

- `PLAN.md §"Algorithm 3"` — the five named normalization passes determine the five `should-stay` labels.
- `SDD.md §6 CMP-CORE-02` — `AC-CORE-02a/b` determine the corpus shape (50 seeds × 7 refactors).
- `.claude/commands/corpus-agent.md` — versioning and labelling-methodology rules.

If `PLAN.md` adds a sixth normalization pass, this corpus MUST gain a corresponding refactor column per `AC-CORP-REFAC-01b` (documented procedure with regression-impact assessment).

---

## 7. Failure modes and error contracts

| Failure | Detection | Response |
|---|---|---|
| Ground-truth label disagreement (curator vs. implementation) | `TST-AC-CORE-02a` / `02b` failure | Investigate per `DOC-RUNBOOK §8` (gate failure response). If the implementation is right and the label is wrong, the corpus is wrong — escalate to Architect Agent to amend `annotation-methodology.md` and bump `corpus_version`. If the label is right and the implementation is wrong, it is a `CMP-CORE-02` bug. |
| Refactor methodology drift | A new `PLAN.md` Algorithm 3 normalization pass is added without a corresponding refactor column | `AC-CORP-REFAC-01b` violation. File a `CLAR-CORP-*` and block the `CMP-CORE-02` release. |
| Manual label without documented procedure | Code review against `.claude/commands/corpus-agent.md` | Hard reject. The Corpus Curator rule forbids hand-labelling without a methodology. |
| Corpus drift (seeds modified without `corpus_version` bump) | `corpus.lock` digest mismatch in CI | Hard fail. The lock file enforces immutability of a pinned version. |
| Seed contamination (a seed accidentally also appears in `CMP-CORP-VULN-01`) | Cross-corpus digest comparison | Re-seed. The seeded-refactor set is for fingerprint invariance, not for recall claims; sharing seeds with `CMP-CORP-VULN-01` would risk cross-contamination of empirical claims. |

This corpus is **not** wired to a CI gate directly — it is a hard input to `TST-AC-CORE-02a/b`, which run inside the unit-test job. Corpus presence is checked as a pre-flight by those tests (mirroring the `tests/corpora/canary/corpus.lock` check pattern in `.github/workflows/attestor.yml`).

---

## 8. Provenance threading

`CMP-CORP-REFAC-01` does **not** emit findings; it has no row-level provenance threading responsibility. It does carry:

| Field | Where | Threading rule |
|---|---|---|
| `corpus_version` | `corpus.lock` | Stamped into Algorithm 3 benchmark report (`CMP-CORE-02` published `weak`-rate, per `CLAR-PARAM-03`). |
| `corpus_digest` | `corpus.lock` | SHA-256 over canonical seed enumeration; verified at test load time. |
| `seed_id` + `refactor` | Test assertion failure message | Failing test reports which `(seed_id, refactor)` pair disagreed with ground truth — required for debuggability. |

**Must NOT touch:** `origin`, `S_version`, `env_digest`, `cpg_order_hash`, `slice_fingerprint` (the corpus measures fingerprint behaviour; it does not produce fingerprints).

---

## 9. Acceptance criteria cross-reference

Quoted verbatim from `WBS.md §16 CMP-CORP-REFAC-01`.

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-CORP-REFAC-01a** | > 50 seeded findings × each refactor; ground-truth labels (`should-flip` vs `should-stay`). | `TST-AC-CORP-REFAC-01a [FORTHCOMING]` — corpus inventory test: assert `pair_count == 50 × 7 == 350`, every pair has a non-empty `ground_truth_label`, the label set is exactly `{should-stay, should-flip}`. |
| **AC-CORP-REFAC-01b** | > Adding a new refactor is a documented procedure with a regression-impact assessment. | `TST-AC-CORP-REFAC-01b [FORTHCOMING]` — checklist test: `annotation-methodology.md §"adding a refactor"` exists; `corpus.lock.corpus_version` semver-bumps on a refactor addition; a regression-impact note exists in the release ledger for the bump. |

**Upstream tests this corpus enables** (the load-bearing assertions for `CMP-CORE-02`):

- `TST-AC-CORE-02a [FORTHCOMING]` — `[FALSIFIER]` Fingerprint invariant under each named refactor on 50 seeded findings. Consumes pairs with `ground_truth_label = should-stay`.
- `TST-AC-CORE-02b [FORTHCOMING]` — `[FALSIFIER]` Fingerprint changes on a genuine fix + aliasing-changing extract. Consumes pairs with `ground_truth_label = should-flip`.
- `TST-AC-CORE-02c [FORTHCOMING]` — `[EMPIRICAL] + [INVARIANT]` `weak`-rate < 5% (`CLAR-PARAM-03` RESOLVED); `weak` never auto-suppressed across a refactor. The corpus provides the population over which the `weak`-rate is measured.
- `TST-INV-5-CORE-02 [FORTHCOMING]` — Weak-class semantics preserved end-to-end. The seeded-refactor set is the input distribution.

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-CORP-REFAC-01 |
|---|---|---|---|
| `CLAR-PARAM-03` | `weak`-fallback publish threshold | **RESOLVED** | 5% confirmed; the seeded-refactor set is the population over which the rate is measured. |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | §1 `Owner` stays DEFERRED; Corpus Curator role placeholder. |

No new CLAR-CORP-* are filed by this document. The corpus shape and labelling rules are fully derivable from `PLAN.md §"Algorithm 3"` + `SDD.md §6` + `WBS.md §16` + `.claude/commands/corpus-agent.md`.

---

## 11. References

- `WBS.md §16 CMP-CORP-REFAC-01` — verbatim Purpose + ACs.
- `SDD.md §6 CMP-CORE-02` — consumer ACs `AC-CORE-02a/b/c`.
- `SDD.md §12` — corpora as first-class deliverables.
- `PLAN.md §"Algorithm 3 — Refactor-stable finding fingerprint"` — five named normalization passes + the `genuine-fix` / `aliasing-changing-extract` flip cases.
- `docs/cross-cutting/DOC-ALGS.md §4` — Algorithm 3 specification.
- `docs/cross-cutting/DOC-INV.md §INV-5` — `fingerprint_class` invariant.
- `docs/cross-cutting/DOC-STAGING.md` — Stage A precondition.
- `docs/components/DOC-CMP-CORE-02.md` (consumer) — Algorithm 3 implementation contract.
- `WBS.md §17 CLAR-PARAM-03` — `weak`-fallback publish threshold resolution.
- `.claude/commands/corpus-agent.md` — Corpus Curator rules (no hand-labelling, versioning required).
- `.claude/rules/01-invariants.md §INV-5` — operational invariant.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for a Corpus Curator to produce a passing `CMP-CORP-REFAC-01`. The corpus is the falsifier; `TST-AC-CORE-02a/b` are the load-bearing tests it enables.*
