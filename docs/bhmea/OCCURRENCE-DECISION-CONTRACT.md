# R07/R08 — Occurrence retention and durable decisions

Status: design contract for corrective issue #378; not implemented acceptance.
Owner: root engineering coordinator. Date: 2026-09-25.
Authority: [DECISION-BHMEA-01](../DECISION-BHMEA-01-current-execution-authority-2026-09-25.md),
the full [R07/R08 review](../REVIEW-BHMEA-EXECUTION-ACTION-ITEMS-2026-09-23.md),
and submitted C08. Preserve compatible FND-02, ORCH-03, TRI-01 and R09 contracts.

## 1. Defect and boundary

The current `services/scan/worker.py` computes a slice before appending a core
Finding. A later identity exception can discard the solver's already detected
results. It also canonicalizes the whole graph before detector dispatch, so a
global identity failure prevents detection entirely. Both `solve()` and
`incremental_solve()` in `analysis/ifds/solver.py` also canonicalize before
tabulation. The new path requires a raw-detection/solver seam; wrapping the
existing `run_detector` or default solver is insufficient.
`deploy/scanipy_oracle/app.py` runs work in a process-local executor,
stores location/commit identities, and removes its checkout in `finally`.
Neither path supplies durable identity attempts or cross-scan human decisions.

R09 protects completed identity-bearing findings and versioned provenance. Do
not weaken those completed-record constraints to represent unfinished work.
Introduce a separate immutable detection occurrence and processing history.
The original engine-derived origin remains fixed even if graph, fingerprint,
signing, persistence projection or attestation later fails. A parse failure
before detection is a failed analysis attempt, not a zero-finding result.

This contract covers storage/matching/coordination. It does not claim the current
canonicalizer, source fidelity, purity, solver or real demo satisfies acceptance.
Those prerequisites have independent R02/R06/R09/R18/R19/R20 evidence gates.

## 2. Record boundaries

| Record | Immutable content / identity | Mutable coordination allowed |
|---|---|---|
| Source capture | Org/codebase, actual resolved commit, framed tree digest, file inventory/digests and immutable storage reference | Retention/cleanup lease only; never rewrite bytes at an existing identity |
| Scan execution | Request idempotency key/payload digest, scope, explicit lineage and requested spec/tool policy; sealed actual capture/spec bindings before detection | Stage states, lease token/expiry, active attempt and error references |
| Detection occurrence | Scan/detector result identity, source capture, engine/origin, rule semantics, actual spec/version and detector environment, message/CWE/severity/location, raw/witness evidence references | No detection-content UPDATE; processing/decision state is joined from other records |
| Identity attempt | Occurrence, attempt number, requested identity policy/code version and actual execution evidence | One-way pending/running/terminal transition guarded by lease; terminal data never rewritten |
| Final projection | Validated completed R09 finding/provenance, bound to the occurrence and successful attempt | No identity/signature rewrite; historical signed bytes remain verifiable |
| Finding entity | Durable scoped cross-scan identity and creation reason | Explicit current lifecycle pointer/revision; history is append-only |
| Occurrence/entity link | Occurrence, entity, matching-policy digest, predecessor and match evidence | Append-only; a rematch creates a new adjudication event, not silent history replacement |
| Human decision event | Target scope, actor/authentication context, action, reason, references, request idempotency and prior revision | Append-only; revoke/change by a new event |
| Lifecycle event | Entity, scan, transition, coverage/matching evidence, predecessor revision | Append-only; current view is a transactionally maintained projection |

Use new additive tables with composite scope constraints and foreign keys; do
not retrofit pending rows into the existing completed `findings` table. Exact
migration DDL is a separately reviewed implementation step. Table-shape and
RLS/grants changes remain separate migrations. Nonempty history must not be
silently dropped on downgrade. No migration may connect to the user's running
database during development.

The legacy `snapshots`/`scans` foreign-key chain requires CPG artifacts. A source
capture must not fabricate those artifacts to fit that chain. It is a separate
pre-identity record, later linked to a real completed snapshot where applicable.
A source-only oracle final-persistence adapter remains an explicit R09/R08
integration prerequisite; this design does not pretend R09 already implements it.

## 3. Capture and emission ordering

1. Allocate a durable scan request with caller idempotency key and canonical
   request digest. Same key/different payload is a conflict, not an update.
2. Capture a real resolved commit and immutable tree; reject a missing commit
   instead of filling forty zeroes. Validate relative POSIX file paths and
   reject escaping symlinks/special files. Source inventory includes all inputs
   used by either detection or identity; do not execute source/build hooks/tests.
3. Seal actual source and accepted spec/detector bindings before detection.
   Record planned and observed environment manifests separately. A configured
   image string is not evidence that an invocation used that image/code.
