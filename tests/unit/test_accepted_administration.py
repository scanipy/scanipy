"""Pure administration, using disposable fixture signatures, never installed keys."""

import copy
import hashlib
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest

from services.scan.accepted_inputs import codec as c
from services.scan.accepted_inputs import models as m
from services.scan.accepted_inputs import schemas as s
from services.scan.accepted_inputs import verify as v
from tests import accepted_input_fixtures as f

pytestmark = pytest.mark.unit
material = f.material
test_only_keys = f.test_only_keys


def signed(material, role):
    return material.objects[role], material.objects[role + "-signature"]


def resign(material, role, changes=None, edit=None):
    schema = s.POLICY if "policy" in role else s.ADMISSION
    document = c.decode_document(material.objects[role], schema)
    document.update(changes or {})
    if edit is not None:
        edit(document)
    raw = c.encode_document(document, schema)
    return raw, f.sign(material.root, schema, raw)


def publication(material):
    return f.frame(
        s.PUBLICATION_INPUT, m.record_dict(material.request.expected_bundle), material.objects
    )


def invoke(material, action, **changes):
    request = material.request
    common = {"trust": request.installed_trust}
    if action in ("policy", "admission", "current"):
        common["root_spki"] = f.spki(material.root)
    if action == "policy":
        args = dict(policy=signed(material, "current-policy"), previous=None, **common)
    elif action == "admission":
        args = dict(
            checkpoint=signed(material, "admission-checkpoint"),
            policy=signed(material, "current-policy"),
            previous=None,
            **common,
        )
    elif action == "current":
        args = dict(
            live=request.live_authority_evidence,
            expected=request.admission,
            reference_time=request.reference_time,
            **common,
        )
    else:
        args = dict(
            bundle=request.bundle,
            publication_input=changes["publication_input"]
            if "publication_input" in changes
            else publication(material),
            expected_bundle=request.expected_bundle,
            **common,
        )
        if action == "publication":
            args.update(admission=request.admission, reference_time="2026-09-25T00:00:20.000000Z")
        else:
            args.update(
                receipt=material.objects["publication-receipt"], publisher_artifact_digest="1" * 64
            )
    args.update(changes)
    return getattr(v, "verify_admin_" + action)(**args)


@pytest.mark.parametrize(
    "action", ["policy", "admission", "current", "publication", "publication_receipt"]
)
def test_five_real_owner_apis(material, action):
    result = invoke(material, action)
    if action in ("policy", "admission"):
        assert result is None
    elif action == "current":
        assert type(result) is m.VerifiedCurrentPolicy
        assert result.permission_expires_at == "2026-09-26T00:00:00.000000Z"
    else:
        assert type(result) is m.VerificationChecks
        expected = v.verify_request(
            material.publication() if action == "publication" else material.historical()
        )
        if action == "publication_receipt":
            expected = replace(expected, verified_at="2026-09-25T00:00:20.000000Z")
        assert result == expected


def test_historical_receipt_has_original_time_and_no_current_authority(material):
    result = invoke(material, "publication_receipt")
    assert result.verified_at == "2026-09-25T00:00:20.000000Z"
    assert result.publication_receipt_digest == c.domain_digest(
        s.PUBLICATION, material.objects["publication-receipt"]
    )
    for name in (
        "qualified_rule_digest",
        "execution_authorization_digest",
        "current_policy_digest",
        "current_policy_revision",
        "checkpoint_digest",
        "checkpoint_generation",
        "admission_epoch",
        "permission_expires_at",
    ):
        assert getattr(result, name) is None
    # No now/clock/current-policy parameter, no mode/SEALED synthesis needed.
    assert result.verified_at != material.request.reference_time


@pytest.mark.parametrize(
    "action", ["policy", "admission", "current", "publication", "publication_receipt"]
)
@pytest.mark.parametrize(
    "field,value",
    [
        ("scope", "global"),
        ("registry_id", UUID(int=999)),
        ("org_id", UUID(int=999)),
        ("root_spki_sha256", "0" * 64),
    ],
)
def test_trust_scope_and_root_fences(material, action, field, value):
    changes = {field: value}
    if field == "scope":
        changes["org_id"] = None
    trust = replace(material.request.installed_trust, **changes)
    with pytest.raises(s.VerificationError):
        invoke(material, action, trust=trust)


