"""Execute the actual Git hooks with isolated trusted command stubs."""

from __future__ import annotations

import json
import shutil
import subprocess
import tomllib
from importlib.metadata import version
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIRS = ["analysis", "detectors", "integrations", "services", "workers"]


def _stub(directory, name, body):
    path = directory / name
    path.write_text(
        "#!/bin/sh\n"
        f"printf '%s' '{name}' >> \"$HOOK_TEST_LOG\"\n"
        'for argument in "$@"; do printf \'\\t%s\' "$argument" >> "$HOOK_TEST_LOG"; done\n'
        "printf '\\n' >> \"$HOOK_TEST_LOG\"\n" + body + "\n"
    )
    path.chmod(0o755)


def _environment(tmp_path):
    commands = tmp_path / "commands"
    commands.mkdir()
    environment = {"PATH": str(commands), "HOOK_TEST_LOG": str(tmp_path / "commands.log")}
    _stub(commands, "npx", 'exit "${MOCK_NPX_STATUS:-0}"')
    _stub(commands, "pre-commit", 'exit "${MOCK_PRE_COMMIT_STATUS:-0}"')
    _stub(
        commands,
        "ruff",
        'case "$1" in check) exit "${MOCK_RUFF_CHECK_STATUS:-0}";; '
        'format) exit "${MOCK_RUFF_FORMAT_STATUS:-0}";; esac',
    )
    _stub(
        commands,
        "mypy",
        'case " $* " in *services*) exit "${MOCK_MYPY_STATUS:-0}";; '
        '*) exit "${MOCK_MYPY_PARTIAL_STATUS:-0}";; esac',
    )
    _stub(commands, "pytest", 'exit "${MOCK_PYTEST_STATUS:-0}"')
    # Discovery is real filesystem inspection. No source fixture is executed.
    for name in ("find", "grep", "head", "xargs", "dirname", "sort", "tr"):
        executable = shutil.which(name)
        assert executable is not None
        (commands / name).symlink_to(executable)
    return environment


def _run_hook(name, tmp_path, environment, *, arguments=(), stdin=""):
    result = subprocess.run(
        ["/bin/sh", str(ROOT / ".husky" / name), *arguments],
        cwd=tmp_path,
        env=environment,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=10,
    )
    log = Path(environment["HOOK_TEST_LOG"])
    commands = [line.split("\t") for line in log.read_text().splitlines()] if log.exists() else []
    return result, commands


def _source_tree(tmp_path, directories=SOURCE_DIRS):
    for name in directories:
        path = tmp_path / name
        path.mkdir()
        (path / "example.py").write_text("pass\n")


@pytest.mark.parametrize("status", [1, 23, 127])
def test_pre_commit_stops_after_lint_staged_failure(tmp_path, status):
    environment = _environment(tmp_path)
    environment["MOCK_NPX_STATUS"] = str(status)
    result, commands = _run_hook("pre-commit", tmp_path, environment)
    assert result.returncode == status
    assert commands == [["npx", "lint-staged"]]


@pytest.mark.parametrize("status", [0, 1, 17])
def test_pre_commit_preserves_second_stage_result_and_order(tmp_path, status):
    environment = _environment(tmp_path)
    environment["MOCK_PRE_COMMIT_STATUS"] = str(status)
    result, commands = _run_hook("pre-commit", tmp_path, environment)
    assert result.returncode == status
    assert commands == [["npx", "lint-staged"], ["pre-commit", "run", "--hook-stage", "pre-commit"]]


@pytest.mark.parametrize("missing", ["npx", "pre-commit"])
def test_pre_commit_missing_executable_is_fatal(tmp_path, missing):
    environment = _environment(tmp_path)
    (Path(environment["PATH"]) / missing).unlink()
    result, commands = _run_hook("pre-commit", tmp_path, environment)
    assert result.returncode == 127
    assert commands == ([] if missing == "npx" else [["npx", "lint-staged"]])


@pytest.mark.parametrize("status", [0, 1, 9])
def test_commit_message_propagates_validator_status_and_quoted_path(tmp_path, status):
    environment = _environment(tmp_path)
    environment["MOCK_PRE_COMMIT_STATUS"] = str(status)
    message = str(tmp_path / "message with spaces.txt")
    result, commands = _run_hook("commit-msg", tmp_path, environment, arguments=(message,))
    assert result.returncode == status
    assert commands == [
        [
            "pre-commit",
            "run",
            "conventional-pre-commit",
            "--hook-stage",
            "commit-msg",
            "--commit-msg-filename",
            message,
        ]
    ]


def test_commit_message_missing_validator_is_fatal(tmp_path):
    environment = _environment(tmp_path)
    (Path(environment["PATH"]) / "pre-commit").unlink()
    result, commands = _run_hook("commit-msg", tmp_path, environment, arguments=("message.txt",))
    assert result.returncode == 127 and commands == []


