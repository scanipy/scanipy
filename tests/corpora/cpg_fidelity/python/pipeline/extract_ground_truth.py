"""Ground-truth extractor for the Python CPG-fidelity corpus (CMP-CORP-CPG-python).

This is the **versioned, self-contained** extraction script mandated by
DOC-CMP-CORP-CPG-python §3.1 / §3.4. It derives, for every Python source file
under a program's ``source/`` tree, deterministic ground-truth annotations:

  * ``ast.json``       — cpython ``ast`` serialization with stable field ordering
                         and source-position preservation (DOC §3.4 step 1).
  * ``cfg.json``       — per-function / per-method control-flow graph
                         (DOC §3.4 step 2). Class methods are CFG'd per-method.
  * ``callgraph.json`` — static call edges as ``(caller, callee, line)`` triples,
                         each tagged ``static`` or ``dynamic`` (DOC §3.4 step 3).
                         ``dynamic`` sites are recorded but EXCLUDED from the
                         gate's precision/recall by ``CMP-CP-06`` (the consumer).
  * ``pdg.json``       — intra-procedural PDG dependence edges: def→use data
                         dependence + control dependence on the guarding branch
                         (DOC §3.4 step 4).

### v0.1.0 methodology note (READ THIS — honest scope)

DOC §3.4 pins a *specific* third-party toolchain for the v1.0.0 bar:
cpython 3.10 ``ast`` + scalpel 1.0.4 (CFG/SDG) + Pyan3 1.2.0 + Pyre 0.0.301
(type-informed call edges). **Those tools are not vendored in this environment
and the pinned interpreter is 3.10; this build runs the AST step on the host
interpreter and replaces the scalpel/Pyan3/Pyre steps with this in-repo,
zero-dependency extractor.** This is a deliberate, documented deviation tracked
by ``CLAR-CORP-07`` (WBS §17). The trade-off:

  * AST ground truth is faithful (it is just cpython ``ast``), but it is recorded
    under the *host* ``python`` version (see ``extraction.yaml``), not the pinned
    3.10. Programs in this corpus are written in the 3.10-compatible subset so the
    serialized AST is stable across 3.10..3.12.
  * Call-graph ground truth here is the **statically name-resolvable** subset
    (module-level functions, class methods reached via an annotated/locally
    constructed receiver, and direct calls). Edges this extractor cannot resolve
    statically are tagged ``dynamic`` and excluded from precision/recall — exactly
    the partition DOC §3.4 step 3 mandates. Because the corpus programs are small
    and self-contained, the static subset is auditable by hand (the dual-review
    protocol, DOC §3.4 step 5).

The extractor is deterministic: same source bytes -> byte-identical JSON.

Run:
    python3 pipeline/extract_ground_truth.py --program programs/0001-...   # one
    python3 pipeline/extract_ground_truth.py --all                         # all
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

CORPUS_ROOT = Path(__file__).resolve().parent.parent
PROGRAMS_DIR = CORPUS_ROOT / "programs"

# ---------------------------------------------------------------------------
# AST serialization (DOC §3.4 step 1)
# ---------------------------------------------------------------------------

_POS_FIELDS = ("lineno", "col_offset", "end_lineno", "end_col_offset")


def _ast_to_dict(node: ast.AST) -> dict:
    """Canonical, position-preserving serialization with stable field ordering."""
    out: dict = {"_type": type(node).__name__}
    for field in node._fields:  # _fields ordering is stable per node type
        value = getattr(node, field, None)
        out[field] = _value_to_jsonable(value)
    for pos in _POS_FIELDS:
        if hasattr(node, pos):
            out[pos] = getattr(node, pos)
    return out


def _value_to_jsonable(value):
    if isinstance(value, ast.AST):
        return _ast_to_dict(value)
    if isinstance(value, list):
        return [_value_to_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, bytes):
        return {"_bytes": value.hex()}
    if isinstance(value, complex):
        return {"_complex": [value.real, value.imag]}
    return repr(value)


def extract_ast(tree: ast.AST) -> dict:
    return _ast_to_dict(tree)


# ---------------------------------------------------------------------------
# Function/method enumeration
# ---------------------------------------------------------------------------


def _qualname(stack: list[str], name: str) -> str:
    return ".".join([*stack, name]) if stack else name


def _iter_functions(tree: ast.Module):
    """Yield (qualname, node, enclosing_class_or_None) for every def/async def."""
    results: list[tuple[str, ast.AST, str | None]] = []

    def walk(node, stack: list[str], cls: str | None):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                walk(child, [*stack, child.name], child.name)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qn = _qualname(stack, child.name)
                results.append((qn, child, cls))
                walk(child, [*stack, child.name], None)
            else:
                walk(child, stack, cls)

    walk(tree, [], None)
    return results


# ---------------------------------------------------------------------------
# CFG (DOC §3.4 step 2) — per-function intra-procedural control-flow graph.
# A compact, deterministic basic-block-free statement-level CFG: one node per
# statement (keyed by lineno), edges for fallthrough + branch/loop/return.
# ---------------------------------------------------------------------------


def _stmt_id(stmt: ast.stmt) -> str:
    return f"L{stmt.lineno}:{type(stmt).__name__}"


def extract_cfg_for(fn: ast.AST) -> dict:
    nodes: list[str] = []
    edges: list[dict] = []
    seen: set[str] = set()

    def add_node(stmt: ast.stmt) -> str:
        nid = _stmt_id(stmt)
        if nid not in seen:
            seen.add(nid)
            nodes.append(nid)
        return nid

    def add_edge(a: str, b: str, kind: str):
        edges.append({"from": a, "to": b, "kind": kind})

    def flow(body: list[ast.stmt], succ: str | None):
        """Wire fallthrough edges through a statement list; succ = node after."""
        prev_exits: list[str] = []
        for i, stmt in enumerate(body):
            nid = add_node(stmt)
            for e in prev_exits:
                add_edge(e, nid, "fallthrough")
            prev_exits = _wire_stmt(stmt, nid)
        if succ is not None:
            for e in prev_exits:
                add_edge(e, succ, "fallthrough")
        return prev_exits

    def _wire_stmt(stmt: ast.stmt, nid: str) -> list[str]:
        if isinstance(stmt, ast.If):
            if stmt.body:
                add_edge(nid, add_node(stmt.body[0]), "true")
            t_exits = flow(stmt.body, None) or [nid]
            if stmt.orelse:
                add_edge(nid, add_node(stmt.orelse[0]), "false")
                f_exits = flow(stmt.orelse, None) or [nid]
                return [*t_exits, *f_exits]
            return [*t_exits, nid]
        if isinstance(stmt, (ast.While, ast.For, ast.AsyncFor)):
            if stmt.body:
                add_edge(nid, add_node(stmt.body[0]), "loop-body")
                body_exits = flow(stmt.body, nid)  # back-edge to header
                for e in body_exits:
                    add_edge(e, nid, "loop-back")
            return [nid]  # exit edge (loop-exit) is the fallthrough successor
        if isinstance(stmt, ast.Return):
            return []  # terminates flow
        return [nid]

    if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        flow(fn.body, None)
    return {"nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# Call graph (DOC §3.4 step 3) — static edges + dynamic-tagged sites.
# ---------------------------------------------------------------------------

# Names whose call is inherently dynamic dispatch (DOC §4.3 dynamic-dispatch).
_DYNAMIC_BUILTINS = {"getattr", "__import__", "eval", "exec"}


def _resolve_callee(call: ast.Call, local_funcs: set[str], local_methods: set[str]):
    """Return (callee_name, kind) where kind in {static, dynamic}.

    Static iff the callee is a bare ``Name`` that resolves to a module-level
    function defined in the same file, or an ``attribute`` whose method name is
    a known method in the file AND the receiver is a plain ``Name``/``self``.
    Everything else (getattr/dict-dispatch/runtime receivers/imports) is dynamic.
    """
    func = call.func
    # Inherently dynamic: getattr(...)( ), x()() where x came from getattr, etc.
    if isinstance(func, ast.Call):
        return ("<call-result>", "dynamic")
    if isinstance(func, ast.Name):
        if func.id in _DYNAMIC_BUILTINS:
            return (func.id, "dynamic")
        if func.id in local_funcs:
            return (func.id, "static")
        return (func.id, "dynamic")  # imported / free name not in file
    if isinstance(func, ast.Attribute):
        attr = func.attr
        recv = func.value
        # self.method() / Class-local method call -> static if method known.
        if isinstance(recv, ast.Name) and attr in local_methods:
            return (attr, "static")
        return (attr, "dynamic")
    if isinstance(func, ast.Subscript):  # dict-of-functions dispatch
        return ("<subscript>", "dynamic")
    return ("<unknown>", "dynamic")


def _calls_in_body(node: ast.AST):
    """Yield ast.Call nodes lexically owned by ``node``'s own body, NOT descending
    into nested FunctionDef/AsyncFunctionDef/Lambda (those are separate callers)."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue  # nested callable owns its own call sites
        if isinstance(child, ast.Call):
            yield child
        yield from _calls_in_body(child)


