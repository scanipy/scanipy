"""CMP-DET-02 — detector registry + closure check.

Discovers ``detectors/<class>/manifest.yaml`` files, parses each, runs the
grammar/closure check for core (DSL) engines, validates the native query file
for oracle engines, derives ``determinism_partition`` from the ``engine`` field,
and admits the result as a frozen :class:`Detector` record.

Two roles fold together (DOC-CMP-DET-02 §2):

1. **Closure check** (AC-DET-02a / INV-4). For ``engine ∈ {ifds, ide}`` the spec
   must lie inside the distributive-by-construction DSL grammar. Membership is
   decided by :func:`analysis.ifds.dsl.parse_spec`; :func:`closure_check` is a
   defense-in-depth *shape* re-validation on the already-frozen
   :class:`~analysis.ifds.dsl.Spec` — it is **not** a re-parse and **not** a
   distributivity decision procedure. Out-of-DSL content raises ``E-DSL-*``
   (surfaced verbatim from the parser) at ``load_manifests`` time.
2. **Partition derivation** (AC-DET-02c). :func:`derive_partition` maps the
   ``engine`` field to one of the two determinism partitions. The mapping is the
   normative source of truth for INV-1 and is consumed by CMP-ORCH-03.

Provenance (DOC-CMP-DET-02 §8.2): CMP-DET-02 stamps only ``determinism_partition``
on its own ``Detector`` record. It writes NO ``origin`` / ``S_version`` /
``env_digest`` / ``cpg_order_hash`` / finding-table fields — those are threaded
downstream.

Persistence (CLAR-DET-01, DEFERRED): on-disk YAML manifests are the source of
truth; the in-memory :class:`DetectorRegistry` is rebuilt at every process start.
No SQL ``detectors`` table is added inline (RULE-4).
"""

from __future__ import annotations

import types
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from analysis.ifds.dsl import DSLError as DSLError  # re-exported (DOC-CMP-DET-02 §3)
from analysis.ifds.dsl import Spec, parse_spec, revalidate_spec

EngineTag = Literal["ifds", "ide", "semgrep", "cpg-query", "external"]
DeterminismPartition = Literal["deterministic-core", "oracle-passthrough"]
LanguageReadiness = Literal["ready", "front-end-blocked", "stage-gated"]
Severity = Literal["low", "medium", "high", "critical"]

# Engine -> partition mapping (DOC-PARTITION §3 / AC-DET-02c). A new engine may
# not be added without amending SDD AC-DET-02c, .claude/rules/05-determinism.md,
# and DOC-PARTITION §3 in lockstep (RULE-4).
CORE_ENGINES: tuple[str, ...] = ("ifds", "ide")
ORACLE_ENGINES: tuple[str, ...] = ("semgrep", "cpg-query", "external")
_ALL_ENGINES: frozenset[str] = frozenset(CORE_ENGINES) | frozenset(ORACLE_ENGINES)

# Required manifest keys (AC-DET-02b). ``determinism_partition`` is DERIVED, not
# authored, and must NOT appear in a manifest file.
_REQUIRED_MANIFEST_KEYS: tuple[str, ...] = (
    "id",
    "cwes",
    "languages",
    "frameworks",
    "engine",
    "severity_default",
    "per_language_readiness",
)


# ─── error types ────────────────────────────────────────────────────────────


class RegistryError(Exception):
    """Manifest-/registry-level rejection (E-REG-001..006).

    DSL-level rejections (E-DSL-001..009) are surfaced verbatim via
    :class:`~analysis.ifds.dsl.DSLError`; the registry never re-wraps them.
    """

    def __init__(self: RegistryError, code: str, message: str) -> None:
        self.code: str = code
        self.message: str = message
        super().__init__(f"{code}: {message}")


class RegistryLoadError(Exception):
    """Atomic ``load_manifests`` failure aggregate.

    Raised when one or more manifest-level errors are detected during a load.
    On any failure the registry is left empty — there is no partial-load mode
    (DOC-CMP-DET-02 §7.3). DSL parse failures propagate as :class:`DSLError`
    directly (verbatim ``E-DSL-*`` code) rather than being aggregated here.
    """

    def __init__(
        self: RegistryLoadError,
        code: str,
        message: str,
        *,
        errors: list[RegistryError] | None = None,
    ) -> None:
        self.code: str = code
        self.message: str = message
        self.errors: list[RegistryError] = errors or []
        super().__init__(f"{code}: {message}")


