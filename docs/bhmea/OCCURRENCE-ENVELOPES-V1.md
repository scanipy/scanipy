# Occurrence persistence envelopes, version 1

Status: approved implementation contract; implementation/test acceptance pending.
Owner: schema/ingest implementation under #378. Date: 2026-09-25.
Companion to [the persistence schema](OCCURRENCE-PERSISTENCE-SCHEMA.md).
No completed finding, signed-record, SARIF, source-tree or legacy API encoding
changes. This is a storage protocol, not producer authentication or R07/R08
end-to-end acceptance.

## Encoding and size boundary

An envelope is exactly UTF-8 JSON with Unicode-scalar-sorted object keys,
compact separators, literal non-ASCII characters and no trailing newline.
Only null, booleans, signed 64-bit integers, scalar strings excluding U+0000,
arrays and string-keyed objects are supported. Reject duplicate keys at every
depth, lone surrogates, floats, nonfinite values, oversized integers, unknown
fields, alternate escaping/whitespace, and nesting deeper than 32. A bool is
not an integer. SQL validates preserved `json` before conversion to `jsonb` and
reconstructs the same bytes independently; `jsonb::text` is not this encoding.
The NUL/integer restrictions address PostgreSQL/Python portability. They apply
only to envelopes, never to separately retained raw bytes or source contents.

The root `schema` string is the ASCII domain, also retained in a typed column.
Digest = SHA256(ASCII domain + one LF + exact envelope bytes). All content
digest strings in envelopes are 64 lowercase hexadecimal characters, except
the explicitly named environment digests, which retain `sha256:` plus 64 hex.
UUID strings use canonical lowercase hyphenated representation. Operational
UUIDs and database times are not deterministic core output identity.

Every envelope is at most 1 MiB, including the aggregate detection-batch
metadata envelope. Additional batch ceilings are 10,000 occurrences, 64 MiB
combined stdout/stderr/raw-result/witness bytes, and 16 MiB raw-result+witness
per occurrence. Thus large metadata may reach its bound before 10,000 rows.
Combined accepted spec/detector/rule raw blobs are limited to 1 MiB; acceptance
authority evidence is separately limited to 1 MiB. Reject before constructing
large SQL parameters; never seal a truncated accepted-content bundle.
Validate before constructing SQL parameters. No truncation may be called a
completed batch. The separate failure-prefix path is at most 64 KiB and must
state whether it is truncated and how many bytes were actually observed.
The Python facade requires exact tuples for accepted detector/rule blobs and
raw observations, exact bytes for blobs, and exact protocol model/envelope
types. Bounded validated metadata constrains raw collection lengths before
iteration or hashing; lists, subclasses and arbitrary iterables are rejected,
not silently copied. The repository revalidates inputs before constructing SQL
parameters; SQL remains an independent boundary for direct callers.

## Domains and closed shapes

All domains below have prefix `scanipy-execution/` and suffix `/1`. Every listed
field is required; explicitly nullable values remain present as JSON null.
Nested objects are closed too. Exact executable validators and parity tests
are part of implementation acceptance, not permission to silently extend v1.

| Domain | Fields besides `schema` |
|---|---|
| `request` | org_id, codebase_id, lineage_id, predecessor_request_id, idempotency_key, source_selector, requested_s_version, requested_policy_digest, retry_policy, identity_policy |
| `planned-policy` | bindings, capture_detection_runner, identity_runner, identity_policy |
| `retry-policy` | max_attempts, lease_seconds, initial_backoff_seconds, max_backoff_seconds |
| `source-inventory` | files |
| `seal` | request_id, resolved_commit, commit_algorithm, tree_algorithm, tree_digest, inventory_digest, storage_object_id, storage_reference, retain_seconds, s_version, planned_policy_digest, accepted_content_digest, acceptance_evidence_digest, intended_files, bindings |
| `accepted-content` | spec_sha256, detector_sha256s, rule_sha256s |
| `work-payload` | request_id, kind, occurrence_id, policy |
| `attempt-policy` | assignment_id, code_policy_digest, environment_policy_digest, lease_seconds |
| `run-input` | binding_key, run_ordinal, argv, cwd, tool_policy_digest, code_policy_digest, environment_policy_digest |
| `occurrence-inventory` | occurrences |
| `detection-batch` | run_id, status, tool_identity, code_identity, actual_invocation, detector_env_digest, full_env_digest, coverage, stdout_sha256, stderr_sha256, occurrences, inventory_digest |
| `run-failure` | code, message, prefix_sha256, observed_byte_count, truncated, observed_full_sha256 |
| `attempt-result` | status, retryable, error, actual_code_digest, actual_env_digest, completed_run_ids, identity, identity_policy_reason |
| `lease-release` | attempt_id, token, reason |
| `cancellation` | request_id, reason |
| `retirement` | capture_id, storage_object_id, token, reason, evidence_digest |

`source_selector` = `{kind: "git-ref", value: nonempty string}` is a requested
selector, not an observed commit. `identity_policy` = `{mode: "required" |
"not-applicable", policy_id, policy_digest, reason}`; not-applicable requires a
nonempty reason. The same request retry policy applies to v1 identity jobs.
No payload permits arbitrary executable callbacks or grants acceptance.

