# DOC-CMP-DEPLOY-03 — Observability surfaces

**Status:** ACTIVE (Phase 0 per-component deliverable)
**Source-of-truth lineage:**

- `WBS.md §2.4 CMP-DEPLOY-03` (Purpose + AC-DEPLOY-03a/b/c).
- `WBS.md §17` — `CLAR-DEPLOY-07` (RESOLVED — OpenTelemetry → CloudWatch Logs + X-Ray).
- `PLAN.md §"Central correction"` — every span and log line must carry `S_version` and `env_digest` (INV-2).
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — CLAR-DEPLOY-07.
- `docs/cross-cutting/DOC-RUNBOOK.md §10` — observability operational reference.
- `docs/cross-cutting/DOC-INV.md §4` — INV-2 (every span carries `S_version` + `env_digest`).
- `.claude/rules/00-global.md` (RULE-6 provenance threading), `.claude/rules/02-provenance.md`.
- `.claude/commands/sre-agent.md` — mandatory structured log fields (the `LoggerFactory` contract).

This document is the **implementation contract** for `CMP-DEPLOY-03`. It defines the OpenTelemetry SDK initialisation, exporter configuration, mandatory span attributes, custom metrics namespace, and the alarm set required by `AC-DEPLOY-03c`. Every component that emits logs or spans MUST initialise via the surface defined here.

---

## 1. Component identity

| Field | Value |
|---|---|
| `CMP-ID` | `CMP-DEPLOY-03` |
| Subsystem | Deployment (`WBS.md §2.4`) |
| Staging | cross-cutting (`WBS.md §2.4`) |
| Depends-On | `CMP-DEPLOY-01` (`WBS.md §20`) |
| Owner | **DEFERRED** via `CLAR-OWNER-01`; operational owner per `.claude/commands/sre-agent.md` is the SRE/DevOps Agent. |
| INV-* touched | **INV-2 (cross-trace audit).** Every emitted span and log line carries `S_version` + `env_digest`. Also carries `origin` on any span that touches a finding emission path. This is the substrate-level audit trail that complements the durable `provenance_records` chain. |
| Substrate | OpenTelemetry SDK · CloudWatch Logs + Metrics + X-Ray (CLAR-DEPLOY-07) |

---

## 2. Mandate

**Verbatim WBS `Purpose:` (`WBS.md §2.4 CMP-DEPLOY-03`):**

> Structured logs, metrics, and traces for every worker and API surface. Carries the per-scan correlation fields needed for cross-component triage (scan id, snapshot id, org id, codebase id, detector id, `S_version`, `env_digest`, `fingerprint_class`, `origin`).

**Operational role.** `CMP-DEPLOY-03` is the **observability initialisation module** every service imports at process start. It bootstraps the OTel SDK with the AWS-resolved exporter set (CloudWatch Logs, CloudWatch Metrics, X-Ray), installs a `LoggerFactory` that enforces the mandatory structured-log fields from `.claude/commands/sre-agent.md`, and registers the alarm set defined by `AC-DEPLOY-03c`. The observability surface is what makes a single `scan_id` resolve to a chronological cross-component trace from webhook ingest through Attestor verdict (`AC-DEPLOY-03a`). The alarms defined here are first-line incident detection for determinism failures, INV-violations at runtime, and CI gate regressions.

---

## 3. Interface contract

`CMP-DEPLOY-03` exposes two surfaces:

1. **Python package** `tools/observability/` imported by every service (`init_otel`, `LoggerFactory`, custom metrics helpers).
2. **Terraform module** `infra/modules/observability/` provisioning CloudWatch log groups, metric streams, X-Ray groups, and the CloudWatch alarms.

### 3.1 OTel SDK initialisation

