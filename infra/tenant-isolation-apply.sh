#!/usr/bin/env bash
# CMP-DEPLOY-05 — provision tenant-isolation substrate (Layers 1 + 3).
# Layer 2 (PostgreSQL RLS) is already applied via db/migrations (PR #265).
#
# Run with valid AWS credentials. Records output for STATUS-AWS-TEAM.md row 8.
#
# Usage:  ./infra/tenant-isolation-apply.sh
#   ENV=prod REGION=us-east-1 WORKER_TASK_ROLE_ARN=arn:aws:... ./infra/tenant-isolation-apply.sh
#
# RULE-9: touches INV-3 (CMK = substrate guarantee for S_customer isolation).
# Do NOT apply without Security Analyst sign-off on this PR.
set -euo pipefail

ENV="${ENV:-prod}"
REGION="${REGION:-us-east-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
WORKER_TASK_ROLE_ARN="${WORKER_TASK_ROLE_ARN:-arn:aws:iam::${ACCOUNT_ID}:role/scanipy-ecs-worker}"

log()  { echo "[$(date -u +%H:%M:%S)] $*"; }
done_() { echo "  ✓ $*"; }

log "CMP-DEPLOY-05 tenant-isolation apply: env=${ENV} region=${REGION} account=${ACCOUNT_ID}"
log "Worker task role: ${WORKER_TASK_ROLE_ARN}"
log ""
log "NOTE: Layer 2 (PostgreSQL RLS) is already applied via PR #265 migrations."

# ---------------------------------------------------------------------------
# Layer 1: S3 bucket-level policy — enforce orgs/{org_id}/ prefix namespacing
# ---------------------------------------------------------------------------
log "Layer 1 — S3 prefix deny policies..."

for BUCKET in "scanipy-${ENV}-snapshot" "scanipy-${ENV}-witness" "scanipy-${ENV}-sarif"; do
  # Bucket existence check — these are created by CMP-DEPLOY-01 Terraform.
  if ! aws s3api head-bucket --bucket "${BUCKET}" --region "${REGION}" 2>/dev/null; then
    echo "  WARN: bucket ${BUCKET} does not exist yet (expected from CMP-DEPLOY-01 IaC)"
    continue
  fi

  # Bucket policy: deny GetObject/PutObject/DeleteObject on any object NOT under orgs/* or _platform/*.
  # Use NotResource (not a Condition on s3:prefix) — s3:prefix is only populated for
  # s3:ListBucket requests; on object actions the key is absent and StringNotLike would
  # evaluate to true unconditionally, blocking all object access.
  POLICY=$(python3 - <<PY
import json
print(json.dumps({
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyNonTenantObjectPaths",
      "Effect": "Deny",
      "Principal": "*",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "NotResource": [
        "arn:aws:s3:::${BUCKET}/orgs/*",
        "arn:aws:s3:::${BUCKET}/_platform/*"
      ]
    }
  ]
}))
PY
)
  aws s3api put-bucket-policy \
    --bucket "${BUCKET}" \
    --policy "${POLICY}" \
    --region "${REGION}"
  done_ "S3 prefix deny policy: ${BUCKET}"
done

# ---------------------------------------------------------------------------
# Layer 3: CMK provisioning Lambda + execution role
# ---------------------------------------------------------------------------
log "Layer 3 — CMK provisioning Lambda..."

LAMBDA_ROLE_NAME="scanipy-${ENV}-tenant-cmk-provisioner"

# Create Lambda execution role if it doesn't exist
if ! aws iam get-role --role-name "${LAMBDA_ROLE_NAME}" 2>/dev/null; then
  aws iam create-role \
    --role-name "${LAMBDA_ROLE_NAME}" \
    --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
    --tags Key=Component,Value=CMP-DEPLOY-05 Key=Env,Value="${ENV}" > /dev/null
  done_ "IAM role: ${LAMBDA_ROLE_NAME}"
