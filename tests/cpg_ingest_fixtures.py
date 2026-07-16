"""Hermetic synthetic Joern-export-JSON fixture for CMP-SNAP-05 CPG-ingest tests.

**UNVERIFIED AGAINST A REAL JOERN INSTALL.** No ``joern`` binary exists in this
build sandbox (see ``analysis/cpg_ingest/mapper.py`` / ``joern_frontend.py``
module docstrings and ``workers/snapshot/joern-scripts/export_cpg.sc``'s own
header). This module hand-constructs a PLAUSIBLE export matching
:class:`analysis.cpg_ingest.mapper.RawJoernExport`'s documented schema, based
on Joern's well-known CPG shape (``.label``/``.code``/``.name``/
``.methodFullName``/``.fullName`` node properties; ``AST``/``CFG``/``CDG``/
``REACHING_DEF`` edge kinds). It is intentionally diffable: once a real
``joern --script export_cpg.sc`` run exists (plan "Wave 4 — local rehearsal"),
running it over the exact two-file snippet documented below and diffing the
real output against :data:`SQLI_FIXTURE_SOURCE_PYTHON` /
:data:`HELPERS_FIXTURE_SOURCE_PYTHON`'s hand-built node/edge shape is the
intended validation step.

## The source the fixture models

Two tiny Python files, chosen to resemble the plan's actual Wave-5 scan
target (``michealkeines/Vulnerable-API``'s ``sqli.py`` — a textbook
unparameterized SQL injection via an f-string) without depending on that repo
being fetchable in this sandbox:

``sqli.py`` (lines 1-8, 1-indexed to match the fixture's ``lineNumber`` values;
line 1-2 = imports, omitted from the fixture's node set for brevity — only the
``get_user`` method body is modelled):

    def get_user(username):              # line 3
        con = sqlite3.connect("db.sqlite3")     # line 4
        cur = con.cursor()                       # line 5
        cur.execute(f"SELECT * FROM USERS WHERE USERNAME='{username}'")  # line 6
        return cur.fetchone()                    # line 7

``helpers.py`` (a second, unrelated file — included specifically to exercise
the mapper's ``filename``-first sort key across files):

    def noop():   # line 1
        pass

## Fixture assumptions (mirrors ``mapper.py``'s "Documented schema assumptions")

* Node ids are the JSON strings ``"n00"``..``"n25"`` (zero-padded so
  lexicographic string comparison agrees with numeric comparison — a fixture
  authoring convenience; real Joern ids are large ``Long``s, always consumed
  as opaque strings by :func:`analysis.cpg_ingest.mapper.map_export`).
* ``METHOD_RETURN`` nodes are placed one line past their method's body — a
  fixture simplification (real Joern's exact synthetic-node line/col
  convention is one of the things a real-Joern diff should confirm).
* ``CDG`` edges here (method-entry -> each top-level statement) are
  ILLUSTRATIVE, not a claim about real Joern's control-dependence semantics
  for unconditional straight-line code — they exist purely so this fixture
  exercises the CDG-collapses-to-PDG mapping rule.
"""

from __future__ import annotations

import copy
from typing import Any, Final

# Human-readable source the fixture models (not parsed — see module docstring).
SQLI_FIXTURE_SOURCE_PYTHON: Final[str] = (
    "def get_user(username):\n"
    '    con = sqlite3.connect("db.sqlite3")\n'
    "    cur = con.cursor()\n"
    "    cur.execute(f\"SELECT * FROM USERS WHERE USERNAME='{username}'\")\n"
    "    return cur.fetchone()\n"
)
HELPERS_FIXTURE_SOURCE_PYTHON: Final[str] = "def noop():\n    pass\n"


def _node(
    node_id: str,
    label: str,
    *,
    filename: str,
    line: int,
    col: int,
    code: str = "",
    name: str = "",
    method_full_name: str = "",
    full_name: str = "",
) -> dict[str, Any]:
    """Build one raw node dict, omitting empty optional fields (mirrors the
    export script's own "omit rather than emit empty" contract)."""
    node: dict[str, Any] = {
        "id": node_id,
        "label": label,
        "filename": filename,
        "lineNumber": line,
        "columnNumber": col,
    }
    if code:
        node["code"] = code
    if name:
        node["name"] = name
    if method_full_name:
        node["methodFullName"] = method_full_name
    if full_name:
        node["fullName"] = full_name
    return node


