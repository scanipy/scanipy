variable "region" {
  type    = string
  default = "us-east-1"
}

variable "env" {
  type    = string
  default = "prod"
}

variable "snapshot_dlq_name" {
  type    = string
  default = "scanipy-snapshot-dlq"
}

variable "detector_dlq_name" {
  type    = string
  default = "scanipy-detector-dlq"
}

variable "log_retention_days" {
  type    = number
  default = 90
}
