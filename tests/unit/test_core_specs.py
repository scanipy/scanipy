"""CORE-family unit / conditional-theorem / invariant test specs (Phase 1, TDD).

Covers the [UNIT], [CONDITIONAL THEOREM]-as-unit and [INVARIANT] acceptance
criteria for the Analysis Core family (CMP-CORE-01/02/03):

    TST-AC-CORE-01a   determinism: byte-identical pre-serialisation hashes
    TST-AC-CORE-01c   incremental visits only AFFECTED + transitive callers
    TST-AC-CORE-03a   CFI-symmetric inputs terminate in (B, T), deterministic
    TST-AC-CORE-03c   persisted field named cpg_order_hash + annotation present
    TST-INV-5-CORE-03 cpg_order_hash annotation co-resident everywhere (INV-5)
    TST-INV-5-CORE-02 weak-classed findings never auto-suppressed (INV-5)
    TST-INV-6-CORE-01 recall claim only on gate-passing pairs (INV-6)

Production code does not exist yet. Each test is a registered-but-dormant stub:
`xfail(strict=False)` + a `pytest.skip` body. It flips red->green when the
matching CMP-CORE-* lands. Marker = execution/frequency class only (the
`--strict-markers` set is closed); the WBS kind tag lives in the docstring.
"""

import itertools
from typing import TYPE_CHECKING

import pytest

from analysis.ifds.dsl.primitives import AccessPathPattern, Sink, Source
from analysis.ifds.dsl.spec import Spec
from analysis.ifds.solver import SummaryCache, incremental_solve, solve
from analysis.ifds.supergraph import ProcId, build_supergraph
from analysis.ordering import (
    CPG,
    CPG_ORDER_HASH_ANNOTATION,
    CanonicalOrderResult,
    Duration,
    NodeId,
    Sha256,
    canonical_order,
    to_auditor_export_fields,
    to_provenance_fields,
    to_sarif_properties,
)

if TYPE_CHECKING:
    from analysis.ifds.solver import Finding

# Fixed run parameters for the CMP-CORE-01 fixture-scale tests (INV-2).
_S_VERSION = "1.0.0"
_ENV_DIGEST = Sha256(b"\xab" * 32)
_SRC_PAT = AccessPathPattern("taint_src")
_SINK_PAT = AccessPathPattern("exec_sink")

# ---------------------------------------------------------------------------
# CMP-CORE-03 test helpers (CFI-style symmetric graph builder)
# ---------------------------------------------------------------------------


def _build_cfi_symmetric_cpg() -> CPG:
    """A CFI-style (Cai-Furer-Immerman) symmetric CPG designed to defeat 2-WL.

    Two structurally-identical gadgets wired into a regular bipartite mesh so
    every node is 2-WL-indistinguishable from its mirror, with no distinguishing
    enclosing-declaration FQN or structural path. Such a graph forces
    individualisation-refinement and (under a tight budget) the weak fallback.
    """
    cpg = CPG()
    width = 6
    left = [cpg.add_node("NODE", structural_path="", enclosing_decl_fqn="") for _ in range(width)]
    right = [cpg.add_node("NODE", structural_path="", enclosing_decl_fqn="") for _ in range(width)]
    # Complete bipartite mesh with a single edge kind: maximally symmetric.
    for u in left:
        for v in right:
            cpg.add_edge(u, v, "AST")
    return cpg


def _strong_result() -> CanonicalOrderResult:
    """A representative `strong` result from an asymmetric, fully-distinguishable
    graph (2-WL resolves every node, so canonical_order returns `strong`)."""
    cpg = CPG()
    a = cpg.add_node("METHOD", resolved_fqn="pkg.A.m", enclosing_decl_fqn="pkg.A")
    b = cpg.add_node("CALL", operator_or_literal="sink", enclosing_decl_fqn="pkg.A")
    cpg.add_edge(a, b, "AST")
    result = canonical_order(cpg)
    assert result.fingerprint_class == "strong"
    return result


def _weak_result() -> CanonicalOrderResult:
    """A representative `weak` result. Constructed directly on the public
    dataclass surface (per advisor: driving canonical_order to a guaranteed weak
    path is flaky), exercising the budget-exhausted fallback shape with the
    annotation Literal that the dataclass requires."""
    return CanonicalOrderResult(
        canonical_order=[NodeId(0), NodeId(1)],
        cpg_order_hash=Sha256(b"\x00" * 32),
        fingerprint_class="weak",
        annotation=CPG_ORDER_HASH_ANNOTATION,
        budget_exhausted=True,
        elapsed_ms=12.5,
    )


# ---------------------------------------------------------------------------
# CMP-CORE-01 test helpers (fixture-scale taint CPGs + a Stage-A injection spec)
# ---------------------------------------------------------------------------


def _injection_spec() -> Spec:
    """A minimal Stage-A `ifds` injection spec: one source + one sink clause.

    The PR1 AccessPathPattern matcher fires on a node whose ``operator_or_literal``
    equals the clause pattern (CLAR-CORE-01 simplification), so the fixtures wire
    a `taint_src` node to an `exec_sink` node and the solver must report it.
    """
    return Spec(
        id="inj.fixture.v1",
        class_="injection",
        languages=("python",),
        engine="ifds",
        clauses=(Source(_SRC_PAT), Sink(_SINK_PAT)),
    )


def _single_proc_taint_cpg() -> CPG:
    """One procedure: source -> intermediate -> sink, all via CFG edges.

    Designed so the PR1 matcher fires (a real source->sink finding exists), which
    is the anti-vacuity backbone of the determinism proxy test.
    """
    cpg = CPG()
    entry = cpg.add_node("METHOD", resolved_fqn="m.main", enclosing_decl_fqn="m.main")
    src = cpg.add_node(
        "CALL", operator_or_literal="taint_src", enclosing_decl_fqn="m.main", structural_path="0"
    )
    mid = cpg.add_node(
        "IDENTIFIER", operator_or_literal="x", enclosing_decl_fqn="m.main", structural_path="1"
    )
    sink = cpg.add_node(
        "CALL", operator_or_literal="exec_sink", enclosing_decl_fqn="m.main", structural_path="2"
    )
    cpg.add_edge(entry, src, "CFG")
    cpg.add_edge(src, mid, "CFG")
    cpg.add_edge(mid, sink, "CFG")
    return cpg


