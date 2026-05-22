# DOC-SARIF — SARIF emission contract

**Status:** ACTIVE (Phase 0 cross-cutting reference)
**Owner:** Documentation Manager Agent
**Source of truth:** `SDD.md` §8 (CMP-FND-01..03), §10 (CMP-CP-05). Where this document and the SDD disagree, the SDD wins.
**SARIF version pin:** **v2.1.0** (OASIS standard).

This document is the canonical contract for every SARIF log Scanipy v3.2 emits. Adherence is mandatory for any component that writes SARIF: `CMP-ORCH-03` (worker), `CMP-FND-01` (normalizer), `CMP-CP-05` (Attestor), and the SARIF export delivered by the Attestation API (`GET /api/v1/attestations/{scan_id}`).

Cross-cutting references this document depends on:

- `.claude/rules/00-global.md` — RULE-6 provenance threading.
- `.claude/rules/01-invariants.md` — INV-1 (origin), INV-2 (S_version, env_digest), INV-5 (cpg_order_hash + annotation).
- `.claude/rules/02-provenance.md` — required Finding fields.
- `.claude/rules/05-determinism.md` — `origin` semantics; two partitions.
- `docs/cross-cutting/DOC-API.md` — Finding shape; this document is the SARIF-mapped equivalent.
- `docs/cross-cutting/DOC-DB.md` — persisted shape; this document defines the wire representation.

---

## 1. Purpose

Every Scanipy emission of SARIF MUST:

1. Validate against the SARIF v2.1.0 JSON schema (OASIS).
2. Carry the Scanipy `properties` extension on every `Result` and every `Run`.
3. Serialize byte-identical given the same `(deterministic-core findings, S_version, env_digest, LLM_TRIAGE=off)`. This is the core invariant (INV-1) behind `CMP-CP-05`.
4. Distinguish the two partitions explicitly: `Run.properties.scanipy.partition ∈ {core, oracle}`.
5. Carry the conditional-canonicality annotation on `cpg_order_hash` everywhere it appears (INV-5).

---

## 2. SARIF version pin

- **Version:** SARIF v2.1.0.
- **Schema URI:** `https://json.schemastore.org/sarif-2.1.0.json` (canonical OASIS mirror).
- **`$schema` and `version` fields:**

```json
{
  "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
  "version": "2.1.0",
  "runs": [ /* see §5 and §6 */ ]
}
```

---

## 3. Reproducible JSON serialization (INV-1 core guarantee)

The core-partition SARIF MUST serialize **byte-identical** across re-runs under fixed `(S_version, env_digest, LLM_TRIAGE=off)`. The deterministic-serialization rules (all hard requirements; CI gate AC-CP-05c):

1. **Key ordering:** every JSON object's keys are emitted in **lexicographic (Unicode code-point) ascending order**. No exceptions, no per-object exception lists.
2. **Whitespace:** no leading or trailing whitespace; no whitespace between tokens. Emit minified JSON (no pretty-print).
3. **Line endings:** the entire log is a single line of UTF-8 followed by a single LF (`\n`). No CR. No BOM.
4. **Encoding:** UTF-8 (no BOM). Non-ASCII characters in `message.text` are emitted as their literal UTF-8 bytes, NOT escaped (e.g. `é` stays `é`, not `é`).
5. **Number formatting:** integers as base-10 with no leading zero, no leading `+`; floats use the shortest round-trip decimal representation (Ryū / Grisu equivalent).
6. **Booleans / null:** `true`, `false`, `null` literally.
7. **No trailing comma anywhere.**
8. **No JSON5, no extensions beyond the SARIF schema.**
9. **Result ordering** (see §7) is part of byte-identity.

If the implementation language's JSON library does not provide guaranteed key ordering, the emitter MUST sort keys explicitly before serialization.

Implementation note: the canonical serializer is `analysis/sarif/canonical_emit.py` (CMP-FND-01); its contract is enforced by `TST-INV-1-FND-01` which asserts byte-identical output across two runs with the same inputs.

The oracle-partition SARIF aims for digest-stability + a measured reproduction rate; the byte-identical guarantee is core-only (`.claude/rules/05-determinism.md`).

---

## 4. The two SARIF flavors (normative choice)

The platform emits **two `Run` objects within a single SARIF log per scan**:

- `runs[0]` — the core partition (`Run.properties.scanipy.partition = "core"`); contains every `Result` with `origin = "deterministic-core"`.
- `runs[1]` — the oracle partition (`Run.properties.scanipy.partition = "oracle"`); contains every `Result` with `origin = "oracle-passthrough"`.

