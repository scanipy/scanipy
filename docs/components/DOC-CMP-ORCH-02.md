# DOC-CMP-ORCH-02 — Heuristic scheduler `SNAP-SCHED-H` (Algorithm 4)

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `SDD.md §7 CMP-ORCH-02` (Purpose, AC-ORCH-02a/b/c)
- `PLAN.md §"Algorithm 4 — Detector scheduling (heuristic)"`
- `PLAN.md §"Per-algorithm summary"` (row "Alg 4")
- `PLAN.md §"Phase 4 — Orchestrator + heuristic scheduler"` (`services/scan/scheduler.py = SNAP-SCHED-H`)
- `docs/cross-cutting/DOC-ALGS.md §5` (Algorithm 4 reference)
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` (CLAR-DEPLOY-06 SQS visibility / DLQ)
- `docs/cross-cutting/DOC-INV.md` (no INV-* owned; `AC-ORCH-02b` is INV-1-adjacent)
- `.claude/rules/00-global.md` (RULE-7 staging gate), `.claude/rules/04-staging.md`

This document is the **implementation contract** for `CMP-ORCH-02`. A code-writing agent given only this file plus the cross-cutting refs listed above must be able to produce a passing implementation without re-reading `SDD.md` (per `AC-DOC-04`).

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-ORCH-02` |
| Subsystem | Orchestration (`SDD.md §7`) |
| Module path | `services/scan/scheduler.py` (per `PLAN.md §"Phase 4"`, `CLAUDE.md §12`) |
| Staging | **cross-cutting** (`SDD.md §7`) — the scheduler runs for every language; per-`(class, language)` correctness gating is the responsibility of `CMP-CP-06` (RULE-7), not ORCH-02. |
| Depends-On | `CMP-ORCH-01` (`WBS.md §20`) |
| Owner | **DEFERRED** via `CLAR-OWNER-01` (`WBS.md §17`) |
| INV-* touched | **None directly.** `AC-ORCH-02b` (schedule-invariance of `deterministic-core` findings) is INV-1-adjacent and is **cross-checked by the Attestor (`CMP-CP-05`)**, not owned here. See `DOC-ALGS.md §5.6`. |

---

## 2. Mandate

**Verbatim SDD `Purpose:` (`SDD.md §7 CMP-ORCH-02`):**

> Snapshot-affinity grouping (amortize CPG load `L`), independent-moldable 2-approx allotment as a heuristic seed only, LPT list-scheduling with dependence-aware deferral, policy-gating classes first. No constant-factor guarantee is claimed.

**Operational role.** `CMP-ORCH-02` is a **heuristic** that orders the queued jobs minted by `CMP-ORCH-01` so that worker fleet wall-clock obeys the published p95 SLA (`AC-ORCH-02a`). It is consumed by the worker pool (`CMP-ORCH-03`); it does **not** itself execute analysis and it does **not** emit findings. Its sole numeric promise is an `[EMPIRICAL]` p95 end-to-end scan latency < 30 min at provisioned worker count `m`, with three named remediations on miss (`PLAN.md §"Algorithm 4"`):

1. Re-fit the work-estimate regression.
2. Raise `m` (worker count).
3. Re-price (push customer to a tier that yields the SLA).

`ρ≈2` from Turek–Wolf–Yu / Jansen–Ohnesorge is cited **only** as the relaxation bound of the idealised independent-moldable seed; it is **never** quoted as a guarantee of the real moldable-DAG-with-setup problem (`AC-ORCH-02c` is a literal doc-link grep test).

The scheduler's *result-independence* — different schedules over the same `(source, S_version, env_digest)` produce **identical** `deterministic-core` findings — is the operational link to INV-1. That property is licensed by **IFDS order-independence** (Algorithm 2 / `CMP-CORE-01`); the scheduler simply does not reach into SARIF bytes. The Attestor (`CMP-CP-05`) cross-checks this property at the release boundary; `CMP-ORCH-02` consumes the cross-check, it does not implement it.

---

## 3. Interface contract

### 3.1 Public Python signatures

