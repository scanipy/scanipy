# DOC-CMP-ORCH-03 — Detector-agnostic worker (per-finding `origin` setter; INV-1 owner)

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `SDD.md §7 CMP-ORCH-03` (Purpose, AC-ORCH-03a/b)
- `PLAN.md §"Phase 4 — Orchestrator + heuristic scheduler"` (`tools/scan/worker/worker.py` loads the CPG once, runs IFDS or oracle, stamps `origin` and `determinism_partition`)
- `PLAN.md §"Engine adapters and the determinism partition"` (the partition contract this component implements)
- `docs/cross-cutting/DOC-PARTITION.md §3, §4, §7` (engine→origin mapping; canonical setter pseudocode; common mistakes)
- `docs/cross-cutting/DOC-PROVENANCE.md §2, §3, §10` (four required fields; per-component threading table row for `CMP-ORCH-03`)
- `docs/cross-cutting/DOC-INV.md §3, §4` (INV-1, INV-2 owner maps)
- `docs/cross-cutting/DOC-API.md §4.5, §5` (worker callback; Finding object shape)
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` (CLAR-DEPLOY-06 SQS visibility 60 min for scan jobs)
- `docs/cross-cutting/DOC-DB.md §4.12` (`findings` table — INV-1/2/5 anchor)
- `.claude/rules/00-global.md` (RULE-6), `.claude/rules/02-provenance.md`, `.claude/rules/05-determinism.md` (canonical setter pseudocode — quoted verbatim in §3.3 below)

This document is the **implementation contract** for `CMP-ORCH-03`. A code-writing agent given only this file plus the cross-cutting refs listed above must be able to produce a passing implementation without re-reading `SDD.md` (per `AC-DOC-04`). **This component is the canonical INV-1 setter site** — the only place in the pipeline where per-finding `origin` is assigned at emission time. Subsequent components (`CMP-FND-01..03`) read `origin`; they never reassign it. The sole authorised re-assignment elsewhere is `CMP-SNAP-04` re-partitioning (append-only, per `DOC-PARTITION §5`).

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-ORCH-03` |
| Subsystem | Orchestration (`SDD.md §7`) |
| Module path | `tools/scan/worker/worker.py` (per `PLAN.md §"Phase 4"`, `CLAUDE.md §12`) |
| Staging | Stage A (Java + Python core classes; oracle-passthrough detectors run cross-stage) |
| Depends-On | `CMP-CORE-01`, `CMP-DET-02`, `CMP-FND-01` (`WBS.md §20`) |
| Owner | **DEFERRED** via `CLAR-OWNER-01` (`WBS.md §17`) |
| INV-* touched | **INV-1 owner** (per-finding `origin` setter; see `DOC-PARTITION.md §4`); **INV-2** (threads `S_version` and `env_digest` onto every emitted finding from the SQS message and `snapshots` row); **INV-5 carrier** (passes `cpg_order_hash` from `CMP-CORE-03` through to every finding with the conditional-canonicality annotation). |

---

## 2. Mandate

**Verbatim SDD `Purpose:` (`SDD.md §7 CMP-ORCH-03`):**

> Load the snapshot CPG once, resolve the detector via the registry, run IFDS for core classes or the oracle adapter otherwise, stamp `origin` and `determinism_partition`, emit SARIF.

**Operational role.** `CMP-ORCH-03` is the **detector-agnostic worker** that ECS Fargate tasks run inside the pinned analysis container image (`env_digest`, `CMP-SNAP-05`). It:

1. Polls the per-detector SQS queue (`CMP-ORCH-01 §4.2.2`) and receives a job message scheduled by `CMP-ORCH-02`.
2. **Loads the snapshot CPG once** from the S3 keys persisted by `CMP-SNAP-01` (per-job amortisation that `CMP-ORCH-02 §3.3` step 1 exploits).
3. **Resolves the detector** via the `CMP-DET-02` registry, reading its `engine` field.
4. **Runs IFDS/IDE via `CMP-CORE-01`** for `engine ∈ {ifds, ide}`, or the **oracle adapter** (Semgrep / Joern CPG query / CodeQL / external) for `engine ∈ {semgrep, cpg-query, external}`.
5. **Stamps `origin` and `determinism_partition` per finding** (the per-finding INV-1 setter; pseudocode in §3.3 is byte-identical to `.claude/rules/05-determinism.md`).
6. **For `mixed`-class detectors**, emits per-finding `origin` (some core, some oracle) without blurring — never a single `origin` for the whole result set (`AC-ORCH-03b`).
7. **Threads the four required provenance fields** onto every finding (`origin`, `S_version`, `env_digest`, `cpg_order_hash` with `canonical iff fingerprint_class = strong`) and passes the SARIF blob to `CMP-FND-01` via the result S3 URI returned in the worker callback to `CMP-ORCH-01`.
8. **Reports job status** to `CMP-ORCH-01` via HMAC-bearer `POST /api/v1/jobs/{job_id}/status` (`AC-ORCH-01b`).

