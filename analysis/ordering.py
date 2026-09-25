"""Content-binding canonical graph identities (BH MEA R18/R20).

V2 uses direction-aware vertex WL refinement and complete bounded IR. Only
directly certified swap automorphisms prune siblings. A completed search yields
canonical encoded structure, not a hash of raw IDs. B exhaustion yields a
deterministic same-source weak result; T exhaustion raises instead of choosing
another successful identity. Elapsed telemetry is not claimed to be pure.

Active contract: docs/PROPOSAL-BHMEA-CANONICAL-BUDGET-2026-09-25.md and the
Black Hat remediation R18/R20. Compatibility/history references:
DOC-CMP-CORE-03, DOC-ALGS section 6, DOC-PROVENANCE section 2.1, and
.claude/rules/01-invariants.md (INV-5). Obsolete raw-ID/time-fallback semantics
in those historical contracts are replaced by the versioned active contract.
"""

from __future__ import annotations

import hashlib
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final, Literal, NewType

NodeId = NewType("NodeId", int)
Sha256 = NewType("Sha256", bytes)
Duration = NewType("Duration", float)
FingerprintClass = Literal["strong", "weak"]
Annotation = Literal["canonical iff fingerprint_class = strong"]
CPG_ORDER_HASH_ANNOTATION: Final[Annotation] = "canonical iff fingerprint_class = strong"
DEFAULT_B: Final[int] = 2**16
DEFAULT_T: Final[Duration] = Duration(0.200)
GRAPH_IDENTITY_NAMESPACE: Final[str] = "scanipy-canonical-graph/2"
BUDGET_POLICY: Final[str] = "scanipy-budget-policy/2"


def _duration_seconds(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("T must be a finite positive duration in seconds")
    duration = float(value)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("T must be a finite positive duration in seconds")
    return duration


class BudgetExhausted(Exception):  # noqa: N818
    """Internal deterministic work exhaustion, not a deadline/malformed graph."""


class CanonicalizationDeadlineExceeded(TimeoutError):  # noqa: N818
    """The invocation is incomplete; no successful strong/weak result exists."""


@dataclass
class CanonicalizationBudget:
    """Shared work counter/deadline including nested normalization.

    B counts entered search states, including the root. Exactly B may finish;
    requesting B+1 takes the weak path. Checkpoints cover all phases. A worker
    watchdog is still needed for preemption: cooperative checks do not promise
    exact operating-system scheduling latency.
    """

    state_limit: int
    duration: float
    clock: Callable[[], float] = field(repr=False)
    started_at: float
    search_states: int = 0

    @classmethod
    def start(cls, B: int = DEFAULT_B, T: Duration = DEFAULT_T) -> CanonicalizationBudget:  # noqa: N803
        if isinstance(B, bool) or not isinstance(B, int) or B <= 0:
            raise ValueError("B must be a positive integer search-state limit")
        duration = _duration_seconds(T)
        clock = time.monotonic
        return cls(B, duration, clock, clock())

    def check(self) -> None:
        if self.clock() - self.started_at >= self.duration:
            raise CanonicalizationDeadlineExceeded("canonicalization deadline exceeded")

    def enter_state(self) -> None:
        self.check()
        if self.search_states == self.state_limit:
            raise BudgetExhausted
        self.search_states += 1

    def elapsed_ms(self) -> float:
        """Telemetry only; successful result paths explicitly check before return."""
        return (self.clock() - self.started_at) * 1000.0


@dataclass(frozen=True)
class CPGNode:
    node_id: NodeId
    kind: str
    operator_or_literal: str
    resolved_fqn: str
    enclosing_decl_fqn: str
    structural_path: str


@dataclass(frozen=True)
class CPGEdge:
    src: NodeId
    dst: NodeId
    kind: str


@dataclass
class CPG:
    """Supported minimal model. IDs are lookup keys, never strong identity."""

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
                node_id,
                kind,
                operator_or_literal,
                resolved_fqn,
                enclosing_decl_fqn,
                structural_path,
            )
        )
        return node_id

    def add_edge(self, src: NodeId, dst: NodeId, kind: str) -> None:
        self.edges.append(CPGEdge(src, dst, kind))