@pytest.mark.parametrize(
    "action", ["policy", "admission", "current", "publication", "publication_receipt"]
)
@pytest.mark.parametrize(
    "poison", ["uuid-int", "missing-uuid-int", "missing-slot", "text", "subclass"]
)
def test_poisoned_trust_rejected_before_hash_or_crypto(material, action, poison, monkeypatch):
    trust = copy.deepcopy(material.request.installed_trust)

    class Bomb:
        def __str__(self):
            pytest.fail("caller formatting")

        def __format__(self, _spec):
            pytest.fail("caller formatting")

        def __eq__(self, _other):
            pytest.fail("caller comparison")

    if poison == "uuid-int":
        object.__setattr__(trust.registry_id, "int", Bomb())
    elif poison == "missing-uuid-int":
        object.__delattr__(trust.registry_id, "int")
    elif poison == "missing-slot":
        object.__delattr__(trust, "registry_id")
    elif poison == "text":
        object.__setattr__(trust, "scope", Bomb())
    else:

        class Text(str):
            def __eq__(self, _other):
                pytest.fail("subclass comparison")

        object.__setattr__(trust, "scope", Text("customer"))
    # Build request frame before blocking the hash helpers used by fixtures.
    kwargs = (
        {}
        if action in ("policy", "admission", "current")
        else {"publication_input": publication(material)}
    )

    def no_caller_hash(data):
        pytest.fail("unvalidated trust reached hashing")

    monkeypatch.setattr(c, "raw_digest", no_caller_hash)
    with pytest.raises(s.VerificationError):
        invoke(material, action, trust=trust, **kwargs)


@pytest.mark.parametrize("part", [0, 1])
@pytest.mark.parametrize("bad", [b"", b"x", bytearray(b"x"), None])
def test_signed_parts_exact_bounded(material, part, bad):
    value = list(signed(material, "current-policy"))
    value[part] = bad
    with pytest.raises(s.VerificationError):
        invoke(material, "policy", policy=tuple(value))


@pytest.mark.parametrize("bad", [[], (), (b"x",), (b"x", b"y", b"z")])
def test_signed_pair_closed(material, bad):
    with pytest.raises(s.VerificationError):
        invoke(material, "policy", policy=bad)


def policy_successor(material, **changes):
    return resign(
        material,
        "current-policy",
        dict(
            event_id=f.uid(901),
            revision=2,
            previous_policy_digest=c.domain_digest(s.POLICY, material.objects["current-policy"]),
            **changes,
        ),
    )


def test_adjacent_policy_successor_and_tombstone(material):
    old = signed(material, "current-policy")
    new = policy_successor(material)
    invoke(material, "policy", policy=new, previous=old)
    retired = resign(
        material,
        "current-policy",
        {
            "event_id": f.uid(901),
            "revision": 2,
            "previous_policy_digest": c.domain_digest(s.POLICY, old[0]),
        },
        lambda d: d["grants"][0].update(status="retired", status_changed_at="2026-09-25T01:00:00Z"),
    )
    invoke(material, "policy", policy=retired, previous=old)
    document = c.decode_document(new[0], s.POLICY)
    document.update(
        event_id=f.uid(902),
        revision=3,
        previous_policy_digest=c.domain_digest(s.POLICY, retired[0]),
    )
    raw = c.encode_document(document, s.POLICY)
    with pytest.raises(s.VerificationError, match="grant-denied"):
        invoke(
            material, "policy", policy=(raw, f.sign(material.root, s.POLICY, raw)), previous=retired
        )


@pytest.mark.parametrize(
    "case", ["missing", "same", "skip", "wrong-predecessor", "drop", "changed-key", "new-outside"]
)
def test_policy_successor_failures(material, case):
    prior = signed(material, "current-policy")
    new = policy_successor(material)
    document = c.decode_document(new[0], s.POLICY)
    if case == "missing":
        prior = None
    elif case == "same":
        new = prior
    elif case == "skip":
        document["revision"] = 3
    elif case == "wrong-predecessor":
        document["previous_policy_digest"] = "0" * 64
    elif case == "drop":
        document["grants"] = []
    elif case == "changed-key":
        document["grants"][0]["key_version"] = 2
    else:
        grant = dict(
            document["grants"][0],
            grant_id=f.uid(903),
            key_version=2,
            not_before="2026-09-24T00:00:00Z",
        )
        document["grants"].append(grant)
    if case != "same":
        raw = c.encode_document(document, s.POLICY)
        new = raw, f.sign(material.root, s.POLICY, raw)
    with pytest.raises(s.VerificationError):
        invoke(material, "policy", policy=new, previous=prior)


def test_initial_policy_checks_all_grant_intervals(material):
    bad = resign(
        material,
        "current-policy",
        edit=lambda d: d["grants"][0].update(not_before="2026-09-24T00:00:00Z"),
    )
    with pytest.raises(s.VerificationError, match="grant-denied"):
        invoke(material, "policy", policy=bad)


