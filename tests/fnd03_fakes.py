"""Hermetic offline fakes + a record builder for CMP-FND-03 specs.

Mirrors the ``FakeKMS`` pattern of ``tests/unit/test_credential_encryption.py``:
no real AWS, no PostgreSQL. The signer is a software RSASSA-PSS implementation
(``cryptography``) that faithfully models ``kms:Sign`` / ``kms:GetPublicKey``
over a per-tenant RSA key, so a verifier validates a signature without signing
(PSS is randomized — verify by public key, never re-sign-and-compare).

The store is an append-only ``dict`` keyed by record ``id`` (no UPDATE/DELETE
method — modelling the no-UPDATE/DELETE grants on ``provenance_records``).
The artifact store is an in-memory ``uri -> bytes`` map. ``repartition_oracle_id``
is a fixtured uuid; no ``snap_oracle_runs`` table exists (CLAR-DB-03 OPEN), and
none is required in-memory.
"""

from __future__ import annotations

import hashlib
import uuid

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from analysis.ordering import CPG_ORDER_HASH_ANNOTATION
from services.scan.provenance import (
    ProvenanceRecord,
    SignedProvenanceRecord,
)


class SoftwareKMSSigner:
    """Offline RSASSA-PSS signer modelling KMS sign / get_public_key.

    A single 2048-bit RSA key stands in for one per-tenant CMK. ``sign`` returns
    the boto3-shaped ``{"Signature", "KeyId"}`` dict; ``get_public_key`` returns
    the DER ``SubjectPublicKeyInfo`` bytes under ``"PublicKey"`` for the pinned
    ``(KeyId, KeyVersion)``. An unknown key version yields no ``PublicKey`` so
    the verifier returns ``KEY_NOT_FOUND``.
    """

    def __init__(self, *, version: str = "v1") -> None:
        self._private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._version = version

    def sign(
        self,
        *,
        KeyId: str,  # noqa: N803
        Message: bytes,  # noqa: N803
        SigningAlgorithm: str,  # noqa: N803
    ) -> dict[str, object]:
        digest = hashes.SHA384() if SigningAlgorithm == "RSASSA_PSS_SHA_384" else hashes.SHA256()
        signature = self._private.sign(
            Message,
            padding.PSS(mgf=padding.MGF1(digest), salt_length=padding.PSS.DIGEST_LENGTH),
            digest,
        )
        # boto3 returns the version-qualified key id under "KeyId".
        return {"Signature": signature, "KeyId": f"{KeyId}:{self._version}"}

    def get_public_key(
        self,
        *,
        KeyId: str,  # noqa: N803
        KeyVersion: str,  # noqa: N803
    ) -> dict[str, object]:
        if KeyVersion != self._version:
            # Unknown version -> KMS would not resolve a public key.
            return {}
        der = self._private.public_key().public_bytes(
            Encoding.DER, PublicFormat.SubjectPublicKeyInfo
        )
        return {"PublicKey": der}


class InMemoryProvenanceStore:
    """Append-only in-memory ``provenance_records`` (keyed by ``id``)."""

    def __init__(self) -> None:
        self._rows: dict[uuid.UUID, SignedProvenanceRecord] = {}

    def append(self, signed: SignedProvenanceRecord) -> None:
        rid = signed.record.id
        if rid in self._rows:
            # Append-only: a record id is written exactly once (PK constraint).
            raise AssertionError(f"duplicate provenance record id {rid}")
        self._rows[rid] = signed

    def get(self, record_id: uuid.UUID) -> SignedProvenanceRecord | None:
        return self._rows.get(record_id)

    def children(self, parent_record_id: uuid.UUID) -> list[SignedProvenanceRecord]:
        return [s for s in self._rows.values() if s.record.parent_record_id == parent_record_id]


class InMemoryArtifactStore:
    """In-memory S3 stand-in (``uri -> bytes``) for digest recomputation."""

    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}

    def put(self, uri: str, blob: bytes) -> None:
        self._blobs[uri] = blob

    def fetch(self, uri: str) -> bytes | None:
        return self._blobs.get(uri)


def make_chain_record(
    *,
    scan_id: uuid.UUID | None = None,
    sarif_bytes: bytes | None = None,
    s_version: str = "1.2.3",
    env_digest: str = "sha256:" + ("b" * 64),
    origin: str = "deterministic-core",
) -> ProvenanceRecord:
    """Build a ``record_type='chain'`` base record with the INV-5 annotation.

    When ``sarif_bytes`` is given, ``sarif_hash`` is its sha256 digest so the
    verifier's artifact recomputation step has a matching artefact.
    """
    sid = scan_id or uuid.uuid4()
    sarif_hash = hashlib.sha256(sarif_bytes).digest() if sarif_bytes is not None else None
    return ProvenanceRecord(
        id=uuid.uuid4(),
        parent_record_id=None,
        record_type="chain",
        scan_id=sid,
        finding_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        codebase_id=uuid.uuid4(),
        commit_sha="a" * 40,
        scm_provider="github",
        snapshot_id=uuid.uuid4(),
        snapshot_digest="sha256:" + ("c" * 64),  # type: ignore[arg-type]
        precondition_status="closed-world",
        S_version=s_version,  # type: ignore[arg-type]
        env_digest=env_digest,  # type: ignore[arg-type]
        cpg_order_hash=b"\x00" * 32,  # type: ignore[arg-type]
        cpg_order_hash_annotation=CPG_ORDER_HASH_ANNOTATION,
        fingerprint_class="strong",
        witness_blob_uri="s3://witness/abc.json",
        slice_fingerprint=b"\x01" * 32,  # type: ignore[arg-type]
        rule_id="R1",
        spec_id="S1",
        detector_id="det-injection",
        detector_engine="ifds",
        sarif_hash=sarif_hash,  # type: ignore[arg-type]
        origin=origin,  # type: ignore[arg-type]
        determinism_partition=origin,  # type: ignore[arg-type]
        repartition_reason=None,
        repartition_oracle_id=None,
        claim_label="CONDITIONAL_THEOREM",
    )
