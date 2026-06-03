"""Unit tests for CMP-CP-02 — credential encryption service.

These tests drive the ≥80% coverage gate for ``services/credential_encryption.py``
and assert the security properties enumerated in DOC-CMP-CP-02 §3-§9 without any
real AWS call. The KMS client is a deterministic offline fake that faithfully
models the two load-bearing KMS behaviours:

  * ``EncryptionContext`` authentication — ``decrypt`` fails if the context (or
    the CMK ARN) does not match the one used at ``encrypt`` time. This is the
    mechanism that makes cross-tenant decryption impossible (CLAR-DEPLOY-16
    layer 3).
  * Key-version embedding in the ``CiphertextBlob`` — a forced rotation bumps the
    CMK's key-material version, but ciphertexts minted under a prior version
    still decrypt because the version is embedded in the blob (DOC-CMP-CP-02
    §3.4 / §7).

RULE-9: CMP-CP-02 touches credential material; the implementing PR requires
Security Analyst sign-off before merge.
"""

from __future__ import annotations

import base64
import dataclasses
import json
from datetime import datetime
from uuid import UUID, uuid4

import pytest

from services.credential_encryption import (
    CredentialEncryptionError,
    CredentialEncryptionService,
    EncryptedCredential,
    KMSKeyMissingError,
    SigningKeyHandle,
    TenantIsolationError,
)

# ---------------------------------------------------------------------------
# Offline KMS fake + in-memory collaborators
# ---------------------------------------------------------------------------


class FakeKMS:
    """Deterministic in-memory KMS that models context auth + key versioning.

    A ``CiphertextBlob`` produced here is a base64-wrapped JSON envelope carrying
    the plaintext (raw via latin-1), the authenticated ``EncryptionContext`` and
    the key-material version in force when ``encrypt`` ran. The base64 wrap means
    the at-rest blob never contains the plaintext bytes verbatim (modelling that
    KMS ciphertext is opaque). ``decrypt`` rejects any blob whose embedded context
    or key ARN does not match the request — exactly as real KMS does — and accepts
    blobs from any historical version of the key.
    """

    def __init__(self) -> None:
        # key_arn -> current key-material version
        self._versions: dict[str, int] = {}
        self._created = 0

    # -- key lifecycle -----------------------------------------------------

    def create_key(
        self,
        *,
        Description: str,  # noqa: N803
        KeyUsage: str,  # noqa: N803
        KeySpec: str,  # noqa: N803
    ) -> dict[str, object]:
        self._created += 1
        arn = f"arn:aws:kms:us-east-1:000000000000:key/fake-{self._created}-{KeyUsage}"
        self._versions[arn] = 1
        return {"KeyMetadata": {"Arn": arn, "KeyUsage": KeyUsage, "KeySpec": KeySpec}}

    def rotate_key_on_demand(self, *, KeyId: str) -> dict[str, object]:  # noqa: N803
        if KeyId not in self._versions:
            raise KMSKeyMissingError(f"no such key {KeyId}")
        self._versions[KeyId] += 1
        return {"KeyId": KeyId}

    # -- crypto ------------------------------------------------------------

    def encrypt(
        self,
        *,
        KeyId: str,  # noqa: N803
        Plaintext: bytes,  # noqa: N803
        EncryptionContext: dict[str, str],  # noqa: N803
    ) -> dict[str, object]:
        if KeyId not in self._versions:
            raise KMSKeyMissingError(f"no such key {KeyId}")
        envelope = {
            "key": KeyId,
            "ver": self._versions[KeyId],
            "ctx": EncryptionContext,
            "pt": Plaintext.decode("latin-1"),
        }
        blob = base64.b64encode(json.dumps(envelope, sort_keys=True).encode("utf-8"))
        return {"CiphertextBlob": blob, "EncryptionAlgorithm": "SYMMETRIC_DEFAULT"}

    def decrypt(
        self,
        *,
        CiphertextBlob: bytes,  # noqa: N803
        KeyId: str,  # noqa: N803
        EncryptionContext: dict[str, str],  # noqa: N803
    ) -> dict[str, object]:
        if KeyId not in self._versions:
            raise KMSKeyMissingError(f"no such key {KeyId}")
        envelope = json.loads(base64.b64decode(CiphertextBlob).decode("utf-8"))
        # KMS authenticates BOTH the key ARN and the EncryptionContext. Any
        # historical key-material version decrypts (versions survive rotation).
        if envelope["key"] != KeyId or envelope["ctx"] != EncryptionContext:
            raise ValueError("InvalidCiphertextException: context/key mismatch")
        return {"Plaintext": envelope["pt"].encode("latin-1")}


