#!/usr/bin/env bash
# CMP-DEPLOY-03 — provision observability surfaces (AWS CLI equivalent of the
# Terraform module in infra/modules/observability/).
#
# Run with valid AWS credentials (OIDC or local profile). Records output to
# docs/status/STATUS-AWS-TEAM.md row 7 fields.
#
# Usage:  ./infra/observability-apply.sh [--env prod] [--region us-east-1]
set -euo pipefail

ENV="${ENV:-prod}"
REGION="${REGION:-us-east-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
NAMESPACE="Scanipy/v3.2"

log()  { echo "[$(date -u +%H:%M:%S)] $*"; }
done_() { echo "  ✓ $*"; }

log "Provisioning CMP-DEPLOY-03 observability for env=${ENV} region=${REGION} account=${ACCOUNT_ID}"

# ---------------------------------------------------------------------------
# SNS topic (alarm bus)
# ---------------------------------------------------------------------------
log "Creating SNS alarm topic..."
SNS_ARN=$(aws sns create-topic \
  --name "scanipy-${ENV}-alarms" \
  --region "${REGION}" \
  --tags Key=Component,Value=CMP-DEPLOY-03 Key=Env,Value="${ENV}" \
  --query TopicArn --output text)
done_ "SNS topic: ${SNS_ARN}"

# ---------------------------------------------------------------------------
# CloudWatch Log Groups
# ---------------------------------------------------------------------------
log "Creating CloudWatch Log Groups..."
for SVC in snapshot-worker detector-worker api attestor otel-collector; do
  aws logs create-log-group \
    --log-group-name "/scanipy/${ENV}/${SVC}" \
    --region "${REGION}" 2>/dev/null || true
  aws logs put-retention-policy \
    --log-group-name "/scanipy/${ENV}/${SVC}" \
    --retention-in-days 90 \
    --region "${REGION}"
  done_ "Log group: /scanipy/${ENV}/${SVC}"
done

# ---------------------------------------------------------------------------
# X-Ray group
# ---------------------------------------------------------------------------
log "Creating X-Ray group..."
XRAY_ARN=$(aws xray create-group \
  --group-name "scanipy-${ENV}" \
  --filter-expression "annotation.env = \"${ENV}\"" \
  --region "${REGION}" \
  --query GroupSummary.GroupARN --output text 2>/dev/null \
  || aws xray get-group \
    --group-name "scanipy-${ENV}" \
    --region "${REGION}" \
    --query GroupSummary.GroupARN --output text)
done_ "X-Ray group: ${XRAY_ARN}"

# ---------------------------------------------------------------------------
# CloudWatch Alarms
# ---------------------------------------------------------------------------
log "Creating CloudWatch Alarms (AC-DEPLOY-03c)..."

# Helper: put_alarm NAME DESCRIPTION METRIC NAMESPACE STAT COMPARISON THRESHOLD PERIOD EVAL_PERIODS SEVERITY [DIMENSIONS...]
put_alarm() {
  local name="$1" desc="$2" metric="$3" ns="$4" stat="$5" cmp="$6" threshold="$7" period="$8" eval_periods="$9" severity="${10}"
  shift 10
  local dims=("$@")

  local dim_args=()
  for d in "${dims[@]:-}"; do
    [[ -n "${d:-}" ]] && dim_args+=(--dimensions "Name=${d%%=*},Value=${d#*=}")
  done

  aws cloudwatch put-metric-alarm \
    --alarm-name "scanipy-${ENV}-${name}" \
    --alarm-description "${desc}" \
    --namespace "${ns}" \
    --metric-name "${metric}" \
    --statistic "${stat}" \
    --comparison-operator "${cmp}" \
    --threshold "${threshold}" \
    --period "${period}" \
    --evaluation-periods "${eval_periods}" \
    --alarm-actions "${SNS_ARN}" \
    --ok-actions "${SNS_ARN}" \
    --treat-missing-data notBreaching \
    --region "${REGION}" \
    "${dim_args[@]}" \
    --tags Key=Component,Value=CMP-DEPLOY-03 Key=Severity,Value="${severity}" Key=Env,Value="${ENV}"
  done_ "Alarm: scanipy-${ENV}-${name}"
}

