"""CMP-TRI-01 — LLM triage ranking: pure scorer + flag-gated cycle orchestrator.

Two layers (DOC-CMP-TRI-01 §3):

* :func:`triage_finding` — the **pure** scorer. Given a :class:`TriageInput`
  (a column-restricted :class:`FindingView` + a bounded code window + a bounded
  SARIF excerpt) and an injected :class:`LLMClient`, it returns a
  :class:`TriageScore`. It performs no I/O beyond the injected LLM call and never
  touches ``findings``.

* :func:`run_triage_cycle` — the flag-gated orchestrator a worker invokes per
  SQS message. With ``LLM_TRIAGE=off`` (the production default) it short-circuits
  **before** any LLM call: no ``triage_scores`` row is written and no LLM call is
  made (``TST-AC-TRI-01a``). With the flag on, for each finding it reads the
  column-restricted projection, calls the scorer, and INSERTs exactly one
  ``triage_scores`` row through the injected write surface — and nothing else
  (``TST-AC-TRI-01b``, ``TST-INV-1-TRI-01``, ``TST-INV-3-TRI-01``).

INV-3 discharge in application code (defence-in-depth above the DB grant fence):

* The findings read surface (:class:`FindingsReadSurface`) exposes **only** the
  ``GRANT SELECT (id, class, rule_id, severity, physical_location, message)``
  projection and offers **no** mutate / delete method at all — modelling
  ``REVOKE ALL ON findings FROM scanipy_triage``.
* The triage write surface (:class:`TriageScoresWriteSurface`) accepts inserts
  into ``triage_scores`` only, and :func:`_assert_allowed_columns` rejects any
  write whose column set is not a subset of :data:`ALLOWED_TRIAGE_COLUMNS`.

The DB-grant-level proof (a real ``scanipy_triage`` role that fails an UPDATE /
DELETE on ``findings`` with a Postgres permission error) is the integration
surface (DOC-CMP-TRI-01 §9, ``AC-TRI-01b``); this module is its application-layer
mirror so the unit specs verify the same contract one layer up.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID


def _truncate_utf8(text: str, max_bytes: int) -> str:
    """Truncate ``text`` to at most ``max_bytes`` UTF-8 bytes on a char boundary.

    Slicing a ``str`` by a *byte* budget directly (``text[:n]``) counts
    characters, not bytes, so a multibyte window could exceed the budget. Encode,
    cut on the byte budget, then drop any partial trailing char on decode.
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


# LLM provider pin (CLAR-DEPLOY-14 RESOLVED 2026-05-23). Recorded verbatim as
# ``model_id`` on every ``triage_scores`` row for the INV-3 audit trail.
MODEL_ID = "claude-sonnet-4-6"

# Bound on the source-code window handed to the LLM prompt. Not constrained by
# any AC (DOC-CMP-TRI-01 §10 — CLAR-PARAM-04 explicit non-action); this is an
# Anthropic prompt-caching cost / latency tradeoff, documented in the PR. The
# worker truncates the window to this many bytes before building the prompt.
DEFAULT_CODE_WINDOW_BYTE_BUDGET = 4096

# Hard bound on the LLM ``free_text`` rationale persisted into the bounded
# ``triage_reason`` JSON payload (DOC-CMP-TRI-01 §4.2 / §7: adversarial-LLM
# output must be length-bounded before persistence, never written unbounded).
MAX_FREE_TEXT_BYTES = 2048

Severity = Literal["info", "low", "medium", "high", "critical"]

# The exact column set CMP-TRI-01 may write — and only into ``triage_scores``.
# Mirrors DOC-CMP-TRI-01 §3.1 / the ``scanipy_triage`` INSERT grant in
# DOC-DB §4.14. ``run_triage_cycle`` asserts every write's keys are a subset of
# this set, and that the target table is ``triage_scores`` (never ``findings``,
# ``provenance_records``, ``spec_versions`` or ``proposed_specs``).
ALLOWED_TRIAGE_COLUMNS: frozenset[str] = frozenset(
    {
        "finding_id",
        "triage_score",
        "triage_reason",
        "model_id",
        "model_version",
        "S_version",
        "env_digest",
    }
)

# The one and only table CMP-TRI-01 writes to.
TRIAGE_SCORES_TABLE = "triage_scores"