def test_pre_push_checks_all_source_directories_once(tmp_path):
    environment = _environment(tmp_path)
    _source_tree(tmp_path)
    result, commands = _run_hook("pre-push", tmp_path, environment)
    assert result.returncode == 0
    assert commands[:3] == [
        ["ruff", "check", "."],
        ["ruff", "format", "--check", "."],
        ["mypy", "--config-file", "pyproject.toml", *SOURCE_DIRS],
    ]
    assert commands[3] == [
        "pytest",
        "tests/",
        "-m",
        "(unit or invariant) and not integration and not falsifier and not empirical",
        "-q",
        "--tb=short",
        "-x",
    ]
    assert len(commands) == 4 and "all checks passed" in result.stdout


@pytest.mark.parametrize(
    ("variable", "status", "expected_commands"),
    [
        ("MOCK_RUFF_CHECK_STATUS", 11, 1),
        ("MOCK_RUFF_FORMAT_STATUS", 12, 2),
        ("MOCK_MYPY_STATUS", 13, 3),
        ("MOCK_PYTEST_STATUS", 14, 4),
    ],
)
def test_pre_push_never_masks_a_failed_stage(tmp_path, variable, status, expected_commands):
    environment = _environment(tmp_path)
    _source_tree(tmp_path)
    environment[variable] = str(status)
    # In particular, services has a real type error but an analysis-only rerun
    # would pass. The old hook masked this via its partial mypy fallback.
    environment["MOCK_MYPY_PARTIAL_STATUS"] = "0"
    result, commands = _run_hook("pre-push", tmp_path, environment)
    assert result.returncode == status
    assert len(commands) == expected_commands
    assert "all checks passed" not in result.stdout


@pytest.mark.parametrize("present", [[], ["services"], ["analysis", "workers"]])
def test_pre_push_scaffold_guard_keeps_every_populated_source_directory(tmp_path, present):
    environment = _environment(tmp_path)
    _source_tree(tmp_path, present)
    (tmp_path / "detectors").mkdir()  # An existing empty directory is not a source input.
    result, commands = _run_hook("pre-push", tmp_path, environment)
    assert result.returncode == 0
    mypy_calls = [command for command in commands if command[0] == "mypy"]
    assert mypy_calls == (
        [["mypy", "--config-file", "pyproject.toml", *present]] if present else []
    )
    assert commands[-1][0] == "pytest"


def test_pre_push_discovery_failure_is_not_an_empty_scaffold(tmp_path):
    environment = _environment(tmp_path)
    _source_tree(tmp_path)
    path = Path(environment["PATH"]) / "find"
    path.unlink()
    _stub(path.parent, "find", "exit 15")
    result, commands = _run_hook("pre-push", tmp_path, environment)
    assert result.returncode == 15
    assert [command[0] for command in commands] == ["ruff", "ruff", "find"]


@pytest.mark.parametrize(("missing", "count"), [("ruff", 0), ("mypy", 2), ("pytest", 3)])
def test_pre_push_missing_quality_tool_is_fatal(tmp_path, missing, count):
    environment = _environment(tmp_path)
    _source_tree(tmp_path)
    (Path(environment["PATH"]) / missing).unlink()
    result, commands = _run_hook("pre-push", tmp_path, environment)
    assert result.returncode == 127
    assert len(commands) == count and "all checks passed" not in result.stdout


@pytest.mark.parametrize("branch", ["main", "production", "release"])
@pytest.mark.parametrize("deletion", [False, True])
def test_pre_push_still_refuses_protected_branch_updates_and_deletions(tmp_path, branch, deletion):
    environment = _environment(tmp_path)
    local_sha = ("0" if deletion else "a") * 40
    stdin = f"refs/heads/feature {local_sha} refs/heads/{branch} {'b' * 40}\n"
    result, commands = _run_hook("pre-push", tmp_path, environment, stdin=stdin)
    assert result.returncode == 1
    assert commands == [] and "refused" in result.stderr


@pytest.mark.parametrize("variable", ["SKIP_HUSKY", "HUSKY"])
def test_pre_push_preserves_existing_explicit_bypass_behavior(tmp_path, variable):
    environment = _environment(tmp_path)
    environment[variable] = "0" if variable == "HUSKY" else "1"
    result, commands = _run_hook("pre-push", tmp_path, environment)
    assert result.returncode == 0 and commands == []
    assert "skipped" in result.stdout


def test_yaml_cli_is_declared_matches_hook_and_really_lints(tmp_path):
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert "yamllint==1.35.1" in project["project"]["optional-dependencies"]["dev"]
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text())
    yamllint_repo = next(
        repository
        for repository in config["repos"]
        if any(hook["id"] == "yamllint" for hook in repository["hooks"])
    )
    assert yamllint_repo["rev"] == "v1.35.1"
    assert version("yamllint") == "1.35.1"
    executable = shutil.which("yamllint")
    assert executable is not None, "Fresh declared dev installation must expose the hook's CLI"
    observed = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=10)
    assert observed.returncode == 0 and observed.stdout.strip() == "yamllint 1.35.1"
    candidate = tmp_path / "candidate.yaml"
    for content, expected in [("key: value\n", 0), ("key: [\n", 1)]:
        candidate.write_text(content)
        lint = subprocess.run(
            [executable, "-c", str(ROOT / ".yamllint.yaml"), str(candidate)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert lint.returncode == expected
    package = json.loads((ROOT / "package.json").read_text())
    assert package["lint-staged"]["*.{yaml,yml}"] == ["yamllint -c .yamllint.yaml"]
