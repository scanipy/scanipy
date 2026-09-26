"""Pure, closed Docker create rendering; no runtime or execution authority.

See docs/bhmea/LOCAL-RUNTIME-DOCKER-POLICY.md sections 3 and 4. The installed
factory, image/inspect validator, kernel observers and controller remain
separate prerequisites. This module performs no filesystem or process work.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, fields
from typing import cast

from tools.worker.bounded_process import FrozenInvocation, ProcessValidationError

_ERROR = "invalid runtime Docker create specification"
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
_IMAGE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CONTROL = "/run/scanipy-control"
_WORK = "/run/scanipy-work"
_RESERVED = (
    "/proc",
    "/sys",
    "/dev",
    "/etc/hosts",
    "/etc/hostname",
    "/etc/resolv.conf",
    _CONTROL,
    _WORK,
)
_EMPTY_SHA256 = hashlib.sha256(b"").digest()


class RuntimeDockerPolicyError(ValueError):
    """Fixed public failure message; caller data is not rendered in errors."""


def _require(condition: bool) -> None:
    if not condition:
        raise RuntimeDockerPolicyError(_ERROR)


@dataclass(frozen=True, slots=True, repr=False)
class RuntimeDockerCreateSpec:
    """Untrusted data carrier, not proof of an installed runtime or permission."""

    purpose: str
    docker_executable: str
    python_executable: str
    worker_path: str
    bootstrap_path: str
    domain_profile_path: str
    host_work_root: str
    runtime_roots: tuple[str, ...]
    uid: int
    gid: int
    deployment_id: str
    installation_id: str
    attempt_id: str
    operation_id: str
    installation_generation: int
    image_config_id: str
    request_digest: bytes
    controller_profile_sha256: bytes
    domain_profile_sha256: bytes
    inventory_sha256: bytes
    program_digest: bytes
    launch_sha256: bytes


_FIELDS = tuple(definition.name for definition in fields(RuntimeDockerCreateSpec))


def _text(value: object, maximum: int) -> str:
    _require(type(value) is str)
    text = cast(str, value)
    # Character count first: never encode an oversized or callback-bearing value.
    _require(0 < len(text) <= maximum)
    try:
        _require(len(text.encode("utf-8", errors="strict")) <= maximum)
    except UnicodeError as error:
        raise RuntimeDockerPolicyError(_ERROR) from error
    return text


def _path(value: object) -> str:
    text = _text(value, 4096)
    _require(text.startswith("/") and text != "/" and "\\" not in text)
    _require(not any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in text))
    _require(all(part not in ("", ".", "..") for part in text[1:].split("/")))
    return text


def _uuid(value: object) -> str:
    text = _text(value, 36)
    _require(_UUID.fullmatch(text) is not None)
    return text


def _digest(value: object) -> bytes:
    _require(type(value) is bytes and len(value) == 32)
    return cast(bytes, value)


def _integer(value: object, maximum: int) -> int:
    _require(type(value) is int and 1 <= value <= maximum)
    return cast(int, value)


def _copy_spec(value: RuntimeDockerCreateSpec) -> RuntimeDockerCreateSpec:
    _require(type(value) is RuntimeDockerCreateSpec)
    try:
        raw = {name: object.__getattribute__(value, name) for name in _FIELDS}
    except AttributeError as error:
        raise RuntimeDockerPolicyError(_ERROR) from error
    purpose = _text(raw["purpose"], 32)
    _require(purpose in ("accepted-verifier", "python-syntax"))
    image = _text(raw["image_config_id"], 71)
    _require(_IMAGE.fullmatch(image) is not None)
    roots = raw["runtime_roots"]
    _require(type(roots) is tuple and 3 <= len(roots) <= 9)
    private_roots = tuple(_path(root) for root in roots)
    _require(len(set(private_roots)) == len(private_roots))
    return RuntimeDockerCreateSpec(
        purpose=purpose,
        docker_executable=_path(raw["docker_executable"]),
        python_executable=_path(raw["python_executable"]),
        worker_path=_path(raw["worker_path"]),
        bootstrap_path=_path(raw["bootstrap_path"]),
        domain_profile_path=_path(raw["domain_profile_path"]),
        host_work_root=_path(raw["host_work_root"]),
        runtime_roots=private_roots,
        uid=_integer(raw["uid"], 2**31 - 1),
        gid=_integer(raw["gid"], 2**31 - 1),
        deployment_id=_uuid(raw["deployment_id"]),
        installation_id=_uuid(raw["installation_id"]),
        attempt_id=_uuid(raw["attempt_id"]),
        operation_id=_uuid(raw["operation_id"]),
        installation_generation=_integer(raw["installation_generation"], 2**63 - 1),
        image_config_id=image,
        request_digest=_digest(raw["request_digest"]),
        controller_profile_sha256=_digest(raw["controller_profile_sha256"]),
        domain_profile_sha256=_digest(raw["domain_profile_sha256"]),
        inventory_sha256=_digest(raw["inventory_sha256"]),
        program_digest=_digest(raw["program_digest"]),
        launch_sha256=_digest(raw["launch_sha256"]),
    )


def _within(parent: str, path: str) -> bool:
    return parent == path or path.startswith(parent + "/")


def _overlap(left: str, right: str) -> bool:
    return _within(left, right) or _within(right, left)


def _parent(path: str) -> str:
    return path.rsplit("/", 1)[0] or "/"


def _mounts(spec: RuntimeDockerCreateSpec, control_source: str) -> tuple[tuple[str, str], ...]:
    roots = spec.runtime_roots
    files = tuple(sorted({spec.python_executable, spec.worker_path, spec.bootstrap_path}))
    domain = spec.domain_profile_path
    _require(
        any(root != spec.bootstrap_path and _within(root, spec.bootstrap_path) for root in roots)
    )
    for path in (*roots, *files, domain):
        _require(not any(_overlap(path, reserved) for reserved in _RESERVED))
        _require(not _overlap(path, spec.host_work_root))
    for root in roots:
        for path in files:
            # Files may be below roots, but cannot masquerade as their parent.
            _require(not _within(path, root))
        _require(not _overlap(domain, root))
    for index, path in enumerate(files):
        _require(not _overlap(domain, path))
        _require(not any(_overlap(path, other) for other in files[index + 1 :]))
    domain_parent = _parent(domain)
    _require(domain_parent != "/")
    _require(not any(_overlap(domain_parent, root) for root in roots))
    _require(
        not any(_overlap(domain_parent, work) for work in (spec.host_work_root, _CONTROL, _WORK))
    )
    cover = tuple(
        root for root in roots if not any(other != root and _within(other, root) for other in roots)
    )
    bindings = {path: path for path in cover}
    for path in files:
        if not any(_within(root, path) for root in cover):
            bindings[path] = path
    bindings[domain] = domain
    bindings[_CONTROL] = control_source
    _require(len(bindings) <= 16)
    return tuple(
        (bindings[destination], destination)
        for destination in sorted(bindings, key=lambda path: path.encode("utf-8"))
    )


def _csv_mount(source: str, destination: str) -> str:
    parts = (
        "type=bind",
        "source=" + source,
        "target=" + destination,
        "readonly",
        "bind-propagation=rprivate",
        "bind-recursive=readonly",
    )
    size = len(parts) - 1
    for part in parts:
        size += len(part.encode("utf-8"))
        if "," in part or '"' in part:
            size += 2 + part.count('"')
    _require(size <= 8192)
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="").writerow(parts)
    result = output.getvalue()
    _require(len(result.encode("utf-8")) == size)
    return result


def _invocation(argv: list[str], environment: dict[str, str], cwd: str) -> FrozenInvocation:
    _require(len(argv) <= 256)
    sizes = [len(value.encode("utf-8")) for value in argv]
    _require(all(size <= 8192 for size in sizes) and sum(size + 1 for size in sizes) <= 65536)
    _require(len(environment) == 10)
    _require(
        sum(len(key.encode()) + len(value.encode()) + 2 for key, value in environment.items())
        <= 16384
    )
    try:
        return FrozenInvocation(
            tuple(argv), tuple(sorted(environment.items())), cwd, 0, _EMPTY_SHA256
        )
    except ProcessValidationError as error:
        raise RuntimeDockerPolicyError(_ERROR) from error


def render_runtime_inner_invocation(
    *,
    purpose: str,
    python_executable: str,
    worker_path: str,
    domain_profile_path: str,
    domain_profile_sha256: bytes,
    attempt_id: str,
    stdin_bytes: int,
    stdin_sha256: bytes,
) -> FrozenInvocation:
    """Render intended inner fields, without hashing, observing or launching."""
    purpose = _text(purpose, 32)
    _require(purpose in ("accepted-verifier", "python-syntax"))
    executable = _path(python_executable)
    worker = _path(worker_path)
    profile = _path(domain_profile_path)
    profile_hash = _digest(domain_profile_sha256)
    attempt = _uuid(attempt_id)
    size = _integer(stdin_bytes, 2621440 if purpose == "accepted-verifier" else 263244)
    input_hash = _digest(stdin_sha256)
    cwd = _WORK + "/" + attempt
    _require(all(not _overlap(cwd, path) for path in (executable, worker, profile)))
    argv = [executable, "-I", "-S", "-B", "-X"]
    if purpose == "accepted-verifier":
        argv.extend(("utf8", "-X"))
    argv.extend(("pycache_prefix=" + cwd + "/pycache", worker))
    environment = {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
    if purpose == "accepted-verifier":
        argv.extend(("--profile", profile, "--profile-sha256", profile_hash.hex()))
        environment["TZ"] = "UTC"
    else:
        # Fixed container-private scratch, not a shared host temporary directory.
        environment.update(HOME=cwd + "/home", TMPDIR=cwd + "/tmp")  # noqa: S108
    _require(len(argv) <= 64)
    sizes = [len(_text(value, 8192).encode("utf-8")) for value in argv]
    _require(sum(size + 1 for size in sizes) <= 65536)
    _require(len(environment) <= 16)
    _require(
        sum(
            len(_text(key, 128).encode("utf-8")) + len(_text(value, 8192).encode("utf-8")) + 2
            for key, value in environment.items()
        )
        <= 16384
    )
    try:
        return FrozenInvocation(
            tuple(argv), tuple(sorted(environment.items())), cwd, size, input_hash
        )
    except ProcessValidationError as error:
        raise RuntimeDockerPolicyError(_ERROR) from error


def render_runtime_docker_create(spec: RuntimeDockerCreateSpec) -> FrozenInvocation:
    """Render only the approved create intent; perform no discovery or launch."""
    spec = _copy_spec(spec)
    attempt = _path(spec.host_work_root + "/" + spec.attempt_id)
    children = {
        name: _path(attempt + "/" + name)
        for name in ("control", "docker-config", "cli-home", "cli-tmp", "cli-bin")
    }
    mounts = _mounts(spec, children["control"])
    name = "scanipy-runtime-" + spec.attempt_id.replace("-", "")
    memory = "134217728" if spec.purpose == "accepted-verifier" else "268435456"
    argv = [
        spec.docker_executable,
        "--host",
        "unix:///run/docker.sock",
        "--config",
        children["docker-config"],
        "container",
        "create",
        "--pull",
        "never",
        "--name",
        name,
        "--hostname",
        name,
        "--user",
        f"{spec.uid}:{spec.gid}",
        "--network",
        "none",
        "--ipc",
        "private",
        "--cgroupns",
        "private",
        "--userns",
        "host",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--security-opt",
        "seccomp=builtin",
        "--security-opt",
        "apparmor=docker-default",
        "--runtime",
        "runc",
        "--restart",
        "no",
        "--init=false",
        "--log-driver",
        "none",
        "--no-healthcheck",
        "--interactive",
        "--attach",
        "stdin",
        "--attach",
        "stdout",
        "--attach",
        "stderr",
        "--memory",
        memory,
        "--memory-swap",
        memory,
        "--cpu-period",
        "100000",
        "--cpu-quota",
        "100000",
        "--pids-limit",
        "16",
        "--shm-size",
        "65536",
        "--workdir",
        "/",
        "--entrypoint",
        spec.python_executable,
    ]
    labels = {
        "schema": "scanipy-docker29-pipe-config/1",
        "deployment-id": spec.deployment_id,
        "installation-id": spec.installation_id,
        "generation": str(spec.installation_generation),
        "attempt-id": spec.attempt_id,
        "operation-id": spec.operation_id,
        "request-digest": spec.request_digest.hex(),
        "outer-profile-sha256": spec.controller_profile_sha256.hex(),
        "domain-profile-sha256": spec.domain_profile_sha256.hex(),
        "inventory-sha256": spec.inventory_sha256.hex(),
        "program-digest": spec.program_digest.hex(),
    }
    for key, value in sorted(labels.items()):
        key = "io.scanipy.runtime." + key
        _require(len(key) <= 64 and len(value) <= 64)
        argv.extend(("--label", key + "=" + value))
    container_environment = {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
        "PATH": "",
        "HOSTNAME": name,
    }
    for key, value in sorted(container_environment.items()):
        argv.extend(("--env", key + "=" + value))
    for source, destination in mounts:
        argv.extend(("--mount", _csv_mount(source, destination)))
    for mount in (
        "/dev:rw,nosuid,noexec,dev,strictatime,mode=755,uid=0,gid=0,size=67108864,nr_inodes=16384",
        # Exact container-only policy target, not access to a host temporary file.
        "/dev/shm:rw,nosuid,noexec,nodev,mode=1777,uid=0,gid=0,size=65536,nr_inodes=16384",  # noqa: S108
        _WORK
        + ":rw,nosuid,nodev,noexec,size=8388608,nr_inodes=1024,mode=0700,"
        + f"uid={spec.uid},gid={spec.gid}",
    ):
        argv.extend(("--tmpfs", mount))
    cache = _WORK + "/bootstrap-" + spec.attempt_id + "/pycache"
    argv.extend(
        (
            spec.image_config_id,
            "-I",
            "-S",
            "-B",
            "-X",
            "utf8",
            "-X",
            "pycache_prefix=" + cache,
            spec.bootstrap_path,
            "--launch",
            _CONTROL + "/launch.json",
            "--launch-sha256",
            spec.launch_sha256.hex(),
        )
    )
    environment = {
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
        "HOME": children["cli-home"],
        "TMPDIR": children["cli-tmp"],
        "PATH": children["cli-bin"],
        "DOCKER_API_VERSION": "1.52",
        "DOCKER_CLI_HOOKS": "false",
        "DOCKER_CLI_HINTS": "false",
        "OTEL_SDK_DISABLED": "true",
    }
    return _invocation(argv, environment, attempt)
