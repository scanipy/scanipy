"""CMP-FND-01 — Findings normalizer + canonical SARIF 2.1.0 emitter.

Source-of-truth: ``DOC-CMP-FND-01``, ``DOC-SARIF`` (§3 canonical serialisation,
§4 two-Run model, §5 Run schema, §6 Result schema, §7 result ordering, §11 the
Scanipy extension shape), ``DOC-PROVENANCE`` §3/§10,
``.claude/rules/02-provenance.md``, ``.claude/rules/05-determinism.md``.

This module is the wire-format boundary between the analysis core / oracle
adapters and every downstream SARIF consumer (Attestor CMP-CP-05, attestation
export, dashboard, GitHub code-scanning). Given a ``frozenset`` of worker
findings produced by CMP-ORCH-03, it emits ONE SARIF v2.1.0 log with **two Run
objects** — ``runs[0]`` for ``origin = "deterministic-core"`` results,
``runs[1]`` for ``origin = "oracle-passthrough"`` results (DOC-SARIF §4).

Load-bearing property: ``normalize`` is **pure**. Same inputs ⇒ byte-identical
``SARIFLog.canonical_bytes``. No I/O. No clock reads. No global state. This is
exactly what CMP-CP-05's core pipeline attests as byte-identical SARIF
(``AC-CP-05a`` / ``TST-INV-1-FND-01``).

BUILD-AHEAD REGIME (sanctioned).
  ``Depends-On`` per ``WBS.md §20`` is ``CMP-CORE-02`` (slice_fingerprint /
  fingerprint_class) and ``CMP-CORE-03`` (cpg_order_hash / annotation). CORE-03
  is built (``analysis.ordering``); CORE-02 is NOT. This emitter therefore
  ACCEPTS ``slice_fingerprint`` and ``fingerprint_class`` as typed inputs on the
  worker finding — it never computes or fakes them. The one INV-5 literal it
  emits is imported from the single construction site
  ``analysis.ordering.CPG_ORDER_HASH_ANNOTATION`` (never the finding's own field,
  never rebuilt from substrings).

  The upstream worker-finding record (CMP-ORCH-03) does not yet exist as a
  shipped dataclass, so the input contract is expressed as the
  :class:`WorkerFinding` ``Protocol`` below, co-located here so that
  ``analysis.sarif`` never imports from ``services`` (layering: services depends
  on analysis, not the reverse). Any object exposing these attributes — the
  future CMP-ORCH-03 ``Finding``, a test double, or a thin adapter over the
  CMP-FND-02 ORM row — is a valid input.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Final, Literal, Protocol, runtime_checkable
from uuid import UUID

from analysis.ordering import CPG_ORDER_HASH_ANNOTATION

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

Partition = Literal["core", "oracle"]
Origin = Literal["deterministic-core", "oracle-passthrough"]
PreconditionStatus = Literal["closed-world", "degraded", "full-reparse"]

SARIF_SCHEMA_URI: Final[str] = "https://json.schemastore.org/sarif-2.1.0.json"
SARIF_VERSION: Final[str] = "2.1.0"
TOOL_NAME: Final[str] = "scanipy"
TOOL_VERSION: Final[str] = "3.2.0"
TOOL_INFORMATION_URI: Final[str] = "https://scanipy.io"

# The exact set of allowed enum domains (DOC-SARIF §6); used by the structural
# validator and the pre-emit invariant pass.
_ORIGINS: Final[frozenset[str]] = frozenset({"deterministic-core", "oracle-passthrough"})
_ENGINES: Final[frozenset[str]] = frozenset({"ifds", "ide", "semgrep", "cpg-query", "external"})
_FP_CLASSES: Final[frozenset[str]] = frozenset({"strong", "weak"})
_SEVERITIES: Final[frozenset[str]] = frozenset({"info", "low", "medium", "high", "critical"})
_STATUSES: Final[frozenset[str]] = frozenset({"open", "suppressed", "fixed"})
_PRECONDITIONS: Final[frozenset[str]] = frozenset({"closed-world", "degraded", "full-reparse"})

# SARIF v2.1.0 ``level`` is a total, deterministic projection of severity
# (DOC-SARIF §6 example: high -> error, medium -> warning). The mapping is
# total over ``_SEVERITIES`` so every finding has a level.
_SEVERITY_TO_LEVEL: Final[dict[str, str]] = {
    "info": "note",
    "low": "note",
    "medium": "warning",
    "high": "error",
    "critical": "error",
}


# ---------------------------------------------------------------------------
# Error contracts (DOC-CMP-FND-01 §7.1)
# ---------------------------------------------------------------------------


class InvariantViolation(Exception):  # noqa: N818  (named verbatim, DOC §7.1)
    """A required provenance field on a Result is missing, empty, or out of
    domain (INV-1 / INV-2 / INV-5). Emission halts; nothing partial is written.

    ``code`` is the ``DOC-API.md §6.1`` error code:
    ``invariant_inv1_violation`` | ``invariant_inv2_violation`` |
    ``invariant_inv5_violation``.
    """

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


class SARIFSchemaViolation(Exception):  # noqa: N818  (named verbatim, DOC §7.1)
    """``SARIFLog.canonical_bytes`` failed SARIF v2.1.0 structural validation."""


class SARIFExtensionViolation(Exception):  # noqa: N818  (named verbatim, DOC §7.1)
    """A Run/Result failed the Scanipy ``scanipy.*`` extension shape (DOC-SARIF §11)."""


class CanonicalEmissionFailure(Exception):  # noqa: N818  (named verbatim, DOC §7.1)
    """A post-serialisation sanity check failed: re-parsed key order or result
    order does not match the canonical contract (DOC-SARIF §3 rule 1 + §7).
    Indicates an emitter bug, not bad data."""


# ---------------------------------------------------------------------------
# Input contract — the worker finding (CMP-ORCH-03 record, build-ahead Protocol)
# ---------------------------------------------------------------------------


@runtime_checkable
class WorkerFinding(Protocol):
    """The internal finding record produced by CMP-ORCH-03 (DOC-CMP-FND-01 §3.1).

    FND-01 is a pure projection onto SARIF; it reads these attributes and never
    mutates them. ``origin`` / ``S_version`` / ``env_digest`` are threaded
    verbatim (FND-01 never re-derives them). ``cpg_order_hash`` /
    ``slice_fingerprint`` are hex strings (64 lowercase hex chars).

    The annotation field on the worker record is intentionally NOT read here: the
    one INV-5 literal emitted is always the
    :data:`analysis.ordering.CPG_ORDER_HASH_ANNOTATION` constant.
    """

    # --- INV-1 (origin) ---
    origin: Origin
    determinism_partition: Origin
    engine: str
    # --- INV-2 (versioned params) ---
    # ``S_version`` keeps its capital S: the normative provenance field name
    # (DOC-SARIF §5/§6/§8 — capital S is load-bearing for canonical key order).
    S_version: str
    env_digest: str
    # --- INV-5 (conditional canonicality) ---
    cpg_order_hash: str  # hex
    fingerprint_class: str  # "strong" | "weak"
    slice_fingerprint: str  # hex
    # --- detection content ---
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
    # --- optional ---
    witness_blob_uri: str | None
    spec_provenance: str | None


@dataclass(frozen=True)
class _Finding:
    """A concrete, immutable :class:`WorkerFinding` for tests and adapters.

    Importing :class:`WorkerFinding` for static typing does not give callers an
    instantiable record; this is the shipped concrete one (the future
    CMP-ORCH-03 ``Finding`` will satisfy the Protocol independently). Validation
    of missing / empty / out-of-domain fields lives in :func:`normalize`
    (fail-fast at emission), NOT in this constructor, so a deliberately broken
    finding can be constructed and fed to the emitter (negative-control (a)).
    """

    origin: Origin
    determinism_partition: Origin
    engine: str
    S_version: str  # normative provenance field name (capital S; DOC-SARIF §5/§6)
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


# ---------------------------------------------------------------------------
# Output types (DOC-CMP-FND-01 §3.1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SARIFRun:
    """One canonical SARIF Run for a single partition."""

    partition: Partition
    canonical_bytes: bytes  # wire-canonical UTF-8 JSON of THIS run object (no LF)
    sarif_hash: str  # sha256 hex of canonical_bytes — fed to CMP-FND-03 link 8
    result_count: int


@dataclass(frozen=True)
class SARIFLog:
    """The normative two-Run log (DOC-SARIF §4). One per scan."""

    runs: tuple[SARIFRun, SARIFRun]  # (core, oracle), in this order
    canonical_bytes: bytes  # full two-run log + single trailing LF
    sarif_hash: str  # sha256 hex of the full two-run log canonical_bytes


# ---------------------------------------------------------------------------
# Canonical serialisation (DOC-SARIF §3 rules 1-8)
# ---------------------------------------------------------------------------


def _canonical_serialize(obj: object) -> bytes:
    """Serialise ``obj`` to the wire-canonical form (DOC-SARIF §3).

    Rule 1 (key ordering): ``sort_keys=True`` sorts every object's keys in
    lexicographic Unicode-code-point order. Rule 2 (minified): tight separators,
    no whitespace. Rule 4 (encoding): ``ensure_ascii=False`` so non-ASCII stays
    as literal UTF-8 bytes; the bytes are UTF-8 encoded. Rule 5 (numbers):
    integers are emitted base-10 by ``json``; we never emit floats (all numeric
    fields are integer line/column positions), so the shortest-round-trip-float
    rule is vacuously satisfied. No trailing LF is added here — the caller adds
    exactly one LF to the full log (rule 3).
    """
    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# Pre-emit invariant validation (DOC-CMP-FND-01 §7.1) — fail-fast in normalize()
# ---------------------------------------------------------------------------


def _require_nonempty_str(value: object, field: str, *, code: str) -> str:
    """A required string provenance field must be a non-empty ``str``.

    Raises :class:`InvariantViolation` (never silently defaults) — this is the
    fail-fast that negative-control (a) exercises.
    """
    if not isinstance(value, str) or value == "":
        raise InvariantViolation(
            f"finding.{field} is required and must be a non-empty string "
            f"(got {value!r}); refusing to emit a finding with a null/blank "
            f"provenance field",
            code=code,
        )
    return value


def _validate_finding(f: WorkerFinding) -> None:
    """Fail-fast pre-emit validation of one worker finding (DOC §7.1).

    Guarantees every required ``scanipy.*`` Result property is present, non-null,
    and in its domain BEFORE any byte is emitted. A failure halts the whole
    emission (no partial SARIF).
    """
    # INV-1 — origin / determinism_partition / engine present + in domain.
    origin = _require_nonempty_str(f.origin, "origin", code="invariant_inv1_violation")
    if origin not in _ORIGINS:
        raise InvariantViolation(
            f"finding.origin={origin!r} is not a valid partition "
            f"(must be one of {sorted(_ORIGINS)}; 'mixed' is never finding-level)",
            code="invariant_inv1_violation",
        )
    dp = _require_nonempty_str(
        f.determinism_partition, "determinism_partition", code="invariant_inv1_violation"
    )
    if dp not in _ORIGINS:
        raise InvariantViolation(
            f"finding.determinism_partition={dp!r} is not a valid partition",
            code="invariant_inv1_violation",
        )
    engine = _require_nonempty_str(f.engine, "engine", code="invariant_inv1_violation")
    if engine not in _ENGINES:
        raise InvariantViolation(
            f"finding.engine={engine!r} is not a valid engine (must be one of {sorted(_ENGINES)})",
            code="invariant_inv1_violation",
        )

    # INV-2 — S_version / env_digest present + non-empty.
    _require_nonempty_str(f.S_version, "S_version", code="invariant_inv2_violation")
    _require_nonempty_str(f.env_digest, "env_digest", code="invariant_inv2_violation")

    # INV-5 — cpg_order_hash present; fingerprint_class in domain.
    _require_nonempty_str(f.cpg_order_hash, "cpg_order_hash", code="invariant_inv5_violation")
    fp = _require_nonempty_str(
        f.fingerprint_class, "fingerprint_class", code="invariant_inv5_violation"
    )
    if fp not in _FP_CLASSES:
        raise InvariantViolation(
            f"finding.fingerprint_class={fp!r} must be 'strong' or 'weak'",
            code="invariant_inv5_violation",
        )

    # Remaining mandatory Result properties (DOC-SARIF §6).
    _require_nonempty_str(f.slice_fingerprint, "slice_fingerprint", code="invariant_inv5_violation")
    _require_nonempty_str(f.rule_id, "rule_id", code="invariant_inv1_violation")
    severity = _require_nonempty_str(f.severity, "severity", code="invariant_inv1_violation")
    if severity not in _SEVERITIES:
        raise InvariantViolation(
            f"finding.severity={severity!r} must be one of {sorted(_SEVERITIES)}",
            code="invariant_inv1_violation",
        )
    _require_nonempty_str(f.class_, "class_", code="invariant_inv1_violation")
    status = _require_nonempty_str(f.status, "status", code="invariant_inv1_violation")
    if status not in _STATUSES:
        raise InvariantViolation(
            f"finding.status={status!r} must be one of {sorted(_STATUSES)}",
            code="invariant_inv1_violation",
        )
    pc = _require_nonempty_str(
        f.precondition_status, "precondition_status", code="invariant_inv1_violation"
    )
    if pc not in _PRECONDITIONS:
        raise InvariantViolation(
            f"finding.precondition_status={pc!r} must be one of {sorted(_PRECONDITIONS)}",
            code="invariant_inv1_violation",
        )

    # Region positions must be ints (they are part of the canonical sort key and
    # the SARIF region; a string would corrupt byte-identity and ordering).
    for field, val in (
        ("start_line", f.start_line),
        ("start_col", f.start_col),
        ("end_line", f.end_line),
        ("end_col", f.end_col),
    ):
        if not isinstance(val, int) or isinstance(val, bool):
            raise InvariantViolation(
                f"finding.{field} must be an int (got {val!r})",
                code="invariant_inv1_violation",
            )


# ---------------------------------------------------------------------------
# Result construction (DOC-SARIF §6 / DOC-CMP-FND-01 Appendix A)
# ---------------------------------------------------------------------------


def _to_result(f: WorkerFinding) -> dict[str, object]:
    """Project one worker finding onto a SARIF Result object (pre-serialisation,
    key order is irrelevant here — the serialiser sorts keys).

    The INV-5 annotation is ALWAYS the imported constant, never ``f``'s own
    annotation field and never reconstructed from substrings.
    """
    properties: dict[str, object] = {
        "scanipy.origin": f.origin,
        "scanipy.S_version": f.S_version,
        "scanipy.env_digest": f.env_digest,
        "scanipy.cpg_order_hash": f.cpg_order_hash,
        "scanipy.cpg_order_hash_annotation": CPG_ORDER_HASH_ANNOTATION,
        "scanipy.fingerprint_class": f.fingerprint_class,
        "scanipy.slice_fingerprint": f.slice_fingerprint,
        "scanipy.determinism_partition": f.determinism_partition,
        "scanipy.engine": f.engine,
        "scanipy.precondition_status": f.precondition_status,
        "scanipy.class": f.class_,
        "scanipy.severity": f.severity,
        "scanipy.status": f.status,
    }
    # Nullable properties: emitted only when present (DOC-SARIF §6 "Nullable").
    if f.spec_provenance:
        properties["scanipy.spec_provenance"] = f.spec_provenance
    if f.witness_blob_uri:
        properties["scanipy.witness_blob_uri"] = f.witness_blob_uri

    return {
        "ruleId": f.rule_id,
        "level": _SEVERITY_TO_LEVEL[f.severity],
        "message": {"text": f.message},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": f.uri},
                    "region": {
                        "startLine": f.start_line,
                        "startColumn": f.start_col,
                        "endLine": f.end_line,
                        "endColumn": f.end_col,
                    },
                },
            }
        ],
        "fingerprints": {
            "scanipy.cpg_order_hash/v1": f.cpg_order_hash,
            "scanipy.slice_fingerprint/v1": f.slice_fingerprint,
        },
        "properties": properties,
    }


def _result_sort_key(result: dict[str, object]) -> tuple[str, str, str, int, str, bytes]:
    """Canonical ascending result-order key (DOC-SARIF §7) + total-order tiebreak.

    The four documented keys are ``(cpg_order_hash, rule_id, uri, start_line)``.
    They can tie (two findings on the same line of the same rule with the same
    canonical hash), so a deterministic total-order tiebreaker is appended:
    ``slice_fingerprint`` then the full canonical serialisation of the Result.
    Without the tiebreaker, byte-identity would be non-deterministic on a
    collision (the advisor's collision trap).
    """
    properties = result["properties"]
    assert isinstance(properties, dict)
    locations = result["locations"]
    assert isinstance(locations, list)
    region = locations[0]["physicalLocation"]["region"]
    return (
        str(properties["scanipy.cpg_order_hash"]),
        str(result["ruleId"]),
        str(locations[0]["physicalLocation"]["artifactLocation"]["uri"]),
        int(region["startLine"]),
        str(properties["scanipy.slice_fingerprint"]),
        _canonical_serialize(result),
    )


def _build_run(
    partition: Partition,
    results: list[dict[str, object]],
    *,
    scan_id: UUID,
    snapshot_id: UUID,
    codebase_id: UUID,
    commit_sha: str,
    S_version: str,  # noqa: N803  (INV-2 provenance field name — normative)
    env_digest: str,
    precondition_status: str,
    llm_triage_flag: bool,
) -> dict[str, object]:
    """Build one SARIF Run object (DOC-SARIF §5) for an already-sorted result list.

    ``tool.driver.rules`` is populated deterministically: one rule definition per
    distinct ``ruleId`` referenced by the run's results, sorted ascending
    (DOC-SARIF §6.2 — every referenced rule MUST have a definition in the same
    run). No ``invocations`` time fields are emitted: ``normalize`` takes no clock
    input, so emitting a timestamp would break byte-identity (TST-INV-1-FND-01).
    """
    rule_ids = sorted({str(r["ruleId"]) for r in results})
    rules = [{"id": rid, "name": rid} for rid in rule_ids]
    return {
        "tool": {
            "driver": {
                "name": TOOL_NAME,
                "version": TOOL_VERSION,
                "informationUri": TOOL_INFORMATION_URI,
                "rules": rules,
            }
        },
        "properties": {
            "scanipy.partition": partition,
            "scanipy.scan_id": str(scan_id),
            "scanipy.snapshot_id": str(snapshot_id),
            "scanipy.codebase_id": str(codebase_id),
            "scanipy.commit_sha": commit_sha,
            "scanipy.S_version": S_version,
            "scanipy.env_digest": env_digest,
            "scanipy.precondition_status": precondition_status,
            "scanipy.llm_triage_flag": llm_triage_flag,
        },
        "results": results,
    }


# ---------------------------------------------------------------------------
# Structural SARIF v2.1.0 validation (DOC-SARIF §11 / AC-FND-01a)
# ---------------------------------------------------------------------------
#
# DESIGN NOTE (build-ahead / dependency scope). The DOC's stated validation
# target is "the OASIS SARIF v2.1.0 JSON schema". That schema is ~600 KB and is
# NOT vendored in-repo; `jsonschema` is not a declared `[dev]` dependency and CI
# installs only `.[dev]`. Pulling in either would expand global CI scope from a
# single-component PR (pyproject.toml is outside this component's declared file
# set). Per CLAR-SARIF-01 (DEFERRED) the hosted schema URL is not pinned and the
# extension schema is meant to be vendored "meanwhile". This validator therefore
# performs structural SARIF-2.1.0 **shape** validation in pure Python (the task's
# explicit ask: "SARIF-2.1.0 schema-shape validation per the DOC's stated
# method"): it checks the document model `normalize` emits — `$schema`/`version`,
# the two Runs, `tool.driver`, every Result's standard SARIF fields, and every
# required `scanipy.*` extension property (DOC-SARIF §11). Swapping in the OASIS
# jsonschema validator once vendored is a drop-in replacement behind this same
# `list[str]` signature.


def _validate_result_shape(result: object, run_idx: int, res_idx: int) -> list[str]:
    """Validate one Result against the SARIF v2.1.0 + Scanipy extension shape."""
    errors: list[str] = []
    where = f"runs[{run_idx}].results[{res_idx}]"
    if not isinstance(result, dict):
        return [f"{where}: result is not an object"]

    # Standard SARIF v2.1.0 Result fields.
    if not isinstance(result.get("ruleId"), str) or not result["ruleId"]:
        errors.append(f"{where}.ruleId: missing or not a non-empty string")
    if result.get("level") not in {"none", "note", "warning", "error"}:
        errors.append(f"{where}.level: not a valid SARIF level")
    message = result.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("text"), str):
        errors.append(f"{where}.message.text: missing or not a string")
    locations = result.get("locations")
    if not isinstance(locations, list) or not locations:
        errors.append(f"{where}.locations: missing or empty")
    else:
        region = (
            locations[0].get("physicalLocation", {}).get("region", {})
            if isinstance(locations[0], dict)
            else {}
        )
        for key in ("startLine", "startColumn", "endLine", "endColumn"):
            if not isinstance(region.get(key), int) or isinstance(region.get(key), bool):
                errors.append(f"{where}.region.{key}: missing or not an int")
        artifact = (
            locations[0].get("physicalLocation", {}).get("artifactLocation", {})
            if isinstance(locations[0], dict)
            else {}
        )
        if not isinstance(artifact.get("uri"), str) or not artifact.get("uri"):
            errors.append(f"{where}.artifactLocation.uri: missing or not a string")

    # SARIF-native fingerprints (DOC-SARIF §6.1).
    fingerprints = result.get("fingerprints")
    if not isinstance(fingerprints, dict):
        errors.append(f"{where}.fingerprints: missing")
    else:
        for fp_key in ("scanipy.cpg_order_hash/v1", "scanipy.slice_fingerprint/v1"):
            if not isinstance(fingerprints.get(fp_key), str) or not fingerprints.get(fp_key):
                errors.append(f"{where}.fingerprints[{fp_key!r}]: missing or not a string")

    # Scanipy extension — every mandatory Result property (DOC-SARIF §6 / §11).
    properties = result.get("properties")
    if not isinstance(properties, dict):
        return [*errors, f"{where}.properties: missing"]
    required = (
        "scanipy.origin",
        "scanipy.S_version",
        "scanipy.env_digest",
        "scanipy.cpg_order_hash",
        "scanipy.cpg_order_hash_annotation",
        "scanipy.fingerprint_class",
        "scanipy.slice_fingerprint",
        "scanipy.determinism_partition",
        "scanipy.engine",
        "scanipy.precondition_status",
        "scanipy.class",
        "scanipy.severity",
        "scanipy.status",
    )
    for key in required:
        val = properties.get(key)
        if not isinstance(val, str) or val == "":
            errors.append(f"{where}.properties[{key!r}]: missing or empty (RULE-6/INV-1/2/5)")
    # The INV-5 annotation literal MUST be the exact constant (DOC-SARIF §11 const).
    if properties.get("scanipy.cpg_order_hash_annotation") != CPG_ORDER_HASH_ANNOTATION:
        errors.append(
            f"{where}.properties['scanipy.cpg_order_hash_annotation']: "
            f"not the literal {CPG_ORDER_HASH_ANNOTATION!r} (INV-5)"
        )
    if properties.get("scanipy.origin") not in _ORIGINS:
        errors.append(f"{where}.properties['scanipy.origin']: not a valid partition (INV-1)")
    return errors


def _validate_run_shape(run: object, run_idx: int, expected_partition: str) -> list[str]:
    """Validate one Run against the SARIF v2.1.0 + Scanipy extension shape."""
    errors: list[str] = []
    where = f"runs[{run_idx}]"
    if not isinstance(run, dict):
        return [f"{where}: run is not an object"]

    driver = run.get("tool", {}).get("driver", {}) if isinstance(run.get("tool"), dict) else {}
    if not isinstance(driver, dict) or driver.get("name") != TOOL_NAME:
        errors.append(f"{where}.tool.driver.name: missing or != {TOOL_NAME!r}")
    rules = driver.get("rules") if isinstance(driver, dict) else None
    rule_ids = (
        {r.get("id") for r in rules if isinstance(r, dict)} if isinstance(rules, list) else set()
    )

    properties = run.get("properties")
    if not isinstance(properties, dict):
        errors.append(f"{where}.properties: missing")
    else:
        if properties.get("scanipy.partition") != expected_partition:
            errors.append(
                f"{where}.properties['scanipy.partition']: != {expected_partition!r} (DOC-SARIF §4)"
            )
        for key in (
            "scanipy.scan_id",
            "scanipy.snapshot_id",
            "scanipy.codebase_id",
            "scanipy.commit_sha",
            "scanipy.S_version",
            "scanipy.env_digest",
            "scanipy.precondition_status",
        ):
            val = properties.get(key)
            if not isinstance(val, str) or val == "":
                errors.append(f"{where}.properties[{key!r}]: missing or empty (INV-2/RULE-6)")
        if not isinstance(properties.get("scanipy.llm_triage_flag"), bool):
            errors.append(f"{where}.properties['scanipy.llm_triage_flag']: not a bool")

    results = run.get("results")
    if not isinstance(results, list):
        return [*errors, f"{where}.results: missing or not an array"]
    for res_idx, result in enumerate(results):
        errors.extend(_validate_result_shape(result, run_idx, res_idx))
        # §6.2: every referenced ruleId MUST have a definition in this run.
        if isinstance(result, dict) and result.get("ruleId") not in rule_ids:
            errors.append(
                f"{where}.results[{res_idx}].ruleId={result.get('ruleId')!r}: "
                f"no matching tool.driver.rules entry (DOC-SARIF §6.2)"
            )
    return errors


def validate_sarif_210(canonical_bytes: bytes) -> list[str]:
    """Structurally validate a serialised SARIF log against the SARIF v2.1.0 +
    Scanipy extension shape (DOC-SARIF §11). Returns ``[]`` on success, else a
    list of human-readable error strings.

    See the DESIGN NOTE above for why this is in-house structural validation
    rather than the OASIS jsonschema validator (CLAR-SARIF-01 / CI dependency
    scope). The signature (``bytes -> list[str]``, ``[]`` == valid) is the same
    one the OASIS validator would expose, so it is a drop-in swap once the schema
    is vendored.
    """
    errors: list[str] = []
    try:
        doc = json.loads(canonical_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return [f"document is not valid JSON: {exc}"]

    if not isinstance(doc, dict):
        return ["top-level SARIF log is not an object"]
    if doc.get("$schema") != SARIF_SCHEMA_URI:
        errors.append(f"$schema: != {SARIF_SCHEMA_URI!r}")
    if doc.get("version") != SARIF_VERSION:
        errors.append(f"version: != {SARIF_VERSION!r}")
    runs = doc.get("runs")
    if not isinstance(runs, list) or len(runs) != 2:
        return [*errors, "runs: must be a 2-element array (core, oracle) per DOC-SARIF §4"]
    errors.extend(_validate_run_shape(runs[0], 0, "core"))
    errors.extend(_validate_run_shape(runs[1], 1, "oracle"))
    return errors


# ---------------------------------------------------------------------------
# Post-serialisation canonical sanity check (DOC-CMP-FND-01 §7.1)
# ---------------------------------------------------------------------------


def _assert_canonical_order(canonical_bytes: bytes) -> None:
    """Re-parse the serialised log and confirm the serialiser did NOT reorder:
    within each Run, results are ascending by the documented key tuple
    (DOC-SARIF §7). Raises :class:`CanonicalEmissionFailure` on disagreement.
    """
    doc = json.loads(canonical_bytes)
    for run in doc["runs"]:
        keys = [_result_sort_key(r) for r in run["results"]]
        if keys != sorted(keys):
            raise CanonicalEmissionFailure(
                f"results in run partition={run['properties']['scanipy.partition']!r} "
                f"are not in canonical order (DOC-SARIF §7)"
            )


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def _sorted_results(findings: frozenset[WorkerFinding], origin: Origin) -> list[dict[str, object]]:
    """Validate + project + canonically sort the findings of one partition."""
    selected = [f for f in findings if f.origin == origin]
    for f in selected:
        _validate_finding(f)
    results = [_to_result(f) for f in selected]
    results.sort(key=_result_sort_key)
    return results


def normalize(
    findings: frozenset[WorkerFinding],
    *,
    scan_id: UUID,
    snapshot_id: UUID,
    codebase_id: UUID,
    commit_sha: str,
    S_version: str,  # noqa: N803  (INV-2 provenance field name — normative)
    env_digest: str,
    precondition_status: PreconditionStatus,
    llm_triage_flag: bool,
) -> SARIFLog:
    """Normative emitter (DOC-SARIF §4): returns ONE SARIFLog containing TWO Runs
    (core first, oracle second). Discharges AC-FND-01a + AC-FND-01b + INV-1/2/5.

    PURE: same inputs ⇒ byte-identical ``SARIFLog.canonical_bytes``. No I/O. No
    clock reads. No global state.

    Raises :class:`InvariantViolation` (fail-fast, no partial emit) if any
    finding is missing a required provenance field; :class:`SARIFSchemaViolation`
    if the serialised log fails the SARIF v2.1.0 structural validator;
    :class:`CanonicalEmissionFailure` if the post-serialisation order check fails.
    """
    # The four required run-level provenance params (INV-2) must be present.
    _require_nonempty_str(commit_sha, "commit_sha", code="invariant_inv2_violation")
    _require_nonempty_str(S_version, "S_version", code="invariant_inv2_violation")
    _require_nonempty_str(env_digest, "env_digest", code="invariant_inv2_violation")

    core_results = _sorted_results(findings, "deterministic-core")
    oracle_results = _sorted_results(findings, "oracle-passthrough")

    core_run_obj = _build_run(
        "core",
        core_results,
        scan_id=scan_id,
        snapshot_id=snapshot_id,
        codebase_id=codebase_id,
        commit_sha=commit_sha,
        S_version=S_version,
        env_digest=env_digest,
        precondition_status=precondition_status,
        llm_triage_flag=llm_triage_flag,
    )
    oracle_run_obj = _build_run(
        "oracle",
        oracle_results,
        scan_id=scan_id,
        snapshot_id=snapshot_id,
        codebase_id=codebase_id,
        commit_sha=commit_sha,
        S_version=S_version,
        env_digest=env_digest,
        precondition_status=precondition_status,
        llm_triage_flag=llm_triage_flag,
    )

    log_obj = {
        "$schema": SARIF_SCHEMA_URI,
        "version": SARIF_VERSION,
        "runs": [core_run_obj, oracle_run_obj],
    }
    log_bytes = _canonical_serialize(log_obj) + b"\n"  # DOC-SARIF §3 rule 3: single LF

    # Halt-on-failure validation (DOC §7.1): schema shape, then canonical order.
    schema_errors = validate_sarif_210(log_bytes)
    if schema_errors:
        raise SARIFSchemaViolation("; ".join(schema_errors))
    _assert_canonical_order(log_bytes)

    core_bytes = _canonical_serialize(core_run_obj)
    oracle_bytes = _canonical_serialize(oracle_run_obj)
    runs = (
        SARIFRun(
            partition="core",
            canonical_bytes=core_bytes,
            sarif_hash=hashlib.sha256(core_bytes).hexdigest(),
            result_count=len(core_results),
        ),
        SARIFRun(
            partition="oracle",
            canonical_bytes=oracle_bytes,
            sarif_hash=hashlib.sha256(oracle_bytes).hexdigest(),
            result_count=len(oracle_results),
        ),
    )
    return SARIFLog(
        runs=runs,
        canonical_bytes=log_bytes,
        sarif_hash=hashlib.sha256(log_bytes).hexdigest(),
    )


def normalize_split(
    findings: frozenset[WorkerFinding],
    *,
    scan_id: UUID,
    snapshot_id: UUID,
    codebase_id: UUID,
    commit_sha: str,
    S_version: str,  # noqa: N803
    env_digest: str,
    precondition_status: PreconditionStatus,
    llm_triage_flag: bool,
) -> tuple[SARIFRun, SARIFRun]:
    """Alternate emitter producing the two partitions as separate single-Run
    SARIF files (``*-core.sarif``, ``*-oracle.sarif``) for customer SARIF
    download (DOC-SARIF §4 permitted alternate). Every canonical/validation
    requirement of :func:`normalize` applies independently to each file.

    Returns ``(core_run, oracle_run)`` where each ``SARIFRun.canonical_bytes`` is
    a FULL standalone single-Run SARIF log (``$schema``/``version``/``runs``)
    with its own trailing LF.
    """

    def _one_file(partition: Partition, origin: Origin, expected: str) -> SARIFRun:
        results = _sorted_results(findings, origin)
        run_obj = _build_run(
            partition,
            results,
            scan_id=scan_id,
            snapshot_id=snapshot_id,
            codebase_id=codebase_id,
            commit_sha=commit_sha,
            S_version=S_version,
            env_digest=env_digest,
            precondition_status=precondition_status,
            llm_triage_flag=llm_triage_flag,
        )
        # The split file is a single-partition document (DOC-SARIF §4 permitted
        # alternate): a one-Run SARIF log. Validate that run's shape directly
        # (the two-Run ``validate_sarif_210`` shape check does not apply here).
        file_obj = {
            "$schema": SARIF_SCHEMA_URI,
            "version": SARIF_VERSION,
            "runs": [run_obj],
        }
        file_bytes = _canonical_serialize(file_obj) + b"\n"
        run_errors = _validate_run_shape(run_obj, 0, expected)
        if run_errors:
            raise SARIFSchemaViolation("; ".join(run_errors))
        return SARIFRun(
            partition=partition,
            canonical_bytes=file_bytes,
            sarif_hash=hashlib.sha256(file_bytes).hexdigest(),
            result_count=len(results),
        )

    return (
        _one_file("core", "deterministic-core", "core"),
        _one_file("oracle", "oracle-passthrough", "oracle"),
    )
