"""Real signatures against test-only trust, distinct from operational grants."""

import os
from dataclasses import replace
from pathlib import PosixPath
from uuid import UUID

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from services.scan.accepted_inputs import codec as c
from services.scan.accepted_inputs import models as m
from services.scan.accepted_inputs import schemas as s
from services.scan.accepted_inputs import verifier_worker as worker
from services.scan.accepted_inputs import verify as v
from tests import accepted_input_fixtures as fixtures

pytestmark = pytest.mark.unit
material = fixtures.material
test_only_keys = fixtures.test_only_keys


def rotated(material, *, grant_changes=None, policy_changes=None, checkpoint_changes=None):
    request = material.request
    policy = c.decode_document(material.objects["current-policy"], s.POLICY)
    policy.update(
        event_id=fixtures.uid(100),
        revision=2,
        previous_policy_digest=c.domain_digest(s.POLICY, material.objects["current-policy"]),
    )
    if grant_changes:
        policy["grants"][0].update(grant_changes)
    policy.update(policy_changes or {})
    policy_raw = c.encode_document(policy, s.POLICY)
    checkpoint = c.decode_document(material.objects["admission-checkpoint"], s.ADMISSION)
    checkpoint.update(
        event_id=fixtures.uid(101),
        generation=2,
        previous_checkpoint_digest=request.admission.checkpoint_digest,
        policy_digest=c.domain_digest(s.POLICY, policy_raw),
        policy_revision=2,
        issued_at="2026-09-25T00:00:40Z",
    )
    checkpoint.update(checkpoint_changes or {})
    checkpoint_raw = c.encode_document(checkpoint, s.ADMISSION)
    admission = m.AdmissionExpectation(
        c.domain_digest(s.ADMISSION, checkpoint_raw),
        checkpoint["generation"],
        UUID(checkpoint["admission_epoch"]),
        checkpoint["policy_digest"],
        checkpoint["policy_revision"],
    )
    objects = dict(material.objects)
    objects.update(
        {
            "current-policy": policy_raw,
            "current-policy-signature": fixtures.sign(material.root, s.POLICY, policy_raw),
            "admission-checkpoint": checkpoint_raw,
            "admission-checkpoint-signature": fixtures.sign(
                material.root, s.ADMISSION, checkpoint_raw
            ),
        }
    )
    live = fixtures.frame(
        s.LIVE, {**{key: policy[key] for key in s.NAMESPACE}, **m.record_dict(admission)}, objects
    )
    authorization = dict(
        material.authorization,
        policy_event_id=policy["event_id"],
        policy_digest=checkpoint["policy_digest"],
        policy_revision=2,
        admission_event_id=checkpoint["event_id"],
        checkpoint_digest=admission.checkpoint_digest,
        checkpoint_generation=admission.checkpoint_generation,
        admission_epoch=str(admission.admission_epoch),
    )
    raw = c.encode_document(authorization, s.EXECUTION)
    digest = c.domain_digest(s.EXECUTION, raw)
    binding = replace(request.ledger.binding, authorization_digest=digest)
    ledger = replace(
        request.ledger,
        execution_authorization_digest=digest,
        binding=binding,
        policy_event_id=UUID(policy["event_id"]),
        admission_event_id=UUID(checkpoint["event_id"]),
    )
    return replace(
        request,
        admission=admission,
        ledger=ledger,
        live_authority_evidence=live,
        execution_authorization=raw,
    )


@pytest.mark.parametrize(
    "mode,expected_count", [("publication", 3), ("historical", 5), ("execution", 7)]
)
def test_real_crypto_three_separate_results_and_exact_work_count(
    material, monkeypatch, mode, expected_count
):
    request = material.request if mode == "execution" else getattr(material, mode)()
    signatures = []
    original = v._signature

    def count(*args, **kwargs):
        signatures.append(args[1])
        return original(*args, **kwargs)

    monkeypatch.setattr(v, "_signature", count)
    result = v.verify_request(request)
    assert len(signatures) == expected_count
    assert result.accepted_content_digest == request.expected_bundle.accepted_content_digest
    assert (result.permission_expires_at is not None) == (mode == "execution")
    assert (result.publication_receipt_digest is not None) == (mode != "publication")
    assert (result.current_policy_digest is not None) == (mode != "historical")
    assert result.verified_at == request.reference_time


