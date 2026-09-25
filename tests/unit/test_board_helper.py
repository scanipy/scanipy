"""Hermetic board CLI contracts: fake gh only, never live project mutations."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit
SCRIPT = Path(__file__).resolve().parents[2] / "scripts/board.sh"
STATUSES = {"Todo": "option-todo", "In Progress": "option-progress", "Done": "option-done"}


@pytest.fixture
def board(tmp_path: Path) -> dict[str, Any]:
    owner = {"__typename": "Organization", "login": "scanipy"}
    options = [{"name": name, "id": option} for name, option in STATUSES.items()]
    item = {
        "id": "item-target",
        "isArchived": False,
        "content": {
            "__typename": "Issue",
            "id": "issue-target",
            "number": 377,
            "repository": {"nameWithOwner": "scanipy/scanipy"},
        },
        "project": {"id": "project-target", "number": 5, "owner": owner},
        "fieldValueByName": {
            "__typename": "ProjectV2ItemFieldSingleSelectValue",
            "name": "Todo",
            "optionId": STATUSES["Todo"],
            "field": {"id": "field-status", "name": "Status"},
        },
    }
    issue: dict[str, Any] = {
        "data": {
            "repository": {
                "nameWithOwner": "scanipy/scanipy",
                "issue": {
                    "id": "issue-target",
                    "number": 377,
                    "projectItems": {
                        "totalCount": 1,
                        "pageInfo": {"hasNextPage": False},
                        "nodes": [item],
                    },
                },
            }
        }
    }
    fields: dict[str, Any] = {
        "data": {
            "node": {
                "__typename": "ProjectV2",
                "id": "project-target",
                "number": 5,
                "closed": False,
                "owner": copy.deepcopy(owner),
                "fields": {
                    "totalCount": 1,
                    "pageInfo": {"hasNextPage": False},
                    "nodes": [
                        {
                            "__typename": "ProjectV2SingleSelectField",
                            "id": "field-status",
                            "name": "Status",
                            "options": options,
                        }
                    ],
                },
            }
        }
    }
    fields["data"]["node"]["statusField"] = fields["data"]["node"]["fields"]["nodes"][0]
    binary = tmp_path / "bin"
    binary.mkdir()
    fake = binary / "gh"
    fake.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "with Path(os.environ['BOARD_TEST_LOG']).open('a') as out:\n"
        "    out.write(json.dumps(args) + '\\n')\n"
        "config = json.loads(Path(os.environ['BOARD_TEST_CONFIG']).read_text())\n"
        "if args[:2] == ['api', 'graphql']:\n"
        "    query = next((v for v in args if v.startswith('query=')), '')\n"
        "    kind = 'issue' if 'query BoardIssue(' in query else 'fields'\n"
        "    assert kind == 'issue' or 'query BoardFields(' in query\n"
        "elif args[:2] == ['project', 'item-edit']:\n"
        "    kind = 'mutation'\n"
        "else:\n"
        "    sys.exit('unexpected gh operation; live calls are forbidden')\n"
        "if config.get('failure') == kind:\n"
        "    sys.exit('controlled gh auth/quota/command failure')\n"
        "print(config.get('raw', {}).get(kind, json.dumps(config.get(kind, {}))))\n"
    )
    fake.chmod(0o755)
    return {
        "root": tmp_path,
        "bin": binary,
        "issue": issue,
        "fields": fields,
        "item": item,
        "connection": issue["data"]["repository"]["issue"]["projectItems"],
        "field_connection": fields["data"]["node"]["fields"],
        "status_field": fields["data"]["node"]["fields"]["nodes"][0],
    }


def _run(
    board: dict[str, Any], *args: str, env: dict[str, str] | None = None
) -> tuple[subprocess.CompletedProcess[str], list[list[str]]]:
    root: Path = board["root"]
    config = root / "config.json"
    config.write_text(
        json.dumps(
            {key: board[key] for key in ("issue", "fields", "failure", "raw") if key in board}
        )
    )
    log = root / "calls.jsonl"
    log.write_text("")
    settings = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("SCANIPY_PROJECT_") and key != "SCANIPY_REPOSITORY"
    }
    settings.update(
        PATH=str(board["bin"]) + os.pathsep + settings["PATH"],
        BOARD_TEST_LOG=str(log),
        BOARD_TEST_CONFIG=str(config),
    )
    settings.update(env or {})
    result = subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=root,
        env=settings,
        capture_output=True,
        text=True,
        check=False,
    )
    return result, [json.loads(line) for line in log.read_text().splitlines()]


def _status(board: dict[str, Any], status: str) -> None:
    board["item"]["fieldValueByName"].update(name=status, optionId=STATUSES[status])


@pytest.mark.parametrize("status", STATUSES)
@pytest.mark.parametrize("command", ["status", "check"])
def test_status_and_check_preserve_cli_and_two_bounded_reads(
    board: dict[str, Any], status: str, command: str
) -> None:
    _status(board, status)
    result, calls = _run(board, command, "377")
    assert result.returncode == (3 if command == "check" and status != "Todo" else 0), result.stderr
    assert (
        result.stdout == status + "\n"
        if command == "status"
        else f"board status: {status}" in result.stdout
    )
    assert len(calls) == 2
    assert all(call[:2] == ["api", "graphql"] for call in calls)
    assert "owner=scanipy" in calls[0] and "repo=scanipy" in calls[0] and "number=377" in calls[0]
    query = next(arg for arg in calls[0] if arg.startswith("query="))
    assert "projectItems(first: 20, includeArchived: true)" in query
    assert "items(" not in query and "fields(" not in query
    assert "id=project-target" in calls[1]
    assert "fields(first: 50)" in next(arg for arg in calls[1] if arg.startswith("query="))
    assert 'statusField: field(name: "Status")' in calls[1][-1]


@pytest.mark.parametrize("before", STATUSES)
@pytest.mark.parametrize("after", STATUSES)
def test_exact_status_mutation_and_idempotent_noop(
    board: dict[str, Any], before: str, after: str
) -> None:
    _status(board, before)
    result, calls = _run(board, "set", "377", after)
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"issue #377: {before} → {after}\n"
    if before == after:
        assert len(calls) == 2
    else:
        assert calls[2] == [
            "project",
            "item-edit",
            "--id",
            "item-target",
            "--field-id",
            "field-status",
            "--project-id",
            "project-target",
            "--single-select-option-id",
            STATUSES[after],
        ]
        assert len(calls) == 3


@pytest.mark.parametrize("command", ["check", "status"])
def test_unset_is_not_todo_and_cannot_start_work(board: dict[str, Any], command: str) -> None:
    board["item"]["fieldValueByName"] = None
    result, calls = _run(board, command, "377")
    assert result.returncode == 2
    assert "Status is Unset; initialize explicitly:" in result.stderr
    assert "OK to start" not in result.stdout
    assert len(calls) == 2


@pytest.mark.parametrize("target", STATUSES)
def test_explicit_set_can_initialize_verified_unset_status(
    board: dict[str, Any], target: str
) -> None:
    board["item"]["fieldValueByName"] = None
    result, calls = _run(board, "set", "377", target)
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"issue #377: Unset → {target}\n"
    assert calls[2][-1] == STATUSES[target]


def test_other_memberships_cannot_redirect_target(board: dict[str, Any]) -> None:
    wrong_owner = copy.deepcopy(board["item"])
    wrong_owner.update(id="item-other-owner")
    wrong_owner["project"].update(
        id="other-project", owner={"__typename": "User", "login": "other"}
    )
    wrong_number = copy.deepcopy(board["item"])
    wrong_number.update(id="item-other-number")
    wrong_number["project"].update(id="other-number", number=6)
    board["connection"]["nodes"] = [wrong_owner, board["item"], wrong_number]
    board["connection"]["totalCount"] = 3
    result, calls = _run(board, "set", "377", "In Progress")
    assert result.returncode == 0, result.stderr
    assert "id=project-target" in calls[1]
    assert calls[2][3] == "item-target"


@pytest.mark.parametrize("kind", ["Organization", "User"])
def test_explicit_repository_and_project_overrides(board: dict[str, Any], kind: str) -> None:
    board["issue"]["data"]["repository"]["nameWithOwner"] = "team/repository"
    board["item"]["content"]["repository"]["nameWithOwner"] = "team/repository"
    for project in (board["item"]["project"], board["fields"]["data"]["node"]):
        project.update(number=9, owner={"__typename": kind, "login": "board-owner"})
    result, calls = _run(
        board,
        "status",
        "377",
        env={
            "SCANIPY_REPOSITORY": "team/repository",
            "SCANIPY_PROJECT_OWNER": "board-owner",
            "SCANIPY_PROJECT_NUMBER": "9",
        },
    )
    assert result.returncode == 0, result.stderr
    assert "owner=team" in calls[0] and "repo=repository" in calls[0]


@pytest.mark.parametrize(
    "defect",
    [
        "wrong-repository",
        "missing-issue",
        "wrong-issue",
        "wrong-issue-id",
        "graphql-errors",
        "empty-memberships",
        "truncated-memberships",
        "count-mismatch",
        "missing-page-info",
        "null-item",
        "duplicate-item",
        "ambiguous-target",
        "wrong-project-number",
        "wrong-owner",
        "archived",
        "wrong-content-repo",
        "wrong-content-number",
        "wrong-content-id",
        "pull-request",
        "wrong-project-id",
        "field-project-number",
        "field-project-owner",
        "field-project-type",
        "closed-project",
        "fields-graphql-errors",
        "truncated-fields",
        "field-count-mismatch",
        "missing-status",
        "duplicate-status",
        "duplicate-field-id",
        "null-field",
        "wrong-field-type",
        "duplicate-option-name",
        "duplicate-option-id",
        "missing-option",
        "unknown-option",
        "missing-value-field",
        "wrong-value-type",
        "wrong-value-field",
        "wrong-value-name",
        "wrong-value-option",
        "malformed-issue-json",
        "malformed-fields-json",
        "missing-status-definition",
        "wrong-status-definition",
    ],
)
def test_malformed_or_ambiguous_evidence_fails_closed_without_mutation(
    board: dict[str, Any], defect: str
) -> None:
    repo = board["issue"]["data"]["repository"]
    item, connection = board["item"], board["connection"]
    project = board["fields"]["data"]["node"]
    fields, field = board["field_connection"], board["status_field"]
    value = item["fieldValueByName"]
    if defect == "wrong-repository":
        repo["nameWithOwner"] = "other/scanipy"
    elif defect == "missing-issue":
        repo["issue"] = None
    elif defect == "wrong-issue":
        repo["issue"]["number"] = 378
    elif defect == "wrong-issue-id":
        repo["issue"]["id"] = "different-issue"
    elif defect == "graphql-errors":
        board["issue"]["errors"] = [{"message": "partial data"}]
    elif defect == "empty-memberships":
        connection.update(nodes=[], totalCount=0)
    elif defect == "truncated-memberships":
        connection["pageInfo"]["hasNextPage"] = True
    elif defect == "count-mismatch":
        connection["totalCount"] = 2
    elif defect == "missing-page-info":
        connection.pop("pageInfo")
    elif defect == "null-item":
        connection["nodes"] = [None]
    elif defect == "duplicate-item":
        connection.update(nodes=[item, item], totalCount=2)
    elif defect == "ambiguous-target":
        duplicate = copy.deepcopy(item)
        duplicate["id"] = "second-item"
        connection.update(nodes=[item, duplicate], totalCount=2)
    elif defect == "wrong-project-number":
        item["project"]["number"] = 6
    elif defect == "wrong-owner":
        item["project"]["owner"]["login"] = "other"
    elif defect == "archived":
        item["isArchived"] = True
    elif defect == "wrong-content-repo":
        item["content"]["repository"]["nameWithOwner"] = "other/scanipy"
    elif defect == "wrong-content-number":
        item["content"]["number"] = 378
    elif defect == "wrong-content-id":
        item["content"]["id"] = "different-issue"
    elif defect == "pull-request":
        item["content"]["__typename"] = "PullRequest"
    elif defect == "wrong-project-id":
        project["id"] = "project-other"
    elif defect == "field-project-number":
        project["number"] = 6
    elif defect == "field-project-owner":
        project["owner"]["login"] = "other"
    elif defect == "field-project-type":
        project["__typename"] = "Issue"
    elif defect == "closed-project":
        project["closed"] = True
    elif defect == "fields-graphql-errors":
        board["fields"]["errors"] = [{"message": "partial data"}]
    elif defect == "truncated-fields":
        fields["pageInfo"]["hasNextPage"] = True
    elif defect == "field-count-mismatch":
        fields["totalCount"] = 2
    elif defect == "missing-status":
        field["name"] = "Not Status"
    elif defect == "duplicate-status":
        duplicate = copy.deepcopy(field)
        duplicate["id"] = "field-second-status"
        fields.update(nodes=[field, duplicate], totalCount=2)
    elif defect == "duplicate-field-id":
        fields.update(nodes=[field, field], totalCount=2)
    elif defect == "null-field":
        fields["nodes"] = [None]
    elif defect == "wrong-field-type":
        field["__typename"] = "ProjectV2Field"
    elif defect == "duplicate-option-name":
        field["options"][1]["name"] = "Todo"
    elif defect == "duplicate-option-id":
        field["options"][1]["id"] = STATUSES["Todo"]
    elif defect == "missing-option":
        field["options"].pop()
    elif defect == "unknown-option":
        field["options"].append({"id": "new-option", "name": "Backlog"})
    elif defect == "missing-value-field":
        item.pop("fieldValueByName")
    elif defect == "wrong-value-type":
        value["__typename"] = "ProjectV2ItemFieldTextValue"
    elif defect == "wrong-value-field":
        value["field"]["id"] = "other-field"
    elif defect == "wrong-value-name":
        value["name"] = "Done"
    elif defect == "wrong-value-option":
        value["optionId"] = "unknown-option"
    elif defect == "malformed-issue-json":
        board["raw"] = {"issue": "not JSON"}
    elif defect == "malformed-fields-json":
        board["raw"] = {"fields": "not JSON"}
    elif defect == "missing-status-definition":
        project.pop("statusField")
    elif defect == "wrong-status-definition":
        project["statusField"] = dict(field, id="other-field")
    else:
        raise AssertionError(defect)
    result, calls = _run(board, "set", "377", "In Progress")
    assert result.returncode == 2, (defect, result.stdout, result.stderr)
    assert "→" not in result.stdout and "OK to start" not in result.stdout
    assert all(call[:2] == ["api", "graphql"] for call in calls)


@pytest.mark.parametrize("failure, count", [("issue", 1), ("fields", 2), ("mutation", 3)])
def test_command_failures_are_errors_never_success(
    board: dict[str, Any], failure: str, count: int
) -> None:
    board["failure"] = failure
    result, calls = _run(board, "set", "377", "In Progress")
    assert result.returncode == 2
    assert "controlled gh" in result.stderr and "board.sh:" in result.stderr
    assert "→" not in result.stdout
    assert len(calls) == count


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("status",),
        ("status", "0"),
        ("check", "-1"),
        ("check", "01"),
        ("status", "2147483648"),
        ("status", "999999999999999999999999"),
        ("status", "1+1"),
        ("status", "377", "extra"),
        ("unknown", "377"),
        ("set", "377"),
        ("set", "377", "Backlog"),
        ("set", "377", "Done", "extra"),
    ],
)
def test_bad_arguments_fail_before_any_network(
    board: dict[str, Any], args: tuple[str, ...]
) -> None:
    result, calls = _run(board, *args)
    assert result.returncode == 2
    assert calls == []


@pytest.mark.parametrize(
    "env",
    [
        {"SCANIPY_PROJECT_NUMBER": "0"},
        {"SCANIPY_PROJECT_NUMBER": "2147483648"},
        {"SCANIPY_PROJECT_OWNER": "owner/other"},
        {"SCANIPY_REPOSITORY": "only-one-part"},
        {"SCANIPY_REPOSITORY": "owner/repo/extra"},
        {"SCANIPY_REPOSITORY": "-option/repo"},
    ],
)
def test_bad_configuration_fails_before_any_network(
    board: dict[str, Any], env: dict[str, str]
) -> None:
    result, calls = _run(board, "status", "377", env=env)
    assert result.returncode == 2
    assert calls == []
