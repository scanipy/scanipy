"""R16 Java argv/env falsifiers; all subprocesses are mocked, never source execution."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from analysis.cpg_ingest import joern_frontend as frontend
from tests.cpg_ingest_fixtures import SQLI_JOERN_EXPORT_FIXTURE
from tools.worker import joern_java_safety as safety
from tools.worker import secure_subprocess as spawn
from tools.worker.joern_java_safety import (
    JAVA_STATIC_PATH,
    JavaStaticEnvironmentError,
    JoernEnvironmentProfile,
    build_java_static_environment,
    observe_java_static_environment,
    validate_java_static_environment,
)

pytestmark = pytest.mark.unit
PROFILE = JoernEnvironmentProfile.JAVA_STATIC_V1


@pytest.fixture
def job(tmp_path):
    source, work = tmp_path / "source", tmp_path / "work"
    source.mkdir()
    (source / "Demo.java").write_text("class Demo {}\n")
    env = build_java_static_environment({}, workdir=work)
    argv = [
        "--language",
        "javasrc",
        "--output",
        str(work / "cpg.bin"),
        str(source),
        "--frontend-args",
        "--delombok-mode",
        "no-delombok",
    ]
    return source, work, env, argv


def prohibit_spawn(monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("unsafe request reached binary lookup or subprocess")

    monkeypatch.setattr(spawn, "resolve_pinned_binary", fail)
    monkeypatch.setattr(spawn.subprocess, "run", fail)


def run_java(job, **changes):
    _, work, env, argv = job
    values = {
        "argv": argv,
        "timeout_s": 1,
        "env": env,
        "cwd": str(work),
        "environment_profile": PROFILE,
    }
    values.update(changes)
    return spawn.secure_run("joern-parse", **values)


def test_exact_profile_positive_and_actual_safe_observation(job, monkeypatch):
    _, work, env, argv = job
    seen = []

    def fake(cmd, **kwargs):
        seen.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0, b"actual-output", b"actual-warning")

    monkeypatch.setattr(spawn.subprocess, "run", fake)
    result = run_java(job)
    assert result.stdout == b"actual-output"
    assert seen[0][0] == ["/opt/joern/joern-parse", *argv]
    assert seen[0][1]["shell"] is False
    assert seen[0][1]["env"] == env
    observed = observe_java_static_environment(env, cwd=work, phase="parse")
    assert observed["profile"] == "scanipy-java-static-env/1"
    assert observed["effective_environment"] == env
    assert observed["directories"]["home"]["mode"] == "0700"
    assert observed["directories"]["tmp"]["mode"] == "0700"


@pytest.mark.parametrize(
    "change",
    [
        lambda a: a[:5],
        lambda a: [*a, "extra"],
        lambda a: [*a, "--fetch-dependencies"],
        lambda a: [*a[:5], "--", *a[6:]],
        lambda a: [*a[:5], "--frontend-args", "--delombok-mode= no-delombok"],
        lambda a: [*a[:-1], "default"],
        lambda a: [*a[:-1], "types-only"],
        lambda a: [*a[:-1], "run-delombok"],
        lambda a: [*a[:-1], "NO-DELOMBOK"],
        lambda a: a[:5] + a[5:] + a[5:],
        lambda a: ["--language=javasrc", *a[2:]],
        lambda a: ["--output", a[3], "--language", "javasrc", *a[4:]],
        lambda a: ["--language", "java", *a[2:]],
        lambda a: ["--language", "pythonsrc", *a[2:]],
        lambda a: [*a[:4], "--source-is-an-option", *a[5:]],
    ],
)
def test_malformed_java_grammar_rejects_before_lookup(job, monkeypatch, change):
    prohibit_spawn(monkeypatch)
    with pytest.raises(spawn.ArgvAllowlistViolation):
        run_java(job, argv=change(job[3]))


@pytest.mark.parametrize(
    "profile", [None, "scanipy-java-static-env/99", "scanipy-java-static-env/1"]
)
def test_java_requires_explicit_typed_supported_profile(job, monkeypatch, profile):
    prohibit_spawn(monkeypatch)
    with pytest.raises(JavaStaticEnvironmentError):
        run_java(job, environment_profile=profile)


@pytest.mark.parametrize("value", ["", "false", "0", "False", "NO-FETCH", " no-fetch", "no-fetch "])
def test_fetch_override_has_no_boolean_or_whitespace_alias(tmp_path, value):
    supplied = {"JAVASRC_FETCH_DEPENDENCIES": value}
    with pytest.raises(JavaStaticEnvironmentError, match="JAVASRC_FETCH_DEPENDENCIES"):
        build_java_static_environment(supplied, workdir=tmp_path / "job")
    assert supplied == {"JAVASRC_FETCH_DEPENDENCIES": value}
    assert not (tmp_path / "job").exists()


@pytest.mark.parametrize(
    "key",
    [
        "JAVA_TOOL_OPTIONS",
        "_JAVA_OPTIONS",
        "JDK_JAVA_OPTIONS",
        "JAVA_OPTS",
        "CLASSPATH",
        "LD_PRELOAD",
        "LD_LIBRARY_PATH",
        "BASH_ENV",
        "ENV",
        "MAVEN_CLI_OPTS",
        "GRADLE_OPTS",
        "JAVASRC_JDK_PATH",
        "UNKNOWN_KEY",
    ],
)
def test_unknown_native_hooks_reject_without_echoing_values(tmp_path, key):
    with pytest.raises(JavaStaticEnvironmentError) as error:
        build_java_static_environment({key: "private-supplied-value"}, workdir=tmp_path / "job")
    assert key in str(error.value)
    assert "private-supplied-value" not in str(error.value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("PATH", "/source/bin:/usr/bin"),
        ("JAVA_HOME", "/source/java"),
        ("HOME", "/tmp"),
        ("TMPDIR", "/tmp"),
        ("LANG", "en_US.UTF-8"),
        ("LC_ALL", "C"),
    ],
)
def test_unsafe_profile_values_fail_closed(tmp_path, field, value):
    with pytest.raises(JavaStaticEnvironmentError, match=field):
        build_java_static_environment({field: value}, workdir=tmp_path / "job")


def test_legacy_worker_and_campaign_inputs_are_explicitly_normalized(tmp_path, monkeypatch):
    work = tmp_path / "job"
    supplied = {
        "PATH": "/opt/joern/bin:/opt/codeql:/opt/temurin-jre/bin:/usr/bin",
        "JAVA_HOME": "/opt/temurin-jre",
        "HOME": str(work),
        "LC_ALL": "C.UTF-8",
    }
    original = dict(supplied)
    monkeypatch.setenv("JAVASRC_FETCH_DEPENDENCIES", "true")
    monkeypatch.setenv("JAVA_TOOL_OPTIONS", "private-ambient-option")
    env = build_java_static_environment(supplied, workdir=work)
    assert supplied == original
    assert env["PATH"] == JAVA_STATIC_PATH
    assert env["HOME"] == str(work / ".scanipy-java-home")
    assert env["JAVASRC_FETCH_DEPENDENCIES"] == "no-fetch"
    assert "JAVA_TOOL_OPTIONS" not in env
    assert build_java_static_environment(env, workdir=work) == env


@pytest.mark.parametrize("phase", ["parse", "export"])
@pytest.mark.parametrize("mutation", ["unknown", "fetch", "missing", "path"])
def test_both_phase_envs_revalidate_before_lookup(job, monkeypatch, phase, mutation):
    _, work, env, argv = job
    env = dict(env)
    if phase == "export":
        env.update(
            SCANIPY_CPG_BIN_PATH=str(work / "cpg.bin"),
            SCANIPY_EXPORT_JSON_PATH=str(work / "cpg_export.json"),
        )
    if mutation == "unknown":
        env["JAVA_TOOL_OPTIONS"] = "unsafe"
    elif mutation == "fetch":
        env["JAVASRC_FETCH_DEPENDENCIES"] = "0"
    elif mutation == "missing":
        del env["HOME"]
    else:
        env["HOME"] = str(work)
    prohibit_spawn(monkeypatch)
    with pytest.raises(JavaStaticEnvironmentError):
        spawn.secure_run(
            "joern-parse" if phase == "parse" else "joern",
            argv=argv if phase == "parse" else ["--script", frontend.EXPORT_SCRIPT_PATH],
            timeout_s=1,
            env=env,
            cwd=str(work),
            environment_profile=PROFILE,
        )


@pytest.mark.parametrize("target", ["work", "home", "tmp", "output"])
def test_existing_symlink_paths_are_rejected(tmp_path, target):
    real, work = tmp_path / "real", tmp_path / "job"
    real.mkdir()
    if target == "work":
        work.symlink_to(real, target_is_directory=True)
        with pytest.raises(JavaStaticEnvironmentError, match="symlink"):
            build_java_static_environment({}, workdir=work)
        return
    work.mkdir(mode=0o700)
    home = work / ".scanipy-java-home"
    if target == "home":
        home.symlink_to(real, target_is_directory=True)
    else:
        home.mkdir(mode=0o700)
        (home / "tmp" if target == "tmp" else work / "cpg.bin").symlink_to(real)
    with pytest.raises(JavaStaticEnvironmentError, match="symlink"):
        build_java_static_environment({}, workdir=work)


@pytest.mark.parametrize("target", ["work", "home", "tmp"])
def test_unsafe_existing_modes_are_rejected_not_chmodded(job, target):
    _, work, _, _ = job
    path = {
        "work": work,
        "home": work / ".scanipy-java-home",
        "tmp": work / ".scanipy-java-home/tmp",
    }[target]
    path.chmod(0o777)
    with pytest.raises(JavaStaticEnvironmentError, match="permission"):
        build_java_static_environment({}, workdir=work)
    assert path.stat().st_mode & 0o777 == 0o777


def test_shared_java_adapter_forwards_both_profiles_and_preserves_failures(job, monkeypatch):
    source, work, _, _ = job
    calls = []

    def fake(cmd, **kwargs):
        calls.append((cmd, kwargs))
        if cmd[0].endswith("joern-parse"):
            (work / "cpg.bin").write_bytes(b"controlled-graph")
        else:
            (work / "cpg_export.json").write_text(json.dumps(SQLI_JOERN_EXPORT_FIXTURE))
        return subprocess.CompletedProcess(cmd, 0, b"raw-out", b"raw-err")

    monkeypatch.setattr(spawn.subprocess, "run", fake)
    cpg = frontend.parse_source(source, "java", env={}, workdir=work)
    assert len(cpg.nodes) == len(SQLI_JOERN_EXPORT_FIXTURE["nodes"])
    assert len(calls) == 2
    for index, (_, kwargs) in enumerate(calls):
        validate_java_static_environment(
            kwargs["env"], cwd=work, phase="parse" if index == 0 else "export"
        )
    failure = subprocess.CalledProcessError(
        9, calls[0][0], output=b"kept", stderr=b"actual-failure"
    )

    def fail(cmd, **kwargs):
        raise failure

    monkeypatch.setattr(spawn.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError) as raised:
        frontend.parse_source(source, "java", env={}, workdir=work)
    assert raised.value is failure
    assert raised.value.stderr == b"actual-failure"


def test_python_legacy_environment_and_export_remain_unprofiled(tmp_path, monkeypatch):
    calls = []

    def fake(tool, argv, **kwargs):
        calls.append((tool, argv, kwargs))
        if tool == "joern":
            Path(kwargs["env"][frontend.ENV_EXPORT_JSON_PATH]).write_text(
                json.dumps(SQLI_JOERN_EXPORT_FIXTURE)
            )
        return subprocess.CompletedProcess([tool, *argv], 0, b"", b"")

    monkeypatch.setattr(frontend, "secure_run", fake)
    frontend.parse_source(
        tmp_path / "source", "python", env={"TEST_OPAQUE": "kept"}, workdir=tmp_path / "work"
    )
    assert all(item[2].get("environment_profile") is None for item in calls)
    assert all(item[2]["env"]["TEST_OPAQUE"] == "kept" for item in calls)
    assert len(calls[0][1]) == 5


@pytest.mark.parametrize("change", ["relative-source", "source-in-job", "job-in-source", "output"])
def test_java_source_job_and_output_boundaries_before_lookup(job, monkeypatch, change):
    source, work, _, argv = job
    argv = list(argv)
    if change == "relative-source":
        argv[4] = "source"
    elif change == "source-in-job":
        nested = work / "source"
        nested.mkdir()
        argv[4] = str(nested)
    elif change == "job-in-source":
        argv[4] = str(source.parent)
    else:
        argv[3] = str(source / "unwanted.bin")
    prohibit_spawn(monkeypatch)
    with pytest.raises(JavaStaticEnvironmentError):
        run_java(job, argv=argv)


def test_source_root_symlink_and_relative_job_rejected(job, tmp_path, monkeypatch):
    source, _, _, argv = job
    link = tmp_path / "source-link"
    link.symlink_to(source, target_is_directory=True)
    changed = list(argv)
    changed[4] = str(link)
    prohibit_spawn(monkeypatch)
    with pytest.raises(JavaStaticEnvironmentError, match="symlink"):
        run_java(job, argv=changed)
    with pytest.raises(JavaStaticEnvironmentError, match="absolute"):
        build_java_static_environment({}, workdir=Path("relative"))


def test_shared_java_overlap_rejects_before_creating_any_source_content(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    original = source / "Demo.java"
    original.write_bytes(b"class Demo {}\n")
    work = source / "must-not-create"
    prohibit_spawn(monkeypatch)
    with pytest.raises(JavaStaticEnvironmentError, match="overlap"):
        frontend.parse_source(source, "java", env={}, workdir=work)
    assert not work.exists()
    assert list(source.iterdir()) == [original]
    assert original.read_bytes() == b"class Demo {}\n"


def test_private_directories_require_actual_owner(job, monkeypatch):
    _, work, env, _ = job
    original_uid = safety.os.geteuid()
    monkeypatch.setattr(safety.os, "geteuid", lambda: original_uid + 1)
    with pytest.raises(JavaStaticEnvironmentError, match="owned"):
        validate_java_static_environment(env, cwd=work, phase="parse")


def test_existing_home_file_and_output_hardlink_are_preserved(tmp_path):
    work = tmp_path / "job"
    work.mkdir(mode=0o700)
    home = work / ".scanipy-java-home"
    home.write_text("original-user-file")
    with pytest.raises(JavaStaticEnvironmentError):
        build_java_static_environment({}, workdir=work)
    assert home.read_text() == "original-user-file"
    other = tmp_path / "other-job"
    env = build_java_static_environment({}, workdir=other)
    (other / "cpg.bin").hardlink_to(home)
    with pytest.raises(JavaStaticEnvironmentError, match="output"):
        validate_java_static_environment(env, cwd=other, phase="parse")
    assert home.read_text() == "original-user-file"


@pytest.mark.parametrize(
    "tool,argv",
    [
        ("joern", ["--script", "/source/custom.sc"]),
        ("joern-parse", ["--language", "pythonsrc", "--output", "/tmp/graph", "/tmp/source"]),
        ("git", ["status"]),
    ],
)
def test_profile_cannot_select_other_tool_or_script(job, monkeypatch, tool, argv):
    _, work, env, _ = job
    prohibit_spawn(monkeypatch)
    expected = spawn.ArgvAllowlistViolation if tool == "git" else JavaStaticEnvironmentError
    message = "Unprofiled Git" if tool == "git" else "mismatch"
    with pytest.raises(expected, match=message):
        spawn.secure_run(
            tool, argv=argv, timeout_s=1, env=env, cwd=str(work), environment_profile=PROFILE
        )


def test_legacy_harness_env_override_cannot_bypass_shared_java_boundary(job, monkeypatch):
    from scripts.validate_refactor_fingerprints import RealFingerprinter

    source, work, _, _ = job
    prohibit_spawn(monkeypatch)
    real = RealFingerprinter(workdir_root=work, env={"JAVASRC_FETCH_DEPENDENCIES": "false"})
    with pytest.raises(JavaStaticEnvironmentError, match="JAVASRC_FETCH_DEPENDENCIES"):
        real(src_dir=source, language="java", filename="Demo.java", line=1)
    assert real.parse_count == 0
