# DOC-CMP-SNAP-04 — Differential reflection oracle

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `SDD.md §4 CMP-SNAP-04` (Purpose, AC-SNAP-04a/b/c)
- `PLAN.md §"Falsifier CW"` (the design — "Additionally, a *differential oracle* …")
- `PLAN.md §"Engine adapters and the determinism partition"` — re-partition consequence
- `docs/cross-cutting/DOC-PROVENANCE.md §4` — re-partition record schema (this component writes them)
- `docs/cross-cutting/DOC-PARTITION.md §5` — re-partition lifecycle (one-way flip; never reverse)
- `docs/cross-cutting/DOC-INV.md §3, §6.2.a` — INV-1 hand-off; INV-4 residual-risk bound
- `docs/cross-cutting/DOC-RUNBOOK.md §6` — operational incident procedure
- `WBS.md §17 CLAR-SLA-01` (RESOLVED — 24h high-impact / 7d routine)
- `.claude/rules/00-global.md`, `.claude/rules/02-provenance.md`, `.claude/rules/05-determinism.md`

This document is the **implementation contract** for `CMP-SNAP-04`. It is the **residual-risk bound** for the undecidable-property case behind `CW-DETECT` (`CMP-SNAP-03`): when an FN slips through, the differential oracle detects it asynchronously and re-partitions affected findings from `deterministic-core` to `oracle-passthrough`.

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-SNAP-04` |
| Subsystem | Snapshotter (`SDD.md §4`) |
| Staging | Stage A |
| Depends-On | `CMP-SNAP-03`, `CMP-FND-02` (`WBS.md §20`) |
| Owner | **DEFERRED** via `CLAR-OWNER-01` |
| INV-* touched | **INV-1** (sole authorized re-partitioner of an already-stamped `origin`); **INV-4 residual-risk bound** (the `CW-DETECT` FN safety net); writes re-partition events to provenance per `DOC-PROVENANCE §4`. |

---

## 2. Mandate

**Verbatim SDD `Purpose:` (`SDD.md §4 CMP-SNAP-04`):**

> Asynchronous whole-program reflection scanner off the critical path; on disagreement with `CW-DETECT`, raise a determinism incident and retroactively re-partition affected findings from `deterministic-core` to `oracle-passthrough`.

**Operational role.** `CMP-SNAP-04` is the **independent slow oracle** that closes the residual undecidable-case risk left by `CMP-SNAP-03 CW-DETECT`. For every snapshot that `CW-DETECT` routed to the closed-world path (`precondition_status = 'closed-world'`), an independent whole-program reflection scanner runs **off the critical path** and emits its own verdict. If the oracle finds reachable reflection where `CW-DETECT` did not, a **determinism incident** is raised: every finding from that snapshot whose `origin = 'deterministic-core'` (i.e., emitted under the wrong precondition) is **retroactively re-partitioned** to `origin = 'oracle-passthrough'`. The re-partition is recorded as an **append-only event** in the signed provenance chain (`DOC-PROVENANCE §4`) so the audit history of the original `deterministic-core` label is preserved. The flip is **one-way**: only `core → oracle` is ever performed by this component; the reverse direction requires a re-snapshot under a corrected `CW-DETECT` (different `env_digest` per INV-2) (`DOC-PARTITION §5`).

---

## 3. Interface contract

`CMP-SNAP-04` runs as a background worker, dequeued from a dedicated low-priority SQS queue. It has no synchronous HTTP surface for clients; it has two internal interfaces:

### 3.1 Input: oracle-run job

```typescript
interface OracleRunJob {
    snapshot_id: string;             // uuid; the snapshot to re-evaluate
    cw_detect_verdict: PreconditionStatus;   // from CMP-SNAP-03 at snapshot time
    cw_detect_version: string;       // semver of CW-DETECT that produced the verdict
    artifact_keys: SnapshotArtifactKeys;     // from CMP-SNAP-01 (read-only)
    enqueued_at: string;             // iso-8601; basis for SLA calculation
}