fi
LAMBDA_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${LAMBDA_ROLE_NAME}"

# Attach inline KMS provisioning + CloudWatch logs policy
aws iam put-role-policy \
  --role-name "${LAMBDA_ROLE_NAME}" \
  --policy-name "tenant-cmk-kms-access" \
  --policy-document "$(python3 - <<PY
import json
print(json.dumps({
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "KMSProvisionCreate",
      "Effect": "Allow",
      "Action": ["kms:CreateKey","kms:CreateAlias","kms:DescribeKey","kms:ListAliases",
                 "kms:EnableKeyRotation"],
      "Resource": "*"
    },
    {
      "Sid": "KMSProvisionOwnedKeysOnly",
      "Effect": "Allow",
      "Action": ["kms:PutKeyPolicy","kms:TagResource"],
      "Resource": "*",
      "Condition": {
        "ForAnyValue:StringLike": {
          "kms:ResourceAliases": ["alias/scanipy-tenant-*"]
        }
      }
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents"],
      "Resource": "arn:aws:logs:${REGION}:${ACCOUNT_ID}:log-group:/aws/lambda/scanipy-${ENV}-tenant-cmk-provisioner:*"
    }
  ]
}))
PY
)"
done_ "IAM role policy attached"

# Package and deploy the Lambda
TMPDIR=$(mktemp -d)
cp "$(dirname "$0")/modules/kms/tenant_cmk_lambda.py" "${TMPDIR}/"
(cd "${TMPDIR}" && zip tenant_cmk_lambda.zip tenant_cmk_lambda.py > /dev/null)

FUNCTION_NAME="scanipy-${ENV}-tenant-cmk-provisioner"
if aws lambda get-function --function-name "${FUNCTION_NAME}" --region "${REGION}" 2>/dev/null; then
  aws lambda update-function-code \
    --function-name "${FUNCTION_NAME}" \
    --zip-file "fileb://${TMPDIR}/tenant_cmk_lambda.zip" \
    --region "${REGION}" > /dev/null
  done_ "Lambda updated: ${FUNCTION_NAME}"
else
  sleep 10  # role propagation
  LAMBDA_ARN=$(aws lambda create-function \
    --function-name "${FUNCTION_NAME}" \
    --runtime "python3.11" \
    --role "${LAMBDA_ROLE_ARN}" \
    --handler "tenant_cmk_lambda.provision_tenant_cmk_handler" \
    --zip-file "fileb://${TMPDIR}/tenant_cmk_lambda.zip" \
    --timeout 30 \
    --environment "Variables={ENV=${ENV},REGION=${REGION},ACCOUNT_ID=${ACCOUNT_ID},WORKER_TASK_ROLE_ARN=${WORKER_TASK_ROLE_ARN}}" \
    --tags Component=CMP-DEPLOY-05,Env="${ENV}" \
    --region "${REGION}" \
    --query FunctionArn --output text)
  done_ "Lambda created: ${LAMBDA_ARN}"
fi
rm -rf "${TMPDIR}"

LAMBDA_ARN="arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${FUNCTION_NAME}"

