"""CMP-DET-01 — distributivity proof-obligation registry (AC-DET-01a, Gate 1).

Every primitive and every sanctioned composition carries a machine-checked
distributivity proof obligation, discharged *exhaustively* over a bounded finite
fact domain (DOC-CMP-DET-01 §3.4, §9.3; DOC-DSL §5). The DSL boot sequence
enumerates the primitive table and the obligation table; a missing or failing
obligation refuses startup (``T-CMP-DET-01-02``). This is CI Gate 1 — a release
blocker on False (``AC-DET-01a``).

Obligation identity table (one per primitive; ``propagate`` has four, one per
PropagateBody form; one closure-step obligation for clause conjunction):

    source · sink · sanitize ·
    propagate:arg_ret · propagate:arg_field · propagate:field_ret ·
    propagate:field_field · compose:clause_union
"""

from __future__ import annotations

from collections.abc import Callable

from analysis.ifds.dsl.flow import (
    build_propagate,
    build_sanitize,
    build_sink,
    build_source,
    enumerate_bounded_fact_domain,
    is_distributive,
    union_flow,
)
from analysis.ifds.dsl.primitives import PROPAGATE_FORMS

ProofObligation = Callable[[], bool]  # property test; returns True on discharge

# The complete set of obligation ids that MUST be discharged for the DSL to
# boot. Mirrors DOC-CMP-DET-01 §9.2 / DOC-DSL §3.5 exactly.
REQUIRED_OBLIGATION_IDS: tuple[str, ...] = (
    "source",
    "sink",
    "sanitize",
    "propagate:arg_ret",
    "propagate:arg_field",
    "propagate:field_ret",
    "propagate:field_field",
    "compose:clause_union",
)

_OBLIGATIONS: dict[str, ProofObligation] = {}


def register_proof(primitive_id: str, obligation: ProofObligation) -> None:
    """Bind a discharged distributivity obligation to a primitive id."""
    _OBLIGATIONS[primitive_id] = obligation


def discharge(primitive_id: str) -> bool:
    """Run a single registered obligation, returning its boolean verdict."""
    return _OBLIGATIONS[primitive_id]()


def registered_obligation_ids() -> frozenset[str]:
    """Return the set of obligation ids currently registered."""
    return frozenset(_OBLIGATIONS)


def all_obligations_discharged() -> bool:
    """DSL boot guard (AC-DET-01a, Gate 1).

    True iff every required primitive and every sanctioned composition has a
    registered obligation that returns True under *exhaustive* enumeration over
    the bounded fact domain. CI Gate 1; release blocker on False.
    """
    if not set(REQUIRED_OBLIGATION_IDS).issubset(_OBLIGATIONS):
        return False
    return all(_OBLIGATIONS[oid]() for oid in REQUIRED_OBLIGATION_IDS)


# ─── Obligation definitions (exhaustive over the bounded domain) ────────────
# The domain is small enough that all 2^|D| * 2^|D| (X, Y) pairs are enumerated
# (DOC-DSL §5: exhaustive, not sampled). Distinct gen/kill tokens model the
# access-path matcher's effect without depending on CMP-CORE-01.

_D = enumerate_bounded_fact_domain()
# Reserve token positions used by the primitives under test.
_GEN, _KILL_A, _KILL_B, _PSRC, _PTGT = 0, 1, 2, 3, 4


def _obl_source() -> bool:
    return is_distributive(build_source(_GEN), _D)


def _obl_sink() -> bool:
    return is_distributive(build_sink(), _D)


def _obl_sanitize() -> bool:
    return is_distributive(build_sanitize(frozenset((_KILL_A, _KILL_B))), _D)


# Distinct in-domain (source, target) fact positions per PropagateBody form.
# build_propagate's distributivity is independent of which facts model the
# positions (see flow.build_propagate docstring + RHS'95 §3), so giving each
# form its own distinct pair makes every `propagate:<form>` obligation a
# concrete, non-identical exhaustive check rather than four registrations of a
# single closure. All facts are within _D = (0..7), so no check is vacuous.
_PF1, _PF2 = 5, 6  # two further reserved positions, distinct from _GEN.._PTGT
_PROPAGATE_FORM_FACTS: dict[str, tuple[int, int]] = {
    "arg_ret": (_PSRC, _PTGT),
    "arg_field": (_PSRC, _PF1),
    "field_ret": (_PF1, _PTGT),
    "field_field": (_PF1, _PF2),
}


def _make_propagate_obl(source: int, target: int) -> ProofObligation:
    """Build the per-form distributivity obligation for propagate(source→target)."""

    def _obl() -> bool:
        return is_distributive(build_propagate(source, target), _D)

    return _obl


def _obl_clause_union() -> bool:
    # Sanctioned composition: union of two distinct distributive primitives.
    composed = union_flow(
        (
            build_source(_GEN),
            build_propagate(_PSRC, _PTGT),
            build_sanitize(frozenset((_KILL_A,))),
        )
    )
    return is_distributive(composed, _D)


def install_default_obligations() -> None:
    """Register the by-construction obligations for every primitive + composition.

    Idempotent. Invoked at import time so ``all_obligations_discharged()`` is
    meaningful from process start (DOC-CMP-DET-01 §4.3 boot-time enumeration).
    """
    register_proof("source", _obl_source)
    register_proof("sink", _obl_sink)
    register_proof("sanitize", _obl_sanitize)
    for form in PROPAGATE_FORMS:
        src, tgt = _PROPAGATE_FORM_FACTS[form]
        register_proof(f"propagate:{form}", _make_propagate_obl(src, tgt))
    register_proof("compose:clause_union", _obl_clause_union)


install_default_obligations()
