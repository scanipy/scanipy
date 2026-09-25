"""Eight ordinary source templates with real, slice-relevant refactor sites.

All sources are SYNTHESIZED and must not be executed by the corpus pipeline.
Expected purity metadata is a requirement, never an engine certificate.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Base:
    cls: str
    language: str
    filename: str
    source: str
    sink_line: int
    source_desc: str
    class_name: str
    parameter: str
    parameter_type: str
    method_name: str
    sink_callee: str
    sink_text: str
    independent_statements: tuple[str, str]
    computation_line: str
    result_name: str
    result_type: str
    expression: str
    helper_parameters: tuple[tuple[str, str, str], ...]
    helper_expression: str
    preconditions: tuple[str, ...]
    auxiliary_files: tuple[tuple[str, str], ...]

    @property
    def files(self) -> dict[str, str]:
        return {self.filename: self.source, **dict(self.auxiliary_files)}


CLASSES = ("injection", "path-traversal", "ssrf", "deserialization")
CLASS_NAMES = ("OrderService", "FileService", "FetchService", "SessionService")
MODULE_NAMES = ("order_service", "file_service", "fetch_service", "session_service")
METHOD_NAMES = ("lookup", "read", "fetch", "restore")


def _java(seed: int, kind: int) -> Base:
    cls, name, method = CLASSES[kind], CLASS_NAMES[kind], METHOD_NAMES[kind]
    p, left, right, result = (f"{stem}{seed:03d}" for stem in ("input", "left", "right", "value"))
    parameter_type, result_type = ("byte[]", "int") if kind == 3 else ("String", "String")
    expression = f"{p}.length - {left} - {right}" if kind == 3 else f"{left} + {p} + {right}"
    constants = (
        ('"SELECT * FROM orders WHERE id = \'"', '"\'"'),
        ('"/var/data/"', '".txt"'),
        ('"http://"', '"/status"'),
        ("0", "0"),
    )[kind]
    independent = tuple(
        f"        {result_type} {v} = {c};" for v, c in zip((left, right), constants, strict=True)
    )
    computation = f"        {result_type} {result} = {expression};"
    imports, setup, tail, sink, callee, returns = (
        (
            "import java.sql.Connection;\nimport java.sql.Statement;\n",
            f"    private final Connection conn;\n\n    public {name}(Connection conn) {{\n"
            "        this.conn = conn;\n    }\n\n",
            f"        Statement st = conn.createStatement();\n        st.executeQuery({result});\n",
            f"st.executeQuery({result});",
            "executeQuery",
            "void",
        ),
        (
            "import java.io.File;\nimport java.io.FileInputStream;\n",
            "",
            f"        File target = new File({result});\n"
            "        FileInputStream stream = new FileInputStream(target);\n"
            "        return stream.readAllBytes();\n",
            "FileInputStream stream = new FileInputStream(target);",
            "FileInputStream",
            "byte[]",
        ),
        (
            "import java.net.URL;\nimport java.net.HttpURLConnection;\n",
            "",
            f"        URL url = new URL({result});\n"
            "        HttpURLConnection connection = (HttpURLConnection) url.openConnection();\n"
            "        return connection.getResponseCode();\n",
            "HttpURLConnection connection = (HttpURLConnection) url.openConnection();",
            "openConnection",
            "int",
        ),
        (
            "import java.io.ByteArrayInputStream;\nimport java.io.ObjectInputStream;\n",
            "",
            f"        ByteArrayInputStream bin = new ByteArrayInputStream({p}, {left}, {result});\n"
            "        ObjectInputStream stream = new ObjectInputStream(bin);\n"
            "        return stream.readObject();\n",
            "return stream.readObject();",
            "readObject",
            "Object",
        ),
    )[kind]
    source = (
        f"package com.scanipy.corpus.refac;\n\n{imports}\npublic class {name} {{\n{setup}"
        f"    public {returns} {method}({parameter_type} {p}) throws Exception {{\n"
        + "\n".join(independent)
        + "\n"
        + computation
        + "\n"
        + tail
        + "    }\n}\n"
    )
    filename = f"src/main/java/com/scanipy/corpus/refac/{name}.java"
    parameters = (
        (("length", "int", f"{p}.length"), (left, "int", left), (right, "int", right))
        if kind == 3
        else ((left, "String", left), (p, "String", p), (right, "String", right))
    )
    helper_expression = f"length - {left} - {right}" if kind == 3 else expression
    auxiliary = (
        (
            "src/main/java/com/scanipy/corpus/client/Client.java",
            f"package com.scanipy.corpus.client;\nimport com.scanipy.corpus.refac.{name};\n"
            "public final class Client {\n"
            f"    public static Class<?> serviceType() {{ return {name}.class; }}\n}}\n",
        ),
    )
    return Base(
        cls,
        "java",
        filename,
        source,
        next(i for i, line in enumerate(source.splitlines(), 1) if line.strip() == sink),
        f"untrusted method parameter {p} reaches {callee}",
        name,
        p,
        parameter_type,
        method,
        callee,
        sink,
        independent,
        computation,
        result,
        result_type,
        expression,
        parameters,
        helper_expression,
        (
            "Java String/primitive operations retain operand and exception order.",
            "Non-null byte array; extraction moves scalar length arithmetic, "
            "not mutable-array access."
            if kind == 3
            else "String operands have resolved String types, not Object.toString conversion.",
        ),
        auxiliary,
    )


def _python(seed: int, kind: int) -> Base:
    cls, name, module, method = (
        CLASSES[kind],
        CLASS_NAMES[kind],
        MODULE_NAMES[kind],
        METHOD_NAMES[kind],
    )
    p, left, right, result = (f"{stem}{seed:03d}" for stem in ("input", "left", "right", "value"))
    constants = (
        ('"SELECT * FROM orders WHERE id = \'"', '"\'"'),
        ('"/var/data/"', '".txt"'),
        ('"http://"', '"/status"'),
        ("0", "0"),
    )[kind]
    independent = tuple(f"        {v} = {c}" for v, c in zip((left, right), constants, strict=True))
    expression = f"{p}[{left}:length - {right}]" if kind == 3 else f"{left} + {p} + {right}"
    computation = f"        {result} = {expression}"
    imports, setup, tail, sink, callee = (
        (
            "import sqlite3\n",
            "    def __init__(self, cursor: sqlite3.Cursor):\n        self.cursor = cursor\n\n",
            f"        self.cursor.execute({result})\n        return self.cursor.fetchall()\n",
            f"self.cursor.execute({result})",
            "execute",
        ),
        (
            "",
            "",
            f'        with open({result}, "rb") as stream:\n            return stream.read()\n',
            f'with open({result}, "rb") as stream:',
            "open",
        ),
        (
            "import urllib.request\n",
            "",
            f"        response = urllib.request.urlopen({result})\n"
            "        return response.status\n",
            f"response = urllib.request.urlopen({result})",
            "urlopen",
        ),
        (
            "import pickle\n",
            "",
            f"        data = pickle.loads({result})\n        return data\n",
            f"data = pickle.loads({result})",
            "loads",
        ),
    )[kind]
    exact_type = "bytes" if kind == 3 else "str"
    source = (
        f'"""Synthetic {cls} fixture; never execute during corpus validation."""\n\n{imports}\n\n'
        f"class {name}:\n{setup}    def {method}(self, {p}):\n"
        f"        if type({p}) is not {exact_type}:\n"
        f'            raise TypeError("exact {exact_type} required")\n'
        + "\n".join(independent)
        + "\n"
        + (f"        length = len({p})\n" if kind == 3 else "")
        + computation
        + "\n"
        + tail
    )
    parameters = (
        ((p, "bytes", p), (left, "int", left), ("length", "int", "length"), (right, "int", right))
        if kind == 3
        else ((left, "str", left), (p, "str", p), (right, "str", right))
    )
    auxiliary = (
        ("refac/__init__.py", '"""Synthetic fixture package."""\n'),
        (
            "consumer.py",
            f"from refac.{module} import {name}\n\ndef service_type():\n    return {name}\n",
        ),
    )
    return Base(
        cls,
        "python",
        f"refac/{module}.py",
        source,
        next(i for i, line in enumerate(source.splitlines(), 1) if line.strip() == sink),
        f"untrusted exact-{exact_type} parameter {p} reaches {callee}",
        name,
        p,
        exact_type,
        method,
        callee,
        sink,
        independent,
        computation,
        result,
        exact_type,
        expression,
        parameters,
        expression,
        (
            f"Source guard establishes exact built-in {exact_type}; a type hint is not proof.",
            "Closed fixture module does not rebind type/len/helper names or inspect frames.",
            "SQLite positional question-mark parameters are the injection fixture API contract."
            if kind == 0
            else "Built-in operand ordering, values, and normal/exceptional behavior "
            "are preserved.",
        ),
        auxiliary,
    )


def render(seed: int) -> Base:
    kind = (seed % 8) // 2
    return _java(seed, kind) if seed % 2 == 0 else _python(seed, kind)