4. Run the detector. Retain actual result bytes and coverage/error evidence.
   Persist every valid occurrence from its complete returned batch in a durable
   transaction **before any identity operation, including whole-graph
   canonicalization**. Raw graph construction required by a core detector is
   distinct from canonical identity; no strong ordering prerequisite may gate
   raw detection. Streaming adapters
   may commit validated batches, but incomplete detection remains explicit.
5. Enqueue identity work in the same transaction as occurrence persistence or
   use a durable outbox. A crash between insert and scheduling must be recoverable.
6. Compute independent graph/slice results, preserving each class/namespace and
   failure reason. Persist terminal attempt evidence; validate the R09 final
   projection separately. Signing/projection failure does not delete occurrence.
7. Evaluate lifecycle only after the relevant detector/identity coverage is
   settled. A visible occurrence need not wait for lifecycle settlement.

Occurrence identity is scan-local, not a cross-refactor fingerprint. Prefer an
adapter's validated unique result ID; otherwise use a versioned canonical result
record plus an explicit duplicate ordinal and retained full payload. Duplicate
ordering and retry collision rules must be tested. Never collapse two identical
results just because their hashes coincide. Same idempotency key with different
content is an error. Preserve raw tool order/multiplicity when canonical ordering
cannot distinguish duplicates; that ambiguity blocks inherited decisions.

Database UUIDs, wall-clock telemetry and attempt IDs are operational identity.
They must not leak into deterministic core bytes without an explicit R10/R20
canonical-output rule. Source locations remain evidence, not structural identity.

## 4. Processing states, retries and fencing

Track detection, identity, finalization and lifecycle independently. Expose
`pending`, `running`, `completed`, `failed`, and explicit `not_applicable` only
where the contract permits it. A completed weak fingerprint is terminal, not
an indefinitely pending strong result. Missing evidence is never `completed`.

- A database lease claim increments a fencing token using a transaction and
  database time. Completion/renewal writes require the exact active token and
  unexpired lease; a stale worker cannot mutate current state.
- An expired attempt becomes an immutable interrupted/failed record before a
  new numbered attempt is created. Do not recycle terminal attempt IDs.
- Use unique constraints for request/occurrence/attempt/outbox/finalization
  idempotency. Commit evidence references and terminal result atomically.
- Cancellation and retry exhaustion leave explicit terminal failure, retained
  detections and a UI-visible reason. Restart recovery is bounded and tested;
  do not simply label all previous running scans as successful or discard them.
- Source cleanup requires no live consumer lease, no eligible retry/outbox job,
  and the configured evidence-retention decision. Identity failure does not
  authorize immediate source deletion. Cleanup is scoped to one verified capture.
  Atomically claim a fenced `retiring` state that blocks new consumers before
  checking/removing bytes; creation of consumers must lock/check the same state.
  Recheck the cleanup token before finalizing retirement; an unlocked
  check-then-delete sequence is insufficient.
- A retained failure is not evidence that the intended analysis completed.

## 5. Match eligibility and scope

Human decisions may be attached to any occurrence. Automatic cross-refactor
inheritance is a narrower privilege: **deterministic-core only**, independent
graph and slice classes both strong, both completed, supported namespaces, and
a reviewed eligible identity policy. Oracle results never inherit automatic
suppression across a refactor, even if an auxiliary structural hash is strong.

The production policy registry starts with no accepted cross-refactor policy
until the corresponding R09/R18/R19/R20 and normalization/fidelity evidence is
accepted. Tests may inject an explicitly labeled controlled policy. A client
cannot authorize its own identity by sending `strong` or `policy_approved=true`.
Store and verify exact policy content digest, evidence/revision references and
supported class/language/normalization scope. No wildcard or implicit upgrade.
Activation/revocation is a reviewed operator-controlled policy event, never an
analysis-result field or an LLM decision. A falsifier or withdrawn approval
revokes applicability. Recompute effective inherited suppression against the
current policy revision on both writes and reads; revocation removes its
automatic effect immediately without deleting decisions, links or evidence.
Reactivation requires a new explicit reviewed event, not a cached old approval.
Each activation has a new identity. Old link certificates remain ineffective
after reactivation until explicitly re-adjudicated against that activation;
turning a registry flag back on must not resurrect old automatic suppression.

The match key includes:

- Org, canonical codebase/repository identity and explicit lineage.
- Origin, engine/detector, vulnerability class and language.
- Exact rule-semantic digest and accepted `S_version` under the initial strict
  compatibility policy. Renaming a rule ID is not implicit semantic equivalence.
- Exact graph/slice namespace and applicable identity/normalization policy.
- Compatible observed analysis environment and analysis-code artifact identity;
  initially exact equality. Scanned commit/tree/locations are not in this key.
- Slice fingerprint bytes.