def _call_chain_cpg() -> tuple[CPG, dict[str, ProcId]]:
    """An interprocedural fixture with a call chain AND an independent procedure.

    Call graph (CALL edges):  top -> mid -> leaf .   Plus an *isolated* procedure
    ``other`` that is NOT a caller of ``leaf`` but carries its OWN taint source.

    This shape is what makes the AC-CORE-01c negative control non-vacuous (per
    the falsifier doctrine): if ``leaf`` is AFFECTED, the closure is
    {leaf, mid, top}; ``other`` is OUTSIDE it. Because ``other`` is independently
    seeded, a FULL solve DOES visit it — so "incremental did not visit other" is a
    real restriction, not a trivially-unreachable node.

    Returns the CPG and a name->ProcId map (proc id == the METHOD entry node id).
    """
    cpg = CPG()

    # leaf procedure: contains the source->sink taint path.
    leaf_entry = cpg.add_node("METHOD", resolved_fqn="p.leaf", enclosing_decl_fqn="p.leaf")
    leaf_src = cpg.add_node(
        "CALL", operator_or_literal="taint_src", enclosing_decl_fqn="p.leaf", structural_path="0"
    )
    leaf_sink = cpg.add_node(
        "CALL", operator_or_literal="exec_sink", enclosing_decl_fqn="p.leaf", structural_path="1"
    )
    cpg.add_edge(leaf_entry, leaf_src, "CFG")
    cpg.add_edge(leaf_src, leaf_sink, "CFG")

    # mid procedure: calls leaf.
    mid_entry = cpg.add_node("METHOD", resolved_fqn="p.mid", enclosing_decl_fqn="p.mid")
    mid_call = cpg.add_node(
        "CALL", operator_or_literal="call_leaf", enclosing_decl_fqn="p.mid", structural_path="0"
    )
    cpg.add_edge(mid_entry, mid_call, "CFG")
    cpg.add_edge(mid_call, leaf_entry, "CALL")

    # top procedure: calls mid.
    top_entry = cpg.add_node("METHOD", resolved_fqn="p.top", enclosing_decl_fqn="p.top")
    top_call = cpg.add_node(
        "CALL", operator_or_literal="call_mid", enclosing_decl_fqn="p.top", structural_path="0"
    )
    cpg.add_edge(top_entry, top_call, "CFG")
    cpg.add_edge(top_call, mid_entry, "CALL")

    # other procedure: independent, NOT a caller of leaf, but carries its own
    # taint source (so a full solve visits it — non-vacuity for the neg control).
    other_entry = cpg.add_node("METHOD", resolved_fqn="p.other", enclosing_decl_fqn="p.other")
    other_src = cpg.add_node(
        "CALL", operator_or_literal="taint_src", enclosing_decl_fqn="p.other", structural_path="0"
    )
    cpg.add_edge(other_entry, other_src, "CFG")

    procs = {
        "leaf": ProcId(int(leaf_entry)),
        "mid": ProcId(int(mid_entry)),
        "top": ProcId(int(top_entry)),
        "other": ProcId(int(other_entry)),
    }
    return cpg, procs


def _interproc_taint_cpg() -> tuple[CPG, dict[str, NodeId]]:
    """Two procedures: source in the CALLER, taint flows into the CALLEE, sink
    INSIDE the callee (PR3 Deliverable 1).

    Caller ``c.caller``:  entry -> taint_src -> call_callee --CALL--> callee.entry
    Callee ``c.callee``:  entry -> y -> exec_sink

    The realising witness must cross the call boundary: it starts at the caller's
    ``taint_src``, walks the caller CFG to the call site, follows the CALL edge to
    the callee entry, then walks the callee CFG to ``exec_sink``. This is the only
    fixture shape that yields a NON-VACUOUS interprocedural witness in the PR1-PR3
    solver: return-flow (sink in the caller AFTER the call) is inert because the
    structural supergraph builds no RETURN adjacency and the summary splice never
    fires in a full solve (it reads ``summaries.summaries`` which is empty until
    the post-loop write). See the Deliverable-1 docstring + CLAR-CORE-01 note.

    Returns the CPG and a name->NodeId map for the load-bearing nodes.
    """
    cpg = CPG()
    caller_entry = cpg.add_node("METHOD", resolved_fqn="c.caller", enclosing_decl_fqn="c.caller")
    src = cpg.add_node(
        "CALL", operator_or_literal="taint_src", enclosing_decl_fqn="c.caller", structural_path="0"
    )
    call_site = cpg.add_node(
        "CALL",
        operator_or_literal="call_callee",
        enclosing_decl_fqn="c.caller",
        structural_path="1",
    )
    cpg.add_edge(caller_entry, src, "CFG")
    cpg.add_edge(src, call_site, "CFG")

    callee_entry = cpg.add_node("METHOD", resolved_fqn="c.callee", enclosing_decl_fqn="c.callee")
    callee_mid = cpg.add_node(
        "IDENTIFIER", operator_or_literal="y", enclosing_decl_fqn="c.callee", structural_path="0"
    )
    callee_sink = cpg.add_node(
        "CALL", operator_or_literal="exec_sink", enclosing_decl_fqn="c.callee", structural_path="1"
    )
    cpg.add_edge(call_site, callee_entry, "CALL")
    cpg.add_edge(callee_entry, callee_mid, "CFG")
    cpg.add_edge(callee_mid, callee_sink, "CFG")

    nodes = {
        "caller_entry": caller_entry,
        "src": src,
        "call_site": call_site,
        "callee_entry": callee_entry,
        "callee_mid": callee_mid,
        "callee_sink": callee_sink,
    }
    return cpg, nodes


def _two_finding_cpg() -> tuple[CPG, dict[str, ProcId]]:
    """A call chain WITH a finding AND an independent out-of-closure proc that
    ALSO carries a complete source -> sink finding (PR3 Deliverable 2).

    Differs from :func:`_call_chain_cpg` in one load-bearing way: the independent
    ``other`` procedure here has its OWN ``taint_src -> exec_sink`` CFG path, so a
    FULL solve emits TWO findings (one in ``leaf``, one in ``other``). When
    AFFECTED = {leaf}, the closure is {leaf, mid, top} and ``other`` is OUTSIDE it.
    A naive incremental_solve (no prior-findings merge) re-tabulates only the
    closure and emits ONLY the ``leaf`` finding — DROPPING the ``other`` finding.
    That dropped finding is exactly the out-of-closure-WITH-finding case PR1/PR2
    could not preserve and PR3 fixes.

    Returns the CPG and a name->ProcId map (proc id == the METHOD entry node id).
    """
    cpg = CPG()

    # leaf procedure: source -> sink (in the AFFECTED closure when affected={leaf}).
    leaf_entry = cpg.add_node("METHOD", resolved_fqn="p.leaf", enclosing_decl_fqn="p.leaf")
    leaf_src = cpg.add_node(
        "CALL", operator_or_literal="taint_src", enclosing_decl_fqn="p.leaf", structural_path="0"
    )
    leaf_sink = cpg.add_node(
        "CALL", operator_or_literal="exec_sink", enclosing_decl_fqn="p.leaf", structural_path="1"
    )
    cpg.add_edge(leaf_entry, leaf_src, "CFG")
    cpg.add_edge(leaf_src, leaf_sink, "CFG")

    # mid procedure: calls leaf.
    mid_entry = cpg.add_node("METHOD", resolved_fqn="p.mid", enclosing_decl_fqn="p.mid")
    mid_call = cpg.add_node(
        "CALL", operator_or_literal="call_leaf", enclosing_decl_fqn="p.mid", structural_path="0"
    )
    cpg.add_edge(mid_entry, mid_call, "CFG")
    cpg.add_edge(mid_call, leaf_entry, "CALL")

    # top procedure: calls mid.
    top_entry = cpg.add_node("METHOD", resolved_fqn="p.top", enclosing_decl_fqn="p.top")
    top_call = cpg.add_node(
        "CALL", operator_or_literal="call_mid", enclosing_decl_fqn="p.top", structural_path="0"
    )
    cpg.add_edge(top_entry, top_call, "CFG")
    cpg.add_edge(top_call, mid_entry, "CALL")

    # other procedure: independent, OUT of the {leaf} closure, with its OWN
    # complete source -> sink finding (this is the finding PR3 must preserve).
    other_entry = cpg.add_node("METHOD", resolved_fqn="p.other", enclosing_decl_fqn="p.other")
    other_src = cpg.add_node(
        "CALL", operator_or_literal="taint_src", enclosing_decl_fqn="p.other", structural_path="0"
    )
    other_sink = cpg.add_node(
        "CALL", operator_or_literal="exec_sink", enclosing_decl_fqn="p.other", structural_path="1"
    )
    cpg.add_edge(other_entry, other_src, "CFG")
    cpg.add_edge(other_src, other_sink, "CFG")

    procs = {
        "leaf": ProcId(int(leaf_entry)),
        "mid": ProcId(int(mid_entry)),
        "top": ProcId(int(top_entry)),
        "other": ProcId(int(other_entry)),
    }
    return cpg, procs


