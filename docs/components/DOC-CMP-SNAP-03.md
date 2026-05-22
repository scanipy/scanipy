# DOC-CMP-SNAP-03 — `CW-DETECT` closed-world precondition detector

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `SDD.md §4 CMP-SNAP-03` (Purpose, AC-SNAP-03a/b)
- `PLAN.md §"Closed-world detector (owner of Algorithm 1's precondition)"` — **Claim CW** (verbatim quoted in §6.1)
- `PLAN.md §"Algorithm 1 — Incremental CPG maintenance"` — consumer
- `docs/cross-cutting/DOC-INV.md §6.2.a` — INV-4 owner exposition for `CW-DETECT`
- `docs/cross-cutting/DOC-ALGS.md §2.7, §2.9` — known sensitivities; falsifier links
- `docs/cross-cutting/DOC-PARTITION.md §2, §5` — downstream partition consequences
- `docs/cross-cutting/DOC-RUNBOOK.md §6, §8.2` — Gate 2 (Falsifier CW) operational procedure
- `WBS.md §17 CLAR-CORP-01` (RESOLVED — reflection corpus N≥50 per category, ≥20 mutation-injected per language)
- `.claude/rules/00-global.md`, `.claude/rules/01-invariants.md §INV-4`

This document is the **implementation contract** for `CMP-SNAP-03`. It is the **INV-4 OWNER** for Algorithm 1's closed-world precondition: a single false negative is a release blocker (`AC-SNAP-03a`).

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-SNAP-03` |
| Subsystem | Snapshotter (`SDD.md §4`) |
| Staging | Stage A (no per-language gate; `CMP-SNAP-03` is cross-language; the **corpus** `CMP-CORP-REFL-01` enumerates per-language reflection patterns) |
| Depends-On | **none** (`WBS.md §20`) — Wave-1 component |
| Owner | **DEFERRED** via `CLAR-OWNER-01` |
| INV-* touched | **INV-4 OWNER** (Algorithm 1 closed-world precondition). Required safe direction: **zero false negatives**. False positives are permitted. Falsifier: `TST-AC-SNAP-03a` (Gate 2 release blocker; `CLAUDE.md §15`). |
| Falsifier corpus | `CMP-CORP-REFL-01` (per `CLAR-CORP-01` RESOLVED: N ≥ 50 per category, ≥ 20 mutation-injected per language) |

---

## 2. Mandate

**Verbatim SDD `Purpose:` (`SDD.md §4 CMP-SNAP-03`):**

> One-sided conservative detector for reachable reflection / dynamic dispatch over an open hierarchy. Owner of Algorithm 1's precondition (INV-4).

**Operational role.** `CW-DETECT` is the **gatekeeper** of Algorithm 1's closed-world hypothesis. The undecidable property is: *does this snapshot contain a reflection / dynamic-dispatch construct that can reach analyzed code?* Because the property is undecidable in dynamically typed languages and in languages with run-time class loading, `CW-DETECT` is a **conservative one-sided over-approximation**. Its **required soundness direction** is zero false negatives: if any such construct is reachable, the verdict MUST be `not-closed-world`. False positives — declaring `not-closed-world` on code that is in fact closed-world — are permitted; they cost performance (more snapshots ride the degraded or full-reparse path) but never correctness. A single false negative is a release blocker (`AC-SNAP-03a`).

This document is consumed by **`CMP-SNAP-02`** (which routes Algorithm 1 by the verdict) and by **`CMP-SNAP-04`** (which independently re-evaluates the verdict asynchronously and re-partitions findings on disagreement). Together with `CMP-SNAP-04` (the differential oracle), the residual undecidable-case risk is bounded to a labeling-correction window with a contractual SLA — see `DOC-CMP-SNAP-04` and `DOC-RUNBOOK §6`.

---

## 3. Interface contract

`CMP-SNAP-03` is invoked in-process by the snapshot worker. Pure function signature:

```typescript
interface CwDetectRequest {
    source_tree_root: string;         // local FS path to checked-out source @ commit
    language_mix: string[];           // detected languages (e.g. ["java", "python"])
    parent_snapshot?: Snapshot;       // optional; used to incrementally update reflection-site cache
}