```python
# tools/observability/init.py

from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor

import os, typing as t

def init_otel(service_name: str) -> None:
    """Initialise OpenTelemetry for a Scanipy v3.2 service.

    Reads from the env-var contract:
      SCANIPY_WORKER_VERSION       -> SERVICE_VERSION resource attribute
      SCANIPY_ENV_DIGEST           -> env_digest resource attribute (INV-2 anchor)
      OTEL_EXPORTER_OTLP_ENDPOINT  -> OTel collector endpoint (in-VPC ECS service)
      OTEL_SERVICE_NAME            -> overrides the service_name argument if set
      AWS_REGION                   -> region tag

    The OTel collector (a sidecar ECS service per CLAR-DEPLOY-07) forwards to:
      - CloudWatch Logs    (logs exporter, structured JSON)
      - CloudWatch Metrics (metric exporter, namespace 'Scanipy/v3.2')
      - X-Ray              (trace exporter, AWS X-Ray)
    """
    env_digest = os.environ.get("SCANIPY_ENV_DIGEST", "")
    if not env_digest:
        raise RuntimeError("INV-2: SCANIPY_ENV_DIGEST must be set before OTel init")

    resource = Resource.create({
        SERVICE_NAME: os.environ.get("OTEL_SERVICE_NAME", service_name),
        SERVICE_VERSION: os.environ.get("SCANIPY_WORKER_VERSION", "unknown"),
        "env_digest": env_digest,
        "deployment.environment": os.environ.get("SCANIPY_ENV", "prod"),
        "cloud.region": os.environ.get("AWS_REGION", "us-east-1"),
    })

    # Tracer
    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter())
    )
    trace.set_tracer_provider(trace_provider)

    # Metrics
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter())],
    )
    metrics.set_meter_provider(meter_provider)

    # Auto-instrumentation for AWS SDK, HTTP, Postgres
    BotocoreInstrumentor().instrument()
    RequestsInstrumentor().instrument()
    Psycopg2Instrumentor().instrument()
```

### 3.2 Mandatory span attributes

Every span emitted in the platform MUST carry the following attributes when in scope (the `LoggerFactory` enforces inclusion in logs; span code-paths set them via the OTel context):

| Attribute | Type | When required | Source |
|---|---|---|---|
| `service` | string | Always | OTel resource (`SERVICE_NAME`) |
| `build_commit` | string (sha) | Always | `SCANIPY_WORKER_VERSION` env var (set at image build) |
| `env_digest` | string (sha256:...) | Always | OTel resource (read from ECS task metadata) |
| `org_id` | uuid | When the operation is within a tenant scope | Set by request-scoped context (`X-Scanipy-Org-Id` header from CMP-CP-01) |
| `scan_id` | uuid | When the operation is part of a scan | Propagated via SQS message attributes + HTTP headers |
| `snapshot_id` | uuid | When operating on a specific snapshot | From the SQS message |
| `codebase_id` | uuid | When operating on a specific codebase | From the scan/snapshot context |
| `detector_id` | string | On any span inside a detector execution | From the detector registry (CMP-DET-02) |
| `S_version` | semver | On any finding-emitting span (INV-2) | From the scan submission (CMP-ORCH-01) |
| `origin` | enum (`deterministic-core`/`oracle-passthrough`) | On any finding-emitting span (INV-1) | Set by CMP-ORCH-03 per detector engine |
| `fingerprint_class` | enum (`strong`/`weak`) | On any span that touches `cpg_order_hash` (INV-5) | From CMP-CORE-02 |
| `cpg_order_hash` | string (sha256) | On any finding-emitting span | From CMP-CORE-03 |
| `precondition_status` | enum (`closed-world`/`degraded`/`full-reparse`) | On snapshot spans | From CMP-SNAP-03 verdict |
| `level` | enum (INFO/WARN/ERROR) | On logs | `LoggerFactory` |
| `ts` | iso8601 | On logs | `LoggerFactory` |

**Note on `org_id`.** Spans crossing the tenant boundary (e.g. the Attestor running against the canary corpus) carry `org_id=null` and `org_id_kind="platform"`. The dashboard must not display platform-level spans alongside tenant traces.

### 3.3 LoggerFactory (mandatory structured fields)

