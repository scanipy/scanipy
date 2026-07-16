#!/usr/bin/env bash
# CMP-CP-03 — provision the RDS PostgreSQL 16 instance (AWS CLI equivalent of
# the Terraform module in infra/modules/database/).
#
# Scope: dev/test ONLY (CLAR-DEPLOY-03 mandates Multi-AZ for production; this
# instance is single-AZ db.t4g.micro — do not treat this as the production
# provisioning path). Provisions into the account's DEFAULT VPC public
# subnets as an interim measure — CLAR-DEPLOY-23 (the private-subnet VPC
# remediation track, "3-VPC") had not landed at the time this ran. Move
# SUBNET_IDS to the new private subnets the moment that module exists; no
# other part of this script needs to change.
#
# Idempotent: safe to re-run; every step is create-if-missing or an in-place
# overwrite of the same-named resource. Never deletes anything.
#
# Isolation: inbound 5432 is scoped to the live ECS task security group
# ("scanipy-workers") ONLY — never a CIDR block.
#
# Secrets: the master password is generated locally (never read back from
# Secrets Manager — `get-secret-value` is never called by this script) and
# is persisted to Secrets Manager immediately after generation so it is not
# lost, matching the platform's Secrets Manager injection decision
# (CLAUDE.md §8 / CLAR-DEPLOY-05).
#
# Usage:  ./infra/database-apply.sh
#   ENV=dev REGION=us-east-1 ./infra/database-apply.sh
set -euo pipefail

ENV="${ENV:-dev}"
REGION="${REGION:-us-east-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# --- Networking (MVP-1 interim; see header note) ----------------------------
VPC_ID="${VPC_ID:-vpc-03d1e840c04bc94f1}"
SUBNET_IDS="${SUBNET_IDS:-subnet-01594ae384ee13769 subnet-008008051e9e35a74 subnet-01e49400058ac1f09}"
ECS_TASK_SG_ID="${ECS_TASK_SG_ID:-sg-0690e02ba20cf57a8}" # scanipy-workers

# --- Instance shape ----------------------------------------------------------
INSTANCE_CLASS="${INSTANCE_CLASS:-db.t4g.micro}"
ENGINE_VERSION="${ENGINE_VERSION:-16.14}"
ALLOCATED_STORAGE="${ALLOCATED_STORAGE:-20}"
DB_NAME="${DB_NAME:-scanipy}"
MASTER_USERNAME="${MASTER_USERNAME:-scanipy_admin}"

DB_IDENTIFIER="scanipy-${ENV}-postgres"
SG_NAME="scanipy-${ENV}-database"
SUBNET_GROUP_NAME="scanipy-${ENV}-db-subnet-group"
MASTER_SECRET_NAME="scanipy/${ENV}/rds-master"

log()  { echo "[$(date -u +%H:%M:%S)] $*"; }
done_() { echo "  ✓ $*"; }

log "Provisioning CMP-CP-03 RDS for env=${ENV} region=${REGION} account=${ACCOUNT_ID}"

