"""CMP-CORE-02 slice identity; BH MEA canonical foundations (R18/R20).

The reverse witness cone is normalized by the existing minimal-model passes,
then canonically encoded with direction-aware WL and bounded IR. Strong certifies
that normalized graph, not completion of the missing real-language purity, alias,
and binding normalization. Full refactor acceptance remains R02/R06/R19 work.
Origin stays caller-owned: an oracle finding does not become deterministic-core.

Strong hashes are explicitly version 2. Source-less callers retain a namespaced
legacy witness fallback. The typed v2 entry point requires a real snapshot tree
digest; none is invented. Nested normalization shares B/T. B exhaustion is weak;
T expiry raises an incomplete attempt instead of selecting different successful
bytes. Elapsed telemetry is outside the deterministic semantic payload.

Active contract: docs/PROPOSAL-BHMEA-CANONICAL-BUDGET-2026-09-25.md (R18/R20).
Compatibility and remaining normalization obligations: DOC-CMP-CORE-02,
DOC-ALGS section 4, DOC-PROVENANCE section 2.1, and INV-5 in
.claude/rules/01-invariants.md. These references do not imply completed R06/R19.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise
from typing import Protocol

from analysis.ordering import (
    BUDGET_POLICY,
    CPG,
    CPG_ORDER_HASH_ANNOTATION,
    DEFAULT_B,
    DEFAULT_T,
    Annotation,
    BudgetExhausted,
    CanonicalizationBudget,
    CPGNode,
    Duration,
    FingerprintClass,
    NodeId,
    Sha256,
    canonical_order,
    encode_graph,
    validate_cpg,
)

SLICE_IDENTITY_NAMESPACE = "scanipy-slice-normal-form/2"
LEGACY_WITNESS_NAMESPACE = "scanipy-witness-edge-sequence/1"
SOURCE_WITNESS_NAMESPACE = "scanipy-source-witness/2"

# ---------------------------------------------------------------------------
# The input port (structural, not nominal)
# ---------------------------------------------------------------------------


class SliceRequest(Protocol):
    """Minimal shape :func:`compute_slice_fingerprint` needs: the realising witness path.

    Algorithm 3 consumes exactly ONE field of its input — the witness node
    sequence — and nothing else (see :func:`compute_slice_fingerprint`: the
    backward cone is taken from ``witness[-1]``, the fields the content hash
    reads all come from the ``CPG``). Typing the parameter as this structural
    Protocol rather than the nominal
    :class:`~analysis.ifds.solver.Finding` therefore widens the *port*, not the
    *guarantee*.

    Why structural: ``analysis.ifds.solver.Finding`` deliberately declares
    ``origin: Literal["deterministic-core"]`` and ``engine: Literal["ifds",
    "ide"]`` — a type-level honesty guard so nothing that is not a core finding
    can be spelled as one (INV-1). An oracle finding
    (``origin="oracle-passthrough"``, ``engine="semgrep"``) MUST NOT be
    shoehorned into that type; it presents its own witness carrier instead (see
    :class:`services.scan.oracle_fingerprint.OracleSliceRequest`).
    ``solver.Finding`` satisfies this Protocol structurally, so every existing
    caller is unchanged.

    IMPORTANT — this Protocol carries NO partition semantics. Computing a
    fingerprint says nothing about a finding's ``origin``: the determinism
    theorem (property (a)) covers ``origin=deterministic-core`` findings only,
    and a fingerprint computed for an oracle finding stays
    ``oracle-passthrough`` (``.claude/rules/05-determinism.md``). The caller owns
    the label; this module never sets or implies one.
    """

    @property
    def witness(self) -> tuple[NodeId, ...]: ...


class SourceScopedSliceRequest(SliceRequest, Protocol):
    """V2 weak identity requires a REAL digest supplied by the snapshot producer.

    This input is not synthesized from witness IDs, the graph, or a placeholder.
    The source-less entry point retains explicitly namespaced legacy weak bytes.
    """

    @property
    def source_tree_digest(self) -> Sha256: ...


# ---------------------------------------------------------------------------
# Error contracts (DOC-CMP-CORE-02 §7)
# ---------------------------------------------------------------------------


class EmptyWitness(Exception):  # noqa: N818 (named verbatim per DOC §7)
    """Algorithm 2 emitted a finding with no realising path. This is a
    CMP-CORE-01 bug (a finding must carry a non-empty witness); we do not silently
    degrade to a degenerate fingerprint (DOC-CMP-CORE-02 §7)."""


class WitnessNotInCPG(Exception):  # noqa: N818 (named verbatim per DOC §7)
    """A witness node id is absent from the CPG — likely a stale snapshot. We
    raise rather than silently degrade (DOC-CMP-CORE-02 §7)."""


# ---------------------------------------------------------------------------
# Result type (DOC-CMP-CORE-02 §3.1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SliceFingerprintResult:
    """Output of :func:`compute_slice_fingerprint`.

    ``cpg_order_hash_annotation`` is always the literal
    :data:`~analysis.ordering.CPG_ORDER_HASH_ANNOTATION` and MUST be persisted
    adjacent to the fingerprint everywhere it appears (INV-5 / DOC-CMP-CORE-02
    §5.1). Strong certifies a completed canonicalization of the implemented
    normalized graph. Full named-refactor proofs require the separate semantic
    normalization work. A weak hash is a same-source identity only, which MUST
    NEVER be auto-suppressed across a refactor (see
    :func:`eligible_for_baseline_suppression`).
    """

    slice_fingerprint: Sha256
    fingerprint_class: FingerprintClass
    budget_exhausted: bool
    elapsed_ms: float
    cpg_order_hash_annotation: Annotation
    identity_namespace: str = "scanipy-slice-fingerprint/1"
    budget_policy: str = "scanipy-budget-policy/1"
    search_states: int = 0


# ---------------------------------------------------------------------------
# Backward interprocedural slice (T-CMP-CORE-02-01; DOC §6 / §4.1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Slice:
    """A backward interprocedural slice: the CPG sub-graph induced by the witness
    nodes plus every CPG edge whose endpoints both lie on the slice. Carried as a
    small ``CPG`` so it can be fed to :func:`~analysis.ordering.canonical_order`
    unchanged."""

    cpg: CPG
    witness: tuple[NodeId, ...]


def _backward_interprocedural_slice(cpg: CPG, witness: tuple[NodeId, ...]) -> _Slice:
    """The backward interprocedural slice from the sink along the witness (DOC §6,
    §4.1).

    The witness is the realising source -> sink path CMP-CORE-01 reconstructed
    (``analysis.ifds.solver._witness``): a connected sequence of CPG node ids that
    crosses procedure boundaries via CALL edges, ending at the sink. The backward
    slice is the **reverse-reachable cone from the sink** over the dataflow edge
    kinds (CFG / CALL / PDG), unioned with the witness nodes themselves — i.e.
    every node from which the sink is reachable along those edges, plus the
    realising path. The induced sub-graph carries every CPG edge whose *both*
    endpoints lie on the cone (all kinds preserved, so AST/structural decoration
    survives for the PDG-only pass to reason over).

    A witness records one path, not all dependencies influencing the sink. The
    cone retains those dependencies, including branches entering intermediate
    witness nodes. The canonicalizer must see that structure rather than an
    artificially simplified path. This still does not add missing interprocedural
    relations to an incomplete upstream model.

    The weak-fallback hash is computed over ``self.witness`` (the ``O(|witness|)``
    linearisation), kept verbatim here; the cone only feeds the *strong*-path
    canonicalisation.

    Raises :class:`EmptyWitness` / :class:`WitnessNotInCPG` per DOC §7.
    """
    if len(witness) == 0:
        raise EmptyWitness("CMP-CORE-01 emitted a finding with an empty witness")

    node_by_id = {n.node_id: n for n in cpg.nodes}
    for nid in witness:
        if nid not in node_by_id:
            raise WitnessNotInCPG(f"witness node {int(nid)} is not in the CPG (stale snapshot?)")

    # Reverse adjacency over dataflow edge kinds (the kinds the taint propagates
    # along — CFG intra-proc, CALL inter-proc, PDG data-dependence). AST/other
    # structural kinds are not traversed for reachability but ARE kept as induced
    # edges below so a future PDG-only pass can strip them.
    dataflow_kinds = {"CFG", "CALL", "PDG"}
    preds: dict[NodeId, list[NodeId]] = {n.node_id: [] for n in cpg.nodes}
    for e in cpg.edges:
        if e.kind in dataflow_kinds and e.dst in preds:
            preds[e.dst].append(e.src)

    # Backward reverse-reachable cone from the sink (the witness's last node),
    # unioned with the witness path itself (it is reachable by construction, but
    # union it explicitly so an inter-proc CALL hop on the witness is never lost).
    sink = witness[-1]
    on_slice: set[NodeId] = set(witness)
    traversed: set[NodeId] = set()
    stack = [sink]
    while stack:
        cur = stack.pop()
        if cur in traversed:
            continue
        traversed.add(cur)
        for p in preds.get(cur, ()):
            on_slice.add(p)
            # Membership is not traversal state: an intermediate witness node
            # already belongs to the slice but its incoming dependencies must
            # still be visited. The old membership test dropped those branches.
            if p not in traversed:
                stack.append(p)

    sliced = CPG()
    # Add nodes in a deterministic order (by original id); canonical_order
    # re-derives a parse-order-independent enumeration over them anyway.
    remap: dict[NodeId, NodeId] = {}
    for nid in sorted(on_slice, key=int):
        n = node_by_id[nid]
        remap[nid] = sliced.add_node(
            n.kind,
            operator_or_literal=n.operator_or_literal,
            resolved_fqn=n.resolved_fqn,
            enclosing_decl_fqn=n.enclosing_decl_fqn,
            structural_path=n.structural_path,
        )
    for e in cpg.edges:
        if e.src in on_slice and e.dst in on_slice:
            sliced.add_edge(remap[e.src], remap[e.dst], e.kind)
    # Witness expressed over the slice's own (remapped) ids, preserving order/revisits.
    remapped_witness = tuple(remap[nid] for nid in witness)
    return _Slice(cpg=sliced, witness=remapped_witness)


# ---------------------------------------------------------------------------
# The five named normalisation passes (T-CMP-CORE-02-02; DOC §3.2, DOC-ALGS §4.4)
# ---------------------------------------------------------------------------
#
# Each pass returns a *new* CPG (the passes are pure). They are applied in the
# fixed order the DOC names them; the order is load-bearing (e.g. FQN
# normalisation must run after alpha-rename so a renamed-then-moved local is stable).


def _node(cpg: CPG, nid: NodeId) -> CPGNode:
    for n in cpg.nodes:
        if n.node_id == nid:
            return n
    raise KeyError(nid)


def _copy_nodes(
    src: CPG,
    dst: CPG,
    *,
    rename: Callable[[CPGNode], str] | None = None,
) -> dict[NodeId, NodeId]:
    """Copy ``src`` nodes into ``dst`` (preserving order), optionally rewriting
    ``operator_or_literal`` via ``rename(node) -> str``. Returns old->new id map."""
    remap: dict[NodeId, NodeId] = {}
    for n in src.nodes:
        op = rename(n) if rename is not None else n.operator_or_literal
        remap[n.node_id] = dst.add_node(
            n.kind,
            operator_or_literal=op,
            resolved_fqn=n.resolved_fqn,
            enclosing_decl_fqn=n.enclosing_decl_fqn,
            structural_path=n.structural_path,
        )
    return remap


def _copy_edges(src: CPG, dst: CPG, remap: dict[NodeId, NodeId]) -> None:
    for e in src.edges:
        dst.add_edge(remap[e.src], remap[e.dst], e.kind)


def _alpha_rename_locals(slice_cpg: CPG, *, _budget: CanonicalizationBudget | None = None) -> CPG:
    """Pass 1 — alpha-renaming for locals (DOC §3.2.1).

    Every IDENTIFIER node's ``operator_or_literal`` (its local-variable name) is
    replaced by a deterministic positional counter assigned in canonical order, so
    a refactor that renames a local (``x`` -> ``userInput``) leaves the normalised
    slice — and therefore the fingerprint — unchanged. Non-local nodes (CALL
    targets, METHOD names, literals) are NOT renamed: their text is dataflow-
    relevant content the fingerprint must remain sensitive to (a changed sink call
    target must flip the fingerprint, AC-CORE-02b). "Local" is identified
    structurally as ``kind == "IDENTIFIER"`` on the minimal CPG model
    (DOC-CMP-CORE-02 §3.2; the per-language def/use back-end that distinguishes a
    local from a field reference is deferred — see CLAR-CORE-02 below).
    """
    if not any(node.kind == "IDENTIFIER" for node in slice_cpg.nodes):
        return slice_cpg
    # Names must not influence the ordering that assigns canonical local names.
    # This is the minimal model's occurrence-based pass, NOT a claim that fields
    # or language-level bindings are modeled. Extended model fields fail closed.
    anonymized = CPG()
    anonymized_remap = _copy_nodes(
        slice_cpg,
        anonymized,
        rename=lambda node: "" if node.kind == "IDENTIFIER" else node.operator_or_literal,
    )
    _copy_edges(slice_cpg, anonymized, anonymized_remap)
    ordering = canonical_order(anonymized, _budget=_budget)
    if ordering.fingerprint_class != "strong":
        raise BudgetExhausted
    inverse = {mapped: original for original, mapped in anonymized_remap.items()}
    order = [inverse[node] for node in ordering.canonical_order]
    counter: dict[NodeId, int] = {}
    next_local = 0
    for nid in order:
        node = _node(slice_cpg, nid)
        if node.kind == "IDENTIFIER":
            counter[nid] = next_local
            next_local += 1

    def _rename(n: CPGNode) -> str:
        return f"%local{counter[n.node_id]}" if n.node_id in counter else n.operator_or_literal

    out = CPG()
    remap = _copy_nodes(slice_cpg, out, rename=_rename)
    _copy_edges(slice_cpg, out, remap)
    return out


def _drop_pdg_only_formatting(slice_cpg: CPG) -> CPG:
    """Pass 2 — PDG-only formatting normalisation (DOC §3.2.2).

    Formatting-only AST decoration (whitespace, comment positions, trailing
    commas, parenthesisation that does not change the PDG) is dropped so only
    PDG-relevant structure survives. On the **minimal CPG model** there is no
    distinct "formatting-only AST decoration" node category to strip — the model
    already carries only PDG/CFG/CALL/AST-structural nodes — so this pass is a
    DELIBERATE NO-OP on this model and is documented as such (it does not pose as
    implemented). The per-language formatting-vs-PDG partition needs the concrete
    front-end AST and is filed as CLAR-CORE-02 below (DOC §10 invites this). It is
    retained as a named, ordered pass so the pipeline shape matches DOC §3.2 and so
    a future front-end can populate it without re-threading the call sites.
    """
    return slice_cpg


def _canonical_topo_sort(slice_cpg: CPG) -> CPG:
    """Pass 3 — canonical topological sort for independent reordering (DOC §3.2.3).

    Independent statements (data-dependence-wise) are ordered by the canonical
    traversal from CMP-CORE-03. Concretely, the fingerprint's content hash already
    consumes nodes in :func:`~analysis.ordering.canonical_order` (a deterministic,
    parse-order- AND independent-reorder-invariant enumeration), so reordering two
    independent statements does not change the hash. This pass is therefore the
    identity on the slice graph itself — the canonicalisation it names is performed
    at hash time by ``_content_hash`` consuming the canonical order. Kept as a
    named, ordered pass for DOC §3.2 fidelity and to localise any future
    materialised re-sort.
    """
    return slice_cpg


def _summary_inline_pure_extract(slice_cpg: CPG) -> CPG:
    """Pass 4 — summary-inlining normalisation for extract/inline-method
    (PURE extract only; DOC §3.2.4, DOC-ALGS §4.9).

    A pure extract-method refactor (factor a side-effect-free, alias-stable
    sequence into a callee, or inline it back) must leave the fingerprint
    unchanged; an IMPURE extract that changes aliasing or side-effect order MUST
    flip it (AC-CORE-02b). Honouring the safe half of this on the minimal CPG model
    requires a purity/alias oracle that the model does not carry (no alias graph,
    no effect summary), and "the precise definition of 'pure extract'" is named by
    DOC §10 as clar-worthy. Implementing a heuristic here would risk normalising an
    IMPURE extract — silently auto-suppressing a genuinely-changed finding, the
    exact failure AC-CORE-02b guards against. The safe, INV-honouring subset is
    therefore: **normalise nothing** (every extract — pure or impure — currently
    flips the fingerprint). This is the one-sided-safe choice: we never wrongly
    suppress; we only miss the pure-extract invariance (a recall, not a soundness,
    gap), which the corpus-scale AC-CORE-02a half measures once CMP-CORP-REFAC-01
    lands. Filed as CLAR-CORE-02 below.
    """
    return slice_cpg


def _fqn_normalise(slice_cpg: CPG) -> CPG:
    """Pass 5 — FQN normalisation for file-move / package-rename (DOC §3.2.5).

    A file-move / package-rename refactor changes a declaration's
    fully-qualified name (``com.old.Pkg.foo`` -> ``com.new.Pkg.foo``) without
    changing its dataflow role. Each FQN (on ``resolved_fqn`` and
    ``enclosing_decl_fqn``) is reduced to its STRUCTURAL identity: the terminal
    symbol (the last ``.``-segment — the member/method name, which IS
    dataflow-relevant) is kept while the package/path prefix is collapsed to a
    single canonical token. So ``com.old.Pkg.foo`` and ``com.new.Pkg.foo`` both
    normalise to ``%pkg.foo`` and become invariant, while a genuinely different
    target (``...bar``) stays distinct. Empty FQNs are left empty.
    """

    def _norm_fqn(fqn: str) -> str:
        if not fqn:
            return ""
        terminal = fqn.rsplit(".", 1)[-1]
        return f"%pkg.{terminal}"

    out = CPG()
    remap: dict[NodeId, NodeId] = {}
    for n in slice_cpg.nodes:
        remap[n.node_id] = out.add_node(
            n.kind,
            operator_or_literal=n.operator_or_literal,
            resolved_fqn=_norm_fqn(n.resolved_fqn),
            enclosing_decl_fqn=_norm_fqn(n.enclosing_decl_fqn),
            structural_path=n.structural_path,
        )
    _copy_edges(slice_cpg, out, remap)
    return out


_NORMALISATION_PASSES: tuple[Callable[[CPG], CPG], ...] = (
    _alpha_rename_locals,
    _drop_pdg_only_formatting,
    _canonical_topo_sort,
    _summary_inline_pure_extract,
    _fqn_normalise,
)


def _normalise(slice_cpg: CPG, *, _budget: CanonicalizationBudget | None = None) -> CPG:
    """Apply the five named passes in the fixed DOC §3.2 order."""
    out = slice_cpg
    for pass_ in _NORMALISATION_PASSES:
        if _budget:
            _budget.check()
        out = (
            _alpha_rename_locals(out, _budget=_budget)
            if pass_ is _alpha_rename_locals
            else pass_(out)
        )
    return out


# ---------------------------------------------------------------------------
# Content hash over the canonicalised normal form (strong path)
# ---------------------------------------------------------------------------


def _content_hash(
    normal_slice: CPG, order: list[NodeId], *, budget: CanonicalizationBudget | None = None
) -> Sha256:
    """sha256 over the NORMALISED node labels (in canonical order) + the
    normalised edge relation (DOC §3.2 step 3 / DOC-ALGS §4.4).

    Uses the same v2 framed graph encoding as CMP-CORE-03 with a distinct slice
    domain. It hashes normalized content — ``(kind, operator_or_literal, resolved_fqn,
    enclosing_decl_fqn)`` per node and ``(edge_kind, src_rank, dst_rank)`` per edge,
    where ``rank`` is the node's position in the canonical order. Hashing content
    (not ids) retains changed graph semantics. Whether a real program refactor
    maps to an equivalent normalized graph is a separate normalization/fidelity
    obligation, not something this content encoder can establish.
    ``structural_path`` is intentionally EXCLUDED — it is a parse-position artefact
    a file-move/reorder would perturb without changing dataflow.
    """
    encoded = encode_graph(normal_slice, order, budget=budget)
    return Sha256(hashlib.sha256(b"SCANIPY-SLICE-STRONG/2\n" + encoded).digest())


def _witness_edge_sequence_hash(witness: tuple[NodeId, ...]) -> Sha256:
    """The ``O(|witness|)``-capped weak fallback (DOC §3.3 / DOC-ALGS §4.5).

    A deterministic linearisation of the witness path: sha256 over the witness
    node-id sequence (8-byte big-endian per id). Same source ⇒ byte-identical weak
    hash. NOT canonical across isomorphic programs — hence ``fingerprint_class =
    "weak"`` and the never-auto-suppress rule.
    """
    h = hashlib.sha256()
    h.update(b"CMP-CORE-02/witness-edge-sequence/v1\n")
    for nid in witness:
        h.update(int(nid).to_bytes(8, "big", signed=False))
    return Sha256(h.digest())


# ---------------------------------------------------------------------------
# Public entry point (DOC-CMP-CORE-02 §3.1)
# ---------------------------------------------------------------------------


def compute_slice_fingerprint(
    finding: SliceRequest,
    cpg: CPG,
    *,
    B: int = DEFAULT_B,  # noqa: N803 ((B, T) budget symbols are the public contract)
    T: Duration = DEFAULT_T,  # noqa: N803
) -> SliceFingerprintResult:
    """V2 strong identity; explicitly legacy weak identity for source-less callers.

    B exhaustion is weak; deadline expiry raises CanonicalizationDeadlineExceeded.
    The class certifies canonicalization of the implemented normalized graph,
    not completion of missing language/purity normalization. This function sets
    no origin. Consumers must preserve identity_namespace with the hash.
    """
    return _compute(finding, cpg, B=B, T=T, source_tree_digest=None)


def compute_slice_fingerprint_v2(
    finding: SourceScopedSliceRequest,
    cpg: CPG,
    *,
    B: int = DEFAULT_B,  # noqa: N803
    T: Duration = DEFAULT_T,  # noqa: N803
) -> SliceFingerprintResult:
    """Source-aware v2 weak encoding; requires a real upstream tree digest."""
    digest = finding.source_tree_digest
    if not isinstance(digest, bytes) or len(digest) != 32:
        raise ValueError("source_tree_digest must be 32 real digest bytes")
    return _compute(finding, cpg, B=B, T=T, source_tree_digest=digest)


def _source_witness_hash(
    cpg: CPG,
    witness: tuple[NodeId, ...],
    digest: bytes,
    budget: CanonicalizationBudget,
) -> Sha256:
    adjacency: dict[tuple[NodeId, NodeId], list[bytes]] = {}
    for edge in cpg.edges:
        budget.check()
        adjacency.setdefault((edge.src, edge.dst), []).append(edge.kind.encode("utf-8"))
    h = hashlib.sha256(b"SCANIPY-SLICE-WEAK/2\n" + digest)
    h.update(len(witness).to_bytes(8, "big"))
    for node in witness:
        budget.check()
        h.update(int(node).to_bytes(8, "big"))
    for src, dst in pairwise(witness):
        kinds = sorted(adjacency.get((src, dst), []))
        if not kinds:
            raise ValueError("source-scoped witness has a disconnected step")
        h.update(len(kinds).to_bytes(8, "big"))
        for kind in kinds:
            h.update(len(kind).to_bytes(8, "big") + kind)
    return Sha256(h.digest())


def _compute(
    finding: SliceRequest,
    cpg: CPG,
    *,
    B: int,  # noqa: N803
    T: Duration,  # noqa: N803
    source_tree_digest: bytes | None,
) -> SliceFingerprintResult:
    budget = CanonicalizationBudget.start(B, T)
    # Validate before copying: extended semantic fields must not be silently lost.
    validate_cpg(cpg, budget)
    sliced = _backward_interprocedural_slice(cpg, finding.witness)
    budget.check()
    # A typed source-aware witness must be connected on every outcome, not only
    # when its weak hash happens to be used. Retain the computed fallback bytes.
    source_weak = (
        _source_witness_hash(cpg, finding.witness, source_tree_digest, budget)
        if source_tree_digest is not None
        else None
    )
    try:
        normal = _normalise(sliced.cpg, _budget=budget)
        ordering = canonical_order(normal, _budget=budget)
        if ordering.fingerprint_class == "weak":
            raise BudgetExhausted
        fingerprint = _content_hash(normal, ordering.canonical_order, budget=budget)
        klass: FingerprintClass = "strong"
        namespace = SLICE_IDENTITY_NAMESPACE
    except BudgetExhausted:
        budget.check()
        klass = "weak"
        if source_tree_digest is None:
            fingerprint = _witness_edge_sequence_hash(sliced.witness)
            namespace = LEGACY_WITNESS_NAMESPACE
        else:
            assert source_weak is not None
            fingerprint = source_weak
            namespace = SOURCE_WITNESS_NAMESPACE
    elapsed_ms = budget.elapsed_ms()
    budget.check()  # No completed/weak artifact is published after the total deadline.
    return SliceFingerprintResult(
        fingerprint,
        klass,
        klass == "weak",
        elapsed_ms,
        CPG_ORDER_HASH_ANNOTATION,
        namespace,
        BUDGET_POLICY,
        budget.search_states,
    )


# ---------------------------------------------------------------------------
# CORE-02-owned baseline-suppression predicate (T-CMP-CORE-02-04; INV-5)
# ---------------------------------------------------------------------------


def eligible_for_baseline_suppression(result: SliceFingerprintResult) -> bool:
    """Necessary slice-side condition, not the complete decision-retention policy.

    Weak and legacy/unrecognized identities are ineligible. The caller must also
    check the independent graph class, compatible versions/semantic coverage,
    actual finding correspondence, and explicit user decision. Historical strong
    labels from the defective v1 algorithm are not upgraded retroactively.
    """
    return (
        result.fingerprint_class == "strong"
        and result.identity_namespace == SLICE_IDENTITY_NAMESPACE
    )


__all__ = [
    "EmptyWitness",
    "SliceFingerprintResult",
    "SliceRequest",
    "SourceScopedSliceRequest",
    "WitnessNotInCPG",
    "compute_slice_fingerprint",
    "compute_slice_fingerprint_v2",
    "eligible_for_baseline_suppression",
]
