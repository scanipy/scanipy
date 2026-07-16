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
#
# --- Input-format + size contract (2026-07-15, CLAR-DEPLOY-21) -------------
#
# TEMPLATE_ORG_ID format: canonical lowercase UUID ONLY
#   (^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ — the DB
#   orgs.id column is `uuid`, db/migrations 20260524_0001). CMP-ORCH-03 MUST
#   validate org_id against this pattern BEFORE substituting it into this
#   template: an unvalidated value such as `*` or `../` would widen the Allow
#   ARNs / narrow the Deny ARNs. The canonical validator + renderer is
#   services/substrate/session_policy.py (render_worker_session_policy) —
#   substitute through it, never with ad-hoc string replace.
#
# TEMPLATE_TENANT_CMK_ARN format: arn:aws:kms:<region>:<account>:key/<uuid>
#   (validated by the same module).
#
# Size ceiling: the rendered JSON is passed as the inline Policy parameter of
#   sts:AssumeRole, which AWS hard-caps at 2048 characters. Current rendered
#   size is ~1752 chars (36-char UUID + full CMK ARN) — ~296 chars headroom.
#   CI guard: tests/unit/test_session_policy_template.py fails the build if a
#   template change would cross the limit (and cross-checks this file's sids
#   and bucket names against the renderer). If the guard trips, compact the
#   template — that is a RULE-9 Security-Analyst-reviewed change.

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
# Provisioned 2026-07-15 (live, us-east-1) and mirrored as IaC in
# infra/modules/dataplane/main.tf; referenced here by name only. Names are
# cross-checked against services/substrate/session_policy.py by
# tests/unit/test_session_policy_template.py.
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
  # S3 Layer 1a: object-level allow for this tenant's prefix (GetObject/PutObject/DeleteObject).
  # s3:ListBucket is a bucket-level action and must live in its own statement with an
  # s3:prefix condition — adding it here on object-level ARNs would have no effect.
  statement {
    sid    = "S3PerTenantAllow"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = [
      "arn:aws:s3:::${local.snapshot_bucket}/orgs/$${TEMPLATE_ORG_ID}/*",
      "arn:aws:s3:::${local.witness_bucket}/orgs/$${TEMPLATE_ORG_ID}/*",
      "arn:aws:s3:::${local.sarif_bucket}/orgs/$${TEMPLATE_ORG_ID}/*",
    ]
  }

  # S3 Layer 1b: platform read-only (canary corpus, CPG fidelity fixtures — no write).
  statement {
    sid     = "S3PlatformReadOnly"
    effect  = "Allow"
    actions = ["s3:GetObject"]
    resources = ["arn:aws:s3:::${local.snapshot_bucket}/_platform/*"]
  }

  # S3 Layer 1c: ListBucket restricted to this tenant's prefix via s3:prefix condition.
  # s3:ListBucket targets bucket-level ARNs; AWS ignores path suffixes on this action.
  # The s3:prefix condition limits the listing to the tenant's prefix + _platform.
  statement {
    sid     = "S3PerTenantListBucket"
    effect  = "Allow"
    actions = ["s3:ListBucket"]
    resources = [
      "arn:aws:s3:::${local.snapshot_bucket}",
      "arn:aws:s3:::${local.witness_bucket}",
      "arn:aws:s3:::${local.sarif_bucket}",
    ]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["orgs/$${TEMPLATE_ORG_ID}/*", "_platform/*"]
    }
  }

  # S3 Layer 1d: explicit Deny on every other org prefix (defence-in-depth
  # against IAM policy ordering surprises). Includes bucket-level ARNs to
  # cover the s3:ListBucket action alongside object-level ARNs.
  statement {
    sid    = "S3OtherOrgsDeny"
    effect = "Deny"
    actions = ["s3:*"]
    not_resources = [
      "arn:aws:s3:::${local.snapshot_bucket}/orgs/$${TEMPLATE_ORG_ID}/*",
      "arn:aws:s3:::${local.witness_bucket}/orgs/$${TEMPLATE_ORG_ID}/*",
      "arn:aws:s3:::${local.sarif_bucket}/orgs/$${TEMPLATE_ORG_ID}/*",
      "arn:aws:s3:::${local.snapshot_bucket}/_platform/*",
      "arn:aws:s3:::${local.snapshot_bucket}",
      "arn:aws:s3:::${local.witness_bucket}",
      "arn:aws:s3:::${local.sarif_bucket}",
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

# The authoritative runtime source is Secrets Manager (scanipy/{env}/worker-session-policy-template),
# stored by infra/tenant-isolation-apply.sh and read by CMP-ORCH-03 at scan launch.
# No local_file resource — a static file copy would diverge from Secrets Manager over time.

output "session_policy_template_json" {
  description = "Per-scan IAM session policy template (TEMPLATE_ORG_ID and TEMPLATE_TENANT_CMK_ARN are substituted at runtime by CMP-ORCH-03)"
  value       = data.aws_iam_policy_document.worker_session_policy_template.json
}
