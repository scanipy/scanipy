"""DEPLOY-03 structured-logging unit specs — TST-AC-DEPLOY-03b (hermetic slice).

Hermetic, Python-testable slice of CMP-DEPLOY-03 (observability surfaces). These
specs exercise the structured-JSON logging surface and the INV-2 fail-closed gate
WITHOUT any OpenTelemetry SDK, AWS CloudWatch, or X-Ray — no network, no AWS.

Covers:
  * AC-DEPLOY-03b — every emitted log line carries ``service`` (name),
    ``build_commit`` and ``env_digest`` (``ScanipyJsonFormatter``).
  * INV-2 fail-closed support — ``init_otel`` refuses to start when
    ``SCANIPY_ENV_DIGEST`` is empty (DOC-CMP-DEPLOY-03 §"INV-2 cross-trace
    audit", §6.1 step 3a).

DEFERRED (NOT covered here — require real AWS X-Ray / CloudWatch + Terraform):
  * AC-DEPLOY-03a — cross-component X-Ray trace keyed on scan id.
  * AC-DEPLOY-03c — provisioned CloudWatch alarm set.
Their integration stubs stay skipped in tests/integration/test_deploy_specs.py.

Source-of-truth: WBS.md §2.4 (verbatim ACs); DOC-CMP-DEPLOY-03.md §3.1, §3.3, §5;
.claude/rules/02-provenance.md (INV-2).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

import pytest

from tools.observability import init_otel
from tools.observability.logging import (
    MANDATORY_FIELDS,
    ScanipyJsonFormatter,
    get_logger,
)


def _format_record(formatter: ScanipyJsonFormatter, msg: str = "hello") -> dict[str, object]:
    """Format one INFO record through ``formatter`` and parse the JSON line."""
    record = logging.LogRecord(
        name="scanipy.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    parsed: dict[str, object] = json.loads(formatter.format(record))
    return parsed


@pytest.fixture
def _otel_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Set the AC-DEPLOY-03b env-var contract to representative non-empty values."""
    monkeypatch.setenv("OTEL_SERVICE_NAME", "snapshot-worker")
    monkeypatch.setenv("SCANIPY_WORKER_VERSION", "deadbeefcafef00d")
    monkeypatch.setenv("SCANIPY_ENV_DIGEST", "sha256:" + "a" * 64)
    yield


@pytest.mark.unit
def test_deploy_03b_formatter_emits_three_mandatory_fields(_otel_env: None) -> None:
    """A formatted log line carries non-empty ``service``, ``build_commit``, ``env_digest``.

    Test id: TST-AC-DEPLOY-03b (hermetic unit slice)
    Maps to AC: AC-DEPLOY-03b — Every emitted log line carries a service name,
        build commit, and ``env_digest``.
    Kind tag: [UNIT]
    Pass criteria: the parsed JSON line contains ``service``, ``build_commit`` and
        ``env_digest`` keys, each present and non-empty.
    Hard gate?: yes — INV-2 (substrate-level env_digest reflection).
    """
    payload = _format_record(ScanipyJsonFormatter())

    for field in MANDATORY_FIELDS:
        assert field in payload, f"mandatory field {field!r} missing from log line"
        assert payload[field], f"mandatory field {field!r} must be non-empty"

    assert payload["service"] == "snapshot-worker"
    assert payload["build_commit"] == "deadbeefcafef00d"
    assert payload["env_digest"] == "sha256:" + "a" * 64
    assert payload["msg"] == "hello"
    assert payload["level"] == "INFO"


@pytest.mark.unit
def test_deploy_03b_get_logger_line_carries_mandatory_fields(
    _otel_env: None, capsys: pytest.CaptureFixture[str]
) -> None:
    """A line emitted via ``get_logger`` is structured JSON with the three fields.

    Exercises the wired handler path (formatter attached by ``get_logger``), not
    just the formatter in isolation, and asserts the handler is not stacked on a
    repeat call (the line is emitted exactly once).
    """
    logger = get_logger("scanipy.deploy03.smoke")
    # Idempotent: a second call must not add a second StreamHandler.
    logger = get_logger("scanipy.deploy03.smoke")
    stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
    assert len(stream_handlers) == 1

    logger.propagate = False
    logger.info("scan started")

    err = capsys.readouterr().err.strip()
    assert err, "expected one structured log line on stderr"
    lines = err.splitlines()
    assert len(lines) == 1, "log line must be emitted exactly once (no stacked handlers)"

    payload = json.loads(lines[0])
    for field in MANDATORY_FIELDS:
        assert payload[field], f"mandatory field {field!r} must be present and non-empty"


@pytest.mark.unit
@pytest.mark.invariant
def test_deploy_03b_init_otel_refuses_empty_env_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    """``init_otel`` fails closed when ``SCANIPY_ENV_DIGEST`` is unset (INV-2).

    Test id: TST-INV-2 support for CMP-DEPLOY-03
    Maps to: DOC-CMP-DEPLOY-03 §"INV-2 cross-trace audit", §6.1 step 3a — init
        refuses to start telemetry against an unpinned ``Env``.
    Pass criteria: ``init_otel`` raises ``RuntimeError`` (not a silent default)
        when ``SCANIPY_ENV_DIGEST`` is missing, and the gate is reached BEFORE any
        OpenTelemetry import (so it holds even with the SDK not installed).
    Hard gate?: yes — INV-2 fail-closed.
    """
    monkeypatch.delenv("SCANIPY_ENV_DIGEST", raising=False)
    with pytest.raises(RuntimeError, match="SCANIPY_ENV_DIGEST"):
        init_otel("snapshot-worker")


@pytest.mark.unit
@pytest.mark.invariant
def test_deploy_03b_init_otel_refuses_blank_env_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty-string ``SCANIPY_ENV_DIGEST`` is treated as unset (INV-2)."""
    monkeypatch.setenv("SCANIPY_ENV_DIGEST", "")
    with pytest.raises(RuntimeError, match="INV-2"):
        init_otel("snapshot-worker")