# ---------------------------------------------------------------------------
# CMP-CORE-02 fingerprint fixtures (a real Finding + its CPG, via the solver)
# ---------------------------------------------------------------------------


def _fingerprint_fixture() -> tuple[CPG, "Finding"]:
    """An asymmetric two-proc taint CPG + the real Finding the solver emits over
    it. 2-WL distinguishes every node, so the slice canonicalises STRONG.

    Built through the shipped CMP-CORE-01 solver (typed interface, not a fake
    witness) so ``finding.witness`` is the genuine connected source -> sink path
    CMP-CORE-02 backward-slices along.
    """
    from analysis.ifds.solver import Finding, solve

    cpg, _nodes = _interproc_taint_cpg()
    result = solve(cpg, _injection_spec(), S_version=_S_VERSION, env_digest=_ENV_DIGEST)
    assert len(result.findings) == 1, "fingerprint fixture must yield exactly one finding"
    finding: Finding = next(iter(result.findings))
    return cpg, finding


def _symmetric_fingerprint_fixture() -> tuple[CPG, "Finding"]:
    """A CPG whose backward-cone slice is 2-WL-symmetric, so a tight budget (B=1)
    forces the WEAK witness-edge-sequence fallback through the REAL code path.

    A diamond of two IDENTICAL ``relay`` CALL nodes: ``src -> {a, b} -> sink``.
    ``a``/``b`` share every label and survive alpha-renaming (only IDENTIFIER nodes are
    renamed). The backward cone from the sink keeps BOTH arms (the realising
    witness took only one), so the normalised slice carries the residual symmetric
    class ``{a, b}`` — individualisation-refinement must resolve it, and B=1 forces
    BudgetExhausted -> ``weak``. The full budget resolves it ``strong`` (the
    weakness is genuinely budget-driven). The Finding is produced by the real
    solver so its witness is genuine.
    """
    from analysis.ifds.solver import Finding, solve

    cpg = CPG()
    entry = cpg.add_node("METHOD", resolved_fqn="s.main", enclosing_decl_fqn="s.main")
    src = cpg.add_node("CALL", operator_or_literal="taint_src", enclosing_decl_fqn="s.main")
    a = cpg.add_node("CALL", operator_or_literal="relay", enclosing_decl_fqn="s.main")
    b = cpg.add_node("CALL", operator_or_literal="relay", enclosing_decl_fqn="s.main")
    sink = cpg.add_node("CALL", operator_or_literal="exec_sink", enclosing_decl_fqn="s.main")
    cpg.add_edge(entry, src, "CFG")
    cpg.add_edge(src, a, "CFG")
    cpg.add_edge(src, b, "CFG")
    cpg.add_edge(a, sink, "CFG")
    cpg.add_edge(b, sink, "CFG")

    result = solve(cpg, _injection_spec(), S_version=_S_VERSION, env_digest=_ENV_DIGEST)
    assert len(result.findings) == 1, "symmetric fixture must yield exactly one finding"
    finding: Finding = next(iter(result.findings))
    return cpg, finding


# ---------------------------------------------------------------------------
# CMP-CORE-01 — IFDS/IDE tabulation solver (Algorithm 2)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_core_01_determinism_proxy_byte_identical_solution_hash() -> None:
    """PROXY for AC-CORE-01a: fixture-scale byte-identical solution hash.

    Test id:       (CMP-CORE-01 PR1 determinism proxy — NOT TST-AC-CORE-01a)
    Maps to AC:    proxy for AC-CORE-01a (the corpus-scale release blocker stays
                   xfail until CMP-CORP-CANARY-01 + CMP-CP-05 land).
    Kind tag:      [UNIT]
    Inputs:        a single fixture taint CPG + a Stage-A injection spec, fixed
                   (S_version, env_digest).
    Outputs:       SolverResult.solution_hash from two independent solve() calls.
    Pass criteria: (i) ANTI-VACUITY — the solver reports a non-empty finding set
                   on the fixture (byte-identity is meaningless on an empty
                   solver); (ii) the two solution_hashes are byte-identical.
    Frequency:     every CI run.
    Hard gate?:    proxy only — the hard AC-CORE-01a gate is the xfail above.
    """
    cpg = _single_proc_taint_cpg()
    spec = _injection_spec()

    r1 = solve(cpg, spec, S_version=_S_VERSION, env_digest=_ENV_DIGEST)
    r2 = solve(cpg, spec, S_version=_S_VERSION, env_digest=_ENV_DIGEST)

    # (i) ANTI-VACUITY: the adapter actually fired source->sink on the fixture.
    #     Without this, byte-identity is vacuously true on an empty solver and a
    #     do-nothing impl would pass. This is the falsifier-doctrine positive
    #     control for the determinism proxy.
    assert r1.findings, "expected at least one source->sink finding on the fixture"
    only = next(iter(r1.findings))
    # The single finding lands at the exec_sink node and threads provenance.
    assert only.origin == "deterministic-core"  # INV-1
    assert only.S_version == _S_VERSION and only.env_digest == _ENV_DIGEST  # INV-2
    assert only.cpg_order_hash_annotation == CPG_ORDER_HASH_ANNOTATION  # INV-5
    assert only.fingerprint_class in ("strong", "weak")

    # (ii) byte-identical pre-serialisation solution hash across re-runs.
    assert isinstance(r1.solution_hash, bytes) and len(r1.solution_hash) == 32
    assert r1.solution_hash == r2.solution_hash


@pytest.mark.unit
def test_core_01_inv2_fail_fast_on_unpinned_params() -> None:
    """INV-2: solve() refuses to run with an empty S_version or env_digest.

    Negative control for the INV-2 fail-fast contract (DOC-CMP-CORE-01 §5.2,
    §7): a silent default would be an invariant violation. A do-nothing guard
    (returning a result anyway) fails this test.
    """
    cpg = _single_proc_taint_cpg()
    spec = _injection_spec()
    with pytest.raises(ValueError):
        solve(cpg, spec, S_version="", env_digest=_ENV_DIGEST)
    with pytest.raises(ValueError):
        solve(cpg, spec, S_version=_S_VERSION, env_digest=Sha256(b""))


