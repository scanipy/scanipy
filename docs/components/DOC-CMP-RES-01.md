# DOC-CMP-RES-01 — Research mode service

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `WBS.md §15 CMP-RES-01` — Purpose, T-CMP-RES-01-01..03 verbatim
- `SDD.md §7 CMP-ORCH-01` (`AC-ORCH-01c`) — the load-bearing test for the `scanipy --query` shim
- `SDD.md §9 CMP-TRI-02` — e-process evaluation stream consumer
- `SDD.md §2 INV-3` — LLM off the detection path
- `PLAN.md §"Phase staging"` (Phase 8) — Research mode rationale
- `docs/cross-cutting/DOC-ALGS.md §7` — Algorithm 6 (anytime-valid e-process)
- `docs/cross-cutting/DOC-INV.md §INV-3` — Research-mode helpers boundary
- `WBS.md §5 CMP-SCM-02` — `T-CMP-SCM-02-02` (the type-system boundary for `search_code()`)
- `.claude/rules/00-global.md`, `.claude/rules/01-invariants.md §INV-3`

This document is the **implementation contract** for `CMP-RES-01`. The service feeds synthetic codebases and labelled CVE findings into the shared scan pool while preserving v2-era `scanipy --query` CLI semantics. Its non-negotiable boundary is INV-3: Research-mode helpers (`search_code()`) MUST NOT leak into the deterministic detection path.

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-RES-01` |
| Subsystem | Research mode (`WBS.md §15`) |
| Staging | post-core (`WBS.md §15`) — depends on Stage A having shipped `CMP-CORE-01` + `CMP-TRI-02`. |
| Depends-On | `CMP-SCM-02` (GitHub-only `search_code()`), `CMP-TRI-02` (e-process evaluation stream) (`WBS.md §20`) |
| Owner | **DEFERRED** via `CLAR-OWNER-01`. Security Analyst sign-off required (touches INV-3 — `RULE-9`). |
| INV-* touched | **INV-3** — Research-mode helpers are rejected on non-Research call paths at the SCM-02 type system boundary (`T-CMP-SCM-02-02`). The CLI shim is caller-transparent and does NOT alter `origin` of any finding. |
| Storage | `services/research/api.py` |

---

## 2. Mandate

**Verbatim WBS `Goal:` (`WBS.md §15`):**

> Preserve the GitHub-search-driven Research mode that feeds synthetic codebases and labelled CVE findings into the same pool; route labelled CVE findings to the e-process evaluation stream.

**Operational role.** `CMP-RES-01` is the v3.2 reattachment of v2-era Research mode. It does three things:

1. **Synthetic codebase feed.** Search GitHub via `CMP-SCM-02.search_code()` (Research-only API), curate the matches into synthetic codebases, and submit them to the shared scan pool through `CMP-ORCH-01` — i.e. they ride the same orchestration as customer scans, with `origin` determined by detector engine the same way.
2. **e-process evaluation stream.** Labelled CVE findings are routed into the Algorithm 6 e-process evaluation pipeline owned by `CMP-TRI-02`, with explicit covariate-shift handling.
3. **Caller-transparent `scanipy --query` shim.** The v2 CLI entry point `scanipy --query extractall --run-semgrep` continues to work; behavior is regression-tested by `TST-AC-ORCH-01c` (specifically: yields the CVE-2025-61765 path-traversal finding with `origin=deterministic-core` on a Stage-A language).

The component is research-instrumentation, not a customer-facing surface. Findings produced under Research mode are tagged `is_research=true` and **never** merged into customer-facing findings; the e-process pipeline consumes them as an evaluation stream only.

---

## 3. Interface contract

`services/research/api.py` exposes a thin Python API. The `scanipy --query` CLI is preserved as a caller-transparent shim that dispatches into this API.

### 3.1 Python API

```python
# services/research/api.py

from typing import Iterable

class ResearchCodebaseFeed:
    """Feed synthetic codebases into the shared scan pool. INV-3 boundary."""

    def __init__(self, scm: GitHubConnector, scan_api: ScanAPI) -> None:
        # scm MUST be the GitHub-only connector (CMP-SCM-02).
        # search_code() is rejected on non-GitHub connectors at the
        # type system per T-CMP-SCM-02-02.
        ...

    def search_and_submit(
        self,
        query: str,
        max_repos: int = 100,
        labels: dict[str, list[CveLabel]] | None = None,
    ) -> Iterable[ScanHandle]:
        """
        1. Resolve `query` via CMP-SCM-02.search_code() → repo list.
        2. For each repo, submit a scan via CMP-ORCH-01.submit_scan(),
           tagging the scan request with `is_research=true` and the
           caller-supplied `labels` (if any).
        3. Yield ScanHandle per submission.
        """
        ...

