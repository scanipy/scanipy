"""Distinct, named source controls beyond the historical seven-column inventory."""

from __future__ import annotations

from dataclasses import dataclass

from bases import Base, render
from refactor_transforms import append_helper, locate, move_files, pure_extract, rename_local


@dataclass(frozen=True)
class Control:
    name: str
    language: str
    finding_class: str
    before_files: dict[str, str]
    after_files: dict[str, str]
    before_locator: dict[str, object]
    after_locator: dict[str, object] | None
    evidence_type: str
    expected_outcome: str
    rationale: str
    expected_purity: str | None = None


def _control(
    base: Base,
    name: str,
    before: dict[str, str],
    after: dict[str, str],
    *,
    before_file: str | None = None,
    after_file: str | None = None,
    outcome: str = "stay",
    purity: str | None = None,
    rationale: str,
) -> Control:
    before_file, after_file = before_file or base.filename, after_file or base.filename
    return Control(
        name,
        base.language,
        base.cls,
        before,
        after,
        locate(before[before_file], before_file, base.sink_callee),
        locate(after[after_file], after_file, base.sink_callee),
        "structural_comparison",
        outcome,
        rationale,
        purity,
    )


def build_controls() -> list[Control]:
    controls = []
    for i in range(8):
        base = render(i)
        label = f"{base.language}-{base.cls}"
        extracted = {**base.files, base.filename: pure_extract(base)}
        controls.append(
            _control(
                base,
                f"{label}-inline-method",
                extracted,
                base.files,
                purity="proven",
                rationale=(
                    "Inverse of a genuine called-helper extraction; "
                    "the multi-operand computation moves back into the caller."
                ),
            )
        )
        renamed = {path: rename_local(text) for path, text in extracted.items()}
        relocated, moved_file = move_files(renamed, base.filename, base.language)
        controls.append(
            _control(
                base,
                f"{label}-extract-rename-relocate",
                base.files,
                relocated,
                after_file=moved_file,
                purity="proven",
                rationale=(
                    "Combined genuine extraction, bound-local rename, "
                    "and physical package/module relocation."
                ),
            )
        )
        original = base.independent_statements[0]
        changed = (
            original.replace("0", "1")
            if base.cls == "deserialization"
            else original.replace("orders", "customers")
            .replace("/var/data/", "/var/private/")
            .replace("http://", "https://")
        )
        # For scalar bounds, change the literal, not the seed-suffixed identifier.
        if base.cls == "deserialization":
            changed = (
                original.rsplit("= 0", 1)[0] + "= 1" + (";" if base.language == "java" else "")
            )
        after = {**base.files, base.filename: base.source.replace(original, changed)}
        controls.append(
            _control(
                base,
                f"{label}-semantic-literal-change",
                base.files,
                after,
                outcome="flip",
                rationale=(
                    "Change a literal that actually feeds the implicated sink; "
                    "canonicalization must retain relevant value semantics."
                ),
            )
        )
    for i in (0, 1):
        base = render(i)
        extracted = {**base.files, base.filename: pure_extract(base)}
        actuals = [a for _, _, a in base.helper_parameters]
        swapped = [actuals[1], actuals[0], *actuals[2:]]
        before_call = "_extracted_value(" + ", ".join(actuals) + ")"
        after_call = "_extracted_value(" + ", ".join(swapped) + ")"
        source = extracted[base.filename]
        controls.append(
            _control(
                base,
                f"{base.language}-argument-position-change",
                extracted,
                {**extracted, base.filename: source.replace(before_call, after_call, 1)},
                outcome="flip",
                purity="proven",
                rationale=(
                    "Swap two actual arguments of a uniquely declared helper; "
                    "operand/binding order changes the returned query."
                ),
            )
        )
        returned = base.helper_expression
        reversed_expression = " + ".join(reversed(returned.split(" + ")))
        controls.append(
            _control(
                base,
                f"{base.language}-helper-return-change",
                extracted,
                {
                    **extracted,
                    base.filename: source.replace(
                        "return " + returned, "return " + reversed_expression
                    ),
                },
                outcome="flip",
                purity="proven",
                rationale=(
                    "Keep call site and callee name but change the returned expression; "
                    "callee semantics must affect identity."
                ),
            )
        )
        broken_source = (
            "public class Broken { public void broken( { }\n"
            if base.language == "java"
            else "def broken(\n"
        )
        broken_file = "Broken.java" if base.language == "java" else "broken.py"
        controls.append(
            Control(
                f"{base.language}-parser-failure",
                base.language,
                base.cls,
                base.files,
                {broken_file: broken_source},
                locate(base.source, base.filename, base.sink_callee),
                None,
                "analysis_failure",
                "failure",
                "Deliberately malformed after-source; parse failure must remain visible "
                "and must never resolve or suppress the prior finding.",
            )
        )
        controls.extend(two_call_chain_controls(base))
    return controls