@dataclass(frozen=True)
class CanonicalOrderResult:
    canonical_order: list[NodeId]
    cpg_order_hash: Sha256
    fingerprint_class: FingerprintClass
    annotation: Annotation
    budget_exhausted: bool
    elapsed_ms: float
    # Old positional/manual constructions remain explicitly legacy. Real v2
    # producers below always supply namespaces, never these compatibility defaults.
    identity_namespace: str = "scanipy-cpg-order/1"
    budget_policy: str = "scanipy-budget-policy/1"
    search_states: int = 0


def _u64(value: int) -> bytes:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**64:
        raise ValueError("graph integer must be unsigned 64-bit")
    return value.to_bytes(8, "big")


def _text(value: str) -> bytes:
    if not isinstance(value, str):
        raise ValueError("graph labels must be strings")
    encoded = value.encode("utf-8", errors="strict")
    return _u64(len(encoded)) + encoded


def _label(node: CPGNode) -> bytes:
    return b"".join(
        _text(value)
        for value in (
            node.kind,
            node.operator_or_literal,
            node.resolved_fqn,
            node.enclosing_decl_fqn,
        )
    )


def validate_cpg(cpg: CPG, budget: CanonicalizationBudget | None = None) -> None:
    """Reject malformed/extended models instead of silently hashing a projection.

    New semantic fields must deliberately extend/version the encoding and may
    not disappear in a legacy graph copy or canonical hash.
    """
    if set(vars(cpg)) - {"model_version"} != {"nodes", "edges"}:
        raise ValueError("unsupported CPG graph fields; update the versioned semantic encoding")
    if getattr(cpg, "model_version", "scanipy-cpg/1") != "scanipy-cpg/1":
        raise ValueError("unsupported CPG model version for canonical graph encoding")
    node_fields = {
        "node_id",
        "kind",
        "operator_or_literal",
        "resolved_fqn",
        "enclosing_decl_fqn",
        "structural_path",
    }
    seen: set[NodeId] = set()
    for node in cpg.nodes:
        if budget:
            budget.check()
        if set(vars(node)) != node_fields:
            raise ValueError("unsupported CPG node fields; update the versioned semantic encoding")
        _u64(node.node_id)
        if node.node_id in seen:
            raise ValueError("duplicate CPG node ID")
        seen.add(node.node_id)
        _label(node)
        _text(node.structural_path)
    for edge in cpg.edges:
        if budget:
            budget.check()
        if set(vars(edge)) != {"src", "dst", "kind"}:
            raise ValueError("unsupported CPG edge fields; update the versioned semantic encoding")
        _u64(edge.src)
        _u64(edge.dst)
        if edge.src not in seen or edge.dst not in seen:
            raise ValueError("CPG edge references a missing node")
        if not edge.kind:
            raise ValueError("CPG edge kind must be nonempty")
        _text(edge.kind)


def encode_graph(
    cpg: CPG, order: list[NodeId], *, budget: CanonicalizationBudget | None = None
) -> bytes:
    """Framed labels and directed typed edges, with multiplicity and no IDs."""
    validate_cpg(cpg, budget)
    by_id = {node.node_id: node for node in cpg.nodes}
    if len(order) != len(by_id) or set(order) != set(by_id):
        raise ValueError("graph encoding requires a complete node permutation")
    rank = {node: i for i, node in enumerate(order)}
    parts = [b"SCANIPY-CANONICAL-GRAPH/2\n", _u64(len(order))]
    for node in order:
        if budget:
            budget.check()
        parts.append(_label(by_id[node]))
    edges = sorted(
        (edge.kind.encode("utf-8"), rank[edge.src], rank[edge.dst]) for edge in cpg.edges
    )
    parts.append(_u64(len(edges)))
    for kind, src, dst in edges:
        if budget:
            budget.check()
        parts.append(_u64(len(kind)) + kind + _u64(src) + _u64(dst))
    result = b"".join(parts)
    if budget:
        budget.check()
    return result