class ResearchEProcessStream:
    """Route labelled CVE findings to CMP-TRI-02's e-process evaluation."""

    def submit_labelled(
        self,
        finding_id: FindingId,
        cve_label: CveLabel,
        covariate_shift_metadata: CovariateShiftMeta,
    ) -> None: ...

@dataclass(frozen=True)
class CveLabel:
    cve_id: str                       # e.g. "CVE-2025-61765"
    cwe_ids: list[str]
    ground_truth: Literal["vulnerable", "not-vulnerable"]
    detector_class: str               # e.g. "path-traversal"
    language: str

@dataclass(frozen=True)
class CovariateShiftMeta:
    population_drift_score: float     # explicit, not implicit (T-CMP-RES-01-02)
    notes: str
```

### 3.2 CLI shim contract (caller-transparent)

The v2 entry point is preserved verbatim:

```
scanipy --query extractall --run-semgrep
```

The shim translates this invocation into a `ResearchCodebaseFeed.search_and_submit()` call. `TST-AC-ORCH-01c` is the binding regression: this exact CLI must yield the CVE-2025-61765 path-traversal finding with `origin=deterministic-core` on a Stage-A language (Java or Python).

**"Caller-transparent" means:**

- Argument parsing identical to v2.
- Exit-code semantics identical to v2.
- Output format identical to v2 for SARIF-stream consumers.
- No new required flags.

The shim MAY internally route into the v3.2 scan pool; the surface contract is what `TST-AC-ORCH-01c` enforces.

### 3.3 What `CMP-RES-01` MUST NOT expose

- It MUST NOT expose `search_code()` to any non-Research code path. The boundary is enforced one layer down at `CMP-SCM-02` (`T-CMP-SCM-02-02`: "Expose `search_code()` for Research mode only; reject Research-mode helpers on non-GitHub connectors at the type system").
- It MUST NOT alter `origin` of any finding. Findings produced from Research-mode-submitted scans get the same `origin` partitioning as customer findings (per detector engine — see `.claude/rules/05-determinism.md`).
- It MUST NOT modify `S_version` or accept specs into `S` outside `CMP-TRI-02`'s e-process pipeline.

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| GitHub-search query string | Operator (Research analyst) | Passed through to `CMP-SCM-02.search_code()`. |
| `max_repos` | Operator | Bounded; default 100. |
| `labels` (optional) | Curated CVE label set | Used to populate the e-process evaluation stream input. |
| CLI args (v2 shim) | `scanipy --query ...` | Verbatim v2 parsing. |

### 4.2 Outputs

| Output | Consumer | Contract |
|---|---|---|
| Scan submissions tagged `is_research=true` | `CMP-ORCH-01.submit_scan()` | Findings emitted carry the standard provenance (per `.claude/rules/02-provenance.md`); the `is_research` flag is an additional non-detection attribute. |
| Labelled findings → e-process | `CMP-TRI-02` Algorithm 6 evaluation stream | Each labelled finding submitted with covariate-shift metadata. |
| Stdout in `scanipy --query` mode | v2 caller | Caller-transparent; matches v2 byte-for-byte for stable consumers. |

---

## 5. Invariants touched

| Invariant | How `CMP-RES-01` discharges it | Test |
|---|---|---|
| **INV-3 (LLM off the detection path)** | Research findings are explicitly evaluation-stream-only (`is_research=true`); they cannot be merged into customer-facing findings or otherwise influence `origin`, `S_version`, or `env_digest` on customer scans. Spec inference (`CMP-TRI-02`) operates on labelled Research data, but acceptance is gated by Algorithm 6's e-process — an accepted spec writes a new `S_version` (per `INV-3`), and the deterministic core only ever consumes pinned `S_version`s. | `TST-AC-TRI-02a/b/c [FORTHCOMING]`, `TST-INV-3-TRI-02 [FORTHCOMING]` |
| **INV-3 (Research-helpers boundary)** | `search_code()` is exposed only to `CMP-RES-01` and rejected on every non-GitHub connector + every non-Research call site, enforced at the type system. Boundary owner: `CMP-SCM-02` (`T-CMP-SCM-02-02`). | `TST-AC-SCM-02-02 [FORTHCOMING]` — type-system test: a non-Research caller importing `search_code` fails type check / fails at runtime; the test must verify both. |
| **INV-1 hand-through** | Research-mode scans ride the same orchestration; `origin` is assigned per detector engine (`.claude/rules/05-determinism.md`). The Research label is an *additional* attribute, never a replacement for `origin`. | `TST-AC-ORCH-01c [FORTHCOMING]` — the regression test asserts `origin=deterministic-core` on the CVE-2025-61765 finding. |

`CMP-RES-01` MUST be reviewed by the Security Analyst Agent per `RULE-9` (any component touching INV-3).

---

## 6. Dependency contract

`Depends-On: CMP-SCM-02, CMP-TRI-02` (`WBS.md §20`).

| Dep | What `CMP-RES-01` assumes |
|---|---|
| `CMP-SCM-02` | The GitHub connector exposes `search_code()` typed as Research-only. The non-Research call-path rejection is enforced one layer down (`T-CMP-SCM-02-02`); `CMP-RES-01` is the *legitimate* consumer of that API and does not need to re-enforce. |
| `CMP-TRI-02` | The e-process evaluation stream accepts labelled findings + covariate-shift metadata and runs Algorithm 6 (see `DOC-ALGS.md §7`). `CMP-RES-01` is one of two upstream feeders (the other is the production triage path); both ride the same Algorithm 6 implementation but on logically separated streams. |

`CMP-RES-01` is NOT a dependency of any deterministic-core component. A core component that imports from `services/research/` would itself be in violation of INV-3 and would be rejected at code review (the `claude-review` CI check, RULE-10).

---

## 7. Failure modes and error contracts

| Failure | Detection | Response |
|---|---|---|
| Research-mode helper leaking into the main scan path | Type-system rejection at `CMP-SCM-02` (`T-CMP-SCM-02-02`); fallback runtime assertion if type system bypassed | **Hard reject at PR review.** Per `RULE-9` (Security Analyst review for INV-3 components). |
| `scanipy --query` shim regression | `TST-AC-ORCH-01c` failure on CI | Treat as a customer-impacting regression. The CLI is a stable surface; fix the routing without altering the surface contract. |
| Research scan produces a finding merged into customer-facing findings | Anomaly in `findings` table: a row with `is_research=true` exposed via customer dashboard query | Hard bug. The `is_research` flag must filter out at every customer-facing read path. |
| Covariate-shift metadata missing on labelled finding submission | Reject at `ResearchEProcessStream.submit_labelled()` boundary | `T-CMP-RES-01-02` requires *explicit* covariate-shift handling. A submission without metadata is rejected with a typed error; the operator must supply or compute the metadata. Implicit covariate-shift assumption is forbidden. |
| GitHub search API quota exhaustion | `CMP-SCM-02` HTTP-retry exhaustion | Standard `CMP-SCM-05` retry/backoff; Research operations are non-urgent and may be deferred. |
| Output drift in `scanipy --query` shim | `TST-AC-ORCH-01c` byte-diff vs. v2 golden output | Hard reject. Caller-transparency is the load-bearing property. |

### 7.1 Anti-patterns rejected

- Sharing scan IDs between Research and customer scans (must be different namespaces).
- Reading customer-tenant data from a Research scan (Research operates on synthetic / public code only; no tenant-scoped reads).
- Bypassing `CMP-TRI-02`'s e-process to "directly accept" a spec inferred from Research data — that would violate INV-3.

---

## 8. Provenance threading

`CMP-RES-01` writes the additional non-detection attribute `is_research` on every scan it submits. It does NOT touch any of the four required provenance fields.

| Field | Where | Threading rule |
|---|---|---|
| `is_research` | `scans` row (Research-tagged) | Boolean; default `false`; set `true` only by `CMP-RES-01` submission paths. Filters out at every customer-facing query. |
| `cve_label` | e-process evaluation stream input (`CMP-TRI-02`) | Optional; present on labelled submissions; carries CVE id, CWE ids, ground truth, detector class, language. |
| `covariate_shift_metadata` | e-process evaluation stream input | Optional but required for labelled submissions (`T-CMP-RES-01-02`). |

**Must NOT touch:** `origin`, `S_version`, `env_digest`, `cpg_order_hash`, `slice_fingerprint`. Findings produced from Research-mode scans inherit these from the standard worker emission paths.

---

## 9. Acceptance criteria cross-reference

`CMP-RES-01` does **not** carry its own top-level AC. Per `WBS.md §15`:

> No new top-level AC; the feature is exercised through CMP-ORCH-01 and CMP-TRI-02 ACs.

The load-bearing tests for this component therefore live upstream:

| Anchor | Verbatim source | Test artifact |
|---|---|---|
| **AC-ORCH-01c** | `SDD.md §7 CMP-ORCH-01`: > Backwards-compat: `scanipy --query extractall --run-semgrep` via Research mode still yields the CVE-2025-61765 path-traversal finding with `origin=deterministic-core` on a Stage-A language. | `TST-AC-ORCH-01c [FORTHCOMING]` — `[REGRESSION]`, the load-bearing test for the CLI shim. |
| **AC-TRI-02a** | `SDD.md §9 CMP-TRI-02`: > **[Adversarial unbounded continuation]** Over many repeated campaigns with an over-broad spec and no finite horizon supplied, realized ever-false-acceptance rate ≤ α. | `TST-AC-TRI-02a [FORTHCOMING]` — Research-mode is a feeder of the campaign data. |
| **AC-TRI-02b** | `SDD.md §9 CMP-TRI-02`: > The e-process implementation passes a martingale-property unit test (empirical `E[E_τ|H0] ≤ 1` across simulated stopping times) before production enablement. | `TST-AC-TRI-02b [FORTHCOMING]` — Gate 4 (`CLAUDE.md §15`); Research-mode does NOT exempt the gate. |
| **AC-TRI-02c** | `SDD.md §9 CMP-TRI-02`: > An accepted spec is written version-pinned as a new `S_version`; the deterministic core only ever consumes pinned specs (INV-3). | `TST-AC-TRI-02c [FORTHCOMING]` — Research-mode-driven spec acceptance respects this rule. |

Per-task verification for `T-CMP-RES-01-01..03`:

| Task | Verification |
|---|---|
| `T-CMP-RES-01-01` | `services/research/api.py` exists; `ResearchCodebaseFeed.search_and_submit()` calls `CMP-SCM-02.search_code()` and `CMP-ORCH-01.submit_scan()`. |
| `T-CMP-RES-01-02` | `ResearchEProcessStream.submit_labelled()` enforces non-null covariate-shift metadata; explicit error on missing metadata. |
| `T-CMP-RES-01-03` | `TST-AC-ORCH-01c` covers the v2 CLI shim; no new CLI surface introduced. |

Recall-claim-per-language tests of Algorithm 2 (per `WBS.md §15`) consume Research-mode-curated corpora; coverage rolled into `TST-AC-CORE-01b` per stage.

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-RES-01 |
|---|---|---|---|
| `CLAR-DEPLOY-14` | LLM provider for triage and spec inference | **RESOLVED** | Anthropic API `claude-sonnet-4-6`. The e-process pipeline (`CMP-TRI-02`) is the LLM consumer; Research-mode feeds it. |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | §1 `Owner` stays DEFERRED; Security Analyst sign-off required per `RULE-9`. |

No new CLAR-RES-* are filed by this document. The Research-mode boundary is fully derivable from `INV-3` + `T-CMP-SCM-02-02` + `WBS.md §15` + `SDD.md §7 AC-ORCH-01c`.

---

## 11. References

- `WBS.md §15 CMP-RES-01` — verbatim Purpose + tasks.
- `WBS.md §5 CMP-SCM-02` — `T-CMP-SCM-02-02` (the type-system boundary for `search_code()`).
- `WBS.md §20` — dependency DAG.
- `SDD.md §7 CMP-ORCH-01` — `AC-ORCH-01c` verbatim.
- `SDD.md §9 CMP-TRI-02` — e-process evaluation stream consumer.
- `SDD.md §2 INV-3` — LLM off the detection path.
- `PLAN.md §"Phase staging"` (Phase 8) — Research-mode rationale.
- `docs/cross-cutting/DOC-ALGS.md §7` — Algorithm 6 (e-process).
- `docs/cross-cutting/DOC-INV.md §INV-3` — boundary exposition.
- `docs/components/DOC-CMP-SCM-02.md` (dep) — the GitHub connector that exposes `search_code()`.
- `docs/components/DOC-CMP-TRI-02.md` (dep) — the e-process gate.
- `docs/components/DOC-CMP-ORCH-01.md` (consumer) — `AC-ORCH-01c` test owner.
- `.claude/rules/00-global.md §RULE-9` — Security Analyst sign-off required for INV-3 components.
- `.claude/rules/01-invariants.md §INV-3` — operational invariant.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an Implementation Agent to produce a passing `CMP-RES-01`. The load-bearing test is `TST-AC-ORCH-01c`; the load-bearing invariant is INV-3 (Research-mode helpers do not leak into the deterministic detection path).*
