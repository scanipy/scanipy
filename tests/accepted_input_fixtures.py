"""Explicitly synthetic authority; no fixture installs an operator or trust."""

from dataclasses import dataclass, replace
from uuid import UUID

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from services.scan.accepted_inputs import codec as c
from services.scan.accepted_inputs import models as m
from services.scan.accepted_inputs import schemas as s


def uid(number):
    return str(UUID(int=number))


def sign(key, schema, data):
    return key.sign(
        schema.encode() + b"\n" + data,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
        hashes.SHA256(),
    )


def spki(key):
    return key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )


def model_document():
    checked = (
        "python-direct-os-import/1",
        "python-no-local-binding-mutation/1",
        "python-exact-str-argument/1",
        "terminal-selected-entry-call/1",
    )
    assumed = ("python-standard-os-implementation/1", "python-no-external-binding-mutation/1")
    conditions = [{"id": name, "evidence_kind": "checked"} for name in checked]
    conditions += [{"id": name, "evidence_kind": "assumed"} for name in assumed]
    return {
        "schema": s.MODEL,
        "target_platform_profiles": ["scanipy-target-cpython311-posix/1"],
        "models": [
            {
                "model_id": "python.os-system/1",
                "language": "python",
                "kind": "external-call",
                "target_platform_profile": "scanipy-target-cpython311-posix/1",
                "operation": "external-api",
                "symbol": {"owner": "os", "member": "system"},
                "signature": {
                    "receiver": None,
                    "parameters": ["python.exact-str"],
                    "result": "python.int",
                },
                "preconditions": sorted(conditions, key=lambda item: item["id"]),
                "normal": {"result": "defined", "effects": ["external-io", "external-process"]},
                "exceptional": {
                    "result": "absent",
                    "continuation": "exit-unknown-exception",
                    "effects": ["unknown-external-effect"],
                },
                "transfer_authorization": {
                    "sink_inputs": [
                        {
                            "position": {"kind": "argument", "index": 0},
                            "class_id": "injection",
                            "context_id": "posix-shell-command",
                        }
                    ],
                    "propagation": [],
                    "sanitization": [],
                },
            }
        ],
    }


def bundle_fixture():
    model_raw = b" " + c.canonical_bytes(model_document()) + b"\n"
    rule = {
        "schema": s.RULE,
        "semantics": s.SEMANTICS,
        "spec_id": "test-injection",
        "class_id": "injection",
        "engine": "ifds",
        "languages": ["python"],
        "projection_profile": s.PROJECTION,
        "model_artifact_digest": c.raw_digest(model_raw),
        "clauses": [
            {
                "primitive": "source",
                "selector": {
                    "kind": "entry_parameter",
                    "language": "python",
                    "source_file": "handler.py",
                    "declaration": ["handler"],
                    "formal_index": 0,
                    "parameter_types": None,
                },
            },
            {
                "primitive": "sink",
                "selector": {
                    "kind": "model",
                    "language": "python",
                    "model_id": "python.os-system/1",
                },
                "position": {"kind": "argument", "index": 0},
                "context_id": "posix-shell-command",
            },
        ],
    }
    rule_raw = c.canonical_bytes(rule) + b"\n"
    profiles = [
        {
            "language": "python",
            "projection_profile": s.PROJECTION,
            "source_syntax_schema": s.SOURCE_SYNTAX,
        }
    ]
    detector = {
        "schema": s.DETECTOR,
        "id": "test-detector",
        "version": "1.0.0",
        "class_id": "injection",
        "cwes": ["CWE-78"],
        "languages": ["python"],
        "frameworks": [],
        "engine": "ifds",
        "severity_default": "high",
        "rule_ids": ["test-injection"],
        "profiles": profiles,
    }
    detector_raw = c.encode_document(detector, s.DETECTOR)
    semantic = {
        "schema": s.SEMANTIC_BINDING,
        "rule_raw_sha256": c.raw_digest(rule_raw),
        "model_raw_sha256": c.raw_digest(model_raw),
        "semantics": s.SEMANTICS,
        "projection_profile": s.PROJECTION,
    }
    member = {
        "rule_id": "test-injection",
        "artifact_id": "test-rule",
        "version": "1.0.0",
        "schema": s.RULE,
        "raw_sha256": c.raw_digest(rule_raw),
        "semantics": s.SEMANTICS,
        "projection_profile": s.PROJECTION,
        "model_artifact_id": "test-model",
        "model_raw_sha256": c.raw_digest(model_raw),
        "semantic_descriptor_digest": c.domain_digest(
            s.SEMANTIC_BINDING, c.encode_document(semantic, s.SEMANTIC_BINDING)
        ),
    }
    manifest = {
        "schema": s.S_MANIFEST,
        "registry_id": uid(1),
        "bundle_id": uid(2),
        "scope": "customer",
        "org_id": uid(3),
        "S_version": "1.0.0",
        "detectors": [
            {
                "detector_id": "test-detector",
                "detector_version": "1.0.0",
                "detector_schema": s.DETECTOR,
                "detector_sha256": c.raw_digest(detector_raw),
                "class_id": "injection",
                "language_profiles": profiles,
                "engine": "ifds",
                "rules": [member],
            }
        ],
        "models": [
            {
                "artifact_id": "test-model",
                "version": "1.0.0",
                "schema": s.MODEL,
                "raw_sha256": c.raw_digest(model_raw),
            }
        ],
    }
    spec = c.encode_spec(c.encode_document(manifest, s.S_MANIFEST), (model_raw,))
    return m.AcceptedBundleBytes(spec, (detector_raw,), (rule_raw,))


