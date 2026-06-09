# CMP-DEPLOY-03 §3.5 — CloudWatch Alarms (AC-DEPLOY-03c)
# Eight alarms as specified. The six in the AC-DEPLOY-03c verbatim statement
# are marked with [AC]; the two DLQ alarms are also required by §3.5.
#
# Metrics in the custom namespace 'Scanipy/v3.2' do not exist until the first
# data point is published by a running worker. CloudWatch alarms on missing
# data default to INSUFFICIENT_DATA, not ALARM, so they are safe to provision
# ahead of data flow.

locals {
  namespace = "Scanipy/v3.2"
  alarm_sns = [var.alarm_sns_arn]
}

# [AC] snapshot-worker failure rate > 5% over 15 min
resource "aws_cloudwatch_metric_alarm" "snapshot_worker_failure_rate" {
  alarm_name          = "scanipy-${var.env}-snapshot-worker-failure-rate"
  alarm_description   = "Snapshot worker failure rate exceeded 5% (CMP-SNAP-05). AC-DEPLOY-03c."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = 5

  metric_query {
    id          = "failure"
    return_data = false
    metric {
      metric_name = "snapshot_worker.failure_count"
      namespace   = local.namespace
      period      = 300
      stat        = "Sum"
      dimensions  = { env_digest = "all" }
    }
  }

  metric_query {
    id          = "total"
    return_data = false
    metric {
      metric_name = "snapshot_worker.job_count"
      namespace   = local.namespace
      period      = 300
      stat        = "Sum"
      dimensions  = {}
    }
  }

  metric_query {
    id          = "rate"
    expression  = "IF(total > 0, 100 * failure / total, 0)"
    return_data = true
  }

  alarm_actions             = local.alarm_sns
  ok_actions                = local.alarm_sns
  treat_missing_data        = "notBreaching"
  insufficient_data_actions = []

  tags = {
    Component = "CMP-DEPLOY-03"
    Severity  = "high"
    Env       = var.env
  }
}

# [AC] detector-worker failure rate > 5% over 15 min
resource "aws_cloudwatch_metric_alarm" "detector_worker_failure_rate" {
  alarm_name          = "scanipy-${var.env}-detector-worker-failure-rate"
  alarm_description   = "Detector worker failure rate exceeded 5% (CMP-ORCH-03). AC-DEPLOY-03c."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = 5

  metric_query {
    id          = "failure"
    return_data = false
    metric {
      metric_name = "detector_worker.failure_count"
      namespace   = local.namespace
      period      = 300
      stat        = "Sum"
      dimensions  = {}
    }
  }

  metric_query {
    id          = "total"
    return_data = false
    metric {
      metric_name = "detector_worker.job_count"
      namespace   = local.namespace
      period      = 300
      stat        = "Sum"
      dimensions  = {}
    }
  }

  metric_query {
    id          = "rate"
    expression  = "IF(total > 0, 100 * failure / total, 0)"
    return_data = true
  }

  alarm_actions             = local.alarm_sns
  ok_actions                = local.alarm_sns
  treat_missing_data        = "notBreaching"
  insufficient_data_actions = []

  tags = {
    Component = "CMP-DEPLOY-03"
    Severity  = "high"
    Env       = var.env
  }
}

# [AC] callback HMAC rejection rate > 0 over 5 min (any rejection is suspicious)
resource "aws_cloudwatch_metric_alarm" "callback_hmac_reject" {
  alarm_name          = "scanipy-${var.env}-callback-hmac-reject"
  alarm_description   = "HMAC callback rejection detected (CMP-ORCH-01/SNAP-01). Any rejection is suspicious. AC-DEPLOY-03c."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 0
  period              = 300
  namespace           = local.namespace
  metric_name         = "callback.hmac_reject_count"
  statistic           = "Sum"

  alarm_actions             = local.alarm_sns
  ok_actions                = local.alarm_sns
  treat_missing_data        = "notBreaching"
  insufficient_data_actions = []

  tags = {
    Component = "CMP-DEPLOY-03"
    Severity  = "high"
    Env       = var.env
  }
}