Each `Run` is independently canonical and independently attested (CMP-CP-05 two pipelines). The Attestor distinguishes them by the `Run.properties.scanipy.partition` value; the core pipeline asserts byte-identity over `runs[0]`; the oracle pipeline asserts digest-stability + reproduction rate over `runs[1]`.

**Permitted alternate:** an emitter MAY also write the two partitions as **two separate SARIF files** (`*-core.sarif`, `*-oracle.sarif`) when a downstream consumer requires it (e.g. customer SARIF download). When this alternate is used, every requirement in this document applies independently to each file.

The "single SARIF log with two runs" model is the **normative wire representation** for internal pipelines (Attestor, attestation export endpoint, customer dashboard). The split-file representation is opt-in per customer integration.

---

## 5. Run-level schema

Every `Run` carries the following `properties` extension (Scanipy-specific):

```json
{
  "tool": {
    "driver": {
      "name": "scanipy",
      "version": "3.2.0",
      "informationUri": "https://scanipy.io",
      "rules": [ /* tool.driver.rules array, one per registered detector */ ]
    }
  },
  "invocations": [
    {
      "executionSuccessful": true,
      "startTimeUtc": "2026-05-23T12:00:00Z",
      "endTimeUtc": "2026-05-23T12:08:14Z"
    }
  ],
  "properties": {
    "scanipy.partition": "core",
    "scanipy.scan_id": "uuid",
    "scanipy.snapshot_id": "uuid",
    "scanipy.codebase_id": "uuid",
    "scanipy.commit_sha": "string (40 hex)",
    "scanipy.S_version": "1.4.0",
    "scanipy.env_digest": "sha256:…",
    "scanipy.attestor_hash": "sha256:…",
    "scanipy.precondition_status": "closed-world | degraded | full-reparse",
    "scanipy.llm_triage_flag": false
  },
  "results": [ /* see §6 and §7 */ ]
}
```

Mandatory non-null on every `Run.properties`: `scanipy.partition`, `scanipy.scan_id`, `scanipy.snapshot_id`, `scanipy.codebase_id`, `scanipy.commit_sha`, `scanipy.S_version`, `scanipy.env_digest`, `scanipy.precondition_status`, `scanipy.llm_triage_flag`.

`scanipy.attestor_hash` is populated by the Attestor (CMP-CP-05) and is null until attestation completes.

`scanipy.llm_triage_flag = true` MUST disqualify the run from core-pipeline byte-identity assertion (`CMP-CP-05` always runs with `LLM_TRIAGE=off` per AC-CP-05c).

---

## 6. Result-level schema

Every `Result` carries the Scanipy `properties` extension on top of the SARIF v2.1.0 standard fields:

```json
{
  "ruleId": "scanipy/path-traversal/extract-all-archive",
  "level": "error",
  "message": { "text": "Untrusted archive extraction without path containment." },
  "locations": [
    {
      "physicalLocation": {
        "artifactLocation": { "uri": "src/extract.py" },
        "region": { "startLine": 42, "startColumn": 13, "endLine": 42, "endColumn": 27 }
      }
    }
  ],
  "fingerprints": {
    "scanipy.slice_fingerprint/v1": "sha256-hex…",
    "scanipy.cpg_order_hash/v1": "sha256-hex…"
  },
  "properties": {
    "scanipy.origin": "deterministic-core",
    "scanipy.S_version": "1.4.0",
    "scanipy.env_digest": "sha256:…",
    "scanipy.cpg_order_hash": "sha256-hex…",
    "scanipy.cpg_order_hash_annotation": "canonical iff fingerprint_class = strong",
    "scanipy.fingerprint_class": "strong",
    "scanipy.slice_fingerprint": "sha256-hex…",
    "scanipy.determinism_partition": "deterministic-core",
    "scanipy.engine": "ifds",
    "scanipy.spec_provenance": "global-revalidated",
    "scanipy.precondition_status": "closed-world",
    "scanipy.witness_blob_uri": "s3://…",
    "scanipy.class": "path-traversal",
    "scanipy.severity": "high",
    "scanipy.status": "open"
  }
}
```

Mandatory non-null on every `Result.properties` (this is the RULE-6 + INV-1/INV-2/INV-5 discharge on the wire):

