# Accepted-ledger SQL boundary — owning implementation contract

Date: 2026-09-26 PKT. Primary component: CMP-ORCH-03 — accepted-input
persistence prerequisite, with explicitly coordinated CMP-CP-03 migration/RLS
and CMP-CI-01 ordinary CI coverage. Root-owned issue: #399.

Status: **root-approved implementation contract; implementation in progress**.
The design basis, consolidation and exact narrow fixture route have scoped root
and independent review approval. Root allocates paths 2–15 below; path 16 remains
separately root-owned. No AL-03 SQL, migration, repository, provider,
namespace, role, key or operational authority is implemented by this document.
Existing AL-02 is a pure input codec, not an authority ledger.

## 0. Current authority, precedence and reading order

This file carries the complete approved original design, amendment, cohesive
allocation and C1/C2 closure, plus the scoped review records. Required AL-03
behavior does not depend on access to a temporary design file. Temporary paths,
old hashes/line references and proposal labels in appendices are preserved
historical provenance, not required runtime locations or current status.

The current engineering authority is
[DECISION-BHMEA-01](../DECISION-BHMEA-01-current-execution-authority-2026-09-25.md).
It does not supply an operator identity, trusted admission installation, native
launch permission or historical component acceptance. Both CLAR-BHMEA-01 and
CLAR-BHMEA-02 remain OPEN; existing WBS/PLAN/SDD history is not rewritten.

Apply this explicit precedence; an unlisted contradiction must stop
implementation for owner review, not be silently resolved:

