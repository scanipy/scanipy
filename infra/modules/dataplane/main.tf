# CMP-DEPLOY-05 / CMP-DEPLOY-01 substrate — tenant data-plane buckets.
#
# APPLIED 2026-07-15 via AWS CLI (account 123456789012, us-east-1) — this file
# mirrors exactly what exists live so IaC matches reality. The resources were
# NOT created by `terraform apply`; a `terraform import` backlog item is
# recorded below. Until the import happens, treat the CLI-applied state as
# authoritative and keep this file in lockstep with any live change.
#
# terraform import backlog (run once a state backend exists):
#   terraform import aws_s3_bucket.snapshot scanipy-prod-snapshot
#   terraform import aws_s3_bucket.witness  scanipy-prod-witness
#   terraform import aws_s3_bucket.sarif    scanipy-prod-sarif
#   (+ the per-bucket versioning / encryption / public-access-block /
#    lifecycle / object-lock / policy sub-resources, each importable by
#    bucket name)
#
# Contents (per CLAUDE.md §8 retention tiers + CLAR-DEPLOY-02/16):
#   scanipy-prod-snapshot — CPG + snapshot artifacts, 90d expiry
#   scanipy-prod-witness  — taint witnesses, 1y expiry
#   scanipy-prod-sarif    — SARIF + provenance, 7y retention via S3 Object
#                           Lock in GOVERNANCE mode (see note below), no expiry
#
# Every bucket: Block Public Access (all four), versioning enabled, default
# encryption SSE-S3 (AES256). Per-tenant CMK envelope encryption is an
# OBJECT-layer concern (CMP-CP-02 encrypts tenant-scoped payloads with the
# tenant CMK before/at putObject) — the bucket default is deliberately SSE-S3,
# not SSE-KMS with a shared key, so a bucket-level default can never blur the
# per-tenant CMK boundary (CLAR-DEPLOY-04).
#
# Object Lock mode: GOVERNANCE, not COMPLIANCE. GOVERNANCE enforces the 7y
# WORM retention against everything except principals explicitly granted
# s3:BypassGovernanceRetention. Switching to COMPLIANCE (no bypass possible,
# not even root, for 7 years) is a management decision with irreversible cost
# consequences — recorded as pending in docs/status/STATUS-MANAGEMENT.md
# territory, NOT taken unilaterally here.
#
# Bucket policy (Layer 1 backstop, CLAR-DEPLOY-16): DenyNonTenantObjectPaths
# denies object read/write/delete on any key OUTSIDE orgs/* or _platform/*,
# for every principal. Enforcing the *per-org* boundary at the bucket-policy
# layer is not expressible with the current sts:AssumeRole flow (the session
# carries no org_id principal tag — the per-scan session policy in
# ../compute/session_policy.tf is the per-org boundary; the KMS encryption
# context is the third layer). See the honest-gap note in
# infra/tenant-isolation-apply.sh.
#
# RULE-9: INV-3-adjacent (tenant data isolation substrate). Security Analyst
# sign-off required before any change ships.

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

locals {
  snapshot_bucket = "scanipy-${var.env}-snapshot"
  witness_bucket  = "scanipy-${var.env}-witness"
  sarif_bucket    = "scanipy-${var.env}-sarif"

  common_tags = {
    Component = "CMP-DEPLOY-05"
    Env       = var.env
    ManagedBy = "tenant-isolation-apply"
  }
}

# ---------------------------------------------------------------------------
# Buckets
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "snapshot" {
  bucket = local.snapshot_bucket
  tags   = local.common_tags
}

resource "aws_s3_bucket" "witness" {
  bucket = local.witness_bucket
  tags   = local.common_tags
}

resource "aws_s3_bucket" "sarif" {
  bucket = local.sarif_bucket
  tags   = local.common_tags

  # Object Lock must be enabled at creation time (it was: CLI
  # create-bucket --object-lock-enabled-for-bucket, 2026-07-15).
  object_lock_enabled = true
}

# ---------------------------------------------------------------------------
# Block Public Access — all four, on all three buckets
# ---------------------------------------------------------------------------

