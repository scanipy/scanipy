# Bounded process evidence and runtime call journal — proposed codec contract

Tracking: #400, under DECISION-BHMEA-01. Owner: root coordinator; this draft is
the schema/ingestion agent's allocated documentation slice. Root approved the
operation, intent/result and loss-marker design for documentation on 2026-09-25.
Root and independent review approved the pure codec design on 2026-09-25 after
the three final corrections recorded below. Implementation verification and
remote gates remain required. The future store still needs its own complete
design review. No codec, store, journal or controller is enabled by this
document. No operational identity, installation or launch is authorized.

## 1. Scope and existing dependencies

Use the actual classes in `tools.worker.bounded_process`:
`FrozenInvocation`, `ProcessOutcome`, `StreamEvidence`, `MemoryOutput`,
`SpoolOutput`, `ProcessValidationError` and `ProcessTransportError`. Do not add
a competing process transport or a `ProcessInvocation` lookalike. The reviewed
transport retains optional/partial evidence; serialization must not upgrade it.
See [BOUNDED-PROCESS.md](BOUNDED-PROCESS.md).

Repository inspection found `CallRef`, `CliOperation` and the launch-event
grammar only in [LOCAL-RUNTIME-PROFILE.md](LOCAL-RUNTIME-PROFILE.md), not in an
implemented Python journal or consumer. These are prospective schema changes,
not reinterpretations of existing signed findings, DB rows or running jobs.

The first slice is pure preparation/decoding of immutable bounded evidence.
It performs no filesystem, clock, process, network, authority or journal calls.
Prepared bytes/references are not durable until a separate actual store writes,
fsyncs and reads them back. A hash or dataclass never supplies that guarantee.

All process fields describe the **host Docker client**. They do not describe
the container init, bootstrap or inner Python worker. Container identity, exit,
kernel observations and inner protocol validation remain separate records.
Docker-client stderr can include client diagnostics as well as relayed worker
stderr; it is not labeled pure inner stderr.

## 2. Canonical storage domain and bounds

`H` is exactly 64 lowercase hexadecimal characters denoting SHA256 of the
referenced **raw bytes**. A `BlobRef` is exactly
`{sha256:H,size:int,key:"blobs/"+H}`. It selects only the bound attempt's private
blob namespace, never a user path or URI. No blob includes its own hash/ref.
Size is an exact integer0..33554432, with the stricter role-specific limits
below: invocation1 MiB, result32 KiB, error8 KiB, path4096 bytes and each stream
readback16 MiB. A zero-size blob still has SHA256(empty), never a zero hash.

Canonical JSON is UTF-8, sorted exact object keys, no whitespace, no ASCII
escaping of ordinary Unicode and shortest ordinary decimal signed-64-bit
integers. Values are Unicode scalar strings excluding U+0000, exact integers,
booleans, null, arrays and closed objects. Reject duplicate/unknown keys,
floats/nonfinite values, coercion, lone surrogates, NUL and noncanonical bytes
before accepting a decoded document. Booleans are not integers. Decode and
re-encode equality uses the original retained bytes, not normalized replacements.
Raw stream bytes remain unrestricted binary within their byte limits.

Preflight character length, depth, queued plus processed value counts and
aggregate escaped UTF-8 size **before** recursive expansion/JSON encoding.
Use exact builtins and class-owned primitive snapshots; no `asdict`, arbitrary
Mapping/iterator, encoder callback, instance validation method, `repr` or `str`
on a caller-owned record/error/path. Length checks precede UTF-8 allocation.

Counting is explicit: the root object/array has containment depth1. A nested
object/array increases that depth by one; a scalar leaf does not add depth.
Every value, including each container/scalar, consumes one value slot, and
every object member **key** consumes an additional slot. The same convention
applies to JSON bytes and immutable prepared/stored values; reserved footer
slots use it too. Keys are not free work hidden outside the value budget.

Before generic JSON parsing/allocation, a bounded linear lexical guard scans
the original byte-capped UTF-8 input, respects string/escape boundaries and
checks container depth, value/key counts and integer-token bounds. Integer
tokens have at most19 decimal digits excluding a minus; compare a bounded token
lexically to9223372036854775807 or negative magnitude9223372036854775808 before
integer conversion. Reject out-of-range/overlong tokens, floats and nonfinite
forms before a generic decoder can allocate their values. Do not use an
arbitrary parser callback. This preflight does not replace duplicate detection,
full JSON syntax, Unicode, exact canonical-byte equality or role-specific checks.

| Record | Encoded-byte maximum | Depth / JSON-value maximum |
|---|---:|---:|
| Invocation blob | 1048576 | 4 / 2048 |
| Intent payload, result payload or CallRef | 2048 | 4 / 64 |
| Runtime call-result blob | 32768 | 8 / 512 |
| Lossy error graph | 8192 | 8 / 1024 |
| Diagnostic spool-path blob | 4096 | Not JSON: exact validated UTF-8 |

The invocation bound accommodates the shared transport's escaping amplification;
it does not expand the runtime profile. Invocation/error/path/result metadata,
intent/result journal events and all other attempt summaries share the existing
**512 KiB metadata** ceiling. All metadata/raw input/output/installed inventories
share the existing **32 MiB total evidence** ceiling. Non-attached output still
shares its 4 MiB ceiling; kernel raw bytes still share their 1 MiB ceiling.
No new allowance is created by storing a reference instead of its bytes.

A prepared single call is bounded by 512 KiB metadata and 32 MiB total bytes;
the actual store must additionally enforce the **remaining cumulative** attempt
budget. Content-address deduplication saves **retained total storage only**:
unique bytes may count once toward the32 MiB physical-evidence reservation.
It does not discount the512 KiB cumulative metadata workload, a call slot,
role-specific limits or cumulative observed/retained non-attached output work.
Charge each actual call/stream occurrence even when its bytes/hash are identical
to a preceding one. Record observed and retained byte counts separately; never
subtract duplicate content from either counter. A failed over-limit observation
remains accurate in its record, not clamped to make the quota appear satisfied.
The initial runtime profiles cannot retain a generic 129 MiB Git spool; that
requires a separately reviewed profile, not truncation disguised as completeness.