class FakeKeyStore:
    def __init__(self) -> None:
        self._cmk: dict[UUID, str] = {}
        self._signing: dict[UUID, str] = {}

    def get_cmk_arn(self, org_id: UUID) -> str | None:
        return self._cmk.get(org_id)

    def set_cmk_arn(self, org_id: UUID, arn: str) -> None:
        self._cmk[org_id] = arn

    def get_signing_key_arn(self, org_id: UUID) -> str | None:
        return self._signing.get(org_id)

    def set_signing_key_arn(self, org_id: UUID, arn: str) -> None:
        self._signing[org_id] = arn


class FakeAuditLog:
    def __init__(self) -> None:
        self.events: list[dict[str, str]] = []

    def write(self, event: dict[str, str]) -> None:
        self.events.append(event)


@pytest.fixture
def service() -> CredentialEncryptionService:
    return CredentialEncryptionService(
        kms=FakeKMS(),
        key_store=FakeKeyStore(),
        audit_log=FakeAuditLog(),
    )


_PLAINTEXT = b"ghp_secret_token_value_0123456789"


# ---------------------------------------------------------------------------
# AC-CP-02a part 1 — unreadable at rest without the managed key
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_ciphertext_at_rest_is_not_plaintext(service: CredentialEncryptionService) -> None:
    org = uuid4()
    enc = service.encrypt_credential(_PLAINTEXT, org)
    assert isinstance(enc, EncryptedCredential)
    assert enc.ciphertext_blob != _PLAINTEXT
    assert _PLAINTEXT not in enc.ciphertext_blob


@pytest.mark.unit
def test_round_trip_recovers_plaintext(service: CredentialEncryptionService) -> None:
    org = uuid4()
    enc = service.encrypt_credential(_PLAINTEXT, org)
    assert service.decrypt_credential(enc, org) == _PLAINTEXT


@pytest.mark.unit
def test_decrypt_with_wrong_org_context_fails(service: CredentialEncryptionService) -> None:
    """Wrong-context decrypt is rejected — the cross-tenant attack surface."""
    org_a, org_b = uuid4(), uuid4()
    enc = service.encrypt_credential(_PLAINTEXT, org_a)
    with pytest.raises(TenantIsolationError):
        service.decrypt_credential(enc, org_b)


@pytest.mark.unit
def test_decrypt_with_wrong_cmk_fails(service: CredentialEncryptionService) -> None:
    """A ciphertext re-pointed at a different (provisioned) CMK does not decrypt."""
    org_a, org_b = uuid4(), uuid4()
    enc_a = service.encrypt_credential(_PLAINTEXT, org_a)
    # Provision a CMK for org_b, then forge a ciphertext that claims org_b's key.
    enc_b = service.encrypt_credential(_PLAINTEXT, org_b)
    forged = dataclasses.replace(enc_a, kms_key_arn=enc_b.kms_key_arn)
    with pytest.raises(TenantIsolationError):
        service.decrypt_credential(forged, org_a)


@pytest.mark.unit
def test_decrypt_with_unknown_cmk_raises_key_missing(
    service: CredentialEncryptionService,
) -> None:
    org = uuid4()
    enc = service.encrypt_credential(_PLAINTEXT, org)
    orphan = dataclasses.replace(enc, kms_key_arn="arn:aws:kms:us-east-1:000000000000:key/deleted")
    with pytest.raises(KMSKeyMissingError):
        service.decrypt_credential(orphan, org)


# ---------------------------------------------------------------------------
# AC-CP-02a part 2 — rotation supported (forced path)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_rotation_preserves_decryptability_of_old_and_new(
    service: CredentialEncryptionService,
) -> None:
    org = uuid4()
    before = service.encrypt_credential(_PLAINTEXT, org)
    service.rotate_cmk(org, reason="scheduled-audit")
    after = service.encrypt_credential(b"new-token-value", org)
    # Ciphertext minted under the prior key version still decrypts.
    assert service.decrypt_credential(before, org) == _PLAINTEXT
    # Ciphertext minted after rotation also decrypts.
    assert service.decrypt_credential(after, org) == b"new-token-value"


