"""CMP-SNAP-05 (CPG-ingest sub-scope, CLAR-SNAP-03/05) — Joern export -> CPG mapper.

Maps the flat JSON node/edge array produced by the in-image CPGQL export script
(``workers/snapshot/joern-scripts/export_cpg.sc``, wired via
:mod:`analysis.cpg_ingest.joern_frontend`) into an :class:`analysis.ordering.CPG`.

**This module owns the plan's Provenance-section obligation verbatim**
(``crispy-dazzling-book.md`` "Provenance / INV concerns"): Algorithm 5
(``analysis/ordering.py``) assigns ``node_id`` by **insertion order** into
``CPG.add_node``, and that insertion order is the seed of the ``weak``-path
tie-break key (``ordering.py`` ``_stable_order_fallback``). If this mapper ever
trusted the raw order of Joern's export ``nodes``/``edges`` arrays, a
non-deterministic Joern internal pass (threaded/overlay parsing) could leak
straight into ``cpg_order_hash`` and break the CP-05 core-partition
byte-identical-SARIF guarantee. So this module **never** iterates
``export["nodes"]`` / ``export["edges"]`` in their given order when deciding
emission order: it rebuilds the AST tree from the raw ``AST``-kind edges,
performs its OWN deterministic depth-first walk (children sorted by
``(filename, lineNumber, columnNumber, raw_id)`` at every level — the raw
``id`` is only ever a last-resort, deterministic string tie-break, never a
signal of "the order Joern happened to emit"), and only THEN calls
``CPG.add_node`` in the resulting global order:
``(filename, lineNumber, columnNumber, ast_preorder_index)``. Edges are
re-derived from the same node-id remapping and re-sorted by
``(kind, src_node_id, dst_node_id)`` before ``CPG.add_edge`` — so the final
``CPG.edges`` list is also independent of raw array order.

``structural_path`` and ``enclosing_decl_fqn`` (the third INV-5-load-bearing
field alongside node-id order) are likewise **computed here, not read from
Joern** — removing the whole axis of dependency on Joern's own notion of
"declaration" or "path" stability the plan calls out.

---
## CLAR-SNAP-05 property -> CPGNode field mapping table (this module's contract)

Every raw node object in the export JSON carries (at most) the following
Joern-property-shaped keys (``RawJoernNode`` below); this table is the
authoritative mapping from those raw properties to
:class:`analysis.ordering.CPGNode` fields. **Nothing else is trusted from the
raw export** for the three order-sensitive fields (node_id / structural_path /
enclosing_decl_fqn) per the Provenance section above.

* ``node_id`` <- assigned by ``CPG.add_node`` from OUR OWN deterministic
  emission order (never Joern's raw array position).
* ``kind`` <- raw ``.label`` verbatim (Joern node type: ``METHOD`` / ``CALL``
  / ``IDENTIFIER`` / ``LITERAL`` / ...).
* ``operator_or_literal`` <- ``.code`` when ``label == "LITERAL"``; ``.name``
  when ``label == "CALL"`` and ``.name`` starts with ``"<operator>."``;
  otherwise ``""``.
* ``resolved_fqn`` <- ``.methodFullName`` when ``label == "CALL"``;
  ``.fullName`` when ``label in {"METHOD", "TYPE_DECL"}``; otherwise ``""``.
* ``enclosing_decl_fqn`` <- OUR OWN AST walk: the ``.fullName`` of the
  nearest ``METHOD``/``TYPE_DECL`` ancestor-or-self (never a raw Joern
  field).
* ``structural_path`` <- OUR OWN AST walk: dot-joined, 0-based
  child-position indices from the nearest ``METHOD``/``TYPE_DECL``
  ancestor-or-self (resets to ``""`` AT that declaration node itself).
  Never a raw Joern field.

``filename`` / ``lineNumber`` / ``columnNumber`` are consumed as ordering
signal AND returned as a **side-table** by :func:`map_export_with_locations`
(``dict[NodeId, SourceLocation]``) so a caller holding a real finding's
``file:line`` can resolve it to a CPG ``NodeId``. A node missing ``filename``
inherits its nearest AST ancestor's resolved filename (Joern typically stamps
``filename`` only on ``METHOD``/``TYPE_DECL``-shaped nodes and leaves it blank
on descendants — see the export script's own doc header for why); a missing
``lineNumber`` / ``columnNumber`` sorts as (and is reported as) ``0``
(documented sentinel, not a real source position).

**Source locations live ONLY in that side-table.** They are never persisted
onto :class:`analysis.ordering.CPGNode` (which has no location fields, by
design) and never enter anything hashed, canonicalised, or fingerprinted —
not the Algorithm 5 seed labels, not ``cpg_order_hash``, not
``slice_fingerprint``. That separation is what makes a finding's identity
refactor-invariant: renaming or moving a file, or inserting a line above a
sink, must not change the fingerprint. Admitting ``filename``/``lineNumber``
into any hashed field would silently destroy that property, so the side-table
is an OUTPUT ALONGSIDE the graph, never a field of it.

## CLAR-SNAP-05 edge-kind vocabulary (this module's contract)

| Raw Joern edge kind | ``CPGEdge.kind`` |
|---|---|
| ``AST``              | ``AST`` (direct passthrough) |
| ``CFG``               | ``CFG`` (direct passthrough) |
| ``CDG``               | ``PDG`` (collapsed) |
| ``REACHING_DEF``      | ``PDG`` (collapsed) |

Any other raw edge kind is **fail-closed**: :class:`UnknownEdgeKindError` is
raised rather than silently dropping or passing through an unvetted kind
string into the ``CPGEdge.kind`` vocabulary Algorithm 5 depends on. Widening
this table (e.g. admitting ``CALL`` / ``DDG`` / ``DOMINATE`` edges) is a
CLAR-SNAP-05 follow-up decision, not something this module should invent
inline (RULE-4).

## Documented schema assumptions (unverified against a real Joern install)

This mapper's raw-JSON schema is a DESIGN, not something read off a live
Joern run (no real ``joern`` binary exists in this build sandbox — see
:mod:`analysis.cpg_ingest.joern_frontend` and
``tests/cpg_ingest_fixtures.py`` for the full disclaimer).
Assumptions baked into both this mapper and the export script it pairs with:

1. Raw node ``id`` is a **JSON string** (not a JSON number) — real Joern node
   ids are ``Long``s that can exceed the 2**53 JSON-safe-integer boundary;
   the export script is designed to call ``.toString`` on the id before
   emission specifically to dodge that precision hazard.
2. ``AST`` edges are directed **parent -> child** (``src`` = parent node id,
   ``dst`` = child node id) — mirrors Joern's actual OverflowDB AST edge
   storage direction (the direction ``.astChildren`` traverses).
3. Every node reachable from a ``METHOD``/``TYPE_DECL`` root via ``AST``
   edges eventually resolves an ``enclosing_decl_fqn``; a raw export with
   orphan nodes (no AST edge at all) is tolerated defensively — such nodes
   are appended to the deterministic order last (sorted by
   ``(filename, lineNumber, columnNumber, raw_id)``) with an empty
   ``enclosing_decl_fqn``/``structural_path``, but this should not occur for
   a well-formed Joern CPG.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, TypedDict

from analysis.ordering import CPG, NodeId

# ---------------------------------------------------------------------------
# Raw export schema (CLAR-SNAP-05) -- see module docstring for the full
# property -> CPGNode mapping table and the documented schema assumptions.
# ---------------------------------------------------------------------------


class RawJoernNode(TypedDict, total=False):
    """One entry of the export JSON's ``"nodes"`` array (CLAR-SNAP-05 schema).

    All keys are optional (``total=False``): a node object only carries the
    Joern properties that are meaningful for its own ``.label`` (e.g. a
    ``LITERAL`` node has no ``methodFullName``); absent keys are treated as
    empty/`None` by this module, never as an error.
    """

    id: str
    label: str
    code: str
    name: str
    methodFullName: str
    fullName: str
    filename: str
    lineNumber: int | None
    columnNumber: int | None


class RawJoernEdge(TypedDict):
    """One entry of the export JSON's ``"edges"`` array (CLAR-SNAP-05 schema)."""

    src: str
    dst: str
    kind: str


