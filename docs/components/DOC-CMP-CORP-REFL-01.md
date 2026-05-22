# DOC-CMP-CORP-REFL-01 — Reflection corpus (Falsifier CW)

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `WBS.md §16 CMP-CORP-REFL-01` — verbatim Purpose + AC-CORP-REFL-01a/b/c
- `SDD.md §12` — "test corpora as deliverables" (corpora are first-class work packages)
- `SDD.md §4 CMP-SNAP-03` — `AC-SNAP-03a` (Falsifier CW; this corpus is its evaluation set)
- `PLAN.md §"Closed-world detector (owner of Algorithm 1's precondition)"` — Claim CW
- `docs/cross-cutting/DOC-INV.md §6.2.a` — INV-4 / `CW-DETECT` exposition (this corpus is the falsifier input)
- `docs/cross-cutting/DOC-RUNBOOK.md §8.2` — Gate 2 (Falsifier CW) operational procedure
- `WBS.md §17 CLAR-CORP-01` — RESOLVED 2026-05-23: N ≥ 50 per category, ≥ 20 mutation-injected per language
- `.claude/commands/corpus-agent.md` — Corpus Curator briefing (this doc is the spec; agent assembles data)
- `.claude/rules/00-global.md`, `.claude/rules/01-invariants.md §INV-4`

This document is the **build specification** for the labelled reflection corpus consumed by `CMP-SNAP-03`'s Falsifier CW. It is the **INV-4 falsifier corpus** — not an INV-4 owner. `CMP-SNAP-03` owns INV-4; this corpus is the empirical artifact the owner is falsified against. A single false negative when `CW-DETECT` runs against this corpus is a **Gate 2 release blocker** (`CLAUDE.md §15`).

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-CORP-REFL-01` |
| Subsystem | Corpora (`WBS.md §16`) |
| Artifact type | **Data** — labelled corpus + reproducible build pipeline (not code) |
| Staging | Stage A (must precede `TST-AC-SNAP-03a`) |
| Depends-On | **none** (`WBS.md §20`) — Wave-1 leaf |
| Owner | **DEFERRED** via `CLAR-OWNER-01` (Corpus Curator role; `/corpus-agent`) |
| INV-* touched | **INV-4 falsifier** — provides the zero-FN evaluation set for `CMP-SNAP-03` (`CW-DETECT`). Gate 2 release blocker. |
| Consumer | `CMP-SNAP-03` (Falsifier CW); via `tests/falsifier/cw/` |

---

## 2. Mandate

**Verbatim WBS `Purpose:` (`WBS.md §16 CMP-CORP-REFL-01`):**

> Curated labelled reflection corpus driving Falsifier CW: Spring dynamic proxies, Python `__import__` / `getattr` dispatch, Ruby `send` / `method_missing`, PHP variable functions, Java `Class.forName`, plus mutation-injected reflection in otherwise-closed-world repos with ground-truth labels.

**Operational role.** Every example in this corpus carries a known-correct **ground-truth verdict** (`closed-world` or `not-closed-world`). `CW-DETECT` is run against the corpus in CI; the **false-negative rate must be exactly zero** (`AC-SNAP-03a`). False positives are permitted and only inform the AC-SNAP-03b routing-rate signal. The corpus is therefore the empirical ground on which Claim CW (`PLAN.md`) is falsified — a single missed reflection construct fails Gate 2 and blocks release. The mutation-injection pipeline (`AC-CORP-REFL-01b`) lets the corpus grow under reproducible, scripted control rather than relying on hand-curation alone.

---

## 3. Interface contract (corpus layout + manifest schema)

A corpus is a **data artifact**; its "interface" is the on-disk layout and the manifest schema, not a code API.

### 3.1 Directory layout

```
tests/corpora/reflection/
├── corpus.lock                          # the manifest (see §3.2)
├── README.md                            # ground-truth-methodology document (see §3.4)
├── LICENSES.md                          # per-source license attribution (see §7)
├── categories/
│   ├── java-class-forname/              # one directory per ReflectionKind
│   │   ├── 0001-jndi-classforname/
│   │   │   ├── source/                  # the example code tree
│   │   │   ├── label.yaml               # ground-truth label (see §3.3)
│   │   │   └── provenance.yaml          # source URL + commit sha + sha256
│   │   ├── 0002-spring-dao-classforname/
│   │   └── ...
│   ├── java-spring-dynamic-proxy/
│   ├── python-import-dunder/
│   ├── python-getattr/
│   ├── python-eval-exec/
│   ├── ruby-send/
│   ├── ruby-method-missing/
│   ├── ruby-define-method/
│   ├── php-variable-function/
│   ├── php-call-user-func/
│   ├── js-require-dynamic/
│   ├── js-function-constructor/
│   ├── js-eval/
│   ├── go-reflect-call/
│   └── mutation-injected/               # see §3.5
│       ├── java/  python/  ruby/  php/  js/  go/
└── pipeline/
    ├── inject_reflection.py             # mutation-injection script (deterministic, seeded)
    ├── label.py                         # label-validation helper
    └── build_lock.py                    # emits corpus.lock