@pytest.mark.unit
def test_rotation_without_provisioned_cmk_raises(
    service: CredentialEncryptionService,
) -> None:
    with pytest.raises(KMSKeyMissingError):
        service.rotate_cmk(uuid4(), reason="forced-compromise")


# ---------------------------------------------------------------------------
# Security properties (DOC-CMP-CP-02 §3-§4)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_encrypted_credential_has_no_plaintext_field() -> None:
    names = {f.name for f in dataclasses.fields(EncryptedCredential)}
    assert "plaintext" not in names
    assert "secret" not in names
    # display_fingerprint digests the at-rest ciphertext, not the secret.
    assert "display_fingerprint" in names


@pytest.mark.unit
def test_display_fingerprint_digests_ciphertext_not_plaintext(
    service: CredentialEncryptionService,
) -> None:
    """Security: the fingerprint must NOT be a hash of the raw secret (that would
    be a confirmation/brute-force oracle + cross-tenant dedupe signal at rest).
    It digests the ciphertext blob instead (RULE-9 Security-Analyst finding, #225).
    """
    from hashlib import sha256

    enc = service.encrypt_credential(_PLAINTEXT, uuid4())
    assert enc.display_fingerprint == sha256(enc.ciphertext_blob).hexdigest()
    # Must NOT equal the hash of the plaintext secret.
    assert enc.display_fingerprint != sha256(_PLAINTEXT).hexdigest()
    assert len(enc.display_fingerprint) == 64
    assert _PLAINTEXT.decode() not in enc.display_fingerprint


@pytest.mark.unit
def test_encryption_context_binds_org_and_purpose(
    service: CredentialEncryptionService,
) -> None:
    org = uuid4()
    enc = service.encrypt_credential(_PLAINTEXT, org)
    assert enc.encryption_context == {"org_id": str(org), "purpose": "scm-credential"}


@pytest.mark.unit
def test_rotation_audit_event_carries_no_credential_material() -> None:
    audit = FakeAuditLog()
    svc = CredentialEncryptionService(kms=FakeKMS(), key_store=FakeKeyStore(), audit_log=audit)
    org = uuid4()
    svc.encrypt_credential(_PLAINTEXT, org)
    svc.rotate_cmk(org, reason="forced-compromise")
    assert len(audit.events) == 1
    event = audit.events[0]
    assert set(event) == {"event", "org_id", "kms_key_arn", "reason", "rotated_at"}
    assert event["event"] == "cmk_rotated"
    assert event["reason"] == "forced-compromise"
    # No credential material in any field.
    for value in event.values():
        assert _PLAINTEXT.decode() not in value


# ---------------------------------------------------------------------------
# Lazy provisioning
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_first_encrypt_provisions_cmk_subsequent_reuses() -> None:
    store = FakeKeyStore()
    svc = CredentialEncryptionService(kms=FakeKMS(), key_store=store, audit_log=FakeAuditLog())
    org = uuid4()
    assert store.get_cmk_arn(org) is None
    enc1 = svc.encrypt_credential(_PLAINTEXT, org)
    arn = store.get_cmk_arn(org)
    assert arn is not None
    enc2 = svc.encrypt_credential(b"another", org)
    # Same tenant CMK reused — not re-provisioned (would orphan ciphertexts).
    assert enc1.kms_key_arn == arn == enc2.kms_key_arn


@pytest.mark.unit
def test_distinct_orgs_get_distinct_cmks(service: CredentialEncryptionService) -> None:
    enc_a = service.encrypt_credential(_PLAINTEXT, uuid4())
    enc_b = service.encrypt_credential(_PLAINTEXT, uuid4())
    assert enc_a.kms_key_arn != enc_b.kms_key_arn


# ---------------------------------------------------------------------------
# Signing-key issuance (CMP-FND-03 consumer)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_signing_key_handle_lazy_and_stable() -> None:
    store = FakeKeyStore()
    svc = CredentialEncryptionService(kms=FakeKMS(), key_store=store, audit_log=FakeAuditLog())
    org = uuid4()
    h1 = svc.get_signing_key_handle(org, purpose="provenance-signing")
    assert isinstance(h1, SigningKeyHandle)
    assert h1.signing_algorithm == "ECDSA_SHA_256"
    assert h1.purpose == "provenance-signing"
    h2 = svc.get_signing_key_handle(org, purpose="provenance-signing")
    assert h1.kms_key_arn == h2.kms_key_arn  # reused, not re-provisioned