def test_rotation_uses_new_event_without_rewriting_original_frame(material):
    request = rotated(material)
    original = material.request.authority_evidence
    checks = v.verify_request(request)
    assert request.authority_evidence == original
    assert checks.current_policy_revision == 2
    assert checks.checkpoint_generation == 2
    assert v.verify_request(material.historical()).current_policy_digest is None


def test_later_publication_keeps_carried_grants_original_validity(material):
    request = material.publication()
    objects = dict(material.objects)
    policy = c.decode_document(objects["current-policy"], s.POLICY)
    policy.update(
        event_id=fixtures.uid(100),
        revision=2,
        previous_policy_digest=request.admission.policy_digest,
        valid_from="2026-09-25T00:00:01Z",
    )
    policy_raw = c.encode_document(policy, s.POLICY)
    approval = c.decode_document(objects["approval-statement"], s.APPROVAL)
    approval["trust_policy_digest"] = c.domain_digest(s.POLICY, policy_raw)
    approval_raw = c.encode_document(approval, s.APPROVAL)
    checkpoint = c.decode_document(objects["admission-checkpoint"], s.ADMISSION)
    checkpoint.update(
        event_id=fixtures.uid(101),
        generation=2,
        previous_checkpoint_digest=request.admission.checkpoint_digest,
        policy_digest=approval["trust_policy_digest"],
        policy_revision=2,
        issued_at="2026-09-25T00:00:01Z",
    )
    checkpoint_raw = c.encode_document(checkpoint, s.ADMISSION)
    objects.update(
        {
            "current-policy": policy_raw,
            "current-policy-signature": fixtures.sign(material.root, s.POLICY, policy_raw),
            "approval-statement": approval_raw,
            "approval-signature": fixtures.sign(material.issuer, s.APPROVAL, approval_raw),
            "admission-checkpoint": checkpoint_raw,
            "admission-checkpoint-signature": fixtures.sign(
                material.root, s.ADMISSION, checkpoint_raw
            ),
        }
    )
    admission = m.AdmissionExpectation(
        c.domain_digest(s.ADMISSION, checkpoint_raw),
        2,
        request.admission.admission_epoch,
        approval["trust_policy_digest"],
        2,
    )
    proof = fixtures.frame(s.PUBLICATION_INPUT, m.record_dict(request.expected_bundle), objects)
    result = v.verify_request(replace(request, admission=admission, authority_evidence=proof))
    assert result.current_policy_revision == 2 and result.permission_expires_at is None


@pytest.mark.parametrize(
    "change",
    [
        {"status": "revoked", "status_changed_at": "2026-09-25T00:00:50Z"},
        {"status": "retired", "status_changed_at": "2026-09-25T00:00:20Z"},
        {"key_version": 2},
        {"issuer_actor_id": fixtures.uid(400)},
        {"spki_sha256": "0" * 64},
    ],
)
def test_current_grant_denial_does_not_erase_historical_verification(material, change):
    assert v.verify_request(material.historical()).publication_receipt_digest is not None
    with pytest.raises(s.VerificationError, match="grant-denied"):
        v.verify_request(rotated(material, grant_changes=change))


def test_retired_key_allows_only_strictly_earlier_published_bytes(material):
    request = rotated(
        material, grant_changes={"status": "retired", "status_changed_at": "2026-09-25T00:00:50Z"}
    )
    assert v.verify_request(request).permission_expires_at is not None


@pytest.mark.parametrize(
    "change",
    [
        {"action": "block"},
        {"expires_at": "2026-09-25T00:01:20Z"},
        {"deployment_id": fixtures.uid(600)},
        {"administrator_actor_id": fixtures.uid(601)},
    ],
)
def test_root_valid_current_checkpoint_can_still_deny_use(material, change):
    with pytest.raises(s.VerificationError, match="checkpoint-denied"):
        v.verify_request(rotated(material, checkpoint_changes=change))


def test_minimum_expiry_preserves_microseconds_and_short_checkpoint(material):
    request = rotated(material, checkpoint_changes={"expires_at": "2026-09-25T00:03:00Z"})
    assert v.verify_request(request).permission_expires_at == "2026-09-25T00:03:00.000000Z"
    assert v.verify_request(material.request).permission_expires_at == "2026-09-25T00:09:00.000002Z"


