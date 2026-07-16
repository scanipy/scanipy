"""CI-runnable guards for the worker session-policy template (CMP-DEPLOY-05 §3.1).

Two jobs:

1. **The 2048-char ceiling** (CLAR-DEPLOY-21): an inline ``sts:AssumeRole``
   session ``Policy`` is hard-capped at 2048 characters by AWS. The rendered
   policy (worst-case realistic substitutions: 36-char UUID org_id, full KMS
   key ARN) must fit, and the renderer must fail loudly — never truncate —
   when it would not. This converts a runtime scan-launch outage into a red CI.
2. **Renderer <-> Terraform lockstep**: ``services/substrate/session_policy.py``
   and ``infra/modules/compute/session_policy.tf`` must describe the same six
   statements over the same three data-plane buckets.

Per CLAR-DEPLOY-21 discipline these are construction/mechanics assertions
only — nothing here claims policy *enforcement* (that is the aws_live window).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from services.substrate.session_policy import (
    MAX_SESSION_POLICY_CHARS,
    SESSION_POLICY_SIDS,
    OrgIdFormatError,
    SessionPolicyTooLargeError,
    TenantCmkArnFormatError,
    build_session_policy_template,
    data_plane_buckets,
    render_session_policy_template,
    render_worker_session_policy,
)

pytestmark = pytest.mark.unit

_TF_PATH = (
    Path(__file__).resolve().parents[2] / "infra" / "modules" / "compute" / "session_policy.tf"
)

ORG_A = "0f7e9b1a-3c2d-4e5f-8a9b-0c1d2e3f4a5b"
CMK_A = "arn:aws:kms:us-east-1:508703380027:key/9d8c7b6a-5f4e-4d3c-b2a1-0f9e8d7c6b5a"


# ---------------------------------------------------------------------------
# The 2048-char sts:AssumeRole ceiling (CLAR-DEPLOY-21)
# ---------------------------------------------------------------------------


def test_rendered_policy_fits_the_sts_2048_char_limit() -> None:
    rendered = render_worker_session_policy(ORG_A, CMK_A)
    assert len(rendered) <= MAX_SESSION_POLICY_CHARS, (
        f"rendered session policy is {len(rendered)} chars > "
        f"{MAX_SESSION_POLICY_CHARS}; scan launches would fail at sts:AssumeRole"
    )


def test_oversize_policy_fails_loudly_instead_of_truncating() -> None:
    """Negative control: the ceiling is enforced, not aspirational."""
    with pytest.raises(SessionPolicyTooLargeError):
        render_worker_session_policy(ORG_A, CMK_A, env="prod" + "x" * 200)


# ---------------------------------------------------------------------------
# Render mechanics
# ---------------------------------------------------------------------------


def test_template_is_valid_json_with_the_six_sids_in_order() -> None:
    doc = json.loads(render_session_policy_template())
    assert tuple(s["Sid"] for s in doc["Statement"]) == SESSION_POLICY_SIDS


def test_rendered_policy_has_no_placeholders_left() -> None:
    rendered = render_worker_session_policy(ORG_A, CMK_A)
    assert "TEMPLATE_ORG_ID" not in rendered
    assert "TEMPLATE_TENANT_CMK_ARN" not in rendered
    doc = json.loads(rendered)
    allow = next(s for s in doc["Statement"] if s["Sid"] == "S3PerTenantAllow")
    assert f"arn:aws:s3:::scanipy-prod-snapshot/orgs/{ORG_A}/*" in allow["Resource"]
    deny = next(s for s in doc["Statement"] if s["Sid"] == "KMSOtherCMKsDeny")
    assert deny["NotResource"] == [CMK_A]


@pytest.mark.parametrize(
    "bad_org",
    [
        "*",
        "acme",
        ORG_A.upper(),
        ORG_A + "/*",
        "../../orgs/victim",
        "0f7e9b1a-3c2d-4e5f-8a9b-0c1d2e3f4a5b/*,arn:aws:s3:::x",
    ],
)
def test_non_uuid_org_id_is_rejected_before_substitution(bad_org: str) -> None:
    """A hostile org_id could widen Allow ARNs / narrow Deny ARNs — reject first."""
    with pytest.raises(OrgIdFormatError):
        render_worker_session_policy(bad_org, CMK_A)


def test_malformed_cmk_arn_is_rejected() -> None:
    with pytest.raises(TenantCmkArnFormatError):
        render_worker_session_policy(ORG_A, "arn:aws:kms:us-east-1:508703380027:alias/x")


# ---------------------------------------------------------------------------
# Renderer <-> Terraform lockstep
# ---------------------------------------------------------------------------


def test_sids_match_the_terraform_template() -> None:
    tf = _TF_PATH.read_text(encoding="utf-8")
    tf_sids = tuple(re.findall(r'sid\s*=\s*"(\w+)"', tf))
    assert tf_sids == SESSION_POLICY_SIDS


def test_bucket_names_match_the_terraform_locals() -> None:
    tf = _TF_PATH.read_text(encoding="utf-8")
    tf_buckets = {
        name: value.replace("${var.env}", "prod")
        for name, value in re.findall(r'(\w+_bucket)\s*=\s*"([^"]+)"', tf)
    }
    snapshot, witness, sarif = data_plane_buckets("prod")
    assert tf_buckets == {
        "snapshot_bucket": snapshot,
        "witness_bucket": witness,
        "sarif_bucket": sarif,
    }


def test_platform_prefix_is_read_only_and_snapshot_only() -> None:
    """_platform/* is a read-only platform corpus surface on the snapshot bucket."""
    template = build_session_policy_template()
    ro = next(s for s in template["Statement"] if s["Sid"] == "S3PlatformReadOnly")
    assert ro["Action"] == ["s3:GetObject"]
    assert ro["Resource"] == ["arn:aws:s3:::scanipy-prod-snapshot/_platform/*"]