# [AC] snapshot-worker failure rate
# NOTE: the Terraform module implements the precise 5%-rate math expression
# (100*failure/total > 5). The CLI put-metric-alarm command does not support
# --metrics math expressions in the simple helper format used here; this alarm
# fires on ANY failure (threshold 0) as a conservative proxy. Replace with the
# Terraform module for the production-accurate rate threshold.
put_alarm "snapshot-worker-failure-rate" \
  "Snapshot worker failure detected (CMP-SNAP-05). AC-DEPLOY-03c. NOTE: conservative threshold — Terraform module implements the 5%/15min rate alarm." \
  "snapshot_worker.failure_count" "${NAMESPACE}" "Sum" \
  "GreaterThanThreshold" "0" "300" "3" "high"

# [AC] detector-worker failure rate
# NOTE: same conservative proxy as snapshot above. Terraform module has the rate math.
put_alarm "detector-worker-failure-rate" \
  "Detector worker failure detected (CMP-ORCH-03). AC-DEPLOY-03c. NOTE: conservative threshold — Terraform module implements the 5%/15min rate alarm." \
  "detector_worker.failure_count" "${NAMESPACE}" "Sum" \
  "GreaterThanThreshold" "0" "300" "3" "high"

# [AC] callback HMAC rejection
put_alarm "callback-hmac-reject" \
  "HMAC callback rejection detected. Any rejection is suspicious. AC-DEPLOY-03c." \
  "callback.hmac_reject_count" "${NAMESPACE}" "Sum" \
  "GreaterThanThreshold" "0" "300" "1" "high"

# [AC] attestor core-partition diff — INCIDENT
put_alarm "attestor-core-diff" \
  "INCIDENT: Attestor core-partition SARIF diff (CMP-CP-05). Any non-zero is a hard incident. AC-DEPLOY-03c / INV-1." \
  "attestor.core_diff_count" "${NAMESPACE}" "Sum" \
  "GreaterThanThreshold" "0" "60" "1" "incident"

# [AC] CW-DETECT oracle disagreement
put_alarm "cw-detect-oracle-disagreement" \
  "CW-DETECT disagrees with differential oracle (CMP-SNAP-04). Triggers re-partition flow. AC-DEPLOY-03c." \
  "cw_detect.oracle_disagreement_count" "${NAMESPACE}" "Sum" \
  "GreaterThanThreshold" "0" "1800" "2" "high"

# [AC] e-process martingale test failure — INCIDENT
put_alarm "eprocess-martingale-test-failure" \
  "INCIDENT: e-process martingale unit test failed (CMP-TRI-02). Blocks customer-enablement deploy. AC-DEPLOY-03c / Gate 4." \
  "eprocess.martingale_test_status" "${NAMESPACE}" "Minimum" \
  "LessThanOrEqualToThreshold" "0" "300" "1" "incident"

# DLQ: snapshot
put_alarm "dlq-snapshot-messages" \
  "Messages in snapshot DLQ for >30min. Investigation required." \
  "ApproximateNumberOfMessagesVisible" "AWS/SQS" "Maximum" \
  "GreaterThanThreshold" "0" "600" "3" "high" \
  "QueueName=scanipy-snapshot-dlq"

# DLQ: detector
put_alarm "dlq-detector-messages" \
  "Messages in detector DLQ for >30min. Investigation required." \
  "ApproximateNumberOfMessagesVisible" "AWS/SQS" "Maximum" \
  "GreaterThanThreshold" "0" "600" "3" "high" \
  "QueueName=scanipy-detector-dlq"

