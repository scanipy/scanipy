"""IFDS/IDE analysis core (Algorithm 2) and its combinator DSL.

Subpackages:
  - ``analysis.ifds.dsl`` — CMP-DET-01 combinator DSL.

Public surface (CMP-CORE-01, this work package):
  - :func:`solve` / :func:`incremental_solve` — RHS'95 Tabulation entry points.
  - :class:`SolverResult`, :class:`Finding` — solver outputs.
  - :class:`SummaryCache` — reusable procedure-summary cache.
  - :class:`ExplodedSupergraph`, :func:`build_supergraph`, :class:`ProcId`.
"""

from analysis.ifds.solver import (
    Fact,
    Finding,
    NonDistributiveSpec,
    SolverResult,
    SummaryCache,
    incremental_solve,
    solve,
)
from analysis.ifds.supergraph import (
    ExplodedSupergraph,
    Procedure,
    ProcId,
    build_supergraph,
)

__all__ = [
    "ExplodedSupergraph",
    "Fact",
    "Finding",
    "NonDistributiveSpec",
    "ProcId",
    "Procedure",
    "SolverResult",
    "SummaryCache",
    "build_supergraph",
    "incremental_solve",
    "solve",
]
