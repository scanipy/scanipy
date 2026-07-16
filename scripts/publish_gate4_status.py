#!/usr/bin/env python3
"""Publish ``eprocess.martingale_test_status`` (CMP-DEPLOY-03 §3.4 metric 10).

The CLAR-DEPLOY-20 Gate-4 status hook: a 0/1 gauge published on **every CI
Gate-4 run** (``ci.yml`` job ``eprocess-unit``) and **once daily** by the canary
heartbeat (``canary.yml``, cron ``30 3 * * *``), so the metric has ≥1 datapoint
per day and its ``SampleCount < 1`` absence alarm (enabled at Stage-A go-live)
is never fail-open. The healthy value (1 = martingale tests green) is emitted
explicitly — for incident-grade run-scoped metrics, absence is ambiguous
("no incident" vs "gate never ran"), so every run publishes.

The caller (the workflow step) derives ``--status`` from the pytest exit code of
``tests/falsifier/eprocess/``; this script only publishes. Publishing is
non-gating: the Gate-4 verdict is enforced by pytest in the workflow, never by
this hook.

Publish lanes (both attempted, in order):

1. **OTel** — :func:`tools.observability.metrics.record_gauge`. Meaningful only
   where a ``MeterProvider`` + ADOT collector exist (an ECS task after
   ``init_otel``); a silent hermetic no-op elsewhere (CI runners, dev boxes).
2. **Direct CloudWatch** — ``aws cloudwatch put-metric-data`` into namespace
   ``Scanipy/v3.2``, only when ``SCANIPY_METRICS_CW_DIRECT=1``. This is the CI
   heartbeat lane (GitHub Actions has no OTel collector), mirroring the §3.4
   metric-12 ``cosign.signature_verify_count`` put-metric-data precedent. It
   requires AWS credentials in the environment; a failed put exits non-zero so
   the workflow log shows the missed heartbeat (the step itself stays
   non-gating).

Exit code: 0 on success (including the everything-was-a-no-op path); 1 when the
explicitly-requested CloudWatch direct put failed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

# Runnable both as ``python scripts/publish_gate4_status.py`` from a bare
# checkout (sys.path[0] is scripts/) and from an installed environment.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

METRIC_NAME = "eprocess.martingale_test_status"
# The CloudWatch namespace normally applied by the ADOT collector's awsemf
# exporter (CLAR-DEPLOY-20). The direct put-metric-data lane bypasses the
# collector, so it must pin the namespace itself — same value, verbatim.
NAMESPACE = "Scanipy/v3.2"


def publish(
    status: int,
    *,
    environ: Mapping[str, str] | None = None,
    runner: object = None,
) -> dict[str, object]:
    """Publish ``status`` (0|1) on both lanes; return a report dict.

    ``environ`` / ``runner`` are injectable for hermetic tests (defaults:
    :data:`os.environ` / :func:`subprocess.run`).
    """
    import os

    if status not in (0, 1):
        raise ValueError(f"status must be 0 or 1 (DOC §3.4 metric 10 gauge); got {status!r}")
    env = os.environ if environ is None else environ
    run = subprocess.run if runner is None else runner

    # Lane 1 — the OTel emitter surface (hermetic no-op without an SDK/collector).
    from tools.observability.metrics import record_gauge

    record_gauge(METRIC_NAME, status)
    report: dict[str, object] = {"metric": METRIC_NAME, "value": status, "otel": "attempted"}

    # Lane 2 — direct CloudWatch (the CI heartbeat lane), opt-in via env var.
    if env.get("SCANIPY_METRICS_CW_DIRECT") == "1":
        aws = shutil.which("aws")
        if aws is None:
            report["cloudwatch_exit"] = 127
            report["cloudwatch_error"] = "aws CLI not found on PATH"
        else:
            proc = run(  # type: ignore[operator]  # injectable runner port
                [
                    aws,
                    "cloudwatch",
                    "put-metric-data",
                    "--namespace",
                    NAMESPACE,
                    "--metric-name",
                    METRIC_NAME,
                    "--value",
                    str(status),
                    "--unit",
                    "None",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            report["cloudwatch_exit"] = proc.returncode
            if proc.returncode != 0:
                report["cloudwatch_error"] = proc.stderr.strip()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--status",
        type=int,
        choices=(0, 1),
        required=True,
        help="Gate-4 verdict: 1 = e-process martingale tests green, 0 = failing.",
    )
    args = parser.parse_args(argv)
    report = publish(args.status)
    print(json.dumps(report, sort_keys=True))
    exit_code = report.get("cloudwatch_exit", 0)
    return 0 if exit_code == 0 else 1


if __name__ == "__main__":  # pragma: no cover — exercised as a CLI by workflows.
    sys.exit(main())