ORCH-03 does **not** normalise SARIF (`CMP-FND-01` does), does **not** compute the slice fingerprint (`CMP-CORE-02` does), and does **not** compute `cpg_order_hash` (`CMP-CORE-03` does). It is the **assembly point** that pulls those values together onto each finding.

---

## 3. Interface contract

### 3.1 Worker entry-point Python signatures

```python
from typing import Literal, Iterable, Optional
from uuid import UUID
from dataclasses import dataclass

# ----- SQS message body shape (produced by CMP-ORCH-01 §4.2.2) ------------

@dataclass(frozen=True)
class WorkerJob:
    job_id: UUID
    scan_id: UUID
    snapshot_id: UUID
    codebase_id: UUID
    commit_sha: str                          # 40-hex
    detector_id: str
    S_version: str                           # semver — INV-2; from scan submission
    env_digest: str                          # "sha256:" + 64 hex; INV-2
    policy_overrides: dict
    hmac_key_id: str                         # for the report-status callback
    callback_path: str                       # "/api/v1/jobs/{job_id}/status"

# ----- Detector record returned by CMP-DET-02 registry --------------------

@dataclass(frozen=True)
class Detector:
    detector_id: str
    engine: Literal["ifds", "ide", "semgrep", "cpg-query", "external"]
    detector_class: str                      # 'injection', 'path-traversal', ...
    is_mixed: bool                           # AC-ORCH-03b
    determinism_partition: Literal[          # derived in manifest from engine
        "deterministic-core", "oracle-passthrough"
    ]
    specs: list["Spec"]                      # combinator-DSL specs (core); or adapter config (oracle)

# ----- Per-finding emission shape -----------------------------------------
#   This is the WORKER-internal shape. The SARIF blob produced by
#   CMP-FND-01 maps to DOC-API.md §5 Finding object.

@dataclass
class Finding:
    # detection content -----------------------------------------------------
    rule_id: str
    detector_id: str
    detector_class: str
    severity: Literal["info", "low", "medium", "high", "critical"]
    message: str
    physical_location: dict                  # {"uri": str, "start_line": int, ...}
    # mixed-detector hint (AC-ORCH-03b) ------------------------------------
    from_core_engine: Optional[bool] = None  # set by the detector adapter on
                                             # each emission when detector.is_mixed.
                                             # MUST be non-None on mixed detectors;
                                             # the setter raises if missing.
    # provenance fields (set/threaded by this worker) ----------------------
    origin: Optional[Literal[                # set by stamp_origin() in §3.3
        "deterministic-core", "oracle-passthrough"]] = None
    determinism_partition: Optional[Literal[
        "deterministic-core", "oracle-passthrough"]] = None
    S_version: Optional[str] = None          # threaded from WorkerJob
    env_digest: Optional[str] = None         # threaded from WorkerJob
    cpg_order_hash: Optional[bytes] = None   # from CMP-CORE-03 (32-byte sha256)
    cpg_order_hash_annotation: str = (
        "canonical iff fingerprint_class = strong"
    )                                        # INV-5 — pinned literal
    fingerprint_class: Optional[Literal["strong", "weak"]] = None
    slice_fingerprint: Optional[bytes] = None  # from CMP-CORE-02
    witness_blob_uri: Optional[str] = None
    engine: Optional[Literal[                # mirror of detector.engine
        "ifds", "ide", "semgrep", "cpg-query", "external"]] = None
    precondition_status: Optional[Literal[
        "closed-world", "degraded", "full-reparse"]] = None  # from snapshots

# ----- Worker top-level entry point ---------------------------------------

def run_detector(
    detector: Detector,
    snapshot: "SnapshotHandle",              # bound to the loaded CPG + indices
    spec_set: "SpecSet",                     # the registered specs for this S_version
) -> set[Finding]:
    """Run `detector` against `snapshot`, returning provenance-threaded
    findings. This is the INV-1 setter site (see §3.3) and the INV-2
    threading site for `S_version` + `env_digest`. The cpg_order_hash
    is sourced from CMP-CORE-03 via the snapshot handle."""
```

