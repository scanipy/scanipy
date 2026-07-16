variable "region" {
  type    = string
  default = "us-east-1"
}

# Dev/test scope only (CLAR-DEPLOY-03: Multi-AZ is mandated for production,
# NOT for this track). Defaults to "dev" (not "prod", unlike the sibling
# observability/dataplane modules) so a bare `terraform apply` never targets
# a production identifier by accident.
variable "env" {
  type    = string
  default = "dev"
}

# --- Networking (MVP-1 interim — see main.tf header) -----------------------
# Default VPC / public subnets until CLAR-DEPLOY-23 (the private-subnet VPC
# remediation track, "3-VPC") lands. `publicly_accessible = false` on the DB
# instance itself means it never gets a public endpoint even though these
# subnets auto-assign public IPs to EC2 — but this is still an interim
# posture, not the target one. Move `subnet_ids` to the new private subnets
# the moment that module exists; nothing else in this module needs to change.
variable "vpc_id" {
  type    = string
  default = "vpc-03d1e840c04bc94f1" # account 123456789012 default VPC, us-east-1
}

variable "subnet_ids" {
  type = list(string)
  default = [
    "subnet-01594ae384ee13769", # us-east-1a
    "subnet-008008051e9e35a74", # us-east-1c
    "subnet-01e49400058ac1f09", # us-east-1b
  ]
}

# The already-live ECS task security group (CMP-DEPLOY-05,
# "Scanipy worker tasks egress to AWS services"). Inbound 5432 is scoped to
# THIS security group only — never a CIDR range — per the task's isolation
# requirement.
variable "ecs_task_security_group_id" {
  type    = string
  default = "sg-0690e02ba20cf57a8" # scanipy-workers
}

# --- Instance shape ----------------------------------------------------------

variable "instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "engine_version" {
  type    = string
  default = "16.14" # latest available PostgreSQL 16.x (CLAR-DEPLOY-03) at apply time
}

variable "allocated_storage" {
  type    = number
  default = 20
}

variable "db_name" {
  type    = string
  default = "scanipy"
}

variable "master_username" {
  type    = string
  default = "scanipy_admin"
}

# No default: never bake a credential into a .tf file, even a dev one.
# Sourced at apply time from a locally-generated value that is immediately
# persisted to AWS Secrets Manager (see infra/database-apply.sh) — this
# module was NOT applied via `terraform apply` (no state backend exists yet;
# same posture as infra/modules/dataplane and infra/modules/observability),
# so this variable documents the shape the eventual `terraform import` would
# need, not a value ever written to a `.tfvars` file.
variable "master_password" {
  type      = string
  sensitive = true
}

# Single-AZ (dev/test scope). CLAR-DEPLOY-03 only mandates Multi-AZ for
# production; do not flip this without a corresponding cost/approval note.
variable "multi_az" {
  type    = bool
  default = false
}