interface CwDetectVerdict {
    verdict: "closed-world" | "degraded" | "full-reparse";
    cw_detect_version: string;        // semver of this detector; sealed into provenance
    reflection_sites: ReflectionSite[]; // empty iff verdict == "closed-world"
    decided_at: string;               // iso-8601
    confidence: "high" | "uncertain"; // uncertain ALWAYS routes to not-closed-world (§6.2)
}

interface ReflectionSite {
    file: string;
    line: number;
    kind: ReflectionKind;
    snippet: string;                  // 1-line evidence string
}

type ReflectionKind =
    | "java-class-forname"
    | "java-method-invoke"            // java.lang.reflect.Method#invoke
    | "java-proxy-newproxy"
    | "java-spring-dynamic-proxy"
    | "python-import-dunder"          // __import__
    | "python-getattr"
    | "python-eval-exec"
    | "ruby-send"
    | "ruby-method-missing"
    | "ruby-define-method"
    | "php-variable-function"
    | "php-call-user-func"
    | "js-require-dynamic"            // require(variable)
    | "js-function-constructor"       // new Function(...)
    | "js-eval"
    | "go-reflect-call"
    | "structural-uncertainty";       // fallback per §6.2
```

**Concrete entry point** (Python; binding for the worker):

```python
def detect(req: CwDetectRequest) -> CwDetectVerdict: ...
```

### 3.1 Verdict mapping

```
verdict := if reflection_sites is non-empty:
              "degraded"            # downstream may further demote to "full-reparse"
                                    # per CMP-SNAP-02 §6.1 thresholds
           elif confidence == "uncertain":
              "degraded"            # fail-closed (INV-4 safe direction)
           else:
              "closed-world"