### 3.2 SARIF emission and worker callback

After `run_detector` returns:

1. Persist the SARIF blob to `s3://orgs/{org_id}/codebases/{codebase_id}/sarif/{scan_id}/{detector_id}.sarif.json` (key path is operational, not contractual).
2. Call `POST /api/v1/jobs/{job_id}/status` with HMAC bearer (per `DOC-API.md §4.5`):

```json
{
  "job_id":                "uuid",
  "scan_id":               "uuid",
  "status":                "done",
  "S_version":             "semver",
  "env_digest":            "sha256:...",
  "findings_count":        42,
  "core_partition_count":  30,
  "oracle_partition_count": 12,
  "result_uri":            "s3://...",
  "witness_uri":           "s3://...",
  "error":                 null
}
```

The HMAC is computed per `DOC-CMP-ORCH-01 §3.3` against the canonical request. `CMP-FND-01` consumes `result_uri` to perform SARIF normalisation and persistence to the `findings` table (`DOC-DB.md §4.12`).

### 3.3 The per-finding `origin` setter — verbatim from `.claude/rules/05-determinism.md`

The following pseudocode is **byte-identical** to the canonical pattern in `.claude/rules/05-determinism.md §"How origin is set"`. Any deviation is a contract break. An expanded form with error-handling boilerplate appears in `DOC-PARTITION.md §4`; both are normative; the rules-file form is the primary reference.

```python
# In CMP-ORCH-03 (detector-agnostic worker):
if detector.engine in ("ifds", "ide"):
    origin = "deterministic-core"
else:
    origin = "oracle-passthrough"

# For mixed detectors: set per-finding, not per-result-set.
for finding in results:
    finding.origin = "deterministic-core" if finding.from_core_engine else "oracle-passthrough"
```

**Operational requirements layered onto this pattern (per `DOC-PARTITION.md §4`):**

1. `CORE_ENGINES = ("ifds", "ide")`; `ORACLE_ENGINES = ("semgrep", "cpg-query", "external")`. The detector registry (`CMP-DET-02`, `AC-DET-02b/c`) rejects any other engine value at registration time. If `detector.engine` is outside both sets at runtime, the worker raises `InvariantViolation` — it never guesses a default `origin`. This is the INV-4-style **safe direction**: silent fallback on origin would mis-partition findings.
2. For `mixed` detectors (`detector.is_mixed = True`, per `AC-ORCH-03b`): the detector adapter **must** set `finding.from_core_engine` on every emission. If `finding.from_core_engine is None` on a mixed detector, the worker raises — not silently falls back. See §7 failure modes.
3. The setter is the **only** site in the emit path that writes `origin`. `CMP-FND-01` (normaliser), `CMP-FND-02` (schema), and `CMP-FND-03` (signed provenance) read `origin`; they never reassign it. The only authorised re-assignment is `CMP-SNAP-04` differential-oracle re-partitioning (append-only, per `DOC-PARTITION.md §5`).
4. `finding.determinism_partition = finding.origin` after the assignment (legacy mirror; both columns must agree per `DOC-DB.md §4.12`).
5. Per `AC-ORCH-03a`, the schema NOT NULL constraint on `findings.origin` (`DOC-DB.md §4.12`) is the **belt** to this **braces** in-worker assertion. A finding leaves this worker with `origin ∈ {"deterministic-core", "oracle-passthrough"}` — never `None`, never `"mixed"`.

### 3.4 Mixed-detector contract (`AC-ORCH-03b`)

A mixed detector (e.g., `crypto-misuse` with both IFDS taint propagation and CPG pattern matches) emits findings tagged at the adapter level:

```python
# Inside a mixed detector adapter:
for f in ifds_results:
    f.from_core_engine = True               # IFDS portion -> deterministic-core
    yield f
for f in pattern_results:
    f.from_core_engine = False              # CPG query portion -> oracle-passthrough
    yield f
```

