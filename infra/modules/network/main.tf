# CLAR-DEPLOY-23 / CMP-DEPLOY-01 substrate — private-subnet network remediation.
#
# APPLIED 2026-07-16 via AWS CLI (account 508703380027, us-east-1) — this file
# mirrors exactly what exists live so IaC matches reality, following the same
# pattern as infra/modules/dataplane/main.tf and infra/modules/kms/main.tf
# (no `terraform apply` was run — there is no state backend in this repo yet;
# see the `terraform import` backlog note below). This file is the durable
# design record + reviewable IaC; infra/network-remediation-apply.sh is what
# actually ran against the live account.
#
# --- Problem this fixes ------------------------------------------------
#
# CLAR-DEPLOY-09 (RESOLVED 2026-05-23, WBS.md §17) ratified "single VPC per
# env, three subnet tiers, VPC endpoints" as the CMP-DEPLOY-01 network model.
# Live reality (verified 2026-07-16 via `aws ecs describe-services`) had
# drifted from that decision: both `snapshot-worker` and `detector-worker`
# ECS services ran in the DEFAULT VPC's default public subnet
# (`subnet-01e49400058ac1f09`, us-east-1b, `172.31.80.0/20`) with
# `assignPublicIp=ENABLED` — every task got a public IP directly reachable
# from the internet. This module + the apply script close that gap.
#
# --- CIDR / VPC choice (documented per the track's "your call" latitude) ---
#
# Reused the EXISTING DEFAULT VPC (`vpc-03d1e840c04bc94f1`, `172.31.0.0/16`)
# rather than standing up a new VPC. Rationale:
#   - Zero new VPC-level cost (a second VPC would need its own IGW, and NAT
#     gateway inter-VPC traffic would need peering/TGW to reach the same
#     account resources — pure overhead for an MVP with a single account).
#   - The default VPC's six default subnets already consume only 6 of 16
#     possible `/20` blocks in `172.31.0.0/16` (`.0/.16/.32/.48/.64/.80`) —
#     ten `/20` blocks are free, comfortably enough for the new tiers below.
#   - The two existing default PUBLIC subnets (us-east-1a `172.31.0.0/20`,
#     us-east-1b `172.31.80.0/20`) are reused as this module's "public" tier
#     verbatim (not recreated) — the NAT gateway lands in the us-east-1a one.
#     They already route to the existing IGW (`igw-053ffb381e2e68b96`) via the
#     VPC's main route table, so no change was needed there.
#
# New subnets added by this module (2 AZs: us-east-1a, us-east-1b — matching
# the two reused public subnets):
#   private-a   172.31.96.0/20   us-east-1a   (ECS tasks; NAT egress)
#   private-b   172.31.112.0/20  us-east-1b   (ECS tasks; NAT egress)
#   isolated-a  172.31.128.0/20  us-east-1a   (reserved for CMP-DEPLOY future
#   isolated-b  172.31.144.0/20  us-east-1b    RDS track — no internet route
#                                               at all, local-VPC only)
#
# --- NAT gateway (MVP scope: ONE, not per-AZ) ---------------------------
#
# A single NAT gateway (`scanipy-prod-nat`) lives in the reused us-east-1a
# public subnet, with a new Elastic IP. This is a deliberate single point of
# failure accepted for MVP cost reasons (~$32.85/mo flat + per-GB data,
# pre-approved) — both private subnets route 0.0.0.0/0 through it. A second,
# per-AZ NAT gateway would double this fixed cost; not justified while both
# ECS services run at `desiredCount=0` baseline. Revisit if/when the services
# carry sustained production traffic.
#
# --- VPC endpoints: what shipped live vs. what's coded-but-not-applied ---
#
# S3 Gateway Endpoint: APPLIED live, both private + isolated route tables.
# Zero incremental cost (gateway endpoints have no hourly or per-GB charge —
# only route-table prefix-list entries) and a genuine cost *reduction*: ECR
# image-layer pulls are served from S3 under the hood, so this removes the
# highest-volume traffic class from the NAT gateway's per-GB data-processing
# bill, for free.
#
# Interface endpoints (ECR api/dkr, CloudWatch Logs, Secrets Manager, KMS,
# SQS) are defined below (resource blocks exist, `count = 0` by default via
# `var.enable_interface_endpoints`) but were NOT applied live in this pass.
# Reasoning, in the interest of not silently blowing the pre-approved AWS
# budget (this track's instructions pre-cleared "RDS ~$15/mo, NAT gateway
# ~$32/mo — total ~$47-50/mo baseline"; interface endpoints are not in that
# figure):
#   - Each interface endpoint costs ~$0.01/hr per AZ (~$7.30/mo) + per-GB
#     data processing. The full 5-service, 2-AZ set this task's brief
#     enumerates (ECR api, ECR dkr, Logs, Secrets Manager, KMS, SQS = 6
#     endpoints) would run ~$87.60/mo at 2 AZs, or ~$43.80/mo even at 1 AZ —
#     roughly matching or exceeding the NAT gateway's own cost, on top of it.
#   - At current traffic (both services `desiredCount=0`; this MVP's only
#     live traffic is one-shot verification `run-task` calls), the flat
#     hourly reservation cost dominates — there is no meaningful per-GB data
#     saving to offset it, unlike the S3 gateway endpoint case above.
#   - The NAT gateway + tightened security group (below) already provide
#     full, working connectivity to ECR/Secrets Manager/KMS/SQS over HTTPS —
#     this is a hardening / cost-optimization deferral, not a functional
#     gap. No ECS task is currently blocked from reaching any AWS API.
#   - `var.enable_interface_endpoints = true` turns every interface endpoint
#     on in one flag once a human signs off on the added recurring cost —
#     see CLAR-DEPLOY-23 in WBS.md §17 for the full number and the decision
#     this needs.
#
# --- Security group ------------------------------------------------------
#
# The pre-existing `scanipy-workers` security group (`sg-0690e02ba20cf57a8`,
# used by both ECS services, untracked by any prior IaC file — created ad
# hoc, no Terraform or apply-script owned it before this module) is brought
# under IaC here and TIGHTENED in place (revoke-then-authorize, not a new
# group + orphan the old one): the shipped rule allowed ALL protocols/ports
# egress to 0.0.0.0/0. Tightened to the task's brief ("HTTPS out for image
# pulls/API calls, no unsolicited inbound"): tcp/443 to 0.0.0.0/0, plus
# tcp+udp/53 to the VPC CIDR only (Route 53 Resolver — required for the task
# to resolve ECR/S3/SQS/KMS hostnames at all; omitting it would silently
# break every HTTPS call). No ingress rules (unchanged — there were none).
#
# --- terraform import backlog (run once a state backend exists) ---------
#   terraform import aws_subnet.private["a"]         subnet-<TBD>
#   terraform import aws_subnet.private["b"]         subnet-<TBD>
#   terraform import aws_subnet.isolated["a"]        subnet-<TBD>
#   terraform import aws_subnet.isolated["b"]         subnet-<TBD>
#   terraform import aws_eip.nat                      eipalloc-<TBD>
#   terraform import aws_nat_gateway.this             nat-<TBD>
#   terraform import aws_route_table.private          rtb-<TBD>
#   terraform import aws_route_table.isolated         rtb-<TBD>
#   terraform import aws_vpc_endpoint.s3              vpce-<TBD>
#   terraform import aws_security_group.workers       sg-0690e02ba20cf57a8
#   (exact IDs recorded in docs/status/STATUS-AWS-TEAM.md § row 11 evidence)
#
# RULE-9: not INV-3/INV-4-owning itself, but it carries the tenant-isolation
# egress path (scanipy-workers SG) that CMP-DEPLOY-05's session-policy model
# assumes is scoped — Security Analyst review is still appropriate before
# this ships, per the general "touches production network posture" bar.

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "env" {
  type    = string
  default = "prod"
}

