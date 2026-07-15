"""
CMP-DEPLOY-05 §3.3 — Per-tenant KMS CMK provisioning Lambda.

Called by CMP-CP-02 synchronously at tenant onboarding.
Idempotent: returns the existing key ARN if the alias already exists, and
re-ensures annual key rotation on that path (rotation-retry gap: a crash
between ``create_alias`` and ``enable_key_rotation`` on a prior invocation
must not leave a tenant CMK permanently unrotated).

Hardening (2026-07-15):
  * ``org_id`` is strictly validated as a canonical lowercase UUID BEFORE any
    interpolation into the KMS alias name or the key policy JSON. The ``orgs.id``
    column is ``uuid`` (db/migrations/versions/20260524_0001_initial_tenancy_tables.py),
    so anything else is a malformed or hostile input. Uppercase hex is rejected
    (not folded): KMS alias names are case-sensitive, so folding would let two
    spellings of one org id map to two different CMKs.
  * boto3/botocore are imported lazily so hermetic unit tests can import this
    module without the AWS SDK installed (repo precedent: OTel lazy import).
  * Environment variables are read lazily (not at import time) for the same
    reason; the deployed Lambda still fails fast on first invocation if the
    Terraform-injected environment is incomplete.

RULE-9: touches INV-3 (credential isolation substrate).
Security Analyst sign-off required before shipping changes.

Environment variables (injected by Terraform):
  REGION               — AWS region
  ACCOUNT_ID           — AWS account ID
  WORKER_TASK_ROLE_ARN — IAM role ARN the per-tenant CMK policy will grant
"""