class TriageWriteSurfaceViolation(Exception):  # noqa: N818 — domain "Violation" name, per InvariantViolation (DOC-CMP-FND-03 §7.1) precedent
    """Raised when a triage write would escape the ``triage_scores`` surface.

    This is the application-layer mirror of the Postgres permission error the
    ``scanipy_triage`` role would raise (DOC-CMP-TRI-01 §7). It fires if a write
    targets a table other than ``triage_scores`` or carries a column outside
    :data:`ALLOWED_TRIAGE_COLUMNS` — an INV-3 / INV-1 violation caught before any
    bytes leave the worker.
    """


@dataclass(frozen=True)
class FindingView:
    """Read-only projection of a ``findings`` row, scoped to the columns
    CMP-TRI-01 may ``SELECT``.

    Matches the grant in DOC-DB §4.14::

        GRANT SELECT (id, class, rule_id, severity, physical_location, message)
          ON findings TO scanipy_triage;

    Deliberately carries **no** ``origin`` / ``S_version`` / ``env_digest`` /
    ``slice_fingerprint`` / ``status`` / detection-content attribute: the triage
    role cannot see, let alone mutate, those columns.
    """

    id: UUID
    # ``class`` is reserved in Python; the SQL column is ``"class"``.
    class_: str
    rule_id: str
    severity: Severity
    physical_location: dict[str, object]  # uri, start_line, end_line (jsonb)
    message: str


@dataclass(frozen=True)
class TriageInput:
    """The bounded payload handed to :func:`triage_finding`.

    ``S_version`` / ``env_digest`` are propagated **read-only** from the source
    ``findings`` row purely so they can be stamped onto the ``triage_scores`` row
    (its own INV-2 witness of the scan context the LLM ran in). They are never
    written back to ``findings`` (DOC-CMP-TRI-01 §5.2).
    """

    finding: FindingView
    code_window: str  # bounded; truncated to the byte budget by the cycle
    sarif_excerpt: str  # bounded; just the result region of the SARIF blob
    S_version: str
    env_digest: str


@dataclass(frozen=True)
class LLMTriageVerdict:
    """Structured response from the injected LLM collaborator.

    The three probabilities are the verbatim ``SDD §9 CMP-TRI-01 Purpose`` triple
    ``(likely_exploitable, likely_test_code, likely_fp)``; ``free_text`` is a
    bounded natural-language rationale. ``model_version`` is the API-reported
    version stamp recorded for the INV-3 audit trail.
    """

    likely_exploitable: float
    likely_test_code: float
    likely_fp: float
    free_text: str
    model_version: str


@dataclass(frozen=True)
class TriageScore:
    """The single ``triage_scores`` row CMP-TRI-01 writes per finding / model.

    Every field here is a column in :data:`ALLOWED_TRIAGE_COLUMNS`; the row is
    written to ``triage_scores`` and nowhere else.
    """

    finding_id: UUID
    triage_score: Decimal  # numeric(5,4) in [0, 1]
    triage_reason: str  # bounded JSON-encoded payload
    model_id: str  # 'claude-sonnet-4-6' (CLAR-DEPLOY-14)
    model_version: str  # API-reported version stamp
    S_version: str  # stamped onto the triage_scores row (INV-2 — for this row)
    env_digest: str  # stamped onto the triage_scores row (INV-2 — for this row)

    def as_row(self) -> dict[str, object]:
        """Render the row as a column→value mapping for the write surface.

        The key set is exactly :data:`ALLOWED_TRIAGE_COLUMNS`, which
        :func:`run_triage_cycle` asserts before the insert.
        """
        return {
            "finding_id": self.finding_id,
            "triage_score": self.triage_score,
            "triage_reason": self.triage_reason,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "S_version": self.S_version,
            "env_digest": self.env_digest,
        }


@runtime_checkable
class LLMClient(Protocol):
    """Injected Anthropic-API-shaped triage collaborator (DOC-CMP-TRI-01 §3.2).

    The LLM is **never** invoked inline on the detection path; it is a post-hoc
    ranker. Tests wire an in-memory fake (no real Anthropic call); production
    wires a client that routes through the ``CMP-CP-01`` per-tenant-quota proxy.
    Its output is *not* required to be reproducible — the Attestor runs with
    ``LLM_TRIAGE=off`` so core byte-identity is independent of triage drift.
    """

    def score(self, inp: TriageInput) -> LLMTriageVerdict: ...