The worker's per-finding setter then routes each finding to its correct partition (`DOC-PARTITION.md §3.1`). A single finding is **never** written with `origin = "mixed"`; that value is not in the enum (`DOC-DB.md §4.12 CHECK constraint`).

### 3.5 Error contracts (worker-side)

| Condition | Worker action |
|---|---|
| SQS message body fails Pydantic validation | Reject; SQS retry up to max-receive=3 then DLQ. |
| Detector unknown in registry | Worker fails; reports `status=failed` with `error.code = "detector_not_found"`. |
| `engine` outside enumerated set at runtime | `InvariantViolation` raised; worker fails; alarm. (`CMP-DET-02` should have rejected at registration; this is defence in depth.) |
| Mixed detector emits a finding with `from_core_engine = None` | `InvariantViolation` raised; worker fails; alarm. (Detector adapter bug.) |
| SARIF blob fails `CMP-FND-01` validation | Worker reports `status=failed`; SARIF blob retained at `result_uri` for triage. |
| HMAC sign failure on callback | Worker retries with a fresh key fetch up to 3×; then alarm. |
| Worker timeout (60 min visibility, `CLAR-DEPLOY-06`) | SQS returns message to queue; max-receive=3 → DLQ. |

---

## 4. Inputs and outputs

### 4.1 Required inputs

| Input | Source | Contract |
|---|---|---|
| `WorkerJob` SQS message | Per-detector SQS queue (populated by `CMP-ORCH-01`, scheduled by `CMP-ORCH-02`) | Carries `S_version`, `env_digest`, detector, snapshot references. |
| Snapshot artefacts (CPG, indices, ΔG, precondition_status) | S3 keys minted by `CMP-SNAP-01` | Loaded once per worker job; CPG-load amortised across detectors on the same snapshot (`CMP-ORCH-02` Pass 1). |
| `Detector` record | `CMP-DET-02` registry | Provides `engine`, `is_mixed`, specs. |
| `cpg_order_hash` + `fingerprint_class` | `CMP-CORE-03` (Algorithm 5) and `CMP-CORE-02` (Algorithm 3) on the loaded CPG | INV-5; carried onto every emitted finding from this snapshot. |
| `precondition_status` | `snapshots.precondition_status` (from `CMP-SNAP-01`) | Carried onto every finding (`DOC-DB.md §4.12 NOT NULL`). |
| HMAC callback key | `WorkerJob.hmac_key_id` + secret fetched from Secrets Manager (`CLAR-DEPLOY-05`) | Per-job rotation (per `DOC-API.md §2.3`). |

### 4.2 Persisted rows owned by `CMP-ORCH-03`

`CMP-ORCH-03` itself does **not** INSERT into `findings` — the worker writes SARIF to S3 and reports the URI to `CMP-ORCH-01`; `CMP-FND-01` is the normaliser that persists `findings` rows from that SARIF. However, the worker **assembles every value** that `CMP-FND-01` then writes. The cross-component threading table in `DOC-PROVENANCE.md §10` row for `CMP-ORCH-03` lists exactly the fields the worker sets on each finding:

| Field | Set by `CMP-ORCH-03` | Sourced from |
|---|---|---|
| `origin` | **yes** (per-finding INV-1 setter) | `detector.engine` (with mixed-detector branch on `finding.from_core_engine`) |
| `determinism_partition` | **yes** (mirror of `origin`) | derived from `origin` |
| `S_version` | **yes** (threaded onto every finding) | `WorkerJob.S_version` |
| `env_digest` | **yes** (threaded onto every finding) | `WorkerJob.env_digest` (also equal to `snapshots.env_digest`) |
| `cpg_order_hash` + `cpg_order_hash_annotation` | **carried** (pass-through; not computed here) | `CMP-CORE-03` on the loaded CPG |
| `fingerprint_class` | **carried** | `CMP-CORE-02` (computed during slice fingerprinting) |
| `slice_fingerprint` | **carried** | `CMP-CORE-02` |
| `witness_blob_uri` | **set if present** (oracle findings may omit) | IFDS witness extraction; written to S3 by worker |
| `engine` | **yes** (mirror of `detector.engine`) | `detector.engine` |
| `precondition_status` | **carried** | `snapshots.precondition_status` |
| `commit_sha`, `snapshot_id`, `scan_id`, `codebase_id`, `org_id` | **carried** | `WorkerJob` + S3 key derivation |

