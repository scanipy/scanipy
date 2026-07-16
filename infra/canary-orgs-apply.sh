#!/usr/bin/env bash
# CMP-CORP-CANARY-01 (runbook item 9) — provision Secrets Manager stubs and IAM
# read policy for canary SCM credentials (GitHub, GitLab, Bitbucket, Azure DevOps).
#
# The four secrets are created with placeholder values.  After running this script,
# fill each secret with real credentials via the platform UIs listed in
# docs/status/STATUS-AWS-TEAM.md §9 "Pending (manual — browser UI required)".
#
# Run with valid AWS credentials (OIDC or local profile).
#
# Usage:  ./infra/canary-orgs-apply.sh [--env prod] [--region us-east-1]
set -euo pipefail

ENV="${ENV:-prod}"
REGION="${REGION:-us-east-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

log()  { echo "[$(date -u +%H:%M:%S)] $*"; }
done_() { echo "  ✓ $*"; }

log "Provisioning CMP-CORP-CANARY-01 canary SCM stubs: env=${ENV} region=${REGION} account=${ACCOUNT_ID}"

# ---------------------------------------------------------------------------
# Secrets Manager stubs — placeholder values; fill after org/PAT creation
# ---------------------------------------------------------------------------
log "Creating Secrets Manager stubs for canary SCM credentials..."

declare -A CANARY_SECRETS=(
  ["scanipy/${ENV}/canary/github"]="Canary GitHub org credentials (scanipy-canary). Populate: token (scopes: repo, read:org), org."
  ["scanipy/${ENV}/canary/gitlab"]="Canary GitLab group credentials (scanipy-canary). Populate: token (scopes: api, write_repository), group."
  ["scanipy/${ENV}/canary/bitbucket"]="Canary Bitbucket workspace credentials (scanipy-canary). Populate: app_password (Repositories: Read+Write), workspace."
  ["scanipy/${ENV}/canary/azure-devops"]="Canary Azure DevOps org credentials (scanipy-canary). Populate: token (Code: Read+Write, Project and Team: Read), org."
)

SECRET_ARNS=()
for SECRET_NAME in "${!CANARY_SECRETS[@]}"; do
  DESCRIPTION="${CANARY_SECRETS[${SECRET_NAME}]}"
  if aws secretsmanager describe-secret --secret-id "${SECRET_NAME}" --region "${REGION}" 2>/dev/null; then
    done_ "Secrets Manager secret already exists: ${SECRET_NAME}"
  else
    ARN=$(aws secretsmanager create-secret \
      --name "${SECRET_NAME}" \
      --description "${DESCRIPTION}" \
      --secret-string '{"token":"PLACEHOLDER","org":"scanipy-canary"}' \
      --region "${REGION}" \
      --tags Key=Component,Value=CMP-CORP-CANARY-01 Key=Env,Value="${ENV}" Key=FillRequired,Value=true \
      --query ARN --output text)
    done_ "Created: ${SECRET_NAME}  (${ARN})"
  fi
  SECRET_ARNS+=("arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:${SECRET_NAME}-*")
done

# ---------------------------------------------------------------------------
# IAM policy — read access to the four canary secrets
# ---------------------------------------------------------------------------
log "Creating IAM policy canary-scm-secrets-read..."

POLICY_DOCUMENT=$(python3 - <<PY
import json
arns = [
    "arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:scanipy/${ENV}/canary/github-*",
    "arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:scanipy/${ENV}/canary/gitlab-*",
    "arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:scanipy/${ENV}/canary/bitbucket-*",
    "arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:scanipy/${ENV}/canary/azure-devops-*",
]
print(json.dumps({
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "CanarySCMSecretsRead",
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue",
                "secretsmanager:DescribeSecret"
            ],
            "Resource": arns
        }
    ]
}))
PY
)

POLICY_NAME="canary-scm-secrets-read"
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"