The **whole-graph hash is not an equality requirement**. Unrelated graph changes
may change it while the implicated slice remains identical. Its actual value,
class and annotation are retained as evidence; strong class is an eligibility
guard, not permission to ignore other requirements.

Before matching, close each comparison group using a key containing the scoped
lineage, detector/class/language and semantic compatibility cohort **without**
fingerprint, strength or processing status. Require sealed detection inventories
on both sides and all potentially competing occurrences accounted for. A weak,
failed, pending or unsupported potential competitor makes the group unresolved;
do not filter it out and falsely call the remaining strong pair unique.
Matching then considers all candidates in both predecessor and current groups,
not the first database row returned. Exactly one eligible predecessor
and one eligible current occurrence for the key are required. Multiple equal
slices, several findings at one sink, unresolved identities or duplicate result
ambiguity block automatic inheritance. Never break a tie using line number,
path similarity, timestamp or insertion order. Persist the ambiguity reason.

Use explicit predecessor/lineage references; do not infer ancestry from commit
lexical order or compare every historic scan globally. Serialize lifecycle
application per codebase/lineage using revision compare-and-swap. An older scan
finishing late cannot overwrite a newer lifecycle pointer. Forked/concurrent
successors require an explicit chosen lineage, not last-writer-wins merging.
Validate lineage, current decision revision and active policy revision in the
same atomic commit boundary. A human revoking decision revision 5 while matching
is in flight must prevent a later commit inheriting that stale decision. Use
fixed lock ordering or equivalent serializable validation, and record the exact
revisions. Effective reads must still honor later policy/decision revocation.

## 6. Lifecycle and decisions

| Observed outcome | Lifecycle / decision behavior |
|---|---|
| Unique eligible unchanged identity | Link to same entity; retain applicable human decision/references with explicit inherited-event linkage |
| Changed strong identity | Create distinct entity; do not copy old suppression; resolve the prior entity only if absence requirements below hold |
| Weak/pending/failed/unsupported/ambiguous identity | Keep occurrence visible; no inherited suppression; no unsupported resolved transition |
| Successful absence with required coverage | Mark prior entity resolved with coverage evidence; preserve its occurrence and decision history |
| Previously resolved identity reappears | Reopen for human review; preserve historical decision but do not reactivate old suppression automatically |
| Scan/parser/detector failure or skipped relevant input | Keep prior lifecycle unchanged or explicitly uncertain; never report successful absence |
| Rule/spec/policy incompatibility | Start a separate comparison cohort; historical decisions remain visible, not silently migrated |

Absence requires successful detection of the intended files/rules on the actual
new capture, plus coverage sufficient to account for the prior implicated source.
Record explicit file relocation/deletion evidence when the old path no longer
exists. An empty match list is insufficient. Excluded/unsupported files, rule
disablement, parse errors, unsettled identity groups and unverified coverage
cannot establish resolution. Require graph-fidelity evidence only where the
applicable detector relies on the graph; a source-only oracle may establish
covered absence without an after fingerprint or irrelevant graph proof. This
never permits automatic oracle suppression inheritance. R04 removal semantics
must agree with this producer; fixture expected labels are not observations.

Decision scope is explicit: `occurrence` (only this immutable observation) or
`entity` (eligible future links in this lineage). A human may suppress a weak
occurrence without thereby granting cross-scan inheritance. Keep three independent
dimensions: human verdict (`unreviewed`, `confirmed`, `false_positive`), human
suppression (`active`, `inactive`) and machine lifecycle (`open`, `resolved`,
`reappeared`, or explicit uncertainty). Typed events set/clear a verdict,
activate/revoke suppression, or add reference metadata. A revocation names its
dimension and prior event: revoking suppression does not erase a false-positive
verdict, references or history. A false-positive verdict does not silently
activate suppression. Do not reuse machine `fixed` as a human verdict that
detection has proved absence.
Direct occurrence decisions override inherited values independently per
dimension: an explicit clear/unreviewed/inactive state shadows inheritance,
rather than falling through to an older entity value. Occurrence-only decisions
never propagate to later scans merely because the occurrence is linked.

Accept decisions through a trusted human-adjudication service, not the LLM
triage role. Record authenticated principal from server context where available;
in intentionally unauthenticated local mode, label the actor as an **unverified
local operator**, never a verified identity supplied by the client. Require
request idempotency and expected entity/decision revision; reject stale edits.
References are inert bounded text/URLs, never auto-fetched or executed. Render
all untrusted source/message/reference text escaped in the UI.
The service boundary must authenticate/authorize the caller independently of
database credentials. The ranker must not possess the operator write capability
or call adjudication endpoints successfully. Local mode binds its write service
to the intended local access boundary and uses an operator-only random capability
plus browser origin/CSRF defenses; container/service peers and source content
do not gain write authority merely because user identity is not authenticated.
No bearer capability is embedded in publicly served JavaScript or logs. Reject
unauthorized service-mediated writes as well as direct database mutations.

