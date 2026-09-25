# R07/R08 — Durable occurrence store, version 1

Status: independently reviewed design contract; code acceptance pending.
Owner: root coordinator, assigned persistence/API scope
under #378; #362 remains the full-scope umbrella. Date: 2026-09-25.

Implementation assignment: schema/ingest agent owns the new shape/security
migrations, typed repository and dedicated store tests in the isolated
`bhmea/occurrence-persistence` branch. Root owns this contract, the dedicated
CI job, and API/production integration. The canonical agent's continuity/raw-solver files and the corpus
agent's R05 campaign files are separate scopes; no overlapping edits are assigned.

Authority: [DECISION-BHMEA-01](../DECISION-BHMEA-01-current-execution-authority-2026-09-25.md)
and [the occurrence/decision contract](OCCURRENCE-DECISION-CONTRACT.md).
This is an additive engineering decision for that existing task. Historical
PLAN/SDD/WBS, completed R09 constraints, old signed records and existing grants
are not rewritten. No full R07/R08 milestone or submitted claim is complete.

PR #411 canonical-review follow-up (2026-09-25): root additionally authorizes
the single `CLAR-BHMEA-02` append in WBS.md section 17 for the still-unimplemented
occurrence-to-final-Finding/SARIF/signature bridge. It remains OPEN; no historical
approval/status or runtime behavior is rewritten by the append. The eventual
projection must use actual identity evidence and the accepted R09 metadata
contract, including explicit missing/failed/not-applicable cases, not synthetic
hashes or an unconditional legacy emitter. #378 and #362 remain In Progress.

## 1. First implementation slice and explicit exclusions

Deliver one coherent PostgreSQL-backed path: allocate an idempotent request and
durable work item; bind a real immutable capture and accepted detector inputs;
retain a returned detection batch and enqueue its identity work atomically;
claim, renew and finish fenced attempts without deleting earlier observations.
The database is the durable queue, not a mirror of an in-memory executor or
an external broker. A disconnected worker can reconnect and recover its state.

The first PR includes two additive migrations, typed repository operations,
bounded in-database detection evidence and real restricted-principal/concurrency
tests. It does not yet supply source capture bytes on disk, SCM invocation,
the raw solver seam, real engine adapters, final finding/signature projection,
entities/human decisions, API authorization, Docker wiring or stage evidence.
Those are the next integrations, not capabilities implied by a schema test.

Do not reuse `SqlJobStateStore`: its proposed `jobs` table is absent from the
migration chain and its API lacks this payload/lease contract. Reuse the
driver-light connection factory and `acquire_for_request` transaction binding,
not an adapter method which independently commits inside another transaction.
The new store is not an ORM-autogeneration change.

The approved [version-1 envelope contract](OCCURRENCE-ENVELOPES-V1.md)
fixes the exact closed field sets, portable JSON types, domain/digest forms,
unknown-location representation, aggregate metadata bound and immutable
coordination constants. Implementations must satisfy both documents. Any
reserved-role preexistence is refused in version 1 rather than adopted.

## 2. Physical namespace, common types and bounds

All new tables/functions live in `scanipy_execution`. Runtime roles receive no
CREATE privilege in that schema. Existing tables stay in `public`. Add only
`UNIQUE (org_id, id)` to `public.codebases` so new composite scope references
are enforceable; do not repair unrelated legacy data by rewriting it.

Common conventions:

- Record IDs are UUIDs. Each scoped row carries `org_id` and `codebase_id`.
  Operational UUIDs, leases and timestamps are not canonical core/SARIF bytes.
- Digests are 32-byte `bytea` internally; image/environment API digests retain
  the explicit `sha256:<64 lowercase hex>` representation. Version/domain
  fields are separate and nonempty; a bare digest is not an algorithm ID.
