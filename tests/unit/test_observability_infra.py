"""Static config-lane assertions for the CMP-DEPLOY-03 observability IaC.

Test id: TST-AC-DEPLOY-03c (config lane, CLAR-DEPLOY-20).

The live-enumeration half of TST-AC-DEPLOY-03c (describe the provisioned
CloudWatch alarm set) stays in ``tests/integration/test_deploy_specs.py`` and
needs AWS credentials. These tests assert the committed IaC itself — the
terraform module, the apply script, the ADOT collector config and task
definition — per the CLAR-DEPLOY-20 implementation contract:

* rate alarms use the completion denominator (``failure_count`` +
  ``success_count``), with ``FILL(fail, 0)`` and
  ``IF(total > 0, 100 * fail0 / total, 0)``, threshold 5, 3-of-3 x 300 s;
* the retired start-time ``job_count`` metric appears nowhere;
* the four new alarms exist (two queue oldest-age backstops, two flag-gated
  absence companions);
* the awsemf exporter pins ``namespace: Scanipy/v3.2`` and
  ``dimension_rollup_option: ZeroAndSingleDimensionRollup`` — the load-bearing
  pin that makes the emitter lane and the ``dimensions = {}`` alarm lane
  compose (d20 risk register: drift here silently starves both rate alarms);
* DLQ alarm dimensions use the live ``*-jobs-dlq`` queue names;
* the collector task definition pins the image by digest and the verified
  IAM roles.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_DIR = _REPO_ROOT / "infra" / "modules" / "observability"
_ALARMS_TF = (_MODULE_DIR / "alarms.tf").read_text()
_VARIABLES_TF = (_MODULE_DIR / "variables.tf").read_text()
_DASHBOARD_TF = (_MODULE_DIR / "dashboard.tf").read_text()
_APPLY_SH = (_REPO_ROOT / "infra" / "observability-apply.sh").read_text()
_OTEL_CONFIG = (_REPO_ROOT / "infra" / "otel-collector" / "config.yaml").read_text()
_TASK_DEF = (_REPO_ROOT / "infra" / "otel-collector" / "task-definition.json").read_text()

_RATE_EXPRESSION = "IF(total > 0, 100 * fail0 / total, 0)"


# --------------------------------------------------------------------------- #
# Rate alarms — CLAR-DEPLOY-20 completion-denominator metric math
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("worker", ["snapshot_worker", "detector_worker"])
def test_rate_alarms_use_completion_denominator(worker: str) -> None:
    """Both rate alarms read failure_count AND success_count (not job_count)."""
    assert f"{worker}.failure_count" in _ALARMS_TF
    assert f"{worker}.success_count" in _ALARMS_TF


def test_rate_alarms_carry_fill_and_if_guard_expressions() -> None:
    """The exact d20 expressions appear once per rate alarm."""
    assert _ALARMS_TF.count('"FILL(fail, 0)"') == 2
    assert _ALARMS_TF.count('"FILL(succ, 0)"') == 2
    assert _ALARMS_TF.count('"fail0 + succ0"') == 2
    assert _ALARMS_TF.count(f'"{_RATE_EXPRESSION}"') == 2


def test_retired_job_count_metric_appears_nowhere() -> None:
    """The start-time job_count denominator is retired (period-skew, d20)."""
    for text in (_ALARMS_TF, _APPLY_SH, _DASHBOARD_TF, _OTEL_CONFIG):
        assert "job_count" not in text


def test_rate_alarms_threshold_and_evaluation_contract() -> None:
    """Threshold 5, 3-of-3 evaluation periods, notBreaching (inviolable per DOC)."""
    assert _ALARMS_TF.count("threshold           = 5\n") == 2
    assert _ALARMS_TF.count("datapoints_to_alarm = 3") == 2
    # Every alarm except the two absence companions treats missing data as
    # notBreaching; the absence companions must breach on missing data.
    assert _ALARMS_TF.count('treat_missing_data        = "breaching"') == 2
    assert _ALARMS_TF.count('treat_missing_data        = "notBreaching"') == 10


def test_apply_script_has_no_threshold_zero_proxy_under_rate_name() -> None:
    """Proxy semantics live NOWHERE under a -failure-rate alarm name."""
    assert "conservative proxy" not in _APPLY_SH
    assert "conservative threshold" not in _APPLY_SH
    # The apply script implements the same metric-math contract as the module.
    assert _APPLY_SH.count(_RATE_EXPRESSION) == 1  # shared helper, two call sites
    assert _APPLY_SH.count('put_rate_alarm "') == 2
    assert "FILL(fail, 0)" in _APPLY_SH
    assert "FILL(succ, 0)" in _APPLY_SH


# --------------------------------------------------------------------------- #
# Four new alarms — queue-age backstops + flag-gated absence companions
# --------------------------------------------------------------------------- #


def test_queue_oldest_age_backstop_alarms_exist() -> None:
    for name in ("snapshot-queue-oldest-age", "detector-queue-oldest-age"):
        assert name in _ALARMS_TF
        assert name in _APPLY_SH
    assert _ALARMS_TF.count('"ApproximateAgeOfOldestMessage"') == 2
    assert _ALARMS_TF.count("threshold           = 900") == 2
    assert "var.snapshot_jobs_queue_name" in _ALARMS_TF
    assert "var.detector_jobs_queue_name" in _ALARMS_TF


def test_absence_companion_alarms_exist_with_samplecount_pattern() -> None:
    for name in ("attestor-run-absent", "eprocess-gate-absent"):
        assert name in _ALARMS_TF
        assert name in _APPLY_SH
    assert _ALARMS_TF.count('statistic           = "SampleCount"') == 2
    assert _ALARMS_TF.count("period              = 86400") == 2
    assert _ALARMS_TF.count('comparison_operator = "LessThanThreshold"') == 2


def test_absence_alarms_gated_behind_flag_defaulting_false() -> None:
    """enable_absence_alarms defaults false; T-STAGE-A-01 flips it (d20)."""
    assert 'variable "enable_absence_alarms"' in _VARIABLES_TF
    var_block = _VARIABLES_TF.split('variable "enable_absence_alarms"')[1]
    assert "default = false" in var_block.split("}")[0]
    assert "T-STAGE-A-01" in _VARIABLES_TF
    assert "CLAR-DEPLOY-20" in _VARIABLES_TF
    assert _ALARMS_TF.count("count = var.enable_absence_alarms ? 1 : 0") == 2
    # Apply-script twin of the flag, also defaulting false.
    assert 'ENABLE_ABSENCE_ALARMS="${ENABLE_ABSENCE_ALARMS:-false}"' in _APPLY_SH


# --------------------------------------------------------------------------- #
# Collector config — the load-bearing awsemf pin (d20 risk mitigation)
# --------------------------------------------------------------------------- #


def test_awsemf_exporter_pins_namespace_and_zero_dim_rollup() -> None:
    assert 'namespace: "Scanipy/v3.2"' in _OTEL_CONFIG
    assert 'dimension_rollup_option: "ZeroAndSingleDimensionRollup"' in _OTEL_CONFIG
    # No metric_declarations allowlist: default all-attribute dims + rollups.
    # (Strip comment lines — the header comment names the block to forbid it.)
    yaml_body = "\n".join(
        line for line in _OTEL_CONFIG.splitlines() if not line.lstrip().startswith("#")
    )
    assert "metric_declarations" not in yaml_body


def test_collector_keeps_xray_traces_pipeline() -> None:
    assert "awsxray" in _OTEL_CONFIG
    assert "traces:" in _OTEL_CONFIG


def test_apply_script_threads_config_via_aot_config_content() -> None:
    assert "AOT_CONFIG_CONTENT" in _TASK_DEF
    assert 'config = (infra / "otel-collector" / "config.yaml").read_text()' in _APPLY_SH


# --------------------------------------------------------------------------- #
# Task definition — digest pin + verified roles
# --------------------------------------------------------------------------- #


def test_task_definition_pins_collector_image_by_digest() -> None:
    assert "aws-otel-collector@sha256:" in _TASK_DEF
    assert ":latest" not in _TASK_DEF


def test_task_definition_uses_verified_iam_roles() -> None:
    assert "role/scanipy-ecs-task-execution" in _TASK_DEF  # existing, verified live
    assert "role/scanipy-otel-collector" in _TASK_DEF  # task role, created by apply
    # The old (non-existent) role name must not resurface.
    assert 'role/scanipy-ecs-execution"' not in _TASK_DEF


# --------------------------------------------------------------------------- #
# DLQ queue names + dashboard interpolation regressions
# --------------------------------------------------------------------------- #


def test_dlq_names_match_live_jobs_dlq_queues() -> None:
    """Live queues (aws sqs list-queues) carry the -jobs-dlq suffix."""
    assert 'default = "scanipy-prod-snapshot-jobs-dlq"' in _VARIABLES_TF
    assert 'default = "scanipy-prod-detector-jobs-dlq"' in _VARIABLES_TF
    for text in (_VARIABLES_TF, _APPLY_SH, _DASHBOARD_TF, _ALARMS_TF):
        assert "scanipy-snapshot-dlq" not in text
        assert "scanipy-detector-dlq" not in text
    assert "snapshot-jobs-dlq" in _APPLY_SH
    assert "detector-jobs-dlq" in _APPLY_SH


def test_dashboard_alarm_widget_uses_resource_arns_not_literal_strings() -> None:
    """Regression: the alarm-summary widget rendered `${data...}` literally."""
    assert '${"$"}{data.aws_caller_identity' not in _DASHBOARD_TF
    assert "aws_cloudwatch_metric_alarm.snapshot_worker_failure_rate.arn" in _DASHBOARD_TF
    assert "aws_cloudwatch_metric_alarm.snapshot_queue_oldest_age.arn" in _DASHBOARD_TF
