output "alarm_sns_arn" {
  description = "SNS topic ARN for alarm notifications (scanipy-{env}-alarms)"
  value       = aws_sns_topic.alarms.arn
}

output "snapshot_worker_log_group" {
  value = aws_cloudwatch_log_group.snapshot_worker.name
}

output "detector_worker_log_group" {
  value = aws_cloudwatch_log_group.detector_worker.name
}

output "api_log_group" {
  value = aws_cloudwatch_log_group.api.name
}

output "attestor_log_group" {
  value = aws_cloudwatch_log_group.attestor.name
}

output "otel_collector_log_group" {
  value = aws_cloudwatch_log_group.otel_collector.name
}

output "xray_group_arn" {
  value = aws_xray_group.scanipy_prod.arn
}

output "dashboard_name" {
  value = aws_cloudwatch_dashboard.scanipy.dashboard_name
}

# All alarm ARNs — consumed by TST-AC-DEPLOY-03c. The two absence alarms are
# null until enable_absence_alarms is flipped (T-STAGE-A-01 / CLAR-DEPLOY-20).
output "alarm_arns" {
  value = {
    snapshot_worker_failure_rate    = aws_cloudwatch_metric_alarm.snapshot_worker_failure_rate.arn
    detector_worker_failure_rate    = aws_cloudwatch_metric_alarm.detector_worker_failure_rate.arn
    callback_hmac_reject            = aws_cloudwatch_metric_alarm.callback_hmac_reject.arn
    attestor_core_diff              = aws_cloudwatch_metric_alarm.attestor_core_diff.arn
    cw_detect_oracle_disagreement   = aws_cloudwatch_metric_alarm.cw_detect_oracle_disagreement.arn
    eprocess_martingale_test_failure = aws_cloudwatch_metric_alarm.eprocess_martingale_test_failure.arn
    dlq_snapshot_messages           = aws_cloudwatch_metric_alarm.dlq_snapshot_messages.arn
    dlq_detector_messages           = aws_cloudwatch_metric_alarm.dlq_detector_messages.arn
    snapshot_queue_oldest_age       = aws_cloudwatch_metric_alarm.snapshot_queue_oldest_age.arn
    detector_queue_oldest_age       = aws_cloudwatch_metric_alarm.detector_queue_oldest_age.arn
    attestor_run_absent             = one(aws_cloudwatch_metric_alarm.attestor_run_absent[*].arn)
    eprocess_gate_absent            = one(aws_cloudwatch_metric_alarm.eprocess_gate_absent[*].arn)
  }
}
