"""Semgrep oracle ``ScanRunner`` adapter — makes CMP-CP-05 demonstrable on the
ORACLE partition (Tier-2 Track C).

WHAT THIS IS. ``services.scan.attestor.attest_scan`` consumes ``F`` through the
typed :class:`~services.scan.attestor.ScanRunner` port, whose production default
(``fail_closed_scan_runner``) raises: the Attestor has therefore only ever been
exercised against in-memory doubles (``tests/cp05_fakes.py``). This module ships
a REAL ``ScanRunner``-shaped adapter for the oracle partition: it invokes the
Semgrep binary over a source checkout with the repo's shipped ruleset
(``deploy/rules/``), projects the results onto CMP-FND-01 worker findings, and
emits the canonical two-Run SARIF log through the real
:func:`analysis.sarif.canonical_emit.normalize`. Calling it twice is exactly what
``attest_scan(..., partition="oracle")`` does, which yields a MEASURED
``reproduction_rate`` over real Semgrep output.

THE HONEST PARTITION IS NOT NEGOTIABLE HERE (``.claude/rules/05-determinism.md``
"Attestor pipeline contract"; DOC-PARTITION §6):

  * Every finding this adapter produces carries ``origin="oracle-passthrough"``
    and ``engine="semgrep"`` (INV-1). It never emits into the core partition, so
    ``SARIFLog.runs[0]`` (core) is always an EMPTY Run.
  * :func:`attest_oracle_scan` pins ``partition="oracle"``. Semgrep output must
    NEVER be fed to the core byte-identical pipeline: a "pass" verdict over
    oracle findings would assert property (a) — the determinism theorem — over a
    partition it does not cover. The oracle verdict is EXACTLY ``"rate-only"``,
    even at ``reproduction_rate == 1.0``. A perfectly reproducing Semgrep run is
    a measured number, not a theorem.

BLOCKING INTEGRATION CONSTRAINT — provenance fields with no oracle-path source.
  ``canonical_emit._validate_finding`` requires, non-empty, on EVERY finding
  (core and oracle alike): ``cpg_order_hash`` (INV-5), ``precondition_status``,
  and ``class_``. None of the three has a legitimate value on a Semgrep-only
  scan:

    | field                 | legitimate producer                | on this path |
    |-----------------------|------------------------------------|--------------|
    | ``cpg_order_hash``    | CMP-CORE-03 ``canonical_order(cpg)``| no CPG built |
    | ``precondition_status``| CMP-SNAP-03 ``CW-DETECT``          | never runs   |
    | ``class_``            | detector spec / CLAR-ORCH-03 (OPEN)| unmapped     |

  The shipped self-host oracle service (``deploy/scanipy_oracle/app.py``) sides
  with honesty by simply NOT HAVING a ``cpg_order_hash`` column — its ``oracle``
  schema is deliberately separate from the tenanted ``findings`` table. That
  omission and FND-01's NOT-NULL requirement are in direct tension, and this
  adapter cannot resolve it: fabricating a sha256 (of the source tree, of the
  ruleset, of anything) would mint a value that LOOKS like a CMP-CORE-03
  canonical-order digest and is not one — precisely the INV-5 lie the invariant
  exists to prevent.

  RESOLUTION TAKEN HERE: all three are REQUIRED, caller-supplied inputs on
  :class:`OracleScanProvenance`, validated on construction. A deployment with no
  CPG cannot supply ``cpg_order_hash`` and gets a typed
  :class:`OracleProvenanceUnavailable` naming the missing producer — fail-closed,
  never a silent default. Surfaced as text for the orchestrator to file a CLAR
  (an implementation agent cannot edit ``WBS.md §17``); it extends the existing
  CLAR-CP-05-03 interface-shape list and touches the OPEN CLAR-ORCH-03 (oracle
  ``class_`` sourcing).

  ``fingerprint_class`` is NOT caller-supplied: it is pinned to ``"weak"`` on
  every finding here, matching the shipped oracle service's precedent ("a
  same-source content id, never a canonical-CPG claim"). Threading a ``"strong"``
  class through from some ``canonical_order`` result would assert INV-5
  canonicality over a Semgrep content hash. ``"weak"`` is the only honest class
  for a finding with no slice witness through a CPG.

DETERMINISM NOTE. This adapter is NOT claimed to be deterministic — that is the
whole point of measuring a rate. Its own projection is a pure function of the
Semgrep JSON, so any measured instability comes from Semgrep/the environment,
not from the mapping layer.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable
from uuid import UUID

from analysis.sarif.canonical_emit import normalize
from services.scan.attestor import (
    AttestationVerdict,
    VerdictProvenanceAppender,
    attest_scan,
)

if TYPE_CHECKING:
    from analysis.sarif.canonical_emit import (
        Origin,
        PreconditionStatus,
        SARIFLog,
        WorkerFinding,
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Every finding this adapter emits (INV-1). Never ``deterministic-core``.
ORACLE_ORIGIN: Final[str] = "oracle-passthrough"
#: The oracle engine (``.claude/rules/05-determinism.md`` "How origin is set").
SEMGREP_ENGINE: Final[str] = "semgrep"
#: INV-5: a Semgrep content id is never a canonical-CPG claim (see module docstring).
ORACLE_FINGERPRINT_CLASS: Final[str] = "weak"

#: Semgrep severity -> Scanipy severity band. Byte-identical to the mapping the
#: shipped self-host oracle service uses (``deploy/scanipy_oracle/app.py``
#: ``_SEV_BAND``) so the two surfaces cannot drift apart. An unrecognised
#: severity is a FAILURE, never a silent default (see :func:`_map_severity`).
_SEVERITY_BAND: Final[dict[str, str]] = {
    "ERROR": "critical",
    "WARNING": "medium",
    "INFO": "low",
}

#: Argv flags mandated for the invocation. ``--no-git-ignore`` scans the whole
#: checkout, ``--metrics=off`` / ``--disable-version-check`` keep the run offline
#: and side-effect free (a version-check HTTP call would be a nondeterminism and
#: privacy source in an attestation run).
_SEMGREP_FLAGS: Final[tuple[str, ...]] = (
    "--json",
    "--quiet",
    "--no-git-ignore",
    "--metrics=off",
    "--disable-version-check",
)

#: Semgrep exits 0 (no findings) or 1 (findings found) on a SUCCESSFUL scan;
#: >= 2 is a genuine error. "findings exist" must never be read as a failure.
_SEMGREP_OK_RETURNCODES: Final[frozenset[int]] = frozenset({0, 1})

_DEFAULT_TIMEOUT_S: Final[int] = 600


# ---------------------------------------------------------------------------
# Error contracts
# ---------------------------------------------------------------------------


class OracleProvenanceUnavailable(Exception):  # noqa: N818  (a constraint, not an error state)
    """A provenance field required by CMP-FND-01 has no oracle-path producer.

    Raised (fail-closed) when the caller cannot supply ``cpg_order_hash``,
    ``precondition_status``, or the ``class_`` for a matched rule. This is the
    BLOCKING INTEGRATION CONSTRAINT documented in the module docstring — a real
    finding about the pipeline, not a transient failure. The adapter refuses to
    invent a value that would read as a CMP-CORE-03 / CW-DETECT output.
    """


class SemgrepInvocationError(Exception):
    """The Semgrep subprocess crashed, timed out, or emitted unparseable output.

    Explicitly NOT raised when Semgrep exits non-zero because it FOUND findings
    (exit 1): that is the normal success path for a scan that detects something.
    """


# ---------------------------------------------------------------------------
# Caller-supplied provenance bundle (the blocking-constraint boundary)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OracleScanProvenance:
    """The provenance every emitted finding must carry (INV-2 / INV-5, RULE-6).

    Every field here is supplied by the CALLER because none of them can be
    derived from a Semgrep run. Construction validates them; an absent or
    malformed value raises :class:`OracleProvenanceUnavailable` naming the
    component that legitimately produces it.

    ``rule_classes`` maps a Semgrep ``check_id`` to its Scanipy vulnerability
    class. There is no shipped rule -> class table (oracle ``class_`` sourcing is
    the OPEN CLAR-ORCH-03), so an unmapped matched rule fails closed rather than
    being labelled by guesswork.

    ``llm_triage_flag`` is a factual record of the run, so it is required rather
    than defaulted: defaulting it to ``False`` would assert that triage was off
    without checking. The oracle pipeline does not REQUIRE it off (only the core
    pipeline does, INV-3), it merely records it.
    """

    snapshot_id: UUID
    codebase_id: UUID
    commit_sha: str
    #: INV-2 provenance field name (capital S is normative; DOC-SARIF §5/§6).
    S_version: str
    env_digest: str
    #: CMP-CORE-03 ``canonical_order(cpg).cpg_order_hash.hex()`` — 64 hex chars.
    cpg_order_hash: str
    #: CMP-SNAP-03 CW-DETECT verdict for the snapshot under scan.
    precondition_status: PreconditionStatus
    #: Semgrep ``check_id`` -> Scanipy class. Unmapped matched rule => fail-closed.
    rule_classes: dict[str, str]
    llm_triage_flag: bool

    def __post_init__(self) -> None:
        for field_name in ("commit_sha", "S_version", "env_digest"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise OracleProvenanceUnavailable(
                    f"{field_name} is required and must be a non-empty string (INV-2); "
                    f"got {value!r}. It is threaded from the scan submission "
                    f"(CMP-ORCH-01) / the pinned worker image digest (CMP-SNAP-01)."
                )
        # INV-5: the hash must be a real CMP-CORE-03 digest. We cannot verify its
        # provenance, but we CAN refuse anything that is not shaped like one, and
        # we never supply one ourselves.
        if not _is_sha256_hex(self.cpg_order_hash):
            raise OracleProvenanceUnavailable(
                f"cpg_order_hash must be 64 lowercase hex chars (INV-5); got "
                f"{self.cpg_order_hash!r}. Its ONLY legitimate producer is "
                f"CMP-CORE-03 canonical_order(cpg) over a CPG of this same "
                f"checkout. A Semgrep-only scan builds no CPG, so on a CPG-less "
                f"deployment this value does not exist and no oracle SARIF can be "
                f"emitted through CMP-FND-01 (which requires it NOT NULL on every "
                f"finding, oracle included). This is a reported integration "
                f"constraint: do NOT substitute a hash of the source tree, the "
                f"ruleset, or the findings — that would forge an INV-5 canonical-"
                f"order digest."
            )
        if self.precondition_status not in ("closed-world", "degraded", "full-reparse"):
            raise OracleProvenanceUnavailable(
                f"precondition_status must be one of "
                f"('closed-world', 'degraded', 'full-reparse'); got "
                f"{self.precondition_status!r}. Its only legitimate producer is the "
                f"CMP-SNAP-03 CW-DETECT verdict for this snapshot, which does not "
                f"run on a Semgrep-only scan."
            )

    def class_for(self, check_id: str) -> str:
        """The Scanipy class for ``check_id``; fail-closed when unmapped."""
        try:
            return self.rule_classes[check_id]
        except KeyError:
            raise OracleProvenanceUnavailable(
                f"Semgrep rule {check_id!r} matched but has no Scanipy class in "
                f"rule_classes. Oracle class sourcing is the OPEN CLAR-ORCH-03; "
                f"there is no shipped rule -> class table, so the class is a "
                f"required caller input rather than a guess from the rule id."
            ) from None


def _is_sha256_hex(value: object) -> bool:
    """True iff ``value`` is exactly 64 lowercase hex characters."""
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(c in "0123456789abcdef" for c in value)


# ---------------------------------------------------------------------------
# The emitted finding record
# ---------------------------------------------------------------------------


@dataclass(eq=False)
class OracleFinding:
    """One Semgrep match as a CMP-FND-01 :class:`WorkerFinding`.

    Declared here rather than importing FND-01's private concrete ``_Finding``,
    following the convention ``services.scan.attestor`` states explicitly for
    this boundary ("inlined here rather than reaching across FND-01's
    module-privacy boundary"). Structural typing does the rest: ``normalize``
    accepts any object exposing the Protocol's attributes.

    ``eq=False`` matches ``services.scan.worker.Finding`` exactly: the
    ``WorkerFinding`` Protocol declares settable attributes, so a ``frozen=True``
    record does NOT satisfy it (its attributes are read-only), and identity
    hashing is what makes a ``set``/``frozenset`` of findings well-formed. The
    same convention gives this module the same conformance check
    (:func:`_oracle_finding_is_workerfinding`).
    """

    origin: Origin
    determinism_partition: Origin
    engine: str
    S_version: str  # normative INV-2 field name (capital S; DOC-SARIF §5/§6)
    env_digest: str
    cpg_order_hash: str
    fingerprint_class: str
    slice_fingerprint: str
    rule_id: str
    message: str
    uri: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int
    severity: str
    class_: str
    status: str
    precondition_status: str
    witness_blob_uri: str | None = None
    spec_provenance: str | None = None


def _oracle_finding_is_workerfinding(f: OracleFinding) -> WorkerFinding:
    """Compile-time assertion that :class:`OracleFinding` satisfies the FND-01
    input Protocol (mirrors ``worker._finding_is_workerfinding``). If a field is
    renamed or a type drifts, mypy fails HERE rather than at the emitter."""
    return f


# ---------------------------------------------------------------------------
# The Semgrep invocation seam
# ---------------------------------------------------------------------------


@runtime_checkable
class SemgrepInvoker(Protocol):
    """Port that returns ONE Semgrep JSON report for ``source_dir``.

    Isolated as a port so the mapping/emission/attestation chain is testable
    without the Semgrep binary (which is absent from hermetic CI, exactly as
    CLAR-PROC-01 condition (2) anticipates for every oracle adapter).
    """

    def invoke(self, source_dir: Path) -> object: ...


@dataclass(frozen=True)
class SubprocessSemgrepInvoker:
    """The real invoker: runs the Semgrep binary as an argv list, no shell.

    ``semgrep_bin`` is resolved to an ABSOLUTE path at construction (``which``),
    so the invocation cannot be redirected by a mutated ``PATH`` mid-run and
    cannot be mis-read as a shell string.

    Exit-code handling (the trap this class exists to get right): Semgrep exits
    **1 when it finds findings** — a successful scan, not a failure. Only exit
    codes outside :data:`_SEMGREP_OK_RETURNCODES`, a timeout, a missing binary,
    or stdout that will not parse as JSON are surfaced as
    :class:`SemgrepInvocationError`.
    """

    rules_dir: Path
    semgrep_bin: str
    timeout_s: int = _DEFAULT_TIMEOUT_S

    @classmethod
    def create(
        cls,
        rules_dir: Path,
        *,
        semgrep_bin: str | None = None,
        timeout_s: int = _DEFAULT_TIMEOUT_S,
    ) -> SubprocessSemgrepInvoker:
        """Resolve the Semgrep binary to an absolute path or fail closed."""
        candidate = semgrep_bin or os.environ.get("SEMGREP_BIN") or "semgrep"
        resolved = shutil.which(candidate)
        if resolved is None:
            raise SemgrepInvocationError(
                f"semgrep binary {candidate!r} not found on PATH; the oracle "
                f"adapter never falls back to a partial path or a shell lookup."
            )
        if not rules_dir.is_dir():
            raise SemgrepInvocationError(f"ruleset directory {str(rules_dir)!r} does not exist")
        return cls(rules_dir=rules_dir.resolve(), semgrep_bin=resolved, timeout_s=timeout_s)

    def invoke(self, source_dir: Path) -> object:
        argv = [
            self.semgrep_bin,
            "scan",
            "--config",
            str(self.rules_dir),
            *_SEMGREP_FLAGS,
            str(source_dir),
        ]
        try:
            # argv list + absolute binary + no shell (S603 is project-wide ignored).
            proc = subprocess.run(
                argv,
                capture_output=True,
                timeout=self.timeout_s,
                check=False,
                env={**os.environ, "SEMGREP_SEND_METRICS": "off"},
            )
        except subprocess.TimeoutExpired as exc:
            raise SemgrepInvocationError(
                f"semgrep timed out after {self.timeout_s}s over {str(source_dir)!r}"
            ) from exc
        except OSError as exc:
            raise SemgrepInvocationError(f"semgrep could not be executed: {exc}") from exc

        stderr_tail = proc.stderr.decode(errors="replace")[-1000:]
        try:
            report: object = json.loads(proc.stdout)
        except ValueError as exc:
            # A genuine crash: unparseable stdout. Report the exit code AND the
            # stderr tail so the failure is diagnosable rather than swallowed.
            raise SemgrepInvocationError(
                f"semgrep produced no parseable JSON (exit {proc.returncode}): {stderr_tail}"
            ) from exc
        if proc.returncode not in _SEMGREP_OK_RETURNCODES:
            # Parseable output but a hard error exit. Exit 1 is NOT here: it means
            # "findings were found", which is a successful scan.
            raise SemgrepInvocationError(
                f"semgrep exited {proc.returncode} (a scan error; exit 0/1 are the "
                f"success codes, 1 meaning findings were found): {stderr_tail}"
            )
        return report


# ---------------------------------------------------------------------------
# Semgrep report -> worker findings
# ---------------------------------------------------------------------------


def _require_mapping(value: object, where: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise SemgrepInvocationError(
            f"semgrep report: {where} is not an object (got {type(value)})"
        )
    return {str(k): v for k, v in value.items()}


def _require_int(value: object, where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise SemgrepInvocationError(f"semgrep report: {where} is not an int (got {value!r})")
    return value


def _require_str(value: object, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise SemgrepInvocationError(
            f"semgrep report: {where} is not a non-empty string (got {value!r})"
        )
    return value


def _map_severity(raw: object, check_id: str) -> str:
    """Semgrep severity -> Scanipy band; unrecognised values fail closed.

    Defaulting an unknown severity (as a lenient UI adapter may) would silently
    mislabel a finding's risk, so an unexpected value is treated as unexpected
    output.
    """
    band = _SEVERITY_BAND.get(str(raw))
    if band is None:
        raise SemgrepInvocationError(
            f"semgrep rule {check_id!r} reported unrecognised severity {raw!r}; "
            f"expected one of {sorted(_SEVERITY_BAND)}"
        )
    return band


def _relative_uri(raw_path: str, source_dir: Path) -> str:
    """Path of the matched file relative to the scanned checkout root.

    Deterministic and machine-independent: an absolute host path in the SARIF
    would make the log vary with the working directory, which the reproduction
    rate would then read as instability that is not Semgrep's.
    """
    try:
        return Path(raw_path).resolve().relative_to(source_dir.resolve()).as_posix()
    except ValueError:
        return Path(raw_path).as_posix()


def _weak_slice_fingerprint(
    *, commit_sha: str, check_id: str, uri: str, start_line: int, start_col: int
) -> str:
    """A deterministic SAME-SOURCE content id for an oracle finding.

    NOT a CMP-CORE-02 Algorithm-3 slice fingerprint: an oracle finding has no
    slice witness through a CPG (see ``services.scan.worker``'s fail-closed
    ``SliceFingerprinter``). It is stable identity for the same finding at the
    same location in the same commit, and nothing more — which is exactly why
    every finding here carries ``fingerprint_class = "weak"``. It is never
    refactor-stable and must never be used to auto-suppress across a refactor.
    Same construction as the shipped ``deploy/scanipy_oracle/app.py``.
    """
    payload = f"{commit_sha}|{check_id}|{uri}|{start_line}|{start_col}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def map_semgrep_report(
    report: object,
    *,
    source_dir: Path,
    provenance: OracleScanProvenance,
) -> frozenset[WorkerFinding]:
    """Project a Semgrep JSON report onto CMP-FND-01 worker findings.

    PURE: a function of ``(report, source_dir, provenance)`` only. Every finding
    is stamped ``origin="oracle-passthrough"`` / ``engine="semgrep"`` (INV-1) and
    ``fingerprint_class="weak"`` (INV-5); the INV-2/INV-5 provenance is threaded
    verbatim from ``provenance`` and never re-derived here.

    Returns a ``frozenset`` because that is ``normalize``'s input type. The set
    is widened to ``frozenset[WorkerFinding]`` explicitly: ``frozenset`` is
    invariant, so a ``frozenset[OracleFinding]`` is not implicitly one of the
    Protocol (the same widening ``worker.emit_sarif`` performs).
    """
    doc = _require_mapping(report, "top level")
    raw_results = doc.get("results", [])
    if not isinstance(raw_results, list):
        raise SemgrepInvocationError("semgrep report: 'results' is not an array")

    findings: list[OracleFinding] = []
    for idx, raw in enumerate(raw_results):
        result = _require_mapping(raw, f"results[{idx}]")
        check_id = _require_str(result.get("check_id"), f"results[{idx}].check_id")
        extra = _require_mapping(result.get("extra", {}), f"results[{idx}].extra")
        start = _require_mapping(result.get("start", {}), f"results[{idx}].start")
        end = _require_mapping(result.get("end", {}), f"results[{idx}].end")
        uri = _relative_uri(_require_str(result.get("path"), f"results[{idx}].path"), source_dir)
        start_line = _require_int(start.get("line"), f"results[{idx}].start.line")
        start_col = _require_int(start.get("col"), f"results[{idx}].start.col")
        message = str(extra.get("message", "")).strip() or check_id

        findings.append(
            OracleFinding(
                # --- INV-1: this adapter emits into the oracle partition ONLY ---
                origin="oracle-passthrough",
                determinism_partition="oracle-passthrough",
                engine=SEMGREP_ENGINE,
                # --- INV-2: threaded verbatim from the caller ---
                S_version=provenance.S_version,
                env_digest=provenance.env_digest,
                # --- INV-5: caller-supplied CMP-CORE-03 hash; class pinned weak ---
                cpg_order_hash=provenance.cpg_order_hash,
                fingerprint_class=ORACLE_FINGERPRINT_CLASS,
                slice_fingerprint=_weak_slice_fingerprint(
                    commit_sha=provenance.commit_sha,
                    check_id=check_id,
                    uri=uri,
                    start_line=start_line,
                    start_col=start_col,
                ),
                # --- detection content, straight from the Semgrep match ---
                rule_id=check_id,
                message=message,
                uri=uri,
                start_line=start_line,
                start_col=start_col,
                end_line=_require_int(end.get("line"), f"results[{idx}].end.line"),
                end_col=_require_int(end.get("col"), f"results[{idx}].end.col"),
                severity=_map_severity(extra.get("severity"), check_id),
                class_=provenance.class_for(check_id),
                status="open",  # CMP-FND-02 schema default for a newly emitted finding
                precondition_status=provenance.precondition_status,
                witness_blob_uri=None,  # no witness blob: an oracle match has no slice
                spec_provenance=None,  # CMP-TRI-03 territory; not set at emission
            )
        )
    widened: frozenset[WorkerFinding] = frozenset(findings)
    return widened


# ---------------------------------------------------------------------------
# The ScanRunner adapter
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SemgrepOracleScanRunner:
    """A real ``F`` for the ORACLE partition: Semgrep over a checkout -> SARIFLog.

    Structurally satisfies :class:`services.scan.attestor.ScanRunner`
    (``run(scan_id) -> SARIFLog``), so ``attest_scan`` can invoke it twice. Each
    ``run`` is a FRESH Semgrep invocation — the adapter caches nothing, because a
    cached second run would manufacture a reproduction rate of 1.0 out of thin
    air rather than measuring one.

    ``runs[0]`` (the core partition) is always EMPTY: this adapter never emits a
    ``deterministic-core`` finding. Feeding it to the core pipeline would be a
    category error, which is why :func:`attest_oracle_scan` pins the partition.
    """

    source_dir: Path
    provenance: OracleScanProvenance
    invoker: SemgrepInvoker

    def run(self, scan_id: UUID) -> SARIFLog:
        """Run Semgrep once and emit the canonical two-Run SARIF log."""
        report = self.invoker.invoke(self.source_dir)
        findings = map_semgrep_report(
            report, source_dir=self.source_dir, provenance=self.provenance
        )
        return normalize(
            findings,
            scan_id=scan_id,
            snapshot_id=self.provenance.snapshot_id,
            codebase_id=self.provenance.codebase_id,
            commit_sha=self.provenance.commit_sha,
            S_version=self.provenance.S_version,
            env_digest=self.provenance.env_digest,
            precondition_status=self.provenance.precondition_status,
            llm_triage_flag=self.provenance.llm_triage_flag,
        )


def attest_oracle_scan(
    scan_id: UUID,
    runner: SemgrepOracleScanRunner,
    *,
    provenance_appender: VerdictProvenanceAppender | None = None,
) -> AttestationVerdict:
    """Attest a Semgrep oracle scan: two fresh runs -> a MEASURED reproduction rate.

    ``partition="oracle"`` is PINNED, not a parameter. There is no argument a
    caller could pass that would route Semgrep output through the core
    byte-identical pipeline, so no code path can produce a ``"pass"``/``"fail"``
    determinism verdict — and therefore a property-(a) claim — over
    ``oracle-passthrough`` findings. The returned verdict always has
    ``result == "rate-only"`` and a measured ``reproduction_rate``, including
    when that rate is exactly 1.0: a perfectly stable oracle run is evidence,
    never a theorem (``.claude/rules/05-determinism.md``).

    ``s_version`` / ``env_digest`` are read off the runner's own provenance so
    the verdict's INV-2 fields cannot drift from the ones stamped on the
    findings it attests.
    """
    return attest_scan(
        scan_id,
        "oracle",
        s_version=runner.provenance.S_version,
        env_digest=runner.provenance.env_digest,
        scan_runner=runner,
        provenance_appender=provenance_appender,
    )


__all__ = [
    "ORACLE_FINGERPRINT_CLASS",
    "ORACLE_ORIGIN",
    "SEMGREP_ENGINE",
    "OracleFinding",
    "OracleProvenanceUnavailable",
    "OracleScanProvenance",
    "SemgrepInvocationError",
    "SemgrepInvoker",
    "SemgrepOracleScanRunner",
    "SubprocessSemgrepInvoker",
    "attest_oracle_scan",
    "map_semgrep_report",
]
