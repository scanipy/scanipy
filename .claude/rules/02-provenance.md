# Provenance threading rules — Scanipy v3.2

Every component that emits, transforms, or persists a finding must thread a defined set of provenance fields. This file specifies exactly which fields each component must carry, derived from `SDD.md §8 (CMP-FND-03)` and `PLAN.md §"Algorithm 5"`.

---

## The four required fields (INV-1, INV-2, INV-5)

| Field | Type | Rule | Set by |
|---|---|---|---|
| `origin` | enum | `deterministic-core` or `oracle-passthrough`. Never null. Never `mixed` at finding level. | CMP-ORCH-03 |
| `S_version` | semver string | The version of the pinned accepted spec set applicable to this scan. Never null. | CMP-ORCH-01 (from scan submission) |
| `env_digest` | sha256 string | The container image digest that defines `Env`. Never null. | CMP-SNAP-01 (from worker image) |
| `cpg_order_hash` | sha256 string + annotation | Hash of the canonical CPG order. Must be stored with annotation: `canonical iff fingerprint_class = strong`. | CMP-CORE-03 |

---

## Additional provenance fields (CMP-FND-02 schema)

| Field | Nullable? | Set by |
|---|---|---|
| `slice_fingerprint` | no | CMP-CORE-02 |
| `fingerprint_class` | no (`strong` / `weak`) | CMP-CORE-02 |
| `determinism_partition` | no | CMP-DET-02 (from manifest) |
| `witness_blob_uri` | yes (null for oracle findings without a slice) | CMP-ORCH-03 |
| `triage_score` | yes | CMP-TRI-01 (only when feature flag on) |
| `triage_reason` | yes | CMP-TRI-01 |
| `spec_provenance` | yes | CMP-TRI-03 (`global-unrevalidated` until revalidated) |
| `status` | no (`open` / `suppressed` / `fixed`) | CMP-FND-02 schema default |

---

## Signed audit chain (CMP-FND-03)

The full provenance record links:

```
source commit
  → snapshot digest
    → S_version
      → env_digest
        → cpg_order_hash (canonical iff strong)
          → taint witness
            → rule / spec id
              → SARIF hash
                → per-finding origin
```

Any differential-oracle re-partition event appends a record to this chain (CMP-SNAP-04, `TST-AC-SNAP-04c`).

---

## Per-component threading responsibilities

| Component | Must carry | Notes |
|---|---|---|
| CMP-SNAP-01 | `env_digest` on snapshot row | Sourced from container image digest |
| CMP-ORCH-03 | `S_version`, `env_digest`, `origin`, `determinism_partition` on every emitted finding | Origin derived from detector engine field |
| CMP-FND-01 | Passes through all four fields; attaches `slice_fingerprint`, `fingerprint_class` | SARIF emission in canonical order |
| CMP-FND-02 | Enforces NOT NULL on `origin`, `S_version`, `env_digest` at schema level | Index on `(codebase_id, slice_fingerprint)` |
| CMP-FND-03 | Full signed chain including `cpg_order_hash` with conditional annotation | Re-partition events appended |
| CMP-CORE-03 | `cpg_order_hash` + annotation everywhere it appears | Named `cpg_order_hash` (never "canonical CPG hash") |
| CMP-TRI-01 | Must NOT touch `origin`, `S_version`, `env_digest`; writes only `triage_*` columns | |
| CMP-TRI-02 | Accepted spec written as new `S_version`; core reads only pinned specs | |
| CMP-SNAP-04 | Re-partition event written to provenance; `origin` flipped on affected rows | |

---

## How to verify threading in code review

1. For every method that constructs a `Finding` or writes to the `findings` table, confirm all four required fields are present and non-null.
2. For `cpg_order_hash`: confirm the adjacent annotation string `"canonical iff fingerprint_class = strong"` is present in the same record.
3. For `CMP-TRI-01`: confirm it does NOT write to `origin`, `S_version`, `env_digest`, `slice_fingerprint`, or detection-content columns.
4. Run `TST-INV-2-*` and `TST-INV-1-*` for the component under review.

---

*Cross-reference: SDD.md §8 (CMP-FND-02, CMP-FND-03), PLAN.md §"Algorithm 5", CLAUDE.md §3 (INV-1, INV-2, INV-5)*