@pytest.mark.parametrize("action", ["admit", "block"])
def test_admission_adjacent_and_block_are_only_structure(material, action):
    prior = signed(material, "admission-checkpoint")
    new = resign(
        material,
        "admission-checkpoint",
        {
            "generation": 2,
            "event_id": f.uid(910),
            "previous_checkpoint_digest": c.domain_digest(s.ADMISSION, prior[0]),
            "action": action,
        },
    )
    invoke(material, "admission", checkpoint=new, previous=prior)


@pytest.mark.parametrize(
    "field,value",
    [
        ("generation", 3),
        ("previous_checkpoint_digest", "0" * 64),
        ("deployment_id", f.uid(990)),
        ("administrator_actor_id", f.uid(990)),
        ("policy_revision", 2),
        ("policy_digest", "0" * 64),
    ],
)
def test_admission_successor_binding_failures(material, field, value):
    prior = signed(material, "admission-checkpoint")
    changes = {
        "generation": 2,
        "event_id": f.uid(910),
        "previous_checkpoint_digest": c.domain_digest(s.ADMISSION, prior[0]),
        field: value,
    }
    new = resign(material, "admission-checkpoint", changes)
    with pytest.raises(s.VerificationError):
        invoke(material, "admission", checkpoint=new, previous=prior)


@pytest.mark.parametrize(
    "time", ["2026-09-24T23:59:59.999999Z", "2026-09-26T00:00:00.000000Z", "bad"]
)
def test_current_time_bounds(material, time):
    with pytest.raises(s.VerificationError):
        invoke(material, "current", reference_time=time)


def test_current_never_chooses_issuer_expiration(material):
    policy = resign(
        material,
        "current-policy",
        edit=lambda d: d["grants"][0].update(not_after="2026-09-25T00:03:00Z"),
    )
    checkpoint = resign(
        material, "admission-checkpoint", {"policy_digest": c.domain_digest(s.POLICY, policy[0])}
    )
    material.objects.update(
        {
            "current-policy": policy[0],
            "current-policy-signature": policy[1],
            "admission-checkpoint": checkpoint[0],
            "admission-checkpoint-signature": checkpoint[1],
        }
    )
    expected = replace(
        material.request.admission,
        policy_digest=c.domain_digest(s.POLICY, policy[0]),
        checkpoint_digest=c.domain_digest(s.ADMISSION, checkpoint[0]),
    )
    live = f.frame(
        s.LIVE,
        {
            **{key: c.decode_document(policy[0], s.POLICY)[key] for key in s.NAMESPACE},
            **m.record_dict(expected),
        },
        material.objects,
    )
    result = invoke(material, "current", live=live, expected=expected)
    assert result.permission_expires_at == "2026-09-26T00:00:00.000000Z"


@pytest.mark.parametrize(
    "field,value",
    [
        ("approval_event_id", f.uid(999)),
        ("publication_key", f.uid(999)),
        ("bundle_id", f.uid(999)),
        ("accepted_content_digest", "0" * 64),
        ("approval_statement_digest", "0" * 64),
        ("approval_signature_sha256", "0" * 64),
        ("evidence_inventory_digest", "0" * 64),
        ("policy_digest", "0" * 64),
        ("policy_revision", 2),
        ("checkpoint_digest", "0" * 64),
        ("checkpoint_generation", 2),
        ("admission_epoch", f.uid(999)),
        ("publisher_actor_id", f.uid(999)),
        ("publisher_artifact_digest", "0" * 64),
        ("published_at", "2026-09-26T00:00:00.000000Z"),
    ],
)
def test_every_historical_receipt_link(material, field, value):
    document = c.decode_document(material.objects["publication-receipt"], s.PUBLICATION)
    document[field] = value
    with pytest.raises(s.VerificationError):
        invoke(material, "publication_receipt", receipt=c.encode_document(document, s.PUBLICATION))


@pytest.mark.parametrize(
    "role", ["current-policy-signature", "admission-checkpoint-signature", "approval-signature"]
)
def test_actual_signature_failure_has_private_cause(material, role):
    material.objects[role] = b"x" * 384
    with pytest.raises(s.VerificationError, match="signature-invalid") as caught:
        invoke(material, "publication")
    assert caught.value.__cause__ is not None


@pytest.mark.parametrize("action", ["current", "publication", "publication_receipt"])
@pytest.mark.parametrize("malformed", [b"", b"x", b"[]", b"\xff"])
def test_malformed_authority_is_not_accepted(material, action, malformed):
    field = "live" if action == "current" else "publication_input"
    with pytest.raises(s.VerificationError):
        invoke(material, action, **{field: malformed})


