"""Independent source-shape checks; never executes a corpus program.

These checks establish fixture validity, not detector correctness or a runtime
pure-extract certificate. Java validation invokes javac with processors disabled.
"""

from __future__ import annotations

import ast
import copy
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from bases import Base
from refactor_transforms import RefactorResult, locate


class InvalidFixtureError(ValueError):
    pass


InvalidFixture = InvalidFixtureError


def require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidFixture(message)


def _substitute(expression: ast.expr, bindings: dict[str, ast.expr]) -> ast.expr:
    class Substitute(ast.NodeTransformer):
        def visit_Name(self, node: ast.Name) -> ast.expr:
            return copy.deepcopy(bindings.get(node.id, node))

    return Substitute().visit(copy.deepcopy(expression))


def validate_extraction(base: Base, source: str) -> None:
    require(base.computation_line not in source, "original computation was not moved")
    require(source.count("_extracted_value(") == 2, "helper must be declared and called once")
    require(len(base.helper_parameters) >= 3, "nontrivial multi-operand extraction required")
    if base.language == "python":
        module = ast.parse(source)
        helpers = [
            n
            for n in module.body
            if isinstance(n, ast.FunctionDef) and n.name == "_extracted_value"
        ]
        require(len(helpers) == 1, "helper must be a module-level function")
        helper = helpers[0]
        require(
            len(helper.body) == 1 and isinstance(helper.body[0], ast.Return),
            "unexpected helper body",
        )
        assignments = [
            n
            for n in ast.walk(module)
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == base.result_name for t in n.targets)
        ]
        require(len(assignments) == 1, "caller result binding is ambiguous")
        call = assignments[0].value
        require(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == helper.name,
            "helper result does not reconnect to caller",
        )
        require(len(call.args) == len(helper.args.args), "actual/formal arity changed")
        bindings = {
            formal.arg: actual for formal, actual in zip(helper.args.args, call.args, strict=True)
        }
        inlined = _substitute(helper.body[0].value, bindings)
        before = ast.parse(base.expression, mode="eval").body
        require(
            ast.dump(inlined) == ast.dump(before), "helper changes the original expression/binding"
        )
        require(
            any(isinstance(n, (ast.BinOp, ast.Subscript)) for n in ast.walk(before)),
            "identity-only extraction",
        )
    else:
        params = ", ".join(f"{t} {n}" for n, t, _ in base.helper_parameters)
        actuals = ", ".join(a for _, _, a in base.helper_parameters)
        declaration = f"private static {base.result_type} _extracted_value({params})"
        require(declaration in source, "private/static typed helper not found")
        require(
            f"{base.result_name} = _extracted_value({actuals});" in source,
            "caller does not use helper return",
        )
        returns = re.findall(r"return (.*);", source[source.index(declaration) :])
        require(
            returns == [base.helper_expression], "helper return does not preserve moved expression"
        )
        bindings = {n: a for n, _, a in base.helper_parameters}
        expanded = re.sub(
            r"\b[A-Za-z_]\w*\b", lambda m: bindings.get(m.group(), m.group()), returns[0]
        )
        require(expanded == base.expression, "actual/formal substitution changes expression")
        require(any(op in returns[0] for op in (" + ", " - ")), "identity-only Java extraction")


def validate_transformation(base: Base, result: RefactorResult) -> None:
    source, refactor = result.source, result.refactor
    require(source != base.source or result.filename != base.filename, "vacuous transformation")
    require(result.filename in result.files, "missing declared source")
    for path, text in result.files.items():
        require(
            not Path(path).is_absolute() and ".." not in Path(path).parts, "unsafe fixture path"
        )
        if path.endswith(".py"):
            ast.parse(text, filename=path)
    if refactor == "independent-reordering":
        first, second = base.independent_statements
        before_lines, after_lines = base.source.splitlines(), source.splitlines()
        require(
            Counter(before_lines) == Counter(after_lines), "reordering added/deleted statements"
        )
        require(before_lines.index(first) < before_lines.index(second), "invalid before ordering")
        require(
            after_lines.index(second) < after_lines.index(first),
            "existing statements were not swapped",
        )
        # Both literal assignments feed the expression; unrelated inserted code cannot pass.
        for statement in (first, second):
            name = statement.split("=")[0].strip().split()[-1]
            require(
                re.search(rf"\b{re.escape(name)}\b", base.expression) is not None,
                "reorder is outside sink computation",
            )
    elif refactor == "pure-extract":
        validate_extraction(base, source)
    elif refactor == "fqn-move-package-rename":
        require(
            result.filename != base.filename and base.filename not in result.files,
            "file did not move",
        )
        if base.language == "java":
            require("package com.scanipy.corpus.relocated.refac;" in source, "package unchanged")
            consumer = result.files["src/main/java/com/scanipy/corpus/client/Client.java"]
            require(
                f"import com.scanipy.corpus.relocated.refac.{base.class_name};" in consumer,
                "consumer import not updated",
            )
        else:
            module = Path(base.filename).stem
            require(
                f"from relocated.refac.{module} import {base.class_name}"
                in result.files["consumer.py"],
                "consumer module reference unchanged",
            )
            require(
                "relocated/__init__.py" in result.files
                and "relocated/refac/__init__.py" in result.files,
                "moved package incomplete",
            )
    elif refactor == "aliasing-changing-extract":
        p = base.parameter
        require(source.count("_mutate(") == 2, "mutation helper is unused or ambiguous")
        sequence = ("_mutate(box)", f"{p} = box[0]", base.computation_line.strip())
        positions = [source.index(part) for part in sequence]
        require(positions == sorted(positions), "mutated value does not feed computation")
        helper = source[source.rfind("_mutate(") :]
        require("box[0] = " in helper or "box[0][0] = " in helper, "helper does not mutate alias")
        require(base.sink_text in source, "original sink not retained")
    elif refactor == "genuine-fix":
        require(
            result.evidence_type == "finding_removal" and result.after_locator is None,
            "fix disappearance must not manufacture after hash",
        )
        if base.cls == "injection":
            require('"SELECT * FROM orders WHERE id = ?"' in source, "query is not parameterized")
            bound = (
                f"st.setString(1, {base.parameter})"
                if base.language == "java"
                else f"({base.parameter},)"
            )
            require(bound in source, "untrusted input is not separately bound")
        elif base.cls in {"path-traversal", "ssrf"}:
            literal = (
                '"/var/data/public.txt"'
                if base.cls == "path-traversal"
                else '"https://example.invalid/status"'
            )
            require(f"{base.result_name} = {literal}" in source, "input still controls destination")
        else:
            forbidden = "ObjectInputStream" if base.language == "java" else "pickle.loads"
            require(forbidden not in source, "unsafe object deserializer remains")
    if result.after_locator is not None:
        require(
            result.after_locator == locate(source, result.filename, base.sink_callee),
            "stale after locator",
        )


def check_java_tree(root: Path) -> dict[str, object]:
    compiler = shutil.which("javac")
    if compiler is None:
        raise RuntimeError("javac is required for explicit Java fixture syntax validation")
    sources = sorted(root.rglob("*.java"))
    if not sources:
        raise InvalidFixture(f"no Java source in {root}")
    with tempfile.TemporaryDirectory(prefix="scanipy-corpus-javac-") as out:
        command = [
            compiler,
            "-J-Xmx256m",
            "-proc:none",
            "--release",
            "17",
            "-encoding",
            "UTF-8",
            "-d",
            out,
            *map(str, sources),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    return {
        "valid": completed.returncode == 0,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "file_count": len(sources),
    }
