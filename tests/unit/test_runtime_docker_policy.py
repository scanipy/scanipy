"""Pure command-intent falsifiers; never Docker, filesystem or runtime approval."""

from __future__ import annotations

import csv
import hashlib
import os
import subprocess
import time
from dataclasses import fields, replace
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from tools.worker import runtime_docker_policy as policy
from tools.worker.bounded_process import FrozenInvocation

pytestmark = pytest.mark.unit

ATTEMPT = "33333333-3333-4333-8333-333333333333"
NAME = "scanipy-runtime-" + ATTEMPT.replace("-", "")
ATTEMPT_ROOT = "/private/jobs/" + ATTEMPT
PATH_FIELDS = (
    "docker_executable",
    "python_executable",
    "worker_path",
    "bootstrap_path",
    "domain_profile_path",
    "host_work_root",
)
UUID_FIELDS = ("deployment_id", "installation_id", "attempt_id", "operation_id")
DIGEST_FIELDS = (
    "request_digest",
    "controller_profile_sha256",
    "domain_profile_sha256",
    "inventory_sha256",
    "program_digest",
    "launch_sha256",
)


def make_spec(**changes: Any) -> policy.RuntimeDockerCreateSpec:
    # Every pin/path is diagnostic data. No fixture installs or executes it.
    original = policy.RuntimeDockerCreateSpec(
        purpose="accepted-verifier",
        docker_executable="/trusted/bin/docker",
        python_executable="/trusted/bin/python",
        worker_path="/runtime/application/verifier_worker.py",
        bootstrap_path="/runtime/application/bootstrap.py",
        domain_profile_path="/private/metadata/domain.json",
        host_work_root="/private/jobs",
        runtime_roots=("/runtime/application", "/runtime/dependency", "/runtime/stdlib"),
        uid=1000,
        gid=1001,
        deployment_id="11111111-1111-4111-8111-111111111111",
        installation_id="22222222-2222-4222-8222-222222222222",
        attempt_id=ATTEMPT,
        operation_id="44444444-4444-4444-8444-444444444444",
        installation_generation=7,
        image_config_id="sha256:" + "a" * 64,
        request_digest=b"r" * 32,
        controller_profile_sha256=b"c" * 32,
        domain_profile_sha256=b"d" * 32,
        inventory_sha256=b"i" * 32,
        program_digest=b"p" * 32,
        launch_sha256=b"l" * 32,
    )
    return replace(original, **changes)


def render(**changes: Any) -> FrozenInvocation:
    return policy.render_runtime_docker_create(make_spec(**changes))


def option_values(invocation: FrozenInvocation, option: str) -> list[str]:
    return [
        invocation.argv[index + 1] for index, value in enumerate(invocation.argv) if value == option
    ]


def decoded_mounts(invocation: FrozenInvocation) -> list[tuple[str, str]]:
    result = []
    for encoded in option_values(invocation, "--mount"):
        # The same RFC-style CSV field grammar, not an actual Docker parser run.
        parts = next(csv.reader([encoded], strict=True))
        assert len(parts) == 6
        assert parts[0] == "type=bind"
        assert parts[1].startswith("source=")
        assert parts[2].startswith("target=")
        assert parts[3:] == ["readonly", "bind-propagation=rprivate", "bind-recursive=readonly"]
        result.append((parts[1][7:], parts[2][7:]))
    return result


def reject(**changes: Any) -> policy.RuntimeDockerPolicyError:
    with pytest.raises(policy.RuntimeDockerPolicyError) as captured:
        render(**changes)
    assert str(captured.value) == "invalid runtime Docker create specification"
    return captured.value