@pytest.mark.parametrize(
    "name,ceiling", [("hashes", 100000), ("size", 134217728), ("loads", 8), ("verifies", 12)]
)
def test_fixed_meter_boundary_no_refunds(name, ceiling):
    work = v._AdminWork()
    work.reserve(**{name: ceiling})
    assert getattr(work, name) == ceiling
    with pytest.raises(s.VerificationError, match="invalid-input"):
        work.reserve(**{name: 1})
    assert getattr(work, name) == ceiling + 1
    with pytest.raises(s.VerificationError):
        work.reserve()


@pytest.mark.parametrize(
    "action", ["policy", "admission", "current", "publication", "publication_receipt"]
)
def test_actual_sha_load_and_rsa_work_is_precharged(material, action, monkeypatch):
    # Prepare ALL fixture work before instrumentation; calling fixtures while
    # metering would falsely attribute test signing/preparation to a verifier.
    request = material.request
    raw = publication(material)
    root_spki = f.spki(material.root)
    args = {"trust": request.installed_trust}
    if action == "policy":
        args.update(policy=signed(material, "current-policy"), previous=None, root_spki=root_spki)
    elif action == "admission":
        args.update(
            checkpoint=signed(material, "admission-checkpoint"),
            policy=signed(material, "current-policy"),
            previous=None,
            root_spki=root_spki,
        )
    elif action == "current":
        args.update(
            live=request.live_authority_evidence,
            expected=request.admission,
            reference_time=request.reference_time,
            root_spki=root_spki,
        )
    else:
        args.update(
            bundle=request.bundle, publication_input=raw, expected_bundle=request.expected_bundle
        )
        if action == "publication":
            args.update(admission=request.admission, reference_time="2026-09-25T00:00:20.000000Z")
        else:
            args.update(
                receipt=material.objects["publication-receipt"], publisher_artifact_digest="1" * 64
            )
    captured = []
    init = v._AdminWork.__init__

    def start(work):
        init(work)
        captured.append(work)

    monkeypatch.setattr(v._AdminWork, "__init__", start)
    counts = {"hashes": 0, "size": 0, "loads": 0, "verifies": 0}
    sha, load, signature = hashlib.sha256, v.serialization.load_der_public_key, v._signature

    def charged_sha(data=b"", **kwargs):
        counts["hashes"] += 1
        counts["size"] += len(data)
        assert counts["hashes"] <= captured[0].hashes
        assert counts["size"] <= captured[0].size
        return sha(data, **kwargs)

    def charged_load(data):
        counts["loads"] += 1
        assert counts["loads"] <= captured[0].loads
        return load(data)

    def charged_signature(*values):
        counts["verifies"] += 1
        assert counts["verifies"] <= captured[0].verifies
        return signature(*values)

    monkeypatch.setattr(hashlib, "sha256", charged_sha)
    monkeypatch.setattr(v.serialization, "load_der_public_key", charged_load)
    monkeypatch.setattr(v, "_signature", charged_signature)
    getattr(v, "verify_admin_" + action)(**args)
    assert len(captured) == 1
    assert counts["loads"] == (2 if action.startswith("publication") else 1)
    assert counts["verifies"] == (
        3 if action.startswith("publication") else 2 if action in ("admission", "current") else 1
    )


@pytest.mark.parametrize("method", ["layout", "content", "members"])
def test_repeated_composite_calls_never_refund(method):
    work = v._AdminWork()
    work.model_count, work.model_size, work.total, work.payload = 1, 100, 1000, 900
    work.detectors = work.rules = 1
    getattr(work, method)()
    first = work.hashes, work.size
    getattr(work, method)()
    assert (work.hashes, work.size) == (first[0] * 2, first[1] * 2)


def test_publication_does_not_construct_verifier_request_or_sealed(material, monkeypatch):
    raw = publication(material)

    def forbidden(*args, **kwargs):
        pytest.fail("fabricated request or frame")

    monkeypatch.setattr(m.VerifierRequest, "__init__", forbidden)
    monkeypatch.setattr(c, "encode_frame", forbidden)
    result = v.verify_admin_publication_receipt(
        material.request.bundle,
        raw,
        material.objects["publication-receipt"],
        trust=material.request.installed_trust,
        expected_bundle=material.request.expected_bundle,
        publisher_artifact_digest="1" * 64,
    )
    assert result.execution_authorization_digest is None


def test_operational_runner_still_refuses_without_any_verification(monkeypatch):
    monkeypatch.setattr(
        v, "verify_admin_current", lambda *a, **k: pytest.fail("production fallback")
    )
    with pytest.raises(s.VerificationError, match="runtime-unsupported"):
        v.run_isolated_verifier(None, profile=None)


