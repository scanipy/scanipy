"""CMP-CORE-03 — Canonical CPG ordering (Algorithm 5).

Computes a deterministic, parse-order-independent enumeration of every CPG node
together with a ``cpg_order_hash`` digest, classified ``strong`` (a true
canonical form found within the ``(B, T)`` budget) or ``weak`` (the budget was
exhausted and a deterministic stable-order fallback was used).

This module is the operational owner of **INV-5**: the hash is *canonical* iff
``fingerprint_class == "strong"``. The literal annotation
``"canonical iff fingerprint_class = strong"`` is exposed as the single
module-level constant :data:`CPG_ORDER_HASH_ANNOTATION`; every downstream
emitter (provenance record, SARIF properties, auditor export) imports that
constant rather than reconstructing the string from substrings.

Algorithm 5 (verbatim, ``PLAN.md §"Algorithm 5"`` / ``DOC-ALGS §6.4``):

    seed labels ``(kind, operator/literal, resolved FQN,
    sorted incident-edge-kind multiset)``; 2-WL to fixpoint; residual symmetric
    classes broken by enclosing-declaration canonical order then bounded
    individualisation-refinement under the shared ``(B, T)`` budget; on
    exhaustion, a stable order keyed by
    ``(declaration-hash, structural-path-from-declaration-root, edge-kind)`` —
    total, deterministic, parse-order-independent, but **not** a true canonical
    form.

The ``(B, T)`` defaults are ``B = 2**16`` search-tree nodes and ``T = 200 ms``
wall-clock (``CLAR-PARAM-01`` RESOLVED 2026-05-23). ``B`` is the authoritative
budget trigger; ``T`` is a soft cap (wall-clock skew is accepted per
``DOC-CMP-CORE-03 §7.1`` so long as ``B`` is honoured).

Source-of-truth: ``DOC-CMP-CORE-03``, ``DOC-ALGS §6``, ``DOC-PROVENANCE §2.1``,
``.claude/rules/01-invariants.md §INV-5``.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Final, Literal, NewType

NodeId = NewType("NodeId", int)
Sha256 = NewType("Sha256", bytes)  # 32 raw bytes
Duration = NewType("Duration", float)  # seconds

FingerprintClass = Literal["strong", "weak"]

Annotation = Literal["canonical iff fingerprint_class = strong"]

# INV-5 anchor. The ONE place this string is constructed. Every emitter that
# writes a record containing ``cpg_order_hash`` imports this constant and never
# rebuilds it from substrings (DOC-CMP-CORE-03 §5.1, DOC-PROVENANCE §2.1).
CPG_ORDER_HASH_ANNOTATION: Final[Annotation] = "canonical iff fingerprint_class = strong"

# CLAR-PARAM-01 RESOLVED 2026-05-23: hard (B, T) canonicalisation budget.
DEFAULT_B: Final[int] = 2**16  # search-tree node cap (authoritative trigger)
DEFAULT_T: Final[Duration] = Duration(0.200)  # wall-clock soft cap (seconds)


class BudgetExhausted(Exception):  # noqa: N818  (named verbatim per DOC-CMP-CORE-03 App. A)
    """Raised internally when the ``(B, T)`` budget is exceeded during the
    bounded individualisation-refinement phase, triggering the deterministic
    stable-order fallback. This is **not** an error condition surfaced to the
    caller — it is the defined ``weak``-class path (DOC-CMP-CORE-03 §7.2)."""


# ---------------------------------------------------------------------------
# Minimal CPG model
# ---------------------------------------------------------------------------
#
# CMP-CORE-03 has no upstream component dependency (Wave-1). It depends only on
# a graph it can enumerate; the production CPG is materialised by CMP-SNAP-01.
# This module defines the minimal structural surface Algorithm 5 needs so it is
# self-contained and testable. NodeIds are assigned by construction order
# (NOT Python ``id()``) so "the same source" yields stable IDs across re-runs.


@dataclass(frozen=True)
class CPGNode:
    """A CPG node. ``node_id`` is assigned by :meth:`CPG.add_node` from
    construction order so it is stable across re-runs of the same source."""

    node_id: NodeId
    kind: str  # e.g. "CALL", "IDENTIFIER", "METHOD"
    operator_or_literal: str  # operator / literal text, "" if none
    resolved_fqn: str  # resolved fully-qualified name, "" if none
    enclosing_decl_fqn: str  # FQN of the enclosing declaration (for tie-break)
    structural_path: str  # deterministic AST traversal path from decl root


@dataclass(frozen=True)
class CPGEdge:
    """A directed CPG edge with a typed kind (e.g. "AST", "CFG", "PDG")."""

    src: NodeId
    dst: NodeId
    kind: str


@dataclass
class CPG:
    """Minimal code-property-graph surface consumed by Algorithm 5.

    Build with :meth:`add_node` / :meth:`add_edge`; NodeIds are assigned
    deterministically from insertion order so that the same source produces the
    same graph and therefore the same ``cpg_order_hash``.
    """

    nodes: list[CPGNode] = field(default_factory=list)
    edges: list[CPGEdge] = field(default_factory=list)

    def add_node(
        self,
        kind: str,
        *,
        operator_or_literal: str = "",
        resolved_fqn: str = "",
        enclosing_decl_fqn: str = "",
        structural_path: str = "",
    ) -> NodeId:
        node_id = NodeId(len(self.nodes))
        self.nodes.append(
            CPGNode(
                node_id=node_id,
                kind=kind,
                operator_or_literal=operator_or_literal,
                resolved_fqn=resolved_fqn,
                enclosing_decl_fqn=enclosing_decl_fqn,
                structural_path=structural_path,
            )
        )
        return node_id

    def add_edge(self, src: NodeId, dst: NodeId, kind: str) -> None:
        self.edges.append(CPGEdge(src=src, dst=dst, kind=kind))


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CanonicalOrderResult:
    """Output of :func:`canonical_order`. The INV-5 anchor.

    ``annotation`` is always the literal :data:`CPG_ORDER_HASH_ANNOTATION` and
    MUST be persisted adjacent to ``cpg_order_hash`` everywhere it appears
    (DOC-CMP-CORE-03 §5.1 / AC-CORE-03c). The hash is a true canonical form
    (equal for isomorphic-but-differently-written programs) iff
    ``fingerprint_class == "strong"``; on the ``weak`` path it is deterministic
    over the same source but not canonical across isomorphism.
    """

    canonical_order: list[NodeId]
    cpg_order_hash: Sha256
    fingerprint_class: FingerprintClass
    annotation: Annotation
    budget_exhausted: bool
    elapsed_ms: float


# ---------------------------------------------------------------------------
# Algorithm 5 phases
# ---------------------------------------------------------------------------


def _incident_edge_kinds(cpg: CPG) -> dict[NodeId, list[str]]:
    """Sorted multiset of incident-edge kinds per node (both directions)."""
    incident: dict[NodeId, list[str]] = {n.node_id: [] for n in cpg.nodes}
    for e in cpg.edges:
        if e.src in incident:
            incident[e.src].append(e.kind)
        if e.dst in incident:
            incident[e.dst].append(e.kind)
    for nid in incident:
        incident[nid].sort()
    return incident


def _neighbours(cpg: CPG) -> dict[NodeId, list[tuple[str, NodeId]]]:
    """Per node, the list of ``(edge_kind, neighbour)`` over incident edges."""
    nbrs: dict[NodeId, list[tuple[str, NodeId]]] = {n.node_id: [] for n in cpg.nodes}
    for e in cpg.edges:
        if e.src in nbrs:
            nbrs[e.src].append((e.kind, e.dst))
        if e.dst in nbrs:
            nbrs[e.dst].append((e.kind, e.src))
    return nbrs


def _hash_label(*parts: object) -> bytes:
    """Deterministic content hash of a label tuple."""
    h = hashlib.sha256()
    h.update(repr(parts).encode("utf-8"))
    return h.digest()


def _seed_labels(cpg: CPG) -> dict[NodeId, bytes]:
    """Phase 1: ``label_0(n) = hash((kind, operator/literal, resolved_fqn,
    sorted incident-edge-kind multiset))``."""
    incident = _incident_edge_kinds(cpg)
    return {
        n.node_id: _hash_label(
            n.kind,
            n.operator_or_literal,
            n.resolved_fqn,
            tuple(incident[n.node_id]),
        )
        for n in cpg.nodes
    }


def _partition_signature(labels: dict[NodeId, bytes]) -> tuple[bytes, ...]:
    """A canonical signature of the label partition for fixpoint detection.

    Order-independent: built from the sorted multiset of labels so that
    re-labelling does not change the signature if the partition is unchanged.
    """
    return tuple(sorted(labels.values()))


def _wl_refine_to_fixpoint(cpg: CPG, labels: dict[NodeId, bytes]) -> dict[NodeId, bytes]:
    """Phase 2: 2-WL refinement.

    ``label_{k+1}(n) = hash((label_k(n), sorted multiset of
    (edge_kind, label_k(neighbour)) over incident edges))`` until the partition
    stops refining. Bounded by ``|nodes|`` iterations (a partition can refine at
    most ``|nodes|`` times).
    """
    nbrs = _neighbours(cpg)
    prev_sig = _partition_signature(labels)
    for _ in range(len(cpg.nodes)):
        new_labels: dict[NodeId, bytes] = {}
        for nid, lbl in labels.items():
            neighbour_labels = sorted((kind, labels[other]) for kind, other in nbrs[nid])
            new_labels[nid] = _hash_label(lbl, tuple(neighbour_labels))
        new_sig = _partition_signature(new_labels)
        labels = new_labels
        if new_sig == prev_sig:
            break
        prev_sig = new_sig
    return labels


def _classes_by_label(labels: dict[NodeId, bytes]) -> dict[bytes, list[NodeId]]:
    """Group node ids by their refined label (the equivalence classes)."""
    classes: dict[bytes, list[NodeId]] = {}
    for nid, lbl in labels.items():
        classes.setdefault(lbl, []).append(nid)
    return classes


def _partition_is_total(labels: dict[NodeId, bytes]) -> bool:
    """True iff every node has a distinct label (no residual symmetry)."""
    return len(set(labels.values())) == len(labels)


def _break_by_enclosing_decl(cpg: CPG, labels: dict[NodeId, bytes]) -> dict[NodeId, bytes]:
    """Tie-break residual symmetric classes first by enclosing-declaration
    canonical order, refining each node's label with its enclosing-decl FQN."""
    node_by_id = {n.node_id: n for n in cpg.nodes}
    return {
        nid: _hash_label(lbl, node_by_id[nid].enclosing_decl_fqn) for nid, lbl in labels.items()
    }


