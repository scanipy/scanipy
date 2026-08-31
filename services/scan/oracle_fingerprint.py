"""Fingerprint an **oracle-passthrough** finding that arrives as ``(file, line)``.

A Semgrep / CodeQL finding has no IFDS witness — it arrives as a source
location. This module bridges that location to the CMP-CORE-02 identity
machinery (:func:`analysis.fingerprint.compute_slice_fingerprint`, Algorithm 3)
so an oracle finding can carry the same refactor-stable
``slice_fingerprint`` + ``fingerprint_class`` identity a core finding carries,
instead of a file/line identity that dies on the first reformat.

How it works: the reported ``(filename, line)`` is resolved to ONE CPG node (the
sink) via the location side-table; that node alone is handed to Algorithm 3 as a
single-node witness ``(sink,)``. Algorithm 3's backward interprocedural slice
then takes the **reverse-reachable cone from ``witness[-1]``** over the
CFG/CALL/PDG edge kinds, so a one-node witness still yields the full backward
dependence slice — the same slice a core finding's multi-node witness would
produce for that sink. The location is used ONLY to pick that node.

---
## Non-negotiables this module is written against

**(1) The location NEVER enters the fingerprint.** ``filename`` / ``line`` /
``column`` are LOOKUP KEYS and nothing else. They are not hashed, not passed to
:func:`~analysis.fingerprint.compute_slice_fingerprint`, and not reachable from
it (it consumes ``witness`` only, and ``analysis.ordering.CPGNode`` carries no
location fields at all). Mixing a location into the hash would manufacture a
fake "invariance" — two scans of an unmodified file agreeing because their line
numbers agree — and would make the product's central claim a lie. The executable
form of this constraint is
``tests/unit/test_oracle_fingerprint.py::test_fingerprint_ignores_source_locations_entirely``:
same graph, completely different line numbers, identical fingerprint.

**(2) An oracle finding stays ``origin="oracle-passthrough"``.** Having a
fingerprint is not having a determinism theorem. Property (a) (byte-identical
SARIF over ``(source, S, Env)``) covers ``origin=deterministic-core`` findings
only; oracle findings get digest-stability + a measured reproduction rate
(``.claude/rules/05-determinism.md``, INV-1). This module returns a
:class:`~analysis.fingerprint.SliceFingerprintResult` and *no* origin: the caller
(CMP-ORCH-03) owns the label and must keep it ``oracle-passthrough``. Nothing
here may be read as promoting a finding into the core partition.

**(3) Only the invariances the implementation actually has.** Of Algorithm 3's
five named normalisation passes, exactly two do real work on the shipped minimal
CPG model: alpha-renaming of locals (pass 1) and FQN normalisation for
file-move / package-rename (pass 5). The formatting pass and the canonical
topo-sort pass are documented NO-OPS, and the pure-extract summary-inlining pass
deliberately normalises nothing (so *every* extract — pure or impure — flips the
fingerprint; the one-sided-safe choice, see
:func:`analysis.fingerprint._summary_inline_pure_extract`). This module claims
alpha-rename and file-move/package-rename invariance and NOTHING ELSE.

**(4) Synthetic fixtures do not prove real-CPG invariance.** The unit tests
build small hand-written CPGs. They prove the *mechanism* — that a single-node
witness drives Algorithm 3, that a rename does not flip the hash, that a
dataflow change does, that an unresolvable location fails closed. They do NOT
prove that a real Joern-parsed repository survives a real refactor: that needs
CMP-CORP-REFAC-01 at corpus scale, which is not this module's evidence to claim.

---
Track A contract (``analysis.cpg_ingest.mapper.map_export_with_locations``)
supplies the ``Mapping[NodeId, SourceLocation]`` side-table this module consumes.
It is referenced STRUCTURALLY (see :class:`SourceLocation` below), so this module
imports nothing from the mapper and is green independently of it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from analysis.fingerprint import SliceFingerprintResult, compute_slice_fingerprint
from analysis.ordering import CPG, DEFAULT_B, DEFAULT_T, Duration, NodeId


class SourceLocation(Protocol):
    """The source position of a CPG node — a **lookup key only** (see §1 above).

    Structural stand-in for Track A's concrete
    ``analysis.cpg_ingest.mapper.SourceLocation`` dataclass
    (``filename: str`` — ``""`` if unknown; ``line: int`` — 1-based, ``0`` =
    unknown; ``column: int`` — ``0`` = unknown), which satisfies this Protocol
    structurally when it lands. Declaring the shape here rather than importing it
    keeps this module and its tests self-contained: no import cycle, no
    dependency on a branch that has not merged, and any other producer of a
    location side-table works unchanged.
    """

    @property
    def filename(self) -> str: ...

    @property
    def line(self) -> int: ...

    @property
    def column(self) -> int: ...


@dataclass(frozen=True)
class OracleSliceRequest:
    """A witness carrier for an oracle finding — satisfies
    :class:`analysis.fingerprint.SliceRequest` structurally.

    This exists so an oracle finding is NEVER shoehorned into
    :class:`analysis.ifds.solver.Finding`, whose
    ``origin: Literal["deterministic-core"]`` / ``engine: Literal["ifds", "ide"]``
    declarations are a deliberate type-level INV-1 honesty guard. An oracle
    finding is ``origin="oracle-passthrough"``, ``engine="semgrep"``; it carries
    a witness and nothing more, which is exactly what Algorithm 3 needs.

    Carrying a witness is not a partition claim: see §2 of the module docstring.
    """

    witness: tuple[NodeId, ...]


def locate_sink_node(
    cpg: CPG,
    locations: Mapping[NodeId, SourceLocation],
    *,
    filename: str,
    line: int,
) -> NodeId | None:
    """Best CPG node for a source ``file:line``, or ``None`` when unresolvable.

    Candidates are the nodes that are present in BOTH ``cpg`` and ``locations``
    (a node absent from ``cpg`` could not be sliced anyway — restricting here
    means the returned id can never trip
    :class:`~analysis.fingerprint.WitnessNotInCPG` downstream) whose location
    matches ``filename`` EXACTLY and whose ``line`` equals ``line`` exactly.

    Selection among the candidates on that line, in priority order:

    1. a ``CALL`` node — an oracle taint/injection finding is reported at a call
       site, and the call is the node whose backward cone is the finding's
       dependence slice;
    2. otherwise the *nearest* node on the line, read as the earliest column
       (a node with the documented ``column == 0`` "unknown" sentinel sorts
       AFTER every node with a real column, so a known position always wins);
    3. ties broken by ascending ``node_id``.

    The full sort key is ``(kind != "CALL", column == 0, column, node_id)``.
    ``node_id`` is unique, so the key is total: the same inputs always select the
    same node regardless of ``Mapping`` iteration order (asserted by
    ``test_locate_sink_node_is_deterministic``).

    NO fuzzy matching. There is no nearest-*line* fallback and no path
    normalisation (a Semgrep-relative path and a Joern ``filename`` that differ
    textually do not match). An unresolvable location returns ``None`` — the
    caller then has an oracle finding without a slice fingerprint, which is a
    supported state (``witness_blob_uri`` is nullable "for oracle findings
    without a slice", ``.claude/rules/02-provenance.md``) — rather than a
    silently wrong node, which would attach one finding's identity to another
    finding's code.
    """
    if line <= 0 or not filename:
        return None

    in_cpg = {n.node_id: n.kind for n in cpg.nodes}
    candidates: list[tuple[bool, bool, int, NodeId]] = []
    for node_id, loc in locations.items():
        kind = in_cpg.get(node_id)
        if kind is None:
            continue
        if loc.filename != filename or loc.line != line:
            continue
        candidates.append((kind != "CALL", loc.column == 0, loc.column, node_id))

    if not candidates:
        return None
    return min(candidates)[3]


def fingerprint_oracle_finding(
    cpg: CPG,
    locations: Mapping[NodeId, SourceLocation],
    *,
    filename: str,
    line: int,
    B: int = DEFAULT_B,  # noqa: N803 ((B, T) budget symbols are the public contract)
    T: Duration = DEFAULT_T,  # noqa: N803
) -> SliceFingerprintResult | None:
    """Locate the sink, build a single-node witness, compute Algorithm 3.

    Returns ``None`` — never a degenerate or invented fingerprint — when
    ``(filename, line)`` does not resolve to a CPG node (see
    :func:`locate_sink_node`).

    The returned :class:`~analysis.fingerprint.SliceFingerprintResult` carries
    ``fingerprint_class`` and the INV-5 ``cpg_order_hash_annotation`` verbatim
    from Algorithm 3; a ``weak`` result is a same-source identity only and MUST
    NOT be auto-suppressed across a refactor
    (:func:`analysis.fingerprint.eligible_for_baseline_suppression`).

    It does NOT carry an ``origin``: the caller keeps the finding
    ``origin="oracle-passthrough"`` (§2 of the module docstring). Pure: same
    inputs ⇒ same output, no I/O.
    """
    sink = locate_sink_node(cpg, locations, filename=filename, line=line)
    if sink is None:
        return None
    # Single-node witness: Algorithm 3's backward slice is the reverse-reachable
    # cone from ``witness[-1]``, so the sink alone recovers the dependence slice.
    # The location is NOT threaded any further than this lookup.
    return compute_slice_fingerprint(OracleSliceRequest(witness=(sink,)), cpg, B=B, T=T)


__all__ = [
    "OracleSliceRequest",
    "SourceLocation",
    "fingerprint_oracle_finding",
    "locate_sink_node",
]