def multi_bundle(*, bad_last=False, global_scope=False):
    """Two raw-distinct artifacts, two detectors/four bilingual rules; fixture only."""
    folder = Path(__file__).parents[1] / "fixtures" / "semantic_g1"
    model = (folder / "operation_models.json").read_bytes()
    base_rule = c.parse_json((folder / "rules.json").read_bytes(), canonical=False)
    base = f.bundle_fixture()
    manifest, _ = c.decode_spec(base.spec_bytes)
    template = manifest["detectors"][0]
    manifest["detectors"], manifest["models"] = [], []
    detectors, rules, models = [], [], [model, model + b"\n"]
    if global_scope:
        manifest.update(scope="global", org_id=None)
    for d in range(2):
        model_digest = c.raw_digest(models[d])
        manifest["models"].append(
            {
                "artifact_id": f"model-{d}",
                "version": "1.0.0",
                "schema": s.MODEL,
                "raw_sha256": model_digest,
            }
        )
        detector = c.decode_document(base.detector_blobs[0], s.DETECTOR)
        detector.update(
            id=f"detector-{d}",
            languages=["python", "java"],
            rule_ids=[f"rule-{d}-0", f"rule-{d}-1"],
            profiles=[
                {
                    "language": lang,
                    "projection_profile": s.PROJECTION,
                    "source_syntax_schema": s.SOURCE_SYNTAX,
                }
                for lang in ("python", "java")
            ],
        )
        detector_raw = c.encode_document(detector, s.DETECTOR)
        detectors.append(detector_raw)
        member = copy.deepcopy(template)
        member.update(
            detector_id=detector["id"],
            detector_sha256=c.raw_digest(detector_raw),
            language_profiles=detector["profiles"],
            rules=[],
        )
        for r in range(2):
            rule = copy.deepcopy(base_rule)
            rule.update(spec_id=f"rule-{d}-{r}", model_artifact_digest=model_digest)
            if bad_last and d == r == 1:
                # Raw/header bindings still match; only the owning semantic
                # decoder can reject this last unsupported selector.
                rule["clauses"][-1]["selector"]["model_id"] = "java.unapproved/1"
            rule_raw = c.canonical_bytes(rule)
            rules.append(rule_raw)
            rule_hash = c.raw_digest(rule_raw)
            semantic = {
                "schema": s.SEMANTIC_BINDING,
                "rule_raw_sha256": rule_hash,
                "model_raw_sha256": model_digest,
                "semantics": s.SEMANTICS,
                "projection_profile": s.PROJECTION,
            }
            member["rules"].append(
                {
                    "rule_id": rule["spec_id"],
                    "artifact_id": rule["spec_id"],
                    "version": "1.0.0",
                    "schema": s.RULE,
                    "raw_sha256": rule_hash,
                    "semantics": s.SEMANTICS,
                    "projection_profile": s.PROJECTION,
                    "model_artifact_id": f"model-{d}",
                    "model_raw_sha256": model_digest,
                    "semantic_descriptor_digest": c.domain_digest(
                        s.SEMANTIC_BINDING, c.encode_document(semantic, s.SEMANTIC_BINDING)
                    ),
                }
            )
        manifest["detectors"].append(member)
    return m.AcceptedBundleBytes(
        c.encode_spec(c.encode_document(manifest, s.S_MANIFEST), tuple(models)),
        tuple(detectors),
        tuple(rules),
    )


