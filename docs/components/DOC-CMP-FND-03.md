# DOC-CMP-FND-03 — Signed provenance record

> **Status:** ACTIVE (Phase 0 deliverable). Satisfies `AC-DOC-04`: an Implementation Agent given only this document plus the cross-cutting refs (`DOC-PROVENANCE`, `DOC-DB`, `DOC-INV`, `DOC-SARIF`, `DOC-DEPLOY-DECISIONS`, `DOC-PARTITION`, `DOC-GLOSSARY`) can produce a passing implementation without re-reading `SDD.md`.

---

## 1. Component identity

| Field | Value |
|---|---|
| **CMP-ID** | `CMP-FND-03` |
| **Subsystem** | Findings & Provenance (`SDD.md §8`) — **signed-chain owner** |
| **Module path** | `services/scan/provenance/` (chain construction, signing, verification, auditor export) |
| **Staging** | Stage A (per `SDD.md §8`) |
| **Depends-On** | `CMP-FND-02` (per `WBS.md §20`) |
| **Touches invariants** | INV-1 (records per-finding `origin` in chain link 9); INV-2 (chain links 3 + 4 carry `S_version`, `env_digest`); **INV-5** (chain link 5 carries `cpg_order_hash` with the literal annotation in the auditor export) |
| **Primary contract** | `DOC-PROVENANCE.md` (chain shape, 9-link chain, KMS signing, auditor export) |
| **Owning maintainer** | Findings & Provenance team |

---

## 2. Mandate

**SDD `Purpose:` (verbatim from `SDD.md §8 → CMP-FND-03`):**

> The auditable chain `source commit → snapshot digest → S_version → env_digest → cpg_order_hash (canonical iff strong) → taint witness → rule/spec id → SARIF hash → per-finding origin`, signed.

**Operational role.** This component is the **construction proof** of `PLAN.md` property (c) — *"a logged construction, hence unconditional"*. For every `findings` row, it materialises a `provenance_records` row carrying the 9-link chain (above), signs the canonical record bytes via AWS KMS asymmetric signature (per `CLAR-DEPLOY-04` RESOLVED), and persists the result append-only. It also persists differential-oracle **re-partition events** as new chained records linked by `parent_record_id` to the affected base record (`DOC-PROVENANCE.md §4`). Finally, it generates the **auditor export** that surfaces every chain field to customers (and to internal auditors), with the conditional-canonicality annotation visually adjacent to the hash (`AC-FND-03b`, `INV-5`).

The chain is independently verifiable from stored artefacts without re-running analysis (`AC-FND-03a`) — a verifier reconstructs canonical bytes, fetches the public key from KMS by `(kms_key_arn, kms_key_version)`, verifies the signature, then recomputes blob digests (SARIF hash, snapshot digest, witness digest).

---

## 3. Interface contract

### 3.1 Public Python signatures

