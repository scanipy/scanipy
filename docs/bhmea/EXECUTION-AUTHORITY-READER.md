# Tenant-local execution-authority reader

2026-09-26. Governing source contract under
[DECISION-BHMEA-01](../DECISION-BHMEA-01-current-execution-authority-2026-09-25.md).
CMP-ORCH-03, coordinated with CMP-CP-03; root-owned #399/#362 remain open.
This document grants no operator installation, migration execution or authority.
It preserves the submitted scope, all historical records and runtime-unsupported.

## 0. Current allocation and precedence

The FIRST slice owns exactly three new files:
`db/migrations/versions/20260926_0008_execution_reader.py`,
`tests/unit/test_execution_authority_role.py`, and this document.
Its base is the reviewed local0007 checkpoint
`85dea23943d4a1053806a4499ee833cf1031cf2d`, tree
`bf24cb894062bd86cb016141f4bfe11c57fcc5a9`.
It implements only an additive database service role and its guarded inverse.
The role, migration and controlled checks are not a reader/factory implementation.

The complete approved reader contracts are retained below so /tmp proposals are
not the sole implementation specification. Their original proposal/evidence
labels remain historical. Current precedence is this section and section1,
then Appendix C over Appendix B over Appendix A. In particular B replaces A's
undecided socket profile, deferred P accounting, spare sixth execute and larger
catalog envelope; C closes B's schema existence/grant-option omission.
Approval of those interfaces does not allocate their future source paths.
The historical unallocated-migration placeholder is now fixed to0008 after0007.

No existing facade, resolver, verifier, codec, model, SQL resource, shared test
fixture, workflow, secret baseline, A2 path, runtime or operator config changes.
Future custody/factory modules and fake/PG/native tests require separate
allocation. All actual PG/UID/socket/keys/current-authority acceptance remains
unrun by this slice; the existing operational verifier stays runtime-unsupported.

## 1. Role-only migration contract

Upgrade0007 to0008 creates only `scanipy_accepted_execution_reader` with
NOLOGIN, NOINHERIT, NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION and
NOBYPASSRLS. It has no password, expiry, settings, membership or ownership.
Only six exact function EXECUTEs and accepted-schema USAGE are granted, without
grant/admin option. The six signatures are Appendix A section3/9's actual
existing owners. R5/R6 are SECURITY DEFINER wrappers with no caller-role string
test requiring alteration; their locks, current checks and original context
are unchanged. This is read-operation-only, not SQL READ ONLY.

Preflight checks the exact0007 predecessor (0008 for inverse), PostgreSQL16 UTF8,
both protected schemas, no colliding role, and all six expected current function
signatures, input/output fields, return types, owner, language, security,
volatility/configuration and bodies. R1/R3 must be the reviewed0007 definitions;
the other four remain frozen0006. Before first mutation take transaction-local
exact object OID/property/body and old ACL-entry snapshots. Existing old grants,
owners, functions and material history are not rewritten or normalized.
Postchecks must prove that only the seven new grant entries were added.
The DO block temporarily uses transaction-local `pg_catalog,pg_temp` search_path
and restores the prior value before Alembic's following revision update. Failure
uses ordinary transaction rollback; no persistent setting or role configuration
is changed. Each of the eight target object ACLs is admitted at at most64 entries
before its normalized old-entry snapshot; this is not a server-allocation bound.

Installer prerequisite: an existing trusted migration administrator operating as
a superuser, with exclusive role/schema DDL custody for the transaction. This
permits complete pg_authid/cluster-wide dependency inspection and avoids
PostgreSQL16 non-superuser creator-membership side effects. No superuser, login
or operator credential is created or granted. Catalog inspection tests password
absence as a boolean; it never fetches/returns password material. SQL output is
no application rows and only fixed non-secret errors. Six target objects,
two schemas and one role bound the retained snapshots; dependency observation
uses a seven-entry allowance plus one overflow sentinel, not an unbounded
returned dependency inventory. Effective-right checks return only booleans.
This is not a fixed PostgreSQL executor/RSS or hard wall-clock guarantee.
The immutable generated upgrade and inverse statements are respectively67,904
and72,619 UTF-8 bytes at this checkpoint; controlled tests bound either below
131,072 bytes. This is source-output accounting, not the future provider P/J/F
budget or proof of database executor work.

The trust boundary is explicit: Alembic's revision is not a persistent original
role-OID anchor. A role-only migration cannot detect malicious same-shaped
drop/recreation by the trusted administrator between migration transactions.
No comment, table or installed OID anchor is invented to claim otherwise.
Within a migration, retain/recheck exact role and object OIDs and metadata.
No collision, mismatched predecessor, unexpected target or uncertain failure
authorizes adoption, automatic cleanup or compensating mutation.

The role's closed state is checked through actual role attributes, no role
membership in either direction or as grantor, no per-role settings, no comment/
security label, exact seven owner-issued nongrantable ACL entries, no protected
schema CREATE/execution-schema USAGE, no extra protected function/table/column/
sequence privilege and no unexpected shared dependency anywhere visible to the
migration administrator. Ordinary public pg_catalog privileges are not claimed
absent. The original mutation-capable resolver permissions remain unchanged.

Downgrade requires the exact current target definitions and closed role/grant
state BEFORE any revoke. Foreign memberships, settings, ownership, grants,
policies or other dependencies (including another database) cause refusal.
The operator must separately detach any installed reader login first.
Then revoke only the six EXECUTEs and single USAGE, prove no remaining role
dependencies, and drop only this role. No CASCADE, DROP OWNED, reassignment,
old-role scrub, table deletion or history-empty requirement is introduced.
Verify all original object/ACL snapshots after the inverse. A failure rolls
back through the ordinary migration transaction; no custom retry is added.

The migration's frozen artifact reads/SQL construction are trusted deployment
inputs, not the future reader's fixed-origin authority interface. Frozen prior
resource hashes and full body/field assertions prevent a moving predecessor
from silently supplying a new target. Source tests must exercise these guards
and actual offline Alembic/dialect literal handling; offline SQL is not a
PostgreSQL syntax, privilege, transaction or catalog execution result.

## 2. Required verification and evidence boundary

Controlled tests cover the exact role/six-signature/seven-grant set, restrictive
flags, collision and revision checks, all-target-before-effect ordering,
unchanged old definitions/ACL projection, no-grant-option/effective-right checks,
bounded foreign-dependency refusal before any revoke, no destructive fallback,
exact downgrade order and offline literal/dialect framing. All existing files
and unrelated ASTs must remain byte-exact.

Separately granted real PG tests must prove actual upgrade/rollback/downgrade,
OID/property/old-ACL/history preservation, every genuine six-read positive,
mutation/helper/bridge/table/CREATE negatives, original-context R5/R6 behavior,
PUBLIC/membership/grant-option drift and foreign database dependencies. Those
tests, reader-harness integration, factory/custody source and native installation
are not implemented or accepted by controlled SQL-string tests.

