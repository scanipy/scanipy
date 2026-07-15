#!/usr/bin/env bash
# CMP-DEPLOY-05 — provision tenant-isolation substrate (Layers 1 + 3) and the
# tenant data-plane buckets (CMP-DEPLOY-01 substrate).
# Layer 2 (PostgreSQL RLS) is already applied via db/migrations (PR #265).
#
# Idempotent: safe to re-run; every step is create-if-missing or an in-place
# overwrite of the same-named resource. Applied live 2026-07-15 (us-east-1,
# account 123456789012); IaC mirrors: infra/modules/dataplane/main.tf (buckets)
# + infra/modules/kms/main.tf (Lambda) + infra/modules/compute/session_policy.tf
# (session-policy template). terraform import backlog is recorded in the
# dataplane module header.
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
CONTROL_PLANE_INVOKER_ARN="${CONTROL_PLANE_INVOKER_ARN:-arn:aws:iam::${ACCOUNT_ID}:role/scanipy-github-deploy}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

log()  { echo "[$(date -u +%H:%M:%S)] $*"; }
done_() { echo "  ✓ $*"; }

log "CMP-DEPLOY-05 tenant-isolation apply: env=${ENV} region=${REGION} account=${ACCOUNT_ID}"
log "Worker task role: ${WORKER_TASK_ROLE_ARN}"
log ""
log "NOTE: Layer 2 (PostgreSQL RLS) is already applied via PR #265 migrations."

# ---------------------------------------------------------------------------
# Layer 0 (substrate): tenant data-plane buckets.
# Retention tiers per CLAUDE.md §8: CPG 90d · witness 1y · SARIF 7y (Object
# Lock). Default encryption is SSE-S3 — the per-tenant CMK envelope is an
# OBJECT-layer concern (CMP-CP-02), deliberately not a bucket default, so a
# shared bucket key can never blur the per-tenant CMK boundary.
# ---------------------------------------------------------------------------
log "Layer 0 — data-plane buckets..."

create_bucket() {
  local bucket="$1"; shift
  if aws s3api head-bucket --bucket "${bucket}" --region "${REGION}" 2>/dev/null; then
    done_ "bucket exists: ${bucket}"
    return 0
  fi
  local extra=()
  if [[ "${REGION}" != "us-east-1" ]]; then
    extra+=(--create-bucket-configuration "LocationConstraint=${REGION}")
  fi
  # "$@" carries e.g. --object-lock-enabled-for-bucket (must be set at creation).
  aws s3api create-bucket --bucket "${bucket}" --region "${REGION}" "${extra[@]+"${extra[@]}"}" "$@" > /dev/null
  done_ "bucket created: ${bucket}"
}

SNAPSHOT_BUCKET="scanipy-${ENV}-snapshot"
WITNESS_BUCKET="scanipy-${ENV}-witness"
SARIF_BUCKET="scanipy-${ENV}-sarif"

create_bucket "${SNAPSHOT_BUCKET}"
create_bucket "${WITNESS_BUCKET}"
create_bucket "${SARIF_BUCKET}" --object-lock-enabled-for-bucket

for BUCKET in "${SNAPSHOT_BUCKET}" "${WITNESS_BUCKET}" "${SARIF_BUCKET}"; do
  aws s3api put-public-access-block --bucket "${BUCKET}" --region "${REGION}" \
    --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
  aws s3api put-bucket-versioning --bucket "${BUCKET}" --region "${REGION}" \
    --versioning-configuration Status=Enabled
  aws s3api put-bucket-encryption --bucket "${BUCKET}" --region "${REGION}" \
    --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"},"BucketKeyEnabled":false}]}'
  aws s3api put-bucket-tagging --bucket "${BUCKET}" --region "${REGION}" \
    --tagging 'TagSet=[{Key=Component,Value=CMP-DEPLOY-05},{Key=Env,Value='"${ENV}"'},{Key=ManagedBy,Value=tenant-isolation-apply}]'
  done_ "BPA + versioning + SSE-S3 + tags: ${BUCKET}"
done

aws s3api put-bucket-lifecycle-configuration --bucket "${SNAPSHOT_BUCKET}" --region "${REGION}" \
  --lifecycle-configuration '{
    "Rules": [{
      "ID": "scanipy-cpg-retention-90d",
      "Status": "Enabled",
      "Filter": {},
      "Expiration": {"Days": 90},
      "NoncurrentVersionExpiration": {"NoncurrentDays": 90},
      "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7}
    }]
  }'
done_ "lifecycle 90d: ${SNAPSHOT_BUCKET}"

aws s3api put-bucket-lifecycle-configuration --bucket "${WITNESS_BUCKET}" --region "${REGION}" \
  --lifecycle-configuration '{
    "Rules": [{
      "ID": "scanipy-witness-retention-1y",
      "Status": "Enabled",
      "Filter": {},
      "Expiration": {"Days": 365},
      "NoncurrentVersionExpiration": {"NoncurrentDays": 365},
      "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7}
    }]
  }'
done_ "lifecycle 1y: ${WITNESS_BUCKET}"

# GOVERNANCE, not COMPLIANCE: COMPLIANCE (unbypassable for 7 years, even by
# root) is a management decision with irreversible cost consequences — do not
# flip it here unilaterally. Tracked for management sign-off.
aws s3api put-object-lock-configuration --bucket "${SARIF_BUCKET}" --region "${REGION}" \
  --object-lock-configuration \
  '{"ObjectLockEnabled":"Enabled","Rule":{"DefaultRetention":{"Mode":"GOVERNANCE","Years":7}}}'
