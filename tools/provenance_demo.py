"""End-to-end demonstration harness for the CMP-FND-03 signed provenance chain.

The chain itself — canonical record bytes, the pre-sign INV-1/INV-5 guards, the
RSASSA-PSS signature, the auditor export and the verifier that reconstructs the
canonical bytes from the stored row — is implemented in
``services/scan/provenance/__init__.py`` and is exercised by the FND-03 specs.
What did not exist is a single place that runs the whole cycle over one
finding: **sign -> auditor export -> verify -> tamper -> verify again**.
This module is that glue and nothing more.

It re-implements no crypto, no hashing and no comparison logic. Every step is a
call into the shipped API:

===========================  ==========================================
step                         shipped callable
===========================  ==========================================
sign (+ append to store)     ``services.scan.provenance.sign_provenance``
auditor export               ``services.scan.provenance.export_auditor_record``
verify                       ``services.scan.provenance.verify_chain``
tamper                       ``dataclasses.replace`` on the frozen record
===========================  ==========================================

The verdicts reported are the verifier's own
``VERIFIED`` / ``TAMPERED`` / ``KEY_NOT_FOUND`` / ``ARTIFACT_MISSING``
literals; this module never decides a verdict itself.

**Signing key — honesty note.** The default signer is
:class:`services.scan.software_kms_signer.SoftwareKMSSigner`: a **local
software RSA key held in this process's memory**, generated at construction
time. It is a non-production stand-in (it refuses to construct when
``ENV``/``SCANIPY_ENV`` is ``prod``) and is explicitly **not** an HSM-backed or
KMS-backed key — a demo run therefore demonstrates that the chain's signature
and tamper-detection mechanics work, not that a key was protected by any
hardware or managed service. Under the Docker/OSS pivot (CLAR-DEPLOY-25) a
local software key provider is the intended substrate; ``kms_key_arn`` keeps
its shipped parameter name because that is the ``sign_provenance`` API, but the
value passed here is a local key label, not an AWS ARN.

**No fabricated provenance.** Every claim-bearing link of the chain
(``commit_sha``, ``snapshot_digest``, ``S_version``, ``env_digest``,
``cpg_order_hash`` + ``fingerprint_class``, witness, rule/spec id,
``sarif_hash``, ``origin``, ``claim_label``) is a required input of
:func:`build_chain_record`. This module invents none of them and supplies no
defaults for any of them. Only the record/row identity UUIDs default (to a
fresh ``uuid4`` per demo run), mirroring how ``append_repartition_event``
mints its own record ``id``. ``origin`` in particular is an input: a finding
produced by an oracle engine is ``oracle-passthrough`` and is **not** covered
by the determinism theorem (``.claude/rules/05-determinism.md``); only the
caller knows which partition its finding came from.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import uuid
from dataclasses import dataclass
from typing import Any

from services.scan.provenance import (
    CPG_ORDER_HASH_ANNOTATION,
    ArtifactStore,
    ClaimLabel,
    DetectorEngine,
    FingerprintClass,
    KMSAsymmetricSigner,
    Origin,
    PreconditionStatus,
    ProvenanceRecord,
    ProvenanceStore,
    SemVer,
    Sha256,
    Sha256Hex,
    SignedProvenanceRecord,
    VerifyVerdict,
    export_auditor_record,
    sign_provenance,
    verify_chain,
)
from services.scan.software_kms_signer import SoftwareKMSSigner

__all__ = [
    "LOCAL_SOFTWARE_KEY_ID",
    "DemoOutcome",
    "DemoProvenanceStore",
    "build_chain_record",
    "run_demo",
    "tamper_record",
]

# Key label handed to ``sign_provenance(kms_key_arn=...)``. NOT an AWS KMS ARN:
# the default signer is an in-process software RSA key (see module docstring).
LOCAL_SOFTWARE_KEY_ID = "local-software-key/provenance-demo"


class DemoProvenanceStore:
    """Append-only in-memory :class:`ProvenanceStore` for a demo run.

    Dict-keyed by record ``id`` with no update/delete method, modelling the
    no-UPDATE/DELETE grants on ``provenance_records``. The test-suite
    counterpart is ``tests/fnd03_fakes.py::InMemoryProvenanceStore``; this one
    exists so the demo needs no import out of ``tests/``. Swap in any object
    satisfying the ``ProvenanceStore`` protocol (e.g. a SQL-backed store) via
    :func:`run_demo`'s ``store`` argument.
    """

    def __init__(self) -> None:
        self._rows: dict[uuid.UUID, SignedProvenanceRecord] = {}

    def append(self, signed: SignedProvenanceRecord) -> None:
        rid = signed.record.id
        if rid in self._rows:
            raise ValueError(f"append-only store: duplicate provenance record id {rid}")
        self._rows[rid] = signed

    def get(self, record_id: uuid.UUID) -> SignedProvenanceRecord | None:
        return self._rows.get(record_id)

    def children(self, parent_record_id: uuid.UUID) -> list[SignedProvenanceRecord]:
        return [s for s in self._rows.values() if s.record.parent_record_id == parent_record_id]


@dataclass(frozen=True)
class DemoOutcome:
    """What one sign -> export -> verify -> tamper -> verify cycle produced."""

    signed: SignedProvenanceRecord
    export: dict[str, object]
    verdict: VerifyVerdict
    tampered_field: str
    tampered_verdict: VerifyVerdict


def build_chain_record(
    *,
    # Link 1 — source commit
    commit_sha: str,
    scm_provider: str,
    # Link 2 — snapshot digest
    snapshot_digest: str,
    precondition_status: PreconditionStatus,
    # Links 3 + 4 — INV-2
    s_version: str,
    env_digest: str,
    # Link 5 — cpg_order_hash + INV-5 (both None for a finding with no CPG order)
    cpg_order_hash: bytes | None,
    fingerprint_class: FingerprintClass | None,
    # Link 6 — taint witness
    witness_blob_uri: str | None,
    slice_fingerprint: bytes | None,
    # Link 7 — rule / spec id
    rule_id: str | None,
    spec_id: str | None,
    detector_id: str | None,
    detector_engine: DetectorEngine | None,
    # Link 8 — SARIF hash (raw sha256 digest of the SARIF log, 32 bytes)
    sarif_hash: bytes | None,
    # Link 9 — per-finding origin (INV-1) + honest-labelling
    origin: Origin,
    claim_label: ClaimLabel,
    # Identity / row keys — demo-run identities unless supplied
    org_id: uuid.UUID | None = None,
    codebase_id: uuid.UUID | None = None,
    scan_id: uuid.UUID | None = None,
    finding_id: uuid.UUID | None = None,
    snapshot_id: uuid.UUID | None = None,
) -> ProvenanceRecord:
    """Assemble a ``record_type='chain'`` :class:`ProvenanceRecord` from real inputs.

    Every claim-bearing link is a required keyword argument: this function has
    no notion of a "plausible" value for any of them and will not invent one.
    ``origin`` must be the finding's true partition — an oracle-engine finding
    is ``oracle-passthrough``.

    The INV-5 annotation is deliberately not a parameter: it is the pinned
    ``analysis.ordering.CPG_ORDER_HASH_ANNOTATION`` literal, which
    ``sign_provenance`` re-checks before signing.

    The UUID arguments identify the row and its scope. They default to a fresh
    ``uuid4`` so a demo run needs no database; pass the real ids when
    demonstrating over a persisted finding.
    """
    return ProvenanceRecord(
        id=uuid.uuid4(),
        parent_record_id=None,
        record_type="chain",
        scan_id=scan_id or uuid.uuid4(),
        finding_id=finding_id or uuid.uuid4(),
        org_id=org_id or uuid.uuid4(),
        codebase_id=codebase_id or uuid.uuid4(),
        commit_sha=commit_sha,
        scm_provider=scm_provider,
        snapshot_id=snapshot_id or uuid.uuid4(),
        snapshot_digest=Sha256Hex(snapshot_digest),
        precondition_status=precondition_status,
        S_version=SemVer(s_version),
        env_digest=Sha256Hex(env_digest),
        cpg_order_hash=None if cpg_order_hash is None else Sha256(cpg_order_hash),
        cpg_order_hash_annotation=CPG_ORDER_HASH_ANNOTATION,
        fingerprint_class=fingerprint_class,
        witness_blob_uri=witness_blob_uri,
        slice_fingerprint=None if slice_fingerprint is None else Sha256(slice_fingerprint),
        rule_id=rule_id,
        spec_id=spec_id,
        detector_id=detector_id,
        detector_engine=detector_engine,
        sarif_hash=None if sarif_hash is None else Sha256(sarif_hash),
        origin=origin,
        determinism_partition=origin,
        repartition_reason=None,
        repartition_oracle_id=None,
        claim_label=claim_label,
    )


def tamper_record(
    signed: SignedProvenanceRecord,
    *,
    field: str,
    value: object,
) -> SignedProvenanceRecord:
    """Return ``signed`` with one record field rewritten, signature untouched.

    Models an attacker (or a corrupted row) editing the persisted record after
    signing. The signature, ``canonical_bytes``, key id and algorithm are
    carried over verbatim — ``verify_chain`` recomputes the canonical bytes
    from the *record*, so the stale signature no longer covers them.
    """
    names = {f.name for f in dataclasses.fields(signed.record)}
    if field not in names:
        raise ValueError(f"{field!r} is not a ProvenanceRecord field")
    if getattr(signed.record, field) == value:
        raise ValueError(f"tamper value for {field!r} equals the original — nothing would change")
    # The field name is chosen at runtime, so the override map is dynamically
    # keyed (``Any``-valued): a tamper deliberately writes a value the field's
    # Literal type would reject, which is the whole point of the exercise.
    override: dict[str, Any] = {field: value}
    return dataclasses.replace(signed, record=dataclasses.replace(signed.record, **override))


def run_demo(
    record: ProvenanceRecord,
    *,
    signer: KMSAsymmetricSigner | None = None,
    store: ProvenanceStore | None = None,
    artifacts: ArtifactStore | None = None,
    kms_key_arn: str = LOCAL_SOFTWARE_KEY_ID,
    tamper_field: str = "commit_sha",
    tamper_value: object = "0" * 40,
) -> DemoOutcome:
    """Run the full cycle over ``record`` and report the verifier's verdicts.

    1. :func:`sign_provenance` — signs and appends to the append-only store.
    2. :func:`export_auditor_record` — the customer/auditor-facing export.
    3. :func:`verify_chain` — expected ``VERIFIED``.
    4. :func:`tamper_record` on ``tamper_field``, then :func:`verify_chain`
       again on the mutated row — expected ``TAMPERED``.

    The tampered record is intentionally not appended to the store (it reuses
    the parent's id, and the store is append-only).

    ``signer`` defaults to a fresh :class:`SoftwareKMSSigner` — a **local
    software RSA key**, non-production, not KMS/HSM-backed. ``artifacts`` is
    passed straight through to the verifier; when it is ``None`` the verifier
    checks the signature only and does not recompute artefact digests.
    """
    active_signer: KMSAsymmetricSigner = SoftwareKMSSigner() if signer is None else signer
    active_store: ProvenanceStore = DemoProvenanceStore() if store is None else store

    signed = sign_provenance(
        record,
        signer=active_signer,
        kms_key_arn=kms_key_arn,
        store=active_store,
    )
    export = export_auditor_record(signed.record.id, store=active_store)
    verdict = verify_chain(signed, signer=active_signer, artifacts=artifacts, store=active_store)

    tampered = tamper_record(signed, field=tamper_field, value=tamper_value)
    tampered_verdict = verify_chain(
        tampered, signer=active_signer, artifacts=artifacts, store=active_store
    )

    return DemoOutcome(
        signed=signed,
        export=export,
        verdict=verdict,
        tampered_field=tamper_field,
        tampered_verdict=tampered_verdict,
    )


def _sha256_bytes(value: str | None, *, flag: str) -> bytes | None:
    """Decode a 64-char hex digest into 32 raw bytes (``None`` passes through)."""
    if value is None:
        return None
    try:
        raw = bytes.fromhex(value)
    except ValueError as exc:
        raise SystemExit(f"{flag}: not valid hex: {exc}") from exc
    if len(raw) != 32:
        raise SystemExit(f"{flag}: expected a 32-byte (64 hex char) sha256, got {len(raw)} bytes")
    return raw


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="provenance-demo",
        description=(
            "Sign, export, verify and tamper-test one CMP-FND-03 provenance record "
            "using a LOCAL SOFTWARE key (non-production stand-in, not KMS/HSM-backed). "
            "Every provenance value is supplied by you; none are invented."
        ),
    )
    add = parser.add_argument
    add("--commit-sha", required=True, help="link 1: source commit sha")
    add("--scm-provider", required=True, help="link 1: e.g. github")
    add("--snapshot-digest", required=True, help="link 2: snapshot digest string")
    add(
        "--precondition-status",
        required=True,
        choices=["closed-world", "degraded", "full-reparse"],
        help="link 2: CW-DETECT verdict for the snapshot",
    )
    add("--s-version", required=True, help="link 3: pinned accepted spec-set version (INV-2)")
    add("--env-digest", required=True, help="link 4: pinned analysis-environment digest (INV-2)")
    add("--cpg-order-hash", help="link 5: 64-hex sha256; omit when the record carries none")
    add("--fingerprint-class", choices=["strong", "weak"], help="link 5: INV-5 canonicality class")
    add("--witness-blob-uri", help="link 6: taint-witness blob uri")
    add("--slice-fingerprint", help="link 6: 64-hex sha256 slice fingerprint")
    add("--rule-id", help="link 7: rule id")
    add("--spec-id", help="link 7: spec id")
    add("--detector-id", help="link 7: detector id")
    add(
        "--detector-engine",
        choices=["ifds", "ide", "semgrep", "cpg-query", "external"],
        help="link 7: engine that produced the finding",
    )
    add("--sarif-hash", help="link 8: 64-hex sha256 of the SARIF log")
    add(
        "--origin",
        required=True,
        choices=["deterministic-core", "oracle-passthrough"],
        help="link 9 (INV-1): the finding's TRUE partition — oracle engines are oracle-passthrough",
    )
    add(
        "--claim-label",
        required=True,
        choices=["CONDITIONAL_THEOREM", "EMPIRICAL", "STAGED", "UNCONDITIONAL"],
        help="honest-labelling class for this record (DOC-PROVENANCE §5)",
    )
    add("--tamper-field", default="commit_sha", help="record field the tamper step rewrites")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: prints the export plus both verdicts as JSON."""
    args = _build_parser().parse_args(argv)

    record = build_chain_record(
        commit_sha=args.commit_sha,
        scm_provider=args.scm_provider,
        snapshot_digest=args.snapshot_digest,
        precondition_status=args.precondition_status,
        s_version=args.s_version,
        env_digest=args.env_digest,
        cpg_order_hash=_sha256_bytes(args.cpg_order_hash, flag="--cpg-order-hash"),
        fingerprint_class=args.fingerprint_class,
        witness_blob_uri=args.witness_blob_uri,
        slice_fingerprint=_sha256_bytes(args.slice_fingerprint, flag="--slice-fingerprint"),
        rule_id=args.rule_id,
        spec_id=args.spec_id,
        detector_id=args.detector_id,
        detector_engine=args.detector_engine,
        sarif_hash=_sha256_bytes(args.sarif_hash, flag="--sarif-hash"),
        origin=args.origin,
        claim_label=args.claim_label,
    )
    outcome = run_demo(record, tamper_field=args.tamper_field)

    print(
        json.dumps(
            {
                "signing_key": {
                    "id": outcome.signed.kms_key_arn,
                    "version": outcome.signed.kms_key_version,
                    "alg": outcome.signed.signature_alg,
                    "kind": "local software RSA key (non-production stand-in, not KMS/HSM-backed)",
                },
                "auditor_export": outcome.export,
                "verify_verdict": outcome.verdict,
                "tampered_field": outcome.tampered_field,
                "verify_verdict_after_tamper": outcome.tampered_verdict,
            },
            indent=2,
            sort_keys=False,
        )
    )
    return 0 if (outcome.verdict, outcome.tampered_verdict) == ("VERIFIED", "TAMPERED") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