type PreconditionStatus = "closed-world" | "degraded" | "full-reparse";
```

Enqueue rule: every newly-`ready` snapshot is enqueued by `CMP-SNAP-01`'s `report_status` handler **iff** its `precondition_status == 'closed-world'`. Snapshots already on the `degraded`/`full-reparse` path are not re-evaluated — their findings are not in the `deterministic-core` partition that the oracle protects.

### 3.2 Output: oracle-run record + (on disagreement) re-partition events

```typescript
interface OracleRunRecord {
    run_id: string;                          // uuid; appears in re-partition records' repartition_oracle_id
    snapshot_id: string;
    oracle_version: string;                  // semver of THIS slow oracle implementation
    oracle_verdict: "closed-world" | "not-closed-world";
    reflection_sites: ReflectionSite[];      // empty iff oracle_verdict == "closed-world"
    started_at: string;
    completed_at: string;
    agreed_with_cw_detect: boolean;          // false iff oracle_verdict != "closed-world"
}
```

Persisted to a dedicated table `snap_oracle_runs` (referenced by `provenance_records.repartition_oracle_id` per `DOC-PROVENANCE §3`):

```sql
CREATE TABLE snap_oracle_runs (
    run_id              uuid        PRIMARY KEY,
    snapshot_id         uuid        NOT NULL REFERENCES snapshots(snapshot_id),
    oracle_version      text        NOT NULL,
    cw_detect_version   text        NOT NULL,
    oracle_verdict      text        NOT NULL CHECK (
                            oracle_verdict IN ('closed-world','not-closed-world')),
    agreed              boolean     NOT NULL,
    reflection_sites    jsonb       NOT NULL DEFAULT '[]',
    started_at          timestamptz NOT NULL,
    completed_at        timestamptz NOT NULL,
    org_id              uuid        NOT NULL REFERENCES orgs(org_id)
);
CREATE INDEX idx_oracle_snapshot ON snap_oracle_runs(snapshot_id);
CREATE INDEX idx_oracle_disagree ON snap_oracle_runs(agreed) WHERE agreed = false;
```

### 3.3 Re-partition write API (in-process)

On disagreement, the oracle invokes the re-partition flow against the provenance store:

```python
def repartition_snapshot(
    snapshot_id: UUID,
    oracle_run_id: UUID,
    reason: str,
) -> RepartitionResult: ...

@dataclass
class RepartitionResult:
    affected_finding_count: int
    new_repartition_record_ids: list[UUID]
    notified_customers: list[UUID]
```

The transaction is **atomic at the snapshot grain** (DB transaction; per `DOC-PROVENANCE §4.3` *cascade semantics*): either all affected findings get a re-partition row appended, or none do.

### 3.4 Error contracts

| Error | Cause | Response |
|---|---|---|
| `SnapshotArtifactsMissing` | S3 artifacts of the snapshot have been GC'd (90d retention expired per CLAR-DEPLOY-15) | Cannot re-evaluate; log + skip the run; emit `OracleRunRecord` with `oracle_verdict = "closed-world"` (i.e., "no disagreement asserted" — safe default that preserves existing labels). |
| `OracleInternalError` | Oracle implementation fails | SQS retry up to 3×; then DLQ + SRE alarm. **Never** write a verdict on internal failure. |
| `RepartitionTxnConflict` | Concurrent re-partition attempt for the same snapshot | Serialize on `(snapshot_id, repartition_oracle_id)` unique index in `provenance_records`; second writer is a no-op (the first writer's records already exist). |

**Safe-default note (residual-risk bound).** When the oracle cannot run (e.g. artifacts GC'd), the **safe default is to leave labels in place** — the oracle is a falsifier, not a re-label engine. False oracle disagreements would over-promote findings from `core` to `oracle`, an INV-1 violation in the opposite direction.

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| `snapshot_id`, `cw_detect_verdict`, `cw_detect_version`, `artifact_keys` | SQS message enqueued by `CMP-SNAP-01` `report_status` handler | Only for snapshots with `precondition_status == 'closed-world'`. |
| Snapshot artifacts (CPG tarball, reverse-symbol index, dyn call graph) | S3 (read-only) | Per `DOC-CMP-SNAP-01 §4.2`. |
| Source tree (re-cloned if needed for whole-program scan) | `CMP-SCM-*` re-clone using stored `commit_sha` | Re-clone is the safe form; do not assume any FS-local cache. |

### 4.2 Outputs

1. **`snap_oracle_runs` row** — one per run, including agreements (the agreement record is the "no disagreement" certificate that lets the Attestor downstream prove the core partition is intact for that snapshot).
2. **Zero or more re-partition records** in `provenance_records` (per `DOC-PROVENANCE §4`) — one per affected finding, each with `record_type = 'repartition'`, `parent_record_id` pointing to the original `chain`-type record, and `repartition_oracle_id` referencing the `snap_oracle_runs` run.
3. **Customer notification** — per affected `org_id`, a notification (channel TBD per ops decision; placeholder in `DOC-RUNBOOK §6.2`) within the SLA window.

---

## 5. Invariants touched

| Invariant | How `CMP-SNAP-04` discharges it | Test |
|---|---|---|
| **INV-1 (re-partition mechanism)** | Sole authorized mutator of an already-stamped `origin`. The flip is **append-only** (parent record is never mutated; a new `record_type='repartition'` row is added with `origin = 'oracle-passthrough'`) and **one-way** (core → oracle; never the reverse). | `TST-AC-SNAP-04a` `[FORTHCOMING]`; `TST-INV-1-SNAP-04` `[FORTHCOMING]` (re-partition exactly once per affected finding) |
| **INV-4 residual-risk bound** | This component is the *bound* on the residual undecidable-case risk that `CW-DETECT` carries (a single FN). It does not own an INV-4 approximation itself; it provides the independent re-evaluation that catches FNs after the fact within the SLA window. | `TST-AC-SNAP-04a, b, c` — falsifier + SLA + provenance event tests |
| **INV-2** (preserved) | Re-partition records inherit the parent's `S_version` and `env_digest`; no new env or spec version is created by a re-partition. | (covered by `TST-INV-2-FND-02` schema test) |

---

## 6. Algorithm / data flow

### 6.1 Detection cycle (per snapshot)

```
1. SQS dequeue OracleRunJob{snapshot_id, cw_detect_verdict=closed-world, ...}.
2. Fetch snapshot artifacts from S3.
3. Run independent whole-program reflection scan (oracle implementation; see §6.2).
4. Compare oracle_verdict against cw_detect_verdict.
5. INSERT snap_oracle_runs row with both verdicts and `agreed = (oracle_verdict == "closed-world")`.
6. If agreed == false (oracle found reflection that CW-DETECT did not):
      INVOKE repartition_snapshot(snapshot_id, run_id, reason).