def rebound_publication(material, bundle):
    manifest, _ = c.decode_spec(bundle.spec_bytes)
    namespace = {name: manifest[name] for name in s.NAMESPACE}
    digest = c.accepted_content_digest(bundle)
    expected = replace(
        material.request.expected_bundle,
        scope=manifest["scope"],
        org_id=None if manifest["org_id"] is None else UUID(manifest["org_id"]),
        accepted_content_digest=digest,
    )
    trust = replace(material.request.installed_trust, scope=expected.scope, org_id=expected.org_id)
    objects = dict(material.objects)
    policy = c.decode_document(objects["current-policy"], s.POLICY)
    policy.update(namespace)
    for grant in policy["grants"]:
        grant.update(scope=expected.scope, org_id=namespace["org_id"])
    policy_raw = c.encode_document(policy, s.POLICY)
    policy_digest = c.domain_digest(s.POLICY, policy_raw)
    adoption = c.decode_document(objects["operator-adoption"], s.ADOPTION)
    adoption.update(namespace, accepted_content_digest=digest)
    objects["operator-adoption"] = c.encode_document(adoption, s.ADOPTION)
    inventory = c.decode_document(objects["approval-evidence-inventory"], s.INVENTORY)
    inventory["objects"][0].update(
        length=len(objects["operator-adoption"]),
        raw_sha256=c.raw_digest(objects["operator-adoption"]),
    )
    objects["approval-evidence-inventory"] = c.encode_document(inventory, s.INVENTORY)
    inventory_digest = c.domain_digest(s.INVENTORY, objects["approval-evidence-inventory"])
    approval = c.decode_document(objects["approval-statement"], s.APPROVAL)
    approval.update(
        namespace,
        accepted_content_digest=digest,
        trust_policy_digest=policy_digest,
        evidence_inventory_digest=inventory_digest,
    )
    objects["approval-statement"] = c.encode_document(approval, s.APPROVAL)
    objects["approval-signature"] = f.sign(
        material.issuer, s.APPROVAL, objects["approval-statement"]
    )
    objects["current-policy"] = policy_raw
    objects["current-policy-signature"] = f.sign(material.root, s.POLICY, policy_raw)
    checkpoint = c.decode_document(objects["admission-checkpoint"], s.ADMISSION)
    checkpoint.update(namespace, policy_digest=policy_digest)
    objects["admission-checkpoint"] = c.encode_document(checkpoint, s.ADMISSION)
    objects["admission-checkpoint-signature"] = f.sign(
        material.root, s.ADMISSION, objects["admission-checkpoint"]
    )
    admission = replace(
        material.request.admission,
        policy_digest=policy_digest,
        checkpoint_digest=c.domain_digest(s.ADMISSION, objects["admission-checkpoint"]),
    )
    return {
        "bundle": bundle,
        "publication_input": f.frame(s.PUBLICATION_INPUT, m.record_dict(expected), objects),
        "trust": trust,
        "expected_bundle": expected,
        "admission": admission,
        "reference_time": "2026-09-25T00:00:20.000000Z",
    }


@pytest.mark.parametrize("bad_last", [False, True])
def test_all_members_and_languages_and_late_failure_are_metered(material, bad_last, monkeypatch):
    from analysis.ifds import bound_rules

    args = rebound_publication(material, multi_bundle(bad_last=bad_last))
    original = bound_rules.decode_bound_rule
    seen = []

    def observed(*values, **kwargs):
        seen.append((kwargs["key"].rule_id, kwargs["language"]))
        return original(*values, **kwargs)

    monkeypatch.setattr(bound_rules, "decode_bound_rule", observed)
    if bad_last:
        with pytest.raises(s.VerificationError, match="unsupported-schema"):
            v.verify_admin_publication(**args)
        assert seen[-1] == ("rule-1-1", "python")  # Every nested row is checked even for Python.
        assert len(seen) == 7
    else:
        v.verify_admin_publication(**args)
        assert seen == [
            (f"rule-{d}-{r}", lang)
            for d in range(2)
            for r in range(2)
            for lang in ("python", "java")
        ]


def test_existing_b_global_publication_is_unchanged_but_admin_ingress_rejects(material):
    args = rebound_publication(material, multi_bundle(global_scope=True))
    request = replace(
        material.publication(),
        bundle=args["bundle"],
        installed_trust=args["trust"],
        expected_bundle=args["expected_bundle"],
        admission=args["admission"],
        authority_evidence=args["publication_input"],
    )
    assert (
        v.verify_request(request).accepted_content_digest
        == args["expected_bundle"].accepted_content_digest
    )
    with pytest.raises(s.VerificationError, match="unsupported-schema"):
        v.verify_admin_publication(**args)


@pytest.mark.parametrize(
    "helper",
    [
        "layout",
        "content",
        "members",
        "key",
        "frame",
        "policy",
        "checkpoint",
        "approval",
        "admission",
    ],
)
def test_helper_precharge_exhaustion_precedes_actual_owner_call(material, helper, monkeypatch):
    work = v._AdminWork()
    bundle = v._admin_bundle(material.request.bundle, work)
    frame = c.decode_frame(publication(material), s.PUBLICATION_INPUT)
    trust = m.record_dict(material.request.installed_trust)
    policy = frame.document("current-policy")
    checkpoint = frame.document("admission-checkpoint")
    now = v._instant("2026-09-25T00:00:20.000000Z")
    root = material.root.public_key()
    work.hashes = 100000
    work.verifies = 12

    def forbidden(*_args, **_kwargs):
        pytest.fail("owner called after exhausted reservation")

    names = {
        "key": (v, "_key"),
        "frame": (c, "decode_frame"),
        "policy": (v, "_policy"),
        "checkpoint": (v, "_checkpoint"),
        "approval": (v, "_approval"),
        "admission": (v, "_admission_expected"),
    }
    if helper in names:
        monkeypatch.setattr(*names[helper], forbidden)
    arguments = {
        "key": (b"x", "0" * 64),
        "frame": (b"x", s.LIVE),
        "policy": (frame, root, trust),
        "checkpoint": (frame, root, trust, policy, now),
        "approval": (frame, m.record_dict(material.request.expected_bundle), policy, now),
        "admission": (frame, checkpoint, policy, material.request.admission),
    }
    assert bundle.spec_bytes == material.request.bundle.spec_bytes
    with pytest.raises(s.VerificationError):
        getattr(work, helper)(*arguments.get(helper, ()))


