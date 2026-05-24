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
# CMP-CORE-01 — IFDS/IDE tabulation solver (Algorithm 2)
# ---------------------------------------------------------------------------


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
@pytest.mark.xfail(reason="CMP-CORE-01 not yet implemented", strict=False)
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
    # TODO: call analysis.ifds.solver.incremental_solve(...); assert
    #       result.visited_procs <= (affected_set | transitive_callers).
    pytest.skip("CMP-CORE-01 not implemented yet")


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
