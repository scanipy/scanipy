# DOC-CMP-CP-05 — Determinism Attestor (partitioned)

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `SDD.md §10 CMP-CP-05` (Purpose, AC-CP-05a, AC-CP-05b, AC-CP-05c)
- `PLAN.md §"Phase 9 — Determinism Attestor, partitioned"`, `§"Engine adapters and the determinism partition"`, `§"Verification"` (Core-partition reproducibility line)
- `docs/cross-cutting/DOC-PARTITION.md §6` (the two pipelines — verbatim Attestor contract)
- `docs/cross-cutting/DOC-INV.md §3 (INV-1)`, `§5 (INV-3 — LLM_TRIAGE=off)`
- `docs/cross-cutting/DOC-DB.md §4.10 (attestations table)`
- `docs/cross-cutting/DOC-SARIF.md` (canonical SARIF format the Attestor diffs)
- `docs/cross-cutting/DOC-RUNBOOK.md §7` (attestation-incident procedure)
- `CLAUDE.md §15` (Gate 3 — required status check on `main`)
- `.claude/rules/05-determinism.md §"Attestor pipeline contract"`, `.claude/rules/01-invariants.md (INV-1)`, `.claude/rules/00-global.md`
- `.github/workflows/attestor.yml` (CI implementation surface)

This document is the **implementation contract** for `CMP-CP-05`. A code-writing agent given only this file plus the cross-cutting refs above must be able to produce a passing implementation without re-reading `SDD.md` (per `AC-DOC-04`).