### 4.3 SQS message acknowledgement

The worker `DeleteMessage`s the SQS message only **after** the callback `POST /api/v1/jobs/{job_id}/status` has been acknowledged by `CMP-ORCH-01` with `204 No Content`. If the callback fails, the message is left to time out and retry; idempotency is enforced by `CMP-ORCH-01` step (c) in `DOC-CMP-ORCH-01 §6`.

---

## 5. Invariants touched

| Invariant | Discharge by `CMP-ORCH-03` | Test |
|---|---|---|
| **INV-1 (origin partition) — primary setter** | `§3.3` setter assigns `origin` per finding from `detector.engine`, with the mixed-detector branch on `from_core_engine`. Schema NOT NULL on `findings.origin` and `findings.determinism_partition` (`DOC-DB.md §4.12`) backstops any miss. A single finding is never written with `origin = "mixed"`. Re-assignment is reserved for `CMP-SNAP-04` (append-only, `DOC-PARTITION.md §5`). | `TST-AC-ORCH-03a [FORTHCOMING]` `[INVARIANT]`, `TST-AC-ORCH-03b [FORTHCOMING]` `[INVARIANT]`, `TST-INV-1-ORCH-03 [FORTHCOMING]` |
| **INV-2 (versioned parameters)** | Threads `S_version` from `WorkerJob.S_version` (bound by `CMP-ORCH-01` at scan submission) and `env_digest` from `WorkerJob.env_digest` (sourced by `CMP-SNAP-01` from the container image digest). Every emitted finding carries both fields. Schema NOT NULL on `findings.S_version` and `findings.env_digest` backstops a miss. | `TST-INV-2-ORCH-03 [FORTHCOMING]` |
| **INV-5 (conditional canonicality) — carrier** | Carries `cpg_order_hash` from `CMP-CORE-03` and the pinned-literal annotation `canonical iff fingerprint_class = strong` onto every emitted finding. Never re-computes the hash; never strips the annotation. Mixed detectors inherit the same hash from the snapshot's loaded CPG. | `TST-INV-5-FND-03 [FORTHCOMING]` (chain-level; the worker is upstream of `CMP-FND-03`) |
| **INV-3 (LLM off the detection path) — fence** | `CMP-ORCH-03` consumes specs only via `CMP-DET-02` and the pinned `S_version`. It never imports an LLM client; it never executes a spec that is not in the registered, version-pinned set. The Attestor runs with `LLM_TRIAGE=off` (`CMP-CP-05`) to verify byte-identical SARIF independent of triage. | (no direct ORCH-03 test; covered by `TST-INV-3-CP-05`) |

`CMP-ORCH-03` is **not** an INV-4 owner (the undecidable-property approximations live in `CMP-SNAP-03 CW-DETECT` and `CMP-DET-01` DSL closure). It does, however, **enforce one operational safe direction**: the per-finding setter raises rather than guesses when `detector.engine` is outside the enumerated set or when a mixed detector omits `from_core_engine` (see §7).

---

## 6. Algorithm / data flow

