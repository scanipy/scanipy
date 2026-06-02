"""Observability surface for Scanipy v3.2 (CMP-DEPLOY-03).

Two public surfaces:

* :mod:`tools.observability.logging` — :class:`ScanipyJsonFormatter` and
  :func:`get_logger`, the structured-JSON logging surface that enforces the
  mandatory log fields (``service``, ``build_commit``, ``env_digest``) required
  by ``AC-DEPLOY-03b``.
* :mod:`tools.observability.init` — :func:`init_otel`, the OpenTelemetry SDK
  bootstrap that fails closed if ``SCANIPY_ENV_DIGEST`` is empty (INV-2 anchor,
  DOC-CMP-DEPLOY-03 §"INV-2 cross-trace audit").

The OpenTelemetry SDK is imported lazily (inside :func:`init_otel`) so that the
logging surface and the env-digest fail-closed gate are importable and unit
testable without the ``opentelemetry-*`` packages installed and without any AWS
CloudWatch / X-Ray calls.

Source-of-truth: ``docs/components/DOC-CMP-DEPLOY-03.md`` §3.
"""

from tools.observability.logging import ScanipyJsonFormatter, get_logger

__all__ = ["ScanipyJsonFormatter", "get_logger", "init_otel"]


def __getattr__(name: str) -> object:
    # Lazy re-export of ``init_otel`` so that importing this package does not
    # transitively import the OpenTelemetry SDK (it is imported only when
    # ``init_otel`` is actually called). Keeps the hermetic slice dependency-free.
    if name == "init_otel":
        from tools.observability.init import init_otel

        return init_otel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