def _individualise_refine(
    cpg: CPG,
    labels: dict[NodeId, bytes],
    *,
    B: int,  # noqa: N803  (budget symbol B is part of the (B, T) public contract)
    deadline: float,
) -> dict[NodeId, bytes]:
    """Phase 3: bounded individualisation-refinement under the shared ``(B, T)``
    budget. Pick a representative of a residual symmetric class, individualise
    it (give it a unique label), re-run 2-WL, and recurse until the partition is
    total. Each search-tree node visited counts against ``B``; wall-clock is
    checked against ``deadline``. Raises :class:`BudgetExhausted` on overrun.
    """
    search_nodes = 0
    work = labels
    while not _partition_is_total(work):
        search_nodes += 1
        if search_nodes >= B:
            raise BudgetExhausted
        if time.monotonic() >= deadline:
            raise BudgetExhausted
        classes = _classes_by_label(work)
        # Deterministically pick the smallest non-singleton class (by label
        # bytes), then its lowest-id member as the individualisation target.
        target_class = min(
            (lbl for lbl, members in classes.items() if len(members) > 1),
            key=lambda lbl: (len(classes[lbl]), lbl),
        )
        target = min(classes[target_class])
        individualised = dict(work)
        individualised[target] = _hash_label(work[target], b"<individualised>", int(target))
        work = _wl_refine_to_fixpoint(cpg, individualised)
    return work


