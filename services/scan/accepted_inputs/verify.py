"""Fixed-profile cryptography and the mandatory isolated execution verifier.

Pure verification is relative to explicit trusted inputs. It neither installs
trust nor proves a supplied receipt came from the durable authority ledger.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import PosixPath
from tempfile import TemporaryDirectory
from typing import Any, cast
from uuid import UUID, uuid4

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from analysis.cpg_ingest.typed_observed import FrozenArray
from analysis.ifds.bound_rules import BoundRuleError, ScalarLimits, encode_qualified_rule_key

from . import codec as c
from . import models as m
from . import schemas as s


def _same(
    left: dict[str, Any],
    right: dict[str, Any],
    keys: tuple[str, ...],
    code: str = "content-mismatch",
) -> None:
    s.require(all(left[key] == right[key] for key in keys), code)


def _namespace(left: dict[str, Any], right: dict[str, Any]) -> None:
    _same(left, right, ("registry_id", "scope", "org_id"), "scope-mismatch")


def _instant(value: str) -> datetime:
    return s.utc(value, microseconds=True)


def _format(value: datetime) -> str:
    return (
        f"{value.year:04d}-{value.month:02d}-{value.day:02d}T"
        f"{value.hour:02d}:{value.minute:02d}:{value.second:02d}.{value.microsecond:06d}Z"
    )


def _key(data: bytes, expected_digest: str, *, root: bool = False) -> rsa.RSAPublicKey:
    m.raw(data, 4096)
    s.require(c.raw_digest(data) == expected_digest, "untrusted-root" if root else "grant-denied")
    try:
        key = serialization.load_der_public_key(data)
        s.require(isinstance(key, rsa.RSAPublicKey), "signature-invalid")
        assert isinstance(key, rsa.RSAPublicKey)
        s.require(key.key_size == 3072 and key.public_numbers().e == 65537, "signature-invalid")
        canonical = key.public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        s.require(canonical == data, "signature-invalid")
        return key
    except (ValueError, TypeError, UnsupportedAlgorithm) as exc:
        if isinstance(exc, s.VerificationError):
            raise
        raise s.VerificationError("signature-invalid") from exc


def _signature(key: rsa.RSAPublicKey, schema_id: str, data: bytes, signature: bytes) -> None:
    s.require(type(signature) is bytes and len(signature) == 384, "signature-invalid")
    try:
        key.verify(
            signature,
            schema_id.encode("ascii") + b"\n" + data,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
            hashes.SHA256(),
        )
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise s.VerificationError("signature-invalid") from exc


def _policy(
    frame: c.ParsedFrame, role: str, root: rsa.RSAPublicKey, trust: dict[str, Any]
) -> dict[str, Any]:
    document = frame.document(role)
    _namespace(document, trust)
    _signature(root, s.POLICY, frame.object(role), frame.object(role + "-signature"))
    return document


def _checkpoint(
    frame: c.ParsedFrame,
    role: str,
    root: rsa.RSAPublicKey,
    trust: dict[str, Any],
    policy: dict[str, Any],
    policy_bytes: bytes,
    when: datetime,
) -> dict[str, Any]:
    checkpoint = frame.document(role)
    _namespace(checkpoint, trust)
    _same(checkpoint, trust, ("deployment_id", "administrator_actor_id"), "checkpoint-denied")
    _signature(root, s.ADMISSION, frame.object(role), frame.object(role + "-signature"))
    s.require(checkpoint["action"] == "admit", "checkpoint-denied")
    s.require(
        checkpoint["policy_revision"] == policy["revision"]
        and checkpoint["policy_digest"] == c.domain_digest(s.POLICY, policy_bytes),
        "checkpoint-denied",
    )
    s.require(
        s.utc(checkpoint["issued_at"]) <= when < s.utc(checkpoint["expires_at"]),
        "checkpoint-denied",
    )
    return checkpoint


def _policy_time(policy: dict[str, Any], when: datetime) -> None:
    s.require(s.utc(policy["valid_from"]) <= when < s.utc(policy["expires_at"]), "policy-expired")


def _grant(policy: dict[str, Any], approval: dict[str, Any]) -> dict[str, Any]:
    selected = [row for row in policy["grants"] if row["grant_id"] == approval["grant_id"]]
    s.require(len(selected) == 1, "grant-denied")
    grant = selected[0]
    _same(
        grant,
        approval,
        (
            "issuer_actor_id",
            "key_id",
            "key_version",
            "spki_sha256",
            "signature_profile",
            "scope",
            "org_id",
        ),
        "grant-denied",
    )
    return cast("dict[str, Any]", grant)


def _grant_use(
    grant: dict[str, Any], when: datetime, published_at: datetime, *, publication: bool = False
) -> None:
    s.require(s.utc(grant["not_before"]) <= when < s.utc(grant["not_after"]), "grant-denied")
    if publication:
        s.require(grant["status"] == "active", "grant-denied")
    else:
        s.require(grant["status"] in ("active", "retired"), "grant-denied")
        if grant["status"] == "retired":
            changed = s.utc(grant["status_changed_at"])
            s.require(published_at < changed <= when, "grant-denied")


def _policy_evolution(
    old: dict[str, Any], old_bytes: bytes, new: dict[str, Any], new_bytes: bytes
) -> None:
    _namespace(old, new)
    s.require(new["revision"] >= old["revision"], "policy-stale")
    if new["revision"] == old["revision"]:
        s.require(new_bytes == old_bytes, "policy-stale")
        return
    if new["revision"] == old["revision"] + 1:
        s.require(
            new["previous_policy_digest"] == c.domain_digest(s.POLICY, old_bytes), "policy-stale"
        )
        previous_ids = {grant["grant_id"] for grant in old["grants"]}
        for grant in new["grants"]:
            if grant["grant_id"] not in previous_ids:
                _grant_admission_interval(grant, new)
    # The genuine repository validates every intermediate event's predecessor.
    # This bounded material check also prevents tombstone/key-field regression
    # between the two retained endpoints; signatures alone are not a live head.
    current = {grant["grant_id"]: grant for grant in new["grants"]}
    for grant in old["grants"]:
        successor = current.get(grant["grant_id"])
        s.require(successor is not None, "grant-denied")
        assert successor is not None
        fixed = tuple(key for key in grant if key not in ("status", "status_changed_at"))
        _same(grant, successor, fixed, "grant-denied")
        allowed = {
            "active": ("active", "retired", "revoked"),
            "retired": ("retired", "revoked"),
            "revoked": ("revoked",),
        }
        s.require(successor["status"] in allowed[grant["status"]], "grant-denied")
        if successor["status"] == grant["status"]:
            s.require(successor["status_changed_at"] == grant["status_changed_at"], "grant-denied")
        elif grant["status_changed_at"] is not None:
            s.require(
                s.utc(successor["status_changed_at"]) >= s.utc(grant["status_changed_at"]),
                "grant-denied",
            )


def _admission_expected(
    checkpoint: dict[str, Any],
    checkpoint_bytes: bytes,
    policy: dict[str, Any],
    policy_bytes: bytes,
    expected: m.AdmissionExpectation,
) -> None:
    m.AdmissionExpectation.__post_init__(expected)
    actual = {
        "checkpoint_digest": c.domain_digest(s.ADMISSION, checkpoint_bytes),
        "checkpoint_generation": checkpoint["generation"],
        "admission_epoch": checkpoint["admission_epoch"],
        "policy_digest": c.domain_digest(s.POLICY, policy_bytes),
        "policy_revision": policy["revision"],
    }
    s.require(actual == m.record_dict(expected), "checkpoint-denied")


def _bundle(request: m.VerifierRequest) -> None:
    manifest = c.validate_bundle_layout(request.bundle)
    expected = m.record_dict(request.expected_bundle)
    _namespace(manifest, expected)
    _same(manifest, expected, ("bundle_id", "S_version"))
    s.require(
        c.accepted_content_digest(request.bundle) == expected["accepted_content_digest"],
        "content-mismatch",
    )
    # Use the actual integrated semantic decoder for every declared language;
    # pure content hashes cannot substitute for its complete schema validation.
    from analysis.ifds.bound_rules import decode_bound_rule

    try:
        for key, detector_raw, rule_raw, model_raw in c.qualified_members(request.bundle):
            detector = c.decode_document(detector_raw, s.DETECTOR, canonical=False)
            for language in detector["languages"]:
                bound = decode_bound_rule(
                    rule_raw, model_raw, key=key, language=language, limits=ScalarLimits()
                )
                rule = bound.rule_document
                s.require(
                    (
                        rule.get("class_id"),
                        rule.get("engine"),
                        rule.get("spec_id"),
                        rule.get("model_artifact_digest"),
                        rule.get("projection_profile"),
                    )
                    == (
                        detector["class_id"],
                        detector["engine"],
                        key.rule_id,
                        key.model_raw_sha256,
                        s.PROJECTION,
                    ),
                    "content-mismatch",
                )
                languages = rule.get("languages")
                s.require(type(languages) is FrozenArray, "content-mismatch")
                assert isinstance(languages, FrozenArray)
                s.require(languages.values == tuple(detector["languages"]), "content-mismatch")
    except BoundRuleError as exc:
        raise s.VerificationError("unsupported-schema") from exc


def _grant_admission_interval(grant: dict[str, Any], policy: dict[str, Any]) -> None:
    s.require(
        s.utc(policy["valid_from"]) <= s.utc(grant["not_before"])
        and s.utc(grant["not_after"]) <= s.utc(policy["expires_at"]),
        "grant-denied",
    )


def _approval(
    frame: c.ParsedFrame,
    expected: dict[str, Any],
    policy: dict[str, Any],
    policy_bytes: bytes,
    when: datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    approval = frame.document("approval-statement")
    _namespace(approval, expected)
    _same(approval, expected, ("bundle_id", "S_version", "accepted_content_digest"))
    s.require(
        approval["trust_policy_digest"] == c.domain_digest(s.POLICY, policy_bytes), "grant-denied"
    )
    grant = _grant(policy, approval)
    _policy_time(policy, when)
    _grant_use(grant, when, when, publication=True)
    if policy["revision"] == 1:
        _grant_admission_interval(grant, policy)
    # Carried grants keep their original admitted interval. The genuine
    # repository validates earlier admissions/omitted intermediate policies.
    issued = s.utc(approval["issued_at"])
    s.require(
        when - timedelta(seconds=300) <= issued <= when + timedelta(seconds=30), "grant-denied"
    )
    issuer = _key(frame.object("issuer-spki"), approval["spki_sha256"])
    _signature(
        issuer, s.APPROVAL, frame.object("approval-statement"), frame.object("approval-signature")
    )
    inventory = frame.document("approval-evidence-inventory")
    inventory_bytes = frame.object("approval-evidence-inventory")
    s.require(
        c.domain_digest(s.INVENTORY, inventory_bytes) == approval["evidence_inventory_digest"],
        "content-mismatch",
    )
    adoption_bytes = frame.object("operator-adoption")
    descriptor = inventory["objects"][0]
    s.require(
        descriptor["length"] == len(adoption_bytes)
        and descriptor["raw_sha256"] == c.raw_digest(adoption_bytes),
        "content-mismatch",
    )
    adoption = frame.document("operator-adoption")
    _namespace(adoption, approval)
    _same(adoption, approval, ("bundle_id", "accepted_content_digest"))
    s.require(adoption["actor_id"] == approval["issuer_actor_id"], "grant-denied")
    s.require(
        timedelta(0) <= issued - s.utc(adoption["decided_at"]) <= timedelta(seconds=300),
        "grant-denied",
    )
    return approval, grant


def _historical(
    request: m.VerifierRequest, frame: c.ParsedFrame, root: rsa.RSAPublicKey, trust: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    assert request.ledger is not None
    manifest = frame.manifest
    expected = m.record_dict(request.expected_bundle)
    s.require(expected["scope"] == "customer", "unsupported-schema")
    _same(
        manifest,
        expected,
        ("registry_id", "bundle_id", "org_id", "accepted_content_digest"),
        "scope-mismatch",
    )
    s.require(
        c.raw_digest(request.authority_evidence) == request.ledger.request_binding_digest,
        "ledger-mismatch",
    )
    receipt = frame.document("publication-receipt")
    s.require(
        c.domain_digest(s.PUBLICATION, frame.object("publication-receipt"))
        == request.ledger.publication_receipt_digest,
        "ledger-mismatch",
    )
    published_at = _instant(receipt["published_at"])
    resolved_at = _instant(manifest["resolved_at"])
    s.require(published_at <= resolved_at <= _instant(request.reference_time), "ledger-mismatch")
    policy = _policy(frame, "publication-policy", root, trust)
    policy_bytes = frame.object("publication-policy")
    approval, _old_grant = _approval(frame, expected, policy, policy_bytes, published_at)
    _namespace(receipt, approval)
    _same(
        receipt,
        approval,
        ("publication_key", "bundle_id", "accepted_content_digest", "evidence_inventory_digest"),
    )
    s.require(
        receipt["approval_event_id"] == approval["event_id"] == manifest["approval_event_id"],
        "content-mismatch",
    )
    s.require(receipt["publisher_actor_id"] == approval["issuer_actor_id"], "grant-denied")
    s.require(
        receipt["approval_statement_digest"]
        == c.domain_digest(s.APPROVAL, frame.object("approval-statement")),
        "content-mismatch",
    )
    s.require(
        receipt["approval_signature_sha256"] == c.raw_digest(frame.object("approval-signature")),
        "content-mismatch",
    )
    s.require(
        receipt["policy_digest"]
        == manifest["publication_policy_digest"]
        == c.domain_digest(s.POLICY, policy_bytes)
        and receipt["policy_revision"] == policy["revision"],
        "policy-stale",
    )
    checkpoint = _checkpoint(
        frame, "publication-checkpoint", root, trust, policy, policy_bytes, published_at
    )
    s.require(
        receipt["checkpoint_digest"]
        == c.domain_digest(s.ADMISSION, frame.object("publication-checkpoint"))
        and receipt["checkpoint_generation"] == checkpoint["generation"]
        and receipt["admission_epoch"] == checkpoint["admission_epoch"],
        "checkpoint-denied",
    )
    current = _policy(frame, "current-policy", root, trust)
    current_bytes = frame.object("current-policy")
    _policy_evolution(policy, policy_bytes, current, current_bytes)
    _policy_time(current, resolved_at)
    _grant_use(_grant(current, approval), resolved_at, published_at)
    admitted = _checkpoint(
        frame, "admission-checkpoint", root, trust, current, current_bytes, resolved_at
    )
    s.require(
        manifest["current_policy_digest"] == c.domain_digest(s.POLICY, current_bytes)
        and manifest["current_policy_revision"] == current["revision"],
        "policy-stale",
    )
    s.require(
        manifest["checkpoint_digest"]
        == c.domain_digest(s.ADMISSION, frame.object("admission-checkpoint"))
        and manifest["checkpoint_generation"] == admitted["generation"]
        and manifest["admission_epoch"] == admitted["admission_epoch"],
        "checkpoint-denied",
    )
    return approval, receipt, current, admitted


def _execution(
    request: m.VerifierRequest,
    frame: c.ParsedFrame,
    root: rsa.RSAPublicKey,
    trust: dict[str, Any],
    approval: dict[str, Any],
    receipt: dict[str, Any],
    original_policy: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], datetime]:
    assert (
        request.admission is not None
        and request.ledger is not None
        and request.selected_rule is not None
    )
    binding = request.ledger.binding
    assert binding is not None
    s.require(
        request.expected_bundle.scope == "customer"
        and request.expected_bundle.org_id == binding.org_id,
        "scope-mismatch",
    )
    c.selected_content(request.bundle, request.selected_rule)
    live = c.decode_frame(request.live_authority_evidence, s.LIVE)
    policy = _policy(live, "current-policy", root, trust)
    policy_bytes = live.object("current-policy")
    _policy_evolution(original_policy, frame.object("current-policy"), policy, policy_bytes)
    now = _instant(request.reference_time)
    _policy_time(policy, now)
    grant = _grant(policy, approval)
    _grant_use(grant, now, _instant(receipt["published_at"]))
    checkpoint = _checkpoint(live, "admission-checkpoint", root, trust, policy, policy_bytes, now)
    _admission_expected(
        checkpoint, live.object("admission-checkpoint"), policy, policy_bytes, request.admission
    )
    live_manifest = live.manifest
    _namespace(live_manifest, trust)
    s.require(
        {key: live_manifest[key] for key in s.ADMISSION_EXPECTATION}
        == m.record_dict(request.admission),
        "checkpoint-denied",
    )
    authorization = c.decode_document(request.execution_authorization, s.EXECUTION)
    digest = c.domain_digest(s.EXECUTION, request.execution_authorization)
    s.require(
        digest == request.ledger.execution_authorization_digest == binding.authorization_digest,
        "ledger-mismatch",
    )
    s.require(authorization["purpose"] == "detector-run", "unsupported-schema")
    expected_binding = m.record_dict(binding)
    aliases = {"event_id": "authorization_event_id"}
    for name in s.EXECUTION_BINDING:
        if name == "authorization_digest":
            continue
        source_name = next((source for source, dest in aliases.items() if dest == name), name)
        s.require(authorization[source_name] == expected_binding[name], "fence-stale")
    manifest = frame.manifest
    _same(
        authorization,
        manifest,
        (
            "registry_id",
            "org_id",
            "codebase_id",
            "request_id",
            "bundle_id",
            "approval_event_id",
            "accepted_content_digest",
        ),
        "ledger-mismatch",
    )
    s.require(
        authorization["request_binding_digest"] == request.ledger.request_binding_digest,
        "ledger-mismatch",
    )
    s.require(
        authorization["policy_event_id"]
        == str(request.ledger.policy_event_id)
        == policy["event_id"]
        and authorization["admission_event_id"]
        == str(request.ledger.admission_event_id)
        == checkpoint["event_id"],
        "policy-stale",
    )
    s.require(
        authorization["policy_digest"] == request.admission.policy_digest
        and authorization["policy_revision"] == request.admission.policy_revision
        and authorization["checkpoint_digest"] == request.admission.checkpoint_digest
        and authorization["checkpoint_generation"] == request.admission.checkpoint_generation
        and authorization["admission_epoch"] == str(request.admission.admission_epoch),
        "policy-stale",
    )
    authorized_at = _instant(authorization["authorized_at"])
    s.require(_instant(manifest["resolved_at"]) <= authorized_at <= now, "fence-stale")
    # Validate the same active grant/policy/admission at issuance, not only now.
    _policy_time(policy, authorized_at)
    _grant_use(grant, authorized_at, _instant(receipt["published_at"]))
    s.require(
        s.utc(checkpoint["issued_at"]) <= authorized_at < s.utc(checkpoint["expires_at"]),
        "checkpoint-denied",
    )
    expires = min(
        _instant(binding.lease_expires_at),
        _instant(binding.capture_lease_expires_at),
        s.utc(grant["not_after"]),
        s.utc(policy["expires_at"]),
        s.utc(checkpoint["expires_at"]),
    )
    s.require(now < expires, "fence-stale")
    return policy, checkpoint, expires


def verify_request(request: m.VerifierRequest) -> m.VerificationChecks:
    """Pure material verification for diagnostic tests/the isolated child only."""
    s.require(type(request) is m.VerifierRequest)
    m.VerifierRequest.__post_init__(request)
    _bundle(request)
    trust = m.record_dict(request.installed_trust)
    expected = m.record_dict(request.expected_bundle)
    _namespace(trust, expected)
    frame = c.decode_frame(
        request.authority_evidence,
        s.PUBLICATION_INPUT if request.mode == "publication-preflight" else s.SEALED,
    )
    root = _key(frame.object("trust-root-spki"), trust["root_spki_sha256"], root=True)
    receipt_digest = qualified_digest = execution_digest = permission = None
    policy_digest = checkpoint_digest = None
    policy_revision = checkpoint_generation = epoch = None
    if request.mode == "publication-preflight":
        assert request.admission is not None
        _namespace(frame.manifest, expected)
        _same(frame.manifest, expected, ("bundle_id", "S_version", "accepted_content_digest"))
        policy = _policy(frame, "current-policy", root, trust)
        policy_bytes = frame.object("current-policy")
        now = _instant(request.reference_time)
        approval, _selected_grant = _approval(frame, expected, policy, policy_bytes, now)
        checkpoint = _checkpoint(
            frame, "admission-checkpoint", root, trust, policy, policy_bytes, now
        )
        _admission_expected(
            checkpoint,
            frame.object("admission-checkpoint"),
            policy,
            policy_bytes,
            request.admission,
        )
        policy_digest = c.domain_digest(s.POLICY, policy_bytes)
        checkpoint_digest = c.domain_digest(s.ADMISSION, frame.object("admission-checkpoint"))
        policy_revision, checkpoint_generation, epoch = (
            policy["revision"],
            checkpoint["generation"],
            UUID(checkpoint["admission_epoch"]),
        )
    else:
        approval, receipt, original_policy, _original_checkpoint = _historical(
            request, frame, root, trust
        )
        receipt_digest = c.domain_digest(s.PUBLICATION, frame.object("publication-receipt"))
        if request.mode == "execution":
            policy, checkpoint, expires = _execution(
                request, frame, root, trust, approval, receipt, original_policy
            )
            assert request.admission is not None and request.selected_rule is not None
            policy_digest, checkpoint_digest = (
                request.admission.policy_digest,
                request.admission.checkpoint_digest,
            )
            policy_revision, checkpoint_generation, epoch = (
                policy["revision"],
                checkpoint["generation"],
                UUID(checkpoint["admission_epoch"]),
            )
            qualified_digest = c.domain_digest(
                request.selected_rule.schema, encode_qualified_rule_key(request.selected_rule)
            )
            execution_digest = c.domain_digest(s.EXECUTION, request.execution_authorization)
            permission = _format(expires)
    result = m.VerificationChecks(
        expected["accepted_content_digest"],
        UUID(approval["event_id"]),
        c.domain_digest(s.APPROVAL, frame.object("approval-statement")),
        receipt_digest,
        qualified_digest,
        execution_digest,
        policy_digest,
        policy_revision,
        checkpoint_digest,
        checkpoint_generation,
        epoch,
        request.reference_time,
        permission,
    )
    s.validate_checks(m.record_dict(result), request.mode)
    return result


def verify_resolved_qualified_rule(
    resolved: m.ResolvedQualifiedRule,
    *,
    expected: m.ExecutionBinding,
    authority: m.ExecutionAuthorityReader,
) -> m.VerifiedQualifiedRule:
    """The caller must supply the installed real reader; no default fake exists.

    The downstream producer calls this itself. A type/previous return value is
    never permission, and operational authority requires the separately owned
    real reader/admission/controller integration.
    """
    s.require(type(resolved) is m.ResolvedQualifiedRule and type(expected) is m.ExecutionBinding)
    m.ResolvedQualifiedRule.__post_init__(resolved)
    m.ExecutionBinding.__post_init__(expected)
    s.require(resolved.binding == expected, "fence-stale")
    context = authority.read_execution_authority(expected)
    s.require(type(context) is m.ExecutionVerificationContext)
    m.ExecutionVerificationContext.__post_init__(context)
    s.require(context.ledger.binding == expected, "fence-stale")
    key = resolved.qualified_rule
    request = m.VerifierRequest(
        uuid4(),
        "execution",
        context.installed_trust,
        m.BundleExpectation(
            UUID(key.registry_id),
            UUID(key.bundle_id),
            key.scope,
            None if key.org_id is None else UUID(key.org_id),
            key.S_version,
            key.accepted_content_digest,
        ),
        context.reference_time,
        authority.runtime_profile.document.verifier_artifact_digest,
        context.admission,
        context.ledger,
        key,
        resolved.bundle,
        resolved.sealed_authority_evidence,
        context.live_authority_evidence,
        resolved.execution_authorization,
    )
    checks = run_isolated_verifier(request, profile=authority.runtime_profile)
    authority.recheck_execution_authority(expected, context)
    return m.VerifiedQualifiedRule(resolved, checks)


def run_isolated_verifier(
    request: m.VerifierRequest, *, profile: m.VerifierRuntimeProfile
) -> m.VerificationChecks:
    """Operational admission requires the real #400 controller/measurement.

    Missing integration never calls the diagnostic runner or an in-process
    verifier. A later explicit integration supplies the actual enforced parent
    boundary, not an input-provided isolated/accepted boolean.
    """
    raise s.VerificationError("runtime-unsupported")


class VerificationProcessError(s.VerificationError):
    """Private actual process evidence; the public string is a fixed code."""

    def __init__(self, code: str, outcome: object) -> None:
        from tools.worker.bounded_process import ProcessOutcome

        s.require(type(outcome) is ProcessOutcome, "internal-error")
        self.outcome = outcome
        super().__init__(code)


@contextmanager
def _diagnostic_workspace(work_root: PosixPath, retained: list[object]) -> Iterator[PosixPath]:
    """A later private-directory cleanup error cannot erase a child outcome."""
    directory = TemporaryDirectory(prefix="verifier-diagnostic-", dir=work_root)
    primary: BaseException | None = None
    prior_cause: BaseException | None = None
    try:
        yield PosixPath(directory.name)
    except BaseException as error:
        primary = error
        prior_cause = error.__cause__ or error.__context__
        raise
    finally:
        try:
            directory.cleanup()
        except BaseException as cleanup_error:
            if primary is not None:
                cause = (
                    BaseExceptionGroup(
                        "diagnostic workspace cleanup failed", [prior_cause, cleanup_error]
                    )
                    if prior_cause is not None
                    else cleanup_error
                )
                raise primary from cause
            if retained:
                evidence = VerificationProcessError("runtime-unsupported", retained[0])
                if isinstance(cleanup_error, Exception):
                    raise evidence from cleanup_error
                raise cleanup_error from evidence
            raise


def _run_diagnostic_verifier(
    request: m.VerifierRequest, *, profile: m.VerifierRuntimeProfile
) -> m.VerificationChecks:
    """Controlled task-owned process tests only, never a production fallback.

    Actual executable/script/profile bytes are checked. Configured aggregate
    artifact digests are fixture assertions, not measured deployment closure.
    This private call has no outer-container/no-egress/native-launch authority.
    """
    from tools.worker.bounded_process import (
        MemoryOutput,
        ProcessLimits,
        run_bounded_process,
    )

    from .verifier_worker import _directory, _overlaps, _read_file

    s.require(type(request) is m.VerifierRequest and type(profile) is m.VerifierRuntimeProfile)
    m.VerifierRequest.__post_init__(request)
    m.VerifierRuntimeProfile.__post_init__(profile)
    document = profile.document
    profile_bytes = _read_file(profile.profile_path, s.MAX_OBJECT, private=True)
    s.require(c.raw_digest(profile_bytes) == profile.profile_sha256, "runtime-unsupported")
    s.require(
        c.decode_document(profile_bytes, s.RUNTIME) == m.record_dict(document),
        "runtime-unsupported",
    )
    s.require(
        c.raw_digest(_read_file(document.python_executable, 134217728))
        == document.python_executable_sha256,
        "runtime-unsupported",
    )
    s.require(
        c.raw_digest(_read_file(document.worker_script, s.MAX_CONTENT))
        == document.worker_script_sha256,
        "runtime-unsupported",
    )
    s.require(
        request.verifier_artifact_digest == document.verifier_artifact_digest, "runtime-unsupported"
    )
    _directory(document.work_root, private=True)
    roots = (*document.stdlib_roots, document.application_root, *document.dependency_roots)
    for root in roots:
        _directory(root)
        s.require(
            not _overlaps(root, document.work_root)
            and not _overlaps(root, profile.profile_path.parent),
            "runtime-unsupported",
        )
    s.require(not _overlaps(document.work_root, profile.profile_path.parent), "runtime-unsupported")
    payload = c.encode_request(request)
    environment = {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC"}
    retained: list[object] = []
    with _diagnostic_workspace(document.work_root, retained) as cwd:
        cache = cwd / "pycache"
        cache.mkdir(mode=0o700)
        argv = (
            str(document.python_executable),
            "-I",
            "-S",
            "-B",
            "-X",
            "utf8",
            "-X",
            "pycache_prefix=" + str(cache),
            str(document.worker_script),
            "--profile",
            str(profile.profile_path),
            "--profile-sha256",
            profile.profile_sha256,
        )
        outcome = run_bounded_process(
            argv,
            stdin=payload,
            env=environment,
            cwd=cwd,
            limits=ProcessLimits(
                stdin_bytes=s.MAX_PACKET,
                stdout_bytes=s.MAX_OUTPUT,
                stderr_bytes=s.MAX_OUTPUT,
                combined_output_bytes=2 * s.MAX_OUTPUT,
                wall_ms=3000,
                cleanup_reserve_ms=500,
            ),
            spool_dir=None,
        )
        retained.append(outcome)
        actual = outcome.invocation
        consistent = (
            actual.argv == argv
            and actual.environment == tuple(sorted(environment.items()))
            and actual.cwd == str(cwd)
            and actual.stdin_bytes == len(payload)
            and actual.stdin_sha256.hex() == c.raw_digest(payload)
            and outcome.stdin_sent_bytes == len(payload)
            and outcome.reason == "exited"
            and outcome.returncode in (0, 2)
            and outcome.cleanup == "completed"
        )
        for output in (outcome.stdout, outcome.stderr):
            if type(output) is not MemoryOutput:
                consistent = False
                continue
            evidence = output.evidence
            consistent = consistent and (
                evidence.eof
                and not evidence.truncated
                and evidence.observed_bytes == evidence.retained_bytes == len(output.data)
                and evidence.retained_sha256 is not None
                and evidence.retained_sha256.hex() == c.raw_digest(output.data)
            )
        if not consistent:
            raise VerificationProcessError("runtime-unsupported", outcome)
        assert type(outcome.stdout) is MemoryOutput and type(outcome.stderr) is MemoryOutput
        try:
            result = c.decode_result(outcome.stdout.data)
            s.require((result.status == "verified") == (outcome.returncode == 0))
            if result.status == "verified":
                s.require(not outcome.stderr.data)
                s.require(
                    result.operation_id == request.operation_id
                    and result.mode == request.mode
                    and result.request_sha256 == c.raw_digest(payload)
                )
                assert result.checks is not None
                return result.checks
            s.require(
                result.request_sha256 is None or result.request_sha256 == c.raw_digest(payload)
            )
            s.require(
                result.operation_id is None
                or (result.operation_id == request.operation_id and result.mode == request.mode)
            )
            raise VerificationProcessError(result.failure_code or "internal-error", outcome)
        except s.VerificationError as error:
            if isinstance(error, VerificationProcessError):
                raise
            raise VerificationProcessError(error.code, outcome) from error