```
Trigger: SQS dequeue from the per-detector queue (scheduled by CMP-ORCH-02).
        Message body = WorkerJob (§3.1).

    1.  Validate WorkerJob schema; reject malformed (SQS retry up to 3).
    2.  Look up Detector via CMP-DET-02 registry.
        If engine not in CORE_ENGINES ∪ ORACLE_ENGINES: InvariantViolation.
    3.  Load snapshot artefacts from S3 keys (CPG tarball, reverse-symbol
        index, dynamic call graph, ΔG, precondition_status record).
        The CPG is loaded once; subsequent detectors on the same snapshot
        scheduled to this worker reuse the in-memory CPG (CMP-ORCH-02 Pass 1).
    4.  Compute cpg_order_hash (delegates to CMP-CORE-03; cached per snapshot).
    5.  Branch on detector.engine:
            engine ∈ {"ifds","ide"}      -> CMP-CORE-01 solver with detector.specs.
            engine ∈ {"semgrep","cpg-query","external"}
                                         -> oracle adapter (Semgrep / Joern
                                            CPG-query / CodeQL / external CLI).
    6.  For each emitted Finding:
            a.  Compute slice_fingerprint + fingerprint_class via CMP-CORE-02.
            b.  Stamp origin via §3.3 setter:
                    if detector.is_mixed:
                        require finding.from_core_engine is not None
                                      (raise InvariantViolation otherwise);
                        finding.origin = ("deterministic-core"
                                          if finding.from_core_engine
                                          else "oracle-passthrough")
                    else:
                        finding.origin = ("deterministic-core"
                                          if detector.engine in ("ifds","ide")
                                          else "oracle-passthrough")
            c.  finding.determinism_partition = finding.origin.
            d.  finding.S_version       = WorkerJob.S_version.
            e.  finding.env_digest      = WorkerJob.env_digest.
            f.  finding.cpg_order_hash  = cpg_order_hash.
            g.  finding.cpg_order_hash_annotation =
                    "canonical iff fingerprint_class = strong".
            h.  finding.engine          = detector.engine.
            i.  finding.precondition_status = snapshot.precondition_status.
            j.  If a witness slice exists, persist it to S3 and set
                    finding.witness_blob_uri.
            k.  Assert finding.origin in {"deterministic-core",
                                          "oracle-passthrough"} (INV-1 belt).
    7.  Pass findings to CMP-FND-01 in-process for SARIF normalisation
        + canonical CPG-order serialisation. Persist the SARIF blob to S3.
    8.  POST /api/v1/jobs/{job_id}/status with HMAC bearer (§3.2).
        Body includes core_partition_count / oracle_partition_count for
        downstream attestation routing.
    9.  On 204 ack: DeleteMessage from SQS. Otherwise: leave to retry.
```

The per-detector run is the only locus in the pipeline where `origin` enters a finding row. Every component downstream (`CMP-FND-01`, `CMP-FND-02` schema, `CMP-FND-03` signed chain) reads the value the worker wrote.

---

## 7. Failure modes and error contracts

| Failure | Detected by | Response | Persisted state |
|---|---|---|---|
| SQS body malformed | Pydantic | Reject; SQS retry up to max-receive=3 then DLQ. Alarm on DLQ depth (`CLAR-DEPLOY-07`). | None. |
| Detector unknown | `CMP-DET-02` lookup | Worker reports `status=failed`, `error.code = "detector_not_found"`. SQS message NOT requeued — failure is deterministic. | `scans` job row → `failed`. |
| `detector.engine` outside enumerated set at runtime | `§3.3` setter | `InvariantViolation` raised. **Fail-closed**: never guess an `origin`. Worker reports `status=failed`; SRE-paged. (Should have been caught at `CMP-DET-02 AC-DET-02b`; this is defence in depth.) | `scans` job row → `failed`. |
| Mixed detector emits `finding.from_core_engine = None` | `§3.3` setter | `InvariantViolation` raised. **Fail-closed**: never guess. Detector adapter bug; alarm. | `scans` job row → `failed`. |
| CPG load fails (S3 read or tarball corrupt) | Worker | Retry once; then `status=failed`. CPG re-derivation requires re-snapshotting (`DOC-RUNBOOK §4.2`). | `scans` job row → `failed`. |
| IFDS solver timeout (per-detector budget exceeded) | `CMP-CORE-01` | Worker reports `status=failed`, `error.code = "solver_timeout"`. The job may be re-queued with a higher worker class via the SRE remediation path. | `scans` job row → `failed`. |
| Oracle adapter crash (Semgrep / CodeQL subprocess error) | Worker subprocess monitor | Retry once with a fresh subprocess; on second failure `status=failed`. | `scans` job row → `failed`. |
| SARIF normalisation fails | `CMP-FND-01` in-process | Worker fails the job and uploads the raw SARIF blob to a quarantine S3 prefix for triage. | `scans` job row → `failed`; raw SARIF retained 14 days. |
| HMAC sign on callback fails | AWS SDK | Refresh key from Secrets Manager; retry up to 3×; then alarm. The job is not lost — SQS visibility timeout returns it. | None. |
| Worker timeout (60 min SQS visibility for scan-job queue) | SQS | SQS re-delivers the message to another worker. After max-receive=3 → DLQ + alarm. | `scans` job row stays prior state until a successful callback or a reconcile job promotes to `failed`. |
| `CMP-SNAP-04` raises a re-partition event after this scan completes | `CMP-SNAP-04` (asynchronous) | **Not the worker's concern.** The worker has already exited; the re-partition is an append-only record (`DOC-PARTITION.md §5`). | Append-only re-partition row in `provenance_records`. |