```python
from dataclasses import dataclass
from typing import Literal, NewType
import uuid

Sha256       = NewType("Sha256", bytes)             # 32 bytes
Sha256Hex    = NewType("Sha256Hex", str)            # 64 hex
SemVer       = NewType("SemVer", str)
RecordKind   = Literal["finding", "repartition"]
Origin       = Literal["deterministic-core", "oracle-passthrough"]
SignatureAlg = Literal["RSASSA_PSS_SHA_256"]        # CLAR-DEPLOY-04 baseline
ClaimLabel   = Literal["CONDITIONAL_THEOREM", "EMPIRICAL", "STAGED", "UNCONDITIONAL"]

@dataclass(frozen=True)
class ProvenanceRecord:
    """The 9-link chain, pre-signature (DOC-PROVENANCE §3)."""
    # Identity & chain linkage
    record_id:                 uuid.UUID
    parent_record_id:          uuid.UUID | None      # set for repartition records
    record_kind:               RecordKind
    # Link 1 — source commit
    org_id:                    uuid.UUID
    codebase_id:               uuid.UUID
    commit_sha:                str                   # 40 hex
    scm_provider:              str                   # 'github'|'gitlab'|...
    # Link 2 — snapshot digest
    snapshot_id:               uuid.UUID
    snapshot_digest:           Sha256Hex
    precondition_status:       Literal["closed-world","degraded","full-reparse"]
    # Links 3 + 4 — INV-2
    S_version:                 SemVer
    env_digest:                Sha256Hex             # sha256:hex64
    # Link 5 — cpg_order_hash + INV-5 annotation
    cpg_order_hash:            Sha256 | None         # NULL only on repartition records
    cpg_order_hash_annotation: str                   # MUST be the literal constant
    fingerprint_class:         Literal["strong","weak"] | None
    # Link 6 — taint witness
    witness_blob_uri:          str | None
    slice_fingerprint:         Sha256 | None
    # Link 7 — rule / spec id
    rule_id:                   str
    spec_id:                   str | None
    detector_id:               str
    detector_engine:           Literal["ifds","ide","semgrep","cpg-query","external"]
    # Link 8 — SARIF hash (from CMP-FND-01)
    sarif_hash:                Sha256
    # Link 9 — per-finding origin (INV-1)
    origin:                    Origin
    determinism_partition:     Origin
    # Re-partition linkage (DOC-PROVENANCE §4)
    repartition_reason:        str | None
    repartition_oracle_id:     uuid.UUID | None
    # Honest-labeling (DOC-PROVENANCE §5)
    claim_label:               ClaimLabel

@dataclass(frozen=True)
class SignedProvenanceRecord:
    record:           ProvenanceRecord
    canonical_bytes:  bytes                          # JSON, lexicographic keys, no whitespace, UTF-8
    kms_key_arn:      str
    kms_key_version:  str
    signature:        bytes                          # KMS asymmetric signature over canonical_bytes
    signature_alg:    SignatureAlg

def sign_provenance(record: ProvenanceRecord) -> SignedProvenanceRecord:
    """
    1. Compute canonical_bytes per DOC-PROVENANCE §3.2.
    2. Call kms:Sign on the tenant CMK with SigningAlgorithm = RSASSA_PSS_SHA_256
       (CLAR-DEPLOY-04). Resolves the CMK ARN via the tenant config (one CMK per tenant
       per CLAR-DEPLOY-16).
    3. Persist to provenance_records and to S3
       `orgs/{org_id}/codebases/{codebase_id}/provenance/{commit_sha}/{record_id}.json.sig`
       under Object Lock (Compliance mode, 7y per CLAR-DEPLOY-15).
    """
    ...

def verify_chain(record: SignedProvenanceRecord) -> Literal["VERIFIED","TAMPERED","KEY_NOT_FOUND","ARTIFACT_MISSING"]:
    """
    Per DOC-PROVENANCE §8.4. Does NOT re-run IFDS / Algorithm 5 / detectors.
    Steps:
      1. Reconstruct canonical_bytes from `record.record` per §3.2.
      2. Fetch KMS public key at (kms_key_arn, kms_key_version).
      3. Verify signature over canonical_bytes with signature_alg.
      4. Fetch S3 artefacts (sarif, witness, snapshot tarball if cached) and recompute digests.
      5. Assert recomputed digests match record.sarif_hash and record.snapshot_digest.
      6. If record_kind == 'repartition':
           a. Verify parent record per 1..5.
           b. Fetch the oracle-run artefact at repartition_oracle_id and assert its
              disagreement with CW-DETECT for the parent snapshot.
    """
    ...

def export_auditor_record(record_id: uuid.UUID) -> dict:
    """Per DOC-PROVENANCE §8.1. The dict's `cpg_order_hash` and
    `cpg_order_hash_annotation` keys MUST be JSON-adjacent."""
    ...
```

### 3.2 Append-only re-partition path

```python
def append_repartition_event(
    *, parent_record_id: uuid.UUID,
    repartition_oracle_id: uuid.UUID,
    repartition_reason: str,
) -> SignedProvenanceRecord:
    """
    Called by CMP-SNAP-04 within the same DB transaction as the
    repartition_events INSERT + findings.origin UPDATE.

    Constructs a new record with record_kind='repartition', origin='oracle-passthrough',
    parent_record_id set, cpg_order_hash NULL (not recomputed on repartition per
    DOC-PROVENANCE §4.1), signs, persists. The parent record is NEVER mutated
    (append-only chain per AC-FND-03c).
    """
    ...
```

### 3.3 The canonical annotation literal

This component imports the same constant the SARIF emitter uses:

```python
from analysis.ordering import CPG_ORDER_HASH_ANNOTATION
# == "canonical iff fingerprint_class = strong"
```

Every `ProvenanceRecord.cpg_order_hash_annotation` is set from this constant. The DB CHECK constraint enforces the literal (DOC-DB defence-in-depth). The auditor export emits the constant in a JSON key visually adjacent to `cpg_order_hash` (`AC-FND-03b`).

