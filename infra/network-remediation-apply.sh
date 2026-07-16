#!/usr/bin/env bash
# CLAR-DEPLOY-23 / CMP-DEPLOY-01 — private-subnet network remediation.
#
# Fixes a live deviation from the already-RESOLVED CLAR-DEPLOY-09 network
# model ("single VPC per env, three subnet tiers, VPC endpoints"): the
# snapshot-worker and detector-worker ECS services were running in the
# default VPC's default PUBLIC subnet with assignPublicIp=ENABLED.
#
# Idempotent: safe to re-run; every step is create-if-missing (tag-based
# lookup) or an in-place overwrite of the same-named resource. Never deletes
# anything. IaC mirror: infra/modules/network/main.tf (full rationale for
# every choice — CIDR layout, single NAT gateway, S3-gateway-only VPC
# endpoints — lives there, not repeated here).
#
# Applied live 2026-07-16 (us-east-1, account 123456789012). Records output
# for docs/status/STATUS-AWS-TEAM.md row 11 + WBS.md CLAR-DEPLOY-23.
#
# Usage:  ./infra/network-remediation-apply.sh
set -euo pipefail

ENV="${ENV:-prod}"
REGION="${REGION:-us-east-1}"
VPC_ID="${VPC_ID:-vpc-03d1e840c04bc94f1}"
IGW_ID="${IGW_ID:-igw-053ffb381e2e68b96}"
PUBLIC_SUBNET_A="${PUBLIC_SUBNET_A:-subnet-01594ae384ee13769}" # us-east-1a
PUBLIC_SUBNET_B="${PUBLIC_SUBNET_B:-subnet-01e49400058ac1f09}" # us-east-1b (ECS ran here, public, pre-fix)
CLUSTER="${CLUSTER:-scanipy-prod}"
WORKERS_SG_NAME="${WORKERS_SG_NAME:-scanipy-workers}"

log()  { echo "[$(date -u +%H:%M:%S)] $*" >&2; }
done_() { echo "  [ok] $*" >&2; }

log "CLAR-DEPLOY-23 network remediation: env=${ENV} region=${REGION} vpc=${VPC_ID}"

# ---------------------------------------------------------------------------
# Helper: find-or-create a subnet by Name tag.
# ---------------------------------------------------------------------------
find_or_create_subnet() {
  local name="$1" cidr="$2" az="$3" tier="$4"
  local existing
  existing=$(aws ec2 describe-subnets --region "${REGION}" \
    --filters "Name=vpc-id,Values=${VPC_ID}" "Name=tag:Name,Values=${name}" \
    --query "Subnets[0].SubnetId" --output text 2>/dev/null || echo "None")
  if [[ "${existing}" != "None" && -n "${existing}" ]]; then
    done_ "subnet exists: ${name} (${existing})"
    echo "${existing}"
    return 0
  fi
  local id
  id=$(aws ec2 create-subnet --region "${REGION}" \
    --vpc-id "${VPC_ID}" --cidr-block "${cidr}" --availability-zone "${az}" \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=${name}},{Key=Component,Value=CMP-DEPLOY-01},{Key=Env,Value=${ENV}},{Key=ManagedBy,Value=network-remediation-apply},{Key=Clar,Value=CLAR-DEPLOY-23},{Key=Tier,Value=${tier}}]" \
    --query "Subnet.SubnetId" --output text)
  aws ec2 modify-subnet-attribute --region "${REGION}" --subnet-id "${id}" --no-map-public-ip-on-launch
  done_ "subnet created: ${name} (${id}, ${cidr}, ${az})"
  echo "${id}"
}

log "Tier: private + isolated subnets (2 AZs)..."
PRIVATE_A=$(find_or_create_subnet "scanipy-${ENV}-private-a" "172.31.96.0/20"  "us-east-1a" "private")
PRIVATE_B=$(find_or_create_subnet "scanipy-${ENV}-private-b" "172.31.112.0/20" "us-east-1b" "private")
ISOLATED_A=$(find_or_create_subnet "scanipy-${ENV}-isolated-a" "172.31.128.0/20" "us-east-1a" "isolated")
ISOLATED_B=$(find_or_create_subnet "scanipy-${ENV}-isolated-b" "172.31.144.0/20" "us-east-1b" "isolated")