```python
from typing import Literal, Optional
from datetime import datetime
from uuid import UUID
from dataclasses import dataclass

@dataclass(frozen=True)
class PendingJob:
    job_id: UUID
    scan_id: UUID
    snapshot_id: UUID
    detector_id: str
    detector_class: str                # 'injection', 'path-traversal', ...
    language: str                      # 'java', 'python', ...
    queued_at: datetime
    est_work: float                    # seconds; from work-estimate regression
    cpg_load_seconds: float            # L per snapshot (amortizable)
    policy_priority: int               # higher = customer-elevated; sorted first
    depends_on: frozenset[UUID]        # other job_ids that must finish first

@dataclass(frozen=True)
class ScheduledJob:
    job_id: UUID
    worker_id: str                     # ECS task ARN or worker pool slot
    start_after: datetime              # earliest dispatch time; may be queued earlier
    snapshot_group_id: str             # group key (= snapshot_id) for CPG-load amortization
    age_credit: float                  # anti-starvation: monotonically increases over wait
    rationale: Literal[
        "policy-gated",                # policy_priority bucket
        "lpt-list-scheduled",          # main LPT scheduling
        "aged-out-of-bucket",          # anti-starvation promotion
    ]

class SchedulerState:
    m: int                             # provisioned worker count (per CLAR-DEPLOY-06)
    work_estimate_model_version: str   # regression model version
    last_p95_seconds: float            # most recent published p95
    last_p95_published_at: datetime

def schedule(
    pending_jobs: list[PendingJob],
    state: SchedulerState,
) -> list[ScheduledJob]:
    """Algorithm 4 entry point. Pure function modulo state-snapshot read.
    The output order is the dispatch order; the SQS dequeue worker pool
    consumes ScheduledJob in this order. The function is deterministic
    for a given (pending_jobs, state) input — schedule-invariance of
    deterministic-core findings (AC-ORCH-02b) holds in spite of non-
    determinism in dispatch wall-clock; the Attestor verifies the
    cross-schedule equivalence."""
```

### 3.2 SQS interaction

`CMP-ORCH-02` does **not** write to SQS directly. It reads queued jobs from the per-detector queues (`CMP-ORCH-01 §4.2.2`) into a priority queue keyed by `(policy_priority, snapshot_group_id, est_work)`, and emits dispatch decisions to the worker pool. Worker pool consumption is the responsibility of `CMP-ORCH-03`; the scheduler is the **decider**, not the **dispatcher**.

Visibility-timeout interaction with `CLAR-DEPLOY-06`:

- Scan-job queue: 60 min visibility timeout. The scheduler must dispatch a job within that window or the SQS message becomes visible again to another consumer.
- Max-receive 3 then DLQ + alarm.
- The scheduler must not flap a job between "scheduled" and "deferred" — once a worker is assigned, the job is committed.

### 3.3 Algorithm 4 cost function and ordering

Per `DOC-ALGS.md §5.4` and the `PLAN.md` verbatim statement:

```
Step 1 — Snapshot-affinity grouping.
    Bucket pending_jobs by snapshot_group_id (= snapshot_id).
    Within a bucket, the CPG is loaded once (cost L) and amortized
    across all detectors that run on it.

Step 2 — Independent-moldable 2-approx allotment (heuristic seed only).
    Compute per-job moldable speedup curve s_j(w) for w ∈ {1..m}.
    Allot workers via the Turek–Wolf–Yu greedy that achieves the
    ρ≈2 bound FOR THE IDEALISED PROBLEM (independent tasks, no setup
    cost). ρ≈2 is the seed; it is NOT the guarantee for the real
    moldable-DAG-with-setup problem.

Step 3 — LPT list-scheduling with dependence-aware deferral.
    Order jobs by Longest-Processing-Time first within each
    policy_priority bucket. Jobs whose depends_on set is unmet are
    deferred to the next pass without losing their LPT order in the
    bucket.

Step 4 — Policy-gating bucket order.
    Buckets with higher policy_priority dispatch first (customer-
    elevated classes, e.g., regulatory or contractual SLAs).

Anti-starvation (age credit).
    Each pending_job accrues age_credit proportional to (now() - queued_at).
    A job whose age_credit exceeds threshold_θ_age is promoted out of
    its policy bucket into the next-higher bucket. Default θ_age = 30 min
    (matches the AC-ORCH-02a p95 budget; one budget-overshoot is the
    triggering event).
```

`m` is the provisioned worker count and is operator-set; the scheduler **does not** auto-scale (`m` change is one of the three p95-miss remediations).

### 3.4 Result-independence contract (`AC-ORCH-02b`)

