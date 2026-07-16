"""CMP-DEPLOY-05 §3.1 — worker session-policy template renderer (Layer 1).

Single source of truth for the per-scan IAM session policy JSON. Three
consumers stay in lockstep through this module:

1. ``infra/tenant-isolation-apply.sh`` renders the *template* (placeholders
   intact) and stores it in Secrets Manager
   (``scanipy/{env}/worker-session-policy-template``).
2. ``CMP-ORCH-03`` substitutes ``TEMPLATE_ORG_ID`` / ``TEMPLATE_TENANT_CMK_ARN``
   per scan and passes the result as the ``Policy`` parameter of
   ``sts:AssumeRole`` (:func:`render_worker_session_policy`).
3. ``tests/unit/test_session_policy_template.py`` is the CI-runnable guard for
   the hard AWS limit: an inline ``sts:AssumeRole`` session policy must be
   **<= 2048 characters** (CLAR-DEPLOY-21 decision record). Exceeding it makes
   every scan launch fail at runtime, so the ceiling is enforced here and in CI.

The template mirrors ``infra/modules/compute/session_policy.tf`` statement for
statement (sids S3PerTenantAllow, S3PlatformReadOnly, S3PerTenantListBucket,
S3OtherOrgsDeny, KMSPerTenantAllow, KMSOtherCMKsDeny). If you change one, you
must change the other — the unit test cross-checks the .tf file's sids.

RULE-9: INV-3-adjacent (tenant CMK scope). Security Analyst sign-off required
on changes.
"""

from __future__ import annotations

import json
import re
from typing import Any

#: Hard AWS limit on the inline ``Policy`` parameter of ``sts:AssumeRole``.
MAX_SESSION_POLICY_CHARS = 2048

#: org_id format — canonical lowercase UUID; the DB ``orgs.id`` column is
#: ``uuid`` (db/migrations 20260524_0001). Enforced BEFORE substitution into
#: the policy so a hostile org_id can never widen an ARN pattern.
ORG_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

#: Per-tenant KMS CMK ARN shape (key id is itself a UUID).
TENANT_CMK_ARN_RE = re.compile(
    r"^arn:aws:kms:[a-z0-9-]+:\d{12}:key/"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

_ORG_PLACEHOLDER = "${TEMPLATE_ORG_ID}"
_CMK_PLACEHOLDER = "${TEMPLATE_TENANT_CMK_ARN}"

#: The six statement sids, in template order (must match session_policy.tf).
SESSION_POLICY_SIDS: tuple[str, ...] = (
    "S3PerTenantAllow",
    "S3PlatformReadOnly",
    "S3PerTenantListBucket",
    "S3OtherOrgsDeny",
    "KMSPerTenantAllow",
    "KMSOtherCMKsDeny",
)


class SessionPolicyError(ValueError):
    """Base error for session-policy rendering failures (fail-closed)."""


class OrgIdFormatError(SessionPolicyError):
    """org_id is not a canonical lowercase UUID."""


class TenantCmkArnFormatError(SessionPolicyError):
    """tenant_cmk_arn is not a well-formed KMS key ARN."""


class SessionPolicyTooLargeError(SessionPolicyError):
    """The rendered policy exceeds the 2048-char sts:AssumeRole limit."""


def data_plane_buckets(env: str = "prod") -> tuple[str, str, str]:
    """The three data-plane bucket names (snapshot, witness, sarif).

    Must match ``infra/modules/compute/session_policy.tf`` locals and
    ``infra/modules/dataplane/main.tf``.
    """
    return (f"scanipy-{env}-snapshot", f"scanipy-{env}-witness", f"scanipy-{env}-sarif")


def build_session_policy_template(env: str = "prod") -> dict[str, Any]:
    """The session-policy template as a dict, placeholders intact."""
    snapshot, witness, sarif = data_plane_buckets(env)
    org = _ORG_PLACEHOLDER
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "S3PerTenantAllow",
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
                "Resource": [
                    f"arn:aws:s3:::{snapshot}/orgs/{org}/*",
                    f"arn:aws:s3:::{witness}/orgs/{org}/*",
                    f"arn:aws:s3:::{sarif}/orgs/{org}/*",
                ],
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
                "Resource": [
                    f"arn:aws:s3:::{snapshot}",
                    f"arn:aws:s3:::{witness}",
                    f"arn:aws:s3:::{sarif}",
                ],
                "Condition": {"StringLike": {"s3:prefix": [f"orgs/{org}/*", "_platform/*"]}},
            },
            {
                "Sid": "S3OtherOrgsDeny",
                "Effect": "Deny",
                "Action": ["s3:*"],
                "NotResource": [
                    f"arn:aws:s3:::{snapshot}/orgs/{org}/*",
                    f"arn:aws:s3:::{witness}/orgs/{org}/*",
                    f"arn:aws:s3:::{sarif}/orgs/{org}/*",
                    f"arn:aws:s3:::{snapshot}/_platform/*",
                    f"arn:aws:s3:::{snapshot}",
                    f"arn:aws:s3:::{witness}",
                    f"arn:aws:s3:::{sarif}",
                ],
            },
            {
                "Sid": "KMSPerTenantAllow",
                "Effect": "Allow",
                "Action": ["kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"],
                "Resource": [_CMK_PLACEHOLDER],
            },
            {
                "Sid": "KMSOtherCMKsDeny",
                "Effect": "Deny",
                "Action": ["kms:Decrypt", "kms:GenerateDataKey"],
                "NotResource": [_CMK_PLACEHOLDER],
            },
        ],
    }