# ─── registry record ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Detector:
    """One registry row (DOC-CMP-DET-02 §3.1, AC-DET-02b).

    Derived from a ``manifest.yaml`` plus, for core engines, a parsed DSL
    :class:`~analysis.ifds.dsl.Spec`. ``determinism_partition`` is DERIVED from
    ``engine`` at registration, never authored on the manifest.
    """

    id: str
    cwes: tuple[str, ...]
    languages: tuple[str, ...]
    frameworks: tuple[str, ...]
    engine: EngineTag
    severity_default: Severity
    determinism_partition: DeterminismPartition
    # Read-only view: a ``frozen=True`` dataclass field that is nonetheless a
    # mutable ``dict`` lets consumers corrupt the process-wide singleton
    # (PR #235 N-2). Stored as a :class:`types.MappingProxyType` so the mapping
    # is immutable; the annotation is :class:`~collections.abc.Mapping` so
    # callers see read-only access only.
    per_language_readiness: Mapping[str, LanguageReadiness]
    spec: Spec | None = None
    oracle_query_path: str | None = None


# ─── partition derivation (AC-DET-02c) ────────────────────────────────────────


def derive_partition(engine: str) -> DeterminismPartition:
    """Map ``engine`` to its determinism partition (AC-DET-02c).

    ``ifds`` / ``ide`` -> ``deterministic-core``;
    ``semgrep`` / ``cpg-query`` / ``external`` -> ``oracle-passthrough``.

    Raises :class:`RegistryError` (E-REG-006) if ``engine`` is outside the
    enumerated set — defense in depth, should have been caught by E-REG-002.
    """
    if engine in CORE_ENGINES:
        return "deterministic-core"
    if engine in ORACLE_ENGINES:
        return "oracle-passthrough"
    raise RegistryError(
        "E-REG-006",
        f"engine={engine!r} not in the enumerated set; register a new engine via AC-DET-02c first.",
    )


# ─── closure check (AC-DET-02a / INV-4, defense in depth) ─────────────────────


def closure_check(detector: Detector) -> None:
    """Re-validate a :class:`Detector`'s engine/spec *shape* (defense in depth).

    This is NOT a re-parse and NOT a distributivity decision procedure — the
    parser (CMP-DET-01) already decided DSL membership. ``closure_check`` only
    confirms that the frozen record is internally consistent before admission:

    For ``engine ∈ {ifds, ide}``:
      - ``detector.spec`` is present;
      - the carried :class:`Spec`'s engine is itself a core (DSL) engine;
      - the spec has at least one clause.

    For ``engine ∈ {semgrep, cpg-query, external}``:
      - ``detector.spec`` is absent;
      - ``detector.oracle_query_path`` is present and the file exists.

    Raises :class:`RegistryError` (E-REG-002/E-REG-004) on a shape violation.
    """
    if detector.engine not in _ALL_ENGINES:
        raise RegistryError(
            "E-REG-002",
            f"engine={detector.engine!r} not in "
            "{ifds, ide, semgrep, cpg-query, external} (AC-DET-02c)",
        )

    if detector.engine in CORE_ENGINES:
        if detector.spec is None:
            raise RegistryError(
                "E-REG-002",
                f"engine={detector.engine!r} requires a DSL spec; none carried "
                f"on detector {detector.id!r}",
            )
        if detector.spec.engine not in CORE_ENGINES:
            raise RegistryError(
                "E-REG-002",
                f"detector {detector.id!r} carries a spec with non-core engine "
                f"{detector.spec.engine!r}",
            )
        if not detector.spec.clauses:
            raise RegistryError(
                "E-REG-002",
                f"detector {detector.id!r} carries a spec with no clauses",
            )
        return

    # Oracle engine path.
    if detector.spec is not None:
        raise RegistryError(
            "E-REG-004",
            f"engine={detector.engine!r} must not carry a DSL spec; it is "
            "oracle-passthrough and names a native query instead",
        )
    if not detector.oracle_query_path or not Path(detector.oracle_query_path).is_file():
        raise RegistryError(
            "E-REG-004",
            f"engine={detector.engine!r} requires oracle_query_path; "
            f"file {detector.oracle_query_path!r} not found",
        )


# ─── registry ─────────────────────────────────────────────────────────────────


