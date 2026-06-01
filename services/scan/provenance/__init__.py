"""CMP-FND-03 — Signed provenance record.

Implementation contract: ``docs/components/DOC-CMP-FND-03.md``.
Cross-cutting refs: ``DOC-PROVENANCE`` (§2 four fields, §3 chain shape + §3.2
canonical record-bytes, §4 re-partition events, §5 honest-labelling, §7 KMS,
§8 auditor export + §8.4 verify procedure), ``DOC-DB §4.13`` (canonical DDL),
``.claude/rules/01-invariants.md`` (INV-1, INV-2, INV-5),
``.claude/rules/02-provenance.md`` (threading rules).

This package constructs, signs, verifies, and exports the 9-link signed audit
chain ``source commit -> snapshot digest -> S_version -> env_digest ->
cpg_order_hash (canonical iff strong) -> taint witness -> rule/spec id ->
SARIF hash -> per-finding origin`` (the construction proof of ``PLAN.md``
property (c)).

All external collaborators — the KMS asymmetric signer, the
``provenance_records`` store, and the S3 artifact store — are injected as
Protocols so the component is testable offline without real AWS / PostgreSQL
(mirrors the dependency-injection pattern of
``services/credential_encryption.py``). The baseline signing algorithm is
``RSASSA_PSS_SHA_256`` (CLAR-DEPLOY-04 / CLAR-FND-01 RESOLVED 2026-05-23); the
DDL CHECK on ``provenance_records.signature_alg`` enforces the same.

INV-5 anchor: the conditional-canonicality annotation is **never** rebuilt from
substrings here. It is imported from the single construction site
``analysis.ordering.CPG_ORDER_HASH_ANNOTATION`` (re-exported by
``services/scan/models/findings.py``) and written JSON-adjacent to
``cpg_order_hash`` in every record and every auditor export.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from dataclasses import dataclass
from typing import Literal, NewType, Protocol, runtime_checkable

from analysis.ordering import CPG_ORDER_HASH_ANNOTATION

Sha256 = NewType("Sha256", bytes)  # 32 raw bytes
Sha256Hex = NewType("Sha256Hex", str)  # 64 hex
SemVer = NewType("SemVer", str)

RecordType = Literal["chain", "repartition", "attestation", "spec-acceptance", "witness-update"]
Origin = Literal["deterministic-core", "oracle-passthrough"]
SignatureAlg = Literal["RSASSA_PSS_SHA_256", "RSASSA_PSS_SHA_384"]
ClaimLabel = Literal["CONDITIONAL_THEOREM", "EMPIRICAL", "STAGED", "UNCONDITIONAL"]
PreconditionStatus = Literal["closed-world", "degraded", "full-reparse"]
DetectorEngine = Literal["ifds", "ide", "semgrep", "cpg-query", "external"]
FingerprintClass = Literal["strong", "weak"]

# Baseline signing algorithm (CLAR-DEPLOY-04 / CLAR-FND-01); the DDL CHECK on
# provenance_records.signature_alg admits only this and RSASSA_PSS_SHA_384.
DEFAULT_SIGNATURE_ALG: SignatureAlg = "RSASSA_PSS_SHA_256"

# Verdicts returned by verify_chain (DOC-PROVENANCE §8.4).
VerifyVerdict = Literal["VERIFIED", "TAMPERED", "KEY_NOT_FOUND", "ARTIFACT_MISSING"]


class ProvenanceError(Exception):
    """Base class for CMP-FND-03 errors (DOC-CMP-FND-03 §7)."""


class RepartitionWithoutParent(ProvenanceError):  # noqa: N818 — name fixed verbatim by DOC-CMP-FND-03 §7.1
    """``append_repartition_event`` called with a ``parent_record_id`` that does
    not resolve to a stored record (DOC-CMP-FND-03 §7.1)."""


class InvariantViolation(ProvenanceError):  # noqa: N818 — name fixed verbatim by DOC-CMP-FND-03 §7.1
    """An application-layer invariant guard tripped before persistence.

    Carries an API error ``code`` per ``DOC-API §6.1`` (e.g.
    ``invariant_inv5_violation``).
    """

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ProvenanceRecord:
    """The 9-link chain, pre-signature.

    Canonical DDL: ``DOC-DB §4.13``; semantics: ``DOC-PROVENANCE §3``. The
    dataclass mirrors that shipped column-per-link shape (CLAR-FND-01 RESOLVED).
    """

    # Identity & chain linkage
    id: uuid.UUID
    parent_record_id: uuid.UUID | None
    record_type: RecordType
    # Scope keys
    scan_id: uuid.UUID
    finding_id: uuid.UUID | None
    # Link 1 — source commit
    org_id: uuid.UUID
    codebase_id: uuid.UUID
    commit_sha: str
    scm_provider: str
    # Link 2 — snapshot digest
    snapshot_id: uuid.UUID
    snapshot_digest: Sha256Hex
    precondition_status: PreconditionStatus
    # Links 3 + 4 — INV-2
    S_version: SemVer
    env_digest: Sha256Hex
    # Link 5 — cpg_order_hash + INV-5 annotation
    cpg_order_hash: Sha256 | None
    cpg_order_hash_annotation: str
    fingerprint_class: FingerprintClass | None
    # Link 6 — taint witness
    witness_blob_uri: str | None
    slice_fingerprint: Sha256 | None
    # Link 7 — rule / spec id
    rule_id: str | None
    spec_id: str | None
    detector_id: str | None
    detector_engine: DetectorEngine | None
    # Link 8 — SARIF hash
    sarif_hash: Sha256 | None
    # Link 9 — per-finding origin (INV-1)
    origin: Origin | None
    determinism_partition: Origin | None
    # Re-partition linkage (DOC-PROVENANCE §4)
    repartition_reason: str | None
    repartition_oracle_id: uuid.UUID | None
    # Honest-labeling (DOC-PROVENANCE §5)
    claim_label: ClaimLabel


@dataclass(frozen=True)
class SignedProvenanceRecord:
    """A :class:`ProvenanceRecord` plus its KMS signing envelope (§3.1)."""

    record: ProvenanceRecord
    canonical_bytes: bytes
    kms_key_arn: str
    kms_key_version: str
    signature: bytes
    signature_alg: SignatureAlg


@runtime_checkable
class KMSAsymmetricSigner(Protocol):
    """Structural subset of the KMS asymmetric-signing surface FND-03 uses.

    Mirrors the boto3 KMS wire shape so any boto3 KMS client — or an offline
    software RSASSA-PSS fake (used in tests) — satisfies it. The signer resolves
    the per-tenant CMK ARN out of band (CLAR-DEPLOY-16: one CMK per tenant);
    callers pass the resolved ``KeyId``. ``GetPublicKey`` returns the
    version-pinned public key so a verifier can validate a signature without
    signing (DOC-PROVENANCE §7.1).
    """

    def sign(
        self,
        *,
        KeyId: str,  # noqa: N803 — boto3 wire parameter names are PascalCase.
        Message: bytes,  # noqa: N803
        SigningAlgorithm: str,  # noqa: N803
    ) -> dict[str, object]: ...

    def get_public_key(
        self,
        *,
        KeyId: str,  # noqa: N803
        KeyVersion: str,  # noqa: N803
    ) -> dict[str, object]: ...


@runtime_checkable
class ProvenanceStore(Protocol):
    """Append-only persistence port for ``provenance_records`` (DOC-DB §4.13).

    The production implementation is SQL-backed under the FND-03 worker IAM
    role; tests wire an in-memory fake. The store is append-only: there is no
    ``update`` / ``delete`` method, faithfully modelling the no-UPDATE/DELETE
    grants on the table (DOC-CMP-FND-03 §7.2). A correction is a new
    ``record_type='repartition'`` row, never an UPDATE of the parent.
    """

    def append(self, signed: SignedProvenanceRecord) -> None: ...

    def get(self, record_id: uuid.UUID) -> SignedProvenanceRecord | None: ...

    def children(self, parent_record_id: uuid.UUID) -> list[SignedProvenanceRecord]: ...


@runtime_checkable
class ArtifactStore(Protocol):
    """Read port over the S3 artifacts the verifier recomputes digests from.

    Keys are the artifact URIs (sarif log, witness blob, snapshot tarball). The
    verifier fetches bytes and recomputes their sha256 to compare against the
    chain's ``sarif_hash`` / ``snapshot_digest`` (DOC-PROVENANCE §8.4 steps 4-5)
    — no IFDS / Algorithm 5 / detector is ever invoked.
    """

    def fetch(self, uri: str) -> bytes | None: ...


def _canonical_value(value: object) -> object:
    """Map a record field to its canonical-JSON representation.

    ``bytes`` -> lowercase hex (matches ``analysis.ordering.to_provenance_fields``);
    ``uuid.UUID`` -> ``str``; everything else (``str`` / ``None``) is left as-is.
    """
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def canonical_record_bytes(record: ProvenanceRecord) -> bytes:
    """Compute the canonical signature input for ``record`` (DOC-PROVENANCE §3.2).

    JSON over every :class:`ProvenanceRecord` field **except** ``signature``,
    ``kms_key_version`` and ``created_at`` (none of which live on the dataclass),
    with keys sorted lexicographically by Unicode code point, no insignificant
    whitespace, UTF-8 encoding. ``sign_provenance`` and ``verify_chain`` both
    call this so the verifier reconstructs bytes from the stored row rather than
    trusting the stored ``canonical_bytes`` (the only way TAMPERED detection is
    meaningful).
    """
    payload = {
        field.name: _canonical_value(getattr(record, field.name))
        for field in dataclasses.fields(record)
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_provenance(
    record: ProvenanceRecord,
    *,
    signer: KMSAsymmetricSigner,
    kms_key_arn: str,
    signature_alg: SignatureAlg = DEFAULT_SIGNATURE_ALG,
    store: ProvenanceStore | None = None,
) -> SignedProvenanceRecord:
    """Compute canonical bytes, sign via ``kms:Sign``, and (optionally) persist.

    Per DOC-CMP-FND-03 §3.1:

    1. Compute ``canonical_bytes`` per DOC-PROVENANCE §3.2.
    2. Call ``kms:Sign`` on the tenant CMK with ``SigningAlgorithm`` = the
       baseline ``RSASSA_PSS_SHA_256`` (CLAR-DEPLOY-04). The CMK ARN is resolved
       by the caller from tenant config (one CMK per tenant, CLAR-DEPLOY-16).
    3. If a ``store`` is supplied, append the signed record (append-only).

    Defence-in-depth INV-5 guard: a record whose ``cpg_order_hash_annotation``
    is not the pinned literal is rejected before signing (the DB CHECK would
    catch it too, but the application-layer catch yields a clearer error,
    DOC-CMP-FND-03 §7.1).
    """
    if record.cpg_order_hash_annotation != CPG_ORDER_HASH_ANNOTATION:
        raise InvariantViolation(
            "cpg_order_hash_annotation must be the pinned INV-5 literal "
            f"{CPG_ORDER_HASH_ANNOTATION!r}; got {record.cpg_order_hash_annotation!r}",
            code="invariant_inv5_violation",
        )

    canonical = canonical_record_bytes(record)
    resp = signer.sign(
        KeyId=kms_key_arn,
        Message=canonical,
        SigningAlgorithm=signature_alg,
    )
    signature = _expect_bytes(resp, "Signature")
    # boto3 returns the version-qualified key id under "KeyId"; the trailing
    # segment is the key-material version that preserves prior signatures across
    # rotation (DOC-PROVENANCE §7.1).
    key_id = str(resp.get("KeyId", kms_key_arn))
    kms_key_version = key_id.split(":")[-1] if ":" in key_id else key_id

    signed = SignedProvenanceRecord(
        record=record,
        canonical_bytes=canonical,
        kms_key_arn=kms_key_arn,
        kms_key_version=kms_key_version,
        signature=signature,
        signature_alg=signature_alg,
    )
    if store is not None:
        store.append(signed)
    return signed


def verify_chain(
    signed: SignedProvenanceRecord,
    *,
    signer: KMSAsymmetricSigner,
    artifacts: ArtifactStore | None = None,
    store: ProvenanceStore | None = None,
) -> VerifyVerdict:
    """Independently verify a signed record from stored artefacts (§8.4).

    Does NOT re-run IFDS / Algorithm 5 / detectors (AC-FND-03a). Steps:

    1. Reconstruct ``canonical_bytes`` from ``signed.record`` per §3.2 (never
       trust the stored ``canonical_bytes``).
    2. Fetch the KMS public key at ``(kms_key_arn, kms_key_version)``.
    3. Verify the signature over the recomputed bytes with ``signature_alg``.
    4. If an ``artifacts`` store is supplied, recompute the sarif / snapshot
       digests and assert they match the record.
    5. For ``record_type == 'repartition'``: verify the parent record per 1-4.

    Verdicts: ``VERIFIED`` | ``TAMPERED`` | ``KEY_NOT_FOUND`` | ``ARTIFACT_MISSING``.
    """
    canonical = canonical_record_bytes(signed.record)

    pub_resp = signer.get_public_key(
        KeyId=signed.kms_key_arn,
        KeyVersion=signed.kms_key_version,
    )
    public_key = pub_resp.get("PublicKey")
    if not isinstance(public_key, (bytes, bytearray)):
        return "KEY_NOT_FOUND"

    if not _verify_signature(
        public_key=bytes(public_key),
        message=canonical,
        signature=signed.signature,
        signature_alg=signed.signature_alg,
    ):
        return "TAMPERED"

    if artifacts is not None:
        artifact_verdict = _verify_artifacts(signed.record, artifacts)
        if artifact_verdict != "VERIFIED":
            return artifact_verdict

    if signed.record.record_type == "repartition" and store is not None:
        parent_id = signed.record.parent_record_id
        if parent_id is None:
            return "TAMPERED"
        parent = store.get(parent_id)
        if parent is None:
            return "ARTIFACT_MISSING"
        parent_verdict = verify_chain(parent, signer=signer, artifacts=artifacts, store=store)
        if parent_verdict != "VERIFIED":
            return parent_verdict

    return "VERIFIED"


def _verify_artifacts(record: ProvenanceRecord, artifacts: ArtifactStore) -> VerifyVerdict:
    """Recompute the SARIF digest from the artifact store (§8.4 steps 4-5).

    Only digest-bearing links are recomputed: ``sarif_hash`` is the one the chain
    carries as a raw digest, so the verifier fetches the SARIF blob and asserts
    its recomputed sha256 matches. ``snapshot_digest`` recomputation
    (DOC-PROVENANCE §8.4 step 4-5) is intentionally deferred: the CPG tarball is
    fetched only "if needed"/when cached (it has a 90-day retention vs. the 7-year
    SARIF/provenance retention, DOC-PROVENANCE §6), and the witness blob carries
    no digest field on the record to compare against, so neither gates the verdict
    here. When a snapshot tarball is provisioned for re-verification, this is the
    extension point. No IFDS / Algorithm 5 / detector is invoked.
    """
    import hashlib

    if record.sarif_hash is not None:
        sarif_uri = f"sarif/{record.scan_id}.sarif.json"
        blob = artifacts.fetch(sarif_uri)
        if blob is None:
            return "ARTIFACT_MISSING"
        if hashlib.sha256(blob).digest() != bytes(record.sarif_hash):
            return "TAMPERED"

    return "VERIFIED"


def export_auditor_record(
    record_id: uuid.UUID,
    *,
    store: ProvenanceStore,
) -> dict[str, object]:
    """Build the customer-facing auditor export for ``record_id`` (§8.1).

    The export's ``cpg_order_hash`` and ``cpg_order_hash_annotation`` keys are
    JSON-adjacent (consecutive ``dict`` insertion order = JSON adjacency,
    AC-FND-03b / INV-5). A ``repartition_history`` array surfaces every
    re-partition event chained to this record (AC-FND-03c).
    """
    signed = store.get(record_id)
    if signed is None:
        raise ProvenanceError(f"no provenance record {record_id}")
    record = signed.record

    export: dict[str, object] = {
        "id": str(record.id),
        "parent_record_id": _opt_uuid(record.parent_record_id),
        "record_type": record.record_type,
        "commit_sha": record.commit_sha,
        "scm_provider": record.scm_provider,
        "snapshot_digest": record.snapshot_digest,
        "precondition_status": record.precondition_status,
        "S_version": record.S_version,
        "env_digest": record.env_digest,
        # INV-5: the hash and its annotation are written consecutively so they
        # are JSON-adjacent; the annotation is the pinned constant, never rebuilt.
        "cpg_order_hash": _opt_hex(record.cpg_order_hash),
        "cpg_order_hash_annotation": record.cpg_order_hash_annotation,
        "fingerprint_class": record.fingerprint_class,
        "witness_blob_uri": record.witness_blob_uri,
        "slice_fingerprint": _opt_hex(record.slice_fingerprint),
        "rule_id": record.rule_id,
        "spec_id": record.spec_id,
        "detector_id": record.detector_id,
        "detector_engine": record.detector_engine,
        "sarif_hash": _opt_hex(record.sarif_hash),
        "origin": record.origin,
        "determinism_partition": record.determinism_partition,
        "claim_label": record.claim_label,
        "kms_key_arn": signed.kms_key_arn,
        "kms_key_version": signed.kms_key_version,
        "signature": signed.signature.hex(),
        "signature_alg": signed.signature_alg,
        "repartition_history": [
            {
                "id": str(child.record.id),
                "repartition_reason": child.record.repartition_reason,
                "repartition_oracle_id": _opt_uuid(child.record.repartition_oracle_id),
                "new_origin": child.record.origin,
            }
            for child in store.children(record_id)
        ],
    }
    return export


def append_repartition_event(
    *,
    parent_record_id: uuid.UUID,
    repartition_oracle_id: uuid.UUID,
    repartition_reason: str,
    store: ProvenanceStore,
    signer: KMSAsymmetricSigner,
    signature_alg: SignatureAlg = DEFAULT_SIGNATURE_ALG,
) -> SignedProvenanceRecord:
    """Append a signed ``record_type='repartition'`` row chained to its parent (§3.2).

    Constructs a NEW record with ``record_type='repartition'``,
    ``origin='oracle-passthrough'``, ``parent_record_id`` set, ``cpg_order_hash``
    NULL (not recomputed on re-partition, DOC-PROVENANCE §4.1), signs, and
    appends. The parent record is NEVER mutated — the store is append-only, so
    the parent's ``canonical_bytes`` are byte-identical before and after
    (AC-FND-03c / INV-1).

    Scope: this owns the ``provenance_records`` append only. The
    ``repartition_events`` INSERT and the ``findings.origin`` UPDATE are
    CMP-SNAP-04's responsibility (they call this within their transaction).
    """
    parent = store.get(parent_record_id)
    if parent is None:
        raise RepartitionWithoutParent(
            f"cannot append re-partition: no parent record {parent_record_id}"
        )
    base = parent.record

    repartition = ProvenanceRecord(
        id=uuid.uuid4(),
        parent_record_id=parent_record_id,
        record_type="repartition",
        scan_id=base.scan_id,
        finding_id=base.finding_id,
        org_id=base.org_id,
        codebase_id=base.codebase_id,
        commit_sha=base.commit_sha,
        scm_provider=base.scm_provider,
        snapshot_id=base.snapshot_id,
        snapshot_digest=base.snapshot_digest,
        precondition_status=base.precondition_status,
        S_version=base.S_version,
        env_digest=base.env_digest,
        # Not recomputed on re-partition (DOC-PROVENANCE §4.1).
        cpg_order_hash=None,
        cpg_order_hash_annotation=CPG_ORDER_HASH_ANNOTATION,
        fingerprint_class=None,
        witness_blob_uri=base.witness_blob_uri,
        slice_fingerprint=base.slice_fingerprint,
        rule_id=base.rule_id,
        spec_id=base.spec_id,
        detector_id=base.detector_id,
        detector_engine=base.detector_engine,
        sarif_hash=base.sarif_hash,
        # INV-1: a re-partition always flips TO oracle-passthrough.
        origin="oracle-passthrough",
        determinism_partition="oracle-passthrough",
        repartition_reason=repartition_reason,
        repartition_oracle_id=repartition_oracle_id,
        # Oracle-partition finding -> EMPIRICAL (DOC-PROVENANCE §5).
        claim_label="EMPIRICAL",
    )
    return sign_provenance(
        repartition,
        signer=signer,
        kms_key_arn=parent.kms_key_arn,
        signature_alg=signature_alg,
        store=store,
    )


def _verify_signature(
    *,
    public_key: bytes,
    message: bytes,
    signature: bytes,
    signature_alg: SignatureAlg,
) -> bool:
    """Verify an RSASSA-PSS signature with the DER-encoded public key.

    Uses ``cryptography`` (already a transitive dependency); the salt is the
    digest length, matching AWS KMS RSASSA_PSS semantics. Returns ``False`` on
    any verification failure (PSS is randomized — never re-sign-and-compare).
    """
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.serialization import load_der_public_key

    digest = hashes.SHA384() if signature_alg == "RSASSA_PSS_SHA_384" else hashes.SHA256()
    try:
        key = load_der_public_key(public_key)
    except (ValueError, TypeError):
        return False
    if not isinstance(key, rsa.RSAPublicKey):
        return False
    try:
        key.verify(
            signature,
            message,
            padding.PSS(mgf=padding.MGF1(digest), salt_length=padding.PSS.DIGEST_LENGTH),
            digest,
        )
    except InvalidSignature:
        return False
    return True


def _expect_bytes(resp: dict[str, object], key: str) -> bytes:
    value = resp.get(key)
    if not isinstance(value, (bytes, bytearray)):
        raise ProvenanceError(
            f"KMS response missing/invalid {key!r}: expected bytes, got {type(value).__name__}"
        )
    return bytes(value)


def _opt_uuid(value: uuid.UUID | None) -> str | None:
    return None if value is None else str(value)


def _opt_hex(value: bytes | None) -> str | None:
    return None if value is None else value.hex()


__all__ = [
    "CPG_ORDER_HASH_ANNOTATION",
    "DEFAULT_SIGNATURE_ALG",
    "ArtifactStore",
    "ClaimLabel",
    "InvariantViolation",
    "KMSAsymmetricSigner",
    "Origin",
    "ProvenanceError",
    "ProvenanceRecord",
    "ProvenanceStore",
    "RecordType",
    "RepartitionWithoutParent",
    "SignatureAlg",
    "SignedProvenanceRecord",
    "VerifyVerdict",
    "append_repartition_event",
    "canonical_record_bytes",
    "export_auditor_record",
    "sign_provenance",
    "verify_chain",
]