# ---------------------------------------------------------------------------
# NAT gateway — ONE, in the reused us-east-1a public subnet.
# ---------------------------------------------------------------------------
log "NAT gateway (single, MVP scope)..."

EIP_ALLOC=$(aws ec2 describe-addresses --region "${REGION}" \
  --filters "Name=tag:Name,Values=scanipy-${ENV}-nat" \
  --query "Addresses[0].AllocationId" --output text 2>/dev/null || echo "None")
if [[ "${EIP_ALLOC}" == "None" || -z "${EIP_ALLOC}" ]]; then
  EIP_ALLOC=$(aws ec2 allocate-address --region "${REGION}" --domain vpc \
    --tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Name,Value=scanipy-${ENV}-nat},{Key=Component,Value=CMP-DEPLOY-01},{Key=Clar,Value=CLAR-DEPLOY-23}]" \
    --query "AllocationId" --output text)
  done_ "EIP allocated: ${EIP_ALLOC}"
else
  done_ "EIP exists: ${EIP_ALLOC}"
fi

NAT_ID=$(aws ec2 describe-nat-gateways --region "${REGION}" \
  --filter "Name=vpc-id,Values=${VPC_ID}" "Name=tag:Name,Values=scanipy-${ENV}-nat" "Name=state,Values=pending,available" \
  --query "NatGateways[0].NatGatewayId" --output text 2>/dev/null || echo "None")
if [[ "${NAT_ID}" == "None" || -z "${NAT_ID}" ]]; then
  NAT_ID=$(aws ec2 create-nat-gateway --region "${REGION}" \
    --subnet-id "${PUBLIC_SUBNET_A}" --allocation-id "${EIP_ALLOC}" \
    --tag-specifications "ResourceType=natgateway,Tags=[{Key=Name,Value=scanipy-${ENV}-nat},{Key=Component,Value=CMP-DEPLOY-01},{Key=Clar,Value=CLAR-DEPLOY-23}]" \
    --query "NatGateway.NatGatewayId" --output text)
  done_ "NAT gateway created: ${NAT_ID} (in ${PUBLIC_SUBNET_A}) — waiting for it to become available..."
  aws ec2 wait nat-gateway-available --region "${REGION}" --nat-gateway-ids "${NAT_ID}"
  done_ "NAT gateway available: ${NAT_ID}"
else
  done_ "NAT gateway exists: ${NAT_ID}"
fi

# ---------------------------------------------------------------------------
# Route tables.
# ---------------------------------------------------------------------------
log "Route tables..."

find_or_create_rt() {
  local name="$1"
  local existing
  existing=$(aws ec2 describe-route-tables --region "${REGION}" \
    --filters "Name=vpc-id,Values=${VPC_ID}" "Name=tag:Name,Values=${name}" \
    --query "RouteTables[0].RouteTableId" --output text 2>/dev/null || echo "None")
  if [[ "${existing}" != "None" && -n "${existing}" ]]; then
    echo "${existing}"
    return 0
  fi
  local id
  id=$(aws ec2 create-route-table --region "${REGION}" --vpc-id "${VPC_ID}" \
    --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=${name}},{Key=Component,Value=CMP-DEPLOY-01},{Key=Clar,Value=CLAR-DEPLOY-23}]" \
    --query "RouteTable.RouteTableId" --output text)
  echo "${id}"
}

PRIVATE_RT=$(find_or_create_rt "scanipy-${ENV}-private-rt")
done_ "private route table: ${PRIVATE_RT}"
ISOLATED_RT=$(find_or_create_rt "scanipy-${ENV}-isolated-rt")
done_ "isolated route table: ${ISOLATED_RT}"