def _intern(signatures: dict[NodeId, bytes]) -> dict[NodeId, int]:
    """Bytewise ranks of exact framed signatures, not hash-based equivalence."""
    colors = {signature: i for i, signature in enumerate(sorted(set(signatures.values())))}
    return {node: colors[signature] for node, signature in signatures.items()}


@dataclass
class _GraphIndex:
    labels: dict[NodeId, bytes]
    incoming: dict[NodeId, list[tuple[bytes, NodeId]]]
    outgoing: dict[NodeId, list[tuple[bytes, NodeId]]]
    pairs: dict[tuple[NodeId, NodeId], tuple[bytes, ...]]

    @classmethod
    def build(cls, cpg: CPG, budget: CanonicalizationBudget) -> _GraphIndex:
        validate_cpg(cpg, budget)
        labels = {node.node_id: _label(node) for node in cpg.nodes}
        incoming: dict[NodeId, list[tuple[bytes, NodeId]]] = {node: [] for node in labels}
        outgoing: dict[NodeId, list[tuple[bytes, NodeId]]] = {node: [] for node in labels}
        pairs: dict[tuple[NodeId, NodeId], list[bytes]] = {}
        for edge in cpg.edges:
            budget.check()
            kind = edge.kind.encode("utf-8")
            incoming[edge.dst].append((kind, edge.src))
            outgoing[edge.src].append((kind, edge.dst))
            pairs.setdefault((edge.src, edge.dst), []).append(kind)
        return cls(
            labels,
            incoming,
            outgoing,
            {pair: tuple(sorted(kinds)) for pair, kinds in pairs.items()},
        )

    def refine(
        self, markers: dict[NodeId, int], budget: CanonicalizationBudget
    ) -> dict[NodeId, int]:
        colors = _intern(
            {node: label + _u64(markers.get(node, 0)) for node, label in self.labels.items()}
        )
        while colors:
            signatures: dict[NodeId, bytes] = {}
            for node in colors:
                budget.check()
                parts = [_u64(colors[node])]
                for adjacency in (self.incoming[node], self.outgoing[node]):
                    neighbors = sorted((kind, colors[other]) for kind, other in adjacency)
                    parts.append(_u64(len(neighbors)))
                    parts.extend(_u64(len(kind)) + kind + _u64(color) for kind, color in neighbors)
                signatures[node] = b"".join(parts)
            refined = _intern(signatures)
            if len(set(refined.values())) == len(set(colors.values())):
                return refined
            colors = refined
        return colors

    def swap_is_automorphism(self, a: NodeId, b: NodeId, budget: CanonicalizationBudget) -> bool:
        """Exact transposition certificate, not a WL/symmetry heuristic.

        Outside vertices are fixed. Every affected directed edge/multiplicity,
        self-loop, reciprocal edge and semantic label is checked. Callers only
        compare members of one marker-preserving color cell. Corresponding
        child trees therefore have identical certificates modulo the swap.
        """
        if self.labels[a] != self.labels[b]:
            return False
        if self.pairs.get((a, a), ()) != self.pairs.get((b, b), ()):
            return False
        if self.pairs.get((a, b), ()) != self.pairs.get((b, a), ()):
            return False
        for other in self.labels:
            budget.check()
            if other not in (a, b) and (
                self.pairs.get((a, other), ()) != self.pairs.get((b, other), ())
                or self.pairs.get((other, a), ()) != self.pairs.get((other, b), ())
            ):
                return False
        return True