@pytest.mark.unit
def test_core_01_witness_is_connected_source_to_sink_path() -> None:
    """PR2: the witness is a real source -> sink path, not the ``(sink,)`` stub.

    Test id:       (CMP-CORE-01 PR2 witness reconstruction — feeds CMP-CORE-02)
    Maps to AC:    PREP for AC-CORE-01a/01b (witness is the input CMP-CORE-02
                   backward-slices along, DOC-CMP-CORE-01 §3.3, DOC-CMP-CORE-02
                   §4.1); not itself a release-blocker AC.
    Kind tag:      [UNIT]
    Inputs:        the single-proc taint fixture (source -> mid -> sink via CFG).
    Outputs:       the realising ``Finding.witness`` tuple.
    Pass criteria: (i) ANTI-VACUITY — exactly one finding at the exec_sink node;
                   (ii) the witness is a CONNECTED path with len > 1 — the
                   placeholder ``(sink,)`` was len 1; (iii) the FIRST node is the
                   seeded source (``operator_or_literal == "taint_src"``), checked
                   against the CPG itself (NOT the solver's own pred map, which
                   would be tautological); (iv) the LAST node is the sink; (v)
                   every consecutive pair in the witness is a real CFG/CALL edge in
                   the supergraph (it is a path, not an arbitrary node set).
    Frequency:     every CI run.
    Hard gate?:    no — PREP that unblocks CMP-CORE-02 witness consumption.
    """
    cpg = _single_proc_taint_cpg()
    spec = _injection_spec()

    result = solve(cpg, spec, S_version=_S_VERSION, env_digest=_ENV_DIGEST)

    # (i) ANTI-VACUITY: the adapter fired exactly one source->sink finding.
    assert len(result.findings) == 1, "expected exactly one source->sink finding"
    finding = next(iter(result.findings))
    witness = finding.witness

    # The set of source node ids, recomputed from the CPG (independent of the
    # solver internals — guards against a tautological "witness[0] is whatever the
    # solver seeded" assertion).
    source_node_ids = {n.node_id for n in cpg.nodes if n.operator_or_literal == str(_SRC_PAT)}
    sink_node_ids = {n.node_id for n in cpg.nodes if n.operator_or_literal == str(_SINK_PAT)}
    assert source_node_ids, "fixture must contain a taint_src node"
    assert finding.sink in sink_node_ids

    # (ii) CONNECTED + non-trivial: the placeholder was the 1-tuple ``(sink,)``.
    assert len(witness) > 1, "witness must be a real path, not the (sink,) placeholder"

    # (iii) first node is a SEEDED SOURCE; (iv) last node is the sink.
    assert witness[0] in source_node_ids, "witness must start at a taint source"
    assert witness[-1] == finding.sink, "witness must end at the sink"

    # (v) every consecutive (a, b) is a real CFG or CALL edge in the supergraph:
    #     the witness is a path through the graph, not an arbitrary node bag. This
    #     is exactly the property CMP-CORE-02 relies on to backward-slice along it.
    sg = build_supergraph(cpg, canonical_order(cpg).canonical_order)

    def _is_edge(a: NodeId, b: NodeId) -> bool:
        if b in sg.cfg_succ.get(a, []):
            return True
        # CALL edge: a is a call site whose callee's ENTRY is b.
        return any(sg.procs[p].entry == b for p in sg.call_succ.get(a, []))

    for a, b in itertools.pairwise(witness):
        assert _is_edge(a, b), f"witness edge {a}->{b} is not a CFG/CALL edge"


@pytest.mark.unit
def test_core_01_witness_byte_identical_across_runs() -> None:
    """PR2: the reconstructed witness is byte-identical across two solve() calls.

    Test id:       (CMP-CORE-01 PR2 witness determinism)
    Maps to AC:    proxy/PREP for AC-CORE-01a (the witness is folded into
                   ``solution_hash`` at solver.py ``_hash_solution``, so its
                   determinism is load-bearing for byte-identical SARIF).
    Kind tag:      [UNIT]
    Inputs:        the single-proc taint fixture, fixed (S_version, env_digest).
    Outputs:       ``Finding.witness`` from two independent solve() calls.
    Pass criteria: the two witnesses are byte-identical tuples. ANTI-VACUITY is
                   shared with the path test: ``len(witness) > 1`` (a degenerate
                   empty/singleton witness would make byte-identity vacuous).
    Honest framing: this is a REGRESSION GUARD against a future set-/hash-ordering
                   nondeterminism in pred reconstruction. In this deterministic
                   codebase a realistic broken impl still passes byte-identity
                   within one process, so a fabricated nondeterminism mutation is
                   not a meaningful negative control here (see the docstring of
                   ``test_core_01_witness_is_connected_source_to_sink_path`` for
                   the real, mutation-verified negative control: the ``(sink,)``
                   placeholder).
    Frequency:     every CI run.
    Hard gate?:    no — PREP.
    """
    cpg = _single_proc_taint_cpg()
    spec = _injection_spec()

    r1 = solve(cpg, spec, S_version=_S_VERSION, env_digest=_ENV_DIGEST)
    r2 = solve(cpg, spec, S_version=_S_VERSION, env_digest=_ENV_DIGEST)

    w1 = next(iter(r1.findings)).witness
    w2 = next(iter(r2.findings)).witness

    # ANTI-VACUITY: a real multi-node path (byte-identity is meaningless on a stub).
    assert len(w1) > 1
    assert w1 == w2, "witness must be byte-identical across re-runs"


@pytest.mark.unit
def test_core_01_summarycache_round_trips_into_incremental_solve() -> None:
    """PR2 (DELIVERABLE 2): solve().summaries round-trips into incremental_solve().

    Test id:       (CMP-CORE-01 PR2 SummaryCache exposure — CLAR-CORE-01)
    Maps to AC:    PREP for AC-CORE-01c (cross-run incremental reuse; CLAR-CORE-01
                   records the previously-dropped ``SolverResult.summaries`` field).
    Kind tag:      [UNIT]
    Inputs:        a base solve() over the call-chain fixture; its
                   ``.summaries`` fed back as ``prior_summaries``.
    Outputs:       the SummaryCache header + a non-raising incremental_solve().
    Pass criteria: (i) ``solve().summaries`` carries the (S_version, env_digest)
                   header; (ii) it round-trips as ``prior_summaries`` into
                   incremental_solve() WITHOUT raising the version-mismatch guard.
                   NEGATIVE CONTROL: a cache whose header is TAMPERED (wrong
                   S_version) DOES raise ValueError — proving the round-trip
                   success is not vacuous (the guard is real, and the matching
                   header is what clears it).
    Frequency:     every CI run.
    Hard gate?:    no — PREP.
    """
    cpg, procs = _call_chain_cpg()
    spec = _injection_spec()

    base = solve(cpg, spec, S_version=_S_VERSION, env_digest=_ENV_DIGEST)

    # (i) the cache is exposed and carries the (S_version, env_digest) header.
    cache = base.summaries
    assert cache.header == (_S_VERSION, bytes(_ENV_DIGEST))
    # ANTI-VACUITY: the base run actually built summaries (it is not an empty cache
    # that would trivially round-trip).
    assert cache.summaries, "base solve must populate at least one procedure summary"

    # (ii) round-trips as prior_summaries WITHOUT raising the version guard.
    affected = frozenset({procs["leaf"]})
    incr = incremental_solve(
        cpg, spec, affected, cache, S_version=_S_VERSION, env_digest=_ENV_DIGEST
    )
    assert incr.summaries.header == (_S_VERSION, bytes(_ENV_DIGEST))

    # NEGATIVE CONTROL: a TAMPERED header (wrong S_version) must raise — this is
    # what proves the clean round-trip above is non-vacuous.
    from analysis.ifds.solver import SummaryCache

    tampered = SummaryCache(
        header=("9.9.9-wrong", bytes(_ENV_DIGEST)),
        summaries=dict(cache.summaries),
        visited=set(cache.visited),
    )
    with pytest.raises(ValueError, match="SummaryCacheVersionMismatch"):
        incremental_solve(
            cpg, spec, affected, tampered, S_version=_S_VERSION, env_digest=_ENV_DIGEST
        )


