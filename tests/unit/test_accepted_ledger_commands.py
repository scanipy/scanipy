"""AL-02 supplied-byte diagnostics: no signer, DB, provider, clock or child."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from typing import Any
from uuid import UUID

import pytest

from services.scan.accepted_inputs import codec as c
from services.scan.accepted_inputs import ledger_commands as lc
from services.scan.accepted_inputs import models as m
from services.scan.accepted_inputs import schemas as s
from services.scan.occurrence_store.codec import decode_envelope, encode_envelope
from tests import accepted_input_fixtures as af
from tests import occurrence_store_fixtures as of

pytestmark = pytest.mark.unit
ACTIONS = tuple(lc._ACTIONS)
uid = af.uid


def wire(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def command(
    action: str, body: dict[str, Any], roles: tuple[str, ...], parts: tuple[bytes, ...]
) -> tuple[bytes, tuple[bytes, ...]]:
    counts: dict[str, int] = {}
    objects = []
    for role, part in zip(roles, parts, strict=True):
        ordinal = counts.get(role, 0)
        counts[role] = ordinal + 1
        objects.append(
            {
                "role": role,
                "ordinal": ordinal,
                "length": len(part),
                "raw_sha256": c.raw_digest(part),
            }
        )
    return wire(
        {
            "schema": lc.COMMAND_SCHEMA,
            "action": action,
            "operation_key": uid(100),
            "namespace_id": uid(101),
            "expected_coordination_revision": 0,
            "body": body,
            "objects": objects,
        }
    ), parts


def publication(
    bundle: m.AcceptedBundleBytes | None = None,
) -> tuple[dict[str, Any], dict[str, bytes], dict[str, Any]]:
    bundle = af.bundle_fixture() if bundle is None else bundle
    manifest, _ = c.decode_spec(bundle.spec_bytes)
    ns = {key: manifest[key] for key in ("registry_id", "scope", "org_id")}
    expected = dict(
        ns,
        bundle_id=manifest["bundle_id"],
        S_version=manifest["S_version"],
        accepted_content_digest=c.accepted_content_digest(bundle),
    )
    issuer = b"NOT DER; structurally carried diagnostic bytes"
    grant = {
        "grant_id": uid(10),
        "key_id": "diagnostic-issuer",
        "key_version": 1,
        "spki_sha256": c.raw_digest(issuer),
        "signature_profile": s.SIGNATURE_PROFILE,
        "issuer_actor_id": uid(11),
        "capability": "publish-builtin",
        "scope": ns["scope"],
        "org_id": ns["org_id"],
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
        "reason": "diagnostic only",
    }
    checkpoint_raw = c.encode_document(checkpoint, s.ADMISSION)
    adoption = {
        "schema": s.ADOPTION,
        **ns,
        "decision_id": uid(17),
        "actor_id": uid(11),
        "action": "adopt-builtin",
        "bundle_id": expected["bundle_id"],
        "accepted_content_digest": expected["accepted_content_digest"],
        "decided_at": "2026-09-25T00:00:01Z",
        "reason": "not an actual decision",
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
        "bundle_id": expected["bundle_id"],
        "S_version": expected["S_version"],
        "accepted_content_digest": expected["accepted_content_digest"],
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
    objects = {
        "approval-statement": c.encode_document(approval, s.APPROVAL),
        "approval-signature": b"\x80" * 384,
        "issuer-spki": issuer,
        "current-policy": policy_raw,
        "current-policy-signature": b"\x81" * 384,
        "trust-root-spki": b"NOT a trust anchor",
        "approval-evidence-inventory": inventory_raw,
        "operator-adoption": adoption_raw,
        "admission-checkpoint": checkpoint_raw,
        "admission-checkpoint-signature": b"\x82" * 384,
    }
    admission = {
        "checkpoint_digest": c.domain_digest(s.ADMISSION, checkpoint_raw),
        "checkpoint_generation": 1,
        "admission_epoch": uid(15),
        "policy_digest": checkpoint["policy_digest"],
        "policy_revision": 1,
    }
    return expected, objects, admission


@pytest.fixture
def cases() -> dict[str, tuple[bytes, tuple[bytes, ...]]]:
    bundle = af.bundle_fixture()
    expected, objects, admission = publication(bundle)
    request = of.request_input(
        UUID(uid(3)), UUID(uid(4)), key="fixed-diagnostic", lineage=UUID(uid(5))
    )
    policy = request.planned_policy.value
    inventory = of.envelope(
        "source-inventory", files=[{"path": "fixture.py", "size": 1, "sha256": "2" * 64}]
    )
    content = of.envelope(
        "accepted-content",
        spec_sha256="1" * 64,
        detector_sha256s=[policy["bindings"][0]["detector_content_digest"]],
        rule_sha256s=[policy["bindings"][0]["rules"][0]["content_digest"]],
    )
    seal = of.envelope(
        "seal",
        request_id=uid(20),
        resolved_commit="1" * 40,
        commit_algorithm="git-sha1",
        tree_algorithm="sha256-length-prefixed-path-and-content-v1",
        tree_digest="2" * 64,
        inventory_digest=inventory.digest.hex(),
        storage_object_id=uid(21),
        storage_reference="diagnostic-only",
        retain_seconds=0,
        s_version="1.0.0",
        planned_policy_digest=request.planned_policy.digest.hex(),
        accepted_content_digest=content.digest.hex(),
        acceptance_evidence_digest="3" * 64,
        intended_files=["fixture.py"],
        bindings=policy["bindings"],
    )
    fence = {
        "work_item_id": uid(22),
        "work_attempt_id": uid(23),
        "fencing_token": 1,
        "work_revision": 0,
    }
    return {
        "install-policy": command(
            "install-policy",
            {"predecessor_policy_digest": None},
            ("policy", "root-signature"),
            (objects["current-policy"], objects["current-policy-signature"]),
        ),
        "record-admission": command(
            "record-admission",
            {"predecessor_checkpoint_digest": None},
            ("checkpoint", "root-signature"),
            (objects["admission-checkpoint"], objects["admission-checkpoint-signature"]),
        ),
        "publish-builtin": command(
            "publish-builtin",
            {"admission": admission, "bundle": expected, "publisher_artifact_digest": "4" * 64},
            ("publication-input", "accepted-spec", "detector", "rule"),
            (
                af.frame(s.PUBLICATION_INPUT, expected, objects),
                bundle.spec_bytes,
                *bundle.detector_blobs,
                *bundle.rule_blobs,
            ),
        ),
        "create-bound-request": command(
            "create-bound-request",
            {
                "admission": admission,
                "bundle": expected,
                "approval_event_id": uid(18),
                "verifier_artifact_digest": "4" * 64,
            },
            ("request", "planned-policy"),
            (request.request.data, request.planned_policy.data),
        ),
        "seal-bound-capture": command(
            "seal-bound-capture",
            {"admission": admission, "fence": fence, "resolver_artifact_digest": "4" * 64},
            ("seal", "source-inventory", "accepted-content"),
            (seal.data, inventory.data, content.data),
        ),
        "authorize-detector": command(
            "authorize-detector",
            {"admission": admission, "fence": fence, "resolver_artifact_digest": "4" * 64},
            ("run-input",),
            (of.invocation().data,),
        ),
        "renew-detector": command(
            "renew-detector",
            {
                "admission": admission,
                "fence": fence,
                "resolver_artifact_digest": "4" * 64,
                "detector_run_id": uid(24),
                "previous_authorization_id": uid(25),
            },
            (),
            (),
        ),
    }


def decode(case: tuple[bytes, tuple[bytes, ...]]) -> lc.LedgerCommand:
    return lc.decode_ledger_command(*case, expected_action=json.loads(case[0])["action"])


def reframe(
    case: tuple[bytes, tuple[bytes, ...]], index: int, raw: bytes
) -> tuple[bytes, tuple[bytes, ...]]:
    row, parts = json.loads(case[0]), list(case[1])
    parts[index] = raw
    row["objects"][index].update(length=len(raw), raw_sha256=c.raw_digest(raw))
    return wire(row), tuple(parts)


@pytest.mark.parametrize("action", ACTIONS)
def test_seven_exact_roundtrips_are_only_input_structure(cases, action):
    case = cases[action]
    result = decode(case)
    assert lc.encode_ledger_command(result, expected_action=action) == case
    assert result.validation == "input-structure-only"
    assert result.command_digest == c.domain_digest(lc.COMMAND_SCHEMA, case[0])
    assert result.command_digest != c.raw_digest(case[0])
    assert result.input_bytes == len(case[0]) + sum(map(len, case[1]))
    assert not hasattr(result, "receipt") and not hasattr(result, "verified")


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize(
    "mutation",
    (
        "extra",
        "missing",
        "wrong-action",
        "bool",
        "uuid",
        "body",
        "extra-part",
        "duplicate",
        "noncanonical",
    ),
)
def test_closed_command_boundaries(cases, action, mutation):
    data, parts = cases[action]
    row = json.loads(data)
    if mutation == "extra":
        row["verified"] = True
    elif mutation == "missing":
        del row["namespace_id"]
    elif mutation == "wrong-action":
        row["action"] = "identity-authorize"
    elif mutation == "bool":
        row["expected_coordination_revision"] = True
    elif mutation == "uuid":
        row["operation_key"] = row["operation_key"].replace("-", "")
    elif mutation == "body":
        row["body"]["current"] = True
    elif mutation == "extra-part":
        parts += (b"hidden",)
    data = wire(row)
    if mutation == "duplicate":
        data = data[:-1] + b',"schema":' + wire(lc.COMMAND_SCHEMA) + b"}"
    elif mutation == "noncanonical":
        data += b"\n"
    with pytest.raises(s.VerificationError):
        lc.decode_ledger_command(data, parts, expected_action=action)


@pytest.mark.parametrize("action", ACTIONS[:-1])
@pytest.mark.parametrize(
    "field,value", (("ordinal", 1), ("role", "unknown"), ("length", 0), ("raw_sha256", "0" * 64))
)
def test_exact_outer_descriptor_binding(cases, action, field, value):
    row = json.loads(cases[action][0])
    row["objects"][0][field] = value
    with pytest.raises(s.VerificationError):
        lc.decode_ledger_command(wire(row), cases[action][1], expected_action=action)


@pytest.mark.parametrize("action", ("install-policy", "record-admission"))
@pytest.mark.parametrize("size", (383, 384, 385))
def test_signature_size_is_not_signature_verification(cases, action, size):
    case = reframe(cases[action], 1, b"z" * size)
    if size == 384:
        assert decode(case).validation == "input-structure-only"
    else:
        with pytest.raises(s.VerificationError):
            decode(case)


@pytest.mark.parametrize("action", ("install-policy", "record-admission"))
def test_predecessor_is_exact_not_inferred_from_coordination(cases, action):
    data, parts = cases[action]
    row = json.loads(data)
    row["expected_coordination_revision"] = 99
    assert decode((wire(row), parts)).validation == "input-structure-only"
    row["body"][next(iter(row["body"]))] = "f" * 64
    with pytest.raises(s.VerificationError):
        decode((wire(row), parts))


@pytest.mark.parametrize("action", ("create-bound-request", "seal-bound-capture"))
def test_owner_domain_digest_cannot_be_replaced_by_raw_hash(cases, action):
    case = cases[action]
    row = json.loads(case[1][0])
    row["requested_policy_digest" if action == "create-bound-request" else "inventory_digest"] = (
        c.raw_digest(case[1][1])
    )
    with pytest.raises(s.VerificationError, match="content-mismatch"):
        decode(reframe(case, 0, wire(row)))


@pytest.mark.parametrize(
    "field,value", (("scope", "global"), ("org_id", uid(999)), ("S_version", "2.0.0"))
)
def test_customer_create_cannot_adopt_other_bundle_scope(cases, field, value):
    row = json.loads(cases["create-bound-request"][0])
    row["body"]["bundle"][field] = value
    if value == "global":
        row["body"]["bundle"]["org_id"] = None
    with pytest.raises(s.VerificationError):
        decode((wire(row), cases["create-bound-request"][1]))


def test_occurrence_text_over_accepted_string_limit_is_preserved(cases):
    case = cases["authorize-detector"]
    row = json.loads(case[1][0])
    row["argv"][0] = "x" * 20000
    raw = encode_envelope("run-input", row).data
    assert decode(reframe(case, 0, raw)).parts == (raw,)


class Poison:
    def __iter__(self):
        raise AssertionError("iterator callback")

    def __len__(self):
        raise AssertionError("length callback")

    def __str__(self):
        raise AssertionError("string callback")

    def __format__(self, spec):
        raise AssertionError("format callback")

    def __eq__(self, other):
        raise AssertionError("equality callback")


@pytest.mark.parametrize(
    "value", ([], {}, Poison(), bytearray(b"x"), type("ForeignTuple", (tuple,), {})())
)
def test_parts_exact_type_before_iteration(cases, value):
    with pytest.raises(s.VerificationError):
        lc.decode_ledger_command(
            cases["renew-detector"][0], value, expected_action="renew-detector"
        )


@pytest.mark.parametrize("field", tuple(lc.LedgerCommand.__dataclass_fields__))
def test_encoder_rejects_poisoned_carrier_without_callbacks(cases, field):
    record = decode(cases["renew-detector"])
    object.__setattr__(record, field, Poison())
    with pytest.raises(s.VerificationError):
        lc.encode_ledger_command(record, expected_action="renew-detector")


@pytest.mark.parametrize("field", ("operation_key", "namespace_id"))
def test_uuid_storage_not_renormalized(cases, field):
    record = decode(cases["renew-detector"])
    object.__setattr__(getattr(record, field), "int", Poison())
    with pytest.raises(s.VerificationError):
        lc.encode_ledger_command(record, expected_action="renew-detector")


@pytest.mark.parametrize("action", ACTIONS)
def test_real_hash_work_never_runs_before_its_reservation(cases, action, monkeypatch):
    case = cases[action]
    observed = {"calls": 0, "bytes": 0, "reserved_calls": 0, "reserved_bytes": 0}
    real_hash, real_reserve = hashlib.sha256, lc._Work.reserve

    def reserve(self, calls, size):
        real_reserve(self, calls, size)
        observed["reserved_calls"], observed["reserved_bytes"] = self.calls, self.bytes

    def hashed(data=b"", *args, **kwargs):
        observed["calls"] += 1
        observed["bytes"] += len(data)
        assert observed["calls"] <= observed["reserved_calls"]
        assert observed["bytes"] <= observed["reserved_bytes"]
        return real_hash(data, *args, **kwargs)

    monkeypatch.setattr(lc._Work, "reserve", reserve)
    monkeypatch.setattr(hashlib, "sha256", hashed)
    result = decode(case)
    assert result.hash_calls_reserved == observed["reserved_calls"]
    assert result.hash_bytes_reserved == observed["reserved_bytes"]


@pytest.mark.parametrize("field", ("MAX_HASH_CALLS", "MAX_HASH_BYTES"))
def test_exact_reserved_work_limit_and_one_less(cases, field, monkeypatch):
    case = cases["publish-builtin"]
    baseline = decode(case)
    value = getattr(
        baseline, "hash_calls_reserved" if field == "MAX_HASH_CALLS" else "hash_bytes_reserved"
    )
    monkeypatch.setattr(lc, field, value)
    assert decode(case) == baseline
    monkeypatch.setattr(lc, field, value - 1)
    with pytest.raises(s.VerificationError):
        decode(case)


@pytest.mark.parametrize("variant", ("command", "count", "total", "part", "signature"))
def test_outer_limits_fail_before_hash(cases, variant, monkeypatch):
    data, parts = cases["install-policy"]
    if variant == "command":
        data = b"x" * 65537
    elif variant == "count":
        parts = (b"",) * 20001
    elif variant == "total":
        parts = (b"x" * 3211265,)
    elif variant == "part":
        parts = (Poison(), parts[1])
    else:
        data, parts = reframe((data, parts), 1, b"x" * 385)

    def forbidden(*args, **kwargs):
        pytest.fail("hash ran before outer rejection")

    monkeypatch.setattr(hashlib, "sha256", forbidden)
    with pytest.raises(s.VerificationError):
        lc.decode_ledger_command(data, parts, expected_action="install-policy")


def expanded_bundle(*, languages=("python", "java"), count=2, scope="customer", mutation=None):
    base = af.bundle_fixture()
    manifest, original_models = c.decode_spec(base.spec_bytes)
    manifest["scope"], manifest["org_id"] = scope, None if scope == "global" else uid(3)
    model_document = json.loads(original_models[0])
    python_model = model_document["models"][0]
    java_model = copy.deepcopy(python_model)
    java_model.update(
        model_id="java.jdbc-execute-query/1",
        language="java",
        target_platform_profile="scanipy-target-java21-jdbc/1",
        symbol={"owner": "java.sql.Statement", "member": "executeQuery"},
        signature={
            "receiver": "java.sql.Statement",
            "parameters": ["java.lang.String"],
            "result": "java.sql.ResultSet",
        },
        preconditions=[
            {"id": name, "evidence_kind": evidence}
            for name, evidence in (
                ("java-declared-statement-receiver/1", "checked"),
                ("java-string-argument/1", "checked"),
                ("java21-jdbc-contract/1", "assumed"),
                ("terminal-selected-entry-call/1", "checked"),
            )
        ],
        normal={"result": "defined", "effects": ["external-io", "unknown-external-effect"]},
    )
    java_model["transfer_authorization"]["sink_inputs"][0]["context_id"] = "sql-query-text"
    models = [model for model in (java_model, python_model) if model["language"] in languages]
    model_document.update(
        models=models,
        target_platform_profiles=sorted({model["target_platform_profile"] for model in models}),
    )
    if mutation == "model-effect":
        model_document["models"][-1]["normal"]["effects"] = []
    model_raw = b" \n" + wire(model_document) + b"\n"
    model_digest = c.raw_digest(model_raw)
    manifest["models"][0]["raw_sha256"] = model_digest
    detector_rows, detector_blobs, rule_blobs = [], [], []
    for index in range(count):
        member = copy.deepcopy(manifest["detectors"][0])
        detector = json.loads(base.detector_blobs[0])
        rule = json.loads(base.rule_blobs[0])
        rule.update(
            spec_id=f"test-injection-{index}",
            languages=list(languages),
            model_artifact_digest=model_digest,
        )
        rule["clauses"] = []
        for language in languages:
            rule["clauses"].extend(
                [
                    {
                        "primitive": "source",
                        "selector": {
                            "kind": "entry_parameter",
                            "language": language,
                            "source_file": "handler.py" if language == "python" else "Handler.java",
                            "declaration": ["handler"],
                            "formal_index": 0,
                            "parameter_types": None
                            if language == "python"
                            else ["java.lang.String"],
                        },
                    },
                    {
                        "primitive": "sink",
                        "selector": {
                            "kind": "model",
                            "language": language,
                            "model_id": "python.os-system/1"
                            if language == "python"
                            else "java.jdbc-execute-query/1",
                        },
                        "position": {"kind": "argument", "index": 0},
                        "context_id": "posix-shell-command"
                        if language == "python"
                        else "sql-query-text",
                    },
                ]
            )
        if index == count - 1:
            if mutation == "rule-class":
                rule["class_id"] = "ssrf"
            elif mutation == "rule-extra":
                rule["accepted"] = True
            elif mutation == "missing-java-sink":
                rule["clauses"] = [
                    clause
                    for clause in rule["clauses"]
                    if not (
                        clause["primitive"] == "sink" and clause["selector"]["language"] == "java"
                    )
                ]
            elif mutation == "rule-model":
                rule["model_artifact_digest"] = "0" * 64
        rule_raw = wire(rule) + b"\n"
        descriptor = member["rules"][0]
        descriptor.update(
            rule_id=rule["spec_id"],
            artifact_id=f"test-rule-{index}",
            raw_sha256=c.raw_digest(rule_raw),
            model_raw_sha256=model_digest,
        )
        semantic = {
            "schema": s.SEMANTIC_BINDING,
            "rule_raw_sha256": descriptor["raw_sha256"],
            "model_raw_sha256": model_digest,
            "semantics": s.SEMANTICS,
            "projection_profile": s.PROJECTION,
        }
        descriptor["semantic_descriptor_digest"] = c.domain_digest(
            s.SEMANTIC_BINDING, c.encode_document(semantic, s.SEMANTIC_BINDING)
        )
        if mutation == "semantic-digest" and index == count - 1:
            descriptor["semantic_descriptor_digest"] = "0" * 64
        profiles = [
            {
                "language": language,
                "projection_profile": s.PROJECTION,
                "source_syntax_schema": s.SOURCE_SYNTAX,
            }
            for language in languages
        ]
        detector.update(
            id=f"test-detector-{index}",
            languages=list(languages),
            profiles=profiles,
            rule_ids=[rule["spec_id"]],
        )
        detector_raw = b" " + c.encode_document(detector, s.DETECTOR) + b"\n"
        member.update(
            detector_id=detector["id"],
            detector_sha256=c.raw_digest(detector_raw),
            language_profiles=profiles,
        )
        if mutation == "detector-class" and index == count - 1:
            member["class_id"] = "ssrf"
        detector_rows.append(member)
        detector_blobs.append(detector_raw)
        rule_blobs.append(rule_raw)
    manifest["detectors"] = detector_rows
    spec = c.encode_spec(c.encode_document(manifest, s.S_MANIFEST), (model_raw,))
    return m.AcceptedBundleBytes(spec, tuple(detector_blobs), tuple(rule_blobs))


def publication_case(bundle=None):
    bundle = expanded_bundle() if bundle is None else bundle
    expected, objects, admission = publication(bundle)
    parts = (
        af.frame(s.PUBLICATION_INPUT, expected, objects),
        bundle.spec_bytes,
        *bundle.detector_blobs,
        *bundle.rule_blobs,
    )
    roles = (
        "publication-input",
        "accepted-spec",
        *("detector" for _ in bundle.detector_blobs),
        *("rule" for _ in bundle.rule_blobs),
    )
    return command(
        "publish-builtin",
        {"admission": admission, "bundle": expected, "publisher_artifact_digest": "4" * 64},
        roles,
        parts,
    )


@pytest.mark.parametrize("languages", (("python",), ("java",), ("python", "java")))
@pytest.mark.parametrize("scope", ("customer", "global"))
def test_complete_multimember_languages_preserve_original_bytes(languages, scope):
    bundle = expanded_bundle(languages=languages, scope=scope)
    result = decode(publication_case(bundle))
    assert result.parts[1:] == (bundle.spec_bytes, *bundle.detector_blobs, *bundle.rule_blobs)
    assert result.validation == "input-structure-only"
    assert result.parts[-1].endswith(b"\n")


@pytest.mark.parametrize(
    "mutation",
    (
        "rule-class",
        "rule-extra",
        "missing-java-sink",
        "rule-model",
        "model-effect",
        "semantic-digest",
        "detector-class",
    ),
)
def test_last_invalid_member_rejects_whole_publication(mutation):
    case = publication_case(expanded_bundle(mutation=mutation))
    with pytest.raises(s.VerificationError):
        decode(case)


@pytest.mark.parametrize("change", ("rule-order", "detector-order", "omitted-rule", "extra-model"))
def test_manifest_order_and_complete_part_census_are_not_subset_checks(change):
    case = publication_case()
    row, parts = json.loads(case[0]), list(case[1])
    if change == "rule-order":
        parts[-1], parts[-2] = parts[-2], parts[-1]
    elif change == "detector-order":
        parts[2], parts[3] = parts[3], parts[2]
    elif change == "omitted-rule":
        parts.pop()
        row["objects"].pop()
    else:
        parts.append(b"extra model")
        row["objects"].append(
            {"role": "model", "ordinal": 0, "length": 11, "raw_sha256": c.raw_digest(parts[-1])}
        )
    for descriptor, part in zip(row["objects"], parts, strict=True):
        descriptor.update(length=len(part), raw_sha256=c.raw_digest(part))
    with pytest.raises(s.VerificationError):
        decode((wire(row), tuple(parts)))


@pytest.mark.parametrize(
    "field",
    (
        "checkpoint_digest",
        "checkpoint_generation",
        "admission_epoch",
        "policy_digest",
        "policy_revision",
    ),
)
def test_publication_expected_admission_has_exact_domain_links(cases, field):
    row = json.loads(cases["publish-builtin"][0])
    old = row["body"]["admission"][field]
    row["body"]["admission"][field] = (
        old + 1 if type(old) is int else uid(999) if field == "admission_epoch" else "0" * 64
    )
    with pytest.raises(s.VerificationError, match="content-mismatch"):
        decode((wire(row), cases["publish-builtin"][1]))


@pytest.mark.parametrize(
    "role,field,value",
    (
        ("approval-statement", "trust_policy_digest", "0" * 64),
        ("approval-statement", "evidence_inventory_digest", "0" * 64),
        ("approval-statement", "grant_id", uid(999)),
        ("approval-statement", "spki_sha256", "0" * 64),
        ("operator-adoption", "actor_id", uid(999)),
        ("operator-adoption", "accepted_content_digest", "0" * 64),
        ("admission-checkpoint", "policy_digest", "0" * 64),
    ),
)
def test_self_contained_links_fail_even_with_reframed_raw_hashes(role, field, value):
    bundle = af.bundle_fixture()
    expected, objects, admission = publication(bundle)
    row = json.loads(objects[role])
    row[field] = value
    objects[role] = wire(row)
    raw = af.frame(s.PUBLICATION_INPUT, expected, objects)
    case = command(
        "publish-builtin",
        {"admission": admission, "bundle": expected, "publisher_artifact_digest": "4" * 64},
        ("publication-input", "accepted-spec", "detector", "rule"),
        (raw, bundle.spec_bytes, *bundle.detector_blobs, *bundle.rule_blobs),
    )
    with pytest.raises(s.VerificationError):
        decode(case)


def audited_decode(case, monkeypatch, *, invalid=False):
    observed = [0, 0]
    reserved = [0, 0]
    real_hash, real_reserve = hashlib.sha256, lc._Work.reserve

    def reserve(self, count, size):
        real_reserve(self, count, size)
        reserved[:] = [self.calls, self.bytes]

    def hashed(data=b"", *args, **kwargs):
        observed[0] += 1
        observed[1] += len(data)
        assert observed[0] <= reserved[0] <= lc.MAX_HASH_CALLS
        assert observed[1] <= reserved[1] <= lc.MAX_HASH_BYTES
        return real_hash(data, *args, **kwargs)

    monkeypatch.setattr(lc._Work, "reserve", reserve)
    monkeypatch.setattr(hashlib, "sha256", hashed)
    if invalid:
        with pytest.raises(s.VerificationError):
            decode(case)
    else:
        result = decode(case)
        assert (result.hash_calls_reserved, result.hash_bytes_reserved) == tuple(reserved)
    return observed, reserved


@pytest.mark.parametrize(
    "mutation",
    (None, "rule-extra", "missing-java-sink", "model-effect", "semantic-digest", "detector-class"),
)
def test_actual_complete_and_malformed_helpers_stay_precharged(mutation, monkeypatch):
    case = publication_case(expanded_bundle(count=4, mutation=mutation))
    observed, reserved = audited_decode(case, monkeypatch, invalid=mutation is not None)
    assert 0 < observed[0] <= reserved[0]


@pytest.mark.parametrize("index", (0, 1))
@pytest.mark.parametrize("mutation", ("prefix", "truncated", "trailing", "last-byte"))
def test_malformed_frame_paths_do_not_escape_hash_reservations(cases, index, mutation, monkeypatch):
    raw = cases["publish-builtin"][1][index]
    if mutation == "prefix":
        raw = b"X" + raw[1:]
    elif mutation == "truncated":
        raw = raw[:-10]
    elif mutation == "trailing":
        raw += b"extra"
    else:
        raw = raw[:-1] + bytes([raw[-1] ^ 1])
    case = reframe(cases["publish-builtin"], index, raw)
    audited_decode(case, monkeypatch, invalid=True)


@pytest.mark.parametrize("action", ACTIONS)
def test_wrong_fixed_action_never_dispatches_another_command(cases, action):
    other = ACTIONS[(ACTIONS.index(action) + 1) % len(ACTIONS)]
    with pytest.raises(s.VerificationError):
        lc.decode_ledger_command(*cases[action], expected_action=other)


@pytest.mark.parametrize(
    "raw",
    (
        b"\xff",
        b"[]",
        b"null",
        b"{" + b'"x":' + b"[" * 34 + b"0" + b"]" * 34 + b"}",
        b'{"x":NaN}',
        b'{"x":1.0}',
        b'{"x":9223372036854775808}',
        b'{"x":"\\ud800"}',
        b'{"x":"\\u0000"}',
    ),
)
def test_lexical_invalid_input_never_reaches_hash(raw, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("hash after malformed header")

    monkeypatch.setattr(hashlib, "sha256", forbidden)
    with pytest.raises(s.VerificationError):
        lc.decode_ledger_command(raw, (), expected_action="renew-detector")


@pytest.mark.parametrize(
    "field",
    ("expected_coordination_revision", "input_bytes", "hash_calls_reserved", "hash_bytes_reserved"),
)
@pytest.mark.parametrize("value", (True, -1, 2**63))
def test_encoder_never_accepts_coerced_or_forged_counters(cases, field, value):
    record = replace(decode(cases["renew-detector"]), **{field: value})
    with pytest.raises(s.VerificationError):
        lc.encode_ledger_command(record, expected_action="renew-detector")


@pytest.mark.parametrize("variant", ("missing-slot", "uuid-string", "wrong-digest", "changed-part"))
def test_encoder_revalidates_exact_original_storage(cases, variant):
    record = decode(cases["install-policy"])
    if variant == "missing-slot":
        object.__delattr__(record, "parts")
    elif variant == "uuid-string":
        object.__setattr__(record, "operation_key", str(record.operation_key))
    elif variant == "wrong-digest":
        object.__setattr__(record, "command_digest", "0" * 64)
    else:
        object.__setattr__(record, "parts", (record.parts[0] + b"\n", record.parts[1]))
    with pytest.raises(s.VerificationError):
        lc.encode_ledger_command(record, expected_action="install-policy")


@pytest.mark.parametrize("field", ("detector_sha256s", "rule_sha256s"))
def test_seal_supplied_binding_arrays_are_exact_not_only_same_length(cases, field):
    case = cases["seal-bound-capture"]
    content = decode_envelope("accepted-content", case[1][2])
    content[field][0] = "0" * 64
    encoded = encode_envelope("accepted-content", content)
    changed = reframe(case, 2, encoded.data)
    seal = json.loads(changed[1][0])
    seal["accepted_content_digest"] = encoded.digest.hex()
    with pytest.raises(s.VerificationError, match="content-mismatch"):
        decode(reframe(changed, 0, wire(seal)))


def test_declared_pins_expiry_and_revocation_are_not_current_authority(cases):
    # These are command operands. No installed profile/clock/DB head is consulted.
    row = json.loads(cases["create-bound-request"][0])
    row["body"]["verifier_artifact_digest"] = "0" * 64
    assert (
        decode((wire(row), cases["create-bound-request"][1])).validation == "input-structure-only"
    )
    expected, objects, admission = publication()
    policy = json.loads(objects["current-policy"])
    policy["grants"][0].update(status="revoked", status_changed_at="2026-09-25T00:00:01Z")
    objects["current-policy"] = c.encode_document(policy, s.POLICY)
    digest = c.domain_digest(s.POLICY, objects["current-policy"])
    checkpoint = json.loads(objects["admission-checkpoint"])
    checkpoint.update(action="block", policy_digest=digest)
    objects["admission-checkpoint"] = c.encode_document(checkpoint, s.ADMISSION)
    approval = json.loads(objects["approval-statement"])
    approval["trust_policy_digest"] = digest
    objects["approval-statement"] = c.encode_document(approval, s.APPROVAL)
    admission.update(
        policy_digest=digest,
        checkpoint_digest=c.domain_digest(s.ADMISSION, objects["admission-checkpoint"]),
    )
    bundle = af.bundle_fixture()
    case = command(
        "publish-builtin",
        {"admission": admission, "bundle": expected, "publisher_artifact_digest": "0" * 64},
        ("publication-input", "accepted-spec", "detector", "rule"),
        (
            af.frame(s.PUBLICATION_INPUT, expected, objects),
            bundle.spec_bytes,
            *bundle.detector_blobs,
            *bundle.rule_blobs,
        ),
    )
    assert decode(case).validation == "input-structure-only"


@pytest.mark.parametrize("action", ACTIONS)
def test_inclusive_action_work_limit_n_and_n_plus_one(cases, action, monkeypatch):
    case = cases[action]
    size = len(case[0]) + sum(map(len, case[1]))
    monkeypatch.setitem(lc._W, action, size)
    assert decode(case).input_bytes == size
    monkeypatch.setitem(lc._W, action, size - 1)

    def forbidden(*args, **kwargs):
        pytest.fail("hash occurred after the inclusive action bound failed")

    monkeypatch.setattr(hashlib, "sha256", forbidden)
    with pytest.raises(s.VerificationError):
        decode(case)


@pytest.mark.parametrize(
    "action,index,maximum",
    (
        ("install-policy", 0, 131072),
        ("record-admission", 0, 65536),
        ("publish-builtin", 0, 1048576),
        ("publish-builtin", 1, 1048576),
        ("create-bound-request", 0, 1048576),
        ("create-bound-request", 1, 1048576),
        ("seal-bound-capture", 0, 1048576),
        ("seal-bound-capture", 1, 1048576),
        ("seal-bound-capture", 2, 1048576),
        ("authorize-detector", 0, 1048576),
    ),
)
@pytest.mark.parametrize("extra", (0, 1))
def test_real_part_and_complete_bundle_cap_before_hash(
    cases, action, index, maximum, extra, monkeypatch
):
    case = cases[action]
    if action == "publish-builtin" and index == 1:
        # The content bound includes S, every detector and every rule.
        maximum -= sum(map(len, case[1][2:]))
    case = reframe(case, index, b"x" * (maximum + extra))

    class ReachedOuterHashError(Exception):
        pass

    def observed_hash(*args, **kwargs):
        raise ReachedOuterHashError

    monkeypatch.setattr(hashlib, "sha256", observed_hash)
    # At N the outer admission admits the finite input; this deliberately invalid
    # inner payload is NOT asserted to be an accepted maximal complete bundle.
    with pytest.raises(s.VerificationError if extra else ReachedOuterHashError):
        decode(case)


@pytest.mark.parametrize("size", (65536, 65537))
def test_command_byte_cap_precedes_generic_parser(size, monkeypatch):
    class ReachedParserError(Exception):
        pass

    def observed_parser(*args, **kwargs):
        raise ReachedParserError

    monkeypatch.setattr(c, "parse_json", observed_parser)
    with pytest.raises(ReachedParserError if size == 65536 else s.VerificationError):
        lc.decode_ledger_command(b"x" * size, (), expected_action="renew-detector")


@pytest.mark.parametrize("count", (20000, 20001))
def test_part_count_cap_precedes_generic_parser(count, monkeypatch):
    class ReachedParserError(Exception):
        pass

    def observed_parser(*args, **kwargs):
        raise ReachedParserError

    monkeypatch.setattr(c, "parse_json", observed_parser)
    with pytest.raises(ReachedParserError if count == 20000 else s.VerificationError):
        lc.decode_ledger_command(b"{}", (b"",) * count, expected_action="renew-detector")


@pytest.mark.parametrize("size", (3211264, 3211265))
def test_coarse_inclusive_input_cap_precedes_generic_parser(size, monkeypatch):
    class ReachedParserError(Exception):
        pass

    def observed_parser(*args, **kwargs):
        raise ReachedParserError

    monkeypatch.setattr(c, "parse_json", observed_parser)
    with pytest.raises(ReachedParserError if size == 3211264 else s.VerificationError):
        lc.decode_ledger_command(b"{}", (b"x" * (size - 2),), expected_action="renew-detector")


@pytest.mark.parametrize(
    "target,action",
    (
        ("decode_frame", "publish-builtin"),
        ("decode_spec", "publish-builtin"),
        ("AcceptedBundleBytes", "publish-builtin"),
        ("qualified_members", "publish-builtin"),
        ("decode_bound_rule", "publish-builtin"),
        ("decode_envelope", "authorize-detector"),
    ),
)
@pytest.mark.parametrize("budget", ("MAX_HASH_CALLS", "MAX_HASH_BYTES"))
def test_every_real_helper_reservation_precedes_its_first_invocation(
    cases, target, action, budget, monkeypatch
):
    owner = (
        m.AcceptedBundleBytes
        if target == "AcceptedBundleBytes"
        else lc
        if target in ("decode_bound_rule", "decode_envelope")
        else c
    )
    attribute = "__post_init__" if target == "AcceptedBundleBytes" else target
    real_helper, real_reserve = getattr(owner, attribute), lc._Work.reserve
    state, entered = {}, []

    def reserve(self, calls, size):
        real_reserve(self, calls, size)
        state.update(MAX_HASH_CALLS=self.calls, MAX_HASH_BYTES=self.bytes)

    def helper(*args, **kwargs):
        entered.append(dict(state))
        return real_helper(*args, **kwargs)

    monkeypatch.setattr(lc._Work, "reserve", reserve)
    monkeypatch.setattr(owner, attribute, helper)
    decode(cases[action])
    assert entered
    monkeypatch.setattr(lc, budget, entered[0][budget] - 1)

    def forbidden(*args, **kwargs):
        pytest.fail("helper was invoked without fitting its complete reservation")

    monkeypatch.setattr(owner, attribute, forbidden)
    with pytest.raises(s.VerificationError):
        decode(cases[action])


@pytest.mark.parametrize(
    "data",
    (
        b"[" + b"0," * 20000 + b"0]",
        b'{"x":"' + b"a" * 16385 + b'"}',
        b'{"x":"' + b"\\u0061" * 10921 + b'"}',
        b'{"x":' + b"1" * 1000 + b"}",
        b'{"x":"' + b"\\u0001" * 100 + b'"}',
        b'{"x":-9223372036854775809}',
    ),
)
def test_owner_lexical_and_canonical_header_fences_preserved(data, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("hash after a bounded lexical/header rejection")

    monkeypatch.setattr(hashlib, "sha256", forbidden)
    with pytest.raises(s.VerificationError):
        lc.decode_ledger_command(data, (), expected_action="renew-detector")


@pytest.mark.parametrize("field", ("operation_key", "namespace_id"))
@pytest.mark.parametrize("integer", (-1, 2**128, True))
def test_encoder_rejects_invalid_original_uuid_integer_storage(cases, field, integer):
    record = decode(cases["renew-detector"])
    object.__setattr__(getattr(record, field), "int", integer)
    with pytest.raises(s.VerificationError):
        lc.encode_ledger_command(record, expected_action="renew-detector")


@pytest.mark.parametrize("where", ("command", "part", "action", "carrier"))
def test_public_exact_types_reject_subclasses_before_callbacks(cases, where):
    class ForeignBytes(bytes):
        def __len__(self):
            pytest.fail("bytes subclass callback")

    class ForeignString(str):
        def __eq__(self, other):
            pytest.fail("string subclass callback")

    class ForeignCommand(lc.LedgerCommand):
        def __getattribute__(self, name):
            pytest.fail("carrier subclass callback")

    raw, parts = cases["install-policy"]
    with pytest.raises(s.VerificationError):
        if where == "carrier":
            lc.encode_ledger_command(
                object.__new__(ForeignCommand), expected_action="install-policy"
            )
        else:
            lc.decode_ledger_command(
                ForeignBytes(raw) if where == "command" else raw,
                (ForeignBytes(parts[0]), parts[1]) if where == "part" else parts,
                expected_action=ForeignString("install-policy")
                if where == "action"
                else "install-policy",
            )


@pytest.mark.parametrize("action", ACTIONS)
def test_int64_coordination_boundary_does_not_establish_revision_currentness(cases, action):
    row = json.loads(cases[action][0])
    row["expected_coordination_revision"] = 2**63 - 1
    assert decode((wire(row), cases[action][1])).expected_coordination_revision == 2**63 - 1
    row["expected_coordination_revision"] += 1
    with pytest.raises(s.VerificationError):
        decode((wire(row), cases[action][1]))
