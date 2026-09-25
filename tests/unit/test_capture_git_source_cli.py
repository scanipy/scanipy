"""Real CLI dispatch/producer tests; source commands and network are poisoned."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from scripts import capture_git_source as cli

from integrations.scm import source_acquisition as acquisition
from tests.unit.test_source_acquisition import fixtures

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def no_native_or_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("offline CLI attempted native/network work")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def test_actual_offline_cli_and_readonly_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    objects, store, evidence, binding = fixtures(tmp_path)
    # Legitimate repeated positional option VALUES preserve multiplicity.
    same_scope = str(uuid4())
    argv = [
        "scripts/capture_git_source.py",
        "offline-objects",
        "--objects-dir",
        str(objects),
        "--store-root",
        str(store),
        "--evidence-root",
        str(evidence),
        "--org-id",
        same_scope,
        "--codebase-id",
        same_scope,
        "--request-id",
        str(binding.request_id),
        "--commit",
        binding.resolved_commit,
        "--owner",
        "repeat",
        "--repository",
        "repeat",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    assert cli.main() == 0
    out = capsys.readouterr()
    assert not out.err
    result = json.loads(out.out)
    assert acquisition.decode_json(out.out.encode(), maximum=32 * 1024) == result
    assert result["caller"] == {
        "kind": "cli",
        "entrypoint": "scripts/capture_git_source.py",
        "argv": argv,
    }
    assert result["caller"]["argv"].count(same_scope) == 2
    assert result["caller"]["argv"].count("repeat") == 2
    proof = evidence / result["proof_id"]
    observed = json.loads((proof / "producer.json").read_bytes())
    assert observed["invocation_kind"] == "library_call" and observed["child_argv"] is None
    producer_before = (proof / "producer.json").read_bytes()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scripts/capture_git_source.py",
            "verify-capture",
            "--store-root",
            str(store),
            "--evidence-root",
            str(evidence),
            "--proof-id",
            result["proof_id"],
            "--expected-proof-digest",
            result["proof_digest"],
            "--expected-receipt",
            str(proof / "capture-receipt.json"),
        ],
    )
    assert cli.main() == 0
    replay = json.loads(capsys.readouterr().out)
    assert replay["operation"] == "verified-existing"
    assert replay["proof_digest"] == result["proof_digest"]
    assert (proof / "producer.json").read_bytes() == producer_before


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["not-a-command"],
        ["offline-objects"],
        ["--allow-network"],
        ["offline-objects", "--secret-value", "private-value"],
    ],
)
def test_invalid_cli_is_fixed_category_without_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    arguments: list[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["scripts/capture_git_source.py", *arguments])
    assert cli.main() == 2
    output = capsys.readouterr()
    assert output.out == "" and output.err == "invalid-input\n"
    assert list(tmp_path.iterdir()) == []


def test_online_refusal_precedes_argument_and_path_processing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("online refusal parsed/staged data")

    monkeypatch.setattr(cli, "_parser", forbidden)
    monkeypatch.setattr(acquisition, "capture_offline_objects", forbidden)
    monkeypatch.setattr(
        sys, "argv", ["scripts/capture_git_source.py", "github", "--allow-network", object()]
    )
    assert cli.main() == 69
    output = capsys.readouterr()
    assert not output.out and output.err == "unavailable-online\n"


@pytest.mark.parametrize(
    "argv",
    [
        ("script",),
        ["script", "x" * 4097],
        ["script"] * 65,
        ["script", "\ud800"],
        ["script", object()],
    ],
)
def test_exact_bounded_startup_argv(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], argv: object
) -> None:
    monkeypatch.setattr(sys, "argv", argv)
    assert cli.main() == 2
    output = capsys.readouterr()
    assert output.out == "" and output.err == "invalid-input\n"
