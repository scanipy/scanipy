# DOC-CMP-CP-02 — Credential encryption service

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `SDD.md §10 CMP-CP-02` (Purpose, AC-CP-02a)
- `PLAN.md §"Phase 6 — Multi-tenant control plane"` (scm_credentials encrypted at rest)
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` (CLAR-DEPLOY-04 KMS envelope encryption, per-tenant CMK, annual rotation; CLAR-DEPLOY-16 layered isolation)
- `docs/cross-cutting/DOC-DB.md §4.5` (`scm_credentials` schema), §4.1 (`orgs.kms_cmk_arn`)
- `docs/cross-cutting/DOC-PROVENANCE.md §7` (signing keys also managed via KMS)
- `docs/cross-cutting/DOC-INV.md §5` (INV-3 ancillary surface)
- `.claude/rules/00-global.md`, `.claude/rules/02-provenance.md`

This document is the **implementation contract** for `CMP-CP-02`. A code-writing agent given only this file plus the cross-cutting refs listed above must be able to produce a passing implementation without re-reading `SDD.md` (per `AC-DOC-04`).

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-CP-02` |
| Subsystem | Control Plane & Attestation (`SDD.md §10`) |
| Staging | cross-cutting |
| Depends-On | none (`WBS.md §20`) |
| Owner | **DEFERRED** via `CLAR-OWNER-01` (`WBS.md §17`) |
| INV-* touched | **INV-3** (ancillary): encrypted SCM credentials cannot be exfiltrated via the LLM-triage surface even if INV-3's direct discharge mechanisms (`CMP-TRI-01..03` write-fence) failed. **Security Analyst sign-off required** under RULE-9 because CP-02 touches credential material. |

---

## 2. Mandate

**Verbatim SDD `Purpose:` (`SDD.md §10 CMP-CP-02`):**

> Encrypt `scm_credentials` at rest; provide the key service CMP-SCM-01 depends on.

**Operational role.** `CMP-CP-02` is the **credential encryption service** for Scanipy v3.2. It is a thin Python module that wraps a boto3 KMS client and provides three operations to the rest of the platform: `encrypt_credential`, `decrypt_credential`, and `rotate_cmk`. Every SCM credential bytes-in/bytes-out passes through this module. Per CLAR-DEPLOY-04 (RESOLVED), the substrate is **AWS KMS envelope encryption**: a per-tenant Customer-Managed Key (CMK) wraps a per-credential data key; the data key encrypts the plaintext. **Annual rotation is performed automatically by AWS KMS**; CP-02 exposes `rotate_cmk(org_id)` only for the *forced* rotation case (suspected compromise, scheduled audit response). Data keys are cached in worker memory for the lifetime of a single scan (CLAR-DEPLOY-04 rationale).

CP-02 is also the key-handle provider for `CMP-FND-03` (signed provenance): the same KMS substrate signs provenance records using KMS asymmetric keys (`DOC-PROVENANCE §7`). CP-02 owns the IAM scoping and the KMS client lifecycle; `CMP-FND-03` consumes signing handles via the same module.

---

## 3. Interface contract

### 3.1 Public API

```python
class CredentialEncryptionService:
    def encrypt_credential(
        self,
        plaintext: bytes,
        org_id: UUID,
    ) -> EncryptedCredential: ...

    def decrypt_credential(
        self,
        ciphertext: EncryptedCredential,
        org_id: UUID,
    ) -> bytes: ...

    def rotate_cmk(
        self,
        org_id: UUID,
        reason: Literal["scheduled", "forced-compromise", "scheduled-audit"],
    ) -> None: ...

    def get_signing_key_handle(
        self,
        org_id: UUID,
        purpose: Literal["provenance-signing"],
    ) -> SigningKeyHandle: ...
```

All four operations are **per-tenant scoped**: the caller's `org_id` MUST be the `request.state.jwt_claims.org_id` set by `CMP-CP-01`. CP-02 does not derive `org_id` itself; it is always provided by the caller, which CP-01 has already authenticated.

