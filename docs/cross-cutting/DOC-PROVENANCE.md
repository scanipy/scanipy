# DOC-PROVENANCE — Provenance record reference

**Owner:** Documentation Manager Agent
**Status:** ACTIVE (Phase 0 cross-cutting deliverable)
**Source-of-truth lineage:**

- `PLAN.md §"Context and the objective"` (property (c): `source commit → snapshot digest → S_version → env_digest → cpg_order_hash (canonical iff strong) → taint witness → rule/spec id → SARIF hash → per-finding origin`)
- `PLAN.md §"Algorithm 5 — Canonical CPG ordering, and the item-4 provenance rename"` (`cpg_order_hash` with conditional annotation)
- `PLAN.md §"Honest-labeling ledger"` (per-claim labelling)
- `SDD.md CMP-FND-02` (findings store schema), `SDD.md CMP-FND-03` (signed provenance record)
- `SDD.md CMP-SNAP-04` (differential-oracle re-partition events)
- `SDD.md §2 INV-1, INV-2, INV-5`
- `WBS.md §10 CMP-FND-03` (task list `T-CMP-FND-03-01..04`)
- `WBS.md §17 CLAR-DEPLOY-04` (AWS KMS envelope encryption), `CLAR-DEPLOY-15` (retention)
- `.claude/rules/02-provenance.md` (threading rules — this document is the canonical extension)
- `.claude/rules/01-invariants.md §INV-1, INV-2, INV-5`
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` (CLAR-DEPLOY-04, 15, 16)

This document is the canonical reference for the **full signed provenance chain**. It extends `.claude/rules/02-provenance.md` (which states the threading rules in code-review form) with full schema, signing/storage policy, and the auditor-export contract. Where this document and the source-of-truth above disagree, the source-of-truth wins.

---

## 1. Purpose

Provenance is the **load-bearing artifact** for three of the six architectural invariants:

- **INV-1** — every finding's `origin` is recorded and signed.
- **INV-2** — every finding's `S_version` and `env_digest` are recorded and signed.
- **INV-5** — the conditional canonicality of `cpg_order_hash` is recorded with its annotation, so an auditor reading the record can decide whether the canonical-form claim applies to their finding.

The provenance chain is also the **construction proof** of `PLAN.md` property (c): *"A logged construction, hence unconditional: source commit → snapshot digest → S version → Env digest → cpg_order_hash (canonical iff strong) → taint witness → rule/spec id → SARIF hash → per-finding origin"*. The chain is unconditional because every link in it is a logged step under operational control; this is the only one of the three load-bearing properties that does not require a precondition (cf. (a) reproducibility and (b) incremental computability, both of which carry preconditions in PLAN.md).

The chain is also the substrate for the **customer attestation export**: a customer-facing report that lists every finding's signed lineage, the conditional-canonicality annotation, and any differential-oracle re-partition events that have moved a finding between partitions.

---

## 2. The four required fields (INV-1, INV-2, INV-5)

Every finding and every provenance record carries the following four fields. `.claude/rules/02-provenance.md §"The four required fields"` is the code-review-time reference; this section is the schema-level reference.

| Field | Type | NOT NULL (schema) | Source-of-truth | Set by component |
|---|---|---|---|---|
| `origin` | enum `{deterministic-core, oracle-passthrough}` | **yes** (`AC-FND-02b`) | `INV-1` (`SDD.md §2`) | `CMP-ORCH-03` (`T-CMP-ORCH-03-03`) |
| `S_version` | semver string | **yes** (`AC-FND-02b`) | `INV-2` (`SDD.md §2`) | `CMP-ORCH-01` from scan submission; threaded by `CMP-ORCH-03` |
| `env_digest` | sha256 string (`"sha256:" + 64 hex`) | **yes** (`AC-FND-02b`) | `INV-2` (`SDD.md §2`) | `CMP-SNAP-01` from container image digest (`AC-SNAP-01c`, `AC-SNAP-05b`) |
| `cpg_order_hash` | sha256 string + annotation | **present and annotated** (`AC-CORE-03c`, `AC-FND-03b`); not declared NOT NULL by `AC-FND-02b` | `INV-5` (`SDD.md §2`, `PLAN.md` item-4 rename) | `CMP-CORE-03` (`T-CMP-CORE-03-04`) |

**Note on NOT NULL.** `AC-FND-02b` pins NOT NULL on exactly three columns: `origin`, `S_version`, `env_digest`. `cpg_order_hash` is required to be present and annotated wherever it appears (`AC-CORE-03c`, `AC-FND-03b`), but `SDD.md` does not declare it NOT NULL at the schema level — the conditional-canonicality annotation is the operative discipline, not a NOT NULL constraint. The schema in §3 below reflects this faithfully.

### 2.1 The conditional-canonicality annotation (INV-5)

The annotation that **must** accompany `cpg_order_hash` wherever it appears (`PLAN.md` item-4 rename; `AC-CORE-03c`):

```
canonical iff fingerprint_class = strong
```

Persisted in: the provenance record (§3), the SARIF `properties` block (cross-link to `DOC-SARIF`), and the customer-facing auditor export (§8). The annotation is **a string of textual prose stored alongside the hash**, not a derived computation — readers must encounter it without having to consult a separate document.

Counter-example (violation of `INV-5`): an auditor export that writes `"cpg_canonical_hash"` without stating that canonicality only holds on the `strong` path.

---

## 3. Full chain schema (`provenance_records` table)

`CMP-FND-03` (`T-CMP-FND-03-01`) constructs the signed audit chain `source commit → snapshot digest → S_version → env_digest → cpg_order_hash → taint witness → rule/spec id → SARIF hash → per-finding origin`. The chain is a **linked list of records**: one `record_type='chain'` row per finding, plus append-only `record_type='repartition'` rows linked back to the affected base record (§4), and scan-level rows for the other record types (`attestation`, `spec-acceptance`, `witness-update`).

> **Canonical DDL: `DOC-DB §4.13`.** Per the `CLAR-FND-01` resolution (2026-05-23), the authoritative `CREATE TABLE provenance_records` lives in `DOC-DB §4.13` — a single source of DDL, so the two documents cannot drift again. This section is the **semantic** reference: it states what each chain-link column carries (§3.1) and which bytes the signature covers (§3.2). Key facts of the reconciled shape:
>
> - **Materialisation:** column-per-link (one typed column per chain link), so INV-1/INV-2/INV-5 are enforced by the schema, not by application code over an opaque `jsonb` payload.
> - **Identity:** PK `id`; discriminator `record_type ∈ {chain, repartition, attestation, spec-acceptance, witness-update}` (`chain` = the per-finding base record); `parent_record_id → provenance_records(id)` for re-partition rows.
> - **Scope keys:** `scan_id` NOT NULL; `finding_id` NULL for scan-level record types.
> - **INV columns:** `S_version`, `env_digest` NOT NULL on **every** row (INV-2 binds every provenance record); `origin` NOT NULL only for `chain`/`repartition` rows (row-level CHECK, INV-1); `cpg_order_hash` paired with the `cpg_order_hash_annotation` pinned literal (INV-5).
> - **Signature:** `kms_key_arn` + `kms_key_version` + `signature` + `signature_alg`, baseline `RSASSA_PSS_SHA_256` (§7.3, `CLAR-DEPLOY-04`).
> - **Type-specific detail** (e-process metrics for `spec-acceptance`, attestation metrics for `attestation`) lives in the owning domain table (`spec_versions` / `attestations`), joined back via `spec_id` / `scan_id` — never inlined here.

### 3.1 Field-by-field cross-reference

| Field | Link in chain | Source | Set by | Invariant |
|---|---|---|---|---|
| `commit_sha` | 1 (source commit) | SCM webhook / scan request | `CMP-ORCH-01` | — |
| `snapshot_id`, `snapshot_digest`, `precondition_status` | 2 (snapshot digest) | Snapshot worker | `CMP-SNAP-01` (`T-CMP-SNAP-01-02`) | — |
| `S_version` | 3 | Scan submission, threaded by orchestrator | `CMP-ORCH-01`/`CMP-ORCH-03` | INV-2 |
| `env_digest` | 4 | Container image digest | `CMP-SNAP-01` (`AC-SNAP-01c`) | INV-2 |
| `cpg_order_hash` + `cpg_order_hash_annotation` + `fingerprint_class` | 5 | Algorithm 5 + Algorithm 3 | `CMP-CORE-03` (`T-CMP-CORE-03-04`), `CMP-CORE-02` (`T-CMP-CORE-02-04`) | INV-5 |
| `witness_blob_uri`, `slice_fingerprint` | 6 (taint witness) | IFDS solver + slice fingerprinter | `CMP-ORCH-03` + `CMP-CORE-02` | — |
| `rule_id`, `spec_id`, `detector_id`, `detector_engine` | 7 (rule/spec id) | Detector registry | `CMP-DET-02` + `CMP-ORCH-03` | — |
| `sarif_hash` | 8 (SARIF hash) | Normalizer | `CMP-FND-01` | — |
| `origin`, `determinism_partition` | 9 (per-finding origin) | Worker | `CMP-ORCH-03` (`T-CMP-ORCH-03-03`) | INV-1 |
| `signature`, `kms_key_arn`, `kms_key_version`, `signature_alg` | (signing envelope, §7) | KMS | `CMP-FND-03` (`T-CMP-FND-03-02`) | — |
| `claim_label` | (honest-labeling, §5) | derived from `origin` + gate status | `CMP-FND-03` | INV-6 (per-language honesty linkage) |

### 3.2 Canonical record-bytes (what the signature covers)

The signature is computed over the **canonical serialization** of every field above except `signature`, `kms_key_version` (the version is supplied separately), and `created_at`. Canonical serialization is JSON with keys sorted lexicographically, no insignificant whitespace, and UTF-8 encoding. The exact algorithm is specified in `DOC-API` (forthcoming sibling). A verifier reconstructs canonical bytes from the stored row, fetches the public key by `kms_key_arn`+`kms_key_version`, and verifies `signature` over the bytes (`AC-FND-03a` — *the record is independently verifiable from stored artifacts without re-running analysis*).

---

## 4. Re-partition event records (append-only, INV-1)

`CMP-SNAP-04` (`T-CMP-SNAP-04-02..03`) is the differential reflection oracle. When it disagrees with `CW-DETECT` — finding reflection in a snapshot that `CW-DETECT` labelled `closed-world` — every finding from that snapshot that carries `origin=deterministic-core` is **retroactively re-partitioned** to `origin=oracle-passthrough`. The re-partition cascade is recorded as new provenance records, **not** by mutating prior records.

### 4.1 Re-partition record shape

A re-partition record has `record_type = 'repartition'` and the following constraints additional to §3:

```sql
-- ALTER above table for the repartition CHECKs:
CHECK (record_type <> 'repartition'
       OR (parent_record_id IS NOT NULL
           AND repartition_reason IS NOT NULL
           AND repartition_oracle_id IS NOT NULL
           AND origin = 'oracle-passthrough'        -- always flip TO oracle
           AND cpg_order_hash IS NULL))             -- not recomputed on repartition
