"""CMP-SNAP-05 (CPG-ingest sub-scope, CLAR-SNAP-03) — source -> CPG ingestion.

Owns "parse source into ``analysis.ordering.CPG``" — the capability
``analysis/cpg_delta.py``'s own docstring explicitly disclaims
("never a real front-end call"; see ``CLAR-SNAP-03``, ``WBS.md §17``).

Public surface (the plan's track-1A/1B handshake):

    from analysis.cpg_ingest.joern_frontend import parse_source
    cpg = parse_source(src_root, language, env=worker_env, workdir=tmp_dir)

Modules:
    joern_frontend  — ``secure_run`` orchestration (parse + CLAR-SNAP-05
                       export phases); the public ``parse_source`` entry point.
    mapper          — Joern export JSON -> ``CPG``, with this package's own
                       deterministic node-emission order (INV-5 load-bearing;
                       see ``mapper``'s module docstring).
    graph_views     — ``analysis.cpg_delta.GraphView`` builder. Wave-2 STUB
                       (typed interface only; not on the bootstrap-scan path).
    decl_reparser   — ``analysis.cpg_delta.DeclReparser`` implementation.
                       Wave-2 STUB (typed interface only; not on the
                       bootstrap-scan path).
"""

from __future__ import annotations