- `scanipy.origin` ∈ `{deterministic-core, oracle-passthrough}` — INV-1.
- `scanipy.S_version` (semver string) — INV-2.
- `scanipy.env_digest` (sha256 hex) — INV-2.
- `scanipy.cpg_order_hash` (sha256 hex) — INV-5.
- `scanipy.cpg_order_hash_annotation` — literal string `"canonical iff fingerprint_class = strong"`. INV-5. The annotation MUST be the exact string. Emitters MAY NOT collapse, abbreviate, or i18n-translate the annotation.
- `scanipy.fingerprint_class` ∈ `{strong, weak}`.
- `scanipy.slice_fingerprint` (sha256 hex).
- `scanipy.determinism_partition` ∈ `{deterministic-core, oracle-passthrough}` (always equal to `scanipy.origin` at emission time; may diverge in historical SARIF after a CMP-SNAP-04 re-partition — see §10).
- `scanipy.engine` ∈ `{ifds, ide, semgrep, cpg-query, external}`.
- `scanipy.precondition_status` ∈ `{closed-world, degraded, full-reparse}`.
- `scanipy.class` (from the allowed list in `DOC-DB.md` §6).
- `scanipy.severity` ∈ `{info, low, medium, high, critical}`.
- `scanipy.status` ∈ `{open, suppressed, fixed}`.

Nullable (may be omitted):

- `scanipy.spec_provenance` — null when the finding does not depend on a revalidatable spec.
- `scanipy.witness_blob_uri` — oracle findings may omit; core findings MUST have a witness (it is the slice).
- `scanipy.triage_score`, `scanipy.triage_reason` — null when `LLM_TRIAGE=off`. When present, these are read from the `triage_scores` table (DOC-DB §4.14), never from the LLM at SARIF-emit time (INV-3).

### 6.1 The `fingerprints` block (SARIF native)

SARIF v2.1.0 provides a native `fingerprints` map; Scanipy uses it for **the two refactor-stable identifiers**: `slice_fingerprint` and `cpg_order_hash`. The native fields enable downstream SARIF tools (GitHub code-scanning, etc.) to correlate findings across runs without parsing the Scanipy `properties` extension.

Conventions:

- Keys are versioned: `scanipy.slice_fingerprint/v1`, `scanipy.cpg_order_hash/v1`.
- Values are hex-encoded sha256 (64 chars).
- Both fingerprints also appear in `properties` for completeness; tools that respect the SARIF native fingerprints get them automatically.

### 6.2 Rule reference

`ruleId` is the canonical Scanipy detector ID, namespaced as `scanipy/<class>/<rule-slug>`. The `tool.driver.rules` array of the same `Run` MUST contain a definition for every rule referenced by results in that run.

---

## 7. Canonical ordering (byte-identity)

Within each `Run.results` array, results MUST be sorted by the following key tuple (lexicographic, ascending):

1. `properties["scanipy.cpg_order_hash"]` (sha256 hex).
2. `ruleId`.
3. `locations[0].physicalLocation.artifactLocation.uri`.
4. `locations[0].physicalLocation.region.startLine` (integer ascending).

The ordering is computed before serialization; the serializer never reorders. Two emissions that disagree on ordering are not byte-identical and so a core-partition emission disagreement is a `CMP-CP-05` fail (AC-CP-05a).

Implementation note: the canonical order over results corresponds 1:1 with the canonical CPG order produced by `CMP-CORE-03` (Algorithm 5). The `cpg_order_hash` sort key is the bridge between graph-canonical ordering and SARIF-canonical ordering.

---

## 8. Examples

**Reading-order note.** The JSON blocks in §8.1 and §8.2 are presented in **reading order** for documentation clarity, NOT in the canonical lexicographic key order required at emission time. Implementers MUST NOT copy these literals into a serializer; the canonical emitter (`analysis/sarif/canonical_emit.py`, CMP-FND-01) sorts every object's keys lexicographically by Unicode code point per §3 before writing bytes. Notably, uppercase `S` (U+0053) precedes every lowercase letter, so `scanipy.S_version` sorts first among `scanipy.*` keys; the `properties` block below shows the keys in alphabetic reading order so a human eye can scan them, not the byte order produced on the wire.

### 8.1 A core-partition result (reading order; canonical emission sorts keys per §3)

