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

import pytest

from analysis.ifds.dsl.primitives import AccessPathPattern, Sink, Source
from analysis.ifds.dsl.spec import Spec
from analysis.ifds.solver import incremental_solve, solve
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
@pytest.mark.xfail(reason="CMP-CORE-02 not yet implemented", strict=False)
def test_inv_5_core_02_weak_class_never_auto_suppressed() -> None:
    """INV-5: weak-classed findings flip class on budget exhaustion + are never
    auto-suppressed across a refactor.

    Test id:       TST-INV-5-CORE-02
    Maps to AC:    INV-5 (owner CMP-CORE-02)
    Kind tag:      [INVARIANT]
    Inputs:        a finding whose slice canonicalisation exhausts (B, T) ->
                   fingerprint_class = "weak"; a refactored variant of the
                   same finding.
    Outputs:       SliceFingerprintResult.fingerprint_class + the CMP-FND-01
                   baseline-lookup decision.
    Pass criteria: (i) class is "weak" exactly when budget_exhausted is True
                   (truthful self-label, never "strong" on exhaustion);
                   (ii) a weak-classed prior is never matched/auto-suppressed
                   across a refactor by the baseline-lookup policy.
    Frequency:     every CI run.
    Hard gate?:    yes.
    """
    # TODO: force budget exhaustion -> assert class == "weak"; assert the
    #       CMP-FND-01 baseline policy does not suppress a weak prior on refactor.
    pytest.skip("CMP-CORE-02 not implemented yet")


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