def frame(schema, manifest, objects):
    value = dict(manifest, schema=schema)
    roles = s.FRAME_ROLES[schema]
    value["objects"] = [
        {
            "role": role,
            "schema": item_schema,
            "length": len(objects[role]),
            "raw_sha256": c.raw_digest(objects[role]),
        }
        for role, item_schema in roles
    ]
    return c.encode_frame(
        schema, c.encode_document(value, schema), tuple(objects[role] for role, _ in roles)
    )


@dataclass
class Material:
    root: rsa.RSAPrivateKey
    issuer: rsa.RSAPrivateKey
    request: m.VerifierRequest
    objects: dict
    sealed_manifest: dict
    authorization: dict

    def historical(self):
        ledger = self.request.ledger
        return replace(
            self.request,
            mode="historical",
            admission=None,
            selected_rule=None,
            ledger=m.LedgerExpectation(
                ledger.publication_receipt_digest,
                ledger.request_binding_digest,
                None,
                None,
                None,
                None,
            ),
            live_authority_evidence=b"",
            execution_authorization=b"",
        )

    def publication(self):
        return replace(
            self.request,
            mode="publication-preflight",
            reference_time="2026-09-25T00:00:20.000000Z",
            ledger=None,
            selected_rule=None,
            authority_evidence=frame(
                s.PUBLICATION_INPUT, m.record_dict(self.request.expected_bundle), self.objects
            ),
            live_authority_evidence=b"",
            execution_authorization=b"",
        )


