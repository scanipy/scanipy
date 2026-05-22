# DOC-CMP-CP-06 — CPG-fidelity gate harness

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `SDD.md §10 CMP-CP-06` (Purpose, AC-CP-06a, AC-CP-06b)
- `PLAN.md §"Phase staging — the sequencing observation"`, `§"Per-language launch gate"` (verbatim CPG-fidelity gate statement)
- `docs/cross-cutting/DOC-STAGING.md §3` (gate criteria), §4 (`(class, language)` pair table), §6 (`STAGE-GATED` semantics), §8 (front-end-blocked reporting)
- `docs/cross-cutting/DOC-INV.md §8 (INV-6)` (verbatim invariant statement + falsifier examples)
- `WBS.md §17 CLAR-CORP-02` (RESOLVED 2026-05-23 — per-language thresholds)
- `.claude/rules/04-staging.md` (operational staging rules)
- `.claude/rules/00-global.md` RULE-7 (no `(class, language)` enters Algorithm 2 benchmarking before `CMP-CP-06` green)
- `.github/workflows/stage-gate.yml` (CI implementation surface — `cpg-fidelity` job)

This document is the **implementation contract** for `CMP-CP-06`. A code-writing agent given only this file plus the cross-cutting refs above must be able to produce a passing implementation without re-reading `SDD.md` (per `AC-DOC-04`).

`CMP-CP-06` is the **owner of INV-6** (per-language honesty). Its gate verdict is the precondition for every `(class, language)` pair entering the Algorithm 2 benchmark (`CMP-CORE-01 AC-CORE-01b`). The staging constraint **overrides the dependency DAG** (per `CLAUDE.md §15` / RULE-7): a CMP that depends on `CMP-CORE-01` may still be `STAGE-GATED` for a given language even if the dependency is `DONE`.

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-CP-06` |
| Subsystem | Control Plane & Attestation (`SDD.md §10`) |
| Staging | per language (the gate is itself the staging mechanism — see `DOC-STAGING §3`) |
| Depends-On | `CMP-SNAP-05` (worker + pinned `Env` — the harness re-uses the worker image to evaluate the front-end against the curated corpus) — per `WBS.md §20` |
| Owner | **DEFERRED** via `CLAR-OWNER-01` (`WBS.md §17`) |
| INV-* touched | **INV-6 owner** (per-language honesty; gate verdict is the empirical falsifier of the recall-validity precondition); ancillary **INV-1** (gate verdict determines whether a `(class, language)` pair ships as `core` or `oracle-passthrough` per `DOC-STAGING §4`) |
| Gate authority | The staging constraint **overrides the dependency DAG** per `WBS.md §15` / `CLAUDE.md §11 RULE-7`: a `(class, language)` pair may not enter Algorithm 2 benchmarking until `CMP-CP-06` is green for that language. |

---

## 2. Mandate

**Verbatim SDD `Purpose:` (`SDD.md §10 CMP-CP-06`):**

> Per-language fidelity corpus with ground-truth ASTs/CFGs/call-edges; gate thresholds (parse success ≥ 99.5%, call-edge precision/recall thresholds, PDG dependence-edge recall threshold). A `(class, language)` pair enters the Algorithm 2 benchmark only after passing.

**Verbatim PLAN gate statement (`PLAN.md §"Per-language launch gate"`):**

> **CPG-fidelity gate.** For language `L`, on a curated fidelity corpus with ground-truth ASTs/CFGs/call-edges, the Joern (or proprietary) front-end for `L` must achieve: parse success ≥ 99.5% of files; call-edge precision/recall ≥ stated thresholds against the ground truth; PDG dependence-edge recall ≥ threshold. Only `(class, L)` pairs that pass enter the Algorithm 2 benchmark; pairs that fail are reported as **front-end-blocked**, not as recall failures, so the falsifier stays meaningful.

**Operational role.** `CMP-CP-06` ships:

1. The per-language fidelity benchmark harness (`pytest -m empirical -k "cpg_fidelity and {language}"`), which runs the Joern (or proprietary) front-end against the curated `CMP-CORP-CPG-{language}` corpus and emits per-metric results.
2. The threshold-evaluation logic that compares benchmark output to the four `CLAR-CORP-02` thresholds and emits `GATE-PASS` or `GATE-FAIL` with the failing metric names.
3. The verdict persistence layer that records per-`(language, metric)` results so downstream consumers (the `/stage-gate` agent, `WBS.md §13` status table, `PLAN.md` honest-labeling ledger) can read them.
4. The reporting contract: a failed language is reported as **`front-end-blocked`**, never as a recall failure (INV-6, `AC-CP-06a`).

`CMP-CP-06` does **not** run Algorithm 2's recall benchmark (`CMP-CORE-01 AC-CORE-01b`). It does **not** modify any detector behaviour. It does **not** ship per-language fixes for front-end deficiencies — those are scoped under separate front-end investment work packages (`T-STAGE-C-FE-01` / `CLAR-FE-02` for Go; `T-STAGE-D-FE-01` / `CLAR-FE-01` for Ruby/PHP).

---

## 3. Interface contract

### 3.1 Per-language thresholds (verbatim from CLAR-CORP-02, RESOLVED 2026-05-23)

| Metric | Threshold | Rationale (verbatim from `DOC-STAGING §3`) |
|---|---|---|
| Parse success rate | **≥ 99.5%** of files | `SDD.md CMP-CP-06`; the corpus must not be a parse-failure corpus. |
| Call-edge precision | **≥ 90%** | `CLAR-CORP-02`; tighter than recall because the IFDS solver is precision-sensitive at the call boundary. |
| Call-edge recall | **≥ 85%** | `CLAR-CORP-02`; below this, Algorithm 2 recall is dominated by front-end miss. |
| PDG dependence-edge recall | **≥ 80%** | `CLAR-CORP-02`; PDG misses cause false negatives that look like spec gaps. |

These thresholds are quoted, **never re-decided**. A threshold change requires a new CTO-approved `CLAR-CORP-02` resolution plus a lockstep update of this document, `DOC-STAGING.md`, `.claude/rules/04-staging.md`, and `.github/workflows/stage-gate.yml`.

### 3.2 Function signatures

```python
# services/control_plane/fidelity.py  (CMP-CP-06)

