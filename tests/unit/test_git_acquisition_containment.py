"""Hermetic #395 containment; no native Git or production acquisition proof."""

from __future__ import annotations

import asyncio
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from integrations.scm import ado, bitbucket, github, gitlab
from integrations.scm.base import RepoRef, SCMAuthMode, SCMCredentials, SCMError
from integrations.scm.native_acquisition import (
    NATIVE_GIT_UNAVAILABLE_REASON,
    NativeGitAcquisitionUnavailable,
)
from services.snapshot import worker
from tools.worker import secure_subprocess as guarded_process
from tools.worker.joern_java_safety import JoernEnvironmentProfile

pytestmark = pytest.mark.unit

_ENV_DIGEST = "sha256:" + "a" * 64
_SHA = "b" * 40
_PRIVATE_INPUT = "do-not-log-caller-input"
_DEFAULT = object()
_PROVIDERS = (
    (github, github.GitHubConnector, "github"),
    (gitlab, gitlab.GitLabConnector, "gitlab"),
    (bitbucket, bitbucket.BitbucketConnector, "bitbucket"),
    (ado, ado.AzureDevOpsConnector, "azure-devops"),
)

_ASSEMBLED_IMPORT_CHECK = r"""
import importlib.abc
import importlib.machinery
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

assembled = Path(sys.argv[1]).resolve()
checkout = Path(sys.argv[2]).resolve()
assert sys.flags.isolated and sys.flags.dont_write_bytecode
assert str(checkout) not in sys.path
first_party = {'analysis', 'db', 'detectors', 'integrations', 'services', 'tools', 'workers', 'web'}

class AssembledOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] not in first_party:
            return None
        # Restrict first-party top-level lookup to the assembled COPY tree.
        # Installed wheels may still supply third-party dependencies, but must
        # never repair a missing project package or namespace directory.
        search = [str(assembled)] if path is None else list(path)
        spec = importlib.machinery.PathFinder.find_spec(fullname, search)
        if spec is None:
            raise ModuleNotFoundError('missing assembled module: ' + fullname)
        origins = list(spec.submodule_search_locations or ())
        if spec.origin is not None:
            origins.append(spec.origin)
        assert origins and all(Path(p).resolve().is_relative_to(assembled) for p in origins)
        return spec

def forbidden(*args, **kwargs):
    raise AssertionError('assembled import/idle must not invoke native tools or job work')

sys.meta_path.insert(0, AssembledOnly())
subprocess.run = subprocess.Popen = os.system = forbidden
from services.snapshot import worker
from integrations.scm.base import SCMError
from integrations.scm.native_acquisition import NativeGitAcquisitionUnavailable

assert Path(worker.__file__).resolve().is_relative_to(assembled)
for name in ('_default_object_store', '_fail_closed_report_status_port',
             '_real_parse_source', 'record_snapshot_job_completion'):
    setattr(worker, name, forbidden)
worker.tempfile.TemporaryDirectory = forbidden
worker.run_execute_loop('sha256:' + 'a' * 64,
                        queue=SimpleNamespace(receive=lambda: None), environ={})
try:
    worker.refuse_native_git_acquisition()
except NativeGitAcquisitionUnavailable as error:
    assert isinstance(error, SCMError)
else:
    raise AssertionError('acquisition refusal missing')
for name, module in tuple(sys.modules.items()):
    if name.split('.')[0] in first_party and getattr(module, '__file__', None):
        assert Path(module.__file__).resolve().is_relative_to(assembled)
print('assembled worker import and idle/refusal passed')
"""


