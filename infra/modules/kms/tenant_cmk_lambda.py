"""
CMP-DEPLOY-05 §3.3 — Per-tenant KMS CMK provisioning Lambda.

Called by CMP-CP-02 synchronously at tenant onboarding.
Idempotent: returns the existing key ARN if the alias already exists.

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

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

REGION = os.environ["REGION"]
ACCOUNT_ID = os.environ["ACCOUNT_ID"]
WORKER_TASK_ROLE_ARN = os.environ["WORKER_TASK_ROLE_ARN"]


def _cmk_key_policy(org_id: str) -> str:
    """KMS key resource policy for a per-tenant CMK.

    Grants:
    - Account root: full key administration (key management only).
    - Worker task role: Decrypt + GenerateDataKey only when the caller's
      session name matches 'scan-*' (set by CMP-ORCH-03 per §6.1 step 4).
    - CMK provisioning Lambda role: DescribeKey, CreateAlias, EnableKeyRotation.
    """
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "RootAdmin",
                "Effect": "Allow",
                "Principal": {"AWS": f"arn:aws:iam::{ACCOUNT_ID}:root"},
                "Action": "kms:*",
                "Resource": "*",
            },
            {
                "Sid": "WorkerDecrypt",
                "Effect": "Allow",
                "Principal": {"AWS": WORKER_TASK_ROLE_ARN},
                "Action": ["kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"],
                "Resource": "*",
                "Condition": {
                    "StringLike": {
                        "aws:RoleSessionName": "scan-*"
                    },
                    "StringEquals": {
                        "kms:EncryptionContext:org_id": org_id
                    },
                },
            },
        ],
    })


def provision_tenant_cmk(org_id: str) -> str:
    """Create or return the existing per-tenant KMS CMK for org_id.

    Returns the CMK ARN (existing or newly created).
    Annual key rotation is enabled automatically (CLAR-DEPLOY-04).
    """
    kms = boto3.client("kms", region_name=REGION)
    alias = f"alias/scanipy-tenant-{org_id}"

    try:
        existing = kms.describe_key(KeyId=alias)
        arn = existing["KeyMetadata"]["Arn"]
        logger.info("tenant_cmk_exists", extra={"org_id": org_id, "arn": arn})
        return arn
    except kms.exceptions.NotFoundException:
        pass
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NotFoundException":
            pass
        else:
            raise

    key = kms.create_key(
        Description=f"Per-tenant CMK for org {org_id} (CMP-DEPLOY-05)",
        KeyUsage="ENCRYPT_DECRYPT",
        KeySpec="SYMMETRIC_DEFAULT",
        Policy=_cmk_key_policy(org_id),
        Tags=[
            {"TagKey": "org_id",    "TagValue": org_id},
            {"TagKey": "Component", "TagValue": "CMP-DEPLOY-05"},
            {"TagKey": "ManagedBy", "TagValue": "tenant-cmk-provisioner"},
        ],
    )
    key_id = key["KeyMetadata"]["KeyId"]
    arn = key["KeyMetadata"]["Arn"]

    kms.create_alias(AliasName=alias, TargetKeyId=key_id)
    kms.enable_key_rotation(KeyId=key_id)

    logger.info("tenant_cmk_created", extra={"org_id": org_id, "arn": arn})
    return arn


def provision_tenant_cmk_handler(event: dict, _context: object) -> dict:
    """Lambda entry point.

    Expected event: {"org_id": "<uuid>"}
    Returns:        {"cmk_arn": "<arn>"}
    """
    org_id = event.get("org_id")
    if not org_id:
        raise ValueError("event.org_id is required")

    cmk_arn = provision_tenant_cmk(org_id)
    return {"cmk_arn": cmk_arn}