- Canonical request/policy/result envelope bytes use UTF-8 sorted-key compact
  JSON, no ASCII escaping, no nonfinite values, and no floats in version 1.
  Allowed values are null, bool, signed 64-bit integer, Unicode scalar string
  excluding U+0000, list and string-keyed object. The same string restriction
  applies to keys. Reject lone surrogates, NUL and out-of-range integer tokens;
  bool is a separate JSON type, not an integer accepted by Python subclassing.
  These explicit portable version-1 bounds avoid PostgreSQL text/jsonb's NUL
  restriction and inconsistent numeric/parser limits. They do not restrict the
  contents of separately retained raw evidence bytes or captured source files.
  Duplicate JSON keys and unknown envelope fields are rejected by the adapter.
  A content digest is SHA256 of the named ASCII domain, one LF and the exact
  envelope bytes. Database functions verify the digest and the typed-field
  projection, and independently reject duplicate/unknown/noncanonical envelope
  forms. Validate preserved `json` text before any `jsonb` conversion can erase
  duplicate keys. SQL canonical-byte verification must match the Python encoder
  exactly, including Unicode key order, escaping and integer tokens; do not use
  `jsonb::text` as if it were Python compact JSON. Bound nesting to 32 levels.
  Parsing a JSON object is not producer authentication.
- Full raw tool bytes are distinct from canonical envelopes and are retained
  unchanged. Hashing them does not make them semantic identity or provenance.
- Version-1 ingestion bounds: at most 10,000 occurrences and 64 MiB of combined
  retained stdout, stderr, raw-result and witness bytes per detector batch;
  at most 16 MiB for one occurrence's raw-result plus witness payload. Canonical
  request/seal/coordination envelopes, including aggregate batch metadata, are
  bounded separately at 1 MiB each. Combined accepted spec/detector/rule bytes
  are bounded at 1 MiB, and their authority evidence at another 1 MiB.
  Validate counts and byte lengths before constructing a large SQL parameter.
  These are conservative implementation limits, not measured stage budgets.
  A limit violation is explicit failed/incomplete detection, never truncation
  followed by a completed inventory. Native subprocess output limiting remains
  an R16 integration requirement; a database bound does not bound child RAM.
- Use `timestamptz` and database-generated coordination times. Lease expiry
  uses fresh `clock_timestamp()` sampled after all required row locks, not
  transaction-start `now()` or a timestamp captured before lock acquisition.
- Every child relation has a composite foreign key that includes all relevant
  org/codebase/request/capture/run/job scope, backed by an exact unique parent
  key. UUID uniqueness alone is not a same-scope constraint.
- All historical foreign keys use RESTRICT/NO ACTION, not cascading deletion.
  Evidence and capture metadata survive retirement of source bytes.

## 3. Eight tables

The named immutable fields below are insert-only. An unconditional trigger
rejects changes to them even if a future grant accidentally widens. Terminal
attempt/run records cannot be rewritten. Runtime DELETE/TRUNCATE is forbidden.
Mutable coordination columns are changed only by the functions in section 4.

### 3.1 `scan_requests`

Immutable: `id`, scope, `lineage_id`, nullable `predecessor_request_id`, nonempty
`idempotency_key`, `request_schema`, `request_bytes`, `request_digest`, and
`created_at`, plus `planned_policy_schema`, `planned_policy_bytes`, and
`planned_policy_digest`. The request envelope contains requested source selector
and spec version and binds the exact planned-policy digest. The independently
validated policy contains ordered detector bindings, capture/detection and
identity runner policies, and the identity policy. It is not an observed commit
or execution manifest. Exact idempotency replay also requires identical planned
policy bytes; a changed plan cannot hide behind the same request envelope.

Version 1 uses exact artifact pins, not an unevaluated allowlist: each detector
binding separates tool/code/environment **policy-document** digests from
`expected_tool_digest`, `expected_code_digest`, and `expected_image_digest`.
Each runner separately fixes its expected code and image. Never compare the
hash of a policy document with the hash of the tool, code, or image it describes.
Null expected pins represent incomplete intent, not wildcard approval; required
missing/mismatched pins cannot complete execution. A future controller must
refuse native launch when required pins are absent, recording an explicit failed
attempt instead of repeatedly leaving an unexecutable request pending.

Unique `(org_id, idempotency_key)`; unique scoped ID and scoped lineage/ID keys.
A predecessor FK includes org, codebase and lineage; self-predecessors are
rejected. References only existing immutable requests, so cycles cannot be
introduced by changing ancestry later. This records explicit ancestry, not a
globally inferred commit order or permission for a late scan to change lifecycle.

