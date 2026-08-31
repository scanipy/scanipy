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
  - ``map_export_with_locations`` — the ``file:line`` -> ``NodeId`` side-table
    (Tier-2 track A). Its anti-vacuity controls are (a) a byte-level GOLDEN
    regression proving ``map_export``'s output did not move when the shared
    walk was extracted, and (b) an INV-5 guard proving no location field ever
    reached ``CPGNode`` / the ``cpg_order_hash`` (the whole refactor-invariance
    claim rests on locations staying OUT of the hashed surface).
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
from pathlib import Path
from typing import Any, Final

import pytest

from analysis.cpg_delta import DeclReparser
from analysis.cpg_ingest import decl_reparser as decl_reparser_mod
from analysis.cpg_ingest import graph_views
from analysis.cpg_ingest import joern_frontend as jf
from analysis.cpg_ingest.mapper import (
    SourceLocation,
    UnknownEdgeKindError,
    UnknownNodeReferenceError,
    map_export,
    map_export_with_locations,
)
from analysis.ordering import CPGNode, canonical_order
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
# mapper.py -- location side-table (Tier-2 track A)
# ---------------------------------------------------------------------------
#
# GOLDEN SNAPSHOT of ``map_export(SQLI_JOERN_EXPORT_FIXTURE)``, captured by
# running the PRE-CHANGE mapper (commit 46cf572, before
# ``map_export_with_locations`` existed) and serialising every CPGNode /
# CPGEdge field. ``map_export`` was then refactored into a thin wrapper over
# the shared walk; this snapshot is the evidence that the refactor was
# behaviour-preserving down to node ids, emission order, field derivation and
# edge order. Regenerating it to make a failure go away defeats its purpose: a
# diff here means ``map_export``'s contract moved, which would ripple into
# ``cpg_order_hash`` and the CMP-CP-05 byte-identical-SARIF guarantee.
_GOLDEN_NODES: Final[list[tuple[int, str, str, str, str, str]]] = [
    (0, "METHOD", "", "helpers.py:<module>.noop", "helpers.py:<module>.noop", ""),
    (1, "METHOD_RETURN", "", "", "helpers.py:<module>.noop", "0"),
    (2, "METHOD", "", "sqli.py:<module>.get_user", "sqli.py:<module>.get_user", ""),
    (3, "METHOD_PARAMETER_IN", "", "", "sqli.py:<module>.get_user", "0"),
    (4, "BLOCK", "", "", "sqli.py:<module>.get_user", "1"),
    (5, "LOCAL", "", "", "sqli.py:<module>.get_user", "1.0"),
    (6, "CALL", "<operator>.assignment", "", "sqli.py:<module>.get_user", "1.1"),
    (7, "IDENTIFIER", "", "", "sqli.py:<module>.get_user", "1.1.0"),
    (8, "CALL", "", "sqlite3.py:sqlite3.connect", "sqli.py:<module>.get_user", "1.1.1"),
    (9, "IDENTIFIER", "", "", "sqli.py:<module>.get_user", "1.1.1.0"),
    (10, "LITERAL", '"db.sqlite3"', "", "sqli.py:<module>.get_user", "1.1.1.1"),
    (11, "LOCAL", "", "", "sqli.py:<module>.get_user", "1.2"),
    (12, "CALL", "<operator>.assignment", "", "sqli.py:<module>.get_user", "1.3"),
    (13, "IDENTIFIER", "", "", "sqli.py:<module>.get_user", "1.3.0"),
    (
        14,
        "CALL",
        "",
        "sqlite3.py:sqlite3.Connection.cursor",
        "sqli.py:<module>.get_user",
        "1.3.1",
    ),
    (15, "IDENTIFIER", "", "", "sqli.py:<module>.get_user", "1.3.1.0"),
    (16, "CALL", "", "sqlite3.py:sqlite3.Cursor.execute", "sqli.py:<module>.get_user", "1.4"),
    (17, "IDENTIFIER", "", "", "sqli.py:<module>.get_user", "1.4.0"),
    (18, "CALL", "<operator>.formatString", "", "sqli.py:<module>.get_user", "1.4.1"),
    (
        19,
        "LITERAL",
        '"SELECT * FROM USERS WHERE USERNAME=\'"',
        "",
        "sqli.py:<module>.get_user",
        "1.4.1.0",
    ),
    (20, "IDENTIFIER", "", "", "sqli.py:<module>.get_user", "1.4.1.1"),
    (21, "LITERAL", '"\'"', "", "sqli.py:<module>.get_user", "1.4.1.2"),
    (22, "RETURN", "", "", "sqli.py:<module>.get_user", "1.5"),
    (23, "CALL", "", "sqlite3.py:sqlite3.Cursor.fetchone", "sqli.py:<module>.get_user", "1.5.0"),
    (24, "IDENTIFIER", "", "", "sqli.py:<module>.get_user", "1.5.0.0"),
    (25, "METHOD_RETURN", "", "", "sqli.py:<module>.get_user", "2"),
]

