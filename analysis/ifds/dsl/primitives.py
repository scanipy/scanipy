"""CMP-DET-01 — combinator DSL primitive constructors.

The four pinned primitives (``source``, ``sink``, ``sanitize``, ``propagate``)
plus the ``Clause`` union. Signatures are normative per DOC-CMP-DET-01 §3.1 and
the canonical PEG in DOC-DSL §2.

These are *declarative data*: frozen dataclasses, no embedded callables. Each
primitive denotes a flow function ``f : 2^D -> 2^D`` that is **distributive by
construction** over the finite powerset fact lattice (DOC-DSL §3). The flow
functions themselves are built in :mod:`analysis.ifds.dsl.flow`; this module
holds only the parsed grammar nodes.

INV-4 (owner): the grammar is the decidable membership test against the
distributive-by-construction fragment. Anything outside it is rejected at
registration, never analyzed (see :mod:`analysis.ifds.dsl.parser`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, NewType

# ─── Access path pattern (argument grammar; not itself a primitive) ─────────
# PEG-parsed per DOC-DSL §2. Kept as opaque string newtypes at this layer;
# the matcher semantics live in CMP-CORE-01 (the solver), not in CMP-DET-01.
AccessPathPattern = NewType("AccessPathPattern", str)
ArgRef = NewType("ArgRef", str)  # "arg[0]" | "arg[name]"
FieldRef = NewType("FieldRef", str)  # "field[name]" | "this.name"
ReturnRef = Literal["ret"]

# The four pinned primitive heads. The grammar admits no other primitive head;
# adding one is a CLAR-* event, never an inline extension (DOC-DSL §2 notes).
PRIMITIVE_HEADS: tuple[str, ...] = ("source", "sink", "sanitize", "propagate")


@dataclass(frozen=True)
class Source:
    """source(access-path-pattern): inject taint(p) into the out-set."""

    pattern: AccessPathPattern


@dataclass(frozen=True)
class Sink:
    """sink(access-path-pattern): identity transfer + read-out predicate."""

    pattern: AccessPathPattern


@dataclass(frozen=True)
class Sanitize:
    """sanitize(access-path-pattern): kill facts matching the pattern."""

    pattern: AccessPathPattern


@dataclass(frozen=True)
class Propagate:
    """propagate(source -> target): gen taint(target) when taint(source) in X.

    Four sanctioned forms (PropagateBody), enumerated by PROPAGATE_FORMS:
      arg -> ret    | arg -> field   | field -> ret   | field -> field
    """

    source: ArgRef | FieldRef
    target: ReturnRef | FieldRef


# Clause union: a Spec is a conjunction (clause-wise union) of these.
Clause = Source | Sink | Sanitize | Propagate

# The four PropagateBody forms, each its own distributivity proof obligation
# (DOC-DSL §3.4, §3.5; AC-DET-01a). Identifiers are positional kinds, not
# concrete refs — the proof obligation is form-indexed.
PropagateForm = Literal["arg_ret", "arg_field", "field_ret", "field_field"]
PROPAGATE_FORMS: tuple[PropagateForm, ...] = (
    "arg_ret",
    "arg_field",
    "field_ret",
    "field_field",
)