7. ACK SQS message.
```

### 6.2 Oracle implementation requirements

The oracle is **slower and more thorough** than `CW-DETECT`:

- Whole-program: traverses the entire dependency closure, including transitive deps.
- Higher-fidelity points-to: uses a deeper Andersen / Steensgaard variant than `CW-DETECT`'s lightweight pre-pass.
- **Independent codebase from `CW-DETECT`**: a shared bug between the two detectors defeats the purpose. The two MUST live in separate modules with separate maintainers (organizational requirement; `DOC-RUNBOOK §6.3` includes "do not share dependencies between the two detectors" as an explicit operational rule).

The oracle's own correctness is bounded by `CMP-CORP-REFL-01` (the same falsifier corpus that `CW-DETECT` is gated against). A FN in the oracle would mean an INV-4 residual-risk leak that nothing catches; the corpus discipline is the operational defense.

### 6.3 Re-partition transaction (atomic, snapshot-grained)

Per `DOC-PROVENANCE §4`:

```sql
BEGIN;

-- Identify every finding-kind record from this snapshot that is currently core.
WITH affected AS (
  SELECT id, slice_fingerprint, rule_id, detector_id, S_version, env_digest,
         org_id, codebase_id, commit_sha, snapshot_digest
    FROM provenance_records
   WHERE snapshot_id = :snapshot_id
     AND record_type = 'chain'
     AND origin = 'deterministic-core'
     AND detector_engine IN ('ifds', 'ide')
)
-- Append one re-partition row per affected finding.
INSERT INTO provenance_records (
    parent_record_id, record_type, created_at,
    org_id, codebase_id, commit_sha, scm_provider,
    snapshot_id, snapshot_digest, precondition_status,
    S_version, env_digest,
    cpg_order_hash, cpg_order_hash_annotation, fingerprint_class,  -- cpg_order_hash NULL for repartition
    rule_id, spec_id, detector_id, detector_engine,
    sarif_hash, origin, determinism_partition,
    repartition_reason, repartition_oracle_id,
    kms_key_arn, kms_key_version, signature, signature_alg,
    claim_label
)
SELECT
    affected.id, 'repartition', now(),   -- id auto-generated by gen_random_uuid() default
    -- (rest inherited from parent record; origin flipped) ...
    'oracle-passthrough', 'oracle-passthrough',
    :reason, :oracle_run_id,
    -- (signature computed by CMP-FND-03 signer in this same transaction)
    -- ...
    'EMPIRICAL'                              -- per DOC-PROVENANCE §5: oracle-passthrough -> EMPIRICAL
  FROM affected;