_GOLDEN_EDGES: Final[list[tuple[int, int, str]]] = [
    (0, 1, "AST"),
    (2, 3, "AST"),
    (2, 4, "AST"),
    (2, 25, "AST"),
    (4, 5, "AST"),
    (4, 6, "AST"),
    (4, 11, "AST"),
    (4, 12, "AST"),
    (4, 16, "AST"),
    (4, 22, "AST"),
    (6, 7, "AST"),
    (6, 8, "AST"),
    (8, 9, "AST"),
    (8, 10, "AST"),
    (12, 13, "AST"),
    (12, 14, "AST"),
    (14, 15, "AST"),
    (16, 17, "AST"),
    (16, 18, "AST"),
    (18, 19, "AST"),
    (18, 20, "AST"),
    (18, 21, "AST"),
    (22, 23, "AST"),
    (23, 24, "AST"),
    (0, 1, "CFG"),
    (2, 6, "CFG"),
    (6, 12, "CFG"),
    (12, 16, "CFG"),
    (16, 22, "CFG"),
    (22, 25, "CFG"),
    (2, 6, "PDG"),
    (2, 12, "PDG"),
    (2, 16, "PDG"),
    (2, 22, "PDG"),
    (3, 20, "PDG"),
    (7, 15, "PDG"),
    (13, 17, "PDG"),
    (13, 24, "PDG"),
]

# A minimal export that the SQLI fixture structurally CANNOT express: its
# ``_node`` helper always stamps ``filename``/``lineNumber``/``columnNumber`` on
# every node, so nothing in it has an absent filename or an absent line/col.
# Here the BLOCK child carries neither, so it must (a) inherit ``"app.py"`` from
# its METHOD AST ancestor and (b) report the documented ``0`` unknown-sentinel.
_INHERITANCE_EXPORT: Final[dict[str, Any]] = {
    "nodes": [
        {
            "id": "m",
            "label": "METHOD",
            "fullName": "app.py:<module>.handler",
            "filename": "app.py",
            "lineNumber": 12,
            "columnNumber": 3,
        },
        {"id": "b", "label": "BLOCK"},  # no filename, no lineNumber/columnNumber
    ],
    "edges": [{"src": "m", "dst": "b", "kind": "AST"}],
}


@pytest.mark.unit
def test_map_export_output_is_unchanged_by_the_side_table_refactor() -> None:
    """REGRESSION: ``map_export`` still returns exactly what it returned pre-change.

    Field-for-field against the golden snapshot captured from the pre-refactor
    implementation (see the ``_GOLDEN_*`` comment above) — node ids, emission
    order, every derived ``CPGNode`` field, and the full re-sorted edge list.
    This is the backward-compatibility contract: ``map_export_with_locations``
    was added *alongside* ``map_export``; it did not redefine it.
    """
    cpg = map_export(SQLI_JOERN_EXPORT_FIXTURE)

    assert [
        (
            n.node_id,
            n.kind,
            n.operator_or_literal,
            n.resolved_fqn,
            n.enclosing_decl_fqn,
            n.structural_path,
        )
        for n in cpg.nodes
    ] == _GOLDEN_NODES
    assert [(e.src, e.dst, e.kind) for e in cpg.edges] == _GOLDEN_EDGES


@pytest.mark.unit
def test_map_export_with_locations_returns_the_identical_cpg() -> None:
    """The contract sentence, asserted literally: "Identical CPG to map_export()"."""
    cpg_plain = map_export(SQLI_JOERN_EXPORT_FIXTURE)
    cpg_with_locs, _locations = map_export_with_locations(SQLI_JOERN_EXPORT_FIXTURE)

    assert cpg_with_locs.nodes == cpg_plain.nodes
    assert cpg_with_locs.edges == cpg_plain.edges


