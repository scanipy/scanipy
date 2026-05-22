# DOC-PARTITION — Determinism partition reference

**Owner:** Documentation Manager Agent
**Status:** ACTIVE (Phase 0 output)
**Source of truth:** `PLAN.md §"Engine adapters and the determinism partition"`, `SDD.md §2 (INV-1)`, `SDD.md CMP-SNAP-04`, `SDD.md CMP-CP-05`, `.claude/rules/05-determinism.md`.
**Invariant:** INV-1 (every finding carries `origin ∈ {deterministic-core, oracle-passthrough}`).

This document defines how every finding emitted by the platform is partitioned, what guarantee applies to each partition, how a finding can move between partitions, and how the Attestor verifies the partition at the release boundary.

When this document conflicts with `PLAN.md` / `SDD.md` / `.claude/rules/05-determinism.md`, those upstream documents win and this one is corrected.

---

## 1. Purpose

The platform produces findings from heterogeneous detection engines. Some of those engines admit a reproducibility theorem; others do not. Mixing them under a single label would either inflate the formal claim past what it can support (claim a theorem over outputs the theorem does not cover) or deflate it below what is actually proven (refuse to assert byte-identity where the math licenses it). Neither is acceptable.

The two-partition model addresses this by attaching, to every finding, an `origin` field that names the partition. The partition determines:

1. **Which Attestor pipeline runs against the finding.** `deterministic-core` findings flow through the core pipeline and are required to be byte-identical across two independent runs. `oracle-passthrough` findings flow through the oracle pipeline and are required only to be digest-stable, with the measured reproduction rate published.
2. **What customer-facing guarantee applies.** Contracts state per `(class, language)` pair which partition applies and quote the corresponding guarantee. The honest-labeling ledger (`PLAN.md §"Honest-labeling ledger"`) is consistent only because the partition is consistent.
3. **What action the differential reflection oracle (`CMP-SNAP-04`) is empowered to take.** It can re-partition a finding from `deterministic-core` to `oracle-passthrough`; it cannot perform the reverse transition.

INV-1 is the schema-level expression of this: every row in the `findings` table carries a non-null `origin`, and the `origin` enum has exactly two values.

---

## 2. Two-partition model

### 2.1 `deterministic-core`

A finding carries `origin = deterministic-core` when **all** of the following hold:

1. The detector's `engine` field in `manifest.yaml` is one of `{ifds, ide}`.
   - The registry (`CMP-DET-02`) derives `determinism_partition = deterministic-core` from this field at registration time (`AC-DET-02c`).
2. The finding passed through the combinator-DSL closure check at detector registration time (`CMP-DET-02`, `CMP-DET-01 AC-DET-01b`).
   - A spec embedding arbitrary code is rejected, never analyzed.
3. The snapshot satisfied the closed-world precondition for Algorithm 1 / Algorithm 2, **OR** was routed to the sound degraded path (`CMP-SNAP-03 CW-DETECT` verdict: `closed-world` or `degraded`).
4. No differential-oracle re-partition event has been raised against this finding since the scan ran (`CMP-SNAP-04`).
5. The Attestor environment was configured with `LLM_TRIAGE=off` at the time of the attestation run (`CMP-CP-05`, INV-3).

**Guarantee (property (a) of `PLAN.md`):** for fixed `(S_version, env_digest)`, re-running `F` over the same source produces **byte-identical SARIF** over all findings with `origin = deterministic-core`. This is a conditional theorem, conditioned on the IFDS/IDE distributivity precondition (owned by the combinator DSL closure check, `CMP-DET-01`) and the closed-world precondition (owned by `CW-DETECT`, `CMP-SNAP-03`). The Attestor (`CMP-CP-05`) is the empirical falsifier of that conditional theorem.

### 2.2 `oracle-passthrough`

A finding carries `origin = oracle-passthrough` when **any** of the following hold:

1. The detector's `engine` field is one of `{semgrep, cpg-query, external}`.
2. The finding was retroactively re-partitioned by the differential oracle (`CMP-SNAP-04`) — i.e., it was emitted as `deterministic-core` but a later asynchronous reflection scan disagreed with `CW-DETECT`, raising a determinism incident.
3. The snapshot was routed to `full-reparse` mode (a closed-world precondition could neither be asserted nor cheaply approximated), and the per-finding `origin` was explicitly set to `oracle-passthrough` for that run.

