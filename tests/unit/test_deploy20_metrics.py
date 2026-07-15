"""CMP-DEPLOY-03 custom-metric emitter specs — CLAR-DEPLOY-20 (hermetic).

Two parts, both hermetic (no AWS, no CloudWatch, no OTel Collector, no
``opentelemetry-*`` install required — the ``dev`` extra never lists it, so
this is the TRUE no-op path CI actually runs under):

  Part A — ``tools.observability.metrics`` itself: the create-once instrument
    cache, the verbatim CloudWatch MetricName / unit / attribute contract
    (CLAR-DEPLOY-20 implementation_contract), and the two safe-degradation
    paths (no OTel installed at all; an installed API predating the sync
    Gauge). A minimal in-test ``opentelemetry.metrics`` double is injected via
    ``sys.modules`` so the module's REAL ``from opentelemetry import metrics``
    import statement (inside ``_meter``) executes — this is the closest
    hermetic analogue available here to the DOC's suggested
    ``InMemoryMetricReader`` check (that reader needs ``opentelemetry-sdk``
    installed; this repo's ``dev`` extra deliberately never installs it, so a
    module double at the same import boundary is the correct substitute, not a
    weaker one — it exercises the identical code path).

  Part B — the six emission-point call sites CLAR-DEPLOY-20 wires (CMP-SNAP-05,
    CMP-ORCH-03, CMP-ORCH-01, CMP-CP-05, CMP-SNAP-04, TRI-02 CLI publisher).
    Each producer module imports ``record_job_completion`` / ``record_counter``
    / ``record_gauge`` by name at module scope, so a spy monkeypatched onto
    that SAME module-level name intercepts every call the production code
    makes without touching ``tools.observability.metrics`` at all — this is a
    pure wiring check (call count, args, attribute contract), reusing the
    EXISTING hermetic DI fakes each owning component's own spec file already
    established (``tests/orch01_fakes.py``, ``tests/orch03_fakes.py``,
    ``tests/cp05_fakes.py``, ``tests/snap04_fakes.py`` collaborators via
    ``services.snapshot``), never inventing new production doubles.

Source-of-truth: ``docs/cross-cutting/DOC-DEPLOY-DECISIONS.md`` (CLAR-DEPLOY-20
``implementation_contract``); ``docs/components/DOC-CMP-DEPLOY-03.md`` §3.4.
"""

from __future__ import annotations

import importlib.util
import sys
import types
import uuid
from collections.abc import Iterator
from typing import Any
from uuid import UUID

import pytest

from services.scan.attestor import AttestationVerdict, attest_scan
from services.scan.worker import InvariantViolation, run_detector
from services.snapshot import InMemoryOracleRunStore, record_oracle_run
from tests.cp05_fakes import SeededNondeterministicScanRunner, make_runner
from tests.orch01_fakes import FakeHmacKeyIssuer, done_report, sign_callback
from tests.orch03_fakes import (
    core_injection_detector,
    deterministic_slice_fingerprinter,
    good_job,
    injection_taint_cpg,
    out_of_set_engine_detector,
)
from tools.observability.metrics import (
    METER_NAME,
    record_counter,
    record_gauge,
    record_job_completion,
)

# ---------------------------------------------------------------------------
# Part A — tools.observability.metrics fixtures + contract tests
# ---------------------------------------------------------------------------


class _FakeInstrument:
    """A calls-recording double for an OTel Counter / Histogram / Gauge."""

    def __init__(self, name: str, unit: str) -> None:
        self.name = name
        self.unit = unit
        self.calls: list[tuple[str, object, dict[str, str] | None]] = []

    def add(self, value: object, attributes: dict[str, str] | None = None) -> None:
        self.calls.append(("add", value, dict(attributes) if attributes else None))

    def record(self, value: object, attributes: dict[str, str] | None = None) -> None:
        self.calls.append(("record", value, dict(attributes) if attributes else None))

    def set(self, value: object, attributes: dict[str, str] | None = None) -> None:
        self.calls.append(("set", value, dict(attributes) if attributes else None))