@pytest.mark.unit
def test_signing_key_rejects_unknown_purpose() -> None:
    svc = CredentialEncryptionService(
        kms=FakeKMS(), key_store=FakeKeyStore(), audit_log=FakeAuditLog()
    )
    with pytest.raises(CredentialEncryptionError):
        svc.get_signing_key_handle(uuid4(), purpose="encryption")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Determinism / metadata
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_encrypt_sets_algorithm_and_timestamp(service: CredentialEncryptionService) -> None:
    enc = service.encrypt_credential(_PLAINTEXT, uuid4())
    assert enc.encryption_algorithm == "SYMMETRIC_DEFAULT"
    assert isinstance(enc.created_at, datetime)
    assert enc.created_at.tzinfo is not None  # UTC-aware


@pytest.mark.unit
def test_malformed_kms_encrypt_response_fails_closed() -> None:
    class BadKMS(FakeKMS):
        def encrypt(self, **kwargs: object) -> dict[str, object]:
            return {"CiphertextBlob": "not-bytes"}

    svc = CredentialEncryptionService(
        kms=BadKMS(), key_store=FakeKeyStore(), audit_log=FakeAuditLog()
    )
    with pytest.raises(CredentialEncryptionError):
        svc.encrypt_credential(_PLAINTEXT, uuid4())


@pytest.mark.unit
def test_create_key_response_missing_arn_fails_closed() -> None:
    class NoArnKMS(FakeKMS):
        def create_key(self, **kwargs: object) -> dict[str, object]:
            return {"KeyMetadata": {}}

    svc = CredentialEncryptionService(
        kms=NoArnKMS(), key_store=FakeKeyStore(), audit_log=FakeAuditLog()
    )
    with pytest.raises(CredentialEncryptionError):
        svc.encrypt_credential(_PLAINTEXT, uuid4())


@pytest.mark.unit
def test_create_key_flat_keyarn_shape_is_accepted() -> None:
    """boto3 nests the ARN under KeyMetadata.Arn; a flat KeyArn is also tolerated."""

    class FlatArnKMS(FakeKMS):
        def create_key(self, **kwargs: object) -> dict[str, object]:
            arn = "arn:aws:kms:us-east-1:000000000000:key/flat-shape"
            self._versions[arn] = 1
            return {"KeyArn": arn}

    svc = CredentialEncryptionService(
        kms=FlatArnKMS(), key_store=FakeKeyStore(), audit_log=FakeAuditLog()
    )
    enc = svc.encrypt_credential(_PLAINTEXT, uuid4())
    assert enc.kms_key_arn == "arn:aws:kms:us-east-1:000000000000:key/flat-shape"


@pytest.mark.unit
def test_decrypt_propagates_credential_encryption_error_unchanged() -> None:
    """A CredentialEncryptionError raised inside the KMS layer is not masked.

    The fail-closed catch-all only translates *opaque* (non-CP) exceptions into a
    TenantIsolationError; a CP-typed error propagates unchanged so callers see the
    precise cause.
    """

    class RaisingKMS(FakeKMS):
        def decrypt(self, **kwargs: object) -> dict[str, object]:
            raise CredentialEncryptionError("explicit KMS-layer validation failure")

    svc = CredentialEncryptionService(
        kms=RaisingKMS(), key_store=FakeKeyStore(), audit_log=FakeAuditLog()
    )
    org = uuid4()
    enc = svc.encrypt_credential(_PLAINTEXT, org)
    with pytest.raises(CredentialEncryptionError, match="explicit KMS-layer validation failure"):
        svc.decrypt_credential(enc, org)


# ---------------------------------------------------------------------------
# DOC-CMP-CP-02 §7 — botocore error-code split (NotFoundException → 500, not 403)
#
# Regression guard for the masking bug: the typed FakeKMS above raises the
# *CP-typed* KMSKeyMissingError, which propagates via the `except
# CredentialEncryptionError: raise` branch and so NEVER exercises the opaque
# catch-all. A REAL botocore ClientError("NotFoundException") is a plain
# Exception (carrying `.response["Error"]["Code"]`) and DID hit the catch-all,
# where it was mislabeled `TenantIsolationError` (403) and pushed onto the
# cross-tenant forensic/WARN channel. `_FakeClientError` models that real shape;
# it deliberately subclasses Exception (NOT CredentialEncryptionError) so it
# reaches the catch-all rather than the typed-propagate branch.
# ---------------------------------------------------------------------------