@pytest.mark.unit
@pytest.mark.xfail(reason="CMP-CORE-01 not yet implemented", strict=False)
def test_core_01a_determinism_byte_identical_solution_hash() -> None:
    """Determinism: re-runs yield byte-identical pre-serialisation hashes.

    Test id:       TST-AC-CORE-01a
    Maps to AC:    AC-CORE-01a
    Kind tag:      [CONDITIONAL THEOREM] (run here as a unit-level oracle;
                   the corpus-scale form feeds Gate 3 via the Attestor)
    Inputs:        100 canary repos (CMP-CORP-CANARY-01) x 5 re-runs under a
                   fixed (S_version, env_digest), LLM_TRIAGE=off.
    Outputs:       SolverResult.solution_hash (sha256) per run.
    Pass criteria: all 5 hashes per repo are byte-identical for every repo;
                   a single mismatch falsifies the DSL-closure precondition or
                   reveals a DSL escape. NEVER weaken to a tolerance.
    Frequency:     every CI run (and Gate 3 / pre-release via Attestor).
    Hard gate?:    yes — release blocker (Gate 3, CMP-CP-05 Attestor).
    """
    # TODO: load CMP-CORP-CANARY-01, run analysis.ifds.solver.solve 5x per repo
    #       under fixed (S_version, env_digest); assert all solution_hash equal.
    pytest.skip("CMP-CORE-01 not implemented yet")


@pytest.mark.unit
def test_core_01c_incremental_visits_only_affected_closure() -> None:
    """Incremental re-tabulation visits only AFFECTED + transitive callers.

    Test id:       TST-AC-CORE-01c
    Maps to AC:    AC-CORE-01c
    Kind tag:      [UNIT]
    Inputs:        a base SolverResult + a seeded AFFECTED set (CMP-SNAP-02
                   Algorithm 1) and the prior SummaryCache.
    Outputs:       SolverResult.visited_procs from incremental_solve.
    Pass criteria: visited_procs is a subset of
                   closure_callers(affected_set) = affected_set union
                   supergraph.transitive_callers(affected_set); no procedure
                   outside that closure is re-tabulated.
    Frequency:     every CI run.
    Hard gate?:    yes.
    """
    cpg, procs = _call_chain_cpg()
    spec = _injection_spec()

    # Base full run tells us which procedures a FULL solve visits — the
    # non-vacuity baseline for the negative control below.
    base = solve(cpg, spec, S_version=_S_VERSION, env_digest=_ENV_DIGEST)

    # A header-matching prior cache (keyed on the same (S_version, env_digest)).
    from analysis.ifds.solver import SummaryCache

    prior = SummaryCache(
        header=(_S_VERSION, bytes(_ENV_DIGEST)),
        summaries={},
        visited=set(),
    )

    # AFFECTED = {leaf}. The LITERAL closure for this fixture is {leaf, mid, top}
    # (mid calls leaf; top calls mid). ``other`` is OUTSIDE the closure.
    affected = frozenset({procs["leaf"]})
    expected_closure = frozenset({procs["leaf"], procs["mid"], procs["top"]})

    # Cross-check the supergraph's own closure matches the hand-computed literal
    # (guards against a tautological subset assertion that just echoes the impl).
    sg = build_supergraph(cpg, canonical_order(cpg).canonical_order)
    assert affected | sg.transitive_callers(affected) == expected_closure
    assert procs["other"] not in expected_closure

    incr = incremental_solve(
        cpg, spec, affected, prior, S_version=_S_VERSION, env_digest=_ENV_DIGEST
    )

    # NON-VACUITY: a FULL solve DOES visit ``other`` (it is independently seeded),
    # so excluding it is a real restriction, not a trivially-unreachable node.
    assert procs["other"] in base.visited_procs

    # AC-CORE-01c (positive): every visited proc lies in the AFFECTED closure.
    assert incr.visited_procs <= expected_closure
    # AC-CORE-01c (the work happened): the affected proc itself was re-tabulated.
    assert procs["leaf"] in incr.visited_procs
    # NEGATIVE CONTROL: the out-of-closure proc is NOT re-tabulated. A
    # visit-everything impl (ignoring affected_set) would fail right here.
    assert procs["other"] not in incr.visited_procs


