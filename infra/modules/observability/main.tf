# CMP-DEPLOY-03 — Observability surfaces (CloudWatch, X-Ray, SNS)
# Provisions log groups, metric namespace anchor, X-Ray group, and the SNS
# alarm bus. Alarms are in alarms.tf; dashboard in dashboard.tf.

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ---------------------------------------------------------------------------
# CloudWatch Log Groups
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "snapshot_worker" {
  name              = "/scanipy/${var.env}/snapshot-worker"
  retention_in_days = var.log_retention_days
  tags = {
    Component = "CMP-SNAP-05"
    Env       = var.env
  }
}

resource "aws_cloudwatch_log_group" "detector_worker" {
  name              = "/scanipy/${var.env}/detector-worker"
  retention_in_days = var.log_retention_days
  tags = {
    Component = "CMP-ORCH-03"
    Env       = var.env
  }
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/scanipy/${var.env}/api"
  retention_in_days = var.log_retention_days
  tags = {
    Component = "CMP-ORCH-01"
    Env       = var.env
  }
}

resource "aws_cloudwatch_log_group" "attestor" {
  name              = "/scanipy/${var.env}/attestor"
  retention_in_days = var.log_retention_days
  tags = {
    Component = "CMP-CP-05"
    Env       = var.env
  }
}

resource "aws_cloudwatch_log_group" "otel_collector" {
  name              = "/scanipy/${var.env}/otel-collector"
  retention_in_days = var.log_retention_days
  tags = {
    Component = "CMP-DEPLOY-03"
    Env       = var.env
  }
}

# ---------------------------------------------------------------------------
# X-Ray group — annotated by scan_id for AC-DEPLOY-03a cross-component trace
# ---------------------------------------------------------------------------
resource "aws_xray_group" "scanipy_prod" {
  group_name        = "scanipy-${var.env}"
  filter_expression = "annotation.env = \"${var.env}\""
  tags = {
    Component = "CMP-DEPLOY-03"
    Env       = var.env
  }
}

# ---------------------------------------------------------------------------
# SNS topic — alarm notification bus (PagerDuty wiring deferred: CLAR-DEPLOY-07)
# ---------------------------------------------------------------------------
resource "aws_sns_topic" "alarms" {
  name = "scanipy-${var.env}-alarms"
  tags = {
    Component = "CMP-DEPLOY-03"
    Env       = var.env
  }
}