```

### 3.2 `corpus.lock` manifest schema (YAML)

```yaml
corpus_id: CMP-CORP-REFL-01
corpus_version: 1.0.0                    # semver; bumped on any item add/remove/relabel
corpus_digest: sha256:...                # sha256 of the canonical serialization of this file
                                         # (computed by pipeline/build_lock.py; written last)
built_at: 2026-MM-DDTHH:MM:SSZ
built_by: <agent-id>                     # corpus-agent run id
ground_truth_method: |                   # see §3.4 for canonical text
  Per-category hand-labelling by Corpus Curator with second-pass review;
  mutation-injection ground-truth by construction (a known reflection site
  inserted by pipeline/inject_reflection.py at a recorded line).

categories:                              # one entry per ReflectionKind directory
  - name: java-class-forname
    language: java
    kind: java-class-forname             # matches CMP-SNAP-03 ReflectionKind enum
    sample_size: 50                      # MUST be ≥ 50 per CLAR-CORP-01
    items:
      - id: 0001-jndi-classforname
        source_url: https://github.com/<org>/<repo>
        commit_sha: <40-char hex>
        path_in_source: path/to/file.java
        sha256: <sha256 of the contents of items.id/source/>
        license: Apache-2.0
        label: not-closed-world          # ground-truth verdict
        expected_sites:                  # MUST be non-empty when label=not-closed-world
          - { file: "path/to/file.java", line: 42, kind: "java-class-forname" }
  - name: mutation-injected-java
    language: java
    kind: mixed                          # mutation-injection covers all Java kinds
    sample_size: 20                      # MUST be ≥ 20 per CLAR-CORP-01
    items: [...]
  # ... and so on per category
```

**Required invariants on `corpus.lock`:**

1. Every category in the table at `§4.3` (per CLAR-CORP-01) has an entry with `sample_size ≥ 50`.
2. Every per-language `mutation-injected` category has `sample_size ≥ 20`.
3. Every `item` has `sha256`, `source_url` + `commit_sha`, and `license`.
4. Every item with `label: not-closed-world` has at least one `expected_sites` entry — this is the per-finding ground truth a sub-detector must produce.

### 3.3 Per-item `label.yaml` schema

```yaml
label: not-closed-world | closed-world
expected_sites:                          # non-empty iff label == not-closed-world
  - file: path/to/file.java
    line: 42
    kind: java-class-forname             # matches CMP-SNAP-03 ReflectionKind
rationale: |
  Free-form explanation of why this is (or is not) reflection. Used by reviewers; not
  consumed by the gate logic.
