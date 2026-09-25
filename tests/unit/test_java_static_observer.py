"""Actual adapter/secure-run observer tests; no real analysis tool is launched."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from analysis.cpg_ingest import joern_frontend as frontend
from tools.worker import secure_subprocess as spawn
from tools.worker.joern_java_safety import (
    JAVA_STATIC_PATH,
    JavaStaticEnvironmentError,
    JoernEnvironmentProfile,
    build_java_static_environment,
)

PROFILE = JoernEnvironmentProfile.JAVA_STATIC_V1


@pytest.fixture
def source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "Demo.java").write_text("class Demo {}\n")
    return source


def complete(cmd, kwargs):
    if cmd[0].endswith("joern-parse"):
        (Path(kwargs["cwd"]) / "cpg.bin").write_bytes(b"controlled-cpg")
    else:
        Path(kwargs["env"][frontend.ENV_EXPORT_JSON_PATH]).write_text('{"nodes":[],"edges":[]}')
    return subprocess.CompletedProcess(cmd, 0, b"raw\x00", b"warning\xff")


def test_java_observes_actual_both_phase_environments_not_adapter_inputs(
    source, tmp_path, monkeypatch
):
    work = tmp_path / "job"
    supplied = {
        "PATH": "/opt/joern/bin:/opt/codeql:/opt/temurin-jre/bin:/usr/bin",
        "HOME": str(work),
    }
    original = dict(supplied)
    events, calls = [], []

    def fake(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return complete(cmd, kwargs)

    monkeypatch.setattr(spawn.subprocess, "run", fake)
    frontend.parse_source(source, "java", env=supplied, workdir=work, observer=events.append)
    assert supplied == original
    assert [event.phase for event in events] == ["parse", "export"]
    for event, (cmd, kwargs) in zip(events, calls, strict=True):
        observed = event.environment_observation
        assert observed["profile"] == PROFILE.value
        assert observed["phase"] == event.phase
        assert observed["effective_environment"] == kwargs["env"]
        assert observed["effective_environment"]["PATH"] == JAVA_STATIC_PATH
        assert observed["effective_environment"]["HOME"] == str(work / ".scanipy-java-home")
        assert observed["effective_environment"]["JAVASRC_FETCH_DEPENDENCIES"] == "no-fetch"
        assert observed["directories"]["home"]["mode"] == "0700"
        assert event.argv == tuple(cmd)
        assert event.requested_argv == tuple(cmd[1:])
        assert event.stdout == b"raw\x00" and event.stderr == b"warning\xff"
        assert event.returncode == 0 and event.error_type is None
        assert event.elapsed_seconds >= 0
    assert (
        frontend.ENV_CPG_BIN_PATH not in events[0].environment_observation["effective_environment"]
    )
    assert frontend.ENV_CPG_BIN_PATH in events[1].environment_observation["effective_environment"]
    assert [event.timeout_s for event in events] == [600, 300]


@pytest.mark.parametrize("phase", ["parse", "export"])
@pytest.mark.parametrize("failure", ["exit", "timeout", "missing"])
def test_java_failures_keep_original_exception_raw_bytes_and_safe_profile(
    source, tmp_path, monkeypatch, phase, failure
):
    work = tmp_path / "job"
    events, errors = [], []

    def fake(cmd, **kwargs):
        actual_phase = "parse" if cmd[0].endswith("joern-parse") else "export"
        if actual_phase != phase:
            return complete(cmd, kwargs)
        if failure == "exit":
            error = subprocess.CalledProcessError(9, cmd, output=b"out\x00", stderr=b"err\xff")
        elif failure == "timeout":
            error = subprocess.TimeoutExpired(
                cmd, kwargs["timeout"], output=b"partial", stderr=b"slow"
            )
        else:
            error = FileNotFoundError("launcher absent")
        errors.append(error)
        # A failed child can alter writable runtime paths. Observation must
        # already exist, not replace this exception with a later stat error.
        (work / ".scanipy-java-home/tmp").chmod(0o777)
        raise error

    monkeypatch.setattr(spawn.subprocess, "run", fake)
    with pytest.raises(Exception) as raised:
        frontend.parse_source(source, "java", env={}, workdir=work, observer=events.append)
    assert raised.value is errors[0]
    assert len(events) == (1 if phase == "parse" else 2)
    event = events[-1]
    assert event.phase == phase and event.error_type == type(errors[0]).__name__
    assert event.environment_observation["directories"]["tmp"]["mode"] == "0700"
    assert (
        event.environment_observation["effective_environment"]["JAVASRC_FETCH_DEPENDENCIES"]
        == "no-fetch"
    )
    if failure == "missing":
        assert event.argv is None and event.returncode is None
        assert event.stdout == event.stderr == b""
    else:
        assert event.argv == tuple(errors[0].cmd)
        assert event.stdout == errors[0].stdout and event.stderr == errors[0].stderr
        assert event.returncode == (9 if failure == "exit" else None)


def test_unprofiled_python_environment_is_never_captured(tmp_path, monkeypatch):
    events = []
    monkeypatch.setattr(spawn.subprocess, "run", lambda cmd, **kwargs: complete(cmd, kwargs))
    frontend.parse_source(
        tmp_path / "source",
        "python",
        env={"PRIVATE_INPUT": "not-observed"},
        workdir=tmp_path / "job",
        observer=events.append,
    )
    assert [event.phase for event in events] == ["parse", "export"]
    assert all(event.environment_observation is None for event in events)
    assert "not-observed" not in repr(events)


def test_profile_projection_rejection_is_visible_without_dump_or_launch(tmp_path, monkeypatch):
    work = tmp_path / "job"
    env = build_java_static_environment({}, workdir=work)
    env["JAVA_TOOL_OPTIONS"] = "private-value-must-not-appear"
    events = []

    def prohibit(*args, **kwargs):
        pytest.fail("invalid profile reached secure_run")

    monkeypatch.setattr(frontend, "secure_run", prohibit)
    with pytest.raises(JavaStaticEnvironmentError, match="JAVA_TOOL_OPTIONS"):
        frontend._observed_run(
            "joern-parse",
            ["unreached"],
            phase="parse",
            timeout_s=600,
            env=env,
            cwd=str(work),
            observer=events.append,
            environment_profile=PROFILE,
        )
    assert len(events) == 1
    assert events[0].environment_observation is None
    assert events[0].argv is None and events[0].returncode is None
    assert events[0].error_type == "JavaStaticEnvironmentError"
    assert "private-value-must-not-appear" not in repr(events)


@pytest.mark.parametrize("profile", [None, "scanipy-java-static-env/1", "unknown-profile"])
def test_missing_or_unknown_profile_is_never_projected(source, tmp_path, monkeypatch, profile):
    work = tmp_path / "job"
    env = build_java_static_environment({}, workdir=work)
    env["PRIVATE_INPUT"] = "never-capture-this-value"
    events = []

    def prohibit(*args, **kwargs):
        pytest.fail("unrecognized profile reached projection or binary lookup")

    monkeypatch.setattr(frontend, "observe_java_static_environment", prohibit)
    monkeypatch.setattr(spawn, "resolve_pinned_binary", prohibit)
    with pytest.raises(JavaStaticEnvironmentError):
        frontend._observed_run(
            "joern-parse",
            [
                "--language",
                "javasrc",
                "--output",
                str(work / "cpg.bin"),
                str(source),
                "--frontend-args",
                "--delombok-mode",
                "no-delombok",
            ],
            phase="parse",
            timeout_s=600,
            env=env,
            cwd=str(work),
            observer=events.append,
            environment_profile=profile,
        )
    assert len(events) == 1
    assert events[0].environment_observation is None
    assert events[0].argv is None and events[0].returncode is None
    assert events[0].error_type == "JavaStaticEnvironmentError"
    assert "never-capture-this-value" not in repr(events)


@pytest.mark.parametrize("observer_enabled", [False, True])
def test_profile_keyword_is_forwarded_with_and_without_observer(
    source, tmp_path, monkeypatch, observer_enabled
):
    calls, events = [], []
    original = frontend.secure_run

    def capture(tool, argv, **kwargs):
        calls.append(kwargs["environment_profile"])
        return original(tool, argv=argv, **kwargs)

    monkeypatch.setattr(frontend, "secure_run", capture)
    monkeypatch.setattr(spawn.subprocess, "run", lambda cmd, **kwargs: complete(cmd, kwargs))
    frontend.parse_source(
        source,
        "java",
        env={},
        workdir=tmp_path / "job",
        observer=events.append if observer_enabled else None,
    )
    assert calls == [PROFILE, PROFILE]
    assert len(events) == (2 if observer_enabled else 0)


def test_observer_failure_is_not_silently_ignored(source, tmp_path, monkeypatch):
    monkeypatch.setattr(spawn.subprocess, "run", lambda cmd, **kwargs: complete(cmd, kwargs))

    def reject(event):
        raise OSError("evidence disk full")

    with pytest.raises(OSError, match="disk full"):
        frontend.parse_source(source, "java", env={}, workdir=tmp_path / "job", observer=reject)


@pytest.mark.parametrize("phase", ["parse", "export"])
@pytest.mark.parametrize("failure", ["exit", "timeout"])
def test_child_and_observer_failure_preserves_child_with_evidence_error_cause(
    source, tmp_path, monkeypatch, phase, failure
):
    events, errors = [], []
    evidence_error = OSError("evidence disk full")

    def fake(cmd, **kwargs):
        actual_phase = "parse" if cmd[0].endswith("joern-parse") else "export"
        if actual_phase != phase:
            return complete(cmd, kwargs)
        if failure == "exit":
            error = subprocess.CalledProcessError(7, cmd, output=b"out", stderr=b"err")
        else:
            error = subprocess.TimeoutExpired(cmd, kwargs["timeout"], output=b"partial")
        errors.append(error)
        raise error

    def reject_failed_event(event):
        events.append(event)
        if event.error_type is not None:
            raise evidence_error

    monkeypatch.setattr(spawn.subprocess, "run", fake)
    with pytest.raises((subprocess.CalledProcessError, subprocess.TimeoutExpired)) as raised:
        frontend.parse_source(
            source, "java", env={}, workdir=tmp_path / "job", observer=reject_failed_event
        )
    assert raised.value is errors[0]
    assert raised.value.__cause__ is evidence_error
    assert events[-1].error_type == type(errors[0]).__name__
    assert events[-1].stdout == errors[0].stdout
    assert events[-1].argv == tuple(errors[0].cmd)
