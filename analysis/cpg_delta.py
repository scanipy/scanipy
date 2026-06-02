"""CMP-SNAP-02 — Incremental CPG maintenance (Algorithm 1).

The **delta engine** of the Snapshotter. Given a parent snapshot's CPG plus
graph-level structures (reverse-symbol index, static call graph, class-hierarchy
view) and the set of declarations a child commit changes, it produces the new
CPG ``G'``, the structural delta ``ΔG``, and the ``AFFECTED`` set of entry
points whose IFDS summaries must be invalidated.

This module is the operational *consumer* of the INV-4 ``CW-DETECT`` verdict
(owned by ``CMP-SNAP-03``); it never overrides the verdict in the unsafe
direction. It routes by the verdict (DOC-CMP-SNAP-02 §6.1) and records the
**route actually taken** as ``precondition_status`` (which can differ from the
bare verdict on the ``degraded → full-reparse`` transition).

**Scope of this implementation (DELIBERATE PARTIAL).** Only the
node-ID-preservation correctness gate (``AC-SNAP-02c`` / ``TST-AC-SNAP-02c``) is
turned green this round. The κ-bound conditional-theorem regression
(``AC-SNAP-02a``) is blocked on a frozen κ that ``CLAR-PARAM-01`` pins only at
Stage A go-live, and the empirical speedup corpus (``AC-SNAP-02b``) is a nightly
open-world benchmark — both stay out of this module's testable surface.

**Parse at the boundary (INV-2 / hermetic).** ``compute_incremental_cpg``
operates on already-parsed graph-level inputs. The source read + Joern
function-granularity reparse is the ``CMP-SNAP-05`` worker's job; it is modelled
here as an **injected collaborator** (:class:`DeclReparser`) — never a real
front-end call. This mirrors the dependency-injection pattern of
``services/scan/provenance`` and ``services/snapshot/service.py``.

Source-of-truth: ``DOC-CMP-SNAP-02`` (§3 interface, §3.1 errors, §6.1 routing,
§6.2 AFFECTED, §6.4 node-ID preservation, §7 failure modes), ``DOC-ALGS §2``,
``.claude/rules/01-invariants.md`` (INV-2, INV-4 hand-off),
``.claude/rules/02-provenance.md``, ``WBS.md §17 CLAR-PARAM-01``.

This module **must not** touch ``origin``, ``S_version``, ``env_digest`` (it
consumes the parent's ``env_digest`` unchanged), ``cpg_order_hash`` or
``slice_fingerprint`` — those are downstream-owned (DOC-CMP-SNAP-02 §8).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal, Protocol, runtime_checkable

from analysis.ordering import CPG, CPGEdge, CPGNode, NodeId

# CLAR-PARAM-01 RESOLVED 2026-05-23: degraded-path reparse fallback thresholds.
DEFAULT_THETA_CONE: Final[float] = 0.25  # |cone| / |G'| ceiling on the degraded path
DEFAULT_THETA_FILES: Final[float] = 0.4  # |changed files| / |files| ceiling

PreconditionStatus = Literal["closed-world", "degraded", "full-reparse"]

# The route actually taken (DOC-CMP-SNAP-02 §6.1). Mirrors the three verdicts but
# names the auditable decision; ``precondition_status`` on the snapshot row is set
# to this, NOT to the bare ``cw_verdict``.
Route = Literal["closed-world", "degraded", "full-reparse"]


# ---------------------------------------------------------------------------
# Errors (DOC-CMP-SNAP-02 §3.1, §7)
# ---------------------------------------------------------------------------


class IncrementalCpgError(Exception):
    """Base class for CMP-SNAP-02 incremental-maintenance errors."""


class NodeIdCollision(IncrementalCpgError):  # noqa: N818 — name fixed verbatim by DOC §3.1
    """A reparse minted a ``NodeId`` that collides with an unchanged-declaration
    node ID inherited from the parent CPG (violates ``AC-SNAP-02c``).

    This is an algorithm bug, not an expected condition: the new node IDs for
    ``AFFECTED`` declarations MUST be disjoint from the preserved IDs of
    not-``AFFECTED`` declarations. A hard failure (DOC §3.1 / §7) — the snapshot
    must not be published.
    """


class EnvDigestMismatch(IncrementalCpgError):  # noqa: N818 — INV-2 fail-closed guard (DOC §7)
    """The parent snapshot's ``env_digest`` differs from the current worker's.

    Per INV-2 a snapshot may not be re-used across ``Env`` values — the parent
    is a *different* ``Env``. The component refuses the incremental path and the
    caller must force a full reparse against the worker's ``Env`` (DOC §7,
    failure-modes table row 1).
    """


# ---------------------------------------------------------------------------
# CPG with a per-declaration node-id accessor (additive; ordering.py untouched)
# ---------------------------------------------------------------------------


class IncrementalCpg(CPG):
    """A :class:`analysis.ordering.CPG` with a per-declaration node-ID accessor.

    Defined here — **not** on ``CPG`` — so ``analysis.ordering`` (CMP-CORE-03,
    whose ``cpg_order_hash`` determinism depends on ``add_node``'s
    insertion-order semantics) is left byte-for-byte unchanged. The accessor is
    read-only; it does not alter construction.
    """

    def node_ids(self, decl: str) -> set[NodeId]:
        """The set of node IDs belonging to declaration ``decl``.

        ``decl`` is an enclosing-declaration FQN (``CPGNode.enclosing_decl_fqn``,
        the natural per-declaration key — DOC-CMP-SNAP-02 §6.4). Returned as a
        set so callers compare membership without depending on insertion order.
        """
        return {n.node_id for n in self.nodes if n.enclosing_decl_fqn == decl}

    def _append_node(self, node: CPGNode) -> None:
        """Append a fully-formed node, preserving its existing ``node_id``.

        Distinct from :meth:`CPG.add_node`, which assigns ``node_id =
        len(self.nodes)``. ID preservation requires inheriting parent IDs
        verbatim and minting controlled fresh IDs for ``AFFECTED`` decls, so this
        path takes the node as-is. ``add_node``'s semantics are never changed.
        """
        self.nodes.append(node)

    def _append_edge(self, edge: CPGEdge) -> None:
        self.edges.append(edge)


# ---------------------------------------------------------------------------
# Graph-level inputs (already parsed; the parse boundary is the worker's job)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeclSubgraph:
    """The reparsed subgraph for a single (changed) declaration.

    Produced by the injected :class:`DeclReparser` (modelling the SNAP-05
    front-end). ``nodes``/``edges`` carry the node IDs the reparser minted; the
    incremental builder validates them against the preserved-ID set and raises
    :class:`NodeIdCollision` on overlap rather than trusting the front-end.
    """

    decl_fqn: str
    nodes: tuple[CPGNode, ...]
    edges: tuple[CPGEdge, ...]


@runtime_checkable
class DeclReparser(Protocol):
    """Injected collaborator: reparse a changed declaration to a fresh subgraph.

    Models the ``CMP-SNAP-05`` worker's function-granularity Joern reparse. It is
    a Protocol so tests fixture it the way ``CMP-FND-03`` fixtured its KMS signer
    — **never** a real front-end call inside this module.

    ``fresh_id_base`` is the lowest node ID the reparser may mint; the builder
    passes ``max(preserved_ids) + 1`` so a well-behaved reparser produces IDs
    disjoint from the preserved set. A misbehaving reparser that returns a
    colliding ID is caught by the builder (NodeIdCollision).
    """

    def reparse(self, decl_fqn: str, *, fresh_id_base: int) -> DeclSubgraph: ...


@dataclass(frozen=True)
class GraphView:
    """The graph-level structures Algorithm 1 reads to compute ``AFFECTED``.

    All read-only; sourced from the parent snapshot's S3 artifacts
    (DOC-CMP-SNAP-02 §4.1). Keys are declaration FQNs; values are sets of FQNs.

    * ``reverse_symbol_index`` — symbol/declaration → declarations that reference
      it (the reverse-symbol closure is the transitive closure over this).
    * ``call_graph`` — declaration → the declarations it calls (its reverse gives
      direct callers of a changed signature).
    * ``class_hierarchy`` — type → its subtypes (the CHA cone of a changed type
      is the transitive closure over this).
    * ``decl_to_type`` — declaration FQN → the type that encloses it (so a CHA
      cone of types maps back to the declarations to invalidate).
    """

    reverse_symbol_index: dict[str, frozenset[str]] = field(default_factory=dict)
    call_graph: dict[str, frozenset[str]] = field(default_factory=dict)
    class_hierarchy: dict[str, frozenset[str]] = field(default_factory=dict)
    decl_to_type: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class IncrementalCpgRequest:
    """Input to :func:`compute_incremental_cpg` (DOC-CMP-SNAP-02 §3).

    Graph-level and hermetic: the parent CPG and graph views are already parsed;
    the changed-declaration reparse is delegated to ``reparser``. There is no
    filesystem read and no HTTP surface here.
    """

    parent_cpg: IncrementalCpg
    parent_env_digest: str  # from the parent snapshot row (INV-2); consumed unchanged
    worker_env_digest: str  # the current worker's Env; must equal parent_env_digest
    cw_verdict: PreconditionStatus  # from CMP-SNAP-03 over source@current_commit
    changed_decls: frozenset[str]  # enclosing-decl FQNs the child commit changed
    changed_types: frozenset[str]  # types whose definition the child commit changed
    graph: GraphView  # reverse-symbol / call-graph / CHA structures (parent)
    reparser: DeclReparser  # injected SNAP-05 front-end seam
    total_files: int = 1  # |files| in the source tree (for changed_files_ratio)
    changed_files: int = 0  # |changed files| (for changed_files_ratio)
    theta_cone: float = DEFAULT_THETA_CONE
    theta_files: float = DEFAULT_THETA_FILES


@dataclass(frozen=True)
class GraphDelta:
    """``ΔG`` — the structural delta (DOC-CMP-SNAP-02 §3, §6.2 step 7)."""

    added_nodes: tuple[NodeId, ...]
    removed_nodes: tuple[NodeId, ...]
    added_edges: tuple[CPGEdge, ...]
    removed_edges: tuple[CPGEdge, ...]
    affected_set: frozenset[str]


@dataclass(frozen=True)
class IncrementalCpgResult:
    """Output of :func:`compute_incremental_cpg` (DOC-CMP-SNAP-02 §3)."""

    new_cpg: IncrementalCpg  # G'
    delta_graph: GraphDelta  # ΔG
    affected: frozenset[str]  # AFFECTED entry points (decl FQNs)
    precondition_status: Route  # the route ACTUALLY taken (may differ from cw_verdict)
    changed_files_ratio: float
    cone_size_ratio: float | None = None  # |cone|/|G'| when not closed-world


# ---------------------------------------------------------------------------
# AFFECTED set (DOC-CMP-SNAP-02 §6.2)
# ---------------------------------------------------------------------------


def _transitive_closure(seeds: frozenset[str], graph: dict[str, frozenset[str]]) -> frozenset[str]:
    """Forward transitive closure of ``seeds`` over ``graph`` (FQN → FQNs)."""
    seen: set[str] = set(seeds)
    stack: list[str] = list(seeds)
    while stack:
        cur = stack.pop()
        for nxt in graph.get(cur, frozenset()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return frozenset(seen)


def _direct_callers(
    changed_decls: frozenset[str], call_graph: dict[str, frozenset[str]]
) -> frozenset[str]:
    """Direct callers of any changed signature (reverse of the call graph)."""
    callers: set[str] = set()
    for caller, callees in call_graph.items():
        if callees & changed_decls:
            callers.add(caller)
    return frozenset(callers)


def compute_affected(
    changed_decls: frozenset[str],
    changed_types: frozenset[str],
    graph: GraphView,
) -> frozenset[str]:
    """Compute the ``AFFECTED`` set (DOC-CMP-SNAP-02 §6.2, ``PLAN.md`` Alg 1).

    ``AFFECTED = changed-decls
                 | reverse-symbol-closure(changed-decls)
                 | direct-callers(changed-signatures)
                 | CHA-cone(changed-types)``  (| denotes set union)

    over graph-level inputs. Each union member is computed here from the parent
    graph views — never accepted as a parameter — so the union logic is what is
    exercised by ``TST-AC-SNAP-02c``.
    """
    reverse_symbol_closure = _transitive_closure(changed_decls, graph.reverse_symbol_index)
    direct_callers = _direct_callers(changed_decls, graph.call_graph)

    # CHA-cone(changed-types): all subtypes (transitively) of changed types,
    # mapped back through decl_to_type to the declarations that must invalidate.
    type_cone = _transitive_closure(changed_types, graph.class_hierarchy)
    cha_cone_decls = frozenset(decl for decl, ty in graph.decl_to_type.items() if ty in type_cone)

    return changed_decls | reverse_symbol_closure | direct_callers | cha_cone_decls


# ---------------------------------------------------------------------------
# Routing (DOC-CMP-SNAP-02 §6.1)
# ---------------------------------------------------------------------------


def _route_for(
    req: IncrementalCpgRequest, changed_files_ratio: float, affected: frozenset[str]
) -> tuple[Route, float | None]:
    """Decide the route actually taken from the CW verdict + thresholds.

    Returns ``(route, cone_size_ratio)``. On the ``degraded`` verdict, a
    file-ratio or cone-ratio breach demotes to ``full-reparse`` (DOC §6.1) — this
    is the one transition where the route differs from the bare verdict.
    """
    if req.cw_verdict == "closed-world":
        return "closed-world", None
    if req.cw_verdict == "full-reparse":
        return "full-reparse", None

    # degraded: apply the θ_files / θ_cone fallback (DOC §6.1).
    if changed_files_ratio > req.theta_files:
        return "full-reparse", None
    parent_node_count = len(req.parent_cpg.nodes)
    # |G'| estimated from parent + delta; AFFECTED decls stand in for the cone.
    estimated_graph = max(parent_node_count, 1)
    cone_nodes = sum(1 for n in req.parent_cpg.nodes if n.enclosing_decl_fqn in affected)
    cone_size_ratio = cone_nodes / estimated_graph
    if cone_size_ratio > req.theta_cone:
        return "full-reparse", cone_size_ratio
    return "degraded", cone_size_ratio


# ---------------------------------------------------------------------------
# Node-ID-preserving reparse (DOC-CMP-SNAP-02 §6.4 — the AC-SNAP-02c gate)
# ---------------------------------------------------------------------------


def _build_preserving_new_cpg(
    parent: IncrementalCpg,
    affected: frozenset[str],
    reparser: DeclReparser,
) -> tuple[IncrementalCpg, GraphDelta]:
    """Materialise ``G'`` by function-granularity reparse (DOC §6.2 step 6, §6.4).

    * Declarations **not in** ``AFFECTED`` reuse their parent node IDs verbatim.
      "Unchanged" == "not in ``AFFECTED``"; the enclosing-declaration content-hash
      change-detection that *populates* ``changed_decls`` (and hence ``AFFECTED``)
      is performed upstream at the source boundary (DOC §6.2 step 1 / §6.4), not in
      this graph-level engine.
    * Declarations **in** ``AFFECTED`` are reparsed through the injected
      ``reparser`` and mint fresh IDs (above the preserved maximum).
    * Any reparsed ID overlapping a preserved ID raises :class:`NodeIdCollision`.
    """
    new_cpg = IncrementalCpg()

    # 1) Carry over not-AFFECTED declarations with their parent node IDs intact.
    preserved_ids: set[NodeId] = set()
    for node in parent.nodes:
        if node.enclosing_decl_fqn in affected:
            continue
        new_cpg._append_node(node)  # node_id preserved verbatim
        preserved_ids.add(node.node_id)

    # Carry edges fully internal to preserved declarations; edges that touch an
    # AFFECTED node are removed from G' and re-supplied by the reparse subgraphs.
    preserved_node_set = set(preserved_ids)
    for edge in parent.edges:
        if edge.src in preserved_node_set and edge.dst in preserved_node_set:
            new_cpg._append_edge(edge)

    fresh_id_base = (max(preserved_ids) + 1) if preserved_ids else 0

    # 2) Reparse AFFECTED declarations and append their fresh subgraphs.
    added_nodes: list[NodeId] = []
    added_edges: list[CPGEdge] = []
    next_base = fresh_id_base
    for decl in sorted(affected):
        sub = reparser.reparse(decl, fresh_id_base=next_base)
        for n in sub.nodes:
            if n.node_id in preserved_ids:
                # The reparse minted an ID already owned by an unchanged decl.
                raise NodeIdCollision(
                    f"reparse of {decl!r} minted node_id {int(n.node_id)} "
                    f"which collides with a preserved unchanged-declaration ID"
                )
            new_cpg._append_node(n)
            added_nodes.append(n.node_id)
        for e in sub.edges:
            new_cpg._append_edge(e)
            added_edges.append(e)
        if sub.nodes:
            next_base = max(int(n.node_id) for n in sub.nodes) + 1

    # 3) ΔG: removed = the parent nodes/edges of AFFECTED decls that did not carry over.
    new_node_ids = {n.node_id for n in new_cpg.nodes}
    removed_nodes = tuple(n.node_id for n in parent.nodes if n.node_id not in new_node_ids)
    new_edge_set = set(new_cpg.edges)
    removed_edges = tuple(e for e in parent.edges if e not in new_edge_set)

    delta = GraphDelta(
        added_nodes=tuple(added_nodes),
        removed_nodes=removed_nodes,
        added_edges=tuple(added_edges),
        removed_edges=removed_edges,
        affected_set=affected,
    )
    return new_cpg, delta


# ---------------------------------------------------------------------------
# Entry point (DOC-CMP-SNAP-02 §3)
# ---------------------------------------------------------------------------


def compute_incremental_cpg(req: IncrementalCpgRequest) -> IncrementalCpgResult:
    """Compute ``G'``, ``ΔG`` and ``AFFECTED`` from a parent snapshot.

    In-process (no HTTP, no filesystem). Routes by ``cw_verdict``
    (DOC-CMP-SNAP-02 §6.1), computes ``AFFECTED`` over the graph-level views
    (§6.2), and materialises ``G'`` with node-ID preservation for not-AFFECTED
    declarations (§6.4). The result's ``precondition_status`` is the route
    **actually** taken, which can differ from the bare verdict on the
    ``degraded → full-reparse`` demotion.

    INV-2 (DOC §7): refuses the incremental path when the parent snapshot's
    ``env_digest`` differs from the worker's — a different ``Env`` may not be
    re-used. Raises :class:`EnvDigestMismatch` (fail-closed); the caller forces a
    full reparse against the worker ``Env``.
    """
    if req.parent_env_digest != req.worker_env_digest:
        raise EnvDigestMismatch(
            f"parent env_digest {req.parent_env_digest!r} != worker env_digest "
            f"{req.worker_env_digest!r}; a snapshot may not be re-used across Env (INV-2)"
        )

    affected = compute_affected(req.changed_decls, req.changed_types, req.graph)

    changed_files_ratio = req.changed_files / max(req.total_files, 1)
    route, cone_size_ratio = _route_for(req, changed_files_ratio, affected)

    # On the ``full-reparse`` route the worker discards any incrementally-built G'
    # and reparses the whole program (DOC §6.1/§6.5). Returning a *partially*
    # preserved graph here would give ``new_cpg`` undefined semantics for that
    # route. So treat **every** declaration as AFFECTED: nothing is preserved, all
    # IDs are fresh, and ``affected_set`` honestly reports "all" — a coherent
    # full-reparse output rather than a half-preserved graph.
    if route == "full-reparse":
        affected = frozenset(n.enclosing_decl_fqn for n in req.parent_cpg.nodes)

    new_cpg, delta = _build_preserving_new_cpg(req.parent_cpg, affected, req.reparser)

    return IncrementalCpgResult(
        new_cpg=new_cpg,
        delta_graph=delta,
        affected=affected,
        precondition_status=route,
        changed_files_ratio=changed_files_ratio,
        cone_size_ratio=cone_size_ratio,
    )