@runtime_checkable
class FindingsReadSurface(Protocol):
    """Column-restricted, read-only view over ``findings`` for the triage role.

    Exposes **only** the ``GRANT SELECT (id, class, rule_id, severity,
    physical_location, message)`` projection as :class:`FindingView`, and offers
    **no** mutate / delete method — the structural mirror of
    ``REVOKE ALL ON findings FROM scanipy_triage`` (DOC-DB §4.14). A worker
    therefore *cannot* express a write to ``findings`` through this surface; the
    contract is enforced by the type, not by discipline.
    """

    def list_for_scan(self, scan_id: UUID) -> list[FindingView]: ...

    def context_for(self, finding_id: UUID) -> tuple[str, str]:
        """Return ``(code_window, sarif_excerpt)`` for the finding.

        The worker sources the bounded code window from the snapshot artifact
        (S3) and the SARIF excerpt from the result region of the SARIF blob.
        """
        ...

    def scan_inv2_params(self, scan_id: UUID) -> tuple[str, str]:
        """Return ``(S_version, env_digest)`` propagated read-only from the scan.

        These stamp the ``triage_scores`` row's own INV-2 fields; they are never
        written back to ``findings``.
        """
        ...


@runtime_checkable
class TriageScoresWriteSurface(Protocol):
    """Insert-only write surface for ``triage_scores`` (DOC-DB §4.14 grant).

    The only method is ``insert``; there is no UPDATE / DELETE and no other
    target table — the structural mirror of
    ``GRANT INSERT ON triage_scores TO scanipy_triage``.
    """

    def insert(self, table: str, row: dict[str, object]) -> None: ...