class _FakeClientError(Exception):
    """Duck-typed stand-in for a botocore ClientError (no botocore dependency).

    botocore is not installed for CP-02; a real ClientError carries the error
    code at ``.response["Error"]["Code"]``. This reproduces that exact shape so
    the structural ``_kms_error_code`` read is exercised against a realistic
    payload — the typed fakes above cannot do this, which is why the bug hid.
    """

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code, "Message": code}}


def _kms_raising_service(code: str) -> CredentialEncryptionService:
    """Service whose KMS.decrypt raises a botocore-shaped ClientError(`code`)."""

    class ClientErrorKMS(FakeKMS):
        def decrypt(self, **kwargs: object) -> dict[str, object]:
            raise _FakeClientError(code)

    return CredentialEncryptionService(
        kms=ClientErrorKMS(), key_store=FakeKeyStore(), audit_log=FakeAuditLog()
    )


@pytest.mark.unit
def test_decrypt_notfound_clienterror_raises_key_missing_not_isolation() -> None:
    """POSITIVE: a botocore NotFoundException maps to KMSKeyMissingError (500).

    Anti-vacuity / the load-bearing split: the raised error must NOT be a
    TenantIsolationError. KMSKeyMissingError and TenantIsolationError are
    *siblings* (both subclass CredentialEncryptionError), so the isinstance
    check proves the NotFound case left the cross-tenant 403 alarm — a
    do-nothing impl (everything → TenantIsolationError) fails the `raises`
    line, and a mapping to a TenantIsolationError subclass would fail the
    isinstance assertion.
    """
    svc = _kms_raising_service("NotFoundException")
    org = uuid4()
    enc = svc.encrypt_credential(_PLAINTEXT, org)
    with pytest.raises(KMSKeyMissingError) as excinfo:
        svc.decrypt_credential(enc, org)
    # Split out of the cross-tenant alarm: must not be (a subclass of) the 403.
    assert not isinstance(excinfo.value, TenantIsolationError)


@pytest.mark.unit
@pytest.mark.parametrize("code", ["InvalidCiphertextException", "AccessDeniedException"])
def test_decrypt_other_clienterror_stays_fail_closed_403(code: str) -> None:
    """NEGATIVE CONTROL: every non-NotFound opaque KMS error stays 403.

    Pins the fail-closed catch-all and RULE-4 (only ONE code is split out):
    - InvalidCiphertextException is the cross-tenant EncryptionContext/CMK
      mismatch — it MUST remain TenantIsolationError.
    - AccessDeniedException is an unrelated opaque error — also fail-closed 403.
    Without this arm a broken impl that mapped EVERY ClientError to
    KMSKeyMissingError (or that read the code and matched too broadly) would
    still pass the positive test; here it raises KMSKeyMissingError where a
    TenantIsolationError is required and fails.
    """
    svc = _kms_raising_service(code)
    org = uuid4()
    enc = svc.encrypt_credential(_PLAINTEXT, org)
    with pytest.raises(TenantIsolationError):
        svc.decrypt_credential(enc, org)


@pytest.mark.unit
def test_kms_error_code_reads_botocore_shape_else_none() -> None:
    """Unit-level guard for the duck-typed reader used by the split.

    A botocore-shaped exception yields its code; anything lacking the
    `.response["Error"]["Code"]` string shape yields None (so it falls through
    to the fail-closed catch-all). This locks the reader against silently
    returning a truthy value for a malformed/absent response.
    """
    from services.credential_encryption import _kms_error_code

    assert _kms_error_code(_FakeClientError("NotFoundException")) == "NotFoundException"
    # No `.response` at all → None (plain ValueError, e.g. our context-mismatch path).
    assert _kms_error_code(ValueError("InvalidCiphertextException: ...")) is None
    # Malformed response shapes → None, never a crash.
    assert _kms_error_code(_BadResponseError(response="not-a-dict")) is None
    assert _kms_error_code(_BadResponseError(response={"Error": "not-a-dict"})) is None
    assert _kms_error_code(_BadResponseError(response={"Error": {"Code": 404}})) is None


class _BadResponseError(Exception):
    """Exception carrying an arbitrary `.response` attr, for the reader guard."""

    def __init__(self, *, response: object) -> None:
        super().__init__("bad-response")
        self.response = response
