"""One-shot bounded Linux process transport, not a domain execution permission.

See docs/bhmea/BOUNDED-PROCESS.md. Production adversarial/native use additionally
requires an independently enforced controller, resource envelope and no-egress
policy. Raw exception chains are private evidence, not public log messages.
"""

from __future__ import annotations

import hashlib
import os
import selectors
import signal
import stat
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path, PosixPath
from typing import Literal, Protocol, cast

_MIB = 1024 * 1024
_CHUNK = 64 * 1024
_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
_SPOOL_FLAGS = os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
Reason = Literal[
    "exited",
    "timeout",
    "stdin_closed",
    "stdout_limit",
    "stderr_limit",
    "combined_output_limit",
    "spawn_error",
    "io_error",
    "cancelled",
]
Cleanup = Literal["not_started", "completed", "incomplete"]


class ProcessValidationError(ValueError):
    """Rejected bounded invocation; no process launch attempted."""


def _require(condition: bool) -> None:
    if not condition:
        raise ProcessValidationError("invalid bounded process value")


def _integer(value: object, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _choice(value: object, options: set[str]) -> bool:
    return type(value) is str and value in options


def _text(value: object, maximum: int, *, empty: bool = True) -> str:
    _require(type(value) is str)
    text = cast(str, value)
    _require((empty or bool(text)) and len(text) <= maximum and "\0" not in text)
    try:
        size = len(text.encode("utf-8", errors="strict"))
    except UnicodeError as error:
        raise ProcessValidationError("invalid bounded process text") from error
    _require(size <= maximum)
    return text


def _argv(value: object) -> tuple[str, ...]:
    _require(type(value) is tuple)
    values = cast(tuple[object, ...], value)
    _require(1 <= len(values) <= 256)
    result = tuple(_text(item, 8192) for item in values)
    _require(result[0].startswith("/"))
    _require(sum(len(item.encode()) + 1 for item in result) <= 65536)
    return result


def _path(value: object) -> PosixPath:
    """Copy bounded primitive path storage, never caller caches or callbacks."""
    _require(type(value) is PosixPath)
    parsed = False
    try:
        parts = object.__getattribute__(value, "_raw_paths")  # CPython 3.12+ layout.
    except AttributeError:
        try:
            parts = object.__getattribute__(value, "_parts")  # CPython 3.11 layout.
        except AttributeError as error:
            raise ProcessValidationError("unsupported bounded process path") from error
        parsed = True
    _require(type(parts) is list and 1 <= len(parts) <= 4096)
    # Bound the built-in slice before copying even if an accidental writer grows
    # the caller's list. Unknown storage and custom containers fail closed.
    snapshot = tuple(parts[:4097])
    _require(1 <= len(snapshot) <= 4096)
    size = 0
    for member in snapshot:
        part = _text(member, 4096)
        size += len(part.encode("utf-8"))
        _require(size <= 4096)
    if parsed:
        try:
            drive = object.__getattribute__(value, "_drv")
            root = object.__getattribute__(value, "_root")
        except AttributeError as error:
            raise ProcessValidationError("unsupported bounded process path") from error
        _require(type(drive) is str and type(root) is str and drive == "" and root == "/")
        _require(snapshot[0] == "/")
        _require(all("/" not in part and part not in ("", ".", "..") for part in snapshot[1:]))
    # Formatting/properties below belong only to this fresh private instance.
    path = PosixPath(*snapshot)
    _text(str(path), 4096, empty=False)
    _require(path.anchor == "/" and len(path.parts) > 1 and ".." not in path.parts)
    return path


def _environment(value: object) -> dict[str, str]:
    _require(type(value) is dict)
    original = cast(dict[object, object], value)
    _require(len(original) <= 64)
    # Built-in dict.copy executes no caller Mapping/iteration callbacks.
    snapshot = original.copy()
    _require(len(snapshot) <= 64)
    result: dict[str, str] = {}
    size = 0
    for key, item in snapshot.items():
        name = _text(key, 128, empty=False)
        _require("=" not in name)
        content = _text(item, 8192)
        size += len(name.encode()) + len(content.encode()) + 2
        _require(size <= 65536)
        result[name] = content
    return result


@dataclass(frozen=True, repr=False)
class ProcessLimits:
    stdin_bytes: int
    stdout_bytes: int
    stderr_bytes: int
    combined_output_bytes: int
    wall_ms: int
    cleanup_reserve_ms: int

    def __post_init__(self) -> None:
        _require(type(self) is ProcessLimits)
        for value, maximum in (
            (self.stdin_bytes, 4 * _MIB),
            (self.stdout_bytes, 128 * _MIB),
            (self.stderr_bytes, _MIB),
            (self.combined_output_bytes, 129 * _MIB),
        ):
            _require(_integer(value, 0, maximum))
        _require(_integer(self.wall_ms, 1, 300000))
        _require(_integer(self.cleanup_reserve_ms, 1, min(5000, self.wall_ms - 1)))
        _require(self.combined_output_bytes <= self.stdout_bytes + self.stderr_bytes)


def _limits(value: ProcessLimits) -> ProcessLimits:
    _require(type(value) is ProcessLimits)
    attributes = vars(value)
    _require(type(attributes) is dict and len(attributes) == 6)
    fields = dict.copy(attributes)
    _require(len(fields) == 6 and all(type(key) is str for key in fields))
    _require(
        set(fields)
        == {
            "stdin_bytes",
            "stdout_bytes",
            "stderr_bytes",
            "combined_output_bytes",
            "wall_ms",
            "cleanup_reserve_ms",
        }
    )
    # Do not call an instance-supplied __post_init__ or retain caller-owned
    # dataclass fields. Exact scalar snapshots are validated by our constructor.
    return ProcessLimits(
        fields["stdin_bytes"],
        fields["stdout_bytes"],
        fields["stderr_bytes"],
        fields["combined_output_bytes"],
        fields["wall_ms"],
        fields["cleanup_reserve_ms"],
    )


@dataclass(frozen=True, repr=False)
class FrozenInvocation:
    argv: tuple[str, ...]
    environment: tuple[tuple[str, str], ...]
    cwd: str
    stdin_bytes: int
    stdin_sha256: bytes

    def __post_init__(self) -> None:
        _require(type(self) is FrozenInvocation)
        _argv(self.argv)
        _require(type(self.environment) is tuple and len(self.environment) <= 64)
        env: dict[str, str] = {}
        for pair in self.environment:
            _require(type(pair) is tuple and len(pair) == 2)
            key = _text(pair[0], 128, empty=False)
            _require(key not in env)
            env[key] = _text(pair[1], 8192)
        _environment(env)
        _require(self.environment == tuple(sorted(env.items())))
        _path(PosixPath(_text(self.cwd, 4096, empty=False)))
        _require(_integer(self.stdin_bytes, 0, 4 * _MIB))
        _require(type(self.stdin_sha256) is bytes and len(self.stdin_sha256) == 32)


@dataclass(frozen=True, repr=False)
class StreamEvidence:
    observed_bytes: int
    retained_bytes: int | None
    retained_sha256: bytes | None
    eof: bool
    truncated: bool

    def __post_init__(self) -> None:
        _require(type(self) is StreamEvidence)
        _require(_integer(self.observed_bytes, 0, 129 * _MIB + _CHUNK))
        _require(type(self.eof) is bool and type(self.truncated) is bool)
        if self.retained_bytes is None:
            _require(self.retained_sha256 is None)
        else:
            _require(_integer(self.retained_bytes, 0, self.observed_bytes))
            _require(type(self.retained_sha256) is bytes and len(self.retained_sha256) == 32)
            _require(self.retained_bytes == self.observed_bytes or self.truncated)


@dataclass(frozen=True, repr=False)
class MemoryOutput:
    evidence: StreamEvidence
    data: bytes

    def __post_init__(self) -> None:
        _require(type(self) is MemoryOutput and type(self.evidence) is StreamEvidence)
        _require(type(self.data) is bytes and len(self.data) <= 16 * _MIB)
        _require(self.evidence.retained_bytes == len(self.data))
        _require(self.evidence.retained_sha256 == hashlib.sha256(self.data).digest())


@dataclass(frozen=True, repr=False)
class SpoolOutput:
    evidence: StreamEvidence
    path: Path

    def __post_init__(self) -> None:
        _require(type(self) is SpoolOutput and type(self.evidence) is StreamEvidence)
        object.__setattr__(self, "path", _path(self.path))


Output = MemoryOutput | SpoolOutput


@dataclass(frozen=True, repr=False)
class ProcessOutcome:
    invocation: FrozenInvocation
    reason: Reason
    pid: int | None
    pgid: int | None
    returncode: int | None
    stdin_sent_bytes: int
    stdout: Output | None
    stderr: Output | None
    elapsed_ms: int
    cleanup: Cleanup

    def __post_init__(self) -> None:
        _require(type(self) is ProcessOutcome and type(self.invocation) is FrozenInvocation)
        _require(
            _choice(
                self.reason,
                {
                    "exited",
                    "timeout",
                    "stdin_closed",
                    "stdout_limit",
                    "stderr_limit",
                    "combined_output_limit",
                    "spawn_error",
                    "io_error",
                    "cancelled",
                },
            )
        )
        _require(
            _choice(
                self.cleanup,
                {
                    "not_started",
                    "completed",
                    "incomplete",
                },
            )
        )
        if self.pid is None:
            _require(
                self.pgid is None and self.returncode is None and self.cleanup == "not_started"
            )
        else:
            _require(_integer(self.pid, 1, 2**31 - 1) and type(self.pgid) is int)
            _require(self.pgid == self.pid and self.cleanup != "not_started")
        if self.returncode is not None:
            _require(_integer(self.returncode, -(2**31), 2**31 - 1))
        _require(_integer(self.stdin_sent_bytes, 0, self.invocation.stdin_bytes))
        _require(type(self.elapsed_ms) is int and self.elapsed_ms >= 0)
        for output in (self.stdout, self.stderr):
            _require(output is None or type(output) in (MemoryOutput, SpoolOutput))
        if self.cleanup == "completed":
            _require(self.returncode is not None)
            for output in (self.stdout, self.stderr):
                _require(output is not None and output.evidence.retained_bytes is not None)
            if self.reason == "exited":
                _require(self.stdin_sent_bytes == self.invocation.stdin_bytes)
                for output in (self.stdout, self.stderr):
                    assert output is not None
                    _require(output.evidence.eof and not output.evidence.truncated)


class ProcessTransportError(RuntimeError):
    """Private partial outcome; public consumers should log a fixed status only."""

    def __init__(self, outcome: ProcessOutcome) -> None:
        _require(type(outcome) is ProcessOutcome)
        super().__init__("bounded process transport failed")
        self.outcome = outcome
        # Preserve an unreaped owned Popen handle until the outer supervisor
        # disposes this failed controller. Never pretend its return code is known.
        self._owned_child: subprocess.Popen[bytes] | None = None


class _DeadlineExpiredError(TimeoutError):
    pass


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise _DeadlineExpiredError("bounded process deadline expired")
    return remaining


def _open_directory(path: Path, deadline: float) -> int:
    _remaining(deadline)
    fd = os.open("/", _DIRECTORY_FLAGS)
    try:
        for name in path.parts[1:]:
            _remaining(deadline)
            child = os.open(name, _DIRECTORY_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700
        ):
            raise OSError("unsafe bounded process directory")
        return fd
    except BaseException:
        os.close(fd)
        raise


class _Hash(Protocol):
    def update(self, data: bytes | memoryview) -> None: ...
    def digest(self) -> bytes: ...


@dataclass(repr=False)
class _Sink:
    path: Path | None = None
    fd: int | None = None
    data: bytearray = field(default_factory=bytearray)
    observed: int = 0
    written: int = 0
    eof: bool = False
    hasher: _Hash = field(default_factory=hashlib.sha256)
    verified: tuple[int, bytes] | None = None

    def retain(self, payload: bytes, deadline: float) -> None:
        if self.path is None:
            self.data.extend(payload)
            self.written += len(payload)
            return
        assert self.fd is not None
        view = memoryview(payload)
        while view:
            _remaining(deadline)
            count = os.write(self.fd, view)
            if count <= 0:
                raise OSError("bounded spool write made no progress")
            self.hasher.update(view[:count])
            self.written += count
            view = view[count:]

    def verify(self, deadline: float) -> None:
        if self.path is None:
            return
        assert self.fd is not None
        _remaining(deadline)
        info = os.fstat(self.fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size != self.written
        ):
            raise OSError("invalid bounded spool storage")
        os.fsync(self.fd)
        os.lseek(self.fd, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        count = 0
        while True:
            _remaining(deadline)
            chunk = os.read(self.fd, min(_CHUNK, self.written - count + 1))
            if not chunk:
                break
            count += len(chunk)
            if count > self.written:
                raise OSError("bounded spool grew during readback")
            digest.update(chunk)
        after = os.fstat(self.fd)
        if (
            count != self.written
            or digest.digest() != self.hasher.digest()
            or (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        ):
            raise OSError("bounded spool readback differs")
        self.verified = count, digest.digest()

    def snapshot(self) -> Output:
        if self.path is None:
            data = bytes(self.data)
            evidence = StreamEvidence(
                self.observed,
                len(data),
                hashlib.sha256(data).digest(),
                self.eof,
                len(data) < self.observed,
            )
            return MemoryOutput(evidence, data)
        count, digest = self.verified if self.verified is not None else (None, None)
        evidence = StreamEvidence(
            self.observed, count, digest, self.eof, self.written < self.observed
        )
        return SpoolOutput(evidence, self.path)


@dataclass(repr=False)
class _Run:
    invocation: FrozenInvocation
    env: dict[str, str]
    cwd: Path
    limits: ProcessLimits
    payload: bytes
    spool: Path | None
    started: float
    deadline: float
    productive: float
    child: subprocess.Popen[bytes] | None = None
    outputs: list[_Sink] = field(default_factory=list)
    directory_fds: list[int] = field(default_factory=list)
    sent: int = 0
    spawn_attempted: bool = False
    reason: Reason = "exited"

    def prepare_storage(self) -> None:
        cwd_fd = _open_directory(self.cwd, self.productive)
        self.directory_fds.append(cwd_fd)
        if self.spool is None:
            self.outputs = [_Sink(), _Sink()]
            return
        spool_fd = _open_directory(self.spool, self.productive)
        self.directory_fds.append(spool_fd)
        cwd_info, spool_info = os.fstat(cwd_fd), os.fstat(spool_fd)
        if (cwd_info.st_dev, cwd_info.st_ino) == (spool_info.st_dev, spool_info.st_ino):
            raise OSError("bounded spool and cwd must differ")
        with os.scandir(spool_fd) as entries:
            if next(entries, None) is not None:
                raise OSError("bounded spool must be empty")
        for name in ("stdout.bin", "stderr.bin"):
            _remaining(self.productive)
            fd = os.open(name, _SPOOL_FLAGS, 0o600, dir_fd=spool_fd)
            self.outputs.append(_Sink(path=self.spool / name, fd=fd))
            # Restrictive inherited umasks are normalized only on these new files.
            os.fchmod(fd, 0o600)

    def launch(self) -> None:
        _remaining(self.productive)
        self.spawn_attempted = True
        self.child = subprocess.Popen(
            self.invocation.argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            close_fds=True,
            start_new_session=True,
            cwd=self.cwd,
            env=self.env,
        )

    def _exited(self) -> bool:
        assert self.child is not None
        result = os.waitid(os.P_PID, self.child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        return result is not None and result.si_pid == self.child.pid

    def pump(self) -> Reason:
        assert self.child is not None
        assert (
            self.child.stdin is not None
            and self.child.stdout is not None
            and self.child.stderr is not None
        )
        pipes = (self.child.stdout, self.child.stderr, self.child.stdin)
        caps = (self.limits.stdout_bytes, self.limits.stderr_bytes)
        with selectors.DefaultSelector() as selector:
            for index, pipe in enumerate(pipes):
                os.set_blocking(pipe.fileno(), False)
                if index == 2 and not self.payload:
                    pipe.close()
                else:
                    selector.register(
                        pipe, selectors.EVENT_WRITE if index == 2 else selectors.EVENT_READ, index
                    )
            while True:
                _remaining(self.productive)
                if self._exited() and all(sink.eof for sink in self.outputs):
                    return "exited" if self.sent == len(self.payload) else "stdin_closed"
                events = selector.select(min(0.05, _remaining(self.productive)))
                # Drain ready output before input writes so immediate error text
                # can be retained before discovering an early stdin close.
                for key, _mask in sorted(events, key=lambda event: cast(int, event[0].data)):
                    _remaining(self.productive)
                    index = cast(int, key.data)
                    pipe = pipes[index]
                    if index == 2:
                        try:
                            sent = os.write(key.fd, self.payload[self.sent : self.sent + _CHUNK])
                        except BlockingIOError:
                            continue
                        except BrokenPipeError:
                            return "stdin_closed"
                        if sent <= 0:
                            raise OSError("bounded stdin write made no progress")
                        self.sent += sent
                        if self.sent == len(self.payload):
                            selector.unregister(pipe)
                            pipe.close()
                        continue
                    try:
                        chunk = os.read(key.fd, _CHUNK)
                    except BlockingIOError:
                        continue
                    sink = self.outputs[index]
                    if not chunk:
                        sink.eof = True
                        selector.unregister(pipe)
                        pipe.close()
                        continue
                    sink.observed += len(chunk)
                    available = min(
                        caps[index] - sink.written,
                        self.limits.combined_output_bytes
                        - sum(item.written for item in self.outputs),
                    )
                    sink.retain(chunk[: max(0, available)], self.productive)
                    if sink.observed > caps[index]:
                        return "stdout_limit" if index == 0 else "stderr_limit"
                    if (
                        sum(item.observed for item in self.outputs)
                        > self.limits.combined_output_bytes
                    ):
                        return "combined_output_limit"

    def _kill_owned_group(self) -> None:
        assert self.child is not None
        # Confirm the child is still ours/unreaped before any numeric PGID use.
        # Exclusive wait ownership is a required controller assumption.
        self._exited()
        try:
            os.killpg(self.child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def _reap(self) -> None:
        assert self.child is not None
        while True:
            pid, status = os.waitpid(self.child.pid, os.WNOHANG)
            if pid == self.child.pid:
                self.child.returncode = os.waitstatus_to_exitcode(status)
                return
            time.sleep(min(0.005, _remaining(self.deadline)))

    def finish(self) -> list[BaseException]:
        errors: list[BaseException] = []
        if self.child is not None:
            try:
                self._kill_owned_group()
            except BaseException as error:
                errors.append(error)
            for pipe in (self.child.stdin, self.child.stdout, self.child.stderr):
                if pipe is not None:
                    try:
                        pipe.close()
                    except BaseException as error:
                        errors.append(error)
            try:
                self._reap()
            except BaseException as error:
                errors.append(error)
        for sink in self.outputs:
            try:
                sink.verify(self.deadline)
            except BaseException as error:
                errors.append(error)
            finally:
                if sink.fd is not None:
                    try:
                        os.close(sink.fd)
                    except BaseException as error:
                        errors.append(error)
        if self.spool is not None and len(self.directory_fds) == 2:
            try:
                _remaining(self.deadline)
                os.fsync(self.directory_fds[1])
            except BaseException as error:
                errors.append(error)
        for fd in reversed(self.directory_fds):
            try:
                os.close(fd)
            except BaseException as error:
                errors.append(error)
        if time.monotonic() > self.deadline:
            errors.append(_DeadlineExpiredError("bounded cleanup deadline expired"))
        return errors

    def outcome(self, outputs: list[Output | None], *, failed_cleanup: bool) -> ProcessOutcome:
        return _make_outcome(self, outputs, failed_cleanup=failed_cleanup)


def _make_outcome(
    run: _Run, outputs: list[Output | None], *, failed_cleanup: bool
) -> ProcessOutcome:
    child = run.child
    cleanup: Cleanup = (
        "not_started" if child is None else ("incomplete" if failed_cleanup else "completed")
    )
    return ProcessOutcome(
        run.invocation,
        run.reason,
        child.pid if child else None,
        child.pid if child else None,
        child.returncode if child else None,
        run.sent,
        outputs[0],
        outputs[1],
        max(0, int((time.monotonic() - run.started) * 1000)),
        cleanup,
    )


def _cause(errors: list[BaseException]) -> BaseException:
    return errors[0] if len(errors) == 1 else BaseExceptionGroup("bounded process failures", errors)


def run_bounded_process(
    argv: tuple[str, ...],
    *,
    stdin: bytes | None,
    env: dict[str, str],
    cwd: Path,
    limits: ProcessLimits,
    spool_dir: Path | None = None,
) -> ProcessOutcome:
    """Run a domain-approved invocation; preserve bounded outcomes, not success claims."""
    values = _argv(argv)
    environment = _environment(env)
    directory = _path(cwd)
    spool = None if spool_dir is None else _path(spool_dir)
    limits = _limits(limits)
    _require(stdin is None or type(stdin) is bytes)
    payload = b"" if stdin is None else stdin
    _require(len(payload) <= limits.stdin_bytes)
    if spool is None:
        _require(limits.stdout_bytes <= 16 * _MIB and limits.combined_output_bytes <= 17 * _MIB)
    else:
        _require(spool != directory)
    _require(
        sys.platform == "linux"
        and all(
            hasattr(os, name)
            for name in (
                "waitid",
                "WNOWAIT",
                "WEXITED",
                "WNOHANG",
                "killpg",
            )
        )
    )
    invocation = FrozenInvocation(
        values,
        tuple(sorted(environment.items())),
        str(directory),
        len(payload),
        hashlib.sha256(payload).digest(),
    )
    started = time.monotonic()
    deadline = started + limits.wall_ms / 1000
    run = _Run(
        invocation,
        environment,
        directory,
        limits,
        payload,
        spool,
        started,
        deadline,
        deadline - limits.cleanup_reserve_ms / 1000,
    )
    errors: list[BaseException] = []
    interruption: BaseException | None = None
    try:
        run.prepare_storage()
        run.launch()
        run.reason = run.pump()
    except _DeadlineExpiredError:
        run.reason = "timeout"
    except BaseException as error:
        if not isinstance(error, Exception):
            interruption = error
            run.reason = "cancelled"
        else:
            run.reason = "spawn_error" if run.spawn_attempted and run.child is None else "io_error"
            errors.append(error)
    finalization_errors = run.finish()
    outputs: list[Output | None] = [None, None]
    # Final byte copies/hashes/record validation are evidence work too. Keep
    # the other stream when one fails; never retry or invent its missing hash.
    for index, sink in enumerate(run.outputs):
        try:
            outputs[index] = sink.snapshot()
        except BaseException as finalization_error:
            finalization_errors.append(finalization_error)
    for recorded_error in finalization_errors:
        if interruption is None and not isinstance(recorded_error, Exception):
            interruption = recorded_error
            run.reason = "cancelled"
        elif recorded_error is not interruption:
            errors.append(recorded_error)
    try:
        outcome = run.outcome(outputs, failed_cleanup=bool(finalization_errors))
    except BaseException as outcome_error:
        if interruption is None and not isinstance(outcome_error, Exception):
            interruption = outcome_error
            run.reason = "cancelled"
        elif outcome_error is not interruption:
            errors.append(outcome_error)
        # Small class-owned fallback retains already validated stream evidence.
        # Unrecoverable allocation failure still requires the outer supervisor.
        outcome = _make_outcome(run, outputs, failed_cleanup=True)
    if time.monotonic() > run.deadline:
        errors.append(_DeadlineExpiredError("bounded evidence finalization deadline expired"))
        outcome = _make_outcome(run, outputs, failed_cleanup=True)
    if errors or interruption is not None:
        evidence_error = ProcessTransportError(outcome)
        if run.child is not None and run.child.returncode is None:
            evidence_error._owned_child = run.child
        if interruption is not None:
            if interruption.__cause__ is not None:
                errors.insert(0, interruption.__cause__)
            if errors:
                evidence_error.__cause__ = _cause(errors)
            raise interruption from evidence_error
        raise evidence_error from _cause(errors)
    return outcome
