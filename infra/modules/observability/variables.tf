variable "region" {
  type    = string
  default = "us-east-1"
}

variable "env" {
  type    = string
  default = "prod"
}

# Live DLQ names (verified 2026-07-15 via `aws sqs list-queues`):
# the queues carry the `-jobs-dlq` suffix, not the bare `-dlq` the module
# previously assumed.
variable "snapshot_dlq_name" {
  type    = string
  default = "scanipy-prod-snapshot-jobs-dlq"
}

variable "detector_dlq_name" {
  type    = string
  default = "scanipy-prod-detector-jobs-dlq"
}

# Jobs queues — consumed by the ApproximateAgeOfOldestMessage backstop alarms
# (CLAR-DEPLOY-20: they catch the silent-worker-death mode the rate alarms'
# IF-guard deliberately ignores).
variable "snapshot_jobs_queue_name" {
  type    = string
  default = "scanipy-prod-snapshot-jobs"
}

variable "detector_jobs_queue_name" {
  type    = string
  default = "scanipy-prod-detector-jobs"
}

# CLAR-DEPLOY-20: companion absence alarms for the run-scoped incident metrics
# (attestor.core_diff_count, eprocess.martingale_test_status). Default FALSE —
# flipping this to true is an explicit T-STAGE-A-01 go-live checklist item;
# until the emitters + daily canary heartbeat are live the absence alarms
# would page permanently.
variable "enable_absence_alarms" {
  type    = bool
  default = false
}

variable "log_retention_days" {
  type    = number
  default = 90
}