**Guarantee:** digest-stability (the same SARIF byte sequence is produced when the underlying tool produces the same output for the same input) **plus** a measured reproduction rate published per release. The Attestor reports the rate numerically; it does **not** assert property (a) over the oracle partition. The customer contract states this distinction explicitly.

---

## 3. Engine → origin mapping

Verbatim from `.claude/rules/05-determinism.md` and `SDD.md AC-DET-02c`:

| `engine` value | Origin assigned at registration | Notes |
|---|---|---|
| `ifds` | `deterministic-core` | RHS Tabulation algorithm with reusable procedure summaries (Algorithm 2). |
| `ide` | `deterministic-core` | Lattice-valued IFDS extension. |
| `semgrep` | `oracle-passthrough` | Semgrep adapter; results are digest-stable but not theorem-covered. |
| `cpg-query` | `oracle-passthrough` | Joern CPG query language adapter. |
| `external` | `oracle-passthrough` | CodeQL / arbitrary third-party tool adapter. |

The registry refuses to load a manifest whose `engine` value falls outside the enumerated set (`AC-DET-02b`). A new engine cannot be added without amending this table, `.claude/rules/05-determinism.md`, and `SDD.md AC-DET-02c` simultaneously.

### 3.1 Mixed detectors

A "mixed" detector is one whose result set contains findings from both partitions — e.g., `crypto-misuse`, where some checks are IFDS taint propagation and others are pattern matches over the CPG. Per `SDD.md AC-ORCH-03b` and `.claude/rules/05-determinism.md` ("Common mistakes"):

- `origin` is set **per finding**, not per result set. A single finding is never written with `origin = mixed`; that value is not in the enum.
- The detector's manifest declares each emission engine separately. The closure check (`CMP-DET-02`) verifies that the engine declared per emission is in the enumerated set above.
- The orchestrator worker (`CMP-ORCH-03`) inspects each finding before persistence and stamps the partition derived from the engine that produced that finding.

---

## 4. Per-finding `origin` setter pattern

The canonical setter lives in `CMP-ORCH-03` (detector-agnostic worker). Pseudocode, adapted from `.claude/rules/05-determinism.md`:

```python
# In CMP-ORCH-03 — runs once per detector invocation.
# Inputs:
#   detector — registered detector record from CMP-DET-02
#   results  — iterable of raw Finding records the detector produced
# Outputs:
#   each Finding has its `origin` and `determinism_partition` fields stamped.

CORE_ENGINES = ("ifds", "ide")
ORACLE_ENGINES = ("semgrep", "cpg-query", "external")

def stamp_origin(detector, results):
    if detector.engine in CORE_ENGINES:
        default_origin = "deterministic-core"
    elif detector.engine in ORACLE_ENGINES:
        default_origin = "oracle-passthrough"
    else:
        # The registry should have rejected this at AC-DET-02b/c. If we
        # reach here, treat it as a hard invariant violation and stop —
        # do not guess an origin.
        raise InvariantViolation(
            "CMP-DET-02 registered a detector with engine="
            f"{detector.engine!r}, which is not in the enumerated set."
        )

    for finding in results:
        if detector.is_mixed and finding.from_core_engine is not None:
            # Mixed detector — per-finding choice (AC-ORCH-03b).
            finding.origin = (
                "deterministic-core"
                if finding.from_core_engine
                else "oracle-passthrough"
            )
        else:
            finding.origin = default_origin

        # determinism_partition is derived, not set independently.
        # (Some legacy schemas keep both; they must agree.)
        finding.determinism_partition = finding.origin

        # INV-1 schema guard — NOT NULL constraint catches misses, but
        # belt-and-braces inside the worker too.
        assert finding.origin in ("deterministic-core", "oracle-passthrough"), \
            "INV-1 violation: origin must be in the enumerated set"
```