```json
{
  "ruleId": "scanipy/path-traversal/extract-all-archive",
  "level": "error",
  "message": { "text": "Untrusted archive extraction without path containment." },
  "locations": [
    {
      "physicalLocation": {
        "artifactLocation": { "uri": "src/extract.py" },
        "region": { "endColumn": 27, "endLine": 42, "startColumn": 13, "startLine": 42 }
      }
    }
  ],
  "fingerprints": {
    "scanipy.cpg_order_hash/v1": "a3f9...64chars",
    "scanipy.slice_fingerprint/v1": "1b22...64chars"
  },
  "properties": {
    "scanipy.class": "path-traversal",
    "scanipy.cpg_order_hash": "a3f9...64chars",
    "scanipy.cpg_order_hash_annotation": "canonical iff fingerprint_class = strong",
    "scanipy.determinism_partition": "deterministic-core",
    "scanipy.engine": "ifds",
    "scanipy.env_digest": "sha256:7e4b...64chars",
    "scanipy.fingerprint_class": "strong",
    "scanipy.origin": "deterministic-core",
    "scanipy.precondition_status": "closed-world",
    "scanipy.severity": "high",
    "scanipy.slice_fingerprint": "1b22...64chars",
    "scanipy.spec_provenance": "global-revalidated",
    "scanipy.status": "open",
    "scanipy.S_version": "1.4.0",
    "scanipy.witness_blob_uri": "s3://scanipy-witness/orgs/.../witness.json.zst"
  }
}
```

### 8.2 An oracle-partition result (reading order; canonical emission sorts keys per §3)

```json
{
  "ruleId": "scanipy/secrets/aws-access-key",
  "level": "warning",
  "message": { "text": "Detected AWS access key pattern." },
  "locations": [
    {
      "physicalLocation": {
        "artifactLocation": { "uri": "config/dev.env" },
        "region": { "endColumn": 80, "endLine": 14, "startColumn": 1, "startLine": 14 }
      }
    }
  ],
  "fingerprints": {
    "scanipy.cpg_order_hash/v1": "0000...64chars",
    "scanipy.slice_fingerprint/v1": "cd11...64chars"
  },
  "properties": {
    "scanipy.class": "secrets",
    "scanipy.cpg_order_hash": "0000...64chars",
    "scanipy.cpg_order_hash_annotation": "canonical iff fingerprint_class = strong",
    "scanipy.determinism_partition": "oracle-passthrough",
    "scanipy.engine": "semgrep",
    "scanipy.env_digest": "sha256:7e4b...64chars",
    "scanipy.fingerprint_class": "weak",
    "scanipy.origin": "oracle-passthrough",
    "scanipy.precondition_status": "closed-world",
    "scanipy.severity": "medium",
    "scanipy.slice_fingerprint": "cd11...64chars",
    "scanipy.status": "open",
    "scanipy.S_version": "1.4.0"
  }
}
```

Notes:

- `witness_blob_uri` is omitted (allowed for oracle findings).
- `spec_provenance` is omitted (the secret detector is not customer-revalidatable in v3.2).
- `cpg_order_hash` is still populated (Algorithm 5 produces a deterministic same-source hash even on the `weak` path; the conditional annotation is precisely there to tell consumers that canonicality holds only on `strong`).

---

## 9. Auditor export (CMP-FND-03 signed chain)

The Attestation export endpoint (`GET /api/v1/attestations/{scan_id}`, see `DOC-API.md §4.7`) returns the SARIF log alongside the signed provenance chain. The export carries:

- The two-run SARIF log (§4) verbatim, in its canonical serialization.
- The signed chain (`provenance_records` row contents) — see `DOC-PROVENANCE.md`.
- The `cpg_order_hash` conditional-canonicality annotation MUST appear in both the SARIF `Result.properties` AND the signed-chain payload (INV-5; AC-FND-03b).

The export's SARIF blob hash MUST match the `attestor_hash` recorded on the corresponding `attestations` row (`DOC-DB.md §4.10`); a mismatch raises `error_code = invariant_inv5_violation` per `DOC-API.md §6.1`.

---

## 10. Historical SARIF after CMP-SNAP-04 re-partition

When `CMP-SNAP-04` flips a finding from `deterministic-core` to `oracle-passthrough` (an oracle-disagreement event):

- The new authoritative `findings` row has `origin = "oracle-passthrough"`.
- **Previously emitted** SARIF files (in S3) are NOT rewritten — they retain their historical record.
- A new SARIF emission for a subsequent scan reflects the new partition.
- The `repartition_events` row (`DOC-DB.md §4.15`) is the bridge that documents the divergence.
- The Attestation export for a scan retrieved AFTER a re-partition event includes both:
  - the original SARIF (with `origin = "deterministic-core"` on the affected results), and
  - the `repartition_events` payload showing the flip.

