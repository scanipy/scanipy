"""Custom-metric emission surface (CMP-DEPLOY-03 §3.4, CLAR-DEPLOY-20 emitter lane).

The single module every Scanipy v3.2 service uses to emit the DOC-CMP-DEPLOY-03
§3.4 custom metrics. Three public functions:

* :func:`record_job_completion` — metrics 1-6 (the per-job worker counters +
  duration histograms for ``snapshot_worker`` / ``detector_worker``).
* :func:`record_counter` — metrics 7-9 (``callback.hmac_reject_count``,
  ``attestor.core_diff_count``, ``cw_detect.oracle_disagreement_count``).
* :func:`record_gauge` — metric 10 (``eprocess.martingale_test_status``, a
  sync Gauge).

Contract anchors (CLAR-DEPLOY-20, ``docs/cross-cutting/DOC-DEPLOY-DECISIONS.md``):

* **Namespace** ``Scanipy/v3.2`` is applied by the ADOT collector's awsemf
  exporter, **never** by emitters — instrument names here are the CloudWatch
  MetricNames verbatim (dots included).
* **Dimensions** are OTel **data-point attributes** (passed per call below);
  resource attributes do NOT become CloudWatch dimensions under awsemf. The
  alarm lane consumes only the zero-dimension rollup the collector produces
  (``dimension_rollup_option: ZeroAndSingleDimensionRollup``).
* **Hermetic-import parity** with ``tools.observability.init``: ``opentelemetry``
  is imported *inside* function bodies only. Importing this module — and calling
  every public function — succeeds with no ``opentelemetry-*`` packages
  installed (a silent no-op), so the hermetic CI slice needs no OTel install and
  a telemetry misconfiguration can never take down a worker's data path.
* Instruments are created once via ``opentelemetry.metrics.get_meter`` with the
  meter name :data:`METER_NAME` and cached in a module-level dict keyed by
  instrument name.

Source-of-truth: ``docs/components/DOC-CMP-DEPLOY-03.md`` §3.4;
``docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`` (CLAR-DEPLOY-20).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Mapping

# The one OTel meter scope for every Scanipy emitter (CLAR-DEPLOY-20 contract).
METER_NAME = "scanipy.observability"

# Module-level instrument cache keyed by instrument name (create-once contract).
# Values are OTel instruments (Counter / Histogram / Gauge); typed ``Any``
# because the OTel API is an optional, lazily-imported dependency.
_instruments: dict[str, Any] = {}

_InstrumentKind = Literal["counter", "histogram", "gauge"]


def _meter() -> Any | None:  # noqa: ANN401 — Meter is an optional, lazily-imported type
    """The scanipy meter, or ``None`` when no ``opentelemetry`` API is installed.

    The import lives here — inside a function body — per the hermetic-import
    contract. When the API is installed but no SDK ``MeterProvider`` was set
    (e.g. ``init_otel`` not called), ``get_meter`` returns the API default
    no-op meter, so emission is still safe.
    """
    try:
        from opentelemetry import metrics
    except ImportError:  # no opentelemetry-* installed: the hermetic no-op path
        return None
    return metrics.get_meter(METER_NAME)


def _instrument(name: str, kind: _InstrumentKind, unit: str) -> Any | None:  # noqa: ANN401 — OTel
    """Return the cached instrument ``name``, creating it once if needed.

    Returns ``None`` (caller no-ops) when OTel is absent, or — for gauges —
    when the installed ``opentelemetry-api`` predates the sync Gauge
    (``Meter.create_gauge``).
    """
    inst = _instruments.get(name)
    if inst is not None:
        return inst
    meter = _meter()
    if meter is None:
        return None
    if kind == "counter":
        inst = meter.create_counter(name, unit=unit)
    elif kind == "histogram":
        inst = meter.create_histogram(name, unit=unit)
    else:
        create_gauge = getattr(meter, "create_gauge", None)
        if create_gauge is None:  # opentelemetry-api < 1.23: no sync Gauge
            return None
        inst = create_gauge(name, unit=unit)
    _instruments[name] = inst
    return inst


def _reset_for_tests() -> None:
    """Clear the instrument cache (test seam only — never called in production).

    The cache pins instruments to the meter that created them; a test that
    swaps the (fake) meter must clear it so instruments re-bind.
    """
    _instruments.clear()


def record_job_completion(
    worker: Literal["snapshot_worker", "detector_worker"],
    outcome: Literal["success", "failure"],
    duration_ms: float,
    *,
    counter_attributes: Mapping[str, str],
    duration_attributes: Mapping[str, str],
) -> None:
    """Record one worker-job completion (DOC §3.4 metrics 1-6, CLAR-DEPLOY-20).

    Increments Counter ``f"{worker}.{outcome}_count"`` (unit ``"1"``) with
    ``counter_attributes`` and records Histogram ``f"{worker}.duration_ms"``
    (unit ``"ms"``) with ``duration_attributes``. Exactly one call per
    dequeued message / detector job (retries count per-attempt, intentionally —
    CLAR-DEPLOY-20): the failure-rate alarm denominator is *completions*
    (``success_count + failure_count``), never job starts.

    Attribute contracts (CloudWatch dimensions via the collector rollup):

    * ``snapshot_worker``: counters ``{region, env_digest}``, duration
      ``{precondition_status}`` (CMP-SNAP-05).
    * ``detector_worker``: counters ``{detector_id, engine, env_digest}``,
      duration ``{detector_id, engine}`` (CMP-ORCH-03).
    """
    counter = _instrument(f"{worker}.{outcome}_count", "counter", "1")
    if counter is not None:
        counter.add(1, attributes=dict(counter_attributes))
    histogram = _instrument(f"{worker}.duration_ms", "histogram", "ms")
    if histogram is not None:
        histogram.record(duration_ms, attributes=dict(duration_attributes))


def record_counter(
    name: str, value: int = 1, *, attributes: Mapping[str, str] | None = None
) -> None:
    """Add ``value`` to Counter ``name`` (unit ``"1"``) — DOC §3.4 metrics 7-9.

    ``value=0`` is a legitimate call and produces a real datapoint: the
    CLAR-DEPLOY-20 amended semantics for ``attestor.core_diff_count`` emit
    ``add(0)`` on every clean attestation run so the ``SampleCount``-absence
    alarm can distinguish "attestor never ran" from "ran clean".
    """
    counter = _instrument(name, "counter", "1")
    if counter is not None:
        counter.add(value, attributes=dict(attributes) if attributes is not None else None)


def record_gauge(name: str, value: int, *, attributes: Mapping[str, str] | None = None) -> None:
    """Set sync Gauge ``name`` (unit ``"1"``) to ``value`` — DOC §3.4 metric 10.

    Used for ``eprocess.martingale_test_status`` (0/1): published on every CI
    Gate-4 run and once daily by the canary heartbeat (CLAR-DEPLOY-20 cadence).
    """
    gauge = _instrument(name, "gauge", "1")
    if gauge is not None:
        gauge.set(value, attributes=dict(attributes) if attributes is not None else None)


__all__ = [
    "METER_NAME",
    "record_counter",
    "record_gauge",
    "record_job_completion",
]