Coordination: nonnegative monotonic `revision`, separate capture/detection/
identity/finalization/lifecycle states, active detection work reference, and
structured error references. Initial stages are pending, not completed.
The first store does not promote finalization or lifecycle to completed.
In the version-1 SQL schema, `finalization_state` and `lifecycle_state` are
explicitly constrained to the literal `pending`. They are reserved integration
states, not claims that an executor or decision-lifecycle processor exists.
Any later transition requires an additive reviewed migration, actual producer
and failure/replay tests; ordinary store success cannot promote these fields.

### 3.2 `source_captures`

Immutable: `id`, scope, `owner_request_id`, `resolved_commit`, `commit_algorithm`, `tree_algorithm`,
`tree_digest`, exact file inventory bytes/digest, immutable `storage_object_id`
and `storage_reference`, `created_at`, and configured `retain_until`.
Version 1 supports a real nonzero 40-hex Git SHA-1 commit; unsupported commit
formats fail explicitly. Never substitute forty zeroes or an unresolved branch.

The source tree uses the existing
`sha256-length-prefixed-path-and-content-v1` domain/encoding, not the raw-v2
export probe's distinct `scanipy-source-tree/1` algorithm. Inventory retains
relative POSIX paths, sizes and actual per-file digests. The capture adapter
must verify traversal, symlinks, special files and immutable bytes; a DB row
does not prove a directory safe or content-addressed.

Here the tree algorithm label is metadata, NOT an ASCII prefix in the hashed
bytes: the existing helper hashes sorted relative POSIX path/content pairs with
unsigned 64-bit big-endian lengths. Do not apply the envelope domain-plus-LF
rule to that tree or change an existing source digest's meaning.

Unique storage object identity/reference: neither may ever be reused, even for
identical contents after retirement. Same content can have a new capture/object.
No fabricated snapshot/CPG artifact foreign key exists.

Version 1 assigns one capture to one request: `owner_request_id` is unique and
its composite FK includes org/codebase. Detection and identity share that capture
within the request. Different requests do not reuse its physical storage object;
cross-request source deduplication is an optional later optimization. This keeps
retirement's request/capture lock ownership unambiguous. A replacement capture
after retirement requires a new explicitly linked request.

Coordination: `retention_state` active/retiring/retired, monotonic cleanup token,
cleanup lease expiry, retirement evidence, revision. `retiring` is irreversible;
no reactivation or replacement bytes at that path. The row remains indefinitely.

### 3.3 `scan_seals`

Exactly one immutable seal per request. Fields: scope, request, capture, seal
schema/bytes/digest, actual `S_version`, accepted spec bytes/digest, accepted
detector/rule bytes/digests, and the intended file/rule/detector inventory.
Requested and observed bindings are not conflated. Planned environment is
explicitly planned; observed detector/full-analysis evidence belongs to runs
and attempts after it exists.

The accepted spec/rule content is copied and bound at sealing time. A reference
to mutable `spec_versions`, or the `S_version` string alone, is insufficient.
The trusted resolver verifies accepted status and the exact content under its
transaction/registry protocol; an API client cannot submit an accepted flag.
Later registry edits cannot change sealed bytes. Version-1 replay with a
different capture/spec/rule/plan digest conflicts; there is no reseal update.
The seal's ordered bindings and policy digest must match the request's preserved
planned policy exactly. A worker cannot select new pins while sealing a request.

The existing `SqlSpecRegistryPort` is not this accepted-content resolver: it
only checks a global version label. Actual accepted-content verification and
its authority evidence remain an unwired producer prerequisite. The first store
binds the trusted producer's exact inputs/evidence without certifying them as
accepted merely because a seal exists; controlled DB fixtures are not proof of
real registry acceptance. Runtime APIs cannot provide an `accepted=true` escape.

Composite request/capture FKs enforce org, codebase and owning request equality. Each intended
detector binding has a stable key and explicit supported engine/adapter policy,
class/language/rule scope. Mixed parent detectors must retain the actual child
engine for each result; they cannot derive every result's origin from the parent.

### 3.4 `detector_runs`

Fields: scoped ID, request/seal/capture, consuming work item and attempt, sealed
detector-binding key, run ordinal, immutable invocation inputs and requested
policy. Unique `(work_attempt_id, detector_binding_key, run_ordinal)` plus the
composite scoped parent keys needed by occurrences.

