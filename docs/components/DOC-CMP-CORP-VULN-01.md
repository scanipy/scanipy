# DOC-CMP-CORP-VULN-01 — OWASP / Juliet / BigVul slices

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `WBS.md §16 CMP-CORP-VULN-01` — Purpose, AC-CORP-VULN-01a/b verbatim
- `SDD.md §12` — corpora are first-class deliverables
- `SDD.md §6 CMP-CORE-01` (AC-CORE-01b) — per-(class, language) recall benchmark consumes this corpus
- `PLAN.md §"Per-language staging overlay"` — INV-6 boundary on per-language honesty
- `docs/cross-cutting/DOC-ALGS.md §3` — Algorithm 2 (IFDS/IDE) tabulation; consumer of recall slices
- `docs/cross-cutting/DOC-INV.md §INV-6` — per-(class, language) honesty contract
- `docs/cross-cutting/DOC-STAGING.md` — Stage A and (class, language) gating
- `.claude/rules/04-staging.md` — (class, language) Algorithm 2 entry rule
- `.claude/commands/corpus-agent.md` — **hard rule: BigVul training data MUST NOT be in the held-out evaluation split**
- `.claude/rules/00-global.md`, `.claude/rules/01-invariants.md §INV-6`

This document is the **implementation contract** for `CMP-CORP-VULN-01`. The corpus is the falsifier for `AC-CORE-01b` — Algorithm 2's empirical per-(class, language) recall claim. Its integrity (especially BigVul held-out / training disjointness) is INV-6's load-bearing precondition.

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-CORP-VULN-01` |
| Subsystem | Cross-cutting corpora (`WBS.md §16`) |
| Staging | Stage A — `(class, language)` slices populated incrementally per stage gate (`.claude/rules/04-staging.md`) |
| Depends-On | **none** (`WBS.md §20`) — Wave-1 component |
| Owner | **DEFERRED** via `CLAR-OWNER-01`. Curated by the Corpus Curator role (`.claude/commands/corpus-agent.md`). |
| INV-* touched | **INV-6 anchor** — the per-(class, language) slicing IS the operational form of INV-6. A slice is populated only when its `(class, language)` pair has passed `CMP-CP-06`. |
| Falsifier role | Owns the held-out evaluation set for Algorithm 2's `[EMPIRICAL]` recall claim (`AC-CORE-01b`). |
| Storage | `tests/corpora/vuln/` (`.claude/commands/corpus-agent.md`) |

---

## 2. Mandate

**Verbatim WBS `Purpose:` (`WBS.md §16 CMP-CORP-VULN-01`):**

> Evaluation slices used by Algorithm 2's per-(class, language) recall claim. Held-out portion of BigVul is preserved across releases.

**Operational role.** `CMP-CORP-VULN-01` is the **held-out evaluation corpus** for `AC-CORE-01b` — Algorithm 2's per-(class, language) recall must exceed Semgrep-default + 10pp at equal precision on this corpus. The corpus comprises three integrated sources:

1. **OWASP Benchmark** — open Java + curated language extensions; used as a published baseline.
2. **Juliet** — NSA/SARD CWE-tagged test cases, multi-language.
3. **BigVul held-out split** — a versioned subset of BigVul that is provably disjoint from any training set used by Algorithm 2 spec inference (`CMP-TRI-02`) or by detector-DSL spec curation. **This disjointness is a hard rule.**

The corpus is the only source of recall numbers reported under `AC-CORE-01b`. Recall numbers from any *other* corpus must be labelled informational and may not satisfy the AC.

---

## 3. Interface contract

The corpus is a versioned on-disk artifact, not a callable service.

```
tests/corpora/vuln/
├── corpus.lock                          # version manifest; SHA-256 over all slice manifests
├── owasp_benchmark/
│   └── slices/<class>/<language>/...
├── juliet/
│   └── slices/<class>/<language>/...
├── bigvul_heldout/
│   ├── heldout_split.lock              # SHA-256 over the heldout sample id set
│   ├── training_exclusion_proof.md     # MANDATORY — see §3.2
│   └── slices/<class>/<language>/...
└── annotation-methodology.md
```

### 3.1 Per-slice manifest

```yaml
slice_id: "owasp-injection-java-001"
source: "owasp_benchmark"               # one of: owasp_benchmark | juliet | bigvul_heldout
class: "injection"                      # one of: injection | path-traversal | ssrf | deserialization | xss | ...
language: "java"                        # java | python | js | ts | go | ruby | php
cwe_ids: ["CWE-89"]                     # ground-truth CWE tags
positive: true                          # true = vulnerable; false = clean fix variant
fix_pair_id: "owasp-injection-java-001-fix"  # null if no paired fix; else slice_id of the clean fix
notes: "BenchmarkTest00001"
```

### 3.2 BigVul training-exclusion contract (HARD RULE)

`tests/corpora/vuln/bigvul_heldout/training_exclusion_proof.md` MUST contain:

1. The deterministic procedure that produced the held-out split (e.g. "sort by `(commit_sha, file_path, function_name)`, take rows whose `sha256(row_id)` MOD 10 == 9").
2. A SHA-256 of the held-out `row_id` set, persisted in `heldout_split.lock`.
3. A SHA-256 of the training-eligible `row_id` set (the complement).
4. A signed assertion that the held-out set has **never** been fed to any spec-inference run (`CMP-TRI-02`), spec-curator review, or detector-DSL design loop.

`heldout_split.lock` is version-pinned. Any modification requires a new corpus semver and a regenerated proof. **A held-out / training intersection is a hard release blocker.** (Source: `.claude/commands/corpus-agent.md` *"Use BigVul training data as part of the held-out evaluation split"* is listed under "What you must never do".)

### 3.3 Per-stage slicing

The corpus is sliced along `(class, language)`. A slice is **populated only when its language has cleared `CMP-CP-06`** (`.claude/rules/04-staging.md`, `INV-6`). At v3.2 GA, only Stage-A languages (Java, Python) carry populated slices for the four core classes (`injection`, `path-traversal`, `ssrf`, `deserialization`).

| Stage | Class × Language slices populated |
|---|---|
| Stage A | (injection, path-traversal, ssrf, deserialization) × (java, python) |
| Stage B | + xss × (js, ts); the four core classes × (js, ts) |
| Stage C | + four core classes × go (after `CMP-CP-06` Go gate) |
| Stage D | + four core classes × (ruby, php) (after `CMP-CP-06` gates; until then ruby/php ride `oracle-passthrough` only) |

A slice that does NOT exist for a `(class, language)` pair means the pair is **front-end-blocked** (`INV-6`); it does NOT mean recall failure (`.claude/rules/01-invariants.md §INV-6`).

### 3.4 `corpus.lock` schema

```yaml
corpus_version: "1.0.0"
corpus_digest: "sha256:<hex>"            # over canonical concat of all slice manifests + heldout_split.lock
sources: ["owasp_benchmark", "juliet", "bigvul_heldout"]
populated_slices:
  - {class: "injection", language: "java", count: 245}
  - {class: "path-traversal", language: "java", count: 120}
  # ... etc
