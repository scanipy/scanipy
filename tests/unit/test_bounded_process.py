"""Trusted Python transport children only; no scanned/native domain execution."""

from __future__ import annotations

import hashlib
import json
import os
import signal
import stat
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tools.worker import bounded_process as bp

pytestmark = pytest.mark.unit
_MIB = 1024 * 1024


@pytest.fixture
def configured(tmp_path):
    cwd = tmp_path / "work"
    spool = tmp_path / "spool"
    cwd.mkdir(mode=0o700)
    spool.mkdir(mode=0o700)
    cwd.chmod(0o700)
    spool.chmod(0o700)
    return {
        "stdin": b"",
        "env": {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        "cwd": cwd,
        "limits": bp.ProcessLimits(4 * _MIB, _MIB, _MIB, 2 * _MIB, 5000, 1000),
    }


def _argv(configured, code):
    return (
        str(Path(sys.executable).resolve()),
        "-I",
        "-S",
        "-B",
        "-X",
        f"pycache_prefix={configured['cwd'] / 'private-pycache'}",
        "-c",
        code,
    )


def _run(configured, code, **changes):
    return bp.run_bounded_process(_argv(configured, code), **(configured | changes))


def _reaped(outcome):
    assert outcome.pid is not None and outcome.pid == outcome.pgid
    assert outcome.returncode is not None
    with pytest.raises(ChildProcessError):
        os.waitpid(outcome.pid, os.WNOHANG)


@pytest.mark.parametrize("payload", [None, b"", b"zero\0bytes\xff\r\n"])
def test_actual_binary_input_and_eof(configured, payload):
    outcome = _run(
        configured, "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())", stdin=payload
    )
    expected = payload or b""
    assert outcome.reason == "exited" and outcome.returncode == 0
    assert outcome.cleanup == "completed"
    assert outcome.stdin_sent_bytes == len(expected)
    assert outcome.invocation.stdin_sha256 == hashlib.sha256(expected).digest()
    assert outcome.stdout.data == expected and outcome.stderr.data == b""
    for stream in (outcome.stdout, outcome.stderr):
        assert stream.evidence.eof and not stream.evidence.truncated
        assert stream.evidence.retained_bytes == stream.evidence.observed_bytes
    _reaped(outcome)


def test_exact_closed_env_snapshot_not_caller_mutation(configured, monkeypatch):
    actual_popen = subprocess.Popen
    caller = configured["env"] | {"MARKER": "original-private-value"}

    def spawn(argv, **kwargs):
        assert kwargs["env"] is not caller
        assert kwargs["shell"] is False and kwargs["close_fds"] is True
        assert kwargs["start_new_session"] is True
        assert kwargs["cwd"] == configured["cwd"]
        caller["MARKER"] = "changed"
        caller["NEW_KEY"] = "not-forwarded"
        return actual_popen(argv, **kwargs)

    monkeypatch.setattr(bp.subprocess, "Popen", spawn)
    outcome = _run(
        configured, "import os,json; print(json.dumps(dict(os.environ),sort_keys=True))", env=caller
    )
    actual = json.loads(outcome.stdout.data)
    assert actual == dict(outcome.invocation.environment)
    assert actual["MARKER"] == "original-private-value"
    assert "NEW_KEY" not in actual and "PATH" not in actual and "PYTHONPATH" not in actual
    for record in (outcome, outcome.invocation, outcome.stdout):
        assert "original-private-value" not in repr(record)


@pytest.mark.parametrize("mode", ["memory", "spool"])
def test_concurrent_input_and_both_outputs_do_not_deadlock(configured, mode):
    size = 256 * 1024
    code = (
        "import os,sys; "
        f"os.write(1,b'o'*{size}); os.write(2,b'e'*{size}); "
        "data=sys.stdin.buffer.read(); sys.stdout.buffer.write(data)"
    )
    changes = {"stdin": b"i" * size}
    if mode == "spool":
        changes["spool_dir"] = configured["cwd"].parent / "spool"
    outcome = _run(configured, code, **changes)
    assert outcome.reason == "exited" and outcome.returncode == 0
    for output, expected in (
        (outcome.stdout, b"o" * size + b"i" * size),
        (outcome.stderr, b"e" * size),
    ):
        data = output.data if type(output) is bp.MemoryOutput else output.path.read_bytes()
        assert data == expected
        assert output.evidence.retained_sha256 == hashlib.sha256(expected).digest()
        assert output.evidence.eof and not output.evidence.truncated
        if type(output) is bp.SpoolOutput:
            assert stat.S_IMODE(output.path.stat().st_mode) == 0o600
    _reaped(outcome)


@pytest.mark.parametrize(
    "which,extra", [("stdout", 0), ("stdout", 1), ("stderr", 0), ("stderr", 1)]
)
def test_exact_stream_caps_and_cap_plus_one(configured, which, extra):
    cap = 1000
    target = 1 if which == "stdout" else 2
    limits = bp.ProcessLimits(0, cap, cap, cap * 2, 5000, 1000)
    outcome = _run(configured, f"import os; os.write({target},b'x'*{cap + extra})", limits=limits)
    output = getattr(outcome, which)
    assert output.data == b"x" * cap
    assert output.evidence.observed_bytes == cap + extra
    assert output.evidence.truncated is bool(extra)
    if extra:
        assert outcome.reason == f"{which}_limit"
    else:
        assert outcome.reason == "exited" and output.evidence.eof
    _reaped(outcome)


def test_combined_cap_is_independent(configured):
    limits = bp.ProcessLimits(0, 1000, 1000, 1500, 5000, 1000)
    outcome = _run(
        configured, "import os; os.write(1,b'a'*1000); os.write(2,b'b'*1000)", limits=limits
    )
    assert outcome.reason == "combined_output_limit"
    assert sum(item.evidence.retained_bytes for item in (outcome.stdout, outcome.stderr)) == 1500
    assert sum(item.evidence.observed_bytes for item in (outcome.stdout, outcome.stderr)) == 2000
    assert outcome.stdout.evidence.truncated or outcome.stderr.evidence.truncated
    _reaped(outcome)


def test_zero_cap_and_large_continuous_output_are_bounded(configured):
    limits = bp.ProcessLimits(0, 0, 0, 0, 5000, 1000)
    outcome = _run(configured, "import os;\nwhile True: os.write(1,b'x'*65536)", limits=limits)
    assert outcome.reason == "stdout_limit" and outcome.stdout.data == b""
    assert 0 < outcome.stdout.evidence.observed_bytes <= 65536
    assert outcome.stdout.evidence.truncated and not outcome.stdout.evidence.eof
    _reaped(outcome)


def test_nonzero_exit_is_not_success_or_output_exception(configured):
    outcome = _run(configured, "import os; os.write(2,b'private-error'); raise SystemExit(7)")
    assert outcome.reason == "exited" and outcome.returncode == 7
    assert outcome.stderr.data == b"private-error"
    assert outcome.cleanup == "completed"
    _reaped(outcome)


def test_early_stdin_close_never_reports_full_protocol(configured):
    outcome = _run(configured, "import os,time; os.close(0); time.sleep(0.2)", stdin=b"i" * _MIB)
    assert outcome.reason == "stdin_closed"
    assert outcome.stdin_sent_bytes < outcome.invocation.stdin_bytes
    _reaped(outcome)


@pytest.mark.parametrize("descendant_pipes", [False, True])
def test_deadline_and_same_group_descendants(configured, descendant_pipes):
    limits = bp.ProcessLimits(0, 1024, 1024, 2048, 1200, 500)
    if descendant_pipes:
        code = (
            "import os,time; pid=os.fork();\n"
            "if pid: os.write(1,str(pid).encode()+b'\\n'); os._exit(0)\n"
            "time.sleep(30)"
        )
    else:
        code = "import time; time.sleep(30)"
    started = time.monotonic()
    outcome = _run(configured, code, limits=limits)
    assert outcome.reason == "timeout" and outcome.cleanup == "completed"
    assert time.monotonic() - started < 3
    assert not outcome.stdout.evidence.eof
    _reaped(outcome)
    if descendant_pipes:
        descendant = int(outcome.stdout.data)
        state = Path(f"/proc/{descendant}/stat")
        # Signal delivery/termination is not a claim of reaping another parent.
        for _ in range(100):
            if not state.exists() or state.read_text().split()[2] == "Z":
                break
            time.sleep(0.005)
        else:
            pytest.fail("owned-group test descendant still running")


def test_normal_exit_still_signals_same_group_closed_pipe_descendant(configured):
    code = (
        "import os,time; pid=os.fork();\n"
        "if pid: os.write(1,str(pid).encode()+b'\\n'); os._exit(0)\n"
        "os.close(0); os.close(1); os.close(2); time.sleep(30)"
    )
    outcome = _run(configured, code)
    assert outcome.reason == "exited" and outcome.returncode == 0
    descendant = int(outcome.stdout.data)
    state = Path(f"/proc/{descendant}/stat")
    for _ in range(100):
        if not state.exists() or state.read_text().split()[2] == "Z":
            break
        time.sleep(0.005)
    else:
        pytest.fail("same-group descendant survived normal cleanup")
    _reaped(outcome)


class PoisonDict(dict):
    def copy(self):
        raise AssertionError("custom dictionary callback")


class PoisonTuple(tuple):
    def __iter__(self):
        raise AssertionError("custom tuple callback")


@pytest.mark.parametrize(
    "field,value",
    [
        ("env", PoisonDict()),
        ("env", {"": "bad"}),
        ("env", {"A=B": "bad"}),
        ("env", {"A": "\0"}),
        ("env", {"A": "\ud800"}),
        ("env", {"A": 1}),
        ("env", {"A" * 129: "x"}),
        ("env", {"A": "x" * 8193}),
        ("env", {str(index): "x" for index in range(65)}),
        ("env", {str(index): "x" * 8192 for index in range(9)}),
        ("stdin", bytearray(b"mutable")),
        ("stdin", memoryview(b"alias")),
        ("stdin", b"x" * (4 * _MIB + 1)),
        ("cwd", Path("relative")),
        ("cwd", Path("/")),
        ("cwd", Path("/tmp/../unsafe")),
        ("cwd", "/tmp/path"),
    ],
    ids=[
        "custom-dict",
        "empty-env-key",
        "equals-env-key",
        "nul-env",
        "surrogate-env",
        "nonstring-env",
        "env-key-bound",
        "env-value-bound",
        "env-count-bound",
        "env-total-bound",
        "mutable-stdin",
        "aliased-stdin",
        "stdin-byte-bound",
        "relative-cwd",
        "root-cwd",
        "parent-cwd",
        "string-cwd",
    ],
)
def test_bad_arguments_before_filesystem_or_spawn(configured, monkeypatch, field, value):
    open_call = Mock(side_effect=AssertionError("filesystem validation must not begin"))
    spawn = Mock(side_effect=AssertionError("spawn must not begin"))
    monkeypatch.setattr(bp.os, "open", open_call)
    monkeypatch.setattr(bp.subprocess, "Popen", spawn)
    with pytest.raises(bp.ProcessValidationError):
        _run(configured, "pass", **{field: value})
    open_call.assert_not_called()
    spawn.assert_not_called()


@pytest.mark.parametrize(
    "argv",
    [
        [],
        (),
        PoisonTuple(("/python",)),
        ("python",),
        ("/x",) * 257,
        ("/x", "a" * 8193),
        ("/x", "\0"),
        ("/x", "\ud800"),
        ("/x", 1),
        ("/x",) + ("x" * 8192,) * 8,
    ],
)
def test_bad_argv_never_launches(configured, monkeypatch, argv):
    spawn = Mock()
    monkeypatch.setattr(bp.subprocess, "Popen", spawn)
    with pytest.raises(bp.ProcessValidationError):
        bp.run_bounded_process(argv, **configured)
    spawn.assert_not_called()


@pytest.mark.parametrize(
    "field,value",
    [
        ("stdin_bytes", True),
        ("stdin_bytes", -1),
        ("stdin_bytes", 4 * _MIB + 1),
        ("stdout_bytes", 128 * _MIB + 1),
        ("stderr_bytes", _MIB + 1),
        ("wall_ms", 0),
        ("wall_ms", 300001),
        ("wall_ms", 1000),
        ("cleanup_reserve_ms", 0),
        ("cleanup_reserve_ms", 5001),
        ("combined_output_bytes", 3 * _MIB),
    ],
)
def test_limits_are_exact_bounded_integers(configured, field, value):
    with pytest.raises(bp.ProcessValidationError):
        replace(configured["limits"], **{field: value})


def test_memory_ceiling_is_not_python_domain_ceiling(configured, monkeypatch):
    # Pure acceptance of the reviewed Semgrep-compatible generic ceiling;
    # no native scanner is invoked and no large buffer is allocated.
    limits = bp.ProcessLimits(0, 16 * _MIB, _MIB, 17 * _MIB, 5000, 1000)
    assert _run(configured, "pass", limits=limits).returncode == 0
    spawn = Mock()
    monkeypatch.setattr(bp.subprocess, "Popen", spawn)
    with pytest.raises(bp.ProcessValidationError):
        _run(configured, "pass", limits=replace(limits, stdout_bytes=16 * _MIB + 1))
    spawn.assert_not_called()


@pytest.mark.parametrize("kind", ["cwd-mode", "cwd-link", "spool-link", "spool-nonempty", "same"])
def test_unsafe_filesystem_routes_do_not_launch(configured, monkeypatch, kind):
    cwd = configured["cwd"]
    spool = cwd.parent / "spool"
    changes = {}
    if kind == "cwd-mode":
        cwd.chmod(0o755)
    elif kind == "cwd-link":
        link = cwd.parent / "link"
        link.symlink_to(cwd, target_is_directory=True)
        changes["cwd"] = link
    elif kind == "spool-link":
        link = cwd.parent / "link"
        link.symlink_to(spool, target_is_directory=True)
        changes["spool_dir"] = link
    elif kind == "spool-nonempty":
        (spool / "stdout.bin").write_bytes(b"must-survive")
        changes["spool_dir"] = spool
    else:
        changes["spool_dir"] = cwd
    spawn = Mock()
    monkeypatch.setattr(bp.subprocess, "Popen", spawn)
    expected = bp.ProcessValidationError if kind == "same" else bp.ProcessTransportError
    with pytest.raises(expected):
        _run(configured, "pass", **changes)
    spawn.assert_not_called()
    if kind == "spool-nonempty":
        assert (spool / "stdout.bin").read_bytes() == b"must-survive"


def test_deadline_includes_first_filesystem_validation(configured, monkeypatch):
    original = bp._open_directory

    def delayed(path, deadline):
        time.sleep(0.04)
        return original(path, deadline)

    spawn = Mock()
    monkeypatch.setattr(bp, "_open_directory", delayed)
    monkeypatch.setattr(bp.subprocess, "Popen", spawn)
    with pytest.raises(bp.ProcessTransportError) as caught:
        _run(configured, "pass", limits=bp.ProcessLimits(0, 0, 0, 0, 30, 10))
    assert caught.value.outcome.reason == "timeout"
    assert caught.value.outcome.cleanup == "not_started"
    assert caught.value.outcome.elapsed_ms >= 30
    spawn.assert_not_called()


def test_spawn_failure_preserves_private_cause_without_inventing_pid(configured):
    with pytest.raises(bp.ProcessTransportError) as caught:
        bp.run_bounded_process((str(configured["cwd"] / "missing-private-binary"),), **configured)
    error = caught.value
    assert isinstance(error.__cause__, FileNotFoundError)
    assert "missing-private-binary" not in str(error) + repr(error)
    assert error.outcome.pid is None and error.outcome.pgid is None
    assert error.outcome.reason == "spawn_error" and error.outcome.cleanup == "not_started"


@pytest.mark.parametrize("operation", ["read", "fstat", "fsync", "corrupt-write"])
def test_spool_observation_failures_are_fatal_and_not_fake_digests(
    configured, monkeypatch, operation
):
    original_stat = os.fstat
    original = getattr(os, "write" if operation == "corrupt-write" else operation)

    def failing(fd, *args):
        if stat.S_ISREG(original_stat(fd).st_mode):
            if operation == "corrupt-write":
                return original(fd, b"x" * len(args[0]))
            raise OSError("private required evidence unavailable")
        return original(fd, *args)

    monkeypatch.setattr(bp.os, "write" if operation == "corrupt-write" else operation, failing)
    with pytest.raises(bp.ProcessTransportError) as caught:
        _run(
            configured,
            "import os; os.write(1,b'actual'); raise SystemExit(7)",
            spool_dir=configured["cwd"].parent / "spool",
        )
    outcome = caught.value.outcome
    assert outcome.returncode == 7 and outcome.cleanup == "incomplete"
    assert outcome.stdout.evidence.retained_bytes is None
    assert outcome.stdout.evidence.retained_sha256 is None
    assert outcome.stdout.path.exists()
    assert "private required" not in str(caught.value) + repr(caught.value)
    _reaped(outcome)


def test_short_spool_and_stdin_writes_are_completed(configured, monkeypatch):
    original = os.write

    def short(fd, data):
        return original(fd, data[: max(1, len(data) // 2)])

    monkeypatch.setattr(bp.os, "write", short)
    payload = b"unchanged\0" * 2000
    outcome = _run(
        configured,
        "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())",
        stdin=payload,
        spool_dir=configured["cwd"].parent / "spool",
    )
    assert outcome.stdout.path.read_bytes() == payload
    assert outcome.stdout.evidence.retained_sha256 == hashlib.sha256(payload).digest()
    assert outcome.stdin_sent_bytes == len(payload) and outcome.returncode == 0


@pytest.mark.parametrize(
    "interruption", [KeyboardInterrupt("private cancellation"), SystemExit(42)]
)
def test_interruption_identity_prior_cause_and_cleanup_preserved(
    configured, monkeypatch, interruption
):
    previous = OSError("private earlier cause")
    interruption.__cause__ = previous

    def interrupted(_run):
        raise interruption

    monkeypatch.setattr(bp._Run, "pump", interrupted)
    with pytest.raises(type(interruption)) as caught:
        _run(configured, "import time; time.sleep(30)")
    assert caught.value is interruption
    evidence_error = interruption.__cause__
    assert type(evidence_error) is bp.ProcessTransportError
    assert evidence_error.__cause__ is previous
    assert evidence_error.outcome.reason == "cancelled"
    assert evidence_error.outcome.returncode == -signal.SIGKILL
    assert evidence_error.outcome.cleanup == "completed"
    _reaped(evidence_error.outcome)


def test_reap_failure_keeps_unknown_status_and_owned_handle(configured, monkeypatch):
    def failed_reap(_run):
        raise OSError("controlled reap failure")

    monkeypatch.setattr(bp._Run, "_reap", failed_reap)
    with pytest.raises(bp.ProcessTransportError) as caught:
        _run(configured, "pass")
    error = caught.value
    try:
        assert error.outcome.cleanup == "incomplete" and error.outcome.returncode is None
        assert error.outcome.pid == error._owned_child.pid
    finally:
        # Test-only bounded disposal of its exact live handle, not product fallback.
        error._owned_child.wait(timeout=3)


def test_never_signal_numeric_group_after_unexpected_reap(configured, monkeypatch):
    def prematurely_reaped(run):
        run.child.wait(timeout=3)
        return "exited"

    signal_call = Mock()
    monkeypatch.setattr(bp._Run, "pump", prematurely_reaped)
    monkeypatch.setattr(bp.os, "killpg", signal_call)
    with pytest.raises(bp.ProcessTransportError) as caught:
        _run(configured, "pass")
    assert caught.value.outcome.cleanup == "incomplete"
    signal_call.assert_not_called()


@pytest.mark.parametrize(
    "count,digest,eof,truncated",
    [
        (None, b"x" * 32, False, False),
        (1, None, False, False),
        (2, b"x" * 32, False, False),
        (0, b"x" * 32, False, False),
        (True, b"x" * 32, False, False),
        (1, b"short", False, False),
        (1, b"x" * 32, 1, False),
    ],
)
def test_evidence_cross_field_invariants(count, digest, eof, truncated):
    with pytest.raises(bp.ProcessValidationError):
        bp.StreamEvidence(1, count, digest, eof, truncated)


def test_memory_hash_and_outcome_invariants(configured):
    outcome = _run(configured, "pass")
    with pytest.raises(bp.ProcessValidationError):
        bp.MemoryOutput(outcome.stdout.evidence, b"not-retained")
    for changes in (
        {"pgid": outcome.pid + 1},
        {"stdin_sent_bytes": 1},
        {"cleanup": "not_started"},
        {"returncode": None},
        {"stdout": None},
    ):
        with pytest.raises(bp.ProcessValidationError):
            replace(outcome, **changes)


@pytest.mark.parametrize(
    "mode", ["short-write", "intermediate-link", "exclusive-race", "hardlink", "unlink"]
)
def test_spool_descriptor_and_exclusive_creation_fences(configured, monkeypatch, mode):
    spool = configured["cwd"].parent / "spool"
    if mode == "short-write":
        original = os.write

        def failed_write(fd, data):
            if stat.S_ISREG(os.fstat(fd).st_mode):
                return 0
            return original(fd, data)

        monkeypatch.setattr(bp.os, "write", failed_write)
    elif mode == "intermediate-link":
        link = spool.parent / "parent-link"
        link.symlink_to(spool.parent, target_is_directory=True)
        spool = link / "spool"
    elif mode == "exclusive-race":
        actual_open = os.open
        target = spool.parent / "must-survive"
        target.write_bytes(b"outside-spool")

        def race(path, flags, *args, **kwargs):
            if path == "stdout.bin":
                (spool / "stdout.bin").symlink_to(target)
            return actual_open(path, flags, *args, **kwargs)

        monkeypatch.setattr(bp.os, "open", race)
    else:
        actual_verify = bp._Sink.verify

        def changed(sink, deadline):
            if sink.path.name == "stdout.bin":
                if mode == "hardlink":
                    os.link(sink.path, spool.parent / "extra-link")
                else:
                    sink.path.unlink()
            return actual_verify(sink, deadline)

        monkeypatch.setattr(bp._Sink, "verify", changed)
    with pytest.raises(bp.ProcessTransportError) as caught:
        _run(configured, "import os; os.write(1,b'output')", spool_dir=spool)
    if mode == "exclusive-race":
        assert target.read_bytes() == b"outside-spool"
    if mode in {"hardlink", "unlink"}:
        assert caught.value.outcome.stdout.evidence.retained_sha256 is None
    if caught.value.outcome.pid is not None:
        _reaped(caught.value.outcome)


def test_new_spool_files_ignore_permissive_and_restrictive_umasks(configured):
    for index, mask in enumerate((0, 0o777)):
        spool = configured["cwd"].parent / f"private-{index}"
        spool.mkdir(mode=0o700)
        spool.chmod(0o700)
        previous = os.umask(mask)
        try:
            outcome = _run(configured, "print('preserved')", spool_dir=spool)
        finally:
            os.umask(previous)
        assert outcome.stdout.path.read_bytes() == b"preserved\n"
        assert stat.S_IMODE(outcome.stdout.path.stat().st_mode) == 0o600


def test_abort_preserves_verified_spool_prefix_but_not_full_output(configured):
    limits = bp.ProcessLimits(0, 17, 0, 17, 5000, 1000)
    outcome = _run(
        configured,
        "import os; os.write(1,b'x'*18)",
        limits=limits,
        spool_dir=configured["cwd"].parent / "spool",
    )
    assert outcome.reason == "stdout_limit" and outcome.cleanup == "completed"
    assert outcome.stdout.path.read_bytes() == b"x" * 17
    assert outcome.stdout.evidence.retained_bytes == 17
    assert outcome.stdout.evidence.retained_sha256 == hashlib.sha256(b"x" * 17).digest()
    assert outcome.stdout.evidence.truncated and not outcome.stdout.evidence.eof


def test_interruption_and_independent_evidence_failure_preserve_all_causes(configured, monkeypatch):
    interrupted = KeyboardInterrupt("private cancellation")
    earlier = RuntimeError("earlier private failure")
    interrupted.__cause__ = earlier
    storage = OSError("private storage failure")

    def stop(_run):
        raise interrupted

    def failed_observation(_sink, _deadline):
        raise storage

    monkeypatch.setattr(bp._Run, "pump", stop)
    monkeypatch.setattr(bp._Sink, "verify", failed_observation)
    with pytest.raises(KeyboardInterrupt) as caught:
        _run(configured, "import time; time.sleep(30)")
    assert caught.value is interrupted
    evidence = caught.value.__cause__
    assert type(evidence) is bp.ProcessTransportError
    assert evidence.outcome.cleanup == "incomplete"
    group = evidence.__cause__
    assert isinstance(group, BaseExceptionGroup)
    assert earlier in group.exceptions and storage in group.exceptions
    assert interrupted not in group.exceptions
    _reaped(evidence.outcome)


def test_no_unbounded_popen_options_or_shared_descriptors(configured, monkeypatch):
    original = subprocess.Popen
    seen = []

    def observed(argv, **kwargs):
        seen.append(kwargs)
        return original(argv, **kwargs)

    monkeypatch.setattr(bp.subprocess, "Popen", observed)
    _run(configured, "pass")
    assert len(seen) == 1
    assert set(seen[0]) == {
        "stdin",
        "stdout",
        "stderr",
        "shell",
        "close_fds",
        "start_new_session",
        "cwd",
        "env",
    }
    assert all(seen[0][name] == subprocess.PIPE for name in ("stdin", "stdout", "stderr"))


def test_unsupported_platform_is_prelaunch(configured, monkeypatch):
    spawn = Mock()
    monkeypatch.setattr(bp.sys, "platform", "win32")
    monkeypatch.setattr(bp.subprocess, "Popen", spawn)
    with pytest.raises(bp.ProcessValidationError):
        _run(configured, "pass")
    spawn.assert_not_called()


def test_no_descriptor_leak_on_success_and_spool_refusal(configured):
    initial = len(tuple(Path("/proc/self/fd").iterdir()))
    spool = configured["cwd"].parent / "spool"
    _run(configured, "pass", spool_dir=spool)
    for _ in range(3):
        with pytest.raises(bp.ProcessTransportError):
            _run(configured, "pass", spool_dir=spool)
        _run(configured, "pass")
    assert len(tuple(Path("/proc/self/fd").iterdir())) == initial


@pytest.mark.parametrize("poison", ["method", "data", "both", "attribute-dict"])
def test_exact_frozen_limits_cannot_supply_method_callbacks(configured, monkeypatch, poison):
    limits = replace(configured["limits"])
    callback = Mock(side_effect=AssertionError("caller instance callback"))
    if poison in {"method", "both"}:
        object.__setattr__(limits, "__post_init__", callback)
    if poison in {"data", "both"}:
        object.__setattr__(limits, "wall_ms", True)
    if poison == "attribute-dict":
        object.__setattr__(limits, "__dict__", PoisonDict(vars(limits)))
    spawn = Mock()
    opened = Mock()
    monkeypatch.setattr(bp.subprocess, "Popen", spawn)
    monkeypatch.setattr(bp.os, "open", opened)
    with pytest.raises(bp.ProcessValidationError):
        _run(configured, "pass", limits=limits)
    callback.assert_not_called()
    spawn.assert_not_called()
    opened.assert_not_called()


def test_limits_are_private_snapshot_not_mutated_caller_record(configured, monkeypatch):
    limits = bp.ProcessLimits(0, 4, 0, 4, 5000, 1000)
    original = subprocess.Popen

    def mutate(argv, **kwargs):
        object.__setattr__(limits, "stdout_bytes", 100000)
        object.__setattr__(limits, "combined_output_bytes", 100000)
        return original(argv, **kwargs)

    monkeypatch.setattr(bp.subprocess, "Popen", mutate)
    outcome = _run(configured, "import os; os.write(1,b'12345')", limits=limits)
    assert outcome.reason == "stdout_limit" and outcome.stdout.data == b"1234"


def test_post_snapshot_deadline_cannot_return_completed_success(configured, monkeypatch):
    clock_offset = [0.0]
    actual_time = time.monotonic
    clock = SimpleNamespace(monotonic=lambda: actual_time() + clock_offset[0], sleep=time.sleep)
    original = bp._Sink.snapshot

    def slow_snapshot(sink):
        result = original(sink)
        clock_offset[0] = 10.0
        return result

    monkeypatch.setattr(bp, "time", clock)
    monkeypatch.setattr(bp._Sink, "snapshot", slow_snapshot)
    with pytest.raises(bp.ProcessTransportError) as caught:
        _run(configured, "print('retained-before-deadline-check')")
    outcome = caught.value.outcome
    assert outcome.reason == "exited" and outcome.returncode == 0
    assert outcome.cleanup == "incomplete" and outcome.elapsed_ms >= 10000
    assert outcome.stdout.data == b"retained-before-deadline-check\n"
    assert isinstance(caught.value.__cause__, TimeoutError)
    _reaped(outcome)


@pytest.mark.parametrize("failure_kind", ["ordinary", "interrupt", "system-exit"])
def test_final_snapshot_failure_keeps_other_stream_and_prior_failures(
    configured, monkeypatch, failure_kind
):
    original_snapshot = bp._Sink.snapshot
    original_verify = bp._Sink.verify
    pump_failure = OSError("private prior pump failure")
    cleanup_failure = OSError("private prior cleanup failure")
    final_failure = {
        "ordinary": RuntimeError("private final hash failure"),
        "interrupt": KeyboardInterrupt("private final interruption"),
        "system-exit": SystemExit(42),
    }[failure_kind]
    recorded = {}

    def pump(run):
        recorded["stderr"] = run.outputs[1]
        # First stream's exact retained evidence can survive the second's error.
        run.outputs[0].observed = 4
        run.outputs[0].retain(b"kept", run.productive)
        raise pump_failure

    def verify(sink, deadline):
        original_verify(sink, deadline)
        if sink is recorded["stderr"]:
            raise cleanup_failure

    def snapshot(sink):
        if sink is recorded["stderr"]:
            raise final_failure
        return original_snapshot(sink)

    monkeypatch.setattr(bp._Run, "pump", pump)
    monkeypatch.setattr(bp._Sink, "verify", verify)
    monkeypatch.setattr(bp._Sink, "snapshot", snapshot)
    expected = bp.ProcessTransportError if failure_kind == "ordinary" else type(final_failure)
    with pytest.raises(expected) as caught:
        _run(configured, "import time; time.sleep(30)")
    if failure_kind == "ordinary":
        evidence = caught.value
    else:
        assert caught.value is final_failure
        evidence = caught.value.__cause__
    assert type(evidence) is bp.ProcessTransportError
    assert evidence.outcome.stdout.data == b"kept"
    assert evidence.outcome.stderr is None
    assert evidence.outcome.cleanup == "incomplete"
    group = evidence.__cause__
    assert isinstance(group, BaseExceptionGroup)
    assert pump_failure in group.exceptions and cleanup_failure in group.exceptions
    if failure_kind == "ordinary":
        assert final_failure in group.exceptions
    else:
        assert final_failure not in group.exceptions
    _reaped(evidence.outcome)


@pytest.mark.parametrize("interrupted", [False, True])
def test_final_outcome_construction_has_bounded_actual_fallback(
    configured, monkeypatch, interrupted
):
    original = (
        KeyboardInterrupt("private final result")
        if interrupted
        else OSError("private final result")
    )

    def fail(_run, _outputs, *, failed_cleanup):
        raise original

    monkeypatch.setattr(bp._Run, "outcome", fail)
    expected = KeyboardInterrupt if interrupted else bp.ProcessTransportError
    with pytest.raises(expected) as caught:
        _run(configured, "print('already-retained')")
    if interrupted:
        assert caught.value is original
        evidence = caught.value.__cause__
    else:
        evidence = caught.value
        assert evidence.__cause__ is original
    assert evidence.outcome.stdout.data == b"already-retained\n"
    assert evidence.outcome.stderr.data == b""
    assert evidence.outcome.cleanup == "incomplete"
    _reaped(evidence.outcome)


class _PoisonPathValue:
    def __getitem__(self, _key):
        raise AssertionError("caller path slicing callback invoked")

    def __iter__(self):
        raise AssertionError("caller path iteration callback invoked")

    def __bool__(self):
        raise AssertionError("caller path truthiness callback invoked")

    def __str__(self):
        raise AssertionError("caller path formatting callback invoked")


@pytest.mark.parametrize("target", ["cwd", "spool_dir"])
def test_poisoned_path_storage_rejects_before_callback_or_filesystem(
    configured, monkeypatch, target
):
    argv = _argv(configured, "pass")
    path = Path(str(configured["cwd"]))
    storage = "_raw_paths" if hasattr(path, "_raw_paths") else "_parts"
    object.__setattr__(path, storage, _PoisonPathValue())
    try:
        object.__delattr__(path, "_str")
    except AttributeError:
        pass

    def forbidden(*_args, **_kwargs):
        raise AssertionError("invalid primitive path reached filesystem or spawn")

    monkeypatch.setattr(bp.os, "open", forbidden)
    monkeypatch.setattr(bp.subprocess, "Popen", forbidden)
    with pytest.raises(bp.ProcessValidationError):
        bp.run_bounded_process(argv, **(configured | {target: path}))


class _PoisonPathList(list):
    def __getitem__(self, _key):
        raise AssertionError("caller list slicing callback invoked")

    def __len__(self):
        raise AssertionError("caller list length callback invoked")


@pytest.mark.parametrize("target", ["cwd", "spool_dir", "output"])
@pytest.mark.parametrize(
    "kind", ["list-subclass", "member", "count", "member-size", "aggregate", "nul", "unicode"]
)
def test_path_primitive_bounds_precede_any_io(configured, monkeypatch, target, kind):
    argv = _argv(configured, "pass")
    path = Path(str(configured["cwd"]))
    storage = "_raw_paths" if hasattr(path, "_raw_paths") else "_parts"
    parts = {
        "list-subclass": _PoisonPathList(["/", "work"]),
        "member": ["/", _PoisonPathValue()],
        "count": ["x"] * 100_000,
        "member-size": ["/", "x" * 4097],
        "aggregate": ["/", "x" * 2048, "y" * 2048],
        "nul": ["/", "null\0member"],
        "unicode": ["/", "lone\ud800surrogate"],
    }[kind]
    object.__setattr__(path, storage, parts)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("invalid primitive path reached filesystem or spawn")

    monkeypatch.setattr(bp.os, "open", forbidden)
    monkeypatch.setattr(bp.subprocess, "Popen", forbidden)
    with pytest.raises(bp.ProcessValidationError):
        if target == "output":
            bp.SpoolOutput(bp.StreamEvidence(0, None, None, False, False), path)
        else:
            bp.run_bounded_process(argv, **(configured | {target: path}))


@pytest.mark.parametrize("field", ["_drv", "_root"])
def test_parsed_path_root_and_drive_are_exact_primitives(field):
    path = Path("/bounded/private-work")
    if hasattr(path, "_raw_paths"):
        # This layout has no parsed drive/root authority; raw components own it.
        object.__setattr__(path, "_raw_paths", [_PoisonPathValue()])
    else:
        object.__setattr__(path, field, _PoisonPathValue())
    with pytest.raises(bp.ProcessValidationError):
        bp._path(path)


def test_fresh_path_snapshot_used_for_launch_spool_and_evidence(configured, monkeypatch):
    argv = _argv(configured, "import os; print(os.getcwd())")
    expected_cwd = Path(str(configured["cwd"]))
    expected_spool = expected_cwd.parent / "spool"
    caller_cwd, caller_spool = Path(str(expected_cwd)), Path(str(expected_spool))
    for path in (caller_cwd, caller_spool):
        object.__setattr__(path, "_str", _PoisonPathValue())
        try:
            object.__setattr__(path, "_pparts", _PoisonPathValue())
        except AttributeError:
            pass
    actual_popen = bp.subprocess.Popen

    def spawn(args, **kwargs):
        assert kwargs["cwd"] is not caller_cwd and kwargs["cwd"] == expected_cwd
        for path in (caller_cwd, caller_spool):
            storage = "_raw_paths" if hasattr(path, "_raw_paths") else "_parts"
            object.__getattribute__(path, storage)[-1] = "changed-after-snapshot"
        return actual_popen(args, **kwargs)

    monkeypatch.setattr(bp.subprocess, "Popen", spawn)
    outcome = bp.run_bounded_process(
        argv, **(configured | {"cwd": caller_cwd, "spool_dir": caller_spool})
    )
    assert outcome.reason == "exited" and outcome.returncode == 0
    assert outcome.invocation.cwd == str(expected_cwd)
    assert outcome.stdout.path == expected_spool / "stdout.bin"
    assert outcome.stdout.path.read_bytes() == (str(expected_cwd) + "\n").encode()
    assert outcome.stderr.path == expected_spool / "stderr.bin"
    _reaped(outcome)


def test_spool_record_retains_its_own_path_snapshot():
    caller = Path("/bounded/private-spool/stdout.bin")
    output = bp.SpoolOutput(bp.StreamEvidence(0, None, None, False, False), caller)
    assert output.path is not caller
    storage = "_raw_paths" if hasattr(caller, "_raw_paths") else "_parts"
    object.__getattribute__(caller, storage)[-1] = _PoisonPathValue()
    object.__setattr__(caller, "_str", _PoisonPathValue())
    assert str(output.path) == "/bounded/private-spool/stdout.bin"


def test_path_utf8_limit_applies_to_the_fresh_normalized_value():
    exact = "/" + "é" * 2047 + "x"
    assert len(exact.encode()) == 4096
    assert str(bp._path(Path(exact))) == exact
    with pytest.raises(bp.ProcessValidationError):
        bp._path(Path(exact + "x"))
