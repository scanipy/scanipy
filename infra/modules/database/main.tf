# CMP-CP-03 substrate — RDS PostgreSQL 16 instance (CLAR-DEPLOY-03).
#
# APPLIED 2026-07-16 via AWS CLI (account 123456789012, us-east-1) —
# `infra/database-apply.sh` performed the live provisioning; this module
# mirrors exactly what exists live, the same posture as
# `infra/modules/dataplane` and `infra/modules/observability` (see their
# header comments). No `terraform apply` was run — there is no state backend
# in this environment yet. A `terraform import` backlog is recorded below so
# this file becomes authoritative the moment a backend exists.
#
# terraform import backlog (run once a state backend exists):
#   terraform import aws_security_group.database          <sg-id>
#   terraform import aws_db_subnet_group.scanipy           scanipy-<env>-db-subnet-group
#   terraform import aws_db_instance.scanipy               scanipy-<env>-postgres
#
# Scope: dev/test, NOT production (per the assigned track). CLAR-DEPLOY-03
# mandates Multi-AZ only for production; this instance is intentionally
# single-AZ, db.t4g.micro. Do not read this module as the production RDS
# shape — a separate prod module/apply is required before go-live, sized and
# reviewed independently (Multi-AZ, larger instance class, longer backup
# retention, deletion protection).
#
# Isolation: the security group admits inbound 5432 ONLY from the live ECS
# task security group (`var.ecs_task_security_group_id`, "scanipy-workers")
# — never a CIDR block. The instance itself is `publicly_accessible = false`
# regardless of the subnets' own public-IP-on-launch setting (MVP-1 interim
# subnet note in variables.tf).
#
# RULE-9 note: this module does not itself touch INV-3/INV-4 (it is
# substrate, not detection logic); CMP-CP-02 (credential encryption) and the
# application-side RLS binding (`db/session.py`, already merged) remain the
# INV-3-adjacent owners of what gets written through this instance.

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

resource "aws_security_group" "database" {
  name        = "scanipy-${var.env}-database"
  description = "Scanipy RDS PostgreSQL - inbound 5432 from ECS tasks only"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from ECS task security group"
    from_port        = 5432
    to_port          = 5432
    protocol         = "tcp"
    security_groups  = [var.ecs_task_security_group_id]
  }

  egress {
    description = "unrestricted egress (RDS never initiates outbound connections that need scoping)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Component = "CMP-CP-03"
    Env       = var.env
  }
}

resource "aws_db_subnet_group" "scanipy" {
  name       = "scanipy-${var.env}-db-subnet-group"
  subnet_ids = var.subnet_ids

  tags = {
    Component = "CMP-CP-03"
    Env       = var.env
  }
}

resource "aws_db_instance" "scanipy" {
  identifier     = "scanipy-${var.env}-postgres"
  engine         = "postgres"
  engine_version = var.engine_version

  instance_class    = var.instance_class
  allocated_storage = var.allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.master_username
  password = var.master_password
  port     = 5432

  db_subnet_group_name   = aws_db_subnet_group.scanipy.name
  vpc_security_group_ids = [aws_security_group.database.id]
  publicly_accessible    = false
  multi_az                = var.multi_az

  # Dev/test posture — see the "Scope" note above. A production instance
  # needs deletion_protection = true and a real backup/snapshot policy.
  backup_retention_period   = 1
  skip_final_snapshot       = true
  deletion_protection       = false
  apply_immediately         = true
  auto_minor_version_upgrade = true

  tags = {
    Component = "CMP-CP-03"
    Env       = var.env
  }
}
