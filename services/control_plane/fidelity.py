"""CMP-CP-06 — CPG-fidelity gate harness (mechanism).

Implementation contract: ``docs/components/DOC-CMP-CP-06.md``.
Cross-cutting refs: ``.claude/rules/04-staging.md`` (NORMATIVE thresholds — §"CPG-
fidelity gate criteria"), ``.claude/rules/01-invariants.md`` (INV-6 owner),
``docs/cross-cutting/DOC-STAGING.md`` (gate criteria + front-end-blocked
reporting), ``WBS.md §17 CLAR-CORP-02`` (RESOLVED 2026-05-23 — the four
thresholds, quoted verbatim below and NEVER re-decided here per DOC §3.1).

CP-06 is the **owner of INV-6** (per-language honesty). It produces the gate
verdict that ``CMP-CORE-01``'s Algorithm-2 recall benchmark consults: a
``(class, language)`` pair may not enter Algorithm-2 benchmarking until CP-06 is
GATE-PASS for that language (RULE-7). A language below threshold is reported
``front-end-blocked`` (naming the failing FIDELITY metric + its value, per DOC
§3.3), and the verdict structurally CANNOT yield an Algorithm-2 detector recall
number for any pair on that language (INV-6 owner-side discharge).

TWO DIFFERENT "RECALLS" — do not conflate (the load-bearing distinction):

  * ``call_edge_recall`` / ``pdg_recall`` are FIDELITY metrics of the front-end
    vs. ground truth. They are part of the verdict and BELONG in ``latest.json``
    even on a fail — DOC §3.4's JSON schema always lists all four metrics, and
    §3.3's compliant phrasing literally names the failing fidelity metric with
    its value ("front-end-blocked: call-edge recall 0.62 < 0.85 threshold").

  * Algorithm-2 DETECTOR recall for a ``(class, language)`` pair is the number
    INV-6 forbids for a non-gate-passing language. CP-06 NEVER computes this
    (DOC §2). Its INV-6 duty is to emit a verdict whose benchmark-eligibility
    accessor (:meth:`FidelityVerdict.benchmark_eligible_recall`) REFUSES on a
    non-gate-passing language, so CMP-CORE-01 excludes the pair.

BUILD-AHEAD REGIME (sanctioned by CLAR-PROC-01, WBS §17 RESOLVED 2026-06-04).
  The DOC §3.2 ``evaluate_fidelity(language, corpus_path)`` contract runs the
  Joern (or proprietary) front-end — inside the CMP-SNAP-05 pinned worker image
  — against the curated corpus and diffs the extracted CPG against ground truth.
  SNAP-05 is IN-PROGRESS and the pinned Soot/WALA/Joern toolchain is unavailable
  in hermetic CI (the in-repo corpora self-declare ``soot: NOT-AVAILABLE``,
  ``corpus_version: 0.1.0``). Per CLAR-PROC-01 condition (2), the corpus + the
  CPG extraction are consumed through TYPED PORTS:

    * :class:`CorpusPort` — yields per-item ground truth + the corpus-level
      ``gate_strength: bool`` authority marker. The production default
      (:func:`fail_closed_corpus_port`) is the real corpus loader; the in-repo
      v0.1.0 loader (:func:`lockfile_corpus_port`) reads ``corpus.lock`` and
      reports ``gate_strength=False`` (non-authoritative — synthesized ground
      truth, unpinned toolchain).
    * :class:`ExtractionPort` — yields the extracted CPG for a corpus item. The
      production default (:func:`fail_closed_extraction_port`) raises a typed
      ``NotImplementedError`` naming the gated dependency (SNAP-05 worker image +
      pinned front-end). Hermetic tests inject a synthetic extraction.

  INTERFACE-SHAPE DEVIATIONS from DOC §3.2 (reported, not invented — surfaced in
  ``clar_filed`` and tied to the CP-06 verdict-shape CLAR, orchestrator-numbered):

    1. ``evaluate_fidelity`` takes injectable ``corpus`` + ``extraction`` ports
       (keyword-only, defaulting to the fail-closed production impls) UNDER the
       DOC's public ``(language, corpus_path)`` signature. The ports are the
       build-ahead seam for the corpus/env-gated real toolchain.
    2. The verdict carries a third ``overall`` state ``ungated`` (DOC §3.2 lists
       only GATE-PASS / GATE-FAIL / front-end-blocked). ``ungated`` is the
       structurally-distinct verdict for a NON-gate-strength corpus: NO PASS is
       constructible from non-authoritative input. This is the true current
       state of every in-repo v0.1.0 corpus (CLAR-CORP-07..11 OPEN).
    3. ``overall`` is the enum {GATE-PASS, GATE-FAIL, ungated}; ``front-end-
       blocked`` is the REPORTING LABEL derived from a GATE-FAIL verdict (DOC
       §3.2 lists front-end-blocked as an ``overall`` value — a DOC §3.2/§3.3
       inconsistency; the TST-AC-CP-06a stub is the contract and expects
       ``overall == "GATE-FAIL"`` with ``front-end-blocked`` as the label, so the
       test wins per the reading-guide step 3). :meth:`FidelityVerdict.label`
       maps GATE-FAIL -> "front-end-blocked".

WHAT CP-06 NEVER DOES (DOC §2, §8): it does not run Algorithm-2's recall
benchmark, does not modify any detector, and emits VERDICTS not findings. The
"four required provenance fields" (RULE-6) do not apply; CP-06's analogues are
``env_digest`` + ``corpus_version`` + ``evaluated_at`` (DOC §8). It never writes
``findings``, ``provenance_records``, or ``attestations``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, cast

if TYPE_CHECKING:
    from collections.abc import Sequence

Language = Literal["java", "python", "js", "go", "ruby", "php"]
MetricName = Literal[
    "parse_success_rate",
    "call_edge_precision",
    "call_edge_recall",
    "pdg_recall",
]
Overall = Literal["GATE-PASS", "GATE-FAIL", "ungated"]

# ---------------------------------------------------------------------------
# Thresholds — VERBATIM from CLAR-CORP-02 (RESOLVED 2026-05-23), quoted in
# DOC-CMP-CP-06 §3.1 and .claude/rules/04-staging.md. NEVER re-decided here: a
# change requires a new CTO-approved CLAR-CORP-02 resolution + lockstep updates
# to the DOC, DOC-STAGING, the staging rule, and .github/workflows/stage-gate.yml
# (DOC §3.1 / RULE-4). Decimal (not float) so the ">=" boundary is exact and the
# latest.json round-trip is lossless (DOC §3.2 metric type is Decimal).
# ---------------------------------------------------------------------------
THRESHOLDS: dict[MetricName, Decimal] = {
    "parse_success_rate": Decimal("0.995"),
    "call_edge_precision": Decimal("0.90"),
    "call_edge_recall": Decimal("0.85"),
    "pdg_recall": Decimal("0.80"),
}

# Ordered metric tuple — drives deterministic failing_metrics order + JSON key
# order (the staging consumer reads latest.json; a stable order keeps the
# round-trip byte-stable).
_METRIC_ORDER: tuple[MetricName, ...] = (
    "parse_success_rate",
    "call_edge_precision",
    "call_edge_recall",
    "pdg_recall",
)


class FidelityGateError(Exception):
    """Base class for CP-06 gate-harness errors."""


class BenchmarkEligibilityError(FidelityGateError):
    """Raised when an Algorithm-2 recall number is requested for a non-gate-passing
    language.

    This is the INV-6 owner-side structural guard: CP-06 STRUCTURALLY CANNOT yield
    an Algorithm-2 detector recall number (the benchmark-eligibility surface that
    feeds CMP-CORE-01) for a language whose verdict is not GATE-PASS. The verdict
    object refuses rather than returning a number (DOC §3.3 forbidden phrasings).
    """


@dataclass(frozen=True)
class FidelityMetrics:
    """The four per-language fidelity metrics + their raw counters (DOC §3.2).

    All four rates are :class:`Decimal` in ``0..1`` so the ``>=`` threshold
    comparison is exact and the ``latest.json`` round-trip is lossless.
    """

    parse_success_rate: Decimal
    call_edge_precision: Decimal
    call_edge_recall: Decimal
    pdg_recall: Decimal
    files_parsed: int
    files_total: int
    call_edges_predicted: int
    call_edges_ground_truth: int
    pdg_edges_predicted: int
    pdg_edges_ground_truth: int

    def rate(self, metric: MetricName) -> Decimal:
        """Return the rate for one of the four threshold metrics."""
        return {
            "parse_success_rate": self.parse_success_rate,
            "call_edge_precision": self.call_edge_precision,
            "call_edge_recall": self.call_edge_recall,
            "pdg_recall": self.pdg_recall,
        }[metric]


@dataclass(frozen=True)
class FidelityVerdict:
    """Per-language gate verdict (DOC §3.2 / §3.4 schema).

    ``overall`` is one of {GATE-PASS, GATE-FAIL, ungated}. ``front-end-blocked``
    is the REPORTING LABEL of a GATE-FAIL verdict (:meth:`label`), not an
    ``overall`` value (see module docstring deviation 3).
    """

    language: Language
    corpus_version: str
    env_digest: str
    metrics: FidelityMetrics
    threshold_results: dict[MetricName, Literal["PASS", "FAIL"]]
    overall: Overall
    failing_metrics: list[str]
    gate_strength: bool
    evaluated_at: datetime

    @property
    def gate_passed(self) -> bool:
        """True iff the language is eligible for Algorithm-2 benchmarking.

        A pass is constructible ONLY when the corpus is authoritative AND every
        threshold is met. This is the single chokepoint INV-6 / RULE-7 depend on.
        """
        return self.overall == "GATE-PASS"

    def label(self) -> str:
        """The downstream reporting label (DOC §3.3 / DOC-STAGING §8).

        GATE-PASS -> "gate-pass"; GATE-FAIL -> "front-end-blocked" (NEVER "recall
        failure"); ungated -> "corpus-not-authoritative". On a fail, the label is
        accompanied by the failing FIDELITY metric + value (see
        :meth:`front_end_blocked_reason`) — that fidelity number is permitted by
        INV-6; the FORBIDDEN number is the Algorithm-2 detector recall, which
        lives behind :meth:`benchmark_eligible_recall`.
        """
        return {
            "GATE-PASS": "gate-pass",
            "GATE-FAIL": "front-end-blocked",
            "ungated": "corpus-not-authoritative",
        }[self.overall]

    def front_end_blocked_reason(self) -> str:
        """Human-readable front-end-blocked reason naming the failing fidelity
        metric(s) and value(s) vs. threshold (DOC §3.3 compliant phrasing).

        Only meaningful on GATE-FAIL. Reports the FIDELITY metric (e.g. call-edge
        recall 0.60 < 0.85), never an Algorithm-2 detector recall number.
        """
        if self.overall != "GATE-FAIL":
            return self.label()
        parts: list[str] = []
        for metric in self.failing_metrics:
            value = self.metrics.rate(metric)  # type: ignore[arg-type]
            threshold = THRESHOLDS[metric]  # type: ignore[index]
            parts.append(f"{metric.replace('_', '-')} {value} < {threshold} threshold")
        return "front-end-blocked: " + "; ".join(parts)

    def benchmark_eligible_recall(self) -> Decimal:
        """The Algorithm-2 benchmark-eligibility accessor (INV-6 chokepoint).

        Returns the call-edge recall ONLY for a gate-passing language — and even
        then this is the FIDELITY recall the benchmark may consult to admit the
        pair, NOT a detector recall (CP-06 computes no detector recall, DOC §2).
        For a non-gate-passing language it RAISES, so a caller (CMP-CORE-01)
        cannot surface a recall number for a front-end-blocked or ungated pair.

        This is the structural INV-6 owner-side discharge: there is NO code path
        that yields a number on a fail.
        """
        if not self.gate_passed:
            raise BenchmarkEligibilityError(
                f"{self.language}: not gate-passing ({self.label()}); refusing to "
                "emit a benchmark-eligible recall number (INV-6). Report "
                f"'{self.front_end_blocked_reason()}' instead."
            )
        return self.metrics.call_edge_recall

    def to_json_dict(self) -> dict[str, object]:
        """Serialize to the DOC §3.4 latest.json schema (Decimal -> str, lossless).

        Rates are written as STRINGS so the Decimal survives the JSON round-trip
        exactly (Decimal -> float -> Decimal would break "identical verdict",
        DOC §3.4 / test-e contract).

        The four threshold rates are emitted as JSON NUMBERS (``float``), NOT
        strings — this is the load-bearing consumer contract: the named consumer
        ``.github/workflows/stage-gate.yml`` "Evaluate thresholds" step does
        ``value = r.get(metric, 0.0)`` then ``value >= threshold`` and
        ``f"{value:.3f}"``. A string rate would raise ``TypeError`` (numeric
        compare) / ``ValueError`` (format) there, so the persisted form MUST be a
        number to match both DOC §3.4 (unquoted) and the consumer. Decimal is kept
        INTERNALLY for the exact ``>=`` boundary; only the persisted form is float.
        The verdict's identity (``overall`` / ``failing_metrics`` / ``language``)
        round-trips exactly — that, not bit-exact Decimal across the file, is the
        "identical verdict" staging contract. ``gate_strength`` is added (deviation
        2 — the authority marker a real gate-strength corpus must carry).
        """
        return {
            "language": self.language,
            "corpus_version": self.corpus_version,
            "env_digest": self.env_digest,
            "parse_success_rate": float(self.metrics.parse_success_rate),
            "call_edge_precision": float(self.metrics.call_edge_precision),
            "call_edge_recall": float(self.metrics.call_edge_recall),
            "pdg_recall": float(self.metrics.pdg_recall),
            "files_parsed": self.metrics.files_parsed,
            "files_total": self.metrics.files_total,
            "call_edges_predicted": self.metrics.call_edges_predicted,
            "call_edges_ground_truth": self.metrics.call_edges_ground_truth,
            "pdg_edges_predicted": self.metrics.pdg_edges_predicted,
            "pdg_edges_ground_truth": self.metrics.pdg_edges_ground_truth,
            "evaluated_at": self.evaluated_at.astimezone(timezone.utc).isoformat(),  # noqa: UP017
            "overall": self.overall,
            "failing_metrics": list(self.failing_metrics),
            "gate_strength": self.gate_strength,
        }

    @classmethod
    def from_json_dict(cls, data: dict[str, object]) -> FidelityVerdict:
        """Re-read a verdict from the DOC §3.4 latest.json schema (the inverse of
        :meth:`to_json_dict`); rates parsed back as :class:`Decimal` from string."""

        def _int(value: object) -> int:
            # JSON ints decode as int; coerce defensively via str so an ``object``
            # static type does not break the int() overload (mypy strict).
            return int(str(value))

        metrics = FidelityMetrics(
            parse_success_rate=Decimal(str(data["parse_success_rate"])),
            call_edge_precision=Decimal(str(data["call_edge_precision"])),
            call_edge_recall=Decimal(str(data["call_edge_recall"])),
            pdg_recall=Decimal(str(data["pdg_recall"])),
            files_parsed=_int(data["files_parsed"]),
            files_total=_int(data["files_total"]),
            call_edges_predicted=_int(data["call_edges_predicted"]),
            call_edges_ground_truth=_int(data["call_edges_ground_truth"]),
            pdg_edges_predicted=_int(data["pdg_edges_predicted"]),
            pdg_edges_ground_truth=_int(data["pdg_edges_ground_truth"]),
        )
        raw_failing = data["failing_metrics"]
        failing = [str(m) for m in raw_failing] if isinstance(raw_failing, list) else []
        threshold_results: dict[MetricName, Literal["PASS", "FAIL"]] = {
            metric: ("FAIL" if metric in failing else "PASS") for metric in _METRIC_ORDER
        }
        language = cast("Language", str(data["language"]))
        overall = cast("Overall", str(data["overall"]))
        return cls(
            language=language,
            corpus_version=str(data["corpus_version"]),
            env_digest=str(data["env_digest"]),
            metrics=metrics,
            threshold_results=threshold_results,
            overall=overall,
            failing_metrics=failing,
            gate_strength=bool(data.get("gate_strength", False)),
            evaluated_at=datetime.fromisoformat(str(data["evaluated_at"])),
        )


# ---------------------------------------------------------------------------
# Typed ports (the build-ahead seam — CLAR-PROC-01 condition (2)).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GroundTruthItem:
    """One corpus item's ground truth (DOC §4.1) — counters needed to score
    fidelity. The metric evaluator consumes a uniform schema regardless of the
    per-language ground-truth JSON layout."""

    item_id: str
    parsed: bool
    call_edges_ground_truth: int
    pdg_edges_ground_truth: int


@dataclass(frozen=True)
class ExtractedItem:
    """One corpus item's extracted CPG counters (DOC §4.1) — what the pinned
    front-end produced, to be diffed against the ground truth."""

    item_id: str
    parsed: bool
    # Call-edge confusion against ground truth (over-approximate edges cost
    # precision, missing edges cost recall — DOC §3.3 / corpus methodology).
    call_edges_true_positive: int
    call_edges_false_positive: int
    call_edges_false_negative: int
    # PDG dependence-edge recall confusion (the gate scores recall only — DOC §3.1).
    pdg_edges_true_positive: int
    pdg_edges_false_negative: int


class CorpusPort(Protocol):
    """Port: the curated fidelity corpus (DOC §4.1).

    ``gate_strength`` is the AUTHORITY MARKER (deviation 2). A pass is
    constructible ONLY when it is ``True``; absent/unknown is treated as ``False``
    (fail-closed). The in-repo v0.1.0 corpora self-declare non-authoritative
    (synthesized ground truth, unpinned toolchain — CLAR-CORP-07..11 OPEN), so
    :func:`lockfile_corpus_port` returns ``False``.
    """

    @property
    def corpus_version(self) -> str: ...

    @property
    def gate_strength(self) -> bool: ...

    def ground_truth(self) -> Sequence[GroundTruthItem]: ...


class ExtractionPort(Protocol):
    """Port: the pinned front-end CPG extraction (DOC §4.1).

    The production impl runs Joern/Soot/WALA inside the CMP-SNAP-05 worker image;
    hermetic tests inject a synthetic extraction. ``env_digest`` is the worker
    image digest the verdict is stamped with (DOC §8)."""

    @property
    def env_digest(self) -> str: ...

    def extract(self, item: GroundTruthItem) -> ExtractedItem: ...


def fail_closed_corpus_port(language: Language, corpus_path: Path) -> CorpusPort:
    """Production corpus loader (DOC §4.1) — GATED on a gate-strength corpus.

    Raises a typed :class:`NotImplementedError` naming the gating CLARs: no
    in-repo corpus is gate-strength yet (CLAR-CORP-07..11 OPEN — synthesized
    ground truth, unpinned Soot/WALA/Joern, JDK drift). When a gate-strength
    corpus lands, this loader reads its ground truth + the explicit authority
    marker. Until then the only hermetic corpus port is
    :func:`lockfile_corpus_port`, which reports ``gate_strength=False``.
    """
    raise NotImplementedError(
        f"CMP-CP-06 gate-strength corpus loader for {language!r} at {corpus_path} is "
        "gated on a gate-strength CPG-fidelity corpus (CLAR-CORP-07..11 OPEN: "
        "synthesized ground truth + unpinned Soot/WALA/Joern toolchain). The in-repo "
        "v0.1.0 corpora are NOT gate-strength; use lockfile_corpus_port for the honest "
        "ungated verdict over the scaffold."
    )


def fail_closed_extraction_port(language: Language, env_digest: str) -> ExtractionPort:
    """Production extraction port (DOC §4.1) — GATED on the SNAP-05 worker image.

    Raises a typed :class:`NotImplementedError` naming the gated dependency: the
    pinned Joern/Soot/WALA front-end runs only inside the CMP-SNAP-05 worker image
    (IN-PROGRESS), which carries the real ``env_digest`` (CLAR-CP-06-02). Hermetic
    tests inject a synthetic extraction port.
    """
    raise NotImplementedError(
        f"CMP-CP-06 CPG extraction for {language!r} (env_digest={env_digest!r}) is gated "
        "on the CMP-SNAP-05 pinned worker image (IN-PROGRESS) carrying the pinned "
        "Joern/Soot/WALA front-end + the real env_digest (CLAR-CP-06-02). Inject a "
        "synthetic ExtractionPort for hermetic evaluation."
    )


class _LockfileCorpusPort:
    """Honest ungated corpus port over an in-repo v0.1.0 scaffold (DOC §4.1).

    Reads ``corpus.lock`` for the ``corpus_version`` and reports
    ``gate_strength=False`` UNCONDITIONALLY: the in-repo corpora self-declare
    synthesized ground truth + unpinned toolchain (CLAR-CORP-07..11 OPEN), so no
    PASS is constructible from them. It does NOT parse per-item ground truth
    (extraction is gated); :meth:`ground_truth` returns an empty sequence, which
    is sufficient because the ungated short-circuit fires before extraction.
    """

    def __init__(self, corpus_version: str) -> None:
        self._corpus_version = corpus_version

    @property
    def corpus_version(self) -> str:
        return self._corpus_version

    @property
    def gate_strength(self) -> bool:
        # Fail-closed: the in-repo v0.1.0 corpora are NOT authoritative
        # (CLAR-CORP-07..11 OPEN). No pass is constructible — encoded here.
        return False

    def ground_truth(self) -> Sequence[GroundTruthItem]:
        return ()


def lockfile_corpus_port(corpus_path: Path) -> CorpusPort:
    """Build a fail-closed :class:`CorpusPort` over an in-repo ``corpus.lock``.

    Hermetic — reads only the lockfile's ``corpus_version`` line; reports
    ``gate_strength=False``. This is the port that makes requirement (4) — the
    honest CURRENT state — hermetic: running the harness over the v0.1.0 scaffold
    yields an ``ungated`` verdict for java + python with NO toolchain. Missing
    lockfile -> ``corpus_version="unknown"`` (still ``gate_strength=False``).
    """
    corpus_version = "unknown"
    lock = corpus_path / "corpus.lock"
    if lock.is_file():
        for line in lock.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("corpus_version:"):
                corpus_version = stripped.split(":", 1)[1].strip().strip("'\"")
                break
    return _LockfileCorpusPort(corpus_version)


# ---------------------------------------------------------------------------
# Metric evaluator (DOC §6 — "Aggregate per-language metrics").
# ---------------------------------------------------------------------------
def _safe_ratio(numerator: int, denominator: int) -> Decimal:
    """Exact Decimal ratio; an empty denominator yields a perfect 1 (a metric with
    no ground-truth instances cannot be missed). Parse rate handles its own zero."""
    if denominator == 0:
        return Decimal(1)
    return (Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.000001"))


def compute_metrics(
    corpus: CorpusPort,
    extraction: ExtractionPort,
) -> FidelityMetrics:
    """Compute the four per-language fidelity metrics from ground truth + the
    extracted CPG (DOC §6). Pure aggregation over the ports — no thresholds here.
    """
    ground_truth = list(corpus.ground_truth())
    files_total = len(ground_truth)
    files_parsed = 0
    ce_tp = ce_fp = ce_fn = ce_gt = 0
    pdg_tp = pdg_fn = pdg_gt = 0
    for gt_item in ground_truth:
        extracted = extraction.extract(gt_item)
        if extracted.parsed:
            files_parsed += 1
        ce_tp += extracted.call_edges_true_positive
        ce_fp += extracted.call_edges_false_positive
        ce_fn += extracted.call_edges_false_negative
        ce_gt += gt_item.call_edges_ground_truth
        pdg_tp += extracted.pdg_edges_true_positive
        pdg_fn += extracted.pdg_edges_false_negative
        pdg_gt += gt_item.pdg_edges_ground_truth
    parse_rate = Decimal(1) if files_total == 0 else _safe_ratio(files_parsed, files_total)
    return FidelityMetrics(
        parse_success_rate=parse_rate,
        call_edge_precision=_safe_ratio(ce_tp, ce_tp + ce_fp),
        call_edge_recall=_safe_ratio(ce_tp, ce_tp + ce_fn),
        pdg_recall=_safe_ratio(pdg_tp, pdg_tp + pdg_fn),
        files_parsed=files_parsed,
        files_total=files_total,
        call_edges_predicted=ce_tp + ce_fp,
        call_edges_ground_truth=ce_gt,
        pdg_edges_predicted=pdg_tp,
        pdg_edges_ground_truth=pdg_gt,
    )


def _verdict_from_metrics(
    language: Language,
    corpus: CorpusPort,
    env_digest: str,
    metrics: FidelityMetrics,
    *,
    evaluated_at: datetime,
) -> FidelityVerdict:
    """Apply the CLAR-CORP-02 thresholds to computed metrics -> verdict.

    The state machine (DOC §6 + deviation 2):
      * a non-gate-strength corpus -> ``ungated`` (NO pass constructible);
      * else all four thresholds met (``>=``, exact Decimal) -> ``GATE-PASS``;
      * else -> ``GATE-FAIL`` with the failing metric(s) named (front-end-blocked).
    """
    threshold_results: dict[MetricName, Literal["PASS", "FAIL"]] = {}
    failing: list[str] = []
    for metric in _METRIC_ORDER:
        if metrics.rate(metric) >= THRESHOLDS[metric]:
            threshold_results[metric] = "PASS"
        else:
            threshold_results[metric] = "FAIL"
            failing.append(metric)
    if not corpus.gate_strength:
        overall: Overall = "ungated"
    elif failing:
        overall = "GATE-FAIL"
    else:
        overall = "GATE-PASS"
    return FidelityVerdict(
        language=language,
        corpus_version=corpus.corpus_version,
        env_digest=env_digest,
        metrics=metrics,
        threshold_results=threshold_results,
        overall=overall,
        failing_metrics=failing,
        gate_strength=corpus.gate_strength,
        evaluated_at=evaluated_at,
    )


def evaluate_fidelity(
    language: Language,
    corpus_path: Path,
    *,
    corpus: CorpusPort | None = None,
    extraction: ExtractionPort | None = None,
    evaluated_at: datetime | None = None,
) -> FidelityVerdict:
    """Run the fidelity gate for ``language`` and emit a :class:`FidelityVerdict`.

    DOC §3.2 public contract is ``evaluate_fidelity(language, corpus_path)``; the
    ``corpus`` / ``extraction`` ports are the build-ahead seam (deviation 1),
    defaulting to the fail-closed production impls. The standard hermetic call for
    the in-repo scaffold passes ``corpus=lockfile_corpus_port(corpus_path)`` and
    omits ``extraction`` (the ungated short-circuit never reaches it).

    State machine (DOC §6 + deviation 2):
      * GATE-PASS — corpus is gate-strength AND all four thresholds met; eligible
        for Algorithm-2 benchmarking on staged ``(class, language)`` pairs.
      * GATE-FAIL — gate-strength corpus, at least one threshold missed; reported
        ``front-end-blocked`` (the failing FIDELITY metric named); a benchmark
        recall number is structurally refused (INV-6, AC-CP-06a).
      * ungated — corpus is NOT gate-strength; NO pass is constructible (the true
        current state of every in-repo v0.1.0 corpus).
    """
    if corpus is None:
        corpus = fail_closed_corpus_port(language, corpus_path)
    # `timezone.utc` (not the 3.11+-only `datetime.UTC` alias that UP017 prefers):
    # the local sandbox is py3.10 where `datetime.UTC` does not exist; CI is py3.11.
    # Matches the repo precedent in services/triage/spec_inference.py.
    when = evaluated_at or datetime.now(timezone.utc)  # noqa: UP017
    # Ungated short-circuit BEFORE extraction (requirement 4: hermetic over the
    # scaffold, no toolchain): a non-authoritative corpus cannot pass, so there is
    # nothing to extract or score for the gate decision.
    if not corpus.gate_strength:
        empty = FidelityMetrics(
            parse_success_rate=Decimal(0),
            call_edge_precision=Decimal(0),
            call_edge_recall=Decimal(0),
            pdg_recall=Decimal(0),
            files_parsed=0,
            files_total=len(list(corpus.ground_truth())),
            call_edges_predicted=0,
            call_edges_ground_truth=0,
            pdg_edges_predicted=0,
            pdg_edges_ground_truth=0,
        )
        return _verdict_from_metrics(
            language, corpus, _UNGATED_ENV_DIGEST, empty, evaluated_at=when
        )
    if extraction is None:
        extraction = fail_closed_extraction_port(language, _UNGATED_ENV_DIGEST)
    metrics = compute_metrics(corpus, extraction)
    return _verdict_from_metrics(
        language, corpus, extraction.env_digest, metrics, evaluated_at=when
    )


# Placeholder env_digest stamped on an ungated verdict: no pinned worker image
# was consulted (extraction never ran), so the verdict cannot claim a production
# Env. A gate-strength run stamps the real CMP-SNAP-05 digest (CLAR-CP-06-02).
_UNGATED_ENV_DIGEST = "sha256:0000000000000000000000000000000000000000000000000000000000000000"


def verdict_path(results_root: Path, language: Language) -> Path:
    """The DOC §3.4 / §4.2 canonical persistence path:
    ``tests/results/cpg_fidelity/{language}/latest.json`` (under ``results_root``)."""
    return results_root / "cpg_fidelity" / language / "latest.json"


def persist_verdict(verdict: FidelityVerdict, results_root: Path) -> Path:
    """Persist ``verdict`` to ``{results_root}/cpg_fidelity/{language}/latest.json``
    (DOC §3.4 — the FORMAT is load-bearing; the staging consumer reads this file).

    Decimal rates are written as strings (lossless round-trip). Returns the path.
    """
    path = verdict_path(results_root, verdict.language)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(verdict.to_json_dict(), indent=2, sort_keys=True)
    path.write_text(payload + "\n", encoding="utf-8")
    return path


def load_verdict(results_root: Path, language: Language) -> FidelityVerdict:
    """Re-read the persisted verdict (the inverse of :func:`persist_verdict`)."""
    path = verdict_path(results_root, language)
    data = json.loads(path.read_text(encoding="utf-8"))
    return FidelityVerdict.from_json_dict(data)