import json
import logging
import os
import re
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Canonical lowercase UUID (matches the DB `orgs.id uuid` column rendered in
# its canonical text form). 36 chars, hex + hyphens only — no `/`, `..`, `*`,
# quotes, or anything else that could alter the alias path or the key-policy
# JSON it is interpolated into.
_ORG_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


@runtime_checkable
class KmsClient(Protocol):
    """Structural subset of the boto3 KMS client this Lambda depends on.

    Mirrors the ``KMSClient`` Protocol convention in
    ``services/credential_encryption.py``: only the methods this module calls
    are declared, so any boto3 KMS client (or the offline ``FakeKms`` in
    ``tests/unit/test_tenant_cmk_lambda.py``) satisfies it structurally —
    keeps ``kms``/``kms_client`` out of ANN401 (no bare ``Any`` params)
    without requiring boto3-stubs as a dependency.
    """

    def describe_key(self, *, KeyId: str) -> dict[str, Any]: ...  # noqa: N803

    def create_key(
        self,
        *,
        Description: str,  # noqa: N803
        KeyUsage: str,  # noqa: N803
        KeySpec: str,  # noqa: N803
        Policy: str,  # noqa: N803
        Tags: list[dict[str, str]],  # noqa: N803
    ) -> dict[str, Any]: ...

    def create_alias(self, *, AliasName: str, TargetKeyId: str) -> None: ...  # noqa: N803

    def enable_key_rotation(self, *, KeyId: str) -> None: ...  # noqa: N803


class OrgIdValidationError(ValueError):
    """The supplied org_id is not a canonical lowercase UUID.

    Raised BEFORE any KMS call and before any interpolation into the alias
    name or key-policy document (fail-closed input boundary).
    """


def validate_org_id(org_id: object) -> str:
    """Validate org_id as a canonical lowercase UUID; return it unchanged.

    The value is interpolated into ``alias/scanipy-tenant-{org_id}`` and into
    the CMK key-policy JSON (``kms:EncryptionContext:org_id``), so the format
    check is a hard security boundary, not a convenience.
    """
    if not isinstance(org_id, str):
        raise OrgIdValidationError(f"org_id must be a string, got {type(org_id).__name__}")
    if not _ORG_ID_RE.fullmatch(org_id):
        raise OrgIdValidationError(
            "org_id must be a canonical lowercase UUID "
            "(orgs.id is uuid per db/migrations 20260524_0001); "
            f"got {org_id!r}"
        )
    return org_id


def _require_env(name: str) -> str:
    """Read a required environment variable lazily; fail loudly if unset."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is not set")
    return value


def _cmk_key_policy(org_id: str, account_id: str, worker_task_role_arn: str) -> str:
    """KMS key resource policy for a per-tenant CMK.

    Grants:
    - Account root: full key administration (key management only).
    - Worker task role: Decrypt + GenerateDataKey only when the caller's
      session name matches 'scan-*' (set by CMP-ORCH-03 per §6.1 step 4)
      AND the encryption context carries this org_id.

    ``org_id`` MUST already have passed :func:`validate_org_id` — the caller
    (:func:`provision_tenant_cmk`) enforces this before interpolation.
    """
    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "RootAdmin",
                    "Effect": "Allow",
                    "Principal": {"AWS": f"arn:aws:iam::{account_id}:root"},
                    "Action": "kms:*",
                    "Resource": "*",
                },
                {
                    "Sid": "WorkerDecrypt",
                    "Effect": "Allow",
                    "Principal": {"AWS": worker_task_role_arn},
                    "Action": ["kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"],
                    "Resource": "*",
                    "Condition": {
                        "StringLike": {"aws:RoleSessionName": "scan-*"},
                        "StringEquals": {"kms:EncryptionContext:org_id": org_id},
                    },
                },
            ],
        }
    )


def _describe_existing_key(kms: KmsClient, alias: str) -> dict[str, Any] | None:
    """Return DescribeKey output for alias, or None if the alias does not exist."""
    try:
        result: dict[str, Any] = kms.describe_key(KeyId=alias)
        return result
    except Exception as exc:
        # botocore raises kms.exceptions.NotFoundException (a ClientError
        # subclass); fakes may raise a plain exception. Treat only a
        # NotFoundException (by type or by error code) as "no such alias".
        not_found = getattr(getattr(kms, "exceptions", None), "NotFoundException", ())
        if not_found and isinstance(exc, not_found):
            return None
        response = getattr(exc, "response", None)
        if isinstance(response, dict):
            code = response.get("Error", {}).get("Code")
            if code == "NotFoundException":
                return None
        raise


def provision_tenant_cmk(org_id: str, kms_client: KmsClient | None = None) -> str:
    """Create or return the existing per-tenant KMS CMK for org_id.

    Returns the CMK ARN (existing or newly created).
    Annual key rotation is enabled automatically (CLAR-DEPLOY-04) and
    re-ensured idempotently on the existing-key path, so a crash between
    ``create_alias`` and ``enable_key_rotation`` in an earlier invocation is
    healed on retry.

    ``kms_client`` is injectable for hermetic unit tests; production passes
    None and a boto3 client is created lazily.
    """
    org_id = validate_org_id(org_id)

    kms = kms_client
    if kms is None:
        # Lazy: hermetic unit runs need no AWS SDK. boto3-stubs/mypy-boto3 are
        # not a project dependency (this is the one file that does a *real*
        # boto3 client construction — every services/* Protocol is designed
        # to avoid that need, see credential_encryption.KMSClient); the
        # runtime object satisfies the KmsClient Protocol structurally.
        # No local `# type: ignore` needed: pyproject.toml's `[[tool.mypy.overrides]]`
        # for `boto3.*` (CLAR-DEPLOY-21, added by PR #313) already covers this import.
        import boto3

        kms = boto3.client("kms", region_name=_require_env("REGION"))

    alias = f"alias/scanipy-tenant-{org_id}"

    existing = _describe_existing_key(kms, alias)
    if existing is not None:
        key_id = existing["KeyMetadata"]["KeyId"]
        arn = str(existing["KeyMetadata"]["Arn"])
        # Rotation-retry gap fix: enable_key_rotation is idempotent — re-ensure
        # it even when the key already exists, before returning.
        kms.enable_key_rotation(KeyId=key_id)
        logger.info("tenant_cmk_exists", extra={"org_id": org_id, "arn": arn})
        return arn

    key = kms.create_key(
        Description=f"Per-tenant CMK for org {org_id} (CMP-DEPLOY-05)",
        KeyUsage="ENCRYPT_DECRYPT",
        KeySpec="SYMMETRIC_DEFAULT",
        Policy=_cmk_key_policy(
            org_id,
            account_id=_require_env("ACCOUNT_ID"),
            worker_task_role_arn=_require_env("WORKER_TASK_ROLE_ARN"),
        ),
        Tags=[
            {"TagKey": "org_id", "TagValue": org_id},
            {"TagKey": "Component", "TagValue": "CMP-DEPLOY-05"},
            {"TagKey": "ManagedBy", "TagValue": "tenant-cmk-provisioner"},
        ],
    )
    key_id = key["KeyMetadata"]["KeyId"]
    arn = str(key["KeyMetadata"]["Arn"])

    kms.create_alias(AliasName=alias, TargetKeyId=key_id)
    kms.enable_key_rotation(KeyId=key_id)

    logger.info("tenant_cmk_created", extra={"org_id": org_id, "arn": arn})
    return arn


def provision_tenant_cmk_handler(event: dict[str, Any], _context: object) -> dict[str, str]:
    """Lambda entry point.

    Expected event: {"org_id": "<canonical lowercase uuid>"}
    Returns:        {"cmk_arn": "<arn>"}

    Raises OrgIdValidationError (a ValueError) on a missing or malformed
    org_id — before any KMS client is even constructed.
    """
    org_id = event.get("org_id")
    if not org_id:
        raise OrgIdValidationError("event.org_id is required")

    cmk_arn = provision_tenant_cmk(validate_org_id(org_id))
    return {"cmk_arn": cmk_arn}