def _validate_unit_interval(name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be in [0, 1]; got {value!r}")


def triage_finding(inp: TriageInput, llm: LLMClient) -> TriageScore:
    """Score a single finding via the injected LLM and build its triage row.

    Pure with respect to ``findings``: it calls ``llm.score`` and returns a
    :class:`TriageScore`. It performs **no** write to ``findings`` and produces
    nothing outside the :data:`ALLOWED_TRIAGE_COLUMNS` surface.

    The headline ``triage_score`` is the LLM's ``likely_exploitable`` probability
    (the prioritisation signal a human triager sorts on); the full
    ``(likely_exploitable, likely_test_code, likely_fp, free_text)`` payload is
    JSON-encoded into ``triage_reason`` per ``SDD §9 CMP-TRI-01 Purpose``.
    """
    verdict = llm.score(inp)
    for name, value in (
        ("likely_exploitable", verdict.likely_exploitable),
        ("likely_test_code", verdict.likely_test_code),
        ("likely_fp", verdict.likely_fp),
    ):
        _validate_unit_interval(name, value)

    reason = _encode_reason(verdict)
    # numeric(5,4): four-place fixed-point in [0, 1].
    score = Decimal(str(verdict.likely_exploitable)).quantize(Decimal("0.0001"))
    return TriageScore(
        finding_id=inp.finding.id,
        triage_score=score,
        triage_reason=reason,
        model_id=MODEL_ID,
        model_version=verdict.model_version,
        S_version=inp.S_version,
        env_digest=inp.env_digest,
    )


def _encode_reason(verdict: LLMTriageVerdict) -> str:
    """JSON-encode the bounded triage_reason payload (DOC-CMP-TRI-01 §4.2).

    ``free_text`` is length-bounded to :data:`MAX_FREE_TEXT_BYTES` before
    encoding so an adversarial / runaway LLM rationale cannot write an unbounded
    payload (DOC §7).
    """
    return json.dumps(
        {
            "likely_exploitable": verdict.likely_exploitable,
            "likely_test_code": verdict.likely_test_code,
            "likely_fp": verdict.likely_fp,
            "free_text": _truncate_utf8(verdict.free_text, MAX_FREE_TEXT_BYTES),
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _assert_allowed_columns(table: str, row: dict[str, object]) -> None:
    """Fail closed unless the write is the ``triage_scores`` allowed surface.

    The application-layer mirror of the ``scanipy_triage`` grant: any target
    other than ``triage_scores`` or any column outside
    :data:`ALLOWED_TRIAGE_COLUMNS` is an INV-3 / INV-1 violation.
    """
    if table != TRIAGE_SCORES_TABLE:
        raise TriageWriteSurfaceViolation(
            f"triage may only write {TRIAGE_SCORES_TABLE!r}; refused write to {table!r}"
        )
    extra = set(row) - ALLOWED_TRIAGE_COLUMNS
    if extra:
        raise TriageWriteSurfaceViolation(
            f"triage write to {table!r} carries disallowed columns {sorted(extra)!r}; "
            f"allowed = {sorted(ALLOWED_TRIAGE_COLUMNS)!r}"
        )


@dataclass
class TriageCycleResult:
    """Summary of one :func:`run_triage_cycle` invocation (for the caller / test).

    ``rows_written`` is the number of ``triage_scores`` rows inserted (0 when the
    flag is off); ``llm_calls`` is the number of LLM invocations (0 when the flag
    is off — ``TST-AC-TRI-01a``).
    """

    rows_written: int = 0
    llm_calls: int = 0
    written_finding_ids: list[UUID] = field(default_factory=list)


def run_triage_cycle(
    scan_id: UUID,
    *,
    llm_triage: bool,
    findings: FindingsReadSurface,
    triage_store: TriageScoresWriteSurface,
    llm: LLMClient,
    code_window_byte_budget: int = DEFAULT_CODE_WINDOW_BYTE_BUDGET,
) -> TriageCycleResult:
    """Flag-gated triage orchestrator for one scan's findings.

    With ``llm_triage`` **False** (the production default, ``LLM_TRIAGE=off``)
    this is a no-op: it returns immediately **without** reading findings, calling
    the LLM, or writing any row (``TST-AC-TRI-01a`` — mechanism (b)).

    With ``llm_triage`` **True**, for each finding in the scan it reads the
    column-restricted projection + bounded context, scores it via
    :func:`triage_finding`, and INSERTs exactly one ``triage_scores`` row through
    the injected write surface. Every write passes :func:`_assert_allowed_columns`
    and targets ``triage_scores`` only; ``findings`` is never written, deleted, or
    mutated, and no row ever targets ``provenance_records`` / ``spec_versions`` /
    ``proposed_specs`` (``TST-AC-TRI-01b``, ``TST-INV-1-TRI-01``,
    ``TST-INV-3-TRI-01``). Ranking is strictly additive: a low / high score never
    removes a finding from any output stream.
    """
    result = TriageCycleResult()
    if not llm_triage:
        # Default-OFF short-circuit: no read, no LLM call, no write. The finding
        # rows' detection content is independent of triage in this canonical
        # configuration (DOC-CMP-TRI-01 §5 mechanism (b)).
        return result

    s_version, env_digest = findings.scan_inv2_params(scan_id)
    for view in findings.list_for_scan(scan_id):
        code_window, sarif_excerpt = findings.context_for(view.id)
        inp = TriageInput(
            finding=view,
            code_window=_truncate_utf8(code_window, code_window_byte_budget),
            sarif_excerpt=sarif_excerpt,
            S_version=s_version,
            env_digest=env_digest,
        )
        score = triage_finding(inp, llm)
        result.llm_calls += 1

        row = score.as_row()
        # Fail-closed application-layer mirror of the scanipy_triage grant.
        _assert_allowed_columns(TRIAGE_SCORES_TABLE, row)
        triage_store.insert(TRIAGE_SCORES_TABLE, row)
        result.rows_written += 1
        result.written_finding_ids.append(view.id)

    return result


__all__ = [
    "ALLOWED_TRIAGE_COLUMNS",
    "DEFAULT_CODE_WINDOW_BYTE_BUDGET",
    "MODEL_ID",
    "TRIAGE_SCORES_TABLE",
    "FindingView",
    "FindingsReadSurface",
    "LLMClient",
    "LLMTriageVerdict",
    "TriageCycleResult",
    "TriageInput",
    "TriageScore",
    "TriageScoresWriteSurface",
    "TriageWriteSurfaceViolation",
    "run_triage_cycle",
    "triage_finding",
]
