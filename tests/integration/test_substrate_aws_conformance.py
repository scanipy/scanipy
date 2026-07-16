"""AWS-emulation conformance tests — CLAR-DEPLOY-21 honestly-emulatable slice.

============================ HONESTY BANNER (BINDING) ==========================
moto does not evaluate IAM/bucket/key policies — no test in this file may
assert access denial. moto emulates boto3/botocore API *mechanics* only: it
does not evaluate IAM session policies, S3 bucket policies, or KMS key
policies, so a deny assertion here would be vacuous by construction (a
non-enforcing emulator green is exactly the broken-implementation-passes
failure mode). Every negative below is a CLIENT-SIDE guard rejection
(services/substrate/object_store.py, pre-boto3-call) paired with a positive
control, or a pure construction/mechanics assertion. The policy-enforcement
negatives (real AccessDenied under a rendered session policy / bucket
prefix-deny / cross-tenant CMK) live in tests/integration/
test_tenant_isolation_live.py behind the ``aws_live`` marker and run only in
the manually-dispatched live-account window (SCANIPY_AWS_LIVE_TESTS=1).
================================================================================

What this file covers (decision record CLAR-DEPLOY-21, issue #283):
- AC-DEPLOY-05b key-resolution arm: S3 key-scheme round-trip on real botocore
  S3 semantics + client-side traversal rejection BEFORE any S3 call.
- AC-DEPLOY-01c conformance arm: real SQS RedrivePolicy DLQ-after-3 semantics
  (upgrading the in-memory StandardQueue model with actual RedrivePolicy JSON).
- KMS envelope mechanics (generate-data-key / encrypt / decrypt round trip).
- Secrets-Manager/STS session-policy render mechanics including the hard
  2048-char ``sts:AssumeRole`` inline session Policy size limit.

Review rule (DOC-DEPLOY-DECISIONS.md § CLAR-DEPLOY-21): any test asserting
AccessDenied/4xx produced by AWS policy evaluation must carry ``aws_live``;
any moto-backed negative must pair with a positive control.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import boto3
import pytest
from moto import mock_aws

from services.substrate.object_store import (
    CrossTenantAccessError,
    InMemoryObjectStore,
    ObjectStore,
    PathTraversalError,
    S3ObjectStore,
    SnapshotKeyBuilder,
)

pytestmark = pytest.mark.integration

_REGION = "us-east-1"
_BUCKET = "scanipy-test-snapshot"

_ORG_A = "11111111-1111-1111-1111-111111111111"
_ORG_B = "99999999-9999-9999-9999-999999999999"

_BUILDER_KW_A = {
    "org_id": _ORG_A,
    "codebase_id": "22222222-2222-2222-2222-222222222222",
    "commit_sha": "0123456789abcdef0123456789abcdef01234567",  # pragma: allowlist secret
    "env_digest": "sha256:" + "a" * 64,
}
_BUILDER_KW_B = {**_BUILDER_KW_A, "org_id": _ORG_B}


@pytest.fixture()
def moto_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """In-process moto backend with fake credentials pinned.

    The env pins guard against a developer's real AWS_PROFILE/credentials
    leaking into the (patched) botocore session — belt-and-braces on top of
    moto's own credential mocking. Millisecond startup, no docker (the reason
    moto won over LocalStack in CLAR-DEPLOY-21).
    """
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", _REGION)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with mock_aws():
        yield


@pytest.fixture()
def s3_client(moto_env: None) -> Any:
    client = boto3.client("s3", region_name=_REGION)
    client.create_bucket(Bucket=_BUCKET)
    return client


def _bucket_keys(s3_client: Any) -> list[str]:
    listed = s3_client.list_objects_v2(Bucket=_BUCKET)
    return [obj["Key"] for obj in listed.get("Contents", [])]


class _ExplodingClient:
    """A stand-in client that fails the test on ANY attribute access.

    Injected to prove the CLAR-DEPLOY-16 guard rejects a bad key BEFORE the
    adapter touches boto3 at all (not merely before the request is sent).
    """

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(
            f"S3 client attribute {name!r} was touched — the client-side guard "
            "must reject the key before any boto3 call"
        )


# --------------------------------------------------------------------------- #
# AC-DEPLOY-05b key-resolution arm — S3ObjectStore on real botocore semantics
# --------------------------------------------------------------------------- #


def test_s3_object_store_round_trip_at_clar_deploy_02_keys(s3_client: Any) -> None:
    """Positive control: all five CLAR-DEPLOY-02 snapshot keys round-trip on S3.

    Real botocore S3 key encoding/decoding (which InMemoryObjectStore cannot
    exercise) — the payload written at each SnapshotKeyBuilder key is read back
    byte-identical, and the persisted keys are exactly the minted keys.
    """
    store = S3ObjectStore(_BUCKET, client=s3_client)
    assert isinstance(store, ObjectStore)  # structural Protocol conformance
    builder = SnapshotKeyBuilder(**_BUILDER_KW_A)

    keys = builder.all_artifact_keys()
    for artifact_type, key in keys.items():
        payload = f"payload:{artifact_type}".encode()
        store.put(_ORG_A, key, payload)
        assert store.get(_ORG_A, key) == payload

    assert sorted(_bucket_keys(s3_client)) == sorted(keys.values())
    # INV-2 anchor: env_digest is carried in every persisted key path.
    assert all(_BUILDER_KW_A["env_digest"] in key for key in _bucket_keys(s3_client))


def test_s3_object_store_rejects_traversal_before_any_s3_call(s3_client: Any) -> None:
    """Client-side guard rejects traversal keys pre-call; nothing lands in S3.

    NOT a deny claim: moto enforces no policy. This asserts the CLAR-DEPLOY-16
    layer-1 *client-side* guard (same checks as InMemoryObjectStore) fires
    before boto3 is touched. The AWS-enforced deny for a key that slips past
    a buggy client lives in the aws_live twin (test_tenant_isolation_live.py).
    """
    # Traversal corpus from tests/unit/test_substrate.py (guard-level keys).
    traversal_keys = [
        f"orgs/{_ORG_A}/../escape",
        f"orgs/{_ORG_A}/%5c../escape",
        f"orgs/{_ORG_A}/a\\b/k",
        f"orgs/{_ORG_A}/%5C../escape",  # upper-case %5C (case-fold)
        f"orgs/{_ORG_A}/x\x00y",
        f"orgs/{_ORG_A}/%2e%2e/other",
    ]

    # (1) The guard fires before ANY boto3 attribute is touched.
    exploding_store = S3ObjectStore(_BUCKET, client=_ExplodingClient())
    for bad_key in traversal_keys:
        with pytest.raises(PathTraversalError):
            exploding_store.put(_ORG_A, bad_key, b"x")
        with pytest.raises(PathTraversalError):
            exploding_store.get(_ORG_A, bad_key)
    # A well-formed key resolving outside the requesting org's prefix is also
    # rejected client-side (guard mechanics, not an AWS policy deny).
    foreign_key = SnapshotKeyBuilder(**_BUILDER_KW_B).artifact_key("cpg_tarball")
    with pytest.raises(CrossTenantAccessError):
        exploding_store.put(_ORG_A, foreign_key, b"x")
    with pytest.raises(CrossTenantAccessError):
        exploding_store.get(_ORG_A, foreign_key)

    # (2) Against the real moto bucket: same rejections, and no object created.
    store = S3ObjectStore(_BUCKET, client=s3_client)
    for bad_key in traversal_keys:
        with pytest.raises(PathTraversalError):
            store.put(_ORG_A, bad_key, b"x")
    with pytest.raises(CrossTenantAccessError):
        store.put(_ORG_A, foreign_key, b"x")
    assert _bucket_keys(s3_client) == [], "a rejected key must never create an S3 object"

    # (3) Positive control: the same operation succeeds for the owning org, so
    # the rejections above cannot be empty-because-absent/broken-client greens.
    own_key = SnapshotKeyBuilder(**_BUILDER_KW_A).artifact_key("cpg_tarball")
    store.put(_ORG_A, own_key, b"own-org-payload")
    assert store.get(_ORG_A, own_key) == b"own-org-payload"
    assert _bucket_keys(s3_client) == [own_key]


def test_s3_list_under_org_prefix_returns_only_own_org_keys(s3_client: Any) -> None:
    """ListObjectsV2 under ``orgs/{org}/`` sees only that org's keys.

    Namespacing-by-construction on real S3 list semantics — explicitly NOT a
    deny claim (moto would happily serve org B's keys to an unscoped listing;
    the ListBucket s3:prefix session-policy condition is live-window evidence).
    """
    store = S3ObjectStore(_BUCKET, client=s3_client)
    keys_a = SnapshotKeyBuilder(**_BUILDER_KW_A).all_artifact_keys()
    keys_b = SnapshotKeyBuilder(**_BUILDER_KW_B).all_artifact_keys()
    for key in keys_a.values():
        store.put(_ORG_A, key, b"a")
    for key in keys_b.values():
        store.put(_ORG_B, key, b"b")

    listed_a = s3_client.list_objects_v2(Bucket=_BUCKET, Prefix=f"orgs/{_ORG_A}/")
    listed_keys_a = {obj["Key"] for obj in listed_a.get("Contents", [])}
    assert listed_keys_a == set(keys_a.values())  # positive control: own keys present
    assert not any(key.startswith(f"orgs/{_ORG_B}/") for key in listed_keys_a)

    listed_b = s3_client.list_objects_v2(Bucket=_BUCKET, Prefix=f"orgs/{_ORG_B}/")
    assert {obj["Key"] for obj in listed_b.get("Contents", [])} == set(keys_b.values())


def test_s3_object_store_matches_in_memory_fake_contract(s3_client: Any) -> None:
    """S3ObjectStore and InMemoryObjectStore agree on the ObjectStore contract.

    Guards against the fake and the production adapter drifting apart: same
    round-trip result, same rejection classes on the same inputs.
    """
    real = S3ObjectStore(_BUCKET, client=s3_client)
    fake = InMemoryObjectStore()
    key = SnapshotKeyBuilder(**_BUILDER_KW_A).artifact_key("precondition_status")
    for impl in (real, fake):
        impl.put(_ORG_A, key, b"parity")
        assert impl.get(_ORG_A, key) == b"parity"
        with pytest.raises(PathTraversalError):
            impl.put(_ORG_A, f"orgs/{_ORG_A}/../x", b"x")
        with pytest.raises(CrossTenantAccessError):
            impl.get(_ORG_A, f"orgs/{_ORG_B}/x")


# --------------------------------------------------------------------------- #
# AC-DEPLOY-01c conformance arm — real SQS RedrivePolicy DLQ-after-3
# --------------------------------------------------------------------------- #


def test_sqs_redrive_policy_dlq_after_3_receives(moto_env: None) -> None:
    """A poison message redrives to the DLQ after 3 receives (maxReceiveCount=3).

    Upgrades AC-DEPLOY-01c from the in-memory StandardQueue model to real SQS
    RedrivePolicy JSON semantics (CLAR-DEPLOY-06 max-receive 3). Mechanics
    only — no policy evaluation involved.
    """
    sqs = boto3.client("sqs", region_name=_REGION)
    dlq_url = sqs.create_queue(QueueName="scanipy-test-snapshot-dlq")["QueueUrl"]
    dlq_arn = sqs.get_queue_attributes(QueueUrl=dlq_url, AttributeNames=["QueueArn"])["Attributes"][
        "QueueArn"
    ]
    main_url = sqs.create_queue(
        QueueName="scanipy-test-snapshot",
        Attributes={
            "RedrivePolicy": json.dumps({"deadLetterTargetArn": dlq_arn, "maxReceiveCount": "3"}),
        },
    )["QueueUrl"]

    def _receive(queue_url: str) -> list[dict[str, Any]]:
        response = sqs.receive_message(
            QueueUrl=queue_url, MaxNumberOfMessages=10, VisibilityTimeout=0
        )
        return list(response.get("Messages", []))

    # Positive control: a healthy message is received once, deleted, and never
    # appears on the DLQ — so the poison assertions below cannot pass vacuously.
    sqs.send_message(QueueUrl=main_url, MessageBody=json.dumps({"snapshot_id": "healthy"}))
    healthy = _receive(main_url)
    assert len(healthy) == 1
    sqs.delete_message(QueueUrl=main_url, ReceiptHandle=healthy[0]["ReceiptHandle"])
    assert _receive(main_url) == []
    assert _receive(dlq_url) == []

    # Poison message: received (and not deleted) 3 times — still on the main
    # queue, not yet redriven.
    sqs.send_message(QueueUrl=main_url, MessageBody=json.dumps({"snapshot_id": "poison"}))
    for attempt in range(1, 4):
        messages = _receive(main_url)
        assert len(messages) == 1, f"receive {attempt} should redeliver the poison message"
    # The 4th receive attempt finds the main queue empty: SQS redrove the
    # message to the DLQ once its receive count exceeded maxReceiveCount=3.
    assert _receive(main_url) == []
    dlq_messages = _receive(dlq_url)
    assert len(dlq_messages) == 1, "poison message did not land in the DLQ after 3 receives"
    assert json.loads(dlq_messages[0]["Body"]) == {"snapshot_id": "poison"}


# --------------------------------------------------------------------------- #
# KMS envelope mechanics — AC-DEPLOY-01e conformance arm (mechanics only)
# --------------------------------------------------------------------------- #


def test_kms_envelope_generate_data_key_decrypt_round_trip(moto_env: None) -> None:
    """KMS envelope mechanics on real botocore shapes: GenerateDataKey → Decrypt.

    Positive-control mechanics for the envelope scheme CMP-CP-02 relies on
    (CLAR-DEPLOY-04). The cross-tenant kms:Decrypt DENY under a rendered
    session policy is NOT asserted here — moto does not evaluate key/session
    policies; that negative lives in the aws_live twin.
    """
    kms = boto3.client("kms", region_name=_REGION)
    cmk_arn = kms.create_key(Description="scanipy tenant CMK (test)")["KeyMetadata"]["Arn"]

    data_key = kms.generate_data_key(KeyId=cmk_arn, KeySpec="AES_256")
    assert len(data_key["Plaintext"]) == 32  # AES_256 data key
    assert data_key["CiphertextBlob"] != data_key["Plaintext"]

    # Envelope open: decrypting the ciphertext blob yields the same data key,
    # attributed to the same CMK.
    opened = kms.decrypt(CiphertextBlob=data_key["CiphertextBlob"])
    assert opened["Plaintext"] == data_key["Plaintext"]
    assert opened["KeyId"] == cmk_arn

    # Direct encrypt/decrypt mechanics under the CMK also round-trip.
    ciphertext = kms.encrypt(KeyId=cmk_arn, Plaintext=b"scanipy-envelope-probe")["CiphertextBlob"]
    assert kms.decrypt(CiphertextBlob=ciphertext)["Plaintext"] == b"scanipy-envelope-probe"


# --------------------------------------------------------------------------- #
# Session-policy render mechanics — Secrets Manager + STS (CLAR-DEPLOY-21)
# --------------------------------------------------------------------------- #

# Mirror of the session-policy template stored by infra/tenant-isolation-apply.sh
# in Secrets Manager (scanipy/{env}/worker-session-policy-template) and defined
# in infra/modules/compute/session_policy.tf. Duplicated here BY DESIGN
# (CLAR-DEPLOY-21: tests/ must not edit or import infra/; duplicate coverage is
# acceptable, conflicting files are not). If the template statements change in
# infra, update this mirror in the same PR — the size assertion below is the
# CI-side early-red for the hard 2048-char sts:AssumeRole inline-policy limit.
_SESSION_POLICY_SECRET = "scanipy/prod/worker-session-policy-template"


def _session_policy_template(env: str) -> str:
    snapshot = f"scanipy-{env}-snapshot"
    witness = f"scanipy-{env}-witness"
    sarif = f"scanipy-{env}-sarif"
    tenant_objects = [
        f"arn:aws:s3:::{snapshot}/orgs/${{TEMPLATE_ORG_ID}}/*",
        f"arn:aws:s3:::{witness}/orgs/${{TEMPLATE_ORG_ID}}/*",
        f"arn:aws:s3:::{sarif}/orgs/${{TEMPLATE_ORG_ID}}/*",
    ]
    buckets = [f"arn:aws:s3:::{snapshot}", f"arn:aws:s3:::{witness}", f"arn:aws:s3:::{sarif}"]
    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "S3PerTenantAllow",
                    "Effect": "Allow",
                    "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
                    "Resource": tenant_objects,
                },
                {
                    "Sid": "S3PlatformReadOnly",
                    "Effect": "Allow",
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{snapshot}/_platform/*"],
                },
                {
                    "Sid": "S3PerTenantListBucket",
                    "Effect": "Allow",
                    "Action": ["s3:ListBucket"],
                    "Resource": buckets,
                    "Condition": {
                        "StringLike": {"s3:prefix": ["orgs/${TEMPLATE_ORG_ID}/*", "_platform/*"]}
                    },
                },
                {
                    "Sid": "S3OtherOrgsDeny",
                    "Effect": "Deny",
                    "Action": ["s3:*"],
                    "NotResource": [
                        *tenant_objects,
                        f"arn:aws:s3:::{snapshot}/_platform/*",
                        *buckets,
                    ],
                },
                {
                    "Sid": "KMSPerTenantAllow",
                    "Effect": "Allow",
                    "Action": ["kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"],
                    "Resource": ["${TEMPLATE_TENANT_CMK_ARN}"],
                },
                {
                    "Sid": "KMSOtherCMKsDeny",
                    "Effect": "Deny",
                    "Action": ["kms:Decrypt", "kms:GenerateDataKey"],
                    "NotResource": ["${TEMPLATE_TENANT_CMK_ARN}"],
                },
            ],
        }
    )


def test_session_policy_template_renders_and_fits_sts_2048_char_limit(moto_env: None) -> None:
    """Template render mechanics + the hard 2048-char sts:AssumeRole Policy limit.

    Render/plumbing only: seeds moto Secrets Manager with the session-policy
    template, substitutes TEMPLATE_ORG_ID / TEMPLATE_TENANT_CMK_ARN at
    worst-case realistic widths (36-char UUID org id, full-length CMK ARN),
    asserts the rendered policy fits the hard AWS limit of 2048 characters for
    an inline sts:AssumeRole session Policy, and that sts.assume_role accepts
    it mechanically. Whether the policy DENIES anything is not observable in
    moto and is asserted only in the aws_live twin.
    """
    template = _session_policy_template("prod")

    # Secrets Manager plumbing: the template survives the store/fetch round
    # trip byte-identically (this is how CMP-ORCH-03 obtains it at scan launch).
    secretsmanager = boto3.client("secretsmanager", region_name=_REGION)
    secretsmanager.create_secret(Name=_SESSION_POLICY_SECRET, SecretString=template)
    fetched = secretsmanager.get_secret_value(SecretId=_SESSION_POLICY_SECRET)["SecretString"]
    assert fetched == template

    # Render at worst-case realistic substitution widths.
    org_id = "11111111-1111-1111-1111-111111111111"
    cmk_arn = "arn:aws:kms:us-east-1:508703380027:key/22222222-2222-2222-2222-222222222222"
    rendered = fetched.replace("${TEMPLATE_ORG_ID}", org_id).replace(
        "${TEMPLATE_TENANT_CMK_ARN}", cmk_arn
    )
    assert "${TEMPLATE_" not in rendered, "unsubstituted template placeholder left in policy"

    parsed = json.loads(rendered)
    assert [statement["Sid"] for statement in parsed["Statement"]] == [
        "S3PerTenantAllow",
        "S3PlatformReadOnly",
        "S3PerTenantListBucket",
        "S3OtherOrgsDeny",
        "KMSPerTenantAllow",
        "KMSOtherCMKsDeny",
    ]

    # The hard AWS limit: an inline session Policy passed to sts:AssumeRole is
    # at most 2048 characters. Trip this early in CI rather than at scan time.
    # (If this fires after a template change, compacting the template is a
    # RULE-9 Security-Analyst-reviewed change to session_policy.tf.)
    assert len(rendered) <= 2048, (
        f"rendered session policy is {len(rendered)} chars — exceeds the hard "
        "2048-char sts:AssumeRole inline-policy limit"
    )

    # STS plumbing: assume_role accepts the rendered policy mechanically.
    # moto does NOT evaluate the policy — this proves parameter shape only.
    sts = boto3.client("sts", region_name=_REGION)
    response = sts.assume_role(
        RoleArn="arn:aws:iam::123456789012:role/scanipy-ecs-worker",
        RoleSessionName="scan-conformance-probe",
        Policy=rendered,
        DurationSeconds=900,
    )
    credentials = response["Credentials"]
    assert credentials["AccessKeyId"] and credentials["SecretAccessKey"]