```

Key properties:

1. **Append-only.** The original `chain`-type record is never mutated. The re-partition record is **chained** via `parent_record_id`, preserving the audit trail.
2. **Flip is one-way.** `origin` always flips to `oracle-passthrough` on a re-partition; the reverse direction is not a re-partition event but a **re-run** under a corrected `CW-DETECT` (different `env_digest`).
3. **Oracle run id.** `repartition_oracle_id` references the specific `snap_oracle_runs` row that produced the disagreement; the verifier can reproduce the disagreement evidence from that row's artifacts.
4. **No new `cpg_order_hash`.** The re-partition does not re-run Algorithm 5; the hash from the parent record is the authoritative same-source hash.

### 4.2 SLA on the labelling-correction window

`AC-SNAP-04b` (`T-CMP-SNAP-04-04`) requires a contractual SLA on the time between the fast `CW-DETECT` decision and the async oracle verdict. Per `CLAR-SLA-01` (`WBS.md §17`, RESOLVED): **24h for high-impact incidents, 7d for routine**. The SLA is published per environment in `DOC-RUNBOOK` (forthcoming sibling).

During this labelling-correction window an affected finding briefly carries the wrong `origin`; the contract states this window explicitly and the customer notification fires per `T-CMP-SNAP-04-02` upon re-partition.

### 4.3 Cascade semantics

A single oracle disagreement may cascade to multiple findings (every finding from the affected snapshot whose `detector_engine ∈ {ifds, ide}`). Each affected finding gets its own re-partition record linked to the same `repartition_oracle_id` but different `parent_record_id` (one per affected base record). The cascade is atomic at the snapshot grain: either all affected records get a re-partition row or none does (DB transaction; `T-CMP-SNAP-04-03`).

---

## 5. Honest-labelling ledger linkage

`PLAN.md §"Honest-labeling ledger"` partitions every claim made by the platform into one of four categories:

- `CONDITIONAL_THEOREM` — proven under a named precondition with a named owner.
- `EMPIRICAL` — measured against a published threshold (no theorem).
- `STAGED` — per-language readiness; covered by Algorithm 2 recall claims only on CPG-fidelity-gate-passing `(class, language)` pairs (`INV-6`).
- `UNCONDITIONAL` — provenance construction itself, e.g. property (c).

Every provenance record carries a `claim_label` (§3) so that the per-finding lineage states its own evidentiary status. The derivation:

```
claim_label := match (origin, detector_engine, stage_gate_status):
    ("deterministic-core",  "ifds" | "ide",     "passed")  -> CONDITIONAL_THEOREM
    ("deterministic-core",  "ifds" | "ide",     "not-applicable-yet") -> STAGED
    ("oracle-passthrough", _, _)                          -> EMPIRICAL
    -- The chain itself (the record's existence + signature) is UNCONDITIONAL;
    -- claim_label refers to the per-finding detection claim, not the chain.
```

The per-finding `claim_label` plus the `(class, language)` gate status (from `CMP-CP-06`, recorded in the manifest snapshot frozen at scan time) gives an auditor the full evidentiary basis for the finding. The ledger in `PLAN.md` is therefore reproducible **mechanically** from the provenance store; `SDD.md §14` requires the honest-labelling ledger to be "a living status table driven by AC pass/fail rather than as prose", and the `claim_label` is the per-finding feed into that table.

---

## 6. Storage and retention

Per `CLAR-DEPLOY-02` (S3) and `CLAR-DEPLOY-15` (retention), both RESOLVED in `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`:

| Artifact | Store | Key path | Retention | Lock |
|---|---|---|---|---|
| `provenance_records` row | PostgreSQL (`RDS` per `CLAR-DEPLOY-03`) | row-level | 7 years | row immutable post-sign |
| Signed canonical bytes | S3 | `orgs/{org_id}/codebases/{codebase_id}/provenance/{commit_sha}/{id}.json.sig` | **7 years** | **S3 Object Lock — Compliance mode** |
| Witness blob | S3 | `orgs/{org_id}/codebases/{codebase_id}/witness/{slice_fingerprint}.json` | 1 year | governance mode |
| SARIF blob | S3 | `orgs/{org_id}/codebases/{codebase_id}/sarif/{scan_id}.sarif.json` | 7 years | Compliance mode |
| CPG tarball | S3 | `orgs/{org_id}/codebases/{codebase_id}/snapshots/{commit_sha}/{env_digest}/cpg.tar.zst` | 90 days | governance mode |

The **7-year + Object-Lock-Compliance** discipline on SARIF + provenance protects the record against any in-tenancy mutation (even by an `org-admin`) until the retention expires (`CLAR-DEPLOY-15`). The customer-facing auditor export (§8) is generated from these records on demand and never replaces them.

`CMP-DEPLOY-05` (tenant isolation) and `CLAR-DEPLOY-16` (per-tenant CMKs + S3 prefix + RLS) enforce that no worker, query, or API surface can resolve a `provenance_records` row, S3 prefix, or KMS data key across an org boundary.

---

## 7. Signing key management

Per `CLAR-DEPLOY-04` (RESOLVED) — **AWS KMS envelope encryption with one per-tenant Customer-Managed Key (CMK)**, annual rotation via KMS automatic rotation. Asymmetric signing keys (RSASSA-PSS / SHA-256 baseline) per tenant for `CMP-FND-03` signing.

### 7.1 Why envelope encryption preserves prior signatures

The KMS envelope-encryption pattern stores `kms_key_version` alongside each signature. When a key rotates:

1. The CMK material rotates (new version generated).
2. Past ciphertexts (and signatures verified against past public keys) remain valid because the **version-pinned public key for the prior version stays resolvable** via `kms_key_arn` + `kms_key_version`.
3. New records use the latest version. The CMK ARN does not change.

A verifier presented with an old provenance record reads `kms_key_arn` + `kms_key_version` from the record, asks KMS for the public key material at that version, and verifies the signature. Rotation never invalidates a prior signature. This satisfies `AC-CP-02a` (rotation supported) and `AC-FND-03a` (independently verifiable).

### 7.2 Key access scope

- One CMK per tenant (`CLAR-DEPLOY-16`); no cross-tenant key access.
- `CMP-FND-03` worker IAM role can `kms:Sign` against the tenant CMK at the active version only; cannot delete keys, cannot disable rotation, cannot create new aliases.
- Customer-facing read paths can `kms:GetPublicKey` for verification but cannot sign.
- KMS Audit logs (CloudTrail) capture every `Sign` and `GetPublicKey` invocation per `CMP-DEPLOY-03` observability (`AC-DEPLOY-03b`).

### 7.3 Signature algorithm

Default: `RSASSA_PSS_SHA_256`. Recorded in the `signature_alg` column so a verifier can pick the correct verification path if the algorithm rolls forward.

---

## 8. Auditor export

`AC-FND-03b` requires the customer-facing auditor export to surface `cpg_order_hash` together with its conditional-canonicality annotation. The export is generated from `provenance_records` plus the linked S3 artifacts and is the load-bearing customer artifact for INV-1, INV-2, INV-5.

### 8.1 Required fields in the auditor export

Per finding (one row in the export, plus zero-or-more re-partition rows linked):

```json
{
  "id":                       "uuid",
  "parent_record_id":         "uuid | null",
  "record_type":              "chain | repartition | attestation | spec-acceptance | witness-update",

  "commit_sha":               "40-hex",
  "snapshot_digest":          "sha256:...",
  "precondition_status":      "closed-world | degraded | full-reparse",

  "S_version":                "semver",
  "env_digest":               "sha256:...",

  "cpg_order_hash":           "sha256:...",
  "cpg_order_hash_annotation":"canonical iff fingerprint_class = strong",
  "fingerprint_class":        "strong | weak | null",

  "witness_blob_uri":         "s3://... | null",
  "slice_fingerprint":        "sha256:... | null",

  "rule_id":                  "string",
  "spec_id":                  "string | null",
  "detector_id":              "string",
  "detector_engine":          "ifds | ide | semgrep | cpg-query | external",

  "sarif_hash":               "sha256:...",
  "origin":                   "deterministic-core | oracle-passthrough",
  "determinism_partition":    "deterministic-core | oracle-passthrough",
  "claim_label":              "CONDITIONAL_THEOREM | EMPIRICAL | STAGED | UNCONDITIONAL",

  "kms_key_arn":              "arn:aws:kms:...",
  "kms_key_version":          "string",
  "signature":                "base64",
  "signature_alg":            "RSASSA_PSS_SHA_256",

  "repartition_history": [
    {
      "id":                   "uuid",
      "created_at":           "iso-8601",
      "repartition_reason":   "string",
      "repartition_oracle_id":"uuid",
      "new_origin":           "oracle-passthrough"
    }
  ]
}
```

### 8.2 The conditional-canonicality annotation must be visually adjacent to the hash

`AC-FND-03b` and `INV-5` are about the auditor *encountering* the annotation alongside the hash, not having to derive it. In the export above, the field `cpg_order_hash_annotation` is **adjacent in the JSON document** to `cpg_order_hash`. The dashboard rendering (`CMP-CP-04`, `AC-CP-04b`) and any PDF or CSV export must preserve this visual adjacency — a row that prints the hash without the annotation is an `INV-5` violation.

### 8.3 The export must not visually blur partitions

`AC-CP-04b` requires the findings view to never visually blur `deterministic-core` and `oracle-passthrough`. The export carries `origin` and `claim_label` per finding; downstream UI / CSV / PDF must render them as distinct columns or distinct visual treatments.

### 8.4 Independent verifiability without re-running analysis

`AC-FND-03a` requires that the record be independently verifiable from stored artifacts. The verifier procedure:

```
verify_record(record):
    1. Reconstruct canonical record bytes per §3.2.
    2. Fetch public key from KMS at (kms_key_arn, kms_key_version).
    3. Verify signature over canonical bytes with signature_alg.
    4. Fetch S3 artifacts (sarif, witness, cpg tarball if needed) and recompute their digests.
    5. Assert recomputed digests == those in the record (sarif_hash, snapshot_digest).
    6. If record_type == 'repartition':
         a. Verify parent record per step 1-5.
         b. Fetch the oracle-run artifact at repartition_oracle_id.
         c. Verify the oracle's disagreement with CW-DETECT for the parent snapshot.
    Output: VERIFIED | TAMPERED(field) | KEY_NOT_FOUND | ARTIFACT_MISSING.
```

The full procedure runs without re-running IFDS, Algorithm 5, or any detector — only digest recomputation and signature verification.

---

## 9. Tests that enforce each field

The per-component invariant-verification suite (`WBS.md §4.3`) plus the `TST-AC-*` suite covers every provenance field. Cross-reference table:

| Field / property | `TST-AC-*` | `TST-INV-*` |
|---|---|---|
| `origin` set correctly per engine | `TST-AC-ORCH-03a`, `TST-AC-ORCH-03b` | `TST-INV-1-ORCH-03`, `TST-INV-1-FND-01..03` |
| `origin` flipped on re-partition | `TST-AC-SNAP-04a`, `TST-AC-SNAP-04c` | `TST-INV-1-SNAP-04` |
| `origin` not touched by triage | `TST-AC-TRI-01a` | `TST-INV-1-TRI-01`, `TST-INV-3-TRI-01` |
| `S_version` non-null per row | `TST-AC-FND-02b` | `TST-INV-2-FND-02`, `TST-INV-2-ORCH-03` |
| `S_version` version-pinned spec | `TST-AC-TRI-02c` | `TST-INV-2-TRI-02` |
| `env_digest` non-null per row | `TST-AC-FND-02b`, `TST-AC-SNAP-01c` | `TST-INV-2-SNAP-01`, `TST-INV-2-FND-02` |
| `env_digest` derived from image digest | `TST-AC-SNAP-05b` | — |
| `cpg_order_hash` named correctly + annotated | `TST-AC-CORE-03c`, `TST-AC-FND-03b` | `TST-INV-5-CORE-03`, `TST-INV-5-FND-03` |
| `fingerprint_class` set + `weak` never auto-suppressed | `TST-AC-CORE-02c` | `TST-INV-5-CORE-02` |
| Re-partition event recorded | `TST-AC-SNAP-04c`, `TST-AC-FND-03c` | `TST-INV-1-SNAP-04` |
| Independent verifiability | `TST-AC-FND-03a` | — |
| Conditional annotation in auditor export | `TST-AC-FND-03b` | `TST-INV-5-FND-03` |
| Findings view never blurs partitions | `TST-AC-CP-04b` | — |
| Attestor `LLM_TRIAGE=off` | `TST-AC-CP-05a`, `TST-AC-CP-05b` | `TST-INV-3-CP-05` |

---

## 10. Per-component threading responsibilities (canonical version)

This subsumes the table in `.claude/rules/02-provenance.md §"Per-component threading responsibilities"`; that file is the code-review shortcut, this is the canonical reference.

| Component | Writes (provenance fields) | Must NOT touch | Tests |
|---|---|---|---|
| `CMP-SNAP-01` | `snapshot_digest`, `env_digest`, `precondition_status` | `origin`, `S_version`, `cpg_order_hash` | `TST-AC-SNAP-01a..c`, `TST-INV-2-SNAP-01` |
| `CMP-SNAP-04` | new re-partition record; `repartition_*` fields; flips dependent records' `origin` (via append) | parent record fields (immutable post-sign) | `TST-AC-SNAP-04a..c`, `TST-INV-1-SNAP-04` |
| `CMP-CORE-03` | `cpg_order_hash` + `cpg_order_hash_annotation` | — | `TST-AC-CORE-03a..c`, `TST-INV-5-CORE-03` |
| `CMP-CORE-02` | `slice_fingerprint`, `fingerprint_class` | `cpg_order_hash`, `origin` | `TST-AC-CORE-02a..c`, `TST-INV-5-CORE-02` |
| `CMP-DET-02` | `detector_id`, `detector_engine`, `rule_id`, `spec_id`, `determinism_partition` (derived in manifest) | finding-level rows | `TST-AC-DET-02a..c` |
| `CMP-ORCH-01` | `S_version` (from scan submission), `commit_sha` | finding-level rows | `TST-AC-ORCH-01a..c` |
| `CMP-ORCH-03` | `origin`, `determinism_partition`, threads `S_version`, `env_digest` onto every finding | `cpg_order_hash` (delegates to `CMP-CORE-03`); detection content of other detectors | `TST-AC-ORCH-03a..b`, `TST-INV-1-ORCH-03`, `TST-INV-2-ORCH-03` |
| `CMP-FND-01` | passes through all four required fields; `sarif_hash` | `origin` (it is already set; just passes through) | `TST-AC-FND-01a..b`, `TST-INV-1-FND-01` |
| `CMP-FND-02` | NOT-NULL enforcement on `origin`, `S_version`, `env_digest` at schema | — | `TST-AC-FND-02a..b`, `TST-INV-1-FND-02`, `TST-INV-2-FND-02` |
| `CMP-FND-03` | the full chain; `signature`, `kms_key_arn`, `kms_key_version`, `signature_alg`, `claim_label` | original records once signed (append-only thereafter) | `TST-AC-FND-03a..c`, `TST-INV-1-FND-03`, `TST-INV-5-FND-03` |
| `CMP-TRI-01` | `triage_score`, `triage_reason` only (in `findings`, not `provenance_records`) | `origin`, `S_version`, `env_digest`, `slice_fingerprint`, `cpg_order_hash`, `rule_id` | `TST-AC-TRI-01a..b`, `TST-INV-1-TRI-01`, `TST-INV-3-TRI-01` |
| `CMP-TRI-02` | writes accepted spec as new `S_version` row in `spec_versions`; core consumes only pinned `S_version` | `provenance_records` directly | `TST-AC-TRI-02a..c`, `TST-INV-2-TRI-02` |
| `CMP-CP-05` | (Attestor reads provenance, does not mutate) | `provenance_records` (read-only) | `TST-AC-CP-05a..c`, `TST-INV-3-CP-05` |

---

## 11. References

- `PLAN.md §"Context and the objective"` — property (c) chain definition.
- `PLAN.md §"Algorithm 5"` — item-4 rename to `cpg_order_hash` with conditional annotation.
- `PLAN.md §"Honest-labeling ledger"` — claim-label partition feeding `claim_label`.
- `SDD.md CMP-FND-02` — store schema; `SDD.md CMP-FND-03` — signed chain.
- `SDD.md CMP-SNAP-04` — re-partition event source.
- `SDD.md §2 INV-1, INV-2, INV-5` — provenance-bearing invariants.
- `WBS.md §10 CMP-FND-03` — implementation tasks (`T-CMP-FND-03-01..04`).
- `WBS.md §17 CLAR-DEPLOY-04`, `CLAR-DEPLOY-15`, `CLAR-DEPLOY-16`, `CLAR-SLA-01` — resolved deployment / SLA decisions.
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — substrate decision record (KMS, S3, retention, isolation).
- `.claude/rules/02-provenance.md` — code-review-time threading rules (canonically extended here).
- `.claude/rules/01-invariants.md` — invariant catalog.
- `DOC-DB §4.13` — **canonical DDL** for `provenance_records` (CLAR-FND-01 RESOLVED 2026-05-23).
- `DOC-API` — canonical record-bytes serialization.
- `DOC-SARIF` — SARIF `properties` block carrying the conditional annotation.
- `DOC-INV` — INV-1/2/5 owner cross-reference.
- `DOC-RUNBOOK` (forthcoming sibling) — labelling-correction window SLA and re-partition incident procedure.

---

*Document end. Status: ACTIVE. Next review: at first acceptance of `CMP-FND-03` `DONE`, or on resolution of `CLAR-OWNER-01` (per-component owner assignment).*