@pytest.mark.parametrize(
    "kind", ["bad-prefix", "last-model-hash", "last-rule-hash", "last-semantics"]
)
def test_malformed_delegate_paths_stay_inside_each_prepaid_hash_budget(material, kind, monkeypatch):
    bundle = multi_bundle(bad_last=kind == "last-semantics")
    expected = dict(
        m.record_dict(material.request.expected_bundle),
        accepted_content_digest=c.accepted_content_digest(bundle),
    )
    if kind == "bad-prefix":
        object.__setattr__(bundle, "spec_bytes", b"bad")
    elif kind == "last-model-hash":
        object.__setattr__(bundle, "spec_bytes", bundle.spec_bytes[:-1] + b"x")
    elif kind == "last-rule-hash":
        object.__setattr__(
            bundle, "rule_blobs", (*bundle.rule_blobs[:-1], bundle.rule_blobs[-1] + b" ")
        )
        expected["accepted_content_digest"] = c.accepted_content_digest(bundle)
    work = v._AdminWork()
    original_sha = hashlib.sha256
    original_reserve = work.reserve
    spent = [0, 0]
    credit = [0, 0]

    def reserve(**kwargs):
        original_reserve(**kwargs)
        # A new explicit helper reservation starts a new exact local allowance,
        # so earlier 20k discovery slack cannot hide a later missing precharge.
        spent[:] = [0, 0]
        credit[:] = [kwargs.get("hashes", 0), kwargs.get("size", 0)]

    def sha(data=b"", **kwargs):
        spent[0] += 1
        spent[1] += len(data)
        assert spent[0] <= credit[0]
        assert spent[1] <= credit[1]
        return original_sha(data, **kwargs)

    monkeypatch.setattr(work, "reserve", reserve)
    monkeypatch.setattr(hashlib, "sha256", sha)
    with pytest.raises(s.VerificationError):
        snapshot = v._admin_bundle(bundle, work)
        v._bundle_material(snapshot, expected, work)


@pytest.mark.parametrize("field", ["detector_blobs", "rule_blobs", "spec_bytes"])
def test_poisoned_bundle_is_shape_checked_before_discovery(material, field, monkeypatch):
    bundle = copy.deepcopy(material.request.bundle)

    class Poison:
        def __iter__(self):
            pytest.fail("caller iteration")

        def __len__(self):
            pytest.fail("caller length")

    object.__setattr__(bundle, field, Poison())
    monkeypatch.setattr(c, "decode_spec", lambda *_: pytest.fail("prevalidation delegate"))
    with pytest.raises(s.VerificationError):
        v._admin_bundle(bundle, v._AdminWork())


def test_caller_uuid_and_slots_can_change_after_private_snapshot(material, monkeypatch):
    trusted = copy.deepcopy(material.request.installed_trust)
    expected = copy.deepcopy(material.request.admission)
    original = c.raw_digest

    def mutate(data):
        object.__setattr__(trusted.registry_id, "int", -1)
        object.__setattr__(trusted, "root_spki_sha256", "0" * 64)
        object.__setattr__(expected.admission_epoch, "int", -1)
        return original(data)

    monkeypatch.setattr(c, "raw_digest", mutate)
    result = invoke(material, "current", trust=trusted, expected=expected)
    assert result.admission_epoch == material.request.admission.admission_epoch


@pytest.mark.parametrize(
    "target,field",
    [
        ("expected", "admission_epoch"),
        ("expected", "policy_revision"),
        ("expected_bundle", "bundle_id"),
        ("expected_bundle", "S_version"),
    ],
)
def test_expectation_slots_reject_poison_before_wire_conversion(
    material, target, field, monkeypatch
):
    value = copy.deepcopy(
        material.request.admission if target == "expected" else material.request.expected_bundle
    )

    class Poison:
        def __str__(self):
            pytest.fail("unvalidated conversion")

        def __format__(self, _):
            pytest.fail("unvalidated conversion")

    member = getattr(value, field)
    if type(member) is UUID:
        object.__setattr__(member, "int", Poison())
    else:
        object.__setattr__(value, field, Poison())
    raw = publication(material)
    monkeypatch.setattr(
        c, "decode_record", lambda *a: pytest.fail("owner conversion before validation")
    )
    if target == "expected":
        # Trust is another validated record, so target the exact record helper
        # rather than confusing its earlier legitimate decode with this one.
        rules, kind = s.ADMISSION_EXPECTATION, m.AdmissionExpectation
    else:
        rules, kind = s.BUNDLE_EXPECTATION, m.BundleExpectation
    assert raw
    with pytest.raises(s.VerificationError):
        v._admin_record(value, kind, rules)


