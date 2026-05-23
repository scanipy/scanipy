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
@pytest.mark.xfail(reason="CMP-CORE-03 not yet implemented", strict=False)
def test_core_03a_cfi_symmetric_terminates_in_budget_deterministic() -> None:
    """CFI-symmetric inputs terminate in (B, T) with deterministic order.

    Test id:       TST-AC-CORE-03a
    Maps to AC:    AC-CORE-03a
    Kind tag:      [UNIT]
    Inputs:        CFI-style symmetric CPGs (designed to defeat 2-WL) from the
                   curated CMP-CORP-CPG-* corpora; B = 2**16 search-tree nodes,
                   T = 0.200 s wall-clock (CLAR-PARAM-01 RESOLVED).
    Outputs:       CanonicalOrderResult.canonical_order + elapsed_ms across runs.
    Pass criteria: (i) terminates within (B=2**16, T=0.200s) — no unbounded
                   loop; (ii) re-running on the same source yields a
                   byte-identical canonical_order (deterministic same-source
                   order even when a true canonical form is not found in budget).
    Frequency:     every CI run.
    Hard gate?:    yes.
    """
    # TODO: call analysis.ordering.canonical_order(cpg, B=2**16, T=0.200) twice
    #       on each CFI graph; assert order_1 == order_2 and elapsed within T.
    pytest.skip("CMP-CORE-03 not implemented yet")


@pytest.mark.invariant
@pytest.mark.xfail(reason="CMP-CORE-03 not yet implemented", strict=False)
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
    # TODO: assert provenance_records column == "cpg_order_hash" and the
    #       annotation is co-resident in the same row.
    pytest.skip("CMP-CORE-03 not implemented yet")


@pytest.mark.invariant
@pytest.mark.xfail(reason="CMP-CORE-03 not yet implemented", strict=False)
def test_core_03c_hash_field_named_cpg_order_hash_sarif() -> None:
    """SARIF result.properties names cpg_order_hash with adjacent annotation.

    Test id:       TST-AC-CORE-03c-2
    Maps to AC:    AC-CORE-03c
    Kind tag:      [INVARIANT]
    Inputs:        a serialised SARIF result emitted by CMP-FND-01.
    Outputs:       the result.properties block.
    Pass criteria: properties contains `cpg_order_hash` AND
                   `cpg_order_hash_annotation == "canonical iff
                   fingerprint_class = strong"` adjacent in the same block.
    Frequency:     every CI run.
    Hard gate?:    yes.
    """
    # TODO: parse SARIF; assert properties["cpg_order_hash"] present and
    #       properties["cpg_order_hash_annotation"] == the literal annotation.
    pytest.skip("CMP-CORE-03 not implemented yet")


@pytest.mark.invariant
@pytest.mark.xfail(reason="CMP-CORE-03 not yet implemented", strict=False)
def test_core_03c_hash_field_named_cpg_order_hash_auditor_export() -> None:
    """Auditor export JSON names cpg_order_hash with adjacent annotation.

    Test id:       TST-AC-CORE-03c-3
    Maps to AC:    AC-CORE-03c
    Kind tag:      [INVARIANT]
    Inputs:        a CMP-FND-03 auditor-export JSON document.
    Outputs:       the export object keys.
    Pass criteria: export carries `cpg_order_hash`, `cpg_order_hash_annotation
                   == "canonical iff fingerprint_class = strong"`, and
                   `fingerprint_class` JSON-adjacent; no renamed variant.
    Frequency:     every CI run.
    Hard gate?:    yes.
    """
    # TODO: load auditor export; assert the three keys are JSON-adjacent and
    #       the annotation matches the CPG_ORDER_HASH_ANNOTATION constant.
    pytest.skip("CMP-CORE-03 not implemented yet")


# ---------------------------------------------------------------------------
# TST-INV-* — invariant tests (INV-5 / INV-6)
# ---------------------------------------------------------------------------


@pytest.mark.invariant
@pytest.mark.xfail(reason="CMP-CORE-03 not yet implemented", strict=False)
def test_inv_5_core_03_annotation_coresident_everywhere() -> None:
    """INV-5: cpg_order_hash annotation co-resident in every emitter.

    Test id:       TST-INV-5-CORE-03
    Maps to AC:    INV-5 (owner CMP-CORE-03)
    Kind tag:      [INVARIANT]
    Inputs:        every emitter that writes a record containing
                   cpg_order_hash — provenance row, SARIF properties, auditor
                   export, dashboard payload.
    Outputs:       each emitted record.
    Pass criteria: no record containing `cpg_order_hash` omits the adjacent
                   annotation `canonical iff fingerprint_class = strong`; the
                   annotation comes from the single CPG_ORDER_HASH_ANNOTATION
                   constant (never reconstructed from substrings).
    Frequency:     every CI run.
    Hard gate?:    yes.
    """
    # TODO: enumerate every cpg_order_hash emitter; assert annotation present
    #       and equal to analysis.ordering.CPG_ORDER_HASH_ANNOTATION.
    pytest.skip("CMP-CORE-03 not implemented yet")


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