```

`CW-DETECT` itself never emits `full-reparse` — that decision belongs to `CMP-SNAP-02` (based on `θ_cone`/`θ_files`). `CW-DETECT` only ever distinguishes "closed-world" from "not-closed-world", and the latter is represented as `degraded` at the CW level.

### 3.2 Error contracts

| Error | Cause | Response |
|---|---|---|
| `ParseFailure` | Source file is unparseable; structural facts unknown for that file | **Fail-closed**: emit a synthetic reflection site `kind="structural-uncertainty"` for the file. Verdict ⇒ `degraded`. |
| `LanguageNotSupported` | A language present in the tree is not yet enumerated in `ReflectionKind` | **Fail-closed**: emit `structural-uncertainty` for any source file in the unsupported language. |
| `InternalError` | Detector itself fails to complete | **Fail-closed**: emit `structural-uncertainty` covering the affected file; the worker may retry. A second consecutive failure DLQs. |

There is **no** error path that produces `closed-world` from a partial / uncertain analysis. **Uncertainty is reflection** by construction.

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| `source_tree_root` | Worker checkout (via `CMP-SCM-*`) | Local FS path. |
| `language_mix` | Worker language-detector | Drives which sub-detectors fire. Unknown ⇒ fail-closed. |
| `parent_snapshot` (optional) | `CMP-SNAP-01` | Used only to read the cached reflection-site index; **never to bias the verdict toward `closed-world`**. |

### 4.2 Outputs

`CwDetectVerdict` (per §3). The verdict is consumed by:

1. `CMP-SNAP-02` (routes Algorithm 1).
2. `CMP-SNAP-01` (persists `precondition_status.json` per `DOC-CMP-SNAP-01 §4.3`).
3. `CMP-SNAP-04` (compares against the differential oracle).

---

## 5. Invariants touched

| Invariant | How `CMP-SNAP-03` discharges it | Test |
|---|---|---|
| **INV-4 OWNER** | Provides a one-sided over-approximation of an undecidable property (reachable reflection). Required safe direction: **zero FN**. Falsifier is a curated reflection corpus (`CMP-CORP-REFL-01`) augmented with mutation-injected reflection. The differential oracle (`CMP-SNAP-04`) is the residual-risk bound for the unsound case. | `TST-AC-SNAP-03a` `[FORTHCOMING]` — **Gate 2 release blocker** (`CLAUDE.md §15`); `TST-INV-4-SNAP-03` `[FORTHCOMING]` |
| **INV-1 hand-off** | The verdict routes downstream emission paths into a partition. A false negative would cause findings to be wrongly emitted as `deterministic-core`; `CMP-SNAP-04` re-partitions those after the fact (`DOC-PARTITION §5`). | `TST-INV-1-SNAP-04` (consumer test) |

---

## 6. Algorithm / data flow

### 6.1 Claim CW (the soundness direction — verbatim from `PLAN.md`)

> **Claim CW (soundness direction).** `CW-DETECT` has a zero false-negative rate with respect to "this snapshot contains a reflection/dynamic construct that can reach analyzed code": if any such construct is reachable, `CW-DETECT` must report *not-closed-world* and route the snapshot to the degraded path. False positives (declaring not-closed-world when the code is in fact closed-world) are permitted and merely cost performance.

`AC-SNAP-03a` operationalizes Claim CW:

> **[Falsifier CW]** Zero false negatives on the curated reflection corpus (Spring dynamic proxies, Python `__import__`/`getattr`, Ruby `send`/`method_missing`, PHP variable functions, Java `Class.forName`, plus mutation-injected reflection). **A single false negative is a release blocker.**

### 6.2 Detection procedure (safe-direction pseudocode)

Mirrors `DOC-INV §6.2.a` — the canonical safe-direction shape:

```python
def detect(req: CwDetectRequest) -> CwDetectVerdict:
    sites: list[ReflectionSite] = []
    confidence = "high"

    for src_file in walk(req.source_tree_root):
        lang = detect_language(src_file)
        if lang not in SUPPORTED_LANGUAGES:
            # Fail-closed: an unsupported language is structural uncertainty
            sites.append(ReflectionSite(src_file, 0, "structural-uncertainty", ""))
            confidence = "uncertain"
            continue

        try:
            ast = parse(src_file, lang)
        except ParseError:
            # Fail-closed: an unparseable file is structural uncertainty
            sites.append(ReflectionSite(src_file, 0, "structural-uncertainty", ""))
            confidence = "uncertain"
            continue

        # Per-language sub-detectors (each one-sided; FN-zero on its corpus slice)
        sites.extend(scan_java(ast)     if lang == "java"   else [])
        sites.extend(scan_python(ast)   if lang == "python" else [])
        sites.extend(scan_ruby(ast)     if lang == "ruby"   else [])
        sites.extend(scan_php(ast)      if lang == "php"    else [])
        sites.extend(scan_js(ast)       if lang in ("js","ts") else [])
        sites.extend(scan_go(ast)       if lang == "go"     else [])

    if sites:
        return CwDetectVerdict("degraded", VERSION, sites, now_iso(), confidence)
    if confidence == "uncertain":
        # Should not reach here (sites non-empty under uncertain) — defensive.
        return CwDetectVerdict("degraded", VERSION,
                               [ReflectionSite("", 0, "structural-uncertainty", "")],
                               now_iso(), "uncertain")
    return CwDetectVerdict("closed-world", VERSION, [], now_iso(), "high")