Transitions: pending/running to one terminal completed/failed/interrupted state.
Terminal evidence records actual tool/code/invocation and observed detector
environment, exact stdout/stderr, coverage/errors, result count and inventory
digest. Missing or unknown environment is not invented to create an occurrence.
If a producer cannot provide required detection bindings, retain the raw failed
run and diagnostic; do not manufacture a valid finding or completed inventory.
Observed tool/code artifacts and detector image must match their named expected
pins, while the reported policy digests must match the separately sealed policy
digests. Successful attempt code/image must match that work kind's runner pins.
Required missing/mismatched observations use bounded failed-run diagnostics and
cannot be recast as a successful occurrence batch. Format and digest checks do
not constitute runtime attestation, accepted-registry verification, or a full
environment manifest; an unobserved full manifest remains absent.

A returned valid batch may retain observations while its run is failed/partial;
those observations remain visible but that inventory is not closed. A zero
exit code, valid JSON or zero results alone cannot establish completed coverage.
The complete file/rule coverage producer remains independently accountable.

New actual detector execution creates a new run, retaining previous run history.
Exact replay of the same run/batch returns its prior occurrence IDs; different
content for that same key conflicts. Identity retries never rerun detection or
allocate replacement occurrence IDs. A future UI distinguishes current selected
detector runs from earlier attempt history without deleting observations.

Version 1 uses a partial unique index on `(request_id, detector_binding_key)`
where run state is completed. A resumed capture/detection attempt reuses that
already committed completed run; it does not execute the binding again or union
duplicate output. `begin_detector_run` explicitly returns either its existing
completed result or a new run for an unfinished binding. Reuse requires the same
seal/capture and compatible exact sealed execution policy; changed tool/code/
environment policy requires a new request. Completion accounts for exactly one
completed run for each intended binding, including reused run IDs in its evidence.

A failed/partial run that retained valid occurrences makes the enclosing
capture/detection work nonretryable in this initial protocol: preserve its
visible observations and failed coverage, then require a new linked request for
another detection execution. Never hide those competitors by selecting a fresh
successful retry or silently resolve lifecycle from it. Failures before a valid
batch commits may retry under the bounded policy. Lost acknowledgement after a
completed batch is handled by exact replay/reuse, not by rerunning the detector.

### 3.5 `detection_occurrences`

Immutable fields: scoped ID; request, capture and detector run; validated adapter
result ID or versioned canonical result key plus duplicate ordinal; full raw
result bytes/digest; nullable actual witness bytes/digest; trusted actual child
engine, engine-derived `origin` and matching `determinism_partition`; detector,
class, language, rule ID and rule-semantic digest; actual `S_version` and observed
detector `env_digest`; CWE, severity, message and structured physical location.
Store any observed full-environment binding separately; absent remains absent.
An identity attempt may later bind a full manifest without rewriting detection.

Unique `(detector_run_id, adapter_result_key, duplicate_ordinal)`, never unique
raw payload hash or fingerprint. Preserve tool order/multiplicity and duplicate
ambiguity. The same run/key with different content conflicts; identical results
at different ordinals remain distinct records.

Engine/origin consistency is checked against the sealed adapter policy, with
ifds/ide core and semgrep/cpg-query/external oracle; mixed output uses its actual
child engine. No graph/slice hash is mandatory or fabricated here. Identity,
suppression, human verdict and lifecycle are not detection-content columns.

### 3.6 `work_items`

Immutable fields: scoped ID, request, kind, nullable occurrence ID, payload
schema/bytes/digest, unique idempotency key, bounded retry/backoff policy and
creation time. Initial kinds are
`capture_detection` (occurrence must be NULL) and `identity` (occurrence required
and belongs to the same request/capture scope). No arbitrary executable command
or callback address is accepted in a payload.

Coordination: pending/running/completed/failed/cancelled; active attempt ID,
monotonic fencing token, next-attempt time, revision and terminal
result/error reference. A terminal item's exact acknowledgement replay is
idempotent; changed payload/status/evidence is a conflict. No resurrection of a
terminal item. Explicit later work gets a new linked item/request.

