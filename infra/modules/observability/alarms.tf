# CMP-DEPLOY-03 §3.5 — CloudWatch Alarms (AC-DEPLOY-03c)
# Twelve alarms. The six in the AC-DEPLOY-03c verbatim statement are marked
# with [AC]; the two DLQ alarms are also required by §3.5; the two queue-age
# backstops and the two (flag-gated) absence alarms are CLAR-DEPLOY-20.
#
# Metrics in the custom namespace 'Scanipy/v3.2' do not exist until the first
# data point is published by a running worker. CloudWatch alarms on missing
# data default to INSUFFICIENT_DATA, not ALARM, so they are safe to provision
# ahead of data flow.
#
# CLAR-DEPLOY-20 rate-alarm contract: denominator = completions
# (failure_count + success_count), NOT job starts — a start-emitted total
# lands in a different 300 s period than the failure of any >5-min job, which
# the IF(total==0) guard would then silence. The alarms read the
# zero-dimension rollup series produced by the collector's awsemf
# `dimension_rollup_option: ZeroAndSingleDimensionRollup` pin
# (infra/otel-collector/config.yaml) — if that pin drifts, the dimensions={}
# queries silently match nothing.

locals {
  namespace = "Scanipy/v3.2"
  alarm_sns = [aws_sns_topic.alarms.arn]
}

# [AC] snapshot-worker failure rate > 5% over 15 min (CLAR-DEPLOY-20 rate math)
resource "aws_cloudwatch_metric_alarm" "snapshot_worker_failure_rate" {
  alarm_name          = "scanipy-${var.env}-snapshot-worker-failure-rate"
  alarm_description   = "Snapshot worker completion-failure rate exceeded 5% over 15 min (CMP-SNAP-05). AC-DEPLOY-03c / CLAR-DEPLOY-20."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  datapoints_to_alarm = 3
  threshold           = 5

  metric_query {
    id          = "fail"
    return_data = false
    metric {
      metric_name = "snapshot_worker.failure_count"
      namespace   = local.namespace
      period      = 300
      stat        = "Sum"
      dimensions  = {}
    }
  }

  metric_query {
    id          = "succ"
    return_data = false
    metric {
      metric_name = "snapshot_worker.success_count"
      namespace   = local.namespace
      period      = 300
      stat        = "Sum"
      dimensions  = {}
    }
  }

  metric_query {
    id          = "fail0"
    expression  = "FILL(fail, 0)"
    return_data = false
  }

  metric_query {
    id          = "succ0"
    expression  = "FILL(succ, 0)"
    return_data = false
  }

  metric_query {
    id          = "total"
    expression  = "fail0 + succ0"
    return_data = false
  }

  metric_query {
    id          = "rate"
    expression  = "IF(total > 0, 100 * fail0 / total, 0)"
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

# [AC] detector-worker failure rate > 5% over 15 min (CLAR-DEPLOY-20 rate math)
resource "aws_cloudwatch_metric_alarm" "detector_worker_failure_rate" {
  alarm_name          = "scanipy-${var.env}-detector-worker-failure-rate"
  alarm_description   = "Detector worker completion-failure rate exceeded 5% over 15 min (CMP-ORCH-03). AC-DEPLOY-03c / CLAR-DEPLOY-20."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  datapoints_to_alarm = 3
  threshold           = 5

  metric_query {
    id          = "fail"
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
    id          = "succ"
    return_data = false
    metric {
      metric_name = "detector_worker.success_count"
      namespace   = local.namespace
      period      = 300
      stat        = "Sum"
      dimensions  = {}
    }
  }

  metric_query {
    id          = "fail0"
    expression  = "FILL(fail, 0)"
    return_data = false
  }

  metric_query {
    id          = "succ0"
    expression  = "FILL(succ, 0)"
    return_data = false
  }

  metric_query {
    id          = "total"
    expression  = "fail0 + succ0"
    return_data = false
  }

  metric_query {
    id          = "rate"
    expression  = "IF(total > 0, 100 * fail0 / total, 0)"
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

# CLAR-DEPLOY-20: jobs-queue oldest-age backstop — catches the
# silent-worker-death mode (no completions emitted at all) that the rate
# alarms' IF-guard deliberately treats as OK.
resource "aws_cloudwatch_metric_alarm" "snapshot_queue_oldest_age" {
  alarm_name          = "scanipy-${var.env}-snapshot-queue-oldest-age"
  alarm_description   = "Oldest message in the snapshot jobs queue > 15 min — workers stalled or dead (CMP-SNAP-05). CLAR-DEPLOY-20 backstop for the rate alarm's zero-traffic OK-state."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = 900
  period              = 300
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  statistic           = "Maximum"
  dimensions = {
    QueueName = var.snapshot_jobs_queue_name
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

resource "aws_cloudwatch_metric_alarm" "detector_queue_oldest_age" {
  alarm_name          = "scanipy-${var.env}-detector-queue-oldest-age"
  alarm_description   = "Oldest message in the detector jobs queue > 15 min — workers stalled or dead (CMP-ORCH-03). CLAR-DEPLOY-20 backstop for the rate alarm's zero-traffic OK-state."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = 900
  period              = 300
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  statistic           = "Maximum"
  dimensions = {
    QueueName = var.detector_jobs_queue_name
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

# CLAR-DEPLOY-20: absence alarm — the attestor must produce >=1 datapoint of
# attestor.core_diff_count per day (emit-healthy-value contract: add(0) on a
# clean run + daily canary heartbeat, canary.yml cron 30 3 * * *). Absence is
# ambiguous (no incident vs. attestor never ran), hence treat_missing_data =
# breaching. Gated behind enable_absence_alarms (default false); flipping it
# true is a T-STAGE-A-01 go-live checklist item.
resource "aws_cloudwatch_metric_alarm" "attestor_run_absent" {
  count = var.enable_absence_alarms ? 1 : 0

  alarm_name          = "scanipy-${var.env}-attestor-run-absent"
  alarm_description   = "No attestor.core_diff_count datapoint in 24 h — attestor (CMP-CP-05) or the daily canary heartbeat is not running. CLAR-DEPLOY-20 absence companion."
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  threshold           = 1
  period              = 86400
  namespace           = local.namespace
  metric_name         = "attestor.core_diff_count"
  statistic           = "SampleCount"

  alarm_actions             = local.alarm_sns
  ok_actions                = local.alarm_sns
  treat_missing_data        = "breaching"
  insufficient_data_actions = []

  tags = {
    Component = "CMP-DEPLOY-03"
    Severity  = "high"
    Env       = var.env
  }
}

# CLAR-DEPLOY-20: absence alarm — eprocess.martingale_test_status must be
# published on every CI Gate-4 run AND daily by canary.yml. Same pattern and
# flag as attestor_run_absent above (T-STAGE-A-01 flips the flag).
resource "aws_cloudwatch_metric_alarm" "eprocess_gate_absent" {
  count = var.enable_absence_alarms ? 1 : 0

  alarm_name          = "scanipy-${var.env}-eprocess-gate-absent"
  alarm_description   = "No eprocess.martingale_test_status datapoint in 24 h — Gate 4 / canary heartbeat (CMP-TRI-02) is not publishing. CLAR-DEPLOY-20 absence companion."
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  threshold           = 1
  period              = 86400
  namespace           = local.namespace
  metric_name         = "eprocess.martingale_test_status"
  statistic           = "SampleCount"

  alarm_actions             = local.alarm_sns
  ok_actions                = local.alarm_sns
  treat_missing_data        = "breaching"
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
