"""CMP-CORE-02 — Slice fingerprint (Algorithm 3).

For each :class:`~analysis.ifds.solver.Finding` produced by CMP-CORE-01, this
module computes the **refactor-stable cross-scan/cross-refactor identity** of the
finding: a backward interprocedural slice along the realising witness, reduced to
a normal form by the five named normalisation passes, then canonicalised under
the shared ``(B, T)`` budget. The output is a ``slice_fingerprint: Sha256`` plus
a ``fingerprint_class ∈ {strong, weak}`` self-label (the gating field for INV-5's
conditional-canonicality semantics).

Source-of-truth: ``DOC-CMP-CORE-02``, ``DOC-ALGS §4`` (Algorithm 3),
``DOC-PARTITION``, ``.claude/rules/02-provenance.md``,
``.claude/rules/01-invariants.md §INV-5``.

BUILD-AHEAD (CLAR-PROC-01, WBS §17 RESOLVED 2026-06-04).
  CMP-CORE-02 stays IN-PROGRESS: the corpus-scale empirical halves of
  ``AC-CORE-02a`` (50 seeded findings, ``CMP-CORP-REFAC-01``), ``AC-CORE-02b``
  (aliasing-changing-extract seed, ``tests/corpora/refactor/corpus.lock``) and
  ``AC-CORE-02c`` (``CMP-CORP-CANARY-01`` weak-rate roll-up) are corpus-gated and
  remain honestly ``xfail``. This module ships the *mechanism* + the hermetic
  acceptance criteria (TST-INV-5-CORE-02 + synthetic positive/negative/weak/budget
  controls). Per the three binding CLAR-PROC-01 conditions: (1) only the hermetic
  subset is asserted green; the corpus halves stay xfail/skip, never faked; (2)
  upstream values are consumed via the typed CMP-CORE-01/03 interfaces
  (:class:`~analysis.ifds.solver.Finding`, :func:`~analysis.ordering.canonical_order`),
  never computed-as-fake; (3) the PR declares prep status and the component stays
  IN-PROGRESS.

INTERFACE RECONCILE (reported, not invented — same pattern as CLAR-CORE-01).
  ``DOC-CMP-CORE-02 §3.1`` types the witness parameter as ``witness_path: "Path"``
  and references ``Finding`` / ``CPG`` placeholders. The **shipped** CMP-CORE-01
  ``Finding.witness`` (``analysis.ifds.solver.Finding``) is a concrete
  ``tuple[NodeId, ...]`` — a connected source -> sink node sequence through the
  supergraph (verified inter-procedurally as of CORE-01 PR2/PR3). This module
  therefore consumes ``Finding`` and ``CPG`` from the shipped types and treats the
  witness as that concrete tuple. ``B`` / ``T`` and the ``(B, T)`` budget machinery
  are shared verbatim with CMP-CORE-03 via :mod:`analysis.ordering` (single
  source of the budget, the ``BudgetExhausted`` signal, and the
  ``CPG_ORDER_HASH_ANNOTATION`` constant).

STRUCTURAL INPUT PORT (:class:`SliceRequest`).
  Algorithm 3 reads exactly one field off its input — the witness node sequence —
  so the entry point is typed against the structural :class:`SliceRequest`
  Protocol instead of the nominal ``solver.Finding``. ``solver.Finding``
  satisfies it structurally (no caller changes), and an **oracle** finding —
  which must NOT be spelled as a ``solver.Finding``, whose ``origin`` /
  ``engine`` literals are a deliberate INV-1 honesty guard — can present its own
  witness carrier (:class:`services.scan.oracle_fingerprint.OracleSliceRequest`).
  Widening the port does NOT widen any guarantee: the determinism theorem still
  covers ``origin=deterministic-core`` findings only.

WHY THE FINGERPRINT IS A *CONTENT* HASH, NOT THE CPG-ORDER HASH.
  CMP-CORE-03's ``cpg_order_hash`` is a hash of node *ids* in canonical order; it
  is invariant under an alpha-rename only because the ids happen to be identical, not
  because the renamed content was normalised away. Reusing it as the fingerprint
  would make refactor-invariance hold for the wrong reason and would mask a broken
  normalisation pass. This module instead uses :func:`~analysis.ordering.canonical_order`
  ONLY for the ordering + the strong/weak verdict, and computes its OWN content
  hash over the *normalised* node labels (in canonical order) and the normalised
  edge relation. A broken alpha-rename therefore changes the fingerprint — which is
  exactly what the mutation-verified negative control in the unit tests asserts.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from analysis.ordering import (
    CPG,
    CPG_ORDER_HASH_ANNOTATION,
    DEFAULT_B,
    DEFAULT_T,
    Annotation,
    CPGNode,
    Duration,
    FingerprintClass,
    NodeId,
    Sha256,
    canonical_order,
)

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
    §5.1). The fingerprint is a true refactor-stable identity (equal across the
    named refactors) iff ``fingerprint_class == "strong"``; on the ``weak`` path it
    is the witness-edge-sequence hash — a same-source identity only, which MUST
    NEVER be auto-suppressed across a refactor (see
    :func:`eligible_for_baseline_suppression`).
    """

    slice_fingerprint: Sha256
    fingerprint_class: FingerprintClass
    budget_exhausted: bool
    elapsed_ms: float
    cpg_order_hash_annotation: Annotation


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

    Why a CONE, not just the witness nodes (DOC-ALGS §4.5): the complexity table
    lists strong as ``O(|slice|)`` and weak as ``O(|witness|)`` *separately*, so the
    slice is strictly larger than the witness. The witness is a single realising
    PATH (RHS write-once ``pred`` picks one predecessor per ``(node, fact)``), so a
    witness-only slice is always a chain — 2-WL resolves every chain node and the
    bounded-canonicalisation budget is never consulted (the ``weak`` branch would be
    dead code). The backward cone restores the genuine dataflow structure (e.g.
    both arms of a branch that both reach the sink), so a structurally-symmetric
    program drives the real ``(B, T)`` budget and the ``weak`` fallback.

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
    stack = [sink]
    while stack:
        cur = stack.pop()
        for p in preds.get(cur, ()):
            if p not in on_slice:
                on_slice.add(p)
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