class RawJoernExport(TypedDict, total=False):
    """The top-level shape written by ``export_cpg.sc``: ``{"nodes": [...], "edges": [...]}``.

    Any additional top-level keys (e.g. a fixture's own ``_meta`` documentation
    block) are ignored by :func:`map_export` — only ``nodes``/``edges`` are read.
    """

    nodes: list[RawJoernNode]
    edges: list[RawJoernEdge]


@dataclass(frozen=True)
class SourceLocation:
    """Where a CPG node came from in the source — side-table payload ONLY.

    Deliberately a SEPARATE type from :class:`analysis.ordering.CPGNode`: a
    location is an out-of-band lookup aid (``file:line`` -> ``NodeId``), never
    part of node identity. Nothing in this dataclass may ever reach a hashed,
    ordered, canonicalised, or fingerprinted field — see the module docstring's
    "Source locations live ONLY in that side-table" paragraph and
    ``.claude/rules/01-invariants.md §INV-5``.

    Attributes:
        filename: the path exactly as Joern reported it (or as inherited from
            the nearest AST ancestor); ``""`` when unknown.
        line: 1-based line number; ``0`` is the documented unknown sentinel.
        column: column number; ``0`` is the documented unknown sentinel.
    """

    filename: str
    line: int
    column: int


# Node labels that count as a "declaration" for enclosing_decl_fqn/structural_path
# purposes (CLAR-SNAP-05 mapping table). Kept narrow and named, not inferred.
_DECL_LABELS: Final[frozenset[str]] = frozenset({"METHOD", "TYPE_DECL"})