@pytest.mark.parametrize(
    "field",
    [
        "checkpoint_digest",
        "policy_digest",
        "checkpoint_generation",
        "policy_revision",
        "admission_epoch",
    ],
)
def test_independent_head_expectation_rejects_root_valid_stale_database(material, field):
    admission = material.request.admission
    changes = {
        field: "f" * 64
        if field.endswith("digest")
        else UUID(fixtures.uid(800))
        if field.endswith("epoch")
        else 2
    }
    with pytest.raises(s.VerificationError, match="checkpoint-denied"):
        v.verify_request(replace(material.request, admission=replace(admission, **changes)))


@pytest.mark.parametrize(
    "field",
    ["publication_receipt_digest", "request_binding_digest", "execution_authorization_digest"],
)
def test_caller_hashed_receipt_is_not_authentic_ledger_read(material, field):
    ledger = material.request.ledger
    if field == "execution_authorization_digest":
        ledger = replace(
            ledger,
            binding=replace(ledger.binding, authorization_digest="f" * 64),
            execution_authorization_digest="f" * 64,
        )
    else:
        ledger = replace(ledger, **{field: "f" * 64})
    with pytest.raises(s.VerificationError, match="ledger-mismatch"):
        v.verify_request(replace(material.request, ledger=ledger))


@pytest.mark.parametrize(
    "field,value",
    [
        ("fencing_token", 2),
        ("work_revision", 5),
        ("detector_run_id", fixtures.uid(900)),
        ("capture_lease_id", fixtures.uid(901)),
        ("request_id", fixtures.uid(902)),
        ("lease_expires_at", "2026-09-25T00:10:00.000002Z"),
    ],
)
def test_exact_record_and_live_binding_must_agree(material, field, value):
    binding = material.request.ledger.binding
    if field.endswith("_id"):
        value = UUID(value)
    changed = replace(binding, **{field: value})
    ledger = replace(material.request.ledger, binding=changed)
    with pytest.raises(s.VerificationError, match="fence-stale"):
        v.verify_request(replace(material.request, ledger=ledger))


@pytest.mark.parametrize(
    "wrong",
    [
        "signature",
        "wrong-key",
        "salt",
        "mgf",
        "trailing-der",
        "private-der",
        "pem",
        "short-signature",
    ],
)
def test_actual_crypto_rejects_signed_looking_or_wrong_profile(material, wrong):
    key = material.issuer
    public = fixtures.spki(key)
    raw = material.objects["approval-statement"]
    signature = material.objects["approval-signature"]
    if wrong == "signature":
        signature = bytes([signature[0] ^ 1]) + signature[1:]
    elif wrong == "wrong-key":
        public = fixtures.spki(material.root)
    elif wrong == "salt":
        signature = key.sign(
            s.APPROVAL.encode() + b"\n" + raw,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=0),
            hashes.SHA256(),
        )
    elif wrong == "mgf":
        signature = key.sign(
            s.APPROVAL.encode() + b"\n" + raw,
            padding.PSS(mgf=padding.MGF1(hashes.SHA512()), salt_length=32),
            hashes.SHA256(),
        )
    elif wrong == "trailing-der":
        public += b"x"
    elif wrong == "private-der":
        public = key.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    elif wrong == "pem":
        public = key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    elif wrong == "short-signature":
        signature = signature[:-1]
    with pytest.raises(s.VerificationError):
        loaded = v._key(public, c.raw_digest(public))
        v._signature(loaded, s.APPROVAL, raw, signature)


@pytest.mark.parametrize("bits,exponent", [(2048, 65537), (3072, 3)])
def test_wrong_rsa_size_or_exponent_rejected(bits, exponent):
    key = rsa.generate_private_key(public_exponent=exponent, key_size=bits)
    public = fixtures.spki(key)
    with pytest.raises(s.VerificationError, match="signature-invalid"):
        v._key(public, c.raw_digest(public))