def _alpha_rename_locals(slice_cpg: CPG) -> CPG:
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
    order = canonical_order(slice_cpg).canonical_order
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


def _normalise(slice_cpg: CPG) -> CPG:
    """Apply the five named passes in the fixed DOC §3.2 order."""
    out = slice_cpg
    for pass_ in _NORMALISATION_PASSES:
        out = pass_(out)
    return out


# ---------------------------------------------------------------------------
# Content hash over the canonicalised normal form (strong path)
# ---------------------------------------------------------------------------


def _content_hash(normal_slice: CPG, order: list[NodeId]) -> Sha256:
    """sha256 over the NORMALISED node labels (in canonical order) + the
    normalised edge relation (DOC §3.2 step 3 / DOC-ALGS §4.4).

    Unlike CMP-CORE-03's ``cpg_order_hash`` (which hashes node *ids*), this hashes
    the normalised *content* — ``(kind, operator_or_literal, resolved_fqn,
    enclosing_decl_fqn)`` per node and ``(edge_kind, src_rank, dst_rank)`` per edge,
    where ``rank`` is the node's position in the canonical order. Hashing content
    (not ids) is what makes the fingerprint sensitive to a changed sink / added
    sanitizer (AC-CORE-02b) yet invariant under the alpha-rename/FQN/reorder refactors
    (their effect is normalised away by the passes BEFORE this hash).
    ``structural_path`` is intentionally EXCLUDED — it is a parse-position artefact
    a file-move/reorder would perturb without changing dataflow.
    """
    rank = {nid: i for i, nid in enumerate(order)}
    node_by_id = {n.node_id: n for n in normal_slice.nodes}
    h = hashlib.sha256()
    h.update(b"CMP-CORE-02/slice-fingerprint/v1\n")
    for nid in order:
        n = node_by_id[nid]
        h.update(
            repr((n.kind, n.operator_or_literal, n.resolved_fqn, n.enclosing_decl_fqn)).encode(
                "utf-8"
            )
        )
        h.update(b"\x00")
    h.update(b"|edges|")
    edge_keys = sorted(
        (e.kind, rank.get(e.src, 1 << 30), rank.get(e.dst, 1 << 30)) for e in normal_slice.edges
    )
    for kind, s, d in edge_keys:
        h.update(repr((kind, s, d)).encode("utf-8"))
        h.update(b"\x00")
    return Sha256(h.digest())


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
    """Backward interprocedural slice + bounded canonicalisation per Algorithm 3.

    Pure: the same ``(finding, cpg, B, T)`` always yields the same
    :class:`SliceFingerprintResult` (no I/O, no global state, no randomness).

    The witness is consumed from ``finding.witness`` (a concrete
    ``tuple[NodeId, ...]`` per the CORE-01 PR2/PR3 reconcile — see the module
    docstring); it is the ONLY field read off the parameter, which is therefore
    typed as the structural :class:`SliceRequest` port rather than the nominal
    ``solver.Finding``. Computing a fingerprint asserts NOTHING about the
    finding's ``origin`` — see :class:`SliceRequest`. On ``(B, T)`` exhaustion,
    returns ``fingerprint_class = "weak"``
    with the witness-edge-sequence hash. A ``weak`` fingerprint MUST NOT be used to
    auto-suppress a finding across a refactor (AC-CORE-02c; the CORE-02-owned
    predicate :func:`eligible_for_baseline_suppression` encodes this for the
    CMP-FND-01 baseline policy to consume).

    Raises :class:`EmptyWitness` if the witness is empty and :class:`WitnessNotInCPG`
    if a witness node is not in ``cpg`` (DOC §7) — defined error contracts, never a
    silent degrade.
    """
    t0 = time.monotonic()

    # 1. Backward interprocedural slice along the witness.
    sliced = _backward_interprocedural_slice(cpg, finding.witness)

    # 2. The five named normalisation passes (fixed order).
    normal = _normalise(sliced.cpg)

    # 3. Bounded canonicalisation under the SHARED (B, T) budget. canonical_order
    #    returns the strong/weak verdict: strong iff 2-WL + bounded individualisation
    #    -refinement converged within (B, T); weak on BudgetExhausted. We reuse its
    #    verdict + ordering, and compute our OWN content hash over the normalised
    #    slice (see _content_hash for why a content hash, not cpg_order_hash).
    order_result = canonical_order(normal, B=B, T=T)

    if order_result.fingerprint_class == "strong":
        fingerprint = _content_hash(normal, order_result.canonical_order)
        return SliceFingerprintResult(
            slice_fingerprint=fingerprint,
            fingerprint_class="strong",
            budget_exhausted=False,
            elapsed_ms=(time.monotonic() - t0) * 1000.0,
            cpg_order_hash_annotation=CPG_ORDER_HASH_ANNOTATION,
        )

    # 4. Budget exhausted -> weak fallback (witness-edge-sequence hash). NEVER an
    #    exception, never a fake "strong" (INV-5 self-label truthfulness).
    fingerprint = _witness_edge_sequence_hash(sliced.witness)
    return SliceFingerprintResult(
        slice_fingerprint=fingerprint,
        fingerprint_class="weak",
        budget_exhausted=True,
        elapsed_ms=(time.monotonic() - t0) * 1000.0,
        cpg_order_hash_annotation=CPG_ORDER_HASH_ANNOTATION,
    )