class _FakeMeterNoGauge:
    """A Meter double WITHOUT ``create_gauge`` (opentelemetry-api < 1.23)."""

    def __init__(self) -> None:
        self.created: list[tuple[str, str, str]] = []
        self.instruments: dict[str, _FakeInstrument] = {}

    def _create(self, kind: str, name: str, unit: str) -> _FakeInstrument:
        self.created.append((kind, name, unit))
        inst = _FakeInstrument(name, unit)
        self.instruments[name] = inst
        return inst

    def create_counter(self, name: str, unit: str = "") -> _FakeInstrument:
        return self._create("counter", name, unit)

    def create_histogram(self, name: str, unit: str = "") -> _FakeInstrument:
        return self._create("histogram", name, unit)


class _FakeMeter(_FakeMeterNoGauge):
    """The full Meter double: adds the sync Gauge (opentelemetry-api >= 1.23)."""

    def create_gauge(self, name: str, unit: str = "") -> _FakeInstrument:
        return self._create("gauge", name, unit)


def _install_fake_otel(monkeypatch: pytest.MonkeyPatch, meter: _FakeMeterNoGauge) -> list[str]:
    """Inject a fake ``opentelemetry.metrics`` module so ``_meter()``'s real
    ``from opentelemetry import metrics`` import succeeds against ``meter``.
    Returns the list that records every ``get_meter(name)`` call (verifies the
    METER_NAME contract). Resets the metrics module's create-once instrument
    cache so the fake meter starts clean.
    """
    from tools.observability import metrics as metrics_mod

    captured_names: list[str] = []

    def get_meter(name: str) -> _FakeMeterNoGauge:
        captured_names.append(name)
        return meter

    fake_metrics_module = types.SimpleNamespace(get_meter=get_meter)
    fake_otel_pkg = types.ModuleType("opentelemetry")
    fake_otel_pkg.metrics = fake_metrics_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "opentelemetry", fake_otel_pkg)
    monkeypatch.setitem(sys.modules, "opentelemetry.metrics", fake_metrics_module)

    metrics_mod._reset_for_tests()
    return captured_names


@pytest.fixture
def fake_meter(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[_FakeMeter, list[str]]]:
    """A full fake Meter (counter/histogram/gauge) installed at the import seam."""
    from tools.observability import metrics as metrics_mod

    meter = _FakeMeter()
    captured_names = _install_fake_otel(monkeypatch, meter)
    yield meter, captured_names
    metrics_mod._reset_for_tests()


@pytest.fixture
def fake_meter_no_gauge(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[_FakeMeterNoGauge, list[str]]]:
    """A fake Meter lacking ``create_gauge`` (pre-1.23 opentelemetry-api)."""
    from tools.observability import metrics as metrics_mod

    meter = _FakeMeterNoGauge()
    captured_names = _install_fake_otel(monkeypatch, meter)
    yield meter, captured_names
    metrics_mod._reset_for_tests()


@pytest.mark.unit
def test_metrics_meter_scope_is_verbatim_scanipy_observability(
    fake_meter: tuple[_FakeMeter, list[str]],
) -> None:
    """``get_meter`` is called with the pinned CLAR-DEPLOY-20 meter name."""
    _meter, captured_names = fake_meter
    record_counter("callback.hmac_reject_count", attributes={"endpoint": "/x"})
    assert METER_NAME == "scanipy.observability"
    assert captured_names == [METER_NAME]