Before launch, reserve the intent plus the maximum required result/error/terminal
and cleanup evidence, as well as remaining cleanup command slots. A preflight
cannot consume all quota and leave cleanup unrecordable. The installed store's
reservation is an actual accounting operation, not an `accepted=true` field.
If reservation cannot be made, do not call the transport. If actual retention
later fails, refuse result admission and preserve the live original failure;
never replace missing evidence with an empty successful result.

## 3. One operation enum and exact call binding

Define `CliOperation` once in the future `tools.worker.process_evidence` module.
Controller, journal codecs and evidence readers import that exact enum. It has
only these ten members/wire values:

| Member | Wire value | Required intended target |
|---|---|---|
| `DAEMON_VERSION` | `daemon-version` | null |
| `DAEMON_INFO` | `daemon-info` | null |
| `IMAGE_INSPECT` | `image-inspect` | Exact installed `sha256:` + 64-hex config ID |
| `CONTAINER_CREATE` | `container-create` | Exact derived `scanipy-runtime-` + attempt UUID hex |
| `CONTAINER_INSPECT_ID` | `container-inspect-id` | Exact owned full 64-hex container ID |
| `CONTAINER_INSPECT_NAME` | `container-inspect-name` | Exact derived attempt name, recovery only |
| `CONTAINER_START_ATTACHED` | `container-start-attached` | Exact owned full container ID |
| `CONTAINER_KILL` | `container-kill` | Exact owned full container ID; fixed KILL operation |
| `CONTAINER_WAIT` | `container-wait` | Exact owned full container ID |
| `CONTAINER_REMOVE` | `container-remove` | Exact owned full container ID; non-forced |

Both permitted purposes use this same closed set. Their memory/input/output and
authority distinctions come from the actual installed profile, not another enum.
Target pins and purpose must belong to the same actual attempt header referenced
by the intent event: image target equals that header's expected config ID, name
equals its derived attempt name, and ID targets require its corroborated owned
container. The isolated payload decoder checks target syntax only; preparation
can check its binding's derived name, while the actual store/controller performs
the cross-header/pin/ownership checks. Binding does not duplicate purpose or
claim an unrelated installed profile from a matching image hash.
No stop, logs, list, prune, exec, shell, wildcard, arbitrary signal or fallback
operation is added. Exact argv for operations other than the already approved
create/start grammar remains a separate renderer/validator prerequisite; this
enum does not infer semantics from an arbitrary argv string.

Use a plain enum with a class-owned fixed identity-to-literal table. Do not
format a poisoned enum's `.name`, `.value`, hash or string conversion. Reject
unknown objects/subclasses, and map decoded exact literals to the same members.

`RuntimeCallBinding` is an exact frozen/slotted, non-content-repr record:

```text
attempt_id: canonical lowercase hyphenated UUID string
operation_id: canonical lowercase hyphenated UUID string
call_id: canonical lowercase hyphenated UUID string
call_sequence: exact integer 1..16
operation: exact CliOperation member
target: exact string satisfying the operation row, or null as required
```

`operation_id` is the parent domain request's UUID, not the CLI-operation enum.
`call_id` identifies one attempted transport call, never an execution permit.
`call_sequence` consumes one of the attempt's sixteen slots even if validation
or launch fails. The controller allocates IDs and the next ordinal through its
serialized actual journal before invoking a fixed internal operation branch.
The branch supplies a constant enum and a target derived from current installed
pins or corroborated owned-container state. Source/rule/API inputs cannot select
an operation, target, callback or substitute journal instance.

The codec checks only structure and internal agreement. The installed factory
and controller prove the supplied values belong to the current attempt. In
particular, matching an enum/ID/name does not prove container ownership.
Name recovery is allowed only after the same attempt's unmatched/ambiguous
create intent, and must corroborate retained complete intent and actual labels,
image/configuration before adopting its returned ID.

## 4. Two journal variants and acyclic persistence order

Add these two kinds to the existing `scanipy-local-runtime-event/1` grammar.
They use its full validated attempt header, sequence, previous-event digest,
timestamp and actual boot/installation facts. Their complete events have a
stricter 8192-byte maximum, charged to the same aggregate metadata budget.

```text
kind:"call-intent"
payload:{call_id:UUID,call_sequence:int,operation:CliOperation,target:string|null,
         invocation:BlobRef}

kind:"call-result"
payload:{intent_event_digest:H,call:CallRef}

CallRef={call_id:UUID,operation:CliOperation,outcome:BlobRef}
```

Required order:

1. Freeze/validate the intended actual shared `FrozenInvocation` and call
   binding. Pure preparation produces canonical invocation bytes and payload.
2. Store the invocation blob, read it back and verify raw hash/size. Append the
   intent event exclusively; fsync the file/directory and read it back. Only
   the returned actual durable event digest may bind the later result.
3. Invoke the actual transport once. The stored invocation remains **requested**
   until compared with a separately observed outcome's frozen invocation.
4. Prepare and retain actual stream/invocation/error/result blobs, including
   mismatches and partial facts. Verify their bytes before making them reachable
   as a successful durable call-result append.
5. Append/read back the call-result event. Its CallRef points to the result blob,
   which points backwards to the intent digest and requested invocation. The
   result blob contains neither its own hash nor the later result-event digest.

These references form an acyclic graph. Event chaining retains the existing
domain-separated event digest; blob references use raw SHA256, not that event
formula. Neither kind creates a signature, grant or new evidence authority.