@pytest.mark.parametrize(
    ("purpose", "memory"),
    [("accepted-verifier", "134217728"), ("python-syntax", "268435456")],
)
def test_exact_fixed_command_and_real_shared_type(purpose: str, memory: str) -> None:
    value = render(purpose=purpose)
    assert type(value) is FrozenInvocation
    expected = (
        "/trusted/bin/docker",
        "--host",
        "unix:///run/docker.sock",
        "--config",
        ATTEMPT_ROOT + "/docker-config",
        "container",
        "create",
        "--pull",
        "never",
        "--name",
        NAME,
        "--hostname",
        NAME,
        "--user",
        "1000:1001",
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
        "/trusted/bin/python",
    )
    assert value.argv[: len(expected)] == expected
    assert value.argv[-13:] == (
        "sha256:" + "a" * 64,
        "-I",
        "-S",
        "-B",
        "-X",
        "utf8",
        "-X",
        "pycache_prefix=/run/scanipy-work/bootstrap-" + ATTEMPT + "/pycache",
        "/runtime/application/bootstrap.py",
        "--launch",
        "/run/scanipy-control/launch.json",
        "--launch-sha256",
        (b"l" * 32).hex(),
    )
    # Exhaust the middle too: no arbitrary or hidden additional flags.
    middle = value.argv[len(expected) : -13]
    counts = {"--label": 11, "--env": 5, "--mount": 6, "--tmpfs": 3}
    expected_order = [flag for flag, count in counts.items() for _ in range(count)]
    assert list(middle[::2]) == expected_order
    assert len(middle) == 2 * sum(counts.values())
    assert value.cwd == ATTEMPT_ROOT
    assert value.stdin_bytes == 0
    assert value.stdin_sha256 == hashlib.sha256(b"").digest()


def test_exact_sorted_labels_and_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKER_HOST", "tcp://untrusted.invalid:2375")
    monkeypatch.setenv("DOCKER_CONTEXT", "untrusted-context")
    monkeypatch.setenv("PYTHONPATH", "/untrusted")
    monkeypatch.setenv("HTTP_PROXY", "untrusted-proxy")
    value = render()
    expected_labels = {
        "schema": "scanipy-docker29-pipe-config/1",
        "deployment-id": make_spec().deployment_id,
        "installation-id": make_spec().installation_id,
        "generation": "7",
        "attempt-id": ATTEMPT,
        "operation-id": make_spec().operation_id,
        "request-digest": (b"r" * 32).hex(),
        "outer-profile-sha256": (b"c" * 32).hex(),
        "domain-profile-sha256": (b"d" * 32).hex(),
        "inventory-sha256": (b"i" * 32).hex(),
        "program-digest": (b"p" * 32).hex(),
    }
    assert option_values(value, "--label") == [
        "io.scanipy.runtime." + key + "=" + label for key, label in sorted(expected_labels.items())
    ]
    assert option_values(value, "--env") == [
        "HOSTNAME=" + NAME,
        "LANG=C.UTF-8",
        "LC_ALL=C.UTF-8",
        "PATH=",
        "TZ=UTC",
    ]
    assert value.environment == tuple(
        sorted(
            {
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "TZ": "UTC",
                "HOME": ATTEMPT_ROOT + "/cli-home",
                "TMPDIR": ATTEMPT_ROOT + "/cli-tmp",
                "PATH": ATTEMPT_ROOT + "/cli-bin",
                "DOCKER_API_VERSION": "1.52",
                "DOCKER_CLI_HOOKS": "false",
                "DOCKER_CLI_HINTS": "false",
                "OTEL_SDK_DISABLED": "true",
            }.items()
        )
    )


def test_exact_bounded_tmpfs_policy() -> None:
    assert option_values(render(), "--tmpfs") == [
        "/dev:rw,nosuid,noexec,dev,strictatime,mode=755,uid=0,gid=0,size=67108864,nr_inodes=16384",
        "/dev/shm:rw,nosuid,noexec,nodev,mode=1777,uid=0,gid=0,size=65536,nr_inodes=16384",
        "/run/scanipy-work:rw,nosuid,nodev,noexec,size=8388608,nr_inodes=1024,"
        "mode=0700,uid=1000,gid=1001",
    ]
    assert not any("/dev/pts" in part or "/dev/mqueue" in part for part in render().argv)


def test_nested_roots_have_minimal_readonly_cover_with_stable_order() -> None:
    roots = ("/runtime", "/runtime/application", "/runtime/stdlib", "/runtime/stdlib/lib-dynload")
    first = render(runtime_roots=roots)
    assert first == render(runtime_roots=tuple(reversed(roots)))
    assert decoded_mounts(first) == [
        ("/private/metadata/domain.json", "/private/metadata/domain.json"),
        (ATTEMPT_ROOT + "/control", "/run/scanipy-control"),
        ("/runtime", "/runtime"),
        ("/trusted/bin/python", "/trusted/bin/python"),
    ]
    # Rendering cannot mutate the separate inventory's nested view declarations.
    assert roots == (
        "/runtime",
        "/runtime/application",
        "/runtime/stdlib",
        "/runtime/stdlib/lib-dynload",
    )