resource "aws_s3_bucket_public_access_block" "all" {
  for_each = {
    snapshot = aws_s3_bucket.snapshot.id
    witness  = aws_s3_bucket.witness.id
    sarif    = aws_s3_bucket.sarif.id
  }

  bucket                  = each.value
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

# ---------------------------------------------------------------------------
# Versioning — enabled everywhere (Object Lock requires it on sarif)
# ---------------------------------------------------------------------------

resource "aws_s3_bucket_versioning" "all" {
  for_each = {
    snapshot = aws_s3_bucket.snapshot.id
    witness  = aws_s3_bucket.witness.id
    sarif    = aws_s3_bucket.sarif.id
  }

  bucket = each.value
  versioning_configuration {
    status = "Enabled"
  }
}

# ---------------------------------------------------------------------------
# Default encryption — SSE-S3 (per-tenant CMK envelope is object-layer; see
# module header)
# ---------------------------------------------------------------------------

resource "aws_s3_bucket_server_side_encryption_configuration" "all" {
  for_each = {
    snapshot = aws_s3_bucket.snapshot.id
    witness  = aws_s3_bucket.witness.id
    sarif    = aws_s3_bucket.sarif.id
  }

  bucket = each.value
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = false
  }
}

# ---------------------------------------------------------------------------
# Lifecycle — retention tiers per CLAUDE.md §8 (CPG 90d, witness 1y, SARIF
# none: the sarif bucket keeps everything for the 7y Object Lock window)
# ---------------------------------------------------------------------------

resource "aws_s3_bucket_lifecycle_configuration" "snapshot" {
  bucket = aws_s3_bucket.snapshot.id

  rule {
    id     = "scanipy-cpg-retention-90d"
    status = "Enabled"
    filter {}

    expiration {
      days = 90
    }
    noncurrent_version_expiration {
      noncurrent_days = 90
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "witness" {
  bucket = aws_s3_bucket.witness.id

  rule {
    id     = "scanipy-witness-retention-1y"
    status = "Enabled"
    filter {}

    expiration {
      days = 365
    }
    noncurrent_version_expiration {
      noncurrent_days = 365
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# ---------------------------------------------------------------------------
# Object Lock — sarif only: GOVERNANCE mode, 7y default retention
# (COMPLIANCE mode is a pending management decision — see module header)
# ---------------------------------------------------------------------------

resource "aws_s3_bucket_object_lock_configuration" "sarif" {
  bucket = aws_s3_bucket.sarif.id

  rule {
    default_retention {
      mode  = "GOVERNANCE"
      years = 7
    }
  }
}

# ---------------------------------------------------------------------------
# Bucket policy — Layer 1 prefix-namespace backstop (CLAR-DEPLOY-16).
# Deny object actions outside orgs/* (and, snapshot-bucket-only, _platform/*)
# for EVERY principal. NotResource (not an s3:prefix Condition) because
# s3:prefix is only populated on s3:ListBucket requests; on object actions
# the condition key is absent and StringNotLike would deny unconditionally.
#
# The _platform/* exemption is scoped to the snapshot bucket only: the
# session policy's S3PlatformReadOnly statement
# (services/substrate/session_policy.py) grants read access to
# `${snapshot}/_platform/*` exclusively — witness and sarif never serve
# _platform/* content, so carrying the exemption there would be an
# unnecessary defence-in-depth gap.
# ---------------------------------------------------------------------------

resource "aws_s3_bucket_policy" "prefix_deny" {
  for_each = {
    snapshot = aws_s3_bucket.snapshot.id
    witness  = aws_s3_bucket.witness.id
    sarif    = aws_s3_bucket.sarif.id
  }

  bucket = each.value

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyNonTenantObjectPaths"
        Effect    = "Deny"
        Principal = "*"
        Action    = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        NotResource = concat(
          ["arn:aws:s3:::${each.value}/orgs/*"],
          each.key == "snapshot" ? ["arn:aws:s3:::${each.value}/_platform/*"] : []
        )
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "bucket_names" {
  description = "The three tenant data-plane bucket names (snapshot, witness, sarif)"
  value = {
    snapshot = aws_s3_bucket.snapshot.id
    witness  = aws_s3_bucket.witness.id
    sarif    = aws_s3_bucket.sarif.id
  }
}