class DetectorRegistry:
    """Process-singleton detector registry (DOC-CMP-DET-02 §3.2).

    Populated by :meth:`load_manifests` at process start; frozen thereafter.
    All consumers (CMP-CORE-01, CMP-ORCH-03, CMP-TRI-02, CMP-CP-05) are
    read-only.
    """

    def __init__(self: DetectorRegistry) -> None:
        self._by_id: dict[str, Detector] = {}
        self._frozen: bool = False

    # -- mutation (boot only) --------------------------------------------------

    def load_manifests(self: DetectorRegistry, root: str = "detectors/") -> None:
        """Discover, parse and register every detector under ``root``.

        For ``engine ∈ {ifds, ide}`` each ``specs/*.dsl.yaml`` is parsed via
        :func:`analysis.ifds.dsl.parse_spec`; a parse failure propagates as
        :class:`DSLError` with its verbatim ``E-DSL-*`` code. For oracle engines
        the native query file is validated to exist.

        The load is **atomic**: on any failure the registry is left empty
        (DOC-CMP-DET-02 §7.3). After a clean load the registry is frozen.

        Boot is a one-shot operation: a second call on an already-frozen
        registry is rejected with ``E-REG-005`` (PR #235 N-1) rather than
        silently rebuilding and re-freezing the singleton.
        """
        if self._frozen:
            raise RegistryError(
                "E-REG-005",
                "load_manifests() called on a frozen registry; boot is a one-shot operation",
            )
        staged: dict[str, Detector] = {}
        errors: list[RegistryError] = []

        try:
            for class_dir in self._iter_class_dirs(root):
                manifest_path = class_dir / "manifest.yaml"
                if not manifest_path.is_file():
                    continue
                detector = self._build_detector(class_dir, manifest_path, staged)
                # closure_check + manifest-level E-REG checks run inside register
                # path semantics; here we admit into the staging area atomically.
                # The duplicate-id check (E-REG-003) is enforced earlier inside
                # _build_detector against ``staged`` (PR #235 F-4: removed the
                # unreachable post-build re-check here).
                closure_check(detector)
                # INV-4 authoritative gate (CLAR-DET-02). closure_check is a
                # shape-only re-validation; it never inspects clause *pattern*
                # content. revalidate_spec re-runs the parser's escape-hatch
                # checks over each clause so a hand-built or tampered Spec cannot
                # slip unparsed escape-hatch content (E-DSL-*) past admission.
                # Idempotent on the production path (specs came from parse_spec).
                if detector.spec is not None:
                    revalidate_spec(detector.spec)
                staged[detector.id] = detector
        except RegistryError as exc:
            # Atomic: discard everything staged this load, leave registry empty.
            self._by_id = {}
            errors.append(exc)
            raise RegistryLoadError(
                exc.code,
                f"load_manifests aborted: {exc.message}",
                errors=errors,
            ) from exc
        except DSLError:
            # DSL parse failure surfaced verbatim (E-DSL-*); registry stays empty.
            self._by_id = {}
            raise

        self._by_id = staged
        self._frozen = True

    def register(self: DetectorRegistry, detector: Detector) -> None:
        """Admit a single :class:`Detector` (closure check + E-REG checks).

        Rejected with :class:`RegistryError` (E-REG-005) once the registry is
        frozen — the registry never mutates after :meth:`load_manifests`.
        """
        if self._frozen:
            raise RegistryError(
                "E-REG-005",
                f"registry is read-only after load_manifests(); "
                f"re-registration of {detector.id!r} rejected",
            )
        closure_check(detector)
        # INV-4 authoritative gate (CLAR-DET-02). closure_check is shape-only and
        # never inspects clause pattern content, so a caller could hand-build a
        # Spec carrying unparsed escape-hatch content (e.g.
        # Source(AccessPathPattern("re.compile(...)"))) and slip it past register().
        # revalidate_spec re-runs the parser's escape-hatch / endpoint checks over
        # each clause and raises the verbatim DSLError (E-DSL-*) on any hit. This
        # is the SAME gate load_manifests applies, so both admission paths enforce
        # it identically (idempotent when the Spec came from parse_spec).
        if detector.spec is not None:
            revalidate_spec(detector.spec)
        if detector.id in self._by_id:
            raise RegistryError(
                "E-REG-003",
                f"detector id {detector.id!r} is already registered",
            )
        self._by_id[detector.id] = detector

    # -- read-only queries -----------------------------------------------------

    def all_for(self: DetectorRegistry, *, language: str, class_: str) -> tuple[Detector, ...]:
        """Detectors matching a (language, class) pair; consumed by CMP-ORCH-03.

        ``class_`` matches a detector whose carried DSL spec class equals
        ``class_`` (core engines) or which declares it via its CWE/framework
        metadata; for the registry contract we match on the DSL spec class for
        core engines and admit oracle detectors by language membership only.
        """
        out: list[Detector] = []
        for det in self._by_id.values():
            if language not in det.languages:
                continue
            if det.spec is not None and det.spec.class_ != class_:
                continue
            out.append(det)
        return tuple(out)

    def by_id(self: DetectorRegistry, detector_id: str) -> Detector:
        """Lookup by id; raises ``KeyError`` on miss."""
        return self._by_id[detector_id]

    def all(self: DetectorRegistry) -> tuple[Detector, ...]:
        """Every registered detector; consumed by CMP-CP-05 (Attestor)."""
        return tuple(self._by_id.values())

    # -- internals -------------------------------------------------------------

    @staticmethod
    def _iter_class_dirs(root: str) -> list[Path]:
        root_path = Path(root)
        if not root_path.is_dir():
            return []
        return sorted(p for p in root_path.iterdir() if p.is_dir())

    def _build_detector(
        self: DetectorRegistry,
        class_dir: Path,
        manifest_path: Path,
        staged: dict[str, Detector],
    ) -> Detector:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise RegistryError(
                "E-REG-001",
                f"manifest {manifest_path!r} is not a mapping",
            )

        for key in _REQUIRED_MANIFEST_KEYS:
            if key not in raw or raw[key] is None:
                raise RegistryError(
                    "E-REG-001",
                    f"missing required manifest field {key!r} (AC-DET-02b)",
                )

        engine = str(raw["engine"])
        if engine not in _ALL_ENGINES:
            raise RegistryError(
                "E-REG-002",
                f"engine={engine!r} not in "
                "{ifds, ide, semgrep, cpg-query, external} (AC-DET-02c)",
            )

        detector_id = str(raw["id"])
        if detector_id in staged:
            raise RegistryError(
                "E-REG-003",
                f"detector id {detector_id!r} is already registered",
            )

        spec: Spec | None = None
        oracle_query_path: str | None = None
        if engine in CORE_ENGINES:
            spec = self._load_core_spec(class_dir)
        else:
            declared = raw.get("oracle_query_path")
            oracle_query_path = str(class_dir / str(declared)) if declared else None
            if not oracle_query_path or not Path(oracle_query_path).is_file():
                raise RegistryError(
                    "E-REG-004",
                    f"engine={engine!r} requires oracle_query_path; "
                    f"file {oracle_query_path!r} not found",
                )

        partition = derive_partition(engine)

        # ``per_language_readiness`` must be a mapping. A YAML list (or scalar)
        # would make ``dict(...)`` raise a bare ``ValueError``/``TypeError`` that
        # escapes ``load_manifests``'s ``except (RegistryError, DSLError)``
        # atomicity handler, skipping the empty-registry reset (PR #235 N-3).
        # Convert it to E-REG-001 so it is caught and the load stays atomic.
        plr_raw = raw["per_language_readiness"]
        if not isinstance(plr_raw, Mapping):
            raise RegistryError(
                "E-REG-001",
                f"per_language_readiness must be a mapping, got {type(plr_raw).__name__!r}",
            )

        return Detector(
            id=detector_id,
            cwes=tuple(str(c) for c in raw["cwes"]),
            languages=tuple(str(lang) for lang in raw["languages"]),
            frameworks=tuple(str(fw) for fw in raw["frameworks"]),
            engine=engine,  # type: ignore[arg-type]  # membership checked above
            severity_default=str(raw["severity_default"]),  # type: ignore[arg-type]
            determinism_partition=partition,
            # Wrapped in a read-only proxy so the frozen Detector cannot be
            # mutated through this field (PR #235 N-2).
            per_language_readiness=types.MappingProxyType(dict(plr_raw)),
            spec=spec,
            oracle_query_path=oracle_query_path,
        )

    @staticmethod
    def _load_core_spec(class_dir: Path) -> Spec:
        """Parse the single ``specs/*.dsl.yaml`` for a core detector.

        DSL parse failures propagate as :class:`DSLError` (verbatim ``E-DSL-*``).
        A core detector with no DSL spec file is a manifest-level error.
        """
        specs_dir = class_dir / "specs"
        spec_files = sorted(specs_dir.glob("*.dsl.yaml")) if specs_dir.is_dir() else []
        if not spec_files:
            raise RegistryError(
                "E-REG-001",
                f"core engine detector in {str(class_dir)!r} has no specs/*.dsl.yaml",
            )
        # One spec per detector for the registry contract; parse the first.
        source_text = spec_files[0].read_text(encoding="utf-8")
        return parse_spec(source_text, source_path=str(spec_files[0]))
