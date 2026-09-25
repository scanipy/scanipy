"""Deterministic, genuine source transformations for the schema-2 corpus.

Source validity is checked independently in validate_fixtures.py. Expected
outcomes are fixed before running an engine, not inferred from its fingerprints.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bases import Base

REFACTORS = [
    "alpha-rename-local",
    "pdg-only-formatting",
    "independent-reordering",
    "pure-extract",
    "fqn-move-package-rename",
    "genuine-fix",
    "aliasing-changing-extract",
]
SHOULD_STAY = set(REFACTORS[:5])
SHOULD_FLIP = set(REFACTORS[5:])
GROUND_TRUTH = {r: "should-stay" if r in SHOULD_STAY else "should-flip" for r in REFACTORS}


@dataclass(frozen=True)
class RefactorResult:
    refactor: str
    ground_truth_label: str
    filename: str
    files: dict[str, str]
    rationale: str
    evidence_type: str
    expected_outcome: str
    before_locator: dict[str, object]
    after_locator: dict[str, object] | None
    expected_purity: str | None = None

    @property
    def source(self) -> str:
        return self.files[self.filename]


def locate(
    source: str, filename: str, callee: str, *, occurrence: int | None = None
) -> dict[str, object]:
    pattern = re.compile(rf"\b{re.escape(callee)}\s*\(")
    matches = [
        (i, line, match)
        for i, line in enumerate(source.splitlines(), 1)
        for match in pattern.finditer(line)
    ]
    if occurrence is None:
        if len(matches) != 1:
            raise ValueError(f"{filename}: expected one {callee} call, found {len(matches)}")
        occurrence = 0
    if occurrence < 0 or occurrence >= len(matches):
        raise ValueError(f"{filename}: missing {callee} occurrence {occurrence}")
    line_number, text, match = matches[occurrence]
    return {
        "file": filename,
        "line": line_number,
        "column": match.start() + 1,
        "callee": callee,
        "call_text": text.strip(),
    }


def rename_local(source: str) -> str:
    names = sorted(set(re.findall(r"\b[A-Za-z_]+\d{3}\b", source)))
    replacements = {old: f"renamed{i}" for i, old in enumerate(names)}
    return re.sub(r"\b[A-Za-z_]+\d{3}\b", lambda m: replacements[m.group()], source)


def append_helper(source: str, helper: str, language: str) -> str:
    if language == "java":
        closing = source.rfind("}")
        return source[:closing] + "\n" + helper + source[closing:]
    return source.rstrip() + "\n\n\n" + helper


def pure_extract(base: Base) -> str:
    actuals = ", ".join(actual for _, _, actual in base.helper_parameters)
    if base.language == "java":
        formals = ", ".join(f"{type_} {name}" for name, type_, _ in base.helper_parameters)
        replacement = (
            f"        {base.result_type} {base.result_name} = _extracted_value({actuals});"
        )
        helper = (
            f"    private static {base.result_type} _extracted_value({formals}) {{\n"
            f"        return {base.helper_expression};\n    }}\n"
        )
    else:
        formals = ", ".join(name for name, _, _ in base.helper_parameters)
        replacement = f"        {base.result_name} = _extracted_value({actuals})"
        helper = f"def _extracted_value({formals}):\n    return {base.helper_expression}\n"
    if base.source.count(base.computation_line) != 1:
        raise ValueError("computation site is not unique")
    return append_helper(
        base.source.replace(base.computation_line, replacement), helper, base.language
    )


def move_files(files: dict[str, str], filename: str, language: str) -> tuple[dict[str, str], str]:
    if language == "java":
        moved = filename.replace("/corpus/refac/", "/corpus/relocated/refac/")
        result = {
            (moved if path == filename else path): text.replace(
                "com.scanipy.corpus.refac", "com.scanipy.corpus.relocated.refac"
            )
            for path, text in files.items()
        }
    else:
        moved = "relocated/" + filename
        result = {
            ("relocated/" + path if path.startswith("refac/") else path): text.replace(
                "from refac.", "from relocated.refac."
            )
            for path, text in files.items()
        }
        result["relocated/__init__.py"] = '"""Relocated synthetic fixture package."""\n'
    return result, moved


def genuine_fix(base: Base) -> str:
    source = base.source
    if base.cls == "injection":
        literal = '"SELECT * FROM orders WHERE id = ?"'
        fixed = (
            f"        {base.result_type} {base.result_name} = {literal};"
            if base.language == "java"
            else f"        {base.result_name} = {literal}"
        )
        source = source.replace(base.computation_line, fixed)
        if base.language == "java":
            source = source.replace(
                "Statement st = conn.createStatement();",
                f"java.sql.PreparedStatement st = conn.prepareStatement({base.result_name});",
            )
            source = source.replace(
                base.sink_text, f"st.setString(1, {base.parameter});\n        st.executeQuery();"
            )
        else:
            source = source.replace(
                base.sink_text, f"self.cursor.execute({base.result_name}, ({base.parameter},))"
            )
    elif base.cls in {"path-traversal", "ssrf"}:
        literal = (
            '"/var/data/public.txt"'
            if base.cls == "path-traversal"
            else '"https://example.invalid/status"'
        )
        fixed = (
            f"        String {base.result_name} = {literal};"
            if base.language == "java"
            else f"        {base.result_name} = {literal}"
        )
        source = source.replace(base.computation_line, fixed)
    elif base.language == "java":
        start = source.index(base.independent_statements[0])
        end = source.index("    }", start)
        source = (
            source[:start] + f"        return new String({base.parameter}, "
            "java.nio.charset.StandardCharsets.UTF_8);\n" + source[end:]
        )
        source = source.replace("import java.io.ByteArrayInputStream;\n", "").replace(
            "import java.io.ObjectInputStream;\n", ""
        )
    else:
        source = source.replace("import pickle", "import json").replace(
            "pickle.loads(", "json.loads("
        )
    return source


def aliasing_extract(base: Base) -> str:
    p = base.parameter
    if base.language == "java":
        element_type = base.parameter_type
        holder = (
            f"        {element_type}[] box = new {element_type}[]{{{p}}};\n"
            f"        _mutate(box);\n        {p} = box[0];\n"
        )
        mutation = (
            'box[0] = box[0] + "-alias";'
            if element_type == "String"
            else "box[0][0] = (byte) (box[0][0] ^ 1);"
        )
        helper = (
            f"    private static void _mutate({element_type}[] box) {{\n"
            f"        {mutation}\n    }}\n"
        )
    else:
        holder = f"        box = [{p}]\n        _mutate(box)\n        {p} = box[0]\n"
        mutation = (
            'box[0] = box[0] + "-alias"'
            if base.parameter_type == "str"
            else "box[0] = box[0][::-1]"
        )
        helper = f"def _mutate(box):\n    {mutation}\n"
    source = base.source.replace(base.computation_line, holder + base.computation_line)
    return append_helper(source, helper, base.language)


RATIONALES = {
    "alpha-rename-local": (
        "Bijective rename of bound parameters/locals; no operator or literal change."
    ),
    "pdg-only-formatting": (
        "Only comments and blank lines change; executable statements are identical."
    ),
    "independent-reordering": (
        "Swap two existing independent literal assignments that both feed the sink computation; "
        "no added/deleted statement."
    ),
    "pure-extract": (
        "Move existing multi-operand slice computation into a called helper; "
        "bind actuals/formals and reconnect the return to the original sink."
    ),
    "fqn-move-package-rename": (
        "Actually move the source file and rename its package/module, "
        "updating a separate importing consumer."
    ),
    "genuine-fix": (
        "Remove the vulnerability by parameter binding, a fixed trusted path/URL, "
        "or replacing object deserialization with non-executing data decoding. "
        "Requires a completed scan establishing absence, not a missing hash."
    ),
    "aliasing-changing-extract": (
        "A called helper mutates an aliased holder and its changed value "
        "reaches the original sink; "
        "not eligible for pure normalization."
    ),
}


def apply_refactor(base: Base, refactor: str) -> RefactorResult:
    if refactor not in REFACTORS:
        raise KeyError(refactor)
    source = base.source
    filename = base.filename
    files = base.files
    if refactor == "alpha-rename-local":
        source = rename_local(source)
    elif refactor == "pdg-only-formatting":
        comment = "// formatting only" if base.language == "java" else "# formatting only"
        source = comment + "\n\n" + source.replace("\n", "\n\n").rstrip("\n") + "\n"
    elif refactor == "independent-reordering":
        first, second = base.independent_statements
        source = source.replace(first + "\n" + second, second + "\n" + first)
    elif refactor == "pure-extract":
        source = pure_extract(base)
    elif refactor == "genuine-fix":
        source = genuine_fix(base)
    elif refactor == "aliasing-changing-extract":
        source = aliasing_extract(base)
    files[filename] = source
    if refactor == "fqn-move-package-rename":
        files, filename = move_files(files, filename, base.language)
        source = files[filename]
    removal = refactor == "genuine-fix"
    after_locator = None if removal else locate(source, filename, base.sink_callee)
    return RefactorResult(
        refactor,
        GROUND_TRUTH[refactor],
        filename,
        files,
        RATIONALES[refactor],
        "finding_removal" if removal else "structural_comparison",
        "absent" if removal else ("stay" if refactor in SHOULD_STAY else "flip"),
        locate(base.source, base.filename, base.sink_callee),
        after_locator,
        "proven"
        if refactor == "pure-extract"
        else ("not_proven" if refactor == "aliasing-changing-extract" else None),
    )