def material_fixture(root, issuer):
    bundle = bundle_fixture()
    digest = c.accepted_content_digest(bundle)
    ns = {"registry_id": uid(1), "scope": "customer", "org_id": uid(3)}
    grant = {
        "grant_id": uid(10),
        "key_id": "test-only-issuer",
        "key_version": 1,
        "spki_sha256": c.raw_digest(spki(issuer)),
        "signature_profile": s.SIGNATURE_PROFILE,
        "issuer_actor_id": uid(11),
        "capability": "publish-builtin",
        "scope": "customer",
        "org_id": uid(3),
        "not_before": "2026-09-25T00:00:00Z",
        "not_after": "2026-09-30T00:00:00Z",
        "status": "active",
        "status_changed_at": None,
    }
    policy = {
        "schema": s.POLICY,
        **ns,
        "event_id": uid(12),
        "revision": 1,
        "previous_policy_digest": None,
        "valid_from": "2026-09-25T00:00:00Z",
        "expires_at": "2026-09-30T00:00:00Z",
        "grants": [grant],
    }
    policy_raw = c.encode_document(policy, s.POLICY)
    checkpoint = {
        "schema": s.ADMISSION,
        **ns,
        "event_id": uid(13),
        "deployment_id": uid(14),
        "generation": 1,
        "previous_checkpoint_digest": None,
        "admission_epoch": uid(15),
        "action": "admit",
        "policy_revision": 1,
        "policy_digest": c.domain_digest(s.POLICY, policy_raw),
        "issued_at": "2026-09-25T00:00:00Z",
        "expires_at": "2026-09-26T00:00:00Z",
        "administrator_actor_id": uid(16),
        "reason": "controlled test only",
    }
    checkpoint_raw = c.encode_document(checkpoint, s.ADMISSION)
    adoption = {
        "schema": s.ADOPTION,
        **ns,
        "decision_id": uid(17),
        "actor_id": uid(11),
        "action": "adopt-builtin",
        "bundle_id": uid(2),
        "accepted_content_digest": digest,
        "decided_at": "2026-09-25T00:00:01Z",
        "reason": "synthetic codec tests, no operational grant",
        "proposal_id": None,
    }
    adoption_raw = c.encode_document(adoption, s.ADOPTION)
    inventory_raw = c.encode_document(
        {
            "schema": s.INVENTORY,
            "approval_kind": "builtin-operator",
            "objects": [
                {
                    "role": "operator-adoption",
                    "schema": s.ADOPTION,
                    "length": len(adoption_raw),
                    "raw_sha256": c.raw_digest(adoption_raw),
                }
            ],
        },
        s.INVENTORY,
    )
    approval = {
        "schema": s.APPROVAL,
        **ns,
        "event_id": uid(18),
        "publication_key": uid(19),
        "bundle_id": uid(2),
        "S_version": "1.0.0",
        "accepted_content_digest": digest,
        "approval_kind": "builtin-operator",
        "issuer_actor_id": uid(11),
        "grant_id": uid(10),
        "key_id": grant["key_id"],
        "key_version": 1,
        "spki_sha256": grant["spki_sha256"],
        "signature_profile": s.SIGNATURE_PROFILE,
        "trust_policy_digest": checkpoint["policy_digest"],
        "issued_at": "2026-09-25T00:00:02Z",
        "evidence_inventory_digest": c.domain_digest(s.INVENTORY, inventory_raw),
        "proposal_id": None,
    }
    approval_raw = c.encode_document(approval, s.APPROVAL)
    approval_sig = sign(issuer, s.APPROVAL, approval_raw)
    receipt = {
        "schema": s.PUBLICATION,
        **ns,
        "approval_event_id": uid(18),
        "publication_key": uid(19),
        "bundle_id": uid(2),
        "approval_statement_digest": c.domain_digest(s.APPROVAL, approval_raw),
        "approval_signature_sha256": c.raw_digest(approval_sig),
        "evidence_inventory_digest": approval["evidence_inventory_digest"],
        "accepted_content_digest": digest,
        "policy_digest": checkpoint["policy_digest"],
        "policy_revision": 1,
        "checkpoint_digest": c.domain_digest(s.ADMISSION, checkpoint_raw),
        "checkpoint_generation": 1,
        "admission_epoch": uid(15),
        "published_at": "2026-09-25T00:00:20.000000Z",
        "publisher_actor_id": uid(11),
        "publisher_artifact_digest": "1" * 64,
    }
    receipt_raw = c.encode_document(receipt, s.PUBLICATION)
    objects = {
        "approval-statement": approval_raw,
        "approval-signature": approval_sig,
        "issuer-spki": spki(issuer),
        "publication-receipt": receipt_raw,
        "publication-policy": policy_raw,
        "publication-policy-signature": sign(root, s.POLICY, policy_raw),
        "publication-checkpoint": checkpoint_raw,
        "publication-checkpoint-signature": sign(root, s.ADMISSION, checkpoint_raw),
        "current-policy": policy_raw,
        "current-policy-signature": sign(root, s.POLICY, policy_raw),
        "trust-root-spki": spki(root),
        "approval-evidence-inventory": inventory_raw,
        "operator-adoption": adoption_raw,
        "admission-checkpoint": checkpoint_raw,
        "admission-checkpoint-signature": sign(root, s.ADMISSION, checkpoint_raw),
    }
    sealed_manifest = {
        "registry_id": uid(1),
        "request_id": uid(20),
        "org_id": uid(3),
        "codebase_id": uid(21),
        "bundle_id": uid(2),
        "accepted_content_digest": digest,
        "approval_event_id": uid(18),
        "publication_policy_digest": checkpoint["policy_digest"],
        "current_policy_digest": checkpoint["policy_digest"],
        "current_policy_revision": 1,
        "checkpoint_digest": receipt["checkpoint_digest"],
        "checkpoint_generation": 1,
        "admission_epoch": uid(15),
        "resolved_at": "2026-09-25T00:00:30.000000Z",
        "verifier_artifact_digest": "2" * 64,
    }
    sealed = frame(s.SEALED, sealed_manifest, objects)
    admission = m.AdmissionExpectation(
        receipt["checkpoint_digest"], 1, UUID(uid(15)), checkpoint["policy_digest"], 1
    )
    live = frame(s.LIVE, {**ns, **m.record_dict(admission)}, objects)
    authorization = {
        "schema": s.EXECUTION,
        **ns,
        "event_id": uid(22),
        "operation_key": uid(23),
        "codebase_id": uid(21),
        "request_id": uid(20),
        "request_binding_digest": c.raw_digest(sealed),
        "bundle_id": uid(2),
        "approval_event_id": uid(18),
        "accepted_content_digest": digest,
        "requested_policy_digest": "3" * 64,
        "policy_event_id": uid(12),
        "policy_digest": checkpoint["policy_digest"],
        "policy_revision": 1,
        "admission_event_id": uid(13),
        "checkpoint_digest": receipt["checkpoint_digest"],
        "checkpoint_generation": 1,
        "admission_epoch": uid(15),
        "work_item_id": uid(24),
        "work_attempt_id": uid(25),
        "work_kind": "capture_detection",
        "fencing_token": 1,
        "work_revision": 4,
        "attempt_policy_digest": "4" * 64,
        "capture_id": uid(26),
        "seal_id": uid(27),
        "capture_lease_id": uid(28),
        "authorized_at": "2026-09-25T00:01:00.000000Z",
        "lease_expires_at": "2026-09-25T00:10:00.000001Z",
        "capture_lease_expires_at": "2026-09-25T00:09:00.000002Z",
        "resolver_artifact_digest": "5" * 64,
        "purpose": "detector-run",
        "action": "initial",
        "detector_run_id": uid(29),
        "run_input_digest": "6" * 64,
        "occurrence_id": None,
        "previous_authorization_id": None,
    }
    auth_raw = c.encode_document(authorization, s.EXECUTION)
    binding = m.ExecutionBinding(
        UUID(uid(3)),
        UUID(uid(21)),
        UUID(uid(20)),
        UUID(uid(26)),
        UUID(uid(27)),
        UUID(uid(24)),
        UUID(uid(25)),
        UUID(uid(29)),
        UUID(uid(28)),
        UUID(uid(22)),
        1,
        4,
        "6" * 64,
        "3" * 64,
        "4" * 64,
        c.domain_digest(s.EXECUTION, auth_raw),
        authorization["lease_expires_at"],
        authorization["capture_lease_expires_at"],
    )
    ledger = m.LedgerExpectation(
        c.domain_digest(s.PUBLICATION, receipt_raw),
        c.raw_digest(sealed),
        binding.authorization_digest,
        binding,
        UUID(uid(12)),
        UUID(uid(13)),
    )
    trust = m.InstalledTrust(
        UUID(uid(14)),
        UUID(uid(1)),
        "customer",
        UUID(uid(3)),
        c.raw_digest(spki(root)),
        UUID(uid(16)),
    )
    expected = m.BundleExpectation(
        UUID(uid(1)), UUID(uid(2)), "customer", UUID(uid(3)), "1.0.0", digest
    )
    request = m.VerifierRequest(
        UUID(uid(30)),
        "execution",
        trust,
        expected,
        "2026-09-25T00:02:00.000000Z",
        "7" * 64,
        admission,
        ledger,
        c.qualified_members(bundle)[0][0],
        bundle,
        sealed,
        live,
        auth_raw,
    )
    return Material(root, issuer, request, objects, sealed_manifest, authorization)


@pytest.fixture(scope="session")
def test_only_keys():
    return tuple(rsa.generate_private_key(public_exponent=65537, key_size=3072) for _ in range(2))


@pytest.fixture
def material(test_only_keys):
    return material_fixture(*test_only_keys)