def render_session_policy_template(env: str = "prod") -> str:
    """Template JSON exactly as stored in Secrets Manager by the apply script.

    ``json.dumps`` default separators — matches the value stored by
    ``infra/tenant-isolation-apply.sh`` on 2026-06-10, so a re-run of the
    script is a no-op unless the template genuinely changed.
    """
    return json.dumps(build_session_policy_template(env))


def render_worker_session_policy(org_id: str, tenant_cmk_arn: str, env: str = "prod") -> str:
    """Substitute a validated org_id + CMK ARN; enforce the 2048-char ceiling.

    This is the CMP-ORCH-03 entry point (§6.1 step 3). Both inputs are format
    checked BEFORE substitution: a non-UUID org_id (e.g. ``*`` or a traversal
    payload) could otherwise widen the Allow ARNs or narrow the Deny ARNs.
    """
    if not ORG_ID_RE.fullmatch(org_id):
        raise OrgIdFormatError(
            f"org_id must be a canonical lowercase UUID, got {org_id!r} "
            "(orgs.id is uuid per db/migrations 20260524_0001)"
        )
    if not TENANT_CMK_ARN_RE.fullmatch(tenant_cmk_arn):
        raise TenantCmkArnFormatError(
            f"tenant_cmk_arn is not a well-formed KMS key ARN: {tenant_cmk_arn!r}"
        )
    rendered = (
        render_session_policy_template(env)
        .replace(_ORG_PLACEHOLDER, org_id)
        .replace(_CMK_PLACEHOLDER, tenant_cmk_arn)
    )
    if len(rendered) > MAX_SESSION_POLICY_CHARS:
        raise SessionPolicyTooLargeError(
            f"rendered session policy is {len(rendered)} chars; the hard "
            f"sts:AssumeRole inline-policy limit is {MAX_SESSION_POLICY_CHARS} "
            "(CLAR-DEPLOY-21). Compact the template — RULE-9 review required."
        )
    return rendered


__all__ = [
    "MAX_SESSION_POLICY_CHARS",
    "ORG_ID_RE",
    "SESSION_POLICY_SIDS",
    "TENANT_CMK_ARN_RE",
    "OrgIdFormatError",
    "SessionPolicyError",
    "SessionPolicyTooLargeError",
    "TenantCmkArnFormatError",
    "build_session_policy_template",
    "data_plane_buckets",
    "render_session_policy_template",
    "render_worker_session_policy",
]