# ---------------------------------------------------------------------------
# Security group — inbound 5432 from the ECS task SG only
# ---------------------------------------------------------------------------
log "Ensuring security group ${SG_NAME}..."
SG_ID=$(aws ec2 describe-security-groups \
  --region "${REGION}" \
  --filters "Name=group-name,Values=${SG_NAME}" "Name=vpc-id,Values=${VPC_ID}" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")

if [[ "${SG_ID}" == "None" || -z "${SG_ID}" ]]; then
  SG_ID=$(aws ec2 create-security-group \
    --group-name "${SG_NAME}" \
    --description "Scanipy RDS PostgreSQL - inbound 5432 from ECS tasks only" \
    --vpc-id "${VPC_ID}" \
    --region "${REGION}" \
    --query GroupId --output text)
  aws ec2 create-tags --region "${REGION}" --resources "${SG_ID}" \
    --tags Key=Component,Value=CMP-CP-03 Key=Env,Value="${ENV}" Key=Name,Value="${SG_NAME}"
  done_ "Created security group: ${SG_ID}"
else
  done_ "Security group already exists: ${SG_ID}"
fi

# Idempotent ingress authorize (ignore "already exists").
aws ec2 authorize-security-group-ingress \
  --group-id "${SG_ID}" \
  --protocol tcp --port 5432 \
  --source-group "${ECS_TASK_SG_ID}" \
  --region "${REGION}" > /dev/null 2>&1 || true
done_ "Ingress 5432 from ${ECS_TASK_SG_ID} (scanipy-workers) authorized on ${SG_ID}"

# ---------------------------------------------------------------------------
# DB subnet group
# ---------------------------------------------------------------------------
log "Ensuring DB subnet group ${SUBNET_GROUP_NAME}..."
if aws rds describe-db-subnet-groups --region "${REGION}" \
    --db-subnet-group-name "${SUBNET_GROUP_NAME}" > /dev/null 2>&1; then
  done_ "DB subnet group already exists: ${SUBNET_GROUP_NAME}"
else
  # shellcheck disable=SC2086
  aws rds create-db-subnet-group \
    --db-subnet-group-name "${SUBNET_GROUP_NAME}" \
    --db-subnet-group-description "Scanipy ${ENV} RDS subnet group (interim: default-VPC public subnets, CLAR-DEPLOY-23 pending)" \
    --subnet-ids ${SUBNET_IDS} \
    --region "${REGION}" \
    --tags Key=Component,Value=CMP-CP-03 Key=Env,Value="${ENV}" > /dev/null
  done_ "Created DB subnet group: ${SUBNET_GROUP_NAME}"
fi

# ---------------------------------------------------------------------------
# Master password — generated locally, never read back via get-secret-value
# ---------------------------------------------------------------------------
if aws secretsmanager describe-secret --secret-id "${MASTER_SECRET_NAME}" --region "${REGION}" > /dev/null 2>&1; then
  log "Master secret ${MASTER_SECRET_NAME} already exists — reusing (this script never calls get-secret-value on it)."
  if [[ -z "${SCANIPY_RDS_MASTER_PASSWORD:-}" ]]; then
    echo "ERROR: ${MASTER_SECRET_NAME} already exists in Secrets Manager but this script cannot read it back" >&2
    echo "(get-secret-value is intentionally never called on it). Re-run with" >&2
    echo "SCANIPY_RDS_MASTER_PASSWORD=<the value you set previously> to proceed idempotently," >&2
    echo "or delete the DB instance + secret to start clean." >&2
    exit 1
  fi
  MASTER_PASSWORD="${SCANIPY_RDS_MASTER_PASSWORD}"
else
  MASTER_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
  aws secretsmanager create-secret \
    --name "${MASTER_SECRET_NAME}" \
    --description "Scanipy ${ENV} RDS master credential (CMP-CP-03, dev/test scope)" \
    --secret-string "{\"username\":\"${MASTER_USERNAME}\",\"password\":\"${MASTER_PASSWORD}\",\"dbname\":\"${DB_NAME}\",\"port\":5432}" \
    --region "${REGION}" \
    --tags Key=Component,Value=CMP-CP-03 Key=Env,Value="${ENV}" > /dev/null
  done_ "Master credential generated and stored: ${MASTER_SECRET_NAME}"
fi

# ---------------------------------------------------------------------------
# RDS instance
# ---------------------------------------------------------------------------
log "Ensuring RDS instance ${DB_IDENTIFIER}..."
EXISTING_STATUS=$(aws rds describe-db-instances --region "${REGION}" \
  --db-instance-identifier "${DB_IDENTIFIER}" \
  --query 'DBInstances[0].DBInstanceStatus' --output text 2>/dev/null || echo "None")

if [[ "${EXISTING_STATUS}" == "None" || -z "${EXISTING_STATUS}" ]]; then
  aws rds create-db-instance \
    --db-instance-identifier "${DB_IDENTIFIER}" \
    --engine postgres \
    --engine-version "${ENGINE_VERSION}" \
    --db-instance-class "${INSTANCE_CLASS}" \
    --allocated-storage "${ALLOCATED_STORAGE}" \
    --storage-type gp3 \
    --storage-encrypted \
    --db-name "${DB_NAME}" \
    --master-username "${MASTER_USERNAME}" \
    --master-user-password "${MASTER_PASSWORD}" \
    --db-subnet-group-name "${SUBNET_GROUP_NAME}" \
    --vpc-security-group-ids "${SG_ID}" \
    --no-publicly-accessible \
    --no-multi-az \
    --backup-retention-period 1 \
    --no-deletion-protection \
    --auto-minor-version-upgrade \
    --region "${REGION}" \
    --tags Key=Component,Value=CMP-CP-03 Key=Env,Value="${ENV}" > /dev/null
  done_ "RDS instance creation requested: ${DB_IDENTIFIER}"
else
  done_ "RDS instance already exists (status=${EXISTING_STATUS}): ${DB_IDENTIFIER}"
fi

log "Waiting for ${DB_IDENTIFIER} to become available (this can take several minutes)..."
aws rds wait db-instance-available --region "${REGION}" --db-instance-identifier "${DB_IDENTIFIER}"
done_ "RDS instance available: ${DB_IDENTIFIER}"

DB_ENDPOINT=$(aws rds describe-db-instances --region "${REGION}" \
  --db-instance-identifier "${DB_IDENTIFIER}" \
  --query 'DBInstances[0].Endpoint.Address' --output text)
DB_PORT=$(aws rds describe-db-instances --region "${REGION}" \
  --db-instance-identifier "${DB_IDENTIFIER}" \
  --query 'DBInstances[0].Endpoint.Port' --output text)

# Refresh the secret with the now-known endpoint (still generated locally,
# never read back — this is a put, not a get).
aws secretsmanager put-secret-value \
  --secret-id "${MASTER_SECRET_NAME}" \
  --secret-string "{\"username\":\"${MASTER_USERNAME}\",\"password\":\"${MASTER_PASSWORD}\",\"host\":\"${DB_ENDPOINT}\",\"port\":${DB_PORT},\"dbname\":\"${DB_NAME}\"}" \
  --region "${REGION}" > /dev/null
done_ "Master secret updated with endpoint: ${MASTER_SECRET_NAME}"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "========================================"
echo " DONE — CMP-CP-03 RDS provisioned"
echo "========================================"
echo "DB instance:        ${DB_IDENTIFIER}"
echo "Endpoint:            ${DB_ENDPOINT}:${DB_PORT}"
echo "Security group:      ${SG_ID} (${SG_NAME}, inbound 5432 from ${ECS_TASK_SG_ID} only)"
echo "DB subnet group:     ${SUBNET_GROUP_NAME}"
echo "Master credential:   ${MASTER_SECRET_NAME} (Secrets Manager — value never printed)"
echo ""
echo "Run migrations with:"
echo "  export SCANIPY_DATABASE_URL=\"postgresql://${MASTER_USERNAME}:<password>@${DB_ENDPOINT}:${DB_PORT}/${DB_NAME}\""
echo "  alembic upgrade head"