variable "vpc_id" {
  description = "Existing VPC to build the new subnet tiers in (this track reuses the default VPC — see module header)."
  type        = string
  default     = "vpc-03d1e840c04bc94f1"
}

variable "public_subnet_ids" {
  description = "Existing (reused, not recreated) default-VPC public subnets, keyed by AZ suffix."
  type        = map(string)
  default = {
    a = "subnet-01594ae384ee13769" # us-east-1a, 172.31.0.0/20
    b = "subnet-01e49400058ac1f09" # us-east-1b, 172.31.80.0/20
  }
}

variable "internet_gateway_id" {
  description = "Existing default-VPC internet gateway (reused, not recreated)."
  type        = string
  default     = "igw-053ffb381e2e68b96"
}

variable "azs" {
  description = "The two AZs this module provisions private/isolated subnets in."
  type        = map(string)
  default = {
    a = "us-east-1a"
    b = "us-east-1b"
  }
}

variable "private_cidrs" {
  type = map(string)
  default = {
    a = "172.31.96.0/20"
    b = "172.31.112.0/20"
  }
}

variable "isolated_cidrs" {
  type = map(string)
  default = {
    a = "172.31.128.0/20"
    b = "172.31.144.0/20"
  }
}

variable "enable_interface_endpoints" {
  description = <<-EOT
    Off by default (see module header cost note). Flip to true once a human
    has signed off on the added ~$44-88/mo (1-AZ vs 2-AZ) recurring cost for
    the ECR/Logs/Secrets-Manager/KMS/SQS interface endpoints. The S3 gateway
    endpoint (free) is always on regardless of this flag.
  EOT
  type    = bool
  default = false
}

locals {
  common_tags = {
    Component = "CMP-DEPLOY-01"
    Env       = var.env
    ManagedBy = "network-remediation-apply"
    Clar      = "CLAR-DEPLOY-23"
  }

  interface_endpoint_services = toset(
    var.enable_interface_endpoints
    ? ["ecr.api", "ecr.dkr", "logs", "secretsmanager", "kms", "sqs"]
    : []
  )
}

# ---------------------------------------------------------------------------
# Private tier — ECS worker tasks. Egress via the NAT gateway.
# ---------------------------------------------------------------------------