def test_standalone_files_and_identical_destinations_deduplicate() -> None:
    value = render(worker_path="/trusted/bin/python")
    mounts = decoded_mounts(value)
    assert mounts.count(("/trusted/bin/python", "/trusted/bin/python")) == 1
    assert len(mounts) == 6
    all_inside = render(python_executable="/runtime/stdlib/python")
    assert len(decoded_mounts(all_inside)) == 5


def test_domain_parent_can_be_shared_with_distinct_standalone_files() -> None:
    value = render(
        python_executable="/private/metadata/python",
        worker_path="/private/metadata/worker.py",
    )
    assert ("/private/metadata/python", "/private/metadata/python") in decoded_mounts(value)
    assert ("/private/metadata/worker.py", "/private/metadata/worker.py") in decoded_mounts(value)


def test_maximum_distinct_root_and_file_cover_remains_bounded() -> None:
    roots = ("/runtime/application", *("/root-" + str(i) for i in range(8)))
    value = render(runtime_roots=roots, worker_path="/standalone/worker.py")
    mounts = decoded_mounts(value)
    assert len(mounts) == 13  # Nine roots + two standalone files + domain + control.
    assert mounts == sorted(mounts, key=lambda pair: pair[1].encode("utf-8"))
    assert len(value.argv) <= 256
    reject(runtime_roots=(*roots, "/tenth-root"))


def test_host_cli_executable_is_not_a_container_mount() -> None:
    value = render(docker_executable="/run/scanipy-control/host-only-docker")
    assert value.argv[0] == "/run/scanipy-control/host-only-docker"
    assert not any(source == value.argv[0] for source, _ in decoded_mounts(value))
    # Host path trust is a later measured factory/loader gate, not a false
    # container-reserved-target test on an unmounted host-only executable.


def test_component_prefixes_are_not_false_ancestry() -> None:
    value = render(
        runtime_roots=("/runtime/app", "/runtime/application", "/devtools"),
        host_work_root="/private/job",
        domain_profile_path="/private/jobs/domain.json",
    )
    mounts = decoded_mounts(value)
    assert ("/runtime/app", "/runtime/app") in mounts
    assert ("/runtime/application", "/runtime/application") in mounts
    assert ("/devtools", "/devtools") in mounts


@pytest.mark.parametrize(
    "path",
    [
        "/proc",
        "/sys",
        "/dev",
        "/etc/hosts",
        "/etc/hostname",
        "/etc/resolv.conf",
        "/run/scanipy-control",
        "/run/scanipy-work",
    ],
)
@pytest.mark.parametrize("location", ["root", "file", "domain"])
@pytest.mark.parametrize("relation", ["equal", "descendant", "ancestor"])
def test_reserved_container_destinations_are_closed(
    path: str, location: str, relation: str
) -> None:
    selected = path if relation == "equal" else path + "/item"
    if relation == "ancestor":
        selected = path.rsplit("/", 1)[0] or "/"
    if location == "root":
        reject(runtime_roots=(selected, "/runtime/application", "/runtime/stdlib"))
    else:
        reject(**{"python_executable" if location == "file" else "domain_profile_path": selected})


@pytest.mark.parametrize(
    "changes",
    [
        {"host_work_root": "/runtime"},
        {"host_work_root": "/runtime/application/jobs"},
        {"host_work_root": "/trusted/bin/python"},
        {"host_work_root": "/private/metadata"},
        {"domain_profile_path": "/runtime/domain.json"},
        {"domain_profile_path": "/runtime/application/domain.json"},
        {"domain_profile_path": "/private/jobs-meta/domain.json", "host_work_root": "/private"},
        {"domain_profile_path": "/run/scanipy-work-meta/domain.json", "host_work_root": "/run"},
        {"domain_profile_path": "/run/domain.json"},
        {"domain_profile_path": "/domain.json"},
        {"domain_profile_path": "/trusted/bin/python"},
        {"domain_profile_path": "/trusted/bin/python/child"},
        {"domain_profile_path": "/trusted/bin", "python_executable": "/trusted/bin/python"},
        {"python_executable": "/runtime/application"},
        {"python_executable": "/runtime"},
        {"worker_path": "/trusted/bin/python/worker.py"},
        {"bootstrap_path": "/runtime/application"},
        {"bootstrap_path": "/outside/bootstrap.py"},
    ],
)
def test_conflicting_files_roots_domain_and_work_are_rejected(changes: dict[str, Any]) -> None:
    reject(**changes)