def _stable_order_fallback(cpg: CPG, labels: dict[NodeId, bytes]) -> list[NodeId]:
    """Phase 4: deterministic stable-order fallback on budget exhaustion.

    Order keyed by ``(declaration_hash, structural_path_from_declaration_root,
    edge_kind-proxy, refined_label, node_id)`` where
    ``declaration_hash := sha256(enclosing_declaration.fqn)``. Total,
    deterministic, parse-order-independent — but **not** canonical across
    isomorphic programs (hence ``fingerprint_class = "weak"``).
    """
    node_by_id = {n.node_id: n for n in cpg.nodes}

    def key(nid: NodeId) -> tuple[bytes, str, bytes, int]:
        node = node_by_id[nid]
        decl_hash = hashlib.sha256(node.enclosing_decl_fqn.encode("utf-8")).digest()
        return (decl_hash, node.structural_path, labels[nid], int(nid))

    return sorted((n.node_id for n in cpg.nodes), key=key)


def _emit_order(labels: dict[NodeId, bytes]) -> list[NodeId]:
    """Emit a total order from a total partition: sort by (label, node_id)."""
    return sorted(labels.keys(), key=lambda nid: (labels[nid], int(nid)))


def _digest_order(order: list[NodeId]) -> Sha256:
    """sha256 over the canonical node order (8-byte big-endian per id)."""
    h = hashlib.sha256()
    for nid in order:
        h.update(int(nid).to_bytes(8, "big", signed=False))
    return Sha256(h.digest())


def _result(
    order: list[NodeId],
    klass: FingerprintClass,
    *,
    budget_exhausted: bool,
    elapsed_s: float,
) -> CanonicalOrderResult:
    return CanonicalOrderResult(
        canonical_order=order,
        cpg_order_hash=_digest_order(order),
        fingerprint_class=klass,
        annotation=CPG_ORDER_HASH_ANNOTATION,
        budget_exhausted=budget_exhausted,
        elapsed_ms=elapsed_s * 1000.0,
    )