@dataclass(frozen=True)
class FidelityMetrics:
    parse_success_rate: Decimal       # 0..1
    call_edge_precision: Decimal      # 0..1
    call_edge_recall: Decimal         # 0..1
    pdg_recall: Decimal               # 0..1
    files_parsed: int
    files_total: int
    call_edges_predicted: int
    call_edges_ground_truth: int
    pdg_edges_predicted: int
    pdg_edges_ground_truth: int

@dataclass(frozen=True)
class FidelityVerdict:
    language: Literal["java", "python", "js", "go", "ruby", "php"]
    corpus_version: str               # hash from corpus.lock
    env_digest: str                   # CMP-SNAP-05 worker image digest
    metrics: FidelityMetrics
    threshold_results: dict[str, Literal["PASS", "FAIL"]]
    overall: Literal["GATE-PASS", "GATE-FAIL", "front-end-blocked"]
    failing_metrics: list[str]        # empty when overall == GATE-PASS
    evaluated_at: datetime

def evaluate_fidelity(
    language: Literal["java", "python", "js", "go", "ruby", "php"],
    corpus_path: Path,                # tests/corpora/cpg_fidelity/{language}/
) -> FidelityVerdict:
    """
    Run the Joern (or proprietary) front-end against the curated corpus
    and compute the four per-language metrics. Apply the CLAR-CORP-02
    thresholds. Emit GATE-PASS, GATE-FAIL, or front-end-blocked.

    - GATE-PASS: all four thresholds met. The language is eligible for
      Algorithm 2 benchmarking on all (class, language) pairs whose
      class is staged for it (per DOC-STAGING §4).
    - GATE-FAIL: at least one threshold missed. The language is reported
      as front-end-blocked. The benchmark MUST NOT report a recall number
      for any (class, language) pair on a GATE-FAIL language; doing so
      would violate INV-6 (AC-CP-06a).
    - front-end-blocked: the same as GATE-FAIL but the reporting label
      that downstream consumers (the WBS table, the honest-labeling
      ledger, customer contracts) use. INV-6 mandates this label;
      "recall failure" is forbidden.
    """

