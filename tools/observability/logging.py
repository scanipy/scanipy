"""Structured-JSON logging surface (CMP-DEPLOY-03, AC-DEPLOY-03b).

:class:`ScanipyJsonFormatter` is the mandatory-field enforcer: every emitted log
line carries ``service`` (name), ``build_commit``, and ``env_digest`` — the three
fields AC-DEPLOY-03b requires on every line (INV-2; ``.claude/rules/02-provenance.md``).

The formatter is a *presence enforcer*, not a value validator: it reads the three
mandatory fields from the process env-var contract (set once at image build /
ECS task start) and always emits them. It never raises — per DOC-CMP-DEPLOY-03 §7
a formatter error must fall back rather than crash the service. The fail-closed
gate on an empty ``SCANIPY_ENV_DIGEST`` lives in :func:`tools.observability.init.init_otel`,
not here.

The OpenTelemetry SDK is imported lazily/guarded so this module is importable and
unit testable with no ``opentelemetry-*`` packages installed (no AWS calls). When
OTel is absent, ``trace_id`` / ``span_id`` degrade to ``None`` (logs are simply not
trace-correlated); the three AC-DEPLOY-03b fields come from env vars and are
unaffected.

Source-of-truth: ``docs/components/DOC-CMP-DEPLOY-03.md`` §3.3;
``.claude/commands/sre-agent.md`` (canonical mandatory-field list).
"""

from __future__ import annotations

import json
import logging
import os
import time
from types import ModuleType
from typing import Any

# OTel is imported guarded so this module is importable with no
# ``opentelemetry-*`` packages installed (the hermetic AC-DEPLOY-03b slice).
# Typed as ``ModuleType | None`` so the value is consistent whether or not the
# SDK is present (no per-environment ``type: ignore`` churn under strict mypy).
_otel_trace: ModuleType | None
try:  # pragma: no cover - exercised by env, not branch-meaningful for the slice
    from opentelemetry import trace as _otel_trace_mod

    _otel_trace = _otel_trace_mod
except ImportError:  # OTel SDK not installed (e.g. the hermetic unit slice).
    _otel_trace = None

# The three AC-DEPLOY-03b mandatory fields, plus the surrounding structured
# envelope. Optional correlation fields are emitted with an explicit ``null`` so
# every log line has a stable schema (DOC §3.3).
MANDATORY_FIELDS = ("service", "build_commit", "env_digest")

_OPTIONAL_CONTEXT_FIELDS = (
    "scan_id",
    "org_id",
    "codebase_id",
    "snapshot_id",
    "detector_id",
    "S_version",
    "origin",
    "fingerprint_class",
)


class ScanipyJsonFormatter(logging.Formatter):
    """Render a :class:`logging.LogRecord` as a single structured-JSON line.

    Every line carries the AC-DEPLOY-03b mandatory fields ``service``,
    ``build_commit`` and ``env_digest`` (sourced from the env-var contract), the
    log envelope (``level``, ``ts``, ``msg``), the current OTel trace/span ids
    (``None`` when OTel is absent), and the optional per-scan correlation fields
    (emitted as ``null`` when the caller did not supply them via ``extra=``).
    """

    def format(self, record: logging.LogRecord) -> str:
        # Pull the current span context (set by OTel) so logs and traces
        # correlate. Degrades to ``None`` when the OTel SDK is not installed.
        ctx = None
        if _otel_trace is not None:
            span = _otel_trace.get_current_span()
            ctx = span.get_span_context() if span is not None else None

        payload: dict[str, Any] = {
            "service": os.environ.get("OTEL_SERVICE_NAME", record.name),
            "build_commit": os.environ.get("SCANIPY_WORKER_VERSION", "unknown"),
            "env_digest": os.environ.get("SCANIPY_ENV_DIGEST", ""),
            "level": record.levelname,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(record.created)),
            "msg": record.getMessage(),
            # Emit ids only for a *valid* span context. An OTel-installed worker
            # with no active span yields an invalid context whose trace/span ids
            # are 0 — emitting "000…0" would falsely imply a real trace, so emit
            # explicit null instead (DOC-CMP-DEPLOY-03 §3.3).
            "trace_id": f"{ctx.trace_id:032x}" if ctx is not None and ctx.is_valid else None,
            "span_id": f"{ctx.span_id:016x}" if ctx is not None and ctx.is_valid else None,
        }
        # Caller-supplied structured fields (the ``extra=`` kwarg lands as
        # attributes on the record). Absent fields are emitted as explicit null.
        for key in _OPTIONAL_CONTEXT_FIELDS:
            payload[key] = getattr(record, key, None)
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    """Return a logger wired to a single :class:`ScanipyJsonFormatter` handler.

    Idempotent: repeated calls for the same ``name`` do not stack handlers, so a
    log line is emitted exactly once in the structured-JSON envelope.
    """
    logger = logging.getLogger(name)
    # Idempotent on *our* handler specifically — match a handler carrying the
    # ScanipyJsonFormatter, not any StreamHandler (a foreign handler must not
    # suppress installing ours).
    if not any(isinstance(h.formatter, ScanipyJsonFormatter) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(ScanipyJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    # Do not propagate to the root logger (whose handlers lack the JSON
    # formatter) — the structured line must be emitted exactly once.
    logger.propagate = False
    return logger
