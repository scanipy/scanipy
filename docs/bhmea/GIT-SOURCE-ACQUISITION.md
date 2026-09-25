# R16 — Native Git containment and source-capture replacement

Status: root-approved containment and packaging correction implemented and
independently reviewed locally; local test/hook checks passed. Merged-base and
publication gates remain open.
Issue: [#395](https://github.com/scanipy/scanipy/issues/395).
Owner: corpus/tooling agent; root owns review, project status and merge.
Date: 2026-09-25. Local dependency base:
`16252b21db172b967f13a815ca9bd8fe3078dd19` (pending PR #390).

Authority: [DECISION-BHMEA-01](../DECISION-BHMEA-01-current-execution-authority-2026-09-25.md).
This is an explicitly unavailable acquisition route until its replacement is
reviewed. Containment is not delivery of safe Git acquisition, source custody,
offline readiness, full R16 or any submitted Black Hat claim. #362 remains open.
The pending Java dependency is not accepted merely because this branch uses it.

## 1. Observed defects and immediate objective

The shared `secure_run` wrapper currently checks Git flag names but accepts
arbitrary `-c` values and bare subcommands. Its comment says the execute loop is
unimplemented, but the legacy snapshot worker actually clones and checks out a
repository. That worker's job parser checks field presence, not a closed URL,
commit or invocation profile; its explicit environment still permits system
Git configuration. `shell=False` alone does not prevent Git from invoking
configured aliases, hooks, filters, credential commands or remote helpers.

The GitHub, GitLab, Bitbucket and Azure DevOps default runners separately call
bare `git` through `asyncio.create_subprocess_exec`, inherit the environment,
and use unbounded `communicate()` without an enforced timeout. Their clone
methods create a destination and can write credential-bearing remote URLs
before their eventual success-path cleanup. They bypass the shared wrapper.

Read-only inspection and a call to the pure allowlist predicate confirmed the
gap. No unsafe/native target command was executed to demonstrate it. This scope
must close these named default paths, not just rename the shared flag allowlist.

**Known separate live route, not contained here:**
`deploy/scanipy_oracle/app.py:_run_scan` directly invokes Git clone/rev-parse
outside these wrappers, uses a mutable checkout and can substitute a zero SHA.
Its startup and scanner also run Semgrep with an ambient runtime. Root owns a
separate app containment/cutover design; that file is outside this 16-file scope.
This change therefore does not contain every live acquisition/scanner route or
establish system-wide no-execution safety. The user's running app/container is
untouched. Do not use #395 approval as authority to claim that legacy app safe.

## 2. Exclusive implementation file list

Only this document may be changed before root approves the design. After that
approval, the exact intended implementation scope is:

| File | Permitted change |
|---|---|
| `docs/bhmea/GIT-SOURCE-ACQUISITION.md` | This contract and actual scoped verification record. |
| `tools/worker/secure_subprocess.py` | Refuse every Git request before argument inspection, binary lookup or process creation; correct obsolete Git safety claims. |
| `workers/snapshot/Dockerfile` | Root-approved 16th-file correction: copy the SCM package required by the new refusal import; no tool/dependency/base-pin or launcher change. |
| `services/snapshot/worker.py` | Refuse default acquisition before staging; remove native clone/checkout calls; preserve downstream behavior through an explicitly injected trusted fixture materializer. |
| `integrations/scm/native_acquisition.py` | New small typed, constant-message native-acquisition refusal shared by snapshot/provider callers. |
| `integrations/scm/github.py` | Guard default clone before destination/credential staging; replace default runner body with explicit refusal; preserve other APIs. |
| `integrations/scm/gitlab.py` | Same containment and compatibility boundary. |
| `integrations/scm/bitbucket.py` | Same containment and compatibility boundary. |
| `integrations/scm/ado.py` | Same containment and compatibility boundary. |
| `tests/unit/test_git_acquisition_containment.py` | New hermetic public-boundary, default-runner, provider and snapshot falsifiers. |
| `tests/unit/test_snap05_execute_loop.py` | Replace fake native Git staging with the explicit trusted fixture materializer; retain downstream assertions and label their limited scope. |
| `tests/unit/test_java_static_safety.py` | Root-approved expansion: only the Git row's expected exception changes to the earlier unconditional Git refusal; other rows and no-spawn assertions remain. |
| `docs/components/DOC-CMP-SNAP-05.md` | Scoped current containment note overriding its historical runnable Git example, without rewriting historical ACs. |
| `docs/components/DOC-CMP-SCM-01.md` | Common current native-clone unavailability/injected-runner boundary. |
| `docs/components/DOC-CMP-SCM-02.md` | Link the current containment boundary for GitHub. |
| `docs/components/DOC-CMP-SCM-03.md` | Link the current containment boundary for the other providers. |

Existing `test_snap_specs.py`, `test_scm_specs.py`, `test_scm_connectors.py` and
Java observer tests are verification targets, not planned edit targets. Java
safety tests have only the narrowly approved Git-row compatibility change above.
If a change outside this list becomes necessary, stop and obtain root's scoped
approval. Do not change the frozen #390 or R05 worktrees, accepted corpus,
Dockerfiles except the approved snapshot package COPY above, dependency pins,
database, user app configuration, PLAN/SDD/WBS,
release state or remote project state.

## 3. Shared process boundary

Every `secure_run("git", ...)` request is unavailable in this generic wrapper.
There is no sanctioned Git profile in this change, including for apparently
read-only commands. A Java `environment_profile` argument does not authorize
Git. Do not add a Git profile enum, arbitrary configuration map, environment
switch or runtime bypass to its unbounded `capture_output=True` API.

The shared allowlist entry point must reject Git before inspecting/traversing
its supplied argv and before binary resolution or `subprocess.run`. Preserve
the existing typed `ArgvAllowlistViolation` category for that boundary, with a
constant explanation that native acquisition requires the separately reviewed
bounded producer. Never interpolate argv, environment, repository URL or
credential material into the refusal. The exported historical
`GIT_ARGV_ALLOWLIST` symbol may remain as an empty immutable compatibility
constant; it is not authorization for bare tokens. A fixed binary-path lookup
is tool metadata, not permission to run that binary.

All non-Git behavior must remain unchanged: Java's exact no-Delombok grammar,
forced no-fetch environment, source/workspace constraints, fixed exporter,
post-adapter observation and original-exception preservation are inherited
unchanged from #390. This scope does not certify other unprofiled tools/scripts.

## 4. Legacy snapshot worker boundary

An idle poll still returns without constructing collaborators, staging files
or emitting a job-completion metric. Existing malformed-job, environment-bind
and parent-snapshot checks remain ahead of acquisition in the same order.

For an otherwise valid job with the production/default acquisition setting:

1. Raise a typed `NativeGitAcquisitionUnavailable` with a constant reason.
2. Do so before resolving the default object-store collaborator or creating a
   temporary directory, source/work directory or other acquisition artifact.
3. Reuse the existing failure path: best-effort failed status, `queue.fail`,
   one failure metric and normal loop return. A secondary reporting failure
   still does not turn the job into success or prevent the normal queue-fail
   path. No source parser, CW detector, upload, ready status or queue ACK runs.

Remove the old real clone/checkout calls rather than leaving a dormant unsafe
acquisition implementation behind a user-controlled feature flag. Remove the
obsolete `_git_env` and Git-only timeout constants if they have no remaining
callers; do not change public process-wrapper exports merely for cleanup.

To retain meaningful tests of existing post-acquisition behavior, add one
explicit internal Python collaborator to `run_execute_loop`:

```python
class SourceMaterializer(Protocol):
    def __call__(self, job: SnapshotJob, destination: Path) -> None: ...

# Additional keyword-only argument; default means unavailable acquisition.
source_materializer: SourceMaterializer | None = None
```

This is a trusted in-process dependency-injection seam, not a source-custody
receipt, native safety profile, public API option or evidence of source identity.
It has no environment/CLI/HTTP/queue selector. The entrypoint supplies no
materializer. Tests explicitly supply a controlled fixture writer and the
existing fake parser/store/status collaborators; production defaults still fail
before staging. The callback writes only the worker-created source destination
in those tests. Existing tests must describe this as controlled downstream
behavior, not a real clone or a successful native-security test. Arbitrary
injected Python can execute arbitrary code and is outside this trust boundary.

Preserve the downstream language/CW/parser, artifact, failure/reporting and
queue semantics for these controlled tests. This avoids weakening those tests
or teaching them to disable the containment guard. No production-safe materializer
is supplied by #395; wiring the real capture-aware producer is later work.

## 5. Four provider clone/default-runner boundaries

Introduce a small shared `NativeGitAcquisitionUnavailable(SCMError)` and a
constant-message refusal function. The error is explicit unavailability, not
`SCMTransientError`, successful empty metadata, a retryable authentication
failure or a suggestion to retry the same unsafe native path.

For each provider, record whether the constructor received a genuinely explicit
runner rather than no runner or that provider's disabled default runner. At
the very beginning of `clone`, refuse the default path before:

- `dest_dir.mkdir`, filesystem traversal or byte counting;
- `_authed_clone_url`, token extraction/staging or remote configuration;
- Git runner invocation, HTTP calls or creation of `CloneMetadata`.

Passing the same default runner explicitly must not evade this early refusal.
The default runner's own callable body must also refuse immediately when called
directly; removing its asynchronous subprocess implementation prevents another
internal caller from accidentally using it. Retain its established signature.

Explicitly supplied trusted recording runners remain compatible with existing
connector conformance tests. Their constructor/API is a Python trust boundary,
not an API-authorized way to execute caller-selected code or a sanctioned
production no-execution profile. Do not broaden credential staging under these
injected paths; their existing behavior is not newly certified as production
custody or failure-safe secret handling by this change.

Do not alter the SCM ABC's six methods, HTTP transport, pagination, retry/backoff,
tiered-star/search compatibility, credential storage, authentication methods,
webhook verification/registration or provider metadata. Existing tests for those
behaviors must continue passing. Native default clone intentionally changes from
unsafe execution to explicit unavailability; it is not claimed feature parity.

## 6. Required containment tests and completion gates

All new tests are hermetic and explicitly unit-marked. A positive control means
an allowed non-Git or trusted injected fixture path, never executing an unsafe
hook, alias, helper, smudge filter, repository command or remote clone.

- [x] Shared wrapper refuses empty/apparently benign/hostile Git argv, arbitrary
  `-c` values, bare aliases, ext/ssh/file URLs and hostile environments before
  binary resolution or subprocess invocation. Poison argv objects are not
  traversed. Supplying the Java profile cannot authorize Git.
- [x] Existing non-Git allowed/denied controls remain, including all #390 Java
  profile and observer tests. No production Java/front-end file is changed.
- [x] Every provider's default clone, explicitly supplied same default runner,
  and directly called default runner refuse. Patch filesystem, credential and
  subprocess entry points to fail if reached; assert no destination exists.
- [x] Provider refusal messages do not contain supplied token/URL/env values.
  Existing trusted recording-runner clone tests and unrelated conformance,
  authentication, discovery, retry and webhook tests still pass.
- [x] Default snapshot job reports failed, queues failure and records exactly
  one failure metric without temporary staging, source/CW/parser work, store
  construction/upload, ready status or ACK. Reporting failure stays failure.
- [x] Idle polling does no work; earlier malformed/env/parent failures preserve
  their established semantics. Controlled source-materializer tests preserve
  the prior downstream parser/artifact/reporting/queue assertions.
- [x] Scoped Ruff/strict mypy, actual configured test selection, normal pre-commit
  and locally invoked pre-push hooks pass without skips/bypasses added to hide
  changed behavior. Remote push and merge gates are not claimed.
- [ ] After #390 is reviewed and merged, incorporate approved main and rerun
  combined checks. Obtain exact-head CI and successful canonical APPROVE before
  merge. A local dependency merge or review comment alone is not that gate.

Root has already verified #395 Project 5 Todo -> check -> In Progress. The
assigned agent must not duplicate board mutations. No native run, push or PR
publication is authorized at this checkpoint. Normal local commit checks after
implementation approval are implementation verification, not native acceptance.

Initial scoped verification passed 275 tests with four existing skips and one
failure: the existing Java-profile negative for `git status` expected the old
`JavaStaticEnvironmentError`. Git now correctly refuses earlier with
`ArgvAllowlistViolation`, before inspecting any Java profile. Root approved the
15th-file expansion to update only that Git row's expected category/message;
other Java rows and no-spawn assertions remain. No product fence was weakened
to satisfy the test. Strict mypy passed all 94 selected source files at that
checkpoint. The corrected scoped rerun passed **276 tests with four existing
skips** in 5.61 seconds. An independent Security Analyst-style local review
found no scoped blocker and independently repeated **276 passed / four skipped**
in 4.50 seconds. This is not the canonical merge review.

### Local verification record

The supported declared development environment was Python 3.11.16, pytest 9.1.1,
Ruff 0.15.22, mypy 2.3.1 and yamllint 1.35.1. Every source import was bound to
this worktree with explicit `PYTHONPATH`, not the environment's installed wheel.
The initial 58 containment cases are unit-marked and run in the normal selection.
No native Git, Joern, Semgrep, app/container or live database probe was used.

The first complete `pytest tests/` run had **1,400 passed, 51 existing skipped,
one failed** in 147.11 seconds. The failed hook-CLI test could not find
`yamllint`: Python was selected by absolute path, but its installed CLI directory
was not on the process PATH. The CLI was already present in the declared
environment. Correcting only PATH produced **1,401 passed, 51 existing skipped,
zero failures/errors** in 147.06 seconds. No test, warning, threshold or skip
behavior was changed for this setup failure.

Equivalent recorded command environment (task-local paths, not deployment
configuration):

```sh
export PATH=/tmp/scanipy-hook-devtools-iT7nt4o1/venv/bin:/tmp/scanipy-root-devtools-KjtYhF/node-v20.19.0-linux-x64/bin:/usr/local/bin:/usr/bin:/bin
export PYTHONPATH=/tmp/scanipy-git-containment-BpjHO9
export PYTHONDONTWRITEBYTECODE=1
export PRE_COMMIT_HOME=/tmp/scanipy-root-devtools-KjtYhF/precommit
unset SCANIPY_AWS_LIVE_TESTS SCANIPY_DATABASE_URL SCANIPY_TEST_DATABASE_URL
unset SCANIPY_OCCURRENCE_TEST_URL SCANIPY_OCCURRENCE_TEST_REQUIRED
python -m pytest tests/ -q --tb=short --junitxml=/tmp/scanipy-git-395-full-declared-path.xml
python -m mypy --config-file pyproject.toml analysis detectors integrations services workers tools
ruff check .
ruff format --check .
```

The explicit broader type check passed all **94 source files**; repository
Ruff and format checks passed (**203 files** already formatted). JUnit files
under `/tmp/scanipy-git-395-{focused,full,full-declared-path}.xml` and the separate
reviewer's `/tmp/scanipy-395-independent-review.xml` are local diagnostic outputs,
not committed immutable acceptance evidence.

The normal `.husky/pre-commit` initially refused three pre-existing explanatory
lines in the SCM component documents as Secret Keyword findings. Inspection
confirmed schema-key names and parameter-assignment examples, not credentials.
Root approved only three syntax-neutral wording corrections: period instead of
semicolon after `clone()`, the GitHub configuration field described as receiving
the supplied parameter, and the same prose form for the Azure consumer field.
All field names and behavior remain unchanged. The rerun passed every applicable
hook, including secret detection; no baseline, inline allowlist or hook rule
changed. Hooks with no matching changed files retain their normal no-files skip.

The normal `.husky/pre-push </dev/null` completed successfully: repository Ruff,
format checking, its full declared **84-source-file** mypy selection and its
configured unit/invariant tests all passed. A separate collection with unchanged
repository options confirmed **1,367 selected / 85 deselected** cases.
Empty stdin means local verification,
not a remote push. The broader explicit 94-file mypy invocation above additionally
covered `tools/`. No native target command was used as a positive control.
The #390 merged-base rerun, exact-head CI and successful canonical review remain
separate outstanding requirements before publication/merge.

### Packaging correction after the initial local checkpoint

The initial local commit is `5c6208ec0d1c788b156aa964374e16d115dbf47a`.
A subsequent read-only producer audit found that the snapshot Dockerfile omitted
`integrations`, although the new worker imports its typed refusal. A rebuilt
image from that recipe would fail at import before idle/failure reporting.
Checkout imports did not establish packaged import closure; no image was built
or run to discover this gap.

Root approved one additional file and the correction
`COPY integrations /app/integrations`, preserving all existing tool/base/lock
pins and commands. The existing containment test now assembles the Dockerfile's
literal local `/app` directory copies and starts a fresh isolated trusted Python
interpreter. An import finder confines every first-party module to that assembled
tree, so neither deliberately poisoned checkout `PYTHONPATH` nor an installed
Scanipy wheel can repair a missing package. The positive checks the actual worker
import, idle path and typed refusal; omitting only the integrations copy is a
required failing control. Native/job entry points are poisoned in the child.
Third-party packages come from the declared development environment: this checks
first-party packaging, not the worker lock's resolved/runtime dependency closure.

The first added tests hit an error while trying to shell-tokenize unrelated
Dockerfile continuation lines; restricting parsing to COPY instructions corrected
only the test assembler. The rerun passed **60 containment tests** in 9.54 seconds,
including both packaging controls. The fresh full configured suite passed
**1,403 tests with 51 existing skips, zero failures/errors** (1,454 collected)
in 152.015 seconds. Its JUnit record is
`/tmp/scanipy-395-packaging-full.xml`; the focused record is
`/tmp/scanipy-395-packaging-unit.xml`. These remain task-local diagnostics.
The normal local pre-push hook passed repository Ruff, format checking (203
files), its full 84-source-file mypy selection and configured unit/invariant
tests. Root independently reviewed the complete three-file packaging delta
and approved its limited implementation; no canonical merge verdict is implied.
The new local commit must pass the unchanged pre-commit/commit-msg hooks.
Any future recipe build has a new measured image
identity; this source edit does not establish that identity or authorize a build,
native probe, image publication or production acquisition.

## 7. Separate mandatory replacement scope (not implemented here)

The next scope must deliver a real bounded producer, not merely another report
model. Proposed entrypoint: `integrations/scm/source_acquisition.py` plus a
trusted local controller/CLI `scripts/capture_git_source.py`, a dedicated Git
process/profile transport and their tests. Reuse #392's source-only custody
backend after its reviewed merge. No generic unbounded wrapper widening.

Required sequence and evidence:

1. Accept a trusted request scope, approved repository endpoint and exact
   nonzero SHA-1 commit. Resolve symbolic refs through a separately closed
   trusted resolver; never pass arbitrary revision expressions to Git.
2. Create an exclusively owned fresh private bare object database with empty
   trusted templates/hooks and closed environment/configuration. Never reuse a
   caller repository, `.git/config`, alternates, worktree, credential helper,
   source-selected command or inherited loader/Git configuration.
3. Fetch only through a reviewed endpoint/egress profile with bounded streams,
   wall time, memory, PIDs and scratch storage. Disable redirects, recursion,
   automatic maintenance and prompting. HTTPS requires its real pinned
   `git-remote-https` helper; arbitrary helpers are forbidden. URL syntax and
   protocol allowlisting alone are not SSRF or network-isolation evidence.
4. Read exact commit/tree/blob objects by OID with no checkout, archive,
   textconv, smudge/filter, follow-symlink, submodule or LFS hydration operation.
   Inspect exact type/size/framing and independently verify Git object hashes.
   Retain original commit/tree bytes, modes, OIDs and blob SHA256 identities.
5. Reject malformed/duplicate/unsafe paths, symlink/gitlink entries, unsupported
   formats and exceeded bounds explicitly, never by omission. Materialize raw
   regular blobs through bounded exclusive no-follow writes into source-only
   staging, then invoke actual `LocalSourceCaptureStore.capture` and `verify`.
   Match stored inventory/content bytes back to the verified Git objects.
6. Bind immutable SCM proof to the generated capture UUID and actual manifest,
   tree and inventory digests. Keep this proof outside the capture's analyzed
   source and outside its closed `source/`, `manifest.json`, `SEALED` object layout.
   The current DB seal has no SCM-proof digest field: add an explicit reviewed
   binding, never misuse accepted-spec authority, a CPG snapshot FK or an
   invented environment identity. File-mode/Git-tree identity and the existing
   path/content-only source hash are distinct evidence.
7. Retain actual argv, effective closed environment, tool/helper/code/image
   artifacts, outcomes and honest bounded failures. Missing runtime identity
   stays missing. Unexpected process arguments are not overwritten with intent.
   LFS pointer bytes are committed blobs, not proof their external content was
   acquired/analyzed. Offline stage use requires verified captures/artifacts,
   not an implicit file-protocol exception to the network profile.
8. Run a separately authorized bounded pinned-image native fixture, then bind
   the actual producer to request/seal/lease and real detector/identity consumers.
   Test restart, nonreuse, orphan handling and fenced retirement. Do not use
   existing app/DB containers or source-selected commands as a rehearsal.

The currently declared Git package is `1:2.39.5-0+deb12u3`; a source document or
package version is not measured installed-tool identity. Pinned upstream design
references, inspected read-only:

- [Git 2.39.5 raw object and batch interfaces](https://github.com/git/git/blob/v2.39.5/Documentation/git-cat-file.txt).
- [Git configuration/environment and replacement controls](https://github.com/git/git/blob/v2.39.5/Documentation/git.txt).
- [Fetch recursion and maintenance options](https://github.com/git/git/blob/v2.39.5/Documentation/fetch-options.txt).
- [Archive attributes](https://github.com/git/git/blob/v2.39.5/Documentation/git-archive.txt)
  omit `export-ignore` entries and rewrite `export-subst` content; archive output
  must not silently substitute for exact committed blob custody.

This document does not mark any replacement TODO complete. Disabling unsafe
acquisition leaves real acquisition unavailable; the full submitted scope and
its implementation/evidence work remain mandatory.