def persist_verdict(verdict: FidelityVerdict) -> None:
    """
    Persist verdict to tests/results/cpg_fidelity/{language}/latest.json
    (the artifact path consumed by .github/workflows/stage-gate.yml step
    'Evaluate thresholds and write verdict'). Also append a row to a
    fidelity_results audit log — see §4.2 for the working-assumption
    persistence scheme and CLAR-CP-06-01 for the persistence-layer
    decision.
    """
```

### 3.3 Reporting contract (INV-6 — AC-CP-06a)

A language `L` that fails the gate is reported as **`front-end-blocked`**, **never** as a recall failure. The forbidden phrasings are:

- "Algorithm 2 recall is 0.31 on Go" — when Go has not passed `CMP-CP-06`.
- "injection (Go) — recall failure" — when Go has not passed `CMP-CP-06`.
- Anything that surfaces a recall number for a `(class, L)` pair where `L` has not passed the gate.

The required phrasings are:

- "injection (Go) — `front-end-blocked`: call-edge recall 0.62 < 0.85 threshold" (per `DOC-INV §8.4` compliant example).
- "Stage C — Go (deferred); fidelity gate not passed (call-edge recall 0.62 < 0.85)."

Per-stage recall tables (`TST-AC-CORE-01b`) include **only gate-passing** pairs. The honest-labeling ledger (`PLAN.md`) distinguishes `[STAGED]` from `[EMPIRICAL]` / `[CONDITIONAL THEOREM]` claims; a front-end-blocked pair belongs in `[STAGED]`.

### 3.4 Consultation contract (AC-CP-06b)

`AC-CP-06b` requires: "Gate results are recorded per language and consulted by the WBS staging logic."

The recording surface is `tests/results/cpg_fidelity/{language}/latest.json` (per `DOC-STAGING §3` and the existing `.github/workflows/stage-gate.yml`). The JSON schema:

```json
{
  "language": "java",
  "corpus_version": "<sha256 of corpus.lock>",
  "env_digest": "sha256:<worker-image-digest>",
  "parse_success_rate": 0.997,
  "call_edge_precision": 0.93,
  "call_edge_recall": 0.88,
  "pdg_recall": 0.84,
  "evaluated_at": "2026-05-23T10:00:00Z",
  "overall": "GATE-PASS",
  "failing_metrics": []
}
```

Consumers:

1. **`/stage-gate` agent** (`.claude/commands/stage-gate.md`) — reads the JSON to verify Stage X promotion (`DOC-STAGING §7.1`).
2. **`WBS.md §13` staging status table** — flipped manually by `/sync-wbs` based on the JSON verdicts.
3. **`CLAUDE.md §7` per-language staging gates table** — surfaces the readiness summary.
4. **`PLAN.md` honest-labeling ledger** — updated on stage promotion (`DOC-STAGING §7.3`).
5. **`CMP-CORE-01`** — refuses to include a non-gate-passing `(class, language)` pair in the Algorithm 2 recall report.

The JSON is the canonical persistence surface for v3.2. **An auxiliary database `fidelity_results` table is not yet defined in `DOC-DB.md`**; if a code-writing agent finds it needs DB-level row-level history (e.g., to render historical trends in the dashboard), `CLAR-CP-06-01` (§10) is the gating decision.

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| `language` parameter | `.github/workflows/stage-gate.yml` `workflow_dispatch.inputs.language` (one of `java`/`python`/`js`/`go`/`ruby`/`php`) | Required. |
| Curated fidelity corpus | `tests/corpora/cpg_fidelity/{language}/` + `corpus.lock` (`CMP-CORP-CPG-{language}`) | Must exist; missing → harness fails with explicit error (existing `stage-gate.yml` step "Verify corpus readiness"). |
| Ground-truth ASTs / CFGs / call-edges | `tests/corpora/cpg_fidelity/{language}/ground_truth/*.json` | Per-file ground truth; format is corpus-specific but the metrics-computation routine consumes a uniform schema. |
| Worker image digest (`env_digest`) | `CMP-SNAP-05` pinned image | The gate harness must re-use the same worker image that production scans use; otherwise the gate's verdict does not apply to production. |
| Joern (or proprietary) front-end binary | Inside the pinned worker image | The front-end being evaluated. |

### 4.2 Outputs / Persisted artifacts

| Output | Location | Contract |
|---|---|---|
| `FidelityVerdict` JSON | `tests/results/cpg_fidelity/{language}/latest.json` | Consumed by `.github/workflows/stage-gate.yml` "Evaluate thresholds" step; consumed by `/stage-gate` agent. |
| Per-test JUnit XML | `stage-gate-{language}-results.xml` (uploaded artifact) | Per-test pass/fail; surfaces individual file-level failures for debugging the corpus. |
| Stage-gate verdict (GitHub Actions check) | GitHub Actions UI | `GATE-PASS` (zero exit) or `GATE-FAIL` (non-zero exit, lists failing metrics). |
| OpenTelemetry counters | metrics `fidelity.parse_success_rate{language}`, `fidelity.call_edge_precision{language}`, etc. | Surfaced on the staging dashboard; trended over time. |
| **Optional** `fidelity_results` DB row | PostgreSQL (proposed; see `CLAR-CP-06-01`) | If the DB table is added, one row per `(language, evaluated_at)` with all four metrics. **Not yet defined in `DOC-DB.md`** — working assumption is JSON-only. |

CP-06 **does not** write to `findings`, `provenance_records`, `attestations`, or any other application table. The only outputs are the JSON verdict file, the JUnit XML, the GitHub Actions check status, and the OTel metrics.

---

## 5. Invariants touched

| Invariant | How `CMP-CP-06` discharges it | Test |
|---|---|---|
| **INV-6 (owner)** | The gate verdict is the empirical falsifier of the recall-validity precondition (`PLAN.md §"Per-language launch gate"`). A language that fails the gate is reported as `front-end-blocked`, **never** as a recall failure. `CMP-CORE-01 AC-CORE-01b` consumes the verdict and refuses to include non-passing pairs in the recall report. | `TST-AC-CP-06a [FORTHCOMING]` (a deliberately-failing language is reported `front-end-blocked`, not as a recall failure); `TST-INV-6-CP-06 [FORTHCOMING]` (gate produces a pass/fail per language; refuses to emit a recall number on a fail). |
| **INV-1** (ancillary, via DOC-STAGING §4) | A `(class, language)` pair that has not passed the gate cannot enter the core partition. The staging table (`DOC-STAGING §4`) drives detector registration so that, e.g., a non-gate-passing Go injection detector ships with `engine ∈ {semgrep, cpg-query}` → `origin=oracle-passthrough` by `CMP-DET-02` / `CMP-ORCH-03`. | `TST-AC-CP-06b [FORTHCOMING]` (WBS staging logic consults the verdict; a non-gate-passing pair is not promoted to core). |

CP-06 is the **owner** of INV-6 — it produces the verdict that the other CMPs honour. It is not the owner of INV-1 (`CMP-ORCH-03` is), but its verdict is the input that determines which partition a `(class, language)` pair lives in.

See `DOC-INV.md §8` for the verbatim INV-6 statement, compliant/violating examples, and cross-cutting touchpoints.

---

## 6. Algorithm / data flow

```
trigger: .github/workflows/stage-gate.yml — workflow_dispatch
         (inputs: language, stage, corpus_version)
              │
              ▼
Step "Verify corpus readiness":
  - tests/corpora/cpg_fidelity/{language}/ must exist
  - corpus.lock must exist
  - missing → exit 1 (CMP-CORP-CPG-{language} not DONE)
              │
              ▼
Step "Run CPG-fidelity benchmark":
  pytest -m "empirical" -k "cpg_fidelity and {language}" \
         --junit-xml=stage-gate-{language}-results.xml
              │
              ▼
  For each corpus file:
    1. Run Joern (or proprietary) front-end → parsed CPG.
    2. Diff parsed CPG against ground-truth AST/CFG/call-edges/PDG.
    3. Increment counters (parsed/total; call-edges TP/FP/FN; PDG TP/FN).
              │
              ▼
  Aggregate per-language metrics:
    parse_success_rate = files_parsed / files_total
    call_edge_precision = TP / (TP + FP)
    call_edge_recall    = TP / (TP + FN)
    pdg_recall          = TP_pdg / (TP_pdg + FN_pdg)
              │
              ▼
  Write tests/results/cpg_fidelity/{language}/latest.json
              │
              ▼
Step "Evaluate thresholds and write verdict":
  thresholds = {
    "parse_success_rate": 0.995,
    "call_edge_precision": 0.90,
    "call_edge_recall":    0.85,
    "pdg_recall":          0.80,
  }
  for metric, threshold in thresholds.items():
      if r[metric] >= threshold: PASS
      else: FAIL → append to failures
  failures empty → "GATE-PASS: all thresholds met for {language}"
  failures non-empty → "GATE-FAIL: <metric>=<value> < <threshold>, …"
                       → exit 1
              │
              ▼
Step "Upload verdict": stage-gate-{language}-verdict artifact uploaded.

  ┌─────────────────────────────────────────────────────────┐
  │ Consumer chain:                                          │
  │  • /stage-gate agent reads latest.json on Stage X promo. │
  │  • /sync-wbs flips the language status in WBS.md §13.    │
  │  • CMP-CORE-01 reads the verdict before computing recall.│
  │  • Honest-labeling ledger updated on promotion.          │
  └─────────────────────────────────────────────────────────┘
```

On `GATE-FAIL`: the failing language is reported as `front-end-blocked` everywhere it surfaces. The remediation is a front-end investment (e.g., `T-STAGE-C-FE-01` for Go points-to, `T-STAGE-D-FE-01` for Ruby/PHP), not a threshold relaxation. Threshold relaxation requires a CTO-approved `CLAR-CORP-02` resolution per §3.1.

---

## 7. Failure modes and error contracts

| Failure | Detected by | Response | Side effect |
|---|---|---|---|
| Corpus directory missing | "Verify corpus readiness" step | Job fails with explicit `ERROR: Corpus directory ... does not exist. CMP-CORP-CPG-{language} must be DONE before stage gate evaluation.` | Indicates a missing dependency; surface to the WBS sync. |
| `corpus.lock` missing | "Verify corpus readiness" step | Job fails with `ERROR: corpus.lock missing`. | Same as above. |
| One or more thresholds missed | "Evaluate thresholds" step | Job exits 1 with `GATE-FAIL: <metric>=<value> < <threshold>` per failing metric. Language reported as `front-end-blocked` everywhere. | The `(class, language)` pairs depending on this language remain `STAGE-GATED` (per `DOC-STAGING §6`). |
| `pytest` itself fails (harness bug) | "Run CPG-fidelity benchmark" step | Job exits non-zero; verdict JSON not written; `latest.json` not refreshed. | Distinct from `GATE-FAIL`: this is a harness bug, not a front-end failure. Fix the harness; do not infer a verdict from a missing JSON. |
| `env_digest` of the gate run differs from the production worker image | Pre-run check (working assumption — see §10) | Job fails with `ERROR: gate env_digest != production env_digest`. | A gate run on a different `Env` is not authoritative for production. Fix the CI pin. |
| Reporting layer surfaces a recall number for a `GATE-FAIL` language | Linter / `TST-AC-CP-06a [FORTHCOMING]` | **Hard PR block.** INV-6 violation. | The patch must replace the recall number with `front-end-blocked: <metric> <value> < <threshold>`. |
| Threshold relaxed in code without CLAR-CORP-02 update | Code review | **PR rejected** (RULE-4 — no invented scope; thresholds are CLAR-CORP-02-owned). | The threshold change requires a CTO-approved CLAR-CORP-02 update + lockstep changes to `DOC-STAGING`, `.claude/rules/04-staging.md`, this document, and `.github/workflows/stage-gate.yml`. |

**Fail-closed posture.** A `GATE-FAIL` blocks the stage promotion. There is no "approximate pass" or "best-effort gate". RULE-7 forbids hacking around the gate to enter Algorithm 2 benchmarking.

---

## 8. Provenance threading

CP-06 emits **verdicts, not findings**. Its threading responsibilities:

| Field | CP-06 contribution |
|---|---|
| `env_digest` | Stamped on every `FidelityVerdict` (`latest.json` and any DB row). The verdict applies to one specific worker image; a different image needs a new verdict. |
| `corpus_version` | Stamped on every `FidelityVerdict`; the hash of the corpus `corpus.lock`. Without it, an after-the-fact corpus change could invalidate the gate without surfacing. |
| `evaluated_at` | Stamped on every `FidelityVerdict`; downstream consumers (the staging dashboard) trend verdict freshness. |

`origin`, `S_version`, `cpg_order_hash` — **not applicable**. CP-06 emits no findings; it emits gate verdicts. The "four required provenance fields" (RULE-6) apply to finding-emitting components; CP-06 is a verdict-emitting component and its analogues are `env_digest` + `corpus_version` + `evaluated_at`.

**Must NOT touch.** `findings`, `provenance_records`, `attestations`, `origin`, `S_version`, `cpg_order_hash`. CP-06 does not modify any production data; it produces an out-of-band verdict that other components consult.

---

## 9. Acceptance criteria cross-reference

The following ACs are quoted **verbatim** from `SDD.md §10 CMP-CP-06`. Paraphrasing is a contract break (RULE-4).

| AC | Verbatim statement | Test artifact | Note |
|---|---|---|---|
| **AC-CP-06a** | > A language failing the gate is reported `front-end-blocked`, not as a recall failure (INV-6). | `TST-AC-CP-06a` `[FORTHCOMING]` | **INV-6 hard discharge.** |
| **AC-CP-06b** | > Gate results are recorded per language and consulted by the WBS staging logic. | `TST-AC-CP-06b` `[FORTHCOMING]` | **Per-language staging gate** — overrides the dependency DAG per `WBS.md §15` / RULE-7. |

**AC-CP-06a** falsifier (for QA Agent):

1. Construct a synthetic corpus where the front-end achieves call-edge recall = 0.60 (below the 0.85 threshold).
2. Run `evaluate_fidelity(language, corpus)`.
3. Assert: `overall == "GATE-FAIL"`, `failing_metrics == ["call_edge_recall"]`, `latest.json` written.
4. Assert: the reporting layer surfaces the language as `front-end-blocked`, never as "recall failure 0.60".
5. Assert: `CMP-CORE-01 AC-CORE-01b` (when test fixture is provided) refuses to include any `(class, language)` pair from this language in the recall report.

**AC-CP-06b** falsifier:

1. Run the gate on a passing language (e.g., Java) → `GATE-PASS`.
2. Run the gate on a failing language (e.g., Go with weak Joern front-end) → `GATE-FAIL`.
3. Assert: both verdicts persisted to `tests/results/cpg_fidelity/{language}/latest.json`.
4. Assert: `/stage-gate` agent, when invoked for Stage A promotion, reads the Java verdict and proceeds; when invoked for Stage C promotion, reads the Go verdict and refuses.
5. Assert: `WBS.md §13` staging status table reflects both verdicts (after a `/sync-wbs` run).

Cross-referenced invariant tests:

- `TST-INV-6-CP-06 [FORTHCOMING]` — the gate harness produces a pass/fail per language and **refuses to report a fail as a recall number** (INV-6 owner-side discharge).
- `TST-INV-6-CORE-01 [FORTHCOMING]` — Algorithm 2's recall report (`CMP-CORE-01 AC-CORE-01b`) contains only gate-passing `(class, language)` pairs (consumer-side discharge).

**Per-language gate authority** (CLAUDE.md §15 / `.claude/rules/00-global.md` RULE-7):

> No `(class, language)` pair enters Algorithm 2 benchmarking before `CMP-CP-06` is green for that language. `STAGE-GATED` is a valid status; the fix is to advance the stage (front-end investment), not to hack around the gate.

`STAGE-GATED` is distinct from `BLOCKED` (per `DOC-STAGING §6`):

- **`BLOCKED`** = some `Depends-On` entry has not reached `DONE` → fix the dependency.
- **`STAGE-GATED`** = every `Depends-On` is `DONE` but the gate has not passed → invest in the front-end / extend the corpus / file a CTO-approved deferral.

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-CP-06 |
|---|---|---|---|
| `CLAR-CORP-02` | Per-language CPG-fidelity thresholds | **RESOLVED** 2026-05-23 | Parse ≥99.5%, call-edge precision ≥90%, recall ≥85%, PDG dependence-edge recall ≥80%. Quoted verbatim in §3.1. |
| `CLAR-FE-01` | Stage-D proprietary front-end (Ruby/PHP) | **DEFERRED** | Ruby + PHP gate cannot pass on Joern alone (per `DOC-STAGING §2 Stage D`). Until resolved, both languages remain `STAGE-GATED` and ship `oracle-passthrough` only. |
| `CLAR-FE-02` | Stage-C points-to investment (Go) | **DEFERRED** | Go gate cannot pass without points-to / interface-dispatch investment (per `DOC-STAGING §2 Stage C`). Until resolved, Go remains `STAGE-GATED`. |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | Owner field in §1 remains DEFERRED. |
| **`CLAR-CP-06-01`** *(new — filed by this document)* | Should fidelity verdicts be persisted to a PostgreSQL `fidelity_results` table in addition to the JSON artifact? The JSON satisfies `AC-CP-06b` literally, but a DB table would enable: (i) row-level history surfaced in the customer dashboard, (ii) per-customer view of which `(class, language)` pairs are core vs oracle, (iii) trend analytics. | **FILED** in `WBS.md §17` (OPEN), target resolution before Stage B GA | Working assumption: JSON-only for v3.2 baseline; DB table deferred until a concrete consumer (e.g., the customer dashboard's per-language readiness view) is in scope. If filed, the schema is straightforward: `(id, language, corpus_version, env_digest, parse_success_rate, call_edge_precision, call_edge_recall, pdg_recall, overall, failing_metrics jsonb, evaluated_at)`. |
| **`CLAR-CP-06-02`** *(new — filed by this document)* | Should the gate harness enforce that the gate-evaluation `env_digest` matches the production worker image, or only record it? | **FILED** in `WBS.md §17` (OPEN), target resolution before Stage A GA | Working assumption: hard-enforce (per §7 "fail-closed posture"). A gate run on a non-production `Env` is not authoritative for production claims. |

---

## 11. References

- `SDD.md §10 CMP-CP-06` — verbatim ACs.
- `PLAN.md §"Phase staging — the sequencing observation"`, `§"Per-language launch gate"` — verbatim gate statement.
- `docs/cross-cutting/DOC-STAGING.md` §3 (gate criteria), §4 (pair table), §6 (STAGE-GATED semantics), §8 (front-end-blocked reporting).
- `docs/cross-cutting/DOC-INV.md` §8 (INV-6 verbatim, compliant/violating examples).
- `WBS.md §17 CLAR-CORP-02` (RESOLVED 2026-05-23 — quoted in §3.1).
- `WBS.md §17 CLAR-FE-01` (DEFERRED — Stage D); `CLAR-FE-02` (DEFERRED — Stage C).
- `WBS.md §15` — gate authority overrides the dependency DAG.
- `CLAUDE.md §7` — per-language staging gates summary table.
- `.claude/rules/04-staging.md` — operational staging rules.
- `.claude/rules/00-global.md` RULE-7 — no `(class, language)` enters Algorithm 2 benchmarking before `CMP-CP-06` green.
- `.claude/rules/01-invariants.md` (INV-6).
- `.github/workflows/stage-gate.yml` — CI implementation surface; `cpg-fidelity` job.
- `docs/components/DOC-CMP-CORE-01.md` (sibling, forthcoming) — Algorithm 2 benchmark; consumes the gate verdict.
- `docs/components/DOC-CMP-SNAP-05.md` (sibling, forthcoming) — pinned worker image (`env_digest` source).
- `docs/components/DOC-CMP-CORP-CPG-*.md` (siblings, forthcoming) — per-language fidelity corpora.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-CP-06`. The per-language thresholds in §3.1 are quoted verbatim from CLAR-CORP-02 (RESOLVED 2026-05-23); changes require a new CTO-approved CLAR-CORP-02 resolution plus lockstep updates to `DOC-STAGING.md`, `.claude/rules/04-staging.md`, and `.github/workflows/stage-gate.yml`.*