# ---------------------------------------------------------------------------
# CORE-02-owned baseline-suppression predicate (T-CMP-CORE-02-04; INV-5)
# ---------------------------------------------------------------------------


def eligible_for_baseline_suppression(result: SliceFingerprintResult) -> bool:
    """Whether a finding with this fingerprint MAY be auto-suppressed by the
    CMP-FND-01 baseline-lookup policy across a refactor (INV-5 / AC-CORE-02c).

    This is the **CORE-02-owned typed interface CMP-FND-01 consumes** (build-ahead
    per CLAR-PROC-01): the baseline-suppression POLICY lives in CMP-FND-01
    (DOC-CMP-CORE-02 §5.1.3), which is out of this component's file set, but the
    *rule* that a ``weak``-classed fingerprint is NEVER eligible is CMP-CORE-02's
    contribution (the truthful flag) and is encoded here so FND-01 reads it from
    one place rather than re-deriving it. Returns ``False`` for every ``weak``
    result; ``True`` only for ``strong`` (a true refactor-stable identity, the only
    class on which a cross-refactor baseline match is sound).

    The never-suppress-``weak`` rule is the operational heart of INV-5's
    conditional-canonicality: a ``weak`` fingerprint is a same-source identity only,
    so matching it across a refactor would silently hide a finding whose identity
    the canonicaliser could not actually establish.
    """
    return result.fingerprint_class == "strong"


__all__ = [
    "EmptyWitness",
    "SliceFingerprintResult",
    "SliceRequest",
    "WitnessNotInCPG",
    "compute_slice_fingerprint",
    "eligible_for_baseline_suppression",
]
