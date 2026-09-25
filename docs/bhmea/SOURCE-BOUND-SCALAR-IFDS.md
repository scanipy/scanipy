# Source-bound scalar IFDS — executable producer contract

Status: ROOT-APPROVED SCOPED DESIGN; local implementation authorized for
[#397](https://github.com/scanipy/scanipy/issues/397), under #378/#362.
Date: 2026-09-25. Owner: canonical/core agent; root owns review, project status
and integration. Root verified Project 5 membership and In Progress before the
first edit. Local dependency: typed-observed checkpoint
`b7dfaba503b9d58262999ddd0850ae45145687ba`; that local dependency is not an
approved merge or production acceptance.

Authority: [DECISION-BHMEA-01](../DECISION-BHMEA-01-current-execution-authority-2026-09-25.md).
The [submitted scope](../blackhat-mea-supporting-material.md),
[full review](../REVIEW-BHMEA-EXECUTION-ACTION-ITEMS-2026-09-23.md) and all
422 corrected corpus cases remain mandatory. This document does not mark R02,
R06, R10, R16, R19, G1 or any submitted claim complete.

Root approved the two meaningful diagnostic source examples, a Python-first
vertical implementation proposal, explicit entry/API models, a new semantic
version that preserves old DSL behavior, and the revised rule isolation, closed
model/selector shapes and whole-capture accounting. Root subsequently reviewed
all worker/result codec and dependency API sections and authorized the exact
18-file local implementation after the selected-entry restriction in section 11.
Code/tests, actual dependency integration and canonical merge approval remain
outstanding. These
engineering decisions are NOT an operational accepted-spec/model event, a
separate human CTO approval, a native-execution authorization or a canonical
PR verdict. No new native probe is authorized by this document.

## 1. Deliverable and strict non-goals

The next code slice must produce real value-flow occurrences and witnesses from
source-bound observations. An AST dump, observed graph container, synthetic
label match, nonzero native CALL count or successful empty scan is insufficient.

The first implemented language is Python. Shared closed rules, typed value
positions and matched call/return tabulation are included. Both diagnostic
source fixtures and their model bytes are included; Java execution remains a
second explicit extension after actual runtime/class/safety/charset evidence.
The Java fixture MUST return unsupported-language/profile in the first producer,
not run through Python semantics or a legacy fallback.

Preserve existing `analysis.ifds.solver.solve`, incremental behavior,
`analysis.ifds.raw`'s internal-bootstrap profile, old DSL text semantics, existing
accepted artifacts, and graph/slice v2 meaning. Do not strip native AST/PDG edges,
change graph labels or add planted source/sink operator strings to gain acceptance.
No DB/API/worker, Java safety allowlist, source-acquisition or publication change
is authorized by this contract's initial code subset.

The initial result proves modeled potential flow under declared assumptions.
It does not prove actual exploit execution, external dispatch, absence of all
vulnerabilities, extraction purity, complete language coverage or soundness of
every API model. Scanned source, its imports, target tests and build hooks are
never executed.

## 2. Versioned boundaries

| Boundary | Exact proposed identifier | Meaning |
| --- | --- | --- |
| Observed input | `scanipy-cpg/2` | Immutable observations, not derived semantic completeness; see the [typed observed contract](TYPED-OBSERVED-CPG-CONTRACT.md). |
| Syntax supplement | `scanipy-source-syntax/1` | Exact source-bound syntax observations with parser/options identity. |
| Projection | `scanipy-java-python-scalar-flow/1` | Closed scalar structural/value/call/return semantics specified here; implementation capabilities separately list Python only initially. |
| Rules | `scanipy-bound-rule-set/1` | Closed typed selectors and ordered clauses; not legacy text reinterpretation. |
| Models | `scanipy-operation-models/1` | Closed target-platform/API/built-in contracts, no executable callbacks. |
| Solver semantics | `scanipy-scalar-ifds/1` | Fixed matched transfers and finite tabulation in sections 9–11. |
| Raw result | `scanipy-semantic-raw-result/1` | Complete raw occurrence/witness envelope, no canonical hashes. |
| Later graph identity | `scanipy-canonical-graph/3` | Requires exact encoding of every new semantic role. NOT implemented here. |
| Later slice identity | `scanipy-slice-normal-form/3` | Requires binding-aware normalization and explicit purity coverage. NOT implemented here. |

The profile meaning is distinct from the implementation's capability manifest.
Adding a language implementation cannot silently broaden any defined operation.
A new operation, matching rule, transfer meaning or identity encoding requires
an explicit compatible extension/version decision and fresh evidence. Unknown
versions/capabilities are errors; they never select an older implementation.

## 3. Exact first source examples

### 3.1 Python: entry value through a transformed helper return

Proposed `tests/fixtures/semantic_g1/python/shell_flow.py`:

```python
import os


def assemble(left, value, right):
    joined = left + value
    return joined + right


def run(input_value):
    if type(input_value) is not str:
        raise TypeError("exact str required")
    prefix = "printf '%s\\n' "
    suffix = " >/dev/null"
    command = assemble(prefix, input_value, suffix)
    os.system(command)
```

The accepted entry model explicitly selects `run` formal 0 as untrusted input.
The external model selects argument 0 of the standard-library `os.system`
invocation as a shell-command sink. The code is static-parser input only.

Required evidence includes all three actual/formal links, both concatenations,
the `joined` definition/read, return expression, matching caller result,
`command` definition/read and sink argument. The minimum nonempty witness uses
the input-dependent path; the full projected operation also retains the two
constant operands. An unused helper or identity-only helper is not a substitute.

The model's target platform is explicit CPython 3.11/POSIX standard-library
behavior. Checked facts include exact import syntax, no source-local shadowing
or rebinding, the exact-type guard, uniquely bound helper, and operand types on
the continuing branch. The accepted environmental assumption excludes external
monkey-patching, custom import hooks and foreign mutation of these bindings.
Source inspection cannot prove that external assumption; report it as assumed,
not observed or globally closed-world. A real producer may proceed only under
the accepted conditional profile, not by silently asserting the assumption.

### 3.2 Java: planned second extension, not initially executable

Proposed `tests/fixtures/semantic_g1/java/SqlFlow.java`:

```java
package g1;

public final class SqlFlow {
    private static java.lang.String assemble(
            java.lang.String left,
            java.lang.String value,
            java.lang.String right) {
        java.lang.String joined = left + value;
        return joined + right;
    }

    public static void run(
            java.lang.String input,
            java.sql.Statement target) throws java.sql.SQLException {
        java.lang.String prefix = "SELECT * FROM records WHERE id = '";
        java.lang.String suffix = "'";
        java.lang.String query = assemble(prefix, input, suffix);
        target.executeQuery(query);
    }
}
```

The proposed source selects `run` formal 0; the sink is the String argument of
the declared JDBC invocation. The helper is private/static, fixed arity and not
overloaded. The proposed minimal binding is source syntax plus unique native
METHOD ownership and an accepted target-platform API model, NOT certification
that native JDK resolution succeeded. A modeled interface call is not proof of
a concrete implementation's runtime behavior. This choice requires the second
extension's explicit contract/acceptance, including nullable/exception behavior.

No JDK/classpath/launcher flag is authorized or guessed here. Keep
`JAVA_STATIC_V1` unchanged. Java syntax production, actual bundled-class loading,
source-position interpretation and safe invocation require their own reviewed
extension and separately authorized real run.

## 4. Immutable input and association trust

The exact cross-module API and imported dependency names are in section 12.5.
Its order of operations is:

```text
trusted execution/capture checks + live accepted-rule verification
  -> bounded immutable source/artifact reads
  -> isolated syntax -> checked projection -> one-rule tabulation
  -> replay-checked CompleteSemanticRawResult
```

Every input is mandatory. There is no constructor that turns self-declared
digests, a caller-supplied `accepted=True`, a graph object or an arbitrary path
into authenticated analysis authority. Controlled unit fixtures are explicitly
diagnostic and cannot earn real acceptance through a production CLI switch.

### 4.1 Exactly one qualified detector/rule per invocation

`resolved_qualified_rule` selects EXACTLY ONE detector and one rule artifact from
the resolver's authenticated bundle. A bundle containing several rules is not
implicitly a joint taint domain. Missing/ambiguous selection fails; never choose
the first, latest or same-named rule. Every rule's fact domain, compiled kills/
generation, worklist, summaries, counters and raw result is independent. No
cross-rule summary cache or sanitizer state is permitted.
Validate every admitted fact, transfer endpoint and summary against the one
invocation context. A foreign QualifiedRuleKey is an invalid-input error, not a
new implicit domain or permission for a cross-rule propagation edge.

The closed `QualifiedRuleKey` metadata has exactly these fields:

```text
schema = scanipy-qualified-rule/1
registry_id, bundle_id, scope, org_id, S_version, accepted_content_digest
detector_id, detector_version, detector_raw_sha256
rule_id, rule_artifact_id, rule_artifact_version, rule_raw_sha256
model_artifact_id, model_artifact_version, model_raw_sha256
semantic_descriptor_digest
```

UUIDs are canonical lowercase UUID text; `scope` is `global` with `org_id=null`
or `customer` with a real org UUID. Versions use the resolver's bounded canonical
MAJOR.MINOR.PATCH labels; all named SHA256 values are 64 lowercase hex. The IDs
obey section 9's ID grammar. Every field is checked against the actual accepted
member and retained bytes; `rule_id` equals that member's `spec_id`. No caller
can restamp a rule with another detector's key. Execution org/codebase/request/
capture identities are separately mandatory, including for a global rule.

Intern this key once per invocation; local in-memory facts may refer to that
immutable context rather than copy it. Their mathematical/serialized identity
still includes it. An explicitly ordered composition runs each expected
qualified rule independently and prefixes every raw key by
`(capture UUID, QualifiedRuleKey)`. Require the exact declared rule inventory;
reject missing/duplicate results or changed keys. Preserve per-rule success,
unsupported and failed states; success from one never marks another complete.
Composite success requires every required selected rule to complete. A rule's
sanitizer cannot kill another rule's same-site/same-ordinal origin.

### 4.2 Whole capture versus selected query coverage

The complete custody inventory is the universe of captured regular files.
ALL of them, including metadata, non-Python and excluded files, count toward
the 16-file, per-file, aggregate-byte and path ceilings. Validate and hash all
bytes before selection. A 17-file capture fails even if only one file is queried;
do not bypass the cap by passing an already-filtered inventory.

`QuerySelection` is immutable trusted controller data with exact fields
`schema=scanipy-scalar-selection/1`, `language`, `analyzed_files`, `excluded_files`.
Language is initially exactly `python`. `analyzed_files` is a nonempty sorted
unique array of safe relative `.py` paths; every captured `.py` file must be
included initially. Each exclusion is exactly `{path, reason}`, with reason
`non-python-source`, `declared-metadata`, or `outside-selected-query`. Paths are
sorted/unique, present in the complete capture, and disjoint from analyzed files.
The union MUST equal the complete inventory. None of these reason labels is a
proof that an excluded file contains no code or cannot influence an application.
Unknown/new/missing files or reclassifying a `.py` file as metadata reject.

Parse and validate every analyzed Python module completely, including unused
declarations. Entry source selectors must name included files; missing selected
entry/formal is an error. Ordinary source-module imports are unsupported in the
first profile, so an excluded file cannot be treated as a resolved dependency.
Only the explicit standard-library import/model assumption is allowed. Non-Python
files may remain excluded, but receive no parsing/analysis completeness claim.
Their content still belongs to the immutable capture and resource accounting.

Retain the exact selection, its SHA256 domain digest (ASCII schema, LF, compact
sorted-key UTF-8 JSON bytes), whole-capture inventory/digest and each analyzed
file's syntax/native validation status. Native file coverage is recorded as a
separate inventory and must cover every analyzed file under its declared frontend
profile; extra native observations are retained and explicitly accounted for,
not discarded to force association. `completed` means this selected-entry query
under this qualified rule completed. Whole-repository analysis status remains
`not_claimed`; parsing some files or verifying capture bytes cannot set it to
complete. The two diagnostic language fixtures use separate query captures.

### 4.3 Trusted adapter obligations

The trusted controller must:

1. Hold the active capture lease and trusted expected receipt/immutable seal.
   Use the reviewed source-custody verifier; keep the source mount read-only
   throughout verification, native parsing and syntax parsing. Same-UID or host
   administrators able to replace mounts/files are outside process-local proof.
2. Resolve the exact scope: org, codebase, request, capture UUID, actual source
   manifest/inventory/tree identities and nonzero resolved commit evidence.
   Source custody alone does not authenticate an asserted Git commit.
3. Re-read bounded regular source bytes from that verified source-only capture,
   check each inventory size/hash, and freeze them in bytes/tuple structures.
   Check file and aggregate limits before copying and again while reading.
   Never hold mutable caller lists/maps, writable buffer aliases or live ASTs
   as immutable inputs merely because a containing dataclass is frozen.
4. Verify the exact fetched CPG artifact bytes against a controller/store-provided
   expected digest, then use the strict typed observed reader. The digest is
   SHA256 of those actual serialized artifact bytes, not source content or a
   newly serialized graph. Retain raw-export identity separately.
5. Bind the producer record to the same capture and complete native file
   inventory. Recompute source byte identities independently. A digest string
   in an otherwise valid export does not prove that the parser used those bytes;
   the trusted adapter, immutable mount and retained actual invocation establish
   that association. Source/native structure checks additionally detect mismatch.
6. Resolve the exact qualified rule/model bytes and immutable authority evidence.
   Revalidate structural closure locally. The resolver authenticates content and
   authorization; it does not prove model truth or validate this solver.
7. Retain actual analysis-code/interpreter/frontend/profile identities. Absence
   remains an explicit missing-evidence failure for a real run, never a guessed
   image SHA or a graph hash repurposed as environment identity.

Raw content SHA fields use 64 lowercase hex in the rule/model boundary; existing
environment representations remain their defined `sha256:...` values. Do not
silently equate these distinct algorithms:

- Source tree: `sha256-length-prefixed-path-and-content-v1`, sorted relative
  paths, u64 big-endian path length/path bytes/content length/content bytes,
  with NO ASCII domain prefix.
- Source inventory: the custody/store's exact versioned envelope and domain
  framing, not a JSON serialization invented here.
- Raw-v2 probe source digest: its separately named `scanipy-source-tree/1`
  framing is different and must be recomputed/compared by meaning, not equality.
- CPG, rule and model raw-content digests: SHA256 of their respective exact bytes.

No source archive digest is invented for a directory capture. A source archive,
when genuinely supplied, has its own independently measured digest.

## 5. Exact conservative limits

All settings are trusted coordinator-only, frozen in the run/profile identity.
No request, source file, rule/model, environment variable or CLI input may raise
them. Each configurable value is an exact positive integer, not bool, and may
only LOWER the version-1 ceiling below. Failure to enforce an OS constraint is
unsupported-runtime, not permission to use an unbounded/in-process fallback.
These are implementation ceilings, not measured stage timing/memory promises.

| Quantity | Version-1 ceiling | Enforcement point |
| --- | ---: | --- |
| Whole-capture regular files, INCLUDING excluded/metadata files | 16 | Before content loading, then verify exact inventory. |
| One source file | 262,144 bytes | Before read and while streaming. |
| Total source content | 1,048,576 bytes | Before copy where known; cumulative while reading. |
| Relative path | 1,024 UTF-8 bytes / 32 components | Before filesystem or syntax use. |
| Rule artifact | 262,144 bytes | Before decoding. |
| Model artifact total | 524,288 bytes | Before decoding all retained models. |
| Accepted S + detector + rule bytes, including framed models | 1,048,576 bytes | Also enforce the independent occurrence/resolver aggregate cap. |
| Ordered clauses / models | 256 / 128 | Before semantic compilation. |
| Rule/model JSON | depth 24; 50,000 values; one string 16,384 bytes | Bounded preflight and strict duplicate-key/type decoding. |
| CPG artifact/raw JSON | 32 MiB / 16 MiB | Strict observed reader, then profile checks. |
| Observed nodes / edges | 10,000 / 100,000 | Observed validation, before projection. |
| Syntax AST occurrences / depth | 20,000 per run / 128 | Iterative child traversal, cumulative parent validation. |
| Syntax response | 8 MiB per run | Streaming parent cap before full decode. |
| Procedures / direct calls | 128 / 2,048 | Before graph construction. |
| Source call depth | 32 | Static graph check; cycles unsupported initially. |
| Typed operations / values / edges | 10,000 / 16,384 / 50,000 | Before insertion; no completed prefix. |
| Source origins | 64 | Before seeding. |
| Potential nonzero fact universe | 131,072 | Checked origin × value-position bound before allocation/tabulation. |
| Distinct path edges | 100,000 | Before first insertion. |
| Incoming/continuation records | 20,000 | Before first insertion. |
| Distinct summaries | 50,000 | Before first insertion. |
| Solver work units | 2,000,000 | Charge before each defined operation in section 11. |
| Raw occurrences | 4,096 | Before result admission. |
| Witness steps | 4,096 each / 65,536 total | Before expansion/serialization; shared proof DAG first. |
| Raw result bytes | 8 MiB | Bounded serialization, no truncated success. |
| Parser child stdout/stderr | 8 MiB / 64 KiB | Concurrent bounded drains; overflow aborts child. |
| Parser child wall deadline | 5,000 ms per file | Launch through exit/read completion. |
| Parser child CPU | soft 2 s / hard 3 s | Set before reading/parsing source. |
| Parser child address space | 256 MiB | RLIMIT_AS before untrusted input. |
| Parser child open files / file output / core dump | 32 / 0 bytes / 0 bytes | RLIMIT_NOFILE, RLIMIT_FSIZE, RLIMIT_CORE before input. |
| Projection/solver process envelope | 512 MiB, 30 s wall | Trusted isolated controller; explicit resource failure. |

All output/member/count bounds compose; satisfying one never disables another.
No O(ancestor-depth) stored path per observed node: reuse the linear ownership
forest and bounded syntax-node identifiers. Do not materialize an all-pairs
binding graph or all call strings. The 30-second envelope is not canonical T.
Canonical B/T and weak fallback are separate later identity semantics.

## 6. Python syntax parser isolation and errors

`ast.parse` is not an untrusted-code execution API, but malformed/huge input can
exhaust parser memory/stack. Never parse source in the controller process.

Use a dedicated stdlib-only trusted Python worker file, not an import of the
target module. The controller selects an absolute verified Python 3.11 binary
and exact verified worker path. Launch with isolated/no-site/no-bytecode flags
`-I -S -B` and an explicit private initially empty `-X pycache_prefix=...`.
Do not rely on `-B` alone: it prevents writes but does not exclude stale readable
bytecode. The worker must not import Scanipy or third-party code from the source
capture, cwd, site packages, user site or an inherited PYTHONPATH.

The exact child environment keys are `LANG=C.UTF-8`, `LC_ALL=C.UTF-8`,
`HOME=<private-workdir>/home` and `TMPDIR=<private-workdir>/tmp`. The controller
creates owned mode-0700 home/tmp and initially empty bytecode-prefix directories
without following symlinks. No additional/inherited Python, dynamic-loader,
shell-startup or executable-search keys are admitted; PATH is absent and the
executable is absolute. Use a fresh private working directory, no secrets/writable host
mounts, and the reviewed controller's no-egress isolation. Resource limits are
set in the trusted worker before reading the source request. A process-local
resource limit is not a claim of sandbox safety against a compromised interpreter;
actual mount/network/runtime isolation must be evidenced separately.

Transport one bounded file per child over exactly this stdin framing:

```text
ASCII "scanipy-python-syntax-request/1" + LF
u32-BE relative-path byte length + exact UTF-8 relative-path bytes
32 raw bytes of expected file SHA256
u64-BE source-content byte length + exact source bytes
EOF
```

Check each announced length against the configured limits before reading or
allocating it. The worker never opens that filename. It checks the declared
length/digest, rejects trailing data, then decodes strict UTF-8.
Initially reject NUL, BOM, non-UTF-8 encoding declarations and lone-surrogate
literal values; never replacement-decode or silently normalize source bytes.

Use only `ast.parse(text, filename=logical_name, mode="exec",
type_comments=False, feature_version=(3, 11))`. Never compile to executable code,
eval, exec, import, unparse/reparse, constant-evaluate target expressions or run
target tests. Record the exact interpreter implementation/version/code identity
and options. Standard-library parser output is syntax, not type/dispatch proof.

Traverse iteratively, counting AST occurrences (not Python object identities;
operator/context nodes may be shared). Assign ordered field/list-index paths.
Retain node kinds, supported primitive fields, field roles and byte locations.
Python column offsets are UTF-8 byte offsets; validate bounds against exact
line bytes, including CRLF and Unicode controls. Location is not binding proof.

The parent imports the corpus-owned `tools/worker/bounded_process.py`; it must
NOT implement a second transport. Root approved this design dependency/scope
correction, not native execution. The complete shared design was subsequently
root-approved for its separately owned implementation; frozen shared API:

```text
run_bounded_process(
    argv: tuple[str, ...], *, stdin: bytes | None, env: dict[str, str],
    cwd: absolute PosixPath, limits: frozen ProcessLimits,
    spool_dir: PosixPath | None = None,
) -> ProcessOutcome
```

Actual dependency integration uses its reviewed code/commit, never a copied
transport or a local substitute for shared types. Its approved design requires
`env` is an EXACT built-in dict of exact strings, `argv` an exact tuple of exact
strings, and stdin exact bytes or None. Custom Mapping objects/subclasses,
poison iterables and implicit coercion are rejected. At that boundary validate
bounded argv/env/stdin and make a private snapshot plus immutable execution
evidence before spawn; later caller mutation must not alter the launched input.
Our closed Python profile remains mandatory before this generic mechanism;
bounded transport is not authority to execute arbitrary commands.

Python uses memory mode with exact prebuilt stdin bytes, per-stream/combined
caps, and a parent cumulative 8 MiB syntax-output cap across children. The shared
transport owns concurrent nonblocking writes/drains, private process groups,
deadline including cleanup, overflow handling, kill/reap and bounded partial
outcomes. It must not interpolate raw output/env into exception messages.
Callbacks and interactive request/response protocols are not needed here.

Distinguish `reaped` completion from `cleanup-incomplete`/unknown outcome. OS
spawn stalls/uninterruptible waits and descendants escaping a process group need
the outer reviewed cgroup/container supervisor; group kill alone does not prove
they terminated. No cleanup-unknown outcome becomes successful parsing. The
domain parent retains the transport failure evidence and accepts completed syntax
only after successful complete transport. A reaped nonzero child may provide a
strictly validated failure-only envelope for error classification; it can never
provide an accepted completed syntax result. A zero exit is NOT domain success:
missing/malformed/trailing/partial syntax response is a protocol error. Child
signal/segfault, MemoryError, RecursionError, resource limit and syntax error
remain explicit failure categories, never an empty module. Errors expose stable
codes and validated locations, not arbitrary source lines or secret values.

### 6.1 Exact shared transport outcome consumed by this profile

These names come from the corpus-owned root-approved shared design, not local
replacement dataclasses. Implementation integration still waits for its actual
reviewed code/commit and required tests:

```text
ProcessLimits(stdin_bytes, stdout_bytes, stderr_bytes, combined_output_bytes,
              wall_ms, cleanup_reserve_ms)
FrozenInvocation(argv: tuple[str, ...], environment: tuple[tuple[str, str], ...],
                 cwd: str, stdin_bytes: int, stdin_sha256: bytes)
StreamEvidence(observed_bytes: int, retained_bytes: int | None,
               retained_sha256: bytes | None,
               eof: bool, truncated: bool)
MemoryOutput(evidence: StreamEvidence, data: bytes)
SpoolOutput(evidence: StreamEvidence, path: Path)
ProcessOutcome(invocation: FrozenInvocation, reason, pid: int | None,
               pgid: int | None, returncode: int | None, stdin_sent_bytes: int,
               stdout: MemoryOutput | SpoolOutput | None,
               stderr: MemoryOutput | SpoolOutput | None,
               elapsed_ms: int, cleanup)
```

`reason` is exactly `exited`, `timeout`, `stdin_closed`, `stdout_limit`,
`stderr_limit`, `combined_output_limit`, `spawn_error`, `io_error` or `cancelled`.
`cleanup` is `not_started`, `completed` or `incomplete`. Digests in these shared
in-memory types are 32 raw SHA256 bytes, not hex strings. There is no success
boolean. A completed cleanup means the leader was reaped, bounded pipes closed,
and final private-group cleanup signal delivered/group absent; it is NOT proof
that escaped descendants died or all descendants were reaped.

Our fixed profile sets stdin cap to the bounded request's exact size, stdout
8 MiB, stderr 64 KiB, combined output 8 MiB + 64 KiB, wall 5000 ms and cleanup
reserve 500 ms. The reserve is INSIDE that wall envelope, not a second timeout.
The worker resource limits in section 5 are fixed profile constants; controller
data/work caps may be lowered, never raised. Check child `getrlimit` observations
against those constants. Cumulative syntax stdout across children is still
8 MiB, including failure frames; a complete child does not reset the run cap.

Prelaunch invalid arguments raise `ProcessValidationError` without a process or
outcome. Postlaunch low-level failures use `ProcessTransportError.outcome` plus
the original `__cause__`; this consumer preserves the partial evidence and
does not convert the error to an exited outcome. Cancellation/cleanup behavior
follows the reviewed shared contract, without a second local implementation.
Unknown retained spool bytes/digest are null together, never invented; our memory
success requires both non-null and independently consistent with actual data.
Cleanup-incomplete raises ProcessTransportError, never an ordinary successful
return. KeyboardInterrupt/SystemExit remains the exact original primary exception
after bounded cleanup; an explicit evidence error cause retains its partial
cancelled outcome and earlier failures. Do not swallow cancellation or expose
private raw exception chains through public API diagnostics.

Accept syntax success only for `reason=exited`, `returncode=0`,
`cleanup=completed`, exact sent stdin length, both outputs of MemoryOutput type,
both EOF flags true, both truncated flags false, consistent observed/retained
counts and recomputed hashes, and a valid complete frame below. Stderr must be
empty for this trusted worker's success protocol. Completed exit 2 may carry a
valid failure frame; no other exit/status combination is success. Preserve
unrecognized/nonempty diagnostic bytes privately, not in public error messages.

### 6.2 Exact Python response framing and envelopes

The trusted worker writes exactly one stdout frame, never logs on stdout:

```text
ASCII "scanipy-python-syntax-response/1" + LF
u64-BE payload-byte length + exact payload bytes
EOF
```

Payload is compact sorted-key UTF-8 JSON (`ensure_ascii=False`, separators
`,` and `:`, no NaN), with no BOM, trailing whitespace or extra document. Parent
compares re-encoded bytes; reject duplicate keys, floats, non-finite numbers,
unpaired surrogates and unknown fields. Check announced length before allocation;
frame + payload must fit the 8 MiB cap. JSON nesting is at most 16 and total
JSON values at most 1,000,000; limits are checked during bounded decode. This
shallow transport limit is separate from the AST's maximum 128-edge depth.

Both statuses have exactly these keys:

```text
schema: "scanipy-source-syntax/1"
status: "completed" | "failed"
source: {path: RelativePath, sha256: Hex64, size: UInt} | null
parser: {implementation: "cpython", version: [3,11,Patch], cache_tag: "cpython-311",
         isolated: 1, no_site: 1, dont_write_bytecode: true,
         pycache_prefix: AbsolutePath, mode: "exec", type_comments: false,
         feature_version: [3,11]} | null
resources: {cpu_seconds: [2,3], address_space_bytes: [268435456,268435456],
            open_files: [32,32], file_bytes: [0,0], core_bytes: [0,0]} | null
nodes: SyntaxNode[] | null
error: {stage, code, location: Location | null} | null
```

`UInt` means exact nonnegative JSON integer within its referenced section-5 cap,
not bool; otherwise integers are signed 64-bit. `Hex64` is 64 lowercase hex.
Patch is a bounded nonnegative integer. Parser/resources are ACTUAL validated
observations, not unconditional echoes of expected configuration. Exact parser
binary/worker digests and outer isolation come from the trusted parent's runtime
evidence, not self-attestation inside this JSON. Parent checks the private prefix,
actual version and flags against its selected runtime. Setup mismatch is failure.

Completed requires source/parser/resources non-null, a nonempty nodes array
rooted at Module, error null, exit 0. Failed requires nodes null, error non-null
and exit 2. Source is null until the complete request, EOF and source digest are
validated. Parser/resources may be null only when their setup/observation failed;
missing fields are not permitted. A resource death may prevent any frame; parent
classifies the process evidence without inventing a worker response.

Error stage/code is one of these exact pairs; never serialize exception repr,
traceback, source line or an arbitrary user-provided message:

| Stage | Codes |
| --- | --- |
| request | `invalid-frame`, `request-limit`, `source-digest-mismatch` |
| runtime | `runtime-mismatch`, `resource-setup-failed` |
| decode | `invalid-utf8`, `unsupported-encoding`, `nul-or-bom` |
| parse | `syntax-error`, `memory-limit`, `recursion-limit` |
| validate | `unsupported-node`, `unsupported-constant`, `invalid-location`, `ast-limit` |
| serialize | `response-limit`, `internal-error` |

Unknown exceptions are failed internal diagnostics, never completed empty ASTs.
Failure `location` is null unless the exact source bytes and a valid interval
were actually established. In particular SyntaxError.offset is NOT assumed to
be an AST UTF-8 column; initially syntax-error locations are null. No guesswork
converts character indexes to byte indexes merely for a prettier diagnostic.

### 6.3 Flat AST occurrence encoding and closed primitive domain

Each SyntaxNode has exactly `{id, kind, parent, fields, location}`. IDs are dense
0..N-1 in field-order preorder. Root id 0 has kind Module and parent null.
Every other parent is exactly `{node: earlier NodeId, field: Name, index: UInt|null}`;
index is null for a scalar child and the actual list position for a list child.
`fields` is an array of `{name, value}` in the exact order below. Every occurrence
has one incoming field reference; all are reachable, no cycles, backward child
references, duplicate parentage, missing nodes or orphan rows. Context/operator
singleton AST objects become separate occurrences. Parent storage is linear;
do not store every ancestor path. The path-derived SourceSyntaxId is recoverable
from this forest; `(source path, node id)` is its compact document-local reference.

Field values are exactly one tagged variant:

```text
{"tag":"node","id":NodeId}
{"tag":"list","items":[Atom,...]}
{"tag":"str","value":UnicodeScalarString}
{"tag":"int","value":SignedInt64}
{"tag":"bool","value":true|false}
{"tag":"none"}
```

Atom is any non-list variant; nested lists are forbidden. Strings contain no
NUL or lone surrogates, are bounded by the source-file byte cap individually,
and by the response cap in aggregate. Preserve exact literal values; never
repr/stringify/coerce unsupported constants. Python bytes, complex, Ellipsis,
float and integers outside signed 64-bit are `unsupported-constant`; their
presence cannot produce a completed syntax document. `None`, bool and integer
syntax can be transported but are not thereby admitted as scalar-flow operands.
String kinds preserve null or the actual `u` prefix; other Constant.kind values
reject. No `literal_eval`, source evaluation or target import is used.

Here N means node, S string, L(T) ordered list of T, and `?` permits the explicit
none variant. All omitted kinds and fields reject. The exact field signatures
are Python-3.11-profile wire requirements, not arbitrary AST attribute export:

| Kind | Ordered fields and value types |
| --- | --- |
| Module | `body:L(N), type_ignores:L(N)` |
| Import | `names:L(N)` |
| alias | `name:S, asname:S?` |
| FunctionDef | `name:S, args:N, body:L(N), decorator_list:L(N), returns:N?, type_comment:S?` |
| arguments | `posonlyargs:L(N), args:L(N), vararg:N?, kwonlyargs:L(N), kw_defaults:L(N?), kwarg:N?, defaults:L(N)` |
| arg | `arg:S, annotation:N?, type_comment:S?` |
| Assign | `targets:L(N), value:N, type_comment:S?` |
| Name | `id:S, ctx:N` |
| Constant | `value:S/int/bool/none, kind:S?` |
| BinOp | `left:N, op:N, right:N` |
| Return | `value:N?` |
| Expr | `value:N` |
| Call | `func:N, args:L(N), keywords:L(N)` |
| Attribute | `value:N, attr:S, ctx:N` |
| If | `test:N, body:L(N), orelse:L(N)` |
| Compare | `left:N, ops:L(N), comparators:L(N)` |
| Raise | `exc:N?, cause:N?` |
| Load, Store, Add, IsNot | no fields |

For example keyword/TypeIgnore nodes have no accepted kind, so nonempty keyword
or type-ignore lists fail; unsupported decorators/defaults/annotations that use
otherwise encodable nodes are rejected by the full semantic syntax prepass in
section 7, not silently dropped by this codec. Verify field-child categories
against these signatures and Python roles (e.g. Name.ctx is Load/Store; BinOp.op
is Add; Compare.ops is IsNot); arbitrary same-shaped nodes cannot substitute.

`Location` is exactly `{start_line, start_byte, end_line, end_byte}`: lines are
1-based, columns 0-based UTF-8 offsets and end exclusive. Nodes with Python
location attributes (including alias/arg) require a complete non-null interval;
Module/arguments/context/operator rows require null. Reject partial attributes,
negative/reversed/out-of-file ranges and offsets inside a multibyte code point.
Build lines from ASCII LF, CRLF or CR only; Unicode line separators inside a
string are not extra source lines. Validate against original unnormalized bytes;
CRLF is not collapsed in retained source. Location narrows association but does
not prove binding or authorize an ambiguous native mapping.

## 7. Supported syntax, scopes and exact identities

Initial Python statement forms: module docstring, exact `import os`, ordinary
module-level function definitions, scalar assignment, return, sink-call
expression and the exact entry guard/raise form in section 3.1. Expression forms:
String literal, uniquely bound local/formal read, ordered String addition,
fixed-arity positional local call, and the approved sink/guard built-ins.

Inspect the COMPLETE module before producing any result. Reject class/async
definitions, decorators, annotations/defaults/star/keyword arguments, general
branches/loops, comprehensions, generators, lambda, walrus, global/nonlocal,
descriptors, arbitrary attribute/field/index access, exception handlers, dynamic
imports/reflection and recursive source call cycles. The one `os.system`
attribute is allowed only through its explicit import/API binding rule. The
one guard has no continuing join: its rejected branch terminates by raising.
General phi nodes are not silently approximated as identity in this profile.

Check all source declarations, including otherwise unused definitions, against
the closed syntax subset. The report lists the selected entry/reachable helper
scope and all declarations' validation status. A completed selected-entry query
does not certify unrelated repository APIs. Missing selected entry/formal is a
binding error. A valid sink rule matching no invocation can complete empty only
after full declared query coverage, never after skipped/failed parsing.

Construct exact snapshot-local identities:

- `SourceSyntaxId = (relative_file, ordered AST field/list-index path)`.
- `ProcedureId = SourceSyntaxId` of the uniquely associated declaration.
- `BindingId = (ProcedureId, lexical local/formal binding ordinal)` from a
  complete scope prepass; assignment uses do not create new lexical bindings.
- `ValueId = (ProcedureId, defining SourceSyntaxId, result-role, port ordinal)`.
  Each parameter entry, literal, read, binary result, assignment result, call
  result and return position has an explicit role. IDs are not source text.
- `OperationId = (ProcedureId, SourceSyntaxId, operation-role ordinal)`.
- `CallSiteId` is the call OperationId; each normal/exceptional continuation
  belongs to that call, never merely to the callee name.

Lexical name resolution uses a whole-function local-binding prepass. A read
before a supported definite assignment is rejected/explicitly exceptional,
never resolved to an arbitrary global. At every supported read, bind the exact
current definition; assignment creates a fresh value definition and updates
only that lexical binding. Literals/parameters never share IDs by equal text.
Each operand retains its positional role and evaluation order.

These IDs may change under refactoring and belong to raw provenance. They are
not canonical IDs and must not be hashed directly into semantic-v3 identity.
Names used to select an entry model are not synthetic native operator labels.

## 8. Source/native association and typed relations

Associate syntax to observations using verified same-file bytes, lexical
ownership, AST structure, declaration/parameter roles, reference edges, literal
values and supported operator templates. Position narrows candidates but does
not choose a winner. No first/last/lowest-ID/FQN tie-breaker is permitted.

Each association returns exactly one verified mapping or an explicit missing,
ambiguous, unsupported-lowering or contradictory-required-structure error.
Synthetic native nodes may be accounted for only by a named, tested pinned
lowering template. Never remove them merely to force a bijection. First real
native runs must validate each template against retained source and export;
mocked association tests cannot establish actual frontend fidelity.

Keep native CALL/dispatch/type hints unchanged. Derived relations carry their
own proof basis and native-hint status (`agrees`, `disagrees`, `absent`, or
`not-applicable`). A hint alone never certifies binding. A source derivation may
supersede a hint only where its complete profile proof is independently valid;
required source/ownership/literal/operand contradictions still fail closed.

Typed relations must include:

1. Declaration and unique lexical/native METHOD ownership.
2. Parameter positions, source bindings and local definition/read edges.
3. Ordered operator operands/results; exact String preconditions.
4. Actual evaluation order, actual-to-formal positions and unique helper target.
5. Explicit return expression/value and matching call-result/continuation.
6. Normal/exceptional exits and model effects.
7. Source/sink model application with original rule ordinals and proof inputs.

String type refinement is independent of the taint in-set. The exact Python
guard and known String literals establish continuing-path types; all helper
actuals must satisfy its String operation preconditions. An annotation or name
alone is insufficient. Reject uncertain operator overloading instead of assuming
`__add__`, `__str__` or a dynamic target is pure/identity.

The sink model records external execution/IO and potential exceptions. It does
not claim that the surrounding procedure is pure. Source helper concatenation
records allocations/possible exceptional behavior; purity normalization is later
work, even when all normal dataflow edges are known.

## 9. Rule/model schema and operational authority

The accepted-input resolver owns authentication, immutable acceptance records,
S-bundle framing, detector identity and content authority. This producer consumes
its exact ordered raw rule/model bytes; it does not reconstruct them, query an
unqualified global S_version, infer acceptance from a fixture path/PR, or turn an
LLM proposal into built-in authority. Code review approves implementation, not
the rule/model content's operational acceptance or statistical quality.

### 9.1 Common JSON domain and exact rule shape

All objects below are CLOSED: all listed keys are required, no additional keys,
duplicate keys, floats, non-finite values, NUL/lone-surrogate strings, bool-as-int
or implicit string/number coercion. Decode bounded exact UTF-8 bytes, preserving
those original bytes for hashing; input whitespace/key order need not be rewritten
into a purported historical representation. Enforce section 5's byte/depth/value
limits before or during decoding. Arrays retain order; only `clauses` may contain
duplicate equal members, because original ordinals are meaningful.

Common types:

- `Id`: ASCII `[A-Za-z][A-Za-z0-9_.:/-]{0,127}`; never interpreted as a path.
- `Name`: ASCII `[A-Za-z_][A-Za-z0-9_]{0,127}`. Unsupported Unicode identifiers
  reject in this initial selector profile, not by replacement/normalization.
- `Digest`: exactly 64 lowercase hexadecimal SHA256 characters.
- `Language`: exactly `python` or `java`; Java is decodable but not executable
  in the first producer. Other legacy Language values are not silently mapped.
- `ClassId`: the existing ClassName values `injection`, `path-traversal`, `ssrf`,
  `deserialization`, `xss`, `crypto-misuse`, `authn-authz`, `secrets`, `dep-cve`,
  `memory-safety`. Decodability does not claim any engine/class eligibility.
- `RelativePath`: normalized safe source-custody POSIX relative path, no empty,
  dot/dot-dot/backslash/control/NUL component; section 5's path bounds apply.
- `TypeId`: exactly `python.exact-str`, `python.int`, `java.lang.String`,
  `java.sql.Statement`, `java.sql.ResultSet`. No ANY, inheritance wildcard,
  implicit coercion, type variable or unresolved type is accepted here.
- `ContextId`: exactly `posix-shell-command` or `sql-query-text`.
- `ArgumentPosition`: exactly `{kind:"argument", index:int[0..255]}`.
- `ResultPosition`: exactly `{kind:"result", index:0}`; integer 0, not bool.

Root rule object:

| Required key | Exact value/type |
| --- | --- |
| schema | `scanipy-bound-rule-set/1` |
| semantics | `scanipy-scalar-ifds/1` |
| spec_id | Id; exact accepted member rule_id |
| class_id | ClassId; exact accepted detector class_id |
| engine | `ifds` only |
| languages | Nonempty unique ordered Language array, maximum 2 |
| projection_profile | `scanipy-java-python-scalar-flow/1` |
| model_artifact_digest | Digest; resolves to this member's exact raw model artifact |
| clauses | Ordered array of 1..256 closed clause objects below |

`class_id` and artifact-scoped model lookup are confirmed with the resolver
owner. Validate every clause's structure, including other-language clauses.
For the requested language require at least one Source and Sink clause, and
exactly one ContextId across applicable Sink/Sanitize clauses. In this initial
profile executable class/context is Python injection/posix-shell-command;
planned Java is injection/sql-query-text. Other combinations are unsupported,
not an empty or oracle result. An applicable source entry must bind uniquely;
a valid bound sink selector may match zero sites after complete query coverage.

Closed selector shapes:

```text
EntrySelector = {
  kind: "entry_parameter", language: Language, source_file: RelativePath,
  declaration: nonempty Name[] (maximum 32), formal_index: int[0..255],
  parameter_types: null | TypeId[] (maximum 256)
}
ModelSelector = {kind: "model", language: Language, model_id: Id}
```

For Python, declaration is exactly one module-level function Name and
parameter_types is null; source_file must be an analyzed `.py` file. For planned
Java, declaration is package components, enclosing type components and method
Name; parameter_types is the exact ordered declared signature, not null. Resolve
through source/native structure, never a native FQN dictionary. formal_index must
be within the actual declared formals. Every selector language belongs to the
rule's languages; ModelSelector also equals its model's language.

Closed clause variants (the braces enumerate ALL keys):

```text
{primitive:"source", selector:EntrySelector}
{primitive:"sink", selector:ModelSelector,
 position:ArgumentPosition, context_id:ContextId}
{primitive:"propagate", selector:ModelSelector,
 from:ArgumentPosition, to:ResultPosition}
{primitive:"sanitize", selector:ModelSelector,
 position:ResultPosition, context_id:ContextId}
```

Each position must fit the model signature and appear in its exact transfer
authorization. There is no global selector-less arg->ret rule, field position,
callback, arbitrary predicate, comment-derived selector or fallback identity.
Unsupported Propagate/Sanitize authorization rejects the invocation even if no
site would match. Original source-clause ordinal remains the root array index.

### 9.2 Exact model shape and finite initial model rows

Root model object has exactly `schema="scanipy-operation-models/1"`,
`target_platform_profiles`, and `models`. Profiles are a nonempty unique sorted
array from `scanipy-target-cpython311-posix/1`, `scanipy-target-java21-jdbc/1`.
Models are 1..128 objects, unique and sorted by model_id. Each model's target
profile must occur in that array; unused listed profiles are invalid.

Every model object has exactly these keys/types:

```text
model_id: Id
language: Language
kind: "builtin-operator" | "external-call"
target_platform_profile: one of the two profile IDs above
operation: "string-concat" | "external-api"
symbol: null | {owner:Id, member:Name}
signature: {receiver:null|TypeId, parameters:TypeId[], result:TypeId}
preconditions: [{id:Id, evidence_kind:"checked"|"assumed"}, ...]
normal: {result:"defined", effects:EffectId[]}
exceptional: {result:"absent", continuation:"exit-unknown-exception",
              effects:EffectId[]}
transfer_authorization: {
  sink_inputs:[{position:ArgumentPosition, class_id:ClassId,
                context_id:ContextId}, ...],
  propagation:[{from:ArgumentPosition, to:ResultPosition}, ...],
  sanitization:[{position:ResultPosition, class_id:ClassId,
                 context_id:ContextId}, ...]
}
```

`EffectId` is exactly `allocation`, `resource-failure`, `external-process`,
`external-io`, or `unknown-external-effect`. Effect arrays are sorted/unique,
maximum 5. Parameters maximum 256. Preconditions are sorted/unique by id,
maximum 16. Each authorization array is unique, maximum 256, sorted by its
position tuple then class/context where present. Null is an explicit field
value, never an omitted unknown. Unknown exception types remain an explicit
exceptional exit, not an assertion that a call cannot fail or has no effects.

Version 1 admits only the following exact rows; a different model_id or changed
signature/effect/check/authorization combination is unsupported. This is a
closed initial capability table, not a promise that arbitrary accepted data
can define executable operations. Extending it requires review/version handling.

| model_id | language/kind/operation | symbol; signature `(receiver; parameters) -> result` | checks | normal / exceptional effects |
| --- | --- | --- | --- | --- |
| `python.string-concat/1` | python / builtin-operator / string-concat | null; `(null; python.exact-str, python.exact-str) -> python.exact-str` | PC | allocation / resource-failure |
| `python.os-system/1` | python / external-call / external-api | `{owner:"os",member:"system"}`; `(null; python.exact-str) -> python.int` | PS | external-io, external-process / unknown-external-effect |
| `java.string-concat/1` | java / builtin-operator / string-concat | null; `(null; java.lang.String, java.lang.String) -> java.lang.String` | JC | allocation / resource-failure |
| `java.jdbc-execute-query/1` | java / external-call / external-api | `{owner:"java.sql.Statement",member:"executeQuery"}`; `(java.sql.Statement; java.lang.String) -> java.sql.ResultSet` | JS | external-io, unknown-external-effect / unknown-external-effect |

Python rows use target-cpython311-posix; Java rows use target-java21-jdbc with
the full prefixes above. The exact precondition bundles (PC/PS/JC/JS are table
notation, NOT JSON IDs) are:

- PC: checked `python-exact-str-operands/1`.
- PS: checked `python-direct-os-import/1`, `python-no-local-binding-mutation/1`,
  `python-exact-str-argument/1`, `terminal-selected-entry-call/1`; assumed
  `python-standard-os-implementation/1`, `python-no-external-binding-mutation/1`.
- JC: checked `java-string-operands/1`; assumed `java-standard-string-semantics/1`.
- JS: checked `java-declared-statement-receiver/1`, `java-string-argument/1`,
  `terminal-selected-entry-call/1`; assumed `java21-jdbc-contract/1`.

The compiled table fixes evidence_kind for each ID; a model cannot relabel an
assumption as a checked fact or omit a required check. Guard interpretation also
requires the selected Python target profile's explicit unmodified-builtins
assumption and verified absence of local shadowing. Record checked and assumed
conditions separately. Actual interpreter/frontend identities are run evidence,
not inferred from a target profile string.

For both concat rows, sink_inputs/sanitization are empty and propagation is
exactly argument 0 -> result 0 and argument 1 -> result 0. For os-system,
propagation/sanitization are empty and sink_inputs is argument 0, class injection,
context posix-shell-command. For jdbc-execute-query, the sole sink input is
argument 0, injection, sql-query-text; propagation/sanitization are empty.
The required normal/exceptional object literals and effect arrays follow the
table exactly. Receiver is separate from zero-based source argument positions;
never subtract native ARGUMENT_INDEX mechanically.

Read/assignment/actual-formal/return relations are language semantics. String
addition uses the exact accepted concat row's fixed operand dependencies even
without a redundant Propagate clause. A Propagate clause can only request an
already authorized relation; it cannot remove a language dependency or claim
an unknown external result is tainted/clean. Its site matching and original
clause evidence remain explicit. The required concat model must be present for
any concatenation in analyzed code, even if no rule clause names it.

External sink calls must be terminal statements in the selected entry; otherwise
unmodeled external effects could invalidate later scalar/binding assumptions.
Other placement rejects initially. Do not treat absence of later statements as
proof of external purity. General post-call effects/receivers remain full-scope
work. No initial production model authorizes sanitization, so a Sanitize clause
is structurally decodable but fails execution authorization. Fixed-kill algebra
and cross-rule isolation tests use explicit low-level diagnostic transfers,
never a production/test flag that admits an unreviewed model row. A real sanitizer
model requires a later precise context/effect contract and accepted content.

Resolve a model by `(rule.model_artifact_digest, model_id)`, never model_id alone
in a process-global dictionary. Two retained model artifacts cannot silently
overwrite one another's definitions. The raw combined accepted S/detector/rule
payloads, including models framed inside S, also obey the resolver/store's 1 MiB
aggregate ceiling; satisfying this producer's individual caps does not waive it.

Finding `rule_id` is the whole rule-set `spec_id`, not an invented sink-ordinal
identifier. Retain matching sink-clause ordinals in raw evidence under that
accepted rule. Different input ports remain distinct sink sites. If current
storage lacks these fields, retain the complete immutable raw payload until an
explicit reviewed storage extension; do not alter the frozen store implicitly.

The exact closed wire shapes above must be cross-reviewed with the resolver;
integration Python type names follow that reviewed implementation rather than
copied substitutes. Schema-valid data still needs operational authority and
verified source/profile preconditions. None of these names or tables creates
an accepted S artifact or authorized model event.

## 10. Matched transfer scheduling and sanitizer correction

Existing `analysis/ifds/dsl/flow.py` and `DOC-DSL` section 4.1 use pointwise union
of complete identity-carrying transfers. Controlled local diagnostic on X={1}:

| Transfer | Result | Existing bounded distributivity check |
| --- | --- | --- |
| sanitize {1} | {} | passes |
| union(sanitize {1}, sink identity) | {1} | passes |
| union(sanitize {1}, unrelated propagate 2->3) | {1} | passes |
| union(sanitize {1}, unrelated source 2) | {1,2} | passes |

This is a real semantic limitation despite distributivity. Preserve its old
version; do not silently redefine historical accepted DSL artifacts.

New semantic version, over NONZERO taint facts:

```text
F_e(X) = ((X \ W_e) union G_e union P_e(X)) \ K_e
```

W is a fixed strong-overwrite set, G fixed authorized generation, P a fixed
non-identity propagation relation, and K a fixed authorized final kill set.
Compile them from the verified operation and accepted models BEFORE tabulation;
they cannot depend on membership tests of the current taint in-set.

Schedule: bind rule instances; read sink predicates on selected input facts;
apply the single compiled normal transfer; follow the appropriate normal or
exceptional successor. Apply identity once, not once per clause. Do not generate
a normal result on an exceptional edge.

Strong overwrite requires a proved singleton definition target. Fresh scalar
definitions provide that boundary initially; ambiguous heap aliases cannot
justify killing facts. A sanitizer of a returned position does not cleanse its
input or every fact sharing an origin. Propagation into an explicitly sanitized
position is removed by final K. Source-generation/K overlap is rejected as a
contradictory model in version 1 rather than resolved by arbitrary rule order.

Fixed generation preserves DISTRIBUTIVITY, not identity. Fixed difference,
relational image and fixed generation distribute over union; their stated
composition therefore does too. This algebra proves the transfer family under
its fixed-set assumptions. Finite exhaustive tests test implementation instances,
not API-model truth, arbitrary language programs or all aliases.

Zero is a distinguished CONTROL fact outside X, W, G, P and K. No rule can name,
sanitize, overwrite, serialize as an origin, or report zero as a finding. Lift
the transfer to singleton exploded edges: zero maps to zero plus G at a reachable
authorized source operation; a nonzero fact maps through identity/kill/relation
with NO unconditional G. Thus sources generate only at reachable program points,
and source generation is represented by zero edges, not by reintroducing zero
from arbitrary nonzero facts. Duplicate source clauses retain separate origins.

Do not mechanically migrate legacy sanitizers: `shlex.quote` returns a value and
has context-specific shell safety; `PreparedStatement.setString` does not cleanse
a separate raw query later passed to executeQuery. Such models require their own
precise effect/context proof and accepted content.

## 11. Exact tabulation, termination and counters

Within one invocation, Fact = `(QualifiedRuleKey, origin source site,
original source-clause ordinal, ValueId)` plus that invocation's distinguished
zero. The key can be interned as a context reference; it is never omitted when
results or state are composed. The origin set and position universe are fixed and bounded
before solving. No unbounded access paths, runtime values, call strings or new
facts allocated from arbitrary source text during iteration are permitted.

Use procedure-relative path edges `(procedure, entry_fact, operation, fact)`.
Only selected entries begin with `(p, zero, entry(p), zero)`. The entry-source
operation generates the corresponding parameter-origin facts from zero.
Otherwise zero propagates solely on control-reachable edges and cannot be killed.
Do not seed every declaration merely because it exists in the observed graph.

Normal transfer inserts the corresponding successor path edges. At a local call:

1. Bind all evaluated actuals to exact callee formals. Zero starts the callee's
   zero context; a tainted actual maps only to its corresponding formal fact.
2. Register an incoming record with caller procedure/entry context, call site,
   exact callee entry fact, caller fact and matching continuation. Seed/reuse
   the callee entry path edge; never clone all dynamic call stacks.
3. Save unrelated caller facts in a separate call-to-return continuation record.
   Release them only when the callee zero context has a reachable NORMAL exit.
   A call proved not to return normally cannot fabricate continuation reachability.
4. At a callee exit, add a summary `(callee, entry_fact, exit_kind, exit_fact)`.
   Join it with ALL matching incoming records. Map only an explicit returned
   value to that call site's result; arbitrary callee locals do not become a
   caller result. Zero normal-exit summaries release control/bypass facts only.
5. A newly discovered summary must revisit waiting callers; a newly registered
   incoming record must consume existing summaries. Maintain indexed deduplicated
   join pairs so neither ordering loses effects nor repeats work indefinitely.
6. Exceptional exits remain distinct and follow only declared exception edges;
   initial source raises terminate the selected path. The initial subset has no
   handlers or source recursion; reject them before tabulation.

Source entry models apply at explicitly selected query entries, not every call
to a similarly named helper. To make that boundary exact without changing this
first domain, REJECT EVERY local call whose callee is ANY selected entry
procedure. Validate the complete projected call graph before compilation AND
before solving, including calls in unreachable/unused procedures. The same
procedure cannot be both a selected query root and a locally called helper in
this profile; no zero-context summary may activate entry-source generation for
a local caller. Two selected entries calling one another reject, even without
recursion. A later context-sensitive entry-activation extension is separate
full-scope work, not an implicit widening of this version.

External sink models observe reachable argument
facts before their invocation. Their approved normal/exception behavior is
explicit, never an unknown-call identity approximation.

Termination argument: input universes, path-edge tuples, incoming records,
summaries and summary/incoming join pairs are finite. Each is admitted at most
once and facts/summaries grow monotonically. The worklist terminates once no new
tuples exist, or fails on an explicit bound. This proves finite termination for
the implemented fixed domain/relations; it does not prove language soundness.

Use exact integer counters, incremented BEFORE the operation:

- `path_edge_admissions`: first insertion of a path edge.
- `incoming_admissions`: first insertion of an incoming/continuation record.
- `summary_admissions`: first insertion of a summary.
- `worklist_pops`: every dequeued path edge.
- `transfer_edge_attempts`: every (path edge, outgoing semantic edge) evaluation.
- `relation_pair_checks`: every candidate fixed propagation pair checked.
- `summary_join_attempts`: each first matching summary/incoming pair evaluation.
- `sink_origin_checks`: every candidate sink-position/origin check.
- `witness_expansion_steps`: every emitted proof step, including shared expansion.

`solver_work_units` is the sum of those counters, including admissions. Match
rules once during bounded compilation; no uncounted whole-graph or all-summary
rescan per worklist item. Charge failed/duplicate edge attempts where the stated
operation occurs; deduplication is not permission to omit its measured work.
Counter definitions/version and all configured limits are retained in evidence.
Tests exercise exact N-1/N/N+1 boundaries. No elapsed-time-dependent weak or
partial-success fallback exists. Time/memory failure is separate failed analysis.

Store first-discovery predecessor/summary dependencies in a shared proof DAG;
only earlier admitted proof records can be parents. Do not copy full paths into
every state. After the fixed point, reconstruct one bounded actual ordered
witness per occurrence and replay-check each binding/transfer/return step.
An invalid or over-limit witness fails the completed result, not just its hash.

## 12. Raw result, errors and replay boundary

Return immutable tuples, not a set that collapses occurrences. Occurrence key:
`(capture UUID, QualifiedRuleKey, sink operation/input port, source site,
original source-clause ordinal)`.
Keep rule_id/spec_id, matching sink ordinals, actual ordered witness and complete
source/native/model/runtime association evidence. No zero fact can be emitted.
No source-clause ordinal is regenerated from filtered clauses.

A complete raw result has exact input bindings, implemented language/profile,
declared query coverage, counters, occurrences and original source/model proof
references. It contains no placeholder cpg_order_hash, slice_fingerprint,
solution_hash or canonical-strength claim. Engine/origin is the new actual IFDS
producer (`ifds` / `deterministic-core`); it is not inferred from an oracle or
asserted as proof of full fidelity. Provenance must retain the accepted authority
and conditional scope that license that producer.

Stable failure categories include invalid-input, unaccepted-input,
source-artifact-mismatch, unsupported-language/profile/syntax/model,
missing/ambiguous-association, unsupported-lowering, parser-syntax/resource/
protocol/runtime failure, work-limit, witness-limit and solver-invariant failure.
No unknown exception becomes empty success. Failed diagnostics may retain a
clearly incomplete bounded prefix, but it is not a CompleteSemanticRawResult,
finding-removal evidence, lifecycle resolution or successful scan coverage.

The raw result is retained durably before any semantic-v3 identity stage. If
the raw sink/witness stage succeeds and later identity fails, preserve that raw
success and expose failed identity. If raw analysis itself fails, do not replace
previous detections with empty findings. Actual durable/worker integration is a
separate dependency, not delivered by a pure returned Python object.

Canonical/encode/fingerprint/legacy solve/run_detector routines are forbidden
anywhere on this raw path. Tests patch them to raise. Later v3 identity must
encode all semantic roles and complete dependence cones; it cannot depend on
the first raw witness, ephemeral IDs or incomplete traversal. Binding-aware
renaming and extraction normalization require separate coverage/purity evidence.

### 12.1 Common result wire rules and input evidence

The following is a CLOSED codec, not a Python-object pickle or extensible
free-form properties map. JSON uses section 6.2's exact canonical byte spelling,
duplicate/type checks, maximum depth 24 and maximum 1,000,000 JSON values.
The COMPLETE result, including framing, is at most 8 MiB. Arrays preserve order;
reject unknown/missing keys, duplicate IDs, references outside their table,
invalid discriminant/null combinations and bool-as-integer. Integer indexes are
nonnegative and bounded by their referenced table. Raw native node IDs retain
the observed model's canonical decimal strings, not guessed integers/FQNs;
native edge references are actual original edge ordinals. Document-local dense
indexes are transport references, NEVER canonical graph IDs.

Framing is exactly ASCII `scanipy-semantic-raw-result/1`, LF, u64-BE JSON length,
JSON bytes, EOF. No compression, extra member, trailing whitespace or failed
prefix is a valid complete result. Raw SHA256 means the hash of these actual
framed bytes; it is NOT cpg_order_hash, slice_fingerprint or solution_hash.
The corresponding projection bytes use the same framing rule with ASCII
`scanipy-scalar-projection/1`; their raw hash binds a replay input, not refactor
invariance. The result embeds the projection object, so no unbounded external
projection fetch is required just to validate its shape.

Common exact records:

```text
ArtifactRef = {sha256: Hex64, size: UInt}
SyntaxRef = {file: FileIndex, node: SyntaxNodeId}
FileRow = {path: RelativePath, sha256: Hex64, size: UInt,
           syntax_response: ArtifactRef}
InputEvidence = {
  capture_id: UUID, source_tree_digest: Hex64, source_inventory_digest: Hex64,
  source_manifest_digest: Hex64, source_archive: ArtifactRef|null,
  cpg_artifact: ArtifactRef, raw_export: ArtifactRef,
  accepted_spec: ArtifactRef, detector: ArtifactRef, rule: ArtifactRef,
  model: ArtifactRef, sealed_authority: ArtifactRef|null,
  execution_authorization: ArtifactRef|null, authority_verification: ArtifactRef|null,
  source_acquisition: ArtifactRef|null, native_invocation: ArtifactRef,
  analysis_manifest: ArtifactRef|null, syntax_invocations: ArtifactRef[]
}
```

Each reference is to retained exact bytes, not an invented path or arbitrary
locator; resolve only through a trusted artifact store. Per-file syntax response
refs include the frame and match the parser outputs used for this projection.
syntax_invocations has the same file order/count and retains actual shared
transport/runtime evidence. No duplicate/different artifact may be substituted
under the same reference. Observed dependency APIs use `sha256:` prefixed text;
validate that exact prefix and digest and explicitly convert to Hex64 here.
Source tree/inventory/manifest digests keep their DISTINCT algorithms from
section 4/the custody contract. Directory capture legitimately has archive null.

All referenced records must be fetched, bounded, rehashed and interpreted under
their own reviewed schemas before production use/replay. Hash equality does not
authenticate origin, live policy or correspondence to a source capture. Evidence
for an actual invocation is not loaded-class attestation. A missing full analysis
manifest is not replaced by a container image hash.

### 12.2 Exact immutable projection and association records

`SemanticProjection` is the frozen in-memory view of this exact object; nested
lists/maps become validated tuples/records with no mutable aliases:

```text
{
  schema: "scanipy-scalar-projection/1",
  profile: "scanipy-java-python-scalar-flow/1", language: "python",
  selection: QuerySelection, selection_digest: Hex64,
  files: FileRow[], procedures: ProcedureRow[], bindings: BindingRow[],
  values: ValueRow[], operations: OperationRow[], relations: RelationRow[],
  control_edges: ControlEdge[], associations: Association[],
  model_applications: ModelApplication[], selected_entries: ProcedureId[],
  native_files: RelativePath[]
}
```

Every row table except files has an `id` equal to its zero-based array position.
Files are sorted by exact UTF-8 path bytes; node references use section 6's
preorder. Procedures follow (file index, declaration syntax-node index); bindings
use formal order then first lexical binding occurrence. Value/operation records
use (procedure order, syntax preorder, explicit role order below, port). Other
tables use the lexicographic tuple of their declared fields excluding id, with
null ordered before non-null, integers numerically, strings by UTF-8 bytes and
arrays elementwise. Associations are ordered by syntax/role/template before
dependent rows are indexed; applications by operation. Validate uniqueness of
semantic row keys; do not collapse original rule clauses or native parallel edges.
This is deterministic serialization within this implementation/profile, NOT a
canonical-labeling claim across equivalent/refactored source.

```text
ProcedureRow = {id, syntax: SyntaxRef, entry: OperationId,
                normal_exit: OperationId, exceptional_exit: OperationId,
                formals: ValueId[], return_value: ValueId|null}
BindingRow = {id, procedure: ProcedureId, syntax: SyntaxRef, name: Name,
              kind: "formal"|"local", formal_index: UInt|null}
ValueRow = {id, procedure: ProcedureId, syntax: SyntaxRef, role: ValueRole,
            port: UInt, binding: BindingId|null, type: ValueType}
OperationRow = {id, procedure: ProcedureId, syntax: SyntaxRef, kind: OperationKind,
                inputs: ValueId[], output: ValueId|null, callee: ProcedureId|null,
                model_application: ModelApplicationId|null}
RelationRow = {id, from_value: ValueId, to_value: ValueId, role: RelationRole,
               operation: OperationId, position: UInt,
               associations: AssociationId[]}
ControlEdge = {id, source: OperationId, target: OperationId, kind: ControlKind,
               call_site: OperationId|null, relations: RelationId[]}
Association = {id, syntax: SyntaxRef, role: AssociationRole,
               template: Id, native_nodes: NativeNodeId[], native_edges: EdgeIndex[],
               hint_status: "agrees"|"disagrees"|"absent"|"not-applicable"}
ModelApplication = {id, operation: OperationId, model_id: Id,
                    checked: [{id: Id, syntax: SyntaxRef[],
                               associations: AssociationId[]}], assumed: Id[]}
```

Closed enums, with listed order used for role ordering:

- ValueRole: `parameter`, `literal`, `read`, `binary-result`,
  `assignment-result`, `call-result`, `return-position`.
- ValueType: `python.unrefined-entry`, `python.exact-str`, `python.int`.
  Unrefined entry is not an executable operand/API model type. Refinement on the
  guard's continuing edge must be proved before String use; it is not a taint
  transfer or permission to treat the rejected branch as passing.
- OperationKind: `entry`, `normal-exit`, `exceptional-exit`, `literal`, `read`,
  `assign`, `string-concat`, `call-local`, `call-external`, `return`,
  `guard-exact-str`, `raise`.
- RelationRole: `definition-read`, `assignment`, `operand-result`,
  `actual-formal`, `return-value`, `return-result`.
- ControlKind: `normal`, `guard-pass`, `guard-raise`, `exception`,
  `call-enter`, `call-return`, `call-bypass`.
- AssociationRole: `declaration`, `formal`, `local`, `read`, `literal`,
  `operator`, `call`, `argument`, `return`, `method-return`, `control`.

Output/arity constraints are exact. Literal has zero inputs and one output;
read/assign one input and one output; concat two ordered inputs and one output;
local call has exactly its ordered callee-formal arity and one output iff the
callee returns a scalar. External call uses the exact model signature. Return
has zero inputs for the selected entry's void completion, otherwise one input
and its procedure's return-position output. Guard has one input and no output;
entry/exits/raise have no data inputs/output (the guard's fixed TypeError literal
is syntax evidence, not a modeled taint receiver). Callee is non-null exactly
for call-local; model_application is non-null exactly for concat/call-external.
Formal bindings have exact consecutive indexes; local indexes are null.
Parameter/read/assignment value binding must match lexical ownership; other
value bindings are null. Every defined value has one defining role/port, every
read uses the correct current definition, and every relation preserves the
matching operation's operand/parameter position. No dangling or cross-procedure
relation is allowed except the explicitly matched actual-formal/return-result.

Normal/guard/exception edges stay in their procedure. Call-enter/return/bypass
carry the EXACT call operation; enter targets that callee's entry, return comes
from its normal exit to that call's continuation, and bypass connects that same
caller call/continuation. A return from another call or exceptional exit never
substitutes for a normal continuation. No general branch or recursion is enabled
by merely including an edge of a known kind. Validate the full section-7 profile.

Relations/associations contain sorted unique reference arrays except where
operand order is explicitly the inputs array. Native edge IDs remain distinct
even for parallel equal payloads. Each template must be an implemented, reviewed
pinned-lowering template; arbitrary Id spelling cannot register a new template.
Evidence must include actual native METHOD ownership and relevant AST/REF/
operand/return structure. Required ambiguity/contradiction fails projection.
ModelApplication.model_id resolves ONLY inside this qualified rule's exact model
artifact; checked/assumed IDs equal that row's declared preconditions, not a
caller-selected subset. Checked evidence is revalidated, not trusted as a boolean.
Effects and exceptional behavior resolve from those retained exact model bytes.

Resource limits apply before table construction and on decode. Total associations
and relation/evidence reference entries each have a 100,000 ceiling in addition
to section-5 node/edge/value limits; no ancestor-path or all-pairs expansion.
`max_relations` bounds the SUM of relation rows and control-edge rows, not a
separate allowance for each. Source-native association template references count
toward max_evidence_references as well as their referenced native table caps.
No `completed` projection may omit an analyzed declaration because it is unused.

### 12.3 Closed complete result, occurrences and replayable witnesses

CompleteSemanticRawResult serializes exactly:

```text
{
  schema: "scanipy-semantic-raw-result/1", status: "completed",
  semantics: "scanipy-scalar-ifds/1", engine: "ifds",
  origin: "deterministic-core", qualified_rule: QualifiedRuleKey,
  execution_kind: "controlled-diagnostic"|"historical-replay"|"fresh-native",
  execution_binding: ExecutionBinding|null, inputs: InputEvidence,
  projection: SemanticProjection, projection_sha256: Hex64,
  coverage: {query: "completed", repository: "not_claimed",
             analyzed_files: RelativePath[], reachable_procedures: ProcedureId[]},
  limits: ScalarLimits, counters: SolverCounters,
  source_origins: SourceOrigin[], control_proofs: ControlProof[],
  occurrences: RawOccurrence[]
}
SourceOrigin = {id, entry: ProcedureId, site: SyntaxRef, parameter: ValueId,
                source_clause_ordinal: UInt}
RawOccurrence = {sink_operation: OperationId, sink_input: UInt, source_origin: OriginId,
                 sink_clause_ordinals: UInt[], witness: ProofStep[]}
Fact = {kind:"zero"} | {kind:"value", origin: OriginId, value: ValueId}
ProofState = {operation: OperationId, fact: Fact}
ProofStep = {before: ProofState, after: ProofState, edge: ControlEdgeId,
             transfer: "zero"|"identity"|"generate"|"propagate",
             relation: RelationId|null, control_proof: ControlProofId|null}
ControlProof = {id, procedure: ProcedureId, steps: ControlStep[]}
ControlStep = {kind:"edge", edge: ControlEdgeId}
             | {kind:"call", call_site: OperationId,
                callee_proof: EarlierControlProofId, bypass_edge: ControlEdgeId}
```

Origin rows are ordered by (entry, original source ordinal, parameter). A source
selector matches exactly one declared entry/formal or fails binding, so repeated
equal Source clauses remain distinct origins. Raw occurrence order is
(sink operation, sink input, source origin); its full logical key is prefixed
by capture_id and QualifiedRuleKey. Exactly one row per such key, no duplicate
or set collapse. sink_clause_ordinals is the sorted NONEMPTY set of actual
matching original Sink clause indexes. Zero, a foreign rule/origin, missing
source clause, invalid input port or ordinal of another primitive is invalid.

Witnesses are chronological exploded-state transitions, not only unconnected
dependency labels. Start at that origin's selected procedure entry with zero;
end at the exact sink operation with a nonzero fact equal to the sink's actual
input ValueId and the occurrence's origin. Consecutive before/after states
match exactly. An entry-source generation step changes zero to its origin's
parameter; it names no relation. Zero propagation stays zero; identity preserves
the same fact; propagation preserves the origin and uses the named edge relation.
Generation/identity/propagation is accepted only if the independently recompiled
one-rule transfer permits it after writes/kills. Relation is non-null exactly
for propagate. No zero kill, nonzero-to-zero or source generation on arbitrary
nonzero input is allowed.

Call-enter pushes its call site; call-return must pop the same site/callee and
map only the explicit callee return position to its caller result. A sink inside
a callee may end with an open matched prefix; a returned-to-wrong-caller trace
rejects. Call-bypass preserves a caller fact only with non-null control_proof
showing that exact callee has a normal zero-control path. Other steps require
control_proof null. This prevents a fabricated continuation after only an
exceptional or unreachable callee exit. Conditional external normal behavior
uses its actual accepted model, not a claim the real call cannot throw.

Each ControlProof is a procedure-relative path from entry to normal exit.
Edge steps are within that procedure and legal under the zero/control semantics;
call steps use a matching bypass edge plus an earlier callee proof. Validate
continuity, call identity, entry/exit and the acyclic reference order. Retain
shared proof DAG storage; charge every expanded control/witness step to the
same 65,536 run-total and 4,096 per-occurrence expansion ceiling. Proof records
are bounded by admitted path states; references cannot hide exponential output.
Solver summaries store callee-relative derivations, NOT an absolute first
caller's history. Witness expansion instantiates the chosen matched incoming
context, so reuse at a second call cannot splice the first caller into its proof.

`SolverCounters` has exactly the nine counters named in section 11 plus their
recomputed `solver_work_units` sum. `ScalarLimits` has exactly the lower-only
named fields mapped in section 12.5; serialize actual configured values, not
unconditionally the ceiling. Coverage files equal projection.files exactly;
reachable_procedures is the actually selected-entry call closure and never
implies whole-repository coverage. Recompute counts/sets; no trusted totals or
pass flag can override malformed evidence.

Only controlled-diagnostic may have execution_binding or authority/analysis/
acquisition references null. Such output is component evidence, never an
authorized production run/G1 result. Historical replay retains the original
binding/evidence and labels its age; it cannot be restamped fresh. A fresh native
run requires real current binding, authority verification, source acquisition,
native invocation and full environment manifest. A pure dataclass constructor,
CLI string or caller-supplied execution_kind never grants that status. The
production runner fixes it from reviewed actual execution evidence; there is
no `--diagnostic-as-fresh` or acceptance bypass.

Witness replay establishes that each reported modeled path exists in the
verified projection under the stated rule/profile. It does NOT by itself prove
fixed-point completion, that no occurrence was omitted, runtime exploitability,
model soundness, source/native authentication or acceptance freshness. Complete
occurrence inventory is the trusted bounded solver's fixed-point obligation;
independent completeness replay reruns projection/compilation/solver and compares
the exact logical occurrence keys and replay-valid witnesses. A checker that
only validates provided witnesses must report that narrower result honestly.

### 12.4 Exact failure object and no partial completed result

`SemanticAnalysisError` has a stable `failure` record plus optional retained
partial process evidence, and chains the original exception without interpolating
raw source/env/output in its message. Its diagnostic wire framing uses ASCII
`scanipy-semantic-raw-failure/1`, LF, u64-BE JSON length, JSON, EOF, at most 64 KiB.
Exact payload:

```text
{schema:"scanipy-semantic-raw-failure/1", status:"failed", stage, code,
 qualified_rule: QualifiedRuleKey|null, capture_id: UUID|null,
 source: SyntaxRef|null, limit_name: ScalarLimitName|null,
 observed: UInt|null, process_evidence: ArtifactRef|null}
```

Stage/code pairs are: input (`invalid-input`, `source-artifact-mismatch`),
authority (`unaccepted-input`, `authority-unavailable`, `stale-execution`),
syntax (`parser-syntax`, `parser-resource`, `parser-protocol`, `parser-runtime`,
`unsupported-syntax`), projection (`unsupported-language`, `unsupported-profile`,
`missing-association`, `ambiguous-association`, `unsupported-lowering`),
rules (`unsupported-model`, `invalid-rule`), solve (`work-limit`, `solver-invariant`),
proof (`witness-limit`, `invalid-proof`), and output (`result-limit`, `internal-error`).
Resource/codec errors retain a valid applicable limit_name/observed pair or null
when no measurement exists; never invent a count. Source is null until safely
bound. A failure contains NO occurrences array, completed coverage or lifecycle
absence assertion. Private partial diagnostics may be retained separately but
cannot deserialize as CompleteSemanticRawResult.

### 12.5 Exact module APIs, dependency imports and implementation order

No extra source file is added. The approved first subset still has 18 files.
Public own-module types are frozen, slotted records with exact primitive/tuple
fields; constructors validate shape/limits but never confer authority. Pure
functions are suitable for controlled tests; only the production runner performs
the trusted execution/lease/source/authority admission sequence.

`analysis.cpg_ingest.source_syntax` owns:

```text
FrozenSourceFile(path: str, content: bytes, sha256: str)
PythonSyntaxRuntime(executable: Path, executable_sha256: str,
                    worker: Path, worker_sha256: str, version: tuple[int,int,int],
                    private_root: Path)
SourceSyntaxDocument(payload, response_bytes: bytes,
                     process: ProcessOutcome | None)
parse_python_file(source: FrozenSourceFile, *, runtime: PythonSyntaxRuntime,
                  limits: ScalarLimits) -> SourceSyntaxDocument
decode_syntax_response(data: bytes, *, source: FrozenSourceFile,
                       runtime: PythonSyntaxRuntime,
                       limits: ScalarLimits) -> SourceSyntaxDocument
```

Payload is the exact immutable section-6 completed schema. Source file hashes
and selected executable/worker hashes are Hex64. The parent rehashes trusted
executable/worker artifacts, enforces its closed
profile and invokes the one imported bounded transport. SourceSyntaxDocument
retains exact response bytes and immutable process evidence in addition to the
decoded payload; decode_syntax_response returns process=None and has no
process-success/authority power. parse_python_file returns a validated actual
process outcome. The production runner requires those observed outcomes for
every syntax document; pure structural replay may use the separately retained
original evidence but cannot restamp a decoder-created object fresh.
`python_syntax_worker.main() -> int` is the stdlib-only framed protocol entrypoint;
it never imports Scanipy or invokes a source path. Worker fixed resource constants
are independently checked against the parent's observations, not imported from
application code that could defeat isolation.

`analysis.ifds.bound_rules` owns QualifiedRuleKey (the resolver imports this
shared semantic key, not a divergent copy), ScalarLimits, BoundRule and
CompiledRuleEffects:

```text
decode_bound_rule(rule_bytes: bytes, model_bytes: bytes, *,
                  key: QualifiedRuleKey, language: str,
                  limits: ScalarLimits) -> BoundRule
compile_bound_rule(rule: BoundRule, projection: SemanticProjection, *,
                   limits: ScalarLimits) -> CompiledRuleEffects
decode_qualified_rule_key(data: bytes) -> QualifiedRuleKey
encode_qualified_rule_key(key: QualifiedRuleKey) -> bytes
```

BoundRule retains original bytes/ordinals, decoded closed schemas and key.
Its exact fields are `key`, `rule_bytes`, `model_bytes`, `language`,
`rule_document`, `model_document`; decoded documents use the closed immutable
section-9 schemas, not mutable JSON dicts exposed to callers.
The key codec implements section 4.1's exact closed metadata as canonical UTF-8
JSON, maximum 16 KiB/depth 4/64 JSON values; no coercion/duplicates/extra keys.
The resolver re-exports this SAME key class and delegates to this codec.
CompiledRuleEffects is exactly `{qualified_rule, projection_sha256, origins,
edges, sinks}`. Origins use the SourceOrigin rows above. Each edges row is exactly
`{edge, write_values, generate_origins, propagate_relations, kill_values}`:
edge is a ControlEdgeId and arrays are sorted unique IDs in the indicated value,
origin or relation table. Each control edge has exactly one compiled row.
Each sinks row is exactly `{operation, input, sink_clause_ordinals}` and sorted
by (operation,input); ordinals are the nonempty sorted original matching Sink
indexes. These fixed sets implement section 10's W/G/P/K for this ONE rule;
calls additionally enforce section 11's call/return/control semantics. Writes
and kills affect only facts for this invocation's origins, never zero. Missing
foreign projection/key references or omitted base language flow reject. The
compiler validates projection identity before use. No mutable callback, legacy
DSL interpretation, global model lookup
or cross-rule cache is accepted. To avoid import cycles, source_syntax accepts
ScalarLimits; bound_rules uses type-only projection imports and does not import
source_syntax or the runner at module initialization.

`ScalarLimits` field names, in section-5 table order, are `max_files`,
`max_file_bytes`, `max_source_bytes`, `max_path_bytes`, `max_path_components`,
`max_rule_bytes`, `max_model_bytes`, `max_accepted_bytes`, `max_clauses`,
`max_models`, `max_rule_json_depth`, `max_rule_json_values`, `max_rule_string_bytes`,
`max_cpg_artifact_bytes`, `max_raw_export_bytes`, `max_native_nodes`,
`max_native_edges`, `max_ast_nodes`, `max_ast_depth`, `max_syntax_bytes`,
`max_procedures`, `max_calls`, `max_call_depth`, `max_operations`, `max_values`,
`max_relations`, `max_origins`, `max_facts`, `max_path_states`, `max_incoming`,
`max_summaries`, `max_solver_work`, `max_occurrences`, `max_witness_steps`,
`max_total_witness_steps`, `max_result_bytes`, `max_associations`,
`max_evidence_references`. All are exact positive ints no higher than the stated
ceilings. Fixed parser/process/JSON-wire profile constants are not configurable
ScalarLimits fields; a trusted outer supervisor supplies its fixed envelope.

`analysis.cpg_ingest.semantic_projection` owns all section-12.2 row types and:

```text
project_scalar_flow(sources: tuple[FrozenSourceFile,...],
                    syntax: tuple[SourceSyntaxDocument,...],
                    observed: TypedObservedGraph, rule: BoundRule, *,
                    selection: QuerySelection, limits: ScalarLimits) -> SemanticProjection
serialize_projection(projection: SemanticProjection, *, limits: ScalarLimits) -> bytes
validate_projection(projection: SemanticProjection, *, sources, syntax, observed,
                     rule: BoundRule, limits: ScalarLimits) -> None
```

Here sources/syntax/observed in validation have the identical types from project.
Validation checks actual source/native/model evidence, not merely reference
shape. The module imports the reviewed typed model; it never converts it to
legacy CPG to exploit lossy name/operator matches. QuerySelection is owned here
and implements section 4.2 exactly. No independently claimed unknown template
can register through this API.

`analysis.ifds.semantic_raw` owns all result/proof/failure types above and:

```text
solve_scalar_ir(projection: SemanticProjection, effects: CompiledRuleEffects, *,
                 context: RawExecutionContext, limits: ScalarLimits
                ) -> CompleteSemanticRawResult
serialize_raw_result(result: CompleteSemanticRawResult, *, limits: ScalarLimits) -> bytes
decode_raw_result(data: bytes, *, limits: ScalarLimits) -> CompleteSemanticRawResult
replay_raw_result(result: CompleteSemanticRawResult, *,
                   projection: SemanticProjection, effects: CompiledRuleEffects,
                   context: RawExecutionContext, limits: ScalarLimits) -> None
```

RawExecutionContext has exactly `qualified_rule`, `execution_kind`,
`execution_binding`, `inputs` with the schemas above. Decode validates all closed
wire structure; replay additionally verifies exact expected bindings/projection/
compiled rule and every witness. Neither function is a live authorization check.
solve charges counters before work and returns only after full fixed point,
complete bounded witnesses/replay and successful serialization-size validation.

The production entrypoint in `scripts.run_semantic_core_case` is:

```text
analyze_source_bound(*, source_store: LocalSourceCaptureStore,
                      receipt: CaptureReceipt, expected: ExecutionBinding,
                      resolved: ResolvedQualifiedRule,
                      authority: ExecutionAuthorityReader,
                      cpg_artifact: bytes, expected_cpg_sha256: str,
                      expected_raw_export_sha256: str,
                      selection: QuerySelection, runtime: PythonSyntaxRuntime,
                      evidence: RawExecutionContext, limits: ScalarLimits
                     ) -> CompleteSemanticRawResult
```

Actual imported dependency names, NOT local authority substitutes:

- `services.scan.source_capture.{LocalSourceCaptureStore,CaptureReceipt}`:
  `source_store.verify(receipt) -> Path` rehashes the stored closed capture.
  It does not acquire a lease, authenticate Git or authorize a tenant. The runner
  requires the trusted controller to maintain the exact active capture lease
  and read-only mount; bounded no-follow reads freeze and rehash ALL inventory
  bytes again. This source adapter is new code inside the runner, not a claimed
  existing safe-read API. Receipt scope and capture_id equal expected binding.
- `analysis.cpg_ingest.typed_observed_wire.deserialize_observed_graph` with
  both actual expected artifact/raw-export digests and bounded graph limits;
  its returned type is `analysis.cpg_ingest.typed_observed.TypedObservedGraph`.
- `services.scan.accepted_inputs.models.{ResolvedQualifiedRule,ExecutionBinding,
  ExecutionAuthorityReader,VerifiedQualifiedRule}` and
  `services.scan.accepted_inputs.verify.verify_resolved_qualified_rule`.
  The runner itself calls `verify_resolved_qualified_rule(resolved,
  expected=expected, authority=authority) -> VerifiedQualifiedRule` before
  semantic dispatch. It does not accept a caller-built verified record as a grant.

ResolvedQualifiedRule retains the full bounded AcceptedBundleBytes (framed
spec_bytes, detector_blobs and rule_blobs), original sealed authority and
execution authorization; detector_bytes/rule_bytes/model_bytes are selected
read-only properties. Reverification checks membership in the full bundle, not
just independently hashed selected copies. The authority reader is trusted
server configuration, never source/rule/CLI input or an arbitrary verifier hook.
It exposes read_execution_authority(expected) -> ExecutionVerificationContext,
recheck_execution_authority(expected, context) -> None and its immutable installed
runtime_profile. The verifier obtains fresh installed trust/admission/ledger/live
authority/reference time, uses its bounded worker, then rechecks current fence,
policy and epoch before returning. Missing real reader/ledger/admission support
is authority-unavailable; no permissive production default is supplied.

ExecutionBinding is the resolver's exact closed detector-purpose type: UUIDs
org_id, codebase_id, request_id, capture_id, seal_id, work_item_id, work_attempt_id,
detector_run_id, capture_lease_id, authorization_event_id; positive fencing_token,
nonnegative work_revision; run_input_digest, requested_policy_digest,
attempt_policy_digest, authorization_digest; and canonical UTC-microsecond
lease_expires_at/capture_lease_expires_at. Import its strict codec; do not duplicate
or reinterpret its digest domains. Full authority schemas and current-ledger
checks remain in the resolver contract. An accepted model's bytes do not prove
its scientific soundness, dispatch assumptions or empirical coverage.

The runner compares evidence/context against actual artifacts, verified binding
and retained runtime observations; it never copies caller labels into proof of
freshness. Its CLI is a trusted controller entrypoint, not an arbitrary path/JSON
grant generator. The real source acquisition/native adapter, active leases,
installed authority reader and reviewed isolated supervisor remain explicit
dependencies for a fresh run. Controlled unit/integration tests call pure layers
with diagnostic context and cannot manufacture production acceptance.

## 13. Exact proposed first code subset

Root approved this contract and local implementation of exactly these 18 NEW
files. Actual dependency integration, independent code review, required tests
and canonical merge approval remain mandatory:

```text
docs/bhmea/SOURCE-BOUND-SCALAR-IFDS.md
analysis/cpg_ingest/source_syntax.py
analysis/cpg_ingest/python_syntax_worker.py
analysis/cpg_ingest/semantic_projection.py
analysis/ifds/bound_rules.py
analysis/ifds/semantic_raw.py
scripts/run_semantic_core_case.py
tests/unit/test_source_syntax.py
tests/unit/test_python_syntax_worker.py
tests/unit/test_semantic_projection.py
tests/unit/test_bound_rules.py
tests/unit/test_semantic_raw.py
tests/integration/test_semantic_core_case.py
tests/empirical/test_semantic_g1_real.py
tests/fixtures/semantic_g1/python/shell_flow.py
tests/fixtures/semantic_g1/java/SqlFlow.java
tests/fixtures/semantic_g1/rules.json
tests/fixtures/semantic_g1/operation_models.json
```

`source_syntax.py` consumes the separately owned/reviewed bounded transport;
the 18-file list contains NO transport implementation or shared transport tests.
Its tests cover Python protocol/profile/limit forwarding and failure propagation;
the corpus-owned tests prove the shared concurrent-I/O mechanism. The complete
shared design is root-approved; integrate only its actual reviewed dependency
code/commit. This does not authorize real native execution or an outer sandbox.

The dedicated stdlib-only worker is additional to the initial report's file
proposal because parser process isolation must not import application/site code.
All new ordinary tests need actual unit/integration markers; native empirical
tests remain opt-in until separate run authorization, and skips are not passes.

The following are NOT in this first subset: `tools/joern/export_source_syntax.sc`,
Java syntax implementation tests, existing secure_subprocess/frontend/profile
files, existing solver/DSL/supergraph, snapshot/scan workers, DB/API/store code,
acceptance resolver, source acquisition/custody, Dockerfiles/pins, canonical-v3
implementation, corpus files and remote state. Request explicit scope expansion
before touching them. Do not copy constants/types from an unmerged dependency;
integrate reviewed dependencies through coordinated branch/merge workflow.

## 14. Earliest executable vertical path and dependency gates

1. Finish/review this contract and accepted-input schema seam. Obtain actual
   authorized model acceptance for exact bytes before a non-diagnostic run.
2. Implement Python syntax isolation, association/projection, rules and solver
   together with the thin runner. The milestone output is a nonempty raw semantic
   result, not another standalone observation container.
3. The runner consumes verified capture/authority plus real retained native
   observations. A recorded-artifact diagnostic is explicitly historical replay,
   not fresh parsing. It cannot label cached/raw fixture bytes as a fresh run.
4. Integrate the reviewed actual raw-v2 native capture adapter and its safe
   invocation/runtime evidence. No new arbitrary Joern command or Git route is
   authorized by the runner. Request separate bounded native-run authorization.
5. Run the exact Python example freshly, retain real source/native associations,
   nonempty witness and negative controls. Fail honestly on unsupported lowering.
6. Implement/review the Java syntax/runtime extension separately, then perform
   equivalent real Java evidence. Do not guess classpath/JDK/launcher flags.
7. Root integrates actual raw retention, semantic-v3 identity and the canonical
   core output boundary. Only then perform independent fresh reruns and G1's
   persisted nonempty core/oracle/provenance checks. G1 is scoped, never full G2.

Code-only/model-only tests and a working historical replay establish component
evidence, not real source authentication or fresh G1 acceptance. The full submitted
goal requires the final executable deployed workflow, not just these libraries.

## 15. Mandatory tests and falsifiers

- [ ] Invalid types, bool-as-integer, unknown/duplicate fields, unknown versions,
  stale/wrong accepted bytes and unresolved model digests reject before solving.
- [ ] Source mutation, stale syntax, wrong CPG artifact, mismatched capture/scope,
  missing/extra file and self-declared source digests cannot establish association.
- [ ] Parser worker isolates imports/cwd/env/bytecode; no target import/eval/exec;
  hostile syntax has no side effects. Exercise syntax error, malformed response,
  zero-exit missing response, signal, timeout, output flood, short input, trailing
  input, all limits, Unicode/CRLF offsets and non-UTF-8/NUL rejection.
- [ ] Exact worker frame/JSON/field types and node-parent consistency reject
  duplicate/missing/unknown fields, out-of-order/dangling/cyclic AST references,
  unexpected child kinds, false getrlimit/parser observations, partial locations,
  mid-codepoint offsets and extra stdout. bytes/complex/Ellipsis/float/huge-int
  constants fail explicitly. Test exact cap/cap+1 and cumulative child output.
- [ ] Raw codecs reject wrong rule/capture/ordinal/port, forged generation,
  zero findings, killed-fact identity, mismatched edge/relation, wrong-caller
  return and bypass with only exceptional/unreachable callee control. Reused
  summaries at two call sites instantiate the correct caller-relative proof.
- [ ] Shared proof references cannot hide cycles/exponential witness expansion;
  count every expansion before work. Valid-path-only replay is not mislabeled
  complete-inventory verification. Missing manifest/authority/real process
  observations cannot promote diagnostic or historical output to fresh-native.
- [ ] Actual parser child limit setup is observed and enforced; no fallback when
  unavailable. Test bounded simultaneous stdin/stdout/stderr and child reaping.
- [ ] Duplicate FQNs/native IDs cannot choose an arbitrary helper. Missing,
  ambiguous or structurally contradictory association fails; pinned lowering
  templates retain every accounted native observation and unsupported states.
- [ ] Distinct lexical bindings/definitions remain distinct; read-before-write,
  shadowed built-ins/os/helper, unknown dynamic calls and unsupported syntax reject.
- [ ] Correct actual/formal, both operator operands, return/result and sink-port
  edges are all necessary: delete/swap/change each and observe the correct failure
  or changed modeled result. A constant helper return yields no finding.
- [ ] A tainted unused local cannot taint a clean sink argument. A tainted first
  call cannot contaminate a clean second call through a mismatched return.
- [ ] Two source clauses retain two origins/ordinals; overlapping sink clauses
  retain evidence without invented rules; distinct sink ports remain distinct.
- [ ] Two accepted qualified rules with the SAME source site and source-clause
  ordinal produce distinct composed keys. One rule's sanitizer cannot change
  the other's facts or result; same textual rule_id from different artifacts/
  detectors cannot collide. Missing/failed/unattempted rules cannot earn composite
  completion or be removed from the required denominator.
- [ ] A 17-file capture fails even with one selected Python file; metadata and
  excluded binary/non-Python bytes count. Missing/extra/unaccounted files, Python
  files relabeled metadata and unresolved excluded imports fail. Selected-query
  completion never becomes whole-repository completeness.
- [ ] New/old summary arrival order produces the same complete fixed point;
  waiting callers are revisited. Unreachable source points do not generate facts.
- [ ] Two selected entry procedures with a local call into either selected entry
  reject before compilation/solving, including a clean actual passed to the
  source-modeled entry and a call from an otherwise unreachable declaration.
  Two independent selected entries without such calls retain separate origins;
  query-root activation cannot leak through a reused zero-context summary.
- [ ] Zero always preserves reachable control, is never killed/generated from a
  nonzero fact, and is never a reported origin. A non-returning callee cannot
  produce a normal continuation. No caller fact becomes an arbitrary result.
- [ ] Sanitizer plus unrelated identity/source/propagate cannot restore the
  sanitized position. Sanitizing a result leaves its input tainted. Contradictory
  source/kill contracts reject; ambiguous aliases cannot enable strong updates.
- [ ] Algebraic distributivity tests plus explicit semantic counterexamples;
  clause ordering cannot reintroduce killed facts. Keep old DSL tests unchanged.
- [ ] Exact work/admission/output N-1/N/N+1 controls, shared proof-DAG bounds,
  witness replay and fail-before-completed-prefix behavior.
- [ ] Patch every forbidden legacy/canonical/fingerprint entrypoint to fail;
  raw success must not call it. Result carries real source/accepted/runtime
  evidence but no invented canonical hash or semantic-completeness claim.
- [ ] First implementation rejects Java execution while retaining its diagnostic
  fixture/model bytes. No implicit Python/legacy fallback.
- [ ] Approved fresh native runs inspect actual nonempty witnesses, complete
  selected scope and constant/clean negatives. Keep replay/fixture evidence apart.
- [ ] Later durable/v3 integration preserves raw detections on identity failure;
  two fresh runs compare the contracted canonical bytes; perturbed output fails.

## 16. Full corpus and R19 obligations remain unchanged

The corrected manifest remains 422 cases: 370 structural comparisons (270 stay,
100 flip), 50 actual finding-removal cases and 2 intentional parser failures.
Do not change its manifest/digests, omit hard cases or count parser failures as
fixes. Exact inventory/locked content remains authoritative in
`tests/corpora/refactor/case-manifest.json` and its SCHEMA.md.

Complete inventory by transformation family:

- 50 each: bound-local alpha rename, formatting, independent reordering,
  physical file/package move, genuine multi-operand pure extraction,
  aliasing-changing extraction, and genuine finding removal (350 total).
- 38 structural genuine-fix comparisons.
- In EACH language and EACH of injection/path-traversal/SSRF/deserialization:
  genuine inline, combined extract/rename/relocate, semantic literal change
  (24 controls total).
- In EACH language: argument-position change, helper-return change, two separate
  sink sites in a two-call chain, intentional parser failure (10 controls total).

For each language the required class/evidence counts are: injection 56 structural,
7 removal and 1 parser failure; path-traversal 45 structural and 6 removal;
SSRF 45 structural and 6 removal; deserialization 39 structural and 6 removal.
The two new G1 cases do not enter or reduce any of these denominators. Expected
purity in the manifest is an expectation, not observed proof.
Their exact source-file entry selectors are scope bindings for these diagnostic
queries, not location-independent source models or evidence of file-move
invariance. Full refactor delivery must supply the appropriate stable production
source/API binding and cannot change S/model bytes to manufacture equality.

Still mandatory beyond this narrow profile:

- [ ] Genuine Java/Python source-to-helper-to-return-to-sink AND helper-containing-
  sink connectivity through exporter, typed model, solver, slice and workflow.
- [ ] Named/default/star/receiver actual/formal binding; Java overloads and
  unresolved signatures; dynamic/virtual target handling; parameter/return types.
- [ ] Instance fields, constructor/factory propagation (including corpus JDBC
  Connection/Statement and SQLite receiver reasoning), aliases, heap/access paths,
  return objects, effects, exceptions and source-visible control/evaluation order.
- [ ] Preserve parallel dependence payloads, semantic metadata and ownership;
  source supplement ambiguity remains explicit rather than invented completeness.
- [ ] Changed callee, argument, return, alias/effect and ambiguous-target controls
  affect the real witness/slice. Native edge count/name membership is insufficient.
- [ ] Binding-aware alpha normalization; exact semantic-v3 graph/slice encoding;
  property/literal/operand distinction and real namespace/history migration.
- [ ] R02 extraction/inline purity certificates based on real effect/alias/type
  evidence, including exceptions and evaluation order. Unknown purity cannot
  inherit suppression. Do not normalize all short helpers merely by syntax.
- [ ] Full R06 invariances and real fix/removal validation over every required
  pair; accepted gate policy, observed preconditions and protected nonregression.
- [ ] R16 safe native source handling, complete per-file coverage and runtime
  identity; R09 artifact classes/provenance; R20 timing/output behavior; actual
  retention/worker/attestation integration and fresh-run failure controls.
- [ ] Version changed model/environment/spec semantics, invalidate any selected
  caches, preserve legacy verification, and keep acceptance runs genuinely fresh.
- [ ] CMP-CP-06 fidelity evidence before Algorithm 2 benchmarking; no recall or
  full-language support inferred from these diagnostics. Complete all C01–C18,
  remaining R01–R20 and G0/G1/G2/G3 requirements in the active review.

## 17. Source evidence and open review actions

Local evidence: corrected seed-001/002 pure-extract sources contain a real
three-operand helper result used by the sink; shipped injection sources target
HTTP/Flask calls rather than those entry parameters. Python's cursor annotation
does not prove instance dispatch. Retained raw-v2 Java observations include
duplicate unresolved helper FQNs and an incorrect overload candidate. The legacy
supergraph's FQN dictionary and exact operator-string matcher are not reused.
The sanitizer table above was reproduced locally using the actual flow builders
over three facts; each composed function still passed that bounded proof check.

Primary upstream sources retrieved read-only on 2026-09-25, Joern commit
`cf59a329bf83063c096e1e803d608e5057d8bb95`:

- [Java frontend build dependency](https://github.com/joernio/joern/blob/cf59a329bf83063c096e1e803d608e5057d8bb95/joern-cli/frontends/javasrc2cpg/build.sbt):
  SHA256 `a8152436781a536ceb9e3651a6b92e17f2a89044bfe226ca78c0a80f979aa87b`.
- [Pinned version declarations](https://github.com/joernio/joern/blob/cf59a329bf83063c096e1e803d608e5057d8bb95/project/Versions.scala):
  JavaParser 3.28.0; SHA256
  `770b092cc3396b6b6f8a9b6c174fc5f62ea25e37a0739d8aa323f31f6bcab1a9`.
- [SourceParser](https://github.com/joernio/joern/blob/cf59a329bf83063c096e1e803d608e5057d8bb95/joern-cli/frontends/javasrc2cpg/src/main/scala/io/joern/javasrc2cpg/util/SourceParser.scala):
  current JAVA_25 configuration/token storage; SHA256
  `f0e88556c077eb2f9470965ffb9c72aec79832449a6ccd61756f1cbc907b88cd`.
- [Python 3.11 AST](https://docs.python.org/3.11/library/ast.html): parser API and
  UTF-8 column-offset semantics. [os.system](https://docs.python.org/3.11/library/os.html#os.system):
  standard-library shell behavior, not proof of a particular target runtime.

Bundled dependency declarations/on-disk hashes do not attest loaded classes,
launcher acceptance, source fidelity or an executed Java parser. No new library,
image build, release, native probe or target program execution was performed.

Reviewed design decisions and remaining implementation/acceptance gates:

- [x] Root reviewed the exact Python subset, strict rejection behavior and
  18-file list; Java implementation stays separate.
- [x] Cross-reviewed exact rule/model JSON schema and accepted-resolver immutable
  return seam, including S_version, model bytes and the required authority proof.
- [x] Reviewed the DESIGN for parser/process limits, OS/runtime enforcement,
  closed environment, source/artifact association trust and failure propagation.
  Actual runtime enforcement is not established by this design review.
- [x] Reviewed value identities, zero semantics, source generation, continuation
  gating, summary joins, termination and work accounting; added the selected-entry
  local-call prohibition before authorizing implementation.
- [ ] Obtain appropriate independent INV-3/INV-4/security review of implementation
  and falsifiers, normal hooks, exact-head CI and canonical APPROVE before merge.
- [ ] Record actual model acceptance separately before a real producer run; a
  successful PR review or this document's approval is not that event.

No item above is marked complete merely by writing this contract.
