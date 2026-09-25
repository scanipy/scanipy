"""R16 closed Java child profile; not source coverage or a complete sandbox.

Contract: docs/bhmea/JAVA-STATIC-INVOCATION.md. Trusted launchers own immutable
source and private job boundaries; no arbitrary JVM/loader environment is used.
"""

from __future__ import annotations

import os
import re
import stat
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Literal


class JoernEnvironmentProfile(StrEnum):
    JAVA_STATIC_V1 = "scanipy-java-static-env/1"


class JavaStaticEnvironmentError(ValueError):
    """Unsupported Java invocation/environment/path, rejected before spawn."""


JAVA_STATIC_PATH = "/opt/joern:/opt/joern/bin:/opt/codeql:/opt/temurin-jre/bin:/usr/bin:/bin"
JAVA_STATIC_HOME = "/opt/temurin-jre"
_WORKER_INPUT_PATH = "/opt/joern/bin:/opt/codeql:/opt/temurin-jre/bin:/usr/bin"
JAVA_STATIC_EXPORT_SCRIPT = "/opt/joern/scripts/export_cpg.sc"
JavaPhase = Literal["parse", "export"]


def _field_error(field: str) -> JavaStaticEnvironmentError:
    # Do not echo supplied values (or arbitrary control-bearing key strings).
    safe_field = field if re.fullmatch(r"[A-Z_][A-Z0-9_]{0,127}", field) else "environment-key"
    return JavaStaticEnvironmentError(f"invalid Java static environment field: {safe_field}")


def _path(path: Path) -> Path:
    if not isinstance(path, Path) or path.anchor != "/" or ".." in path.parts:
        raise JavaStaticEnvironmentError("Java paths must be absolute and normalized")
    if len(path.parts) < 3:
        raise JavaStaticEnvironmentError("Java job/source path must not be a filesystem root")
    return path


def _no_symlink_components(path: Path) -> None:
    for component in (*reversed(path.parents), path):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode):
            raise JavaStaticEnvironmentError("symlink in Java job/source path")
        if component != path and not stat.S_ISDIR(info.st_mode):
            raise JavaStaticEnvironmentError("non-directory Java path ancestor")


def _owned_directory(path: Path, *, private: bool) -> os.stat_result:
    _no_symlink_components(path)
    try:
        info = path.lstat()
    except OSError as exc:
        raise JavaStaticEnvironmentError("required Java directory is unavailable") from exc
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
        raise JavaStaticEnvironmentError("Java directory must be owned by the worker")
    mode = stat.S_IMODE(info.st_mode)
    if (private and mode != 0o700) or mode & 0o022 or mode & 0o300 != 0o300:
        raise JavaStaticEnvironmentError("unsafe Java directory permissions")
    return info


def _check_outputs(workdir: Path) -> None:
    for name in ("cpg.bin", "cpg_export.json"):
        target = workdir / name
        _no_symlink_components(target)
        try:
            info = target.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1:
            raise JavaStaticEnvironmentError("unsafe existing Java output target")


def _make_directory(path: Path, *, parents: bool = False) -> None:
    try:
        path.mkdir(mode=0o700, parents=parents, exist_ok=True)
    except OSError as exc:
        raise JavaStaticEnvironmentError("Java runtime directory cannot be created safely") from exc


def _expected(workdir: Path, phase: JavaPhase) -> dict[str, str]:
    _path(workdir)
    if phase not in {"parse", "export"}:
        raise JavaStaticEnvironmentError("unsupported Java profile phase")
    home = workdir / ".scanipy-java-home"
    expected = {
        "PATH": JAVA_STATIC_PATH,
        "JAVA_HOME": JAVA_STATIC_HOME,
        "HOME": str(home),
        "TMPDIR": str(home / "tmp"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "JAVASRC_FETCH_DEPENDENCIES": "no-fetch",
    }
    if phase == "export":
        expected.update(
            SCANIPY_CPG_BIN_PATH=str(workdir / "cpg.bin"),
            SCANIPY_EXPORT_JSON_PATH=str(workdir / "cpg_export.json"),
        )
    return expected


def _mapping(env: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(env, Mapping):
        raise JavaStaticEnvironmentError("Java environment must be an explicit mapping")
    copied: dict[str, str] = {}
    for key, value in env.items():
        if not isinstance(key, str):
            raise JavaStaticEnvironmentError("Java environment keys must be text")
        if not isinstance(value, str):
            raise _field_error(key)
        copied[key] = value
    return copied


def build_java_static_environment(supplied: Mapping[str, str], *, workdir: Path) -> dict[str, str]:
    """Validate reviewed inputs, create private runtime dirs, return a new env.

    Caller/ambient dictionaries are never mutated or inherited. Existing unsafe
    paths are rejected, not chmod-ed. Filesystem races remain a launcher duty.
    """
    expected = _expected(workdir, "parse")
    source = _mapping(supplied)
    for key, value in source.items():
        if key not in expected:
            raise _field_error(key)
        accepted = {expected[key]}
        if key == "PATH":
            accepted.add(_WORKER_INPUT_PATH)
        elif key == "HOME":
            accepted.add(str(workdir))
        if value not in accepted:
            raise _field_error(key)
    _no_symlink_components(workdir)
    _make_directory(workdir, parents=True)
    _owned_directory(workdir, private=False)
    for directory in (Path(expected["HOME"]), Path(expected["TMPDIR"])):
        _no_symlink_components(directory)
        _make_directory(directory)
        _owned_directory(directory, private=True)
    validate_java_static_environment(expected, cwd=workdir, phase="parse")
    return expected


def validate_java_static_environment(
    env: Mapping[str, str], *, cwd: Path, phase: JavaPhase
) -> None:
    """Reject every non-profile key/value and unsafe job path before a launch."""
    expected = _expected(cwd, phase)
    actual = _mapping(env)
    for key in actual.keys() | expected.keys():
        if key not in actual or key not in expected or actual[key] != expected[key]:
            raise _field_error(key)
    _owned_directory(cwd, private=False)
    _owned_directory(Path(expected["HOME"]), private=True)
    _owned_directory(Path(expected["TMPDIR"]), private=True)
    _check_outputs(cwd)


def validate_java_parse_paths(*, source: Path, output: Path, cwd: Path) -> None:
    """Check the source-root/job relationship, not all source-tree contents."""
    _path(source)
    _path(output)
    _no_symlink_components(source)
    if not source.is_dir():
        raise JavaStaticEnvironmentError("Java source root must be an existing directory")
    if source.is_relative_to(cwd) or cwd.is_relative_to(source):
        raise JavaStaticEnvironmentError("Java source root and job directory must not overlap")
    if output != cwd / "cpg.bin":
        raise JavaStaticEnvironmentError("Java output must be the exact job cpg.bin path")


def observe_java_static_environment(
    env: Mapping[str, str], *, cwd: Path, phase: JavaPhase
) -> dict[str, object]:
    """Safe actual-child projection; not generic env dumping or attestation."""
    validate_java_static_environment(env, cwd=cwd, phase=phase)
    directories = {}
    for name, path in (("workdir", cwd), ("home", Path(env["HOME"])), ("tmp", Path(env["TMPDIR"]))):
        info = _owned_directory(path, private=name != "workdir")
        directories[name] = {
            "path": str(path),
            "uid": info.st_uid,
            "mode": f"{stat.S_IMODE(info.st_mode):04o}",
        }
    return {
        "profile": JoernEnvironmentProfile.JAVA_STATIC_V1.value,
        "phase": phase,
        "effective_environment": dict(env),
        "directories": directories,
    }
