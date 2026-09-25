"""Controlled Python children only; no controller/native/operational trust claim."""

import importlib.util
import marshal
import os
import py_compile
import stat
import sys
import sysconfig
import time
from dataclasses import dataclass, field, replace
from importlib.machinery import EXTENSION_SUFFIXES
from pathlib import Path, PosixPath

import pytest

from services.scan.accepted_inputs import codec as c
from services.scan.accepted_inputs import models as m
from services.scan.accepted_inputs import schemas as s
from services.scan.accepted_inputs import verify as v
from tests import accepted_input_fixtures as fixtures
from tools.worker import bounded_process as transport

pytestmark = pytest.mark.integration
material = fixtures.material
test_only_keys = fixtures.test_only_keys
ROOT = Path(__file__).resolve().parents[2]
_DIAGNOSTIC_RUNTIME = None


@dataclass
class _CopyBudget:
    """Test-only copy budget, not installed-artifact measurement or authority."""

    max_files: int = 10_000
    max_entries: int = 20_000
    max_depth: int = 64
    max_path_bytes: int = 4096
    max_file_bytes: int = 32 * 1024 * 1024
    max_total_bytes: int = 128 * 1024 * 1024
    wall_seconds: float = 30.0
    files: int = 0
    entries: int = 0
    total_bytes: int = 0
    started: float = field(default_factory=time.monotonic)

    def check(self):
        if time.monotonic() - self.started >= self.wall_seconds:
            raise ValueError("diagnostic-copy-deadline")

    def observe(self, path, depth):
        self.check()
        self.entries += 1
        if self.entries > self.max_entries or depth > self.max_depth:
            raise ValueError("diagnostic-copy-limit")
        if len(str(path)) > self.max_path_bytes or len(str(path).encode()) > self.max_path_bytes:
            raise ValueError("diagnostic-copy-limit")
        observed = path.stat(follow_symlinks=False)
        if not (stat.S_ISREG(observed.st_mode) or stat.S_ISDIR(observed.st_mode)):
            raise ValueError("diagnostic-copy-nonregular")
        return observed

    def reserve(self, observed):
        self.files += 1
        self.total_bytes += observed.st_size
        if (
            self.files > self.max_files
            or observed.st_size > self.max_file_bytes
            or self.total_bytes > self.max_total_bytes
        ):
            raise ValueError("diagnostic-copy-limit")