def test_key_limit_precedes_asn1_parsing(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("oversized DER must fail before parser")

    monkeypatch.setattr(v.serialization, "load_der_public_key", forbidden)
    with pytest.raises(s.VerificationError):
        v._key(b"x" * 4097, "0" * 64)


def test_signature_domain_cannot_be_reused(material):
    public = fixtures.spki(material.issuer)
    with pytest.raises(s.VerificationError, match="signature-invalid"):
        v._signature(
            v._key(public, c.raw_digest(public)),
            s.POLICY,
            material.objects["approval-statement"],
            material.objects["approval-signature"],
        )


def test_production_never_falls_back_to_diagnostic(material, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("missing production controller must not launch diagnostic worker")

    monkeypatch.setattr(v, "_run_diagnostic_verifier", forbidden)
    with pytest.raises(s.VerificationError, match="runtime-unsupported"):
        v.run_isolated_verifier(material.request, profile=None)


def diagnostic_reader(material, events):
    """Test-only adapter protocol fixture; not a live grant or installation."""
    request = material.request

    class Reader:
        runtime_profile = m.VerifierRuntimeProfile(
            PosixPath("/diagnostic/metadata/profile.json"),
            "a" * 64,
            m.VerifierRuntimeDocument(
                "cpython",
                "3.11.16",
                PosixPath("/diagnostic/bin/python"),
                "b" * 64,
                PosixPath("/diagnostic/application/worker.py"),
                "c" * 64,
                PosixPath("/diagnostic/application"),
                "d" * 64,
                (PosixPath("/diagnostic/stdlib"),),
                (PosixPath("/diagnostic/dependencies"),),
                "e" * 64,
                request.verifier_artifact_digest,
                PosixPath("/diagnostic/work"),
            ),
        )
        context = m.ExecutionVerificationContext(
            request.installed_trust,
            request.admission,
            request.ledger,
            request.live_authority_evidence,
            request.reference_time,
        )

        def read_execution_authority(self, expected):
            events.append("read")
            assert expected == request.ledger.binding
            return self.context

        def recheck_execution_authority(self, expected, context):
            events.append("recheck")
            assert expected == request.ledger.binding and context is self.context

    return Reader()


def resolved_fixture(material):
    request = material.request
    return m.ResolvedQualifiedRule(
        request.selected_rule,
        request.bundle,
        request.authority_evidence,
        request.execution_authorization,
        request.ledger.binding,
    )


def test_execution_facade_requires_fresh_read_and_post_verification_recheck(material, monkeypatch):
    events = []
    reader = diagnostic_reader(material, events)
    resolved = resolved_fixture(material)

    def diagnostic_verify(request, *, profile):
        # Deliberately injected test seam only; the real public launcher refuses.
        events.append("verify")
        assert profile is reader.runtime_profile
        return v.verify_request(request)

    monkeypatch.setattr(v, "run_isolated_verifier", diagnostic_verify)
    first = v.verify_resolved_qualified_rule(resolved, expected=resolved.binding, authority=reader)
    second = v.verify_resolved_qualified_rule(resolved, expected=resolved.binding, authority=reader)
    assert type(first) is m.VerifiedQualifiedRule and type(second) is m.VerifiedQualifiedRule
    assert events == ["read", "verify", "recheck"] * 2


@pytest.mark.parametrize("barrier", ["before-read", "read", "context-fence", "verify", "recheck"])
def test_execution_facade_never_exposes_value_across_failed_authority_barrier(
    material, monkeypatch, barrier
):
    events = []
    reader = diagnostic_reader(material, events)
    resolved = resolved_fixture(material)
    expected = resolved.binding
    denied = s.VerificationError("fence-stale")

    def refuse(*args, **kwargs):
        raise denied

    if barrier == "before-read":
        expected = replace(expected, fencing_token=expected.fencing_token + 1)
    elif barrier == "read":
        reader.read_execution_authority = refuse
    elif barrier == "context-fence":
        reader.context = replace(
            reader.context,
            ledger=replace(
                reader.context.ledger,
                binding=replace(expected, fencing_token=expected.fencing_token + 1),
            ),
        )
    elif barrier == "recheck":
        reader.recheck_execution_authority = refuse

    def diagnostic_verify(request, *, profile):
        events.append("verify")
        if barrier == "verify":
            raise denied
        return v.verify_request(request)

    monkeypatch.setattr(v, "run_isolated_verifier", diagnostic_verify)
    with pytest.raises(s.VerificationError, match="fence-stale"):
        v.verify_resolved_qualified_rule(resolved, expected=expected, authority=reader)
    assert ("verify" in events) == (barrier in ("verify", "recheck"))
    assert "recheck" not in events


@pytest.mark.parametrize("entry", ["constructor", "encoder", "header", "diagnostic"])
def test_operation_uuid_poison_cannot_format_encode_read_or_launch(material, monkeypatch, entry):
    class PoisonInteger:
        def __format__(self, _spec):
            raise AssertionError("UUID formatting must never reach a caller object")

    profile = diagnostic_reader(material, []).runtime_profile
    object.__setattr__(material.request.operation_id, "int", PoisonInteger())

    def forbidden(*args, **kwargs):
        raise AssertionError("invalid operation UUID must fail before serialization or filesystem")

    monkeypatch.setattr(c.json, "dumps", forbidden)
    monkeypatch.setattr(worker, "_read_file", forbidden)
    monkeypatch.setattr("tools.worker.bounded_process.run_bounded_process", forbidden)
    with pytest.raises(s.VerificationError):
        if entry == "constructor":
            replace(material.request)
        elif entry == "encoder":
            c.encode_request(material.request)
        elif entry == "header":
            c._request_header(material.request)
        else:
            v._run_diagnostic_verifier(material.request, profile=profile)


def test_operation_uuid_retains_fresh_primitive_snapshot(material):
    original = material.request.operation_id
    request = replace(material.request)
    assert request.operation_id == original and request.operation_id is not original
    object.__setattr__(original, "int", -1)
    assert c.decode_request(c.encode_request(request)).operation_id == request.operation_id


def test_directory_close_failure_never_recloses_reused_number_or_leaks_child(tmp_path, monkeypatch):
    sentinel = tmp_path / "sentinel"
    sentinel.write_bytes(b"private diagnostic file")
    original_open, original_close = os.open, os.close
    opened, closed, retained = [], [], []
    failure = OSError("injected close failure after release")

    def observe_open(*args, **kwargs):
        descriptor = original_open(*args, **kwargs)
        opened.append(descriptor)
        return descriptor

    def fail_first_close(descriptor):
        original_close(descriptor)
        closed.append(descriptor)
        if len(closed) == 1:
            replacement = original_open(sentinel, os.O_RDONLY)
            retained.append(replacement)
            assert replacement == descriptor
            raise failure

    monkeypatch.setattr(worker.os, "open", observe_open)
    monkeypatch.setattr(worker.os, "close", fail_first_close)
    try:
        with pytest.raises(OSError) as caught:
            worker._directory(PosixPath(tmp_path), private=True)
        assert caught.value is failure
        assert len(opened) == 2 and closed == opened
        assert os.fstat(retained[0]).st_size == len(b"private diagnostic file")
    finally:
        for descriptor in retained:
            original_close(descriptor)


@pytest.mark.parametrize("failure", ["read", "read-interrupt", "cleanup-only"])
def test_file_cleanup_preserves_primary_cause_and_final_failure(tmp_path, monkeypatch, failure):
    path = tmp_path / "input"
    path.write_bytes(b"exact bytes")
    path.chmod(0o600)
    original_open, original_close, original_read = os.open, os.close, os.read
    descriptor = None
    closed = []
    primary = KeyboardInterrupt() if failure == "read-interrupt" else OSError("read failure")
    prior = ValueError("earlier cause")
    primary.__cause__ = prior
    cleanup = OSError("close failure after release")

    def observe_open(target, *args, **kwargs):
        nonlocal descriptor
        result = original_open(target, *args, **kwargs)
        if target == path:
            descriptor = result
        return result

    def fail_read(number, size):
        if number == descriptor and failure != "cleanup-only":
            raise primary
        return original_read(number, size)

    def fail_close(number):
        original_close(number)
        if number == descriptor:
            closed.append(number)
            raise cleanup

    monkeypatch.setattr(worker.os, "open", observe_open)
    monkeypatch.setattr(worker.os, "read", fail_read)
    monkeypatch.setattr(worker.os, "close", fail_close)
    with pytest.raises(BaseException) as caught:
        worker._read_file(PosixPath(path), 64, private=True)
    assert closed == [descriptor]
    if failure == "cleanup-only":
        assert caught.value is cleanup
    else:
        assert caught.value is primary
        assert caught.value.__cause__.exceptions == (prior, cleanup)


def test_directory_final_close_failure_refuses_success(tmp_path, monkeypatch):
    original_close = os.close
    primary = OSError("last directory close")
    target_identity = (tmp_path.stat().st_dev, tmp_path.stat().st_ino)
    failed = []

    def fail_target(number):
        metadata = os.fstat(number)
        original_close(number)
        if (metadata.st_dev, metadata.st_ino) == target_identity:
            failed.append(number)
            raise primary

    monkeypatch.setattr(worker.os, "close", fail_target)
    with pytest.raises(OSError) as caught:
        worker._directory(PosixPath(tmp_path), private=True)
    assert caught.value is primary and len(failed) == 1
