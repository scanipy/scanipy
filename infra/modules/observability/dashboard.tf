# CMP-DEPLOY-03 — CloudWatch Dashboard
# One dashboard covering the four subsystems per DOC-CMP-DEPLOY-03 §4.2.

resource "aws_cloudwatch_dashboard" "scanipy" {
  dashboard_name = "scanipy-${var.env}"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "text"
        x      = 0; y = 0; width = 24; height = 1
        properties = { markdown = "## Scanipy v3.2 — ${var.env} | [Runbook](https://github.com/scanipy/scanipy/blob/main/docs/cross-cutting/DOC-RUNBOOK.md)" }
      },

      # --- Scan lifecycle ---
      {
        type   = "metric"
        x      = 0; y = 1; width = 8; height = 6
        properties = {
          title  = "Snapshot worker — failure count"
          region = var.region
          metrics = [["Scanipy/v3.2", "snapshot_worker.failure_count"]]
          view   = "timeSeries"; stat = "Sum"; period = 300
        }
      },
      {
        type   = "metric"
        x      = 8; y = 1; width = 8; height = 6
        properties = {
          title  = "Detector worker — failure count"
          region = var.region
          metrics = [["Scanipy/v3.2", "detector_worker.failure_count"]]
          view   = "timeSeries"; stat = "Sum"; period = 300
        }
      },
      {
        type   = "metric"
        x      = 16; y = 1; width = 8; height = 6
        properties = {
          title  = "Callback HMAC rejections"
          region = var.region
          metrics = [["Scanipy/v3.2", "callback.hmac_reject_count"]]
          view   = "timeSeries"; stat = "Sum"; period = 300
        }
      },

      # --- Attestor / determinism ---
      {
        type   = "metric"
        x      = 0; y = 7; width = 12; height = 6
        properties = {
          title  = "INCIDENT: Attestor core-partition diff (any non-zero = incident)"
          region = var.region
          metrics = [["Scanipy/v3.2", "attestor.core_diff_count"]]
          view   = "timeSeries"; stat = "Sum"; period = 60
          annotations = { horizontal = [{ value = 0; label = "incident threshold"; color = "#d62728" }] }
        }
      },
      {
        type   = "metric"
        x      = 12; y = 7; width = 12; height = 6
        properties = {
          title  = "CW-DETECT oracle disagreement"
          region = var.region
          metrics = [["Scanipy/v3.2", "cw_detect.oracle_disagreement_count"]]
          view   = "timeSeries"; stat = "Sum"; period = 1800
        }
      },

      # --- CI gates ---
      {
        type   = "metric"
        x      = 0; y = 13; width = 12; height = 6
        properties = {
          title  = "e-process martingale test status (1=pass, 0=incident)"
          region = var.region
          metrics = [["Scanipy/v3.2", "eprocess.martingale_test_status"]]
          view   = "timeSeries"; stat = "Minimum"; period = 300
        }
      },

      # --- DLQ depth ---
      {
        type   = "metric"
        x      = 12; y = 13; width = 12; height = 6
        properties = {
          title  = "DLQ depth — snapshot + detector"
          region = var.region
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.snapshot_dlq_name],
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.detector_dlq_name]
          ]
          view = "timeSeries"; stat = "Maximum"; period = 600
        }
      },

      # --- Alarm summary ---
      # Alarm ARNs are taken from the alarm resources directly (an earlier
      # revision built them by string interpolation and rendered the
      # `${data.aws_caller_identity...}` fragment literally into the JSON).
      {
        type   = "alarm"
        x      = 0; y = 19; width = 24; height = 4
        properties = {
          title = "All Scanipy alarms"
          alarms = concat(
            [
              aws_cloudwatch_metric_alarm.snapshot_worker_failure_rate.arn,
              aws_cloudwatch_metric_alarm.detector_worker_failure_rate.arn,
              aws_cloudwatch_metric_alarm.callback_hmac_reject.arn,
              aws_cloudwatch_metric_alarm.attestor_core_diff.arn,
              aws_cloudwatch_metric_alarm.cw_detect_oracle_disagreement.arn,
              aws_cloudwatch_metric_alarm.eprocess_martingale_test_failure.arn,
              aws_cloudwatch_metric_alarm.dlq_snapshot_messages.arn,
              aws_cloudwatch_metric_alarm.dlq_detector_messages.arn,
              aws_cloudwatch_metric_alarm.snapshot_queue_oldest_age.arn,
              aws_cloudwatch_metric_alarm.detector_queue_oldest_age.arn,
            ],
            aws_cloudwatch_metric_alarm.attestor_run_absent[*].arn,
            aws_cloudwatch_metric_alarm.eprocess_gate_absent[*].arn,
          )
        }
      }
    ]
  })
}