`CMP-ORCH-02` must satisfy: for any two valid dispatch orders `σ_1` and `σ_2` of the same `pending_jobs` set under fixed `(S_version, env_digest)`, the SARIF blobs produced by the resulting scans **agree byte-for-byte over `origin = deterministic-core` findings**. This is licensed by:

1. **IFDS order-independence** (RHS'95) — the solver computes the meet-over-all-valid-paths solution independent of worklist order; `CMP-CORE-01` is the proof obligation.
2. **Canonical CPG ordering** (`CMP-CORE-03`, Algorithm 5) — the SARIF serialisation order is a function of `cpg_order_hash`, not of dispatch wall-clock.
3. **Per-finding `origin` set by `CMP-ORCH-03`** at emission time from the detector's `engine` field — never set by the scheduler.

The Attestor (`CMP-CP-05`) verifies the property empirically per release on the canary corpus. If a schedule-dependent diff appears on the core partition, the diagnosis is **not** a scheduler bug; it is a violation of one of (1), (2), or (3) above, and the scheduler is read-only against the partition.

---

## 4. Inputs and outputs

### 4.1 Required inputs

| Input | Source | Contract |
|---|---|---|
| `pending_jobs[]` | SQS read of per-detector queues populated by `CMP-ORCH-01 §4.2.2` | Each job carries `S_version`, `env_digest`, `snapshot_id`, `detector_id`. |
| `m` (provisioned worker count) | ECS service desired-count; operational setting | Operator-pinned; not in-band tunable. |
| `work_estimates` | `Map<detector_id, Duration>` from the work-estimate regression model | Re-fit on a p95 miss (`PLAN.md §"Algorithm 4"`). |
| `policy_priority` per job | `org_policies` table (read at scan submission by `CMP-ORCH-01`) | Stamped onto the SQS message body. |
| Operational telemetry | OpenTelemetry → CloudWatch (`CLAR-DEPLOY-07`) | p95 published; missed-p95 events drive remediation. |

### 4.2 Outputs

The scheduler emits **dispatch decisions** to the worker pool. There are **no persisted rows** owned by the scheduler:

- No `findings` row (scheduler never touches detection output).
- No `provenance_records` row (scheduler never threads provenance fields beyond what is already on the SQS message).
- No `scans` mutation (scan state transitions are owned by `CMP-ORCH-01` upon worker callback).

The scheduler does emit observability events (`scheduler.dispatch`, `scheduler.defer`, `scheduler.aged_out`) for SRE telemetry; these are logs/metrics, not persisted state.

### 4.3 SQS message hand-off shape

The scheduler does not re-encode the SQS message; it consumes the body produced by `CMP-ORCH-01 §4.2.2` and decides **when** and **to which worker** the body is delivered. Delivery is implemented by setting SQS visibility timeout and committing the worker assignment to a transient `dispatch_assignments` Redis hash (operational, not in DOC-DB).

---

## 5. Invariants touched

| Invariant | Discharge by `CMP-ORCH-02` | Test |
|---|---|---|
| **None directly.** | The scheduler is a pure orderer; it never reads or writes finding-level fields. `AC-ORCH-02b` (schedule-invariance) is the **operational manifestation** of INV-1 over the scheduler's output: cross-schedule core SARIF equivalence is licensed by IFDS order-independence (`CMP-CORE-01`) and canonical CPG ordering (`CMP-CORE-03`), and is cross-checked by the Attestor (`CMP-CP-05`). | `TST-AC-ORCH-02b [FORTHCOMING]` `[INVARIANT]` (per `WBS.md §6`); paired with `TST-AC-CP-05a` core-pipeline byte-identity. |

`CMP-ORCH-02` is **not** an INV-2 setter (does not stamp `S_version` or `env_digest`; reads them off the SQS body), **not** an INV-3 actor, **not** an INV-4 owner (no undecidable approximation), and **not** an INV-5 owner (no `cpg_order_hash` write).

---

## 6. Algorithm / data flow

```
Trigger: SQS-poll loop (per-detector queues populated by CMP-ORCH-01).
    Cadence: continuous; the scheduler tick is a soft 1-second loop
             scheduling outstanding pending_jobs against available
             worker pool capacity.

Pass 1: Snapshot-affinity bucketing.
    Group pending_jobs by snapshot_id. Within a bucket, jobs share
    the CPG load L; the scheduler dispatches them to the same worker
    where feasible (worker capacity permitting), so that the CPG is
    loaded once.

Pass 2: Independent-moldable 2-approx allotment (heuristic seed).
    For each bucket, compute the moldable speedup curve and allot
    worker counts via the Turek–Wolf–Yu greedy. This is the seed for
    Pass 3, NOT a finished schedule. ρ≈2 is the IDEALISED bound,
    explicitly NOT the real-problem guarantee (AC-ORCH-02c).

Pass 3: LPT list-scheduling with dependence-aware deferral.
    Within each policy_priority bucket, order jobs Longest-Processing-Time
    first. A job whose depends_on set has unmet members is deferred
    to the next pass without losing LPT order.

Pass 4: Policy-priority bucket dispatch order.
    Buckets ordered by descending policy_priority dispatch first.

Anti-starvation pass.
    For every pending_job whose age_credit exceeds θ_age (default
    30 min), promote into the next-higher policy_priority bucket on
    the next pass. The promoted job is dispatched as soon as worker
    capacity opens.

Dispatch.
    For each ScheduledJob in output order:
        a. Assign worker_id from the pool (ECS task ARN).
        b. Reset SQS visibility timeout to the worker's expected wall-
           clock (default 60 min per CLAR-DEPLOY-06).
        c. Emit scheduler.dispatch OTel event with the rationale.

p95 monitoring (asynchronous loop).
    Every release window, compute end-to-end scan latency p95 over the
    finished_at − started_at distribution of the `scans` table.
    If p95 > 30 min for the window:
        - Page SRE (CLAR-DEPLOY-07 alarm).
        - Open an incident with the three published remediations as
          options: refit work-estimate regression / raise m / re-price.
```

---

## 7. Failure modes and error contracts

| Failure | Detected by | Response | Persisted state |
|---|---|---|---|
| Scheduler crash / restart | ECS health check | Worker pool drains; SQS visibility timeouts return jobs to the queue; new scheduler instance picks up where the prior one left off. SQS is the authoritative pending-job store. | None lost (SQS is durable). |
| Starvation (low-priority job aged > θ_age) | Anti-starvation pass | Promote into next-higher policy bucket; dispatch on next pass. | OTel event `scheduler.aged_out`. |
| `m` set to zero | Health check | Refuse to dispatch; raise critical alarm. SQS messages remain visible. | None. |
| Scheduler-state corruption (Redis dispatch hash mismatch) | Periodic reconciler | Drop the hash; SQS visibility timeouts cause jobs to be re-delivered; new scheduler instance rebuilds from SQS. | None — SQS is the authoritative store, `dispatch_assignments` is transient. |
| Work-estimate regression severely off (jobs run 10× longer than estimate) | p95 monitor | Trigger one of the three published remediations (`PLAN.md §"Algorithm 4"`). Do not tune work_estimates in-loop (would compromise schedule invariance). | Regression model version bump (offline). |
| p95 miss for a release window | p95 monitor | SRE page; remediation per `PLAN.md`. **Do not auto-scale `m` in-loop** — `m` is operator-pinned. | Incident record (operational). |
| Job stuck (`depends_on` cycle) | Static analysis at scheduling | Reject schedule; alarm. A `depends_on` cycle is a producer bug in `CMP-ORCH-01` or `CMP-CORE-01` summary-edge computation. | None. |
| Two schedulers active simultaneously (race) | Lease lock | Loser exits; winner continues. SQS dedupes via the per-message receipt handle. | None. |

**INV-4 (safe direction) is not implicated** — the scheduler does not approximate any undecidable property. It is a heuristic against a moldable-DAG-with-setup problem and is honest about it (`AC-ORCH-02c`).

---

## 8. Provenance threading

`CMP-ORCH-02` is a **pass-through** for provenance. It does not write any of the four required fields (`origin`, `S_version`, `env_digest`, `cpg_order_hash`); they are already on the SQS message body produced by `CMP-ORCH-01` and are read by `CMP-ORCH-03` at emission time.

| Field | Source on SQS body | Threading rule |
|---|---|---|
| `S_version` | Set by `CMP-ORCH-01` at submission | Carried unchanged through dispatch. |
| `env_digest` | Set by `CMP-ORCH-01` from `snapshots.env_digest` | Carried unchanged through dispatch. |
| `origin` | Not on the SQS body — set per-finding by `CMP-ORCH-03` from `detector.engine` | Never on the scheduler's path. |
| `cpg_order_hash` | Not on the SQS body — computed by `CMP-CORE-03` during analysis | Never on the scheduler's path. |

**Must NOT touch:** any finding-level field, any provenance record, any spec row, any snapshot row, any audit signature. The scheduler is the **only** orchestration component that is allowed to be entirely provenance-blind, precisely because it never writes a finding.

---

## 9. Acceptance criteria cross-reference

The following ACs are quoted **verbatim** from `SDD.md §7 CMP-ORCH-02`. Paraphrasing an AC is a contract break (RULE-4). Every TST-AC-* is `[FORTHCOMING]` because the QA phase has not begun.

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-ORCH-02a** | > **[Empirical p95]** Production-shaped replay at the provisioned worker count yields p95 end-to-end scan latency < 30 min. | `TST-AC-ORCH-02a [FORTHCOMING]` `[EMPIRICAL]` (per `WBS.md §6`) |
| **AC-ORCH-02b** | > Two runs under different schedules produce identical `deterministic-core` findings (cross-checked by the Attestor). | `TST-AC-ORCH-02b [FORTHCOMING]` `[INVARIANT]`; paired with `TST-AC-CP-05a` |
| **AC-ORCH-02c** | > ρ≈2 appears in documentation only as the relaxation bound, never as a guarantee. | `TST-AC-ORCH-02c [FORTHCOMING]` `[UNIT]` (doc-link grep test per `WBS.md §6`) |

`AC-ORCH-02c` is enforced as a CI-time documentation grep — any `.md` file in the repo that mentions `ρ≈2` (or `rho ~ 2`, `2-approx`, `ρ ≈ 2`) without an adjacent "relaxation bound" / "heuristic seed only" qualifier fails the test. This document complies in §2, §3.3, and §6.

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on `CMP-ORCH-02` |
|---|---|---|---|
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | Owner field in §1 remains "DEFERRED" until populated. |
| `CLAR-DEPLOY-06` | Queue technology + DLQ + visibility-timeout / retry semantics | **RESOLVED** | Amazon SQS standard + per-queue DLQ; scan-job visibility 60 min, max-receive 3 (per `DOC-DEPLOY-DECISIONS.md` line 104). The scheduler must dispatch within this window. |
| `CLAR-SLA-02` | Numeric per-tenant rate-limit budgets enforced by `CMP-CP-01` | **DEFERRED** | Indirectly relevant: per-tenant API-budget exhaustion affects pending-job arrival rate; the scheduler is rate-blind otherwise. |
| (none) | Work-estimate regression model artifact + cadence | n/a | Not a `CLAR-*`; the model is an offline artifact managed by the SRE Agent and refit on a published p95 miss per `PLAN.md §"Algorithm 4"`. |

No new `CLAR-ORCH-*` items are filed by this document; every AC of `CMP-ORCH-02` is unambiguous given the cross-cutting references.

---

## 11. References

- `SDD.md §7 CMP-ORCH-02` — verbatim AC statements.
- `PLAN.md §"Algorithm 4 — Detector scheduling (heuristic)"` — verbatim algorithm and degradation response.
- `PLAN.md §"Per-algorithm summary"` — row "Alg 4" honest-labelling status (`EMPIRICAL`).
- `PLAN.md §"Phase 4 — Orchestrator + heuristic scheduler"` — file path `services/scan/scheduler.py`.
- `docs/cross-cutting/DOC-ALGS.md §5` — Algorithm 4 reference with `TST-AC-*` mapping.
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — CLAR-DEPLOY-06 (SQS visibility, DLQ).
- `docs/components/DOC-CMP-ORCH-01.md` (sibling) — submission and SQS message production.
- `docs/components/DOC-CMP-ORCH-03.md` (sibling) — worker that consumes scheduled jobs.
- `docs/components/DOC-CMP-CORE-01.md` (sibling) — IFDS order-independence, the proof source for `AC-ORCH-02b`.
- `docs/components/DOC-CMP-CORE-03.md` (sibling) — canonical CPG ordering, the proof source for `AC-ORCH-02b`.
- `docs/components/DOC-CMP-CP-05.md` (sibling, forthcoming) — Attestor cross-check of `AC-ORCH-02b`.
- `.claude/rules/00-global.md` (RULE-7 staging gate), `.claude/rules/04-staging.md` — staging discipline (scheduler is cross-cutting; per-language gating is `CMP-CP-06`).

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-ORCH-02`.*
