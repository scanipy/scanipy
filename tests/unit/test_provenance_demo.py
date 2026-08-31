"""Unit tests for ``tools/provenance_demo.py`` — the FND-03 chain demo harness.

Hermetic: no database, no network, no AWS. The signer is the in-process
:class:`SoftwareKMSSigner` (a local software RSA key, non-production
stand-in), and the store is the module's in-memory append-only
``DemoProvenanceStore``.

Scope: these tests assert that the *harness* drives the shipped chain end to
end and reports the verifier's own verdicts. The chain's internals (canonical
bytes, the INV-1/INV-5 pre-sign guards, re-partition linkage, artefact digest
recomputation) are already covered by the FND-03 specs in
``tests/unit/test_fnd_specs.py`` and ``tests/integration/test_fnd_specs.py``
and are not re-tested here.

The demo record models an **oracle-passthrough** finding (``semgrep`` engine):
that partition is not covered by the determinism theorem — only the signature
chain is being demonstrated.
"""

from __future__ import annotations

import json

import pytest

from analysis.ordering import CPG_ORDER_HASH_ANNOTATION
from services.scan.provenance import ProvenanceRecord
from tools.provenance_demo import build_chain_record, main, run_demo, tamper_record

# Obviously-synthetic test inputs. They are test fixture data, not claims about
# any real scan; the demo module itself supplies no defaults for these fields.
_COMMIT_SHA = "1" * 40
_ENV_DIGEST = "sha256:" + ("2" * 64)
_SNAPSHOT_DIGEST = "sha256:" + ("3" * 64)
_SARIF_HASH_HEX = "4" * 64


def _oracle_record() -> ProvenanceRecord:
    return build_chain_record(
        commit_sha=_COMMIT_SHA,
        scm_provider="github",
        snapshot_digest=_SNAPSHOT_DIGEST,
        precondition_status="full-reparse",
        s_version="1.2.3",
        env_digest=_ENV_DIGEST,
        # An oracle finding carries no CPG canonical order in this demo.
        cpg_order_hash=None,
        fingerprint_class=None,
        witness_blob_uri=None,
        slice_fingerprint=None,
        rule_id="python.lang.security.demo-rule",
        spec_id=None,
        detector_id="semgrep-oracle",
        detector_engine="semgrep",
        sarif_hash=bytes.fromhex(_SARIF_HASH_HEX),
        origin="oracle-passthrough",
        claim_label="EMPIRICAL",
    )


@pytest.mark.unit
def test_demo_happy_path_signs_exports_and_verifies() -> None:
    """sign -> export -> verify yields the shipped verifier's ``VERIFIED`` verdict."""
    outcome = run_demo(_oracle_record())

    assert outcome.verdict == "VERIFIED"
    # The signature is real bytes over the canonical record, not a placeholder.
    assert outcome.signed.signature_alg == "RSASSA_PSS_SHA_256"
    assert len(outcome.signed.signature) > 0

    export = outcome.export
    # INV-1 / INV-2 / INV-5 threading survives into the auditor export.
    assert export["origin"] == "oracle-passthrough"
    assert export["S_version"] == "1.2.3"
    assert export["env_digest"] == _ENV_DIGEST
    assert export["cpg_order_hash_annotation"] == CPG_ORDER_HASH_ANNOTATION


@pytest.mark.unit
def test_demo_tamper_path_is_detected_by_the_shipped_verifier() -> None:
    """Rewriting one persisted field flips the verifier's verdict to ``TAMPERED``."""
    outcome = run_demo(
        _oracle_record(),
        tamper_field="env_digest",
        tamper_value="sha256:" + ("9" * 64),
    )

    assert outcome.verdict == "VERIFIED"
    assert outcome.tampered_field == "env_digest"
    assert outcome.tampered_verdict == "TAMPERED"


@pytest.mark.unit
def test_tamper_record_rejects_a_no_op_edit() -> None:
    """A tamper that changes nothing would make the demo vacuous — refuse it."""
    outcome = run_demo(_oracle_record())

    with pytest.raises(ValueError, match="equals the original"):
        tamper_record(outcome.signed, field="commit_sha", value=_COMMIT_SHA)

    with pytest.raises(ValueError, match="not a ProvenanceRecord field"):
        tamper_record(outcome.signed, field="not_a_field", value="x")


@pytest.mark.unit
def test_cli_runs_the_full_cycle_and_reports_both_verdicts(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI entry point exits 0 only when VERIFIED then TAMPERED both hold."""
    exit_code = main(
        [
            "--commit-sha",
            _COMMIT_SHA,
            "--scm-provider",
            "github",
            "--snapshot-digest",
            _SNAPSHOT_DIGEST,
            "--precondition-status",
            "full-reparse",
            "--s-version",
            "1.2.3",
            "--env-digest",
            _ENV_DIGEST,
            "--sarif-hash",
            _SARIF_HASH_HEX,
            "--detector-engine",
            "semgrep",
            "--detector-id",
            "semgrep-oracle",
            "--origin",
            "oracle-passthrough",
            "--claim-label",
            "EMPIRICAL",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["verify_verdict"] == "VERIFIED"
    assert payload["verify_verdict_after_tamper"] == "TAMPERED"
    assert payload["auditor_export"]["origin"] == "oracle-passthrough"
    assert "not KMS/HSM-backed" in payload["signing_key"]["kind"]