def two_call_chain_controls(base: Base) -> list[Control]:
    """Two distinct argument contexts reuse one multi-assignment pure helper.

    Each sink is a separate required case. Merely finding one of the two calls
    cannot satisfy both, and the returned local must reconnect to both callers.
    """
    left, argument, right = [actual for _, _, actual in base.helper_parameters]
    if base.language == "java":
        before_computation = (
            f"        String partial = {left} + {argument};\n"
            f"        String {base.result_name} = partial + {right};"
        )
        before_second = (
            f'        String secondary = "archived-" + {argument};\n'
            f"        String secondPartial = {left} + secondary;\n"
            f"        String secondValue = secondPartial + {right};\n"
            "        st.executeQuery(secondValue);\n"
        )
        after_computation = (
            f"        String {base.result_name} = _extracted_value({left}, {argument}, {right});"
        )
        after_second = (
            f'        String secondary = "archived-" + {argument};\n'
            f"        String secondValue = _extracted_value({left}, secondary, {right});\n"
            "        st.executeQuery(secondValue);\n"
        )
        helper = (
            "    private static String _extracted_value("
            "String prefix, String item, String suffix) {\n"
            "        String partial = prefix + item;\n"
            "        String completed = partial + suffix;\n"
            "        return completed;\n    }\n"
        )
    else:
        before_computation = (
            f"        partial = {left} + {argument}\n        {base.result_name} = partial + {right}"
        )
        before_second = (
            f'        secondary = "archived-" + {argument}\n'
            f"        second_partial = {left} + secondary\n"
            f"        second_value = second_partial + {right}\n"
            "        self.cursor.execute(second_value)\n"
        )
        after_computation = (
            f"        {base.result_name} = _extracted_value({left}, {argument}, {right})"
        )
        after_second = (
            f'        secondary = "archived-" + {argument}\n'
            f"        second_value = _extracted_value({left}, secondary, {right})\n"
            "        self.cursor.execute(second_value)\n"
        )
        helper = (
            "def _extracted_value(prefix, item, suffix):\n"
            "    partial = prefix + item\n"
            "    completed = partial + suffix\n"
            "    return completed\n"
        )
    sink_line = "        " + base.sink_text + "\n"
    before_source = base.source.replace(base.computation_line, before_computation).replace(
        sink_line, sink_line + before_second
    )
    after_source = append_helper(
        base.source.replace(base.computation_line, after_computation).replace(
            sink_line, sink_line + after_second
        ),
        helper,
        base.language,
    )
    before = {**base.files, base.filename: before_source}
    after = {**base.files, base.filename: after_source}
    return [
        Control(
            f"{base.language}-two-call-chain-sink-{index + 1}",
            base.language,
            base.cls,
            before,
            after,
            locate(before_source, base.filename, base.sink_callee, occurrence=index),
            locate(after_source, base.filename, base.sink_callee, occurrence=index),
            "structural_comparison",
            "stay",
            "A multi-assignment computation is moved into one called helper reused "
            "with two distinct argument contexts; this case selects one exact sink occurrence.",
            "proven",
        )
        for index in range(2)
    ]