@pytest.mark.unit
def test_core_01_interproc_witness_connected_across_call_boundary() -> None:
    """PR3 (DELIVERABLE 1): the witness is a CONNECTED path across a call boundary.

    Test id:       (CMP-CORE-01 PR3 interprocedural witness verification)
    Maps to AC:    PREP for AC-CORE-01a/01b (the interprocedural witness is the
                   input CMP-CORE-02 backward-slices along, DOC-CMP-CORE-01 §3.3).
    Kind tag:      [UNIT]
    Inputs:        the two-procedure fixture — source in the CALLER, taint flows
                   through a CALL edge into the CALLEE, sink INSIDE the callee.
    Outputs:       the realising ``Finding.witness`` tuple.
    Pass criteria: (i) ANTI-VACUITY — exactly one finding at the callee's
                   exec_sink; (ii) the witness STARTS at the caller's seeded
                   ``taint_src`` and ENDS at the callee sink, so it genuinely
                   spans two procedures; (iii) every consecutive pair is a real
                   CFG or CALL edge in the supergraph — i.e. the path is
                   CONNECTED across the call boundary, NOT a disconnected node
                   bag; (iv) EXACTLY ONE consecutive pair is a CALL edge (the
                   boundary crossing), and it goes from a CALLER node to the
                   CALLEE entry; (v) CALLEE-INTERNAL nodes appear in the witness
                   (no elision on this path) — the callee entry and the callee's
                   internal CFG node both lie on the realising path.

    Empirical shape (DOC-CMP-CORE-01 §3.3, "summary-level witnesses"): on this
    fixture the witness is the FULL connected node sequence
    ``src -> call_site -> callee_entry -> callee_mid -> callee_sink`` with the
    boundary pred written at solver.py ``add(callee.entry, fact, (call_node,
    fact))`` (the CALL-edge propagation), NOT the summary splice. There is NO
    callee-internal elision here: the boundary pred records the CALL node as the
    predecessor of the callee entry, and the callee's own intraprocedural CFG
    walk supplies every node between the entry and the sink. The latent
    summary-splice elision DOC §3.3 sanctions (the splice records the call node
    as the return-site predecessor) would only surface for a sink reached via
    RETURN-flow back into the caller — a path that is INERT in the PR1-PR3 solver
    (the structural supergraph builds no RETURN adjacency, and the splice reads
    an empty summary table during a full solve). See clar_filed for the
    CLAR-CORE-01 amendment recording this precisely.

    Frequency:     every CI run.
    Hard gate?:    no — PREP that unblocks CMP-CORE-02 interprocedural witness
                   consumption + removes a recorded CORE-02-start blocker.
    """
    cpg, nodes = _interproc_taint_cpg()
    spec = _injection_spec()

    result = solve(cpg, spec, S_version=_S_VERSION, env_digest=_ENV_DIGEST)

    # (i) ANTI-VACUITY: exactly one source->sink finding, at the callee sink.
    assert len(result.findings) == 1, "expected exactly one interprocedural finding"
    finding = next(iter(result.findings))
    assert finding.sink == nodes["callee_sink"], "the sink must be the callee's exec_sink"
    witness = finding.witness

    # Recompute source/sink node ids from the CPG itself (independent of the
    # solver internals — not a tautology against the solver's own pred map).
    source_node_ids = {n.node_id for n in cpg.nodes if n.operator_or_literal == str(_SRC_PAT)}
    assert nodes["src"] in source_node_ids

    # (ii) the witness spans two procedures: caller source -> callee sink.
    assert len(witness) > 1, "witness must be a real path, not the (sink,) placeholder"
    assert witness[0] == nodes["src"], "witness must start at the caller's taint source"
    assert witness[-1] == nodes["callee_sink"], "witness must end at the callee sink"

    sg = build_supergraph(cpg, canonical_order(cpg).canonical_order)

    def _is_cfg_edge(a: NodeId, b: NodeId) -> bool:
        return b in sg.cfg_succ.get(a, [])

    def _is_call_edge(a: NodeId, b: NodeId) -> bool:
        # CALL edge: a is a call site whose callee's ENTRY is b.
        return any(sg.procs[p].entry == b for p in sg.call_succ.get(a, []))

    # (iii) CONNECTED across the boundary: every consecutive pair is a real edge.
    call_edges = []
    for a, b in itertools.pairwise(witness):
        assert _is_cfg_edge(a, b) or _is_call_edge(a, b), (
            f"witness edge {a}->{b} is neither a CFG nor a CALL edge — disconnected"
        )
        if _is_call_edge(a, b):
            call_edges.append((a, b))

    # (iv) EXACTLY ONE boundary crossing, from a caller node to the callee entry.
    assert len(call_edges) == 1, "the witness must cross the call boundary exactly once"
    (cross_from, cross_to) = call_edges[0]
    assert sg.proc_of_node.get(cross_from) == ProcId(int(nodes["caller_entry"])), (
        "the CALL edge must originate in the caller procedure"
    )
    assert cross_to == nodes["callee_entry"], "the CALL edge must land on the callee entry"

    # (v) CALLEE-INTERNAL nodes appear (no elision on this path): the callee entry
    # AND its internal CFG node both lie on the realising witness.
    assert nodes["callee_entry"] in witness, "callee entry must appear in the witness"
    assert nodes["callee_mid"] in witness, "callee-internal CFG node must appear (no elision)"
    # The portion of the witness inside the callee is a contiguous tail.
    callee_pid = ProcId(int(nodes["callee_entry"]))
    callee_nodes_on_path = [n for n in witness if sg.proc_of_node.get(n) == callee_pid]
    assert callee_nodes_on_path == [
        nodes["callee_entry"],
        nodes["callee_mid"],
        nodes["callee_sink"],
    ], "the callee-internal witness segment must be the full entry->mid->sink path"


@pytest.mark.unit
def test_core_01_incremental_preserves_out_of_closure_finding() -> None:
    """PR3 (DELIVERABLE 2): incremental_solve preserves an out-of-closure finding.

    Test id:       (CMP-CORE-01 PR3 incremental == full equality, out-of-closure)
    Maps to AC:    AC-CORE-01c completeness side (the readout must not DROP a
                   finding in an unchanged, out-of-closure procedure relative to a
                   full solve — DOC-ALGS §2 Algorithm-1 handoff, property (b)).
    Kind tag:      [UNIT]
    Inputs:        a fixture with an AFFECTED call chain ({leaf, mid, top}) AND an
                   independent out-of-closure procedure ``other`` that carries its
                   OWN complete source->sink finding; a prior full SolverResult fed
                   back as ``prior_summaries`` + ``prior_findings``.
    Outputs:       incremental_solve().findings and .solution_hash.
    Pass criteria: (i) ANTI-VACUITY — a FULL solve emits TWO findings, one in the
                   closure (``leaf``) and one OUTSIDE it (``other``); the
                   out-of-closure finding is real, not vacuously absent;
                   (ii) the incremental result, given the prior findings, is EQUAL
                   to the full result on BOTH the finding set AND the
                   pre-serialisation ``solution_hash`` — i.e. the out-of-closure
                   finding is PRESERVED, not dropped; (iii) AC-CORE-01c still
                   holds — ``other`` is NOT re-tabulated (its finding is reused,
                   not recomputed).

    THIS IS THE NEGATIVE CONTROL PR1/PR2 DELIBERATELY COULD NOT PASS. Reverting
    the prior-findings merge in incremental_solve drops the ``other`` finding and
    fails the equality assertion (mutation-verified).

    Frequency:     every CI run.
    Hard gate?:    yes — completeness of the incremental readout.
    """
    cpg, procs = _two_finding_cpg()
    spec = _injection_spec()

    full = solve(cpg, spec, S_version=_S_VERSION, env_digest=_ENV_DIGEST)

    # (i) ANTI-VACUITY: the full solve finds TWO sinks — one in leaf (in closure),
    # one in other (OUT of the {leaf} closure). Both are real source->sink paths.
    sg = build_supergraph(cpg, canonical_order(cpg).canonical_order)
    sink_procs = {sg.proc_of_node.get(f.sink) for f in full.findings}
    assert len(full.findings) == 2, "full solve must emit two findings (leaf + other)"
    assert procs["leaf"] in sink_procs
    assert procs["other"] in sink_procs

    # AFFECTED = {leaf}; closure = {leaf, mid, top}; ``other`` is OUTSIDE it.
    affected = frozenset({procs["leaf"]})
    expected_closure = frozenset({procs["leaf"], procs["mid"], procs["top"]})
    assert affected | sg.transitive_callers(affected) == expected_closure
    assert procs["other"] not in expected_closure

    # (ii) incremental_solve, given the prior summaries + prior findings, is EQUAL
    # to the full solve on the finding set AND the byte-level solution_hash. The
    # out-of-closure ``other`` finding is preserved via the prior-findings merge.
    incr = incremental_solve(
        cpg,
        spec,
        affected,
        full.summaries,
        S_version=_S_VERSION,
        env_digest=_ENV_DIGEST,
        prior_findings=full.findings,
    )
    assert incr.findings == full.findings, (
        "incremental readout must preserve the out-of-closure finding (== full)"
    )
    assert incr.solution_hash == full.solution_hash, (
        "merged solution_hash must be byte-identical to the full-solve hash"
    )

    # (iii) AC-CORE-01c still holds: ``other`` was NOT re-tabulated — its finding
    # was REUSED from prior_findings, not recomputed. (A merge that secretly
    # re-tabulated everything would defeat property (b).)
    assert incr.visited_procs <= expected_closure
    assert procs["other"] not in incr.visited_procs
    assert procs["leaf"] in incr.visited_procs


