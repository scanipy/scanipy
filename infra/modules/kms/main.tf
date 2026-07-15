# CMP-DEPLOY-05 §3.3 — Per-tenant KMS CMK provisioning (Layer 3 tenant isolation)
#
# This Terraform module manages the KMS infrastructure for tenant CMK provisioning:
#   1. The Lambda execution role + function that CMP-CP-02 calls on tenant onboarding.
#   2. A KMS key policy template (applied to every per-tenant CMK at creation).
#
# Per-tenant CMKs are NOT managed by Terraform — they are dynamic (one per org,
# created on first onboarding) and owned by the Lambda function below.
#
# RULE-9: touches INV-3 (per-tenant CMK = substrate guarantee that a tenant's
# S_customer cannot leak across tenants). Security Analyst sign-off required.

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

variable "region"      { type = string; default = "us-east-1" }
variable "env"         { type = string; default = "prod" }
variable "account_id"  { type = string }
variable "worker_task_role_arn" {
  description = "ARN of the ECS worker task role that will be allowed to use tenant CMKs"
  type        = string
}
variable "control_plane_invoker_arns" {
  description = <<-EOT
    IAM principals allowed to invoke the tenant-CMK provisioning Lambda.
    Deny-by-default posture: Lambda resource policies are additive Allow-only,
    so the effective invoker set is (a) these explicit grants plus (b) any
    same-account IAM identity whose own policy grants lambda:InvokeFunction —
    the account root always qualifies. Default: the GitHub-Actions OIDC deploy
    role only. Add the CMP-CP-02 runtime role here when it exists (it is the
    real production caller at tenant onboarding).
  EOT
  type        = list(string)
  default     = []
}

# ---------------------------------------------------------------------------
# Lambda execution role — minimal permissions to create/describe KMS keys
# ---------------------------------------------------------------------------
resource "aws_iam_role" "tenant_cmk_lambda" {
  name = "scanipy-${var.env}-tenant-cmk-provisioner"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Component = "CMP-DEPLOY-05"; Env = var.env }
}

resource "aws_iam_role_policy" "tenant_cmk_lambda" {
  name = "tenant-cmk-kms-access"
  role = aws_iam_role.tenant_cmk_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # kms:CreateKey / kms:CreateAlias must stay on Resource="*" — no key ID exists at creation time.
        Sid    = "KMSProvisionCreate"
        Effect = "Allow"
        Action = [
          "kms:CreateKey",
          "kms:CreateAlias",
          "kms:DescribeKey",
          "kms:ListAliases",
          "kms:EnableKeyRotation",
        ]
        Resource = "*"
      },
      {
        # kms:PutKeyPolicy can grant kms:Decrypt to arbitrary principals if left on Resource="*".
        # Restrict to keys the Lambda owns via kms:ResourceAliases so a compromised Lambda
        # cannot modify other tenants' CMKs.
        Sid    = "KMSProvisionOwnedKeysOnly"
        Effect = "Allow"
        Action = ["kms:PutKeyPolicy", "kms:TagResource"]
        Resource = "*"
        Condition = {
          "ForAnyValue:StringLike" = {
            "kms:ResourceAliases" = ["alias/scanipy-tenant-*"]
          }
        }
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${var.region}:${var.account_id}:log-group:/aws/lambda/scanipy-${var.env}-tenant-cmk-provisioner:*"
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# Lambda function — tenant_cmk_lambda.py (inline archive)
# ---------------------------------------------------------------------------
data "archive_file" "tenant_cmk_lambda" {
  type        = "zip"
  source_file = "${path.module}/tenant_cmk_lambda.py"
  output_path = "${path.module}/tenant_cmk_lambda.zip"
}

resource "aws_lambda_function" "tenant_cmk" {
  function_name    = "scanipy-${var.env}-tenant-cmk-provisioner"
  role             = aws_iam_role.tenant_cmk_lambda.arn
  handler          = "tenant_cmk_lambda.provision_tenant_cmk_handler"
  runtime          = "python3.11"
  filename         = data.archive_file.tenant_cmk_lambda.output_path
  source_code_hash = data.archive_file.tenant_cmk_lambda.output_base64sha256
  timeout          = 30

  environment {
    variables = {
      ENV        = var.env
      REGION     = var.region
      ACCOUNT_ID = var.account_id
      WORKER_TASK_ROLE_ARN = var.worker_task_role_arn
    }
  }

  tags = { Component = "CMP-DEPLOY-05"; Env = var.env }
}

# ---------------------------------------------------------------------------
# Invocation restriction (applied live 2026-07-15 via `aws lambda
# add-permission`, statement id `scanipy-control-plane-invoke` — the CLI/
# apply-script grant used the plain id since it only ever adds one default
# invoker; a `terraform apply` of the resource below would independently
# grant the same principal under a per-ARN-hashed id
# (`scanipy-control-plane-invoke-<8 hex>`, to stay collision-free across
# multiple invokers in `control_plane_invoker_arns`). Both forms are
# functionally identical Allow grants for the same principal — Terraform
# does not currently own this resource live (see the dataplane module's
# terraform-import-backlog note; the same CLI-authoritative posture applies
# here), so no drift/duplicate-grant risk exists today.
#
# This Lambda mints per-tenant CMKs — its invoker set IS the tenant-onboarding
# control plane. Lambda resource policies are Allow-only (no Deny statements
# via add-permission), so "deny-by-default" here means: grant explicitly only
# the control-plane principals below; every other principal must come through
# its own IAM identity policy, which no scanipy worker/task role carries
# (worker roles get S3/KMS data-plane actions only, never lambda:*). The
# account root retains invocation via IAM as always.
#
# Default grant: role/scanipy-github-deploy (the OIDC deploy role). The
# CMP-CP-02 runtime role must be appended to var.control_plane_invoker_arns
# when it exists.
# ---------------------------------------------------------------------------
resource "aws_lambda_permission" "control_plane_invoke" {
  for_each = toset(
    length(var.control_plane_invoker_arns) > 0
    ? var.control_plane_invoker_arns
    : ["arn:aws:iam::${var.account_id}:role/scanipy-github-deploy"]
  )

  statement_id  = "scanipy-control-plane-invoke-${substr(sha256(each.value), 0, 8)}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.tenant_cmk.function_name
  principal     = each.value
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
output "lambda_arn" {
  description = "ARN of the tenant CMK provisioning Lambda (invoked by CMP-CP-02 on tenant onboarding)"
  value       = aws_lambda_function.tenant_cmk.arn
}

output "lambda_role_arn" {
  description = "Execution role ARN for the CMK provisioning Lambda"
  value       = aws_iam_role.tenant_cmk_lambda.arn
}
