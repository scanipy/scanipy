"""CMP-SNAP-05 CPG-ingest sub-scope (CLAR-SNAP-03/05) — hermetic unit tests.

Covers the track-1A deliverable (plan ``crispy-dazzling-book.md`` Wave-1
table):

  - :mod:`analysis.cpg_ingest.mapper` — Joern export JSON -> ``CPG``, with the
    mapper's OWN deterministic node-emission order (the INV-5 / CP-05
    provenance obligation the plan's Provenance section calls out). The two
    anti-vacuity controls here are (a) repeated-parse determinism and (b),
    the load-bearing one, ORDER-INDEPENDENCE from the raw export array order
    (``shuffled_export`` reverses both arrays; a mapper that trusted raw
    order would fail this, not (a)).
  - :mod:`analysis.cpg_ingest.joern_frontend` — the ``secure_run`` call shape,
    monkeypatched exactly like ``tests/unit/test_snap_specs.py:541-573``
    (fake the process spawn, never a real ``joern`` binary).
  - :mod:`analysis.cpg_ingest.graph_views` / ``decl_reparser`` — honest
    Wave-2 stubs: assert they raise (never silently return a fake result).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from analysis.cpg_delta import DeclReparser
from analysis.cpg_ingest import decl_reparser as decl_reparser_mod
from analysis.cpg_ingest import graph_views
from analysis.cpg_ingest import joern_frontend as jf
from analysis.cpg_ingest.mapper import (
    UnknownEdgeKindError,
    UnknownNodeReferenceError,
    map_export,
)
from analysis.ordering import canonical_order
from tests.cpg_ingest_fixtures import SQLI_JOERN_EXPORT_FIXTURE, shuffled_export

# ---------------------------------------------------------------------------
# mapper.py
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_mapper_ordering_and_field_derivation_on_sqli_fixture() -> None:
    """The mapper's own deterministic order + the CLAR-SNAP-05 field mapping.

    Spot-checks derived by hand-tracing the fixture's AST (see
    ``tests/cpg_ingest_fixtures.py`` docstring): the two-file fixture's
    ``helpers.py`` subtree sorts entirely before ``sqli.py`` (filename is the
    primary sort key), and every node within a file sorts by
    ``(line, col, ast_preorder_index)``.
    """
    cpg = map_export(SQLI_JOERN_EXPORT_FIXTURE)

    assert len(cpg.nodes) == 26
    # helpers.py (n24 METHOD noop, n25 METHOD_RETURN) sorts entirely before
    # every sqli.py node, then sqli.py nodes follow in raw-id order (which,
    # in THIS fixture, happens to already be DFS/line/col order — see the
    # order-independence test below for the real robustness proof).
    kinds_in_order = [n.kind for n in cpg.nodes]
    assert kinds_in_order[:2] == ["METHOD", "METHOD_RETURN"]  # n24, n25
    assert cpg.nodes[0].resolved_fqn == "helpers.py:<module>.noop"
    assert cpg.nodes[0].enclosing_decl_fqn == "helpers.py:<module>.noop"
    assert cpg.nodes[0].structural_path == ""
    assert cpg.nodes[1].enclosing_decl_fqn == "helpers.py:<module>.noop"
    assert cpg.nodes[1].structural_path == "0"

    by_kind_fqn = {(n.kind, n.resolved_fqn) for n in cpg.nodes}
    assert ("METHOD", "sqli.py:<module>.get_user") in by_kind_fqn

    # Locate the get_user METHOD node and the tainted `username` IDENTIFIER
    # use inside the f-string by their unique (kind, operator_or_literal) /
    # (kind, resolved_fqn) shape rather than by raw id (the mapper does not
    # expose raw ids at all -- proving the public CPGNode surface is enough).
    get_user = next(
        n for n in cpg.nodes if n.kind == "METHOD" and n.resolved_fqn == "sqli.py:<module>.get_user"
    )
    assert get_user.enclosing_decl_fqn == "sqli.py:<module>.get_user"
    assert get_user.structural_path == ""

    username_uses = [
        n
        for n in cpg.nodes
        if n.kind == "IDENTIFIER"
        and n.enclosing_decl_fqn == "sqli.py:<module>.get_user"
        and n.structural_path == "1.4.1.1"
    ]
    assert len(username_uses) == 1
    username_use = username_uses[0]
    assert username_use.resolved_fqn == ""  # IDENTIFIER nodes never carry a resolved_fqn
    assert username_use.operator_or_literal == ""  # not a LITERAL/operator CALL

    # CALL node resolved_fqn (methodFullName) vs operator CALL (no methodFullName).
    connect_call = next(n for n in cpg.nodes if n.resolved_fqn == "sqlite3.py:sqlite3.connect")
    assert connect_call.kind == "CALL"
    assert connect_call.operator_or_literal == ""

    assignment_calls = [n for n in cpg.nodes if n.operator_or_literal == "<operator>.assignment"]
    assert len(assignment_calls) == 2  # con = ...; cur = ...
    assert all(n.resolved_fqn == "" for n in assignment_calls)

    literal_nodes = [n for n in cpg.nodes if n.kind == "LITERAL"]
    assert {n.operator_or_literal for n in literal_nodes} == {
        '"db.sqlite3"',
        '"SELECT * FROM USERS WHERE USERNAME=\'"',
        '"\'"',
    }

    # Edge-kind collapsing (CLAR-SNAP-05 vocabulary): AST/CFG direct,
    # CDG+REACHING_DEF -> PDG.
    kind_counts: dict[str, int] = {}
    for e in cpg.edges:
        kind_counts[e.kind] = kind_counts.get(e.kind, 0) + 1
    assert kind_counts == {"AST": 24, "CFG": 6, "PDG": 8}


@pytest.mark.unit
def test_mapper_deterministic_across_repeated_parse() -> None:
    """Parsing the SAME fixture bytes twice yields byte-identical CPG.nodes/edges.

    A pure-function control: the mapper must not depend on wall-clock, set/
    dict hash randomization, or any other hidden non-determinism.
    """
    export_copy_1: dict[str, Any] = json.loads(json.dumps(SQLI_JOERN_EXPORT_FIXTURE))
    export_copy_2: dict[str, Any] = json.loads(json.dumps(SQLI_JOERN_EXPORT_FIXTURE))

    cpg1 = map_export(export_copy_1)
    cpg2 = map_export(export_copy_2)

    assert cpg1.nodes == cpg2.nodes
    assert cpg1.edges == cpg2.edges

    result1 = canonical_order(cpg1)
    result2 = canonical_order(cpg2)
    assert result1.cpg_order_hash == result2.cpg_order_hash
    assert result1.fingerprint_class == result2.fingerprint_class


@pytest.mark.unit
def test_mapper_order_independent_of_raw_export_array_order() -> None:
    """MUTATION-TARGETED anti-vacuity control (module docstring).

    ``shuffled_export`` reverses both the raw ``nodes`` and ``edges`` arrays —
    same semantic graph, different raw order (the exact class of instability
    a real Joern run's threaded/overlay parsing could introduce across
    re-runs, per the plan's Provenance section). The mapper's OWN
    deterministic emission order must make this a no-op on the final ``CPG``:
    a mapper that instead trusted ``export["nodes"]``'s raw array position
    would FAIL this test (while still passing the repeated-parse-of-the-
    SAME-bytes test above), which is exactly why both controls are present.
    """
    shuffled = shuffled_export(SQLI_JOERN_EXPORT_FIXTURE)
    assert shuffled["nodes"] != SQLI_JOERN_EXPORT_FIXTURE["nodes"]  # sanity: genuinely reordered
    assert shuffled["edges"] != SQLI_JOERN_EXPORT_FIXTURE["edges"]

    cpg_original = map_export(SQLI_JOERN_EXPORT_FIXTURE)
    cpg_shuffled = map_export(shuffled)

    assert cpg_original.nodes == cpg_shuffled.nodes
    assert cpg_original.edges == cpg_shuffled.edges

    result_original = canonical_order(cpg_original)
    result_shuffled = canonical_order(cpg_shuffled)
    assert result_original.cpg_order_hash == result_shuffled.cpg_order_hash


@pytest.mark.unit
def test_mapper_unknown_edge_kind_is_fail_closed() -> None:
    """A raw edge kind outside the CLAR-SNAP-05 vocabulary is refused, not dropped."""
    bad_export = {
        "nodes": [
            {"id": "a", "label": "METHOD", "fullName": "x", "filename": "f.py", "lineNumber": 1},
            {"id": "b", "label": "BLOCK", "filename": "f.py", "lineNumber": 1},
        ],
        "edges": [{"src": "a", "dst": "b", "kind": "DDG"}],  # not in EDGE_KIND_MAP
    }
    with pytest.raises(UnknownEdgeKindError):
        map_export(bad_export)


@pytest.mark.unit
def test_mapper_dangling_ast_edge_reference_is_fail_closed() -> None:
    """An AST edge pointing at a node id absent from ``"nodes"`` is refused."""
    bad_export = {
        "nodes": [{"id": "a", "label": "METHOD", "fullName": "x", "filename": "f.py"}],
        "edges": [{"src": "a", "dst": "missing", "kind": "AST"}],
    }
    with pytest.raises(UnknownNodeReferenceError):
        map_export(bad_export)


@pytest.mark.unit
def test_mapper_dangling_non_ast_edge_reference_is_fail_closed() -> None:
    """A non-AST edge (CFG here) pointing at a missing node id is also refused."""
    bad_export = {
        "nodes": [{"id": "a", "label": "METHOD", "fullName": "x", "filename": "f.py"}],
        "edges": [{"src": "a", "dst": "missing", "kind": "CFG"}],
    }
    with pytest.raises(UnknownNodeReferenceError):
        map_export(bad_export)


# ---------------------------------------------------------------------------
# joern_frontend.py
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_parse_source_secure_run_call_shape(tmp_path: Path) -> None:
    """``parse_source`` issues exactly two allowlisted ``secure_run`` calls
    (parse then CLAR-SNAP-05 export) and correctly threads the export env vars.

    Monkeypatches the underlying spawn exactly like
    ``tests/unit/test_snap_specs.py:541-573`` — no real ``joern`` binary is
    invoked or required.
    """
    import tools.worker.secure_subprocess as ss

    calls: list[dict[str, Any]] = []

    def _fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        calls.append({"cmd": cmd, "kwargs": kwargs})
        env = kwargs.get("env", {})
        # Mimic the real export script: on the export-phase call, write the
        # export JSON to the path threaded via the env var contract.
        if jf.ENV_EXPORT_JSON_PATH in env:
            Path(env[jf.ENV_EXPORT_JSON_PATH]).write_text(
                json.dumps(SQLI_JOERN_EXPORT_FIXTURE), encoding="utf-8"
            )
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    orig = ss.subprocess.run
    ss.subprocess.run = _fake_run  # type: ignore[assignment]
    try:
        cpg = jf.parse_source(
            tmp_path / "src",
            "python",
            env={"PATH": "/opt/joern/bin"},
            workdir=tmp_path / "work",
        )
    finally:
        ss.subprocess.run = orig  # type: ignore[assignment]

    assert len(calls) == 2

    parse_call, export_call = calls
    # --- Phase 1: parse (pinned binary, allowlisted flags, shell=False). ---
    assert parse_call["cmd"][0] == "/opt/joern/bin/joern"
    assert "--language" in parse_call["cmd"] and "python" in parse_call["cmd"]
    assert "--cpg-only" in parse_call["cmd"]
    assert parse_call["kwargs"]["shell"] is False

    # --- Phase 2: export (fixed in-image script path, env-threaded params). ---
    assert export_call["cmd"] == ["/opt/joern/bin/joern", "--script", jf.EXPORT_SCRIPT_PATH]
    assert export_call["kwargs"]["shell"] is False
    export_env = export_call["kwargs"]["env"]
    assert jf.ENV_CPG_BIN_PATH in export_env
    assert jf.ENV_EXPORT_JSON_PATH in export_env
    # The cpg.bin path threaded into the export env matches the --output path
    # given to the parse phase (the two phases share the same intermediate file).
    output_flag_index = parse_call["cmd"].index("--output")
    assert export_env[jf.ENV_CPG_BIN_PATH] == parse_call["cmd"][output_flag_index + 1]

    # --- The mapped result matches mapping the fixture directly. ---
    assert cpg.nodes == map_export(SQLI_JOERN_EXPORT_FIXTURE).nodes
    assert cpg.edges == map_export(SQLI_JOERN_EXPORT_FIXTURE).edges


@pytest.mark.unit
def test_parse_source_missing_export_json_is_fail_closed(tmp_path: Path) -> None:
    """If the export phase reports success but writes no JSON, refuse fail-closed."""
    import tools.worker.secure_subprocess as ss

    def _fake_run_no_export(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        # Never writes the export JSON file, unlike the happy-path fake above.
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    orig = ss.subprocess.run
    ss.subprocess.run = _fake_run_no_export  # type: ignore[assignment]
    try:
        with pytest.raises(jf.JoernExportMissingError):
            jf.parse_source(
                tmp_path / "src",
                "python",
                env={"PATH": "/opt/joern/bin"},
                workdir=tmp_path / "work",
            )
    finally:
        ss.subprocess.run = orig  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# graph_views.py / decl_reparser.py -- honest Wave-2 stubs
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_build_graph_view_is_an_honest_stub() -> None:
    """Wave-2 stub: raises rather than returning a fake/empty GraphView."""
    cpg = map_export(SQLI_JOERN_EXPORT_FIXTURE)
    with pytest.raises(NotImplementedError, match="Wave-2"):
        graph_views.build_graph_view(cpg)


@pytest.mark.unit
def test_joern_decl_reparser_satisfies_protocol_but_is_an_honest_stub(tmp_path: Path) -> None:
    """``JoernDeclReparser`` structurally satisfies ``DeclReparser`` (a
    ``@runtime_checkable`` Protocol) but its body is a Wave-2 stub."""
    reparser = decl_reparser_mod.JoernDeclReparser(
        src_root=tmp_path / "src", language="python", env={}, workdir=tmp_path / "work"
    )
    assert isinstance(reparser, DeclReparser)

    with pytest.raises(NotImplementedError, match="Wave-2"):
        reparser.reparse("sqli.py:<module>.get_user", fresh_id_base=1000)