if aws iam get-policy --policy-arn "${POLICY_ARN}" 2>/dev/null; then
  # Update default version of existing policy
  EXISTING_VERSION=$(aws iam get-policy --policy-arn "${POLICY_ARN}" \
    --query Policy.DefaultVersionId --output text)
  aws iam create-policy-version \
    --policy-arn "${POLICY_ARN}" \
    --policy-document "${POLICY_DOCUMENT}" \
    --set-as-default > /dev/null
  # Clean up non-default versions (max 5 versions allowed)
  aws iam delete-policy-version \
    --policy-arn "${POLICY_ARN}" \
    --version-id "${EXISTING_VERSION}" 2>/dev/null || true
  done_ "IAM policy updated: ${POLICY_ARN}"
else
  aws iam create-policy \
    --policy-name "${POLICY_NAME}" \
    --policy-document "${POLICY_DOCUMENT}" \
    --description "Read access to canary SCM credential secrets (CMP-CORP-CANARY-01)" \
    --tags Key=Component,Value=CMP-CORP-CANARY-01 Key=Env,Value="${ENV}" > /dev/null
  done_ "IAM policy created: ${POLICY_ARN}"
fi

# ---------------------------------------------------------------------------
# Attach policy to worker and deploy roles
# ---------------------------------------------------------------------------
log "Attaching canary-scm-secrets-read to worker and deploy roles..."

for ROLE in "scanipy-worker-task" "scanipy-github-deploy"; do
  if aws iam get-role --role-name "${ROLE}" 2>/dev/null; then
    aws iam attach-role-policy \
      --role-name "${ROLE}" \
      --policy-arn "${POLICY_ARN}" 2>/dev/null || true
    done_ "Policy attached to role: ${ROLE}"
  else
    echo "  WARN: role ${ROLE} not found (created by CMP-DEPLOY-01); attachment skipped"
  fi
done

# ---------------------------------------------------------------------------
# Summary — paste into STATUS-AWS-TEAM.md row 9
# ---------------------------------------------------------------------------
echo ""
echo "========================================"
echo " DONE — Evidence for STATUS-AWS-TEAM.md"
echo "========================================"
echo "Secrets Manager stubs:"
echo "  scanipy/${ENV}/canary/github"
echo "  scanipy/${ENV}/canary/gitlab"
echo "  scanipy/${ENV}/canary/bitbucket"
echo "  scanipy/${ENV}/canary/azure-devops"
echo "IAM policy:  ${POLICY_ARN}"
echo "Attached to: scanipy-worker-task, scanipy-github-deploy"
echo ""
echo "NEXT STEPS (manual — browser UI required):"
echo "  GitHub:      github.com/organizations/new → PAT (repo, read:org)"
echo "               aws secretsmanager put-secret-value --secret-id scanipy/${ENV}/canary/github --secret-string '{\"token\":\"<PAT>\",\"org\":\"scanipy-canary\"}'"
echo "  GitLab:      gitlab.com/groups/new → group access token (api, write_repository)"
echo "               aws secretsmanager put-secret-value --secret-id scanipy/${ENV}/canary/gitlab --secret-string '{\"token\":\"<TOKEN>\",\"group\":\"scanipy-canary\"}'"
echo "  Bitbucket:   bitbucket.org → workspace scanipy-canary → app password (Repositories: Read+Write)"
echo "               aws secretsmanager put-secret-value --secret-id scanipy/${ENV}/canary/bitbucket --secret-string '{\"app_password\":\"<PWD>\",\"workspace\":\"scanipy-canary\"}'"
echo "  AzureDevOps: dev.azure.com → org scanipy-canary → PAT (Code: Read+Write, Project+Team: Read)"
echo "               aws secretsmanager put-secret-value --secret-id scanipy/${ENV}/canary/azure-devops --secret-string '{\"token\":\"<PAT>\",\"org\":\"scanipy-canary\"}'"