@pytest.mark.unit
def test_record_job_completion_success_emits_verbatim_counter_and_histogram(
    fake_meter: tuple[_FakeMeter, list[str]],
) -> None:
    """Metrics 4-6 (detector_worker): verbatim CloudWatch MetricName/unit/attrs."""
    meter, _ = fake_meter
    env_digest = "sha256:" + "a" * 64
    record_job_completion(
        "detector_worker",
        "success",
        42.5,
        counter_attributes={
            "detector_id": "java-py-injection",
            "engine": "ifds",
            "env_digest": env_digest,
        },
        duration_attributes={"detector_id": "java-py-injection", "engine": "ifds"},
    )
    assert ("counter", "detector_worker.success_count", "1") in meter.created
    assert ("histogram", "detector_worker.duration_ms", "ms") in meter.created
    assert meter.instruments["detector_worker.success_count"].calls == [
        (
            "add",
            1,
            {"detector_id": "java-py-injection", "engine": "ifds", "env_digest": env_digest},
        )
    ]
    assert meter.instruments["detector_worker.duration_ms"].calls == [
        ("record", 42.5, {"detector_id": "java-py-injection", "engine": "ifds"})
    ]


@pytest.mark.unit
def test_record_job_completion_failure_emits_verbatim_failure_counter(
    fake_meter: tuple[_FakeMeter, list[str]],
) -> None:
    """Metrics 1-3 (snapshot_worker): the failure leg + duration histogram."""
    meter, _ = fake_meter
    record_job_completion(
        "snapshot_worker",
        "failure",
        10.0,
        counter_attributes={"region": "us-east-1", "env_digest": "sha256:" + "b" * 64},
        duration_attributes={"precondition_status": "degraded"},
    )
    assert ("counter", "snapshot_worker.failure_count", "1") in meter.created
    assert meter.instruments["snapshot_worker.failure_count"].calls[0][0] == "add"
    assert meter.instruments["snapshot_worker.duration_ms"].calls == [
        ("record", 10.0, {"precondition_status": "degraded"})
    ]


@pytest.mark.unit
def test_record_counter_default_value_is_one(fake_meter: tuple[_FakeMeter, list[str]]) -> None:
    """Metric 7 (``callback.hmac_reject_count``): default ``value=1``."""
    meter, _ = fake_meter
    record_counter(
        "callback.hmac_reject_count", attributes={"endpoint": "/api/v1/jobs/{job_id}/status"}
    )
    assert meter.instruments["callback.hmac_reject_count"].calls == [
        ("add", 1, {"endpoint": "/api/v1/jobs/{job_id}/status"})
    ]


@pytest.mark.unit
def test_record_counter_zero_is_a_real_datapoint(
    fake_meter: tuple[_FakeMeter, list[str]],
) -> None:
    """CLAR-DEPLOY-20 amended semantics: ``add(0)`` on a clean attestor run is a
    REAL datapoint, not a skipped call — the ``SampleCount``-absence alarm
    needs it to distinguish "never ran" from "ran clean"."""
    meter, _ = fake_meter
    record_counter("attestor.core_diff_count", value=0)
    assert meter.instruments["attestor.core_diff_count"].calls == [("add", 0, None)]


@pytest.mark.unit
def test_record_counter_no_attributes_passes_none(
    fake_meter: tuple[_FakeMeter, list[str]],
) -> None:
    meter, _ = fake_meter
    record_counter("attestor.core_diff_count", value=1)
    assert meter.instruments["attestor.core_diff_count"].calls == [("add", 1, None)]


@pytest.mark.unit
def test_record_gauge_sets_value_unit_one(fake_meter: tuple[_FakeMeter, list[str]]) -> None:
    """Metric 10 (``eprocess.martingale_test_status``): a sync Gauge, unit ``"1"``."""
    meter, _ = fake_meter
    record_gauge("eprocess.martingale_test_status", 1)
    assert ("gauge", "eprocess.martingale_test_status", "1") in meter.created
    assert meter.instruments["eprocess.martingale_test_status"].calls == [("set", 1, None)]


@pytest.mark.unit
def test_record_gauge_is_a_noop_when_meter_lacks_create_gauge(
    fake_meter_no_gauge: tuple[_FakeMeterNoGauge, list[str]],
) -> None:
    """A pre-1.23 opentelemetry-api meter (no sync Gauge) degrades silently —
    no crash, no instrument created (INV: the emitter can never take down the
    Gate-4 CLI or a worker)."""
    meter, _ = fake_meter_no_gauge
    record_gauge("eprocess.martingale_test_status", 1)  # must not raise
    assert meter.created == []


