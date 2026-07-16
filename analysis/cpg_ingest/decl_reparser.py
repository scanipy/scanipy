"""CMP-SNAP-05 (CPG-ingest sub-scope) — ``DeclReparser`` implementation (Wave-2 STUB).

``analysis.cpg_delta.DeclReparser`` is the injected collaborator
``compute_incremental_cpg`` (CMP-SNAP-02) uses for function-granularity
re-parsing of a single changed declaration (``cpg_delta.py`` §"Parse at the
boundary"). It is a ``@runtime_checkable`` ``Protocol`` — production callers
never construct one directly from this module without going through the
typed seam; tests fixture a fake the way CMP-FND-03 fixtured its KMS signer.

This module ships :class:`JoernDeclReparser`, a REAL class that structurally
satisfies the ``DeclReparser`` protocol (verified by this module's own unit
test via ``isinstance(..., DeclReparser)``, since the protocol is
``@runtime_checkable``) so CMP-SNAP-02 integration has a concrete,
typed-correct collaborator to wire in — but per the plan's Wave-1 table
("stub acceptable") its :meth:`JoernDeclReparser.reparse` body raises
:class:`NotImplementedError` rather than faking a re-parse. Same rationale as
:mod:`analysis.cpg_ingest.graph_views`: nothing on the critical path to the
first bootstrap-scan ``Finding`` needs this (CLAR-SNAP-04 — the first
snapshot bypasses ``compute_incremental_cpg`` entirely), so this is honestly
unbuilt rather than faked (RULE-4).

TODO (Wave-2): a real ``reparse`` needs a Joern **function-granularity**
re-parse — i.e. re-running the parse+export pipeline scoped to a single
declaration rather than the whole ``src_root``. Joern's CLI (per the pinned
``JOERN_ARGV_ALLOWLIST``) has no "parse just this one method" flag, so this
likely needs either (a) a second in-image CPGQL script parameterized by
``decl_fqn`` (mirrors the CLAR-SNAP-05 export-script pattern in
:mod:`analysis.cpg_ingest.joern_frontend`) that re-parses and re-exports only
the subtree under that declaration, re-mapped through
:func:`analysis.cpg_ingest.mapper.map_export` with node ids remapped starting
at ``fresh_id_base`` (never colliding with ``compute_incremental_cpg``'s
preserved-id set — the builder raises ``NodeIdCollision`` if this class
misbehaves), or (b) a full-file re-parse with the builder responsible for
diffing which nodes are "new" — a design decision, not something to invent
inline here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from analysis.cpg_delta import DeclSubgraph

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True)
class JoernDeclReparser:
    """Real ``DeclReparser`` protocol implementation — Wave-2 STUB body.

    Structurally satisfies ``analysis.cpg_delta.DeclReparser`` (a
    ``@runtime_checkable Protocol`` requiring only a matching ``reparse``
    method — verified by this module's unit test). Carries exactly the
    context a real function-granularity re-parse will need once built: the
    same ``(src_root, language, env, workdir)`` shape as
    :func:`analysis.cpg_ingest.joern_frontend.parse_source`, so wiring the
    real implementation in Wave-2 is a body change, not a signature change.
    """

    src_root: Path
    language: str
    env: Mapping[str, str]
    workdir: Path

    def reparse(self, decl_fqn: str, *, fresh_id_base: int) -> DeclSubgraph:
        """Re-parse a single changed declaration to a fresh subgraph.

        **Wave-2 STUB — not implemented.** See module docstring TODO.

        Args:
            decl_fqn: the enclosing-declaration FQN CMP-SNAP-02 determined
                changed (``CPGNode.enclosing_decl_fqn`` shape).
            fresh_id_base: the lowest node id this reparse may mint (the
                builder passes ``max(preserved_ids) + 1``); a real
                implementation must mint ids ``>= fresh_id_base`` and disjoint
                from the preserved set.

        Raises:
            NotImplementedError: always, until the Wave-2 function-granularity
                re-parse pipeline lands (see module docstring TODO).
        """
        raise NotImplementedError(
            "analysis.cpg_ingest.decl_reparser.JoernDeclReparser.reparse is "
            "Wave-2 scope (track-1A stub, plan Wave-1 table) — "
            "compute_incremental_cpg is bypassed entirely for the "
            "CLAR-SNAP-04 bootstrap (no-parent) path, so no caller on the "
            f"critical path to the first Finding needs a real reparse yet. "
            f"decl_fqn={decl_fqn!r} fresh_id_base={fresh_id_base!r} — see this "
            "module's docstring TODO for the function-granularity re-parse "
            "design question."
        )


__all__ = ["JoernDeclReparser"]