@pytest.mark.unit
@pytest.mark.invariant
def test_core_01_incremental_rejects_version_mismatched_prior_findings() -> None:
    """INV-2 guard (PR #287 review finding): prior findings from a DIFFERENT
    pinned (S_version, env_digest) must be REJECTED, never silently merged.

    A preserved finding is re-emitted into this run's result; merging one
    produced under a different S or Env would thread stale provenance. Both
    mismatch axes are exercised; the matching case is the existing preservation
    test (anti-vacuity lives there).
    """
    cpg, procs = _two_finding_cpg()
    spec = _injection_spec()
    full = solve(cpg, spec, S_version=_S_VERSION, env_digest=_ENV_DIGEST)
    affected = frozenset({procs["leaf"]})

    # Key fresh (empty) summaries to the RUN's bumped params so the
    # pre-existing SummaryCacheVersionMismatch guard does NOT fire first —
    # isolating the prior_FINDINGS guard under test.
    bumped_s = _S_VERSION + "-bumped"
    with pytest.raises(ValueError, match="INV-2"):
        incremental_solve(
            cpg,
            spec,
            affected,
            SummaryCache(header=(bumped_s, bytes(_ENV_DIGEST)), summaries={}, visited=set()),
            S_version=bumped_s,  # S mismatch vs the prior findings
            env_digest=_ENV_DIGEST,
            prior_findings=full.findings,
        )

    other_env = Sha256(bytes([1]) * 32)
    with pytest.raises(ValueError, match="INV-2"):
        incremental_solve(
            cpg,
            spec,
            affected,
            SummaryCache(header=(_S_VERSION, bytes(other_env)), summaries={}, visited=set()),
            S_version=_S_VERSION,
            env_digest=other_env,  # Env mismatch vs the prior findings
            prior_findings=full.findings,
        )


# ---------------------------------------------------------------------------
# CMP-CORE-03 — Canonical CPG ordering (Algorithm 5)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_core_03a_cfi_symmetric_terminates_in_budget_deterministic() -> None:
    """CFI-symmetric inputs terminate in (B, T) with deterministic order.

    Test id:       TST-AC-CORE-03a
    Maps to AC:    AC-CORE-03a
    Kind tag:      [UNIT]
    Inputs:        CFI-style symmetric CPGs (designed to defeat 2-WL); B = 2**16
                   search-tree nodes, T = 0.200 s wall-clock (CLAR-PARAM-01
                   RESOLVED).
    Outputs:       CanonicalOrderResult.canonical_order + elapsed_ms across runs.
    Pass criteria: (i) terminates within (B=2**16, T=0.200s) — no unbounded
                   loop; (ii) re-running on the same source yields a
                   byte-identical canonical_order (deterministic same-source
                   order even when a true canonical form is not found in budget).
    Frequency:     every CI run.
    Hard gate?:    yes.
    """
    cpg = _build_cfi_symmetric_cpg()
    r1 = canonical_order(cpg, B=2**16, T=Duration(0.200))
    r2 = canonical_order(cpg, B=2**16, T=Duration(0.200))

    # (i) terminates within (B, T): B and T are both hard triggers; a budget
    # exhaustion yields a weak result, NOT an unbounded loop or an exception.
    assert r1.fingerprint_class in ("strong", "weak")
    assert isinstance(r1.cpg_order_hash, bytes)
    assert len(r1.cpg_order_hash) == 32
    assert len(r1.canonical_order) == len(cpg.nodes)
    assert set(r1.canonical_order) == {n.node_id for n in cpg.nodes}

    # (ii) byte-identical same-source order + hash across re-runs.
    assert r1.canonical_order == r2.canonical_order
    assert r1.cpg_order_hash == r2.cpg_order_hash
    assert r1.fingerprint_class == r2.fingerprint_class


@pytest.mark.invariant
def test_core_03c_hash_field_named_cpg_order_hash_provenance() -> None:
    """Persisted provenance field is named cpg_order_hash + annotation present.

    Test id:       TST-AC-CORE-03c-1
    Maps to AC:    AC-CORE-03c
    Kind tag:      [INVARIANT]
    Inputs:        a persisted provenance_records row produced from a
                   CanonicalOrderResult.
    Outputs:       the row's column names + values.
    Pass criteria: the field is named exactly `cpg_order_hash`; the same row
                   carries `cpg_order_hash_annotation == "canonical iff
                   fingerprint_class = strong"`; no variant name
                   ("canonical_cpg_hash", "cpg_canonical_hash") appears.
    Frequency:     every CI run.
    Hard gate?:    yes.
    """
    result = _strong_result()
    row = to_provenance_fields(result)

    assert "cpg_order_hash" in row
    assert row["cpg_order_hash_annotation"] == "canonical iff fingerprint_class = strong"
    assert row["cpg_order_hash_annotation"] == CPG_ORDER_HASH_ANNOTATION
    # No renamed variant anywhere in the emitted record.
    assert "canonical_cpg_hash" not in row
    assert "cpg_canonical_hash" not in row


@pytest.mark.invariant
def test_core_03c_hash_field_named_cpg_order_hash_sarif() -> None:
    """SARIF result.properties names cpg_order_hash with adjacent annotation.

    Test id:       TST-AC-CORE-03c-2
    Maps to AC:    AC-CORE-03c
    Kind tag:      [INVARIANT]
    Inputs:        a SARIF result.properties block produced from a
                   CanonicalOrderResult (the payload CMP-FND-01 splices in).
    Outputs:       the result.properties block.
    Pass criteria: properties contains `cpg_order_hash` AND
                   `cpg_order_hash_annotation == "canonical iff
                   fingerprint_class = strong"` adjacent in the same block.
    Frequency:     every CI run.
    Hard gate?:    yes.
    """
    import json

    result = _strong_result()
    props = to_sarif_properties(result)

    assert "cpg_order_hash" in props
    assert props["cpg_order_hash_annotation"] == CPG_ORDER_HASH_ANNOTATION
    assert "canonical_cpg_hash" not in props
    assert "cpg_canonical_hash" not in props

    # JSON-adjacency: the annotation key serialises immediately after the hash.
    serialised = json.dumps(props)
    hash_idx = serialised.index('"cpg_order_hash"')
    annot_idx = serialised.index('"cpg_order_hash_annotation"')
    assert annot_idx > hash_idx