1. Sections 0–4 here govern current scope/status, actual dependency base and the
   separately approved fixture/CI expansion. They do not alter owner wire bytes.
   [Appendix I: planned-pin boundary](#al03-appendix-i) narrowly clarifies SQL's
   missing-runtime-pin predicate versus the separate installed-runtime gate;
   it overrides Appendix B's ambiguous installed-pin denial wording only.
   [Appendix J: current-read control](#al03-appendix-j) explicitly replaces
   Appendix D's all-selection C for R5/R6 and Appendix H's eight single-ticket
   bridge schedule; all other owner wire and public limits remain unchanged.
2. [Appendix H: delegated-work closure](#al03-appendix-h) supersedes the old
   mutation all-fetch/control accounting with explicit F_total/M_total, image,
   request-history and canonical-concatenation admission. Its proposal/pending
   labels describe its preserved pre-approval cutoff; section 0.2 records the
   subsequent exact root/peer approval. It changes no owner wire or old SQL.
3. [Appendix D: C1/C2](#al03-appendix-d) closes the six read signatures/results,
   selectors/errors, read I/F/C/G/H/B quotas, raw support retrieval, R5/R6
   current locks and rechecks, the private unadmitted installer, its immutable
   installation columns and exact global/customer RLS/dispatcher semantics.
   These replace the original's incomplete read/installer descriptions.
4. [Appendix C: cohesive allocation](#al03-appendix-c) combines original
   AL-03/04/05 SQL work into one usable boundary: all seven mutations, all six
   reads and installer, five tables, exact bridges/ACLs, immutable history and
   the positive EXECUTION composite-key spine. It does NOT allocate the actual
   installed administrative ingress, ExecutionAuthorityReader provider, native
   launcher or DB-BAR. Its original 14-new-file inventory is superseded ONLY by
   the explicit 16-path ownership inventory below.
5. [Appendix B: amendment 01](#al03-appendix-b) resolves the original's command
   roles/return pair and per-action W/F/G/hash caps; forbids retrospective
   lower-operation adoption; fixes complete planned-policy derivation and the
   single selected language per detector; fixes initial metadata-only denial,
   reason order, no-output observation and deny-before-renew; and makes schema
   USAGE, zero/one-live-target predicates and narrow cross-owner grants explicit.
6. [Appendix A: original design](#al03-appendix-a) supplies the remaining
   authority/history, five-table, immutable binding, lock, replay, restore and
   acceptance obligations. Its split implementation sequence is historical,
   not permission to ship placeholder tables or defer every usable writer.
7. Appendices E/F retain the actual scoped review chronology. Their historical
   proposal/14-file labels are not the current allocation/status statement.
8. Appendix G preserves the contrary lower-helper evidence and earlier proposed
   accounting. Appendix H, not G's fresh-only register13A or separate-fetch
   suggestion, supplies the final approved accounting rule.

Specific disambiguations are mandatory:

- R5's actual LedgerExpectation has binding plus THREE dependent nullable
  fields: execution_authorization_digest, policy_event_id, admission_event_id.
  All four must be nonnull for R5/R6. There is no fifth invented field.
- Control-only execution bridges must lock/select bounded named columns, not
  call old whole-row/to_jsonb v1_lock while claiming zero raw fetch/hash work.
- AL-02's actual owner codec remains unchanged. SQL independently checks its
  wire; no copied ExecutionBinding/receipt or normalization of poisoned owner
  slots is allowed. Low-level SQL rows remain untrusted bounded input to the
  real owning facade.
- Historical operation replay returns the original committed bytes before
  fresh eligibility and never adopts an unbound lower request/seal/run.
- The installer retains configuration declarations only. It creates neither
  signed authority nor an independently trusted InstalledTrust source.
- The integrated 0005 owner inserts a NEW detector row with state `running`
  (`execution_v1_tables.sql` default; the begin INSERT supplies no state).
  Require actual NEW `completed=false`, `replayed=false` and that exact new
  row's `running` state; do not rewrite it to the historical proposal's
  `pending`, add a trigger, or modify 0004/0005. This is metadata state, not
  evidence of a native process. General active-target predicates still accept
  pending/running. Initial denial inserts DENIAL and fails the actual run and
  attempt atomically, so no active intermediate is committed on that branch.
  Root approved this owner-grounded correction on September 26; required
  real-PG controls must assert the actual NEW state and denial rollback/commit.
- Original complete reader/provider, crypto, runtime and restore tests remain
  downstream gates where those adapters are outside this SQL allocation.
  A SQL-only result must not be reported as passing those integration tests.

### 0.1 Preserved approval inputs

These are hashes of the original complete source records, NOT hashes of this
assembled document. Heading levels alone are demoted in their retained text.

| Retained record | Original SHA-256 |
| --- | --- |
| Appendix A, original 741 lines | 16cccece8c5af9772518e241ee791d470db2f0ad1108b1e0924dc579006332ac |
| Appendix B, amendment 544 lines | f95f1595ba23e699675529c80e0aca768df32064816805cfefef11295932a9a9 |
| Appendix C, allocation 180 lines | f7ece9da52023fc62ce4e6b4fc9b5f2497589cfa01d052938e8bb5f29dd2d24e |
| Appendix D, corrected C1/C2 240 lines | 56f1057a579f0910f937220251ed2845267d66bb3e9e10e73c5a04e3ecaa61c2 |
| Appendix G, initial lower-helper work audit 133 lines | 8da687764f419fd7e20c063d91f512168812862bbf2c03d924621939ed1ccf1f |
| Appendix H, final delegated-work closure 248 lines | 85174198d5937e3755412d6cad53b60db9c9af5bcf6c8edb6a137d8c10b478fb |

Root and independent peers reviewed the complete original/amendment and corrected
C1/C2 against actual owners. Root separately approved the cohesive SQL scope.
On September 26, root approved adding the existing harness as path 15 and a
separate ROOT-OWNED CI change as path 16, after the concrete global-role cleanup
gap was identified. That is engineering scope approval, not code/test acceptance.
The consolidation and corrected fixture route are now approved as recorded in
section 4.1. Source allocation is not implementation or operational acceptance.

### 0.2 Delegated-work evidence, exact approval and implementation conditions

On September 26, the implementation audit exposed whole-row raw selections,
to_jsonb/OLD/NEW copies, duplicated variable TEXT, repeated lower hashes and
historical-row traversal omitted by the original mutation accounting. Appendix G
retains that contrary evidence. Root and canonical_budget_audit read the complete
owner helpers and Appendix H; the independent audit corroborated raw/SHA schedules
and corrected register's lower replay14A, shared census ticket accounting and the
N-seen+1 off-by-one. Root and peer approved H at the exact hash above as a scoped
engineering admission design. No database or runtime test supplied that approval.

H's numeric F_total/M_total/image/R/K/N rules and hex pin are current implementation
requirements, not hypothetical optional fallbacks. In particular seal F_total is
18,087,936 bytes, authorize145,494,016 and renewal63,639,552; public W/G and SHA
ceilings remain unchanged. Each lower helper is precharged with no refunds.
The old F table is the F_direct slot list, not an unchanged all-fetch ceiling.
Wide otherwise valid occurrence envelopes may fail the explicit K work limit;
never truncate content, apply the accepted20,000-value cap to occurrence input,
or imply the complete submitted workload has thereby passed. Physical PostgreSQL
memory/I/O/runtime, restricted-role N/N+1 and existing-functionality gates remain.

The census's planned_new_rows is derived inside trusted fixed SQL, never supplied
as a new caller argument or bridge selector. Before begin, capture-context with
an existing seal and zero live runs conservatively reserves one planned run;
pre-seal capture-context reserves zero. If that same sealed capture-context is
used without a subsequent begin, the extra one-row reservation remains conservative
and may reject at the bound; it is not silently removed. After begin, detector-
context counts the actual inserted run and reserves zero planned rows, avoiding a
second count. Initial denial consumes the already reserved authorize run; renewal
denial adds none. Test these transitions and exact N/N+1, not only fresh small data.

Each four-table census pre-reserves one aggregate N+1 ticket, initializes seen to
planned_new_rows, uses LIMIT N-seen+1 and increments seen by actual returned rows;
seen>N rejects immediately. The eight-census/32-ticket schedule is a maximum,
not an unbounded retry loop. Pin bytea_output='hex' on new delegating AL routes
only and verify hostile caller escape is restored on success/error. Keep all old
0004/0005 definitions/config/ACLs intact. The ordinary-function-history scope and
NEW-create owner-injected error_reference limitation in H remain explicit.

This amendment adds no role, table, bridge parameter, file allocation, provider,
operator/key installation, native permission or completed component claim. The
affected helper paths remain held until root confirms this repository incorporation;
thereafter only the previously allocated implementation and fast focused checks
are authorized. Real PG, broad suites, hooks and commits need separate scheduling.

## 1. Actual integrated dependency base and unchanged owners

Worktree: /tmp/scanipy-accepted-ledger-sql-UXpsyI.
Branch: bhmea/accepted-ledger-sql.
Clean dependency-preparation HEAD:
be3c00ddefa1921d7f3f9aebd909f8380ff5bf4c.
Its tree: e1c5a5291103a9182fe9c3c16ea56ed57a05f1fe.
This document was drafted on that base; the root approval below precedes source work.

| Dependency | Exact integrated commit | Meaning |
| --- | --- | --- |
| AL-02 | 66607b9537242d7ca05c93b2da03722b841dd83c | Reviewed pure command owner, not SQL authority |
| Accepted main | 95fa5d1991cbb65b89569c399c51186ba44cae9e | Accepted revision-12 handoff |
| Occurrence | cadd386b81854c31976489eaefc129dc01fcf96b | Actual eight-table execution owner and fixture |
| Inventory | 40ba98afa353428e96add873cdecc52b84b6a0e1 | Actual reviewed runtime-artifact owner |
| Rule codec | 80f45c32dc77f1ecce07de8a90a257672bd8cc75 | Actual complete rule/model codec |

All five are verified ancestors of the preparation HEAD. Local integration of a
reviewed dependency is not a claim that every feature has remote canonical
acceptance. There was no cherry-picked type copy or independent replacement.

Four normal merge commits were created in order:
90651bf8389364b02f0c2d78e62b49932866f8f3,
33ce940ea51d984b31f559299f99ef21c27a8134,
6841c3dd153c1f5dbd3f77de39cafaf90de3a0e0,
be3c00ddefa1921d7f3f9aebd909f8380ff5bf4c.
Normal commit hooks passed using their actual merge-conflict-only selection;
that is not a full-tree type/test check. No broad/pre-push/remote/DB gate ran.

Conflicts were confined to the inherited secret baseline. The approved exact
167-record identity union retains all flags/config/exclusions and actual CI
line references; an automatic duplicate semantic_g1 JSON key was removed by
restoring the already approved identical baseline. No new secret disposition
was accepted. Baseline SHA:
594f401e654b0f07de7297d9fa06675f50727920f58a2f249077bf1e8d616540.

The actual accepted-input package and bound_rules.py are unchanged from AL-02.
AL-02 source SHA:
bc361a8f5f6a2ad422df2248ad6207ee565123004cf813319cb5346cd0dc587f.
Its dedicated test SHA:
27e1c23072ac06a854d610c4267a2b42a66e175683317534a81438c93f088ad3.
Occurrence migrations/resources/repository/harness match the specified
occurrence dependency exactly. The actual migration head is
20260925_0005, down from 0004 then 0003; reserve new 20260926_0006 only with
down_revision=20260925_0005. Recheck at implementation time; no parallel head.

Reuse these repository owners directly:

- services/scan/accepted_inputs/ledger_commands.py: LedgerCommand,
  decode_ledger_command, encode_ledger_command, COMMAND_SCHEMA and actual
  action validation/reserved hash work.
- services/scan/accepted_inputs/models.py, schemas.py, codec.py, verify.py:
  exact existing expectations, ExecutionBinding, frames, raw/domain identities
  and complete-bundle validation. The public operational verifier refusal stays.
- analysis/ifds/bound_rules.py: actual QualifiedRuleKey and full rule/model
  decoding, including each declared language; no service-owned lookalike.
- services/scan/occurrence_store and frozen execution_v1 resources:
  actual envelope domains, lower-operation semantics, scopes/fences and grants.
- Existing runtime artifacts are dependencies, not installed runtime authority.

Focused compatibility evidence on this exact pre-document base: Python 3.11.16,
actual unit-selected test_accepted_ledger_commands.py plus
test_runtime_artifacts.py, 385 passed / zero failures/errors/skips, 11.648 seconds.
Report: /tmp/scanipy-al03-dependency-focused.xml. This historical report path is
not a protocol dependency. No new AL SQL or PostgreSQL test exists in that run.
The task-owned node_modules symlink was removed after hooks; its target was
unchanged and the worktree was clean before this draft.

## 2. Exact current file ownership and implementation boundary

Current total is 16 paths, not 14 all-new files. Root's section 4.1 decision
allocates this contract and paths 2–15 to the schema implementation agent.
Path 16 remains root-owned. No unlisted file or operational action is allocated.

| # | Path | Ownership / change |
| --- | --- | --- |
| 1 | docs/bhmea/ACCEPTED-LEDGER-SQL.md | New owning contract; delegated author, root review |
| 2 | db/migrations/versions/20260926_0006_accepted_ledger.py | New migration |
| 3 | db/migrations/versions/accepted_v1_shapes.json | New frozen shapes |
| 4 | db/migrations/versions/accepted_v1_tables.sql | New five-table DDL |
| 5 | db/migrations/versions/accepted_v1_validation.sql | New bounded owner-equivalent SQL validation |
| 6 | db/migrations/versions/accepted_v1_history.sql | New immutable/coordination guards |
| 7 | db/migrations/versions/accepted_v1_operations.sql | New seven fixed mutation implementations |
| 8 | db/migrations/versions/accepted_v1_reads.sql | New six fixed bounded reads / private installer |
| 9 | db/migrations/versions/accepted_v1_execution_bridges.sql | New narrowly execution-owned bridge definitions |
| 10 | db/migrations/versions/accepted_v1_acl.sql | New exact additive ACL inventory |
| 11 | services/scan/accepted_inputs/ledger_repository.py | New bounded function-only facade |
| 12 | tests/unit/test_accepted_ledger_repository.py | New facade/fixture-safety controls |
| 13 | tests/integration/test_accepted_ledger_sql.py | New actual SQL/owner/atomicity tests |
| 14 | tests/integration/test_accepted_ledger_security.py | New restricted-role/locking/ACL tests |
| 15 | tests/occurrence_store_postgres.py | Existing harness; narrow closed-profile extension |
| 16 | .github/workflows/ci.yml | Existing; ROOT-OWNED later separate AL PostgreSQL job |

No existing accepted model/schema/codec or 0004/0005 migration/resource is edited.
The new migration may add only the explicitly approved composite keys/bridges and
exact grants, preserving old source, signed history, owners and unrelated ACLs.
No SQL interpreter imports runtime Python schema code into a historic migration.
No sixth ledger table, eighth runtime command, generic privileged helper, API,
real provider, runtime barrier, native launch or service-login installation.

The unresolved DB-BAR release/old-parent/pre-reservation paths remain separate.
The scoped positive EXECUTION key/FK preparation is not a barrier implementation.
Do not allocate placeholder barrier tables or weaken a fence to make fixtures pass.

## 3. Proposed exact fixture route for path 15

This section makes the root-approved narrow harness expansion executable as a
design, approved before code by the review recorded below. Existing target/ownership,
closed URL/socket-path routing, ambient libpq rejection and no-failure-adoption
guards stay. Lexical socket-path checks do not prove filesystem no-follow custody.

### 3.1 Constructor and fixed session fixtures

Retain the actual PrivatePostgres class, with the proposed signature:

```python
PrivatePostgres(
    url: str, *, profile: Literal["occurrence", "accepted"] = "occurrence"
)
```

The profile is a closed exact string, selected by trusted test setup, not by URL
query, schema bytes or an arbitrary iterable of roles/migrations/callbacks.
Its value controls a fixed migration ceiling and exact reserved-role inventory.
Existing callers default to occurrence. No profile grants production authority.

- occurrence_pg remains session-scoped, reading ONLY
  SCANIPY_OCCURRENCE_TEST_URL and SCANIPY_OCCURRENCE_TEST_REQUIRED.
  Its default migration target is explicitly 20260925_0005, never evolving head.
- New accepted_ledger_pg is session-scoped in this same harness, reading ONLY
  SCANIPY_ACCEPTED_LEDGER_TEST_URL and SCANIPY_ACCEPTED_LEDGER_TEST_REQUIRED.
  It instantiates the accepted profile and explicitly stages through 0005
  before 20260926_0006. Both allocated AL integration modules register the same
  `pytest_plugins = ["tests.occurrence_store_postgres"]` plugin, matching the
  existing occurrence tests. They must share ONE accepted-profile fixture
  instance per pytest session. Do not directly import the fixture into each
  module: that can create separate FixtureDefs and competing global roles.
- Missing URL with corresponding REQUIRED="1" is a test failure; otherwise
  missing explicit URL is a local optional skip, not acceptance. There is NO
  fallback between these variables, to an application URL or to a discovered DSN.
- Explicit migrate/downgrade targets remain limited to the task-owned child
  database and the fixed test sequence. A default never silently tracks head.
  Validate the actual resolved SQLAlchemy/libpq target before the child command.

Both session fixtures cannot share one cluster: role names are cluster-global.
Full combined verification needs separate task-owned clusters or serialized
separate processes with completed ownership-checked disposal. Running processes
separately alone does not authorize adoption of a still-existing role set.
Never bypass this by sharing/adopting reserved roles or cleaning another fixture.

### 3.2 Exact role ownership and migration sequence

Occurrence profile's reserved set remains the six full scanipy_exec_ names:
owner, request, detector, identity, cleanup, read.
Accepted profile preflights that set PLUS these five exact new full names:

```text
scanipy_accepted_owner
scanipy_accepted_policy_admin
scanipy_accepted_publisher
scanipy_accepted_resolver
scanipy_accepted_reader
```

Refuse any preexisting selected reserved role before creating the child.
Existing unowned legacy prerequisites remain unowned and must not be altered
or dropped. Do not catch a racing CREATE and adopt its resulting role/OID.

Both profiles first exercise the existing controlled 0003→0004→0005 sequence,
including hostile default ACLs, reserved execution-role refusal, original legacy
byte/ACL checks and empty execution-only round trip. Calls in that sequence use
explicit 0005 rather than head. Track the six exact execution OIDs only after
confirmed successful atomic migration; retain them across later AL failures.

Accepted profile then captures the unchanged execution object/owner/body/ACL
baseline and performs the explicit 0005→0006 sequence. Exercise refusal of a
task-created accepted reserved role before successful installation. Record its
OID from the successful CREATE/commit, verify it before removing ONLY that
controlled role, and never infer ownership from a name seen after failure.

After successful atomic 0006, verify/capture exactly the five new accepted OIDs.
Failed or ambiguous migration acknowledgement is not ownership proof; do not
select all matching names in finally and adopt/drop them. Unexpected identities
fail closed for explicit recovery. Exercise empty 0006→0005→0006 round trip:
remove/check only exact migration-owned AL objects/roles/grants/composite keys,
prove the six execution roles and unrelated legacy/execution ACLs unchanged,
and capture fresh accepted OIDs after the final successful upgrade.

Create only task-owned restricted diagnostic logins after installation for the
four accepted runtime capabilities, alongside required existing execution test
principals. Never create an accepted_owner runtime login/membership. Owner-only
installer tests may use the fixture's explicitly privileged isolated admin
connection/SET ROLE; this is diagnostic setup, not operational identity selection.

Final disposal verifies the created child database OID/owner and every recorded
role OID. Drop only that child without FORCE, then only the roles this fixture
proved it created. No CASCADE, foreign role adoption, leaked-session termination,
app database access or broad name-based cleanup. AL tables disappear with the
owned child; new cluster-global roles must not leak after a successful test.

### 3.3 Required fixture falsifiers and separate CI

Add no-DB tests to the allocated unit module for unknown profile, explicit
environment separation, fixed migration targets, failed/ambiguous migration
ownership, role appearance after preflight, changed OIDs and cleanup refusal.
Retain the actual existing malicious DSN/query/socket/ambient-routing controls.
No callback/injected migration success can replace real-PG acceptance.

Real isolated tests cover all eleven reserved roles, hostile inherited ACLs,
every accepted restricted capability and forbidden route, installer denial,
global/customer scope, default/adversarial RLS settings, empty round trip,
nonempty refusal, exact old owner/body/ACL/key preservation and no residual role.
Retain actual attempted/selected/pass/skip counts and failed-run histories.

Path 16 remains root-owned and unedited in this draft. It adds a SEPARATE
disposable PostgreSQL job selecting BOTH AL integration modules, with explicit
SCANIPY_ACCEPTED_LEDGER_TEST_URL and REQUIRED="1", pinned reviewed image,
bounded resources, retained JUnit and nonempty/no-skipped actual cases.
Keep existing occurrence job, its environment and test selection unchanged.
Do not run the two fixture sessions against a shared cluster.
Creating/provisioning/running either cluster still needs explicit coordination.

## 4. Actionable gates and completion meaning

- [x] Root review/approve this assembled contract and exact fixture route.
- [x] Allocate the 14 non-document delegated source/resource/test paths explicitly;
  coordinate the separately root-owned workflow change.
- [ ] Implement one coherent five-table, seven-mutation, six-read and private
  installer boundary; no tables-only or digest-only substitute.
- [ ] Preserve exact owner bytes and all scoped keys; prove raw/domain separation,
  complete language/member validation and malformed-path precharged work.
- [ ] Implement exact additive grants, immutable guards, namespace-first locks,
  fresh post-wait time, no retrospective adoption and no renewal on denial.
- [ ] Prove every applicable original AL-T01–T19, amendment section 8 and C1/C2
  section 8 SQL/codec/fixture obligation with real restricted isolated PostgreSQL.
  Provider/runtime portions remain explicitly downstream, not silently passed.
- [ ] Prove facade bounded conversion, poisoned-slot refusal, exact SQL result
  validation, discard-on-ambiguous-commit and byte-identical historical replay.
- [ ] Independent full security/code review, actual normal hooks, combined full
  tests and exact-head remote gates after scheduled resource coordination.
- [ ] Separately install genuine administrative crypto, operator/service identity,
  independent admission/restore provider and actual ExecutionAuthorityReader.
- [ ] Separately complete DB-BAR/current runtime/source-custody/recovery integration
  and AL-T20 operational evidence before enabling any native consumer.

Only the first two dependency mechanisms already exist: reviewed AL-02 and the
integrated owner foundations. Their successful tests do not complete AL-03,
R07/R08/R09/R13/R19, G0/G1/G2/G3, all 422 cases, stage readiness or submitted
promises. This draft creates no current authorization and changes no public
operational refusal.

### 4.1 Root review and bounded implementation allocation

2026-09-26 PKT / September 25 UTC. Root reviewed all new sections 0–4 and
independently compared all six retained appendices byte-for-byte against the
previously reviewed complete originals, with only heading demotion. All four
approved source hashes and unchanged dependency bytes were reverified.
The independent reviewer checked the actual harness, owner models, SQL/roles,
dependency ancestors and corrected fixture route, approving consolidation SHA
`cb1474c6f98a7b1a2329c907a3f130c59823ba8b2a93616adc382947eb11b3e0`.

Two precision corrections are retained: lexical socket-path validation is not
filesystem no-follow custody; both AL test modules register the same fixture
plugin and share one session instance instead of duplicating global-role setup.
This record changes status/allocation only, not the reviewed wire or test route.

Root now allocates paths 2–15 to the schema implementation agent in this
independent worktree, with this contract as the governing specification.
Implement the complete cohesive SQL boundary, its real facade and tests; do
not stop at placeholder tables. Use actual owners and preserve prior bytes,
failure evidence and all listed limits. Any unresolved semantic/DDL/ACL/helper
budget contradiction returns to root before changing the contract or scope.

Trusted unit/static checks may run. Coordinate real-PG provisioning/migrations,
full suites, pre-push and all remote actions with root before execution; never
use the user database, adopt roles, invent an operator or enable a runtime.
The workflow remains root-owned. Independent code/security review, required
real database tests, normal hooks and exact-head canonical approval still
precede merge. No full R/C/G or stage-readiness acceptance is awarded.

The following complete retained records supply all remaining exact fields,
signatures, limits, transitions and test obligations under the precedence above.

<a id="al03-appendix-a"></a>
## Appendix A. Original authority-ledger design — retained historical text

Historical labels, snapshot dates, temporary paths and numbered section references
in this block belong to the original record. They do not override the current
precedence, scope or implementation status in sections 0–4 above. Section references
inside this block refer to that same block unless an original document is named.
The complete source text follows, with heading levels demoted for this document.

### AUTH-LEDGER-01 — Durable accepted inputs and current execution authority

Status: **PROPOSED; design only; not approved for implementation or operation.**
Date: 2026-09-25. Author: root-delegated canonical/core agent.
Scope: close the actual ledger/reader prerequisite of #399/#400 and DB-BAR-01.
No repository, database, trust installation, runtime, native analysis, signing,
test campaign, or remote mutation was performed for this note.

#### 1. Decision summary and hard boundary

Implement the five-table accepted-input ledger already proposed by the owning
resolver contract, with function-only writes and exact immutable evidence.
Add two narrowly granted, execution-owned parent-lock/read bridges. Implement
the actual `ExecutionAuthorityReader` against this ledger and the independently
installed admission provider. Do not invent another `ExecutionBinding`, a
`verified=true` column, a fixture signing identity, or a caller-authorized reader.

The intended dependency order is:

1. Owner-installed trust, admission state, runtime profiles and service identities.
2. Bounded, signature-checked administrative policy/publication ingress.
3. Atomic content/publication/request/seal ledger operations.
4. Atomic actual detector-run allocation plus execution-authorization event.
5. Actual #399 execution verifier, using committed ledger rows and fresh reader
   checks before and after its bounded verification process.
6. Actual #400 launch admission and the separately designed runtime barrier.

Steps 1, 2, 5 and 6 are not supplied by SQL tables or this proposal. In
particular, the current operational verifier deliberately returns
`runtime-unsupported`; a diagnostic verifier is not a production fallback.
The initial execution consumer remains **customer-scoped, detector-purpose**,
as required by the actual verifier. Identity-purpose records remain decodable
history but require their own later execution consumer and authority adapter.
Builtin operational adoption is not statistical model acceptance or semantic
soundness. The full submitted scope, including all 422 corpus cases, remains
unchanged and is not satisfied by this ledger.

The historical 411-line DB-BAR-01 note remains unchanged:
`/tmp/scanipy-runtime-db-barrier-review-O4ogSJ/DB-BARRIER-DESIGN.md`, SHA-256
`95853cb8e611d1e880d67d817f94602562b5f828acf6ded0ca796321d101933e`.
Root approved that note's conservative direction, not a migration, grant,
operational authority, or solution to old-parent exclusion. This new note
proposes the missing authority dependency; it does not backdate its existence.

#### 2. Inspected implementation and reproducible evidence

Resolver snapshot: `/tmp/scanipy-accepted-resolver-7MduJ3tp`, clean HEAD
`58b552c919a99f244c12cbdb11f9fb3eb8cdd64f`.
Occurrence snapshot: `/tmp/scanipy-occurrence-store-hbleeF`, HEAD
`fe61c9cdcf4ae56cf5c7fd682b3a73c3502f1808`.
The actual models, schemas, codecs, verifier, SQL operations/validation/grants,
and relevant parent contracts were read. No SQL or verifier was executed.

| Actual source | Consequence for this design |
| --- | --- |
| `accepted_inputs/models.py:152,177,323,387` | Reuse the actual binding, ledger expectation, context and reader protocol. |
| `accepted_inputs/schemas.py:306,515` | Seal, execution and denial records already have closed, distinct schemas. |
| `accepted_inputs/codec.py:25,31,199,274` | Raw SHA, domain SHA, framed evidence and accepted-content digest are different operations. |
| `accepted_inputs/verify.py:414–462` | Live policy/checkpoint and EXECUTION domain hash are verified independently of raw artifact hashes. |
| `accepted_inputs/verify.py:607–664` | Public consumer reads current authority, invokes isolated verification, then rechecks; operational launch is unavailable. |
| `ACCEPTED-INPUT-RESOLVER.md §§7–8` | Five proposed tables, monotonic history, restricted roles and independent restore admission already exist as design. |
| `execution_v1_operations.sql:267` | Actual request UUID is allocated by SQL, not carried in the caller's request envelope. |
| Same file, `v1_lock`, line 293 | Request/capture/work/attempt/run locks precede the live-fence time sample. |
| Same file, `v1_renew`, line 228 | Renewal advances work revision and actual lease, not the same-attempt token. |
| Same file, `begin_detector_run_v1`, line 545 | Actual run allocation and completed historical replay are distinct. |
| `execution_v1_validation.sql:24–64` | Existing canonical/framing helpers are private, not automatically callable by a new owner. |
| `20260925_0005_execution_security.py`; `execution_v1_acl.sql` | Execute-only capabilities and forced RLS prohibit quietly granting cross-namespace table writes. |

Exact source SHA-256 values:

```text
accepted_inputs/models.py
baa597f021f6bb41615fcbc8b0dd494dae1d16e8651cfea2489546db808c1d78
accepted_inputs/schemas.py
6546703c50c6b200283e2946c421988485d1ddbde2dca508dc4e1724e714a509
accepted_inputs/codec.py
208aaa6bdef29d6f0e7d689da036b75be07c9dddfa2e999bf5a5d7f575eff5e2
accepted_inputs/verify.py
21f2db2ed7da922cd963764320803a61519f9e047ff554886f42ce867ae68479
ACCEPTED-INPUT-RESOLVER.md
43a1ce3fe53b817107e11ef28ce3ddb678ba7dc12ba165414544bb0a33880d84
execution_v1_operations.sql
67bc29b0213c61513182d6af061726efdca61acaf80880f47b2e9fe2c71fcc5d
20260925_0005_execution_security.py
605fdbcc875aeaaed20095595add9480eeeb24d6f31c8afd47bd89402fc1533f
occurrence_store/repository.py
6531923c335afafbf2e6980cf4ad777998cc49373fdf29f615e0b4441a950fd1
```

#### 3. Authority sources: what is trusted, and by whom

The database is authoritative for committed occurrence state and immutable
ledger observations, not for installing its own root or deciding that its
restored policy head is current. The installed admission provider is outside
the database's backup/restore domain. Its trusted configuration supplies the
actual `InstalledTrust`: deployment, registry/scope/org, pinned root SPKI SHA,
and allowed administrator actor. None is inferred from a UUID or DB row.

The dedicated policy administrator/publisher/resolver services are trusted
for cryptographic and independent-provider checks which SQL cannot perform.
SQL checks canonical bytes, scope, references, monotonic transitions, exact
hashes, current locked occurrence state and committed operation history.
SQL does not perform RSA verification, read a host checkpoint file, attest a
loaded runtime, or authenticate an arbitrary caller-supplied verification result.

This is an explicit capability trust boundary: compromise of a privileged
publisher/resolver login can violate its ingress obligations. Signature fields
and an `is_verified` flag do not eliminate that fact. Scan users, rankers,
triage principals and model-generated proposals never receive those logins.
Installed profiles and their effective measurement/containment remain #400
obligations. A runtime digest in a receipt is not proof of actual execution.

There is a concrete bootstrap gap in today's API. Its modes are only
`publication-preflight`, `historical`, and `execution`. Execution requires an
actual committed authorization; historical does not authorize a new live use;
publication preflight cannot be repurposed for an old approval by changing its
issue date. Do not fabricate a prospective ledger/binding, rewrite SEALED, or
invoke a private diagnostic function to bridge this gap.

Recommended minimal resolution: bounded administrative ingress validates each
new signed policy/checkpoint/publication before its function-only commit.
Current authorization relies on that immutable ledger provenance plus fresh
external admission and SQL grant/time checks, then the **existing execution
mode** independently verifies the actual committed record before analysis.
Factoring/exposing the owning verifier's policy/checkpoint checks into a real
bounded administrative adapter is a required implementation slice, not an
already available public API. No crypto is copied into SQL or another module.
If root instead requires independent fresh crypto before every authorization
commit, approve a separately specified current-use preflight mode first; the
present modes cannot honestly supply it. Neither option permits a fake grant.

#### 4. Reuse these exact records, digests and bounded codecs

All application types below come from `services.scan.accepted_inputs.models`;
all document schemas/codecs come from its existing `schemas` and `codec`.
`QualifiedRuleKey` remains owned by `analysis.ifds.bound_rules`. No replacement
classes, reflective callback dispatch, or schema copied from input is permitted.

| Bytes / value | Required identity |
| --- | --- |
| Raw detector, rule, model, key, signature, framed blob | `SHA256(actual_bytes)`; 64 lowercase hex at this owner boundary. |
| POLICY, ADMISSION, APPROVAL, PUBLICATION, EXECUTION records | `SHA256(ASCII(schema_id) + LF + exact canonical record bytes)`. |
| Original request SEALED frame | **Raw** SHA of the entire original frame. |
| Accepted bundle content | Existing occurrence `accepted-content` envelope/domain over exact framed S and ordered raw detector/rule hashes. |
| AdmissionExpectation | Actual checkpoint/policy **domain** digests plus exact generation/revision/epoch. |
| Runtime journal ArtifactRef | Its own raw artifact digest; never compare it directly to EXECUTION's domain digest. |

Original detector/rule/model bytes may have noncanonical whitespace/key order;
they remain unchanged. Control/authority documents are closed canonical JSON.
SEALED has the exact existing 15 ordered roles; LIVE has the exact existing
four roles. Length framing is schema+LF, then big-endian unsigned 8-byte part
lengths and exact parts; no trailing bytes. Preserve original signatures/DER,
duplicate role payloads and all original evidence. Never reconstruct an old
signature payload from a parsed map or replace it with a newer policy frame.

Use the actual limits, not a new uncapped SQL/HTTP wrapper: content aggregate
1,048,576 bytes; SEALED/authority 1,048,576; LIVE 262,144; ordinary object
65,536; policy 131,072 and at most 64 grants; whole verifier packet 2,621,440;
20,000 JSON values, depth 32, string 16,384 UTF-8 bytes; signed int64 integers.
Admission before expensive parse/allocation is mandatory at both the trusted
service and SQL entrypoint. One-dimensional SQL byte arrays require lower
bound 1 (or empty where the actual schema permits it); check aggregate lengths
and row cardinality before iteration. No concatenated batch bypasses these caps.
Keep the configured 15-second statement / 2-second lock ceilings. They bound
DB requests, not total retained history or every hostile host scheduling delay.

Frozen/slotted Python instances are not authorization or proof of valid storage.
At the reader/adapter boundary, take a bounded exact primitive snapshot once:
actual class, every required slot, exact UUID with valid integer storage,
exact int excluding bool, exact str/tuple/bytes and all owning schema constraints.
Then call the owning codec on private snapshots. `record_dict` is a wire
conversion, not validation of original UUID slots: normalizing a forged string
back into a UUID would recreate the previously confirmed scalar boundary bug.
Do not validate an original and then reread that mutable original for use.

#### 5. Minimal physical ledger and constraints

New namespace: `scanipy_accepted_inputs`. Keep the parent's five logical tables;
this proposal does not add a mutable latest-permission table. Exact PostgreSQL
DDL and migration numbers need a separate allocated implementation/review.

##### 5.1 `registry_namespaces`

Immutable UUID id, registry_id, closed scope, nullable org_id according to scope,
created_at. Unique registry/scope/org with NULL-safe global uniqueness.
Only these fields may change: policy_event_id/digest/revision,
admission_event_id/checkpoint_digest/generation/epoch,
coordination_revision and updated_at. Start unadmitted: null links/digests/epoch,
zero policy/checkpoint generations. Owner-selected namespace bootstrap creates
no authority and installs no key. No runtime auto-discovery/bootstrap operation.

Every changed policy/admission head advances coordination_revision once;
exact historical replay never advances it. Policies advance revision by exactly
one with exact predecessor domain digest. Admissions advance the independently
installed checkpoint chain by exactly one, with exact predecessor digest;
missing intermediate history must be reconciled, not skipped. Initial revision/
generation 1 requires null predecessor. Every head link has a same-namespace
typed FK to the corresponding immutable event. Temporary mismatches deny use.

##### 5.2 `artifact_versions` and `bundle_versions`

Artifacts retain namespace, UUID row ID, closed kind (`detector`, `rule-set`,
`operation-model`), exact artifact ID/version/schema, raw bytes, length and raw
SHA. The scoped kind/ID/version key is immutable and unique; same key/different
bytes fails, even if a caller supplies a matching-looking digest.

Bundles retain namespace, actual bundle UUID, exact S_version, exact framed S,
accepted-content envelope bytes/domain digest, and ordered referenced artifact
row IDs for detectors, rules and models. Validate the entire existing owner
bundle layout and each descriptor, language/class/spec/profile/model binding.
Order is significant; duplicate rule/source ordinals are not collapsed.
The content aggregate, not each member separately, must fit MAX_CONTENT.

Arrays do not provide element FKs. Publication alone resolves every element
under the namespace lock and checks same-scope kind/ID/version/hash/order before
insertion. Immutable/no-delete guards preserve the validated closure thereafter.
If implementation prefers a sixth normalized membership table, stop for scope
review rather than claiming array FKs exist. Exact UUID and S-version conflicts
cannot be resolved by renaming/replacing the old version.

##### 5.3 `authority_events`

Append-only id, namespace, closed kind, record_schema, exact record_bytes,
domain record_digest, recorded_at; unique event ID and typed operation key.
Kinds remain exactly policy, admission, approval, seal-authorization,
execution-authorization and execution-denial. Typed nullable columns carry
the corresponding record's bundle/approval/policy/admission/request/capture/
seal/work/attempt/run/occurrence/predecessor links, revisions and digests.
Closed kind-specific checks require exact byte/column equality and NULL shape;
composite namespace/org/codebase/request/attempt FKs prevent cross-scope links.
No generic JSON event whose fields merely resemble the intended type.

Policy/admission events retain original root signature bytes. Approval rows
retain original issuer signature, DER, inventory, adoption and PUBLICATION
receipt bytes/domain digest. SQL-generated seal/execution/denial records are
explicitly ledger observations, not signed approvals. SQL recorded_at is not
substituted for issuer-signed dates; both are retained with their different meaning.

Keep immutable request-command bytes/digest alongside each mutating event for
idempotency (§6). For positive execution chains, index exact namespace/attempt/
target and enforce one initial authorization, a unique predecessor successor,
and unique target/work_revision. Renewal must point to the exact current leaf,
same attempt/token/run/input; it may reference a newer admitted policy.
Do not traverse all history to find a target: use bounded indexed lookups.
Denial is a different kind and never a chain-positive permission. A completed
or failed target cannot acquire another initial grant by changing operation key.

##### 5.4 `request_bundle_bindings`

Immutable composite occurrence request scope, exact bundle/approval/initial
policy/checkpoint event links, original SEALED bytes and its raw digest, resolved
timestamp and actual initial command bytes/digest. Unique org/request; all
typed columns agree with the original frame. Retain the original requested
policy's ordered binding content separately from source/runtime identities.
Later authorizations reference this history; they never update its current-policy
fields, resolved_at or checkpoint to make an old request appear freshly resolved.

For all four history tables, owner-level UPDATE/DELETE/TRUNCATE must fail;
function-only INSERT is required. Namespace transition guards allow only the
enumerated coordination changes. Normalize hostile inherited/default ACLs and
force RLS. Trigger disabling, replacing trusted functions or restoring both
independent authority stores by a privileged host administrator is outside this
capability boundary, not a feature proven safe by immutable row declarations.

#### 6. Requests are not receipts: exact replay semantics

Proposed new internal command format, requiring root/schema-owner approval:
`scanipy-accepted-ledger-command/1`. It belongs in the actual accepted-input
schema/codec package, not a separate services-free lookalike. Exact keys:
`schema`, `action`, `operation_key`, `namespace_id`,
`expected_coordination_revision`, `body`, `objects`.
UUID fields are canonical UUID text on wire; coordination is nonnegative int64.
Action is one of install-policy, record-admission, publish-builtin,
create-bound-request, seal-bound-capture, authorize-detector, renew-detector.
No arbitrary extra action or metadata. Maximum canonical command JSON 65,536
bytes, with existing depth/value/string bounds. Binary inputs are separate
ordered parts; each object descriptor has exactly role, ordinal, length,
raw_sha256. Roles/ordinal counts are fixed by the selected action below.

Common body parts `admission` and `bundle` mean the **actual owning**
AdmissionExpectation and BundleExpectation shapes, not weaker duplicates.
`fence` is exactly work_item_id, work_attempt_id, fencing_token, work_revision;
its values are commands to be checked, not a constructed ExecutionBinding.

| Action | Exact body fields | Exact binary object sequence |
| --- | --- | --- |
| install-policy | predecessor_policy_digest (nullable only initially) | policy, root-signature |
| record-admission | predecessor_checkpoint_digest (nullable only initially) | checkpoint, root-signature |
| publish-builtin | admission, bundle, publisher_artifact_digest | actual PUBLICATION_INPUT frame; framed S; detector blobs in manifest order; rule blobs in manifest order |
| create-bound-request | admission, bundle, approval_event_id, verifier_artifact_digest | occurrence request envelope; planned-policy envelope |
| seal-bound-capture | admission, fence, resolver_artifact_digest | actual occurrence capture/seal request; source inventory; accepted-content envelope |
| authorize-detector | admission, fence, resolver_artifact_digest | actual occurrence run-input envelope |
| renew-detector | admission, fence, detector_run_id, previous_authorization_id, resolver_artifact_digest | none; actual occurrence renewal derives its duration from the locked work policy |

The occurrence binary object names above are exactly `request`, `planned-policy`,
`seal`, `source-inventory`, `accepted-content`, and `run-input`.
There is no invented renewal envelope. Envelope names refer to the owning types;
their full validated bytes remain inputs, not merely three caller hashes.
For seal/authorization/renewal, request/bundle/capture/run scope is read from
actual locked rows. Do not add caller-selected IDs to fill unknown slots.
Publication input already owns its evidence role schema. Administrative commands
have no caller-selected `verified` result. Configured artifact digests are
installed-adapter expectations, not scan-user choices or loaded-code attestation.

The command's raw object descriptors and actual bytes are both revalidated.
Aggregate raw inputs use the existing content/authority/MAX_PACKET ceilings.
The command domain digest is distinct from all receipt/event/content digests.
Store original command bytes and original binary material, or immutable typed
references which recover the identical bytes. A command key match requires
exact complete command/input equality, not just a match on selected fields.

Receipt event IDs/times and newly allocated request/run/seal/lease IDs come from
the actual DB operation. A caller cannot submit a preconstructed PUBLICATION or
EXECUTION record and have it become its own evidence of commit.
Replay first locks the namespace and finds the exact scoped operation key.
If identical, return the original immutable receipt, IDs and bytes, explicitly
as replay; do not rerun mutation, refresh timestamps, renew a lease, or launch.
Changed input is conflict. Returning historical bytes does not assert their
current eligibility; live readers still perform §10. A changed current head
does not rewrite an otherwise exact historical receipt.

If commit acknowledgement is lost, discard that transaction/session, then read
or retry the exact key with the original bytes on a fresh transaction. No
re-signing, replacement event, alternate key or second child launch is justified
by a missing acknowledgement. A genuinely uncommitted stale command must be
reverified under current policy, not silently altered under its old key.

#### 7. Exact operation inventory and atomic relationships

All new public SQL names below are proposals with `_v1` suffixes. They accept
the exact action command plus its fixed raw parts, or the exact read selectors
described below. Unknown signatures/actions fail before mutation. The service
authenticates the real tenant/operator before choosing a configured capability.

| Function | Capability and transaction obligation |
| --- | --- |
| `install_policy_v1` | policy-admin only; exact signed successor; full grant/tombstone evolution; event and namespace head atomically advance. |
| `record_admission_v1` | policy-admin only; exact independently installed signed checkpoint; retain event and matching coordination copy atomically. |
| `publish_builtin_bundle_v1` | publisher only; current admitted active publication grant, unchanged preverified bytes, entire content closure plus approval/receipt commit together. |
| `read_publication_receipt_v1` | publisher/reader/resolver; exact namespace + publication key or approval UUID; returns historical bytes, never a permission boolean. |
| `read_exact_bundle_v1` | reader/resolver; exact namespace + bundle UUID + accepted-content digest; no latest lookup. |
| `read_authority_event_v1` | reader/resolver; exact namespace + kind + event UUID + domain digest. |
| `read_request_binding_v1` | reader/resolver; exact authenticated org/codebase/request; original frame only. |
| `create_bound_request_v1` | resolver; create actual occurrence request/work plus original registry binding in one atomic function. |
| `seal_bound_capture_v1` | resolver; current live claim/current authority; actual capture/seal/lease plus SEAL_AUTHORIZATION event in one commit. |
| `authorize_detector_run_v1` | resolver; actual begin-detector-run result plus initial EXECUTION in one commit; completed-run replay is not authorized anew. |
| `renew_authorized_execution_v1` | resolver; detector only initially; actual renewal and successor EXECUTION in one commit. |
| `read_execution_authority_v1` | resolver only; exact actual ExecutionBinding + installed admission expectation; locked current context read. |
| `recheck_execution_authority_v1` | resolver only; same binding + prior context/head identities; fresh locked check, no record refresh. |

Denial insertion is a **private** path of authorize/renew only when an actual
valid detector target can be named, not a caller RPC accepting a fabricated
denial event. A pre-seal failure cannot fill the required run/capture/lease slots
and uses ordinary bounded attempt failure instead. No `claim_authorized_identity_v1` grant
exists in this first implementation; its owning contract remains a later TODO.
No statistical publication alias and no SQL function for root-key installation.

Administrative ingress checks original root/issuer signatures and supported
schemas before taking DB locks. Under lock, SQL repeats all byte/reference/
scope/history/grant/time/head checks that do not require crypto or host state.
Every intermediate policy must be validated on insertion, not only the old and
latest endpoints which the current verifier can compare. Old grant identity,
key fingerprint/version, issuer, scope and original validity interval remain
immutable; retired/revoked tombstones cannot disappear or reactivate. New use
of an old publication under retirement follows actual verifier `_grant_use`:
retirement happened after publication, and validity still holds; revocation
never permits new use. Publication itself requires an active current grant.

Actual request ID allocation is important: occurrence `create_request_v1`
generates it. The combined function must call that operation first, then build
the original SEALED manifest with the **returned actual ID**, actual post-lock
resolved_at, original publication evidence and selected current admitted objects,
and commit binding and request together. A framing failure rolls back both.
Do not guess a UUID, add an unreviewed externally assigned-ID path, publish a
half-bound request, or rewrite SEALED after commit.

This requires a narrow private SQL canonical/frame implementation for the
already-owned schemas, independently cross-tested byte-for-byte with actual
`encode_document`/`encode_frame` and occurrence envelope codecs. PostgreSQL
`jsonb::text` is not that encoding. Validate original JSON before duplicate-key
loss, maintain exact UTF-8/key/number semantics, and bound depth/values/escaped
bytes before construction. Reusing an occurrence private helper requires an
explicit narrow grant; this proposal instead keeps any new SQL helper private
to the accepted owner and requires owner-codec equivalence tests. It is not a
second semantic schema or permission to normalize old raw content.

Sealing fetches exact original accepted raw blobs from the binding; it never
takes arbitrary caller substitutes for them. The source capture inventory and
SCM/custody proof remain separately verified owning inputs. Initial detector
authorization reads the actual new run ID, exact immutable run input digest,
capture/seal/lease, current work revision and token from occurrence operations.
A pre-existing completed run returns historical results only; a failed target
uses existing retry/supersession rules, not a resurrected authorization.

Renewal uses actual post-renewal revision and both lease expiries. Same-attempt
token is unchanged. New attempt means its actual new token and initial event,
not a renewal of an old chain. Keep one active detector launch per capture/
detection attempt in the first adapter. Authorizing a second run cannot reuse
the first run's authorization even if their input hashes coincide.

Positive authorization samples DB time after locks and requires current live
work, capture consumer and admitted grant/policy/checkpoint. The effective
deadline is the minimum of work lease, capture lease, grant not_after, policy
expires_at and checkpoint expires_at. A recorded 900-second work lease cannot
extend a shorter permission. Convert this to a bounded monotonic runtime
deadline only in the real launcher, with its separately checked current clocks.

Denial records use the actual existing DENIAL schema and `observed_at`, not
`authorized_at`. They require a valid identifiable bundle/target/fence and
cryptographically valid admitted policy material; expiry/denial may prevent use.
Missing/corrupt trust, unavailable checkpoint or stale foreign fences cannot
fabricate those required slots. Live targets may use the existing bounded
failure operations; closed/lost-fence targets require the separately installed
recovery evidence path described in §12, not a fictitious ordinary DB writer.
A valid live denial commits failed run/attempt state with its event;
no child launches while failure persistence is retried. Preserve raw findings.

#### 8. Two execution-owned bridges and fixed global lock order

The accepted owner cannot directly SELECT FOR UPDATE occurrence tables under
the promised execute-only grants. The current private `v1_lock` is not a safe
runtime grant: it exposes generic kind/live choices and returns broad rows.
Do not solve this by granting owner membership, table DML or a generic helper.

Propose exactly these new execution-owned SECURITY DEFINER bridges, callable
only by `scanipy_accepted_owner`, not by scanner, publisher or resolver logins:

1. `lock_accepted_capture_context_v1(org, work, attempt, token, revision)`:
   fixed capture_detection live mode; internally use existing parent locks,
   validate the actual claim and return bounded typed control fields. Before
   sealing, capture/seal/consumer are explicitly absent; after sealing return
   the actual same-attempt capture/lease and seal binding. Never invent IDs.
2. `lock_accepted_detector_context_v1(org, work, attempt, token, revision,
   run_id, capture_lease_id)`: same parent order, exact live detector target,
   actual sealed source/bundle/input binding and current consumer. Reject
   missing/mismatched run/consumer, wrong kind, terminal/cancelled state or fence.

The capture bridge's exact internal return keys are org_id, codebase_id,
request_id, work_item_id, work_attempt_id, fencing_token, work_revision,
requested_policy_digest, attempt_policy_digest, lease_expires_at, capture_id,
seal_id, capture_lease_id, capture_lease_expires_at, accepted_content_digest,
acceptance_evidence_digest, db_now. UUID/int/digest/timestamp encodings follow
the actual owner schemas. Before sealing, the six capture-through-evidence
fields are all null; after sealing all are present. Reject a partial group.
The detector bridge returns that fully present shape plus detector_run_id,
run_input_digest and run_state; state is exactly pending or running. All fields
are taken from actual validated rows and canonical envelopes, not input echoes.
The seal's acceptance_evidence_digest is the raw original SEALED frame digest.

These are closed internal SQL result shapes, not replacement application
ExecutionBinding models, durable receipts or grants. The accepted owner must
validate the result's scope and exact expected fields before constructing the
actual owning models. Raw source/result blobs are not returned. No caller
`live=false`, arbitrary lock table or open-ended returned row dictionary.

All combined operations take this order:

```text
accepted namespace/head
  -> occurrence request
  -> capture (if it exists)
  -> work item(s), UUID order when plural
  -> attempt(s), UUID order when plural
  -> detector run(s), UUID order when plural
  -> capture consumer(s), UUID order when plural
  -> future runtime barrier row(s), UUID order when plural
  -> fresh clock_timestamp() and complete live checks
```

Parent serialization preserves existing ordinary operations; new consumers
must not first hold a consumer/barrier and then try to acquire its parents.
Add an explicit consumer lock after the current run-lock stage; the current
v1_lock already checks its data under parent locks but does not return it.
Never reuse the earlier time sample after waiting for another required lock.
The initial lookup of immutable IDs does not authorize anything; reread/check
locked rows and all exact scope/IDs before return. Lock timeout is failure.

Combined grants to accepted owner are only the two proposed bridges plus these
actual existing occurrence signatures (no private wildcard EXECUTE):

```text
create_request_v1(uuid,uuid,bytea,bytea,bytea,bytea)
register_capture_and_seal_v1(uuid,uuid,uuid,bigint,bigint,
  bytea,bytea,bytea,bytea,bytea,bytea,bytea,bytea[],bytea[],bytea)
begin_detector_run_v1(uuid,uuid,uuid,bigint,bigint,bytea,bytea)
renew_capture_detection_v1(uuid,uuid,uuid,bigint,bigint)
fail_detector_run_v1(uuid,uuid,uuid,bigint,bigint,uuid,bytea,bytea,bytea)
finish_capture_detection_v1(uuid,uuid,uuid,bigint,bigint,bytea,bytea)
```

Do not grant retain_detection_batch, claim/expire/retirement, identity, generic
v1_lock, v1_renew or v1_finish to this new owner by convenience. Ordinary detector
claim and evidence ingestion remain under their existing dedicated capabilities;
the accepted owner uses finish only for the explicit failed-attempt branch.
Resolve/test this exact catalog allowlist and reject extra overload grants.
All definers have fixed search_path and explicit tenant checks. Trusted org
context must come from authenticated server scope; `app.org_id` is not login
authentication. Existing role names are refused rather than adopted.

Cancellation, timeout/failure ingestion and cleanup must remain recordable
without acquiring new positive authority. Those parent-only paths must never
take the namespace lock later. If a future operation needs both, restart in the
global order. No operator, signer, verifier subprocess, filesystem reservation,
container operation or arbitrary callback runs while SQL locks are held.

#### 9. Role and grant matrix

All five new roles retain the owning contract's NOLOGIN, NOINHERIT,
NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOBYPASSRLS flags.

| Role | Permitted new capabilities |
| --- | --- |
| accepted_owner | Own accepted schema; two private execution bridges plus exact combined-operation occurrence functions; no runtime membership/login. |
| accepted_policy_admin | install_policy_v1 and record_admission_v1 only. |
| accepted_publisher | publish_builtin_bundle_v1 and read_publication_receipt_v1 only. |
| accepted_resolver | Exact listed content/history reads and bound request/seal/detector authorization/renewal/current-reader functions. |
| accepted_reader | Exact scoped historical content/event/binding/publication reads only. |

Names above abbreviate the `scanipy_accepted_` role prefix. Deployment explicitly
assigns authenticated service logins to selected roles; this note creates none.
Neither triage nor ranker can change policy, publish, authorize, suppress or
mutate findings through this ledger. No generic accepted RPC dispatcher.
Normalize new schema/table/sequence/function ACLs and default grants, revoke
PUBLIC execution, and assert absence of direct DML, REFERENCES, DDL, private
helper execution and owner-role membership. Test catalog permissions under
restricted real logins, not just a superuser transaction with a mocked GUC.
The additive migration must enumerate its new/replaced objects explicitly.
**Do not rerun `execution_v1_acl.sql` wholesale**: it enumerates every object
in that namespace and would revoke unrelated/previous accepted grants.
Snapshot unaffected ACLs before migration and prove exact preservation after it.

#### 10. Actual reader, admission material and cross-record consistency

Implement the exact public owner protocol:

```text
read_execution_authority(expected: ExecutionBinding)
    -> ExecutionVerificationContext
recheck_execution_authority(expected: ExecutionBinding,
                            context: ExecutionVerificationContext) -> None
runtime_profile: actual VerifierRuntimeProfile
```

Its instance is installed server configuration, never request/bundle/CLI input.
No constructor creates authority. The returned context is ordinary bounded data
which the actual verifier consumes; it is not a transferable launch credential.

Read algorithm:

1. Snapshot/revalidate actual expected binding and installed configuration.
   Read bounded independent admission state and configured trust from their real
   providers; capture exact generation/digest/epoch and root/config identity.
2. In one DB transaction, lock namespace then the actual detector context.
   Check external admission against exact current namespace policy/checkpoint;
   check original request binding, actual publication receipt and target's exact
   current positive authorization leaf. Check every one of the 18 binding fields,
   current policy/grant/lease conditions and scope. Sample time after all locks.
3. Build actual LedgerExpectation from committed PUBLICATION domain digest,
   original SEALED raw digest, EXECUTION domain digest, actual binding and exact
   current policy/admission event IDs. Build actual AdmissionExpectation from
   the independently installed checkpoint. Construct LIVE from the actual four
   retained policy/signature/checkpoint/signature objects using the owner codec.
4. Return actual ExecutionVerificationContext with installed trust, admission,
   ledger, LIVE bytes and post-lock reference_time. Release DB locks before any
   verifier process. Re-read the external provider/config before returning;
   changed/missing state fails rather than returning a stale positive view.
5. Public `verify_resolved_qualified_rule` performs its existing actual bounded
   execution verification. It then calls recheck: fresh external reads, same
   locked DB validation, fresh time, exact prior context/head/leaf/binding
   identities. A change forces failure/new explicit authorization; do not amend
   or restamp the candidate context to make the old check appear current.

The required 18 fields are the actual ten UUID fields, fencing_token,
work_revision, four digest fields and two lease timestamps from models.py.
Authorization event_id aliases authorization_event_id; authorization_digest
is the domain hash of the retained exact EXECUTION bytes. UUID-string coercion
or equality after normalization is insufficient original-input validation.

There is no need for a new opaque admission schema: the existing LIVE frame is
the concrete proposed admission material for later runtime owner-adapter checks.
Decode its exact policy/checkpoint and compare the actual AdmissionExpectation
and installed provider. Journal pure replay still treats this role as opaque
until that adapter exists; it cannot infer authority from a raw blob digest.
For the execution role, decode actual EXECUTION bytes, recompute its domain hash,
and separately check raw ArtifactRef integrity. A pair of digest strings without
actual bytes cannot establish their cross-artifact relationship.

The authorization-to-source/run links must be checked by the trusted ledger,
not merely the scalar solver: request bundle/content, original seal, capture
consumer ownership, exact run input and attempt policy, current target leaf,
source custody/SCM adapter result and live barrier all have distinct owners.
Existing reader result fields remain unchanged; do not smuggle a source custody
or kernel cleanup claim into a permission digest.

#### 11. Publication, revocation and restore races

The independent provider retains the last installed generation/digest/epoch
outside database backup/restore. Its signed checkpoint is installed only by
the actual privileged administrator, with bounded no-follow reads, durable
atomic replacement and serialization. An ordinary reader cannot bootstrap it
from the highest signed checkpoint found in the DB or repair it with old data.
The root key/administrator/provider storage choice is still outstanding.

Policy advance intentionally has a blocked interval, not a fictitious DB/file
atomic commit: validate successor, commit policy head, install external signed
checkpoint for that head, then record matching DB admission copy. Until both
copies and the head agree, deny new use. Exact retries reconcile signed bytes
and predecessor keys; never restore an earlier policy to recover availability.
Normal rotation preserves epoch. Expired checkpoint blocks; it is not cached
permission simply because the database still contains its signature.

Before attaching a restored DB to live services, independently install a
`block` checkpoint with a new epoch and exclude existing launchers. Quarantine
the restored endpoint; recover missing policy history from independently trusted
material; reconcile old work, leases, captures and runtime holds; then explicitly
install new admit for the exact recovered current head/new epoch. No old-epoch
authorization or request receipt becomes a new permit. Missing trusted recovery
material means blocked operation. Do not purge findings to enable recovery.

Provider, DB and launcher clocks must agree within the owning 30-second bound;
detected backward movement or excess skew blocks positive authority. Signed
second-resolution dates and microsecond DB lease timestamps retain their exact
formats. Rechecking after verification/commit and immediately before launch is
mandatory, but does not make revocation instantaneous or lock external state
atomically with SQL. The linearization point is the locked authorization commit
under the observed current head; later revocation prevents new uses and triggers
the separately implemented runtime termination/reconciliation policy.

This design does not defeat an administrator rolling back both DB and independent
admission state, replacing trusted code/keys, falsifying clocks, or attaching a
restored DB outside the controlled procedure. No consensus/hardware attestation
is available or claimed. Document this threat boundary in the eventual runbook.

#### 12. Relationship to runtime exclusion and retained failures

The DB-BAR-01 nonexpiring held/released barrier is still required in addition to
leases and this ledger. A valid authority row does not establish that a previous
parent or child is dead. Work-item-wide native exclusion applies across attempts;
capture-wide holds block retirement. Cancellation/failure remains recordable and
does not release the barrier merely by releasing ordinary capture leases.

Future barrier claim must use an actual current authorization leaf and lock in
§8 order. Persist the exact authorization and intended request/input/launch scope
before reservation/create. Release is not granted to the general resolver: only
an installed trusted recovery adapter with actual current exclusion/cleanup
evidence may request it. A structurally valid receipt/hash or absent PID is not
that proof. Replayed release returns history, not permission to launch again.

Exact existing claim/release requests are looked up and byte-compared before
fresh positive live-admission checks. Replay may return original history after
expiry, cancellation or release, without performing a new launch or changing
the old receipt. A replayed claim's own held row is not an earlier competing
hold. Only a **new** claim checks predecessor holds/current permission and must
require the exact detector run to be pending/running: `begin_detector_run_v1`
can return a completed historical run while the enclosing work is still live.
That completed target is not eligible for a new native hold or authorization.

Late raw bytes after cancellation/expiry need special care. Actual fe61
`retain_detection_batch_v1` and `fail_detector_run_v1` permit exact existing
terminal replay but require live `v1_lock` for new writes; they do not offer a
general late-write path after the run is terminalized. Preserve actual late
streams/results in the installed recovery journal, linked to the old run and
barrier, without creating occurrences, claiming successful detection, rewriting
terminal rows, or treating old authorization as live. The proposed journal may
retain pending call results during recovery and forbids missing-result terminal
success; its pure schema does not implement durable recovery storage. Any DB
late-observation ingestion needs its own append-only codec/function contract.
Do not widen ordinary live APIs or recovery-role grants to bypass those fences.

Crash after DB hold commit but before filesystem reservation remains a separate
unresolved pre-reservation recovery path. No terminal journal exists to cite.
Do not fabricate null terminal references, reserved/cleanup events, or force a
normal terminal-release schema onto it. Exact daemon/name/ownership provenance
and old-parent exclusion need their own reviewed protocol before any release.
This ledger supplies real event links for that design; it does not solve it.

#### 13. Required falsifiers before any operational claim

These are implementation acceptance TODOs, not tests run for this note.

| ID | Required controlled failure / positive boundary |
| --- | --- |
| AL-T01 | Restricted real PostgreSQL roles: all authorized functions work; cross-org/global confusion, direct DML/DDL/REFERENCES, private helper and owner membership fail. Hostile default ACLs do not leak grants; unrelated existing ACLs remain byte-for-byte unchanged. |
| AL-T02 | Canonical owner/SQL codec equivalence, Unicode/control escaping, duplicate keys before jsonb loss, deep/large values and N±1 aggregate bounds; malformed SQL array dimensions/lower bounds. |
| AL-T03 | Same operation key/exact original bytes returns same IDs/times/signatures; one changed member, order, signature, expected head or target conflicts. Lost commit acknowledgement never allocates a second event or run. |
| AL-T04 | Raw and domain digests deliberately differ. Reject swapped EXECUTION/ArtifactRef identities, false PUBLICATION links and a valid-looking caller receipt absent from the actual ledger. |
| AL-T05 | Policy predecessor/revision and checkpoint predecessor/generation exact; missing intermediate tombstone, key mutation, retired/reactivated or revoked grant rejected; publication vs historical retired-use rules kept distinct. |
| AL-T06 | Last invalid bundle member rolls back all new artifacts/bundle/approval. Exact version reuse allowed only with identical raw bytes. Ordered model/rule/source clauses remain intact. |
| AL-T07 | Real SQL request ID appears in original SEALED; force framing/binding failure after ID allocation and prove request/work/binding all roll back. Exact replay never rewrites original current-policy/resolved_at fields. |
| AL-T08 | Seal/source input mismatch or final authorization insertion failure rolls back the seal/lease changes; valid source custody is independently required, not inferred from the accepted bundle. |
| AL-T09 | Actual run allocation plus initial event atomic; completed historical replay yields no new authorization; changed key cannot reauthorize completed/failed run. Same hash on a different run remains a different target. |
| AL-T10 | Renewal reads actual post-update revision/expiries, same token; chain fork, old predecessor, wrong run/attempt, renewed secondary target or old token rejected. Failed successor insert rolls back lease renewal. |
| AL-T11 | Hold a parent/run/consumer lock until the lease expires; authorization/read/recheck must sample time after the final lock and fail. Check real lock timeout, clock skew/backward-time failure and shorter grant deadlines. |
| AL-T12 | Change/revoke policy or external admission at preflight→SQL, SQL→commit, context→verifier and verifier→recheck boundaries. No stale positive fallback or rewritten context; exact historical reads remain historical. |
| AL-T13 | Restore an older otherwise correctly signed DB while independent epoch/head is newer or blocked; no execution. Missing recovery material stays blocked; no highest-DB-generation self-bootstrap. |
| AL-T14 | Actual malformed/forged ExecutionBinding UUID/int/string slots, hostile dataclass/attribute callbacks, changes after snapshot, bool-as-int and wrong declared digest all fail before consumer use. |
| AL-T15 | Reader compares all 18 fields, actual chain leaf, original SEALED and both policy/checkpoint events; fake constructed Context/VerifiedQualifiedRule never substitutes for the installed reader and live recheck. |
| AL-T16 | Missing provider/root/profile/controller/operational verifier, unknown schema, unsupported identity execution or statistical publication fail explicitly; test keys/diagnostic worker cannot enter production configuration. |
| AL-T17 | Failed/revoked/expired attempts preserve raw detections and exact failure; malformed authority does not create a DENIAL with invented fields; retry is not a loop of permanently pending work. New late bytes after terminalization stay in real recovery evidence, not rewritten run rows or new successful occurrences. |
| AL-T18 | Concurrent authorize/renew/cancel/expire/retire with deterministic interleaving: no reverse lock order, no duplicate chain successor, cancellation recordable and retirement held while real runtime exclusion remains unresolved. |
| AL-T19 | Pre-reservation crash cannot produce a fabricated terminal release; old parent resuming after lease expiry remains excluded by the separately reviewed actual barrier mechanism. Exact claim/release replay precedes new-use checks, excludes its own hold, and returns no new permission; a completed historical target cannot obtain a new hold. |
| AL-T20 | #399 full actual production reader/worker/recheck path and #400 release path use real installed identities/current storage and retained bytes. Pure schema tests are explicitly insufficient for this acceptance. |

#### 14. Proposed allocation sequence and completion criteria

- **AL-01 — Owner decisions / admission adapter.** Confirm actual trust root,
  administrator/publisher actors, namespace/deployment, protected independent
  storage and service-login assignments. Implement real bounded administrative
  validation/provider before publishing anything. No keys or trust are created
  by this note; SQL migration may only start with unadmitted namespace state.
- **AL-02 — Owner codecs / command contract.** Review §6's new command shape;
  allocate actual accepted-input schemas/codecs and narrow SQL encoding guards.
  Cross-test existing records/frames without rewriting historical raw bytes.
- **AL-03 — Migration / capabilities.** Five tables, immutable transition guards,
  scoped indexes/FKs, two execution-owned bridges and exact role/function grants.
  Use real isolated PostgreSQL permission/rollback/locking tests, not mocks alone.
- **AL-04 — Atomic publication and request/seal operations.** Implement complete
  content and original-frame binding; demonstrate actual receipt provenance and
  no half-bound request/seal after failure.
- **AL-05 — Per-detector authorization and reader.** Implement actual run/renewal
  transactions plus the existing reader interface and full immutable evidence.
  Keep operational entrypoints refusing while installed dependencies are absent.
- **AL-06 — Runtime barrier integration.** Review DB-BAR-01 together with this
  ledger, especially current-head parent ordering and pre-reservation recovery.
  Do not enable launch/retry/retirement until old-parent exclusion is real.
- **AL-07 — Operational and restore falsifiers.** Run approved constrained tests
  with owner-selected identities and actual controller. Only then consider
  enabling real #399/#400 consumers; preserve original diagnostic evidence.

Before coding, root should decide: (A) accept §3's signature-verified-ingress
trust boundary or allocate a new bounded current-use-preflight mode; (B) approve
§6's single owned command schema and §7's narrow owner-codec-equivalent SQL
framing; (C) approve the two exact cross-owner bridges and grant/lock inventory;
(D) allocate the independent admission/provider and old-parent exclusion work,
with operator choices explicitly pending. No source implementation is authorized
merely by resolving these design questions in prose.

Completion of AL-02/03 alone is not current authorization. Completion of all
these ledger tasks is still not proof of call binding, semantic soundness,
native process safety, source custody, full R19, R07 persistence integration,
R04 corpus acceptance, G1/G2, or readiness on the presentation machine.

<a id="al03-appendix-b"></a>
## Appendix B. Amendment 01 — retained historical text

Historical labels, snapshot dates, temporary paths and numbered section references
in this block belong to the original record. They do not override the current
precedence, scope or implementation status in sections 0–4 above. Section references
inside this block refer to that same block unless an original document is named.
The complete source text follows, with heading levels demoted for this document.

### AUTH-LEDGER-AMENDMENT-01 — Exact commands, policy binding and denial/replay

Status: PROPOSED DESIGN AMENDMENT; no implementation or operational approval.
Date: 2026-09-25. Author: root-delegated independent corpus/tooling reviewer.
This is an additive temporary design document, not a repository modification.

#### 1. Authority, precedence and unchanged boundaries

This amendment closes five concrete review findings in the unchanged proposal
`AUTHORITY-LEDGER-DESIGN.md` (741 lines), SHA-256
`16cccece8c5af9772518e241ee791d470db2f0ad1108b1e0924dc579006332ac`.
If approved, the explicit refinements below supersede only its ambiguous
command caps, lower-level replay, policy derivation, denial/renewal and grants.
All its other restrictions and unresolved operational dependencies remain.

The actual inspected owners are:

- accepted-input resolver `58b552c919a99f244c12cbdb11f9fb3eb8cdd64f`, at
  `/tmp/scanipy-accepted-resolver-7MduJ3tp`;
- occurrence store `fe61c9cdcf4ae56cf5c7fd682b3a73c3502f1808`, at
  `/tmp/scanipy-occurrence-store-hbleeF`.

The original proposal records the inspected source-file hashes. In particular,
this amendment uses actual `accepted_inputs/{models,schemas,codec,verify}.py`,
`occurrence_store/{_schemas,models,codec,repository}.py` and the versioned
execution SQL/ACLs, not a new lookalike ExecutionBinding or receipt model.
No code, SQL, keys, native command, test, installation or remote action was run
to establish this design. All tests below are TODOs.

Root has selected these directions, subject to the exact amendment review:

1. Bounded signature-verified administrative ingress, not a new current-use
   verifier mode or a diagnostic fallback. SQL trusts the installed privileged
   ingress service for checks it cannot perform, repeats its own checks and
   does not accept a caller `verified` bit.
2. One command codec owned by the actual accepted-input package, independently
   equivalent private SQL framing, the two execution-owned bridges, and narrow
   schema USAGE plus explicit function grants.
3. Exactly one explicitly selected installed-supported language/profile per
   detector binding in this first integration. Complete accepted raw contents
   remain unchanged. Separate language requests/runs are allowed; required
   Java AND Python evidence is not reduced.

The seven command action names and proposed SQL functions below are NEW owner
schema/API work. Existing records/envelopes retain their current schemas.
No migration or source allocation follows merely from writing this amendment.

#### 2. No adoption of preexisting low-level operations

The current occurrence functions intentionally support ordinary historical
replay. That is not evidence a combined authority-ledger transaction happened.

| Actual lower-level behavior | Required NEW combined-command behavior |
| --- | --- |
| `create_request_v1` finds `(org_id, idempotency_key)` and returns its old request/work | Reject if there is no exact previously committed combined command and request binding; never attach the first binding after the fact. |
| `register_capture_and_seal_v1` finds a matching old seal | Reject; do not attach a first SEAL_AUTHORIZATION or pretend the original seal and new event committed atomically. |
| `begin_detector_run_v1` returns an old running/pending exact invocation | Reject new authorization under another operation key; do not adopt another adapter's run. |
| `begin_detector_run_v1` returns a completed binding | Historical result only; no initial authorization, renewal or new native hold. |

Every combined function first authenticates capability/scope, bounds and
validates the complete command, locks its namespace and looks up its exact
operation key. The key is unique across actions within that namespace. A key
match requires identical action, command bytes and every ordered binary part,
not merely matching selected digests. It returns the original committed result
without invoking the lower-level mutation, checking fresh eligibility, extending
a lease, refreshing time or changing the namespace revision. Changed input is
a conflict. Historical replay remains history, never launch permission.

Only when no combined command exists does the function perform new-use checks
and compare `expected_coordination_revision` against the locked current head.
For a NEW create/seal/begin operation, any lower-level `replayed=true` or
completed result aborts and rolls back the entire transaction. Explicitly
detect an existing unbound request/seal/run before building new ledger output;
also check the returned result to close a race. No adoption/import fallback.
Underlying functions still perform their own exact replay and permission tests.

The request's existing nonempty idempotency string is not the new command's
UUID operation key. Preserve and check both; changing either cannot bypass
the other namespace's uniqueness or create retroactive atomicity.

After an ambiguous commit, discard the connection and retry/read the identical
combined command through a fresh transaction. Committed history is returned
even if the attempt is now terminal or authority expired. If no transaction
committed, fresh eligibility/fence checks still apply; failure to commit is not
permission to choose a replacement key. A read observes committed DB history,
not source custody, kernel cleanup, durable filesystem evidence or current use.

#### 3. One exact owner command and seven fixed SQL entrypoints

##### 3.1 Common wire and binary parts

Proposed schema: `scanipy-accepted-ledger-command/1`. Exact JSON keys are
`schema`, `action`, `operation_key`, `namespace_id`,
`expected_coordination_revision`, `body`, `objects`. Unknown, duplicate or
missing keys fail before conversion to a representation that loses duplicates.
Canonical UTF-8, integer and lexical rules are those of the actual accepted
owner. UUIDs are canonical UUID strings on wire; the revision is an exact
nonnegative signed-int64 integer, never bool.

Every object descriptor has exactly `role`, `ordinal`, `length`, `raw_sha256`.
The ordinal is zero-based within its role. Singleton roles require ordinal 0;
repeated detector/rule roles require contiguous ordinals in manifest order.
`length` is the exact nonnegative byte length; hash is SHA-256 of actual raw
bytes, not a domain digest. The descriptor sequence and binary part sequence
must agree exactly. No duplicate descriptor, extra role, omitted member,
reordered member, NULL element or invisible trailing part is accepted.

Python inputs are detached, bounded exact primitives: exact command bytes and
an exact tuple of exact bytes, not an iterable, Mapping subclass or callback.
Original owning-model fields are snapshot/validated before any wire conversion:
no UUID-string repair or validate-then-reread. SQL takes non-NULL `bytea` and
`bytea[]`; nonempty arrays must be one-dimensional with lower bound 1. Empty
array is allowed ONLY for renew-detector. Bound cardinality, every length and
their sum BEFORE hashing, decoding or copying nested content.

Each proposed SQL function takes exactly `(command_bytes bytea, parts bytea[])`
and requires its own fixed `action`, not a caller-controlled dispatcher:

| Action / function | Exact body keys | Exact outer binary roles, in order |
| --- | --- | --- |
| install-policy / `install_policy_v1` | `predecessor_policy_digest` | `policy`, `root-signature` |
| record-admission / `record_admission_v1` | `predecessor_checkpoint_digest` | `checkpoint`, `root-signature` |
| publish-builtin / `publish_builtin_bundle_v1` | `admission`, `bundle`, `publisher_artifact_digest` | `publication-input`, `accepted-spec`, then all `detector` parts, then all `rule` parts |
| create-bound-request / `create_bound_request_v1` | `admission`, `bundle`, `approval_event_id`, `verifier_artifact_digest` | `request`, `planned-policy` |
| seal-bound-capture / `seal_bound_capture_v1` | `admission`, `fence`, `resolver_artifact_digest` | `seal`, `source-inventory`, `accepted-content` |
| authorize-detector / `authorize_detector_run_v1` | `admission`, `fence`, `resolver_artifact_digest` | `run-input` |
| renew-detector / `renew_authorized_execution_v1` | `admission`, `fence`, `detector_run_id`, `previous_authorization_id`, `resolver_artifact_digest` | none |

Only the two predecessor digest fields can be null, and only for the initial
revision/generation. All other listed body fields are required and nonnull.
`admission` and `bundle` use the actual AdmissionExpectation and BundleExpectation
field definitions, including the latter's scope-dependent nullable org_id;
these nested null rules are unchanged. `fence` has exactly `work_item_id`,
`work_attempt_id`, `fencing_token`, `work_revision`. It is not a new authority
model. Artifact digests must match installed service configuration; the command
field alone does not attest that artifact or authorize a scan user's choice.

`publication-input` is the existing PUBLICATION_INPUT frame with its exact ten
inner roles. `accepted-spec` is the existing framed S including its model bytes.
Detector/rule counts and order come from S, not from an untrusted declared count
alone. There are no additional model parts. Seal/authorization fetch the
original bundle and SEALED frame from the ledger; caller replacements are not
an input option. Occurrence envelope names mean the current owner schemas.

##### 3.2 Results and owner-schema changes

Propose one internal SQL return pair `(record_bytes bytea, replayed boolean)`.
This is explicitly NEW transport plumbing, not a new signed/durable receipt
schema, verification result or proof of client-observed commit acknowledgement.
Returned bytes must decode as the existing owning object for the action:

| Action | Existing owning object returned |
| --- | --- |
| install-policy | retained POLICY document |
| record-admission | retained ADMISSION document |
| publish-builtin | PUBLICATION receipt constructed from actual committed rows |
| create-bound-request | original SEALED frame containing the actual new SQL request ID |
| seal-bound-capture | SEAL_AUTHORIZATION record |
| authorize-detector / renew-detector | EXECUTION or DENIAL, according to the committed branch |

These objects keep their existing fields and raw/domain digest definitions.
Do not add a `verified`, `current`, success boolean, synthetic run ID or new
failure-code enum. The side-row operation key/action and exact original command
parts bind results that do not themselves have an operation-key field. Readers
obtain other actual occurrence IDs through existing permitted owner reads; the
return pair does not invent missing IDs. Only the transaction wrapper returning
after successful commit can acknowledge that write; a row returned inside an
uncommitted transaction is not a durable receipt to the caller.

Required ADDITIVE owner-schema work is the command schema/codec, seven signatures,
this internal SQL result shape and the two bridge result shapes. No change to
ExecutionBinding, DENIAL, run-failure, attempt-result or attempt-policy is
proposed. Any implementation needing another field must stop for owner review.

#### 4. Explicit input, fetch and hashing work bounds

These are proposed command-protocol limits, not demonstrated CPU, memory,
PostgreSQL storage or presentation-machine performance guarantees. They must
be implemented and tested before allocation can be called operationally ready.
They do not replace lower owning-schema limits or the full required corpus.

Constants in bytes: C=65,536 command JSON; A=1,048,576;
L=262,144 LIVE; P=131,072 policy; O=65,536 ordinary accepted object;
RSA-3072 signature=384. The command retains owner limits depth32, values20,000,
string16,384 UTF-8 bytes, int64. Its binary-part count is at most20,000 AND must
fit C's descriptor/JSON limits. Each occurrence envelope separately keeps its
actual 1MiB lexical/schema limits; do not silently apply accepted-document
string constraints to arbitrary existing occurrence messages/paths.

| Action | Maximum input W: command plus raw parts | Maximum generated result G |
| --- | --- | --- |
| install-policy | C+P+384 =196,992 | P |
| record-admission | C+O+384 =131,456 | O |
| publish-builtin | C+2A =2,162,688 | O |
| create-bound-request | C+2A =2,162,688 | A |
| seal-bound-capture | C+3A =3,211,264 | O |
| authorize-detector | C+A =1,114,112 | O |
| renew-detector | C =65,536 | O |

Publication's frame is at most A; its COMPLETE S+detector+rule content aggregate
is at most A, not A per member. Seal has three separate occurrence envelopes,
each at most A. The verifier's existing MAX_PACKET=2,621,440 is a different
protocol and must NOT be reused as a universal ledger command ceiling.
PostgreSQL/driver framing and hex/copy expansion are not included in W; their
bounded transport/memory implementation is an explicit later acceptance check.

For NEW commands, fetch only exact indexed immutable rows/parts plus the locked
head; no latest-bundle search, history walk or user-selected join. Charge every
logical fetched payload, including a repeated reference, before materializing
it. The following closed slots give F, the aggregate fetch ceiling:

| Action | Allowed fetched raw closure and F ceiling |
| --- | --- |
| install-policy | one predecessor policy/signature: P+384 |
| record-admission | current policy/signature plus predecessor checkpoint/signature: P+O+768 |
| publish-builtin | current LIVE L; at most A total existing raw content checked for same-version reuse; at most A prior publication evidence and O receipt for an exact existing publication conflict check: L+2A+O |
| create-bound-request | current LIVE L; exact complete bundle content A; original publication evidence A and PUBLICATION O: L+2A+O |
| seal-bound-capture | current LIVE L; original SEALED A; exact bundle content A; original planned-policy A: L+3A |
| authorize-detector / renew-detector | current LIVE L; original SEALED A; exact bundle content A; original planned-policy A; original occurrence seal A; exact run-input A; SEAL_AUTHORIZATION O and at most one prior EXECUTION O: L+5A+2O |

Predecessor/current head fields, bridge results and index-conflict keys are
bounded control metadata, at most O TOTAL additionally per command. No raw
evidence can be hidden in that allowance. Incrementally reuse a private fetched
blob after validating it; a second fetch is charged again. Distinct immutable
refs preserve provenance even when bytes coincide. Nested frame payloads are
inside their charged frame, not an excuse to fetch another uncounted closure.
All such parsed payloads still have bounded decode/hash work.

Exact historical replay has its own smaller path: fetch at most W original
command/parts, G original result and O control metadata, byte-compare and return.
It does NOT fetch the fresh positive-authority closure to manufacture permission.
The original command/input/result bytes must be recoverable; digest equality
alone is insufficient for idempotency. No more than one matching row is allowed.

PROPOSED common work ceilings: at most100,000 SHA-256 invocations and
134,217,728 bytes supplied to SHA-256 per command invocation, on either replay or new
command paths. Charge every actual raw/domain hash input, including schema+LF,
repeated validation and generated data; a cache is not quota exemption.
These are explicit finite admission limits, NOT a measured claim that all
syntactically maximal bundles fit. The C/header limit already narrows the set
of admissible member layouts; reject over-limit requests, never drop members.

The implementation must precharge before each new helper hash. Before invoking
unchanged occurrence SQL, reserve a reviewed upper bound for ALL its internal
hash work using actual envelope/raw lengths and its fixed control flow, then
reconcile without allowing an uncharged call. In particular, request work-payload
hashing, seal raw-member/authority hashing and failure lease-release hashing
are not free. If that bound cannot be established, the command is unavailable;
do not claim an after-the-fact counter constrains an opaque helper. Avoid
per-rule rehash of the complete bundle; decode once into bounded private data.

Keep statement_timeout15s and lock_timeout2s through the real restricted
connection/controller. A timeout rolls back; it is not positive authority.
The installed wrapper uses one public mutating command per transaction; these
per-command limits do not claim a global session/history/storage quota or
prevent a privileged service from issuing many separately bounded commands.
Positive/N/N+1 tests must demonstrate every action on the intended complete
Java/Python bundle and test the maximum supported member layout. An input/work
cap failure remains explicit unsupported work, not a claim the full submitted
requirements can be met by a reduced bundle. Any cap change needs reviewed
protocol/runtime evidence, not an unrecorded retry with increased limits.

#### 5. Complete planned-policy derivation, without content substitution

The trusted installed resolver validates the COMPLETE actual framed S and all
detector/rule/model bytes with the owning codec and QualifiedRuleKey/semantic
descriptor rules. It retains that entire accepted content exactly once. It
derives one occurrence BINDING for every S detector, in S order, as follows:

| Occurrence field | Required origin |
| --- | --- |
| `detector_id`, `class_id`, `detector_content_digest` | Exact detector member and checked raw detector/class correspondence; digest is raw SHA. |
| `engines` | Exactly `["ifds"]` for this first actual accepted profile; no CodeQL/Semgrep capability inferred. |
| `language` | Exactly one installed-supported selection from this detector's validated `language_profiles`, also present in its raw detector languages. |
| `rules` | ALL this detector's rule members in manifest order, with whole rule-set `rule_id`, raw rule SHA as `content_digest`, and actual owning `semantic_descriptor_digest` as `semantic_digest`. No clause ID substitution. |
| `key` | The injective selected-profile key below; a locator within this request, not canonical finding identity. |
| adapter/tool/code/environment policy digests and expected tool/code/image pins | Installed trusted resolver profile for that selected language/adapter; never bundle-provided authority or a copy from observed results. |

Proposed key spelling is the concatenation of `accepted-detector/`, the
zero-based detector ordinal in canonical decimal, `/`, exact language, `/`,
exact selected projection profile, `/`, exact selected source syntax schema.
Allowed values are the actual checked finite profile strings, not arbitrary
components. For this owner snapshot they are `python` or `java`,
`scanipy-java-python-scalar-flow/1` and `scanipy-source-syntax/1`.
Within one request the ordinal is unique; changing any selection changes the
key. No zip/order heuristic is used to infer semantic rule/source binding.

The whole ordered planned-policy, including actual capture_detection_runner,
identity_runner and identity_policy, is encoded with the occurrence owner.
Compare COMPLETE bytes with the supplied planned-policy; request's
requested_policy_digest must be its actual domain digest, and requested S
version/content must agree with the immutable bundle. Expected positive
artifact/image pins must be present and match installed profiles. A policy
digest is not a measured artifact/image digest. Preserve all these separately.

SQL independently checks the complete bundle-derived binding projection and
ordered membership, finite language/profile/key selection, required pins,
exact request/planned-policy correspondence, and seal equality. Installed
profile authenticity and raw source/host observation remain privileged adapter
obligations; no host trust is derived from a SQL row or caller-provided hash.
The adapter must not submit an arbitrary alternate planned policy merely
because it passes the ordinary occurrence schema. Retry and identity policies
retain their owner validation and separate explicit operational choices.

Actual attempt-policy v1 has assignment_id, code_policy_digest,
environment_policy_digest and lease_seconds: it has NO language field. Do not
quietly add one. Selection is immutable in requested planned-policy/key; the
actual attempt belongs to that exact request and its runner policy hashes must
match the selected planned runner. EXECUTION binds BOTH requested-policy and
actual attempt-policy digests. This is the explicit transitive attempt binding,
not a claim that a language field already exists. Later simultaneous
multi-profile-per-detector work requires an owner-schema/cardinality design.

When a detector supports both languages, choose one explicitly per request;
another request/run can select the other, retaining the same complete accepted
content identity. Do not duplicate raw detector bytes to manufacture another
binding, rename language to `mixed`, omit rules, or re-number their ordinals.
Coverage for unselected/unsupported source languages remains unknown/not run.
This mapping does not satisfy the full required Java+Python campaign by itself.

#### 6. Initial denial and renewal: actual rows and exact failure evidence

##### 6.1 Preconditions shared with positive authorization

After own-command replay handling, require an already combined-bound request
and authorized seal, exact run-input/binding, authenticated same-tenant scope,
live current capture_detection attempt/token/revision and actual capture lease.
Take namespace→request→capture→work→attempt→runs→consumer locks in the original
order, then fresh `clock_timestamp()` and complete live checks. Allocation of
a new run must be followed by its exact detector-context bridge and a fresh
post-lock check; do not reuse a time sample taken before a required lock wait.

For a DENIAL record, the current policy/checkpoint and original bundle/grant
history must still be valid, bounded, cryptographically checked identifiable
material, with an exact observed current head. They may deny positive use.
Missing/corrupt trust/provider data, foreign scope, stale fence, unbound request
or unavailable required linkage is a command failure, not permission to invent
DENIAL fields. Lost-fence/terminal evidence belongs to the future real recovery
journal, not a new ordinary terminal-row write.

Enforce at most one pending/running authorized detector target per attempt in
the combined SQL path, not merely one successor per target. Lock actual runs;
reject a different live target even if input digests coincide. A prior terminal
target is not active authority. Proper retries still use the occurrence owner's
new attempt/token and explicit supersession rules; no resurrected old event.

##### 6.2 Initial deny is a real metadata-only run transaction

Proposed minimal branch, needing explicit implementation review:

1. Validate the immutable source/seal/binding/run-input and live fence above.
2. Call actual `begin_detector_run_v1`; require a NEW pending metadata row, not
   replay/completed. No process, detector, source execution or coverage occurs.
3. Under held locks, evaluate current positive conditions. If positive, append
   actual initial EXECUTION. If an eligible denial below applies, construct
   existing DENIAL using this actual new run, capture, consumer and current
   fence/head. Initial `previous_authorization_id` is null.
4. In the same transaction insert DENIAL, call existing fail_detector_run and
   finish_capture_detection with the exact failed envelopes below, and retain
   the command/result. Any failure rolls back run/event/terminalization together.

Allocation here records a refused intended invocation, not an observed child
start. A different key cannot adopt that terminal run. Replaying this committed
combined denial returns exactly its original event despite terminalized work.

The actual DENIAL enum is unchanged. Evaluate reasons in this fixed order,
only after structural/scope/head prerequisites succeed:

1. `policy-expired`: current policy outside its valid time interval;
2. `unsupported-authority`: valid identified checkpoint blocks use or is outside
   its valid time interval, or the identified authority is not supported for
   this detector-purpose consumer;
3. `grant-revoked`: the identified approval's current grant is revoked;
4. `grant-expired`: identified grant is outside its validity interval;
5. `unsupported-authority`: remaining failed actual `_grant_use` retirement/use
   condition, without reclassifying a revoked or expired grant;
6. `missing-runtime-pin`: required installed runtime/artifact pin is unavailable
   or does not match the immutable requested profile.

Unknown/mismatched namespace, missing grant/tombstone, corrupt chain or missing
provider is rejected before this branch. Existing `scope-conflict` remains a
decodable owner reason but is NOT emitted by this first adapter; it must not
launder foreign scope into an otherwise valid target. Future mappings need a
reviewed amendment. Use DENIAL.observed_at, never EXECUTION.authorized_at.
All required owner fields come from actual rows/records/configuration, not zeros.

##### 6.3 Failed envelopes do not fabricate empty detector output

Construct actual `scanipy-execution/run-failure/1` with fixed code equal to the
selected existing DENIAL reason, fixed message `Accepted execution denied.`,
prefix bytes empty and prefix_sha256=SHA256(empty), observed_byte_count=null,
truncated=true, observed_full_sha256=null. The latter fields explicitly mean
there is NO complete child-output observation in this envelope. Empty retained
prefix does NOT mean the detector emitted zero bytes. No new failure enum.

Construct actual `scanipy-execution/attempt-result/1` with status=failed,
retryable=false, error={code: same reason, message: same fixed message},
actual_code_digest=null, actual_env_digest=null, completed_run_ids=[],
identity=null, identity_policy_reason=null. The empty completed list acknowledges
no successful run in this failure result; it does not delete or deny prior
retained runs/findings. Both envelopes are canonical owner bytes with their
actual domain digests. Bound each generated failure envelope by O.

Current fail_detector_run records failure without advancing work revision;
finish changes the work/attempt, advances revision and releases ordinary capture
leases. DENIAL retains the observed pre-terminal fence/leases unchanged. A
runtime barrier is NOT released by these operations. Do not claim no native
child exists merely from failed DB state, especially on a renewal denial.

##### 6.4 Renewal checks first; no extension on denial

Require the exact current positive EXECUTION leaf, same run/attempt/token and
input, exact supplied previous_authorization_id, live pending/running target
and unchanged original binding. Re-evaluate current authority AFTER locks.

- Positive branch: call actual renew_capture_detection, reread actual new work
  revision and both expiries through the bridge, then append one successor
  EXECUTION with action=renew. If recheck/event insertion fails, rollback the
  renewal. Same-attempt token stays unchanged.
- Eligible denial branch: DO NOT call renew. Append DENIAL with the actual prior
  authorization ID and observed old fence, then fail run/attempt atomically as
  above. No positive successor, no lease extension and no automatic retry loop.
- Malformed/missing/stale prerequisites: reject without creating positive or
  synthetic denial history. A separately authorized ordinary live failure may
  be persisted; if the fence is gone, retain future recovery evidence instead.

Any child already running is an outer controller/old-parent exclusion issue.
Its late bytes must remain tied to the old actual run/barrier in the real
recovery journal; ordinary fe61 APIs cannot append new terminal-run observations.
No new DB late-observation API or weakened fence is implied by this amendment.

#### 7. Exact permissions and bridge obligations

Add precisely `USAGE ON SCHEMA scanipy_execution TO scanipy_accepted_owner`.
Without it, granting function EXECUTE alone does not supply schema access.
Do NOT grant execution-owner membership, CREATE, table DML/REFERENCES/TRUNCATE,
sequences or generic private helper access. Accepted runtime roles receive
USAGE on their own accepted schema only as required for their fixed functions.

Grant execution function EXECUTE to accepted_owner ONLY for the original note's
two new fixed-live bridges and these existing exact signatures:

```text
create_request_v1(uuid,uuid,bytea,bytea,bytea,bytea)
register_capture_and_seal_v1(uuid,uuid,uuid,bigint,bigint,
 bytea,bytea,bytea,bytea,bytea,bytea,bytea,bytea[],bytea[],bytea)
begin_detector_run_v1(uuid,uuid,uuid,bigint,bigint,bytea,bytea)
renew_capture_detection_v1(uuid,uuid,uuid,bigint,bigint)
fail_detector_run_v1(uuid,uuid,uuid,bigint,bigint,uuid,bytea,bytea,bytea)
finish_capture_detection_v1(uuid,uuid,uuid,bigint,bigint,bytea,bytea)
```

Bridges remain defined by execution owner and callable only by accepted_owner;
they explicitly lock consumer rows AFTER runs and resample time afterward.
They return only the original note's closed actual-row control shapes; no
caller `live=false`, generic row dictionary or raw artifact fetch. No grants
to retain_detection_batch, claim, expire, retirement, identity, v1_lock,
v1_renew, v1_finish or arbitrary newly added overloads. Existing signatures and
ordinary checks are not replaced.

Because accepted_owner has no direct run-table reads, enforce the first
integration's single-target rule INSIDE those execution-owned bridges. The
public capture-context bridge requires no pending/running detector run in the
attempt before a new seal/begin path; the detector-context bridge requires that
the supplied pending/running run is the attempt's ONLY such run, regardless of
whether another run has an accepted-ledger event. Shared internal lock code must
not accidentally apply the pre-begin zero-run predicate to the detector bridge.
This is a proposed narrow bridge predicate, not an added return field or table
grant. Exact combined replay takes neither bridge. It prevents denial-finish
from silently interrupting an unrelated unbound live target under this adapter.

Only the privileged accepted function implementation can call the underlying
finish capability, and its reachable branch here passes status=failed.
The existing finish signature itself is broader; do not falsely claim its
EXECUTE grant enforces failed-only arguments. Runtime logins never receive this
cross-owner grant or accepted_owner membership. Test the actual restricted
roles and reachable functions, not only trusted superuser SQL behavior.

Strict action grants remain:

- accepted_policy_admin: install-policy and record-admission only;
- accepted_publisher: publish-builtin and its exact historical receipt read;
- accepted_resolver: create/seal/authorize/renew and exact approved reads;
- accepted_reader: exact historical reads only;
- accepted_owner: NOLOGIN implementation owner, never a runtime principal.

All five roles retain the original NOLOGIN/NOINHERIT/NOBYPASSRLS and other
nonadministrative flags. Concrete authenticated service login assignments and
global/tenant installation remain operator decisions, not inferred from GUCs.
`app.org_id` is scope context, NOT authentication or current authority.

Use fixed `search_path=pg_catalog,<trusted owning schema>,pg_temp` with pg_temp
explicitly last; qualify all referenced functions/relations. Revoke PUBLIC and
hostile default grants on only the explicitly new objects in the same migration
transaction. Preserve unrelated old ACLs; never replay the namespace-wide old
execution ACL scrub. Refuse preexisting reserved roles rather than adopting
their memberships/default privileges. Forced RLS applies to all new rows.

#### 8. Required implementation falsifiers and remaining decisions

The following are TODOs, not evidence produced by this amendment:

1. Cross-owner schema/SQL framing parity for all seven actions and every existing
   returned record/frame. Reject duplicate keys, unknown body/roles, wrong
   ordinals, multidimensional/lower-bound-zero arrays, bool integers, poisoned
   model slots, non-bytes parts and pre-hash aggregate overflow.
2. Create an ordinary unbound request, ordinary seal and ordinary pending/run
   replay; NEW combined commands must reject all three with no new event or
   binding. Completed run never receives authorization. Exact combined replay
   still works after expiry/cancellation and returns byte-identical history.
3. Inject failure after request/run/seal allocation, failure-envelope insertion,
   renewal or event creation; all coupled changes rollback. Ambiguous commit
   replay on a fresh connection cannot allocate another target or refresh time.
4. Complete ordered planned-policy derivation: both selected languages, reversed
   or omitted/duplicated rule/detector parts, wrong semantic descriptor, clause
   IDs instead of rule-set IDs, mutated installed pins, mismatched attempt runner,
   mixed-language fiction and deliberate detector duplication. Preserve complete
   accepted-content identity in both language requests.
5. Real initial metadata-only denial and renewal denial: actual target IDs,
   fixed owner reason ordering, no fake empty output, no renewed lease, atomic
   failed attempt, preserved earlier findings and exact subsequent command replay.
6. Competing authorized runs, leaf forks, stale revisions, consumer lock waits
   crossing expiry and new commands against old terminal targets all reject.
   Cancellation/failure still work without new positive authority.
7. Per-action W/F/G and hash-call/hash-byte N/N+1 limits, actual driver expansion,
   bounded fetch slots and no full-history/per-rule-full-bundle hashing. Reserve
   actual frozen occurrence helper work before calling it. Demonstrate intended
   complete bundle positives without hidden member removal or larger retry caps.
8. Real restricted-role USAGE/EXECUTE tests, absence of direct privileges/owner
   membership, hostile defaults and unchanged legacy ACLs. Wrong action through
   another action's SQL function fails even for an otherwise authorized role.

Before source allocation, root/schema owners must explicitly accept or revise
the new command/SQL return pair, finite quotas/fetch plan, key spelling,
initial-denial transaction and reason mapping. They must check required owner
changes remain additive; no unversioned attempt-policy extension is allowed.

Still UNAVAILABLE: installed root/publisher/administrator identity; genuine
independent admission provider and restore procedure; actual administrative
verification ingress; installed-runtime provenance; current #399 production
worker/reader; source acquisition/custody integration; runtime barriers,
old-parent exclusion, durable recovery journal/late bytes, installer and native
controller. No SQL/readback receipt solves these. Full R07/R08/R13/R19, G0/G1/G2,
422-case coverage and stage readiness remain separate, unaccepted obligations.

<a id="al03-appendix-c"></a>
## Appendix C. Cohesive AL-03 allocation — retained historical text

Historical labels, snapshot dates, temporary paths and numbered section references
in this block belong to the original record. They do not override the current
precedence, scope or implementation status in sections 0–4 above. Section references
inside this block refer to that same block unless an original document is named.
The complete source text follows, with heading levels demoted for this document.

### AL-03 — cohesive accepted-ledger SQL boundary allocation

2026-09-26 PKT. PROPOSED; two exact pre-code closures below remain required.
No repository, SQL, DB, key, test or remote change; earlier design approval is not allocation/authority.

#### 1. Inspected owners and dependency base

Authority design: /tmp/scanipy-authority-ledger-design-N7j0v7/AUTHORITY-LEDGER-DESIGN.md
(741 lines, SHA16cccece8c5af9772518e241ee791d470db2f0ad1108b1e0924dc579006332ac);
amendment01 (544, SHAf95f1595ba23e699675529c80e0aca768df32064816805cfefef11295932a9a9).
AL-02 commit66607b9537242d7ca05c93b2da03722b841dd83c directly extends owner58b552c919a99f244c12cbdb11f9fb3eb8cdd64f.
Occurrence3992e5c4363264cde23d8d3e78b8cddb77828de0 retains reviewed0004/0005 SQL;
operations SHA67bc29b0213c61513182d6af061726efdca61acaf80880f47b2e9fe2c71fcc5d.
Accepted main595484bd currently has only migrations0001–0003. AL-02 is NOT a
descendant of occurrence3992e5c: integrate actual reviewed dependencies normally,
not copied models or independently recreated migrations; reconcile conflicts first.

#### 2. Verdict and minimum decisions before source allocation

Do NOT implement the original tables-only AL-03 while deferring every writer.
Propose actual append/head, publication, request, seal, authorization/denial/renewal
and bounded reads in one SQL boundary: former AL-03/04/05 SQL, not their external
administrative/operational adapters. Root must approve this consolidated scope.

AL03-C1 — Freeze six read SQL signatures, result columns/null shapes, selectors,
not-found/conflict behavior and per-read input/fetch/generated/hash quotas.
The design names read_publication_receipt_v1, read_exact_bundle_v1,
read_authority_event_v1, read_request_binding_v1, read_execution_authority_v1,
recheck_execution_authority_v1, but only prose selectors/public Python protocol.
Do not invent a permissive jsonb row, reuse mutator quotas silently, omit original
signatures/material, or construct a fake ExecutionVerificationContext from hashes.

AL03-C2 — Freeze privileged installation of the unadmitted namespace row
and exact forced-RLS treatment of global versus customer rows. No new runtime
action, automatic namespace creation from scan input, fixture-only SQL INSERT,
inferred administrator/root, or NULL tenant authority. Existing verifier._execution
requires customer scope; global publication/history cannot silently become a
customer execution. Installer identity remains a later real operator choice.

Review physical column/check/index projection and SQL helper reservations with
implementation; these are not new wire semantics. RES intent-retirement and
256/512MiB replay-budget gaps are runtime-store issues, NOT AL read blockers.

#### 3. Exact proposed files after AL03-C1/C2 and root allocation

All14 paths NEW; existing owner codecs/0004/0005 resources remain unchanged:

1. docs/bhmea/ACCEPTED-LEDGER-SQL.md — closed C1/C2, DDL/ACL inventory and evidence.
2. db/migrations/versions/20260926_0006_accepted_ledger.py
3. db/migrations/versions/accepted_v1_shapes.json
4. db/migrations/versions/accepted_v1_tables.sql
5. db/migrations/versions/accepted_v1_validation.sql
6. db/migrations/versions/accepted_v1_history.sql
7. db/migrations/versions/accepted_v1_operations.sql
8. db/migrations/versions/accepted_v1_reads.sql
9. db/migrations/versions/accepted_v1_execution_bridges.sql
10. db/migrations/versions/accepted_v1_acl.sql
11. services/scan/accepted_inputs/ledger_repository.py
12. tests/unit/test_accepted_ledger_repository.py
13. tests/integration/test_accepted_ledger_sql.py
14. tests/integration/test_accepted_ledger_security.py

Reserve revision20260926_0006 with down_revision20260925_0005 only after checking
the then-current migration head; no parallel head or renumbering old revisions.
Migration imports only its frozen resources, never mutable runtime schema code.

#### 4. Physical rows, exact identities and history

Use the five approved scanipy_accepted_inputs tables, not a generic event blob:
registry_namespaces; artifact_versions; bundle_versions; authority_events;
request_bundle_bindings. Namespace UUID→registry/scope/org is immutable and
NULL-safe unique; only exact policy/admission heads and coordination fields move.
Each changed head advances coordination once; identical replay advances nothing.
Start unadmitted with null heads/digests/epoch and zero revisions.
Artifact key(namespace,kind,artifact_id,version) cannot change bytes; bundle key
and ordered complete S/detector/rule/model membership preserve all raw contents.
Arrays are NOT FKs: under namespace lock validate every referenced same-scope
member, then immutable guards preserve closure. No sixth table without approval.
Event kind is exactly policy/admission/approval/seal-authorization/
execution-authorization/execution-denial. Derive closed typed columns/NULL matrix
from actual schemas.py; raw record bytes/domain must equal every projection.
Retain original policy/checkpoint signatures and approval publication evidence.
Each event/binding table has UNIQUE(namespace_id,operation_key); namespace lock
plus bounded exact-key lookup in BOTH enforces cross-table/action uniqueness.
No cross-table UNIQUE exists or sixth index table is implied; changed bytes conflict.
Original request binding has unique(org_id,request_id), original SEALED/raw hash,
actual request ID and immutable bundle/approval/head references; no restamping.
Positive chains: unique initial target/attempt, unique predecessor successor and
target/work_revision; same attempt/token/run/input on renewal; indexed leaf lookup.

#### 5. Function-only writes and transaction facade

Implement unchanged AL-02 seven fixed functions, each(command_bytes bytea,parts bytea[]):
install_policy_v1; record_admission_v1; publish_builtin_bundle_v1;
create_bound_request_v1; seal_bound_capture_v1; authorize_detector_run_v1;
renew_authorized_execution_v1. Each returns(record_bytes bytea,replayed boolean)
with the existing action-specific POLICY/ADMISSION/PUBLICATION/SEALED/
SEAL_AUTHORIZATION/EXECUTION-or-DENIAL bytes, never a supplied receipt or grant bit.
Facade validates original AL-02/returned owning bytes and uses fixed signatures;
one mutation/fresh caller transaction, no autocommit/internal commit,15s/2s timeouts.
History replay precedes new eligibility, uses original complete bytes and never
calls lower mutation. New command rejects any preexisting unbound/replayed lower
request/seal/run; actual returned IDs enter generated frames before atomic commit.
All bundle languages/rules validate; one explicitly installed-supported language
per detector/request, complete inventory once, exact planned-policy derivation.
Initial denial creates actual pending metadata run, DENIAL+failed run/attempt,
no child or fake empty output. Renewal denial never extends either lease.
Implement amendment01 reason precedence/failure envelopes byte-exactly.

#### 6. Locks, roles and execution-owned bridges

Five new reserved NOLOGIN/NOINHERIT/NOBYPASSRLS nonadministrative roles:
scanipy_accepted_owner, _policy_admin, _publisher, _resolver, _reader (full prefix).
Refuse existing roles; grants follow amendment01§7. Accepted owner gets execution
USAGE plus ONLY six enumerated signatures/two fixed-live bridges, not v1_lock.
lock_accepted_capture_context_v1(uuid,uuid,uuid,bigint,bigint) requires zero live
detector runs; lock_accepted_detector_context_v1(uuid,uuid,uuid,bigint,bigint,uuid,uuid)
requires target to be the ONLY pending/running run, including unbound competitors.
Return exactly original§8 actual-row control fields; no raw blob/verified flag.
Lock namespace/head→request→capture→work→attempt→runs→consumer; UUID order within
plural classes; fresh clock after final wait, recheck all scope/fence/expiry.
Parent-only cancel/fail/expire remains usable and never acquires AL afterward.
Keep owner-level history UPDATE/DELETE/TRUNCATE refusal, forced RLS, qualified
SQL/fixed search_path; no service owner membership/direct DML/REFERENCES/DDL.
Scrub ONLY exact new objects; never rerun execution_v1_acl.sql namespace-wide.
Downgrade requires empty new history/no dependents, exact own grants/key removal,
unaffected old body/owner/ACL preservation; no CASCADE or security removal in place.

#### 7. Required positive EXECUTION FK spine for later DB-BAR

authority_events must expose UNIQUE(namespace_id,kind,id,org_id,codebase_id,
request_id,capture_id,seal_id,work_item_id,work_attempt_id,detector_run_id,
capture_lease_id,record_digest). Positive detector EXECUTION requires all nonnull,
customer scope and exact actual record equality; event_id→id, authorization
domain digest→record_digest, NEVER raw ArtifactRef SHA. Other kinds retain their
own closed NULL shapes. Retain token/revision/input/policy/expiry columns too.
Add run UNIQUE(org_id,codebase_id,request_id,capture_id,seal_id,work_item_id,work_attempt_id,id)
and lease UNIQUE(org_id,codebase_id,request_id,capture_id,work_item_id,work_attempt_id,fencing_token,id).
Never fill capture_detection.work_items.capture_id (correctly NULL today).
Later DB-BAR immediate FK uses this full key via trusted DDL REFERENCES authority,
not runtime REFERENCES or execution_owner→AL read/member privilege.
Owning-route note5a0c9df6 requires historical EXECUTION prelock in AL phase even
for stale-leaf NEW; only-live-target check; actual locked expiry receipt output.
Its claim/recipe/acquisition/release wire is still unclosed and OUTSIDE AL-03.
No barrier table/function/runtime-claim grant or cleanup authority is added here.

#### 8. Bounded validation and external authority boundary

SQL independently validates canonical lexical JSON before duplicate-key loss,
exact framing/roles/membership/digests/rows; jsonb::text is not owner encoding.
Cross-test with actual AL-02/accepted codec/occurrence codec; no imported Python
inside SQL, detached partial validator, caller callback or verified=true shortcut.
Apply amendment01 W/F/G/control slots and100000 SHA calls/134217728 input bytes;
reserve all unchanged occurrence-helper work BEFORE calls, including malformed
paths. Bound arrays/lower bounds/nested values/escaping before copying/hashing.
C1 separately closes read quotas; no full-history scan or fetch-after-budget check.
Actual trusted administrative crypto/admission services run outside locks; SQL
does not authenticate them. Missing root/actor/profile/provider/ingress/runtime
means no activation; no real login memberships or invented model acceptance.
Keep actual ExecutionAuthorityReader protocol, LIVE/ExecutionBinding codecs and
read→verify→recheck/currentness obligations; AL-03 repository is not that provider.
Do not change run_isolated_verifier's operational refusal or source/native paths.

#### 9. Required acceptance and next dependency order

Use real isolated PostgreSQL restricted roles, current migrations and actual owner
bytes; diagnostic signed test material is not an operator acceptance/publication.
Test all seven committed result pairs, cross-language whole-bundle positives,
SQL/Python byte parity, duplicate/malformed/oversize arrays and W/F/G/hash N±1;
cross-tenant/global misuse, owner/ACL/default privilege attacks and rollback.
Force failures after request/run/seal allocation, renewal and generated framing;
no partial rows, invented IDs or lease extension. Replay lost acknowledgement on
fresh connection after cancel/expiry; changed input/key/low-level adoption fails.
Interleave policy/revoke/admission/consumer waits, leaf forks and two live targets;
fresh post-lock time, denial retention and unchanged prior findings mandatory.
Check full positive FK mismatches and unchanged old ACLs/operations before/after.
Owner slot mutation and return corruption fail; no ignored invalid derived fields.
C1/C2 freeze→reviewed dependency integration→14-file SQL→independent security/code/
real-PG review→separate installed administrative/provider/reader/runtime/barrier.
No fixture-only completion or full R/C/G, Java/native, custody, restore/stage claim.

<a id="al03-appendix-d"></a>
## Appendix D. Closed C1/C2 reads and installer — retained historical text

Historical labels, snapshot dates, temporary paths and numbered section references
in this block belong to the original record. They do not override the current
precedence, scope or implementation status in sections 0–4 above. Section references
inside this block refer to that same block unless an original document is named.
The complete source text follows, with heading levels demoted for this document.

### AL03-C1/C2 — exact reads and unadmitted installation

2026-09-26 PKT. PROPOSED for root/peer review; no code, tests, DB or activation.
Closes only the two gaps in AL-03-ALLOCATION.md f7ece9da52023fc62ce4e6b4fc9b5f2497589cfa01d052938e8bb5f29dd2d24e.
Basis: approved authority741/amendment544, AL-02 commit66607b9, actual owner58b552c
and occurrence3992e5c. Existing seven mutating actions and owner wire types remain.
All referenced schema constants/shapes below are actual accepted_inputs.schemas;
models/codec are the owning Python types, not reconstructed substitutes.

#### 1. Common SQL/read boundary

All six live in scanipy_accepted_inputs, SECURITY DEFINER owned by scanipy_accepted_owner,
with fixed search_path=pg_catalog,scanipy_accepted_inputs,pg_temp; non-STRICT explicit NULL guards.
R1 grants:publisher/reader/resolver; R2–R4:reader/resolver; R5–R6:resolver ONLY (scanipy_accepted_ prefix).
Fully qualify cross-schema names. No overload, arbitrary query/selector callback,
latest-bundle lookup, runtime/FS/process operation or mutation hidden in a read.
One fresh caller transaction, statement_timeout15s/lock_timeout2s, no autocommit.
Authenticated installed dispatcher sets transaction-local scope (§8); every p_namespace
must equal it before lookup. Customer p_org must equal both dispatch and namespace org.
Historical reads ignore current grant/lease eligibility; they never refresh history.
Each returns exactly one row with the columns below; no absent-as-NULL/empty success.
Only R1 selector XOR and R6 SQL void have explicitly permitted SQL NULL behavior.
All bytea values are original bounded bytes; digests are exactly32 raw bytes on SQL
wire and lowercase64hex in owning JSON. Raw SHA and D(schema,bytes) stay distinct.

R1 read_publication_receipt_v1(p_namespace uuid,p_publication_key uuid,p_approval_event_id uuid)
  RETURNS TABLE(record_bytes bytea)
Exactly ONE selector after namespace is nonnull. Resolve the approval row by its
unique(namespace,publication_key) or typed(namespace,approval,id), respectively.
Return original PUBLICATION, validate all selector/row/APPROVAL links and stored
domain digest. Never substitute APPROVAL or regenerate published_at. No history walk.

R2 read_exact_bundle_v1(p_namespace uuid,p_bundle_id uuid,p_content_digest bytea)
  RETURNS TABLE(spec_bytes bytea,detector_blobs bytea[],rule_blobs bytea[])
Arrays are nonempty,1-D,lower-bound1,nonnull elements, original manifest order;
framed S already retains exact model bytes, not a fourth manufactured model array.
Validate exact complete AcceptedBundleBytes, bundle ID/namespace/content digest,
all detector/rule/model relations and every declared language using actual bound rules.
Return complete inventory once; reject mismatch/over-limit, never omit a member.

R3 read_authority_event_v1(p_namespace uuid,p_kind text,p_event_id uuid,p_record_digest bytea)
  RETURNS TABLE(record_bytes bytea,supporting_objects bytea[])
Kind is exactly policy/admission/approval/seal-authorization/execution-authorization/
execution-denial. ID is the retained record event_id; digest is its owning D.
Record schema is respectively POLICY/ADMISSION/APPROVAL/SEAL_AUTHORIZATION/EXECUTION/DENIAL.
Exact supporting sequence: policy/admission->[original root signature384bytes];
approval->[original PUBLICATION_INPUT frame, original PUBLICATION receipt];
remaining three kinds->empty bytea[] (nonnull). Nonempty arrays are1-D/lower1.
Validate raw/record domain/row fields; approval frame's APPROVAL bytes MUST equal
record_bytes and its receipt must match actual stored publication links/digest.
Preserve all signature/DER/adoption/inventory bytes inside that original frame.
Data retrieval/shape/link integrity is NOT fresh signature verification/current use.

R4 read_request_binding_v1(p_namespace uuid,p_org uuid,p_codebase uuid,p_request uuid)
  RETURNS TABLE(sealed_bytes bytea)
Customer only; exact scoped request binding, original SEALED frame/raw digest;
validate frame/request/bundle/approval/head references, not present-day eligibility.
SEALED contains original publication and resolution evidence, not replacement LIVE.

R5 read_execution_authority_v1(p_namespace uuid,binding_bytes bytea,admission_bytes bytea)
  RETURNS TABLE(ledger_bytes bytea,live_bytes bytea,reference_time text)
binding_bytes is canonical JSON of exact EXECUTION_BINDING shape; admission_bytes
is exact ADMISSION_EXPECTATION shape. Neither adds schema keys absent in these
actual owner dictionaries. Decode with owning rules, not a new authority model.
ledger_bytes is canonical LEDGER_EXPECTATION shape; live_bytes is actual LIVE
four-object frame; reference_time is exact owner UTC microsecond instant(27ASCII).
All fields nonnull; ledger.binding and its three dependent nullable fields MUST be
present here. No InstalledTrust, runtime profile or independently installed checkpoint
is invented from DB rows. AdmissionExpectation is supplied by the real provider.

R6 recheck_execution_authority_v1(p_namespace uuid,binding_bytes bytea,admission_bytes bytea,
  prior_ledger_bytes bytea,prior_live_bytes bytea,prior_reference_time text) RETURNS void
Input shapes are R5's actual owner shapes. Freshly repeat R5 checks under locks;
require byte-exact prior ledger/LIVE equality and admission/binding equality,
fresh reference_time>=prior_reference_time, complete current validity. Return SQL
void only; Python owner method returns None. Never return/restamp a newer context.
No EXECUTION event, lease renewal or current-authorization receipt is created.

#### 2. Exact rejection behavior and consumer assembly

Null/unknown/duplicate/invalid shape, invalid selector XOR or limits: fixed
VerificationError code invalid-input. Missing exact row/duplicate stored match,
wrong requested digest/record linkage: ledger-mismatch; malformed stored bytes:
content-mismatch. These SQL exceptions use P0001 with only the fixed owning code.
Capability/dispatch mismatch uses42501/scope-mismatch without revealing foreign rows.
R5/R6 stale fence/terminal target->fence-stale; changed prior head->policy-stale;
invalid current checkpoint->checkpoint-denied; grant/time failures use actual
grant-denied/policy-expired. Preserve57014/55P03/driver failures as failure, no retry
with larger limits or cached positive. Original details remain private cause data.
Facade maps only known fixed codes; unexpected SQL/row/type failures are fatal.

Before conversion, independently snapshot exact UUID int/str/int/tuple slots of
actual owning models; no caller validator/equality callback or UUID-string repair.
Bound driver bytes/arrays before copying; trusted driver bytea memoryviews need an
explicit bounded contiguous-byte conversion, not arbitrary __bytes__/iterables.
R2 constructs actual AcceptedBundleBytes; R4 supplies exact sealed_authority_evidence;
R3 EXECUTION supplies exact execution_authorization for ResolvedQualifiedRule.
R5 decodes actual LedgerExpectation, not a new trusted-context class. Real installed
adapter combines it with independently loaded InstalledTrust/AdmissionExpectation
and LIVE/reference_time into actual ExecutionVerificationContext. No constructor
or successful historical read authenticates those providers or enables launch.

#### 3. Locked current read and recheck

All reads lock selected namespace first; R1–R4 then read only exact immutable rows.
R5/R6 lock namespace/head/claimed actual EXECUTION and current leaf before occurrence;
request→capture→work→attempt→runs→consumer follows, UUID order within plural groups.
Use actual execution-owned fixed detector bridge; target is the ONLY pending/running
run in its attempt, including unbound competitors. No generic live=false helper.
After final lock wait, resample clock_timestamp and require all18 actual binding
fields, current positive leaf, original SEALED, bundle/approval/publication,
SEAL_AUTHORIZATION, request/planned/attempt/run inputs and scope to agree.
AUTHORIZATION digest is EXECUTION D; request_binding_digest is original SEALED raw SHA.
Build ledger policy_event_id/admission_event_id from actual current retained rows;
build LIVE from exact current policy/signature/checkpoint/signature, with original
signed times unchanged. Check grant evolution/tombstones and policy/checkpoint
validity; effective permission ends at the minimum of both leases/grant/policy/checkpoint.
EXECUTION policy/admission IDs/digests/revisions/epoch must equal current heads;
require resolved_at<=authorized_at<=now and valid grant/checkpoint at issuance and now.
Global/current-scope mismatch fails; a read creates no permission against later change.

Installed adapter reads real trust/admission BEFORE SQL and re-reads both AFTER
SQL locks are released; any config/generation/digest/epoch change fails. No provider,
crypto, filesystem or callback work inside SQL locks. Actual verifier then runs
and recheck compares original context against fresh external state before/after SQL.
Adapter enforces owning30s clock/backward rules; operational verifier stays unavailable.

#### 4. Exact per-call data and generated-work ceilings

Constants bytes: O65536,P131072,A1048576,L262144,C65536 control metadata;
signature384; N20000 maximum selected members plus stricter content/header bounds.
I counts bytea/text argument bytes; UUID/selector/null-presence parameters fit C.
F counts every logical fetched raw payload, even repeated references/cache hits;
C additionally covers ALL fetched/control IDs, lengths, arrays and scalar metadata.
G counts all returned binary/text payload bytes, including unchanged historical bytes.
No driver/protocol/hex-expansion memory guarantee is implied; that adapter is bounded separately.

| Read | I maximum | Closed fetched payload slots F | G maximum |
|---|---:|---|---:|
| R1 |0|APPROVAL O + PUBLICATION O|O|
| R2 |32|complete S+detector+rule aggregate A (models inside S)|A|
| R3 policy/admission |32+24|record<=P + signature384|P+384|
| R3 approval |32+24|APPROVAL O + PUBLICATION_INPUT A + PUBLICATION O|A+2O|
| R3 seal/execution/denial |32+24|record O|O|
| R4 |0|original SEALED A|A|
| R5 |2O|current signed material L + SEALED A + bundle A + planned-policy A + seal A + run-input A + seal-auth O + EXECUTION O + PUBLICATION O|L+O+27|
| R6 |3O+L+27|same exact slots as R5|0 (SQL void)|

Every slot is at most one exact row/frame or the R2 complete ordered aggregate;
no chain walk, latest scan, unrestricted membership join or extra raw fetch in C.
Current slots recover original bytes from actual retained AL commands/rows, compare
their domains to locked occurrence columns; bridges return control, not raw blobs.
Persist validated immutable byte lengths/counts at insertion. Read lengths/IDs,
reserve F/C BEFORE selecting/copying TOAST payloads, then verify actual length.
Generated LIVE/ledger use existing owner lexical/depth32/value20000/string limits
and preflight escaped bytes before encoding; occurrence envelopes keep their own
1MiB rules. All returns must fit G before delivery; no successful partial rows.
No row/event generation; whole read atomic failure if any input/fetch/output limit fails.

#### 5. Hash-work boundary, including malformed paths

SQL read and facade validation EACH get fresh separate ceilings H100000 SHA calls,
B134217728 hash-input bytes. Count every raw/domain/frame validation/repeated role;
pre-reserve before hash or unchanged helper, including early-malformed calls.
Never add facade work into SQL counters or claim one meters the other's execution.
New private SQL hashes charge exact1 and actual input length (schema+LF included).
Control-only bridges use narrow-column parent locks:0 raw fetch/0 hashes, NOT old
v1_lock's whole-row/to_jsonb path. Any expansion needs reviewed pre-reservation.
Frozen owner-helper reservation schedule for facade, definitions M models,D detectors,
R rules; S spec length,T complete bundle bytes,U model bytes,V detector+rule bytes:
- first decode_spec:20000 calls,S bytes before its model count is known;
- AcceptedBundleBytes construction:M calls,U bytes;
- qualified_members:3M+3+2D+3R calls;3U+T+V+2(A+len('scanipy-execution/accepted-content/1\n'))
  +R(O+len(SEMANTIC_BINDING)+1) bytes;
- decode_bound_rule for EACH actual member/language:2 calls,rule+model byte lengths;
- decode_frame:fixed4/10/15 calls for LIVE/PUBLICATION_INPUT/SEALED,len(frame) bytes;
- encode_frame:same role count,preflight final frame length; internal re-decode counted;
- raw/domain digest:1,exact actual bytes/prefix. Owning decode_document/record add0 SHA.
Reserve only from already bounded private inputs; do not invoke a helper to learn
its reservation. Retained M/D/R metadata never replaces actual member validation.
SQL's private codecs have their own explicit per-hash counters; no Python imports.
All language/role/member repeats remain charged; no reduced inventory on exhaustion.

#### 6. Structural installer, separate from seven runtime actions

Private initialize_registry_namespace_v1(p_namespace uuid,installation_bytes bytea)
RETURNS TABLE(namespace_id uuid,replayed boolean), SECURITY INVOKER owned by
scanipy_accepted_owner, fixed owning search_path. No PUBLIC/runtime EXECUTE grant.
Only a separately authorized migration/installation administrator explicitly using
the owner role can call it; no service login/membership is created or chosen here.
Input is existing INSTALLED_TRUST canonical document<=4096 and nonnull UUID; §2 errors apply.
Validate all actual scope/deployment/registry/root-fingerprint/administrator fields;
this DB copy is a configuration declaration, NOT installed trust/key proof.
Add immutable namespace installation_bytes and installation_sha25632byte columns;
retain exact declaration for replay, never use it as the independent trust source.
Fresh transaction sets validated namespace/org RLS selectors, locks any visible
existing namespace row; UNIQUE serializes insertion of an absent scoped key.
Insert only null-head/zero-revision state. Same identity gives exact replay; alternate
namespace ID for same(registry,scope,org) or changed declaration conflicts.
Exact replay returns original namespace even after later admission, without reset.
No policy/checkpoint/signature/event/model publication is inserted by installation.
I4096,F4096+C,G17 logical UUID+bool bytes,H1,B4096; bounds before copy/hash.
No automatic call from a runtime command. Existing seven-action wire is unchanged.

#### 7. Forced RLS and exact dispatch route

All five tables ENABLE/FORCE RLS; accepted_owner is NOLOGIN/NOBYPASSRLS, not a runtime role.
Trusted installed dispatcher authenticates login+tenant/operator before selecting a
configured namespace/capability; no namespace derived from scanned/bundle/user SQL.
It sets SET LOCAL scanipy.accepted_namespace_id to canonical UUID and app.org_id
to customer UUID or empty for a dedicated global transaction; never connection-global.
Entry EXECUTE ACL is checked before definer switch; both selectors are checked before lookup.
Namespace row RLS USING/WITH CHECK: id=selected_namespace AND ((scope='customer'
AND org_id=selected_org) OR(scope='global' AND org_id IS NULL AND selected_org IS NULL)).
Other tables require namespace_id=selected_namespace AND accessible exact namespace;
authority_events additionally uses org_id IS NOT DISTINCT FROM namespace.org_id.
Request bindings require customer and matching nonnull org. Nullable composite FKs
alone do NOT enforce global-org equality; exact insert/row checks preserve that link.
Missing/malformed settings deny. Global history/admin requests use global-only
transactions, never NULL tenant bypass on customer rows or global→customer adoption.
Only accepted_owner has needed table rights; runtime roles have exact function grants,
no SELECT/DML/REFERENCES/DDL/owner membership. Installer is a private owner-only route.
GUCs are NOT authentication: a compromised privileged dispatcher login can set them;
the threat boundary explicitly trusts that installed service, not arbitrary clients.
Unprivileged clients cannot gain capability by forging GUCs. No new sixth mapping table.

#### 8. Review/falsifier requirements and unchanged boundaries

Test all six signatures/NULL/enum/error cases, historical expired/revoked reads,
all supporting roles, missing original signatures and exact complete raw membership;
I/F/C/G/H/B N±1 BEFORE work, repeated cached-role charging, malformed helper prefixes.
Exercise actual restricted PostgreSQL roles, global/customer mismatches, forged GUCs
without capability, installer denial, same-key races/replay and unchanged admitted heads.
Lock waits crossing lease/grant/checkpoint expiry, current-leaf/18-slot mutations,
provider changes around SQL/verifier and backwards time must fail without restamping.
Preserve namespace-locked exact operation-key lookup in BOTH event/binding tables;
no sixth table/cross-table UNIQUE fiction, inverse AL grants or changed DB-BAR wire.
This proposes structural installer/read behavior only. Real identities, independent
provider/restore, administrative crypto, source custody, runtime exclusion and native
activation remain separate; no fixture key, UUID or pure read becomes authority.

<a id="al03-appendix-e"></a>
## Appendix E. September 25 scoped root review — retained record

Historical labels, snapshot dates, temporary paths and numbered section references
in this block belong to the original record. They do not override the current
precedence, scope or implementation status in sections 0–4 above. Section references
inside this block refer to that same block unless an original document is named.
The complete source text follows, with heading levels demoted for this document.

### Root design review — authority-ledger amendment

Status: scoped design approved; implementation and operational acceptance open.
Date: 2026-09-25. Decision owner: root engineering coordinator under
DECISION-BHMEA-01 and the current full Black Hat objective.

Root read all 544 amendment lines. The independent canonical/budget reviewer
also read the complete 741-line original and 544-line amendment, comparing the
actual accepted-input models/framing and occurrence schema/SQL/ACL owners.
No remaining owning-type contradiction was found in the amended design.

Approved exact inputs:

- `AUTHORITY-LEDGER-DESIGN.md`: SHA256
  `16cccece8c5af9772518e241ee791d470db2f0ad1108b1e0924dc579006332ac`.
- `AUTHORITY-LEDGER-AMENDMENT-01.md`: SHA256
  `f95f1595ba23e699675529c80e0aca768df32064816805cfefef11295932a9a9`.

The amendment takes precedence only over its enumerated ambiguities. Root
accepts its seven-action command/SQL result pair, closed role ordering and
W/F/G/hash quotas, selected-language key spelling, metadata-only initial denial,
reason ordering and deny-before-renew behavior. Complete raw accepted content,
actual owning envelopes, strict no-retrospective-adoption and narrow bridges/
USAGE/EXECUTE remain mandatory. One selected language per detector is an
initial cardinality choice, not removal of the full Java AND Python campaign.

Before operational use, implement and verify the explicit helper hash-work
reservation bounds, seven-command framing parity, namespace operation-key
uniqueness, actual restricted-role and rollback/lock tests. A bounded protocol
does not establish measured resource capacity, current installed authority,
native cleanup, source custody or durable client acknowledgement.

This approval allocates no repository files or DB migration by itself. The
next source slice requires explicit ownership against the actual accepted-input
package. Real operator/publisher/root identities, independent admission/restore
control, service logins and runtime/exclusion dependencies remain unavailable.
Do not invent keys, identities, test-provider production authority or adoption
fallbacks. No full R-task, claim, G0–G3 or release acceptance is awarded.

<a id="al03-appendix-f"></a>
## Appendix F. September 26 scoped root review — retained record

Historical labels, snapshot dates, temporary paths and numbered section references
in this block belong to the original record. They do not override the current
precedence, scope or implementation status in sections 0–4 above. Section references
inside this block refer to that same block unless an original document is named.
The complete source text follows, with heading levels demoted for this document.

### Root review — AL-03 read/install contract closure

2026-09-26 PKT / September 25 UTC. Root read the complete 240-line C1/C2
proposal and the 180-line AL-03 allocation, against the approved original
authority design/amendment and actual owner frame/model code.

Reviewed final C1/C2 SHA256:
`56f1057a579f0910f937220251ed2845267d66bb3e9e10e73c5a04e3ecaa61c2`.
The sole independent-review correction changes R5 to binding plus THREE
dependent nullable fields: execution_authorization_digest, policy_event_id
and admission_event_id. All four are nonnull for this current execution read.
Root verified that exact schema/model group and the real encode/decode-frame
hash behavior. No nonexistent fifth nullable field is allocated.

Scoped engineering design approval: six fixed bounded read interfaces; the
owner-only unadmitted configuration installer; its two immutable namespace
columns; null-safe customer/global RLS and trusted-dispatcher boundary.
No sixth table, eighth runtime command or operational trust source is added.
The installer stores configuration, not independent InstalledTrust proof,
and creates no policy/admission/event/model authority or runtime membership.

New fixed execution bridges must use narrow-column locks and the original
predicates, not legacy whole-row v1_lock while claiming zero raw fetch.
Actual generated/fetched/hash work remains metered; malformed paths and all
member/language repeats count. Historical reads/replay do not renew permission.
Real external provider checks stay outside locks and remain unimplemented.

This closes C1/C2 for the proposed cohesive 14-file SQL/function boundary;
it is not a claim that code, migrations, grants or a real provider now exist.
Root must first integrate reviewed dependencies and publish the exact owning
implementation contract before allocating source edits. Required real-PG,
independent security/code, normal local and exact-head remote gates remain.

No current operator, key, login, namespace, policy or trusted installation was
selected or activated. No repository, database, native engine or external state
changed through this design approval. Full R/C/G acceptance remains open.


<a id="al03-appendix-g"></a>
## Appendix G. Lower-helper contrary evidence — retained original audit

The complete source record follows with heading levels demoted only. Temporary
paths and proposal/approval labels retain their original cutoff. Current section
0 supplies precedence, subsequent exact approval and implementation conditions;
this record does not independently activate a database or operational authority.

### AL-03 lower-owner work audit — proposed accounting amendment, not approval

2026-09-26. Read-only source derivation; no database/owner mutation or test run.
Owner tree: /tmp/scanipy-accepted-ledger-sql-UXpsyI at be3c00d, unchanged 0004/0005.
Numbers below are logical selected-byte/work reservations, NOT measured allocation,
PostgreSQL RSS, actual TOAST I/O, latency or installation capacity guarantees.
SQL may keep TOAST references lazy: nevertheless SELECT * is charged conservatively;
the existing AL F definition counts selected raw payloads, not only disk reads.

#### 1. Names and preconditions

A=1048576, O=65536. Prefix D(n)=len('scanipy-execution/'+n+'/1\n').
Q=request_bytes, P=planned_policy_bytes, I=inventory_bytes, W=work.payload_bytes,
Y=work.retry_policy_bytes, X=attempt.policy_bytes: each length <=A.
S=seal_bytes, C=accepted_content_bytes, T=spec+all detector+all rule raw bytes,
E=acceptance_evidence_bytes: S,C,T,E each<=A by actual owner insertion checks.
U=run.input_bytes<=A; Z=generated denial run-failure<=O;
J=generated denial attempt-result<=O; L=generated lease-release exact bytes.
All letters mean byte lengths below. No raw byte becomes a policy/artifact hash.

Live accepted paths must already hold the narrow bridge's parent locks and require
live attempt/work, uncancelled request, active capture/consumer, and zero/one run.
These make work terminal bytes, attempt result, capture retirement bytes and
consumer release bytes NULL. A pending/running target has no terminal payload
under the real functions. Public AL replay invokes NONE of the lower helpers.
Ordinary owner-function-written rows have error_reference=NULL; no reviewed
execution function populates that unconstrained jsonb column. A new narrow bridge
can reject nonnull error_reference by a boolean test without fetching its contents.
That explicit control is needed before claiming the whole-row projection bound.
Arbitrary direct owner corruption remains outside the runtime-capability proof.

#### 2. Shared whole-row path and immutable-trigger costs

operations.sql:301,303–307 select W twice, request, capture, attempt; 316 selects
the consumer in live mode. Thus each v1_lock selects
K=2(W+Y)+Q+P+I+X <=8A (pre-capture I=0 gives<=7A).
operations.sql:324–325 then to_jsonb(w,r,c,a), including bytea hex strings;
consumer is NOT in the returned JSON. Its selected release bytes are NULL here.
This path is not the new zero-raw bridge. Each repeated v1_lock is charged again.

history.sql:5–6 converts BOTH OLD and NEW rows to_jsonb for EVERY UPDATE before
immutable-field subtraction. Count both images, including untouched raw fields.
The tables have no INSERT trigger. UPDATE ... RETURNING * selects another image;
RETURNING id/revision does not return raw payload. These costs are included below.
v1_stages operations.sql:138–140 updates one request, causing two raw row images.
Its recursive/aggregate relational scan is separate from byte/hash accounting;
the existing 15s statement deadline bounds it, not a claimed fixed history count.

#### 3. Exact reachable helper schedules and conservative selected raw bounds

| Helper/path | Selected raw/OLD+NEW images, including repeated reads | Max |
|---|---|---:|
| create NEW | 2(Q+P) RETURNING at281/289 +2(Q+P) update trigger |8A|
| create lower replay (then AL rejects) | existing Q+P+cancellation at283; no nested lock |3A|
| register NEW, no preexisting capture/seal | K with I=0 at406 +(Q+P) at409–410 +2(Q+P) request update434 |13A|
| begin NEW | K at552 +(S+C+T+E) seal SELECT553; both existing-run lookups miss |12A|
| begin lower replay/conflict | preceding12A plus one selected terminal/existing run at558 or567 |78A+O|
| renew live | K at232 +2X attempt update +2(W+Y) work update; live lease has no raw release |14A|
| fail live target | 2K at531/538 +U SELECT532 +(2U+Z) update +2(Q+P) stages update |23A+O|
| finish failed AFTER fail, one target | 2K at149/162 +(X+W+Y) SELECT150/151 +(3X+2J) attempt update/RETURNING +(3W+3Y+2J) work update/RETURNING +L lease update +2(Q+P) stages |32A+4O+L|

Begin's terminal row is bounded by U<=A, result<=A, retained stdout+stderr<=64A
and optional failure_prefix<=O using actual owner API limits. Only one of the two
existing-run branches can hit: the completed hit returns; otherwise lookup567
is unique. A new AL command must reject either replay/completed result, but that
does NOT retroactively remove this pre-rejection selection/copy cost.
The completed branch also constructs up to10000 occurrence UUIDs (operations562),
roughly400001 JSON bytes before fixed keys: it does NOT fit the AL O-control slot.
No occurrence raw result/witness bytes are selected by that UUID query.

Fail's target must be live under held locks, so its raw stdout/stderr/result are
NULL before update; do not apply its bound to an arbitrary terminal replay.
Finish runs only AFTER that target was failed in this same transaction; its
interrupt-other-runs UPDATE201–202 therefore hits zero rows. If it can hit other
targets, this schedule is invalid. capture_leases UNIQUE(work_attempt_id) limits
v1_release_all to at most ONE hash/update; no unbounded row multiplier is allowed.

#### 4. Lower SHA schedule (includes calls hidden in helper expressions)

| Helper | H reservation | B reservation |
|---|---:|---|
| create |5|D(request)+Q +D(planned-policy)+P +3*(D(work-payload)+A)|
| register |6+Dcount+Rcount|D(seal)+S +D(source-inventory)+I +D(accepted-content)+C +T+2E|
| begin |1|D(run-input)+U|
| renew |0|0|
| fail |3|D(run-failure)+Z+2*prefix_length|
| finish failed |2|D(attempt-result)+J +D(lease-release)+L|

create: request/policy envelope hashes272/273; v1_insert_work10 hashes its supplied
digest and inside v1_envelope, then hashes stored payload again15 (3, not2).
register: envelope hashes380–382; spec389; authority391/431; detector/rule395/399.
fail: envelope526, prefix527, conservative second prefix530 even though the approved
truncated=true branch normally short-circuits it. Approved prefix length is zero.
finish: envelope148, release_all107. v1_semantic(attempt-result) adds no hash.
No immutable trigger hashes. Caller-computed input digests are ADDITIONAL AL work.
Malformed paths use the same pre-reservation; never subtract after short circuit.
New work-payload length depends on actual newly allocated request UUID; reserve A
before call, not a helper call made to discover cost. L can be pre-encoded with
the exact actual attempt UUID/token/fixed reason, separately charged if hashed.

#### 5. Composition and proposed minimal closure

Positive authorize invokes begin once: lower-selected12A on successful NEW path;
initial denial invokes begin+fail+finish:67A+5O+L; renewal positive14A;
renewal denial invokes fail+finish:55A+5O+L. The rejected begin branch requires
78A+O selected-raw reservation if existing terminal payload remains selectable.
These are AL-INTERNAL delegate work, not new accepted payloads or returned G.
Current closed F tables cannot truthfully contain these repeated costs in F or C.

Propose preserve AL direct fetched closure F/C and W/G unchanged, but explicitly
add a SEPARATE per-command delegated selected-raw/row-image counter with the above
branch-complete fixed reservations BEFORE calling each unchanged helper. Its
numeric total ceiling and exceptional generated-control allowance require root
approval; none is enabled by this note. Whole command H/B remain unchanged and
charge the exact lower SHA reservations into the same AL hash-work meter.

JSON projection/copy work needs its own explicit accounting, not a fictitious
zero-cost F exclusion. At each v1_lock, bytea payload becomes about2*(W+Y+Q+P+I+X)
hex bytes; original text-column escaping/JSON structure adds more. OLD/NEW trigger
projections repeat analogous expansion. JSONB headers/alignment, intermediate
concatenation and to_jsonb/build-object copies are NOT exactly raw*2 or an RSS
proof. Before numeric copy acceptance, derive a conservative wrapper-level
logical generated-byte allowance covering the fixed image count and existing
owner string origins, then separately test actual bounded driver/PG allocations.
No maximum backing memory or physical I/O guarantee follows from this table.

Alternative requiring separate owner API approval: exact input-aware absence
precheck/fixed narrow lower wrappers could avoid completed-row selection and
UUID-list expansion. The two approved bridges lack request idempotency/run-input
selectors; do not silently add those fields, broaden table grants, change0005,
or claim current return-after-replay checks prevent the original materialization.
Until the delegated raw/control/copy rule is reviewed, affected helper calls stay
unimplemented; independent accepted codec/DDL/facade work can continue.


<a id="al03-appendix-h"></a>
## Appendix H. Approved delegated-work closure — retained final proposal

The complete source record follows with heading levels demoted only. Temporary
paths and proposal/approval labels retain their original cutoff. Current section
0 supplies precedence, subsequent exact approval and implementation conditions;
this record does not independently activate a database or operational authority.

### AL-03 delegated work closure — proposal for explicit approval

2026-09-26; supersedes only WORK-01's proposed accounting mechanism, not evidence.
Source: accepted-ledger tree be3c00d; unchanged execution 0004/0005 SQL/resources.
No code, limits, grants or database state changed. Root approved the hex-pin
direction, not the numeric proposals below. All ceilings are logical admission
credits, not PostgreSQL allocator/RSS/physical-I/O or completion-time promises.

#### 1. Accounting meanings and preconditions

A=1,048,576; O=65,536; L_live=262,144; h=16,384; l=4,096 bytes.
Use WORK-01's Q,P,I,W,Y,X,S,C,T,E,U,Z,J,L raw-length names. L<=l; Z,J<=O.
All variable TEXT copied from an occurrence envelope is separately charged:
request.idempotency_key<=Q, capture.storage_reference<=S, attempt.assignment_id<=X,
run.detector_binding_key<=U, seal.s_version<=S. The accepted16KiB string rule
does NOT apply to these fields. Work idempotency is fixed kind+UUID text.

F_total=F_direct+F_delegate. This explicitly REPLACES the old table's claim that
its F covered ALL fetches. That old table remains the closed F_direct slot list;
none of the delegated raw selection/OLD+NEW images is hidden in control metadata.
M_total=M_direct+M_delegate counts selected scalar/control bytes separately;
M_direct remains O. Row-image generation and canonical-concatenation credits are
additional counters, never substitutes for F_total, M_total or existing H/B.
Repeated reads/roles/OLD+NEW observations remain charged even with cache/TOAST reuse.

Before legacy delegation, the existing narrow execution-owned bridge must reject
nonnull request.error_reference by a boolean test, before whole-row materialization.
It also establishes the previously required live, uncancelled, active-parent,
zero/one-live-run conditions under locks. Then work terminal bytes, attempt result,
capture retirement and consumer release bytes are NULL. Denial finishes only after
its one target was failed, so finish's interrupt-other-live-runs update affects zero.
UNIQUE(work_attempt_id) makes release_all affect at most one capture lease.

NEW create's lower conflict path has no work/attempt bridge before SELECT *.
Its bound relies on ordinary function-only history: no existing execution function
writes error_reference, and original request/cancellation envelopes are <=A.
Arbitrary owner-injected nonnull JSON there is NOT covered by this proof; enforcing
that before create's collision SELECT would need a separately approved fixed owner
precheck/API. Do not pretend the existing bridge accepts a request-idempotency selector.
The same ordinary-history qualification underlies raw stream/array totals stored by
the old APIs; table DDL alone does not independently constrain every stored raw total.

#### 2. Hex pin and explicit row-image generation

Every new AL SQL entrypoint/private route that can delegate has the function setting
SET bytea_output='hex'. Do not modify a 0004/0005 function/config/ACL. PostgreSQL's
function SET restores the caller's setting at return/error. Tests use caller escape.
jsonb.c:923 invokes bytea's output function; varlena.c:393–417 distinguishes modes:
[jsonb source](https://raw.githubusercontent.com/postgres/postgres/REL_16_STABLE/src/backend/utils/adt/jsonb.c),
[bytea source](https://raw.githubusercontent.com/postgres/postgres/REL_16_STABLE/src/backend/utils/adt/varlena.c).
Thus each bytea contributes 2n hex characters plus bounded prefix/quoting; this is
NOT a claim that total JSON construction or allocator copying costs only 2n.

Define B_row=2*(raw payload bytes)+6*(variable TEXT UTF8 bytes)+h. The 6 factor
covers JSON escaping without assuming the duplicate text preserves original spelling.
h covers <=40 fixed columns, keys<=64 ASCII bytes, and fixed scalar renderings<=256
bytes each: 40*(64+256+8)=13,120<h. UUID/int/time/schema/32-byte digest/null fields
and bytea prefix/quotes fit these allowances. No arbitrary jsonb column is included.
For one complete logical row image: r<=10A+h; w<=4A+h; c<=8A+h; a<=8A+h;
live run d<=8A+h; lease<=h. A new Z/J/L payload adds 2*its bytes to that image.

v1_lock produces four row to_jsonb results plus the enclosing build_object:
post-capture <=60A+9h; pre-capture <=44A+7h. These count both the child results
and enclosing logical result. The history guard produces TWO full OLD/NEW images
AND both OLD-minus-mutable/NEW-minus-mutable results: charge <=2*B_old+2*B_new,
even if immutable-field removal shrinks them or an equality test avoids later work.
Typed SELECT/RETURNING row payload copies are charged by F/M; they are not extra
JSON expressions. This counter measures explicit logical representation results,
not undocumented intermediate PostgreSQL allocator operations.

| Helper reservation | F_delegate | Selected variable TEXT + fixed row fields | Image-result credits |
| --- | --- | --- | --- |
| create, both NEW/conflict paths | 8A | 4A+4h | 40A+4h |
| register, including rejected lower replay | 14A | 4A+8h | 84A+11h |
| begin, including rejected completed/terminal lookup | 78A+O | 5A+8h | 61A+9h |
| renew live | 14A | 5A+12h | 108A+21h |
| fail live target | 23A+O | 11A+17h | 192A+4O+26h |
| finish failed after that fail | 32A+4O+l | 12A+24h | 208A+8O+4l+34h |

The begin image bound includes 1MiB for the completed-result UUID aggregate and
enclosing result. There are <=10,000 actual occurrence UUIDs on that ordinary
completed run: JSON text <=400,001 plus fixed keys. Reserve a separate 8O=524,288
delegated control-result maximum BEFORE the call; reject NEW's completed result,
without treating this internal rejected value as an allowed public G expansion.
Other lower control results fit O. No occurrence raw bytes are fetched by that query.
Register's fresh path selects13A; its lower replay path selects8A in v1_lock,
2A request/planned bytes and4A existing seal before rejection. Reserve14A without
assuming an unimplemented pre-call absence proof. Its replay row JSON is only the
lock's60A+9h, below the fresh path's84A+11h; old seal is selected, not to_jsonb.

#### 3. Closed command ceilings, with no reservation refunds

Reserve the helper's entire row above before each call, including unused branches;
do not refund after a short circuit. In particular authorize can reserve begin's
rejected-terminal branch AND later fail+finish despite those paths being exclusive.
This deliberately exceeds the actual successful/denied-path raw totals in WORK-01.

| Command | F_direct from original NEW slot table | Maximum F_delegate reservation | Proposed F_total NEW ceiling (bytes) |
| --- | --- | --- | ---: |
| install-policy | 131,456 | 0 | 131,456 |
| record-admission | 197,376 | 0 | 197,376 |
| publish-builtin | 2,424,832 | 0 | 2,424,832 |
| create-bound-request | 2,424,832 | 8A | 10,813,440 |
| seal-bound-capture | 3,407,872 | 14A | 18,087,936 |
| authorize-detector | 5,636,096 | 133A+6O+l | 145,494,016 |
| renew-detector | 5,636,096 | max(14A,55A+5O+l) | 63,639,552 |

Historical combined replay remains W+G fetched raw plus O control, with NO lower
delegation or fresh closure. Use the larger of that path and the NEW table as the
function's overall bound (install-policy overall328,064; other rows unchanged).
No operation may exceed the common F_total guard144A=150,994,944 even if a future
slot formula is accidentally larger. Old W/G/accepted-content limits are unchanged.
Proposed image-result ceiling512A=536,870,912: authorize's unreclaimed sum is
461A+12O+4l+69h <463A. Renewal denial is400A+12O+4l+60h <402A.
This is sequential logical generated work, not simultaneously resident bytes.

#### 4. Request-scoped bounded history census, not a live-target shortcut

Propose N=65,536 total existing rows across this request's work_items,
work_attempts,detector_runs,detection_occurrences PLUS planned new execution rows.
Authorize, including initial denial, reserves one new run; create creates one work
item on a fresh request. Seal/renewal/renewal denial add no row in those four sets;
initial denial adds no row beyond its already reserved run. This is a NEW explicit unsupported-
work admission rule, not a historical invariant or a finding/coverage assertion.

Run the census in existing execution-owned bridge internals after the request lock,
before any legacy whole-row delegate. Four fixed queries select only id using the
existing org/request fields. Reserve ONE aggregate (N+1)-row ticket before its first
query. Set seen=planned_new_rows; each query uses LIMIT N-seen+1, then increments
seen by its actual returned row count. Stop immediately when seen>N; otherwise
continue to the next fixed table. Thus all four queries collectively emit<=N+1
rows from one ticket; never use unspent_ticket+1, which would allow an extra row.
This is not four N-sized reservations or a refunded reservation.
Never SELECT full rows, aggregate an unbounded ID array,
add a new caller selector, release the parent lock, or pretend count(*) limits work.
The returned bridge shape stays unchanged; a successful invocation simply passed
its internally enforced admission. A repeat bridge call repeats/charges its census.
No proof is claimed for index/executor rows examined before LIMIT: that remains
statement-timeout/real-PG acceptance, distinct from emitted logical control rows.

All ordinary writes in these old operations acquire the same request lock first;
this stabilizes the scoped sets while delegating. v1_lock:309 may then emit at most
N historical run IDs per call, not just one live ID. v1_stages' covered graph is a
set of <=N rows: ordinary begin serializes requests, rejects pending competitors,
returns an existing completed binding, refuses retained partial terminals, and
supersedes the sole previous zero-result failed leaf. Unique supersedes_run_id
prevents forks. Hence <=1 leaf per binding is inductive for function-written history,
not a new table CHECK or a claim about arbitrary owner corruption/cyclic edits.

Propose R=32*(N+1)=2,097,184 logical relational-row credits per command; one credit
allows up to64 logical scalar bytes (UUID pair/ordinal/count/control). Reserve the
known scoped cardinality before each query/helper, never infer it from live count.
The conservative fixed composite schedule is:

| Delegated scoped work | Maximum (N+1)-row tickets |
| --- | ---: |
| at most eight bridge invocations, each with one aggregate census | 8 |
| begin1 + fail2 + finish2 v1_lock historical run-ID passes | 5 |
| two v1_stages: covered seed, recursive set, failed set, identity-work set | 8 |
| begin completed UUIDs, partial-observation join, active-run and failed-leaf sets | 4 |
| finish partial-observation join and conservative interrupted-run predicate pass | 2 |
| remaining fixed parent/lease/bridge scalar lookups and bounded live-target checks | 5 |
| total pre-reserved maximum | 32 |

These are logical rows emitted to the expression/aggregate, not all join probes.
Bridge zero/one-live-target checks must use bounded at-most-two-ID selection, not
an unbounded array. Fixed lookups and the <=16 such live-target IDs fit the last
allowance without any uncounted full-history fetch. The table is a permitted maximum
call schedule, not permission to loop until success or reset a ticket on retry.
Additional bridge/helper invocation must have credits before use, not hide in C.
This counts emitted IDs/aggregate input records and recursive set members; it does
NOT purport to count planner join comparisons, hash-table probes or physical reads.

M_delegate includes those64R bytes PLUS the selected scalar column reservations
in §2. Its largest unreclaimed sum is28A+49h; M_direct=O remains additional.
Propose M_total<=160A=167,772,160: 64R+28A+49h+O=164,448,256 <160A.
The prior O-total-control statement is expressly superseded for delegated work;
no near-A assignment/key/reference is misclassified as a small fixed control.

#### 5. Separate finite canonical-concatenation admission

execution_v1_validation.sql:24–55 repeatedly concatenates growing text. Therefore
the image counter cannot stand in for cumulative canonical text-result work.
For an already bounded candidate with output-length bound n and lexical value+key
token bound v, propose K(n,v)=8*(n+1)*(v+1)+16*n+4,096 text-byte credits.
An unchanged canonical traversal has at most v value/key visits; each visit has
at most eight explicit scalar/key/concatenation text results of length<=n+1.
The linear term covers enclosing text/UTF8 conversions. Depth remains the owner's32.
This is a conservative expression-result bound, NOT JSONB/RSS/allocator accounting.

Count tokens with a bounded linear lexical pass over the actual candidate bytes
BEFORE generic JSON allocation/delegation; retain no per-token list. A key and each
container/scalar consume a token; strings/escapes are scanned, not interpreted as
tokens. Existing owner shape/canonical checks still run. Do not impose the accepted
20,000-value cap on occurrence bytes. Malformed input also consumes its reservation.
For a raw envelope use n=its exact byte length, v=its lexical count. Noncanonical
portable input's canonical form cannot be longer than the original spelling.

| Helper | Canonical traversal reservation, independent of SHA reservation |
| --- | --- |
| create | K(Q,vQ)+K(P,vP)+3*K(Q+512,vQ+64) |
| register | K(S,vS)+K(I,vI)+K(C,vC) |
| begin | K(U,vU) |
| renew | 0 |
| fail | K(Z,64), with generated Z<=O |
| finish failed | K(J,64)+K(l,16) |

The three create terms cover generated work-payload v1_bytes, its envelope's
canonical check, and retry-policy v1_bytes. Fresh UUID text is always36 bytes;
512 bytes/64 tokens safely covers the fixed substituted wrapper before its owning
A-limit check. Lease release is generated by v1_bytes, not an uncounted free hash.
Reserve generated denial bytes/tokens from the closed constant-message forms before
construction; no user traceback/message or arbitrary result array enters them.

Propose cumulative K ceiling2,147,483,648 (2GiB) per SQL command. This supports large
few-field envelopes but explicitly refuses very wide valid envelopes whose unchanged
quadratic helper cannot fit this conservative work allowance. It does NOT declare
all syntactically maximal bundles executable; no member/input is truncated, omitted,
rehash-normalized or retried with a higher limit. Root must approve this new work
admission constraint; until then helpers stay held. The full submitted workload
remains unaccepted where this fixed initial budget cannot support it.

H<=100,000 and SHA-input B<=134,217,728 remain unchanged and separate. Actual
prefix lengths request28/planned35/work33/seal25/inventory37/content37/run30/
failure32/attempt35/lease34 give create B<=5A+162, register B<=6A+99,
initial-denial B=U+Z+J+L+131 and renewal-denial B=Z+J+L+101; H schedules are
5,6+D+R,1,0,3,2. Reserve all before each helper, including malformed paths.

#### 6. Failures, tests and still-open acceptance

Limit/precondition failures use fixed P0001 invalid-input (or existing scope error),
before affected lower helper; transaction aborts, no DENIAL fabricates an accounting
failure. Statement_timeout15s/lock_timeout2s remain; timeout is never authorization.
Mandatory real-PG controls: each F/M/image/R/K N and N+1; exact raw/TEXT near-A
rows; all six helper paths including returned/rejected completed run and large UUID
list and ordinary unbound lower seal replay; 12/13 etc is not a substitute for request historyN/N+1; repeated same-binding
failed runs; scoped sibling identity rows; current locks/concurrency; zero/one target.
Instrument hidden SHA and canonical-expression/row-image reservations before calls.
Verify caller escape restored after success/error; old function definitions/config,
ACLs, raw evidence and signed history unchanged. Confirm error_reference rejection
on every bridge-covered path and explicitly retain NEW-create qualification above.
Run complete intended Java/Python bundle and wide-envelope unsupported-work controls.

These are proposed logical counters, not a claim to bound every PostgreSQL internal
copy, TOAST read, join probe, disk block, process memory or real15s completion. Real
restricted-role/isolated-PG memory/runtime/instrumentation acceptance is still required.
No physical installation, operator trust, DB-BAR/native controller or live verifier
authority follows. No code allocation expansion or historical owner modification.

<a id="al03-appendix-i"></a>

## Appendix I — SQL planned pins versus installed-runtime validation

Date: 2026-09-26 PKT. Root-directed governing clarification; repository
incorporation awaits root readback before this branch is implemented. Appendices
A–H and their exact historical approval cutoffs remain unchanged.

SQL may retain schema-valid null expected pins in immutable request/planned-policy
and seal intent. This is incomplete intent, not runtime readiness. After all
existing complete ordered bundle projection, request/seal, actual attempt-policy,
scope/head/history and live-fence checks, a positive EXECUTION or renewal requires:

- Every binding in the COMPLETE planned-policy binding list has nonnull
  expected_tool_digest, expected_code_digest and expected_image_digest. Checking
  only the selected detector is insufficient.
- BOTH capture_detection_runner and identity_runner have nonnull
  expected_code_digest and expected_image_digest, including a declared
  not-applicable identity policy. These are existing fields, not new defaults.

Null in any one of those required schema-valid fields selects the existing
missing-runtime-pin DENIAL only when no earlier Appendix B section 6.2 reason
applies. Initial denial retains the real NEW running metadata run, DENIAL and
actual fail/finish results atomically; renewal denial does not extend the lease.
Missing fields, malformed pins, projection mismatch or unavailable required
binding/history remain command errors, not this null-pin reason. No positive
authorization may be generated by substituting a pin or reducing the binding list.

SQL cannot observe installed-profile availability or authentic current artifact
measurements. Nonnull planned strings are NOT evidence of installation, and
resolver_artifact_digest identifies the resolver service artifact only: it is
neither a runner/tool pin nor a value to compare across those different domains.
Trusted ingress/controller must check actual current installed configuration and
its exact matching pins. Missing/corrupt required installed configuration or an
installed mismatch not represented by the owning command fields is a command
failure, never invented SQL DENIAL evidence. The SQL positive record alone does
not discharge that separate prerequisite or activate runtime execution.

Exact operation-key replay still returns original committed bytes before current
eligibility, including an original denial after configuration changes. Immutable
request/seal intent cannot be patched during retry; replay is not promotion to a
fresh positive authorization. No callback, GUC authority channel, field, flag,
schema, digest-domain substitution or old 0004/0005 modification is introduced.

Required controls independently null each of the three binding pins (also in an
unselected binding) and each of the four runner pins; preserve the exact intent,
select last-precedence missing-runtime-pin when eligible, and prove no positive
event/renewed lease or committed active initial-denial intermediate. Cover all
nonnull valid intent with DIFFERENT resolver-service versus runner/tool digests,
earlier denial precedence, malformed/missing-field command rollback, atomic denial
rollback, immutable changed retry rejection and byte-exact denial replay without
promotion. Future ingress/controller tests must separately reject unavailable or
mismatched installed configuration; SQL tests must not claim to observe it.

Subsequent root readback approved this clarification and lifted its branch hold
at document SHA-256
5bfbbaaffe7380631d1ba9f2ab7d7e2c54940a825c27997b0ef2b444f72136c0.
That hash identifies the reviewed input before this chronology note. It is scoped
engineering implementation approval, not a new runtime observation or acceptance.

<a id="al03-appendix-j"></a>

## Appendix J — Current-read delegated control and exact bridge schedule

The retained proposal below is root- and independently peer-approved engineering
admission design on September 26, at SHA-256
5596d1aedc3a964f9c9a0fc0725583befc3d55ad48427fa7706058face3d0b6a.
Its pending/proposed labels describe the review input, not a still-open design
vote. Implementation remains held until root reads back this incorporation;
no PostgreSQL/runtime test or operational installation supplied the approval.

Root and canonical_budget_audit read the complete current bridge, renderer,
Appendix D/H and both proposal revisions. The original de6dceb4e9364a82e14efa942b1d257aa58a0b82484fe56940fbf25d1e9f0343
is retained outside the repository as contrary derivation history: it described
twelve instead of ten target columns and understated the conservative JSON
punctuation allowance. The revised ten-column/4096-byte statement below fixes
both without increasing the existing per-representation16384-byte reservation.
Required behavior is fully contained here; the temporary file is not a runtime
or implementation dependency.

This appendix overrides only D's R5/R6 all-selection C and H's eight bridges
with one ticket each. The actual bound is one detector bridge per R5/R6 read,
no nested public meter reset, and at most two bridges per applicable NEW
mutation, each paying separate census and ordered-lock tickets. It preserves
A–I, original owner bytes, direct-C and public I/F/G/H/B limits and all remaining
DB/provider/runtime/installation/nonacceptance qualifications.

### Retained reviewed proposal

### AL-03 current-read delegated-control amendment — proposed, not activated

Date: 2026-09-26. Revision 2 corrects target-column count and the conservative
JSON punctuation allowance; original de6dceb4 remains unchanged alongside this file.
Root must approve the exact delta before R5/R6 implementation.
Governing input is ACCEPTED-LEDGER-SQL.md ad9c68cb7f21ec47633e615d14fcd36b27c3f0d84c53cd6a8436a70bfa7ce2f8.
Actual fixed bridge template: accepted_v1_execution_bridges.sql
66f825663c530be0a5f75d0bbd67fd57380c0c4182ed1e50f5600bb810e6c69a.
Its renderer is 20260926_0006_accepted_ledger.py
34e3c8eaf11af28dd076323bec8aff53bc3380a2ab818412a08f7cdcc3c2ccf1.
No SQL execution, physical measurement or source modification supplies this audit.

#### 1. Actual bridge work, including the missed second ID pass

Both fixed signatures share the template. The detector variant alone adds the
exact supplied run/lease checks and three returned fields; R5/R6 use it only.
The capture bridge is not a fallback for an invalid detector read.

| Source | Selected/produced logical work | Bound and lock relation |
|---|---|---|
| lines13–26; old v1_org6–12 | tenant setting, request locator; seven named request scalar/boolean columns | fixed; request lock first; error_reference is tested, never projected as raw JSON |
| lines32–38 | capture UUID; seal UUID/capture UUID/two32-byte digests | each exact unique request row; no seal/source raw payload |
| lines40–55 | four id-only subqueries, each count result | ONE shared N+1 census ticket, N=65536; LIMIT N-seen+1, stop at seen>N |
| lines57–76 | exact capture, work, attempt named scalar columns | parent→capture→work→attempt order, enum text only; no payload/result/terminal bytea |
| lines78–79 | every attempt run UUID, ordered and locked | SEPARATE <=N emitted-ID pass, stabilized by request lock; not included in the census ticket |
| lines80–84 + renderer target block | at most two active UUIDs; detector variant's exact ten-column target row | fixed bound; zero-run capture versus exactly one supplied live detector |
| lines89–103 | exact ten-column consumer row, fresh clock | consumer lock after runs; terminal/stale/released/expired target fails |
| lines104–115 + renderer result | one17-key result, optionally one20-key result | only UUID/int/digest/UTC instant/closed enum/null; no full row-to-json |

The census emits <=N+1 IDs in total, not four times N. The ordered lock pass
emits <=N, not one live ID. Work/attempt/run/occurrence counts include ordinary
history, with capture's existing sealed path reserving one server-derived NEW
run and detector reserving zero. Parent lock retains the approved ordinary-owner
history qualification. Rows examined by executor/indexes before LIMIT are NOT
claimed bounded by this emitted-row counter.

Bridge raw-payload F=0, SHA H=0/B=0, legacy concatenation K=0, OLD/NEW image
count=0. No old v1_lock/v1_stages/v1_envelope is called. Encode of four/five fixed
32-byte digests is real bounded hex work, not hashing. Tenant cast failure,
missing/foreign parent, N+1, terminal target and lock timeout do not refund work.
The existing new-function bytea_output='hex' pin remains; it changes no old GUC.

#### 2. Proposed closed current-read reservation

C1/C2 previously defined C=65536 as ALL selected control, so this is an explicit
supersession for R5/R6 only, not a relabeling that claims the old all-fetch cap.
Keep C_direct=65536 for accepted-ledger control/IDs/lengths/scalars. Before the
ONE detector bridge per R5 or R6, reserve separately:

- C_delegate_ID=2*(N+1)*64 =8,388,736 logical scalar bytes. One ticket covers
  the aggregate census; the other covers the independent ordered run-ID pass.
- C_delegate_fixed=65,536 for all fixed bridge selections, tenant input, four
  count results, at most two active IDs, result construction and returned copy.
  Fixed selected columns are <128 scalars, each <=64 bytes after bounded enum/
  UUID/int/digest/time rendering; allowance8192. Each result has <=20 keys of
  <=32ASCII bytes and values <=64 bytes: <=4096 raw JSON bytes. Reserve16384 for
  each of base result, detector-extended result and delivered result (49152),
  plus8192 selected fields and8192 fixed framing/count/tenant margin =65536.
- C_total=C_direct+C_delegate_ID+C_delegate_fixed =8,519,808 bytes.
- R_delegate=2*(N+1)+32 =131,106 emitted-row credits. The final32 cover all
  fixed singleton/count/active-target selections above; they are not another
  N-row history ticket. No second bridge, hidden retry or refund is permitted.

This is a logical named-representation reservation, not an exact allocator-copy
or resident-memory bound. R5/R6 get one shared meter each: M_total=C_total for
these control selections/constructions, with C_direct separately enforced.
Existing meter bucket3 can enforce M_total and bucket7 C_direct; bucket5 gets
the exact read R ceiling. A private initializer/reservation extension is enough;
no public input, callback, bridge parameter or configurable caller budget.
The entire bridge reservation is charged BEFORE its first selector/lock call.
Its fixed function does not read caller-owned counters as permission.

ALL public I/F/G/schema/return limits remain C1/C2's exact values. H100000,
B134217728 remain separate and apply to actual owner decoding/frame/bundle work.
Bridge0 raw/SHA/K does not waive those owning validations or move raw into C.
R1–R4 remain unchanged. Current reads do not execute legacy mutable helpers, so
they acquire neither WORK02's large mutation row-image allowance nor a K credit.
R6 invokes the shared private current-read body ONCE under its own initialized
meter, never the public R5 which would reset counters. Its prior ledger/LIVE
decoding/equality and output-free return share the same H/B/C_direct limits.

#### 3. Explicit mutation-schedule correction, ceilings unchanged

The same newly noticed ordered-run pass must be charged in mutations too.
Narrow the actual fixed planner to at most TWO bridge invocations per NEW
seal/authorize/renew command (create/policy/admission/publication use zero).
Each bridge consumes two N+1 tickets, not one. Fixed bridge scalar/result work
fits the existing five fixed-work tickets, precharged once before the first
occurrence call; it is not omitted or charged again as raw payload.

Worst authorize denial: two bridges4 + begin/fail/finish19 + fixed5 =28 tickets,
below unchanged R=32*(N+1); no refunds. Seal uses4+register2+fixed5=11. Positive
renewal uses4+renew3+fixed5=12. Renewal denial uses one bridge2+fail6+finish8+
fixed5=21. Create uses lower1+fixed5=6. Existing M160A/image512A/F_total/K/H/B
remain unchanged; 28*64*(N+1)+28A+49h+O <142A for authorize, below160A.
Do not retain the old prose permission for eight bridges with one ticket each:
that would omit eight ordered-ID passes. More calls need another reviewed plan.

#### 4. Failure, replay and mandatory verification

Combined mutation replay remains historical and calls no bridge. R5/R6 are
fresh current reads, NOT replay; repeated separate calls each pay a full fresh
budget. An exact prior R6 result creates no shortcut around locks/time/current
leaf or provider rechecks. Stale/terminal/foreign/N+1/timeout outcomes remain
failure; no partial current-context return and no synthetic DENIAL from reads.

Required controls: source/call instrumentation proves one R5/R6 bridge and no
nested public meter reset; IDs counted once in census and once again in locks;
separate direct-C, delegate-C, R and H/B N/N+1; admission BEFORE each call;
N-history pass and N+1 failure including sibling identities/occurrences and
server-planned rows; early missing/terminal failure keeps charged reservations;
post-wait expiry; hostile caller escape restored on success/failure; unchanged
bridge shape/grants, old0004/0005 definitions/config/ACLs and original owner wire.
Mutation tests enforce exact two-bridge maximum,28-ticket worst branch and
replay zero delegates. Test actual intended bundles, not only tiny fixture data.

No PG executor/RSS/TOAST/I/O/15-second guarantee is inferred. Real restricted-
role tests and measured runtime remain gates. Provider/crypto/current installed
admission and DB-BAR/runtime authority remain outside this allocation.

### Stored-error classification implementation clarification — 2026-09-26

Root approved this narrow implementation clarification after reading Appendix D's
error contract and the validation source. It does not supersede D, H or J and does
not alter public signatures, schemas, budgets, old execution definitions or ACLs.
The prior complete governing input is
`519dbf5cd94b6fe57a744684eabe07e1abb93344f00ef368896d50b9d6b9d853`.

An actual `v1_charge` ceiling rejection keeps SQLSTATE `P0001` and primary message
`invalid-input`, with fixed private diagnostic DETAIL `accepted-work-limit`.
Dedicated stored-only document/frame/bundle/occurrence wrappers invoke the actual
owner validator once under the existing shared meter. They rethrow that marker
unchanged and map only known malformed-input `P0001/invalid-input` owner errors to
`content-mismatch`. Existing `content-mismatch`/link errors, `57014`, `55P03` and
unexpected driver or SQL failures are preserved. No counter is reset/refunded;
no new hash or lower-helper invocation is introduced by the wrapper.

Callsite provenance is explicit: fetched immutable records, frames, bundles and
occurrence envelopes, including historical replay's `original.result`, use the
stored wrapper. Incoming commands/parts and caller-supplied R6 prior material use
the original input decoder. Shared already-decoded material/link helpers retain
their own original error rules; a constructor or stored label grants no authority.
The Python facade continues mapping only the existing fixed primary codes and
keeps original driver diagnostics in the private exception cause.

Required tests distinguish malformed stored content from cumulative H/B/F/C
exhaustion, including failures inside frame/bundle decoding, exact private detail
preservation, unchanged public code, historical replay, and unchanged input error
classification. This note records implementation direction only: real PostgreSQL,
full-suite, migration/security and operational acceptance remain pending.

### Generated-denial and backward-time corrections — 2026-09-26

Root's source review identified two concrete implementation omissions; five
configured source-order tests retained those failures before correction in
`/tmp/scanipy-al03-root-generated-clock-source-red.xml`. This is source-test
evidence, not a PostgreSQL reproduction. The reviewed source inputs were operations
`b78d09f0f3de33f296a3ec2657242411c343a0ef12f1326cc91f426d9aa1c8a3`
and reads `8950dfdbed003536ee44f5123edb8ea31ea8bc421a14ab5536f244c723981b07`.

Root approved prepaying `K(65536,64)` twice plus `K(4096,16)` before constructing
either fixed generated denial failure/result JSON value. Validate each actual
result's bytes/tokens against those upper bounds afterward. Remove only the two
redundant generated-path `v1_lower_preflight` calls: fail/finish still use their
unchanged `v1_lower_reserve`, including H/B/F/M/images/R, without refunds or meter
reset. All five fixed denial reasons follow this same construction schedule.
No ceiling, original occurrence shape or legacy helper is changed.

Positive seal/initial/renewal compare actual first/latest bridge `db_now` values
and retained SEALED resolution/seal/previous-authorization times as applicable.
The final fresh moment cannot precede the latest bridge observation; renewal's
post-renew observation cannot precede its already sampled pre-renew moment.
R5/R6 also require the actual bridge observation not precede issuance and the
final moment not precede the bridge; R6 retains the prior-reference lower bound.
Detected backwards intervals are command failure, not fabricated DENIAL or a
restamped current record. Lease upper bounds and existing current policy/grant
checks remain. No system clock, extra wire field, provider or authority is added.

Source-order and transaction-local controlled future-observation tests cover the
corrections without changing global clocks or old execution functions. Actual
PostgreSQL and all previously open acceptance gates remain pending.

### Retained occurrence validation qualification — 2026-09-26

Root confirmed that this slice must not duplicate the complete occurrence semantic
codec or widen the fixed bridges. `v1_stored_occurrence` validates bounded syntax,
canonical encoding and the exact schema name; it is not an independent full-shape
or semantic validator. Original NEW inputs receive the actual owning lower helper's
complete validation before commit. Later reads depend on that immutable ordinary
history and rebind retained planned-policy/run-input digests and accepted/seal
scope, IDs and policy material to the actual locked lower commitments.

The fixed bridges expose the reviewed control projection, not the complete raw
seal or a new seal-intent digest. Fetched seal-command fields are protected by
immutable AL history and the explicit accepted/planned/request/authority/material
comparisons, not a claim that every unused seal field is independently rehashed
against a newly exposed lower seal digest. Malformed syntax still gets the stored
error classification above; altered planned/run bytes or compared seal material
must fail their existing commitments. Coherent privileged corruption of both
ownership domains is not a claimed threat guarantee, and no constructor supplies
missing source, approval, runtime or administrator authority.

### Facade input-versus-stored error correction — 2026-09-26

Independent peer review reproduced six error-classification failures and three
passing controls against facade input
`63bc2e2809d36ddeeb956a6cc684c10ff66c7af6cba7b4cf230d5a9d84d33114`.
The unchanged external nine-case source is
`/tmp/scanipy-al03-facade-peer-oMIpgu8Z/test_facade_provenance.py`
(SHA256 `51cc4d7f283eff4a1a3366a14cd47574ea60d0c409c97f510c425c4cfcd7d997`),
with red report `/tmp/scanipy-al03-facade-peer-provenance-red.xml`
(SHA256 `9c2d3f48fcf37755423089e11376a9c17f19bc17df1dee3e524f04c1cc496dc7`).
The separately retained malformed returned-installer-UUID control failed once
in `/tmp/scanipy-al03-facade-peer-installer-red.xml`
(SHA256 `263e4f282870c28dd857d9c5cfb6cbae41ab3cf1e1715a92acd5bf89dca7c7b9`).
These are private-driver unit diagnostics of error provenance, not an authority
bypass or PostgreSQL reproduction. The earlier 185-case reports remain historical.

Root approved explicit private input-versus-stored selection at the existing
`_current` and `_Work.frame` decode sites. R5 returned ledger, LIVE and reference
syntax uses stored-content classification; malformed returned installer UUID
syntax does too. R6 caller-supplied prior material preserves the actual owning
input decoder's errors. The already AL-02-validated incoming publisher frame is
explicitly marked input. Work reservations and hashes remain outside error
remapping, with identical limits, schedules and invocation counts. Known binding,
policy, checkpoint and fence errors are unchanged; a valid but different returned
namespace remains `ledger-mismatch`. No public signature, SQL/ABI, owner codec,
constructor authority or installed identity changes.

Owned regression cases cover the two provenance directions, returned scalar
syntax versus identity mismatch, unchanged valid R5/R6 bytes, both H/B reservation
failures, preserved known binding errors and explicit publisher input provenance.
The original external nine cases plus separate installer case remain unchanged.
The configured final focused run passed 189 cases (179 owned plus those 10
external controls), zero skips/failures/errors, in 10.808 seconds at
`/tmp/scanipy-al03-facade-provenance-final.xml`; Ruff, format and strict facade
mypy checks passed. This is a single overlapping focused run, not 189 new cases
to add to the earlier 185-case totals.
Real PostgreSQL, broad gates and operational/provider acceptance remain pending.

### First PostgreSQL smoke and literal SQL submission correction — 2026-09-26

The first authorized three-node smoke stopped at the first fixture setup under
`-x`: one setup error, zero test-body executions, failures or skips, 15.207 seconds.
`/tmp/scanipy-al03-pg-first-smoke.xml` retains the complete migration failure
(SHA256 `7433aa88c59d06af80226695a9b3ad0947a6f53c13f09f4edfe1b99a32420315`).
Migration input was
`34e3c8eaf11af28dd076323bec8aff53bc3380a2ab818412a08f7cdcc3c2ccf1`.
Fixture teardown passed its database/role OID checks; a subsequent read-only check
of the exact private bootstrap found no fixture databases, roles or connections.
The root-owned isolated cluster was left running; no retry was performed.

Alembic's `op.execute(str)` constructs a SQLAlchemy `text()` expression. Colon
tokens inside the literal validation-resource JSON were interpreted as bind
parameters (`0`, `1`, `null`) rather than PostgreSQL literal text. A separate
database-free compiler regression retained one failure and one passing downgrade
control in `/tmp/scanipy-al03-literal-compiler-red.xml`
(SHA256 `51143a603ccce8dd2739d3b8c8c44ea2e0b8f751141b3270f9071134e508500c`).
This corroborates the submission-layer defect; it does not validate any AL SQL
function's execution behavior.

Root approved only a private migration submission helper using Alembic's supported
literal-colon escape: add one backslash before every colon in a resource statement
before `op.execute`. SQLAlchemy removes that added layer when compiling. Existing
backslashes, JSON, casts and percent signs remain unchanged in PostgreSQL literal
text; percent escaping stays with the normal dialect/DBAPI parameterized path.
The helper covers the frozen SQL resources, shape-registry function and rendered
bridges. Other static migration statements, transaction handling and normal
Alembic execution are unchanged; no raw-driver/autocommit shortcut is introduced.
All resource file bytes and old 0004/0005 definitions/configuration/ACLs remain
unchanged, as do AL schemas, work limits, role grants and authority semantics.

Twenty database-free controls compare complete upgrade/downgrade statement
generation and compilation, require empty bind sets, and check exact named offline
SQL and pyformat percent-escaped text plus its reconstructed literal text. They
include repeated and preexisting backslash-colons, casts, numeric/null JSON values,
Unicode names and literal percent/mapping-like strings. The actual Alembic offline
emitter is exercised under the repository's named/literal-binds settings. These
tests do not substitute for the next separately authorized PostgreSQL smoke.
The final configured focused run passed 209 cases (199 owned and the unchanged
10 external facade controls), zero skips/failures/errors, in 8.216 seconds at
`/tmp/scanipy-al03-literal-submission-final.xml`. Ruff, formatting and strict mypy
for migration/facade passed. Counts overlap earlier runs and are not additive.

### Current immutable-read lock and fixture-name decision — 2026-09-26

Root approved this narrow current decision before its implementation. Immutable
AL records, including the claimed EXECUTION leaf and request binding, are read
under the already-held namespace row lock; they do not independently require
`FOR UPDATE`. This overrides only the earlier R5/R6 wording that those immutable
rows themselves are row-locked. Their content remains immutable, and head/leaf
selection and insertion are serialized by the namespace lock through transaction
completion. Existing exact predicates, fresh-time checks and work reservations
are unchanged. Namespace locks in operations/installation/history and every
execution-store bridge lock remain. No UPDATE privilege is added to immutable
tables, and owner no-op/update/delete/truncate refusal remains required. The
separate proposed DB-BAR positive-event prelock is not changed or implemented.

The second smoke, `/tmp/scanipy-al03-pg-literal-smoke.xml` (SHA256
`bf12972e6ac27cbb270d685bc14ec069130bcbbc97f35de9d21c7cfda1a0db2d`),
recorded one passed test body, one later setup error and one teardown error in
22.852 seconds. Its XML has two testcases and two error elements, zero test
failures or skips; the third selected node did not run. The migration/empty
roundtrip completed. Admission then failed for insufficient table privilege on
an immutable policy-row `FOR UPDATE`; cleanup independently refused its role
inventory mismatch. Neither error is hidden or represented as full SQL success.

The accepted policy-admin test-login formula generated 65 ASCII bytes while the
observed server identifier bound is 63. The actual catalog contained the truncated
63-byte name. A bounded synthetic 64-byte lookup established that scalar `name`
comparison matched it but the ownership-map text-array comparison did not. This
explains the cleanup refusal without claiming that an OID was replaced; the
terminated process's exact original two-character hex suffix/map was not retained.
The 64-byte comparison was a synthetic diagnostic, not the 65-byte generated name.
No truncation-based adoption, deletion or reconstruction of that lost key is allowed.
The residual task database/roles remain root-owned for separate disposition.

Root approved a fixture-only fix: keep existing occurrence login names unchanged;
new accepted logins use `altest_` plus the accepted suffix, `_`, and the complete
32-character UUID hex (at most 61 ASCII bytes). Check actual server identifier
limit before CREATE, and require the returned name/OID to match the created name
exactly before GRANT or ownership capture. Publish staged login ownership and
credentials only after successful commit; failure or ambiguity grants no new
cleanup ownership. Offline controls cover old/new lengths, preserved legacy names,
pre-CREATE limit rejection, returned-name mismatch, exact success and failed commit.
Real owner DML refusal, namespace waits, leaf checks and replay remain mandatory
PostgreSQL gates; no retry or residual cleanup follows from this decision alone.

The unchanged pre-correction source was tested with nine database-free controls:
eight failed and the legacy-name positive passed in 1.906 seconds, zero errors
or skips, at `/tmp/scanipy-al03-lock-login-unit-red.xml` (SHA256
`5d9dabb1dd3b82db7bc3c1c06cf8f128e05b5e11560b73dc6ac7f9b1ab5812c6`).
That report identifies source/static and mocked-driver failures, not additional
PostgreSQL observations. The correction removes exactly ten authority-event
and one request-binding `FOR UPDATE` clauses. Omitting full-line SQL comments
from the corrected operations resource yields SHA256
`a6e860ddb4c3a353fa3be03ebf2bd4d61ee2db3c50b5f539df7ba815f3720159`,
matching the independently predicted eleven-removal result; no other SQL byte
changes are included except the explanatory immutable-read comment.

Both the login lookup predicate and returned role name explicitly use
`rolname::text`; no implicit PostgreSQL `name` truncation can rescue a lookup.
The complete generated batch remains staged through exact readback, GRANT,
commit and connection-context exit. Controlled CREATE/readback/GRANT/commit/close
failures leave the previous ownership and credential maps unchanged. The refined
configured focused run passed 254 cases (218 AL cases and 36 unchanged occurrence
repository cases), zero failures/errors/skips, in 7.155 seconds at
`/tmp/scanipy-al03-lock-login-final-refined.xml` (SHA256
`515abc529ef95e94793ab35829f4f97cce7040c36f7feb8659f084485d2dca0c`).
The earlier 252-case run remains a pre-final-query/refinement checkpoint, not
additional independent coverage. Four immutable-table/column UPDATE-privilege
negatives and two R5/R6 namespace-wait/current-leaf controls were added to the
existing integration modules; all 144 integration cases were collected only,
not executed after this correction. No SQL effectiveness or cleanup success is
inferred from these database-free results.

After preserving the failed cluster's catalog and client-state evidence, root
separately removed that exact disposable container and recorded its disposition
at `/tmp/scanipy-al03-reviewed-pg-6ERTSe5j/FAILED-CLUSTER-CHECKPOINT.md`.
This did not adopt truncated role names or alter application resources. Root
created a new isolated cluster; its existence grants no test execution, migration,
cleanup or operational permission. The old URL must not be reused.

### AL sealing-fixture composition correction — 2026-09-26

The next authorized three-node smoke on the replacement cluster recorded two
passed tests and one failed test, zero setup/teardown errors or skips, in 36.918
seconds. Its report is `/tmp/scanipy-al03-pg-lock-login-smoke.xml` (SHA256
`0ba5a43bbbe4845ef0f00449cd6386401c79fb4c13df57148671abaeeca5fe4b`).
Migration/roundtrip and historical publication/binding passed. The third test
failed while constructing fixture input, before the seal SQL call: the AL fixture
had revised the request's detector/rule content bindings to the actual accepted
bundle but passed that request to the legacy occurrence helper, whose raw content
remains its fixed controlled spec/detector/rule bytes. The unchanged `CaptureSeal`
constructor correctly rejected the detector binding mismatch before the fixture's
later content replacement could run. This is a fixture-composition defect, not
evidence that the production binding guard or SQL contract should be relaxed.
Teardown completed; a separate bounded read-only catalog check found only the
bootstrap/default databases, only `al03_admin` among task-role prefixes, and no
other client backends. The diagnostic connection was closed. Older reports remain
unchanged; this three-test result is not whole-migration acceptance.

Root approved an AL-only correction. Obtain a valid legacy source-evidence
template using the tenant org and codebase, then use one `dataclasses.replace`
to construct the final actual `CaptureSeal` with all coupled fields changed
together: exact requested bindings, planned-policy digest and requested S_version;
actual accepted spec/detector/rule bytes and their content envelope; and the exact
supplied sealed-evidence bytes/hash. The real owner constructor validates this
final composition before the AL command is formed. No invalid intermediate
`CaptureSeal` is constructed or bypassed. The shared occurrence helper and its
twelve prior direct call sites, production models, all SQL, facade and harness
remain unchanged. The global/customer pure-input controls use explicit
tenant-scoped requests and do not call `create()`. An explicit separate TODO
remains: `SqlLedger.create()` currently passes `self.org=None` for a global
bundle, which is invalid for the tenant `RequestInput`. That fixture/call-path
defect is not corrected here; a separate correction and actual global
request/adoption/seal tests remain required. This fix neither establishes global
execution nor changes the existing customer-only production consumer boundary.

Before the fix, eleven focused controls at fixture SHA256
`80c4cf825fe537fbc12396967366dc73fc2061114611290edbf0504d74e18cea`
recorded ten failures and one expected detector-negative pass, zero errors/skips,
in 2.831 seconds at `/tmp/scanipy-al03-seal-fixture-confirmed-red.xml` (SHA256
`eb806138619f233f382a60b7e6dcd57df8843368737912a40e5e90e3b50fdce8`).
An earlier draft red is retained separately; its unreachable test reconstruction
helper was corrected before this confirmed run. After the fixture correction,
all eleven passed in 1.797 seconds at `/tmp/scanipy-al03-seal-fixture-green.xml`.
They cover exact requested identity/version/plan and raw bundle/evidence bindings,
customer/global template selection, independent detector/rule mismatches and all
seven explicit nullable runtime-pin fields without promotion to readiness.

The final bounded offline selection passed 324 cases (229 AL repository, 36
unchanged occurrence repository and 59 unchanged occurrence envelope cases), zero
failures/errors/skips, in 7.074 seconds at `/tmp/scanipy-al03-seal-fixture-final.xml`
(SHA256 `d8bafebf7f00db2f6cfd78a6ce4c433fbf627d68c2b1cc0769e14b560171e4a5`).
Ruff, formatting and diff checks passed. These overlap prior counts, are not
additive, and do not replace a separately authorized PostgreSQL rerun. No further
database connection, retry, broad suite, hook or commit was performed for this fix.

Root and the independent corpus reviewer approved the scoped sealing-fixture
correction at integration SHA256
`11c714286af379f35455de750508d748d7796f85d7860888320d9e80be0386a0`,
unit SHA256 `5fa9fd5e3c5efea93fc30fa41bd03c65784c1a628544e819691b5f060e69b161`
and reviewed document SHA256
`87b8bb8bbb8b7b4674ba9595032835481d9237c6b333f6b67bed379024b1c0a4`.
The independent review reconstructed the exact prior integration file by
replacing only the changed method and verified unchanged unit/document prefixes.
Its eleven focused offline controls passed, zero failures/errors/skips, in 2.641
seconds at `/tmp/scanipy-al03-seal-fixture-peer-final.xml` (SHA256
`b062e9a05915c04cdf4ba28f154ee50dfe81c7d1f7d6080b2fe66ea6af9cb73f`).
The author's 324-case offline evidence above is unchanged; counts overlap.

The subsequently authorized same-three-node PostgreSQL smoke passed all three
test bodies, zero failures/errors/skips, in 41.498 seconds at
`/tmp/scanipy-al03-pg-seal-fixture-smoke.xml` (SHA256
`abbdd429133a99c255e3916b352a95a8345003e3ea3b3c3d4f698ec6e3910bdd`).
This exercised the isolated migration/roundtrip, exact historical publication
and request binding, and initial actual RUNNING run with immutable same-command
replay. Fixture teardown succeeded. A separate bounded read-only PostgreSQL
16.15 catalog check found only bootstrap/default databases, only `al03_admin`
among task-role prefixes, and no other client backends; the diagnostic connection
was closed. The six frozen source/test/document hashes and all earlier reports
were preserved through the run. This is three-test evidence only: the 144-case
integration selection and full-suite/migration/runtime acceptance remain open.

The separate global TODO also has a deeper owning-protocol boundary: merely
using `tenant_org` in the fixture cannot enable direct global execution. Current
AL command codec, facade, SQL and verifier consistently reject that path. A future
global-publication-to-tenant adoption flow requires coordinated explicit owning
schema and composition design, followed by real positive/negative tests; the
existing same-scope operator-adoption record is not that flow. No scope guard,
signed global `org_id=None`, or admission predicate may be removed or rewritten
to make a fixture pass. No such design or implementation is approved here.

### AL lower-run bytea assertion correction — 2026-09-26

The authorized 144-case PostgreSQL selection stopped after 17 cases: 16 passed
and one failed, zero errors/skips, in 203.856 seconds. The retained report is
`/tmp/scanipy-al03-pg-expanded-144.xml` (SHA256
`fc09b759bc390c9f2f7b34feedf9028158d5b6ee209ac9bfa9189f15e926b862`).
The failure was in
`test_existing_unbound_lower_run_is_not_adopted_and_remains_unchanged`:
the expected AL rejection and unchanged counts passed, but the final tuple
comparison used the driver's raw bytea memoryview against
`memoryview(invocation.data)`. That assertion did not establish exact stored
bytes. The test fixture was subsequently disposed; its prior row bytes are not
reconstructed or certified by this correction.

Root separately performed and closed a bounded read-only driver diagnostic on
the isolated bootstrap database. A controlled 26-byte `bytea` value returned a
memoryview with format `c`, while a view of the expected Python bytes had format
`B`: direct equality was false, but `bytes(actual) == expected` was true. This
establishes the representation pitfall, not the contents of the failed test's
previous row. The associated catalog check found only bootstrap/default
databases, only `al03_admin` among task-role prefixes, and no other clients.
No production, SQL, permissions or immutable-row guard change follows from it.

The approved correction is limited to the existing integration test, its
repository unit-test module and this append. A small test-only snapshot helper
retains the exact `SELECT state,input_bytes ... WHERE id=%s` query and converts
each returned bytea value with `bytes`; it does not decode, hash, rewrite or
discard row contents. Before the blocked AL call, the actual snapshot must equal
`[("running", invocation.data)]`. After the same expected rejection, both the
unchanged count assertion and exact equality with that saved row snapshot must
pass. Thus the future PostgreSQL rerun must prove the actual before/after bytes;
normalizing a driver representation does not weaken the byte-equality check.

Four coupled offline controls invoke this actual helper with `c` then `B` views
and the reverse, each with identical data and with one byte changed. Their inert
payload includes NUL and a high byte; the changed-byte cases must remain unequal.
They also verify the exact query/parameters and both returned snapshots. These
tests do not execute SQL or reproduce the prior disposed fixture's contents.
The bounded offline selection passed 328 cases (233 AL repository, including
the four new controls; 36 unchanged occurrence repository; 59 unchanged envelope
cases), zero failures/errors/skips, in 9.969 seconds at
`/tmp/scanipy-al03-bytea-snapshot-final.xml` (SHA256
`ca9a2a27a0523e25734958138416433b308eadb3bbe5b166e67cb1017fcdf44a`).
Ruff and formatting checks passed after formatting only the new query assertion.
An initial collection-count guard expected a summary line, but the configured
double-quiet output listed module counts; it stopped before test execution.
The corrected guard verified exactly 233 + 36 + 59 before the one test run.
No PostgreSQL rerun, broad suite, hook, commit or remote action was performed.
Earlier reports remain unchanged and no acceptance is promoted.

### Actual bytea rerun and second-cluster capacity failure — 2026-09-26

Root subsequently authorized one corrected PostgreSQL case, followed by the
unchanged 144-case selection only after success and verified fixture cleanup.
The single case passed, zero failures/errors/skips, in 31.730 seconds at
`/tmp/scanipy-al03-pg-bytea-snapshot-single.xml` (SHA256
`1c64c7f4c90903188266ffe2d900acc1d92b20633b8edf22d53347fe6ad305c0`).
This new fixture proved actual stored state/input bytes equal the requested
invocation before the blocked AL call and unchanged afterward. It does not
recover the earlier disposed row. The bounded read-only cleanup check exactly
matched the pre-run four bootstrap/default database names/OIDs/owners and sole
`al03_admin` task-role OID, with zero other clients; the connection was closed.

The expanded run collected exactly 43 SQL and 101 security cases. It stopped at
the first failure: 26 passing bodies, one failed body and one separate teardown
error, zero skips, in 549.981 seconds. JUnit therefore has **28 entries**, not
28 executed bodies or 144 completed tests. All entries are from the SQL module;
the security module was not reached. Report:
`/tmp/scanipy-al03-pg-bytea-expanded-144.xml` (SHA256
`958da4a248fb696efb56b76fb0e7463b19e6c3f0f36cca6bfdd3b05df010d09c`).
The three preceding census parameter cases passed. Case
`test_actual_bridge_request_census_n_and_n_plus_one_includes_planned_run[1-True]`
failed at the privileged 65,534-row fixture INSERT, before the bounded AL call
and its expected admission assertion: PostgreSQL could not extend
`base/25881/27022` because the device was full. Teardown separately lost its
server connection while attempting the ownership-checked `DROP DATABASE`.
This is a session-fixture data/WAL capacity failure, not an observed breach of
the 15-second AL operation limit and not a completed admission result.

The exact second root-owned container was
`4dbc2fc3e9f15ce2421963ada8792c9b363426b09a0e17782c7b8865d6d2f651`.
Root's 2026-09-25 23:58:38 UTC inspection found exit status 1 at
23:57:36.335410883 UTC, `OOMKilled=false`; network none/no ports, 1,536 MiB
memory with equal swap ceiling, two CPUs, 256 PIDs and 1 GiB data tmpfs were
unchanged. Logs placed the INSERT DiskFull at 23:57:26.234 UTC, an autovacuum
PANIC writing `pg_wal/xlogtemp.1156` at 23:57:26.238, and startup-recovery
FATAL DiskFull at 23:57:35.135 before shutdown. These are root's actual
inspection/log observations, not additional database tests by this appendix.

Before the failure, authorized host observations found active server CPU while
the pytest client waited. A later single read-only activity query caught a
0.136583-second active `record_admission_v1` call after progress resumed; it did
not identify the previous long-running statement and its connection was closed.
After the failed run, the one authorized cleanup-status connection attempt found
the exact socket absent and established no connection. Cleanup and the failed
fixture's final child/role state are **unverified**; exited tmpfs contents are
unavailable. No restart, removal, forced cleanup or retry was performed here.

All eight frozen source/test/harness/document hashes stayed unchanged through
both runs; this append is the only subsequent in-repository change. The second
failure has its own outside checkpoint at
`/tmp/scanipy-al03-reviewed-pg-6ERTSe5j/SECOND-FAILED-CLUSTER-CHECKPOINT.md`;
the first failed-cluster checkpoint and all earlier reports remain unchanged.
Root owns any exact-target disposal and new-cluster allocation. A proposed
3 GiB data tmpfs / 4 GiB memory-and-swap-ceiling replacement is isolated test
capacity only, not a production-limit change or proven sufficient bound for
the full 144-case workload. Fresh resource review and explicit authorization
remain required; no AL, runtime, authority or full-scope acceptance is promoted.

### AL operation-specific TRUNCATE refusal correction — 2026-09-26

Root later provisioned a third isolated cluster with 3 GiB data tmpfs and a
4 GiB memory/equal memory-plus-swap ceiling, preserving the old stopped cluster.
After explicit authorization, the unchanged 144-case selection ran once on
that fresh cluster and stopped at the next failure: 87 passed, one failed,
zero errors/skips, in 751.113 seconds. All 43 SQL cases passed; 45 security
cases ran (44 passed and one failed), leaving 56 unexecuted. The report is
`/tmp/scanipy-al03-pg-capacity-144-20260926.xml` (SHA256
`2410990454625ad17e984961512f0f1c80e78cce9971e61d11ebcbb6fce24b93`).
This is not a completed 144-case or full-capacity acceptance result. All frozen
source/test hashes remained unchanged during that run. Fixture teardown
succeeded; the one authorized bounded read-only cleanup check matched the
original four database names/OIDs/owner10, sole non-`pg_` role `al03_admin` OID10
and zero other clients. The diagnostic connection was closed; no retry followed.

The failed test was
`test_material_history_owner_noop_update_delete_and_truncate_are_refused[bundle_versions]`.
Its TRUNCATE was rejected with SQLSTATE `0A000` and the exact primary message
`cannot truncate a table referenced in a foreign key constraint`, naming the
`authority_events` reference. The test incorrectly demanded the immutable
trigger's code and message for this earlier FK refusal. PostgreSQL16 documents
that single-table TRUNCATE RESTRICT refuses unlisted referencing tables;
`0A000` means `feature_not_supported`. This is not evidence that the table's
BEFORE TRUNCATE trigger ran. See the
[TRUNCATE reference](https://www.postgresql.org/docs/16/sql-truncate.html) and
[error-code appendix](https://www.postgresql.org/docs/16/errcodes-appendix.html).

Root approved changes only to the existing security test and this append.
UPDATE/DELETE and the FK-unreferenced artifact table's TRUNCATE keep their
original strict codes and immutable-history message. Only single-table
TRUNCATE of `bundle_versions`, `authority_events` or `request_bundle_bindings`
may take the `0A000` branch, with the exact primary message and a detail naming
one of that target's actual closed external FK referrers. Self-references are
excluded. Complete namespace-filtered, ID-ordered logical JSONB-text rows must
be nonempty before every operation and identical after rejection and rollback;
the check does not compare bytea view formats or reduce equality to counts.

One added runtime catalog test requires exactly five enabled-origin,
noninternal BEFORE STATEMENT TRUNCATE-only bindings, without WHEN predicates or
arguments, all pointing to the exact qualified `v1_immutable_history()` OID.
It also checks that actual function's trigger return type, PL/pgSQL language,
closed search path and exact unconditional `P0001` RAISE body. The existing
artifact-table negative supplies actual shared-function execution evidence;
the catalog checks supply binding evidence for the other tables, not a claim
that each FK-blocked guard was individually executed. No production function,
constraint, trigger, privilege, limit or table format changes are authorized.
No CASCADE, multi-table mutation, trigger disabling or fixture sharding is used.

Ruff and formatting checks passed. Configured collection, with database URLs
unset, verified exactly 145 cases: the unchanged 43 SQL cases and 102 security
cases, including the one new catalog test. No test body or PostgreSQL connection
was executed for this correction. The runtime assertion remains subject to
independent review and a later separately authorized PG run. All earlier
failures, unexecuted cases, capacity limitations and global adoption/authority
TODOs remain; no acceptance status is promoted here.

### AL focused TRUNCATE runtime checkpoint — 2026-09-26

After root and independent scoped approval, one authorized five-case PG run
passed all four material-history parameters and the new runtime catalog test:
5 passed, zero failures/errors/skips, in 45.134 seconds. It used the unchanged
third isolated cluster and stopped after that exact selection. Report:
`/tmp/scanipy-al03-pg-truncate-focused5.xml`, SHA256
`d15c47c89fa0243e65e293b21b184164bd638025a844a0855aaf57977249f190`.
All 16 frozen source/test/owner/contract hashes matched before and after the
run; security remained `b06c14c606ac166adbe989c8bd6507c9975a29a4053eeb9198880dae19512ff2`.
This append preserves the preceding contract bytes at SHA256
`7a21ad1ee36037926ada73c2d27b7761f7228ff891127c9d45038e231b82891f`.

The single authorized bounded read-only cleanup query returned the original
four database names/OIDs/owner10, sole non-`pg_` role `al03_admin` OID10 and zero
other clients; its connection closed. The diagnostic's first local assertion
expected numeric JSON OIDs, while PostgreSQL returned string OIDs, and exited
on that representation mismatch. Offline comparison of the already-returned
observation confirmed the exact baseline; no second connection or query ran.
The complete retained bounded observation was:

```json
{"databases": [["al03_bootstrap", "16384", "10"], ["postgres", "5", "10"], ["template0", "4", "10"], ["template1", "1", "10"]], "other_clients": [], "roles": [["al03_admin", "10"]]}
```

No container, configuration, source or test changed, and no retry occurred.
The prior 87/1 result remains preserved. Full 145-case execution still requires
a separate grant; this focused result is not full AL, capacity or authority
acceptance and does not individually execute the FK-blocked TRUNCATE guards.

### AL complete 145-case checkpoint and foreign-scope test strengthening — 2026-09-26

After a separate root grant, one unchanged full selection passed all 145 cases:
43 SQL and 102 security tests, zero failures/errors/skips, in 740.980 seconds.
Report: `/tmp/scanipy-al03-pg-truncate-full145.xml`, SHA256
`0916a2454069614cab0b6f18c695ae757a0ce30094cdf4256788b35fff59461b`.
All 16 frozen hashes matched before and after that run, including security
`b06c14c606ac166adbe989c8bd6507c9975a29a4053eeb9198880dae19512ff2`
and the preceding 3,427-line contract at SHA256
`25448c92f11d12b3d05885899b0afa03bb9b8fb4242c7a086e8e4f3d2b41b8da`.
The one authorized bounded read-only cleanup query and exact string-OID
comparison succeeded, then the connection closed. It returned:

```json
{"databases": [["al03_bootstrap", "16384", "10"], ["postgres", "5", "10"], ["template0", "4", "10"], ["template1", "1", "10"]], "other_clients": [], "roles": [["al03_admin", "10"]]}
```

This result belongs to that exact prior test snapshot. During read-only
lookahead, root identified a test-strength gap: the foreign-scope publication
read used a random absent key and accepted any `VerificationError`, so absence
could mask the intended authorization assertion. A separately allocated
test-only refinement now takes the actual approval's publication UUID, first
reads that same key through the genuine reader context and requires exact
publication receipt bytes, then requires `scope-mismatch` for the same-role,
foreign-org read. The original rollback remains. The actual R1 SQL checks the
namespace before publication lookup; neither production behavior nor absent-key
semantics changed. No other test body or production/harness file was changed.

The stronger test has not yet been PostgreSQL-executed; the earlier 145 passes
must not be attributed to it. Independent review and any later focused runtime
check remain separate gates. All historical failures and cleanup diagnostics
remain retained. This isolated fixture result is not operator/current-authority,
controller/native, full application or submission acceptance.

Ruff and formatting checks passed for this refinement. Configured collection
with database selectors unset still reports 145 cases (43 SQL and 102 security);
no test body, fixture or PostgreSQL connection ran for these checks.

### AL strengthened foreign-scope runtime checkpoint — 2026-09-26

After root and independent scoped approval, one separately authorized PG run
of `test_same_role_foreign_scope_cannot_read_exact_publication` passed:
one case, zero failures/errors/skips, 24.825 seconds. Report:
`/tmp/scanipy-al03-pg-foreign-scope-single.xml`, SHA256
`647a011d8c5b5e1045617af614f882d365163fc8d573fb6f4dd714bb9f8d673c`.
All 16 frozen hashes matched before and after, including security
`b5328d4398d8f7d17d537d7a8a1f3ee4666fc6cf71c7b53840844861e1f0aa8e`
and the preceding 3,465-line contract at SHA256
`dab76315f4f679e74ad503600af7fcb2ef140fea2607f3cb019bb078cb05a490`.
Read-only container checks before and after confirmed the exact third-cluster
identity and unchanged restrictions, running with no OOM or restart. The sole
authorized bounded cleanup query matched all four original database names,
OID strings and owner10, sole non-`pg_` role `al03_admin` OID10, and zero other
clients; its connection closed. No retry or configuration change occurred.

The earlier 145-case report remains attributed to security `b06c14c6` and
contract `25448c92`, not this strengthened snapshot. The full selection and
this specific-case result are distinct reports, not 146 unique cases. No full
rerun of the strengthened snapshot is claimed. Historical failures and all
remaining publication, operational/current-authority and controller gates
remain open; no such authority or acceptance is created by this result.

### AL base-driver descriptor typing correction — 2026-09-26

The normal checkpoint commit stopped in the actual isolated pre-commit Mypy
2.3.1 hook with three errors: `Error.pgcode` was typed as `str | None`, neither
member exposing `__get__`, and `Error.diag` as `Diagnostics`, also without that
method. Other invoked checks passed; HEAD did not advance. This was a genuine
failed normal gate, not a skipped or bypassed checker. The preceding 3,489-line
contract remains preserved at SHA256
`64e7e0a0f1983d4264bbb0bb240ba058635fd7dc4a1df603253c22966b3a0e86`.

The installed `types-psycopg2` version is `2.9.21.20260911`; its actual
`psycopg2-stubs/_psycopg.pyi` SHA256 is
`227e7913e233de91f8c4cecba3d9a50b6b697ec132e84ff0796ddc63671dd2c0`.
Those annotations describe attribute values, not the underlying class
descriptors. Read-only inspection with Python3.11.16/psycopg2 2.9.13 confirmed
the base `Error.__dict__` entries are respectively a `member_descriptor` and
`getset_descriptor`, each owned by `psycopg2.Error`. The earlier general tooling
environment lacked this stub package; its previous Mypy result did not cover
the isolated-hook typing surface.

Root approved only two lookup changes: read the same `pgcode` and `diag`
descriptors from `psycopg2.Error.__dict__` before the unchanged `__get__` calls.
The exact driver-exception class gate, fixed safe code/message mapping, original
private exception causes and cleanup chaining remain unchanged. There is no
instance attribute dispatch, subclass-property fallback, ignore directive,
blanket Any cast, stub change or relaxed checker configuration. This follows
the existing base-descriptor approach for exception cause/context inspection.

The earlier full145 and stronger-single PG reports belong to the prior
`16be3470` facade bytes. No PG test of this new source is claimed; scheduled
combined verification and normal publication gates remain required. No SQL,
owner wire, test, harness, workflow, baseline or runtime authority changed.

Configured collection and execution of the two existing unit modules passed
519 cases (233 repository and 286 command-owner), zero failures/errors/skips,
in 19.098 seconds. Report: `/tmp/scanipy-al03-driver-descriptor-unit.xml`, SHA256
`e9b124f34f95690b0bb9d7e47d0cfbaf5b926864a880e01282bead73fd4b075d`.
Source SHA256 is
`e39d1f9a337b8cab28fcb3ab0369e4ca556f1dbc8d2b96cbf9b40b0e420716eb`.
Ruff/format passed. The actual cached `pre-commit run mypy --files
services/scan/accepted_inputs/ledger_repository.py --verbose` then passed its
isolated hook, reporting no issues in one source file (1.18 seconds). A separate
interpreter-path diagnostic typo exited127 before invoking any test/checker;
it was not a product failure. No dependency installation or hook bypass occurred.

These existing unit controls cover error propagation, cleanup and input/stored
provenance; they are not dedicated live-C-diagnostic or hostile-driver-subclass
regressions. No new tests or outside controls were run. The staged source remains
the old `16be3470` snapshot pending root review/restaging; this scoped hook pass
is not a successful normal commit, full suite, PostgreSQL or canonical gate.

### AL primary-component attribution correction — 2026-09-26

The original header's CMP-DET-02 attribution was incorrect. It is retained here
as correction history, not reinterpreted as an earlier ORCH-03 label or a change
to the historical detector-registry mandate. Root requested this narrow
metadata correction after the PR #426 canonical scope finding. The prior
3,540-line contract at candidate 7c992e1578cd2f7613ad85c93d9928c9902a5aed has SHA256
896089f456a451ffe1fa5224ad9bbe097d0776885bdee791b5b5fd0d7e5ed4af.

The primary owner is CMP-ORCH-03: this is the accepted-input persistence
prerequisite for worker execution, not detector manifest discovery or a
replacement registry. CLAUDE section 12 maps services/scan to orchestration;
DOC-CMP-ORCH-03 sections 2, 3.1 and 5 describe detector/spec resolution and
the version-pinned input fence. Accepted PR #418 used CMP-ORCH-03 for the
same accepted_inputs owner, including verify.py; its final canonical
[review](https://github.com/scanipy/scanipy/pull/418#issuecomment-5841154346)
approved that bounded foundation with CLAR-BHMEA-01 OPEN and no issue closure.
Its accepted merge is 3b0221df12d080b774df34ddafde930703de30d9.

The coordinated scope remains explicit: CMP-CP-03 is the migration/RLS vehicle
for this exact owning schema and cross-owner bridge/ACL boundary; CMP-CI-01
coverage is the ordinary required AL integration job, not a new numbered gate.
DOC-CMP-CP-03 sections 2 and 3.1 preserve application ownership of runtime
writes; DOC-CMP-CI-01 section 3.2 distinguishes ordinary CI from Gates 1-4.
The current AL contract, not a component-label inference, specifies the exact
commands, five tables, seven mutations, six reads, installer and their limits.
The complete comparison scope is the already coordinated 18 paths: the 16-path
AL-03 allocation in section 2 plus its actual two-file AL-02 dependency. It
remains one reviewed migration/bridge/facade/codec/fixture/CI unit; no source,
SQL, schema, ACL, fixture, CI, signature or work-budget behavior changes here.

DECISION-BHMEA-01 preserves compatible historical contracts and requires
explicit current extensions and all applicable review/tests. This correction
does not reassign CMP-DET-02, invent a component or historical TST-AC alias,
resolve CLAR-BHMEA-01/02, or complete any ORCH-03, CP-03, CI-01, C/R milestone
or board item. Refs #399 and #362 remain non-closing references. The ordinary
AL job does not establish full historical Gate acceptance. Actual installed
administration, independent current authority, DB-BAR, native runtime and
Finding/SARIF/provenance integration remain outside this persistence slice.

This proposal was prepared outside the repository while the frozen candidate's
combined full run was active. No repository byte was changed during that run.
Any root application afterward requires normal hooks and the applicable fresh
checks and exact-head canonical approval; this note records no full-run result,
remote acceptance, installation, launch permission or release.