def _edge(src: str, dst: str, kind: str) -> dict[str, str]:
    return {"src": src, "dst": dst, "kind": kind}


_SQLI = "sqli.py"
_HELPERS = "helpers.py"

_NODES: Final[list[dict[str, Any]]] = [
    _node("n00", "METHOD", filename=_SQLI, line=3, col=1, full_name="sqli.py:<module>.get_user"),
    _node(
        "n01",
        "METHOD_PARAMETER_IN",
        filename=_SQLI,
        line=3,
        col=16,
        code="username",
        name="username",
    ),
    _node("n02", "BLOCK", filename=_SQLI, line=3, col=27),
    _node("n03", "LOCAL", filename=_SQLI, line=4, col=5, code="con", name="con"),
    _node(
        "n04",
        "CALL",
        filename=_SQLI,
        line=4,
        col=5,
        code='con = sqlite3.connect("db.sqlite3")',
        name="<operator>.assignment",
    ),
    _node("n05", "IDENTIFIER", filename=_SQLI, line=4, col=5, code="con", name="con"),
    _node(
        "n06",
        "CALL",
        filename=_SQLI,
        line=4,
        col=11,
        code='sqlite3.connect("db.sqlite3")',
        name="connect",
        method_full_name="sqlite3.py:sqlite3.connect",
    ),
    _node("n07", "IDENTIFIER", filename=_SQLI, line=4, col=11, code="sqlite3", name="sqlite3"),
    _node("n08", "LITERAL", filename=_SQLI, line=4, col=27, code='"db.sqlite3"'),
    _node("n09", "LOCAL", filename=_SQLI, line=5, col=5, code="cur", name="cur"),
    _node(
        "n10",
        "CALL",
        filename=_SQLI,
        line=5,
        col=5,
        code="cur = con.cursor()",
        name="<operator>.assignment",
    ),
    _node("n11", "IDENTIFIER", filename=_SQLI, line=5, col=5, code="cur", name="cur"),
    _node(
        "n12",
        "CALL",
        filename=_SQLI,
        line=5,
        col=11,
        code="con.cursor()",
        name="cursor",
        method_full_name="sqlite3.py:sqlite3.Connection.cursor",
    ),
    _node("n13", "IDENTIFIER", filename=_SQLI, line=5, col=11, code="con", name="con"),
    _node(
        "n14",
        "CALL",
        filename=_SQLI,
        line=6,
        col=5,
        code="cur.execute(f\"SELECT * FROM USERS WHERE USERNAME='{username}'\")",
        name="execute",
        method_full_name="sqlite3.py:sqlite3.Cursor.execute",
    ),
    _node("n15", "IDENTIFIER", filename=_SQLI, line=6, col=5, code="cur", name="cur"),
    _node(
        "n16",
        "CALL",
        filename=_SQLI,
        line=6,
        col=17,
        code="f\"SELECT * FROM USERS WHERE USERNAME='{username}'\"",
        name="<operator>.formatString",
    ),
    _node(
        "n17",
        "LITERAL",
        filename=_SQLI,
        line=6,
        col=17,
        code='"SELECT * FROM USERS WHERE USERNAME=\'"',
    ),
    _node("n18", "IDENTIFIER", filename=_SQLI, line=6, col=54, code="username", name="username"),
    _node("n19", "LITERAL", filename=_SQLI, line=6, col=63, code='"\'"'),
    _node("n20", "RETURN", filename=_SQLI, line=7, col=5, code="return cur.fetchone()"),
    _node(
        "n21",
        "CALL",
        filename=_SQLI,
        line=7,
        col=12,
        code="cur.fetchone()",
        name="fetchone",
        method_full_name="sqlite3.py:sqlite3.Cursor.fetchone",
    ),
    _node("n22", "IDENTIFIER", filename=_SQLI, line=7, col=12, code="cur", name="cur"),
    _node("n23", "METHOD_RETURN", filename=_SQLI, line=8, col=1, code="RET"),
    _node("n24", "METHOD", filename=_HELPERS, line=1, col=1, full_name="helpers.py:<module>.noop"),
    _node("n25", "METHOD_RETURN", filename=_HELPERS, line=2, col=1, code="RET"),
]

