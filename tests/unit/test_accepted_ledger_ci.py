"""Exercise the actual ordinary AL job validator; no server or subprocess."""

from __future__ import annotations

import ast
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import yaml

pytestmark = pytest.mark.unit
WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/ci.yml"
EXPECTED = {
    "tests.integration.test_accepted_ledger_sql": 43,
    "tests.integration.test_accepted_ledger_security": 102,
    "tests.integration.test_accepted_historical_reads": 38,
    "tests.integration.test_execution_authority_role": 63,
}


def steps():
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]["accepted-ledger-tests"]["steps"]


def python_body(step):
    _shell, separator, code = step["run"].partition("<<'PY'\n")
    assert separator and code.endswith("\nPY\n")
    return code.removesuffix("\nPY\n")


def validator():
    selected = [step for step in steps() if step.get("name", "").startswith("Require exactly")]
    assert len(selected) == 1 and selected[0]["if"] == "always()"
    tree = ast.parse(python_body(selected[0]))
    imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)]
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "validate_report"
    ]
    assert len(functions) == 1
    # Only the trusted workflow's imports and validator execute. Its file reads,
    # catalog/driver operations, shell, test launcher and print calls do not.
    namespace = {}
    exec(
        compile(ast.Module(body=[*imports, *functions], type_ignores=[]), str(WORKFLOW), "exec"),
        namespace,
    )
    return namespace["validate_report"]


def report(counts=None):
    counts = EXPECTED if counts is None else counts
    root = ET.Element("testsuites")
    suite = ET.SubElement(
        root, "testsuite", tests=str(sum(counts.values())), skipped="0", failures="0", errors="0"
    )
    for module, count in counts.items():
        for index in range(count):
            ET.SubElement(suite, "testcase", classname=module, name=f"controlled_{index}")
    return root, suite


def test_explicit_selection_preserves_old_modules_and_adds_reader_role_module():
    selected = [
        step
        for step in steps()
        if step.get("name") == "Run AL tests and compare the actual dedicated-cluster baseline"
    ]
    assert len(selected) == 1
    tree = ast.parse(python_body(selected[0]))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
        and node.func.attr == "run"
    ]
    assert len(calls) == 1 and isinstance(calls[0].args[0], ast.List)
    arguments = [node.value for node in calls[0].args[0].elts if isinstance(node, ast.Constant)]
    assert [item for item in arguments if item.startswith("tests/integration/")] == [
        module.replace(".", "/") + ".py" for module in EXPECTED
    ]
    assert all(
        item in arguments
        for item in ("-m", "integration", "-x", "--junitxml=accepted-ledger-junit.xml")
    )


def test_actual_validator_accepts_exact_246_controlled_cases():
    root, _suite = report()
    validator()(ET.tostring(root))


def test_original_145_without_new_cases_cannot_satisfy_expanded_job():
    root, _suite = report(dict(list(EXPECTED.items())[:2]))
    with pytest.raises(AssertionError, match="exactly"):
        validator()(ET.tostring(root))


def test_total_alone_does_not_replace_per_module_counts():
    changed = dict(EXPECTED)
    changed["tests.integration.test_accepted_ledger_sql"] += 1
    changed["tests.integration.test_accepted_historical_reads"] -= 1
    root, _suite = report(changed)
    with pytest.raises(AssertionError, match="exactly"):
        validator()(ET.tostring(root))


@pytest.mark.parametrize("tag", ("skipped", "failure", "error"))
def test_any_case_skip_or_failure_rejects_even_with_zero_suite_counters(tag):
    root, suite = report()
    ET.SubElement(suite[0], tag)
    with pytest.raises(AssertionError, match="no skips"):
        validator()(ET.tostring(root))


@pytest.mark.parametrize("field", ("skipped", "failures", "errors"))
def test_nonzero_suite_failure_counters_reject(field):
    root, suite = report()
    suite.set(field, "1")
    with pytest.raises(AssertionError, match="suite reports"):
        validator()(ET.tostring(root))


@pytest.mark.parametrize("mutation", ("duplicate", "empty", "count", "outside", "second-suite"))
def test_identity_and_suite_accounting_cannot_hide_missing_cases(mutation):
    root, suite = report()
    if mutation == "duplicate":
        suite[1].set("name", suite[0].get("name"))
    elif mutation == "empty":
        suite[0].set("name", "")
    elif mutation == "count":
        suite.set("tests", "247")
    elif mutation == "outside":
        root.append(ET.Element("testcase", classname="outside", name="hidden"))
    else:
        ET.SubElement(root, "testsuite")
    with pytest.raises(AssertionError):
        validator()(ET.tostring(root))


@pytest.mark.parametrize("value", ("text-not-bytes", b"x" * 4194305, b"<wrong-root/>"))
def test_report_type_size_and_root_are_checked(value):
    with pytest.raises(AssertionError):
        validator()(value)


def test_original_183_without_reader_role_cases_cannot_satisfy_expanded_job():
    root, _suite = report(dict(list(EXPECTED.items())[:3]))
    with pytest.raises(AssertionError, match="exactly"):
        validator()(ET.tostring(root))


@pytest.mark.parametrize("module", tuple(EXPECTED)[:-1])
def test_reader_role_count_cannot_be_replaced_by_other_passing_cases(module):
    changed = dict(EXPECTED)
    changed[module] += 1
    changed["tests.integration.test_execution_authority_role"] -= 1
    root, _suite = report(changed)
    with pytest.raises(AssertionError, match="exactly"):
        validator()(ET.tostring(root))


@pytest.mark.parametrize("mutation", ("missing", "unexpected", "duplicate", "empty"))
def test_reader_role_report_identities_are_required(mutation):
    root, suite = report()
    if mutation == "missing":
        suite.remove(suite[-1])
        suite.set("tests", str(len(suite)))
    elif mutation == "unexpected":
        suite[-1].set("classname", "tests.integration.unallocated_reader")
    elif mutation == "duplicate":
        suite[-1].set("name", suite[-2].get("name"))
    else:
        suite[-1].set("name", "")
    with pytest.raises(AssertionError):
        validator()(ET.tostring(root))


@pytest.mark.parametrize("tag", ("skipped", "failure", "error"))
def test_reader_role_cases_must_execute_without_skips_or_errors(tag):
    root, suite = report()
    ET.SubElement(suite[-1], tag)
    with pytest.raises(AssertionError, match="no skips"):
        validator()(ET.tostring(root))


def test_actual_validator_also_accepts_the_single_testsuite_root():
    _root, suite = report()
    validator()(ET.tostring(suite))