**Pattern notes:**
- The setter never writes `origin = None` and never writes `origin = "mixed"`.
- For a `mixed` detector, the worker requires each finding to carry a `from_core_engine` boolean (set by the detector adapter). If the detector adapter forgets to set it, the worker raises — not silently falls back. Silent fallbacks here would mis-partition findings and silently degrade the determinism claim.
- The setter is the **only** place `origin` is set in the emit path. Findings normalizers (`CMP-FND-01`) and provenance writers (`CMP-FND-03`) read `origin` but never reassign it. The only legitimate re-assignment is `CMP-SNAP-04` re-partitioning (see §5).

---

## 5. Re-partition lifecycle

The differential reflection oracle (`CMP-SNAP-04`) is the only authorised mutator of an already-stamped `origin`. Its job is to close the residual undecidability risk that `CW-DETECT` (`CMP-SNAP-03`) carries: `CW-DETECT` is required to be one-sided (zero false negatives), but a single FN would mis-label a finding as `deterministic-core` when the snapshot was in fact not closed-world.

### 5.1 Trigger

The async oracle scans the snapshot off the critical path. If its verdict on the closed-world precondition disagrees with the synchronous `CW-DETECT` verdict that ran in line with the scan — i.e., the oracle says "not closed-world" where `CW-DETECT` said "closed-world" — a **determinism incident** is raised.

### 5.2 Cascade

For every finding emitted by the affected snapshot that carries `origin = deterministic-core`:

1. Flip `origin` from `deterministic-core` to `oracle-passthrough`.
2. Append a re-partition event record to the signed provenance chain (`CMP-FND-03`, `AC-FND-03c`). The record names the originating `CW-DETECT` version and the oracle version that detected the disagreement.
3. Notify affected customers within the labeling-correction SLA (`CLAR-SLA-01` resolution: 24h for high-impact incidents, 7d for routine — see DOC-RUNBOOK §6 for the operational procedure).
4. The honest-labeling ledger entry for the affected `(class, language)` pair is updated to record the re-partition rate.

### 5.3 Permanence

After re-partitioning, the finding's `origin` is `oracle-passthrough` **permanently**. The only path to restoring `deterministic-core` is to re-snapshot the codebase at the same commit under a `CW-DETECT` version that correctly classifies the snapshot as **not closed-world from the start**, so that the finding is never emitted as `deterministic-core` in the first place. This guarantees there is no "round-trip" race where a finding flickers between partitions across reruns.

The reverse transition `oracle-passthrough → deterministic-core` is **never** performed on an existing row. Any code path that appears to do this is a bug.

---

## 6. Attestor pipelines (CMP-CP-05)

The Attestor runs **two separate pipelines** on every detector / engine / `Env` change (`AC-CP-05c`). The pipelines share no logic beyond their input filter; they have separate inputs, separate pass criteria, and separate failure handlers.

### 6.1 Core pipeline

| Aspect | Specification |
|---|---|
| **Input filter** | All findings on the canary corpus with `origin = deterministic-core`. |
| **Run configuration** | Two independent re-runs of `F` under fixed `(S_version, env_digest, LLM_TRIAGE=off)`. |
| **Pass criterion** | Byte-identical SARIF between the two runs over the input filter. (`AC-CP-05a`) |
| **Failure** | **Hard CI fail.** Block deploy. Raise a determinism incident. Triage steps in DOC-RUNBOOK §7. |
| **Implementation surface** | `.github/workflows/attestor.yml` — job `attestor-core`. |
| **Authority** | Required status check on `main`. (CI gate 3 — `CMP-CI-01` `AC-CI-01c`.) |

The core pipeline is the empirical falsifier of property (a). A core-pipeline byte difference is, by definition, evidence that one of the conditional theorem's hypotheses was violated on this snapshot — DSL escape, closed-world FN, environment drift, or implementation nondeterminism. It is never an acceptable noise; every diff is investigated.

### 6.2 Oracle pipeline

| Aspect | Specification |
|---|---|
| **Input filter** | All findings on the canary corpus with `origin = oracle-passthrough`. |
| **Run configuration** | Two independent re-runs of `F` under fixed `(S_version, env_digest)`. Triage flag is not required to be off (oracle findings are not theorem-covered anyway). |
| **Pass criterion** | Digest-stability + measured reproduction rate. The rate is published per release. (`AC-CP-05b`) |
| **Failure** | Numeric rate falls below threshold → reported in the release notes; the Attestor publishes the rate but does **not** hard-fail on rate alone. A regression triggers an investigation but not a release block. |
| **Implementation surface** | `.github/workflows/attestor.yml` — job `determinism-canary` (when the canary corpus is present). |
| **Authority** | Informational; not a required status check. |