_AST_EDGES: Final[list[dict[str, str]]] = [
    _edge("n00", "n01", "AST"),
    _edge("n00", "n02", "AST"),
    _edge("n00", "n23", "AST"),
    _edge("n02", "n03", "AST"),
    _edge("n02", "n04", "AST"),
    _edge("n02", "n09", "AST"),
    _edge("n02", "n10", "AST"),
    _edge("n02", "n14", "AST"),
    _edge("n02", "n20", "AST"),
    _edge("n04", "n05", "AST"),
    _edge("n04", "n06", "AST"),
    _edge("n06", "n07", "AST"),
    _edge("n06", "n08", "AST"),
    _edge("n10", "n11", "AST"),
    _edge("n10", "n12", "AST"),
    _edge("n12", "n13", "AST"),
    _edge("n14", "n15", "AST"),
    _edge("n14", "n16", "AST"),
    _edge("n16", "n17", "AST"),
    _edge("n16", "n18", "AST"),
    _edge("n16", "n19", "AST"),
    _edge("n20", "n21", "AST"),
    _edge("n21", "n22", "AST"),
    _edge("n24", "n25", "AST"),
]

_CFG_EDGES: Final[list[dict[str, str]]] = [
    _edge("n00", "n04", "CFG"),
    _edge("n04", "n10", "CFG"),
    _edge("n10", "n14", "CFG"),
    _edge("n14", "n20", "CFG"),
    _edge("n20", "n23", "CFG"),
    _edge("n24", "n25", "CFG"),
]

# Illustrative only (module docstring "Fixture assumptions").
_CDG_EDGES: Final[list[dict[str, str]]] = [
    _edge("n00", "n04", "CDG"),
    _edge("n00", "n10", "CDG"),
    _edge("n00", "n14", "CDG"),
    _edge("n00", "n20", "CDG"),
]

_REACHING_DEF_EDGES: Final[list[dict[str, str]]] = [
    _edge("n01", "n18", "REACHING_DEF"),  # username param -> use in the f-string (taint edge)
    _edge("n05", "n13", "REACHING_DEF"),  # con def -> con receiver use
    _edge("n11", "n15", "REACHING_DEF"),  # cur def -> cur receiver use (execute)
    _edge("n11", "n22", "REACHING_DEF"),  # cur def -> cur receiver use (fetchone)
]

_EDGES: Final[list[dict[str, str]]] = [
    *_AST_EDGES,
    *_CFG_EDGES,
    *_CDG_EDGES,
    *_REACHING_DEF_EDGES,
]

# The canonical fixture object — see module docstring for provenance/assumptions.
SQLI_JOERN_EXPORT_FIXTURE: Final[dict[str, Any]] = {
    "_meta": {
        "assumptions": (
            "Hand-constructed, unverified against a real Joern install — see "
            "this module's docstring."
        ),
        "models": [SQLI_FIXTURE_SOURCE_PYTHON, HELPERS_FIXTURE_SOURCE_PYTHON],
    },
    "nodes": _NODES,
    "edges": _EDGES,
}


def shuffled_export(export: dict[str, Any]) -> dict[str, Any]:
    """A deep copy of ``export`` with ``nodes``/``edges`` array order reversed.

    Same semantic graph, different raw array order — the direct
    operationalisation of the mapper's core requirement (module docstring of
    ``analysis.cpg_ingest.mapper``): "never trust whatever order Joern's
    export array happens to produce". :func:`analysis.cpg_ingest.mapper.map_export`
    must produce a BYTE-IDENTICAL ``CPG`` from ``export`` and
    ``shuffled_export(export)``.
    """
    out = copy.deepcopy(export)
    out["nodes"] = list(reversed(out["nodes"]))
    out["edges"] = list(reversed(out["edges"]))
    return out


__all__ = [
    "HELPERS_FIXTURE_SOURCE_PYTHON",
    "SQLI_FIXTURE_SOURCE_PYTHON",
    "SQLI_JOERN_EXPORT_FIXTURE",
    "shuffled_export",
]