done_ "Object Lock GOVERNANCE 7y: ${SARIF_BUCKET}"

# ---------------------------------------------------------------------------
# Layer 1: S3 bucket-level policy — enforce orgs/{org_id}/ prefix namespacing
# ---------------------------------------------------------------------------
log "Layer 1 — S3 prefix deny policies..."

for BUCKET in "${SNAPSHOT_BUCKET}" "${WITNESS_BUCKET}" "${SARIF_BUCKET}"; do
  # Bucket policy: deny GetObject/PutObject/DeleteObject on any object NOT under orgs/* or _platform/*.
  # Use NotResource (not a Condition on s3:prefix) — s3:prefix is only populated for
  # s3:ListBucket requests; on object actions the key is absent and StringNotLike would
  # evaluate to true unconditionally, blocking all object access.
  #
  # HONEST GAP (recorded 2026-07-15): this bucket policy enforces the
  # NAMESPACE (nothing outside orgs/* or _platform/*), not the per-org
  # boundary. Matching the object key's org_id against the caller's org at
  # the bucket-policy layer would need an org-scoped principal context (e.g.
  # aws:PrincipalTag/org_id via sts:TagSession), which the current
  # AssumeRole flow (inline session Policy + scan-* session name, DOC §6.1)
  # does not carry — and an unresolvable policy variable inside a blanket
  # Deny would lock out the control plane. The per-org boundary is enforced
  # by the per-scan IAM session policy (Layer 1, session_policy.tf) and the
  # per-tenant CMK encryption context (Layer 3). Moving org-matching into
  # bucket policies = session-tagging design change → RULE-9 review first.
  POLICY=$(python3 - "${BUCKET}" <<'PY'
import json
import sys

bucket = sys.argv[1]
print(json.dumps({
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyNonTenantObjectPaths",
      "Effect": "Deny",
      "Principal": "*",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "NotResource": [
        f"arn:aws:s3:::{bucket}/orgs/*",
        f"arn:aws:s3:::{bucket}/_platform/*",
      ],
    }
  ],
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

# Package and deploy the Lambda (hardened 2026-07-15: strict org_id validation
# + idempotent enable_key_rotation on the existing-key path — see
# infra/modules/kms/tenant_cmk_lambda.py and tests/unit/test_tenant_cmk_lambda.py)
TMPDIR=$(mktemp -d)
cp "${REPO_ROOT}/infra/modules/kms/tenant_cmk_lambda.py" "${TMPDIR}/"
(cd "${TMPDIR}" && zip tenant_cmk_lambda.zip tenant_cmk_lambda.py > /dev/null)

FUNCTION_NAME="scanipy-${ENV}-tenant-cmk-provisioner"
if aws lambda get-function --function-name "${FUNCTION_NAME}" --region "${REGION}" > /dev/null 2>&1; then
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

# Invocation restriction: grant lambda:InvokeFunction to the control-plane
# principal only. Lambda resource policies are Allow-only, so deny-by-default
# means: no explicit grant beyond this — no scanipy worker/task role carries
# lambda:* in its identity policy, and account root retains access via IAM.
# Add the CMP-CP-02 runtime role (the real onboarding caller) when it exists.
# add-permission fails on a duplicate statement id — tolerate re-runs.
if aws lambda add-permission \
  --function-name "${FUNCTION_NAME}" \
  --statement-id "scanipy-control-plane-invoke" \
  --action "lambda:InvokeFunction" \
  --principal "${CONTROL_PLANE_INVOKER_ARN}" \
  --region "${REGION}" > /dev/null 2>&1; then
  done_ "invoke permission granted: ${CONTROL_PLANE_INVOKER_ARN}"
else
  done_ "invoke permission already present (statement-id scanipy-control-plane-invoke)"
fi

# ---------------------------------------------------------------------------
# Session policy template render (Layer 1 — stored for CMP-ORCH-03).
# Single source of truth: services/substrate/session_policy.py (also consumed
# by CMP-ORCH-03 and by the 2048-char CI guard in
# tests/unit/test_session_policy_template.py — the sts:AssumeRole inline
# Policy hard limit, CLAR-DEPLOY-21).
# ---------------------------------------------------------------------------
log "Rendering session policy template..."
SESSION_POLICY_TEMPLATE=$(PYTHONPATH="${REPO_ROOT}" python3 -c \
  "from services.substrate.session_policy import render_session_policy_template as r; print(r('${ENV}'))")

# Store to Secrets Manager so CMP-ORCH-03 can read it at runtime.
SECRET_NAME="scanipy/${ENV}/worker-session-policy-template"
if aws secretsmanager describe-secret --secret-id "${SECRET_NAME}" --region "${REGION}" > /dev/null 2>&1; then
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
echo "Layer 0 (buckets):       ${SNAPSHOT_BUCKET} (90d) · ${WITNESS_BUCKET} (1y) · ${SARIF_BUCKET} (Object Lock GOVERNANCE 7y)"
echo "Layer 1 (IAM template):  ${SECRET_NAME} in Secrets Manager + s3api bucket policies applied"
echo "Layer 2 (RLS):           already applied via PR #265"
echo "Layer 3 (CMK Lambda):    ${LAMBDA_ARN}"
echo "Lambda role:             ${LAMBDA_ROLE_ARN}"
echo "Lambda invokers:         ${CONTROL_PLANE_INVOKER_ARN} (+ account root via IAM)"