The two-pipeline contract in §3 is **byte-identical** to `.claude/rules/05-determinism.md §"Attestor pipeline contract"` and `docs/cross-cutting/DOC-PARTITION.md §6`. Updates require lockstep changes in all three documents.

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-CP-05` |
| Subsystem | Control Plane & Attestation (`SDD.md §10`) |
| Staging | Stage A (gates Stage B entry; Attestor must be green on Stage-A core partition before JS/TS launch — `DOC-STAGING §2 Stage B`) |
| Depends-On | `CMP-ORCH-01` (scan API the Attestor re-invokes), `CMP-FND-03` (signed provenance the Attestor appends to) — per `WBS.md §20` |
| Owner | **DEFERRED** via `CLAR-OWNER-01` (`WBS.md §17`) |
| INV-* touched | **INV-1 hard gate** (core pipeline is the empirical falsifier of property (a) over `origin=deterministic-core`); **INV-3** (the core pipeline runs with `LLM_TRIAGE=off` — verifies byte-identity is independent of any LLM triage path); **INV-2** (re-runs use the same `S_version`, `env_digest`); **INV-5** (re-runs must produce the same `cpg_order_hash` and annotation) |
| CI Gate | **Gate 3** (`CLAUDE.md §15`) — required status check on `main` for every detector / engine / `Env` change (`AC-CP-05c`) |

---

## 2. Mandate

**Verbatim SDD `Purpose:` (`SDD.md §10 CMP-CP-05`):**

> Two pipelines. Core: re-run `F` under fixed `(S_version, env_digest, LLM_TRIAGE=off)` and assert byte-identical SARIF over the core partition (hard fail on diff). Oracle: record oracle digests and report a measured reproduction rate with no theorem attached.

**Operational role.** `CMP-CP-05` is the **empirical falsifier of property (a)** of `PLAN.md` — the conditional theorem that, for fixed `(S_version, env_digest)`, re-running `F` over the same source produces byte-identical SARIF over `origin=deterministic-core`. The component:

1. Runs **two independent pipelines** on every detector / engine / `Env` change, separated by input partition (`origin`).
2. Hard-fails CI on a core-partition byte difference (`AC-CP-05a`, `AC-CP-05c`).
3. Reports a numeric reproduction rate on the oracle partition without ever asserting the theorem (`AC-CP-05b`).
4. Writes one `attestations` row per `(scan_id, partition)` recording the verdict.
5. Appends the verdict to the signed provenance chain (`CMP-FND-03`), stamping an `attestor_hash` that auditors can compare across releases.

`CMP-CP-05` is **read-only against the partition**: it does **not** modify `origin` on any finding (re-partitioning is `CMP-SNAP-04`'s job, never the Attestor's — per `DOC-PARTITION §6.3`). It does **not** assert any guarantee over oracle findings beyond the digest-stability + measured rate (a 100% rate on a release is empirical, not theorem-licensed).

---

## 3. Interface contract — two pipelines (verbatim contract)

The Attestor runs **two separate pipelines** on every detector / engine / `Env` change (`AC-CP-05c`). The pipelines share no logic beyond their input filter; they have separate inputs, separate pass criteria, and separate failure handlers. The two tables in §3.1 and §3.2 are reproduced **character-for-character** from `docs/cross-cutting/DOC-PARTITION.md §6.1` and `§6.2` respectively (the more-detailed normative form of the rule-file contract in `.claude/rules/05-determinism.md §"Attestor pipeline contract"`). When any of the three documents drifts, `DOC-PARTITION §6` is the upstream truth and the others are corrected.

### 3.1 Core pipeline

| Aspect | Specification |
|---|---|
| **Input filter** | All findings on the canary corpus with `origin = deterministic-core`. |
| **Run configuration** | Two independent re-runs of `F` under fixed `(S_version, env_digest, LLM_TRIAGE=off)`. |
| **Pass criterion** | Byte-identical SARIF between the two runs over the input filter. (`AC-CP-05a`) |
| **Failure** | **Hard CI fail.** Block deploy. Raise a determinism incident. Triage steps in DOC-RUNBOOK §7. |
| **Implementation surface** | `.github/workflows/attestor.yml` — job `attestor-core`. |
| **Authority** | Required status check on `main`. (CI gate 3 — `CMP-CI-01` `AC-CI-01c`.) |

The core pipeline is the empirical falsifier of property (a). A core-pipeline byte difference is, by definition, evidence that one of the conditional theorem's hypotheses was violated on this snapshot — DSL escape, closed-world FN, environment drift, or implementation nondeterminism. It is never an acceptable noise; every diff is investigated.

### 3.2 Oracle pipeline

| Aspect | Specification |
|---|---|
| **Input filter** | All findings on the canary corpus with `origin = oracle-passthrough`. |
| **Run configuration** | Two independent re-runs of `F` under fixed `(S_version, env_digest)`. Triage flag is not required to be off (oracle findings are not theorem-covered anyway). |
| **Pass criterion** | Digest-stability + measured reproduction rate. The rate is published per release. (`AC-CP-05b`) |
| **Failure** | Numeric rate falls below threshold → reported in the release notes; the Attestor publishes the rate but does **not** hard-fail on rate alone. A regression triggers an investigation but not a release block. |
| **Implementation surface** | `.github/workflows/attestor.yml` — job `determinism-canary` (when the canary corpus is present). |
| **Authority** | Informational; not a required status check. |

The oracle pipeline reports a number, never a theorem. Customer contracts quote that number per release; they do not quote (a) over oracle findings.

### 3.3 What the pipelines must never do (verbatim DOC-PARTITION §6.3)

- The core pipeline must **never** assert any guarantee — byte-identity or otherwise — over findings with `origin = oracle-passthrough`.
- The oracle pipeline must **never** claim property (a) on its findings, even if the measured rate happens to be 100% on a given release.
- Neither pipeline may modify `origin`. Modification is `CMP-SNAP-04`'s job, not the Attestor's. The Attestor is **read-only against the partition**.
- Neither pipeline may suppress, delete, or transform a finding. The Attestor is a verifier, not a normalizer.

### 3.4 Function signatures

```python
# services/scan/attestor.py  (CMP-CP-05)

@dataclass(frozen=True)
class AttestationVerdict:
    scan_id: UUID
    partition: Literal["core", "oracle"]
    result: Literal["pass", "fail", "rate-only"]
    attestor_hash: bytes              # sha256 of the canonical SARIF blob over this partition
    reproduction_rate: Decimal | None # NULL on core partition; 0..1 on oracle partition
    s_version: str
    env_digest: str
    signed_chain_id: UUID | None      # FK → provenance_records.id (CMP-FND-03)
    diff_summary: str | None          # NULL on pass; populated with first-N-bytes diff on fail