@pytest.mark.invariant
def test_core_03c_hash_field_named_cpg_order_hash_auditor_export() -> None:
    """Auditor export JSON names cpg_order_hash with adjacent annotation.

    Test id:       TST-AC-CORE-03c-3
    Maps to AC:    AC-CORE-03c
    Kind tag:      [INVARIANT]
    Inputs:        a CMP-FND-03 auditor-export field trio produced from a
                   CanonicalOrderResult.
    Outputs:       the export object keys.
    Pass criteria: export carries `cpg_order_hash`, `cpg_order_hash_annotation
                   == "canonical iff fingerprint_class = strong"`, and
                   `fingerprint_class` JSON-adjacent; no renamed variant.
    Frequency:     every CI run.
    Hard gate?:    yes.
    """
    import json

    result = _strong_result()
    export = to_auditor_export_fields(result)

    assert {"cpg_order_hash", "cpg_order_hash_annotation", "fingerprint_class"} <= export.keys()
    assert export["cpg_order_hash_annotation"] == CPG_ORDER_HASH_ANNOTATION
    assert export["fingerprint_class"] in ("strong", "weak")
    assert "canonical_cpg_hash" not in export
    assert "cpg_canonical_hash" not in export

    # JSON-adjacency of the three keys (DOC-PROVENANCE §8.2).
    serialised = json.dumps(export)
    hash_idx = serialised.index('"cpg_order_hash"')
    annot_idx = serialised.index('"cpg_order_hash_annotation"')
    klass_idx = serialised.index('"fingerprint_class"')
    assert hash_idx < annot_idx < klass_idx


# ---------------------------------------------------------------------------
# TST-INV-* — invariant tests (INV-5 / INV-6)
# ---------------------------------------------------------------------------


@pytest.mark.invariant
@pytest.mark.parametrize("fingerprint_class", ["strong", "weak"])
def test_inv_5_core_03_annotation_coresident_everywhere(fingerprint_class: str) -> None:
    """INV-5: cpg_order_hash annotation co-resident in every emitter, both classes.

    Test id:       TST-INV-5-CORE-03
    Maps to AC:    INV-5 (owner CMP-CORE-03)
    Kind tag:      [INVARIANT]
    Inputs:        every emitter that writes a record containing
                   cpg_order_hash — provenance row, SARIF properties, auditor
                   export — for BOTH fingerprint_class values (`strong` and the
                   budget-exhausted `weak` fallback path).
    Outputs:       each emitted record.
    Pass criteria: no record containing `cpg_order_hash` omits the adjacent
                   annotation `canonical iff fingerprint_class = strong`; the
                   annotation comes from the single CPG_ORDER_HASH_ANNOTATION
                   constant (never reconstructed from substrings). The annotation
                   is present and identical on the `weak` path too — it is the
                   weak path that makes the annotation load-bearing (the hash is
                   NOT canonical there), so dropping it on weak is the failure
                   this case guards against.
    Frequency:     every CI run.
    Hard gate?:    yes.
    """
    result = _strong_result() if fingerprint_class == "strong" else _weak_result()
    assert result.fingerprint_class == fingerprint_class
    # The dataclass itself cannot be constructed without the annotation Literal.
    assert result.annotation == CPG_ORDER_HASH_ANNOTATION

    emitters = (to_provenance_fields, to_sarif_properties, to_auditor_export_fields)
    for emit in emitters:
        record = emit(result)
        assert "cpg_order_hash" in record, emit.__name__
        # Co-resident annotation, identical on BOTH the strong and weak paths.
        assert record["cpg_order_hash_annotation"] == CPG_ORDER_HASH_ANNOTATION, emit.__name__
        assert record["fingerprint_class"] == fingerprint_class, emit.__name__
        # No renamed variant that would drop the conditional label.
        assert "canonical_cpg_hash" not in record, emit.__name__
        assert "cpg_canonical_hash" not in record, emit.__name__


@pytest.mark.invariant
def test_inv_5_core_02_weak_class_never_auto_suppressed() -> None:
    """INV-5: weak-classed findings flip class on budget exhaustion + are never
    auto-suppressed across a refactor.

    Test id:       TST-INV-5-CORE-02
    Maps to AC:    INV-5 (owner CMP-CORE-02)
    Kind tag:      [INVARIANT]
    Inputs:        a finding whose slice canonicalisation exhausts (B, T) ->
                   fingerprint_class = "weak" (forced via B=1 on a symmetric
                   slice; per advisor + _weak_result, T is flaky so we drive the
                   REAL path through B); and a strong-class finding.
    Outputs:       SliceFingerprintResult.fingerprint_class + the CORE-02-owned
                   eligible_for_baseline_suppression() decision (the typed
                   interface the CMP-FND-01 baseline policy consumes — build-ahead
                   per CLAR-PROC-01).
    Pass criteria: (i) class is "weak" exactly when budget_exhausted is True
                   (truthful self-label, never "strong" on exhaustion);
                   (ii) a weak-classed result is NEVER eligible for baseline
                   suppression across a refactor (the never-auto-suppress rule),
                   while a strong-classed result IS eligible (non-vacuity: the
                   predicate is not a constant-False).
    Frequency:     every CI run.
    Hard gate?:    yes.
    """
    from analysis.fingerprint import (
        compute_slice_fingerprint,
        eligible_for_baseline_suppression,
    )

    # A strong result on an asymmetric witness (2-WL distinguishes every node).
    strong_cpg, strong_finding = _fingerprint_fixture()
    strong = compute_slice_fingerprint(strong_finding, strong_cpg)
    assert strong.fingerprint_class == "strong"
    assert strong.budget_exhausted is False

    # A weak result forced by B=1 on a symmetric witness slice (the REAL budget
    # -exhausted path, not a hand-built dataclass): canonical_order raises
    # BudgetExhausted -> witness-edge-sequence fallback -> class "weak".
    weak_cpg, weak_finding = _symmetric_fingerprint_fixture()
    weak = compute_slice_fingerprint(weak_finding, weak_cpg, B=1)

    # (i) truthful self-label: class is exactly "weak" iff the budget was exhausted.
    assert weak.fingerprint_class == "weak"
    assert weak.budget_exhausted is True
    # The annotation rides with the result on BOTH classes (INV-5 co-residency).
    assert strong.cpg_order_hash_annotation == CPG_ORDER_HASH_ANNOTATION
    assert weak.cpg_order_hash_annotation == CPG_ORDER_HASH_ANNOTATION

    # (ii) the never-auto-suppress rule: a weak result is NEVER eligible for a
    # cross-refactor baseline match; a strong result IS (non-vacuity — the
    # predicate is not constant-False, so the weak=False assertion is meaningful).
    assert eligible_for_baseline_suppression(weak) is False
    assert eligible_for_baseline_suppression(strong) is True


@pytest.mark.invariant
@pytest.mark.xfail(reason="CMP-CORE-01 not yet implemented", strict=False)
def test_inv_6_core_01_recall_claim_only_gate_passing_pairs() -> None:
    """INV-6: recall/precision claims only on CPG-fidelity-gate-passing pairs.

    Test id:       TST-INV-6-CORE-01
    Maps to AC:    INV-6 (owner CMP-CORE-01 for AC-CORE-01b)
    Kind tag:      [INVARIANT]
    Inputs:        the Algorithm 2 benchmark harness fed a (class, language)
                   set that mixes CMP-CP-06-passing pairs and front-end-blocked
                   pairs.
    Outputs:       the per-(class, language) recall table rows.
    Pass criteria: recall/precision rows are emitted ONLY for gate-passing
                   pairs; a front-end-blocked pair is reported with status
                   `front-end-blocked`, NEVER as a recall failure / low number.
    Frequency:     every CI run.
    Hard gate?:    yes.
    """
    # TODO: feed a mixed gate-pass table; assert blocked pairs carry
    #       status="front-end-blocked" and never appear as recall numbers.
    pytest.skip("CMP-CORE-01 not implemented yet")