class Poison:
    def __str__(self) -> str:
        raise AssertionError("caller __str__ invoked")

    def __iter__(self) -> Any:
        raise AssertionError("caller iteration invoked")

    def __len__(self) -> int:
        raise AssertionError("caller length invoked")

    def __format__(self, _: str) -> str:
        raise AssertionError("caller format invoked")

    def __bool__(self) -> bool:
        raise AssertionError("caller bool invoked")


@pytest.mark.parametrize("field", [field.name for field in fields(policy.RuntimeDockerCreateSpec)])
def test_every_slot_rejects_poison_without_callbacks(field: str) -> None:
    reject(**{field: Poison()})


@pytest.mark.parametrize("field", [field.name for field in fields(policy.RuntimeDockerCreateSpec)])
def test_every_missing_slot_is_a_typed_failure(field: str) -> None:
    value = make_spec()
    object.__delattr__(value, field)
    with pytest.raises(policy.RuntimeDockerPolicyError) as captured:
        policy.render_runtime_docker_create(value)
    assert type(captured.value.__cause__) is AttributeError


class TextSubclass(str):
    def encode(self, *args: Any, **kwargs: Any) -> bytes:
        raise AssertionError("caller encoding invoked")


class TupleSubclass(tuple[Any, ...]):
    def __iter__(self) -> Any:
        raise AssertionError("caller iteration invoked")


class BytesSubclass(bytes):
    def hex(self, *args: Any, **kwargs: Any) -> str:
        raise AssertionError("caller hexadecimal formatter invoked")


class IntSubclass(int):
    def __str__(self) -> str:
        raise AssertionError("caller integer formatter invoked")


class SpecSubclass(policy.RuntimeDockerCreateSpec):
    def __getattribute__(self, name: str) -> Any:
        raise AssertionError("caller attribute invoked")


@pytest.mark.parametrize("field", PATH_FIELDS + UUID_FIELDS + ("purpose", "image_config_id"))
def test_text_subclasses_are_not_coerced(field: str) -> None:
    reject(**{field: TextSubclass(getattr(make_spec(), field))})


@pytest.mark.parametrize("field", DIGEST_FIELDS)
@pytest.mark.parametrize("value", [b"x" * 31, b"x" * 33, bytearray(32), BytesSubclass(b"x" * 32)])
def test_digest_type_and_length_are_exact(field: str, value: Any) -> None:
    reject(**{field: value})


@pytest.mark.parametrize("field", ("uid", "gid", "installation_generation"))
@pytest.mark.parametrize(
    "value",
    [True, False, 0, -1, 1.0, "1", IntSubclass(1)],
    ids=["true", "false", "zero", "negative", "float", "text", "int-subclass"],
)
def test_integer_types_and_positive_bounds(field: str, value: Any) -> None:
    reject(**{field: value})


@pytest.mark.parametrize(
    "field,maximum",
    [("uid", 2**31 - 1), ("gid", 2**31 - 1), ("installation_generation", 2**63 - 1)],
)
def test_integer_upper_boundary(field: str, maximum: int) -> None:
    render(**{field: maximum})
    reject(**{field: maximum + 1})


@pytest.mark.parametrize("field", UUID_FIELDS)
@pytest.mark.parametrize(
    "value", ["", "A" * 36, "a" * 32, ATTEMPT + "a", " " + ATTEMPT, UUID(ATTEMPT)]
)
def test_uuid_strings_are_closed_without_object_formatting(field: str, value: Any) -> None:
    reject(**{field: value})


@pytest.mark.parametrize(
    "value",
    [
        "latest",
        "sha256:" + "A" * 64,
        "sha256:" + "a" * 63,
        "sha256:" + "a" * 65,
        "registry/image@sha256:" + "a" * 64,
    ],
)
def test_image_is_full_lowercase_config_identity_only(value: str) -> None:
    reject(image_config_id=value)


@pytest.mark.parametrize("value", ["", "python", "java", "accepted-verifier ", "PYTHON-SYNTAX"])
def test_purpose_has_no_arbitrary_profile(value: str) -> None:
    reject(purpose=value)


