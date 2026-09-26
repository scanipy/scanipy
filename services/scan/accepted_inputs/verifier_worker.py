"""Internal fixed verifier worker; direct runs establish no operational authority.

Only trusted bootstrap imports precede resource/profile checks. This entrypoint
does not install trust, open a database, execute target code, or launch children.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import resource
import stat
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import PosixPath
from typing import Any

_MAX_PROFILE = 65536
_MAX_INPUT = 2621440
_MAX_OUTPUT = 16384
_ENVIRONMENT = {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC"}
_RESOURCE_LIMITS = (
    (resource.RLIMIT_AS, (134217728, 134217728)),
    (resource.RLIMIT_CPU, (2, 2)),
    (resource.RLIMIT_NOFILE, (32, 32)),
    (resource.RLIMIT_FSIZE, (0, 0)),
    (resource.RLIMIT_CORE, (0, 0)),
)


class _RuntimeError(ValueError):
    """Private fixed failure, never echo a path/environment/input."""


def _require(condition: bool) -> None:
    if not condition:
        raise _RuntimeError("runtime-unsupported")


def _path(value: object) -> PosixPath:
    _require(type(value) is str)
    assert isinstance(value, str)
    _require(0 < len(value) <= 4096 and value.startswith("/") and value != "/")
    _require(
        "\\" not in value and not any(ord(item) < 32 or 127 <= ord(item) <= 159 for item in value)
    )
    _require(len(value.encode("utf-8")) <= 4096)
    result = PosixPath(value)
    _require(
        str(result) == value and all(part not in ("", ".", "..") for part in value.split("/")[1:])
    )
    return result


@contextmanager
def _owned_fds() -> Iterator[list[int]]:
    """Close each owned number once, retaining primary and cleanup failures."""
    owned: list[int] = []
    primary: BaseException | None = None
    prior: BaseException | None = None
    try:
        yield owned
    except BaseException as error:
        primary = error
        prior = error.__cause__ or error.__context__
    failures: list[BaseException] = []
    while owned:
        descriptor = owned.pop()  # A failed close may already release/reuse it.
        try:
            os.close(descriptor)
        except BaseException as error:
            failures.append(error)
    if primary is None and failures:
        primary = next(
            (error for error in failures if not isinstance(error, Exception)), failures[0]
        )
        failures.remove(primary)
        prior = primary.__cause__ or primary.__context__
    if primary is not None:
        if failures:
            raise primary from BaseExceptionGroup(
                "verifier descriptor cleanup failed", ([prior] if prior else []) + failures
            )
        raise primary


def _directory(path: PosixPath, *, private: bool = False) -> None:
    # Descriptor walks refuse symlink components. A trusted nonconcurrent host
    # writer and separately enforced controller are still required.
    with _owned_fds() as owned:
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        owned.append(fd)
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            owned.append(child)
            owned.remove(fd)
            os.close(fd)
            fd = child
        metadata = os.fstat(fd)
        _require(stat.S_ISDIR(metadata.st_mode))
        if private:
            _require(metadata.st_uid == os.geteuid() and stat.S_IMODE(metadata.st_mode) == 0o700)
        else:
            _require(metadata.st_uid in (0, os.geteuid()) and not metadata.st_mode & 0o022)


def _read_file(path: PosixPath, maximum: int, *, private: bool = False) -> bytes:
    _directory(path.parent, private=private)
    with _owned_fds() as owned:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        owned.append(fd)
        before = os.fstat(fd)
        _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1)
        _require(before.st_uid in ((os.geteuid(),) if private else (0, os.geteuid())))
        _require(not before.st_mode & (0o077 if private else 0o022))
        _require(0 < before.st_size <= maximum)
        chunks = []
        total = 0
        while True:
            part = os.read(fd, min(65536, maximum + 1 - total))
            if not part:
                break
            total += len(part)
            _require(total <= maximum)
            chunks.append(part)
        after = os.fstat(fd)
        _require(
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        )
        _require(total == before.st_size)
        return b"".join(chunks)


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        _require(key not in value)
        value[key] = item
    return value


def _overlaps(left: PosixPath, right: PosixPath) -> bool:
    return left == right or left in right.parents or right in left.parents


def prepare_runtime(arguments: tuple[str, ...]) -> tuple[bytes, dict[str, Any]]:
    """Validate the pinned diagnostic/controlled runtime before reading stdin."""
    _require(type(arguments) is tuple and len(arguments) == 5)
    _require(arguments[1] == "--profile" and arguments[3] == "--profile-sha256")
    _require(type(arguments[4]) is str and re.fullmatch(r"[0-9a-f]{64}", arguments[4]) is not None)
    _require(
        sys.platform == "linux"
        and sys.implementation.name == "cpython"
        and sys.version_info[:2] == (3, 11)
    )
    _require(
        sys.flags.isolated == 1
        and sys.flags.no_site == 1
        and sys.flags.utf8_mode == 1
        and sys.dont_write_bytecode
    )
    _require(dict(os.environ) == _ENVIRONMENT)
    for kind, limits in _RESOURCE_LIMITS:
        resource.setrlimit(kind, limits)
        _require(resource.getrlimit(kind) == limits)
    cwd = _path(str(PosixPath.cwd()))
    _directory(cwd, private=True)
    cache = cwd / "pycache"
    _require(sys.pycache_prefix == str(cache))
    _directory(cache, private=True)
    with os.scandir(cache) as entries:
        _require(next(entries, None) is None)
    profile_path = _path(arguments[2])
    profile_bytes = _read_file(profile_path, _MAX_PROFILE, private=True)
    _require(hashlib.sha256(profile_bytes).hexdigest() == arguments[4])
    # This is bounded, externally hash-pinned configuration, not request JSON.
    # Full closed canonical validation follows immediately after trusted imports.
    profile = json.loads(profile_bytes.decode("utf-8"), object_pairs_hook=_pairs)
    _require(type(profile) is dict)
    _require(profile.get("schema") == "scanipy-accepted-verifier-runtime/1")
    _require(profile.get("implementation") == "cpython")
    _require(
        profile.get("python_version") == ".".join(str(value) for value in sys.version_info[:3])
    )
    _require(profile.get("resource_profile") == "scanipy-verifier-limits/1")
    executable = _path(profile["python_executable"])
    script = _path(profile["worker_script"])
    _require(str(executable) == sys.executable and str(script) == arguments[0])
    _require(
        hashlib.sha256(_read_file(executable, 134217728)).hexdigest()
        == profile["python_executable_sha256"]
    )
    _require(
        hashlib.sha256(_read_file(script, 1048576)).hexdigest() == profile["worker_script_sha256"]
    )
    application = _path(profile["application_root"])
    stdlib, dependencies = profile["stdlib_roots"], profile["dependency_roots"]
    _require(
        type(stdlib) is list
        and type(dependencies) is list
        and 1 <= len(stdlib) <= 4
        and 1 <= len(dependencies) <= 4
    )
    roots = (
        [_path(value) for value in stdlib]
        + [application]
        + [_path(value) for value in dependencies]
    )
    _require(len(set(roots)) == len(roots))
    work_root = _path(profile["work_root"])
    _directory(work_root, private=True)
    _require(cwd.parent == work_root)
    for root in roots:
        _directory(root)
        _require(not _overlaps(root, cwd) and not _overlaps(root, profile_path.parent))
    _require(not _overlaps(cwd, profile_path.parent))
    sys.path[:] = [str(path) for path in roots]
    return profile_bytes, profile


def _bootstrap_failure() -> int:
    # No request has been read: operation/mode/full-input digest stay unknown.
    value = {
        "schema": "scanipy-accepted-verifier-result/1",
        "operation_id": None,
        "request_sha256": None,
        "mode": None,
        "status": "rejected",
        "failure_code": "runtime-unsupported",
        "checks": None,
    }
    sys.stdout.buffer.write(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")
    )
    sys.stdout.buffer.flush()
    return 2


def main() -> int:
    try:
        profile_bytes, profile = prepare_runtime(tuple(sys.argv))
    except (Exception, MemoryError):
        return _bootstrap_failure()
    from services.scan.accepted_inputs import codec as codec
    from services.scan.accepted_inputs import models as models
    from services.scan.accepted_inputs import schemas as schemas
    from services.scan.accepted_inputs.verify import verify_request

    operation_id = mode = request_digest = None
    try:
        codec.decode_document(profile_bytes, schemas.RUNTIME)
        data = sys.stdin.buffer.read(_MAX_INPUT + 1)
        if len(data) > _MAX_INPUT:
            raise schemas.VerificationError("invalid-input")
        request_digest = hashlib.sha256(data).hexdigest()
        request = codec.decode_request(data)
        operation_id, mode = request.operation_id, request.mode
        schemas.require(
            request.verifier_artifact_digest == profile["verifier_artifact_digest"],
            "runtime-unsupported",
        )
        checks = verify_request(request)
        result = models.VerificationResult(
            operation_id, request_digest, mode, "verified", None, checks
        )
        exit_code = 0
    except schemas.VerificationError as error:
        result = models.VerificationResult(
            operation_id, request_digest, mode, "rejected", error.code, None
        )
        exit_code = 2
    except Exception:
        result = models.VerificationResult(
            operation_id, request_digest, mode, "rejected", "internal-error", None
        )
        exit_code = 2
    encoded = codec.encode_result(result)
    if len(encoded) > _MAX_OUTPUT:
        raise _RuntimeError("internal-error")
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
