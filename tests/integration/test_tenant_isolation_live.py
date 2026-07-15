"""Live-account tenant-isolation enforcement negatives — ``aws_live`` twins.

CLAR-DEPLOY-21 honesty partition: moto and LocalStack-CE do not evaluate IAM
session policies, S3 bucket policies, or KMS key policies, so the REAL deny
observations for AC-DEPLOY-05a/05b's enforcement arms live here and run ONLY
in a manually-dispatched live-account window (SCANIPY_AWS_LIVE_TESTS=1,
credentials via the OIDC deploy role, account 508703380027). The dated run URL
of that window — never this marker's existence — is the WBS §21 /
STATUS-AWS-TEAM evidence.

Discipline (binding, from the decision record):
- Every deny assertion pairs with a positive control (the same operation
  succeeds for the owning org), so empty-because-absent can never pass as
  denied.
- Inside the window these tests FAIL LOUDLY on missing prerequisites (absent
  buckets/secret/CMKs/role surface as errors or assertion failures) — no
  nested skips beyond the single SCANIPY_AWS_LIVE_TESTS gate, so a live window
  cannot silently green.

Prerequisites the window must provision first (STATUS-AWS-TEAM rows 8/10):
- The three data-plane buckets + orgs/ prefix-deny bucket policies
  (infra/tenant-isolation-apply.sh).
- The session-policy template secret scanipy/{env}/worker-session-policy-template.
- The worker task role (default arn:aws:iam::508703380027:role/scanipy-ecs-worker,
  override via SCANIPY_LIVE_WORKER_ROLE_ARN) assumable by the window
  credentials, with its KMS grants keyed to session names ``scan-*``.
- Two tenant CMKs with aliases alias/scanipy-tenant-{org} for the org ids in
  SCANIPY_LIVE_TENANT_ORG_A / SCANIPY_LIVE_TENANT_ORG_B (provision via the
  tenant-CMK Lambda; defaults below are the dedicated live-test tenants).
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError

pytestmark = [
    pytest.mark.integration,
    pytest.mark.aws_live,
    pytest.mark.skipif(
        os.environ.get("SCANIPY_AWS_LIVE_TESTS") != "1",
        reason=(
            "policy-enforcement negatives run only in the live AWS account window "
            "(SCANIPY_AWS_LIVE_TESTS=1)"
        ),
    ),
]

LIVE_ACCOUNT_ID = "508703380027"
_ENV = os.environ.get("SCANIPY_LIVE_ENV", "prod")
_REGION = os.environ.get("SCANIPY_LIVE_REGION", "us-east-1")
_SNAPSHOT_BUCKET = f"scanipy-{_ENV}-snapshot"
_SESSION_POLICY_SECRET = f"scanipy/{_ENV}/worker-session-policy-template"
_WORKER_ROLE_ARN = os.environ.get(
    "SCANIPY_LIVE_WORKER_ROLE_ARN",
    f"arn:aws:iam::{LIVE_ACCOUNT_ID}:role/scanipy-ecs-worker",
)
# Dedicated live-test tenant org ids (tenant CMKs provisioned once per account
# via the tenant-CMK Lambda; see module docstring). Override to point at any
# two existing tenants.
_TENANT_ORG_A = os.environ.get("SCANIPY_LIVE_TENANT_ORG_A", "live-isolation-a")
_TENANT_ORG_B = os.environ.get("SCANIPY_LIVE_TENANT_ORG_B", "live-isolation-b")

# A syntactically valid, deliberately nonexistent CMK ARN for renders whose
# test only exercises the S3 statements — keeps the S3 deny test independent
# of CMK provisioning. STS validates policy syntax, not resource existence.
_DUMMY_CMK_ARN = f"arn:aws:kms:{_REGION}:{LIVE_ACCOUNT_ID}:key/00000000-0000-0000-0000-000000000000"


def _base_session() -> Any:
    """Window credentials (OIDC deploy role), pinned to the intended account.

    Fails loudly — never skips — if the window points anywhere but the
    Scanipy live account, so a misconfigured window cannot green (or trash
    another account).
    """
    session = boto3.session.Session(region_name=_REGION)
    identity = session.client("sts").get_caller_identity()
    assert identity["Account"] == LIVE_ACCOUNT_ID, (
        f"live window is running against account {identity['Account']}, "
        f"expected {LIVE_ACCOUNT_ID} — refusing to continue"
    )
    return session


def _rendered_session_policy(session: Any, org_id: str, cmk_arn: str) -> str:
    """Fetch the template from Secrets Manager and substitute per-scan values.

    Same mechanics CMP-ORCH-03 performs at scan launch. A missing secret
    raises ClientError (loud failure — prerequisite not provisioned).
    """
    template = session.client("secretsmanager").get_secret_value(SecretId=_SESSION_POLICY_SECRET)[
        "SecretString"
    ]
    rendered = template.replace("${TEMPLATE_ORG_ID}", org_id).replace(
        "${TEMPLATE_TENANT_CMK_ARN}", cmk_arn
    )
    assert "${TEMPLATE_" not in rendered, "unsubstituted placeholder in session policy"
    assert len(rendered) <= 2048, (
        f"rendered session policy is {len(rendered)} chars — exceeds the hard "
        "2048-char sts:AssumeRole inline-policy limit"
    )
    return rendered


def _assume_org_scoped_session(session: Any, org_id: str, cmk_arn: str) -> Any:
    """Assume the worker role under the rendered per-org session policy.

    Session name matches ``scan-*`` (the tenant CMK key policy conditions
    worker access on that pattern — infra/modules/kms/tenant_cmk_lambda.py).
    """
    credentials = session.client("sts").assume_role(
        RoleArn=_WORKER_ROLE_ARN,
        RoleSessionName=f"scan-live-{uuid.uuid4().hex[:12]}",
        Policy=_rendered_session_policy(session, org_id, cmk_arn),
        DurationSeconds=900,
    )["Credentials"]
    return boto3.session.Session(
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
        region_name=_REGION,
    )


def _tenant_cmk_arn(session: Any, org_id: str) -> str:
    """Resolve alias/scanipy-tenant-{org_id}; loud ClientError if absent."""
    key_metadata = session.client("kms").describe_key(KeyId=f"alias/scanipy-tenant-{org_id}")
    return str(key_metadata["KeyMetadata"]["Arn"])


def _error_code(exc_info: pytest.ExceptionInfo[ClientError]) -> str:
    return str(exc_info.value.response["Error"]["Code"])


def test_deploy_05a_live_session_policy_denies_cross_org_s3() -> None:
    """Org-A session policy: s3:GetObject on orgs/B/... is AccessDenied for real.

    Test id: TST-AC-DEPLOY-05a (S3 enforcement arm, live twin of the moto
        key-resolution tests in test_substrate_aws_conformance.py).
    Deny observed: real AWS IAM evaluation of the rendered session policy
        (S3PerTenantAllow scoping + S3OtherOrgsDeny NotResource statement).
    Positive control: the same GetObject succeeds for the owning org's key
        under the same session, so the deny cannot be empty-because-absent.
    """
    base = _base_session()
    s3_base = base.client("s3")
    run_id = uuid.uuid4().hex[:12]
    org_a, org_b = f"live-a-{run_id}", f"live-b-{run_id}"
    key_a = f"orgs/{org_a}/isolation-probe/{run_id}.txt"
    key_b = f"orgs/{org_b}/isolation-probe/{run_id}.txt"

    # Seed both orgs' objects with the (unrestricted) window credentials.
    # Missing bucket → loud ClientError: prerequisite not provisioned.
    s3_base.put_object(Bucket=_SNAPSHOT_BUCKET, Key=key_a, Body=b"org-a-artifact")
    s3_base.put_object(Bucket=_SNAPSHOT_BUCKET, Key=key_b, Body=b"org-b-artifact")
    try:
        scoped = _assume_org_scoped_session(base, org_a, _DUMMY_CMK_ARN)
        s3_scoped = scoped.client("s3")

        # Positive control FIRST: the org-A session reads org-A's artifact.
        own = s3_scoped.get_object(Bucket=_SNAPSHOT_BUCKET, Key=key_a)["Body"].read()
        assert own == b"org-a-artifact"

        # The REAL deny: same session, org-B key → AccessDenied from AWS.
        with pytest.raises(ClientError) as denied:
            s3_scoped.get_object(Bucket=_SNAPSHOT_BUCKET, Key=key_b)
        assert _error_code(denied) == "AccessDenied"

        # Writes across the boundary are denied too.
        with pytest.raises(ClientError) as denied_write:
            s3_scoped.put_object(Bucket=_SNAPSHOT_BUCKET, Key=key_b, Body=b"overwrite")
        assert _error_code(denied_write) == "AccessDenied"
        # And org B's artifact is untouched.
        remained = s3_base.get_object(Bucket=_SNAPSHOT_BUCKET, Key=key_b)["Body"].read()
        assert remained == b"org-b-artifact"
    finally:
        for key in (key_a, key_b):
            s3_base.delete_object(Bucket=_SNAPSHOT_BUCKET, Key=key)


def test_deploy_05a_live_cross_tenant_cmk_decrypt_denied() -> None:
    """Org-A session cannot kms:Decrypt ciphertext bound to org-B's CMK.

    Test id: TST-AC-DEPLOY-05a (KMS layer-3 enforcement arm, live).
    Deny observed: real AWS evaluation of the rendered session policy's
        KMSPerTenantAllow/KMSOtherCMKsDeny statements (+ the per-tenant CMK
        key policy) on a cross-tenant kms:Decrypt.
    Positive control: org-B's own session generates AND decrypts the same
        data key successfully, so the ciphertext is demonstrably decryptable.
    Prerequisite (loud failure if absent): tenant CMKs for both org ids —
        provision via the tenant-CMK Lambda before the window.
    """
    base = _base_session()
    cmk_a = _tenant_cmk_arn(base, _TENANT_ORG_A)
    cmk_b = _tenant_cmk_arn(base, _TENANT_ORG_B)
    assert cmk_a != cmk_b, "tenant CMK aliases resolve to the same key — invalid fixture"

    # Org-B scoped session: envelope data key under org-B's CMK.
    scoped_b = _assume_org_scoped_session(base, _TENANT_ORG_B, cmk_b)
    kms_b = scoped_b.client("kms")
    data_key = kms_b.generate_data_key(KeyId=cmk_b, KeySpec="AES_256")

    # Positive control: org B decrypts its own ciphertext under its session.
    opened_by_owner = kms_b.decrypt(CiphertextBlob=data_key["CiphertextBlob"])
    assert opened_by_owner["Plaintext"] == data_key["Plaintext"]

    # The REAL deny: an org-A scoped session (allow-listed only for cmk_a,
    # explicit deny on every other CMK) cannot decrypt org-B ciphertext.
    scoped_a = _assume_org_scoped_session(base, _TENANT_ORG_A, cmk_a)
    with pytest.raises(ClientError) as denied:
        scoped_a.client("kms").decrypt(CiphertextBlob=data_key["CiphertextBlob"])
    assert _error_code(denied) == "AccessDenied"


def test_deploy_05b_live_bucket_policy_prefix_deny() -> None:
    """Bucket policy denies object access outside orgs/* and _platform/* prefixes.

    Test id: TST-AC-DEPLOY-05b (bucket-policy enforcement arm, live twin of
        the moto key-resolution/namespacing tests).
    Deny observed: real AWS evaluation of the DenyNonTenantObjectPaths bucket
        policy (Principal "*", NotResource orgs/* + _platform/*) applied by
        infra/tenant-isolation-apply.sh — it denies even the window's
        unrestricted credentials, which is exactly the point.
    Positive control: the same credentials put/get/delete under orgs/... just
        fine, so the deny is attributable to the prefix, not broken creds.
    Prerequisite (loud failure if absent): the bucket + its prefix-deny policy
        (STATUS-AWS-TEAM row 8). If the policy is missing, the stray put
        SUCCEEDS and the pytest.raises below fails the test — honest red.
    """
    base = _base_session()
    s3 = base.client("s3")
    run_id = uuid.uuid4().hex[:12]
    stray_key = f"stray/{run_id}/escape.txt"
    tenant_key = f"orgs/live-05b-{run_id}/probe.txt"

    try:
        # Positive control: tenant-prefixed object access works end to end.
        s3.put_object(Bucket=_SNAPSHOT_BUCKET, Key=tenant_key, Body=b"tenant-prefixed")
        fetched = s3.get_object(Bucket=_SNAPSHOT_BUCKET, Key=tenant_key)["Body"].read()
        assert fetched == b"tenant-prefixed"

        # The REAL deny: writing outside orgs/* and _platform/* is refused by
        # the bucket policy for ANY principal.
        with pytest.raises(ClientError) as denied_put:
            s3.put_object(Bucket=_SNAPSHOT_BUCKET, Key=stray_key, Body=b"escape")
        assert _error_code(denied_put) == "AccessDenied"

        # Reading a non-tenant path is denied as well (GetObject is in the
        # deny action list, so the error is AccessDenied, not NoSuchKey).
        with pytest.raises(ClientError) as denied_get:
            s3.get_object(Bucket=_SNAPSHOT_BUCKET, Key=stray_key)
        assert _error_code(denied_get) == "AccessDenied"
    finally:
        # Best-effort cleanup; the stray delete is itself expected to be
        # denied when the policy is in place (DeleteObject is denied too).
        s3.delete_object(Bucket=_SNAPSHOT_BUCKET, Key=tenant_key)
        try:
            s3.delete_object(Bucket=_SNAPSHOT_BUCKET, Key=stray_key)
        except ClientError as cleanup_error:
            if cleanup_error.response["Error"]["Code"] != "AccessDenied":
                raise


def test_live_window_marker_discipline() -> None:
    """The live window itself is running with the gate env var set.

    A canary that the module actually executed in the window (its pass proves
    the gate fired), guarding the no-nested-skips rule: any prerequisite
    failure in the tests above must surface as a loud error/assertion — the
    only skip this module may ever report is the SCANIPY_AWS_LIVE_TESTS gate.
    """
    assert os.environ.get("SCANIPY_AWS_LIVE_TESTS") == "1"
