"""Refactor-invariance validation harness for ``slice_fingerprint`` (Algorithm 3).

WHAT THIS IS
------------
An *empirical* harness that runs the curated refactor corpus
(``tests/corpora/refactor/`` — CMP-CORP-REFAC-01) against the REAL Joern
front-end and the REAL fingerprint implementation, and reports, per refactor
kind, whether the fingerprint actually stayed or actually flipped versus the
corpus ground truth.

It computes nothing it cannot compute. A pair whose before- or after-side
cannot be parsed, whose sink cannot be located, or for which the fingerprinter
returns no result is reported as ``unevaluated`` with a reason — never as a
"stayed" or a "flipped". No fingerprint value in the report is synthesised,
defaulted, or inferred; every one of them came back from the fingerprinter.

HOW STRONG IS THE RESULT?
-------------------------
Only as strong as the corpus. ``tests/corpora/refactor/README.md`` discloses
that the 350 pairs are round-robined from **8 base templates**, so the corpus
holds only ~8 distinct (class, language) sink-topologies: it is
*count-complete but topology-thin*. A pass here is evidence about 8 topologies
repeated 50 times, NOT about 50 independent programs. This caveat is repeated
verbatim in every report this harness emits.

Two further honesty rules are baked into the comparison logic:

1. **A missing fingerprint is never a flip.** On ``genuine-fix`` the detector
   may legitimately find no sink on the after side. That is a plausible and
   interesting outcome, but it is not a *computed* flip, so it is recorded as
   ``unevaluated: no-fingerprint-after``. Reading it as a green flip would
   manufacture the very result this harness exists to test.
2. **A weak/weak match is not invariance evidence.** ``analysis.fingerprint``
   documents ``fingerprint_class = "weak"`` as the witness-edge-sequence hash —
   a *same-source* identity only, explicitly not canonical across isomorphic
   programs (INV-5). Comparing two weak fingerprints across a refactor is
   meaningless for a ``should-stay`` claim. Every pair therefore carries
   ``comparison_validity ∈ {strong, weak}`` (weak if either side is weak) and
   the report tables the strong/strong subset separately.

WHERE IT RUNS
-------------
The real fingerprinter calls
``analysis.cpg_ingest.joern_frontend.parse_source``, which shells out to the
pinned ``joern-parse`` / ``joern`` binaries. It therefore has to run INSIDE the
Scanipy snapshot worker image (``workers/snapshot/Dockerfile``), exactly like
``~/scanipy-demo/runner/cpg_stats.py``. This module ships no docker driver of
its own; the orchestrator runs it in-image.

Two collaborators land on parallel tracks and are imported lazily, behind a
seam, so this module is importable and unit-testable without them:

* ``analysis.cpg_ingest.mapper.map_export_with_locations`` (TRACK A)
* ``services.scan.oracle_fingerprint.fingerprint_oracle_finding`` (TRACK B)

If either is missing the harness fails LOUDLY at startup rather than emitting
350 unevaluated rows.

Cross-references: ``tests/corpora/refactor/README.md``,
``tests/corpora/refactor/annotation-methodology.md``, ``analysis/fingerprint.py``,
``.claude/rules/01-invariants.md`` §INV-5.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal, Protocol

import yaml

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Iterable, Mapping, Sequence

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

GroundTruth = Literal["should-stay", "should-flip"]
Outcome = Literal["stayed", "flipped", "unevaluated"]
ComparisonValidity = Literal["strong", "weak"]

#: Ground-truth label -> the outcome that label demands (annotation-methodology.md §1).
EXPECTED_OUTCOME: Final[dict[str, str]] = {
    "should-stay": "stayed",
    "should-flip": "flipped",
}

#: Repeated verbatim in every emitted report. Sourced from
#: tests/corpora/refactor/README.md "Status — v0.1.0".
CORPUS_CAVEAT: Final[str] = (
    "Results are only as strong as the corpus. CMP-CORP-REFAC-01 v0.1.0 is "
    "count-complete but TOPOLOGY-THIN: its 350 pairs are round-robined from 8 base "
    "templates, so it contains only ~8 distinct (class, language) sink-topologies. "
    "Treat these numbers as evidence about 8 topologies repeated 50 times, not about "
    "50 independent programs (see tests/corpora/refactor/README.md and CLAR-CORP-17)."
)

#: Comparison-validity caveat, also repeated in every report.
WEAK_CLASS_CAVEAT: Final[str] = (
    "A 'weak' fingerprint_class is the witness-edge-sequence hash — a same-source "
    "identity only, NOT canonical across isomorphic programs (INV-5). A stayed/flipped "
    "verdict on a pair where either side is weak is NOT invariance evidence; read the "
    "strong/strong subset."
)

#: Env handed to the Joern front-end when running inside the snapshot worker
#: image. Mirrors ~/scanipy-demo/runner/cpg_stats.py. Override with --joern-env-json.
DEFAULT_JOERN_ENV: Final[dict[str, str]] = {
    "PATH": "/opt/joern/bin:/opt/codeql:/opt/temurin-jre/bin:/usr/bin",
    "JAVA_HOME": "/opt/temurin-jre",
}

#: Filename parse_source writes its export JSON to inside its workdir. Mirrors
#: analysis.cpg_ingest.joern_frontend._EXPORT_JSON_FILENAME (private there).
_EXPORT_JSON_FILENAME: Final[str] = "cpg_export.json"

_CALL_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(")


# ---------------------------------------------------------------------------
# Errors — every one of these means "the harness could not run", not "a pair failed"
# ---------------------------------------------------------------------------


class HarnessError(Exception):
    """Base class: the harness itself cannot proceed."""


class CorpusIntegrityError(HarnessError):
    """The corpus on disk disagrees with itself (meta.yaml vs corpus.lock).

    Fail-closed: a harness that silently prefers one source of truth over the
    other would report ground truth that nobody wrote down.
    """


class HarnessDependencyError(HarnessError):
    """A module the real fingerprinter needs is not importable.

    Raised eagerly at startup so an un-integrated worktree produces one loud
    message rather than 350 identical unevaluated rows.
    """


# ---------------------------------------------------------------------------
# Corpus model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CorpusMeta:
    """Provenance block read from ``corpus.lock``, echoed into every report."""

    corpus_id: str
    corpus_version: str
    corpus_digest: str
    distinct_topologies: int
    seed_count: int
    pair_count: int
    refactor_taxonomy: dict[str, str]


@dataclass(frozen=True)
class RefactorPair:
    """One (seed, refactor) pair with its ground truth and both source trees.

    ``before_sink_line`` is taken verbatim from ``meta.yaml``'s
    ``seed_finding.sink_line`` (1-based). The corpus records NO after-side sink
    coordinates, so the after-side line is located at evaluation time — see
    :func:`locate_sink_line`.
    """

    seed_id: str
    language: str
    finding_class: str
    refactor: str
    ground_truth: str
    before_dir: Path
    after_dir: Path
    sink_file: str
    before_sink_line: int


def _as_str(value: object, *, where: str, key: str) -> str:
    if not isinstance(value, str):
        raise CorpusIntegrityError(f"{where}: {key!r} is {type(value).__name__}, expected str")
    return value


def _as_int(value: object, *, where: str, key: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise CorpusIntegrityError(f"{where}: {key!r} is {type(value).__name__}, expected int")
    return value


def _as_mapping(value: object, *, where: str, key: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CorpusIntegrityError(f"{where}: {key!r} is {type(value).__name__}, expected mapping")
    return value


def _as_list(value: object, *, where: str, key: str) -> list[Any]:
    if not isinstance(value, list):
        raise CorpusIntegrityError(f"{where}: {key!r} is {type(value).__name__}, expected list")
    return value


def load_corpus_meta(corpus_dir: Path) -> CorpusMeta:
    """Read ``corpus.lock``'s provenance block.

    Raises:
        CorpusIntegrityError: the lock file is absent or structurally wrong.
    """
    lock_path = corpus_dir / "corpus.lock"
    if not lock_path.is_file():
        raise CorpusIntegrityError(f"no corpus.lock at {lock_path}")
    raw = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    lock = _as_mapping(raw, where=str(lock_path), key="<root>")
    where = str(lock_path)
    taxonomy_raw = _as_mapping(lock.get("refactor_taxonomy"), where=where, key="refactor_taxonomy")
    taxonomy = {
        str(k): _as_str(v, where=where, key=f"refactor_taxonomy[{k}]")
        for k, v in taxonomy_raw.items()
    }
    return CorpusMeta(
        corpus_id=_as_str(lock.get("corpus_id"), where=where, key="corpus_id"),
        corpus_version=_as_str(lock.get("corpus_version"), where=where, key="corpus_version"),
        corpus_digest=_as_str(lock.get("corpus_digest"), where=where, key="corpus_digest"),
        distinct_topologies=_as_int(
            lock.get("distinct_topologies"), where=where, key="distinct_topologies"
        ),
        seed_count=_as_int(lock.get("seed_count"), where=where, key="seed_count"),
        pair_count=_as_int(lock.get("pair_count"), where=where, key="pair_count"),
        refactor_taxonomy=taxonomy,
    )


def _lock_ground_truth_index(corpus_dir: Path) -> dict[tuple[str, str], str]:
    """``(seed_id, refactor) -> ground_truth_label`` as recorded in ``corpus.lock``."""
    lock_path = corpus_dir / "corpus.lock"
    lock = _as_mapping(
        yaml.safe_load(lock_path.read_text(encoding="utf-8")), where=str(lock_path), key="<root>"
    )
    index: dict[tuple[str, str], str] = {}
    for seed in _as_list(lock.get("seeds"), where=str(lock_path), key="seeds"):
        seed_map = _as_mapping(seed, where=str(lock_path), key="seeds[]")
        seed_id = _as_str(seed_map.get("seed_id"), where=str(lock_path), key="seed_id")
        pairs = _as_list(seed_map.get("refactor_pairs"), where=str(lock_path), key="refactor_pairs")
        for pair in pairs:
            pair_map = _as_mapping(pair, where=str(lock_path), key="refactor_pairs[]")
            refactor = _as_str(pair_map.get("refactor"), where=str(lock_path), key="refactor")
            label = _as_str(
                pair_map.get("ground_truth_label"), where=str(lock_path), key="ground_truth_label"
            )
            index[(seed_id, refactor)] = label
    return index


def load_pairs(corpus_dir: Path, *, limit: int | None = None) -> list[RefactorPair]:
    """Enumerate every (seed, refactor) pair, cross-checked against ``corpus.lock``.

    ``meta.yaml`` is the per-seed source of truth for paths and labels;
    ``corpus.lock`` is the pinned inventory. Any disagreement between them is a
    hard :class:`CorpusIntegrityError` — the harness will not pick a winner.

    Args:
        corpus_dir: the ``tests/corpora/refactor`` directory.
        limit: evaluate only the first ``limit`` seeds in sorted order (smoke
            subset). ``None`` means every seed.

    Raises:
        CorpusIntegrityError: missing/parse-broken metadata, or a meta.yaml
            label that disagrees with corpus.lock.
    """
    seeds_dir = corpus_dir / "seeds"
    if not seeds_dir.is_dir():
        raise CorpusIntegrityError(f"no seeds/ directory under {corpus_dir}")
    lock_index = _lock_ground_truth_index(corpus_dir)

    seed_dirs = sorted(p for p in seeds_dir.iterdir() if p.is_dir())
    if limit is not None:
        seed_dirs = seed_dirs[:limit]

    pairs: list[RefactorPair] = []
    for seed_dir in seed_dirs:
        pairs.extend(_load_seed_pairs(seed_dir, lock_index=lock_index))
    return pairs


def _load_seed_pairs(
    seed_dir: Path, *, lock_index: Mapping[tuple[str, str], str]
) -> list[RefactorPair]:
    meta_path = seed_dir / "meta.yaml"
    if not meta_path.is_file():
        raise CorpusIntegrityError(f"no meta.yaml in {seed_dir}")
    where = str(meta_path)
    meta = _as_mapping(
        yaml.safe_load(meta_path.read_text(encoding="utf-8")), where=where, key="<root>"
    )
    seed_id = _as_str(meta.get("seed_id"), where=where, key="seed_id")
    finding = _as_mapping(meta.get("seed_finding"), where=where, key="seed_finding")
    language = _as_str(finding.get("language"), where=where, key="seed_finding.language")
    finding_class = _as_str(finding.get("class"), where=where, key="seed_finding.class")
    sink_file = _as_str(finding.get("sink_file"), where=where, key="seed_finding.sink_file")
    sink_line = _as_int(finding.get("sink_line"), where=where, key="seed_finding.sink_line")
    before_dir = seed_dir / _as_str(meta.get("before_dir"), where=where, key="before_dir")

    pairs: list[RefactorPair] = []
    for entry in _as_list(meta.get("refactor_pairs"), where=where, key="refactor_pairs"):
        entry_map = _as_mapping(entry, where=where, key="refactor_pairs[]")
        refactor = _as_str(entry_map.get("refactor"), where=where, key="refactor")
        label = _as_str(entry_map.get("ground_truth_label"), where=where, key="ground_truth_label")
        after_dir = seed_dir / _as_str(entry_map.get("after_dir"), where=where, key="after_dir")

        locked = lock_index.get((seed_id, refactor))
        if locked is None:
            raise CorpusIntegrityError(
                f"{seed_id}/{refactor}: present in meta.yaml but absent from corpus.lock"
            )
        if locked != label:
            raise CorpusIntegrityError(
                f"{seed_id}/{refactor}: meta.yaml label {label!r} disagrees with "
                f"corpus.lock label {locked!r}"
            )
        if label not in EXPECTED_OUTCOME:
            raise CorpusIntegrityError(
                f"{seed_id}/{refactor}: unknown ground_truth_label {label!r} "
                f"(expected one of {sorted(EXPECTED_OUTCOME)})"
            )
        pairs.append(
            RefactorPair(
                seed_id=seed_id,
                language=language,
                finding_class=finding_class,
                refactor=refactor,
                ground_truth=label,
                before_dir=before_dir,
                after_dir=after_dir,
                sink_file=sink_file,
                before_sink_line=sink_line,
            )
        )
    return pairs


# ---------------------------------------------------------------------------
# After-side sink location
# ---------------------------------------------------------------------------
#
# CORPUS GAP: meta.yaml / corpus.lock record `sink_line` for the BEFORE tree
# only. No after-side sink coordinate exists anywhere in the corpus, yet the
# TRACK-B fingerprint entry point is keyed by (filename, line). The locator
# below is harness plumbing to bridge that gap, and it is deliberately
# conservative: it derives the callee token from the before-side sink line and
# requires a UNIQUE line in the after file to carry it. Zero or multiple
# candidates -> the pair is unevaluated, never guessed. Every located line and
# the token used are written into the JSON report so a reader can audit them.


def sink_callee_token(line_text: str) -> str | None:
    """The callee identifier of the outermost call on a sink line, or ``None``.

    The last ``ident(`` on the line is taken: for ``new FileInputStream(target)``
    and ``st.executeQuery(q)`` alike, that is the sink call itself.
    """
    matches = _CALL_TOKEN_RE.findall(line_text)
    if not matches:
        return None
    token: str = matches[-1]
    return token


def locate_sink_line(text: str, token: str) -> list[int]:
    """1-based line numbers in ``text`` that contain a call to ``token``.

    Returns every candidate; the caller requires exactly one.
    """
    needle = re.compile(rf"\b{re.escape(token)}\s*\(")
    return [i for i, line in enumerate(text.splitlines(), 1) if needle.search(line)]


def resolve_source_file(directory: Path, sink_file: str) -> Path | None:
    """The source file inside ``directory`` that holds the seeded finding.

    Prefers the corpus-declared ``sink_file`` name; falls back to the single
    file in the directory when the refactor renamed it. Returns ``None`` when
    the choice would be a guess (no file, or several candidates).
    """
    declared = directory / sink_file
    if declared.is_file():
        return declared
    if not directory.is_dir():
        return None
    candidates = sorted(p for p in directory.iterdir() if p.is_file())
    if len(candidates) == 1:
        return candidates[0]
    return None


# ---------------------------------------------------------------------------
# Fingerprinter seam
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SideFingerprint:
    """What the fingerprinter actually returned for one side of one pair."""

    slice_fingerprint: str
    fingerprint_class: str
    budget_exhausted: bool


class Fingerprinter(Protocol):
    """Parse ``src_dir`` and fingerprint the finding at ``filename``:``line``.

    Contract:
        * return a :class:`SideFingerprint` only when one was genuinely computed;
        * return ``None`` when the finding has no resolvable sink / no witness
          (the harness records ``no-fingerprint-<side>``, NEVER a flip);
        * raise on parse failure or budget/tooling failure (the harness records
          the exception text as the unevaluated reason).
    """

    def __call__(
        self, *, src_dir: Path, language: str, filename: str, line: int
    ) -> SideFingerprint | None: ...


def _hexify(value: object) -> str:
    """Render a ``Sha256`` (``NewType`` over raw bytes) as lowercase hex."""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    return str(value)


def _adapt_result(result: object) -> SideFingerprint:
    """Wrap a ``SliceFingerprintResult`` without inventing any of its fields."""
    fingerprint = getattr(result, "slice_fingerprint", None)
    fp_class = getattr(result, "fingerprint_class", None)
    if fingerprint is None or fp_class is None:
        raise HarnessDependencyError(
            "fingerprint_oracle_finding returned an object without "
            f"slice_fingerprint/fingerprint_class: {type(result).__name__}"
        )
    return SideFingerprint(
        slice_fingerprint=_hexify(fingerprint),
        fingerprint_class=str(fp_class),
        budget_exhausted=bool(getattr(result, "budget_exhausted", False)),
    )


#: The three real collaborators, as ``(module, attribute, label)``. Resolved by
#: name at runtime (``importlib``) rather than by a top-level ``from ... import``
#: because TRACK A and TRACK B land on parallel branches: a static import would
#: make this module un-typecheckable until they merge, and a ``type: ignore``
#: would flip to an unused-ignore error the moment they do (``warn_unused_ignores``).
_REAL_COLLABORATORS: Final[tuple[tuple[str, str, str], ...]] = (
    ("analysis.cpg_ingest.joern_frontend", "parse_source", ""),
    ("analysis.cpg_ingest.mapper", "map_export_with_locations", " [TRACK A]"),
    ("services.scan.oracle_fingerprint", "fingerprint_oracle_finding", " [TRACK B]"),
)


def require_real_dependencies() -> tuple[Any, Any, Any]:
    """Resolve the real collaborators, or fail loudly naming what is missing.

    Returns:
        ``(parse_source, map_export_with_locations, fingerprint_oracle_finding)``.

    Raises:
        HarnessDependencyError: any of the three is unavailable. TRACK A
            (``map_export_with_locations``) and TRACK B
            (``fingerprint_oracle_finding``) land in parallel; until they do,
            this is the loud failure — not 350 unevaluated rows.
    """
    import importlib

    missing: list[str] = []
    resolved: list[Any] = []
    for module_name, attr, label in _REAL_COLLABORATORS:
        try:
            module = importlib.import_module(module_name)
            resolved.append(getattr(module, attr))
        except (ImportError, AttributeError) as exc:
            missing.append(f"{module_name}.{attr}{label} ({type(exc).__name__}: {exc})")
            resolved.append(None)
    if missing:
        raise HarnessDependencyError(
            "the real fingerprinter cannot run — missing collaborators:\n  - "
            + "\n  - ".join(missing)
            + "\nThis harness refuses to emit a report it could not compute."
        )
    return resolved[0], resolved[1], resolved[2]


class RealFingerprinter:
    """Default :class:`Fingerprinter`: real Joern parse + real Algorithm 3.

    Must run inside the snapshot worker image (the ``joern-parse`` / ``joern``
    binaries are resolved from ``PATH``). Parsed trees are cached by resolved
    source directory, so a seed's ``before/`` tree is parsed once and reused
    across all 7 of its refactors.
    """

    def __init__(
        self,
        *,
        workdir_root: Path,
        env: Mapping[str, str] | None = None,
    ) -> None:
        parse_source, map_with_locations, fingerprint_oracle = require_real_dependencies()
        self._parse_source = parse_source
        self._map_with_locations = map_with_locations
        self._fingerprint_oracle = fingerprint_oracle
        self._workdir_root = workdir_root
        self._env: dict[str, str] = dict(env) if env is not None else dict(DEFAULT_JOERN_ENV)
        self._cache: dict[tuple[str, str], tuple[Any, Any]] = {}
        self._parse_count = 0

    @property
    def parse_count(self) -> int:
        """How many real Joern parses were performed (cache misses)."""
        return self._parse_count

    def _parse(self, src_dir: Path, language: str) -> tuple[Any, Any]:
        key = (str(src_dir.resolve()), language)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        workdir = self._workdir_root / f"parse-{len(self._cache):05d}"
        workdir.mkdir(parents=True, exist_ok=True)
        env = dict(self._env)
        env.setdefault("HOME", str(workdir))
        # parse_source performs both joern phases and writes the export JSON into
        # workdir; re-read it here rather than re-running joern for TRACK A's mapper.
        self._parse_source(src_dir, language, env=env, workdir=workdir)
        self._parse_count += 1
        export_path = workdir / _EXPORT_JSON_FILENAME
        export = json.loads(export_path.read_text(encoding="utf-8"))
        cpg, locations = self._map_with_locations(export)
        self._cache[key] = (cpg, locations)
        return cpg, locations

    def __call__(
        self, *, src_dir: Path, language: str, filename: str, line: int
    ) -> SideFingerprint | None:
        cpg, locations = self._parse(src_dir, language)
        result = self._fingerprint_oracle(cpg, locations, filename=filename, line=line)
        if result is None:
            return None
        return _adapt_result(result)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PairResult:
    """The evaluated (or explicitly unevaluated) verdict for one pair."""

    seed_id: str
    language: str
    finding_class: str
    refactor: str
    ground_truth: str
    expected_outcome: str
    outcome: str
    matches_expectation: bool | None
    unevaluated_reason: str | None = None
    unevaluated_detail: str | None = None
    before_sink_line: int | None = None
    after_sink_line: int | None = None
    sink_token: str | None = None
    before_locator_agrees: bool | None = None
    before_fingerprint: str | None = None
    after_fingerprint: str | None = None
    before_fingerprint_class: str | None = None
    after_fingerprint_class: str | None = None
    comparison_validity: str | None = None


def _unevaluated(
    pair: RefactorPair, reason: str, detail: str | None = None, **extra: object
) -> PairResult:
    return PairResult(
        seed_id=pair.seed_id,
        language=pair.language,
        finding_class=pair.finding_class,
        refactor=pair.refactor,
        ground_truth=pair.ground_truth,
        expected_outcome=EXPECTED_OUTCOME[pair.ground_truth],
        outcome="unevaluated",
        matches_expectation=None,
        unevaluated_reason=reason,
        unevaluated_detail=detail,
        before_sink_line=pair.before_sink_line,
        **extra,  # type: ignore[arg-type]
    )


def evaluate_pair(pair: RefactorPair, fingerprinter: Fingerprinter) -> PairResult:
    """Fingerprint both sides of ``pair`` and compare.

    Never fabricates: every non-``unevaluated`` outcome is backed by two
    fingerprints the ``fingerprinter`` actually returned.
    """
    before_file = resolve_source_file(pair.before_dir, pair.sink_file)
    if before_file is None:
        return _unevaluated(pair, "before-source-missing", str(pair.before_dir))
    after_file = resolve_source_file(pair.after_dir, pair.sink_file)
    if after_file is None:
        return _unevaluated(pair, "after-source-missing", str(pair.after_dir))

    try:
        before_text = before_file.read_text(encoding="utf-8")
        after_text = after_file.read_text(encoding="utf-8")
    except OSError as exc:  # unreadable tree — report, do not guess
        return _unevaluated(pair, "source-unreadable", str(exc))

    before_lines = before_text.splitlines()
    if not 1 <= pair.before_sink_line <= len(before_lines):
        return _unevaluated(
            pair,
            "before-sink-line-out-of-range",
            f"meta sink_line={pair.before_sink_line}, file has {len(before_lines)} lines",
        )
    token = sink_callee_token(before_lines[pair.before_sink_line - 1])
    if token is None:
        return _unevaluated(
            pair,
            "sink-token-underivable",
            f"no call syntax on before sink line {pair.before_sink_line}",
        )

    before_candidates = locate_sink_line(before_text, token)
    before_locator_agrees = before_candidates == [pair.before_sink_line]

    after_candidates = locate_sink_line(after_text, token)
    if len(after_candidates) != 1:
        return _unevaluated(
            pair,
            "sink-not-located",
            f"token {token!r} matched {len(after_candidates)} lines in "
            f"{after_file.name} (need exactly 1): {after_candidates}",
            sink_token=token,
            before_locator_agrees=before_locator_agrees,
        )
    after_line = after_candidates[0]

    try:
        before_fp = fingerprinter(
            src_dir=pair.before_dir,
            language=pair.language,
            filename=before_file.name,
            line=pair.before_sink_line,
        )
    except Exception as exc:
        return _unevaluated(
            pair,
            "before-fingerprint-error",
            f"{type(exc).__name__}: {exc}",
            sink_token=token,
            after_sink_line=after_line,
            before_locator_agrees=before_locator_agrees,
        )
    try:
        after_fp = fingerprinter(
            src_dir=pair.after_dir,
            language=pair.language,
            filename=after_file.name,
            line=after_line,
        )
    except Exception as exc:
        return _unevaluated(
            pair,
            "after-fingerprint-error",
            f"{type(exc).__name__}: {exc}",
            sink_token=token,
            after_sink_line=after_line,
            before_locator_agrees=before_locator_agrees,
            before_fingerprint=before_fp.slice_fingerprint if before_fp else None,
            before_fingerprint_class=before_fp.fingerprint_class if before_fp else None,
        )

    common: dict[str, object] = {
        "sink_token": token,
        "after_sink_line": after_line,
        "before_locator_agrees": before_locator_agrees,
        "before_fingerprint": before_fp.slice_fingerprint if before_fp else None,
        "before_fingerprint_class": before_fp.fingerprint_class if before_fp else None,
        "after_fingerprint": after_fp.slice_fingerprint if after_fp else None,
        "after_fingerprint_class": after_fp.fingerprint_class if after_fp else None,
    }
    # HONESTY RULE 1: a missing fingerprint is never a flip. "No finding on the
    # after side" may well be correct detector behaviour after a genuine-fix,
    # but it is not a COMPUTED flip, so it stays unevaluated.
    if before_fp is None:
        return _unevaluated(pair, "no-fingerprint-before", None, **common)
    if after_fp is None:
        return _unevaluated(pair, "no-fingerprint-after", None, **common)

    outcome = "stayed" if before_fp.slice_fingerprint == after_fp.slice_fingerprint else "flipped"
    # HONESTY RULE 2: a verdict is only invariance evidence when BOTH sides are
    # strong; a weak fingerprint is a same-source identity (INV-5).
    validity: ComparisonValidity = (
        "strong"
        if before_fp.fingerprint_class == "strong" and after_fp.fingerprint_class == "strong"
        else "weak"
    )
    return PairResult(
        seed_id=pair.seed_id,
        language=pair.language,
        finding_class=pair.finding_class,
        refactor=pair.refactor,
        ground_truth=pair.ground_truth,
        expected_outcome=EXPECTED_OUTCOME[pair.ground_truth],
        outcome=outcome,
        matches_expectation=outcome == EXPECTED_OUTCOME[pair.ground_truth],
        before_sink_line=pair.before_sink_line,
        after_sink_line=after_line,
        sink_token=token,
        before_locator_agrees=before_locator_agrees,
        before_fingerprint=before_fp.slice_fingerprint,
        after_fingerprint=after_fp.slice_fingerprint,
        before_fingerprint_class=before_fp.fingerprint_class,
        after_fingerprint_class=after_fp.fingerprint_class,
        comparison_validity=validity,
    )


def evaluate_pairs(pairs: Iterable[RefactorPair], fingerprinter: Fingerprinter) -> list[PairResult]:
    """Evaluate every pair in order. One pair's failure never aborts the run."""
    return [evaluate_pair(pair, fingerprinter) for pair in pairs]


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@dataclass
class RefactorRow:
    """One row of the per-refactor-kind table."""

    refactor: str
    ground_truth: str = ""
    expected_outcome: str = ""
    total: int = 0
    stayed: int = 0
    flipped: int = 0
    unevaluated: int = 0
    as_expected: int = 0
    contrary_to_expectation: int = 0
    strong_strong_total: int = 0
    strong_strong_as_expected: int = 0
    unevaluated_reasons: dict[str, int] = field(default_factory=dict)


def build_report(
    results: Sequence[PairResult],
    meta: CorpusMeta,
    *,
    corpus_dir: Path,
    limit: int | None,
    fingerprinter_name: str,
) -> dict[str, Any]:
    """Assemble the machine-readable report. Pure: no I/O, no clock, no RNG."""
    rows: dict[str, RefactorRow] = {}
    for res in results:
        row = rows.setdefault(res.refactor, RefactorRow(refactor=res.refactor))
        row.ground_truth = res.ground_truth
        row.expected_outcome = res.expected_outcome
        row.total += 1
        if res.outcome == "unevaluated":
            row.unevaluated += 1
            reason = res.unevaluated_reason or "unspecified"
            row.unevaluated_reasons[reason] = row.unevaluated_reasons.get(reason, 0) + 1
            continue
        if res.outcome == "stayed":
            row.stayed += 1
        else:
            row.flipped += 1
        if res.matches_expectation:
            row.as_expected += 1
        else:
            row.contrary_to_expectation += 1
        if res.comparison_validity == "strong":
            row.strong_strong_total += 1
            if res.matches_expectation:
                row.strong_strong_as_expected += 1

    class_counts = {
        "before": {"strong": 0, "weak": 0, "other": 0},
        "after": {"strong": 0, "weak": 0, "other": 0},
    }
    for res in results:
        for side, value in (
            ("before", res.before_fingerprint_class),
            ("after", res.after_fingerprint_class),
        ):
            if value is None:
                continue
            bucket = value if value in ("strong", "weak") else "other"
            class_counts[side][bucket] += 1

    unevaluated = [
        {
            "seed_id": r.seed_id,
            "language": r.language,
            "class": r.finding_class,
            "refactor": r.refactor,
            "ground_truth": r.ground_truth,
            "reason": r.unevaluated_reason,
            "detail": r.unevaluated_detail,
        }
        for r in results
        if r.outcome == "unevaluated"
    ]
    reason_totals: dict[str, int] = {}
    for entry in unevaluated:
        key = str(entry["reason"])
        reason_totals[key] = reason_totals.get(key, 0) + 1

    evaluated = [r for r in results if r.outcome != "unevaluated"]
    strong_evaluated = [r for r in evaluated if r.comparison_validity == "strong"]
    return {
        "schema_version": 1,
        "generated_by": "scripts/validate_refactor_fingerprints.py",
        "caveats": {
            "corpus_topology": CORPUS_CAVEAT,
            "weak_fingerprint_class": WEAK_CLASS_CAVEAT,
        },
        "corpus": {
            "dir": str(corpus_dir),
            "corpus_id": meta.corpus_id,
            "corpus_version": meta.corpus_version,
            "corpus_digest": meta.corpus_digest,
            "distinct_topologies": meta.distinct_topologies,
            "seed_count": meta.seed_count,
            "pair_count": meta.pair_count,
            "refactor_taxonomy": meta.refactor_taxonomy,
        },
        "run": {
            "limit": limit,
            "fingerprinter": fingerprinter_name,
            "pairs_considered": len(results),
            "seeds_considered": len({r.seed_id for r in results}),
        },
        "totals": {
            "pairs": len(results),
            "evaluated": len(evaluated),
            "unevaluated": len(unevaluated),
            "stayed": sum(1 for r in evaluated if r.outcome == "stayed"),
            "flipped": sum(1 for r in evaluated if r.outcome == "flipped"),
            "as_expected": sum(1 for r in evaluated if r.matches_expectation),
            "contrary_to_expectation": sum(1 for r in evaluated if not r.matches_expectation),
            "strong_strong_evaluated": len(strong_evaluated),
            "strong_strong_as_expected": sum(1 for r in strong_evaluated if r.matches_expectation),
            "unevaluated_reason_counts": reason_totals,
        },
        "fingerprint_class_counts": class_counts,
        "by_refactor": {name: asdict(row) for name, row in sorted(rows.items())},
        "unevaluated": unevaluated,
        "pairs": [asdict(r) for r in results],
    }


def render_summary(report: Mapping[str, Any]) -> str:
    """A short human-readable summary. Repeats both caveats verbatim."""
    corpus = report["corpus"]
    totals = report["totals"]
    run = report["run"]
    lines: list[str] = []
    lines.append("Refactor-fingerprint invariance — empirical run")
    lines.append("=" * 62)
    lines.append(
        f"corpus   : {corpus['corpus_id']} v{corpus['corpus_version']} "
        f"({corpus['distinct_topologies']} distinct topologies, "
        f"{corpus['pair_count']} pairs on record)"
    )
    lines.append(f"digest   : {corpus['corpus_digest']}")
    lines.append(
        f"run      : fingerprinter={run['fingerprinter']} limit={run['limit']} "
        f"pairs={run['pairs_considered']} seeds={run['seeds_considered']}"
    )
    lines.append("")
    header = (
        f"{'refactor':<28}{'expect':<9}{'stayed':>7}{'flipped':>8}"
        f"{'uneval':>8}{'as-exp':>8}{'CONTRA':>8}{'strong':>8}"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for name, row in report["by_refactor"].items():
        lines.append(
            f"{name:<28}{row['expected_outcome']:<9}{row['stayed']:>7}{row['flipped']:>8}"
            f"{row['unevaluated']:>8}{row['as_expected']:>8}"
            f"{row['contrary_to_expectation']:>8}{row['strong_strong_total']:>8}"
        )
    lines.append("-" * len(header))
    lines.append(
        f"{'TOTAL':<28}{'':<9}{totals['stayed']:>7}{totals['flipped']:>8}"
        f"{totals['unevaluated']:>8}{totals['as_expected']:>8}"
        f"{totals['contrary_to_expectation']:>8}{totals['strong_strong_evaluated']:>8}"
    )
    lines.append("")
    lines.append(
        "fingerprint_class: before "
        + ", ".join(f"{k}={v}" for k, v in report["fingerprint_class_counts"]["before"].items())
        + " | after "
        + ", ".join(f"{k}={v}" for k, v in report["fingerprint_class_counts"]["after"].items())
    )
    lines.append("")
    if totals["unevaluated"]:
        lines.append(f"UNEVALUATED PAIRS ({totals['unevaluated']}) — never counted as a result:")
        for reason, count in sorted(totals["unevaluated_reason_counts"].items()):
            lines.append(f"  {count:>5}  {reason}")
        shown = report["unevaluated"][:10]
        for entry in shown:
            detail = f" — {entry['detail']}" if entry["detail"] else ""
            lines.append(f"    - {entry['seed_id']}/{entry['refactor']}: {entry['reason']}{detail}")
        if len(report["unevaluated"]) > len(shown):
            lines.append(f"    ... {len(report['unevaluated']) - len(shown)} more (see JSON)")
    else:
        lines.append("UNEVALUATED PAIRS: none.")
    lines.append("")
    lines.append("CAVEAT (corpus): " + CORPUS_CAVEAT)
    lines.append("")
    lines.append("CAVEAT (weak class): " + WEAK_CLASS_CAVEAT)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_DEFAULT_CORPUS_DIR: Final[Path] = Path("tests/corpora/refactor")


def build_arg_parser() -> argparse.ArgumentParser:
    """The ``--help`` surface."""
    parser = argparse.ArgumentParser(
        prog="validate_refactor_fingerprints",
        description=(
            "Run the CMP-CORP-REFAC-01 refactor corpus against the real Joern front-end "
            "and the real slice_fingerprint, and report per-refactor stayed/flipped vs "
            "ground truth. Pairs that cannot be parsed, located, or fingerprinted are "
            "reported as UNEVALUATED — never as a result. Nothing is fabricated."
        ),
        epilog=(
            "MUST run inside the Scanipy snapshot worker image (it shells out to the "
            "pinned joern binaries). RESULTS ARE ONLY AS STRONG AS THE CORPUS: " + CORPUS_CAVEAT
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=_DEFAULT_CORPUS_DIR,
        help=f"refactor corpus directory (default: {_DEFAULT_CORPUS_DIR})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="path for the machine-readable JSON report",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=None,
        help="optional path for the human-readable summary (always printed to stdout)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="evaluate only the first N seeds (sorted) — smoke subset",
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=None,
        help="scratch dir for joern intermediates (default: a fresh temp dir)",
    )
    parser.add_argument(
        "--joern-env-json",
        type=Path,
        default=None,
        help="JSON file of env vars for the joern child process (default: in-image PATH/JAVA_HOME)",
    )
    return parser


def run(
    *,
    corpus_dir: Path,
    fingerprinter: Fingerprinter,
    fingerprinter_name: str,
    limit: int | None = None,
) -> dict[str, Any]:
    """Load, evaluate, and report. The importable entry point for tests."""
    meta = load_corpus_meta(corpus_dir)
    pairs = load_pairs(corpus_dir, limit=limit)
    results = evaluate_pairs(pairs, fingerprinter)
    return build_report(
        results,
        meta,
        corpus_dir=corpus_dir,
        limit=limit,
        fingerprinter_name=fingerprinter_name,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns 0 on a completed run, 2 when the harness cannot run.

    A run that finds results CONTRARY to the ground truth still exits 0: a red
    cell in this table is a finding, not a harness failure.
    """
    args = build_arg_parser().parse_args(argv)
    env: dict[str, str] = dict(DEFAULT_JOERN_ENV)
    if args.joern_env_json is not None:
        loaded = json.loads(Path(args.joern_env_json).read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            print("--joern-env-json must contain a JSON object", file=sys.stderr)
            return 2
        env = {str(k): str(v) for k, v in loaded.items()}

    with tempfile.TemporaryDirectory(prefix="refac-fp-") as tmp:
        workdir = Path(args.workdir) if args.workdir is not None else Path(tmp)
        workdir.mkdir(parents=True, exist_ok=True)
        try:
            fingerprinter: Fingerprinter = RealFingerprinter(workdir_root=workdir, env=env)
            report = run(
                corpus_dir=args.corpus_dir,
                fingerprinter=fingerprinter,
                fingerprinter_name="RealFingerprinter(joern+algorithm-3)",
                limit=args.limit,
            )
        except HarnessError as exc:
            print(f"HARNESS CANNOT RUN: {exc}", file=sys.stderr)
            return 2

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = render_summary(report)
    if args.summary_out is not None:
        summary_path = Path(args.summary_out)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(summary + "\n", encoding="utf-8")
    print(summary)
    print(f"\nJSON report written to {out_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI wrapper
    raise SystemExit(main())