**Safe-direction discipline.** The worker fails closed in every above row that mentions `InvariantViolation`. Silent fallback on `origin` would mis-partition findings and silently degrade the determinism claim; the worker therefore raises and pages, never guesses. This is the operational analogue of INV-4 (one-sided approximation) — applied here at the per-finding setter rather than at an undecidable-property approximation.

---

## 8. Provenance threading

`CMP-ORCH-03` is the **central provenance-threading site** of the analysis pipeline. Per `.claude/rules/02-provenance.md §"Per-component threading responsibilities"` row for `CMP-ORCH-03` and `DOC-PROVENANCE.md §10`:

| Field | Threading rule (verbatim from `.claude/rules/02-provenance.md` and `DOC-PROVENANCE §10`) |
|---|---|
| `origin` | **Set per finding** by the §3.3 setter from `detector.engine` (with `finding.from_core_engine` branch on mixed detectors). NOT NULL; CHECK in `('deterministic-core','oracle-passthrough')`. |
| `determinism_partition` | Mirror of `origin`; both columns must agree (`DOC-DB.md §4.12`). |
| `S_version` | Threaded from `WorkerJob.S_version` onto every finding. NOT NULL (INV-2 schema fence). |
| `env_digest` | Threaded from `WorkerJob.env_digest` onto every finding. NOT NULL; CHECK (`sha256:hex64`) (INV-2 schema fence). |
| `cpg_order_hash` | Carried from `CMP-CORE-03` onto every finding. 32-byte sha256. |
| `cpg_order_hash_annotation` | **Pinned literal** `canonical iff fingerprint_class = strong`. NOT NULL; CHECK (`= 'canonical iff fingerprint_class = strong'`) (INV-5 schema fence). |
| `fingerprint_class` | Carried from `CMP-CORE-02`. CHECK in `('strong','weak')`. |
| `slice_fingerprint` | Carried from `CMP-CORE-02`. 32-byte sha256. |
| `engine` | Mirror of `detector.engine`. CHECK in `('ifds','ide','semgrep','cpg-query','external')`. |
| `precondition_status` | Carried from `snapshots.precondition_status` set by `CMP-SNAP-01`. CHECK in `('closed-world','degraded','full-reparse')`. |
| `witness_blob_uri` | Set if a witness slice was extracted (IFDS path); NULL otherwise (oracle findings may omit). |

**Must NOT touch:** `triage_score`, `triage_reason` (those are in the separate `triage_scores` table written only by `CMP-TRI-01`); `signature`, `kms_key_arn`, `signature_alg` (those are written by `CMP-FND-03` after canonical-record signing); `repartition_*` (those are append-only records by `CMP-SNAP-04`); `status`, `suppression_reason` (default `open`; mutated only by `DOC-API.md §4.4 PATCH` under INV-3 fence).

The full chain `source commit → snapshot digest → S_version → env_digest → cpg_order_hash → taint witness → rule/spec id → SARIF hash → per-finding origin` (PLAN.md property (c)) closes at `CMP-FND-03`. `CMP-ORCH-03` contributes **links 5 (carried), 6 (set if present), 7 (rule/spec id, from `Detector`), and 9 (per-finding `origin`)** to that chain.

---

## 9. Acceptance criteria cross-reference

The following ACs are quoted **verbatim** from `SDD.md §7 CMP-ORCH-03`. Paraphrasing an AC is a contract break (RULE-4). Every TST-AC-* is `[FORTHCOMING]` because the QA phase has not begun.

`SDD.md §7 CMP-ORCH-03` defines exactly **two** ACs (`a` and `b`); there is no `AC-ORCH-03c`.

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-ORCH-03a** | > Every emitted finding has a correct `origin` (INV-1). | `TST-AC-ORCH-03a [FORTHCOMING]` `[INVARIANT]` (per `WBS.md §6`) |
| **AC-ORCH-03b** | > A `mixed`-class detector emits per-finding `origin` (some core, some oracle) without blurring. | `TST-AC-ORCH-03b [FORTHCOMING]` `[INVARIANT]` |