# CLAR-SNAP-05 edge-kind vocabulary: AST/CFG direct, CDG+REACHING_DEF -> PDG.
EDGE_KIND_MAP: Final[dict[str, str]] = {
    "AST": "AST",
    "CFG": "CFG",
    "CDG": "PDG",
    "REACHING_DEF": "PDG",
}


class UnknownEdgeKindError(Exception):
    """A raw edge carried a ``kind`` outside the CLAR-SNAP-05 vocabulary.

    Fail-closed (mirrors ``tools.worker.secure_subprocess.UnknownTool``): an
    edge kind this module has no documented mapping for is refused rather than
    silently dropped or passed through unvetted into ``CPGEdge.kind``.
    """


class UnknownNodeReferenceError(Exception):
    """An edge referenced a raw node id absent from the export's ``"nodes"`` array.

    Fail-closed: a dangling edge reference indicates a malformed/truncated
    export and is refused rather than silently skipped.
    """


def _line(node: RawJoernNode) -> int:
    """``lineNumber`` as an ordering sentinel: missing/None sorts as ``0``."""
    return int(node.get("lineNumber") or 0)


def _col(node: RawJoernNode) -> int:
    """``columnNumber`` as an ordering sentinel: missing/None sorts as ``0``."""
    return int(node.get("columnNumber") or 0)


def _operator_or_literal(node: RawJoernNode) -> str:
    """CLAR-SNAP-05 mapping: literal text or operator symbol, ``""`` otherwise."""
    label = node.get("label", "")
    if label == "LITERAL":
        return str(node.get("code") or "")
    if label == "CALL":
        name = str(node.get("name") or "")
        if name.startswith("<operator>."):
            return name
    return ""


def _resolved_fqn(node: RawJoernNode) -> str:
    """CLAR-SNAP-05 mapping: callee FQN for calls, own FQN for declarations."""
    label = node.get("label", "")
    if label == "CALL":
        return str(node.get("methodFullName") or "")
    if label in _DECL_LABELS:
        return str(node.get("fullName") or "")
    return ""


def _node_sort_key(
    nid: str, nodes_by_id: dict[str, RawJoernNode], inherited_filename: str
) -> tuple[str, int, int, str]:
    """Deterministic per-level sibling order: ``(filename, line, col, raw_id)``.

    ``raw_id`` is the LAST-resort tie-break — a stable string comparison, never
    treated as a signal of "the order Joern happened to emit" (module docstring
    Provenance section).
    """
    node = nodes_by_id[nid]
    filename = str(node.get("filename") or inherited_filename)
    return (filename, _line(node), _col(node), nid)