@pytest.mark.unit
def test_location_side_table_is_keyed_by_the_cpg_node_ids() -> None:
    """Every ``NodeId`` the CPG assigned — and no other key — is in the side-table.

    This is the property that makes the table usable as a lookup at all: a
    caller resolving ``file:line`` -> ``NodeId`` must land on ids that actually
    index into ``cpg.nodes``.
    """
    cpg, locations = map_export_with_locations(SQLI_JOERN_EXPORT_FIXTURE)

    assert set(locations) == {n.node_id for n in cpg.nodes}
    assert len(locations) == 26
    # Keys index into cpg.nodes positionally (CPG.add_node assigns 0..n-1).
    for node in cpg.nodes:
        assert cpg.nodes[node.node_id] is node


@pytest.mark.unit
def test_location_side_table_maps_known_fixture_nodes_to_their_file_and_line() -> None:
    """Spot-checks against the fixture's own documented source coordinates."""
    cpg, locations = map_export_with_locations(SQLI_JOERN_EXPORT_FIXTURE)

    # cpg.nodes[0] is helpers.py's `noop` METHOD (filename is the primary sort
    # key, so the whole helpers.py subtree sorts first) — fixture n24, line 1.
    assert cpg.nodes[0].resolved_fqn == "helpers.py:<module>.noop"
    assert locations[cpg.nodes[0].node_id] == SourceLocation(
        filename="helpers.py", line=1, column=1
    )
    # ...and its METHOD_RETURN — fixture n25, line 2.
    assert locations[cpg.nodes[1].node_id] == SourceLocation(
        filename="helpers.py", line=2, column=1
    )

    # The tainted `username` IDENTIFIER inside the f-string — fixture n18,
    # sqli.py line 6 col 54. Located by its structural path (the mapper does
    # not expose raw ids), exactly as the field-derivation test above does.
    username_use = next(
        n
        for n in cpg.nodes
        if n.kind == "IDENTIFIER"
        and n.enclosing_decl_fqn == "sqli.py:<module>.get_user"
        and n.structural_path == "1.4.1.1"
    )
    assert locations[username_use.node_id] == SourceLocation(filename="sqli.py", line=6, column=54)

    # The `cur.execute(...)` sink CALL — fixture n14, sqli.py line 6 col 5.
    execute_call = next(
        n for n in cpg.nodes if n.resolved_fqn == "sqlite3.py:sqlite3.Cursor.execute"
    )
    assert locations[execute_call.node_id] == SourceLocation(filename="sqli.py", line=6, column=5)

    # Every node reports one of the fixture's two files; none is left blank.
    assert {loc.filename for loc in locations.values()} == {"sqli.py", "helpers.py"}


@pytest.mark.unit
def test_location_side_table_inherits_filename_and_zeroes_unknown_line_col() -> None:
    """Inherited-filename + ``0``-sentinel behaviour, on an export the SQLI
    fixture structurally cannot express (see ``_INHERITANCE_EXPORT``)."""
    cpg, locations = map_export_with_locations(_INHERITANCE_EXPORT)

    assert len(cpg.nodes) == 2
    method = next(n for n in cpg.nodes if n.kind == "METHOD")
    block = next(n for n in cpg.nodes if n.kind == "BLOCK")

    assert locations[method.node_id] == SourceLocation(filename="app.py", line=12, column=3)
    # The BLOCK carries NO filename of its own: it inherits its METHOD AST
    # ancestor's, exactly as the mapper's ordering walk already resolved it.
    # Its absent lineNumber/columnNumber become the documented `0` sentinel
    # (NOT `None`, and never a guessed real position).
    assert locations[block.node_id] == SourceLocation(filename="app.py", line=0, column=0)


@pytest.mark.unit
def test_location_side_table_is_independent_of_raw_export_array_order() -> None:
    """ANTI-VACUITY: reversing both raw arrays leaves the side-table identical.

    The side-table is keyed by NodeIds the mapper assigns from its OWN
    deterministic emission order, so a ``file:line`` lookup performed against
    two runs of a threaded/overlay Joern parse must agree — the same obligation
    ``test_mapper_order_independent_of_raw_export_array_order`` discharges for
    the graph itself.
    """
    shuffled = shuffled_export(SQLI_JOERN_EXPORT_FIXTURE)
    assert shuffled["nodes"] != SQLI_JOERN_EXPORT_FIXTURE["nodes"]  # sanity

    _cpg_original, locations_original = map_export_with_locations(SQLI_JOERN_EXPORT_FIXTURE)
    _cpg_shuffled, locations_shuffled = map_export_with_locations(shuffled)

    assert locations_original == locations_shuffled


