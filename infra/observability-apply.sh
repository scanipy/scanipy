#!/usr/bin/env bash
# CMP-DEPLOY-03 — provision observability surfaces (AWS CLI equivalent of the
# Terraform module in infra/modules/observability/).
#
# Run with valid AWS credentials (OIDC or local profile). Records output to
# docs/status/STATUS-AWS-TEAM.md row 7 fields.
#
# Usage:  ./infra/observability-apply.sh [--env prod] [--region us-east-1]
#
# TODO(CMP-DEPLOY-01 follow-up): ECR repository hardening
# (imageTagMutability=IMMUTABLE, scanOnPush=true) for scanipy-snapshot and
# scanipy-detector is currently applied ad hoc via the AWS CLI and is not
# codified in IaC. It is intentionally NOT added here — the ECR repositories
# are provisioned by CMP-DEPLOY-01's `infra/modules/registry` module
# (docs/components/DOC-CMP-DEPLOY-01.md), not by CMP-DEPLOY-03, so the fix
# belongs in that module (or its own apply script), not in this
# observability script. File a tracked follow-up against CMP-DEPLOY-01
# rather than folding registry-owned config into this script.
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
# SNS subscription (optional, idempotent)
# ---------------------------------------------------------------------------
# Set ALARM_EMAIL to subscribe an address to the alarm topic on every apply
# without creating duplicate subscriptions. The subscription lands in
# PendingConfirmation until the recipient clicks the confirmation link SNS
# emails them — that confirmation step cannot be automated from here.
if [[ -n "${ALARM_EMAIL:-}" ]]; then
  log "Checking SNS subscription for ${ALARM_EMAIL}..."
  EXISTING_SUB=$(aws sns list-subscriptions-by-topic \
    --topic-arn "${SNS_ARN}" \
    --region "${REGION}" \
    --query "Subscriptions[?Protocol=='email' && Endpoint=='${ALARM_EMAIL}'].SubscriptionArn" \
    --output text)
  if [[ -z "${EXISTING_SUB}" ]]; then
    aws sns subscribe \
      --topic-arn "${SNS_ARN}" \
      --protocol email \
      --notification-endpoint "${ALARM_EMAIL}" \
      --region "${REGION}" >/dev/null
    done_ "SNS subscription created for ${ALARM_EMAIL} (PendingConfirmation — recipient must confirm)"
  else
    done_ "SNS subscription already present for ${ALARM_EMAIL} (${EXISTING_SUB})"
  fi
else
  log "ALARM_EMAIL not set — skipping SNS subscription step (subscribe manually or re-run with ALARM_EMAIL=<addr>)"
fi

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
  --query Group.GroupARN --output text 2>/dev/null \
  || aws xray get-group \
    --group-name "scanipy-${ENV}" \
    --region "${REGION}" \
    --query Group.GroupARN --output text)
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

# Helper: put_rate_alarm NAME DESCRIPTION WORKER
# CLAR-DEPLOY-20 completion-failure rate: rate = IF(total > 0, 100*fail0/total, 0)
# where fail0 = FILL(<worker>.failure_count, 0), total = fail0 + FILL(<worker>.success_count, 0).
# 300 s periods, threshold 5, 3-of-3 evaluation periods (">5% over 15 min"),
# treat_missing_data = notBreaching. The dimensionless metric queries read the
# zero-dimension rollup series pinned in infra/otel-collector/config.yaml.
put_rate_alarm() {
  local name="$1" desc="$2" worker="$3"

  local metrics
  metrics=$(cat <<JSON
[
  {"Id": "fail", "ReturnData": false,
   "MetricStat": {"Metric": {"Namespace": "${NAMESPACE}", "MetricName": "${worker}.failure_count"},
                  "Period": 300, "Stat": "Sum"}},
  {"Id": "succ", "ReturnData": false,
   "MetricStat": {"Metric": {"Namespace": "${NAMESPACE}", "MetricName": "${worker}.success_count"},
                  "Period": 300, "Stat": "Sum"}},
  {"Id": "fail0", "Expression": "FILL(fail, 0)", "ReturnData": false},
  {"Id": "succ0", "Expression": "FILL(succ, 0)", "ReturnData": false},
  {"Id": "total", "Expression": "fail0 + succ0", "ReturnData": false},
  {"Id": "rate", "Expression": "IF(total > 0, 100 * fail0 / total, 0)", "ReturnData": true}
]
JSON
)

  aws cloudwatch put-metric-alarm \
    --alarm-name "scanipy-${ENV}-${name}" \
    --alarm-description "${desc}" \
    --metrics "${metrics}" \
    --comparison-operator GreaterThanThreshold \
    --threshold 5 \
    --evaluation-periods 3 \
    --datapoints-to-alarm 3 \
    --alarm-actions "${SNS_ARN}" \
    --ok-actions "${SNS_ARN}" \
    --treat-missing-data notBreaching \
    --region "${REGION}" \
    --tags Key=Component,Value=CMP-DEPLOY-03 Key=Severity,Value=high Key=Env,Value="${ENV}"
  done_ "Alarm: scanipy-${ENV}-${name}"
}

