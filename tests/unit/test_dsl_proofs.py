"""Gate 1: DSL distributivity proof stubs — TST-AC-DET-01a.

These tests verify that every registered detector spec satisfies the
distributivity precondition required by the IFDS/IDE tabulation algorithm
(Reps-Horwitz-Sagiv). Until CMP-DET-01 is implemented, the proofs are
marked xfail so the CI job exists and is exercisable without blocking.

When CMP-DET-01 is DONE, replace xfail markers with real proof assertions.
"""

import pytest


@pytest.mark.unit
@pytest.mark.xfail(
    reason="CMP-DET-01 (Combinator DSL) not yet implemented — proof stubs",
    strict=False,
)
def test_dsl_closure_empty_registry_is_distributive() -> None:
    """An empty detector registry trivially satisfies distributivity."""
    # TODO: import DetectorRegistry from detectors.registry when CMP-DET-01 is DONE
    # registry = DetectorRegistry()
    # assert registry.all_distributive()
    pytest.skip("CMP-DET-01 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(
    reason="CMP-DET-01 (Combinator DSL) not yet implemented — proof stubs",
    strict=False,
)
def test_dsl_closure_rejects_non_dsl_spec() -> None:
    """The DSL closure check must reject any non-DSL spec at registration time.

    INV-4: combinator DSL closure check rejects any non-DSL spec at
    registration — never silently accepts.
    """
    # TODO: CLAR-PARAM-01 — formalise the 'non-DSL spec' type boundary
    pytest.skip("CMP-DET-01 not implemented yet")


@pytest.mark.unit
@pytest.mark.xfail(
    reason="CMP-DET-01 (Combinator DSL) not yet implemented — proof stubs",
    strict=False,
)
def test_dsl_closure_all_registered_specs_distributive() -> None:
    """All registered detector specs must pass the distributivity proof.

    Maps to: AC-DET-01a (Gate 1 hard requirement).
    """
    # TODO: iterate detectors.registry.REGISTRY and assert each spec.is_distributive()
    pytest.skip("CMP-DET-01 not implemented yet")