Request creation inserts its initial work atomically. Batch persistence inserts
one unique identity item for every persisted valid occurrence atomically; explicit
not-applicable identity still records its policy/reason, never vanishes.

### 3.7 `work_attempts`

Fields: scoped ID, work item, attempt number, assignment identity, fencing token,
requested policy/code binding, start/lease timestamps and state. Unique
`(work_item_id, attempt_number)` and `(work_item_id, fencing_token)`.

One-way running to completed/failed/interrupted/cancelled; a terminal state
requires its immutable evidence/result/error. Requested inputs are never changed
to match an observed result. Lease renewal can only extend the current live
attempt under the same token. Expiry preserves an interrupted record before
another attempt number/token is created.

Identity evidence retains each independent graph/slice descriptor and its
annotation/status/namespace/class, including graph success followed by slice
failure. Use R09 typed descriptors, not a second ambiguous shared class. A
terminal failed attempt is not a completed final finding. Completed-record
projection/signing is a separately validated subsequent integration.

### 3.8 `capture_leases`

Fields: scoped capture, request, work item and attempt FKs; token, acquired time,
expiry and released state/reason. No generic unverified consumer string. An
active attempt is the consumer, and both its work lease and capture lease must
remain live. Acquisition/renewal locks the capture used by retirement and checks
active retention state, correct immutable seal, active attempt/token and scope.

Capture retirement is blocked by any live consumer or pending/retry-eligible
work referencing the capture, even between attempts when no lease is held.
Release is idempotent with exact payload; it cannot revive a retired lease.

## 4. Transactional operation contract

Use narrow versioned SQL functions with typed parameters and a typed Python
repository facade. Functions perform their own scope, state, payload, revision
and lease checks; a WHERE clause used voluntarily by one caller is not the
runtime write fence. Public operation families are:

1. `create_request`: atomic unique insert plus initial work. Concurrent first
   inserts yield one winner; an exact retry returns it and a different request
   digest for the same org/idempotency key conflicts, including another codebase.
2. `claim_capture_detection` / `claim_identity`: separate kind-scoped functions,
   explicit trusted org dispatch, deterministic eligible queue selection and
   row locking. Claim increments token and attempt number. Expired prior work
   is terminalized before an eligible replacement attempt, never by resurrecting
   a terminal work item. If a seal exists, claim also acquires the new attempt's
   capture lease atomically after checking active retention state. Pre-seal
   capture/detection work has no capture yet. No BYPASSRLS/global tenant discovery.
3. `renew_attempt`: require expected item revision, active attempt/token and
   unexpired lease after locking; expired work cannot be renewed back to life.
4. `register_capture_and_seal`: requires the live capture/detection attempt;
   bind validated immutable capture plus accepted input seal AND its initial
   consumer lease atomically. There is no committed sealed running consumer
   without capture-lease protection. Exact retries return prior data and validate
   the still-live consumer; conflicting evidence/capture/plan refuses. An expired
   consumer needs a newly claimed attempt, not revival of its old lease.
5. `begin_detector_run`: validates the sealed binding and active work/capture
   leases; retains immutable invocation inputs before result ingestion.
6. `retain_detection_batch`: validates all records first, then in one transaction
   locks scope/current attempt, inserts raw observations and identity work, and
   seals the exact run inventory/status/evidence. Any fault rolls back all three.
   No duplicate result is removed and no identity function is invoked here.
   A separate bounded `fail_detector_run` records malformed/oversized/missing-
   binding failures without requiring the rejected large batch parameter. It
   retains a bounded diagnostic/raw prefix (maximum 64 KiB), explicit truncation
   and observed byte-count flags, and only actually observed digests. It never
   labels that prefix complete raw evidence or a closed inventory. Previously
   committed valid observations remain intact.
7. `finish_attempt`: validates current item revision, token, live lease and exact
   evidence. Atomically persists the terminal attempt and releases its consumers.
   Success completes the item only after required child inventories/evidence are
   settled. A retryable failure retains the failed attempt and returns the item
   to pending with bounded backoff and no active attempt while retries remain.
   Nonretryable failure, cancellation or exhaustion terminalizes the item.
   An identical acknowledgement replay may read the prior attempt result; it
   must never rewrite it, reschedule twice or complete a different attempt.