@pytest.mark.parametrize(
    "value",
    [
        [],
        list(make_spec().runtime_roots),
        TupleSubclass(make_spec().runtime_roots),
        (),
        ("/a", "/b"),
        ("/a",) * 3,
        ("/a",) * 10,
        ("/a", "/b", Poison()),
        ("/a", "/b", TextSubclass("/c")),
    ],
)
def test_root_collection_and_members_are_closed(value: Any) -> None:
    reject(runtime_roots=value)


def test_unbounded_generator_rejected_without_advancing() -> None:
    def forbidden() -> Any:
        raise AssertionError("generator advanced")
        yield "/never"  # pragma: no cover

    reject(runtime_roots=forbidden())


def test_spec_subclass_rejected_without_attribute_dispatch() -> None:
    value = object.__new__(SpecSubclass)
    with pytest.raises(policy.RuntimeDockerPolicyError):
        policy.render_runtime_docker_create(value)


@pytest.mark.parametrize("value", [None, {}, [], Poison()])
def test_non_record_input_is_not_adapted(value: Any) -> None:
    with pytest.raises(policy.RuntimeDockerPolicyError):
        policy.render_runtime_docker_create(value)


@pytest.mark.parametrize("kind", ["path", "uuid"])
def test_poisoned_path_and_uuid_primitives_never_format(kind: str) -> None:
    if kind == "path":
        path = Path("/a")
        if hasattr(path, "_raw_paths"):
            object.__setattr__(path, "_raw_paths", Poison())
        else:
            object.__setattr__(path, "_parts", Poison())
        reject(docker_executable=path)
    else:
        identifier = UUID(ATTEMPT)
        object.__setattr__(identifier, "int", Poison())
        reject(attempt_id=identifier)


@pytest.mark.parametrize(
    "value",
    [
        "/",
        "relative",
        "//absolute",
        "/a//b",
        "/a/",
        "/a/./b",
        "/a/../b",
        "/a\\b",
        "/a\0b",
        "/a\rb",
        "/a\nb",
        "/a\tb",
        "/a\x7fb",
        "/a\x80b",
        "/a\x9fb",
        "/a\ud800b",
        Path("/a"),
    ],
)
def test_path_grammar_rejects_non_scalar_or_non_normalized(value: Any) -> None:
    reject(docker_executable=value)


def test_path_character_limit_precedes_encoding() -> None:
    error = reject(docker_executable="/" + "x" * 4095 + "\ud800")
    assert error.__cause__ is None


def test_path_utf8_boundary_and_unicode_preservation() -> None:
    path = "/" + "é" * 2047 + "x"
    assert len(path.encode()) == 4096
    assert render(docker_executable=path[:-1]).argv[0] == path[:-1]
    assert render(docker_executable=path).argv[0] == path
    reject(docker_executable=path + "x")


def test_derived_paths_count_longest_suffix() -> None:
    suffix = "/" + ATTEMPT + "/docker-config"
    root = "/" + "x" * (4096 - len(suffix) - 1)
    value = render(host_work_root=root)
    assert len(option_values(value, "--config")[0].encode()) == 4096
    reject(host_work_root=root + "x")


@pytest.mark.parametrize(
    "path",
    [
        "/runtime/a,b",
        '/runtime/a"b',
        '/runtime/值,"x',
        "/runtime/source=x,target=/untrusted,readonly=false",
    ],
)
def test_csv_roundtrip_cannot_inject_mount_fields(path: str) -> None:
    value = render(runtime_roots=("/runtime/application", "/runtime/stdlib", path))
    assert (path, path) in decoded_mounts(value)
    assert all(
        source == target or target == "/run/scanipy-control"
        for source, target in decoded_mounts(value)
    )