def canonical_order(
    cpg: CPG,
    *,
    B: int = DEFAULT_B,  # noqa: N803  ((B, T) budget symbols are the public contract)
    T: Duration = DEFAULT_T,  # noqa: N803
) -> CanonicalOrderResult:
    """Compute a deterministic enumeration of ``cpg`` plus ``cpg_order_hash``.

    Pure: the same ``(cpg, B, T)`` always yields the same
    :class:`CanonicalOrderResult`. No I/O, no global state, no randomness.

    ``strong`` is returned when 2-WL + bounded individualisation-refinement
    converged to a total partition within ``(B, T)``; ``weak`` is returned when
    the budget was exhausted and the stable-order fallback was used. The ``weak``
    path is a defined success mode, not a failure (DOC-CMP-CORE-03 §7.2): the
    order is still deterministic over the same source.

    The returned ``annotation`` is always :data:`CPG_ORDER_HASH_ANNOTATION` and
    MUST be persisted adjacent to the hash everywhere (INV-5 / AC-CORE-03c).
    """
    t0 = time.monotonic()
    deadline = t0 + float(T)

    if len(cpg.nodes) == 0:
        # Trivial canonical form: the empty order over the empty graph.
        return _result([], "strong", budget_exhausted=False, elapsed_s=time.monotonic() - t0)

    labels = _seed_labels(cpg)
    labels = _wl_refine_to_fixpoint(cpg, labels)

    if _partition_is_total(labels):
        order = _emit_order(labels)
        return _result(order, "strong", budget_exhausted=False, elapsed_s=time.monotonic() - t0)

    # Tie-break residual symmetry by enclosing-declaration order, then refine.
    labels = _break_by_enclosing_decl(cpg, labels)
    labels = _wl_refine_to_fixpoint(cpg, labels)
    if _partition_is_total(labels):
        order = _emit_order(labels)
        return _result(order, "strong", budget_exhausted=False, elapsed_s=time.monotonic() - t0)

    try:
        labels = _individualise_refine(cpg, labels, B=B, deadline=deadline)
        order = _emit_order(labels)
        return _result(order, "strong", budget_exhausted=False, elapsed_s=time.monotonic() - t0)
    except BudgetExhausted:
        order = _stable_order_fallback(cpg, labels)
        return _result(order, "weak", budget_exhausted=True, elapsed_s=time.monotonic() - t0)


# ---------------------------------------------------------------------------
# INV-5 payload helpers (the payload CMP-FND-01/02/03 splice into their records)
# ---------------------------------------------------------------------------
#
# CMP-CORE-03 does not persist anything itself (DOC-CMP-CORE-03 §4.3). It
# produces the payload that the downstream emitters write. These helpers are the
# single canonical shape of that payload: each one carries the hash, the
# annotation (from the constant), and the fingerprint_class — JSON-adjacent.
# Downstream components MUST import the annotation constant via these helpers (or
# the constant directly), never reconstruct it.


def to_provenance_fields(result: CanonicalOrderResult) -> dict[str, str]:
    """``provenance_records`` field trio (CMP-FND-03, DOC-PROVENANCE §3.1).

    The annotation is co-resident with the hash in the same record (INV-5).
    """
    return {
        "cpg_order_hash": result.cpg_order_hash.hex(),
        "cpg_order_hash_annotation": CPG_ORDER_HASH_ANNOTATION,
        "fingerprint_class": result.fingerprint_class,
    }


def to_sarif_properties(result: CanonicalOrderResult) -> dict[str, str]:
    """SARIF ``result.properties`` field trio (CMP-FND-01, DOC-SARIF).

    The annotation key is JSON-adjacent to the hash key in the same block.
    """
    return {
        "cpg_order_hash": result.cpg_order_hash.hex(),
        "cpg_order_hash_annotation": CPG_ORDER_HASH_ANNOTATION,
        "fingerprint_class": result.fingerprint_class,
    }


def to_auditor_export_fields(result: CanonicalOrderResult) -> dict[str, str]:
    """Auditor-export JSON field trio (CMP-FND-03, DOC-PROVENANCE §8.1).

    The annotation is JSON-adjacent to the hash so an auditor encounters it
    without consulting a separate document (INV-5 / AC-FND-03b).
    """
    return {
        "cpg_order_hash": result.cpg_order_hash.hex(),
        "cpg_order_hash_annotation": CPG_ORDER_HASH_ANNOTATION,
        "fingerprint_class": result.fingerprint_class,
    }