`files` is a path-sorted unique list of `{path, size, sha256}`. Paths are relative
POSIX paths without empty, dot, parent, backslash or NUL components; sizes are
nonnegative int64. Empty inventories are allowed but prove no useful coverage.
The digest of this envelope is independent of the source tree digest.
`tree_algorithm` is exactly `sha256-length-prefixed-path-and-content-v1`:
the existing sorted path/content u64-BE length framing is unchanged and does
not gain a domain+LF prefix. Inside the seal its digest has 64 hex; a source
helper's `sha256:` prefix is removed only at that explicit adapter boundary.

Each binding is `{key, detector_id, engines, adapter_policy_digest, class_id,
language, rules, detector_content_digest, tool_policy_digest, code_policy_digest,
environment_policy_digest, expected_tool_digest, expected_code_digest,
expected_image_digest}`. Engines are a nonempty
unique subset of ifds/ide/semgrep/cpg-query/external. Each rule is
`{rule_id, semantic_digest, content_digest}`. Binding keys and rule IDs within a
binding are unique. The three expected artifact pins may be null only as explicit
incomplete intent; null is never completion authority. An actual invocation records `{argv, cwd}`.
For every accepted batch (completed or partial-failed), the ordered actual argv
and cwd must exactly equal that run's immutable `run-input`. Unexpected actual
values belong in bounded `run-failure` raw evidence with explicit failure, not
an accepted occurrence batch. Never replace observed values with requested
ones. This consistency check does not attest that a native process ran.
Tool/code identity records are `{policy_digest, artifact_digest, evidence_digest}`;
the policy digest must equal its exact sealed input. These are trusted producer
observations, not authenticity proved by the existence of a hash string.

The exact planned-policy envelope bytes/schema/digest are immutable request
columns, supplied with `create_request_v1` along with request bytes/digest.
`requested_policy_digest` equals this envelope's domain-separated digest, and
the request identity policy must equal its planned-policy copy. At sealing,
`planned_policy_digest` and the ordered full binding objects must still equal
the originally requested policy. Each runner is `{code_policy_digest,
environment_policy_digest, expected_code_digest, expected_image_digest}`;
capture/detection and identity runners are separate processes and may differ.
Claims require the appropriate runner's code/environment policy hashes and the
immutable retry-policy lease duration. Policy hashes identify policy documents,
not observed executable bytes, and must never be equated to artifact hashes.

Actual run tool/code `artifact_digest` and detector image digest must match
their named expected pins before accepting valid occurrences. Successful
attempt code/image observations must match their respective runner pins.
Missing/mismatching pins retain bounded failed-run evidence with actual mismatch,
not invented bindings; previously committed occurrences remain unchanged.
Failed attempts may retain genuinely observed mismatching artifacts as failure.
Future worker/controller integration must refuse native launch when required
expected pins are absent and settle an explicit failed attempt, not leave it
pending forever. Matching pins still do not attest actual runtime execution;
the trusted producer and full-environment manifest remain separate prerequisites.

Accepted spec, detector and rule bytes are separate bytea payloads. The
accepted-content manifest binds their SHA256 digests: one spec blob, detector
blobs in binding order, rule blobs in binding/rule order. The seal binds this
manifest's domain-separated digest and exact authority-evidence bytes' raw
SHA256. SQL checks each actual blob's digest against manifest and seal bindings.
Neither stored bytes nor a version label establish real registry acceptance;
that trusted resolver remains separately unwired.

An occurrence metadata item is `{result_key, duplicate_ordinal, tool_ordinal,
engine, rule_id, cwe, severity, message, location, raw_sha256, witness_sha256}`.
The key is a validated adapter ID or explicit versioned canonical key;
duplicate ordinal preserves otherwise identical results. Tool ordinal retains
returned order. CWE may be null if unobserved. Witness digest is null exactly
when no witness bytes exist. Engine determines origin; class/language/detector/
rule semantics/S_version are copied from the immutable seal, environment from
the actual run. No identity operation runs during batch retention.

Location is `{status, path, start_line, start_column, end_line, end_column}`.
Status is known/partial/unknown. Unknown has all other fields null; known has
observed path and start line; partial contains some evidence but does not meet
known's minimum. Coordinates are null or positive integers, columns require
their line, and an end requires a compatible observed start and forward order.
Do not fabricate `cpg://` paths, node-ID coordinates, or line 1. Original raw
bytes retain unsupported tool location information without promoting it.

Coverage is `{status, files, rules, errors}` with status complete/partial/failed.
Only complete with exact intended file/rule inventories and no errors can
close a run. An occurrence-inventory envelope binds the ordered metadata list
before operational occurrence IDs are allocated. Run status completed requires
complete coverage; failed may retain all valid observations without closing
the inventory or authorizing a new automatic detection attempt.

Attempt identity is null or the existing strict R09 descriptor pair, version 2.
It retains independent statuses, namespaces, classes and exact scoped annotation,
including completed graph + failed slice. A failed attempt is not a final
finding. `error` is null or `{code, message}`. Required identity completion needs
both completed artifacts; explicit not-applicable requires policy/reason and
not-applicable descriptors. No strong value authorizes inherited suppression.