@pytest.mark.parametrize("field", ["spec_bytes", "detector_blobs", "rule_blobs"])
def test_bundle_preallocation_caps_before_any_decode(material, field, monkeypatch):
    bundle = copy.deepcopy(material.request.bundle)
    value = b"x" * (s.MAX_CONTENT + 1) if field == "spec_bytes" else (b"x",) * (s.MAX_VALUES + 1)
    object.__setattr__(bundle, field, value)
    monkeypatch.setattr(c, "decode_spec", lambda *_: pytest.fail("oversize count reached decoder"))
    with pytest.raises(s.VerificationError):
        v._admin_bundle(bundle, v._AdminWork())


def test_aggregate_content_cap_precedes_discovery(material, monkeypatch):
    bundle = copy.deepcopy(material.request.bundle)
    object.__setattr__(bundle, "detector_blobs", (b"x" * s.MAX_CONTENT,))
    monkeypatch.setattr(
        c, "decode_spec", lambda *_: pytest.fail("aggregate overrun reached decoder")
    )
    with pytest.raises(s.VerificationError):
        v._admin_bundle(bundle, v._AdminWork())


def test_discovery_precharge_blocks_at_n_plus_one(material, monkeypatch):
    work = v._AdminWork()
    work.hashes = 80001
    monkeypatch.setattr(c, "decode_spec", lambda *_: pytest.fail("discovery before reservation"))
    with pytest.raises(s.VerificationError):
        v._admin_bundle(material.request.bundle, work)
    assert work.hashes == 100001


@pytest.mark.parametrize("helper", ["frame", "key"])
def test_repeated_malformed_helpers_keep_full_reservations(helper):
    work = v._AdminWork()
    for attempt in (1, 2):
        with pytest.raises(s.VerificationError):
            if helper == "frame":
                work.frame(b"wrong frame", s.LIVE)
            else:
                work.key(b"wrong der", hashlib.sha256(b"wrong der").hexdigest())
        assert work.hashes == attempt * (4 if helper == "frame" else 1)
        assert work.size == attempt * len(b"wrong frame" if helper == "frame" else b"wrong der")
        assert work.loads == (0 if helper == "frame" else attempt)


@pytest.mark.parametrize("action", ["current", "publication"])
def test_current_block_checkpoint_never_becomes_permission(material, action):
    raw, signature = resign(material, "admission-checkpoint", {"action": "block"})
    material.objects.update(
        {"admission-checkpoint": raw, "admission-checkpoint-signature": signature}
    )
    admission = replace(
        material.request.admission, checkpoint_digest=c.domain_digest(s.ADMISSION, raw)
    )
    if action == "current":
        live = f.frame(
            s.LIVE,
            {
                **{key: c.decode_document(raw, s.ADMISSION)[key] for key in s.NAMESPACE},
                **m.record_dict(admission),
            },
            material.objects,
        )
        kwargs = {"live": live, "expected": admission}
    else:
        kwargs = {"admission": admission}
    with pytest.raises(s.VerificationError, match="checkpoint-denied"):
        invoke(material, action, **kwargs)


@pytest.mark.parametrize(
    "role,field,value",
    [
        ("approval-statement", "approval_kind", "statistical"),
        ("operator-adoption", "proposal_id", f.uid(999)),
        ("approval-evidence-inventory", "approval_kind", "statistical"),
    ],
)
def test_inferred_or_statistical_material_cannot_be_relabelled(material, role, field, value):
    schema = dict(s.PUBLICATION_ROLES)[role]
    document = c.decode_document(material.objects[role], schema)
    document[field] = value
    malformed = c.canonical_bytes(document)
    original = publication(material)
    frame = c.decode_frame(original, s.PUBLICATION_INPUT)
    manifest = frame.manifest
    objects = list(frame.objects)
    index = [name for name, _ in s.PUBLICATION_ROLES].index(role)
    objects[index] = malformed
    manifest["objects"][index].update(length=len(malformed), raw_sha256=c.raw_digest(malformed))
    # Build only a deliberately invalid test vector; production encode_frame
    # correctly refuses it. Original framing is schema LF plus u64 parts.
    parts = [c.canonical_bytes(manifest), *objects]
    forged = (
        s.PUBLICATION_INPUT.encode()
        + b"\n"
        + b"".join(len(p).to_bytes(8, "big") + p for p in parts)
    )
    with pytest.raises(s.VerificationError):
        invoke(material, "publication", publication_input=forged)