class PoisonInput:
    def __iter__(self):
        raise AssertionError("must not iterate refused input")

    def __len__(self):
        raise AssertionError("must not inspect refused input length")

    def __str__(self):
        raise AssertionError("must not disclose refused input")

    def __fspath__(self):
        raise AssertionError("must not access refused path")


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["log"],
        ["--version"],
        ["clone", "https://example.invalid/repo.git", "/private/new"],
        ["checkout", _SHA],
        ["-c", "core.sshCommand=" + _PRIVATE_INPUT, "fetch"],
        ["-c", "credential.helper=!" + _PRIVATE_INPUT, "fetch"],
        ["-c", "alias.probe=!" + _PRIVATE_INPUT, "probe"],
        ["clone", "ext::" + _PRIVATE_INPUT, "/private/new"],
        ["clone", "ssh://example.invalid/repo", "/private/new"],
        ["clone", "file:///private/repo", "/private/new"],
        PoisonInput(),
    ],
)
@pytest.mark.parametrize("profile", [None, JoernEnvironmentProfile.JAVA_STATIC_V1, "unknown"])
def test_public_git_wrapper_refuses_before_input_lookup_or_spawn(monkeypatch, argv, profile):
    resolve = Mock(side_effect=AssertionError("must not resolve binary"))
    spawn = Mock(side_effect=AssertionError("must not spawn"))
    monkeypatch.setattr(guarded_process, "resolve_pinned_binary", resolve)
    monkeypatch.setattr(guarded_process.subprocess, "run", spawn)
    with pytest.raises(guarded_process.ArgvAllowlistViolation, match="Unprofiled Git") as exc:
        guarded_process.secure_run(
            "git",
            argv,
            timeout_s=1,
            env={"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_VALUE_0": _PRIVATE_INPUT},
            cwd=PoisonInput(),
            environment_profile=profile,
        )
    assert _PRIVATE_INPUT not in str(exc.value)
    resolve.assert_not_called()
    spawn.assert_not_called()


def test_empty_git_allowlist_does_not_allow_bare_tokens():
    assert guarded_process.GIT_ARGV_ALLOWLIST == frozenset()
    with pytest.raises(guarded_process.ArgvAllowlistViolation, match="Unprofiled Git"):
        guarded_process._enforce_allowlist("git", ["arbitrary-verb"])


def test_non_git_wrapper_positive_control_preserves_exact_child_arguments(monkeypatch):
    completed = subprocess.CompletedProcess(["/opt/codeql/codeql", "database"], 0, b"ok", b"")
    spawn = Mock(return_value=completed)
    monkeypatch.setattr(guarded_process.subprocess, "run", spawn)
    supplied_env = {"PATH": "/opt/codeql"}
    actual = guarded_process.secure_run(
        "codeql", ["database"], timeout_s=7, env=supplied_env, cwd="/private/work"
    )
    assert actual is completed
    spawn.assert_called_once_with(
        ["/opt/codeql/codeql", "database"],
        capture_output=True,
        check=True,
        timeout=7,
        env=supplied_env,
        cwd="/private/work",
        shell=False,
    )


def _connector(provider, runner=_DEFAULT):
    module, constructor, identifier = provider
    credentials = SCMCredentials(identifier, SCMAuthMode.PAT, {"token": _PRIVATE_INPUT})
    options = {"transport": Mock()}
    if identifier == "azure-devops":
        options["organization"] = "controlled-org"
    if runner is not _DEFAULT:
        options["git_runner"] = runner
    return module, constructor(credentials, **options)


@pytest.mark.parametrize("provider", _PROVIDERS, ids=[p[2] for p in _PROVIDERS])
@pytest.mark.parametrize("explicit_default", [False, True])
def test_provider_default_clone_refuses_before_files_credentials_or_io(
    monkeypatch, tmp_path, provider, explicit_default
):
    module, _, identifier = provider
    _, connector = _connector(
        provider, module._default_git_runner if explicit_default else _DEFAULT
    )
    destination = tmp_path / "must-not-be-created"
    repo = RepoRef(identifier, "owner", "repo", "https://" + _PRIVATE_INPUT + "@example.invalid/r")
    forbidden = Mock(side_effect=AssertionError("refusal must precede side effects"))
    with monkeypatch.context() as boundary:
        boundary.setattr(Path, "mkdir", forbidden)
        boundary.setattr(Path, "rglob", forbidden)
        boundary.setattr(connector, "_authed_clone_url", forbidden)
        boundary.setattr(connector, "_git_runner", forbidden)
        boundary.setattr(asyncio, "create_subprocess_exec", forbidden)
        with pytest.raises(NativeGitAcquisitionUnavailable) as exc:
            asyncio.run(connector.clone(repo, commit_sha=_SHA, dest_dir=destination))
        assert isinstance(exc.value, SCMError)
        assert str(exc.value) == NATIVE_GIT_UNAVAILABLE_REASON
        assert _PRIVATE_INPUT not in str(exc.value)
        forbidden.assert_not_called()
        connector._transport.request.assert_not_called()
    assert not destination.exists()


