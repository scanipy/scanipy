# Shared bounded process transport — version 1 design

Status: root-approved shared transport, implemented and independently reviewed
locally under [#398](https://github.com/scanipy/scanipy/issues/398). Native source
commands, container launches and production acceptance are not authorized by
this document. Root authorized only this shared three-file implementation slice
and its small trusted test children, after the recorded review clarifications.
Owner: corpus/tooling agent. Consumers: source-bound Python syntax,
accepted-input verifier and Git acquisition. No consumer implements a competing
transport. Authority:
[DECISION-BHMEA-01](../DECISION-BHMEA-01-current-execution-authority-2026-09-25.md).

## 1. Deliverable, ownership and non-goals

Implement only `tools/worker/bounded_process.py` and
`tests/unit/test_bounded_process.py` for this shared dependency, after approval
of this entire contract. Its purpose is concurrent bounded one-shot stdin,
stdout and stderr with explicit exit, partial-output and cleanup evidence.
It is NOT an executable allowlist, sandbox, source classifier, environment
attestation service, credential channel or authorization decision.

The domain adapter must first validate its exact tool, argv, environment,
trusted code/import closure, input protocol and actual runtime policy. The
generic transport never accepts target-selected callbacks, iterators, factories,
interactive protocols, shell command strings, `preexec_fn` or arbitrary Popen
options. It does not alter `secure_run`, its Git refusal, Java safety profiles
or any existing native tool route. This is a Linux/Python 3.11+ contract; an
unsupported platform fails before launching instead of falling back.

Only trusted test children may run during the implementation's hermetic tests.
Their bytes/scripts are authored in Scanipy tests, never scanned source.
Native Git/Joern/Semgrep and real production parser/verifier runs require their
own later reviewed controller and explicit execution approval.

## 2. Public API and exact value types

All records below are frozen dataclasses. Constructors and the public function
revalidate exact runtime types; a frozen record containing mutable/custom values
does not qualify. Public values and raw buffers have non-content-bearing reprs.
Wrapper exception messages/reprs do not embed argv, environment, stdout, stderr
or stdin. Preserved original exception causes may themselves contain private
paths/data; keep chains private and emit only fixed status codes publicly,
never unrestricted tracebacks.

```python
@dataclass(frozen=True)
class ProcessLimits:
    stdin_bytes: int
    stdout_bytes: int
    stderr_bytes: int
    combined_output_bytes: int
    wall_ms: int
    cleanup_reserve_ms: int

@dataclass(frozen=True)
class FrozenInvocation:
    argv: tuple[str, ...]
    environment: tuple[tuple[str, str], ...]  # sorted by exact key
    cwd: str
    stdin_bytes: int
    stdin_sha256: bytes                     # exactly 32 bytes

@dataclass(frozen=True)
class StreamEvidence:
    observed_bytes: int
    retained_bytes: int | None
    retained_sha256: bytes | None           # 32 bytes, or unknown
    eof: bool
    truncated: bool

@dataclass(frozen=True)
class MemoryOutput:
    evidence: StreamEvidence
    data: bytes

@dataclass(frozen=True)
class SpoolOutput:
    evidence: StreamEvidence
    path: Path

@dataclass(frozen=True)
class ProcessOutcome:
    invocation: FrozenInvocation
    reason: Literal[
        "exited", "timeout", "stdin_closed", "stdout_limit", "stderr_limit",
        "combined_output_limit", "spawn_error", "io_error", "cancelled",
    ]
    pid: int | None
    pgid: int | None
    returncode: int | None
    stdin_sent_bytes: int
    stdout: MemoryOutput | SpoolOutput | None
    stderr: MemoryOutput | SpoolOutput | None
    elapsed_ms: int
    cleanup: Literal["not_started", "completed", "incomplete"]

class ProcessValidationError(ValueError):
    """Rejected bounded invocation; no subprocess was attempted."""

class ProcessTransportError(RuntimeError):
    outcome: ProcessOutcome

def run_bounded_process(
    argv: tuple[str, ...],
    *,
    stdin: bytes | None,
    env: dict[str, str],
    cwd: Path,
    limits: ProcessLimits,
    spool_dir: Path | None = None,
) -> ProcessOutcome: ...
```

`env` means an EXACT built-in dict, not the general Mapping interface. `argv`
means an exact tuple of exact strings. `stdin` is exact immutable bytes or None;
None and empty bytes both send zero bytes and close stdin. Strings contain no
NUL or invalid Unicode scalar sequence. Paths are exact concrete `PosixPath`
instances, not custom `PathLike` objects. Limits require exact int, never bool.
Reject subclasses/custom containers before iteration, encoding, hashing or
filesystem work. No unbounded poison iterable may be consumed for validation.
Environment keys must be nonempty and contain no equals sign.

Exact PosixPath type alone is insufficient: its internal component storage and
cached strings can still be illicitly mutated. Before invoking any path
property, formatting method or filesystem operation, read only its class-owned
raw storage: the inspected CPython 3.11 `_parts` or 3.12 `_raw_paths` layout.
Require an exact built-in list with 1..4096 members; take a bounded built-in
slice of at most 4097 before copying, recheck count, then require exact strings
and bounded individual/aggregate UTF-8 bytes. On the parsed 3.11 layout, also
check exact primitive drive/root and component constraints. Unknown layouts
fail closed. Never read caller `_str`/`_pparts` caches as authority or invoke a
caller iterator/slicer/formatter. Construct a fresh private PosixPath, apply the
same normalized-absolute/no-parent/root/4-KiB checks, and use ONLY that copy for
directory walks, Popen, spool creation and frozen evidence. SpoolOutput stores
its own fresh path copy, not a caller alias. This does not broaden any domain's
path allowlist or protect against a privileged concurrent filesystem writer.

Validate container count first, then bounded string lengths/types, then encoded
lengths. Copy the exact dict to a private built-in dict, validate that snapshot,
and use ONLY that snapshot for Popen and frozen evidence. Freeze argv and input
bytes similarly; concurrent mutation of the caller's dict cannot change the
executed or recorded environment. A concurrent mutation observed while copying
is a validation failure. There is no callback between validation and spawn.

The returned records never confer authorization. A consumer must not accept a
caller-constructed ProcessOutcome in place of observing its own transport call.
Tests may patch the trusted transport seam; that is not production attestation.

## 3. Generic hard ceilings and domain profiles

These are implementation ceilings, not stage performance promises. Domain
profiles set explicit LOWER caps; request/source data cannot raise them. Zero
is allowed for byte caps and means any corresponding byte is excessive.

| Quantity | Generic version-1 maximum |
| --- | ---: |
| Argv entries, including absolute executable | 256 |
| One argv entry / all encoded argv, including separators | 8 KiB / 64 KiB |
| Environment entries | 64 |
| Environment key / value / all encoded pairs | 128 bytes / 8 KiB / 64 KiB |
| One cwd/spool absolute path | 4 KiB UTF-8 |
| Immutable stdin | 4 MiB |
| Memory stdout / stderr / combined output | 16 MiB / 1 MiB / 17 MiB |
| Spool stdout / stderr / combined output | 128 MiB / 1 MiB / 129 MiB |
| Total wall interval | 300,000 ms |
| Cleanup reservation, contained within wall interval | 5,000 ms |
| Individual read/write chunk | 64 KiB |

Require `1 <= wall_ms <= 300000` and
`1 <= cleanup_reserve_ms < wall_ms`, with reservation at most 5,000 ms.
Combined cap cannot exceed the sum of per-stream caps. Individual caps need not
sum to the combined cap; a smaller combined limit is independently enforced.
The memory/spool mode selects the applicable generic maximum before allocation.

| Domain | Stdin | Stdout / stderr / combined | Wall / cleanup reservation |
| --- | ---: | --- | --- |
| Python syntax, per file | Domain frame, at most 270,336 bytes | 8 MiB / 64 KiB / 8 MiB + 64 KiB | 5,000 / 500 ms |
| Accepted-input verification | 2,621,440 bytes | 16,384 / 16,384 / 32,768 bytes | 3,000 / 500 ms |
| Git object batch, proposed | At most 4 MiB of exact OID lines | Spool: 128 MiB / 1 MiB / 129 MiB | At most 60,000 / 2,000 ms |
| Semgrep observation, future only | Domain-defined, within 4 MiB | 16 MiB / 1 MiB / 17 MiB | Separate reviewed profile required |

Python's parent additionally enforces its cumulative 8 MiB syntax-output ceiling
across files. The verifier child separately sets AS 128 MiB and CPU 2 seconds;
the syntax child separately sets its own documented rlimits before input.
Transport does not set them using unsafe preexec callbacks or invent proof that
they were applied. Git requires an outer memory/PID/storage/network envelope.
Semgrep framing/progress-line handling is a domain problem; transport is bytes
only and does not search for JSON or accept a valid-looking prefix.

## 4. Trusted paths, isolated spawn and output modes

The executable is an absolute path selected/verified by the domain. Generic
absolute-path syntax is not binary identity verification. Domain code must bind
the actual resolved executable, helpers/imports, mounted source code and runtime
image separately. The transport never resolves a bare command through PATH.

Require an existing absolute normalized owned mode-0700 cwd. Walk all directory
components without following symlinks using directory descriptors; reject `..`,
root-as-workdir, wrong ownership and unsafe leaf mode. The launcher provides an
exclusive trusted parent/mount. Cwd/spool path substitution by same-UID or mount
administrators is outside this process-local guarantee and MUST be prevented by
the controller. A check followed by pathname-based Popen cwd is not an atomic
hostile-concurrent-filesystem sandbox.

Popen has exactly `shell=False`, binary pipes for all three streams,
`close_fds=True`, `start_new_session=True`, the explicit cwd/environment and
frozen argv. No inherited additional descriptors, terminal, shell, fd passthrough
or inherited environment. Require Linux `waitid`/WNOWAIT/process-group support
before spawn. Do not use `preexec_fn`, `communicate()` or an unbounded wait/read.

Memory mode retains bounded bytes directly. Spool mode requires an existing
empty owned mode-0700 spool directory, distinct from cwd and without symlinked
components. Bounded descriptor-based enumeration rejects any existing entry.
Create exactly `stdout.bin` and `stderr.bin` with O_CREAT|O_EXCL|O_NOFOLLOW,
close-on-exec, mode 0600, and retained directory descriptors. Existing output
is never overwritten, appended, repaired, reused or removed. Partial files
remain available for diagnostics; transport has no cleanup/delete API.

Account for partial writes. Before reporting spool retention, fsync each file,
independently re-read its bounded actual bytes and compare count/hash with the
acknowledged writes, then fsync the containing directory. Check regular type,
owner, one link, exact mode and descriptor identity. Hashing only bytes offered
to write does not establish retained evidence. This I/O is within the wall
budget subject to the blocking-kernel/outer-supervisor caveat below.

`retained_bytes` and `retained_sha256` are both null when actual retained spool
content cannot be established after a storage/readback error. A path can still
be returned as a diagnostic location, never as verified bytes. Memory outputs
always bind their actual data. This nullable pair is a deliberate refinement of
the provisional API: required-evidence failure must not fabricate a digest.
If a whole stream's final byte-copy/hash/record construction fails, that output
record is absent instead; independently completed evidence for the other stream
is retained. The operation raises a fatal evidence error with incomplete cleanup,
not a result accepting the successfully materialized prefix/other stream.

## 5. Concurrent pump, EOF and overflow rules

After bounded PURE argument/type/length checks and before the FIRST filesystem
validation/allocation, start one monotonic absolute wall deadline. The productive
interval ends at wall deadline minus cleanup reservation. Path validation,
allocation/spawn and retention/readback consume that same interval.
Final buffer snapshots, hashes and outcome-record construction are included;
check the absolute deadline again AFTER constructing the final evidence before
admitting a returned completed outcome.

Set all pipe descriptors nonblocking. A selector loop fairly services writable
stdin and readable stdout/stderr with at most one bounded chunk per ready stream
per iteration; recheck time and counters before each operation. Partial stdin
writes advance only by acknowledged bytes. Close stdin immediately when all
input is sent. A broken stdin pipe before all bytes were sent is `stdin_closed`,
not success; still retain output and return code if available.

Each output read is charged before retention to the stream and combined totals.
Never allocate based on an output-announced length. On overflow retain at most
the applicable remaining prefix capacity, set truncated and abort the process
group. At most one additional chunk may be observed before detecting overflow;
`observed_bytes` records what was actually read, not what the child might have
written. Stop reading on abort after the bounded final observation; do not turn
drain/cleanup into another unbounded stream. A per-stream violation is identified
before combined violation for the same chunk; otherwise preserve the first
observed failure. Scheduling-dependent failure order is diagnostic, not a
cross-run determinism claim.

`eof=True` requires an actual zero-byte pipe read. Closing a pipe during abort
does not establish EOF. `truncated=True` means observed bytes were not retained;
even `truncated=False` with EOF false is incomplete. A retained prefix hash is
never the whole child-output hash unless EOF and all observed bytes are retained.

Do not report normal completion just because the leader exited. A child can
leave inherited pipes open in descendants. Productive completion requires all
stdin sent/closed, EOF on both outputs and observed leader exit before deadline.
The exact nonzero return code is a normal `reason="exited"` transport outcome,
not a Python CalledProcessError containing raw output. The domain must reject it
unless its separately reviewed protocol explicitly handles that nonzero status.

## 6. Deadline, process groups and honest cleanup

Observe leader exit with Linux waitid(WEXITED|WNOHANG|WNOWAIT), retaining it
unreaped until the final process-group signal. Never call Popen.poll/wait early
and later signal a numeric PGID that could have been reused after leader reap.
The private session has PID=PGID. Before reaping, send SIGKILL to its group on
abort and also at final normal cleanup, to contain same-group descendants that
closed their pipes. ESRCH is an acceptable absent-group observation. Never send
signals to an arbitrary supplied PID/group or to the controller's group.

Within the remaining reserved interval: close pipes, finish bounded evidence
retention and reap only the owned direct child. No unbounded blocking wait.
Returncode remains null if the child was not reaped with a known status.

- `not_started`: no Popen child was successfully acknowledged/owned. This is not
  proof that an unsuccessful OS launch performed no transient fork.
- `completed`: owned leader reaped, pipes closed, required final group signal
  delivered or group observed absent, and output retention completed. This is
  process-local cleanup, NOT proof that every descendant is dead/reaped.
- `incomplete`: any required local cleanup/evidence step failed or did not finish
  by the absolute deadline. Preserve live PID/PGID and partial evidence for the
  trusted outer supervisor; never retry automatically or start another child.

SIGKILL delivery is not proof of descendant termination; a child can escape its
group, and a blocked kernel operation/process creation can exceed user-space
deadlines. No Python implementation can promise a hard real-time upper bound
or kill an uninterruptible D-state task. An independently enforced cgroup,
resource-limited container, no-egress mounts/network and external wall-time
supervisor are REQUIRED for production adversarial/native use. This module
neither launches that controller nor trusts a caller boolean saying it exists.
Without it, controlled transport tests prove only the local mechanism.

## 7. Failure propagation and consumer acceptance

Validation errors use constant ProcessValidationError messages before spawn.
After a valid frozen invocation exists, file-allocation/spawn/I/O/readback/cleanup
errors raise ProcessTransportError with its best actual partial outcome and
original failure as `__cause__`. Preserve both independent failures in an
explicit exception group when necessary; never discard a child failure merely
because evidence recording also failed. Exception chains must not contain cycles.

Ordinary child nonzero exit, timeout, premature stdin close and output overflow
return typed failed outcomes only when local cleanup/evidence succeeded.
Cleanup-incomplete ALWAYS raises ProcessTransportError. No path converts a
storage error into an ordinary analyzable child failure or continues a campaign
after losing its required process evidence.

For KeyboardInterrupt/SystemExit (or another BaseException interruption), finish
the same bounded cleanup, retain reason `cancelled`, and re-raise the EXACT
original exception object as primary. Its explicit cause is a
ProcessTransportError carrying the partial outcome; retain any prior cause and
cleanup failure beneath that evidence error, using BaseExceptionGroup only if
needed. Do not turn cancellation into a normal returned outcome or silently
swallow SystemExit. Tests must verify original exception identity and cause
preservation as well as child cleanup.

There is deliberately no `success` boolean. A domain may consider transport
complete only for `reason="exited"`, allowed returncode, completed cleanup,
all stdin sent, both EOF, no truncation and exact verified retained bytes.
It must THEN validate the complete domain protocol, lengths/digests, expected
input identity and resource/profile evidence. Zero exit cannot turn malformed,
empty, trailing, partial or incompatible output into valid syntax, signature
authority, source acquisition or analysis coverage.

Enforce outcome cross-field invariants: retention count/hash are null together,
otherwise the digest is exactly 32 bytes and `0 <= retained <= observed`.
Memory count/hash equal the actual bytes. PID and PGID are paired, positive and
equal for an owned private session; a not-started outcome has neither. A known
return code requires reaping the owned child. Sent input never exceeds frozen
input size. A returned normal completed outcome has both verified output
records; no truncated/EOF combination can imply successful full output unless
the remaining explicit completeness predicates also hold.

Root and both consumer owners read the complete contract on 2026-09-25.
Root approved this exact three-file implementation slice after the privacy,
deadline, environment-key, transient-spawn and outcome-invariant clarifications
above. This is design approval, not implementation or runtime acceptance.

## 8. Required tests and implementation sequence

All new tests are unit-marked and selected by normal CI/pre-push. Use only small
trusted Python children, private tmp directories and bounded test supervisors.
Never use the generic mechanism to execute a fixture's source as a test.

- [ ] Exact types/count/string/cap/path checks before Popen; poison tuple/dict/
  path subclasses and invalid UTF-8/NUL/bool values never invoke callbacks.
  Exact but internally poisoned paths also reject before callbacks/I/O; stale
  caches are ignored, actual launch/spool/evidence use private copies, and
  later caller component mutation cannot redirect the operation/result path.
- [ ] Caller env mutation cannot change actual child env or frozen evidence.
  Exact env/argv/cwd/input digest observed by a trusted echo child; repr privacy.
- [ ] Concurrent large stdin/stdout/stderr cannot deadlock; partial writes,
  early stdin close, empty input, binary NUL bytes and each EOF handled exactly.
- [ ] Each exact cap passes; cap+1 and combined overflow abort with bounded
  prefixes, honest EOF/truncation and original raw bytes. No valid-prefix pass.
- [ ] Memory and spool paths, short writes, corrupt writes, readback/stat/fsync
  failures, existing files/symlinks/hardlinks/wrong mode and no deletion/reuse.
- [ ] Spawn failure, nonzero exit, timeout, inherited descendant pipes and
  same-group child termination. Assert owned leader reaped and no extra launch.
- [ ] Unknown/reap-incomplete and injected cleanup failure retain IDs/outcome;
  never claim all descendants reaped. Test no PGID signal after leader reap.
- [ ] Child plus evidence plus cleanup failure retains every cause; exact
  KeyboardInterrupt/SystemExit survives with partial evidence and bounded cleanup.
- [ ] Consumer forwarding tests use this real wrapper where trust matters;
  patched recording outcomes are explicitly controlled tests, not runtime proof.
- [ ] Ruff, strict mypy, full configured tests, normal hooks, independent review,
  exact-head CI and canonical APPROVE before merging the shared dependency.

Open integration actions: implement the separately reviewed outer controller;
bind real runtime/tool/code/helper identities; enforce cumulative domain limits;
add exact protocol consumers; measure stage resources. No full R16/R05/G0/G1/G2
or submitted claim is satisfied by this contract or by controlled pump tests.

## 9. Local implementation and verification checkpoint

The three-file implementation has local scoped approval from root and both
consumer owners. Independent reviews required two substantive corrections:
class-owned immutable limit snapshots instead of caller instance-method dispatch,
and failure-safe final stream/outcome construction with a post-finalization
deadline check. Added method/data/attribute-dictionary poison and mutation
falsifiers, surviving-stream/unknown-evidence controls and snapshot/outcome
ordinary-error/interruption/deadline cases. Original interruptions and earlier
causes remain private, retained evidence; no source/native enablement was added.

The initial 80 then expanded 91 focused cases passed. Initial strict mypy found
Literal exact-type narrowing and an exception-variable reuse issue; class-owned
object predicates and distinct variable names corrected these without weakening
runtime checks. The first full pre-review-fix run passed 1,558/51 existing skips;
the post-fix 102-case full run passed 1,569/51. These are historical checkpoints,
not claims that the earlier gaps were acceptable.

The final 102 focused tests passed in 5.095 seconds, no failures/errors/skips.
All 102 are selected by actual CI/pre-push markers. Independent 102-case runs
passed in 5.266 seconds (canonical agent) and 5.066 seconds (root); the schema
agent separately reviewed the entire module and final corrections without
running overlapping native/domain work. One metadata-only follow-up replaced
17 automatic parameter IDs with short fixed labels: the deliberate 4 MiB input
previously inflated JUnit IDs. Assertions, limits and selection are unchanged;
focused evidence shrank from about 4.1 MiB to 16 KiB.

Final configured full suite on the short-ID tree: **1,569 passed, 51 existing
skips, zero failures/errors**, 1,620 total, 157.864 seconds. Broader strict mypy
passed all 96 source files; repository Ruff and formatting passed (207 files).
The normal local pre-push hook passed its full 85-source-file mypy selection,
Ruff/format and configured unit/invariant selection. Normal pre-commit and
commit-msg hooks subsequently passed for shared checkpoint
`62a61583ba340405fde8b30ff636ad50d800ddaf`.

Recorded commands used the declared Python 3.11.16 development environment,
explicit source PYTHONPATH and installed CLI PATH; live AWS/DB opt-ins were
unset. No tests, warnings, caps or skip rules were weakened:

```sh
export PATH=/tmp/scanipy-hook-devtools-iT7nt4o1/venv/bin:/tmp/scanipy-root-devtools-KjtYhF/node-v20.19.0-linux-x64/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/tmp/scanipy-git-objects-BbzwR9
export PYTHONDONTWRITEBYTECODE=1
export PRE_COMMIT_HOME=/tmp/scanipy-root-devtools-KjtYhF/precommit
unset SCANIPY_AWS_LIVE_TESTS SCANIPY_DATABASE_URL SCANIPY_TEST_DATABASE_URL
unset SCANIPY_OCCURRENCE_TEST_URL SCANIPY_OCCURRENCE_TEST_REQUIRED
python -m pytest tests/unit/test_bounded_process.py -q --tb=short --junitxml=/tmp/scanipy-398-transport-short-ids.xml
python -m pytest tests/ -q --tb=short --junitxml=/tmp/scanipy-398-transport-checkpoint-full.xml
python -m mypy --config-file pyproject.toml analysis detectors integrations services workers tools
sh .husky/pre-push </dev/null
```

### 9.1 Separate path-snapshot correction after the offline checkpoint

The offline producer was separately checkpointed at
`6dbbfec087d103f1f2c24852dd19fd8f31c53a03` (177 focused and 1,746 full-suite
passes, 51 existing skips, normal local hooks). Root then identified that the
shared transport's own `_path` still formatted an exact but internally
poisonable PosixPath. Consumer-side path copies do not satisfy this public
transport boundary, so root assigned this existing three-file slice as a
separate correction; no offline producer or consumer files are changed.

The new regression was first run against the unchanged transport. It failed
exactly at pathlib formatting → caller component slicing, before the poisoned
filesystem/Popen sentinels: one failure, 102 deselected, 0.71 seconds
(`/tmp/scanipy-398-transport-path-before.xml`). No child or native source command
ran during that falsifier. The original failed evidence is retained, not
relabelled as a passing checkpoint. This correction implements the primitive
snapshot/actual-copy-use rules above without changing time/byte limits,
allowlists, process profiles, or production availability.

All 130 focused cases passed without skips on the declared Python 3.11.16
runtime in 5.30 seconds (`/tmp/scanipy-398-transport-path-focused.xml`) and on
the already-present Python 3.12.14 runtime in 5.58 seconds
(`/tmp/scanipy-398-transport-path-python312.xml`); no dependency was installed.
Ruff/format and strict module mypy pass. Root reviewed and approved the scoped
three-file delta and independently reran all 130 cases without failures/skips
in 5.39 seconds (`/tmp/scanipy-398-transport-path-root-review.xml`). The schema
consumer independently read and approved the correction without an overlapping
test run. The actual CI/pre-push markers select all 130 tests. Normal staged
pre-commit checks passed without source rewrites. Broad runs were serialized
to limit host contention. The final configured `python -m pytest tests/` run
passed **1,774 tests with 51 existing skips and zero failures/errors**, 1,825
total, in 169.62 seconds (`/tmp/scanipy-398-transport-path-full.xml`). The
normal local pre-push then passed repository Ruff/format (213 files), its full
87-source-file mypy selection, and the configured unit/invariant test selection.
No remote CI/canonical review or operational acceptance is claimed.

JUnit files are task-local diagnostic records, not portable immutable acceptance
artifacts. Existing user containers/database were untouched. Only small trusted
Python test children ran; no Git/Joern/Semgrep, scanned code, domain verifier,
controller, image build or stage campaign was launched. Exact-head CI/canonical
review and merged-dependency tests remain necessary before repository acceptance.