# 0.0.0.0/0 -> NAT on the private RT (idempotent: create-route errors if it
# already exists identically; replace-route is the safe upsert).
aws ec2 replace-route --region "${REGION}" --route-table-id "${PRIVATE_RT}" \
  --destination-cidr-block "0.0.0.0/0" --nat-gateway-id "${NAT_ID}" 2>/dev/null \
  || aws ec2 create-route --region "${REGION}" --route-table-id "${PRIVATE_RT}" \
       --destination-cidr-block "0.0.0.0/0" --nat-gateway-id "${NAT_ID}" >/dev/null
done_ "private RT: 0.0.0.0/0 -> ${NAT_ID}"

# Isolated RT deliberately gets no default route (local-VPC-only tier).

for pair in "${PRIVATE_A}:${PRIVATE_RT}" "${PRIVATE_B}:${PRIVATE_RT}" "${ISOLATED_A}:${ISOLATED_RT}" "${ISOLATED_B}:${ISOLATED_RT}"; do
  SUBNET_ID="${pair%%:*}"; RT_ID="${pair##*:}"
  ASSOC=$(aws ec2 describe-route-tables --region "${REGION}" --route-table-ids "${RT_ID}" \
    --query "RouteTables[0].Associations[?SubnetId=='${SUBNET_ID}'].RouteTableAssociationId | [0]" --output text 2>/dev/null || echo "None")
  if [[ "${ASSOC}" == "None" || -z "${ASSOC}" ]]; then
    aws ec2 associate-route-table --region "${REGION}" --subnet-id "${SUBNET_ID}" --route-table-id "${RT_ID}" >/dev/null
    done_ "associated ${SUBNET_ID} -> ${RT_ID}"
  else
    done_ "already associated: ${SUBNET_ID} -> ${RT_ID}"
  fi
done

# ---------------------------------------------------------------------------
# S3 Gateway VPC endpoint (free — see module header for the "why" and why
# interface endpoints are deliberately NOT applied here).
# ---------------------------------------------------------------------------
log "S3 gateway VPC endpoint..."

S3_VPCE=$(aws ec2 describe-vpc-endpoints --region "${REGION}" \
  --filters "Name=vpc-id,Values=${VPC_ID}" "Name=service-name,Values=com.amazonaws.${REGION}.s3" "Name=vpc-endpoint-type,Values=Gateway" \
  --query "VpcEndpoints[?State=='available'].VpcEndpointId | [0]" --output text 2>/dev/null || echo "None")
if [[ "${S3_VPCE}" == "None" || -z "${S3_VPCE}" ]]; then
  S3_VPCE=$(aws ec2 create-vpc-endpoint --region "${REGION}" \
    --vpc-id "${VPC_ID}" --service-name "com.amazonaws.${REGION}.s3" --vpc-endpoint-type Gateway \
    --route-table-ids "${PRIVATE_RT}" "${ISOLATED_RT}" \
    --tag-specifications "ResourceType=vpc-endpoint,Tags=[{Key=Name,Value=scanipy-${ENV}-s3-gw},{Key=Component,Value=CMP-DEPLOY-01},{Key=Clar,Value=CLAR-DEPLOY-23}]" \
    --query "VpcEndpoint.VpcEndpointId" --output text)
  done_ "S3 gateway endpoint created: ${S3_VPCE}"
else
  # Ensure it's associated with both route tables even if it pre-existed.
  aws ec2 modify-vpc-endpoint --region "${REGION}" --vpc-endpoint-id "${S3_VPCE}" \
    --add-route-table-ids "${PRIVATE_RT}" "${ISOLATED_RT}" >/dev/null 2>&1 || true
  done_ "S3 gateway endpoint exists: ${S3_VPCE}"
fi

# ---------------------------------------------------------------------------
# Security group: tighten scanipy-workers in place (find-or-create, then
# revoke the broad egress rule if present, authorize the scoped ones).
# ---------------------------------------------------------------------------
log "Security group: ${WORKERS_SG_NAME} (tighten to HTTPS+DNS egress only)..."

SG_ID=$(aws ec2 describe-security-groups --region "${REGION}" \
  --filters "Name=vpc-id,Values=${VPC_ID}" "Name=group-name,Values=${WORKERS_SG_NAME}" \
  --query "SecurityGroups[0].GroupId" --output text 2>/dev/null || echo "None")