The oracle pipeline reports a number, never a theorem. Customer contracts quote that number per release; they do not quote (a) over oracle findings.

### 6.3 What the pipelines must never do

- The core pipeline must never assert any guarantee — byte-identity or otherwise — over findings with `origin = oracle-passthrough`.
- The oracle pipeline must never claim property (a) on its findings, even if the measured rate happens to be 100% on a given release. (A 100% rate is empirical, not theorem-licensed.)
- Neither pipeline may modify `origin`. Modification is the differential oracle's job (`CMP-SNAP-04`), not the Attestor's. The Attestor is read-only against the partition.

---

## 7. Common partition mistakes

Verbatim from `.claude/rules/05-determinism.md`:

| Mistake | Correct behaviour |
|---|---|
| Writing `origin = "mixed"` at the finding level | Set per-finding origin; a single finding is never `mixed`. |
| Claiming byte-identical SARIF for oracle findings | The oracle pipeline reports a rate; byte-identical is a core-only claim. |
| Leaving `origin` null on a finding | Hard invariant violation (INV-1); blocked by the schema NOT NULL constraint. |
| Re-using the same Attestor pass criterion for both partitions | Two separate pipelines with separate pass criteria. |
| Performing an `oracle-passthrough → deterministic-core` transition on an existing finding | Not permitted. Re-snapshot under a corrected `CW-DETECT` is the only path. |
| Inferring `origin` at SARIF emission time | `origin` is set at the worker (`CMP-ORCH-03`); normalizer and provenance writers read, never reassign. |

---

## 8. References

| Reference | Where defined |
|---|---|
| **INV-1** | `CLAUDE.md §3`, `SDD.md §2`, `.claude/rules/01-invariants.md` |
| **`CMP-ORCH-03`** | `SDD.md §7`, `AC-ORCH-03a/b` — origin setter owner |
| **`CMP-FND-01`** | `SDD.md §8` — normalizer; reads `origin`, never reassigns |
| **`CMP-FND-02`** | `SDD.md §8`, `AC-FND-02b` — schema NOT NULL on `origin`, `S_version`, `env_digest` |
| **`CMP-FND-03`** | `SDD.md §8` — signed provenance; re-partition events appended |
| **`CMP-SNAP-03`** | `SDD.md §4`, `AC-SNAP-03a` — `CW-DETECT`; INV-4 owner; safe direction = zero FN |
| **`CMP-SNAP-04`** | `SDD.md §4`, `AC-SNAP-04a/b/c` — differential oracle; re-partition trigger |
| **`CMP-CP-05`** | `SDD.md §10`, `AC-CP-05a/b/c` — Attestor (partitioned) |
| **`CMP-DET-01`** | `SDD.md §5`, `AC-DET-01a/b` — combinator DSL closure |
| **`CMP-DET-02`** | `SDD.md §5`, `AC-DET-02a/b/c` — registry derives partition from engine |
| **`CMP-CI-01` Gate 3** | `CLAUDE.md §15` — Attestor as required status check on `main` |
| **`PLAN.md §"Engine adapters and the determinism partition"`** | Verbatim partition statement |
| **`PLAN.md §"Honest-labeling ledger"`** | The four classes of claim that depend on the partition being honest |
| **`CLAR-SLA-01`** | `WBS.md §17` — 24h / 7d labeling-correction SLA |
| **`.claude/rules/05-determinism.md`** | Operational rules, this document expands them |
| **`.claude/rules/02-provenance.md`** | Provenance threading rules; partition is one of the four required threaded fields |
| **`DOC-RUNBOOK.md §6`** | Differential-oracle incident procedure |
| **`DOC-RUNBOOK.md §7`** | Attestation-incident procedure |
| **`DOC-STAGING.md`** | Per-language staging; partition gates per (class, language) |

---

*End of DOC-PARTITION. Updates to the partition contract require changes to `.claude/rules/05-determinism.md` and `SDD.md AC-DET-02c` in lockstep with this document; the three are a single contract.*