def _walk_ast(
    roots: list[str], nodes_by_id: dict[str, RawJoernNode], ast_children: dict[str, list[str]]
) -> tuple[dict[str, int], dict[str, str], dict[str, str], dict[str, str]]:
    """Iterative (non-recursive) deterministic pre-order AST walk.

    Returns four per-node-id maps: ``preorder_index`` (the final emission
    tie-break), ``structural_path``, ``enclosing_decl_fqn``, ``resolved_filename``
    (the inherited-or-own filename used purely as ordering signal). Iterative
    (an explicit stack, not Python recursion) so this does not risk
    ``RecursionError`` on a deep real-world AST.
    """
    preorder_index: dict[str, int] = {}
    structural_path: dict[str, str] = {}
    enclosing_decl_fqn: dict[str, str] = {}
    resolved_filename: dict[str, str] = {}

    roots_sorted = sorted(roots, key=lambda r: _node_sort_key(r, nodes_by_id, ""))
    # Stack entries: (node_id, parent_decl_fqn, parent_filename, local_prefix).
    # Roots are pushed in REVERSE sorted order so popping (LIFO) processes them
    # in ascending sorted order.
    stack: list[tuple[str, str, str, str]] = [(r, "", "", "") for r in reversed(roots_sorted)]

    counter = 0
    while stack:
        nid, parent_decl_fqn, parent_filename, local_prefix = stack.pop()
        node = nodes_by_id[nid]
        label = node.get("label", "")
        is_decl = label in _DECL_LABELS

        this_decl_fqn = str(node.get("fullName") or "") if is_decl else parent_decl_fqn
        this_filename = str(node.get("filename") or parent_filename)
        this_prefix = "" if is_decl else local_prefix

        enclosing_decl_fqn[nid] = this_decl_fqn
        structural_path[nid] = this_prefix
        resolved_filename[nid] = this_filename
        preorder_index[nid] = counter
        counter += 1

        children = sorted(
            ast_children.get(nid, ()),
            key=lambda cid: _node_sort_key(cid, nodes_by_id, this_filename),
        )
        # Push in reverse so the ascending-sorted child is popped (visited)
        # first; recover each child's true 0-based position for structural_path.
        n_children = len(children)
        for i, cid in enumerate(reversed(children)):
            pos = n_children - 1 - i
            child_prefix = f"{this_prefix}.{pos}" if this_prefix else str(pos)
            stack.append((cid, this_decl_fqn, this_filename, child_prefix))

    # Defensive fallback for nodes never reached by the AST walk (orphans —
    # should not occur for a well-formed Joern CPG; see module docstring
    # assumption 3). Appended last, in a deterministic order of their own.
    orphans = sorted(
        (nid for nid in nodes_by_id if nid not in preorder_index),
        key=lambda nid: _node_sort_key(nid, nodes_by_id, ""),
    )
    for nid in orphans:
        enclosing_decl_fqn[nid] = ""
        structural_path[nid] = ""
        resolved_filename[nid] = str(nodes_by_id[nid].get("filename") or "")
        preorder_index[nid] = counter
        counter += 1

    return preorder_index, structural_path, enclosing_decl_fqn, resolved_filename