```python
@dataclass(frozen=True)
class EncryptedCredential:
    ciphertext_blob: bytes          # opaque KMS envelope-encrypted blob (CiphertextBlob from kms:Encrypt)
    kms_key_arn: str                # arn:aws:kms:<region>:<acct>:key/<uuid>  (the tenant CMK)
    encryption_algorithm: str       # KMS spec; default "SYMMETRIC_DEFAULT"
    encryption_context: dict[str, str]
                                    # MUST include {"org_id": "<uuid>", "purpose": "scm-credential"}
    display_fingerprint: str        # sha256 of plaintext, hex; display-only; never used for crypto
    created_at: datetime            # iso-8601 utc

@dataclass(frozen=True)
class SigningKeyHandle:
    kms_key_arn: str                # asymmetric KMS key (ECDSA P-256, P-384 — see DOC-PROVENANCE §7.3)
    signing_algorithm: Literal["ECDSA_SHA_256", "ECDSA_SHA_384"]
    purpose: Literal["provenance-signing"]
```

### 3.2 Encryption contract (`encrypt_credential`)

```python
def encrypt_credential(plaintext, org_id):
    # 1. Look up the tenant CMK ARN from orgs.kms_cmk_arn (DOC-DB §4.1).
    cmk_arn = sql.scalar("SELECT kms_cmk_arn FROM orgs WHERE id = :id", id=org_id)
    if cmk_arn is None:
        # First-time credential write for this tenant — provision the CMK now.
        cmk_arn = self._provision_cmk(org_id, purpose="credential")
        sql.execute("UPDATE orgs SET kms_cmk_arn = :arn WHERE id = :id",
                    arn=cmk_arn, id=org_id)
    # 2. Call KMS:Encrypt with explicit EncryptionContext (org_id binding).
    resp = self._kms.encrypt(
        KeyId=cmk_arn,
        Plaintext=plaintext,
        EncryptionContext={"org_id": str(org_id), "purpose": "scm-credential"},
    )
    # 3. Compute the display fingerprint (no crypto significance).
    display_fp = sha256(plaintext).hexdigest()
    return EncryptedCredential(
        ciphertext_blob=resp["CiphertextBlob"],
        kms_key_arn=cmk_arn,
        encryption_algorithm=resp.get("EncryptionAlgorithm", "SYMMETRIC_DEFAULT"),
        encryption_context={"org_id": str(org_id), "purpose": "scm-credential"},
        display_fingerprint=display_fp,
        created_at=utcnow(),
    )
```

**Encryption-context binding (CRITICAL).** Every call MUST include `{"org_id": "<uuid>", "purpose": "scm-credential"}` (or `"purpose": "provenance-signing"` for signing-key issuance) in `EncryptionContext`. KMS authenticates this context: a `Decrypt` call with a different context fails with `InvalidCiphertextException`. This is the mechanism that prevents a ciphertext for org A from being decrypted under the same CMK as if it were org B's — the CMK ARN, plus the encryption context, jointly identify the tenant.

### 3.3 Decryption contract (`decrypt_credential`)

```python
def decrypt_credential(ciphertext, org_id):
    # 0. The caller MUST present org_id equal to the JWT-derived org_id (CMP-CP-01).
    #    Cross-tenant decryption is rejected at the KMS layer via EncryptionContext mismatch.
    # 1. Pull the data key by calling KMS:Decrypt.
    resp = self._kms.decrypt(
        CiphertextBlob=ciphertext.ciphertext_blob,
        KeyId=ciphertext.kms_key_arn,
        EncryptionContext={"org_id": str(org_id), "purpose": "scm-credential"},
    )
    # 2. Return plaintext bytes. Caller is responsible for clearing them after use.
    return resp["Plaintext"]
```