Per attempt, enforce unique call ID and ordinal, exactly one intent per pair,
and at most one result for that intent. A byte-identical retry of an append is
idempotent; a changed replay fails. Never execute the transport again under an
existing call ID. Results may complete out of ordinal order: the attached start
is still running while the controller makes inspection calls. The journal
serializes actual appends without inventing a transport completion order.

An unresolved/hung transport gets **no fabricated result**. Its durable unmatched
intent and failed/orphaned attempt remain possibly executed, including after
restart. A transport that actually returns an exception without an outcome can
have the explicit unavailable-result variant below. A still-live thread is not
such a returned exception. Later recovery may retain one genuinely obtained
result; it cannot rewrite an earlier result or turn intent into observed output.

`started.start_call_id` references the preceding start **intent**, because its
attached call need not have returned. Other CallRefs reference preceding
same-attempt call-result events with matching enum/ID. Preserve these refinements
to operational payloads:

- `loaded.daemon_raw` becomes `daemon_calls:[CallRef x2]`, version then info.
- `created.inspect` becomes `inspect_call:CallRef` for exact-ID inspect.
- `observed.inspect` becomes `inspect_call:CallRef` for exact-ID inspect.
- `domain-exited.container_inspect` becomes `container_inspect_call:CallRef`.
- `cleanup.final_inspect` becomes `final_inspect_call:CallRef|null`.

The full raw inspect response remains reachable through that call's actual
stdout evidence. Image/name-recovery inspections likewise have mandatory
call-result events even if no extra semantic event references them. An absent
post-removal inspect is null, not a manufactured empty response. Semantic
validators still decide whether a retained result actually satisfies its phase.

## 5. Exact stored invocation/result and stream views

Invocation blob:

```text
{schema:"scanipy-process-invocation/1",argv:[string,...],
 environment:[[name,value],...],cwd:string,stdin_bytes:int,stdin_sha256:H}
```

Preserve actual shared bounds: 1..256 argv entries, each <=8192 UTF-8 bytes,
sum(length+1)<=65536; <=64 sorted unique environment pairs, names <=128 bytes
and nonempty/no equals, values <=8192, aggregate <=65536; cwd <=4096 satisfying
the shared nonroot absolute POSIX-path validation; stdin size0..4194304. Preserve
the actual cwd's exact text rather than replacing it with a normalized spelling.
Initial Docker intents additionally require normalized paths and
have the exact ten-variable environment and stricter 16384-byte environment
budget from the installed profile. Do not silently apply that intended policy
to erase a mismatching **actual** invocation. Retain a structurally valid shared
invocation mismatch and fail domain admission independently.

For `prepare_call_intent` only, the normalized cwd ends in slash plus the
binding's canonical attempt UUID, with a nonroot normalized parent as the
intended host work root. Derive HOME/TMPDIR/PATH as cwd plus cli-home/cli-tmp/
cli-bin and require the exact ten fixed host environment rows from the outer
profile, including every derived path's byte cap. This is internal consistency,
not proof that a directory, empty PATH, trusted root or installed CLI exists.
The standalone invocation codec and actual-outcome snapshot retain the wider
shared model. Full argv/executable/configuration agreement remains a separate
actual renderer/controller check, not inferred from the enum or environment.

The shared `FrozenInvocation` does not distinguish `stdin=None` from `b""`:
both have size zero and SHA256(empty). Do not invent a requested-input-mode bit.
An intended zero input is not observed EOF or proof a child consumed nothing.

Runtime result blob:

```text
{schema:"scanipy-runtime-call/1",scope:"host-docker-client",
 attempt_id:UUID,operation_id:UUID,call_id:UUID,call_sequence:int,
 operation:CliOperation,target:string|null,intent_event_digest:H,
 requested_invocation:BlobRef,
 outcome:StoredOutcome|null,
 unavailable_reason:null|"validation-refused"|"exception-no-outcome",
 error_id:UUID|null,error_graph:BlobRef|null}

StoredOutcome={invocation:BlobRef,reason:Reason,pid:int|null,pgid:int|null,
 returncode:int|null,stdin_sent_bytes:int,stdout:StoredOutput|null,
 stderr:StoredOutput|null,elapsed_ms:int,cleanup:Cleanup}

StoredOutput={kind:"memory"|"spool",reported:StoredStreamEvidence,
 path:BlobRef|null,custody:Custody}

StoredStreamEvidence={observed_bytes:int,retained_bytes:int|null,
 retained_sha256:H|null,eof:bool,truncated:bool}

Custody={state:"verified"|"unavailable"|"mismatch"|"diagnostic-copy",
 bytes:BlobRef|null}
```

`Reason` and `Cleanup` are exactly the actual shared model's closed literals,
not translated success/failure labels. All numeric values are exact integers;
PID/PGID/returncode and stream bounds mirror the actual shared classes. Elapsed
is a nonnegative signed-64-bit integer, never a reconstructed inner duration.
Validate the shared cross-field invariants independently from class-owned
snapshots; constructors are not trusted after mutation.

The pure stored-result decoder validates all locally available fields but does
not open its invocation BlobRef. Checking stdin_sent_bytes against the referenced
invocation's stdin_bytes requires future store cross-blob readback; preparation
already enforces that full relation against the actual live invocation snapshot.
No decoder success claims cross-blob integrity or runtime admission.

An observed outcome requires null unavailable_reason. An absent outcome requires
a real returned error and nonnull unavailable_reason/error ID/graph. Use
validation-refused only for an exact actual `ProcessValidationError`; otherwise
use exception-no-outcome. A live unresolved invocation stays an unmatched intent.
`error_id` and graph are paired; an outcome can coexist with a real failure.
The graph has the same error ID. No error-free fabricated absence is accepted.

### 5.1 Selected actual transport-error carrier

`prepare_call_result` uses exactly one bounded carrier-selection rule:

When error is null there is no carrier. For a nonnull root error:

1. If `error` is the **exact** actual ProcessTransportError class, select it.
2. Otherwise read only the root error's immediate explicit `__cause__` through
   the builtin BaseException descriptor. Select it only when its type is the
   exact ProcessTransportError class. This covers the actual shared transport's
   `raise interruption from evidence_error` termination path.
3. Otherwise select no carrier. Never search context, deeper causes or group
   members for current-call transport authority. A directly selected carrier
   takes precedence over any other transport error in its own chain.

This is an internal consistency check, not proof that a caller-constructed
exception came from a real launch. The installed caller still supplies the real
transport observation. For other error shapes, supplied outcome remains
data-only: do not infer a fallback outcome from arbitrary exception graph nodes.

For a selected carrier, use BaseException's builtin `__dict__` descriptor,
not `error.outcome`, an overridden property or arbitrary attribute traversal.
Require an exact builtin dict with2 or3 keys, required `outcome` and
`_owned_child`, and only optional `__notes__`. Snapshot at most4 builtin items
before examining them; concurrent change or an excess item is a typed failure.
Check exact string keys/counts and at most32 ASCII characters per key before
comparison or building a private lookup.
Unknown/missing keys, custom dictionaries and poisoned/missing outcome storage
are fatal preparation errors. Extract only the outcome from the bounded private
snapshot. The `_owned_child` reference is opaque: never inspect, format, hash,
serialize, dispose or call its methods. Optional notes are likewise not traversed
or serialized; genuine builtin notes remain untouched on the live exception.

Independently snapshot and fully validate the carrier's actual outcome and the
supplied `outcome` argument through class-owned bounded primitives. Supplied
outcome must be **nonnull and equal to that complete snapshot**, including all
invocation fields, every reason/PID/returncode/elapsed/cleanup field, optional
stream presence, complete reported evidence, exact memory bytes and safely
snapshotted spool paths. Do not call caller dataclass equality or compare only
hashes/success fields. A missing/invalid/mismatching carrier or supplied outcome
is fatal ProcessEvidenceError, never exception-no-outcome and never silently
replaced by a convenient alternative. Preserve the original live carrier,
primary error, child ownership and chains unchanged for the owning supervisor.

### 5.2 Retention and actual-model distinctions

Preserve these distinctions without coercion:

- Missing output (`null`) is different from a known empty memory stream with
  retained size zero and SHA256(empty). EOF false remains false even at zero.
- A spool's null retained count/hash is an inseparable unknown pair; it is not
  zero. Observed bytes may exceed a retained cap by the transport's detection
  read. Preserve that actual count rather than clamping it.
- `exited`, returncode zero and cleanup incomplete is a valid **failure** record,
  for example after late snapshot/hash/deadline failure. It is not success.
- Timeout/io/stdin-closed reasons can coexist with a reaped returncode and
  cleanup completed. Completed client cleanup is disposal, not domain acceptance.
- One stream can exist while the other is null after independent snapshot loss.
  A truncated prefix is never admitted as the full domain response.
- Cleanup not_started means no acknowledged owned Popen child, not proof that
  no transient fork or partial spool creation occurred.

Memory output has null path; spool output has a nonnull diagnostic path ref.
Memory output retains its exact bytes/hash/size with custody verified, or pure
validation fails: a poisoned memory record is not quietly repaired. For spool
output, `path` is the exact safely snapshotted diagnostic path blob; it is never
a restart read target. The separate store reads only its pre-registered held
spool directory/file identities for the named stream.

Spool custody is computed without modifying reported evidence:

- verified: retained readback bytes exactly match a known reported count/hash.
- unavailable: no readback bytes, bytes ref null; never successful retention.
- mismatch: readback exists but differs from a known reported count/hash.
- diagnostic-copy: readback exists but reported retention is unknown; the copy
  does not retroactively establish the transport's original retention facts.

All mismatches/unknowns remain retained failure diagnostics. A later stored-byte
hash match cannot promote reported EOF/truncation/cleanup or turn a diagnostic
copy into original complete output. The store separately verifies every blob's
own bytes on restart. This is byte custody, not proof of process authenticity.

## 6. Bounded lossy private error graph

The exact original exception objects and their primary/cause/context/cleanup
chains stay private and unchanged in the live process. The wire representation
is explicitly lossy/opaque, not a reconstructed exception or traceback. Never
pickle, call exception methods/properties, format arbitrary error arguments or
publish raw chains in user-facing logs.

Closed graph:

```text
{schema:"scanipy-private-error-graph/1",error_id:UUID,root:0,
 nodes:[{id:int,class:ClassCode,args:[Argument,...],cause:int|null,
         context:int|null,suppress_context:bool,group_children:[int,...]|null},...],
 omissions:[{node:int|null,field:LossField,reason:LossReason},...],
 omission_overflow:null|{additional_details_at_least:1,exact_count:null,
                       enumeration:"incomplete"}}
```

At least1 and at most32 nodes, 96 total cause/context/group edges, traversal
depth16 (root depth0) and32 omission details. Node IDs are contiguous starting
zero; refs name retained nodes only. Traverse depth-first in the fixed order
cause, context, then group children in original array order; inspect a node's
arguments before its outgoing edges. Assign IDs on first discovery. Detect
shared/cyclic identities with bounded builtin integer identity keys, not an
exception's hash/equality method; retain their graph references without recursive
expansion. No fabricated node/ref is used for a missing branch; an omission
explicitly records the loss.

`ClassCode` is one of `base-exception`, `exception`, `runtime-error`,
`value-error`, `type-error`, `attribute-error`, `memory-error`, `eof-error`,
`os-error`, `file-not-found`, `permission-error`, `timeout-error`,
`interrupted-error`, `keyboard-interrupt`, `system-exit`, `exception-group`,
`base-exception-group`, `process-validation`, `process-transport`, `opaque`.
Only exact identity with the corresponding builtin/shared class gets its code;
unknown/custom subclasses are opaque and record class/opaque-type loss unless
the overflow marker has already stopped traversal. Do not read dynamic class
names or notes.

