"""CMP-SNAP-05 (CPG-ingest sub-scope) — ``GraphView`` builder (Wave-2 STUB).

``analysis.cpg_delta.GraphView`` (CMP-SNAP-02's ``compute_incremental_cpg``
input) needs a ``reverse_symbol_index`` / ``call_graph`` / ``class_hierarchy`` /
``decl_to_type`` built from a real, freshly-parsed :class:`analysis.ordering.CPG`
before the incremental (2nd-commit-onward) path can run for real.

**Per the approved plan (`crispy-dazzling-book.md`, Wave-1 table, track 1A
row): this is explicitly Wave-2 scope.** The plan's headline finding is that
the FIRST scan is a bootstrap full-parse (CLAR-SNAP-04) that bypasses
``compute_incremental_cpg`` — and therefore ``GraphView`` — entirely; nothing
on the critical path to the first ``Finding`` calls this module. It is stubbed
here with a typed, honest ``NotImplementedError`` (the same "name the unbuilt
deps rather than fake the pipeline" discipline
``services/snapshot/worker.py::run_execute_loop`` already uses) so:

* the typed interface exists NOW for whoever picks up the Wave-2 incremental
  work (no second round of interface bikeshedding), and
* nothing downstream can silently get a fake, empty, or wrong ``GraphView`` —
  a real caller finds out immediately, at the call site, that this is unbuilt.

TODO (Wave-2, tracked informally here — no dedicated CLAR filed since the plan
already scopes this as Wave-2 and no PLAN/SDD-level ambiguity blocks it, RULE-4):
  - ``reverse_symbol_index``: for every node with a non-empty ``resolved_fqn``,
    invert to "symbol FQN -> {referencing declaration FQNs}" by walking
    non-AST (CFG/PDG) edges and ``enclosing_decl_fqn`` back to the referencing
    declaration.
  - ``call_graph``: for every ``CALL`` node with a non-empty ``resolved_fqn``,
    ``enclosing_decl_fqn -> {resolved_fqn}``.
  - ``class_hierarchy`` / ``decl_to_type``: needs Joern's ``INHERITS_FROM``/
    ``TYPE_DECL`` structural relationships, which are not yet part of the
    CLAR-SNAP-05 export schema (:mod:`analysis.cpg_ingest.mapper` exports
    ``AST``/``CFG``/``CDG``/``REACHING_DEF`` only) — widening the export
    schema to carry inheritance edges is itself a Wave-2 prerequisite.
"""

from __future__ import annotations

from analysis.cpg_delta import GraphView
from analysis.ordering import CPG


def build_graph_view(cpg: CPG) -> GraphView:
    """Build a :class:`analysis.cpg_delta.GraphView` from a parsed :class:`CPG`.

    **Wave-2 STUB — not implemented.** See module docstring. The typed
    signature is fixed now (``CPG -> GraphView``, matching
    ``analysis.cpg_delta.GraphView``'s shipped field set) so CMP-SNAP-02
    integration work has a stable seam to build against; the body
    intentionally raises rather than returning a fake/empty ``GraphView`` that
    would silently make ``compute_incremental_cpg`` produce ``AFFECTED = ∅``
    (the exact bootstrap-path failure mode CLAR-SNAP-04 documents for the
    *first* snapshot — returning an empty stub here would reproduce that same
    failure mode for the *second* snapshot instead, which is strictly worse
    since it would look like a real incremental result).

    Args:
        cpg: a freshly mapped :class:`analysis.ordering.CPG` (e.g. the output
            of :func:`analysis.cpg_ingest.joern_frontend.parse_source`).

    Raises:
        NotImplementedError: always, until the Wave-2 builder lands (see the
            module docstring TODO list for the four fields' derivation plan).
    """
    raise NotImplementedError(
        "analysis.cpg_ingest.graph_views.build_graph_view is Wave-2 scope "
        "(track-1A stub, plan Wave-1 table) — CMP-SNAP-02's "
        "compute_incremental_cpg is bypassed entirely for the CLAR-SNAP-04 "
        f"bootstrap (no-parent) path, so no caller on the critical path to the "
        f"first Finding needs a real GraphView yet. Got a CPG with "
        f"{len(cpg.nodes)} nodes / {len(cpg.edges)} edges — see this module's "
        "docstring TODO list for the four fields' derivation plan."
    )


__all__ = ["build_graph_view"]