### 3.4 Canonical record-bytes (signature input)

Per `DOC-PROVENANCE.md §3.2`: JSON with keys sorted lexicographically by Unicode code point, no insignificant whitespace, UTF-8 encoding. The signature covers every field of `ProvenanceRecord` **except** `signature`, `kms_key_version`, and `created_at`. The exact algorithm is the same as `DOC-SARIF.md §3` — minified JSON with lexicographic key order.

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source |
|---|---|
| `findings` row | `CMP-FND-02` (this component reads, never mutates) |
| `snapshot_digest`, `env_digest`, `precondition_status` | `CMP-SNAP-01` via `snapshots` row |
| `S_version` | `CMP-ORCH-01` via `findings.S_version` |
| `cpg_order_hash`, `cpg_order_hash_annotation`, `fingerprint_class` | `CMP-CORE-03` via `findings` row |
| `slice_fingerprint`, `witness_blob_uri` | `CMP-CORE-02` (slice) + `CMP-ORCH-03` (uri) |
| `rule_id`, `spec_id`, `detector_id`, `detector_engine` | `CMP-DET-02` manifest + `findings` row |
| `sarif_hash` | `CMP-FND-01` (`SARIFLog.sarif_hash` or per-partition `SARIFRun.sarif_hash`) |
| `origin`, `determinism_partition` | `CMP-ORCH-03` via `findings` row |
| Re-partition trigger | `CMP-SNAP-04` (`AC-SNAP-04a/b/c`) |
| KMS CMK | per-tenant, resolved from `orgs.kms_cmk_arn` (`DOC-DB.md §4.1`) |

### 4.2 Outputs

| Output | Consumer |
|---|---|
| `provenance_records` row | `CMP-CP-05` (Attestor reads, never mutates); `CMP-CP-04` dashboard; auditor export endpoint |
| S3 signed canonical bytes | independent verifier; long-term audit retrieval |
| `SignedProvenanceRecord` (in-memory) | `attestations.signed_chain_id` FK target (`DOC-DB.md §4.10`) |
| Auditor export JSON | `GET /api/v1/attestations/{scan_id}` (`DOC-API.md §4.7`); customer dashboard; CSV / PDF export |

### 4.3 Persisted artefacts

| Artefact | Location | Retention |
|---|---|---|
| `provenance_records` row | PostgreSQL (`DOC-DB.md §4.13`) | 7 years (per `CLAR-DEPLOY-15`) |
| Signed canonical bytes | S3 `orgs/{org_id}/codebases/{codebase_id}/provenance/{commit_sha}/{record_id}.json.sig` | 7 years, S3 Object Lock — Compliance mode (per `CLAR-DEPLOY-15`) |

---

## 5. Invariants touched

### 5.1 INV-1 — Determinism partition (chain link 9 + re-partition append)