resource "aws_subnet" "private" {
  for_each = var.azs

  vpc_id                  = var.vpc_id
  cidr_block              = var.private_cidrs[each.key]
  availability_zone       = each.value
  map_public_ip_on_launch = false

  tags = merge(local.common_tags, {
    Name = "scanipy-${var.env}-private-${each.key}"
    Tier = "private"
  })
}

# ---------------------------------------------------------------------------
# Isolated tier — reserved for the future RDS track (CLAR-DEPLOY-03). No
# internet route of any kind; local-VPC traffic only.
# ---------------------------------------------------------------------------

resource "aws_subnet" "isolated" {
  for_each = var.azs

  vpc_id                  = var.vpc_id
  cidr_block              = var.isolated_cidrs[each.key]
  availability_zone       = each.value
  map_public_ip_on_launch = false

  tags = merge(local.common_tags, {
    Name = "scanipy-${var.env}-isolated-${each.key}"
    Tier = "isolated"
  })
}

# ---------------------------------------------------------------------------
# NAT gateway — ONE, in the reused us-east-1a public subnet (MVP scope).
# ---------------------------------------------------------------------------

resource "aws_eip" "nat" {
  domain = "vpc"
  tags   = merge(local.common_tags, { Name = "scanipy-${var.env}-nat" })
}

resource "aws_nat_gateway" "this" {
  allocation_id = aws_eip.nat.id
  subnet_id     = var.public_subnet_ids["a"]
  tags          = merge(local.common_tags, { Name = "scanipy-${var.env}-nat" })

  depends_on = [var.internet_gateway_id]
}

# ---------------------------------------------------------------------------
# Route tables
# ---------------------------------------------------------------------------

resource "aws_route_table" "private" {
  vpc_id = var.vpc_id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this.id
  }
  tags = merge(local.common_tags, { Name = "scanipy-${var.env}-private-rt" })
}

resource "aws_route_table_association" "private" {
  for_each       = aws_subnet.private
  subnet_id      = each.value.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table" "isolated" {
  vpc_id = var.vpc_id
  tags   = merge(local.common_tags, { Name = "scanipy-${var.env}-isolated-rt" })
  # Deliberately no default route — isolated tier is local-VPC-only.
}

resource "aws_route_table_association" "isolated" {
  for_each       = aws_subnet.isolated
  subnet_id      = each.value.id
  route_table_id = aws_route_table.isolated.id
}

# ---------------------------------------------------------------------------
# VPC endpoints
# ---------------------------------------------------------------------------

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.private.id, aws_route_table.isolated.id]
  tags              = merge(local.common_tags, { Name = "scanipy-${var.env}-s3-gw" })
}

resource "aws_security_group" "vpc_endpoints" {
  count       = var.enable_interface_endpoints ? 1 : 0
  name        = "scanipy-${var.env}-vpc-endpoints"
  description = "Allow HTTPS from the private-subnet worker SG to interface VPC endpoints"
  vpc_id      = var.vpc_id

  ingress {
    description     = "HTTPS from ECS worker tasks"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.workers.id]
  }

  tags = merge(local.common_tags, { Name = "scanipy-${var.env}-vpc-endpoints" })
}

resource "aws_vpc_endpoint" "interface" {
  for_each             = local.interface_endpoint_services
  vpc_id               = var.vpc_id
  service_name         = "com.amazonaws.${var.region}.${each.value}"
  vpc_endpoint_type    = "Interface"
  subnet_ids           = [for s in aws_subnet.private : s.id]
  security_group_ids   = [aws_security_group.vpc_endpoints[0].id]
  private_dns_enabled  = true
  tags                 = merge(local.common_tags, { Name = "scanipy-${var.env}-${each.value}" })
}

# ---------------------------------------------------------------------------
# Security group — tightened in place (see module header).
# ---------------------------------------------------------------------------

resource "aws_security_group" "workers" {
  # NOTE: this brings the pre-existing sg-0690e02ba20cf57a8 under IaC. If
  # importing into a real terraform state, `terraform import` this resource
  # onto that ID rather than letting `apply` create a duplicate group.
  name        = "scanipy-workers"
  description = "Scanipy worker tasks egress to AWS services"
  vpc_id      = var.vpc_id

  egress {
    description = "HTTPS to AWS APIs (ECR, S3, SQS, KMS, Secrets Manager, CloudWatch)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "DNS (TCP) to the in-VPC Route 53 Resolver"
    from_port   = 53
    to_port     = 53
    protocol    = "tcp"
    cidr_blocks = ["172.31.0.0/16"]
  }

  egress {
    description = "DNS (UDP) to the in-VPC Route 53 Resolver"
    from_port   = 53
    to_port     = 53
    protocol    = "udp"
    cidr_blocks = ["172.31.0.0/16"]
  }

  tags = merge(local.common_tags, { Name = "scanipy-workers" })
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "private_subnet_ids" {
  value = [for s in aws_subnet.private : s.id]
}

output "isolated_subnet_ids" {
  value = [for s in aws_subnet.isolated : s.id]
}

output "nat_gateway_id" {
  value = aws_nat_gateway.this.id
}

output "workers_security_group_id" {
  value = aws_security_group.workers.id
}
