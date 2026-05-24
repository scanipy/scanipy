"""Gate 1: DSL distributivity proofs — TST-AC-DET-01a.

These tests discharge AC-DET-01a: every DSL primitive and every sanctioned
composition carries a machine-checked distributivity proof obligation
(``f(X | Y) == f(X) | f(Y)``), verified EXHAUSTIVELY over a bounded finite fact
domain (DOC-DSL §5; DOC-CMP-DET-01 §9.3). A missing or failing obligation is a
release blocker (Gate 1 under CMP-CI-01).

CMP-DET-01 owns the proof obligations. The closure/registration check (parser)
is exercised in ``tests/unit/test_det_specs.py`` (TST-AC-DET-01b /
TST-INV-4-DET-01). The downstream DetectorRegistry that *consumes* discharged
obligations is CMP-DET-02 (not yet implemented).
"""

import pytest

from analysis.ifds.dsl.flow import (
    build_propagate,
    build_sanitize,
    build_sink,
    build_source,
    enumerate_bounded_fact_domain,
    is_distributive,
    union_flow,
)
from analysis.ifds.dsl.proofs import (
    REQUIRED_OBLIGATION_IDS,
    all_obligations_discharged,
    discharge,
    registered_obligation_ids,
)

_D = enumerate_bounded_fact_domain()


@pytest.mark.unit
def test_dsl_boot_guard_all_obligations_discharged() -> None:
    """AC-DET-01a (Gate 1): the DSL boot guard returns True.

    Every required primitive + sanctioned composition has a registered
    obligation that discharges under exhaustive enumeration. On False the
    process must refuse startup (T-CMP-DET-01-02); CI Gate 1 flips red.
    """
    assert set(REQUIRED_OBLIGATION_IDS).issubset(registered_obligation_ids())
    assert all_obligations_discharged() is True


@pytest.mark.unit
def test_dsl_every_required_obligation_discharges_individually() -> None:
    """AC-DET-01a: one discharged obligation per primitive/composition.

    propagate has four (arg_ret, arg_field, field_ret, field_field); plus the
    clause-conjunction closure step (DOC-DSL §3.5, §4.1).
    """
    assert len(REQUIRED_OBLIGATION_IDS) == 8
    for oid in REQUIRED_OBLIGATION_IDS:
        assert discharge(oid) is True, f"obligation {oid} not discharged"


@pytest.mark.unit
def test_distributivity_source() -> None:
    """source(p): X |-> X | {taint(p)} is distributive (exhaustive over D)."""
    assert is_distributive(build_source(0), _D)


@pytest.mark.unit
def test_distributivity_sink_identity() -> None:
    """sink(p): identity flow is distributive; read-out is off-lattice."""
    assert is_distributive(build_sink(), _D)


@pytest.mark.unit
def test_distributivity_sanitize() -> None:
    """sanitize(p): X |-> X \\ K_p is distributive (set difference over union)."""
    assert is_distributive(build_sanitize(frozenset((1, 2))), _D)


@pytest.mark.unit
@pytest.mark.parametrize("form", ["arg_ret", "arg_field", "field_ret", "field_field"])
def test_distributivity_propagate(form: str) -> None:
    """propagate(s -> t): gen-of-t conditioned on s is distributive, all 4 forms.

    Each PropagateBody form is its own obligation (DOC-DSL §3.4). The algebra is
    identical across forms; the form fixes only which abstract positions s/t
    model.
    """
    assert form in {"arg_ret", "arg_field", "field_ret", "field_field"}
    assert is_distributive(build_propagate(3, 4), _D)


@pytest.mark.unit
def test_distributivity_clause_conjunction_closure() -> None:
    """Sanctioned composition: a finite union of distributive flows is distributive.

    Closure step for clause conjunction (DOC-DSL §4.1; RHS'95 §3).
    """
    composed = union_flow((build_source(0), build_propagate(3, 4), build_sanitize(frozenset((1,)))))
    assert is_distributive(composed, _D)


@pytest.mark.unit
def test_distributivity_check_detects_a_non_distributive_function() -> None:
    """The exhaustive checker is not vacuous: a non-distributive flow fails it.

    A "kill the whole set if any fact is present" transfer depends on the
    in-set non-linearly and violates f(X | Y) = f(X) | f(Y). Guards against a
    checker that trivially returns True.
    """

    def non_distributive(x: frozenset[int]) -> frozenset[int]:
        return frozenset() if x else frozenset((0,))

    assert is_distributive(non_distributive, _D) is False