def _stat_identity(observed):
    return tuple(
        getattr(observed, name)
        for name in (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
    )


def _copy_source_ancestors(source, budget):
    if not source.is_absolute():
        raise ValueError("diagnostic-copy-relative-root")
    for parent in reversed(source.parents):
        observed = budget.observe(parent, 0)
        if not stat.S_ISDIR(observed.st_mode):
            raise ValueError("diagnostic-copy-nonregular")


def _copy_regular(source, destination, observed, budget, *, executable=False):
    budget.check()
    source_fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if _stat_identity(os.fstat(source_fd)) != _stat_identity(observed):
            raise ValueError("diagnostic-copy-changed")
        destination_fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            copied = 0
            while True:
                budget.check()
                data = os.read(source_fd, min(65536, observed.st_size - copied + 1))
                if not data:
                    break
                copied += len(data)
                if copied > observed.st_size:
                    raise ValueError("diagnostic-copy-changed")
                remaining = memoryview(data)
                while remaining:
                    budget.check()
                    written = os.write(destination_fd, remaining)
                    if written <= 0:
                        raise OSError("diagnostic-copy-short-write")
                    remaining = remaining[written:]
            if copied != observed.st_size or _stat_identity(os.fstat(source_fd)) != _stat_identity(
                observed
            ):
                raise ValueError("diagnostic-copy-changed")
            if executable:
                os.fchmod(destination_fd, 0o700)
        finally:
            os.close(destination_fd)
    finally:
        os.close(source_fd)
    budget.check()


def _private_copy_tree(source, destination, budget, *, stdlib_root=False):
    # Only fixed trusted fixture roots. Reject source symlinks; omit caches to
    # create a fresh diagnostic distribution, not a complete installed inventory.
    records = []
    _copy_source_ancestors(source, budget)

    def preflight(path, relative, depth):
        observed = budget.observe(path, depth)
        if stat.S_ISREG(observed.st_mode):
            budget.reserve(observed)
        records.append((relative, observed))
        if stat.S_ISDIR(observed.st_mode):
            with os.scandir(path) as children:
                for child in children:
                    child_path = path / child.name
                    separate_dependency_container = (
                        stdlib_root
                        and relative == Path()
                        and child.name in ("site-packages", "dist-packages")
                    )
                    if (
                        child.name == "__pycache__"
                        or child.name.endswith(".pyc")
                        or separate_dependency_container
                    ):
                        budget.observe(child_path, depth + 1)
                        continue
                    preflight(child_path, relative / child.name, depth + 1)

    preflight(source, Path(), 0)
    # Every source size/entry is bounded before destination allocation/copy.
    for relative, observed in records:
        budget.check()
        target = destination / relative
        if stat.S_ISDIR(observed.st_mode):
            target.mkdir(mode=0o700)
        else:
            _copy_regular(source / relative, target, observed, budget)
    budget.check()


def _private_copy_file(source, destination, budget, *, executable=False):
    _copy_source_ancestors(source, budget)
    observed = budget.observe(source, 0)
    if not stat.S_ISREG(observed.st_mode):
        raise ValueError("diagnostic-copy-nonregular")
    budget.reserve(observed)
    _copy_regular(source, destination, observed, budget, executable=executable)


@pytest.fixture(scope="module", autouse=True)
def private_diagnostic_runtime(tmp_path_factory):
    # Tighten ONLY new diagnostic copies, not the shared writable dev runtime.
    global _DIAGNOSTIC_RUNTIME
    budget = _CopyBudget()
    root = tmp_path_factory.mktemp("accepted-verifier-runtime")
    binary = root / "python" / "bin"
    binary.mkdir(parents=True, mode=0o700)
    binary.parent.chmod(0o700)
    executable = binary / "python3.11"
    source_executable = Path(sys.executable).resolve(strict=True)
    _private_copy_file(source_executable, executable, budget, executable=True)
    assert c.raw_digest(executable.read_bytes()) == c.raw_digest(source_executable.read_bytes())
    library = binary.parent / "lib"
    library.mkdir(mode=0o700)
    stdlib = library / "python3.11"
    _private_copy_tree(Path(sysconfig.get_path("stdlib")), stdlib, budget, stdlib_root=True)
    dependencies = root / "dependencies"
    dependencies.mkdir(mode=0o700)
    installed = Path(sysconfig.get_path("purelib"))
    for name in ("cryptography", "cffi", "pycparser", "yaml"):
        _private_copy_tree(installed / name, dependencies / name, budget)
    extensions = []
    for suffix in EXTENSION_SUFFIXES:
        candidate = installed / ("_cffi_backend" + suffix)
        try:
            budget.observe(candidate, 0)
        except FileNotFoundError:
            continue
        extensions.append(candidate)
    assert len(extensions) == 1
    _private_copy_file(extensions[0], dependencies / extensions[0].name, budget)
    application = root / "application"
    application.mkdir(mode=0o700)
    for name in ("analysis", "services", "tools"):
        _private_copy_tree(ROOT / name, application / name, budget)
    budget.check()
    _DIAGNOSTIC_RUNTIME = (
        PosixPath(executable),
        PosixPath(stdlib),
        PosixPath(dependencies),
        PosixPath(application),
    )
    yield
    _DIAGNOSTIC_RUNTIME = None


@pytest.mark.parametrize("kind", ["file", "directory", "ancestor", "omitted-cache"])
def test_private_fixture_copy_never_follows_symlinks(tmp_path, kind):
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").write_bytes(b"diagnostic fixture outside selected source")
    if kind == "ancestor":
        alias = tmp_path / "alias"
        alias.symlink_to(tmp_path, target_is_directory=True)
        source = alias / "source"
    else:
        name = "__pycache__" if kind == "omitted-cache" else "linked"
        target = outside / "secret" if kind == "file" else outside
        (source / name).symlink_to(target, target_is_directory=kind != "file")
    destination = tmp_path / "copy"
    with pytest.raises(ValueError, match="diagnostic-copy-nonregular"):
        _private_copy_tree(source, destination, _CopyBudget())
    assert not destination.exists()


@pytest.mark.parametrize(
    "limits",
    [
        {"max_files": 0},
        {"max_entries": 0},
        {"max_depth": 0},
        {"max_path_bytes": 1},
        {"max_file_bytes": 3},
        {"max_total_bytes": 3},
        {"wall_seconds": 0.0},
    ],
)
def test_private_fixture_copy_bounds_before_destination_allocation(tmp_path, limits):
    source = tmp_path / "source"
    source.mkdir()
    (source / "file").write_bytes(b"four")
    destination = tmp_path / "copy"
    with pytest.raises(ValueError, match=r"diagnostic-copy-(limit|deadline)"):
        _private_copy_tree(source, destination, _CopyBudget(**limits))
    assert not destination.exists()


def test_private_fixture_copy_shared_byte_budget_and_exact_bytes(tmp_path):
    budget = _CopyBudget(max_total_bytes=4, max_file_bytes=4)
    source = tmp_path / "source"
    source.write_bytes(b"four")
    destination = tmp_path / "copy"
    _private_copy_file(source, destination, budget)
    assert destination.read_bytes() == b"four"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    with pytest.raises(ValueError, match="diagnostic-copy-limit"):
        _private_copy_file(source, tmp_path / "over", budget)
    assert not (tmp_path / "over").exists()


def test_stdlib_copy_omits_only_direct_separately_copied_dependency_containers(tmp_path):
    source = tmp_path / "stdlib"
    source.mkdir()
    (source / "core.py").write_bytes(b"core")
    for name in ("site-packages", "dist-packages"):
        (source / name).mkdir()
        (source / name / "unrelated-dev-package").write_bytes(b"not part of diagnostic runtime")
    destination = tmp_path / "copy"
    _private_copy_tree(source, destination, _CopyBudget(max_total_bytes=4), stdlib_root=True)
    assert sorted(path.name for path in destination.iterdir()) == ["core.py"]
    # This is not a generic exclusion in application/dependency trees.
    with pytest.raises(ValueError, match="diagnostic-copy-limit"):
        _private_copy_tree(source, tmp_path / "not-stdlib", _CopyBudget(max_total_bytes=4))
    assert not (tmp_path / "not-stdlib").exists()


def runtime_profile(tmp_path, *, application=None, script=None):
    """Actual file hashes; synthetic aggregate bindings are explicitly diagnostic."""
    private = tmp_path / "profile"
    private.mkdir(mode=0o700)
    work = tmp_path / "work"
    work.mkdir(mode=0o700)
    assert _DIAGNOSTIC_RUNTIME is not None
    executable, stdlib, dependencies, default_application = _DIAGNOSTIC_RUNTIME
    application = application or default_application
    worker = PosixPath(script or application / "services/scan/accepted_inputs/verifier_worker.py")
    roots = [stdlib]
    extension_root = stdlib / "lib-dynload"
    if extension_root.is_dir():
        roots.append(extension_root)
    document = m.VerifierRuntimeDocument(
        "cpython",
        ".".join(str(item) for item in sys.version_info[:3]),
        executable,
        c.raw_digest(executable.read_bytes()),
        worker,
        c.raw_digest(worker.read_bytes()),
        PosixPath(application),
        "8" * 64,
        tuple(roots),
        (dependencies,),
        "9" * 64,
        "7" * 64,
        PosixPath(work),
    )
    raw = c.encode_document(m.record_dict(document), s.RUNTIME)
    path = private / "runtime.json"
    path.write_bytes(raw)
    path.chmod(0o600)
    return m.VerifierRuntimeProfile(PosixPath(path), c.raw_digest(raw), document)


@pytest.mark.parametrize("mode", ["publication", "historical", "execution"])
def test_actual_fixed_worker_under_128m_three_seconds(material, tmp_path, monkeypatch, mode):
    profile = runtime_profile(tmp_path)
    request = material.request if mode == "execution" else getattr(material, mode)()
    outcomes = []
    original = transport.run_bounded_process

    def observe(*args, **kwargs):
        assert kwargs["limits"].wall_ms == 3000
        assert kwargs["limits"].cleanup_reserve_ms == 500
        assert kwargs["spool_dir"] is None
        outcome = original(*args, **kwargs)
        outcomes.append(outcome)
        return outcome

    monkeypatch.setattr(transport, "run_bounded_process", observe)
    checked = v._run_diagnostic_verifier(request, profile=profile)
    assert checked.accepted_content_digest == request.expected_bundle.accepted_content_digest
    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.returncode == 0 and outcome.cleanup == "completed"
    assert outcome.elapsed_ms <= 3000
    assert outcome.stderr.data == b""
    assert outcome.invocation.environment == (
        ("LANG", "C.UTF-8"),
        ("LC_ALL", "C.UTF-8"),
        ("TZ", "UTC"),
    )
    assert (
        "-I" in outcome.invocation.argv
        and "-S" in outcome.invocation.argv
        and "-B" in outcome.invocation.argv
    )
    assert any(argument.startswith("pycache_prefix=") for argument in outcome.invocation.argv)
    assert list(profile.document.work_root.iterdir()) == []


def test_actual_rejection_retains_original_bounded_child_outcome(material, tmp_path):
    profile = runtime_profile(tmp_path)
    request = replace(
        material.request,
        installed_trust=replace(material.request.installed_trust, root_spki_sha256="0" * 64),
    )
    with pytest.raises(v.VerificationProcessError, match="untrusted-root") as caught:
        v._run_diagnostic_verifier(request, profile=profile)
    outcome = caught.value.outcome
    assert outcome.returncode == 2 and outcome.cleanup == "completed"
    result = c.decode_result(outcome.stdout.data)
    assert result.status == "rejected" and result.failure_code == "untrusted-root"
    assert result.request_sha256 == c.raw_digest(c.encode_request(request))


@pytest.mark.parametrize(
    "field", ["profile_sha256", "python_executable_sha256", "worker_script_sha256"]
)
def test_wrong_actual_artifact_binding_refuses_before_spawn(material, tmp_path, monkeypatch, field):
    profile = runtime_profile(tmp_path)
    if field == "profile_sha256":
        profile = replace(profile, profile_sha256="0" * 64)
    else:
        document = replace(profile.document, **{field: "0" * 64})
        raw = c.encode_document(m.record_dict(document), s.RUNTIME)
        profile.profile_path.write_bytes(raw)
        profile = replace(profile, document=document, profile_sha256=c.raw_digest(raw))

    def forbidden(*args, **kwargs):
        raise AssertionError("invalid actual profile must not spawn")

    monkeypatch.setattr(transport, "run_bounded_process", forbidden)
    with pytest.raises(s.VerificationError, match="runtime-unsupported"):
        v._run_diagnostic_verifier(material.request, profile=profile)


def test_profile_symlink_and_writable_import_root_refuse(material, tmp_path, monkeypatch):
    profile = runtime_profile(tmp_path)
    link = profile.profile_path.parent / "link.json"
    link.symlink_to(profile.profile_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("invalid path must not spawn")

    monkeypatch.setattr(transport, "run_bounded_process", forbidden)
    with pytest.raises(OSError):
        v._run_diagnostic_verifier(
            material.request, profile=replace(profile, profile_path=PosixPath(link))
        )
    bad_root = tmp_path / "writable"
    bad_root.mkdir(mode=0o777)
    bad_root.chmod(0o777)
    document = replace(profile.document, application_root=PosixPath(bad_root))
    raw = c.encode_document(m.record_dict(document), s.RUNTIME)
    profile.profile_path.write_bytes(raw)
    with pytest.raises(ValueError, match="runtime-unsupported"):
        v._run_diagnostic_verifier(
            material.request,
            profile=replace(profile, document=document, profile_sha256=c.raw_digest(raw)),
        )


@pytest.mark.parametrize("poison", ["prefix", "nonempty-cache", "cache-mode"])
def test_actual_worker_rejects_wrong_or_nonempty_private_cache(
    material, tmp_path, monkeypatch, poison
):
    profile = runtime_profile(tmp_path)
    original = transport.run_bounded_process

    def poisoned(argv, **kwargs):
        cache = kwargs["cwd"] / "pycache"
        if poison == "prefix":
            argv = tuple(
                "pycache_prefix=" + str(tmp_path / "old-cache")
                if item.startswith("pycache_prefix=")
                else item
                for item in argv
            )
        elif poison == "nonempty-cache":
            (cache / "stale.pyc").write_bytes(b"stale diagnostic cache")
        else:
            cache.chmod(0o755)
        return original(argv, **kwargs)

    monkeypatch.setattr(transport, "run_bounded_process", poisoned)
    with pytest.raises(v.VerificationProcessError, match="runtime-unsupported") as caught:
        v._run_diagnostic_verifier(material.request, profile=profile)
    assert caught.value.outcome.returncode == 2


def test_ambient_python_loader_controls_are_not_forwarded(material, tmp_path, monkeypatch):
    profile = runtime_profile(tmp_path)
    poison = tmp_path / "ambient"
    poison.mkdir(mode=0o700)
    marker = tmp_path / "unexpected"
    (poison / "sitecustomize.py").write_text(f"open({str(marker)!r},'w').write('bad')")
    (poison / "evil.pth").write_text(f"import pathlib;pathlib.Path({str(marker)!r}).touch()")
    for name in ("PYTHONPATH", "PYTHONHOME", "PYTHONPYCACHEPREFIX", "PYTHONSTARTUP"):
        monkeypatch.setenv(name, str(poison))
    v._run_diagnostic_verifier(material.request, profile=profile)
    assert not marker.exists()


def test_poisoned_adjacent_pyc_is_ignored_for_fresh_private_prefix(material, tmp_path):
    # Task-owned trusted code copy, not scanned source. The stale cache has a
    # matching timestamp/size header but hostile test bytecode; -B alone loads it.
    application = tmp_path / "trusted-application"
    application.mkdir(mode=0o700)
    budget = _CopyBudget()
    for name in ("analysis", "services", "tools"):
        _private_copy_tree(ROOT / name, application / name, budget)
    source = application / "services/scan/accepted_inputs/schemas.py"
    cache_path = Path(importlib.util.cache_from_source(str(source)))
    py_compile.compile(str(source), cfile=str(cache_path), doraise=True)
    header = cache_path.read_bytes()[:16]
    poison = compile("raise RuntimeError('stale-cache-must-not-load')", str(source), "exec")
    cache_path.write_bytes(header + marshal.dumps(poison))
    profile = runtime_profile(tmp_path, application=application)
    checked = v._run_diagnostic_verifier(material.request, profile=profile)
    assert (
        checked.accepted_content_digest == material.request.expected_bundle.accepted_content_digest
    )


@pytest.mark.parametrize(
    "failure", ["exit-disagreement", "stdout-suffix", "stderr", "wrong-input-hash"]
)
def test_parent_never_admits_transport_or_domain_disagreement(
    material, tmp_path, monkeypatch, failure
):
    profile = runtime_profile(tmp_path)
    original = transport.run_bounded_process

    def changed(*args, **kwargs):
        outcome = original(*args, **kwargs)
        if failure == "exit-disagreement":
            return replace(outcome, returncode=2)
        raw = outcome.stdout.data
        if failure == "stdout-suffix":
            raw += b"\n"
        elif failure == "wrong-input-hash":
            row = c.parse_json(raw)
            row["request_sha256"] = "0" * 64
            raw = c.canonical_bytes(row)
        if failure == "stderr":
            stderr = transport.MemoryOutput(
                transport.StreamEvidence(1, 1, bytes.fromhex(c.raw_digest(b"x")), True, False), b"x"
            )
            return replace(outcome, stderr=stderr)
        stdout = transport.MemoryOutput(
            transport.StreamEvidence(
                len(raw), len(raw), bytes.fromhex(c.raw_digest(raw)), True, False
            ),
            raw,
        )
        return replace(outcome, stdout=stdout)

    monkeypatch.setattr(transport, "run_bounded_process", changed)
    with pytest.raises(v.VerificationProcessError):
        v._run_diagnostic_verifier(material.request, profile=profile)


def test_operational_wrapper_never_uses_diagnostic_runner(material, tmp_path, monkeypatch):
    profile = runtime_profile(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("operational authority is unavailable")

    monkeypatch.setattr(v, "_run_diagnostic_verifier", forbidden)
    monkeypatch.setattr(transport, "run_bounded_process", forbidden)
    with pytest.raises(s.VerificationError, match="runtime-unsupported"):
        v.run_isolated_verifier(material.request, profile=profile)


@pytest.mark.parametrize("failure", ["cleanup-only", "cleanup-interrupt", "transport", "interrupt"])
def test_later_workspace_cleanup_preserves_outcome_and_original_failure(
    material, tmp_path, monkeypatch, failure
):
    profile = runtime_profile(tmp_path)
    original_directory = v.TemporaryDirectory
    cleanup_error = KeyboardInterrupt() if failure == "cleanup-interrupt" else OSError("cleanup")

    class FailingCleanup(original_directory):
        def cleanup(self):
            super().cleanup()
            raise cleanup_error

    monkeypatch.setattr(v, "TemporaryDirectory", FailingCleanup)
    original_run = transport.run_bounded_process
    observed = []
    failures = []
    prior = OSError("original low-level failure")

    def failing_run(*args, **kwargs):
        outcome = original_run(*args, **kwargs)
        observed.append(outcome)
        if failure in ("transport", "interrupt"):
            primary = transport.ProcessTransportError(outcome)
            if failure == "interrupt":
                primary = KeyboardInterrupt()
            failures.append(primary)
            raise primary from prior
        return outcome

    monkeypatch.setattr(transport, "run_bounded_process", failing_run)
    with pytest.raises(BaseException) as caught:
        v._run_diagnostic_verifier(material.request, profile=profile)
    assert len(observed) == 1 and observed[0].returncode == 0
    if failures:
        assert caught.value is failures[0]
        assert type(caught.value.__cause__) is BaseExceptionGroup or isinstance(
            caught.value.__cause__, ExceptionGroup
        )
        assert caught.value.__cause__.exceptions == (prior, cleanup_error)
    elif failure == "cleanup-interrupt":
        assert caught.value is cleanup_error
        assert caught.value.__cause__.outcome is observed[0]
    else:
        assert caught.value.outcome is observed[0]
        assert caught.value.__cause__ is cleanup_error
    assert list(profile.document.work_root.iterdir()) == []


@pytest.mark.parametrize("fault", ["address-space", "wall-time", "resource-setup"])
def test_real_kernel_limit_or_setup_failure_is_not_a_result(material, tmp_path, fault):
    assert _DIAGNOSTIC_RUNTIME is not None
    original = _DIAGNOSTIC_RUNTIME[3] / "services/scan/accepted_inputs/verifier_worker.py"
    text = original.read_text()
    needle = "        profile_bytes, profile = prepare_runtime(tuple(sys.argv))"
    if fault == "address-space":
        text = text.replace(needle, needle + "\n        bytearray(256 * 1024 * 1024)", 1)
    elif fault == "wall-time":
        text = text.replace(needle, needle + "\n        import time\n        time.sleep(30)", 1)
    else:
        text = text.replace(
            "        resource.setrlimit(kind, limits)",
            '        raise OSError("controlled resource setup failure")',
            1,
        )
    assert text != original.read_text()
    script = tmp_path / "controlled_fault_worker.py"
    script.write_text(text)
    script.chmod(0o600)
    profile = runtime_profile(tmp_path, script=script)
    with pytest.raises(v.VerificationProcessError, match="runtime-unsupported") as caught:
        v._run_diagnostic_verifier(material.request, profile=profile)
    outcome = caught.value.outcome
    assert outcome.cleanup == "completed"
    if fault == "wall-time":
        assert outcome.reason == "timeout"
    else:
        assert outcome.returncode == 2
        result = c.decode_result(outcome.stdout.data)
        assert result.status == "rejected" and result.checks is None
        assert result.operation_id is None and result.request_sha256 is None