@pytest.mark.parametrize("provider", _PROVIDERS, ids=[p[2] for p in _PROVIDERS])
def test_direct_default_runner_also_refuses_uninspected_inputs(monkeypatch, provider):
    module, _, _ = provider
    spawn = Mock(side_effect=AssertionError("must not spawn"))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    with pytest.raises(NativeGitAcquisitionUnavailable):
        asyncio.run(module._default_git_runner(PoisonInput(), PoisonInput()))
    spawn.assert_not_called()


@pytest.mark.parametrize("provider", _PROVIDERS, ids=[p[2] for p in _PROVIDERS])
def test_explicit_trusted_recording_runner_preserves_connector_clone_contract(
    monkeypatch, tmp_path, provider
):
    calls = []

    async def recording_runner(argv, cwd):
        calls.append((tuple(argv), cwd))
        if argv[0] == "rev-parse":
            return 0, _SHA + "\n", ""
        if argv[0] == "rev-list":
            return 0, _SHA + "\n", ""
        return 0, "", ""

    _, connector = _connector(provider, recording_runner)
    forbidden = Mock(side_effect=AssertionError("recording collaborator must not spawn"))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    destination = tmp_path / "trusted-recording-fixture"
    repo = RepoRef(provider[2], "owner", "repo", "https://example.invalid/repo.git")
    observed = asyncio.run(connector.clone(repo, commit_sha=_SHA, dest_dir=destination))
    assert observed.commit_sha == _SHA
    assert observed.provider == provider[2]
    assert [argv[0] for argv, _ in calls] == [
        "init",
        "remote",
        "fetch",
        "checkout",
        "remote",
        "rev-parse",
        "rev-list",
    ]
    assert calls[4][0] == ("remote", "remove", "origin")
    assert all(cwd == destination for _, cwd in calls)
    forbidden.assert_not_called()


def _job_body():
    return {
        "snapshot_id": "controlled-snapshot",
        "org_id": "11111111-1111-1111-1111-111111111111",
        "codebase_id": "22222222-2222-2222-2222-222222222222",
        "commit_sha": _SHA,
        "env_digest": _ENV_DIGEST,
        "clone_url": "ext::" + _PRIVATE_INPUT,
        "source_materializer": _PRIVATE_INPUT,
    }


@pytest.mark.parametrize("report_failure", [False, True])
def test_default_snapshot_fails_before_staging_and_never_acks_or_reports_ready(
    monkeypatch, report_failure
):
    queue = Mock()
    queue.receive.return_value = SimpleNamespace(
        message=SimpleNamespace(body=_job_body()), receipt_handle=17
    )
    reporter = Mock()
    if report_failure:
        reporter.report.side_effect = RuntimeError("controlled report failure")
    forbidden = Mock(side_effect=AssertionError("must refuse before acquisition side effects"))
    metrics, logger = Mock(), Mock()
    monkeypatch.setattr(worker.tempfile, "TemporaryDirectory", forbidden)
    monkeypatch.setattr(worker, "_default_object_store", forbidden)
    monkeypatch.setattr(worker, "_real_parse_source", forbidden)
    monkeypatch.setattr(worker.cw_detect, "detect", forbidden)
    monkeypatch.setattr(worker, "secure_run", forbidden)
    monkeypatch.setattr(worker, "record_snapshot_job_completion", metrics)
    monkeypatch.setattr(worker, "get_logger", Mock(return_value=logger))
    worker.run_execute_loop(
        _ENV_DIGEST,
        queue=queue,
        report_status=reporter,
        environ={"SOURCE_MATERIALIZER": _PRIVATE_INPUT, "SCANIPY_ENABLE_GIT": "1"},
    )
    forbidden.assert_not_called()
    reporter.report.assert_called_once()
    observed = reporter.report.call_args.args[0]
    assert observed.state == "failed"
    assert observed.error == NATIVE_GIT_UNAVAILABLE_REASON
    assert observed.snapshot_digest is None
    assert observed.precondition_status is None
    assert observed.env_digest == _ENV_DIGEST
    assert _PRIVATE_INPUT not in str(logger.mock_calls)
    queue.fail.assert_called_once_with(17)
    queue.ack.assert_not_called()
    metrics.assert_called_once()
    assert metrics.call_args.args[0] == "failure"
    assert metrics.call_args.kwargs["precondition_status"] == "unknown"