@pytest.mark.unit
def test_instruments_are_created_once_and_reused(
    fake_meter: tuple[_FakeMeter, list[str]],
) -> None:
    """The create-once contract: two calls with the same instrument name create
    the underlying OTel instrument exactly once."""
    meter, _ = fake_meter
    record_counter("cw_detect.oracle_disagreement_count", attributes={"language": "java"})
    record_counter("cw_detect.oracle_disagreement_count", attributes={"language": "python"})
    assert meter.created.count(("counter", "cw_detect.oracle_disagreement_count", "1")) == 1
    assert meter.instruments["cw_detect.oracle_disagreement_count"].calls == [
        ("add", 1, {"language": "java"}),
        ("add", 1, {"language": "python"}),
    ]


@pytest.mark.unit
def test_reset_for_tests_clears_the_instrument_cache(
    fake_meter: tuple[_FakeMeter, list[str]],
) -> None:
    """``_reset_for_tests`` (the test seam) forces re-creation on the next call —
    exercised here directly since fixtures also rely on it for isolation."""
    from tools.observability import metrics as metrics_mod

    meter, _ = fake_meter
    record_counter("cw_detect.oracle_disagreement_count")
    metrics_mod._reset_for_tests()
    record_counter("cw_detect.oracle_disagreement_count")
    assert meter.created.count(("counter", "cw_detect.oracle_disagreement_count", "1")) == 2


@pytest.mark.unit
def test_hermetic_noop_when_opentelemetry_not_installed() -> None:
    """The TRUE hermetic-absence path: this repo's ``dev`` extra never installs
    ``opentelemetry-*`` (by design — DOC-CMP-DEPLOY-03), so every public
    function must be a safe no-op with nothing installed. Skips (rather than
    silently mis-testing) if a future dependency change makes the package
    available, since that would no longer exercise the absence branch.
    """
    if importlib.util.find_spec("opentelemetry") is not None:
        pytest.skip("opentelemetry is installed in this environment")
    record_job_completion(
        "snapshot_worker",
        "success",
        12.5,
        counter_attributes={"region": "us-east-1", "env_digest": "sha256:" + "a" * 64},
        duration_attributes={"precondition_status": "closed-world"},
    )
    record_counter("attestor.core_diff_count", value=0)
    record_gauge("eprocess.martingale_test_status", 1)


@pytest.mark.unit
def test_observability_package_lazily_reexports_metric_functions() -> None:
    """``tools.observability`` re-exports the three emitters without eagerly
    importing OTel (``__getattr__`` lazy re-export, CLAR-DEPLOY-20)."""
    import tools.observability as obs

    assert obs.record_counter is record_counter
    assert obs.record_gauge is record_gauge
    assert obs.record_job_completion is record_job_completion
    with pytest.raises(AttributeError):
        _ = obs.definitely_not_a_real_attribute  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Part B — emission-point wiring (producer modules), existing hermetic fakes
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_snap05_record_snapshot_job_completion_wires_region_and_env_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CMP-SNAP-05: :func:`record_snapshot_job_completion` calls the shared
    emitter with the {region, env_digest} counter attrs + {precondition_status}
    duration attr (CLAR-DEPLOY-20)."""
    import services.snapshot.worker as snap_worker

    calls: list[tuple[str, str, float, dict[str, str], dict[str, str]]] = []

    def _spy(
        worker: str,
        outcome: str,
        duration_ms: float,
        *,
        counter_attributes: dict[str, str],
        duration_attributes: dict[str, str],
    ) -> None:
        calls.append(
            (worker, outcome, duration_ms, dict(counter_attributes), dict(duration_attributes))
        )

    monkeypatch.setattr(snap_worker, "record_job_completion", _spy)

    env_digest = "sha256:" + "c" * 64
    snap_worker.record_snapshot_job_completion(
        "success",
        250.0,
        env_digest=env_digest,
        precondition_status="closed-world",
        environ={"AWS_REGION": "eu-west-1"},
    )

    assert calls == [
        (
            "snapshot_worker",
            "success",
            250.0,
            {"region": "eu-west-1", "env_digest": env_digest},
            {"precondition_status": "closed-world"},
        )
    ]


@pytest.mark.unit
def test_snap05_record_snapshot_job_completion_defaults_region_us_east_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No ``AWS_REGION`` in the injected environ -> the documented default."""
    import services.snapshot.worker as snap_worker

    calls: list[dict[str, str]] = []
    monkeypatch.setattr(
        snap_worker,
        "record_job_completion",
        lambda *a, counter_attributes, duration_attributes, **k: calls.append(
            dict(counter_attributes)
        ),
    )

    env_digest = "sha256:" + "d" * 64
    snap_worker.record_snapshot_job_completion(
        "failure", 5.0, env_digest=env_digest, precondition_status="degraded", environ={}
    )
    assert calls == [{"region": "us-east-1", "env_digest": env_digest}]


