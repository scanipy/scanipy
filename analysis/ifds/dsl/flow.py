"""CMP-DET-01 — flow-function denotations of DSL primitives.

Each DSL primitive denotes an IFDS flow function ``f : 2^D -> 2^D`` over the
finite powerset lattice of program facts ``D`` (DOC-DSL §3). This module builds
the concrete transfer for each primitive / sanctioned composition so the
distributivity proof obligations (AC-DET-01a) can be discharged *exhaustively*
over a bounded ``D``.

Distributivity contract (RHS'95 §3): ``f(X | Y) = f(X) | f(Y)`` for all
``X, Y subset D``. Each builder below is distributive by construction; the
one-line proofs are in DOC-DSL §3 and the exhaustive machine checks are in
:mod:`analysis.ifds.dsl.proofs` / ``tests/unit/test_dsl_proofs.py``.

The fact domain here is an abstract finite set of opaque tokens. A token models
``taint(p)`` for some access path ``p``; the primitives are parameterised by
*which* tokens they gen/kill, mirroring the access-path matcher without
depending on CMP-CORE-01's concrete matcher.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from itertools import combinations

# A fact is an opaque hashable token; the fact set is a frozenset over D.
Fact = int
FactSet = frozenset[Fact]
FlowFunction = Callable[[FactSet], FactSet]


def enumerate_bounded_fact_domain(max_size: int = 8) -> tuple[Fact, ...]:
    """Return the bounded finite fact domain D used for exhaustive proofs.

    The bound is pinned by CMP-DET-01 at implementation (DOC-DSL §5; CLAR-PARAM-01
    explicitly does NOT cover it). DOC-DSL recommends ``|D| <= 12``; we pin
    ``|D| = 8`` so the exhaustive enumeration is ``2^8 * 2^8 = 65_536`` pairs per
    obligation — comfortably exhaustive yet fast in CI. The requirement from
    AC-DET-01a is *exhaustive over a bounded domain*, not a specific size.
    """
    if max_size < 1:
        raise ValueError("fact domain must be non-empty for a meaningful proof")
    return tuple(range(max_size))


def powerset(domain: Iterable[Fact]) -> Iterable[FactSet]:
    """Yield every subset of ``domain`` as a FactSet (exhaustive, not sampled)."""
    items = tuple(domain)
    for r in range(len(items) + 1):
        for combo in combinations(items, r):
            yield frozenset(combo)


# ─── Primitive flow-function builders ───────────────────────────────────────
# Each builder takes the abstract gen/kill parameters that the access-path
# matcher would supply and returns a distributive FlowFunction.


def build_source(gen: Fact) -> FlowFunction:
    """source(p): X |-> X | {taint(p)}.

    Distributive: (X|Y)|{t} = (X|{t})|(Y|{t}).
    """

    def f(x: FactSet) -> FactSet:
        return x | {gen}

    return f


def build_sink() -> FlowFunction:
    """sink(p): identity on the fact set (the read-out predicate is off-lattice).

    Distributive: id(X|Y) = id(X)|id(Y). The ReportPredicate is monotone, not
    distributive, but it is NOT a flow function (DOC-DSL §3.2) and is therefore
    not subject to this obligation.
    """

    def f(x: FactSet) -> FactSet:
        return x

    return f


def build_sanitize(kill: frozenset[Fact]) -> FlowFunction:
    """sanitize(p): X |-> X \\ K_p for a fixed predicate-defined kill set K_p.

    Distributive: (X|Y)\\K = (X\\K)|(Y\\K).
    """

    def f(x: FactSet) -> FactSet:
        return x - kill

    return f


def build_propagate(source: Fact, target: Fact) -> FlowFunction:
    """propagate(s -> t): X |-> X | {taint(t) : taint(s) in X}.

    Distributive: g(X|Y) = (X|Y)|A(X|Y) = (X|A(X))|(Y|A(Y)) = g(X)|g(Y),
    because A(X|Y) = A(X)|A(Y) (taint(s) in X|Y iff in X or in Y).

    The four PropagateBody forms (arg->ret, arg->field, field->ret,
    field->field) share this builder; the form determines only which abstract
    positions ``source`` and ``target`` model, not the transfer's algebra. Each
    form carries its own proof obligation (DOC-DSL §3.4).
    """

    def f(x: FactSet) -> FactSet:
        if source in x:
            return x | {target}
        return x

    return f


def union_flow(functions: Iterable[FlowFunction]) -> FlowFunction:
    """Clause conjunction (DOC-DSL §4.1): spec(X) = union of clause transfers.

    A finite union of distributive functions over a powerset lattice is
    distributive (RHS'95 §3). This is the sanctioned-composition obligation.
    """
    fs = tuple(functions)

    def f(x: FactSet) -> FactSet:
        out: FactSet = frozenset()
        for g in fs:
            out = out | g(x)
        return out

    return f


def is_distributive(f: FlowFunction, domain: tuple[Fact, ...]) -> bool:
    """Exhaustively verify f(X | Y) == f(X) | f(Y) over all subsets of ``domain``.

    Exhaustive, not sampled (AC-DET-01a). Returns False on the first
    counterexample. ``2^|D| * 2^|D|`` pairs are enumerated.
    """
    subsets = tuple(powerset(domain))
    for x in subsets:
        fx = f(x)
        for y in subsets:
            if f(x | y) != fx | f(y):
                return False
    return True


__all__ = [
    "Fact",
    "FactSet",
    "FlowFunction",
    "build_propagate",
    "build_sanitize",
    "build_sink",
    "build_source",
    "enumerate_bounded_fact_domain",
    "is_distributive",
    "powerset",
    "union_flow",
]