Read cause/context/suppression/args through the builtin `BaseException`
descriptors, and group children through the builtin `BaseExceptionGroup`
descriptor. Do not dispatch a subclass property or instance override. Capture
explicit cause and implicit context separately; suppression remains an actual
boolean. The graph does not rewrite chains or decide which original error wins.
Even a subclass that poisons `.args`, `.exceptions`, `.__cause__`,
`.__context__`, `.__getattribute__` or formatting must not receive a callback:
read the known builtin descriptors directly, not those named instance attributes.

Before iterating arguments, require the descriptor result to be an **exact
builtin tuple** and read its O(1) length. Snapshot at most the first8 entries per
node, further reduced by the remaining32-argument aggregate allowance. An
oversized tuple records an `args/items` omission; never materialize or iterate
the whole original tuple. Unsupported prefix values still consume inspected
argument slots even when their payload is omitted.

For a native BaseExceptionGroup, similarly require an exact tuple from the
builtin children descriptor. Snapshot at most the first32 members and no more
than the remaining96-edge allowance **before** expansion. Record `group/items`
or `group/edges` when the original length exceeds that permitted prefix; never
iterate the remaining children to count or format them. The retained group
array has at most32 members; cause/context and repeated-child edges consume
the same global edge budget. No native group means group_children is null;
an omitted/truncated native group can have an empty array with explicit loss.
Recheck all remaining budgets before admitting each member: earlier depth-first
branches can consume allowance after the initial bounded prefix snapshot.

An Argument is exactly `{kind:"text",value:string}`, `{kind:"bytes",base64:string}`,
`{kind:"int",value:int}`, `{kind:"bool",value:bool}` or `{kind:"null"}`.
Only exact primitive values qualify. Each text/raw-byte argument is <=512 bytes;
binary is canonical RFC4648 padded base64. At most32 arguments and2048 encoded
argument JSON bytes **across the entire graph**. Oversized, nested, callback-
bearing, float or nonportable arguments are omitted, never formatted. The fixed
graph format intentionally excludes traceback frames, arbitrary attributes and
notes; readers must not mistake it for full exception reconstruction.

`LossField` is `class|args|cause|context|group`; `LossReason` is
`opaque-type|unsupported-primitive|bytes|depth|nodes|edges|items`.
Before adding any node/edge/argument/detail, reserve1024 bytes of the8192-byte
graph bound and32 of its1024 JSON values for the fixed footer/closure. Use actual
canonical-byte accounting,
not an estimate that allows a later allocation to exceed the cap.

On the first omission detail that cannot fit (the33rd detail or byte-budget
exhaustion), set the fixed overflow object and **stop graph traversal**. It means
at least one further detail is omitted, with the remaining count unknown. Never
walk further error branches just to count losses, silently drop excess details,
or claim an exact remaining count. Already retained graph data remains valid;
any newly unvisited outgoing refs are null/absent with the aggregate loss marker.
The footer is always affordable because its space was reserved in advance.
Such a null edge is not proof of an absent original cause; readers consult both
per-field omissions and the graph-wide overflow marker before interpreting it.

`decode_error_graph` must perform graph semantics after bounded JSON decoding,
not merely accept a canonical object with familiar keys:

- Require root exactly integer0, a nonempty node array with `nodes[i].id == i`,
  and every cause/context/group reference inside that array. Starting at0,
  traverse cause, context, then group children in retained order, skipping
  recursion on already seen IDs. All nodes must be reachable, and their first-
  discovery sequence must be exactly0,1,...,N-1; reject reordered or orphan nodes.
- Enforce retained first-discovery depth<=16, <=96 total retained edges
  (including repeated/back references), <=32 members per group, <=8 retained
  arguments per node and<=32 in total. Verify the aggregate2048 encoded argument
  bytes, each primitive/tag/base64 bound and the overall graph byte/value caps.
  Retained validation cannot establish how many original unseen values existed.
- All omission node IDs are null for graph-wide loss or reference retained
  nodes. Validate each closed field/reason pair: class only opaque-type; args
  only unsupported-primitive/bytes/items; cause/context/group only
  depth/nodes/edges/bytes/items. A class/opaque-type omission names an opaque
  node when its node ID is present. Repeated omission records are allowed when
  separate original values lost the same kind of information.
- Exact exception-group/base-exception-group codes require a group array;
  known nongroup codes require null. Opaque can represent either. An empty
  native-group array needs a matching group omission or overflow marker.
  Opaque class loss needs its class omission or the overflow marker. Suppression
  is an exact boolean, but do not invent a cause-presence implication: explicit
  suppression with no cause is a genuine Python state.
- Validate the overflow footer's exact fixed fields/literals, nullable refs
  and all Argument variants; unknown extras/inconsistent tags fail. The marker
  may appear with fewer than32 details because byte/value exhaustion can occur
  first. It signals unknown omitted detail, not proof of an exact unseen count
  or permission to admit malformed retained nodes.

Graph validation never recreates exceptions or assigns live cause/context,
notes, child handles or transport outcomes from stored class labels.

Serialization failure itself is fatal evidence failure. The caller preserves
the original live primary and any new serialization/store/cleanup failure as
private causes/groups; it does not replace the original with a synthetic
success, silently swallow the new failure, or mutate chains in this pure codec.

## 7. Exact proposed pure API and stored/live separation

The proposed module is `tools.worker.process_evidence`. Its four new carrier
records are exact frozen/slotted, non-content-repr data, revalidated at every
public boundary: RuntimeCallBinding, EvidenceBlob, PreparedCallIntent and
PreparedCallResult. Stored JSON views use exact immutable tagged tuples as
defined below, not a parallel hierarchy of process/authority models.
Neither form is an execution grant. `EvidenceBlob` is exactly
`{data:bytes,sha256:bytes32}`; its ref uses raw size/hash. A prepared result has
at most8 unique blobs: requested/actual invocation, two streams, two diagnostic
spool paths, error graph and result. Equal content may share a blob.