# [AC] snapshot-worker failure rate > 5% over 15 min (CLAR-DEPLOY-20 rate math)
put_rate_alarm "snapshot-worker-failure-rate" \
  "Snapshot worker completion-failure rate exceeded 5% over 15 min (CMP-SNAP-05). AC-DEPLOY-03c / CLAR-DEPLOY-20." \
  "snapshot_worker"

# [AC] detector-worker failure rate > 5% over 15 min (CLAR-DEPLOY-20 rate math)
put_rate_alarm "detector-worker-failure-rate" \
  "Detector worker completion-failure rate exceeded 5% over 15 min (CMP-ORCH-03). AC-DEPLOY-03c / CLAR-DEPLOY-20." \
  "detector_worker"

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

# DLQ: snapshot (live queue name verified via `aws sqs list-queues`: *-jobs-dlq)
put_alarm "dlq-snapshot-messages" \
  "Messages in snapshot DLQ for >30min. Investigation required." \
  "ApproximateNumberOfMessagesVisible" "AWS/SQS" "Maximum" \
  "GreaterThanThreshold" "0" "600" "3" "high" \
  "QueueName=scanipy-${ENV}-snapshot-jobs-dlq"

# DLQ: detector
put_alarm "dlq-detector-messages" \
  "Messages in detector DLQ for >30min. Investigation required." \
  "ApproximateNumberOfMessagesVisible" "AWS/SQS" "Maximum" \
  "GreaterThanThreshold" "0" "600" "3" "high" \
  "QueueName=scanipy-${ENV}-detector-jobs-dlq"

# CLAR-DEPLOY-20: jobs-queue oldest-age backstops — catch the silent-worker-
# death mode (no completions emitted at all) that the rate alarms' IF-guard
# deliberately treats as OK.
put_alarm "snapshot-queue-oldest-age" \
  "Oldest message in the snapshot jobs queue > 15 min — workers stalled or dead (CMP-SNAP-05). CLAR-DEPLOY-20 backstop." \
  "ApproximateAgeOfOldestMessage" "AWS/SQS" "Maximum" \
  "GreaterThanThreshold" "900" "300" "3" "high" \
  "QueueName=scanipy-${ENV}-snapshot-jobs"

put_alarm "detector-queue-oldest-age" \
  "Oldest message in the detector jobs queue > 15 min — workers stalled or dead (CMP-ORCH-03). CLAR-DEPLOY-20 backstop." \
  "ApproximateAgeOfOldestMessage" "AWS/SQS" "Maximum" \
  "GreaterThanThreshold" "900" "300" "3" "high" \
  "QueueName=scanipy-${ENV}-detector-jobs"

