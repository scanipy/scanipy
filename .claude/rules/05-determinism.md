# Determinism partition rules — Scanipy v3.2

Source: `PLAN.md §"Engine adapters and the determinism partition"`, `SDD.md §2 (INV-1)`, `WBS.md §1.1`.

---

## The two partitions

### `deterministic-core`

A finding is `deterministic-core` when **all** of the following hold:

1. The detector's `engine ∈ {ifds, ide}` (registered in `manifest.yaml`).
2. The finding passed through the combinator-DSL closure check (CMP-DET-02, CMP-DET-01).
3. The snapshot satisfied the closed-world precondition — OR — was routed to the sound degraded path (CMP-SNAP-03 verdict: `closed-world` or `degraded`).
4. No differential-oracle re-partition event has been raised for this finding since the scan ran (CMP-SNAP-04).
5. `LLM_TRIAGE=off` at the time of the attestation run (CMP-CP-05).

**Guarantee:** for fixed `(S_version, env_digest)`, re-running `F` on the same source produces byte-identical SARIF over `origin=deterministic-core` findings.

### `oracle-passthrough`

A finding is `oracle-passthrough` when:

- The detector's `engine ∈ {semgrep, cpg-query, external}`, OR
- The finding was retroactively re-partitioned by the differential oracle (CMP-SNAP-04), OR
- The snapshot was routed to `full-reparse` mode and the `origin` was explicitly set to `oracle-passthrough` for that run.

**Guarantee:** digest-stability + a measured reproduction rate (not the determinism theorem). The Attestor reports this rate numerically; it never asserts property (a) over oracle findings.

---

## How `origin` is set

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

---

## Differential oracle re-partitioning (CMP-SNAP-04)

When the async differential reflection scanner disagrees with `CW-DETECT`:

1. Raise a determinism incident.
2. For every finding in the affected snapshot that carries `origin=deterministic-core`: flip to `oracle-passthrough`.
3. Log the re-partition event to provenance (CMP-FND-03).
4. Notify affected customers.
5. The honest-labeling ledger must record the labeling-correction window and its SLA.

After re-partitioning, the finding's `origin` is `oracle-passthrough` permanently (until the snapshot is re-run under a `CW-DETECT` version that correctly classifies the snapshot as not-closed-world from the start).

---

## Attestor pipeline contract (CMP-CP-05)

Two separate pipelines:

| Pipeline | Input partition | Pass criterion | Failure action |
|---|---|---|---|
| **Core** | `origin=deterministic-core` | Byte-identical SARIF across two independent runs under fixed `(S_version, env_digest, LLM_TRIAGE=off)` | Hard CI fail; incident raised |
| **Oracle** | `origin=oracle-passthrough` | Digest-stability + a measured reproduction rate | Numeric rate reported; no theorem assertion; no hard fail on rate |

The core pipeline must **never** assert any guarantee over oracle-partition findings. The oracle pipeline must **never** claim the determinism theorem.

---

## Common mistakes

| Mistake | Correct behaviour |
|---|---|
| Writing `origin = "mixed"` at the finding level | Set per-finding origin; a single finding is never `mixed` |
| Claiming byte-identical SARIF for oracle findings | Oracle pipeline reports a rate; byte-identical is a core-only claim |
| Leaving `origin` null on a finding | Hard invariant violation (INV-1); blocked by the schema NOT NULL constraint |
| Re-using the same Attestor pass criterion for both partitions | Two separate pipelines with separate pass criteria |

---

*Cross-reference: SDD.md §2 (INV-1), PLAN.md §"Engine adapters", CLAUDE.md §3 (INV-1), `.claude/rules/02-provenance.md`*