```python
def encode_invocation(invocation: FrozenInvocation) -> bytes: ...
def decode_invocation(data: bytes) -> StoredInvocation: ...
def cli_operation_from_wire(value: str) -> CliOperation: ...

def prepare_call_intent(
    binding: RuntimeCallBinding, invocation: FrozenInvocation,
) -> PreparedCallIntent: ...

def prepare_call_result(
    intent: PreparedCallIntent, *, intent_event_digest: bytes,
    outcome: ProcessOutcome | None,
    error_id: str | None, error: BaseException | None,
    spool_readback: tuple[bytes | None, bytes | None] = (None, None),
) -> PreparedCallResult: ...

def decode_call_intent(data: bytes) -> StoredCallIntent: ...
def decode_call_result(data: bytes) -> StoredCallResult: ...
def decode_call_ref(data: bytes) -> StoredCallRef: ...
def decode_error_graph(data: bytes) -> StoredErrorGraph: ...
```

`PreparedCallIntent` contains exactly binding, a privately reconstructed actual
shared `FrozenInvocation`, invocation_blob:EvidenceBlob and payload:bytes.
Its payload is section4's intent payload; duplicate fields must agree exactly.
`PreparedCallResult` contains exactly call_ref:StoredCallRef,
payload:bytes (section4 result payload), and blobs:tuple[EvidenceBlob,...].
The actual event digest input is32 raw bytes, not caller-formatted hex.
Error ID is a canonical UUID string and is paired with the actual error object.

Stored values have exactly this representation; these tags are in-memory only,
not added to the JSON wire:

```text
StoredValue := null | exact bool | exact signed64 int | exact scalar str
               | StoredArray | StoredObject
StoredArray := ("array", exact tuple[StoredValue,...])
StoredObject := ("object", exact tuple[(exact str,StoredValue),...])
```

Object members are unique and sorted by exact UTF-8 key bytes; arrays preserve
order. Reject other tuple lengths/tags/subclasses or mutable containers before
iteration. The validated decoder freezes only these primitives. Every named
Stored* record below is an alias of StoredObject with this **exact closed**
field set and the section2–6 constraints, not an independently constructible
class that certifies validity. An array field is StoredArray; an object field
is its named StoredObject alias, never a mutable dict/list.
These tuples contain private evidence and have ordinary tuple representations;
do not log/format/return them as public summaries. Only the four carrier classes
provide a non-content repr. Fixed error codes remain the public reporting path.

| Alias | Exact fields and in-memory value types |
|---|---|
| StoredBlobRef | sha256:str(H), size:int, key:str(`blobs/`+H) |
| StoredInvocation | schema:str(literal), argv:array[str], environment:array[array[str x2]], cwd:str, stdin_bytes:int, stdin_sha256:str(H) |
| StoredCallIntent | call_id:str(UUID), call_sequence:int, operation:str(wire literal), target:str or null, invocation:StoredBlobRef |
| StoredCallRef | call_id:str(UUID), operation:str(wire literal), outcome:StoredBlobRef |
| StoredCallResult | schema:str(literal), scope:str(`host-docker-client`), attempt_id:str(UUID), operation_id:str(UUID), call_id:str(UUID), call_sequence:int, operation:str(wire literal), target:str or null, intent_event_digest:str(H), requested_invocation:StoredBlobRef, outcome:StoredOutcome or null, unavailable_reason:str(literal) or null, error_id:str(UUID) or null, error_graph:StoredBlobRef or null |
| StoredOutcome | invocation:StoredBlobRef, reason:str(Reason), pid:int or null, pgid:int or null, returncode:int or null, stdin_sent_bytes:int, stdout:StoredOutput or null, stderr:StoredOutput or null, elapsed_ms:int, cleanup:str(Cleanup) |
| StoredOutput | kind:str(`memory` or `spool`), reported:StoredStreamEvidence, path:StoredBlobRef or null, custody:StoredCustody |
| StoredStreamEvidence | observed_bytes:int, retained_bytes:int or null, retained_sha256:str(H) or null, eof:bool, truncated:bool |
| StoredCustody | state:str(`verified`, `unavailable`, `mismatch` or `diagnostic-copy`), bytes:StoredBlobRef or null |
| StoredErrorGraph | schema:str(literal), error_id:str(UUID), root:int(0), nodes:array[StoredErrorNode], omissions:array[StoredOmission], omission_overflow:StoredOmissionOverflow or null |
| StoredErrorNode | id:int, class:str(ClassCode), args:array[StoredArgument], cause:int or null, context:int or null, suppress_context:bool, group_children:array[int] or null |
| StoredArgument | Exactly one closed variant: `{kind:str("text"),value:str}`; `{kind:str("bytes"),base64:str}`; `{kind:str("int"),value:int}`; `{kind:str("bool"),value:bool}`; or `{kind:str("null")}` |
| StoredOmission | node:int or null, field:str(LossField), reason:str(LossReason) |
| StoredOmissionOverflow | additional_details_at_least:int(1), exact_count:null, enumeration:str(`incomplete`) |

All UUIDs/digests in stored views remain canonical **strings**, not UUID/bytes
objects. All state/kind/Reason/Cleanup/ClassCode/LossField/LossReason fields are
the exact closed **strings** specified above, not new Python enum types.
Stored operation strings are validated using the one CliOperation identity
table; `cli_operation_from_wire` maps an exact supported string to that same
enum for an internal controller/journal consumer. Only RuntimeCallBinding has
an actual CliOperation field. This is one enum, not duplicated parser/consumer
registries. StreamName in the future store signature is exactly the string
literal type `stdout|stderr`, not another enum or a path.