Primary PostgreSQL16 basis for the migration-only interpretation:
[shared dependencies](https://www.postgresql.org/docs/16/catalog-pg-shdepend.html),
[GRANT](https://www.postgresql.org/docs/16/sql-grant.html), and
[DROP ROLE](https://www.postgresql.org/docs/16/sql-droprole.html).
Plain DROP ROLE would remove memberships automatically, so this contract
requires their prior refusal; it never relies on that implicit cleanup.

## Appendix A — approved full reader allocation contract

The following complete retained record supplies the future source/interface,
custody, original-context and acceptance requirements. Its original proposal
status is historical; only section0's three paths are currently allocated.

## EAR-01 — proposed tenant-local execution-authority reader allocation

Status: OUTSIDE-REPOSITORY PROPOSAL; no source, migration, installation or execution allocation.
Prepared 2026-09-26 from accepted checkout a871c00a9b05299f11b2662dd9bdb3bf841f2afd.
DECISION-BHMEA-01 remains controlling. This is a CMP-ORCH-03 reader extension coordinated with
the existing CMP-CP-03 persistence owner, not a reassignment of DET-02 or a new acceptance gate.
The four pre-existing untracked files in that checkout were neither read for this task nor changed.

### 1. Outcome, dependencies and exclusions

Implement a real, installed, tenant-local `ExecutionAuthorityReader` and a genuine six-read
composition path using the existing accepted-ledger facade. The dedicated database service role
can execute those six read operations and no accepted-ledger mutation. It is **read-operation-only**,
not a SQL READ ONLY transaction: R5/R6 deliberately take namespace/execution row locks.

Keep `verify.run_isolated_verifier()` unchanged and `runtime-unsupported`. Do not register this
reader as a default, call the diagnostic verifier, or return `VerifiedQualifiedRule` from a reader.
No scan-selected callback, supplied trust object, prior receipt, signed document or database row
becomes the installed authority. No A2 signing, publication, pending/head mutation, restore,
operator-adoption, global-bundle or inferred-gate behavior is added by this allocation.

Required dependency order before source integration:

1. Freeze/review the A2 publisher and its public checkpoint layout; preserve its seven owned paths.
2. Resolve the separately allocated 0007 R1/R3 private absence classification. Its public errors, link,
   length and work failures remain unchanged; this reader never treats an arbitrary error as absence.
3. Freeze the separately owned A2 fixture opt-in checkpoint before touching the shared fixture.
4. Assign this migration the actual next free revision **after those dependencies**. The filename
   below is a placeholder, not a reservation of `20260926_0007` or a fabricated migration head.
5. Approve this exact reader/configuration/role contract and finite accounting before implementation.

Pure source and fake fault tests can be built before deployment. Actual PG, dropped-UID custody,
combined factory/PG and eventual verifier/controller activation require separate reviewed grants.
Existing A1 native38 evidence concerns its immutable fa2 source/image, not this new reader.

### 2. Exhaustive proposed file ownership

New files (nine; names subject only to root's allocation approval):

| Path | Sole responsibility |
|---|---|
| `docs/bhmea/EXECUTION-AUTHORITY-READER.md` | Self-contained installed-reader contract and evidence history. |
| `services/scan/accepted_inputs/authority_custody.py` | Fixed-origin public/credential custody, immutable private snapshots, finite FD/lock owner. |
| `services/scan/accepted_inputs/execution_authority.py` | Restricted connection factory, tracked cursor adapter, one-shot six-read composer/reader. |
| `db/migrations/versions/<NEXT_AFTER_B_ABSENCE>_execution_authority_reader.py` | One new NOLOGIN role and exact additive six-function grants; guarded inverse. |
| `tests/unit/test_execution_authority_custody.py` | Bounded parser/FS/lock/clock/cleanup fakes, no real installation. |
| `tests/unit/test_execution_authority_reader.py` | Actual owner codecs plus controlled connection/crypto schedules and failure matrices. |
| `tests/unit/test_execution_authority_role.py` | Migration SQL/collision/upgrade/downgrade static controls. |
| `tests/integration/test_execution_authority_reader.py` | Opt-in real PG role, six reads, races, original-context and rollback assertions. |
| `tests/integration/test_execution_authority_custody.py` | Opt-in isolated fixed-origin/dropped-reader custody; later explicit combined PG cases. |

One existing path, separately serialized after the A2 fixture checkpoint:
`tests/occurrence_store_postgres.py`, only the explicit reader opt-in profile and its owned OID
cleanup. Thus the proposed source slice is ten paths, not permission to edit any A2 source.
No changes to old migrations/resources, models, codecs, verifier, facade, workflow, secret baseline,
historical PLAN/SDD/WBS/submission, runtime controller, renderer, RES or process transport.
Hosted CI wiring is a later explicit allocation; local PG tests are not hosted coverage.

### 3. Actual owner seams to preserve

`models.ExecutionAuthorityReader` is the existing trusted adapter port, with exactly:

```python
runtime_profile: VerifierRuntimeProfile
read_execution_authority(expected: ExecutionBinding) -> ExecutionVerificationContext
recheck_execution_authority(expected: ExecutionBinding,
                            context: ExecutionVerificationContext) -> None
```

The context contains actual `InstalledTrust`, `AdmissionExpectation`, `LedgerExpectation`, original
LIVE bytes and R5's actual `reference_time`. It is an observation, not a capability or durable receipt.
`ExecutionBinding` retains all eighteen fields: ten actual UUID slots; `fencing_token` and
`work_revision` exact ints; four digest strings; two canonical microsecond UTC lease strings.
Snapshot those original slots once before encoding/decoding. Do not repair UUID strings, bools,
mutated nested objects, subclass callbacks or paths by a convenient round trip.

Use the actual owning facade signatures, one public operation per fresh transaction:

| Read | `AcceptedLedgerRepository` method | Closed composer selector |
|---|---|---|
| R4 | `read_request_binding(codebase_id, request_id) -> bytes` | Bound execution's exact codebase/request. |
| R1 | `read_publication_receipt(*, publication_key=None, approval_event_id=None) -> bytes` | Exact approval ID parsed from that R4 SEALED frame; XOR rule unchanged. |
| R2 | `read_exact_bundle(expected: BundleExpectation) -> AcceptedBundleBytes` | Exact tenant-qualified key and SEALED/receipt bundle/content identity. |
| R3 | `read_authority_event(kind, event_id, record_digest) -> (bytes, tuple[bytes,...])` | Literal `execution-authorization`, bound event ID/domain digest; support must be empty. |
| R5 | `read_execution_authority(binding, admission) -> (LedgerExpectation, bytes, str)` | Original binding and independently loaded current external checkpoint expectation. |
| R6 | `recheck_execution_authority(binding, admission, ledger, live, reference_time) -> None` | Exact original R5 tuple, never a newly refreshed context. |

R5/R6 use actual private `v1_read_current`, one existing no-refund SQL meter each, namespace lock,
actual detector bridge and fresh post-final-lock database time. They already check request/seal/run,
planned policy/material, current policy/checkpoint/events, leases and fencing. Their wrapper/private
body does not hard-code `scanipy_accepted_resolver`; no role-test or lock relaxation is needed.
Do not replace them with a table SELECT, cached Python predicate or the old whole-row lock helper.

### 4. Independent fixed-origin installation proposal

New module-owned **configuration** wire types below are proposals, not new authority record types.
Actual trust, runtime, policy, checkpoint, LIVE, SEALED and execution records retain their owners.
Public head parsing consumes the existing A2 `scanipy-local-admission-head/1` layout, with no new
wire version. A2 writer-to-reader conformance tests are mandatory; do not import an A2 admin session
or make private issuer methods the public reader interface.

Proposed fixed origin: `/etc/scanipy/accepted-inputs/reader-startup.json`, root-owned 0444, regular,
nlink1, <=4096 bytes/depth2/64 values. Closed fields: schema literal
`scanipy-installed-execution-reader-anchor/1`, configuration_path, raw_sha256, installation_id,
generation. UUID/digest/path/count slots have actual owner primitive rules; no environment override.

Its separately root-owned 0444 configuration is <=16384 bytes/depth4/256 values, schema literal
`scanipy-installed-execution-reader/1`, and these exact proposed fields:
`installation_id`, `generation`, `reader_uid`, `reader_gid`, `public_gid`, `admin_uid`,
`publisher_uid`, `namespace_id`, `org_id`, `authority_installation_id`,
`authority_configuration_sha256`, `authority_root`, `trust_sha256`, `runtime_profile_path`,
`runtime_profile_sha256`, and `connection`.
`connection` is exactly `{host, port, dbname, user, password_file, socket_uid, socket_gid}`.
No URL, service, options, role selector, search_path, alternate trust, arbitrary SQL or callback.
`host` is one canonical absolute Unix-socket directory, not TCP/DNS. Port is an exact int1..65535;
dbname/user are 1..63 ASCII `[A-Za-z_][A-Za-z0-9_]*`, not executable/SQL fragments. UIDs/GIDs are
exact ints1..2147483647; UUID, positive generation and digest fields use their actual owner shapes.

Reader UID is nonzero and distinct from admin/publisher. Real/effective/saved UID and GID must match
the installed reader identity; supplementary groups are exactly the sorted unique set of configured
public_gid and socket_gid. Require zero CapInh/CapPrm/CapEff/CapAmb and NoNewPrivs1 before private reads.
There is no accepted root invocation, CAP_DAC override, retained admin/publisher privilege or
implicit inherited group. The permitted group set and zero-capability Linux preflight belong
to this reader contract, not the A1 root-bootstrap profile. Test principals are not operator values.

The password leaf is reader-owned 0400, regular/nlink1, 1..16384 bytes, exact UTF-8 without NUL;
do not strip whitespace or output it. Its private directory is reader-owned 0700; trusted root
ancestors are non-writable by group/other. It must be outside authority/public/source/work trees.
The authority root and public-readable files retain the existing A2 admin/public-GID layout.
Reader startup must not enumerate/open `admin/`, `publisher/`, root.pk8, issuer PKCS8, imports or ops.
Connection credentials are new read-service credentials, never one of A2's five privileged routes.

Socket custody is not supplied by libpq's lexical URL parsing. Before any connection, walk the
fixed path with held nofollow descriptors, check configured owner/group and no untrusted write
access, and verify the exact `.s.PGSQL.<port>` socket leaf without following links. A concrete
production socket mode/ancestor profile and server identity binding remain operator decisions;
source allocation must first fix that profile, with no diagnostic/ambient-path fallback.
Successful SQL role/catalog checks complement this custody; they do not authenticate a malicious
replacement local server. Install/restore/old-parent exclusion remain genuine prerequisites.

InstalledTrust is decoded from exact pinned `authority_root/trust.json` using the actual owner;
require `scope == 'customer'` and the installed org/registry/namespace mapping. Read and raw-pin
`root.spki`, then let public verification authenticate its actual RSA profile and trust digest.
Read the pinned runtime profile through the same strict public-file custody and decode the actual
`VerifierRuntimeDocument`/`VerifierRuntimeProfile`. This binds metadata only: no measurement of its
executable/application/dependency trees or operational sandbox is claimed here.

### 5. Public checkpoint custody and time

Use the **same existing** `namespace.lock` inode and SH flock as A2 uses with EX. Own the open before
flock; bounded nonblocking attempts and one monotonic deadline; no lockfile creation/replacement.
Its inherited admin:public_gid0660 mode is retained. The reader never writes it; this is not a claim
that the OS denies all writes to that group-writable lock inode. Head/signature leaves remain0440.
Order is external SH lock before any R5/R6 database lock. Never hold a DB transaction while doing
RSA verification or filesystem synchronization, and never hold a DB transaction across the verifier.

For each R5 and R6 observation, under SH: require no pending.json; exact public/checkpoints names;
complete prefix generation 1..head generation, <=64; no unknown/future/staging names. Every historical
generation has exact directory and four regular 0440/nlink1 leaves with actual owner/group/size
checks. Read current and immediate predecessor bytes only. This is not a historical-content audit.
Do not traverse private A2 subtrees to reproduce its broader administration census.

Head fields are exactly existing schema/installation_id/configuration_sha256/namespace_id/generation/
checkpoint_digest/policy_digest/policy_revision/admission_epoch/installed_at. Bind them to independently
installed authority identity and actual current signed records; domain digests are not raw SHA pins.
Generation1 has no predecessor; later current checkpoint must link exact generation-1 checkpoint.
Do not impose `verify_admin_policy`'s adjacent-policy-revision rule across checkpoint generations:
unchanged policy or multiple separately installed policy revisions do not change that owner rule.

Open through held directories with O_NOFOLLOW/O_NONBLOCK/O_CLOEXEC. Full held/named leaf and measured
directory stamps include device/inode/type/mode/UID/GID/nlink/size/mtime/ctime. Walk ancestors with
identity/security projection, not volatile sibling mtime/size. Reject foreign mounts, symlinks,
hardlinks, truncation/growth, aliases and unknown membership. Synchronize opened public head/current/
predecessor closure and relevant directories, then re-read exact bytes and stamps before usable
return. No check-then-path-reopen, metadata-only content proof, mutation, repair or durable ack.

Use `verify_admin_admission(current, trust=..., root_spki=..., policy=current_policy,
previous=immediate_predecessor_checkpoint_or_None)` once to authenticate the actual adjacent
checkpoint relation. It also authenticates current policy; the unused predecessor-policy signature
is retained/read exactly but is not advertised as a separately authenticated historical policy.
Build an actual LIVE frame from the four current role bytes with actual owner encoding; compare the
R5-returned LIVE roles/manifest exactly. Use `verify_admin_current` at local-before-R5, actual R5 DB
reference time, and local-before-R6. All three authenticate current permission at those instants.

UTC samples are actual local clock reads before/after each phase, never caller inputs. Reject local
backwards movement, expired/block permission and lease expiry at final local checks. R5's canonical
database time stays unmodified; R6's existing SQL checks fresh post-lock database time and original
context. Do not assume an undocumented zero-skew relationship or fabricate a database timestamp.
Release SH only after required local/current byte checks. Between R5 and R6, release locks/resources;
reacquire and demand the exact original installation/head/role bytes. A successor is stale for that
reader, not permission to replace its original context. Both observations are finite point-in-time
checks, not atomicity across all stores or continuous permission after return.

The external head remains independent highwater, not the highest signed directory or a DB row.
Both-store rollback cannot be detected from these bytes alone. Operator-qualified independent
backup, restore block/new epoch and old-parent exclusion remain unavailable; no reader recovery,
block-to-admit transition, config/root rotation or automatic retry/adoption is included.

### 6. Restricted factory and exact once-only ownership

Proposed role name `scanipy_accepted_execution_reader`: NOLOGIN, NOINHERIT, NOSUPERUSER,
NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOBYPASSRLS; no ownership/grant option. Installer separately
creates the named login with only SET capability to this role, no other protected role/membership.
No admin/resolver credential is accepted because it can also perform these reads.

Each of six operations uses one newly connected/discarded connection, never a pool or caller
connection. Supply closed keyword arguments to the actual DB driver, bounded connect_timeout,
application_name and initial timeout options. Clear/override all ambient PG/service/passfile/options
inputs before driver entry; no DSN output. A psycopg2 connection context is not a close owner.

Private prelude sets the transaction to READ COMMITTED/READ WRITE, SET LOCAL ROLE to the fixed new role, and
performs a fixed bounded catalog assertion: actual login/current-role identities, attributes,
protected memberships, schema usage, exact six read privileges, no seven mutation/initializer/
private-helper/table/sequence/CREATE/execution-bridge privileges or grant option. Capture exact
qualified function OIDs/signatures; no caller-selected introspection. Ordinary built-in pg_catalog
permissions are not misdescribed as forbidden. The catalog response is one fixed tuple, <=16384
encoded scalar bytes/256 values; no full function definitions or unbounded row iteration is fetched.
Tenant isolation still requires installed org/
namespace dispatch: the role's function set alone is not a per-tenant database capability.

Then use unchanged `accepted_ledger_transaction(factory, namespace_id, org_id)` and unchanged
`AcceptedLedgerRepository`. Facade construction installs actual namespace/org/timeouts. Its one
public `_call` retains fixed SQL, row count/EOF, stored-content and original driver-error semantics.
Return a result only after its transaction's successful commit AND owned connection/cursor closure.
Commit ambiguity, rollback/close failure or interruption yields no successful result and no retry.

The existing facade `_cursor` acquires before its own try. Do not claim that it alone closes the
acknowledged-acquisition boundary. The new factory-local adapter has a preinitialized guarded
registry of at most THREE raw cursors: prelude/catalog, facade constructor, facade public read.
Store each returned raw cursor in that registry before giving its private proxy to the facade.
Mark a proxy's close attempt BEFORE calling the actual raw close. Factory exit attempts each
outstanding cursor once, then the connection once. Successful early closes are not repeated;
uncertain close is never retried by number/object. Fail closed after any uncertainty.

Use actual `sql_adapters.Connection`/cursor structural methods only, delegating unchanged SQL and
driver exceptions. This is not a generic public database wrapper. Guard raw connect/cursor acquisition
and every acknowledged handoff inside the owning try. Preserve original exception identity and its
prior explicit cause, otherwise implicit context, alongside cleanup errors. Attempt later owned
cleanup even when an earlier close fails. Do not claim arbitrary-signal atomicity between opcodes.

Exact maximum per transaction: one connect, three cursor acquisitions/closes, at most six fixed
SQL executes (SET TRANSACTION; SET LOCAL ROLE; catalog; facade set_config; one facade operation; no sixth
business query), one commit, at most one rollback, one connection close. Across six operations:
six connections, eighteen cursors, <=36 explicit executes, <=6 driver implicit BEGINs, <=6 commits
and <=6 rollbacks. Do not hide transaction protocol commands inside the explicit-execute count.
No F read nesting.
The sixth execute credit is spare for the fixed prelude implementation, not an optional API query.
Final SQL text/count/catalog row envelope must be reviewed before implementation acceptance.

### 7. One-shot public composition and immutable original context

Proposed sole factory API (new, not already implemented):

```python
@contextmanager
def installed_execution_reader(*, expected: ExecutionBinding,
                               qualified_rule: QualifiedRuleKey
                               ) -> Iterator[InstalledExecutionReader]: ...
```

`InstalledExecutionReader` has a private constructor, immutable actual `runtime_profile` and
`resolved: ResolvedQualifiedRule` properties, and exactly the two existing protocol methods.
Public arguments are requested identities, not authority. No root/path/DSN/role/clock/factory/trust
parameter, test-mode flag or public direct constructor. Unit substitutes bind private dependencies.

Enter snapshots exact primitive inputs and installed configuration, then performs R4,R1,R2,R3 in
that order. Check actual key/customer/registry/bundle/content/version/qualified-member membership;
all detector/rule/model members are retained once in the actual bundle, not filtered to fit schema.
R1 receipt must byte-equal SEALED's publication-receipt role. R3 must be actual EXECUTION, not DENIAL,
and each original binding field must match its owner mapping (`authorization_event_id` -> event_id;
authorization_digest -> owner domain digest). No absent-run/adoption or synthetic evidence branch.

Construct `ResolvedQualifiedRule` with the genuine full bundle, original SEALED, original execution
record and original binding; its constructor/selected-content work is charged, not trusted by type.
It is not a verified result. State is MATERIAL_READY; one R5 transitions to CONTEXT_READ, one R6 to
RECHECKED. Any failure makes the handle unusable except once-only close. Wrong-order/second method
calls reject before DB effects, preserving spent counters and original context.

R5 must bind ledger publication_receipt_digest to actual PUBLICATION **domain** digest;
request_binding_digest to exact SEALED **raw** digest; execution_authorization_digest to original
EXECUTION **domain** digest; binding exact; current policy/admission event IDs to returned LIVE.
Also compare full returned LIVE to independently loaded public current bytes/expectation.
Create the actual `ExecutionVerificationContext` only after this and successful transaction exit.
Privately retain a detached original snapshot of every context field/byte; no mutable alias.

R6 first independently snapshots the supplied context's original typed slots and demands exact
equality with that retained original, including time, LIVE, IDs and all binding fields. It does not
accept a same-binding freshly fetched LIVE or silently refresh external checkpoint expectation.
Call R6 with those original values, perform final public/local-time checks, and acknowledge only
after successful commit/close. Context object identity is not the authority check.
No lock, credential or connection is exposed to `verify_resolved_qualified_rule`; that existing
consumer remains runtime-unsupported at its operational verifier step after obtaining context.

### 8. Aggregate admission, work and limitations

The following are proposed **new reader** composition ceilings, not increases to A2/AL owner caps.
Reserve before each actual delegate, including failure/malformed branches; no cache/refund discount.
One lifecycle has ONE local P preparation meter, at most SIX F facade tickets, FOUR V public
verification tickets (one admission, three current), and no C command ticket/signature operation.
Each P/F/V reserves its existing-style <=100000 SHA calls/134217728 bytes; the owner's stricter
actual schedule still applies. P pays every direct codec/model/qualified-member/domain operation.
FS raw hashes separately <=128 calls/16777216 bytes. Aggregate explicit client SHA reservation is
therefore <=1100128 calls/1493172224 bytes. RSA-internal hashing is separate: <=32 public key loads,
<=48 verifies across four V tickets, ZERO signing/private-key loads. These are ceiling reservations,
not measured actual work, allocator/RSS limits or a promise every maximum-size input completes.

P preflight must use actual owner's helper schedules, not the constructor's output or reported count.
With M models, D detectors, R rules, U model bytes, T content bytes, W detector+rule bytes,
A=1048576, O=65536 and actual domain prefix lengths p/q: decode_spec reserves discovery before
hashing; bundle validation pays M/U; accepted_content_digest pays M+3+D+R and U+T+2*(A+p);
qualified_members pays 3M+3+2D+3R and 3U+T+W+2*(A+p)+R*(O+q). Resolved construction includes its
own bundle validation AND selected_content/qualified_members pass. Frame encode and decode each
pay their role hashes independently. Raw SHA, domain prefixes and failed candidate work count.
`decode_document`, `decode_record`, canonical metadata and PosixPath snapshots are not blanket
hash-free pipelines: direct metadata JSON has no SHA, but nested constructors can invoke owners.

Selected successful facade output maximum (excluding the separately bounded six catalog tuples) is
R4 A + R1 O + R2 A + R3 O + R5 (O+262144+27) = 2555931 bytes. R6 is the exact void-row result.
The selected R3 has no support; generic R3's existing larger cap stays unchanged. No frame trailers,
partial arrays, missing-as-empty results, repeated reads, metadata reconstruction or hidden copies.
The six catalog tuple allowance adds at most98304 scalar bytes, making2654235 total selected
returned scalar/payload bytes; repeated local copies still consume the separate copy accounting.

Six separate SQL owner meters retain their actual per-call caps; aggregate ceilings, not one reset:

| Existing SQL bucket | Sum for R4,R1,R2,R3,R5,R6 |
|---|---:|
| Explicit SHA calls / bytes | 600000 / 805306368 |
| Raw fetched bytes, using unchanged generic R3 cap | 14811136 |
| Control representation bytes | 17301760 |
| Relational representation bytes | 8650948 |
| JSON image bytes | 3221225472 |
| Canonical byte work | 12884901888 |
| History/control census bucket | 393216 |

The SQL raw fetch bucket and its companion fetched-length bucket have the same per-route ceiling;
do not merge/refund them or advertise these sums as PG memory allocation. R5/R6 retain their actual
5701632 raw /8519808 control /131106 relational budgets and one bridge reserve each.

Proposed reader FS/application ceilings: 64MiB cumulative file reads, no writes, 32768 counted
filesystem calls, <=32 simultaneously held FDs, <=16MiB retained application raw-byte buffers,
<=512 public names and <=64 checkpoint generations. This new aggregate call allowance includes
initial fixed configuration/credential/profile reads, two full public metadata observations,
paid current/predecessor rereads, six connection custody checks and once-only cleanup. No relaxed
per-leaf/record/path limit; paths remain <=4096 UTF-8 bytes/128 components. Driver network syscalls
are not dishonestly counted as these explicit FS calls.

Before code acceptance, instrument the actual fixed walk/entry/read/close schedule, including
64-generation and maximum-path positives, to demonstrate it fits those ceilings. Account separately
for parser tagged slots/cumulative copy work versus retained bytes. Neither existing F/V meters nor
this proposal prove total Python/driver/PG heap; the exact implementation's copy/slot ledger and
external memory enforcement are required evidence, not grounds to invent a heap guarantee.

Proposed one lifecycle deadline: 120s from before argument/config work, 118s work and 2s cleanup
reserve; never reset at R5/R6 or following malformed input. SQL statement/lock caps stay15000/2000ms;
connect<=2s. Admit each SQL/commit phase only with its whole fixed timeout and cleanup remaining.
Check before/after crypto, custody and SQL. Waiting for the still-unimplemented verifier consumes
this same lifecycle time; a slow use is unavailable, not a renewed reader lease.
Blocking kernel/libpq/crypto/rollback/close cannot be made hard-bounded by elapsed-time checks alone.
An actual compatible supervision/termination ownership contract remains necessary for activation;
do not return successful authority on cleanup timeout or silently reuse a possibly live connection.

### 9. Additive migration and fixture behavior

Upgrade preflight rejects a pre-existing new-role name, unexpected function signatures/owners or
unsupported dependency revision. No adoption of a similarly named role. Create only the new role;
grant USAGE on `scanipy_accepted_inputs` and EXECUTE on exactly these existing signatures:

```text
read_publication_receipt_v1(uuid,uuid,uuid)
read_exact_bundle_v1(uuid,uuid,bytea)
read_authority_event_v1(uuid,text,uuid,bytea)
read_request_binding_v1(uuid,uuid,uuid,uuid)
read_execution_authority_v1(uuid,bytea,bytea)
recheck_execution_authority_v1(uuid,bytea,bytea,bytea,bytea,text)
```

No table/column/sequence privilege, schema CREATE, initializer, seven mutation functions, private
helper, `scanipy_execution` USAGE/bridge, admin option, grant option or PUBLIC grant. Existing five
roles, exact function bodies/owners/search_path, RLS, triggers, locks, budgets and ACL entries stay
byte/semantic unchanged except the six additive ACL entries and new schema-USAGE entry.
Do not run 0006's broad new-object ACL normalization over existing objects during this upgrade.

Downgrade validates exact new role attributes, grant set and identity; any external membership,
ownership, unexpected grant or dependency stops it. Operator must first detach the service login.
Revoke only this migration's six EXECUTEs and one USAGE, then drop only this role. No CASCADE,
DROP OWNED, old-role ACL scrub, table/row deletion or downgrade of earlier B/AL migrations. Existing
material history does not require deletion to remove this role; original migrations keep their own
separate nonempty-history downgrade guards. Test upgraded and populated downgrade preservation.

Shared fixture coordination is explicit: canonical's proposed
`PrivatePostgres(url, profile='accepted', administration=False, migration_cwd=None)` is not yet a
stable implementation. Its default accepted0006/10-login and administration0006/13-login profiles
must remain unchanged. Proposed later `authority_reader=False` is an exact bool, accepted-only,
mutually exclusive with administration, with a closed reviewed target revision (never arbitrary
caller migration names). Begin from accepted setup, apply the eventual reader dependency chain,
then add one short owned login for the new role. Record each successful role/database OID before
grant/use; pre-existing name or failed migration never authorizes cleanup/adoption.
Existing occurrence0005/6-login profile, old role schedules and cleanup remain exact. Both reader
integration modules register the same fixture plugin, not separate imported FixtureDefs. The
production fixed-origin factory is not bypassed to call a diagnostic reader in native tests.

### 10. Required verification, and what remains unchosen

Unit/fake matrix: exact original typed-slot corruption; missing vs empty rows; every role/digest/link;
full bundle including multi-profile raw inventory without selecting unsupported coverage; repeated
R5/R6, foreign/same-shaped/rebuilt context; UTC backwards/lease/permission endpoints; full64 prefix;
pending/future/missing/unknown public names; same-length current/predecessor mutation; symlink,
hardlink, mount, permission and lock replacement; all acknowledged open/cursor/connection handoffs;
every close failure/uncertain-close combination with primary cause/context; commit+rollback failure;
no second close/SQL/retry after failure. Exercise actual owner helpers, meter all delegated work,
malformed maximal values and explicit raw/slot/copy/FD/name/time limits. Fakes are not native proof.

Real PG opt-in: all six methods succeed with the **new** role on genuine committed fixture rows;
all seven mutations, initializer, direct DML/no-op/delete/truncate, private helpers, CREATE,
SET ROLE to old privileged roles and bridge access fail with exact operation-specific expectations.
Old reader still cannot R5/R6; old resolver retains its original writes. Test exact new-role catalog,
tenant foreign-scope existing keys, original R5/R6 bytes, policy/checkpoint/lease/fence/run changes,
namespace wait/time advancement, malformed stored records and no lower-row adoption. Compare full
logical row/catalog snapshots before/after rollback; normalize bytea bytes without weakening equality.
Upgrade collision/rollback, exact-grant downgrade and unrelated role/object/OID preservation are required.

Native opt-in: isolated root bootstrap installs the REAL fixed reader origin/public layout and a
separate dropped reader identity; no host installation/keys/UID changes. Prove no private issuer/root
PKCS8 access, actual SH/EX contention, readonly public behavior, exact group/cap/FD preflight and
real acquisition/read interruption/once-only cleanup. Use actual disposable public signatures from
reviewed setup; no signing API exists in this module. Combined real factory+PG tests need their own
bounded socket/login resource grant and cleanup proof, not merely a fake connection or mocked OS.

Unchosen before production: actual reader/login/UID/GID/socket identities, anchor/config generation,
namespace/org mapping, database/server custody, runtime artifact pins, independent-backup/restore
operator, old-parent exclusion, outer blocking-operation supervisor and capacity/memory qualification.
No values are inferred from test identities or current containers. No automatic installer, cleanup
of unknown residue, SQL mutation or global/inferred extension fills these gaps.
Repository source allocation can proceed only after root resolves the exact proposed fixed socket
profile and approves the new aggregate accounting/interface; operator activation remains separate.

### 11. Reproducible source pins and evidence provenance

Read-only source snapshot a871c00a9b05299f11b2662dd9bdb3bf841f2afd; SHA256:

```text
models.py             baa597f021f6bb41615fcbc8b0dd494dae1d16e8651cfea2489546db808c1d78
verify.py             830bedb2b2428a717fd75cb08b8c071b6383eda2591fdfd5eed2356ce0949460
codec.py              208aaa6bdef29d6f0e7d689da036b75be07c9dddfa2e999bf5a5d7f575eff5e2
schemas.py            6546703c50c6b200283e2946c421988485d1ddbde2dca508dc4e1724e714a509
ledger_repository.py  e39d1f9a337b8cab28fcb3ab0369e4ca556f1dbc8d2b96cbf9b40b0e420716eb
0006 migration        e72cd56841dfe001958f03356f0366b03b2a63ac9bea3c0f7c7c8652f9957842
accepted_v1_reads.sql c7cead1435acf3f2c35c7a24979f10bcf964809b890c17fdac2ed2ff09340e18
operations.sql       795d7b41c8f320de3e80782abef1375fd456b4be5214c61ea6417f5a372d90e7
acl.sql              c9cc9c65a673f8c704aa4f0ceab4f76abc95303228256546b0103b0d29b7b2ca
validation.sql       3f61298ad1b142a4aae39e71b4dbbdcb0ba4a30bae431c63ff9e0e19fe5927d0
PG fixture           f3e1e1b207c32dc2cb680a9916dfcaa3a38d1c9b83b36db1682d0400593aeed2
resolver contract    adf758066315539af8736738792809541c4d89411efe0512d764663677a859a4
AL SQL contract      46eae809608c00e6ba3777ee1d23b1a9b5f4e4c59e2c3dc2b412b4479db8b71a
```

Code paths above are under `services/scan/accepted_inputs/`, SQL under `db/migrations/versions/`,
fixture at `tests/occurrence_store_postgres.py`; governing docs are actual
`docs/bhmea/ACCEPTED-INPUT-RESOLVER.md` and `docs/bhmea/ACCEPTED-LEDGER-SQL.md`.
V2/V3 outside contract hashes: 48cb40b4c8bdcb79e3acb1ccc7c5cd14b0cf3413e8335145f793362c51d056ba /
5f0e3a971ec7cbf4c3c3f68c265b0542a4a6f3eeee0db235b140e5fab4e03b69.
Coordinated A2 harness proposal (not applied):
`/tmp/scanipy-a2-harness-allocation-SjP4B4Al/A2-HARNESS-ALLOCATION-01.md`,
SHA4f5e68065a30f36a2b9d69b65bc59a6e32273260f64999d8dcc7176ca34dc3f3.
This note has no executed test/PG/native result and makes no source or full-scope approval claim.

## Appendix B — approved socket, P-accounting and exact catalog revision

## EAR-02 — fixed socket, preparation accounting and catalog contract

2026-09-26; OUTSIDE-REPOSITORY DESIGN REVISION, not a code or operational grant.
EAR-01 remains byte-exact at SHA256
f2866b07739522d663d910527046ab5fa81627f3866c401adca9bb0a11f86ca5.
This revision replaces its undecided socket profile, vague catalog/prelude allowance and deferred
P parser/copy admission. All other EAR-01 scope, ten proposed paths, source pins, six-read order,
original R5/R6 context invariants, failure rules, tests and runtime-unsupported exclusion remain.
In particular, this does not change A2, the old facade, old SQL bodies, verifier or runtime limits.

### 1. Fixed installation/socket decisions

The independent reader anchor/configuration and actual owner trust/runtime records are unchanged
from EAR-01. UID/GID slots are exact positive integers <=2147483647, not selected from the caller,
ambient environment or current test container. Add these exact relationships:

- `reader_uid` differs from `admin_uid`, `publisher_uid` and `connection.socket_uid`.
- The socket directory is exactly `socket_uid:socket_gid`, mode0750, a real directory.
- Its exact leaf `.s.PGSQL.<decimal port>` is S_IFSOCK, `socket_uid:socket_gid`, mode0770, nlink1.
- Every ancestor is owned by UID0 or that installed socket_uid and has no group/other write bits;
  reject symlinks, procfs-FD paths, foreign devices below the selected socket root and aliases.
- The reader's real/effective/saved UID/GID, sorted supplementary groups `{public_gid,socket_gid}`,
  zero CapInh/CapPrm/CapEff/CapAmb and NoNewPrivs1 are checked before credential reads.
  No assumption that its primary GID implicitly supplies a missing supplementary group.

Walk components with held nofollow/CLOEXEC directory FDs; retain the selected directory FD and
the validated chain's identity/security projections. Immediately before and after **each connect**,
recheck held directory identity, named directory identity and named socket leaf identity/metadata.
The leaf is never opened as a regular file. A socket replacement, mode/owner change, stale held
path, reconnect or vanished leaf invalidates the reader; close the acknowledged connection once.
Connect still uses libpq's fixed absolute socket path. These checks do not bind a libpq connect to
a held-directory FD at the kernel API level. The installed server UID and root are trusted not to
substitute the server during that interval. SQL catalog agreement alone is not server authentication.
SO_PEERCRED can be assessed later if that trust model changes; no generic transport is added here.

The password remains an independent reader-owned0400/nlink1 leaf in its reader-owned0700 private
directory. No A2 credential, root key, issuer key or admin/publisher session is accepted. Root/server
socket custody, the actual configured server process and backup separation are installation facts,
not inferred from a JSON signature or observed catalog. No values are supplied by this proposal.

Explicit root-key linkage: decode the exact `trust_sha256`-pinned trust.json into actual
`InstalledTrust` after its original slot/schema checks. Its `root_spki_sha256` is the expected raw
SHA256 of the held root.spki bytes. Precharge that raw hash and require exact equality before any
public-key load. The independent configuration needs no duplicate root-SPKI digest field.
The existing public verification helper then checks the actual root RSA profile/signatures.

### 2. Preparation accounting: definitions and enforceable limits

There is ONE P ledger for the entire existing120s lifecycle, created before argument/config work;
118s work plus2s cleanup, no phase reset. Existing P/F/V SHA and crypto limits from EAR-01 remain.
This adds explicit preparation parser/copy admission; it does not alter existing F/V internals.

P has these monotonically spent counters, tested before the corresponding action:

| Counter | Whole-lifecycle ceiling | Meaning |
|---|---:|---|
| `p_slots_reserved` | 536870912 | Conservative logical tagged/container-member slots admitted for direct P work and P-owned delegates. |
| `p_copy_reserved` | 17179869184 | Conservative cumulative bytes of P decoding/encoding/snapshot/frame-copy work. |
| `p_own_slots` | 1048576 | Actual reader-created primitive/tuple/list/dict/member slots; also charged to p_slots_reserved. |
| `p_own_copy` | 536870912 | Reader-created/decoded/encoded/sliced/joined byte/text capacities; also charged to p_copy_reserved. |
| `live_raw_capacity` | 16777216 | Simultaneously retained reader raw-byte buffers, including adopted owner results. |

These are logical admission/reservation counters, NOT CPython allocation counts, heap/RSS, total
driver/server copies or measured CPU work. The large cumulative reservation is intentionally not
a simultaneous memory allocation. Freed buffers reduce only live_raw_capacity, never spent work.
F facade and V verification work are still separately reserved as complete owner tickets before
entry. Their bounded returned bytes are charged when adopted by the reader; their internal copies
are not silently called P work or claimed to be measured by P. SQL keeps its separate EAR-01 meters.

For reader-owned work, charge destination capacity BEFORE making each bytes/text copy, slice,
decode, encode, join or snapshot. A comparison charges the examined byte extent as copy-work even
if Python performs no copy. Charge every tuple/list/dict element or key/value destination slot
before insertion. Repeated logical roles/readbacks charge again, even when immutable bytes alias.
All exceptions consume prior reservations; no refund/cache credit or successful-result counter.
UTF-8 conversion uses a bounded pre-admitted output extent, not `encode()` followed by a size check.
Foreign dataclasses/paths are detached by exact original primitive slots before owner invocation.

The following closed delegation recipes reserve both counters BEFORE invoking an existing helper.
`B` is a checked byte extent and `V` a checked upper bound on tagged JSON keys+values/containers.
For owner JSON raw input use `V=min(20000,B)`; for private anchor/config/head parsing pass its
actual stricter max_values/depth to public `decode_bounded_json` and use that smaller bound.
No tree is first parsed to discover the budget. Owned dictionary inputs are counted while built.

```text
J(B,V) = (slots 64*V + 256,
          copy  64*B + 1024*V + 65536)
R(B,V,K) = 2*J(B,V) + (8192*K, 262144*K)
Spec(T,M) = J(T,min(20000,T)) + (2*M+16, 2*T+8*M)
Frame(B,k) = (64*min(40000,B)+256*(k+1)+8*(k+1),
              68*B+1024*min(40000,B)+65536*(k+1)+128*(k+1))
```

`J` covers one bounded JSON/document/canonical helper, including its primitive preflight, parser
object-pair staging/unique-object map, scalar UTF-8 checks, shape/uniqueness scratch, canonical text
and byte results. The64 multipliers and per-value1024 term are conservative credits for these
fixed source passes, not a claim every input performs64 copies. They also cover rejected duplicate,
noncanonical, invalid-scalar and first-over-limit branches. Text bytes use UTF-8/worst output extents;
the ledger makes no one-byte-per-Unicode-codepoint assumption.
`R` covers a record_dict/decode_record/constructor snapshot pair, including nested binding, with
`K` pre-admitted PosixPath occurrences; path part-list and repeated 4096-byte normalization work is
charged by its explicit additive term. It is not applied to AcceptedBundleBytes/ResolvedQualifiedRule.
`Spec` covers actual decode_spec: document decode plus part slices/model tuple slots and framing.
`Frame` covers actual encode_frame OR decode_frame, including encode's validating decode, part
slices and role document decodes. A failed frame can decode a final20000-value object after an
accepted prefix of20000 values before aggregate rejection; the40000 term covers that branch.
Metadata/object extents together are bounded by the frame input/output B; binary signatures/SPKI
are included, and `k` is exactly4 LIVE or15 SEALED roles. Each additional helper call reserves anew.

P's sole composite resolved-constructor recipe is `Q`; it must be reserved before calling the
actual `ResolvedQualifiedRule` constructor, not reconstructed from its result. Let actual bounded
spec/model/detector/rule inventory counts be M,D,R, total content T<=1048576, and detector lengths
b_i. Each d_i=min(20000,b_i); sum(b_i)<=T; sum(d_i)<=T. Use independently bounded counts before
discovery when necessary and reject before the delegate if this conservative reservation will fail.

```text
Q = 4*Spec(T,M) + 3*J(1048576,20032)
    + sum_i J(b_i,d_i)
    + R*(J(1024,16) + J(4096,64)) + 2*J(4096,64)
    + (16*(M+D+R)+256, 128*(M+D+R)+65536)
```

Source mapping: the actual constructor/selected_content/qualified_members path performs four
decode_spec passes (outer bundle check, qualified_members bundle check, explicit decode_spec,
accepted_content_digest bundle check); accepted-content envelope encoding/reparse is covered by
three J envelopes, including its actual occurrence owner; each detector has one document parse;
each rule has one fixed semantic document encode and one bounded QualifiedRuleKey construction.
There are two selected-key encodes, plus model/member maps and result/match tuple/list slots.
The per-key4096/64 and semantic1024/16 extents follow their closed actual fields, not arbitrary
16384-byte schema strings. No selected-content properties are called again by this reader.

Full P delegate schedule ceilings are: <=48 simple J calls with B<=131072,V<=20000;
<=16 R calls with B<=65536,V<=256 and SUM(K)<=64; <=6 Frame calls with B<=1048576,k<=15;
<=2 standalone Spec calls for bounded count discovery/detached bundle construction;
and exactly one Q for successful material assembly. Private metadata, trust/profile/public records,
original binding/context snapshots and P frame work all consume these same counters. They are
finite maxima, not permission for new business reads or a per-method fresh allowance.
The implementation must label each callsite with this existing closed category; an unlisted
compound owner helper is unavailable until its recipe is reviewed. F/V entries do not count as
simple J/R calls, and their outputs do not authorize a second uncharged constructor.

A conservative arithmetic envelope, even using independent M=D=R=20000 despite actual combined
constraints, T=1048576, sum(b_i),sum(d_i)<=T, gives Q<=194965824 slots/13896250368 copy bytes.
Adding the entire48J+16R+64-path+6Frame+2Spec schedule and full own-work allowance gives
276549344 slots/16843146752 copy bytes, below the fixed536870912/17179869184 ceilings.
This demonstrates that the reservation profile itself does not exclude the maximal bounded
inventory merely because no precise count has yet been parsed. Existing SHA/schema constraints
still independently reject invalid or overly expensive members; no weakened owner limit follows.

Retained buffers remain separate: pre-reserve capacities for fixed-origin/public reads, current
and predecessor closures, complete bundle, SEALED, EXECUTION, LIVE, original context and output
staging. The six facade outputs retain EAR-01's2555931-byte aggregate bound; no all-history byte
read or inventory copy is introduced. Keep only counted immutable snapshots; never source a
budget decision from a caller-supplied count, digest cache, filesystem path, or decoded object's
overridable method. Small source-level instrumentation tests must verify every actual P helper
entry/category and own allocation charge, including failure paths, before source approval.

### 3. One fixed catalog statement and five explicit executes

The login has one direct membership in `scanipy_accepted_execution_reader` with SET TRUE,
INHERIT FALSE, ADMIN FALSE; both identities are non-superuser, NOINHERIT, NOCREATEDB,
NOCREATEROLE, NOREPLICATION and NOBYPASSRLS. The service role is NOLOGIN and a member of no role.
The login is not an owner of either protected schema/object. The configured local server/root
remain trusted administrators; these are effective privilege checks, not defense against that
server lying about its catalog. Built-in pg_catalog permissions are not claimed absent.

One prelude cursor executes, in order:

1. `SET TRANSACTION ISOLATION LEVEL READ COMMITTED READ WRITE`
2. `SET LOCAL ROLE scanipy_accepted_execution_reader`
3. The single fixed catalog SELECT below, with only expected login/database bound values.
Then the unchanged facade constructor's set_config SELECT is execute4, and exactly one closed
facade R1..R6 call is execute5. There is NO sixth/spare query. Each operation has one implicit
driver BEGIN, at most one commit and at most one rollback, all counted separately from executes.
Across the reader: six connections, eighteen cursor acquisitions/once-only closes,30 explicit
executes,<=6 implicit BEGINs,<=6 commits,<=6 rollbacks,<=6 connection closes. No pooled connection.

Connection options fix statement_timeout15000, lock_timeout2000 and connect_timeout2 before
prelude execution. Facade construction retains its own same timeout settings. The connection is
not SQL READ ONLY. Driver-version/profile compatibility is tested, never inferred from those options.
The catalog targets PostgreSQL16's actual membership option columns; another major version is
unavailable until this exact query/profile is reviewed, not an automatic permissive fallback.

This is the proposed exact query, not executed SQL. `$LOGIN` and `$DATABASE` below are the only
bound parameters (implementation uses the driver's `%s` placeholders, never interpolation):

```sql
WITH expected(ord,signature) AS (VALUES
 (1,'read_publication_receipt_v1(uuid,uuid,uuid)'),
 (2,'read_exact_bundle_v1(uuid,uuid,bytea)'),
 (3,'read_authority_event_v1(uuid,text,uuid,bytea)'),
 (4,'read_request_binding_v1(uuid,uuid,uuid,uuid)'),
 (5,'read_execution_authority_v1(uuid,bytea,bytea)'),
 (6,'recheck_execution_authority_v1(uuid,bytea,bytea,bytea,bytea,text)')
), allowed AS (
 SELECT ord,pg_catalog.to_regprocedure('scanipy_accepted_inputs.'||signature)::oid AS oid
 FROM expected
), identities AS (
 SELECT l.oid AS login_oid,r.oid AS role_oid,
   pg_catalog.to_regrole('scanipy_accepted_owner')::oid AS owner_oid,
   (l.rolcanlogin AND NOT r.rolcanlogin AND NOT l.rolinherit AND NOT r.rolinherit
    AND NOT l.rolsuper AND NOT r.rolsuper AND NOT l.rolcreatedb AND NOT r.rolcreatedb
    AND NOT l.rolcreaterole AND NOT r.rolcreaterole
    AND NOT l.rolreplication AND NOT r.rolreplication
    AND NOT l.rolbypassrls AND NOT r.rolbypassrls) AS attributes_ok
 FROM pg_catalog.pg_roles l CROSS JOIN pg_catalog.pg_roles r
 WHERE l.rolname=session_user AND r.rolname=current_user
), checks AS (
 SELECT i.*,
   (SELECT count(*)=6 AND count(DISTINCT oid)=6 FROM allowed) AS six_ok,
   (SELECT count(*)=1 AND coalesce(bool_and(m.roleid=i.role_oid AND m.set_option
       AND NOT m.inherit_option AND NOT m.admin_option),false)
    FROM pg_catalog.pg_auth_members m WHERE m.member=i.login_oid) AS login_membership_ok,
   NOT EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members m WHERE m.member=i.role_oid) AS role_membership_ok,
   NOT EXISTS(
     SELECT 1 FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
     WHERE n.nspname IN ('scanipy_accepted_inputs','scanipy_execution') AND
       (pg_catalog.has_function_privilege(i.role_oid,p.oid,'EXECUTE')
         IS DISTINCT FROM (p.oid IN (SELECT oid FROM allowed))
        OR pg_catalog.has_function_privilege(i.role_oid,p.oid,'EXECUTE WITH GRANT OPTION')
        OR pg_catalog.has_function_privilege(i.login_oid,p.oid,'EXECUTE')
        OR p.proowner IN (i.role_oid,i.login_oid))) AS function_rights_ok,
   NOT EXISTS(
     SELECT 1 FROM allowed a LEFT JOIN pg_catalog.pg_proc p ON p.oid=a.oid
     WHERE p.oid IS NULL OR p.proowner<>i.owner_oid OR NOT p.prosecdef
       OR p.proconfig IS DISTINCT FROM
          ARRAY['search_path=pg_catalog, scanipy_accepted_inputs, pg_temp','bytea_output=hex']::text[]
   ) AS definitions_ok,
   NOT EXISTS(
     SELECT 1 FROM pg_catalog.pg_namespace n
     WHERE n.nspname IN ('scanipy_accepted_inputs','scanipy_execution') AND
       (n.nspowner IN (i.role_oid,i.login_oid)
        OR pg_catalog.has_schema_privilege(i.role_oid,n.oid,'CREATE')
        OR pg_catalog.has_schema_privilege(i.login_oid,n.oid,'CREATE')
        OR pg_catalog.has_schema_privilege(i.login_oid,n.oid,'USAGE')
        OR pg_catalog.has_schema_privilege(i.role_oid,n.oid,'USAGE')
             IS DISTINCT FROM (n.nspname='scanipy_accepted_inputs'))
   ) AS schemas_ok,
   NOT EXISTS(
     SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
     CROSS JOIN LATERAL (VALUES (i.role_oid),(i.login_oid)) AS principal(oid)
     WHERE n.nspname IN ('scanipy_accepted_inputs','scanipy_execution') AND
       (c.relowner=principal.oid OR
        CASE WHEN c.relkind='S' THEN pg_catalog.has_sequence_privilege(principal.oid,c.oid,'USAGE,SELECT,UPDATE')
             WHEN c.relkind IN ('r','p','v','m','f') THEN
               pg_catalog.has_table_privilege(principal.oid,c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
               OR pg_catalog.has_any_column_privilege(principal.oid,c.oid,'SELECT,INSERT,UPDATE,REFERENCES')
             ELSE false END)
   ) AS data_rights_ok
 FROM identities i
)
SELECT session_user::text,current_user::text,pg_catalog.current_database()::text,
       pg_catalog.current_setting('server_version_num')::int,
       ARRAY(SELECT oid::bigint FROM allowed ORDER BY ord),
       coalesce((SELECT attributes_ok AND six_ok AND login_membership_ok AND role_membership_ok
          AND function_rights_ok AND definitions_ok AND schemas_ok AND data_rights_ok
          AND owner_oid IS NOT NULL FROM checks),false)
       AND session_user=$LOGIN AND current_user='scanipy_accepted_execution_reader'
       AND pg_catalog.current_database()=$DATABASE
       AND pg_catalog.current_setting('transaction_isolation')='read committed'
       AND pg_catalog.current_setting('transaction_read_only')='off'
       AND (SELECT setting::bigint=15000 FROM pg_catalog.pg_settings WHERE name='statement_timeout')
       AND (SELECT setting::bigint=2000 FROM pg_catalog.pg_settings WHERE name='lock_timeout');
```

Require exactly one tuple of SIX columns, then exact EOF: three exact strings matching configured
login/fixed role/database; exact int160000..169999; exact built-in list of six distinct nonzero OIDs
(exact ints<=4294967295, no bool); exact boolTrue. Do not accept str OIDs/memoryview/int coercion.
Snapshot it before use. Envelope<=1024 scalar bytes/32 tagged values, charged as own P work.
The new total for facade outputs plus six catalog envelopes is2562075 bytes, replacing EAR-01's
larger catalog allowance. This is not a statement about driver/backend allocation size.
The fixed query deliberately checks protected accepted/execution surfaces, not a claim that the
login cannot invoke any ordinary pg_catalog function or that PostgreSQL is globally immutable.

No query result is a receipt or independent trust. Missing/malformed catalog data, unauthorized
effective inherited/PUBLIC privilege, extra role membership, changed function owner/config,
timeout or protocol error closes the connection and fails before any facade operation.
The old roles/ACL bodies remain unchanged. Actual PostgreSQL16 query/type semantics and role
positives/negatives must pass the separately granted integration tests before this factory is accepted.

### 4. Transaction and cleanup ownership precision

The private connection proxy tracks `commit_attempted`, `rollback_attempted`, `close_attempted`
and each of at most three raw cursor close attempts. Prelude lives inside the same guarded raw
connection ownership as the facade. If it fails before the facade helper owns the transaction,
the factory attempts rollback once; after the helper is entered, its rollback goes through the
same tracked proxy. Factory cleanup performs rollback only if needed and not already attempted.
This closes the prelude-failure branch without a second rollback after an uncertain helper rollback.
Never mark acquisition/cleanup ownership after an unguarded line boundary or use a retry loop.

Do not modify old `ledger_repository._cursor`. Its returned cursor is the private proxy whose
raw cursor was already placed in the guarded registry. Result publication waits for commit,
all owned cursor closes and connection close. Preserve primary identity and cause-or-context
plus cleanup failures; attempt other owned cleanup once even when one close fails. A connection
or descriptor with uncertain close is not reused. Interrupt controls cover every acknowledged
handoff, including before facade entry, catalog EOF, constructor cursor, commit and final close.
All schedules remain within the same120s lifecycle; actual hard interruption/driver cleanup
compatibility is still an installation qualification, not an excuse to claim a close completed.

### 5. Dependency-ordered allocation recommendation

No source grant is requested by writing this document. Root can split the eventual work:

1. After the separately allocated0007 absence migration is reviewed, reserve actual0008 for the
   new role-only migration, its new unit module and the new reader contract. No dependency on
   executing A2 native/PG just to prepare this additive role source; old bodies/roles stay exact.
2. Prepare the two new custody/factory modules and their new unit modules under this contract,
   keeping verifier runtime-unsupported and A2's seven paths frozen. No placeholder installed
   identities, compatibility bypass or alternate diagnostic constructor.
3. Only after canonical's separate administration harness checkpoint is stable, allocate the
   one shared fixture delta plus the two opt-in integration modules. Existing0005/0006 defaults
   and administration mode are preserved; reader profile's target chain is closed0007→0008.

Root must approve this accounting/query contract before source allocation. Tests must check exact
query text/execute count, P category reservations and arithmetic at all maxima, parser/copy failure
precharge, fixed socket0770/0750 and pre/post-connect drift, known-good current R5/R6 context, and
every once-only cleanup branch. They do not need real installation to establish source correctness.
Genuine role/SQL and dropped-reader tests still need their own isolated grants. Actual root/server
identities, credentials, runtime measurements, independent restore/old-parent exclusion and final
outer supervision remain unchosen operational obligations. No physical runtime framework is added.

### 6. Source basis and evidence status

All EAR-01 source pins remain the basis; no files there changed for this revision. Additional
source-backed delegation pins read for the accounting derivation:
`analysis/ifds/bound_rules.py` SHA590879fa362a615775bbe47d44d3d14e6980cd973019594a7dd1b4b125a2db5b;
`services/scan/occurrence_store/codec.py` SHA832185712993c2e398a5e9cc24d9d0c2c571a739805088307c23a2545156b845.
Actual codec paths reviewed: bounded JSON preflight/loads/canonical/shape; frame/spec encode/decode;
record/path snapshots; ResolvedQualifiedRule→selected_content→qualified_members; occurrence
accepted-content encode→CanonicalEnvelope→decode. No rule/compiler execution is proposed here.
Arithmetic was evaluated as plain integer expressions only. No tests, SQL, PG, keys, native code,
socket connections or filesystem custody operation was executed for this proposal.

## Appendix C — approved exact schema catalog closure

## EAR02 catalog correction proposal

2026-09-26; design only, following the independent0007 owner review. No reader
source, migration, SQL/server execution, tests or installation is allocated here.
EAR02 remains byte-exact at
`ddeba8eeedc4032d51c20ec7a92c9fcbbf10860c85706ee13d9a19c39f6cefa0`;
EAR01 remains `f2866b07739522d663d910527046ab5fa81627f3866c401adca9bb0a11f86ca5`.

### Required narrow correction

Root correctly identified that EAR02's selected-role schema USAGE comparison
admits USAGE WITH GRANT OPTION on the accepted schema. That violates EAR01's
no-grant-option contract even though CREATE, login USAGE and data/function
privileges are separately checked. Correct the proposed `schemas_ok` expression
with exactly these two additions; all other query clauses remain unchanged:

```sql
   (SELECT count(*)=2 FROM pg_catalog.pg_namespace n
      WHERE n.nspname IN ('scanipy_accepted_inputs','scanipy_execution'))
   AND NOT EXISTS(
     SELECT 1 FROM pg_catalog.pg_namespace n
     WHERE n.nspname IN ('scanipy_accepted_inputs','scanipy_execution') AND
       (n.nspowner IN (i.role_oid,i.login_oid)
        OR pg_catalog.has_schema_privilege(i.role_oid,n.oid,'CREATE')
        OR pg_catalog.has_schema_privilege(i.login_oid,n.oid,'CREATE')
        OR pg_catalog.has_schema_privilege(i.login_oid,n.oid,'USAGE')
        OR pg_catalog.has_schema_privilege(i.role_oid,n.oid,'USAGE WITH GRANT OPTION')
        OR pg_catalog.has_schema_privilege(i.role_oid,n.oid,'USAGE')
             IS DISTINCT FROM (n.nspname='scanipy_accepted_inputs'))
   ) AS schemas_ok,
```

The fixed two-name count rejects a missing protected execution schema instead
of treating its omitted catalog rows as a vacuous denial. It does not restrict
unrelated schemas or invent a new installed schema/owner identity. The selected
role gets ordinary USAGE only on the accepted schema; the login is already
denied USAGE on either protected schema, and both principals are denied CREATE.
The new grant-option predicate applies to both protected schema rows.

This changes no statement count, parameter, returned column, cursor schedule,
raw/parser/copy ceiling,120s envelope, role membership or original R5/R6 context.
Copies of the longer fixed SQL literal remain charged to actual own work.
It adds only fixed catalog work within the same single catalog SELECT. No SQL
READ ONLY claim is introduced: these remain read operations that can row-lock.

### Required future controls, not performed here

Keep the valid profile positive with ordinary selected-role accepted-schema
USAGE and both protected schemas present. Reject the same grant with grant
option, selected-role execution-schema USAGE, either-principal CREATE, login
USAGE, and either protected schema absent. Preserve all existing six-function,
membership, owner, table/column/sequence, deadline and exact result/EOF checks.
Future real PG tests should observe these privileges through the same proposed
catalog query, not infer its result from a mocked boolean. Migration numbering
and ACL installation still depend on reviewed0007 and separately allocated0008.

## 3. First role-only source checkpoint — 2026-09-26

The three-path allocation in section0 is implemented for independent review,
not committed or installed. Existing tracked files, old migrations/resources,
runtime-unsupported and all A2/harness code remain byte-exact to85dea239.
The new test module exercises87 controlled cases: frozen predecessor definitions,
actual six-target declarations/body/metadata, exact seven grants and inverse,
pre-effect guard ordering, dependency/privilege predicates and real offline
SQLAlchemy/Alembic framing. Guard string inspection is not live catalog execution.

Two same-selection runs passed87 each with zero failures/errors/skips; these are
overlapping controls, not174 distinct tests. Final report:
`/tmp/scanipy-execution-reader-role-evidence-yaM8hHBH/role-final.xml`,
SHA256 `5c9e336502c66888eaa5937500e9f8f2be7f6dac583faed0e69cec36f67b8380`,
1.353s JUnit/1.35s console. Declared Python3.11, closed environment, explicit
worktree PYTHONPATH and configured pyproject were used; plugin autoload and
ambient pytest options were disabled. Ruff check/format and strict mypy on the
new migration passed. Initial authoring lint diagnostics were corrected; no
failed PostgreSQL result is implied because no PostgreSQL operation was run.

Section2's real PG positives/negatives, rollback/cross-database dependency and
preservation tests remain required, as do source/security/canonical review and
later composition checks. Full provider/custody/native/operator qualification
is still unimplemented; this checkpoint confers no current execution authority.