@pytest.mark.unit
def test_source_locations_never_leak_into_the_hashed_cpg_surface() -> None:
    """INV-5 / refactor-invariance GUARD — the load-bearing anti-faking control.

    A finding's identity is the canonical form of its dependence slice, NOT its
    source position: renaming a file or inserting lines above a sink must not
    change ``cpg_order_hash`` (and hence ``slice_fingerprint``). That only holds
    while location data stays strictly in the side-table. This test fails the
    moment anyone adds a filename/line/column field to ``CPGNode`` or lets one
    reach the hashed surface.
    """
    # 1. `CPGNode` has no location-shaped field at all.
    cpg_node_fields = {f.name for f in dataclasses.fields(CPGNode)}
    assert cpg_node_fields == {
        "node_id",
        "kind",
        "operator_or_literal",
        "resolved_fqn",
        "enclosing_decl_fqn",
        "structural_path",
    }

    # 2. Relocating EVERY node to a different file, line and column — with the
    #    AST shape, sibling order and all semantic fields preserved — leaves
    #    both the derived CPGNode fields and the `cpg_order_hash` untouched.
    #    That is the refactor-invariance claim itself, executed: same program,
    #    relocated source.
    cpg, locations = map_export_with_locations(SQLI_JOERN_EXPORT_FIXTURE)

    relocated: dict[str, Any] = json.loads(json.dumps(SQLI_JOERN_EXPORT_FIXTURE))
    for raw in relocated["nodes"]:
        raw["filename"] = "renamed/" + str(raw["filename"])
        raw["lineNumber"] = int(raw["lineNumber"]) + 500
        raw["columnNumber"] = int(raw["columnNumber"]) + 7

    cpg_relocated, locations_relocated = map_export_with_locations(relocated)

    def _hashed_fields(node: Any) -> tuple[str, str, str, str, str]:
        return (
            node.kind,
            node.operator_or_literal,
            node.resolved_fqn,
            node.enclosing_decl_fqn,
            node.structural_path,
        )

    assert [_hashed_fields(n) for n in cpg_relocated.nodes] == [
        _hashed_fields(n) for n in cpg.nodes
    ]
    assert cpg_relocated.edges == cpg.edges
    assert canonical_order(cpg_relocated).cpg_order_hash == canonical_order(cpg).cpg_order_hash

    # 3. ...while the SIDE-TABLE — the only place locations live — DID move.
    #    (Anti-vacuity for step 2: proves the relocation was real, not a no-op.)
    assert locations_relocated != locations
    assert locations_relocated[cpg.nodes[0].node_id] == SourceLocation(
        filename="renamed/helpers.py", line=501, column=8
    )


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
    # --- Phase 1: parse (headless joern-parse — validated against real joern
    # v4.0.554: the main `joern` launcher has no --output/--cpg-only, and the
    # Scanipy language id "python" must map to joern's "pythonsrc" frontend
    # name (bare "python" selects the unbundled legacy py2cpg.sh generator). ---
    assert parse_call["cmd"][0] == "/opt/joern/joern-parse"
    assert "--language" in parse_call["cmd"] and "pythonsrc" in parse_call["cmd"]
    assert "python" not in parse_call["cmd"]  # the UNMAPPED id must never pass through
    assert "--cpg-only" not in parse_call["cmd"]
    # The source root rides as the trailing POSITIONAL argument.
    assert parse_call["cmd"][-1] == str(tmp_path / "src")
    assert parse_call["kwargs"]["shell"] is False
    # Both phases receive a writable HOME (defaulted to the workdir) — the JVM
    # + joern console need one; without it the script phase dies opaquely.
    assert parse_call["kwargs"]["env"]["HOME"] == str(tmp_path / "work")

    # --- Phase 2: export (fixed in-image script path, env-threaded params). ---
    assert export_call["cmd"] == ["/opt/joern/joern", "--script", jf.EXPORT_SCRIPT_PATH]
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