`spool_readback` is exactly a two-element tuple, stdout then stderr. Each element
is exact bytes <=16 MiB or null. Nonnull entries are allowed only for the matching
actual SpoolOutput. Memory bytes come only from the independently snapshotted
MemoryOutput. The trusted store supplies spool readback from registered held
objects; the pure API checks internal consistency but does not authenticate
where caller-provided bytes came from. Never invoke a callback or open the
SpoolOutput's caller-owned path. A path snapshot uses bounded primitive CPython
3.11/3.12 layouts as in the actual reviewed transport, ignoring cached strings;
unsupported storage/layout fails before formatting.

These exact stored views are produced only after the relevant schema validation;
their tuple shape/type alias alone does not authenticate a caller-built value.
Decode never returns/revives a
live ProcessOutcome, Path, exception, Popen object or authority token. It does not
open a BlobRef. The later store performs cross-blob/hash/intent/event readback
and returns these views with separately established byte-integrity status.

All nested actual shared records are snapshotted through class-owned fields
before hashing/formatting. Reject poisoned dictionaries, extra/missing fields,
subclasses and mutable/custom aliases; do not call their instance methods.
The returned stored/transport class name cannot substitute for revalidation.
Fixed `ProcessEvidenceError` messages contain no raw inputs or secret paths;
original causes remain private. No implicit in-process/diagnostic fallback is
added to a production controller.

Unit tests may exercise operational-syntax bytes as isolated codec test vectors;
they must not publish those vectors as an actual operational journal with
invented run/authority facts. Actual diagnostic runs require separate diagnostic
artifact domains/store roots, as the profile already requires. A test outcome
for an ordinary trusted Python child is not relabeled as an observed Docker
client merely because this codec can encode its shared fields.

## 8. Separate future durable store boundary

This is **not** part of the first pure codec allocation. A future concrete
`tools.worker.runtime_evidence.RuntimeEvidenceStore` is bound by the installed
controller to one actual private attempt journal and its quota reservation.
Source/API inputs cannot supply that instance or its root/clock/append callback.
Its proposed methods are:

```python
def append_call_intent(self, prepared: PreparedCallIntent) -> DurableCallIntent: ...
def collect_spool(self, intent: DurableCallIntent, *, stream: StreamName) -> bytes: ...
def append_call_result(
    self, intent: DurableCallIntent, prepared: PreparedCallResult,
) -> DurableCallResult: ...
def read_call(self, reference: StoredCallRef) -> StoredCallEvidence: ...
def unresolved_calls(self) -> tuple[StoredCallIntent, ...]: ...
```

StreamName is the closed stdout/stderr string literal type, not a path. Durable
receipts bind
the actual attempt, call ID and read-back event digest; they are not authority
tokens, and the store rechecks its own journal when consumed. Journal sequence,
timestamp, boot/context facts, private directory FDs and quota come from actual
bound store/controller state, never prepared-record assertions. The complete
constructor/FD lifecycle/receipt and journal-state schemas need a separate
review before this store's implementation is allocated.

The complete proposed root/attempt handle, held-descriptor publication,
receipt/state/replay, quota, registered-spool and parent-barrier protocol is
in [RUNTIME-EVIDENCE-STORE.md](RUNTIME-EVIDENCE-STORE.md). It remains a separate
design/implementation gate; PE's pure codec checkpoint does not certify any
durable journal or DB/runtime authority. Its root/attempt lifetime distinction
preserves this section's attempt-bound `RuntimeEvidenceStore` name.
Scoped refusal receipts and fixed-ID read/retry, fresh prerequisite evidence
inventories and an irreversible recovery-only boundary are part of that
separate proposal; none is supplied by the pure process codec.
Read-only evidence views certify a complete visible prefix only; actual
durability receipts require the writer's publication/fsync/replay protocol.

Register the exclusive private spool directory identity and fixed filenames
**before** transport launch; do not precreate files that the actual transport
creates with O_EXCL. Observe the actual file identities after creation, and
read only registered stdout.bin/stderr.bin under held private FDs, with
nofollow/nonblocking opens, exact type/owner/mode/nlink/size/identity checks and
bounded read/rechecks. A stored diagnostic path is never reopened on restart.
If spool readback fails, propagate an evidence error with its original cause;
the controller may retain an unavailable/mismatch diagnostic result but cannot
admit success. Collecting a later file copy cannot change original transport
retention/EOF/cleanup fields. Never retry closing an uncertain numeric FD.

Persist blobs exclusively using bounded private temporary files, write/fsync,
readback hash/size, no-replace publication and directory fsync. Existing bytes
must match exactly; a collision/mismatch is failure. Append events atomically
with corresponding exclusive/readback durability and global append ordering.
An acknowledgement failure is ambiguous until reread from the actual journal;
it never permits a second native/CLI execution.

On restart, verify chain/sequence and every referenced byte blob with the same
caps. Derive unmatched calls from actual intent/result records. Never infer
child termination from a result hash or from killing the attached Docker client.
Unknown cleanup retains the outer attempt's orphan/retirement barrier and parent
leases. Only the current controller/factory's separate observations/authority
checks can decide cleanup or domain admission.

## 9. Required falsifiers and allocation gates

- [x] **PE-01:** Root and independent review of this complete document, exact API,
  enum, two journal variants and the targeted profile cross-reference changes.
- [x] **PE-02:** Allocate only tools/worker/process_evidence.py and
  tests/unit/test_process_evidence.py for the pure first slice, using the actual
  reviewed shared models. No storage/launch code in that allocation.
- [x] **PE-03:** N-1/N/N+1 encoding/depth/value/aggregate bounds; duplicate/extras;
  byte-preserving binary/UTF-8; poisoned models/enums/errors/Path/UUID and no
  caller iteration/formatting/property callbacks; unchanged live exception chains.