**Caching contract (CLAR-DEPLOY-04 rationale).** Plaintext bytes returned from `decrypt_credential` MAY be held in worker memory **for the lifetime of a single scan** and MUST be discarded at scan completion. They MUST NOT be persisted to disk, logged, exported to OTel attributes, or passed to any LLM call.

### 3.4 Rotation contract (`rotate_cmk`)

KMS handles **annual rotation automatically** (CLAR-DEPLOY-04). The application `rotate_cmk(org_id, reason)` method handles only **forced** rotation:

```python
def rotate_cmk(org_id, reason):
    cmk_arn = sql.scalar("SELECT kms_cmk_arn FROM orgs WHERE id = :id", id=org_id)
    # Force a new key-material version. AWS KMS preserves all prior key versions;
    # existing ciphertexts remain decryptable (the wrapping key version is embedded
    # in the CiphertextBlob).
    self._kms.rotate_key_on_demand(KeyId=cmk_arn)
    # Log the rotation event to provenance via CMP-FND-03's audit trail; no findings
    # are mutated by rotation (key versions are addressable inside CiphertextBlob).
    audit_log.write({
        "event": "cmk_rotated",
        "org_id": str(org_id),
        "kms_key_arn": cmk_arn,
        "reason": reason,
        "rotated_at": utcnow().isoformat(),
    })
```

**Why ciphertexts survive rotation (per `DOC-PROVENANCE §7.1`).** Envelope encryption stores the wrapping-key version inside the `CiphertextBlob`. KMS resolves the version at decrypt time and uses the corresponding historical key material. No ciphertext re-encryption is required at rotation.

### 3.5 Signing-key issuance (`get_signing_key_handle`)

```python
def get_signing_key_handle(org_id, purpose):
    assert purpose == "provenance-signing"
    # Asymmetric KMS keys per tenant; created lazily on first use.
    arn = sql.scalar("SELECT kms_signing_key_arn FROM orgs WHERE id = :id", id=org_id)
    if arn is None:
        arn = self._provision_signing_key(org_id)
        sql.execute("UPDATE orgs SET kms_signing_key_arn = :arn WHERE id = :id",
                    arn=arn, id=org_id)
    return SigningKeyHandle(
        kms_key_arn=arn,
        signing_algorithm="ECDSA_SHA_256",     # per DOC-PROVENANCE §7.3
        purpose=purpose,
    )
```

`CMP-FND-03` consumes this handle to sign provenance records (see `DOC-PROVENANCE §7`).

### 3.6 IAM scope (CLAR-DEPLOY-16 layer 3)

The CP-02 module runs under an IAM role with:

- `kms:Encrypt`, `kms:Decrypt`, `kms:GenerateDataKey`, `kms:RotateKeyOnDemand` scoped via a condition that constrains the `aws:RequestTag/org_id` to the calling session's tag.
- `kms:CreateKey`, `kms:CreateAlias` permitted only via the tenant-creation workflow (separate IAM role; not the request-path role).

