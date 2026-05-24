"""CMP-CP-02 — Credential encryption service (KMS envelope encryption).

Implementation contract: ``docs/components/DOC-CMP-CP-02.md``.
Cross-cutting refs: ``docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`` (CLAR-DEPLOY-04
KMS envelope encryption, per-tenant CMK, annual auto-rotation; CLAR-DEPLOY-16
layered isolation), ``DOC-DB §4.1/§4.5``, ``DOC-PROVENANCE §7``, ``DOC-INV §5``.

``CredentialEncryptionService`` is the credential-encryption substrate for
Scanipy v3.2. It wraps an AWS-KMS client and provides four per-tenant-scoped
operations: ``encrypt_credential``, ``decrypt_credential``, ``rotate_cmk`` and
``get_signing_key_handle``. Every SCM credential's bytes-in / bytes-out passes
through this module (DOC-CMP-CP-02 §2).

Envelope-encryption contract (CLAR-DEPLOY-04): a per-tenant Customer-Managed Key
(CMK) wraps a per-credential data key; the data key encrypts the plaintext. AWS
KMS performs annual rotation automatically; ``rotate_cmk`` exists only for the
*forced* case (suspected compromise / scheduled audit).

INV-3 (ancillary): credential plaintext never crosses the LLM-triage surface.
This module enforces the application-side guarantees that make that true:

  * Plaintext is **never** logged, persisted to disk, exported to OTel span
    attributes, or returned in any structure other than the raw ``bytes`` from
    ``decrypt_credential``. The only safe identifier is ``display_fingerprint``
    (a sha256 hex digest with no cryptographic significance).
  * Every KMS call binds an ``EncryptionContext`` of ``{"org_id", "purpose"}``;
    KMS authenticates the context so a ciphertext minted for org A cannot be
    decrypted as if it were org B's, even under the same CMK ARN. This is layer
    3 of CLAR-DEPLOY-16 (KMS per-tenant data isolation).

CP-02 does **not** write ``findings`` / ``provenance_records`` / ``triage_scores``
rows; it is a key service consumed by ``CMP-SCM-01`` (encrypt at registration),
``CMP-SNAP-05`` (decrypt at scan time) and ``CMP-FND-03`` (signing-key handle).
All external collaborators — the KMS client, the org-key store, and the audit
log — are injected so the service is testable offline without real AWS.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

# Region used to mint placeholder ARNs when this module lazily provisions a CMK
# via the injected KMS client. The real ARN is whatever the KMS client returns;
# this constant only affects the synthesized alias path.
DEFAULT_KMS_REGION = "us-east-1"

# The encryption-context purpose tags (DOC-CMP-CP-02 §3.2). KMS authenticates
# these, so they are load-bearing security values, not cosmetic labels.
PURPOSE_SCM_CREDENTIAL = "scm-credential"
PURPOSE_PROVENANCE_SIGNING = "provenance-signing"

# Forced-rotation reason codes accepted by ``rotate_cmk`` (DOC-CMP-CP-02 §3.4).
RotationReason = Literal["scheduled", "forced-compromise", "scheduled-audit"]


class CredentialEncryptionError(Exception):
    """Base class for CP-02 errors (fail-closed posture, DOC-CMP-CP-02 §7)."""


class TenantIsolationError(CredentialEncryptionError):
    """Decrypt attempted with an ``org_id`` that does not match the ciphertext.

    Surfaced when the KMS layer rejects an ``EncryptionContext`` / CMK mismatch
    (cross-tenant decryption attempt). Maps to HTTP 403 ``tenant_isolation_violation``
    in the API layer (DOC-CMP-CP-02 §7).
    """


class KMSKeyMissingError(CredentialEncryptionError):
    """Tenant CMK is absent on a decrypt path.

    Never auto-create on decrypt: a missing CMK means it was deleted, and
    silently re-creating it would orphan every existing ciphertext
    (DOC-CMP-CP-02 §7). Maps to HTTP 500 ``KMS_KEY_MISSING``.
    """


@dataclass(frozen=True)
class EncryptedCredential:
    """At-rest representation of an encrypted SCM credential (DOC-CMP-CP-02 §3.1).

    Deliberately carries **no** plaintext field: every attribute here is safe to
    persist to ``scm_credentials`` (DOC-DB §4.5). ``display_fingerprint`` is a
    sha256 hex digest used only for display / dedupe; it has no cryptographic
    role and is never used to derive a key.
    """

    ciphertext_blob: bytes
    kms_key_arn: str
    encryption_algorithm: str
    encryption_context: dict[str, str]
    display_fingerprint: str
    created_at: datetime


@dataclass(frozen=True)
class SigningKeyHandle:
    """Handle to a per-tenant asymmetric KMS signing key (DOC-PROVENANCE §7.3).

    Consumed by ``CMP-FND-03`` to invoke ``kms:Sign`` against provenance records.
    """

    kms_key_arn: str
    signing_algorithm: Literal["ECDSA_SHA_256", "ECDSA_SHA_384"]
    purpose: Literal["provenance-signing"]


@runtime_checkable
class KMSClient(Protocol):
    """Structural subset of the boto3 KMS client this service depends on.

    Only the methods CP-02 calls are declared; any boto3 KMS client (or an
    offline fake) satisfies this Protocol. Return shapes mirror the boto3 KMS
    response dicts (``CiphertextBlob``, ``Plaintext``, ``KeyMetadata`` ...).
    """

    def encrypt(
        self,
        *,
        KeyId: str,  # noqa: N803 — boto3 wire parameter names are PascalCase.
        Plaintext: bytes,  # noqa: N803
        EncryptionContext: dict[str, str],  # noqa: N803
    ) -> dict[str, object]: ...

    def decrypt(
        self,
        *,
        CiphertextBlob: bytes,  # noqa: N803
        KeyId: str,  # noqa: N803
        EncryptionContext: dict[str, str],  # noqa: N803
    ) -> dict[str, object]: ...

    def rotate_key_on_demand(self, *, KeyId: str) -> dict[str, object]: ...  # noqa: N803

    def create_key(
        self,
        *,
        Description: str,  # noqa: N803
        KeyUsage: str,  # noqa: N803
        KeySpec: str,  # noqa: N803
    ) -> dict[str, object]: ...


@runtime_checkable
class OrgKeyStore(Protocol):
    """Persistence of per-tenant KMS key ARNs (``orgs.kms_cmk_arn`` / ``kms_signing_key_arn``).

    A thin port over ``DOC-DB §4.1``. The application wires a SQL-backed
    implementation under the control-plane internal IAM role; tests wire an
    in-memory fake.
    """

    def get_cmk_arn(self, org_id: UUID) -> str | None: ...

    def set_cmk_arn(self, org_id: UUID, arn: str) -> None: ...

    def get_signing_key_arn(self, org_id: UUID) -> str | None: ...

    def set_signing_key_arn(self, org_id: UUID, arn: str) -> None: ...


@runtime_checkable
class AuditLog(Protocol):
    """Sink for the ``cmk_rotated`` audit event (OTel → CloudWatch, CLAR-DEPLOY-07).

    The event payload must never contain credential material — only
    ``{org_id, kms_key_arn, reason, rotated_at}`` (DOC-CMP-CP-02 §4.3).
    """

    def write(self, event: dict[str, str]) -> None: ...


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class CredentialEncryptionService:
    """KMS envelope-encryption service for SCM credentials (CMP-CP-02).

    All collaborators are injected: ``kms`` (boto3-compatible KMS client),
    ``key_store`` (per-tenant ARN persistence) and ``audit_log`` (rotation event
    sink). The ``now`` callable is injectable so ``created_at`` is deterministic
    under test.
    """

    kms: KMSClient
    key_store: OrgKeyStore
    audit_log: AuditLog

    def encrypt_credential(self, plaintext: bytes, org_id: UUID) -> EncryptedCredential:
        """Encrypt ``plaintext`` under the tenant CMK, provisioning it lazily.

        Binds ``EncryptionContext={"org_id", "purpose": "scm-credential"}`` so the
        ciphertext is cryptographically pinned to the tenant (DOC-CMP-CP-02 §3.2).
        Returns an :class:`EncryptedCredential` carrying no plaintext; the caller
        (``CMP-SCM-01``) persists it to ``scm_credentials``.
        """
        cmk_arn = self.key_store.get_cmk_arn(org_id)
        if cmk_arn is None:
            cmk_arn = self._provision_cmk(org_id)
            self.key_store.set_cmk_arn(org_id, cmk_arn)

        context = {"org_id": str(org_id), "purpose": PURPOSE_SCM_CREDENTIAL}
        resp = self.kms.encrypt(
            KeyId=cmk_arn,
            Plaintext=plaintext,
            EncryptionContext=context,
        )
        ciphertext_blob = _expect_bytes(resp, "CiphertextBlob")
        algorithm = str(resp.get("EncryptionAlgorithm", "SYMMETRIC_DEFAULT"))

        return EncryptedCredential(
            ciphertext_blob=ciphertext_blob,
            kms_key_arn=cmk_arn,
            encryption_algorithm=algorithm,
            encryption_context=context,
            # Display-only sha256; never a key-derivation input (DOC-CMP-CP-02 §3.2).
            display_fingerprint=sha256(plaintext).hexdigest(),
            created_at=_now(),
        )

    def decrypt_credential(self, ciphertext: EncryptedCredential, org_id: UUID) -> bytes:
        """Decrypt ``ciphertext`` back to plaintext bytes for the calling tenant.

        Fail-closed: a cross-tenant attempt (``EncryptionContext`` / CMK mismatch)
        raises :class:`TenantIsolationError`; a deleted CMK raises
        :class:`KMSKeyMissingError`. The returned plaintext is single-scan and
        MUST be discarded at scan completion by the caller — it is never logged,
        persisted, or passed to an LLM (DOC-CMP-CP-02 §3.3 / §4.3).
        """
        context = {"org_id": str(org_id), "purpose": PURPOSE_SCM_CREDENTIAL}
        try:
            resp = self.kms.decrypt(
                CiphertextBlob=ciphertext.ciphertext_blob,
                KeyId=ciphertext.kms_key_arn,
                EncryptionContext=context,
            )
        except CredentialEncryptionError:
            # Already-classified CP errors (e.g. KMSKeyMissingError) propagate
            # unchanged so callers see the precise cause (DOC-CMP-CP-02 §7).
            raise
        except Exception as exc:  # translate opaque KMS errors fail-closed.
            raise TenantIsolationError(
                "decrypt rejected: EncryptionContext / CMK mismatch "
                f"(requested org_id={org_id}, ciphertext key={ciphertext.kms_key_arn})"
            ) from exc
        return _expect_bytes(resp, "Plaintext")

    def rotate_cmk(self, org_id: UUID, reason: RotationReason) -> None:
        """Force a new CMK key-material version (DOC-CMP-CP-02 §3.4).

        AWS KMS preserves all prior key versions, so existing ciphertexts remain
        decryptable — the wrapping-key version is embedded in each
        ``CiphertextBlob`` and resolved by KMS at decrypt time. No ciphertext
        re-encryption occurs. Emits a ``cmk_rotated`` audit event whose payload
        contains no credential material.
        """
        cmk_arn = self.key_store.get_cmk_arn(org_id)
        if cmk_arn is None:
            raise KMSKeyMissingError(f"cannot rotate: no CMK provisioned for org_id={org_id}")
        self.kms.rotate_key_on_demand(KeyId=cmk_arn)
        self.audit_log.write(
            {
                "event": "cmk_rotated",
                "org_id": str(org_id),
                "kms_key_arn": cmk_arn,
                "reason": reason,
                "rotated_at": _now().isoformat(),
            }
        )

    def get_signing_key_handle(
        self,
        org_id: UUID,
        purpose: Literal["provenance-signing"],
    ) -> SigningKeyHandle:
        """Return a per-tenant asymmetric signing-key handle for ``CMP-FND-03``.

        Lazily provisions an ECDSA P-256 key on first use (DOC-PROVENANCE §7.3).
        """
        if purpose != PURPOSE_PROVENANCE_SIGNING:
            raise CredentialEncryptionError(f"unsupported signing-key purpose: {purpose!r}")
        arn = self.key_store.get_signing_key_arn(org_id)
        if arn is None:
            arn = self._provision_signing_key(org_id)
            self.key_store.set_signing_key_arn(org_id, arn)
        return SigningKeyHandle(
            kms_key_arn=arn,
            signing_algorithm="ECDSA_SHA_256",
            purpose=purpose,
        )

    # -- internal provisioning -------------------------------------------------

    def _provision_cmk(self, org_id: UUID) -> str:
        """Create a symmetric per-tenant CMK via the KMS client."""
        resp = self.kms.create_key(
            Description=f"scanipy scm-credential CMK for org {org_id}",
            KeyUsage="ENCRYPT_DECRYPT",
            KeySpec="SYMMETRIC_DEFAULT",
        )
        return _key_arn(resp)

    def _provision_signing_key(self, org_id: UUID) -> str:
        """Create an asymmetric per-tenant signing key via the KMS client."""
        resp = self.kms.create_key(
            Description=f"scanipy provenance-signing key for org {org_id}",
            KeyUsage="SIGN_VERIFY",
            KeySpec="ECC_NIST_P256",
        )
        return _key_arn(resp)


def _expect_bytes(resp: dict[str, object], key: str) -> bytes:
    value = resp.get(key)
    if not isinstance(value, bytes):
        raise CredentialEncryptionError(
            f"KMS response missing/invalid {key!r}: expected bytes, got {type(value).__name__}"
        )
    return value


def _key_arn(resp: dict[str, object]) -> str:
    """Extract the new key ARN from a ``kms:CreateKey`` response.

    boto3 nests it under ``KeyMetadata.Arn``; a flat ``KeyArn`` is also accepted.
    """
    metadata = resp.get("KeyMetadata")
    if isinstance(metadata, dict):
        arn = metadata.get("Arn")
        if isinstance(arn, str):
            return arn
    flat = resp.get("KeyArn")
    if isinstance(flat, str):
        return flat
    raise CredentialEncryptionError("KMS create_key response missing KeyMetadata.Arn")


__all__ = [
    "DEFAULT_KMS_REGION",
    "AuditLog",
    "CredentialEncryptionError",
    "CredentialEncryptionService",
    "EncryptedCredential",
    "KMSClient",
    "KMSKeyMissingError",
    "OrgKeyStore",
    "SigningKeyHandle",
    "TenantIsolationError",
]