def test_idle_snapshot_does_not_resolve_any_collaborator_or_emit_metric(monkeypatch):
    queue = Mock()
    queue.receive.return_value = None
    forbidden = Mock(side_effect=AssertionError("idle poll must not do work"))
    for name in (
        "_default_object_store",
        "_fail_closed_report_status_port",
        "_real_parse_source",
        "record_snapshot_job_completion",
        "refuse_native_git_acquisition",
    ):
        monkeypatch.setattr(worker, name, forbidden)
    monkeypatch.setattr(worker.tempfile, "TemporaryDirectory", forbidden)
    worker.run_execute_loop(_ENV_DIGEST, queue=queue, environ={})
    forbidden.assert_not_called()
    queue.fail.assert_not_called()
    queue.ack.assert_not_called()


def test_entrypoint_never_supplies_materializer_from_cli_or_environment(monkeypatch):
    execute = Mock()
    monkeypatch.setattr(worker, "boot", Mock(return_value=_ENV_DIGEST))
    monkeypatch.setattr(worker, "run_execute_loop", execute)
    monkeypatch.setenv("SOURCE_MATERIALIZER", _PRIVATE_INPUT)
    assert worker.main(["--enable-git", _PRIVATE_INPUT]) == 0
    execute.assert_called_once_with(_ENV_DIGEST)


@pytest.mark.parametrize("omit_integrations", [False, True], ids=["recipe", "missing-copy"])
def test_snapshot_docker_package_copy_closure_imports_without_checkout_fallback(
    tmp_path, omit_integrations
):
    """Assemble trusted local COPY inputs, not an image/native-tool smoke test."""
    checkout = Path(__file__).resolve().parents[2]
    assembled = tmp_path / "app"
    assembled.mkdir()
    copied = []
    for line in (checkout / "workers/snapshot/Dockerfile").read_text().splitlines():
        heading = line.split(maxsplit=1)
        if not heading or heading[0].upper() != "COPY":
            continue
        fields = shlex.split(line, comments=True)
        assert len(fields) >= 3
        if fields[1].startswith("--"):
            continue
        assert len(fields) == 3, "review new COPY syntax before changing the assembly test"
        source, target = fields[1:]
        if not target.startswith("/app/"):
            continue
        source_path = checkout / source
        target_path = assembled / target.removeprefix("/app/")
        assert source_path.resolve().is_relative_to(checkout)
        assert target_path.resolve().is_relative_to(assembled)
        assert source_path.is_dir()
        if omit_integrations and source == "integrations":
            continue
        shutil.copytree(
            source_path, target_path, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
        )
        copied.append(source)
    assert ("integrations" in copied) is not omit_integrations
    # Deliberately poison PYTHONPATH with the checkout. -I plus the first-party
    # finder above rejects both that leakage and an installed Scanipy wheel.
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-X",
            f"pycache_prefix={tmp_path / 'private-pycache'}",
            "-c",
            _ASSEMBLED_IMPORT_CHECK,
            str(assembled),
            str(checkout),
        ],
        cwd=tmp_path,
        env={"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONPATH": str(checkout)},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if omit_integrations:
        assert completed.returncode != 0
        assert "missing assembled module: integrations" in completed.stderr
    else:
        assert completed.returncode == 0, completed.stderr
        assert "assembled worker import and idle/refusal passed" in completed.stdout