bigvul_heldout_lock_ref: "bigvul_heldout/heldout_split.lock"
training_exclusion_proof_ref: "bigvul_heldout/training_exclusion_proof.md"
licenses:                                # see §7 "license compliance"
  owasp_benchmark: "Apache-2.0"
  juliet: "Public Domain (NIST)"
  bigvul: "MIT"
```

---

## 4. Inputs and outputs

### 4.1 Inputs (to corpus authors)

| Input | Source | Contract |
|---|---|---|
| OWASP Benchmark | upstream public release | Vendored at pinned release tag; license recorded in `corpus.lock`. |
| Juliet | NSA/SARD release | Vendored at pinned version; ground-truth CWE labels preserved. |
| BigVul | upstream public release | Held-out split derived deterministically per §3.2; the **same** held-out lock is preserved across releases (`AC-CORP-VULN-01a`). |

### 4.2 Outputs (to test consumers)

| Output | Consumer | Contract |
|---|---|---|
| Per-(class, language) slice | `TST-AC-CORE-01b` | Each per-stage benchmark run reports per-slice precision/recall. The benchmark MUST exclude any slice whose `(class, language)` pair has not cleared `CMP-CP-06`. |
| `corpus_version` + `corpus_digest` | Attestor benchmark report (`CMP-CP-05`) | Stamped into recall benchmark report; a recall claim is auditable only with the corpus version pinned. |
| `heldout_split.lock` digest | Release ledger | Persisted across releases as proof of BigVul disjointness (`AC-CORP-VULN-01a`). |

---

## 5. Invariants touched

| Invariant | How `CMP-CORP-VULN-01` discharges it | Test |
|---|---|---|
| **INV-6 anchor** | Slices populated only for `(class, language)` pairs that have cleared `CMP-CP-06`. A non-existent slice reports as `front-end-blocked`, not as recall failure. The corpus IS the operational instantiation of INV-6. The slice population list is the authoritative input to the per-stage staging table. | `TST-INV-6-CORE-01 [FORTHCOMING]`, `TST-INV-6-CP-06 [FORTHCOMING]` |
| **Algorithm 2 recall claim (`AC-CORE-01b`)** | Held-out + BigVul-training-disjoint corpus IS the falsifier for Algorithm 2's empirical recall claim. Without disjointness the recall number is uninterpretable — a model that memorized training would self-validate. | `TST-AC-CORE-01b [FORTHCOMING]` (per stage) |

**The BigVul training-exclusion contract anchors INV-6 honesty.** If the held-out set is contaminated, any recall number reported under `AC-CORE-01b` is invalid (the model has seen the test). Disjointness is therefore both a corpus rule (`§3.2`) AND a release-blocker condition (§7 below).

---

## 6. Dependency contract

`Depends-On: []` (`WBS.md §20`). Wave-1.

The corpus consumer is `CMP-CORE-01` via `TST-AC-CORE-01b`. The slice population schedule is gated by `CMP-CP-06` per language. The corpus does NOT depend on `CMP-CP-06` to *exist*, but the *use* of a given slice depends on its `(class, language)` pair having cleared the fidelity gate.

---

## 7. Failure modes and error contracts

| Failure | Detection | Response |
|---|---|---|
| **BigVul training-leakage detection** (held-out ∩ training-eligible ≠ ∅) | `heldout_split.lock` digest vs. training-eligible set intersection check at every corpus update | **Hard release blocker.** Recall numbers since the contamination date are invalid; the release ledger must record the invalidation. Re-derive the split per `§3.2`, re-run `AC-CORE-01b` benchmarks against the new lock. (Source: `.claude/commands/corpus-agent.md`.) |
| Held-out lock mutated between releases | Cross-release `heldout_split.lock` digest comparison | Hard reject. `AC-CORP-VULN-01a` ("BigVul held-out split is versioned and never used for training") requires the lock be **preserved across releases**. A change requires a new corpus semver AND a release-ledger entry. |
| License compliance — a vendored corpus carries an incompatible license | License audit on `corpus.lock` | If license forbids redistribution: the slice ships as a fetch-on-demand reference, not as vendored content. Recorded under `corpus.lock.licenses`. Juliet (Public Domain) and BigVul (MIT) are on the vendor allow-list. OWASP BenchmarkJava is **GPL-2.0** — off the allow-list; it ships fetch-on-demand (pinned commit + `upstream_sha256`), not vendored (CLAR-CORP-18). A new source requires a license review before vendoring. |
| Slice exists for a `(class, language)` pair that has not cleared `CMP-CP-06` | Pre-flight check in `TST-AC-CORE-01b` | The slice is **excluded** from the benchmark and the pair is reported as `front-end-blocked` (`.claude/rules/01-invariants.md §INV-6`). The slice's presence is not itself an error; running it through Algorithm 2 anyway is. |
| Annotation drift (a slice's `cwe_ids` change without methodology amendment) | `annotation-methodology.md` version vs. slice manifest version check | Reject. The Corpus Curator role forbids relabelling without a documented methodology. |

This corpus is **not** wired to a CI gate directly — it is a hard input to `TST-AC-CORE-01b`, which runs as part of the per-stage benchmark (driven by `CMP-CP-06` gate state).

---

## 8. Provenance threading

`CMP-CORP-VULN-01` does **not** emit findings; it has no row-level provenance threading responsibility. It does carry:

| Field | Where | Threading rule |
|---|---|---|
| `corpus_version` | `corpus.lock` | Stamped into Algorithm 2 recall benchmark report; recall numbers are only auditable when paired with this version. |
| `corpus_digest` | `corpus.lock` | SHA-256 over canonical slice enumeration. |
| `heldout_split.lock` digest | `corpus.lock` (bigvul_heldout sub-lock) | Persisted across releases as the BigVul-disjointness witness. |
| `slice_id` | Per-finding test report | Failing benchmark rows report which slice the false negative came from — needed to file `CMP-CP-06` regressions vs. detector regressions. |

**Must NOT touch:** `origin`, `S_version`, `env_digest`, `cpg_order_hash`, `slice_fingerprint` (those are runtime finding attributes; the corpus is a static input).

---

## 9. Acceptance criteria cross-reference

Quoted verbatim from `WBS.md §16 CMP-CORP-VULN-01`.

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-CORP-VULN-01a** | > OWASP Benchmark + Juliet integrated; BigVul held-out split is versioned and never used for training. | `TST-AC-CORP-VULN-01a [FORTHCOMING]` — corpus integrity test: assert OWASP + Juliet slice manifests exist with correct ground-truth CWE tags; assert `heldout_split.lock` exists and its digest is preserved across releases; assert `training_exclusion_proof.md` exists and the held-out / training-eligible intersection is empty. |
| **AC-CORP-VULN-01b** | > Per-(class, language) slicing supports the per-stage benchmark in `TST-AC-CORE-01b`. | `TST-AC-CORP-VULN-01b [FORTHCOMING]` — slicing test: assert every Stage-A `(class, language)` pair from `.claude/rules/04-staging.md` has a populated slice with `count > 0`; assert front-end-blocked pairs have no slice OR are tagged accordingly. |

**Upstream tests this corpus enables:**

- `TST-AC-CORE-01b [FORTHCOMING]` — `[EMPIRICAL]` per-stage recall ≥ Semgrep-default + 10pp at equal precision on `(class, language)` pairs that have cleared `CMP-CP-06`. The pass criterion is empirical against this corpus.
- `TST-INV-6-CORE-01 [FORTHCOMING]` — Recall numbers reported only for gate-passing pairs.
- `TST-INV-6-CP-06 [FORTHCOMING]` — Front-end-blocked pairs are reported as `front-end-blocked`, never as recall failures.

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-CORP-VULN-01 |
|---|---|---|---|
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | §1 `Owner` stays DEFERRED; Corpus Curator role placeholder. |

`CLAR-CORP-02` (per-language `CMP-CP-06` thresholds) is upstream — VULN slices are populated only after a language clears its threshold, but the threshold itself is `CMP-CP-06`'s clarification, not VULN's. No impact on this doc.

No new CLAR-CORP-* are filed by this document. The corpus shape, BigVul disjointness rule, and licensing constraints are fully derivable from `WBS.md §16` + `.claude/commands/corpus-agent.md` + `.claude/rules/04-staging.md`.

---

## 11. References

- `WBS.md §16 CMP-CORP-VULN-01` — verbatim Purpose + ACs.
- `SDD.md §6 CMP-CORE-01` (`AC-CORE-01b`) — consumer recall claim.
- `SDD.md §12` — corpora as first-class deliverables.
- `SDD.md §11` — staging overlay.
- `PLAN.md §"Per-language staging overlay"` — INV-6 boundary.
- `docs/cross-cutting/DOC-ALGS.md §3` — Algorithm 2 specification.
- `docs/cross-cutting/DOC-INV.md §INV-6` — per-(class, language) honesty.
- `docs/cross-cutting/DOC-STAGING.md` — stage gates.
- `.claude/rules/04-staging.md` — `(class, language)` Algorithm 2 entry rule.
- `.claude/commands/corpus-agent.md` — **hard rule: BigVul training data MUST NOT be in the held-out evaluation split**.
- `.claude/rules/01-invariants.md §INV-6` — operational invariant.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for a Corpus Curator to produce a passing `CMP-CORP-VULN-01`. The BigVul training-exclusion contract is the load-bearing rule; a violation invalidates `AC-CORE-01b` and is a hard release blocker.*