def _canonical_search(
    cpg: CPG, index: _GraphIndex, budget: CanonicalizationBudget
) -> tuple[list[NodeId], bytes]:
    pending: list[dict[NodeId, int]] = [{}]
    best: tuple[bytes, tuple[NodeId, ...]] | None = None
    while pending:
        budget.enter_state()
        markers = pending.pop()
        colors = index.refine(markers, budget)
        cells: dict[int, list[NodeId]] = {}
        for node, color in colors.items():
            cells.setdefault(color, []).append(node)
        ambiguous = [(len(nodes), color) for color, nodes in cells.items() if len(nodes) > 1]
        if not ambiguous:
            order = sorted(colors, key=colors.__getitem__)
            candidate = (encode_graph(cpg, order, budget=budget), tuple(order))
            if best is None or candidate < best:
                best = candidate
            continue
        _, target_color = min(ambiguous)
        representatives: list[NodeId] = []
        for node in sorted(cells[target_color]):
            if not any(
                index.swap_is_automorphism(node, other, budget) for other in representatives
            ):
                representatives.append(node)
        for node in reversed(representatives):
            budget.check()
            pending.append({**markers, node: len(markers) + 1})
    assert best is not None  # Empty graph: one empty leaf.
    return list(best[1]), best[0]


def _stable_order_fallback(cpg: CPG) -> list[NodeId]:
    """Same-source fallback from untouched input, never a partial search state."""
    incident: dict[NodeId, list[str]] = {node.node_id: [] for node in cpg.nodes}
    for edge in cpg.edges:
        incident[edge.src].append(edge.kind)
        incident[edge.dst].append(edge.kind)
    return [
        node.node_id
        for node in sorted(
            cpg.nodes,
            key=lambda node: (
                hashlib.sha256(node.enclosing_decl_fqn.encode("utf-8")).digest(),
                node.structural_path.encode("utf-8"),
                tuple(sorted(incident[node.node_id])),
                _label(node),
                node.node_id,
            ),
        )
    ]


def canonical_order(
    cpg: CPG,
    *,
    B: int = DEFAULT_B,  # noqa: N803
    T: Duration = DEFAULT_T,  # noqa: N803
    _budget: CanonicalizationBudget | None = None,
) -> CanonicalOrderResult:
    """V2 identity or explicit deadline failure; B exhaustion alone is weak.

    ``_budget`` is the internal shared-invocation seam for slice normalization.
    Strong encoded structure is invariant; its raw-ID mapping is not. Consumers
    must retain ``identity_namespace`` instead of emitting new hashes as v1.
    """
    budget = _budget if _budget is not None else CanonicalizationBudget.start(B, T)
    index = _GraphIndex.build(cpg, budget)
    klass: FingerprintClass = "strong"
    try:
        order, encoded = _canonical_search(cpg, index, budget)
    except BudgetExhausted:
        budget.check()
        klass = "weak"
        order = _stable_order_fallback(cpg)
        encoded = encode_graph(cpg, order, budget=budget)
    domain = b"SCANIPY-CPG-STRONG/2\n" if klass == "strong" else b"SCANIPY-CPG-WEAK/2\n"
    digest = Sha256(hashlib.sha256(domain + encoded).digest())
    elapsed_ms = budget.elapsed_ms()
    budget.check()  # Total invocation deadline, including final encoding/hash/telemetry.
    return CanonicalOrderResult(
        order,
        digest,
        klass,
        CPG_ORDER_HASH_ANNOTATION,
        klass == "weak",
        elapsed_ms,
        GRAPH_IDENTITY_NAMESPACE,
        BUDGET_POLICY,
        budget.search_states,
    )


def to_provenance_fields(result: CanonicalOrderResult) -> dict[str, str]:
    """Co-resident graph class, annotation and namespace, never silently v1."""
    return {
        "cpg_order_hash": result.cpg_order_hash.hex(),
        "cpg_order_hash_annotation": CPG_ORDER_HASH_ANNOTATION,
        "fingerprint_class": result.fingerprint_class,
        "cpg_order_namespace": result.identity_namespace,
        "canonicalization_budget_policy": result.budget_policy,
    }


def to_sarif_properties(result: CanonicalOrderResult) -> dict[str, str]:
    return to_provenance_fields(result)


def to_auditor_export_fields(result: CanonicalOrderResult) -> dict[str, str]:
    return to_provenance_fields(result)