## Immutable coordination policy

Version-1 limits: attempts 1..16; lease 1..900 seconds; initial backoff 0..3600;
maximum backoff 0..86400, initial <= maximum. Defaults: 3 attempts, 300-second
lease, 1-second initial and 60-second maximum backoff. Retry delay is
min(maximum, initial * 2^(attempt_number - 1)). Attempt-policy lease must equal
the item's immutable policy lease, and renewal uses that duration. Cleanup
leases are fixed at 300 seconds. Retention is 0..315360000 seconds from the
database-created capture time; replay compares duration, not caller timestamps.

Lock order: request, capture, work item, attempt, detector run. Sample
clock_timestamp only after required locks. All nonterminal work for a capture
blocks retirement, including expired-running work until explicit expiry settles
it. Retiring is irreversible and storage object/reference never reused.
Exact committed terminal replay is read-only even after expiry/replacement;
never-committed stale writes fail. Completed bindings are reused, while partial
retained results prevent retry and cannot be filtered out of stage accounting.
New executions after a pre-batch failed/interrupted zero-occurrence run retain
an immutable `supersedes_run_id` with a composite same-scope/binding FK to the
unreferenced failure-chain leaf, not a wall-clock or caller-ordinal ordering.
Terminal failed run IDs cannot be begun again. Requested and
observed argv/cwd remain separately labeled; launcher differences are not
silently called equal, and storing either does not prove source-custody execution.

The Python transaction facade sets transaction-local statement and lock
deadlines to 15,000 ms and 2,000 ms respectively. A timeout is an error, never
an empty successful result. Direct SQL dispatchers must enforce equivalent
bounded deadlines; role grants are not a deadline mechanism. The connection
factory must acquire fresh connections and close/discard them on every exit,
including commit errors. Do not acknowledge a result before context exit or
nest this transaction binder; ambiguous commits are retried on a fresh
transaction using the same immutable request/run keys. Transaction-local
tenant bindings and deadlines must not escape to a subsequent borrower.

## Implementation and verification boundaries

Migration A creates shapes, checks, composite scopes and immutable-history
guards. B creates only fresh reserved roles, RLS and narrowly granted functions;
any pre-existing scanipy_exec_* reserved role is refused rather than adopted.
Both downgrades refuse any new history. No runtime direct DML/TRUNCATE or
owner membership, and no new legacy app/system/triage grant. Request cancellation,
detector, identity and cleanup operations have distinct capabilities.

Required evidence includes cross-language SQL/Python canonical-byte vectors,
real restricted PostgreSQL principals, concurrency/lease-expiry/retirement
falsifiers, fault rollback, exact acknowledged replay and bounded raw-byte cases.
Tests must be selected by actual CI markers. Production capture/resolver/native
detector/final-projection/API/UI integration and full R07/R08 acceptance remain
outstanding under the parent contract.

All SQL `bytea[]` wire parameters (accepted detectors/rules and raw
results/witnesses) must be empty or one-dimensional with lower bound 1. A
different bound or dimension is rejected, never silently indexed as absent
nullable witness data. Original raw bytes remain unrestricted within the
declared byte caps; this array-shape rule does not change their contents.

## Verification and remaining integration work

The dedicated PostgreSQL test module is
[`test_occurrence_store.py`](../../tests/integration/test_occurrence_store.py);
its fixture uses only the explicit occurrence-test URL, validates the resolved
child target and checks database/role ownership before disposal. It never
discovers the application's DSN. Unit tests cover codecs, limits, transaction
errors and the fixture's URL/ownership rejection paths without PostgreSQL.

Independent read-only validation on the isolated PostgreSQL 16.15/UTF8 fixture
agreed on 20 envelope, 5 scalar/depth, 4 size and 6 array vectors. Near-limit
root and nested invalid objects rejected normally with SQLSTATE 22023 under a
3-second deadline (observed 0.5800 s and 0.2042 s on that host). These are
bounded fixture observations, not general latency or denial-of-service claims.

The following remain required for the full submitted functionality:

- Wire authenticated request/status services to fresh, transaction-bound
  connections using the role-specific facade. GUC binding is not authentication.
- Supply genuine accepted-registry, source-custody and observed artifact/image
  evidence. Refuse native launch when required expected pins are missing and
  retain an explicit failed attempt; never infer execution attestation from hashes.
- Wire raw detector completion before graph/slice finalization throughout the
  real solver and worker paths, with exact-key recovery after ambiguous commits.
- Execute durable identity jobs with actual independent producers; preserve
  provisional occurrences and their original origin when later identity fails.
- Integrate truthful asynchronous status, final finding/SARIF/signature
  projection, continuity decisions and human-authority persistence. This store
  intentionally never completes finalization or lifecycle by itself.
- Connect irreversible retirement to the verified source-capture backend.
  These database tests delete no source object and do not certify filesystem
  cleanup, reactivation safety outside the protocol, or a native detector run.

The umbrella delivery and #378 remain open; this foundation is not an
end-to-end R07/R08 completion claim.
