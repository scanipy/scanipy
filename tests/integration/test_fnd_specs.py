"""FND-family integration specs — TST-AC-FND-03a (independent verifiability).

Spec-first TDD: production code for the Findings & Provenance subsystem does
not exist yet, so the spec below is a registered-but-dormant stub. It carries
an ``@pytest.mark.xfail(strict=False)`` so the suite collects and runs without
blocking; the body calls ``pytest.skip`` until CMP-FND-03 is DONE, at which
point the skip is removed and the stubbed assertion goes live.

Pattern mirrors ``tests/unit/test_dsl_proofs.py`` (the canonical convention).

This file holds the end-to-end verifiability spec: the signed provenance chain
must be re-verifiable from stored artefacts (DB row + S3 blobs + KMS public
key) WITHOUT re-running IFDS / Algorithm 5 / any detector (DOC-PROVENANCE §8.4,
DOC-CMP-FND-03 §3.1 ``verify_chain``).

Covers (from WBS §4.2):
  - TST-AC-FND-03a   [INTEGRATION] — record independently verifiable, no re-run
"""

import pytest


@pytest.mark.integration
@pytest.mark.xfail(
    reason="CMP-FND-03 (Signed provenance record) not yet implemented",
    strict=False,
)
def test_fnd_03a_record_independently_verifiable_without_rerun() -> None:
    """The signed record is independently verifiable from stored artefacts.

    Test id:        TST-AC-FND-03a
    Maps to AC:     AC-FND-03a — "The record is independently verifiable from
                    stored artifacts without re-running analysis."
    Kind tag:       [INTEGRATION]
    Inputs:         A persisted ``provenance_records`` row + its S3-resident
                    signed canonical bytes (``.json.sig``), the referenced SARIF
                    blob, witness blob, snapshot tarball (if cached), and the
                    KMS public key resolvable by ``(kms_key_arn,
                    kms_key_version)``. Two scenarios: (1) an untampered record;
                    (2) a record with one signed field mutated.
    Outputs:        ``verify_chain(record)`` ∈ {VERIFIED, TAMPERED, KEY_NOT_FOUND,
                    ARTIFACT_MISSING} (DOC-CMP-FND-03 §3.1).
    Pass criteria:  ``verify_chain`` returns ``"VERIFIED"`` for the untampered
                    record and ``"TAMPERED"`` for the mutated one, by: (a)
                    reconstructing canonical_bytes per DOC-PROVENANCE §3.2, (b)
                    fetching the KMS public key and verifying the RSASSA_PSS
                    signature, (c) recomputing ``sarif_hash`` and
                    ``snapshot_digest`` from the stored blobs and asserting
                    equality. The procedure invokes NO IFDS solver, NO Algorithm
                    5 run, NO detector (assert via call-graph / mock spies that
                    those modules are never entered).
    Frequency:      every CI run
    Hard gate?:     yes — component acceptance gate for CMP-FND-03 (AC-FND-03a).
    """
    # TODO: from services.scan.provenance import verify_chain when CMP-FND-03 is DONE
    # assert verify_chain(signed_record) == "VERIFIED"
    # mutate one signed field; assert verify_chain(mutated) == "TAMPERED"
    # assert solver/detectors never invoked during verification
    pytest.skip("CMP-FND-03 not implemented yet")