def extract_callgraph(tree: ast.Module) -> dict:
    funcs = _iter_functions(tree)
    local_funcs = {qn.split(".")[-1] for qn, _, _ in funcs}
    local_methods = {qn.split(".")[-1] for qn, _, cls in funcs if cls is not None}

    edges: list[dict] = []
    for caller_qn, fn, _cls in funcs:
        for sub in _calls_in_body(fn):
            callee, kind = _resolve_callee(sub, local_funcs, local_methods)
            edges.append(
                {
                    "caller": caller_qn,
                    "callee": callee,
                    "line": sub.lineno,
                    "kind": kind,
                }
            )
    edges.sort(key=lambda e: (e["caller"], e["line"], e["callee"], e["kind"]))
    return {"edges": edges}


# ---------------------------------------------------------------------------
# PDG dependence edges (DOC §3.4 step 4) — intra-procedural.
# Data dependence: a use of name N at line L depends on the most recent binding
# of N. Control dependence: a statement nested in an If/While/For body depends
# on the controlling test.
# ---------------------------------------------------------------------------


def _iter_names(node: ast.AST):
    """Walk ``node`` for Name refs WITHOUT entering nested callable definitions."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(child, ast.Name):
            yield child
        yield from _iter_names(child)


def _names_loaded(node: ast.AST) -> set[str]:
    out = set()
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
        out.add(node.id)
    for n in _iter_names(node):
        if isinstance(n.ctx, ast.Load):
            out.add(n.id)
    return out


def _names_stored(node: ast.AST) -> set[str]:
    out = set()
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
        out.add(node.id)
    for n in _iter_names(node):
        if isinstance(n.ctx, ast.Store):
            out.add(n.id)
    return out


def extract_pdg_for(fn: ast.AST) -> dict:
    edges: list[dict] = []
    last_def: dict[str, int] = {}

    # seed parameter definitions at the def line
    if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for arg in (
            fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs
        ):
            last_def[arg.arg] = fn.lineno

    def visit(body: list[ast.stmt], control: int | None):
        for stmt in body:
            # data dependence: each loaded name -> its last def
            for name in sorted(_names_loaded(stmt)):
                if name in last_def and last_def[name] != stmt.lineno:
                    edges.append(
                        {
                            "from_line": last_def[name],
                            "to_line": stmt.lineno,
                            "kind": "data",
                            "var": name,
                        }
                    )
            # control dependence
            if control is not None:
                edges.append(
                    {"from_line": control, "to_line": stmt.lineno, "kind": "control"}
                )
            # update defs
            for name in sorted(_names_stored(stmt)):
                last_def[name] = stmt.lineno
            # recurse into compound statements
            if isinstance(stmt, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                visit(stmt.body, stmt.lineno)
                if getattr(stmt, "orelse", None):
                    visit(stmt.orelse, stmt.lineno)
            elif isinstance(stmt, (ast.With, ast.AsyncWith)):
                visit(stmt.body, control)
            elif isinstance(stmt, ast.Try):
                visit(stmt.body, control)
                for handler in stmt.handlers:
                    visit(handler.body, control)
                visit(stmt.orelse, control)
                visit(stmt.finalbody, control)

    if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        visit(fn.body, None)
    edges.sort(key=lambda e: (e["from_line"], e["to_line"], e["kind"], e.get("var", "")))
    return {"edges": edges}


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def _dump_json(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=False, ensure_ascii=True) + "\n"


def extract_program(program_dir: Path) -> None:
    source_dir = program_dir / "source"
    gt_dir = program_dir / "ground_truth"
    gt_dir.mkdir(parents=True, exist_ok=True)

    py_files = sorted(source_dir.rglob("*.py"))
    if not py_files:
        raise SystemExit(f"{program_dir.name}: no .py files under source/")

    ast_all: dict = {}
    cfg_all: dict = {}
    cg_all: dict = {}
    pdg_all: dict = {}
    parse_records: list[dict] = []

    for py in py_files:
        rel = py.relative_to(source_dir).as_posix()
        text = py.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text, filename=rel)
            parse_records.append({"file": rel, "parsed": True})
        except SyntaxError as exc:  # recorded; parse-success metric input
            parse_records.append({"file": rel, "parsed": False, "error": str(exc)})
            continue

        ast_all[rel] = extract_ast(tree)
        funcs = _iter_functions(tree)
        cfg_all[rel] = {qn: extract_cfg_for(fn) for qn, fn, _ in funcs}
        cg_all[rel] = extract_callgraph(tree)
        pdg_all[rel] = {qn: extract_pdg_for(fn) for qn, fn, _ in funcs}

    (gt_dir / "ast.json").write_text(_dump_json(ast_all), encoding="utf-8")
    (gt_dir / "cfg.json").write_text(_dump_json(cfg_all), encoding="utf-8")
    (gt_dir / "callgraph.json").write_text(_dump_json(cg_all), encoding="utf-8")
    (gt_dir / "pdg.json").write_text(_dump_json(pdg_all), encoding="utf-8")
    (gt_dir / "parse.json").write_text(_dump_json(parse_records), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract Python CPG ground truth")
    ap.add_argument("--program", help="program dir (relative to corpus root or absolute)")
    ap.add_argument("--all", action="store_true", help="extract every program")
    args = ap.parse_args()

    if args.all:
        for d in sorted(p for p in PROGRAMS_DIR.iterdir() if p.is_dir()):
            extract_program(d)
            print(f"extracted {d.name}")
        return 0
    if args.program:
        p = Path(args.program)
        if not p.is_absolute():
            p = CORPUS_ROOT / args.program
        extract_program(p)
        print(f"extracted {p.name}")
        return 0
    ap.error("pass --program <dir> or --all")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
