# CMP-DEPLOY-05 §3.1 — IAM session policy template (Layer 1 tenant isolation)
#
# This file defines a Terraform data source that renders the per-scan session
# policy template. The template is stored in session_policy.json.tpl and
# parameterised at runtime by CMP-ORCH-03 before calling sts:AssumeRole.
#
# The session policy is an INTERSECTION with the worker task role's grants —
# a worker cannot acquire rights the task role doesn't already have, but the
# session policy narrows those rights to a single org's prefix and CMK.
#
# RULE-9: this module is INV-3-adjacent (per-tenant CMK scope is the substrate
# guarantee that tenant S_customer cannot leak across tenants). Security Analyst
# sign-off required before any change ships.

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "env" {
  type    = string
  default = "prod"
}

# ---------------------------------------------------------------------------
# S3 bucket names (per CLAR-DEPLOY-02 — orgs/{org_id}/... prefix scheme)
# These buckets are provisioned by CMP-DEPLOY-01; referenced here by name only.
# ---------------------------------------------------------------------------
locals {
  snapshot_bucket = "scanipy-${var.env}-snapshot"
  witness_bucket  = "scanipy-${var.env}-witness"
  sarif_bucket    = "scanipy-${var.env}-sarif"
}

# ---------------------------------------------------------------------------
# Session policy template rendered at task-launch time by CMP-ORCH-03.
# TEMPLATE_ORG_ID and TEMPLATE_TENANT_CMK_ARN are substituted per scan.
# The rendered JSON is passed as the Policy parameter to sts:AssumeRole.
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "worker_session_policy_template" {
  # S3 Layer 1a: allow only the authenticated tenant's prefix.
  statement {
    sid    = "S3PerTenantAllow"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [
      "arn:aws:s3:::${local.snapshot_bucket}/orgs/$${TEMPLATE_ORG_ID}/*",
      "arn:aws:s3:::${local.witness_bucket}/orgs/$${TEMPLATE_ORG_ID}/*",
      "arn:aws:s3:::${local.sarif_bucket}/orgs/$${TEMPLATE_ORG_ID}/*",
      # Platform-level read (canary corpus, CPG fidelity fixtures) — no write.
      "arn:aws:s3:::${local.snapshot_bucket}/_platform/*",
    ]
  }

  # S3 Layer 1b: explicit Deny on every other org prefix (defence-in-depth
  # against IAM policy ordering surprises).
  statement {
    sid    = "S3OtherOrgsDeny"
    effect = "Deny"
    actions = ["s3:*"]
    not_resources = [
      "arn:aws:s3:::${local.snapshot_bucket}/orgs/$${TEMPLATE_ORG_ID}/*",
      "arn:aws:s3:::${local.witness_bucket}/orgs/$${TEMPLATE_ORG_ID}/*",
      "arn:aws:s3:::${local.sarif_bucket}/orgs/$${TEMPLATE_ORG_ID}/*",
      "arn:aws:s3:::${local.snapshot_bucket}/_platform/*",
    ]
  }

  # KMS Layer 3: only the per-tenant CMK for this org; Deny all other KMS keys.
  statement {
    sid    = "KMSPerTenantAllow"
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey",
      "kms:DescribeKey",
    ]
    resources = ["$${TEMPLATE_TENANT_CMK_ARN}"]
  }

  statement {
    sid    = "KMSOtherCMKsDeny"
    effect = "Deny"
    actions = ["kms:Decrypt", "kms:GenerateDataKey"]
    not_resources = ["$${TEMPLATE_TENANT_CMK_ARN}"]
  }
}

# Render the policy to a local file so CMP-ORCH-03 can read the template
# from the container image (the file is copied in via the worker Dockerfile).
resource "local_file" "session_policy_template" {
  filename = "${path.module}/session_policy_template.json"
  content  = data.aws_iam_policy_document.worker_session_policy_template.json
}

output "session_policy_template_json" {
  description = "Per-scan IAM session policy template (TEMPLATE_ORG_ID and TEMPLATE_TENANT_CMK_ARN are substituted at runtime by CMP-ORCH-03)"
  value       = data.aws_iam_policy_document.worker_session_policy_template.json
}