This is by design — auditability requires the historical record to be immutable; the new authoritative state lives in the DB row and the next scan's SARIF.

---

## 11. JSON Schema for the Scanipy `properties` extension

A standalone JSON Schema (Draft 2020-12) validates the `scanipy.*` keys on every Run and Result. The schema is checked in CI on every emitted SARIF blob (CMP-CI-01).

**Schema URI:** `https://schemas.scanipy.io/sarif-extension/v1.0.0.json` — proposed; **filed as `CLAR-SARIF-01`** (see §13) because the hosting URL is not pinned anywhere upstream.

Pseudocode of the schema's top-level shape:

```yaml
$schema: https://json-schema.org/draft/2020-12/schema
$id: https://schemas.scanipy.io/sarif-extension/v1.0.0.json
title: Scanipy SARIF extension v1
$defs:
  RunProperties:
    type: object
    required:
      - scanipy.partition
      - scanipy.scan_id
      - scanipy.snapshot_id
      - scanipy.codebase_id
      - scanipy.commit_sha
      - scanipy.S_version
      - scanipy.env_digest
      - scanipy.precondition_status
      - scanipy.llm_triage_flag
    properties:
      scanipy.partition: { enum: [core, oracle] }
      scanipy.scan_id: { type: string, format: uuid }
      # ...
  ResultProperties:
    type: object
    required:
      - scanipy.origin
      - scanipy.S_version
      - scanipy.env_digest
      - scanipy.cpg_order_hash
      - scanipy.cpg_order_hash_annotation
      - scanipy.fingerprint_class
      - scanipy.slice_fingerprint
      - scanipy.determinism_partition
      - scanipy.engine
      - scanipy.precondition_status
      - scanipy.class
      - scanipy.severity
      - scanipy.status
    properties:
      scanipy.origin: { enum: [deterministic-core, oracle-passthrough] }
      scanipy.cpg_order_hash_annotation: { const: "canonical iff fingerprint_class = strong" }
      # ...
```

The `const` constraint on `cpg_order_hash_annotation` enforces INV-5 at the schema layer: an emission that elides or alters the annotation fails JSON Schema validation in CI.

---

## 12. CI validation

CMP-CI-01 runs the following gates on every emitted SARIF blob (corpus + canary + every PR):

1. **SARIF v2.1.0 schema validation** against the OASIS schema (hard fail).
2. **Scanipy extension validation** against the JSON Schema in §11 (hard fail).
3. **Byte-identical assertion** on the canonical-core run across two independent runs under fixed `(S_version, env_digest, LLM_TRIAGE=off)` (hard fail; AC-CP-05a).
4. **Canonical ordering check** — results sorted per §7 (hard fail).
5. **Annotation-presence check** — every Result has the literal `cpg_order_hash_annotation` string (hard fail; INV-5).

Failures of any gate above are blocking for merge / promotion.

---

## 13. References and CLARs

### 13.1 References

- `SDD.md` §8 (CMP-FND-01..03), §10 (CMP-CP-05).
- `DOC-DEPLOY-DECISIONS.md` CLAR-DEPLOY-15 (retention).
- `DOC-API.md` §4.7, §5.
- `DOC-DB.md` §4.12 (findings), §4.13 (provenance_records).
- `.claude/rules/00-global.md` RULE-6.
- `.claude/rules/01-invariants.md` INV-1, INV-2, INV-5.
- `.claude/rules/02-provenance.md`.
- `.claude/rules/05-determinism.md`.
- OASIS SARIF v2.1.0 specification.

### 13.2 CLARIFICATION items filed by this document

(Mirrored in `WBS.md §17`.)

- **CLAR-SARIF-01** — Hosting URL for the JSON Schema (`https://schemas.scanipy.io/sarif-extension/v1.0.0.json` proposed). Blocks: CMP-CI-01 schema gate (the schema can be vendored locally meanwhile). Target: before first customer SARIF export GA.

---

*Cross-reference: `SDD.md` §8 (CMP-FND-01..03), `DOC-API.md`, `DOC-DB.md`, `.claude/rules/01-invariants.md` (INV-1, INV-2, INV-5), `.claude/rules/02-provenance.md`, `.claude/rules/05-determinism.md`.*