labelled_by: <reviewer-id>               # who hand-labelled this; "pipeline" for mutation-injected
review_status: single-pass | second-pass # second-pass is required for non-mutation items
```

### 3.4 Ground-truth methodology (`README.md`)

`README.md` MUST document:

- Per-category labelling protocol (who reads the source, what construct counts as reflection, dispute-resolution procedure).
- The mutation-injection pipeline's deterministic seed contract (`pipeline/inject_reflection.py` must be a pure function of `(clean_repo_sha, seed, injection_recipe)`).
- The dual-review requirement for hand-labelled items (`review_status: second-pass`).
- The forbidden-source list (anything used to train an LLM-based reflection classifier — see §7).

A corpus is **not DONE** without this document populated. No "vendored mystery zip".

### 3.5 Mutation-injection pipeline

`pipeline/inject_reflection.py` reads a clean closed-world source tree (with `label: closed-world` ground truth verified by `CW-DETECT` baseline) and inserts a single reflection construct at a recorded site. The output item is labelled `not-closed-world` by construction with `expected_sites` set to the injection point. The script MUST be deterministic in `(input_sha, seed, recipe)` — re-running with the same triple reproduces the same output (this is what makes `AC-CORP-REFL-01b` testable).

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| Hand-curated reflection samples | Public OSS repos with permissive licenses | Each sample: source URL + commit sha + sha256; license recorded |
| Clean closed-world repos | Curated separately; provide the base for mutation injection | Must pass `CW-DETECT` as `closed-world` before any injection |
| Per-language reflection construct catalog | Mirrors `CMP-SNAP-03 ReflectionKind` enum | Adding a `ReflectionKind` requires adding a category here |

### 4.2 Outputs

| Output | Where | Consumer |
|---|---|---|
| `tests/corpora/reflection/` + `corpus.lock` | Repo (or LFS / object store, lock file in repo) | `CMP-SNAP-03` Falsifier CW (`TST-AC-SNAP-03a`) |
| `corpus_version` (semver) | `corpus.lock` | Release ledger (`AC-CORP-REFL-01c`); Attestor / Falsifier reports |
| `corpus_digest` (sha256) | `corpus.lock` | Falsifier reports — pinned per CI run |

### 4.3 Category coverage table (per CLAR-CORP-01 RESOLVED)

| Language | Required categories | Per-category `sample_size` | Mutation-injected (separate) |
|---|---|---|---|
| Java | `java-class-forname`, `java-method-invoke`, `java-proxy-newproxy`, `java-spring-dynamic-proxy` | ≥ 50 each | ≥ 20 (`mutation-injected/java/`) |
| Python | `python-import-dunder`, `python-getattr`, `python-eval-exec` | ≥ 50 each | ≥ 20 (`mutation-injected/python/`) |
| Ruby | `ruby-send`, `ruby-method-missing`, `ruby-define-method` | ≥ 50 each | ≥ 20 (`mutation-injected/ruby/`) |
| PHP | `php-variable-function`, `php-call-user-func` | ≥ 50 each | ≥ 20 (`mutation-injected/php/`) |
| JS/TS | `js-require-dynamic`, `js-function-constructor`, `js-eval` | ≥ 50 each | ≥ 20 (`mutation-injected/js/`) |
| Go | `go-reflect-call` | ≥ 50 | ≥ 20 (`mutation-injected/go/`) |

Adding a new `ReflectionKind` to `CMP-SNAP-03` is forbidden without a matching category here at N ≥ 50.

---

## 5. Invariants touched

| Invariant | How `CMP-CORP-REFL-01` discharges it | Test |
|---|---|---|
| **INV-4 (falsifier)** | Provides the labelled evaluation set against which `CMP-SNAP-03`'s safe-direction claim (zero FN) is checked. The corpus does not own INV-4 (that is `CMP-SNAP-03`); it is the empirical artifact the owner's falsifier runs on. The Gate 2 assertion `fn_rate == 0.0` is meaningful only if this corpus is correctly built and labelled. | `TST-AC-SNAP-03a` `[FORTHCOMING]` — Gate 2 release blocker, consumer-facing. Its inputs are exactly `corpus.lock`'s items and labels. |

This corpus also indirectly feeds **INV-1** (a false negative here would cause snapshots to be wrongly partitioned `deterministic-core`) and is bounded against **INV-1 residual risk** by `CMP-SNAP-04` (differential oracle).

---

## 6. Dependency contract

`CMP-CORP-REFL-01` is a leaf node in the dependency DAG (`WBS.md §20`). It assumes:

- `CMP-SNAP-03`'s `ReflectionKind` enum is the source of truth for category names — corpus categories MUST mirror it. A divergence is a corpus bug, not a `CW-DETECT` bug.
- The Falsifier CW harness in `tests/falsifier/cw/` reads `corpus.lock`'s items and runs `CW-DETECT` against each `source/` tree, comparing the verdict against `label.yaml`.

Downstream consumers depending on this corpus: `CMP-SNAP-03` (Gate 2), `CMP-SNAP-04` (uses some items as seeded-FN inputs for `AC-SNAP-04a`).

---

## 7. Failure modes and error contracts

| Failure | Detection | Required response |
|---|---|---|
| **Reproducibility break** — an item lacks `source_url` + `commit_sha` + `sha256` (a "vendored mystery zip") | `pipeline/build_lock.py` refuses to emit `corpus.lock` | Reject the corpus build; item must be re-sourced with deterministic provenance. No exception. |
| **Ground-truth quality** — hand-labelled item without `review_status: second-pass` | `pipeline/build_lock.py` rejects items missing dual review | Re-label under the dual-review protocol; document any methodology change in `README.md`. |
| **License incompatibility** — an item's license is not on the allow-list (MIT, Apache-2.0, BSD-2/3, MPL-2.0; never GPL/AGPL without explicit CTO approval) | `pipeline/build_lock.py` validates `license` against allow-list | Reject the item; find a compatible replacement. Record refusal in `LICENSES.md`. |
| **`corpus_digest` drift** — `corpus.lock`'s recorded digest does not match the canonical re-serialization | CI digest check (`tests/falsifier/cw/test_lock_digest.py`) | Hard CI fail. Corpus owner must rebuild and re-pin. |
| **Mutation-injection non-reproducibility** — re-running `inject_reflection.py` with the same `(input_sha, seed, recipe)` produces a different output | Pipeline unit test | Hard fail; this is `AC-CORP-REFL-01b`. Fix the script's non-determinism (typically: a non-deterministic AST traversal or `random()` call without seed). |
| **A FN survives in the Falsifier CW run** — `CW-DETECT` returns `closed-world` on an item labelled `not-closed-world` | Gate 2 harness | A single FN is a **release blocker** (`AC-SNAP-03a`). Fix `CW-DETECT`; do NOT delete or relabel the corpus item to "resolve" the failure. Per `DOC-RUNBOOK §8.2`: "expand the corpus only after the fix lands; do not relax the gate." |
| **Forbidden training-data overlap** — a corpus item is identical to (or templated from) a sample used to train any LLM-based reflection classifier downstream | Manual review during `README.md` methodology pass | Reject the item; document in `LICENSES.md` / `README.md`. |

---

## 8. Provenance threading

A corpus does not write to the `findings` provenance schema directly. Instead, it carries its own provenance fields that **feed into** the Attestor and Falsifier reports:

| Field | Where | Threading rule |
|---|---|---|
| `corpus_version` (semver) | `corpus.lock` → Falsifier CW report (`tests/results/falsifier_cw/{run-id}.json`) | Bumped on any add/remove/relabel; the version is part of the release ledger (`AC-CORP-REFL-01c`). |
| `corpus_digest` (sha256 of canonical `corpus.lock` serialization) | `corpus.lock` → Falsifier CW report; recorded on every Gate 2 run | Pins the exact evaluation set used in a CI run; an Attestor disagreement traceable back to `corpus_digest`. |
| Per-item `sha256`, `source_url`, `commit_sha`, `license` | `corpus.lock` items | The reproducibility contract — every item is independently re-buildable. |

**Must NOT touch:** `origin`, `S_version`, `env_digest`, `cpg_order_hash`, `slice_fingerprint`, or any row in the `findings` table. The corpus is not a detector.

---

## 9. Acceptance criteria cross-reference

Quoted verbatim from `WBS.md §16 CMP-CORP-REFL-01`. Paraphrasing an AC is a contract break (RULE-4). All `TST-AC-CORP-REFL-01-*` are `[FORTHCOMING]`.

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-CORP-REFL-01a** | > Corpus covers every category listed above with ≥ N labelled examples per category (`N` filed as `CLAR-CORP-01`). | `TST-AC-CORP-REFL-01a` `[FORTHCOMING]` — asserts `corpus.lock` has every category in `§4.3` with `sample_size ≥ 50`, and every per-language `mutation-injected` category with `sample_size ≥ 20` (per `CLAR-CORP-01` RESOLVED). |
| **AC-CORP-REFL-01b** | > Mutation-injection pipeline reproducibly generates labelled reflection scenarios from clean closed-world repos. | `TST-AC-CORP-REFL-01b` `[FORTHCOMING]` — runs `inject_reflection.py` twice with same `(input_sha, seed, recipe)`; asserts byte-identical output. |
| **AC-CORP-REFL-01c** | > Corpus is versioned; a corpus change is part of the release ledger. | `TST-AC-CORP-REFL-01c` `[FORTHCOMING]` — asserts `corpus.lock` carries `corpus_version` (semver) and `corpus_digest`; CI checks the release ledger contains an entry for the active version. |

**Consumer-facing gate test (this corpus exists to make it runnable):**

- `TST-AC-SNAP-03a` `[FORTHCOMING]` — **Gate 2 release blocker** (`CLAUDE.md §15`). Runs `CW-DETECT` against every item in `corpus.lock`; asserts `fn_rate == 0.0`. The corpus is the evaluation input.
- `TST-AC-SNAP-04a` `[FORTHCOMING]` — uses a designated subset of `mutation-injected/` items as seeded FN inputs for the differential-oracle re-partition test.

Invariant tests cross-referenced:

- `TST-INV-4-SNAP-03 [FORTHCOMING]` — falsifier verification (this corpus is the input).

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-CORP-REFL-01 |
|---|---|---|---|
| `CLAR-CORP-01` | Reflection corpus minimum sample size per category | **RESOLVED** 2026-05-23 | N ≥ 50 per category, ≥ 20 mutation-injected per language. Drives `§4.3`. |
| `CLAR-OWNER-01` | Per-component / corpus owner | **DEFERRED** | `§1` Owner stays DEFERRED; Corpus Curator role assignment pending. |

**No new CLAR-CORP-* are filed by this document.** All inputs are pinned.

---

## 11. References

- `WBS.md §16 CMP-CORP-REFL-01` — verbatim ACs.
- `SDD.md §12` — corpora as work packages.
- `SDD.md §4 CMP-SNAP-03 AC-SNAP-03a` — Falsifier CW consumer.
- `PLAN.md §"Closed-world detector"` — Claim CW (the property this corpus falsifies).
- `docs/cross-cutting/DOC-INV.md §6.2.a` — INV-4 / `CW-DETECT`.
- `docs/cross-cutting/DOC-RUNBOOK.md §8.2` — Gate 2 (Falsifier CW) operational procedure.
- `docs/components/DOC-CMP-SNAP-03.md` — consumer (the INV-4 owner).
- `docs/components/DOC-CMP-SNAP-04.md` — differential oracle consumer.
- `.claude/commands/corpus-agent.md` — Corpus Curator briefing.
- `WBS.md §17 CLAR-CORP-01` — sample-size resolution.
- `CLAUDE.md §15` — CI gate table (Gate 2).
- `.claude/rules/01-invariants.md §INV-4` — operational invariant.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for a Corpus Curator agent to assemble `CMP-CORP-REFL-01` and for the Falsifier CW harness implementer to consume it. The Gate 2 release blocker (`TST-AC-SNAP-03a`) is the load-bearing test; this corpus is its evaluation set.*