@pytest.mark.unit
def test_orch03_run_detector_emits_success_completion_metric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CMP-ORCH-03: a successful ``run_detector`` call emits exactly one
    ``detector_worker`` success completion metric, verbatim attrs (CLAR-DEPLOY-20)."""
    import services.scan.worker as scan_worker

    calls: list[tuple[str, str, dict[str, str], dict[str, str]]] = []

    def _spy(
        worker: str,
        outcome: str,
        duration_ms: float,
        *,
        counter_attributes: dict[str, str],
        duration_attributes: dict[str, str],
    ) -> None:
        assert isinstance(duration_ms, float) and duration_ms >= 0.0
        calls.append((worker, outcome, dict(counter_attributes), dict(duration_attributes)))

    monkeypatch.setattr(scan_worker, "record_job_completion", _spy)

    job = good_job()
    findings = run_detector(
        core_injection_detector(),
        injection_taint_cpg(),
        job,
        slice_fingerprinter=deterministic_slice_fingerprinter(),
    )
    assert findings, "anti-vacuity: the real #288 spec must fire a finding"
    assert calls == [
        (
            "detector_worker",
            "success",
            {"detector_id": "java-py-injection", "engine": "ifds", "env_digest": job.env_digest},
            {"detector_id": "java-py-injection", "engine": "ifds"},
        )
    ]


@pytest.mark.unit
def test_orch03_run_detector_emits_failure_completion_metric_and_reraises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fail-closed raise (out-of-set engine) still emits exactly one
    ``failure`` completion metric before propagating — the metric wrapper never
    swallows the exception (byte-identical behaviour, purely additive telemetry)."""
    import services.scan.worker as scan_worker

    calls: list[tuple[str, str, dict[str, str]]] = []

    def _spy(
        worker: str,
        outcome: str,
        duration_ms: float,
        *,
        counter_attributes: dict[str, str],
        duration_attributes: dict[str, str],
    ) -> None:
        calls.append((worker, outcome, dict(counter_attributes)))

    monkeypatch.setattr(scan_worker, "record_job_completion", _spy)

    job = good_job()
    with pytest.raises(InvariantViolation):
        run_detector(
            out_of_set_engine_detector(),
            injection_taint_cpg(),
            job,
            slice_fingerprinter=deterministic_slice_fingerprinter(),
        )

    assert calls == [
        (
            "detector_worker",
            "failure",
            {"detector_id": "bad-engine", "engine": "quantum", "env_digest": job.env_digest},
        )
    ]