```

Key safe-direction properties of the pseudocode (every one of which is testable):

1. The default return on uncertainty is **never** `closed-world`. There is no code path that turns an unsupported language, a parse failure, or an internal error into a `closed-world` verdict.
2. Per-language sub-detectors are **one-sided** within their slice: each is required to produce FN=0 on `CMP-CORP-REFL-01`'s slice for that language. False positives within a sub-detector are permitted.
3. The cached reflection-site index from `parent_snapshot` is read-only; it can **add** sites (e.g. carry forward a known reflection site for an unchanged file) but never subtract them.

### 6.3 Per-language sub-detector requirements (FN-zero corpus slice)

Per `CLAR-CORP-01` (RESOLVED 2026-05-23), the falsifier corpus `CMP-CORP-REFL-01` contains:

- **N ≥ 50 per category** (one category per `ReflectionKind` for the language).
- **≥ 20 mutation-injected** reflection examples per language (inserted into otherwise-closed-world repos with ground-truth labels).

| Language | Required `ReflectionKind` coverage in `CMP-CORP-REFL-01` |
|---|---|
| Java | `java-class-forname`, `java-method-invoke`, `java-proxy-newproxy`, `java-spring-dynamic-proxy` |
| Python | `python-import-dunder`, `python-getattr`, `python-eval-exec` |
| Ruby | `ruby-send`, `ruby-method-missing`, `ruby-define-method` |
| PHP | `php-variable-function`, `php-call-user-func` |
| JS/TS | `js-require-dynamic`, `js-function-constructor`, `js-eval` |
| Go | `go-reflect-call` |

A submission that adds a new `ReflectionKind` MUST add a corresponding corpus category with N ≥ 50 examples (corpus update is a `CMP-CORP-REFL-01` task and a precondition for the kind to be considered "covered"). Adding a `ReflectionKind` without a corpus update is forbidden.

### 6.4 What `CW-DETECT` does NOT do

- It does **not** decide whether reflection actually reaches analyzed code at runtime (that would require points-to analysis with high precision; the Stage-C investment `T-STAGE-C-FE-01` is the place this conversation lives, see `CLAR-FE-02` DEFERRED). The detector treats any reachable reflection-bearing site as `not-closed-world`.
- It does **not** emit findings. `CW-DETECT` is a routing oracle, not a detector in the `CMP-DET-*` sense.
- It does **not** mutate `origin` on any finding (`CMP-SNAP-04` does, post-hoc).

---

## 7. Failure modes and error contracts

| Failure | Detection | Response (must be safe-direction) |
|---|---|---|
| Source file unparseable | `ParseError` from front-end | Emit `structural-uncertainty` site; verdict ⇒ `degraded`. **Never** `closed-world`. |
| Language unsupported | `lang not in SUPPORTED_LANGUAGES` | Emit `structural-uncertainty` site for every file in that language; verdict ⇒ `degraded`. |
| Internal sub-detector exception | try/except | Emit `structural-uncertainty` covering the file; verdict ⇒ `degraded`. Alarm on repeat failures. |
| All files closed-world but a vendored dependency contains reflection | Sub-detectors scan source tree by default — vendored deps must be included if they are part of the analysis scope | Per `PLAN.md §"Algorithm 1"`: the closed-world hypothesis is "over a hierarchy closed under the analysis scope". If a dependency is included in the analysis, it is in scope; reflection in it ⇒ `degraded`. |
| Mutation-injected reflection in a benchmark | Should be detected (it is the falsifier purpose) | A FN here is a **release blocker** (`AC-SNAP-03a`). |

**Safe-direction contract (the load-bearing requirement).** For every input where the analysis cannot **prove** the absence of reflection, the verdict is `degraded`. There is no third option. Implementations are forbidden from including a "best-effort closed-world" fast path that returns `closed-world` from a heuristic.

---

## 8. Provenance threading

`CMP-SNAP-03` writes:

| Field | Where | Threading rule |
|---|---|---|
| `verdict` (`closed-world | degraded | full-reparse` — at this level, only the first two) | `precondition_status.json` (via `CMP-SNAP-01`) | The verdict is **immutable once persisted**; downstream consumers may interpret it but never rewrite it. |
| `cw_detect_version` | `precondition_status.json` | Semver of the detector; written into provenance so `CMP-SNAP-04` can identify which CW version produced the verdict on a disagreement. |
| `reflection_sites` | `precondition_status.json` | List of detected sites; the audit chain link to the differential oracle's comparison input. |
| `confidence` | `precondition_status.json` | `high | uncertain`; an `uncertain` verdict must be `degraded`. |

**Must NOT touch:** `origin`, `S_version`, `env_digest`, `cpg_order_hash`, `slice_fingerprint`, finding-level rows.

---

## 9. Acceptance criteria cross-reference

Quoted verbatim from `SDD.md §4 CMP-SNAP-03`. Paraphrasing an AC is a contract break (RULE-4). All TST-AC-* are `[FORTHCOMING]`.

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-SNAP-03a** | > **[Falsifier CW]** Zero false negatives on the curated reflection corpus (Spring dynamic proxies, Python `__import__`/`getattr`, Ruby `send`/`method_missing`, PHP variable functions, Java `Class.forName`, plus mutation-injected reflection). A single false negative is a release blocker. | `TST-AC-SNAP-03a` `[FORTHCOMING]` — **Gate 2 release blocker** (`CLAUDE.md §15`). The pass criterion is the literal assertion `fn_rate == 0.0` on `CMP-CORP-REFL-01`. |
| **AC-SNAP-03b** | > False positives are permitted; the combined true-positive + false-positive routing rate is measured and reported (this, not the true reflection rate, is what the ≤15% target governs). | `TST-AC-SNAP-03b` `[FORTHCOMING]` — measurement against a representative repo population. The ≤15% target is for the combined routing rate; this is **not** a release blocker, it is an economics signal. |

Invariant tests cross-referenced:

- `TST-INV-4-SNAP-03 [FORTHCOMING]` — invariant verification of safe direction (no `closed-world` verdict on any corpus-positive input).
- `TST-INV-1-SNAP-04 [FORTHCOMING]` — re-partition (the residual-risk bound, owned by `CMP-SNAP-04`).

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-SNAP-03 |
|---|---|---|---|
| `CLAR-CORP-01` | Reflection corpus minimum sample size per category | **RESOLVED** | N ≥ 50 per category, ≥ 20 mutation-injected per language. |
| `CLAR-SLA-01` | Differential-oracle labeling-correction window SLA | **RESOLVED** | 24h high-impact / 7d routine. Owned by `CMP-SNAP-04`, but `CW-DETECT` is the upstream that the SLA exists to bound. |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | §1 `Owner` stays DEFERRED. |
| `CLAR-FE-02` | Stage-C points-to / interface-dispatch scope | **DEFERRED** | Would (if scoped richer than Andersen baseline) reduce FP rate on Go; does not affect FN. Stage A unaffected. |
| `CLAR-FE-01` | Stage-D proprietary front-end (Ruby / PHP fidelity) | **DEFERRED** | A weak Ruby / PHP front-end yields more `structural-uncertainty` → more `degraded` verdicts. INV-4 safe direction is preserved (it just costs performance). |

No new CLAR-SNAP-* are filed by this document.

---

## 11. References

- `SDD.md §4 CMP-SNAP-03` — verbatim ACs.
- `PLAN.md §"Closed-world detector (owner of Algorithm 1's precondition)"` — Claim CW verbatim source.
- `PLAN.md §"Algorithm 1 — Incremental CPG maintenance"` — downstream consumer.
- `docs/cross-cutting/DOC-INV.md §6.2.a` — canonical INV-4 exposition for `CW-DETECT`.
- `docs/cross-cutting/DOC-ALGS.md §2.7, §2.9` — falsifier and known sensitivities.
- `docs/cross-cutting/DOC-PARTITION.md §2, §5` — downstream partition consequences.
- `docs/cross-cutting/DOC-RUNBOOK.md §6` (differential-oracle incident procedure), `§8.2` (Gate 2 — Falsifier CW response).
- `docs/components/DOC-CMP-SNAP-02.md` (sibling) — verdict consumer.
- `docs/components/DOC-CMP-SNAP-04.md` (sibling) — differential oracle (the residual-risk bound).
- `docs/components/DOC-CMP-CORP-REFL-01.md` (sibling, forthcoming) — falsifier corpus.
- `WBS.md §17 CLAR-CORP-01` — corpus sample-size resolution.
- `CLAUDE.md §15` — CI gate table (Gate 2).
- `.claude/rules/01-invariants.md §INV-4` — operational invariant.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-SNAP-03`. The Gate 2 release blocker (`TST-AC-SNAP-03a`) is the load-bearing test; any change to `CW-DETECT` must keep it green.*