# ---------------------------------------------------------------------------
# Session policy template render (Layer 1 — stored for CMP-ORCH-03)
# ---------------------------------------------------------------------------
log "Rendering session policy template..."
SESSION_POLICY_TEMPLATE=$(python3 - <<PY
import json
print(json.dumps({
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3PerTenantAllow",
      "Effect": "Allow",
      "Action": ["s3:GetObject","s3:PutObject","s3:DeleteObject"],
      "Resource": [
        f"arn:aws:s3:::scanipy-${ENV}-snapshot/orgs/\${TEMPLATE_ORG_ID}/*",
        f"arn:aws:s3:::scanipy-${ENV}-witness/orgs/\${TEMPLATE_ORG_ID}/*",
        f"arn:aws:s3:::scanipy-${ENV}-sarif/orgs/\${TEMPLATE_ORG_ID}/*",
      ]
    },
    {
      "Sid": "S3PlatformReadOnly",
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": [f"arn:aws:s3:::scanipy-${ENV}-snapshot/_platform/*"]
    },
    {
      "Sid": "S3PerTenantListBucket",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": [
        f"arn:aws:s3:::scanipy-${ENV}-snapshot",
        f"arn:aws:s3:::scanipy-${ENV}-witness",
        f"arn:aws:s3:::scanipy-${ENV}-sarif",
      ],
      "Condition": {
        "StringLike": {
          "s3:prefix": [f"orgs/\${TEMPLATE_ORG_ID}/*", "_platform/*"]
        }
      }
    },
    {
      "Sid": "S3OtherOrgsDeny",
      "Effect": "Deny",
      "Action": ["s3:*"],
      "NotResource": [
        f"arn:aws:s3:::scanipy-${ENV}-snapshot/orgs/\${TEMPLATE_ORG_ID}/*",
        f"arn:aws:s3:::scanipy-${ENV}-witness/orgs/\${TEMPLATE_ORG_ID}/*",
        f"arn:aws:s3:::scanipy-${ENV}-sarif/orgs/\${TEMPLATE_ORG_ID}/*",
        f"arn:aws:s3:::scanipy-${ENV}-snapshot/_platform/*",
        f"arn:aws:s3:::scanipy-${ENV}-snapshot",
        f"arn:aws:s3:::scanipy-${ENV}-witness",
        f"arn:aws:s3:::scanipy-${ENV}-sarif",
      ]
    },
    {
      "Sid": "KMSPerTenantAllow",
      "Effect": "Allow",
      "Action": ["kms:Decrypt","kms:GenerateDataKey","kms:DescribeKey"],
      "Resource": ["\${TEMPLATE_TENANT_CMK_ARN}"]
    },
    {
      "Sid": "KMSOtherCMKsDeny",
      "Effect": "Deny",
      "Action": ["kms:Decrypt","kms:GenerateDataKey"],
      "NotResource": ["\${TEMPLATE_TENANT_CMK_ARN}"]
    }
  ]
}))
PY
)

# Store to Secrets Manager so CMP-ORCH-03 can read it at runtime.
SECRET_NAME="scanipy/${ENV}/worker-session-policy-template"
if aws secretsmanager describe-secret --secret-id "${SECRET_NAME}" --region "${REGION}" 2>/dev/null; then
  aws secretsmanager put-secret-value \
    --secret-id "${SECRET_NAME}" \
    --secret-string "${SESSION_POLICY_TEMPLATE}" \
    --region "${REGION}" > /dev/null
  done_ "Session policy template updated in Secrets Manager: ${SECRET_NAME}"
else
  aws secretsmanager create-secret \
    --name "${SECRET_NAME}" \
    --description "Per-scan IAM session policy template (TEMPLATE_ORG_ID + TEMPLATE_TENANT_CMK_ARN substituted by CMP-ORCH-03)" \
    --secret-string "${SESSION_POLICY_TEMPLATE}" \
    --region "${REGION}" \
    --tags Key=Component,Value=CMP-DEPLOY-05 Key=Env,Value="${ENV}" > /dev/null
  done_ "Session policy template stored in Secrets Manager: ${SECRET_NAME}"
fi

# ---------------------------------------------------------------------------
# Summary — paste into STATUS-AWS-TEAM.md row 8
# ---------------------------------------------------------------------------
echo ""
echo "========================================"
echo " DONE — Evidence for STATUS-AWS-TEAM.md"
echo "========================================"
echo "Layer 1 (IAM template):  ${SECRET_NAME} in Secrets Manager + s3api bucket policies applied"
echo "Layer 2 (RLS):           already applied via PR #265"
echo "Layer 3 (CMK Lambda):    ${LAMBDA_ARN}"
echo "Lambda role:             ${LAMBDA_ROLE_ARN}"