def map_export_with_locations(
    export: RawJoernExport | dict[str, Any],
) -> tuple[CPG, dict[NodeId, SourceLocation]]:
    """Identical CPG to :func:`map_export`, plus a side-table of node_id -> source location.

    The single shared implementation of the mapper walk; :func:`map_export` is a
    thin wrapper that discards the second element. Building the side-table is
    purely additive (a dict populated inside the existing emission loop from the
    same ``NodeId`` :meth:`~analysis.ordering.CPG.add_node` returns), so the
    ``CPG`` this returns is byte-identical to what :func:`map_export` has always
    returned for the same input.

    Args:
        export: the parsed JSON object written by ``export_cpg.sc`` (or an
            equivalent fixture) — ``{"nodes": [...], "edges": [...]}``. Any
            other top-level key is ignored.

    Returns:
        ``(cpg, locations)`` where ``cpg`` is exactly :func:`map_export`'s result
        and ``locations`` maps EVERY ``NodeId`` in ``cpg.nodes`` (orphans
        included) to its :class:`SourceLocation`. The filename is the node's own
        ``filename`` or, when absent, the one inherited from its nearest AST
        ancestor; a missing ``lineNumber``/``columnNumber`` is reported as the
        documented ``0`` sentinel. The side-table is a lookup aid ONLY — see the
        module docstring: locations never touch ``CPGNode`` or any hashed,
        ordered, or fingerprinted field.

    Raises:
        UnknownEdgeKindError: a raw edge's ``kind`` is outside the
            CLAR-SNAP-05 vocabulary (``AST``/``CFG``/``CDG``/``REACHING_DEF``).
        UnknownNodeReferenceError: a raw edge references a node id absent from
            ``export["nodes"]``.
    """
    raw_nodes: list[RawJoernNode] = list(export.get("nodes", []))
    raw_edges: list[RawJoernEdge] = list(export.get("edges", []))

    nodes_by_id: dict[str, RawJoernNode] = {str(n["id"]): n for n in raw_nodes}

    ast_children: dict[str, list[str]] = {}
    ast_parent_of: dict[str, str] = {}
    for e in raw_edges:
        if e.get("kind") == "AST":
            src, dst = str(e["src"]), str(e["dst"])
            if src not in nodes_by_id or dst not in nodes_by_id:
                raise UnknownNodeReferenceError(
                    f"AST edge ({src!r} -> {dst!r}) references a node id absent "
                    "from export['nodes']"
                )
            ast_children.setdefault(src, []).append(dst)
            ast_parent_of[dst] = src

    roots = [nid for nid in nodes_by_id if nid not in ast_parent_of]
    preorder_index, structural_path, enclosing_decl_fqn, resolved_filename = _walk_ast(
        roots, nodes_by_id, ast_children
    )

    emission_order = sorted(
        nodes_by_id.keys(),
        key=lambda nid: (
            resolved_filename[nid],
            _line(nodes_by_id[nid]),
            _col(nodes_by_id[nid]),
            preorder_index[nid],
        ),
    )

    cpg = CPG()
    raw_to_node_id: dict[str, NodeId] = {}
    # Side-table ONLY (never a CPGNode field, never hashed) — module docstring.
    locations: dict[NodeId, SourceLocation] = {}
    for nid in emission_order:
        node = nodes_by_id[nid]
        node_id = cpg.add_node(
            node.get("label", ""),
            operator_or_literal=_operator_or_literal(node),
            resolved_fqn=_resolved_fqn(node),
            enclosing_decl_fqn=enclosing_decl_fqn[nid],
            structural_path=structural_path[nid],
        )
        raw_to_node_id[nid] = node_id
        locations[node_id] = SourceLocation(
            filename=resolved_filename[nid],
            line=_line(node),
            column=_col(node),
        )

    mapped_edges: list[tuple[str, NodeId, NodeId]] = []
    for e in raw_edges:
        raw_kind = e["kind"]
        kind = EDGE_KIND_MAP.get(raw_kind)
        if kind is None:
            raise UnknownEdgeKindError(
                f"edge kind {raw_kind!r} is not in the CLAR-SNAP-05 vocabulary "
                f"{sorted(EDGE_KIND_MAP)}; refusing to emit an unvetted CPGEdge.kind"
            )
        src_raw, dst_raw = str(e["src"]), str(e["dst"])
        if src_raw not in raw_to_node_id or dst_raw not in raw_to_node_id:
            raise UnknownNodeReferenceError(
                f"edge ({src_raw!r} -> {dst_raw!r}, kind={raw_kind!r}) references "
                "a node id absent from export['nodes']"
            )
        mapped_edges.append((kind, raw_to_node_id[src_raw], raw_to_node_id[dst_raw]))

    for kind, src_id, dst_id in sorted(mapped_edges):
        cpg.add_edge(src_id, dst_id, kind)

    return cpg, locations


def map_export(export: RawJoernExport | dict[str, Any]) -> CPG:
    """Map a Joern export JSON object into an :class:`analysis.ordering.CPG`.

    Args:
        export: the parsed JSON object written by ``export_cpg.sc`` (or an
            equivalent fixture) — ``{"nodes": [...], "edges": [...]}``. Any
            other top-level key is ignored.

    Returns:
        A :class:`~analysis.ordering.CPG` whose node emission order is this
        module's OWN deterministic ``(filename, line, col, ast_preorder_index)``
        order (never the raw array order) and whose edges are re-sorted by
        ``(kind, src_node_id, dst_node_id)`` — see module docstring.

    Raises:
        UnknownEdgeKindError: a raw edge's ``kind`` is outside the
            CLAR-SNAP-05 vocabulary (``AST``/``CFG``/``CDG``/``REACHING_DEF``).
        UnknownNodeReferenceError: a raw edge references a node id absent from
            ``export["nodes"]``.
    """
    cpg, _locations = map_export_with_locations(export)
    return cpg


__all__ = [
    "EDGE_KIND_MAP",
    "RawJoernEdge",
    "RawJoernExport",
    "RawJoernNode",
    "SourceLocation",
    "UnknownEdgeKindError",
    "UnknownNodeReferenceError",
    "map_export",
    "map_export_with_locations",
]
