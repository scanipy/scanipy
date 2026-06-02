"""OpenTelemetry SDK bootstrap (CMP-DEPLOY-03).

:func:`init_otel` is the observability initialisation surface every Scanipy v3.2
service calls at process start (DOC-CMP-DEPLOY-03 §3.1, §6.1). It fails closed if
``SCANIPY_ENV_DIGEST`` is empty (INV-2 anchor, DOC §"INV-2 cross-trace audit"):
without the env digest there is no verifiable ``Env`` to stamp on spans/logs, so
the process must exit before serving traffic rather than emit unanchored telemetry.

The fail-closed env-digest gate is evaluated **first**, and the OpenTelemetry SDK
is imported **inside** the function body **after** that gate. This is deliberate:
``import tools.observability.init`` and the "refuses when ``SCANIPY_ENV_DIGEST``
unset" behaviour are both exercisable with no ``opentelemetry-*`` packages
installed and with no AWS CloudWatch / X-Ray calls (the hermetic AC-DEPLOY-03b
slice). The heavy SDK + exporter wiring is reached only on the success path, when
a real ``env_digest`` is present and the collector sidecar is configured.

Source-of-truth: ``docs/components/DOC-CMP-DEPLOY-03.md`` §3.1, §6.1;
``docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`` (CLAR-DEPLOY-07).
"""

from __future__ import annotations

import os


def init_otel(service_name: str) -> None:
    """Initialise OpenTelemetry for a Scanipy v3.2 service.

    Reads from the env-var contract:

    * ``SCANIPY_ENV_DIGEST``        -> ``env_digest`` resource attribute (INV-2 anchor)
    * ``SCANIPY_WORKER_VERSION``    -> ``SERVICE_VERSION`` resource attribute / ``build_commit``
    * ``OTEL_SERVICE_NAME``         -> overrides the ``service_name`` argument if set
    * ``OTEL_EXPORTER_OTLP_ENDPOINT`` -> OTel collector sidecar endpoint (in-VPC ECS service)
    * ``AWS_REGION``                -> ``cloud.region`` resource attribute

    The OTel collector (a sidecar ECS service per CLAR-DEPLOY-07) forwards to
    CloudWatch Logs (structured JSON), CloudWatch Metrics (namespace
    ``Scanipy/v3.2``), and AWS X-Ray (traces).

    Raises:
        RuntimeError: if ``SCANIPY_ENV_DIGEST`` is empty/unset. INV-2 fail-closed:
            the process must not start telemetry against an unpinned ``Env``.
    """
    # INV-2 fail-closed gate — evaluated BEFORE any OTel SDK import so the gate is
    # testable without the opentelemetry packages installed (DOC §6.1 step 3a).
    env_digest = os.environ.get("SCANIPY_ENV_DIGEST", "")
    if not env_digest:
        raise RuntimeError("INV-2: SCANIPY_ENV_DIGEST must be set before OTel init")

    # Heavy SDK + AWS exporter wiring is imported only on the success path. Kept
    # inside the function so module import stays dependency-free for the hermetic
    # AC-DEPLOY-03b slice.
    from opentelemetry import metrics, trace
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
    from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create(
        {
            SERVICE_NAME: os.environ.get("OTEL_SERVICE_NAME", service_name),
            SERVICE_VERSION: os.environ.get("SCANIPY_WORKER_VERSION", "unknown"),
            "env_digest": env_digest,
            "deployment.environment": os.environ.get("SCANIPY_ENV", "prod"),
            "cloud.region": os.environ.get("AWS_REGION", "us-east-1"),
        }
    )

    # Tracer -> X-Ray (via the OTel collector sidecar).
    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(trace_provider)

    # Metrics -> CloudWatch Metrics (namespace Scanipy/v3.2, via the collector).
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter())],
    )
    metrics.set_meter_provider(meter_provider)

    # Auto-instrumentation for AWS SDK, HTTP, and Postgres.
    BotocoreInstrumentor().instrument()
    RequestsInstrumentor().instrument()
    Psycopg2Instrumentor().instrument()
