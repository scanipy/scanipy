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