# CLAR-DEPLOY-20: companion absence alarms for the run-scoped incident metrics
# (attestor.core_diff_count / eprocess.martingale_test_status must produce
# >= 1 datapoint per day: emit-healthy-value on every run + daily canary
# heartbeat). Gated behind ENABLE_ABSENCE_ALARMS, default false — flipping it
# is an explicit T-STAGE-A-01 go-live checklist item; enabling before the
# emitters + canary heartbeat are live would page permanently.
ENABLE_ABSENCE_ALARMS="${ENABLE_ABSENCE_ALARMS:-false}"
if [[ "${ENABLE_ABSENCE_ALARMS}" == "true" ]]; then
  put_absence_alarm() {
    local name="$1" desc="$2" metric="$3"
    aws cloudwatch put-metric-alarm \
      --alarm-name "scanipy-${ENV}-${name}" \
      --alarm-description "${desc}" \
      --namespace "${NAMESPACE}" \
      --metric-name "${metric}" \
      --statistic SampleCount \
      --comparison-operator LessThanThreshold \
      --threshold 1 \
      --period 86400 \
      --evaluation-periods 1 \
      --alarm-actions "${SNS_ARN}" \
      --ok-actions "${SNS_ARN}" \
      --treat-missing-data breaching \
      --region "${REGION}" \
      --tags Key=Component,Value=CMP-DEPLOY-03 Key=Severity,Value=high Key=Env,Value="${ENV}"
    done_ "Alarm: scanipy-${ENV}-${name}"
  }

  put_absence_alarm "attestor-run-absent" \
    "No attestor.core_diff_count datapoint in 24 h — attestor (CMP-CP-05) or daily canary heartbeat not running. CLAR-DEPLOY-20 absence companion." \
    "attestor.core_diff_count"

  put_absence_alarm "eprocess-gate-absent" \
    "No eprocess.martingale_test_status datapoint in 24 h — Gate 4 / canary heartbeat (CMP-TRI-02) not publishing. CLAR-DEPLOY-20 absence companion." \
    "eprocess.martingale_test_status"
else
  log "Skipping absence alarms (ENABLE_ABSENCE_ALARMS=false — T-STAGE-A-01 go-live item, CLAR-DEPLOY-20)"
fi

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
         ["AWS/SQS","ApproximateNumberOfMessagesVisible","QueueName","scanipy-${ENV}-snapshot-jobs-dlq"],
         ["AWS/SQS","ApproximateNumberOfMessagesVisible","QueueName","scanipy-${ENV}-detector-jobs-dlq"]
       ],"stat":"Maximum","period":600}},
    {"type":"metric","x":0,"y":19,"width":12,"height":6,
     "properties":{"title":"Jobs queue oldest-message age (s) — CLAR-DEPLOY-20 backstop","region":"${REGION}",
       "metrics":[
         ["AWS/SQS","ApproximateAgeOfOldestMessage","QueueName","scanipy-${ENV}-snapshot-jobs"],
         ["AWS/SQS","ApproximateAgeOfOldestMessage","QueueName","scanipy-${ENV}-detector-jobs"]
       ],"stat":"Maximum","period":300}},
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
# The committed infra/otel-collector/config.yaml (awsemf namespace +
# ZeroAndSingleDimensionRollup pin, CLAR-DEPLOY-20) is threaded into the task
# via the AOT_CONFIG_CONTENT environment variable. JSON-escaping the YAML is
# done in python (sed cannot safely inject multi-line content).
log "Registering OTel collector task definition..."
TASK_DEF=$(ACCOUNT_ID="${ACCOUNT_ID}" REGION="${REGION}" ENV_NAME="${ENV}" \
  INFRA_DIR="$(dirname "$0")" python3 - <<'PY'
import json
import os
import pathlib

infra = pathlib.Path(os.environ["INFRA_DIR"])
subs = {
    "<ACCOUNT_ID>": os.environ["ACCOUNT_ID"],
    "<REGION>": os.environ["REGION"],
    "<ENV>": os.environ["ENV_NAME"],
}

config = (infra / "otel-collector" / "config.yaml").read_text()
for placeholder, value in subs.items():
    config = config.replace(placeholder, value)

raw = (infra / "otel-collector" / "task-definition.json").read_text()
for placeholder, value in subs.items():
    raw = raw.replace(placeholder, value)

task_def = json.loads(raw)
for container in task_def["containerDefinitions"]:
    for env in container.get("environment", []):
        if env["name"] == "AOT_CONFIG_CONTENT":
            env["value"] = config

print(json.dumps(task_def))
PY
)
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
ALARMS=(snapshot-worker-failure-rate detector-worker-failure-rate callback-hmac-reject
        attestor-core-diff cw-detect-oracle-disagreement eprocess-martingale-test-failure
        dlq-snapshot-messages dlq-detector-messages
        snapshot-queue-oldest-age detector-queue-oldest-age)
if [[ "${ENABLE_ABSENCE_ALARMS}" == "true" ]]; then
  ALARMS+=(attestor-run-absent eprocess-gate-absent)
fi
for ALARM in "${ALARMS[@]}"; do
  ARN="arn:aws:cloudwatch:${REGION}:${ACCOUNT_ID}:alarm:scanipy-${ENV}-${ALARM}"
  echo "  ${ALARM}: ${ARN}"
done