# ---------------------------------------------------------------------------
# CloudWatch Dashboard
# ---------------------------------------------------------------------------
log "Creating CloudWatch Dashboard..."
DASHBOARD_BODY=$(python3 - <<PY
import json, sys

widgets = [
    {"type":"text","x":0,"y":0,"width":24,"height":1,
     "properties":{"markdown":"## Scanipy v3.2 — prod"}},
    {"type":"metric","x":0,"y":1,"width":8,"height":6,
     "properties":{"title":"Snapshot worker failures","region":"${REGION}",
       "metrics":[["Scanipy/v3.2","snapshot_worker.failure_count"]],"stat":"Sum","period":300}},
    {"type":"metric","x":8,"y":1,"width":8,"height":6,
     "properties":{"title":"Detector worker failures","region":"${REGION}",
       "metrics":[["Scanipy/v3.2","detector_worker.failure_count"]],"stat":"Sum","period":300}},
    {"type":"metric","x":16,"y":1,"width":8,"height":6,
     "properties":{"title":"Callback HMAC rejections","region":"${REGION}",
       "metrics":[["Scanipy/v3.2","callback.hmac_reject_count"]],"stat":"Sum","period":300}},
    {"type":"metric","x":0,"y":7,"width":12,"height":6,
     "properties":{"title":"INCIDENT: Attestor core-partition diff","region":"${REGION}",
       "metrics":[["Scanipy/v3.2","attestor.core_diff_count"]],"stat":"Sum","period":60}},
    {"type":"metric","x":12,"y":7,"width":12,"height":6,
     "properties":{"title":"CW-DETECT oracle disagreement","region":"${REGION}",
       "metrics":[["Scanipy/v3.2","cw_detect.oracle_disagreement_count"]],"stat":"Sum","period":1800}},
    {"type":"metric","x":0,"y":13,"width":12,"height":6,
     "properties":{"title":"e-process martingale status (1=pass)","region":"${REGION}",
       "metrics":[["Scanipy/v3.2","eprocess.martingale_test_status"]],"stat":"Minimum","period":300}},
    {"type":"metric","x":12,"y":13,"width":12,"height":6,
     "properties":{"title":"DLQ depth","region":"${REGION}",
       "metrics":[
         ["AWS/SQS","ApproximateNumberOfMessagesVisible","QueueName","scanipy-snapshot-dlq"],
         ["AWS/SQS","ApproximateNumberOfMessagesVisible","QueueName","scanipy-detector-dlq"]
       ],"stat":"Maximum","period":600}},
]
print(json.dumps({"widgets": widgets}))
PY
)
aws cloudwatch put-dashboard \
  --dashboard-name "scanipy-${ENV}" \
  --dashboard-body "${DASHBOARD_BODY}" \
  --region "${REGION}" > /dev/null
DASHBOARD_URL="https://${REGION}.console.aws.amazon.com/cloudwatch/home?region=${REGION}#dashboards/dashboard/scanipy-${ENV}"
done_ "Dashboard: ${DASHBOARD_URL}"

# ---------------------------------------------------------------------------
# OTel collector task definition
# ---------------------------------------------------------------------------
log "Registering OTel collector task definition..."
TASK_DEF=$(sed \
  -e "s/<ACCOUNT_ID>/${ACCOUNT_ID}/g" \
  -e "s/<REGION>/${REGION}/g" \
  -e "s/<ENV>/${ENV}/g" \
  "$(dirname "$0")/otel-collector/task-definition.json")
TASK_DEF_ARN=$(aws ecs register-task-definition \
  --cli-input-json "${TASK_DEF}" \
  --region "${REGION}" \
  --query taskDefinition.taskDefinitionArn --output text)
done_ "OTel collector task def: ${TASK_DEF_ARN}"

# ---------------------------------------------------------------------------
# Summary — paste these into STATUS-AWS-TEAM.md row 7
# ---------------------------------------------------------------------------
echo ""
echo "========================================"
echo " DONE — Evidence for STATUS-AWS-TEAM.md"
echo "========================================"
echo "SNS alarm topic:     ${SNS_ARN}"
echo "X-Ray group ARN:     ${XRAY_ARN}"
echo "Dashboard URL:       ${DASHBOARD_URL}"
echo "OTel task def ARN:   ${TASK_DEF_ARN}"
echo ""
echo "Alarm ARNs:"
for ALARM in snapshot-worker-failure-rate detector-worker-failure-rate callback-hmac-reject \
             attestor-core-diff cw-detect-oracle-disagreement eprocess-martingale-test-failure \
             dlq-snapshot-messages dlq-detector-messages; do
  ARN="arn:aws:cloudwatch:${REGION}:${ACCOUNT_ID}:alarm:scanipy-${ENV}-${ALARM}"
  echo "  ${ALARM}: ${ARN}"
done