-- Update findings table mirror (CMP-FND-02) so the live UI reflects the new origin.
UPDATE findings
   SET origin = 'oracle-passthrough',
       determinism_partition = 'oracle-passthrough'
 WHERE snapshot_id = :snapshot_id
   AND origin = 'deterministic-core'
   AND detector_engine IN ('ifds', 'ide');

-- (Outside the transaction): emit customer notification to affected orgs.

COMMIT;
```

**Key properties (mirror `DOC-PROVENANCE §4`):**

1. **Append-only** — original `record_type='chain'` records are never UPDATEd; only `record_type='repartition'` is inserted.
2. **One-way flip** — every re-partition row has `origin = 'oracle-passthrough'`. The reverse direction is not a re-partition event; it requires a fresh snapshot under a corrected `CW-DETECT` (different `env_digest`).
3. **Atomic at snapshot grain** — either every affected finding gets its row or none does.
4. **Cascade** — a single oracle disagreement may flip many findings (every `deterministic-core` finding from the affected snapshot whose `detector_engine ∈ {ifds, ide}`).
5. **No new `cpg_order_hash`** — the parent's hash is authoritative; the re-partition does not re-run Algorithm 5.

### 6.4 SLA on labeling-correction window

Per `CLAR-SLA-01` (RESOLVED 2026-05-23):

| Incident class | Window |
|---|---|
| High-impact (production tenant, public CVE class) | **24 h** from SQS enqueue to repartition + notification |
| Routine | **7 d** from SQS enqueue to repartition + notification |

Operational measurement: `T_repartition = repartition_record.created_at - snap_oracle_runs.row enqueued_at`. The percentile of `T_repartition` per incident class is reported on the SLA dashboard; misses are paged. The numeric SLA is finalized at Stage A go-live per `CLAR-SLA-01`.

---

## 7. Failure modes and error contracts

| Failure | Detection | Response |
|---|---|---|
| Snapshot artifacts GC'd before oracle ran | S3 `NoSuchKey` | Skip; emit agreement row with reason `artifacts-gced`. Operational signal: increase SLA window for older snapshots if the rate climbs (see `DOC-RUNBOOK §6`). |
| Oracle disagreement on an oracle-passthrough finding | (cannot happen; only `core` findings are at risk) | Defensive check; if encountered, log error + alarm. |
| Re-partition transaction conflict (two oracles process the same snapshot in parallel) | DB unique constraint on `(snapshot_id, repartition_oracle_id)` in re-partition rows | Second writer is a no-op. |
| Oracle FN (false negative — oracle agrees with CW-DETECT when reflection is in fact present) | Caught only by the corpus discipline (`CMP-CORP-REFL-01`) at release time | Release-blocker test for the oracle, mirroring `AC-SNAP-03a` for `CW-DETECT` (the oracle is gated against the same corpus). |
| Customer notification delivery failure | Notification dispatcher | Retry with exponential backoff per `CMP-SCM-05`-style retry module; the re-partition record itself is durable. |

**What this component must never do (per `DOC-RUNBOOK §6.3`):**

- **Never** flip `oracle-passthrough → deterministic-core` (the reverse direction is not a re-partition; it requires a fresh snapshot under a different `env_digest`).
- **Never** mutate the original `finding`-kind provenance record; append a re-partition record instead.
- **Never** drop a finding because it was re-partitioned (`status` is not touched; only `origin`).
- **Never** modify `S_version`, `env_digest`, `cpg_order_hash`, or `slice_fingerprint` on the original record.

---

## 8. Provenance threading

`CMP-SNAP-04` writes:

| Field | Where | Threading rule |
|---|---|---|
| `snap_oracle_runs` row | dedicated table | One per run (agreement or disagreement). |
| New `provenance_records` rows | provenance table; `record_type = 'repartition'` | One per affected finding; per `DOC-PROVENANCE §4`. |
| `origin` (on the new repartition row) | always `'oracle-passthrough'` | The one-way flip rule. |
| `determinism_partition` (on the new repartition row) | always `'oracle-passthrough'` | Mirrors `origin`. |
| `repartition_reason` | new row | Short description (e.g. `"oracle-found-spring-proxy-at-X.java:42"`). |
| `repartition_oracle_id` | new row | FK to `snap_oracle_runs(id)` (table to be added — `CLAR-DB-03`). |
| `parent_record_id` | new row | FK to the original `finding`-kind record. |
| `cpg_order_hash` | new row | **NULL** on repartition rows (not re-computed). |
| `claim_label` | new row | `'EMPIRICAL'` (per `DOC-PROVENANCE §5` mapping: `oracle-passthrough → EMPIRICAL`). |

**Must NOT touch:** original `finding`-kind rows (they are immutable post-sign). Re-partition is by **append**, not by **update**.

---

## 9. Acceptance criteria cross-reference

Quoted verbatim from `SDD.md §4 CMP-SNAP-04`. Paraphrasing an AC is a contract break (RULE-4). All TST-AC-* are `[FORTHCOMING]`.

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-SNAP-04a** | > A seeded `CW-DETECT` false negative is detected by the oracle and triggers re-partitioning of exactly the affected findings. | `TST-AC-SNAP-04a` `[FORTHCOMING]` — falsifier: seed an FN into the corpus, run end-to-end, assert (i) oracle disagrees, (ii) exactly the affected findings flip, (iii) un-affected findings remain `deterministic-core`. |
| **AC-SNAP-04b** | > The labeling-correction window (fast decision → async oracle verdict) is measured and a contractual SLA value is produced for it. | `TST-AC-SNAP-04b` `[FORTHCOMING]` — measurement test: percentile distribution of `T_repartition` per incident class; matches `CLAR-SLA-01` window (24h / 7d). |
| **AC-SNAP-04c** | > Every re-partition event is written to provenance. | `TST-AC-SNAP-04c` `[FORTHCOMING]` — assert every re-partition produces a `record_type='repartition'` row linked to the parent via `parent_record_id` and to the oracle run via `repartition_oracle_id`. |

Invariant tests cross-referenced:

- `TST-INV-1-SNAP-04 [FORTHCOMING]` — re-partition exactly once per affected finding; original record immutable.

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-SNAP-04 |
|---|---|---|---|
| `CLAR-SLA-01` | Differential-oracle labeling-correction window | **RESOLVED** | 24h high-impact / 7d routine. Numeric finalize at Stage A go-live. |
| `CLAR-DEPLOY-15` | Per-artifact retention | **RESOLVED** | CPG-class artifacts 90d; oracle runs against snapshots older than 90d cannot re-evaluate (safe-default agreement row). |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | §1 `Owner` stays DEFERRED. |

No new CLAR-SNAP-* are filed by this document.

---

## 11. References

- `SDD.md §4 CMP-SNAP-04` — verbatim ACs.
- `PLAN.md §"Falsifier CW"` — design source (differential oracle + retroactive re-partition).
- `PLAN.md §"Engine adapters and the determinism partition"` — re-partition consequence.
- `docs/cross-cutting/DOC-PROVENANCE.md §4` — re-partition record schema (canonical; this component writes them).
- `docs/cross-cutting/DOC-PARTITION.md §5` — re-partition lifecycle.
- `docs/cross-cutting/DOC-INV.md §3 (INV-1), §6.2.a (INV-4)`.
- `docs/cross-cutting/DOC-RUNBOOK.md §6` — operational incident procedure.
- `docs/components/DOC-CMP-SNAP-01.md` (sibling) — enqueue source.
- `docs/components/DOC-CMP-SNAP-03.md` (sibling) — `CW-DETECT` (upstream verdict that this component re-evaluates).
- `docs/components/DOC-CMP-FND-02.md` (forthcoming sibling) — `findings` mirror update.
- `docs/components/DOC-CMP-FND-03.md` (forthcoming sibling) — signed-chain writer.
- `WBS.md §17 CLAR-SLA-01` — resolved SLA window.
- `.claude/rules/05-determinism.md`, `.claude/rules/02-provenance.md`.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-SNAP-04`. The component's reason for existence is the residual-risk bound on `CW-DETECT`; without it, an undetected FN is invisible at re-run (the canary test reproduces the wrong path) — the differential oracle is the only line of defense.*