```python
# tools/observability/logging.py
import json, logging, time, os, typing as t
from opentelemetry import trace

REQUIRED_FIELDS = {
    "service", "build_commit", "env_digest",
    "level", "ts", "msg",
    # optional but emitted with explicit null:
    "scan_id", "org_id", "codebase_id", "snapshot_id",
    "detector_id", "S_version", "origin", "fingerprint_class",
}

class ScanipyJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Pull current span context (set by OTel) so logs and traces correlate.
        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None

        payload: dict[str, t.Any] = {
            "service":      os.environ.get("OTEL_SERVICE_NAME", record.name),
            "build_commit": os.environ.get("SCANIPY_WORKER_VERSION", "unknown"),
            "env_digest":   os.environ.get("SCANIPY_ENV_DIGEST", ""),
            "level":        record.levelname,
            "ts":           time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(record.created)),
            "msg":          record.getMessage(),
            "trace_id":     f"{ctx.trace_id:032x}" if ctx else None,
            "span_id":      f"{ctx.span_id:016x}" if ctx else None,
        }
        # Caller-supplied structured fields (record.__dict__'s `extra` kwarg)
        for k in ("scan_id", "org_id", "codebase_id", "snapshot_id",
                  "detector_id", "S_version", "origin", "fingerprint_class"):
            payload[k] = getattr(record, k, None)
        return json.dumps(payload, ensure_ascii=False)

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(ScanipyJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
```

### 3.4 Custom metrics namespace

CloudWatch namespace: **`Scanipy/v3.2`**.

| Metric | Type | Dimensions | Emitted by |
|---|---|---|---|
| `snapshot_worker.failure_count` | counter | `region`, `env_digest` | `CMP-SNAP-05` on `report_status(state='failed')` |
| `snapshot_worker.duration_ms` | histogram | `precondition_status` | `CMP-SNAP-05` per job |
| `detector_worker.failure_count` | counter | `detector_id`, `engine`, `env_digest` | `CMP-ORCH-03` per failure |
| `detector_worker.duration_ms` | histogram | `detector_id`, `engine` | `CMP-ORCH-03` per detector run |
| `callback.hmac_reject_count` | counter | `endpoint` | `CMP-ORCH-01` / `CMP-SNAP-01` on HMAC rejection |
| `attestor.core_diff_count` | counter | (no dimensions) | `CMP-CP-05` on core-partition byte diff (any non-zero is incident-grade) |
| `cw_detect.oracle_disagreement_count` | counter | `language` | `CMP-SNAP-04` on a `CW-DETECT` ↔ oracle disagreement |
| `eprocess.martingale_test_status` | gauge (0/1) | (no dimensions) | `CMP-TRI-02` after the martingale unit test |
| `dlq.message_count` | gauge | `queue_name` | SQS metric stream (passive) |
| `cosign.signature_verify_count` | counter | `image_name`, `result` (`success`/`fail`) | ECS task launch hook (`CMP-DEPLOY-04`) |

### 3.5 Alarms (verbatim contract from AC-DEPLOY-03c)

The following alarms MUST exist and be wired to the on-call paging surface. **Wiring (PagerDuty integration) is deferred per `CLAR-DEPLOY-07` (RESOLVED — placeholder for v3.2 baseline). Alarms themselves are not deferred.**

| Alarm | Threshold | Metric | Severity |
|---|---|---|---|
| `snapshot_worker.failure_rate` | > 5% over 15min | `snapshot_worker.failure_count` / total | high |
| `detector_worker.failure_rate` | > 5% over 15min | `detector_worker.failure_count` / total | high |
| `callback.hmac_reject_rate` | > 0% over 5min | `callback.hmac_reject_count` (any rejection is suspicious) | high |
| `attestor.core_diff` | > 0 | `attestor.core_diff_count` | **incident** (any non-zero is a hard incident per `AC-DEPLOY-03c`) |
| `cw_detect.oracle_disagreement` | > 0 over 1h | `cw_detect.oracle_disagreement_count` | high (triggers `CMP-SNAP-04` re-partition flow) |
| `eprocess.martingale_test_failure` | status = 0 | `eprocess.martingale_test_status` | **incident** (blocks customer-enablement deploy per `CMP-CI-01` Gate 4) |
| `dlq.snapshot_messages` | > 0 sustained 30min | `dlq.message_count{queue=snapshot-dlq}` | high |
| `dlq.detector_messages` | > 0 sustained 30min | `dlq.message_count{queue=detector-dlq}` | high |

---

## 4. Inputs and outputs