def attest_scan(
    scan_id: UUID,
    partition: Literal["core", "oracle"],
) -> AttestationVerdict:
    """
    Run the attestation pipeline for `scan_id` on the given partition.

    Core partition:
      1. Load the persisted SARIF blob for scan_id, filtered to origin=deterministic-core.
      2. Re-run F against the same (codebase, commit_sha, S_version, env_digest)
         under LLM_TRIAGE=off — a second independent execution.
      3. Re-filter to origin=deterministic-core, canonicalize per DOC-SARIF.
      4. Compare byte-for-byte.
         - identical → result="pass"
         - any diff → result="fail" + diff_summary populated + incident raised

    Oracle partition:
      1. Load the persisted SARIF blob for scan_id, filtered to origin=oracle-passthrough.
      2. Re-run F against the same inputs (LLM_TRIAGE may be anything).
      3. Re-filter to origin=oracle-passthrough.
      4. Compute reproduction_rate = (# stable findings) / (# total findings).
      5. result="rate-only"; never "pass"/"fail" on rate alone.

    Both partitions:
      - Append the verdict to provenance_records via CMP-FND-03.
      - Insert into attestations (DOC-DB §4.10).
      - Stamp attestor_hash on the run-level SARIF properties block.
    """
```

The core pipeline call site (`.github/workflows/attestor.yml` `attestor-core`) iterates over the canary corpus and invokes `attest_scan(scan_id, "core")` per canary repo; any `result="fail"` aborts the job with non-zero exit.

### 3.5 SARIF canonicalization

Per `DOC-SARIF.md`, the SARIF used for byte-comparison is the **canonical** form produced by `CMP-FND-01` (normalizer) ordered by `cpg_order_hash` (Algorithm 5, `CMP-CORE-03`). Without canonicalization, byte-identity would be impossible (Python dict ordering, JSON whitespace, etc.). Canonicalization is **not** the Attestor's job — it is `CMP-FND-01`'s; the Attestor compares the already-canonical blobs.

A canonical SARIF blob produced by two independent runs under fixed `(S_version, env_digest, LLM_TRIAGE=off)` is byte-identical **iff** property (a) holds for the snapshot. The Attestor is the falsifier of that "iff".

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| `scan_id` | CI invocation (`attestor.yml`) for each canary repo | The scan whose SARIF is being re-attested. |
| Persisted SARIF blob | S3 (via `findings`/`scans` lookup) | Canonical-ordered per `DOC-SARIF`; emitted by `CMP-FND-01`. |
| `(S_version, env_digest)` | `scans` table row | The pinned analysis configuration; the re-run uses the same values. |
| Canary corpus | `tests/corpora/canary/corpus.lock` (`CMP-CORP-CANARY-01`) | 100 canary repos × 3+ SCMs; if absent, CI logs warning and skips the determinism-canary job (existing `.github/workflows/attestor.yml` behaviour). |
| `LLM_TRIAGE` env var | CI environment | Forced to `"off"` for the core pipeline (line 71 of `attestor.yml`). |

### 4.2 Outputs / Persisted artifacts

| Output | Location | Contract |
|---|---|---|
| `attestations` row | PostgreSQL (`DOC-DB §4.10`) | One row per `(scan_id, partition)`; UNIQUE constraint enforces no duplicate attestation per partition per scan. |
| `attestor_hash` | `attestations.attestor_hash` + stamped on run-level SARIF `properties.attestor_hash` | sha256 of the canonical SARIF blob over the partition; auditor-visible. |
| Provenance-chain entry | `provenance_records` (CMP-FND-03) | Appends the attestation verdict to the signed chain; links via `attestations.signed_chain_id`. |
| CI verdict (`pass`/`fail`/`rate-only`) | GitHub Actions check status | Required status check on `main` for the core job; informational for the oracle job. |
| Incident ticket (on core fail) | DOC-RUNBOOK §7 procedure (PagerDuty/Slack) | Hard CI block; deploy halted; on-call engineer follows runbook. |
| Reproduction-rate metric | OpenTelemetry counter `attestor.oracle_reproduction_rate` | Published per release; surfaced on the Attestor dashboard. |

The `attestations` table schema (verbatim from `DOC-DB §4.10`):

| Column | Type | Constraint |
|---|---|---|
| `id` | uuid | PK |
| `org_id` | uuid | FK → orgs(id) |
| `scan_id` | uuid | FK → scans(id) ON DELETE CASCADE |
| `partition` | text | CHECK (`partition IN ('core','oracle')`) |
| `attestor_hash` | bytea | NOT NULL (sha256) |
| `result` | text | CHECK (`result IN ('pass','fail','rate-only')`) |
| `reproduction_rate` | numeric(5,4) | NULL on core; 0..1 on oracle |
| `S_version` | text | NOT NULL (INV-2) |
| `env_digest` | text | NOT NULL (INV-2) |
| `signed_chain_id` | uuid | FK → provenance_records(id) |
| `created_at` | timestamptz | DEFAULT now() |

Indices: PK; UNIQUE `(scan_id, partition)`; INDEX `(org_id, created_at DESC)`. RLS: standard template.

---

## 5. Invariants touched

| Invariant | How `CMP-CP-05` discharges it | Test |
|---|---|---|
| **INV-1 (hard gate)** | The core pipeline is the empirical falsifier of property (a) over `origin=deterministic-core`. A core-partition byte difference is hard CI fail → release block → incident. The Attestor never modifies `origin` (re-partition is `CMP-SNAP-04`'s exclusive responsibility). | `TST-AC-CP-05a [FORTHCOMING]` (seeded core-path nondeterminism fails core pipeline); `TST-INV-1-FND-02 [FORTHCOMING]` (no INSERT to attestations without correct partition value). |
| **INV-3** | The core pipeline runs with `LLM_TRIAGE=off` (env var pinned in `attestor.yml`). Byte-identity under `LLM_TRIAGE=off` proves the core partition is independent of any LLM path — the schema-level INV-3 fence (`triage_scores` split from `findings`) plus the Attestor's `LLM_TRIAGE=off` configuration are the two complementary discharges. | `TST-INV-3-CP-05 [FORTHCOMING]` (Attestor configuration verifies `LLM_TRIAGE=off`). |
| **INV-2** | The re-run uses the same `(S_version, env_digest)` as the original scan; the `attestations` row carries both as NOT NULL columns. A re-run against a drifted `env_digest` is a configuration error, not a determinism violation. | `TST-INV-2-CP-05 [FORTHCOMING]` (re-run rejects if `env_digest` differs from the original scan's). |
| **INV-5** | The re-run must produce the same `cpg_order_hash` (and the same `cpg_order_hash_annotation` literal) on every finding. Byte-identical SARIF presupposes that the canonical order is identical, which presupposes the hash and annotation are identical per finding. | `TST-INV-5-CP-05 [FORTHCOMING]` (a finding whose annotation flickers between `strong` and `weak` across runs triggers the core-pipeline byte diff). |

The Attestor is the **discharge mechanism**, not the value-setter, for INV-1/INV-3/INV-5. It produces empirical evidence that the upstream owners (`CMP-ORCH-03`, `CMP-FND-02`, `CMP-CORE-03`, `CMP-TRI-01`) discharged their share.

See `DOC-INV.md` for full invariant statements (verbatim); `DOC-PARTITION.md §6` for the two-pipeline contract reference.

---

## 6. Algorithm / data flow

```
trigger: push to main / PR — paths: detectors/**, analysis/**, workers/**,
         services/scan/**, services/snapshot/**
              │
              ▼
.github/workflows/attestor.yml — `attestor-core` job (required status check)
              │
              ▼
For each canary repo in tests/corpora/canary/:
  ┌─────────────────────────────────────────────────────────┐
  │ CORE PIPELINE                                           │
  │  1. Load persisted SARIF for the canary scan,           │
  │     filter to origin=deterministic-core,                │
  │     canonical-ordered by cpg_order_hash (CMP-CORE-03).  │
  │  2. Re-run F (CMP-ORCH-01.submit + CMP-ORCH-03.run)     │
  │     under (S_version, env_digest, LLM_TRIAGE=off)       │
  │     — second independent execution.                     │
  │  3. Filter run-2 SARIF to origin=deterministic-core.    │
  │  4. Compute sha256 of both blobs → attestor_hash_{1,2}. │
  │  5. Byte-compare blob_1 vs blob_2.                      │
  │     ├── identical → result="pass", attestor_hash=h_1    │
  │     └── any diff  → result="fail", diff_summary=<first  │
  │                       differing offsets + bytes>,       │
  │                       incident raised (DOC-RUNBOOK §7)  │
  │  6. INSERT attestations (scan_id, partition='core', …). │
  │  7. CMP-FND-03 appends verdict to provenance_records.   │
  │  8. On result="fail": GitHub Actions job exits non-zero │
  │     → required status check fails → main branch         │
  │     protection blocks merge → deploy halted.            │
  └─────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────┐
  │ ORACLE PIPELINE (informational; not blocking)           │
  │  1. Load persisted SARIF, filter to oracle-passthrough. │
  │  2. Re-run F under (S_version, env_digest). LLM_TRIAGE  │
  │     setting does not matter (oracle findings not        │
  │     theorem-covered).                                   │
  │  3. Compute reproduction_rate = # stable findings /     │
  │     # total findings over the oracle partition.         │
  │  4. result = "rate-only" (never "pass"/"fail").         │
  │  5. INSERT attestations (scan_id, partition='oracle',   │
  │     reproduction_rate=<rate>, …).                       │
  │  6. Publish rate to OpenTelemetry; surface on dashboard │
  │     and release notes.                                  │
  │  7. Job does NOT exit non-zero on low rate; investigate │
  │     out-of-band.                                        │
  └─────────────────────────────────────────────────────────┘
```

Both pipelines stamp `attestor_hash` on the run-level SARIF `properties` block so downstream auditors can compare the hash across releases without re-running the Attestor.

---

## 7. Failure modes and error contracts

| Failure | Detected by | Response | Side effect |
|---|---|---|---|
| Core-pipeline byte difference between run-1 and run-2 SARIF | `attest_scan(scan_id, "core")` byte-compare | **Hard CI fail.** Job exits non-zero. `result="fail"` written to `attestations`. Incident raised per `DOC-RUNBOOK §7`. Deploy halted via branch protection. | Triage candidates (per DOC-RUNBOOK §7): DSL escape (CMP-DET-01), closed-world FN (CMP-SNAP-03), env drift (CMP-SNAP-05), worker nondeterminism (CMP-ORCH-03). |
| Oracle pipeline reproduction rate below threshold | `attest_scan(scan_id, "oracle")` | Numeric rate recorded; release notes flagged; OpenTelemetry alarm raised. **No hard CI fail.** | Investigation ticket; potential oracle-tool version drift; rate trend monitored. |
| Re-run `env_digest` differs from original scan | Pre-run check in `attest_scan` | Job fails with configuration error (not a determinism error). | Indicates a misconfigured CI environment — the Attestor cannot speak to property (a) under different `Env`. Fix the CI pin. |
| Canary corpus absent (`tests/corpora/canary/corpus.lock` missing) | Step 1 of `determinism-canary` job | Job logs warning and skips (existing `attestor.yml` behaviour). The `attestor-core` job still runs the per-test attestor checks. | `CMP-CORP-CANARY-01` is the blocker; surface it as a dependency to merge. |
| Re-run requires `LLM_TRIAGE=off` but env var leaks `on` | CI env-var check in step 1 | Hard CI fail with explicit error: "core pipeline requires `LLM_TRIAGE=off`". | This is the schema-level INV-3 backstop at the Attestor; without it, byte-identity would not prove independence from triage. |
| Provenance append fails (`CMP-FND-03` error) | `attest_scan` post-verdict step | Hard CI fail; attestation row is **not** committed (transactional). | Without provenance, the verdict is not auditable; refuse to ship a verdict that is not in the chain. |
| Attestor itself produces non-canonical SARIF (would indicate a CMP-FND-01 bug, not a CP-05 bug) | Diff between persisted and re-run SARIF, with the diff being whitespace/ordering | Hard CI fail; surface as CMP-FND-01 incident, not CMP-CP-05. | The Attestor is read-only; if normalization drifts, the upstream owner fixes it. |

**Fail-closed posture.** The Attestor is the last gate before deploy. It is configured to fail closed: a core-pipeline byte difference, an environment misconfiguration, a missing dependency, or a provenance-append failure all halt the deploy. There is no "best-effort" mode for the core pipeline.

---

## 8. Provenance threading

Per `CLAUDE.md §11` RULE-6, every finding-affecting component must thread the four required fields. CP-05 **does not emit findings**; it emits attestations. Its threading responsibilities:

| Field | CP-05 contribution |
|---|---|
| `origin` | **Read-only.** CP-05 filters input by `origin` (core pipeline reads only `deterministic-core`; oracle pipeline reads only `oracle-passthrough`). It never writes `origin` on any finding. |
| `S_version` | Stamped on every `attestations` row (NOT NULL); the re-run uses the same `S_version` as the original scan. |
| `env_digest` | Stamped on every `attestations` row (NOT NULL); pre-run check refuses to re-attest if the current CI `env_digest` differs from the original scan's. |
| `cpg_order_hash` + annotation | **Read-only.** The Attestor compares SARIF that already carries `cpg_order_hash + annotation` per finding. A drift in the hash or annotation across runs is detected as a core-partition byte difference. |
| `attestor_hash` | **Written by CP-05.** Stamped on the run-level SARIF `properties.attestor_hash` and persisted to `attestations.attestor_hash`. Auditors use this to confirm that two release artifacts came from the same canonical SARIF blob. |
| `signed_chain_id` | **Written by CP-05.** Links the `attestations` row to the `provenance_records` entry that records the verdict. `CMP-FND-03 AC-FND-03c` requires the chain to include attestation events. |

**Must NOT touch.** CP-05 does not write to `findings`, does not modify any provenance row produced upstream, does not flip `origin`, and does not produce triage outputs. Re-partitioning is `CMP-SNAP-04`'s exclusive authority (`DOC-PARTITION §5`).

---

## 9. Acceptance criteria cross-reference

The following ACs are quoted **verbatim** from `SDD.md §10 CMP-CP-05`. Paraphrasing is a contract break (RULE-4).

| AC | Verbatim statement | Test artifact | CI Gate |
|---|---|---|---|
| **AC-CP-05a** | > A deliberately introduced nondeterminism in the core path fails the core pipeline. | `TST-AC-CP-05a` `[FORTHCOMING]` | Gate 3 |
| **AC-CP-05b** | > The oracle pipeline reports a numeric reproduction rate and never asserts the theorem. | `TST-AC-CP-05b` `[FORTHCOMING]` | informational |
| **AC-CP-05c** | > CI runs both pipelines on the canary corpus on every detector / engine / `Env` change. | `TST-AC-CP-05c` `[FORTHCOMING]` | **Gate 3** (`CLAUDE.md §15` — required status check on `main`) |

**AC-CP-05a** falsifier (for QA Agent):

1. Pick a representative deterministic-core scan from the canary corpus.
2. Introduce a deliberate source of nondeterminism in the core path — e.g., a non-canonical map iteration order in `CMP-FND-01`, a clock-dependent value, an unordered set in a slice fingerprint computation.
3. Run `attest_scan(scan_id, "core")`. Expect `result="fail"` with `diff_summary` populated.
4. Assert the GitHub Actions check fails and main-branch protection blocks merge.

**AC-CP-05b** falsifier:

1. Run `attest_scan(scan_id, "oracle")` over the canary corpus.
2. Assert the verdict carries `result="rate-only"`, `reproduction_rate ∈ [0, 1]`, and never `"pass"`/`"fail"`.
3. Assert the published release-notes text never claims "byte-identical" over oracle findings.

**AC-CP-05c** falsifier:

1. Submit a PR that touches `detectors/**` or `analysis/**` or `workers/**` or `services/scan/**` or `services/snapshot/**`.
2. Assert `.github/workflows/attestor.yml` runs and is listed as a required status check on `main`.
3. Verify branch protection is configured: `main` cannot accept a merge without the `attestor-core` check passing (see `CLAUDE.md §15`).

Cross-referenced invariant tests:

- `TST-INV-1-FND-02 [FORTHCOMING]` — schema NOT NULL on partition; the Attestor cannot write an `attestations` row without a valid partition value.
- `TST-INV-3-CP-05 [FORTHCOMING]` — the Attestor enforces `LLM_TRIAGE=off` on the core pipeline.
- `TST-INV-5-CP-05 [FORTHCOMING]` — annotation flicker across runs surfaces as a core-pipeline diff.

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-CP-05 |
|---|---|---|---|
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | Owner field in §1 remains DEFERRED. |
| `CLAR-FE-01` | Stage-D proprietary front-end (Ruby/PHP) | **DEFERRED** | Affects which `(class, language)` pairs the Attestor's core pipeline can speak to. Until Stage D's gate passes, Ruby/PHP findings are oracle-only; the Attestor reports them on the oracle pipeline. |
| `CLAR-FE-02` | Stage-C points-to investment (Go) | **DEFERRED** | Same as above for Go. Until `CMP-CP-06` passes for Go, Go core-partition findings do not exist; the Attestor's core pipeline has no Go inputs. |
| **`CLAR-CP-05-01`** *(new — filed by this document)* | Oracle-pipeline reproduction-rate **target floor** — what numeric rate triggers a release-notes flag vs an OTel alarm? The contract requires "measured rate, no hard fail," but a target floor for the alarm threshold is not pinned. | **FILED** in `WBS.md §17` (OPEN), target resolution before Stage A GA | Affects oracle-pipeline alarm tuning. Working assumption: alarm at < 99% rate over a 7-day rolling window; investigate at < 95%. |
| **`CLAR-CP-05-02`** *(new — filed by this document)* | Attestor cadence — does the core pipeline run on **every** push to `main` (current `attestor.yml`) or only on commits that touch the listed paths (also current `attestor.yml`)? The SDD `AC-CP-05c` says "on every detector / engine / `Env` change"; the workflow `paths:` filter encodes this but may miss `Env` changes that only touch e.g. base-image pins. | **FILED** in `WBS.md §17` (OPEN), target resolution before Stage A GA | Working assumption: the existing `paths:` filter covers `Env` changes via `workers/**` (which holds the Dockerfile). If `Env` is pinned outside `workers/**` (e.g., in `infra/`), the filter must be extended. |

No additional CLAR is filed; the two-pipeline contract is fully specified by `DOC-PARTITION §6` + `.claude/rules/05-determinism.md`. The two new CLARs above are operational-tuning questions, not contract gaps.

---

## 11. References

- `SDD.md §10 CMP-CP-05` — verbatim ACs.
- `PLAN.md §"Phase 9 — Determinism Attestor, partitioned"`, `§"Engine adapters and the determinism partition"`, `§"Verification"` (Core-partition reproducibility line).
- `docs/cross-cutting/DOC-PARTITION.md` §6 — Attestor two-pipeline contract (byte-identical to this document's §3).
- `docs/cross-cutting/DOC-INV.md` §3 (INV-1), §5 (INV-3).
- `docs/cross-cutting/DOC-DB.md` §4.10 — `attestations` schema.
- `docs/cross-cutting/DOC-SARIF.md` — canonical SARIF format the Attestor diffs.
- `docs/cross-cutting/DOC-RUNBOOK.md` §7 — attestation-incident procedure.
- `docs/cross-cutting/DOC-STAGING.md` §2 Stage B — Attestor green on Stage-A core is the prerequisite for Stage B entry.
- `docs/components/DOC-CMP-ORCH-01.md` (sibling, forthcoming) — scan API the Attestor re-invokes.
- `docs/components/DOC-CMP-FND-03.md` (sibling, forthcoming) — signed provenance the Attestor appends to.
- `docs/components/DOC-CMP-SNAP-04.md` (sibling) — the only authorised mutator of `origin`; the Attestor is read-only against the partition.
- `docs/components/DOC-CMP-CORP-CANARY-01.md` (sibling, forthcoming) — the canary corpus the Attestor consumes.
- `CLAUDE.md §15` — Gate 3 (required status check on `main`).
- `.claude/rules/05-determinism.md` §"Attestor pipeline contract" — operational rules.
- `.claude/rules/01-invariants.md` (INV-1, INV-3).
- `.claude/rules/00-global.md` RULE-6 (provenance threading), RULE-7 (staging), RULE-10 (code review).
- `.github/workflows/attestor.yml` — CI implementation surface (jobs `attestor-core`, `determinism-canary`).

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-CP-05`. The two-pipeline tables in §3.1 / §3.2 are reproduced character-for-character from `DOC-PARTITION §6.1` / `§6.2` (the upstream normative form). The condensed two-row table in `.claude/rules/05-determinism.md §"Attestor pipeline contract"` is the operational rule-file digest of the same contract. Any update must be applied lockstep to all three documents, with `DOC-PARTITION §6` as the source of truth on drift.*