- [x] **PE-04:** Missing versus empty versus unknown stream retention; independent
  stream loss; late exited-zero/incomplete; completed cleanup on non-success;
  truncated prefix; actual/requested mismatch; malformed partial outcome rejection.
  Direct/explicit-immediate-cause transport carriers must reject missing/different
  supplied outcomes and poisoned storage; context/deeper/group carriers are never
  selected as fallback. Live child handles/notes remain uninspected and unchanged.
- [x] **PE-05:** Error cycles/shared groups, cause/context/suppression, interruptions,
  opaque args,32/33 omission details, byte-budget overflow and fixed footer;
  prove traversal stops without counting unvisited branches or touching callbacks.
  Reject unreachable/reordered/out-of-depth retained graphs and invalid refs,
  group/argument/loss variants; test exact key-inclusive lexical counts and
  signed64 integer-token rejection before generic parsing/allocation.
- [ ] **PE-06:** Separate store/journal review and implementation, including two
  interleaved calls, missing intent, changed replay, wrong attempt/operation/ref,
  mid-append/readback/fsync faults, quota reservation and live-primary retention.
- [ ] **PE-07:** Real private spool custody/restart/FD-race tests and exact pending
  call reconciliation; no reopening diagnostic paths or touching foreign resources.
- [ ] **PE-08:** Actual fixed Docker-operation renderers, effective config/kernel
  observers, bootstrap/controller/factory and mode authority remain prerequisites.
  Normal hooks, exact-head CI/canonical approval and reviewed runtime tests remain
  separate. Neither prepared evidence nor this draft permits a container launch.

### Local design checkpoint

Root read the complete contract, targeted profile delta and actual shared
transport. The independent canonical/budget agent read all 728 pre-checkpoint
contract lines and the complete profile delta, then approved the pure codec
design at source-document SHA256
`49ee7768b085c5f36dd0a1472f9235a29a52932a3835c6585d689d998458f224`
and profile SHA256
`c029aaaacbf81e6f1fbd184660612d030d389d550a4675b6e6e9562437ee1c1b`.
These hashes identify the reviewed pre-checkpoint bytes, not this later
status-only addition. The three resolved findings were actual carrier/outcome
consistency, pre-parse key/depth/integer accounting, and retained error-graph
reachability/DFS semantics. Original live failures and child handles remain
private; the codec is data preparation, not proof of process authenticity.

This is local design approval only. No source, codec, store, migration, keys,
profiles, native process, container or operational event was created by this
documentation slice. The later two-file codec must pass independent code
review, normal hooks and exact-head remote gates; PE-06 onward remain separate.

### Local pure-codec implementation checkpoint — 2026-09-25

PE-02 through PE-05 now have an implemented, locally tested and independently
reviewed pure slice; these ticks are not repository merge, durability or runtime
acceptance. The allocation added only tools/worker/process_evidence.py and
tests/unit/test_process_evidence.py. This document's intent-only path and
cross-blob decoder clarifications preserve the existing outer-profile policy
and actual shared transport evidence; they do not broaden authority.

Root reviewed the complete implementation and tests. Independent corpus/tooling
review approved the corrected slice after finding a loss-record mismatch. Frozen
source SHA256 is
`601fef04b641b28c6f7e3abe948490bd7507287c103194a42b2cc7f943ac0fe8`;
test SHA256 is
`14178e56d736b301715941bebe3da051d8482f5fbb3f0ff7d061b01be844628a`.

Retain both discovered failures and their corrections:

- Root's three intended-path falsifiers initially failed against source
  `f974ad14e99e75e7ff525603b25f3439c7a38eabffbe8708d4e34f72c8277c72`:
  `/tmp/scanipy-process-evidence-root-path-red.xml`. Intended Docker cwd now
  rejects backslash and C0/DEL/C1 characters. Standalone and actual invocation
  evidence still preserves the wider valid shared-model paths unchanged.
- Independent real-byte-budget regression failed against source
  `b023663fa34a6702302d339982feac7c1de830e2fb423f3e087991cbd91b9a0f`:
  `/tmp/scanipy-process-evidence-corpus-loss-red.xml` (one failure). The two
  implementation-owner regressions also failed before the correction:
  `/tmp/scanipy-process-evidence-owner-loss-red.xml` (two failures). Node/edge
  and argument rollback now attempt the smaller per-field bytes-omission record;
  aggregate overflow starts only when an omission detail cannot fit. Existing
  true overflow and traversal-stop controls remain intact.

Final checks on these exact frozen bytes:

- Root: **483 passed**, zero failures/errors/skips, in 3.79 seconds:
  `/tmp/scanipy-process-evidence-root-final.xml`.
- Implementation owner: the same **483 passed** on Python 3.11.16 and 3.12.14:
  `/tmp/scanipy-process-evidence-loss-final-py311.xml` and
  `/tmp/scanipy-process-evidence-loss-corrected-py312.xml`.
- Independent reviewer: **480 passed**, zero failures/errors/skips, in 5.43
  seconds: `/tmp/scanipy-process-evidence-corpus-final.xml`.
- Scoped Ruff, format, strict source mypy and diff checks passed. The final
  483-case selection is 479 repository cases plus three unchanged root path
  falsifiers and the unchanged independent loss falsifier. The reviewer's
  480-case selection omits the three root external cases. These overlapping
  counts and earlier 477/480-case checkpoints are not additive evidence.

These are local controlled records, not a portable immutable acceptance archive.
No filesystem store, journal event, installed profile/key, process launch,
container, kernel observation or authenticated admission was created by the
pure codec tests. Final combined-tree full regression, normal commit/push hooks,
exact-head CI and successful canonical APPROVE remain required. PE-06 through
PE-08, the installed runtime/controller/factory and all full Black Hat acceptance
claims remain open.