Invariant tests directly attached to this component:

- `TST-INV-1-ORCH-03 [FORTHCOMING]` — every emitted finding has a correct, non-null `origin` (`DOC-INV.md §3`).
- `TST-INV-2-ORCH-03 [FORTHCOMING]` — every emitted finding carries non-null `S_version` and `env_digest` (`DOC-INV.md §4`).

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on `CMP-ORCH-03` |
|---|---|---|---|
| `CLAR-API-01` | URL alignment under `/api/v1/`: SDD path for the worker callback is `POST /api/v1/jobs/{job_id}/status`; task-prompt proposed `POST /api/v1/internal/workers/{worker_id}/report_status` | **DEFERRED** | SDD path is normative; the worker MUST call `POST /api/v1/jobs/{job_id}/status` until and unless `CLAR-API-01` is resolved otherwise. `DOC-API.md §4.5` mirrors this stance. |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | Owner field in §1 remains "DEFERRED" until populated. |
| `CLAR-DEPLOY-06` | Queue technology + DLQ + visibility-timeout / retry semantics | **RESOLVED** | Amazon SQS standard + per-queue DLQ; **scan-job visibility 60 min**, max-receive 3 (per `DOC-DEPLOY-DECISIONS.md` line 104; snapshot-job visibility 15 min is owned by `CMP-SNAP-01`). |
| `CLAR-DEPLOY-14` | LLM provider + per-tenant quota controls | **RESOLVED** | The worker does **not** call the LLM; the LLM is consumed by `CMP-TRI-01..03` after findings are persisted. INV-3 fence is structural. |
| `CLAR-SLA-02` | Numeric per-tenant rate-limit budgets enforced by `CMP-CP-01` | **DEFERRED** | Indirect: caps on submission rate from `CMP-ORCH-01` set the worker pool's load; the worker is rate-blind otherwise. |

No new `CLAR-ORCH-*` items are filed by this document; the per-finding setter pattern, the mixed-detector contract, and the four-field threading are unambiguous given the cross-cutting references.

---

## 11. References

- `SDD.md §7 CMP-ORCH-03` — verbatim AC statements.
- `PLAN.md §"Phase 4 — Orchestrator + heuristic scheduler"` — `tools/scan/worker/worker.py`; "loads the CPG once, runs IFDS for core classes / oracle adapters otherwise, stamps `origin` and `determinism_partition`."
- `PLAN.md §"Engine adapters and the determinism partition"` — partition contract.
- `docs/cross-cutting/DOC-PARTITION.md §3 (engine→origin), §4 (setter), §5 (re-partition), §7 (common mistakes)`.
- `docs/cross-cutting/DOC-PROVENANCE.md §2 (four fields), §3 (chain), §10 (per-component threading)`.
- `docs/cross-cutting/DOC-INV.md §3 (INV-1), §4 (INV-2)`.
- `docs/cross-cutting/DOC-API.md §4.5 (worker callback), §5 (Finding object)`.
- `docs/cross-cutting/DOC-DB.md §4.12 (findings — INV-1/2/5 anchor)`.
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — CLAR-DEPLOY-06 (SQS 60-min scan visibility), CLAR-DEPLOY-14 (LLM).
- `docs/components/DOC-CMP-ORCH-01.md` (sibling) — SQS message production + worker callback ingress.
- `docs/components/DOC-CMP-ORCH-02.md` (sibling) — scheduler.
- `docs/components/DOC-CMP-CORE-01.md` (sibling) — IFDS/IDE solver.
- `docs/components/DOC-CMP-CORE-02.md` (sibling) — slice fingerprint, `fingerprint_class`.
- `docs/components/DOC-CMP-CORE-03.md` (sibling) — `cpg_order_hash` (Algorithm 5).
- `docs/components/DOC-CMP-DET-02.md` (sibling) — detector registry; engine field source.
- `docs/components/DOC-CMP-SNAP-01.md` (sibling) — snapshot artefacts + `env_digest`.
- `.claude/rules/00-global.md` (RULE-6), `.claude/rules/02-provenance.md`, `.claude/rules/05-determinism.md` (canonical setter — §3.3 above quotes verbatim).

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-ORCH-03`. The per-finding `origin` setter (§3.3) is the INV-1 anchor of the pipeline; deviations in the setter pattern are a hard contract break.*