- Every `ProvenanceRecord.origin` is set from the `findings` row verbatim (the `findings` schema's enum CHECK guarantees it is one of the two values).
- Re-partition events are recorded as **new** records with `origin = 'oracle-passthrough'` and `parent_record_id` pointing at the affected base record. The base record is **never** mutated (append-only; `DOC-PROVENANCE.md §4.1`). This satisfies `AC-FND-03c`.
- The auditor export's `repartition_history` array (`DOC-PROVENANCE.md §8.1`) surfaces every re-partition for that finding.

### 5.2 INV-2 — Versioned parameters (chain links 3, 4)

- `ProvenanceRecord.S_version` (link 3) and `.env_digest` (link 4) are non-null on every record. The DB enforces NOT NULL (`DOC-DB.md §5`).
- The canonical bytes that the signature covers include both fields; tampering with either invalidates the signature.

### 5.3 INV-5 — Conditional canonicality annotation (**LITERAL EMITTER, AUDITOR EXPORT OWNER**)

- `ProvenanceRecord.cpg_order_hash_annotation` is set from the `CPG_ORDER_HASH_ANNOTATION` constant. Never constructed locally.
- The DB column has a literal CHECK constraint enforcing the exact string (`DOC-DB.md §4.13`).
- The auditor export emits `cpg_order_hash` and `cpg_order_hash_annotation` as JSON-adjacent keys (`DOC-PROVENANCE.md §8.2`). Any UI / CSV / PDF rendering MUST preserve visual adjacency (`AC-CP-04b`).
- `AC-FND-03b` is satisfied iff the annotation appears alongside the hash everywhere it is surfaced.

**Counter-example (do not write).** Auditor export JSON:
```json
{"cpg_order_hash": "a3f9...64hex"}
```
This is an INV-5 violation — the annotation has been stripped. Compare with the correct shape (`DOC-PROVENANCE.md §8.1`):
```json
{
  "cpg_order_hash":            "a3f9...64hex",
  "cpg_order_hash_annotation": "canonical iff fingerprint_class = strong",
  "fingerprint_class":         "strong"
}
```

### 5.4 INV-4 (passive)

This component does not approximate anything undecidable. INV-4 is not its concern.

### 5.5 INV-6 — Honest labelling ledger linkage

The `claim_label` field on every record is derived from `origin × detector_engine × stage_gate_status` per the matching table in `DOC-PROVENANCE.md §5`:

```
("deterministic-core",  "ifds"|"ide", "passed")            -> CONDITIONAL_THEOREM
("deterministic-core",  "ifds"|"ide", "not-applicable-yet") -> STAGED
("oracle-passthrough", _, _)                                -> EMPIRICAL
```

The chain construction itself (record existence + signature) is `UNCONDITIONAL` (property (c) of PLAN.md). The `claim_label` on a record refers to the *per-finding detection claim*, not the chain. The honest-labelling ledger in `PLAN.md §"Honest-labeling ledger"` is reproducible mechanically by aggregating `claim_label` over all records.

---

## 6. Dependency contract

`Depends-On:` **`CMP-FND-02`** (per `WBS.md §20`).

This component **assumes**:

- `CMP-FND-02` has created the `findings` and `provenance_records` tables (the latter is in the `CMP-FND-02` migration set per `DOC-DB.md §4.13`); FKs from `provenance_records` to `findings`, `scans`, `orgs` resolve.
- `CMP-FND-01` has computed `sarif_hash` for the relevant scan (per-partition or whole-log).
- `CMP-FND-02`'s `findings_cpg_order_hash_annotation_literal` CHECK is enforced (defence-in-depth — even a buggy FND-03 emitter cannot insert a wrong annotation).
- `CMP-CORE-03` has exposed the `CPG_ORDER_HASH_ANNOTATION` constant.
- AWS KMS is configured per `CLAR-DEPLOY-04` RESOLVED: one CMK per tenant (`orgs.kms_cmk_arn`), asymmetric signing key, baseline algorithm `RSASSA_PSS_SHA_256`, annual rotation via KMS automatic rotation; CloudTrail captures every `kms:Sign` and `kms:GetPublicKey` invocation.
- S3 retention class with Object Lock — Compliance mode is provisioned for the `provenance/` prefix per `CLAR-DEPLOY-15` (7 years).
- `CMP-SNAP-04` (re-partition source) is the **only** caller of `append_repartition_event`.

This component is consumed by **`CMP-SNAP-01`** (links to provenance record via `WBS.md §20`: `CMP-SNAP-01 → [CMP-SCM-01, CMP-FND-03]`), **`CMP-CP-04`** (dashboard surfaces records), **`CMP-CP-05`** (Attestor reads `attestations.signed_chain_id`).

---

## 7. Failure modes and error contracts

### 7.1 Failure modes

| Mode | Detection | Response |
|---|---|---|
| KMS signing failure (`kms:Sign` throttled, key disabled, transient) | KMS API error | Exponential backoff with jitter (5 retries up to 30s); on final failure, alarm + page; the affected record stays unsigned in a `pending_signature` retry queue. **Do not** persist a record with `signature = NULL` to the main `provenance_records` table. |
| KMS signing algorithm not enabled on key | KMS `KMSInvalidStateException` | Hard fail; alarm; the tenant CMK is misconfigured — operator intervention required. |
| Signature verification mismatch (verifier path) | KMS public-key verify returns false | Flag chain as `TAMPERED(field=signature)`; alarm with high severity; the record is preserved (immutable) for forensic inspection. |
| Annotation literal mismatch on a constructed record | Application-layer assertion before DB INSERT | Raise `InvariantViolation(code="invariant_inv5_violation")` per `DOC-API.md §6.1`; HTTP 500. The DB CHECK would catch it too, but the application-layer catch yields a clearer error. |
| Re-partition append without parent | application-layer guard + DB FK constraint on `parent_record_id` | rollback; raise `RepartitionWithoutParent`. |
| Missing parent chain link on re-partition verify | verifier step 6a fails | `VERIFIED` returns the tamper code; alarm. |
| Object Lock prevents mutation (correct behaviour) | S3 `ObjectLockRetainUntilDate` enforced | This is the *intended* response to any attempt to mutate or delete a signed artefact within retention. |
| Attempted mutation of a base record after re-partition | Application-layer policy (no UPDATE on `provenance_records`) | Rollback; alarm. `provenance_records` has **no UPDATE / DELETE grants** per `DOC-DB.md §4.13` — the table is append-only. |
| Cross-tenant KMS access attempt | KMS IAM denies | The worker role is scoped to one CMK ARN per task per `CLAR-DEPLOY-16`; cross-tenant access raises `AccessDeniedException`. |

### 7.2 Append-only discipline

`provenance_records` is **append-only** by grant (no UPDATE / DELETE on the table). Once a record is signed and inserted, it is immutable for the lifetime of S3 Object Lock. Re-partition events are *new* records with `parent_record_id` set, never UPDATEs of the parent. `T-CMP-FND-03-04` is the operational implementation; `AC-FND-03c` is the AC.

### 7.3 Idempotency

`sign_provenance` is *not* idempotent at the signature level — calling KMS twice produces two different signatures (RSASSA-PSS uses random salt). However, the same `record_id` constraint on `provenance_records` (PK) prevents a second insert. Callers must use stable `record_id`s (UUIDv4 generated once, persisted with the signed payload).

---

## 8. Provenance threading

This component **constructs** the chain; it is the canonical writer of every link except where another component already wrote it on `findings` (then FND-03 reads and copies):

| Chain link | Source | Field on `provenance_records` |
|---|---|---|
| 1 — source commit | SCM webhook / scan request via `findings.commit_sha` | `commit_sha`, `scm_provider` |
| 2 — snapshot digest | `CMP-SNAP-01` via `snapshots.cpg_tarball_uri` digest | `snapshot_id`, `snapshot_digest`, `precondition_status` |
| 3 — `S_version` | `findings.S_version` (already INV-2 NOT NULL) | `S_version` |
| 4 — `env_digest` | `findings.env_digest` (already INV-2 NOT NULL) | `env_digest` |
| 5 — `cpg_order_hash` + annotation | `findings.cpg_order_hash` + `CPG_ORDER_HASH_ANNOTATION` | `cpg_order_hash`, `cpg_order_hash_annotation`, `fingerprint_class` |
| 6 — taint witness | `findings.witness_blob_uri`, `findings.slice_fingerprint` | `witness_blob_uri`, `slice_fingerprint` |
| 7 — rule / spec id | `findings.rule_id`, `CMP-DET-02` manifest for `detector_id`, `detector_engine`, `spec_id` | `rule_id`, `spec_id`, `detector_id`, `detector_engine` |
| 8 — SARIF hash | `CMP-FND-01` `SARIFLog.sarif_hash` (or per-partition) | `sarif_hash` |
| 9 — per-finding `origin` | `findings.origin` | `origin`, `determinism_partition` |

Signing envelope (set by this component):

| Field | Source |
|---|---|
| `signature` | `kms:Sign` over `canonical_bytes` |
| `kms_key_arn` | `orgs.kms_cmk_arn` for the tenant |
| `kms_key_version` | active version at signing time |
| `signature_alg` | `RSASSA_PSS_SHA_256` (CLAR-DEPLOY-04 baseline) |
| `claim_label` | derived per §5.5 |

A code-review check on any FND-03 patch: every new chain construction path imports `CPG_ORDER_HASH_ANNOTATION` and writes it adjacent to `cpg_order_hash` in both the DB row and the auditor export JSON.

---

## 9. Acceptance criteria cross-reference

| AC ID | Verbatim from `SDD.md §8 CMP-FND-03` | Test ID | Label | Notes |
|---|---|---|---|---|
| `AC-FND-03a` | "The record is independently verifiable from stored artifacts without re-running analysis." | `TST-AC-FND-03a` `[FORTHCOMING]` | `[INTEGRATION]` | Implements the `verify_chain` procedure of `DOC-PROVENANCE.md §8.4`; given a stored `provenance_records` row + S3 artefacts + KMS public key, returns `VERIFIED` for an untampered record and `TAMPERED(field)` for a mutated record. No IFDS / Algorithm 5 / detector invocations during verification. |
| `AC-FND-03b` | "The `cpg_order_hash` field carries its conditional-canonicality annotation in the auditor export (INV-5)." | `TST-AC-FND-03b` `[FORTHCOMING]` | `[INVARIANT]` | Asserts the auditor export JSON contains `cpg_order_hash_annotation` as a JSON-adjacent key with the literal string `"canonical iff fingerprint_class = strong"`. Greps export for any abbreviated/translated variant; fails on hit. |
| `AC-FND-03c` | "Differential-oracle re-partition events appear in the record." | `TST-AC-FND-03c` `[FORTHCOMING]` | `[INVARIANT]` | Seed a re-partition event via `CMP-SNAP-04`; assert a new `provenance_records` row exists with `record_kind = 'repartition'`, `parent_record_id` set to the base record, `origin = 'oracle-passthrough'`, and the auditor export's `repartition_history` array surfaces it. |
| `TST-INV-1-FND-03` | — (invariant test) | `TST-INV-1-FND-03` `[FORTHCOMING]` | `[INVARIANT]` | Every chained record has non-null `origin`; the parent is never mutated post-sign (append-only). |
| `TST-INV-2-FND-03` | — (invariant test) | `TST-INV-2-FND-03` `[FORTHCOMING]` | `[INVARIANT]` | Every chained record has non-null `S_version` and `env_digest`. |
| `TST-INV-5-FND-03` | — (invariant test) | `TST-INV-5-FND-03` `[FORTHCOMING]` | `[INVARIANT]` | The annotation literal is present in every chain record and every auditor export. |

Per `WBS.md §10 CMP-FND-03`: tasks are `T-CMP-FND-03-01` (construct chain), `T-CMP-FND-03-02` (sign), `T-CMP-FND-03-03` (stamp annotation in auditor export), `T-CMP-FND-03-04` (append re-partition events). Tests: `TST-AC-FND-03a`, `TST-AC-FND-03b`, `TST-AC-FND-03c`, `TST-INV-1-FND-03`, `TST-INV-5-FND-03`.

---

## 10. Open questions

- **`CLAR-DEPLOY-04` (RESOLVED).** AWS KMS envelope encryption, per-tenant CMKs, annual rotation, asymmetric signing. Decision record: `DOC-DEPLOY-DECISIONS.md`.
- **`CLAR-DEPLOY-15` (RESOLVED).** SARIF + provenance retention = 7 years under S3 Object Lock — Compliance mode.
- **`CLAR-DEPLOY-16` (RESOLVED).** Per-tenant isolation backstop = S3 prefix + RDS RLS + KMS per-tenant CMKs. The IAM role for `CMP-FND-03` is scoped to one CMK ARN per task; cross-tenant `kms:Sign` denied.
- **`CLAR-SLA-01` (RESOLVED).** Differential-oracle labelling-correction window = 24h high-impact / 7d routine. Published per environment in `DOC-RUNBOOK`.
- **`CLAR-FND-01` (FILED BY THIS DOCUMENT — see Appendix C).** `DOC-DB.md §4.13` and `DOC-PROVENANCE.md §3` describe two structurally different shapes for `provenance_records` (column-per-link vs. `chain_payload jsonb`; `record_kind` 2-enum vs. `record_type` 5-enum; `RSASSA_PSS_SHA_256` vs. `ecdsa-p256-sha256` baseline; `kms_key_arn + kms_key_version` vs. `signature_key_id + signature_algorithm + signature_value`). This document treats **`DOC-PROVENANCE.md §3` as the primary contract for `CMP-FND-03`** (it is the dedicated chain reference and aligns with the SDD chain shape); `DOC-DB.md §4.13` is treated as the persistence layer's reasonable rendering of the same conceptual shape into a SQL table. The DB-shape mismatch must be reconciled before migration delivery.

If an Implementation Agent encounters ambiguity not covered here (e.g. unspecified rendering of `repartition_history` in CSV vs. PDF exports), file `CLAR-FND-NN` in `WBS.md §17` per `.claude/rules/03-scope.md`. **Do not invent missing scope.**

---

## Appendix A. Signing-path sketch (informative)

```python
from analysis.ordering import CPG_ORDER_HASH_ANNOTATION

def sign_finding_record(finding_row, snapshot_row, sarif_hash, detector_manifest):
    record = ProvenanceRecord(
        # ... populate every field from finding_row + snapshot_row + detector_manifest;
        # cpg_order_hash_annotation MUST be CPG_ORDER_HASH_ANNOTATION (never a string literal);
        # parent_record_id=None for record_kind="finding"; sarif_hash from CMP-FND-01.
    )
    canonical = _canonical_serialize(record)                       # DOC-PROVENANCE §3.2
    cmk_arn   = _tenant_cmk_arn(finding_row.org_id)                # CLAR-DEPLOY-16
    kms_resp  = kms.sign(KeyId=cmk_arn, Message=canonical,
                         SigningAlgorithm="RSASSA_PSS_SHA_256")    # CLAR-DEPLOY-04
    signed = SignedProvenanceRecord(record, canonical, cmk_arn,
                                    kms_resp["KeyId"].split(":")[-1],
                                    kms_resp["Signature"], "RSASSA_PSS_SHA_256")
    _persist_to_db(signed)       # provenance_records table (append-only)
    _persist_to_s3(signed)       # Object Lock — Compliance, 7y per CLAR-DEPLOY-15
    return signed
```

Full field-by-field mapping in §3.1 + §8. The `append_repartition_event` path follows the same shape with `record_kind="repartition"`, `parent_record_id` set, `cpg_order_hash=None`, `origin="oracle-passthrough"`.

## Appendix B. CLAR-FND-01 (filed by this document)

**Filed in `WBS.md §17` as OPEN.** Brief: `DOC-DB.md §4.13` and `DOC-PROVENANCE.md §3` define the `provenance_records` table with structurally different shapes:

| Concern | `DOC-DB.md §4.13` | `DOC-PROVENANCE.md §3` |
|---|---|---|
| Layout | enum + opaque `chain_payload jsonb` | one column per chain link |
| Record-kind enum | `record_type IN ('chain','repartition','attestation','spec-acceptance','witness-update')` | `record_kind IN ('finding','repartition')` |
| Signing-algorithm baseline | `signature_algorithm IN ('ecdsa-p256-sha256','ecdsa-p384-sha384')` | `signature_alg = 'RSASSA_PSS_SHA_256'` |
| KMS key-id surface | `signature_key_id` | `kms_key_arn` + `kms_key_version` |

These differences imply different migration code, verification code, and KMS configuration. This document treats `DOC-PROVENANCE.md §3` as the primary contract for `CMP-FND-03` (aligns with SDD chain shape + `CLAR-DEPLOY-04` algorithm). `DOC-DB.md §4.13` must be reconciled before migration delivery. Architect Agent + CTO Agent ratification required.

**Auditor export sample shape.** See `DOC-PROVENANCE.md §8.1` for the full JSON shape and §5.3 of this document for the INV-5 adjacency rule.

---

## Appendix C. Cross-references

- `SDD.md §8 CMP-FND-03` — verbatim ACs and `Purpose:`.
- `WBS.md §10 CMP-FND-03` — task list (`T-CMP-FND-03-01..04`); `§15` invariant map; `§17` CLAR register; `§20` DAG.
- `DOC-PROVENANCE` — §3 (chain shape, primary contract for this component), §4 (re-partition events), §5 (honest-labelling), §6 (storage + retention), §7 (KMS), §8 (auditor export), §9 (test map), §10 (per-component threading).
- `DOC-DB` §4.13 (persistence rendering — see CLAR-FND-01), §4.15 (`repartition_events` trigger contract), §7 (retention).
- `DOC-INV` (INV-1, INV-2, INV-5 — this component is a co-owner of all three).
- `DOC-SARIF` §9 (auditor export adjacency), §10 (historical SARIF after re-partition).
- `DOC-DEPLOY-DECISIONS` (CLAR-DEPLOY-04 KMS, CLAR-DEPLOY-15 retention, CLAR-DEPLOY-16 isolation).
- `DOC-CMP-CORE-03` §5.1 (the `CPG_ORDER_HASH_ANNOTATION` constant).
- `DOC-CMP-FND-02` (the `findings` row this component reads).
- `DOC-CMP-SNAP-04` (re-partition event source — only caller of `append_repartition_event`).
- `.claude/rules/01-invariants.md` (INV-1, INV-2, INV-5).
- `.claude/rules/02-provenance.md` (provenance threading rules).
- `.claude/rules/05-determinism.md` (re-partition is monotonic toward oracle).