8. `cancel_work` / `expire_attempt`: trusted coordination operations retain the
   reason and prior observations. Retry exhaustion is explicit failure, not
   completed-empty detection; cancellation cannot erase queued evidence. Expiry
   interrupts pending/running detector runs associated with that attempt and
   releases its consumers. The item becomes pending/backoff only if retryable
   and within its immutable retry policy; otherwise it becomes terminal failed.
9. `acquire_capture_lease` / `renew_capture_lease` / `release_capture_lease`:
   validate consumer FK, live active attempt and irreversible retention fence.
10. `claim_retirement` / `finish_retirement`: enforce section 6, retain exact
    object identity and evidence, and never expose a reactivation operation.

The operation names above describe families, not a generic public dispatcher.
Public renewal/completion/lease/expiry wrappers are kind-specific: detector
wrappers hard-code `capture_detection`; identity wrappers hard-code `identity`.
Only private owner-only helpers are shared. Each wrapper validates the item's
actual kind even if a caller knows another item's ID/token. `current_user`
inside SECURITY DEFINER is the owner and is not an invoker authorization check.
Only the request service gets a scoped `cancel_request` capability (all of its
request's work, with expected request revision); detector/identity workers get
only expiry/finish wrappers for their own kind. Cleanup gets retirement only.

Choose and enforce one lock order across operations: request, capture, work
item, attempt, detector run. Resolve immutable IDs before locks, then revalidate
all relations/versions after locks. Queue selection may use SKIP LOCKED only if
it does not invert this order; avoid holding an item lock while waiting for its
request/capture. Re-evaluate eligibility after acquisition, not from an earlier
unlocked read. Numeric lease durations/retry limits are bounded configured
coordination policy, not caller-selected arbitrary intervals or stage SLAs.

All mutations run in one explicit caller transaction. A crash/disconnect before
commit leaves no acknowledged partial operation. A crash after commit is
handled by exact idempotent replay, not guessing that no response means failure.
Renewal or completion blocked on a row lock until after expiry must fail even
if the transaction began while the lease was live.

Request stage states are derived from exact child work/run inventories, not
arbitrary caller-supplied success flags. Capture/detection completion requires
all planned detector bindings accounted for. A failed/partial run with retained
occurrences cannot be omitted from that denominator. An older pre-batch failure
with zero retained occurrences may be superseded by its explicitly permitted
successful retry; retain both attempts and the supersession link/evidence.
Identity processing cannot be marked successful
while an occurrence's required job is pending/failed. The first store does not
derive successful absence, finalization or lifecycle from these aggregates.
Aggregate failures cannot be hidden by whichever child writes last: an identity
finish must not turn known failed detection back into running, and claiming or
adding another identity job must not erase a different terminal failed job.
Derive states centrally from the complete scoped child inventory, preserving
the explicitly recorded pre-batch retry/supersession exception above.

## 5. Database privilege boundary

Create a dedicated `scanipy_exec_owner` NOLOGIN, NOBYPASSRLS, non-superuser,
non-CREATEROLE privilege holder for SQL functions. It is not the table owner.
Runtime cannot inherit/SET ROLE into it; NOLOGIN alone is insufficient. Refuse
an unsafe pre-existing role instead of silently adopting broad cluster grants.
The migration owns the new schema/tables; application roles cannot alter them.

New runtime capability roles are distinct: `scanipy_exec_request` (request
creation/cancellation), `scanipy_exec_detector` (capture/seal and detection within a claimed
job), `scanipy_exec_identity` (identity attempts), `scanipy_exec_cleanup`
(retirement), and `scanipy_exec_read` (scoped read models). No role is implicitly
granted to `scanipy_app`, `scanipy_system`, `scanipy_triage` or PUBLIC. No human
decision/lifecycle write capability is provisioned before its implementation.

ENABLE and FORCE RLS on every new scoped table, with fail-closed transaction-local
`app.org_id` binding. Grant only required SELECT and explicit function EXECUTE
to runtime roles; no direct INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES, table/schema
ownership, CREATE, grant options or definer-role memberships. Preserve the old
triage write surface unchanged and test it still works where originally allowed.

Functions use `SECURITY DEFINER`, fixed
`search_path = pg_catalog, scanipy_execution, pg_temp`, and fully qualified
relations/functions. Revoke default PUBLIC EXECUTE in the same transaction as
creation, then grant each exact function signature to its intended role only.
Do not grant one generic unrestricted mutation dispatcher. This follows
[PostgreSQL 16's security-definer guidance](https://www.postgresql.org/docs/16/sql-createfunction.html#SQL-CREATEFUNCTION-SECURITY).
RLS is not a TRUNCATE or REFERENCES fence; test privileges separately as described
in [PostgreSQL's row-security contract](https://www.postgresql.org/docs/16/ddl-rowsecurity.html).

Do not assume the migration role's default privileges are safe. Normalize ACLs
on every newly created execution schema/table/function, including grants to
PUBLIC or arbitrary existing roles and private helpers, before installing the
explicit allowlist. Do not rewrite cluster-wide default privileges or unrelated
legacy object grants. A-only state must likewise expose no runtime DML/DDL.

The GUC remains trusted service context, not authentication. A credential holder
can set custom GUCs. API principal/capability/origin/CSRF protections and ranker
service-mediated write denial still require later implementation/tests. The
first single-tenant Docker dispatcher receives its explicit configured org;
multi-tenant discovery is not silently implemented with the legacy system role.

## 6. Irreversible source retirement

Hold the same request/capture locks used by new consumer creation. Check retention
time, no live consumers, and no pending/retry-eligible work, then mark retiring
with a new cleanup token. Only then may a trusted capture-store adapter remove
the exact verified immutable object. Retain metadata/inventory/history.

A database token cannot stop a filesystem deletion already in flight. Therefore
the old capture can never become active again, and its object/path can never be
reused. A replacement cleaner acts only on that same permanently retiring
object. Completion requires the current cleanup token and evidence; a stale
cleaner cannot finalize a newer attempt. Later analysis needing source creates
a new capture/object and explicitly linked new request, never mutates a seal.

The first DB PR tests these state/permission races; it does not perform deletion
or certify a concrete local/object-store cleanup implementation.

## 7. Migrations, tests and next integration actions

Migration A adds table shapes, common constraints, immutable-content guards and
indexes. Migration B adds dedicated roles, RLS and narrowly granted functions.
Do not mix table-shape and RLS changes. A-only state has no runtime grants.
Both downgrade paths refuse if any new history exists; protections cannot be
dropped from populated tables as a supposed harmless security rollback. Empty
upgrade/downgrade/re-upgrade removes the new schema, functions, grants, roles
and composite parent index cleanly. Do not use CASCADE to hide dependencies.

Required first-PR tests (real isolated PostgreSQL 16 unless purely byte/type tests):

- [ ] Empty migration round-trip and residue checks outside `public`; populated
  downgrade refusal preserves all records and protections.
- [ ] Restricted LOGIN principals verify DML/TRUNCATE/DDL/role-escalation and
  wrong-function denial; tests do not merely run as superuser with a GUC.
- [ ] Hostile default ACLs cannot leak table DML or private-helper EXECUTE to
  PUBLIC or an unrelated role. All preexisting reserved roles are refused,
  including superficially safe ones; legacy/default ACLs remain unchanged.
- [ ] Missing/wrong tenant, same-org wrong codebase, wrong request/capture/run,
  malicious predecessor, pooled-binding reuse and temporary-schema shadowing.
- [ ] Concurrent first insert: exact payload deduplicates, changed payload
  conflicts; same-status but changed terminal payload also conflicts.
- [ ] Complete and partial/failed batches, exact count/inventory digest, zero
  findings versus unsuccessful detection, duplicate multiplicity and replay.
- [ ] Fault between occurrence insert, identity scheduling and inventory seal:
  no partial commit. A fully rolled-back random allocation need not reuse its
  IDs; a COMMITTED replay/ambiguous acknowledgement must return identical IDs.
  Exact committed terminal replay may return its old result after expiry or a
  newer attempt without mutation; a never-committed stale batch is rejected.
- [ ] Independent graph/slice outcomes, failed later slice, immutable original
  origin/spec/environment and absence of fabricated final metadata.
- [ ] Stale/expired renewal and completion, replacement attempt history, token
  mismatch, cancellation/exhaustion, and blocked-lock expiry with two connections.
- [ ] Consumer/retirement race; pending retry blocks retirement; retiring never
  reactivates; late cleaner cannot affect a distinct replacement capture.
- [ ] Mutating the legacy spec registry after a seal leaves exact sealed inputs
  unchanged; changed seal replay fails.
- [ ] Completed-binding resume after lost acknowledgement reuses its exact run
  and occurrence IDs. Partial retained results prevent an automatic detection
  rerun or hidden competitor filtering; new execution requires a linked request.
- [ ] Cross-kind child interleavings preserve known detection/identity failures;
  failed terminal run replay is not misreported as a running/completed result.
- [ ] Policy-document and actual artifact digests cannot be substituted for
  one another. Missing pins, changed sealed pins, mismatched actual artifacts,
  and kind-crossing runner policy fail without manufacturing completed evidence.
- [ ] Kind-crossing completion/renewal/lease/expiry calls fail even with a known
  foreign item/token; request cancellation and cleanup privileges stay distinct.
- [ ] Direct SQL rejects duplicate keys at every depth, unknown fields, alternate
  noncanonical encodings and mismatched typed projections/digests; Unicode and
  integer framing agree with the Python adapter under the named envelope version.
  Cover NUL, lone surrogates, supplementary Unicode, signed 64-bit boundaries,
  oversized integer tokens and bool-versus-integer confusion before conversion
  to jsonb can normalize or erase their original representation.
- [ ] Evidence-size/count limits fail explicitly without completed truncation.
- [ ] Tests are selected by actual CI `-m unit` / `-m integration` expressions.
  Live database tests must never connect to the user's running app database.

The dedicated `occurrence-store-tests` CI job uses its own digest-pinned
PostgreSQL service, not the legacy integration cluster: reserved role names are
cluster-global. Only explicit `SCANIPY_OCCURRENCE_TEST_URL` opts a local test run
in. `SCANIPY_OCCURRENCE_TEST_REQUIRED=1` in CI makes a missing URL fail, and the
job requires nonempty executed tests with no skips. The fixture may create and
dispose only its uniquely named, OID/owner-verified child database and roles it
created itself. Unexpected preexisting reserved roles or ownership drift fail
closed; no application-DSN discovery, legacy baseline downgrade/restore,
forced disconnection, broad cleanup, or CASCADE. Disposable fixture cleanup is
not a production-history deletion API. Preserve JUnit evidence for the actual
restricted-login, committed concurrency and fault tests.

Mandatory next integrations, still outstanding after a successful store PR:

- [ ] Real immutable source-store implementation and safe same-source handoff.
- [ ] Trusted accepted-content resolver with real registry authority evidence;
  a mutable version-label lookup or a stored seal is not acceptance verification.
- [ ] Raw solver/worker detection before ALL canonical identity, including the
  current solver's own initial canonicalization; retain actual raw witnesses.
- [ ] Real Semgrep exit/coverage checks and occurrence adapter, no zero-commit or
  unknown-tool fallback; preserve every returned result before set conversion.
- [ ] Source-only oracle final projection and real full-environment/signature
  producers, preserving R09 completed-record constraints and old signed bytes.
- [ ] Docker worker/API/UI restart, lease/retry recovery, visible identity failure
  and history; implement operation-specific authentication/capabilities.
- [ ] Durable entities, append-only human decisions/policy activations, current
  read-time revocation and lifecycle-generation CAS using the pure matcher.
- [ ] Real refactor/changed/fixed/reappeared workflow evidence on the accepted
  combined artifact. Production matching policy stays empty until its gates pass.

## 8. Independent design review

On 2026-09-25 the independent corpus/tooling agent read this contract, the actual
database/worker/solver paths and the applicable Security Analyst/global/provenance
instructions. Review required explicit retry transitions, atomic initial source
leases, one-request capture ownership, kind-scoped function authorization,
completed-binding resume, bounded failed-run evidence, committed-replay semantics,
SQL envelope validation and irreversible retirement. These changes are recorded
above. The final design review found no remaining scoped architecture/security
blocker after its two final wording corrections. This is design approval only:
no migration, restricted-principal test, raw-detection integration or canonical
PR approval is claimed. Implemented code requires independent review again.
