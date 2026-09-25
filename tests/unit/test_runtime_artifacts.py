"""Actual file measurement fixtures; no measured file is imported or executed."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from tools.worker import runtime_artifacts as runtime

pytestmark = pytest.mark.unit


def encoded(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def domain(schema: str, value: object) -> bytes:
    digest = hashlib.sha256()
    digest.update(schema.encode("ascii"))
    digest.update(b"\n")
    digest.update(encoded(value))
    return digest.digest()


@pytest.fixture(autouse=True)
def never_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        pytest.fail("runtime measurement must not spawn or execute measured data")

    monkeypatch.setattr(subprocess, "Popen", fail)
    monkeypatch.setattr(os, "system", fail)


def prepare(tmp_path: Path, *, nested: bool = False):
    for name in ("stdlib", "application", "dependency", "metadata", "bin"):
        (tmp_path / name).mkdir(mode=0o700)
    (tmp_path / "stdlib" / "empty").mkdir(mode=0o700)
    data = {
        "stdlib/core.py": b"not executed stdlib data",
        "application/worker.py": b"raise RuntimeError('must never execute')\n",
        "dependency/.hidden": b"dependency bytes\x00\xff",
        "bin/python": b"not an executable interpreter",
    }
    if nested:
        (tmp_path / "stdlib" / "extension").mkdir(mode=0o700)
        data["stdlib/extension/one.so"] = b"not a loaded shared library"
    for name, payload in data.items():
        (tmp_path / name).write_bytes(payload)
        (tmp_path / name).chmod(0o600)
    bindings = [
        runtime.RuntimeRootBinding("stdlib", 0, tmp_path / "stdlib"),
        *(
            [runtime.RuntimeRootBinding("stdlib", 1, tmp_path / "stdlib" / "extension")]
            if nested
            else []
        ),
        runtime.RuntimeRootBinding("application", 0, tmp_path / "application"),
        runtime.RuntimeRootBinding("dependency", 0, tmp_path / "dependency"),
    ]
    roots = []
    for root in bindings:
        directories = []
        files = []
        for path in sorted(root.path.rglob("*")):
            relative = path.relative_to(root.path).as_posix()
            if path.is_dir():
                directories.append(relative)
            else:
                payload = path.read_bytes()
                files.append(
                    {
                        "path": relative,
                        "size": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }
                )
        roots.append(
            {
                "role": root.role,
                "ordinal": root.ordinal,
                "path": str(root.path),
                "directories": directories,
                "files": files,
            }
        )
    profile = hashlib.sha256(b"diagnostic-only installed profile").digest()
    doc = {
        "schema": runtime.SCHEMA,
        "profile_sha256": profile.hex(),
        "purpose": "python-syntax",
        "implementation": "cpython",
        "python_version": "3.11.16",
        "protocol_version": "test-source-syntax/1",
        "resource_profile": "test-only/1",
        "roots": roots,
        "runtime_bindings": [
            {
                "role": role,
                "path": str(tmp_path / name),
                "size": len(data[name]),
                "sha256": hashlib.sha256(data[name]).hexdigest(),
            }
            for role, name in (("executable", "bin/python"), ("worker", "application/worker.py"))
        ],
    }
    groups = {
        role: domain(
            "scanipy-runtime-root-group/1",
            {"role": role, "roots": [root for root in roots if root["role"] == role]},
        )
        for role in ("stdlib", "application", "dependency")
    }
    program = {
        key: doc[key]
        for key in (
            "purpose",
            "implementation",
            "python_version",
            "protocol_version",
            "resource_profile",
            "runtime_bindings",
        )
    }
    program.update({role + "_digest": digest.hex() for role, digest in groups.items()})
    program_digest = domain("scanipy-runtime-program/1", program)
    doc.update(
        application_digest=groups["application"].hex(),
        dependency_digest=groups["dependency"].hex(),
        program_digest=program_digest.hex(),
    )
    expected = runtime.RuntimeArtifactBindings(
        "python-syntax",
        "cpython",
        "3.11.16",
        "test-source-syntax/1",
        "test-only/1",
        runtime.RuntimeFileBinding(
            tmp_path / "bin/python", hashlib.sha256(data["bin/python"]).digest()
        ),
        runtime.RuntimeFileBinding(
            tmp_path / "application/worker.py",
            hashlib.sha256(data["application/worker.py"]).digest(),
        ),
        tuple(bindings),
        groups["application"],
        groups["dependency"],
        program_digest,
    )
    metadata = runtime.RuntimeMetadataPaths(
        *(
            tmp_path / "metadata" / name
            for name in ("inventory.json", "profile.json", "installation.json")
        )
    )
    raw = encoded(doc)
    installed = runtime.InstalledRuntimeArtifactInventory(
        raw, hashlib.sha256(raw).digest(), metadata
    )
    return installed, expected, profile, doc, data


def verify(fixture, **kwargs):
    installed, expected, profile, *_ = fixture
    return runtime.require_installed_runtime_artifacts(
        installed, expected=expected, profile_sha256=profile, **kwargs
    )


def repack(fixture, doc):
    raw = encoded(doc)
    installed = replace(
        fixture[0], inventory_bytes=raw, inventory_sha256=hashlib.sha256(raw).digest()
    )
    return (installed, *fixture[1:])


@pytest.mark.parametrize("nested", [False, True])
def test_actual_complete_measurement_and_empty_directories(tmp_path: Path, nested: bool) -> None:
    fixture = prepare(tmp_path, nested=nested)
    result = verify(fixture)
    assert result.expected == fixture[1] and result.expected is not fixture[1]
    assert result.inventory_bytes == fixture[0].inventory_bytes
    assert result.inventory_sha256 == hashlib.sha256(result.inventory_bytes).digest()
    assert result.inventory_digest == domain(runtime.SCHEMA, fixture[3])
    assert result.program_digest == fixture[1].program_digest
    assert result.stdlib_digest == domain(
        "scanipy-runtime-root-group/1",
        {"role": "stdlib", "roots": [r for r in fixture[3]["roots"] if r["role"] == "stdlib"]},
    )
    assert 0 <= result.elapsed_ms < 30000


def test_independent_builder_matches_exact_root_rows(tmp_path: Path) -> None:
    fixture = prepare(tmp_path)
    actual = fixture[3]["roots"]
    independent = []
    for role, name in (
        ("stdlib", "core.py"),
        ("application", "worker.py"),
        ("dependency", ".hidden"),
    ):
        payload = fixture[4][role + "/" + name]
        independent.append(
            {
                "role": role,
                "ordinal": 0,
                "path": str(tmp_path / role),
                "directories": ["empty"] if role == "stdlib" else [],
                "files": [
                    {
                        "path": name,
                        "size": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }
                ],
            }
        )
    assert actual == independent
    assert verify(fixture).application_digest == domain(
        "scanipy-runtime-root-group/1", {"role": "application", "roots": [independent[1]]}
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "missing",
        "empty-missing",
        "symlink",
        "hardlink",
        "writable",
        "fifo",
        "changed",
        "root-mode",
        "ancestor-mode",
    ],
)
def test_actual_filesystem_refusals(tmp_path: Path, mutation: str) -> None:
    fixture = prepare(tmp_path)
    file = tmp_path / "stdlib" / "core.py"
    if mutation == "extra":
        (tmp_path / "stdlib" / "extra").write_bytes(b"unexpected")
    elif mutation == "missing":
        file.unlink()
    elif mutation == "empty-missing":
        (tmp_path / "stdlib" / "empty").rmdir()
    elif mutation == "symlink":
        file.unlink()
        file.symlink_to(tmp_path / "bin/python")
    elif mutation == "hardlink":
        os.link(file, tmp_path / "second-link")
    elif mutation == "writable":
        file.chmod(0o666)
    elif mutation == "fifo":
        file.unlink()
        os.mkfifo(file)
    elif mutation == "changed":
        file.write_bytes(b"same bytes are not assumed")
    elif mutation == "root-mode":
        (tmp_path / "stdlib").chmod(0o775)
    else:
        tmp_path.chmod(0o775)
    with pytest.raises(runtime.RuntimeArtifactError):
        verify(fixture)


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "bool-ordinal",
        "bool-size",
        "bad-hash",
        "profile",
        "root-path",
        "path-traversal",
        "c1",
        "duplicate",
        "runtime-order",
        "digest",
        "purpose",
        "schema",
    ],
)
def test_wire_rejections_before_filesystem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    fixture = prepare(tmp_path)
    doc = fixture[3]
    if mutation == "unknown":
        doc["extra"] = None
    elif mutation == "bool-ordinal":
        doc["roots"][0]["ordinal"] = False
    elif mutation == "bool-size":
        doc["roots"][0]["files"][0]["size"] = True
    elif mutation == "bad-hash":
        doc["roots"][0]["files"][0]["sha256"] = "g" * 64
    elif mutation == "profile":
        doc["profile_sha256"] = "0" * 64
    elif mutation == "root-path":
        doc["roots"][0]["path"] = "/unexpected"
    elif mutation == "path-traversal":
        doc["roots"][0]["files"][0]["path"] = "../escape"
    elif mutation == "c1":
        doc["roots"][0]["files"][0]["path"] = "bad\x80"
    elif mutation == "duplicate":
        doc["roots"][0]["directories"] *= 2
    elif mutation == "runtime-order":
        doc["runtime_bindings"].reverse()
    elif mutation == "digest":
        doc["program_digest"] = "0" * 64
    elif mutation == "purpose":
        doc["purpose"] = "native-git"
    else:
        doc["schema"] += "-unsupported"
    changed = repack(fixture, doc)

    def forbidden(*_args, **_kwargs):
        pytest.fail("invalid metadata reached filesystem")

    monkeypatch.setattr(os, "open", forbidden)
    with pytest.raises(runtime.RuntimeArtifactError):
        verify(changed)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":1,"a":2}',
        b'{"x":NaN}',
        b'{"x":1.2}',
        b'{"x":-0}',
        b' {"x":1}',
        b'{"x":"\\ud800"}',
        b"[" * 13 + b"]" * 13,
        b'{"x":9223372036854775808}',
    ],
)
def test_malformed_json(tmp_path: Path, raw: bytes) -> None:
    fixture = prepare(tmp_path)
    with pytest.raises(runtime.RuntimeArtifactError):
        verify(
            (
                replace(
                    fixture[0], inventory_bytes=raw, inventory_sha256=hashlib.sha256(raw).digest()
                ),
                *fixture[1:],
            )
        )


@pytest.mark.parametrize("field", ["inventory", "profile", "installation"])
def test_metadata_origins_outside_all_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    fixture = prepare(tmp_path)
    origins = replace(fixture[0].metadata_paths, **{field: tmp_path / "stdlib" / "metadata.json"})
    changed = replace(fixture[0], metadata_paths=origins)
    monkeypatch.setattr(os, "open", lambda *_a, **_kw: pytest.fail("overlap reached filesystem"))
    with pytest.raises(runtime.RuntimeArtifactError):
        verify((changed, *fixture[1:]))


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_files", 4),
        ("max_entries", 1),
        ("max_depth", 1),
        ("max_file_bytes", 1),
        ("max_total_bytes", 1),
        ("max_inventory_bytes", 1),
        ("max_json_depth", 1),
        ("max_json_values", 1),
        ("max_roots", 2),
    ],
)
def test_independent_caps(tmp_path: Path, field: str, value: int) -> None:
    fixture = prepare(tmp_path, nested=field == "max_depth")
    with pytest.raises(runtime.RuntimeArtifactError, match="limit"):
        verify(fixture, limits=replace(runtime.RuntimeArtifactLimits(), **{field: value}))


def test_repeated_runtime_reads_are_charged(tmp_path: Path) -> None:
    fixture = prepare(tmp_path)
    total = sum(len(value) for value in fixture[4].values()) + len(
        fixture[4]["application/worker.py"]
    )
    for extra in (0, 1):
        assert verify(fixture, limits=runtime.RuntimeArtifactLimits(max_total_bytes=total + extra))
    with pytest.raises(runtime.RuntimeArtifactError, match="limit"):
        verify(fixture, limits=runtime.RuntimeArtifactLimits(max_total_bytes=total - 1))


def test_mutation_after_first_read_is_not_hidden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = prepare(tmp_path)
    original = runtime._read
    changed = False

    def read(*args, **kwargs):
        nonlocal changed
        result = original(*args, **kwargs)
        if not changed:
            changed = True
            (tmp_path / "stdlib" / "core.py").write_bytes(b"late mutation")
        return result

    monkeypatch.setattr(runtime, "_read", read)
    with pytest.raises(runtime.RuntimeArtifactError, match="changed"):
        verify(fixture)


def test_final_result_work_counts_toward_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = prepare(tmp_path)
    clock = [0]
    original = runtime._domain

    def digest(schema, raw):
        result = original(schema, raw)
        if schema == runtime.SCHEMA:
            clock[0] = 30_000_000_000
        return result

    monkeypatch.setattr(runtime.time, "monotonic_ns", lambda: clock[0])
    monkeypatch.setattr(runtime, "_domain", digest)
    with pytest.raises(runtime.RuntimeArtifactError, match="timeout"):
        verify(fixture)


def test_poisoned_path_cannot_dispatch_custom_strings(tmp_path: Path) -> None:
    fixture = prepare(tmp_path)

    class Poison:
        def __str__(self):
            pytest.fail("poison dispatched")

    path = Path("/private/path")
    object.__setattr__(path, "_parts", ["/", Poison()])
    expected = replace(fixture[1], executable=replace(fixture[1].executable, path=path))
    with pytest.raises(runtime.RuntimeArtifactError):
        verify((fixture[0], expected, *fixture[2:]))


def test_original_interrupt_and_prior_cause_survive_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = prepare(tmp_path)
    original = KeyboardInterrupt("keep identity")
    prior = ValueError("prior cause")
    close_failure = OSError("close completed but signaled failure")
    close = os.close
    failed = False

    def broken_read(*_args, **_kwargs):
        raise original from prior

    def broken_close(fd):
        nonlocal failed
        close(fd)
        if not failed and original.__cause__ is prior:
            failed = True
            raise close_failure

    monkeypatch.setattr(os, "read", broken_read)
    monkeypatch.setattr(os, "close", broken_close)
    with pytest.raises(KeyboardInterrupt) as caught:
        verify(fixture)
    assert caught.value is original
    assert isinstance(original.__cause__, BaseExceptionGroup)
    assert original.__cause__.exceptions == (prior, close_failure)


@pytest.mark.parametrize("fault", ["read", "short-eof", "stat", "scandir", "open", "close"])
def test_filesystem_faults_never_return_success(tmp_path: Path, monkeypatch, fault) -> None:
    fixture = prepare(tmp_path)
    failure = OSError("private fault retained only as cause")
    if fault == "short-eof":
        monkeypatch.setattr(os, "read", lambda *_args: b"")
    elif fault == "close":
        close = os.close
        fired = False

        def broken_close(fd):
            nonlocal fired
            close(fd)
            if not fired:
                fired = True
                raise failure

        monkeypatch.setattr(os, "close", broken_close)
    else:

        def broken(*_args, **_kwargs):
            raise failure

        monkeypatch.setattr(os, "fstat" if fault == "stat" else fault, broken)
    with pytest.raises(runtime.RuntimeArtifactError) as caught:
        verify(fixture)
    assert caught.value.reason in ("storage", "changed")
    if fault != "short-eof":
        assert caught.value.__cause__ is failure


def test_first_filesystem_validation_obeys_deadline(tmp_path: Path, monkeypatch) -> None:
    fixture = prepare(tmp_path)
    original = runtime._inventory
    clock = [0]

    def inventory(*args):
        result = original(*args)
        clock[0] = 30_000_000_000
        return result

    monkeypatch.setattr(runtime.time, "monotonic_ns", lambda: clock[0])
    monkeypatch.setattr(runtime, "_inventory", inventory)
    monkeypatch.setattr(os, "open", lambda *_a, **_k: pytest.fail("expired input opened a path"))
    with pytest.raises(runtime.RuntimeArtifactError, match="timeout"):
        verify(fixture)


def test_actual_read_chunks_are_bounded_and_short_reads_supported(
    tmp_path: Path, monkeypatch
) -> None:
    fixture = prepare(tmp_path)
    original = os.read
    observed = []

    def short(fd, count):
        assert 0 < count <= 65536
        result = original(fd, min(3, count))
        observed.append(len(result))
        return result

    monkeypatch.setattr(os, "read", short)
    assert verify(fixture)
    assert 0 in observed and len(observed) > 10


@pytest.mark.parametrize("difference", [-1, 0, 1])
def test_exact_file_and_metadata_boundaries(tmp_path: Path, difference: int) -> None:
    fixture = prepare(tmp_path)
    largest = max(len(value) for value in fixture[4].values())
    limits = runtime.RuntimeArtifactLimits(max_file_bytes=largest + difference)
    if difference < 0:
        with pytest.raises(runtime.RuntimeArtifactError, match="limit"):
            verify(fixture, limits=limits)
    else:
        assert verify(fixture, limits=limits)
    limits = runtime.RuntimeArtifactLimits(
        max_inventory_bytes=len(fixture[0].inventory_bytes) + difference
    )
    if difference < 0:
        with pytest.raises(runtime.RuntimeArtifactError, match="limit"):
            verify(fixture, limits=limits)
    else:
        assert verify(fixture, limits=limits)


def test_final_membership_and_ancestor_traversals_are_counted(tmp_path: Path) -> None:
    fixture = prepare(tmp_path)
    # Two passes: root and each absolute ancestor plus four child entries
    # (three files, one empty dir); two runtime paths with parent walks + file.
    roots = sum(len(root.path.parts) for root in fixture[1].roots)
    runtime_paths = sum(
        len(binding.path.parent.parts) + 1 for binding in (fixture[1].executable, fixture[1].worker)
    )
    total = 2 * (roots + 4 + runtime_paths)
    assert verify(fixture, limits=runtime.RuntimeArtifactLimits(max_entries=total))
    assert verify(fixture, limits=runtime.RuntimeArtifactLimits(max_entries=total + 1))
    with pytest.raises(runtime.RuntimeArtifactError, match="limit"):
        verify(fixture, limits=runtime.RuntimeArtifactLimits(max_entries=total - 1))


def test_directory_added_after_payload_read_is_detected(tmp_path: Path, monkeypatch) -> None:
    fixture = prepare(tmp_path)
    original = runtime._read
    calls = 0

    def changed(*args, **kwargs):
        nonlocal calls
        result = original(*args, **kwargs)
        calls += 1
        if calls == 5:
            (tmp_path / "stdlib" / "new-empty").mkdir(mode=0o700)
        return result

    monkeypatch.setattr(runtime, "_read", changed)
    with pytest.raises(runtime.RuntimeArtifactError):
        verify(fixture)


@pytest.mark.parametrize("target", ["metadata", "root", "limits", "file", "installed"])
def test_poisoned_exact_records_revalidated_before_paths(
    tmp_path: Path, monkeypatch, target
) -> None:
    fixture = prepare(tmp_path)
    installed, expected = fixture[:2]
    limits = runtime.RuntimeArtifactLimits()
    if target == "metadata":
        object.__setattr__(installed.metadata_paths, "profile", object())
    elif target == "root":
        object.__setattr__(expected.roots[0], "ordinal", False)
    elif target == "limits":
        object.__setattr__(limits, "max_files", True)
    elif target == "file":
        object.__setattr__(expected.worker, "sha256", bytearray(32))
    else:
        object.__setattr__(installed, "inventory_bytes", bytearray(b"{}"))
    monkeypatch.setattr(os, "open", lambda *_a, **_k: pytest.fail("poison reached filesystem"))
    with pytest.raises(runtime.RuntimeArtifactError):
        verify(fixture, limits=limits)


def test_wrong_owner_is_rejected(tmp_path: Path, monkeypatch) -> None:
    fixture = prepare(tmp_path)
    original = runtime._safe

    class WrongOwner:
        st_mode = 0o100600
        st_uid = -1
        st_nlink = 1
        st_size = 1

    def wrong(info, **kwargs):
        original(WrongOwner() if not kwargs["directory"] else info, **kwargs)

    monkeypatch.setattr(runtime, "_safe", wrong)
    with pytest.raises(runtime.RuntimeArtifactError, match="unsafe-path"):
        verify(fixture)


def test_only_root_owned_literal_tmp_is_sticky_exception(tmp_path: Path) -> None:
    fixture = prepare(tmp_path)
    tmp_path.chmod(0o1777)
    with pytest.raises(runtime.RuntimeArtifactError, match="unsafe-path"):
        verify(fixture)


def test_caller_path_mutation_cannot_change_private_snapshot(tmp_path: Path, monkeypatch) -> None:
    fixture = prepare(tmp_path)
    path = fixture[1].executable.path
    parts = object.__getattribute__(path, "_parts")
    original_parts = list(parts)
    require = runtime._require
    checks = 0

    class Poison:
        def __len__(self):
            pytest.fail("caller-owned new part len dispatched")

        def __eq__(self, _other):
            pytest.fail("caller-owned new part equality dispatched")

    def mutate_after_snapshot(condition, reason="invalid-input"):
        nonlocal checks
        checks += 1
        require(condition, reason)
        if checks == 5:
            parts[:] = ["/", Poison()]

    try:
        monkeypatch.setattr(runtime, "_require", mutate_after_snapshot)
        observed = runtime._path(path, 4096)
        assert str(observed) == "/" + "/".join(original_parts[1:])
        assert checks > 5
    finally:
        parts[:] = original_parts


def test_path_snapshot_copy_is_bounded_even_if_list_grows(tmp_path: Path) -> None:
    path = tmp_path / "path"
    object.__setattr__(path, "_parts", ["/"] + ["x"] * 10000)
    with pytest.raises(runtime.RuntimeArtifactError):
        runtime._path(path, 10)