### 4.1 Inputs

| Input | Source | Contract |
|---|---|---|
| `SCANIPY_ENV_DIGEST` env var | ECS task metadata (`CMP-SNAP-05` reads, `init_otel` reads) | INV-2 anchor; init fails if empty. |
| `SCANIPY_WORKER_VERSION` | Image build (LABEL + ENV) | Becomes `build_commit` attribute. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Env var | OTel collector sidecar endpoint (provisioned by `CMP-DEPLOY-01` `observability` module). |
| Spans from instrumented services | OTel auto-instrumentation + manual `tracer.start_as_current_span` calls | Carry mandatory attributes from §3.2. |

### 4.2 Outputs

| Output | Where | Contract |
|---|---|---|
| Structured JSON logs | CloudWatch Logs (group from `CMP-DEPLOY-01` outputs) | Per `ScanipyJsonFormatter`; every required field present (null permitted where indicated). |
| Custom metrics | CloudWatch Metrics namespace `Scanipy/v3.2` | Per §3.4. |
| Distributed traces | AWS X-Ray | Per §3.2 attributes; `scan_id` propagation enables `AC-DEPLOY-03a` cross-component trace. |
| Alarms | CloudWatch Alarms in `infra/modules/observability` | Per §3.5. |
| Dashboards | CloudWatch Dashboards (provisioned by Terraform) | One per subsystem (scan lifecycle, snapshot lifecycle, attestor, CI gates). |

---

## 5. Invariants touched

| Invariant | How `CMP-DEPLOY-03` discharges it | Test |
|---|---|---|
| **INV-2 (cross-trace audit)** | Every emitted span and log line carries `env_digest` and (where relevant) `S_version`. `init_otel` refuses to start if `SCANIPY_ENV_DIGEST` is empty. The OTel resource attributes are set once at process start and are immutable for the process lifetime. | `TST-AC-DEPLOY-03b` `[FORTHCOMING]`; downstream `TST-INV-2-ORCH-03` (the values are correct, not just present). |
| **INV-1 supporting** | Spans on finding-emitting paths carry `origin`. This lets cross-trace audit confirm at a substrate level (independently of the durable `provenance_records` chain) that a finding's origin was set per `CMP-ORCH-03`'s engine-derived rule. | `TST-AC-DEPLOY-03a` `[FORTHCOMING]` (the trace contains `origin` on every finding-emit span). |
| **INV-5 supporting** | Spans that touch `cpg_order_hash` carry `fingerprint_class` so an auditor reading the trace can confirm canonicality status without reaching into the `provenance_records` table. | `TST-INV-5-CORE-03` (downstream — the value is correctly threaded). |

---

## 6. Algorithm / data flow

### 6.1 Initialisation flow (per process)

```
1. ECS task starts.
2. Container entrypoint imports tools.observability.init_otel and calls it
   with the service name (e.g. 'snapshot-worker', 'detector-worker', 'api').
3. init_otel:
   a. Reads SCANIPY_ENV_DIGEST; raises RuntimeError if empty (INV-2 fail-closed).
   b. Builds the OTel Resource with service/version/env_digest attributes.
   c. Wires BatchSpanProcessor -> OTLPSpanExporter -> OTel collector sidecar.
   d. Wires PeriodicExportingMetricReader -> OTLPMetricExporter -> collector.
   e. Auto-instruments botocore, requests, psycopg2.
4. Service main loop starts; every span automatically inherits the resource
   attributes set in step 3b.
5. Service code adds request-scoped attributes (org_id, scan_id, etc.) via
   tracer.start_as_current_span(..., attributes={...}) or span.set_attribute(...).
6. LoggerFactory.get_logger('<module>') returns a logger whose Formatter pulls
   the current OTel span context so logs are trace-correlated.
```

### 6.2 Cross-component trace correlation (`AC-DEPLOY-03a`)

The trace for a single `scan_id` flows:

```
[webhook ingest (CMP-SCM-02/03)]   trace_id=T  parent=none
  └─ [snapshot enqueue (CMP-SNAP-01)]  trace_id=T  parent=webhook
       └─ [snapshot worker (CMP-SNAP-05)]  trace_id=T  parent=snapshot-enqueue
            ├─ [CW-DETECT (CMP-SNAP-03)]  trace_id=T
            ├─ [CPG build (CMP-SNAP-02)]  trace_id=T
            └─ [report_status (HMAC POST)] trace_id=T
                 └─ [detector fanout (CMP-ORCH-02)]  trace_id=T  parent=report_status
                      ├─ [detector worker A (CMP-ORCH-03)]  trace_id=T
                      │    └─ [normalizer (CMP-FND-01)]  trace_id=T
                      ├─ [detector worker B] ... (parallel)
                      └─ [attestor (CMP-CP-05)]  trace_id=T (separate but linked)
                           └─ [callback delivery (CMP-ORCH-01)]  trace_id=T
```

Propagation between async hops (SQS, HMAC POST) uses W3C Trace Context headers:
- **SQS:** `X-Ray-TraceId` SQS message attribute (set by the boto3 instrumentation, propagated by the consumer's first span).
- **HMAC POST:** `traceparent` HTTP header (set by `requests` instrumentation).

### 6.3 Alarm wiring

```
CloudWatch Metric (custom or AWS-native)
  -> CloudWatch Alarm (defined in infra/modules/observability/alarms.tf)
     -> SNS topic 'scanipy-prod-alarms'
        -> (deferred wiring to PagerDuty per CLAR-DEPLOY-07; SNS is the boundary)
```

---

## 7. Failure modes and error contracts

| Failure | Detection | Response |
|---|---|---|
| OTel collector sidecar unavailable | OTLP export retry loop fails | OTel falls back to a local-only buffered log stream (CloudWatch Logs direct via container log driver). Alarm `otel.export_failure_rate` fires; spans are dropped (with metric) rather than blocking the worker. Logs still reach CloudWatch via the awslogs driver. |
| `SCANIPY_ENV_DIGEST` env var missing | `init_otel` raises at process start | Process exits non-zero before serving traffic. INV-2 fail-closed. |
| Log volume exceeds CloudWatch ingest quota | CloudWatch service metric | Logs are sampled at the LoggerFactory level (50% INFO, 100% WARN/ERROR) per region. Sampling rate is a config knob. |
| Span attribute `origin` missing on a finding-emit span | Caught by code review + a lint rule in `LoggerFactory`'s `extra` kwarg validation | Treated as an INV-1 violation; PR is rejected. Runtime missing attribute is a soft warning + metric. |
| X-Ray sampling drops a trace | Configured 10% sampling for INFO-level paths; 100% for ERROR | A dropped trace cannot be reconstructed; the durable `provenance_records` chain is the absolute audit source. Span-level audit is a debugging surface, not a compliance surface. |
| Alarm misfires (false positive) | SRE on-call ack | Document in `DOC-RUNBOOK §10`; tune threshold in next patch release. Alarm thresholds in §3.5 are inviolable for the four listed in `AC-DEPLOY-03c`. |
| LoggerFactory `extra` kwarg type mismatch | Runtime exception in `ScanipyJsonFormatter` | Falls back to vanilla `logging.Formatter`; emits an `observability.formatter_error` metric. Service does not crash. |

---

## 8. Provenance threading

`CMP-DEPLOY-03` does not write to `provenance_records`. It carries the four required provenance fields through the observability surface as **read-side fields** (so an operator triaging a finding can reach the full audit trail without an additional DB join):

| Field | How it threads through observability |
|---|---|
| `origin` | Set as a span attribute on every finding-emit span; also written as a log field by `LoggerFactory` when the caller passes `extra={"origin": ...}`. |
| `S_version` | Span attribute on finding-emit spans; pulled from the scan-submission context. |
| `env_digest` | OTel resource attribute (set once at process start); also a log field for every line. **The substrate's most-distributed copy of `env_digest`.** |
| `cpg_order_hash` (+ annotation) | Span attribute on emit spans; the annotation `canonical iff fingerprint_class = strong` is appended only on the auditor-export side (CMP-FND-03), not in observability spans (it would inflate every span). The `fingerprint_class` attribute is sufficient for an operator to compute the annotation. |

**Must NOT modify** any of the four — observability is a read-side reflection of values set by `CMP-ORCH-03`, `CMP-SNAP-01`, `CMP-CORE-02/03`, etc.

---

## 9. Acceptance criteria cross-reference

Quoted verbatim from `WBS.md §2.4 CMP-DEPLOY-03`. Paraphrasing an AC is a contract break (RULE-4). All TST-AC-* are `[FORTHCOMING]`.

| AC | Verbatim statement | Test artifact |
|---|---|---|
| **AC-DEPLOY-03a** | > A single scan id resolves to a chronological cross-component trace covering at least: webhook ingest, snapshot worker, every detector worker, normalizer, attestor verdict, callback delivery. | `TST-AC-DEPLOY-03a` `[FORTHCOMING]` — integration test: submit a scan; query X-Ray with the `scan_id` (set as a custom annotation); assert the returned trace contains spans for each of webhook ingest, snapshot worker, every detector, `CMP-FND-01`, `CMP-CP-05`, and the callback POST. |
| **AC-DEPLOY-03b** | > Every emitted log line carries a service name, build commit, and `env_digest`. | `TST-AC-DEPLOY-03b` `[FORTHCOMING]` — log-fixture test: capture stdout of every service across a smoke scan; for each line, parse JSON; assert `service`, `build_commit`, `env_digest` keys are present and non-empty. |
| **AC-DEPLOY-03c** | > Alarms exist for: snapshot-worker failure rate, detector-worker failure rate, callback HMAC rejection rate, Attestor core-partition diff (any non-zero rate is a hard incident), `CW-DETECT` differential-oracle disagreement rate, e-process martingale-unit-test failure. | `TST-AC-DEPLOY-03c` `[FORTHCOMING]` — IaC test: `terraform plan` in the observability module asserts the existence of each of the six named CloudWatch Alarms with the thresholds in §3.5. |

---

## 10. Open questions

All `CLAR-DEPLOY-*` items bearing on this component are **RESOLVED**.

| CLAR-ID | Question | Status | Impact on CMP-DEPLOY-03 |
|---|---|---|---|
| `CLAR-DEPLOY-07` | Observability stack | **RESOLVED** | OTel → CloudWatch Logs + Metrics + X-Ray; alarm wiring to PagerDuty is a placeholder for v3.2 baseline (SNS topic is the boundary). |
| `CLAR-DEPLOY-01` | Cloud / compute service | **RESOLVED** | ECS Fargate; OTel collector runs as a sidecar ECS service. |
| `CLAR-OWNER-01` | Per-component owner | **DEFERRED** | §1 `Owner` stays DEFERRED. |

No new CLAR-DEPLOY-* are filed by this document.

---

## 11. References

- `WBS.md §2.4 CMP-DEPLOY-03` — verbatim Purpose + ACs.
- `docs/cross-cutting/DOC-DEPLOY-DECISIONS.md` — CLAR-DEPLOY-07.
- `docs/cross-cutting/DOC-RUNBOOK.md §10` — observability operational reference.
- `docs/cross-cutting/DOC-INV.md §4` — INV-2 owner exposition.
- `docs/cross-cutting/DOC-PROVENANCE.md §2` — the four required provenance fields (the read-side reflection here MUST match the write-side fields there).
- `docs/components/DOC-CMP-DEPLOY-01.md` (sibling) — provisions the CloudWatch / X-Ray / SNS substrate.
- `docs/components/DOC-CMP-DEPLOY-02.md` (sibling) — bakes `init_otel` and `LoggerFactory` into the worker image.
- `docs/components/DOC-CMP-SNAP-05.md` (consumer) — calls `init_otel` at worker boot.
- `.claude/rules/00-global.md` (RULE-6 provenance threading), `.claude/rules/02-provenance.md`.
- `.claude/commands/sre-agent.md` — mandatory structured log field list (canonical source for the `LoggerFactory` contract).

---

*Document end. Status: ACTIVE. Per `AC-DOC-04`, this file plus the cross-cutting refs above is sufficient for an implementation agent to produce a passing `CMP-DEPLOY-03`. This component is the cross-trace audit surface; INV-2's substrate-level reflection lives here.*