# [AC] attestor core-partition diff > 0 — INCIDENT grade; any non-zero is a hard incident
resource "aws_cloudwatch_metric_alarm" "attestor_core_diff" {
  alarm_name          = "scanipy-${var.env}-attestor-core-diff"
  alarm_description   = "INCIDENT: Attestor core-partition SARIF diff detected (CMP-CP-05). Any non-zero count is a hard incident per AC-DEPLOY-03c / INV-1."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 0
  period              = 60
  namespace           = local.namespace
  metric_name         = "attestor.core_diff_count"
  statistic           = "Sum"

  alarm_actions             = local.alarm_sns
  ok_actions                = local.alarm_sns
  treat_missing_data        = "notBreaching"
  insufficient_data_actions = []

  tags = {
    Component = "CMP-DEPLOY-03"
    Severity  = "incident"
    Env       = var.env
  }
}

# [AC] CW-DETECT oracle disagreement > 0 over 1 h
resource "aws_cloudwatch_metric_alarm" "cw_detect_oracle_disagreement" {
  alarm_name          = "scanipy-${var.env}-cw-detect-oracle-disagreement"
  alarm_description   = "CW-DETECT disagrees with differential oracle (CMP-SNAP-04). Triggers re-partition flow. AC-DEPLOY-03c."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = 0
  period              = 1800
  namespace           = local.namespace
  metric_name         = "cw_detect.oracle_disagreement_count"
  statistic           = "Sum"

  alarm_actions             = local.alarm_sns
  ok_actions                = local.alarm_sns
  treat_missing_data        = "notBreaching"
  insufficient_data_actions = []

  tags = {
    Component = "CMP-DEPLOY-03"
    Severity  = "high"
    Env       = var.env
  }
}

# [AC] e-process martingale unit test failure (status = 0 means failed)
resource "aws_cloudwatch_metric_alarm" "eprocess_martingale_test_failure" {
  alarm_name          = "scanipy-${var.env}-eprocess-martingale-test-failure"
  alarm_description   = "INCIDENT: e-process martingale unit test failed (CMP-TRI-02). Blocks customer-enablement deploy. AC-DEPLOY-03c / Gate 4."
  comparison_operator = "LessThanOrEqualToThreshold"
  evaluation_periods  = 1
  threshold           = 0
  period              = 300
  namespace           = local.namespace
  metric_name         = "eprocess.martingale_test_status"
  statistic           = "Minimum"

  alarm_actions             = local.alarm_sns
  ok_actions                = local.alarm_sns
  treat_missing_data        = "notBreaching"
  insufficient_data_actions = []

  tags = {
    Component = "CMP-DEPLOY-03"
    Severity  = "incident"
    Env       = var.env
  }
}

# DLQ: snapshot queue > 0 sustained 30 min
resource "aws_cloudwatch_metric_alarm" "dlq_snapshot_messages" {
  alarm_name          = "scanipy-${var.env}-dlq-snapshot-messages"
  alarm_description   = "Messages in snapshot DLQ for > 30 min. Manual investigation required."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = 0
  period              = 600
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Maximum"
  dimensions = {
    QueueName = var.snapshot_dlq_name
  }

  alarm_actions             = local.alarm_sns
  ok_actions                = local.alarm_sns
  treat_missing_data        = "notBreaching"
  insufficient_data_actions = []

  tags = {
    Component = "CMP-DEPLOY-03"
    Severity  = "high"
    Env       = var.env
  }
}

# DLQ: detector queue > 0 sustained 30 min
resource "aws_cloudwatch_metric_alarm" "dlq_detector_messages" {
  alarm_name          = "scanipy-${var.env}-dlq-detector-messages"
  alarm_description   = "Messages in detector DLQ for > 30 min. Manual investigation required."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = 0
  period              = 600
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Maximum"
  dimensions = {
    QueueName = var.detector_dlq_name
  }

  alarm_actions             = local.alarm_sns
  ok_actions                = local.alarm_sns
  treat_missing_data        = "notBreaching"
  insufficient_data_actions = []

  tags = {
    Component = "CMP-DEPLOY-03"
    Severity  = "high"
    Env       = var.env
  }
}