This is layer-3 of CLAR-DEPLOY-16 (KMS per-tenant data keys). Combined with CP-01's session-variable enforcement (layer 2) and S3 prefix isolation (layer 1), cross-tenant credential decryption requires breaking **all three** layers — a single application bug is insufficient.

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| `plaintext: bytes` | Caller (`CMP-SCM-01..03` at registration; `CMP-SNAP-05` at worker decrypt) | UTF-8 or raw; CP-02 is bytes-agnostic. |
| `org_id: UUID` | Caller (sourced from `CMP-CP-01`'s `request.state.jwt_claims`) | Used as the encryption-context anchor and the row-key for `orgs.kms_cmk_arn`. |
| `EncryptedCredential` (on decrypt) | Persistence layer; row from `scm_credentials` (`DOC-DB §4.5`) | `ciphertext_blob`, `kms_key_arn`, `encryption_context` round-trip exactly. |
| Tenant CMK ARN | `orgs.kms_cmk_arn` (`DOC-DB §4.1`) | Created lazily on first credential write; one CMK per tenant per purpose. |

### 4.2 Outputs / Persisted state

| Output | Persisted to | Contract |
|---|---|---|
| `EncryptedCredential` row | `scm_credentials` table (`DOC-DB §4.5`) | Caller (`CMP-SCM-01`) INSERTs the row using values from the returned `EncryptedCredential`. CP-02 does not write the table itself. |
| `orgs.kms_cmk_arn`, `orgs.kms_signing_key_arn` | `orgs` table (`DOC-DB §4.1`) | Written by CP-02 on lazy CMK provisioning under the control-plane internal IAM role. |
| Audit-log event on rotation | OpenTelemetry → CloudWatch Logs (`CLAR-DEPLOY-07`) | One event per `rotate_cmk` call; includes `org_id`, `kms_key_arn`, `reason`. |
| `SigningKeyHandle` | Returned to `CMP-FND-03` | Used to invoke `kms:Sign` against provenance records. |

### 4.3 Plaintext lifecycle

| Stage | Allowed | Notes |
|---|---|---|
| In memory during a scan | yes | Returned by `decrypt_credential`; held only for the scan's lifetime. |
| Logged | **never** | No INFO/DEBUG/WARN/ERROR log line may contain plaintext. The `display_fingerprint` (sha256 hex) is the only safe identifier. |
| Persisted to disk | **never** | Worker filesystem MUST be tmpfs / overlayfs-only for the scan working directory; plaintext credentials never flush. |
| Exported to OTel span attributes | **never** | Span attributes may include `org_id`, `kms_key_arn`, `display_fingerprint` only. |
| Passed to LLM call | **never** (INV-3 ancillary) | Triage and spec-inference paths never invoke `decrypt_credential`. The triage role's IAM denies `kms:Decrypt` against any credential-purpose CMK. |

---

## 5. Invariants touched

| Invariant | How `CMP-CP-02` discharges it | Test |
|---|---|---|
| **INV-3** (ancillary) | The LLM-triage role (`CMP-TRI-01`) has no `kms:Decrypt` grant against any `purpose=scm-credential` CMK. Combined with the schema-level INV-3 enforcement (`DOC-DB §4.14`: triage role has `INSERT ON triage_scores` only, no SELECT on `findings.*`), this means credentials cannot leak via the LLM surface even if a triage prompt is malicious. | `TST-INV-3-CP-02 [FORTHCOMING]` — IAM-policy assertion test. |
| **CLAR-DEPLOY-16 layer 3** | Per-tenant CMK with mandatory `org_id` `EncryptionContext` makes cross-tenant decryption impossible without breaking the KMS-layer authorization. Combined with CP-01 (layer 2) and S3 prefix isolation (layer 1), three independent backstops protect every credential. | `TST-AC-CP-02a [FORTHCOMING]` (negative test: decryption with wrong `org_id` in context fails). |
| **CLAR-DEPLOY-04 contract** | Per-tenant CMK exists; annual auto-rotation enabled; forced rotation via `rotate_cmk` works without re-encrypting ciphertexts. | `TST-AC-CP-02a [FORTHCOMING]` (rotation supported). |

See `DOC-INV.md §5` for INV-3 verbatim; do not paraphrase here.

---

## 6. Algorithm / data flow

```
caller (CMP-SCM-01 register-credentials / CMP-SNAP-05 worker-decrypt)
    | provides (plaintext or ciphertext, org_id)
    v
CP-02.encrypt_credential / decrypt_credential
    | 1. Look up orgs.kms_cmk_arn for org_id (lazy-provision on first encrypt).
    | 2. Build EncryptionContext = {org_id, purpose}.
    | 3. boto3 kms.encrypt() / kms.decrypt() with KeyId + EncryptionContext.
    | 4. On encrypt: compute display_fingerprint = sha256(plaintext).hex.
    v
KMS (AWS-managed; envelope encryption; annual auto-rotation)
    | returns CiphertextBlob (encrypt) / Plaintext (decrypt)
    v
CP-02 returns
    | encrypt -> EncryptedCredential dataclass (caller INSERTs into scm_credentials)
    | decrypt -> bytes (caller uses transiently; clears at scan end)

CP-02.rotate_cmk(org_id, reason)
    | kms.rotate_key_on_demand(KeyId=cmk_arn)
    | audit_log.write(event="cmk_rotated", reason=reason, ...)
    | NO ciphertext re-encryption; key version embedded in CiphertextBlob.

CP-02.get_signing_key_handle(org_id, purpose="provenance-signing")
    | lazy-provisions an asymmetric ECDSA key the first time;
    | returns SigningKeyHandle for CMP-FND-03 to invoke kms.Sign().
```

---

## 7. Failure modes and error contracts

| Failure | Detected by | Response | Side effect |
|---|---|---|---|
| KMS API rate limit (`ThrottlingException`) | boto3 KMS call | Retry with exponential backoff (3 attempts, jitter); after exhaustion → `503 KMS_UNAVAILABLE`. | CloudWatch alarm on sustained throttling. |
| Tenant CMK missing on decrypt | KMS `NotFoundException` or our pre-lookup | **Surface the error; never auto-create.** A missing CMK means it was deleted (deliberate or accident) — auto-creating would silently re-create the tenant key under a new ARN and orphan all existing ciphertexts. Return `500 KMS_KEY_MISSING` with a runbook reference. | Page SRE; this is a tenant-impact event. |
| `EncryptionContext` mismatch on decrypt (cross-tenant attempt) | KMS `InvalidCiphertextException` | `403 tenant_isolation_violation`. | WARN OTel event with `{requested_org_id, ciphertext_kms_arn, route}`. |
| CMK rotation fails partway | boto3 KMS call | Retry with backoff; never leave the CMK in an inconsistent state — KMS rotation is atomic on the KMS side, so a failed call means the rotation simply did not happen and ciphertexts remain readable under the prior key. | Log the rotation attempt; alarm on persistent failure. |
| Decryption succeeds but plaintext logged | (would-be programming bug) | Compile-time / lint-time enforcement: no log statement in CP-02 or downstream services may interpolate the return value of `decrypt_credential`. | Pre-commit hook + code review (RULE-9 Security Analyst sign-off). |
| KMS region outage | boto3 KMS call (timeout) | `503 KMS_UNAVAILABLE`; fail closed. | Page SRE. |

**Fail-closed posture.** Any KMS error during decrypt fails the requesting operation. CP-02 never falls back to plaintext, alternate keys, or a cached plaintext that survived an earlier scan. The `Plaintext` lifecycle is single-scan.

---

## 8. Provenance threading

CP-02 itself does **not** write `findings` rows or `provenance_records` rows. Its threading responsibility is:

| Field | CP-02 role |
|---|---|
| `scm_credentials.kms_key_arn`, `ciphertext`, `display_fingerprint` | Populated from `EncryptedCredential` by the caller after `encrypt_credential` returns. |
| `orgs.kms_cmk_arn`, `orgs.kms_signing_key_arn` | Lazily provisioned by CP-02. |
| `provenance_records.kms_key_arn`, `kms_key_version`, `signature`, `signature_alg` (in `CMP-FND-03`) | The `SigningKeyHandle` returned by CP-02 is the input to `kms:Sign` calls in `CMP-FND-03` (`signature_alg='RSASSA_PSS_SHA_256'` baseline, CLAR-FND-01). CP-02 does not write `provenance_records`; it provides the key handle. |
| Audit-log event on `rotate_cmk` | OTel attribute set: `{org_id, kms_key_arn, reason}`; no finding-row mutation. |

**Must NOT touch.** CP-02 never reads or writes `findings`, `triage_scores`, `attestations`, `repartition_events`. The triage role's IAM (managed via `CMP-DEPLOY-05`) explicitly denies `kms:Decrypt` against credential CMKs — this is the IAM-level INV-3 ancillary fence.

---

## 9. Acceptance criteria cross-reference

The following AC is quoted **verbatim** from `SDD.md §10 CMP-CP-02`. Paraphrasing is a contract break (RULE-4).

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-CP-02a** | > Credentials are unreadable at rest without the managed key; rotation is supported. | `TST-AC-CP-02a` `[FORTHCOMING]` |

The AC-CP-02a falsifier has two parts:

1. **Unreadable-without-key:** an `EncryptedCredential` row exported from the DB cannot be decrypted by any actor lacking `kms:Decrypt` against the tenant CMK with the matching `EncryptionContext`. This is verified by attempting decryption under (a) a wrong-context call, (b) a wrong-CMK call, (c) a no-IAM call — all three must fail.
2. **Rotation supported:** `rotate_cmk(org_id, reason="scheduled-audit")` succeeds; a credential encrypted under the prior key version is still decryptable; a credential encrypted after rotation is also decryptable; both invocations produce valid plaintext.

Invariant tests cross-referenced:

- `TST-INV-3-CP-02 [FORTHCOMING]` — the triage role's IAM denies `kms:Decrypt` against any credential CMK. Discharges INV-3 ancillary at the substrate level.

---

## 10. Open questions

| CLAR-ID | Question | Status | Impact on CMP-CP-02 |
|---|---|---|---|
| `CLAR-DEPLOY-04` | KMS / envelope encryption vendor + rotation primitive | **RESOLVED** | AWS KMS; per-tenant CMK; annual auto-rotation. CP-02 is a boto3 KMS wrapper. **Do not re-decide.** |
| `CLAR-DEPLOY-16` | Per-tenant data-isolation backstop | **RESOLVED** | CP-02 implements layer 3 (KMS per-tenant CMKs with `EncryptionContext` binding). |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | Owner field in §1 remains DEFERRED. |
| `CLAR-MIGRATION-01` | v2 → v3.2 data migration | **DEFERRED** | v2 credentials (if migrated) must be re-encrypted under v3.2 tenant CMKs at migration time, not lazily on first read. Migration plan (when filed) MUST address this. Working assumption: new-env-only — no v2 credential ever enters v3.2 unencrypted. |

**RULE-9 Security Analyst sign-off** (not a CLAR; a global rule from `.claude/rules/00-global.md`) applies to every CP-02 PR because CP-02 touches credential and signing-key material (INV-3 ancillary surface). The Security Analyst Agent must review and sign off before merge.

No new CLAR-CP-02-* are filed by this document; the AC is unambiguous given CLAR-DEPLOY-04.

---

## 11. References

- `SDD.md §10 CMP-CP-02` — verbatim AC.
- `PLAN.md §"Phase 6 — Multi-tenant control plane"`.
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — CLAR-DEPLOY-04 (KMS), CLAR-DEPLOY-16 (isolation).
- `docs/cross-cutting/DOC-DB.md` §4.1 (`orgs`), §4.5 (`scm_credentials`).
- `docs/cross-cutting/DOC-PROVENANCE.md §7` — signing-key management (consumer of CP-02's `get_signing_key_handle`).
- `docs/cross-cutting/DOC-INV.md §5` — INV-3 verbatim.
- `docs/components/DOC-CMP-CP-01.md` (sibling) — JWT-derived `org_id` source.
- `docs/components/DOC-CMP-CP-03.md` (sibling) — schema migrations including `orgs.kms_cmk_arn`.
- `docs/components/DOC-CMP-FND-03.md` (sibling, forthcoming) — provenance-signing consumer.
- `.claude/rules/00-global.md` RULE-9 (Security Analyst sign-off); `.claude/rules/02-provenance.md`.

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-CP-02`.*