if [[ "${SG_ID}" == "None" || -z "${SG_ID}" ]]; then
  SG_ID=$(aws ec2 create-security-group --region "${REGION}" \
    --group-name "${WORKERS_SG_NAME}" --description "Scanipy worker tasks egress to AWS services" --vpc-id "${VPC_ID}" \
    --tag-specifications "ResourceType=security-group,Tags=[{Key=Name,Value=${WORKERS_SG_NAME}},{Key=Component,Value=CMP-DEPLOY-01},{Key=Clar,Value=CLAR-DEPLOY-23}]" \
    --query "GroupId" --output text)
  done_ "security group created: ${SG_ID}"
else
  done_ "security group exists: ${SG_ID}"
fi

# Revoke the broad all-protocol egress rule if it's still present (idempotent
# — revoke on a non-existent rule just errors, which we swallow).
if aws ec2 revoke-security-group-egress --region "${REGION}" --group-id "${SG_ID}" \
  --ip-permissions 'IpProtocol=-1,IpRanges=[{CidrIp=0.0.0.0/0}]' >/dev/null 2>&1; then
  done_ "revoked broad all-protocol egress rule"
else
  done_ "broad egress rule already absent"
fi

# Authorize the scoped rules (idempotent — authorize on an existing identical
# rule errors "already exists", which we swallow).
aws ec2 authorize-security-group-egress --region "${REGION}" --group-id "${SG_ID}" \
  --ip-permissions 'IpProtocol=tcp,FromPort=443,ToPort=443,IpRanges=[{CidrIp=0.0.0.0/0,Description="HTTPS to AWS APIs"}]' >/dev/null 2>&1 || true
aws ec2 authorize-security-group-egress --region "${REGION}" --group-id "${SG_ID}" \
  --ip-permissions 'IpProtocol=tcp,FromPort=53,ToPort=53,IpRanges=[{CidrIp=172.31.0.0/16,Description="DNS TCP to VPC resolver"}]' >/dev/null 2>&1 || true
aws ec2 authorize-security-group-egress --region "${REGION}" --group-id "${SG_ID}" \
  --ip-permissions 'IpProtocol=udp,FromPort=53,ToPort=53,IpRanges=[{CidrIp=172.31.0.0/16,Description="DNS UDP to VPC resolver"}]' >/dev/null 2>&1 || true
done_ "egress scoped to tcp/443 (0.0.0.0/0) + tcp+udp/53 (VPC CIDR only)"

# ---------------------------------------------------------------------------
# ECS services: move both to the new private subnets, disable public IP.
# ---------------------------------------------------------------------------
log "ECS services: move snapshot-worker + detector-worker to private subnets..."

for SVC in snapshot-worker detector-worker; do
  aws ecs update-service --region "${REGION}" --cluster "${CLUSTER}" --service "${SVC}" \
    --network-configuration "awsvpcConfiguration={subnets=[${PRIVATE_A},${PRIVATE_B}],securityGroups=[${SG_ID}],assignPublicIp=DISABLED}" \
    --force-new-deployment >/dev/null
  done_ "updated ${SVC}: subnets=[${PRIVATE_A},${PRIVATE_B}] assignPublicIp=DISABLED sg=${SG_ID}"
done

log ""
log "Summary:"
log "  private subnets:  ${PRIVATE_A} (us-east-1a) ${PRIVATE_B} (us-east-1b)"
log "  isolated subnets: ${ISOLATED_A} (us-east-1a) ${ISOLATED_B} (us-east-1b)"
log "  NAT gateway:       ${NAT_ID} (in ${PUBLIC_SUBNET_A})"
log "  private route tbl: ${PRIVATE_RT}"
log "  isolated route tbl:${ISOLATED_RT}"
log "  S3 gateway VPCE:   ${S3_VPCE}"
log "  security group:    ${SG_ID} (${WORKERS_SG_NAME})"
log "Done."