LLM triage remains additive ranking only. Preserve its existing write grants;
it cannot insert decision/lifecycle/link events, modify detection, suppress,
change origin or delete records. Human decisions do not rewrite signed detection
bytes. Repartitioning, where authorized, remains its separate append-only audit
path and invalidates unsupported automatic inheritance.

## 7. Persistence and API implementation requirements

- Enforce scope on every relation, not just an `org_id` column in each table.
  Composite foreign keys or equivalent verified constraints must prevent an
  occurrence/entity/capture/decision pointing into another tenant/codebase.
- Define dedicated runtime grants: detector writes immutable observations;
  identity worker owns attempts/projections; human service owns decisions;
  lifecycle coordinator owns links/events. LLM ranker has no new write grant.
  Use RLS consistent with local single-tenant and existing tenancy contracts.
- Preserve history with append-only constraints/triggers and restricted grants.
  A system database superuser is not the runtime principal used to prove fences.
- API exposes occurrence ID, actual detection, separate processing states,
  identity values/classes when present, failure reason, entity association and
  decision/history. Poll until relevant stages are terminal; never hide failed
  identity occurrences or label provisional output a signed final finding.
- Wire the real separate Docker worker to shared immutable source and this
  durable queue/lease state. Health, permissions, migrations, limits and retry
  recovery need real Compose tests, not merely a pure matcher test.
- Maintain compatibility for existing completed finding/provenance consumers;
  new provisional response types are explicit versioned API objects.

## 8. Action items and acceptance evidence

No checkbox is complete merely because this contract exists.

- [ ] Review exact schema/roles and composite scope invariants before migration.
- [ ] Implement source-capture/request/occurrence storage and transactional
  scheduling; prove result retention before the first identity invocation.
- [ ] Decouple raw solver detection/solution evidence from canonical-order and
  identity-bearing final result construction. Retain actual witnesses without
  fake canonical hashes, and verify stable final witness/solution serialization
  separately after successful identity processing.
- [ ] Implement fenced attempts/finalization with idempotent restart recovery.
- [ ] Implement strict policy-driven unique matching and ordered lifecycle.
- [ ] Implement append-only scoped human decisions and inert references.
- [ ] Prove database grants/RLS/append-only behavior on isolated PostgreSQL.
- [ ] Test all four graph/slice class combinations, oracle-with-strong-auxiliary
  hash, unknown versions, unaccepted policy, rule/tenant/engine mismatch and
  changed whole-graph hash with the same accepted slice.
- [ ] Test duplicate equal slices on either side, multiple sinks, incomplete
  identity groups (including one strong pair plus a weak/failed competitor)
  and malicious/cross-scope relationship requests.
- [ ] Test policy withdrawal/reactivation and human revocation racing with
  matching; effective inherited suppression must follow current authority.
- [ ] Test independent false-positive verdict/suppression/lifecycle dimensions
  and both direct and service-mediated ranker write denial.
- [ ] Test changed vulnerability, successful removal, actual file relocation,
  disabled rule, parse failure, source omission and resolved reappearance.
- [ ] Inject failure after detection and after an earlier completed identity;
  all detected occurrences remain. Retry must not duplicate/overwrite history.
  Include whole-graph canonicalization failure before any slice work.
- [ ] Test stale lease completion, interrupted transaction, process restart,
  out-of-order scans, forked successors and concurrent decision edits.
  Include new consumer creation racing with capture retirement/cleanup.
- [ ] Integrate real engine adapters, final snapshot/provenance projection,
  Docker worker/API/UI; preserve CWE and origin labels.
- [ ] Demonstrate real Java/Python harmless-refactor decision continuity only
  after the supported analysis/identity policies pass their independent gates.

R07 `component_verified` requires persistence, matching, guard and lifecycle
evidence. R08 `component_verified` requires real asynchronous capture/worker/API
behavior. G2 jointly requires real refactor/rescan history in the live workflow;
neither task waits for the other's whole-task DONE. No SQLite-only/in-memory
test, synthetic strong flag, or successful source parse closes these milestones.

## 9. Design review record

An independent agent review on 2026-09-25 identified seven design gaps: cohort
closure, policy withdrawal, joint revision checks and cleanup fencing, global
identity ordering, engine-specific absence, separate human verdict/suppression,
and API-level ranker exclusion. The revised contract addresses each explicitly.
The agent also read the repository Security Analyst instructions and approved
this **design for implementation planning only**. No runtime grants, API,
database, Compose or real refactor acceptance is asserted. Required canonical
PR review remains separate; security validation must be repeated on implemented
code with real restricted-principal and concurrency tests.