def test_csv_quoted_amplication_is_bounded_before_encoder(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("oversized mount reached encoder")

    monkeypatch.setattr(policy.csv, "writer", forbidden)
    with pytest.raises(policy.RuntimeDockerPolicyError):
        policy._csv_mount("/" + '"' * 4095, "/" + '"' * 4095)


def test_exact_mount_argument_limit() -> None:
    overhead = len(policy._csv_mount("/x", "/x").encode()) - 4
    source = "/" + "x" * 4095
    target = "/" + "y" * (8192 - overhead - len(source) - 1)
    assert len(target) <= 4096
    assert len(policy._csv_mount(source, target[:-1]).encode()) == 8191
    assert len(policy._csv_mount(source, target).encode()) == 8192
    with pytest.raises(policy.RuntimeDockerPolicyError):
        policy._csv_mount(source, target + "y")
    reject(runtime_roots=("/runtime/application", "/runtime/stdlib", "/" + "x" * 4095))


def test_snapshot_survives_mutation_of_original_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    original = make_spec()
    expected = policy.render_runtime_docker_create(original)
    real_mounts = policy._mounts

    def mutate_after_snapshot(copied: policy.RuntimeDockerCreateSpec, control: str) -> Any:
        assert copied is not original
        for field in fields(policy.RuntimeDockerCreateSpec):
            object.__setattr__(original, field.name, Poison())
        return real_mounts(copied, control)

    monkeypatch.setattr(policy, "_mounts", mutate_after_snapshot)
    assert policy.render_runtime_docker_create(original) == expected


def test_renderer_performs_no_filesystem_clock_or_process_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("pure renderer performed an external operation")

    with monkeypatch.context() as local:
        for module, name in (
            (os, "open"),
            (os, "stat"),
            (os, "lstat"),
            (os, "getcwd"),
            (subprocess, "Popen"),
            (time, "monotonic"),
            (time, "time"),
        ):
            local.setattr(module, name, forbidden)
        value = render()
    assert type(value) is FrozenInvocation


def test_private_aggregate_bounds_defend_final_transport_handoff() -> None:
    environment = dict(render().environment)
    cwd = ATTEMPT_ROOT
    # Count, per-value and aggregate limits are independent. This exercises the
    # last private guard even though the closed public grammar uses fewer flags.
    policy._invocation(["/docker"] + ["x"] * 254, environment, cwd)
    policy._invocation(["/docker"] + ["x"] * 255, environment, cwd)
    policy._invocation(["/" + "x" * 8190], environment, cwd)
    policy._invocation(["/" + "x" * 8191], environment, cwd)
    for argv in (["/docker"] + ["x"] * 256, ["/" + "x" * 8192], ["/docker"] + ["x" * 8192] * 8):
        with pytest.raises(policy.RuntimeDockerPolicyError):
            policy._invocation(argv, environment, cwd)
    environment["HOME"] = "x" * 16384
    with pytest.raises(policy.RuntimeDockerPolicyError):
        policy._invocation(["/docker"], environment, cwd)


def test_private_environment_aggregate_boundary() -> None:
    environment = dict(render().environment)
    environment["HOME"] = "x" * 8192
    environment["TMPDIR"] = ""
    cost = sum(len(key.encode()) + len(value.encode()) + 2 for key, value in environment.items())
    gap = 16384 - cost
    assert 0 < gap <= 8192
    for size in (gap - 1, gap):
        environment["TMPDIR"] = "y" * size
        result = policy._invocation(["/docker"], environment, ATTEMPT_ROOT)
        assert (
            sum(len(key.encode()) + len(value.encode()) + 2 for key, value in result.environment)
            == cost + size
        )
    environment["TMPDIR"] = "y" * (gap + 1)
    with pytest.raises(policy.RuntimeDockerPolicyError):
        policy._invocation(["/docker"], environment, ATTEMPT_ROOT)


def test_shared_transport_validation_failure_is_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    original = policy.ProcessValidationError("private shared failure")

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise original

    monkeypatch.setattr(policy, "FrozenInvocation", fail)
    error = reject()
    assert error.__cause__ is original


def test_public_argument_aggregate_boundary_is_not_truncated() -> None:
    # Eight independent roots supply a large yet individually bounded mount set.
    roots = ("/runtime/application", *("/" + str(i) + "x" * 3700 for i in range(8)))
    value = render(runtime_roots=roots)
    size = sum(len(argument.encode()) + 1 for argument in value.argv)
    gap = 65536 - size
    assert 0 < gap < 4096 - len(value.argv[0])
    executable = value.argv[0] + "x" * gap
    below = render(runtime_roots=roots, docker_executable=executable[:-1])
    assert sum(len(argument.encode()) + 1 for argument in below.argv) == 65535
    final = render(runtime_roots=roots, docker_executable=executable)
    assert sum(len(argument.encode()) + 1 for argument in final.argv) == 65536
    reject(runtime_roots=roots, docker_executable=executable + "x")
    assert len(decoded_mounts(final)) == 12


def test_input_and_output_repr_do_not_include_content() -> None:
    value = make_spec()
    assert value.domain_profile_path not in repr(value)
    assert value.domain_profile_path not in repr(policy.render_runtime_docker_create(value))
