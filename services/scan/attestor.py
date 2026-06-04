#   ``S_version`` keeps its capital S in the public re-run signature: it is the
#   normative provenance field name (INV-2; DOC-PROVENANCE §2). It rides through
#   the F-port unchanged so the byte-canonical SARIF key order CMP-FND-01 emits
#   (and the Attestor attests) is preserved. The ``AttestationVerdict`` field is
#   spelled ``s_version`` verbatim per DOC-CMP-CP-05 §3.4 (not "corrected").
"""CMP-CP-05 — partitioned Determinism Attestor (mechanism).

Implementation contract: ``docs/components/DOC-CMP-CP-05.md`` (§3 the two
pipelines — NORMATIVE, byte-identical to ``docs/cross-cutting/DOC-PARTITION.md``
§6 and ``.claude/rules/05-determinism.md`` "Attestor pipeline contract").
Cross-cutting refs: ``DOC-PARTITION`` §6, ``DOC-PROVENANCE`` (the signed chain
the Attestor appends to), ``.claude/rules/05-determinism.md`` (the two-pipeline
table is normative), ``.claude/rules/01-invariants.md`` (INV-1 hard gate, INV-3
LLM_TRIAGE=off).

The Attestor is the **empirical falsifier of property (a)**: for fixed
``(S_version, env_digest, LLM_TRIAGE=off)``, two independent re-runs of ``F``
over the same source must produce BYTE-IDENTICAL SARIF over the
``origin=deterministic-core`` partition. Any byte difference is a HARD FAIL.

Two pipelines, two pass criteria (DOC-CMP-CP-05 §3):

  * **Core** (``partition="core"``): re-run ``F`` twice under fixed
    ``(S_version, env_digest, LLM_TRIAGE=off)``; assert byte-identical SARIF over
    ``runs[0]`` (the core partition Run). Identical -> ``result="pass"``; any diff
    -> ``result="fail"`` + ``diff_summary`` populated (the incident artifact).
    ``LLM_TRIAGE`` MUST be off (INV-3); the core pipeline FAILS CLOSED if the flag
    is on.

  * **Oracle** (``partition="oracle"``): re-run ``F`` twice under fixed
    ``(S_version, env_digest)``; compute a MEASURED ``reproduction_rate`` =
    ``# stable findings / # total findings`` over ``runs[1]`` (the oracle Run).
    ``result`` is EXACTLY ``"rate-only"`` — never ``"pass"``/``"fail"``, and the
    verdict NEVER asserts the determinism theorem (no "byte-identical" /
    property-(a) language), even at rate 1.0.

WHAT THE PIPELINES NEVER DO (DOC-CMP-CP-05 §3.3 / DOC-PARTITION §6.3):
  * the core pipeline never asserts a guarantee over ``oracle-passthrough``;
  * the oracle pipeline never claims property (a), even at rate 1.0;
  * neither pipeline modifies ``origin`` (re-partition is CMP-SNAP-04's job) —
    the Attestor is READ-ONLY against the partition;
  * neither pipeline suppresses, deletes, or transforms a finding.

BUILD-AHEAD REGIME (sanctioned by CLAR-PROC-01, WBS §17 RESOLVED 2026-06-04).
  The DOC §3.4 ``attest_scan(scan_id, partition)`` contract loads a *persisted*
  SARIF blob for ``scan_id`` from S3 (run-1) and re-invokes the ORCH-01 scan API
  (run-2). Neither S3 nor a scan-by-id API exists in a hermetic CI. Per
  CLAR-PROC-01 condition (2), ``F`` is consumed through a TYPED port
  (:class:`ScanRunner`): ``run(scan_id) -> SARIFLog``. The production default
  (:func:`fail_closed_scan_runner`) raises a typed ``NotImplementedError`` naming
  the gated dependencies (ORCH-01 scan API + S3 blob load). A hermetic test
  injects a deterministic ``F`` built from ``services.scan.worker.run_detector``
  + ``emit_sarif`` over a synthetic CPG and the real #288 spec.

  INTERFACE-SHAPE DEVIATIONS from DOC §3.4 (reported, not invented; surfaced as
  text for the orchestrator to file a CLAR — the implementation agent cannot edit
  WBS §17):
    (i)  ``F`` is an injected ``ScanRunner`` port, not an in-module S3 load + scan
         API re-invocation. CLAR-PROC-01 condition (2).
    (ii) Hermetically BOTH runs are fresh F invocations; the DOC's "load persisted
         run-1 blob + re-run once" collapses to "run F twice fresh" — which is the
         stronger determinism check (it does not trust a stored blob).
    (iii)``attestor_hash`` is the sha256 of the CORE Run's canonical bytes
         (``SARIFLog.runs[0].canonical_bytes``), never the whole two-Run log:
         the oracle partition is *permitted* to differ and must not corrupt the
         core verdict (DOC §3.3).
    (iv) The ``attestations`` table INSERT (DOC §4.2) and the FND-03 provenance
         append are DB/AWS-gated; the provenance append is an OPTIONAL injected
         seam (default ``None`` -> ``signed_chain_id=None``, which the DOC's
         ``UUID | None`` field permits). No DB row is written in the hermetic
         surface; ``CMP-CP-05`` stays IN-PROGRESS until CANARY-01 + the
         persistence layer land.

Interface-shape deviations vs DOC §3.4 are consolidated in CLAR-CP-05-03
(WBS §17): injected ScanRunner F-port, caller-supplied s_version/env_digest,
fresh double-run, persistence-gated attestations/provenance seams, and the
oracle-rate denominator reading.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from analysis.sarif.canonical_emit import SARIFLog


# ---------------------------------------------------------------------------
# Type aliases (DOC-CMP-CP-05 §3.4)
# ---------------------------------------------------------------------------

Partition = Literal["core", "oracle"]
Result = Literal["pass", "fail", "rate-only"]

# The INV-3 env-var name the core pipeline pins off (DOC-CMP-CP-05 §4.1 / §7).
LLM_TRIAGE_ENV: str = "LLM_TRIAGE"


# ---------------------------------------------------------------------------
# Error contracts (DOC-CMP-CP-05 §7)
# ---------------------------------------------------------------------------


class AttestorConfigurationError(Exception):
    """A pre-run configuration check failed — NOT a determinism violation.

    Raised when the core pipeline is asked to run with ``LLM_TRIAGE`` leaked to a
    value other than ``"off"`` (INV-3 backstop, DOC-CMP-CP-05 §7 "core pipeline
    requires LLM_TRIAGE=off"), or when a partition is invoked with an
    ``s_version`` / ``env_digest`` that does not match the persisted scan's.

    Distinct from a determinism FAIL: a byte difference yields
    ``result="fail"`` (a verdict), whereas a misconfiguration is a hard error
    that aborts before the byte-compare can speak to property (a).
    """


# ---------------------------------------------------------------------------
# The F port (build-ahead seam, CLAR-PROC-01 condition (2))
# ---------------------------------------------------------------------------


@runtime_checkable
class ScanRunner(Protocol):
    """The ``F`` re-run port the Attestor invokes (DOC-CMP-CP-05 §3.4).

    ``run(scan_id)`` re-executes ``F`` over the SAME
    ``(codebase, commit_sha, S_version, env_digest)`` as the original scan and
    returns the canonical two-Run :class:`~analysis.sarif.canonical_emit.SARIFLog`
    (``runs[0]`` = core partition, ``runs[1]`` = oracle partition, per
    DOC-SARIF §4). The Attestor never canonicalises — it compares the
    already-canonical blobs CMP-FND-01 emits (DOC-CMP-CP-05 §3.5).

    Production: an ORCH-01 scan-API + S3 blob-load adapter (env-gated). Hermetic:
    a deterministic ``F`` over a synthetic CPG + the real #288 spec, injected
    through this typed seam — never a host-binary shell-out.
    """

    def run(self, scan_id: UUID) -> SARIFLog: ...


class _FailClosedScanRunner:
    """Production ``F`` port: raises until the env-gated scan-API/S3 load lands."""

    def run(self, scan_id: UUID) -> SARIFLog:
        raise NotImplementedError(
            f"attest_scan cannot re-run F for scan_id={scan_id} on the production "
            f"path: it requires the CMP-ORCH-01 scan API (re-invoke) + the S3 "
            f"persisted-SARIF blob load (CMP-CP-05 build-ahead, CLAR-PROC-01), "
            f"neither of which exists in a hermetic CI. Inject a ScanRunner via "
            f"attest_scan(..., scan_runner=...) in a hermetic test."
        )


def fail_closed_scan_runner() -> ScanRunner:
    """The default ``F`` port: fail-closed until ORCH-01 + S3 load land."""
    return _FailClosedScanRunner()


# ---------------------------------------------------------------------------
# Optional provenance-append seam (DOC-CMP-CP-05 §8) — DB/KMS-gated.
# ---------------------------------------------------------------------------


@runtime_checkable
class VerdictProvenanceAppender(Protocol):
    """Optional port that appends the verdict to the FND-03 signed chain.

    DOC-CMP-CP-05 §8: the verdict links to a ``provenance_records`` row via
    ``signed_chain_id``. That append is KMS/DB-gated; this seam is OPTIONAL
    (default ``None`` -> ``signed_chain_id=None``, which the DOC's
    ``UUID | None`` field permits). When supplied, it returns the id of the
    appended chain record.
    """

    def append_attestation(
        self,
        *,
        scan_id: UUID,
        partition: Partition,
        result: Result,
        attestor_hash: bytes,
    ) -> UUID: ...


# ---------------------------------------------------------------------------
# Verdict (DOC-CMP-CP-05 §3.4)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AttestationVerdict:
    """The result of one attestation pipeline run (DOC-CMP-CP-05 §3.4).

    Field names are verbatim from the DOC signature (``s_version`` lowercase per
    §3.4 — NOT "corrected" to capital-S; that would be an undocumented deviation).
    ``reproduction_rate`` is ``None`` on the core partition and a measured
    ``Decimal`` in ``[0, 1]`` on the oracle partition. ``diff_summary`` is ``None``
    on a pass and carries the first-differing-offset incident artifact on a core
    fail. ``signed_chain_id`` is ``None`` unless a provenance appender was injected.
    """

    scan_id: UUID
    partition: Partition
    result: Result
    attestor_hash: bytes  # sha256 of the canonical SARIF blob over THIS partition
    reproduction_rate: Decimal | None  # None on core; 0..1 on oracle
    s_version: str
    env_digest: str
    signed_chain_id: UUID | None  # FK -> provenance_records.id (CMP-FND-03); None if not wired
    diff_summary: str | None  # None on pass; first-differing-offset incident artifact on fail


# ---------------------------------------------------------------------------
# Core-pipeline byte comparison + incident artifact
# ---------------------------------------------------------------------------


def _diff_summary(blob_1: bytes, blob_2: bytes) -> str:
    """Build the incident artifact for a core-pipeline byte difference.

    Reports the first differing byte offset and the differing bytes (the
    DOC-CMP-CP-05 §6 "first differing offsets + bytes" diff). The comparison that
    drives the verdict is EXACT byte equality (never a tolerance/similarity/rate);
    this function only summarises an already-detected difference for the incident.
    """
    if len(blob_1) != len(blob_2):
        length_note = f"length {len(blob_1)} != {len(blob_2)}; "
    else:
        length_note = ""
    n = min(len(blob_1), len(blob_2))
    offset = next((i for i in range(n) if blob_1[i] != blob_2[i]), n)
    b1 = blob_1[offset : offset + 16]
    b2 = blob_2[offset : offset + 16]
    return (
        f"core-partition SARIF byte difference (property (a) FALSIFIED): "
        f"{length_note}first diff at offset {offset}: "
        f"run1={b1!r} run2={b2!r}"
    )


# ---------------------------------------------------------------------------
# Oracle-pipeline reproduction rate
# ---------------------------------------------------------------------------


def _oracle_reproduction_rate(run_1: SARIFLog, run_2: SARIFLog) -> Decimal:
    """Measured oracle reproduction rate = ``# reproduced / # in run 1``.

    Per DOC-CMP-CP-05 §3.4 step 4 (oracle partition). The DOC's persisted-blob-vs-
    rerun model reads the denominator as the ORIGINAL run's finding count: a finding
    is "reproduced" iff its canonical Result projection from run 1 (the
    persisted-blob analogue) reappears in run 2's oracle Run (``runs[1]``); the rate
    is ``# reproduced / # in run 1``. This is the asymmetric persisted-vs-rerun
    denominator — NOT a Jaccard union over both runs (the choice is surfaced for a
    CLAR). An empty run-1 oracle partition -> rate 1.0 (vacuously: nothing was
    unreproduced). Returns a ``Decimal`` quantised to 4 places (matching
    ``attestations.reproduction_rate numeric(5,4)``, DOC §4.2). The result is always
    "rate-only"; the rate is never a theorem claim.
    """
    set_1 = _oracle_result_bytes(run_1)
    set_2 = _oracle_result_bytes(run_2)
    if not set_1:
        return Decimal("1.0000")
    reproduced = set_1 & set_2
    rate = Decimal(len(reproduced)) / Decimal(len(set_1))
    return rate.quantize(Decimal("0.0001"))


def _oracle_result_bytes(log: SARIFLog) -> frozenset[bytes]:
    """The canonical per-Result byte projections of the oracle Run (``runs[1]``).

    Splits the oracle Run's canonical bytes into one byte-string per Result so set
    membership models per-finding stability. Each Result is re-serialised with the
    SAME canonical JSON parameters CMP-FND-01 uses (``sort_keys=True``, tight
    separators, ``ensure_ascii=False`` UTF-8 — DOC-SARIF §3 rules 1/2/4) — inlined
    here rather than reaching across FND-01's module-privacy boundary — so the
    identity is robust and order-independent.
    """
    import json

    oracle_run = log.runs[1]
    doc = json.loads(oracle_run.canonical_bytes)
    results = doc.get("results", [])
    return frozenset(
        json.dumps(r, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        for r in results
    )


# ---------------------------------------------------------------------------
# Public entry point (DOC-CMP-CP-05 §3.4)
# ---------------------------------------------------------------------------


def attest_scan(
    scan_id: UUID,
    partition: Partition,
    *,
    s_version: str,
    env_digest: str,
    scan_runner: ScanRunner | None = None,
    provenance_appender: VerdictProvenanceAppender | None = None,
) -> AttestationVerdict:
    """Run the attestation pipeline for ``scan_id`` on ``partition``.

    Core partition (DOC-CMP-CP-05 §3.1):
      1. INV-3 backstop: refuse to run unless ``LLM_TRIAGE=off`` (fail-closed,
         :class:`AttestorConfigurationError`). Byte-identity under triage-off is
         what proves the core partition is independent of any LLM path.
      2. Re-run ``F`` TWICE under fixed ``(s_version, env_digest)``.
      3. Byte-compare ``runs[0]`` (the core partition Run) ONLY — EXACT equality.
         identical -> ``result="pass"``; any diff -> ``result="fail"`` +
         ``diff_summary`` (the incident artifact).
      4. ``attestor_hash`` = sha256 of the CORE Run's canonical bytes
         (``SARIFLog.runs[0].sarif_hash``), never the whole two-Run log.

    Oracle partition (DOC-CMP-CP-05 §3.2):
      1. Re-run ``F`` twice under fixed ``(s_version, env_digest)``. ``LLM_TRIAGE``
         is NOT required off (oracle findings are not theorem-covered).
      2. Compute a MEASURED ``reproduction_rate`` over ``runs[1]`` (the oracle Run).
      3. ``result="rate-only"`` — NEVER ``"pass"``/``"fail"``; the verdict never
         asserts the determinism theorem.

    ``scan_runner`` defaults to the fail-closed production ``F`` port
    (CLAR-PROC-01); a hermetic test injects a deterministic ``F``.
    ``provenance_appender`` is optional (default ``None`` -> ``signed_chain_id=None``).
    """
    runner = scan_runner if scan_runner is not None else fail_closed_scan_runner()

    if partition == "core":
        # INV-3 fail-closed backstop (DOC-CMP-CP-05 §7). The core pipeline MUST run
        # with LLM_TRIAGE=off; byte-identity asserted while triage could be active
        # would not prove independence from the LLM path.
        triage = os.environ.get(LLM_TRIAGE_ENV, "off")
        if triage != "off":
            raise AttestorConfigurationError(
                f"core pipeline requires {LLM_TRIAGE_ENV}=off (INV-3); got "
                f"{LLM_TRIAGE_ENV}={triage!r}. Refusing to assert byte-identity "
                f"while the LLM triage path could be active."
            )
        return _attest_core(
            scan_id,
            runner,
            s_version=s_version,
            env_digest=env_digest,
            provenance_appender=provenance_appender,
        )

    if partition == "oracle":
        return _attest_oracle(
            scan_id,
            runner,
            s_version=s_version,
            env_digest=env_digest,
            provenance_appender=provenance_appender,
        )

    raise AttestorConfigurationError(  # pragma: no cover — Literal guards callers
        f"partition must be 'core' or 'oracle'; got {partition!r}"
    )


def _attest_core(
    scan_id: UUID,
    runner: ScanRunner,
    *,
    s_version: str,
    env_digest: str,
    provenance_appender: VerdictProvenanceAppender | None,
) -> AttestationVerdict:
    """Core pipeline: two fresh F runs, EXACT byte-compare of the core Run."""
    log_1 = runner.run(scan_id)
    log_2 = runner.run(scan_id)

    blob_1 = log_1.runs[0].canonical_bytes  # runs[0] == core partition (DOC-SARIF §4)
    blob_2 = log_2.runs[0].canonical_bytes

    # The verdict-driving comparison is EXACT byte equality. NEVER a tolerance,
    # a similarity score, or a hash-prefix compare (a 1-byte change must fail).
    if blob_1 == blob_2:
        result: Result = "pass"
        diff_summary: str | None = None
    else:
        result = "fail"
        diff_summary = _diff_summary(blob_1, blob_2)

    attestor_hash = bytes.fromhex(log_1.runs[0].sarif_hash)
    signed_chain_id = _maybe_append(
        provenance_appender,
        scan_id=scan_id,
        partition="core",
        result=result,
        attestor_hash=attestor_hash,
    )
    return AttestationVerdict(
        scan_id=scan_id,
        partition="core",
        result=result,
        attestor_hash=attestor_hash,
        reproduction_rate=None,  # NULL on the core partition (DOC §3.4)
        s_version=s_version,
        env_digest=env_digest,
        signed_chain_id=signed_chain_id,
        diff_summary=diff_summary,
    )


def _attest_oracle(
    scan_id: UUID,
    runner: ScanRunner,
    *,
    s_version: str,
    env_digest: str,
    provenance_appender: VerdictProvenanceAppender | None,
) -> AttestationVerdict:
    """Oracle pipeline: measured reproduction rate; result is ALWAYS 'rate-only'."""
    log_1 = runner.run(scan_id)
    log_2 = runner.run(scan_id)

    rate = _oracle_reproduction_rate(log_1, log_2)
    # result is EXACTLY "rate-only" — never "pass"/"fail" on rate alone, even at
    # rate 1.0. The verdict asserts a measured number, NEVER property (a).
    attestor_hash = bytes.fromhex(log_1.runs[1].sarif_hash)
    signed_chain_id = _maybe_append(
        provenance_appender,
        scan_id=scan_id,
        partition="oracle",
        result="rate-only",
        attestor_hash=attestor_hash,
    )
    return AttestationVerdict(
        scan_id=scan_id,
        partition="oracle",
        result="rate-only",
        attestor_hash=attestor_hash,
        reproduction_rate=rate,
        s_version=s_version,
        env_digest=env_digest,
        signed_chain_id=signed_chain_id,
        diff_summary=None,
    )


def _maybe_append(
    appender: VerdictProvenanceAppender | None,
    *,
    scan_id: UUID,
    partition: Partition,
    result: Result,
    attestor_hash: bytes,
) -> UUID | None:
    """Append the verdict to the signed chain iff an appender was injected."""
    if appender is None:
        return None
    return appender.append_attestation(
        scan_id=scan_id,
        partition=partition,
        result=result,
        attestor_hash=attestor_hash,
    )


__all__ = [
    "LLM_TRIAGE_ENV",
    "AttestationVerdict",
    "AttestorConfigurationError",
    "Partition",
    "Result",
    "ScanRunner",
    "VerdictProvenanceAppender",
    "attest_scan",
    "fail_closed_scan_runner",
]