@pytest.mark.unit
def test_orch01_post_job_status_emits_hmac_reject_counter_on_invalid_hmac(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CMP-ORCH-01: an invalid-HMAC callback increments
    ``callback.hmac_reject_count`` at the verify seam BEFORE the 401 raise
    (CLAR-DEPLOY-20 metric 7), attributed by the stable path TEMPLATE."""
    from services.scan.api import (
        _CALLBACK_PATH_TEMPLATE,
        InvalidHmacError,
        OrgScopedScanStore,
        post_job_status,
    )

    calls: list[tuple[str, int, dict[str, str] | None]] = []
    import services.scan.api as scan_api

    monkeypatch.setattr(
        scan_api,
        "record_counter",
        lambda name, value=1, *, attributes=None: calls.append(
            (name, value, dict(attributes) if attributes else None)
        ),
    )

    issuer = FakeHmacKeyIssuer()
    job_id, scan_id = UUID(int=40), UUID(int=41)
    body = done_report(job_id, scan_id)
    with pytest.raises(InvalidHmacError):
        post_job_status(
            job_id,
            body,
            b"{}",
            hmac_header="HMAC k-unknown:deadbeef",
            worker_id_header="worker-1",
            timestamp_header=1000,
            key_issuer=issuer,
            scan_store=OrgScopedScanStore(),
            now=lambda: 1000,
        )

    assert calls == [("callback.hmac_reject_count", 1, {"endpoint": _CALLBACK_PATH_TEMPLATE})]


@pytest.mark.unit
def test_orch01_post_job_status_does_not_emit_counter_on_valid_hmac(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The positive leg: a correctly-signed callback never touches the counter
    (anti-vacuity companion to the rejection test above)."""
    from services.scan.api import OrgScopedScanStore, post_job_status

    calls: list[object] = []
    import services.scan.api as scan_api

    monkeypatch.setattr(scan_api, "record_counter", lambda *a, **k: calls.append((a, k)))

    issuer = FakeHmacKeyIssuer()
    job_id, scan_id = UUID(int=42), UUID(int=43)
    body = done_report(job_id, scan_id)
    key_id, secret = issuer.issue(job_id=job_id, scan_id=scan_id)
    header, body_bytes = sign_callback(
        job_id=job_id,
        worker_id="worker-1",
        timestamp=1000,
        body=body,
        key_id=key_id,
        secret=secret,
    )

    result = post_job_status(
        job_id,
        body,
        body_bytes,
        hmac_header=header,
        worker_id_header="worker-1",
        timestamp_header=1000,
        key_issuer=issuer,
        scan_store=OrgScopedScanStore(),
        now=lambda: 1000,
    )

    assert result is None
    assert calls == []


_CP05_SCAN_ID = UUID(int=2)  # matches good_job().scan_id — the synthetic F's scan
_CP05_S_VERSION = "1.4.2"
_CP05_ENV_DIGEST = "sha256:" + "a" * 64


@pytest.mark.unit
def test_cp05_attest_core_emits_core_diff_count_zero_on_clean_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CMP-CP-05: a clean attestation run emits ``attestor.core_diff_count``
    with ``add(0)`` — CLAR-DEPLOY-20 amended semantics (a REAL datapoint, not a
    skipped call), no attributes (no-dims metric)."""
    monkeypatch.setenv("LLM_TRIAGE", "off")
    calls: list[tuple[str, int, dict[str, str] | None]] = []
    import services.scan.attestor as attestor_mod

    monkeypatch.setattr(
        attestor_mod,
        "record_counter",
        lambda name, value=1, *, attributes=None: calls.append((name, value, attributes)),
    )

    verdict: AttestationVerdict = attest_scan(
        _CP05_SCAN_ID,
        "core",
        s_version=_CP05_S_VERSION,
        env_digest=_CP05_ENV_DIGEST,
        scan_runner=make_runner(),
    )
    assert verdict.result == "pass"
    assert calls == [("attestor.core_diff_count", 0, None)]


@pytest.mark.unit
def test_cp05_attest_core_emits_core_diff_count_one_on_seeded_nondeterminism(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A seeded core-path nondeterminism (Gate-3 falsifier's own teeth) flips
    the emitted value to 1 — the metric tracks the run's real byte-diff count."""
    monkeypatch.setenv("LLM_TRIAGE", "off")
    calls: list[tuple[str, int, dict[str, str] | None]] = []
    import services.scan.attestor as attestor_mod

    monkeypatch.setattr(
        attestor_mod,
        "record_counter",
        lambda name, value=1, *, attributes=None: calls.append((name, value, attributes)),
    )

    verdict: AttestationVerdict = attest_scan(
        _CP05_SCAN_ID,
        "core",
        s_version=_CP05_S_VERSION,
        env_digest=_CP05_ENV_DIGEST,
        scan_runner=SeededNondeterministicScanRunner(),
    )
    assert verdict.result == "fail"
    assert calls == [("attestor.core_diff_count", 1, None)]


@pytest.mark.unit
def test_snap04_record_oracle_run_emits_disagreement_counter_with_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CMP-SNAP-04: a disagreement run increments
    ``cw_detect.oracle_disagreement_count{language}`` exactly once."""
    calls: list[tuple[str, int, dict[str, str] | None]] = []
    import services.snapshot.diff_oracle as diff_oracle_mod

    monkeypatch.setattr(
        diff_oracle_mod,
        "record_counter",
        lambda name, value=1, *, attributes=None: calls.append((name, value, attributes)),
    )

    store = InMemoryOracleRunStore()
    run = record_oracle_run(
        snapshot_id=uuid.uuid4(),
        oracle_verdict="not-closed-world",
        oracle_version="oracle-1.0.0",
        cw_detect_version="cw-1.0.0",
        started_at="2026-06-01T00:00:00+00:00",
        completed_at="2026-06-01T00:05:00+00:00",
        oracle_run_store=store,
        language="java",
    )
    assert run.agreed is False
    assert calls == [("cw_detect.oracle_disagreement_count", 1, {"language": "java"})]


@pytest.mark.unit
def test_snap04_record_oracle_run_defaults_language_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No ``language`` kwarg supplied -> the documented ``"unknown"`` default
    (the DOC §3.2 row carries no language column yet — AC-SNAP-04a deferred)."""
    calls: list[tuple[str, int, dict[str, str] | None]] = []
    import services.snapshot.diff_oracle as diff_oracle_mod

    monkeypatch.setattr(
        diff_oracle_mod,
        "record_counter",
        lambda name, value=1, *, attributes=None: calls.append((name, value, attributes)),
    )

    store = InMemoryOracleRunStore()
    record_oracle_run(
        snapshot_id=uuid.uuid4(),
        oracle_verdict="not-closed-world",
        oracle_version="oracle-1.0.0",
        cw_detect_version="cw-1.0.0",
        started_at="2026-06-01T00:00:00+00:00",
        completed_at="2026-06-01T00:05:00+00:00",
        oracle_run_store=store,
    )
    assert calls == [("cw_detect.oracle_disagreement_count", 1, {"language": "unknown"})]


@pytest.mark.unit
def test_snap04_record_oracle_run_no_counter_on_agreement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An agreement (closed-world) row emits NOTHING — metric absence is
    healthy for event counters (CLAR-DEPLOY-20 ``treat_missing_data=notBreaching``)."""
    calls: list[object] = []
    import services.snapshot.diff_oracle as diff_oracle_mod

    monkeypatch.setattr(diff_oracle_mod, "record_counter", lambda *a, **k: calls.append((a, k)))

    store = InMemoryOracleRunStore()
    run = record_oracle_run(
        snapshot_id=uuid.uuid4(),
        oracle_verdict="closed-world",
        oracle_version="oracle-1.0.0",
        cw_detect_version="cw-1.0.0",
        started_at="2026-06-01T00:00:00+00:00",
        completed_at="2026-06-01T00:05:00+00:00",
        oracle_run_store=store,
    )
    assert run.agreed is True
    assert calls == []


# ---------------------------------------------------------------------------
# Part B (cont.) — TRI-02 Gate-4 heartbeat CLI (scripts/publish_gate4_status.py)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_publish_gate4_status_otel_lane_calls_record_gauge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lane 1 (OTel): ``publish`` always calls :func:`record_gauge` with the
    pinned metric name + the caller's 0/1 status."""
    from scripts.publish_gate4_status import METRIC_NAME, publish

    calls: list[tuple[str, int, dict[str, str] | None]] = []
    import tools.observability.metrics as metrics_mod

    monkeypatch.setattr(
        metrics_mod,
        "record_gauge",
        lambda name, value, *, attributes=None: calls.append((name, value, attributes)),
    )

    report = publish(1, environ={})
    assert calls == [(METRIC_NAME, 1, None)]
    assert report["otel"] == "attempted"
    assert "cloudwatch_exit" not in report  # lane 2 dormant without the opt-in env var


@pytest.mark.unit
def test_publish_gate4_status_rejects_out_of_range_status() -> None:
    from scripts.publish_gate4_status import publish

    with pytest.raises(ValueError, match="0 or 1"):
        publish(2, environ={})


@pytest.mark.unit
def test_publish_gate4_status_cloudwatch_lane_is_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lane 2 (direct CloudWatch put-metric-data) fires ONLY when
    ``SCANIPY_METRICS_CW_DIRECT=1``, and shells out via the injected runner
    (never a bare ``subprocess.run`` at call time) — hermetic, no real AWS CLI."""
    from scripts.publish_gate4_status import METRIC_NAME, NAMESPACE, publish

    captured_argv: list[list[str]] = []

    def _fake_runner(argv: list[str], **kwargs: Any) -> types.SimpleNamespace:
        captured_argv.append(argv)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    # shutil.which("aws") must resolve for the runner branch to fire; patch it
    # to a deterministic non-empty path (no real binary invoked — the runner is
    # injected, not subprocess.run itself).
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/aws")

    report = publish(0, environ={"SCANIPY_METRICS_CW_DIRECT": "1"}, runner=_fake_runner)
    assert report["cloudwatch_exit"] == 0
    assert len(captured_argv) == 1
    argv = captured_argv[0]
    assert argv[:3] == ["/usr/bin/aws", "cloudwatch", "put-metric-data"]
    assert "--namespace" in argv and NAMESPACE in argv
    assert "--metric-name" in argv and METRIC_NAME in argv
    assert "--value" in argv and "0" in argv


@pytest.mark.unit
def test_publish_gate4_status_cloudwatch_lane_missing_aws_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No ``aws`` on PATH -> a clean 127 report, never a raised exception."""
    from scripts.publish_gate4_status import publish

    monkeypatch.setattr("shutil.which", lambda _name: None)
    report = publish(1, environ={"SCANIPY_METRICS_CW_DIRECT": "1"})
    assert report["cloudwatch_exit"] == 127
    assert "aws CLI not found" in str(report["cloudwatch_error"])


@pytest.mark.unit
def test_publish_gate4_status_main_exit_code_reflects_cloudwatch_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``main`` returns non-zero ONLY when the explicitly-requested CloudWatch
    put failed; the OTel lane is always non-gating."""
    from scripts.publish_gate4_status import main

    monkeypatch.setenv("SCANIPY_METRICS_CW_DIRECT", "1")
    monkeypatch.setattr("shutil.which", lambda _name: None)  # forces exit_code 127 -> main() 1

    exit_code = main(["--status", "1"])
    assert exit_code == 1
    out = capsys.readouterr().out
    assert '"metric": "eprocess.martingale_test_status"' in out


@pytest.mark.unit
def test_publish_gate4_status_main_success_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """No CloudWatch opt-in -> ``main`` returns 0 (OTel-only, non-gating)."""
    from scripts.publish_gate4_status import main

    monkeypatch.delenv("SCANIPY_METRICS_CW_DIRECT", raising=False)
    assert main(["--status", "0"]) == 0
