"""CMP-DET-01 — combinator DSL for taint specs.

A declarative DSL whose primitives (``source``, ``sink``, ``sanitize``,
``propagate``, sanctioned compositions) are distributive-by-construction over
the finite fact domain. Operational owner of Algorithm 2's distributivity
precondition (INV-4): any spec outside this grammar is rejected at registration
with a precise ``E-DSL-*`` diagnostic, never analyzed.

Public surface (DOC-CMP-DET-01 §3):
  - :func:`parse_spec` — parser entry point; returns a frozen :class:`Spec` or
    raises :class:`DSLError`.
  - :func:`revalidate_spec` — re-run the INV-4 escape-hatch gate over an
    already-constructed :class:`Spec` (closes the hand-built-Spec bypass; see
    CMP-DET-02 ``register()``). Raises :class:`DSLError` on any escape hatch.
  - :class:`Spec`, :class:`Source`, :class:`Sink`, :class:`Sanitize`,
    :class:`Propagate` — the closed grammar.
  - :func:`all_obligations_discharged` — DSL boot guard (AC-DET-01a, Gate 1).
"""

from __future__ import annotations

from analysis.ifds.dsl.errors import DSLError, DSLErrorCode
from analysis.ifds.dsl.parser import parse_spec, revalidate_spec
from analysis.ifds.dsl.primitives import (
    Clause,
    Propagate,
    Sanitize,
    Sink,
    Source,
)
from analysis.ifds.dsl.proofs import (
    REQUIRED_OBLIGATION_IDS,
    all_obligations_discharged,
    registered_obligation_ids,
)
from analysis.ifds.dsl.spec import Spec

__all__ = [
    "REQUIRED_OBLIGATION_IDS",
    "Clause",
    "DSLError",
    "DSLErrorCode",
    "Propagate",
    "Sanitize",
    "Sink",
    "Source",
    "Spec",
    "all_obligations_discharged",
    "parse_spec",
    "registered_obligation_ids",
    "revalidate_spec",
]
